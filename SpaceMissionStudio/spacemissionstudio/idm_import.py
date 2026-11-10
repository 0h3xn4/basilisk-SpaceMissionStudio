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
import dataclasses
import math
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


#: Where the origin of the body frame (body point B) is put (decision IDM-31):
#: the body element's own frame, as in IDM-CIC, or the centre of gravity.
ORIGINS = ("element", "cog")
ORIGIN_LABELS = {"element": "the body element's frame", "cog": "the centre of gravity"}


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
    devices: list = field(default_factory=list)  # (equipment name, kind label, product or "") found by name
    devices_added: list = field(default_factory=list)  # device names added to the spacecraft
    devices_skipped: list = field(default_factory=list)  # (equipment name, why)
    power_modes: list = field(default_factory=list)  # (system mode name, total [W], duty cycle [-])
    power_average_w: float | None = None  # [W] duty-cycle average, when the duty cycles add up to one
    panels: tuple = ()  # (solar array panels, total area [m^2], normal lines, the largest group's (+) normal)
    power_set: list = field(default_factory=list)  # what the import set in the power budget, as text
    properties: list = field(default_factory=list)  # (name, value type, kind labels, values) on the devices found
    origin: str = ""  # one of ORIGINS, set by merge
    origin_m: list = field(default_factory=list)  # [m] the origin (B) in the body element's frame, set by merge
    origin_moved_m: list = field(default_factory=list)  # [m] how far B moved in this import ([] for not at all)
    origin_moved: list = field(default_factory=list)  # what moved with it, as text
    center_of_mass_m: list = field(default_factory=list)  # [m] from B after the import

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
            distinct = list(dict.fromkeys(names))  # one name per item, however many times it occurs
            shown = ", ".join(distinct[:3]) + (f" and {len(distinct) - 3} more" if len(distinct) > 3 else "")
            out.append(f"  approximated ({len(names)}): {reason}: {shown}")
        if self.margins:
            levels = collections.Counter((level or "not given", margin) for _, level, margin in self.margins)
            text = "; ".join(f"{level} {margin * 100:g} % x{count}" for (level, margin), count in sorted(levels.items()))
            out.append(f"  mass margins in the file (reported, not applied: nominal masses imported): {text}")
        if self.devices:
            out.append(f"  devices found by name ({len(self.devices)}): "
                       + "; ".join(f"{name} ({label}{', ' + product if product else ''})"
                                   for name, label, product in self.devices))
        if self.devices_added:
            out.append(f"  devices added to the spacecraft ({len(self.devices_added)}): {', '.join(self.devices_added)}")
        if self.origin:
            where = ", ".join(f"{v:.6g}" for v in self.origin_m)
            out.append(f"  origin of the body frame: {ORIGIN_LABELS[self.origin]}, at [{where}] m in "
                       f"{self.body_element}'s frame"
                       + (f"; the centre of gravity is [{', '.join(f'{v:.4g}' for v in self.center_of_mass_m)}] m "
                          "from it" if self.center_of_mass_m else ""))
        if self.origin_moved_m:
            out.append(f"  origin moved by [{', '.join(f'{v:.6g}' for v in self.origin_moved_m)}] m: "
                       + (", ".join(self.origin_moved) or "nothing else to move"))
        for name, why in self.devices_skipped:
            out.append(f"    device not added: {name}: {why}")
        if self.power_modes:
            out.append("  system modes (power of the imported units): "
                       + "; ".join(f"{name} {total:.6g} W (duty cycle {duty:g})" for name, total, duty in self.power_modes)
                       + (f"; duty-cycle average {self.power_average_w:.6g} W" if self.power_average_w is not None
                          else "; no duty-cycle average (the duty cycles do not add up to one)"))
        if self.panels:
            count, area, lines, normal = self.panels
            out.append(f"  solar array panels: {count}, {area:.6g} m^2 in all"
                       + (f", along {lines} different normal lines (the power model takes the largest group)"
                          if lines > 1 else "")
                       + f"; normal line {normal} in the body frame (+), or its opposite (-)")
        for text in self.power_set:
            out.append(f"  power budget: {text}")
        if self.properties:
            out.append(f"  properties of the devices found ({len(self.properties)}): "
                       + "; ".join(f"{name} ({value_type}) on {', '.join(kinds)}: "
                                   + (", ".join(values[:3]) + (" ..." if len(values) > 3 else "") if values
                                      else "no value")
                                   for name, value_type, kinds, values in self.properties))
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
    devices: list = field(default_factory=list)  # idm_devices.DeviceFinding, found by name
    power: PowerPlan | None = None
    mappings: list = field(default_factory=list)  # idm_properties.Mapping, set by set_mappings
    #: [m] The point of the body element's frame its positions are measured
    #: from: the origin B the last merge put (:func:`plan` gives them from
    #: the element frame's own origin).
    origin_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])


def recorded_origin(record) -> tuple[str, list]:
    """``(origin, offset [m])`` an earlier import (its model record) put the
    body frame's origin at: one of :data:`ORIGINS` and the origin's place in
    the body element's frame; ("element", zeros) when it says none."""
    if record is None:
        return "element", [0.0, 0.0, 0.0]
    origin = record.details.get("origin", "element")
    try:
        offset = [float(v) for v in record.details.get("origin_offset_m", "0, 0, 0").split(",")]
    except ValueError:
        offset = []
    if origin not in ORIGINS or len(offset) != 3 or not all(math.isfinite(v) for v in offset):
        return "element", [0.0, 0.0, 0.0]
    return origin, offset


def shift_plan(the_plan: Plan, d) -> None:
    """Measure ``the_plan``'s positions from the point ``d`` [m] (given from
    where they are measured now): its parts, point masses, stowed poses and
    devices."""
    d = np.asarray(d, dtype=float).reshape(3)
    if not np.any(d):
        return
    for item in the_plan.parts:
        item.config.position_b_m = _vec(np.asarray(item.config.position_b_m) - d)
    for item in the_plan.equipment:
        item.config.mount.position_m = _vec(np.asarray(item.config.mount.position_m) - d)
    the_plan.stowed = {source: (None if pose is None else (_vec(np.asarray(pose[0]) - d), pose[1]))
                       for source, pose in the_plan.stowed.items()}
    for finding in the_plan.devices:
        finding.position_m = _vec(np.asarray(finding.position_m) - d)
        if finding.axis_origin_m is not None:  # a thruster's plume start (decision IDM-32)
            finding.axis_origin_m = _vec(np.asarray(finding.axis_origin_m) - d)
    the_plan.origin_m = _vec(np.asarray(the_plan.origin_m) + d)


def set_mappings(the_plan: Plan, mappings) -> None:
    """Read the properties named in ``mappings`` (``idm_properties.Mapping``)
    for the devices and the battery of ``the_plan``, and keep the mapping in
    its record (a ValueError when the mapping is not valid)."""
    from .idm_properties import check_mappings, mapping_text

    mappings = list(mappings)
    check_mappings(mappings)
    the_plan.mappings = mappings
    if mappings:
        the_plan.details["property_map"] = mapping_text(mappings)
    else:
        the_plan.details.pop("property_map", None)


def recorded_mappings(record) -> list:
    """The property mapping an earlier import (its model record) used, or []."""
    from .idm_properties import parse_mappings_text

    if record is None:
        return []
    try:
        return parse_mappings_text(record.details.get("property_map", ""))
    except ValueError:
        return []  # a mapping this version no longer takes is not reused


@dataclass
class PowerPlan:
    """What an IDM-CIC model says of the power budget: the power of the
    imported units in each system mode (``idm.power.ModePower``), the
    duty-cycle average [W] (None unless the duty cycles add up to one), and
    the solar array panels (``idm.power.Panel``) and their groups by normal
    line (``idm.power.panel_groups``, largest area first)."""

    modes: list
    average_w: float | None
    panels: list
    groups: list


@dataclass
class PowerChoice:
    """What to set in the spacecraft's power budget: ``bus_load`` the name
    of the system mode whose power is the bus load, or "average" (the
    duty-cycle average), or "" (leave it); ``panels`` whether to set the
    panel area and normal from the largest group of panels; ``normal_sign``
    +1 or -1, which side of the group's normal line carries the cells (the
    file does not say); ``battery`` whether to set the battery capacity from
    the batteries' mapped capacity property (:func:`set_mappings`)."""

    bus_load: str = ""
    panels: bool = False
    normal_sign: int = 1
    battery: bool = False

    @property
    def any(self) -> bool:
        return bool(self.bus_load) or self.panels or self.battery


#: Of a power budget an import creates (the panel area set, none there):
#: the values the file does not give, the spacecraft editor's own for a new
#: power budget (``import.power_defaults`` until they are set).
POWER_DEFAULT_FIELDS = ("panel_efficiency", "battery_capacity_wh", "battery_initial_soc")


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
    from . import idm_devices

    devices = idm_devices.detect(model, placement, body, mounted)
    summary.devices = [(d.equipment, idm_devices.KIND_LABELS[d.kind], d.product) for d in devices]
    from .idm_properties import properties_by_kind

    rows = properties_by_kind((d.kind, d.properties) for d in devices)
    summary.properties = [(name, value_type, sorted(idm_devices.KIND_LABELS[k] for k in kinds), texts)
                          for name, value_type, kinds, texts in rows.values()]
    power_plan = _power_plan(model, placement, body, mounted, devices)
    summary.power_modes = [(p.mode.name, p.total_w, p.mode.duty_cycle) for p in power_plan.modes]
    summary.power_average_w = power_plan.average_w
    if power_plan.panels:
        summary.panels = (len(power_plan.panels), _tidy(sum(p.area_m2 for p in power_plan.panels)),
                          len(power_plan.groups), list(power_plan.groups[0][0]))
    return Plan(parts, points, stowed, groups, summary, details, apply_facets, devices, power_plan)


def _power_plan(model: IdmModel, placement: Placement, body: str, mounted: dict, devices: list) -> PowerPlan:
    """The system modes' power of the imported units, and the panels of
    the solar arrays found (``devices``)."""
    from .idm import power

    units = [u for u in placement.units if _reaches(u.element, body, mounted)]
    modes = power.mode_powers(model, units)
    arrays = {d.source_id for d in devices if d.kind == "solar_array"}
    found = power.panels(placement, placement.element_frames[body], [u for u in units if u.full_id in arrays])
    return PowerPlan(modes, power.duty_cycle_average(modes), found, power.panel_groups(found))


def power_values(the_plan: Plan, choice: PowerChoice) -> dict:
    """``{PowerConfig field: value}`` that ``choice`` sets from
    ``the_plan`` (an IdmError when the choice names what the file does not
    give)."""
    power_plan = the_plan.power
    values = {}
    if choice.bus_load:
        if power_plan is None:
            raise IdmError("the model gives no system modes")
        if choice.bus_load == "average":
            if power_plan.average_w is None:
                raise IdmError("the model's duty cycles do not add up to one: there is no duty-cycle average; "
                               "choose a system mode")
            values["bus_idle_power_w"] = power_plan.average_w
        else:
            mode = next((p for p in power_plan.modes if p.mode.name == choice.bus_load), None)
            if mode is None:
                names = ", ".join(repr(p.mode.name) for p in power_plan.modes) or "none"
                raise IdmError(f"no system mode {choice.bus_load!r} in the model (its system modes: {names})")
            values["bus_idle_power_w"] = mode.total_w
    if choice.panels:
        if power_plan is None or not power_plan.groups:
            raise IdmError("the model has no flat solar array panel to take the area and normal from")
        normal, area, _ = power_plan.groups[0]
        sign = -1.0 if choice.normal_sign < 0 else 1.0
        values["panel_area_m2"] = area
        values["panel_normal_b"] = [0.0 if v == 0.0 else _tidy(sign * v) for v in normal]
    if choice.battery:
        capacity, _ = battery_capacity(the_plan)
        if capacity is None:
            raise IdmError("no battery capacity in the model: map the batteries' capacity property to "
                           "battery.capacity_wh, with its unit")
        values["battery_capacity_wh"] = capacity
    return values


def battery_capacity(the_plan: Plan) -> tuple[float | None, list]:
    """The total capacity [W*h] of the batteries found, from the mapped
    capacity property of each (None when no battery gives one), and how
    each was read."""
    from .idm_properties import mapped_values

    total, read = None, []
    for finding in the_plan.devices:
        if finding.kind != "battery":
            continue
        values, _ = mapped_values("battery", finding.properties, the_plan.mappings)
        for value in values:
            if value.target.param == "capacity_wh":
                total = (total or 0.0) + value.value
                read.append(f"{finding.equipment}: {value.describe()}")
    return (_tidy(total) if total is not None else None), read


def power_details(the_plan: Plan, choice: PowerChoice) -> dict:
    """How each value ``choice`` sets was read, as an import record's details."""
    power_plan = the_plan.power
    details = {}
    if choice.bus_load == "average":
        details["bus_load"] = (f"duty-cycle average of {len(power_plan.modes)} system modes, the power of the "
                               "imported units in each")
    elif choice.bus_load:
        mode = next(p for p in power_plan.modes if p.mode.name == choice.bus_load)
        details["bus_load"] = (f"system mode {mode.mode.name}: the power of {len(mode.units)} imported unit(s) in it"
                               + (f"; {len(mode.unstated)} unit(s) with power modes it does not set counted as 0 W"
                                  if mode.unstated else ""))
    if choice.panels:
        normal, area, members = power_plan.groups[0]
        details["panels"] = (f"{len(members)} solar array panel(s) along one normal line, the largest flat face of "
                             f"each: {', '.join(p.equipment for p in members)}; the side carrying the cells chosen "
                             f"by the user ({'+' if choice.normal_sign >= 0 else '-'})")
        if len(power_plan.groups) > 1:
            details["panels"] += f"; {len(power_plan.groups) - 1} other normal line(s) left out"
    if choice.battery:
        _, read = battery_capacity(the_plan)
        details["battery"] = f"{len(read)} battery unit(s), added up: " + "; ".join(read)
    return details


def apply_power(scenario, spacecraft: str, the_plan: Plan, choice: PowerChoice, author: str = "",
                summary: ImportSummary | None = None) -> dict:
    """Set in ``scenario``'s spacecraft ``spacecraft``'s power budget what
    ``choice`` takes from ``the_plan`` (:func:`power_values`), and record
    it (an import record of target "power"). Without a power budget, one
    is made when the panel area is set, with the spacecraft editor's own
    values for what the file does not give (:data:`POWER_DEFAULT_FIELDS`);
    without one and without the panel area, nothing is set and the summary
    says why. Returns ``{field: value}`` set."""
    from .schema.scenario import DEFAULT_PANEL_EFFICIENCY, PowerConfig, power_import_values

    sc = next((s for s in scenario.spacecraft if s.name == spacecraft), None)
    if sc is None:
        raise IdmError(f"no spacecraft {spacecraft!r} in the scenario")
    if not choice.any:
        return {}
    values = power_values(the_plan, choice)
    details = power_details(the_plan, choice)
    lines = []
    if sc.power is None:
        if "panel_area_m2" not in values:
            if summary is not None:
                summary.power_set.append("not set: the spacecraft has no power budget, and a new one needs the "
                                         "panel area (choose the solar array panels too, or turn its power budget on)")
            return {}
        sc.power = PowerConfig(panel_area_m2=values["panel_area_m2"], panel_efficiency=DEFAULT_PANEL_EFFICIENCY)
        defaults = [name for name in POWER_DEFAULT_FIELDS if name not in values]
        values.update({name: getattr(sc.power, name) for name in defaults})
        if defaults:
            details["defaults"] = ", ".join(defaults)
        lines.append(f"made (it had none); {', '.join(n.replace('_', ' ') for n in defaults)} are the editor's "
                     "values for a new power budget, not the file's: set them")
    for name, value in values.items():
        setattr(sc.power, name, list(value) if isinstance(value, list) else value)
    if "bus_idle_power_w" in values:
        lines.append(f"bus load {values['bus_idle_power_w']:.6g} W ({details['bus_load']})")
    if "panel_area_m2" in values:
        lines.append(f"panel area {values['panel_area_m2']:.6g} m^2, normal {values['panel_normal_b']} in the body "
                     "frame")
    if choice.battery:
        lines.append(f"battery capacity {values['battery_capacity_wh']:.6g} W*h ({details['battery']})")
    previous = next((r for r in scenario.imports if (r.spacecraft, r.target) == (spacecraft, "power")), None)
    record_values = dict(previous.values) if previous is not None else {}
    record_details = dict(previous.details) if previous is not None else {}
    record_values.update(power_import_values(sc, values))
    record_details.update(details)
    put_import(scenario, ImportRecord(spacecraft, "power", FORMAT, the_plan.summary.source, the_plan.summary.sha256,
                                      record_values, datetime.now(UTC).replace(microsecond=0).isoformat(), author,
                                      record_details))
    if summary is not None:
        summary.power_set.extend(lines)
    return values


def unset_power(scenario) -> list[tuple[str, list]]:
    """``(spacecraft, fields)`` of each power budget an IDM-CIC import
    made whose values the file does not give are still the defaults it was
    made with (``import.power_defaults``)."""
    found = []
    for record in getattr(scenario, "imports", []):
        if record.target != "power" or not record.details.get("defaults"):
            continue
        config = next((sc for sc in scenario.spacecraft if sc.name == record.spacecraft), None)
        if config is None or config.power is None:
            continue
        names = record.details["defaults"].split(", ")
        from .schema.scenario import power_import_values

        now = power_import_values(config, names)
        if all(now.get(f"power.{name}") == record.values.get(f"power.{name}") for name in names):
            found.append((record.spacecraft, names))
    return found


def add_devices(scenario, spacecraft: str, the_plan: Plan, choices, author: str = "",
                summary: ImportSummary | None = None):
    """Add the devices of ``the_plan`` chosen in ``choices`` (one
    ``idm_devices.DeviceChoice`` per finding) to ``scenario``'s spacecraft
    ``spacecraft`` (a thruster to its 3D model's equipment, decision
    IDM-32), and record them (an import record of target "devices"). A finding whose unit an earlier import already added a
    device for is left as it is (it may have been edited since). Returns the
    ``idm_devices.DeviceResult``; ``summary``, when given, lists what was
    added and skipped."""
    from . import idm_devices

    sc = next((s for s in scenario.spacecraft if s.name == spacecraft), None)
    if sc is None:
        raise IdmError(f"no spacecraft {spacecraft!r} in the scenario")
    previous = next((r for r in scenario.imports if (r.spacecraft, r.target) == (spacecraft, "devices")), None)
    done = idm_devices.recorded_units(previous)
    findings, kept_choices, skipped = [], [], []
    for finding, choice in zip(the_plan.devices, choices):
        if choice.add and finding.source_id in done:
            skipped.append((finding.equipment, "added by an earlier import: left as it is"))
            continue
        findings.append(finding)
        kept_choices.append(choice)
    taken = {d.name for d in list(sc.sensors) + list(sc.actuators)}
    taken_equipment = {e.name for e in sc.model.equipment} if sc.model is not None else set()
    result = idm_devices.keep_fitting(sc, idm_devices.build_devices(findings, kept_choices, taken,
                                                                    the_plan.mappings, taken_equipment))
    result.skipped[:0] = skipped
    sc.sensors = list(sc.sensors) + result.sensors
    sc.actuators = list(sc.actuators) + result.actuators
    if result.equipment:  # keep_fitting kept them only with a model to carry them
        sc.model.equipment = list(sc.model.equipment) + result.equipment
    if result.values:
        values = dict(previous.values) if previous is not None else {}
        details = dict(previous.details) if previous is not None else {}
        values.update(result.values)
        details.update(result.details)
        put_import(scenario, ImportRecord(spacecraft, "devices", FORMAT, the_plan.summary.source,
                                          the_plan.summary.sha256, values,
                                          datetime.now(UTC).replace(microsecond=0).isoformat(), author, details))
    if summary is not None:
        summary.devices_added = [d.name for d in result.sensors + result.actuators + result.equipment]
        summary.devices_skipped = list(result.skipped)
    return result


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
          orbit_only: bool | None = None, origin: str | None = None) -> ImportSummary:
    """Write ``the_plan`` into ``scenario``'s spacecraft ``spacecraft``
    (module docstring), the meshes into ``models/<spacecraft>_idm.obj``
    beside ``scenario_path``. Returns the summary with what was added,
    updated, kept and gone. The scenario is changed in place, and only
    when the whole import succeeds: if anything fails (the meshes file
    cannot be written, say), the spacecraft and the import records are
    put back as they were, so no part is left naming a mesh file that was
    not written. Saving it is the caller's.

    ``origin`` (one of :data:`ORIGINS`; None: where the last import put
    it, else the element's frame) is where the body frame's origin goes
    (decision IDM-31): moving it moves every position of the spacecraft
    (``model3d.origin.move_origin``), the import records' too, and
    ``the_plan``'s (:func:`shift_plan`), so the devices it adds next are
    measured from it."""
    if origin is not None and origin not in ORIGINS:
        raise IdmError(f"origin {origin!r} must be one of {ORIGINS}")
    sc = next((s for s in scenario.spacecraft if s.name == spacecraft), None)
    if sc is None:
        raise IdmError(f"no spacecraft {spacecraft!r} in the scenario")
    saved_spacecraft, saved_imports = copy.deepcopy(vars(sc)), copy.deepcopy(list(scenario.imports))
    saved_plan = (copy.deepcopy(the_plan.parts), copy.deepcopy(the_plan.equipment), dict(the_plan.stowed),
                  copy.deepcopy(the_plan.devices), list(the_plan.origin_m))
    try:
        return _merge(scenario, sc, spacecraft, the_plan, scenario_path, author, orbit_only, origin)
    except BaseException:
        _restore(sc, saved_spacecraft)
        scenario.imports[:] = saved_imports
        (the_plan.parts, the_plan.equipment, the_plan.stowed, the_plan.devices, the_plan.origin_m) = saved_plan
        raise


def _restore(target, saved: dict) -> None:
    """Put ``target``'s attributes back as ``saved`` (a deep copy of its
    ``vars``), keeping the identity of its model object, which an editor
    may hold."""
    model, saved_model = getattr(target, "model", None), saved.get("model")
    if model is not None and saved_model is not None:
        vars(model).clear()
        vars(model).update(vars(saved_model))
        saved = {**saved, "model": model}
    vars(target).clear()
    vars(target).update(saved)


def _merge(scenario, sc, spacecraft: str, the_plan: Plan, scenario_path, author: str,
           orbit_only: bool | None, origin: str | None) -> ImportSummary:
    """:func:`merge`'s work on spacecraft ``sc``, in place."""
    from .model3d import model as model3d

    base_dir = Path(scenario_path).expanduser().resolve().parent
    summary = copy.deepcopy(the_plan.summary)
    previous = _previous_record(scenario, spacecraft)
    previous_values = dict(previous.values) if previous is not None and previous.format == FORMAT else {}
    # The spacecraft and the last record are measured from where the last
    # import put the origin: the plan is measured from there too.
    previous_origin, previous_offset = recorded_origin(previous if previous is not None
                                                       and previous.format == FORMAT else None)
    shift_plan(the_plan, np.asarray(previous_offset) - np.asarray(the_plan.origin_m))
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
    record_values = model_import_values(record_model)
    if orbit_only is None:
        orbit_only = getattr(scenario, "simulation_mode", "") == "orbit_only"
    derived = model3d.derive(model, base_dir)

    # The origin of the body frame (decision IDM-31).
    chosen = origin or previous_origin
    d = np.zeros(3)
    if chosen == "cog":
        if derived.mass_properties is not None and derived.mass_properties.mass_kg > 0.0:
            # To the micrometre, so that moving there and back gives the
            # same numbers, and an unchanged model re-imports unchanged.
            d = np.round(np.asarray(derived.mass_properties.center_of_mass_m, dtype=float), 6)
        else:
            summary.notes.append("the model has no mass, so it has no centre of gravity: the origin is left "
                                 "where it was")
    else:
        d = -np.asarray(previous_offset, dtype=float)
    if np.linalg.norm(d) > 1.0e-9:
        from .model3d.origin import move_origin, shift_record_values

        summary.origin_moved = move_origin(sc, d)
        summary.origin_moved_m = _vec(d)
        record_values = shift_record_values(record_values, d)
        for k, record in enumerate(scenario.imports):  # the devices this import's model placed before
            if record.spacecraft == spacecraft and record.target != TARGET and record.values:
                scenario.imports[k] = dataclasses.replace(record, values=shift_record_values(record.values, d))
        shift_plan(the_plan, d)
        derived = model3d.derive(model, base_dir)
    offset = _vec(np.asarray(previous_offset, dtype=float) + d)
    details = dict(the_plan.details)
    details["origin"] = chosen
    details["origin_offset_m"] = ", ".join(f"{v:.10g}" for v in offset)
    put_import(scenario, ImportRecord(spacecraft, TARGET, FORMAT, summary.source, summary.sha256, record_values,
                                      datetime.now(UTC).replace(microsecond=0).isoformat(), author, details))
    summary.origin, summary.origin_m = chosen, offset
    if derived.mass_properties is not None and derived.mass_properties.mass_kg > 0.0:
        summary.center_of_mass_m = _vec(derived.mass_properties.center_of_mass_m)
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
