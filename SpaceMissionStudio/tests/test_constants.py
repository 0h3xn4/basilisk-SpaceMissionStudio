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
"""The one set of constants (spacemissionstudio.constants, transparency
plan Phase 3c): Basilisk's own values, and the only ones the analyses use."""

import math
from pathlib import Path

import pytest

from spacemissionstudio import constants


@pytest.mark.requires_basilisk
def test_the_constants_are_basilisks():
    """Each constant equals the one Basilisk's simulation uses: its gravity
    factory's Earth and astroConstants.h (through orbitalMotion); the
    Earth's rotation within the rounding of the binding."""
    from Basilisk.utilities import orbitalMotion as om
    from Basilisk.utilities import simIncludeGravBody

    earth = simIncludeGravBody.gravBodyFactory().createEarth()
    assert constants.EARTH_GM_M3_S2 == earth.mu == om.MU_EARTH * 1e9
    assert constants.EARTH_EQUATORIAL_RADIUS_M == earth.radEquator == om.REQ_EARTH * 1e3
    assert constants.EARTH_J2 == om.J2_EARTH
    assert constants.ASTRONOMICAL_UNIT_M == om.AU * 1e3
    # The C header's 2 pi / 23.9345 h rounds the sidereal day, 1.1e-6 below the binding's 7.292115e-05;
    # the header's is the one kept (the lifetime's atmosphere rotation, unchanged).
    assert constants.EARTH_ROTATION_RAD_S == pytest.approx(om.OMEGA_EARTH, rel=2e-6)
    for body, radius_km in constants.CENTRAL_BODY_EQUATORIAL_RADIUS_KM.items():
        name = {"mars barycenter": "MARS", "jupiter barycenter": "JUPITER"}.get(body, body.upper())
        assert radius_km == getattr(om, f"REQ_{name}"), body
    for body, j2 in constants.CENTRAL_BODY_J2.items():
        name = {"mars barycenter": "MARS"}.get(body, body.upper())
        assert j2 == getattr(om, f"J2_{name}"), body


def test_the_c_header_defines_what_the_python_binding_rounds():
    """The Earth's rotation and the solar flux, as astroConstants.h
    defines them (the binding rounds the first and lacks the second)."""
    header = (Path(__file__).resolve().parents[2] / "src" / "architecture" / "utilities" / "astroConstants.h")
    if not header.exists():
        pytest.skip("Basilisk's sources are not next to SpaceMissionStudio")
    text = header.read_text(encoding="utf-8")
    assert "#define OMEGA_EARTH       (2*MPI/23.9345/3600.)" in text
    assert constants.EARTH_ROTATION_RAD_S == 2.0 * math.pi / 23.9345 / 3600.0
    assert "#define SOLAR_FLUX_EARTH    1361.0" in text and constants.SOLAR_FLUX_1AU_W_M2 == 1361.0


def test_every_analysis_takes_the_one_set():
    """The analyses' Earth constants are the one set's, not copies of
    their own: the lifetime, the budget, the orbit design, the generators,
    the scenario checks, the environment estimates and optical navigation."""
    from spacemissionstudio.engine import (constellation, environment_models, lifetime, opnav, orbit_design,
                                           propellant_budget, scenario_checks)

    gm, radius, j2 = constants.EARTH_GM_M3_S2, constants.EARTH_EQUATORIAL_RADIUS_M, constants.EARTH_J2
    assert (lifetime.MU_EARTH_M3_S2, lifetime.REQ_EARTH_M, lifetime.J2_EARTH) == (gm, radius, j2)
    assert lifetime.OMEGA_EARTH_RAD_S == constants.EARTH_ROTATION_RAD_S
    assert (propellant_budget.MU_EARTH_M3_S2, propellant_budget.REQ_EARTH_M) == (gm, radius)
    assert (orbit_design._EARTH_MU_KM3_S2 * 1e9, orbit_design._EARTH_REQUATOR_KM * 1e3) == (gm, radius)
    assert orbit_design._EARTH_J2 == j2
    assert constellation.CENTRAL_BODY_EQUATORIAL_RADIUS_KM is constants.CENTRAL_BODY_EQUATORIAL_RADIUS_KM
    assert constellation.CENTRAL_BODY_J2 is constants.CENTRAL_BODY_J2
    assert (scenario_checks._MU_M3_S2, scenario_checks._R_EARTH_M, scenario_checks._J2) == (gm, radius, j2)
    assert scenario_checks._EARTH_RADIUS_M == radius
    assert (environment_models._EARTH_GM_M3_S2, environment_models._EARTH_RADIUS_M,
            environment_models._EARTH_J2) == (gm, radius, j2)
    assert environment_models.ASTRONOMICAL_UNIT_M == constants.ASTRONOMICAL_UNIT_M
    assert environment_models.TOTAL_SOLAR_IRRADIANCE_W_M2 == constants.SOLAR_FLUX_1AU_W_M2
    assert opnav.BODY_RADIUS_M["earth"] == radius


def test_the_checks_judge_re_entry_by_the_lifetimes_parameter():
    """The scenario checks call a perigee below the lifetime's re-entry
    altitude a re-entry within an orbit; they used a 120 km of their own,
    which a project changing lifetime.reentry_altitude_km did not move."""
    from spacemissionstudio.config.registry import Configuration
    from spacemissionstudio.engine.scenario_checks import plausibility_warnings
    from spacemissionstudio.schema.scenario import OrbitIC, Scenario, SpacecraftConfig

    def warnings(configuration):
        orbit = OrbitIC(type="classical_elements", semi_major_axis_km=6378.1366 + 150.0, eccentricity=0.0,  # [km]
                        inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0)  # [deg]
        scenario = Scenario(name="low", epoch_utc="2030-01-01T00:00:00",
                            spacecraft=[SpacecraftConfig(name="s", orbit=orbit)])
        scenario.configuration = configuration
        return [w for w in plausibility_warnings(scenario) if "re-enters" in w]

    assert warnings(None) == []  # a 150 km perigee is above the default 120 km
    assert warnings(Configuration({"lifetime.reentry_altitude_km": 200.0})) == [
        "s: perigee at 150 km -- it re-enters within about an orbit"]
