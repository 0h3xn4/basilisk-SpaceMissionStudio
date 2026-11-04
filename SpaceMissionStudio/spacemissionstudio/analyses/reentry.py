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
"""A preliminary re-entry casualty-risk estimate in the manner of NASA's
DAS, from the 3D model's parts (model analyses, Phase D). Labelled
"preliminary" everywhere: it is no substitute for DAS, DRAMA or SESAM.

1. **Break-up** at ``reentry.breakup_altitude_km`` (78 km: DAS 3.0 User's
   Guide, NASA/TP-2019-220300, Sec. 3.8): every part with mass becomes a
   fragment with its own mass, surface area ``S`` and material.
2. **Descent** of each fragment: planar flight over a spherical,
   non-rotating Earth with point-mass gravity, from the circular speed at
   the break-up altitude and a flight-path angle of zero, in the U.S.
   Standard Atmosphere 1976 (Basilisk's table). A convex body tumbling at
   random in Newtonian flow has an orientation-averaged drag ``q S / 4``:
   ``C_d = 1`` on its mean projected area ``S / 4`` (Cauchy).
3. **Heating**: the Sutton–Graves stagnation-point flux
   ``q_s = k sqrt(rho / R_n) V^3`` with ``k = 1.748e-4 kg^0.5/m``,
   derived from Sutton and Graves's ``K_air`` (NASA TR R-376, Table II;
   decision D-15), ``R_n`` the radius of the sphere with the same mean
   projected area. The heat absorbed is ``q_s S / 4`` (the windward
   ``cos`` law averaged over a tumbling convex body), less the
   re-radiation ``eps sigma S T^4``.
4. **Demise**: a lumped energy balance from 300 K: the fragment heats at
   ``m c_p`` to its melting temperature, then melts as it absorbs
   ``m h_f``. A fragment that lands partly melted keeps the unmelted mass.
   No emissivity at re-entry temperatures could be sourced, so each
   fragment is computed twice, with ``eps = 0`` (the most heat: demise-
   prone) and ``eps = 1`` (survival-prone); the survival-prone result is
   the one reported (decision D-14).
5. **Casualty area**: each fragment landing with more than
   ``reentry.casualty_energy_j`` (15 J: NASA-STD-8719.14B, via the DAS
   guide) adds ``(0.6 + sqrt(A_i))^2`` (Kelley, NTRS 20120002794, Eq. 1;
   0.6 m the root of a standing person's cross-section), ``A_i = S / 4``.
6. **Risk**: ``E_c = A_c rho_pop`` with the population density the user
   gives (no default, decision D-16), against ``reentry.casualty_risk_limit``
   (1:10,000, NASA-STD-8719.14B Req. 4.7-1a, via the DAS guide).

A part with no material, or a material without the thermal values
(melting temperature, heat of fusion, specific heat), cannot
demise here: it is counted as surviving whole, and said so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..config import materials as library
from ..config import registry
from ..constants import EARTH_EQUATORIAL_RADIUS_M, EARTH_GM_M3_S2

SUTTON_GRAVES_K = 0.1113 / (2.0 * math.sqrt(101325.0))  # [kg^0.5/m] K_air / (2 sqrt(1 atm)), decision D-15
STEFAN_BOLTZMANN = 5.670374419e-8  # [W/(m^2 K^4)] CODATA 2018 (exact in the 2019 SI)
INITIAL_TEMPERATURE_K = 300.0  # [K] the lumped start temperature (DAS's assumption, Sec. 4.1.3)
_STEP_S = 0.05  # [s] RK4 step
_THERMAL = ("melting_temperature_k", "heat_of_fusion_j_kg", "specific_heat_j_kg_k")


@dataclass
class Fragment:
    part: str
    material: str
    mass_kg: float  # [kg]
    area_m2: float  # [m^2] surface S
    demise_altitude_km: float | None = None  # [km] None: it lands
    surviving_mass_kg: float = 0.0  # [kg]
    impact_energy_j: float = 0.0  # [J]
    casualty_area_m2: float = 0.0  # [m^2]
    note: str = ""


@dataclass
class ReentryEstimate:
    spacecraft: str
    breakup_altitude_km: float
    fragments: list = field(default_factory=list)  # list[Fragment], survival-prone (eps = 1): the reported
    demise_prone: list = field(default_factory=list)  # list[Fragment], eps = 0
    population_density_per_km2: float | None = None
    risk_limit: float = 1e-4
    notes: list = field(default_factory=list)
    label: str = "Preliminary estimate (DAS-like, simplified): not a substitute for DAS, DRAMA or SESAM."

    @property
    def casualty_area_m2(self) -> float:
        return sum(f.casualty_area_m2 for f in self.fragments)

    @property
    def casualty_area_demise_prone_m2(self) -> float:
        return sum(f.casualty_area_m2 for f in self.demise_prone)

    @property
    def risk(self) -> float | None:
        """Expected casualties ``A_c rho_pop`` (1/km^2 to 1/m^2), or None
        without a population density."""
        if self.population_density_per_km2 is None:
            return None
        return self.casualty_area_m2 * self.population_density_per_km2 * 1e-6

    @property
    def compliant(self) -> bool | None:
        return None if self.risk is None else self.risk <= self.risk_limit

    def rows(self) -> list[dict]:
        rows = []
        for survival, demise in zip(self.fragments, self.demise_prone):
            rows.append({"part": survival.part, "material": survival.material, "mass_kg": survival.mass_kg,
                         "surface_m2": survival.area_m2,
                         "demise_altitude_km": survival.demise_altitude_km,
                         "surviving_mass_kg": survival.surviving_mass_kg,
                         "impact_energy_j": survival.impact_energy_j,
                         "casualty_area_m2": survival.casualty_area_m2,
                         "demise_prone_surviving_mass_kg": demise.surviving_mass_kg,
                         "demise_prone_casualty_area_m2": demise.casualty_area_m2, "note": survival.note})
        return rows


def thermal_values(model, name: str) -> dict | None:
    """The material ``name``'s thermal values
    ``{melting_temperature_k, heat_of_fusion_j_kg, specific_heat_j_kg_k}``
    from the model's own materials or the library, or None when one is
    missing."""
    own = next((m for m in model.materials if m.name == name), None)
    if own is not None:
        values = {key: getattr(own, key) for key in _THERMAL}
    elif name in library.MATERIALS:
        entry = library.MATERIALS[name]
        values = {key: getattr(entry, key).value if getattr(entry, key) is not None else None for key in _THERMAL}
    else:
        return None
    return values if all(v is not None for v in values.values()) else None


class _Atmosphere:
    """US76 density by altitude [m] (Basilisk's table, read once)."""

    _cached = None

    def __init__(self):
        if _Atmosphere._cached is None:
            from ..engine import atmosphere_tables, kernels

            path = kernels.cached_path(atmosphere_tables.data_file("us_standard_1976"))
            altitudes, densities, _temperatures = atmosphere_tables.load("us_standard_1976", path)
            _Atmosphere._cached = (np.asarray(altitudes, float), np.log(np.asarray(densities, float)))
        self.altitudes, self.log_density = _Atmosphere._cached

    def density(self, altitude_m: float) -> float:
        return float(np.exp(np.interp(altitude_m, self.altitudes, self.log_density)))


def descend(mass_kg, area_m2, thermal, emissivity, breakup_m, atmosphere) -> tuple:
    """``(demise altitude [m] or None, surviving mass [kg], impact speed
    [m/s])`` of one fragment (module docstring)."""
    radius = EARTH_EQUATORIAL_RADIUS_M
    mu = EARTH_GM_M3_S2
    projected = area_m2 / 4.0  # [m^2]
    nose = math.sqrt(projected / math.pi)  # [m]
    melt_t, fusion, cp = (thermal["melting_temperature_k"], thermal["heat_of_fusion_j_kg"],
                          thermal["specific_heat_j_kg_k"]) if thermal else (None, None, None)
    # state: altitude [m], speed [m/s], flight-path angle [rad], stored energy above 300 K [J]
    state = np.array([breakup_m, math.sqrt(mu / (radius + breakup_m)), 0.0, 0.0])
    sensible = mass_kg * cp * (melt_t - INITIAL_TEMPERATURE_K) if thermal else math.inf  # [J]
    to_melt = mass_kg * fusion if thermal else math.inf  # [J]

    def temperature(energy):
        if not thermal:
            return INITIAL_TEMPERATURE_K
        return INITIAL_TEMPERATURE_K + min(energy, sensible) / (mass_kg * cp)

    def derivative(s):
        h, v, gamma, energy = s
        r = radius + h
        g = mu / r ** 2
        rho = atmosphere.density(h)
        drag = 0.5 * rho * v * v * projected / mass_kg  # [m/s^2] C_d = 1
        heat = SUTTON_GRAVES_K * math.sqrt(rho / nose) * v ** 3 * projected  # [W]
        heat -= emissivity * STEFAN_BOLTZMANN * area_m2 * temperature(energy) ** 4
        return np.array([v * math.sin(gamma), -drag - g * math.sin(gamma), (v / r - g / v) * math.cos(gamma),
                         heat if thermal else 0.0])

    while state[0] > 0.0:
        k1 = derivative(state)
        k2 = derivative(state + 0.5 * _STEP_S * k1)
        k3 = derivative(state + 0.5 * _STEP_S * k2)
        k4 = derivative(state + _STEP_S * k3)
        state = state + _STEP_S / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        state[3] = max(state[3], 0.0)
        if state[3] >= sensible + to_melt:
            return state[0], 0.0, 0.0
    melted = min(max(state[3] - sensible, 0.0), to_melt)
    surviving = mass_kg * (1.0 - melted / to_melt) if thermal else mass_kg
    return None, surviving, float(state[1])


def _surface_areas(model, derived) -> dict:
    """Each built part's whole surface [m^2], hidden parts too (they have
    mass): the shape's true faces, or a mesh's triangles."""
    from ..model3d import shapes

    built = {p.name: p for p in derived.parts if p.mesh is not None}
    areas = {}
    for part in model.parts:
        if part.name not in built:
            continue
        if part.shape == "mesh":
            a, b, c = built[part.name].mesh.corners()
            areas[part.name] = float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())
        else:
            dims = {k: float(v) for k, v in part.dimensions_m.items()}
            areas[part.name] = float(sum(face.area_m2 for face in shapes.faces(part.shape, dims, sides=part.sides)))
    return areas


def reentry_estimate(sc, base_dir=None, population_density_per_km2=None, scenario=None) -> ReentryEstimate:
    """The :class:`ReentryEstimate` of spacecraft ``sc``'s 3D model."""
    from . import common

    if sc.model is None:
        raise common.AnalysisError(f"{sc.name}: the re-entry estimate needs a 3D model (its parts and materials)")
    breakup_km = registry.value("reentry.breakup_altitude_km", scenario)
    energy_limit = registry.value("reentry.casualty_energy_j", scenario)
    estimate = ReentryEstimate(sc.name, breakup_km, population_density_per_km2=population_density_per_km2,
                               risk_limit=registry.value("reentry.casualty_risk_limit", scenario))
    derived, _scene = common.derived_and_scene(sc, "deployed", base_dir)
    areas = _surface_areas(sc.model, derived)
    atmosphere = _Atmosphere()
    for part in sc.model.parts:
        if not part.counts_toward_mass or part.mass_kg <= 0.0 or areas.get(part.name, 0.0) <= 0.0:
            continue
        thermal = thermal_values(sc.model, part.material) if part.material else None
        note = "" if thermal else ("no material: counted as surviving whole" if not part.material else
                                   f"{part.material} has no melting temperature, heat of fusion or specific heat: "
                                   "counted as surviving whole")
        for emissivity, out in ((1.0, estimate.fragments), (0.0, estimate.demise_prone)):
            fragment = Fragment(part.name, part.material, float(part.mass_kg), areas[part.name], note=note)
            demise_m, surviving, speed = descend(part.mass_kg, areas[part.name], thermal, emissivity,
                                                 breakup_km * 1000.0, atmosphere)
            if demise_m is not None:
                fragment.demise_altitude_km = float(demise_m) / 1000.0
            fragment.surviving_mass_kg = surviving
            fragment.impact_energy_j = 0.5 * surviving * speed ** 2
            if fragment.impact_energy_j > energy_limit:
                fragment.casualty_area_m2 = (0.6 + math.sqrt(areas[part.name] / 4.0)) ** 2
            out.append(fragment)
    if population_density_per_km2 is None:
        estimate.notes.append("no population density given: the casualty area only (decision D-16)")
    estimate.notes.append("the mass of the parts as given; equipment items and propellant are not fragments")
    return estimate
