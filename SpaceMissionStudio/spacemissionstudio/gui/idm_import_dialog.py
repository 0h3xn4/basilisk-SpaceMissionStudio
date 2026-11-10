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
"""The 3D model editor's **Import IDM-CIC model...** dialog: choose a
``.idm`` file (IDM-CIC is (c) CNES), the configuration, an optional
stowed configuration and the body element, and see what the import will
do before it is applied. The file is read and the import planned in a
worker thread (``spacemissionstudio.idm``, ``idm_import.plan``); the
editor merges the plan into its model (``idm_import.merge``).

**Devices found** lists the equipment whose names name a sensor or
actuator (``spacemissionstudio.idm_devices``): for each, whether to add it
to the spacecraft, the axis of its equipment frame that is its boresight
or spin axis, and the catalog product whose values it takes (none: the
device runs with Basilisk's defaults until its values are set, and the
pre-run checks say so). A thruster goes to the 3D model's equipment
(decision IDM-32): placed at the start of its plume cone, thrusting
against it, with the thrust of its product or mapped property; one whose
shapes show no plume cone is added only when ticked, along the axis
chosen. Solar arrays and batteries are listed, not added.
:meth:`IdmImportDialog.device_choices` is what was chosen.

**Power** offers what the model says of the power budget
(``idm_import.PowerPlan``): the bus load as the power of the imported
equipment in one of the model's system modes (or their duty-cycle
average, when the duty cycles add up to one), and the panel area and
normal from the solar array panels found, with the side carrying the
cells chosen (the file does not say), and the battery capacity from the
batteries' mapped capacity property. Nothing is set unless ticked.
:meth:`IdmImportDialog.power_choice` is what was chosen.

**Properties** lists the properties the devices' equipment carry in the
model (``idm.properties``), one row per name: for each, the value it gives
(**Use as**, ``idm_properties.TARGETS``) and the unit its values are in,
which the user chooses (one is offered only when the property's type has
the value's dimension). :meth:`IdmImportDialog.property_mappings` is the
mapping; the devices' rows and the battery choice follow it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .theme import set_role
from .widgets import ComboBox

CREDIT = ("Reads IDM-CIC models (IDM-CIC is © CNES) with SpaceMissionStudio's own reader. SpaceMissionStudio "
          "is not affiliated with or endorsed by CNES.")
_DEFAULT = ""  # the combo data for "the default values" / "chosen" / "none"


class _Worker(QThread):
    """Reads the file (when no model is given) and plans the import."""

    finished_ok = Signal(object, object)  # model, plan
    failed = Signal(str)

    def __init__(self, path, model, options: dict, parent=None):
        super().__init__(parent)
        self._path, self._model, self._options = path, model, options

    def run(self) -> None:
        from .. import idm, idm_import

        try:
            model = self._model or idm.load(self._path)
            self.finished_ok.emit(model, idm_import.plan(model, **self._options))
        except idm.IdmError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 -- shown in the dialog
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class IdmImportDialog(QDialog):
    """See the module docstring. :meth:`plan` is the accepted plan."""

    DEVICE_COLUMNS = ("Add", "Equipment", "Subsystem", "Kind", "Axis", "Catalog product", "Note")
    PROPERTY_COLUMNS = ("Property", "Type", "On", "Values", "Use as", "Unit", "Note")

    def __init__(self, path=None, parent: QWidget | None = None, start_dir=None, devices_allowed: bool = True,
                 mappings=None, origin: str = "element"):
        super().__init__(parent)
        self._initial_mappings = list(mappings or [])  # an earlier import's (idm_import.recorded_mappings)
        self._mapping_problem = ""
        self._blocked: dict = {}  # {device row: True while it cannot be added}
        self.setWindowTitle("Import IDM-CIC model")
        self.resize(900, 720)
        self._devices_allowed = devices_allowed
        self._start_dir = Path(start_dir) if start_dir else None
        self._path: Path | None = None
        self._model = None
        self._plan = None
        self._worker: _Worker | None = None
        self._again = False
        layout = QVBoxLayout(self)
        self.credit = set_role(QLabel(CREDIT), tone="secondary")
        self.credit.setWordWrap(True)
        layout.addWidget(self.credit)
        form = QFormLayout()
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Choose an .idm file")
        row.addWidget(self.path_edit, 1)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_browse)
        row.addWidget(browse)
        form.addRow("Model file", row)
        self.configuration_combo = ComboBox()
        self.configuration_combo.setToolTip("The configuration whose articulations, fillings and optional units are "
                                            "imported")
        form.addRow("Configuration", self.configuration_combo)
        self.stowed_combo = ComboBox()
        self.stowed_combo.setToolTip("A second configuration (e.g. the launch one) whose poses become the model's "
                                     "stowed configuration")
        form.addRow("Stowed configuration", self.stowed_combo)
        self.body_combo = ComboBox()
        self.body_combo.setToolTip("The element whose frame becomes the body frame; the elements mounted on it come "
                                   "with it")
        form.addRow("Body element", self.body_combo)
        self.facets_check = QCheckBox("Build drag and solar pressure facets from the imported shapes")
        self.facets_check.setToolTip("Off by default: the file gives no surface coefficients, so the parts keep "
                                     "the default ones")
        form.addRow("", self.facets_check)
        self.origin_combo = ComboBox()
        self.origin_combo.addItem("The body element's frame (as in IDM-CIC)", "element")
        self.origin_combo.addItem("The centre of gravity", "cog")
        self.origin_combo.setCurrentIndex(max(0, self.origin_combo.findData(origin)))
        self.origin_combo.setToolTip(
            "Where the origin of the spacecraft's body frame goes. The body element's frame keeps every position as "
            "in IDM-CIC; the centre of gravity (of the model as imported, propellant included) moves the origin "
            "there, and every position of the spacecraft with it: parts, point masses, sensors, actuators, thrusters, "
            "facets, the tank, the solar array hinges, the launcher plane. Either way the run is the same: the "
            "simulation takes the centre of gravity from the origin. The choice is kept for the next import.")
        form.addRow("Origin of the body frame", self.origin_combo)
        layout.addLayout(form)
        layout.addWidget(QLabel("What the import will do"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.preview, 1)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 2)
        devices_page = QWidget()
        devices_layout = QVBoxLayout(devices_page)
        self.tabs.addTab(devices_page, "Devices found")
        self.devices_note = set_role(QLabel(""), tone="secondary")
        self.devices_note.setWordWrap(True)
        devices_layout.addWidget(self.devices_note)
        self.devices_table = QTableWidget(0, len(self.DEVICE_COLUMNS))
        self.devices_table.setHorizontalHeaderLabels(self.DEVICE_COLUMNS)
        self.devices_table.verticalHeader().setVisible(False)
        self.devices_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.devices_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.devices_table.setTabKeyNavigation(False)
        self.devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.devices_table.horizontalHeader().setStretchLastSection(True)
        devices_layout.addWidget(self.devices_table, 1)
        self._findings: list = []
        properties_page = QWidget()
        properties_layout = QVBoxLayout(properties_page)
        self.tabs.addTab(properties_page, "Properties")
        self.properties_note = set_role(QLabel(""), tone="secondary")
        self.properties_note.setWordWrap(True)
        properties_layout.addWidget(self.properties_note)
        self.properties_table = QTableWidget(0, len(self.PROPERTY_COLUMNS))
        self.properties_table.setHorizontalHeaderLabels(self.PROPERTY_COLUMNS)
        self.properties_table.verticalHeader().setVisible(False)
        self.properties_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.properties_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.properties_table.setTabKeyNavigation(False)
        self.properties_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.properties_table.horizontalHeader().setStretchLastSection(True)
        properties_layout.addWidget(self.properties_table, 1)
        self._property_rows: list = []  # (name, value type, kinds)
        power_page = QWidget()
        power_layout = QVBoxLayout(power_page)
        self.tabs.addTab(power_page, "Power")
        self.power_note = set_role(QLabel(""), tone="secondary")
        self.power_note.setWordWrap(True)
        power_layout.addWidget(self.power_note)
        power_form = QFormLayout()
        self.bus_check = QCheckBox("Set the bus load from")
        self.bus_check.setToolTip("The power budget's bus load: the power of the imported equipment in this system "
                                  "mode of the model")
        self.bus_combo = ComboBox()
        power_form.addRow(self.bus_check, self.bus_combo)
        self.panels_check = QCheckBox("Set the panel area and normal")
        self.panels_check.setToolTip("The power budget's panel area and normal: the solar array panels found by "
                                     "name along one normal line (the largest group), the largest flat face of each")
        self.normal_combo = ComboBox()
        self.normal_combo.setToolTip("Which side of the panels carries the cells, as a body-frame normal: the file "
                                     "does not say")
        power_form.addRow(self.panels_check, self.normal_combo)
        self.battery_check = QCheckBox("Set the battery capacity from the batteries' capacity property")
        self.battery_check.setToolTip("The power budget's battery capacity: the batteries' capacity property, mapped "
                                      "on the Properties tab, added up")
        self.battery_label = QLabel("")
        power_form.addRow(self.battery_check, self.battery_label)
        power_layout.addLayout(power_form)
        power_layout.addStretch(1)
        self.status = set_role(QLabel(""), tone="caution")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.currentIndexChanged.connect(self._replan)
        self.facets_check.toggled.connect(self._replan)
        self._update_buttons()
        if path is not None:
            self.open_file(path)

    # -- choosing ------------------------------------------------------------------------------------------------

    def _on_browse(self) -> None:
        start = str(self._path.parent if self._path else self._start_dir or Path.home())
        name, _ = QFileDialog.getOpenFileName(self, "Import an IDM-CIC model", start, "IDM-CIC model (*.idm *.IDM)")
        if name:
            self.open_file(name)

    def open_file(self, path) -> None:
        """Read ``path`` and plan its import with the default choices."""
        self._path = Path(path)
        self.path_edit.setText(str(self._path))
        self._model = None
        self._plan = None
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.blockSignals(False)
        self._start({})

    def _options(self) -> dict:
        return {"configuration": self.configuration_combo.currentData() or None,
                "stowed_configuration": self.stowed_combo.currentData() or None,
                "body_element": self.body_combo.currentData() or None,
                "apply_facets": self.facets_check.isChecked()}

    def _replan(self) -> None:
        if self._model is None:
            return
        if self._worker is not None:
            self._again = True
            return
        self._start(self._options())

    def _start(self, options: dict) -> None:
        self._plan = None
        self.preview.setPlainText("Reading the model..." if self._model is None else "Planning the import...")
        self.status.setText("")
        self._worker = _Worker(self._path, self._model, options, self)
        self._worker.finished_ok.connect(self._on_planned)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_worker_done)
        self._update_buttons()
        self._worker.start()

    def _fill_combos(self, model) -> None:
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.blockSignals(True)
        self.configuration_combo.addItem("Default values", _DEFAULT)
        self.stowed_combo.addItem("None", _DEFAULT)
        for c in model.configurations:
            label = f"{c.id} ({c.name})" if c.name != c.id else c.id
            self.configuration_combo.addItem(label, c.id)
            self.stowed_combo.addItem(label, c.id)
        self.body_combo.addItem("Chosen (the heaviest element the others hang on)", _DEFAULT)
        for e in model.elements:
            self.body_combo.addItem(e.name, e.full_id)
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.blockSignals(False)

    def _on_planned(self, model, plan) -> None:
        if self._model is None:
            self._model = model
            self._fill_combos(model)
        self._plan = plan
        self.preview.setPlainText("\n".join(plan.summary.lines()))
        self._fill_devices(plan.devices)
        self._fill_power(plan.power)
        self._fill_properties(plan.devices)

    def _fill_properties(self, findings: list) -> None:
        """One row per property name the devices' equipment carry, mapped
        as before (an earlier import's mapping, or this dialog's)."""
        from .. import idm_devices, idm_properties

        previous = {idm_properties.normalized(m.property): m for m in (self.property_mappings(require_unit=False)
                                                                        or self._initial_mappings)}
        rows = idm_properties.properties_by_kind((f.kind, f.properties) for f in findings)
        table = self.properties_table
        table.setRowCount(len(rows))
        self._property_rows = []
        for row, (key, (name, value_type, kinds, texts)) in enumerate(rows.items()):
            self._property_rows.append((name, value_type, kinds))
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(value_type))
            table.setItem(row, 2, QTableWidgetItem(", ".join(sorted(idm_devices.KIND_LABELS[k] for k in kinds))))
            table.setItem(row, 3, QTableWidgetItem(", ".join(texts[:4]) + (" ..." if len(texts) > 4 else "")
                                                   if texts else "no value"))
            use = ComboBox()
            use.addItem("Not used", "")
            for target in idm_properties.TARGETS.values():
                if target.kind in kinds:
                    use.addItem(target.label, target.key)
            use.setAccessibleName(f"Use {name} as")
            unit = ComboBox()
            unit.setAccessibleName(f"Unit of {name}")
            table.setCellWidget(row, 4, use)
            table.setCellWidget(row, 5, unit)
            table.setItem(row, 6, QTableWidgetItem(""))
            mapping = previous.get(key)
            if mapping is not None and use.findData(mapping.target) >= 0:
                use.setCurrentIndex(use.findData(mapping.target))
            self._fill_units(row, mapping.unit if mapping is not None else None)
            use.currentIndexChanged.connect(lambda _i, row=row: self._on_use_changed(row))
            unit.currentIndexChanged.connect(lambda _i: self._apply_mappings())
            use.setEnabled(use.count() > 1)
        self.properties_note.setText(
            "No property on the devices found." if not rows else
            "Properties your team keeps on the equipment. Map one to a value and say the unit its values are in: "
            "a device then takes it (over a catalog product's), and a wheel or magnetorquer that the properties give "
            "every value can be added without a product. Nothing is read from a property that is not mapped.")
        self._apply_mappings()

    def _fill_units(self, row: int, chosen: str | None) -> None:
        """The units the row's value takes; the one offered (or ``chosen``) selected."""
        from .. import idm_properties

        use, unit = self.properties_table.cellWidget(row, 4), self.properties_table.cellWidget(row, 5)
        unit.blockSignals(True)
        unit.clear()
        target = idm_properties.TARGETS.get(use.currentData() or "")
        if target is not None:
            unit.addItem("Choose the unit", "")
            for name, _factor in target.units:
                unit.addItem(name, name)
            offered = chosen if chosen is not None else idm_properties.suggested_unit(self._property_rows[row][1],
                                                                                      target)
            unit.setCurrentIndex(max(0, unit.findData(offered)))
        unit.setEnabled(target is not None)
        unit.blockSignals(False)

    def _on_use_changed(self, row: int) -> None:
        self._fill_units(row, None)
        self._apply_mappings()

    def property_mappings(self, require_unit: bool = True) -> list:
        """The mapping shown (``idm_properties.Mapping``): each row with a
        value chosen and (``require_unit``) its unit."""
        from .. import idm_properties

        mappings = []
        for row, (name, _value_type, _kinds) in enumerate(self._property_rows):
            target = self.properties_table.cellWidget(row, 4).currentData() or ""
            unit = self.properties_table.cellWidget(row, 5).currentData() or ""
            if target and (unit or not require_unit):
                mappings.append(idm_properties.Mapping(name, target, unit))
        return mappings

    def _apply_mappings(self) -> None:
        """The mapping into the plan; the notes, device rows and battery
        choice follow it."""
        from .. import idm_import, idm_properties

        if self._plan is None:
            return
        problem = ""
        try:
            idm_import.set_mappings(self._plan, self.property_mappings())
        except ValueError as exc:
            problem = str(exc)
            idm_import.set_mappings(self._plan, [])
        for row, (name, _value_type, _kinds) in enumerate(self._property_rows):
            target = self.properties_table.cellWidget(row, 4).currentData() or ""
            unit = self.properties_table.cellWidget(row, 5).currentData() or ""
            note = "" if not target else "choose the unit its values are in" if not unit else \
                f"read as {idm_properties.TARGETS[target].param} [{idm_properties.TARGETS[target].unit}]"
            self.properties_table.item(row, 6).setText(note)
        self._mapping_problem = problem
        for row in range(len(self._findings)):
            self._update_device_row(row)
        self._update_battery()
        self._update_buttons()

    def _fill_power(self, power_plan) -> None:
        """The system modes and the panel normals the model gives, nothing
        ticked."""
        modes = power_plan.modes if power_plan is not None else []
        groups = power_plan.groups if power_plan is not None else []
        self.bus_combo.clear()
        for entry in modes:
            self.bus_combo.addItem(f"system mode {entry.mode.name}: {entry.total_w:.6g} W", entry.mode.name)
        if power_plan is not None and power_plan.average_w is not None:
            self.bus_combo.addItem(f"duty-cycle average: {power_plan.average_w:.6g} W", "average")
        self.normal_combo.clear()
        if groups:
            normal, area, members = groups[0]
            for sign in (1, -1):
                shown = [0.0 if v == 0.0 else sign * v for v in normal]
                self.normal_combo.addItem(f"{'+' if sign > 0 else '-'} [{', '.join(f'{v:.4g}' for v in shown)}]: "
                                          f"{area:.6g} m^2, {len(members)} panel(s)", sign)
        for check, combo, any_found in ((self.bus_check, self.bus_combo, bool(modes)),
                                        (self.panels_check, self.normal_combo, bool(groups))):
            check.setChecked(False)
            check.setEnabled(any_found and self._devices_allowed)
            combo.setEnabled(any_found and self._devices_allowed)
        if not self._devices_allowed and (modes or groups):
            self.power_note.setText("This scenario runs orbit only, which simulates no power budget: nothing is set.")
        elif not (modes or groups):
            self.power_note.setText("The model gives no system modes and no flat solar array panel.")
        else:
            self.power_note.setText(
                "A system mode's power is that of the imported equipment in it (counted as 0 W where its modes do "
                "not set one). Without a power budget, setting the panels makes one, with the editor's panel "
                "efficiency and battery until you set them (the pre-run checks say so).")

    def power_choice(self):
        """The ``idm_import.PowerChoice`` as shown."""
        from .. import idm_import

        bus = self.bus_combo.currentData() if self.bus_check.isChecked() and self.bus_check.isEnabled() else ""
        panels = self.panels_check.isChecked() and self.panels_check.isEnabled()
        battery = self.battery_check.isChecked() and self.battery_check.isEnabled()
        return idm_import.PowerChoice(bus or "", panels, self.normal_combo.currentData() or 1, battery)

    def _update_battery(self) -> None:
        """The battery choice: offered when the mapping gives a capacity."""
        from .. import idm_import

        capacity, read = idm_import.battery_capacity(self._plan) if self._plan is not None else (None, [])
        self.battery_check.setEnabled(capacity is not None and self._devices_allowed)
        if capacity is None:
            self.battery_check.setChecked(False)
        self.battery_label.setText(f"{capacity:.6g} W*h from {len(read)} battery unit(s)" if capacity is not None
                                   else "map the batteries' capacity property on the Properties tab")

    def _fill_devices(self, findings: list) -> None:
        """One row per device found, with the default choices
        (``idm_devices.default_choices``)."""
        from .. import idm_devices

        self._findings = list(findings)
        self._blocked = {}
        table = self.devices_table
        table.setRowCount(len(findings))
        for row, (finding, choice) in enumerate(zip(findings, idm_devices.default_choices(findings))):
            add = QCheckBox()
            add.setChecked(choice.add and self._devices_allowed)
            add.setEnabled(finding.addable and self._devices_allowed)
            add.setAccessibleName(f"Add {finding.equipment}")
            table.setCellWidget(row, 0, add)
            table.setItem(row, 1, QTableWidgetItem(finding.equipment))
            table.setItem(row, 2, QTableWidgetItem(finding.subsystem))
            table.setItem(row, 3, QTableWidgetItem(idm_devices.KIND_LABELS[finding.kind]))
            axis = ComboBox()
            if finding.model_axis is not None:
                axis.addItem("from the model", idm_devices.MODEL_AXIS)
            for name in idm_devices.AXES:
                axis.addItem(name, name)
            axis.setCurrentIndex(max(0, axis.findData(choice.axis)))
            axis.setEnabled(finding.addable)
            axis.setToolTip(
                ("From the model: " + idm_devices.axis_text(finding, idm_devices.MODEL_AXIS) + ", "
                 f"[{', '.join(f'{v:.3g}' for v in finding.model_axis)}] in the body frame. "
                 if finding.model_axis is not None else
                 "The model's shapes show no axis (no "
                 + ("plume" if finding.kind == "thruster" else "field-of-view") + " cone"
                 + (" or cylinder" if finding.kind in idm_devices.CYLINDER_KINDS else "") + "): +z by default. ")
                + "Or an axis of the equipment's frame in IDM-CIC (+z: the axis of its revolution shapes).")
            table.setCellWidget(row, 4, axis)
            product = ComboBox()
            product.addItem("None (no thrust)" if finding.kind in idm_devices.EQUIPMENT_KINDS else
                            "None (Basilisk's defaults)" if finding.kind not in idm_devices.REQUIRED_VALUES else
                            "None", "")
            for name in idm_devices.product_names(finding.kind) if finding.addable else []:
                product.addItem(name, name)
            product.setCurrentIndex(max(0, product.findData(choice.product)))
            product.setEnabled(finding.addable)
            table.setCellWidget(row, 5, product)
            note = QTableWidgetItem("")
            table.setItem(row, 6, note)
            product.currentIndexChanged.connect(lambda _i, row=row: self._update_device_row(row))
            add.toggled.connect(lambda _on, row=row: self._update_device_row(row))
            self._update_device_row(row)
        self.devices_note.setText(
            "None found by name." if not findings else
            ("This scenario runs orbit only, which simulates no sensors or actuators: they are listed, not added."
             if not self._devices_allowed else
             "The model says what each device is and where it sits, not how it performs: a device takes its values "
             "from the catalog product chosen, or runs with Basilisk's defaults until you set them (the pre-run "
             "checks say so). A thruster goes to the 3D model's equipment, for the design checks."))

    def _update_device_row(self, row: int) -> None:
        """The note of a row: why it is not added, or where its values come from."""
        from .. import idm_devices

        finding = self._findings[row]
        add = self.devices_table.cellWidget(row, 0)
        product = self.devices_table.cellWidget(row, 5).currentData() or ""
        values, problems = idm_devices.finding_values(finding, self._plan.mappings if self._plan else [])
        mapped = [v.target.param for v in values]
        why = idm_devices.why_not(finding.kind, product, mapped)
        if finding.addable and not why and self._blocked.get(row) and self._devices_allowed:
            add.setChecked(True)  # what blocked it is given now: added, as the default choices would
        self._blocked[row] = bool(why)
        if not finding.addable:
            text = why
        elif why:
            text = why
            add.setChecked(False)
        elif not add.isChecked():
            text = "not added" + (": " + idm_devices.why_not(finding.kind, product, mapped, axis_known=False)
                                  if finding.kind in idm_devices.EQUIPMENT_KINDS and finding.model_axis is None else "")
        elif finding.kind in idm_devices.EQUIPMENT_KINDS:
            thrust = "MaxThrust" in mapped
            text = ("to the 3D model's equipment; thrust: " + (
                "from its properties" if thrust else product if product else
                "none (the authority matrix takes it per newton)"))
        elif product:
            text = f"values: {product}" + (f", with {', '.join(mapped)} from its properties" if mapped else "")
        elif mapped:
            text = f"values: {', '.join(mapped)} from its properties; Basilisk's defaults for the rest"
        else:
            text = "values: Basilisk's defaults until set"
        if problems:
            text += "; not read: " + "; ".join(problems)
        add.setEnabled(self._devices_allowed and finding.addable and not why)
        self.devices_table.item(row, 6).setText(text)
        self.devices_table.item(row, 6).setToolTip(text)  # the column cuts long notes

    def origin(self) -> str:
        """Where the body frame's origin goes: one of ``idm_import.ORIGINS``."""
        return self.origin_combo.currentData()

    def device_choices(self) -> list:
        """One ``idm_devices.DeviceChoice`` per device found, as shown."""
        from .. import idm_devices

        choices = []
        for row, finding in enumerate(self._findings):
            add = self.devices_table.cellWidget(row, 0).isChecked()
            choices.append(idm_devices.DeviceChoice(add and self._devices_allowed, finding.kind,
                                                    self.devices_table.cellWidget(row, 4).currentData(),
                                                    self.devices_table.cellWidget(row, 5).currentData() or ""))
        return choices

    def _on_failed(self, message: str) -> None:
        self._plan = None
        self.preview.setPlainText("")
        self.status.setText(f"Cannot import: {message}")

    def _on_worker_done(self) -> None:
        if self._worker is not None:
            self._worker.wait()  # "finished" comes just before the thread ends: let it end before it is dropped
        self._worker = None
        if self._again:
            self._again = False
            self._start(self._options())
            return
        self._update_buttons()

    def _update_buttons(self) -> None:
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(self._plan is not None and self._worker is None and not self._mapping_problem)
        if self._mapping_problem:
            self.status.setText(f"Properties: {self._mapping_problem}.")
        elif self.status.text().startswith("Properties: "):
            self.status.setText("")

    def _on_accept(self) -> None:
        if self._plan is not None and self._worker is None:
            self.accept()

    # -- result --------------------------------------------------------------------------------------------------

    def plan(self):
        """The import planned for the choices shown (``idm_import.Plan``), or None."""
        return self._plan

    def busy(self) -> bool:
        """Whether the file is being read or the import planned."""
        return self._worker is not None

    def done(self, result: int) -> None:  # noqa: D102 -- a closed dialog must not leave its thread running
        self._finish_worker()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        self._finish_worker()
        super().closeEvent(event)

    def _finish_worker(self) -> None:
        worker = self._worker
        if worker is not None:
            self._again = False
            worker.wait()
