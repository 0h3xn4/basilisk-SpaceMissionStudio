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

"""Every row of the UI overhaul plan's §5.2 ("Every current element and
its new place") is reachable in the shell of M2a: a command of the action
registry (with its palette entry), a page of an area, or the screen that
opens a dialog. The table is read from the plan, so a row added there
without a check here fails. Where a row's new form needs a rebuilt screen
(M2b to M8), the check is where the function is reached now."""

import re
from pathlib import Path

import pytest

_PLAN = Path(__file__).resolve().parents[2] / "docs" / "ui" / "UI_OVERHAUL_PLAN.md"


def _plan_rows():
    text = _PLAN.read_text(encoding="utf-8")
    section = text[text.index("### 5.2 Every current element and its new place"):
                   text.index("### 5.3 Exports in one place")]
    return [today for today, _new in re.findall(r"^\| (.+?) \| (.+?) \|$", section, re.MULTILINE)[1:]]


@pytest.fixture(scope="module")
def window(qapp):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow

    question = QMessageBox.question
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard)
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window.resize(1280, 720)  # [px] the smallest window the views are checked at
    window.show()
    assert window.open_path(TEMPLATES_DIR / "23_starter_complete_small_satellite.json")
    qapp.processEvents()
    yield window
    window.close()
    QMessageBox.question = question


# -- what "reachable" means -----------------------------------------------------

def _command(window, *command_ids):
    """A command of the registry, listed in the palette under its name."""
    labels = {entry.label for entry in window.palette_entries()}
    for command_id in command_ids:
        command = window.commands[command_id]
        if command_id != "help.palette":  # the palette does not list itself
            assert f"{command.category} > {command.label}" in labels, command_id


def _shown(window, widget, area):
    """``widget`` comes into view in ``area``."""
    window.show_view(widget)
    assert window.shell.current_area() == area
    assert widget.isVisibleTo(window)


def _tree(window, path):
    """The Scenario area's tree node ``path`` (a page with sections shows
    its first)."""
    item = dict(window.scenario_editor.page_tree.paths())[path]
    window._show_tree_item(item)
    assert window.shell.current_area() == "scenario"
    current = window.scenario_editor.page_tree.tree.currentItem()
    assert current is item or current.parent() is item


def _button(window, button, area, show):
    """A button of a hosted screen: ``show`` brings it into view in ``area``."""
    show()
    assert window.shell.current_area() == area
    assert button.isVisibleTo(window) and button.isEnabled(), button.text()


def _reference_card(window):
    """The start-up question is Home's card (M3), not a modal dialog."""
    card = window.load_scenario_widget.reference_card
    card.ask()
    try:
        window.shell.show_area("home")
        assert card.isVisibleTo(window) and card.fetch_button.isEnabled()
    finally:
        card.dismiss()


def _dialog(module_name, class_name):
    """The dialog's class still exists (it is opened from its screen)."""
    import importlib

    module = importlib.import_module(f"spacemissionstudio.gui.{module_name}")
    assert isinstance(getattr(module, class_name), type)


def _spacecraft_list(window):
    return window.scenario_editor.spacecraft_list


# -- §5.2, row by row -----------------------------------------------------------

_ROWS = {
    "**File** › New": lambda w: (_command(w, "file.new"), _button(
        w, w.load_scenario_widget.start_from_scratch.button, "home", lambda: w.shell.show_area("home"))),
    "File › Open…": lambda w: (_command(w, "file.open"), _button(
        w, w.load_scenario_widget.browse_button, "home", lambda: w.shell.show_area("home"))),
    "File › Save, Save As…": lambda w: (_command(w, "file.save", "file.save_as"),
                                        _button(w, w.top_bar.save_button, w.shell.current_area(), lambda: None)),
    "File › Quit": lambda w: _command(w, "file.quit"),
    "**Edit** › Undo, Redo": lambda w: _command(w, "edit.undo", "edit.redo"),
    "**Run** › Run (Ctrl+R)": lambda w: (_command(w, "run.run"),
                                         _button(w, w.top_bar.run_button, w.shell.current_area(), lambda: None)),
    "Run › Run mode (Single, Monte Carlo, SIL)": lambda w: (
        _command(w, "run.mode.single", "run.mode.monte_carlo", "run.mode.sil"),
        _in_the_header(w, w.run_mode_control, "run"), _button(
            w, w.run_mode_control.buttons["sil"], "run", lambda: w.shell.show_area("run"))),
    "Run › Cancel Run (Esc)": lambda w: (_command(w, "run.cancel"), _shown(w, w.shell.page("run").buttons[
        w.abort_action], "run")),
    "Run › Live plot": lambda w: (_command(w, "run.live_plot"),
                                  _shown(w, w.run_page.live_plot_check, "run")),
    "Run › Check Reference Data": lambda w: (_command(w, "run.check_data"),
                                             _shown(w, w.status_items.data_button, w.shell.current_area())),
    "Run › Vizard Configuration…": lambda w: (_command(w, "run.vizard_config"),
                                             _shown(w, w.run_page.vizard_section, "run")),
    "Run › Launch Vizard": lambda w: (_command(w, "run.vizard_launch"),
                                     _shown(w, w.shell.page("run").buttons[w.vizard_launch_action], "run")),
    "Run › Open Monte Carlo Results…": lambda w: (_command(w, "run.open_monte_carlo"), _shown(
        w, w.shell.page("run").buttons[w.open_monte_carlo_results_action], "run")),
    # M5b: the folder is a field of Run > Run in Monte Carlo mode, remembered per scenario.
    "Monte Carlo archive-folder picker (modal, every batch)": lambda w: (
        _command(w, "run.mode.monte_carlo"), _archive_field(w)),
    "Run › Clear Time Cursor": lambda w: (_command(w, "run.clear_cursor"), _shown(
        w, w.shell.page("results").buttons[w.clear_cursor_action], "results")),
    "**Analyses** › End of Life, Budget": lambda w: (_command(w, "analyses.end_of_life", "analyses.budget"),
                                                    _shown(w, w.lifetime_widget, "run"),
                                                    _shown(w, w.budget_widget, "run")),
    "**Tools** › 3D Model…": lambda w: (_command(w, "tools.model_3d"), _shown(
        w, w.shell.page("scenario").buttons[w.model_3d_action], "scenario")),
    "Tools › Flight Software": lambda w: (_command(w, "tools.flight_software"),
                                          _shown(w, w.flight_software_widget, "reports")),
    "Tools › Reference Data…": lambda w: (_command(w, "tools.reference_data"),
                                          _shown(w, w.settings_page.buttons["tools.reference_data"], "settings")),
    "**View** › Side Panel, Inspector, Explain, Problems": lambda w: (
        _command(w, "view.inspector", "view.explain", "view.problems"),
        _toggles(w, "view.inspector", w.side_dock, "Ctrl+I"), _toggles(w, "view.problems", w.problems_dock, "Ctrl+J")),
    "View › Reset Layout": lambda w: (_command(w, "view.reset_layout"),
                                      _shown(w, w.settings_page.buttons["view.reset_layout"], "settings")),
    "View › Time Cursor ▸": lambda w: _command(w, *(c.id for c in w.commands if c.category == "Time Cursor")),
    "View › Theme ▸": lambda w: (_command(w, "view.theme.system", "view.theme.light", "view.theme.dark"),
                                 _shown(w, w.settings_page.buttons["view.theme.dark"], "settings")),
    "**Help** › User manual": lambda w: (_command(w, "help.manual"), _shown(w, w.shell.rail.buttons["help"],
                                                                             w.shell.current_area())),
    "Help › Keyboard shortcuts": lambda w: (_command(w, "help.shortcuts"),
                                            _shown(w, w.settings_page.shortcuts_table, "settings")),
    "Help › Command palette": lambda w: (_command(w, "help.palette"),
                                         _shown(w, w.top_bar.search_button, w.shell.current_area())),
    "Help › About": lambda w: (_command(w, "help.about"),
                               _shown(w, w.settings_page.buttons["help.about"], "settings")),
    "**Toolbar row 1**: New, Open, Save, Run, Single run ▾, Cancel, Live plot, 3D Model": lambda w: (
        _command(w, "file.new", "file.open", "file.save", "run.run", "run.mode.single", "run.cancel",
                 "run.live_plot", "tools.model_3d"), _no_toolbars(w)),
    "**Toolbar row 2**: Vizard Configuration, Launch Vizard, Check Reference Data": lambda w: (
        _command(w, "run.vizard_config", "run.vizard_launch", "run.check_data"), _no_toolbars(w)),
    "Title bar (name, save state, from template, run state chip)": lambda w: (
        _shown(w, w.top_bar.name_label, w.shell.current_area()), _in_the_status_bar(w, w.run_chip),
        _top_bar_says(w, "from template 23")),
    "Run progress strip": lambda w: _in_the_status_bar(w, w.run_progress),
    "Stale-results banner": lambda w: _is_above_the_areas(w, w.stale_results_banner),
    "Status bar items": lambda w: _shown(w, w.status_items.basilisk_label, w.shell.current_area()),
    # M4 removes it with the editor's rebuild; the Problems panel already lists the same problems.
    "Validation strip under the editor": lambda w: _shown(w, w.scenario_editor.validation_label, "scenario"),
    "**Scenario tab** › Templates": lambda w: _shown(w, w.load_scenario_widget, "home"),
    "Scenario › Scenario, Environment, Spacecraft…, Ground stations…, Mission sequence, Monte Carlo": lambda w: [
        _tree(w, path) for path in ("Scenario", "Environment", "Spacecraft", "Ground stations", "Mission sequence",
                                    "Monte Carlo")],
    "Scenario › JSON": lambda w: (_in_the_header(w, w.scenario_editor.json_button, "scenario"),
                                  _shown(w, w.scenario_editor.json_page, "scenario")),
    "Scenario › Analyses › End of Life, Budget": lambda w: (_shown(w, w.lifetime_widget, "run"),
                                                           _shown(w, w.budget_widget, "run")),
    "Scenario › Analyses › Flight Software": lambda w: _shown(w, w.flight_software_widget, "reports"),
    "Spacecraft › Budget (AD10) inputs": lambda w: _tree(
        w, f"Spacecraft > {_spacecraft_list(w).to_list()[0].name} > Budget (AD10)"),
    "**Results** › Plots": lambda w: _shown(w, w.results_widget, "results"),
    "Results › Dashboard": lambda w: _shown(w, w.mission_dashboard_widget, "results"),
    "Results › Output": lambda w: _shown(w, w.mission_output_widget, "results"),
    "Results › Monte Carlo": lambda w: (_monte_carlo_shown(w)),
    # M6 adds Results > Overview; nothing is there to reach yet.
    "(none)": lambda w: None,
    "**Events** tab": lambda w: _shown(w, w.event_timeline_widget, "timeline"),
    "**Compare** tab": lambda w: _shown(w, w.compare_widget, "results"),
    "**Log** tab": lambda w: _shown(w, w.log_widget, "run"),
    "Side **Inspector**": lambda w: (_command(w, "view.inspector"), _side(w, w.inspector_widget)),
    "Side **Explain**": lambda w: (_command(w, "view.explain"), _tree(w, "Overview"),
                                  _shown(w, w.scenario_explainer_widget, "scenario")),
    "Side **Problems**": lambda w: (_command(w, "view.problems"), _side(w, w.problems_widget),
                                   _in_the_status_bar(w, w.status_items.problems_button)),
    # The dialogs M4 and M5 turn into inline pages or the inspector: opened from their screen as before.
    "`SpacecraftEditorDialog` (Add spacecraft)": lambda w: (
        _dialog("spacecraft_editor", "SpacecraftEditorDialog"),
        _button(w, _spacecraft_list(w).add_button, "scenario", lambda: _tree(w, "Spacecraft"))),
    "`_ItemEditorDialog` (device)": lambda w: (_dialog("sensor_actuator_editor", "_ItemEditorDialog"),
                                              _tree(w, f"Spacecraft > {_spacecraft_list(w).to_list()[0].name}")),
    "`GroundStationEditorDialog`": lambda w: (_dialog("ground_station_editor", "GroundStationEditorDialog"),
                                             _tree(w, "Ground stations")),
    "`_CommandEditorDialog`": lambda w: (_dialog("mission_sequence_editor", "_CommandEditorDialog"),
                                        _tree(w, "Mission sequence")),
    "`_DispersionEditorDialog`": lambda w: (_dialog("monte_carlo_editor", "_DispersionEditorDialog"),
                                           _tree(w, "Monte Carlo")),
    "`PropagationSetupDialog`": lambda w: (_dialog("propagation_setup_dialog", "PropagationSetupDialog"),
                                          _tree(w, "Environment")),
    "`ModelEditorDialog`": lambda w: (_dialog("model_editor_dialog", "ModelEditorDialog"),
                                     _command(w, "tools.model_3d")),
    "`_ImportOptionsDialog`": lambda w: (_dialog("model_editor_dialog", "_ImportOptionsDialog"),
                                        _command(w, "tools.model_3d")),
    "`BoxFacetDialog`": lambda w: (_dialog("facet_editor", "BoxFacetDialog"),
                                  _tree(w, f"Spacecraft > {_spacecraft_list(w).to_list()[0].name}")),
    "`SpacecraftTemplateDialog`": lambda w: (
        _dialog("spacecraft_template_dialog", "SpacecraftTemplateDialog"),
        _button(w, _spacecraft_list(w).new_from_template_button, "scenario", lambda: _tree(w, "Spacecraft"))),
    "Walker, Phasing, ROE generators": lambda w: [
        _button(w, button, "scenario", lambda: _tree(w, "Spacecraft"))
        for button in (_spacecraft_list(w).generate_constellation_button,
                       _spacecraft_list(w).generate_phasing_formation_button,
                       _spacecraft_list(w).generate_roe_formation_button)],
    "`TemplateCustomizeWizard`": lambda w: (_dialog("template_wizard", "TemplateCustomizeWizard"),
                                           _shown(w, w.load_scenario_widget, "home")),
    "`OrbitSwitchDialog`": lambda w: (_dialog("orbit_ic_widget", "OrbitSwitchDialog"),
                                     _tree(w, f"Spacecraft > {_spacecraft_list(w).to_list()[0].name}")),
    "`SilRunDialog`": lambda w: (_dialog("sil_dialog", "SilRunDialog"), _command(w, "run.mode.sil")),
    "`VizardDialog`": lambda w: (_dialog("vizard_dialog", "VizardDialog"), _command(w, "run.vizard_config")),
    "`StartupFetchDialog`": lambda w: (_dialog("startup_fetch_dialog", "StartupFetchDialog"),
                                      _command(w, "tools.reference_data"), _reference_card(w)),
    "Reference data dialog": lambda w: (_command(w, "tools.reference_data"), _reference_data_opens(w)),
    "`CommandPalette`": lambda w: (_dialog("command_palette", "CommandPalette"), _command(w, "help.palette")),
    "`ShortcutsDialog`": lambda w: (_command(w, "help.shortcuts"), _shortcuts_in_settings(w)),
    "`ManualDialog`": lambda w: (_dialog("help_dialog", "ManualDialog"), _command(w, "help.manual")),
    "About box": lambda w: _command(w, "help.about"),
    "Discard-changes and autosave-recovery boxes": lambda w: (w._confirm_discard_unsaved,
                                                             w._check_autosave_recovery),
    "Toasts (`feedback.py`)": lambda w: _toast_shows(w),
}


def _archive_field(window):
    window.set_run_mode("monte_carlo")
    try:
        _shown(window, window.run_page.archive_edit, "run")
        assert window.run_page.archive_browse.isVisibleTo(window)
    finally:
        window.set_run_mode("single")


def _toast_shows(window):
    from spacemissionstudio.gui.feedback import show_toast

    toast = show_toast(window, "Reachable")
    assert toast.isVisible()
    toast.close()


def _no_toolbars(window):
    from PySide6.QtWidgets import QToolBar

    assert window.findChildren(QToolBar) == []


def _top_bar_says(window, text):
    assert text in window.top_bar.detail_label.text()


def _is_above_the_areas(window, widget):
    """Over every area: in the work column above the area stack."""
    layout = window.shell.work_layout
    assert layout.indexOf(widget) >= 0 and layout.indexOf(widget) < layout.indexOf(window.shell.stack)


def _monte_carlo_shown(window):
    window._show_monte_carlo_tab()
    assert window.shell.current_area() == "results"
    assert window.current_view() is window.monte_carlo_results_widget


def _side(window, widget):
    """A panel: hidden, then shown by show_view()."""
    dock = next(dock for dock in window._docks() if dock.widget() is widget)
    dock.hide()
    window.show_view(widget)
    assert dock.isVisibleTo(window)


def _toggles(window, command_id, dock, keys):
    """A command that shows and hides ``dock``, with its shortcut."""
    action = window.commands.action(command_id)
    assert action is dock.toggleViewAction() and window.commands[command_id].keys == keys
    shown = dock.isVisibleTo(window)
    action.trigger()
    assert dock.isVisibleTo(window) is not shown
    action.trigger()
    assert dock.isVisibleTo(window) is shown


def _in_the_status_bar(window, widget):
    assert window.statusBar().isAncestorOf(widget)


def _in_the_header(window, widget, area):
    """A control of ``area``'s header (the Scenario area's Form · JSON toggle)."""
    assert window.shell.page(area).header.isAncestorOf(widget)


def _reference_data_opens(window):
    window.commands.action("tools.reference_data").trigger()
    assert window.data_dialog.isVisible()
    window.data_dialog.close()


def _shortcuts_in_settings(window):
    window.commands.action("help.shortcuts").trigger()
    assert window.shell.current_area() == "settings"
    assert window.settings_page.shortcuts_table.rowCount() > 20


def test_every_row_of_the_plan_has_a_check():
    """The checks below are §5.2's rows, no more and no fewer."""
    assert sorted(_plan_rows()) == sorted(_ROWS)


@pytest.mark.parametrize("row", list(_ROWS))
def test_every_row_is_reachable_in_the_shell(window, row):
    """The §5.2 row ``row`` is reachable: its command is in the registry
    and the palette, its page in its area, or its dialog's screen is."""
    _ROWS[row](window)


def test_the_menu_bar_is_gone_and_every_command_is_on_the_window(window):
    """No menu bar and no toolbar: every command's action is the window's
    own (so its shortcut works in every area), the views' own Time Cursor
    moves aside, which work while Results has the focus."""
    assert window.menuWidget() is None or not window.menuWidget().actions()
    _no_toolbars(window)
    for command in window.commands:
        if command.category == "Time Cursor":
            assert command.action not in window.actions()
        else:
            assert command.action in window.actions(), command.id
