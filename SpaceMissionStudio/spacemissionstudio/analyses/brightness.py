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
"""The spacecraft's visual magnitude seen from the ground (model analyses).

From each ground station and observer site, while the observer is in
darkness (the Sun at least the depression angle below its horizon,
parameter ``analyses.observer_sun_depression_deg``, decision D-17), the
spacecraft is lit and above the site's minimum elevation, the light the
facets reflect diffusely (Lambert) toward the observer is

``ratio = sum rho_d A cos(theta_s) cos(theta_o) (1 - f_s)(1 - f_o) / (pi d^2)``

of the sunlight at the spacecraft, over the facets facing both the Sun
and the observer, ``rho_d`` each facet's diffuse coefficient, ``f_s`` and
``f_o`` the parts of it other parts shade from each direction (taken as
independent), ``d`` the range. The magnitude is
``m = m_sun - 2.5 log10(ratio (1 AU / d_sun)^2)``, ``m_sun = -26.74``
(the Sun's apparent V magnitude, Hostetler and Cowardin, NASA NTRS
20190033905). No specular term (decision D-10). The vertical is the
geocentric one.

Series ``<site>.brightness_of_<sc>.visual_magnitude`` (NaN when not
visible), from which the Timeline's visible intervals come.
"""

from __future__ import annotations

import math

import numpy as np

from ..constants import ASTRONOMICAL_UNIT_M
from ..engine.results import TimeSeries

SUN_MAGNITUDE = -26.74  # [mag] apparent V magnitude of the Sun (Hostetler and Cowardin, NTRS 20190033905)


def brightness_series(result, geometry, light, sites, depression_deg: float) -> tuple[list, list[str]]:
    """``(series, notes)``: one per site in ``sites`` ((name, min elevation
    [deg])) whose position the run recorded."""
    out, notes = [], []
    if geometry.sun_n is None:
        return out, ["brightness: the run does not track the Sun"]
    diffuse = np.array([f.diffuse_coeff for f in light.facets], dtype=float)
    sun_b, sun_distance = geometry.unit_body(geometry.sun_n)
    sun_from_centre = geometry.sun_n - geometry.central_n
    for name, min_elevation_deg in sites:
        where = result.series.get(f"{name}.station.position_N")
        if where is None:
            notes.append(f"brightness: no position recorded for {name}")
            continue
        site_n = np.column_stack([np.interp(geometry.time_s, where.time_s, np.asarray(where.data, float)[:, k])
                                  for k in range(3)])
        up = site_n - geometry.central_n
        up /= np.linalg.norm(up, axis=1)[:, None]
        to_sc = geometry.position_n - site_n
        rng = np.linalg.norm(to_sc, axis=1)  # [m]
        elevation = np.arcsin(np.clip(np.einsum("ij,ij->i", to_sc / rng[:, None], up), -1.0, 1.0))
        to_sun = sun_from_centre - (site_n - geometry.central_n)
        sun_elevation = np.arcsin(np.clip(np.einsum("ij,ij->i", to_sun / np.linalg.norm(to_sun, axis=1)[:, None],
                                                    up), -1.0, 1.0))
        visible = ((sun_elevation < -math.radians(depression_deg)) & (geometry.sunlight > 0.0)
                   & (elevation >= math.radians(min_elevation_deg)))
        magnitude = np.full(len(geometry.time_s), np.nan)
        observer_b = geometry.to_body(-to_sc / rng[:, None])
        for i in np.flatnonzero(visible):
            s, o = sun_b[i], observer_b[i]
            both = np.flatnonzero((light.normals @ s > 0.0) & (light.normals @ o > 0.0))
            if not len(both):
                continue
            lit = light.light(s, both)  # A cos_s (1 - f_s)
            seen = np.clip(light.normals[both] @ o, 0.0, None) * (1.0 - light.shaded(o, both))
            ratio = float(np.sum(diffuse[both] * lit * seen)) / (math.pi * rng[i] ** 2)
            ratio *= geometry.sunlight[i] * (ASTRONOMICAL_UNIT_M / sun_distance[i]) ** 2
            if ratio > 0.0:
                magnitude[i] = SUN_MAGNITUDE - 2.5 * math.log10(ratio)
        out.append(TimeSeries(f"{name}.brightness_of_{geometry.spacecraft}.visual_magnitude", geometry.time_s,
                              ("visual_magnitude",), magnitude, units="mag"))
    return out, notes


def lambert_sphere_magnitude(diameter_m: float, albedo: float, range_m: float, phase_rad: float) -> float:
    """A Lambertian sphere's magnitude (the validation case): its
    reflected flux is ``albedo pi (D/2)^2 f(p) / d^2`` of the sunlight, with
    ``f(p) = (2 / (3 pi^2)) [sin p + (pi - p) cos p]`` (Hostetler and
    Cowardin, NTRS 20190033905, Eq. 10, after Barker et al., AMOS 2004)."""
    phase_function = 2.0 / (3.0 * math.pi ** 2) * (math.sin(phase_rad) + (math.pi - phase_rad) * math.cos(phase_rad))
    ratio = albedo * math.pi * (diameter_m / 2.0) ** 2 * phase_function / range_m ** 2
    return SUN_MAGNITUDE - 2.5 * math.log10(ratio)
