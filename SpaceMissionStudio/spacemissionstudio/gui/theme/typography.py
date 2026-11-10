#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""Type, spacing and shape: the brief's scale, in pixels.

Inter for the interface, JetBrains Mono for numbers in tables, IDs, code
and logs. Sizes and weights are the only ones the GUI uses; spacing is on
a 4 px grid.
"""

from __future__ import annotations

UI_FONT_FAMILY = "Inter"
MONO_FONT_FAMILY = "JetBrains Mono"
# The CSS font stack of web views (plots): the bundled faces first.
WEB_FONT_STACK = "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif"
WEB_MONO_STACK = "'JetBrains Mono', ui-monospace, 'Cascadia Mono', monospace"

# Sizes [px].
SIZE = {
    "caption": 11,  # [px]
    "small": 12,  # [px] small text and table cells
    "body": 13,  # [px] the base size
    "section": 15,  # [px] section titles
    "page": 18,  # [px] page titles
    "display": 22,  # [px] rare
}
# Weights: regular, medium, semibold. Nothing else.
WEIGHT = {"regular": 400, "medium": 500, "semibold": 600}

# Spacing, the 4 px grid [px].
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}  # [px]
CONTROL_HEIGHT = {"compact": 28, "default": 32}  # [px]
ROW_HEIGHT = 26  # [px] table rows
RADIUS = {"control": 6, "panel": 8}  # [px] controls; panels, popovers and dialogs
FOCUS_RING = 2  # [px]
BORDER = 1  # [px]
ICON_SIZE = {"ui": 16, "rail": 20}  # [px]
# Motion: hover, panel open/close and toasts. Never data values or plots.
MOTION_MS = {"fast": 120, "slow": 180}  # [ms]

# The widest a form, a list editor or a page of reading text grows: at
# 2560 px its fields and buttons stretched to 1500 px, labels and values a
# head-turn apart. Plots, tables and the JSON view keep the full width.
CONTENT_MAX_WIDTH_PX = 960  # [px]
