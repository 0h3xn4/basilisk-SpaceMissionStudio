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

"""Small colored pill/badge ``QLabel`` styling helper -- "at-a-glance
status, not prose". Extracted (Phase 6 audit fix) from
``mission_dashboard_widget.py``, where this was originally written as
that module's own private helper for template 19's live telemetry
panels; pulled out here so ``scenario_explainer_widget.py`` can reuse the
EXACT same visual language instead of inventing a second one, keeping
status-color meaning genuinely reserved/consistent app-wide (per the
``dataviz`` skill's own discipline: a color means one thing everywhere it
appears, never reused as decoration).

Pure Qt styling, no logic -- every badge kind maps to one fixed
``(background, foreground)`` pair of ``theme.PALETTE`` keys, applied via
:func:`badge_style`.
"""

from __future__ import annotations

from .theme import PALETTE

# Carbon tags: a fill with text of the same hue (gray, green, red, blue
# tags; warning uses the warning notification colours, Carbon having no
# yellow tag). Status colours keep their one meaning. Each is a pair of
# PALETTE keys, looked up when a badge is styled, so a badge takes the
# theme in use.
MUTED = ("selected", "text")  # gray tag
SUCCESS = ("tag_success_bg", "tag_success_text")  # green tag
DANGER = ("tag_danger_bg", "tag_danger_text")  # red tag
ACCENT = ("tag_accent_bg", "tag_accent_text")  # blue tag
WARNING = ("warning_soft", "warning")


def badge_style(colors: tuple) -> str:
    """The stylesheet of a badge in ``colors``: a pair of PALETTE keys (or
    of colours)."""
    bg, fg = (PALETTE.get(name, name) for name in colors)
    return f"background-color: {bg}; color: {fg}; border-radius: 10px; padding: 2px 10px;"
