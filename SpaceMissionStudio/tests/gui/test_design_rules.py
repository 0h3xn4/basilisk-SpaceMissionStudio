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
"""docs/DESIGN.md against the code: its colour token table is
theme.py's, its shortcut table the menus', and no GUI module but the
theme writes a colour of its own (docs/ux-standard.md, "no new hard-coded
colours")."""

import io
import re
import tokenize
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESIGN = _ROOT / "docs" / "DESIGN.md"
_GUI = _ROOT / "spacemissionstudio" / "gui"
_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|\brgba?\(")
_NAMED = re.compile(r"\bQt\.(?:GlobalColor\.)?(?!transparent\b)(?:red|green|blue|black|white|gray|darkGray|lightGray|"
                    r"yellow|cyan|magenta|darkRed|darkGreen|darkBlue)\b")

# The colours a GUI module may write itself, with why: data or an image,
# never the UI's own chrome.
# A string's text: a STRING token, or from Python 3.12 an f-string's
# literal parts.
_TEXT_TOKENS = {tokenize.STRING} | ({tokenize.FSTRING_MIDDLE} if hasattr(tokenize, "FSTRING_MIDDLE") else set())
_ALLOWED = {
    "icons.py": {"#0F62FE", "#002D9C", "#CFB87C", "#A88F53"},  # the app icon's own colours, the same in both themes
    "model_editor_dialog.py": {"#000000", "#FFFFFF", "rgb("},  # a user-picked part colour and the text readable on it
    "model_view_widget.py": {"#d62728", "#2ca02c", "#1f77b4", "rgb("},  # body axes x/y/z (identity); part colours (data)
}


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end >= 0 else len(text)]


@pytest.mark.requires_gui
def test_the_token_table_matches_the_theme():
    """Each LIGHT/DARK key is one row of DESIGN.md's table, with both
    values; no row names a key the theme does not have."""
    from spacemissionstudio.gui.theme import DARK, LIGHT

    rows = re.findall(r"^\| `(\w+)` \| `(#[0-9A-F]{6})` \| `(#[0-9A-F]{6})` \|", _DESIGN.read_text(), re.MULTILINE)
    assert {key: (light, dark) for key, light, dark in rows} == {key: (LIGHT[key], DARK[key]) for key in LIGHT}
    assert len(rows) == len(LIGHT)


@pytest.mark.requires_gui
def test_the_shortcut_table_matches_the_menus(qtbot, monkeypatch):
    """Every menu command with a shortcut, submenus included, is a row of
    DESIGN.md's shortcut table with its first shortcut; every row is such
    a command."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    found = {}

    def walk(menu, path):
        for action in menu.actions():
            name = path + [action.text().replace("&", "")]
            if action.menu() is not None:
                walk(action.menu(), name)
            elif not action.isSeparator() and action.shortcuts():
                found[" > ".join(name)] = action.shortcuts()[0].toString()

    for action in window.menuBar().actions():
        walk(action.menu(), [action.text().replace("&", "")])
    table = _section(_DESIGN.read_text(), "| Command | Keys |")
    rows = dict(re.findall(r"^\| ([^|]+?) \| ([^|]+?) \|$", table, re.MULTILINE)[1:])  # past the header row
    rows.pop("---", None)
    assert rows == found


def test_no_hard_coded_colour_outside_the_theme():
    """No string in gui/ but theme.py holds a colour (#rrggbb, #rgb,
    rgb()/rgba()) and no code names a Qt colour, beyond the listed
    exceptions; widgets take PALETTE's."""
    found = {}
    for path in sorted(_GUI.glob("*.py")):
        if path.name == "theme.py":
            continue
        source = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            hits = set(_COLOUR.findall(token.string)) if token.type in _TEXT_TOKENS else set()
            extra = hits - _ALLOWED.get(path.name, set())
            if extra:
                found.setdefault(path.name, set()).update(extra)
        for match in _NAMED.finditer(source):
            found.setdefault(path.name, set()).add(match.group(0))
    assert found == {}
