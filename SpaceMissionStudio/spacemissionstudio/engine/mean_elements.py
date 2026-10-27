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
critical inclination.

Basilisk's ``orbitalMotion.clMeanOscMap`` (first-order Brouwer-Lyddane,
Schaub & Junkins) has long-period terms divided by ``1 - 5 cos^2 i``,
which is zero at the critical inclination, 63.435 deg and 116.565 deg. A
600 km orbit at 63.435 deg came back with a mean perigee of -1159 km; a
Molniya orbit there with an eccentricity above 1 (audit of 2026-10-27).

:func:`cl_mean_osc_map` calls ``clMeanOscMap`` unchanged everywhere else.
Within :data:`CRITICAL_BAND_RAD` of either critical value it evaluates the
map at the nearer edge of the band and carries the inclination difference
across: the other elements' corrections are those at the edge. Checked
against the elements averaged over one orbit of the J2 motion (no
singular terms): within 0.4 km of mean perigee for a 600 km orbit and
0.7 km for a Molniya orbit across the band, where the plain map was off
by up to 1700 km and failed (``tests/test_mean_elements.py``, which
allows 0.5 and 1 km).
"""

from __future__ import annotations

import math

#: The critical inclination [rad]: ``1 - 5 cos^2 i = 0`` (63.435 deg).
CRITICAL_INCLINATION_RAD = math.acos(math.sqrt(0.2))
#: Half-width of the band around it (and around 180 deg minus it) where
#: the map is evaluated at the band's edge [rad].
CRITICAL_BAND_RAD = math.radians(1.0)


def mapping_inclination(inclination_rad: float) -> float:
    """The inclination [rad] to evaluate ``clMeanOscMap`` at: the given
    one, or the nearer edge of the critical band it lies in."""
    for critical in (CRITICAL_INCLINATION_RAD, math.pi - CRITICAL_INCLINATION_RAD):
        offset = inclination_rad - critical
        if abs(offset) < CRITICAL_BAND_RAD:
            return critical + math.copysign(CRITICAL_BAND_RAD, offset if offset else -1.0)
    return inclination_rad


def cl_mean_osc_map(req_m: float, j2: float, source, target, sign: int) -> None:
    """``clMeanOscMap(req, j2, source, target, sign)`` (sign -1: osculating
    to mean, +1: mean to osculating), finite at the critical inclination.
    ``source`` is left unchanged."""
    from Basilisk.utilities import orbitalMotion

    inclination = source.i
    used = mapping_inclination(inclination)
    if used == inclination:
        orbitalMotion.clMeanOscMap(req_m, j2, source, target, sign)
        return
    moved = orbitalMotion.ClassicElements()
    moved.a, moved.e, moved.i = source.a, source.e, used
    moved.Omega, moved.omega, moved.f = source.Omega, source.omega, source.f
    orbitalMotion.clMeanOscMap(req_m, j2, moved, target, sign)
    target.i += inclination - used
