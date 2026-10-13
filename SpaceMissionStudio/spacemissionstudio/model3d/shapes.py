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

"""The simple shapes a model is built from, each in its own local frame
with its bounding box centred on the origin:

========== ==================================== ===============================
Shape      Dimensions [m]                       Local frame
========== ==================================== ===============================
box        ``x``, ``y``, ``z``                  edges along the axes
prism      ``width_across_flats``, ``height``;  regular n-gon along z; the
           ``sides`` (8: an octagon)            first flat faces +x
cylinder   ``diameter``, ``height``             axis along z
cone       ``base_diameter``, ``height``        base at -z, apex at +z
sphere     ``diameter``
panel      ``width``, ``length``, ``thickness`` width along x, length along y,
                                                faces +z and -z
========== ==================================== ===============================

Each shape gives a closed triangle mesh (what is drawn and exported), its
outer :class:`Face` list (what drag and solar pressure act on) and its mass
properties. Curved shapes are drawn with ``segments`` flat sides, but their
mass properties are the exact curved ones, and their faces carry the true
curved area: ``segments`` side faces of a cylinder share its side area,
so the area they show along any direction across the axis tends to the
true ``diameter * height``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from ..schema.scenario import MODEL_SHAPE_DIMENSIONS, MODEL_SHAPE_FACES, MODEL_SHAPES
from . import mass_properties as mp
from .geometry import Mesh

# The shape names, their dimensions and their face names are the schema's
# (no numpy there), so validation and geometry cannot disagree.
SHAPES = tuple(s for s in MODEL_SHAPES if s != "mesh")
DIMENSIONS: Dict[str, Tuple[str, ...]] = MODEL_SHAPE_DIMENSIONS
FACE_NAMES: Dict[str, Tuple[str, ...]] = MODEL_SHAPE_FACES

DEFAULT_SIDES = 8
DEFAULT_SEGMENTS = 16


@dataclass
class Face:
    """One flat outer face: ``area_m2`` [m^2], outward unit ``normal``,
    ``centroid_m`` [m] (where its force acts) and ``group`` (the name used
    to leave it out, see ``FACE_NAMES``)."""

    name: str
    group: str
    area_m2: float
    normal: np.ndarray
    centroid_m: np.ndarray


def _box_mesh(x: float, y: float, z: float) -> Mesh:
    hx, hy, hz = 0.5 * x, 0.5 * y, 0.5 * z
    vertices = [[sx * hx, sy * hy, sz * hz] for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    # Corner index = (sx > 0) + 2 (sy > 0) + 4 (sz > 0); quads wound outward.
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    triangles = [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]
    return Mesh(vertices, triangles)


def _prism_mesh(radius: float, height: float, sides: int, phase: float) -> Mesh:
    """A closed prism along z on a regular polygon of circumradius
    ``radius``, its first corner at angle ``phase``."""
    angles = phase + 2.0 * math.pi * np.arange(sides) / sides
    ring = np.stack([radius * np.cos(angles), radius * np.sin(angles)], axis=1)
    hz = 0.5 * height
    bottom = np.column_stack([ring, np.full(sides, -hz)])
    top = np.column_stack([ring, np.full(sides, hz)])
    vertices = np.concatenate([bottom, top, [[0.0, 0.0, -hz], [0.0, 0.0, hz]]])
    bottom_center, top_center = 2 * sides, 2 * sides + 1
    triangles = []
    for i in range(sides):
        j = (i + 1) % sides
        triangles += [(i, j, sides + j), (i, sides + j, sides + i)]  # side quad, outward
        triangles.append((bottom_center, j, i))  # bottom cap, facing -z
        triangles.append((top_center, sides + i, sides + j))  # top cap, facing +z
    return Mesh(vertices, triangles)


def _cone_mesh(radius: float, height: float, segments: int) -> Mesh:
    angles = 2.0 * math.pi * np.arange(segments) / segments
    hz = 0.5 * height
    ring = np.column_stack([radius * np.cos(angles), radius * np.sin(angles), np.full(segments, -hz)])
    vertices = np.concatenate([ring, [[0.0, 0.0, -hz], [0.0, 0.0, hz]]])
    base_center, apex = segments, segments + 1
    triangles = []
    for i in range(segments):
        j = (i + 1) % segments
        triangles.append((i, j, apex))
        triangles.append((base_center, j, i))
    return Mesh(vertices, triangles)


def _sphere_mesh(radius: float, segments: int) -> Mesh:
    """A latitude-longitude sphere: ``segments`` around, ``segments // 2``
    from pole to pole."""
    around = max(segments, 4)
    rings = max(segments // 2, 2)
    vertices = [[0.0, 0.0, -radius]]
    for k in range(1, rings):
        polar = math.pi * k / rings  # from the south pole
        z = -radius * math.cos(polar)
        rho = radius * math.sin(polar)
        for i in range(around):
            phi = 2.0 * math.pi * i / around
            vertices.append([rho * math.cos(phi), rho * math.sin(phi), z])
    vertices.append([0.0, 0.0, radius])
    north = len(vertices) - 1
    triangles = []

    def ring_index(k: int, i: int) -> int:
        return 1 + (k - 1) * around + (i % around)

    for i in range(around):
        triangles.append((0, ring_index(1, i + 1), ring_index(1, i)))
        triangles.append((north, ring_index(rings - 1, i), ring_index(rings - 1, i + 1)))
    for k in range(1, rings - 1):
        for i in range(around):
            a, b = ring_index(k, i), ring_index(k, i + 1)
            c, d = ring_index(k + 1, i + 1), ring_index(k + 1, i)
            triangles += [(a, b, c), (a, c, d)]
    return Mesh(vertices, triangles)


def _fibonacci_directions(count: int) -> np.ndarray:
    """``count`` unit vectors spread evenly over the sphere."""
    k = np.arange(count) + 0.5
    z = 1.0 - 2.0 * k / count
    phi = math.pi * (3.0 - math.sqrt(5.0)) * k
    rho = np.sqrt(1.0 - z * z)
    return np.column_stack([rho * np.cos(phi), rho * np.sin(phi), z])


def _face(name: str, group: str, area: float, normal, centroid) -> Face:
    return Face(name, group, float(area), np.asarray(normal, dtype=float), np.asarray(centroid, dtype=float))


def mesh(shape: str, dims: Dict[str, float], sides: int = DEFAULT_SIDES,
         segments: int = DEFAULT_SEGMENTS) -> Mesh:
    """The closed local-frame triangle mesh of a shape."""
    if shape == "box":
        return _box_mesh(dims["x"], dims["y"], dims["z"])
    if shape == "panel":
        return _box_mesh(dims["width"], dims["length"], dims["thickness"])
    if shape == "prism":
        apothem = 0.5 * dims["width_across_flats"]
        return _prism_mesh(apothem / math.cos(math.pi / sides), dims["height"], sides, math.pi / sides)
    if shape == "cylinder":
        return _prism_mesh(0.5 * dims["diameter"], dims["height"], segments, 0.0)
    if shape == "cone":
        return _cone_mesh(0.5 * dims["base_diameter"], dims["height"], segments)
    if shape == "sphere":
        return _sphere_mesh(0.5 * dims["diameter"], segments)
    raise ValueError(f"unknown shape {shape!r}")


def faces(shape: str, dims: Dict[str, float], sides: int = DEFAULT_SIDES,
          segments: int = DEFAULT_SEGMENTS) -> List[Face]:
    """The local-frame outer faces of a shape (see the module docstring)."""
    if shape == "box":
        x, y, z = dims["x"], dims["y"], dims["z"]
        return [_face("+x", "+x", y * z, [1, 0, 0], [x / 2, 0, 0]), _face("-x", "-x", y * z, [-1, 0, 0], [-x / 2, 0, 0]),
                _face("+y", "+y", x * z, [0, 1, 0], [0, y / 2, 0]), _face("-y", "-y", x * z, [0, -1, 0], [0, -y / 2, 0]),
                _face("+z", "+z", x * y, [0, 0, 1], [0, 0, z / 2]), _face("-z", "-z", x * y, [0, 0, -1], [0, 0, -z / 2])]
    if shape == "panel":
        area = dims["width"] * dims["length"]
        half = 0.5 * dims["thickness"]
        return [_face("+z", "+z", area, [0, 0, 1], [0, 0, half]), _face("-z", "-z", area, [0, 0, -1], [0, 0, -half])]
    if shape in ("prism", "cylinder"):
        h = dims["height"]
        if shape == "prism":
            count = sides
            apothem = 0.5 * dims["width_across_flats"]
            cap_area = count * apothem * apothem * math.tan(math.pi / count)
            side_area = 2.0 * apothem * math.tan(math.pi / count) * h
            centroid_radius = apothem
        else:
            count = segments
            radius = 0.5 * dims["diameter"]
            cap_area = math.pi * radius * radius
            side_area = 2.0 * math.pi * radius * h / count  # the true curved area, shared
            centroid_radius = radius
        result = [_face("+z", "+z", cap_area, [0, 0, 1], [0, 0, h / 2]),
                  _face("-z", "-z", cap_area, [0, 0, -1], [0, 0, -h / 2])]
        for k in range(count):
            angle = 2.0 * math.pi * k / count
            normal = [math.cos(angle), math.sin(angle), 0.0]
            result.append(_face(f"side {k + 1}", "sides", side_area, normal,
                                [centroid_radius * normal[0], centroid_radius * normal[1], 0.0]))
        return result
    if shape == "cone":
        r, h = 0.5 * dims["base_diameter"], dims["height"]
        slant = math.hypot(r, h)
        result = [_face("-z", "-z", math.pi * r * r, [0, 0, -1], [0, 0, -h / 2])]
        for k in range(segments):
            angle = 2.0 * math.pi * k / segments
            normal = [h * math.cos(angle) / slant, h * math.sin(angle) / slant, r / slant]
            centroid = [2.0 * r / 3.0 * math.cos(angle), 2.0 * r / 3.0 * math.sin(angle), -h / 2 + h / 3]
            result.append(_face(f"side {k + 1}", "sides", math.pi * r * slant / segments, normal, centroid))
        return result
    if shape == "sphere":
        r = 0.5 * dims["diameter"]
        count = max(2 * segments, 8)
        area = 4.0 * math.pi * r * r / count
        return [_face(f"face {k + 1}", "sphere", area, n, r * n) for k, n in enumerate(_fibonacci_directions(count))]
    raise ValueError(f"unknown shape {shape!r}")


def mass_properties(shape: str, dims: Dict[str, float], mass_kg: float, shell: bool,
                    sides: int = DEFAULT_SIDES) -> mp.MassProperties:
    """Local-frame mass properties of ``mass_kg`` spread through the shape
    (``shell`` False) or over its surface (True). Flat-sided shapes use the
    exact mesh integrals; curved ones the closed forms."""
    if shape == "cylinder":
        return mp.cylinder(mass_kg, 0.5 * dims["diameter"], dims["height"], shell)
    if shape == "cone":
        return mp.cone(mass_kg, 0.5 * dims["base_diameter"], dims["height"], shell)
    if shape == "sphere":
        return mp.sphere(mass_kg, 0.5 * dims["diameter"], shell)
    local_mesh = mesh(shape, dims, sides=sides)
    return mp.shell_mesh(local_mesh, mass_kg) if shell else mp.solid_mesh(local_mesh, mass_kg)
