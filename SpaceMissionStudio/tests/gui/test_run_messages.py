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


"""What a run says when it ends or cannot start (docs/ux-audit.md U-21,
U-22, U-23, U-39): a toast with the run's name, length and events; run
names on the chip, the plots and the provenance line; problems in the
Log, a toast and the status bar rather than a message box."""

import datetime
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


@pytest.fixture
def toasts(monkeypatch):
    """The toasts the main window shows, as ``(message, kind)``."""
    from spacemissionstudio.gui import main_window

    shown = []
    real = main_window.show_toast
    monkeypatch.setattr(main_window, "show_toast",
                        lambda parent, message, kind="success", **k: shown.append((message, kind))
                        or real(parent, message, kind, **k))
    return shown


def _result(name="test"):
    from spacemissionstudio.engine.results import ResultSet, RunProvenance, TimeSeries

    result = ResultSet(scenario_name=name)
    result.add(TimeSeries("sat-1.position_N", [0.0, 60.0], ("x", "y", "z"),  # [s]
                          [[7.0e6, 0.0, 0.0], [7.0e6, 1.0e3, 0.0]], units="m"))  # [m]
    result.provenance = RunProvenance(
        spacemissionstudio_version="9.9.9", basilisk_version="2.12.0",
        run_started_utc="2030-01-01T00:00:00+00:00", integrator="rk4", dynamics_task_rate_s=1.0,  # [s]
    )
    return result


def test_events_summary_counts_each_kind(monkeypatch):
    """ "4 passes, 1 eclipse" in the order of the Events tab; "no events"
    when there were none."""
    from spacemissionstudio.engine import events
    from spacemissionstudio.engine.events import Event
    from spacemissionstudio.gui.main_window import events_summary

    found = [Event("pass", "sat-1", 0.0, 60.0, "Berlin")] * 4 + [Event("eclipse", "sat-1", 0.0, 60.0, "Umbra")]
    monkeypatch.setattr(events, "extract_events", lambda result: found)
    assert events_summary(_result()) == "4 passes, 1 eclipse"
    monkeypatch.setattr(events, "extract_events", lambda result: [])
    assert events_summary(_result()) == "no events"


def test_a_finished_run_says_its_name_length_and_events(window, toasts, monkeypatch):
    """The toast names the run, how long it took and what happened in it;
    the chip and the status bar name the run too."""
    from spacemissionstudio.gui import main_window

    monkeypatch.setattr(main_window, "events_summary", lambda result: "4 passes, 15 eclipses")
    window._start_busy("Running")
    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._on_run_finished(_result(window._last_run_scenario.name))
    message, kind = toasts[-1]
    assert message.startswith("Run 1 complete in ") and message.endswith(": 4 passes, 15 eclipses")
    assert kind == "success"
    assert window.top_bar.chip.text().startswith("Run 1: done in ")
    assert window.statusBar().currentMessage().startswith("Run 1 complete")
    window._start_busy("Running")
    window._on_run_cancelled(_result(window._last_run_scenario.name))
    assert toasts[-1] == ("Run 2 cancelled: what was computed is shown", "info")


def test_compared_runs_are_named_in_the_plot_and_provenance(window):
    """With a run to compare, each trace says which run it is; the
    provenance line starts with the shown run's name and time."""
    for _ in range(2):
        window._last_run_scenario = window.scenario_editor.to_scenario()
        window._keep_run(_result(), cancelled=False)
    results = window.results_widget
    results.set_result(_result())
    shown = window.run_history.latest()
    assert results.provenance_label.text().startswith(f"Run 2, {shown.finished:%H:%M} · SpaceMissionStudio")
    results.compare_combo.setCurrentIndex(results.compare_combo.findData(1))
    names = [trace.name for trace in results.figure.data]
    assert any(name.endswith("(Run 2)") for name in names) and any(name.endswith("(Run 1)") for name in names)


def test_without_a_comparison_traces_keep_their_plain_names(window):
    """One run shown on its own: no run name on its traces."""
    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._keep_run(_result(), cancelled=False)
    window.results_widget.set_result(_result())
    assert not any("(Run" in trace.name for trace in window.results_widget.figure.data)


def test_a_run_name_has_its_number_and_time():
    """RunRecord.name is "Run 2, 12:19"; next_number is the next run's number."""
    from spacemissionstudio.gui.run_history import RunHistory

    history = RunHistory()
    assert history.next_number == 1
    record = history.add({}, _result(), "", finished=datetime.datetime(2030, 1, 1, 12, 19))
    assert record.name == "Run 1, 12:19" and history.next_number == 2


def test_an_invalid_scenario_opens_problems_at_the_field(window, toasts, monkeypatch):
    """Run with a problem in the scenario: no message box; the Problems
    tab opens and the editor goes to the field; a toast says why."""
    from spacemissionstudio.schema.scenario import ScenarioValidationError

    def invalid():
        raise ScenarioValidationError("duration_days must be > 0")

    activated = []
    monkeypatch.setattr(window, "_on_problem_activated", lambda message: activated.append(message))
    monkeypatch.setattr(window.scenario_editor, "to_scenario", invalid)
    window.on_run()
    assert window._run_worker is None
    assert window.side_tabs.currentWidget() is window.problems_widget
    assert activated == ["duration_days must be > 0"]
    assert toasts[-1][0].startswith("Cannot run: ") and toasts[-1][1] == "warning"
    assert window.run_problems[-1].startswith("Cannot run: ")


def test_toasts_sit_above_the_status_bar(window):
    """A toast never covers the status bar's run state and reference data."""
    from spacemissionstudio.gui.feedback import show_toast

    window.resize(1280, 720)  # [px]
    window.show()
    toast = show_toast(window, "Run 1 complete in 5 s: 4 passes, 15 eclipses")
    assert toast.geometry().bottom() < window.statusBar().geometry().top()


def test_a_failed_run_opens_the_log_at_its_errors(window, toasts):
    """A failed run says so in a toast and opens the Log at its errors."""
    window._start_busy("Running")
    window._on_run_failed("boom")
    assert toasts[-1] == ("Run failed: boom", "error")
    assert window.current_view() is window.log_widget
    assert window.top_bar.chip.state == "failed"
