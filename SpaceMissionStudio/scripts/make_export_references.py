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

"""Write each export the GUI makes from fixed inputs (UI overhaul M8: the
export files must stay byte-identical to 1.1.0's), through the same engine
and widget functions the GUI calls. No Basilisk needed::

    QT_QPA_PLATFORM=offscreen python scripts/make_export_references.py OUT_DIR

Run with 1.1.0's package first on ``sys.path`` (``PYTHONPATH=<a 1.1.0
checkout>/SpaceMissionStudio``) it wrote the files in
``tests/data/exports_1_1_0.zip`` (a zip, so no line-ending or end-of-file
rule changes a byte); ``tests/gui/test_export_files.py`` runs it on this
code and compares every byte. The inputs are fixed (and the time a provenance record is made is
pinned), so only the export code could make two runs differ.

Covered: the results CSVs and their provenance, the events CSV, the
Mission Output CSV and its provenance, the Monte Carlo runs table, the
budget CSV, the ``.obj`` model and the SIL report. Not covered: the PNG
and SVG plots (the web engine draws them), the flight-software project
(``tests/test_fsw_export.py`` checks it against Basilisk's files) and the
Vizard file (Basilisk writes it during a run).
"""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

_R_M = 6778.0e3  # [m]
_N_RAD_S = math.sqrt(3.986004415e14 / _R_M ** 3)  # [rad/s]
_EPOCH = "2030-01-01T00:00:00"
_PINNED_RECORD = {"spacemissionstudio_version": "1.1.0", "basilisk_version": "2.12.0",
                  "scenario_sha256": "0" * 64, "created_utc": "2030-01-01T00:00:00+00:00"}


def _result():
    from spacemissionstudio.engine.results import ResultSet, RunProvenance, TimeSeries

    t = np.linspace(0.0, 5400.0, 31)  # [s]
    u = _N_RAD_S * t  # [rad]
    result = ResultSet("Reference export")
    result.add(TimeSeries("sat-1.position_N", t, ("x", "y", "z"),
                          np.column_stack([_R_M * np.cos(u), _R_M * np.sin(u), np.zeros_like(u)]), units="m"))
    result.add(TimeSeries("sat-1.battery_charge", t, ("battery_charge",), (300.0 - t / 60.0)[:, None], units="W*h"))
    result.provenance = RunProvenance("1.1.0", "2.12.0", "2030-01-01T00:00:00+00:00", "rk4", 1.0)
    return result


def _events():
    from spacemissionstudio.engine import events as event_model

    return [event_model.Event(event_model.ACCESS, "sat-1", 600.0, 1140.0, "pass over berlin", "elevation 42 deg",
                              other="berlin", quantities=(("max_elevation_deg", 42.25),)),
            event_model.Event(event_model.ECLIPSE, "sat-1", 1800.0, 3900.0, "eclipse (umbra)",
                              quantities=(("lowest_sunlight_pct", 0.0),)),
            event_model.Event(event_model.MODE, "sat-1", 4200.0, 4200.0, "mode: sun pointing", note="sun pointing")]


def _summary():
    from spacemissionstudio.engine.results import CommandSummary, ReportEntry

    return CommandSummary(reports=[
        ReportEntry(label="Before burn", t_s=600.0, values={"sat-1.position_N": np.array([_R_M, 0.0, 0.0]),
                                                            "sat-1.battery_charge": np.array([290.0])}),
        ReportEntry(label="After burn", t_s=1200.0, values={"sat-1.position_N": np.array([0.0, _R_M, 1.5]),
                                                           "sat-1.battery_charge": np.array([280.0])})],
        commands_executed=4)


def _batch(folder: Path):
    from spacemissionstudio.engine import monte_carlo_results as mcr

    t = np.linspace(0.0, 3000.0, 30)  # [s]
    runs = 4
    phase = (np.arange(runs) - (runs - 1) / 2) * 1e-4  # [rad]
    u = _N_RAD_S * t[None, :] + phase[:, None]
    r = np.stack([_R_M * np.cos(u), _R_M * np.sin(u), np.zeros_like(u)], axis=-1)
    v = np.stack([-_R_M * _N_RAD_S * np.sin(u), _R_M * _N_RAD_S * np.cos(u), np.zeros_like(u)], axis=-1)
    batch = mcr.MonteCarloBatch("Reference batch", "earth", t, list(range(runs)), [runs], {"sat-1": r},
                                {"sat-1": v}, [{"sat-1 drag coefficient [-]": 2.0 + 0.2 * k} for k in range(runs)],
                                _EPOCH)
    mcr.save(batch, folder)


def _budget():
    from types import SimpleNamespace

    rows = [SimpleNamespace(phase="Operations", contributor="In-plane orbit control", delta_v_m_s=12.3456,
                            propellant_kg=0.41234, margin="5 %", source="last run"),
            SimpleNamespace(phase="End of life", contributor="Lower perigee", delta_v_m_s=None, propellant_kg=1.5,
                            margin="", source="AD10 Sec. 5")]
    return SimpleNamespace(rows=rows, total_delta_v_m_s=12.3456, total_propellant_kg=1.91234)


def _sil_report():
    from spacemissionstudio.sil.contract import PortSpec
    from spacemissionstudio.sil.report import Comparator, SilReport, timing_summary

    layout = {"itemsize": 16, "fields": [{"name": "torque", "offset": 0, "shape": [2], "kind": "<f8"}]}
    port = PortSpec("rw_torqueOutMsg", "Demo", 16, "0" * 16)
    comparator = Comparator([port], [], {"Demo": layout}, expected_steps=3)
    for t in (0.0, 1.0, 2.0):
        comparator.add(t, [struct.pack("<2d", 1.0 + t, 0.5)], [struct.pack("<2d", 1.0, 0.5)])
    report = SilReport(spacecraft="sat-1", binary="/opt/fsw/fsw_host", binary_sha256="a" * 64, fsw_name="sat-1",
                       fsw_config_digest="1" * 64, scenario_config_digest="1" * 64, contract_version=1,
                       rate_ns=1_000_000_000, address_kind="unix", round_trip=timing_summary([200_000, 400_000]),
                       execution=timing_summary([5_000, 6_000]), completed=True)
    comparator.finish(report)
    report.steps = 3
    return report


def _model():
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    return SpacecraftModelConfig(parts=[
        ModelPartConfig("bus", "box", {"x": 0.3, "y": 0.2, "z": 0.2}, mass_kg=12.0),  # [m], [kg]
        ModelPartConfig("antenna", "cylinder", {"diameter": 0.06, "height": 0.1}, position_b_m=[0.0, 0.0, 0.15],
                        mass_kg=0.4),  # [m], [kg]
        ModelPartConfig("panel", "panel", {"width": 0.2, "length": 0.4, "thickness": 0.01},
                        position_b_m=[0.0, 0.3, 0.0], mass_kg=1.1, distribution="shell")])  # [m], [kg]


def write_all(out: Path) -> list:
    """Every covered export into ``out``; the files written."""
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio import output_provenance

    app = QApplication.instance() or QApplication(sys.argv[:1])
    record = output_provenance.scenario_record
    output_provenance.scenario_record = lambda scenario: dict(_PINNED_RECORD)  # the time it is made, pinned
    try:
        _write(out, app)
    finally:
        output_provenance.scenario_record = record
    return sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())


def _write(out: Path, app) -> None:
    from spacemissionstudio import output_provenance
    from spacemissionstudio.engine import events as event_model

    out.mkdir(parents=True, exist_ok=True)

    _result().export_csv(out / "results")  # Results > Export CSV...
    event_model.write_csv(_events(), out / "events.csv", _EPOCH)  # Timeline > Export CSV...
    summary_path = out / "mission_output.csv"
    _summary().export_csv(summary_path)  # Output > Export CSV...
    output_provenance.write_sidecar(summary_path, _result().provenance_record())

    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _batch(out / "batch_folder")
    widget = MonteCarloResultsWidget()
    widget.load_folder(out / "batch_folder")
    widget.export_table_csv(out / "monte_carlo_runs.csv")  # Monte Carlo > Export table CSV...
    widget.deleteLater()
    for path in sorted((out / "batch_folder").iterdir()):  # the batch summary is the engine's: not an export here
        path.unlink()
    (out / "batch_folder").rmdir()

    from spacemissionstudio.gui.budget_widget import BudgetWidget
    from spacemissionstudio.schema import load_scenario

    templates = Path(sys.modules["spacemissionstudio"].__file__).parent / "scenarios" / "templates"
    scenario = load_scenario(templates / "01_two_body_circular_orbit.json")
    budget = BudgetWidget()
    budget._scenario, budget._budget = scenario, _budget()
    budget._copy()  # Budget > Copy as CSV
    (out / "budget.csv").write_bytes(app.clipboard().text().encode("utf-8"))  # the clipboard's text, as it is
    budget.deleteLater()

    from spacemissionstudio.model3d import model as model3d
    from spacemissionstudio.model3d import obj_io

    obj_io.write_obj(out / "model.obj", model3d.obj_groups(model3d.derive(_model(), templates)))  # 3D model

    (out / "sil_report.json").write_text(_sil_report().to_json() + "\n", encoding="utf-8")  # SIL > Save report


def main(argv: list) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    written = write_all(Path(argv[0]))
    print(json.dumps(written, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
