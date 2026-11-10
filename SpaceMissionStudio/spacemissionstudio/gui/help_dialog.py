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
"""The user manual, shown from Help (the rail's last button, F1) without
a network (UX/UI guidelines, "help and examples built in"). The keyboard
shortcuts are a section of Settings (``gui.settings_page``) since M2a.

The manual is the copy shipped as package data (``spacemissionstudio/help/``,
kept current by ``scripts/sync_help.py``), rendered by Qt's own Markdown
support. Links inside the manual jump to their section; links to other
sites are not opened (the tool works offline) -- the address is shown
instead, for the user to open elsewhere if they wish.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QTextCursor
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout, QWidget

from .widgets import make_window

HELP_DIR = Path(__file__).resolve().parent.parent / "help"
MANUAL = HELP_DIR / "USER_MANUAL.md"


def heading_slug(text: str) -> str:
    """The anchor GitHub gives a heading: lower case, punctuation dropped,
    spaces to hyphens (the manual's table of contents uses these)."""
    slug = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return slug.replace(" ", "-")


class ManualDialog(QDialog):
    """The bundled user manual, in a window of its own
    (``widgets.show_window``)."""

    def __init__(self, parent: QWidget | None = None, manual: Path = MANUAL):
        super().__init__(parent)
        make_window(self)
        self.setWindowTitle("SpaceMissionStudio User Manual")
        self.resize(900, 760)  # [px]
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setSearchPaths([str(manual.parent)])
        self.browser.anchorClicked.connect(self._on_link)
        self.link_note = QLabel("")
        self.link_note.setWordWrap(True)
        self.link_note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
        layout.addWidget(self.link_note)
        layout.addWidget(buttons)
        try:
            self.browser.setMarkdown(manual.read_text(encoding="utf-8"))
        except OSError as exc:
            self.browser.setPlainText(f"The user manual could not be read ({exc}). It is USER_MANUAL.md in the "
                                      "SpaceMissionStudio folder of the source.")
        self._fit_images(manual.parent)
        self._anchors = self._heading_positions()

    def _fit_images(self, base: Path, max_width_px: int = 820) -> None:
        """Scale screenshots wider than ``max_width_px`` down, keeping their
        aspect, so the manual never scrolls sideways."""
        document = self.browser.document()
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isImageFormat():
                    image_format = fragment.charFormat().toImageFormat()
                    image = QImage(str(base / image_format.name()))
                    if not image.isNull() and image.width() > max_width_px:
                        image_format.setWidth(max_width_px)
                        image_format.setHeight(image.height() * max_width_px / image.width())
                        cursor = QTextCursor(document)
                        cursor.setPosition(fragment.position())
                        cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                        cursor.setCharFormat(image_format)
                iterator += 1
            block = block.next()

    def _heading_positions(self) -> dict[str, int]:
        positions = {}
        block = self.browser.document().begin()
        while block.isValid():
            if block.blockFormat().headingLevel() > 0:
                positions.setdefault(heading_slug(block.text()), block.position())
            block = block.next()
        return positions

    def show_section(self, slug: str) -> bool:
        """Scroll to the heading with this anchor; False when there is none."""
        position = self._anchors.get(slug)
        if position is None:
            return False
        cursor = QTextCursor(self.browser.document())
        cursor.setPosition(position)
        self.browser.setTextCursor(cursor)
        bar = self.browser.verticalScrollBar()
        bar.setValue(bar.value() + self.browser.cursorRect(cursor).top())  # heading at the top
        return True

    def _on_link(self, url: QUrl) -> None:
        if url.scheme() in ("http", "https", "mailto", "ftp"):
            self.link_note.setText(f"Links to other sites are not opened (SpaceMissionStudio works offline): "
                                   f"{url.toString()}")
            return
        if url.hasFragment() and self.show_section(url.fragment()):
            self.link_note.setText("")
            return
        self.link_note.setText(f"Not found in the manual: {url.toString()}")
