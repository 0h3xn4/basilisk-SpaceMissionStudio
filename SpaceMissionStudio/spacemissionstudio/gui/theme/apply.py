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
"""Applying the theme: live, at any time, without a restart.

:func:`apply_theme` selects the tokens, sets the application's palette and
its one style sheet, and then emits :data:`signals`'s ``changed``. Widgets
styled by the sheet restyle themselves; what paints colours itself (plots,
diagrams, item colours in lists) connects to ``changed`` and redraws.

The choice (View > Theme: System, Light or Dark) is kept in
``~/.spacemissionstudio/settings.ini``. With System, the theme follows the
platform's colour scheme, also when it changes while the app runs.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from . import state
from .fonts import load_fonts, ui_font
from .qss import stylesheet
from .typography import UI_FONT_FAMILY

THEMES = ("system", "light", "dark")  # the View > Theme choices


class _Signals(QObject):
    changed = Signal(str)  # "light" or "dark", after the new theme is in place


signals = _Signals()
last_apply_ms = [0.0]  # [ms] how long the last apply_theme took (measured, for the timing log)
_followed: list = []  # the application whose colour-scheme changes are followed


def _settings():
    from PySide6.QtCore import QSettings

    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


def theme_setting() -> str:
    """The View > Theme choice: ``"system"`` (the default), ``"light"`` or ``"dark"``."""
    value = str(_settings().value("appearance/theme", "system"))
    return value if value in THEMES else "system"


def set_theme_setting(value: str) -> None:
    """Remember the View > Theme choice."""
    if value not in THEMES:
        raise ValueError(f"theme must be one of {THEMES}, not {value!r}")
    settings = _settings()
    settings.setValue("appearance/theme", value)
    settings.sync()


def resolve_theme(setting: str, app: Optional[QApplication] = None) -> str:
    """``"light"`` or ``"dark"`` for the setting: ``"system"`` follows the
    platform's colour scheme (light when it does not say)."""
    if setting in ("light", "dark"):
        return setting
    app = app or QApplication.instance()
    if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
        return "dark"
    return "light"


def _palette(app: QApplication) -> QPalette:
    t = state.TOKENS
    palette = QPalette(app.palette())
    roles = {
        QPalette.ColorRole.Window: "bg.canvas", QPalette.ColorRole.WindowText: "text.primary",
        QPalette.ColorRole.Base: "bg.surface", QPalette.ColorRole.AlternateBase: "bg.surface",
        QPalette.ColorRole.Text: "text.primary", QPalette.ColorRole.Button: "bg.surface",
        QPalette.ColorRole.ButtonText: "text.primary", QPalette.ColorRole.Highlight: "accent.soft",
        QPalette.ColorRole.HighlightedText: "text.primary", QPalette.ColorRole.ToolTipBase: "bg.raised",
        QPalette.ColorRole.ToolTipText: "text.primary", QPalette.ColorRole.PlaceholderText: "text.muted",
        QPalette.ColorRole.Link: "text.link", QPalette.ColorRole.Mid: "text.secondary",
        QPalette.ColorRole.Light: "bg.raised", QPalette.ColorRole.Midlight: "border.subtle",
        QPalette.ColorRole.Dark: "border.strong", QPalette.ColorRole.Shadow: "shadow",
    }
    for role, token in roles.items():
        palette.setColor(QPalette.ColorGroup.All, role, QColor(t[token]))
    if hasattr(QPalette.ColorRole, "Accent"):
        palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Accent, QColor(t["accent"]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["text.disabled"]))
    return palette


def apply_theme(app: QApplication, theme: Optional[str] = None) -> str:
    """Apply ``theme`` (``"light"`` or ``"dark"``; None: the View > Theme
    setting) to ``app``, live. Returns the theme applied.

    "Fusion" is the base style: the one built-in Qt style that renders the
    same on Linux, macOS and Windows and that style sheets restyle
    predictably. The sheet is cleared before the new one is set: Qt then
    builds the new rules once instead of diffing every widget against the
    old ones, which measured about five times faster on the main window.
    """
    started = time.perf_counter()
    mode = theme or resolve_theme(theme_setting(), app)
    state.select(mode)
    if app.style().name().lower() != "fusion":
        app.setStyle("Fusion")
    if UI_FONT_FAMILY in load_fonts() and app.font().family() != UI_FONT_FAMILY:
        app.setFont(ui_font())
    app.setPalette(_palette(app))
    sheet = stylesheet(state.TOKENS, state.SERIES_COLORS)
    if app.styleSheet():
        app.setStyleSheet("")
    app.setStyleSheet(sheet)
    if theme is None:
        follow_system(app)
    last_apply_ms[0] = (time.perf_counter() - started) * 1e3
    signals.changed.emit(mode)
    return mode


def follow_system(app: QApplication) -> None:
    """While the setting is System, re-apply the theme when the platform's
    colour scheme changes."""
    if _followed:
        return
    _followed.append(app)

    def changed(*_args) -> None:
        if theme_setting() == "system":
            apply_theme(app, resolve_theme("system", app))

    app.styleHints().colorSchemeChanged.connect(changed)


def set_role(widget: QWidget, role: Optional[str] = None, tone: Optional[str] = None,
             badge: Optional[str] = None, **properties) -> QWidget:
    """Give ``widget`` its look from the style sheet: a ``role``, a text
    ``tone``, a status ``badge`` or other style properties (``variant``,
    ``state``). None clears one. A widget already shown is re-polished, so
    a change of state shows at once. Returns ``widget``."""
    values = dict(role=role, tone=tone, badge=badge, **properties)
    changed = False
    for name, value in values.items():
        current = widget.property(name)
        if (current or None) != (value or None):
            widget.setProperty(name, value if value is not None else None)
            changed = True
    if changed and widget.testAttribute(Qt.WidgetAttribute.WA_WState_Polished):
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
    return widget
