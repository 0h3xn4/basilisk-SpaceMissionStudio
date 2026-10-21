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

"""The app shell's always-visible state (docs/ux-audit.md U-04, U-06,
U-07): the top bar names the scenario, whether it has unsaved changes,
where it came from and the last run; its chip shows the run state; the
status bar shows the Basilisk version, the reference data, the Earth
orientation data and the frames."""

import time
from datetime import datetime
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
    """A main window with template 22 open; closing it discards changes and
    error dialogs return at once."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def test_source_of_names_templates_files_and_new_scenarios(tmp_path):
    """A template is "template NN", any other file its name, a scenario
    never saved nothing."""
    from spacemissionstudio.gui.app_shell import source_of

    assert source_of(_TEMPLATES / "22_starter_first_leo_satellite.json", _TEMPLATES) == "template 22"
    assert source_of(tmp_path / "my_mission.json", _TEMPLATES) == "my_mission.json"
    assert source_of(None, _TEMPLATES) == ""


def test_the_top_bar_names_the_scenario_and_its_state(window):
    """Template 22 as shipped reads "Unchanged · from template 22 · not run
    yet". An edit makes it "Unsaved changes" and renames the scenario in
    the bar."""
    bar = window.top_bar
    assert bar.name_label.text() == window.scenario_editor.name_edit.text().strip()
    assert bar.detail_label.text() == "Unchanged · from template 22 · not run yet"

    window.scenario_editor.name_edit.setText("My first satellite")
    assert bar.name_label.text() == "My first satellite"
    assert bar.detail_label.text().startswith("Unsaved changes · from template 22")


def test_the_top_bar_says_saved_for_a_saved_file(window, tmp_path):
    """After File > Save As to a file of the user's, the bar says "Saved"
    and names that file."""
    path = tmp_path / "my_mission.json"
    window._save_to(path)
    assert window.top_bar.detail_label.text() == "Saved · from my_mission.json · not run yet"


def test_the_chip_follows_a_finished_run(window):
    """Idle at start; "Running" while busy, with the elapsed time; "Run 1:
    done in ..." afterwards, and the top bar keeps the run's name, time,
    state and length (U-22)."""
    from spacemissionstudio.engine.results import ResultSet

    chip = window.run_chip
    assert (chip.state, chip.text()) == ("idle", "No run yet")
    window._start_busy("Running")
    assert chip.state == "running"
    window._run_started_s = time.monotonic() - 65.0  # [s] a run that took a little over a minute
    window._busy_elapsed.restart()
    window._update_busy_elapsed()
    assert chip.text() == "Running 0:00"

    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._on_run_finished(ResultSet(scenario_name=window._last_run_scenario.name))
    assert (chip.state, chip.text()) == ("done", "Run 1: done in 1 min 05 s")
    assert "Run 1 at " in window.top_bar.detail_label.text()
    assert ", done, 1 min 05 s" in window.top_bar.detail_label.text()


def test_the_chip_shows_a_live_run_percentage(window):
    """A run that reports progress shows its percentage on the chip."""
    window._start_busy("Running", determinate=True)
    window._busy_progress.setValue(43)
    window._update_busy_elapsed()
    assert window.run_chip.text() == "Running 43 %"


@pytest.mark.parametrize("handler, state, text", [
    ("failed", "failed", "Failed"),
    ("cancelled", "cancelled", "Run 1: cancelled"),
])
def test_the_chip_shows_failed_and_cancelled_runs(window, handler, state, text):
    """A failed or cancelled run leaves its state on the chip and in the
    top bar's last-run text."""
    from spacemissionstudio.engine.results import ResultSet

    window._start_busy("Running")
    window._last_run_scenario = window.scenario_editor.to_scenario()
    if handler == "failed":
        window._on_run_failed("boom")
    else:
        window._on_run_cancelled(ResultSet(scenario_name=window._last_run_scenario.name))
    assert (window.run_chip.state, window.run_chip.text()) == (state, text)
    assert f", {state}, " in window.top_bar.detail_label.text()


def test_the_chip_rejects_an_unknown_state(qtbot):
    """Only the states the theme styles are accepted."""
    from spacemissionstudio.gui.app_shell import StatusChip

    chip = StatusChip()
    qtbot.addWidget(chip)
    with pytest.raises(ValueError):
        chip.set_state("paused", "Paused")


def _file(status):
    from spacemissionstudio.engine.reference_data import ReferenceFile

    return ReferenceFile(kind="SPICE kernel", name=f"{status}.bsp", status=status)


def test_the_status_bar_items(window, monkeypatch):
    """The qualified Basilisk; all reference data OK or how many files need
    attention (with a warning style); Earth orientation with its high
    accuracy end date, or none and the fallback Earth-fixed frame."""
    from spacemissionstudio import dependencies
    from spacemissionstudio.engine import earth_orientation, reference_data

    items = window.status_items
    monkeypatch.setattr(dependencies, "basilisk_version", lambda: "2.12.0")
    monkeypatch.setattr(dependencies, "basilisk_check", lambda version=None: None)
    monkeypatch.setattr(reference_data, "inventory", lambda: [_file("ok"), _file("ok")])
    monkeypatch.setattr(earth_orientation, "installed", lambda directory=None: ["a kernel"])
    monkeypatch.setattr(earth_orientation, "high_accuracy_until", lambda kernels: datetime(2027, 1, 15))
    items.refresh()
    assert items.basilisk_label.text() == "Basilisk 2.12.0"
    assert items.data_button.text() == "Reference data: all 2 OK"
    assert items.data_button.property("state") == ""
    assert items.earth_orientation_label.text() == "Earth orientation: high accuracy to 2027-01-15"
    assert items.frames_label.text() == "Frames: EME2000 · ITRF93 · UTC"

    monkeypatch.setattr(dependencies, "basilisk_check", lambda version=None: "Basilisk 2.13.0 is not qualified")
    monkeypatch.setattr(reference_data, "inventory", lambda: [_file("ok"), _file("missing"), _file("out of date")])
    monkeypatch.setattr(earth_orientation, "installed", lambda directory=None: [])
    items.refresh()
    assert items.basilisk_label.text() == "Basilisk 2.12.0 (not qualified)"
    assert items.basilisk_label.property("state") == "warning"
    assert items.data_button.text() == "Reference data: 2 of 3 need attention"
    assert items.data_button.property("state") == "warning"
    assert items.earth_orientation_label.text() == "Earth orientation: none (IAU_EARTH)"
    assert items.frames_label.text() == "Frames: EME2000 · IAU_EARTH · UTC"


def test_the_reference_data_item_opens_the_data_dialog(window):
    """Clicking the reference data entry in the status bar opens the
    Reference data dialog, where the files are listed; the main tabs stay
    where they were."""
    window.show_view(window.results_widget)
    assert not window.data_dialog.isVisible()
    window.status_items.data_button.click()
    assert window.data_dialog.isVisible() and window.data_dialog.isAncestorOf(window.data_panel_widget)
    assert window.current_view() is window.results_widget
    window.data_dialog.close()


def test_the_status_bar_follows_the_data_tab(window, monkeypatch):
    """A refresh of the reference data panel (after a download, import or rollback)
    refreshes the status bar's summary too."""
    from spacemissionstudio.engine import reference_data

    monkeypatch.setattr(reference_data, "inventory", lambda: [_file("missing")])
    window.data_panel_widget.refresh()
    assert window.status_items.data_button.text() == "Reference data: 1 of 1 need attention"


def test_a_closed_window_is_freed(qapp, monkeypatch):
    """Nothing the window connects keeps it alive once it is closed and
    dropped. A lambda holding the window on a child's signal did (the status
    bar's reference data item): the window then lived until the interpreter
    exited and its web views were torn down too late, a segfault on exit
    (CI's offline step, PR #50; the same as #48's editor lambda)."""
    import gc
    import weakref

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    # Opening a file is left out: its toast holds the window only until the
    # toast closes, a few seconds later, which is not a leak.
    ref = weakref.ref(window)
    window.close()
    del window
    gc.collect()
    assert ref() is None
