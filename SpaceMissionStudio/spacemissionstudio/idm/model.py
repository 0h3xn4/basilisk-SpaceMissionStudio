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
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""An IDM-CIC model, typed, and placed in one of its configurations.

:func:`load` reads a ``.idm`` file into an :class:`IdmModel`: its
configurations, elements, equipment and their shapes, in SI units.
:meth:`IdmModel.place` then finds, for one configuration, every unit the
spacecraft physically holds (the equipment instances of each element's
subsystems, and the equipment occurrences inside assembly instances,
never the templates inside an assembly's definition), with its pose in
the model's global frame, its tank fillings and whether it is enabled.
Nothing here knows about scenarios: the mapping layer
(``spacemissionstudio.idm_import``) turns a placement into a 3D model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import archive, frames, graph
from .errors import IdmError
from .shapes import ShapeGeometry, geometry, position_transform
from .values import boolean, color, date, number

#: The model versions the reader was written against; others are read
#: with a warning.
SUPPORTED_VERSIONS = ("3.4", "3.5")
UNIT_INSTANCES = ("EquipmentInstance", "AssemblyInstance")
UNIT_OCCURRENCES = ("EquipmentOccurrence", "AssemblyOccurrence")
MASS_TYPES = ("Total", "Area", "Volume")


@dataclass
class Configuration:
    """A saved configuration: its ``fullId``, name and enabled elements."""

    id: str
    full_id: str
    name: str
    enabled_elements: list


@dataclass
class ShapeDef:
    """One shape of an equipment: its geometry, its pose in the
    equipment's frame and its mass definition."""

    id: str
    full_id: str
    name: str
    geometry: ShapeGeometry
    pose: np.ndarray
    mass_type: str
    mass_total_kg: float
    mass_per_m2: float  # [kg/m^2]
    mass_per_m3: float  # [kg/m^3]
    color: tuple | None = None
    #: False when every layer the shape is on is hidden by default (a
    #: field of view or another visual aid).
    shown: bool = True

    @property
    def mass_kg(self) -> float:
        """[kg] The shape's mass from its mass definition: the total, or the
        area or volume of its geometry times the density."""
        if self.mass_type == "Area":
            return self.mass_per_m2 * self.geometry.area_m2
        if self.mass_type == "Volume":
            return self.mass_per_m3 * self.geometry.volume_m3
        return self.mass_total_kg


@dataclass
class Equipment:
    """An equipment definition: name, subsystem, colour, its mass
    properties' origin (``FromGeometry`` or ``ManualInput``) and manual
    values, its margin and maturity level, and its shapes."""

    id: str
    full_id: str
    name: str
    subsystem: str
    color: tuple
    mci_origin: str
    manual_mass_kg: float
    manual_cog_m: np.ndarray
    manual_inertia_kg_m2: np.ndarray
    mass_margin: float  # [-] fraction
    maturity: str
    shapes: list
    node: graph.Node = field(repr=False, default=None)

    @property
    def manual(self) -> bool:
        return self.mci_origin == "ManualInput"


@dataclass
class TankFill:
    """A tank shape of a placed unit and its filling in the configuration."""

    shape_full_id: str
    content_full_id: str
    fraction: float  # [-]
    capacity_kg: float  # [kg]

    @property
    def propellant_kg(self) -> float:
        return self.fraction * self.capacity_kg


@dataclass
class PlacedUnit:
    """An equipment instance or occurrence in a configuration: its
    ``fullId``, equipment, element and subsystem, its pose in the global
    frame and the ``fullId`` of each of its shapes' occurrence."""

    full_id: str
    equipment: Equipment
    element: str  # the element's fullId
    subsystem: str
    frame: np.ndarray
    shape_ids: dict  # {shape fullId: shape occurrence fullId}
    tanks: list


@dataclass
class Element:
    """An element (a spacecraft module, a launcher adapter, ...): its root
    coordinate system and the element it is mounted on (None when free)."""

    id: str
    full_id: str
    name: str
    root_cs: str
    mounted_on: str | None


@dataclass
class Placement:
    """The units of a configuration (``configuration`` None: the defaults)."""

    configuration: Configuration | None
    units: list
    enabled_elements: list
    element_frames: dict  # {element fullId: 4 x 4 root frame in the global frame}
    notes: list


@dataclass
class IdmModel:
    """A read ``.idm`` file (module docstring)."""

    path: Path
    sha256: str
    version: str
    project: str
    last_modification: str
    configurations: list
    elements: list
    equipment: dict  # {fullId: Equipment}
    graph: graph.Graph = field(repr=False)
    entries: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    shown_layers: dict = field(default_factory=dict)  # {layer fullId: shown by default}

    def configuration(self, key: str | None) -> Configuration | None:
        """The configuration with id, ``fullId`` or name ``key`` (None: none)."""
        if key is None or key == "":
            return None
        for c in self.configurations:
            if key in (c.id, c.full_id, c.name):
                return c
        names = ", ".join(f"{c.id} ({c.name})" for c in self.configurations) or "none"
        raise IdmError(f"the model has no configuration {key!r}; it has {names}")

    def element(self, key: str) -> Element:
        """The element with id, ``fullId`` or name ``key``."""
        for e in self.elements:
            if key in (e.id, e.full_id, e.name):
                return e
        names = ", ".join(f"{e.id} ({e.name})" for e in self.elements) or "none"
        raise IdmError(f"the model has no element {key!r}; it has {names}")

    def place(self, configuration: str | None = None) -> Placement:
        """Every enabled unit in ``configuration`` (id, ``fullId`` or name;
        None for the defaults) with its global pose."""
        return _Placer(self, self.configuration(configuration)).run()


def load(path) -> IdmModel:
    """Read the ``.idm`` file at ``path`` (see the module docstring)."""
    opened = archive.read(path)
    g = graph.parse(opened.model_xml)
    return _build(opened, g)


def _system(g: graph.Graph) -> graph.Node:
    for data in g.root.many("IdmData"):
        if data.tag == "MainSystem":
            return data
    raise IdmError("model.xml has no MainSystem: not an IDM-CIC model")


def _build(opened: archive.IdmArchive, g: graph.Graph) -> IdmModel:
    system = _system(g)
    notes = []
    version = g.version
    if not any(version == v or version.startswith(v + ".") for v in SUPPORTED_VERSIONS):
        notes.append(f"model version {version or 'not given'}: the reader was written for versions "
                     f"{', '.join(SUPPORTED_VERSIONS)}; check the result")
    if g.duplicates:
        notes.append(f"{g.duplicates} object(s) repeat an identifier already used; the first of each was used")
    configurations = [Configuration(c.id, c.full_id, c.text("name", c.id) or c.id, c.ref_list("enabledElements"))
                      for c in system.many("configurations")]
    elements = []
    equipment = {}
    shown_layers = {layer.full_id: boolean(layer.text("isSelectedByDefault"), f"{layer.full_id}.isSelectedByDefault",
                                           default=True) for layer in system.many("layers")}
    for e in system.many("elements"):
        root = _root_cs(e, g)
        mounted = None
        if root is not None:
            parent = root.ref("parentCoordinateSystem")
            if parent:
                mounted = _element_of(parent)
        elements.append(Element(e.id, e.full_id, e.text("name", e.id) or e.id,
                                root.full_id if root is not None else "", mounted))
        for related in e.many("relatedSubsystems"):
            subsystem = g.find(related.ref("subsystem"))
            subsystem_name = (subsystem.text("name") if subsystem is not None else None) or related.id
            for unit in related.many("units"):
                for eq in _equipment_nodes(unit):
                    if eq.full_id not in equipment:
                        equipment[eq.full_id] = _equipment(eq, subsystem_name, shown_layers)
    return IdmModel(opened.path, opened.sha256, version, system.text("projectName", "") or "",
                    date(system.text("lastModification")), configurations, elements, equipment, g,
                    opened.entries, notes, shown_layers)


def _equipment_nodes(unit: graph.Node):
    if unit.tag == "Equipment":
        yield unit


def _element_of(full_id: str) -> str:
    """The element ``fullId`` (``el.N``) an object's ``fullId`` lies in."""
    return full_id.split("_", 1)[0]


def _root_cs(element: graph.Node, g: graph.Graph) -> graph.Node | None:
    """The element's root coordinate system: the first of its own whose
    parent is not one of the element's."""
    own = element.many("coordinateSystems")
    ids = {cs.full_id for cs in own}
    for cs in own:
        parent = cs.ref("parentCoordinateSystem")
        if not parent or parent not in ids:
            return cs
    return own[0] if own else None


def _shown(layers: list, shown_layers: dict) -> bool:
    """Whether a shape on ``layers`` is shown by default: when it is on no
    layer, or on one shown by default."""
    return not layers or any(shown_layers.get(layer, True) for layer in layers)


def _vector(node: graph.Node | None, where: str) -> np.ndarray:
    if node is None:
        return np.zeros(3)
    return np.array([number(node.text(axis), f"{where}.{axis}", default=0.0) for axis in "xyz"])


def _matrix(node: graph.Node | None, where: str) -> np.ndarray:
    if node is None:
        return np.zeros((3, 3))
    return np.array([[number(node.text(a + b), f"{where}.{a + b}", default=0.0) for b in "xyz"] for a in "xyz"])


def _equipment(eq: graph.Node, subsystem: str, shown_layers: dict | None = None) -> Equipment:
    where = eq.full_id
    shapes = []
    eq_color = color(eq.text("color"))
    for shape in eq.many("shapes"):
        definition = shape.one("shapeDefinition")
        if definition is None:
            continue
        mass = shape.one("massDefinition")
        mass_type = (mass.text("massType") if mass is not None else "Total") or "Total"
        if mass_type not in MASS_TYPES:
            raise IdmError(f"{shape.full_id}: mass type {mass_type!r} is not one of {', '.join(MASS_TYPES)}")

        def read(name, mass=mass, shape=shape):
            return number(mass.text(name) if mass is not None else None, f"{shape.full_id}.{name}", default=0.0)

        shapes.append(ShapeDef(shape.id, shape.full_id, shape.text("name") or definition.tag,
                               geometry(definition, shape.full_id),
                               position_transform(shape.one("position"), f"{shape.full_id}.position"),
                               mass_type, read("massTotal"), read("massPerSquareMeter"), read("massPerCubeMeter"),
                               color(shape.text("color")) if shape.text("color") else None,
                               _shown(shape.ref_list("layers"), shown_layers or {})))
    return Equipment(eq.id, eq.full_id, eq.text("name", eq.id) or eq.id, subsystem, eq_color,
                     eq.text("mciDataOrigin", "FromGeometry") or "FromGeometry",
                     number(eq.text("manualMass"), f"{where}.manualMass", default=0.0),
                     _vector(eq.one("manualCog"), f"{where}.manualCog"),
                     _matrix(eq.one("manualInertiaMatrix"), f"{where}.manualInertiaMatrix"),
                     number(eq.text("massMargin"), f"{where}.massMargin", default=0.0),
                     eq.text("massMaturityLevel", "") or "", shapes, eq)


class _Placer:
    """Walks the model's physical units for one configuration."""

    def __init__(self, model: IdmModel, configuration: Configuration | None) -> None:
        self.model = model
        self.g = model.graph
        self.cfg = configuration
        self.frames: dict = {}
        self.notes: list = []
        self._busy: set = set()

    # -- configuration values
    def _value(self, holder: graph.Node, collection: str, field_name: str, default_field: str, where: str) -> float:
        if self.cfg is not None:
            for value in holder.many(collection):
                if value.ref("configuration") == self.cfg.full_id:
                    return number(value.text(field_name), f"{value.full_id}.{field_name}", default=0.0)
        return number(holder.text(default_field), f"{where}.{default_field}", default=0.0)

    def enabled(self, unit: graph.Node) -> bool:
        """Whether a unit definition is in the configuration."""
        if not boolean(unit.text("isOptional"), f"{unit.full_id}.isOptional", default=False):
            return True
        if self.cfg is not None:
            for link in unit.many("optionalUnitLinks"):
                if link.ref("configuration") == self.cfg.full_id:
                    return boolean(link.text("enabled"), f"{link.full_id}.enabled", default=True)
        return boolean(unit.text("defaultEnabledValue"), f"{unit.full_id}.defaultEnabledValue", default=True)

    # -- poses
    def frame(self, node: graph.Node) -> np.ndarray:
        """The 4 x 4 pose of a unit or coordinate system in the global frame."""
        key = id(node)
        if key in self.frames:
            return self.frames[key]
        if key in self._busy:
            raise IdmError(f"{node.full_id}: its coordinate systems form a loop")
        self._busy.add(key)
        try:
            result = self._frame(node)
        finally:
            self._busy.discard(key)
        self.frames[key] = result
        return result

    def _parent(self, node: graph.Node) -> np.ndarray | None:
        parent = self.g.follow(node, "parentCoordinateSystem")
        return self.frame(parent) if parent is not None else None

    def _frame(self, node: graph.Node) -> np.ndarray:
        tag = node.tag
        if tag in UNIT_INSTANCES or tag in UNIT_OCCURRENCES:
            base = self._parent(node)
            return (base if base is not None else frames.identity()) @ position_transform(
                self._unit_position(node), f"{node.full_id}.position")
        if tag == "CoordinateSystemDefinition":
            base = self._parent(node)
            pose = position_transform(node.one("position"), f"{node.full_id}.position")
            return (base if base is not None else frames.identity()) @ pose @ self._articulation(node, node)
        if tag == "CoordinateSystem":
            definition = self._definition(node)
            base = self._parent(node)
            if base is None:
                owner = node.owner
                base = self.frame(owner) if owner is not None and owner.tag != "Element" else frames.identity()
            pose = position_transform(definition.one("position"), f"{definition.full_id}.position")
            return base @ pose @ self._articulation(node, definition)
        raise IdmError(f"{node.full_id or tag}: a {tag} cannot be a coordinate system")

    def _unit_position(self, node: graph.Node) -> graph.Node | None:
        seen = 0
        while node is not None and seen < 64:
            position = node.one("position")
            if position is not None:
                return position
            node = self.g.follow(node, "originOccurrence")
            seen += 1
        return None

    def _definition(self, cs: graph.Node) -> graph.Node:
        node, seen = cs, 0
        while node.tag != "CoordinateSystemDefinition":
            origin = self.g.follow(node, "originCoordinateSystem")
            if origin is None or seen > 64:
                raise IdmError(f"{cs.full_id}: a coordinate system copy without its definition")
            node, seen = origin, seen + 1
        return node

    def _articulation(self, cs: graph.Node, definition: graph.Node) -> np.ndarray:
        defined = definition.one("articulation")
        if defined is None:
            return frames.identity()
        kind = "rotation" if "Rotation" in defined.tag else "translation"
        axis = defined.text("axis", "Z") or "Z"
        node, holder, seen = cs, None, 0
        while node is not None and seen < 64:  # the copy's own value first, then its origin's
            holder = node.one("articulation")
            if holder is not None:
                break
            node = self.g.follow(node, "originCoordinateSystem") if node.tag == "CoordinateSystem" else None
            seen += 1
        holder = holder or defined
        value = self._value(holder, "articulationValues", "value", "defaultValue", holder.full_id or cs.full_id)
        return frames.articulation(kind, axis, value)

    # -- the walk
    def run(self) -> Placement:
        system = _system(self.g)
        enabled_ids = set(self.cfg.enabled_elements) if self.cfg is not None else None
        units, enabled, element_frames = [], [], {}
        for element in system.many("elements"):
            if enabled_ids is not None and element.full_id not in enabled_ids:
                continue
            enabled.append(element.full_id)
            root = _root_cs(element, self.g)
            element_frames[element.full_id] = self.frame(root) if root is not None else frames.identity()
            for related in element.many("relatedSubsystems"):
                subsystem = self.g.find(related.ref("subsystem"))
                name = (subsystem.text("name") if subsystem is not None else None) or related.id
                for node in related.many("unitInstances"):
                    self._walk(node, element.full_id, name, units)
        return Placement(self.cfg, units, enabled, element_frames, self.notes)

    def _walk(self, node: graph.Node, element: str, subsystem: str, units: list) -> None:
        unit = self.g.follow(node, "unit")
        if unit is None:
            self.notes.append(f"{node.full_id}: an instance without its unit was left out")
            return
        if not self.enabled(unit):
            return
        if node.tag in ("AssemblyInstance", "AssemblyOccurrence"):
            for child in node.many("unitOccurrences"):
                self._walk(child, element, subsystem, units)
            return
        if node.tag not in ("EquipmentInstance", "EquipmentOccurrence"):
            return
        equipment = self.model.equipment.get(unit.full_id)
        if equipment is None:
            equipment = self.model.equipment[unit.full_id] = _equipment(unit, subsystem, self.model.shown_layers)
        shape_ids = {occ.ref("shape"): occ.full_id for occ in node.many("shapeOccurrences") if occ.ref("shape")}
        units.append(PlacedUnit(node.full_id, equipment, element, subsystem, self.frame(node), shape_ids,
                                self._tanks(node, equipment)))

    def _tanks(self, node: graph.Node, equipment: Equipment) -> list:
        tank_shapes = {s.full_id: s for s in equipment.shapes if s.geometry.object_type == "Tank"}
        if not tank_shapes:
            return []
        holder, seen = node, 0
        while holder is not None and not holder.many("tankContents") and seen < 64:
            holder = self.g.follow(holder, "originOccurrence")
            seen += 1
        contents = holder.many("tankContents") if holder is not None else []
        fills = []
        for content in contents:
            tank = self.g.find(content.ref("tank"))
            shape = tank.owner if tank is not None else None
            if shape is None or shape.full_id not in tank_shapes:
                continue
            fraction = self._value(content, "tankContentValues", "fillingPercentage", "defaultFillingPercentage",
                                   content.full_id)
            capacity = number(tank.text("capacity"), f"{tank.full_id}.capacity", default=0.0)
            fills.append(TankFill(shape.full_id, content.full_id, fraction, capacity))
        missing = set(tank_shapes) - {f.shape_full_id for f in fills}
        for shape_id in sorted(missing):
            self.notes.append(f"{node.full_id}: tank {shape_id} has no filling; taken as empty")
        return fills
