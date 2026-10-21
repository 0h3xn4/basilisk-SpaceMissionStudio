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

"""The Settings area (UI overhaul plan §5.2): appearance, reference data,
layout, the keyboard shortcuts and about, each a section of one page.

Every control is a command of the window's action registry
(:mod:`gui.actions`), shown here as a button, and the shortcut list is
generated from the registry, so this page and the command palette agree.
"""

from __future__ import annotations

import weakref
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QScrollArea, QTableWidget, QTableWidgetItem,
                               QToolButton, QVBoxLayout, QWidget)

from .theme import CONTENT_MAX_WIDTH_PX, SPACE, set_role

# (key, title, what it is for)
_SECTIONS: Tuple[Tuple[str, str, str], ...] = (
    ("appearance", "Appearance", "The theme applies at once, to every open view."),
    ("reference_data", "Reference data", "The SPICE kernels, gravity fields, magnetic model, space weather and "
                                         "Earth orientation files, with their sources, dates and checksums."),
    ("layout", "Layout", "The navigation rail, the inspector and the Problems panel; Reset Layout puts them "
                         "back as a new window has them."),
    ("keyboard", "Keyboard", "Every command with a shortcut. Ctrl+K finds any command by name."),
    ("about", "About", ""),
)


class SettingsPage(QScrollArea):
    """The settings, one section under the other."""

    def __init__(self, commands, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Weakly: the registry holds the window, and a child holding the
        # window would keep it alive once closed (test_a_closed_window_is_freed).
        self._commands = weakref.ref(commands)
        self.setWidgetResizable(True)
        body = QWidget()
        body.setMaximumWidth(CONTENT_MAX_WIDTH_PX)
        self.setWidget(body)
        self._layout = QVBoxLayout(body)
        self._layout.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        self._layout.setSpacing(SPACE["sm"])
        self.section_titles: Dict[str, QLabel] = {}
        self.buttons: Dict[str, QToolButton] = {}
        for key, title, text in _SECTIONS:
            if self.section_titles:
                self._layout.addSpacing(SPACE["lg"])
            heading = set_role(QLabel(title), role="section-title")
            heading.setObjectName(f"settings_{key}")
            self.section_titles[key] = heading
            self._layout.addWidget(heading)
            if text:
                self._layout.addWidget(set_role(QLabel(text), tone="secondary"))
            getattr(self, f"_build_{key}")()
        self._layout.addStretch(1)

    def sections(self) -> List[Tuple[str, str]]:
        """(key, title) of each section, in order."""
        return [(key, title) for key, title, _text in _SECTIONS]

    def show_section(self, key: str) -> None:
        """Scroll ``key``'s section to the top and refresh what it lists."""
        if key == "keyboard":
            self.refresh_shortcuts()
        heading = self.section_titles[key]
        self.verticalScrollBar().setValue(heading.y() - SPACE["sm"])

    def _row(self, command_ids: Tuple[str, ...]) -> None:
        row = QHBoxLayout()
        row.setSpacing(SPACE["xs"])
        for command_id in command_ids:
            row.addWidget(self._button(self._commands().action(command_id)))
        row.addStretch(1)
        self._layout.addLayout(row)

    def _button(self, action: QAction) -> QToolButton:
        button = QToolButton()
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.buttons[action.objectName()] = button
        return button

    def _build_appearance(self) -> None:
        self._row(("view.theme.system", "view.theme.light", "view.theme.dark"))

    def _build_reference_data(self) -> None:
        self._row(("tools.reference_data",))

    def _build_layout(self) -> None:
        self._row(("view.rail_icons", "view.inspector", "view.problems", "view.reset_layout"))

    def _build_keyboard(self) -> None:
        self.shortcuts_table = QTableWidget(0, 3)
        self.shortcuts_table.setHorizontalHeaderLabels(["Category", "Command", "Shortcut"])
        self.shortcuts_table.verticalHeader().setVisible(False)
        self.shortcuts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.shortcuts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.shortcuts_table.horizontalHeader().setStretchLastSection(True)
        self._layout.addWidget(self.shortcuts_table)
        self.refresh_shortcuts()

    def refresh_shortcuts(self) -> None:
        """The table again from the registry."""
        commands = self._commands()
        rows = commands.shortcut_rows() if commands is not None else []
        table = self.shortcuts_table
        table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        # Every row in view: the page scrolls, not the table.
        height = table.horizontalHeader().height() + sum(table.rowHeight(r) for r in range(len(rows)))
        table.setFixedHeight(height + 2 * table.frameWidth())

    def _build_about(self) -> None:
        import spacemissionstudio

        self.version_label = set_role(QLabel(f"SpaceMissionStudio {spacemissionstudio.__version__}"), role="strong")
        self._layout.addWidget(self.version_label)
        self._row(("help.about", "help.manual"))
