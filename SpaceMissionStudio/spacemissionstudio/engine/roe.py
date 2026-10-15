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

**Passive safety** (D'Amico and Montenbruck, JGCD 29(3), 2006). With
``da = 0`` the radial and cross-track separations are an ellipse in the
radial/cross-track plane; it keeps away from the origin when the e/i
vectors are parallel. :func:`min_radial_normal_separation` is its
closest approach.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

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


def roe_to_rtn(roe: Sequence[float], u: float, a: float, n: float) -> Tuple[np.ndarray, np.ndarray]:
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


def secular_j2_rates(elements: MeanElements, j2: float, r_eq: float, mu: float) -> Tuple[float, float, float]:
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


def propagate_roe(roe: Sequence[float], chief: MeanElements, dt: float, j2: float, r_eq: float,
                  mu: float) -> np.ndarray:
    """The mean ROE ``dt`` [s] later (:func:`j2_stm`)."""
    return j2_stm(chief, dt, j2, r_eq, mu) @ np.asarray(roe, dtype=float)


# -- impulsive manoeuvres -------------------------------------------------------

@dataclass(frozen=True)
class Burn:
    """One impulsive burn: at mean argument of latitude ``u`` [rad], with
    an RTN delta-V [m/s]."""

    u: float  # [rad] where on the orbit to fire (chief's mean argument of latitude)
    dv_rtn: Tuple[float, float, float]  # [m/s] radial, along-track, cross-track
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


def in_plane_pair(d_da: float, d_dex: float, d_dey: float, a: float, n: float) -> List[Burn]:
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
                n: float) -> List[Burn]:
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


def out_of_plane(d_dix: float, d_diy: float, a: float, n: float, opposite: bool = False) -> Optional[Burn]:
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
               max_drift_da: float, j2: float, r_eq: float, mu: float) -> DriftPlan:
    """The ``da`` that brings ``dl`` to the target in ``window_s`` [s],
    the other ROE already at their target; with the J2 STM, so the drift
    the e/i vectors cause under J2 is included. Limited to
    ``|da| <= max_drift_da``; the drift then takes longer."""
    x = np.asarray(target, dtype=float).copy()
    x[1] = float(roe_now[1])
    phi = j2_stm(chief, window_s, j2, r_eq, mu)
    rate = phi[1, 0]  # d(dl) per unit da over the window
    without_da = float(phi[1] @ np.r_[0.0, x[1:]])
    drift_da = (float(target[1]) - without_da) / rate if rate != 0.0 else 0.0
    if abs(drift_da) <= max_drift_da:
        return DriftPlan(drift_da=drift_da, duration_s=window_s)
    drift_da = math.copysign(max_drift_da, drift_da)
    per_second = j2_stm(chief, 1.0, j2, r_eq, mu)
    rate_per_s = float(per_second[1] @ np.r_[drift_da, x[1:]] - x[1])  # d(dl)/dt at the capped da
    needed = wrap_pi(float(target[1]) - x[1])
    duration = needed / rate_per_s if rate_per_s != 0.0 else window_s
    return DriftPlan(drift_da=drift_da, duration_s=max(duration, window_s))


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
