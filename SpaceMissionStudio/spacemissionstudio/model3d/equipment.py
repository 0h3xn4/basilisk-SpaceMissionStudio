#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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
"""Mounted equipment: every sensor, actuator, antenna and item of
``model.equipment`` that has a place on the spacecraft, as one list of
:class:`MountedItem` in the body frame, for the configuration asked for.

A mount (``schema.scenario.MountConfig``) gives only what the definition it
belongs to does not (decision D-03); the rest comes from the definition:

=========================== ============================ ========================
Definition                  Position                     Boresight, field of view
=========================== ============================ ========================
thruster (``actuators``)    ``params.r_B``               ``params.tHat_B`` (the
                                                         plume runs along minus it)
reaction wheel              ``params.rWB_B``             ``params.gsHat_B``
magnetic torque rod         --                           ``params.gtHat_B``
coarse sun sensor           --                           ``params.nHat_B``,
                                                         ``params.fov_deg``
thermal sensor              --                           ``params.nHat_B``
RF antenna (``rf_link``)    --                           ``antenna_boresight_b``
                                                         (else ``comms_pointing``),
                                                         ``antenna_beamwidth_deg``
=========================== ============================ ========================

A mount on a part (``mount.part``) gives its own position and boresight in
the part's frame, and moves with the part: in the stowed configuration it
is where the part's stowed pose takes it. A value taken from the
definition is in the body frame for the deployed configuration and moves
with the part the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import mass_properties as mp
from .geometry import rotation_matrix


@dataclass
class MountedItem:
    """One piece of mounted equipment, in the body frame."""

    name: str
    kind: str  # e.g. "star_tracker", "coarse_sun_sensor", "thruster", "antenna", "solar_cell", "camera", "unit"
    source: str  # where it is defined: "sensors", "actuators", "rf_link" or "equipment"
    part: str  # the part it is mounted on, or ""
    position_b_m: np.ndarray | None  # [m]
    boresight_b: np.ndarray | None  # [-] unit
    field_of_view_deg: float | None = None  # [deg] full cone angle
    exclusion_sun_deg: float | None = None  # [deg]
    exclusion_earth_deg: float | None = None  # [deg]
    exclusion_moon_deg: float | None = None  # [deg]
    earth_atmosphere_km: float | None = None  # [km]
    plume_half_angle_deg: float | None = None  # [deg]
    thrust_n: float | None = None  # [N]
    mass_kg: float = 0.0  # [kg] model.equipment only
    maturity: str = ""
    subsystem: str = ""

    @property
    def has_exclusions(self) -> bool:
        return any(v is not None for v in (self.exclusion_sun_deg, self.exclusion_earth_deg, self.exclusion_moon_deg))


def _unit(vector) -> np.ndarray | None:
    if vector is None:
        return None
    v = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(v))
    return v / norm if norm > 0.0 else None


def part_pose(model, part_name: str, configuration: str):
    """``(R, p)`` of a part in ``configuration`` (``x_B = R x_local + p``),
    or None when the model has no such part."""
    from .model import poses

    part = next((p for p in model.parts if p.name == part_name), None) if model is not None else None
    if part is None:
        return None
    position, rotation_deg = poses(model, configuration).get(part.name, (part.position_b_m, part.rotation_deg))
    return rotation_matrix(rotation_deg), np.asarray(position, dtype=float)


def _place(model, mount, position_default, boresight_default, configuration: str):
    """The body-frame position and boresight of a mount in ``configuration``."""
    position = None if position_default is None else np.asarray(position_default, dtype=float)
    boresight = _unit(boresight_default)
    if mount is not None and mount.part and model is not None:
        deployed = part_pose(model, mount.part, "deployed")
        here = part_pose(model, mount.part, configuration)
        if deployed is not None:
            r_d, p_d = deployed
            r_c, p_c = here
            # Values from the definition: body frame, deployed; move them with the part.
            if position is not None:
                position = r_c @ (r_d.T @ (position - p_d)) + p_c
            if boresight is not None:
                boresight = r_c @ (r_d.T @ boresight)
            # The mount's own values: in the part's frame.
            if mount.position_m is not None:
                position = r_c @ np.asarray(mount.position_m, dtype=float) + p_c
            if mount.boresight is not None:
                boresight = _unit(r_c @ np.asarray(mount.boresight, dtype=float))
            return position, boresight
    if mount is not None:
        if mount.position_m is not None:
            position = np.asarray(mount.position_m, dtype=float)
        if mount.boresight is not None:
            boresight = _unit(mount.boresight)
    return position, boresight


def _angles(mount, fov_default=None) -> dict:
    values = {"field_of_view_deg": fov_default}
    if mount is None:
        return values
    for name in ("field_of_view_deg", "exclusion_sun_deg", "exclusion_earth_deg", "exclusion_moon_deg",
                 "earth_atmosphere_km", "plume_half_angle_deg"):
        value = getattr(mount, name)
        if value is not None:
            values[name] = float(value)
    return values


def mounted_items(sc, configuration: str = "deployed") -> list[MountedItem]:
    """Every sensor, actuator and antenna of spacecraft ``sc`` with a mount
    or a direction of its own, and every item of its model's equipment, in
    the body frame of ``configuration``."""
    model = sc.model
    items: list[MountedItem] = []
    for sensor in sc.sensors:
        mount = getattr(sensor, "mount", None)
        params = sensor.params or {}
        boresight = params.get("nHat_B") if sensor.kind in ("coarse_sun_sensor", "thermal") else None
        fov = params.get("fov_deg") if sensor.kind == "coarse_sun_sensor" else None
        if mount is None and boresight is None:
            continue
        position, direction = _place(model, mount, None, boresight, configuration)
        items.append(MountedItem(sensor.name, sensor.kind, "sensors", mount.part if mount else "", position,
                                 direction, **_angles(mount, None if fov is None else float(fov))))
    for actuator in sc.actuators:
        mount = getattr(actuator, "mount", None)
        params = actuator.params or {}
        position = boresight = None
        thrust = None
        if actuator.kind == "thruster":
            position, boresight = params.get("r_B"), params.get("tHat_B")
            thrust = params.get("MaxThrust")
        elif actuator.kind == "reaction_wheel":
            position, boresight = params.get("rWB_B"), params.get("gsHat_B")
        elif actuator.kind == "magnetic_torque_rod":
            boresight = params.get("gtHat_B")
        if mount is None and actuator.kind != "thruster":
            continue
        placed_position, direction = _place(model, mount, position, boresight, configuration)
        item = MountedItem(actuator.name, actuator.kind, "actuators", mount.part if mount else "", placed_position,
                           direction, **_angles(mount))
        item.thrust_n = None if thrust is None else float(thrust)
        items.append(item)
    if sc.rf_link is not None:
        mount = sc.rf_link.antenna_mount
        boresight = sc.rf_link.antenna_boresight_b
        if boresight is None and sc.comms_pointing is not None:
            boresight = sc.comms_pointing.antenna_boresight_b
        if mount is not None:
            position, direction = _place(model, mount, None, boresight, configuration)
            beam = sc.rf_link.antenna_beamwidth_deg
            items.append(MountedItem("rf antenna", "antenna", "rf_link", mount.part, position, direction,
                                     **_angles(mount, None if beam is None else float(beam))))
    if model is not None:
        for equipment in model.equipment:
            position, direction = _place(model, equipment.mount, None, None, configuration)
            item = MountedItem(equipment.name, equipment.kind, "equipment", equipment.mount.part, position, direction,
                               **_angles(equipment.mount))
            item.thrust_n = equipment.thrust_n
            item.mass_kg = float(equipment.mass_kg)
            item.maturity = equipment.maturity
            item.subsystem = equipment.subsystem
            items.append(item)
    return items


def equipment_point_masses(model, configuration: str = "deployed") -> list[mp.MassProperties]:
    """The model's equipment with a mass, as point masses at their mounts
    (they count in the computed mass properties and the mass budget)."""
    masses = []
    for equipment in getattr(model, "equipment", []):
        if equipment.mass_kg <= 0.0:
            continue
        position, _ = _place(model, equipment.mount, None, None, configuration)
        if position is None:
            continue
        masses.append(mp.MassProperties(float(equipment.mass_kg), np.asarray(position, dtype=float), np.zeros((3, 3))))
    return masses
