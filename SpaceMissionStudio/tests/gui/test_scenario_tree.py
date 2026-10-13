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

"""The Scenario Editor as a tree (docs/ux-audit.md U-01, U-10, U-11, U-17):
one page per node; the spacecraft, ground stations and the environment
edited in their pages as they are typed in, with Undo; a node counts the
problems about it; the list's Edit... goes to the node; a page follows a
change made elsewhere."""

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
    """A main window with template 22 open; closing it discards changes."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def _spacecraft_form(window):
    editor = window.scenario_editor
    editor.show_spacecraft(0)
    return editor._spacecraft_nodes[0].form


def test_a_template_opens_on_the_scenario_page(window):
    """Opening a template shows its Scenario page; a new window shows Templates."""
    editor = window.scenario_editor
    assert editor.page_tree.current_page() is editor.scenario_page and window.current_view() is editor


def test_a_spacecraft_is_edited_in_its_page_with_undo(window):
    """An edit in the spacecraft's page applies to the scenario (a save
    right after it included); Undo takes it back and the page shows it."""
    form = _spacecraft_form(window)
    form.dry_mass_kg.setValue(175.0)  # [kg]
    assert window.scenario_editor.to_scenario().spacecraft[0].dry_mass_kg == pytest.approx(175.0)  # [kg]
    assert window.top_bar.detail_label.text().startswith("Unsaved changes")
    window._history_timer.stop()
    window._record_history()  # as the settle timer would
    window.undo_action.trigger()
    assert window.scenario_editor.spacecraft_list.to_list()[0].dry_mass_kg == pytest.approx(150.0)  # [kg]
    assert _spacecraft_form(window).dry_mass_kg.value() == pytest.approx(150.0)  # [kg] the page follows


def test_renaming_a_spacecraft_renames_its_node(window):
    """The node and the Spacecraft list take the new name."""
    editor = window.scenario_editor
    form = _spacecraft_form(window)
    form.name_edit.setText("my-sat-2")
    editor.flush_forms()
    assert editor._spacecraft_nodes[0].item.text(0) == "my-sat-2"
    assert editor.spacecraft_list.list_widget.item(0).text() == "my-sat-2"


def test_a_form_that_does_not_validate_blocks_the_scenario(window):
    """An empty name is not applied: the page marks it, Problems lists it,
    the node counts it, and the scenario is not valid (no run with the old
    values)."""
    from spacemissionstudio.schema.scenario import ScenarioValidationError

    editor = window.scenario_editor
    form = _spacecraft_form(window)
    form.name_edit.setText("")
    editor.flush_forms()
    assert form.problem_banner.isVisibleTo(form)
    assert any("name must not be empty" in text for _severity, text in window.problems_widget.problems)
    assert editor._spacecraft_nodes[0].item.text(0) == "my-sat (1)" and editor.spacecraft_item.text(0) == "Spacecraft (1)"
    with pytest.raises(ScenarioValidationError, match="name must not be empty"):
        editor.to_scenario()
    form.name_edit.setText("my-sat")
    editor.flush_forms()
    assert editor.to_scenario().spacecraft[0].name == "my-sat" and not form.problem_banner.isVisibleTo(form)


def test_a_scenario_problem_counts_on_its_node(window):
    """An invalid epoch puts a count on the Scenario node."""
    editor = window.scenario_editor
    editor.epoch_edit.setText("2030-13-45T99:00:00")
    assert editor.scenario_item.text(0) == "Scenario (1)"
    editor.epoch_edit.setText("2030-01-01T08:30:00")
    assert editor.scenario_item.text(0) == "Scenario"


def test_edit_in_the_list_goes_to_the_node(window, monkeypatch):
    """Edit... selects the spacecraft's node; no dialog opens."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    monkeypatch.setattr(SpacecraftEditorDialog, "exec", lambda self: pytest.fail("a dialog opened"))
    editor = window.scenario_editor
    editor.spacecraft_list.list_widget.setCurrentRow(0)
    editor.spacecraft_list.edit_button.click()
    assert editor.page_tree.current_page() is editor._spacecraft_nodes[0].holder


def test_a_ground_station_is_edited_in_its_page(window):
    """A station's page applies its edits too."""
    editor = window.scenario_editor
    editor.show_station(0)
    form = editor._station_nodes[0].form
    form.min_elev_deg.setValue(15.0)  # [deg]
    assert editor.to_scenario().ground_stations[0].min_elevation_deg == pytest.approx(15.0)  # [deg]


def test_a_change_made_elsewhere_rebuilds_the_page(window, monkeypatch):
    """The 3D model editor's OK changes the spacecraft outside its page; the
    page shows the new mass."""
    from spacemissionstudio.gui import model_editor_dialog
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    from PySide6.QtWidgets import QDialog

    _spacecraft_form(window)
    model = SpacecraftModelConfig(parts=[ModelPartConfig(name="bus", shape="box",
                                                         dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0},  # [m]
                                                         mass_kg=120.0)])  # [kg]
    monkeypatch.setattr(model_editor_dialog.ModelEditorDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(model_editor_dialog.ModelEditorDialog, "model", lambda self: model)
    window.model_3d_action.trigger()
    assert _spacecraft_form(window).dry_mass_kg.value() == pytest.approx(120.0)  # [kg]


def test_the_simulation_mode_rebuilds_the_spacecraft_pages(window):
    """Full attitude adds the attitude tabs to the spacecraft's page."""
    editor = window.scenario_editor
    def tabs():
        widget = _spacecraft_form(window).tabs
        return [widget.tabText(i) for i in range(widget.count()) if widget.isTabVisible(i)]

    assert "Attitude control" not in tabs()  # template 22 is orbit only
    editor.simulation_mode_combo.setCurrentIndex(editor.simulation_mode_combo.findData("full_attitude"))
    assert "Attitude control" in tabs()


def test_escape_does_not_close_an_embedded_form(window, qtbot):
    """Escape in a page's form leaves the form where it is."""
    from PySide6.QtCore import Qt

    form = _spacecraft_form(window)
    window.show()
    qtbot.keyClick(form.dry_mass_kg, Qt.Key.Key_Escape)
    assert form.isVisibleTo(window.scenario_editor._spacecraft_nodes[0].holder)


def test_the_palette_goes_to_every_node(window):
    """The command palette lists each node of the scenario tree."""
    labels = [entry.label for entry in window.palette_entries()]
    assert "Go to tab > Scenario > Spacecraft > my-sat" in labels
    assert "Go to tab > Scenario > Analyses > Budget" in labels
