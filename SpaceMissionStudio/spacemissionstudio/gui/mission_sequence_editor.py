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

"""The Mission Sequence editor: a scenario's ``mission_sequence``, the GUI
counterpart of ``schema.command.Command``/``engine.mission_engine.MissionEngine``
(docs/ux-audit.md U-15).

:class:`MissionSequenceEditorWidget` shows the steps as a tree (``if``/``while``
steps hold steps of their own): each with its kind's icon, a sentence saying
what it does (:func:`step_sentence`) and a checkbox that leaves it out of the
run (``Command.enabled``). Steps are reordered by dragging or with Move up /
Move down. The selected step's form is shown beside the tree and applied as
you type, 300 ms after the last edit; a step with a problem is shown in the
error colour, the problem in a banner over its form and in Problems.

``_CommandEditorDialog`` is that form: a Kind combo picks the command shape
(fixed once a step exists), the rest of the form is kind-conditional fields.
It builds a real ``schema.command.Command`` and calls its own ``validate()``,
the single source of truth for what each kind requires. It also works as a
dialog (``to_dataclass()``/``_on_accept()``).

The spacecraft, ground-station and series names come from zero-argument
providers (``set_spacecraft_names_provider()`` and its siblings), read each
time a step's form is built.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..schema.command import (
    SUPPORTED_COMMAND_KINDS,
    PASS_EVENT_KINDS,
    SUPPORTED_EVENT_KINDS,
    SUPPORTED_MANEUVER_FRAMES,
    SUPPORTED_STOP_CONDITIONS,
    Command,
)
from .feedback import ProblemBanner, show_dialog_error, show_toast
from .icons import step_icon
from .page_tree import embed_dialog, watch_edits
from .theme import on_change, set_role
from .theme.items import retint, tint
from .widgets import ComboBox, PreciseDoubleSpinBox, SpinBox, finish_form

# Mirrors engine.mission_engine._ASSIGNMENT_CONTROLLERS/_ASSIGNMENT_ATTRIBUTES
# -- duplicated here (not imported) because engine.mission_engine imports
# engine.service -> Basilisk at module level (see engine/results.py's own
# docstring on why Basilisk-free/GUI-safe modules stay separate from it),
# and this dialog must be usable with no Basilisk installed. Keep these in
# sync if either changes.
_ASSIGNMENT_CONTROLLER_CHOICES = ("station_keeping", "phasing_keeping", "constant_thrust")
_ASSIGNMENT_PARAMETER_CHOICES = ("thrust_n", "isp_s")

# self.stack page order -- "if"/"while" share one page (same params shape:
# just "condition"), so this has one fewer entries than
# SUPPORTED_COMMAND_KINDS.
_KIND_PAGE_INDEX = {"propagate": 0, "maneuver": 1, "assignment": 2, "report": 3, "if": 4, "while": 4,
                     "script_block": 5, "lambert_transfer": 6}


def _spin_component(value: float = 0.0) -> QDoubleSpinBox:
    box = PreciseDoubleSpinBox()
    box.setRange(-1.0e9, 1.0e9)
    box.setDecimals(6)
    box.setSingleStep(0.1)
    box.setValue(value)
    # Three side by side: sized for everyday values, not the range's longest
    # text ("-1000000000.000000"), so the row fits a page beside the tree.
    box.setMinimumWidth(110)  # [px]
    box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return box


class _CommandEditorDialog(QDialog):
    def __init__(self, command: Command | None = None, parent: QWidget | None = None,
                 spacecraft_names: list[str] | None = None, series_names: list[str] | None = None,
                 ground_station_names: list[str] | None = None):
        super().__init__(parent)
        self._spacecraft_names = spacecraft_names or []
        self._ground_station_names = ground_station_names or []
        self._series_names = series_names or []
        self.setWindowTitle("Edit command" if command is not None else "New command")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.kind_combo = ComboBox()
        self.kind_combo.setToolTip(
            "What this step in the mission sequence actually does, run in order (top to bottom "
            "in the tree) starting from the scenario's own initial conditions -- each command "
            "picks up exactly where the previous one left off:\n\n"
            "propagate: just advance the simulation (no maneuver) until a stop condition.\n"
            "maneuver: an instantaneous delta-V impulse.\n"
            "lambert_transfer: solve for, and apply, the delta-V to reach a target position by "
            "a given time.\n"
            "assignment: change a running controller's parameter (e.g. thrust) mid-mission.\n"
            "report: snapshot named series at this point in time.\n"
            "if / while: run nested child commands conditionally/repeatedly.\n"
            "script_block: arbitrary unsandboxed Python."
        )
        self.kind_combo.addItems(list(SUPPORTED_COMMAND_KINDS))
        # Changing kind on an existing command would orphan whatever
        # children it has in the tree (only "if"/"while" carry children,
        # and MissionSequenceEditorWidget derives them from tree structure,
        # not from this dialog) -- so kind is fixed once a command exists;
        # only choosable while adding a brand new one.
        self.kind_combo.setEnabled(command is None)
        if command is not None:
            index = self.kind_combo.findText(command.kind)
            if index >= 0:
                self.kind_combo.setCurrentIndex(index)
        form.addRow("Kind", self.kind_combo)

        self.label_edit = QLineEdit(command.label if command is not None and command.label else "")
        self.label_edit.setPlaceholderText("optional, e.g. 'Prop to periapsis'")
        form.addRow("Label", self.label_edit)
        layout.addLayout(form)

        self.stack = QStackedWidget()
        params = command.params if command is not None else {}
        self._build_propagate_page(params)
        self._build_maneuver_page(params)
        self._build_assignment_page(params)
        self._build_report_page(params)
        self._build_conditional_page(params)
        self._build_script_block_page(params)
        self._build_lambert_transfer_page(params)
        layout.addWidget(self.stack)

        self.kind_combo.currentTextChanged.connect(self._on_kind_changed)
        self._on_kind_changed(self.kind_combo.currentText())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # See constellation_dialog.py's identical fix for why this is
        # needed: Qt can size a freshly-constructed QDialog smaller than
        # its own sizeHint() on first show() on a real desktop, a gap
        # this project's own offscreen test rendering doesn't reproduce.
        finish_form(self)  # units in the fields, optional groups collapse (M4a)
        self.resize(self.sizeHint())

    def _on_kind_changed(self, kind: str) -> None:
        self.stack.setCurrentIndex(_KIND_PAGE_INDEX[kind])

    # -- page construction ---------------------------------------------------
    def _build_propagate_page(self, params: dict) -> None:
        page = QWidget()
        form = QFormLayout(page)

        self.stop_condition_combo = ComboBox()
        self.stop_condition_combo.setToolTip(
            "When this propagate step stops and moves on to the next command:\n"
            "duration: after a fixed number of days (below).\n"
            "epoch: at a specific calendar date/time (below).\n"
            "event: as soon as a chosen spacecraft event happens (periapsis, apoapsis, or the start or "
            "end of the next pass over a ground station) -- below."
        )
        self.stop_condition_combo.addItems(list(SUPPORTED_STOP_CONDITIONS))
        index = self.stop_condition_combo.findText(params.get("stop_condition", "duration"))
        if index >= 0:
            self.stop_condition_combo.setCurrentIndex(index)
        form.addRow("Stop condition", self.stop_condition_combo)

        self.propagate_stop_stack = QStackedWidget()
        form.addRow(self.propagate_stop_stack)

        duration_page = QWidget()
        duration_form = QFormLayout(duration_page)
        duration_form.setContentsMargins(0, 0, 0, 0)
        self.duration_days_spin = PreciseDoubleSpinBox()
        self.duration_days_spin.setRange(1e-6, 1e6)
        self.duration_days_spin.setDecimals(6)
        self.duration_days_spin.setValue(float(params.get("duration_days", 1.0)))
        duration_form.addRow("Duration [days]", self.duration_days_spin)
        self.propagate_stop_stack.addWidget(duration_page)

        epoch_page = QWidget()
        epoch_form = QFormLayout(epoch_page)
        epoch_form.setContentsMargins(0, 0, 0, 0)
        self.stop_epoch_edit = QLineEdit(str(params.get("stop_epoch_utc", "")))
        self.stop_epoch_edit.setPlaceholderText("ISO 8601 UTC, e.g. 2030-01-05T00:00:00")
        epoch_form.addRow("Stop epoch (UTC)", self.stop_epoch_edit)
        self.propagate_stop_stack.addWidget(epoch_page)

        event_page = QWidget()
        event_form = QFormLayout(event_page)
        event_form.setContentsMargins(0, 0, 0, 0)
        self.event_kind_combo = ComboBox()
        self.event_kind_combo.setToolTip(
            "periapsis: stop at the next closest approach to the central body.\n"
            "apoapsis: stop at the next farthest point from the central body.\n"
            "pass_start: stop when the next pass over the ground station below begins.\n"
            "pass_end: stop when the current (or next) pass over that station ends."
        )
        self.event_kind_combo.addItems(list(SUPPORTED_EVENT_KINDS))
        event_index = self.event_kind_combo.findText(params.get("event_kind", SUPPORTED_EVENT_KINDS[0]))
        if event_index >= 0:
            self.event_kind_combo.setCurrentIndex(event_index)
        event_form.addRow("Event", self.event_kind_combo)
        self.propagate_event_spacecraft_combo = ComboBox()
        self.propagate_event_spacecraft_combo.addItems(self._spacecraft_names)
        sc_index = self.propagate_event_spacecraft_combo.findText(params.get("spacecraft", ""))
        if sc_index >= 0:
            self.propagate_event_spacecraft_combo.setCurrentIndex(sc_index)
        event_form.addRow("Spacecraft", self.propagate_event_spacecraft_combo)
        self.propagate_event_station_combo = ComboBox()
        self.propagate_event_station_combo.setToolTip("The ground station whose pass ends this propagate.")
        station = params.get("ground_station", "")
        self.propagate_event_station_combo.addItems(self._ground_station_names)
        if station and station not in self._ground_station_names:
            # Keep a station this scenario no longer has visible rather than
            # silently swapping it for another one; validation flags it.
            self.propagate_event_station_combo.addItem(station)
        station_index = self.propagate_event_station_combo.findText(station)
        if station_index >= 0:
            self.propagate_event_station_combo.setCurrentIndex(station_index)
        event_form.addRow("Ground station", self.propagate_event_station_combo)
        self.propagate_event_station_label = event_form.labelForField(self.propagate_event_station_combo)
        self.event_kind_combo.currentTextChanged.connect(self._update_event_station_visibility)
        self._update_event_station_visibility(self.event_kind_combo.currentText())
        self.propagate_stop_stack.addWidget(event_page)

        self.stop_condition_combo.currentTextChanged.connect(
            lambda text: self.propagate_stop_stack.setCurrentIndex(SUPPORTED_STOP_CONDITIONS.index(text))
        )
        self.propagate_stop_stack.setCurrentIndex(
            SUPPORTED_STOP_CONDITIONS.index(self.stop_condition_combo.currentText())
        )

        self.stack.addWidget(page)

    def _update_event_station_visibility(self, event_kind: str) -> None:
        visible = event_kind in PASS_EVENT_KINDS
        self.propagate_event_station_combo.setVisible(visible)
        self.propagate_event_station_label.setVisible(visible)

    def _build_maneuver_page(self, params: dict) -> None:
        page = QWidget()
        form = QFormLayout(page)

        self.maneuver_spacecraft_combo = ComboBox()
        self.maneuver_spacecraft_combo.addItems(self._spacecraft_names)
        index = self.maneuver_spacecraft_combo.findText(params.get("spacecraft", ""))
        if index >= 0:
            self.maneuver_spacecraft_combo.setCurrentIndex(index)
        form.addRow("Spacecraft", self.maneuver_spacecraft_combo)

        delta_v = params.get("delta_v_m_s", [0.0, 0.0, 0.0])
        row = QHBoxLayout()
        self.delta_v_x_spin = _spin_component(delta_v[0] if len(delta_v) > 0 else 0.0)
        self.delta_v_y_spin = _spin_component(delta_v[1] if len(delta_v) > 1 else 0.0)
        self.delta_v_z_spin = _spin_component(delta_v[2] if len(delta_v) > 2 else 0.0)
        _delta_v_tip = (
            "An INSTANTANEOUS velocity change applied the moment this command runs (an idealized "
            "impulsive burn -- no finite burn duration or propellant/thrust-hardware modeling), "
            "in the frame chosen below."
        )
        for box in (self.delta_v_x_spin, self.delta_v_y_spin, self.delta_v_z_spin):
            box.setToolTip(_delta_v_tip)
        row.addWidget(self.delta_v_x_spin)
        row.addWidget(self.delta_v_y_spin)
        row.addWidget(self.delta_v_z_spin)
        row_widget = QWidget()
        row_widget.setLayout(row)
        form.addRow("Delta-V [m/s]", row_widget)

        self.maneuver_frame_combo = ComboBox()
        self.maneuver_frame_combo.addItems(list(SUPPORTED_MANEUVER_FRAMES))
        frame_index = self.maneuver_frame_combo.findText(params.get("frame", "inertial"))
        if frame_index >= 0:
            self.maneuver_frame_combo.setCurrentIndex(frame_index)
        self.maneuver_frame_combo.setToolTip(
            "inertial: delta-V applied directly in the N frame.\n"
            "vnb: velocity/normal/binormal orbit frame.\n"
            "rtn: radial/transverse/normal orbit frame."
        )
        form.addRow("Frame", self.maneuver_frame_combo)

        self.stack.addWidget(page)

    def _build_lambert_transfer_page(self, params: dict) -> None:
        page = QWidget()
        form = QFormLayout(page)

        self.lambert_spacecraft_combo = ComboBox()
        self.lambert_spacecraft_combo.addItems(self._spacecraft_names)
        index = self.lambert_spacecraft_combo.findText(params.get("spacecraft", ""))
        if index >= 0:
            self.lambert_spacecraft_combo.setCurrentIndex(index)
        form.addRow("Spacecraft", self.lambert_spacecraft_combo)

        target_position = params.get("target_position_m", [0.0, 0.0, 0.0])
        row = QHBoxLayout()
        self.lambert_target_x_spin = _spin_component(target_position[0] if len(target_position) > 0 else 0.0)
        self.lambert_target_y_spin = _spin_component(target_position[1] if len(target_position) > 1 else 0.0)
        self.lambert_target_z_spin = _spin_component(target_position[2] if len(target_position) > 2 else 0.0)
        row.addWidget(self.lambert_target_x_spin)
        row.addWidget(self.lambert_target_y_spin)
        row.addWidget(self.lambert_target_z_spin)
        row_widget = QWidget()
        row_widget.setLayout(row)
        form.addRow("Target position [m] (EME2000, central body)", row_widget)

        self.lambert_tof_spin = PreciseDoubleSpinBox()
        self.lambert_tof_spin.setRange(1.0, 1.0e9)
        self.lambert_tof_spin.setDecimals(1)
        self.lambert_tof_spin.setSingleStep(60.0)
        self.lambert_tof_spin.setValue(float(params.get("time_of_flight_s", 3600.0)))
        self.lambert_tof_spin.setToolTip(
            "Time from THIS command's own execution until arrival at the target position. The computed "
            "delta-V is applied immediately (like a maneuver command), not at a separately-delayed time."
        )
        form.addRow("Time of flight [s]", self.lambert_tof_spin)

        self.lambert_num_rev_spin = SpinBox()
        self.lambert_num_rev_spin.setRange(0, 20)
        self.lambert_num_rev_spin.setValue(int(params.get("num_revolutions", 0)))
        form.addRow("Number of revolutions", self.lambert_num_rev_spin)

        self.lambert_max_dist_spin = PreciseDoubleSpinBox()
        self.lambert_max_dist_spin.setRange(0.001, 1.0e9)
        self.lambert_max_dist_spin.setDecimals(3)
        self.lambert_max_dist_spin.setValue(float(params.get("max_distance_target_m", 1000.0)))
        self.lambert_max_dist_spin.setToolTip(
            "lambertValidator rejects the solution (zero delta-V, no maneuver applied) if its own "
            "propagated miss distance at arrival exceeds this."
        )
        form.addRow("Max distance from target [m]", self.lambert_max_dist_spin)

        self.lambert_min_radius_spin = PreciseDoubleSpinBox()
        self.lambert_min_radius_spin.setRange(0.0, 1.0e12)
        self.lambert_min_radius_spin.setDecimals(1)
        self.lambert_min_radius_spin.setValue(float(params.get("min_orbit_radius_m", 0.0)))
        self.lambert_min_radius_spin.setToolTip(
            "lambertValidator rejects the solution if the transfer trajectory dips below this radius from "
            "the central body. 0 disables the check -- set it to the central body's own radius to avoid a "
            "transfer that clips the surface."
        )
        form.addRow("Min orbit radius [m]", self.lambert_min_radius_spin)

        self.stack.addWidget(page)

    def _build_assignment_page(self, params: dict) -> None:
        page = QWidget()
        form = QFormLayout(page)

        self.assignment_spacecraft_combo = ComboBox()
        self.assignment_spacecraft_combo.addItems(self._spacecraft_names)
        self.assignment_controller_combo = ComboBox()
        self.assignment_controller_combo.addItems(list(_ASSIGNMENT_CONTROLLER_CHOICES))
        self.assignment_parameter_combo = ComboBox()
        self.assignment_parameter_combo.addItems(list(_ASSIGNMENT_PARAMETER_CHOICES))

        target = params.get("target", "")
        target_parts = target.split(".") if isinstance(target, str) else []
        if len(target_parts) == 3:
            sc_index = self.assignment_spacecraft_combo.findText(target_parts[0])
            if sc_index >= 0:
                self.assignment_spacecraft_combo.setCurrentIndex(sc_index)
            controller_index = self.assignment_controller_combo.findText(target_parts[1])
            if controller_index >= 0:
                self.assignment_controller_combo.setCurrentIndex(controller_index)
            parameter_index = self.assignment_parameter_combo.findText(target_parts[2])
            if parameter_index >= 0:
                self.assignment_parameter_combo.setCurrentIndex(parameter_index)

        form.addRow("Spacecraft", self.assignment_spacecraft_combo)
        form.addRow("Controller", self.assignment_controller_combo)
        form.addRow("Parameter", self.assignment_parameter_combo)

        self.assignment_value_spin = PreciseDoubleSpinBox()
        self.assignment_value_spin.setRange(-1.0e9, 1.0e9)
        self.assignment_value_spin.setDecimals(6)
        value = params.get("value", 0.0)
        self.assignment_value_spin.setValue(float(value) if isinstance(value, (int, float)) else 0.0)
        form.addRow("New value", self.assignment_value_spin)

        hint = QLabel(
            "Changes a controller setting mid-mission, e.g. lower thrust for a later phase. "
            "Specific impulse only changes the propellant used, not the force."
        )
        hint.setWordWrap(True)
        set_role(hint, tone="secondary")
        form.addRow(hint)

        self.stack.addWidget(page)

    def _build_report_page(self, params: dict) -> None:
        """A checkable list of the series this scenario produces (real user
        feedback: typing series names from memory, where one typo fails
        the run). Nothing ticked means "snapshot every series"."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.report_summary_label = QLabel()
        layout.addWidget(self.report_summary_label)
        filter_row = QHBoxLayout()
        self.report_filter_edit = QLineEdit()
        self.report_filter_edit.setPlaceholderText("Filter, e.g. sat-1 or battery")
        self.report_filter_edit.setClearButtonEnabled(True)
        self.report_filter_edit.textChanged.connect(self._on_report_filter_changed)
        filter_row.addWidget(self.report_filter_edit, 1)
        self.report_clear_button = QPushButton("Clear selection")
        self.report_clear_button.setAutoDefault(False)
        self.report_clear_button.clicked.connect(self._on_report_clear)
        filter_row.addWidget(self.report_clear_button)
        layout.addLayout(filter_row)
        self.report_series_list = QListWidget()
        self.report_series_list.setMinimumHeight(220)  # [px]
        selected = [str(name) for name in params.get("series", [])]
        known = set(self._series_names)
        for name in self._series_names:
            self._add_report_item(name, name in selected)
        for name in selected:
            if name not in known:
                # Kept (so open + OK changes nothing) but flagged: the run
                # would fail on it.
                self._add_report_item(name, True, missing=True)
        if not self._series_names:
            self.report_series_list.setToolTip("Add spacecraft to the scenario to list their series here.")
        self.report_series_list.itemChanged.connect(lambda _item: self._update_report_summary())
        layout.addWidget(self.report_series_list, 1)
        self._update_report_summary()
        self.stack.addWidget(page)

    def _add_report_item(self, name: str, checked: bool, missing: bool = False) -> None:
        item = QListWidgetItem(f"{name}  (not produced by this scenario)" if missing else name)
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        if missing:
            tint(item, "status.critical.text")
            item.setToolTip("This scenario does not produce this series, so the run would stop here. "
                            "Untick it, or rename the spacecraft/device it refers to.")
        self.report_series_list.addItem(item)

    def report_selected_series(self) -> list[str]:
        return [self.report_series_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.report_series_list.count())
                if self.report_series_list.item(i).checkState() == Qt.CheckState.Checked]

    def _update_report_summary(self) -> None:
        count = len(self.report_selected_series())
        self.report_summary_label.setText(
            "Nothing ticked: every series is snapshotted." if count == 0
            else f"{count} series ticked." if count > 1 else "1 series ticked.")

    def _on_report_filter_changed(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.report_series_list.count()):
            item = self.report_series_list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_report_clear(self) -> None:
        for i in range(self.report_series_list.count()):
            self.report_series_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _build_conditional_page(self, params: dict) -> None:
        """Shared by ``if``/``while`` -- both take just a ``condition``
        expression string (see ``Command._validate_conditional``); which
        one this dialog is building for is chosen by the Kind combo, not
        this method.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(
            "A condition, e.g.  spacecraft['sat-1']['altitude_m'] < 400000\n"
            "Available: t_s (mission time, s), duration_days and, per spacecraft, r_BN_N, v_BN_N, altitude_m, "
            "mass_kg. Allowed: numbers, names, [ ] indexing, arithmetic, comparisons, and/or/not."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.condition_edit = QLineEdit(str(params.get("condition", "")))
        layout.addWidget(self.condition_edit)
        layout.addStretch(1)
        self.stack.addWidget(page)

    def _build_script_block_page(self, params: dict) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(
            "Python code, run without a sandbox. Only run scripts you trust: Run asks before it runs them."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.script_code_edit = QPlainTextEdit(str(params.get("code", "")))
        self.script_code_edit.setTabChangesFocus(True)
        set_role(self.script_code_edit, role="mono")
        layout.addWidget(self.script_code_edit)
        self.stack.addWidget(page)

    # -- (dis)assembly --------------------------------------------------------
    def _collect_params(self, kind: str) -> dict:
        if kind == "propagate":
            stop_condition = self.stop_condition_combo.currentText()
            params: dict = {"stop_condition": stop_condition}
            if stop_condition == "duration":
                params["duration_days"] = self.duration_days_spin.value()
            elif stop_condition == "epoch":
                params["stop_epoch_utc"] = self.stop_epoch_edit.text().strip()
            else:  # "event"
                params["event_kind"] = self.event_kind_combo.currentText()
                params["spacecraft"] = self.propagate_event_spacecraft_combo.currentText()
                if params["event_kind"] in PASS_EVENT_KINDS:
                    params["ground_station"] = self.propagate_event_station_combo.currentText()
            return params
        if kind == "maneuver":
            return {
                "spacecraft": self.maneuver_spacecraft_combo.currentText(),
                "delta_v_m_s": [self.delta_v_x_spin.value(), self.delta_v_y_spin.value(),
                                self.delta_v_z_spin.value()],
                "frame": self.maneuver_frame_combo.currentText(),
            }
        if kind == "lambert_transfer":
            return {
                "spacecraft": self.lambert_spacecraft_combo.currentText(),
                "target_position_m": [self.lambert_target_x_spin.value(), self.lambert_target_y_spin.value(),
                                       self.lambert_target_z_spin.value()],
                "time_of_flight_s": self.lambert_tof_spin.value(),
                "num_revolutions": self.lambert_num_rev_spin.value(),
                "max_distance_target_m": self.lambert_max_dist_spin.value(),
                "min_orbit_radius_m": self.lambert_min_radius_spin.value(),
            }
        if kind == "assignment":
            target = ".".join((
                self.assignment_spacecraft_combo.currentText(),
                self.assignment_controller_combo.currentText(),
                self.assignment_parameter_combo.currentText(),
            ))
            return {"target": target, "value": self.assignment_value_spin.value()}
        if kind == "report":
            return {"series": self.report_selected_series()}
        if kind in ("if", "while"):
            return {"condition": self.condition_edit.text().strip()}
        if kind == "script_block":
            return {"code": self.script_code_edit.toPlainText()}
        raise AssertionError(f"unhandled kind {kind!r} -- _KIND_PAGE_INDEX/SUPPORTED_COMMAND_KINDS out of sync")

    def _on_accept(self) -> None:
        try:
            self.to_dataclass()
        except ValueError as exc:
            show_dialog_error(self, f"This command is not valid: {exc}")
            return
        self.accept()

    def to_dataclass(self) -> Command:
        kind = self.kind_combo.currentText()
        label = self.label_edit.text().strip() or None
        # Command.validate()'s "assignment" check only requires a dotted
        # string (see schema.command.Command._validate_assignment) -- it
        # doesn't require the spacecraft segment itself to be non-empty,
        # unlike "maneuver"/propagate "event", which do reject a blank
        # spacecraft. With no spacecraft defined yet, assignment_spacecraft_
        # combo has no items and currentText() is "", which would otherwise
        # build a target like ".station_keeping.thrust_n" that silently
        # passes both Command.validate() and the scenario-level reference
        # check (schema.references._command_references skips an empty
        # name) -- caught only much later, deep into a mission_sequence
        # run. Reject it here instead, immediately, like the other two
        # spacecraft-name fields already are.
        if kind == "assignment" and not self.assignment_spacecraft_combo.currentText():
            raise ValueError("command: assignment.target must name a spacecraft -- add a spacecraft under "
                              "Resources first")
        command = Command(kind=kind, label=label, params=self._collect_params(kind))
        errors = command.validate("command")
        if errors:
            raise ValueError("\n".join(errors))
        return command


_KIND_TITLES = {
    "propagate": "Propagate", "maneuver": "Maneuver (impulsive burn)", "lambert_transfer": "Lambert transfer",
    "assignment": "Change a controller setting", "report": "Report", "if": "If", "while": "While",
    "script_block": "Python script",
}
_CONTAINER_KINDS = ("if", "while")


def _duration_text(days: float) -> str:
    """ "1 day", "2.5 days", "6 h", "30 min"."""
    if days >= 1.0:
        return f"{days:g} day" + ("" if days == 1.0 else "s")
    if days * 24.0 >= 1.0:
        return f"{days * 24.0:.3g} h"
    return f"{days * 1440.0:.3g} min"


def step_sentence(command: Command) -> str:
    """What a step does, in words (docs/ux-audit.md U-15): "Propagate until
    my-sat's next pass over berlin-gs starts". Never raises: a step whose
    parameters are wrong reads as its kind."""
    try:
        return _sentence(command.kind, command.params)
    except (TypeError, ValueError, KeyError, AttributeError, ZeroDivisionError):
        return _KIND_TITLES.get(command.kind, command.kind)


def _sentence(kind: str, p: dict) -> str:
    spacecraft = p.get("spacecraft") or "(no spacecraft)"
    if kind == "propagate":
        stop = p.get("stop_condition", "duration")
        if stop == "duration":
            return f"Propagate for {_duration_text(float(p.get('duration_days', 0.0)))}"
        if stop == "epoch":
            return f"Propagate until {p.get('stop_epoch_utc') or '(no epoch)'} UTC"
        event = p.get("event_kind", "")
        if event in PASS_EVENT_KINDS:
            station = p.get("ground_station") or "(no station)"
            return (f"Propagate until {spacecraft}'s next pass over {station} "
                    f"{'starts' if event == 'pass_start' else 'ends'}")
        return f"Propagate until {spacecraft}'s next {event}"
    if kind == "maneuver":
        delta_v = [float(v) for v in p.get("delta_v_m_s", [0.0, 0.0, 0.0])]
        size = sum(v * v for v in delta_v) ** 0.5  # [m/s]
        frame = p.get("frame", "inertial")
        return (f"Burn {size:.3g} m/s on {spacecraft} "
                f"({frame if frame == 'inertial' else frame.upper()} {', '.join(f'{v:g}' for v in delta_v)} m/s)")
    if kind == "lambert_transfer":
        return (f"Lambert transfer of {spacecraft} to the target in "
                f"{_duration_text(float(p.get('time_of_flight_s', 0.0)) / 86400.0)}")
    if kind == "assignment":
        target = str(p.get("target", ""))
        parts = target.split(".")
        value = p.get("value")
        if len(parts) == 3:
            return f"Set {parts[0]}'s {parts[1].replace('_', ' ')} {parts[2]} to {value:g}"
        return f"Set {target or '(no target)'} to {value}"
    if kind == "report":
        series = list(p.get("series", []))
        if not series:
            return "Report every series"
        return f"Report {series[0]}" if len(series) == 1 else f"Report {len(series)} series"
    if kind in _CONTAINER_KINDS:
        return f"{_KIND_TITLES[kind]} {p.get('condition') or '(no condition)'}"
    if kind == "script_block":
        lines = len(str(p.get("code", "")).splitlines())
        return f"Run a Python script ({lines} line{'' if lines == 1 else 's'})"
    return _KIND_TITLES.get(kind, kind)


class _StepTree(QTreeWidget):
    """The steps, reordered by dragging: a step drops between steps, or
    into an ``if``/``while`` (the only steps that take children)."""

    moved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setIconSize(QSize(18, 18))  # [px]

    def dropEvent(self, event) -> None:  # noqa: N802 -- Qt override
        item = self.currentItem()
        if event.source() is not self or item is None:
            event.ignore()
            return
        target = self.itemAt(event.position().toPoint())
        where = self.dropIndicatorPosition()
        # The move is made here, keeping the step's data and its children;
        # a copy action stops Qt from also removing the dragged row.
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        if self.move_into_place(item, target, where):
            self.moved.emit()

    def move_into_place(self, item: QTreeWidgetItem, target: QTreeWidgetItem | None, where) -> bool:
        """Move ``item`` above, below or (for an ``if``/``while``) into
        ``target``, or to the end when ``target`` is None. False, and
        nothing moved, for a drop into a step that takes no steps or into
        ``item`` itself."""
        position = QAbstractItemView.DropIndicatorPosition
        root = self.invisibleRootItem()
        if target is None or where == position.OnViewport:
            owner, index = root, root.childCount()
        elif where == position.OnItem:
            if not target.flags() & Qt.ItemFlag.ItemIsDropEnabled:
                return False
            owner, index = target, target.childCount()
        else:
            owner = target.parent() or root
            index = owner.indexOfChild(target) + (1 if where == position.BelowItem else 0)
        node = owner
        while node is not None:
            if node is item:
                return False
            node = node.parent()
        old_owner = item.parent() or root
        old_index = old_owner.indexOfChild(item)
        if old_owner is owner and old_index < index:
            index -= 1
        old_owner.takeChild(old_index)
        owner.insertChild(index, item)
        if owner is not root:
            owner.setExpanded(True)
        self._expand(item)  # a re-inserted row comes back collapsed
        self.setCurrentItem(item)
        return True

    def _expand(self, item: QTreeWidgetItem) -> None:
        item.setExpanded(True)
        for i in range(item.childCount()):
            self._expand(item.child(i))


class MissionSequenceEditorWidget(QWidget):
    """Edits a scenario's ``mission_sequence`` (docs/ux-audit.md U-15): the
    steps as a tree, each with its kind's icon, a sentence saying what it
    does and a checkbox that leaves it out of the run; the selected step's
    form beside it, applied as you type. Steps are reordered by dragging or
    with Move up / Move down, and nested inside an ``if``/``while`` with
    Add inside.

    A tree node's ``children`` are never read off the ``Command`` stored on
    it (``_new_item`` stores it with ``children`` cleared): the tree's own
    nesting is the structure.
    """

    changed = Signal()
    form_shown = Signal(object)  # the selected step's new form

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._spacecraft_names_provider = None
        self._series_names_provider = None
        self._ground_station_names_provider = None
        self._building = False
        self.form: _CommandEditorDialog | None = None
        self._form_item: QTreeWidgetItem | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)  # [ms] after the last edit
        self._timer.timeout.connect(self._apply_form)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, 1)

        steps = QWidget()
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        self.tree = _StepTree()
        on_change(self._retint)
        self.tree.setToolTip("Drag a step to move it, or into an if/while step to nest it. Untick a step to "
                             "leave it out of the run.")
        steps_layout.addWidget(self.tree, 1)

        edit_row = QHBoxLayout()
        self.add_button = QPushButton("Add step")
        self.add_button.setToolTip("Adds a step after the selected one.")
        self.add_button.setMenu(self._kind_menu(self._on_add_kind))
        self.add_child_button = QPushButton("Add inside")
        self.add_child_button.setToolTip("Adds a step inside the selected 'if'/'while' step.")
        self.add_child_button.setMenu(self._kind_menu(self._on_add_child_kind))
        self.duplicate_button = QPushButton("Duplicate")
        self.remove_button = QPushButton("Remove")
        self.move_up_button = QPushButton("Move up")
        self.move_up_button.setToolTip("Moves the step up (Alt+Up).")
        self.move_down_button = QPushButton("Move down")
        self.move_down_button.setToolTip("Moves the step down (Alt+Down).")
        for button in (self.add_button, self.add_child_button, self.duplicate_button, self.remove_button,
                       self.move_up_button, self.move_down_button):
            edit_row.addWidget(button)
        edit_row.addStretch(1)
        steps_layout.addLayout(edit_row)
        self.splitter.addWidget(steps)

        self.form_stack = QStackedWidget()
        self.empty_label = QLabel("Select a step to edit it here, or add one with Add step.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.form_stack.addWidget(self.empty_label)
        form_page = QWidget()
        form_layout = QVBoxLayout(form_page)
        form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_title = QLabel()
        self.form_title.setObjectName("sectionTitle")
        form_layout.addWidget(self.form_title)
        self.problem_banner = ProblemBanner()
        form_layout.addWidget(self.problem_banner)
        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        form_layout.addWidget(self.form_scroll, 1)
        self.form_stack.addWidget(form_page)
        self.splitter.addWidget(self.form_stack)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)

        self.duplicate_button.clicked.connect(self._on_duplicate)
        self.remove_button.clicked.connect(self._on_remove)
        self.move_up_button.clicked.connect(self._on_move_up)
        self.move_down_button.clicked.connect(self._on_move_down)
        QShortcut(QKeySequence("Alt+Up"), self.tree, self._on_move_up)
        QShortcut(QKeySequence("Alt+Down"), self.tree, self._on_move_down)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self.tree, self._on_remove)
        self.tree.currentItemChanged.connect(self._on_current_item)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.moved.connect(self._on_moved)
        self._update_button_states()

    _SIDE_BY_SIDE_PX = 1100  # [px] narrower than this, the form goes under the list

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt override
        """The form beside the list on a wide page, under it on a narrow one
        (1280 px with the tree and the side panel), so neither the steps'
        sentences nor the form is cut off."""
        super().resizeEvent(event)
        orientation = (Qt.Orientation.Horizontal if event.size().width() >= self._SIDE_BY_SIDE_PX
                       else Qt.Orientation.Vertical)
        if self.splitter.orientation() != orientation:
            self.splitter.setOrientation(orientation)

    # -- providers --------------------------------------------------------------------------------------------

    def set_spacecraft_names_provider(self, provider) -> None:
        """``provider`` is a zero-argument callable returning the
        scenario's current spacecraft names."""
        self._spacecraft_names_provider = provider

    def _spacecraft_names(self) -> list[str]:
        return sorted(self._spacecraft_names_provider()) if self._spacecraft_names_provider else []

    def set_ground_station_names_provider(self, provider) -> None:
        """Same convention as :meth:`set_spacecraft_names_provider`, for the
        propagate step's pass-event station picker."""
        self._ground_station_names_provider = provider

    def _ground_station_names(self) -> list[str]:
        return sorted(self._ground_station_names_provider()) if self._ground_station_names_provider else []

    def set_series_names_provider(self, provider) -> None:
        """``provider`` returns the series names the current scenario will
        produce (``engine.series_names.expected_series_names``), for the
        report step's pick-list."""
        self._series_names_provider = provider

    def _series_names(self) -> list[str]:
        return list(self._series_names_provider()) if self._series_names_provider else []

    # -- items ------------------------------------------------------------------------------------------------

    def _kind_menu(self, slot) -> QMenu:
        menu = QMenu(self)
        for kind in SUPPORTED_COMMAND_KINDS:
            action = menu.addAction(step_icon(kind), _KIND_TITLES.get(kind, kind))
            action.setData(kind)
        menu.triggered.connect(slot)
        return menu

    @staticmethod
    def command_of(item: QTreeWidgetItem) -> Command:
        return item.data(0, Qt.ItemDataRole.UserRole)

    @staticmethod
    def _item_text(command: Command) -> str:
        sentence = step_sentence(command)
        return f"{command.label}: {sentence}" if command.label else sentence

    def _new_item(self, command: Command) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        self._building = True
        try:
            flags = (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
                     | Qt.ItemFlag.ItemIsDragEnabled)
            if command.kind in _CONTAINER_KINDS:
                flags |= Qt.ItemFlag.ItemIsDropEnabled
            item.setFlags(flags)
            self._store(item, command)
        finally:
            self._building = False
        return item

    def _store(self, item: QTreeWidgetItem, command: Command) -> None:
        """Keep ``command`` (children cleared) on ``item`` and show it."""
        node_command = Command(kind=command.kind, label=command.label, params=dict(command.params),
                               enabled=command.enabled)
        building, self._building = self._building, True
        try:
            item.setData(0, Qt.ItemDataRole.UserRole, node_command)
            item.setText(0, self._item_text(node_command))
            item.setIcon(0, step_icon(node_command.kind))
            item.setCheckState(0, Qt.CheckState.Checked if node_command.enabled is not False
                               else Qt.CheckState.Unchecked)
            self._show_state(item)
        finally:
            self._building = building

    def _retint(self, _mode: str) -> None:
        retint(self.tree)

    def _show_state(self, item: QTreeWidgetItem) -> None:
        """A disabled step is greyed (and so are the steps inside it); a
        step with a problem is in the error colour, the problem in its
        tooltip."""
        command = self.command_of(item)
        errors = command.validate(self.path_of(item))
        off = not self._runs(item)
        tint(item, "status.critical.text" if errors else "text.secondary" if off else None)
        font = item.font(0)
        font.setItalic(off)
        item.setFont(0, font)
        tips = [f"{_KIND_TITLES.get(command.kind, command.kind)} step"]
        if off:
            tips.append("Left out of the run (unticked)" if not command.enabled
                        else "Left out of the run: a step it is inside is unticked")
        tips.extend(errors)
        item.setToolTip(0, "\n".join(tips))

    def _runs(self, item: QTreeWidgetItem) -> bool:
        node = item
        while node is not None:
            if not self.command_of(node).enabled:
                return False
            node = node.parent()
        return True

    def path_of(self, item: QTreeWidgetItem) -> str:
        """The step's path in the scenario, as problems name it:
        ``mission_sequence[2].children[0]``."""
        parts = []
        node = item
        while node is not None:
            parent = node.parent()
            index = parent.indexOfChild(node) if parent is not None else self.tree.indexOfTopLevelItem(node)
            parts.insert(0, f"[{index}]")
            node = parent
        return "mission_sequence" + ".children".join(parts)

    def item_at_path(self, path: str) -> QTreeWidgetItem | None:
        """The step a problem's path names (``mission_sequence[2].children[0]``,
        with or without a label after it), or None."""
        match = re.match(r"mission_sequence((?:\[\d+\])(?:\.children\[\d+\])*)", path)
        if not match:
            return None
        item = None
        for index in (int(i) for i in re.findall(r"\[(\d+)\]", match.group(1))):
            count = item.childCount() if item is not None else self.tree.topLevelItemCount()
            if index >= count:
                return None
            item = item.child(index) if item is not None else self.tree.topLevelItem(index)
        return item

    def _all_items(self, parent: QTreeWidgetItem | None = None):
        owner = parent if parent is not None else self.tree.invisibleRootItem()
        for i in range(owner.childCount()):
            child = owner.child(i)
            yield child
            yield from self._all_items(child)

    def _refresh_states(self) -> None:
        """Paths and enabled states change when steps move: re-check all."""
        for item in self._all_items():
            self._show_state(item)

    # -- editing ----------------------------------------------------------------------------------------------

    def _update_button_states(self) -> None:
        item = self.tree.currentItem()
        has_selection = item is not None
        for button in (self.duplicate_button, self.remove_button, self.move_up_button, self.move_down_button):
            button.setEnabled(has_selection)
        self.add_child_button.setEnabled(has_selection and self.command_of(item).kind in _CONTAINER_KINDS)

    def _default_command(self, kind: str) -> Command:
        """A new step of ``kind``, with the form's own defaults."""
        form = _CommandEditorDialog(spacecraft_names=self._spacecraft_names(), series_names=self._series_names(),
                                    ground_station_names=self._ground_station_names())
        form.kind_combo.setCurrentText(kind)
        command = Command(kind=kind, params=form._collect_params(kind))
        form.deleteLater()
        return command

    def add_step(self, kind: str, inside: bool = False) -> QTreeWidgetItem:
        """Add a ``kind`` step after the selected one (at the end when none
        is), or as the last step inside the selected ``if``/``while``; it is
        selected, its form shown."""
        self.flush()
        command = self._default_command(kind)
        item = self._new_item(command)
        current = self.tree.currentItem()
        if inside and current is not None and self.command_of(current).kind in _CONTAINER_KINDS:
            current.addChild(item)
            current.setExpanded(True)
        elif current is not None:
            owner = current.parent() or self.tree.invisibleRootItem()
            owner.insertChild(owner.indexOfChild(current) + 1, item)
        else:
            self.tree.addTopLevelItem(item)
        self._refresh_states()
        self.tree.setCurrentItem(item)
        show_toast(self.window(), f"Added step: {self._item_text(command)}")
        self.changed.emit()
        return item

    def _on_add_kind(self, action) -> None:
        self.add_step(action.data())

    def _on_add_child_kind(self, action) -> None:
        self.add_step(action.data(), inside=True)

    def _on_duplicate(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        self.flush()
        copy = self._build_tree_item(self._item_to_command(item))
        owner = item.parent() or self.tree.invisibleRootItem()
        owner.insertChild(owner.indexOfChild(item) + 1, copy)
        copy.setExpanded(True)
        self._refresh_states()
        self.tree.setCurrentItem(copy)
        self.changed.emit()

    def _on_remove(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        self._timer.stop()
        command = self.command_of(item)
        owner = item.parent() or self.tree.invisibleRootItem()
        owner.removeChild(item)
        self._refresh_states()
        show_toast(self.window(), f"Removed step: {self._item_text(command)}", kind="info")
        self.changed.emit()

    def _on_move_up(self) -> None:
        self._move(-1)

    def _on_move_down(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        self.flush()
        owner = item.parent() or self.tree.invisibleRootItem()
        index = owner.indexOfChild(item)
        new_index = index + delta
        if not 0 <= new_index < owner.childCount():
            return
        owner.takeChild(index)
        owner.insertChild(new_index, item)
        self.tree._expand(item)
        self._refresh_states()
        self.tree.setCurrentItem(item)
        self.changed.emit()

    def _on_moved(self) -> None:
        self._refresh_states()
        self._update_button_states()
        self._show_form_title()
        self.changed.emit()

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        """The checkbox was toggled."""
        if self._building:
            return
        command = self.command_of(item)
        enabled = item.checkState(0) == Qt.CheckState.Checked
        if command.enabled == enabled:
            return
        self._store(item, Command(kind=command.kind, label=command.label, params=dict(command.params),
                                  enabled=enabled))
        for child in self._all_items(item):
            self._show_state(child)
        self.changed.emit()

    # -- the selected step's form -----------------------------------------------------------------------------

    def _on_current_item(self, current: QTreeWidgetItem | None, _previous) -> None:
        self.flush()
        self._update_button_states()
        self._show_form(current)

    def _show_form(self, item: QTreeWidgetItem | None) -> None:
        if self.form is not None:
            self.form_scroll.takeWidget()
            self.form.deleteLater()
            self.form = None
        self._form_item = item
        if item is None:
            self.form_stack.setCurrentWidget(self.empty_label)
            return
        form = _CommandEditorDialog(command=self.command_of(item), spacecraft_names=self._spacecraft_names(),
                                    series_names=self._series_names(),
                                    ground_station_names=self._ground_station_names())
        embed_dialog(form)
        # The kind is fixed once a step exists, and the title above says it.
        form.kind_combo.hide()
        kind_label = form.findChild(QFormLayout).labelForField(form.kind_combo)
        if kind_label is not None:
            kind_label.hide()
        # Size the form by its own kind's page, not the widest of all kinds'.
        for i in range(form.stack.count()):
            if i != form.stack.currentIndex():
                form.stack.widget(i).setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.form = form
        self.form_scroll.setWidget(form)
        watch_edits(form, self._timer.start)
        self.form_stack.setCurrentIndex(1)
        self._show_form_title()
        self._show_form_problems()
        self.form_shown.emit(form)

    def _show_form_title(self) -> None:
        if self._form_item is not None:
            command = self.command_of(self._form_item)
            self.form_title.setText(f"{_KIND_TITLES.get(command.kind, command.kind)} -- "
                                    f"{self.path_of(self._form_item)}")

    def _show_form_problems(self) -> None:
        errors = self.command_of(self._form_item).validate(self.path_of(self._form_item))
        if errors:
            self.problem_banner.show_problem("\n".join(errors))
        else:
            self.problem_banner.hide()

    def _apply_form(self) -> None:
        """Store the form's step on its node: a wrong value too, which the
        tree, the banner and Problems then show."""
        item, form = self._form_item, self.form
        if item is None or form is None:
            return
        old = self.command_of(item)
        kind = old.kind
        command = Command(kind=kind, label=form.label_edit.text().strip() or None,
                          params=form._collect_params(kind), enabled=old.enabled)
        if command == old:
            return
        self._store(item, command)
        self._show_form_problems()
        self.changed.emit()

    def flush(self) -> None:
        """Apply the form now, if an edit is waiting."""
        if self._timer.isActive():
            self._timer.stop()
            self._apply_form()

    def show_step(self, path: str) -> bool:
        """Select the step a problem's path names and show its form."""
        item = self.item_at_path(path)
        if item is None:
            return False
        node = item.parent()
        while node is not None:
            node.setExpanded(True)
            node = node.parent()
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        return True

    # -- (dis)assembly ----------------------------------------------------------------------------------------

    def _item_to_command(self, item: QTreeWidgetItem) -> Command:
        command = self.command_of(item)
        children = [self._item_to_command(item.child(i)) for i in range(item.childCount())]
        return Command(kind=command.kind, label=command.label, params=dict(command.params), children=children,
                       enabled=command.enabled)

    def _build_tree_item(self, command: Command) -> QTreeWidgetItem:
        item = self._new_item(command)
        for child in command.children:
            item.addChild(self._build_tree_item(child))
        return item

    def to_command_list(self) -> list[Command]:
        self.flush()
        return [self._item_to_command(self.tree.topLevelItem(i)) for i in range(self.tree.topLevelItemCount())]

    def from_command_list(self, commands: list[Command]) -> None:
        self._timer.stop()
        self._show_form(None)
        self.tree.clear()
        for command in commands:
            self.tree.addTopLevelItem(self._build_tree_item(command))
        self.tree.expandAll()
        self._refresh_states()
        self._update_button_states()
