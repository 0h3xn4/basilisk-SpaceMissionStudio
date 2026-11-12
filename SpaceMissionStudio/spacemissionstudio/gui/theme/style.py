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

"""The application's style: Fusion, with what a style sheet cannot do.

Qt polishes each widget once as it is shown (again on a theme change);
:meth:`AppStyle.polish` then prepares the kinds that need more than the
style sheet:

- every :class:`QComboBox`: a readable, filterable list (theme/combo.py);
- every :class:`QDialog`: as tall as its wrapped text needs, so nothing
  is cut off (theme/dialogs.py).

Set by :func:`theme.apply_theme`; the style sheet goes on top of it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QProxyStyle, QStyle

from . import combo, dialogs


class AppStyle(QProxyStyle):
    """Fusion, with every combo box and dialog prepared (module docstring)."""

    def __init__(self) -> None:
        super().__init__("Fusion")

    def polish(self, arg):  # Qt's overloads: QWidget, QPalette or QApplication
        result = super().polish(arg)
        if isinstance(arg, QComboBox):
            combo.prepare(arg)
        elif isinstance(arg, QDialog):
            dialogs.prepare(arg)
        return result

    def styleHint(self, hint, option=None, widget=None, return_data=None):  # noqa: N802 -- Qt's name
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            return 0  # a list below the field, not a menu over it
        return super().styleHint(hint, option, widget, return_data)
