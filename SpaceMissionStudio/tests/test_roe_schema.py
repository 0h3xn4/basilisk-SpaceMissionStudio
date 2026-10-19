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
"""The ROE formation in the scenario file (schema.scenario.RoeFormationConfig):
it saves and loads unchanged, each rule of its validation names what is
wrong, and renaming the chief follows into it. No Basilisk (the runs
are in ``test_roe_formation_run.py``)."""

from pathlib import Path

import pytest

from spacemissionstudio.schema import RoeFormationConfig, RoeTargetConfig, load_scenario
from spacemissionstudio.schema.references import find_spacecraft_references, rename_spacecraft
from spacemissionstudio.schema.scenario import ScenarioValidationError

_TEMPLATE = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
             / "05_formation_flying_phasing.json")


def _scenario(**roe_overrides):
    """Template 05's chief and follower, the follower in an ROE formation
    instead of phasing keeping."""
    scenario = load_scenario(_TEMPLATE)
    follower = next(sc for sc in scenario.spacecraft if sc.phasing_keeping is not None)
    chief = follower.phasing_keeping.chief_spacecraft
    follower.phasing_keeping = None
    fields = dict(chief_spacecraft=chief, targets=[RoeTargetConfig(0.0, [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]),
                                                  RoeTargetConfig(1.0, [0.0, 0.0, 0.0, 300.0, 0.0, 300.0])])
    fields.update(roe_overrides)
    follower.roe_formation = RoeFormationConfig(**fields)
    return scenario, follower


def test_an_roe_formation_saves_and_loads_unchanged(tmp_path):
    """A valid ROE formation, with a reconfiguration, survives a save and
    a load field by field."""
    scenario, follower = _scenario(control_law="continuous", tolerance_m=[1.0, 10.0, 5.0, 5.0],
                                   differential_drag=False, drag_estimate_window_days=2.5)
    scenario.validate()
    path = tmp_path / "roe.json"
    scenario.save(path)
    loaded = next(sc for sc in load_scenario(path).spacecraft if sc.name == follower.name)
    assert loaded.roe_formation == follower.roe_formation


@pytest.mark.parametrize("overrides, message", [
    ({"control_law": "lqr"}, "control_law"),
    ({"targets": []}, "at least one entry"),
    ({"targets": [RoeTargetConfig(0.5, [0.0] * 6)]}, r"targets\[0\].start_day must be 0"),
    ({"targets": [RoeTargetConfig(0.0, [0.0] * 6), RoeTargetConfig(0.0, [0.0] * 6)]}, "later than the one before"),
    ({"targets": [RoeTargetConfig(0.0, [0.0] * 5)]}, "6 finite numbers"),
    ({"targets": [RoeTargetConfig(0.0, [0.0, float("nan"), 0.0, 0.0, 0.0, 0.0])]}, "6 finite numbers"),
    ({"tolerance_m": [1.0, 1.0, 1.0]}, "tolerance_m"),
    ({"tolerance_m": [1.0, 0.0, 1.0, 1.0]}, "tolerance_m"),
    ({"correction_window_days": 0.0}, "correction_window_days"),
    ({"max_burn_fraction_of_orbit": 0.8}, "at most 0.5"),
    ({"differential_drag": 1}, "differential_drag must be true or false"),
    ({"drag_estimate_window_days": 0.0}, "drag_estimate_window_days"),
    ({"drag_estimate_window_days": float("inf")}, "drag_estimate_window_days"),
    ({"chief_spacecraft": "nobody"}, "not one of this scenario's spacecraft"),
])
def test_each_bad_value_is_named(overrides, message):
    """Each invalid field is refused with a message that names it."""
    scenario, _ = _scenario(**overrides)
    with pytest.raises(ScenarioValidationError, match=message):
        scenario.validate()


def test_the_follower_needs_station_keeping():
    """The ROE controller fires the station-keeping thruster: without it
    the formation is refused."""
    scenario, follower = _scenario()
    follower.station_keeping = None
    with pytest.raises(ScenarioValidationError, match="requires station_keeping"):
        scenario.validate()


def test_phasing_keeping_and_an_roe_formation_exclude_each_other():
    """Both would control the same formation: only one may be set."""
    scenario, follower = _scenario()
    follower.phasing_keeping = load_scenario(_TEMPLATE).spacecraft[1].phasing_keeping
    assert follower.phasing_keeping is not None
    with pytest.raises(ScenarioValidationError, match="keep one of them"):
        scenario.validate()


def test_an_eccentric_chief_is_refused():
    """The guidance is the near-circular one: a chief eccentricity above
    0.01 is refused."""
    scenario, follower = _scenario()
    chief = next(sc for sc in scenario.spacecraft if sc.name == follower.roe_formation.chief_spacecraft)
    chief.orbit.eccentricity = 0.05
    with pytest.raises(ScenarioValidationError, match="near-circular"):
        scenario.validate()


def test_point_mass_gravity_is_refused():
    """Mean elements and the STM are Earth's J2 theory: point-mass
    gravity is refused."""
    scenario, _ = _scenario()
    scenario.gravity.central_body_degree = 0
    with pytest.raises(ScenarioValidationError, match="J2"):
        scenario.validate()


def test_a_long_run_is_refused():
    """An ROE formation runs as one simulation: over 100 days is
    refused."""
    scenario, _ = _scenario()
    scenario.sim_settings.duration_days = 150.0
    scenario.sim_settings.record_interval_s = 600.0
    with pytest.raises(ScenarioValidationError, match="roe_formation runs at most"):
        scenario.validate()


def test_renaming_the_chief_follows_into_the_formation():
    """The chief is a reference: it is listed, and a rename updates it."""
    scenario, follower = _scenario()
    chief = follower.roe_formation.chief_spacecraft
    paths = [ref.path for ref in find_spacecraft_references(scenario, chief)]
    assert any(path.endswith("roe_formation.chief_spacecraft") for path in paths)
    rename_spacecraft(scenario, chief, "lead")
    assert follower.roe_formation.chief_spacecraft == "lead"


def test_a_file_from_before_differential_drag_compensates_it(tmp_path):
    """A scenario saved before the drag fields existed loads with the
    compensation on and a one-day estimate window, the defaults."""
    import json

    scenario, follower = _scenario()
    path = tmp_path / "roe.json"
    scenario.save(path)
    data = json.loads(path.read_text())
    saved = next(sc for sc in data["spacecraft"] if sc["name"] == follower.name)["roe_formation"]
    del saved["differential_drag"], saved["drag_estimate_window_days"]
    path.write_text(json.dumps(data))
    loaded = next(sc for sc in load_scenario(path).spacecraft if sc.name == follower.name).roe_formation
    assert loaded.differential_drag is True
    assert loaded.drag_estimate_window_days == 1.0  # [day]
