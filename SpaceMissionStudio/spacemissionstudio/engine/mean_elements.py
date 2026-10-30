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
"""J2 mean <-> osculating classical elements that stay finite at the
critical inclination and for equatorial orbits.

Basilisk's ``orbitalMotion.clMeanOscMap`` (first-order Brouwer-Lyddane,
Schaub & Junkins) has long-period terms divided by ``1 - 5 cos^2 i``,
which is zero at the critical inclination, 63.435 deg and 116.565 deg. A
600 km orbit at 63.435 deg came back with a mean perigee of -1159 km; a
Molniya orbit there with an eccentricity above 1 (audit of 2026-10-27).
It also divides by ``tan i``: at 0 deg exactly it raises
ZeroDivisionError.

:func:`cl_mean_osc_map` calls ``clMeanOscMap`` unchanged everywhere else.
Within :data:`CRITICAL_BAND_RAD` of either critical value it evaluates the
map at both edges of the band, carries the inclination difference across,
and blends the two by distance (in equinoctial elements): the map stays
continuous, so two satellites on either side of the critical value get
consistent mean elements (with the nearer edge alone, a jump at the
critical value put a follower 200 m off in semi-major axis). Within
:data:`EQUATORIAL_BAND_RAD` of 0 or 180 deg it evaluates the map at the
band's edge. Checked against the elements averaged over one orbit of the
J2 motion (no singular terms): within 0.02 km of mean perigee for a
600 km orbit and 0.7 km for a Molniya orbit across the band, where the
plain map was off by up to 1700 km and failed (``tests/test_mean_elements.py``,
which allows 0.5 and 1 km).

:func:`osculating_from_mean` inverts the map, for placing satellites by
their mean elements (the Walker and phasing generators).
"""

from __future__ import annotations

import math

#: The critical inclination [rad]: ``1 - 5 cos^2 i = 0`` (63.435 deg).
CRITICAL_INCLINATION_RAD = math.acos(math.sqrt(0.2))
#: Half-width of the band around it (and around 180 deg minus it) where
#: the map is blended from its values at the band's edges [rad].
CRITICAL_BAND_RAD = math.radians(1.0)
#: Below this inclination (and above 180 deg minus it) the map is
#: evaluated at the band's edge [rad].
EQUATORIAL_BAND_RAD = math.radians(1.0)
#: Correction steps in :func:`osculating_from_mean` (below a millimetre of
#: semi-major axis in two, as in ``roe_formation.follower_orbit``).
_PLACEMENT_ITERATIONS = 6


def _critical_band(inclination_rad: float):
    """``(lower edge, upper edge)`` [rad] of the critical band holding the
    inclination, or None."""
    for critical in (CRITICAL_INCLINATION_RAD, math.pi - CRITICAL_INCLINATION_RAD):
        if abs(inclination_rad - critical) < CRITICAL_BAND_RAD:
            return critical - CRITICAL_BAND_RAD, critical + CRITICAL_BAND_RAD
    return None


def _map_at(req_m: float, j2: float, source, target, sign: int, used_rad: float) -> None:
    """``clMeanOscMap`` evaluated at inclination ``used_rad``, with the
    inclination difference carried across."""
    from Basilisk.utilities import orbitalMotion

    moved = orbitalMotion.ClassicElements()
    moved.a, moved.e, moved.i = source.a, source.e, used_rad
    moved.Omega, moved.omega, moved.f = source.Omega, source.omega, source.f
    orbitalMotion.clMeanOscMap(req_m, j2, moved, target, sign)
    target.i += source.i - used_rad
    if not 0.0 <= target.i <= math.pi:
        # Carried past the end of the inclination range (an equatorial
        # orbit): the same orbit, with the node and perigee turned by 180 deg.
        target.i = -target.i if target.i < 0.0 else 2.0 * math.pi - target.i
        target.Omega = (target.Omega + math.pi) % (2.0 * math.pi)
        target.omega = (target.omega + math.pi) % (2.0 * math.pi)


def cl_mean_osc_map(req_m: float, j2: float, source, target, sign: int) -> None:
    """``clMeanOscMap(req, j2, source, target, sign)`` (sign -1: osculating
    to mean, +1: mean to osculating), finite and continuous at the critical
    inclination and at 0 and 180 deg. ``source`` is left unchanged."""
    from Basilisk.utilities import orbitalMotion

    inclination = source.i
    band = _critical_band(inclination)
    if band is not None:
        lower, upper = band
        retrograde = inclination > math.pi / 2.0
        at_lower, at_upper = orbitalMotion.ClassicElements(), orbitalMotion.ClassicElements()
        _map_at(req_m, j2, source, at_lower, sign, lower)
        _map_at(req_m, j2, source, at_upper, sign, upper)
        weight = (upper - inclination) / (upper - lower)  # 1 at the lower edge, 0 at the upper
        low, high = _equinoctial(at_lower, retrograde), _equinoctial(at_upper, retrograde)
        blended = [h + weight * (lo - h) for lo, h in zip(low[:5], high[:5])]
        blended.append(high[5] + weight * _wrap_pi(low[5] - high[5]))
        _set_equinoctial(target, blended, retrograde)
    elif inclination < EQUATORIAL_BAND_RAD:
        _map_at(req_m, j2, source, target, sign, EQUATORIAL_BAND_RAD)
    elif inclination > math.pi - EQUATORIAL_BAND_RAD:
        _map_at(req_m, j2, source, target, sign, math.pi - EQUATORIAL_BAND_RAD)
    else:
        orbitalMotion.clMeanOscMap(req_m, j2, source, target, sign)


def _equinoctial(elements, retrograde: bool):
    """Equinoctial elements (Broucke and Cefola, with the retrograde
    factor), well defined at e = 0 and at i = 0 (prograde) or 180 deg
    (retrograde): a, h, k, p, q and the true longitude L."""
    factor = -1.0 if retrograde else 1.0
    perigee_longitude = elements.omega + factor * elements.Omega
    # tan(i/2), or for a retrograde orbit cot(i/2) = tan((180 deg - i)/2)
    half = math.tan(((math.pi - elements.i) if retrograde else elements.i) / 2.0)
    return [elements.a, elements.e * math.sin(perigee_longitude), elements.e * math.cos(perigee_longitude),
            half * math.sin(elements.Omega), half * math.cos(elements.Omega), perigee_longitude + elements.f]


def _set_equinoctial(elements, values, retrograde: bool) -> None:
    factor = -1.0 if retrograde else 1.0
    a, h, k, p, q, true_longitude = values
    elements.a = a
    elements.e = math.hypot(h, k)
    elements.Omega = math.atan2(p, q) % (2.0 * math.pi)
    tilt = 2.0 * math.atan(math.hypot(p, q))
    elements.i = math.pi - tilt if retrograde else tilt
    perigee_longitude = math.atan2(h, k)
    elements.omega = (perigee_longitude - factor * elements.Omega) % (2.0 * math.pi)
    elements.f = (true_longitude - perigee_longitude) % (2.0 * math.pi)


def _wrap_pi(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def osculating_from_mean(req_m: float, j2: float, mean):
    """The osculating classical elements whose J2 mean elements are
    ``mean`` (``ClassicElements``, true anomaly in ``f``). The first-order
    map is not its own inverse (second order in J2: a few metres of
    semi-major axis, enough to drift satellites apart), so the osculating
    elements are corrected until mapping them back gives ``mean``, as
    ``roe_formation.follower_orbit`` does, in equinoctial elements (well
    defined for circular and equatorial orbits)."""
    from Basilisk.utilities import orbitalMotion

    osculating = orbitalMotion.ClassicElements()
    cl_mean_osc_map(req_m, j2, mean, osculating, 1)
    retrograde = mean.i > math.pi / 2.0
    wanted = _equinoctial(mean, retrograde)
    for _ in range(_PLACEMENT_ITERATIONS):
        back = orbitalMotion.ClassicElements()
        cl_mean_osc_map(req_m, j2, osculating, back, -1)
        step = [w - b for w, b in zip(wanted, _equinoctial(back, retrograde))]
        step[5] = _wrap_pi(step[5])
        _set_equinoctial(osculating, [x + d for x, d in zip(_equinoctial(osculating, retrograde), step)],
                         retrograde)
    return osculating


def series_trace(result, spacecraft: str):
    """How the run's mean-element series of ``spacecraft`` were made
    (``engine.trace``; transparency plan, Phase 4a): the map, its radius
    and J2, the bands, and how many samples fell in each. None when the run
    has no mean elements for it. Basilisk-free: it reads the run's series."""
    import numpy as np

    from .. import constants
    from .trace import Quantity, Trace

    mean_name = f"{spacecraft}.orbit_elements_mean.semi_major_axis"
    inclination_name = f"{spacecraft}.orbit_elements.inclination"
    if mean_name not in result.series or inclination_name not in result.series:
        return None
    inclination = np.asarray(result.series[inclination_name].data[:, 0], dtype=float)  # [rad] osculating
    mean_a = np.asarray(result.series[mean_name].data[:, 0], dtype=float)  # [m]
    critical = sum(_critical_band(float(i)) is not None for i in inclination)
    equatorial = int(np.sum((inclination < EQUATORIAL_BAND_RAD) | (inclination > math.pi - EQUATORIAL_BAND_RAD)))
    return Trace(
        f"Mean orbital elements ({spacecraft})", "mean", "first-order J2 mean", "[-]",
        "mean = osculating with J2's short-period terms removed: clMeanOscMap(R_eq, J2, osculating, mean, -1); "
        "within b_crit of the critical inclination, the map's values at the band's edges blended by distance; "
        "within b_eq of 0 or 180 deg, the map at the band's edge",
        "Basilisk's orbitalMotion.clMeanOscMap (first-order Brouwer-Lyddane, Schaub & Junkins); "
        "SpaceMissionStudio's handling of the critical inclination (engine.mean_elements)",
        inputs=(Quantity("osculating elements, each sample", "osculating", f"{inclination.size} samples", "[-]",
                         f"last run: {spacecraft}.orbit_elements.*, from the recorded position and velocity"),
                Quantity("the Earth's equatorial radius", "R_eq", constants.EARTH_EQUATORIAL_RADIUS_M, "[m]",
                         "constant: EARTH_EQUATORIAL_RADIUS_M (Basilisk's radEquator of the run's Earth)"),
                Quantity("the Earth's J2", "J2", constants.EARTH_J2, "[-]",
                         "constant: EARTH_J2 (Basilisk's orbitalMotion.J2_EARTH)"),
                Quantity("half-width of the critical-inclination band", "b_crit", math.degrees(CRITICAL_BAND_RAD),
                         "[deg]", "constant: mean_elements.CRITICAL_BAND_RAD"),
                Quantity("half-width of the equatorial band", "b_eq", math.degrees(EQUATORIAL_BAND_RAD), "[deg]",
                         "constant: mean_elements.EQUATORIAL_BAND_RAD")),
        intermediates=(Quantity("samples within the critical band", "n_crit", critical, "[-]",
                                f"computed: from {inclination_name}"),
                       Quantity("samples within the equatorial band", "n_eq", equatorial, "[-]",
                                f"computed: from {inclination_name}"),
                       Quantity("samples with no closed orbit (no mean elements)", "n_none",
                                int(np.sum(~np.isfinite(mean_a))), "[-]", f"computed: from {mean_name}")),
        notes=("The run makes mean elements only for an Earth orbit with gravity of degree 2 or more, the J2 its "
               "motion holds.",
               "The critical inclination is 63.435 deg (and 116.565 deg), where 1 - 5 cos^2 i = 0 and the plain "
               "map's long-period terms are infinite."))
