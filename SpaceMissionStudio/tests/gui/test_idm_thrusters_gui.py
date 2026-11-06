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

"""Thrusters in the GUI (decision IDM-32): the import dialog's row of a
thruster with a plume cone (added, along the model's axis, to the 3D
model's equipment), of one without (not added until ticked, and why), and
a spacecraft dialog putting the thruster on its model. The models are the
synthetic fixtures ``tests/data/idm/axessat`` and ``devicesat``."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
from idm_fixtures import model_xml, write_idm  # noqa: E402

pytestmark = pytest.mark.requires_gui

_TEMPLATE = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates" / \
    "06_attitude_pointing_basic.json"


def _dialog(qtbot, tmp_path, fixture):
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(write_idm(tmp_path / f"{fixture}.idm", model_xml(fixture)))
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.plan() is not None, timeout=30000)
    return dialog


def _row(dialog, equipment) -> int:
    table = dialog.devices_table
    return next(r for r in range(table.rowCount()) if table.item(r, 1).text() == equipment)


def test_a_thruster_with_a_plume_cone_goes_to_the_model(qtbot, tmp_path):
    """Ticked, along the model's axis, its plume in the tooltip; no
    product: no thrust, and a product's thrust once one is chosen."""
    dialog = _dialog(qtbot, tmp_path, "axessat")
    table = dialog.devices_table
    row = _row(dialog, "Thruster 2")
    assert table.cellWidget(row, 0).isChecked() and table.cellWidget(row, 0).isEnabled()
    axis = table.cellWidget(row, 4)
    assert axis.currentData() == "model"
    assert "the plume cone 'Plume', against the plume (plume half-angle 26.565 deg)" in axis.toolTip()  # [deg] half of 53.1301
    product = table.cellWidget(row, 5)
    assert product.itemText(0) == "None (no thrust)"
    assert table.item(row, 6).text() == "to the 3D model's equipment; thrust: none (the authority matrix takes it " \
                                        "per newton)"
    product.setCurrentIndex(1)
    assert table.item(row, 6).text() == f"to the 3D model's equipment; thrust: {product.currentData()}"
    choice = dialog.device_choices()[row]
    assert (choice.add, choice.kind, choice.axis, choice.product) == (True, "thruster", "model",
                                                                     product.currentData())


def test_a_thruster_without_a_plume_cone_waits_for_an_axis(qtbot, tmp_path):
    """Not ticked, but it can be; the note says why it is not added and
    the tooltip that its shapes show no plume cone."""
    dialog = _dialog(qtbot, tmp_path, "devicesat")
    table = dialog.devices_table
    row = _row(dialog, "Thruster 1N")
    add = table.cellWidget(row, 0)
    assert not add.isChecked() and add.isEnabled()
    assert table.item(row, 6).text().startswith("not added: its direction is not in its shapes (no plume cone)")
    assert "no plume cone" in table.cellWidget(row, 4).toolTip()
    add.setChecked(True)
    assert table.item(row, 6).text().startswith("to the 3D model's equipment; thrust: ")
    assert dialog.device_choices()[row].add


def test_a_spacecraft_dialog_puts_the_thruster_on_its_model(qtbot, tmp_path, monkeypatch):
    """The devices chosen, from the 3D model editor's OK: the thruster
    joins the dialog's model, the sensors its list, and the pending
    devices record keeps the thruster's values."""
    from spacemissionstudio import idm, idm_devices, idm_import
    from spacemissionstudio.gui import spacecraft_editor
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    messages = []
    monkeypatch.setattr(spacecraft_editor, "report", lambda _parent, text, **_kw: messages.append(text))
    scenario = load_scenario(_TEMPLATE)
    sat = scenario.spacecraft[0]
    sat.model = SpacecraftModelConfig(apply_facets=False, parts=[
        ModelPartConfig(name="bus", shape="box", mass_kg=100.0, dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0})])
    dialog = SpacecraftEditorDialog(config=sat, simulation_mode="full_attitude", imports_provider=lambda: [])
    qtbot.addWidget(dialog)
    plan = idm_import.plan(idm.load(write_idm(tmp_path / "axessat.idm", model_xml("axessat"))))
    dialog._add_imported_devices(plan, idm_devices.default_choices(plan.devices))
    assert [e.name for e in dialog._model.equipment] == ["Thruster 2 nozzle"]
    assert "Star tracker optical head" in [s.name for s in dialog.sensor_list.to_list()]
    record = dialog.pending_imports()[-1]
    assert record.target == "devices"
    assert record.values["model.equipment[Thruster 2 nozzle].mount.boresight[2]"] == 1.0
    assert "Added 1 thruster(s) to the 3D model's equipment: Thruster 2 nozzle." in messages[-1]
    assert [e.name for e in dialog.to_dataclass().model.equipment] == ["Thruster 2 nozzle"]
