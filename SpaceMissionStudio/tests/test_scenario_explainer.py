"""Tests for spacemissionstudio.engine.scenario_explainer -- no Basilisk
import, runs anywhere.
"""

from pathlib import Path

import pytest

from spacemissionstudio.engine.scenario_explainer import Badge, explain
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import (
    GravityConfig,
    OrbitIC,
    PhasingKeepingConfig,
    Scenario,
    SpacecraftConfig,
    StationKeepingConfig,
)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"
_TEMPLATE_PATHS = sorted(_TEMPLATES_DIR.glob("*.json"))

# Generous ceiling -- a cheap, permanent regression guard against this
# quietly regrowing into prose or a bullet wall later (see this module's
# own docstring: every string here must be ONE short, scannable fragment).
_MAX_STRING_LEN = 90


def _single_spacecraft_scenario(**orbit_overrides) -> Scenario:
    orbit_defaults = dict(
        type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
        inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0,
    )
    orbit_defaults.update(orbit_overrides)
    return Scenario(
        name="point-mass test",
        epoch_utc="2030-01-01T00:00:00",
        spacecraft=[SpacecraftConfig(name="sat-1", orbit=OrbitIC(**orbit_defaults))],
    )


def test_zero_spacecraft_scenario_does_not_raise():
    scenario = Scenario(name="empty", epoch_utc="2030-01-01T00:00:00", spacecraft=[])
    explanation = explain(scenario)
    assert explanation.headline == "empty"
    assert explanation.spacecraft_table == []


def test_trivial_scenario_produces_short_tiles_and_no_table():
    explanation = explain(_single_spacecraft_scenario())
    assert len(explanation.stat_tiles) >= 3
    assert explanation.spacecraft_table == []
    labels = {tile.label for tile in explanation.stat_tiles}
    assert "Spacecraft" in labels
    assert "Duration" in labels
    assert "Gravity" in labels


def test_degree_10_sun_moon_gravity_shows_up_as_a_tile():
    scenario = _single_spacecraft_scenario()
    scenario.gravity = GravityConfig(central_body="earth", central_body_degree=10,
                                      third_body_perturbers=["sun", "moon"])
    explanation = explain(scenario)
    gravity_tile = next(t for t in explanation.stat_tiles if t.label == "Gravity")
    assert "10" in gravity_tile.value
    assert gravity_tile.value == "Degree-10 Earth + Sun/Moon"  # body names capitalised


def test_sso_detection_fires_at_the_real_reference_point():
    # 97.40 deg at 6878.1366 km altitude -- the same reference value
    # engine.orbit_design.sun_synchronous_inclination_deg's own docstring
    # verifies against.
    from spacemissionstudio.schema.scenario import GravityConfig

    scenario = _single_spacecraft_scenario(semi_major_axis_km=6878.1366, inclination_deg=97.40)
    scenario.gravity = GravityConfig(central_body="earth", central_body_degree=2)
    explanation = explain(scenario)
    orbit_tile = next(t for t in explanation.stat_tiles if t.label == "Orbit")
    assert "SSO" in orbit_tile.value
    env_section = next((s for s in explanation.sections if s.title == "Environment"), None)
    assert env_section is not None
    assert any(b.label == "Sun-synchronous" for b in env_section.badges)


def test_sso_detection_does_not_fire_for_an_unrelated_inclination():
    explanation = explain(_single_spacecraft_scenario(semi_major_axis_km=6878.1366, inclination_deg=51.6))
    orbit_tile = next(t for t in explanation.stat_tiles if t.label == "Orbit")
    assert "SSO" not in orbit_tile.value
    env_section = next((s for s in explanation.sections if s.title == "Environment"), None)
    assert env_section is None or not any(b.label == "Sun-synchronous" for b in env_section.badges)


def test_template_05_shaped_chief_follower_pair_produces_spacecraft_table():
    chief = SpacecraftConfig(
        name="chief-1",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                       inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
        station_keeping=StationKeepingConfig(target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05,
                                              isp_s=1500.0, propellant_kg=5.0),
    )
    follower = SpacecraftConfig(
        name="follower-1",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                       inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0,
                       anomaly_type="mean", mean_anomaly_deg=0.413509),
        station_keeping=StationKeepingConfig(target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05,
                                              isp_s=1500.0, propellant_kg=5.0),
        phasing_keeping=PhasingKeepingConfig(chief_spacecraft="chief-1", target_separation_km=[50.0]),
    )
    scenario = Scenario(name="formation", epoch_utc="2030-01-01T00:00:00", spacecraft=[chief, follower])

    explanation = explain(scenario)
    assert len(explanation.spacecraft_table) == 2
    names = {row.name for row in explanation.spacecraft_table}
    assert names == {"chief-1", "follower-1"}

    formation_section = next(s for s in explanation.sections if s.title == "Formation / orbit maintenance")
    badge_labels = {b.label for b in formation_section.badges}
    assert "Station-keeping" in badge_labels
    assert "Phasing-keeping" in badge_labels
    assert formation_section.notes == []  # both spacecraft DO have station_keeping -- no warning note

    assert len(explanation.formation_diagrams) == 1
    diagram = explanation.formation_diagrams[0]
    assert diagram.chief_name == "chief-1"
    assert diagram.follower_name == "follower-1"
    assert diagram.target_separation_km == 50.0
    assert diagram.tolerance_fraction == 0.10
    assert diagram.restore_tolerance_fraction == 0.02


def test_formation_diagram_uses_the_first_entry_of_a_multi_step_schedule():
    chief = SpacecraftConfig(name="chief-1", orbit=OrbitIC(
        type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
        inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))
    follower = SpacecraftConfig(
        name="follower-1",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                       inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
        phasing_keeping=PhasingKeepingConfig(chief_spacecraft="chief-1", target_separation_km=[1000.0, 500.0, 100.0]),
    )
    scenario = Scenario(name="constellation", epoch_utc="2030-01-01T00:00:00", spacecraft=[chief, follower])

    explanation = explain(scenario)
    assert len(explanation.formation_diagrams) == 1
    assert explanation.formation_diagrams[0].target_separation_km == 1000.0  # the FIRST (current) step


def test_a_basilisk_formation_law_gets_its_badge_and_no_tolerance_diagram():
    """The diagram draws the drift-orbit law's trigger/restore band, which a
    Basilisk law (engine.formation_control) does not have."""
    chief = SpacecraftConfig(name="chief-1", orbit=OrbitIC(
        type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
        inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))
    follower = SpacecraftConfig(
        name="follower-1",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                       inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.4),
        phasing_keeping=PhasingKeepingConfig(chief_spacecraft="chief-1", target_separation_km=[50.0],
                                             control_law="mean_oe"),
    )
    explanation = explain(Scenario(name="f", epoch_utc="2030-01-01T00:00:00", spacecraft=[chief, follower]))
    formation_section = next(s for s in explanation.sections if s.title == "Formation / orbit maintenance")
    assert "Basilisk mean-element feedback" in {b.label for b in formation_section.badges}
    assert explanation.formation_diagrams == []


def test_no_formation_diagram_without_phasing_keeping():
    scenario = _single_spacecraft_scenario()
    explanation = explain(scenario)
    assert explanation.formation_diagrams == []


def test_phasing_keeping_without_station_keeping_surfaces_a_note():
    chief = SpacecraftConfig(name="chief-1", orbit=OrbitIC(
        type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
        inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))
    follower = SpacecraftConfig(
        name="follower-1",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                       inclination_deg=97.59, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
        phasing_keeping=PhasingKeepingConfig(chief_spacecraft="chief-1", target_separation_km=[50.0]),
    )
    scenario = Scenario(name="formation", epoch_utc="2030-01-01T00:00:00", spacecraft=[chief, follower])

    explanation = explain(scenario)
    formation_section = next(s for s in explanation.sections if s.title == "Formation / orbit maintenance")
    assert formation_section.notes  # follower-1 has phasing_keeping but no station_keeping
    assert "follower-1" in formation_section.notes[0]


@pytest.mark.parametrize("path", _TEMPLATE_PATHS, ids=lambda p: p.name)
def test_explain_does_not_raise_on_any_bundled_template(path):
    scenario = load_scenario(path)
    explanation = explain(scenario)
    assert explanation.headline  # every bundled template has a real name


@pytest.mark.parametrize("path", _TEMPLATE_PATHS, ids=lambda p: p.name)
def test_every_string_in_the_explanation_stays_short(path):
    """Permanent regression guard: this module's whole design point is
    terse, scannable fragments, not prose -- a real user explicitly
    rejected two earlier, more verbose designs before this one. Checked
    against every real bundled template, not just synthetic cases.
    """
    scenario = load_scenario(path)
    explanation = explain(scenario)
    for tile in explanation.stat_tiles:
        assert len(tile.value) <= _MAX_STRING_LEN, f"{tile.label}: {tile.value!r}"
    for section in explanation.sections:
        for badge in section.badges:
            assert len(badge.label) <= _MAX_STRING_LEN, f"{section.title}: {badge.label!r}"
        for note in section.notes:
            assert len(note) <= 220, f"{section.title} note too long: {note!r}"  # notes allow a bit more
    for row in explanation.spacecraft_table:
        for column, value in row.facts.items():
            assert len(value) <= _MAX_STRING_LEN, f"{row.name}.{column}: {value!r}"


def test_explain_never_raises_even_on_a_scenario_missing_its_own_schema_defaults():
    # A somewhat pathological but legal input -- an empty-string name and
    # no spacecraft -- exercising the try/except wrapper directly rather
    # than only via well-formed inputs.
    scenario = Scenario(name="", epoch_utc="", spacecraft=[])
    explanation = explain(scenario)
    assert isinstance(explanation.headline, str)


def test_badge_default_kind_is_neutral():
    assert Badge("x").kind == "neutral"


def _template_scenario(prefix):
    return load_scenario(next((Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios"
                               / "templates").glob(f"{prefix}_*.json")))


def test_identical_spacecraft_share_one_table_row():
    """A 6-satellite constellation used to repeat the same row six times."""
    rows = explain(_template_scenario("04")).spacecraft_table
    assert len(rows) == 1
    assert rows[0].name == "leo-01-01 ... leo-02-03 (6)"


def test_badges_use_plain_names_and_reserve_status_colours():
    """Real user feedback on clutter: Drag/SRP badges were in the warning
    colour and power/RF in the success colour, though neither is a state;
    attitude modes showed code names; stations were a count plus a list."""
    every_badge = []
    for path in sorted((Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios"
                        / "templates").glob("*.json")):
        for section in explain(load_scenario(path)).sections:
            if section.title == "Check before running":  # a real state: the one place warning colour belongs
                assert {badge.kind for badge in section.badges} == {"warning"}
            else:
                every_badge += section.badges
            for note in section.notes:
                assert "_" not in note, note  # no code names in notes either
    assert {badge.kind for badge in every_badge} <= {"accent", "neutral"}
    labels = {badge.label for badge in every_badge}
    assert not labels & {"inertial3D", "hillPoint", "velocityPoint", "sunSafePoint", "locationPointing"}
    assert "Sun pointing" in labels
    stations = next(s for s in explain(_template_scenario("19")).sections if s.title == "Ground stations")
    assert [b.label for b in stations.badges] == ["berlin-gs"]
    assert stations.notes == ["berlin-gs: 2 passes, first at 10 min for 8 min (peak 60 deg)"]


def test_sso_inclination_without_oblateness_is_not_called_sun_synchronous():
    """The precession that makes an orbit Sun-synchronous comes from J2;
    templates 01/09/10/12 use a Sun-synchronous inclination with point-mass
    gravity, where the plane never turns -- the badge would be a false claim."""
    explanation = explain(_single_spacecraft_scenario(semi_major_axis_km=6878.1366, inclination_deg=97.40))
    orbit_tile = next(t for t in explanation.stat_tiles if t.label == "Orbit")
    assert orbit_tile.value.startswith("Classical")
    env_section = next((s for s in explanation.sections if s.title == "Environment"), None)
    assert env_section is None or not any(b.label == "Sun-synchronous" for b in env_section.badges)


def test_checks_section_comes_first_and_flags_a_late_first_pass():
    """Template 19 used to start at midnight UTC: its first Berlin pass came
    8.2 h into a 12 h run, so users saw "never" any contact. The Explain tab
    now says so before the run."""
    scenario = _template_scenario("19")
    scenario.epoch_utc = "2030-01-01T00:00:00"
    scenario.sim_settings.duration_days = 0.5
    sections = explain(scenario).sections
    assert sections[0].title == "Check before running"
    assert sections[0].notes == ["berlin-gs: the first pass only comes at 8.2 h of a 12.0 h run"]
    assert all(s.title != "Check before running" for s in explain(_template_scenario("19")).sections)


def test_duration_tile_uses_a_readable_unit():
    """Template 19's 2 h 15 min run showed as "0.09375 d"."""
    from spacemissionstudio.engine.scenario_explainer import _duration_label

    assert [_duration_label(d) for d in (0.01, 0.09375, 0.5, 14.0)] == ["14.4 min", "2.25 h", "12 h", "14 d"]
    tile = next(t for t in explain(_template_scenario("19")).stat_tiles if t.label == "Duration")
    assert tile.value == "2.25 h"


def test_the_altitude_is_above_the_scenarios_own_central_body():
    """Audit L21: the orbit tile subtracted Earth's radius around any body;
    a 1837.4 km orbit around the Moon is 100 km up, not -4541 km."""
    from spacemissionstudio.engine.scenario_explainer import explain
    from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SpacecraftConfig

    scenario = Scenario(name="moon", epoch_utc="2030-01-01T00:00:00", gravity=GravityConfig(central_body="moon"),
                        spacecraft=[SpacecraftConfig(name="lunar", orbit=OrbitIC(
                            type="classical_elements", semi_major_axis_km=1837.4, eccentricity=0.0,
                            inclination_deg=90.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))])
    orbit_tile = next(tile for tile in explain(scenario).stat_tiles if tile.label == "Orbit")
    assert "100 km alt" in orbit_tile.value


def test_a_failing_section_leaves_the_rest_of_the_tab(monkeypatch, caplog):
    """Audit L21: one section raising blanked the whole Explain tab, with
    nothing logged; now only that section is left out, and it is logged."""
    import logging

    from spacemissionstudio.engine import scenario_explainer
    def broken(scenario):
        raise ValueError("half-edited")

    monkeypatch.setattr(scenario_explainer, "_environment_section", broken)
    scenario = load_scenario(next(_TEMPLATES_DIR.glob("18_*.json")))
    with caplog.at_level(logging.DEBUG, logger="spacemissionstudio.engine.scenario_explainer"):
        explanation = scenario_explainer.explain(scenario)
    assert explanation.stat_tiles and explanation.sections
    assert "Explain tab: broken failed" in caplog.text and "half-edited" in caplog.text


def _roe_scenario(control_law="impulsive"):
    """Template 05 with its follower in an ROE formation: 2 km behind,
    then a 300 m passively safe helix from day 1."""
    from spacemissionstudio.schema import RoeFormationConfig, RoeTargetConfig

    scenario = _template_scenario("05")
    follower = next(sc for sc in scenario.spacecraft if sc.phasing_keeping is not None)
    chief = follower.phasing_keeping.chief_spacecraft
    follower.phasing_keeping = None
    follower.roe_formation = RoeFormationConfig(
        chief_spacecraft=chief, control_law=control_law,
        targets=[RoeTargetConfig(0.0, [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]),  # [m]
                 RoeTargetConfig(1.0, [0.0, 0.0, 0.0, 300.0, 0.0, 300.0])])  # [m]
    return scenario, follower


@pytest.mark.parametrize("law, badge", [("impulsive", "ROE formation (impulsive)"),
                                        ("continuous", "ROE formation (Basilisk mean-element feedback)")])
def test_an_roe_formation_is_explained(law, badge):
    """The formation section names the ROE law, says each target in words
    (with its closest radial/cross-track approach), and carries one
    e/i-vector diagram with every target."""
    scenario, follower = _roe_scenario(law)
    explanation = explain(scenario)
    section = next(s for s in explanation.sections if s.title == "Formation / orbit maintenance")
    assert badge in [b.label for b in section.badges]
    notes = [n for n in section.notes if n.startswith(follower.name)]
    assert len(notes) == 2
    assert "2000 m behind" in notes[0] and "not passively safe" in notes[0]
    assert "closest radial/cross-track approach 300 m" in notes[1]
    assert all(len(note) <= 220 for note in notes)
    assert explanation.formation_diagrams == []  # no phasing keeping left
    [diagram] = explanation.roe_diagrams
    assert diagram.follower_name == follower.name
    assert diagram.chief_name == follower.roe_formation.chief_spacecraft
    assert diagram.targets == [(0.0, [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]), (1.0, [0.0, 0.0, 0.0, 300.0, 0.0, 300.0])]


@pytest.mark.parametrize("law, compensate, words", [
    ("impulsive", True, "measures the decay it causes and compensates it"),
    ("impulsive", False, "'Compensate differential drag' is off"),
    ("continuous", True, "continuous law's feedback corrects it"),
])
def test_differential_drag_is_explained(law, compensate, words):
    """A follower with three times the chief's drag area is told to feel
    differential drag, with what its law does about it; the twins of
    template 05 are not."""
    scenario, follower = _roe_scenario(law)
    section = next(s for s in explain(scenario).sections if s.title == "Formation / orbit maintenance")
    assert not any("differential drag" in n for n in section.notes)
    follower.drag_area_m2 *= 3.0
    follower.roe_formation.differential_drag = compensate
    section = next(s for s in explain(scenario).sections if s.title == "Formation / orbit maintenance")
    [note] = [n for n in section.notes if "differential drag" in n]
    assert note.startswith(f"{follower.name}: drag coefficient x area / dry mass 0.0225 m^2/kg against ")
    assert "0.0075: differential drag" in note and words in note
    assert len(note) <= 220


def test_no_roe_diagram_without_an_roe_formation():
    """A scenario without an ROE formation has no ROE diagram."""
    assert explain(_template_scenario("05")).roe_diagrams == []


def _opnav_scenario(template="01", **camera):
    from spacemissionstudio.schema import GravityConfig, OpticalNavigationConfig

    scenario = _template_scenario(template)
    scenario.gravity = GravityConfig(central_body="mars barycenter", third_body_perturbers=["sun"])
    sc = scenario.spacecraft[0]
    sc.orbit.type = "classical_elements"
    sc.orbit.semi_major_axis_km = 18000.0  # [km]
    sc.orbit.eccentricity = 0.2  # [-]
    sc.optical_navigation = OpticalNavigationConfig(**camera)
    return scenario, sc


def test_optical_navigation_is_explained():
    """The section names the camera and the disk's size at periapsis and
    apoapsis (Mars, 40 deg over 512 px, 14 400 and 21 600 km: radius
    tan(asin(R / r)) / X, 341 and 224 px across), and says an
    orbit-only camera points perfectly."""
    scenario, sc = _opnav_scenario()
    section = next(s for s in explain(scenario).sections if s.title == "Optical navigation")
    assert any("40 deg camera, 512 x 512 px" in n for n in section.notes)
    sizes = next(n for n in section.notes if "px across" in n)
    assert "341 px across at periapsis" in sizes and "224 px across at apoapsis" in sizes
    assert any("points at the body perfectly" in n for n in section.notes)
    assert not [b for b in section.badges if b.kind == "warning"]


def test_optical_navigation_warns_about_disk_size_and_pointing():
    """A narrow camera sees the disk larger than the image at periapsis, a
    coarse one too small at apoapsis; with attitude, a camera not pointed
    at the central body, or along another axis than locationPointing's,
    is flagged."""
    scenario, _ = _opnav_scenario(field_of_view_deg=10.0)
    section = next(s for s in explain(scenario).sections if s.title == "Optical navigation")
    assert any("larger than the image" in b.label for b in section.badges)
    scenario, _ = _opnav_scenario(resolution_px=[16, 16], min_radius_px=10.0)
    section = next(s for s in explain(scenario).sections if s.title == "Optical navigation")
    assert any("smaller than the usable size" in b.label for b in section.badges)
    scenario, sc = _opnav_scenario(template="15")
    sc.fsw_params = {"target_body": "moon", "pHat_B": [0.0, 0.0, 1.0]}
    section = next(s for s in explain(scenario).sections if s.title == "Optical navigation")
    assert any("not pointed at the central body" in b.label for b in section.badges)
    sc.fsw_params = {"target_body": "mars barycenter", "pHat_B": [1.0, 0.0, 0.0]}
    section = next(s for s in explain(scenario).sections if s.title == "Optical navigation")
    assert any("is not the camera's boresight" in b.label for b in section.badges)
    sc.fsw_params = {"target_body": "mars barycenter", "pHat_B": [0.0, 0.0, 1.0]}
    section = next(s for s in explain(scenario).sections if s.title == "Optical navigation")
    assert not [b for b in section.badges if b.kind == "warning"]


def _eros_scenario():
    from spacemissionstudio.schema.scenario import LandmarkNavigationConfig

    scenario = _template_scenario("01")
    scenario.gravity.central_body = "eros"
    scenario.gravity.polyhedral_gravity = True
    scenario.gravity.third_body_perturbers = ["sun"]
    scenario.spacecraft[0].orbit.semi_major_axis_km = 35.0  # [km]
    scenario.spacecraft[0].landmark_navigation = LandmarkNavigationConfig()
    return scenario


def test_the_small_body_section_gives_spin_orbit_and_pixel_size():
    """Around Eros: the gravity model, its 5.27 h spin, the orbit's period
    in turns of Eros, and the landmark camera's 13.9 m per pixel at the
    lowest point (30 deg over 1024 px from 35 km, above Eros's 8.42 km mean
    radius); the tiles give the distance from the centre and the shape model."""
    explanation = explain(_eros_scenario())
    section = next(s for s in explanation.sections if s.title == "Small body")
    assert [b.label for b in section.badges] == ["433 Eros: shape model (Basilisk polyhedralGravityModel)"]
    notes = " ".join(section.notes)
    assert "every 5.27 h" in notes and "17.1 h, 3.2 turns" in notes and "13.9 m on the surface per pixel" in notes
    tiles = {tile.label: tile.value for tile in explanation.stat_tiles}
    assert tiles["Orbit"].endswith("35 km from the centre") and tiles["Gravity"] == "Eros shape model + Sun"


def test_a_point_mass_eros_or_an_unpointed_camera_is_flagged():
    """Point-mass gravity around Eros, and a camera with attitude but no
    pointing at Eros, each get a warning badge."""
    scenario = _eros_scenario()
    scenario.gravity.polyhedral_gravity = False
    scenario.spacecraft[0].landmark_navigation = None
    labels = [b.label for s in explain(scenario).sections if s.title == "Small body" for b in s.badges]
    assert any("Point-mass gravity" in label for label in labels)
    scenario = _eros_scenario()
    scenario.simulation_mode = "full_attitude"
    labels = [b.label for s in explain(scenario).sections if s.title == "Small body" for b in s.badges]
    assert any("not pointed at 433 Eros" in label for label in labels)


def test_missing_eros_files_are_checked_before_running():
    """Without the Eros ephemeris and shape the run would stop at once:
    'Check before running' says so."""
    from spacemissionstudio.engine import small_bodies
    from spacemissionstudio.engine.scenario_checks import scenario_warnings

    warnings = scenario_warnings(_eros_scenario())
    assert any("ephemeris of 433 Eros is not installed" in w for w in warnings)
    try:
        shape_missing = small_bodies.shape_path(small_bodies.EROS) is None
    except ImportError:
        shape_missing = False
    assert any("shape model of 433 Eros" in w for w in warnings) == shape_missing
