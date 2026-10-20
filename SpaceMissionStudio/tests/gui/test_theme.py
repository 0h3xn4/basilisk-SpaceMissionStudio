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
"""The theme package (gui/theme/): the token table, the bundled fonts and
icons, the generated style sheet, the Plotly template and the live theme
switch (docs/ui/UI_OVERHAUL.md, "Tokens"; docs/DECISIONS.md)."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_ROOT = Path(__file__).resolve().parents[2]
_BRIEF = _ROOT / "docs" / "ui" / "UI_OVERHAUL.md"
_DECISIONS = _ROOT / "docs" / "DECISIONS.md"



def test_the_tokens_are_the_briefs_table_or_a_recorded_adjustment():
    """Every row of the brief's token table is a token of the same value,
    except where tokens.ADJUSTED changes it to pass WCAG AA, and each
    adjusted token is named in docs/DECISIONS.md."""
    from spacemissionstudio.gui.theme import tokens

    table = re.findall(r"^\| ([a-z]+\.[a-z]+|accent) \| (#[0-9A-F]{6})[^|]*\| (#[0-9A-F]{6})[^|]*\|$",
                       _BRIEF.read_text(encoding="utf-8"), re.MULTILINE)
    assert len(table) == 10  # bg.selected is derived; the other ten rows carry values
    decisions = _DECISIONS.read_text(encoding="utf-8")
    for name, dark, light in table:
        assert tokens.BRIEF["dark"][name] == dark and tokens.BRIEF["light"][name] == light, name
        for mode in tokens.MODES:
            value = tokens.tokens(mode)[name]
            assert value == tokens.ADJUSTED[mode].get(name, tokens.BRIEF[mode][name]), (mode, name)
    for mode, changed in tokens.ADJUSTED.items():
        for name, value in changed.items():
            assert f"`{name}`" in decisions and value in decisions, (mode, name, value)
    status = dict(re.findall(r"(critical|serious|caution|normal|standby) (#[0-9A-F]{6})",
                             _BRIEF.read_text(encoding="utf-8")))
    assert status == tokens.STATUS_BRIEF


def test_both_themes_have_the_same_tokens_and_the_selected_tint():
    """Light and dark define the same token names; bg.selected is the
    accent at 10 % (light) and 16 % (dark) over the surface."""
    from spacemissionstudio.gui.theme import tokens

    light, dark = tokens.tokens("light"), tokens.tokens("dark")
    assert set(light) == set(dark)
    for mode, values in (("light", light), ("dark", dark)):
        assert values["bg.selected"] == tokens.mix(values["accent"], values["bg.surface"],
                                                   tokens.SELECTED_SHARE[mode])
    assert tokens.SELECTED_SHARE == {"light": 0.10, "dark": 0.16}
    with pytest.raises(ValueError):
        tokens.tokens("sepia")


def test_the_bundled_fonts_register_and_are_the_application_font(restored_theme):
    """Inter (400, 500, 600) and JetBrains Mono (400, 500) ship in the
    package with their OFL texts, register with Qt from there, and Inter
    at the 13 px body size is the application font. CI runs this on
    Linux, Windows and macOS."""
    from PySide6.QtGui import QFontDatabase

    from spacemissionstudio.gui.theme import FONTS_DIR, MONO_FONT_FAMILY, UI_FONT_FAMILY, apply_theme, load_fonts

    assert sorted(p.relative_to(FONTS_DIR).as_posix() for p in FONTS_DIR.rglob("*.ttf")) == [
        "inter/Inter-Medium.ttf", "inter/Inter-Regular.ttf", "inter/Inter-SemiBold.ttf",
        "jetbrains-mono/JetBrainsMono-Medium.ttf", "jetbrains-mono/JetBrainsMono-Regular.ttf"]
    for family in ("inter", "jetbrains-mono"):
        assert "SIL OPEN FONT LICENSE" in (FONTS_DIR / family / "OFL.txt").read_text(encoding="utf-8").upper()
    families = load_fonts()
    assert UI_FONT_FAMILY in families and MONO_FONT_FAMILY in families
    assert {"Regular", "Medium", "SemiBold"} <= set(QFontDatabase.styles(UI_FONT_FAMILY))
    apply_theme(restored_theme, "light")
    assert restored_theme.font().family() == UI_FONT_FAMILY
    assert restored_theme.font().pixelSize() == 13  # [px] the brief's body size


def test_no_ibm_plex_or_carbon_remains_in_the_gui():
    """The Carbon restyle is gone: no IBM Plex file and no Carbon name in
    the GUI package's code (docs/DECISIONS.md records the change)."""
    gui = _ROOT / "spacemissionstudio" / "gui"
    assert not [p for p in gui.rglob("*") if "plex" in p.name.lower()]
    named = [p.name for p in gui.rglob("*.py") if re.search(r"\bCarbon\b|IBM Plex", p.read_text(encoding="utf-8"))]
    assert named == []


def test_numeric_columns_get_tabular_figures(qapp):
    """Numbers in tables use Inter's tabular figures where Qt supports font
    features, JetBrains Mono otherwise."""
    from PySide6.QtGui import QFont

    from spacemissionstudio.gui.theme import MONO_FONT_FAMILY, numeric_font, tabular_figures_supported

    font = numeric_font()
    if tabular_figures_supported():
        assert font.featureValue(QFont.Tag("tnum")) == 1
    else:
        assert font.family() == MONO_FONT_FAMILY


def test_every_icon_the_app_uses_is_bundled_with_its_licence():
    """The toolbar and step icons and the style sheet's glyphs are Lucide
    icons in the package, with Lucide's ISC licence."""
    from spacemissionstudio.gui.theme import icons

    names = set(icons.ACTION_ICONS.values()) | set(icons.STEP_ICONS.values()) | {
        "chevron-down", "chevron-up", "chevron-right", "check"}
    assert sorted(name for name in names if not icons.available(name)) == []
    assert "ISC License" in (icons.ICONS_DIR / "LICENSE").read_text(encoding="utf-8")
    for path in icons.ICONS_DIR.glob("*.svg"):
        assert "currentColor" in path.read_text(encoding="utf-8"), path.name  # tintable


def test_icons_follow_the_theme(restored_theme):
    """An icon is drawn in its token's colour of the theme in use: the same
    QIcon changes colour when the theme does."""
    from spacemissionstudio.gui.theme import TOKENS, apply_theme, icon

    def ink(qicon):
        image = qicon.pixmap(64, 64).toImage()
        pixels = [image.pixelColor(x, y) for x in range(64) for y in range(64)]
        return max(pixels, key=lambda c: c.alpha()).name().upper()

    play = icon("play", "accent")
    apply_theme(restored_theme, "light")
    light = ink(play)
    assert light == TOKENS["accent"]
    apply_theme(restored_theme, "dark")
    assert ink(play) == TOKENS["accent"] != light


def test_every_toolbar_action_has_an_icon(qtbot):
    """Every toolbar action has an icon, except the run-mode drop-down."""
    from PySide6.QtWidgets import QToolBar

    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    for toolbar in window.findChildren(QToolBar):
        for action in toolbar.actions():
            if action.isSeparator() or action is window.run_mode_button_action:
                continue  # the run mode picker beside Run: a text drop-down, like a combo box (U-18)
            assert not action.icon().isNull(), action.text()


def test_apply_theme_sets_the_palette_and_one_sheet(restored_theme):
    """Applying a theme sets the palette from the tokens (Mid, used for
    muted hint text, is text.secondary: Qt's computed default was
    unreadable) and a style sheet; applying it twice changes nothing."""
    from PySide6.QtGui import QPalette

    from spacemissionstudio.gui.theme import TOKENS, apply_theme

    for mode in ("light", "dark"):
        apply_theme(restored_theme, mode)
        palette = restored_theme.palette()
        assert palette.color(QPalette.ColorRole.Window).name().upper() == TOKENS["bg.canvas"]
        assert palette.color(QPalette.ColorRole.Base).name().upper() == TOKENS["bg.surface"]
        assert palette.color(QPalette.ColorRole.Mid).name().upper() == TOKENS["text.secondary"]
        sheet = restored_theme.styleSheet()
        apply_theme(restored_theme, mode)
        assert restored_theme.styleSheet() == sheet != ""


def test_every_file_the_style_sheet_references_exists(restored_theme):
    """The combo and spin arrows and the tick are tinted icon files: a
    missing one would silently bring back arrow-less combo boxes."""
    from spacemissionstudio.gui.theme import apply_theme

    for mode in ("light", "dark"):
        apply_theme(restored_theme, mode)
        referenced = re.findall(r"url\(([^)]+)\)", restored_theme.styleSheet())
        assert referenced
        assert [path for path in referenced if not Path(path).is_file()] == []


def test_the_style_sheet_parses_without_qt_warnings(qtbot, restored_theme):
    """No Qt style sheet warning while the main window, a scenario and
    the editor dialogs are shown in either theme (the brief's
    "no warnings from Qt about stylesheets")."""
    from PySide6.QtCore import qInstallMessageHandler

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme

    messages = []
    previous = qInstallMessageHandler(lambda _mode, _context, text: messages.append(text))
    try:
        templates = _ROOT / "spacemissionstudio" / "scenarios" / "templates"
        for mode in ("light", "dark"):
            apply_theme(restored_theme, mode)
            window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
            qtbot.addWidget(window)
            window.show()
            assert window.open_path(next(templates.glob("19_*.json")))
            window.scenario_editor.show_spacecraft(0)
            for index in range(window.main_tabs.count()):
                window.main_tabs.setCurrentIndex(index)
                restored_theme.processEvents()
    finally:
        qInstallMessageHandler(previous)
    assert [m for m in messages if "style" in m.lower() or "parse" in m.lower()] == []


def test_the_plotly_template_comes_from_the_tokens():
    """Plots: Inter, transparent backgrounds over the surface, gridlines in
    border.subtle, axis text in text.secondary, the categorical palette as
    the colourway."""
    from spacemissionstudio.gui.theme import palettes, plotly_template, tokens

    for mode in tokens.MODES:
        t = tokens.tokens(mode)
        layout = plotly_template.layout(t, palettes.categorical(mode))
        assert layout["paper_bgcolor"] == layout["plot_bgcolor"] == plotly_template.TRANSPARENT
        assert layout["font"]["family"].startswith("'Inter'")
        assert layout["xaxis"]["gridcolor"] == t["border.subtle"]
        assert layout["yaxis"]["tickfont"]["color"] == t["text.secondary"]
        assert layout["colorway"] == palettes.CATEGORICAL[mode]
        assert t["bg.surface"] in plotly_template.page_css(t)
        assert "@font-face" in plotly_template.font_faces()


def _oklab(colour):
    r, g, b = (int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b))
    lms = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
           0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
           0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    lo, m, s = (v ** (1 / 3) for v in lms)
    return (0.2104542553 * lo + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * lo - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * lo + 0.7827717662 * m - 0.8086757660 * s)


def test_the_categorical_palette_is_distinct_and_readable():
    """Eight colours per theme, each at least 3:1 against the surface and
    at least Delta E 8 (OKLab x 100) from every status colour and the
    accent; neighbouring slots at least Delta E 15 apart (the full
    colour-vision-deficiency check is the validator run recorded in
    docs/DECISIONS.md)."""
    from spacemissionstudio.gui.theme import palettes, tokens

    def delta_e(a, b):
        return 100 * sum((x - y) ** 2 for x, y in zip(_oklab(a), _oklab(b))) ** 0.5

    for mode in tokens.MODES:
        t = tokens.tokens(mode)
        series = palettes.CATEGORICAL[mode]
        assert len(series) == len(set(series)) == 8
        reserved = [t["accent"]] + [t[f"status.{name}{part}"] for name in tokens.STATUSES[:-1]
                                    for part in ("", ".text")]
        for colour in series:
            assert tokens.contrast(colour, t["bg.surface"]) >= 3.0, (mode, colour)
            assert min(delta_e(colour, other) for other in reserved) >= 8.0, (mode, colour)
        assert min(delta_e(a, b) for a, b in zip(series, series[1:])) >= 15.0, mode


def test_the_charts_share_the_live_series_colours(restored_theme):
    """Plots and the event timeline read the theme's categorical palette,
    one slot per event kind, and follow a theme change."""
    from spacemissionstudio.engine import events
    from spacemissionstudio.gui import event_timeline_widget, results_widget
    from spacemissionstudio.gui.theme import SERIES_COLORS, apply_theme, palettes

    for mode in ("light", "dark"):
        apply_theme(restored_theme, mode)
        assert results_widget._SERIES_COLORS == SERIES_COLORS == palettes.CATEGORICAL[mode]
        assert [event_timeline_widget.kind_colour(kind) for kind in events.KINDS] == SERIES_COLORS[:len(events.KINDS)]


def test_set_role_restyles_a_shown_widget(qtbot, restored_theme):
    """A label's tone set after it is shown takes effect at once."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.theme import TOKENS, apply_theme, set_role

    apply_theme(restored_theme, "light")
    label = QLabel("value")
    qtbot.addWidget(label)
    label.show()
    restored_theme.processEvents()
    set_role(label, tone="critical")
    assert label.palette().color(label.foregroundRole()).name().upper() == TOKENS["status.critical.text"]
    set_role(label, tone=None)
    assert label.palette().color(label.foregroundRole()).name().upper() == TOKENS["text.primary"]


def test_the_primary_run_button_draws_its_icon_on_the_fill(qtbot, restored_theme):
    """The Run button is filled with the accent, so its icon is drawn in
    text.on_accent: the action's accent icon would vanish on the fill. It
    stays so after the action changes."""
    from PySide6.QtWidgets import QToolButton

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import TOKENS, apply_theme

    apply_theme(restored_theme, "light")
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    button = window.findChild(QToolButton, "primaryToolButton")
    window.run_action.setToolTip("changed")  # an action change copies the action's icon onto the button
    qtbot.wait(10)
    image = button.icon().pixmap(32, 32).toImage()
    ink = max((image.pixelColor(x, y) for x in range(32) for y in range(32)), key=lambda c: c.alpha())
    assert ink.name().upper() == TOKENS["text.on_accent"]
