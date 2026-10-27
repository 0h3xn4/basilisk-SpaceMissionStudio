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
"""Chart palettes, generated for each theme.

:data:`CATEGORICAL` is the 8-colour categorical palette of every plot and
diagram, in a fixed order: series take slots in order and never cycle
back to a slot already in use. It was searched for in OKLCH and checked
with the data-visualisation validator (``docs/DECISIONS.md``):

* light, on ``bg.surface`` #FFFFFF: worst adjacent colour-vision-deficiency
  separation Delta E 14.3 (protan), worst adjacent normal-vision Delta E
  20.8, every colour at least 3:1 against the surface;
* dark, on ``bg.surface`` #111418: worst adjacent CVD Delta E 14.8
  (deutan), normal-vision 15.2, every colour at least 3:1;
* every colour at least Delta E 8 from every status colour (icon and text
  values) and from the accent, so a series is never read as a status.

It is validated for adjacent pairs (lines, bars, stacks: every chart in
the GUI today). With all 28 pairs side by side (a scatter of eight
groups) two pairs fall below the floors in each theme, which is why every
chart keeps a legend: colour is never the only cue.
"""

from __future__ import annotations


# Hue order (OKLCH h): orchid 325, brown 65, purple 305, green 135, teal
# 185, blue 265, crimson 10, ocean 225.
CATEGORICAL: dict[str, list[str]] = {
    "light": ["#AE59B4", "#8A3600", "#6C25A4", "#236400", "#00A596", "#5283FE", "#B80040", "#005F93"],
    "dark": ["#CA4ED3", "#B36C0D", "#8B63B6", "#458604", "#00A794", "#3163F1", "#DA185B", "#007CB1"],
}


def categorical(mode: str) -> list[str]:
    """The categorical palette of ``mode``: a copy."""
    return list(CATEGORICAL[mode])

# The application icon (gui/icons.py): blue solar panels in the light
# theme's accent, a gold (multi-layer insulation) body. One icon for both
# themes: the taskbar's background is the platform's, not ours.
APP_ICON = {
    "panel": "#2563EB",  # the light accent
    "panel_line": "#1E3A8A",  # antenna and panel grid lines
    "body": "#CFB87C",
    "body_line": "#A88F53",  # the body's centre line
}

# The axes of the 3D model view: x, y, z in the red, green, blue order
# every 3D tool uses. They draw geometry, not status.
AXIS_COLOURS = ("#D62728", "#2CA02C", "#1F77B4")


def ink_on(colour: str) -> str:
    """Black or white, whichever reads on a fill of ``colour`` (a colour
    the user picked, such as a 3D part's)."""
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#000000" if (r * 299 + g * 587 + b * 114) > 128000 else "#FFFFFF"


def swatch_style(colour: str) -> str:
    """The style sheet of a button that shows a colour the user picked
    (``#RRGGBB``), labelled in ink that reads on it."""
    return f"background-color: {colour}; color: {ink_on(colour)};"
