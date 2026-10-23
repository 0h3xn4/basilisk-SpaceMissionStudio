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

"""DataTable (UI overhaul M6b): a table of values with the table rules
(CLAUDE.md, Tables), for the views that showed a ``QTableWidget``.

- a ``QTableView`` over :class:`DataModel` (a ``QAbstractTableModel``),
  through :class:`_Filter` (a ``QSortFilterProxyModel``);
- a sticky header; numeric columns right-aligned in the numeric font,
  their unit in the header; no zebra; row hover (the style sheet);
- Ctrl+C and :meth:`DataTable.copy` copy the selected rows (or every
  shown row) as TSV with the header; :meth:`DataTable.text` is the same
  text for the rows shown;
- the header's context menu shows and hides columns;
- a group row (:class:`Row` ``group=True``) spans the table, in the
  heading weight on the selected-row surface;
- filtering is a predicate on the model's rows (:meth:`DataTable.set_row_filter`);
  columns can be hidden (:meth:`DataTable.set_hidden_columns`);
- an empty state (its text, and a primary action when one is given)
  instead of an empty grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from PySide6.QtCore import QAbstractTableModel, QObject, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QMenu, QPushButton, QStackedWidget,
                               QTableView, QVBoxLayout, QWidget)

from .theme import TOKENS, numeric_font, set_role, ui_font

_SORT_ROLE = Qt.ItemDataRole.UserRole  # a cell's sort key (Row.keys)
_SIZED_ROWS = 200  # rows a column's width is measured from


@dataclass
class Row:
    """One row: a text per column; ``tooltips`` by column; ``keys`` the
    values a sortable table sorts by (default: the texts); ``group`` makes
    it a heading row across the table (its first cell only); ``bold`` sets
    the row in the heading weight (Budget's worst case); ``muted`` are
    columns in the secondary colour (Compare's "(same)")."""

    cells: Sequence[str]
    tooltips: Dict[int, str] = field(default_factory=dict)
    keys: Optional[Sequence] = None
    group: bool = False
    bold: bool = False
    muted: frozenset = frozenset()


class DataModel(QAbstractTableModel):
    """The rows of a :class:`DataTable`."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.headers: List[str] = []
        self.header_tooltips: Dict[int, str] = {}
        self.bold_columns: set = set()
        self.numeric: set = set()  # columns of numbers
        self.rows: List[Row] = []
        # Made once: data() is asked for every cell's font while the view sizes
        # its columns, and a QFont with its features is slow to make.
        self._numeric_font = numeric_font()
        self._heading_font = ui_font("small", "semibold")

    def set_table(self, headers: Sequence[str], rows: Sequence[Row], numeric: Sequence[int] = ()) -> None:
        self.beginResetModel()
        self.headers, self.rows, self.numeric = list(headers), list(rows), set(numeric)
        self.header_tooltips, self.bold_columns = {}, set()
        self.endResetModel()

    def set_header_marks(self, bold: Sequence[int], tooltips: Dict[int, str]) -> None:
        """Columns whose header is in bold (Output's report at the time cursor), and header tooltips."""
        self.bold_columns, self.header_tooltips = set(bold), dict(tooltips)
        if self.headers:
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(self.headers) - 1)

    def rowCount(self, parent=None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    def columnCount(self, parent=None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.headers)

    def text(self, row: int, column: int) -> str:
        cells = self.rows[row].cells
        return cells[column] if column < len(cells) else ""

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, column = self.rows[index.row()], index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self.text(index.row(), column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.tooltips.get(column)
        if role == _SORT_ROLE:
            return row.keys[column] if row.keys is not None and column < len(row.keys) else self.text(index.row(),
                                                                                                         column)
        if row.group:
            if role == Qt.ItemDataRole.FontRole:
                return self._heading_font
            if role == Qt.ItemDataRole.BackgroundRole:
                return QColor(TOKENS["bg.selected"])  # looked up when drawn: it follows a theme change
            return None
        if role == Qt.ItemDataRole.FontRole and row.bold:
            return self._heading_font
        if role == Qt.ItemDataRole.ForegroundRole and column in row.muted:
            return QColor(TOKENS["text.secondary"])  # looked up when drawn: it follows a theme change
        if column in self.numeric:
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if role == Qt.ItemDataRole.FontRole:
                return self._numeric_font
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802 -- Qt API name
        if orientation != Qt.Orientation.Horizontal or not 0 <= section < len(self.headers):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.header_tooltips.get(section)
        if role == Qt.ItemDataRole.FontRole and section in self.bold_columns:
            return self._heading_font
        if role == Qt.ItemDataRole.TextAlignmentRole and section in self.numeric:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class _Filter(QSortFilterProxyModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.predicate: Optional[Callable[[int], bool]] = None

    def filterAcceptsRow(self, source_row, source_parent) -> bool:  # noqa: N802 -- Qt API name
        return self.predicate is None or self.predicate(source_row)


class _View(QTableView):
    copy_requested = Signal()

    def keyPressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_requested.emit()
            return
        super().keyPressEvent(event)


class DataTable(QWidget):
    """A table of values (see the module docstring). ``action_requested``:
    the empty state's primary action."""

    action_requested = Signal()
    row_chosen = Signal(int)  # the model row picked (set_single_pick)

    def __init__(self, empty_text: str = "Nothing to show.", action: Optional[str] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.addStretch(1)
        self.empty_label = set_role(QLabel(empty_text), tone="secondary")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        self.empty_button = set_role(QPushButton(action or ""), variant="primary")
        self.empty_button.setVisible(action is not None)
        self.empty_button.clicked.connect(self.action_requested)
        empty_layout.addWidget(self.empty_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)
        self.stack.addWidget(self.empty)

        self.model = DataModel(self)
        self.proxy = _Filter(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(_SORT_ROLE)
        self.view = _View()
        self.view.setModel(self.proxy)
        self.view.verticalHeader().setVisible(False)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setWordWrap(False)
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.view.copy_requested.connect(lambda: QGuiApplication.clipboard().setText(self.copy_text()))
        header = self.view.horizontalHeader()
        header.setResizeContentsPrecision(_SIZED_ROWS)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_menu)
        self.stack.addWidget(self.view)
        self.stack.setCurrentWidget(self.empty)

    # -- content ------------------------------------------------------------------------------
    def set_table(self, headers: Sequence[str], rows: Sequence[Row], numeric: Sequence[int] = (),
                  stretch: int = 0) -> None:
        """Show ``rows`` under ``headers``; ``numeric`` are the columns of
        numbers; column ``stretch`` takes the width left, the others their
        content's."""
        self.view.setUpdatesEnabled(False)
        self.model.set_table(headers, rows, numeric)
        header = self.view.horizontalHeader()
        for column in range(len(headers)):
            # Sized to their content once, here, not on every layout of the view
            # (that asked for every cell's text and font at each one, M6b).
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch if column == stretch
                                        else QHeaderView.ResizeMode.Interactive)
            self.view.setColumnHidden(column, False)
        self.view.resizeColumnsToContents()
        self._update_spans()
        self.view.setUpdatesEnabled(True)
        self.stack.setCurrentWidget(self.view if rows else self.empty)

    def clear(self, empty_text: Optional[str] = None) -> None:
        self.model.set_table([], [])
        self.view.clearSpans()
        if empty_text is not None:
            self.empty_label.setText(empty_text)
        self.stack.setCurrentWidget(self.empty)

    def set_empty_text(self, text: str) -> None:
        self.empty_label.setText(text)

    def set_row_filter(self, predicate: Optional[Callable[[int], bool]]) -> None:
        """Show the model rows ``predicate(row)`` accepts (None: every row)."""
        self.proxy.predicate = predicate
        self.proxy.invalidate()
        self._update_spans()

    def set_hidden_columns(self, columns: Sequence[int]) -> None:
        hidden = set(columns)
        for column in range(self.model.columnCount()):
            self.view.setColumnHidden(column, column in hidden)

    def set_single_pick(self) -> None:
        """One row at a time is picked; ``row_chosen`` carries it (a model row)."""
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.selectionModel().selectionChanged.connect(self._on_picked)

    def _on_picked(self, *_args) -> None:
        rows = self.view.selectionModel().selectedRows()
        if rows:
            self.row_chosen.emit(self.proxy.mapToSource(rows[0]).row())

    def chosen_row(self) -> Optional[int]:
        """The model row picked, or None."""
        rows = self.view.selectionModel().selectedRows()
        return self.proxy.mapToSource(rows[0]).row() if rows else None

    def fit_rows(self) -> None:
        """As tall as its rows: a short table under others needs no scroll bar of its own."""
        header = self.view.horizontalHeader()
        self.view.setFixedHeight(header.height() + sum(self.view.rowHeight(r) for r in range(self.row_count())) + 4)

    def row_is_bold(self, row: int) -> bool:
        """The shown row ``row`` is in the heading weight."""
        return self.model.rows[self.shown_rows()[row]].bold

    def set_sortable(self, column: int = 0, order=Qt.SortOrder.AscendingOrder) -> None:
        """Sort by a header click, by the rows' keys; sorted by ``column`` first."""
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(column, order)

    def sort_by(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        self.view.sortByColumn(column, order)

    def column_count(self) -> int:
        return self.model.columnCount()

    def set_header_marks(self, bold: Sequence[int] = (), tooltips: Optional[Dict[int, str]] = None) -> None:
        self.model.set_header_marks(bold, tooltips or {})

    def _update_spans(self) -> None:
        self.view.clearSpans()
        columns = self.model.columnCount()
        if not any(row.group for row in self.model.rows):
            return
        for row in range(self.proxy.rowCount()):
            source = self.proxy.mapToSource(self.proxy.index(row, 0)).row()
            if self.model.rows[source].group and columns > 1:
                self.view.setSpan(row, 0, 1, columns)

    # -- reading it ---------------------------------------------------------------------------
    def row_count(self) -> int:
        """The rows shown."""
        return self.proxy.rowCount()

    def shown_rows(self) -> List[int]:
        """The model rows shown, in their order."""
        return [self.proxy.mapToSource(self.proxy.index(row, 0)).row() for row in range(self.proxy.rowCount())]

    def shown_columns(self) -> List[int]:
        return [c for c in range(self.model.columnCount()) if not self.view.isColumnHidden(c)]

    def header_text(self, column: int) -> str:
        return self.model.headers[column]

    def header_is_bold(self, column: int) -> bool:
        return column in self.model.bold_columns

    def cell(self, row: int, column: int) -> str:
        """The text of the shown row ``row``, column ``column``."""
        return self.model.text(self.shown_rows()[row], column)

    def cell_alignment(self, row: int, column: int) -> int:
        """The alignment flags of the shown row ``row``'s cell (0: the default, left)."""
        index = self.proxy.index(row, column)
        return int(self.proxy.data(index, Qt.ItemDataRole.TextAlignmentRole) or 0)

    def cell_tooltip(self, row: int, column: int) -> Optional[str]:
        return self.model.rows[self.shown_rows()[row]].tooltips.get(column)

    def _tsv(self, rows: List[int]) -> str:
        columns = self.shown_columns()
        lines = ["\t".join(self.model.headers[c].replace("\n", " ") for c in columns)]
        for row in rows:
            lines.append("\t".join(self.model.text(row, c) for c in columns).rstrip("\t"))
        return "\n".join(lines)

    def text(self) -> str:
        """The rows shown as tab-separated text, the header first."""
        return self._tsv(self.shown_rows())

    def copy_text(self) -> str:
        """The selected rows (every row shown when none is) as TSV."""
        selected = sorted({self.proxy.mapToSource(index).row()
                           for index in self.view.selectionModel().selectedRows()})
        return self._tsv(selected or self.shown_rows())

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.copy_text())

    def _on_header_menu(self, at) -> None:
        menu = QMenu(self)
        for column, name in enumerate(self.model.headers):
            action = menu.addAction(name.replace("\n", " "))
            action.setCheckable(True)
            action.setChecked(not self.view.isColumnHidden(column))
            action.setEnabled(column != 0)  # the first column names the row
            action.toggled.connect(lambda on, c=column: self.view.setColumnHidden(c, not on))
        menu.popup(self.view.horizontalHeader().mapToGlobal(at))
        self.column_menu = menu  # kept while it is open
