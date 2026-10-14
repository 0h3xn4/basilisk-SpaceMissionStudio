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
"""The Events tab and the shared time cursor (UX/UI guidelines: "events
as a timeline with a sortable, exportable table"; "one shared time cursor
across views")."""

import json

import numpy as np
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from spacemissionstudio.engine.results import ResultSet, RunProvenance, TimeSeries
from spacemissionstudio.gui.event_timeline_widget import EventTimelineWidget
from spacemissionstudio.gui.time_cursor import TimeCursor, describe

_T = np.arange(100, dtype=float) * 60.0  # [s]


def _result(second_station=False):
    result = ResultSet("test")
    access = np.zeros(100)
    access[10:20] = access[60:65] = 1
    sunlight = np.ones(100)  # [-] illumination factor
    sunlight[30:50] = 0.0
    result.add(TimeSeries("gs.access_to_sat.has_access", _T, ("has_access",), access))
    result.add(TimeSeries("sat.eclipse.illumination_factor", _T, ("illumination_factor",), sunlight))
    if second_station:
        other = np.zeros(100)
        other[80:90] = 1
        elevation = np.radians(np.full(100, 30.0))  # [rad]
        result.add(TimeSeries("kiruna.access_to_sat.has_access", _T, ("has_access",), other))
        result.add(TimeSeries("kiruna.access_to_sat.elevation", _T, ("elevation",), elevation))
    return result


def _column(widget, heading):
    headings = [widget.table.horizontalHeaderItem(c).text().replace("\n", " ")
                for c in range(widget.table.columnCount())]
    return headings.index(heading)


def test_the_cursor_emits_only_when_it_moves(qtbot):
    cursor = TimeCursor()
    seen = []
    cursor.changed.connect(seen.append)
    cursor.set_time(60)
    cursor.set_time(60.0)
    cursor.clear()
    assert seen == [60.0, None]
    assert describe(4500.0) == "T+1.250 h"
    assert describe(4500.0, "2026-01-01T00:00:00") == "T+1.250 h (2026-01-01 01:15:00 UTC)"


def test_the_table_lists_every_event_and_sorts_by_time_not_text(qtbot):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(_result())
    assert widget.table.rowCount() == 3
    assert "2 passes, 1 eclipse" in widget.summary_label.text()
    assert "No burns" in widget.summary_label.text()
    starts = [widget.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in range(3)]
    assert starts == sorted(starts)  # earliest first until the user sorts
    assert "lowest sunlight 0%" in widget.table.item(1, 0).toolTip()  # the full detail on hover
    widget.table.sortItems(2, Qt.SortOrder.DescendingOrder)  # duration
    assert widget.table.item(0, 3).text() == "eclipse (umbra)"  # 19 min sorts above 9 min and 4 min
    assert set(widget.gantt.rows) == {"sat eclipse", "gs - sat"}


def test_kind_filters_hide_rows_in_the_table_and_the_timeline(qtbot):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(_result())
    widget.kind_boxes["eclipse"].setChecked(False)
    assert widget.table.rowCount() == 2
    assert widget.gantt.rows == ["gs - sat"]


def test_a_click_on_the_timeline_or_a_row_moves_the_shared_cursor(qtbot):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 500)
    cursor = TimeCursor()
    widget.set_time_cursor(cursor)
    widget.set_result(_result())
    widget.show()
    qtbot.waitExposed(widget)
    gantt = widget.gantt
    x = gantt.x_of(35 * 60.0)
    qtbot.mouseClick(gantt, Qt.MouseButton.LeftButton, pos=QPointF(x, 5).toPoint())
    assert abs(cursor.time_s - 35 * 60.0) < (gantt.view[1] - gantt.view[0]) / 100  # within a pixel or so
    assert "eclipse (umbra) (sat)" in widget.cursor_label.text()
    widget.table.sortItems(0, Qt.SortOrder.AscendingOrder)
    widget._on_row_clicked(2, 0)  # the second pass
    assert cursor.time_s == 60 * 60.0
    assert "pass over gs (sat)" in widget.cursor_label.text()
    cursor.clear()
    assert gantt.cursor_s is None


def test_the_wheel_zooms_and_fit_shows_the_whole_run(qtbot):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(_result())
    gantt = widget.gantt
    whole = gantt.view

    event = QWheelEvent(QPointF(gantt.width() / 2, 5), QPointF(), QPoint(), QPoint(0, 120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    gantt.wheelEvent(event)
    assert gantt.view[1] - gantt.view[0] < whole[1] - whole[0]
    widget.fit_button.click()
    assert gantt.view == whole


def test_export_writes_the_shown_events_and_the_run_provenance(qtbot, tmp_path):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    result = _result()
    result.provenance = RunProvenance("test", "2.12.0", "2026-01-01T00:00:00+00:00", "rk4", 1.0)
    widget.set_result(result, "2026-01-01T00:00:00")
    widget.kind_boxes["pass"].setChecked(False)
    path = widget.export_csv(tmp_path / "events.csv")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and lines[1].startswith("eclipse,sat")
    assert "start_utc" in lines[0]
    sidecar = json.loads((tmp_path / "events.csv.provenance.json").read_text(encoding="utf-8"))
    assert sidecar["spacemissionstudio_version"] == "test"


def test_no_result_shows_a_hint_and_disables_export(qtbot):
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    assert widget.table.rowCount() == 0
    assert not widget.export_button.isEnabled()
    assert "Run a scenario" in widget.summary_label.text()


def test_headings_carry_the_time_system_and_units_and_numbers_align_right(qtbot):
    """U-31: "Start (UTC)", "Duration [min]"; each measured value in its own
    right-aligned column at a fixed precision, not in a Detail text."""
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(_result(second_station=True), "2026-01-01T00:00:00")
    assert widget.columns(widget.visible_events()) == [
        "Start (UTC)", "End (UTC)", "Duration [min]", "Event", "Station",
        "Max elevation [deg]", "Lowest sunlight [%]"]  # one spacecraft: no Spacecraft column
    assert widget.table.horizontalHeaderItem(2).text() == "Duration\n[min]"  # the unit under the name
    assert widget.table.item(0, 0).text() == "2026-01-01 00:10:00"
    duration = widget.table.item(0, _column(widget, "Duration [min]"))
    assert duration.text() == "9.00" and duration.textAlignment() & Qt.AlignmentFlag.AlignRight
    sunlight = widget.table.item(1, _column(widget, "Lowest sunlight [%]"))
    assert sunlight.text() == "0" and sunlight.textAlignment() & Qt.AlignmentFlag.AlignRight
    assert widget.table.item(3, _column(widget, "Max elevation [deg]")).text() == "30.0"
    assert widget.table.item(0, _column(widget, "Max elevation [deg]")).text() == ""  # gs has no elevation
    two = _result()
    two.add(TimeSeries("sat-2.eclipse.illumination_factor", _T, ("illumination_factor",), np.ones(100) * 0.5))
    widget.set_result(two)
    assert "Spacecraft" in widget.columns(widget.visible_events())
    widget.set_result(_result())  # no epoch: elapsed hours, and no column without a value
    assert widget.columns(widget.visible_events())[:2] == ["Start [h]", "End [h]"]
    assert widget.table.item(0, 0).text() == "0.1667"
    assert "Max elevation [deg]" not in widget.columns(widget.visible_events())


def test_search_and_the_station_filter_narrow_the_timeline_table_and_export(qtbot, tmp_path):
    """U-32: a search box and a ground-station filter."""
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(_result(second_station=True))
    assert [widget.station_combo.itemText(i) for i in range(widget.station_combo.count())] == [
        "All stations", "gs", "kiruna"]
    widget.station_combo.setCurrentText("kiruna")
    assert widget.table.rowCount() == 1 and widget.gantt.rows == ["kiruna - sat"]
    assert widget.shown_label.text() == "1 of 4 events shown"
    widget.station_combo.setCurrentText("All stations")
    widget.search.setText("UMBRA")
    assert [e.label for e in widget.visible_events()] == ["eclipse (umbra)"]
    widget.search.setText("pass gs")  # every word must match
    assert [e.other for e in widget.visible_events()] == ["gs", "gs"]
    lines = widget.export_csv(tmp_path / "events.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    widget.search.clear()
    assert widget.table.rowCount() == 4 and widget.shown_label.text() == ""
    widget.set_result(_result())  # a station that has gone keeps nothing stale
    assert widget.station_combo.isEnabled()
    widget.set_result(ResultSet("empty"))
    assert not widget.station_combo.isEnabled()


def test_ctrl_c_copies_the_selected_rows_as_tsv_with_headings(qtbot):
    """U-32: Ctrl+C gives tab-separated text a spreadsheet pastes as columns."""
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(_result())
    widget.table.selectRow(0)
    widget.table.setFocus()
    qtbot.keyClick(widget.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    lines = QApplication.clipboard().text().splitlines()
    assert lines[0].split("\t") == widget.columns(widget.visible_events())
    assert lines[1].split("\t")[:4] == ["0.1667", "0.3167", "9.00", "pass over gs"]
    assert "Duration [min]" in lines[0]  # the heading on one line again
    assert len(lines) == 2


def test_arrow_keys_on_the_table_move_the_cursor_and_ctrl_f_finds(qtbot):
    """Keyboard-only use: the rows set the cursor as a click does, and
    Ctrl+F goes to the search box."""
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    cursor = TimeCursor()
    widget.set_time_cursor(cursor)
    widget.set_result(_result())
    widget.show()
    qtbot.waitExposed(widget)
    widget.table.setFocus()
    widget.table.setCurrentCell(0, 0)
    assert cursor.time_s == 10 * 60.0
    qtbot.keyClick(widget.table, Qt.Key.Key_Down)
    assert cursor.time_s == 30 * 60.0  # the eclipse
    widget._pick_time(5.0)  # [s] set on the timeline
    widget.table.sortItems(2, Qt.SortOrder.DescendingOrder)  # the current row moves with its event
    assert cursor.time_s == 5.0  # a sort does not move the cursor
    assert widget.find_shortcut.key().toString() == "Ctrl+F"
    widget.find_shortcut.activated.emit()
    assert widget.focusWidget() is widget.search
