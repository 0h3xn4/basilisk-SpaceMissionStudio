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
"""Computed and overridden values in the scenario file (the transparency
plan, Phase 5b, first step): a value the tool computed is marked so until
it is edited, an override keeps the computed value and the reason, and
every provenance record lists them. A scenario without marks saves and
hashes as before (tests/test_scenario_hashes.py)."""

import json
from pathlib import Path

import pytest

from spacemissionstudio import output_provenance
from spacemissionstudio.engine import long_run
from spacemissionstudio.engine.results import RunProvenance
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import (ScenarioValidationError, ValueMark, parse_scenario_text,
                                                resolve_value_path, scenario_text, value_mark_records,
                                                value_mark_status)

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_INCLINATION = "spacecraft[leo-comms-1].orbit.inclination_deg"


def _scenario():
    """Template 19: leo-comms-1 in a Sun-synchronous orbit, berlin-gs."""
    return load_scenario(next(_TEMPLATES.glob("19_*.json")))


def _computed(scenario):
    """The inclination marked as computed, at the value the field holds."""
    return ValueMark(_INCLINATION, "computed", scenario.spacecraft[0].orbit.inclination_deg,
                     "Sun-synchronous inclination at the orbit's a and e (engine.orbit_design)")


def test_a_scenario_without_marks_writes_none():
    scenario = _scenario()
    assert scenario.value_marks == [] and "value_marks" not in scenario.to_dict()
    assert "value_marks" not in scenario_text(scenario)


def test_marks_save_and_load_with_the_scenario(tmp_path):
    """A computed and an overridden value round-trip through the file."""
    scenario = _scenario()
    scenario.value_marks = [_computed(scenario),
                            ValueMark("ground_stations[berlin-gs].min_elevation_deg", "overridden", 5.0,
                                      "the template's suggested mask", reason="the site's horizon survey: 10 deg",
                                      author="A. Engineer", time_utc="2026-11-01T09:00:00+00:00")]
    path = tmp_path / "marked.json"
    scenario.save(path)
    assert json.loads(path.read_text(encoding="utf-8"))["value_marks"][1]["reason"] == "the site's horizon survey: 10 deg"
    back = load_scenario(path)
    assert back.value_marks == scenario.value_marks
    assert output_provenance.scenario_sha256(back) == output_provenance.scenario_sha256(scenario)


def test_a_computed_value_is_marked_until_it_is_edited():
    scenario = _scenario()
    mark = _computed(scenario)
    scenario.value_marks = [mark]
    assert value_mark_status(scenario, mark) == "computed"
    scenario.spacecraft[0].orbit.inclination_deg = 98.0  # [deg]
    assert value_mark_status(scenario, mark) == "edited"
    scenario.validate()  # an edited value is valid; the mark only records what was computed
    (record,) = value_mark_records(scenario)
    assert (record["status"], record["value_used"], record["value"]) == ("edited", 98.0, mark.value)


def test_an_override_needs_a_reason_and_keeps_the_computed_value():
    scenario = _scenario()
    computed = scenario.spacecraft[0].orbit.inclination_deg
    scenario.spacecraft[0].orbit.inclination_deg = 97.0  # [deg]
    scenario.value_marks = [ValueMark(_INCLINATION, "overridden", computed, "Sun-synchronous inclination")]
    with pytest.raises(ScenarioValidationError, match="an overridden value needs a reason"):
        scenario.validate()
    scenario.value_marks[0].reason = "the launcher's injection inclination"
    scenario.validate()
    (record,) = value_mark_records(scenario)
    assert (record["status"], record["value_used"], record["value"]) == ("overridden", 97.0, computed)
    assert record["reason"] == "the launcher's injection inclination"


@pytest.mark.parametrize(("path", "field"), [
    ("sim_settings.duration_days", "duration_days"),
    (_INCLINATION, "inclination_deg"),
    ("ground_stations[berlin-gs].min_elevation_deg", "min_elevation_deg"),
    ("ground_stations[0].latitude_deg", "latitude_deg"),  # by index, where no item has that name
])
def test_a_path_names_a_field_by_names_and_brackets(path, field):
    record, name = resolve_value_path(_scenario(), path)
    assert name == field and hasattr(record, field)


@pytest.mark.parametrize(("path", "words"), [
    ("", "empty"),
    ("sim_settings.no_such_field", "has no field 'no_such_field'"),
    ("spacecraft[nobody].orbit.inclination_deg", "has no item 'nobody'"),
    ("spacecraft[leo-comms-1]", "names a list item, not a field"),
    ("sim_settings[0].duration_days", "is not a list"),
    ("sim_settings..duration_days", "is not a path of field names"),
])
def test_a_path_that_names_no_field_is_refused(path, words):
    with pytest.raises(ValueError, match=words):
        resolve_value_path(_scenario(), path)


@pytest.mark.parametrize(("change", "words"), [
    (lambda m: setattr(m, "path", "spacecraft[leo-comms-1].name"), "is 'leo-comms-1', not a number"),
    (lambda m: setattr(m, "path", "sim_settings.nothing"), "has no field 'nothing'"),
    (lambda m: setattr(m, "state", "guessed"), "state must be one of"),
    (lambda m: setattr(m, "value", float("nan")), "value must be a finite number"),
    (lambda m: setattr(m, "source", " "), "source must say what computed the value"),
    (lambda m: setattr(m, "time_utc", "yesterday"), "is not an ISO 8601 time"),
])
def test_a_malformed_mark_is_refused(change, words):
    scenario = _scenario()
    mark = _computed(scenario)
    change(mark)
    scenario.value_marks = [mark]
    with pytest.raises(ScenarioValidationError, match=words):
        scenario.validate()


def test_a_value_is_marked_once():
    scenario = _scenario()
    scenario.value_marks = [_computed(scenario), _computed(scenario)]
    with pytest.raises(ScenarioValidationError, match="marks a value more than once"):
        scenario.validate()


def test_an_unknown_field_in_a_mark_is_refused():
    """A mark's unknown field is refused, naming it, as every record's is."""
    data = _scenario().to_dict()
    data["value_marks"] = [{"path": _INCLINATION, "state": "computed", "value": 97.59, "source": "x", "colour": 1}]
    with pytest.raises(ScenarioValidationError, match="value_marks\\[0\\]: unexpected field 'colour'"):
        parse_scenario_text(json.dumps(data), "marked.json")


def test_the_provenance_records_the_marks():
    """The record of an output made from the scenario (a lifetime, a
    budget, a batch) lists the marks, and only when there are some; a long
    run's record takes them from the scenario as given, not from a
    segment's copy."""
    scenario = _scenario()
    assert "value_marks" not in output_provenance.scenario_record(scenario)
    scenario.value_marks = [_computed(scenario)]
    (record,) = output_provenance.scenario_record(scenario)["value_marks"]
    assert record["path"] == _INCLINATION and record["status"] == "computed"
    whole = long_run._whole_run_provenance(scenario, [RunProvenance("test", "2.12.0", "", "rk4", 1.0)], None)
    assert whole.value_marks == value_mark_records(scenario) and whole.to_dict()["value_marks"] == whole.value_marks
    assert "value_marks" not in RunProvenance("test", "2.12.0", "", "rk4", 1.0).to_dict()  # a run's record as before


@pytest.mark.requires_basilisk
def test_a_runs_provenance_records_the_marks():
    from spacemissionstudio.engine.service import SimulationService

    scenario = _scenario()
    scenario.value_marks = [_computed(scenario)]
    provenance = SimulationService(scenario).nominal_provenance()
    assert provenance.value_marks == value_mark_records(scenario)
