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
"""The parameter registry and project configuration files
(spacemissionstudio.config, transparency audit Phase 3a, 3b): every
parameter is declared with its unit and source, the shipped defaults file
is the registry's, a project file is checked against it, and setting each
parameter changes what it says it changes."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from spacemissionstudio.config import files, registry
from spacemissionstudio.config.registry import ConfigError, Configuration
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import (GravityConfig, OrbitIC, PropellantBudgetConfig, Scenario,
                                                ScenarioValidationError, SpacecraftConfig, StationKeepingConfig)


def test_every_parameter_is_declared_with_what_a_reader_needs():
    """A name ``<area>.<parameter>``, a unit, what it controls, a source,
    and a default it may take itself."""
    declared = registry.parameters()
    assert declared and len({p.name for p in declared}) == len(declared)
    for parameter in declared:
        assert parameter.area and "." in parameter.name, parameter.name
        assert parameter.unit.startswith("[") and parameter.controls and parameter.source, parameter.name
        assert parameter.check(parameter.default) == pytest.approx(parameter.default), parameter.name


def test_the_shipped_defaults_file_is_the_registry():
    """config/defaults.yaml is generated from the registry
    (scripts/build_config_defaults.py) and lists every parameter, commented
    out: as a project file, it changes nothing."""
    text = files.DEFAULTS_FILE.read_text(encoding="utf-8")
    assert text == files.defaults_yaml(), "run scripts/build_config_defaults.py"
    for parameter in registry.parameters():
        assert f"# {parameter.name}: " in text
    assert files.read(files.DEFAULTS_FILE).overrides == {}


# The page of docs/models that documents each area (the brief: every model, rule and assumption).
_MODEL_PAGES = {"propellant_budget": "propellant-budget.md", "lifetime": "lifetime.md",
                "link": "link-data-and-power.md", "data_handling": "link-data-and-power.md",
                "results": "reading-results.md", "dynamics": "dynamics-run-control.md",
                "space_weather": "environment-and-data.md", "tle": "environment-and-data.md",
                "orbit_control": "orbit-control.md", "geo_station_keeping": "orbit-control.md",
                "roe_formation": "roe-formation.md"}


def test_every_parameter_is_documented_on_its_models_page():
    """Each area has its page in docs/models, linked from the index, and the
    page names each of its parameters."""
    from pathlib import Path

    models = Path(__file__).resolve().parent.parent / "docs" / "models"
    index = (models / "README.md").read_text(encoding="utf-8")
    assert {p.area for p in registry.parameters()} == set(_MODEL_PAGES)
    for area, page in _MODEL_PAGES.items():
        assert f"({page})" in index, page
        assert f"`{area}.*`" in index, area
        text = (models / page).read_text(encoding="utf-8")
        for parameter in registry.parameters(area):
            assert f"`{parameter.name.split('.', 1)[1]}`" in text, parameter.name


def _project(tmp_path, body: str):
    path = tmp_path / "project.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_project_file_is_read_and_checked_against_the_registry(tmp_path):
    """Values are checked against their parameter's kind and limits; a
    name, a key or a value the registry does not know is refused, naming
    the file and the parameter."""
    good = files.read(_project(tmp_path, "format: 1\nparameters:\n  propellant_budget.cam_count_factor: 3\n"
                                         "  propellant_budget.launch_delays_years: [0, 2]\n"))
    assert good.overrides == {"propellant_budget.cam_count_factor": 3.0,
                              "propellant_budget.launch_delays_years": (0.0, 2.0)}
    assert good.file["path"].endswith("project.yaml") and len(good.file["sha256"]) == 64
    for body, message in (("parameters:\n  propellant_budget.nope: 1\n", "unknown parameter 'propellant_budget.nope'"),
                          ("parameters:\n  propellant_budget.residual_fraction: 0.9\n", "at most 0.5"),
                          ("parameters:\n  propellant_budget.max_iterations: 2.5\n", "a whole number"),
                          ("parameters:\n  propellant_budget.eol_drag_coeff: high\n", "a finite number"),
                          ("parameter:\n  x: 1\n", "unknown key(s) parameter"),
                          ("format: 2\n", "format 2"),
                          ("parameters: [1, 2\n", "not valid YAML")):
        with pytest.raises(ConfigError, match="project.yaml") as caught:
            files.read(_project(tmp_path, body))
        assert message in str(caught.value), body


def test_a_scenario_reads_the_configuration_it_names_and_no_other(tmp_path):
    """``config_file`` is read relative to the scenario's folder when it is
    loaded; one that cannot be used makes the scenario invalid, naming the
    problem; a file beside a scenario that does not name it is not read.
    The configuration is never saved, and does not change the scenario's
    hash."""
    from spacemissionstudio import output_provenance

    path = tmp_path / "s.json"
    scenario = Scenario(name="s", epoch_utc="2030-01-01T00:00:00", spacecraft=[SpacecraftConfig(
        name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]))])
    _project(tmp_path, "parameters:\n  propellant_budget.cam_count_factor: 3\n")
    scenario.save(path)
    assert load_scenario(path).configuration is None  # beside it, not named: not read
    scenario.config_file = "project.yaml"
    scenario.save(path)
    loaded = load_scenario(path)
    assert loaded.configuration.overrides == {"propellant_budget.cam_count_factor": 3.0}
    assert registry.value("propellant_budget.cam_count_factor", loaded) == 3.0
    assert "configuration" not in path.read_text(encoding="utf-8")
    plain = load_scenario(path)
    plain.configuration = None
    assert output_provenance.scenario_sha256(plain) == output_provenance.scenario_sha256(loaded)
    _project(tmp_path, "parameters:\n  propellant_budget.cam_count_factor: 0\n")
    with pytest.raises(ScenarioValidationError, match="scenario.config_file: .*at least 1"):
        load_scenario(path)
    scenario.config_file = "missing.yaml"
    scenario.save(path)
    with pytest.raises(ScenarioValidationError, match="missing.yaml: could not be read"):
        load_scenario(path)
    unsaved = Scenario.from_dict(scenario.to_dict())
    files.attach(unsaved, None)
    assert "save the scenario first" in unsaved.configuration.error


# -- every budget parameter changes what it says it changes -----------------------------------

def _budget_scenario(**budget):
    spacecraft = SpacecraftConfig(
        name="sat-1", dry_mass_kg=120.0, enable_drag=True, srp_coeff=1.3, srp_area_m2=2.0,
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6778.1366, eccentricity=0.0,
                      inclination_deg=97.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
        station_keeping=StationKeepingConfig(target_altitude_km=400.0, deadband_km=1.0, thrust_n=0.05, isp_s=1500.0,
                                             propellant_kg=5.0),
        propellant_budget=PropellantBudgetConfig(**budget))
    return Scenario(name="b", epoch_utc="2030-01-01T00:00:00", spacecraft=[spacecraft],
                    gravity=GravityConfig(central_body="earth"))


def _no_reentry(*_args):
    return 0.0, 400.0, 0.5, []


def _makeup(*_args, **_kwargs):
    return SimpleNamespace(delta_v_m_s=100.0, altitude_km=400.0, warnings=[])


def _budget(scenario, **kwargs):
    from spacemissionstudio.engine import propellant_budget as pb

    kwargs.setdefault("reentry_solver", _no_reentry)
    kwargs.setdefault("makeup", _makeup)
    return pb.compute_budget(scenario, "sat-1", **kwargs)


def _row(budget, contributor):
    return next(r for r in budget.rows if r.contributor.startswith(contributor))


def _cam(scenario):
    row = _row(_budget(scenario), "Collision avoidance")
    return row.delta_v_m_s, row.margin


def _reentry_inputs(scenario, monkeypatch):
    """The Cd and percentile the disposal solver passes to the decay."""
    from spacemissionstudio.engine import lifetime as lt
    from spacemissionstudio.engine import propellant_budget as pb

    seen = {}

    def density(_scenario, _start, years, forecast_percentile=50.0):
        seen["percentile"] = forecast_percentile
        return SimpleNamespace(data_files={}), years, []

    def decay(_orbit, _start, ballistic, _density, _horizon, *_args, **_kwargs):
        seen["ballistic"] = ballistic
        return SimpleNamespace(reentered=True, lifetime_years=1.0)

    monkeypatch.setattr(lt, "density_for_scenario", density)
    monkeypatch.setattr(lt, "propagate_decay", decay)
    pb.uncontrolled_reentry_delta_v(scenario, scenario.spacecraft[0], datetime(2035, 1, 1), 125.0, 5.0)
    return seen


def _sweep_years(scenario):
    from spacemissionstudio.engine import propellant_budget as pb

    sweep = pb.launch_delay_sweep(scenario, "sat-1", reentry_solver=_no_reentry, makeup=_makeup)
    return [case.delay_years for case in sweep.cases]


def _scaled_source(scenario):
    from spacemissionstudio.engine import propellant_budget as pb

    flown = pb.RunContributors(run_days=1500.0, scale=1.1, in_plane=(50.0, 1.0))
    return _row(_budget(scenario, flown=flown), "In-plane").source


def _altitudes(scenario):
    from spacemissionstudio.engine import propellant_budget as pb

    return pb.default_altitudes_km(260.0, scenario)


# name: (value to set, budget inputs the case needs, what to measure)
_CASES = {
    "propellant_budget.cam_count_factor": (3.0, {"collision_avoidance_count": 2.0}, _cam),
    "propellant_budget.cam_sma_change_m": (50.0, {"collision_avoidance_count": 2.0}, _cam),
    "propellant_budget.attitude_propellant_factor": (
        3.0, {"attitude_thruster_propellant_kg": 1.0},
        lambda s: (_row(_budget(s), "Attitude").propellant_kg, _row(_budget(s), "Attitude").margin)),
    "propellant_budget.controlled_last_burn_margin": (
        0.3, {"disposal": "controlled_reentry", "controlled_reentry_delta_v_m_s": 50.0,
              "controlled_reentry_last_burn_m_s": 20.0},
        lambda s: (_row(_budget(s), "Controlled").delta_v_m_s, _row(_budget(s), "Controlled").margin)),
    "propellant_budget.residual_fraction": (0.05, {}, lambda s: (_row(_budget(s), "Residual").propellant_kg,
                                                                  _row(_budget(s), "Residual").margin)),
    "propellant_budget.uncertainty_fraction": (0.05, {}, lambda s: _row(_budget(s), "Loading").propellant_kg),
    "propellant_budget.eol_drag_coeff": (3.0, {}, None),  # measured with the disposal solver below
    "propellant_budget.eol_percentile": (95.0, {}, None),
    "propellant_budget.operations_drag_coeff": (2.2, {}, lambda s: [n for n in _budget(s).notes if "Cd" in n]),
    "propellant_budget.operations_percentile": (50.0, {}, lambda s: [n for n in _budget(s).notes if "MSFC" in n]),
    "propellant_budget.geo_graveyard_base_m": (300e3, {"disposal": "graveyard"},
                                               lambda s: _row(_budget(s), "Graveyard").delta_v_m_s),
    "propellant_budget.geo_graveyard_per_cr_a_m": (2000e3, {"disposal": "graveyard"},
                                                   lambda s: _row(_budget(s), "Graveyard").delta_v_m_s),
    "propellant_budget.convergence_kg": (10.0, {"tank_capacity_kg": 0.0}, lambda s: _budget(s).iterations),
    "propellant_budget.max_iterations": (1, {}, lambda s: _budget(s).notes[-1]),
    "propellant_budget.launch_delays_years": ((0.0, 2.0), {"mission_years": 1.0}, _sweep_years),
    "propellant_budget.scaled_run_ratio": (1.2, {}, _scaled_source),
    "propellant_budget.altitude_step_km": (25.0, {}, _altitudes),
    "propellant_budget.altitude_floor_km": (300.0, {}, _altitudes),
}


# -- every lifetime parameter changes what it says it changes ----------------------------------

def _lifetime_scenario():
    return _budget_scenario()  # a LEO station keeper at 400 km with drag


def _flat_density(seen=None):
    """A density model of a fixed 1e-11 kg/m^3, noting the ring sizes it sees."""
    import numpy as np

    def density(_t_s, r_m):
        if seen is not None:
            seen.add(len(r_m))
        return np.full(len(r_m), 1e-11)  # [kg/m^3]
    return density


def _decay(scenario):
    from spacemissionstudio.engine import lifetime as lt

    seen = set()
    orbit = lt.MeanOrbit(lt.REQ_EARTH_M + 300e3, 0.001, 1.7, 0.0, 0.0)
    result = lt.propagate_decay(orbit, datetime(2030, 1, 1), 0.02, _flat_density(seen), 1.0, scenario=scenario)
    return round(result.lifetime_s), len(result.time_s), sorted(seen)


def _makeup_samples(scenario, monkeypatch):
    from spacemissionstudio.engine import lifetime as lt

    monkeypatch.setattr(lt, "density_for_scenario", lambda _s, _start, years, **_k: (_flat_density(), years, []))
    return len(lt.drag_makeup(scenario, scenario.spacecraft[0], datetime(2030, 1, 1), 0.1).time_s)


def _cli_lifetime(scenario, monkeypatch, tmp_path):
    """The options ``lifetime`` passes the estimate when none are given."""
    from spacemissionstudio import cli
    from spacemissionstudio.engine import lifetime as lt

    seen = {}

    def end_of_life(_scenario, _name, **kwargs):
        seen.update(kwargs)
        raise lt.LifetimeError("stopped here")

    monkeypatch.setattr(lt, "end_of_life", end_of_life)
    overrides = scenario.configuration.overrides if scenario.configuration is not None else {}
    (tmp_path / "project.yaml").write_text("parameters:\n" + "".join(f"  {k}: {v}\n" for k, v in overrides.items()),
                                           encoding="utf-8")
    saved = Scenario.from_dict(scenario.to_dict())
    saved.config_file = "project.yaml"
    saved.gravity.third_body_perturbers = ["sun"]  # a station keeper needs the Sun to validate
    path = tmp_path / "s.json"
    saved.save(path)
    assert cli.main(["lifetime", str(path)]) == 3
    return seen["max_years"], seen["forecast_percentile"], seen["drag_coeff"]


def _rules(scenario):
    from spacemissionstudio.engine import lifetime as lt

    result = lt.LifetimeResult(True, 10.0 * 365.25 * 86400.0, None, None, None, datetime(2030, 1, 1))
    return [(label, result.meets(years)) for years, label, _key in lt.disposal_rules(scenario)]


# name: (value to set, what to measure: called with the scenario, monkeypatch and tmp_path)
_LIFETIME_CASES = {
    "lifetime.reentry_altitude_km": (200.0, lambda s, _m, _t: _decay(s)),
    "lifetime.ring_points": (8, lambda s, _m, _t: _decay(s)),
    "lifetime.max_step_s": (43200.0, lambda s, _m, _t: _decay(s)),
    "lifetime.max_perigee_drop_fraction": (0.001, lambda s, _m, _t: _decay(s)),
    "lifetime.zero_debris_years": (12.0, lambda s, _m, _t: _rules(s)),
    "lifetime.iadc_years": (8.0, lambda s, _m, _t: _rules(s)),
    "lifetime.makeup_step_s": (43200.0, lambda s, m, _t: _makeup_samples(s, m)),
    "lifetime.default_drag_coeff": (3.0, _cli_lifetime),
    "lifetime.default_forecast_percentile": (95.0, _cli_lifetime),
    "lifetime.default_horizon_years": (10.0, _cli_lifetime),
}
# Set where they act, in the GUI: {parameter: "file under tests/gui::test"}
_GUI_CASES = {
    "lifetime.default_deorbit_perigee_km": "test_lifetime_widget.py::test_the_pages_defaults_are_the_configurations",
    "results.pointing_converged_deg":
        "test_mission_dashboard_widget.py::test_the_tracking_badge_uses_the_projects_converged_angle",
    "results.battery_critical_fraction":
        "test_results_overview.py::test_the_battery_card_uses_the_runs_critical_fraction",
}


# -- every link and data-handling parameter changes what it says it changes -------------------

def _downlink(configuration):
    """A half-day run of tests/test_data_handling.py's fast downlink: the
    samples the link closed in, and the bits downlinked."""
    from test_data_handling import _orbit_only_downlink

    from spacemissionstudio.engine.service import SimulationService

    scenario = _orbit_only_downlink(days=0.5)
    scenario.configuration = configuration
    result = SimulationService(scenario).run()
    return (int(result.series["berlin-gs.access_to_sat.link_closed"].data[:, 0].sum()),
            float(result.series["sat.data_handling.data_downlinked"].data[-1, 0]))


def _pointing_loss(configuration, off_boresight_deg):
    from spacemissionstudio.engine import link_budget
    from spacemissionstudio.schema.scenario import RFLinkConfig

    rf_link = RFLinkConfig(15.0, 8.2e9, 1.0e6, antenna_beamwidth_deg=10.0)  # [W], [Hz], [bit/s], [deg]
    return link_budget.pointing_loss_db(rf_link, off_boresight_deg, SimpleNamespace(configuration=configuration))


def _pass_note(configuration):
    from test_data_handling import _scenario

    from spacemissionstudio.engine.scenario_explainer import explain

    scenario = _scenario()
    scenario.configuration = configuration
    return next(s for s in explain(scenario).sections if s.title == "Data handling").notes


# name: (value to set, what to measure: called with the scenario's configuration, None for the defaults)
_LINK_CASES = {
    "link.required_margin_db": (12.0, _downlink),
    "link.pointing_loss_coeff_db": (6.0, lambda c: _pointing_loss(c, 4.0)),  # [deg] within the clamp
    "link.max_pointing_loss_db": (50.0, lambda c: _pointing_loss(c, 30.0)),  # [deg] clamped: 108 dB unclamped
    "data_handling.packet_size_bits": (1.0e8, _downlink),
    "data_handling.explainer_pass_minutes": (5.0, _pass_note),
}


def test_every_parameter_has_a_case_that_sets_it():
    """A parameter declared without a case below fails here: the
    definition of done asks that a test set each one (transparency audit
    9.4). A GUI default's case is a named test of its page."""
    from pathlib import Path

    declared = {p.name for p in registry.parameters()}
    cases = (set(_CASES) | set(_LIFETIME_CASES) | set(_LINK_CASES) | set(_RESULTS_CASES) | set(_DYNAMICS_CASES)
             | set(_ENVIRONMENT_CASES) | set(_CONTROL_CASES) | set(_ROE_CASES) | set(_GUI_CASES))
    assert declared == cases, f"no case for {sorted(declared - cases)}"
    for where in _GUI_CASES.values():
        file, name = where.split("::")
        assert f"def {name}(" in (Path(__file__).resolve().parent / "gui" / file).read_text(encoding="utf-8"), where


def test_the_percentile_choices_are_msfcs():
    """A percentile parameter takes only the percentiles MSFC publishes,
    the ones a forecast can be resolved at; any other is refused when the
    file is read, not when a run needs it."""
    from spacemissionstudio.config import parameters
    from spacemissionstudio.engine import spaceweather

    assert parameters._MSFC_PERCENTILES == spaceweather.MSFC_PERCENTILES
    for name in ("propellant_budget.operations_percentile", "propellant_budget.eol_percentile",
                 "lifetime.default_forecast_percentile"):
        assert registry.parameter(name).check(95) == 95.0
        with pytest.raises(ConfigError, match="one of 95, 50, 5"):
            registry.parameter(name).check(60.0)


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("name", sorted(_LIFETIME_CASES))
def test_setting_a_lifetime_parameter_changes_what_it_controls(name, monkeypatch, tmp_path):
    """Each lifetime parameter set in a project configuration changes the
    output it says it controls."""
    value, measure = _LIFETIME_CASES[name]
    default_scenario, changed = _lifetime_scenario(), _lifetime_scenario()
    changed.configuration = Configuration({name: registry.parameter(name).check(value)})
    (tmp_path / "default").mkdir()
    (tmp_path / "changed").mkdir()
    before = measure(default_scenario, monkeypatch, tmp_path / "default")
    after = measure(changed, monkeypatch, tmp_path / "changed")
    assert before != after, name


# -- every results parameter changes what it says it changes ----------------------------------

def _run_with(configuration):
    """tests/test_run_summary.py's run, with a provenance recording
    ``configuration`` as a run's does."""
    from test_run_summary import _run

    result = _run()
    result.provenance = SimpleNamespace(configuration=registry.record(SimpleNamespace(configuration=configuration)),
                                        central_body_mu_m3_s2=0.0, frames={})
    return result


def _sma_change(configuration):
    from spacemissionstudio.engine import run_summary

    return run_summary.by_key(run_summary.summarize(_run_with(configuration)))["sat.mean_sma_change"].value


def _eclipse_labels(configuration):
    from spacemissionstudio.engine import events

    result = _run_with(configuration)
    sunlight = result.series["sat.eclipse.illumination_factor"].data[:, 0]
    sunlight[30:65] = 0.3  # [-] a partial eclipse: 30 % of the sunlight at its deepest
    return [e.label for e in events.extract_events(result) if e.kind == events.ECLIPSE]


# name: (value to set, what to measure: called with the run's configuration, None for the defaults)
_RESULTS_CASES = {
    "results.sma_window_orbits": (0.5, _sma_change),
    "results.umbra_sunlight_fraction": (0.5, _eclipse_labels),
}


@pytest.mark.parametrize("name", sorted(_RESULTS_CASES))
def test_setting_a_results_parameter_changes_how_a_run_is_read(name):
    """Each results parameter a run's configuration set changes what is
    read from the run -- the mean semi-major axis change, the eclipse's
    kind -- and set to its default, leaves it as it was."""
    value, measure = _RESULTS_CASES[name]
    before = measure(None)
    assert measure(Configuration({name: registry.parameter(name).check(value)})) != before, name
    assert measure(Configuration({name: registry.default(name)})) == before, name


# -- every dynamics parameter changes what it says it changes ---------------------------------

def _orbit_run(configuration, drag=True, altitude_km=400.0, **settings):
    """Half a day of a circular orbit (400 km), orbit only, 60 s steps: the
    chunks the run executes in (its re-entry checks), its last position [m]
    and its warnings."""
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema.scenario import SimSettings, SpaceWeatherConfig

    spacecraft = SpacecraftConfig(name="s", enable_drag=drag, orbit=OrbitIC(
        type="classical_elements", semi_major_axis_km=6378.1366 + altitude_km, eccentricity=0.0,  # [km]
        inclination_deg=51.6,  # [deg]
        raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))
    scenario = Scenario(name="d", epoch_utc="2030-01-01T00:00:00", simulation_mode="orbit_only",
                        spacecraft=[spacecraft], gravity=GravityConfig(central_body="earth"),
                        space_weather=SpaceWeatherConfig(atmosphere_model="exponential"),
                        sim_settings=SimSettings(duration_days=0.5, dynamics_task_rate_s=60.0,  # [day], [s]
                                                 integrator="rkf45", **settings))
    scenario.validate()
    scenario.configuration = configuration
    service = SimulationService(scenario)
    service.build()
    stops = []
    configure = service.scSim.ConfigureStopTime
    service.scSim.ConfigureStopTime = lambda stop_ns: (stops.append(stop_ns), configure(stop_ns))[1]
    result = service.run()
    position = result.series["s.position_N"].data  # [m] none when the run stopped at its start
    return len(stops), tuple(position[-1].round(3)) if len(position) else None, result.warnings


def _with(configuration, **base):
    """``configuration`` over ``base`` ({name: value})."""
    return Configuration({**base, **(configuration.overrides if configuration is not None else {})})


_NEAR = {"dynamics.reentry_near_perigee_km": 500.0}  # [km] above the 400 km orbit: every check is a near one

# name: (value to set, what to measure: called with the scenario's configuration, None for the defaults)
_DYNAMICS_CASES = {
    "dynamics.integrator_relative_tolerance": (1e-4, lambda c: _orbit_run(c)[1]),
    "dynamics.integrator_absolute_tolerance": (1e-2, lambda c: _orbit_run(c)[1]),
    "dynamics.reentry_check_s": (3600.0, lambda c: _orbit_run(c)[0]),
    "dynamics.reentry_altitude_km": (290.0, lambda c: [w for w in _orbit_run(c, altitude_km=280.0)[2]
                                                       if "re-entered" in w]),
    "dynamics.reentry_near_perigee_km": (500.0, lambda c: _orbit_run(c)[0]),
    "dynamics.reentry_near_check_s": (600.0, lambda c: _orbit_run(_with(c, **_NEAR))[0]),
    "dynamics.conservation_tolerance": (1e-12, lambda c: [w for w in _orbit_run(c, drag=False)[2] if "drifted" in w]),
}


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("name", sorted(_DYNAMICS_CASES))
def test_setting_a_dynamics_parameter_changes_what_it_controls(name):
    """Each dynamics parameter set in a project configuration changes what
    it controls -- the trajectory, the re-entry checks, the conservation
    warning -- and set to its default, leaves it as it was."""
    value, measure = _DYNAMICS_CASES[name]
    before = measure(None)
    assert measure(Configuration({name: registry.parameter(name).check(value)})) != before, name
    assert measure(Configuration({name: registry.default(name)})) == before, name


# -- every environment data parameter changes what it says it changes --------------------------

def _repeated_cycle(configuration):
    """The space weather a run from mid-2041 to 2045 is given, past the end
    of MSFC's prediction (October 2041): the file's days and the warnings."""
    import tempfile

    from spacemissionstudio.engine import spaceweather
    from spacemissionstudio.schema.scenario import SpaceWeatherConfig

    with tempfile.TemporaryDirectory() as cache:
        resolved = spaceweather.resolve_for(SpaceWeatherConfig(cache_dir=cache), datetime(2041, 6, 1),
                                            datetime(2045, 1, 1), scenario=SimpleNamespace(configuration=configuration))
        return resolved.path.read_text(encoding="utf-8"), tuple(resolved.warnings)


def _tle_warnings(configuration):
    """The scenario checks of tests/test_tle.py's ISS TLE, 10.3 days old."""
    from test_tle import LINE1, LINE2

    from spacemissionstudio.engine.scenario_checks import scenario_warnings

    scenario = Scenario(name="t", epoch_utc="2019-12-20T00:00:00", spacecraft=[SpacecraftConfig(
        name="iss", orbit=OrbitIC(type="tle", tle_line1=LINE1, tle_line2=LINE2))])
    scenario.configuration = configuration
    return [w for w in scenario_warnings(scenario) if "TLE" in w]


# name: (value to set, what to measure: called with the scenario's configuration, None for the defaults)
_ENVIRONMENT_CASES = {
    "space_weather.msfc_repeat_months": (120, _repeated_cycle),
    "tle.age_warning_days": (15.0, _tle_warnings),
}


@pytest.mark.parametrize("name", sorted(_ENVIRONMENT_CASES))
def test_setting_an_environment_parameter_changes_what_it_controls(name):
    """Each environment data parameter set in a project configuration
    changes what it controls -- the space weather past MSFC's prediction,
    the TLE age warning -- and set to its default, leaves it as it was."""
    value, measure = _ENVIRONMENT_CASES[name]
    before = measure(None)
    assert measure(Configuration({name: registry.parameter(name).check(value)})) != before, name
    assert measure(Configuration({name: registry.default(name)})) == before, name


def test_a_repeat_longer_than_the_prediction_is_refused(tmp_path):
    """MSFC's shipped table holds 187 months: repeating its last 200 is
    refused, naming the parameter."""
    from spacemissionstudio.engine import spaceweather
    from spacemissionstudio.schema.scenario import SpaceWeatherConfig

    scenario = SimpleNamespace(configuration=Configuration({"space_weather.msfc_repeat_months": 200}))
    with pytest.raises(spaceweather.SpaceWeatherError, match="msfc_repeat_months asks to repeat its last 200"):
        spaceweather.resolve_for(SpaceWeatherConfig(cache_dir=str(tmp_path)), datetime(2041, 6, 1),
                                 datetime(2045, 1, 1), scenario=scenario)


@pytest.mark.requires_basilisk
def test_a_runs_provenance_records_the_tolerances_it_used():
    """The tolerances a project configuration sets are the ones the run's
    provenance records."""
    from spacemissionstudio.engine.service import SimulationService, integrator_tolerances

    scenario = _budget_scenario()
    scenario.gravity.third_body_perturbers = ["sun"]  # a station keeper needs the Sun to validate
    scenario.configuration = Configuration({"dynamics.integrator_relative_tolerance": 1e-8})
    assert integrator_tolerances("rkf78", scenario) == (1e-8, 1e-8)
    assert integrator_tolerances("rk2", scenario) == (None, None)
    provenance = SimulationService(scenario).nominal_provenance()
    assert provenance.integrator_relative_tolerance == 1e-8


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("name", sorted(_LINK_CASES))
def test_setting_a_link_or_data_parameter_changes_what_it_controls(name):
    """Each link and data-handling parameter set in a project configuration
    changes the output it says it controls -- the simulated downlink, the
    pointing loss, the explanation's note -- and set to its default, leaves
    it as it was."""
    value, measure = _LINK_CASES[name]
    before = measure(None)
    assert measure(Configuration({name: registry.parameter(name).check(value)})) != before, name
    assert measure(Configuration({name: registry.default(name)})) == before, name


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("name", sorted(_CASES))
def test_setting_a_parameter_changes_what_it_controls(name, monkeypatch):
    """Each parameter set in a project configuration changes the output
    it says it controls, and leaves it as it was at its default."""
    value, budget, measure = _CASES[name]
    default_scenario, changed = _budget_scenario(**budget), _budget_scenario(**budget)
    changed.configuration = Configuration({name: registry.parameter(name).check(value)})
    if measure is None:
        before, after = _reentry_inputs(default_scenario, monkeypatch), _reentry_inputs(changed, monkeypatch)
    else:
        before, after = measure(default_scenario), measure(changed)
    assert before != after, name
    same = _budget_scenario(**budget)
    same.configuration = Configuration({name: registry.parameter(name).check(registry.default(name))})
    if measure is not None:
        assert measure(same) == before, name


@pytest.mark.requires_basilisk
def test_the_budgets_record_names_the_configuration_and_the_rules_in_effect(tmp_path):
    """A budget's ``--out`` record: its rules as in effect, under their
    registry names, and in the provenance the file and each value it
    changes, with the default it replaces."""
    from spacemissionstudio.engine import analysis_records

    scenario = _budget_scenario()
    scenario.configuration = Configuration({"propellant_budget.residual_fraction": 0.05},
                                           {"path": "/p/project.yaml", "sha256": "ab" * 32})
    record = analysis_records.budget_record(scenario, "sat-1", _budget(scenario))
    assert record["model"]["rules"]["propellant_budget.residual_fraction"] == 0.05
    assert record["model"]["rules"]["propellant_budget.cam_count_factor"] == 4.0
    assert record["provenance"]["configuration"] == {
        "file": {"path": "/p/project.yaml", "sha256": "ab" * 32},
        "overrides": {"propellant_budget.residual_fraction": {"value": 0.05, "default": 0.01, "unit": "[-]",
                                                              "source": "AD10 Sec. 5.8"}}}


def test_a_runs_recorded_value_is_the_one_it_had():
    """registry.recorded_value reads a value back from a provenance's
    ``configuration`` (a run shown later is judged by its own rules): the
    override when the run had one, else the default."""
    record = registry.record(SimpleNamespace(configuration=Configuration({"link.required_margin_db": 3.0})))
    assert registry.recorded_value("link.required_margin_db", record) == 3.0
    assert registry.recorded_value("link.required_margin_db", {}) == 0.0
    assert registry.recorded_value("link.required_margin_db", None) == 0.0
    assert registry.recorded_value("link.max_pointing_loss_db", record) == 30.0


def test_a_run_is_read_with_its_own_configuration():
    """registry.value_of_run: the value a run's provenance recorded; the
    default for a run without provenance or without that override."""
    from spacemissionstudio.engine.results import ResultSet

    assert registry.value_of_run("results.sma_window_orbits", ResultSet("no provenance")) == 1.0
    assert registry.value_of_run("results.sma_window_orbits", _run_with(None)) == 1.0
    configured = _run_with(Configuration({"results.sma_window_orbits": 2.0}))
    assert registry.value_of_run("results.sma_window_orbits", configured) == 2.0


# -- editing a project file (config.files.set_value, the Assumptions page) ---------------------

def test_setting_a_value_edits_only_its_line(tmp_path):
    """A value set replaces its own line and keeps the line's comment; a
    parameter the file does not name is added under ``parameters``; the
    rest of the file, comments included, is unchanged."""
    path = _project(tmp_path, "# our project\nformat: 1\nparameters:\n"
                              "  propellant_budget.residual_fraction: 0.05   # measured on our tanks\n")
    files.set_value(path, "propellant_budget.residual_fraction", 0.06)
    files.set_value(path, "propellant_budget.launch_delays_years", [0, 2])
    assert path.read_text(encoding="utf-8") == (
        "# our project\nformat: 1\nparameters:\n"
        "  propellant_budget.residual_fraction: 0.06   # measured on our tanks\n"
        "  propellant_budget.launch_delays_years: [0.0, 2.0]  # [year]\n")
    assert files.read(path).overrides == {"propellant_budget.residual_fraction": 0.06,
                                          "propellant_budget.launch_delays_years": (0.0, 2.0)}


def test_a_new_file_is_the_defaults_and_a_set_value_uncomments_its_line(tmp_path):
    """``new_file`` writes the defaults file (refusing to overwrite); a
    value set uncomments that parameter's own line, and Reset comments it
    out again at the default."""
    path = tmp_path / "project.yaml"
    files.new_file(path)
    assert path.read_text(encoding="utf-8") == files.defaults_yaml()
    with pytest.raises(ConfigError, match="already exists"):
        files.new_file(path)
    files.set_value(path, "lifetime.iadc_years", 20)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert "  lifetime.iadc_years: 20.0  # [year]" in lines and "  # lifetime.iadc_years: 25.0  # [year]" not in lines
    assert len(lines) == len(files.defaults_yaml().splitlines())
    files.reset_value(path, "lifetime.iadc_years")
    assert path.read_text(encoding="utf-8") == files.defaults_yaml()
    files.reset_value(path, "lifetime.iadc_years")  # already the default: nothing to do
    assert path.read_text(encoding="utf-8") == files.defaults_yaml()


def test_a_value_refused_leaves_the_file_as_it_was(tmp_path):
    """A value out of range, a name the registry lacks, or an edit that
    would leave the file unreadable: ConfigError, and the file unchanged."""
    text = "parameters:\n  lifetime.iadc_years: 20\n"
    path = _project(tmp_path, text)
    with pytest.raises(ConfigError, match="at most 100"):
        files.set_value(path, "lifetime.iadc_years", 1000)
    with pytest.raises(ConfigError, match="unknown parameter"):
        files.set_value(path, "lifetime.no_such_rule", 1)
    broken = tmp_path / "flow.yaml"  # a flow mapping: replacing its line drops the closing brace
    broken.write_text("parameters: {lifetime.iadc_years: 20,\n  lifetime.zero_debris_years: 5}\n", encoding="utf-8")
    before = broken.read_text(encoding="utf-8")
    with pytest.raises(ConfigError):
        files.set_value(broken, "lifetime.zero_debris_years", 6)
    assert broken.read_text(encoding="utf-8") == before
    assert path.read_text(encoding="utf-8") == text



# -- the orbit controllers (engine.orbit_maintenance, engine.geo_station_keeping) ---------------------
# Each measure drives the controller's own decision directly, with hand-made states, as
# tests/test_orbit_maintenance.py and tests/test_geo_station_keeping.py do.

def _gate_allows_a_firing(configuration):
    """An eccentricity-neutral firing of 1000 s at 0.01 m/s^2, its maneuver
    already at e = 3e-3: whether the gate lets it start (the firing's own
    allowance is 6.6e-3 at the default 2.5, one orbit's 4.8e-3 below it)."""
    import numpy as np

    from spacemissionstudio.engine.orbit_maintenance import ThrusterOnTimeModel

    thruster = ThrusterOnTimeModel(eccentricity_neutral=True, scenario=SimpleNamespace(configuration=configuration))
    thruster.eccVector = np.array([3e-3, 0.0])  # [-]
    return thruster._start_allowed(1.0, 1000.0, 1.0, 100.0, 0.0, 7600.0, 1.1e-3)  # [s], [N], [kg], [rad], ...


def _small_burn_command(configuration):
    """A burn needing 4 s of a thruster whose minimum on-time is 10 s:
    skipped below half an impulse bit, rounded up to one above."""
    from spacemissionstudio.engine.orbit_maintenance import ThrusterOnTimeModel

    thruster = ThrusterOnTimeModel(min_on_time_s=10.0, scenario=SimpleNamespace(configuration=configuration))
    return thruster.command(owner=object(), want_firing=True, remaining_dv=0.04, sign=1.0, thrust_n=1.0,
                            mass_kg=100.0, dt_s=30.0, in_sun=True, u_rad=0.0, v_mps=7600.0, mean_motion=1.1e-3)


def _phasing_controller(configuration, **overrides):
    from spacemissionstudio.engine.orbit_maintenance import PhasingKeepingController, SeparationSchedule

    nominal_a_m = 6928e3  # [m]
    settings = dict(name="pk", mu=3.986004418e14, nominal_a_m=nominal_a_m,
                    separation_schedule=SeparationSchedule(distances_km=[5.0], interval_days=0.0,
                                                           semi_major_axis_m=nominal_a_m),
                    tolerance_fraction=0.1, restore_tolerance_fraction=0.5, correction_window_days=1.0,
                    max_drift_days=5.0, max_delta_a_m=1000.0, thrust_n=0.05, isp_s=1500.0, dry_mass_kg=400.0,
                    scenario=SimpleNamespace(configuration=configuration))
    settings.update(overrides)
    return PhasingKeepingController(**settings)


def _cycles_before_phasing_stops(configuration):
    """Correction cycles that end outside the tolerance (a frozen 30 deg
    phase error) before phasing keeping suspends itself."""
    from test_orbit_maintenance import _build_non_convergent_phasing_controller

    controller = _build_non_convergent_phasing_controller(scenario=SimpleNamespace(configuration=configuration))
    controller.UpdateState(0)
    for cycle in range(1, 20):
        controller.state = controller.BURN_RESTORE
        controller._accumDv = controller._targetDv
        controller.UpdateState(int(cycle * 1e9))
        if controller.suspendedDueToNonConvergence:
            return cycle
    return None


def _split_trim(configuration):
    """A 60 m semi-major-axis correction with a 228 m minimum impulse bit:
    flown as one bit out and one back (the second leg's delta-V) when
    neither skipping nor one bit lands within the trim tolerance."""
    from spacemissionstudio.engine.orbit_maintenance import ThrusterOnTimeModel

    controller = _phasing_controller(configuration)
    controller.thruster = ThrusterOnTimeModel(min_on_time_s=1000.0)  # [s]
    controller._start_burn(60.0)  # [m]
    return controller._pendingLegDv


def _geo_controller(configuration, **config):
    from spacemissionstudio.engine.geo_station_keeping import GeoStationKeepingController
    from spacemissionstudio.schema.scenario import GeoStationKeepingConfig

    settings = dict(target_longitude_deg=10.0, thrust_n=0.01, isp_s=220.0, propellant_kg=50.0)  # [deg], [N], [s], [kg]
    settings.update(config)
    return GeoStationKeepingController("geo", 3.986004418e14, 6378136.6, GeoStationKeepingConfig(**settings), 500.0,
                                       scenario=SimpleNamespace(configuration=configuration))


def _geo_north_south_burn(configuration):
    """A north-south burn planned at the node of a 0.1 deg orbit (limit
    0.05 deg): its half arc and the delta-V it needs."""
    import math

    import numpy as np

    controller = _geo_controller(configuration, inclination_max_deg=0.05)
    controller._nsActive = True
    inclination = math.radians(0.1)  # [rad]
    r_n = np.array([42164e3, 0.0, 0.0])  # [m] at the ascending node
    v_n = np.array([0.0, 3074.7 * math.cos(inclination), 3074.7 * math.sin(inclination)])  # [m/s]
    h_hat = np.cross(r_n, v_n) / np.linalg.norm(np.cross(r_n, v_n))
    controller._north_south_force(r_n, v_n, h_hat, np.array([0.0, 0.0, 1.0]), inclination, 550.0)  # [kg]
    return round(controller._nsBurn[1], 12), round(controller._nsBurn[3], 12)


def _geo_maneuver_ends(configuration):
    """A north-south burn past its arc having delivered 85 % of its
    delta-V: whether the maneuver ends there."""
    import numpy as np

    controller = _geo_controller(configuration)
    controller._nsActive = True
    controller._nsBurn = [np.array([1.0, 0.0, 0.0]), 0.1, np.array([0.0, 0.0, 1.0]), 1.0, 0.85]
    r_n = np.array([0.0, 42164e3, 0.0])  # [m] 90 deg past the node
    controller._north_south_force(r_n, np.array([-3074.7, 0.0, 0.0]), np.array([0.0, 0.0, 1.0]),
                                  np.array([0.0, 0.0, 1.0]), 0.0, 550.0)
    return controller._nsActive


def _geo_east_west_plan(configuration):
    """At 80 deg E, east of the 75 deg E stable point (pulled back west), an
    eastward error of 0.06 deg and an eastward drift that would carry it
    0.3 x the 0.05 deg box further: whether a burn stops the drift (its
    delta-V)."""
    import math

    from spacemissionstudio.engine.geo_station_keeping import longitude_acceleration

    controller = _geo_controller(configuration, target_longitude_deg=80.0, longitude_deadband_deg=0.05)
    lon, a_m = math.radians(80.06), 42166.2e3  # [rad], [m]
    accel = abs(longitude_acceleration(lon, a_m, controller.rEquator))  # [rad/s^2] toward 75 E: inward
    drift = math.sqrt(2.0 * accel * 0.3 * controller.deadband)  # [rad/s]
    return controller._plan_east_west(math.radians(0.06), drift, a_m, lon)


def _geo_fits_in_half_an_hour(configuration):
    """East-west drift fits over 30 minutes of 60 s steps, with a day of
    samples already held."""
    import math

    import numpy as np
    from Basilisk.architecture import messaging

    from spacemissionstudio.engine.geo_station_keeping import _SIDEREAL_DAY_S

    controller = _geo_controller(configuration)
    state, planet = messaging.SCStatesMsg(), messaging.SpicePlanetStateMsg()
    payload = messaging.SpicePlanetStateMsgPayload()
    payload.J20002Pfix = np.eye(3).tolist()
    planet.write(payload)
    controller.scStateInMsg.subscribeTo(state)
    controller.planetStateInMsg.subscribeTo(planet)
    controller.Reset(0)
    start = _SIDEREAL_DAY_S + 60.0  # [s]
    controller._historyStartT = 0.0
    controller._history.extend((t, 0.0) for t in np.arange(60.0, start, 60.0))
    fits, fit = [], controller._drift_fit
    controller._drift_fit = lambda t: fits.append(t) or fit(t)
    lon = math.radians(10.0)  # [rad]
    for step in range(30):
        sc = messaging.SCStatesMsgPayload()
        sc.r_BN_N = [42164e3 * math.cos(lon), 42164e3 * math.sin(lon), 0.0]  # [m]
        sc.v_BN_N = [-3074.7 * math.sin(lon), 3074.7 * math.cos(lon), 0.0]  # [m/s]
        t = start + 60.0 * step  # [s]
        state.write(sc, int(t * 1e9))
        controller.UpdateState(int(t * 1e9))
    return len(fits)


_CONTROL_CASES = {
    "orbit_control.eccentricity_gate_factor": (0.5, _gate_allows_a_firing),
    "orbit_control.min_impulse_skip_fraction": (0.3, _small_burn_command),
    "orbit_control.phasing_non_convergent_cycles": (4, _cycles_before_phasing_stops),
    "orbit_control.relative_sma_trim_m": (100.0, _split_trim),
    "geo_station_keeping.max_half_arc_deg": (5.0, _geo_north_south_burn),
    "geo_station_keeping.inclination_reset_fraction": (0.5, _geo_north_south_burn),
    "geo_station_keeping.fit_interval_s": (300.0, _geo_fits_in_half_an_hour),
    "geo_station_keeping.drift_stop_fraction": (0.5, _geo_east_west_plan),
    "geo_station_keeping.ns_completion_fraction": (0.8, _geo_maneuver_ends),
}


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("name", sorted(_CONTROL_CASES))
def test_setting_a_controller_parameter_changes_what_it_controls(name):
    """Each orbit controller parameter set in a project configuration
    changes the decision it controls -- the firing gate, a small burn's
    rounding, phasing's divergence guard and trim, GEO station keeping's
    burn arc, target, fit cadence, drift stop and maneuver end -- and set
    to its default, leaves it as it was."""
    value, measure = _CONTROL_CASES[name]
    before = measure(None)
    assert measure(Configuration({name: registry.parameter(name).check(value)})) != before, name
    assert measure(Configuration({name: registry.default(name)})) == before, name


@pytest.mark.requires_basilisk
def test_the_controllers_read_the_scenarios_configuration():
    """The run builds each controller with its scenario, so a project's
    values reach the simulated station keeping, phasing and GEO control."""
    from pathlib import Path

    from spacemissionstudio.engine.service import SimulationService

    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    scenario = load_scenario(next(templates.glob("03_*.json")))
    scenario.configuration = Configuration({"geo_station_keeping.fit_interval_s": 1200.0,
                                            "orbit_control.min_impulse_skip_fraction": 0.2})
    service = SimulationService(scenario)
    service.build(initialize=False)
    controller = next(h.geo_station_keeping_controller for h in service._handles.values()
                      if h.geo_station_keeping_controller is not None)
    assert controller.fitIntervalS == 1200.0
    scenario = load_scenario(next(templates.glob("05_*.json")))
    scenario.configuration = Configuration({"orbit_control.phasing_non_convergent_cycles": 5,
                                            "orbit_control.min_impulse_skip_fraction": 0.2})
    service = SimulationService(scenario)
    service.build(initialize=False)
    phasing = [h.phasing_keeping_controller for h in service._handles.values()
               if getattr(h, "phasing_keeping_controller", None) is not None]
    assert phasing and all(c.maxNonConvergentCycles == 5 and c.thruster.skipFraction == 0.2 for c in phasing)


# The ROE formation guidance (engine.roe_formation), on a controller built
# directly: a 500 km sun-synchronous chief and a hold target 500 m behind.
_ROE_TARGET_M = (0.0, -500.0, 0.0, 200.0, 0.0, 200.0)  # [m] a times the mean ROE
_ROE_A_M = 6878137.0  # [m] the chief's mean semi-major axis


def _roe_controller(configuration):
    import math

    from spacemissionstudio.engine import roe
    from spacemissionstudio.engine.roe_formation import RoeFormationController
    from spacemissionstudio.schema.scenario import RoeFormationConfig, RoeTargetConfig

    mu = 3.986004418e14  # [m^3/s^2]
    config = RoeFormationConfig(chief_spacecraft="chief", targets=[RoeTargetConfig(0.0, list(_ROE_TARGET_M))])
    controller = RoeFormationController("follower", config, mu, 6378136.3, 1.0826e-3,  # [m], [-]
                                        thrust_n=0.1, isp_s=220.0, dry_mass_kg=100.0,  # [N], [s], [kg]
                                        eclipse_sunlit_threshold=0.5,  # [-]
                                        scenario=SimpleNamespace(configuration=configuration))
    chief = roe.MeanElements(_ROE_A_M, 0.001, math.radians(97.4), 0.3, 0.2, 0.1)  # [m], [-], [rad] x 4
    return controller, chief, math.sqrt(mu / _ROE_A_M ** 3)  # [rad/s]


def _roe_decision(configuration, error_m, drift_m=None, decay_m_per_day=None):
    """The controller's decision at t = 1000 s with the mean ROE ``error_m``
    [m] off the target, a drift holding ``a*da = drift_m`` [m] in progress
    and a differential-drag decay of ``a*da`` [m/day] to plan with."""
    import numpy as np

    controller, chief, n = _roe_controller(configuration)
    target = np.array(_ROE_TARGET_M) / _ROE_A_M
    controller._driftDa = None if drift_m is None else drift_m / _ROE_A_M
    controller._dragRate = None if decay_m_per_day is None else decay_m_per_day / 86400.0 / _ROE_A_M
    controller._decide(1000.0, target + np.array(error_m) / _ROE_A_M, target, chief, 0.0, n, 120.0)  # [s], [kg]
    return controller


def _roe_next_check(configuration):
    """In tolerance: when the controller looks again."""
    return _roe_decision(configuration, [0.0] * 6)._nextDecisionT


def _roe_glide(configuration):
    """A 100 m drift with 1000 m of mean longitude to go: the da it is cut
    back to."""
    return _roe_decision(configuration, [0.0, 1000.0, 0.0, 0.0, 0.0, 0.0], drift_m=-100.0)._driftDa


def _roe_corrects_directly(configuration):
    """A 140 m (seven-tolerance) mean longitude error: corrected without a
    drift?"""
    return _roe_decision(configuration, [0.0, 140.0, 0.0, 0.0, 0.0, 0.0])._driftDa is None


def _roe_burns_for_drag(configuration):
    """In tolerance with a 12 m/day decay: the burns planned to stay inside
    (none while the look-ahead is inside the trigger)."""
    return len(_roe_decision(configuration, [0.0] * 6, decay_m_per_day=-12.0)._pending)


def _roe_drag_cycle_burns(configuration):
    """A 3 m da error with a 12 m/day decay: the drag cycle's burns [m/s]."""
    controller = _roe_decision(configuration, [3.0, 0.0, 0.0, 0.0, 0.0, 0.0], decay_m_per_day=-12.0)
    return [round(p.burn.magnitude, 12) for p in controller._pending]


def _roe_after_eclipse(configuration):
    """A burn meeting eclipse for the third time: the burns still planned
    (it waits an orbit, or the plan is dropped)."""
    import numpy as np

    from spacemissionstudio.engine import roe
    from spacemissionstudio.engine.roe_formation import _Pending

    controller, chief, n = _roe_controller(configuration)
    burn = _Pending(1000.0, roe.Burn(0.0, (0.0, 0.002, 0.0), "in-plane"))  # [s], [rad], [m/s]
    burn.eclipseTries = 2
    controller._firing = burn
    target = np.array(_ROE_TARGET_M) / _ROE_A_M
    controller._impulsive(1000.0, 1.0, target, target, chief, np.array([_ROE_A_M, 0.0, 0.0]),  # [s], [s], [m]
                          np.array([0.0, 7612.6, 0.0]), 0.0, n, 120.0, False)  # [m/s], [rad], [kg]
    return len(controller._pending)


def _roe_decay_estimate(configuration, orbits, step_m=0.0):
    """The decay [1/s] fitted to ``orbits`` of a 3.5 m/day decay sampled
    each minute, with a ``step_m`` jump halfway (a reboost of the chief)."""
    import math

    controller, _chief, n = _roe_controller(configuration)
    estimator = controller.new_drag_estimator(_ROE_A_M, n)
    period_s = 2.0 * math.pi / n
    for k in range(int(orbits * period_s / 60.0)):
        t = 60.0 * k  # [s]
        jump = step_m if t > 0.5 * orbits * period_s else 0.0  # [m]
        estimator.add(t, (-3.5 / 86400.0 * t + jump) / _ROE_A_M)
    return estimator.rate()


def _roe_drift(configuration, error_dl_m, drift_m):
    """A drift holding ``a*da = drift_m`` [m] with ``error_dl_m`` [m] of mean
    longitude to go: the da it holds after the decision (None: stopped)."""
    drift = _roe_decision(configuration, [0.0, error_dl_m, 0.0, 0.0, 0.0, 0.0], drift_m=drift_m)._driftDa
    return None if drift is None else round(drift * _ROE_A_M, 9)


def _roe_held_drift_check(configuration):
    """A 30 m drift, held (its da already reached), 300 m from the target
    and gliding in over one orbit, with two orbits between checks: when
    the controller looks again before the stop is due."""
    import numpy as np

    controller, chief, n = _roe_controller(configuration)
    controller.glideOrbits, controller.holdingCheckFraction = 1.0, 2.0  # [orbit] so the look-again comes first
    target = np.array(_ROE_TARGET_M) / _ROE_A_M
    controller._driftDa = 30.0 / _ROE_A_M
    controller._decide(1000.0, target + np.array([30.0, 300.0, 0.0, 0.0, 0.0, 0.0]) / _ROE_A_M, target, chief,
                       0.0, n, 120.0)  # [s], [rad], [kg]
    return controller._nextDecisionT


def _roe_large_error_burns(configuration):
    """A 1000 m mean longitude error, no drift yet: the burns planned [m/s]
    (made again from where the first plan's burns lead, or not)."""
    controller = _roe_decision(configuration, [0.0, 1000.0, 0.0, 0.0, 0.0, 0.0])
    return [round(p.burn.magnitude, 12) for p in controller._pending]


def _roe_decay_compensated(configuration):
    """A 0.2 m/day decay estimated, in tolerance: the decay the guidance
    plans with (None: left to the ordinary corrections)."""
    import numpy as np

    controller, chief, n = _roe_controller(configuration)
    controller.dragEstimator = SimpleNamespace(rate=lambda: -0.2 / 86400.0 / _ROE_A_M)  # [1/s]
    target = np.array(_ROE_TARGET_M) / _ROE_A_M
    controller._decide(1000.0, target, target, chief, 0.0, n, 120.0)  # [s], [rad], [kg]
    return controller._dragRate


_ROE_CASES = {
    "roe_formation.holding_check_fraction": (0.5, _roe_next_check),
    "roe_formation.glide_orbits": (6.0, _roe_glide),
    "roe_formation.direct_dl_factor": (10.0, _roe_corrects_directly),
    "roe_formation.eclipse_retries": (5, _roe_after_eclipse),
    "roe_formation.drag_min_orbits": (2.0, lambda configuration: _roe_decay_estimate(configuration, 3.0)),
    "roe_formation.drag_jump_m": (1.0, lambda configuration: _roe_decay_estimate(configuration, 6.0, 0.3)),
    "roe_formation.drag_hold_fraction": (0.3, _roe_drag_cycle_burns),
    "roe_formation.drag_lookahead_orbits": (1.0, _roe_burns_for_drag),
    "roe_formation.drag_trigger_fraction": (0.95, _roe_burns_for_drag),
    "roe_formation.drag_significance_fraction": (1.0, _roe_decay_compensated),
    "roe_formation.slow_drift_fraction": (2.0, lambda configuration: _roe_drift(configuration, 15.0, 3.0)),
    "roe_formation.stop_band_factor": (1.0, lambda configuration: _roe_drift(configuration, 5.0, 2.5)),
    "roe_formation.cutback_band_factor": (2.0, lambda configuration: _roe_drift(configuration, 1000.0, 50.0)),
    "roe_formation.stop_reached_fraction": (0.05, lambda configuration: _roe_drift(configuration, 5.0, 2.0)),
    "roe_formation.min_check_s": (3000.0, _roe_held_drift_check),
    "roe_formation.replan_shift_fraction": (10.0, _roe_large_error_burns),
}


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("name", sorted(_ROE_CASES))
def test_setting_an_roe_guidance_rule_changes_its_decision(name):
    """Each ROE guidance rule set in a project configuration changes the
    decision it controls -- when to look again, the glide-in drift, a
    direct correction or a drift, the eclipse retries, the decay
    estimate's span and jumps, the drag cycle and when it is corrected,
    whether a decay is compensated, a drift's slow end, its stop and
    cut-back bands, when its stop counts as reached, the earliest
    look-again and the re-plan -- and set to its default, leaves it as it
    was."""
    value, measure = _ROE_CASES[name]
    before = measure(None)
    assert measure(Configuration({name: registry.parameter(name).check(value)})) != before, name
    assert measure(Configuration({name: registry.default(name)})) == before, name


@pytest.mark.requires_basilisk
def test_the_roe_controller_reads_the_scenarios_configuration():
    """The run builds the ROE formation controller with its scenario, so a
    project's guidance rules reach the simulated formation."""
    from pathlib import Path

    from spacemissionstudio.engine.service import SimulationService

    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    scenario = load_scenario(next(templates.glob("29_*.json")))
    scenario.configuration = Configuration({"roe_formation.glide_orbits": 5.0,
                                            "roe_formation.eclipse_retries": 4})
    service = SimulationService(scenario)
    service.build(initialize=False)
    controllers = [h.roe_formation_controller for h in service._handles.values()
                   if h.roe_formation_controller is not None]
    assert controllers and all(c.glideOrbits == 5.0 and c.eclipseRetries == 4 for c in controllers)
