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
"""Environment exposure of each face over a run (model analyses).

**Atomic oxygen.** The flux on a facet is ``n_O |v| max(0, n . v_hat)
(1 - f)`` (NASA CR-189627's flux to a surface), with ``v`` the velocity
relative to the co-rotating atmosphere (``v - w_E x r``) and ``f`` the
part of the facet other parts shade from the ram direction. ``n_O`` is
the density the run's drag used, all of it counted as atomic oxygen,
``rho / m_O``: an upper bound (decision D-08). It needs drag in the run;
without it only the sun hours are computed. Series
``<sc>.exposure.ao_flux`` [1/(cm^2 s)], one column per facet; the
fluence is its integral (:func:`totals`). The erosion depth, fluence times
the material's erosion yield, is given only for a face whose material has
a sourced yield (``config.materials``).

**Sun hours.** The equivalent sun hours (CR-189554's measure: hours of
the Sun at normal incidence and 1 AU) accumulate at
``sunlight max(0, n . s) (1 - f) (1 AU / d)^2`` per hour: series
``<sc>.exposure.sun_factor`` [-], one column per facet.
"""

from __future__ import annotations

import numpy as np

from ..constants import ASTRONOMICAL_UNIT_M, EARTH_ROTATION_RAD_S
from ..engine.results import TimeSeries

# The mass of an oxygen atom: its standard atomic weight 15.999 (CIAAW, IUPAC 2009 conventional value)
# times the dalton 1.66053906660e-27 kg (CODATA 2018).
OXYGEN_ATOM_KG = 15.999 * 1.66053906660e-27  # [kg]


def exposure_series(result, geometry, light, central_body: str) -> tuple[list, list[str]]:
    out, notes = [], []
    n = len(geometry.time_s)
    names = tuple(f.name for f in light.facets)
    density = result.series.get(f"{geometry.spacecraft}.atmosphere.density")
    velocity = result.series.get(f"{geometry.spacecraft}.velocity_N")
    if density is None or velocity is None:
        notes.append("surface exposure: no drag in the run: no atomic oxygen (sun hours only)")
    else:
        rho = np.interp(geometry.time_s, density.time_s, np.asarray(density.data, float)[:, 0])  # [kg/m^3]
        v_n = np.column_stack([np.interp(geometry.time_s, velocity.time_s, np.asarray(velocity.data, float)[:, k])
                               for k in range(3)])
        if central_body == "earth":
            omega = np.array([0.0, 0.0, EARTH_ROTATION_RAD_S])  # [rad/s] about the inertial z axis
            v_n = v_n - np.cross(omega, geometry.position_n - geometry.central_n)
        speed = np.linalg.norm(v_n, axis=1)  # [m/s]
        ram_b = geometry.to_body(v_n / speed[:, None])
        flux = np.zeros((n, len(names)))
        for i in range(n):
            flux[i] = light.light(ram_b[i]) / light.areas  # [-] cos (1 - f)
        flux *= (rho / OXYGEN_ATOM_KG * speed)[:, None] * 1e-4  # [1/(cm^2 s)]
        out.append(TimeSeries(f"{geometry.spacecraft}.exposure.ao_flux", geometry.time_s, names, flux,
                              units="1/(cm^2*s)"))
    if geometry.sun_n is None:
        notes.append("surface exposure: the run does not track the Sun: no sun hours")
        return out, notes
    sun_b, distance = geometry.unit_body(geometry.sun_n)
    factor = np.zeros((n, len(names)))
    for i in range(n):
        if geometry.sunlight[i] > 0.0:
            factor[i] = light.light(sun_b[i]) / light.areas
    factor *= (geometry.sunlight * (ASTRONOMICAL_UNIT_M / distance) ** 2)[:, None]
    out.append(TimeSeries(f"{geometry.spacecraft}.exposure.sun_factor", geometry.time_s, names, factor, units="-"))
    return out, notes


def totals(result, sc, materials_by_face=None) -> list[dict]:
    """Per facet: the atomic-oxygen fluence [1/cm^2], the equivalent sun
    hours [h] and, where the face's material has a sourced erosion yield,
    the erosion depth [um]."""
    rows = {}
    for key, name in (("ao_fluence_cm2", "ao_flux"), ("sun_hours", "sun_factor")):
        series = result.series.get(f"{sc.name}.exposure.{name}")
        if series is None:
            continue
        integral = np.trapezoid(np.asarray(series.data, float), series.time_s, axis=0)
        if key == "sun_hours":
            integral = integral / 3600.0  # [h]
        for column, value in zip(series.columns, integral):
            rows.setdefault(column, {"face": column})[key] = float(value)
    for face, row in rows.items():
        material = (materials_by_face or {}).get(face)
        if material is not None and material[1] is not None and "ao_fluence_cm2" in row:
            row["material"] = material[0]
            row["erosion_um"] = row["ao_fluence_cm2"] * material[1] * 1e4  # [cm] to [um]
    return list(rows.values())
