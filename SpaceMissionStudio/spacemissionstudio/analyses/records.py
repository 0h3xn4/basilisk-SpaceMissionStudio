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
"""The model analyses as files: a JSON record and CSV tables, each with
what they were computed from (the same provenance as the other analyses'
records, ``engine.analysis_records``).

A record holds ``inputs`` (the spacecraft, the sampling), ``model`` (the
method and the sources of the values it used), ``results`` (every table,
with units in the column names), ``findings`` (each with its rule) and
``notes``, and ``provenance``. A table is a CSV with a
``<file>.provenance.json`` beside it.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .. import output_provenance
from ..engine.analysis_records import _plain, _provenance
from . import common

DESIGN_KIND = "design_checks"

_RAY_METHOD = ("ray casting against the model's parts: exact intersections for boxes, panels, prisms, cylinders, "
               "cones and spheres, a bounding-volume hierarchy of triangles for meshes; a cone sampled uniformly in "
               "solid angle (Fibonacci spiral), with the binomial standard error (model3d.raycast)")


def design_tables(report) -> dict:
    """``{table name: rows}`` of a :class:`.design_checks.DesignReport`."""
    tables = {}
    if report.fov is not None:
        tables["field_of_view"] = report.fov.rows()
    if report.authority is not None:
        tables["thruster_authority"] = [{**row, "torque_bol_n_m": " ".join(f"{v:.6g}" for v in row["torque_bol_n_m"]),
                                         "torque_eol_n_m": " ".join(f"{v:.6g}" for v in row["torque_eol_n_m"]),
                                         "arm_bol_m": " ".join(f"{v:.6g}" for v in row["arm_bol_m"]),
                                         "arm_eol_m": " ".join(f"{v:.6g}" for v in row["arm_eol_m"])}
                                        for row in report.authority.rows()]
    if report.plumes:
        tables["plume_impingement"] = [{"thruster": p.thruster, "half_angle_deg": p.half_angle_deg,
                                        "blocked_percent": 100.0 * p.blocked_fraction,
                                        "standard_error_percent": 100.0 * p.standard_error,
                                        "parts": "; ".join(f"{q} {100.0 * f:.1f} %" for q, f in p.by_part.items()),
                                        "samples": p.samples} for p in report.plumes]
    if report.mass is not None:
        tables["mass_budget"] = report.mass.rows()
    if report.launcher is not None:
        tables["launcher_envelope"] = [{"part": p.part, "outside_m": p.distance_m, "where": p.where}
                                       for p in report.launcher.protrusions]
    return {name: rows for name, rows in tables.items() if rows}


def design_record(scenario, report) -> dict:
    """The JSON record of ``report`` (a :class:`.design_checks.DesignReport`)."""
    sc = common.spacecraft(scenario, report.spacecraft)
    mass = report.mass
    results = {"tables": design_tables(report)}
    if mass is not None:
        results["mass_budget_totals"] = {
            "basic_dry_kg": mass.basic_dry_kg, "growth_kg": mass.growth_kg,
            "dry_with_growth_kg": mass.dry_with_growth_kg, "system_margin_percent": mass.system_margin_percent,
            "system_margin_kg": mass.system_margin_kg, "propellant_kg": mass.propellant_kg,
            "launch_mass_kg": mass.launch_mass_kg, "mass_limit_kg": mass.mass_limit_kg,
            "limit_source": mass.limit_source, "headroom_kg": mass.headroom_kg}
    if report.authority is not None:
        results["thruster_authority"] = {"com_bol_b_m": report.authority.com_bol_b_m,
                                         "com_eol_b_m": report.authority.com_eol_b_m,
                                         "propellant_kg": report.authority.propellant_kg,
                                         "matrix_bol": report.authority.matrix_bol,
                                         "matrix_eol": report.authority.matrix_eol,
                                         "rank_bol": report.authority.rank("bol"),
                                         "rank_eol": report.authority.rank("eol")}
    if report.launcher is not None:
        check = report.launcher
        results["launcher"] = {"envelope": check.envelope, "source": check.source,
                               "configuration": check.configuration, "fits": check.fits,
                               "largest_faceting_error_m": check.largest_faceting_error_m,
                               "mass_kg": check.mass_kg, "mass_limit_kg": check.mass_limit_kg,
                               "com_height_m": check.com_height_m, "com_height_limit_m": check.com_height_limit_m,
                               "com_lateral_m": check.com_lateral_m, "com_lateral_limit_m": check.com_lateral_limit_m,
                               "out_of_scope": check.out_of_scope}
    notes = []
    if report.fov is not None:
        notes += [f"field of view not checked: {item}: {why}" for item, why in report.fov.skipped]
    notes += [f"plume not checked: {item}: {why}" for item, why in report.plume_skipped]
    for part in (report.authority, mass, report.launcher):
        notes += list(getattr(part, "notes", []) or [])
    return {
        "kind": DESIGN_KIND,
        "spacecraft": report.spacecraft,
        "inputs": {"samples": report.samples, "model_sha256": common.model_hash(sc.model)
                   if sc.model is not None else None},
        "model": {"ray_casting": _RAY_METHOD,
                  "mass_margins": {"policy": mass.policy, "source": mass.policy_source} if mass is not None else None,
                  "plume": "geometry only: a cone of the user's half-angle along minus the thrust direction"},
        "results": _plain(results),
        "findings": [finding.to_dict() for finding in report.findings()],
        "notes": notes,
        "provenance": _provenance(scenario, {}),
    }


def write_tables(tables: dict, folder, record: dict) -> list[Path]:
    """Each table as ``<folder>/<name>.csv``, with its provenance beside it
    (``record['provenance']``); returns the CSV paths."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows in tables.items():
        path = folder / f"{name}.csv"
        columns = list(rows[0])
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(_plain(rows))
        output_provenance.write_sidecar(path, dict(_plain(record["provenance"]), kind=record["kind"], table=name,
                                                   spacecraft=record["spacecraft"]))
        written.append(path)
    return written


def write_record(path, record: dict) -> Path:
    """``record`` as JSON at ``path`` (``engine.analysis_records.write``)."""
    from ..engine import analysis_records

    return analysis_records.write(Path(path), record)


RUN_KIND = "model_analyses"
REENTRY_KIND = "reentry_estimate"


def run_record(scenario, report, result) -> dict:
    """The JSON record of a run's model analyses (``run_analyses.RunReport``)."""
    sc = common.spacecraft(scenario, report.spacecraft)
    budget = report.disturbances
    results = {"tables": report.tables()}
    if budget is not None:
        results["disturbances"] = {
            "period_s": budget.period_s, "whole_orbits": budget.whole_orbits,
            "momentum_end_n_m_s": budget.momentum_end_n_m_s, "momentum_max_n_m_s": budget.momentum_max_n_m_s,
            "momentum_per_orbit_n_m_s": budget.momentum_per_orbit_n_m_s,
            "wheel_capacity_n_m_s": budget.wheel_capacity_n_m_s, "wheel_ratio": budget.wheel_ratio(),
            "dipole_available_a_m2": budget.dipole_available_a_m2, "dipole_needed_a_m2": budget.dipole_needed_a_m2}
    record = {
        "kind": RUN_KIND,
        "spacecraft": report.spacecraft,
        "inputs": {"model_analyses": _plain(sc.model_analyses), "samples": common.samples_for(sc)},
        "model": {"ray_casting": _RAY_METHOD,
                  "pages": ["docs/models/model-analyses.md"]},
        "results": _plain(results),
        "findings": [finding.to_dict() for finding in report.findings()],
        "notes": list(report.notes) + (list(budget.notes) if budget is not None else []),
        "provenance": _provenance(scenario, {}),
    }
    if getattr(result, "provenance", None) is not None:
        record["provenance"]["run"] = _plain(result.provenance_record())
    return record


def reentry_record(scenario, estimate) -> dict:
    """The JSON record of a preliminary re-entry estimate."""
    from ..config import registry

    return {
        "kind": REENTRY_KIND,
        "spacecraft": estimate.spacecraft,
        "label": estimate.label,
        "inputs": {"population_density_per_km2": estimate.population_density_per_km2},
        "model": {"page": "docs/models/reentry.md",
                  "rules": {parameter.name: registry.value(parameter.name, scenario)
                            for parameter in registry.parameters("reentry")}},
        "results": _plain({"fragments": estimate.rows(), "casualty_area_m2": estimate.casualty_area_m2,
                           "casualty_area_demise_prone_m2": estimate.casualty_area_demise_prone_m2,
                           "risk": estimate.risk, "risk_limit": estimate.risk_limit,
                           "compliant": estimate.compliant}),
        "notes": list(estimate.notes),
        "provenance": _provenance(scenario, {}),
    }
