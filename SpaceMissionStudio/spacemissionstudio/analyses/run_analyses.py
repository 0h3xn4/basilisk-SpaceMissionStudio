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
"""The model analyses of a finished run (decision D-07): the series they
add to its results, for each spacecraft that asks
(``model_analyses``). Called by ``engine.service`` at the end of
``_extract_results``, after every recorded series, like the link margin.

Each analysis is its own module (``blinding``, ``shading``, ``exposure``,
``brightness``); what one cannot compute is a note in the run's warnings,
never an error that loses the run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from ..engine.findings import Finding
from ..config import registry
from . import blinding, brightness, common, exposure, shading
from .run_geometry import run_geometry

_log = logging.getLogger(__name__)


def add_to(result, scenario, base_dir=None) -> None:
    """Add every asked-for analysis's series to ``result``."""
    for sc in scenario.spacecraft:
        analyses = sc.model_analyses
        if analyses is None:
            continue
        try:
            _add_spacecraft(result, scenario, sc, base_dir)
        except Exception as exc:  # noqa: BLE001 -- the run's results stand; the analysis says it failed
            _log.debug("model analyses of %s failed", sc.name, exc_info=True)
            result.warnings.append(Finding(f"{sc.name}: model analyses not made ({type(exc).__name__}: {exc})",
                                           "check.not_run"))


def _note(result, sc, text: str) -> None:
    result.warnings.append(Finding(f"{sc.name}: model analyses: {text}", "analyses.note"))


def _add_spacecraft(result, scenario, sc, base_dir) -> None:
    analyses = sc.model_analyses
    geometry = run_geometry(result, sc.name, scenario.gravity.central_body)
    if geometry is None:
        _note(result, sc, "the run recorded no attitude: nothing computed")
        return
    items = common.mounted(sc)
    if analyses.disturbance_torques:  # undersized wheels or magnetorquers: the run's warnings (Problems panel)
        from .disturbances import disturbance_budget

        budget = disturbance_budget(result, sc)
        if budget is not None:
            result.warnings.extend(budget.findings())
    if analyses.sensor_blinding:
        series, notes = blinding.blinding_series(geometry, items)
        for one in series:
            result.add(one)
        for text in notes:
            _note(result, sc, text)
        if not series:
            _note(result, sc, "sensor blinding: no mounted item has exclusion angles")
    if analyses.antenna_obstruction:
        antenna = next((item for item in items if item.kind == "antenna"), None)
        if antenna is None:
            _note(result, sc, "antenna obstruction: no antenna is mounted (rf_link.antenna_mount or an equipment "
                              "item of kind antenna)")
        else:
            scene = common.scene(sc, "deployed", base_dir)
            for one in blinding.obstruction_series(result, geometry, antenna, scene,
                                                   [gs.name for gs in scenario.ground_stations]):
                result.add(one)
    light = None
    if analyses.array_shading or analyses.surface_exposure or analyses.brightness:
        light = shading.facet_light(sc, base_dir, common.samples_for(sc))
    found = []
    if analyses.array_shading:
        efficiency = sc.power.panel_efficiency if sc.power is not None else None
        found.append(shading.shading_series(geometry, light, items, efficiency))
    if analyses.surface_exposure:
        found.append(exposure.exposure_series(result, geometry, light, scenario.gravity.central_body))
    if analyses.brightness:
        sites = [(gs.name, gs.min_elevation_deg) for gs in scenario.ground_stations]
        sites += [(site.name, site.min_elevation_deg) for site in analyses.observers
                  if site.name not in {gs.name for gs in scenario.ground_stations}]
        depression = registry.value("analyses.observer_sun_depression_deg", scenario)  # [deg]
        found.append(brightness.brightness_series(result, geometry, light, sites, depression))
    for series, notes in found:
        for one in series:
            result.add(one)
        for text in notes:
            _note(result, sc, text)


def expected_names(scenario, sc) -> list[str]:
    """The series :func:`add_to` and the recorders behind it give ``sc``
    (``engine.series_names``), as far as the scenario says."""
    analyses = sc.model_analyses
    if analyses is None:
        return []
    from ..model3d.equipment import mounted_items

    names: list[str] = []
    stations = [gs.name for gs in scenario.ground_stations]
    try:
        items = mounted_items(sc)
    except Exception:  # noqa: BLE001 -- a half-edited model: no item names to offer
        items = []
    if analyses.sensor_blinding:
        blinded = [item for item in items if item.has_exclusions and item.boresight_b is not None]
        names += [f"{sc.name}.blinding.{item.name}" for item in blinded]
        if any(item.kind == "star_tracker" for item in blinded):
            names.append(f"{sc.name}.blinding.all_star_trackers")
    if analyses.antenna_obstruction:
        names += [f"{gs}.access_to_{sc.name}.antenna_obstructed" for gs in stations]
    if analyses.array_shading:
        cells = [item for item in items if item.kind == "solar_cell"]
        names += [f"{sc.name}.shading.{item.name}" for item in cells]
        if cells and sc.power is not None:
            names.append(f"{sc.name}.shading.power")
    if analyses.surface_exposure:
        if sc.enable_drag:
            names += [f"{sc.name}.atmosphere.density", f"{sc.name}.exposure.ao_flux"]
        names.append(f"{sc.name}.exposure.sun_factor")
    if analyses.brightness:
        sites = stations + [site.name for site in analyses.observers if site.name not in stations]
        names += [f"{site}.brightness_of_{sc.name}.visual_magnitude" for site in sites]
    return names


@dataclass
class RunReport:
    """What a finished run's model analyses give for one spacecraft, in
    tables (the Results tab, the command line, the record)."""

    spacecraft: str
    disturbances: object | None = None  # disturbances.DisturbanceBudget
    blinding: list = field(default_factory=list)  # rows
    obstruction: list = field(default_factory=list)
    shading: list = field(default_factory=list)
    exposure: list = field(default_factory=list)
    brightness: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def findings(self) -> list:
        return self.disturbances.findings() if self.disturbances is not None else []

    def tables(self) -> dict:
        tables = {"blinding": self.blinding, "antenna_obstruction": self.obstruction, "array_shading": self.shading,
                  "surface_exposure": self.exposure, "brightness": self.brightness}
        if self.disturbances is not None:
            tables["disturbance_torques"] = self.disturbances.rows()
        return {name: rows for name, rows in tables.items() if rows}


def _on_time(series, column: int = -1) -> tuple[float, float]:
    """``(fraction of samples on, time on [s])`` of a 0/1 column."""
    t = np.asarray(series.time_s, dtype=float)
    on = np.asarray(series.data, dtype=float)[:, column] > 0.5
    dt = np.diff(t, append=t[-1]) if len(t) else t
    return (float(on.mean()) if len(on) else 0.0), float(dt[on].sum())


def report(result, scenario, sc) -> RunReport:
    """The :class:`RunReport` of ``sc`` from ``result`` (series the run
    recorded; nothing is computed again but the budgets)."""
    from . import disturbances, exposure

    out = RunReport(sc.name, notes=[str(w) for w in result.warnings if f"{sc.name}: model analyses" in str(w)])
    out.disturbances = disturbances.disturbance_budget(result, sc)
    for name, series in result.series.items():
        if name.startswith(f"{sc.name}.blinding."):
            fraction, seconds = _on_time(series)
            out.blinding.append({"item": name.split(".blinding.", 1)[1], "blinded_percent": 100.0 * fraction,
                                 "blinded_minutes": seconds / 60.0})
        elif name.endswith(f".access_to_{sc.name}.antenna_obstructed"):
            access = result.series.get(name.replace(".antenna_obstructed", ".has_access"))
            _fraction, blocked = _on_time(series, 0)
            pass_s = _on_time(access, 0)[1] if access is not None else 0.0
            out.obstruction.append({"station": name.split(".access_to_", 1)[0], "pass_minutes": pass_s / 60.0,
                                    "obstructed_minutes": blocked / 60.0})
        elif name.startswith(f"{sc.name}.shading.") and name != f"{sc.name}.shading.power":
            shaded = np.asarray(series.data, dtype=float)[:, 0]
            out.shading.append({"cells": name.split(".shading.", 1)[1], "mean_shaded_percent": 100.0 * shaded.mean(),
                                "max_shaded_percent": 100.0 * shaded.max()})
        elif name.endswith(f".brightness_of_{sc.name}.visual_magnitude"):
            magnitude = np.asarray(series.data, dtype=float)[:, 0]
            seen = np.isfinite(magnitude)
            t = np.asarray(series.time_s, dtype=float)
            dt = np.diff(t, append=t[-1]) if len(t) else t
            out.brightness.append({"site": name.split(".brightness_of_", 1)[0],
                                   "visible_minutes": float(dt[seen].sum()) / 60.0,
                                   "brightest_mag": float(np.nanmin(magnitude)) if seen.any() else None})
    power = result.series.get(f"{sc.name}.shading.power")
    if power is not None:
        data = np.asarray(power.data, dtype=float)
        lost = np.trapezoid(data[:, -2] - data[:, -1], power.time_s) / 3600.0  # [W*h]
        out.notes.append(f"array shading: {lost:.3g} W*h lost over the run "
                         f"({100.0 * lost / max(np.trapezoid(data[:, -2], power.time_s) / 3600.0, 1e-12):.2g} %)")
    if f"{sc.name}.exposure.sun_factor" in result.series:
        materials = _face_materials(sc)
        out.exposure = exposure.totals(result, sc, materials)
    return out


def _face_materials(sc) -> dict:
    """``{facet name: (material, erosion yield [cm^3/atom] or None)}``: a
    face property's material, else its part's."""
    from ..config import materials as library

    if sc.model is None:
        return {}

    def erosion(name):
        own = next((m for m in sc.model.materials if m.name == name), None)
        if own is not None:
            return own.ao_erosion_yield_cm3_atom
        entry = library.MATERIALS.get(name)
        return entry.ao_erosion_yield_cm3_atom.value if entry and entry.ao_erosion_yield_cm3_atom else None

    found = {}
    by_part = {p.name: p.material for p in sc.model.parts if p.material}
    try:
        derived, _scene = common.derived_and_scene(sc, "deployed", getattr(sc, "_base_dir", None))
        names = [f.name for f in derived.facets]
    except Exception:  # noqa: BLE001 -- no facets: no materials to give
        names = []
    for name in names:
        part, face = name.split(": ", 1)
        override = next((fp.material for fp in sc.model.face_properties
                         if fp.part == part and fp.material and fp.face in (face, _group(face))), "")
        material = override or by_part.get(part, "")
        if material:
            found[name] = (material, erosion(material))
    return found


def _group(face: str) -> str:
    from ..model3d.model import face_group

    return face_group(face)
