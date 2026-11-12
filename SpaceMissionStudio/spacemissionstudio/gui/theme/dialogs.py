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

"""Dialogs never cut off their own text.

Qt does not size a window by the height its wrapped labels need at the
window's width: a dialog with a word-wrapped label gets the height the
label would need on a squarer layout, and when the window manager makes
it wider or narrower than that, or the fonts differ from where it was
laid out, the lines below the first and the buttons are cut off (the
orbit-type switch, reported 2026-11-12). :func:`prepare`, called for
every :class:`QDialog` as Qt polishes it (:class:`theme.style.AppStyle`),
watches the dialog: when it is shown or its width changes, its minimum
height becomes what its layout needs at that width, and it grows to it.
A minimum height the dialog's own code set stays the floor.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QDialog

_ORIGINAL_MIN = "smsOwnMinimumHeight"
_WIDTH = "smsFittedWidth"


def prepare(dialog: QDialog) -> None:
    if dialog.property(_ORIGINAL_MIN) is not None:
        return
    dialog.setProperty(_ORIGINAL_MIN, dialog.minimumHeight())
    dialog.installEventFilter(_FitFilter.instance())


def fit(dialog: QDialog) -> None:
    """Make ``dialog`` at least as tall as its layout needs at its width."""
    layout = dialog.layout()
    if layout is None or not layout.hasHeightForWidth():
        return
    width = dialog.width()
    dialog.setProperty(_WIDTH, width)
    needed = layout.totalHeightForWidth(width)
    floor = dialog.property(_ORIGINAL_MIN) or 0
    minimum = max(int(floor), needed)
    if dialog.minimumHeight() != minimum:
        dialog.setMinimumHeight(minimum)
    if dialog.height() < minimum:
        dialog.resize(width, minimum)


class _FitFilter(QObject):
    """One filter for every dialog, holding none of them."""

    _instance: _FitFilter | None = None

    @classmethod
    def instance(cls) -> _FitFilter:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def eventFilter(self, dialog, event) -> bool:  # noqa: N802 -- Qt's name
        kind = event.type()
        if kind == QEvent.Type.Show or (kind == QEvent.Type.Resize and dialog.property(_WIDTH) != dialog.width()):
            fit(dialog)
        return False
