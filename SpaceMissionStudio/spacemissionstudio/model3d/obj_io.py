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

"""Reading and writing Wavefront ``.obj`` meshes (and their ``.mtl``
colours), without a third-party library.

What is read:

- ``v x y z`` vertices; ``f`` faces of three or more corners, written
  ``i``, ``i/t``, ``i//n`` or ``i/t/n``, indices from 1 or negative (from
  the end). Faces with more than three corners are split into a fan.
- ``o name`` and ``g name`` start a group; each group becomes one part. A
  name seen again adds to that group; faces before any name go to
  ``"default"``.
- ``usemtl`` and ``mtllib``: a group's colour is the ``Kd`` of the first
  material it uses, read from a ``.mtl`` in the same folder only (a
  ``mtllib`` naming another folder is ignored, so a file cannot make the
  reader open arbitrary paths).
- Everything else (texture coordinates, normals, smoothing, lines, curves)
  is ignored: the shape comes from the faces alone.

``.obj`` files carry no unit and no "up" direction. :func:`read_obj` takes
``units`` (``m``, ``mm``, ``cm``, ``in``) and ``up_axis`` (``z``, or ``y``
for the many tools that export Y-up; turned so their up becomes +z).

Limits, checked before anything large is built: 50 MB per file and
1,000,000 triangles. A malformed line raises :class:`ObjError` naming the
line number.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Sequence

import numpy as np

from .geometry import Mesh

MAX_FILE_BYTES = 50 * 1024 * 1024  # [byte]
MAX_TRIANGLES = 1_000_000

UNITS_M = {"m": 1.0, "mm": 0.001, "cm": 0.01, "in": 0.0254}  # [m] per file unit
UP_AXES = ("z", "y")


class ObjError(ValueError):
    """An ``.obj`` or ``.mtl`` file that cannot be read, with the reason."""


@dataclass
class ObjGroup:
    """One named group: its mesh [m] (in the converted frame) and colour
    (RGB in 0..1, or None when no material gives one)."""

    name: str
    mesh: Mesh
    color: tuple[float, float, float] | None = None


@dataclass
class ObjFile:
    groups: list[ObjGroup] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def group(self, name: str) -> ObjGroup:
        for group in self.groups:
            if group.name == name:
                return group
        raise KeyError(name)


def _read_text(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ObjError(f"{path}: cannot be read ({exc.strerror or exc})") from exc
    if size > MAX_FILE_BYTES:
        raise ObjError(f"{path}: {size / 1e6:.1f} MB is larger than the {MAX_FILE_BYTES // (1024 * 1024)} MB limit")
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _read_mtl(path: Path) -> dict[str, tuple[float, float, float]]:
    colors: dict[str, tuple[float, float, float]] = {}
    current: str | None = None
    for number, line in enumerate(_read_text(path).splitlines(), start=1):
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        if parts[0] == "newmtl":
            current = " ".join(parts[1:]) or f"material {number}"
        elif parts[0] == "Kd" and current is not None:
            try:
                rgb = tuple(min(max(float(v), 0.0), 1.0) for v in parts[1:4])
            except ValueError as exc:
                raise ObjError(f"{path}, line {number}: Kd needs three numbers") from exc
            if len(rgb) == 3:
                colors[current] = rgb
    return colors


def _corner_index(token: str, vertex_count: int, path: Path, number: int) -> int:
    text = token.split("/", 1)[0]
    try:
        index = int(text)
    except ValueError as exc:
        raise ObjError(f"{path}, line {number}: {token!r} is not a vertex index") from exc
    resolved = index - 1 if index > 0 else vertex_count + index
    if index == 0 or not 0 <= resolved < vertex_count:
        raise ObjError(f"{path}, line {number}: vertex {index} does not exist (the file has {vertex_count} so far)")
    return resolved


def _convert(vertices: np.ndarray, units: str, up_axis: str) -> np.ndarray:
    if units not in UNITS_M:
        raise ObjError(f"unknown units {units!r}; use one of {', '.join(UNITS_M)}")
    if up_axis not in UP_AXES:
        raise ObjError(f"unknown up axis {up_axis!r}; use 'z' or 'y'")
    converted = vertices * UNITS_M[units]
    if up_axis == "y":  # (x, y, z) Y-up -> Z-up: +90 deg about x
        converted = np.column_stack([converted[:, 0], -converted[:, 2], converted[:, 1]])
    return converted


def read_obj(path, units: str = "m", up_axis: str = "z") -> ObjFile:
    """Read ``path`` (see the module docstring). Each group's mesh keeps
    only the vertices its faces use."""
    path = Path(path)
    text = _read_text(path)
    vertices: list[tuple[float, float, float]] = []
    group_triangles: dict[str, list[tuple[int, int, int]]] = {}
    group_material: dict[str, str] = {}
    materials: dict[str, tuple[float, float, float]] = {}
    warnings: list[str] = []
    current = "default"
    material: str | None = None
    triangle_count = 0
    for number, line in enumerate(text.splitlines(), start=1):
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        keyword = parts[0]
        if keyword == "v":
            try:
                x, y, z = (float(v) for v in parts[1:4])
            except ValueError as exc:
                raise ObjError(f"{path}, line {number}: a vertex needs three numbers") from exc
            if not all(math.isfinite(v) for v in (x, y, z)):
                raise ObjError(f"{path}, line {number}: a vertex coordinate is not finite")
            vertices.append((x, y, z))
        elif keyword == "f":
            if len(parts) < 4:
                raise ObjError(f"{path}, line {number}: a face needs at least three corners")
            corners = [_corner_index(token, len(vertices), path, number) for token in parts[1:]]
            triangles = group_triangles.setdefault(current, [])
            for k in range(1, len(corners) - 1):
                triangles.append((corners[0], corners[k], corners[k + 1]))
            triangle_count += len(corners) - 2
            if triangle_count > MAX_TRIANGLES:
                raise ObjError(f"{path}: more than {MAX_TRIANGLES:,} triangles; simplify the model first")
            if material is not None:
                group_material.setdefault(current, material)
        elif keyword in ("o", "g"):
            current = " ".join(parts[1:]) or "default"
        elif keyword == "usemtl":
            material = " ".join(parts[1:]) or None
        elif keyword == "mtllib":
            name = " ".join(parts[1:])
            if os.path.basename(name) != name or name in ("", ".", ".."):
                warnings.append(f"line {number}: material file {name!r} is not in the model's folder; ignored")
                continue
            mtl_path = path.parent / name
            if mtl_path.is_file():
                materials.update(_read_mtl(mtl_path))
            else:
                warnings.append(f"material file {name} not found; colours from it are not used")
    if not group_triangles:
        raise ObjError(f"{path}: no faces found")
    converted = _convert(np.asarray(vertices, dtype=float).reshape(-1, 3), units, up_axis)
    groups = []
    for name, triangles in group_triangles.items():
        indices = np.asarray(triangles, dtype=np.int64)
        used, remapped = np.unique(indices, return_inverse=True)
        mesh = Mesh(converted[used], remapped.reshape(-1, 3))
        groups.append(ObjGroup(name, mesh, materials.get(group_material.get(name, ""))))
    return ObjFile(groups, warnings)


def _number(value: float) -> str:
    return f"{value:.9g}"


def write_obj(path, groups: Sequence[ObjGroup]) -> Path:
    """Write ``groups`` to ``path`` and their colours to a ``.mtl`` beside
    it (same stem). Returns the ``.obj`` path."""
    path = Path(path)
    mtl_path = path.with_suffix(".mtl")
    obj_lines = ["# SpaceMissionStudio 3D model; units: m; body frame, +z up",
                 f"mtllib {mtl_path.name}"]
    mtl_lines = ["# SpaceMissionStudio 3D model colours"]
    offset = 0
    for k, group in enumerate(groups):
        material = f"material_{k + 1}"
        r, g, b = group.color if group.color is not None else (0.7, 0.7, 0.7)
        mtl_lines += [f"newmtl {material}", f"Kd {_number(r)} {_number(g)} {_number(b)}"]
        obj_lines += [f"o {group.name}", f"usemtl {material}"]
        obj_lines += [f"v {_number(x)} {_number(y)} {_number(z)}" for x, y, z in group.mesh.vertices]
        obj_lines += [f"f {a + offset + 1} {b + offset + 1} {c + offset + 1}" for a, b, c in group.mesh.triangles]
        offset += len(group.mesh.vertices)
    path.write_text("\n".join(obj_lines) + "\n", encoding="utf-8")
    mtl_path.write_text("\n".join(mtl_lines) + "\n", encoding="utf-8")
    return path
