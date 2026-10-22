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
"""Both themes and the live switch (docs/ui/UI_OVERHAUL.md, "Themes" and
"Accessibility"): WCAG 2.2 AA contrast over every pair of tokens the GUI
draws, the View > Theme setting, and a switch that restyles every open
view at once, plots included."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"



@pytest.mark.parametrize("mode", ["light", "dark"])
def test_every_pair_the_app_draws_meets_wcag_aa(mode):
    """Text on each of its backgrounds at 4.5:1, icons, indicators and the
    focus ring at 3:1 (WCAG 2.2, 1.4.3 and 1.4.11), in each theme."""
    from spacemissionstudio.gui.theme import tokens

    values = tokens.tokens(mode)
    low = [(fg, bg, round(tokens.contrast(values[fg], values[bg]), 2)) for fg, bg, need in tokens.CONTRAST_PAIRS
           if tokens.contrast(values[fg], values[bg]) < need]
    assert low == []
    assert len(tokens.CONTRAST_PAIRS) >= 70


def test_the_contrast_formula_is_wcags():
    """Black on white is 21:1, a colour on itself 1:1, and #767676 on white
    the familiar 4.54:1."""
    from spacemissionstudio.gui.theme.tokens import contrast

    assert round(contrast("#000000", "#FFFFFF"), 2) == 21.0
    assert contrast("#2563EB", "#2563EB") == 1.0
    assert round(contrast("#767676", "#FFFFFF"), 2) == 4.54


def test_both_role_palettes_have_the_same_keys_and_select_fills_one_dict(restored_theme):
    """The role palette (PALETTE, the names widgets read) has the same keys
    in both themes; selecting a theme fills the same dict, so a module
    that imported it sees the theme in use."""
    from spacemissionstudio.gui import theme

    assert set(theme.DARK) == set(theme.LIGHT)
    palette = theme.PALETTE
    theme.select_palette("dark")
    assert palette is theme.PALETTE and palette == theme.DARK and theme.current_theme() == "dark"
    with pytest.raises(ValueError):
        theme.select_palette("sepia")


def test_the_theme_setting_is_kept_and_system_follows_the_platform(qapp, monkeypatch):
    """View > Theme is remembered in settings.ini (under the test's home);
    System is light unless the platform says dark."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui import theme

    assert theme.theme_setting() == "system"
    theme.set_theme_setting("dark")
    assert theme.theme_setting() == "dark" and theme.resolve_theme("dark") == "dark"
    with pytest.raises(ValueError):
        theme.set_theme_setting("sepia")

    class _Hints:
        def __init__(self, scheme):
            self.scheme = scheme

        def colorScheme(self):  # noqa: N802 -- Qt API name
            return self.scheme

    monkeypatch.setattr(qapp, "styleHints", lambda: _Hints(Qt.ColorScheme.Dark))
    assert theme.resolve_theme("system", qapp) == "dark"
    monkeypatch.setattr(qapp, "styleHints", lambda: _Hints(Qt.ColorScheme.Unknown))
    assert theme.resolve_theme("system", qapp) == "light"


def _light_only():
    from spacemissionstudio.gui.theme import tokens

    light, dark = tokens.tokens("light"), tokens.tokens("dark")
    return {v.upper() for v in light.values()} - {v.upper() for v in dark.values()}


def _colours(sheet):
    return {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", sheet)}


def test_a_live_switch_restyles_every_open_view(qtbot, restored_theme):
    """Switched to dark with the window open: the one application sheet
    holds no light-only colour, no widget keeps a sheet of its own, the
    canvas, a field and a badge paint in the dark tokens, and the plots
    and the explainer badges are rebuilt from the dark tokens."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui import results_widget
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import TOKENS, apply_theme, signals

    apply_theme(restored_theme, "light")
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    assert window.open_path(_TEMPLATES.glob("22_*.json").__next__())  # badges, the top bar, a page
    qtbot.waitUntil(lambda: not window.scenario_explainer_widget.pending, timeout=10000)  # its explanation (M4b)
    window.scenario_editor.show_spacecraft(0)
    restored_theme.processEvents()
    seen = []
    signals.changed.connect(seen.append)
    try:
        apply_theme(restored_theme, "dark")
    finally:
        signals.changed.disconnect(seen.append)
    restored_theme.processEvents()
    assert seen == ["dark"]
    assert _colours(restored_theme.styleSheet()) & _light_only() == set()
    own = [type(w).__name__ for w in [window, *window.findChildren(object)]
           if hasattr(w, "styleSheet") and w.styleSheet() and w.objectName() != "qt_scrollarea_viewport"]
    assert own == []
    image = window.grab().toImage()
    assert image.pixelColor(2, image.height() // 2).name().upper() in {TOKENS["bg.canvas"], TOKENS["bg.surface"]}
    window.show_view(window.scenario_explainer_widget)  # Scenario > Overview, a page since M4b (was a dock)
    restored_theme.processEvents()
    badges = [w for w in window.findChildren(QLabel) if w.property("badge") and w.isVisible()]
    assert badges, "the starter template's explainer shows badges"
    badge = badges[0]
    fill = badge.grab().toImage().pixelColor(badge.width() // 2, 1).name().upper()
    assert fill == TOKENS[f"status.{badge.property('badge')}.soft"]
    assert f"background: {TOKENS['bg.surface']}" in results_widget._empty_state_html()
    assert TOKENS["bg.surface"] in results_widget._page_style()


def test_view_theme_applies_the_choice_at_once(qtbot, reported, restored_theme):
    """View > Theme > Dark stores the choice and applies it now; Light
    brings the light theme back."""
    from spacemissionstudio.gui import theme
    from spacemissionstudio.gui.main_window import MainWindow

    theme.apply_theme(restored_theme, "light")
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.theme_actions["system"].isChecked()
    window.theme_actions["dark"].trigger()
    assert theme.theme_setting() == "dark" and theme.current_theme() == "dark"
    assert reported[-1] == ("Theme: dark. It is the theme shown now.", "info")
    window.theme_actions["light"].trigger()
    assert theme.current_theme() == "light"
    assert reported[-1] == ("Theme: light. It is the theme shown now.", "info")


def test_item_colours_follow_a_theme_change(qtbot, restored_theme):
    """A list row coloured from a token takes the new theme's value when
    the theme changes (theme/items.py)."""
    from PySide6.QtWidgets import QListWidget, QListWidgetItem

    from spacemissionstudio.gui.theme import TOKENS, apply_theme
    from spacemissionstudio.gui.theme.items import retint, tint

    apply_theme(restored_theme, "light")
    view = QListWidget()
    qtbot.addWidget(view)
    item = QListWidgetItem("error row")
    view.addItem(item)
    tint(item, "status.critical.text")
    light = item.foreground().color().name().upper()
    apply_theme(restored_theme, "dark")
    retint(view)
    assert light == "#DA2331" and item.foreground().color().name().upper() == TOKENS["status.critical.text"] != light


def test_a_deleted_view_is_not_called_on_a_theme_change(qtbot, restored_theme):
    """A widget that redraws on theme changes and is then deleted by Qt is
    dropped from the listeners, not called (its C++ object is gone)."""
    from PySide6.QtWidgets import QWidget
    from shiboken6 import delete

    from spacemissionstudio.gui import theme

    calls = []

    class _View(QWidget):
        def _restyle(self, mode):
            calls.append((self.objectName(), mode))

    kept, dropped = _View(), _View()
    kept.setObjectName("kept")
    qtbot.addWidget(kept)
    theme.on_change(kept._restyle)
    theme.on_change(dropped._restyle)
    delete(dropped)  # Qt deletes the widget; the Python object stays
    theme.apply_theme(restored_theme, "dark")
    assert calls == [("kept", "dark")]
