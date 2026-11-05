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
pre-run checks say so). Thrusters, solar arrays and batteries are listed,
not added. :meth:`IdmImportDialog.device_choices` is what was chosen.

**Power** offers what the model says of the power budget
(``idm_import.PowerPlan``): the bus load as the power of the imported
equipment in one of the model's system modes (or their duty-cycle
average, when the duty cycles add up to one), and the panel area and
normal from the solar array panels found, with the side carrying the
cells chosen (the file does not say). Nothing is set unless ticked.
:meth:`IdmImportDialog.power_choice` is what was chosen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

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

    def __init__(self, path=None, parent: QWidget | None = None, start_dir=None, devices_allowed: bool = True):
        super().__init__(parent)
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
        layout.addLayout(form)
        layout.addWidget(QLabel("What the import will do"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.preview, 1)
        layout.addWidget(QLabel("Devices found"))
        self.devices_note = set_role(QLabel(""), tone="secondary")
        self.devices_note.setWordWrap(True)
        layout.addWidget(self.devices_note)
        self.devices_table = QTableWidget(0, len(self.DEVICE_COLUMNS))
        self.devices_table.setHorizontalHeaderLabels(self.DEVICE_COLUMNS)
        self.devices_table.verticalHeader().setVisible(False)
        self.devices_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.devices_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.devices_table.setTabKeyNavigation(False)
        self.devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.devices_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.devices_table, 1)
        self._findings: list = []
        layout.addWidget(QLabel("Power"))
        self.power_note = set_role(QLabel(""), tone="secondary")
        self.power_note.setWordWrap(True)
        layout.addWidget(self.power_note)
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
        layout.addLayout(power_form)
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
        return idm_import.PowerChoice(bus or "", panels, self.normal_combo.currentData() or 1)

    def _fill_devices(self, findings: list) -> None:
        """One row per device found, with the default choices
        (``idm_devices.default_choices``)."""
        from .. import idm_devices

        self._findings = list(findings)
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
            axis.addItems(idm_devices.AXES)
            axis.setCurrentText(choice.axis)
            axis.setEnabled(finding.addable)
            axis.setToolTip("The axis of the equipment's frame in IDM-CIC that is the device's boresight, spin axis "
                            "or dipole axis (+z: the axis of IDM-CIC's revolution shapes)")
            table.setCellWidget(row, 4, axis)
            product = ComboBox()
            product.addItem("None (Basilisk's defaults)" if finding.kind not in idm_devices.REQUIRED_VALUES else
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
             "checks say so)."))

    def _update_device_row(self, row: int) -> None:
        """The note of a row: why it is not added, or where its values come from."""
        from .. import idm_devices

        finding = self._findings[row]
        add = self.devices_table.cellWidget(row, 0)
        product = self.devices_table.cellWidget(row, 5).currentData() or ""
        why = idm_devices.why_not(finding.kind, product)
        if not finding.addable:
            text = why
        elif why:
            text = why
            add.setChecked(False)
        elif not add.isChecked():
            text = "not added"
        else:
            text = f"values: {product}" if product else "values: Basilisk's defaults until set"
        add.setEnabled(self._devices_allowed and finding.addable and not why)
        self.devices_table.item(row, 6).setText(text)

    def device_choices(self) -> list:
        """One ``idm_devices.DeviceChoice`` per device found, as shown."""
        from .. import idm_devices

        choices = []
        for row, finding in enumerate(self._findings):
            add = self.devices_table.cellWidget(row, 0).isChecked()
            choices.append(idm_devices.DeviceChoice(add and self._devices_allowed, finding.kind,
                                                    self.devices_table.cellWidget(row, 4).currentText(),
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
        ok.setEnabled(self._plan is not None and self._worker is None)

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
