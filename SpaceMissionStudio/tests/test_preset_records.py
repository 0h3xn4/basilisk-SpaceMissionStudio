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
"""Spacecraft made from a preset (the transparency plan, Phase 5b): one
record per spacecraft keeps the preset's name and the numbers it gave, so
each value still as the preset gave it can be told from one changed."""

import json
from pathlib import Path

import pytest

from spacemissionstudio import output_provenance
from spacemissionstudio.engine.results import RunProvenance
from spacemissionstudio.engine.scenario_explainer import explain
from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.references import rename_spacecraft
from spacemissionstudio.schema.scenario import (PresetRecord, ScenarioValidationError, number_fields, preset_records,
                                                preset_status, preset_values, scenario_text)

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"


def _scenario_with_preset():
    """Template 19 (full attitude, the Sun modelled) with its spacecraft
    replaced by the ESPA preset."""
    scenario = load_scenario(next(_TEMPLATES.glob("19_*.json")))
    preset = SPACECRAFT_TEMPLATES[0]
    config = preset.build()
    config.name, config.orbit = "espa-1", scenario.spacecraft[0].orbit
    scenario.spacecraft = [config]
    scenario.ground_stations, scenario.mission_sequence = [], []
    scenario.presets = [PresetRecord("espa-1", preset.name, preset_values(config), "2026-11-01T12:00:00+00:00")]
    return scenario


def test_the_numbers_of_a_record_by_field_names():
    config = SPACECRAFT_TEMPLATES[0].build()
    fields = number_fields(config)
    assert fields["dry_mass_kg"] == config.dry_mass_kg and fields["inertia_kg_m2[0]"] == config.inertia_kg_m2[0]
    assert fields["sensors[st-1].params.noise_arcsec"] == 5.0  # [arcsec]
    values = preset_values(config)
    assert "orbit.semi_major_axis_km" in fields and not any(path.startswith("orbit") for path in values)


def test_a_preset_record_saves_with_the_scenario_and_says_what_changed(tmp_path):
    scenario = _scenario_with_preset()
    scenario.validate()
    path = tmp_path / "preset.json"
    scenario.save(path)
    back = load_scenario(path)
    assert back.presets == scenario.presets
    assert json.loads(path.read_text(encoding="utf-8"))["presets"][0]["preset"] == SPACECRAFT_TEMPLATES[0].name
    status = preset_status(back, back.presets[0])
    assert status["changed"] == [] and status["kept"] == len(back.presets[0].values)
    back.spacecraft[0].dry_mass_kg = 120.0  # [kg]
    status = preset_status(back, back.presets[0])
    assert status["changed"] == [("dry_mass_kg", scenario.spacecraft[0].dry_mass_kg, 120.0)]
    assert status["kept"] == len(back.presets[0].values) - 1


def test_a_scenario_without_presets_writes_none():
    scenario = load_scenario(next(_TEMPLATES.glob("01_*.json")))
    assert "presets" not in scenario.to_dict() and "presets" not in scenario_text(scenario)
    assert "presets" not in output_provenance.scenario_record(scenario)
    assert "presets" not in RunProvenance("test", "2.12.0", "", "rk4", 1.0).to_dict()


@pytest.mark.parametrize(("change", "words"), [
    (lambda r: setattr(r, "spacecraft", "nobody"), "is not one of this scenario's spacecraft"),
    (lambda r: setattr(r, "preset", " "), "must name the preset"),
    (lambda r: setattr(r, "values", {"dry_mass_kg": "heavy"}), "must map field paths to finite numbers"),
])
def test_a_malformed_record_is_refused(change, words):
    scenario = _scenario_with_preset()
    change(scenario.presets[0])
    with pytest.raises(ScenarioValidationError, match=words):
        scenario.validate()


def test_a_record_follows_a_rename_and_is_listed_once():
    scenario = _scenario_with_preset()
    rename_spacecraft(scenario, "espa-1", "espa-2")
    assert scenario.presets[0].spacecraft == "espa-2"
    scenario.validate()
    scenario.presets.append(scenario.presets[0])
    with pytest.raises(ScenarioValidationError, match="names a spacecraft more than once"):
        scenario.validate()


def test_explain_and_the_provenance_record_the_preset():
    scenario = _scenario_with_preset()
    scenario.spacecraft[0].drag_area_m2 = 2.0  # [m^2]
    (record,) = preset_records(scenario)
    assert record["preset"] == SPACECRAFT_TEMPLATES[0].name and record["changed"][0]["path"] == "drag_area_m2"
    assert output_provenance.scenario_record(scenario)["presets"] == [record]
    (section,) = [s for s in explain(scenario).sections if s.title == "Computed and overridden values"]
    assert [b.label for b in section.badges] == ["1 from a preset"]
    (note,) = section.notes
    assert note.startswith(f"espa-1: from preset {SPACECRAFT_TEMPLATES[0].name}, {record['kept']} of "
                           f"{record['values']} values as it gave them; changed: drag_area_m2 ")
