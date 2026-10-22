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

"""The Timeline at scale (UI overhaul M7): 10,000 events with rows made
when shown and sorted by value, lanes drawn merged by pixel, the event
under the pointer found by bisection; a UTC axis with Z; zoom and pan by
wheel, drag and keys. And the plots: an export keeps every sample however
the plot thins its lines."""

import sys
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

pytestmark = pytest.mark.requires_gui

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
_YEAR_S = 365.25 * 86400.0  # [s]


@pytest.fixture
def timeline(qtbot, monkeypatch):
    """The Timeline given 10,000 synthetic events over a year, with an epoch."""
    from measure_timeline import synthetic_events

    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui import event_timeline_widget

    events = synthetic_events(10000)
    monkeypatch.setattr(event_timeline_widget.event_model, "extract_events", lambda result: list(events))
    monkeypatch.setattr(event_timeline_widget.event_model, "missing_kinds", lambda result: {})
    result = ResultSet("timeline")
    result.add(TimeSeries("sat-1.position_N", np.array([0.0, _YEAR_S]), ("x", "y", "z"), np.zeros((2, 3)), "m"))
    widget = event_timeline_widget.EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(1280, 720)  # [px]
    widget.show()
    qtbot.waitExposed(widget)
    widget.set_result(result, "2030-01-01T00:00:00Z")
    return widget


def test_ten_thousand_events_make_only_the_rows_shown(timeline):
    """The table holds every event, but only the rows shown (and the few
    its columns are sized from) are made."""
    assert timeline.table.row_count() == 10000
    assert len(timeline.rows._made) < 200
    starts = [timeline.row_event(r).start_s for r in range(50)]
    assert starts == sorted(starts)  # earliest first


def test_a_header_sorts_the_rows_by_value(timeline):
    """Sorting by duration orders by the number (a 35 min eclipse above a
    10 min pass), not by its text; the rows are made again for the order."""
    duration = [timeline.table.header_text(c) for c in range(timeline.table.column_count())].index("Duration\n[min]")
    timeline.table.sort_by(duration, Qt.SortOrder.DescendingOrder)
    assert timeline.table.cell(0, duration) == "35.00" and timeline.table.cell(9999, duration) == "10.00"
    assert timeline.row_event(0).kind == "eclipse"


def test_the_search_narrows_ten_thousand_events(timeline):
    timeline.search.setText("kiruna")
    shown = timeline.visible_events()
    assert shown and all(event.other == "kiruna" for event in shown)
    assert timeline.table.row_count() == len(shown)
    assert timeline.gantt.rows == ["kiruna - sat-1", "kiruna - sat-2"]


def test_a_lane_draws_merged_spans_and_finds_the_event_under_the_pointer(timeline):
    """A year of passes on 1,000 px: at most a span a pixel, and the event
    under the pointer is the one there."""
    from spacemissionstudio.gui.event_timeline_widget import _merged

    gantt = timeline.gantt
    lane = gantt.lanes[0]
    x0 = np.linspace(0.0, 1000.0, lane.starts.size)  # [px]
    spans = _merged(x0, x0 + 2.0)
    assert len(spans) <= 1000 and spans[0][0] == 0.0 and spans[-1][1] >= 1000.0
    event = gantt.events[int(lane.index[len(lane.index) // 2])]
    gantt.view = (event.start_s - 3600.0, event.end_s + 3600.0)  # [s] two hours around it
    point = QPointF(gantt.x_of((event.start_s + event.end_s) / 2), 5)
    assert gantt.event_at(point) is event


def test_the_axis_is_utc_with_z(timeline):
    """Round UTC times: hours and minutes with Z, a date at midnight."""
    gantt = timeline.gantt
    gantt.view = (0.0, 6 * 3600.0)  # [s] the first six hours
    labels = [label for _time, label in gantt._ticks()]
    assert labels and all(label.endswith("Z") or label == "2030-01-01" for label in labels)
    assert "01:00Z" in labels or "02:00Z" in labels
    gantt.fit()
    assert all(label[:4] in ("2030", "2031") for _time, label in gantt._ticks())  # a year: dates


def test_without_an_epoch_the_axis_is_elapsed_time(timeline):
    gantt = timeline.gantt
    gantt.set_events(gantt.events, gantt.run_end_s, None)
    assert all(label.endswith((" h", " d")) for _time, label in gantt._ticks())


def test_keys_wheel_and_drag_zoom_and_pan(timeline, qtbot):
    gantt = timeline.gantt
    whole = gantt.view
    gantt.setFocus()
    qtbot.keyClick(gantt, Qt.Key.Key_Plus)
    zoomed = gantt.view
    assert zoomed[1] - zoomed[0] < whole[1] - whole[0]
    qtbot.keyClick(gantt, Qt.Key.Key_Right)
    assert gantt.view[0] > zoomed[0] and gantt.view[1] - gantt.view[0] == pytest.approx(zoomed[1] - zoomed[0])
    moved = gantt.view
    gantt.wheelEvent(QWheelEvent(QPointF(gantt.width() / 2, 5), QPointF(), QPoint(), QPoint(0, 120),
                                 Qt.MouseButton.NoButton, Qt.KeyboardModifier.ShiftModifier,
                                 Qt.ScrollPhase.NoScrollPhase, False))
    assert gantt.view[0] < moved[0]  # Shift+wheel pans, it does not zoom
    before = gantt.view
    qtbot.mousePress(gantt, Qt.MouseButton.RightButton, pos=QPoint(600, 5))
    qtbot.mouseMove(gantt, QPoint(500, 5))
    qtbot.mouseRelease(gantt, Qt.MouseButton.RightButton, pos=QPoint(500, 5))
    assert gantt.view[0] > before[0]  # dragged left: later times come into view
    qtbot.keyClick(gantt, Qt.Key.Key_0)
    assert gantt.view == whole


def test_an_export_keeps_every_sample_the_plot_thins(qtbot, tmp_path, monkeypatch):
    """Plots show at most _MAX_PLOT_POINTS_PER_LINE points a line; Export
    CSV writes every sample (display decimation only)."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui import results_widget

    samples = 3 * results_widget._MAX_PLOT_POINTS_PER_LINE
    t = np.arange(samples, dtype=float)  # [s]
    result = ResultSet("long")
    result.add(TimeSeries("sat-1.battery_charge", t, ("battery_charge",), np.sin(t / 50.0)[:, None], "W*h"))
    widget = results_widget.ResultsWidget()
    qtbot.addWidget(widget)
    widget.set_result(result)
    assert len(widget.figure.data[0].y) <= results_widget._MAX_PLOT_POINTS_PER_LINE
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(results_widget, "report", lambda *a, **k: None)
    widget._on_export()
    rows = (tmp_path / "sat-1.battery_charge.csv").read_text(encoding="utf-8").splitlines()
    assert len(rows) == samples + 1  # the header and every sample
