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
"""Tests for spacemissionstudio.engine.constellation -- no Basilisk import, runs
anywhere. Checks the Walker-pattern math directly (RAAN/mean-anomaly
spacing, semi-major axis) rather than just "it doesn't crash".
"""

import pytest

from spacemissionstudio.engine.constellation import (
    CENTRAL_BODY_EQUATORIAL_RADIUS_KM,
    CENTRAL_BODY_J2,
    SeparationSchedule,
    WalkerConstellationRequest,
    generate_walker_constellation,
    simulated_j2,
)
from spacemissionstudio.schema.scenario import OrbitIC, PowerConfig, ScenarioValidationError, SpacecraftConfig


def _template(**overrides):
    defaults = dict(
        name="template", dry_mass_kg=50.0,
        orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
    )
    defaults.update(overrides)
    return SpacecraftConfig(**defaults)


def _request(**overrides):
    defaults = dict(total_satellites=12, num_planes=3, phasing_factor=1, altitude_km=780.0, inclination_deg=86.4)
    defaults.update(overrides)
    return WalkerConstellationRequest(**defaults)


def test_generates_total_satellites_count():
    """A 12-satellite Walker request gives 12 spacecraft with unique names."""
    sats = generate_walker_constellation(_request(), _template())
    assert len(sats) == 12
    assert len({s.name for s in sats}) == 12  # every name unique


def test_more_satellites_than_a_scenario_holds_are_refused_before_any_is_made():
    """Audit R9: --total-satellites 10000000 ran for more than a minute; the
    request is refused first, at a scenario's limit of 1000."""
    from spacemissionstudio.schema.scenario import MAX_SPACECRAFT

    assert len(generate_walker_constellation(_request(total_satellites=MAX_SPACECRAFT, num_planes=10),
                                             _template())) == MAX_SPACECRAFT
    with pytest.raises(ScenarioValidationError, match="total_satellites must be at most 1000"):
        generate_walker_constellation(_request(total_satellites=10_000_000, num_planes=1000), _template())


def test_semi_major_axis_matches_altitude_plus_earth_radius():
    """Every satellite's semi-major axis is Earth's equatorial radius plus the
    500 km altitude."""
    sats = generate_walker_constellation(_request(altitude_km=500.0), _template())
    expected_sma = CENTRAL_BODY_EQUATORIAL_RADIUS_KM["earth"] + 500.0
    for s in sats:
        assert s.orbit.semi_major_axis_km == pytest.approx(expected_sma)


def test_raan_spacing_is_360_over_planes_for_delta_pattern():
    """A delta pattern of 3 planes spaces them 360/3 = 120 deg apart in
    RAAN."""
    sats = generate_walker_constellation(_request(total_satellites=6, num_planes=3, phasing_factor=0), _template())
    raans = sorted({s.orbit.raan_deg for s in sats})
    assert raans == pytest.approx([0.0, 120.0, 240.0])


def test_raan_spacing_is_180_over_planes_for_star_pattern():
    """A star pattern of 3 planes spaces them 180/3 = 60 deg apart in RAAN."""
    sats = generate_walker_constellation(
        _request(total_satellites=6, num_planes=3, phasing_factor=0, pattern="star"), _template()
    )
    raans = sorted({s.orbit.raan_deg for s in sats})
    assert raans == pytest.approx([0.0, 60.0, 120.0])


def test_mean_anomaly_spacing_within_one_plane():
    """Four satellites in a plane are 90 deg apart in mean anomaly."""
    sats = generate_walker_constellation(_request(total_satellites=8, num_planes=2, phasing_factor=0), _template())
    plane1_anomalies = sorted(s.orbit.mean_anomaly_deg for s in sats if s.orbit.raan_deg == 0.0)
    assert plane1_anomalies == pytest.approx([0.0, 90.0, 180.0, 270.0])


def test_phasing_factor_offsets_adjacent_planes():
    """With T=8, P=2, F=1 the second plane is offset by F*360/T = 45 deg in
    mean anomaly."""
    # T=8, P=2, F=1 -> phase offset between planes = F * 360/T = 45 deg
    sats = generate_walker_constellation(_request(total_satellites=8, num_planes=2, phasing_factor=1), _template())
    plane0 = sorted(s.orbit.mean_anomaly_deg for s in sats if s.orbit.raan_deg == 0.0)
    plane1 = sorted(s.orbit.mean_anomaly_deg for s in sats if s.orbit.raan_deg == 180.0)
    assert plane0 == pytest.approx([0.0, 90.0, 180.0, 270.0])
    assert plane1 == pytest.approx([45.0, 135.0, 225.0, 315.0])


def test_raan_offset_rotates_whole_constellation():
    """A 30 deg RAAN offset rotates every plane by 30 deg."""
    sats = generate_walker_constellation(
        _request(total_satellites=6, num_planes=3, phasing_factor=0, raan_offset_deg=30.0), _template()
    )
    raans = sorted({s.orbit.raan_deg for s in sats})
    assert raans == pytest.approx([30.0, 150.0, 270.0])


def test_orbit_uses_mean_anomaly_not_true_anomaly():
    """Generated orbits give the mean anomaly, not the true anomaly."""
    sats = generate_walker_constellation(_request(), _template())
    for s in sats:
        assert s.orbit.anomaly_type == "mean"
        assert s.orbit.true_anomaly_deg is None
        assert s.orbit.mean_anomaly_deg is not None


def test_template_fields_other_than_name_and_orbit_are_preserved():
    """Every satellite keeps the template's other fields, with its own copy of
    the power model."""
    template = _template(dry_mass_kg=123.0, power=PowerConfig(panel_area_m2=1.5, panel_efficiency=0.3))
    sats = generate_walker_constellation(_request(total_satellites=4, num_planes=2, phasing_factor=0), template)
    for s in sats:
        assert s.dry_mass_kg == 123.0
        assert s.power == template.power
        assert s.power is not template.power  # deep-copied, not shared


def test_generated_names_are_deterministic_and_prefixed():
    """Names are prefix-plane-slot, numbered from 01."""
    sats = generate_walker_constellation(_request(total_satellites=4, num_planes=2, name_prefix="iridium"),
                                          _template())
    assert {s.name for s in sats} == {"iridium-01-01", "iridium-01-02", "iridium-02-01", "iridium-02-02"}


def test_generated_scenario_validates(tmp_path):
    """A scenario of the generated satellites validates and saves."""
    from spacemissionstudio.schema.scenario import GravityConfig, Scenario

    sats = generate_walker_constellation(_request(total_satellites=4, num_planes=2), _template())
    scenario = Scenario(name="walker test", epoch_utc="2030-01-01T00:00:00",
                         gravity=GravityConfig(central_body="earth"), spacecraft=sats)
    scenario.validate()  # must not raise
    scenario.save(tmp_path / "walker.json")  # round-trips through JSON cleanly


@pytest.mark.parametrize("overrides,match", [
    (dict(total_satellites=0), "total_satellites"),
    (dict(num_planes=0), "num_planes"),
    (dict(total_satellites=10, num_planes=3), "evenly divisible"),
    (dict(phasing_factor=3), "phasing_factor"),
    (dict(altitude_km=0.0), "altitude_km"),
    (dict(inclination_deg=200.0), "inclination_deg"),
    (dict(eccentricity=1.0), "eccentricity"),
    (dict(pattern="triangle"), "pattern"),
    (dict(central_body="pluto"), "central_body"),
    (dict(name_prefix="  "), "name_prefix"),
])
def test_request_validation_rejects_bad_input(overrides, match):
    """Each bad request field is refused, naming it: zero satellites or planes,
    satellites not divisible by planes, a phasing factor of P or more, a zero
    altitude, an inclination over 180 deg, eccentricity 1, an unknown pattern
    or body, a blank prefix."""
    with pytest.raises(ScenarioValidationError, match=match):
        _request(**overrides).validate()


# -- SeparationSchedule -----------------------------------------------------

def test_separation_schedule_rejects_empty_distances():
    """A separation schedule without distances is refused."""
    with pytest.raises(ValueError, match="at least one distance"):
        SeparationSchedule(distances_km=[], interval_days=90.0, semi_major_axis_m=7.0e6)


def test_separation_schedule_single_entry_holds_for_whole_mission():
    """A one-entry schedule gives that separation, as an angle (distance / a),
    at any time."""
    schedule = SeparationSchedule(distances_km=[100.0], interval_days=90.0, semi_major_axis_m=7.0e6)
    expected = 100.0 * 1000.0 / 7.0e6
    assert schedule.value_at(0.0) == pytest.approx(expected)
    assert schedule.value_at(1.0e9) == pytest.approx(expected)  # far beyond any interval -- still holds


def test_separation_schedule_steps_through_distances_on_schedule():
    """A three-entry schedule changes separation at each 90-day interval, not
    before."""
    a_m = 7.0e6
    schedule = SeparationSchedule(distances_km=[1000.0, 500.0, 100.0], interval_days=90.0, semi_major_axis_m=a_m)
    day_s = 86400.0

    assert schedule.value_at(0.0) == pytest.approx(1000.0 * 1000.0 / a_m)
    assert schedule.value_at(89.0 * day_s) == pytest.approx(1000.0 * 1000.0 / a_m)
    assert schedule.value_at(90.0 * day_s) == pytest.approx(500.0 * 1000.0 / a_m)
    assert schedule.value_at(179.0 * day_s) == pytest.approx(500.0 * 1000.0 / a_m)
    assert schedule.value_at(180.0 * day_s) == pytest.approx(100.0 * 1000.0 / a_m)


def test_separation_schedule_holds_at_last_entry_when_not_looping():
    """Without looping, the schedule holds its last separation after its
    end."""
    a_m = 7.0e6
    schedule = SeparationSchedule(distances_km=[1000.0, 500.0, 100.0], interval_days=90.0, semi_major_axis_m=a_m,
                                   loop=False)
    day_s = 86400.0
    far_future = 1000.0 * day_s
    assert schedule.value_at(far_future) == pytest.approx(100.0 * 1000.0 / a_m)


def test_separation_schedule_loops_when_requested():
    """With looping, the schedule starts again from its first separation after
    its last."""
    a_m = 7.0e6
    schedule = SeparationSchedule(distances_km=[1000.0, 500.0, 100.0], interval_days=90.0, semi_major_axis_m=a_m,
                                   loop=True)
    day_s = 86400.0
    # index 3 (0-based) wraps back to index 0
    assert schedule.value_at(3 * 90.0 * day_s) == pytest.approx(1000.0 * 1000.0 / a_m)
    assert schedule.value_at(4 * 90.0 * day_s) == pytest.approx(500.0 * 1000.0 / a_m)


def test_separation_schedule_zero_interval_holds_first_entry():
    """A zero interval holds the first separation for the whole mission."""
    schedule = SeparationSchedule(distances_km=[1000.0, 500.0], interval_days=0.0, semi_major_axis_m=7.0e6)
    assert schedule.value_at(0.0) == pytest.approx(1000.0 * 1000.0 / 7.0e6)
    assert schedule.value_at(1.0e9) == pytest.approx(1000.0 * 1000.0 / 7.0e6)


def test_the_generators_use_j2_only_when_the_run_models_it():
    """Audit E4: mean elements matter only with spherical-harmonics gravity
    (degree 2 or more); with a point mass, or a body without a gravity
    field, osculating and mean elements are the same."""
    assert simulated_j2("earth", 10) == CENTRAL_BODY_J2["earth"] == pytest.approx(1.082616e-3)
    assert simulated_j2("earth", 2) == CENTRAL_BODY_J2["earth"]
    assert simulated_j2("earth", 1) == simulated_j2("earth", 0) == 0.0
    assert simulated_j2("mars barycenter", 4) == pytest.approx(1.96045e-3)
    assert simulated_j2("moon", 10) == 0.0


def test_without_j2_the_pattern_is_written_as_it_is():
    """With no J2 the generator needs no Basilisk and writes the pattern's
    elements unchanged, with their mean anomaly."""
    for sc in generate_walker_constellation(_request(), _template()):
        assert sc.orbit.anomaly_type == "mean"
        assert sc.orbit.semi_major_axis_km == pytest.approx(CENTRAL_BODY_EQUATORIAL_RADIUS_KM["earth"] + 780.0)


# -- phasing-keeping wired by the generator ---------------------------------

def _station_keeping():
    from spacemissionstudio.schema.scenario import StationKeepingConfig

    return StationKeepingConfig(target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05,  # [km], [km], [N]
                                isp_s=1500.0, propellant_kg=5.0)  # [s], [kg]


def test_phasing_keeping_makes_each_planes_first_satellite_the_chief(tmp_path):
    """With phasing-keeping, each plane's first satellite is its chief (no
    phasing of its own) and slot k of the plane holds a * k * 360/S deg of
    arc ahead of it, with the law asked for; the scenario validates."""
    import math

    from spacemissionstudio.schema.scenario import GravityConfig, Scenario

    request = _request(total_satellites=8, num_planes=2, altitude_km=550.0, eccentricity=0.001,
                       phasing_keeping=True, phasing_control_law="hill_pd")
    sats = generate_walker_constellation(request, _template(station_keeping=_station_keeping()))
    a_km = CENTRAL_BODY_EQUATORIAL_RADIUS_KM["earth"] + 550.0  # [km]
    for plane in (1, 2):
        chief, *followers = [sc for sc in sats if sc.name.startswith(f"sat-{plane:02d}-")]
        assert chief.name == f"sat-{plane:02d}-01" and chief.phasing_keeping is None
        for slot, follower in enumerate(followers, start=1):
            phasing = follower.phasing_keeping
            assert phasing.chief_spacecraft == chief.name and phasing.control_law == "hill_pd"
            assert phasing.target_separation_km == [pytest.approx(a_km * slot * math.pi / 2.0, abs=1e-6)]  # [km]
            # The placed slot is that separation ahead of the chief.
            ahead_deg = (follower.orbit.mean_anomaly_deg - chief.orbit.mean_anomaly_deg) % 360.0  # [deg]
            assert ahead_deg == pytest.approx(slot * 90.0)
    scenario = Scenario(name="walker phasing", epoch_utc="2030-01-01T00:00:00",
                        gravity=GravityConfig(central_body="earth", third_body_perturbers=["sun"]), spacecraft=sats)
    scenario.validate()
    scenario.save(tmp_path / "walker.json")


def test_the_controller_targets_each_slots_own_phase():
    """The separation each follower holds is, for the phasing controller
    (SeparationSchedule's arc-length angle), exactly its slot's spacing."""
    import math

    request = _request(total_satellites=6, num_planes=1, phasing_factor=0, altitude_km=700.0, eccentricity=0.001,
                       phasing_keeping=True)
    sats = generate_walker_constellation(request, _template(station_keeping=_station_keeping()))
    a_m = (CENTRAL_BODY_EQUATORIAL_RADIUS_KM["earth"] + 700.0) * 1000.0  # [m]
    for slot, follower in enumerate(sats[1:], start=1):
        schedule = SeparationSchedule(follower.phasing_keeping.target_separation_km, 90.0, a_m)
        assert schedule.value_at(0.0) == pytest.approx(math.radians(slot * 60.0), abs=1e-9)  # [rad]


def test_phasing_keeping_keeps_the_templates_tuning():
    """The template's own phasing-keeping tuning is kept; only the chief, the
    separation and the law are the generator's."""
    from spacemissionstudio.schema.scenario import PhasingKeepingConfig

    tuned = PhasingKeepingConfig(chief_spacecraft="elsewhere", target_separation_km=[5.0], tolerance_fraction=0.2,
                                 correction_window_days=6.0)  # [km], [-], [day]
    sats = generate_walker_constellation(
        _request(total_satellites=4, num_planes=1, phasing_factor=0, eccentricity=0.001, phasing_keeping=True),
        _template(station_keeping=_station_keeping(), phasing_keeping=tuned))
    assert sats[0].phasing_keeping is None
    for follower in sats[1:]:
        assert follower.phasing_keeping.chief_spacecraft == "sat-01-01"
        assert follower.phasing_keeping.tolerance_fraction == 0.2
        assert follower.phasing_keeping.correction_window_days == 6.0
        assert follower.phasing_keeping.control_law == "drift_orbit"
    assert tuned.chief_spacecraft == "elsewhere"  # the template is not changed


@pytest.mark.parametrize("request_overrides,template_overrides,match", [
    (dict(eccentricity=0.001), dict(), "station-keeping"),
    (dict(eccentricity=0.0), dict(station_keeping=True), "eccentricity"),
    (dict(total_satellites=3, num_planes=3, phasing_factor=0, eccentricity=0.001), dict(station_keeping=True),
     "two satellites per plane"),
    (dict(eccentricity=0.001, phasing_control_law="bang_bang"), dict(station_keeping=True), "phasing_control_law"),
])
def test_phasing_keeping_is_refused_without_what_it_needs(request_overrides, template_overrides, match):
    """Phasing-keeping is refused, saying why, for a template without
    station-keeping (no thruster), an exactly circular point-mass orbit (no
    measurable phase), one satellite per plane (nothing to hold) or an
    unknown law."""
    if template_overrides.pop("station_keeping", False):
        template_overrides["station_keeping"] = _station_keeping()
    with pytest.raises(ScenarioValidationError, match=match):
        generate_walker_constellation(_request(phasing_keeping=True, **request_overrides),
                                      _template(**template_overrides))


def test_without_phasing_keeping_nothing_is_wired():
    """Without the option the generator wires no phasing (as before)."""
    sats = generate_walker_constellation(_request(), _template(station_keeping=_station_keeping()))
    assert all(sc.phasing_keeping is None for sc in sats)


@pytest.mark.requires_basilisk
def test_a_generated_plane_runs_on_its_targets():
    """A generated plane runs (point-mass Earth, 0.1 day, over one orbit):
    once the controller's one-orbit smoothing has filled, every follower's
    separation error is under 0.01 deg, and no follower fired, so the
    targets are where the slots were placed (a wrong one would be off by a
    slot, 90 deg). Before that, the raw error swings by about 2e rad (0.1
    deg at e = 0.001), true against mean anomaly."""
    import numpy as np

    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema.scenario import GravityConfig, Scenario, SimSettings

    request = _request(total_satellites=4, num_planes=1, phasing_factor=0, altitude_km=550.0, inclination_deg=53.0,
                       eccentricity=0.001, phasing_keeping=True)
    sats = generate_walker_constellation(request, _template(station_keeping=_station_keeping()))
    scenario = Scenario(name="walker phasing run", epoch_utc="2030-01-01T00:00:00",
                        gravity=GravityConfig(central_body="earth", central_body_degree=0, third_body_perturbers=["sun"]),
                        sim_settings=SimSettings(duration_days=0.1), spacecraft=sats)  # [day]
    scenario.validate()
    result = SimulationService(scenario).run()
    for follower in sats[1:]:
        error = result.series[f"{follower.name}.phasing_keeping.separation_error"].data[:, 0]  # [deg]
        assert error.shape[0] > 0 and abs(error[-1]) < 0.01  # [deg]
        assert np.all(result.series[f"{follower.name}.phasing_keeping.state"].data[:, 0] == 0)  # IDLE throughout
