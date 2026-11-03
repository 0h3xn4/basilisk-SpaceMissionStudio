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
"""Results › Model Analyses: a run's model analyses
(``analyses.run_analyses``) for each spacecraft that asked for them: the
disturbance-torque budget with the momentum and the sizing, the blinding,
antenna obstruction, array shading, exposure and brightness tables, and
the findings. The series themselves are in Results › Plots and the
events on the Timeline. Save... writes the record and the tables with
their provenance."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import export_log
from .data_table import DataTable, Row
from .theme import set_role
from .widgets import ComboBox

_TABLES = (("disturbance_torques", "Disturbance torques"), ("blinding", "Sensor blinding"),
           ("antenna_obstruction", "Antenna obstruction during passes"), ("array_shading", "Array shading"),
           ("surface_exposure", "Surface exposure (atomic oxygen, sun hours)"),
           ("brightness", "Brightness from the ground"))


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


class ModelAnalysesWidget(QWidget):
    """The Model Analyses tab of Results."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scenario = None
        self._result = None
        self.report = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Spacecraft"))
        self.spacecraft_combo = ComboBox()
        self.spacecraft_combo.currentTextChanged.connect(lambda _name: self._show())
        top.addWidget(self.spacecraft_combo, 1)
        self.save_button = QPushButton("Save...")
        self.save_button.setToolTip("Write the record (model_analyses.json) and each table (CSV), each with its "
                                    "provenance, to a folder")
        self.save_button.clicked.connect(self._save_clicked)
        top.addWidget(self.save_button)
        layout.addLayout(top)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.findings_label = QLabel("")
        self.findings_label.setWordWrap(True)
        layout.addWidget(self.findings_label)
        self.tables: dict = {}
        self.groups: dict = {}
        for key, title in _TABLES:
            table = DataTable()
            group = QGroupBox(title)
            QVBoxLayout(group).addWidget(table)
            layout.addWidget(group)
            self.tables[key], self.groups[key] = table, group
        self.notes_label = set_role(QLabel(""), tone="secondary")
        self.notes_label.setWordWrap(True)
        layout.addWidget(self.notes_label)
        layout.addStretch(1)

    @staticmethod
    def has_analyses(scenario) -> bool:
        return scenario is not None and any(sc.model_analyses is not None for sc in scenario.spacecraft)

    def set_run(self, scenario, result) -> None:
        """The run's scenario and results (None: nothing to show)."""
        self._scenario, self._result = scenario, result
        names = [sc.name for sc in scenario.spacecraft if sc.model_analyses is not None] if scenario else []
        self.spacecraft_combo.blockSignals(True)
        self.spacecraft_combo.clear()
        self.spacecraft_combo.addItems(names)
        self.spacecraft_combo.blockSignals(False)
        self._show()

    def _show(self) -> None:
        from ..analyses import run_analyses

        name = self.spacecraft_combo.currentText()
        sc = next((s for s in self._scenario.spacecraft if s.name == name), None) if self._scenario else None
        self.report = run_analyses.report(self._result, self._scenario, sc) if sc and self._result else None
        self.save_button.setEnabled(self.report is not None)
        if self.report is None:
            self.summary_label.setText("Run a scenario whose spacecraft set model analyses to see them here.")
            for group in self.groups.values():
                group.setVisible(False)
            self.findings_label.setText("")
            self.notes_label.setText("")
            return
        tables = self.report.tables()
        for key, table in self.tables.items():
            rows = tables.get(key, [])
            self.groups[key].setVisible(bool(rows))
            if rows:
                columns = list(rows[0])
                table.set_table(columns, [Row(tuple(_text(r.get(c)) for c in columns)) for r in rows],
                                numeric=range(1, len(columns)), stretch=0)
                table.fit_rows()
        budget = self.report.disturbances
        if budget is not None:
            per_orbit = budget.required_momentum_n_m_s()
            span = "per orbit" if budget.momentum_per_orbit_n_m_s is not None else "over the run"
            text = (f"Momentum {budget.momentum_max_n_m_s:.4g} N·m·s at most over the run; per body axis "
                    f"{', '.join(f'{v:.4g}' for v in per_orbit)} N·m·s {span}.")
            if budget.wheel_capacity_n_m_s is not None:
                text += " Wheels hold " + ", ".join(f"{v:.4g}" for v in budget.wheel_capacity_n_m_s) + " N·m·s."
            self.summary_label.setText(text)
        else:
            self.summary_label.setText("No disturbance torques recorded (model_analyses.disturbance_torques).")
        findings = self.report.findings()
        self.findings_label.setText("\n".join(f"- {f}" for f in findings))
        set_role(self.findings_label, tone="caution" if findings else None)
        notes = list(self.report.notes) + (list(budget.notes) if budget is not None else [])
        self.notes_label.setText("\n".join(f"- {n}" for n in notes))

    def _save_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the model analyses to a folder")
        if folder:
            self.save(Path(folder))

    def save(self, folder: Path) -> list[Path]:
        from ..analyses import records

        record = records.run_record(self._scenario, self.report, self._result)
        folder.mkdir(parents=True, exist_ok=True)
        written = [records.write_record(folder / "model_analyses.json", record)]
        written += records.write_tables(self.report.tables(), folder, record)
        export_log.record("model_analyses", folder)
        return written
