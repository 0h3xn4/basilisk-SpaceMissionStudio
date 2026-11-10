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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Importing an IDM-CIC model into a spacecraft's 3D model
(``spacemissionstudio.idm_import``, ``idm-import``, ``idm-info``): the
parts, point masses and stowed poses in the body frame, the mass
properties against hand calculations, provenance, and re-import rules
(match on fullId, update only what the file set, keep the user's edits,
flag what is gone). The fixture is synthetic (``tests/data/idm``).

Hand calculations for the demosat fixture, defaults (no configuration):
the bus box 20 kg centred at (0, 0, 0.25); the wing 2 kg, its plate's
centre 0.5 m out from the hinge at (0.5, 0, 0.25) and 0.01 m up, so at
(1.0, 0, 0.26), and at launch turned 90 deg about y: (0.51, 0, -0.25);
the computer 3.5 kg at its frame (0.2, 0, 0.1) plus its 0.05 m centre of
gravity: (0.2, 0, 0.15); two pointers of 0.25 kg each with the centre of
gravity 0.1 m along their x: turned Rx(90) Ry(90) (intrinsic) to
(0, 0.1, 0), and turned Rz(90) after a rotation-first translation
(0, 0.1, 0) to (-0.1, 0.1, 0); the tank's wall 1.2 kg and 0.5 x 12 kg of
propellant, both centred at (0, 0, 0.15); the bracket's block
0.1^3 m^3 x 2700 kg/m^3 = 2.7 kg at (-0.35, 0.25, 0.35) and its sheet
1 x 2 m^2 x 0.5 kg/m^2 = 1 kg at (0.1, 1.2, 0.4); the plate with a hole
1 kg, 0.4 x 0.4 x 0.05 m less a 0.1 m radius cylinder centred 0.05 m off
x, at (-0.05 pi 0.01 0.05 / V, 0, -0.025) with V = 0.008 - pi 0.01 0.05;
the lens 0.8 kg at (0.1, 0, 0.65). 38.7 kg in all. The optional spare
battery (1 kg) only at launch; the jig element is not mounted on the bus.
"""

import copy
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest
from idm_fixtures import model_xml, write_idm

from spacemissionstudio import cli, idm, idm_import
from spacemissionstudio.engine.scenario_checks import scenario_warnings
from spacemissionstudio.model3d import model as model3d
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import Scenario, SpacecraftModelConfig, import_status

_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "spacemissionstudio" / "scenarios" / "two_body_validation.json"
_HOLE_VOLUME = 0.008 - math.pi * 0.01 * 0.05  # [m^3]
_POINTS = {  # [kg], [m]: each mass and where it is, defaults (module docstring)
    "Body box": (20.0, (0.0, 0.0, 0.25)), "Wing": (2.0, (1.0, 0.0, 0.26)), "Computer": (3.5, (0.2, 0.0, 0.15)),
    "Pointer": (0.25, (0.0, 0.1, 0.0)), "Pointer 2": (0.25, (-0.1, 0.1, 0.0)),
    "Propellant tank": (1.2, (0.0, 0.0, 0.15)), "Propellant tank propellant": (6.0, (0.0, 0.0, 0.15)),
    "Bracket Block": (2.7, (-0.35, 0.25, 0.35)), "Bracket Sheet": (1.0, (0.1, 1.2, 0.4)),
    "Plate with hole": (1.0, (-0.05 * math.pi * 0.01 * 0.05 / _HOLE_VOLUME, 0.0, -0.025)),
    "Lens": (0.8, (0.1, 0.0, 0.65)),
}


def _model(tmp_path, text=None):
    return idm.load(write_idm(tmp_path / "demosat.idm", text))


def _scenario(tmp_path) -> Path:
    path = tmp_path / "scenario.json"
    shutil.copyfile(_SOURCE, path)
    return path


def _items(plan) -> dict:
    return {item.base_name: item for item in plan.parts + plan.equipment}


def test_the_plan_places_every_part_in_the_body_frame(tmp_path):
    """Parts and point masses where the hand calculation puts them; the
    massless field-of-view cone left out; the jig's element left out."""
    plan = idm_import.plan(_model(tmp_path))
    s = plan.summary
    assert (s.body_element, s.elements) == ("Bus", ["Bus", "Camera"])
    assert s.left_out == [("Ground jig", "not mounted on Bus")]
    assert s.mass_kg == pytest.approx(38.7) and s.propellant_kg == 6.0
    items = _items(plan)
    assert "Bracket Keep-out zone" not in items
    body = items["Body box"].config
    assert (body.shape, body.dimensions_m, body.position_b_m, body.mass_kg) == (
        "box", {"x": 1.0, "y": 0.8, "z": 0.5}, [0.0, 0.0, 0.25], 20.0)
    assert body.source_id == "el.1_ss.STR_eqi.1-1_sh.1" and body.subsystem == "Structure"
    assert items["Wing"].config.position_b_m == [1.0, 0.0, 0.26]
    lens = items["Lens"].config
    assert (lens.shape, lens.position_b_m, lens.dimensions_m) == ("cylinder", [0.1, 0.0, 0.65],
                                                                 {"diameter": 0.1, "height": 0.1})
    assert items["Computer"].config.mount.position_m == [0.2, 0.0, 0.15]
    pointers = sorted(i.config.mount.position_m for i in plan.equipment if i.base_name == "Pointer")
    assert np.allclose(pointers, [[-0.1, 0.1, 0.0], [0.0, 0.1, 0.0]])
    assert items["Bracket Sheet"].config.distribution == "shell" and items["Bracket Sheet"].config.mass_kg == 1.0
    assert items["Bracket Block"].config.mass_kg == pytest.approx(2.7)
    assert set(plan.groups) == {"el.1_ss.STR_eq.5_sh.1", "el.1_ss.STR_eq.5_sh.1_propellant",
                                "el.1_ss.STR_eq.7_sh.2", "el.1_ss.STR_eq.8_sh.1"}
    reasons = " | ".join(s.approximations)
    assert "hidden by default" in reasons and "manual inertia" in reasons and "Boolean" in reasons
    assert ("Wing", "Level_B", 0.2) in s.margins


def test_a_configuration_sets_the_optional_units_fillings_and_stowed_poses(tmp_path):
    model = _model(tmp_path)
    launch = idm_import.plan(model, "LCH")
    assert launch.summary.mass_kg == pytest.approx(38.7 + 1.0 + 6.0) and launch.summary.propellant_kg == 12.0
    assert "Spare battery" in _items(launch) and launch.summary.left_out == [("Ground jig",
                                                                               "not enabled in this configuration")]
    plan = idm_import.plan(model, "OPS", stowed_configuration="Launch")
    wing = _items(plan)["Wing"]
    position, rotation = plan.stowed[wing.source_id]
    assert np.allclose(position, [0.51, 0.0, -0.25]) and np.allclose(rotation, [0.0, 90.0, 0.0])
    assert set(plan.stowed) == {wing.source_id}  # nothing else moves
    with pytest.raises(idm.IdmError, match="no element 'Nope'"):
        idm_import.plan(model, body_element="Nope")
    assert idm_import.plan(model, body_element="Ground jig").summary.elements == ["Ground jig"]


def test_the_merged_model_gives_the_hand_calculated_mass_properties(tmp_path):
    """Written into a scenario: the meshes beside it, the parts and point
    masses, the applied mass and centre of mass, a valid scenario."""
    path = _scenario(tmp_path)
    scenario = load_scenario(path)
    summary = idm_import.merge(scenario, "sat-1", idm_import.plan(_model(tmp_path)), path)
    scenario.validate()
    sc = scenario.spacecraft[0]
    assert (tmp_path / "models" / "sat-1_idm.obj").is_file() and sc.model.meshes[0].path == "models/sat-1_idm.obj"
    assert len(summary.added) == len(_POINTS) and not summary.updated
    derived = model3d.derive(sc.model, tmp_path)
    assert derived.errors == []
    total = sum(m for m, _ in _POINTS.values())
    center = sum(m * np.asarray(r) for m, r in _POINTS.values()) / total
    assert derived.mass_properties.mass_kg == pytest.approx(38.7)
    assert np.allclose(derived.mass_properties.center_of_mass_m, center, atol=1e-9)
    assert sc.dry_mass_kg == pytest.approx(38.7) and np.allclose(sc.center_of_mass_b_m, center, atol=1e-9)
    assert sc.model.apply_facets is False and not any(p.in_surface_model for p in sc.model.parts)


def test_the_import_is_recorded_with_its_source_and_saved_only_when_set(tmp_path):
    """The record: the file, its SHA-256, the configuration and version,
    and each imported value keyed by the source object's fullId; a
    scenario without an import saves without source_id or details."""
    path = _scenario(tmp_path)
    plain = json.loads(path.read_text())
    assert "source_id" not in json.dumps(Scenario.from_dict(plain).to_dict())
    model = _model(tmp_path)
    scenario = load_scenario(path)
    idm_import.merge(scenario, "sat-1", idm_import.plan(model, "OPS"), path)
    (record,) = scenario.imports
    assert (record.target, record.format, record.sha256) == ("model", "idm_cic", model.sha256)
    assert record.source == str(model.path)
    assert record.details["configuration"] == "OPS (Operations)" and record.details["model_version"] == "3.4.1.1"
    assert record.values["model.parts[el.1_ss.STR_eqi.1-1_sh.1].mass_kg"] == 20.0
    assert record.values["model.equipment[el.1_ss.STR_eqi.3-1].mount.position_m[2]"] == 0.15
    assert import_status(scenario, record)["changed"] == []
    again = Scenario.from_dict(json.loads(json.dumps(scenario.to_dict())))
    again.validate()
    assert again.imports[0].details == record.details and again.spacecraft[0].model.parts[0].source_id


def _reimport(tmp_path, text, scenario, path):
    model = idm.load(write_idm(tmp_path / "demosat.idm", text))
    return idm_import.merge(scenario, "sat-1", idm_import.plan(model), path)


def test_a_reimport_updates_what_the_file_set_keeps_edits_and_flags_what_is_gone(tmp_path):
    """Matched by fullId: the wing's new mass is taken; the body box's
    mass the user edited is kept, its new size taken; a renamed part keeps
    its name; the computer gone from the file stays, flagged, and is a
    pre-run warning; values never imported are not touched."""
    path = _scenario(tmp_path)
    scenario = load_scenario(path)
    _reimport(tmp_path, None, scenario, path)
    model = scenario.spacecraft[0].model
    parts = {p.source_id: p for p in model.parts}
    parts["el.1_ss.STR_eqi.1-1_sh.1"].mass_kg = 25.0  # the user's edit
    parts["el.2_ss.PAY_assi.2-1_eqi.1-1_sh.1"].name = "Main lens"  # a rename
    parts["el.1_ss.STR_eqi.1-1_sh.1"].material = "aluminium_6061_t6"  # never imported
    text = model_xml()
    text = text.replace("<massTotal>2</massTotal>", "<massTotal>3</massTotal>", 1)  # the wing
    text = text.replace("<d1>1</d1>\n<d2>0,8</d2>", "<d1>1,2</d1>\n<d2>0,8</d2>", 1)  # the body box, longer
    start = text.index('<EquipmentInstance id="3-1"')
    text = text[:start] + text[text.index("</EquipmentInstance>", start) + len("</EquipmentInstance>"):]
    summary = _reimport(tmp_path, text, scenario, path)
    scenario.validate()
    parts = {p.source_id: p for p in model.parts}
    body = parts["el.1_ss.STR_eqi.1-1_sh.1"]
    assert body.mass_kg == 25.0 and body.dimensions_m["x"] == 1.2 and body.material == "aluminium_6061_t6"
    assert parts["el.1_ss.STR_eqi.2-1_sh.1"].mass_kg == 3.0
    assert parts["el.2_ss.PAY_assi.2-1_eqi.1-1_sh.1"].name == "Main lens"
    assert ("Body box", "mass") in summary.kept and "Wing" in summary.updated and "Body box" in summary.updated
    assert summary.gone == ["Computer"] and any(e.name == "Computer" for e in model.equipment)
    rules = [w.rule_id for w in scenario_warnings(scenario)]
    assert "import.source_item_gone" in rules
    status = import_status(scenario, scenario.imports[0])
    assert [path for path, _, _ in status["changed"]] == ["model.parts[el.1_ss.STR_eqi.1-1_sh.1].mass_kg"]
    assert model3d.derive(model, tmp_path).errors == []
    unchanged = _reimport(tmp_path, text, scenario, path)
    assert unchanged.added == [] and unchanged.updated == [] and unchanged.unchanged > 0


def test_an_import_that_fails_changes_nothing(tmp_path, monkeypatch):
    """The meshes file cannot be written (a read-only folder): the import
    raises and leaves the spacecraft, its model object and the import
    records as they were, so no part names a mesh file that was not
    written (the 3D model editor then refused its OK with "mesh_index must
    name one of the model's 0 mesh file(s)")."""
    path = _scenario(tmp_path)
    scenario = load_scenario(path)
    sc = scenario.spacecraft[0]
    before = copy.deepcopy(sc)
    imports = list(scenario.imports)

    def refuse(*_args, **_kwargs):
        raise PermissionError(13, "Permission denied", str(tmp_path / "models"))

    monkeypatch.setattr(idm_import, "write_obj", refuse)
    with pytest.raises(PermissionError):
        idm_import.merge(scenario, "sat-1", idm_import.plan(_model(tmp_path)), path)
    assert sc == before and scenario.imports == imports
    assert not (tmp_path / "models").exists() or not any((tmp_path / "models").iterdir())

    holder_model = SpacecraftModelConfig(parts=[])  # an editor's model object keeps its identity
    sc.model = holder_model
    with pytest.raises(PermissionError):
        idm_import.merge(scenario, "sat-1", idm_import.plan(_model(tmp_path)), path)
    assert sc.model is holder_model and holder_model.parts == [] and holder_model.meshes == []


def test_a_gone_mesh_part_keeps_its_mesh(tmp_path):
    """The meshes file is rewritten with the groups the kept parts still
    use, so a part the file no longer has still draws and weighs."""
    path = _scenario(tmp_path)
    scenario = load_scenario(path)
    _reimport(tmp_path, None, scenario, path)
    text = model_xml()
    start = text.index('<EquipmentInstance id="8-1"')
    text = text[:start] + text[text.index("</EquipmentInstance>", start) + len("</EquipmentInstance>"):]
    summary = _reimport(tmp_path, text, scenario, path)
    assert summary.gone == ["Plate with hole"]
    derived = model3d.derive(scenario.spacecraft[0].model, tmp_path)
    assert derived.errors == [] and derived.mass_properties.mass_kg == pytest.approx(38.7)


def test_an_unsupported_version_is_read_with_a_note(tmp_path):
    model = _model(tmp_path, model_xml().replace('version="3.4.1.1"', 'version="2.9"'))
    assert any("version 2.9" in note for note in model.notes)
    assert any("version 2.9" in note for note in idm_import.plan(model).summary.notes)


def test_names_are_made_valid_and_unique():
    assert idm_import.safe_name("M1.2: mirror / support") == "M1-2- mirror - support"
    assert idm_import.safe_name("  ") == "part" and idm_import.safe_name("con") == "con 1"
    taken = {"Panel"}
    assert idm_import.unique_name("Panel", taken) == "Panel 2" and "Panel 2" in taken
    assert len(idm_import.safe_name("x" * 100)) == 64


def test_the_commands_list_and_import_a_model(tmp_path, capsys):
    """idm-info writes nothing and lists the elements; idm-import saves
    the scenario through the change history; errors exit 1 with the
    reason."""
    source = write_idm(tmp_path / "demosat.idm")
    assert cli.main(["idm-info", str(source)]) == 0
    out = capsys.readouterr().out
    assert "element 1: Bus" in out and "mounted on Bus" in out and "OPS (Operations)" in out
    scenario = _scenario(tmp_path)
    out_path = tmp_path / "out.json"
    assert cli.main(["idm-import", str(source), str(scenario), "--spacecraft", "sat-1", "--configuration", "OPS",
                     "--stowed-configuration", "LCH", "--out", str(out_path)]) == 0
    assert "3D model imported" in capsys.readouterr().out
    saved = load_scenario(out_path)
    assert saved.imports[0].details["stowed_configuration"] == "LCH (Launch)"
    assert len(saved.spacecraft[0].model.stowed) == 1 and (tmp_path / "models" / "sat-1_idm.obj").is_file()
    assert cli.main(["idm-import", str(tmp_path / "none.idm"), str(scenario), "--spacecraft", "sat-1"]) == 1
    assert "could not read" in capsys.readouterr().err
    assert cli.main(["idm-import", str(source), str(scenario), "--spacecraft", "nobody"]) == 1
    assert cli.main(["idm-info", str(source), "--configuration", "X"]) == 1
    assert "no configuration 'X'" in capsys.readouterr().err
