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

"""Random seeds: each model gets its own, derived from the scenario's
(``engine.seeds``; audit E5). Before, every model kept Basilisk's default
``RNGSeed``, so two identical sensors drew identical noise."""

import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from spacemissionstudio.engine.seeds import BASILISK_DEFAULT_RNG_SEED, assign_rng_seeds, derived_seed
from spacemissionstudio.schema import ScenarioValidationError, load_scenario
from spacemissionstudio.schema.scenario import SimSettings

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"


def _model(tag, seed=BASILISK_DEFAULT_RNG_SEED):
    return SimpleNamespace(ModelTag=tag, RNGSeed=seed)


def test_each_model_gets_its_own_seed_and_a_chosen_seed_is_kept():
    """Models still on Basilisk's default seed get one each, from the run's
    seed and their name (a second model with the same name, or one without
    a name, too); a seed set on purpose stays."""
    nav = _model("sat-1_nav", seed=41)
    first, second, untagged = _model("sat-1_css-1"), _model("sat-1_css-1"), _model("")
    sim = SimpleNamespace(TaskList=[SimpleNamespace(TaskModels=[first, nav]),
                                    SimpleNamespace(TaskModels=[second, untagged])])
    seeds = assign_rng_seeds(sim, 0)
    assert nav.RNGSeed == 41 and "sat-1_nav" not in seeds
    assert set(seeds) == {"sat-1_css-1", "sat-1_css-1#2", "TaskList[1].TaskModels[1]"}
    assert len({first.RNGSeed, second.RNGSeed, untagged.RNGSeed}) == 3
    assert first.RNGSeed == seeds["sat-1_css-1"] == derived_seed(0, "sat-1_css-1")
    assert all(0 <= seed < 2 ** 32 for seed in seeds.values())


def test_a_derived_seed_depends_on_both_the_run_seed_and_the_name():
    """The same run seed and name give the same seed; another of either gives
    another."""
    assert derived_seed(0, "sat-1_css-1") == derived_seed(0, "sat-1_css-1")
    assert derived_seed(0, "sat-1_css-1") != derived_seed(1, "sat-1_css-1")
    assert derived_seed(0, "sat-1_css-1") != derived_seed(0, "sat-2_css-1")


def test_the_scenario_seed_is_a_whole_number_in_range():
    """sim_settings.seed is a whole number from 0 to 2**31 - 1."""
    SimSettings(seed=0).validate()
    SimSettings(seed=2 ** 31 - 1).validate()
    for bad in (-1, 2 ** 31, 1.5, True):
        with pytest.raises(ScenarioValidationError, match="sim_settings.seed"):
            SimSettings(seed=bad).validate()


def _twin_sun_sensors(seed=0, noise=0.05):  # noise [-]
    """Template 14 for 7.2 minutes with a noisy css-1 and an identical twin,
    css-1b: their two readings."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = load_scenario(next(_TEMPLATES.glob("14_*.json")))
    scenario.sim_settings.duration_days = 0.005  # [day]
    scenario.sim_settings.seed = seed
    sensors = scenario.spacecraft[0].sensors
    sensors[0].params["noise_std"] = noise
    twin = copy.deepcopy(sensors[0])
    twin.name = "css-1b"
    sensors.append(twin)
    result = SimulationService(scenario).run()
    return (result.series["sat-1.sensor.css-1"].data[:, 0], result.series["sat-1.sensor.css-1b"].data[:, 0],
            result.provenance)


@pytest.mark.requires_basilisk
def test_two_identical_sensors_draw_independent_noise_that_repeats_with_the_seed():
    """Two identical noisy sun sensors on one spacecraft gave identical
    readings (noise correlation 1.0). Now their noise is independent, the
    same scenario gives the same readings, another seed other noise, and
    the provenance records the seeds."""
    a, b, provenance = _twin_sun_sensors()
    truth, _, _ = _twin_sun_sensors(noise=0.0)
    lit = (truth > 0.1) & (a > 0.1) & (b > 0.1)
    noise_a, noise_b = a[lit] - truth[lit], b[lit] - truth[lit]
    assert lit.sum() > 100
    assert abs(np.corrcoef(noise_a, noise_b)[0, 1]) < 0.2
    assert 0.03 < noise_a.std() < 0.07 and 0.03 < noise_b.std() < 0.07  # set 0.05

    again, _, _ = _twin_sun_sensors()
    assert np.array_equal(a, again)
    other, _, _ = _twin_sun_sensors(seed=7)
    assert not np.array_equal(a, other)

    assert provenance.rng_seed == 0
    assert provenance.rng_seeds["sat-1_css-1"] != provenance.rng_seeds["sat-1_css-1b"]
