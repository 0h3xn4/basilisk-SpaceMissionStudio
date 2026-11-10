#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""The 3D View while a run runs: what the run gives it, as it goes.

* :class:`LiveFeed`: a thread-safe buffer between the run (the worker
  thread) and the view (the GUI thread), and the run's optional pacing
  to real time. The view drains it (:meth:`LiveFeed.drain`).
* The probe (:func:`attach`): a Basilisk ``sysModel.SysModel`` added to
  the dynamics task, last in it, only when a feed is given
  (``SimulationService.live_feed``). Every N dynamics steps it reads each
  spacecraft's state message (``r_BN_N``, ``v_BN_N``) and the attitude
  the run's results use (the error-free navigation attitude, else the
  navigation attitude, else the spacecraft state's ``sigma_BN`` in a
  full-attitude run without control; none in a translation-only run) and
  appends ``(t, r, v, sigma)`` to the feed. It only reads messages: no
  number the run computes changes. It is added after the run's random
  seeds are assigned, so it has none and is not in the provenance.
* Pacing: "as fast as possible" (0), or a factor of real time (1, 10,
  100, 1000): the probe sleeps, in slices of at most
  :data:`SLEEP_SLICE_S`, while the simulated time is ahead of the wall
  clock times the factor, and stops waiting as soon as the run is
  cancelled. A run slower than the factor is not made to catch up.

This module is Basilisk-free except :func:`attach`.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

_logger = logging.getLogger(__name__)

#: The pacing choices: label, simulated seconds per real second (0: as fast as possible).
PACING = (("As fast as possible", 0.0), ("1× real time", 1.0), ("10× real time", 10.0),
          ("100× real time", 100.0), ("1000× real time", 1000.0))
SAMPLES_PER_ORBIT = 200  # [-] the probe samples about this often per orbit
PACED_SAMPLE_RATE_HZ = 20.0  # [Hz] with pacing, at least this many samples per real second where the step allows
MAX_SAMPLES = 20000  # [-] the probe samples a run's Duration at most this many times
MAX_PACED_SAMPLES = 100000  # [-] the same, for a run held to real time (watched, so sampled finer)
SLEEP_SLICE_S = 0.05  # [s] the longest the probe sleeps before it looks at Cancel again
CATCH_UP_LIMIT_S = 1.0  # [s] a run this far behind its pace starts its pace again from where it is


def sample_interval_s(period_s: float | None, duration_s: float, step_s: float, pacing: float = 0.0) -> float:
    """How often the probe samples [s], a whole number of dynamics steps:
    ``period_s / SAMPLES_PER_ORBIT`` (``duration_s / 2000`` without an
    orbit period), with pacing at most ``pacing / PACED_SAMPLE_RATE_HZ``,
    and never more than :data:`MAX_SAMPLES` (paced, :data:`MAX_PACED_SAMPLES`)
    over ``duration_s``."""
    step_s = max(float(step_s), 1e-9)  # [s]
    if period_s is not None and math.isfinite(period_s) and period_s > 0.0:
        wanted = period_s / SAMPLES_PER_ORBIT  # [s]
    else:
        wanted = max(duration_s, step_s) / 2000.0  # [s]
    if pacing > 0.0:
        wanted = min(wanted, pacing / PACED_SAMPLE_RATE_HZ)
    wanted = max(wanted, duration_s / (MAX_PACED_SAMPLES if pacing > 0.0 else MAX_SAMPLES))
    return round(max(1, round(wanted / step_s)) * step_s, 9)  # [s] to the nanosecond


@dataclass
class LiveSamples:
    """Samples drained from a feed: ``n`` times, ``k`` spacecraft."""

    times_s: np.ndarray  # (n,) [s] from the scenario's epoch
    position_m: np.ndarray  # (n, k, 3) [m] frame N
    velocity_m_s: np.ndarray  # (n, k, 3) [m/s] frame N
    sigma_BN: np.ndarray  # (n, k, 3) [-] MRP; NaN for a spacecraft without an attitude


class LiveFeed:
    """Samples of a run as it goes, from the probe to the view.

    ``pacing``: simulated seconds per real second (0: as fast as
    possible); ``interval_s``: how often to sample [s] (None: chosen by
    :func:`sample_interval_s`); ``duration_s``: the run's Duration [s];
    ``should_cancel``: the run's cancel flag, which ends any wait;
    ``clock`` and ``sleep``: for the tests."""

    def __init__(self, pacing: float = 0.0, interval_s: float | None = None, duration_s: float = 0.0,
                 should_cancel: Callable[[], bool] | None = None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self._lock = threading.Lock()
        self._samples: list[tuple] = []
        self._pacing = max(0.0, float(pacing))
        self._reference: tuple[float, float] | None = None  # (wall clock [s], simulated time [s]) the pace counts from
        self.interval_s = interval_s  # [s] as asked; None: automatic
        self.interval_used_s: float | None = None  # [s] as the probe chose it
        self.duration_s = float(duration_s)  # [s]
        self.should_cancel = should_cancel
        self.clock, self.sleep = clock, sleep
        self.offset_s = 0.0  # [s] added to the probe's time: a segment's start in a segmented run
        self.names: list[str] = []
        self.attitude: list[bool] = []
        self.extent_m = 0.0  # [m] the largest apoapsis (or distance) at the start, for the view's first camera
        self.count = 0  # samples pushed
        self.slept_s = 0.0  # [s] time spent waiting for the pace

    # -- the probe's side (the worker thread) ---------------------------------------
    def start(self, names: list[str], attitude: list[bool], extent_m: float) -> None:
        with self._lock:
            if not self.names:
                self.names, self.attitude = list(names), list(attitude)
            self.extent_m = max(self.extent_m, float(extent_m))

    def push(self, t_s: float, position_m, velocity_m_s, sigma_BN) -> None:
        """One sample of every spacecraft at ``t_s``."""
        with self._lock:
            self._samples.append((float(t_s), position_m, velocity_m_s, sigma_BN))
            self.count += 1

    def cancelled(self) -> bool:
        return self.should_cancel is not None and bool(self.should_cancel())

    def pace(self, t_s: float) -> None:
        """Wait while simulated time ``t_s`` is ahead of the pace."""
        pacing = self._pacing
        if pacing <= 0.0:
            return
        now = self.clock()
        with self._lock:
            if self._reference is None:
                self._reference = (now, t_s)
            wall0, sim0 = self._reference
        due = wall0 + (t_s - sim0) / pacing  # [s] wall clock
        if now - due > CATCH_UP_LIMIT_S:  # slower than the pace: no rush to catch up
            with self._lock:
                self._reference = (now, t_s)
            return
        while now < due and not self.cancelled() and self._pacing == pacing:
            wait = min(SLEEP_SLICE_S, due - now)
            self.sleep(wait)
            self.slept_s += wait
            now = self.clock()

    # -- the view's side (the GUI thread) ----------------------------------------------
    @property
    def pacing(self) -> float:
        return self._pacing

    def set_pacing(self, pacing: float) -> None:
        """Change the pace while the run goes (it counts from now)."""
        with self._lock:
            self._pacing = max(0.0, float(pacing))
            self._reference = None

    def pending(self) -> int:
        with self._lock:
            return len(self._samples)

    def drain(self, limit: int | None = None) -> LiveSamples | None:
        """The samples pushed since the last drain (at most ``limit``, the
        oldest first), or None."""
        with self._lock:
            if not self._samples:
                return None
            taken = self._samples if limit is None else self._samples[:limit]
            self._samples = [] if limit is None else self._samples[limit:]
        count = len(self.names) or len(taken[0][1])
        return LiveSamples(times_s=np.array([s[0] for s in taken], dtype=float),
                           position_m=np.array([s[1] for s in taken], dtype=float).reshape(-1, count, 3),
                           velocity_m_s=np.array([s[2] for s in taken], dtype=float).reshape(-1, count, 3),
                           sigma_BN=np.array([s[3] for s in taken], dtype=float).reshape(-1, count, 3))


def _orbit(mu: float | None, r_m: np.ndarray, v_m_s: np.ndarray) -> tuple[float | None, float]:
    """The orbit period [s] (None if unbound or without mu) and the
    apoapsis radius (or the distance when unbound) [m]."""
    radius = float(np.linalg.norm(r_m))  # [m]
    if not mu or radius == 0.0:
        return None, radius
    energy = 0.5 * float(v_m_s @ v_m_s) - mu / radius  # [m^2/s^2]
    if energy >= 0.0:
        return None, radius
    a = -mu / (2.0 * energy)  # [m]
    h2 = float(np.sum(np.cross(r_m, v_m_s) ** 2))  # [m^4/s^2]
    e = math.sqrt(max(0.0, 1.0 - h2 / (mu * a)))  # [-]
    return 2.0 * math.pi * math.sqrt(a ** 3 / mu), a * (1.0 + e)


_PROBE_CLASS = None


def _probe_class():
    """The probe's class, made on first use (it needs Basilisk)."""
    global _PROBE_CLASS
    if _PROBE_CLASS is not None:
        return _PROBE_CLASS
    from Basilisk.architecture import sysModel
    from Basilisk.utilities import macros

    class LiveProbe(sysModel.SysModel):
        """Reads each spacecraft's state (and attitude) every
        ``interval_ns`` and pushes it to the feed; reads only."""

        def __init__(self, feed: LiveFeed, states, attitudes, mu, step_s: float, duration_s: float):
            super().__init__()
            self.ModelTag = "liveViewProbe"
            self.feed, self.states, self.attitudes, self.mu = feed, states, attitudes, mu
            self.stepS, self.durationS = step_s, duration_s
            self.intervalNs = 0
            self.nextNs = 0
            self.failed = False

        def Reset(self, CurrentSimNanos):  # noqa: N802,N803 -- Basilisk's names
            try:
                orbits = [_orbit(self.mu, np.array(m.read().r_BN_N, dtype=float), np.array(m.read().v_BN_N, dtype=float))
                          for m in self.states]
                periods = [p for p, _ in orbits if p is not None]
                interval = self.feed.interval_s or self.feed.interval_used_s or sample_interval_s(
                    min(periods) if periods else None, self.feed.duration_s or self.durationS, self.stepS,
                    self.feed.pacing)
                self.feed.interval_used_s = interval
                self.intervalNs = max(1, macros.sec2nano(interval))
                self.nextNs = int(CurrentSimNanos)
                self.feed.start([], [], max((r for _, r in orbits), default=0.0))
            except Exception:  # noqa: BLE001 -- the view must never break the run
                _logger.exception("The live 3D View's probe could not start; the run goes on without it")
                self.failed = True

        def UpdateState(self, CurrentSimNanos):  # noqa: N802,N803 -- Basilisk's names
            if self.failed or CurrentSimNanos < self.nextNs:
                return
            try:
                while self.nextNs <= CurrentSimNanos:
                    self.nextNs += self.intervalNs
                t_s = CurrentSimNanos * macros.NANO2SEC + self.feed.offset_s  # [s]
                states = [m.read() for m in self.states]
                sigma = []
                for state, (msg, from_state) in zip(states, self.attitudes):
                    if msg is None:
                        sigma.append((math.nan, math.nan, math.nan))
                    else:
                        sigma.append(tuple(state.sigma_BN if from_state else msg.read().sigma_BN))
                self.feed.push(t_s, [tuple(s.r_BN_N) for s in states], [tuple(s.v_BN_N) for s in states], sigma)
                self.feed.pace(t_s)
            except Exception:  # noqa: BLE001 -- the view must never break the run
                _logger.exception("The live 3D View's probe failed; the run goes on without it")
                self.failed = True

    _PROBE_CLASS = LiveProbe
    return LiveProbe


def attitude_source(service, handle) -> tuple[object | None, bool]:
    """The message the run's ``attitude_sigma_BN`` comes from, as the
    results take it (``SimulationService._extract_results``): ``(msg,
    from_state)``; ``(None, False)`` without one."""
    if handle.truth_nav is not None:
        return handle.truth_nav.attOutMsg, False
    if getattr(handle, "attitude_msg", None) is not None:
        return handle.attitude_msg, False
    if service.scenario.simulation_mode == "full_attitude":
        return handle.sc_object.scStateOutMsg, True
    return None, False


def attach(service, feed: LiveFeed):
    """Add the probe to ``service``'s dynamics task, last in it
    (``SimulationService.initialize`` calls this after the seeds are
    assigned and before ``InitializeSimulation``). Returns the probe."""
    handles = list(service.spacecraft_handles.items())
    attitudes = [attitude_source(service, handle) for _name, handle in handles]
    feed.start([name for name, _handle in handles], [msg is not None for msg, _ in attitudes], 0.0)
    probe = _probe_class()(feed, [handle.sc_object.scStateOutMsg for _name, handle in handles], attitudes,
                           service.mu, service.scenario.sim_settings.dynamics_task_rate_s,
                           service.scenario.sim_settings.duration_days * 86400.0)
    service.scSim.AddModelToTask(service.dyn_task_name, probe)  # default priority: after every other model
    return probe
