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

"""Values shown to be read, not as a line of text (gui.value_sheet), and
dialogs that never cut off their own text (gui.theme.dialogs)."""

import pytest

pytestmark = pytest.mark.requires_gui


def test_a_value_sheet_gives_each_value_its_row(qtbot):
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.value_sheet import ValueSheet

    sheet = ValueSheet("Mass", [("Mass", "86", "kg"), ("Eccentricity", "0.001", "")], note="From B")
    qtbot.addWidget(sheet)
    value = sheet.grid.itemAtPosition(0, 1).widget()
    assert value.text() == "86" and value.alignment() & Qt.AlignmentFlag.AlignRight
    assert sheet.grid.itemAtPosition(0, 2).widget().text() == "kg"
    assert sheet.value("Eccentricity") == "0.001"
    assert sheet.text() == "Mass\nMass: 86 kg\nEccentricity: 0.001\nFrom B"
    empty = ValueSheet("Page", empty="No values yet.")
    qtbot.addWidget(empty)
    assert empty.text() == "Page\nNo values yet."


def test_a_value_table_aligns_numbers_right(qtbot):
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.value_sheet import ValueTable

    table = ValueTable("Inertia [kg m²]", ["", "x", "y"], [["x", "14.0", "0"], ["y", "0", "12.5"]], numeric=(1, 2))
    qtbot.addWidget(table)
    assert table.grid.itemAtPosition(1, 1).widget().alignment() & Qt.AlignmentFlag.AlignRight
    assert table.grid.itemAtPosition(1, 0).widget().alignment() & Qt.AlignmentFlag.AlignLeft
    assert table.text().splitlines()[1:] == ["\tx\ty", "x\t14.0\t0", "y\t0\t12.5"]


def test_the_3d_model_editor_shows_mass_properties_as_tables(qtbot):
    """Mass and centre of mass as rows, the inertia as a matrix, the
    principal axes with their nearest body axis; the plain text stays the
    command line's."""
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    dialog = ModelEditorDialog(None, spacecraft_name="sat-1")
    qtbot.addWidget(dialog)
    dialog.add_part("prism")
    dialog.add_part("panel")
    dialog.recompute_now()
    summary = dialog.mass_summary
    assert summary.mass_sheet.rows[0] == ("Mass", "86", "kg")
    assert [row[0] for row in summary.inertia_table.rows] == ["x", "y", "z"]
    assert summary.inertia_table.rows[0][1] == "14.0113"
    assert [row[3] for row in summary.axes_table.rows] == ["+y", "+z", "+x"]
    assert summary.text().startswith("mass 86 kg")
    surfaces = dialog.surfaces_label
    assert surfaces.sheet.value("Number of facets") == "12" and surfaces.areas.value("From +z") == "2.828"


@pytest.fixture
def themed(restored_theme):
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, "light")
    yield restored_theme
    restored_theme.setStyle("Fusion")


def test_a_dialog_grows_to_fit_its_wrapped_text(qtbot, themed):
    """Made narrower than its text was laid out for, a dialog with a
    word-wrapped label grows taller, so no line or button is cut off."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    label = QLabel("A long explanation that wraps onto several lines when the dialog is narrow. " * 6)
    label.setWordWrap(True)
    layout.addWidget(label)
    layout.addWidget(QDialogButtonBox(QDialogButtonBox.StandardButton.Ok))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.resize(260, dialog.height())
    qtbot.waitUntil(lambda: dialog.height() >= layout.totalHeightForWidth(dialog.width()))
    assert dialog.minimumHeight() >= layout.totalHeightForWidth(dialog.width())
    assert label.geometry().bottom() <= dialog.height()
