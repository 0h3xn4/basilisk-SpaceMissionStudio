#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""Imported values with their source and hash (transparency plan, Phase
8c): ``ccsds-import`` records the file, its SHA-256 and the values read;
a mass properties file is kept with its path; a file changed or moved
since is a pre-run warning; the records follow a renamed spacecraft, are
saved only when there are some, and go into the run's provenance."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from spacemissionstudio import cli
from spacemissionstudio.engine.scenario_checks import scenario_warnings
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.references import rename_spacecraft
from spacemissionstudio.schema.scenario import (ImportRecord, ModelMassPropertiesConfig, ScenarioValidationError,
                                                SpacecraftModelConfig, import_records, import_status)

_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "spacemissionstudio" / "scenarios" / "two_body_validation.json"
_OMM = Path(__file__).resolve().parent / "data" / "ccsds" / "omm_g7.txt"


def _imported(tmp_path):
    """two_body_validation with sat-1's orbit read from a copy of an OMM."""
    message = tmp_path / "orbit.omm"
    shutil.copyfile(_OMM, message)
    out = tmp_path / "imported.json"
    assert cli.main(["ccsds-import", str(message), str(_SOURCE), "--spacecraft", "sat-1", "--out", str(out)]) == 0
    return load_scenario(out), message, out


def _rules(scenario) -> list[str]:
    return [w.rule_id for w in scenario_warnings(scenario) if w.rule_id.startswith("import.")]


def test_ccsds_import_records_the_file_its_hash_and_the_values(tmp_path):
    """The record: the spacecraft, what was set, the format, the file's
    absolute path and SHA-256, and the values as read (the TLE's lines
    too); a second import of the same orbit replaces it."""
    scenario, message, out = _imported(tmp_path)
    (record,) = scenario.imports
    assert (record.spacecraft, record.target, record.format) == ("sat-1", "orbit", "ccsds_omm")
    assert record.source == str(message.resolve())
    assert record.sha256 == hashlib.sha256(message.read_bytes()).hexdigest()
    assert record.values["orbit.tle_line2"] == scenario.spacecraft[0].orbit.tle_line2 and record.time_utc
    assert import_status(scenario, record) == {"source": "unchanged", "kept": len(record.values), "changed": []}
    assert _rules(scenario) == []
    assert cli.main(["ccsds-import", str(message), str(out), "--spacecraft", "sat-1"]) == 0
    assert len(load_scenario(out).imports) == 1


def test_a_changed_or_missing_file_is_a_pre_run_warning(tmp_path):
    """The file changed since: import.source_changed; gone:
    import.source_missing; the values are still those imported."""
    scenario, message, _out = _imported(tmp_path)
    message.write_text(message.read_text() + "COMMENT edited later\n")
    found = [w for w in scenario_warnings(scenario) if w.rule_id == "import.source_changed"]
    assert len(found) == 1 and "sat-1's orbit was imported from" in found[0] and "has changed since" in found[0]
    assert found[0].actual == "the file's SHA-256 differs"
    message.unlink()
    assert _rules(scenario) == ["import.source_missing"]
    assert import_records(scenario)[0]["source_now"] == "missing"


def test_the_values_edited_since_are_recorded(tmp_path):
    """An edit after the import: the record keeps the values read, the
    status names each value changed, the provenance records both."""
    scenario, _message, _out = _imported(tmp_path)
    line2 = scenario.spacecraft[0].orbit.tle_line2
    scenario.spacecraft[0].orbit.tle_line2 = line2[:-1] + str((int(line2[-1]) + 1) % 10)
    status = import_status(scenario, scenario.imports[0])
    assert status["changed"] == [("orbit.tle_line2", line2, scenario.spacecraft[0].orbit.tle_line2)]
    (provenance,) = import_records(scenario)
    assert provenance["source_now"] == "unchanged" and provenance["changed"][0]["imported"] == line2


def test_the_records_follow_the_spacecraft_and_are_saved_only_when_there_are_some(tmp_path):
    """A rename takes the record along; a scenario without imports saves
    as before (no "imports" key); a record of no spacecraft is refused."""
    scenario, _message, _out = _imported(tmp_path)
    rename_spacecraft(scenario, "sat-1", "sat-a")
    assert scenario.imports[0].spacecraft == "sat-a"
    scenario.validate()
    plain = load_scenario(_SOURCE)
    assert "imports" not in plain.to_dict() and "imports" in scenario.to_dict()
    scenario.imports.append(ImportRecord("nobody", "orbit", "ccsds_opm", "/x.opm", "0" * 64))
    with pytest.raises(ScenarioValidationError, match="not one of this scenario's spacecraft"):
        scenario.validate()


def test_a_mass_properties_file_is_kept_with_its_path(tmp_path):
    """The import keeps the file's absolute path with its name and SHA-256;
    a later change of the file is the same warning; the path is written
    only when there is one, so a scenario's file is as before."""
    from spacemissionstudio.model3d.mass_import import read_mass_properties

    path = tmp_path / "mass.json"
    path.write_text(json.dumps({"mass_kg": 12.0, "center_of_mass_m": [0.0, 0.0, 0.1],
                                "inertia_kg_m2": [[1.0, 0, 0], [0, 2.0, 0], [0, 0, 3.0]]}))
    config, _notes = read_mass_properties(path)
    assert (config.source_file, config.source_path) == ("mass.json", str(path.resolve()))
    scenario = load_scenario(_SOURCE)
    scenario.spacecraft[0].model = SpacecraftModelConfig(mass_properties_source="imported", mass_properties=config)
    assert _rules(scenario) == [] and import_records(scenario)[0]["target"] == "model.mass_properties"
    path.write_text(path.read_text() + " ")
    assert _rules(scenario) == ["import.source_changed"]
    typed = ModelMassPropertiesConfig(mass_kg=12.0)
    scenario.spacecraft[0].model = SpacecraftModelConfig(mass_properties_source="typed", mass_properties=typed)
    assert "source_path" not in scenario.to_dict()["spacecraft"][0]["model"]["mass_properties"]
    assert import_records(scenario) == []


@pytest.mark.requires_basilisk
def test_a_run_records_the_imports(tmp_path):
    """The run's provenance lists each import with the file's state when
    the run started."""
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema.scenario import SimSettings

    scenario, _message, _out = _imported(tmp_path)
    scenario.sim_settings = SimSettings(duration_days=0.01)  # [day]
    provenance = SimulationService(scenario).run().provenance.to_dict()
    assert provenance["imports"] == import_records(scenario)
    assert "imports" not in SimulationService(load_scenario(_SOURCE)).nominal_provenance().to_dict()
