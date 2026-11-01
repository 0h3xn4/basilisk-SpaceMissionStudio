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
_PAGES = {"monte_carlo.spread_statistic": "monte-carlo-statistics.md"}

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
