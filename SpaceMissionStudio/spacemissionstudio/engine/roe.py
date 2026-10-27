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

r"""Relative orbital elements (ROE): the math behind ROE formation flying.

Pure numpy, no Basilisk: the controllers in ``engine.roe_formation`` feed
it mean elements that Basilisk's ``orbitalMotion.clMeanOscMap`` computed.
This module is the tool's own code; Basilisk has no ROE module.

**The ROE.** The quasi-nonsingular set of D'Amico (PhD thesis, TU Delft,
2010), from the chief's (c) and the deputy's (d) *mean* elements, with
``u = omega + M`` the mean argument of latitude::

    da  = (a_d - a_c) / a_c
    dl  = (u_d - u_c) + (Omega_d - Omega_c) cos(i_c)
    dex = e_d cos(omega_d) - e_c cos(omega_c)
    dey = e_d sin(omega_d) - e_c sin(omega_c)
    dix = i_d - i_c
    diy = (Omega_d - Omega_c) sin(i_c)

All six are dimensionless; times the chief's semi-major axis they are
lengths, which is how a user types and reads them (``a_c * roe``, in m).
``(dex, dey)`` is the relative eccentricity vector, ``(dix, diy)`` the
relative inclination vector.

**Near-circular relative motion** (first order, chief eccentricity << 1),
in the chief's RTN frame (radial, along-track, cross-track)::

    r_R / a = da - dex cos u - dey sin u
    r_T / a = dl + 2 dex sin u - 2 dey cos u
    r_N / a = dix sin u - diy cos u

**J2.** :func:`j2_stm` is the state transition matrix of the mean ROE
under secular J2 of Koenig, Guffanti and D'Amico, "New State Transition
Matrices for Spacecraft Relative Motion in Perturbed Orbits", JGCD 40(7),
2017 (the quasi-nonsingular ROE, J2 only). The tests check it against an
independent propagation: both spacecraft's mean elements moved with the
secular J2 rates of Omega, omega and M, then the ROE taken from them.

**Impulsive control** (near-circular; D'Amico 2010, Gaias and D'Amico,
JGCD 38(6), 2015). Gauss's equations in ROE form, for a burn of
``(dv_R, dv_T, dv_N)`` at mean argument of latitude ``u``::

    d(da)  = 2 dv_T / (n a)
    d(dex) = (sin u dv_R + 2 cos u dv_T) / (n a)
    d(dey) = (-cos u dv_R + 2 sin u dv_T) / (n a)
    d(dix) = cos u dv_N / (n a)
    d(diy) = sin u dv_N / (n a)

Two along-track burns half an orbit apart change ``da`` and the
eccentricity vector at the least delta-V, ``(n a / 2) max(|d(da)|,
|d(de)|)``; one cross-track burn changes the inclination vector, for
``n a |d(di)|``. ``dl`` is moved by drifting: a temporary ``da`` makes it
change at ``-3/2 n da`` (plus J2 terms) and a second pair of burns stops
the drift (:func:`plan_drift`).

**Differential drag.** Two spacecraft with different ballistic
coefficients see the relative semi-major axis decay at a nearly steady
rate ``da_dot``, so the mean longitude drifts away quadratically. As in
the density-model-free approach of Koenig, Guffanti and D'Amico (2017),
the rate is not computed from an atmosphere model but estimated from the
measured mean ``da`` (:class:`DifferentialDragEstimator`, a straight-line
fit with one offset per stretch between burns) and treated as constant
over a prediction: :func:`drag_column` is the matching extra column of
the state transition matrix (the drift of ``da`` itself plus the J2
terms through it; drag's direct effect on the e vector is of the order
of the eccentricity and left out). In a hold, :func:`drag_hold_cycle`
sets ``da`` to the side the drag takes it from, so the mean longitude
swings symmetrically about its target between two corrections and the
delta-V spent is the least that cancels the decay, ``n a |da_dot| / 2``
per second.

**Passive safety** (D'Amico and Montenbruck, JGCD 29(3), 2006). With
``da = 0`` the radial and cross-track separations are an ellipse in the
radial/cross-track plane; it keeps away from the origin when the e/i
vectors are parallel. :func:`min_radial_normal_separation` is its
closest approach.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Callable, Sequence

import numpy as np

ROE_LABELS = ("da", "dlambda", "dex", "dey", "dix", "diy")  # the order of every ROE vector here


@dataclass(frozen=True)
class MeanElements:
    """Mean classical elements: SI units, angles in radians."""

    a: float  # [m] semi-major axis
    e: float  # [-] eccentricity
    i: float  # [rad] inclination
    raan: float  # [rad] right ascension of the ascending node
    argp: float  # [rad] argument of periapsis
    mean_anomaly: float  # [rad]

    @property
    def mean_argument_of_latitude(self) -> float:
        """``u = omega + M`` [rad]."""
        return self.argp + self.mean_anomaly


def wrap_pi(angle: float) -> float:
    """An angle [rad] in [-pi, pi)."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def roe_from_mean_elements(chief: MeanElements, deputy: MeanElements) -> np.ndarray:
    """The six quasi-nonsingular ROE (dimensionless; module docstring)."""
    d_raan = wrap_pi(deputy.raan - chief.raan)
    du = wrap_pi(deputy.mean_argument_of_latitude - chief.mean_argument_of_latitude)
    return np.array([
        (deputy.a - chief.a) / chief.a,
        wrap_pi(du + d_raan * math.cos(chief.i)),
        deputy.e * math.cos(deputy.argp) - chief.e * math.cos(chief.argp),
        deputy.e * math.sin(deputy.argp) - chief.e * math.sin(chief.argp),
        deputy.i - chief.i,
        d_raan * math.sin(chief.i),
    ])


def deputy_elements_from_roe(chief: MeanElements, roe: Sequence[float]) -> MeanElements:
    """The deputy's mean elements for ``roe`` around ``chief``: the exact
    inverse of :func:`roe_from_mean_elements`. Needs an inclined chief
    (``sin i != 0``), as ``diy`` does."""
    da, dl, dex, dey, dix, diy = (float(x) for x in roe)
    sin_i = math.sin(chief.i)
    if abs(sin_i) < 1e-9:
        raise ValueError("ROE need an inclined chief orbit: diy is the node difference times sin(i)")
    raan = chief.raan + diy / sin_i
    ex = chief.e * math.cos(chief.argp) + dex
    ey = chief.e * math.sin(chief.argp) + dey
    e = math.hypot(ex, ey)
    argp = math.atan2(ey, ex) if e > 0.0 else chief.argp
    u = chief.mean_argument_of_latitude + dl - (raan - chief.raan) * math.cos(chief.i)
    return MeanElements(a=chief.a * (1.0 + da), e=e, i=chief.i + dix, raan=raan, argp=argp,
                        mean_anomaly=wrap_pi(u - argp))


def roe_to_rtn(roe: Sequence[float], u: float, a: float, n: float) -> tuple[np.ndarray, np.ndarray]:
    """First-order RTN position [m] and velocity [m/s] of the deputy
    relative to a near-circular chief at mean argument of latitude ``u``
    [rad], semi-major axis ``a`` [m] and mean motion ``n`` [rad/s]."""
    da, dl, dex, dey, dix, diy = (float(x) for x in roe)
    su, cu = math.sin(u), math.cos(u)
    position = a * np.array([da - dex * cu - dey * su,
                             dl + 2.0 * dex * su - 2.0 * dey * cu,
                             dix * su - diy * cu])
    velocity = a * n * np.array([dex * su - dey * cu,
                                 -1.5 * da + 2.0 * dex * cu + 2.0 * dey * su,
                                 dix * cu + diy * su])
    return position, velocity


def secular_j2_rates(elements: MeanElements, j2: float, r_eq: float, mu: float) -> tuple[float, float, float]:
    """Secular J2 rates [rad/s] of ``(Omega, omega, M)`` for mean elements."""
    eta = math.sqrt(1.0 - elements.e ** 2)
    kappa = _kappa(elements.a, eta, j2, r_eq, mu)
    cos_i = math.cos(elements.i)
    n = math.sqrt(mu / elements.a ** 3)
    return (-2.0 * kappa * cos_i,
            kappa * (5.0 * cos_i ** 2 - 1.0),
            n + kappa * eta * (3.0 * cos_i ** 2 - 1.0))


def _kappa(a: float, eta: float, j2: float, r_eq: float, mu: float) -> float:
    """``3/4 J2 R^2 sqrt(mu) / (a^(7/2) eta^4)`` [rad/s] (Koenig et al. 2017)."""
    return 0.75 * j2 * r_eq ** 2 * math.sqrt(mu) / (a ** 3.5 * eta ** 4)


def j2_stm(chief: MeanElements, dt: float, j2: float, r_eq: float, mu: float) -> np.ndarray:
    """6x6 state transition matrix of the mean ROE over ``dt`` [s] under
    the chief's Keplerian motion and secular J2 (Koenig, Guffanti and
    D'Amico 2017, quasi-nonsingular ROE). ``j2 = 0`` gives the Keplerian
    matrix: only ``dl`` drifts, at ``-3/2 n da``."""
    a, e, i, argp = chief.a, chief.e, chief.i, chief.argp
    n = math.sqrt(mu / a ** 3)  # [rad/s]
    eta = math.sqrt(1.0 - e ** 2)
    kappa = _kappa(a, eta, j2, r_eq, mu)  # [rad/s]
    big_e, big_f, big_g = 1.0 + eta, 4.0 + 3.0 * eta, 1.0 / eta ** 2
    cos_i, sin_i = math.cos(i), math.sin(i)
    big_p = 3.0 * cos_i ** 2 - 1.0
    big_q = 5.0 * cos_i ** 2 - 1.0
    big_s = math.sin(2.0 * i)
    big_t = sin_i ** 2
    argp_dot = kappa * big_q  # [rad/s]
    argp_f = argp + argp_dot * dt
    exi, eyi = e * math.cos(argp), e * math.sin(argp)
    exf, eyf = e * math.cos(argp_f), e * math.sin(argp_f)
    c, s = math.cos(argp_dot * dt), math.sin(argp_dot * dt)
    tau = dt  # [s]
    phi = np.eye(6)
    phi[1, 0] = -(1.5 * n + 3.5 * kappa * big_e * big_p) * tau
    phi[1, 2] = kappa * exi * big_f * big_g * big_p * tau
    phi[1, 3] = kappa * eyi * big_f * big_g * big_p * tau
    phi[1, 4] = -kappa * big_f * big_s * tau
    phi[2, 0] = 3.5 * kappa * eyf * big_q * tau
    phi[2, 2] = c - 4.0 * kappa * exi * eyf * big_g * big_q * tau
    phi[2, 3] = -s - 4.0 * kappa * eyi * eyf * big_g * big_q * tau
    phi[2, 4] = 5.0 * kappa * eyf * big_s * tau
    phi[3, 0] = -3.5 * kappa * exf * big_q * tau
    phi[3, 2] = s + 4.0 * kappa * exi * exf * big_g * big_q * tau
    phi[3, 3] = c + 4.0 * kappa * eyi * exf * big_g * big_q * tau
    phi[3, 4] = -5.0 * kappa * exf * big_s * tau
    phi[5, 0] = 3.5 * kappa * big_s * tau
    phi[5, 2] = -4.0 * kappa * exi * big_g * big_s * tau
    phi[5, 3] = -4.0 * kappa * eyi * big_g * big_s * tau
    phi[5, 4] = 2.0 * kappa * big_t * tau
    return phi


def drag_column(chief: MeanElements, dt: float, j2: float, r_eq: float, mu: float) -> np.ndarray:
    """The change of the six mean ROE over ``dt`` [s] per unit of a steady
    relative semi-major axis decay ``da_dot`` [1/s] (module docstring):
    ``da`` moves by ``da_dot dt``, and everything :func:`j2_stm` drives
    from ``da`` by half its ``da`` column times ``dt``, since ``da`` grows
    linearly from its start."""
    column = 0.5 * dt * j2_stm(chief, dt, j2, r_eq, mu)[:, 0]
    column[0] = dt
    return column


def propagate_roe(roe: Sequence[float], chief: MeanElements, dt: float, j2: float, r_eq: float,
                  mu: float, da_dot: float = 0.0) -> np.ndarray:
    """The mean ROE ``dt`` [s] later (:func:`j2_stm`), with a steady
    differential-drag decay ``da_dot`` [1/s] of the relative semi-major
    axis (:func:`drag_column`)."""
    later = j2_stm(chief, dt, j2, r_eq, mu) @ np.asarray(roe, dtype=float)
    if da_dot != 0.0:
        later = later + da_dot * drag_column(chief, dt, j2, r_eq, mu)
    return later


# -- differential drag ------------------------------------------------------------

class DifferentialDragEstimator:
    """The relative semi-major axis decay rate ``da_dot`` [1/s] from the
    measured mean ``da``: one straight line with a common slope and one
    offset per segment, fitted over the last ``window_s`` [s].

    A burn changes ``da``, so the caller starts a new segment after each
    (``add(..., new_segment=True)``); a jump between two samples larger
    than ``jump_da`` [-] starts one too (the chief's own reboosts, which
    this spacecraft's controller does not see). Segments with fewer than
    three samples are left out. :meth:`rate` gives ``None`` until the
    segments together span ``min_span_s`` [s]: over one orbit the short-
    period part the mean-element map leaves in ``da`` biases the slope.
    """

    def __init__(self, window_s: float, min_span_s: float, jump_da: float, sample_interval_s: float = 60.0):
        self.window_s = window_s  # [s]
        self.min_span_s = min_span_s  # [s]
        self.jump_da = jump_da  # [-]
        self.sample_interval_s = sample_interval_s  # [s]
        self._t: list[float] = []  # [s]
        self._da: list[float] = []  # [-]
        self._segment: list[int] = []
        self._next_segment = False

    def break_segment(self) -> None:
        """The next sample starts a new segment (a burn in between)."""
        self._next_segment = True

    def add(self, t_s: float, da: float, new_segment: bool = False) -> None:
        """One measurement of the mean ``da`` [-] at ``t_s`` [s]; kept at
        most every ``sample_interval_s``."""
        new_segment = new_segment or self._next_segment
        if self._t and not new_segment and t_s - self._t[-1] < self.sample_interval_s:
            return
        self._next_segment = False
        if not self._t:
            segment = 0
        elif new_segment or abs(da - self._da[-1]) > self.jump_da:
            segment = self._segment[-1] + 1
        else:
            segment = self._segment[-1]
        self._t.append(t_s)
        self._da.append(da)
        self._segment.append(segment)
        start = t_s - self.window_s
        drop = 0
        while drop < len(self._t) and self._t[drop] < start:
            drop += 1
        if drop:
            del self._t[:drop], self._da[:drop], self._segment[:drop]

    def rate(self) -> float | None:
        """The fitted ``da_dot`` [1/s], or ``None`` without enough data."""
        if not self._t:
            return None
        t = np.asarray(self._t)
        da = np.asarray(self._da)
        segment = np.asarray(self._segment)
        numerator = denominator = span = 0.0
        for label in np.unique(segment):
            part = segment == label
            if np.count_nonzero(part) < 3:
                continue
            dt = t[part] - t[part].mean()
            numerator += float(dt @ (da[part] - da[part].mean()))
            denominator += float(dt @ dt)
            span += float(t[part][-1] - t[part][0])
        if span < self.min_span_s or denominator <= 0.0:
            return None
        return numerator / denominator


def drag_is_significant(da_dot: float, tolerance_dl: float, window_s: float, n: float) -> bool:
    """Whether a decay ``da_dot`` [1/s] moves the mean longitude by more
    than half its tolerance ``tolerance_dl`` [-] over ``window_s`` [s]:
    ``3/4 n |da_dot| window^2`` (the Keplerian drift of a linearly growing
    ``da``). Smaller rates, such as the scatter of the estimate for twin
    spacecraft, are left to the ordinary corrections."""
    return 0.75 * n * abs(da_dot) * window_s ** 2 > 0.5 * tolerance_dl


@dataclass(frozen=True)
class DragHoldCycle:
    """How a hold copes with a steady decay of ``da`` (:func:`drag_hold_cycle`)."""

    da_bias: float  # [-] da to set at a correction, relative to the target's
    dl_offset: float  # [-] dl to set at a correction, relative to the target's
    half_cycle_s: float  # [s] until dl turns back towards where it started


def drag_hold_cycle(da_dot: float, tolerance_da: float, tolerance_dl: float, n: float,
                    fraction: float = 0.6) -> DragHoldCycle:
    """The correction that keeps a hold inside ``fraction`` of its ``da``
    and ``dl`` tolerances [-] for as long as it can under a steady decay
    ``da_dot`` [1/s].

    With ``da`` set to ``-da_dot t*`` off the target's, the drag carries it
    through the target to ``+da_dot t*`` in ``2 t*``, while the mean
    longitude, moving at ``-3/2 n da``, goes out and comes back along a
    parabola that turns at ``t*``: it swings by ``3/4 n |da_dot| t*^2``. It
    starts at half that swing on the side it moves away from, so it stays
    symmetric about the target. ``t*`` is the largest time for which both
    the swing and ``|da|`` stay inside ``fraction`` of their tolerances.
    Each correction then changes ``da`` by ``2 da_dot t*``, which over the
    cycle is the least delta-V that cancels the drag."""
    rate = abs(da_dot)
    if rate == 0.0:
        return DragHoldCycle(da_bias=0.0, dl_offset=0.0, half_cycle_s=math.inf)
    by_dl = math.sqrt(4.0 * fraction * tolerance_dl / (1.5 * n * rate))
    by_da = fraction * tolerance_da / rate
    half = min(by_dl, by_da)  # [s]
    swing = 0.75 * n * rate * half ** 2
    # da starts on the side opposite to the decay; dl first moves the way
    # -3/2 n da takes it, which is the sign of da_dot, so it starts on the other side.
    return DragHoldCycle(da_bias=-da_dot * half, dl_offset=-math.copysign(0.5 * swing, da_dot),
                         half_cycle_s=half)


# -- impulsive manoeuvres -------------------------------------------------------

@dataclass(frozen=True)
class Burn:
    """One impulsive burn: at mean argument of latitude ``u`` [rad], with
    an RTN delta-V [m/s]."""

    u: float  # [rad] where on the orbit to fire (chief's mean argument of latitude)
    dv_rtn: tuple[float, float, float]  # [m/s] radial, along-track, cross-track
    kind: str  # "in-plane" or "out-of-plane"

    @property
    def magnitude(self) -> float:
        """|delta-V| [m/s]."""
        return float(math.sqrt(sum(x * x for x in self.dv_rtn)))


def burn_effect(burn: Burn, a: float, n: float) -> np.ndarray:
    """The change of the six ROE a burn makes (Gauss's equations in ROE
    form, near-circular; module docstring)."""
    dv_r, dv_t, dv_n = burn.dv_rtn
    su, cu = math.sin(burn.u), math.cos(burn.u)
    return np.array([2.0 * dv_t,
                     -2.0 * dv_r,
                     su * dv_r + 2.0 * cu * dv_t,
                     -cu * dv_r + 2.0 * su * dv_t,
                     cu * dv_n,
                     su * dv_n]) / (n * a)


def in_plane_pair(d_da: float, d_dex: float, d_dey: float, a: float, n: float) -> list[Burn]:
    """The two along-track burns, half an orbit apart, that change ``da``
    by ``d_da`` and the eccentricity vector by ``(d_dex, d_dey)`` at the
    least delta-V. The first burn is at the eccentricity change's angle;
    burns of zero size are left out."""
    d_de = math.hypot(d_dex, d_dey)
    u1 = math.atan2(d_dey, d_dex) if d_de > 0.0 else 0.0
    dv1 = n * a / 4.0 * (d_da + d_de)  # [m/s]
    dv2 = n * a / 4.0 * (d_da - d_de)  # [m/s]
    burns = [Burn(u=u1 % (2.0 * math.pi), dv_rtn=(0.0, dv1, 0.0), kind="in-plane"),
             Burn(u=(u1 + math.pi) % (2.0 * math.pi), dv_rtn=(0.0, dv2, 0.0), kind="in-plane")]
    return [b for b in burns if abs(b.dv_rtn[1]) > 0.0]


def in_plane_at(d_da: float, d_dex: float, d_dey: float, locations_u: Sequence[float], a: float,
                n: float) -> list[Burn]:
    """Along-track burns at the given arguments of latitude [rad] that
    make the same change as :func:`in_plane_pair`: for when the optimal
    pair's locations cannot be used, e.g. in eclipse. Any three distinct
    locations give an exact solution; with more, the one with the
    smallest sum of squared burns (least squares). It costs more delta-V
    than the optimal pair."""
    matrix = np.array([[2.0] * len(locations_u),
                       [2.0 * math.cos(u) for u in locations_u],
                       [2.0 * math.sin(u) for u in locations_u]]) / (n * a)
    dv = np.linalg.lstsq(matrix, np.array([d_da, d_dex, d_dey]), rcond=None)[0]
    return [Burn(u=float(u) % (2.0 * math.pi), dv_rtn=(0.0, float(v), 0.0), kind="in-plane")
            for u, v in zip(locations_u, dv) if abs(v) > 0.0]


def out_of_plane(d_dix: float, d_diy: float, a: float, n: float, opposite: bool = False) -> Burn | None:
    """The cross-track burn that changes the inclination vector by
    ``(d_dix, d_diy)``: at the change's angle, or half an orbit later with
    the opposite sign (``opposite``). ``None`` for no change."""
    d_di = math.hypot(d_dix, d_diy)
    if d_di == 0.0:
        return None
    u = math.atan2(d_diy, d_dix)
    dv = n * a * d_di  # [m/s]
    if opposite:
        u, dv = u + math.pi, -dv
    return Burn(u=u % (2.0 * math.pi), dv_rtn=(0.0, 0.0, dv), kind="out-of-plane")


def minimum_in_plane_dv(d_da: float, d_de: float, a: float, n: float) -> float:
    """The least delta-V [m/s] of any along-track burns making these
    changes: ``(n a / 2) max(|d_da|, |d_de|)``."""
    return n * a / 2.0 * max(abs(d_da), abs(d_de))


@dataclass(frozen=True)
class DriftPlan:
    """A ``dl`` correction by drifting: hold ``da`` at ``drift_da`` for
    ``duration_s``, then return it to the target."""

    drift_da: float  # [-] da to hold while drifting
    duration_s: float  # [s]


def plan_drift(roe_now: Sequence[float], target: Sequence[float], chief: MeanElements, window_s: float,
               max_drift_da: float, j2: float, r_eq: float, mu: float, min_drift_da: float = 0.0) -> DriftPlan:
    """The ``da`` that brings ``dl`` to the target in ``window_s`` [s],
    the other ROE already at their target; with the J2 STM, so the drift
    the e/i vectors cause under J2 is included. Limited to
    ``|da| <= max_drift_da``; the drift then takes longer. At least
    ``min_drift_da``, a drift the burns can set; the drift is then
    shorter."""
    x = np.asarray(target, dtype=float).copy()
    x[1] = float(roe_now[1])
    phi = j2_stm(chief, window_s, j2, r_eq, mu)
    rate = phi[1, 0]  # d(dl) per unit da over the window
    without_da = float(phi[1] @ np.r_[0.0, x[1:]])
    drift_da = (float(target[1]) - without_da) / rate if rate != 0.0 else 0.0
    if min_drift_da <= abs(drift_da) <= max_drift_da:
        return DriftPlan(drift_da=drift_da, duration_s=window_s)
    drift_da = math.copysign(min(max(abs(drift_da), min_drift_da), max_drift_da), drift_da)
    per_second = j2_stm(chief, 1.0, j2, r_eq, mu)
    rate_per_s = float(per_second[1] @ np.r_[drift_da, x[1:]] - x[1])  # d(dl)/dt at this da
    needed = wrap_pi(float(target[1]) - x[1])
    duration = needed / rate_per_s if rate_per_s != 0.0 else window_s
    return DriftPlan(drift_da=drift_da, duration_s=max(duration, 0.0))


# -- guidance: what to fire, where and when -------------------------------------

@dataclass(frozen=True)
class Correction:
    """What :func:`plan_correction` decided: the burns to fire, and the
    drift's ``da`` from then on (``None``: no drift)."""

    burns: tuple[Burn, ...]
    drift_da: float | None  # [-]
    drift_s: float | None  # [s] a new drift's planned duration (None otherwise)


def plan_correction(roe_now: Sequence[float], target: Sequence[float], chief: MeanElements,
                    tolerance: Sequence[float], window_s: float, max_drift_da: float,
                    drift_da: float | None, stop_drift: bool, sunlit: Callable[[float], bool] | None,
                    j2: float, r_eq: float, mu: float) -> Correction:
    """The impulsive guidance's decision, from the mean ROE now (all
    dimensionless).

    ``tolerance`` is ``(da, dl, |de|, |di|)``: how far each part may stray
    from ``target``. The mean longitude is moved by drifting: out of
    tolerance and not drifting, a drift is planned (:func:`plan_drift`,
    over ``window_s``); a drift in progress (``drift_da``, the ``da`` it
    holds) keeps that ``da`` until ``stop_drift``, when ``da`` goes back
    to the target's. When to stop is the caller's (it knows when the
    burns will fire, :func:`sequence_dl_shift`). A drift's ``da`` is
    small (0.25 m moves ``dl`` 35 m in a day at 550 km), so a drift is at
    least a quarter of the ``da`` tolerance, and while one starts, runs or
    stops ``da`` is set to half that; holding, the whole tolerance
    applies.

    The ``da`` wanted and the eccentricity vector are set by one set of
    along-track burns, the inclination vector by one cross-track burn;
    each only when out of tolerance. ``sunlit(u)``, when given, says
    whether a burn at mean argument of latitude ``u`` would be in
    sunlight. The optimal along-track pair is then replaced by burns at
    sunlit locations (:func:`in_plane_at`), the cross-track burn moved
    half an orbit (opposite sign)."""
    roe_now = np.asarray(roe_now, dtype=float)
    target = np.asarray(target, dtype=float)
    a = chief.a
    n = math.sqrt(mu / a ** 3)  # [rad/s]
    error_dl = wrap_pi(float(roe_now[1] - target[1]))
    fine_da = 0.25 * tolerance[0]
    desired_da, new_drift_da, drift_s = float(target[0]), None, None
    if drift_da is not None:
        if not stop_drift:
            desired_da = new_drift_da = drift_da
    elif abs(error_dl) > tolerance[1]:
        plan = plan_drift(roe_now, target, chief, window_s, max_drift_da, j2, r_eq, mu, fine_da)
        desired_da = new_drift_da = plan.drift_da
        drift_s = plan.duration_s

    d_da = desired_da - float(roe_now[0])
    d_de = target[2:4] - roe_now[2:4]
    d_di = target[4:6] - roe_now[4:6]
    burns: list[Burn] = []
    da_threshold = tolerance[0] if drift_da is None and new_drift_da is None else 0.5 * fine_da
    if abs(d_da) > da_threshold or math.hypot(*d_de) > tolerance[2]:
        pair = in_plane_pair(d_da, float(d_de[0]), float(d_de[1]), a, n)
        if sunlit is not None and not all(sunlit(b.u) for b in pair):
            locations = sunlit_locations(sunlit, [b.u for b in pair] or [0.0])
            pair = in_plane_at(d_da, float(d_de[0]), float(d_de[1]), locations, a, n)
        burns += pair
    if math.hypot(*d_di) > tolerance[3]:
        burn = out_of_plane(float(d_di[0]), float(d_di[1]), a, n)
        if sunlit is not None and not sunlit(burn.u):
            burn = out_of_plane(float(d_di[0]), float(d_di[1]), a, n, opposite=True)
        burns.append(burn)
    return Correction(burns=tuple(burns), drift_da=new_drift_da, drift_s=drift_s)


def in_plane_sequence(d_da: float, d_dex: float, d_dey: float, d_dl: float, da_now: float,
                      times_s: Sequence[float], locations_u: Sequence[float], a: float,
                      n: float, da_dot: float = 0.0) -> list[tuple[float, Burn]]:
    """Along-track burns at the given times [s from now] and arguments of
    latitude [rad] that change ``da`` by ``d_da`` and the eccentricity
    vector by ``(d_dex, d_dey)`` and move ``dl`` by ``d_dl`` by the last
    burn, with ``da`` ``da_now`` until the first: four conditions, so at
    least four burns; with more, the smallest sum of squares (least
    squares, minimum norm). Unlike :func:`in_plane_pair`, the mean
    longitude ends where it should: a pair alone moves it by
    ``1.5 n (d(da)_1) T/2`` (24 m for a 10 m eccentricity change at
    550 km), because ``da`` is off between its burns.

    With a differential-drag decay ``da_dot`` [1/s], ``da`` is
    ``da_now + d_da`` at the last burn, drag included, and the mean
    longitude's extra drift ``-3/4 n da_dot t^2`` is allowed for."""
    end_s = max(times_s)
    scale = 2.0 / (n * a)  # d(da) per m/s along-track
    matrix = np.array([[scale] * len(times_s),
                       [scale * math.cos(u) for u in locations_u],
                       [scale * math.sin(u) for u in locations_u],
                       [-1.5 * n * scale * (end_s - t) for t in times_s]])
    wanted = np.array([d_da - da_dot * end_s, d_dex, d_dey,
                       d_dl + 1.5 * n * da_now * end_s + 0.75 * n * da_dot * end_s ** 2])
    dv = np.linalg.lstsq(matrix, wanted, rcond=None)[0]
    return sorted(((float(t), Burn(u=float(u) % (2.0 * math.pi), dv_rtn=(0.0, float(v), 0.0), kind="in-plane"))
                   for t, u, v in zip(times_s, locations_u, dv) if abs(v) > 1e-12), key=lambda p: p[0])


def sequence_dl_shift(scheduled: Sequence[tuple[float, Burn]], a: float, n: float) -> float:
    """How much further [-] ``dl`` moves by the end of a burn sequence
    (:func:`schedule_burns` output) than if its total change of ``da`` were
    made now: each along-track burn's ``d(da)`` acts only from its time
    ``t_i`` on, so ``1.5 n sum(d(da)_i t_i)``. A pair half an orbit apart
    or three burns around the eclipse leave ``da`` off between burns, and
    this is the ``dl`` that costs."""
    return 1.5 * n * sum(2.0 * burn.dv_rtn[1] / (n * a) * when for when, burn in scheduled)


def sunlit_locations(sunlit: Callable[[float], bool], preferred: Sequence[float], count: int = 3,
                     step_rad: float = math.radians(5.0), min_separation_rad: float = math.radians(20.0)
                     ) -> list[float]:
    """``count`` distinct sunlit arguments of latitude [rad] for
    :func:`in_plane_at`: the sunlit one nearest each ``preferred``
    location first, then the sunlit ones farthest from those chosen. The
    ``preferred`` locations themselves when no location is sunlit."""
    grid = [k * step_rad for k in range(int(round(2.0 * math.pi / step_rad)))]
    lit = [u for u in grid if sunlit(u)]
    if not lit:
        return list(preferred)

    def separation(u1: float, u2: float) -> float:
        return abs(wrap_pi(u1 - u2))

    chosen: list[float] = []
    for u in preferred:
        nearest = min(lit, key=lambda candidate: separation(candidate, u))
        if all(separation(nearest, c) >= min_separation_rad for c in chosen):
            chosen.append(nearest)
    while len(chosen) < count:
        candidate = max(lit, key=lambda u: min((separation(u, c) for c in chosen), default=math.pi))
        if chosen and min(separation(candidate, c) for c in chosen) < min_separation_rad:
            break  # the sunlit arc is too short for more distinct locations
        chosen.append(candidate)
    return chosen[:count]


def schedule_burns(burns: Sequence[Burn], u_now: float, n: float, max_dv_per_burn: float,
                   min_lead_s: float, min_separation_s: float) -> list[tuple[float, Burn]]:
    """When to fire each burn, as ``(seconds from now, burn)`` in time
    order: the next time the spacecraft passes the burn's argument of
    latitude, at least ``min_lead_s`` ahead. A burn larger than
    ``max_dv_per_burn`` [m/s] is split into equal parts at the same
    location on consecutive orbits; a part closer than
    ``min_separation_s`` to one already scheduled waits an orbit."""
    period_s = 2.0 * math.pi / n
    pieces: list[tuple[float, Burn]] = []
    for burn in burns:
        parts = max(1, math.ceil(burn.magnitude / max_dv_per_burn)) if max_dv_per_burn > 0.0 else 1
        part = Burn(u=burn.u, dv_rtn=tuple(x / parts for x in burn.dv_rtn), kind=burn.kind)
        lead_s = ((burn.u - u_now) % (2.0 * math.pi)) / n
        if lead_s < min_lead_s:
            lead_s += period_s
        pieces += [(lead_s + k * period_s, part) for k in range(parts)]
    scheduled: list[tuple[float, Burn]] = []
    for when, part in sorted(pieces, key=lambda p: p[0]):
        while any(abs(when - other) < min_separation_s for other, _ in scheduled):
            when += period_s
        scheduled.append((when, part))
    return sorted(scheduled, key=lambda p: p[0])


# -- formation design ---------------------------------------------------------

def safe_formation(along_track_m: float, radial_m: float, cross_track_m: float, phase_deg: float,
                   a: float) -> np.ndarray:
    """ROE (dimensionless) of a passively safe formation: the follower
    ``along_track_m`` ahead of the chief, moving on an ellipse of radial
    half-size ``radial_m`` and cross-track half-size ``cross_track_m``
    around that point, with parallel e/i vectors at ``phase_deg``. A phase
    of 90 deg puts the inclination vector along ``diy``, which J2 does not
    turn (``dix = 0``)."""
    phase = math.radians(phase_deg)
    return np.array([0.0, along_track_m, radial_m * math.cos(phase), radial_m * math.sin(phase),
                     cross_track_m * math.cos(phase), cross_track_m * math.sin(phase)]) / a


def min_radial_normal_separation(roe: Sequence[float], a: float) -> float:
    """The closest approach [m] in the radial/cross-track plane over an
    orbit, ``da`` taken as zero (D'Amico and Montenbruck 2006)::

        sqrt(2) a |de . di| / sqrt(|de|^2 + |di|^2 + |de + di| |de - di|)
    """
    de = np.array([roe[2], roe[3]], dtype=float)
    di = np.array([roe[4], roe[5]], dtype=float)
    denominator = math.sqrt(float(de @ de + di @ di)
                            + float(np.linalg.norm(de + di) * np.linalg.norm(de - di)))
    if denominator == 0.0:
        return 0.0
    return math.sqrt(2.0) * a * abs(float(de @ di)) / denominator
