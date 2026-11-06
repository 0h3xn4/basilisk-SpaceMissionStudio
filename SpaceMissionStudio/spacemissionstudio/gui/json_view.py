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


"""The scenario as JSON, editable (docs/ux-audit.md U-16): the Scenario
editor's JSON mode (its Form · JSON toggle, UI overhaul M4b), showing the
text :meth:`Scenario.save` writes. Edits apply to
the other pages 500 ms after the last keystroke, through the same parsing
and migration as opening a file (``schema.scenario.parse_scenario_text``);
the scenario's problems then show in Problems and at the fields, as for any
edit. Text that is not JSON, or not a scenario, is not applied: the line is
marked, the banner says what is wrong, and the scenario counts as invalid
until it is fixed or discarded (Discard puts the scenario's own text
back). Back to Form applies a waiting edit first and is refused while
the text does not apply. An edit on another page shows here when JSON
mode is next shown, unless the text holds an edit not yet applied.

The text is a JSON code editor (``gui/code_editor.py``, decisions JE-01
to JE-03 of ``docs/developer/json-editor.md``): highlighted, with line
numbers, and with the scenario's problems (:meth:`ScenarioJsonView.set_problems`,
the Problems list's) marked at the key or value each is about
(``gui/json_positions.py``); the one at the cursor shows under the text.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..schema.scenario import Scenario, ScenarioJSONError, ScenarioValidationError, parse_scenario_text, scenario_text
from . import json_assist, json_positions
from .code_editor import ERROR, WARNING, JsonEditor
from .feedback import ProblemBanner
from .problem_location import locate
from .theme import set_role

SOURCE = "JSON view"  # how this page's problems start
_HELP_CHARS = 240  # the longest key description shown under the text (the tooltip has it all)


class ScenarioJsonView(QWidget):
    """``applied`` carries the scenario parsed from an edit; ``failed`` the
    problem with one that could not be applied ("" once it is fixed);
    ``discarded`` that the user dropped an edit that could not be applied."""

    applied = Signal(object)
    failed = Signal(str)
    discarded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        intro = QLabel("The scenario as it is saved. Edit it here and the form follows; an edit in the "
                       "form shows here.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.banner = ProblemBanner()
        self.discard_button = QPushButton("Discard")
        self.discard_button.setToolTip("Drop this edit: the text goes back to the scenario's.")
        self.discard_button.clicked.connect(self._on_discard)
        self.banner.layout().addWidget(self.discard_button)
        layout.addWidget(self.banner)
        self.edit = JsonEditor()
        self.edit.setObjectName("jsonEdit")
        self.edit.setAccessibleName("Scenario JSON")
        self.edit.setAccessibleDescription("Ctrl+Space offers what can be typed at the cursor, Ctrl+Shift+Space "
                                           "describes the key there; F8 and Shift+F8 go to the next and the "
                                           "previous problem.")
        self.edit.setTabChangesFocus(True)  # keyboard users leave the page with Tab
        layout.addWidget(self.edit, 1)
        self.cursor_problem = QLabel("")
        self.cursor_problem.setObjectName("jsonCursorProblem")
        self.cursor_problem.setWordWrap(True)
        self.cursor_problem.setVisible(False)
        layout.addWidget(self.cursor_problem)
        self.edit.cursor_problem_changed.connect(self._update_cursor_line)
        self.edit.cursorPositionChanged.connect(self._update_cursor_line)
        self.edit.completion_source = lambda text, position: json_assist.completions(text, position, self._data)
        self.edit.help_source = json_assist.help_at
        self._data = None  # the scenario's JSON as last read: the names completion offers
        self._problems: list = []  # (severity, message) of the scenario, as the Problems list gives them
        self._names: tuple = ((), ())  # the spacecraft's and ground stations' names, for locate
        self.error = ""
        self._dirty = False
        self._setting = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(500)  # [ms] after the last keystroke
        self._timer.timeout.connect(self._apply)
        self.edit.textChanged.connect(self._on_text_changed)

    @property
    def dirty(self) -> bool:
        """The text holds an edit not applied yet (waiting, or wrong)."""
        return self._dirty

    def show_scenario(self, scenario: Scenario) -> None:
        """Show ``scenario``'s text, unless the text holds an edit not yet
        applied. The cursor stays on its line."""
        if self._dirty:
            return
        text = scenario_text(scenario)
        if text == self.edit.toPlainText():
            return
        line = self.edit.textCursor().blockNumber()
        scroll = self.edit.verticalScrollBar().value()
        self._setting = True
        try:
            self.edit.setPlainText(text)
        finally:
            self._setting = False
        block = self.edit.document().findBlockByNumber(min(line, self.edit.document().blockCount() - 1))
        self.edit.setTextCursor(QTextCursor(block))
        self.edit.verticalScrollBar().setValue(scroll)
        self._mark_problems()

    def set_problems(self, problems, spacecraft_names=(), station_names=()) -> None:
        """The scenario's problems (``(severity, message)``, as the
        Problems list), marked where they are in the text when it is
        JSON. While the text holds an edit not yet applied, the marks
        already there follow it as it is typed."""
        self._problems = [(severity, message) for severity, message in problems if message]
        self._names = (tuple(spacecraft_names), tuple(station_names))
        self._mark_problems()

    def _mark_problems(self) -> None:
        if self._dirty:
            return
        text = self.edit.toPlainText()
        try:
            data = json.loads(text)
        except ValueError:
            return  # not JSON: its own error is marked instead
        self._data = data
        nodes = json_positions.index(text)
        marks = []
        for severity, message in self._problems:
            path = json_positions.json_path(locate(message, *self._names), data)
            span = json_positions.mark_span(nodes, path) if path is not None else None
            if span is not None:
                marks.append((WARNING if severity == "warning" else ERROR, message, *span))
        self.edit.set_diagnostics(marks)

    def problem_marks(self) -> list[tuple[str, str, str]]:
        """``(severity, message, marked text)`` of each problem marked."""
        return [(d.severity, d.message, d.cursor.selectedText()) for d in self.edit.diagnostics]

    def _update_cursor_line(self, _problem: str = "") -> None:
        """Under the text: the problem at the cursor, else the description
        of the key the cursor is on (the first line and the source's
        comment, shortened), else nothing."""
        here = self.edit.textCursor().position()
        problem = self.edit.problem_at_cursor
        if problem:
            severity = next((d.severity for d in self.edit.diagnostics if d.covers(here)), ERROR)
            text, tone = f"At the cursor: {problem}", "critical" if severity == ERROR else "caution"
        else:
            lines = self.edit.help_text(here).split("\n")
            text = " ".join(line for line in lines if line)
            if len(text) > _HELP_CHARS:
                text = text[:_HELP_CHARS - 1].rstrip() + "…"
            tone = "secondary"
        self.cursor_problem.setText(text)
        self.cursor_problem.setVisible(bool(text))
        set_role(self.cursor_problem, tone=tone)

    def reset(self) -> None:
        """Forget an edit not applied (another scenario was opened)."""
        self._timer.stop()
        self._dirty = False
        self._set_error("", None)

    def _on_discard(self) -> None:
        self.reset()
        self.discarded.emit()

    def flush(self) -> None:
        """Apply a waiting edit now."""
        if self._timer.isActive():
            self._timer.stop()
            self._apply()

    def _on_text_changed(self) -> None:
        if self._setting:
            return
        self._dirty = True
        self._timer.start()

    def _apply(self) -> None:
        try:
            scenario = parse_scenario_text(self.edit.toPlainText(), SOURCE)
        except ScenarioJSONError as exc:
            self._set_error(f"{SOURCE}: line {exc.line}, column {exc.column}: {exc.reason}", exc.line, exc.column,
                            exc.reason)
            return
        except ScenarioValidationError as exc:
            self._set_error(str(exc), None)
            return
        self._dirty = False
        self._set_error("", None)
        self.applied.emit(scenario)

    def _set_error(self, message: str, line: int | None, column: int = 1, reason: str = "") -> None:
        changed = message != self.error
        self.error = message
        if message:
            self.banner.show_problem(message + "\nNot applied: the form shows the scenario without this edit. Fix it, "
                                     "or Discard it to go back to the form.")
        else:
            self.banner.hide()
        self.edit.set_error_line(line)
        if line is not None:  # the place itself, underlined, with the reason
            block = self.edit.document().findBlockByNumber(line - 1)
            start = block.position() + max(0, min(column - 1, block.length() - 1))
            self.edit.set_diagnostics([(ERROR, reason or message, start, start)])
        elif message:
            self.edit.set_diagnostics([])
        else:
            self._mark_problems()
        if changed:
            self.failed.emit(message)
