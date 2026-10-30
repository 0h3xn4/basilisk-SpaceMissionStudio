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
"""A lifetime and a propellant budget as JSON files, with what they were
computed from (transparency audit, Phase 2g; ICD-03, ICD 5.3.3).

Each record holds:

- ``inputs``: what was asked (the spacecraft, the options);
- ``model``: the values the calculation used that are not in the scenario
  file (the drag area and coefficient, the rules and margins), named as in
  the code or, for a budget's rules, as in the parameter registry
  (``config.parameters``), with the values in effect;
- ``results``: the figures shown, with their units in their names;
- ``notes`` or ``warnings``: as printed;
- ``provenance``: the tool and Basilisk versions, the scenario's hash, the
  time, the data files read with their SHA-256, and the configuration
  (``config.registry.record``: the project file and each value it
  changes); for a budget after a run, that run's own record too.

Without Basilisk: the records are built from results already computed.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from .. import output_provenance

LIFETIME_KIND = "lifetime"
BUDGET_KIND = "propellant_budget"
LINK_BUDGET_KIND = "link_budget"


def _plain(value):
    """``value`` as JSON: dataclasses, arrays, numbers and dates made plain."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, np.ndarray):
        return [_plain(v) for v in value.tolist()]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _provenance(scenario, data_files: dict) -> dict:
    from ..config import registry

    return dict(output_provenance.scenario_record(scenario), data_files=_plain(data_files),
                configuration=registry.record(scenario))


def lifetime_record(scenario, spacecraft_name: str, end, max_years: float, forecast_percentile: float,
                    drag_coeff: float | None, deorbit_perigee_km: float | None) -> dict:
    """The record of ``end`` (:class:`.lifetime.EndOfLife`), computed for
    ``spacecraft_name`` with these options (:func:`.lifetime.end_of_life`'s);
    ``drag_coeff`` None means the spacecraft's own."""
    from . import lifetime
    from ..config import registry

    life = end.lifetime
    verdicts = {}
    for years, _label, key in lifetime.disposal_rules(scenario):
        verdicts[key] = ("met" if life.meets(years) else "not met") if life.known(years) else "not known"
    rules = {parameter.name: registry.value(parameter.name, scenario)
             for parameter in registry.parameters("lifetime")}  # in effect: provenance.configuration says
    return {
        "kind": LIFETIME_KIND,
        "spacecraft": spacecraft_name,
        "inputs": {"max_years": max_years, "forecast_percentile": forecast_percentile,
                   "drag_coeff": "own" if drag_coeff is None else drag_coeff,
                   "deorbit_perigee_km": deorbit_perigee_km, "from_end_of_run": end.from_end_of_run},
        "model": {"method": "orbit-averaged mean-element decay under drag and J2 (engine.lifetime)",
                  "atmosphere_model": scenario.space_weather.atmosphere_model,
                  "area_m2": end.area_m2, "drag_coeff": end.drag_coeff, "mass_kg": end.mass_kg,
                  "ballistic_coefficient_m2_kg": end.ballistic_coefficient_m2_kg, "rules": rules},
        "results": {"start_utc": life.start_utc, "reentered": life.reentered,
                    "reentry_utc": life.reentry_utc, "lifetime_years": life.lifetime_years,
                    "horizon_years": life.horizon_years, "rules": verdicts,
                    "deorbit": None if end.deorbit is None else _plain(end.deorbit),
                    # How each figure was computed (engine.trace)
                    "traces": _plain(end.traces)},
        "decay": {"time_s": life.time_s, "perigee_altitude_km": life.perigee_altitude_km,
                  "apogee_altitude_km": life.apogee_altitude_km},
        "warnings": list(life.warnings),
        "provenance": _provenance(scenario, end.data_files),
    }


def budget_record(scenario, spacecraft_name: str, budget, result=None) -> dict:
    """The record of ``budget`` (:class:`.propellant_budget.Budget`) for
    ``spacecraft_name``; ``result``: the run it took its simulated
    contributors from, if any."""
    from . import propellant_budget as pb
    from ..config import registry
    from ..schema.scenario import PropellantBudgetConfig

    spacecraft = next(sc for sc in scenario.spacecraft if sc.name == spacecraft_name)
    config = spacecraft.propellant_budget or PropellantBudgetConfig()
    rules = {parameter.name: registry.value(parameter.name, scenario)
             for parameter in registry.parameters("propellant_budget")}  # in effect: provenance.configuration says
    constants = {name: getattr(pb, name) for name in ("G0_M_S2", "MU_EARTH_M3_S2", "REQ_EARTH_M")}
    provenance = _provenance(scenario, budget.data_files)
    if result is not None:
        provenance["run"] = _plain(result.provenance_record())
    return {
        "kind": BUDGET_KIND,
        "spacecraft": spacecraft_name,
        "inputs": {"propellant_budget": _plain(config), "from_run": result is not None},
        "model": {"method": "rocket equation per contributor, in the order of the rows (engine.propellant_budget, "
                            "ESA AD10)", "rules": rules, "constants": constants},
        "results": {"dry_mass_kg": budget.dry_mass_kg, "isp_s": budget.isp_s, "efficiency": budget.efficiency,
                    "iterations": budget.iterations, "rows": _plain(budget.rows),
                    "total_delta_v_m_s": budget.total_delta_v_m_s,
                    "total_propellant_kg": budget.total_propellant_kg,
                    # How each number was computed (engine.trace); each row carries its own two
                    "traces": _plain(budget.traces)},
        "notes": list(budget.notes),
        "provenance": provenance,
    }


def link_budget_record(scenario, spacecraft_name: str, station_name: str, range_m: float, range_source: str,
                       pointing_error_deg: float, traces: dict) -> dict:
    """The record of a link budget (:func:`.link_budget.link_budget_traces`)
    from ``spacecraft_name`` to ``station_name`` at ``range_m``."""
    from ..config import registry

    return {
        "kind": LINK_BUDGET_KIND,
        "spacecraft": spacecraft_name,
        "ground_station": station_name,
        "inputs": {"range_m": range_m, "range_source": range_source, "pointing_error_deg": pointing_error_deg},
        "model": {"method": "free-space Eb/N0 link equation (engine.link_budget)",
                  "rules": {p.name: registry.value(p.name, scenario) for p in registry.parameters("link")}},
        "results": {key: trace.value for key, trace in traces.items()} | {"traces": _plain(traces)},
        "provenance": _provenance(scenario, {}),
    }


def write(path: Path, record: dict) -> Path:
    """``record`` as indented JSON at ``path``."""
    path = Path(path)
    path.write_text(json.dumps(_plain(record), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return path
