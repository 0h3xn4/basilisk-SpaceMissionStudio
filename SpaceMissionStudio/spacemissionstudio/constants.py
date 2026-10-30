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
"""The one set of physical constants SpaceMissionStudio's own calculations
use (transparency plan, Phase 3c): Basilisk's, from
``architecture/utilities/astroConstants.h``, the ones every simulated orbit
already uses. The lifetime, the budget, the orbit design, the generators,
the checks and the explanations take them from here, so an estimate and a
run of the same orbit agree on the Earth they are about.

``tests/test_constants.py`` checks each value against Basilisk's own, so
they cannot drift apart. Without Basilisk, and without the GUI.

Not here: the gravity field files' own reference values (GGM03S, GGM2B),
which only the field's coefficients use, and the constants inside
Basilisk's modules (for instance its faceted SRP's 1368 W/m^2), which this
tool does not change (``docs/models/constants.md``).
"""

import math

# -- Earth -------------------------------------------------------------------------------------
EARTH_GM_M3_S2 = 398600.436e9  # [m^3/s^2] MU_EARTH
EARTH_EQUATORIAL_RADIUS_M = 6378136.6  # [m] REQ_EARTH, from SPICE
EARTH_J2 = 1082.616e-6  # [-] J2_EARTH
# The Earth turns as SPICE's pck00010 turns it (IAU 2009, IAU_EARTH): the prime meridian is W0 + W' d
# past the equator's node, d in TDB days from J2000. Not astroConstants.h's OMEGA_EARTH, whose
# 23.9345 h day is rounded and 1.2e-6 slow (docs/models/constants.md).
IAU_EARTH_PRIME_MERIDIAN_DEG = 190.147  # [deg] W0
IAU_EARTH_PRIME_MERIDIAN_RATE_DEG_DAY = 360.9856235  # [deg/day] W'
EARTH_ROTATION_RAD_S = math.radians(IAU_EARTH_PRIME_MERIDIAN_RATE_DEG_DAY) / 86400.0  # [rad/s]

# -- Sun ---------------------------------------------------------------------------------------
ASTRONOMICAL_UNIT_M = 149597870693.0  # [m] AU2M
SOLAR_FLUX_1AU_W_M2 = 1361.0  # [W/m^2] SOLAR_FLUX_EARTH (ECSS-E-ST-10-04C Table 6-2 gives the same)

# -- defined values ----------------------------------------------------------------------------
STANDARD_GRAVITY_M_S2 = 9.80665  # [m/s^2] g0, CGPM 1901 (Basilisk's EARTH_GRAV): Isp in seconds to exhaust speed
SPEED_OF_LIGHT_M_S = 299792458.0  # [m/s] SI definition

# -- the central bodies a run can use (schema.scenario.SUPPORTED_CENTRAL_BODIES) ---------------
CENTRAL_BODY_EQUATORIAL_RADIUS_KM = {  # [km] REQ_*
    "sun": 695000.0,
    "mercury": 2439.7,
    "venus": 6051.8,
    "earth": EARTH_EQUATORIAL_RADIUS_M / 1000.0,
    "moon": 1737.4,
    "mars barycenter": 3396.19,
    "jupiter barycenter": 71492.0,
}
CENTRAL_BODY_J2 = {  # [-] J2_* of the bodies a run can give spherical-harmonics gravity
    "earth": EARTH_J2,
    "mars barycenter": 1960.45e-6,
}
