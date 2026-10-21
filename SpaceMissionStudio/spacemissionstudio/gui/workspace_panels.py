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

"""The panels of the app shell's workspace (UX/UI Standard, "Target layout";
docs/ux-audit.md U-02, U-05, U-23):

* :class:`InspectorWidget` -- the focused field: its label, value, allowed
  range and help text (a right dock).
* :class:`ProblemsWidget` -- the scenario's validation error and plausibility
  warnings as a table (severity, ID, object, message; the Problems panel at
  the bottom); Enter or a double-click opens where one is fixed.
* :class:`LogViewWidget` -- the session's log, filterable by level and text
  (the *Log* tab). :func:`install_log_view` attaches it to the root logger.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Sequence, Tuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QSpinBox, QTableView, QTextEdit, QVBoxLayout, QWidget)

from .feedback import row_label
from .problem_location import JSON_VIEW, MISSION_SEQUENCE, PROPAGATION, SCENARIO, SPACECRAFT, locate
from .theme import ROW_HEIGHT, SPACE, TOKENS, icon, mono_font, set_role
from .widgets import ComboBox


def _empty_state(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("emptyState")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    set_role(label, role="empty")
    return label


def _plain(text: str) -> str:
    """A tooltip's text without its HTML."""
    return re.sub(r"<[^>]+>", "", text or "").replace("&nbsp;", " ").strip()


# -- Inspector ----------------------------------------------------------------

def field_label(widget: QWidget) -> str:
    """The label a form gives ``widget`` (or the row holding it), else its
    accessible name, else a check box's own text, else ""."""
    nested = row_label(widget)
    if nested:
        return nested
    node = widget
    for _level in range(3):  # a field can sit in a row widget inside the form
        parent = node.parentWidget()
        if parent is None:
            break
        layout = parent.layout()
        if isinstance(layout, QFormLayout):
            label = layout.labelForField(node)
            if isinstance(label, QLabel):
                return label.text().rstrip(":").strip()
        node = parent
    if widget.accessibleName():
        return widget.accessibleName()
    if isinstance(widget, QCheckBox):
        return widget.text()
    return ""


def field_value(widget: QWidget) -> str:
    if isinstance(widget, QAbstractSpinBox):
        return widget.text()
    if isinstance(widget, QLineEdit):
        return widget.text()
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, QCheckBox):
        return "on" if widget.isChecked() else "off"
    if isinstance(widget, (QPlainTextEdit, QTextEdit)):
        text = widget.toPlainText()
        return text if len(text) <= 200 else text[:200] + "..."
    return ""


def field_range(widget: QWidget) -> str:
    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        suffix = widget.suffix().strip()
        unit = f" {suffix}" if suffix else ""
        return f"{widget.minimum():g} to {widget.maximum():g}{unit}"
    return ""


class InspectorWidget(QWidget):
    """The focused field's details: label, value, allowed range and help."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.empty_label = _empty_state("Select a field to see its value, allowed range and help here.")
        layout.addWidget(self.empty_label)
        self.form = QWidget()
        form = QFormLayout(self.form)
        self.name_label = QLabel()
        self.name_label.setObjectName("inspectorName")
        self.name_label.setWordWrap(True)
        self.value_label = QLabel()
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.range_label = QLabel()
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        form.addRow("Field", self.name_label)
        form.addRow("Value", self.value_label)
        form.addRow("Allowed", self.range_label)
        form.addRow("Help", self.help_label)
        layout.addWidget(self.form)
        layout.addStretch(1)
        self.form.setVisible(False)
        self._widget: Optional[QWidget] = None

    def inspect(self, widget: Optional[QWidget]) -> None:
        """Show ``widget``'s details, or the empty state for None."""
        self._widget = widget
        self.refresh()

    def refresh(self) -> None:
        widget = self._widget
        try:
            alive = widget is not None and widget.isVisible() is not None
        except RuntimeError:  # its C++ object was deleted
            alive = False
        if not alive:
            self._widget = None
            self.empty_label.setVisible(True)
            self.form.setVisible(False)
            return
        name = field_label(widget) or _plain(widget.toolTip()).split("\n")[0] or type(widget).__name__
        self.name_label.setText(name)
        self.value_label.setText(field_value(widget) or "-")
        allowed = field_range(widget)
        self.range_label.setText(allowed or "-")
        self.help_label.setText(_plain(widget.toolTip()) or _plain(widget.whatsThis()) or "-")
        self.empty_label.setVisible(False)
        self.form.setVisible(True)


# -- Problems -----------------------------------------------------------------

PROBLEM_COLUMNS = ("Severity", "ID", "Object", "Message")
_SEVERITY = {"error": ("Error", "octagon-alert", "status.critical.text", 0),
             "warning": ("Warning", "triangle-alert", "status.caution.text", 1)}
_AREA_OBJECT = {SCENARIO: "Scenario", PROPAGATION: "Propagation setup", MISSION_SEQUENCE: "Mission sequence",
                JSON_VIEW: "JSON"}


@dataclass(frozen=True)
class Problem:
    """One row of the Problems panel: ``text`` is the message as raised (it
    says where it is fixed), ``shown`` the message in the user's terms;
    ``field`` (the ID column) and ``obj`` come from where it is fixed."""

    severity: str  # "error" or "warning"
    text: str
    shown: str
    field: str
    obj: str


def problem_row(severity: str, text: str, shown: str, spacecraft: Sequence[str] = (),
                stations: Sequence[str] = ()) -> Problem:
    """A problem with its ID (the field path it is about, "-" when it names
    none) and object (the scenario, the propagation setup, a spacecraft or
    a ground station, the mission sequence or the JSON page)."""
    location = locate(text, spacecraft, stations)
    if location is None:
        return Problem(severity, text, shown, "-", "Scenario")
    obj = _AREA_OBJECT.get(location.area, location.name)
    return Problem(severity, text, shown, location.path or "-", obj)


class ProblemsModel(QAbstractTableModel):
    """The problems as a table: severity (icon and word), ID, object,
    message. The severity's colour is looked up when drawn, so it follows a
    theme change."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.rows: List[Problem] = []

    def set_rows(self, rows: List[Problem]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: Optional[QModelIndex] = None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    def columnCount(self, parent: Optional[QModelIndex] = None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(PROBLEM_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802 -- Qt API name
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return PROBLEM_COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        problem, column = self.rows[index.row()], index.column()
        word, icon_name, tone, rank = _SEVERITY.get(problem.severity, ("Note", "info", "text.primary", 2))
        if role == Qt.ItemDataRole.DisplayRole:
            return (word, problem.field, problem.obj, problem.shown)[column]
        if role == Qt.ItemDataRole.DecorationRole and column == 0:
            return icon(icon_name, tone.rsplit(".", 1)[0])
        if role == Qt.ItemDataRole.ForegroundRole and column == 0:
            return QColor(TOKENS[tone])
        if role == Qt.ItemDataRole.FontRole and column == 1:
            return mono_font()
        if role == Qt.ItemDataRole.ToolTipRole:
            return ("Double-click to open the 3D model editor" if _MODEL_MARK in problem.text
                    else "Double-click to go to where it is fixed")
        if role == SORT_ROLE:
            # Errors first; within a severity, as the scenario lists them.
            return (rank, index.row()) if column == 0 else (str(self.data(index)).lower(), index.row())
        return None


SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class _SortProxy(QSortFilterProxyModel):
    def lessThan(self, left, right) -> bool:  # noqa: N802 -- Qt API name
        return left.data(SORT_ROLE) < right.data(SORT_ROLE)


class ProblemsTable(QTableView):
    """The problems; Ctrl+C copies the selected rows as TSV."""

    def keyPressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.matches(QKeySequence.StandardKey.Copy):
            QApplication.clipboard().setText(self.selection_tsv())
            event.accept()
            return
        super().keyPressEvent(event)

    def selection_tsv(self) -> str:
        """The selected rows, in the order shown, under a line of headings."""
        rows = sorted({index.row() for index in self.selectionModel().selectedIndexes()})
        if not rows:
            return ""
        model = self.model()
        columns = range(model.columnCount())
        lines = ["\t".join(model.headerData(c, Qt.Orientation.Horizontal) for c in columns)]
        lines += ["\t".join(str(model.index(row, c).data()) for c in columns) for row in rows]
        return "\n".join(lines) + "\n"


class ProblemsWidget(QWidget):
    """The scenario's validation error and plausibility warnings: the
    Problems panel at the bottom of the window (UI overhaul M2b)."""

    activated = Signal(str)  # a problem was activated (its text): show where to fix it
    count_changed = Signal(int)
    counts_changed = Signal(int, int)  # errors, warnings

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.empty_label = _empty_state("No problems: the scenario is valid.")
        self.model = ProblemsModel(self)
        self.proxy = _SortProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = ProblemsTable()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.activated.connect(self._on_activated)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table, 1)
        self.problems: List[Tuple[str, str]] = []
        self.set_problems([])

    def _on_activated(self, index) -> None:
        self.activated.emit(self.problem_at(index.row()).text)

    def problem_at(self, row: int) -> Problem:
        """The problem shown in row ``row`` (the table's order)."""
        return self.model.rows[self.proxy.mapToSource(self.proxy.index(row, 0)).row()]

    def index_of(self, problem: int) -> QModelIndex:
        """The table's index of ``problems[problem]`` (its first column)."""
        return self.proxy.mapFromSource(self.model.index(problem, 0))

    def row_text(self, row: int) -> str:
        """Row ``row`` in words: "Error: <message>"."""
        return f"{self.proxy.index(row, 0).data()}: {self.proxy.index(row, 3).data()}"

    def shown_rows(self) -> List[Tuple[str, str, str, str]]:
        """The table as shown: (severity, ID, object, message) per row."""
        return [tuple(str(self.proxy.index(row, column).data()) for column in range(len(PROBLEM_COLUMNS)))
                for row in range(self.proxy.rowCount())]

    def set_problems(self, problems: List[Tuple[str, ...]], spacecraft: Sequence[str] = (),
                     stations: Sequence[str] = ()) -> None:
        """``problems``: ``(severity, text)`` or ``(severity, text, shown
        text)``, severity "error" or "warning". ``text`` is the message as
        raised, which says where it is fixed; the table shows the shown text.
        ``spacecraft`` and ``stations`` name the objects a message can be about."""
        self.problems = [(problem[0], problem[1]) for problem in problems]
        rows = [problem_row(problem[0], problem[1], problem[2] if len(problem) > 2 else problem[1],
                            spacecraft, stations) for problem in problems]
        self.model.set_rows(rows)
        if rows:
            self.table.resizeColumnToContents(0)
            for column in (1, 2):
                self.table.setColumnWidth(column, min(self.table.sizeHintForColumn(column) + SPACE["lg"],
                                                      SPACE["xxl"] * 8))
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        errors = sum(1 for problem in rows if problem.severity == "error")
        self.count_changed.emit(len(rows))
        self.counts_changed.emit(errors, len(rows) - errors)


_MODEL_MARK = "3D model"  # in every 3D model problem (engine.scenario_checks)


def model_problem_spacecraft(text: str, names: List[str]) -> Optional[str]:
    """The spacecraft whose 3D model problem ``text`` is about, or None when
    it is not about a 3D model (see :mod:`problem_location`)."""
    location = locate(text, names)
    if location is not None and location.area == SPACECRAFT and location.field == "model":
        return location.name
    return None



# -- Log ----------------------------------------------------------------------

LOG_LEVELS = (("Info and above", logging.INFO), ("Warnings and errors", logging.WARNING),
              ("Errors only", logging.ERROR), ("Everything", logging.DEBUG))
MAX_LOG_RECORDS = 5000  # [-] records kept for the view (the log file keeps everything)


class _LogBridge(QObject):
    """Carries records from any thread to the GUI thread (a queued signal)."""

    record = Signal(object)


class _ViewHandler(logging.Handler):
    def __init__(self, bridge: _LogBridge) -> None:
        super().__init__(level=logging.INFO)
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info and record.exc_info[0] is not None:
                message += "\n" + logging.Formatter().formatException(record.exc_info)
            self._bridge.record.emit((record.created, record.levelno, record.name, message))
        except RuntimeError:  # the view is gone
            pass
        except Exception:  # noqa: BLE001 -- logging must never raise into the caller
            self.handleError(record)


class LogViewWidget(QWidget):
    """The session's log, filterable by level and text. Records reach it
    through :func:`install_log_view`; the log file keeps everything."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.level_combo = ComboBox()  # ignores the mouse wheel unless focused, like every combo here
        for label, level in LOG_LEVELS:
            self.level_combo.addItem(label, level)
        self.level_combo.setToolTip("Which records to show")
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter (text in the message or the source)")
        self.filter_edit.setClearButtonEnabled(True)
        self.open_file_button = QPushButton("Open log file")
        self.open_file_button.setToolTip("The full log, with debug records and every traceback")
        self.open_file_button.clicked.connect(self.open_log_file)
        row.addWidget(QLabel("Show:"))
        row.addWidget(self.level_combo)
        row.addWidget(self.filter_edit, 1)
        row.addWidget(self.open_file_button)
        layout.addLayout(row)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setObjectName("logText")
        self.text.setFont(mono_font())
        self.text.setPlaceholderText("Nothing logged yet in this session.")
        layout.addWidget(self.text, 1)
        self.records: Deque[Tuple[float, int, str, str]] = deque(maxlen=MAX_LOG_RECORDS)
        self.level_combo.currentIndexChanged.connect(self._render)
        self.filter_edit.textChanged.connect(self._render)
        self.bridge = _LogBridge(self)
        self.bridge.record.connect(self.add_record)
        self._update_file_button()

    def _matches(self, record: Tuple[float, int, str, str]) -> bool:
        _created, level, name, message = record
        if level < self.level_combo.currentData():
            return False
        needle = self.filter_edit.text().strip().lower()
        return not needle or needle in message.lower() or needle in name.lower()

    @staticmethod
    def _line(record: Tuple[float, int, str, str]) -> str:
        created, level, name, message = record
        return f"{time.strftime('%H:%M:%S', time.localtime(created))}  {logging.getLevelName(level):<7}  " \
               f"{name}: {message}"

    def add_record(self, record: Tuple[float, int, str, str]) -> None:
        self.records.append(record)
        if self._matches(record):
            self.text.appendPlainText(self._line(record))

    def _render(self) -> None:
        self.text.setPlainText("\n".join(self._line(r) for r in self.records if self._matches(r)))
        self.text.moveCursor(self.text.textCursor().MoveOperation.End)

    def show_errors(self) -> None:
        """Filter to warnings and errors and scroll to the last one."""
        self.level_combo.setCurrentIndex(self.level_combo.findData(logging.WARNING))
        self.filter_edit.clear()
        self._render()

    def _update_file_button(self) -> None:
        from .. import logging_setup

        path = logging_setup.get_log_file_path()
        self.open_file_button.setEnabled(path is not None)
        self.open_file_button.setToolTip(str(path) if path else "Not logging to a file in this session")

    def open_log_file(self) -> None:
        from .. import logging_setup

        path = logging_setup.get_log_file_path()
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def install_log_view(view: LogViewWidget) -> logging.Handler:
    """Send the root logger's records (INFO and above) to ``view`` until it
    is destroyed."""
    handler = _ViewHandler(view.bridge)
    root = logging.getLogger()
    root.addHandler(handler)
    view.destroyed.connect(lambda *_args: root.removeHandler(handler))
    return handler
