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

"""The app shell's workspace (docs/ux-audit.md U-02, U-05, U-23): the main
tabs Scenario / Results / Events / Compare / Log, the side panel with the
Inspector, Explain and Problems, the reference data dialog, and the layout
kept between sessions with View > Reset Layout."""

import logging
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


def _new_window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


@pytest.fixture
def window(qtbot, monkeypatch):
    """A main window with template 22 open; closing it discards changes."""
    w = _new_window(qtbot, monkeypatch)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def _tab_texts(tabs):
    return [tabs.tabText(i) for i in range(tabs.count())]


def _finish_a_run(window, name=None):
    from spacemissionstudio.engine.results import ResultSet

    if name is not None:
        window.scenario_editor.name_edit.setText(name)
    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._on_run_finished(ResultSet(scenario_name=window._last_run_scenario.name))
    window.finish_run_end()  # M6b: the end of a run is shown in steps; take them


def test_the_areas_and_what_they_hold(window):
    """The rail's areas as the plan lists them (§5.1), each holding its
    screens. Home is the Templates; Scenario the scenario tree (U-01) with
    the scenario's own nodes, one per spacecraft (one under it per tab of
    its editor) and ground station; Run the analyses and the log; Results
    the run's plots, dashboard, output and Compare; Timeline the events;
    Reports the flight software. Help opens the manual; Explain is the
    Scenario tree's first node, Overview (M4b)."""
    assert [area.label for area in window.shell.page_areas()] == [
        "Home", "Scenario", "Run", "Results", "Timeline", "Reports", "Settings"]
    assert window.shell.areas["help"].page is None and window.shell.areas["help"].action is window.manual_action
    assert window.shell.page("home").content is window.load_scenario_widget
    assert [path for path, _page in window.scenario_editor.page_tree.paths()] == [
        "Overview", "Scenario", "Environment", "Spacecraft", "Spacecraft > my-sat",
        *(f"Spacecraft > my-sat > {tab}" for tab in ("Orbit / mass", "Power / propulsion / link budget", "3D model",
                                                     "Vizard model", "Budget (AD10)")),
        "Ground stations",
        "Ground stations > berlin-gs", "Mission sequence", "Monte Carlo"]
    assert window.shell.page("scenario").header.isAncestorOf(window.scenario_editor.mode_toggle)  # Form · JSON
    assert _tab_texts(window.run_views) == ["Run", "End of Life", "Budget", "History", "Log"]  # History: M5a; Run: M5b
    assert _tab_texts(window.results_views) == ["Overview", "Plots", "Dashboard", "Output", "Compare"]  # Overview: M6a
    assert window.shell.page("timeline").content is window.event_timeline_widget
    assert window.shell.page("reports").content is window.reports_views  # M8: Exports, then Flight Software
    assert _tab_texts(window.reports_views) == ["Exports", "Flight Software"]
    assert window.side_dock.widget() is window.inspector_widget
    assert window.scenario_editor.page_tree.item_of(window.scenario_explainer_widget) is window.overview_item
    assert window.current_view() is window.scenario_editor  # opening a template shows the editor


def test_show_view_selects_every_level(window):
    """show_view() reaches a page wherever it is: a page in a scroll area
    in the Run area, a Results view, a side panel page."""
    window.show_view(window.lifetime_widget)
    assert window.shell.current_area() == "run"
    assert window.current_view() is window.lifetime_widget
    window.show_view(window.mission_output_widget)
    assert window.shell.current_area() == "results"
    assert window.current_view() is window.mission_output_widget
    window.show_view(window.problems_widget)
    assert window.problems_dock.isVisibleTo(window)


def test_problems_list_the_validation_error_and_warnings(window):
    """The Problems page lists what the editor finds, its tab counts them,
    and double-clicking one opens the Scenario Editor."""
    problems = window.problems_widget
    assert not [p for p in problems.problems if p[0] == "error"]
    window.scenario_editor.epoch_edit.setText("2030-13-45T99:00:00")
    errors = [text for severity, text in problems.problems if severity == "error"]
    assert errors and "epoch" in errors[0].lower()
    tab_text = window.problems_dock.windowTitle()
    assert tab_text == f"Problems ({len(problems.problems)})"
    assert problems.proxy.rowCount() == len(problems.problems) and problems.row_text(0).startswith("Error: ")

    window.show_view(window.results_widget)
    problems.table.activated.emit(problems.index_of(0))
    assert window.current_view() is window.scenario_editor


def test_the_inspector_follows_the_focused_field(window, qapp):
    """Focusing a field shows its label, value, range and help. The test
    sends the application's focusChanged signal itself: Qt sends it only
    for the active window, and on a shared desktop (macOS CI, several
    workers) the test's window need not be the active one."""
    inspector = window.inspector_widget
    qapp.focusChanged.emit(None, window.scenario_editor.name_edit)
    assert inspector.name_label.text() == "Name"
    assert inspector.value_label.text() == window.scenario_editor.name_edit.text()
    qapp.focusChanged.emit(window.scenario_editor.name_edit, inspector.name_label)  # a click into the panel itself
    assert inspector.name_label.text() == "Name"

    from spacemissionstudio.gui.workspace_panels import field_range

    from PySide6.QtWidgets import QDoubleSpinBox

    box = QDoubleSpinBox()
    box.setRange(0.0, 10.0)  # [m]
    box.setSuffix(" m")
    box.setToolTip("<b>Height</b> of the thing")
    inspector.inspect(box)
    assert field_range(box) == "0 to 10 m" and inspector.range_label.text() == "0 to 10 m"
    assert inspector.help_label.text() == "Height of the thing"
    inspector.inspect(None)
    assert inspector.empty_label.isVisibleTo(inspector) and not inspector.form.isVisibleTo(inspector)


def test_the_log_tab_shows_the_session_log(window, qtbot):
    """Records from any logger reach the Log tab; the level box and the
    text filter narrow them; show_errors() keeps warnings and errors."""
    log = window.log_widget
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("spacemissionstudio.test").info("a plain note about orbit 7")
    logging.getLogger("spacemissionstudio.test").warning("a warning about orbit 8")
    qtbot.waitUntil(lambda: "orbit 8" in log.text.toPlainText(), timeout=2000)  # [ms]
    assert "orbit 7" in log.text.toPlainText()
    log.filter_edit.setText("orbit 7")
    assert "orbit 7" in log.text.toPlainText() and "orbit 8" not in log.text.toPlainText()
    log.show_errors()
    assert "orbit 8" in log.text.toPlainText() and "orbit 7" not in log.text.toPlainText()


def test_a_failed_run_opens_the_log(window, monkeypatch):
    """A failed run opens the Log tab at its warnings and errors."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    window._start_busy("Running")
    window._on_run_failed("boom")
    assert window.current_view() is window.log_widget
    assert window.log_widget.level_combo.currentData() == logging.WARNING


def test_the_compare_tab_lists_runs_and_their_input_differences(window, qtbot):
    """With two runs, Compare ticks both and shows the inputs that differ;
    the shown run and one other ticked has Results draw that one dashed,
    and Results' choice ticks the pair here (U-33)."""
    compare = window.compare_widget
    assert compare.empty_label.isVisibleTo(compare)
    _finish_a_run(window)
    _finish_a_run(window, name="22 - a second version")
    window.show_view(compare)  # Compare is refreshed when shown (M5a)
    qtbot.waitUntil(lambda: compare.run_list.count() == 2, timeout=10000)
    assert compare.content.isVisibleTo(compare) and compare.run_list.count() == 2
    assert [r.number for r in compare.checked_runs()] == [1, 2]  # the new run and the one before it
    inputs = [compare.inputs_table.cell(row, 0) for row in range(compare.inputs_table.row_count())]
    assert "name" in inputs
    compare.set_checked([1, 2])
    assert window.results_widget.compare_combo.currentData() == 1
    window.results_widget.compare_combo.setCurrentIndex(0)  # and back, from Results
    assert compare.chosen_number() is None and [r.number for r in compare.checked_runs()] == [2]
    window.results_widget.compare_combo.setCurrentIndex(window.results_widget.compare_combo.findData(1))
    assert [r.number for r in compare.checked_runs()] == [1, 2]


def test_the_stale_banner_shows_only_over_run_views(window):
    """After an edit the banner shows over Results, Events and Compare, not
    over the editor the edit is being made in."""
    _finish_a_run(window)
    window.scenario_editor.name_edit.setText("edited after the run")
    banner = window.stale_results_banner
    window.show_view(window.scenario_editor)
    assert not banner.isVisibleTo(window)
    for view in (window.results_widget, window.event_timeline_widget, window.compare_widget):
        window.show_view(view)
        assert banner.isVisibleTo(window)


def test_the_layout_is_kept_and_reset(qtbot, monkeypatch):
    """A hidden side panel stays hidden in the next window (the layout file
    is under the home folder, a temporary one in tests); View > Reset
    Layout brings it back."""
    first = _new_window(qtbot, monkeypatch)
    first.show()
    first.side_dock.hide()
    first.close()
    assert (Path.home() / ".spacemissionstudio" / "layout.ini").is_file()

    second = _new_window(qtbot, monkeypatch)
    second.show()
    assert not second.side_dock.isVisible()
    second.reset_layout_action.trigger()
    assert second.side_dock.isVisible()
    assert second.scenario_editor.page_tree.item_of(second.scenario_explainer_widget) is second.overview_item


def test_the_view_analyses_and_tools_commands(window):
    """The View commands show and hide the side panel, open each of its
    pages, reset the layout, collapse the rail and set the theme; the
    Analyses and Tools commands open their pages; Tools > Reference Data
    opens the dialog."""
    view = [command.label for command in window.commands if command.category == "View"]
    assert view == ["Inspector", "Explain", "Problems", "Reset Layout", "Navigation: Icons Only",
                    "Theme: System", "Theme: Light", "Theme: Dark"]

    def trigger(category, label):
        next(c for c in window.commands if c.category == category and c.label == label).action.trigger()

    trigger("Analyses", "Budget")
    assert window.current_view() is window.budget_widget
    trigger("Tools", "Flight Software")
    assert window.current_view() is window.flight_software_widget
    trigger("Tools", "Reference Data...")
    assert window.data_dialog.isVisible()
    window.data_dialog.close()
    window.problems_dock.hide()
    trigger("View", "Problems")
    assert window.problems_dock.isVisibleTo(window)


def _box_model():
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    return SpacecraftModelConfig(parts=[
        ModelPartConfig(name="bus", shape="box", dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0},  # [m]
                        mass_kg=100.0),  # [kg]
    ])


def _accept_the_model_editor(monkeypatch, model):
    """The 3D model editor returns ``model`` at once, as if OK was clicked;
    returns the names it was opened for."""
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.gui import model_editor_dialog

    opened = []
    monkeypatch.setattr(model_editor_dialog.ModelEditorDialog, "exec",
                        lambda self: opened.append(self._spacecraft_name) or QDialog.DialogCode.Accepted)
    monkeypatch.setattr(model_editor_dialog.ModelEditorDialog, "model", lambda self: model)
    return opened


def test_the_3d_model_entry_is_in_the_scenario_header(window, qtbot):
    """3D Model... is a button in the Scenario area's header, visible at the
    window's own size, and a Tools command, so the model editor is not only
    a tab of the spacecraft editor."""
    window.show()
    qtbot.waitExposed(window)
    window.show_view(window.scenario_editor)
    assert window.shell.page("scenario").buttons[window.model_3d_action].isVisibleTo(window)
    assert window.commands["tools.model_3d"].category == "Tools"


def test_the_3d_model_entry_applies_the_model(window, monkeypatch):
    """With one spacecraft the editor opens for it. OK stores the model and
    writes its mass and inertia into the spacecraft (template 22 is orbit
    only, so its facets are left alone); Undo takes it back."""
    opened = _accept_the_model_editor(monkeypatch, _box_model())
    before = window.scenario_editor.spacecraft_list.to_list()[0]
    window.model_3d_action.trigger()
    after = window.scenario_editor.spacecraft_list.to_list()[0]
    assert opened == [before.name]
    assert after.model is not None and after.model.parts[0].name == "bus"
    assert after.dry_mass_kg == pytest.approx(100.0)  # [kg]
    assert after.inertia_kg_m2[0] == pytest.approx(100.0 * 2.0 / 12.0)  # [kg*m^2] m (y^2 + z^2) / 12
    assert after.facets == before.facets
    assert window.top_bar.detail_label.text().startswith("Unsaved changes")

    window._history_timer.stop()
    window._record_history()  # as the settle timer would
    window.undo_action.trigger()
    assert window.scenario_editor.spacecraft_list.to_list()[0].model is None


def test_the_3d_model_entry_asks_which_spacecraft(window, monkeypatch):
    """With several spacecraft it asks which one; Cancel changes nothing."""
    import dataclasses

    from PySide6.QtWidgets import QInputDialog

    spacecraft_list = window.scenario_editor.spacecraft_list
    first = spacecraft_list.to_list()[0]
    spacecraft_list.from_list([first, dataclasses.replace(first, name="sat-b")])
    opened = _accept_the_model_editor(monkeypatch, _box_model())

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("sat-b", True)))
    window.model_3d_action.trigger()
    assert opened == ["sat-b"]
    assert [c.model is not None for c in spacecraft_list.to_list()] == [False, True]

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    window.model_3d_action.trigger()
    assert opened == ["sat-b"]


def test_the_3d_model_entry_without_a_spacecraft(window, monkeypatch):
    """With no spacecraft it opens the Scenario Editor and says to add one."""
    opened = _accept_the_model_editor(monkeypatch, _box_model())
    window.scenario_editor.spacecraft_list.from_list([])
    window.show_view(window.results_widget)
    window.model_3d_action.trigger()
    assert opened == [] and window.current_view() is window.scenario_editor


@pytest.fixture
def model_window(qtbot, monkeypatch):
    """A main window with template 28, whose spacecraft has a 3D model."""
    w = _new_window(qtbot, monkeypatch)
    assert w.open_path(next(_TEMPLATES.glob("28_*.json")))
    return w


def test_the_model_editor_says_what_the_next_run_uses(qtbot):
    """The editor's Use tab says what an applied model changes in this
    scenario: only the dry mass in an orbit-only run, the mass properties
    and facets in a full-attitude one; nothing when the mode is unknown."""
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    notes = {}
    for mode in ("orbit_only", "full_attitude", None):
        dialog = ModelEditorDialog(None, simulation_mode=mode)
        qtbot.addWidget(dialog)
        notes[mode] = (dialog.use_note.text(), dialog.use_note.isVisibleTo(dialog))
    assert "orbit only" in notes["orbit_only"][0] and "dry mass" in notes["orbit_only"][0]
    assert "inertia in the attitude dynamics" in notes["full_attitude"][0]
    assert notes[None] == ("", False)


def test_applying_a_model_says_what_it_wrote():
    """The toast after OK names what the model wrote into the spacecraft."""
    from spacemissionstudio.gui.spacecraft_editor import applied_summary

    values = {"dry_mass_kg": 300.0, "center_of_mass_b_m": [0.048, 0.0, 0.0],  # [kg], [m]
              "inertia_kg_m2": [0.0] * 9, "facets": [object()] * 18}
    assert applied_summary("octa-sat", values) == ("Applied the 3D model of 'octa-sat': dry mass 300 kg, "
                                                   "center of mass 4.8 cm from B, inertia, 18 facets")
    assert applied_summary("octa-sat", {}).startswith("Stored the 3D model of 'octa-sat' (nothing applied")


def test_model_problems_name_their_spacecraft():
    """A 3D model problem is matched to its spacecraft, the longest name
    first; other problems are not model problems."""
    from spacemissionstudio.gui.workspace_panels import model_problem_spacecraft

    names = ["sat-1", "sat-10"]
    assert model_problem_spacecraft("sat-10: 3D model: the mesh file is missing", names) == "sat-10"
    assert model_problem_spacecraft("sat-1: dry_mass_kg differ from the 3D model -- open the model", names) == "sat-1"
    assert model_problem_spacecraft("sat-1: the perigee is below 100 km", names) is None
    assert model_problem_spacecraft("other: 3D model: missing", names) is None


def test_a_stale_model_problem_opens_the_model_editor(model_window, monkeypatch):
    """When the spacecraft's mass no longer matches its 3D model, Problems
    says so; double-clicking it opens that spacecraft's model editor, and OK
    applies the model again, which clears the problem."""
    import dataclasses

    from PySide6.QtCore import Qt

    spacecraft_list = model_window.scenario_editor.spacecraft_list
    sc = spacecraft_list.to_list()[0]
    opened = _accept_the_model_editor(monkeypatch, sc.model)
    spacecraft_list.from_list([dataclasses.replace(sc, dry_mass_kg=sc.dry_mass_kg + 10.0)])  # [kg]
    model_window.scenario_editor.revalidate()
    problems = model_window.problems_widget
    row = next(i for i, (_severity, text) in enumerate(problems.problems) if "differ from the 3D model" in text)
    assert problems.index_of(row).data(Qt.ItemDataRole.ToolTipRole) == "Double-click to open the 3D model editor"

    problems.table.activated.emit(problems.index_of(row))
    assert opened == [sc.name] and model_window.current_view() is model_window.scenario_editor
    assert spacecraft_list.to_list()[0].dry_mass_kg == pytest.approx(sc.dry_mass_kg)
    assert not [text for _severity, text in problems.problems if "differ from the 3D model" in text]


def test_the_explain_badge_opens_the_model_editor(model_window, monkeypatch, qtbot):
    """The Explain panel's "3D model" badge is a button: it opens that
    spacecraft's model editor."""
    qtbot.waitUntil(lambda: not model_window.scenario_explainer_widget.pending, timeout=10000)
    sc = model_window.scenario_editor.spacecraft_list.to_list()[0]
    opened = _accept_the_model_editor(monkeypatch, sc.model)
    buttons = model_window.scenario_explainer_widget.model_buttons
    assert [b.text() for b in buttons] == [f"{sc.name}: 3D model, {len(sc.model.parts)} parts"]
    buttons[0].click()
    assert opened == [sc.name]
