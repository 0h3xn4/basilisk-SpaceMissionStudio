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

"""The import dialog's axis choice (decision IDM-30): a device whose
shapes show an axis offers "from the model" first, chosen, and says in its
tooltip where it comes from; one whose shapes show none offers the axes of
its frame, +z chosen. The model is the synthetic fixture
``tests/data/idm/axessat``."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
from idm_fixtures import model_xml, write_idm  # noqa: E402

pytestmark = pytest.mark.requires_gui


def _dialog(qtbot, tmp_path):
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(write_idm(tmp_path / "axessat.idm", model_xml("axessat")))
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.plan() is not None, timeout=30000)
    return dialog


def _axis_combo(dialog, equipment):
    table = dialog.devices_table
    row = next(r for r in range(table.rowCount()) if table.item(r, 1).text() == equipment)
    return row, table.cellWidget(row, 4)


def test_the_axis_from_the_model_is_offered_first_and_chosen(qtbot, tmp_path):
    """The star tracker: "from the model" chosen, the cone and its field of
    view in the tooltip; the gyro: the frame's axes only, +z chosen; the
    choices returned carry what is shown, and an axis picked instead."""
    dialog = _dialog(qtbot, tmp_path)
    tracker_row, tracker = _axis_combo(dialog, "Star tracker optical head")
    assert tracker.itemText(0) == "from the model" and tracker.currentData() == "model"
    assert [tracker.itemData(i) for i in range(tracker.count())] == ["model", "+x", "-x", "+y", "-y", "+z", "-z"]
    assert "the field-of-view cone 'Field of view' (field of view 29.8628 deg)" in tracker.toolTip()
    gyro_row, gyro = _axis_combo(dialog, "Gyro unit")
    assert gyro.findData("model") == -1 and gyro.currentData() == "+z"
    assert "shapes show no axis (no field-of-view cone)" in gyro.toolTip()
    _row, wheel = _axis_combo(dialog, "Reaction wheel sideways")
    assert "from the cylinder 'Rotor'" in wheel.toolTip() and "[0, -1, 0]" in wheel.toolTip()
    choices = dialog.device_choices()
    assert (choices[tracker_row].axis, choices[gyro_row].axis) == ("model", "+z")
    tracker.setCurrentIndex(tracker.findData("-x"))
    assert dialog.device_choices()[tracker_row].axis == "-x"
