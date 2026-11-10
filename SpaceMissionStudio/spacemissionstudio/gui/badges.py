#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
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
