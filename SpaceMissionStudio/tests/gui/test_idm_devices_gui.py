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

"""The devices an IDM-CIC import finds, in the GUI: the import dialog's
**Devices found** table (add, axis, catalog product, why not), and the
devices chosen reaching the spacecraft through the 3D model editor's OK,
from the spacecraft list and from a spacecraft dialog. The model is the
synthetic fixture ``tests/data/idm/devicesat``."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
from idm_fixtures import model_xml, write_idm  # noqa: E402

pytestmark = pytest.mark.requires_gui

_TEMPLATE = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates" / \
    "06_attitude_pointing_basic.json"


def _dialog(qtbot, tmp_path, devices_allowed=True):
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(write_idm(tmp_path / "devicesat.idm", model_xml("devicesat")),
                             devices_allowed=devices_allowed)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.plan() is not None, timeout=30000)
    return dialog


def _rows(dialog) -> dict:
    table = dialog.devices_table
    return {table.item(row, 1).text(): row for row in range(table.rowCount())}


def test_the_dialog_lists_the_devices_found_with_their_choices(qtbot, tmp_path):
    """One row per device found: the sensors and the magnetorquer named
    after a product are ticked; a wheel without a product cannot be ticked
    until one is chosen; a battery is listed only; the choices returned are
    those shown, with the axis and product picked."""
    dialog = _dialog(qtbot, tmp_path)
    rows, table = _rows(dialog), dialog.devices_table
    assert len(rows) == 11
    assert table.cellWidget(rows["Gyro unit"], 0).isChecked()
    assert table.cellWidget(rows["Magnétocoupleur Z MTQ800"], 0).isChecked()
    wheel = rows["Reaction Wheel X"]
    assert not table.cellWidget(wheel, 0).isEnabled() and "u_max" in table.item(wheel, 6).text()
    table.cellWidget(wheel, 5).setCurrentIndex(1)  # a catalog wheel
    assert table.cellWidget(wheel, 0).isEnabled()
    table.cellWidget(wheel, 0).setChecked(True)
    table.cellWidget(wheel, 4).setCurrentText("-z")
    battery = rows["Battery pack"]
    assert not table.cellWidget(battery, 0).isEnabled() and "capacity" in table.item(battery, 6).text()
    choices = dict(zip(rows, dialog.device_choices()))
    assert choices["Reaction Wheel X"].add and choices["Reaction Wheel X"].axis == "-z"
    assert choices["Reaction Wheel X"].product == table.cellWidget(wheel, 5).currentData()
    assert not choices["Battery pack"].add
    assert table.item(rows["Gyro unit"], 6).text() == "values: Basilisk's defaults until set"


def test_an_orbit_only_scenario_lists_the_devices_without_adding_them(qtbot, tmp_path):
    """Orbit only: the devices are listed, none can be ticked, and the
    dialog says why."""
    dialog = _dialog(qtbot, tmp_path, devices_allowed=False)
    assert "orbit only" in dialog.devices_note.text()
    assert not any(choice.add for choice in dialog.device_choices())
    assert not any(dialog.devices_table.cellWidget(row, 0).isEnabled()
                   for row in range(dialog.devices_table.rowCount()))


def _editor_result(tmp_path, scenario):
    """What a 3D model editor's OK hands over after an import with the
    default device choices: its model, devices, record and device import."""
    from spacemissionstudio import idm, idm_devices, idm_import

    plan = idm_import.plan(idm.load(write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))))
    sat = scenario.spacecraft[0]
    idm_import.merge(scenario, sat.name, plan, tmp_path / "scenario.json")
    record = next(r for r in scenario.imports if r.target == "model")
    return SimpleNamespace(spacecraft_name=sat.name, model=lambda: sat.model, devices=lambda: None,
                           import_record=lambda: record,
                           device_import=lambda: (plan, idm_devices.default_choices(plan.devices)),
                           power_import=lambda: None)


def test_the_spacecraft_list_adds_the_devices_on_the_editor_s_ok(qtbot, tmp_path):
    """The 3D model editor's OK, from the spacecraft list: the devices
    chosen join the spacecraft, the magnetorquer it cannot take is left
    out, and both import records (model, devices) are emitted."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATE)
    widget = SpacecraftListWidget()
    qtbot.addWidget(widget)
    widget.from_list(scenario.spacecraft)
    widget.set_simulation_mode_provider(lambda: "full_attitude")
    records = []
    widget.import_recorded.connect(records.append)
    widget._apply_model_editor(_editor_result(tmp_path, scenario))
    [sat] = widget.to_list()
    assert [d.name for d in sat.sensors] == ["Star tracker head ST200", "Coarse sun sensor +X", "Gyro unit",
                                             "Magnetometer 1"]
    assert sat.actuators == []
    assert [r.target for r in records] == ["model", "devices"]
    assert set(records[1].details) == {f"sensors[{d.name}]" for d in sat.sensors}


def test_a_spacecraft_dialog_adds_the_devices_to_its_lists(qtbot, tmp_path, monkeypatch):
    """The 3D model editor's OK, from a spacecraft dialog: the devices
    chosen join its Sensors list, and its pending imports hold the devices
    record."""
    from spacemissionstudio.gui import spacecraft_editor
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

    reported = []
    monkeypatch.setattr(spacecraft_editor, "report", lambda widget, text, kind="error": reported.append(text))
    scenario = load_scenario(_TEMPLATE)
    dialog = SpacecraftEditorDialog(config=scenario.spacecraft[0], simulation_mode="full_attitude")
    qtbot.addWidget(dialog)
    editor = _editor_result(tmp_path, scenario)
    dialog._add_imported_devices(*editor.device_import())
    assert [d.name for d in dialog.sensor_list.to_list()] == ["Star tracker head ST200", "Coarse sun sensor +X",
                                                             "Gyro unit", "Magnetometer 1"]
    assert [r.target for r in dialog.pending_imports()] == ["devices"]
    assert reported and reported[0].startswith("Added 4 device(s) found in the IDM-CIC model")
    assert "Magnétocoupleur Z MTQ800 (the spacecraft cannot take it as it is" in reported[0]
