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

"""The window's navigation (UI overhaul plan §5.1): a rail of areas on the
left and the area shown beside it.

* :class:`NavRail`: one button per area, icon and label, collapsible to
  icons only. Settings and Help sit at its bottom.
* :class:`AreaPage`: an area's page, a header (its title and the
  commands of the area) over the screen it hosts.
* :class:`AreaStack`: the pages, one shown at a time.
* :class:`Shell`: the rail and the stack. :meth:`Shell.register` adds an
  area, so a later area (Operations) is one more call, with no change to
  the shell.

The shell only shows and switches; the window decides what each area
holds (``MainWindow``).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from .flow_layout import FlowLayout
from .theme import ICON_SIZE, SPACE, icon, set_role


@dataclass
class Area:
    """One area of the rail."""

    id: str
    label: str
    icon: str  # a bundled Lucide icon
    order: int
    page: AreaPage | None  # None: a button that runs ``action`` instead of showing a page (Help)
    bottom: bool = False  # pinned at the rail's bottom (Settings, Help)
    action: QAction | None = None


class AreaPage(QWidget):
    """An area's page: a header with the title and the area's commands,
    over ``content``, the screen it hosts unchanged."""

    def __init__(self, area_id: str, title: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.area_id = area_id
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = QFrame()
        self.header.setObjectName("areaHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(SPACE["lg"], SPACE["sm"], SPACE["lg"], SPACE["sm"])
        header_layout.setSpacing(SPACE["md"])
        self.title_label = set_role(QLabel(title), role="page-title")
        header_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignTop)
        self._buttons = QWidget()
        self._buttons_layout = FlowLayout(self._buttons, spacing=SPACE["xs"])
        header_layout.addWidget(self._buttons, 1)
        self.buttons: dict[QAction, QToolButton] = {}
        self.header.setVisible(False)  # shown once it has a command
        layout.addWidget(self.header)
        layout.addWidget(content, 1)

    def add_command(self, action: QAction, primary: bool = False) -> QToolButton:
        """A button for ``action`` in the header: its text, icon and
        enabled state follow the action."""
        button = QToolButton()
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        if primary:
            button.setObjectName("primaryToolButton")
        self._buttons_layout.addWidget(button)
        self.buttons[action] = button
        self.header.setVisible(True)
        return button

    def add_widget(self, widget: QWidget) -> None:
        """A control of the area's own in the header (the run mode button)."""
        self._buttons_layout.addWidget(widget)
        self.header.setVisible(True)


class AreaStack(QStackedWidget):
    """The areas' pages; :meth:`MainWindow.show_view` walks up to it."""


class NavRail(QFrame):
    """The areas as buttons, top to bottom; the collapse button last."""

    area_chosen = Signal(str)
    collapsed_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navRail")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACE["xs"], SPACE["sm"], SPACE["xs"], SPACE["sm"])
        self._layout.setSpacing(SPACE["xs"])
        self._top = QVBoxLayout()
        self._top.setSpacing(SPACE["xs"])
        self._bottom = QVBoxLayout()
        self._bottom.setSpacing(SPACE["xs"])
        self._layout.addLayout(self._top)
        self._layout.addStretch(1)
        self._layout.addLayout(self._bottom)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        self._labels: dict[str, str] = {}
        self._keys: dict[str, str] = {}
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("railCollapseButton")
        self.collapse_button.setAutoRaise(True)
        self.collapse_button.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        self._layout.addWidget(self.collapse_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.collapsed = False
        self._show_collapse_state()

    def add_area(self, area: Area, keys: str = "", index: int = -1) -> QToolButton:
        """A button for ``area`` at ``index`` of its group (top or bottom;
        last when -1)."""
        button = QToolButton()
        button.setObjectName("railButton")
        button.setIcon(icon(area.icon, "text.secondary"))
        button.setIconSize(QSize(ICON_SIZE["rail"], ICON_SIZE["rail"]))
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._labels[area.id] = area.label
        self._keys[area.id] = keys
        if area.page is not None:
            button.setCheckable(True)
            self.group.addButton(button)
            button.clicked.connect(lambda _checked=False, area_id=area.id: self.area_chosen.emit(area_id))
        elif area.action is not None:
            button.clicked.connect(area.action.trigger)
        (self._bottom if area.bottom else self._top).insertWidget(index, button)
        self.buttons[area.id] = button
        self._show_label(area.id)
        return button

    def set_current(self, area_id: str) -> None:
        button = self.buttons.get(area_id)
        if button is not None and button.isCheckable():
            button.setChecked(True)

    def current(self) -> str | None:
        return next((area_id for area_id, button in self.buttons.items() if button.isChecked()), None)

    def set_collapsed(self, collapsed: bool) -> None:
        """Icons only (``collapsed``) or icon and label."""
        if collapsed == self.collapsed:
            return
        self.collapsed = collapsed
        for area_id in self.buttons:
            self._show_label(area_id)
        self._show_collapse_state()
        self.collapsed_changed.emit(collapsed)

    def _show_label(self, area_id: str) -> None:
        button, label, keys = self.buttons[area_id], self._labels[area_id], self._keys[area_id]
        button.setText(label)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly if self.collapsed
                                  else Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setToolTip(f"{label} ({keys})" if keys else label)
        button.setAccessibleName(label)

    def _show_collapse_state(self) -> None:
        name = "panel-left-open" if self.collapsed else "panel-left-close"
        self.collapse_button.setIcon(icon(name, "text.secondary"))
        text = "Show the area names" if self.collapsed else "Icons only"
        self.collapse_button.setToolTip(text)
        self.collapse_button.setAccessibleName(text)


class Shell(QWidget):
    """The rail and the areas. ``area_changed`` says which is shown."""

    area_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.rail = NavRail()
        self.stack = AreaStack()
        layout.addWidget(self.rail)
        self.work = QWidget()  # the window puts its top bar and banners above the stack
        self.work_layout = QVBoxLayout(self.work)
        self.work_layout.setContentsMargins(0, 0, 0, 0)
        self.work_layout.setSpacing(0)
        self.work_layout.addWidget(self.stack, 1)
        layout.addWidget(self.work, 1)
        self.areas: dict[str, Area] = {}
        self.rail.area_chosen.connect(self.show_area)
        self.stack.currentChanged.connect(self._on_current_changed)

    def register(self, area_id: str, icon_name: str, label: str, content: QWidget | None, order: int,
                 bottom: bool = False, action: QAction | None = None, keys: str = "") -> Area:
        """Add an area: ``content`` is the screen it hosts (None for a
        button that triggers ``action``); ``order`` places it on the rail;
        ``keys`` is the shortcut shown in its tooltip."""
        if area_id in self.areas:
            raise ValueError(f"area {area_id!r} is registered twice")
        page = AreaPage(area_id, label, content) if content is not None else None
        area = Area(area_id, label, icon_name, order, page, bottom, action)
        self.areas[area_id] = area
        if page is not None:
            self.stack.addWidget(page)
        # In its place among the areas of its group: a later area slots in.
        index = sum(1 for other in self.areas.values()
                    if other.bottom == bottom and other.order < order)
        self.rail.add_area(area, keys, index)
        return area

    def page(self, area_id: str) -> AreaPage:
        page = self.areas[area_id].page
        if page is None:
            raise KeyError(f"area {area_id!r} has no page")
        return page

    def show_area(self, area_id: str) -> None:
        self.stack.setCurrentWidget(self.page(area_id))

    def current_area(self) -> str | None:
        page = self.stack.currentWidget()
        return page.area_id if isinstance(page, AreaPage) else None

    def area_of(self, widget: QWidget) -> str | None:
        """The area whose page holds ``widget``, or None."""
        return next((area.id for area in self.areas.values()
                     if area.page is not None and (area.page is widget or area.page.isAncestorOf(widget))), None)

    def page_areas(self) -> list[Area]:
        """The areas with a page, in rail order."""
        return [area for area in sorted(self.areas.values(), key=lambda a: a.order) if area.page is not None]

    def _on_current_changed(self, _index: int) -> None:
        area_id = self.current_area()
        if area_id is not None:
            self.rail.set_current(area_id)
            self.area_changed.emit(area_id)
