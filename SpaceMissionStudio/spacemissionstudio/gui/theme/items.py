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
"""Token colours on item-view items (list, tree and table rows).

An item's colour is set once, when the item is made; the style sheet does
not reach it. :func:`tint` records the token on the item and sets the
colour; :func:`retint` sets every recorded colour of a view again, in the
theme in use. A view that tints its items connects ``retint`` to the
theme's ``changed`` signal through a method of its own.
"""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem

from .state import PALETTE, TOKENS

# Where an item keeps its token names: one data role per kind of colour.
FOREGROUND_ROLE = int(Qt.ItemDataRole.UserRole) + 0x7E1
BACKGROUND_ROLE = int(Qt.ItemDataRole.UserRole) + 0x7E2


def _value(token: str) -> str:
    return TOKENS[token] if token in TOKENS else PALETTE[token]


def tint(item, foreground: str | None = None, background: str | None = None, column: int = 0) -> None:
    """Colour ``item``'s text (and background) with tokens (or role names);
    None leaves that colour unset. ``column`` is a tree item's column."""
    tree = isinstance(item, QTreeWidgetItem)
    for token, role, setter in ((foreground, FOREGROUND_ROLE, "setForeground"),
                                (background, BACKGROUND_ROLE, "setBackground")):
        if tree:
            item.setData(column, role, token)
            getattr(item, setter)(column, QBrush(QColor(_value(token))) if token else QBrush())
        else:
            item.setData(role, token)
            getattr(item, setter)(QBrush(QColor(_value(token))) if token else QBrush())


def _retint_item(item, column: int | None = None) -> None:
    for role, setter in ((FOREGROUND_ROLE, "setForeground"), (BACKGROUND_ROLE, "setBackground")):
        token = item.data(column, role) if column is not None else item.data(role)
        if token:
            if column is not None:
                getattr(item, setter)(column, QBrush(QColor(_value(token))))
            else:
                getattr(item, setter)(QBrush(QColor(_value(token))))


def retint(view) -> None:
    """Set the recorded token colours of every item of ``view`` again."""
    if isinstance(view, QTreeWidget):
        stack = [view.topLevelItem(i) for i in range(view.topLevelItemCount())]
        while stack:
            item = stack.pop()
            for column in range(view.columnCount()):
                _retint_item(item, column)
            stack.extend(item.child(i) for i in range(item.childCount()))
    elif isinstance(view, QListWidget):
        for row in range(view.count()):
            item: QListWidgetItem = view.item(row)
            _retint_item(item)
    elif isinstance(view, QTableWidget):
        for row in range(view.rowCount()):
            for column in range(view.columnCount()):
                cell: QTableWidgetItem | None = view.item(row, column)
                if cell is not None:
                    _retint_item(cell)
