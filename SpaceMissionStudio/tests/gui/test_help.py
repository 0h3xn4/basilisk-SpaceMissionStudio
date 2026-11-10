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
#
"""The user manual and keyboard shortcuts in the Help menu, offline
(UX/UI guidelines, "help and examples built in")."""

import re
from pathlib import Path

from PySide6.QtCore import QUrl

_TOOL = Path(__file__).resolve().parents[2]


def test_the_bundled_manual_is_the_current_manual():
    """The package copy matches USER_MANUAL.md and its images (run scripts/sync_help.py after edits)."""
    from spacemissionstudio.gui.help_dialog import HELP_DIR

    text = (_TOOL / "USER_MANUAL.md").read_bytes()
    assert (HELP_DIR / "USER_MANUAL.md").read_bytes() == text
    for image in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text.decode("utf-8")):
        assert (HELP_DIR / image).read_bytes() == (_TOOL / image).read_bytes(), image


def test_every_contents_link_of_the_manual_finds_its_section(qtbot):
    """Each in-manual link (the table of contents) jumps to a heading."""
    from spacemissionstudio.gui.help_dialog import ManualDialog

    dialog = ManualDialog()
    qtbot.addWidget(dialog)
    text = (_TOOL / "USER_MANUAL.md").read_text(encoding="utf-8")
    anchors = re.findall(r"\]\(#([^)]+)\)", text)
    assert anchors
    for anchor in anchors:
        assert dialog.show_section(anchor), anchor


def test_links_to_other_sites_are_not_opened(qtbot, monkeypatch):
    """The dialog shows the address instead of opening a browser."""
    from PySide6.QtGui import QDesktopServices

    from spacemissionstudio.gui.help_dialog import ManualDialog

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    dialog = ManualDialog()
    qtbot.addWidget(dialog)
    dialog.browser.anchorClicked.emit(QUrl("https://example.org/page"))
    assert opened == []
    assert "not opened" in dialog.link_note.text() and "example.org" in dialog.link_note.text()


def test_help_offers_the_manual_on_f1_and_the_shortcuts(qtbot):
    """F1, and the rail's Help button, open the manual; the shortcut list
    includes Run (Ctrl+R)."""
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.manual_action.shortcut().toString() == "F1"
    assert window.shell.areas["help"].action is window.manual_action
    window.on_keyboard_shortcuts()
    table = window.settings_page.shortcuts_table
    shortcuts = {table.item(r, 2).text() for r in range(table.rowCount())}
    assert "Ctrl+R" in shortcuts and "F1" in shortcuts
