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
"""The Compare tab (docs/ux-audit.md U-33, decision 5): two or more runs,
saved to disk, compared with the oldest ticked one -- a summary with
deltas, the inputs that differ, the events and overlaid plots."""

from datetime import datetime

import numpy as np
import pytest

from spacemissionstudio.engine import run_store
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.gui.run_history import RunHistory

pytestmark = pytest.mark.requires_gui

_T = np.arange(0.0, 7200.0, 60.0)  # [s]
_N = _T.size


def _result(delta_v_m_s, passes=1):
    result = ResultSet("demo")
    result.add(TimeSeries("sat.position_N", _T, ("x", "y", "z"), np.zeros((_N, 3)), "m"))
    result.add(TimeSeries("sat.station_keeping.delta_v", _T, ("cumulative_delta_v",),
                          np.linspace(0.0, delta_v_m_s, _N), "m/s"))
    access = np.zeros(_N)
    for k in range(passes):
        access[10 + 30 * k:20 + 30 * k] = 1
    result.add(TimeSeries("gs.access_to_sat.has_access", _T, ("has_access",), access))
    return result


def _scenario(duration_days, drag=0.0):
    return {"name": "demo", "sim_settings": {"duration_days": duration_days}, "drag": drag}


@pytest.fixture
def compare(qtbot, tmp_path):
    from spacemissionstudio.gui.compare_widget import CompareWidget

    widget = CompareWidget()
    qtbot.addWidget(widget)
    history = RunHistory(store_root=tmp_path / "runs")
    history.add(_scenario(1.0), _result(1.0, passes=1), "2030-01-01T00:00:00", finished=datetime(2026, 10, 14, 9, 0))
    history.add(_scenario(1.0, drag=2.2), _result(1.5, passes=2), "2030-01-01T00:00:00",
                finished=datetime(2026, 10, 14, 9, 5))
    history.add(_scenario(2.0), _result(0.5, passes=3), "2030-01-01T00:00:00", finished=datetime(2026, 10, 14, 9, 10))
    widget.set_runs(history.runs, history.runs[-1], None, history.store_root)
    widget.resize(1200, 700)
    return widget, history


def _column(table, heading):
    return [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())].index(heading)


def _row(table, first_cell):
    return [table.item(r, 0).text() for r in range(table.rowCount())].index(first_cell)


def test_a_new_run_is_compared_with_the_one_before_it(compare):
    widget, _history = compare
    assert [r.number for r in widget.checked_runs()] == [2, 3]
    assert "Comparing with Run 2" in widget.status_label.text()
    assert widget.run_list.count() == 3
    assert widget.run_list.item(0).text() == "Run 3, 09:10 (shown)\ndemo"


def test_the_summary_has_a_delta_per_run_against_the_oldest_ticked(compare):
    widget, _history = compare
    widget.set_checked([1, 2, 3])
    table = widget.summary_table
    headings = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
    assert headings == ["Figure", "Unit", "Run 1 (base)", "Run 2", "Δ Run 2", "Run 3", "Δ Run 3"]
    row = _row(table, "Delta-V")
    assert table.item(row, 1).text() == "m/s"
    assert [table.item(row, c).text() for c in range(2, 7)] == ["1.000", "1.500", "+0.500", "0.500", "-0.500"]
    assert table.item(_row(table, "Passes"), _column(table, "Δ Run 3")).text() == "+2"
    assert table.item(row, 2).textAlignment() & 0x2  # right-aligned numbers (Qt.AlignRight)


def test_the_inputs_that_differ_from_the_base_old_to_new(compare):
    widget, _history = compare
    widget.set_checked([1, 2, 3])
    table = widget.inputs_table
    drag, duration = _row(table, "drag"), _row(table, "sim_settings.duration_days")
    assert [table.item(drag, c).text() for c in range(1, 4)] == ["0.0", "2.2", "(same)"]
    assert [table.item(duration, c).text() for c in range(1, 4)] == ["1.0", "(same)", "2.0"]
    widget.set_checked([1, 1])
    assert "Tick two or more" in widget.status_label.text() and table.rowCount() == 0


def test_the_events_are_counted_with_their_total_time(compare):
    widget, _history = compare
    table = widget.events_table
    row = _row(table, "pass over gs")
    assert table.item(row, 1).text() == "2 × 18.0 min"  # Run 2, the base here
    assert table.item(row, 2).text() == "3 × 27.0 min"
    assert table.item(row, 3).text() == "+1 × +9.0 min"


def test_the_plots_overlay_one_series_of_every_ticked_run(compare):
    widget, _history = compare
    widget.set_checked([1, 2, 3])
    widget.series_combo.setCurrentIndex(widget.series_combo.findData("sat.station_keeping.delta_v"))
    traces = widget.figure.data
    assert [t.name for t in traces] == ["Run 1, 09:00 (base)", "Run 2, 09:05", "Run 3, 09:10"]
    assert [t.line.dash for t in traces] == ["solid", "dash", "dash"]
    assert np.isclose(traces[1].y[-1], 1.5)  # [m/s]
    assert widget.figure.layout.xaxis.title.text == "Elapsed time [h]"
    assert not widget.column_combo.isVisibleTo(widget)  # one column: nothing to pick


def test_runs_of_an_earlier_session_are_listed_and_read_back_when_ticked(qtbot, tmp_path):
    """The main window lists the saved runs at start-up and reads a run's
    series from disk only when it is compared."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    earlier = RunHistory(store_root=run_store.default_root())  # under the test's home folder
    earlier.add(_scenario(1.0), _result(1.0), "", finished=datetime(2026, 10, 13, 17, 0))
    earlier.add(_scenario(2.0), _result(2.0), "", finished=datetime(2026, 10, 13, 17, 30))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    compare = window.compare_widget
    assert compare.run_list.count() == 2 and compare.run_list.item(0).text().startswith("Run 2, 13 Oct 17:30")
    assert not any(r.in_memory for r in window.run_history.runs)
    compare.set_checked([1, 2])
    assert all(r.in_memory for r in window.run_history.runs)
    table = compare.summary_table
    assert table.item(_row(table, "Delta-V"), _column(table, "Δ Run 2")).text() == "+1.000"
    compare.run_list.setCurrentRow(1)  # Run 1
    original_question = QMessageBox.question
    try:
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        compare.delete_button.click()
    finally:
        QMessageBox.question = original_question
    assert [r.number for r in run_store.load_index(run_store.default_root())] == [2]
    assert compare.run_list.count() == 1 and compare.empty_label.isVisibleTo(compare)


def test_the_shown_run_cannot_be_deleted_and_an_unreadable_one_is_named(compare):
    widget, history = compare
    widget.run_list.setCurrentRow(0)  # Run 3, shown
    assert not widget.delete_button.isEnabled()
    widget.run_list.setCurrentRow(1)
    assert widget.delete_button.isEnabled()
    old = history.find(1)
    old.forget_series()
    (history.store_root / old.saved.run_id / "series.npz").write_bytes(b"not a zip file")
    widget.set_checked([1, 2, 3])
    assert "Run 1, 09:00 could not be read back" in widget.status_label.text()
