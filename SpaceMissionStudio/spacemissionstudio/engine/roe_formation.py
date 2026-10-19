#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

r"""The ROE formation controller (``schema.scenario.RoeFormationConfig``):
holds a follower at, or moves it between, targets in relative orbital
elements, with the math of ``engine.roe``.

**Measurement.** Each tick both spacecraft's osculating states become
mean elements with Basilisk's ``orbitalMotion.clMeanOscMap`` (first-order
J2, osculating to mean), the same mapping ``meanOEFeedback`` uses, and the
mean ROE are taken from those. Truth states: there is no relative
navigation filter.

**Two laws** (``control_law``):

* ``"impulsive"``, the tool's own guidance (``engine.roe``). At each
  decision point (every quarter orbit while the formation is inside its
  tolerances, one orbit after the last burn of a correction), the mean
  ROE are compared with the active target:

  - an along-track error up to five tolerances, or a relative
    semi-major axis or e vector out of tolerance, is corrected with
    along-track burns over the next two orbits that set ``da``, the e
    vector and the mean longitude together
    (:func:`.roe.in_plane_sequence`): a plain burn pair would leave the
    mean longitude tens of metres off, as ``da`` is off between its burns;
  - a larger along-track error drifts: along-track burns set a drift
    ``da`` (:func:`.roe.plan_drift`, with the J2 state transition matrix
    over ``correction_window_days``), cut back as the target nears so the
    rest takes no less than three orbits, and stopped once stopping now
    (the stop burns still take time to fire,
    :func:`.roe.sequence_dl_shift`) brings it to the target;
  - an inclination vector out of tolerance gets one cross-track burn.

  Each burn is fired as an arc centred on its planned argument of
  latitude, at full thrust for as long as its delta-V needs; a burn
  longer than ``max_burn_fraction_of_orbit`` is split over consecutive
  orbits. The controller records, by argument of latitude, where the
  last orbit was in eclipse, and plans burns only at sunlit locations
  once it knows (the first orbit's burns are planned as if sunlit). A
  burn that still meets eclipse waits an orbit; after three tries the
  plan is dropped and made again. A new target in the schedule drops the
  plan at once. During a correction the ROE can leave their tolerances
  (``da`` between the burns of a sequence, the along-track offset during
  e-vector changes); they come back when it ends.
* ``"continuous"``: Basilisk's ``meanOEFeedback`` (oeType 1, mean
  equinoctial elements), run unmodified. Its target difference is the ROE
  target turned into the deputy's mean elements
  (:func:`.roe.deputy_elements_from_roe`) and both sets into equinoctial
  elements (``orbitalMotion.clElem2eqElem``), refreshed every
  ``target_refresh_s`` because J2 turns the chief's node and perigee.

Both laws fire the follower's ``station_keeping`` thruster as
``engine.formation_control.FormationControlBridge`` does: the shared
:class:`~.orbit_maintenance.ThrusterOnTimeModel` (minimum on-time, one
owner at a time), no thrust in eclipse, propellant from the shared tank
fed back into the hub mass, an ideal inertial force. The follower's
station keeping is put in formation-follower mode with no reference, so
it never fires on its own: the ROE controller holds the relative
semi-major axis, the chief's reboosts included.

**Telemetry** (``engine.service`` turns it into ``{sc}.roe_formation.*``):
the mean ROE and their error from the target in metres, the state
(:data:`HOLDING` ... :data:`CONTINUOUS_FIRING`), the cumulative delta-V,
the closest radial/cross-track approach the current ROE give, the active
target's index and, for the continuous law, the commanded and applied
force.

**Vizard** (``engine.vizard``'s ROE panels): every tick the controller
writes its delta-V against the shared tank's total, the Hill-frame
separation from the chief (R, T, N in km, one scale for the three: twice
the largest extent any target asks for) and the closest radial/cross-track
approach the current ROE give (m, against twice the largest any target
asks for), each as a magnitude within its scale (a negative level shows as
"Unavailable" in Vizard).
"""

from __future__ import annotations

import copy
import math
from typing import List, Optional

import numpy as np

from Basilisk.architecture import messaging, sysModel
from Basilisk.fswAlgorithms import meanOEFeedback
from Basilisk.simulation import simpleNav
from Basilisk.utilities import macros, orbitalMotion

from ..schema.scenario import OrbitIC, RoeFormationConfig, RoeTargetConfig, ScenarioValidationError, SpacecraftConfig
from . import roe
from .orbit_maintenance import (
    LogThinner,
    PhasingKeepingController,
    StationKeepingController,
    _clamp_magnitude,
    _eclipse_illumination_fraction,
    _log_sunlit_transition,
)
from .propellant_bookkeeping import apply_propellant_burn
from .results import TimeSeries

HOLDING = 0  # state: inside the tolerances, nothing planned
PLANNED = 1  # state: burns planned, waiting for their location
IN_PLANE_BURN = 2  # state: an along-track burn fired
OUT_OF_PLANE_BURN = 3  # state: a cross-track burn fired
DRIFTING = 4  # state: drifting to the target's mean longitude
CONTINUOUS_FIRING = 5  # state: the continuous law fired

_SUNLIT_BINS = 72  # eclipse record by argument of latitude, 5 deg per bin
_ECLIPSE_RETRIES = 3  # a burn that meets eclipse this many times drops the plan
_HOLDING_CHECK_FRACTION = 0.25  # [-] of an orbit between decisions while in tolerance
_GLIDE_ORBITS = 3.0  # [-] a drift's da is cut back to close the rest in no less than this
_DIRECT_DL_FACTOR = 5.0  # [-] dl errors up to this many tolerances are corrected without a drift
_DAY_S = 86400.0  # [s]
_PLACEMENT_ITERATIONS = 6  # follower_orbit's mean/osculating correction (below a millimetre in two)


def mean_elements(r_m, v_mps, mu: float, req: float, j2: float) -> Optional[roe.MeanElements]:
    """Mean classical elements from an osculating state (``clMeanOscMap``,
    sign -1); ``None`` when the state is not a closed orbit."""
    try:
        osc = orbitalMotion.rv2elem(mu, np.asarray(r_m, dtype=float), np.asarray(v_mps, dtype=float))
        if not (0.0 <= osc.e < 1.0 and osc.a > 0.0):
            return None
        mean = orbitalMotion.ClassicElements()
        orbitalMotion.clMeanOscMap(req, j2, osc, mean, -1)
        mean_anomaly = orbitalMotion.E2M(orbitalMotion.f2E(mean.f, mean.e), mean.e)
    except (ValueError, ZeroDivisionError):
        return None
    values = (mean.a, mean.e, mean.i, mean.Omega, mean.omega, mean_anomaly)
    if not all(math.isfinite(x) for x in values):
        return None
    return roe.MeanElements(*values)


def equinoctial_target(chief: roe.MeanElements, target_roe) -> List[float]:
    """``meanOEFeedback``'s ``targetDiffOeMean`` for oeType 1 (``[da/a,
    dP1, dP2, dQ1, dQ2, dl]``, deputy minus chief) that puts the deputy
    at ``target_roe`` (dimensionless) from ``chief``."""
    deputy = roe.deputy_elements_from_roe(chief, target_roe)
    sets = []
    for elements in (chief, deputy):
        classic = orbitalMotion.ClassicElements()
        classic.a, classic.e, classic.i = elements.a, elements.e, elements.i
        classic.Omega, classic.omega = elements.raan, elements.argp
        classic.f = orbitalMotion.E2f(orbitalMotion.M2E(elements.mean_anomaly, elements.e), elements.e)
        eq = orbitalMotion.EquinoctialElements()
        orbitalMotion.clElem2eqElem(classic, eq)
        sets.append(eq)
    c, d = sets
    return [(d.a - c.a) / c.a, d.P1 - c.P1, d.P2 - c.P2, d.Q1 - c.Q1, d.Q2 - c.Q2, roe.wrap_pi(d.l - c.l)]


def follower_orbit(chief_orbit: OrbitIC, roe_m, req: float, j2: float) -> OrbitIC:
    """The follower's osculating classical elements that put it at
    ``roe_m`` [m] from a chief on ``chief_orbit`` (classical elements):
    the chief's elements to mean (``clMeanOscMap``, sign -1), the
    follower's mean elements from the ROE
    (:func:`.roe.deputy_elements_from_roe`), and those back to osculating
    (sign +1), corrected until mapping them back gives the follower's mean
    elements. Placing it with osculating differences instead would start
    the formation off by the J2 short-period terms, hundreds of metres."""
    if chief_orbit.type != "classical_elements":
        raise ValueError("the chief's orbit must be given as classical elements")
    osc = orbitalMotion.ClassicElements()
    osc.a = chief_orbit.semi_major_axis_km * 1000.0  # [m]
    osc.e = chief_orbit.eccentricity
    osc.i = math.radians(chief_orbit.inclination_deg)
    osc.Omega = math.radians(chief_orbit.raan_deg)
    osc.omega = math.radians(chief_orbit.arg_periapsis_deg)
    if chief_orbit.anomaly_type == "mean":
        mean_anomaly = math.radians(chief_orbit.mean_anomaly_deg)
        osc.f = orbitalMotion.E2f(orbitalMotion.M2E(mean_anomaly, osc.e), osc.e)
    else:
        osc.f = math.radians(chief_orbit.true_anomaly_deg)
    mean = orbitalMotion.ClassicElements()
    orbitalMotion.clMeanOscMap(req, j2, osc, mean, -1)
    chief = roe.MeanElements(mean.a, mean.e, mean.i, mean.Omega, mean.omega,
                             orbitalMotion.E2M(orbitalMotion.f2E(mean.f, mean.e), mean.e))
    deputy = roe.deputy_elements_from_roe(chief, np.asarray(roe_m, dtype=float) / chief.a)
    deputy_mean = orbitalMotion.ClassicElements()
    deputy_mean.a, deputy_mean.e, deputy_mean.i = deputy.a, deputy.e, deputy.i
    deputy_mean.Omega, deputy_mean.omega = deputy.raan, deputy.argp
    deputy_mean.f = orbitalMotion.E2f(orbitalMotion.M2E(deputy.mean_anomaly, deputy.e), deputy.e)
    deputy_osc = orbitalMotion.ClassicElements()
    orbitalMotion.clMeanOscMap(req, j2, deputy_mean, deputy_osc, 1)
    # The first-order map is not its own inverse (second order in J2: a
    # few metres of semi-major axis, which drift the formation hundreds of
    # metres a day): correct the osculating elements until their mean
    # elements are the follower's.
    # In the near-circular orbit's well-conditioned elements: the
    # eccentricity vector and the argument of latitude, not e, omega, f.
    def nonsingular(el):
        return np.array([el.a, el.e * math.cos(el.omega), el.e * math.sin(el.omega), el.i, el.Omega,
                         el.omega + el.f])

    wanted = nonsingular(deputy_mean)
    for _ in range(_PLACEMENT_ITERATIONS):
        back = orbitalMotion.ClassicElements()
        orbitalMotion.clMeanOscMap(req, j2, deputy_osc, back, -1)
        step = wanted - nonsingular(back)
        step[4:] = [roe.wrap_pi(x) for x in step[4:]]
        a_, ex, ey, inc, raan, u = nonsingular(deputy_osc) + step
        deputy_osc.a, deputy_osc.i, deputy_osc.Omega = a_, inc, raan
        deputy_osc.e, deputy_osc.omega = math.hypot(ex, ey), math.atan2(ey, ex)
        deputy_osc.f = u - deputy_osc.omega
    return OrbitIC(type="classical_elements", semi_major_axis_km=deputy_osc.a / 1000.0,
                   eccentricity=deputy_osc.e, inclination_deg=math.degrees(deputy_osc.i),
                   raan_deg=math.degrees(deputy_osc.Omega) % 360.0,
                   arg_periapsis_deg=math.degrees(deputy_osc.omega) % 360.0, anomaly_type="true",
                   true_anomaly_deg=math.degrees(deputy_osc.f) % 360.0)


def generate_roe_follower(chief: SpacecraftConfig, template: SpacecraftConfig, follower_name: str, roe_m,
                          control_law: str = "impulsive") -> SpacecraftConfig:
    """A follower cloned from ``template`` (mass, hardware, attitude
    control unchanged), placed at ``roe_m`` [m] from ``chief``
    (:func:`follower_orbit`, with Basilisk's Earth J2 and equatorial
    radius, as the run measures them) and holding it with an ROE
    formation. The template's station keeping provides the thruster and
    tank. Raises ScenarioValidationError when that is missing or the
    chief's orbit is not classical elements."""
    if template.station_keeping is None:
        raise ScenarioValidationError(
            f"{template.name} has no station keeping: an ROE formation fires that thruster -- add station "
            "keeping to it, or pick another template spacecraft")
    if chief.orbit.type != "classical_elements":
        raise ScenarioValidationError(f"chief {chief.name!r}'s orbit must be classical elements, not "
                                      f"{chief.orbit.type!r}")
    follower = copy.deepcopy(template)
    follower.name = follower_name
    follower.orbit = follower_orbit(chief.orbit, roe_m, orbitalMotion.REQ_EARTH * 1000.0, orbitalMotion.J2_EARTH)
    follower.phasing_keeping = None
    follower.roe_formation = RoeFormationConfig(chief_spacecraft=chief.name, control_law=control_law,
                                                targets=[RoeTargetConfig(0.0, [float(x) for x in roe_m])])
    return follower


class RoeTargetSchedule:
    """The active ROE target [m] at a time: each target from its
    ``start_day`` on."""

    def __init__(self, config: RoeFormationConfig):
        self.starts_s = [t.start_day * _DAY_S for t in config.targets]  # [s]
        self.targets_m = [np.asarray(t.roe_m, dtype=float) for t in config.targets]  # [m]

    def index_at(self, t_s: float) -> int:
        index = 0
        for k, start in enumerate(self.starts_s):
            if t_s >= start:
                index = k
        return index


class _Pending:
    """One scheduled burn (or part of one)."""

    def __init__(self, center_s: float, burn: roe.Burn):
        self.centerS = center_s  # [s] sim time of the burn's planned argument of latitude
        self.burn = burn
        self.remainingDv = burn.magnitude  # [m/s]
        self.eclipseTries = 0


class RoeFormationController(sysModel.SysModel):
    """One follower's ROE formation controller. Build with
    :func:`build_roe_formation`."""

    def __init__(self, name: str, config: RoeFormationConfig, mu: float, req: float, j2: float,
                 thrust_n: float, isp_s: float, dry_mass_kg: float, eclipse_sunlit_threshold: float,
                 g0_mps2: float = 9.80665):
        super().__init__()
        self.ModelTag = name
        self.config = config
        self.controlLaw = config.control_law
        self.schedule = RoeTargetSchedule(config)

        self.scStateInMsgA = messaging.SCStatesMsgReader()  # chief
        self.scStateInMsgB = messaging.SCStatesMsgReader()  # follower
        self.eclipseInMsgB = messaging.EclipseMsgReader()
        self.forceInMsg = messaging.CmdForceInertialMsgReader()  # "continuous": meanOEFeedback's request
        self.deltaVOutMsg = messaging.DataStorageStatusMsg()  # Vizard gauges (module docstring)
        self.separationRadialOutMsg = messaging.DataStorageStatusMsg()
        self.separationTransverseOutMsg = messaging.DataStorageStatusMsg()
        self.separationNormalOutMsg = messaging.DataStorageStatusMsg()
        self.minSeparationOutMsg = messaging.DataStorageStatusMsg()

        # Wired by build_roe_formation.
        self.extForceEffectorB = None
        self.scObjectB = None
        self.altitudeControllerB: Optional[StationKeepingController] = None
        self.thruster = None  # the follower's shared ThrusterOnTimeModel
        self.lawModule = None  # "continuous": the meanOEFeedback module
        self.chiefName = ""

        self.mu, self.req, self.j2 = mu, req, j2  # [m^3/s^2], [m], [-]
        self.thrustN = thrust_n  # [N]
        self.ispS = isp_s  # [s]
        self.g0 = g0_mps2  # [m/s^2]
        self.dryMass = dry_mass_kg  # [kg]
        self.sunlitThreshold = eclipse_sunlit_threshold  # [-]
        self.dvBudgetMps = 0.0  # [m/s] shared-tank total, for the Vizard gauge (set by build_roe_formation)
        self.separationCapacityKm, self.marginCapacityM = gauge_scales(config)  # [km], [m]

        self.state = HOLDING
        self._lastT: Optional[float] = None  # [s]
        self._targetIndex: Optional[int] = None
        self._nextDecisionT = 0.0  # [s]
        self._driftDa: Optional[float] = None  # [-] the da a drift in progress holds
        self._pending: List[_Pending] = []
        self._firing: Optional[_Pending] = None
        self._sunlit = np.ones(_SUNLIT_BINS, dtype=bool)  # by argument of latitude, from the last orbit
        self._lastInSun: Optional[bool] = None
        self._lastRefreshT: Optional[float] = None  # [s] "continuous": when the target was last set
        self._cumulativeDv = 0.0  # [m/s]
        self._loggedState = HOLDING
        self._peakCommandSinceLog = 0.0  # [N]
        self._peakAppliedSinceLog = 0.0  # [N]
        self._direction = np.zeros(3)

        self.lastRoeM = np.full(6, np.nan)  # [m]
        self.lastErrorM = np.full(6, np.nan)  # [m]

        self.logThinner = LogThinner()
        self.tLog: list = []
        self.roeLog: list = []  # [m] six mean ROE times the chief's mean semi-major axis
        self.errorLog: list = []  # [m] ROE minus the active target
        self.stateLog: list = []
        self.deltaVLog: list = []  # [m/s]
        self.propellantLog: list = []  # [kg]
        self.minSeparationLog: list = []  # [m]
        self.targetIndexLog: list = []
        self.commandedForceLog: list = []  # [N] "continuous"
        self.appliedForceLog: list = []  # [N] "continuous"

    # -- helpers ----------------------------------------------------------
    def Reset(self, CurrentSimNanos):
        self._lastT = CurrentSimNanos * macros.NANO2SEC
        self._targetIndex = None
        self._nextDecisionT = self._lastT
        self._driftDa = None
        self._pending = []
        self._firing = None
        self._lastRefreshT = None
        if self.extForceEffectorB is not None:
            self.extForceEffectorB.extForce_N = [0.0, 0.0, 0.0]

    def _bin(self, u: float) -> int:
        return int((u % (2.0 * math.pi)) / (2.0 * math.pi) * _SUNLIT_BINS) % _SUNLIT_BINS

    def _sunlit_at(self, u: float, half_arc: float) -> bool:
        """Whether the arc of ``half_arc`` [rad] either side of ``u`` was
        sunlit on the last orbit."""
        steps = max(1, int(math.ceil(2.0 * half_arc / (2.0 * math.pi / _SUNLIT_BINS))))
        return all(self._sunlit[self._bin(u - half_arc + k * 2.0 * half_arc / steps)] for k in range(steps + 1))

    def _log(self, t: float, propellant_kg: float, min_separation_m: float) -> None:
        if not self.logThinner.due(t):
            return
        self.tLog.append(t)
        self.roeLog.append(self.lastRoeM.copy())
        self.errorLog.append(self.lastErrorM.copy())
        self.stateLog.append(self._loggedState)
        self.deltaVLog.append(self._cumulativeDv)
        self.propellantLog.append(propellant_kg)
        self.minSeparationLog.append(min_separation_m)
        self.targetIndexLog.append(self._targetIndex if self._targetIndex is not None else 0)
        self.commandedForceLog.append(self._peakCommandSinceLog)
        self.appliedForceLog.append(self._peakAppliedSinceLog)
        self._loggedState = HOLDING
        self._peakCommandSinceLog = 0.0
        self._peakAppliedSinceLog = 0.0

    def _note_state(self, state: int) -> None:
        """The logged state is the most telling one since the last sample:
        a burn, then a drift, then a plan."""
        rank = {HOLDING: 0, PLANNED: 1, DRIFTING: 2, IN_PLANE_BURN: 3, OUT_OF_PLANE_BURN: 3, CONTINUOUS_FIRING: 3}
        self.state = state
        if rank[state] >= rank[self._loggedState]:
            self._loggedState = state

    def _fire(self, force_direction, want_n: float, remaining_dv: Optional[float], mass_kg: float, dt: float,
              in_sun: bool, u: float, v: float, n: float) -> float:
        """Fires the shared thruster this tick; returns the thrust [N]."""
        tracker = self.altitudeControllerB
        if tracker.burnOn or self.thruster.firing_owned_by(tracker) or tracker.propellant <= 1e-9:
            return 0.0
        thrust, _extra_dv, _too_small = self.thruster.command(
            owner=self, want_firing=want_n > 0.0, remaining_dv=remaining_dv, sign=0.0, thrust_n=want_n,
            mass_kg=mass_kg, dt_s=dt, in_sun=in_sun, u_rad=u, v_mps=v, mean_motion=n)
        if thrust > 0.0:
            self._direction = np.asarray(force_direction, dtype=float)
        return thrust

    # -- the impulsive law ------------------------------------------------
    def _decide(self, t: float, roe_now, target, chief: roe.MeanElements, u: float, n: float,
                mass_kg: float) -> None:
        a = chief.a
        tolerance = [x / a for x in self.config.tolerance_m]
        burn_half_arc = math.pi * self.config.max_burn_fraction_of_orbit
        period_s = 2.0 * math.pi / n
        longest_s = period_s * self.config.max_burn_fraction_of_orbit  # [s] the longest burn part
        max_dv = longest_s * self.thrustN / mass_kg  # [m/s]

        def plan(roe_used, stop_drift: bool, drift_da: Optional[float] = None, tolerance=tolerance):
            correction = roe.plan_correction(
                roe_used, target, chief, tolerance, self.config.correction_window_days * _DAY_S,
                self.config.max_drift_m / a, self._driftDa if drift_da is None else drift_da, stop_drift,
                lambda location: self._sunlit_at(location, burn_half_arc), self.j2, self.req, self.mu)
            burns = [b for b in correction.burns if b.magnitude > 0.0]
            return correction, roe.schedule_burns(burns, u, n, max_dv, min_lead_s=0.5 * longest_s + 1.0,
                                                  min_separation_s=1.5 * longest_s)

        error_dl = roe.wrap_pi(float(roe_now[1] - target[1]))
        next_check_s = period_s * _HOLDING_CHECK_FRACTION
        if self._driftDa is not None:
            # The stop burns take time to fire, and dl keeps drifting until
            # they do (roe.sequence_dl_shift); where it ends depends on which
            # pass over their locations they use, in steps of 1.5 n da T.
            # So the drift glides in: its da is cut back to close the rest
            # in no less than _GLIDE_ORBITS, down to the slow da whose stop
            # steps fit the tolerance, and it stops from there, once stopping
            # now brings dl to (or past) the target.
            slow_da = max(0.25 * tolerance[0], tolerance[1] / (1.5 * n * period_s))
            glide_da = max(slow_da, abs(error_dl) / (1.5 * n * _GLIDE_ORBITS * period_s))
            stop, stop_scheduled = plan(roe_now, stop_drift=True)
            final = error_dl + roe.sequence_dl_shift(stop_scheduled, a, n)
            reached = final * error_dl <= 0.0 or abs(final) < 0.5 * tolerance[1]
            if reached and abs(self._driftDa) <= 1.5 * slow_da:
                correction, scheduled = stop, stop_scheduled
            elif abs(self._driftDa) > 1.25 * glide_da:
                correction, scheduled = plan(roe_now, stop_drift=False,
                                             drift_da=math.copysign(glide_da, self._driftDa))
            else:
                correction, scheduled = plan(roe_now, stop_drift=False)
                rate = 1.5 * n * abs(self._driftDa)  # [1/s] how fast dl moves
                if rate > 0.0:  # look again before the stop is due
                    next_check_s = min(next_check_s, max(60.0, abs(final) / rate))
        elif abs(error_dl) <= _DIRECT_DL_FACTOR * tolerance[1]:
            correction, scheduled = self._direct(roe_now, target, chief, tolerance, u, n, mass_kg, plan)
        else:
            correction, scheduled = plan(roe_now, stop_drift=False)
            # The burns set da only one by one, so dl ends up elsewhere than
            # the plan assumed: plan once more from where they lead.
            shift = roe.sequence_dl_shift(scheduled, a, n)
            if abs(shift) > 0.25 * tolerance[1]:
                shifted = np.array(roe_now, dtype=float)
                shifted[1] += shift
                correction, scheduled = plan(shifted, stop_drift=False)
        self._driftDa = correction.drift_da
        self._pending = [_Pending(t + when, burn) for when, burn in scheduled]
        self._nextDecisionT = t + next_check_s if not self._pending else math.inf

    def _direct(self, roe_now, target, chief: roe.MeanElements, tolerance, u: float, n: float, mass_kg: float,
                plan):
        """A small correction without a drift: the cross-track burn as
        planned, and along-track burns over the next two orbits that set
        da, the e vector and dl together (:func:`.roe.in_plane_sequence`),
        so an e-vector correction does not throw dl out. Falls back to the
        drift plan when a burn would be longer than a part may be."""
        a = chief.a
        period_s = 2.0 * math.pi / n
        longest_s = period_s * self.config.max_burn_fraction_of_orbit  # [s]
        error = np.asarray(roe_now, dtype=float) - target
        error[1] = roe.wrap_pi(float(error[1]))
        cross_only = list(tolerance)
        cross_only[1] = math.inf  # dl is the sequence's
        correction, scheduled = plan(roe_now, stop_drift=False, tolerance=cross_only)
        scheduled = [(when, burn) for when, burn in scheduled if burn.kind == "out-of-plane"]
        needs_in_plane = (abs(error[0]) > tolerance[0] or math.hypot(error[2], error[3]) > tolerance[2]
                          or abs(error[1]) > tolerance[1])
        if not needs_in_plane:
            return correction, scheduled
        u1 = math.atan2(-error[3], -error[2]) if math.hypot(error[2], error[3]) > 0.0 else u + math.pi / 2.0
        burn_half_arc = math.pi * self.config.max_burn_fraction_of_orbit
        locations = [u1, u1 + math.pi]
        if not all(self._sunlit_at(x, burn_half_arc) for x in locations):
            locations = roe.sunlit_locations(lambda x: self._sunlit_at(x, burn_half_arc), locations)
        times, places = [], []
        for location in locations:
            lead_s = ((location - u) % (2.0 * math.pi)) / n
            if lead_s < 0.5 * longest_s + 1.0:
                lead_s += period_s
            times += [lead_s, lead_s + period_s]
            places += [location, location]
        sequence = roe.in_plane_sequence(-float(error[0]), -float(error[2]), -float(error[3]), -float(error[1]),
                                         float(roe_now[0]), times, places, a, n)
        max_dv = longest_s * self.thrustN / mass_kg  # [m/s]
        if any(burn.magnitude > max_dv for _, burn in sequence):
            return plan(roe_now, stop_drift=False)
        for index, (when, burn) in enumerate(scheduled):  # keep the cross-track burn clear of the sequence
            while any(abs(when - other) < 1.5 * longest_s for other, _ in sequence):
                when += period_s
            scheduled[index] = (when, burn)
        return correction, sorted(sequence + scheduled, key=lambda p: p[0])

    def _impulsive(self, t: float, dt: float, roe_now, target, chief, rB, vB, u: float, n: float,
                   mass_kg: float, in_sun: bool) -> float:
        """This tick's thrust [N] of the impulsive law."""
        if self._firing is None and not self._pending and t >= self._nextDecisionT:
            self._decide(t, roe_now, target, chief, u, n, mass_kg)

        thrust = 0.0
        if self._firing is None and self._pending:
            nextBurn = self._pending[0]
            on_time = nextBurn.remainingDv * mass_kg / self.thrustN  # [s]
            if t >= nextBurn.centerS - 0.5 * on_time:
                self._firing = self._pending.pop(0)
        if self._firing is not None:
            burn = self._firing
            rHat = rB / np.linalg.norm(rB)
            hHat = np.cross(rB, vB)
            hHat = hHat / np.linalg.norm(hHat)
            tHat = np.cross(hHat, rHat)
            dv_r, dv_t, dv_n = burn.burn.dv_rtn
            direction = dv_r * rHat + dv_t * tHat + dv_n * hHat
            direction = direction / np.linalg.norm(direction)
            if not in_sun:
                # Eclipse at the burn: an orbit later, at the same place.
                period_s = 2.0 * math.pi / n
                burn.eclipseTries += 1
                self._firing = None
                if burn.eclipseTries >= _ECLIPSE_RETRIES:
                    self._pending = []
                    self._nextDecisionT = t
                else:
                    burn.centerS += period_s
                    self._pending.insert(0, burn)
                    self._pending.sort(key=lambda p: p.centerS)
            else:
                thrust = self._fire(direction, self.thrustN, burn.remainingDv, mass_kg, dt, in_sun, u,
                                    float(np.linalg.norm(vB)), n)
                delivered = thrust / mass_kg * dt  # [m/s]
                burn.remainingDv -= delivered
                if burn.remainingDv <= 1e-9 or (thrust == 0.0 and not self.thruster.firing_owned_by(self)):
                    self._firing = None
                    if not self._pending:  # look again one orbit later; a quarter while drifting
                        self._nextDecisionT = t + 2.0 * math.pi / n * (
                            _HOLDING_CHECK_FRACTION if self._driftDa is not None else 1.0)
                if thrust > 0.0:
                    self._note_state(IN_PLANE_BURN if burn.burn.kind == "in-plane" else OUT_OF_PLANE_BURN)
        if thrust == 0.0:
            if self._driftDa is not None:
                self._note_state(DRIFTING)
            elif self._pending or self._firing is not None:
                self._note_state(PLANNED)
            else:
                self._note_state(HOLDING)
        return thrust

    # -- the continuous law -----------------------------------------------
    def _continuous(self, t: float, dt: float, chief, target, rB, vB, u: float, n: float, mass_kg: float,
                    in_sun: bool, target_changed: bool) -> float:
        if self.lawModule is not None and (target_changed or self._lastRefreshT is None
                                           or t - self._lastRefreshT >= self.config.target_refresh_s):
            self.lawModule.targetDiffOeMean = equinoctial_target(chief, target)
            self._lastRefreshT = t
        request = np.array(self.forceInMsg().forceRequestInertial) if self.forceInMsg.isLinked() else np.zeros(3)
        request_n = float(np.linalg.norm(request)) if np.all(np.isfinite(request)) else 0.0  # [N]
        self._peakCommandSinceLog = max(self._peakCommandSinceLog, request_n)
        thrust = 0.0
        if request_n > 0.0:
            want_n = min(request_n, self.thrustN)
            thrust = self._fire(request / request_n, want_n, want_n * dt / mass_kg, mass_kg, dt, in_sun, u,
                                float(np.linalg.norm(vB)), n)
        self._peakAppliedSinceLog = max(self._peakAppliedSinceLog, thrust)
        self._note_state(CONTINUOUS_FIRING if thrust > 0.0 else HOLDING)
        return thrust

    # -- each tick ----------------------------------------------------------
    def UpdateState(self, CurrentSimNanos):
        t = CurrentSimNanos * macros.NANO2SEC  # [s]
        dt = t - self._lastT if self._lastT is not None else 0.0  # [s]
        self._lastT = t
        tracker = self.altitudeControllerB

        stateA, stateB = self.scStateInMsgA(), self.scStateInMsgB()
        rA, vA = np.array(stateA.r_BN_N), np.array(stateA.v_BN_N)
        rB, vB = np.array(stateB.r_BN_N), np.array(stateB.v_BN_N)
        chief = mean_elements(rA, vA, self.mu, self.req, self.j2)
        deputy = mean_elements(rB, vB, self.mu, self.req, self.j2)
        if chief is None or deputy is None or abs(math.sin(chief.i)) < 1e-9:
            if self.extForceEffectorB is not None:
                self.extForceEffectorB.extForce_N = [0.0, 0.0, 0.0]
            self.lastRoeM = np.full(6, np.nan)
            self.lastErrorM = np.full(6, np.nan)
            self._log(t, tracker.propellant, float("nan"))
            return

        a = chief.a
        n = math.sqrt(self.mu / a ** 3)  # [rad/s]
        roe_now = roe.roe_from_mean_elements(chief, deputy)
        index = self.schedule.index_at(t)
        target = self.schedule.targets_m[index] / a
        target_changed = index != self._targetIndex
        if target_changed:
            self._targetIndex = index
            if self._firing is None:  # a firing in progress finishes; the rest is planned again
                self._pending = []
            self._driftDa = None
            self._nextDecisionT = t
        error = roe_now - target
        error[1] = roe.wrap_pi(float(error[1]))
        self.lastRoeM = roe_now * a
        self.lastErrorM = error * a

        u = PhasingKeepingController._argument_of_latitude(rB, vB)
        in_sun = True
        if self.eclipseInMsgB.isLinked():
            illumination = _eclipse_illumination_fraction(self.eclipseInMsgB())
            in_sun = illumination > self.sunlitThreshold
            self._lastInSun = _log_sunlit_transition(self.ModelTag, t, illumination, in_sun, self._lastInSun)
            self._sunlit[self._bin(u)] = in_sun

        mass_kg = (self.scObjectB.scMassOutMsg.read().massSC if self.scObjectB is not None
                   else self.dryMass + tracker.propellant)  # [kg]
        if self.controlLaw == "impulsive":
            thrust = self._impulsive(t, dt, roe_now, target, chief, rB, vB, u, n, mass_kg, in_sun)
        else:
            thrust = self._continuous(t, dt, chief, target, rB, vB, u, n, mass_kg, in_sun, target_changed)

        if thrust > 0.0:
            self._cumulativeDv += thrust / mass_kg * dt  # [m/s]
        hub_mass = self.scObjectB.hub.mHub if self.scObjectB is not None else self.dryMass + tracker.propellant
        new_mass, tracker.propellant, _burned_kg, _m_dot = apply_propellant_burn(
            hub_mass, tracker.propellant, thrust, self.ispS, dt, self.g0)
        if self.scObjectB is not None:
            self.scObjectB.hub.mHub = new_mass
        held_by_station_keeping = tracker.burnOn or self.thruster.firing_owned_by(tracker)
        if self.extForceEffectorB is not None and not held_by_station_keeping:
            self.extForceEffectorB.extForce_N = (thrust * self._direction).tolist()

        margin_m = roe.min_radial_normal_separation(roe_now, a)
        self._publish(CurrentSimNanos, rA, vA, rB, vB, margin_m)
        self._log(t, tracker.propellant, margin_m)

    def _publish(self, now_ns: int, rA, vA, rB, vB, margin_m: float) -> None:
        """The Vizard gauges (module docstring)."""
        rho, _ = orbitalMotion.rv2hill(rA, vA, rB, vB)
        gauges = [(self.deltaVOutMsg, self._cumulativeDv, self.dvBudgetMps)]  # [m/s]
        gauges += [(msg, float(x) / 1000.0, self.separationCapacityKm)  # [km]
                   for msg, x in zip((self.separationRadialOutMsg, self.separationTransverseOutMsg,
                                      self.separationNormalOutMsg), rho)]
        gauges.append((self.minSeparationOutMsg, margin_m, self.marginCapacityM))  # [m]
        for msg, value, capacity in gauges:
            payload = messaging.DataStorageStatusMsgPayload()
            payload.storageCapacity = capacity
            payload.storageLevel = _clamp_magnitude(value, capacity)
            msg.write(payload, now_ns, self.moduleID)


def gauge_scales(config: RoeFormationConfig):
    """(separation scale [km], approach scale [m]) for the Vizard gauges:
    twice the largest radial (|a da| + |a de|), along-track (|a dl| +
    2 |a de|) or cross-track (|a di|) extent any target asks for, and
    twice the largest closest approach any target has; at least 0.1 km
    and 10 m, so a formation of zeros still draws."""
    extent_m, margin_m = 0.0, 0.0  # [m]
    for target in config.targets:
        da, dl, dex, dey, dix, diy = target.roe_m
        de, di = math.hypot(dex, dey), math.hypot(dix, diy)  # [m]
        extent_m = max(extent_m, abs(da) + de, abs(dl) + 2.0 * de, di)
        margin_m = max(margin_m, roe.min_radial_normal_separation(target.roe_m, 1.0))
    return max(2.0 * extent_m / 1000.0, 0.1), max(2.0 * margin_m, 10.0)  # [km], [m]


def build_roe_formation(scSim, task_name: str, tag: str, mu: float, chief_sc_object, follower_sc_object,
                        follower_station_keeping_controller: StationKeepingController, follower_eclipse_out_msg,
                        config: RoeFormationConfig, central_radius_m: float, j2: float) -> RoeFormationController:
    """Builds one follower's :class:`RoeFormationController` on
    ``task_name``; for the continuous law, ``meanOEFeedback`` with truth
    navigation of both spacecraft (``simpleNav``, no noise) before it, so
    the controller reads this tick's request."""
    station_keeping = follower_station_keeping_controller
    controller = RoeFormationController(
        name=f"{tag}RoeFormation", config=config, mu=mu, req=central_radius_m, j2=j2,
        thrust_n=station_keeping.thrustN, isp_s=station_keeping.ispS, dry_mass_kg=station_keeping.dryMass,
        eclipse_sunlit_threshold=station_keeping.sunlitThreshold)

    if config.control_law == "continuous":
        navs = []
        for role, sc_object in (("Chief", chief_sc_object), ("Follower", follower_sc_object)):
            nav = simpleNav.SimpleNav()
            nav.ModelTag = f"{tag}RoeNav{role}"
            nav.scStateInMsg.subscribeTo(sc_object.scStateOutMsg)
            scSim.AddModelToTask(task_name, nav)
            navs.append(nav)
        law = meanOEFeedback.meanOEFeedback()
        law.ModelTag = f"{tag}RoeMeanOEFeedback"
        law.chiefTransInMsg.subscribeTo(navs[0].transOutMsg)
        law.deputyTransInMsg.subscribeTo(navs[1].transOutMsg)
        mass_kg = station_keeping.dryMass + station_keeping.propellant  # [kg] at the start
        law.K = (np.eye(6) * config.continuous_gain * mass_kg).flatten().tolist()  # [N*m/s]
        law.oeType = 1  # equinoctial: non-singular at e = 0
        law.mu = mu  # [m^3/s^2]
        law.req = central_radius_m  # [m]
        law.J2 = j2  # [-]
        law.targetDiffOeMean = [0.0] * 6  # set from the ROE target on the first tick
        scSim.AddModelToTask(task_name, law)
        controller.lawModule = law
        controller._navs = navs  # keep the SWIG objects alive with the controller
        controller.forceInMsg.subscribeTo(law.forceOutMsg)

    controller.scStateInMsgA.subscribeTo(chief_sc_object.scStateOutMsg)
    controller.scStateInMsgB.subscribeTo(follower_sc_object.scStateOutMsg)
    if follower_eclipse_out_msg is not None:
        controller.eclipseInMsgB.subscribeTo(follower_eclipse_out_msg)
    controller.extForceEffectorB = station_keeping.extForceEffector
    controller.scObjectB = follower_sc_object
    controller.altitudeControllerB = station_keeping
    controller.thruster = station_keeping.thruster
    controller.chiefName = chief_sc_object.ModelTag
    controller.dvBudgetMps = station_keeping.dvBudgetMps  # [m/s] the shared tank's total
    # The ROE controller holds the relative semi-major axis, the chief's
    # reboosts included: the follower's station keeping never fires on its
    # own (formation follower with nothing to follow).
    station_keeping.formationFollower = True
    station_keeping.formationReference = None
    scSim.AddModelToTask(task_name, controller)
    return controller


ROE_COLUMNS = tuple(f"a_{label}" for label in roe.ROE_LABELS)  # each ROE times the chief's semi-major axis


def result_series(name: str, controller: RoeFormationController) -> List[TimeSeries]:
    """The controller's telemetry as ``{name}.roe_formation.*`` series."""
    t_s = np.asarray(controller.tLog)
    prefix = f"{name}.roe_formation"
    series = [
        TimeSeries(f"{prefix}.roe", t_s, ROE_COLUMNS, np.asarray(controller.roeLog).reshape(-1, 6), units="m"),
        TimeSeries(f"{prefix}.roe_error", t_s, ROE_COLUMNS, np.asarray(controller.errorLog).reshape(-1, 6),
                   units="m"),
        TimeSeries(f"{prefix}.state", t_s, ("state",), np.asarray(controller.stateLog, dtype=float), units="-"),
        # this controller's own delta-V; the tank is the station keeping's
        # ({name}.station_keeping.propellant_remaining), as for phasing keeping
        TimeSeries(f"{prefix}.delta_v", t_s, ("cumulative_delta_v",), np.asarray(controller.deltaVLog),
                   units="m/s"),
        TimeSeries(f"{prefix}.min_rn_separation", t_s, ("min_rn_separation",),
                   np.asarray(controller.minSeparationLog), units="m"),
        TimeSeries(f"{prefix}.target_index", t_s, ("target_index",),
                   np.asarray(controller.targetIndexLog, dtype=float), units="-"),
    ]
    if controller.controlLaw == "continuous":
        series.append(TimeSeries(f"{prefix}.force", t_s, ("commanded", "applied"),
                                 np.column_stack([controller.commandedForceLog, controller.appliedForceLog])
                                 .reshape(-1, 2), units="N"))
    return series
