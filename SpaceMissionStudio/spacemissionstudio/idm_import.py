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
"""Importing an IDM-CIC model (IDM-CIC is © CNES) into a spacecraft's 3D
model: the mapping layer above the reader (``spacemissionstudio.idm``).

:func:`plan` turns a model placed in a configuration into parts,
mounted point masses, stowed poses and generated meshes, all in the body
frame of one element; :func:`merge` writes a plan into a scenario: the
meshes file beside the scenario, the parts and equipment matched to an
earlier import by the source object's ``fullId``, the import record, and
the mass properties applied to the spacecraft. The rules are in
``docs/developer/idm-cic-integration.md`` (sections 3 to 9).
"""

from __future__ import annotations

import collections
import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from .idm import frames
from .idm.errors import IdmError
from .idm.model import IdmModel, Placement
from .model3d import mass_properties as mp
from .model3d.obj_io import ObjError, ObjGroup, read_obj, write_obj
from .schema.scenario import (
    _NAME_FORBIDDEN,
    MAX_NAME_CHARS,
    ImportRecord,
    ModelMeshConfig,
    ModelPartConfig,
    MountConfig,
    MountedEquipmentConfig,
    PartPoseConfig,
    SpacecraftModelConfig,
    model_import_values,
    put_import,
)

FORMAT = "idm_cic"
TARGET = "model"
#: The folder, beside the scenario, that the generated meshes are written to.
MESH_FOLDER = "models"
_PRIMITIVES = ("box", "cylinder", "cone", "sphere")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{k}" for k in range(1, 10)),
                     *(f"LPT{k}" for k in range(1, 10))}


def mesh_file_name(spacecraft: str) -> str:
    """The generated meshes' file, relative to the scenario's folder."""
    return f"{MESH_FOLDER}/{spacecraft}_idm.obj"


@dataclass
class ImportSummary:
    """What an import read and did, for the CLI and the GUI to show."""

    source: str
    sha256: str
    version: str
    project: str
    configuration: str
    stowed_configuration: str
    body_element: str
    elements: list  # the element names imported
    left_out: list  # (element name, reason)
    parts: int = 0
    equipment: int = 0
    meshes: int = 0
    mass_kg: float = 0.0  # [kg] of what was imported, propellant included
    propellant_kg: float = 0.0  # [kg]
    approximations: dict = field(default_factory=dict)  # {reason: [item names]}
    margins: list = field(default_factory=list)  # (equipment name, maturity level, margin fraction)
    notes: list = field(default_factory=list)
    added: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    kept: list = field(default_factory=list)  # (item name, what was kept as edited)
    gone: list = field(default_factory=list)
    unchanged: int = 0

    def lines(self) -> list[str]:
        """The summary as text lines."""
        out = [f"IDM-CIC model {self.source} (model version {self.version or 'not given'}"
               + (f", project {self.project}" if self.project else "") + ")",
               f"  configuration: {self.configuration}"
               + (f"; stowed configuration: {self.stowed_configuration}" if self.stowed_configuration else ""),
               f"  body frame: element {self.body_element}; elements imported: {', '.join(self.elements)}"]
        for name, reason in self.left_out:
            out.append(f"  left out: element {name} ({reason})")
        out.append(f"  {self.parts} part(s), {self.equipment} point mass(es), {self.meshes} generated mesh(es); "
                   f"{self.mass_kg:.6g} kg imported" + (f", of which {self.propellant_kg:.6g} kg propellant"
                                                        if self.propellant_kg else ""))
        if self.added or self.updated or self.kept or self.gone or self.unchanged:
            out.append(f"  re-import: {len(self.added)} added, {len(self.updated)} updated, {self.unchanged} unchanged, "
                       f"{len(self.kept)} kept as edited, {len(self.gone)} no longer in the file")
        for name, what in self.kept:
            out.append(f"    kept as edited: {name}: {what}")
        for name in self.gone:
            out.append(f"    no longer in the file (kept; remove it if it should go): {name}")
        for reason, names in sorted(self.approximations.items()):
            shown = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
            out.append(f"  approximated ({len(names)}): {reason}: {shown}")
        if self.margins:
            levels = collections.Counter((level or "not given", margin) for _, level, margin in self.margins)
            text = "; ".join(f"{level} {margin * 100:g} % x{count}" for (level, margin), count in sorted(levels.items()))
            out.append(f"  mass margins in the file (reported, not applied: nominal masses imported): {text}")
        for note in self.notes:
            out.append(f"  note: {note}")
        return out


@dataclass
class Plan:
    """A model ready to merge: parts (mesh parts without a mesh index yet),
    point masses, stowed poses by part ``source_id``, the generated mesh
    groups and the summary."""

    parts: list
    equipment: list
    stowed: dict  # {part source_id: (position, rotation) or None}
    groups: dict  # {group name: ObjGroup}
    summary: ImportSummary
    details: dict
    apply_facets: bool = False


def _tidy(value: float, noise: float = 1.0e-9) -> float:
    """Summation noise to zero, and 10 significant digits."""
    if abs(value) < noise:
        return 0.0
    return float(f"{value:.10g}")


def _vec(values) -> list:
    return [_tidy(float(v)) for v in values]


def _angles(r: np.ndarray) -> list:
    """[deg] roll, pitch and yaw of ``r``, tidied (-180 written as 180)."""
    return [180.0 if abs(a + 180.0) < 1e-9 else a for a in (_tidy(a) for a in frames.roll_pitch_yaw_deg(r))]


def safe_name(text: str, fallback: str = "part") -> str:
    """``text`` as a valid model item name: no characters that file names
    refuse, single spaces, at most the name length."""
    cleaned = "".join("-" if (ch in _NAME_FORBIDDEN or ord(ch) < 32 or ord(ch) == 127) else ch for ch in text or "")
    cleaned = " ".join(cleaned.split()).strip(" -") or fallback
    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned += " 1"
    return cleaned[:MAX_NAME_CHARS].strip()


def unique_name(base: str, taken: set) -> str:
    """``base``, or ``base 2``, ``base 3``... the first not in ``taken``
    (which it joins)."""
    name, k = base, 1
    while name in taken:
        k += 1
        suffix = f" {k}"
        name = base[:MAX_NAME_CHARS - len(suffix)].rstrip() + suffix
    taken.add(name)
    return name


def element_masses(model: IdmModel, placement: Placement) -> dict:
    """[kg] ``{element fullId: mass}`` of each enabled element's units."""
    masses = collections.defaultdict(float)
    for unit in placement.units:
        eq = unit.equipment
        masses[unit.element] += eq.manual_mass_kg if eq.manual else sum(s.mass_kg for s in eq.shapes)
        masses[unit.element] += sum(t.propellant_kg for t in unit.tanks)
    return dict(masses)


def _mounted_on(model: IdmModel) -> dict:
    return {e.full_id: e.mounted_on for e in model.elements}


def _reaches(element: str, body: str, mounted: dict) -> bool:
    seen = set()
    while element is not None and element not in seen:
        if element == body:
            return True
        seen.add(element)
        element = mounted.get(element)
    return False


def choose_body(model: IdmModel, placement: Placement, body_element: str | None) -> str:
    """The body element's ``fullId``: the one named, or else the enabled
    element with the most mass among those not mounted on another
    enabled element (ties: the first)."""
    if body_element:
        element = model.element(body_element)
        if element.full_id not in placement.enabled_elements:
            raise IdmError(f"element {element.name!r} is not enabled in this configuration")
        return element.full_id
    if not placement.enabled_elements:
        raise IdmError("no element is enabled in this configuration: nothing to import")
    masses = element_masses(model, placement)
    mounted = _mounted_on(model)
    enabled = set(placement.enabled_elements)
    roots = [e for e in placement.enabled_elements if mounted.get(e) not in enabled] or placement.enabled_elements

    def carried(root):  # the mass on it, its own and its mounted elements'
        return sum(masses.get(e, 0.0) for e in placement.enabled_elements if _reaches(e, root, mounted))

    best = max(roots, key=lambda e: (carried(e), -placement.enabled_elements.index(e)))
    # Prefer the heaviest element of the chosen tree that the others hang on: the tree's root unless it carries
    # nothing of its own (an "orbit" element holding the spacecraft for display).
    while masses.get(best, 0.0) <= 0.0:
        children = [e for e in placement.enabled_elements if mounted.get(e) == best]
        if not children:
            break
        best = max(children, key=lambda e: (carried(e), -placement.enabled_elements.index(e)))
    return best


@dataclass
class _Item:
    """A part or point mass before naming: its source, base name and pose."""

    source_id: str
    base_name: str
    config: object


def _shape_parts(unit, shape, body_unit: np.ndarray, groups: dict, approximations: dict, label: str,
                 point_masses: list) -> list:
    """The parts (and point masses, appended to ``point_masses``) of one
    shape of a placed unit."""
    g = shape.geometry
    eq = unit.equipment
    occurrence = unit.shape_ids.get(shape.full_id) or f"{unit.full_id}_sh.{shape.id}"
    pose = body_unit @ shape.pose
    mass = 0.0 if eq.manual else max(0.0, float(shape.mass_kg))
    if not shape.shown and mass <= 0.0:
        approximations.setdefault("a massless shape only on layers hidden by default (a field of view or another "
                                  "visual aid): left out", []).append(label)
        return []
    color = list(shape.color or eq.color)
    for note in g.notes:
        if g.kind == "point" and g.wire and mass <= 0.0:
            continue
        approximations.setdefault(note, []).append(label)
    parts = []
    if g.kind == "point":
        if mass > 0.0:
            where = pose @ np.append(g.centroid_m, 1.0)
            point_masses.append(_Item(occurrence, f"{label}", MountedEquipmentConfig(
                name="", kind="unit", mount=MountConfig(position_m=_vec(where[:3]), boresight=[0.0, 0.0, 1.0]),
                mass_kg=_tidy(mass), subsystem=unit.subsystem, source_id=occurrence)))
        return parts
    if g.kind in _PRIMITIVES:
        placed = pose @ g.local
        part = ModelPartConfig(name="", shape=g.kind, dimensions_m={k: _tidy(v) for k, v in g.dims.items()},
                               position_b_m=_vec(placed[:3, 3]), rotation_deg=_angles(placed[:3, :3]),
                               color=color, visible=shape.shown, mass_kg=_tidy(mass),
                               distribution="solid" if g.solid else "shell", in_surface_model=False,
                               subsystem=unit.subsystem, source_id=occurrence)
        if g.kind in ("cylinder", "cone", "sphere"):
            part.segments = 32
        parts.append(_Item(occurrence, label, part))
    else:
        distribution = "solid" if g.solid else "shell"
        if g.solid:
            try:
                mp.solid_mesh(g.mesh.welded(), 1.0)
            except mp.MassPropertiesError:
                distribution = "shell"
                approximations.setdefault("the generated solid is not closed: its mass spread over its surface",
                                          []).append(label)
        group = shape.full_id
        if group not in groups:
            groups[group] = ObjGroup(group, g.mesh, tuple(color))
        parts.append(_Item(occurrence, label, ModelPartConfig(
            name="", shape="mesh", mesh_group=group, position_b_m=_vec(pose[:3, 3]),
            rotation_deg=_angles(pose[:3, :3]), color=color, visible=shape.shown, mass_kg=_tidy(mass),
            distribution=distribution, in_surface_model=False, subsystem=unit.subsystem, source_id=occurrence)))
    if g.cavity is not None:
        for fill in unit.tanks:
            if fill.shape_full_id != shape.full_id:
                continue
            group = f"{shape.full_id}_propellant"
            if group not in groups:
                groups[group] = ObjGroup(group, g.cavity, (0.9, 0.6, 0.2))
            parts.append(_Item(f"{occurrence}_propellant", f"{label} propellant", ModelPartConfig(
                name="", shape="mesh", mesh_group=group, position_b_m=_vec(pose[:3, 3]),
                rotation_deg=_angles(pose[:3, :3]), color=[0.9, 0.6, 0.2], visible=False,
                mass_kg=_tidy(max(0.0, fill.propellant_kg)), distribution="solid", in_surface_model=False,
                subsystem=unit.subsystem, source_id=f"{occurrence}_propellant")))
    return parts


def _items(model: IdmModel, placement: Placement, body: str, approximations: dict, margins: list, groups: dict):
    """Every part and point mass of the elements carried by ``body``."""
    mounted = _mounted_on(model)
    body_inverse = frames.inverse(placement.element_frames[body])
    parts, points = [], []
    margin_seen = set()
    for unit in placement.units:
        if not _reaches(unit.element, body, mounted):
            continue
        eq = unit.equipment
        body_unit = body_inverse @ unit.frame
        label = safe_name(eq.name, "equipment")
        if eq.full_id not in margin_seen:
            margin_seen.add(eq.full_id)
            if eq.mass_margin:
                margins.append((eq.name, eq.maturity, eq.mass_margin))
        if eq.manual and eq.manual_mass_kg > 0.0:
            where = body_unit @ np.append(eq.manual_cog_m, 1.0)
            points.append(_Item(unit.full_id, label, MountedEquipmentConfig(
                name="", kind="unit", mount=MountConfig(position_m=_vec(where[:3]), boresight=[0.0, 0.0, 1.0]),
                mass_kg=_tidy(eq.manual_mass_kg), subsystem=unit.subsystem, source_id=unit.full_id)))
            if np.any(eq.manual_inertia_kg_m2 != 0.0):
                approximations.setdefault("a manual inertia matrix is reported, not applied (its reference point "
                                          "and axes are not stated)", []).append(label)
        for shape in eq.shapes:
            shape_label = safe_name(f"{eq.name} {shape.name}", "part") if len(eq.shapes) > 1 else label
            parts += _shape_parts(unit, shape, body_unit, groups, approximations, shape_label, points)
    return parts, points


def plan(model: IdmModel, configuration: str | None = None, stowed_configuration: str | None = None,
         body_element: str | None = None, apply_facets: bool = False) -> Plan:
    """Map ``model`` in ``configuration`` (None: the defaults) into parts
    and point masses in the body frame of ``body_element`` (None: chosen,
    :func:`choose_body`); ``stowed_configuration`` (optional) gives the
    stowed poses of the parts that are elsewhere in it."""
    placement = model.place(configuration)
    body = choose_body(model, placement, body_element)
    mounted = _mounted_on(model)
    names = {e.full_id: e.name for e in model.elements}
    included = [e for e in placement.enabled_elements if _reaches(e, body, mounted)]
    left_out = []
    for e in model.elements:
        if e.full_id in included:
            continue
        if e.full_id not in placement.enabled_elements:
            left_out.append((e.name, "not enabled in this configuration"))
        elif _reaches(body, e.full_id, mounted):
            left_out.append((e.name, f"{names[body]} is mounted on it"))
        else:
            left_out.append((e.name, f"not mounted on {names[body]}"))
    approximations, margins, notes, groups = {}, [], list(model.notes) + list(placement.notes), {}
    parts, points = _items(model, placement, body, approximations, margins, groups)
    stowed: dict = {}
    stowed_label = ""
    if stowed_configuration:
        other = model.place(stowed_configuration)
        stowed_label = _label(other.configuration)
        if body not in other.enabled_elements:
            raise IdmError(f"element {names[body]!r} is not enabled in the stowed configuration {stowed_label}")
        other_parts, other_points = _items(model, other, body, {}, [], dict(groups))
        poses = {item.source_id: item.config for item in other_parts}
        moved_points = 0
        point_places = {item.source_id: item.config.mount.position_m for item in other_points}
        for item in points:
            if item.source_id in point_places and point_places[item.source_id] != item.config.mount.position_m:
                moved_points += 1
        for item in parts:
            there = poses.get(item.source_id)
            if there is None:
                notes.append(f"{item.base_name} is not in the stowed configuration; it keeps its deployed place there")
                continue
            here = item.config
            if there.position_b_m != here.position_b_m or there.rotation_deg != here.rotation_deg:
                stowed[item.source_id] = (there.position_b_m, there.rotation_deg)
        if moved_points:
            notes.append(f"{moved_points} point mass(es) move in the stowed configuration; the stowed mass properties "
                         "keep them at their deployed place")
    summary = ImportSummary(str(model.path), model.sha256, model.version, model.project,
                            _label(placement.configuration), stowed_label, names[body],
                            [names[e] for e in included], left_out, approximations=approximations, margins=margins,
                            notes=notes)
    summary.parts = len(parts)
    summary.equipment = len(points)
    summary.meshes = len(groups)
    summary.mass_kg = _tidy(sum(i.config.mass_kg for i in parts + points))
    summary.propellant_kg = _tidy(sum(i.config.mass_kg for i in parts if i.source_id.endswith("_propellant")))
    details = {"model_version": model.version, "configuration": summary.configuration,
               "body_element": names[body], "elements": ", ".join(summary.elements)}
    if stowed_label:
        details["stowed_configuration"] = stowed_label
    if model.last_modification:
        details["model_last_modification"] = model.last_modification
    return Plan(parts, points, stowed, groups, summary, details, apply_facets)


def _label(configuration) -> str:
    if configuration is None:
        return "default values (no saved configuration)"
    return f"{configuration.id} ({configuration.name})" if configuration.name != configuration.id \
        else configuration.id


# -- merging into a scenario ------------------------------------------------

_PART_GROUPS = {
    "geometry": lambda where, part: _part_geometry(where, part),
    "mass": lambda where, part: {f"{where}.mass_kg": part.mass_kg, f"{where}.distribution": part.distribution},
    "position": lambda where, part: {f"{where}.position_b_m[{k}]": v for k, v in enumerate(part.position_b_m)},
    "rotation": lambda where, part: {f"{where}.rotation_deg[{k}]": v for k, v in enumerate(part.rotation_deg)},
}


def _part_geometry(where: str, part) -> dict:
    values = {f"{where}.shape": part.shape}
    values.update({f"{where}.dimensions_m.{k}": v for k, v in part.dimensions_m.items()})
    if part.shape == "mesh":
        values[f"{where}.mesh_group"] = part.mesh_group
    return values


def _set_part_group(part, name: str, new) -> None:
    if name == "geometry":
        part.shape, part.dimensions_m = new.shape, dict(new.dimensions_m)
        part.mesh_group, part.mesh_index = new.mesh_group, new.mesh_index
        part.segments = new.segments
    elif name == "mass":
        part.mass_kg, part.distribution = new.mass_kg, new.distribution
    elif name == "position":
        part.position_b_m = list(new.position_b_m)
    else:
        part.rotation_deg = list(new.rotation_deg)


def _decide(current: dict, new: dict, previous: dict) -> str:
    """"same", "update" (the current values are the ones imported last
    time) or "keep" (edited since, or never imported)."""
    if current == new:
        return "same"
    if current and all(path in previous for path in current) and all(previous[p] == v for p, v in current.items()):
        return "update"
    return "keep"


def _previous_record(scenario, spacecraft: str) -> ImportRecord | None:
    for record in scenario.imports:
        if record.spacecraft == spacecraft and record.target == TARGET:
            return record
    return None


def _old_groups(model, base_dir: Path, mesh_index: int | None) -> dict:
    if mesh_index is None:
        return {}
    path = Path(model.meshes[mesh_index].path)
    path = path if path.is_absolute() else base_dir / path
    try:
        return {g.name: g for g in read_obj(path).groups}
    except (OSError, ObjError):
        return {}


def merge(scenario, spacecraft: str, the_plan: Plan, scenario_path, author: str = "",
          orbit_only: bool | None = None) -> ImportSummary:
    """Write ``the_plan`` into ``scenario``'s spacecraft ``spacecraft``
    (module docstring), the meshes into ``models/<spacecraft>_idm.obj``
    beside ``scenario_path``. Returns the summary with what was added,
    updated, kept and gone. The scenario is changed in place; saving it
    is the caller's."""
    from .model3d import model as model3d

    sc = next((s for s in scenario.spacecraft if s.name == spacecraft), None)
    if sc is None:
        raise IdmError(f"no spacecraft {spacecraft!r} in the scenario")
    base_dir = Path(scenario_path).expanduser().resolve().parent
    summary = copy.deepcopy(the_plan.summary)
    previous = _previous_record(scenario, spacecraft)
    previous_values = dict(previous.values) if previous is not None and previous.format == FORMAT else {}
    model = sc.model if sc.model is not None else SpacecraftModelConfig(apply_facets=the_plan.apply_facets)
    if sc.model is None:
        sc.model = model
    if the_plan.apply_facets:
        model.apply_facets = True
    relative = mesh_file_name(spacecraft)
    mesh_index = next((k for k, m in enumerate(model.meshes) if Path(m.path).as_posix() == relative), None)
    old_groups = _old_groups(model, base_dir, mesh_index)
    index = mesh_index if mesh_index is not None else len(model.meshes)

    parts_by_source = {p.source_id: p for p in model.parts if p.source_id}
    taken_parts = {p.name for p in model.parts}
    new_sources = set()
    imported_parts = []
    for item in the_plan.parts:
        new = copy.deepcopy(item.config)
        if new.shape == "mesh":
            new.mesh_index = index
        if the_plan.apply_facets and new.shape in _PRIMITIVES:
            new.in_surface_model = True
        new_sources.add(item.source_id)
        old = parts_by_source.get(item.source_id)
        if old is None:
            new.name = unique_name(item.base_name, taken_parts)
            model.parts.append(new)
            summary.added.append(new.name)
            imported_parts.append(new)
            continue
        new.name = old.name
        imported_parts.append(new)
        where = f"model.parts[{item.source_id}]"
        changed, kept = False, []
        for group, values_of in _PART_GROUPS.items():
            decision = _decide(values_of(where, old), values_of(where, new), previous_values)
            if decision == "update":
                _set_part_group(old, group, new)
                changed = True
            elif decision == "keep":
                kept.append(group)
        if kept:
            summary.kept.append((old.name, ", ".join(kept)))
        if changed:
            summary.updated.append(old.name)
        elif not kept:
            summary.unchanged += 1

    equipment_by_source = {e.source_id: e for e in model.equipment if e.source_id}
    taken_equipment = {e.name for e in model.equipment}
    imported_equipment = []
    for item in the_plan.equipment:
        new = copy.deepcopy(item.config)
        new_sources.add(item.source_id)
        old = equipment_by_source.get(item.source_id)
        if old is None:
            new.name = unique_name(item.base_name, taken_equipment)
            model.equipment.append(new)
            summary.added.append(new.name)
            imported_equipment.append(new)
            continue
        new.name = old.name
        imported_equipment.append(new)
        where = f"model.equipment[{item.source_id}]"
        changed, kept = False, []
        for group, values_of in (("mass", lambda e, w=where: {f"{w}.mass_kg": e.mass_kg}),
                                 ("position", lambda e, w=where: {f"{w}.mount.position_m[{k}]": v
                                                                  for k, v in enumerate(e.mount.position_m or [])})):
            decision = _decide(values_of(old), values_of(new), previous_values)
            if decision == "update":
                if group == "mass":
                    old.mass_kg = new.mass_kg
                else:
                    old.mount.position_m = list(new.mount.position_m)
                    old.mount.part = ""
                changed = True
            elif decision == "keep":
                kept.append(group)
        if kept:
            summary.kept.append((old.name, ", ".join(kept)))
        if changed:
            summary.updated.append(old.name)
        elif not kept:
            summary.unchanged += 1

    # Stowed poses of the imported parts.
    name_of = {p.source_id: p.name for p in model.parts if p.source_id}
    poses = {pose.part: pose for pose in model.stowed}
    imported_poses = []
    if the_plan.summary.stowed_configuration or any(k.startswith("model.stowed[") for k in previous_values):
        for source_id in sorted(set(name_of) & new_sources):
            name = name_of[source_id]
            where = f"model.stowed[{source_id}]"
            pose = poses.get(name)
            target = the_plan.stowed.get(source_id)

            def values_of(p, w=where):
                if p is None:
                    return {}
                position, rotation = (p.position_b_m, p.rotation_deg) if isinstance(p, PartPoseConfig) else p
                out = {f"{w}.position_b_m[{k}]": v for k, v in enumerate(position)}
                out.update({f"{w}.rotation_deg[{k}]": v for k, v in enumerate(rotation)})
                return out

            current, new = values_of(pose), values_of(target)
            if target is not None:
                imported_poses.append(PartPoseConfig(name, list(target[0]), list(target[1])))
            if current == new:
                continue
            stale = not current or all(previous_values.get(p) == v for p, v in current.items())
            if stale and (current or target is not None):
                if target is None:
                    model.stowed = [p for p in model.stowed if p.part != name]
                elif pose is None:
                    model.stowed.append(PartPoseConfig(name, list(target[0]), list(target[1])))
                else:
                    pose.position_b_m, pose.rotation_deg = list(target[0]), list(target[1])
                if name not in summary.updated and name not in summary.added:
                    summary.updated.append(name)
            elif not stale:
                summary.kept.append((name, "stowed pose"))

    for p in model.parts:
        if p.source_id and p.source_id not in new_sources:
            summary.gone.append(p.name)
    for e in model.equipment:
        if e.source_id and e.source_id not in new_sources:
            summary.gone.append(e.name)

    # The meshes file: this import's groups, and those parts still on it need.
    groups = dict(the_plan.groups)
    for p in model.parts:
        if p.shape == "mesh" and p.mesh_index == index and p.mesh_group not in groups:
            if p.mesh_group in old_groups:
                groups[p.mesh_group] = old_groups[p.mesh_group]
            else:
                summary.notes.append(f"part {p.name}: its mesh group {p.mesh_group} is no longer available")
    if groups:
        path = base_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write_obj(path, [groups[name] for name in sorted(groups)])
        mesh = ModelMeshConfig(relative, model3d.file_sha256(path), "m", "z")
        if mesh_index is None:
            model.meshes.append(mesh)
        else:
            model.meshes[mesh_index] = mesh

    # The record: the values as this import gives them, by source_id.
    record_model = SpacecraftModelConfig(parts=imported_parts, equipment=imported_equipment, stowed=imported_poses)
    put_import(scenario, ImportRecord(spacecraft, TARGET, FORMAT, summary.source, summary.sha256,
                                      model_import_values(record_model),
                                      datetime.now(UTC).replace(microsecond=0).isoformat(), author,
                                      dict(the_plan.details)))
    if orbit_only is None:
        orbit_only = scenario.simulation_mode == "orbit_only"
    derived = model3d.derive(model, base_dir)
    for message in derived.errors:
        summary.notes.append(f"3D model: {message}")
    model3d.apply(sc, derived, orbit_only=orbit_only)
    return summary


def gone_items(scenario) -> list:
    """``(spacecraft, item name, source)`` of each imported part or point
    mass that its file no longer has (a re-import flagged it, and it is
    still in the model)."""
    found = []
    for record in scenario.imports:
        if record.target != TARGET:
            continue
        sc = next((s for s in scenario.spacecraft if s.name == record.spacecraft), None)
        if sc is None or sc.model is None:
            continue
        keys = set(record.values)
        for item, kind in [(p, "parts") for p in sc.model.parts] + [(e, "equipment") for e in sc.model.equipment]:
            if item.source_id and not any(k.startswith(f"model.{kind}[{item.source_id}].") for k in keys):
                found.append((sc.name, item.name, record.source))
    return found
