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

"""The import dialog's **Properties** tab: one row per property name on
the devices found, mapped to a value with its unit; the devices' rows and
the battery choice follow the mapping. The model is the synthetic fixture
``tests/data/idm/powersat``."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
from idm_fixtures import model_xml, write_idm  # noqa: E402

pytestmark = pytest.mark.requires_gui


def _dialog(qtbot, tmp_path, mappings=None):
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(write_idm(tmp_path / "powersat.idm", model_xml("powersat")), mappings=mappings)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.plan() is not None, timeout=30000)
    return dialog


def _rows(table, column=0) -> dict:
    return {table.item(row, column).text(): row for row in range(table.rowCount())}


def _map(dialog, name, target, unit=None):
    table = dialog.properties_table
    row = _rows(table)[name]
    use = table.cellWidget(row, 4)
    use.setCurrentIndex(use.findData(target))
    if unit is not None:
        unit_combo = table.cellWidget(row, 5)
        unit_combo.setCurrentIndex(unit_combo.findData(unit))
    return row


def test_mapping_the_wheel_s_properties_lets_it_be_added(qtbot, tmp_path):
    """Each property on the devices is a row; a wheel cannot be added
    until its torque and inertia are mapped with their units, then it is
    ticked and says its values come from its properties; the mapping
    returned is the one shown."""
    dialog = _dialog(qtbot, tmp_path)
    table, devices = dialog.properties_table, dialog.devices_table
    assert set(_rows(table)) == {"Max torque", "Wheel inertia", "Speed range", "Field of view", "ARW", "Capacity"}
    wheel = _rows(devices, 1)["Reaction Wheel X"]
    assert not devices.cellWidget(wheel, 0).isEnabled()
    row = _map(dialog, "Max torque", "reaction_wheel.u_max")
    assert table.cellWidget(row, 5).currentData() == "" and "choose the unit" in table.item(row, 6).text()
    _map(dialog, "Max torque", "reaction_wheel.u_max", "mN*m")
    _map(dialog, "Wheel inertia", "reaction_wheel.Js", "kg*m^2")
    assert devices.cellWidget(wheel, 0).isEnabled() and devices.cellWidget(wheel, 0).isChecked()
    assert devices.item(wheel, 6).text() == "values: u_max, Js from its properties; Basilisk's defaults for the rest"
    roue = _rows(devices, 1)["Roue Y"]
    assert not devices.cellWidget(roue, 0).isEnabled() and "Wheel inertia: empty" in devices.item(roue, 6).text()
    assert [(m.property, m.target, m.unit) for m in dialog.property_mappings()] == [
        ("Max torque", "reaction_wheel.u_max", "mN*m"), ("Wheel inertia", "reaction_wheel.Js", "kg*m^2")]


def test_a_unit_is_offered_only_for_a_matching_type(qtbot, tmp_path):
    """The sun sensor's "Field of view", an angle: degrees offered; the
    wheel's "Speed range", typed as a distance: no unit offered."""
    dialog = _dialog(qtbot, tmp_path)
    table = dialog.properties_table
    assert table.cellWidget(_map(dialog, "Field of view", "coarse_sun_sensor.fov_deg"), 5).currentData() == "deg"
    assert table.cellWidget(_map(dialog, "Speed range", "reaction_wheel.Omega_max"), 5).currentData() == ""


def test_a_bad_mapping_stops_the_import_and_says_why(qtbot, tmp_path):
    """Two properties to one value: Import is disabled and the dialog says
    why, until one is changed."""
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = _dialog(qtbot, tmp_path)
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    _map(dialog, "Max torque", "reaction_wheel.u_max", "N*m")
    _map(dialog, "Wheel inertia", "reaction_wheel.u_max", "N*m")
    assert not ok.isEnabled() and "two properties are mapped to reaction_wheel.u_max" in dialog.status.text()
    _map(dialog, "Wheel inertia", "")
    assert ok.isEnabled() and dialog.status.text() == ""


def test_the_battery_follows_the_mapping_and_an_earlier_one_is_shown(qtbot, tmp_path):
    """The battery choice is offered once the capacity is mapped; a
    dialog opened with an earlier import's mapping shows it."""
    from spacemissionstudio.idm_properties import Mapping

    dialog = _dialog(qtbot, tmp_path)
    assert not dialog.battery_check.isEnabled()
    _map(dialog, "Capacity", "battery.capacity_wh", "W*h")
    assert dialog.battery_check.isEnabled() and dialog.battery_label.text().startswith("85 W*h")
    dialog.battery_check.setChecked(True)
    assert dialog.power_choice().battery
    (tmp_path / "again").mkdir()
    again = _dialog(qtbot, tmp_path / "again", [Mapping("Capacity", "battery.capacity_wh", "kW*h")])
    row = _rows(again.properties_table)["Capacity"]
    assert again.properties_table.cellWidget(row, 5).currentData() == "kW*h"
    assert again.battery_label.text().startswith("85000 W*h")
