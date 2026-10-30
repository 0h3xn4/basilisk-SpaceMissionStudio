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
    # The Earth's rotation is SPICE's pck00010 rate, 5e-8 from the binding's rounded 7.292115e-05 (the
    # C header's 2 pi / 23.9345 h is 1.2e-6 slow: test_the_earth_turns_as_spice_turns_it).
    assert constants.EARTH_ROTATION_RAD_S == pytest.approx(om.OMEGA_EARTH, rel=1e-7)
    for body, radius_km in constants.CENTRAL_BODY_EQUATORIAL_RADIUS_KM.items():
        name = {"mars barycenter": "MARS", "jupiter barycenter": "JUPITER"}.get(body, body.upper())
        assert radius_km == getattr(om, f"REQ_{name}"), body
    for body, j2 in constants.CENTRAL_BODY_J2.items():
        name = {"mars barycenter": "MARS"}.get(body, body.upper())
        assert j2 == getattr(om, f"J2_{name}"), body
    from spacemissionstudio.engine.geo_station_keeping import _OMEGA_EARTH  # needs Basilisk

    assert _OMEGA_EARTH == constants.EARTH_ROTATION_RAD_S


def test_the_c_header_defines_what_the_python_binding_rounds():
    """The solar flux and standard gravity, as astroConstants.h defines
    them (the binding lacks them)."""
    header = (Path(__file__).resolve().parents[2] / "src" / "architecture" / "utilities" / "astroConstants.h")
    if not header.exists():
        pytest.skip("Basilisk's sources are not next to SpaceMissionStudio")
    text = header.read_text(encoding="utf-8")
    assert "#define SOLAR_FLUX_EARTH    1361.0" in text and constants.SOLAR_FLUX_1AU_W_M2 == 1361.0
    assert "#define EARTH_GRAV 9.80665" in text and constants.STANDARD_GRAVITY_M_S2 == 9.80665


def test_the_earth_turns_as_spice_turns_it():
    """The Earth's rotation rate is the prime meridian's rate of pck00010,
    the IAU_EARTH model the pass predictions and the GEO elements use and
    the kernel the simulation loads; astroConstants.h's 2 pi / 23.9345 h
    rounds the sidereal day and is 1.2e-6 slow."""
    assert (constants.IAU_EARTH_PRIME_MERIDIAN_DEG, constants.IAU_EARTH_PRIME_MERIDIAN_RATE_DEG_DAY) == (190.147,
                                                                                                    360.9856235)
    assert constants.EARTH_ROTATION_RAD_S == math.radians(360.9856235) / 86400.0
    assert (2.0 * math.pi / 23.9345 / 3600.0) / constants.EARTH_ROTATION_RAD_S - 1.0 == pytest.approx(-1.2e-6, abs=1e-7)


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
    from spacemissionstudio.engine import ccsds_odm, link_budget, propellant_bookkeeping, scenario_explainer

    assert ccsds_odm.EARTH_GM_KM3_S2 * 1e9 == gm
    assert scenario_explainer._BODY_RADIUS_KM is constants.CENTRAL_BODY_EQUATORIAL_RADIUS_KM
    assert propellant_budget.G0_M_S2 == constants.STANDARD_GRAVITY_M_S2
    assert link_budget._C_LIGHT_M_S == environment_models.SPEED_OF_LIGHT_M_S == constants.SPEED_OF_LIGHT_M_S
    assert propellant_bookkeeping.total_delta_v_budget.__defaults__[-1] == constants.STANDARD_GRAVITY_M_S2


def test_no_module_keeps_a_copy_of_a_constant():
    """No analysis writes one of the set's values as a literal of its own
    (Phase 3c missed g0 in six controllers, GEO station keeping's Earth
    rotation, the ODM's GM, Explain's body radii and the speed of light)."""
    import tokenize

    package = Path(__file__).resolve().parents[1] / "spacemissionstudio"
    copies = ("9.80665", "299792458", "398600.436", "7.2921159", "6378.1366", "6378136.6", "1082.616",
              "360.9856235", "69.184", "1.81554", "14.928")
    found = []
    for path in sorted(package.rglob("*.py")):
        if path.name == "constants.py":
            continue
        with path.open("rb") as stream:  # number literals only: a docstring may cite a value
            found += [f"{path.relative_to(package)}:{token.start[0]}: {token.string}"
                      for token in tokenize.tokenize(stream.readline)
                      if token.type == tokenize.NUMBER and any(token.string.startswith(c) for c in copies)]
    assert found == []


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


def test_the_earth_rotation_angle_counts_the_leap_seconds_of_its_date():
    """The pass predictions and the GEO elements turn the Earth by TDB
    days from J2000 with the leap seconds of the scenario's date. They added
    a fixed 69.184 s (37 leap seconds), 3 s short for a 2010 epoch: the Earth
    turned 0.0125 deg too far, a quarter of a 0.05 deg GEO box. Across the
    leap second of 2016-12-31, a UTC day is 86 401 s of TDB."""
    from spacemissionstudio.engine import orbit_design, scenario_checks, time_system

    before, after = "2016-12-31T12:00:00", "2017-01-01T12:00:00"
    turned = math.degrees(scenario_checks._earth_rotation_angle(after, 0.0)
                          - scenario_checks._earth_rotation_angle(before, 0.0))  # [deg]
    assert turned == pytest.approx(360.9856235 * 86401.0 / 86400.0, abs=1e-6)
    geo = orbit_design.geostationary_elements_deg(after, 0.0)[2] - orbit_design.geostationary_elements_deg(before, 0.0)[2]
    assert geo % 360.0 == pytest.approx((360.9856235 * 86401.0 / 86400.0) % 360.0, abs=1e-6)
    days = time_system.tdb_seconds_past_j2000("2010-01-01T00:00:00") / 86400.0  # [day]
    assert orbit_design.geostationary_elements_deg("2010-01-01T00:00:00", 0.0)[2] == pytest.approx(
        (190.147 + 360.9856235 * days) % 360.0, abs=1e-9)


@pytest.mark.requires_basilisk
def test_the_earths_triaxiality_is_the_gravity_fields():
    """GEO station keeping plans with the J22 and lambda22 of the GGM03S
    file the run loads (they were 1.81554e-6 and -14.928 deg, with no
    source recorded)."""
    from Basilisk.simulation.gravityEffector import loadGravFromFileToList

    from spacemissionstudio.engine import gravity_field, kernels
    from spacemissionstudio.engine.geo_station_keeping import _J22, _LAMBDA_22

    c_bar, s_bar, _, _ = loadGravFromFileToList(str(kernels.cached_path(gravity_field.FIELD_FILES["earth"])), 2)
    scale = math.sqrt(2.0 * 5.0 / math.factorial(4))  # [-] full normalization of degree 2, order 2
    c22, s22 = c_bar[2][2] * scale, s_bar[2][2] * scale  # [-] unnormalized
    assert constants.EARTH_J22 == pytest.approx(math.hypot(c22, s22), rel=1e-12)
    assert constants.EARTH_LAMBDA22_DEG == pytest.approx(math.degrees(0.5 * math.atan2(s22, c22)), abs=1e-10)
    assert (_J22, _LAMBDA_22) == (constants.EARTH_J22, math.radians(constants.EARTH_LAMBDA22_DEG))
