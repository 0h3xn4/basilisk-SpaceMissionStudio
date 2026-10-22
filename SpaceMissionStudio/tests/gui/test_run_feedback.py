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


"""Run feedback (docs/ux-audit.md U-18, U-19, U-41, U-46): one Run with a
mode (single run, Monte Carlo, SIL), a progress strip with the phase, the
time elapsed and left and Cancel (Esc), and a Live plot toggle that says
its state."""

import sys
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
    """A main window with template 22 open."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def test_run_starts_the_selected_mode(window, monkeypatch):
    """Ctrl+R's Run starts a single run, the Monte Carlo batch or SIL, as
    the mode beside it says; the mode button names it."""
    started = []
    monkeypatch.setattr(window, "_launch_run", lambda sil=None: started.append("single"))
    monkeypatch.setattr(window, "on_run_monte_carlo", lambda: started.append("monte_carlo"))
    monkeypatch.setattr(window, "_run_sil_mode", lambda: started.append("sil"))
    assert window.run_action.shortcut().toString() == "Ctrl+R"
    for mode, label in (("single", "Single run"), ("monte_carlo", "Monte Carlo"), ("sil", "SIL")):
        window.set_run_mode(mode)
        assert window.run_mode == mode and window.run_mode_button.text().startswith(label)
        window.run_action.trigger()
    assert started == ["single", "monte_carlo", "sil"]


def test_choosing_a_mode_from_the_menu_changes_it(window):
    """Picking Monte Carlo in the mode menu makes Run start it."""
    window.monte_carlo_action.trigger()
    assert window.run_mode == "monte_carlo" and "Monte Carlo" in window.run_action.toolTip()


def test_sil_mode_without_a_spacecraft_that_can_says_so(window, monkeypatch):
    """Template 22 is orbit only: no flight software to run in the loop.
    Run in SIL mode says so and opens the Flight Software page."""
    window.set_run_mode("sil")
    runs = []
    monkeypatch.setattr(window, "_launch_run", lambda sil=None: runs.append(sil))
    window.on_run()
    assert runs == [] and window.current_view() is window.flight_software_widget


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX executable bit")
def test_sil_mode_asks_for_the_program_and_runs(window, monkeypatch, tmp_path):
    """With one spacecraft that can run SIL, Run asks for the program and
    starts the run with it (M5b: asked on Run > Run, not in a dialog)."""
    from spacemissionstudio.gui import fsw_workbench_widget

    monkeypatch.setattr(fsw_workbench_widget, "exportable_reason", lambda scenario, spacecraft: None)
    runs = []
    monkeypatch.setattr(window, "_launch_run", lambda sil=None: runs.append(sil))
    window.set_run_mode("sil")
    window.on_run()
    assert runs == [] and window.current_view() is window.run_page  # the program is not chosen yet
    program = tmp_path / "fsw_host"
    program.write_bytes(b"#!/bin/sh\nexit 0\n")
    program.chmod(0o755)
    form = window.run_page.sil_form
    form.path_edit.setText(str(program))
    form.consent_check.setChecked(True)
    window.on_run()
    assert [(name, options.binary) for name, options in runs] == [("my-sat", str(program.resolve()))]


def test_the_strip_shows_phase_time_and_cancel(window, qtbot):
    """While a run goes the strip shows its phase, percentage, elapsed time
    and, once there is enough to go on, the time left; Cancel stops it."""
    from spacemissionstudio.gui.app_shell import RunProgressStrip

    strip = window.run_progress
    assert isinstance(strip, RunProgressStrip) and not strip.isVisibleTo(window)
    window._start_busy("Running 22...")
    assert strip.isVisibleTo(window) and strip.phase_label.text() == "Running 22"
    assert strip.bar.maximum() == 0  # busy until a fraction arrives
    strip.set_phase("Propagating: day 0.25 of 1")
    strip.set_fraction(0.25)
    assert strip.phase_label.text() == "Propagating: day 0.25 of 1" and strip.bar.value() == 25
    assert strip.time_label.text().startswith("25 % · 0:0")
    strip._elapsed.restart()
    strip._elapsed = _FakeElapsed(8000)  # [ms] 8 s in, a quarter done: about 24 s left
    strip.refresh_time()
    assert strip.remaining_s() == pytest.approx(24.0) and "about 0:24 left" in strip.time_label.text()
    window._stop_busy("Run complete.", "done", "Done")
    assert not strip.isVisibleTo(window)


class _FakeElapsed:
    """A QElapsedTimer stand-in that reports a fixed time."""

    def __init__(self, ms):
        self.ms = ms

    def elapsed(self):
        return self.ms

    def isValid(self):
        return True


def test_no_time_left_is_guessed_too_early(qtbot):
    """Under 2 % or 3 s, or with no fraction, the strip says nothing about
    the time left."""
    from spacemissionstudio.gui.app_shell import RunProgressStrip

    strip = RunProgressStrip()
    qtbot.addWidget(strip)
    strip.start("Running")
    strip._elapsed = _FakeElapsed(10000)  # [ms]
    assert strip.remaining_s() is None
    strip.set_fraction(0.01)
    assert strip.remaining_s() is None
    strip._elapsed = _FakeElapsed(2000)  # [ms]
    strip.set_fraction(0.5)
    assert strip.remaining_s() is None


def test_escape_cancels_a_run(window, monkeypatch):
    """Esc is Cancel Run's shortcut while a run can be cancelled; the strip
    then says it is cancelling."""
    from PySide6.QtGui import QKeySequence

    class _Worker:
        cancelled = False

        def isRunning(self):
            return True

        def request_cancel(self):
            _Worker.cancelled = True

    assert window.abort_action.shortcut() == QKeySequence("Esc") and not window.abort_action.isEnabled()
    window._start_busy("Running")
    window._run_worker = _Worker()
    window.abort_action.setEnabled(True)
    window.abort_action.trigger()
    assert _Worker.cancelled and window.run_progress.cancel_button.text() == "Cancelling..."
    assert not window.run_progress.cancel_button.isEnabled()


def test_a_monte_carlo_batch_counts_its_cases(window, tmp_path):
    """The strip counts a batch's finished cases from their files, and
    says why Cancel is not offered."""
    window._start_busy("Monte Carlo: 0 of 4 cases done", cancellable=False, cancel_note="runs to the end")
    window._mc_archive_dir, window._mc_total = tmp_path, 4
    for case in range(3):
        (tmp_path / f"run{case}.data").write_bytes(b"")
    window._poll_monte_carlo()
    strip = window.run_progress
    assert strip.phase_label.text() == "Monte Carlo: 3 of 4 cases done" and strip.bar.value() == 75
    assert not strip.cancel_button.isEnabled() and strip.cancel_button.toolTip() == "runs to the end"


def test_the_worker_reports_phase_and_fraction_without_live_plot(qtbot, monkeypatch):
    """A run reports its phase and fraction with Live plot off too."""
    from spacemissionstudio.gui.run_worker import RunWorker
    from spacemissionstudio.schema import load_scenario

    worker = RunWorker(load_scenario(_TEMPLATES / "22_starter_first_leo_satellite.json"), live=False)
    phases, fractions = [], []
    worker.phase.connect(phases.append)
    worker.fraction.connect(fractions.append)
    worker._report(0.25, "Propagating")
    assert phases == ["Propagating: day 0.25 of 1"] and fractions == [0.25]


def test_a_mission_sequence_reports_its_steps(qtbot):
    """Each Mission Sequence step is a phase: "Step 2 of 5: ...", and the
    fraction counts the steps done."""
    from spacemissionstudio.gui.run_worker import RunWorker
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio.schema.command import Command

    worker = RunWorker(load_scenario(_TEMPLATES / "22_starter_first_leo_satellite.json"))
    phases, fractions = [], []
    worker.phase.connect(phases.append)
    worker.fraction.connect(fractions.append)
    worker._on_step(2, 4, Command(kind="report", params={"series": []}))
    assert phases == ["Step 2 of 4: Report every series"] and fractions == [0.25]


def test_the_live_plot_toggle_says_its_state(window):
    """Live plot reads "Live plot: on" or "off" (U-46)."""
    assert window.live_plot_action.text() == "Live plot: on"
    window.live_plot_action.setChecked(False)
    assert window.live_plot_action.text() == "Live plot: off"


def test_the_mode_cannot_change_during_a_run(window):
    """While a run goes, Run, the mode button and its modes are disabled."""
    window._start_busy("Running")
    assert not window.run_action.isEnabled() and not window.run_mode_button.isEnabled()
    assert not any(action.isEnabled() for action in window.run_mode_group.actions())
    window._stop_busy("Done.", "done", "Done")
    assert window.run_mode_button.isEnabled() and window.monte_carlo_action.isEnabled()
