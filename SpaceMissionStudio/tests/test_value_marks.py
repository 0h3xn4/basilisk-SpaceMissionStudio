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


def test_a_rename_carries_the_marks_and_a_removal_drops_them():
    """schema.references' renames point the marks at the new name; a mark
    whose spacecraft is gone, or whose field no longer holds a number, is
    not live."""
    from spacemissionstudio.schema.references import rename_ground_station, rename_spacecraft
    from spacemissionstudio.schema.scenario import live_value_marks

    scenario = _scenario()
    station = ValueMark("ground_stations[berlin-gs].min_elevation_deg", "computed", 10.0, "the template")
    scenario.value_marks = [_computed(scenario), station]
    rename_spacecraft(scenario, "leo-comms-1", "leo-comms-2")
    rename_ground_station(scenario, "berlin-gs", "bonn-gs")
    assert [m.path for m in scenario.value_marks] == ["spacecraft[leo-comms-2].orbit.inclination_deg",
                                                      "ground_stations[bonn-gs].min_elevation_deg"]
    scenario.validate()
    scenario.ground_stations = []
    assert live_value_marks(scenario, scenario.value_marks) == [scenario.value_marks[0]]
    scenario.spacecraft[0].orbit.inclination_deg = None
    assert live_value_marks(scenario, scenario.value_marks) == []


def _walker_request(**changes):
    from spacemissionstudio.engine.constellation import WalkerConstellationRequest

    request = dict(total_satellites=4, num_planes=2, phasing_factor=1, altitude_km=550.0, inclination_deg=53.0)
    request.update(changes)
    return WalkerConstellationRequest(**request)


def test_the_walker_generator_marks_what_it_computed():
    """Each satellite's semi-major axis, RAAN and mean anomaly, at the
    values written, with its plane and slot; the inclination only when
    something computed it."""
    from spacemissionstudio.engine.constellation import generate_walker_constellation, walker_value_marks

    request = _walker_request()
    generated = generate_walker_constellation(request, _scenario().spacecraft[0])
    marks = walker_value_marks(request, generated)
    assert len(marks) == 3 * 4
    by_path = {mark.path: mark for mark in marks}
    third = generated[2]  # plane 2, slot 1
    raan = by_path[f"spacecraft[{third.name}].orbit.raan_deg"]
    assert raan.value == third.orbit.raan_deg and "plane 2 of 2, slot 1 of 2" in raan.source
    assert "Walker delta 4/2/1 at 550 km" in raan.source
    assert by_path[f"spacecraft[{third.name}].orbit.mean_anomaly_deg"].value == third.orbit.mean_anomaly_deg
    assert not any(path.endswith("inclination_deg") for path in by_path)
    marks = walker_value_marks(request, generated, inclination_source="Sun-synchronous inclination at ...")
    assert by_path[f"spacecraft[{third.name}].orbit.raan_deg"].state == "computed"
    assert sum(mark.path.endswith("inclination_deg") for mark in marks) == 4


@pytest.mark.requires_basilisk
def test_with_j2_every_osculating_element_is_marked():
    from spacemissionstudio.engine.constellation import generate_walker_constellation, walker_value_marks

    request = _walker_request()
    generated = generate_walker_constellation(request, _scenario().spacecraft[0], j2=1.08262668e-3)
    marks = walker_value_marks(request, generated, j2=1.08262668e-3)
    assert len(marks) == 6 * 4 and all("osculating from the mean elements with J2" in m.source for m in marks)
    scenario = _scenario()
    scenario.spacecraft = generated
    scenario.value_marks = marks
    assert {record["status"] for record in value_mark_records(scenario)} == {"computed"}
