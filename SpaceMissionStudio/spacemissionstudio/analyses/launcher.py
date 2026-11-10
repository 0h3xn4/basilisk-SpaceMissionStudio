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
"""Launcher compatibility: the stowed spacecraft against the launcher's
envelope, and its mass and centre of mass against the limits.

The envelope (``model.launcher``) stands on the separation plane through
``origin_b_m``, with its axis along ``axis_b``: a point is at height ``h``
above the plane and distance ``rho`` from the axis. A cylinder allows
``0 <= h <= H`` and ``rho <= D / 2``; a box ``|u| <= W / 2``,
``|v| <= Dp / 2`` (``u`` along ``width_axis_b``); a profile the radius
interpolated linearly between its points. Every vertex of every part in
the stowed configuration is measured (the deployed one when the model has
no stowed poses); curved parts are drawn with :data:`CHECK_SEGMENTS` sides
for this check, whose vertices lie on the true surface, so the largest
protrusion can be under-read by at most ``r (1 - cos(pi / n))`` for a
radius ``r``, which the report gives. A protrusion is the largest distance
a part's vertices lie outside the envelope.

Stiffness and fundamental-frequency requirements need a structural model
and are not checked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..config import envelopes as library
from ..model3d import model as model3d
from ..model3d import shapes
from ..model3d.geometry import rotation_matrix
from . import common

CHECK_SEGMENTS = 128  # [-] sides of curved parts for the envelope check


@dataclass
class Protrusion:
    part: str
    distance_m: float  # [m] outside the envelope
    where: str  # "radius", "top", "below the separation plane", "width", "depth"


@dataclass
class LauncherCheck:
    spacecraft: str
    envelope: str  # its name, or "custom"
    source: str
    configuration: str
    protrusions: list = field(default_factory=list)  # list[Protrusion], parts outside only
    largest_faceting_error_m: float = 0.0  # [m]
    mass_kg: float | None = None  # [kg] the launch mass checked
    mass_limit_kg: float | None = None
    com_height_m: float | None = None  # [m] above the separation plane
    com_height_limit_m: float | None = None
    com_lateral_m: float | None = None  # [m] from the axis
    com_lateral_limit_m: float | None = None
    notes: list = field(default_factory=list)
    out_of_scope: str = "Stiffness and fundamental frequencies need a structural model: not checked."

    @property
    def fits(self) -> bool:
        return not self.protrusions

    def limit_problems(self) -> list[str]:
        problems = []
        for label, value, limit, unit in (("mass", self.mass_kg, self.mass_limit_kg, "kg"),
                                          ("centre-of-mass height", self.com_height_m, self.com_height_limit_m, "m"),
                                          ("centre-of-mass lateral offset", self.com_lateral_m,
                                           self.com_lateral_limit_m, "m")):
            if value is not None and limit is not None and value > limit:
                problems.append(f"{label} {value:.4g} {unit} is over its limit {limit:.4g} {unit}")
        return problems


def _envelope(config):
    """The envelope's shape and dimensions, from the library or the config."""
    if config.envelope != "custom":
        entry = library.ENVELOPES[config.envelope]
        return entry.name, entry.source, entry.shape, entry.diameter_m, entry.height_m, entry.width_m, \
            entry.depth_m, [list(p) for p in entry.profile], entry
    return "custom", config.source, config.shape, config.diameter_m, config.height_m, config.width_m, \
        config.depth_m, config.profile, None


def _part_vertices(part, position, rotation_deg, derived_mesh):
    """A part's vertices in the body frame, curved shapes finely drawn."""
    if part.shape == "mesh":
        return derived_mesh.vertices
    dims = {k: float(v) for k, v in part.dimensions_m.items()}
    local = shapes.mesh(part.shape, dims, sides=part.sides, segments=CHECK_SEGMENTS)
    return local.vertices @ rotation_matrix(rotation_deg).T + np.asarray(position, dtype=float)


def _outside(h, u, v, rho, shape, dims, profile):
    """Per vertex, ``(distance outside, where)``."""
    diameter, height, width, depth = dims
    rows = [(-h, "below the separation plane")]
    if shape in ("cylinder", "box"):
        rows.append((h - height, "top"))
    if shape == "cylinder":
        rows.append((rho - 0.5 * diameter, "radius"))
    elif shape == "box":
        rows += [(np.abs(u) - 0.5 * width, "width"), (np.abs(v) - 0.5 * depth, "depth")]
    else:
        heights = np.array([p[0] for p in profile])
        radii = np.array([p[1] for p in profile])
        allowed = np.interp(h, heights, radii)
        rows.append((np.where((h >= heights[0]) & (h <= heights[-1]), rho - allowed,
                              np.maximum(heights[0] - h, h - heights[-1])), "radius"))
        rows.append((h - heights[-1], "top"))
    distances = np.column_stack([r[0] for r in rows])
    worst = np.argmax(distances, axis=1)
    return distances[np.arange(len(h)), worst], [rows[k][1] for k in worst]


def launcher_check(sc, base_dir=None) -> LauncherCheck | None:
    """:class:`LauncherCheck` of spacecraft ``sc``, or None when its model
    has no launcher set."""
    if sc.model is None or sc.model.launcher is None:
        return None
    config = sc.model.launcher
    name, source, shape, diameter, height, width, depth, profile, entry = _envelope(config)
    configuration = "stowed" if sc.model.stowed else "deployed"
    result = LauncherCheck(sc.name, name, source, configuration)
    if configuration == "deployed":
        result.notes.append("the model has no stowed configuration: the deployed one is checked")
    derived, _scene = common.derived_and_scene(sc, configuration, base_dir)
    meshes = {p.name: p.mesh for p in derived.parts if p.mesh is not None}
    poses = model3d.poses(sc.model, configuration)
    axis = np.asarray(config.axis_b, dtype=float)
    axis /= np.linalg.norm(axis)
    width_axis = np.asarray(config.width_axis_b, dtype=float)
    width_axis = width_axis - axis * float(width_axis @ axis)
    if np.linalg.norm(width_axis) < 1e-9:
        width_axis = np.cross(axis, [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0])
    width_axis /= np.linalg.norm(width_axis)
    depth_axis = np.cross(axis, width_axis)
    origin = np.asarray(config.origin_b_m, dtype=float)
    for part in sc.model.parts:
        if part.name not in meshes:
            continue
        position, rotation_deg = poses.get(part.name, (part.position_b_m, part.rotation_deg))
        vertices = _part_vertices(part, position, rotation_deg, meshes[part.name])
        rel = vertices - origin
        h, u, v = rel @ axis, rel @ width_axis, rel @ depth_axis
        rho = np.hypot(u, v)
        distance, where = _outside(h, u, v, rho, shape, (diameter, height, width, depth), profile)
        k = int(np.argmax(distance))
        if distance[k] > 0.0:
            result.protrusions.append(Protrusion(part.name, float(distance[k]), where[k]))
        if part.shape in ("cylinder", "cone", "sphere"):
            radius = 0.5 * float(part.dimensions_m.get("diameter", part.dimensions_m.get("base_diameter", 0.0)))
            result.largest_faceting_error_m = max(result.largest_faceting_error_m,
                                                  radius * (1.0 - math.cos(math.pi / CHECK_SEGMENTS)))
    result.protrusions.sort(key=lambda p: -p.distance_m)
    # Mass and centre of mass: the stowed configuration's computed properties, with propellant.
    props = derived.computed if derived.computed.mass_kg > 0.0 else None
    if props is not None:
        from .mass_budget import mass_budget

        result.mass_kg = float(props.mass_kg) + mass_budget(sc).propellant_kg
        com = np.asarray(props.center_of_mass_m, dtype=float) - origin
        result.com_height_m = float(com @ axis)
        result.com_lateral_m = float(np.linalg.norm(com - axis * (com @ axis)))
        result.notes.append("mass and centre of mass: the stowed parts' computed properties, plus the propellant "
                            "(placed at the dry centre of mass)")
    limits = entry if entry is not None else config
    result.mass_limit_kg = config.mass_limit_kg if config.mass_limit_kg is not None else limits.mass_limit_kg
    result.com_height_limit_m = (config.com_height_limit_m if config.com_height_limit_m is not None
                                 else limits.com_height_limit_m)
    result.com_lateral_limit_m = (config.com_lateral_limit_m if config.com_lateral_limit_m is not None
                                  else limits.com_lateral_limit_m)
    return result
