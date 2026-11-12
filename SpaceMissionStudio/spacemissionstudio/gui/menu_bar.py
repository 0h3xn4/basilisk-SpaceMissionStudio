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

"""The main window's menu bar: File, Edit, View, Go, Run, Tools and Help.

Every item is a command of the action registry (:mod:`gui.actions`), the
same :class:`QAction` the command palette, the top bar, the area headers
and the shortcut list use. A menu item, a shortcut and a button therefore
cannot disagree: they share one text, one shortcut and one enabled state.

:data:`MENUS` lays the menus out. An entry is a command id, ``"-"`` for a
separator, ``(title, entries)`` for a submenu, or :data:`RECENT` for the
recent scenarios. ``tests/gui/test_menu_bar.py`` checks that every
registered command is in a menu once, so a new command needs a place
here.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Sequence
from typing import Union

from PySide6.QtWidgets import QMenu, QMenuBar

from . import recent_files
from .actions import ActionRegistry

RECENT = "@recent"  # File > Open Recent: the recent scenario files

Entry = Union[str, tuple[str, Sequence["Entry"]]]

MENUS: tuple[tuple[str, tuple[Entry, ...]], ...] = (
    ("&File", ("file.new", "file.open", ("Open &Recent", (RECENT,)), "-",
               "file.save", "file.save_as", "-",
               "file.change_history", "tools.ccsds_export", "-",
               "file.quit")),
    ("&Edit", ("edit.undo", "edit.redo", "-", "edit.settings")),
    ("&View", ("view.inspector", "view.calculation", "view.problems", "view.explain", "-",
               "view.menu_bar", "view.rail_icons", "-",
               "view.theme.system", "view.theme.light", "view.theme.dark", "-",
               "view.reset_layout", "-",
               "help.palette")),
    ("&Go", ("go.home", "go.scenario", "go.run", "go.results", "go.timeline", "go.reports", "-",
             ("&Time Cursor", ("cursor.next_sample", "cursor.previous_sample", "cursor.ten_samples_on",
                               "cursor.ten_samples_back", "-", "cursor.next_event", "cursor.previous_event", "-",
                               "cursor.start_of_the_run", "cursor.end_of_the_run", "-",
                               "run.clear_cursor")))),
    ("&Run", ("run.run", "run.cancel", "-",
              ("Run &Mode", ("run.mode.single", "run.mode.monte_carlo", "run.mode.sil")),
              "run.live_plot", "-",
              "analyses.end_of_life", "analyses.budget", "analyses.design_checks", "-",
              "run.open_monte_carlo")),
    ("&Tools", ("tools.model_3d", "tools.flight_software", "-",
                "tools.ccsds_check", "-",
                "tools.reference_data", "run.check_data")),
    ("&Help", ("help.manual", "help.shortcuts", "-",
               "help.licences", "help.about")),
)


def command_ids(entries: Sequence[Entry] = None) -> list[str]:
    """Every command id :data:`MENUS` places, in menu order (with repeats,
    so a test can find one placed twice)."""
    if entries is None:
        entries = [entry for _title, menu in MENUS for entry in menu]
    ids: list[str] = []
    for entry in entries:
        if isinstance(entry, tuple):
            ids.extend(command_ids(entry[1]))
        elif entry not in ("-", RECENT):
            ids.append(entry)
    return ids


def build_menu_bar(menu_bar: QMenuBar, registry: ActionRegistry,
                   open_recent: Callable[[object], object]) -> dict[str, QMenu]:
    """Fill ``menu_bar`` from :data:`MENUS` with the registry's actions;
    ``open_recent`` gets the action of a file picked under File > Open
    Recent (its path is the action's data, None for Clear the List). Returns
    each menu and submenu by its title without the ampersand."""
    menus: dict[str, QMenu] = {}
    for title, entries in MENUS:
        menu = menu_bar.addMenu(title)
        menu.setObjectName(f"menu.{title.replace('&', '').lower()}")
        menus[title.replace("&", "")] = menu
        _fill(menu, entries, registry, open_recent, menus)
    return menus


def _fill(menu: QMenu, entries: Sequence[Entry], registry: ActionRegistry, open_recent, menus: dict) -> None:
    """A module function, not a closure: a nested function calling itself is
    a reference cycle, which kept ``open_recent`` (and so the window) alive
    until a garbage collection."""
    for entry in entries:
        if entry == "-":
            menu.addSeparator()
        elif entry == RECENT:
            RecentMenu.attach(menu, open_recent)
        elif isinstance(entry, tuple):
            title, children = entry
            submenu = menu.addMenu(title)
            submenu.setObjectName(f"menu.{title.replace('&', '').lower().replace(' ', '_')}")
            menus[title.replace("&", "")] = submenu
            _fill(submenu, children, registry, open_recent, menus)
        else:
            menu.addAction(registry.action(entry))


class RecentMenu:
    """File > Open Recent: the recent scenarios, read from the settings each
    time the menu opens, so it agrees with Home's list. A file's action
    carries its path as data; ``open_recent`` gets the action triggered
    (a bound method: a lambda holding the window on a child's signal keeps
    the window alive past its close, see gui.actions)."""

    @staticmethod
    def attach(menu: QMenu, open_recent: Callable[[object], object]) -> None:
        menu.aboutToShow.connect(lambda: RecentMenu.refresh(menu))
        # Weakly: a bound method of the window on a child's signal kept the
        # window alive after it closed, to be freed by a later collection in
        # whatever thread ran it (a segfault, tests/gui/test_help.py alone).
        target = weakref.WeakMethod(open_recent) if hasattr(open_recent, "__self__") else (lambda: open_recent)
        menu.triggered.connect(lambda action: (target() or (lambda _action: None))(action))
        RecentMenu.refresh(menu)

    @staticmethod
    def refresh(menu: QMenu) -> None:
        menu.clear()
        paths = [path for path in recent_files.recent() if path.is_file()]
        for number, path in enumerate(paths, start=1):
            name = path.name.replace("&", "&&")  # a literal ampersand, not a mnemonic
            action = menu.addAction(f"&{number} {name}" if number < 10 else name)
            action.setStatusTip(str(path))
            action.setToolTip(str(path))
            action.setData(str(path))
        if not paths:
            menu.addAction("No recent scenarios").setEnabled(False)
        menu.addSeparator()
        clear = menu.addAction("&Clear the List")
        clear.setEnabled(bool(recent_files.recent()))
        clear.triggered.connect(recent_files.clear)
