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

"""The power an IDM-CIC model's equipment draws in each of its system
modes (``docs/developer/idm-cic-integration.md``, section 16).

An equipment definition has power modes, each a power and a dissipation.
A system mode (with a duty cycle, the share of the lifetime spent in it)
sets, for each placed unit, which power mode it is in: through the
element mode of the unit's element that the system mode links, else
directly through a mapping between the system mode and the unit. A
mapping without a power mode gives its own custom power. A unit that no
mapping covers in a system mode is reported as not stated there and
counted as drawing nothing.

The power is in watts: the format's description gives no unit, and the
values of the sample models settle it (a reaction wheel's "On" mode is
about 10, a magnetometer's about 1; in kilowatts they would be absurd).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .values import number


@dataclass
class SystemMode:
    """A system mode: its ``fullId``, name and duty cycle [-] (0 to 1)."""

    full_id: str
    name: str
    duty_cycle: float


@dataclass
class ModePower:
    """The power of the units counted in one system mode: the total [W],
    each unit's (name, power [W], power mode name, or "custom"), and the
    units no mapping covers in it."""

    mode: SystemMode
    total_w: float = 0.0  # [W]
    units: list = field(default_factory=list)  # (unit name, power [W], how)
    unstated: list = field(default_factory=list)  # unit names


def system_modes(model) -> list[SystemMode]:
    """The model's system modes, in file order."""
    g = model.graph
    found = []
    for node in g.iter("SystemMode"):
        if not node.full_id or node.text("name") is None:
            continue  # a reference, not the definition
        found.append(SystemMode(node.full_id, node.text("name") or node.id,
                                number(node.text("dutyCycle"), f"{node.full_id}.dutyCycle", 0.0)))
    return found


def _element_modes_of(model) -> dict:
    """``{system mode fullId: {element mode fullId}}`` from both sides of
    the link (a system mode's element modes, an element mode's system
    modes)."""
    g = model.graph
    links: dict = {}
    for node in g.iter("ElementMode"):
        if not node.full_id or node.text("name") is None:
            continue
        for system in node.ref_list("systemModes"):
            links.setdefault(system, set()).add(node.full_id)
    for node in g.iter("SystemMode"):
        if node.full_id and node.text("name") is not None:
            links.setdefault(node.full_id, set()).update(node.ref_list("elementModes"))
    return links


def _mapping_power(g, mapping) -> tuple[float, str]:
    """``(power [W], how)`` of an element-to-equipment or system-to-equipment
    mapping: its power mode's, or its custom power."""
    mode = g.find(mapping.ref("powerMode"))
    if mode is not None:
        return number(mode.text("power"), f"{mode.full_id}.power", 0.0), mode.text("name") or mode.id
    return number(mapping.text("customPower"), f"{mapping.full_id}.customPower", 0.0), "custom"


def mode_powers(model, units) -> list[ModePower]:
    """For each system mode, the power of ``units`` (placed units, e.g. those
    of the imported elements) in it, and the units it does not cover."""
    g = model.graph
    links = _element_modes_of(model)
    result = []
    for mode in system_modes(model):
        element_modes = links.get(mode.full_id, set())
        entry = ModePower(mode)
        for unit in units:
            node = g.find(unit.full_id)
            if node is None:
                continue
            found = None
            for mapping in node.many("elementToEquipmentPowerModes"):
                if mapping.ref("elementMode") in element_modes:
                    found = _mapping_power(g, mapping)
                    break
            if found is None:
                for mapping in node.many("systemToEquipmentPowerModes"):
                    if mapping.ref("systemMode") == mode.full_id:
                        found = _mapping_power(g, mapping)
                        break
            if found is None:
                if unit.equipment.full_id and _has_power_modes(g, unit.equipment.full_id):
                    entry.unstated.append(unit.equipment.name)
                continue
            power, how = found
            entry.units.append((unit.equipment.name, power, how))
            entry.total_w += power
        entry.total_w = float(f"{entry.total_w:.10g}")
        result.append(entry)
    return result


def _has_power_modes(g, equipment_full_id: str) -> bool:
    node = g.find(equipment_full_id)
    return node is not None and bool(node.many("powerModes"))


def duty_cycle_average(powers: list[ModePower]) -> float | None:
    """The lifetime average power [W], the duty-cycle-weighted mean of the
    modes' totals, when the duty cycles add up to one (within 1e-6); None
    otherwise (the share of the lifetime the model does not place is not
    known)."""
    total = sum(p.mode.duty_cycle for p in powers)
    if not powers or abs(total - 1.0) > 1.0e-6:
        return None
    return float(f"{sum(p.mode.duty_cycle * p.total_w for p in powers):.10g}")


#: A box is a flat panel when its thinnest side is at most this share of
#: the next one [-].
FLAT_RATIO = 0.1  # [-]
#: Two panel normals within this angle of one line (either sense) are one
#: panel orientation [deg].
SAME_LINE_DEG = 1.0  # [deg]


@dataclass
class Panel:
    """A flat shape of a solar array unit: the unit's ``fullId`` and
    equipment name, the face area [m^2] and the face's normal line in the
    body frame (a unit vector; the file does not say which side carries
    the cells)."""

    source_id: str
    equipment: str
    area_m2: float  # [m^2]
    normal_b: list


def _flat_face(geometry, pose):
    """``(area [m^2], unit normal in the frame of pose)`` of a flat box or
    a plane surface mesh; None for any other shape."""
    import numpy as np

    if geometry.kind == "box":
        sides = [abs(geometry.dims.get(k, 0.0)) for k in ("x", "y", "z")]
        order = sorted(range(3), key=lambda k: sides[k])
        thin, mid, big = (sides[k] for k in order)
        if mid <= 0.0 or thin > FLAT_RATIO * mid:
            return None
        rotation = (pose @ geometry.local)[:3, :3]
        return mid * big, rotation[:, order[0]]
    if geometry.kind == "mesh" and not geometry.solid and geometry.mesh is not None and geometry.area_m2 > 0.0:
        vertices = np.asarray(geometry.mesh.vertices, dtype=float)
        normal = None
        for a, b, c in np.asarray(geometry.mesh.triangles):
            n = np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a])
            if np.linalg.norm(n) > 1.0e-12:
                normal = n / np.linalg.norm(n)
                break
        if normal is None or np.max(np.abs((vertices - vertices[0]) @ normal)) > 1.0e-9:
            return None  # not a plane
        return geometry.area_m2, pose[:3, :3] @ normal
    return None


def panels(placement, body_frame, units) -> list[Panel]:
    """The flat faces of ``units`` (the solar array units, placed): for
    each unit, its largest flat shape (its other flat shapes are taken as
    layers of the same panel: cover glass, cells, substrate). ``body_frame``
    is the body element's frame in the global frame."""
    from . import frames

    body_inverse = frames.inverse(body_frame)
    found = []
    for unit in units:
        best = None
        for shape in unit.equipment.shapes:
            face = _flat_face(shape.geometry, body_inverse @ unit.frame @ shape.pose)
            if face is not None and (best is None or face[0] > best[0]):
                best = face
        if best is not None:
            area, normal = best
            found.append(Panel(unit.full_id, unit.equipment.name, float(f"{area:.10g}"),
                               [0.0 if abs(v) < 1.0e-9 else float(f"{v:.10g}") for v in normal]))
    return found


def panel_groups(found: list[Panel]) -> list[tuple[list, float, list]]:
    """The panels by normal line, largest total area first: ``(normal_b,
    total area [m^2], panels)``; the normal is the first panel's, and a
    panel facing the other way along it counts too."""
    import math

    import numpy as np

    groups = []
    limit = math.cos(math.radians(SAME_LINE_DEG))
    for panel in found:
        for group in groups:
            if abs(float(np.dot(group[0], panel.normal_b))) >= limit:
                group[2].append(panel)
                break
        else:
            groups.append([panel.normal_b, 0.0, [panel]])
    for group in groups:
        group[1] = float(f"{sum(p.area_m2 for p in group[2]):.10g}")
    return sorted((tuple(g) for g in groups), key=lambda g: -g[1])
