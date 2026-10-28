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
"""A small body's shape model as a closed polyhedron (numpy only, no
Basilisk).

The run's gravity is Basilisk's ``polyhedralGravityModel``; this module
reads the same shape file for what the tool does with the shape itself:
whether a point is inside the body (an impact), the body's volume and
centroid, surface points for landmarks, and an independent constant-density
polyhedron field (Werner and Scheeres 1997, *Celestial Mechanics and
Dynamical Astronomy* 65, 313-344) that the tests compare with Basilisk's.

Positions are in the body-fixed frame, in metres; facets list their three
vertices counter-clockwise seen from outside (outward normals).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_FOUR_PI = 4.0 * np.pi  # [-] solid angle of a closed surface seen from inside


class ShapeError(ValueError):
    """The shape file could not be read or is not a closed polyhedron."""


@dataclass
class Polyhedron:
    """Vertices [m] and facets (zero-based vertex indices)."""

    vertices: np.ndarray  # (n, 3) [m]
    facets: np.ndarray  # (m, 3) int
    _edges: tuple[np.ndarray, ...] = field(default=(), init=False, repr=False)

    @property
    def volume(self) -> float:
        """[m^3] from the signed tetrahedra on the origin."""
        a, b, c = (self.vertices[self.facets[:, k]] for k in range(3))
        return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)

    @property
    def centroid(self) -> np.ndarray:
        """[m] centre of volume (the centre of mass at constant density)."""
        a, b, c = (self.vertices[self.facets[:, k]] for k in range(3))
        six_v = np.einsum("ij,ij->i", a, np.cross(b, c))
        return (six_v[:, None] * (a + b + c)).sum(axis=0) / (4.0 * six_v.sum())

    @property
    def facet_centers(self) -> np.ndarray:
        """[m] (m, 3)"""
        return self.vertices[self.facets].mean(axis=1)

    @property
    def facet_normals(self) -> np.ndarray:
        """(m, 3) outward unit normals."""
        a, b, c = (self.vertices[self.facets[:, k]] for k in range(3))
        n = np.cross(b - a, c - a)
        return n / np.linalg.norm(n, axis=1, keepdims=True)

    @property
    def facet_areas(self) -> np.ndarray:
        """[m^2] (m,)"""
        a, b, c = (self.vertices[self.facets[:, k]] for k in range(3))
        return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)

    def solid_angles(self, point: np.ndarray) -> np.ndarray:
        """Signed solid angle [sr] of each facet seen from ``point`` [m]
        (Van Oosterom and Strackee 1983)."""
        r1, r2, r3 = (self.vertices[self.facets[:, k]] - np.asarray(point, float) for k in range(3))
        n1, n2, n3 = (np.linalg.norm(r, axis=1) for r in (r1, r2, r3))
        numerator = np.einsum("ij,ij->i", r1, np.cross(r2, r3))
        denominator = (n1 * n2 * n3 + n1 * np.einsum("ij,ij->i", r2, r3) + n2 * np.einsum("ij,ij->i", r3, r1)
                       + n3 * np.einsum("ij,ij->i", r1, r2))
        return 2.0 * np.arctan2(numerator, denominator)

    def contains(self, points: np.ndarray, chunk: int = 256) -> np.ndarray:
        """True for each point [m] inside the body: the facets' solid
        angles add up to 4 pi inside and to 0 outside."""
        points = np.atleast_2d(np.asarray(points, float))
        inside = np.zeros(len(points), dtype=bool)
        a, b, c = (self.vertices[self.facets[:, k]] for k in range(3))
        for start in range(0, len(points), chunk):
            p = points[start:start + chunk, None, :]
            r1, r2, r3 = a[None] - p, b[None] - p, c[None] - p
            n1, n2, n3 = (np.linalg.norm(r, axis=2) for r in (r1, r2, r3))
            numerator = np.einsum("pij,pij->pi", r1, np.cross(r2, r3))
            denominator = (n1 * n2 * n3 + n1 * np.einsum("pij,pij->pi", r2, r3)
                           + n2 * np.einsum("pij,pij->pi", r3, r1) + n3 * np.einsum("pij,pij->pi", r1, r2))
            total = 2.0 * np.arctan2(numerator, denominator).sum(axis=1)
            inside[start:start + chunk] = total > 0.5 * _FOUR_PI
        return inside

    def _edge_data(self):
        """Each undirected edge once: its two vertices and the dyad
        E = n_A n_A^e + n_B n_B^e (Werner and Scheeres eq. 11)."""
        if self._edges:
            return self._edges
        normals = self.facet_normals
        starts = self.facets.reshape(-1)
        ends = np.roll(self.facets, -1, axis=1).reshape(-1)
        owner = np.repeat(np.arange(len(self.facets)), 3)
        direction = self.vertices[ends] - self.vertices[starts]
        edge_normal = np.cross(direction, normals[owner])
        edge_normal /= np.linalg.norm(edge_normal, axis=1, keepdims=True)
        dyads = np.einsum("ij,ik->ijk", normals[owner], edge_normal)
        key = np.sort(np.stack([starts, ends], axis=1), axis=1)
        unique, inverse, counts = np.unique(key, axis=0, return_inverse=True, return_counts=True)
        if np.any(counts != 2):
            raise ShapeError("the shape is not closed: an edge does not belong to exactly two facets")
        summed = np.zeros((len(unique), 3, 3))
        np.add.at(summed, inverse.reshape(-1), dyads)
        self._edges = (unique[:, 0], unique[:, 1], summed)
        return self._edges

    def field(self, point: np.ndarray, mu: float) -> tuple[float, np.ndarray]:
        """Potential [m^2/s^2] (positive, mu/r far away) and acceleration
        [m/s^2] at ``point`` [m] of the body with gravitational parameter
        ``mu`` [m^3/s^2] at constant density (Werner and Scheeres 1997,
        eqs. 15 and 16)."""
        potential, acceleration, _ = self._evaluate(point, mu, gradient=False)
        return potential, acceleration

    def field_and_gradient(self, point: np.ndarray, mu: float) -> tuple[np.ndarray, np.ndarray]:
        """Acceleration [m/s^2] and its gradient d a / d r [1/s^2] (Werner
        and Scheeres 1997, eq. 17) at ``point`` [m]."""
        _, acceleration, gradient = self._evaluate(point, mu, gradient=True)
        return acceleration, gradient

    def _evaluate(self, point, mu: float, gradient: bool):
        p = np.asarray(point, float)
        g_rho = mu / self.volume  # [1/s^2] G times the density
        i_start, i_end, dyads = self._edge_data()
        ra, rb = self.vertices[i_start] - p, self.vertices[i_end] - p
        a, b = np.linalg.norm(ra, axis=1), np.linalg.norm(rb, axis=1)
        e = np.linalg.norm(self.vertices[i_end] - self.vertices[i_start], axis=1)
        wire = np.log((a + b + e) / (a + b - e))
        er = np.einsum("ijk,ik->ij", dyads, ra)
        normals = self.facet_normals
        rf = self.vertices[self.facets[:, 0]] - p
        omega = self.solid_angles(p)
        fr = normals * np.einsum("ij,ij->i", normals, rf)[:, None]
        potential = 0.5 * g_rho * (np.einsum("ij,ij,i->", ra, er, wire) - np.einsum("ij,ij,i->", rf, fr, omega))
        acceleration = -g_rho * (er * wire[:, None]).sum(axis=0) + g_rho * (fr * omega[:, None]).sum(axis=0)
        tensor = None
        if gradient:
            facet_dyads = np.einsum("ij,ik->ijk", normals, normals)
            tensor = g_rho * (np.einsum("ijk,i->jk", dyads, wire) - np.einsum("ijk,i->jk", facet_dyads, omega))
        return float(potential), acceleration, tensor


def load(path) -> Polyhedron:
    """Read a ``.tab`` shape: PDS3 ``v x y z`` / ``f i j k`` rows (km,
    zero-based) as in Basilisk's ``eros007790.tab``, or Gaskell's
    ``nVertex nFacet`` header and numbered rows (km, one-based)."""
    path = Path(path)
    try:
        lines = path.read_text(encoding="ascii").split("\n")
    except (OSError, UnicodeDecodeError) as exc:
        raise ShapeError(f"could not read the shape file {path.name}: {exc}") from exc
    vertices, facets = [], []
    try:
        head = lines[0].split()
        if len(head) == 2 and all(part.isdigit() for part in head):
            n_vertex, n_facet = int(head[0]), int(head[1])
            rows = [line.split() for line in lines[1:] if line.strip()]
            vertices = [[float(x) for x in row[1:4]] for row in rows[:n_vertex]]
            facets = [[int(x) - 1 for x in row[1:4]] for row in rows[n_vertex:n_vertex + n_facet]]
        else:
            for line in lines:
                parts = line.split()
                if parts and parts[0] == "v":
                    vertices.append([float(x) for x in parts[1:4]])
                elif parts and parts[0] == "f":
                    facets.append([int(x) for x in parts[1:4]])
    except (ValueError, IndexError) as exc:
        raise ShapeError(f"{path.name} is not a shape file this tool reads: {exc}") from exc
    if len(vertices) < 4 or len(facets) < 4:
        raise ShapeError(f"{path.name} has no closed shape ({len(vertices)} vertices, {len(facets)} facets)")
    shape = Polyhedron(np.asarray(vertices) * 1e3, np.asarray(facets, dtype=int))  # [km] -> [m]
    if shape.facets.min() < 0 or shape.facets.max() >= len(shape.vertices):
        raise ShapeError(f"{path.name}: a facet names a vertex the file does not have")
    if shape.volume <= 0.0:
        raise ShapeError(f"{path.name}: the facets do not face outwards")
    return shape
