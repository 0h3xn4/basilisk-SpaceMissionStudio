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

"""The Results readout (docs/ux-audit.md U-25): every shown series' value
at one time, with its unit -- the time under the pointer while it is over
a plot, else the shared time cursor's.

:func:`value_at` reads a sample: linearly interpolated between the two
samples around the time, except for a series that wraps (an angle in
[0, 360) deg) or steps (whole numbers that hold between most samples,
such as a mode or an on/off state), which show the last sample at or
before the time. Values are in
the plot's display units (km, deg, ...), as the plot shows them.
"""

from __future__ import annotations


import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ..engine.results import TimeSeries
from .theme import set_role


def _is_stepped(column: np.ndarray) -> bool:
    """Whole numbers that hold between most samples (a mode, a state, an
    on/off flag), not a smooth series that happens to be whole."""
    finite = column[np.isfinite(column)]
    if len(finite) < 2 or not np.all(finite == np.round(finite)):
        return False
    return bool(np.mean(np.diff(finite) == 0) > 0.5)


def value_at(series: TimeSeries, column: int, time_s: float, factor: float = 1.0,
             wraps: bool = False) -> float | None:
    """Column ``column`` of ``series`` at ``time_s`` [s], times ``factor``,
    or None outside the recorded span."""
    times = np.asarray(series.time_s, dtype=float)
    if not len(times) or time_s < times[0] or time_s > times[-1]:
        return None
    data = np.asarray(series.data[:, column], dtype=float)
    if wraps or _is_stepped(data):
        index = int(np.searchsorted(times, time_s, side="right")) - 1
        value = data[max(index, 0)]
    else:
        value = float(np.interp(time_s, times, data))
    return None if not np.isfinite(value) else float(value) * factor


def format_value(value: float | None) -> str:
    """Six significant digits, without an exponent for everyday sizes."""
    if value is None:
        return "-"
    if value != 0.0 and (abs(value) >= 1e7 or abs(value) < 1e-4):
        return f"{value:.5e}"
    return f"{value:,.6g}" if abs(value) >= 1e4 else f"{value:.6g}"


class ReadoutPanel(QWidget):
    """A table of (series, value, unit) rows, one block per shown plot."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.time_label = QLabel("Readout: click a plot or point at it")
        self.time_label.setWordWrap(True)
        set_role(self.time_label, tone="secondary")
        layout.addWidget(self.time_label)
        self.table = QTableWidget(0, 3)
        self.table.setTabKeyNavigation(False)  # read-only: Tab leaves the table; the arrows move in it (M9)
        self.table.setHorizontalHeaderLabels(["Series", "Value", "Unit"])
        self.table.setAccessibleName("Readout")
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

    def show_rows(self, heading: str, blocks: list[tuple[str, list[tuple[str, float | None, str]]]]) -> None:
        """``heading`` the time; ``blocks`` ``(plot title, [(label, value, unit), ...])``."""
        self.time_label.setText(heading)
        rows = sum(1 + len(lines) for _title, lines in blocks)
        self.table.clearSpans()
        self.table.setRowCount(rows)
        row = 0
        for title, lines in blocks:
            item = QTableWidgetItem(title)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setToolTip(title)
            self.table.setItem(row, 0, item)
            self.table.setSpan(row, 0, 1, 3)
            row += 1
            for label, value, unit in lines:
                self.table.setItem(row, 0, QTableWidgetItem(f"  {label}"))
                value_item = QTableWidgetItem(format_value(value))
                value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 1, value_item)
                self.table.setItem(row, 2, QTableWidgetItem(unit))
                row += 1

    def rows(self) -> list[tuple[str, str, str]]:
        """The table's text, row by row (for tests and copying)."""
        out = []
        for row in range(self.table.rowCount()):
            cells = [self.table.item(row, column) for column in range(3)]
            out.append(tuple(cell.text().strip() if cell is not None else "" for cell in cells))
        return out
