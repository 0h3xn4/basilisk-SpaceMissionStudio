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
"""The colour tokens: the one source of every colour the GUI draws.

:data:`BRIEF` is the token table of ``docs/ui/UI_OVERHAUL.md`` verbatim,
the same in SpaceMissionStudio, SystemDesignStudio and HarnessDesignStudio.
:data:`ADJUSTED` lists the values changed to pass WCAG 2.2 AA, each with
the contrast that failed; ``docs/DECISIONS.md`` records them. Everything
else (:func:`tokens`) is derived from those two: the selected background,
the accent's hover and pressed steps, the status colours' text and tinted
backgrounds, and the diff backgrounds.

Token names are the brief's dotted names (``bg.canvas``, ``text.primary``,
``status.critical``). Status follows the Astro UXDS taxonomy: critical,
serious, caution, normal, standby and off. Each status has three tokens:
``status.<name>`` for icons and indicators (3:1 against the surfaces),
``status.<name>.text`` for words (4.5:1 against the surfaces and its own
tint) and ``status.<name>.soft`` for a tinted background.
"""

from __future__ import annotations

from typing import Dict

MODES = ("light", "dark")

# The brief's token table, verbatim.
BRIEF: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg.canvas": "#0B0D10",
        "bg.surface": "#111418",
        "bg.raised": "#171B21",
        "bg.hover": "#1D222A",
        "border.subtle": "#222832",
        "border.strong": "#2E3540",
        "text.primary": "#E7E9EC",
        "text.secondary": "#A1A8B3",
        "text.muted": "#7A828E",
        "accent": "#4C8DFF",
    },
    "light": {
        "bg.canvas": "#F7F7F8",
        "bg.surface": "#FFFFFF",
        "bg.raised": "#FFFFFF",
        "bg.hover": "#F0F1F3",
        "border.subtle": "#E4E5E9",
        "border.strong": "#D0D3D9",
        "text.primary": "#16181D",
        "text.secondary": "#50565F",
        "text.muted": "#7C838D",
        "accent": "#2563EB",
    },
}
# bg.selected: the accent over the surface at this share (the brief: 16 % dark, 10 % light).
SELECTED_SHARE = {"dark": 0.16, "light": 0.10}  # [-]

# The brief's status proposal (Astro UXDS), the same in both themes.
STATUS_BRIEF = {
    "critical": "#FF4D4F",
    "serious": "#FF8A3D",
    "caution": "#F5B83D",
    "normal": "#3DD68C",
    "standby": "#56B4F5",
}
STATUSES = ("critical", "serious", "caution", "normal", "standby", "off")

# Values changed from the brief to pass WCAG 2.2 AA, with what failed. The
# lightness (OKLab L) was moved in 0.005 steps, hue and chroma kept, until
# the value passed against every background it is drawn on: the canvas,
# the surface, the raised surface, the hover row and the selected row.
ADJUSTED: Dict[str, Dict[str, str]] = {
    "light": {
        # 3.83:1 on bg.surface (needs 4.5:1 for text).
        "text.muted": "#666D77",
        # Icons and indicators (3:1): the brief's light-theme status values
        # are drawn for a dark background; on white they reach 2.5-1.6:1.
        "status.critical": "#FF4D4F",  # 3.25:1 as given: kept
        "status.serious": "#E16F18",
        "status.caution": "#BE8400",
        "status.normal": "#00A45D",
        "status.standby": "#3496D5",
        # Words (4.5:1).
        "status.critical.text": "#DA2331",
        "status.serious.text": "#BD4E00",
        "status.caution.text": "#9E6500",
        "status.normal.text": "#00833F",
        "status.standby.text": "#0077B4",
    },
    "dark": {
        # 4.12:1 on bg.hover and 3.86:1 on bg.selected (needs 4.5:1).
        "text.muted": "#868E9A",
    },
}

# Text drawn on the accent fill (a primary button, a ticked box). White on
# the dark theme's #4C8DFF is 3.2:1, so the dark theme uses its canvas.
ON_ACCENT = {"light": "#FFFFFF", "dark": "#0B0D10"}
# A tint's share of the surface for status and diff backgrounds.
SOFT_SHARE = {"light": 0.07, "dark": 0.16}  # [-]
# Text selection inside fields: the accent at this share.
TEXT_SELECTION_SHARE = {"light": 0.22, "dark": 0.34}  # [-]
# Disabled text: text.primary at this share over the surface. WCAG 1.4.3
# exempts inactive controls; it is kept readable all the same.
DISABLED_SHARE = 0.38  # [-]
# The accent's hover and pressed steps: mixed towards black (light) or
# white (dark) by these shares.
ACCENT_STEP = {"hover": 0.10, "pressed": 0.20}  # [-]
# The shadow of floating elements (menus, popovers, dialogs, toasts).
SHADOW = {"light": "#16181D", "dark": "#000000"}
SHADOW_ALPHA = {"light": 0.12, "dark": 0.48}  # [-]


def mix(colour: str, base: str, share: float) -> str:
    """``colour`` laid over ``base`` at ``share`` (0..1), as ``#RRGGBB``."""
    a = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(base[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(round(x * share + y * (1.0 - share)) for x, y in zip(a, b))


def _build(mode: str) -> Dict[str, str]:
    t = dict(BRIEF[mode])
    t.update({key: value for key, value in ADJUSTED[mode].items() if not key.startswith("status.")})
    surface, accent = t["bg.surface"], t["accent"]
    t["bg.selected"] = mix(accent, surface, SELECTED_SHARE[mode])
    t["bg.field"] = surface
    t["border.focus"] = accent
    t["text.disabled"] = mix(t["text.primary"], surface, DISABLED_SHARE)
    t["text.on_accent"] = ON_ACCENT[mode]
    t["text.link"] = accent
    toward = "#000000" if mode == "light" else "#FFFFFF"
    t["accent.hover"] = mix(toward, accent, ACCENT_STEP["hover"])
    t["accent.pressed"] = mix(toward, accent, ACCENT_STEP["pressed"])
    t["accent.soft"] = mix(accent, surface, TEXT_SELECTION_SHARE[mode])
    for name in STATUSES:
        if name == "off":
            icon = text = t["text.muted"]
        else:
            icon = ADJUSTED[mode].get(f"status.{name}", STATUS_BRIEF[name])
            text = ADJUSTED[mode].get(f"status.{name}.text", icon)
        t[f"status.{name}"] = icon
        t[f"status.{name}.text"] = text
        t[f"status.{name}.soft"] = mix(icon, surface, SOFT_SHARE[mode]) if name != "off" else t["bg.hover"]
    t["diff.added"] = t["status.normal.soft"]
    t["diff.removed"] = t["status.critical.soft"]
    t["diff.changed"] = t["status.caution.soft"]
    t["shadow"] = SHADOW[mode]
    return t


_TOKENS = {mode: _build(mode) for mode in MODES}


def tokens(mode: str) -> Dict[str, str]:
    """Every token of ``mode`` (``"light"`` or ``"dark"``): a copy."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, not {mode!r}")
    return dict(_TOKENS[mode])


# WCAG 2.2 AA pairs the GUI draws: (foreground, background, minimum ratio).
# 4.5:1 for text (1.4.3), 3:1 for icons, indicators and focus rings (1.4.11).
TEXT_BACKGROUNDS = ("bg.canvas", "bg.surface", "bg.raised", "bg.hover", "bg.selected")
CONTRAST_PAIRS = (
    [(fg, bg, 4.5) for fg in ("text.primary", "text.secondary", "text.muted") for bg in TEXT_BACKGROUNDS]
    + [("text.link", bg, 4.5) for bg in ("bg.canvas", "bg.surface", "bg.raised", "bg.hover")]
    + [("text.on_accent", key, 4.5) for key in ("accent", "accent.hover", "accent.pressed")]
    + [("text.primary", "accent.soft", 4.5)]
    + [(f"status.{name}.text", bg, 4.5) for name in STATUSES
       for bg in ("bg.canvas", "bg.surface", "bg.raised", f"status.{name}.soft")]
    + [("text.primary", f"status.{name}.soft", 4.5) for name in STATUSES]
    + [(f"status.{name}", bg, 3.0) for name in STATUSES for bg in ("bg.canvas", "bg.surface", "bg.raised")]
    + [("border.focus", bg, 3.0) for bg in ("bg.canvas", "bg.surface", "bg.raised", "bg.field")]
    + [("accent", bg, 3.0) for bg in ("bg.canvas", "bg.surface")]
)


def luminance(colour: str) -> float:
    """WCAG relative luminance of ``#RRGGBB``."""
    channels = [int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two ``#RRGGBB`` colours."""
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)
