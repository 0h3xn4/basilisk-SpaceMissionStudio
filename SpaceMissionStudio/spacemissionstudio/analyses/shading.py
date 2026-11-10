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
"""Light on the model's faces over a run (model analyses): array shading
with its power, shared by ``exposure`` and ``brightness``.

The faces are the model's facets (``model3d.model.derive``, the deployed
configuration): one per flat face, one per curved strip or mesh plane
group, with the face properties applied. For a direction in the body
frame, a facet's light is ``A max(0, n . s) (1 - f)``, ``f`` the part of
it other parts block (``Scene.face_shading``, ray-sampled with its
standard error). The shading is cached per direction to within
:data:`DIRECTION_STEP`, so a Sun-pointing spacecraft costs one ray cast
for the Sun.

**Array shading.** Each mounted ``solar_cell`` item is the facet of its
part whose normal is nearest its boresight. Its series
``<sc>.shading.<item>`` holds the shaded fraction and the incidence
cosine. When the spacecraft has a power budget (its cells' efficiency),
``<sc>.shading.power`` holds each cell's power
``S A eta cos(theta) (1 - f) sunlight`` [W], ``S`` the solar flux at the
run's Sun distance, and the totals unshaded and shaded. It is reported beside the power budget (decision D-09).
"""

from __future__ import annotations

import numpy as np

from ..constants import ASTRONOMICAL_UNIT_M, SOLAR_FLUX_1AU_W_M2
from ..engine.results import TimeSeries

DIRECTION_STEP = 1.0e-3  # [rad] about: directions closer than this share their shading


class FacetLight:
    """The shading of a model's facets from directions in the body frame,
    cached."""

    def __init__(self, scene, facets, samples: int):
        self.scene, self.facets, self.samples = scene, facets, samples
        self.normals = np.array([np.asarray(f.normal_b, float) / np.linalg.norm(f.normal_b) for f in facets])
        self.areas = np.array([f.area_m2 for f in facets], dtype=float)
        self._cache: dict = {}

    def shaded(self, direction_b: np.ndarray, which=None) -> np.ndarray:
        """The shaded fraction of each facet in ``which`` (default all) lit
        from ``direction_b`` (0 for a facet facing away)."""
        which = range(len(self.facets)) if which is None else which
        key = tuple(np.round(np.asarray(direction_b) / DIRECTION_STEP).astype(int))
        found = self._cache.setdefault(key, {})
        out = np.zeros(len(which))
        for i, k in enumerate(which):
            if k not in found:
                if self.normals[k] @ direction_b <= 0.0:
                    found[k] = 0.0
                else:
                    part, face = self.facets[k].name.split(": ", 1)
                    found[k] = self.scene.face_shading(part, face, direction_b, self.samples).shaded_fraction
            out[i] = found[k]
        return out

    def light(self, direction_b: np.ndarray, which=None) -> np.ndarray:
        """``A max(0, n . s) (1 - f)`` [m^2] of each facet in ``which``."""
        which = list(range(len(self.facets))) if which is None else list(which)
        cosines = np.clip(self.normals[which] @ direction_b, 0.0, None)
        return self.areas[which] * cosines * (1.0 - self.shaded(direction_b, which))


def facet_light(sc, base_dir, samples):
    """A :class:`FacetLight` of ``sc``'s deployed model."""
    from . import common

    derived, scene = common.derived_and_scene(sc, "deployed", base_dir)
    return FacetLight(scene, list(derived.facets), samples)


def solar_flux(geometry) -> np.ndarray:
    """[W/m^2] at the spacecraft, from the run's Sun distance."""
    distance = np.linalg.norm(geometry.sun_n - geometry.position_n, axis=1)
    return SOLAR_FLUX_1AU_W_M2 * (ASTRONOMICAL_UNIT_M / distance) ** 2


def shading_series(geometry, light: FacetLight, items, efficiency) -> tuple[list, list[str]]:
    """``(series, notes)`` of the mounted solar-cell ``items``."""
    out, notes = [], []
    cells = [item for item in items if item.kind == "solar_cell" and item.boresight_b is not None]
    if not cells:
        return out, ["array shading: no mounted solar_cell item"]
    if geometry.sun_n is None:
        return out, ["array shading: the run does not track the Sun"]
    names = [f.name for f in light.facets]
    sun_b, _distance = geometry.unit_body(geometry.sun_n)
    flux = solar_flux(geometry) * geometry.sunlight
    n = len(geometry.time_s)
    power_columns, power_labels = [], []
    unshaded_total = np.zeros(n)
    for item in cells:
        own = [k for k, name in enumerate(names) if name.startswith(f"{item.part}: ")]
        if not own:
            notes.append(f"array shading: {item.name}: its part {item.part!r} has no face")
            continue
        k = own[int(np.argmax(light.normals[own] @ np.asarray(item.boresight_b, float)))]
        shaded = np.array([light.shaded(sun_b[i], [k])[0] if flux[i] > 0.0 else 0.0 for i in range(n)])  # no rays in umbra
        cosine = np.clip(sun_b @ light.normals[k], 0.0, None)
        out.append(TimeSeries(f"{geometry.spacecraft}.shading.{item.name}", geometry.time_s,
                              ("shaded_fraction", "incidence_cos"), np.column_stack([shaded, cosine]), units="-"))
        if efficiency is not None:
            unshaded = flux * light.areas[k] * efficiency * cosine  # [W]
            unshaded_total += unshaded
            power_columns.append(unshaded * (1.0 - shaded))
            power_labels.append(item.name)
    if efficiency is None:
        notes.append("array shading: no power budget (cell efficiency): the power is not computed")
    elif power_columns:
        shaded_total = np.sum(power_columns, axis=0)
        out.append(TimeSeries(f"{geometry.spacecraft}.shading.power", geometry.time_s,
                              (*power_labels, "total_unshaded", "total_shaded"),
                              np.column_stack([*power_columns, unshaded_total, shaded_total]), units="W"))
    return out, notes
