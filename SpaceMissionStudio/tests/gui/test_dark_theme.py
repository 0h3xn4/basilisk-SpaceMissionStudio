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
"""The dark theme (docs/ux-standard.md, "dark and light themes";
iteration 7a): Carbon g100 under the light theme's keys, readable pairs in
both themes, the View > Theme setting, recoloured glyphs, and no light
colour left in a dark window."""

import re

import pytest

pytestmark = pytest.mark.requires_gui

# (text, background, minimum WCAG contrast): the pairs the stylesheet and
# the widgets draw. 4.5:1 for text, 3:1 for indicators and outlines
# (WCAG 2.1, 1.4.3 and 1.4.11).
_PAIRS = [
    ("text", "bg", 4.5), ("text", "surface", 4.5), ("text", "field", 4.5), ("text", "selected", 4.5),
    ("text", "hover", 4.5), ("text_muted", "bg", 4.5), ("text_muted", "surface", 4.5),
    ("text_muted", "field", 4.5), ("on_accent", "accent", 4.5), ("on_accent", "accent_hover", 4.5),
    ("on_accent", "accent_pressed", 4.5), ("accent_text", "surface", 4.5), ("accent_text", "bg", 4.5),
    ("on_inverse", "inverse", 4.5), ("danger_text", "danger_soft", 4.5), ("success_text", "success_soft", 4.5),
    ("warning", "warning_soft", 4.5), ("info_text", "info_soft", 4.5), ("text", "danger_soft", 4.5),
    ("text", "success_soft", 4.5), ("text", "warning_soft", 4.5), ("text", "info_soft", 4.5),
    ("tag_success_text", "tag_success_bg", 4.5), ("tag_danger_text", "tag_danger_bg", 4.5),
    ("tag_accent_text", "tag_accent_bg", 4.5), ("warning", "surface", 4.5), ("danger_text", "surface", 3.0),
    ("focus", "field", 3.0), ("focus", "surface", 3.0), ("border_strong", "field", 1.5),
    ("accent", "bg", 3.0), ("danger", "surface", 4.5), ("danger", "bg", 4.5), ("success", "surface", 3.0),  # danger is error text too
    ("icon_inverse", "text", 3.0),  # the tick on a ticked box
]


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.fixture
def dark_palette():
    """The dark palette while the test runs; the light one after."""
    from spacemissionstudio.gui import theme

    theme.select_palette("dark")
    yield theme
    theme.select_palette("light")


def test_both_themes_have_the_same_keys():
    """The dark and light themes define the same colors."""
    from spacemissionstudio.gui.theme import DARK, LIGHT

    assert set(DARK) == set(LIGHT)


@pytest.mark.parametrize("name", ["light", "dark"])
def test_every_pair_the_app_draws_is_readable(name):
    """Text on its backgrounds at 4.5:1, outlines and indicators at 3:1,
    in each theme (the field rule is a field's edge, at 1.5:1)."""
    from spacemissionstudio.gui.theme import DARK, LIGHT

    palette = DARK if name == "dark" else LIGHT
    low = [(fg, bg, round(_contrast(palette[fg], palette[bg]), 2)) for fg, bg, need in _PAIRS
           if _contrast(palette[fg], palette[bg]) < need]
    assert low == []


def test_the_light_palette_is_unchanged_by_the_new_keys():
    """In the light theme the new keys are the colours their uses had."""
    from spacemissionstudio.gui.theme import LIGHT

    assert LIGHT["accent_text"] == LIGHT["focus"] == LIGHT["accent"]
    assert LIGHT["on_inverse"] == LIGHT["icon_inverse"] == LIGHT["on_accent"]
    assert (LIGHT["disabled_fill"], LIGHT["on_disabled_fill"]) == (LIGHT["text_disabled"], LIGHT["border_strong"])


def test_select_palette_fills_the_same_dict(dark_palette):
    """PALETTE is one dict: what imported it sees the theme selected."""
    from spacemissionstudio.gui.theme import DARK, PALETTE

    assert PALETTE == DARK and dark_palette.current_theme() == "dark"
    with pytest.raises(ValueError):
        dark_palette.select_palette("sepia")


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


def test_glyphs_are_recoloured_for_the_dark_theme(dark_palette):
    """A dark copy of an SVG: each light glyph colour swapped for the dark
    one of the same key, white kept; the light theme uses the file."""
    from spacemissionstudio.gui.theme import _ASSETS_DIR, DARK, LIGHT

    source = _ASSETS_DIR / "chevron-down.svg"
    copy = dark_palette.themed_asset(source)
    assert copy != source and copy.name == source.name
    text = copy.read_text(encoding="utf-8").upper()
    assert DARK["text_muted"] in text and LIGHT["text_muted"] not in text
    assert "#FFFFFF" in dark_palette.themed_asset(_ASSETS_DIR / "tb-run.svg").read_text(encoding="utf-8").upper()
    tick = dark_palette.themed_asset(_ASSETS_DIR / "check.svg").read_text(encoding="utf-8").upper()
    assert DARK["icon_inverse"] in tick and "#FFFFFF" not in tick  # dark on the light fill of a ticked box
    dark_palette.select_palette("light")
    assert dark_palette.themed_asset(source) == source


def test_a_dark_window_has_no_light_colour_left(qtbot, dark_palette):
    """Built in the dark theme, no widget's stylesheet holds a colour only
    the light theme has (a colour read at import, or typed in), and the
    badges and a chart take the dark tokens."""
    from spacemissionstudio.gui.badges import SUCCESS, badge_style
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import DARK, LIGHT

    light_only = {value.upper() for value in LIGHT.values()} - {value.upper() for value in DARK.values()}
    from pathlib import Path

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    templates = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
    assert window.open_path(templates / "22_starter_first_leo_satellite.json")  # badges, the top bar, a page
    window.scenario_editor.show_spacecraft(0)
    found = set()
    for widget in [window, *window.findChildren(object)]:
        sheet = widget.styleSheet() if hasattr(widget, "styleSheet") else ""
        found |= {colour.upper() for colour in re.findall(r"#[0-9A-Fa-f]{6}\b", sheet)} & light_only
    assert found == set()
    assert DARK["tag_success_bg"] in badge_style(SUCCESS)
    from spacemissionstudio.gui.results_widget import _empty_state_html, _page_style

    assert f"background: {DARK['surface']}" in _empty_state_html() and DARK["surface"] in _page_style()


def test_view_theme_remembers_the_choice_for_the_next_start(qtbot, reported):
    """View > Theme > Dark stores the choice and says when it applies."""
    from spacemissionstudio.gui import theme
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.theme_actions["system"].isChecked()
    window.theme_actions["dark"].trigger()
    assert theme.theme_setting() == "dark"
    assert reported[-1] == ("Theme: dark. It applies when SpaceMissionStudio next starts.", "info")
    window.theme_actions["light"].trigger()
    assert reported[-1] == ("Theme: light. It is the theme shown now.", "info")
