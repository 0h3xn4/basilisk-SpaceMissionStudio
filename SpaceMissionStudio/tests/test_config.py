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
_MODEL_PAGES = {"propellant_budget": "propellant-budget.md"}


def test_every_parameter_is_documented_on_its_models_page():
    """Each area has its page in docs/models, linked from the index, and the
    page names each of its parameters."""
    from pathlib import Path

    models = Path(__file__).resolve().parent.parent / "docs" / "models"
    index = (models / "README.md").read_text(encoding="utf-8")
    assert {p.area for p in registry.parameters()} == set(_MODEL_PAGES)
    for area, page in _MODEL_PAGES.items():
        assert f"({page})" in index, page
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

    def decay(_orbit, _start, ballistic, _density, _horizon, *_args):
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


def test_every_parameter_has_a_case_that_sets_it():
    """A parameter declared without a case below fails here: the
    definition of done asks that a test set each one (transparency audit
    9.4)."""
    declared = {p.name for p in registry.parameters()}
    assert declared == set(_CASES), f"no case for {sorted(declared - set(_CASES))}"


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
