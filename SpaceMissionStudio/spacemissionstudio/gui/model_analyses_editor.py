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
"""The spacecraft editor's Model analyses group (3D model tab): which of a
run's model analyses the spacecraft asks for (``ModelAnalysesConfig``),
the residual dipole, the ray samples and the brightness's observer sites.
Checked: the spacecraft keeps a ``model_analyses``; unchecked: none."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..schema.scenario import ModelAnalysesConfig, ObserverSiteConfig
from .widgets import NumberField, SpinBox, style_number

_SWITCHES = (("sensor_blinding", "Sensor blinding by the Sun, Earth and Moon"),
             ("antenna_obstruction", "Antenna obstruction during passes"),
             ("disturbance_torques", "Disturbance torques (recorded in the run)"),
             ("array_shading", "Solar-cell shading and its power"),
             ("surface_exposure", "Atomic oxygen and sun hours per face"),
             ("brightness", "Brightness from the ground"))
_OBSERVER_COLUMNS = ("Name", "Latitude [deg]", "Longitude [deg]", "Altitude [m]", "Min. elevation [deg]")


class ModelAnalysesGroup(QGroupBox):
    """The model analyses of one spacecraft."""

    def __init__(self, config: ModelAnalysesConfig | None, parent=None):
        super().__init__("Model analyses", parent)
        self.setCheckable(True)
        self.setChecked(config is not None)
        self.setToolTip("Analyses of a run made with the 3D model and the mounted equipment: their series, "
                        "events and tables are in Results › Model Analyses (docs/models/model-analyses.md).")
        c = config or ModelAnalysesConfig()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.switches: dict = {}
        for name, label in _SWITCHES:
            box = QCheckBox(label)
            box.setChecked(bool(getattr(c, name)))
            form.addRow(box)
            self.switches[name] = box
        self.dipole = [NumberField("A·m²", minimum=-1.0e4, maximum=1.0e4, decimals=3, value=float(v))
                       for v in c.residual_dipole_a_m2]
        dipole_row = QHBoxLayout()
        for field in self.dipole:
            dipole_row.addWidget(field)
        dipole_widget = QWidget()
        dipole_widget.setLayout(dipole_row)
        form.addRow("Residual dipole x, y, z", dipole_widget)
        self.samples = SpinBox()
        self.samples.setRange(16, 65536)
        self.samples.setValue(int(c.samples))
        style_number(self.samples, "rays")
        self.samples.setToolTip("Rays per face or cone: the error falls as 1 / sqrt(samples)")
        form.addRow("Ray samples", self.samples)
        layout.addLayout(form)
        self.observers = QTableWidget(0, len(_OBSERVER_COLUMNS))
        self.observers.setHorizontalHeaderLabels(_OBSERVER_COLUMNS)
        self.observers.setToolTip("Observer sites for the brightness, beside the ground stations")
        for site in c.observers:
            self._add_row(site)
        layout.addWidget(self.observers)
        buttons = QHBoxLayout()
        add = QPushButton("Add observer site")
        add.clicked.connect(lambda: self._add_row(ObserverSiteConfig(f"site-{self.observers.rowCount() + 1}", 0.0,
                                                                     0.0)))
        remove = QPushButton("Remove")
        remove.clicked.connect(lambda: self.observers.removeRow(self.observers.currentRow())
                               if self.observers.currentRow() >= 0 else None)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def _add_row(self, site: ObserverSiteConfig) -> None:
        row = self.observers.rowCount()
        self.observers.insertRow(row)
        for column, value in enumerate((site.name, site.latitude_deg, site.longitude_deg, site.altitude_m,
                                        site.min_elevation_deg)):
            self.observers.setItem(row, column, QTableWidgetItem(value if isinstance(value, str) else f"{value:g}"))

    def field_widget(self, name: str) -> QWidget | None:
        """The widget for the field ``name`` ("samples"), or None."""
        if name in self.switches:
            return self.switches[name]
        if name == "samples":
            return self.samples
        if name == "residual_dipole_a_m2":
            return self.dipole[0]
        if name == "observers":
            return self.observers
        return None

    def to_config(self) -> ModelAnalysesConfig | None:
        """The analyses asked for, or None when the group is off. A site
        whose numbers do not read is refused with its row."""
        if not self.isChecked():
            return None
        observers = []
        for row in range(self.observers.rowCount()):
            cells = [self.observers.item(row, c).text().strip() if self.observers.item(row, c) else ""
                     for c in range(len(_OBSERVER_COLUMNS))]
            try:
                numbers = [float(text) for text in cells[1:]]
            except ValueError as exc:
                raise ValueError(f"model_analyses.observers: row {row + 1}: a number does not read ({exc})") from exc
            observers.append(ObserverSiteConfig(cells[0], *numbers))
        return ModelAnalysesConfig(**{name: box.isChecked() for name, box in self.switches.items()},
                                   residual_dipole_a_m2=[field.value() for field in self.dipole],
                                   observers=observers, samples=self.samples.value())
