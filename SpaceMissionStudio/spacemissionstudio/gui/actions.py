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

"""The main window's action registry, every command in one place (UI
overhaul plan §5.1).

A command is a :class:`QAction` with an id (``"file.save"``), a category
for the command palette ("File", "Run", ...), the area of the navigation
rail it belongs to, and old names the palette also finds it by. The
command palette, the shortcut list and every tooltip are generated from
here, so they cannot disagree. The window owns the actions, so their
shortcuts work from every area, with no menu bar.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QWidget

# The areas of the navigation rail (gui.shell), and "global" for commands
# that belong to the whole window (the palette, undo, the side panel).
AREAS = ("home", "scenario", "run", "results", "timeline", "reports", "settings", "help", "global")

Keys = Union[str, QKeySequence, QKeySequence.StandardKey]


@dataclass
class Command:
    """One registered command."""

    id: str
    action: QAction
    category: str  # the palette's group: "File", "Run", "View", ...
    area: str  # one of AREAS
    tip: str = ""  # what it does, without the shortcut
    keywords: Tuple[str, ...] = field(default_factory=tuple)  # older names the palette also matches

    @property
    def label(self) -> str:
        """The action's text without its mnemonic ampersand."""
        return self.action.text().replace("&", "")

    @property
    def keys(self) -> str:
        """Its first shortcut as shown ("Ctrl+S"): a standard key binds
        several on some platforms, the first is the one to learn."""
        return self.action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)


def tooltip_text(label: str, keys: str, tip: str) -> str:
    """ "Save (Ctrl+S)", then what it does on the next line."""
    title = f"{label} ({keys})" if keys else label
    return f"{title}\n{tip}" if tip else title


def _sequences(keys: Union[Keys, Sequence[Keys], None]) -> List[QKeySequence]:
    if keys is None:
        return []
    if isinstance(keys, (str, QKeySequence, QKeySequence.StandardKey)):
        keys = [keys]
    sequences: List[QKeySequence] = []
    for key in keys:
        if isinstance(key, QKeySequence.StandardKey):
            sequences.extend(QKeySequence.keyBindings(key))
        else:
            sequences.append(QKeySequence(key))
    return sequences


class ActionRegistry:
    """The window's commands, in the order they were added."""

    def __init__(self, owner: QWidget) -> None:
        # Weakly: the window holds the registry, and a cycle through the
        # window leaves it to the garbage collector, which may run only
        # after Qt WebEngine has shut down (a segfault at exit).
        self._owner = weakref.ref(owner)
        self._commands: Dict[str, Command] = {}

    def add(self, command_id: str, text: str, handler: Optional[Callable[..., object]] = None, *,
            category: str, area: str, tip: str = "", shortcut: Union[Keys, Sequence[Keys], None] = None,
            qicon: Optional[QIcon] = None, checkable: bool = False, checked: bool = False,
            keywords: Iterable[str] = (), action: Optional[QAction] = None,
            on_window: bool = True) -> QAction:
        """Register a command and return its action: a new :class:`QAction`
        owned by the window, or ``action`` (for one Qt makes, such as a
        dock's toggle, or a view's own). ``handler`` is connected to
        ``triggered``, or to ``toggled`` for a checkable action.
        ``on_window`` False leaves a view's action where it is, so its
        shortcut keeps working only inside that view."""
        if command_id in self._commands:
            raise ValueError(f"command {command_id!r} is registered twice")
        if area not in AREAS:
            raise ValueError(f"unknown area {area!r}")
        owner = self._owner()
        if action is None:
            action = QAction(text, owner)
        else:
            action.setText(text)
        if qicon is not None:
            action.setIcon(qicon)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        sequences = _sequences(shortcut)
        if sequences:
            action.setShortcuts(sequences)
        action.setObjectName(command_id)
        if handler is not None:
            (action.toggled if checkable else action.triggered).connect(handler)
        if on_window:
            # On the window, so the shortcut works in every area with no menu bar.
            owner.addAction(action)
        command = Command(command_id, action, category, area, tip, tuple(keywords))
        self._commands[command_id] = command
        self.refresh_tooltip(command_id)
        return action

    def refresh_tooltip(self, command_id: str, tip: Optional[str] = None) -> None:
        """Write the tooltip again from the label, shortcut and ``tip`` (the
        stored one when None), e.g. after the text changed."""
        command = self._commands[command_id]
        if tip is not None:
            command.tip = tip
        command.action.setToolTip(tooltip_text(command.label, command.keys, command.tip))

    def __contains__(self, command_id: str) -> bool:
        return command_id in self._commands

    def __getitem__(self, command_id: str) -> Command:
        return self._commands[command_id]

    def __iter__(self) -> Iterator[Command]:
        return iter(self._commands.values())

    def action(self, command_id: str) -> QAction:
        return self._commands[command_id].action

    def command_of(self, action: QAction) -> Optional[Command]:
        return next((command for command in self if command.action is action), None)

    def in_area(self, area: str) -> List[Command]:
        return [command for command in self if command.area == area]

    def shortcut_rows(self) -> List[Tuple[str, str, str]]:
        """(category, command, shortcut) of every command with a shortcut,
        by category, each category's commands in the order they were added:
        the Keyboard list in Settings."""
        rows = [(command.category, command.label, command.keys) for command in self if command.keys]
        return sorted(rows, key=lambda row: row[0])
