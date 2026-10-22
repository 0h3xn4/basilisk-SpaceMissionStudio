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

"""The end of a run and its record (UI overhaul M5a): a run saved and the
store pruned in a worker, listed at once; Compare refreshed when shown and
Results drawn once; Run > History with each run's status, mode, duration
and provenance; the Log's record of each run."""

import threading
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
    """A main window with template 22 open; closing it discards changes."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    qtbot.waitUntil(lambda: not w.run_history.loading, timeout=10000)
    return w


def _finish_a_run(window, warnings=()):
    from spacemissionstudio.engine.results import ResultSet

    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._start_busy("Running")
    window._on_run_finished(ResultSet(scenario_name=window._last_run_scenario.name, warnings=list(warnings)))


def _saved(window, qtbot):
    qtbot.waitUntil(lambda: not window.run_history.saving, timeout=10000)


# -- the end of a run ------------------------------------------------------------------------------


def test_a_run_is_saved_in_a_worker_and_listed_at_once(window, qtbot, monkeypatch):
    """The run is listed when it ends; it is saved, and the store pruned, in
    another thread, and History says "Saving..." until it is on disk."""
    from spacemissionstudio.engine import run_store

    threads, gate = [], threading.Event()
    real_save = run_store.save

    def slow_save(*args, **kwargs):
        threads.append(threading.current_thread())
        gate.wait(10)
        return real_save(*args, **kwargs)

    monkeypatch.setattr(run_store, "save", slow_save)
    _finish_a_run(window)
    record = window.run_history.runs[-1]
    assert record.number == 1 and record.saved is None
    assert window.history_view.entries()[0].saved == "Saving..."
    gate.set()
    _saved(window, qtbot)
    assert threads and threads[0] is not threading.main_thread()
    assert record.saved is not None
    assert window.history_view.entries()[0].saved == "Saved"


def test_closing_waits_for_a_run_being_saved(window, qtbot, monkeypatch):
    """A run that ended just before the window closes is on disk after it."""
    from spacemissionstudio.engine import run_store

    real_save = run_store.save
    monkeypatch.setattr(run_store, "save", lambda *a, **k: (threading.Event().wait(0.3), real_save(*a, **k))[1])
    _finish_a_run(window)
    record = window.run_history.runs[-1]
    window._mark_clean()
    assert window.close()
    assert record.saved is not None
    assert [saved.number for saved in run_store.load_index(window.run_history.store_root)] == [1]


def test_compare_is_refreshed_when_shown_not_at_the_end_of_a_run(window, monkeypatch):
    """Compare's plot took 58-113 ms at the end of every run: it is
    refreshed when it is shown, once."""
    calls = []
    real = window.compare_widget.set_runs
    monkeypatch.setattr(window.compare_widget, "set_runs", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    window.show_view(window.results_widget)
    _finish_a_run(window)
    assert calls == []
    window.show_view(window.compare_widget)
    assert calls == [1] and window.compare_widget.run_list.count() == 1


def test_results_are_drawn_once_at_the_end_of_a_run(window, monkeypatch):
    """With nothing compared, keeping the run does not draw the plots a
    second time."""
    calls = []
    real = window.results_widget._redraw
    monkeypatch.setattr(window.results_widget, "_redraw", lambda: (calls.append(1), real())[1])
    _finish_a_run(window)
    assert len(calls) == 1


# -- Run > History ---------------------------------------------------------------------------------


def test_history_lists_a_run_with_its_status_mode_and_duration(window, qtbot):
    """A finished run: Done, Single, "Run 1", how long it took; its
    double-click shows Results. The empty state has Run."""
    view = window.history_view
    assert view.empty.isVisibleTo(view) and not view.table.isVisibleTo(view)
    assert view.empty_run_button.property("variant") == "primary"
    _finish_a_run(window)
    _saved(window, qtbot)
    entry = view.entries()[0]
    assert (entry.status, entry.mode, entry.number, entry.saved) == ("done", "Single", 1, "Saved")
    assert entry.duration_s is not None and entry.duration_s >= 0  # [s]
    model = view.model
    texts = [model.text(entry, column) for column in range(model.columnCount())]
    assert texts[:4] == ["Done", "Run 1", window._last_run_scenario.name, "Single"]
    assert texts[5].endswith(" s")
    view.table.doubleClicked.emit(view.proxy.index(0, 0))
    assert window.current_view() is window.results_widget


def test_a_failed_run_and_a_batch_are_listed_for_the_session(window):
    """The run store keeps neither: History lists them for the session, a
    failure with its message."""
    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._start_busy("Running")
    window._on_run_failed("boom")
    entry = window.history_view.entries()[0]
    assert (entry.status, entry.mode, entry.saved, entry.detail) == ("failed", "Single", "Not kept", "boom")
    assert entry.started_utc.endswith("Z")
    window._add_history_extra("partial", "Monte Carlo", "20 runs, 2 failed; saved in /tmp/batch")
    statuses = [e.status for e in window.history_view.entries()]
    assert sorted(statuses) == ["failed", "partial"]


def test_history_lists_earlier_runs_read_in_a_worker(qtbot, monkeypatch, tmp_path):
    """The runs of an earlier session are read in a worker and listed:
    saved, their mode not recorded."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.engine import run_store
    from spacemissionstudio.engine.results import ResultSet
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.run_history import RunHistory

    earlier = RunHistory(store_root=run_store.default_root())
    earlier.add({"name": "yesterday"}, ResultSet(scenario_name="yesterday"), "",
                finished=datetime(2026, 10, 13, 17, 0))
    threads = []
    real = run_store.load_index
    monkeypatch.setattr(run_store, "load_index", lambda root: (threads.append(threading.current_thread()),
                                                               real(root))[1])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: bool(window.history_view.entries()), timeout=10000)
    assert threads and threads[0] is not threading.main_thread()
    entry = window.history_view.entries()[0]
    assert (entry.scenario, entry.saved, entry.mode, entry.number) == ("yesterday", "Saved", "", 1)
    assert window.history_view.model.text(entry, 3) == "-"


def test_a_runs_provenance_opens_in_a_popover_and_rows_copy(window, qtbot):
    """Provenance shows the selected run's in a popover; Copy and Ctrl+C put
    the rows on the clipboard as tab-separated text with the header."""
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.run_history_view import HISTORY_COLUMNS, HistoryEntry

    view = window.history_view
    view.set_entries([HistoryEntry(status="done", scenario="sat", number=4, mode="Single",
                                   started_utc="2026-10-22T10:00:00Z", duration_s=12.5, saved="Saved",
                                   provenance={"basilisk_version": "2.12.0", "integrator": "rkf78"})])
    assert not view.provenance_button.isEnabled()
    view.table.selectRow(0)
    assert view.provenance_button.isEnabled()
    view.provenance_button.click()
    assert view.popover.isVisible() and "basilisk_version: 2.12.0" in view.popover.body.text()
    view.popover.hide()
    view.copy()
    lines = QApplication.clipboard().text().splitlines()
    assert lines[0] == "\t".join(HISTORY_COLUMNS)
    assert lines[1].split("\t")[:6] == ["Done", "Run 4", "sat", "Single", "2026-10-22T10:00:00Z", "12.5 s"]


# -- the Log -----------------------------------------------------------------------------------------


def test_the_log_records_each_run(window, qtbot, caplog):
    """Start, end with its length, the run's warnings and where it is saved,
    from the GUI (the engine logs nothing during a normal run)."""
    import logging

    caplog.set_level(logging.INFO, logger="spacemissionstudio.run")  # the app logs INFO (logging_setup)
    _finish_a_run(window, warnings=["drag off: the orbit does not decay"])
    _saved(window, qtbot)
    messages = [message for _created, _level, name, message in window.log_widget.records
                if name == "spacemissionstudio.run"]
    assert any(m.startswith("Run 1 done in ") for m in messages)
    assert "Run 1: drag off: the orbit does not decay" in messages
    assert any(m.startswith("Run 1 saved to ") for m in messages)


def test_the_log_copies_what_it_shows(window, caplog):
    """Copy puts the selection, or every record shown, on the clipboard."""
    import logging

    from PySide6.QtWidgets import QApplication

    caplog.set_level(logging.INFO, logger="spacemissionstudio.run")
    logging.getLogger("spacemissionstudio.run").info("Run 9 done in 1.0 s: test, 0 series")
    window.log_widget.copy()
    assert "Run 9 done in 1.0 s" in QApplication.clipboard().text()
