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
a group without a page of its own that shows its first child, or a section:
a part of its parent's page (a spacecraft's Orbit / mass or Attitude
control), which :attr:`PageTree.section_shown` asks the page to show. A node
can carry a problem count, shown after its title in the error colour, or in
the warning colour when all of them are warnings. A page's widget can be any
widget; :meth:`PageTree.show_page` selects the node of any widget inside a
page, a section's when the section's widget holds it, so
``MainWindow.show_view`` finds pages through it.

:func:`watch_edits` calls back on any edit in a form: a forms' fields'
change signals, and the ``changed`` signal of custom widgets.
:func:`embed_dialog` shows an editor dialog as a form inside a page.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterator, List, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLineEdit, QListWidget, QPlainTextEdit, QSplitter, QStackedWidget,
                               QTableWidget, QTreeWidget, QTreeWidgetItem, QWidget)

from .theme import PALETTE

_WIDGET_ROLE = Qt.ItemDataRole.UserRole
_TITLE_ROLE = Qt.ItemDataRole.UserRole + 1
_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
_SECTION_ROLE = Qt.ItemDataRole.UserRole + 3  # a section's key
_SECTION_WIDGET_ROLE = Qt.ItemDataRole.UserRole + 4  # the part of the page it shows, once there is one
_WARNINGS_ROLE = Qt.ItemDataRole.UserRole + 5  # how many of the count are warnings


class _UpKeys(QObject):
    """Whether the key being handled moves up the tree: a node without a
    page of its own then passes the selection on upwards, not back to its
    first child (else Up could never leave it)."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.up = False

    def eventFilter(self, _watched, event):  # noqa: N802 -- Qt API name
        if event.type() == QEvent.Type.KeyPress:
            self.up = event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_PageUp)
            QTimer.singleShot(0, self._clear)
        return False

    def _clear(self) -> None:
        self.up = False


class PageTree(QWidget):
    """A tree of nodes beside the page of the selected one."""

    page_shown = Signal(object)  # the page's widget
    section_shown = Signal(object, str)  # the page's widget and the section's key, after page_shown

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
        self._keys = _UpKeys(self)
        self.tree.installEventFilter(self._keys)

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

    def add_section(self, title: str, key: str, parent: QTreeWidgetItem) -> QTreeWidgetItem:
        """A node under the page node ``parent`` showing a part of its page:
        selecting it shows the page and emits :attr:`section_shown` with
        ``key``. Selecting ``parent`` shows its first section."""
        item = self._new_item(title, parent, None)
        item.setData(0, _WIDGET_ROLE, parent.data(0, _WIDGET_ROLE))
        item.setData(0, _SECTION_ROLE, key)
        item.setToolTip(0, title)  # a long title is cut at the tree's width
        return item

    def set_section_widget(self, item: QTreeWidgetItem, widget: Optional[QWidget]) -> None:
        """The widget that holds section ``item``'s part of the page, for
        :meth:`item_of`; None while the page has no such widget yet."""
        item.setData(0, _SECTION_WIDGET_ROLE, widget)

    @staticmethod
    def section_key(item: QTreeWidgetItem) -> Optional[str]:
        return item.data(0, _SECTION_ROLE)

    def sections(self, item: QTreeWidgetItem) -> List[QTreeWidgetItem]:
        """``item``'s section nodes, in order."""
        return [item.child(i) for i in range(item.childCount()) if self.section_key(item.child(i)) is not None]

    def show_section(self, page_item: QTreeWidgetItem, key: str) -> bool:
        """Select the section of ``page_item`` with ``key``."""
        section = next((s for s in self.sections(page_item) if self.section_key(s) == key), None)
        if section is not None:
            self.tree.setCurrentItem(section)
        return section is not None

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
        if widget is not None and self.section_key(item) is None:  # a section's page is its parent's
            self.stack.removeWidget(widget)
            widget.deleteLater()
        owner = item.parent() or self.tree.invisibleRootItem()
        owner.removeChild(item)

    def set_title(self, item: QTreeWidgetItem, title: str) -> None:
        item.setData(0, _TITLE_ROLE, title)
        self._show_title(item)

    def set_problem_count(self, item: QTreeWidgetItem, count: int, warnings: int = 0) -> None:
        """Show ``count`` problems after the node's title: in the error
        colour when one is an error, in the warning colour when all
        ``count`` are warnings (``warnings`` of them are)."""
        item.setData(0, _COUNT_ROLE, count)
        item.setData(0, _WARNINGS_ROLE, min(warnings, count))
        self._show_title(item)

    def problem_count(self, item: QTreeWidgetItem) -> int:
        return item.data(0, _COUNT_ROLE) or 0

    def warning_count(self, item: QTreeWidgetItem) -> int:
        return item.data(0, _WARNINGS_ROLE) or 0

    def _show_title(self, item: QTreeWidgetItem) -> None:
        title, count = item.data(0, _TITLE_ROLE), self.problem_count(item)
        warnings = self.warning_count(item)
        errors = count - warnings
        item.setText(0, f"{title} ({count})" if count else title)
        colour = PALETTE["danger_text"] if errors else PALETTE["warning"]
        item.setForeground(0, QBrush(QColor(colour)) if count else QBrush())
        parts = [f"{n} {word}{'s' if n != 1 else ''}" for n, word in ((errors, "error"), (warnings, "warning")) if n]
        tip = f"{' and '.join(parts)} here: see Problems" if count else ""
        if self.section_key(item) is not None:
            tip = f"{title}\n{tip}" if tip else title
        item.setToolTip(0, tip)

    # -- showing -----------------------------------------------------------------------------------------------

    def _on_current_item(self, item: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]) -> None:
        if item is None:
            return
        widget = item.data(0, _WIDGET_ROLE)
        # A group, or a page shown through its sections, passes the
        # selection on: down to its first child, up (a key moving up) to its
        # last, or above it when leaving it from inside.
        children = self.sections(item) or (
            [item.child(i) for i in range(item.childCount())] if widget is None else [])
        if children:
            if self._keys.up and _within(previous, item):
                above = self.tree.itemAbove(item)
                if above is not None:
                    self.tree.setCurrentItem(above)
                    return
            self.tree.setCurrentItem(children[-1] if self._keys.up else children[0])
            return
        if widget is not None:
            if item.parent() is not None:
                item.parent().setExpanded(True)  # a section of a closed node
            self.stack.setCurrentWidget(widget)
            self.page_shown.emit(widget)
            key = self.section_key(item)
            if key is not None:
                self.section_shown.emit(widget, key)

    def item_of(self, widget: QWidget) -> Optional[QTreeWidgetItem]:
        """The node whose page is ``widget`` or holds it: the section whose
        widget holds it, when there is one."""
        for item, page in self.items():
            if self.section_key(item) is None and (page is widget or page.isAncestorOf(widget)):
                for section in self.sections(item):
                    part = section.data(0, _SECTION_WIDGET_ROLE)
                    if part is not None and (part is widget or part.isAncestorOf(widget)):
                        return section
                return item
        return None

    def show_page(self, widget: QWidget) -> bool:
        """Select the node of the page that is or holds ``widget``."""
        item = self.item_of(widget)
        if item is not None:
            self.tree.setCurrentItem(item)
        return item is not None

    @staticmethod
    def page_of(item: QTreeWidgetItem) -> Optional[QWidget]:
        """The page node ``item`` shows (its parent's, for a section)."""
        return item.data(0, _WIDGET_ROLE)

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

    def paths(self) -> List[Tuple[str, QTreeWidgetItem]]:
        """``("Spacecraft > my-sat > Orbit / mass", node)`` for every node
        with a page, in tree order (select one with ``tree.setCurrentItem``)."""
        result = []
        for item, _widget in self.items():
            names, node = [], item
            while node is not None:
                names.insert(0, node.data(0, _TITLE_ROLE))
                node = node.parent()
            result.append((" > ".join(names), item))
        return result


def _within(item: Optional[QTreeWidgetItem], ancestor: QTreeWidgetItem) -> bool:
    """Whether ``item`` is below ``ancestor`` in the tree."""
    node = item.parent() if item is not None else None
    while node is not None:
        if node is ancestor:
            return True
        node = node.parent()
    return False


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
