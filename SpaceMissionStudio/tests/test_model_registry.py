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
#
"""config.models, the registry of selectable models (transparency plan,
Phase 6a), and its first choice: the Monte Carlo spread's statistic
(Basilisk-free, on synthetic circular orbits)."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.config import files, models, registry
from spacemissionstudio.config.registry import ConfigError, Configuration
from spacemissionstudio.engine import monte_carlo_results as mcr

_TESTS = Path(__file__).resolve().parent
_MODELS_DOCS = _TESTS.parent / "docs" / "models"
# The page of docs/models that documents each choice's models.
_PAGES = {"monte_carlo.spread_statistic": "monte-carlo-statistics.md",
          "propellant_budget.margin_policy": "propellant-budget.md",
          "dynamics.shadowing_bodies": "dynamics-run-control.md",
          "link.atmospheric_loss": "link-data-and-power.md",
          "power.degradation": "link-data-and-power.md"}

_R_M = 6778.0e3  # [m] orbit radius
_N_RAD_S = math.sqrt(3.986004415e14 / _R_M ** 3)  # [rad/s] mean motion


def _batch(phase_rad, statistic="population"):
    """Equatorial circular orbits, run k ``phase_rad[k]`` ahead along track."""
    t = np.linspace(0.0, 3000.0, 20)  # [s]
    u = _N_RAD_S * t[None, :] + np.asarray(phase_rad)[:, None]
    r = np.stack([_R_M * np.cos(u), _R_M * np.sin(u), np.zeros_like(u)], axis=-1)
    v = np.stack([-_R_M * _N_RAD_S * np.sin(u), _R_M * _N_RAD_S * np.cos(u), np.zeros_like(u)], axis=-1)
    return mcr.MonteCarloBatch("synthetic", "earth", t, list(range(len(phase_rad))), [], {"sat-1": r},
                               {"sat-1": v}, [{} for _ in phase_rad], "2030-01-01T00:00:00", statistic)


def test_every_model_is_declared_with_what_a_reader_needs():
    """Each choice is a parameter of kind "model" whose values are its
    models and whose default is one of them; each model has a title, a
    method, inputs, outputs, assumptions and references, a page that names
    it, and evidence: tests that exist."""
    assert models.choices() == list(_PAGES)
    for choice in models.choices():
        parameter = registry.parameter(choice)
        assert parameter.kind == "model" and parameter.choices == models.names(choice)
        assert parameter.default in models.names(choice)
        page = (_MODELS_DOCS / _PAGES[choice]).read_text(encoding="utf-8")
        assert f"`{choice}`" in page
        for model in models.models(choice):
            assert model.title and model.method and model.inputs and model.outputs and model.assumptions
            assert model.references and model.evidence and model.applies_to
            assert f"`{model.name}`" in page and model.title in page, model.name
            for where in model.evidence:
                file, name = where.split("::")
                assert f"def {name}(" in (_TESTS.parent / file).read_text(encoding="utf-8"), where


def test_a_model_is_declared_once_and_whole():
    """A second declaration of a name, or one without its evidence, is a
    fault of the code, found when it is imported."""
    first = models.models("monte_carlo.spread_statistic")[0]
    with pytest.raises(ValueError, match="declared twice"):
        models.register(first)
    from dataclasses import replace

    with pytest.raises(ValueError, match="every part"):
        models.register(replace(first, name="median", evidence=()))
    assert models.names("monte_carlo.spread_statistic") == ("population", "sample")


def test_a_project_file_chooses_a_model_by_name(tmp_path):
    """The choice is set as any parameter is; a name that is not one of its
    models is refused when the file is read, naming the models."""
    path = tmp_path / "project.yaml"
    path.write_text("format: 1\nparameters:\n  monte_carlo.spread_statistic: sample\n", encoding="utf-8")
    configuration = files.read(path)
    assert configuration.overrides == {"monte_carlo.spread_statistic": "sample"}

    class _Scenario:
        pass

    scenario = _Scenario()
    scenario.configuration = configuration
    assert models.active("monte_carlo.spread_statistic", scenario).title == "Sample standard deviation"
    assert models.active("monte_carlo.spread_statistic").name == "population"  # the default
    assert models.records(scenario, "monte_carlo")["monte_carlo.spread_statistic"]["model"] == "sample"
    assert models.records(scenario, "a single run") == {}
    path.write_text("format: 1\nparameters:\n  monte_carlo.spread_statistic: median\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="one of population, sample, got 'median'"):
        files.read(path)
    with pytest.raises(ConfigError, match="one of population, sample"):
        registry.parameter("monte_carlo.spread_statistic").check(1.0)


def test_each_spread_statistic_is_the_one_it_declares():
    """Population: divided by N (numpy.std's default, the tool's statistic
    before the choice). Sample: by N - 1, sqrt(N / (N - 1)) times larger:
    1.2247 for three runs. One run: no spread either way."""
    phase = [0.0, 1e-4, -1e-4]  # [rad]
    along_m = np.asarray(phase) * _R_M  # [m] each run's along-track offset
    population = mcr.final_spread(_batch(phase), "sat-1")
    sample = mcr.final_spread(_batch(phase, "sample"), "sat-1")
    assert population.along_track_m == pytest.approx(math.sqrt(np.sum(along_m ** 2) / 3), rel=1e-6)
    assert sample.along_track_m == pytest.approx(math.sqrt(np.sum(along_m ** 2) / 2), rel=1e-6)
    assert sample.along_track_m / population.along_track_m == pytest.approx(math.sqrt(3 / 2), rel=1e-9)
    series = mcr.to_result_set(_batch(phase, "sample")).series["sat-1.monte_carlo.spread"].data
    assert series[-1, 1] == pytest.approx(sample.along_track_m, rel=1e-12)
    assert mcr.final_spread(_batch([1e-4], "sample"), "sat-1").along_track_m == 0.0
    assert set(mcr.SPREAD_DDOF) == set(models.names(mcr.SPREAD_CHOICE))


def test_a_batch_keeps_its_statistic_and_says_which(tmp_path):
    """The summary saves the statistic and reads it back; a summary
    written before the choice reads as population; an unknown one is
    refused. The command line's line names it."""
    mcr.save(_batch([0.0, 1e-4, -1e-4], "sample"), tmp_path)
    loaded = mcr.load(tmp_path)
    assert loaded.spread_statistic == "sample"
    assert mcr.statistic_line(loaded) == ("1-sigma: the sample standard deviation of the 3 run(s) "
                                          "(monte_carlo.spread_statistic: sample)")
    meta = json.loads((tmp_path / mcr.SUMMARY_JSON).read_text())
    del meta["spread_statistic"]
    (tmp_path / mcr.SUMMARY_JSON).write_text(json.dumps(meta))
    assert mcr.load(tmp_path).spread_statistic == "population"
    meta["spread_statistic"] = "median"
    (tmp_path / mcr.SUMMARY_JSON).write_text(json.dumps(meta))
    with pytest.raises(mcr.MonteCarloResultsError, match="unknown spread statistic 'median'"):
        mcr.load(tmp_path)


def test_the_default_statistic_gives_the_numbers_it_gave():
    """The default is the population standard deviation, so every batch
    reads as before the choice (the golden baseline checks the templates)."""
    assert registry.default("monte_carlo.spread_statistic") == "population"
    batch = _batch([0.0, 2e-4, -1e-4, 5e-5])
    rel = mcr.offsets(batch.positions["sat-1"], batch.velocities["sat-1"])
    np.testing.assert_array_equal(mcr.to_result_set(batch).series["sat-1.monte_carlo.spread"].data,
                                  rel.std(axis=0))
    assert Configuration().overrides == {}


_POLICY = "propellant_budget.margin_policy"


class _Configured:
    """A stand-in scenario carrying only a configuration."""

    def __init__(self, overrides):
        self.configuration = Configuration(overrides=overrides)


def test_a_margin_policy_sets_its_margins_and_a_projects_own_value_wins():
    """AD10's equations (the default) set nothing: the margins are the
    parameters' defaults. The summary table sets the residual and the
    uncertainty to 10 % and 20 %; a value the project file sets itself
    replaces the policy's. The record names what the policy set, and a run
    read later gets the same values from it."""
    assert models.names(_POLICY) == ("ad10_equations", "ad10_summary_table")
    assert registry.default(_POLICY) == "ad10_equations" and models.model(_POLICY, "ad10_equations").sets == ()
    table = _Configured({_POLICY: "ad10_summary_table"})
    assert registry.value("propellant_budget.residual_fraction", table) == 0.10
    assert registry.value("propellant_budget.uncertainty_fraction", table) == 0.20
    assert registry.value("propellant_budget.cam_count_factor", table) == 4.0  # the equations'
    assert registry.set_by("propellant_budget.residual_fraction", table).name == "ad10_summary_table"
    own = _Configured({_POLICY: "ad10_summary_table", "propellant_budget.residual_fraction": 0.05})
    assert registry.value("propellant_budget.residual_fraction", own) == 0.05
    assert registry.set_by("propellant_budget.residual_fraction", own) is None
    assert registry.value("propellant_budget.uncertainty_fraction", own) == 0.20
    record = registry.record(own)
    assert record["set_by_models"] == {"propellant_budget.uncertainty_fraction": {
        "value": 0.2, "default": 0.02, "unit": "[-]", "model": "propellant_budget.margin_policy: ad10_summary_table"}}
    assert registry.recorded_value("propellant_budget.uncertainty_fraction", record) == 0.20
    assert registry.recorded_value("propellant_budget.residual_fraction", record) == 0.05
    assert "set_by_models" not in registry.record(_Configured({}))  # a default record is as before
    assert registry.value("propellant_budget.residual_fraction") == 0.01


def test_a_model_that_sets_a_value_its_parameter_may_not_take_is_refused(monkeypatch):
    """The values a model sets are checked against their parameters when
    the registry is declared, as a default is."""
    from dataclasses import replace

    bad = replace(models.model(_POLICY, "ad10_summary_table"), name="bad",
                  sets=(("propellant_budget.residual_fraction", 2.0),))
    monkeypatch.setitem(models._MODELS, _POLICY, {**models._MODELS[_POLICY], "bad": bad})
    monkeypatch.setitem(registry._REGISTRY, _POLICY, replace(registry.parameter(_POLICY),
                                                             choices=models.names(_POLICY)))
    with pytest.raises(ConfigError, match="residual_fraction: at most 0.5"):
        registry.check_models()
    monkeypatch.setitem(registry._REGISTRY, _POLICY, replace(registry.parameter(_POLICY),
                                                             choices=("ad10_equations",)))
    with pytest.raises(ValueError, match="not a parameter of kind 'model'"):
        registry.check_models()


def _budget_scenario(overrides):
    from spacemissionstudio.schema.scenario import (GravityConfig, OrbitIC, PropellantBudgetConfig, Scenario,
                                                    SpacecraftConfig, StationKeepingConfig)

    spacecraft = SpacecraftConfig(
        name="sat-1", dry_mass_kg=120.0, enable_drag=True,
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6378.1366 + 400.0, eccentricity=0.0,
                      inclination_deg=97.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
        station_keeping=StationKeepingConfig(target_altitude_km=400.0, deadband_km=1.0, thrust_n=0.05,
                                             isp_s=1500.0, propellant_kg=5.0),
        propellant_budget=PropellantBudgetConfig(in_plane_control_delta_v_m_s=20.0, tank_capacity_kg=10.0))
    scenario = Scenario(name="b", epoch_utc="2030-01-01T00:00:00", spacecraft=[spacecraft],
                        gravity=GravityConfig(central_body="earth", third_body_perturbers=["sun"]))
    scenario.configuration = Configuration(overrides=overrides)
    return scenario


def test_the_summary_tables_budget_says_so_and_records_it():
    """With the summary table, the residual and uncertainty rows are 10 %
    and 20 % of the 10 kg tank; the note names the policy and the
    equations' values, each trace input says the policy set it, and the
    budget's record names the policy and what it set. AD10's equations
    give the note as before."""
    from spacemissionstudio.engine import analysis_records
    from spacemissionstudio.engine import propellant_budget as pb

    budget = pb.compute_budget(_budget_scenario({_POLICY: "ad10_summary_table"}), "sat-1")
    rows = {r.contributor: r for r in budget.rows}
    assert rows["Residual"].propellant_kg == pytest.approx(1.0)  # [kg] 10 % of 10 kg
    assert rows["Loading uncertainty and gauging"].propellant_kg == pytest.approx(2.0)  # [kg]
    assert ("residual and uncertainty are 10% and 20% of the tank load (propellant_budget.margin_policy: "
            "ad10_summary_table, AD10's summary table; AD10's equations give 1% and 2%, Secs. 5.8, 6.4)"
            in budget.notes)
    source = rows["Residual"].propellant_trace.inputs[0].source
    assert source == ("parameter: propellant_budget.residual_fraction "
                      "(set by propellant_budget.margin_policy: ad10_summary_table)")
    scenario = _budget_scenario({_POLICY: "ad10_summary_table"})
    record = analysis_records.budget_record(scenario, "sat-1", budget)
    assert record["model"]["models"][_POLICY]["model"] == "ad10_summary_table"
    assert record["model"]["models"][_POLICY]["sets"] == {"propellant_budget.residual_fraction": 0.1,
                                                          "propellant_budget.uncertainty_fraction": 0.2}
    assert record["model"]["rules"]["propellant_budget.residual_fraction"] == 0.10
    assert record["provenance"]["configuration"]["set_by_models"]["propellant_budget.residual_fraction"][
        "model"] == "propellant_budget.margin_policy: ad10_summary_table"
    equations = pb.compute_budget(_budget_scenario({}), "sat-1")
    assert ("residual and uncertainty are 1% and 2% of the tank load (AD10 Secs. 5.8, 6.4; its summary table "
            "prints 10% and 20%)" in equations.notes)
    assert {r.contributor: r for r in equations.rows}["Residual"].propellant_trace.inputs[0].source == (
        "parameter: propellant_budget.residual_fraction")
