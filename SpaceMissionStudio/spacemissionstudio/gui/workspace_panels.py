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
  warnings (a right dock); double-clicking one opens the Scenario Editor.
* :class:`LogViewWidget` -- the session's log, filterable by level and text
  (the *Log* tab). :func:`install_log_view` attaches it to the root logger.
* :class:`CompareWidget` -- the session's runs and the inputs that differ
  between the shown run and the chosen one (the *Compare* tab).
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from typing import Deque, List, Optional, Tuple

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from .theme import MONO_FONT_FAMILY, PALETTE
from .widgets import ComboBox


def _empty_state(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("emptyState")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(f"color: {PALETTE['text_muted']}; padding: 24px;")
    return label


def _plain(text: str) -> str:
    """A tooltip's text without its HTML."""
    return re.sub(r"<[^>]+>", "", text or "").replace("&nbsp;", " ").strip()


# -- Inspector ----------------------------------------------------------------

def field_label(widget: QWidget) -> str:
    """The label a form gives ``widget`` (or the row holding it), else its
    accessible name, else a check box's own text, else ""."""
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

class ProblemsWidget(QWidget):
    """The scenario's validation error and plausibility warnings."""

    activated = Signal(str)  # a problem was double-clicked (its text): show where to fix it
    count_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.empty_label = _empty_state("No problems: the scenario is valid.")
        self.list = QListWidget()
        self.list.setWordWrap(True)
        # Wrapped lines, never a sideways scroll bar: items re-wrap when the panel resizes.
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.list, 1)
        self.problems: List[Tuple[str, str]] = []
        self.set_problems([])

    def _on_item_activated(self, item) -> None:
        self.activated.emit(self.problems[self.list.row(item)][1])

    def set_problems(self, problems: List[Tuple[str, str]]) -> None:
        """``problems``: ``(severity, text)`` pairs, severity "error" or "warning"."""
        self.problems = list(problems)
        self.list.clear()
        colours = {"error": PALETTE["danger_text"], "warning": PALETTE["warning"]}
        for severity, text in self.problems:
            item = QListWidgetItem(f"{'Error' if severity == 'error' else 'Warning'}: {text}")
            item.setForeground(_brush(colours.get(severity, PALETTE["text"])))
            item.setToolTip("Double-click to open the 3D model editor" if _MODEL_MARK in text
                            else "Double-click to open the Scenario Editor")
            self.list.addItem(item)
        self.empty_label.setVisible(not self.problems)
        self.list.setVisible(bool(self.problems))
        self.count_changed.emit(len(self.problems))


# engine.scenario_checks' 3D model warnings read "<spacecraft>: 3D model: ..."
# or "<spacecraft>: ... differ from the 3D model ...".
_MODEL_MARK = "3D model"


def model_problem_spacecraft(text: str, names: List[str]) -> Optional[str]:
    """The spacecraft whose 3D model problem ``text`` is about, or None when
    it is not about a 3D model. The longest matching name wins, so "sat-10"
    is not taken for "sat-1"."""
    if _MODEL_MARK not in text:
        return None
    for name in sorted(names, key=len, reverse=True):
        if text.startswith(f"{name}: "):
            return name
    return None


def _brush(colour: str):
    from PySide6.QtGui import QBrush, QColor

    return QBrush(QColor(colour))


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
        self.text.setFont(QFont(MONO_FONT_FAMILY))
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


# -- Compare ------------------------------------------------------------------

class CompareWidget(QWidget):
    """The session's runs; choosing one compares it with the shown run: its
    inputs that differ, here, and its curves, dashed, in Results."""

    compare_chosen = Signal(object)  # a run number, or None for no comparison

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.empty_label = _empty_state("Run the scenario twice (or two versions of it) to compare the runs here.")
        layout.addWidget(self.empty_label)
        self.content = QWidget()
        content = QVBoxLayout(self.content)
        content.setContentsMargins(0, 0, 0, 0)
        self.shown_label = QLabel()
        self.shown_label.setWordWrap(True)
        content.addWidget(self.shown_label)
        content.addWidget(QLabel("Compare with:"))
        self.run_list = QListWidget()
        self.run_list.setMaximumHeight(160)  # [px]
        self.run_list.currentItemChanged.connect(self._on_choice)
        content.addWidget(self.run_list)
        self.summary_label = QLabel()
        content.addWidget(self.summary_label)
        self.table = QTableWidget(0, 3)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        content.addWidget(self.table, 1)
        layout.addWidget(self.content, 1)
        self._runs: list = []
        self._current = None
        self._updating = False
        self.set_runs([], None)

    def set_runs(self, runs: list, current, chosen_number=None) -> None:
        """``runs``: ``gui.run_history.RunRecord`` objects, oldest first;
        ``current``: the one the run views show; ``chosen_number``: the run
        compared with it, if any."""
        self._runs, self._current = list(runs), current
        others = [r for r in self._runs if current is None or r.number != current.number]
        self._updating = True
        self.run_list.clear()
        none_item = QListWidgetItem("(no comparison)")
        none_item.setData(Qt.ItemDataRole.UserRole, None)
        self.run_list.addItem(none_item)
        selected = none_item
        for record in reversed(others):
            item = QListWidgetItem(record.label)
            item.setData(Qt.ItemDataRole.UserRole, record.number)
            self.run_list.addItem(item)
            if record.number == chosen_number:
                selected = item
        self.run_list.setCurrentItem(selected)
        self._updating = False
        has = current is not None and bool(others)
        self.empty_label.setVisible(not has)
        self.content.setVisible(has)
        self.shown_label.setText(f"Shown: {current.label}" if current is not None else "")
        self._fill_table(chosen_number)

    def chosen_number(self):
        item = self.run_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _on_choice(self, *_args) -> None:
        if self._updating:
            return
        number = self.chosen_number()
        self._fill_table(number)
        self.compare_chosen.emit(number)

    def _fill_table(self, number) -> None:
        from ..engine import scenario_diff

        other = next((r for r in self._runs if r.number == number), None) if number is not None else None
        rows = scenario_diff.diff(self._current.scenario, other.scenario) if other and self._current else []
        self.table.setRowCount(len(rows))
        if other is None or self._current is None:
            self.table.setHorizontalHeaderLabels(["Input", "Shown run", "Compared run"])
            self.summary_label.setText("Choose a run to see the inputs that differ.")
            return
        self.table.setHorizontalHeaderLabels(["Input", f"Run {self._current.number} (shown)",
                                              f"Run {other.number}"])
        for row, (path, mine, theirs) in enumerate(rows):
            for column, value in enumerate((path, scenario_diff.short(mine), scenario_diff.short(theirs))):
                item = QTableWidgetItem(value)
                item.setToolTip(str((path, mine, theirs)[column]))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.summary_label.setText(f"{len(rows)} input(s) differ; Results draws Run {other.number} dashed."
                                   if rows else f"The inputs are the same; Results draws Run {other.number} dashed.")
