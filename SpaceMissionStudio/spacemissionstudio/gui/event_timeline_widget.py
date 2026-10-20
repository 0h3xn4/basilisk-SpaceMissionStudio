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
"""The Events tab: a run's passes, eclipses, burns, thruster firings and
mode changes as a Gantt timeline over a sortable table (UX/UI guidelines,
"events as a timeline with a sortable, exportable table").

The events come from :func:`engine.events.extract_events`. The timeline
shows the shared :class:`gui.time_cursor.TimeCursor` and sets it by click
or drag; a table row (clicked, or reached with the arrow keys) sets it to
the event's start; Esc clears it. The mouse wheel zooms the timeline
around the pointer and "Fit" shows the whole run.

The table (docs/ux-audit.md U-31, U-32) says the time system and unit in
each heading ("Start (UTC)", "Duration [min]") and gives every measured
value its own right-aligned column at a fixed precision ("Max elevation
[deg]", "Lowest sunlight [%]", ...; :data:`engine.events.QUANTITIES`).
A search box (Ctrl+F) and a station filter narrow the timeline, the
table and the export alike. Ctrl+C copies the selected rows, with the
headings, as tab-separated text for a spreadsheet. The table exports to
CSV with a provenance file beside it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QToolTip, QVBoxLayout, QWidget)

from .. import output_provenance
from ..engine import events as event_model
from ..engine.results import ResultSet
from .feedback import report
from .theme import PALETTE, SERIES_COLORS, set_role
from .time_cursor import TimeCursor, describe

# Fixed categorical order, one slot per kind (the Results tab's series colours).
KIND_SLOTS: Dict[str, int] = {kind: index for index, kind in enumerate(event_model.KINDS)}


def kind_colour(kind: str) -> str:
    """The colour of an event kind in the theme in use."""
    return SERIES_COLORS[KIND_SLOTS[kind]] if kind in KIND_SLOTS else PALETTE["accent"]
_ALL_STATIONS = "All stations"
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_ROW_HEIGHT = 22  # [px]
_AXIS_HEIGHT = 26  # [px]
_MIN_BAR_PX = 2  # [px] a short event on a long run stays visible


def _plural(kind: str, count: int) -> str:
    """"1 pass", "2 passes", "1 thruster firing", "3 thruster firings"."""
    if count == 1:
        return f"1 {kind}"
    return f"{count} {kind}{'es' if kind.endswith('ss') else 's'}"


def _duration_text(seconds: float) -> str:
    if seconds < 120.0:
        return f"{seconds:.0f} s"
    if seconds < 7200.0:
        return f"{seconds / 60.0:.1f} min"
    return f"{seconds / 3600.0:.2f} h"


class _SortItem(QTableWidgetItem):
    """A cell that sorts by a number, not by its text."""

    def __init__(self, text: str, key: float):
        super().__init__(text)
        self._key = key

    def __lt__(self, other):  # noqa: D105 -- Qt sort hook
        if isinstance(other, _SortItem):
            return self._key < other._key
        return super().__lt__(other)


def _matches(event: event_model.Event, words: List[str]) -> bool:
    """Every search word appears in the event's text (any case)."""
    text = " ".join((event.kind, event.spacecraft, event.other, event.label, event.detail)).lower()
    return all(word in text for word in words)


class _EventTable(QTableWidget):
    """The events table; Ctrl+C copies the selected rows as TSV (U-32)."""

    def keyPressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.matches(QKeySequence.StandardKey.Copy):
            QApplication.clipboard().setText(self.selection_tsv())
            event.accept()
            return
        super().keyPressEvent(event)

    def selection_tsv(self) -> str:
        """The selected rows, in the order shown, under a line of headings."""
        rows = sorted({index.row() for index in self.selectedIndexes()})
        if not rows:
            return ""
        columns = range(self.columnCount())
        lines = ["\t".join(self.horizontalHeaderItem(c).text().replace("\n", " ") for c in columns)]
        for row in rows:
            cells = [self.item(row, c) for c in columns]
            lines.append("\t".join(cell.text() if cell is not None else "" for cell in cells))
        return "\n".join(lines) + "\n"


class GanttView(QWidget):
    """The timeline: one row per spacecraft and kind (per station for a pass)."""

    time_picked = Signal(float)  # [s]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(_AXIS_HEIGHT + 2 * _ROW_HEIGHT)
        self.events: List[event_model.Event] = []
        self.rows: List[str] = []
        self.cursor_s: Optional[float] = None
        self.run_end_s = 1.0  # [s]
        self.view = (0.0, 1.0)  # [s] the visible time span

    def set_events(self, events: List[event_model.Event], run_end_s: float) -> None:
        self.events = events
        self.rows = list(dict.fromkeys(e.row for e in sorted(events, key=lambda e: (e.kind, e.row))))
        self.run_end_s = max(run_end_s, max((e.end_s for e in events), default=0.0), 1.0)  # [s]
        self.fit()
        self.setMinimumHeight(_AXIS_HEIGHT + max(len(self.rows), 2) * _ROW_HEIGHT + 4)

    def fit(self) -> None:
        self.view = (0.0, self.run_end_s)
        self.update()

    def set_cursor_time(self, time_s: Optional[float]) -> None:
        self.cursor_s = time_s
        self.update()

    # -- geometry ---------------------------------------------------------

    def _label_width(self) -> int:
        metrics = QFontMetrics(self.font())
        return min(max([metrics.horizontalAdvance(r) for r in self.rows] + [60]) + 12, self.width() // 3)

    def _plot_rect(self) -> QRectF:
        left = self._label_width()
        return QRectF(left, 0, max(self.width() - left - 8, 10), self.height() - _AXIS_HEIGHT)

    def x_of(self, time_s: float) -> float:
        rect = self._plot_rect()
        start, end = self.view
        return rect.left() + (time_s - start) / (end - start) * rect.width()

    def time_at(self, x: float) -> float:
        rect = self._plot_rect()
        start, end = self.view
        fraction = min(max((x - rect.left()) / rect.width(), 0.0), 1.0)
        return start + fraction * (end - start)  # [s]

    def event_at(self, point: QPointF) -> Optional[event_model.Event]:
        row = int(point.y() // _ROW_HEIGHT)
        if not 0 <= row < len(self.rows):
            return None
        time_s = self.time_at(point.x())
        tolerance_s = (self.view[1] - self.view[0]) / max(self._plot_rect().width(), 1.0) * 3  # [s] 3 px
        for event in self.events:
            if event.row == self.rows[row] and event.start_s - tolerance_s <= time_s <= event.end_s + tolerance_s:
                return event
        return None

    # -- painting ---------------------------------------------------------

    def paintEvent(self, _event):  # noqa: N802 -- Qt API name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(PALETTE["surface"]))
        rect = self._plot_rect()
        muted, grid = QColor(PALETTE["text_muted"]), QColor(PALETTE["border"])
        if not self.rows:
            painter.setPen(muted)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No events in this run.")
            return
        for index, row in enumerate(self.rows):
            top = index * _ROW_HEIGHT
            painter.setPen(QColor(PALETTE["text"]))
            painter.drawText(QRectF(4, top, rect.left() - 8, _ROW_HEIGHT),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, row)
            painter.setPen(grid)
            painter.drawLine(QPointF(rect.left(), top + _ROW_HEIGHT), QPointF(rect.right(), top + _ROW_HEIGHT))
        self._paint_axis(painter, rect, muted, grid)
        row_index = {row: i for i, row in enumerate(self.rows)}
        start, end = self.view
        painter.setPen(Qt.PenStyle.NoPen)
        for event in self.events:
            if event.end_s < start or event.start_s > end:
                continue
            x0, x1 = self.x_of(max(event.start_s, start)), self.x_of(min(event.end_s, end))
            top = row_index[event.row] * _ROW_HEIGHT + 4
            painter.setBrush(QColor(kind_colour(event.kind)))
            painter.drawRoundedRect(QRectF(x0, top, max(x1 - x0, _MIN_BAR_PX), _ROW_HEIGHT - 8), 2, 2)
        if self.cursor_s is not None and start <= self.cursor_s <= end:
            x = self.x_of(self.cursor_s)
            painter.setPen(QPen(QColor(PALETTE["accent"]), 2))  # the time cursor: a selection
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.bottom()))

    def _paint_axis(self, painter: QPainter, rect: QRectF, muted: QColor, grid: QColor) -> None:
        start, end = self.view
        span_h = (end - start) / 3600.0  # [h]
        step_h = next((s for s in (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 6, 12, 24, 48, 168, 720, 2160, 8760)
                       if span_h / s <= 8), 8760.0)  # [h]
        tick = np.ceil(start / 3600.0 / step_h) * step_h  # [h]
        while tick <= end / 3600.0:
            x = self.x_of(tick * 3600.0)
            painter.setPen(grid)
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.bottom()))
            painter.setPen(muted)
            label = f"{tick / 24:g} d" if step_h >= 24 else f"{tick:g} h"
            painter.drawText(QRectF(x - 40, rect.bottom() + 2, 80, _AXIS_HEIGHT - 4), Qt.AlignmentFlag.AlignCenter,
                             label)
            tick += step_h

    # -- mouse ------------------------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.button() == Qt.MouseButton.LeftButton and event.position().x() >= self._plot_rect().left():
            self.time_picked.emit(self.time_at(event.position().x()))

    def mouseMoveEvent(self, event):  # noqa: N802 -- Qt API name
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.time_picked.emit(self.time_at(event.position().x()))
            return
        hit = self.event_at(event.position())
        if hit is None:
            QToolTip.hideText()
            return
        text = f"{hit.label} ({hit.spacecraft})\n{_duration_text(hit.duration_s)}" + (
            f"\n{hit.detail}" if hit.detail else "")
        QToolTip.showText(event.globalPosition().toPoint(), text, self)

    def wheelEvent(self, event):  # noqa: N802 -- Qt API name
        """Zoom around the pointer, in to one second across at most."""
        centre = self.time_at(event.position().x())
        factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        start, end = self.view
        width = min(max((end - start) * factor, 1.0), self.run_end_s)  # [s]
        new_start = min(max(centre - (centre - start) * width / (end - start), 0.0), self.run_end_s - width)
        self.view = (new_start, new_start + width)
        self.update()


class EventTimelineWidget(QWidget):
    """The Events tab."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cursor: Optional[TimeCursor] = None
        self._result: Optional[ResultSet] = None
        self._epoch_utc: Optional[str] = None
        self.events: List[event_model.Event] = []
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.kind_boxes: Dict[str, QCheckBox] = {}
        for kind in event_model.KINDS:
            box = QCheckBox(_plural(kind, 2)[2:].capitalize())
            box.setChecked(True)
            set_role(box, series=str(KIND_SLOTS[kind]))  # a swatch of the kind's colour
            box.toggled.connect(self._apply_filter)
            controls.addWidget(box)
            self.kind_boxes[kind] = box
        controls.addStretch(1)
        self.fit_button = QPushButton("Fit")
        self.fit_button.setToolTip("Show the whole run. The mouse wheel zooms the timeline.")
        controls.addWidget(self.fit_button)
        self.export_button = QPushButton("Export CSV...")
        self.export_button.setToolTip("The events shown in the table, with a provenance file beside them.")
        self.export_button.clicked.connect(self._on_export)
        controls.addWidget(self.export_button)
        layout.addLayout(controls)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search events (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search events")
        self.search.setToolTip("Every word must appear in the event, spacecraft, station or its values.")
        self.search.textChanged.connect(self._apply_filter)
        filters.addWidget(self.search, 2)
        self.station_combo = QComboBox()
        self.station_combo.setAccessibleName("Ground station")
        self.station_combo.setToolTip("Show the passes and downlinks of one ground station only.")
        self.station_combo.currentIndexChanged.connect(self._apply_filter)
        filters.addWidget(self.station_combo, 1)
        self.shown_label = QLabel("")
        set_role(self.shown_label, tone="secondary")
        filters.addWidget(self.shown_label)
        filters.addStretch(1)
        layout.addLayout(filters)
        self.find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self,
                                       context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.find_shortcut.activated.connect(lambda: (self.search.setFocus(), self.search.selectAll()))

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.cursor_label = QLabel(describe(None))
        self.cursor_label.setWordWrap(True)
        layout.addWidget(self.cursor_label)

        splitter = self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.gantt = GanttView()
        self.fit_button.clicked.connect(self.gantt.fit)
        self.gantt.time_picked.connect(self._pick_time)
        splitter.addWidget(self.gantt)
        self.table = _EventTable(0, 0)
        self.table.setAccessibleName("Events")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)  # values stay next to their event
        self.table.cellClicked.connect(self._on_row_clicked)
        self._filling = False
        self.table.currentCellChanged.connect(self._on_current_cell_changed)
        self._sorted_by_user = False
        self.table.horizontalHeader().sectionClicked.connect(lambda _c: setattr(self, "_sorted_by_user", True))
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        clear = QShortcut(QKeySequence("Esc"), self, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        clear.activated.connect(lambda: self._pick_time(None))
        self.set_result(None)

    # -- wiring -----------------------------------------------------------

    def set_time_cursor(self, cursor: TimeCursor) -> None:
        self._cursor = cursor
        cursor.changed.connect(self.on_cursor_changed)
        self.on_cursor_changed(cursor.time_s)

    def set_result(self, result: Optional[ResultSet], epoch_utc: Optional[str] = None) -> None:
        self._result, self._epoch_utc = result, epoch_utc
        self.events = event_model.extract_events(result)
        missing = event_model.missing_kinds(result) if result is not None else {}
        counts = {kind: sum(e.kind == kind for e in self.events) for kind in event_model.KINDS}
        if result is None:
            self.summary_label.setText("Run a scenario to see its passes, eclipses, burns and mode changes.")
        else:
            text = ", ".join(_plural(kind, n) for kind, n in counts.items() if n)
            self.summary_label.setText((text or "No events") + "." + "".join(
                f" No {_plural(kind, 2)[2:]}: {why}." for kind, why in missing.items()))
        self.export_button.setEnabled(bool(self.events))
        self._fill_stations()
        self._apply_filter()

    def _fill_stations(self) -> None:
        stations = sorted({e.other for e in self.events if e.other})
        current = self.station_combo.currentText()
        self.station_combo.blockSignals(True)
        self.station_combo.clear()
        self.station_combo.addItems([_ALL_STATIONS] + stations)
        self.station_combo.setCurrentIndex(max(self.station_combo.findText(current), 0))
        self.station_combo.blockSignals(False)
        self.station_combo.setEnabled(bool(stations))
        self.station_combo.setToolTip("Show the passes and downlinks of one ground station only." if stations
                                      else "This run has no ground stations.")

    def visible_events(self) -> List[event_model.Event]:
        """The events the kind boxes, the station filter and the search let
        through: what the timeline, the table and the export show."""
        shown = {kind for kind, box in self.kind_boxes.items() if box.isChecked()}
        station = self.station_combo.currentText()
        words = self.search.text().lower().split()
        return [e for e in self.events if e.kind in shown and (station in ("", _ALL_STATIONS) or e.other == station)
                and _matches(e, words)]

    def _apply_filter(self) -> None:
        visible = self.visible_events()
        self.shown_label.setText(f"{len(visible)} of {len(self.events)} events shown"
                                 if len(visible) != len(self.events) else "")
        run_end = max((float(s.time_s[-1]) for s in self._result.series.values() if s.time_s.size),
                      default=0.0) if self._result is not None else 0.0  # [s]
        self.gantt.set_events(visible, run_end)
        self._fill_table(visible)
        self._fit_timeline_height()

    def showEvent(self, event):  # noqa: N802 -- Qt API name
        super().showEvent(event)
        self._fit_timeline_height()

    def _fit_timeline_height(self) -> None:
        """The timeline as tall as its rows; the table gets the rest."""
        total = sum(self.splitter.sizes())
        if total > 0:
            wanted = min(self.gantt.minimumHeight() + 8, total // 2)  # [px]
            self.splitter.setSizes([wanted, total - wanted])

    def _utc_texts(self, times_s: List[float]) -> Optional[List[str]]:
        """UTC text for each elapsed time, or None without a usable epoch."""
        if not self._epoch_utc or not times_s:
            return None
        from ..engine import time_system

        try:
            return [event_model.utc_text(moment, "seconds")
                    for moment in time_system.elapsed_to_utc(self._epoch_utc, times_s)]
        except ValueError:
            return None

    def columns(self, visible: List[event_model.Event]) -> List[str]:
        """The table's headings for ``visible``: a spacecraft column only
        for a run with several, and a station, measured-value or note column
        only when some event has one (so 1280 px holds the table)."""
        utc = self._utc_texts([0.0]) is not None
        headings = ["Start (UTC)", "End (UTC)"] if utc else ["Start [h]", "End [h]"]
        headings += ["Duration [min]", "Event"]  # the event names its kind ("pass over ...", "eclipse (umbra)")
        headings += ["Spacecraft"] if len({e.spacecraft for e in self.events}) > 1 else []
        headings += ["Station"] if any(e.other for e in visible) else []
        headings += [f"{event_model.QUANTITIES[key][0]} [{event_model.QUANTITIES[key][1]}]"
                     for key in event_model.present_quantities(visible)]
        headings += ["Note"] if any(e.note for e in visible) else []
        return headings

    def _fill_table(self, visible: List[event_model.Event]) -> None:
        headings = self.columns(visible)
        keys = event_model.present_quantities(visible)
        starts = self._utc_texts([e.start_s for e in visible])
        ends = self._utc_texts([e.end_s for e in visible])
        self._filling = True
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setColumnCount(len(headings))
        # the unit under the name keeps the value columns narrow (Ctrl+C joins them again)
        self.table.setHorizontalHeaderLabels([heading.replace(" [", "\n[") for heading in headings])
        self.table.setRowCount(len(visible))
        for row, event in enumerate(visible):
            if starts is not None and ends is not None:
                cells = [_SortItem(starts[row], event.start_s), _SortItem(ends[row], event.end_s)]
            else:
                cells = [_SortItem(f"{event.start_s / 3600.0:.4f}", event.start_s),
                         _SortItem(f"{event.end_s / 3600.0:.4f}", event.end_s)]
                for cell in cells:
                    cell.setTextAlignment(_RIGHT)
            cells.append(_SortItem(f"{event.duration_s / 60.0:.2f}", event.duration_s))
            cells[-1].setTextAlignment(_RIGHT)
            cells.append(QTableWidgetItem(event.label))
            if "Spacecraft" in headings:
                cells.append(QTableWidgetItem(event.spacecraft))
            if "Station" in headings:
                cells.append(QTableWidgetItem(event.other))
            for key in keys:
                value = event.quantity(key)
                fmt = event_model.QUANTITIES[key][2]
                cells.append(_SortItem("" if value is None else format(value, fmt),
                                       float("-inf") if value is None else value))
                cells[-1].setTextAlignment(_RIGHT)
            if "Note" in headings:
                cells.append(QTableWidgetItem(event.note))
                cells[-1].setToolTip(event.note)
            cells[0].setData(Qt.ItemDataRole.UserRole, event.start_s)
            tip = f"T+{event.start_s:.1f} s" + (f"\n{event.detail}" if event.detail else "")
            for column, item in enumerate(cells):
                if not item.toolTip():
                    item.setToolTip(tip)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        if self.table.horizontalHeader().sortIndicatorSection() == 0 and not self._sorted_by_user:
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)  # earliest first until the user sorts
        self.table.resizeColumnsToContents()
        self._filling = False

    # -- cursor -----------------------------------------------------------

    def _pick_time(self, time_s: Optional[float]) -> None:
        if self._cursor is not None:
            self._cursor.set_time(time_s)
        else:
            self.on_cursor_changed(time_s)

    def _on_row_clicked(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        start = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if start is not None:
            self._pick_time(float(start))

    def _on_current_cell_changed(self, row: int, _column: int, previous_row: int, _previous_column: int) -> None:
        """The arrow keys move the cursor from row to row, as a click does."""
        if not self._filling and row >= 0 and row != previous_row:
            self._on_row_clicked(row, 0)

    def on_cursor_changed(self, time_s: Optional[float]) -> None:
        self.gantt.set_cursor_time(time_s)
        if time_s is None:
            self.cursor_label.setText(describe(None))
            return
        current = [f"{e.label} ({e.spacecraft})" for e in self.visible_events() if e.start_s <= time_s <= e.end_s]
        self.cursor_label.setText(f"Cursor {describe(time_s, self._epoch_utc)}: "
                                  + ("; ".join(current) if current else "no event in progress") + ".")

    # -- export -----------------------------------------------------------

    def _on_export(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(self, "Export events to CSV", "events.csv", "CSV files (*.csv)")
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix != ".csv":
            path = path.with_suffix(".csv")
        try:
            self.export_csv(path)
        except OSError as exc:
            report(self, f"Could not export the events to {path}: {exc}")
            return
        report(self, f"Exported {len(self.visible_events())} events to {path}", kind="success")

    def export_csv(self, path: Path) -> Path:
        """Write the shown events to ``path``, and the run's provenance to
        ``<path>.provenance.json`` (as the Mission Output export does)."""
        event_model.write_csv(self.visible_events(), path, self._epoch_utc)
        provenance = getattr(self._result, "provenance", None)
        if provenance is not None:  # provenance on every output (UX/UI guidelines)
            output_provenance.write_sidecar(path, provenance.to_dict())
        return path
