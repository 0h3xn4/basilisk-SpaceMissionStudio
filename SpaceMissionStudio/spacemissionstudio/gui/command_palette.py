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
"""The command palette (UX/UI guidelines, "a command palette"; Ctrl+K):
every command of the window's action registry, every area and page, the
scenario's objects and the settings, found by typing a few letters of
their name.

Each word typed must appear in the entry or its keywords (a command's
older names: "events" finds the Timeline); entries whose name starts with
the first word come first. Enter runs the highlighted entry; a disabled
command is listed, greyed, and not run.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


@dataclass
class PaletteEntry:
    label: str  # e.g. "Run > Run"
    run: Callable[[], object]
    shortcut: str = ""
    enabled: bool = True
    keywords: str = ""  # other names it is found by, not shown


def command_entries(registry) -> list[PaletteEntry]:
    """One entry per command of ``registry`` (:class:`gui.actions.ActionRegistry`),
    named "Category > Command"."""
    return [PaletteEntry(f"{command.category} > {command.label}", command.action.trigger, command.keys,
                         command.action.isEnabled(), " ".join(command.keywords)) for command in registry]


def matches(query: str, entries: list[PaletteEntry]) -> list[PaletteEntry]:
    """Entries containing every word of ``query`` (any case) in their name
    or keywords; those whose command name starts with the first word first,
    then in order."""
    words = query.lower().split()
    if not words:
        return list(entries)
    found = [e for e in entries if all(w in f"{e.label} {e.keywords}".lower() for w in words)]
    return sorted(found, key=lambda e: not e.label.lower().rsplit("> ", 1)[-1].startswith(words[0]))


class CommandPalette(QDialog):
    """Type to filter, arrows to choose, Enter to run, Esc to close."""

    def __init__(self, entries: list[PaletteEntry], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.resize(520, 420)  # [px]
        self._entries = entries
        self.ran: PaletteEntry | None = None
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command, a page or an object, e.g. \"run\", \"save as\", \"sat-1\"")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill)
        self.search.returnPressed.connect(self.run_current)
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _item: self.run_current())
        layout.addWidget(self.list, 1)
        self.hint = QLabel("")
        layout.addWidget(self.hint)
        self.search.installEventFilter(self)
        self._fill("")

    def _fill(self, query: str) -> None:
        self.list.clear()
        for entry in matches(query, self._entries):
            item = QListWidgetItem(entry.label + (f"    {entry.shortcut}" if entry.shortcut else ""))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            if not entry.enabled:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("Not available right now.")
            self.list.addItem(item)
        first = next((i for i in range(self.list.count()) if self.list.item(i).flags() & Qt.ItemFlag.ItemIsEnabled),
                     None)
        if first is not None:
            self.list.setCurrentRow(first)
        self.hint.setText("" if self.list.count() else "Nothing matches.")

    def eventFilter(self, watched, event):  # noqa: N802 -- Qt API name
        """Up and Down in the search box move through the list."""
        if watched is self.search and event.type() == event.Type.KeyPress and \
                event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = -1 if event.key() == Qt.Key.Key_Up else 1
            row = self.list.currentRow()
            while 0 <= row + step < self.list.count():
                row += step
                if self.list.item(row).flags() & Qt.ItemFlag.ItemIsEnabled:
                    self.list.setCurrentRow(row)
                    break
            return True
        return super().eventFilter(watched, event)

    def run_current(self) -> None:
        item = self.list.currentItem()
        entry = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if entry is None or not entry.enabled:
            return
        self.ran = entry
        self.accept()
        entry.run()
