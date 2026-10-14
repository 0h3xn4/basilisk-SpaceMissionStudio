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

"""ScenarioEditorWidget: the full scenario form, composing every
sub-editor into one :class:`schema.scenario.Scenario`. This is the single
place that assembles/disassembles a ``Scenario`` from widget state --
``MainWindow`` never touches individual fields itself.

Only edits what ``engine.service.SimulationService`` actually consumes
PLUS ground stations (pure scenario data, see
``ground_station_editor.py``'s docstring for why that's different from
sensors/actuators/FSW modes, which this editor deliberately omits).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..engine.scenario_checks import plausibility_warnings
from ..engine.series_names import expected_series_names
from ..schema.scenario import (
    GravityConfig,
    Scenario,
    ScenarioValidationError,
    SimSettings,
    SpaceWeatherConfig,
)
from .feedback import bring_into_view, clear_field_error, show_field_error
from .page_tree import PageTree, watch_edits
from .ground_station_editor import GroundStationListWidget
from .mission_sequence_editor import MissionSequenceEditorWidget
from .monte_carlo_editor import MonteCarloGroupWidget
from .problem_location import GROUND_STATION, PROPAGATION, SCENARIO, SPACECRAFT, locate
from .spacecraft_editor import SpacecraftListWidget
from .theme import PALETTE
from .widgets import ComboBox



def _page(widget: QWidget) -> QScrollArea:
    """``widget`` as a page of the tree: in a scroll area, so a long form
    never sets the window's height."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(widget)
    return scroll


class _EscapeFilter(QObject):
    """An embedded dialog would close on Escape (QDialog.reject)."""

    def eventFilter(self, _watched, event):  # noqa: N802 -- Qt API name
        return event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape


def _embed(dialog: QDialog) -> None:
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


class _Debounce(QObject):
    """Tells the editor a live form settled: 300 ms after its last edit,
    so a form is not validated at every keystroke."""

    settled = Signal()

    def __init__(self, form: QWidget, kind: str, node=None) -> None:
        super().__init__(form)
        self.form, self.kind, self.node = form, kind, node
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)  # [ms]
        self._timer.timeout.connect(self.settled)
        watch_edits(form, self.poke)

    def poke(self, *_args) -> None:
        self._timer.start()

    def flush(self) -> None:
        """Apply now, if an edit is waiting."""
        if self._timer.isActive():
            self._timer.stop()
            self.settled.emit()


class _FormNode:
    """A spacecraft's or ground station's node: its page, the config it
    shows, and its live form once the page was first shown."""

    def __init__(self, item, holder: QWidget, config) -> None:
        self.item, self.holder, self.config = item, holder, config
        self.form = None
        self.debounce = None


class ScenarioEditorWidget(QWidget):
    """Emits :attr:`changed` on any edit anywhere in the form (including
    inside the spacecraft/ground-station dialogs), so :class:`MainWindow`
    can track an unsaved-changes flag and re-run live validation.
    """

    changed = Signal()
    # (severity, text, shown text) after every revalidate(): the Problems dock lists them.
    problems_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        # The scenario as a tree of pages (docs/ux-audit.md U-01): one page
        # per node, the spacecraft and ground stations each a node of their
        # own whose form applies edits as they are made (U-11). MainWindow
        # adds Templates and the Analyses to the same tree.
        self.page_tree = PageTree()
        outer_layout.addWidget(self.page_tree, 1)
        self.problems: list = []
        self._form_errors: dict = {}  # a live form's problem, by form; the scenario is not valid while there is one
        self._applying = False  # a live form is writing its value: the lists need no rebuild
        self._spacecraft_nodes: list = []
        self._station_nodes: list = []
        self._environment_form = None

        self.scenario_page = _page(self._build_identity_group())
        self.environment_page = self._build_propagation_group()
        self.spacecraft_page = _page(self._build_spacecraft_group())
        self.ground_station_page = _page(self._build_ground_station_group())
        self.mission_sequence_page = _page(self._build_mission_sequence_group())
        self.monte_carlo_page = _page(self._build_monte_carlo_group())
        tree = self.page_tree
        self.scenario_item = tree.add_page("Scenario", self.scenario_page)
        self.environment_item = tree.add_page("Environment", self.environment_page)
        self.spacecraft_item = tree.add_page("Spacecraft", self.spacecraft_page)
        self.ground_station_item = tree.add_page("Ground stations", self.ground_station_page)
        self.mission_sequence_item = tree.add_page("Mission sequence", self.mission_sequence_page)
        self.monte_carlo_item = tree.add_page("Monte Carlo", self.monte_carlo_page)
        tree.page_shown.connect(self._on_page_shown)
        self.spacecraft_list.set_edit_handler(self.show_spacecraft)
        self.ground_station_list.set_edit_handler(self.show_station)
        self.spacecraft_list.changed.connect(self._on_spacecraft_list_changed)
        self.ground_station_list.changed.connect(self._on_station_list_changed)
        self.spacecraft_list.reloaded.connect(self._on_spacecraft_list_changed)
        self.ground_station_list.reloaded.connect(self._on_station_list_changed)
        # The spacecraft forms show the tabs of the mode and offer the
        # stations there are: a new mode or station list rebuilds them.
        self.simulation_mode_combo.currentIndexChanged.connect(self._reset_spacecraft_forms)

        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        outer_layout.addWidget(self.validation_label)
        # Plausibility checks while editing (UX/UI guidelines): orbits that
        # cannot be flown, a run outside the installed reference data.
        self.plausibility_label = QLabel()
        self.plausibility_label.setWordWrap(True)
        self.plausibility_label.setStyleSheet(f"color: {PALETTE['warning']};")
        self.plausibility_label.setVisible(False)
        outer_layout.addWidget(self.plausibility_label)

        self.changed.connect(self.revalidate)
        self._rebuild_environment_form()
        self._rebuild_nodes(self._spacecraft_nodes, self.spacecraft_list.to_list(), self.spacecraft_item, "spacecraft")
        self._rebuild_nodes(self._station_nodes, self.ground_station_list.to_list(), self.ground_station_item,
                            "station")
        self.revalidate()

    # -- construction ------------------------------------------------------
    def _build_identity_group(self) -> QGroupBox:
        group = QGroupBox("Scenario")
        form = QFormLayout(group)
        self.name_edit = QLineEdit("new scenario")
        self.name_edit.textChanged.connect(self.changed)
        form.addRow("Name", self.name_edit)

        # First choice in the form, deliberately -- per the feature
        # request this responds to, simulation mode should be picked
        # "before starting with anything else". "Orbit only" is a
        # stricter, beginner-friendly mode: Scenario.validate() rejects
        # any spacecraft with fsw_mode/sensors/actuators/power set while
        # this is selected (see Scenario.simulation_mode's docstring) --
        # switching TO "Orbit only" on a scenario that already has those
        # set will make Save/Run fail with a specific error naming what to
        # remove, same "surface it, don't silently drop it" discipline as
        # everywhere else in this app.
        self.simulation_mode_combo = ComboBox()
        self.simulation_mode_combo.addItem("Full attitude (sensors, actuators, FSW, power)",
                                            userData="full_attitude")
        self.simulation_mode_combo.addItem("Orbit only (cannonball -- no attitude features)",
                                            userData="orbit_only")
        self.simulation_mode_combo.setToolTip(
            "Full attitude: sensors, actuators, FSW pointing/control, and power budgets are all available.\n"
            "Orbit only: a simpler cannonball spacecraft (drag_area_m2/srp_area_m2 as its average cross-section) "
            "for pure orbit-propagation questions (delta-V budgets, orbit lifetime, station-keeping cadence, ...) "
            "-- no sensors/actuators/FSW/power on any spacecraft in this mode."
        )
        self.simulation_mode_combo.currentIndexChanged.connect(self.changed)
        form.addRow("Simulation mode", self.simulation_mode_combo)

        self.epoch_edit = QLineEdit("2030-01-01T00:00:00")
        self.epoch_edit.setPlaceholderText("ISO 8601 UTC, e.g. 2030-01-01T00:00:00")
        self.epoch_edit.setToolTip(
            "The real calendar date/time (UTC) the simulation starts at -- 'sim time 0' in "
            "every plot. This matters beyond just a label: it fixes where the Sun and Moon "
            "actually are, so it affects eclipse timing, solar-panel power generation, Sun "
            "-pointing/Sun-safe attitude modes, and (for a Sun-synchronous orbit) which RAAN "
            "corresponds to a given local time of day. Must be ISO 8601 (as shown in the "
            "placeholder) -- anything else fails validation."
        )
        self.epoch_edit.textChanged.connect(self.changed)
        form.addRow("Epoch (UTC)", self.epoch_edit)

        self.description_edit = QPlainTextEdit()
        # Was 60px (~2 lines) -- nowhere near enough for the built-in
        # template missions' own multi-paragraph descriptions (see
        # spacemissionstudio/scenarios/templates/), which needed constant
        # scrolling just to read a few lines at a time. Tall enough to
        # show most of one of those at once without letting this one
        # field dominate the whole scenario form (Propagation setup/
        # Spacecraft/Ground stations/Mission sequence/Monte Carlo all
        # need their own visible room below it) -- it still scrolls
        # internally for anything longer, same as before, just far less
        # eagerly.
        self.description_edit.setFixedHeight(220)
        self.description_edit.textChanged.connect(self.changed)
        form.addRow("Description", self.description_edit)
        return group

    def _build_propagation_group(self) -> QWidget:
        """The Environment page: gravity and perturbations, the integrator
        and duration, and space weather, in :class:`PropagationSetupDialog`'s
        form, embedded and applied as it is edited (U-17; it used to be a
        read-only summary and a modal dialog). ``self._gravity`` /
        ``self._sim_settings`` / ``self._space_weather`` stay this widget's
        source of truth for those three dataclasses."""
        self._gravity = GravityConfig()
        self._fsw_exports: list = []  # FswExportRecord list, kept as loaded (see set_fsw_exports)
        self._sim_settings = SimSettings()
        self._space_weather = SpaceWeatherConfig()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        return page

    def _rebuild_environment_form(self) -> None:
        """A new Environment form from the current settings (after a load or
        an undo)."""
        from .propagation_setup_dialog import PropagationSetupDialog

        if self._environment_form is not None:
            self._form_errors.pop(id(self._environment_form), None)
            self._environment_form.setParent(None)
            self._environment_form.deleteLater()
        form = PropagationSetupDialog(self._gravity, self._sim_settings, self._space_weather,
                                      parent=self.environment_page)
        _embed(form)
        _Debounce(form, "environment").settled.connect(self._on_form_settled)
        self.environment_page.layout().addWidget(form)
        self._environment_form = form

    def _build_spacecraft_group(self) -> QGroupBox:
        group = QGroupBox("Spacecraft")
        layout = QVBoxLayout(group)
        self.spacecraft_list = SpacecraftListWidget()
        self.spacecraft_list.set_central_body_provider(lambda: self._gravity.central_body)
        self.spacecraft_list.set_simulation_mode_provider(lambda: self.simulation_mode_combo.currentData())
        self.spacecraft_list.set_ground_station_names_provider(
            lambda: [gs.name for gs in self.ground_station_list.to_list()]
        )
        self.spacecraft_list.set_epoch_provider(lambda: self.epoch_edit.text().strip())
        self._base_dir_provider = None  # set_base_dir_provider
        self.spacecraft_list.changed.connect(self.changed)
        self.spacecraft_list.changed.connect(self._refresh_monte_carlo_spacecraft_names)
        layout.addWidget(self.spacecraft_list)
        return group

    def _build_ground_station_group(self) -> QGroupBox:
        group = QGroupBox("Ground stations")
        layout = QVBoxLayout(group)
        self.ground_station_list = GroundStationListWidget()
        self.ground_station_list.changed.connect(self.changed)
        layout.addWidget(self.ground_station_list)
        return group

    def _build_mission_sequence_group(self) -> QGroupBox:
        group = QGroupBox("Mission sequence")
        layout = QVBoxLayout(group)
        self.mission_sequence_editor = MissionSequenceEditorWidget()
        self.mission_sequence_editor.set_spacecraft_names_provider(
            lambda: [sc.name for sc in self.spacecraft_list.to_list()]
        )
        self.mission_sequence_editor.set_ground_station_names_provider(
            lambda: [gs.name for gs in self.ground_station_list.to_list()]
        )
        self.mission_sequence_editor.set_series_names_provider(self._expected_series_names)
        self.mission_sequence_editor.changed.connect(self.changed)
        layout.addWidget(self.mission_sequence_editor)
        return group

    def _build_monte_carlo_group(self) -> MonteCarloGroupWidget:
        self.monte_carlo_group = MonteCarloGroupWidget()
        self.monte_carlo_group.changed.connect(self.changed)
        self._refresh_monte_carlo_spacecraft_names()
        return self.monte_carlo_group

    def _refresh_monte_carlo_spacecraft_names(self) -> None:
        self.monte_carlo_group.set_spacecraft_names([sc.name for sc in self.spacecraft_list.to_list()])

    # -- the tree's spacecraft and ground station nodes ---------------------
    def _rebuild_nodes(self, nodes: list, configs: list, parent_item, kind: str) -> None:
        """One node per spacecraft or station under ``parent_item``, each
        with an empty page its form fills when first shown."""
        current = self.page_tree.current_page()
        shown = next((node.config.name for node in nodes if node.holder is current), None)
        for node in nodes:
            self._form_errors.pop(id(node), None)
            self.page_tree.remove(node.item)
        nodes.clear()
        for config in configs:
            holder = QWidget()
            QVBoxLayout(holder).setContentsMargins(0, 0, 0, 0)
            holder.setProperty("formKind", kind)
            nodes.append(_FormNode(self.page_tree.add_page(config.name, holder, parent_item), holder, config))
        again = next((node for node in nodes if node.config.name == shown), None)
        if again is not None:
            self.page_tree.tree.setCurrentItem(again.item)
        elif shown is not None:
            self.page_tree.tree.setCurrentItem(parent_item)
        self._update_problem_counts()

    def _on_spacecraft_list_changed(self) -> None:
        self._follow_list(self._spacecraft_nodes, self.spacecraft_list.to_list(), self.spacecraft_item, "spacecraft")

    def _on_station_list_changed(self) -> None:
        self._follow_list(self._station_nodes, self.ground_station_list.to_list(), self.ground_station_item,
                          "station")
        self._reset_spacecraft_forms()  # their pointing target lists the stations

    def _follow_list(self, nodes: list, configs: list, parent_item, kind: str) -> None:
        """After a list changed outside its nodes' forms (Add, Remove, a
        generator, the 3D model editor, Undo): rebuild the nodes when the
        list's shape changed, else refresh the forms whose config changed."""
        if self._applying:
            return
        if [node.config.name for node in nodes] != [config.name for config in configs]:
            self._rebuild_nodes(nodes, configs, parent_item, kind)
            return
        for node, config in zip(nodes, configs):
            if node.config is not config:
                node.config = config
                self._drop_form(node)

    def _drop_form(self, node: _FormNode) -> None:
        """Forget ``node``'s form; it is built again from its config, now if
        its page is shown."""
        self._form_errors.pop(id(node), None)
        if node.form is not None:
            node.form.setParent(None)
            node.form.deleteLater()
            node.form = node.debounce = None
        if self.page_tree.current_page() is node.holder:
            self._build_form(node)

    def _reset_spacecraft_forms(self) -> None:
        for node in self._spacecraft_nodes:
            self._drop_form(node)

    def _on_page_shown(self, page) -> None:
        node = self._node_of(page)
        if node is not None and node.form is None:
            self._build_form(node)

    def _node_of(self, page):
        return next((node for node in self._spacecraft_nodes + self._station_nodes if node.holder is page), None)

    def _build_form(self, node: _FormNode) -> None:
        """``node``'s live form: the spacecraft or station editor, embedded."""
        if node in self._spacecraft_nodes:
            from .spacecraft_editor import SpacecraftEditorDialog

            row = self._spacecraft_nodes.index(node)
            others = sorted(c.name for i, c in enumerate(self.spacecraft_list.to_list()) if i != row)
            spacecraft_list = self.spacecraft_list
            form = SpacecraftEditorDialog(
                config=node.config, parent=node.holder, other_spacecraft_names=others,
                simulation_mode=self.simulation_mode_combo.currentData(),
                ground_station_names=[gs.name for gs in self.ground_station_list.to_list()],
                epoch_provider=spacecraft_list._epoch_provider, base_dir_provider=spacecraft_list._base_dir_provider,
                central_body_provider=spacecraft_list._central_body_provider)
            kind = "spacecraft"
        else:
            from .ground_station_editor import GroundStationEditorDialog

            row = self._station_nodes.index(node)
            others = sorted(c.name for i, c in enumerate(self.ground_station_list.to_list()) if i != row)
            form = GroundStationEditorDialog(config=node.config, parent=node.holder, other_names=others)
            kind = "station"
        _embed(form)
        node.holder.layout().addWidget(form)
        node.form = form
        node.debounce = _Debounce(form, kind, node)
        node.debounce.settled.connect(self._on_form_settled)

    def _on_form_settled(self) -> None:
        debounce = self.sender()
        if debounce.kind == "environment":
            self._apply_environment(debounce.form)
        elif debounce.node is not None and debounce.node.form is debounce.form:
            self._apply_node(debounce.node, debounce.kind)

    def _apply_environment(self, form) -> None:
        """The Environment form's values, when they validate."""
        try:
            gravity, sim_settings, space_weather = form.to_gravity(), form.to_sim_settings(), form.to_space_weather()
            gravity.validate()
            sim_settings.validate()
            space_weather.validate()
        except (ScenarioValidationError, ValueError) as exc:
            location = locate(str(exc))
            form.show_problem(location.path if location is not None and location.area == PROPAGATION else "",
                              str(exc), focus=False)
            self._form_errors[id(form)] = str(exc)
            self.revalidate()
            return
        form.clear_problem()
        self._form_errors.pop(id(form), None)
        if (gravity, sim_settings, space_weather) == (self._gravity, self._sim_settings, self._space_weather):
            self.revalidate()
            return
        self._gravity, self._sim_settings, self._space_weather = gravity, sim_settings, space_weather
        self.changed.emit()

    def _apply_node(self, node: _FormNode, kind: str) -> None:
        """A spacecraft's or station's form's values, when they validate:
        written into its list, and the node renamed when the name changed."""
        nodes, config_list, area = ((self._spacecraft_nodes, self.spacecraft_list, SPACECRAFT) if kind == "spacecraft"
                                    else (self._station_nodes, self.ground_station_list, GROUND_STATION))
        form, row = node.form, nodes.index(node)
        name = form.name_edit.text().strip()
        others = {c.name for i, c in enumerate(config_list.to_list()) if i != row}
        what = "spacecraft" if kind == "spacecraft" else "ground station"
        error, config = "", None
        if not name:
            error = f"{node.config.name}: name must not be empty"
        elif name in others:
            error = f"{name}: name -- a {what} named {name!r} already exists"
        else:
            try:
                config = form.to_dataclass()
            except (ScenarioValidationError, ValueError) as exc:
                error = str(exc)
        if error:
            location = locate(error, [name, node.config.name]) if kind == "spacecraft" else \
                locate(error, station_names=[name, node.config.name])
            path = location.path if location is not None and location.area == area else ""
            form.show_problem(path or ("name" if "name" in error.split(" -- ")[0] else ""), error, focus=False)
            self._form_errors[id(node)] = error
            self.revalidate()
            return
        form.clear_problem()
        self._form_errors.pop(id(node), None)
        if config == node.config:
            self.revalidate()
            return
        node.config = config
        self._applying = True
        try:
            config_list.replace_config(row, config)
        finally:
            self._applying = False
        self.page_tree.set_title(node.item, config.name)

    def flush_forms(self) -> None:
        """Apply every live form's waiting edit now (before a save or a run)."""
        forms = [getattr(self, "_environment_form", None)]
        forms += [n.form for n in getattr(self, "_spacecraft_nodes", []) + getattr(self, "_station_nodes", [])]
        for form in forms:
            debounce = form.findChild(_Debounce) if form is not None else None
            if debounce is not None:
                debounce.flush()

    # -- going to a node ------------------------------------------------------
    def show_scenario_page(self) -> None:
        self.page_tree.tree.setCurrentItem(self.scenario_item)

    def is_editor_page(self, page) -> bool:
        """Whether ``page`` is one of the editor's own (not Templates or an
        analysis, which MainWindow adds)."""
        return page in (self.scenario_page, self.environment_page, self.spacecraft_page, self.ground_station_page,
                        self.mission_sequence_page, self.monte_carlo_page) or self._node_of(page) is not None

    def _show_node(self, nodes: list, row: int):
        node = nodes[row]
        self.page_tree.tree.setCurrentItem(node.item)
        if node.form is None:
            self._build_form(node)
        return node

    def show_spacecraft(self, row: int) -> None:
        """The page of spacecraft ``row``: Edit... and a double-click in the
        Spacecraft list."""
        self._show_node(self._spacecraft_nodes, row)

    def show_station(self, row: int) -> None:
        self._show_node(self._station_nodes, row)

    def show_spacecraft_problem(self, name: str, path: str = "", message: str = "") -> None:
        """The page of spacecraft ``name``, at the problem ``message`` about
        its field ``path`` (Problems, U-12)."""
        rows = [node.config.name for node in self._spacecraft_nodes]
        if name in rows:
            node = self._show_node(self._spacecraft_nodes, rows.index(name))
            if message:
                node.form.show_problem(path, message)

    def show_station_problem(self, name: str, path: str = "", message: str = "") -> None:
        rows = [node.config.name for node in self._station_nodes]
        if name in rows:
            node = self._show_node(self._station_nodes, rows.index(name))
            if message:
                node.form.show_problem(path, message)

    def edit_propagation_setup(self, path: str = "", message: str = "") -> None:
        """The Environment page, at the problem ``message`` about its field
        ``path`` when given (Problems, U-12)."""
        self.page_tree.tree.setCurrentItem(self.environment_item)
        if message:
            self._environment_form.show_problem(path, message)

    def _update_problem_counts(self, problems=None) -> None:
        """Each node's count of the problems about it; Spacecraft and
        Ground stations add up their nodes'."""
        problems = self.problems if problems is None else problems
        spacecraft = [node.config.name for node in self._spacecraft_nodes]
        stations = [node.config.name for node in self._station_nodes]
        counts: dict = {}
        for _severity, text in problems:
            location = locate(text, spacecraft, stations)
            item = None
            if location is None:
                continue
            if location.area == SCENARIO:
                item = self.scenario_item
            elif location.area == PROPAGATION:
                item = self.environment_item
            elif location.area == SPACECRAFT and location.name in spacecraft:
                item = self._spacecraft_nodes[spacecraft.index(location.name)].item
            elif location.area == GROUND_STATION and location.name in stations:
                item = self._station_nodes[stations.index(location.name)].item
            if item is not None:
                counts[id(item)] = counts.get(id(item), 0) + 1
        for item, _page_widget in self.page_tree.items():
            self.page_tree.set_problem_count(item, counts.get(id(item), 0))
        for parent, nodes in ((self.spacecraft_item, self._spacecraft_nodes), (self.ground_station_item,
                                                                                self._station_nodes)):
            self.page_tree.set_problem_count(parent, sum(counts.get(id(node.item), 0) for node in nodes))

    # -- (dis)assembly -------------------------------------------------------
    def set_base_dir_provider(self, provider) -> None:
        """``provider`` returns the scenario file's folder, or None while the
        scenario is unsaved: where a 3D model's relative mesh paths start
        (the spacecraft editor and the plausibility checks need it)."""
        self._base_dir_provider = provider
        self.spacecraft_list.set_base_dir_provider(provider)

    def to_scenario(self) -> Scenario:
        """Raises :class:`ScenarioValidationError` with a specific message
        on anything invalid -- callers (Save, Run, the live-validation
        label) all go through this one method.
        """
        self.flush_forms()  # an edit still waiting in a live form counts (a save or a run right after it)
        if self._form_errors:
            raise ScenarioValidationError(next(iter(self._form_errors.values())))
        scenario = self._draft_scenario()
        scenario.validate()
        return scenario

    def draft_scenario(self) -> Scenario:
        """The scenario as currently edited, NOT validated (undo history)."""
        return self._draft_scenario()

    def _draft_scenario(self) -> Scenario:
        """The scenario as currently edited, NOT validated."""
        return Scenario(
            name=self.name_edit.text().strip(),
            epoch_utc=self.epoch_edit.text().strip(),
            simulation_mode=self.simulation_mode_combo.currentData(),
            description=self.description_edit.toPlainText(),
            gravity=self._gravity,
            sim_settings=self._sim_settings,
            space_weather=self._space_weather,
            spacecraft=self.spacecraft_list.to_list(),
            ground_stations=self.ground_station_list.to_list(),
            monte_carlo=self.monte_carlo_group.to_dataclass(),
            mission_sequence=self.mission_sequence_editor.to_command_list(),
            fsw_exports=list(self._fsw_exports),
        )

    def set_fsw_exports(self, records: list) -> None:
        """Replaces the recorded flight-software exports (Flight Software
        tab); they have no widget here but must survive every edit."""
        self._fsw_exports = list(records)
        self.changed.emit()

    def _expected_series_names(self) -> list[str]:
        try:
            return expected_series_names(self._draft_scenario())
        except Exception:  # noqa: BLE001 -- a half-edited form must never break the command dialog
            return []

    def from_scenario(self, scenario: Scenario) -> None:
        self.name_edit.setText(scenario.name)
        self.name_edit.setCursorPosition(0)  # a long name otherwise opens scrolled to its END
        self.epoch_edit.setText(scenario.epoch_utc)
        mode_index = self.simulation_mode_combo.findData(scenario.simulation_mode)
        if mode_index >= 0:
            self.simulation_mode_combo.setCurrentIndex(mode_index)
        self.description_edit.setPlainText(scenario.description)

        self._gravity = scenario.gravity
        self._sim_settings = scenario.sim_settings
        self._space_weather = scenario.space_weather
        self._rebuild_environment_form()

        self.spacecraft_list.from_list(scenario.spacecraft)
        self.ground_station_list.from_list(scenario.ground_stations)
        self._refresh_monte_carlo_spacecraft_names()
        self.monte_carlo_group.from_dataclass(scenario.monte_carlo)
        self.mission_sequence_editor.from_command_list(scenario.mission_sequence)
        self._fsw_exports = list(scenario.fsw_exports)

        self.revalidate()

    def reset_to_default(self) -> None:
        self.from_scenario(Scenario(
            name="new scenario",
            epoch_utc="2030-01-01T00:00:00",
            spacecraft=[],
        ))

    # The scenario's own fields, by their path in Scenario, and the label
    # their messages use (docs/ux-audit.md U-12).
    _FIELDS = {"name": ("name_edit", "Name"), "epoch_utc": ("epoch_edit", "Epoch (UTC)"),
               "simulation_mode": ("simulation_mode_combo", "Simulation mode"),
               "description": ("description_edit", "Description")}

    def field_widget(self, path: str):
        """The editor's widget for a scenario field ("epoch_utc"), or None."""
        entry = self._FIELDS.get(path)
        return getattr(self, entry[0]) if entry else None

    def focus_field(self, path: str) -> bool:
        """Show and focus the field at ``path``; whether there is one."""
        widget = self.field_widget(path)
        if widget is not None:
            self.show_scenario_page()
            bring_into_view(widget)
        return widget is not None

    def _spacecraft_and_station_names(self):
        return ([sc.name for sc in self.spacecraft_list.to_list()],
                [gs.name for gs in self.ground_station_list.to_list()])

    def problem_display(self, text: str) -> str:
        """``text`` as Problems and the field show it: a scenario field's
        message starts with its label, not its schema path ("Epoch (UTC)
        '2030-13-45T99:00:00' is not ...", not "scenario.epoch_utc ...")."""
        location = locate(text, *self._spacecraft_and_station_names())
        if location is not None and location.area == SCENARIO and location.path in self._FIELDS:
            return self._FIELDS[location.path][1] + text[len("scenario." + location.path):]
        return text

    def _show_field_problem(self, text: str) -> None:
        """Mark the scenario field ``text`` is about and show it under it;
        clear the field marked before."""
        marked = getattr(self, "_marked_field", None)
        if marked is not None:
            clear_field_error(marked)
            self._marked_field = None
        location = locate(text, *self._spacecraft_and_station_names()) if text else None
        widget = self.field_widget(location.path) if location is not None and location.area == SCENARIO else None
        if widget is not None:
            show_field_error(widget, self.problem_display(text))
            self._marked_field = widget

    def revalidate(self) -> None:
        warnings = []
        problems = []
        try:
            scenario = self.to_scenario()
        except ScenarioValidationError as exc:
            self.validation_label.setText(f"⚠ {self.problem_display(str(exc))}")
            self.validation_label.setStyleSheet(f"color: {PALETTE['danger']};")
            problems.append(("error", str(exc)))
            problems += [("error", error) for error in self._form_errors.values() if error != str(exc)]
            self._show_field_problem(str(exc))
        else:
            self._show_field_problem("")
            self.validation_label.setText("✓ valid")
            self.validation_label.setStyleSheet(f"color: {PALETTE['success']};")
            base_dir = self._base_dir_provider() if self._base_dir_provider else None
            warnings = plausibility_warnings(scenario, base_dir=base_dir)
        self.plausibility_label.setText("\n".join(f"⚠ {warning}" for warning in warnings))
        self.plausibility_label.setVisible(bool(warnings))
        self.problems = problems + [("warning", warning) for warning in warnings]
        self._update_problem_counts()
        self.problems_changed.emit(self.problem_rows())

    def problem_rows(self) -> list:
        """The problems as the Problems dock lists them: ``(severity, text,
        shown text)``."""
        return [(severity, text, self.problem_display(text)) for severity, text in self.problems]
