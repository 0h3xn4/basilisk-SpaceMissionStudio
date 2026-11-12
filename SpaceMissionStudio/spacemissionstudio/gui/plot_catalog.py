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

from ..plot_categories import PLOT_GROUPS, catalog_path

def _leaf_names(item: QTreeWidgetItem) -> list[str]:
    names = []
    for index in range(item.childCount()):
        child = item.child(index)
        name = child.data(0, _NAME_ROLE)
        names += [name] if name else _leaf_names(child)
    return names


def _leaf_count(item: QTreeWidgetItem) -> int:
    return len(_leaf_names(item))


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
        within a group; ``shown``: the names ticked. The entries nest by
        :func:`plot_categories.catalog_path`: topic, spacecraft (when the run
        has several), group of related plots, plot."""
        self._filling = True
        try:
            self.tree.clear()
            self._items = {}
            self._labels = {}
            paths = [(name, label, catalog_path(name, label, group)) for name, label, group in entries]
            several = len({path[1] for _name, _label, path in paths if path[1] is not None}) > 1
            # A group named as its topic ("Sensors" under Sensors), or of one
            # plot, adds a level and says nothing: its plots sit one up.
            sizes: dict[tuple, int] = {}
            for _name, _label, (topic, spacecraft, subgroup, _title) in paths:
                sizes[(topic, spacecraft, subgroup)] = sizes.get((topic, spacecraft, subgroup), 0) + 1
            paths = [(name, label, (topic, spacecraft,
                                    None if subgroup in (None, topic) or sizes[(topic, spacecraft, subgroup)] < 2
                                    else subgroup, title))
                     for name, label, (topic, spacecraft, subgroup, title) in paths]
            order = {group: index for index, group in enumerate(PLOT_GROUPS)}
            nodes: dict[tuple, QTreeWidgetItem] = {}
            spacecraft_nodes: set = set()

            def node(key: tuple, text: str, parent) -> QTreeWidgetItem:
                item = nodes.get(key)
                if item is None:
                    item = QTreeWidgetItem(parent if parent is not None else self.tree, [text])
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    nodes[key] = item
                return item

            for name, label, (topic, spacecraft, subgroup, title) in sorted(
                    paths, key=lambda entry: order.get(entry[2][0], len(order))):
                parent = node((topic,), topic, None)
                key = (topic,)
                if several and spacecraft is not None:
                    key += (spacecraft,)
                    parent = node(key, spacecraft, parent)
                    spacecraft_nodes.add(key)
                if subgroup is not None:
                    key += (subgroup,)
                    parent = node(key, subgroup, parent)
                item = QTreeWidgetItem(parent, [title])
                item.setData(0, _NAME_ROLE, name)
                item.setToolTip(0, name if name != ACCESS_TIMELINE else "Every ground station's passes in one chart")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if name in shown else Qt.CheckState.Unchecked)
                self._items[name] = item
                self._labels[name] = label
            for key, item in nodes.items():
                count = _leaf_count(item)
                item.setText(0, f"{item.text(0)} ({count})")
                if len(key) == 1:
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                # Topics and spacecraft open; a group of related plots opens
                # only when one of its plots is shown.
                item.setExpanded(len(key) == 1 or key in spacecraft_nodes
                                 or any(name in shown for name in _leaf_names(item)))
        finally:
            self._filling = False
        self._filter(self.search.text())

    def names(self) -> list[str]:
        """Every entry's name, in catalog order."""
        return list(self._items)

    def label(self, name: str) -> str:
        """The plot's whole title (the tree shows only what its parents leave)."""
        return getattr(self, "_labels", {}).get(name, name)

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

        def visit(item: QTreeWidgetItem, context: str) -> int:
            name = item.data(0, _NAME_ROLE)
            if name:
                haystack = f"{item.text(0)} {self.label(name)} {name} {context}".lower()
                hidden = not all(word in haystack for word in words)
                item.setHidden(hidden)
                return 0 if hidden else 1
            shown = sum(visit(item.child(i), f"{context} {item.text(0)}") for i in range(item.childCount()))
            item.setHidden(shown == 0)
            if words and shown:
                item.setExpanded(True)  # a search shows where its matches are
            return shown

        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index), "")

    def _on_search_entered(self) -> None:
        visible = self.visible_names()
        exact = [name for name in visible if self.search.text().strip() in (name, self.label(name))]
        if visible:
            self.activated.emit((exact or visible)[0])

    def visible_names(self) -> list[str]:
        """The entries the search leaves shown."""
        def shown(item) -> bool:
            while item is not None:
                if item.isHidden():
                    return False
                item = item.parent()
            return True

        return [name for name, item in self._items.items() if shown(item)]

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
