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

"""Mass, center of mass and inertia.

:class:`MassProperties` holds the inertia about the body's own center of
mass. Bodies are combined with the parallel-axis theorem
(:func:`combine`); a body is turned and moved with :func:`placed`.

For a mesh the integrals are exact, not sampled:

- a **solid** (mass spread through the volume) sums the signed tetrahedra
  each triangle forms with the origin; this needs a closed, outward-wound
  surface (:meth:`.geometry.Mesh.is_closed`);
- a **shell** (mass spread over the surface) sums the triangles.

Both use the same closed form: the second moment ``integral(x x^T)`` of a
tetrahedron with one corner at the origin and corners ``a, b, c`` is
``V/20 (a a^T + b b^T + c c^T + s s^T)`` with ``s = a + b + c``; that of a
triangle of area ``A`` is ``A/12`` times the same sum.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Iterable

import numpy as np

from .geometry import Mesh, triangle_areas_and_normals


class MassPropertiesError(ValueError):
    """Mass properties that cannot be computed, with the reason."""


@dataclass
class MassProperties:
    """``mass_kg`` [kg], ``center_of_mass_m`` (3,) [m] and ``inertia_kg_m2``
    (3, 3) [kg*m^2] about that center of mass, in one frame's axes."""

    mass_kg: float
    center_of_mass_m: np.ndarray
    inertia_kg_m2: np.ndarray

    def __post_init__(self) -> None:
        self.center_of_mass_m = np.asarray(self.center_of_mass_m, dtype=float).reshape(3)
        self.inertia_kg_m2 = np.asarray(self.inertia_kg_m2, dtype=float).reshape(3, 3)

    def inertia_about(self, point_m) -> np.ndarray:
        """The inertia about ``point_m`` instead of the center of mass
        (parallel-axis theorem), same axes."""
        d = self.center_of_mass_m - np.asarray(point_m, dtype=float)
        return self.inertia_kg_m2 + self.mass_kg * (np.dot(d, d) * np.eye(3) - np.outer(d, d))

    def principal(self) -> tuple[np.ndarray, np.ndarray]:
        """``(moments (3,), axes (3, 3))``: the principal moments in
        ascending order and, as columns, their unit axes."""
        moments, axes = np.linalg.eigh(0.5 * (self.inertia_kg_m2 + self.inertia_kg_m2.T))
        return moments, axes


def zero() -> MassProperties:
    """No mass."""
    return MassProperties(0.0, np.zeros(3), np.zeros((3, 3)))


def placed(local: MassProperties, rotation: np.ndarray, position_m) -> MassProperties:
    """``local`` (in a part's own frame) expressed in the body frame, for a
    part placed at ``R @ x_local + position``."""
    r = np.asarray(rotation, dtype=float)
    return MassProperties(local.mass_kg, r @ local.center_of_mass_m + np.asarray(position_m, dtype=float),
                          r @ local.inertia_kg_m2 @ r.T)


def combine(bodies: Iterable[MassProperties]) -> MassProperties:
    """One body made of ``bodies`` (all in the same frame)."""
    bodies = [b for b in bodies if b.mass_kg > 0.0]
    total = sum(b.mass_kg for b in bodies)
    if total <= 0.0:
        return zero()
    center = sum(b.mass_kg * b.center_of_mass_m for b in bodies) / total
    inertia = sum((b.inertia_about(center) for b in bodies), np.zeros((3, 3)))
    return MassProperties(total, center, inertia)


def _second_moment_sum(a, b, c) -> np.ndarray:
    """Per element, ``a a^T + b b^T + c c^T + s s^T`` with ``s = a + b + c``:
    shape (M, 3, 3)."""
    s = a + b + c
    return (np.einsum("mi,mj->mij", a, a) + np.einsum("mi,mj->mij", b, b)
            + np.einsum("mi,mj->mij", c, c) + np.einsum("mi,mj->mij", s, s))


def _from_moments(mass_kg: float, measure: float, first: np.ndarray, second: np.ndarray) -> MassProperties:
    """Mass properties from the zeroth (``measure``: volume or area), first
    and second moments of a uniform distribution of ``mass_kg``."""
    density = mass_kg / measure
    center = first / measure
    inertia_origin = density * (np.trace(second) * np.eye(3) - second)
    inertia_center = inertia_origin - mass_kg * (np.dot(center, center) * np.eye(3) - np.outer(center, center))
    return MassProperties(mass_kg, center, inertia_center)


def solid_mesh(mesh: Mesh, mass_kg: float) -> MassProperties:
    """``mass_kg`` spread uniformly through the volume a closed mesh
    encloses. Raises :class:`MassPropertiesError` when the mesh is not
    closed or encloses no volume."""
    if not mesh.is_closed():
        raise MassPropertiesError("the surface is not closed, so it encloses no definite volume; "
                                  "use the 'shell' mass distribution instead")
    a, b, c = mesh.corners()
    volumes = np.einsum("mi,mi->m", a, np.cross(b, c)) / 6.0
    volume = float(volumes.sum())
    if volume < 0.0:  # wound inside out: same integrals with the sign flipped
        volumes = -volumes
        volume = -volume
    if volume <= 0.0:
        raise MassPropertiesError("the surface encloses no volume")
    first = (volumes[:, None] * (a + b + c)).sum(axis=0) / 4.0
    second = (volumes[:, None, None] * _second_moment_sum(a, b, c)).sum(axis=0) / 20.0
    return _from_moments(mass_kg, volume, first, second)


def shell_mesh(mesh: Mesh, mass_kg: float) -> MassProperties:
    """``mass_kg`` spread uniformly over a mesh's surface (open or closed)."""
    areas, _, centroids = triangle_areas_and_normals(mesh)
    area = float(areas.sum())
    if area <= 0.0:
        raise MassPropertiesError("the surface has no area")
    a, b, c = mesh.corners()
    first = (areas[:, None] * centroids).sum(axis=0)
    second = (areas[:, None, None] * _second_moment_sum(a, b, c)).sum(axis=0) / 12.0
    return _from_moments(mass_kg, area, first, second)


# Curved shapes: closed forms (a faceted mesh would only approximate them).
# Local frames: axis along z, the bounding box centred on the origin.

def cylinder(mass_kg: float, radius_m: float, height_m: float, shell: bool) -> MassProperties:
    """A cylinder along z, centred; solid, or a shell of side wall and both
    end caps (mass shared by area)."""
    r, h = radius_m, height_m
    if not shell:
        axial = 0.5 * mass_kg * r * r
        transverse = mass_kg * (3.0 * r * r + h * h) / 12.0
        return MassProperties(mass_kg, np.zeros(3), np.diag([transverse, transverse, axial]))
    side_area = 2.0 * math.pi * r * h
    cap_area = math.pi * r * r
    m_side = mass_kg * side_area / (side_area + 2.0 * cap_area)
    m_cap = mass_kg * cap_area / (side_area + 2.0 * cap_area)
    axial = m_side * r * r + 2.0 * (0.5 * m_cap * r * r)
    transverse = m_side * (0.5 * r * r + h * h / 12.0) + 2.0 * (0.25 * m_cap * r * r + m_cap * (0.5 * h) ** 2)
    return MassProperties(mass_kg, np.zeros(3), np.diag([transverse, transverse, axial]))


def cone(mass_kg: float, radius_m: float, height_m: float, shell: bool) -> MassProperties:
    """A cone along z with its base at ``z = -h/2`` and apex at ``+h/2``;
    solid, or a shell of side surface and base disk (mass shared by area)."""
    r, h = radius_m, height_m
    base_z = -0.5 * h
    if not shell:
        center_z = base_z + 0.25 * h
        axial = 0.3 * mass_kg * r * r
        transverse = mass_kg * (3.0 * r * r / 20.0 + 3.0 * h * h / 80.0)
        return MassProperties(mass_kg, [0.0, 0.0, center_z], np.diag([transverse, transverse, axial]))
    slant = math.hypot(r, h)
    side_area = math.pi * r * slant
    base_area = math.pi * r * r
    m_side = mass_kg * side_area / (side_area + base_area)
    m_base = mass_kg * base_area / (side_area + base_area)
    side = MassProperties(m_side, [0.0, 0.0, base_z + h / 3.0],
                          np.diag([m_side * (0.25 * r * r + h * h / 18.0)] * 2 + [0.5 * m_side * r * r]))
    base = MassProperties(m_base, [0.0, 0.0, base_z], np.diag([0.25 * m_base * r * r] * 2 + [0.5 * m_base * r * r]))
    return combine([side, base])


def sphere(mass_kg: float, radius_m: float, shell: bool) -> MassProperties:
    """A sphere, centred; solid (2/5 m r^2) or a thin shell (2/3 m r^2)."""
    moment = (2.0 / 3.0 if shell else 0.4) * mass_kg * radius_m * radius_m
    return MassProperties(mass_kg, np.zeros(3), moment * np.eye(3))
