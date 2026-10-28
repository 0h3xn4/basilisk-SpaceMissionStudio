"""Tests for gui.main_window.MainWindow -- the full File/Run workflow,
with QFileDialog/QMessageBox monkeypatched so nothing blocks on a real
modal dialog. The "Run" test below genuinely exercises the no-Basilisk
error path in this development sandbox (see test_run_worker.py).
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal

pytestmark = pytest.mark.requires_gui


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Every test in this file gets an isolated autosave recovery
    location, same as tests/test_autosave.py's own fixture -- this
    file's own ``window`` fixture constructs a real ``MainWindow``,
    whose autosave timer/startup check (gui.autosave, design
    -philosophy roadmap item M4) must never read or write a real
    user's actual home directory from an automated test run.
    """
    from spacemissionstudio.gui import autosave

    recovery_dir = tmp_path / "autosave"
    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", recovery_dir)
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", recovery_dir / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    # Safety net: qtbot.addWidget()'s teardown calls .close() on the
    # window, which -- for a test that leaves it dirty on purpose (e.g.
    # test_editing_marks_dirty) -- triggers the REAL, unmocked
    # unsaved-changes QMessageBox.question() prompt. In offscreen mode
    # nothing ever answers it, so teardown hangs forever. Default to
    # "Discard" here; any test that specifically exercises the close
    # -confirmation prompt overrides this with its own monkeypatch.setattr
    # call, which simply takes over for the rest of that test.
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))

    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


def _add_valid_spacecraft(window):
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    window.scenario_editor.spacecraft_list.from_list([
        SpacecraftConfig(name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0]))
    ])
    window.scenario_editor.changed.emit()


def test_initial_title_is_untitled(window):
    """A new window's title says the scenario is untitled."""
    assert window.windowTitle() == "SpaceMissionStudio -- untitled"


def _explained(window, qtbot) -> None:
    """Wait for the explanation an edit asked for (250 ms later, from a worker; M4b)."""
    qtbot.waitUntil(lambda: not window.scenario_explainer_widget.pending, timeout=10000)


def test_explain_tab_exists_and_shows_the_default_scenario_on_startup(window):
    """The Explain tab exists and, on start-up, shows its placeholder for the
    default scenario (which has no spacecraft and so does not validate) instead
    of its blank constructor state."""
    assert window.scenario_editor.page_tree.item_of(window.scenario_explainer_widget) is window.overview_item
    assert window.overview_item.text(0) == "Overview"
    # reset_to_default()'s own scenario has zero spacecraft (invalid --
    # Scenario.validate() requires >= 1), so the placeholder is the
    # correct initial state here, not a crash -- this is the real
    # regression this test guards: reset_to_default() runs BEFORE
    # __init__ wires the changed signal, so without the explicit initial
    # call this fix adds, the widget would be left showing its
    # constructor-time blank state instead of ever calling set_scenario()
    # at all.
    assert not window.scenario_explainer_widget._placeholder_label.isHidden()


def test_explain_tab_refreshes_on_edit(window, qtbot):
    """Adding a valid spacecraft makes the Explain tab show a headline and at
    least one stat tile."""
    _add_valid_spacecraft(window)
    _explained(window, qtbot)
    assert window.scenario_explainer_widget._headline_label.isHidden() is False
    tile_labels = {
        window.scenario_explainer_widget._tiles_row.itemAt(i).widget()
        for i in range(window.scenario_explainer_widget._tiles_row.count())
        if window.scenario_explainer_widget._tiles_row.itemAt(i).widget() is not None
    }
    assert tile_labels  # at least one stat tile rendered for the new spacecraft


def test_explain_tab_shows_placeholder_while_scenario_is_invalid(window):
    """While the scenario does not validate (an empty name), the Explain tab
    shows its placeholder."""
    window.scenario_editor.name_edit.setText("")  # name must not be empty -- an invalid scenario
    window.scenario_editor.changed.emit()
    assert not window.scenario_explainer_widget._placeholder_label.isHidden()


def test_explain_tab_refreshes_on_new(window, qtbot):
    """File > New replaces the explained scenario with the placeholder, not the
    previous headline."""
    _add_valid_spacecraft(window)
    _explained(window, qtbot)
    assert not window.scenario_explainer_widget._headline_label.isHidden()
    window.on_new()
    # on_new() resets to reset_to_default()'s own zero-spacecraft scenario,
    # which does NOT validate (Scenario.validate() requires >= 1
    # spacecraft) -- the placeholder, not the stale "sat-1" headline from
    # before on_new(), is the correct post-reset state.
    assert not window.scenario_explainer_widget._placeholder_label.isHidden()


def test_toolbar_actions_are_all_visible(window, qtbot):
    """Regression test for a real user report, with a screenshot: on
    their platform, one toolbar button ("Launch Vizard") simply wasn't
    visible in a single, wide, un-movable QToolBar -- confirmed present
    in the Run menu (so the QAction itself was fine), meaning it was a
    toolbar-width/overflow rendering issue this sandbox's own offscreen
    Fusion-style rendering never reproduced. _build_toolbar() now uses
    two shorter, fixed rows instead of one wide one specifically so no
    single action's visibility depends on window width/platform toolbar
    -overflow behavior. The toolbars are gone (UI overhaul M2a): assert
    every command they held is a visible button where it now lives -- the
    top bar (Save, Run and its mode), the Run area's header (the run
    controls, Vizard, the reference data check) and Home (New and Open,
    as the page's own New blank scenario and Browse for a file...) --
    not just present as a QAction object somewhere.
    """
    window.show()
    qtbot.waitExposed(window)

    top = window.top_bar
    for widget in (top.save_button, top.run_button, window.run_mode_button):
        assert widget.isVisibleTo(window), f"{widget.text()!r} is not visible in the top bar"
    window.shell.show_area("run")
    header = window.shell.page("run").buttons
    for action in (window.run_action, window.abort_action, window.vizard_launch_action, window.check_kernels_action):
        assert action in header, f"{action.text()!r} is missing from the Run area"
        assert header[action].isVisibleTo(window), f"{action.text()!r}'s button is not visible"
    assert window.run_mode_control.isVisibleTo(window)
    # M5b: Live plot and the Vizard options are on Run > Run
    window.show_view(window.run_page)
    assert window.run_page.live_plot_check.isVisibleTo(window)
    assert window.run_page.vizard_section.isVisibleTo(window)
    window.shell.show_area("home")
    home = window.load_scenario_widget
    assert home.start_from_scratch.button.isVisibleTo(window) and home.browse_button.isVisibleTo(window)
    # The run modes (Monte Carlo among them) are in the mode buttons' menu, beside Run (U-18).
    assert window.run_mode_button.menu().actions() == window.run_mode_group.actions()
    assert sorted(window.run_mode_control.buttons) == sorted(a.data() for a in window.run_mode_group.actions())  # M5b
    assert window.monte_carlo_action in window.run_mode_group.actions()


def test_editing_marks_dirty(window):
    """An edit marks the scenario unsaved and adds an asterisk to the title."""
    assert not window._dirty
    _add_valid_spacecraft(window)
    assert window._dirty
    assert window.windowTitle().endswith("*")


def test_save_as_then_open_round_trip(window, tmp_path, monkeypatch):
    """Save As writes the file and clears the unsaved mark; New empties the
    editor; Open brings the saved spacecraft back."""
    from PySide6.QtWidgets import QFileDialog

    _add_valid_spacecraft(window)
    save_path = tmp_path / "test_scenario.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(save_path), "")))
    window.on_save_as()

    assert save_path.exists()
    assert not window._dirty
    assert window._current_path == save_path

    window.on_new()
    assert window._current_path is None
    assert window.scenario_editor.spacecraft_list.to_list() == []

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(save_path), "")))
    window.on_open()
    assert window._current_path == save_path
    assert window.scenario_editor.spacecraft_list.to_list()[0].name == "sat-1"


def test_save_after_opening_a_template_asks_where_and_keeps_the_template(window, tmp_path, monkeypatch):
    """Audit of 2026-10-27 (G1): Save after opening a built-in template
    wrote over the template file. It now goes to Save As, which starts in
    the home folder under the template's name; the template is unchanged
    and the saved file becomes the scenario's."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    template = TEMPLATES_DIR / "22_starter_first_leo_satellite.json"
    shipped = template.read_bytes()
    assert window.open_path(template)
    window.scenario_editor.name_edit.setText("my first satellite")
    asked = []
    save_path = tmp_path / "mine.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (asked.append(a[2]), (str(save_path), ""))[1]))
    window.on_save()

    assert asked == [str(Path.home() / template.name)]
    assert template.read_bytes() == shipped
    assert save_path.exists() and window._current_path == save_path and not window._dirty


def test_save_as_refuses_the_templates_folder(window, monkeypatch, reported):
    """Save As into the built-in templates folder is refused with a
    warning; the template is unchanged and the scenario stays unsaved."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    template = TEMPLATES_DIR / "22_starter_first_leo_satellite.json"
    shipped = template.read_bytes()
    assert window.open_path(template)
    window.scenario_editor.name_edit.setText("my first satellite")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(template), "")))
    window.on_save_as()

    assert template.read_bytes() == shipped
    assert reported and reported[-1][1] == "warning" and "built-in templates folder" in reported[-1][0]
    assert window._dirty


def test_save_with_invalid_scenario_shows_error_and_does_not_write(window, tmp_path, monkeypatch, reported):
    """No message box (U-39): a warning toast says why, and Problems opens
    at the field, as a refused run does."""
    from PySide6.QtWidgets import QFileDialog

    save_path = tmp_path / "invalid.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(save_path), "")))

    window.on_save_as()  # no spacecraft yet -- invalid

    assert not save_path.exists()
    assert len(reported) == 1 and reported[0][1] == "warning" and reported[0][0].startswith("Cannot save:")
    assert window.problems_dock.isVisibleTo(window)


def test_a_save_that_cannot_be_written_is_reported(window, tmp_path, monkeypatch, reported):
    """Audit M9: an OSError from saving (here a folder path under a file)
    was only logged; the user now sees "Could not save" and the scenario
    stays unsaved."""
    from PySide6.QtWidgets import QFileDialog

    _add_valid_spacecraft(window)
    blocker = tmp_path / "a_file"
    blocker.write_text("not a folder")
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(blocker / "scenario.json"), "")))
    window.on_save_as()

    assert len(reported) == 1 and reported[0][1] == "error"
    assert reported[0][0].startswith("Could not save the scenario to") and "(more in the Log)" in reported[0][0]
    assert window._current_path is None and window._dirty


def test_open_missing_file_shows_error(window, tmp_path, monkeypatch, reported):
    """Opening a file that does not exist reports one error naming the path and
    keeps no current file."""
    from PySide6.QtWidgets import QFileDialog

    missing = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(missing), "")))

    window.on_open()
    assert len(reported) == 1 and reported[0][1] == "error" and str(missing) in reported[0][0]
    assert window._current_path is None


def test_window_starts_on_load_scenario_tab(window):
    """The window starts on the Load scenario page."""
    assert window.current_view() is window.load_scenario_widget


def test_choosing_a_template_opens_it_and_switches_to_editor_tab(window):
    """Choosing a template opens it as the current file and switches to the
    Scenario Editor."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    template_path = sorted(TEMPLATES_DIR.glob("*.json"))[0]

    window.load_scenario_widget.path_chosen.emit(template_path)

    assert window._current_path == template_path
    assert window.current_view() is window.scenario_editor
    assert len(window.scenario_editor.spacecraft_list.to_list()) >= 1


def test_choosing_a_template_with_unsaved_changes_prompts_first(window, monkeypatch):
    """Choosing a template with unsaved changes asks first; cancelling keeps
    the unsaved scenario and the Load page."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from PySide6.QtWidgets import QMessageBox

    _add_valid_spacecraft(window)
    question_calls = []
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: question_calls.append(1) or QMessageBox.StandardButton.Cancel))

    template_path = sorted(TEMPLATES_DIR.glob("*.json"))[0]
    window.load_scenario_widget.path_chosen.emit(template_path)

    assert len(question_calls) == 1
    # Cancelled -- the original (dirty) scenario must still be showing,
    # not the template that was about to replace it.
    assert window._current_path is None
    assert window.current_view() is window.load_scenario_widget


def test_choosing_a_customized_scenario_opens_it_with_no_current_path(window):
    """gui.template_wizard.TemplateCustomizeWizard emits an in-memory
    Scenario, not a file path -- _on_load_scenario_customized must leave
    _current_path at None (so on_save() routes through on_save_as()
    rather than silently writing over the original template file this
    scenario was built from).
    """
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.schema import load_scenario

    template_path = TEMPLATES_DIR / "03_geo_station_keeping.json"
    scenario = load_scenario(template_path)
    scenario.spacecraft[0].geo_station_keeping.longitude_deadband_deg = 0.1

    window.load_scenario_widget.scenario_customized.emit(scenario)

    assert window._current_path is None
    assert window.current_view() is window.scenario_editor
    loaded = window.scenario_editor.to_scenario()
    assert loaded.spacecraft[0].geo_station_keeping.longitude_deadband_deg == 0.1
    # The original template file itself must be untouched.
    assert load_scenario(template_path).spacecraft[0].geo_station_keeping.longitude_deadband_deg != 0.1


def test_choosing_a_customized_scenario_with_unsaved_changes_prompts_first(window, monkeypatch):
    """Opening a customized template with unsaved changes asks first;
    cancelling stays on the Load page."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.schema import load_scenario
    from PySide6.QtWidgets import QMessageBox

    _add_valid_spacecraft(window)
    question_calls = []
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: question_calls.append(1) or QMessageBox.StandardButton.Cancel))

    scenario = load_scenario(TEMPLATES_DIR / "03_geo_station_keeping.json")
    window.load_scenario_widget.scenario_customized.emit(scenario)

    assert len(question_calls) == 1
    assert window.current_view() is window.load_scenario_widget


def test_customized_scenario_that_fails_validation_shows_error_not_crash(window, monkeypatch, reported):
    """A customized template that fails validation reports an error and stays
    on the Load page."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(TEMPLATES_DIR / "03_geo_station_keeping.json")
    scenario.spacecraft[0].geo_station_keeping.longitude_deadband_deg = -1.0  # invalid: must be > 0

    window.load_scenario_widget.scenario_customized.emit(scenario)

    assert len(reported) == 1 and reported[0][0].startswith("Could not open the customized scenario")
    assert window.current_view() is window.load_scenario_widget


def test_on_new_switches_to_editor_tab(window):
    """File > New switches to the Scenario Editor."""
    window.show_view(window.load_scenario_widget)
    window.on_new()
    assert window.current_view() is window.scenario_editor


def test_open_path_returns_true_on_success_false_on_failure(window, tmp_path, monkeypatch):
    """open_path returns True for a template and False for a missing file."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    template_path = sorted(TEMPLATES_DIR.glob("*.json"))[0]
    assert window.open_path(template_path) is True

    missing = tmp_path / "does_not_exist.json"
    assert window.open_path(missing) is False


@pytest.mark.usefixtures("basilisk_unavailable")
def test_run_without_basilisk_shows_error_and_reenables_action(window, qtbot):
    """Without Basilisk, Run reports one problem saying Basilisk is not
    installed (in the Log, a toast and the status bar: U-39) and enables
    Run again."""
    _add_valid_spacecraft(window)

    window.on_run()
    assert not window.run_action.isEnabled()
    qtbot.waitUntil(lambda: window.run_action.isEnabled(), timeout=5000)

    assert len(window.run_problems) == 1
    assert "Basilisk is not installed" in window.run_problems[0]


def test_run_with_invalid_scenario_shows_error_without_starting_worker(window):
    """An invalid scenario never starts a worker: the problem is said once
    (Log, toast, status bar; no message box, U-23) and Problems opens."""
    window.on_run()  # no spacecraft -- invalid, should never construct a RunWorker

    assert len(window.run_problems) == 1 and window.run_problems[0].startswith("Cannot run: ")
    assert window.statusBar().currentMessage().startswith("Cannot run: ")
    assert window.problems_dock.isVisibleTo(window)
    assert window._run_worker is None


def test_close_with_unsaved_changes_prompts_and_cancel_blocks_close(window, monkeypatch):
    """Closing with unsaved changes asks; Cancel keeps the window open."""
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    _add_valid_spacecraft(window)
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel))

    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()


def test_close_with_unsaved_changes_discard_allows_close(window, monkeypatch):
    """Closing with unsaved changes asks; Discard closes the window."""
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    _add_valid_spacecraft(window)
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))

    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


def test_configure_vizard_sets_request(window, monkeypatch):
    """Accepting the Vizard dialog with live streaming chosen stores a
    live-stream request."""
    assert window._vizard_request is None

    window.on_configure_vizard()  # M5b: the Vizard form on Run > Run, applied as it is edited
    window.run_page.vizard_form.live_stream_radio.setChecked(True)

    assert window._vizard_request is not None
    assert window._vizard_request.live_stream is True


def test_configure_vizard_cancel_leaves_request_unchanged(window, monkeypatch):
    """Cancelling the Vizard dialog stores no request."""
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.gui.vizard_dialog import VizardDialog

    monkeypatch.setattr(VizardDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    window.on_configure_vizard()
    assert window._vizard_request is None


def test_run_passes_vizard_request_to_worker(window, monkeypatch):
    """Run hands the stored Vizard request to the run worker."""
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.run_worker import RunWorker
    from spacemissionstudio.engine.vizard import VizardRequest

    _add_valid_spacecraft(window)
    window._vizard_request = VizardRequest(live_stream=True)
    # on_run() now confirms Vizard is connected before starting a
    # live-stream run (see its own comment) -- stubbed out here since
    # this test is about vizard_request passthrough, not the Vizard
    # process itself (see test_run_ensures_vizard_is_running_before_a_
    # live_stream_run for that).
    monkeypatch.setattr(MainWindow, "on_launch_vizard", lambda self: True)

    captured = {}
    original_init = RunWorker.__init__

    def spy_init(self, scenario, vizard_request=None, live=False, parent=None, allow_scripts=False):
        captured["vizard_request"] = vizard_request
        original_init(self, scenario, vizard_request=vizard_request, live=live, parent=parent,
                      allow_scripts=allow_scripts)

    monkeypatch.setattr(RunWorker, "__init__", spy_init)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)  # don't actually spin up the thread

    window.on_run()
    assert captured["vizard_request"] is window._vizard_request


def test_run_starts_busy_indicator_and_disables_other_run_actions(window, monkeypatch):
    """Run starts the busy indicator, disables Run, Live plot and Monte Carlo,
    and says it is running."""
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)  # don't actually spin up the thread

    window.on_run()
    assert window._busy_timer.isActive()
    assert not window.run_action.isEnabled()
    assert not window.live_plot_action.isEnabled()  # can't toggle it mid-run either
    assert not window.monte_carlo_action.isEnabled()  # can't start a second run while one is in flight
    assert "Running" in window.statusBar().currentMessage()


def test_live_plot_action_is_checked_by_default(window):
    """Live plot is on by default."""
    assert window.live_plot_action.isChecked()


def test_run_passes_live_flag_from_action_to_worker(window, monkeypatch):
    """Run passes the Live plot toggle to the run worker, on and off."""
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    captured = {}
    original_init = RunWorker.__init__

    def spy_init(self, scenario, vizard_request=None, live=False, parent=None, allow_scripts=False):
        captured["live"] = live
        captured["allow_scripts"] = allow_scripts
        original_init(self, scenario, vizard_request=vizard_request, live=live, parent=parent,
                      allow_scripts=allow_scripts)

    monkeypatch.setattr(RunWorker, "__init__", spy_init)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)
    monkeypatch.setattr(type(window), "_confirm_script_blocks", lambda self, blocks: True)

    window.live_plot_action.setChecked(True)
    window.on_run()
    assert captured["live"] is True

    window.live_plot_action.setChecked(False)
    window.on_run()
    assert captured["live"] is False


def test_run_with_live_plot_clears_previous_result_and_shows_results_tab(window, monkeypatch):
    """A live run clears the previous run's plots and switches to the Results
    page."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)

    stale = ResultSet(scenario_name="stale")
    stale.add(TimeSeries("sat-1.position_N", [0.0], ("x", "y", "z"), [[0.0, 0.0, 0.0]], units="m"))
    window.results_widget.set_result(stale)
    window.show_view(window.lifetime_widget)  # some page other than the run views

    window.live_plot_action.setChecked(True)
    window.on_run()

    assert window.results_widget.plot_names() == []
    assert window.current_view() is window.results_widget


def test_run_finished_preserves_users_series_selection(window):
    """Regression test for an audit finding: _on_run_finished() used to
    call ResultsWidget.set_result(), which unconditionally rebuilds
    the plot catalog and resets the shown plot to the first series -- so the
    instant a live-watched run actually finished, whatever series the
    user had picked to watch snapped back to the first one. It must use
    set_live_result() instead, which only rebuilds when the series set
    itself changes.
    """
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    def _result():
        rs = ResultSet(scenario_name="test")
        rs.add(TimeSeries("sat-1.position_N", [0.0], ("x", "y", "z"), [[0.0, 0.0, 0.0]], units="m"))
        rs.add(TimeSeries("sat-1.velocity_N", [0.0], ("x", "y", "z"), [[0.0, 0.0, 0.0]], units="m/s"))
        return rs

    window._on_run_progress(_result(), 0.5)
    window.results_widget.show_series("sat-1.velocity_N")

    window._on_run_finished(_result())

    assert window.results_widget.current_series_name() == "sat-1.velocity_N"


def test_close_while_run_in_progress_is_blocked(window, qtbot, monkeypatch):
    """Closing during a run is refused, with one problem saying the run is
    still going."""
    import threading

    from PySide6.QtGui import QCloseEvent
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    release = threading.Event()
    monkeypatch.setattr(RunWorker, "run", lambda self: release.wait(5))

    window.on_run()
    qtbot.waitUntil(lambda: window._run_worker.isRunning(), timeout=5000)

    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert len(window.run_problems) == 1 and "still running" in window.run_problems[0]

    release.set()
    qtbot.waitUntil(lambda: not window._run_worker.isRunning(), timeout=5000)


def test_run_progress_updates_results_widget_and_busy_bar(window):
    """A progress update plots the partial result and sets the progress bar to
    its fraction."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    window._start_busy("Running test...", determinate=True)
    partial = ResultSet(scenario_name="test")
    partial.add(TimeSeries("sat-1.position_N", [0.0, 1.0], ("x", "y", "z"),
                            [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], units="m"))

    window._on_run_progress(partial, 0.5)

    assert len(window.results_widget.plot_names()) == 1
    assert window._busy_progress.value() == 50


def test_run_progress_exception_is_caught_not_propagated(window, monkeypatch):
    """Real user feedback: running another simulation after a previous
    one "seems to break a lot of things in the GUI" -- the app should
    never crash or get stuck just because something unusual happened.
    If a live-progress update ever raises (for whatever reason, on
    whichever chunk), _on_run_progress must swallow it (logged, surfaced
    once in the Log and a toast) rather than let it propagate out through
    Qt's own signal dispatch -- the simulation itself, on its own
    thread, is completely unaffected either way.
    """
    from spacemissionstudio.engine.results import ResultSet

    window._start_busy("Running test...", determinate=True)
    monkeypatch.setattr(
        window.results_widget, "set_live_result",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    window._on_run_progress(ResultSet(scenario_name="test"), 0.5)  # must not raise

    assert len(window.run_problems) == 1 and "boom" in window.run_problems[0]


def test_run_progress_exception_dialog_shown_only_once_per_run(window, monkeypatch):
    """A live-plot error is reported once per run, not once per update, and
    again in the next run."""
    from spacemissionstudio.engine.results import ResultSet

    window._start_busy("Running test...", determinate=True)
    monkeypatch.setattr(
        window.results_widget, "set_live_result",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    for _ in range(5):
        window._on_run_progress(ResultSet(scenario_name="test"), 0.5)

    assert len(window.run_problems) == 1  # not a message-per-chunk storm

    # A fresh on_run() (a new run starting) resets the suppression --
    # confirmed via the same flag on_run() itself resets, not by driving
    # a full real run here.
    window._progress_error_shown = False
    window._on_run_progress(ResultSet(scenario_name="test"), 0.5)
    assert len(window.run_problems) == 2


def test_run_finished_exception_still_stops_busy_indicator(window, monkeypatch):
    """Same robustness principle as _on_run_progress's own tests, for the
    terminal handler: if displaying a successfully-finished run's results
    ever raises, the busy/Run-disabled state must still clear -- the
    historically worst form of "breaks a lot of things" is the user
    being unable to start another run at all without restarting the app.
    """
    from spacemissionstudio.engine.results import ResultSet
    from spacemissionstudio.gui import main_window as main_window_module

    window._start_busy("Running test...")
    monkeypatch.setattr(
        window.results_widget, "set_live_result",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(main_window_module.QMessageBox, "warning", lambda *a, **k: None)

    window._on_run_finished(ResultSet(scenario_name="test", series={}))  # must not raise

    assert not window._busy_timer.isActive()
    assert window.run_action.isEnabled()


def test_run_cancelled_exception_still_stops_busy_indicator(window, monkeypatch):
    """An error while showing a cancelled run's result still stops the busy
    indicator, enables Run and disables Abort."""
    from spacemissionstudio.engine.results import ResultSet
    from spacemissionstudio.gui import main_window as main_window_module

    window._start_busy("Running test...")
    window.abort_action.setEnabled(True)
    monkeypatch.setattr(
        window.results_widget, "set_live_result",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(main_window_module.QMessageBox, "warning", lambda *a, **k: None)

    window._on_run_cancelled(ResultSet(scenario_name="test", series={}))  # must not raise

    assert not window._busy_timer.isActive()
    assert window.run_action.isEnabled()
    assert not window.abort_action.isEnabled()


def test_on_run_clears_previous_results_even_when_not_live(window, monkeypatch):
    """Real gap found while investigating the "breaks a lot of things"
    report: results_widget/mission_dashboard_widget were only cleared at
    the start of a new run when Live Plot was on -- a non-live run (or
    one with a mission_sequence) left the PREVIOUS run's plot on screen
    for the entire new run, indistinguishable from this run already
    having (stale, wrong) results before it actually does.
    """
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    stale = ResultSet(scenario_name="stale")
    stale.add(TimeSeries("sat-1.position_N", [0.0, 1.0], ("x", "y", "z"),
                          [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], units="m"))
    window.results_widget.set_result(stale)
    assert len(window.results_widget.plot_names()) == 1

    window.live_plot_action.setChecked(False)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)  # don't actually spin up the thread

    window.on_run()

    assert window.results_widget.plot_names() == []


def test_on_run_captures_epoch_and_passes_it_to_results_widget(window, monkeypatch):
    """Run remembers the scenario's epoch at the time it starts."""
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    window.scenario_editor.epoch_edit.setText("2031-05-01T00:00:00")
    monkeypatch.setattr(RunWorker, "start", lambda self: None)  # don't actually spin up the thread

    window.on_run()

    assert window._last_run_epoch_utc == "2031-05-01T00:00:00"


def test_run_finished_passes_captured_epoch_to_results_widget(window):
    """A finished run gives the Results page the epoch captured when it
    started."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    window._last_run_epoch_utc = "2032-01-01T00:00:00"
    result = ResultSet(scenario_name="test")
    result.add(TimeSeries("sat-1.position_N", [0.0, 1.0], ("x", "y", "z"),
                           [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], units="m"))

    window._on_run_finished(result)

    assert window.results_widget._epoch_utc == "2032-01-01T00:00:00"


def test_run_finished_stops_busy_indicator_and_reenables_actions(window):
    """A finished run stops the busy indicator and enables Run and Monte
    Carlo."""
    from spacemissionstudio.engine.results import ResultSet

    window._start_busy("Running test...")
    window._on_run_finished(ResultSet(scenario_name="test", series={}))
    assert not window._busy_timer.isActive()
    assert window.run_action.isEnabled()
    assert window.monte_carlo_action.isEnabled()


def test_run_failed_stops_busy_indicator_and_reenables_actions(window, monkeypatch):
    """A failed run stops the busy indicator and enables Run and Monte
    Carlo."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    window._start_busy("Running test...")
    window._on_run_failed("boom")
    assert not window._busy_timer.isActive()
    assert window.run_action.isEnabled()
    assert window.monte_carlo_action.isEnabled()


def test_run_failed_dialog_mentions_the_log_file_when_configured(window, monkeypatch):
    """Direct user feedback: a bare error message with nothing else to go
    on (e.g. a raw C++ exception's str()) left no way to actually
    diagnose an unexpected failure -- see logging_setup's own module
    docstring. Once logging is configured (real entry points always do
    this; a bare MainWindow() in a test does not, by default -- see the
    test right after this one for that case), the error must say where
    the full traceback landed. It goes to the Log, which opens at its
    errors (U-23), rather than a message box.
    """
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    fake_log_path = Path("/tmp/fake/spacemissionstudio_20300101T000000Z.log")
    monkeypatch.setattr(main_window, "get_log_file_path", lambda: fake_log_path)

    window._on_run_failed("boom")

    assert len(window.run_problems) == 1
    shown_message = window.run_problems[0]
    assert "boom" in shown_message
    assert str(fake_log_path) in shown_message
    assert window.current_view() is window.log_widget


def test_run_failed_dialog_omits_the_log_hint_when_logging_was_never_configured(window, monkeypatch):
    """Without a log file there is no path to name: the message is just the error."""
    from spacemissionstudio.gui import main_window

    monkeypatch.setattr(main_window, "get_log_file_path", lambda: None)

    window._on_run_failed("boom")

    assert window.run_problems == ["Run failed: boom"]


def test_monte_carlo_failed_dialog_mentions_the_log_file_when_configured(window, monkeypatch):
    """A failed Monte Carlo batch names the log file, like a failed run."""
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    fake_log_path = Path("/tmp/fake/spacemissionstudio_20300101T000000Z.log")
    monkeypatch.setattr(main_window, "get_log_file_path", lambda: fake_log_path)

    window._on_monte_carlo_failed("boom")

    assert str(fake_log_path) in window.run_problems[0]


def test_run_monte_carlo_rejects_disabled_monte_carlo(window):
    """Monte Carlo turned off: said once, and the Monte Carlo page opens
    where it is turned on."""
    _add_valid_spacecraft(window)  # monte_carlo defaults to disabled

    window.on_run_monte_carlo()
    assert len(window.run_problems) == 1
    assert "enable monte carlo" in window.run_problems[0].lower()
    assert window._mc_worker is None


def test_run_monte_carlo_starts_worker_with_chosen_archive_dir(window, monkeypatch, tmp_path):
    """Monte Carlo starts its worker with the chosen archive folder and run
    count, disables both run actions and starts the busy indicator."""
    from spacemissionstudio.gui.run_worker import MonteCarloWorker
    from spacemissionstudio.schema.scenario import DispersionConfig, MonteCarloConfig
    from PySide6.QtWidgets import QFileDialog

    _add_valid_spacecraft(window)
    window.scenario_editor.monte_carlo_group.set_spacecraft_names(["sat-1"])
    window.scenario_editor.monte_carlo_group.from_dataclass(MonteCarloConfig(
        enabled=True, num_runs=3,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=[90, 110])],
    ))

    archive_dir = tmp_path / "mc_archive"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(archive_dir)))
    monkeypatch.setattr(MonteCarloWorker, "start", lambda self: None)  # don't actually spin up the thread

    window.on_run_monte_carlo()
    assert window._mc_worker is not None
    assert window._mc_worker.archive_dir == archive_dir
    assert window._mc_worker.mc_config.num_runs == 3
    assert not window.monte_carlo_action.isEnabled()
    assert not window.run_action.isEnabled()  # can't start a second run while one is in flight
    assert window._busy_timer.isActive()


def _enable_monte_carlo(window):
    from spacemissionstudio.schema.scenario import DispersionConfig, MonteCarloConfig

    _add_valid_spacecraft(window)
    window.scenario_editor.monte_carlo_group.set_spacecraft_names(["sat-1"])
    window.scenario_editor.monte_carlo_group.from_dataclass(MonteCarloConfig(
        enabled=True, num_runs=2,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=[90, 110])],
    ))


def test_run_monte_carlo_refuses_a_folder_holding_other_files(window, monkeypatch, tmp_path):
    """Audit M10: the batch must never mix with (or be mistaken for) other files."""
    from PySide6.QtWidgets import QFileDialog

    _enable_monte_carlo(window)
    (tmp_path / "notes.txt").write_text("mine", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))

    window.on_run_monte_carlo()
    assert window._mc_worker is None
    assert "empty folder" in window.run_problems[0]


def test_run_monte_carlo_asks_before_replacing_an_earlier_batch(window, monkeypatch, tmp_path):
    """A folder holding an earlier batch is replaced only after the user
    agrees: No starts nothing, Yes starts a worker that overwrites."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from spacemissionstudio.gui.run_worker import MonteCarloWorker

    _enable_monte_carlo(window)
    for name in ("MonteCarlo.data", "run0.data", "run0.json", "batch_results.json", "batch_results.npz"):
        (tmp_path / name).write_bytes(b"old")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(MonteCarloWorker, "start", lambda self: None)
    answers = [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]
    # Discard once the two answers are used: closing the window at teardown asks too.
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: answers.pop(0) if answers else QMessageBox.StandardButton.Discard))

    window.on_run_monte_carlo()  # declined
    assert window._mc_worker is None
    window.on_run_monte_carlo()  # accepted
    assert window._mc_worker is not None and window._mc_worker.overwrite


def test_run_monte_carlo_asks_consent_for_script_blocks(window, monkeypatch, tmp_path):
    """Audit H1: every Monte Carlo run now flies the Mission Sequence, so its
    script blocks need the same consent as Run Simulation."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.run_worker import MonteCarloWorker
    from spacemissionstudio.schema.command import Command

    _enable_monte_carlo(window)
    window.scenario_editor.mission_sequence_editor.from_command_list([
        Command(kind="propagate", params={"duration_days": 0.01}),
        Command(kind="script_block", params={"code": "pass"}),
    ])
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path / "mc")))
    monkeypatch.setattr(MonteCarloWorker, "start", lambda self: None)
    consent = [False, True]
    monkeypatch.setattr(window, "_confirm_script_blocks", lambda blocks: consent.pop(0))

    window.on_run_monte_carlo()
    assert window._mc_worker is None
    window.on_run_monte_carlo()
    assert window._mc_worker is not None and window._mc_worker.allow_scripts


def test_monte_carlo_finished_stops_busy_indicator_and_reenables_actions(window):
    """A finished Monte Carlo batch stops the busy indicator and enables both
    run actions."""
    window._start_busy("Running Monte Carlo test...")
    window._on_monte_carlo_finished([])
    assert not window._busy_timer.isActive()
    assert window.run_action.isEnabled()
    assert window.monte_carlo_action.isEnabled()


def test_monte_carlo_finished_with_no_failures_shows_a_toast(window):
    """Regression guard: found while checking this tab's feedback for
    consistency -- _on_run_finished (the single-run sibling) already
    shows a toast on success, but this Monte Carlo equivalent had none
    at all.
    """
    window._start_busy("Running Monte Carlo test...")
    window._on_monte_carlo_finished([])

    toasts = getattr(window, "_spacemissionstudio_active_toasts", [])
    assert any("Monte Carlo complete" in t.text() for t in toasts)


def test_monte_carlo_finished_with_failures_does_not_show_a_toast(window, monkeypatch):
    """The QMessageBox.warning already shown for a partial failure is
    strong enough feedback on its own -- same reasoning as
    _on_run_failed having no toast alongside its own QMessageBox.critical.
    """
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    window._start_busy("Running Monte Carlo test...")
    window._on_monte_carlo_finished([2])

    toasts = getattr(window, "_spacemissionstudio_active_toasts", [])
    assert not any("Monte Carlo complete" in t.text() for t in toasts)


def test_monte_carlo_failed_stops_busy_indicator_and_reenables_actions(window, monkeypatch):
    """A failed Monte Carlo batch stops the busy indicator and enables both run
    actions."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    window._start_busy("Running Monte Carlo test...")
    window._on_monte_carlo_failed("boom")
    assert not window._busy_timer.isActive()
    assert window.run_action.isEnabled()
    assert window.monte_carlo_action.isEnabled()


def test_run_monte_carlo_cancel_dialog_does_not_start_worker(window, monkeypatch):
    """Cancelling the archive-folder dialog starts no Monte Carlo worker."""
    from spacemissionstudio.schema.scenario import MonteCarloConfig
    from PySide6.QtWidgets import QFileDialog

    _add_valid_spacecraft(window)
    window.scenario_editor.monte_carlo_group.set_spacecraft_names(["sat-1"])
    window.scenario_editor.monte_carlo_group.from_dataclass(MonteCarloConfig(enabled=True))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))

    window.on_run_monte_carlo()
    assert window._mc_worker is None


def test_run_with_mission_sequence_ignores_live_flag_and_shows_mission_output(window, monkeypatch):
    """A run with a mission sequence is never live, whatever the Live plot
    toggle says (MissionEngine has no live mode)."""
    from spacemissionstudio.gui.run_worker import RunWorker
    from spacemissionstudio.schema.command import Command

    _add_valid_spacecraft(window)
    window.scenario_editor.mission_sequence_editor.from_command_list([
        Command(kind="script_block", params={"code": "pass"}),
    ])
    window.scenario_editor.changed.emit()

    captured = {}
    original_init = RunWorker.__init__

    def spy_init(self, scenario, vizard_request=None, live=False, parent=None, allow_scripts=False):
        captured["live"] = live
        captured["allow_scripts"] = allow_scripts
        original_init(self, scenario, vizard_request=vizard_request, live=live, parent=parent,
                      allow_scripts=allow_scripts)

    monkeypatch.setattr(RunWorker, "__init__", spy_init)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)
    monkeypatch.setattr(type(window), "_confirm_script_blocks", lambda self, blocks: True)

    window.live_plot_action.setChecked(True)
    window.on_run()

    # MissionEngine has no run_live() equivalent (see RunWorker.run()) --
    # a mission_sequence run always ignores the live-plot toggle.
    assert captured["live"] is False


def test_script_blocks_run_only_after_the_user_confirms(window, monkeypatch):
    """SRS-S-03: a scenario with a script_block asks first. Declining
    starts nothing; confirming starts the run with the consent passed on."""
    from spacemissionstudio.gui.run_worker import RunWorker
    from spacemissionstudio.schema.command import Command

    _add_valid_spacecraft(window)
    window.scenario_editor.mission_sequence_editor.from_command_list([
        Command(kind="script_block", label="mine", params={"code": "print('hello')"}),
    ])
    window.scenario_editor.changed.emit()
    started, asked = [], []
    monkeypatch.setattr(RunWorker, "start", lambda self: started.append(self.allow_scripts))

    monkeypatch.setattr(type(window), "_confirm_script_blocks", lambda self, blocks: asked.append(blocks) or False)
    window.on_run()
    assert started == []
    assert [path for path, _ in asked[0]] == ["mission_sequence[0]"]

    monkeypatch.setattr(type(window), "_confirm_script_blocks", lambda self, blocks: True)
    window.on_run()
    assert started == [True]


def test_script_block_confirmation_shows_the_code_and_defaults_to_no(window, monkeypatch):
    """The confirmation lists each block's path and code, and No is the
    default button."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.schema.command import Command

    seen = {}

    def fake_exec(box):
        seen["details"] = box.detailedText()
        seen["default"] = box.defaultButton() is box.button(QMessageBox.StandardButton.No)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    block = Command(kind="script_block", label="mine", params={"code": "print('hello')"})
    assert window._confirm_script_blocks([("mission_sequence[0]", block)]) is False
    assert "mission_sequence[0] (mine): 14 characters, SHA-256 " in seen["details"]
    assert "print('hello')" in seen["details"]
    assert seen["default"]


def test_script_block_confirmation_shows_all_of_a_long_block(window, monkeypatch):
    """Audit R3: only the first 600 characters were shown, with no sign of
    the cut, and Yes ran all of it. The whole code is shown now, with its
    length and SHA-256, so a payload after harmless lines is seen."""
    import hashlib

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.schema.command import Command

    seen = {}
    monkeypatch.setattr(QMessageBox, "exec", lambda box: seen.setdefault("details", box.detailedText())
                        and QMessageBox.StandardButton.No)
    code = "x = 1\n" * 200 + "import shutil; shutil.rmtree('/')\n"  # the payload after 1200 harmless characters
    block = Command(kind="script_block", params={"code": code})
    assert window._confirm_script_blocks([("mission_sequence[2]", block)]) is False
    assert code in seen["details"]
    assert f"{len(code)} characters, SHA-256 {hashlib.sha256(code.encode()).hexdigest()}" in seen["details"]


def test_run_finished_with_command_summary_shows_mission_output_tab(window):
    """A finished mission-sequence run switches to Mission Output, which counts
    the commands run."""
    from spacemissionstudio.engine.results import CommandSummary, ReportEntry, ResultSet

    summary = CommandSummary(reports=[ReportEntry(label="x", t_s=1.0, values={})], commands_executed=1)
    window._on_run_finished(ResultSet(scenario_name="test", series={}), summary)
    window.finish_run_end()  # M6b: the end of a run is shown in steps; take them

    assert window.current_view() is window.mission_output_widget
    assert "1 command run" in window.mission_output_widget.summary_label.text()


def test_run_finished_without_command_summary_shows_results_tab(window):
    """A finished plain run switches to the Results page."""
    from spacemissionstudio.engine.results import ResultSet

    window.show_view(window.lifetime_widget)  # some page other than the run views
    window._on_run_finished(ResultSet(scenario_name="test", series={}))
    window.finish_run_end()  # M6b: the end of a run is shown in steps; take them
    assert window.current_view() is window.results_widget


class _FakeVizardProcess:
    def __init__(self, pid=999):
        self.pid = pid
        self._alive = True
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self):
        return None if self._alive else 0

    def kill_for_test(self):
        self._alive = False

    def terminate(self):
        self.terminate_calls += 1
        self._alive = False

    def kill(self):
        self.kill_calls += 1
        self._alive = False

    def wait(self, timeout=None):
        return 0


def test_launch_vizard_starts_it_when_not_running(window, monkeypatch):
    """Launch Vizard starts the found executable and says so in the status
    bar."""
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    calls = []
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: calls.append(path) or _FakeVizardProcess())

    window.on_launch_vizard()

    assert calls == [Path("/fake/Vizard")]
    assert "Launched Vizard" in window.statusBar().currentMessage()


def test_launch_vizard_does_not_relaunch_while_already_running(window, monkeypatch):
    """The exact behavior the "Launch Vizard" action depends on: clicking
    it again while Vizard is still open must not spawn a second instance.
    """
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    calls = []
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: calls.append(path) or _FakeVizardProcess())

    window.on_launch_vizard()
    window.on_launch_vizard()
    window.on_launch_vizard()

    assert len(calls) == 1
    assert "already running" in window.statusBar().currentMessage().lower()


def test_launch_vizard_relaunches_after_the_process_exits(window, monkeypatch):
    """After Vizard exits, Launch Vizard starts a new process."""
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    processes = [_FakeVizardProcess(pid=111), _FakeVizardProcess(pid=222)]
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    monkeypatch.setattr(main_window, "launch_vizard", lambda path, direct_comm_address=None: processes.pop(0))

    window.on_launch_vizard()
    first = window._vizard_process
    first.kill_for_test()

    window.on_launch_vizard()
    assert window._vizard_process.pid == 222


def test_launch_vizard_not_found_falls_back_to_browse(window, monkeypatch):
    """`on_launch_vizard()`'s own contract once `find_vizard_executable()`
    comes up empty: whatever `_locate_vizard()` resolves to (via either
    its "Download" or "Browse..." path -- see the dedicated tests for
    those below) gets launched. Mocked at that seam rather than
    QFileDialog directly, since which of the two sub-paths the user took
    is no longer this test's concern.
    """
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    picked = Path("/picked/Vizard")
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: None)
    monkeypatch.setattr(main_window.MainWindow, "_locate_vizard", lambda self: picked)
    monkeypatch.setattr(main_window, "launch_vizard", lambda path, direct_comm_address=None: _FakeVizardProcess())

    window.on_launch_vizard()

    assert window._vizard_process is not None


def test_launch_vizard_not_found_and_resolution_cancelled_does_nothing(window, monkeypatch):
    """When Vizard is not found and the user cancels locating it, nothing is
    launched."""
    from spacemissionstudio.gui import main_window

    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: None)
    monkeypatch.setattr(main_window.MainWindow, "_locate_vizard", lambda self: None)
    launch_calls = []
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: launch_calls.append(path))

    window.on_launch_vizard()

    assert launch_calls == []
    assert window._vizard_process is None


def test_locate_vizard_browse_option_remembers_the_picked_path(window, monkeypatch):
    """The original manual-browse path, now reached via the "not found"
    QMessageBox's "Browse..." button -- clicked here by text match (see
    this test's own `_click` helper) rather than assuming a specific
    button object, since QMessageBox builds its buttons fresh each call.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    picked = Path("/picked/Vizard")
    monkeypatch.setattr(QMessageBox, "exec", _click_message_box_button("Browse..."))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(picked), "")))
    remembered = []
    monkeypatch.setattr("spacemissionstudio.gui.main_window.remember_vizard_executable",
                         lambda path: remembered.append(path))

    result = window._locate_vizard()

    assert result == picked
    assert remembered == [picked]


def test_locate_vizard_browse_cancelled_returns_none(window, monkeypatch):
    """Cancelling the Browse dialog while locating Vizard returns no path."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    monkeypatch.setattr(QMessageBox, "exec", _click_message_box_button("Browse..."))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))

    assert window._locate_vizard() is None


def test_locate_vizard_dismissed_returns_none(window, monkeypatch):
    """Neither "Download Vizard" nor "Browse..." clicked (e.g. the dialog
    was closed via its window decoration) -- QMessageBox's own
    `clickedButton()` then returns its implicit Cancel button, which
    matches neither of the two named buttons this method checks for.
    """
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)  # never click anything

    assert window._locate_vizard() is None


class _FakeVizardFetchWorker(QObject):
    """Stands in for ``VizardFetchWorker`` without spinning up a real
    ``QThread`` -- mirrors this test file's own ``RunWorker``-patching
    convention (``monkeypatch.setattr(RunWorker, "start", ...)``) rather
    than exercising real threading/network in a unit test. Signals are
    emitted synchronously from :meth:`start`, exactly as they would be
    for a worker whose background thread happened to finish before the
    caller's nested ``QEventLoop`` even started spinning -- a real,
    documented-safe case for ``QEventLoop`` (``quit()`` before ``exec()``
    just makes the next ``exec()`` return immediately), not a test-only
    shortcut.
    """

    finished_ok = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, outcome_path=None, outcome_error=None, parent=None):
        super().__init__(parent)
        self._outcome_path = outcome_path
        self._outcome_error = outcome_error
        self.cancel_requested = False

    def request_cancel(self):
        self.cancel_requested = True

    def start(self):
        if self._outcome_error is not None:
            self.failed.emit(self._outcome_error)
        else:
            self.finished_ok.emit(self._outcome_path)

    def wait(self):
        pass


def test_fetch_vizard_with_progress_success_remembers_and_returns_the_path(window, monkeypatch):
    """A successful Vizard download returns the executable's path and remembers
    it."""
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    fetched = Path("/fetched/Vizard")
    monkeypatch.setattr(main_window, "VizardFetchWorker",
                         lambda parent=None: _FakeVizardFetchWorker(outcome_path=str(fetched)))
    remembered = []
    monkeypatch.setattr(main_window, "remember_vizard_executable", lambda path: remembered.append(path))

    result = window._fetch_vizard_with_progress()

    assert result == fetched
    assert remembered == [fetched]


def test_fetch_vizard_with_progress_failure_shows_error_and_returns_none(window, monkeypatch, reported):
    """A failed Vizard download returns no path and reports the reason as an
    error, without a message box."""
    from spacemissionstudio.gui import main_window

    monkeypatch.setattr(main_window, "VizardFetchWorker",
                         lambda parent=None: _FakeVizardFetchWorker(outcome_error="could not download: boom"))

    result = window._fetch_vizard_with_progress()

    assert result is None
    assert reported == [("Could not download Vizard: could not download: boom", "error")]  # the reason, no box


def _click_message_box_button(button_text):
    """Returns a replacement for ``QMessageBox.exec`` that, instead of
    actually blocking on user input, finds one of the box's own
    ``addButton()``-added buttons by its visible text and clicks it --
    exercising the real ``clickedButton()``/``buttonClicked`` machinery
    (that connection is wired in ``addButton()`` itself, not only while
    ``exec()`` is actually running) rather than faking the outcome.
    """
    def _exec(self):
        for button in self.buttons():
            if button.text() == button_text:
                button.click()
                return 0
        raise AssertionError(f"no QMessageBox button with text {button_text!r}")
    return _exec


def test_launch_vizard_failure_shows_error(window, monkeypatch, reported):
    """An OS error launching Vizard is reported with its reason, and no process
    is kept."""
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))

    def raise_oserror(path, direct_comm_address=None):
        raise OSError("permission denied")

    monkeypatch.setattr(main_window, "launch_vizard", raise_oserror)

    window.on_launch_vizard()

    assert len(reported) == 1 and reported[0][1] == "error" and "permission denied" in reported[0][0]
    assert window._vizard_process is None


def test_launch_vizard_passes_direct_comm_address_when_live_stream_configured(window, monkeypatch):
    """Direct user feedback: manually launching Vizard for a live-stream
    run left it sitting on its own manual launcher screen (see
    on_launch_vizard()'s own docstring) -- it must be started with its
    -directComm flag whenever Vizard Configuration is set to live-stream.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui import main_window
    from spacemissionstudio.gui.vizard_launcher import DEFAULT_LIVE_STREAM_ADDRESS

    window._vizard_request = VizardRequest(live_stream=True)
    calls = []
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: calls.append(direct_comm_address)
                         or _FakeVizardProcess())
    # A real launch with a -directComm address shows a one-time
    # "needs one click" info dialog (see on_launch_vizard()'s own
    # comment) -- mocked here since this test is about the address
    # passed to launch_vizard(), not that dialog itself (see
    # test_launch_vizard_shows_the_one_click_hint_once_per_session for
    # that).
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    window.on_launch_vizard()

    assert calls == [DEFAULT_LIVE_STREAM_ADDRESS]


def test_launch_vizard_shows_the_one_click_hint_once_per_session(window, monkeypatch):
    """-directComm pre-fills Vizard's socket address but (confirmed by
    direct user report) does not click "Start Visualization" for the
    user -- shown once per session as an info dialog so that one
    remaining click isn't a silent surprise, but not repeated on every
    single subsequent live-stream launch/run. A long info toast since
    U-39, not a message box.
    """
    from pathlib import Path

    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui import main_window

    window._vizard_request = VizardRequest(live_stream=True)
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: _FakeVizardProcess())
    info_calls = []
    real_toast = main_window.show_toast
    monkeypatch.setattr(main_window, "show_toast",
                        lambda parent, message, kind="success", **k: info_calls.append((message, kind))
                        or real_toast(parent, message, kind, **k))

    assert not window._vizard_live_stream_hint_shown
    window.on_launch_vizard()
    assert len(info_calls) == 1
    assert "Start Visualization" in info_calls[0][0] and info_calls[0][1] == "info"
    assert window._vizard_live_stream_hint_shown

    # Vizard process still running -> "already running" early return,
    # no relaunch, no repeated dialog.
    window.on_launch_vizard()
    assert len(info_calls) == 1


def test_launch_vizard_passes_no_direct_comm_address_without_live_stream(window, monkeypatch):
    """Without a live-stream request, Vizard is launched without a
    direct-communication address."""
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    assert window._vizard_request is None  # save-file mode, or never configured at all
    calls = []
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: calls.append(direct_comm_address)
                         or _FakeVizardProcess())

    window.on_launch_vizard()

    assert calls == [None]


def test_launch_vizard_relaunches_a_mismatched_already_running_instance(window, monkeypatch):
    """The known residual gap this closes: Vizard was already launched
    (by this same session's "Launch Vizard" button) before live-stream
    was ever configured -- e.g. for a save-file run, or before Vizard
    Configuration was set at all -- so the running instance has no
    -directComm connection. Simply trusting "already running" here would
    reproduce the exact original bug one launch later; it must be
    terminated and replaced with a live-stream-ready one instead.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui import main_window
    from spacemissionstudio.gui.vizard_launcher import DEFAULT_LIVE_STREAM_ADDRESS

    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    launch_calls = []
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: launch_calls.append(direct_comm_address)
                         or _FakeVizardProcess())
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    # First launch: no live-stream configured yet.
    window.on_launch_vizard()
    first_process = window._vizard_process
    assert launch_calls == [None]

    # Now live-stream gets configured, and Vizard is asked for again.
    window._vizard_request = VizardRequest(live_stream=True)
    window.on_launch_vizard()

    assert first_process.terminate_calls == 1
    assert launch_calls == [None, DEFAULT_LIVE_STREAM_ADDRESS]
    assert window._vizard_process is not first_process
    assert window._vizard_direct_comm_address == DEFAULT_LIVE_STREAM_ADDRESS


def test_launch_vizard_keeps_a_live_stream_ready_instance_for_a_later_save_file_launch(window, monkeypatch):
    """The opposite direction is NOT a mismatch worth relaunching over --
    a -directComm connection doesn't stop Vizard from also being used to
    open a save file, so an already-live-stream-ready instance is kept.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui import main_window

    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    launch_calls = []
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: launch_calls.append(direct_comm_address)
                         or _FakeVizardProcess())
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    window._vizard_request = VizardRequest(live_stream=True)
    window.on_launch_vizard()
    first_process = window._vizard_process

    window._vizard_request = None  # switch to save-file/no request
    window.on_launch_vizard()

    assert first_process.terminate_calls == 0
    assert len(launch_calls) == 1  # never relaunched
    assert window._vizard_process is first_process


def test_launch_vizard_never_touches_an_instance_it_did_not_itself_launch(window, monkeypatch):
    """self._vizard_process is None (this session never launched Vizard
    itself) even though Vizard may well already be running externally --
    there is no reliable way to ask it whether it's connected, so a
    fresh, correctly-configured instance is launched alongside it rather
    than guessing about (or worse, killing) a process this app doesn't
    own.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui import main_window
    from spacemissionstudio.gui.vizard_launcher import DEFAULT_LIVE_STREAM_ADDRESS

    assert window._vizard_process is None
    window._vizard_request = VizardRequest(live_stream=True)
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    launch_calls = []
    monkeypatch.setattr(main_window, "launch_vizard",
                         lambda path, direct_comm_address=None: launch_calls.append(direct_comm_address)
                         or _FakeVizardProcess())
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    window.on_launch_vizard()

    assert launch_calls == [DEFAULT_LIVE_STREAM_ADDRESS]


def test_run_ensures_vizard_is_running_before_a_live_stream_run(window, monkeypatch):
    """Regression test for a real user report: a live-stream run appeared
    to hang at 0% with Abort having no effect, because Vizard was never
    actually connected (see on_run()'s own comment) -- on_run() must
    confirm Vizard first via on_launch_vizard(), not just hand the
    request to RunWorker and hope.
    """
    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    window._vizard_request = VizardRequest(live_stream=True)
    calls = []
    monkeypatch.setattr(MainWindow, "on_launch_vizard", lambda self: calls.append(1) or True)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)  # don't actually spin up the thread

    window.on_run()

    assert calls == [1]
    assert window._run_worker is not None  # the run actually proceeded


def test_run_refuses_to_start_when_vizard_cannot_be_confirmed(window, monkeypatch):
    """A live Vizard stream that cannot be confirmed running stops the run
    before it starts, and says why."""
    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    window._vizard_request = VizardRequest(live_stream=True)
    monkeypatch.setattr(MainWindow, "on_launch_vizard", lambda self: False)
    start_calls = []
    monkeypatch.setattr(RunWorker, "start", lambda self: start_calls.append(1))

    window.on_run()

    assert len(window.run_problems) == 1 and "Vizard is not connected" in window.run_problems[0]
    assert start_calls == []
    assert window._run_worker is None  # never even constructed


def test_run_always_relaunches_vizard_fresh_for_a_live_stream_run(window, monkeypatch):
    """Real user feedback: "when running a new simulation after a
    previous simulation finished, vizard should completely refresh so it
    actually displays only stuff from the current simulation, and not the
    previous one." Confirmed directly from Vizard's own Unity source (see
    on_run()'s own comment): a running Vizard Main Scene has no way to
    reset itself live, so reusing an already-running, matching instance
    across separate runs (on_launch_vizard()'s own deliberate behavior,
    still correct for its OWN "Launch Vizard" menu entry point) must NOT
    happen when on_run() itself starts a new live-stream run -- the
    previous self-launched process must always be terminated and a fresh
    one started, even though it would otherwise "match" and be reused.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.engine.vizard import VizardRequest
    from spacemissionstudio.gui import main_window
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    window._vizard_request = VizardRequest(live_stream=True)
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    launch_calls = []
    processes = [_FakeVizardProcess(pid=1), _FakeVizardProcess(pid=2)]
    monkeypatch.setattr(
        main_window, "launch_vizard",
        lambda path, direct_comm_address=None: launch_calls.append(direct_comm_address) or processes[len(launch_calls) - 1]
    )
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(RunWorker, "start", lambda self: None)

    window.on_run()  # first run: nothing to terminate yet, launches process 1
    first_process = window._vizard_process
    assert first_process is processes[0]
    assert first_process.terminate_calls == 0

    window.on_run()  # second run: must terminate process 1 and launch a fresh one

    assert first_process.terminate_calls == 1
    assert window._vizard_process is processes[1]
    assert window._vizard_process is not first_process
    assert len(launch_calls) == 2


def test_run_never_touches_vizard_without_a_live_stream_request(window, monkeypatch):
    """Vizard Configuration defaults to None (no request at all) --
    on_run() must not try to launch/confirm Vizard for an ordinary run.
    """
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    assert window._vizard_request is None
    calls = []
    monkeypatch.setattr(MainWindow, "on_launch_vizard", lambda self: calls.append(1) or True)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)

    window.on_run()

    assert calls == []


def test_close_with_no_unsaved_changes_does_not_prompt(window, monkeypatch):
    """Closing without unsaved changes closes at once, without asking."""
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    question_calls = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: question_calls.append(1)))

    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


# -- Abort Simulation (direct user feedback: "there should also be the
# option to abort a running simulation, if needed, without breaking the
# tool") -- see gui.run_worker.RunWorker's own module docstring for the
# cooperative-cancellation design these tests exercise the MainWindow
# wiring for.

def test_abort_action_disabled_until_a_run_starts(window):
    """Abort is disabled before any run."""
    assert not window.abort_action.isEnabled()


def test_on_run_enables_abort_action(window, monkeypatch):
    """Starting a run enables Abort."""
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)  # don't actually spin up the thread

    window.on_run()

    assert window.abort_action.isEnabled()


def test_on_run_monte_carlo_never_enables_abort_action(window, monkeypatch):
    """MonteCarloWorker has no request_cancel() -- see abort_action's own
    construction comment in main_window.py -- so a Monte Carlo run must
    never enable it.
    """
    from PySide6.QtWidgets import QFileDialog
    from spacemissionstudio.gui.run_worker import MonteCarloWorker
    from spacemissionstudio.schema.scenario import MonteCarloConfig

    _add_valid_spacecraft(window)
    window.scenario_editor.monte_carlo_group.set_spacecraft_names(["sat-1"])
    window.scenario_editor.monte_carlo_group.from_dataclass(MonteCarloConfig(enabled=True))
    window.scenario_editor.changed.emit()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/mc"))
    monkeypatch.setattr(MonteCarloWorker, "start", lambda self: None)

    window.on_run_monte_carlo()

    assert not window.abort_action.isEnabled()


def test_run_finished_disables_abort_action(window):
    """A finished run disables Abort."""
    from spacemissionstudio.engine.results import ResultSet

    window._start_busy("Running test...")
    window.abort_action.setEnabled(True)
    window._on_run_finished(ResultSet(scenario_name="test", series={}))
    assert not window.abort_action.isEnabled()


def test_run_failed_disables_abort_action(window, monkeypatch):
    """A failed run disables Abort."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    window._start_busy("Running test...")
    window.abort_action.setEnabled(True)
    window._on_run_failed("boom")
    assert not window.abort_action.isEnabled()


def test_on_abort_run_calls_request_cancel_on_the_running_worker(window, monkeypatch):
    """Abort asks the running worker to cancel and disables itself."""
    from PySide6.QtWidgets import QMessageBox
    from spacemissionstudio.gui.run_worker import RunWorker

    # isRunning() is patched to always return True below (to simulate an
    # in-flight worker without a real thread) -- if that patch is still
    # in effect when qtbot's teardown closes this window, closeEvent()
    # would hit its own real, unmocked "run in progress" QMessageBox and
    # block forever in this offscreen test session waiting for a click
    # that never comes. Mocked here too, same as
    # test_close_while_run_in_progress_is_blocked, so teardown can't hang
    # on it regardless of fixture teardown ordering.
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    _add_valid_spacecraft(window)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)
    window.on_run()
    assert window.abort_action.isEnabled()

    cancel_calls = []
    monkeypatch.setattr(RunWorker, "isRunning", lambda self: True)
    monkeypatch.setattr(RunWorker, "request_cancel", lambda self: cancel_calls.append(1))

    window.on_abort_run()

    assert cancel_calls == [1]
    assert not window.abort_action.isEnabled()


def test_on_abort_run_is_a_no_op_without_a_running_worker(window):
    """Abort without a run does nothing and raises nothing."""
    # No run ever started -- window._run_worker is still None -- must not
    # raise.
    window.on_abort_run()
    assert not window.abort_action.isEnabled()


def test_run_cancelled_updates_results_widget_and_status(window):
    """A cancelled run stops the busy indicator, switches Abort off and Run on,
    plots the partial result with the run's epoch on the Results page and says
    the run was cancelled."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    window._start_busy("Running test...")
    window.abort_action.setEnabled(True)
    window._last_run_epoch_utc = "2032-01-01T00:00:00"
    partial = ResultSet(scenario_name="test")
    partial.add(TimeSeries("sat-1.position_N", [0.0, 1.0], ("x", "y", "z"),
                            [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], units="m"))

    window._on_run_cancelled(partial)
    window.finish_run_end()  # M6b: the end of a run is shown in steps; take them

    assert not window._busy_timer.isActive()
    assert not window.abort_action.isEnabled()
    assert window.run_action.isEnabled()
    assert len(window.results_widget.plot_names()) == 1
    assert window.results_widget._epoch_utc == "2032-01-01T00:00:00"
    assert window.current_view() is window.results_widget
    assert window.statusBar().currentMessage() == "Run 1 cancelled."


def test_run_cancelled_with_command_summary_shows_mission_output_tab(window):
    """A cancelled mission-sequence run switches to Mission Output, which
    counts the commands run."""
    from spacemissionstudio.engine.results import CommandSummary, ReportEntry, ResultSet

    summary = CommandSummary(reports=[ReportEntry(label="x", t_s=1.0, values={})], commands_executed=1)
    window._on_run_cancelled(ResultSet(scenario_name="test", series={}), summary)
    window.finish_run_end()  # M6b: the end of a run is shown in steps; take them

    assert window.current_view() is window.mission_output_widget
    assert "1 command run" in window.mission_output_widget.summary_label.text()


def test_end_to_end_cancel_signal_updates_window_without_crashing(window, qtbot, monkeypatch):
    """Drives the real signal/slot connection (RunWorker.cancelled ->
    MainWindow._on_run_cancelled) through a real background QThread,
    matching test_close_while_run_in_progress_is_blocked's approach for
    the same reason: this is the one thing a pure method-call test like
    the ones above can't prove -- that the Signal(object, object) really
    is connected end to end.
    """
    from spacemissionstudio.engine.results import ResultSet
    from spacemissionstudio.gui.run_worker import RunWorker

    _add_valid_spacecraft(window)
    partial = ResultSet(scenario_name="test", series={})

    def fake_run(self):
        self.cancelled.emit(partial, None)

    monkeypatch.setattr(RunWorker, "run", fake_run)

    window.on_run()
    qtbot.waitUntil(lambda: window._run_worker is not None, timeout=5000)
    qtbot.waitUntil(lambda: not window._run_worker.isRunning(), timeout=5000)
    # cancelled is a queued (cross-thread) connection -- the QThread
    # reporting not-running any more doesn't guarantee the GUI thread has
    # actually processed the queued slot invocation yet, so wait on the
    # slot's own observable effect rather than the thread state.
    qtbot.waitUntil(lambda: not window.abort_action.isEnabled(), timeout=5000)

    assert window.statusBar().currentMessage() == "Run 1 cancelled."


def test_about_dialog_shows_version_and_basilisk_status(window, monkeypatch):
    """Regression guard for a real gap found while auditing the rest of
    the app: spacemissionstudio.__version__ already existed (a packaged
    desktop app, shipping .deb/Windows installers), but nothing in the
    GUI surfaced it anywhere -- no Help menu, no About dialog, no
    version visible at all.
    """
    from PySide6.QtWidgets import QMessageBox

    import spacemissionstudio

    calls = []
    monkeypatch.setattr(QMessageBox, "about", staticmethod(lambda *a, **k: calls.append(a)))

    window.on_about()

    assert len(calls) == 1
    shown_text = calls[0][2]
    assert spacemissionstudio.__version__ in shown_text
    assert "Basilisk" in shown_text


# -- autosave / crash recovery (design-philosophy roadmap item M4) ----------

def test_autosave_tick_does_nothing_when_not_dirty(window):
    """Without unsaved changes, the autosave timer writes no recovery file."""
    from spacemissionstudio.gui import autosave

    assert not window._dirty
    window._on_autosave_tick()
    assert autosave.read_recovery_file() is None


def test_autosave_tick_writes_recovery_file_while_dirty(window):
    """With unsaved changes, the autosave timer writes a recovery file holding
    the scenario and no original path."""
    from spacemissionstudio.gui import autosave

    _add_valid_spacecraft(window)
    assert window._dirty

    window._on_autosave_tick()

    info = autosave.read_recovery_file()
    assert info is not None
    assert info.scenario.spacecraft[0].name == "sat-1"
    assert info.original_path is None  # never saved yet in this test


def test_autosave_tick_skips_silently_when_scenario_currently_invalid(window):
    """Mid-edit, the in-memory scenario can be transiently invalid (e.g.
    a spacecraft with an empty name) -- the autosave tick must skip
    that tick quietly rather than popping an error dialog on a timer
    the user never directly triggered.
    """
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig
    from spacemissionstudio.gui import autosave

    window.scenario_editor.spacecraft_list.from_list([
        SpacecraftConfig(name="", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                 velocity_km_s=[0, 7.5, 0]))
    ])
    window.scenario_editor.changed.emit()
    assert window._dirty

    window._on_autosave_tick()  # must not raise

    assert autosave.read_recovery_file() is None


def test_saving_clears_the_recovery_file(window, tmp_path, monkeypatch):
    """Saving removes the recovery file."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui import autosave

    _add_valid_spacecraft(window)
    window._on_autosave_tick()
    assert autosave.read_recovery_file() is not None

    save_path = tmp_path / "scenario.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(save_path), "")))
    window.on_save_as()

    assert autosave.read_recovery_file() is None


def test_discarding_unsaved_changes_clears_the_recovery_file(window, monkeypatch):
    """Discarding unsaved changes (File > New, Discard) removes the recovery
    file."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave

    _add_valid_spacecraft(window)
    window._on_autosave_tick()
    assert autosave.read_recovery_file() is not None

    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window.on_new()

    assert autosave.read_recovery_file() is None


def test_check_autosave_recovery_with_no_recovery_file_does_nothing(window):
    """Without a recovery file, the start-up check changes nothing."""
    window._check_autosave_recovery()  # must not raise, nothing to restore
    assert window._current_path is None
    assert not window._dirty


def test_check_autosave_recovery_user_accepts_restores_and_marks_dirty(window, monkeypatch):
    """Accepting recovery restores the scenario and its original path, still
    marked unsaved."""
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.schema.scenario import OrbitIC, Scenario, SpacecraftConfig

    scenario = Scenario(name="recovered", epoch_utc="2030-01-01T00:00:00Z")
    scenario.spacecraft = [SpacecraftConfig(
        name="recovered-sat", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0])
    )]
    original_path = Path("/does/not/matter/mission.json")
    autosave.write_recovery_file(scenario, original_path)

    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Open))

    window._check_autosave_recovery()

    assert window.scenario_editor.spacecraft_list.to_list()[0].name == "recovered-sat"
    assert window._current_path == original_path
    assert window._dirty  # recovered content is still unsaved -- NOT the same as a clean open
    assert window.windowTitle().endswith("*")


def test_check_autosave_recovery_user_declines_clears_file_and_leaves_editor_untouched(window, monkeypatch):
    """Declining recovery removes the recovery file and leaves the editor empty
    and unchanged."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.schema.scenario import OrbitIC, Scenario, SpacecraftConfig

    scenario = Scenario(name="recovered", epoch_utc="2030-01-01T00:00:00Z")
    scenario.spacecraft = [SpacecraftConfig(
        name="recovered-sat", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0])
    )]
    autosave.write_recovery_file(scenario, None)

    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))

    window._check_autosave_recovery()

    assert window.scenario_editor.spacecraft_list.to_list() == []
    assert not window._dirty
    assert autosave.read_recovery_file() is None


def test_join_finished_worker_waits_out_a_thread_that_already_signalled(qtbot):
    """Regression test: a worker emits its terminal signal from INSIDE
    run(), so Run can be re-enabled while that thread is still returning;
    on_run()/on_run_monte_carlo() replacing the last reference to it then
    made Qt abort the whole app ("QThread: Destroyed while thread is still
    running"). _join_finished_worker() must leave it fully stopped first.
    """
    import threading

    from PySide6.QtCore import QThread, Signal

    from spacemissionstudio.gui.main_window import _join_finished_worker

    release = threading.Event()

    class _SignalsThenLingers(QThread):
        done = Signal()

        def run(self):
            self.done.emit()
            release.wait(5)  # still "returning" after its terminal signal  # [s]

    worker = _SignalsThenLingers()
    with qtbot.waitSignal(worker.done, timeout=5000):
        worker.start()
    assert worker.isRunning()

    threading.Timer(0.05, release.set).start()  # [s]
    _join_finished_worker(worker)
    assert not worker.isRunning()
    _join_finished_worker(None)  # no previous worker: a no-op


def test_explain_tab_title_counts_pre_run_warnings(window, qapp, qtbot):
    """Pre-run checks (engine.scenario_checks) only help if they're seen:
    the Explain tab's own title says when there's something to check."""
    from pathlib import Path

    templates = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
    from spacemissionstudio.schema import load_scenario

    assert window.open_path(next(templates.glob("19_*.json")))
    _explained(window, qtbot)
    assert window.overview_item.text(0) == "Overview"
    late = load_scenario(next(templates.glob("19_*.json")))
    late.epoch_utc = "2030-01-01T00:00:00"  # the old epoch: no Berlin pass in the run
    window.scenario_editor.from_scenario(late)
    window.scenario_editor.changed.emit()
    _explained(window, qtbot)
    assert window.overview_item.text(0) == "Overview (1 to check)"


def test_a_run_hands_the_scenarios_featured_series_to_the_results_tab(window, monkeypatch):
    """The Results tab's one-click suggestions come from the scenario
    being run -- template 19's description names five series."""
    from pathlib import Path

    from spacemissionstudio.engine.series_names import featured_series
    from spacemissionstudio.gui.run_worker import RunWorker
    from spacemissionstudio.schema import load_scenario

    path = next((Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates")
                .glob("19_*.json"))
    assert window.open_path(path)
    monkeypatch.setattr(RunWorker, "start", lambda self: None)  # don't actually spin up the thread
    window.on_run()
    assert window.results_widget._featured == featured_series(load_scenario(path))
    assert len(window.results_widget._featured) == 5


def test_results_offer_the_last_runs_vizard_file_and_open_it(window, monkeypatch, tmp_path):
    """After a run that wrote a playback file, Results shows "Open in
    Vizard", which starts Vizard with -loadFile on that file; a new run
    hides it again."""
    from pathlib import Path

    from spacemissionstudio.gui import main_window

    playback = tmp_path / "run.bin"
    playback.write_bytes(b"\x00")
    window._last_run_vizard_file = str(playback)
    window._offer_vizard_playback()
    assert window.results_widget.vizard_button.isVisibleTo(window.results_widget)
    calls = []
    monkeypatch.setattr(main_window, "find_vizard_executable", lambda: Path("/fake/Vizard"))
    monkeypatch.setattr(main_window, "launch_vizard",
                        lambda path, load_file=None: calls.append((path, load_file)) or _FakeVizardProcess())
    window.results_widget.vizard_button.click()
    assert calls == [(Path("/fake/Vizard"), playback)]
    window._clear_run_views()
    assert not window.results_widget.vizard_button.isVisibleTo(window.results_widget)


def test_no_vizard_button_when_the_run_wrote_no_file(window, tmp_path):
    """When the run's Vizard file does not exist, the Results page offers no
    Vizard playback button."""
    window._last_run_vizard_file = str(tmp_path / "missing.bin")
    window._offer_vizard_playback()
    assert not window.results_widget.vizard_button.isVisibleTo(window.results_widget)


def test_finished_runs_are_kept_for_comparison(window):
    """Each finished or cancelled run joins the session's history, and the
    Results tab offers the earlier ones (UX/UI guidelines, run comparison)."""
    import numpy as np

    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    window._last_run_scenario = window.scenario_editor.draft_scenario()
    window._last_run_epoch_utc = window._last_run_scenario.epoch_utc
    for _ in range(2):
        result = ResultSet("r")
        result.add(TimeSeries("sat-1.position_N", np.arange(3.0), ("x", "y", "z"), np.zeros((3, 3)), units="m"))
        window._keep_run(result, cancelled=False)
    assert [r.number for r in window.run_history.runs] == [1, 2]
    assert window.results_widget.compare_combo.findData(1) >= 0
    window._clear_run_views()
    assert not window.results_widget.compare_combo.isVisibleTo(window.results_widget)


def test_the_run_page_says_monte_carlo_is_off_before_run(window):
    """Audit G5: the run mode could be Monte Carlo while the scenario's
    Monte Carlo was off, and Run said so only after the click. The Run
    page's Monte Carlo options now say it is off, with Enable Monte Carlo,
    which turns it on and opens Scenario > Monte Carlo; the note goes when
    Monte Carlo is on."""
    group = window.scenario_editor.monte_carlo_group
    group.enabled_check.setChecked(False)
    window.set_run_mode("monte_carlo")
    window.show_view(window.run_page)
    note = window.run_page.monte_carlo_off
    assert note.isVisibleTo(window.run_page)
    window.run_page.enable_monte_carlo_button.click()
    assert group.enabled_check.isChecked()
    assert not note.isVisibleTo(window.run_page)
    assert window.current_view() is window.scenario_editor
    assert window.scenario_editor.page_tree.current_page() is window.scenario_editor.monte_carlo_page
