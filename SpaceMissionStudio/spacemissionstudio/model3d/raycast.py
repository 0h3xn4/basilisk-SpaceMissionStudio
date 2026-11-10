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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Rays against a spacecraft's 3D model, in the body frame: the geometry
the analyses built on the model share (field-of-view obstruction, plume
impingement, shading, exposure, brightness).

A :class:`Scene` holds the parts of a model in one configuration (deployed
or stowed). Rays meet the parts' true surfaces:

- **the simple shapes exactly** (decision D-06): a box, panel, prism,
  cylinder, cone or sphere is a convex solid. A ray meets it in one
  interval of its length, found from the distances where it crosses the
  shape's boundary surfaces (planes and quadrics, in the part's own frame)
  and a test of which of the pieces between them lie inside;
- **imported meshes by their triangles** (Möller–Trumbore), through a
  bounding-volume hierarchy built per mesh.

Every query is vectorised over rays: ``(N, 3)`` origins and directions in,
one value per ray out. A ray that starts inside a simple shape is blocked
by it at distance 0 (a ray inside a mesh part meets its far side), except
for the parts it is told to ignore (the part a sensor is mounted on, the
part a sampled face belongs to).

The queries on top -- :meth:`Scene.cone_blockage` and
:meth:`Scene.face_shading` -- sample directions or points, and report the
binomial standard error of the fraction they find, ``sqrt(p (1 - p) / n)``
for ``n`` samples. Faces are sampled on their true (curved) surfaces, with
the names :func:`.shapes.faces` gives them.

Pure numpy, Basilisk-free and GUI-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import shapes
from .geometry import Mesh, rotation_matrix

# A ray's own start is not a hit: distances below this (relative to the
# model's size) are ignored, so a ray leaving a surface does not hit it.
_EPSILON_RELATIVE = 1.0e-9  # [-] of the scene's size
_LEAF_TRIANGLES = 8  # [-] triangles per leaf of a mesh's hierarchy


@dataclass
class ScenePart:
    """One part placed in the scene: ``rotation`` and ``position`` map its
    local frame to the body frame (``x_B = R x_local + p``)."""

    name: str
    shape: str  # one of shapes.SHAPES, or "mesh"
    dims: dict
    rotation: np.ndarray
    position: np.ndarray
    sides: int = shapes.DEFAULT_SIDES
    segments: int = shapes.DEFAULT_SEGMENTS
    mesh: Mesh | None = None  # mesh parts: the body-frame triangles
    bounds_min: np.ndarray = field(default_factory=lambda: np.zeros(3))
    bounds_max: np.ndarray = field(default_factory=lambda: np.zeros(3))
    _bvh: object = None


def _local_bounds(part: ScenePart) -> tuple[np.ndarray, np.ndarray]:
    """The part's corners of its local bounding box."""
    d = part.dims
    if part.shape == "box":
        half = 0.5 * np.array([d["x"], d["y"], d["z"]])
    elif part.shape == "panel":
        half = 0.5 * np.array([d["width"], d["length"], d["thickness"]])
    elif part.shape == "prism":
        radius = 0.5 * d["width_across_flats"] / math.cos(math.pi / part.sides)
        half = np.array([radius, radius, 0.5 * d["height"]])
    elif part.shape in ("cylinder", "cone"):
        radius = 0.5 * (d["diameter"] if part.shape == "cylinder" else d["base_diameter"])
        half = np.array([radius, radius, 0.5 * d["height"]])
    elif part.shape == "sphere":
        half = np.full(3, 0.5 * d["diameter"])
    else:
        raise ValueError(f"unknown shape {part.shape!r}")
    return -half, half


def _place_bounds(part: ScenePart) -> None:
    if part.shape == "mesh":
        part.bounds_min, part.bounds_max = part.mesh.bounds()
        return
    low, high = _local_bounds(part)
    corners = np.array([[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])])
    placed = corners @ part.rotation.T + part.position
    part.bounds_min, part.bounds_max = placed.min(axis=0), placed.max(axis=0)


def _box_entry(origins, directions, low, high):
    """Slab test against axis-aligned boxes: ``(t_enter, t_exit)`` per ray,
    ``t_enter > t_exit`` for a miss. ``low``/``high`` broadcast."""
    with np.errstate(divide="ignore", invalid="ignore"):
        inverse = 1.0 / directions
        t1 = (low - origins) * inverse
        t2 = (high - origins) * inverse
    # A direction component of zero: inside the slab, any t; outside, none.
    zero = directions == 0.0
    inside = (origins >= low) & (origins <= high)
    t1 = np.where(zero, np.where(inside, -np.inf, np.inf), t1)
    t2 = np.where(zero, np.where(inside, np.inf, -np.inf), t2)
    near = np.minimum(t1, t2).max(axis=-1)
    far = np.maximum(t1, t2).min(axis=-1)
    return near, far


# -- the simple shapes ---------------------------------------------------------------------------------------------

def _planes(part: ScenePart):
    """``(normals (k, 3), offsets (k,))`` of a flat-sided shape: inside is
    ``n . x <= c`` for every plane."""
    d = part.dims
    if part.shape in ("box", "panel"):
        hx, hy, hz = (0.5 * d["x"], 0.5 * d["y"], 0.5 * d["z"]) if part.shape == "box" else (
            0.5 * d["width"], 0.5 * d["length"], 0.5 * d["thickness"])
        normals = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=float)
        return normals, np.array([hx, hx, hy, hy, hz, hz])
    if part.shape == "prism":
        n = part.sides
        apothem = 0.5 * d["width_across_flats"]
        angles = 2.0 * math.pi * np.arange(n) / n  # the first flat faces +x (shapes.faces)
        normals = np.column_stack([np.cos(angles), np.sin(angles), np.zeros(n)])
        normals = np.vstack([normals, [[0, 0, 1], [0, 0, -1]]])
        return normals, np.concatenate([np.full(n, apothem), [0.5 * d["height"]] * 2])
    raise ValueError(part.shape)


def _convex_planes_interval(o, d, normals, offsets):
    """Kay–Kajiya clipping of rays against ``n . x <= c``: ``(t_enter,
    t_exit)``."""
    denominators = d @ normals.T  # (N, k)
    numerators = offsets[None, :] - o @ normals.T
    with np.errstate(divide="ignore", invalid="ignore"):
        t = numerators / denominators
    entering = denominators < 0.0
    leaving = denominators > 0.0
    parallel_outside = (denominators == 0.0) & (numerators < 0.0)
    t_enter = np.where(entering, t, -np.inf).max(axis=1)
    t_exit = np.where(leaving, t, np.inf).min(axis=1)
    t_exit = np.where(parallel_outside.any(axis=1), -np.inf, t_exit)
    return t_enter, t_exit


def _quadratic_roots(a, b, c):
    """Real roots of ``a t^2 + b t + c``, two per row (NaN when there are
    none); a linear equation gives one root, twice."""
    disc = b * b - 4.0 * a * c
    roots = np.full(a.shape + (2,), np.nan)
    quadratic = np.abs(a) > 1.0e-14
    ok = quadratic & (disc >= 0.0)
    sqrt_disc = np.sqrt(np.where(ok, disc, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        roots[ok, 0] = ((-b - sqrt_disc) / (2.0 * a))[ok]
        roots[ok, 1] = ((-b + sqrt_disc) / (2.0 * a))[ok]
        linear = ~quadratic & (np.abs(b) > 1.0e-300)
        roots[linear, 0] = (-c / b)[linear]
        roots[linear, 1] = roots[linear, 0]
    return roots


def _curved_candidates(part: ScenePart, o, d):
    """Distances where rays cross the boundary surfaces of a cylinder,
    cone or sphere (local frame)."""
    dims = part.dims
    if part.shape == "sphere":
        r = 0.5 * dims["diameter"]
        a = np.einsum("ij,ij->i", d, d)
        b = 2.0 * np.einsum("ij,ij->i", o, d)
        c = np.einsum("ij,ij->i", o, o) - r * r
        return _quadratic_roots(a, b, c)
    h = dims["height"]
    with np.errstate(divide="ignore", invalid="ignore"):
        t_bottom = np.where(d[:, 2] != 0.0, (-0.5 * h - o[:, 2]) / d[:, 2], np.nan)
        t_top = np.where(d[:, 2] != 0.0, (0.5 * h - o[:, 2]) / d[:, 2], np.nan)
    if part.shape == "cylinder":
        r = 0.5 * dims["diameter"]
        a = d[:, 0] ** 2 + d[:, 1] ** 2
        b = 2.0 * (o[:, 0] * d[:, 0] + o[:, 1] * d[:, 1])
        c = o[:, 0] ** 2 + o[:, 1] ** 2 - r * r
    else:  # cone: base at -h/2, apex at +h/2
        k = 0.5 * dims["base_diameter"] / h
        apex_gap = 0.5 * h - o[:, 2]
        a = d[:, 0] ** 2 + d[:, 1] ** 2 - k * k * d[:, 2] ** 2
        b = 2.0 * (o[:, 0] * d[:, 0] + o[:, 1] * d[:, 1] + k * k * apex_gap * d[:, 2])
        c = o[:, 0] ** 2 + o[:, 1] ** 2 - k * k * apex_gap ** 2
    return np.column_stack([_quadratic_roots(a, b, c), t_bottom, t_top])


def _inside(part: ScenePart, x, tolerance):
    """Which local points lie inside the shape (with ``tolerance`` [m])."""
    dims = part.dims
    if part.shape == "sphere":
        r = 0.5 * dims["diameter"]
        return np.einsum("ij,ij->i", x, x) <= (r + tolerance) ** 2
    h = dims["height"]
    in_height = np.abs(x[:, 2]) <= 0.5 * h + tolerance
    rho2 = x[:, 0] ** 2 + x[:, 1] ** 2
    if part.shape == "cylinder":
        r = 0.5 * dims["diameter"]
        return in_height & (rho2 <= (r + tolerance) ** 2)
    radius_here = 0.5 * dims["base_diameter"] * np.clip((0.5 * h - x[:, 2]) / h, 0.0, None)
    return in_height & (np.sqrt(rho2) <= radius_here + tolerance)


def _curved_interval(part: ScenePart, o, d, tolerance):
    """The one interval of each ray inside a convex curved shape:
    ``(t_enter, t_exit)``, ``t_enter > t_exit`` for a miss."""
    candidates = _curved_candidates(part, o, d)
    candidates = np.sort(np.where(np.isnan(candidates), np.inf, candidates), axis=1)
    count = candidates.shape[1]
    t_enter = np.full(len(o), np.inf)
    t_exit = np.full(len(o), -np.inf)
    # The pieces between consecutive crossings, and before the first one
    # (a ray that starts inside); the shape is convex, so at most one is in.
    bounds = np.concatenate([np.full((len(o), 1), -np.inf), candidates], axis=1)
    for k in range(count):
        start, end = bounds[:, k], bounds[:, k + 1]
        finite = np.isfinite(end)
        with np.errstate(invalid="ignore"):
            mid = np.where(np.isfinite(start), 0.5 * (start + end), end - 1.0)
        mid = np.where(finite, mid, np.nan)
        points = o + np.nan_to_num(mid)[:, None] * d
        inside = finite & _inside(part, points, tolerance)
        first = inside & ~np.isfinite(t_exit)
        t_enter = np.where(first, start, t_enter)
        t_exit = np.where(inside, end, t_exit)
    return t_enter, t_exit


# -- imported meshes: a bounding-volume hierarchy ------------------------------------------------------------------

@dataclass
class _Hierarchy:
    """A mesh's triangles, reordered so each node's are contiguous, and the
    nodes: their boxes, children (-1 for a leaf) and triangle ranges."""

    a: np.ndarray
    edge1: np.ndarray
    edge2: np.ndarray
    low: np.ndarray
    high: np.ndarray
    left: np.ndarray
    right: np.ndarray
    start: np.ndarray
    count: np.ndarray


def _build_hierarchy(mesh: Mesh) -> _Hierarchy:
    a, b, c = mesh.corners()
    centroids = (a + b + c) / 3.0
    tri_low = np.minimum(np.minimum(a, b), c)
    tri_high = np.maximum(np.maximum(a, b), c)
    order = np.arange(len(a))
    nodes = []  # [low, high, left, right, start, count]

    def build(lo: int, hi: int) -> int:
        index = len(nodes)
        idx = order[lo:hi]
        nodes.append([tri_low[idx].min(axis=0), tri_high[idx].max(axis=0), -1, -1, lo, hi - lo])
        if hi - lo > _LEAF_TRIANGLES:
            spread = centroids[idx].max(axis=0) - centroids[idx].min(axis=0)
            axis = int(np.argmax(spread))
            if spread[axis] > 0.0:
                order[lo:hi] = idx[np.argsort(centroids[idx, axis], kind="stable")]
                mid = (lo + hi) // 2
                nodes[index][2] = build(lo, mid)
                nodes[index][3] = build(mid, hi)
        return index

    if len(a):
        build(0, len(a))
    return _Hierarchy(a[order], (b - a)[order], (c - a)[order],
                      np.array([n[0] for n in nodes]).reshape(-1, 3), np.array([n[1] for n in nodes]).reshape(-1, 3),
                      np.array([n[2] for n in nodes], dtype=np.int64), np.array([n[3] for n in nodes], dtype=np.int64),
                      np.array([n[4] for n in nodes], dtype=np.int64), np.array([n[5] for n in nodes], dtype=np.int64))


def _triangle_hits(o, d, a, e1, e2, epsilon):
    """Möller–Trumbore for paired rays and triangles: the distance, or inf."""
    p = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1.0e-18
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = o - a
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    v = np.einsum("ij,ij->i", d, q) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (t > epsilon)
    return np.where(hit, t, np.inf)


def _mesh_nearest(h: _Hierarchy, o, d, epsilon):
    """The nearest triangle hit per ray through the hierarchy (inf: none)."""
    best = np.full(len(o), np.inf)
    if len(h.start) == 0:
        return best
    rays = np.arange(len(o))
    nodes = np.zeros(len(o), dtype=np.int64)
    while len(rays):
        near, far = _box_entry(o[rays], d[rays], h.low[nodes], h.high[nodes])
        keep = (near <= far) & (far > epsilon) & (near < best[rays])
        rays, nodes = rays[keep], nodes[keep]
        leaf = h.left[nodes] < 0
        if leaf.any():
            leaf_rays, leaf_nodes = rays[leaf], nodes[leaf]
            counts = h.count[leaf_nodes]
            pair_rays = np.repeat(leaf_rays, counts)
            offsets = np.arange(counts.sum()) - np.repeat(np.cumsum(counts) - counts, counts)
            tris = np.repeat(h.start[leaf_nodes], counts) + offsets
            t = _triangle_hits(o[pair_rays], d[pair_rays], h.a[tris], h.edge1[tris], h.edge2[tris], epsilon)
            np.minimum.at(best, pair_rays, t)
        inner = ~leaf
        rays = np.concatenate([rays[inner], rays[inner]])
        nodes = np.concatenate([h.left[nodes[inner]], h.right[nodes[inner]]])
    return best


# -- the scene -----------------------------------------------------------------------------------------------------

@dataclass
class ConeBlockage:
    """What part of a cone of directions the model blocks: the blocked
    fraction, each blocking part's share (of the whole cone), the samples
    used and the fraction's standard error."""

    fraction: float  # [-]
    by_part: dict  # part name -> [-]
    samples: int
    standard_error: float  # [-]


@dataclass
class FaceShading:
    """What part of a face's light (weighted by the incidence cosine) other
    parts block from a direction: the shaded fraction, the lit fraction of
    the face (0 when it faces away), the samples and the standard error."""

    shaded_fraction: float  # [-] of the light the face would get without shadows
    facing_fraction: float  # [-] of the face's samples turned toward the direction
    samples: int
    standard_error: float  # [-]
    by_part: dict = field(default_factory=dict)  # part name -> [-] of the light it blocks


class Scene:
    """The parts of a model in one configuration, ready for rays."""

    def __init__(self, parts: list[ScenePart]):
        self.parts = list(parts)
        for part in self.parts:
            _place_bounds(part)
            if part.shape == "mesh":
                part._bvh = _build_hierarchy(part.mesh)
        self.names = [p.name for p in self.parts]
        if self.parts:
            low = np.min([p.bounds_min for p in self.parts], axis=0)
            high = np.max([p.bounds_max for p in self.parts], axis=0)
            self.size_m = float(np.linalg.norm(high - low)) or 1.0
        else:
            self.size_m = 1.0
        self.epsilon_m = _EPSILON_RELATIVE * self.size_m
        self._face_samples: dict = {}

    def index(self, name: str) -> int:
        return self.names.index(name)

    def nearest(self, origins, directions, exclude=()) -> tuple[np.ndarray, np.ndarray]:
        """``(distance, part index)`` of the first part each ray meets
        (``inf`` and ``-1`` for none). Directions need not be unit vectors;
        distances are in units of their length. Parts named in ``exclude``
        are ignored."""
        o = np.atleast_2d(np.asarray(origins, dtype=float))
        d = np.atleast_2d(np.asarray(directions, dtype=float))
        o, d = np.broadcast_arrays(o, d)
        o, d = np.ascontiguousarray(o), np.ascontiguousarray(d)
        best = np.full(len(o), np.inf)
        which = np.full(len(o), -1, dtype=np.int64)
        skip = set(exclude)
        for k, part in enumerate(self.parts):
            if part.name in skip:
                continue
            near, far = _box_entry(o, d, part.bounds_min, part.bounds_max)
            candidates = np.nonzero((near <= far + self.epsilon_m) & (far > self.epsilon_m) & (near < best))[0]
            if not len(candidates):
                continue
            t = self._part_distance(part, o[candidates], d[candidates])
            closer = t < best[candidates]
            best[candidates[closer]] = t[closer]
            which[candidates[closer]] = k
        return best, which

    def _part_distance(self, part: ScenePart, o, d) -> np.ndarray:
        if part.shape == "mesh":
            return _mesh_nearest(part._bvh, o, d, self.epsilon_m)
        local_o = (o - part.position) @ part.rotation
        local_d = d @ part.rotation
        if part.shape in ("box", "panel", "prism"):
            normals, offsets = _planes(part)
            t_enter, t_exit = _convex_planes_interval(local_o, local_d, normals, offsets)
        else:
            t_enter, t_exit = _curved_interval(part, local_o, local_d, self.epsilon_m)
        hit = (t_enter <= t_exit) & (t_exit > self.epsilon_m)
        # A ray that starts inside is blocked at once (distance 0).
        return np.where(hit, np.maximum(t_enter, 0.0), np.inf)

    def visible(self, points, directions, exclude=(), max_distance=np.inf) -> np.ndarray:
        """True where nothing lies along ``directions`` from ``points``
        within ``max_distance`` (in units of the directions' length)."""
        distance, _ = self.nearest(points, directions, exclude)
        return distance >= max_distance

    def cone_blockage(self, apex, axis, half_angle_rad: float, samples: int = 256, exclude=()) -> ConeBlockage:
        """The fraction of a cone of directions (apex, axis, half-angle)
        that meets the model, sampled uniformly in solid angle."""
        directions = cone_directions(axis, half_angle_rad, samples)
        _, which = self.nearest(np.broadcast_to(np.asarray(apex, dtype=float), directions.shape), directions, exclude)
        blocked = which >= 0
        n = len(directions)
        fraction = float(blocked.mean())
        by_part = {self.names[k]: float(np.count_nonzero(which == k)) / n for k in np.unique(which[blocked])}
        return ConeBlockage(fraction, dict(sorted(by_part.items(), key=lambda kv: -kv[1])), n,
                            math.sqrt(fraction * (1.0 - fraction) / n))

    def face_samples(self, part_name: str, face_name: str, samples: int):
        """``(points, normals, weights)`` of a face of a part, in the body
        frame (see :func:`face_samples`), cached."""
        key = (part_name, face_name, samples)
        if key not in self._face_samples:
            part = self.parts[self.index(part_name)]
            self._face_samples[key] = placed_face_samples(part, face_name, samples)
        return self._face_samples[key]

    def face_shading(self, part_name: str, face_name: str, direction, samples: int = 256) -> FaceShading:
        """What part of the light from ``direction`` (toward the source)
        that face ``face_name`` of ``part_name`` would get other parts
        block. The face's own part is ignored for a convex shape, which
        cannot shade itself on its lit side."""
        points, normals, weights = self.face_samples(part_name, face_name, samples)
        s = np.asarray(direction, dtype=float)
        s = s / np.linalg.norm(s)
        cosines = normals @ s
        lit = cosines > 0.0
        n = len(points)
        if not lit.any():
            return FaceShading(0.0, 0.0, n, 0.0)
        part = self.parts[self.index(part_name)]
        exclude = () if part.shape == "mesh" else (part_name,)
        start = points[lit] + normals[lit] * (10.0 * self.epsilon_m)
        _, which = self.nearest(start, np.broadcast_to(s, start.shape), exclude)
        light = weights[lit] * cosines[lit]
        total = float(light.sum())
        blocked = which >= 0
        shaded = float(light[blocked].sum()) / total
        by_part = {self.names[k]: float(light[which == k].sum()) / total for k in np.unique(which[blocked])}
        count = int(lit.sum())
        return FaceShading(shaded, count / n, n, math.sqrt(shaded * (1.0 - shaded) / count), by_part)


def scene_from_model(model, derived=None, configuration: str = "deployed", base_dir=None) -> Scene:
    """The scene of a :class:`~spacemissionstudio.schema.scenario.SpacecraftModelConfig`
    in ``configuration``: the simple shapes from their dimensions, the
    mesh parts from ``derived`` (:func:`.model.derive` in the same
    configuration; derived here when not given). Parts that could not be
    built are left out, as in the model."""
    from . import model as model_module

    if derived is None:
        derived = model_module.derive(model, base_dir=base_dir, configuration=configuration)
    poses = model_module.poses(model, configuration)
    built = {p.name: p for p in derived.parts if p.mesh is not None}
    parts = []
    for part in model.parts:
        if part.name not in built:
            continue
        position, rotation_deg = poses.get(part.name, (part.position_b_m, part.rotation_deg))
        rotation = rotation_matrix(rotation_deg)
        dims = {k: float(v) for k, v in part.dimensions_m.items()}
        if part.shape == "mesh":
            parts.append(ScenePart(part.name, "mesh", dims, rotation, np.asarray(position, dtype=float),
                                   mesh=built[part.name].mesh))
        else:
            parts.append(ScenePart(part.name, part.shape, dims, rotation, np.asarray(position, dtype=float),
                                   sides=part.sides, segments=part.segments))
    return Scene(parts)


# -- sampling ------------------------------------------------------------------------------------------------------

def cone_directions(axis, half_angle_rad: float, count: int) -> np.ndarray:
    """``count`` unit directions spread uniformly in solid angle over the
    cap of half-angle ``half_angle_rad`` about ``axis`` (a Fibonacci
    spiral on the cap)."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    k = np.arange(count) + 0.5
    cos_cap = math.cos(half_angle_rad)
    z = 1.0 - (1.0 - cos_cap) * k / count  # uniform in cos: uniform in solid angle
    phi = math.pi * (3.0 - math.sqrt(5.0)) * k
    rho = np.sqrt(np.clip(1.0 - z * z, 0.0, None))
    local = np.column_stack([rho * np.cos(phi), rho * np.sin(phi), z])
    return local @ _frame_with_z(axis).T


def _frame_with_z(z) -> np.ndarray:
    """A rotation whose third column is the unit vector ``z``."""
    helper = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = np.cross(helper, z)
    x /= np.linalg.norm(x)
    return np.column_stack([x, np.cross(z, x), z])


def _grid(count: int) -> tuple[np.ndarray, np.ndarray]:
    """A stratified ``m x m`` grid of cell centres in the unit square, with
    ``m = ceil(sqrt(count))``."""
    m = max(1, math.ceil(math.sqrt(count)))
    u = (np.arange(m) + 0.5) / m
    uu, vv = np.meshgrid(u, u, indexing="ij")
    return uu.reshape(-1), vv.reshape(-1)


def _rectangle(center, axis_u, axis_v, width, height, normal, count):
    u, v = _grid(count)
    points = (np.asarray(center, dtype=float) + np.outer(u - 0.5, axis_u) * width + np.outer(v - 0.5, axis_v) * height)
    weights = np.full(len(points), width * height / len(points))
    return points, np.tile(np.asarray(normal, dtype=float), (len(points), 1)), weights


def _disk(z: float, radius: float, normal_z: float, count: int):
    u, v = _grid(count)
    rho = radius * np.sqrt(u)
    theta = 2.0 * math.pi * v
    points = np.column_stack([rho * np.cos(theta), rho * np.sin(theta), np.full(len(u), z)])
    weights = np.full(len(points), math.pi * radius * radius / len(points))
    return points, np.tile([0.0, 0.0, normal_z], (len(points), 1)), weights


def _polygon_cap(corners: np.ndarray, z: float, normal_z: float, count: int):
    """A regular polygon (corners in xy) sampled by its fan triangles."""
    n = len(corners)
    per = max(1, math.ceil(count / n))
    u, v = _grid(per)
    fold = u + v > 1.0
    u, v = np.where(fold, 1.0 - u, u), np.where(fold, 1.0 - v, v)
    points, weights = [], []
    for i in range(n):
        a, b = corners[i], corners[(i + 1) % n]
        tri = np.outer(u, a) + np.outer(v, b)
        points.append(np.column_stack([tri, np.full(len(tri), z)]))
        area = 0.5 * abs(a[0] * b[1] - a[1] * b[0])
        weights.append(np.full(len(tri), area / len(tri)))
    points = np.concatenate(points)
    return points, np.tile([0.0, 0.0, normal_z], (len(points), 1)), np.concatenate(weights)


def face_samples(shape: str, dims: dict, face_name: str, count: int, sides: int = shapes.DEFAULT_SIDES,
                 segments: int = shapes.DEFAULT_SEGMENTS, mesh: Mesh | None = None):
    """``(points (k, 3), normals (k, 3), weights (k,))`` on a face, in the
    shape's local frame (a mesh's in the frame its triangles are in): about
    ``count`` points on a stratified grid over the true surface, each
    standing for ``weight`` of its area [m^2]. Face names are those of
    :func:`.shapes.faces`; a curved side ``side k`` is the strip of the
    true surface centred on its facet's normal."""
    if shape in ("box", "panel"):
        if shape == "box":
            size = {"x": dims["x"], "y": dims["y"], "z": dims["z"]}
        else:
            size = {"x": dims["width"], "y": dims["length"], "z": dims["thickness"]}
        axis = face_name[1]
        sign = 1.0 if face_name[0] == "+" else -1.0
        k = "xyz".index(axis)
        others = [i for i in range(3) if i != k]
        normal = np.zeros(3)
        normal[k] = sign
        center = normal * 0.5 * size[axis]
        eu, ev = np.eye(3)[others[0]], np.eye(3)[others[1]]
        return _rectangle(center, eu, ev, size["xyz"[others[0]]], size["xyz"[others[1]]], normal, count)
    if shape in ("prism", "cylinder", "cone"):
        h = dims["height"]
        if face_name in ("+z", "-z"):
            z = 0.5 * h if face_name == "+z" else -0.5 * h
            normal_z = 1.0 if face_name == "+z" else -1.0
            if shape == "prism":
                radius = 0.5 * dims["width_across_flats"] / math.cos(math.pi / sides)
                angles = math.pi / sides + 2.0 * math.pi * np.arange(sides) / sides
                corners = np.column_stack([radius * np.cos(angles), radius * np.sin(angles)])
                return _polygon_cap(corners, z, normal_z, count)
            radius = 0.5 * (dims["diameter"] if shape == "cylinder" else dims["base_diameter"])
            return _disk(z, radius, normal_z, count)
        k = int(face_name.split()[1]) - 1
        n = sides if shape == "prism" else segments
        theta_k = 2.0 * math.pi * k / n
        if shape == "prism":
            apothem = 0.5 * dims["width_across_flats"]
            side = 2.0 * apothem * math.tan(math.pi / n)
            normal = np.array([math.cos(theta_k), math.sin(theta_k), 0.0])
            tangent = np.array([-math.sin(theta_k), math.cos(theta_k), 0.0])
            return _rectangle(apothem * normal, tangent, np.array([0.0, 0.0, 1.0]), side, h, normal, count)
        u, v = _grid(count)
        theta = theta_k + (u - 0.5) * 2.0 * math.pi / n
        if shape == "cylinder":
            r = 0.5 * dims["diameter"]
            points = np.column_stack([r * np.cos(theta), r * np.sin(theta), (v - 0.5) * h])
            normals = np.column_stack([np.cos(theta), np.sin(theta), np.zeros(len(u))])
            area = 2.0 * math.pi * r * h / n
        else:
            r = 0.5 * dims["base_diameter"]
            slant = math.hypot(r, h)
            s = 1.0 - np.sqrt(1.0 - v)  # uniform in area: the strip narrows toward the apex
            rho = r * (1.0 - s)
            points = np.column_stack([rho * np.cos(theta), rho * np.sin(theta), -0.5 * h + s * h])
            normals = np.column_stack([h * np.cos(theta), h * np.sin(theta), np.full(len(u), r)]) / slant
            area = math.pi * r * slant / n
        return points, normals, np.full(len(points), area / len(points))
    if shape == "sphere":
        r = 0.5 * dims["diameter"]
        faces_count = max(2 * segments, 8)
        directions = shapes._fibonacci_directions(faces_count)
        fine = shapes._fibonacci_directions(faces_count * max(count, 1))
        owner = np.argmax(fine @ directions.T, axis=1)
        k = int(face_name.split()[1]) - 1
        mine = fine[owner == k]
        area = 4.0 * math.pi * r * r / faces_count
        return r * mine, mine.copy(), np.full(len(mine), area / max(len(mine), 1))
    if shape == "mesh":
        return _mesh_face_samples(mesh, face_name, count)
    raise ValueError(f"unknown shape {shape!r}")


def _mesh_face_samples(mesh: Mesh, face_name: str, count: int):
    """Samples on a mesh's ``plane k``: its triangles (grouped as
    :func:`.surfaces.mesh_faces` groups them), each sampled in proportion
    to its area."""
    from . import surfaces
    from .geometry import triangle_areas_and_normals

    areas, normals, centroids = triangle_areas_and_normals(mesh)
    groups = surfaces.mesh_face_groups(mesh)
    k = int(face_name.split()[1]) - 1
    tris = np.nonzero(groups == k)[0]
    a, b, c = mesh.corners()
    total = float(areas[tris].sum())
    points, weights, normal_rows = [], [], []
    for t in tris:
        share = max(1, round(count * areas[t] / total))
        u, v = _grid(share)
        fold = u + v > 1.0
        u, v = np.where(fold, 1.0 - u, u), np.where(fold, 1.0 - v, v)
        points.append(a[t] + np.outer(u, b[t] - a[t]) + np.outer(v, c[t] - a[t]))
        weights.append(np.full(len(u), areas[t] / len(u)))
        normal_rows.append(np.tile(normals[t], (len(u), 1)))
    return np.concatenate(points), np.concatenate(normal_rows), np.concatenate(weights)


def placed_face_samples(part: ScenePart, face_name: str, count: int):
    """:func:`face_samples` of a scene part's face, in the body frame."""
    if part.shape == "mesh":
        return face_samples("mesh", {}, face_name, count, mesh=part.mesh)
    points, normals, weights = face_samples(part.shape, part.dims, face_name, count, part.sides, part.segments)
    return points @ part.rotation.T + part.position, normals @ part.rotation.T, weights
