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

"""A JSON code editor for the JSON page (``gui/json_view.py``, decisions
JE-01 to JE-03 of ``docs/developer/json-editor.md``).

:class:`JsonEditor` is a ``QPlainTextEdit`` with:

- syntax highlighting (:class:`JsonHighlighter`): keys, strings, numbers,
  ``true``/``false``/``null`` and punctuation in the theme's colours
  (the ``code.*`` tokens), redrawn when the theme changes;
- line numbers in a gutter, with a dot on each line that has a problem
  (red for an error, amber for a warning);
- the current line's background and the bracket matching the one at the
  cursor;
- problems marked where they are (:meth:`JsonEditor.set_diagnostics`): a
  wavy underline in the problem's colour, its message in a tooltip and,
  for the keyboard, in :attr:`JsonEditor.problem_at_cursor` (the JSON
  page shows it under the text); F8 and Shift+F8 go to the next and the
  previous problem;
- Enter keeps the line's indentation, two spaces more after ``{`` or ``[``;
- completion (:attr:`JsonEditor.completion_source`): Ctrl+Space, or
  typing inside a key or a string value, offers what fits there in a
  list; Enter or Tab inserts the one chosen, Escape closes the list;
- help (:attr:`JsonEditor.help_source`): pointing at a key shows its
  description, as does Ctrl+Shift+Space at the cursor.

A problem's place is a ``QTextCursor`` selection, so it follows the text
as it is edited until the problems are given again.
"""

from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QPainter, QStandardItem, QStandardItemModel, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor, QTextFormat)
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QToolTip, QWidget

from . import theme
from .json_positions import tokens
from .theme import TOKENS

ERROR, WARNING = "error", "warning"
_SEVERITY_TOKEN = {ERROR: "status.critical", WARNING: "status.caution"}
_INDENT = "  "  # the indentation the scenario file is written with (json.dumps(indent=2))


@dataclass
class Diagnostic:
    """A problem in the text: its ``severity`` (:data:`ERROR` or
    :data:`WARNING`), its ``message`` and the characters it is about (a
    selection that moves with the text)."""

    severity: str
    message: str
    cursor: QTextCursor

    def covers(self, position: int) -> bool:
        return self.cursor.selectionStart() <= position <= self.cursor.selectionEnd()


class JsonHighlighter(QSyntaxHighlighter):
    """Colours each line's JSON tokens (a JSON string cannot span lines,
    so each line is read on its own)."""

    def __init__(self, document) -> None:
        super().__init__(document)
        self.formats: dict[str, QTextCharFormat] = {}
        self.update_colours()

    def update_colours(self) -> None:
        self.formats = {}
        for kind in ("key", "string", "number", "literal", "punctuation"):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(TOKENS[f"code.{kind}"]))
            self.formats[kind] = fmt
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 -- Qt's name
        for token in tokens(text):
            self.setFormat(token.start, token.end - token.start, self.formats[token.kind])


class _Gutter(QWidget):
    """The line numbers, drawn by :meth:`JsonEditor.paint_gutter`."""

    def __init__(self, editor: "JsonEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 -- Qt's name
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        self.editor.paint_gutter(event)


class JsonEditor(QPlainTextEdit):
    """The JSON page's text (module docstring). ``cursor_problem_changed``
    carries :attr:`problem_at_cursor` when it changes."""

    cursor_problem_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFont(theme.mono_font("body"))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.highlighter = JsonHighlighter(self.document())
        self.gutter = _Gutter(self)
        self.diagnostics: list[Diagnostic] = []
        self.error_line: int | None = None  # a line (from 1) the text stops being JSON at
        self.problem_at_cursor = ""
        # (text, position) -> (start, end, [json_assist.Completion]); (text, position) -> description
        self.completion_source = None
        self.help_source = None
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._model = QStandardItemModel(self.completer)
        self.completer.setModel(self._model)
        self.completer.popup().setAccessibleName("Completions")
        self.completer.activated[str].connect(self.insert_completion)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._on_cursor_moved)
        self._update_gutter_width()
        self._refresh_selections()
        theme.on_change(self._on_theme)

    # -- the gutter -------------------------------------------------------------
    def gutter_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return self.fontMetrics().horizontalAdvance("9") * (digits + 2) + 6

    def _update_gutter_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().resizeEvent(event)
        area = self.contentsRect()
        self.gutter.setGeometry(QRect(area.left(), area.top(), self.gutter_width(), area.height()))

    def _line_severity(self) -> dict[int, str]:
        """The worst severity of each line (block number) with a problem."""
        lines: dict[int, str] = {}
        for diagnostic in self.diagnostics:
            line = self.document().findBlock(diagnostic.cursor.selectionStart()).blockNumber()
            if lines.get(line) != ERROR:
                lines[line] = diagnostic.severity
        if self.error_line is not None:
            lines[self.error_line - 1] = ERROR
        return lines

    def paint_gutter(self, event) -> None:
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(TOKENS["bg.canvas"]))
        severities = self._line_severity()
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        height = self.fontMetrics().height()
        current = self.textCursor().blockNumber()
        dot = max(4, height // 3)
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(TOKENS["text.primary" if number == current else "text.muted"]))
                painter.drawText(0, top, self.gutter.width() - dot - 6, height, Qt.AlignmentFlag.AlignRight,
                                 str(number + 1))
                if number in severities:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(TOKENS[_SEVERITY_TOKEN[severities[number]]]))
                    painter.drawEllipse(self.gutter.width() - dot - 3, top + (height - dot) // 2, dot, dot)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    # -- problems ---------------------------------------------------------------
    def set_diagnostics(self, problems) -> None:
        """Mark ``problems``: ``(severity, message, start, end)`` with
        character offsets into the text as it is now."""
        self.diagnostics = []
        length = self.document().characterCount() - 1
        for severity, message, start, end in problems:
            cursor = QTextCursor(self.document())
            cursor.setPosition(max(0, min(start, length)))
            cursor.setPosition(max(0, min(end, length)), QTextCursor.MoveMode.KeepAnchor)
            self.diagnostics.append(Diagnostic(severity, message, cursor))
        self.diagnostics.sort(key=lambda d: d.cursor.selectionStart())
        self._refresh_selections()
        self._on_cursor_moved()
        self.gutter.update()

    def set_error_line(self, line: int | None) -> None:
        """The line (from 1) the text stops being JSON at, shaded; None for none."""
        self.error_line = line
        self._refresh_selections()
        self.gutter.update()

    def messages_at(self, position: int) -> list[str]:
        """The messages of the problems at character ``position``."""
        return [d.message for d in self.diagnostics if d.covers(position)]

    def go_to_problem(self, forward: bool = True) -> bool:
        """Move the cursor to the next (or previous) problem, round the
        end of the text; False when there is none."""
        if not self.diagnostics:
            return False
        here = self.textCursor().position()
        starts = [d.cursor.selectionStart() for d in self.diagnostics]
        if forward:
            target = next((s for s in starts if s > here), starts[0])
        else:
            target = next((s for s in reversed(starts) if s < here), starts[-1])
        cursor = self.textCursor()
        cursor.setPosition(target)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        return True

    # -- selections: current line, matching bracket, problems, the JSON error --------
    def _refresh_selections(self) -> None:
        selections = []
        if self.error_line is not None:
            block = self.document().findBlockByNumber(self.error_line - 1)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.format.setBackground(QColor(TOKENS["status.critical.soft"]))
                selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                selection.cursor = QTextCursor(block)
                selections.append(selection)
        elif not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(TOKENS["code.current_line"]))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = QTextCursor(self.textCursor().block())
            selections.append(selection)
        selections += self._bracket_selections()
        for diagnostic in self.diagnostics:
            selection = QTextEdit.ExtraSelection()
            selection.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
            selection.format.setUnderlineColor(QColor(TOKENS[_SEVERITY_TOKEN[diagnostic.severity]]))
            cursor = QTextCursor(diagnostic.cursor)
            if cursor.selectionStart() == cursor.selectionEnd():  # an empty place: mark its character
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            selection.cursor = cursor
            selections.append(selection)
        self.setExtraSelections(selections)

    def _bracket_selections(self) -> list:
        from .json_positions import matching_bracket

        text = self.toPlainText()
        position = self.textCursor().position()
        for place in (position, position - 1):  # the bracket after the cursor, else the one before it
            if 0 <= place < len(text) and text[place] in "{}[]":
                other = matching_bracket(text, place)
                if other is None:
                    return []
                found = []
                for offset in (place, other):
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setBackground(QColor(TOKENS["code.bracket"]))
                    selection.format.setFontWeight(QFont.Weight.Bold)
                    cursor = QTextCursor(self.document())
                    cursor.setPosition(offset)
                    cursor.setPosition(offset + 1, QTextCursor.MoveMode.KeepAnchor)
                    selection.cursor = cursor
                    found.append(selection)
                return found
        return []

    def _on_cursor_moved(self) -> None:
        self._refresh_selections()
        self.gutter.update()
        text = " ".join(self.messages_at(self.textCursor().position()))
        if text != self.problem_at_cursor:
            self.problem_at_cursor = text
            self.cursor_problem_changed.emit(text)

    def _on_theme(self, _mode: str) -> None:
        self.highlighter.update_colours()
        self._refresh_selections()
        self.gutter.update()

    # -- completion and help ---------------------------------------------------------
    def offered(self) -> list:
        """What the completion list offers now (``json_assist.Completion``)."""
        if self.completion_source is None:
            return []
        return self.completion_source(self.toPlainText(), self.textCursor().position())[2]

    def show_completions(self, typed: bool = False) -> bool:
        """Offer what fits at the cursor; ``typed``: only while a key or a
        string value is being typed (not right after a closed string).
        Returns whether the list shows."""
        popup = self.completer.popup()
        if self.completion_source is None:
            return False
        position = self.textCursor().position()
        start, _end, items = self.completion_source(self.toPlainText(), position)
        if not items or (typed and start >= position):
            popup.hide()
            return False
        self._model.clear()
        for item in items:
            row = QStandardItem(item.label)
            row.setToolTip(item.detail)
            row.setData(item.detail, Qt.ItemDataRole.AccessibleDescriptionRole)
            self._model.appendRow(row)
        rect = self.cursorRect()
        rect.setWidth(max(260, popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 16))
        self.completer.complete(rect)
        popup.setCurrentIndex(self._model.index(0, 0))
        return True

    def insert_completion(self, label: str) -> None:
        """Put the completion ``label`` (offered at the cursor) in place of
        the word typed; a new key's value is then selected, to type over."""
        if self.completion_source is None:
            return
        start, end, items = self.completion_source(self.toPlainText(), self.textCursor().position())
        item = next((i for i in items if i.label == label), None)
        if item is None:
            return
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(item.insert)
        cursor.endEditBlock()
        if item.select is not None:
            cursor.setPosition(start + item.select[0])
            cursor.setPosition(start + item.select[1], QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.completer.popup().hide()

    def help_text(self, position: int) -> str:
        return self.help_source(self.toPlainText(), position) if self.help_source is not None else ""

    # -- events -------------------------------------------------------------------
    def viewportEvent(self, event) -> bool:  # noqa: N802 -- Qt's name
        if event.type() == QEvent.Type.ToolTip:
            position = self.cursorForPosition(event.pos()).position()
            messages = self.messages_at(position) or [text for text in [self.help_text(position)] if text]
            if messages:
                QToolTip.showText(event.globalPos(), "\n".join(messages), self.viewport())
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().viewportEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        popup = self.completer.popup()
        if popup.isVisible() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape,
                                                 Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            event.ignore()  # the completer's list takes them
            return
        control = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if control and event.key() == Qt.Key.Key_Space:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                position = self.textCursor().position()
                text = "\n".join(self.messages_at(position)) or self.help_text(position)
                if text:
                    QToolTip.showText(self.mapToGlobal(self.cursorRect().bottomLeft()), text, self)
            else:
                self.show_completions()
            return
        if event.key() == Qt.Key.Key_F8:
            self.go_to_problem(not event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers():
            cursor = self.textCursor()
            line = cursor.block().text()
            before = line[:cursor.positionInBlock()]
            indent = line[:len(line) - len(line.lstrip(" "))]
            if before.rstrip().endswith(("{", "[")):
                indent += _INDENT
            cursor.insertText("\n" + indent)
            self.setTextCursor(cursor)
            return
        super().keyPressEvent(event)
        typed = event.text()
        if typed and not control and (typed == '"' or typed.isalnum() or typed == "_"):
            self.show_completions(typed=True)
        elif popup.isVisible() and event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Left,
                                                   Qt.Key.Key_Right):
            self.show_completions(typed=True)
        elif popup.isVisible() and typed:
            popup.hide()
