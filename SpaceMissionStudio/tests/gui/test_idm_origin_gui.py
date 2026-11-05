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

"""The origin of the body frame at the centre of gravity, in the GUI
(decision IDM-31): the import dialog's choice, the 3D model editor moving
its model and the devices' mounts, and the spacecraft list and dialog
moving the rest of the spacecraft on the editor's OK. The models are the
synthetic fixture ``tests/data/idm`` (demosat)."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
from idm_fixtures import write_idm  # noqa: E402

pytestmark = pytest.mark.requires_gui

_TEMPLATE = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates" / \
    "06_attitude_pointing_basic.json"
_SHIFT = [0.1, -0.2, 0.3]  # [m] an origin moved by this much


def test_the_dialog_offers_the_origin_and_starts_from_the_last_one(qtbot, tmp_path):
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(write_idm(tmp_path / "demosat.idm"))
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.plan() is not None, timeout=30000)
    assert dialog.origin() == "element"
    assert [dialog.origin_combo.itemData(i) for i in range(dialog.origin_combo.count())] == ["element", "cog"]
    assert "centre of gravity" in dialog.origin_combo.toolTip()
    again = IdmImportDialog(write_idm(tmp_path / "again.idm"), origin="cog")
    qtbot.addWidget(again)
    qtbot.waitUntil(lambda: not again.busy() and again.plan() is not None, timeout=30000)
    assert again.origin() == "cog" and again.origin_combo.currentText() == "The centre of gravity"


def test_the_model_editor_moves_its_model_and_the_mounts(qtbot, tmp_path):
    """An import at the centre of gravity: the model's centre of gravity
    is at B, a sensor's mount (edited here) moves by the same amount,
    which origin_shift() hands to the spacecraft; a re-import with the
    choice the dialog then offers moves nothing more."""
    from spacemissionstudio import idm, idm_import
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog
    from spacemissionstudio.schema.scenario import MountConfig, SensorConfig

    sensor = SensorConfig(kind="imu", name="gyro", mount=MountConfig(position_m=[0.5, 0.0, 0.0]))
    devices = SimpleNamespace(sensors=[sensor], actuators=[], rf_link=None, comms_pointing=None)
    editor = ModelEditorDialog(None, spacecraft_name="sat-1", base_dir=tmp_path, devices=devices)
    qtbot.addWidget(editor)
    assert editor.origin_shift() is None
    plan = idm_import.plan(idm.load(write_idm(tmp_path / "demosat.idm")))
    summary = editor.import_idm(plan, origin="cog")
    shift = editor.origin_shift()
    assert shift == pytest.approx(summary.origin_moved_m) and np.linalg.norm(shift) > 0.1
    editor.recompute_now()
    assert np.allclose(editor.derived.mass_properties.center_of_mass_m, 0.0, rtol=0.0, atol=1e-6)
    assert editor.devices().sensors[0].mount.position_m == pytest.approx(list(np.asarray([0.5, 0.0, 0.0]) - shift))
    assert idm_import.recorded_origin(editor.import_record())[0] == "cog"
    again = editor.import_idm(idm_import.plan(idm.load(write_idm(tmp_path / "demosat.idm"))))
    assert not again.origin_moved_m and editor.origin_shift() == pytest.approx(shift)


def _editor(scenario, shift):
    """A 3D model editor's OK after an import that moved the origin by
    ``shift`` (its model already moved; the mounts as it holds them)."""
    sat = scenario.spacecraft[0]
    return SimpleNamespace(spacecraft_name=sat.name, model=lambda: sat.model, devices=lambda: None,
                           import_record=lambda: None, device_import=lambda: None, power_import=lambda: None,
                           origin_shift=lambda: list(shift))


def _with_hand_values(scenario):
    """The template's spacecraft with a model (as the editor hands it
    back), a facet and a gyro placed by hand, and a devices record of an
    earlier import placing the gyro."""
    from spacemissionstudio.schema.scenario import (FacetConfig, ImportRecord, ModelPartConfig, MountConfig,
                                                    SensorConfig, SpacecraftModelConfig)

    sat = scenario.spacecraft[0]
    sat.model = SpacecraftModelConfig(apply_facets=False, parts=[  # the facet below is the user's own
        ModelPartConfig(name="bus", shape="box", mass_kg=100.0, dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0})])
    sat.facets = [FacetConfig(name="hand", area_m2=1.0, normal_b=[0.0, 0.0, 1.0], location_b=[0.0, 0.0, 0.5])]
    sat.sensors = [SensorConfig(kind="imu", name="gyro", mount=MountConfig(position_m=[0.5, 0.0, 0.0]))]
    scenario.imports = [ImportRecord(sat.name, "devices", "idm_cic", "/x.idm", "0" * 64,
                                     {"sensors[gyro].mount.position_m[0]": 0.5, "sensors[gyro].kind": "imu"})]
    return sat


def test_the_spacecraft_list_moves_the_rest_on_the_editor_s_ok(qtbot, tmp_path):
    """From the spacecraft list: the facet and the gyro move by the shift,
    and the devices record is emitted moved, so a re-import compares like
    with like."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATE)
    _with_hand_values(scenario)
    widget = SpacecraftListWidget()
    qtbot.addWidget(widget)
    widget.from_list(scenario.spacecraft)
    widget.set_simulation_mode_provider(lambda: "full_attitude")
    widget.set_imports_provider(lambda: scenario.imports)
    records = []
    widget.import_recorded.connect(records.append)
    widget._apply_model_editor(_editor(scenario, _SHIFT))
    [sat] = widget.to_list()
    assert sat.facets[0].location_b == pytest.approx([-0.1, 0.2, 0.2])
    assert sat.sensors[0].mount.position_m == pytest.approx([0.4, 0.2, -0.3])
    [record] = records
    assert record.target == "devices" and record.values["sensors[gyro].mount.position_m[0]"] == pytest.approx(0.4)
    assert record.values["sensors[gyro].kind"] == "imu"


def test_a_spacecraft_dialog_moves_its_form_on_the_editor_s_ok(qtbot, tmp_path, monkeypatch):
    """From a spacecraft dialog: the facet table and the sensor list move
    by the shift, and its pending devices record is the moved one."""
    from spacemissionstudio.gui import spacecraft_editor
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

    monkeypatch.setattr(spacecraft_editor, "report", lambda *args, **kwargs: None)
    scenario = load_scenario(_TEMPLATE)
    sat = _with_hand_values(scenario)
    dialog = SpacecraftEditorDialog(config=sat, simulation_mode="full_attitude",
                                    imports_provider=lambda: scenario.imports)
    qtbot.addWidget(dialog)
    dialog._move_origin(_SHIFT)
    assert dialog.facet_table.to_list()[0].location_b == pytest.approx([-0.1, 0.2, 0.2])
    assert dialog.sensor_list.to_list()[0].mount.position_m == pytest.approx([0.4, 0.2, -0.3])
    [record] = dialog.pending_imports()
    assert record.values["sensors[gyro].mount.position_m[0]"] == pytest.approx(0.4)
