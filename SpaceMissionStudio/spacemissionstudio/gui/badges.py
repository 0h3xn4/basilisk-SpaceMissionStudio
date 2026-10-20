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

"""Status badges: a small pill that says a state at a glance, its colour
from the status tokens (``theme/qss.py``'s ``[badge=...]`` rules) and its
text always written out, so colour is never the only cue. One look for
every badge in the app (the dashboard, the explainer, the Flight Software
and End of Life tabs), and a status colour means one thing everywhere.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .theme import set_role

# Badge kinds: the Astro UXDS statuses they stand for.
MUTED = "off"
SUCCESS = "normal"
DANGER = "critical"
ACCENT = "standby"
WARNING = "caution"
KINDS = (MUTED, SUCCESS, DANGER, ACCENT, WARNING, "serious")


def set_badge(widget: QWidget, kind: str) -> QWidget:
    """Show ``widget`` (a label or a button) as a badge of ``kind``."""
    if kind not in KINDS:
        raise ValueError(f"unknown badge kind {kind!r}")
    return set_role(widget, badge=kind)
