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
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QColor, QFontDatabase, QTextCursor, QTextFormat
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..schema.scenario import Scenario, ScenarioJSONError, ScenarioValidationError, parse_scenario_text, scenario_text
from .feedback import ProblemBanner
from .theme import TOKENS

SOURCE = "JSON view"  # how this page's problems start


class ScenarioJsonView(QWidget):
    """``applied`` carries the scenario parsed from an edit; ``failed`` the
    problem with one that could not be applied ("" once it is fixed);
    ``discarded`` that the user dropped an edit that could not be applied."""

    applied = Signal(object)
    failed = Signal(str)
    discarded = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
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
        self.edit = QPlainTextEdit()
        self.edit.setObjectName("jsonEdit")
        self.edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.edit.setTabChangesFocus(True)  # keyboard users leave the page with Tab
        layout.addWidget(self.edit, 1)
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
            self._set_error(f"{SOURCE}: line {exc.line}, column {exc.column}: {exc.reason}", exc.line)
            return
        except ScenarioValidationError as exc:
            self._set_error(str(exc), None)
            return
        self._dirty = False
        self._set_error("", None)
        self.applied.emit(scenario)

    def _set_error(self, message: str, line: Optional[int]) -> None:
        changed = message != self.error
        self.error = message
        if message:
            self.banner.show_problem(message + "\nNot applied: the form shows the scenario without this edit. Fix it, "
                                     "or Discard it to go back to the form.")
        else:
            self.banner.hide()
        selections = []
        if line is not None:
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(TOKENS["status.critical.soft"]))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = QTextCursor(self.edit.document().findBlockByNumber(line - 1))
            selections.append(selection)
        self.edit.setExtraSelections(selections)
        if changed:
            self.failed.emit(message)
