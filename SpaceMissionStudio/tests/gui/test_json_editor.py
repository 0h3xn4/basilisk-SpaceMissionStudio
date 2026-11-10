#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
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


def _page(qtbot, monkeypatch):
    """Template 22's JSON page."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    window.scenario_editor.show_json()
    return window


def _select(edit, start, end):
    from PySide6.QtGui import QTextCursor

    cursor = edit.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    edit.setTextCursor(cursor)


def test_typing_a_value_offers_its_choices_and_enter_inserts_one(qtbot, monkeypatch):
    """The orbit's type, typed over with a quote, offers the three orbit
    types; Down and Enter put "cartesian" there, and the edit applies."""
    from PySide6.QtCore import Qt

    window = _page(qtbot, monkeypatch)
    view = window.scenario_editor.json_view
    edit = view.edit
    text = edit.toPlainText()
    start = text.index('"type": "classical_elements"') + len('"type": ')
    _select(edit, start, start + len('"classical_elements"'))
    qtbot.keyClicks(edit, '"')
    popup = edit.completer.popup()
    assert popup.isVisible()
    assert [edit._model.item(i).text() for i in range(edit._model.rowCount())] == ["classical_elements", "cartesian",
                                                                                   "tle"]
    assert "One of: classical_elements, cartesian, tle" in edit._model.item(0).toolTip()
    qtbot.keyClick(popup, Qt.Key.Key_Down)
    qtbot.keyClick(popup, Qt.Key.Key_Return)
    assert not popup.isVisible()
    assert '"type": "cartesian",' in edit.toPlainText()
    qtbot.keyClick(edit, Qt.Key.Key_Escape)  # no list: nothing happens
    view.flush()
    assert json.loads(edit.toPlainText())["spacecraft"][0]["orbit"]["type"] == "cartesian"


def test_ctrl_space_offers_a_new_key_and_selects_its_default(qtbot, monkeypatch):
    """In a new sensor object, Ctrl+Space offers its fields; "mount" is
    inserted with an empty object, selected to type over; Escape closes
    the list without inserting."""
    from PySide6.QtCore import Qt

    window = _page(qtbot, monkeypatch)
    edit = window.scenario_editor.json_view.edit
    text = edit.toPlainText()
    start = text.index('"sensors": [') + len('"sensors": [')
    end = text.index("]", start)
    _select(edit, start, end)
    edit.insertPlainText('{"kind": "imu", "name": "gyro", ')
    qtbot.keyClick(edit, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    popup = edit.completer.popup()
    labels = [edit._model.item(i).text() for i in range(edit._model.rowCount())]
    assert popup.isVisible() and labels == ["params", "mount"]
    qtbot.keyClick(popup, Qt.Key.Key_Escape)
    assert not popup.isVisible() and edit.toPlainText().count('"mount"') == 0
    edit.show_completions()
    edit.insert_completion("mount")
    assert '"name": "gyro", "mount": {}' in edit.toPlainText() and edit.textCursor().selectedText() == "{}"


def test_a_key_is_described_on_hover_and_under_the_text(qtbot, monkeypatch):
    """The cursor on "dry_mass_kg": its type, default and the source's
    comment under the text, shortened, and in full from help_text."""
    window = _page(qtbot, monkeypatch)
    view = window.scenario_editor.json_view
    edit = view.edit
    position = edit.toPlainText().index('"dry_mass_kg"') + 3
    _select(edit, position, position)
    full = edit.help_text(position)
    assert full.startswith("dry_mass_kg: number, default 100.0") and "WITHOUT station-keeping propellant" in full
    line = view.cursor_problem.text()
    assert view.cursor_problem.isVisibleTo(view) and line.startswith("dry_mass_kg: number, default 100.0 [kg]")
    assert len(line) <= 240 and line.endswith("…")
    _select(edit, 0, 0)
    assert not view.cursor_problem.isVisibleTo(view)


def _page_of(qtbot, monkeypatch, template):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.open_path(_TEMPLATES / template)
    window.scenario_editor.show_json()
    return window


def test_f2_renames_a_spacecraft_everywhere_and_applies(qtbot, monkeypatch):
    """Template 05: F2 on the follower's chief asks for the new name
    (answered "leader"); both places change, the edit applies to the
    form, and Undo (Ctrl+Z in the text) puts the text back at once."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QInputDialog

    window = _page_of(qtbot, monkeypatch, "05_formation_flying_phasing.json")
    view = window.scenario_editor.json_view
    edit = view.edit
    before = edit.toPlainText()
    position = before.index('"chief_spacecraft": "') + len('"chief_spacecraft": "') + 1
    _select(edit, position, position)
    asked = []
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda parent, title, label, text="": (asked.append((label, text)), ("leader", True))[1]))
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key.Key_F2)
    [(label, proposed)] = asked
    assert proposed == "chief-1" and "spacecraft 'chief-1'" in label
    after = edit.toPlainText()
    assert after.count('"leader"') == 2 and '"chief-1"' not in after
    scenario = window.scenario_editor.to_scenario()
    assert "leader" in [sc.name for sc in scenario.spacecraft]
    edit.undo()
    assert edit.toPlainText() == before


def test_f12_goes_to_the_definition_and_ctrl_period_fixes(qtbot, monkeypatch):
    """F12 on the chief selects its own name; Ctrl+. on an orbit type that
    is not one offers the three, and the first is applied."""
    from PySide6.QtCore import Qt

    window = _page_of(qtbot, monkeypatch, "05_formation_flying_phasing.json")
    edit = window.scenario_editor.json_view.edit
    text = edit.toPlainText()
    position = text.index('"chief_spacecraft": "') + len('"chief_spacecraft": "') + 1
    _select(edit, position, position)
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key.Key_F12)
    assert edit.textCursor().selectedText() == '"chief-1"' and edit.textCursor().position() != position
    start = text.index('"type": "classical_elements"') + len('"type": ')
    _select(edit, start, start + len('"classical_elements"'))
    edit.insertPlainText('"clasical"')
    _select(edit, start + 2, start + 2)
    assert [f.label for f in edit.fixes()] == ["Use 'classical_elements'", "Use 'cartesian'", "Use 'tle'"]
    menu = edit.show_quick_fixes()
    assert menu is not None and [a.text() for a in menu.actions()][0] == "Use 'classical_elements'"
    menu.actions()[0].trigger()
    menu.close()
    assert '"type": "classical_elements"' in edit.toPlainText()


def test_a_misspelt_key_is_marked_where_it_is_and_the_text_formats(qtbot, monkeypatch):
    """A key the record does not have stops the edit (the banner says
    which); it is now also marked at its place. Shift+Alt+F lays out a
    text squeezed onto one line again."""
    from PySide6.QtCore import Qt

    window = _page_of(qtbot, monkeypatch, "22_starter_first_leo_satellite.json")
    view = window.scenario_editor.json_view
    edit = view.edit
    good = edit.toPlainText()
    edit.setPlainText(good.replace('"dry_mass_kg"', '"dry_mas_kg"', 1))
    view.flush()
    assert "dry_mas_kg" in view.error
    [mark] = [d for d in edit.diagnostics if "dry_mas_kg" in d.message]
    assert mark.cursor.selectedText() == '"dry_mas_kg"' and "did you mean 'dry_mass_kg'" in mark.message
    edit.setPlainText(json.dumps(json.loads(good)))
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key.Key_F, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier)
    assert edit.toPlainText() == good
    edit.setPlainText('{"name": ')
    assert not edit.format_document() and edit.toPlainText() == '{"name": '
