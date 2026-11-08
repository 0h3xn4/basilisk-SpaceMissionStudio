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

"""The JSON page's code editor (``gui/code_editor.py``, decisions JE-01 to
JE-03): syntax colours from the theme, line numbers, the matching
bracket, problems marked at their place with their message on hover and
under the text, F8 between them, Enter keeping the indentation; and on
the JSON page of a real scenario, the scenario's own problem marked at
its value."""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_TEXT = '{\n  "name": "sat",\n  "mass": 12.5,\n  "on": true,\n  "list": [1, 2]\n}\n'


@pytest.fixture
def editor(qtbot):
    from spacemissionstudio.gui.code_editor import JsonEditor

    widget = JsonEditor()
    qtbot.addWidget(widget)
    widget.setPlainText(_TEXT)
    widget.resize(500, 300)
    widget.show()
    return widget


def _colour_at(editor, offset: int) -> str:
    block = editor.document().findBlock(offset)
    for fmt_range in block.layout().formats():
        if fmt_range.start <= offset - block.position() < fmt_range.start + fmt_range.length:
            return fmt_range.format.foreground().color().name().upper()
    return ""


def test_the_tokens_take_the_theme_s_code_colours(editor, restored_theme):
    """A key, a string, a number, a literal and a brace each in its code.*
    colour; a theme change recolours them."""
    from spacemissionstudio.gui import theme
    from spacemissionstudio.gui.theme import TOKENS

    def colours():
        return {kind: _colour_at(editor, _TEXT.index(text)) for kind, text in
                (("key", '"name"'), ("string", '"sat"'), ("number", "12.5"), ("literal", "true"), ("punctuation", "{"))}

    kinds = ("key", "string", "number", "literal", "punctuation")
    assert colours() == {kind: TOKENS[f"code.{kind}"] for kind in kinds}
    theme.apply_theme(restored_theme, "dark")
    assert colours() == {kind: TOKENS[f"code.{kind}"] for kind in kinds}
    assert TOKENS["code.number"] == theme.tokens.tokens("dark")["code.number"]


def test_the_gutter_holds_the_line_numbers(editor):
    """The text starts right of the gutter, which widens for more digits."""
    narrow = editor.gutter_width()
    assert editor.viewportMargins().left() == narrow > 0
    editor.setPlainText("\n" * 1200)
    assert editor.gutter_width() > narrow and editor.viewportMargins().left() == editor.gutter_width()


def test_the_bracket_at_the_cursor_and_its_match_are_marked(editor):
    from PySide6.QtGui import QTextCursor

    cursor = editor.textCursor()
    cursor.setPosition(_TEXT.index("["))
    editor.setTextCursor(cursor)
    marked = sorted(s.cursor.selectionStart() for s in editor.extraSelections() if s.cursor.hasSelection())
    assert marked == [_TEXT.index("["), _TEXT.index("]")]
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    cursor.setPosition(_TEXT.index('"sat"') + 2)
    editor.setTextCursor(cursor)
    assert not [s for s in editor.extraSelections() if s.cursor.hasSelection()]


def test_problems_are_marked_with_their_message(editor, qtbot):
    """Each problem is underlined in its colour, its line has a dot in the
    gutter, its message is given at the cursor and on hover, and F8 /
    Shift+F8 go from one to the next."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QTextCharFormat

    from spacemissionstudio.gui.theme import TOKENS

    mass = _TEXT.index("12.5")
    name = _TEXT.index('"sat"')
    editor.set_diagnostics([("warning", "mass looks low", mass, mass + 4), ("error", "name taken", name, name + 5)])
    underlined = {s.cursor.selectedText(): s.format.underlineColor().name().upper() for s in editor.extraSelections()
                  if s.format.underlineStyle() == QTextCharFormat.UnderlineStyle.WaveUnderline}
    assert underlined == {"12.5": QColor(TOKENS["status.caution"]).name().upper(),
                          '"sat"': QColor(TOKENS["status.critical"]).name().upper()}
    assert editor._line_severity() == {1: "error", 2: "warning"}
    seen = []
    editor.cursor_problem_changed.connect(seen.append)
    qtbot.keyClick(editor, Qt.Key.Key_F8)
    assert editor.textCursor().position() == name and editor.problem_at_cursor == "name taken"
    qtbot.keyClick(editor, Qt.Key.Key_F8)
    assert editor.textCursor().position() == mass and editor.problem_at_cursor == "mass looks low"
    qtbot.keyClick(editor, Qt.Key.Key_F8)  # round the end
    assert editor.textCursor().position() == name
    qtbot.keyClick(editor, Qt.Key.Key_F8, Qt.KeyboardModifier.ShiftModifier)
    assert editor.textCursor().position() == mass
    assert seen[:2] == ["name taken", "mass looks low"]
    assert editor.messages_at(mass + 2) == ["mass looks low"] and editor.messages_at(0) == []


def test_a_mark_follows_the_text_as_it_is_typed(editor):
    """A problem's place is a selection: typing before it moves it."""
    mass = _TEXT.index("12.5")
    editor.set_diagnostics([("error", "bad", mass, mass + 4)])
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.insertText("   ")
    assert editor.diagnostics[0].cursor.selectedText() == "12.5"


def test_enter_keeps_the_indentation(editor, qtbot):
    """After `{` or `[`, two spaces more; elsewhere, the line's own."""
    from PySide6.QtCore import Qt

    cursor = editor.textCursor()
    cursor.setPosition(_TEXT.index('"sat",') + len('"sat",'))
    editor.setTextCursor(cursor)
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    assert editor.textCursor().block().text() == "  "
    editor.setPlainText('{\n  "a": [')
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    assert editor.textCursor().block().text() == "    "


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


def test_the_scenario_s_problem_is_marked_at_its_value(qtbot, monkeypatch):
    """Template 22's JSON page: a dry mass of -1 kg typed there is applied,
    the scenario's validation problem is marked on the value -1.0, its
    message shows under the text when the cursor is on it, and the mark
    goes once the value is fixed."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    editor = window.scenario_editor
    editor.show_json()
    view = editor.json_view
    data = json.loads(view.edit.toPlainText())
    data["spacecraft"][0]["dry_mass_kg"] = -1.0  # [kg] not valid
    view.edit.setPlainText(json.dumps(data, indent=2))
    view.flush()
    editor.revalidate()
    [(severity, message, marked)] = [m for m in view.problem_marks() if "dry_mass_kg" in m[1]]
    assert severity == "error" and marked == "-1.0"
    cursor = view.edit.textCursor()
    cursor.setPosition(view.edit.diagnostics[[d.message for d in view.edit.diagnostics].index(message)]
                       .cursor.selectionStart() + 1)
    view.edit.setTextCursor(cursor)
    assert view.cursor_problem.isVisibleTo(view) and view.cursor_problem.text() == f"At the cursor: {message}"
    data["spacecraft"][0]["dry_mass_kg"] = 150.0  # [kg]
    view.edit.setPlainText(json.dumps(data, indent=2))
    view.flush()
    editor.revalidate()
    assert not [m for m in view.problem_marks() if "dry_mass_kg" in m[1]]
    assert not view.cursor_problem.isVisibleTo(view)
