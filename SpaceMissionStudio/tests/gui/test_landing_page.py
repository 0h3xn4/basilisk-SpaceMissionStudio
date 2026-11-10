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
"""The landing page at start-up (the owner's request of 2026-11-10): the
window starts on Home with no scenario open and no earlier run listed; the
work areas show an empty state and the scenario's commands are disabled
until a scenario is opened; a stored run comes back with its own scenario
only; the window's size is kept."""

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import run_store
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.gui.run_history import RunHistory

pytestmark = pytest.mark.requires_gui

_TEMPLATE = "01_two_body_circular_orbit.json"
_T = np.arange(0.0, 600.0, 60.0)  # [s]


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """A recovery file of the test's own, never the user's."""
    from spacemissionstudio.gui import autosave

    recovery_dir = tmp_path / "autosave"
    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", recovery_dir)
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", recovery_dir / "recovery.json")


def _new_window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    return window


@pytest.fixture
def window(qtbot, monkeypatch):
    return _new_window(qtbot, monkeypatch)


def _result():
    result = ResultSet("demo")
    result.add(TimeSeries("sat.position_N", _T, ("x", "y", "z"), np.zeros((_T.size, 3)), "m"))
    return result


def _scenario_file(folder: Path, name: str) -> Path:
    """A valid scenario file named ``name`` (template 01, renamed)."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.schema.scenario import load_scenario

    scenario = load_scenario(TEMPLATES_DIR / _TEMPLATE)
    scenario.name = name
    path = folder / f"{name}.json"
    scenario.save(path)
    return path


def _store_runs(*names):
    """One saved run per scenario name, in the run store under the test's home folder."""
    earlier = RunHistory(store_root=run_store.default_root())
    for minute, name in enumerate(names):
        earlier.add({"name": name}, _result(), "", finished=datetime(2026, 11, 9, 17, minute))


def _listed(window):
    """The runs each list shows: Results, Run › History, Compare."""
    window.show_view(window.compare_widget)  # Compare refreshes when shown
    in_results = sorted(run.number for run in window.results_widget._runs)  # the shown run and its Compare with
    in_history = sorted(entry.number for entry in window.history_view.entries() if entry.number is not None)
    in_compare = sorted(run.number for run in window.compare_widget._runs)
    return in_results, in_history, in_compare


def test_the_window_starts_on_home_with_nothing_open(window):
    """At start the window shows Home, says no scenario is open (title and
    top bar), and every other work area shows the empty state instead of
    its header and content."""
    window.show()
    assert not window.scenario_open
    assert window.shell.current_area() == "home"
    assert window.windowTitle() == "SpaceMissionStudio -- no scenario open"
    assert window.top_bar.name_label.text() == "No scenario open"
    assert not window.top_bar.save_button.isEnabled()
    for area_id in ("scenario", "run", "results", "timeline", "reports"):
        window.shell.show_area(area_id)
        page = window.shell.page(area_id)
        assert page.showing_empty
        assert page.empty_state.isVisible() and not page.content.isVisible() and not page.header.isVisible()
        assert "No scenario is open" in page.empty_state.title_label.text()
    assert window.problems_widget.model.rowCount() == 0  # the editor's blank default has nothing to fix


def test_the_scenario_commands_are_disabled_until_a_scenario_is_open(window):
    """Save, Save As, Run, the exports and the scenario's other commands are
    disabled while nothing is open; New, Open, Settings, Help and the
    palette are not. The palette lists the disabled commands greyed and
    does not run them, and offers none of the scenario's pages."""
    disabled = ("file.save", "file.save_as", "file.change_history", "edit.undo", "edit.redo", "run.run",
                "run.mode.monte_carlo", "run.vizard_config", "run.open_monte_carlo", "tools.model_3d",
                "tools.ccsds_export", "analyses.budget", "tools.flight_software", "view.explain")
    for command_id in disabled:
        assert not window.commands.action(command_id).isEnabled(), command_id
    for command_id in ("file.new", "file.open", "file.quit", "help.manual", "help.palette", "help.about",
                       "go.home", "go.results", "run.check_data", "tools.ccsds_check", "view.theme.dark"):
        assert window.commands.action(command_id).isEnabled(), command_id
    assert not window.run_mode_button.isEnabled() and not window.run_mode_control.isEnabled()

    entries = {entry.label: entry for entry in window.palette_entries()}
    assert not entries["File > Save"].enabled and not entries["Run > Run"].enabled
    assert entries["File > New Scenario"].enabled and "Go to > Home" in entries and "Go to > Results" in entries
    assert not any(label.startswith(("Go to > Scenario >", "Go to > Results >", "Show series >"))
                   for label in entries)
    window.commands.action("file.save").trigger()  # a disabled command does nothing (no file dialog)
    assert not window.scenario_open


def test_new_scenario_opens_one_and_enables_its_commands(window):
    """New Scenario (here the Run area's empty state's button) opens a
    scenario: the areas show their content, the commands are enabled, the
    title names it and it has nothing unsaved."""
    window.show()
    window.shell.show_area("run")
    window.no_scenario_states["run"].new_button.click()
    assert window.scenario_open
    assert window.shell.current_area() == "scenario"
    assert window.windowTitle() == "SpaceMissionStudio -- untitled"
    for area_id in ("scenario", "run", "results", "timeline", "reports"):
        page = window.shell.page(area_id)
        assert not page.showing_empty and not page.empty_state.isVisibleTo(window)
    window.shell.show_area("run")
    assert window.shell.page("run").header.isVisible() and window.run_views.isVisible()
    for command_id in ("file.save", "file.save_as", "run.run", "tools.model_3d", "view.explain"):
        assert window.commands.action(command_id).isEnabled(), command_id
    assert window.run_mode_button.isEnabled()
    assert not window._dirty
    assert any(label.startswith("Go to > Scenario >") for label in (e.label for e in window.palette_entries()))


def test_the_empty_state_opens_new_open_and_home(window, tmp_path, monkeypatch):
    """The empty state's buttons: Go to Home shows Home, and its Open button
    opens the file chosen."""
    from PySide6.QtWidgets import QFileDialog

    window.show()
    state = window.no_scenario_states["results"]
    window.shell.show_area("results")
    state.home_button.click()
    assert window.shell.current_area() == "home"

    path = _scenario_file(tmp_path, "from-the-empty-state")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    window.no_scenario_states["timeline"].open_button.click()
    assert window.scenario_open and window._current_path == path
    assert window.windowTitle() == "SpaceMissionStudio -- from-the-empty-state.json"


def test_a_template_and_a_restored_autosave_open_a_scenario(qtbot, monkeypatch):
    """Opening a template from Home opens a scenario; so does accepting the
    crash-recovery prompt, which leaves it unsaved."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.schema.scenario import load_scenario

    window = _new_window(qtbot, monkeypatch)
    window.load_scenario_widget.path_chosen.emit(TEMPLATES_DIR / _TEMPLATE)
    assert window.scenario_open and window.commands.action("run.run").isEnabled()

    autosave.write_recovery_file(load_scenario(TEMPLATES_DIR / _TEMPLATE), None)
    restored = _new_window(qtbot, monkeypatch)
    assert not restored.scenario_open
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Open))
    restored._check_autosave_recovery()
    assert restored.scenario_open and restored._dirty
    assert restored.windowTitle().endswith("untitled*")


def test_a_stored_run_comes_back_with_its_scenario_only(qtbot, monkeypatch, tmp_path):
    """No stored run is listed at start; opening scenario A lists A's stored
    run (Results, Run › History, Compare) and not B's; opening B lists
    B's instead; New lists none. Nothing is deleted from the store."""
    _store_runs("A", "B")  # Run 1 of A, Run 2 of B
    path_a, path_b = _scenario_file(tmp_path, "A"), _scenario_file(tmp_path, "B")
    window = _new_window(qtbot, monkeypatch)
    window.run_history.wait_loaded()
    window._on_runs_loaded()
    assert [run.number for run in window.run_history.runs] == [1, 2]  # read, so new runs number on
    assert _listed(window) == ([], [], [])

    assert window.open_path(path_a)
    assert _listed(window) == ([1], [1], [1])
    assert window.open_path(path_b)
    assert _listed(window) == ([2], [2], [2])
    window.on_new()
    assert _listed(window) == ([], [], [])
    assert window.open_path(path_a)
    assert _listed(window) == ([1], [1], [1])
    assert [saved.number for saved in run_store.load_index(run_store.default_root())] == [1, 2]


def test_a_run_made_since_opening_stays_listed_until_another_scenario_is_opened(qtbot, monkeypatch, tmp_path):
    """A run made with the scenario open is listed while it is open, even
    after a rename; opening another scenario hides it, and reopening its
    scenario lists it again (from the store, by its name)."""
    from spacemissionstudio.schema.scenario import load_scenario

    path_a, path_b = _scenario_file(tmp_path, "A"), _scenario_file(tmp_path, "B")
    window = _new_window(qtbot, monkeypatch)
    window.run_history.wait_loaded()
    assert window.open_path(path_a)
    window._start_busy("Running A...")
    window._stop_busy("Run 1 complete.", "done", "Done")
    window._last_run_scenario = load_scenario(path_a)
    window._keep_run(_result(), cancelled=False)
    window.run_history.wait_for_saves()
    window.scenario_editor.name_edit.setText("A renamed")
    window.scenario_editor.changed.emit()
    assert _listed(window) == ([1], [1], [1])
    assert window.open_path(path_b)
    assert _listed(window) == ([], [], [])
    assert window.open_path(path_a)
    assert _listed(window) == ([1], [1], [1])


def test_the_window_size_is_kept_but_not_the_scenario(qtbot, monkeypatch, tmp_path):
    """Closing keeps the window's size for the next start, but the next
    window starts with nothing open, whatever was open before."""
    first = _new_window(qtbot, monkeypatch)
    first.show()
    first.resize(first.minimumSizeHint().width(), 560)  # [px] the new window's own height is 850 px
    assert first.open_path(_scenario_file(tmp_path, "A"))
    size = first.size()
    first.close()

    second = _new_window(qtbot, monkeypatch)
    second.show()
    # The height as it was (the width is fitted to the 800 px offscreen screen).
    assert second.height() == size.height() == 560  # [px]
    assert not second.scenario_open and second.shell.current_area() == "home"
    assert second.windowTitle() == "SpaceMissionStudio -- no scenario open"
