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

"""The Settings area (UI overhaul plan §5.2): appearance, reference data,
network, change history, layout, the keyboard shortcuts and about, each a
section of one page.

Every command is one of the window's action registry (:mod:`gui.actions`),
shown here as a button, and the shortcut list is generated from the
registry, so this page and the command palette agree. The UI scale and reduce
motion (M8) are preferences, not commands: they are set here only.
"""

from __future__ import annotations

import weakref

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
                               QWidget)

from .. import history, network
from . import units
from .widgets import ComboBox
from .theme import (CONTENT_MAX_WIDTH_PX, SPACE, UI_SCALES, reduce_motion, set_reduce_motion, set_role,
                    set_ui_scale_setting, ui_scale_setting)

# (key, title, what it is for)
_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("appearance", "Appearance", "The theme applies at once, to every open view; the UI scale at the next "
                                 "start."),
    ("reference_data", "Reference data", "The SPICE kernels, gravity fields, magnetic model, space weather and "
                                         "Earth orientation files, with their sources, dates and checksums."),
    ("network", "Network", "SpaceMissionStudio reaches the network only for a download you start, and "
                         "only the addresses listed for it. Offline, no download can start."),
    ("history", "Change history", "Each save records what it changed beside the scenario "
                                  "(mission.history.jsonl), with this name as its author; the command line uses "
                                  "it too. Empty: your user name."),
    ("layout", "Layout", "The navigation rail, the inspector and the Problems panel; Reset Layout puts them "
                         "back as a new window has them."),
    ("keyboard", "Keyboard", "Every command with a shortcut. Ctrl+K finds any command by name."),
    ("about", "About", ""),
)


class SettingsPage(QScrollArea):
    """The settings, one section under the other."""

    def __init__(self, commands, parent: QWidget | None = None) -> None:
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
        self.section_titles: dict[str, QLabel] = {}
        self.buttons: dict[str, QToolButton] = {}
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

    def sections(self) -> list[tuple[str, str]]:
        """(key, title) of each section, in order."""
        return [(key, title) for key, title, _text in _SECTIONS]

    def show_section(self, key: str) -> None:
        """Scroll ``key``'s section to the top and refresh what it lists."""
        if key == "keyboard":
            self.refresh_shortcuts()
        heading = self.section_titles[key]
        self.verticalScrollBar().setValue(heading.y() - SPACE["sm"])

    def _row(self, command_ids: tuple[str, ...]) -> None:
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
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        row.addWidget(QLabel("UI scale"))
        self.ui_scale = ComboBox()  # the wheel does not change it
        for percent in UI_SCALES:
            self.ui_scale.addItem(f"{percent} %", percent)
        self.ui_scale.setCurrentIndex(UI_SCALES.index(ui_scale_setting()))
        self.ui_scale.setToolTip("The size of text and controls, from the next start")
        self.ui_scale.currentIndexChanged.connect(self._on_ui_scale)
        row.addWidget(self.ui_scale)
        self.ui_scale_note = set_role(QLabel(""), tone="secondary")
        row.addWidget(self.ui_scale_note)
        row.addStretch(1)
        self._layout.addLayout(row)
        self.reduce_motion = QCheckBox("Reduce motion")
        self.reduce_motion.setToolTip("Notifications appear and go at once, without fading")
        self.reduce_motion.setChecked(reduce_motion())
        self.reduce_motion.toggled.connect(set_reduce_motion)
        self._layout.addWidget(self.reduce_motion)
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        row.addWidget(QLabel("Plot units"))
        self.plot_units = ComboBox()
        for value, text in units.PLOT_UNITS:
            self.plot_units.addItem(text, value)
        self.plot_units.setCurrentIndex(self.plot_units.findData(units.plot_units()))
        self.plot_units.setToolTip("The units the plots and the run comparison show: the display units, or the "
                                   "values as recorded and exported (SI: m, rad, s). The exports are always SI.")
        self.plot_units.setAccessibleName("Plot units")
        self.plot_units.currentIndexChanged.connect(self._on_plot_units)
        row.addWidget(self.plot_units)
        self.plot_units_note = set_role(QLabel(""), tone="secondary")
        row.addWidget(self.plot_units_note)
        row.addStretch(1)
        self._layout.addLayout(row)

    def _on_plot_units(self, index: int) -> None:
        units.set_plot_units(self.plot_units.itemData(index))
        self.plot_units_note.setText("Applies to the plots drawn next.")

    def _on_ui_scale(self, index: int) -> None:
        set_ui_scale_setting(self.ui_scale.itemData(index))
        self.ui_scale_note.setText("Applies at the next start.")

    def _build_history(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        row.addWidget(QLabel("Author"))
        self.author_edit = QLineEdit(history.set_author_name())
        self.author_edit.setPlaceholderText(history.default_author())
        self.author_edit.setToolTip("Your name, as the change history records it; empty: your user name")
        self.author_edit.setAccessibleName("Author")
        self.author_edit.editingFinished.connect(self._on_author)
        row.addWidget(self.author_edit, 1)
        self._layout.addLayout(row)
        self.author_note = set_role(QLabel(""), tone="secondary")
        self.author_note.setWordWrap(True)
        self._layout.addWidget(self.author_note)

    def _build_network(self) -> None:
        self.offline_box = QCheckBox("Work offline: no downloads")
        self.offline_box.toggled.connect(self._on_offline)
        self._layout.addWidget(self.offline_box)
        self.network_note = set_role(QLabel(""), tone="secondary")
        self.network_note.setWordWrap(True)
        self._layout.addWidget(self.network_note)
        hosts = "\n".join(f"{p.label}: {', '.join(p.hosts)}" for p in network.PURPOSES.values())
        self.network_hosts = set_role(QLabel(hosts), tone="secondary")
        self.network_hosts.setWordWrap(True)
        self._layout.addWidget(self.network_hosts)
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        self.network_log_button = QPushButton("Open the network log")
        self.network_log_button.setToolTip(f"Every network use allowed or refused: {network.log_path()}")
        self.network_log_button.clicked.connect(self._open_network_log)
        row.addWidget(self.network_log_button)
        row.addStretch(1)
        self._layout.addLayout(row)
        self.refresh_network()

    def refresh_network(self) -> None:
        """Show the policy in effect; the box is locked when an administrator
        or the environment sets it."""
        current = network.policy()
        self.offline_box.blockSignals(True)
        self.offline_box.setChecked(current.offline)
        self.offline_box.blockSignals(False)
        self.offline_box.setEnabled(not current.locked)
        note = current.describe()
        if current.locked:
            note += " You cannot change this here."
        self.network_note.setText(note)

    def _on_offline(self, offline: bool) -> None:
        try:
            network.set_user_offline(offline)
        except (OSError, PermissionError) as exc:
            set_role(self.network_note, tone="critical")
            self.network_note.setText(f"Not changed: {exc}")
            return
        set_role(self.network_note, tone="secondary")
        self.refresh_network()
        window = self.window()
        if hasattr(window, "apply_network_policy"):
            window.apply_network_policy()

    def _open_network_log(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        path = network.log_path()
        if not path.exists():
            self.network_note.setText("Nothing logged yet: no network use was allowed or refused.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_author(self) -> None:
        try:
            history.set_author(self.author_edit.text())
        except OSError as exc:
            set_role(self.author_note, tone="critical")
            self.author_note.setText(f"Could not keep the name: {exc}")
            return
        self.author_edit.setText(history.set_author_name())
        set_role(self.author_note, tone="secondary")
        self.author_note.setText(f"Saves are recorded as {history.current_author()}.")

    def _build_reference_data(self) -> None:
        self._row(("tools.reference_data",))

    def _build_layout(self) -> None:
        self._row(("view.rail_icons", "view.inspector", "view.problems", "view.reset_layout"))

    def _build_keyboard(self) -> None:
        self.shortcuts_table = QTableWidget(0, 3)
        self.shortcuts_table.setTabKeyNavigation(False)  # read-only: Tab leaves the table; the arrows move in it (M9)
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
        self._row(("help.about", "help.licences", "help.manual"))
