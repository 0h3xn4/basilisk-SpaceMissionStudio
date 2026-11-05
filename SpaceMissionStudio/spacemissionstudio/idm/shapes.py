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
"""The geometry of IDM-CIC's 3D objects, in our own parameterisation.

Each object is read into a :class:`ShapeGeometry` in the shape's own
frame: one of the 3D model's exact primitives (box, cylinder, cone,
sphere) with its pose in that frame, or a closed (solids) or open
(surfaces) triangle mesh built here, or a point when the object has no
geometry the importer models. Its volume and area give the mass of a
shape whose mass is set per cubic or square metre.

Conventions (fixed against the example models, design note section 4;
assumed where marked):

- Box, extruded triangle and quadrangle: a corner at the origin; the
  base length ``d1`` along +x, the width along +y, the thickness along
  +z. Rectangle, triangle and quadrangle surfaces the same, in z = 0.
- Cylinders, cones, paraboloids and the tank: the axis along +z, the
  base centre at the origin, the height ``d3`` (negative: along -z).
  Revolutions run from ``angle1`` to ``angle2`` [deg] about +z from +x.
- Spheres and tori: centred on the origin (assumed), in the xy plane.
- Thicknesses (``d4`` of hollow objects) are taken inward from the
  outer size (assumed); a paraboloid's vertically.
- The tank: a cylinder of radius ``d1`` from z = 0 to ``d3`` closed by
  two hemispheres beyond (assumed), its wall ``d4`` thick.
- The stretch factor ``s`` is not modelled: a value other than 1 is
  noted as an approximation.
- Topologies (Boolean operations): a union adds a body and a difference
  removes one, so the mass properties are exact when the united bodies
  do not overlap and each removed body lies inside the rest; anything
  else is noted as an approximation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..model3d.geometry import Mesh
from . import frames
from .errors import IdmError
from .values import number

#: Sides of a full revolution; a partial one gets its share (at least 8).
SEGMENTS = 64
#: Points along a sphere's or torus's profile half-circle or circle.
PROFILE_POINTS = 32

SOLIDS = ("Box", "FilledBox", "ExtrudedTriangle", "ExtrudedQuadrangle", "FilledCylinder", "HollowCylinder",
          "FilledCone", "HollowCone", "FilledSphere", "HollowSphere", "FilledTorus", "HollowTorus",
          "FilledParaboloid", "HollowParaboloid", "Tank", "Topology")
SURFACES = ("Rectangle", "Triangle", "Quadrangle", "Disc", "HollowDisc", "Cylinder", "Cone", "Sphere", "Torus",
            "Paraboloid")
WIRES = ("Line", "Arc", "Ellipse", "Curve")


@dataclass
class ShapeGeometry:
    """One 3D object in its shape's frame (module docstring).

    ``kind`` is "box", "cylinder", "cone" or "sphere" (the 3D model's
    primitives, ``dims`` their dimensions [m] and ``local`` the 4 x 4 pose
    of the primitive's own centred frame in the shape frame), "mesh"
    (``mesh`` in the shape frame) or "point" (no geometry: a point mass at
    ``centroid_m``). ``solid`` is False for a surface. ``notes`` say what
    is approximated."""

    object_type: str
    kind: str
    solid: bool
    volume_m3: float = 0.0
    area_m2: float = 0.0
    centroid_m: np.ndarray = field(default_factory=lambda: np.zeros(3))
    dims: dict = field(default_factory=dict)
    local: np.ndarray = field(default_factory=frames.identity)
    mesh: Mesh | None = None
    notes: list = field(default_factory=list)
    #: The tank's inner (propellant) cavity, for a tank: a closed mesh.
    cavity: Mesh | None = None
    cavity_volume_m3: float = 0.0
    #: A line or arc (no area or volume): noted only when it has a mass.
    wire: bool = False
    #: A cone built as a mesh: its radius at z = 0, its radius at z = h, and
    #: h [m], as the model gives them (the mesh's radii are scaled to keep
    #: each circle's area, so its angle is read from these).
    cone: tuple | None = None


def _params(node, names, where: str) -> dict:
    return {name: number(node.text(name), f"{where}.{name}", default=0.0) for name in names}


def _span(p: dict) -> tuple:
    a1 = p.get("angle1", 0.0)
    a2 = p.get("angle2", 360.0)
    if a2 <= a1:
        a2 += 360.0
    return a1, min(a2, a1 + 360.0)


def _full(a1: float, a2: float) -> bool:
    return a2 - a1 >= 360.0 - 1.0e-9


# -- meshes --------------------------------------------------------------

def _signed_volume(vertices: np.ndarray, triangles: np.ndarray) -> float:
    if len(triangles) == 0:
        return 0.0
    a, b, c = vertices[triangles[:, 0]], vertices[triangles[:, 1]], vertices[triangles[:, 2]]
    return float(np.einsum("mi,mi->m", a, np.cross(b, c)).sum() / 6.0)


def _area(vertices: np.ndarray, triangles: np.ndarray) -> float:
    if len(triangles) == 0:
        return 0.0
    a, b, c = vertices[triangles[:, 0]], vertices[triangles[:, 1]], vertices[triangles[:, 2]]
    return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())


def _outward(mesh: Mesh) -> Mesh:
    """A closed mesh wound so it encloses positive volume."""
    if _signed_volume(mesh.vertices, mesh.triangles) < 0.0:
        return Mesh(mesh.vertices, mesh.triangles[:, ::-1])
    return mesh


def _inverted(mesh: Mesh) -> Mesh:
    return Mesh(mesh.vertices, mesh.triangles[:, ::-1])


def _join(meshes) -> Mesh:
    vertices, triangles, offset = [], [], 0
    for m in meshes:
        vertices.append(m.vertices)
        triangles.append(m.triangles + offset)
        offset += len(m.vertices)
    if not vertices:
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))
    return Mesh(np.vstack(vertices), np.vstack(triangles))


def _transformed(mesh: Mesh, m: np.ndarray) -> Mesh:
    return Mesh(mesh.vertices @ m[:3, :3].T + m[:3, 3], mesh.triangles)


def _polygon_area(points) -> float:
    p = np.asarray(points, dtype=float)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def triangulate(points) -> list:
    """Triangles ``(i, j, k)`` (counter-clockwise) covering the simple
    polygon ``points`` [(u, v)] by ear clipping."""
    pts = [tuple(map(float, p)) for p in points]
    order = list(range(len(pts)))
    if _polygon_area(pts) < 0.0:
        order.reverse()

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside(p, a, b, c):
        return cross(a, b, p) >= -1e-15 and cross(b, c, p) >= -1e-15 and cross(c, a, p) >= -1e-15

    result = []
    guard = 0
    while len(order) > 3 and guard < 10 * len(pts) ** 2:
        guard += 1
        n = len(order)
        for k in range(n):
            i, j, m = order[(k - 1) % n], order[k], order[(k + 1) % n]
            a, b, c = pts[i], pts[j], pts[m]
            turn = cross(a, b, c)
            if turn <= 1e-15:
                if abs(turn) <= 1e-15 and n > 3:  # a straight corner: drop it
                    order.pop(k)
                    break
                continue
            if any(inside(pts[q], a, b, c) for q in order if q not in (i, j, m)):
                continue
            result.append((i, j, m))
            order.pop(k)
            break
        else:
            break  # no ear: not a simple polygon
    if len(order) == 3:
        i, j, m = order
        if cross(pts[i], pts[j], pts[m]) > 1e-15:
            result.append((i, j, m))
    return result


def revolve(profile, a1_deg: float, a2_deg: float, closed: bool, segments: int = SEGMENTS) -> Mesh:
    """The surface swept by ``profile`` [(r, z)] about +z from ``a1_deg``
    to ``a2_deg``. ``closed``: the profile is a closed polygon (its last
    point joins its first) and the result a closed solid, with end caps
    when the revolution is partial. The radii are scaled so each circle's
    (or arc's) polygon has the area of the true circle (or sector)."""
    full = _full(a1_deg, a2_deg)
    span = 360.0 if full else a2_deg - a1_deg
    n = max(8, int(math.ceil(segments * span / 360.0)))
    angles = np.radians(a1_deg + span * np.arange(n + (0 if full else 1)) / n)
    step = math.radians(span / n)
    k = math.sqrt(step / math.sin(step))
    profile = [(float(r), float(z)) for r, z in profile]
    on_axis = [abs(r) < 1e-12 for r, _ in profile]
    vertices, index = [], []
    for (r, z), axis in zip(profile, on_axis, strict=True):
        if axis:
            index.append([len(vertices)] * len(angles))
            vertices.append((0.0, 0.0, z))
        else:
            row = []
            for a in angles:
                row.append(len(vertices))
                vertices.append((k * r * math.cos(a), k * r * math.sin(a), z))
            index.append(row)
    triangles = []
    count = len(profile)
    edges = range(count if closed else count - 1)
    for i in edges:
        j = (i + 1) % count
        if on_axis[i] and on_axis[j]:
            continue
        for s in range(n):
            t = (s + 1) % len(angles) if full else s + 1
            a, b = index[i][s], index[j][s]
            c, d = index[j][t], index[i][t]
            if not on_axis[j]:
                triangles.append((a, b, c))
            if not on_axis[i]:
                triangles.append((a, c, d))
    if closed and not full:
        caps = triangulate(profile)
        for s, flip in ((0, True), (len(angles) - 1, False)):
            for i, j, m in caps:
                tri = (index[i][s], index[j][s], index[m][s])
                triangles.append(tri[::-1] if flip else tri)
    mesh = Mesh(np.array(vertices, dtype=float), np.array(triangles, dtype=np.int64).reshape(-1, 3))
    return _outward(mesh) if closed else mesh


def extrude(polygon, height: float) -> Mesh:
    """The prism of the polygon ``polygon`` [(x, y)] in z = 0 swept to
    z = ``height``, closed and wound outward."""
    pts = [tuple(map(float, p)) for p in polygon]
    if _polygon_area(pts) < 0.0:
        pts.reverse()
    n = len(pts)
    vertices = [(x, y, 0.0) for x, y in pts] + [(x, y, height) for x, y in pts]
    triangles = []
    for i, j, k in triangulate(pts):
        triangles.append((k, j, i))  # bottom, facing -z
        triangles.append((i + n, j + n, k + n))  # top, facing +z
    for i in range(n):
        j = (i + 1) % n
        triangles += [(i, j, j + n), (i, j + n, i + n)]
    return _outward(Mesh(np.array(vertices), np.array(triangles, dtype=np.int64)))


def flat(polygon) -> Mesh:
    """The polygon ``polygon`` [(x, y)] in z = 0, as a surface."""
    pts = [tuple(map(float, p)) for p in polygon]
    vertices = [(x, y, 0.0) for x, y in pts]
    return Mesh(np.array(vertices), np.array(triangulate(pts), dtype=np.int64).reshape(-1, 3))


def _arc(r: float, z0: float, start: float, stop: float, points: int = PROFILE_POINTS):
    """Points (r sin t, z0 - r cos t) for t from start to stop [rad]: a
    half circle from the bottom pole (t = 0) to the top (t = pi)."""
    return [(r * math.sin(t), z0 - r * math.cos(t)) for t in np.linspace(start, stop, points + 1)]


def _circle(center_r: float, radius: float, points: int = PROFILE_POINTS * 2):
    return [(center_r + radius * math.cos(t), radius * math.sin(t))
            for t in np.linspace(0.0, 2.0 * math.pi, points, endpoint=False)]


def _parabola(radius: float, height: float, offset: float = 0.0, points: int = PROFILE_POINTS):
    return [(radius * u, height * u * u + offset) for u in np.linspace(0.0, 1.0, points + 1)]


def _triangle(d1: float, d2: float, angle1_deg: float):
    a = math.radians(angle1_deg)
    return [(0.0, 0.0), (d1, 0.0), (d2 * math.cos(a), d2 * math.sin(a))]


def _quadrangle(d1: float, d2: float, d3: float, angle1_deg: float, angle2_deg: float):
    a1, a2 = math.radians(angle1_deg), math.radians(angle2_deg)
    return [(0.0, 0.0), (d1, 0.0), (d1 - d3 * math.cos(a2), d3 * math.sin(a2)), (d2 * math.cos(a1), d2 * math.sin(a1))]


def _capsule(radius: float, length: float):
    """A closed profile: hemisphere below z = 0, cylinder to ``length``,
    hemisphere above."""
    lower = _arc(radius, 0.0, 0.0, math.pi / 2.0)
    upper = [(r, z + length) for r, z in _arc(radius, 0.0, math.pi / 2.0, math.pi)]
    return lower + upper[1:]


def _with_hole(outer, inner):
    """A closed C-shaped profile between two profiles that both run from
    the axis to the axis (outer counter-clockwise, inner reversed)."""
    return list(outer) + list(reversed(inner))


# -- the objects -----------------------------------------------------------

def _mesh_geometry(object_type: str, mesh: Mesh, solid: bool, notes: list) -> ShapeGeometry:
    volume = _signed_volume(mesh.vertices, mesh.triangles) if solid else 0.0
    area = _area(mesh.vertices, mesh.triangles)
    if solid and volume > 0.0:
        a, b, c = mesh.vertices[mesh.triangles[:, 0]], mesh.vertices[mesh.triangles[:, 1]], \
            mesh.vertices[mesh.triangles[:, 2]]
        vols = np.einsum("mi,mi->m", a, np.cross(b, c)) / 6.0
        centroid = (vols[:, None] * (a + b + c)).sum(axis=0) / 4.0 / volume
    elif len(mesh.vertices):
        centroid = mesh.vertices.mean(axis=0)
    else:
        centroid = np.zeros(3)
    return ShapeGeometry(object_type, "mesh", solid, volume, area, centroid, mesh=mesh, notes=notes)


def _centred(m_translation) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = m_translation
    return m


def _stretch_note(p: dict, notes: list) -> None:
    if "s" in p and abs(p["s"] - 1.0) > 1e-12 and p["s"] != 0.0:
        notes.append(f"stretch factor s = {p['s']:g} not modelled")


def _as_cone(shape: ShapeGeometry, r0: float, r1: float, h: float) -> ShapeGeometry:
    if shape.mesh is not None:
        shape.cone = (r0, r1, h)
    return shape


def geometry(node, where: str = "", as_mesh: bool = False) -> ShapeGeometry:
    """The :class:`ShapeGeometry` of an object (``shapeDefinition``'s
    child node). ``as_mesh`` builds a mesh even for the exact primitives
    (Boolean operations need one)."""
    t = node.tag
    where = where or node.full_id or t
    p = _params(node, ("d1", "d2", "d3", "d4", "angle1", "angle2", "s", "r"), where)
    if "angle2" not in node.values:
        p["angle2"] = 360.0 if t not in ("ExtrudedTriangle", "ExtrudedQuadrangle", "Triangle", "Quadrangle") \
            else p["angle2"]
    if "s" not in node.values:
        p["s"] = 1.0
    d1, d2, d3, d4 = p["d1"], p["d2"], p["d3"], p["d4"]
    notes: list = []
    _stretch_note(p, notes)
    a1, a2 = _span(p)
    full = _full(a1, a2)

    if t in ("Box", "FilledBox"):
        if p.get("r", 0.0) > 0.0:
            notes.append(f"rounded edges (r = {p['r']:g} m) not modelled")
        size = [abs(d1), abs(d2), abs(d3)]
        center = [d1 / 2.0, d2 / 2.0, d3 / 2.0]
        if min(size) <= 0.0:
            if sorted(size)[1] <= 0.0:
                return _point(t, center, ["a box with less than two non-zero sides has no geometry"])
            k = size.index(0.0)
            u, v = [i for i in range(3) if i != k]
            corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
            vertices = []
            for cu, cv in corners:
                point = [0.0, 0.0, 0.0]
                point[u], point[v] = cu * (d1, d2, d3)[u], cv * (d1, d2, d3)[v]
                vertices.append(point)
            mesh = Mesh(np.array(vertices), np.array([(0, 1, 2), (0, 2, 3)]))
            return _mesh_geometry(t, mesh, False, notes + ["a box with a zero side: taken as a flat plate"])
        if as_mesh:
            mesh = extrude([(0, 0), (d1, 0), (d1, d2), (0, d2)], d3)
            return _mesh_geometry(t, mesh, True, notes)
        return ShapeGeometry(t, "box", True, size[0] * size[1] * size[2],
                             2.0 * (size[0] * size[1] + size[1] * size[2] + size[0] * size[2]),
                             np.array(center), {"x": size[0], "y": size[1], "z": size[2]}, _centred(center),
                             notes=notes)
    if t == "ExtrudedTriangle":
        return _mesh_geometry(t, extrude(_triangle(d1, d2, p["angle1"]), d3), True,
                              notes + ["extruded triangle: corner convention assumed"])
    if t == "ExtrudedQuadrangle":
        return _mesh_geometry(t, extrude(_quadrangle(d1, d2, d3, p["angle1"], p["angle2"]), d4), True,
                              notes + ["extruded quadrangle: corner convention assumed"])
    if t == "Rectangle":
        return _mesh_geometry(t, flat([(0, 0), (d1, 0), (d1, d2), (0, d2)]), False, notes)
    if t == "Triangle":
        return _mesh_geometry(t, flat(_triangle(d1, d2, p["angle1"])), False,
                              notes + ["triangle: corner convention assumed"])
    if t == "Quadrangle":
        return _mesh_geometry(t, flat(_quadrangle(d1, d2, d3, p["angle1"], p["angle2"])), False,
                              notes + ["quadrangle: corner convention assumed"])

    if t == "FilledCylinder":
        if d1 <= 0.0 or d3 == 0.0:
            return _point(t, [0, 0, d3 / 2.0], ["a cylinder without radius or height has no geometry"])
        if full and not as_mesh:
            return ShapeGeometry(t, "cylinder", True, math.pi * d1 * d1 * abs(d3),
                                 2.0 * math.pi * d1 * (d1 + abs(d3)), np.array([0.0, 0.0, d3 / 2.0]),
                                 {"diameter": 2.0 * d1, "height": abs(d3)}, _centred([0.0, 0.0, d3 / 2.0]),
                                 notes=notes)
        return _mesh_geometry(t, revolve([(0, 0), (d1, 0), (d1, d3), (0, d3)], a1, a2, True), True, notes)
    if t == "HollowCylinder":
        inner = max(0.0, d1 - d4)
        return _mesh_geometry(t, revolve([(inner, 0), (d1, 0), (d1, d3), (inner, d3)], a1, a2, True), True, notes)
    if t == "FilledCone":
        if d3 == 0.0 or (d1 <= 0.0 and d2 <= 0.0):
            return _point(t, [0, 0, d3 / 2.0], ["a cone without radius or height has no geometry"])
        if full and not as_mesh and (d1 <= 0.0 or d2 <= 0.0):
            base = d1 if d2 <= 0.0 else d2
            # The model's cone has its base at -z of its centred frame: turn it over when the base is at +z.
            base_at_top = (d2 > 0.0) != (d3 < 0.0)
            local = _centred([0.0, 0.0, d3 / 2.0])
            if base_at_top:
                local[:3, :3] = frames.axis_rotation("X", 180.0)
            h = abs(d3)
            return ShapeGeometry(t, "cone", True, math.pi * base * base * h / 3.0,
                                 math.pi * base * (base + math.hypot(base, h)),
                                 local[:3, 3] + local[:3, :3] @ np.array([0.0, 0.0, -h / 4.0]),
                                 {"base_diameter": 2.0 * base, "height": h}, local, notes=notes)
        return _as_cone(_mesh_geometry(t, revolve([(0, 0), (d1, 0), (d2, d3), (0, d3)], a1, a2, True), True,
                                       notes), d1, d2, d3)
    if t == "HollowCone":
        profile = [(max(0.0, d1 - d4), 0), (d1, 0), (d2, d3), (max(0.0, d2 - d4), d3)]
        return _as_cone(_mesh_geometry(t, revolve(profile, a1, a2, True), True, notes), d1, d2, d3)
    if t == "FilledSphere":
        if d1 <= 0.0:
            return _point(t, [0, 0, 0], ["a sphere without radius has no geometry"])
        if full and not as_mesh:
            return ShapeGeometry(t, "sphere", True, 4.0 / 3.0 * math.pi * d1 ** 3, 4.0 * math.pi * d1 * d1,
                                 np.zeros(3), {"diameter": 2.0 * d1}, frames.identity(), notes=notes)
        return _mesh_geometry(t, revolve(_arc(d1, 0.0, 0.0, math.pi), a1, a2, True), True, notes)
    if t == "HollowSphere":
        inner = max(0.0, d1 - d4)
        profile = _arc(d1, 0.0, 0.0, math.pi) if inner <= 0.0 else \
            _with_hole(_arc(d1, 0.0, 0.0, math.pi), _arc(inner, 0.0, 0.0, math.pi))
        return _mesh_geometry(t, revolve(profile, a1, a2, True), True, notes)
    if t in ("FilledTorus", "HollowTorus"):
        if d2 <= 0.0 or d1 < d2:
            return _point(t, [0, 0, 0], ["a torus whose tube reaches the axis is not modelled"])
        outer = revolve(_circle(d1, d2), a1, a2, True)
        if t == "HollowTorus" and d2 - d4 > 0.0:
            outer = _join([outer, _inverted(revolve(_circle(d1, d2 - d4), a1, a2, True))])
        return _mesh_geometry(t, outer, True, notes)
    if t == "FilledParaboloid":
        profile = _parabola(d1, d3) + [(0.0, d3)]
        return _mesh_geometry(t, revolve(profile, a1, a2, True), True, notes)
    if t == "HollowParaboloid":
        thickness = d4 if d3 >= 0.0 else -d4
        profile = _parabola(d1, d3) + list(reversed(_parabola(d1, d3, thickness)))
        return _mesh_geometry(t, revolve(profile, a1, a2, True), True,
                              notes + ["paraboloid thickness taken along the axis"])
    if t == "Tank":
        if d1 <= 0.0:
            return _point(t, [0, 0, d3 / 2.0], ["a tank without radius has no geometry"])
        length = max(0.0, d3)
        inner = max(0.0, d1 - d4)
        outer_profile = _capsule(d1, length)
        wall_profile = _with_hole(outer_profile, _capsule(inner, length)) if inner > 0.0 else outer_profile
        wall = _mesh_geometry(t, revolve(wall_profile, 0.0, 360.0, True), True, notes)
        if inner > 0.0:
            wall.cavity = revolve(_capsule(inner, length), 0.0, 360.0, True)
            wall.cavity_volume_m3 = _signed_volume(wall.cavity.vertices, wall.cavity.triangles)
        return wall

    if t == "Disc":
        return _mesh_geometry(t, revolve([(0.0, 0.0), (d1, 0.0)], a1, a2, False), False, notes)
    if t == "HollowDisc":
        return _mesh_geometry(t, revolve([(max(0.0, d1 - d4), 0.0), (d1, 0.0)], a1, a2, False), False, notes)
    if t == "Cylinder":
        return _mesh_geometry(t, revolve([(d1, 0.0), (d1, d3)], a1, a2, False), False, notes)
    if t == "Cone":
        return _as_cone(_mesh_geometry(t, revolve([(d1, 0.0), (d2, d3)], a1, a2, False), False, notes), d1, d2, d3)
    if t == "Sphere":
        return _mesh_geometry(t, revolve(_arc(d1, 0.0, 0.0, math.pi), a1, a2, False), False, notes)
    if t == "Torus":
        circle = _circle(d1, d2)
        return _mesh_geometry(t, revolve(circle + circle[:1], a1, a2, False), False, notes)
    if t == "Paraboloid":
        return _mesh_geometry(t, revolve(_parabola(d1, d3), a1, a2, False), False, notes)

    if t == "Line":
        return _point(t, [d1 / 2.0, d2 / 2.0, d3 / 2.0], ["lines are wires: the mass is placed at the line's midpoint"],
                      wire=True)
    if t in WIRES:
        return _point(t, [0.0, 0.0, 0.0], [f"{t.lower()}s are wires: the mass is placed at the shape's origin"],
                      wire=True)
    if t == "Topology":
        return _topology(node, where)
    return _point(t, [0.0, 0.0, 0.0], [f"{t} objects are not modelled: the mass is placed at the shape's origin"])


def _point(object_type: str, centroid, notes: list, wire: bool = False) -> ShapeGeometry:
    return ShapeGeometry(object_type, "point", False, 0.0, 0.0, np.asarray(centroid, dtype=float), notes=notes,
                         wire=wire)


def _position(node, where: str) -> np.ndarray:
    """The 4 x 4 transform of a ``Position`` node (identity when absent)."""
    if node is None:
        return frames.identity()
    return frames.pose([number(node.text(axis), f"{where}.{axis}", default=0.0) for axis in "xyz"],
                       node.text("rotationOrder") or "Rx_Ry_Rz",
                       [number(node.text(f"rotation{k}"), f"{where}.rotation{k}", default=0.0) for k in (1, 2, 3)],
                       node.text("transformationOrder") or "Translation_Rotation")


position_transform = _position


def _topology(node, where: str) -> ShapeGeometry:
    pieces, notes = [], ["Boolean operations: united bodies taken as not overlapping, removed bodies as inside"]
    for k, op in enumerate(node.many("topologicalOperations")):
        kind = (op.text("operationType") or "").strip()
        if op.tag != "BooleanOperation" or kind not in ("Union", "Difference"):
            what = kind or op.tag
            return _point("Topology", _first_centroid(pieces),
                          [f"the Boolean operation {what} is not modelled: the mass is placed at the shape's origin"
                           if not pieces else f"the Boolean operation {what} is not modelled: the mass is placed at "
                           "the centroid of the bodies before it"])
        objects = [child for children in op.objects.values() for child in children if child.tag != "Position"]
        target = op.one("object3d") or (objects[0] if objects else None)
        if target is None:
            raise IdmError(f"{where}: Boolean operation {k + 1} has no object")
        g = geometry(target, f"{where}.operation{k + 1}", as_mesh=True)
        if g.kind != "mesh" or not g.solid:
            return _point("Topology", _first_centroid(pieces),
                          [f"a Boolean operation on a {target.tag} is not modelled: the mass is placed at the "
                           "shape's origin"])
        notes += [note for note in g.notes if note not in notes]
        mesh = _transformed(g.mesh, _position(op.one("position"), f"{where}.operation{k + 1}.position"))
        pieces.append(mesh if kind == "Union" else _inverted(mesh))
    if not pieces:
        return _point("Topology", [0.0, 0.0, 0.0], ["an empty Boolean operation"])
    mesh = _join(pieces)
    g = _mesh_geometry("Topology", mesh, True, notes)
    if g.volume_m3 <= 0.0:
        return _point("Topology", [0.0, 0.0, 0.0], ["the Boolean operations leave no volume"])
    return g


def _first_centroid(pieces) -> np.ndarray:
    if not pieces:
        return np.zeros(3)
    g = _mesh_geometry("Topology", _join(pieces), True, [])
    return g.centroid_m if g.volume_m3 > 0.0 else np.zeros(3)
