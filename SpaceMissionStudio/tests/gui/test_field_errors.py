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

"""Errors at the field (docs/ux-audit.md U-12): a problem's message shows
under the field it is about, which is marked; Problems names a scenario
field by its label; double-clicking a problem opens where it is fixed (the scenario tree's
page, since 3b), the field shown and marked; the dialogs' OK shows a
problem the same way instead of a message box."""

import dataclasses
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    """A main window with template 22 open; closing it discards changes,
    and an error message box would fail the test."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: pytest.fail(f"message box: {a}")))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def _activate_error(window):
    problems = window.problems_widget
    row = next(i for i, (severity, _text) in enumerate(problems.problems) if severity == "error")
    problems.list.itemActivated.emit(problems.list.item(row))


def test_a_field_error_shows_under_its_row_and_clears(qtbot):
    """In a form the message goes in a row under the field; clearing it
    removes the row and the mark. Outside a form it follows the field."""
    from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLineEdit, QWidget

    from spacemissionstudio.gui.feedback import clear_field_error, field_error_text, show_field_error

    host = QWidget()
    qtbot.addWidget(host)
    form = QFormLayout(host)
    first, second = QLineEdit(), QLineEdit()
    form.addRow("First", first)
    form.addRow("Second", second)
    show_field_error(first, "First is wrong")
    assert form.rowCount() == 3 and field_error_text(first) == "First is wrong"
    assert form.itemAt(1, QFormLayout.ItemRole.FieldRole).widget().text() == "First is wrong"
    assert first.property("state") == "error"
    show_field_error(first, "Still wrong")
    assert form.rowCount() == 3 and field_error_text(first) == "Still wrong"
    clear_field_error(first)
    assert form.rowCount() == 2 and field_error_text(first) == "" and first.property("state") == ""

    row = QWidget()
    qtbot.addWidget(row)
    box = QHBoxLayout(row)
    lone = QLineEdit()
    box.addWidget(lone)
    show_field_error(lone, "Lone is wrong")
    assert box.count() == 2 and field_error_text(lone) == "Lone is wrong"


def test_an_invalid_epoch_is_marked_at_its_field(window):
    """The epoch field is marked and says what is wrong under it; Problems
    and the editor name it "Epoch (UTC)", not "scenario.epoch_utc"."""
    from spacemissionstudio.gui.feedback import field_error_text

    editor = window.scenario_editor
    editor.epoch_edit.setText("2030-13-45T99:00:00")
    assert field_error_text(editor.epoch_edit).startswith("Epoch (UTC) '2030-13-45T99:00:00' is not a valid ISO 8601")
    assert window.problems_widget.list.item(0).text().startswith("Error: Epoch (UTC) '2030-13-45T99:00:00'")
    assert "scenario.epoch_utc" not in editor.validation_label.text()

    editor.epoch_edit.setText("2030-01-01T08:30:00")
    assert field_error_text(editor.epoch_edit) == "" and editor.epoch_edit.property("state") == ""


def test_a_scenario_problem_focuses_its_field(window, monkeypatch):
    """Double-clicking a scenario field's problem shows that field."""
    from spacemissionstudio.gui import scenario_editor

    shown = []
    monkeypatch.setattr(scenario_editor, "bring_into_view", shown.append)
    window.show_view(window.results_widget)
    window.scenario_editor.name_edit.setText("")
    _activate_error(window)
    assert window.current_view() is window.scenario_editor and shown == [window.scenario_editor.name_edit]


@pytest.mark.parametrize("edit, widget_of", [
    (lambda sc: dataclasses.replace(sc, drag_coeff=-1.0), lambda d: d.drag_coeff),  # [-]
    (lambda sc: dataclasses.replace(sc, orbit=dataclasses.replace(sc.orbit, eccentricity=1.2)),  # [-]
     lambda d: d.orbit_widget.ecc),
])
def test_a_spacecraft_problem_opens_its_page_at_the_field(window, edit, widget_of):
    """Double-clicking a spacecraft's problem opens its page in the scenario
    tree: the banner says what is wrong, the field's tab is shown and the
    field is marked."""
    from spacemissionstudio.gui.feedback import field_error_text

    editor = window.scenario_editor
    spacecraft_list = editor.spacecraft_list
    spacecraft_list.from_list([edit(spacecraft_list.to_list()[0])])
    editor.revalidate()
    _activate_error(window)
    node = editor._spacecraft_nodes[0]
    form = node.form
    error = next(text for severity, text in window.problems_widget.problems if severity == "error")
    widget = widget_of(form)
    assert editor.page_tree.current_page() is node.holder
    assert form.problem_banner.isVisibleTo(form) and form.problem_banner.label.text() == error
    assert field_error_text(widget) == error
    assert form.tabs.currentWidget().isAncestorOf(widget)


def test_a_propagation_problem_opens_the_environment_at_the_field(window):
    """A duration of -1 day opens the Environment page at its duration."""
    from spacemissionstudio.gui.feedback import field_error_text

    editor = window.scenario_editor
    editor._sim_settings = dataclasses.replace(editor._sim_settings, duration_days=-1.0)  # [days]
    editor.revalidate()
    _activate_error(window)
    assert editor.page_tree.current_page() is editor.environment_page
    assert field_error_text(editor._environment_form.duration_days_spin).startswith(
        "sim_settings.duration_days must be > 0")


def test_a_ground_station_problem_opens_its_page_at_the_field(window):
    """A latitude of 100 deg opens that station's page at its latitude."""
    from spacemissionstudio.gui.feedback import field_error_text

    editor = window.scenario_editor
    stations = editor.ground_station_list
    stations.from_list([dataclasses.replace(stations.to_list()[0], latitude_deg=100.0)])  # [deg]
    editor.revalidate()
    _activate_error(window)
    node = editor._station_nodes[0]
    assert editor.page_tree.current_page() is node.holder
    assert field_error_text(node.form.lat_deg).startswith("berlin-gs: latitude_deg must be in [-90, 90]")


def test_the_spacecraft_editor_ok_shows_a_problem_at_the_field(qtbot, monkeypatch):
    """OK on a spacecraft whose Cartesian position is zero keeps the dialog
    open with the problem at the position field, not in a message box."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.feedback import field_error_text
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: pytest.fail(f"message box: {a}")))
    dialog = SpacecraftEditorDialog(simulation_mode="orbit_only")
    qtbot.addWidget(dialog)
    orbit = dialog.orbit_widget
    orbit.type_combo.setCurrentIndex(orbit.type_combo.findData("cartesian"))
    for box in (orbit.pos_x_km, orbit.pos_y_km, orbit.pos_z_km):
        box.setValue(0.0)  # [km]
    dialog._on_accept()
    assert dialog.result() == 0 and dialog.problem_banner.isVisibleTo(dialog)
    assert "position_km must not be [0, 0, 0]" in field_error_text(orbit.pos_x_km)


def test_every_spacecraft_field_has_a_place(qtbot):
    """Each top-level spacecraft field leads somewhere in the editor, so a
    problem about it never opens the dialog without showing where."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import SpacecraftConfig

    dialog = SpacecraftEditorDialog(simulation_mode="full_attitude")
    qtbot.addWidget(dialog)
    assert [f.name for f in dataclasses.fields(SpacecraftConfig) if dialog.field_widget(f.name) is None] == []


def test_editing_a_marked_dialog_field_clears_its_error(qtbot):
    """In a dialog the mark goes as soon as the field is edited."""
    from spacemissionstudio.gui.feedback import field_error_text
    from spacemissionstudio.gui.ground_station_editor import GroundStationEditorDialog

    dialog = GroundStationEditorDialog()
    qtbot.addWidget(dialog)
    dialog.show_problem("latitude_deg", "gs-1: latitude_deg must be in [-90, 90]")
    assert field_error_text(dialog.lat_deg)
    dialog.lat_deg.setValue(45.0)  # [deg]
    assert field_error_text(dialog.lat_deg) == "" and dialog.lat_deg.property("state") == ""
