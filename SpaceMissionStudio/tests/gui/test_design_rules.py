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
"""docs/DESIGN.md against the code: its colour token table is the theme
package's, its shortcut table the menus', and no GUI module outside
gui/theme/ writes a colour, a font family or a pixel size of its own
(docs/ui/UI_OVERHAUL.md, "Tokens": "No hex colour, font family or pixel
size appears anywhere else in GUI code; a test enforces this")."""

import io
import re
import tokenize
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESIGN = _ROOT / "docs" / "DESIGN.md"
_GUI = _ROOT / "spacemissionstudio" / "gui"
_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|\brgba?\(")
# A CSS size or font in a string, and a font family by name.
_SIZE = re.compile(r"\b\d+(?:\.\d+)?(?:px|pt)\b|font-size|font-weight|font-family")
_FAMILY = re.compile(r"\b(?:Inter|JetBrains|Plex|monospace|sans-serif|Helvetica|Arial|Segoe|Consolas|Courier)\b")
# Code that sets a font size or family, or a style sheet, itself.
_CALLS = re.compile(r"\.(?:setPointSize|setPointSizeF|setPixelSize|setFamily|setFamilies|setStyleSheet)\(|"
                    r"\bQFont\(\s*['\"]")
_NAMED = re.compile(r"\bQt\.(?:GlobalColor\.)?(?!transparent\b)(?:red|green|blue|black|white|gray|darkGray|lightGray|"
                    r"yellow|cyan|magenta|darkRed|darkGreen|darkBlue)\b")

# The colours a GUI module may write itself, with why: data or an image,
# never the UI's own chrome.
# A string's text: a STRING token, or from Python 3.12 an f-string's
# literal parts.
_TEXT_TOKENS = {tokenize.STRING} | ({tokenize.FSTRING_MIDDLE} if hasattr(tokenize, "FSTRING_MIDDLE") else set())
_ALLOWED = {
    "model_view_widget.py": {"rgb("},  # a 3D part's own colour (data, picked by the user)
}
# Lines that may set a style sheet themselves, with why.
_ALLOWED_CALLS = {
    "model_editor_dialog.py": {"swatch_style("},  # the swatch of a user-picked colour (theme.palettes.swatch_style)
}


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end >= 0 else len(text)]


@pytest.mark.requires_gui
def test_the_token_table_matches_the_theme():
    """Each token of the theme is one row of DESIGN.md's token table, with
    its light and dark values; no row names a token the theme does not
    have."""
    from spacemissionstudio.gui.theme import tokens

    light, dark = tokens.tokens("light"), tokens.tokens("dark")
    rows = re.findall(r"^\| `([a-z][a-z0-9_.]*)` \| `(#[0-9A-F]{6})` \| `(#[0-9A-F]{6})` \|", _DESIGN.read_text(),
                      re.MULTILINE)
    assert {key: (lt, dk) for key, lt, dk in rows} == {key: (light[key], dark[key]) for key in light}
    assert len(rows) == len(light)


@pytest.mark.requires_gui
def test_the_shortcut_table_matches_the_menus(qtbot, monkeypatch):
    """Every menu command with a shortcut, submenus included, is a row of
    DESIGN.md's shortcut table with its first shortcut; every row is such
    a command. A row naming a standard key has that key's first binding on
    the running platform (none: no shortcut), whatever its Keys column
    says (Redo is Ctrl+Y offscreen, Ctrl+Shift+Z on macOS)."""
    from PySide6.QtGui import QKeySequence
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
    table = _section(_DESIGN.read_text(), "| Command | Keys | Standard key |").split("\n\n")[0]  # this table only
    rows = re.findall(r"^\| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \|$", table, re.MULTILINE)[1:]  # past the header
    expected = {}
    for command, keys, standard in rows:
        if command == "---":
            continue
        if standard != "-":
            bindings = QKeySequence.keyBindings(getattr(QKeySequence.StandardKey, standard))
            keys = bindings[0].toString() if bindings else None
        if keys is not None:
            expected[command] = keys
    assert expected == found
    assert {command for command, _keys, standard in rows if standard == "-"} <= set(found)


def _docstring(previous_type) -> bool:
    """A string token that is a statement of its own: a docstring."""
    return previous_type in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)


def test_no_hard_coded_style_outside_the_theme():
    """No string in gui/ outside gui/theme/ holds a colour (#rrggbb, #rgb,
    rgb()/rgba()), a CSS size, weight or font family, or a font family by
    name; no code names a Qt colour or sets a font size, a font family or
    a style sheet itself; beyond the listed exceptions. Widgets take the
    theme's tokens, fonts and roles."""
    found = {}
    for path in sorted(_GUI.rglob("*.py")):
        if path.relative_to(_GUI).parts[0] == "theme":
            continue
        name = path.relative_to(_GUI).as_posix()
        source = path.read_text(encoding="utf-8")
        previous = None
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in (tokenize.COMMENT, tokenize.NL):
                continue
            if token.type in _TEXT_TOKENS and not (token.type == tokenize.STRING and _docstring(previous)):
                hits = {m for rx in (_COLOUR, _SIZE, _FAMILY) for m in rx.findall(token.string)}
                extra = hits - _ALLOWED.get(name, set())
                if extra:
                    found.setdefault(name, set()).update(extra)
            previous = token.type
        for match in _NAMED.finditer(source):
            found.setdefault(name, set()).add(match.group(0))
        for line in source.splitlines():
            code = line.split("#", 1)[0]
            if _CALLS.search(code) and not any(ok in code for ok in _ALLOWED_CALLS.get(name, ())):
                found.setdefault(name, set()).add(code.strip())
    assert found == {}
