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

"""SpacecraftTemplateDialog: pick one of
:data:`engine.spacecraft_templates.SPACECRAFT_TEMPLATES` by name, with its
description shown alongside. Does not import
``engine.spacecraft_templates`` beyond the template list/dataclass itself
-- no Basilisk anywhere in that chain (see that module's docstring),
consistent with this project's "gui/ doesn't need to know engine/ imports
Basilisk" split used elsewhere (e.g. ``constellation_dialog.py``).

Only collects the CHOICE -- :meth:`selected_template`'s ``.build()``
still needs calling by the caller (``gui.spacecraft_editor.
SpacecraftListWidget._on_new_from_template``), which then opens the
ordinary :class:`SpacecraftEditorDialog` on the built config so the user
sets the actual name/orbit/anything else there, same as "Add..."/"Edit...".
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..engine.spacecraft_templates import SPACECRAFT_TEMPLATES, SpacecraftTemplate
from .theme import set_role


class SpacecraftTemplateDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("New spacecraft from template")
        self.resize(520, 320)

        layout = QVBoxLayout(self)
        description_label = QLabel(
            "Start a new spacecraft from a physically-reasonable preset instead of a blank default -- "
            "you can adjust everything (including the orbit) in the editor that opens next."
        )
        # See phasing_formation_dialog.py's identical fix (same
        # copy-pasted top-description-QLabel shape, same missing
        # word-wrap) for the real screenshot that found this bug.
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        body = QHBoxLayout()
        self.list_widget = QListWidget()
        for template in SPACECRAFT_TEMPLATES:
            self.list_widget.addItem(QListWidgetItem(template.name))
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        # Wide enough for the longest preset name: at an even 50/50 split
        # the first name overflowed and the list grew a horizontal scrollbar.
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setMinimumWidth(self.list_widget.sizeHintForColumn(0) + 2 * self.list_widget.frameWidth()
                                         + 16)
        body.addWidget(self.list_widget, stretch=1)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        set_role(self.description_label, tone="secondary")
        body.addWidget(self.description_label, stretch=1)
        layout.addLayout(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if SPACECRAFT_TEMPLATES:
            self.list_widget.setCurrentRow(0)

    def _on_selection_changed(self, row: int) -> None:
        if 0 <= row < len(SPACECRAFT_TEMPLATES):
            self.description_label.setText(SPACECRAFT_TEMPLATES[row].description)
        else:
            self.description_label.setText("")

    def selected_template(self) -> SpacecraftTemplate | None:
        row = self.list_widget.currentRow()
        if 0 <= row < len(SPACECRAFT_TEMPLATES):
            return SPACECRAFT_TEMPLATES[row]
        return None
