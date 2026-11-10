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
"""End of Life › Re-entry casualty (preliminary): the DAS-like estimate of
``analyses.reentry`` for one spacecraft, with the population density the
user gives, computed in a worker thread. Labelled preliminary beside every
number; Save... writes its record."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import export_log
from .data_table import DataTable, Row
from .theme import set_role
from .widgets import ComboBox, NumberField

PRELIMINARY = ("Preliminary estimate (DAS-like, simplified): not a substitute for DAS, DRAMA or SESAM. "
               "See docs/models/reentry.md.")


class _Worker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, scenario, sc, base_dir, density, parent=None):
        super().__init__(parent)
        self._args = (scenario, sc, base_dir, density)

    def run(self) -> None:
        from ..analyses.reentry import reentry_estimate

        scenario, sc, base_dir, density = self._args
        try:
            self.finished_ok.emit(reentry_estimate(sc, base_dir, density, scenario))
        except Exception as exc:  # noqa: BLE001 -- shown on the page
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ReentrySection(QGroupBox):
    """The re-entry casualty section of the End of Life page."""

    def __init__(self, parent=None):
        super().__init__("Re-entry casualty (preliminary)", parent)
        self._scenario = None
        self._base_dir: Path | None = None
        self._worker: _Worker | None = None
        self.estimate = None
        layout = QVBoxLayout(self)
        label = set_role(QLabel(PRELIMINARY), tone="caution")
        label.setWordWrap(True)
        layout.addWidget(label)
        row = QHBoxLayout()
        row.addWidget(QLabel("Spacecraft"))
        self.spacecraft_combo = ComboBox()
        row.addWidget(self.spacecraft_combo, 1)
        self.density_check = QCheckBox("Population density")
        self.density_check.setToolTip("People per km^2 under the re-entry: no default (model-analyses decision D-16)")
        row.addWidget(self.density_check)
        self.density_field = NumberField("/km²", minimum=0.0, maximum=1.0e5, decimals=2)
        self.density_field.setEnabled(False)
        self.density_check.toggled.connect(self.density_field.setEnabled)
        row.addWidget(self.density_field)
        self.compute_button = set_role(QPushButton("Estimate"), variant="primary")
        self.compute_button.clicked.connect(self.compute)
        row.addWidget(self.compute_button)
        self.save_button = QPushButton("Save...")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_clicked)
        row.addWidget(self.save_button)
        layout.addLayout(row)
        self.table = DataTable("Estimate breaks the 3D model's parts up at the break-up altitude and follows each "
                               "to the ground.")
        layout.addWidget(self.table)
        self.result_label = set_role(QLabel(""), role="strong")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        self.notes_label = set_role(QLabel(""), tone="secondary")
        self.notes_label.setWordWrap(True)
        layout.addWidget(self.notes_label)
        self._update_enabled()

    def set_scenario(self, scenario, base_dir: Path | None = None) -> None:
        self._scenario, self._base_dir = scenario, base_dir
        names = [sc.name for sc in scenario.spacecraft if sc.model is not None] if scenario is not None else []
        if names != [self.spacecraft_combo.itemText(i) for i in range(self.spacecraft_combo.count())]:
            current = self.spacecraft_combo.currentText()
            self.spacecraft_combo.clear()
            self.spacecraft_combo.addItems(names)
            if current in names:
                self.spacecraft_combo.setCurrentText(current)
        self._update_enabled()

    def _update_enabled(self) -> None:
        self.compute_button.setEnabled(self.spacecraft_combo.count() > 0 and self._worker is None)
        self.compute_button.setToolTip("" if self.spacecraft_combo.count() else
                                       "Needs a spacecraft with a 3D model (Scenario › 3D Model...)")

    def compute(self) -> None:
        name = self.spacecraft_combo.currentText()
        sc = next((s for s in self._scenario.spacecraft if s.name == name), None) if self._scenario else None
        if sc is None or self._worker is not None:
            return
        density = self.density_field.value() if self.density_check.isChecked() else None
        self.result_label.setText(f"Estimating {name}...")
        self._worker = _Worker(self._scenario, sc, self._base_dir, density, self)
        self._worker.finished_ok.connect(self._show)
        self._worker.failed.connect(lambda message: self.result_label.setText(f"Could not estimate: {message}"))
        self._worker.finished.connect(self._worker_done)
        self._update_enabled()
        self._worker.start()

    def wait_for_worker(self, timeout_ms: int = 60000) -> None:
        if self._worker is not None:
            self._worker.wait(timeout_ms)

    def _worker_done(self) -> None:
        self._worker = None
        self._update_enabled()

    def _show(self, estimate) -> None:
        self.estimate = estimate
        rows = []
        for r in estimate.rows():
            fate = (f"demises at {r['demise_altitude_km']:.1f} km" if r["demise_altitude_km"] is not None
                    else f"lands: {r['surviving_mass_kg']:.2f} kg, {r['impact_energy_j']:.3g} J")
            rows.append(Row((r["part"], r["material"] or "(none)", f"{r['mass_kg']:g}", fate,
                             f"{r['casualty_area_m2']:.3f}", f"{r['demise_prone_casualty_area_m2']:.3f}"),
                            tooltips={3: r["note"]} if r["note"] else {}))
        self.table.set_table(("Part", "Material", "Mass [kg]", "Fate (eps = 1)", "Casualty area [m²]",
                              "Demise-prone [m²]"), rows, numeric=(2, 4, 5), stretch=3)
        self.table.fit_rows()
        text = (f"Casualty area {estimate.casualty_area_m2:.3f} m² (survival-prone bound; demise-prone "
                f"{estimate.casualty_area_demise_prone_m2:.3f} m²).")
        if estimate.risk is not None:
            verdict = "within" if estimate.compliant else "over"
            text += (f" Casualty risk {estimate.risk:.3g} at {estimate.population_density_per_km2:g} people/km², "
                     f"{verdict} the limit {estimate.risk_limit:g} (NASA-STD-8719.14B).")
        else:
            text += " Give a population density for the risk."
        self.result_label.setText(text)
        set_role(self.result_label, role="strong", tone="critical" if estimate.compliant is False else None)
        self.notes_label.setText("\n".join(f"- {n}" for n in estimate.notes))
        self.save_button.setEnabled(True)

    def _save_clicked(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(self, "Save the re-entry estimate", "reentry.json", "JSON (*.json)")
        if path:
            self.save(Path(path))

    def save(self, path: Path) -> Path:
        from ..analyses import records

        written = records.write_record(path, records.reentry_record(self._scenario, self.estimate))
        export_log.record("reentry_json", written)
        return written
