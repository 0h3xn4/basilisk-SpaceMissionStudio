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

"""The Results plot catalog (docs/ux-audit.md U-24): every plot of a run,
grouped (Orbit, Attitude, Power, Link, ... from
:func:`plot_categories.plot_group`), with a search box.

A tick shows the plot in the grid, and clearing it takes it out;
clicking a plot's name shows it in the selected cell instead
(:attr:`PlotCatalog.activated`), as does Enter in the search box (the
first plot it leaves, or the one whose title or code name was typed in
full). Entries are the series' code names (the
CSV file names); the text is the plot's title, and the tooltip the code
name. :data:`ACCESS_TIMELINE` is the one entry that is not a series: the
ground-station access timeline, offered under Link when the run has
passes.
"""

from __future__ import annotations


from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..plot_categories import PLOT_GROUPS

ACCESS_TIMELINE = "@access_timeline"  # the catalog entry of the ground-station access timeline
_NAME_ROLE = Qt.ItemDataRole.UserRole


class PlotCatalog(QWidget):
    """Grouped, searchable list of a run's plots with a tick for each shown one."""

    activated = Signal(str)  # a plot's name was clicked: show it in the selected cell
    toggled = Signal(str, bool)  # a plot's tick changed (by the user)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search plots")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search plots")
        self.search.textChanged.connect(self._filter)
        # Enter shows the first plot the search leaves (type a title or a
        # code name, press Enter -- as the old series box allowed).
        self.search.returnPressed.connect(self._on_search_entered)
        layout.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAccessibleName("Plot catalog")
        self.tree.setUniformRowHeights(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemActivated.connect(self._on_item_activated)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree, 1)
        self._items: dict[str, QTreeWidgetItem] = {}
        self._filling = False
        self._just_toggled: QTreeWidgetItem | None = None  # the tick box this click changed

    # -- contents ----------------------------------------------------------

    def set_entries(self, entries: list[tuple], shown: list[str]) -> None:
        """``entries``: ``(name, label, group)`` in the order to list them
        within a group; ``shown``: the names ticked."""
        self._filling = True
        try:
            self.tree.clear()
            self._items = {}
            groups: dict[str, QTreeWidgetItem] = {}
            order = {group: index for index, group in enumerate(PLOT_GROUPS)}
            for name, label, group in sorted(entries, key=lambda entry: order.get(entry[2], len(order))):
                parent = groups.get(group)
                if parent is None:
                    parent = QTreeWidgetItem(self.tree, [group])
                    parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    font = parent.font(0)
                    font.setBold(True)
                    parent.setFont(0, font)
                    groups[group] = parent
                item = QTreeWidgetItem(parent, [label])
                item.setData(0, _NAME_ROLE, name)
                item.setToolTip(0, name if name != ACCESS_TIMELINE else "Every ground station's passes in one chart")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if name in shown else Qt.CheckState.Unchecked)
                self._items[name] = item
            for group, parent in groups.items():
                parent.setText(0, f"{group} ({parent.childCount()})")
            self.tree.expandAll()
        finally:
            self._filling = False
        self._filter(self.search.text())

    def names(self) -> list[str]:
        """Every entry's name, in catalog order."""
        return list(self._items)

    def label(self, name: str) -> str:
        item = self._items.get(name)
        return item.text(0) if item is not None else name

    def set_shown(self, shown: list[str]) -> None:
        """Tick exactly ``shown`` (no :attr:`toggled` signals)."""
        self._filling = True
        try:
            for name, item in self._items.items():
                item.setCheckState(0, Qt.CheckState.Checked if name in shown else Qt.CheckState.Unchecked)
        finally:
            self._filling = False

    def select(self, name: str) -> None:
        """Highlight ``name``'s entry (the selected cell's plot) and scroll to it."""
        item = self._items.get(name)
        if item is not None:
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)

    # -- search ------------------------------------------------------------

    def _filter(self, text: str) -> None:
        words = text.lower().split()
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            group_text = group.text(0).lower()
            visible = 0
            for child_index in range(group.childCount()):
                child = group.child(child_index)
                haystack = f"{child.text(0)} {child.data(0, _NAME_ROLE)} {group_text}".lower()
                hidden = not all(word in haystack for word in words)
                child.setHidden(hidden)
                visible += not hidden
            group.setHidden(visible == 0)

    def _on_search_entered(self) -> None:
        visible = self.visible_names()
        exact = [name for name in visible if self.search.text().strip() in (name, self.label(name))]
        if visible:
            self.activated.emit((exact or visible)[0])

    def visible_names(self) -> list[str]:
        """The entries the search leaves shown."""
        return [name for name, item in self._items.items() if not item.isHidden() and not item.parent().isHidden()]

    # -- signals -----------------------------------------------------------

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        name = item.data(0, _NAME_ROLE)
        if not self._filling and name:
            self._just_toggled = item
            # A tick by keyboard (Space) brings no click: forget it once this event is done.
            QTimer.singleShot(0, self._forget_toggle)
            self.toggled.emit(name, item.checkState(0) == Qt.CheckState.Checked)

    def _forget_toggle(self) -> None:
        self._just_toggled = None

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        # A click on the name shows the plot. A click on the tick box only
        # ticks it: Qt changes the check state first (itemChanged), then
        # reports the click, so that click is skipped here.
        if self._just_toggled is item:
            self._just_toggled = None
            return
        name = item.data(0, _NAME_ROLE)
        if name:
            self.activated.emit(name)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        self._on_item_activated(item, column)
