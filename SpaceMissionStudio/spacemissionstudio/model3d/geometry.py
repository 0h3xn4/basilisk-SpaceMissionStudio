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

"""Triangle meshes and part placement.

A part is placed in the body frame by a rotation and an offset: a point
``x_local`` of the part is at ``R @ x_local + position`` in the body frame.
``R`` comes from ``rotation_deg = [roll, pitch, yaw]``: the part's axes are
the body axes turned by yaw about z, then pitch about the new y, then roll
about the new x (a 3-2-1 sequence), so ``R = Rz(yaw) @ Ry(pitch) @ Rx(roll)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np


@dataclass
class Mesh:
    """Triangles: ``vertices`` (N, 3) [m] and ``triangles`` (M, 3) vertex
    indices, wound counter-clockwise seen from outside (outward normals)."""

    vertices: np.ndarray
    triangles: np.ndarray

    def __post_init__(self) -> None:
        self.vertices = np.asarray(self.vertices, dtype=float).reshape(-1, 3)
        self.triangles = np.asarray(self.triangles, dtype=np.int64).reshape(-1, 3)

    def corners(self):
        """The three corner arrays ``(a, b, c)``, each (M, 3)."""
        v = self.vertices
        t = self.triangles
        return v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]

    def transformed(self, rotation: np.ndarray, position: Sequence[float],
                    scale: Sequence[float] | None = None) -> Mesh:
        """This mesh scaled (per axis, in its own frame), rotated and moved.
        A mirroring scale (negative determinant) reverses the winding so the
        normals still point outward."""
        vertices = self.vertices
        triangles = self.triangles
        if scale is not None:
            factors = np.asarray(scale, dtype=float)
            vertices = vertices * factors
            if np.prod(factors) < 0.0:
                triangles = triangles[:, ::-1]
        vertices = vertices @ np.asarray(rotation, dtype=float).T + np.asarray(position, dtype=float)
        return Mesh(vertices, triangles.copy())

    def welded(self, tolerance_m: float = 1.0e-7) -> Mesh:
        """This mesh with vertices closer than ``tolerance_m`` merged, and
        triangles that collapse to a line or point dropped. Exporters often
        repeat a corner once per face (for per-face normals or texture
        seams); welding makes such a surface closed again."""
        if len(self.vertices) == 0:
            return Mesh(self.vertices.copy(), self.triangles.copy())
        keys = np.round(self.vertices / tolerance_m).astype(np.int64)
        _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
        inverse = inverse.reshape(-1)
        triangles = inverse[self.triangles]
        keep = ((triangles[:, 0] != triangles[:, 1]) & (triangles[:, 1] != triangles[:, 2])
                & (triangles[:, 0] != triangles[:, 2]))
        return Mesh(self.vertices[first], triangles[keep])

    def is_closed(self) -> bool:
        """True when every edge is shared by exactly two triangles that run
        along it in opposite directions: a watertight, consistently wound
        surface, which a solid's volume integrals need."""
        if len(self.triangles) == 0:
            return False
        t = self.triangles
        n = np.int64(max(len(self.vertices), int(t.max()) + 1))
        directed = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
        forward = directed[:, 0] * n + directed[:, 1]
        if len(np.unique(forward)) != len(forward):
            return False  # an edge used twice in the same direction
        return bool(np.isin(directed[:, 1] * n + directed[:, 0], forward).all())

    def bounds(self):
        """``(min_xyz, max_xyz)`` of the vertices."""
        return self.vertices.min(axis=0), self.vertices.max(axis=0)


def rotation_matrix(rotation_deg: Sequence[float]) -> np.ndarray:
    """``R = Rz(yaw) @ Ry(pitch) @ Rx(roll)`` for ``[roll, pitch, yaw]`` in
    degrees (see the module docstring)."""
    roll, pitch, yaw = np.radians(np.asarray(rotation_deg, dtype=float))
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    return rz @ ry @ rx


def triangle_areas_and_normals(mesh: Mesh):
    """``(areas (M,), unit_normals (M, 3), centroids (M, 3))``. A degenerate
    triangle has area 0 and normal [0, 0, 0]."""
    a, b, c = mesh.corners()
    cross = np.cross(b - a, c - a)
    norm = np.linalg.norm(cross, axis=1)
    areas = 0.5 * norm
    with np.errstate(invalid="ignore", divide="ignore"):
        normals = np.where(norm[:, None] > 0.0, cross / norm[:, None], 0.0)
    return areas, normals, (a + b + c) / 3.0


def merge(meshes: Sequence[Mesh]) -> Mesh:
    """One mesh holding all of ``meshes``."""
    vertices = []
    triangles = []
    offset = 0
    for mesh in meshes:
        vertices.append(mesh.vertices)
        triangles.append(mesh.triangles + offset)
        offset += len(mesh.vertices)
    if not vertices:
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))
    return Mesh(np.concatenate(vertices), np.concatenate(triangles))
