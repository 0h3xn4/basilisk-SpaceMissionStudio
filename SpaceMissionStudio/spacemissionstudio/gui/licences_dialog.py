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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
"""Help › Third-Party Licences: the app's licence (EUPL-1.2, in English and
German) and the notices of everything the package redistributes, each in a
tab, read-only and selectable, from the files ``spacemissionstudio.legal``
finds. A window of its own (``widgets.show_window``), like the manual; the
texts are read when the window opens, not when the app starts."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget

from .. import legal
from .theme import mono_font
from .widgets import make_window


class LicencesDialog(QDialog):
    """One tab per licence file found; a note when none is (a broken install)."""

    def __init__(self, parent: QWidget | None = None, files: list[legal.LicenceFile] | None = None):
        super().__init__(parent)
        make_window(self)
        self.setWindowTitle("Third-Party Licences")
        self.resize(820, 680)  # [px]
        self.tabs = QTabWidget()
        files = legal.licence_files() if files is None else files
        for entry in files:
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setFont(mono_font())
            view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            try:
                view.setPlainText(entry.path.read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                view.setPlainText(f"{entry.path} could not be read ({exc}).")
            self.tabs.addTab(view, entry.title)
        if not files:
            note = QPlainTextEdit()
            note.setReadOnly(True)
            note.setPlainText("No licence files were found in this installation. They are LICENSE, LICENSE.de and "
                              "THIRD_PARTY_NOTICES in the SpaceMissionStudio folder of the source.")
            self.tabs.addTab(note, "Licences")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)
