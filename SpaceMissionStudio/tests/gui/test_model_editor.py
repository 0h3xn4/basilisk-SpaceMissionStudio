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

"""Tests for the 3D model editor (gui.model_editor_dialog, gui.model_view_widget)
and its place in the spacecraft editor: building a model from shapes,
importing an .obj and a mass-properties file, the 3D view's contents, and
the spacecraft editor applying the model and keeping it on a re-edit."""

import json

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui


def _editor(qtbot, model=None, base_dir=None):
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    dialog = ModelEditorDialog(model, spacecraft_name="sat-1", base_dir=base_dir)
    qtbot.addWidget(dialog)
    return dialog


def test_adding_shapes_builds_the_model_and_the_view(qtbot):
    """Adding a prism (an octagon) and a panel gives two parts with their
    default sizes and masses; the result shows their total mass, and the
    3D view has one mesh per part plus the axes and the center of mass."""
    dialog = _editor(qtbot)
    bus = dialog.add_part("prism")
    dialog.add_part("panel")
    dialog.recompute_now()
    assert bus.sides == 8
    assert [p.name for p in dialog.model().parts] == ["prism", "panel"]
    assert "mass 86 kg" in dialog.mass_summary.text()
    names = [trace.name for trace in dialog.view.figure.data]
    assert names[:2] == ["prism", "panel"]
    assert "center of mass" in names and "x axis" in names
    assert "facets" in dialog.surfaces_label.text()


def test_editing_the_form_changes_the_selected_part(qtbot):
    """The part form writes into the selected part: a dimension, the
    position, the mass, a face left out; the selected part is drawn opaque
    and the others faded."""
    dialog = _editor(qtbot)
    dialog.add_part("box")
    dialog.add_part("box")
    w = dialog.part_widgets
    w["dim:x"].setValue(1.5)
    w["position_b_m"][2].setValue(0.75)
    w["mass_kg"].setValue(42.0)
    w["face:-z"].setChecked(False)
    dialog.recompute_now()
    part = dialog.model().parts[1]
    assert part.name == "box 2"
    assert part.dimensions_m["x"] == 1.5 and part.position_b_m == [0.0, 0.0, 0.75]
    assert part.mass_kg == 42.0 and part.excluded_faces == ["-z"]
    opacities = {t.name: t.opacity for t in dialog.view.figure.data if t.type == "mesh3d"}
    assert opacities == {"box": pytest.approx(0.35), "box 2": 1.0}


def test_duplicate_delete_and_rename(qtbot):
    """Duplicate gives a uniquely named copy; a name another part has, or
    one with '/', is refused; Delete removes the selected part."""
    dialog = _editor(qtbot)
    dialog.add_part("sphere")
    dialog.duplicate_part()
    assert [p.name for p in dialog.model().parts] == ["sphere", "sphere 2"]
    dialog.part_widgets["name"].setText("sphere")
    dialog.part_widgets["name"].editingFinished.emit()
    assert dialog.model().parts[1].name == "sphere 2"
    dialog.part_widgets["name"].setText("tank")
    dialog.part_widgets["name"].editingFinished.emit()
    assert dialog.model().parts[1].name == "tank"
    dialog.delete_part()
    assert [p.name for p in dialog.model().parts] == ["sphere"]


def test_importing_an_obj_adds_one_part_per_group(qtbot, tmp_path):
    """An .obj with two groups, in millimetres, copied beside the scenario:
    two mesh parts (mass 0 until set), the mesh stored by a relative path
    with its SHA-256, and drawn in metres."""
    from spacemissionstudio.model3d import obj_io, shapes

    source_dir = tmp_path / "cad"
    source_dir.mkdir()
    obj_io.write_obj(source_dir / "sat.obj", [
        obj_io.ObjGroup("body", shapes.mesh("box", {"x": 1000.0, "y": 800.0, "z": 600.0}), (0.9, 0.8, 0.1)),
        obj_io.ObjGroup("antenna", shapes.mesh("cone", {"base_diameter": 400.0, "height": 150.0}))])
    scenario_dir = tmp_path / "scenario"
    scenario_dir.mkdir()
    dialog = _editor(qtbot, base_dir=scenario_dir)
    names = dialog.import_obj(source_dir / "sat.obj", units="mm", copy_to_scenario=True)
    dialog.recompute_now()
    model = dialog.model()
    assert names == ["body", "antenna"]
    assert model.meshes[0].path == "models/sat.obj" and len(model.meshes[0].sha256) == 64
    assert (scenario_dir / "models" / "sat.mtl").is_file()
    assert [p.mass_kg for p in model.parts] == [0.0, 0.0]
    body = next(t for t in dialog.view.figure.data if t.name == "body")
    assert max(body.x) == pytest.approx(0.5)  # 1000 mm wide -> +-0.5 m
    assert model.parts[0].color == pytest.approx([0.9, 0.8, 0.1])


def test_mass_properties_typed_and_imported(qtbot, tmp_path):
    """Typed: the typed values become the model's mass properties. Imported:
    a JSON file sets the source to 'imported' and fills the values."""
    dialog = _editor(qtbot)
    dialog.add_part("box")
    dialog.recompute_now()
    dialog.source_buttons["typed"].setChecked(True)
    assert dialog.typed_group.isEnabled()
    dialog.typed_mass.setValue(55.0)
    dialog.typed_com[2].setValue(0.1)
    dialog.recompute_now()
    assert dialog.derived.mass_properties.mass_kg == 55.0
    np.testing.assert_allclose(dialog.derived.mass_properties.center_of_mass_m, [0.0, 0.0, 0.1])

    path = tmp_path / "mass.json"
    path.write_text(json.dumps({"mass_kg": 140.0, "center_of_mass_m": [0.0, 0.01, 0.2],
                                "inertia_kg_m2": [[20, 0, 0], [0, 21, 0], [0, 0, 15]]}))
    dialog.import_mass_properties(path)
    dialog.recompute_now()
    model = dialog.model()
    assert model.mass_properties_source == "imported"
    assert model.mass_properties.source_file == "mass.json"
    assert dialog.derived.mass_properties.mass_kg == 140.0
    assert not dialog.typed_group.isEnabled()


def test_spacecraft_editor_applies_the_model_and_keeps_it(qtbot, monkeypatch):
    """Through the 3D model tab: the model's mass, center of mass, full
    inertia (with products) and facets reach the spacecraft; the fields
    the model fills are locked; OK keeps the model and the products, and
    reopening and OK'ing again changes nothing (no data lost on re-edit)."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    model = SpacecraftModelConfig(parts=[
        ModelPartConfig(name="bus", shape="box", dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0}, mass_kg=100.0),
        ModelPartConfig(name="boom", shape="box", dimensions_m={"x": 0.1, "y": 0.1, "z": 1.0}, mass_kg=5.0,
                        position_b_m=[0.4, 0.4, 1.0])])
    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    dialog._model = model
    dialog._on_apply_model()
    config = dialog.to_dataclass()
    assert config.dry_mass_kg == pytest.approx(105.0)
    assert config.center_of_mass_b_m[2] == pytest.approx(5.0 / 105.0)
    assert config.inertia_kg_m2[1] != 0.0  # Ixy: the boom sits off both x and y
    assert len(config.facets) == 12
    assert not dialog.dry_mass_kg.isEnabled() and not dialog.facet_table.isEnabled()
    assert "match the model" in dialog.model_summary.text()

    again = SpacecraftEditorDialog(config=config)
    qtbot.addWidget(again)
    assert again.to_dataclass() == config


def test_hand_written_products_of_inertia_survive_a_re_edit(qtbot):
    """A spacecraft whose file has products of inertia keeps them after
    the dialog is opened and OK'd (the form edits only the moments)."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    config = SpacecraftConfig(name="sat-1", inertia_kg_m2=[20.0, -0.4, 0.1, -0.4, 22.0, 0.2, 0.1, 0.2, 15.0],
                              orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0],
                                            velocity_km_s=[0.0, 7.5, 0.0]))
    dialog = SpacecraftEditorDialog(config=config)
    qtbot.addWidget(dialog)
    assert dialog.products_label.isVisibleTo(dialog)
    assert dialog.to_dataclass().inertia_kg_m2 == config.inertia_kg_m2
