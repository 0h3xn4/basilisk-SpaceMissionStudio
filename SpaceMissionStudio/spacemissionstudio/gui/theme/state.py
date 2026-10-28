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
"""The theme in use: its tokens, the role palette widgets read, and the
chart palette, each one dict or list filled in place by :func:`select`, so
a module that imported it sees the theme selected now.

:data:`PALETTE` maps the role names the widgets use (``text_muted``,
``danger_soft`` ...) to tokens (:data:`ROLES`). Prefer the token names in
new code: ``TOKENS["text.secondary"]``.
"""

from __future__ import annotations


from . import palettes, tokens

# Role -> token. The roles are the names widgets have read since before
# the token table; each now stands for one token.
ROLES: dict[str, str] = {
    "bg": "bg.canvas",
    "surface": "bg.surface",
    "surface_alt": "bg.canvas",
    "raised": "bg.raised",
    "field": "bg.field",
    "hover": "bg.hover",
    "selected": "bg.selected",
    "border": "border.subtle",
    "border_strong": "border.strong",
    "field_edge": "border.strong",
    "text": "text.primary",
    "text_muted": "text.secondary",
    "text_faint": "text.muted",
    "text_disabled": "text.disabled",
    "disabled_fill": "bg.hover",
    "on_disabled_fill": "text.disabled",
    "accent": "accent",
    "accent_text": "text.link",
    "focus": "border.focus",
    "accent_hover": "accent.hover",
    "accent_pressed": "accent.pressed",
    "accent_soft": "accent.soft",
    "on_accent": "text.on_accent",
    "inverse": "bg.raised",
    "on_inverse": "text.primary",
    "icon_inverse": "text.on_accent",
    "danger": "status.critical.text",
    "success": "status.normal.text",
    "warning": "status.caution.text",
    "warning_fill": "status.caution",
    "info": "status.standby",
    "danger_soft": "status.critical.soft",
    "success_soft": "status.normal.soft",
    "warning_soft": "status.caution.soft",
    "info_soft": "status.standby.soft",
    "success_text": "status.normal.text",
    "danger_text": "status.critical.text",
    "info_text": "status.standby.text",
    "tag_success_bg": "status.normal.soft", "tag_success_text": "status.normal.text",
    "tag_danger_bg": "status.critical.soft", "tag_danger_text": "status.critical.text",
    "tag_accent_bg": "status.standby.soft", "tag_accent_text": "status.standby.text",
}


def role_palette(mode: str) -> dict[str, str]:
    """The role palette of ``mode``."""
    values = tokens.tokens(mode)
    return {role: values[token] for role, token in ROLES.items()}


LIGHT = role_palette("light")
DARK = role_palette("dark")

TOKENS: dict[str, str] = tokens.tokens("light")
PALETTE: dict[str, str] = dict(LIGHT)
SERIES_COLORS: list[str] = palettes.categorical("light")
_current = ["light"]


def select(mode: str) -> None:
    """Fill :data:`TOKENS`, :data:`PALETTE` and :data:`SERIES_COLORS` with
    ``mode``'s values (``"light"`` or ``"dark"``)."""
    if mode not in tokens.MODES:
        raise ValueError(f"theme must be 'light' or 'dark', not {mode!r}")
    TOKENS.clear()
    TOKENS.update(tokens.tokens(mode))
    PALETTE.clear()
    PALETTE.update(role_palette(mode))
    SERIES_COLORS[:] = palettes.categorical(mode)
    _current[0] = mode


def current() -> str:
    """``"light"`` or ``"dark"``: the theme in use."""
    return _current[0]
