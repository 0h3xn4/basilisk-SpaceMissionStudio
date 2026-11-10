#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#

"""The 3D model editor's Equipment and Stowed tabs (model-analyses
decision D-24).

**Equipment** lists what is mounted on the model: the model's own items
(``model.equipment``: a camera, a nozzle, solar cells, a unit with a
mass), which are added, edited and deleted here, and the spacecraft's
sensors, actuators and RF antenna, whose mount (``mount``,
``rf_link.antenna_mount``) is edited here while the device itself stays
in its own editor. A device's position and boresight left unticked come
from its definition (a thruster's ``r_B`` and ``tHat_B``...), as the
analyses take them (decision D-03).

**Stowed** gives the selected part a stowed pose (folded for launch) and
switches the view between the deployed and stowed configurations.

Both tabs edit the objects they are given in place and emit ``changed``.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QMenu, QPushButton, QRadioButton, QToolButton, QVBoxLayout, QWidget)

from ..config import materials as library
from ..schema.scenario import EQUIPMENT_KINDS, MountConfig, MountedEquipmentConfig, PartPoseConfig, name_error
from .theme import set_role
from .widgets import ComboBox, NumberField

_BODY_FRAME = "Body frame (no part)"
_DEVICE_SOURCES = (("sensors", "sensor"), ("actuators", "actuator"))
_RF = "rf_link"


class _OptionalNumber(QWidget):
    """A tick box and a number: the value, or None when unticked."""

    changed = Signal()

    def __init__(self, unit: str, minimum: float, maximum: float, value: float, decimals: int = 2):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.check = QCheckBox()
        self.field = NumberField(unit, minimum=minimum, maximum=maximum, decimals=decimals, value=value)
        layout.addWidget(self.check)
        layout.addWidget(self.field, 1)
        self.check.toggled.connect(self._on_toggled)
        self.field.valueChanged.connect(lambda _v: self.changed.emit())
        self._on_toggled(False)

    def _on_toggled(self, on: bool) -> None:
        self.field.setEnabled(on)
        self.changed.emit()

    def value(self) -> float | None:
        return float(self.field.value()) if self.check.isChecked() else None

    def set_value(self, value: float | None) -> None:
        blocked = self.blockSignals(True)
        self.check.setChecked(value is not None)
        if value is not None:
            self.field.setValue(float(value))
        self.field.setEnabled(value is not None)
        self.blockSignals(blocked)


class _Vector(QWidget):
    """Three numbers, optionally behind a tick box (None when unticked)."""

    changed = Signal()

    def __init__(self, unit: str, minimum: float, maximum: float, decimals: int = 4, optional: bool = True):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.check = QCheckBox()
        self.check.setVisible(optional)
        self.check.setChecked(not optional)
        layout.addWidget(self.check)
        self.fields = [NumberField(unit, minimum=minimum, maximum=maximum, decimals=decimals, step=0.01)
                       for _ in range(3)]
        for field in self.fields:
            field.setMinimumWidth(70)  # [px] three to a row must fit the form column
            layout.addWidget(field, 1)
            field.valueChanged.connect(lambda _v: self.changed.emit())
        self.check.toggled.connect(self._on_toggled)

    def _on_toggled(self, on: bool) -> None:
        for field in self.fields:
            field.setEnabled(on)
        self.changed.emit()

    def set_optional(self, optional: bool) -> None:
        self.check.setVisible(optional)
        if not optional:
            self.check.setChecked(True)

    def value(self) -> list | None:
        return [float(f.value()) for f in self.fields] if self.check.isChecked() else None

    def set_value(self, value) -> None:
        blocked = self.blockSignals(True)
        self.check.setChecked(value is not None)
        for field, v in zip(self.fields, value if value is not None else (0.0, 0.0, 0.0)):
            field.setValue(float(v))
            field.setEnabled(value is not None)
        self.blockSignals(blocked)


class EquipmentTab(QWidget):
    """The mounted equipment of a model and of the spacecraft's devices
    (module docstring). ``devices`` has ``sensors``, ``actuators`` and
    ``rf_link`` (or is None: the model's own equipment only)."""

    changed = Signal()

    def __init__(self, model, devices=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._model, self._devices = model, devices
        self._rows: list = []  # (source, key): ("equipment", index), ("sensors", name), ...
        self._loading = False
        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_selected)
        left.addWidget(self.list)
        buttons = QHBoxLayout()
        self.add_button = QToolButton()
        self.add_button.setText("Add")
        self.add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.add_button)
        for kind in EQUIPMENT_KINDS:
            menu.addAction(kind.replace("_", " "), lambda k=kind: self.add_item(k))
        self.add_button.setMenu(menu)
        self.add_button.setToolTip("Equipment the scenario has no other definition for: a camera, a nozzle, solar "
                                   "cells, a unit with a mass")
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_item)
        self.mount_button = QPushButton("Mount on the model")
        self.mount_button.setToolTip("Give this device a place on the model, or take it away")
        self.mount_button.clicked.connect(self._on_toggle_mount)
        for button in (self.add_button, self.delete_button, self.mount_button):
            buttons.addWidget(button)
        left.addLayout(buttons)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._on_name_edited)
        form.addRow("Name", self.name_edit)
        self.kind_combo = ComboBox()
        for kind in EQUIPMENT_KINDS:
            self.kind_combo.addItem(kind.replace("_", " "), kind)
        self.kind_combo.currentIndexChanged.connect(self._on_edited)
        form.addRow("Kind", self.kind_combo)
        self.part_combo = ComboBox()
        self.part_combo.currentIndexChanged.connect(self._on_edited)
        self.part_combo.setToolTip("The part it moves with (to the stowed pose too); its position and boresight "
                                   "are then in that part's frame")
        form.addRow("On part", self.part_combo)
        self.position = _Vector("m", -100.0, 100.0)
        self.position.setToolTip("Unticked: from the device's definition (body frame, deployed)")
        form.addRow("Position", self.position)
        self.boresight = _Vector("", -1.0, 1.0)
        self.boresight.setToolTip("Unticked: from the device's definition. Normalized when used.")
        form.addRow("Boresight", self.boresight)
        self.fov = _OptionalNumber("deg", 0.01, 360.0, 20.0)
        self.fov.setToolTip("The full cone angle")
        form.addRow("Field of view", self.fov)
        self.exclusions = {name: _OptionalNumber("deg", 0.0, 180.0, 30.0) for name in ("sun", "earth", "moon")}
        for name, box in self.exclusions.items():
            box.setToolTip(f"Half-angle about the boresight inside which the {name.title()} blinds it "
                           "(no default: give the datasheet's)")
            form.addRow(f"{name.title()} exclusion", box)
        self.atmosphere = _OptionalNumber("km", 0.0, 1000.0, 0.0)
        self.atmosphere.setToolTip("Added to the Earth's radius for its bright limb")
        form.addRow("Earth atmosphere", self.atmosphere)
        self.plume = _OptionalNumber("deg", 0.01, 90.0, 15.0)
        self.plume.setToolTip("Thrusters: the plume cone's half-angle, along minus the boresight")
        form.addRow("Plume half-angle", self.plume)
        self.mass = NumberField("kg", minimum=0.0, maximum=1.0e5, decimals=3)
        self.mass.setToolTip("A point mass at the mount: it counts in the computed mass properties")
        form.addRow("Mass", self.mass)
        self.thrust = _OptionalNumber("N", 1.0e-6, 1.0e5, 1.0, decimals=4)
        form.addRow("Thrust", self.thrust)
        self.maturity = ComboBox()
        self.maturity.currentIndexChanged.connect(self._on_edited)
        form.addRow("Maturity", self.maturity)
        self.subsystem = QLineEdit()
        self.subsystem.editingFinished.connect(self._on_edited)
        form.addRow("Subsystem", self.subsystem)
        self.form_rows = form
        for widget in (self.position, self.boresight, self.fov, *self.exclusions.values(), self.atmosphere,
                       self.plume, self.thrust):
            widget.changed.connect(self._on_edited)
        self.mass.valueChanged.connect(self._on_edited)
        right.addLayout(form)
        self.note = QLabel()
        self.note.setWordWrap(True)
        set_role(self.note, tone="secondary")
        right.addWidget(self.note)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        set_role(self.problem, tone="caution")
        right.addWidget(self.problem)
        right.addStretch(1)
        self.form_widget = QWidget()
        self.form_widget.setLayout(right)
        layout.addWidget(self.form_widget, 2)
        self.refresh()

    # -- rows ------------------------------------------------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the list and the part choices (after a part was added,
        renamed or deleted), keeping the selection."""
        current = self._rows[self.list.currentRow()] if 0 <= self.list.currentRow() < len(self._rows) else None
        self._rows, labels = [], []
        for index, item in enumerate(self._model.equipment):
            self._rows.append(("equipment", index))
            labels.append(f"{item.name}  ({item.kind.replace('_', ' ')})")
        if self._devices is not None:
            for source, word in _DEVICE_SOURCES:
                for device in getattr(self._devices, source):
                    self._rows.append((source, device.name))
                    mounted = "" if getattr(device, "mount", None) is not None else ", not mounted"
                    labels.append(f"{device.name}  ({word}: {device.kind}{mounted})")
            if self._devices.rf_link is not None:
                self._rows.append((_RF, None))
                mounted = "" if self._devices.rf_link.antenna_mount is not None else ", not mounted"
                labels.append(f"RF antenna  (RF link{mounted})")
        blocked = self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems(labels)
        self.list.blockSignals(blocked)
        self._loading = True
        self.part_combo.clear()
        self.part_combo.addItem(_BODY_FRAME, "")
        for part in self._model.parts:
            self.part_combo.addItem(part.name, part.name)
        self.maturity.clear()
        self.maturity.addItem("(none)", "")
        policy = library.mass_policy(self._model.mass_budget.policy if self._model.mass_budget else "")
        for category in policy.categories:
            self.maturity.addItem(category, category)
        self._loading = False
        row = self._rows.index(current) if current in self._rows else (0 if self._rows else -1)
        self.list.setCurrentRow(row)
        self._on_selected(row)

    def _row(self):
        row = self.list.currentRow()
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def _device(self, row):
        source, key = row
        if source == _RF:
            return self._devices.rf_link
        return next(d for d in getattr(self._devices, source) if d.name == key)

    def _mount(self, row) -> MountConfig | None:
        source, key = row
        if source == "equipment":
            return self._model.equipment[key].mount
        device = self._device(row)
        return device.antenna_mount if source == _RF else getattr(device, "mount", None)

    def _set_mount(self, row, mount: MountConfig | None) -> None:
        device = self._device(row)
        if row[0] == _RF:
            device.antenna_mount = mount
        else:
            device.mount = mount

    def selected_name(self) -> str | None:
        """The selected item's name as the analyses know it (the view
        highlights it), or None."""
        row = self._row()
        if row is None:
            return None
        source, key = row
        if source == "equipment":
            return self._model.equipment[key].name
        return "rf antenna" if source == _RF else key

    def add_item(self, kind: str) -> MountedEquipmentConfig:
        """Add an item of the model's equipment and select it."""
        taken = {item.name for item in self._model.equipment}
        n = 1
        while f"{kind}-{n}" in taken:
            n += 1
        item = MountedEquipmentConfig(f"{kind}-{n}", kind, MountConfig(position_m=[0.0, 0.0, 0.0],
                                                                       boresight=[0.0, 0.0, 1.0]))
        self._model.equipment.append(item)
        self.refresh()
        self.list.setCurrentRow(self._rows.index(("equipment", len(self._model.equipment) - 1)))
        self.changed.emit()
        return item

    def delete_item(self) -> None:
        row = self._row()
        if row is None or row[0] != "equipment":
            return
        del self._model.equipment[row[1]]
        self.refresh()
        self.changed.emit()

    def _on_toggle_mount(self) -> None:
        row = self._row()
        if row is None or row[0] == "equipment":
            return
        self._set_mount(row, None if self._mount(row) is not None else MountConfig())
        self.refresh()
        self.changed.emit()

    # -- the form --------------------------------------------------------------------------------------------

    def _on_selected(self, _index: int) -> None:
        self._loading = True  # the form's own signals while it is set up are not edits
        try:
            self._show_row()
        finally:
            self._loading = False

    def _show_row(self) -> None:
        row = self._row()
        mount = self._mount(row) if row is not None else None
        equipment = row is not None and row[0] == "equipment"
        self.delete_button.setEnabled(equipment)
        self.mount_button.setEnabled(row is not None and not equipment)
        self.mount_button.setText("Remove the mount" if mount is not None and not equipment else "Mount on the model")
        self.form_widget.setEnabled(mount is not None)
        for widget in (self.name_edit, self.kind_combo, self.mass, self.thrust, self.maturity, self.subsystem):
            self.form_rows.setRowVisible(widget, equipment or row is None)
        self.position.set_optional(not equipment)
        self.boresight.set_optional(not equipment)
        self.problem.setText("")
        if row is None:
            self.note.setText("Nothing is mounted yet: Add puts an item of equipment on the model."
                              if self._devices is not None else "Add puts an item of equipment on the model.")
            return
        if equipment:
            self.note.setText("")
        elif mount is None:
            self.note.setText("Not mounted on the model: the analyses take this device's direction from its "
                              "definition, if it has one. Mount it to give it a part, a place or a field of view.")
        else:
            self.note.setText("The device itself is edited in its own editor; here, where it sits. A value left "
                              "unticked comes from its definition.")
        if mount is None:
            return
        if equipment:
            item = self._model.equipment[row[1]]
            self.name_edit.setText(item.name)
            self.kind_combo.setCurrentIndex(max(self.kind_combo.findData(item.kind), 0))
            self.mass.setValue(float(item.mass_kg))
            self.thrust.set_value(item.thrust_n)
            self.maturity.setCurrentIndex(max(self.maturity.findData(item.maturity), 0))
            self.subsystem.setText(item.subsystem)
        self.part_combo.setCurrentIndex(max(self.part_combo.findData(mount.part), 0))
        self.position.set_value(mount.position_m)
        self.boresight.set_value(mount.boresight)
        self.fov.set_value(mount.field_of_view_deg)
        for name, box in self.exclusions.items():
            box.set_value(getattr(mount, f"exclusion_{name}_deg"))
        self.atmosphere.set_value(mount.earth_atmosphere_km)
        self.plume.set_value(mount.plume_half_angle_deg)

    def _on_edited(self, *_args) -> None:
        if self._loading:
            return
        row = self._row()
        mount = self._mount(row) if row is not None else None
        if mount is None:
            return
        boresight = self.boresight.value()
        if boresight is not None and not any(boresight):
            self.problem.setText("The boresight must not be zero")
            return
        self.problem.setText("")
        mount.part = self.part_combo.currentData() or ""
        mount.position_m = self.position.value()
        mount.boresight = boresight
        mount.field_of_view_deg = self.fov.value()
        for name, box in self.exclusions.items():
            setattr(mount, f"exclusion_{name}_deg", box.value())
        mount.earth_atmosphere_km = self.atmosphere.value()
        mount.plume_half_angle_deg = self.plume.value()
        if row[0] == "equipment":
            item = self._model.equipment[row[1]]
            kind = self.kind_combo.currentData()
            if kind != item.kind:
                item.kind = kind
                self.list.item(self.list.currentRow()).setText(f"{item.name}  ({kind.replace('_', ' ')})")
            item.mass_kg = float(self.mass.value())
            item.thrust_n = self.thrust.value()
            item.maturity = self.maturity.currentData() or ""
            item.subsystem = self.subsystem.text().strip()
        self.changed.emit()

    def _on_name_edited(self) -> None:
        row = self._row()
        if self._loading or row is None or row[0] != "equipment":
            return
        item = self._model.equipment[row[1]]
        name = self.name_edit.text().strip()
        if name == item.name:
            return
        others = {other.name for other in self._model.equipment if other is not item}
        problem = name_error("equipment", name) or (f"another item is called {name!r}" if name in others else None)
        if problem:
            self.name_edit.setText(item.name)
            self.problem.setText(problem)
            return
        item.name = name
        self.list.item(self.list.currentRow()).setText(f"{name}  ({item.kind.replace('_', ' ')})")
        self.changed.emit()


class StowedTab(QWidget):
    """The selected part's stowed pose, and which configuration the view
    shows (module docstring)."""

    changed = Signal()
    configuration_changed = Signal(str)

    def __init__(self, model, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model
        self._part = None
        self._loading = False
        layout = QVBoxLayout(self)
        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Show the model"))
        self.view_group = QButtonGroup(self)
        self.view_buttons = {}
        for configuration, label in (("deployed", "deployed"), ("stowed", "stowed (for launch)")):
            button = QRadioButton(label)
            self.view_group.addButton(button)
            self.view_buttons[configuration] = button
            view_row.addWidget(button)
            button.toggled.connect(lambda on, c=configuration: on and self.configuration_changed.emit(c))
        self.view_buttons["deployed"].setChecked(True)
        view_row.addStretch(1)
        layout.addLayout(view_row)
        self.pose_check = QCheckBox("This part moves for launch (it has a stowed pose)")
        self.pose_check.toggled.connect(self._on_pose_toggled)
        layout.addWidget(self.pose_check)
        form = QFormLayout()
        self.position = _Vector("m", -100.0, 100.0, optional=False)
        self.rotation = _Vector("deg", -360.0, 360.0, decimals=3, optional=False)
        form.addRow("Stowed position of the part", self.position)
        form.addRow("Stowed rotation (roll, pitch, yaw)", self.rotation)
        self.position.changed.connect(self._on_edited)
        self.rotation.changed.connect(self._on_edited)
        layout.addLayout(form)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        set_role(self.summary, tone="secondary")
        layout.addWidget(self.summary)
        layout.addStretch(1)
        self.show_part(None)

    def configuration(self) -> str:
        return "stowed" if self.view_buttons["stowed"].isChecked() else "deployed"

    def _pose(self):
        if self._part is None:
            return None
        return next((p for p in self._model.stowed if p.part == self._part.name), None)

    def show_part(self, part) -> None:
        """The stowed pose of ``part`` (a ``ModelPartConfig``, or None)."""
        self._part = part
        pose = self._pose()
        self._loading = True
        self.pose_check.setEnabled(part is not None)
        self.pose_check.setText(f"{part.name} moves for launch (it has a stowed pose)" if part is not None
                                else "Select a part to give it a stowed pose")
        self.pose_check.setChecked(pose is not None)
        self.position.set_value(pose.position_b_m if pose else (part.position_b_m if part else None))
        self.rotation.set_value(pose.rotation_deg if pose else (part.rotation_deg if part else None))
        for vector in (self.position, self.rotation):
            vector.setEnabled(pose is not None)
        self._loading = False
        posed = [p.part for p in self._model.stowed]
        self.summary.setText(("Stowed poses: " + ", ".join(posed) + ". " if posed else "No part has a stowed pose: "
                              "stowed, the model is as deployed. ")
                             + "A part without one stays where it is; equipment mounted on a part moves with it. "
                             "The launcher envelope is checked against the stowed configuration.")

    def _on_pose_toggled(self, on: bool) -> None:
        if self._loading or self._part is None:
            return
        pose = self._pose()
        if on and pose is None:
            self._model.stowed.append(PartPoseConfig(self._part.name, list(self._part.position_b_m),
                                                     list(self._part.rotation_deg)))
        elif not on and pose is not None:
            self._model.stowed.remove(pose)
        self.show_part(self._part)
        self.changed.emit()

    def _on_edited(self) -> None:
        pose = self._pose()
        if self._loading or pose is None:
            return
        pose.position_b_m = self.position.value()
        pose.rotation_deg = self.rotation.value()
        self.changed.emit()
