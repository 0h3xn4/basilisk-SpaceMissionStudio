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

"""A tree of pages (docs/ux-audit.md U-01): a tree on the left, the
selected node's page on the right. The Scenario Editor is built on it.

:class:`PageTree` holds the tree and a stack of pages. A node is a page, or
a group without a page of its own that shows its first child. A node can
carry a problem count, shown after its title. A page's widget can be any
widget; :meth:`PageTree.show_page` selects the node of any widget inside a
page, so ``MainWindow.show_view`` finds pages through it.

:func:`watch_edits` calls back on any edit in a form: a forms' fields'
change signals, and the ``changed`` signal of custom widgets.
:func:`embed_dialog` shows an editor dialog as a form inside a page.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterator, List, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLineEdit, QListWidget, QPlainTextEdit, QSplitter, QStackedWidget,
                               QTableWidget, QTreeWidget, QTreeWidgetItem, QWidget)

from .theme import PALETTE

_WIDGET_ROLE = Qt.ItemDataRole.UserRole
_TITLE_ROLE = Qt.ItemDataRole.UserRole + 1


class PageTree(QWidget):
    """A tree of nodes beside the page of the selected one."""

    page_shown = Signal(object)  # the page's widget

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setObjectName("pageTree")
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(170)  # [px]
        self.stack = QStackedWidget()
        self.stack.page_tree = self  # MainWindow.show_view finds pages through it
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([220, 900])  # [px]
        layout.addWidget(self.splitter)
        self.tree.currentItemChanged.connect(self._on_current_item)

    # -- building --------------------------------------------------------------------------------------------

    def add_page(self, title: str, widget: QWidget, parent: Optional[QTreeWidgetItem] = None,
                 index: Optional[int] = None) -> QTreeWidgetItem:
        """A node showing ``widget``, under ``parent`` (the top level when
        None), at ``index`` among its siblings (last when None)."""
        item = self._new_item(title, parent, index)
        item.setData(0, _WIDGET_ROLE, widget)
        self.stack.addWidget(widget)
        if self.tree.currentItem() is None:
            self.tree.setCurrentItem(item)
        return item

    def add_group(self, title: str, parent: Optional[QTreeWidgetItem] = None) -> QTreeWidgetItem:
        """A node without a page: selecting it shows its first child."""
        return self._new_item(title, parent, None)

    def _new_item(self, title: str, parent, index) -> QTreeWidgetItem:
        item = QTreeWidgetItem([title])
        item.setData(0, _TITLE_ROLE, title)
        owner = parent if parent is not None else self.tree.invisibleRootItem()
        owner.insertChild(owner.childCount() if index is None else index, item)
        if parent is not None:
            parent.setExpanded(True)
        return item

    def remove(self, item: QTreeWidgetItem) -> None:
        """Remove ``item`` and its children, and their pages from the stack
        (the pages are deleted)."""
        for child in [item.child(i) for i in range(item.childCount())]:
            self.remove(child)
        widget = item.data(0, _WIDGET_ROLE)
        if widget is not None:
            self.stack.removeWidget(widget)
            widget.deleteLater()
        owner = item.parent() or self.tree.invisibleRootItem()
        owner.removeChild(item)

    def set_title(self, item: QTreeWidgetItem, title: str) -> None:
        item.setData(0, _TITLE_ROLE, title)
        self._show_title(item)

    def set_problem_count(self, item: QTreeWidgetItem, count: int) -> None:
        """Show ``count`` problems after the node's title, in the error colour."""
        item.setData(0, Qt.ItemDataRole.UserRole + 2, count)
        self._show_title(item)

    def problem_count(self, item: QTreeWidgetItem) -> int:
        return item.data(0, Qt.ItemDataRole.UserRole + 2) or 0

    def _show_title(self, item: QTreeWidgetItem) -> None:
        title, count = item.data(0, _TITLE_ROLE), self.problem_count(item)
        item.setText(0, f"{title} ({count})" if count else title)
        item.setForeground(0, QBrush(QColor(PALETTE["danger_text"])) if count else QBrush())
        item.setToolTip(0, f"{count} problem{'s' if count != 1 else ''} here: see Problems" if count else "")

    # -- showing -----------------------------------------------------------------------------------------------

    def _on_current_item(self, item: Optional[QTreeWidgetItem], _previous) -> None:
        if item is None:
            return
        widget = item.data(0, _WIDGET_ROLE)
        if widget is None and item.childCount():
            self.tree.setCurrentItem(item.child(0))
            return
        if widget is not None:
            self.stack.setCurrentWidget(widget)
            self.page_shown.emit(widget)

    def item_of(self, widget: QWidget) -> Optional[QTreeWidgetItem]:
        """The node whose page is ``widget`` or holds it."""
        for item, page in self.items():
            if page is widget or page.isAncestorOf(widget):
                return item
        return None

    def show_page(self, widget: QWidget) -> bool:
        """Select the node of the page that is or holds ``widget``."""
        item = self.item_of(widget)
        if item is not None:
            self.tree.setCurrentItem(item)
        return item is not None

    def current_page(self) -> Optional[QWidget]:
        return self.stack.currentWidget()

    def items(self) -> Iterator[Tuple[QTreeWidgetItem, QWidget]]:
        """Every node with a page, and its page, in tree order."""
        def walk(item):
            for index in range(item.childCount()):
                child = item.child(index)
                widget = child.data(0, _WIDGET_ROLE)
                if widget is not None:
                    yield child, widget
                yield from walk(child)
        yield from walk(self.tree.invisibleRootItem())

    def paths(self) -> List[Tuple[str, QWidget]]:
        """``("Spacecraft > my-sat", page)`` for every page, in tree order."""
        result = []
        for item, widget in self.items():
            names, node = [], item
            while node is not None:
                names.insert(0, node.data(0, _TITLE_ROLE))
                node = node.parent()
            result.append((" > ".join(names), widget))
        return result


_EDIT_SIGNALS = (
    (QLineEdit, "textChanged"), (QPlainTextEdit, "textChanged"), (QAbstractSpinBox, "valueChanged"),
    (QComboBox, "currentIndexChanged"), (QAbstractButton, "toggled"), (QListWidget, "itemChanged"),
    (QTableWidget, "itemChanged"),
)


def watch_edits(root: QWidget, callback: Callable[[], None]) -> int:
    """Connect ``callback`` to every edit in ``root``'s form: its fields'
    change signals and its custom widgets' ``changed`` signals. Returns how
    many signals it connected. A spin box's own line edit is left out (its
    value signal covers it)."""
    connected = 0
    seen: Dict[int, bool] = {}
    for widget in [root, *root.findChildren(QWidget)]:
        if id(widget) in seen:
            continue
        seen[id(widget)] = True
        if isinstance(widget, QLineEdit) and isinstance(widget.parentWidget(), (QAbstractSpinBox, QComboBox)):
            continue
        custom = getattr(type(widget), "changed", None)
        if isinstance(custom, Signal) and widget is not root:
            widget.changed.connect(callback)
            connected += 1
            continue
        for cls, name in _EDIT_SIGNALS:
            if isinstance(widget, cls):
                signal = getattr(widget, name, None)
                if signal is not None:
                    try:
                        signal.connect(callback)
                    except TypeError:  # an overloaded signal (valueChanged[int]/[str] on some boxes)
                        continue
                    connected += 1
                break
    return connected


class _EscapeFilter(QObject):
    """An embedded dialog would close on Escape (QDialog.reject)."""

    def eventFilter(self, _watched, event):  # noqa: N802 -- Qt API name
        return event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape


def embed_dialog(dialog: QDialog) -> None:
    """Show ``dialog`` as a form inside a page: no window, no OK/Cancel."""
    dialog.setWindowFlags(Qt.WindowType.Widget)
    for box in dialog.findChildren(QDialogButtonBox):
        if box.parentWidget() is dialog:
            box.hide()
    # A page is narrower than the dialog's window was (the tree and the side
    # panel beside it, at 1280 px): a row too wide for it puts its field
    # under its label instead of scrolling sideways.
    for form in dialog.findChildren(QFormLayout):
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.invalidate()
    dialog._escape_filter = _EscapeFilter(dialog)
    dialog.installEventFilter(dialog._escape_filter)
