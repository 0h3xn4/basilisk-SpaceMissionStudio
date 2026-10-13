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

"""From a :class:`~spacemissionstudio.schema.scenario.SpacecraftModelConfig`
to what the simulation reads.

:func:`derive` places every part in the body frame and gives the drawn
meshes, the mass properties (computed from the parts, or the typed or
imported ones) and the facets. It never raises: a part that cannot be
built (a missing mesh file, a solid that is not closed) is reported in
``errors`` and left out, so an editor can call it on every change.

:func:`apply` writes those values into the spacecraft's own fields --
``dry_mass_kg``, ``center_of_mass_b_m``, ``inertia_kg_m2`` and
``facets`` -- which the engine, Monte Carlo and long runs read exactly as
when they are typed in. :func:`stale_fields` says which of them no longer
match the model.

**Mass bookkeeping.** The model's mass is what the hub carries.
``dry_mass_kg`` counts flexible solar arrays too (they are their own state
effectors with their own mass, see ``engine.solar_arrays``), so applying
adds their mass to the model's. Parts drawn for an array should therefore
have ``counts_toward_mass`` off. Station-keeping propellant stays outside
``dry_mass_kg``, as before.

``visible`` only controls drawing (the editor and Vizard); a hidden part
still has its mass and faces.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..schema.scenario import FacetConfig
from . import mass_properties as mp
from . import obj_io, shapes, surfaces
from .geometry import Mesh, rotation_matrix

# Applied values that differ from the model's by less than this are the
# same (rounding in the saved file).
_STALE_RELATIVE = 1.0e-6  # [-]


@dataclass
class DerivedPart:
    """One part as drawn: its body-frame mesh and colour, or the reason it
    could not be built."""

    name: str
    mesh: Optional[Mesh]
    color: Tuple[float, float, float]
    visible: bool
    error: Optional[str] = None


@dataclass
class DerivedModel:
    parts: List[DerivedPart] = field(default_factory=list)
    computed: mp.MassProperties = field(default_factory=mp.zero)  # from the parts that count toward mass
    mass_properties: Optional[mp.MassProperties] = None  # per mass_properties_source; None when there is no mass
    faces: List[shapes.Face] = field(default_factory=list)  # body frame, with "part: face" names
    facets: Optional[List[FacetConfig]] = None  # None when there are none or too many
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def projected_areas_m2(self) -> Dict[str, float]:
        """Area seen from +x, -x, +y, -y, +z and -z [m^2]."""
        axes = {"+x": [1, 0, 0], "-x": [-1, 0, 0], "+y": [0, 1, 0], "-y": [0, -1, 0], "+z": [0, 0, 1], "-z": [0, 0, -1]}
        return {name: surfaces.projected_area_m2(self.faces, d) for name, d in axes.items()}

    def bounds(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        meshes = [p.mesh for p in self.parts if p.mesh is not None and len(p.mesh.vertices)]
        if not meshes:
            return None
        return (np.min([m.vertices.min(axis=0) for m in meshes], axis=0),
                np.max([m.vertices.max(axis=0) for m in meshes], axis=0))


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def mesh_path(mesh_config, base_dir) -> Path:
    """A model mesh file's path: as written if absolute, else relative to
    ``base_dir`` (the scenario file's folder)."""
    path = Path(mesh_config.path).expanduser()
    if path.is_absolute() or base_dir is None:
        return path
    return Path(base_dir) / path


class MeshCache:
    """Read ``.obj`` files once per (path, size, modification time, units,
    up axis), and each mesh part's unit-mass properties and faces once per
    (file, group, scale, distribution). An editor keeps one for its
    lifetime; :func:`derive` makes a fresh one when given none."""

    def __init__(self) -> None:
        self._files: Dict[tuple, obj_io.ObjFile] = {}
        self._parts: Dict[tuple, tuple] = {}

    def read(self, path: Path, units: str, up_axis: str) -> obj_io.ObjFile:
        stat = path.stat()
        key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns, units, up_axis)
        if key not in self._files:
            self._files[key] = obj_io.read_obj(path, units=units, up_axis=up_axis)
        return self._files[key]

    def mesh_part(self, file_key: tuple, group: obj_io.ObjGroup, scale: tuple, shell: bool):
        """``(scaled_mesh, unit-mass properties or MassPropertiesError, local faces)``."""
        key = (file_key, group.name, scale, shell)
        if key not in self._parts:
            scaled = group.mesh.transformed(np.eye(3), [0.0, 0.0, 0.0], scale=scale).welded()
            try:
                unit = mp.shell_mesh(scaled, 1.0) if shell else mp.solid_mesh(scaled, 1.0)
            except mp.MassPropertiesError as exc:
                unit = exc
            self._parts[key] = (scaled, unit, surfaces.mesh_faces(scaled))
        return self._parts[key]


def _scaled(unit: mp.MassProperties, mass_kg: float) -> mp.MassProperties:
    return mp.MassProperties(mass_kg, unit.center_of_mass_m, unit.inertia_kg_m2 * mass_kg)


def _typed(model) -> Optional[mp.MassProperties]:
    typed = model.mass_properties
    if typed is None:
        return None
    return mp.MassProperties(typed.mass_kg, typed.center_of_mass_b_m, np.reshape(typed.inertia_kg_m2, (3, 3)))


def derive(model, base_dir=None, cache: Optional[MeshCache] = None) -> DerivedModel:
    """See the module docstring. ``base_dir`` resolves relative mesh paths."""
    cache = cache or MeshCache()
    result = DerivedModel()
    files: Dict[int, Tuple[tuple, obj_io.ObjFile]] = {}
    for index, mesh_config in enumerate(model.meshes):
        path = mesh_path(mesh_config, base_dir)
        try:
            obj = cache.read(path, mesh_config.units, mesh_config.up_axis)
        except (OSError, obj_io.ObjError) as exc:
            result.errors.append(f"mesh file {mesh_config.path}: {exc}")
            continue
        files[index] = ((str(path), mesh_config.units, mesh_config.up_axis), obj)
        if mesh_config.sha256 and file_sha256(path) != mesh_config.sha256:
            result.warnings.append(f"mesh file {mesh_config.path} changed since it was imported (SHA-256 differs)")

    bodies: List[mp.MassProperties] = []
    for part in model.parts:
        color = tuple(float(c) for c in part.color)
        try:
            rotation = rotation_matrix(part.rotation_deg)
            position = np.asarray(part.position_b_m, dtype=float)
            shell = part.distribution == "shell"
            if part.shape == "mesh":
                if part.mesh_index not in files:
                    raise ValueError("its mesh file could not be read")
                file_key, obj = files[part.mesh_index]
                try:
                    group = obj.group(part.mesh_group)
                except KeyError:
                    raise ValueError(f"the mesh file has no group {part.mesh_group!r}") from None
                scaled, unit, local_faces = cache.mesh_part(file_key, group, tuple(float(s) for s in part.scale), shell)
                local_mesh = scaled
                local_mass = None if isinstance(unit, Exception) else _scaled(unit, float(part.mass_kg))
                mass_error = str(unit) if isinstance(unit, Exception) else None
            else:
                dims = {k: float(v) for k, v in part.dimensions_m.items()}
                local_mesh = shapes.mesh(part.shape, dims, sides=part.sides, segments=part.segments)
                local_faces = shapes.faces(part.shape, dims, sides=part.sides, segments=part.segments)
                local_mass = shapes.mass_properties(part.shape, dims, float(part.mass_kg), shell, sides=part.sides)
                mass_error = None
        except (ValueError, KeyError, mp.MassPropertiesError) as exc:
            result.parts.append(DerivedPart(part.name, None, color, part.visible, str(exc)))
            result.errors.append(f"part {part.name!r}: {exc}")
            continue
        result.parts.append(DerivedPart(part.name, local_mesh.transformed(rotation, position), color, part.visible))
        if part.counts_toward_mass and part.mass_kg > 0.0:
            if mass_error is not None:
                result.errors.append(f"part {part.name!r}: {mass_error}")
            else:
                bodies.append(mp.placed(local_mass, rotation, position))
        if part.in_surface_model:
            excluded = set(part.excluded_faces)
            for face in surfaces.placed_faces(local_faces, rotation, position):
                if face.group not in excluded and face.area_m2 > 0.0:
                    face.name = f"{part.name}: {face.name}"
                    result.faces.append(face)

    result.computed = mp.combine(bodies)
    if model.mass_properties_source == "computed":
        result.mass_properties = result.computed if result.computed.mass_kg > 0.0 else None
        if result.mass_properties is None:
            result.warnings.append("no part has a mass that counts toward the spacecraft's mass")
    else:
        result.mass_properties = _typed(model)

    if result.faces:
        if len(result.faces) > surfaces.MAX_FACETS:
            result.warnings.append(f"the model gives {len(result.faces)} facets, more than {surfaces.MAX_FACETS}: "
                                   "leave some parts out of the surface model, or simplify the mesh")
        else:
            result.facets = [FacetConfig(name=face.name, area_m2=float(face.area_m2),
                                         normal_b=[float(v) for v in face.normal],
                                         location_b=[float(v) for v in face.centroid_m],
                                         **_coefficients(model, face.name)) for face in result.faces]

    box = result.bounds()
    if box is not None and result.mass_properties is not None:
        low, high = box
        com = result.mass_properties.center_of_mass_m
        margin = 1.0e-6 + 0.01 * float(np.max(high - low))
        if np.any(com < low - margin) or np.any(com > high + margin):
            result.warnings.append("the center of mass lies outside the model")
    return result


def _coefficients(model, face_name: str) -> dict:
    part_name = face_name.split(": ", 1)[0]
    part = next(p for p in model.parts if p.name == part_name)
    return {"drag_coeff": float(part.drag_coeff), "specular_coeff": float(part.specular_coeff),
            "diffuse_coeff": float(part.diffuse_coeff)}


def _arrays_mass_kg(sc_config) -> float:
    return float(sum(array.mass_kg for array in sc_config.solar_arrays))


def _clean(value: float) -> float:
    """A float rounded to 10 significant digits, so a saved file does not
    carry floating-point noise such as 1.2000000000000002."""
    return float(f"{value:.10g}") if value != 0.0 else 0.0


# Below these, a value is summation noise (an octagon's corners add up to
# 1e-17 m, not to 0): tidied to exactly zero.
_POSITION_NOISE_M = 1.0e-9  # [m]
_INERTIA_NOISE_RELATIVE = 1.0e-12  # [-] of the largest moment


def tidy(props: mp.MassProperties) -> mp.MassProperties:
    """``props`` with summation noise set to zero, the inertia made exactly
    symmetric, and everything rounded to 10 significant digits."""
    com = np.where(np.abs(props.center_of_mass_m) < _POSITION_NOISE_M, 0.0, props.center_of_mass_m)
    inertia = 0.5 * (props.inertia_kg_m2 + props.inertia_kg_m2.T)
    floor = _INERTIA_NOISE_RELATIVE * float(np.max(np.abs(inertia))) if inertia.size else 0.0
    inertia = np.where(np.abs(inertia) < floor, 0.0, inertia)
    clean = np.vectorize(_clean)
    return mp.MassProperties(_clean(props.mass_kg), clean(com), clean(inertia))


def applied_values(sc_config, derived: DerivedModel, orbit_only: bool = False) -> dict:
    """The field values :func:`apply` would write: a subset of
    ``dry_mass_kg``, ``center_of_mass_b_m``, ``inertia_kg_m2`` and
    ``facets``. Facets are left alone in an orbit-only scenario, which
    cannot use them."""
    model = sc_config.model
    values: dict = {}
    if model.apply_mass_properties and derived.mass_properties is not None:
        props = tidy(derived.mass_properties)
        values["dry_mass_kg"] = _clean(props.mass_kg + _arrays_mass_kg(sc_config))
        values["center_of_mass_b_m"] = [float(v) for v in props.center_of_mass_m]
        values["inertia_kg_m2"] = [float(v) for v in props.inertia_kg_m2.reshape(9)]
    if model.apply_facets and not orbit_only and derived.facets is not None:
        values["facets"] = derived.facets
    return values


def apply(sc_config, derived: DerivedModel, orbit_only: bool = False) -> List[str]:
    """Write :func:`applied_values` into ``sc_config``; returns the names of
    the fields written."""
    values = applied_values(sc_config, derived, orbit_only=orbit_only)
    for name, value in values.items():
        setattr(sc_config, name, value)
    return list(values)


def _differs(a, b) -> bool:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = max(float(np.max(np.abs(a))) if a.size else 0.0, float(np.max(np.abs(b))) if b.size else 0.0, 1.0e-9)
    return a.shape != b.shape or float(np.max(np.abs(a - b))) > _STALE_RELATIVE * scale


def stale_fields(sc_config, derived: DerivedModel, orbit_only: bool = False) -> List[str]:
    """The fields whose stored values no longer match what the model
    gives (the model was edited, or the fields were edited by hand)."""
    stale = []
    for name, value in applied_values(sc_config, derived, orbit_only=orbit_only).items():
        current = getattr(sc_config, name)
        if name == "facets":
            if len(current) != len(value) or any(
                    c.name != v.name or _differs([c.area_m2, *c.normal_b, *c.location_b, c.drag_coeff,
                                                  c.specular_coeff, c.diffuse_coeff],
                                                 [v.area_m2, *v.normal_b, *v.location_b, v.drag_coeff,
                                                  v.specular_coeff, v.diffuse_coeff])
                    for c, v in zip(current, value)):
                stale.append(name)
        elif _differs(current, value):
            stale.append(name)
    return stale


def obj_groups(derived: DerivedModel, visible_only: bool = True) -> List[obj_io.ObjGroup]:
    """The built parts as ``.obj`` groups (body frame), for Vizard or an
    export."""
    return [obj_io.ObjGroup(p.name, p.mesh, p.color) for p in derived.parts
            if p.mesh is not None and (p.visible or not visible_only)]


def principal_summary(props: mp.MassProperties) -> List[str]:
    """Short lines describing mass properties, for the CLI and the editor."""
    props = tidy(props)
    moments, axes = props.principal()
    axes = np.where(np.abs(axes) < 1.0e-9, 0.0, axes) + 0.0  # no "-0.0000"
    com = props.center_of_mass_m
    i = props.inertia_kg_m2
    lines = [f"mass {props.mass_kg:.6g} kg",
             f"center of mass [{com[0]:.6g}, {com[1]:.6g}, {com[2]:.6g}] m from B",
             "inertia about it [kg m^2]: "
             f"Ixx {i[0, 0]:.6g}, Iyy {i[1, 1]:.6g}, Izz {i[2, 2]:.6g}, "
             f"Ixy {i[0, 1]:.6g}, Ixz {i[0, 2]:.6g}, Iyz {i[1, 2]:.6g}",
             "principal moments [kg m^2]: " + ", ".join(f"{m:.6g}" for m in moments)]
    for k in range(3):
        axis = axes[:, k]
        angle = math.degrees(math.acos(min(1.0, abs(float(axis[int(np.argmax(np.abs(axis)))])))))
        lines.append(f"  axis {k + 1}: [{axis[0]:.4f}, {axis[1]:.4f}, {axis[2]:.4f}] "
                     f"({angle:.1f} deg from the nearest body axis)")
    return lines
