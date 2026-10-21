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
"""The GUI's theme: one source of truth for colour, type, spacing, icons
and plot styling (``docs/DESIGN.md``).

* :mod:`.tokens`: the colour tokens (the brief's table, plus what is
  derived from it) and the WCAG contrast pairs.
* :mod:`.typography`: font families, the size and weight scale, spacing,
  radii and motion.
* :mod:`.palettes`: the categorical chart palette.
* :mod:`.fonts`: the bundled Inter and JetBrains Mono, registered with Qt.
* :mod:`.icons`: the bundled Lucide icons, tinted from the tokens.
* :mod:`.qss`: the application style sheet, generated from the tokens.
* :mod:`.plotly_template`: the Plotly layout and plot-page CSS.
* :mod:`.apply`: :func:`apply_theme` (live), the ``changed`` signal and
  the theme setting.

No colour, font family or pixel size appears in GUI code outside this
package (``tests/gui/test_design_rules.py`` checks it): widgets read
:data:`TOKENS` (or the older role names in :data:`PALETTE`), pick a look
with :func:`set_role`, and redraw on ``signals.changed``.
"""

from __future__ import annotations

import weakref

from PySide6.QtCore import QObject
from shiboken6 import isValid

from . import palettes, plotly_template, tokens
from .apply import (THEMES, apply_theme, follow_system, last_apply_ms, resolve_theme, set_role,
                    set_theme_setting, signals, theme_setting)
from .fonts import FONTS_DIR, load_fonts, mono_font, numeric_font, tabular_figures_supported, ui_font
from .icons import action_icon, icon, step_icon
from .qss import stylesheet
from .state import DARK, LIGHT, PALETTE, ROLES, SERIES_COLORS, TOKENS, current as current_theme
from .state import select as select_palette
from .typography import (CONTENT_MAX_WIDTH_PX, CONTROL_HEIGHT, ICON_SIZE, MONO_FONT_FAMILY, RADIUS, ROW_HEIGHT,
                         SIZE, SPACE, UI_FONT_FAMILY, WEB_FONT_STACK, WEB_MONO_STACK, WEIGHT)

_listeners: list = []  # weak references to the callbacks of on_change


def on_change(callback) -> None:
    """Call ``callback(mode)`` after every theme change. A bound method is
    held weakly and dropped once its object is gone, or (a widget) once
    Qt has deleted it, so a closed view never runs."""
    _listeners.append(weakref.WeakMethod(callback) if hasattr(callback, "__self__") else (lambda: callback))


def _notify(mode: str) -> None:
    live = []
    for ref in _listeners:
        callback = ref()
        owner = getattr(callback, "__self__", None)
        if callback is None or (isinstance(owner, QObject) and not isValid(owner)):
            continue  # its object is gone, or Qt deleted the widget
        live.append((ref, callback))
    _listeners[:] = [ref for ref, _callback in live]
    for _ref, callback in live:
        callback(mode)


signals.changed.connect(_notify)


def colour(token: str) -> str:
    """The current ``#RRGGBB`` of ``token`` (or of a role name)."""
    return TOKENS[token] if token in TOKENS else PALETTE[token]


__all__ = [
    "CONTENT_MAX_WIDTH_PX", "CONTROL_HEIGHT", "DARK", "FONTS_DIR", "ICON_SIZE", "LIGHT", "MONO_FONT_FAMILY",
    "PALETTE", "RADIUS", "ROLES", "ROW_HEIGHT", "SERIES_COLORS", "SIZE", "SPACE", "THEMES", "TOKENS",
    "UI_FONT_FAMILY", "WEB_FONT_STACK", "WEB_MONO_STACK", "WEIGHT", "action_icon", "apply_theme", "colour",
    "current_theme", "follow_system", "icon", "last_apply_ms", "load_fonts", "mono_font", "numeric_font",
    "on_change", "palettes", "plotly_template", "resolve_theme", "select_palette", "set_role",
    "set_theme_setting", "signals", "step_icon", "stylesheet", "tabular_figures_supported", "theme_setting",
    "tokens", "ui_font",
]
