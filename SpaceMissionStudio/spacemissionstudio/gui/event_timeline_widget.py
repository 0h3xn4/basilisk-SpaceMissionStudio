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

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSplitter, QToolTip, QVBoxLayout, QWidget)

from . import export_log
from .. import output_provenance
from ..engine import events as event_model
from ..engine.results import ResultSet
from .data_table import DataTable, LazyRows, Row
from .feedback import report
from .theme import PALETTE, SERIES_COLORS, set_role
from .time_cursor import TimeCursor, describe

# Fixed categorical order, one slot per kind (the Results tab's series colours).
KIND_SLOTS: dict[str, int] = {kind: index for index, kind in enumerate(event_model.KINDS)}


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


def _event_text(event: event_model.Event) -> str:
    """What the search looks in: the event's text, any case."""
    return " ".join((event.kind, event.spacecraft, event.other, event.label, event.detail)).lower()


def _matches(event: event_model.Event, words: list[str]) -> bool:
    """Every search word appears in the event's text (any case)."""
    text = _event_text(event)
    return all(word in text for word in words)


_UTC_BLOCK = 128  # events whose UTC times are worked out together, when a row of them is first shown


class _EventRows(LazyRows):
    """The table's rows, made when the view shows them (UI overhaul M7: a
    QTableWidgetItem a cell for 10,000 events held the window for seconds);
    sorted by each column's values with NumPy."""

    def __init__(self, events: list[event_model.Event], headings: list[str], keys: list[str],
                 epoch_utc: str | None) -> None:
        super().__init__(len(events))
        self.events, self.headings, self.keys, self.epoch_utc = events, headings, keys, epoch_utc
        self.utc = headings[0] == "Start (UTC)"
        self.order = np.arange(len(events))
        self._utc_blocks: dict[int, tuple] = {}

    def event(self, index: int) -> event_model.Event:
        """The event of row ``index`` in the order shown."""
        return self.events[int(self.order[index])]

    def _utc(self, position: int) -> tuple:
        block = position // _UTC_BLOCK
        texts = self._utc_blocks.get(block)
        if texts is None:
            from ..engine import time_system

            chunk = self.events[block * _UTC_BLOCK:(block + 1) * _UTC_BLOCK]
            moments = time_system.elapsed_to_utc(self.epoch_utc, [e.start_s for e in chunk]
                                                 + [e.end_s for e in chunk])  # one call: each has a fixed cost
            texts = [event_model.utc_text(m, "seconds") for m in moments]
            texts = self._utc_blocks[block] = (texts[:len(chunk)], texts[len(chunk):])
        return texts[0][position % _UTC_BLOCK], texts[1][position % _UTC_BLOCK]

    def make(self, index: int) -> Row:
        position = int(self.order[index])
        event = self.events[position]
        if self.utc:
            cells = list(self._utc(position))
        else:
            cells = [f"{event.start_s / 3600.0:.4f}", f"{event.end_s / 3600.0:.4f}"]
        cells += [f"{event.duration_s / 60.0:.2f}", event.label]
        if "Spacecraft" in self.headings:
            cells.append(event.spacecraft)
        if "Station" in self.headings:
            cells.append(event.other)
        for key in self.keys:
            value = event.quantity(key)
            cells.append("" if value is None else format(value, event_model.QUANTITIES[key][2]))
        tip = f"T+{event.start_s:.1f} s" + (f"\n{event.detail}" if event.detail else "")
        tooltips = dict.fromkeys(range(len(cells)), tip)
        if "Note" in self.headings:
            tooltips[len(cells)] = event.note
            cells.append(event.note)
        return Row(cells, tooltips=tooltips)

    def sort_keys(self, column: int) -> np.ndarray:
        heading = self.headings[column]
        events = self.events
        if heading.startswith("Start"):
            return np.array([e.start_s for e in events])
        if heading.startswith("End"):
            return np.array([e.end_s for e in events])
        if heading.startswith("Duration"):
            return np.array([e.duration_s for e in events])
        texts = {"Event": lambda e: e.label, "Spacecraft": lambda e: e.spacecraft, "Station": lambda e: e.other,
                 "Note": lambda e: e.note}.get(heading)
        if texts is not None:
            return np.array([texts(e) for e in events], dtype=object)
        key = self.keys[column - (len(self.headings) - len(self.keys) - ("Note" in self.headings))]
        return np.array([-np.inf if e.quantity(key) is None else e.quantity(key) for e in events])

    def sort(self, column: int, descending: bool) -> None:
        if not 0 <= column < len(self.headings):
            return
        order = np.argsort(self.sort_keys(column), kind="stable")
        self.order = order[::-1] if descending else order


class _Lane:
    """One lane of the timeline: its events (``index`` into the timeline's
    list) by start, and their ends' running maximum (to find those in view)."""

    def __init__(self, index: np.ndarray, starts: np.ndarray, ends: np.ndarray, kind_codes: np.ndarray,
                 kind_names: list[str]) -> None:
        self.index = index
        self.starts, self.ends = starts[index], ends[index]  # [s]
        self.reach = np.maximum.accumulate(self.ends) if self.ends.size else self.ends  # [s]
        codes = kind_codes[index]
        present = np.unique(codes)
        self.kinds = [kind_names[code] for code in present]
        self.kind_of = np.searchsorted(present, codes)

    def in_view(self, start: float, end: float) -> slice:
        """The events that overlap ``start`` to ``end`` [s] are within this slice."""
        return slice(int(np.searchsorted(self.reach, start, "left")), int(np.searchsorted(self.starts, end, "right")))


# UTC tick steps [s]: minutes to years, round in UTC
_UTC_STEPS_S = (60, 300, 600, 900, 1800, 3600, 2 * 3600, 3 * 3600, 6 * 3600, 12 * 3600, 86400, 2 * 86400,
                7 * 86400, 14 * 86400, 30 * 86400, 91 * 86400, 182 * 86400, 365 * 86400)
_PAN_STEP = 0.1  # [-] of the visible span, an arrow key
_ZOOM_STEP = 0.8  # [-] the visible span after one zoom-in step


class GanttView(QWidget):
    """The timeline: one row per spacecraft and kind (per station for a
    pass). The wheel zooms around the pointer; Shift+wheel, a horizontal
    wheel and a right- or middle-button drag pan; +/- zoom, the arrow keys
    pan, 0 or Home fits. A left click or drag sets the time cursor."""

    time_picked = Signal(float)  # [s]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(_AXIS_HEIGHT + 2 * _ROW_HEIGHT)
        self.events: list[event_model.Event] = []
        self.rows: list[str] = []
        self.lanes: list[_Lane] = []
        self.cursor_s: float | None = None
        self.run_end_s = 1.0  # [s]
        self.view = (0.0, 1.0)  # [s] the visible time span
        self.epoch_utc: str | None = None
        self._utc_span: tuple | None = None
        self._utc_key: tuple | None = None  # (epoch, run end) the span is of
        self._pan_from: tuple | None = None  # (x [px], view) while a drag pans

    def set_events(self, events: list[event_model.Event], run_end_s: float, epoch_utc: str | None = None) -> None:
        """Show ``events``: arrays and lanes made with NumPy (M7: 10,000 events
        sorted and split in Python held the window 30-110 ms)."""
        self.events = events
        self.epoch_utc = epoch_utc
        count = len(events)
        rows = [e.row for e in events]
        kinds = [e.kind for e in events]
        self.rows = list(dict.fromkeys(row for _kind, row in sorted(set(zip(kinds, rows)))))
        row_code = {row: code for code, row in enumerate(self.rows)}
        kind_names = sorted(set(kinds))
        kind_code = {kind: code for code, kind in enumerate(kind_names)}
        starts = np.fromiter((e.start_s for e in events), float, count)  # [s]
        ends = np.fromiter((e.end_s for e in events), float, count)  # [s]
        codes = np.fromiter((row_code[row] for row in rows), int, count)
        kind_codes = np.fromiter((kind_code[kind] for kind in kinds), int, count)
        order = np.lexsort((starts, codes))  # by lane, then start
        bounds = np.searchsorted(codes[order], np.arange(len(self.rows) + 1))
        self.lanes = [_Lane(order[bounds[lane]:bounds[lane + 1]], starts, ends, kind_codes, kind_names)
                      for lane in range(len(self.rows))]
        self.run_end_s = max(run_end_s, float(ends.max()) if count else 0.0, 1.0)  # [s]
        if (epoch_utc, self.run_end_s) != self._utc_key:  # once a run, not at each filter (~10 ms a conversion)
            self._utc_key, self._utc_span = (epoch_utc, self.run_end_s), None  # (UTC at 0, at the run's end)
            if epoch_utc:
                from ..engine import time_system

                try:
                    self._utc_span = tuple(time_system.elapsed_to_utc(epoch_utc, [0.0, self.run_end_s]))
                except ValueError:
                    pass
        self.fit()
        self.setMinimumHeight(_AXIS_HEIGHT + max(len(self.rows), 2) * _ROW_HEIGHT + 4)

    def fit(self) -> None:
        self.view = (0.0, self.run_end_s)
        self.update()

    def set_cursor_time(self, time_s: float | None) -> None:
        self.cursor_s = time_s
        self.update()

    def _show(self, start: float, width: float) -> None:
        """Show ``width`` [s] from ``start``, kept within the run."""
        width = min(max(width, 1.0), self.run_end_s)  # [s] one second across at most
        start = min(max(start, 0.0), self.run_end_s - width)
        self.view = (start, start + width)
        self.update()

    def zoom(self, factor: float, centre_s: float | None = None) -> None:
        """Scale the visible span by ``factor`` (< 1 zooms in) around ``centre_s`` (default: its middle)."""
        start, end = self.view
        centre = (start + end) / 2.0 if centre_s is None else centre_s
        width = (end - start) * factor
        self._show(centre - (centre - start) * width / (end - start), width)

    def pan(self, fraction: float) -> None:
        """Move the visible span by ``fraction`` of its width (> 0: later)."""
        start, end = self.view
        self._show(start + fraction * (end - start), end - start)

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

    def event_at(self, point: QPointF) -> event_model.Event | None:
        row = int(point.y() // _ROW_HEIGHT)
        if not 0 <= row < len(self.rows):
            return None
        time_s = self.time_at(point.x())
        tolerance_s = (self.view[1] - self.view[0]) / max(self._plot_rect().width(), 1.0) * 3  # [s] 3 px
        lane = self.lanes[row]
        near = lane.in_view(time_s - tolerance_s, time_s + tolerance_s)
        return next((self.events[i] for i in lane.index[near]
                     if self.events[i].start_s - tolerance_s <= time_s <= self.events[i].end_s + tolerance_s), None)

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
        start, end = self.view
        scale = rect.width() / (end - start)  # [px/s]
        painter.setPen(Qt.PenStyle.NoPen)
        for index, lane in enumerate(self.lanes):
            shown = lane.in_view(start, end)
            if shown.start >= shown.stop:
                continue
            top = index * _ROW_HEIGHT + 4
            x0 = rect.left() + (np.maximum(lane.starts[shown], start) - start) * scale  # [px]
            x1 = np.maximum(rect.left() + (np.minimum(lane.ends[shown], end) - start) * scale, x0 + _MIN_BAR_PX)
            kinds = lane.kind_of[shown]
            for kind_index, kind in enumerate(lane.kinds):
                mine = kinds == kind_index
                if not mine.any():
                    continue
                painter.setBrush(QColor(kind_colour(kind)))
                for left, right in _merged(x0[mine], x1[mine]):
                    painter.drawRoundedRect(QRectF(left, top, right - left, _ROW_HEIGHT - 8), 2, 2)
        if self.cursor_s is not None and start <= self.cursor_s <= end:
            x = self.x_of(self.cursor_s)
            painter.setPen(QPen(QColor(PALETTE["accent"]), 2))  # the time cursor: a selection
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.bottom()))

    def _ticks(self) -> list[tuple]:
        """``(time [s], label)`` of each tick in view: round UTC times with
        Z when the run has an epoch (UI overhaul M7), else elapsed hours or days."""
        start, end = self.view
        width_px = max(self._plot_rect().width(), 1.0)
        if self._utc_span is not None:
            from datetime import datetime, timedelta

            # Between the run's two ends, UTC follows elapsed time to within
            # milliseconds (TDB - UTC drifts that little): enough for ticks
            # labelled to the minute, without a conversion at every paint.
            zero, run_end = self._utc_span
            per_s = (run_end - zero).total_seconds() / self.run_end_s  # [-] UTC seconds per elapsed second
            first, last = zero + timedelta(seconds=start * per_s), zero + timedelta(seconds=end * per_s)
            span_s = max((last - first).total_seconds(), 1.0)  # [s]
            step_s = next((s for s in _UTC_STEPS_S if span_s / s <= width_px / 90.0), _UTC_STEPS_S[-1])
            day = datetime(first.year, first.month, first.day)
            tick = day + timedelta(seconds=np.ceil((first - day).total_seconds() / step_s) * step_s) \
                if step_s < 86400 else day + timedelta(days=1 if first > day else 0)
            ticks = []
            while tick <= last and len(ticks) < 200:
                time_s = start + (tick - first).total_seconds() * (end - start) / span_s
                if step_s < 86400 and (tick.hour or tick.minute):
                    label = f"{tick:%H:%M}Z"
                else:
                    label = f"{tick:%Y-%m-%d}"
                ticks.append((time_s, label))
                tick += timedelta(seconds=step_s) if step_s < 86400 else timedelta(days=step_s // 86400)
            return ticks
        span_h = (end - start) / 3600.0  # [h]
        step_h = next((s for s in (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 6, 12, 24, 48, 168, 720, 2160, 8760)
                       if span_h / s <= 8), 8760.0)  # [h]
        tick_h = np.ceil(start / 3600.0 / step_h) * step_h  # [h]
        ticks = []
        while tick_h <= end / 3600.0:
            ticks.append((tick_h * 3600.0, f"{tick_h / 24:g} d" if step_h >= 24 else f"{tick_h:g} h"))
            tick_h += step_h
        return ticks

    def _paint_axis(self, painter: QPainter, rect: QRectF, muted: QColor, grid: QColor) -> None:
        for time_s, label in self._ticks():
            x = self.x_of(time_s)
            painter.setPen(grid)
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.bottom()))
            painter.setPen(muted)
            painter.drawText(QRectF(x - 45, rect.bottom() + 2, 90, _AXIS_HEIGHT - 4), Qt.AlignmentFlag.AlignCenter,
                             label)

    # -- mouse and keys ---------------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._pan_from = (event.position().x(), self.view)
        elif event.button() == Qt.MouseButton.LeftButton and event.position().x() >= self._plot_rect().left():
            self.time_picked.emit(self.time_at(event.position().x()))

    def mouseReleaseEvent(self, event):  # noqa: N802 -- Qt API name
        self._pan_from = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 -- Qt API name
        if self._pan_from is not None:
            x, (start, end) = self._pan_from
            moved_s = (x - event.position().x()) / max(self._plot_rect().width(), 1.0) * (end - start)  # [s]
            self._show(start + moved_s, end - start)
            return
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
        """Zoom around the pointer, in to one second across at most;
        Shift+wheel or a horizontal wheel pans."""
        delta = event.angleDelta()
        if delta.x() or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            steps = (delta.x() or delta.y()) / 120.0
            self.pan(-steps * _PAN_STEP)
            return
        self.zoom(_ZOOM_STEP if delta.y() > 0 else 1.0 / _ZOOM_STEP, self.time_at(event.position().x()))

    def keyPressEvent(self, event):  # noqa: N802 -- Qt API name
        key = event.key()
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom(_ZOOM_STEP)
        elif key == Qt.Key.Key_Minus:
            self.zoom(1.0 / _ZOOM_STEP)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.pan(_PAN_STEP if key == Qt.Key.Key_Right else -_PAN_STEP)
        elif key in (Qt.Key.Key_0, Qt.Key.Key_Home):
            self.fit()
        else:
            super().keyPressEvent(event)


def _merged(x0: np.ndarray, x1: np.ndarray) -> list[tuple]:
    """The spans ``x0`` to ``x1`` [px] (by ``x0``) joined where they touch:
    a year of passes is a few hundred rectangles, not thousands."""
    if x0.size == 0:
        return []
    reach = np.maximum.accumulate(x1)
    starts = np.flatnonzero(np.concatenate([[True], x0[1:] > reach[:-1] + 1.0]))
    ends = np.concatenate([starts[1:], [x0.size]]) - 1
    return list(zip(x0[starts].tolist(), reach[ends].tolist()))


class EventTimelineWidget(QWidget):
    """The Timeline area (the run's events)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cursor: TimeCursor | None = None
        self._result: ResultSet | None = None
        self._epoch_utc: str | None = None
        self.events: list[event_model.Event] = []
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.kind_boxes: dict[str, QCheckBox] = {}
        for kind in event_model.KINDS:
            box = QCheckBox(_plural(kind, 2)[2:].capitalize())
            box.setChecked(True)
            set_role(box, series=str(KIND_SLOTS[kind]))  # a swatch of the kind's colour
            box.toggled.connect(self._apply_filter)
            controls.addWidget(box)
            self.kind_boxes[kind] = box
        controls.addStretch(1)
        self.fit_button = QPushButton("Fit")
        self.fit_button.setToolTip("Show the whole run (0). The wheel or +/- zooms the timeline; Shift+wheel, the "
                                   "arrow keys or a right-button drag move it.")
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
        # A DataTable whose rows are made when shown (UI overhaul M7): 10,000 events at once.
        self.table = DataTable("No events in this run.", direct=True)  # filtered here, sorted by its rows
        self.table.view.setAccessibleName("Events")
        self.table.set_presorted()
        self.table.view.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)  # earliest first
        self.table.view.clicked.connect(lambda index: self._on_row_clicked(index.row()))
        self._filling = False
        self.table.view.selectionModel().currentRowChanged.connect(self._on_current_row_changed)
        self._texts: list[str] = []  # each event's search text, made once a run
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

    def set_result(self, result: ResultSet | None, epoch_utc: str | None = None) -> None:
        self._result, self._epoch_utc = result, epoch_utc
        self.events = event_model.extract_events(result)
        self._texts = [_event_text(event) for event in self.events]
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

    def visible_events(self) -> list[event_model.Event]:
        """The events the kind boxes, the station filter and the search let
        through: what the timeline, the table and the export show."""
        shown = {kind for kind, box in self.kind_boxes.items() if box.isChecked()}
        station = self.station_combo.currentText()
        words = self.search.text().lower().split()
        any_station = station in ("", _ALL_STATIONS)
        return [e for e, text in zip(self.events, self._texts)
                if e.kind in shown and (any_station or e.other == station) and all(w in text for w in words)]

    def _apply_filter(self) -> None:
        visible = self.visible_events()
        self.shown_label.setText(f"{len(visible)} of {len(self.events)} events shown"
                                 if len(visible) != len(self.events) else "")
        run_end = max((float(s.time_s[-1]) for s in self._result.series.values() if s.time_s.size),
                      default=0.0) if self._result is not None else 0.0  # [s]
        self.gantt.set_events(visible, run_end, self._epoch_utc)
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

    def _utc_texts(self, times_s: list[float]) -> list[str] | None:
        """UTC text for each elapsed time, or None without a usable epoch."""
        if not self._epoch_utc or not times_s:
            return None
        from ..engine import time_system

        try:
            return [event_model.utc_text(moment, "seconds")
                    for moment in time_system.elapsed_to_utc(self._epoch_utc, times_s)]
        except ValueError:
            return None

    def columns(self, visible: list[event_model.Event]) -> list[str]:
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

    def _fill_table(self, visible: list[event_model.Event]) -> None:
        headings = self.columns(visible)
        keys = event_model.present_quantities(visible)
        utc = headings[0] == "Start (UTC)"
        numeric = [c for c, h in enumerate(headings)
                   if (not utc and c < 2) or h.startswith("Duration") or h in self._quantity_headings(keys)]
        self._filling = True
        self.rows = _EventRows(visible, headings, keys, self._epoch_utc)
        # the unit under the name keeps the value columns narrow (Ctrl+C joins them again)
        self.table.set_table([heading.replace(" [", "\n[") for heading in headings], self.rows, numeric=numeric,
                             stretch=-1)
        header = self.table.view.horizontalHeader()
        self.table.sort_by(header.sortIndicatorSection() if header.sortIndicatorSection() < len(headings) else 0,
                           header.sortIndicatorOrder())  # the order chosen, earliest first until one is
        self._filling = False

    @staticmethod
    def _quantity_headings(keys: list[str]) -> list[str]:
        return [f"{event_model.QUANTITIES[key][0]} [{event_model.QUANTITIES[key][1]}]" for key in keys]

    # -- cursor -----------------------------------------------------------

    def _pick_time(self, time_s: float | None) -> None:
        if self._cursor is not None:
            self._cursor.set_time(time_s)
        else:
            self.on_cursor_changed(time_s)

    def row_event(self, row: int) -> event_model.Event:
        """The event of the table's shown row ``row``."""
        return self.rows.event(self.table.shown_rows()[row])

    def _on_row_clicked(self, row: int) -> None:
        if 0 <= row < self.table.row_count():
            self._pick_time(float(self.row_event(row).start_s))

    def _on_current_row_changed(self, current, previous) -> None:
        """The arrow keys move the cursor from row to row, as a click does."""
        if not self._filling and current.isValid() and current.row() != previous.row():
            self._on_row_clicked(current.row())

    def on_cursor_changed(self, time_s: float | None) -> None:
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
        export_log.record("events_csv", path)
        report(self, f"Exported {len(self.visible_events())} events to {path}", kind="success")

    def export_csv(self, path: Path) -> Path:
        """Write the shown events to ``path``, and the run's provenance to
        ``<path>.provenance.json`` (as the Mission Output export does)."""
        event_model.write_csv(self.visible_events(), path, self._epoch_utc)
        provenance = getattr(self._result, "provenance", None)
        if provenance is not None:  # provenance on every output (UX/UI guidelines)
            output_provenance.write_sidecar(path, provenance.to_dict())
        return path
