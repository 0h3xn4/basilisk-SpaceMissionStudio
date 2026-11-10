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

"""The rest of the 3D model editor's model data (model-analyses decision
D-25), which until now only the scenario file's JSON view edited:

- :class:`MaterialsTab`: the model's own materials (``model.materials``),
  beside the library's sourced ones, which are always available;
- :class:`BudgetLauncherTab`: the mass budget (``model.mass_budget``: the
  margin policy, a system margin, the mass limit and its source) and the
  launcher envelope (``model.launcher``);
- :class:`FacePropertiesTable`: in the part form, a material and
  reflection coefficients per face of the part, in place of the part's
  (``model.face_properties``).

Each edits the model it is given in place and emits ``changed``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..config import envelopes as envelope_library
from ..config import materials as library
from ..schema.scenario import (LAUNCHER_SHAPES, MATERIAL_FIELDS, MODEL_SHAPE_FACES, FacePropertyConfig,
                               LauncherConfig, MassBudgetConfig, MaterialConfig)
from .model_equipment_tabs import _OptionalNumber, _Vector
from .theme import set_role
from .widgets import ComboBox

_NO_MATERIAL = "(none)"
_PART_VALUE = "(the part's)"
# The material fields' labels and the ranges their fields take (the schema checks >= 0, and <= 1 for the two).
_MATERIAL_LABELS = {"density_kg_m3": ("Density", "kg/m³", 1.0e5, 1), "melting_temperature_k": ("Melting point", "K",
                                                                                                1.0e4, 1),
                    "heat_of_fusion_j_kg": ("Heat of fusion", "J/kg", 1.0e8, 0),
                    "specific_heat_j_kg_k": ("Specific heat", "J/(kg·K)", 1.0e5, 1),
                    "emissivity": ("Emissivity", "", 1.0, 3), "solar_absorptance": ("Solar absorptance", "", 1.0, 3),
                    "ao_erosion_yield_cm3_atom": ("AO erosion yield", "×10⁻²⁴ cm³/atom", 1.0e4, 3)}
# The erosion yield is shown in units of 1e-24 cm^3/atom (Kapton H's is 3.0 of them): the stored value is the
# shown one divided by this, so 3.0 is stored as exactly 3e-24.
_PER_UNIT = {"ao_erosion_yield_cm3_atom": 1.0e24}


def material_names(model) -> list[str]:
    """Every material a part or face may name: the library's, then the
    model's own."""
    return [*library.MATERIALS, *(m.name for m in model.materials if m.name not in library.MATERIALS)]


def fill_material_combo(combo: ComboBox, model, current: str, empty_label: str = _NO_MATERIAL) -> None:
    """``combo`` with no material, the library's and the model's own,
    ``current`` selected."""
    blocked = combo.blockSignals(True)
    combo.clear()
    combo.addItem(empty_label, "")
    for name in library.MATERIALS:
        combo.addItem(f"{name} ({library.MATERIALS[name].description})", name)
    for material in model.materials:
        if material.name not in library.MATERIALS:
            combo.addItem(f"{material.name} (the model's own)", material.name)
    index = combo.findData(current)
    if index < 0 and current:  # a name the model no longer has: kept, so it is seen and refused on OK
        combo.addItem(f"{current} (unknown)", current)
        index = combo.count() - 1
    combo.setCurrentIndex(max(index, 0))
    combo.blockSignals(blocked)


class MaterialsTab(QWidget):
    """The model's own materials (module docstring)."""

    changed = Signal()

    def __init__(self, model, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model
        self._loading = False
        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        note = QLabel(f"The library's {len(library.MATERIALS)} sourced materials are always available "
                      "(docs/models/materials.md). Add your own here, with where its values come from.")
        note.setWordWrap(True)
        set_role(note, tone="secondary")
        left.addWidget(note)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_selected)
        left.addWidget(self.list)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_material)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_material)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        left.addLayout(buttons)
        layout.addLayout(left, 1)
        self.form_widget = QWidget()
        right = QVBoxLayout(self.form_widget)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._on_name_edited)
        form.addRow("Name", self.name_edit)
        self.fields = {}
        for name, _unit in MATERIAL_FIELDS:
            label, unit, maximum, decimals = _MATERIAL_LABELS[name]
            box = _OptionalNumber(unit, 0.0, maximum, 0.0, decimals=decimals)
            box.changed.connect(self._on_edited)
            self.fields[name] = box
            form.addRow(label, box)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Where the values come from: a datasheet, a handbook, a test report")
        self.source_edit.editingFinished.connect(self._on_edited)
        form.addRow("Source", self.source_edit)
        right.addLayout(form)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        set_role(self.problem, tone="caution")
        right.addWidget(self.problem)
        right.addStretch(1)
        layout.addWidget(self.form_widget, 2)
        self.refresh()

    def refresh(self) -> None:
        row = self.list.currentRow()
        blocked = self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems([m.name for m in self._model.materials])
        self.list.blockSignals(blocked)
        row = min(max(row, 0), len(self._model.materials) - 1)
        self.list.setCurrentRow(row)
        self._on_selected(row)

    def _material(self) -> MaterialConfig | None:
        row = self.list.currentRow()
        return self._model.materials[row] if 0 <= row < len(self._model.materials) else None

    def _users(self, name: str) -> list[str]:
        """The parts and faces that name material ``name``."""
        users = [f"part {p.name!r}" for p in self._model.parts if p.material == name]
        return users + [f"{f.part}: {f.face}" for f in self._model.face_properties if f.material == name]

    def add_material(self) -> MaterialConfig:
        taken = set(material_names(self._model))
        n = 1
        while f"material-{n}" in taken:
            n += 1
        material = MaterialConfig(f"material-{n}")
        self._model.materials.append(material)
        self.refresh()
        self.list.setCurrentRow(len(self._model.materials) - 1)
        self.changed.emit()
        return material

    def delete_material(self) -> None:
        material = self._material()
        if material is None:
            return
        users = self._users(material.name)
        if users:
            self.problem.setText(f"{material.name!r} is used by {', '.join(users)}: give them another material "
                                 "before deleting it")
            return
        self._model.materials.remove(material)
        self.refresh()
        self.changed.emit()

    def _on_selected(self, _row: int) -> None:
        material = self._material()
        self.form_widget.setEnabled(material is not None)
        self.delete_button.setEnabled(material is not None)
        self.problem.setText("")
        if material is None:
            return
        self._loading = True
        self.name_edit.setText(material.name)
        for name, box in self.fields.items():
            value = getattr(material, name)
            box.set_value(None if value is None else round(value * _PER_UNIT.get(name, 1.0), 9))
        self.source_edit.setText(material.source)
        self._loading = False

    def _on_edited(self, *_args) -> None:
        material = self._material()
        if self._loading or material is None:
            return
        for name, box in self.fields.items():
            value = box.value()
            setattr(material, name, None if value is None else value / _PER_UNIT.get(name, 1.0))
        material.source = self.source_edit.text().strip()
        self.changed.emit()

    def _on_name_edited(self) -> None:
        material = self._material()
        if self._loading or material is None:
            return
        name = self.name_edit.text().strip()
        if name == material.name:
            return
        problem = ("a material needs a name" if not name else
                   f"{name!r} is a library material: pick another name" if name in library.MATERIALS else
                   f"another material is called {name!r}" if name in {m.name for m in self._model.materials} else None)
        if problem:
            self.name_edit.setText(material.name)
            self.problem.setText(problem)
            return
        old = material.name
        for part in self._model.parts:  # the parts and faces that use it follow the rename
            if part.material == old:
                part.material = name
        for face in self._model.face_properties:
            if face.material == old:
                face.material = name
        material.name = name
        self.list.item(self.list.currentRow()).setText(name)
        self.problem.setText("")
        self.changed.emit()


class FacePropertiesTable(QTableWidget):
    """A part's faces, each with a material and reflection coefficients in
    place of the part's (blank: the part's); see the module docstring."""

    changed = Signal()

    def __init__(self, model, part, parent: QWidget | None = None):
        super().__init__(0, 4, parent)
        self._model, self._part = model, part
        self._loading = True
        self.setHorizontalHeaderLabels(["Face", "Material", "Diffuse", "Specular"])
        self.verticalHeader().setVisible(False)
        self.setToolTip("Blank: the part's own material and coefficients. A face's diffuse and specular "
                        "reflection must sum to at most 1.")
        for face in MODEL_SHAPE_FACES[part.shape]:
            row = self.rowCount()
            self.insertRow(row)
            label = QTableWidgetItem(face)
            label.setFlags(label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(row, 0, label)
            entry = self._entry(face)
            combo = ComboBox()
            fill_material_combo(combo, model, entry.material if entry else "", empty_label=_PART_VALUE)
            combo.currentIndexChanged.connect(lambda _i, f=face: self._on_edited(f))
            self.setCellWidget(row, 1, combo)
            for column, name in ((2, "diffuse_coeff"), (3, "specular_coeff")):
                value = getattr(entry, name) if entry else None
                self.setItem(row, column, QTableWidgetItem("" if value is None else f"{value:g}"))
        self.itemChanged.connect(lambda item: self._on_edited(self.item(item.row(), 0).text()))
        self.resizeColumnsToContents()
        self._loading = False
        self.problem = ""

    def _entry(self, face: str) -> FacePropertyConfig | None:
        return next((f for f in self._model.face_properties if f.part == self._part.name and f.face == face), None)

    def _on_edited(self, face: str) -> None:
        if self._loading:
            return
        row = MODEL_SHAPE_FACES[self._part.shape].index(face)
        material = self.cellWidget(row, 1).currentData() or ""
        values = {}
        for column, name in ((2, "diffuse_coeff"), (3, "specular_coeff")):
            text = self.item(row, column).text().strip().replace(",", ".") if self.item(row, column) else ""
            try:
                value = float(text) if text else None
            except ValueError:
                value = None
            if value is not None and not 0.0 <= value <= 1.0:
                value = None
            if text and value is None:
                self.problem = f"{face}: {name.split('_')[0]} must be a number in [0, 1]"
                return
            values[name] = value
        self.problem = ""
        entry = self._entry(face)
        if not material and values["diffuse_coeff"] is None and values["specular_coeff"] is None:
            if entry is not None:
                self._model.face_properties.remove(entry)
        elif entry is None:
            self._model.face_properties.append(FacePropertyConfig(self._part.name, face, material, **values))
        else:
            entry.material = material
            entry.diffuse_coeff, entry.specular_coeff = values["diffuse_coeff"], values["specular_coeff"]
        self.changed.emit()


class BudgetLauncherTab(QWidget):
    """The mass budget and the launcher envelope (module docstring)."""

    changed = Signal()
    policy_changed = Signal()

    def __init__(self, model, parent: QWidget | None = None):
        super().__init__(parent)
        self._model = model
        self._loading = True
        layout = QHBoxLayout(self)

        self.budget_group = QGroupBox("Mass budget")
        self.budget_group.setCheckable(True)
        self.budget_group.setToolTip("Unticked: the default policy and no mass limit")
        budget = QFormLayout(self.budget_group)
        self.policy = ComboBox()
        for key, policy in library.MASS_MARGIN_POLICIES.items():
            self.policy.addItem(policy.name, key)
        self.policy.setToolTip("The margin policy: its maturity categories are the ones parts and equipment take")
        budget.addRow("Margin policy", self.policy)
        self.system_margin = _OptionalNumber("%", 0.0, 100.0, 0.0)
        self.system_margin.setToolTip("Unticked: the policy's own system margin")
        budget.addRow("System margin", self.system_margin)
        self.mass_limit = _OptionalNumber("kg", 0.001, 1.0e6, 100.0, decimals=3)
        budget.addRow("Mass limit", self.mass_limit)
        self.limit_source = QLineEdit()
        self.limit_source.setPlaceholderText("Where the limit comes from: a launcher's guide, a port's rating")
        budget.addRow("Limit source", self.limit_source)
        layout.addWidget(self.budget_group, 1)

        self.launcher_group = QGroupBox("Launcher envelope (the stowed configuration is checked)")
        self.launcher_group.setCheckable(True)
        launcher = QFormLayout(self.launcher_group)
        self.envelope = ComboBox()
        self.envelope.addItem("Custom (the dimensions below)", "custom")
        for key, envelope in envelope_library.ENVELOPES.items():
            self.envelope.addItem(envelope.name, key)
        if not envelope_library.ENVELOPES:
            self.envelope.setToolTip("No launcher's envelope could be sourced yet (decision D-11): give your own")
        launcher.addRow("Envelope", self.envelope)
        self.shape = ComboBox()
        for shape in LAUNCHER_SHAPES:
            self.shape.addItem(shape, shape)
        launcher.addRow("Shape", self.shape)
        self.dimensions = {name: _OptionalNumber("m", 0.001, 100.0, 1.0, decimals=4)
                           for name in ("diameter_m", "height_m", "width_m", "depth_m")}
        for name, label in (("diameter_m", "Diameter"), ("height_m", "Height"), ("width_m", "Width"),
                            ("depth_m", "Depth")):
            launcher.addRow(label, self.dimensions[name])
        self.profile = QTableWidget(0, 2)
        self.profile.setHorizontalHeaderLabels(["Height [m]", "Radius [m]"])
        self.profile.verticalHeader().setVisible(False)
        self.profile.setToolTip("Points of an axisymmetric envelope, from the separation plane up: rising heights")
        profile_buttons = QHBoxLayout()
        add_point = QPushButton("Add point")
        add_point.clicked.connect(self._add_profile_point)
        remove_point = QPushButton("Remove point")
        remove_point.clicked.connect(self._remove_profile_point)
        profile_buttons.addWidget(add_point)
        profile_buttons.addWidget(remove_point)
        profile_buttons.addStretch(1)
        profile_widget = QWidget()
        profile_layout = QVBoxLayout(profile_widget)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.addWidget(self.profile)
        profile_layout.addLayout(profile_buttons)
        launcher.addRow("Profile", profile_widget)
        self.origin = _Vector("m", -100.0, 100.0, optional=False)
        self.origin.setToolTip("The separation plane's centre, in the body frame")
        launcher.addRow("Separation plane at", self.origin)
        self.axis = _Vector("", -1.0, 1.0, optional=False)
        self.axis.setToolTip("Up the envelope, from the separation plane (normalized)")
        launcher.addRow("Axis", self.axis)
        self.width_axis = _Vector("", -1.0, 1.0, optional=False)
        launcher.addRow("Width axis (box)", self.width_axis)
        self.launcher_mass = _OptionalNumber("kg", 0.001, 1.0e6, 100.0, decimals=3)
        launcher.addRow("Mass limit", self.launcher_mass)
        self.com_height = _OptionalNumber("m", 0.001, 100.0, 1.0, decimals=4)
        launcher.addRow("Centre of mass height limit", self.com_height)
        self.com_lateral = _OptionalNumber("m", 0.001, 100.0, 0.01, decimals=4)
        launcher.addRow("Centre of mass lateral limit", self.com_lateral)
        self.launcher_source = QLineEdit()
        self.launcher_source.setPlaceholderText("Where the envelope and limits come from")
        launcher.addRow("Source", self.launcher_source)
        self.launcher_form = launcher
        layout.addWidget(self.launcher_group, 2)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        set_role(self.problem, tone="caution")
        launcher.addRow(self.problem)

        self.load()
        self.budget_group.toggled.connect(self._on_budget_edited)
        self.policy.currentIndexChanged.connect(self._on_budget_edited)
        self.system_margin.changed.connect(self._on_budget_edited)
        self.mass_limit.changed.connect(self._on_budget_edited)
        self.limit_source.editingFinished.connect(self._on_budget_edited)
        self.launcher_group.toggled.connect(self._on_launcher_edited)
        for widget in (self.envelope, self.shape):
            widget.currentIndexChanged.connect(self._on_launcher_edited)
        for widget in (*self.dimensions.values(), self.origin, self.axis, self.width_axis, self.launcher_mass,
                       self.com_height, self.com_lateral):
            widget.changed.connect(self._on_launcher_edited)
        self.profile.itemChanged.connect(self._on_launcher_edited)
        self.launcher_source.editingFinished.connect(self._on_launcher_edited)

    def load(self) -> None:
        """Show the model's mass budget and launcher."""
        self._loading = True
        budget = self._model.mass_budget
        self.budget_group.setChecked(budget is not None)
        b = budget or MassBudgetConfig()
        self.policy.setCurrentIndex(max(self.policy.findData(b.policy), 0))
        self.system_margin.set_value(b.system_margin_percent)
        self.mass_limit.set_value(b.mass_limit_kg)
        self.limit_source.setText(b.limit_source)
        launcher = self._model.launcher
        self.launcher_group.setChecked(launcher is not None)
        c = launcher or LauncherConfig()
        self.envelope.setCurrentIndex(max(self.envelope.findData(c.envelope), 0))
        self.shape.setCurrentIndex(max(self.shape.findData(c.shape), 0))
        for name, box in self.dimensions.items():
            box.set_value(getattr(c, name))
        self.profile.setRowCount(0)
        for height, radius in c.profile:
            self._append_point(height, radius)
        self.origin.set_value(c.origin_b_m)
        self.axis.set_value(c.axis_b)
        self.width_axis.set_value(c.width_axis_b)
        self.launcher_mass.set_value(c.mass_limit_kg)
        self.com_height.set_value(c.com_height_limit_m)
        self.com_lateral.set_value(c.com_lateral_limit_m)
        self.launcher_source.setText(c.source)
        self._loading = False
        self._show_shape_rows()

    def _show_shape_rows(self) -> None:
        custom = self.envelope.currentData() == "custom"
        shape = self.shape.currentData()
        needs = {"cylinder": ("diameter_m", "height_m"), "box": ("width_m", "depth_m", "height_m"),
                 "profile": ()}[shape]
        self.launcher_form.setRowVisible(self.shape, custom)
        for name, box in self.dimensions.items():
            self.launcher_form.setRowVisible(box, custom and name in needs)
        self.launcher_form.setRowVisible(self.profile.parentWidget(), custom and shape == "profile")
        self.launcher_form.setRowVisible(self.width_axis, custom and shape == "box")

    def _append_point(self, height: float, radius: float) -> None:
        row = self.profile.rowCount()
        self.profile.insertRow(row)
        self.profile.setItem(row, 0, QTableWidgetItem(f"{height:g}"))
        self.profile.setItem(row, 1, QTableWidgetItem(f"{radius:g}"))

    def _add_profile_point(self) -> None:
        last = self._profile_points()
        height = last[-1][0] + 0.5 if last else 0.0  # [m] half a metre above the last point
        radius = last[-1][1] if last else 1.0  # [m]
        self._append_point(height, radius)

    def _remove_profile_point(self) -> None:
        if self.profile.currentRow() >= 0:
            self.profile.removeRow(self.profile.currentRow())
            self._on_launcher_edited()

    def _profile_points(self) -> list:
        points = []
        for row in range(self.profile.rowCount()):
            cells = [self.profile.item(row, c).text().strip().replace(",", ".") if self.profile.item(row, c)
                     else "" for c in range(2)]
            points.append([float(cells[0]), float(cells[1])])
        return points

    def _on_budget_edited(self, *_args) -> None:
        if self._loading:
            return
        old = self._model.mass_budget.policy if self._model.mass_budget is not None else ""
        if not self.budget_group.isChecked():
            self._model.mass_budget = None
        else:
            self._model.mass_budget = MassBudgetConfig(
                policy=self.policy.currentData() or "", system_margin_percent=self.system_margin.value(),
                mass_limit_kg=self.mass_limit.value(), limit_source=self.limit_source.text().strip())
        new = self._model.mass_budget.policy if self._model.mass_budget is not None else ""
        if new != old:
            self.policy_changed.emit()
        self.changed.emit()

    def _on_launcher_edited(self, *_args) -> None:
        if self._loading:
            return
        self._show_shape_rows()
        if not self.launcher_group.isChecked():
            self._model.launcher = None
            self.problem.setText("")
            self.changed.emit()
            return
        try:
            profile = self._profile_points()
        except ValueError:
            self.problem.setText("A profile point is not a number")
            return
        self.problem.setText("")
        envelope = self.envelope.currentData()
        dims = {name: box.value() for name, box in self.dimensions.items()}
        self._model.launcher = LauncherConfig(
            envelope=envelope, shape=self.shape.currentData(), **dims, profile=profile,
            origin_b_m=self.origin.value(), axis_b=self.axis.value(), width_axis_b=self.width_axis.value(),
            mass_limit_kg=self.launcher_mass.value(), com_height_limit_m=self.com_height.value(),
            com_lateral_limit_m=self.com_lateral.value(), source=self.launcher_source.text().strip())
        self.changed.emit()
