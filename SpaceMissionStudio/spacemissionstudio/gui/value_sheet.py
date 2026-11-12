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

"""ValueSheet: values laid out to be read, not a line of text.

A run of "a 6928.000 km, e 0.000000, i 97.5900 deg, RAAN ..." reads as
noise. A value sheet gives each quantity its own row: the name on the
left in the secondary tone, the number right-aligned in tabular figures
so digits line up, and the unit beside it. A title says what the values
are; a note under it says what the reader should know (a frame, a
source). Values can be selected and copied.

Use it wherever the GUI shows several values of one thing: a dialog that
compares two states, a summary, a popover. ``rows`` are
``(name, value, unit)``; an empty unit leaves the cell blank.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from .theme import SPACE, numeric_font, set_role

Row = tuple[str, str, str]


class ValueSheet(QWidget):
    """A titled sheet of ``(name, value, unit)`` rows (module docstring)."""

    def __init__(self, title: str = "", rows: Iterable[Row] = (), note: str = "", empty: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE["xs"])
        self.title_label = set_role(QLabel(title), role="heading")
        self.title_label.setVisible(bool(title))
        column.addWidget(self.title_label)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(SPACE["md"])
        self.grid.setVerticalSpacing(SPACE["xs"])
        column.addLayout(self.grid)
        self.empty_label = set_role(QLabel(empty), tone="secondary")
        column.addWidget(self.empty_label)
        self.note_label = set_role(QLabel(note), role="caption")
        self.note_label.setVisible(bool(note))
        column.addWidget(self.note_label)
        column.addStretch(1)
        self.rows: list[Row] = []
        self.set_rows(rows)

    def set_rows(self, rows: Iterable[Row]) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.rows = [tuple(row) for row in rows]
        for index, (name, value, unit) in enumerate(self.rows):
            name_label = set_role(QLabel(name), tone="secondary")
            value_label = QLabel(value)
            value_label.setFont(numeric_font("body"))
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            unit_label = set_role(QLabel(unit), tone="secondary")
            self.grid.addWidget(name_label, index, 0)
            self.grid.addWidget(value_label, index, 1)
            self.grid.addWidget(unit_label, index, 2)
        self.grid.setColumnStretch(3, 1)  # the room is left over on the right, values stay by their names
        self.empty_label.setVisible(not self.rows and bool(self.empty_label.text()))

    def value(self, name: str) -> str:
        """The value shown for ``name`` ("" when there is none)."""
        return next((value for row_name, value, _unit in self.rows if row_name == name), "")

    def text(self) -> str:
        """The sheet as plain lines, "name: value unit" (for copying, tests
        and screen readers)."""
        lines = [self.title_label.text()] if self.title_label.text() else []
        lines += [f"{name}: {value} {unit}".rstrip() for name, value, unit in self.rows]
        if not self.rows and self.empty_label.text():
            lines.append(self.empty_label.text())
        if self.note_label.text():
            lines.append(self.note_label.text())
        return "\n".join(lines)


class ValueTable(QWidget):
    """A small read-only table of values with a title: a header row in the
    caption style, numbers right-aligned in tabular figures, text left.
    For a matrix (an inertia tensor) or a handful of rows (principal
    axes); a long or sortable list is a :class:`gui.data_table.DataTable`.
    ``numeric`` names the columns (by index) that hold numbers."""

    def __init__(self, title: str, headers: list[str], rows: Iterable[Iterable[str]] = (),
                 numeric: Iterable[int] = (), note: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE["xs"])
        self.title_label = set_role(QLabel(title), role="heading")
        self.title_label.setVisible(bool(title))
        column.addWidget(self.title_label)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(SPACE["lg"])
        self.grid.setVerticalSpacing(SPACE["xs"])
        column.addLayout(self.grid)
        self.note_label = set_role(QLabel(note), role="caption")
        self.note_label.setVisible(bool(note))
        column.addWidget(self.note_label)
        self.headers = list(headers)
        self.numeric = set(numeric)
        self.rows: list[list[str]] = []
        self.set_rows(rows)

    def _align(self, index: int) -> Qt.AlignmentFlag:
        horizontal = Qt.AlignmentFlag.AlignRight if index in self.numeric else Qt.AlignmentFlag.AlignLeft
        return horizontal | Qt.AlignmentFlag.AlignVCenter

    def set_rows(self, rows: Iterable[Iterable[str]]) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.rows = [list(row) for row in rows]
        for index, header in enumerate(self.headers):
            label = set_role(QLabel(header), role="caption")
            label.setAlignment(self._align(index))
            self.grid.addWidget(label, 0, index)
        for row_index, row in enumerate(self.rows, start=1):
            for index, value in enumerate(row):
                label = QLabel(value)
                if index in self.numeric:
                    label.setFont(numeric_font("body"))
                elif index == 0:
                    set_role(label, tone="secondary")
                label.setAlignment(self._align(index))
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.grid.addWidget(label, row_index, index)
        self.grid.setColumnStretch(len(self.headers), 1)

    def text(self) -> str:
        """The table as tab-separated lines, with its title."""
        lines = [self.title_label.text()] if self.title_label.text() else []
        lines += ["\t".join(self.headers)] + ["\t".join(row) for row in self.rows]
        return "\n".join(lines)


class FoldSection(QWidget):
    """A titled part that starts folded: a disclosure button with the title,
    and the body under it once opened. For what a reader may want but need
    not see at first (a template's "What to look at", details of a
    finding): the screen shows the gist, the rest is one click away."""

    def __init__(self, title: str, body: QWidget, folded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QToolButton

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE["xs"])
        self.button = QToolButton()
        self.button.setText(title)
        self.button.setCheckable(True)
        self.button.setChecked(not folded)
        self.button.setAutoRaise(True)
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setAccessibleName(title)
        self.button.toggled.connect(self.set_open)
        column.addWidget(self.button)
        self.body = body
        column.addWidget(body)
        self.set_open(not folded)

    def set_open(self, opened: bool) -> None:
        self.button.blockSignals(True)
        self.button.setChecked(opened)
        self.button.blockSignals(False)
        self.button.setArrowType(Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow)
        self.body.setVisible(opened)

    def is_open(self) -> bool:
        return self.button.isChecked()
