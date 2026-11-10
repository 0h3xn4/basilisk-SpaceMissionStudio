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

"""Moving a spacecraft's body point B (the origin of its body frame).

Every position of a spacecraft is measured from B, in body axes. Moving B
to the point ``d`` (given in the present body frame) is a translation:
each position ``p`` becomes ``p - d``. Directions (boresights, spin axes,
normals), rotations and the inertia (about the centre of mass) do not
change, and neither does anything the simulation computes: Basilisk's hub
takes the centre of mass from B (``center_of_mass_b_m``), so drag, solar
pressure and thrust keep their torque about the same physical point.

The positions moved (:func:`move_origin`):

- the 3D model: each part's ``position_b_m``, each mounted equipment's
  ``mount.position_m`` (when it is not given in a part's frame), each
  stowed pose's ``position_b_m``, the launcher's ``origin_b_m`` and typed
  mass properties' ``center_of_mass_b_m``;
- the spacecraft: ``center_of_mass_b_m``, each sensor's and actuator's
  ``mount.position_m`` (when not in a part's frame) and its ``r_B``
  (thruster) or ``rWB_B`` (wheel), the RF antenna's mount (when not in a
  part's frame), each facet's ``location_b``, the fuel
  tank's ``tank_position_b_m`` and each solar array's ``hinge_position_b``.

An import record keeps the values it wrote, to tell a value edited since
from one it may update; :func:`shift_record_values` moves its positions
the same way, so a later import still compares like with like.
"""

from __future__ import annotations

import re

import numpy as np

#: The import record value paths that are positions from B, by their end.
_RECORD_POSITION = re.compile(r"(\.position_b_m|\.mount\.position_m|\.params\.r_B|\.params\.rWB_B)\[([0-2])\]$")
#: Device parameters that are positions from B [m].
DEVICE_POSITION_PARAMS = ("r_B", "rWB_B")


def _moved(vector, d: np.ndarray) -> list:
    return [_clean(float(v) - float(s)) for v, s in zip(vector, d, strict=True)]


def _clean(value: float) -> float:
    """Ten significant digits, and summation noise to zero."""
    return 0.0 if abs(value) < 1.0e-12 else float(f"{value:.10g}")


def _is_vector(value) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 3 and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)


def move_model_origin(model, d) -> list[str]:
    """Move the origin of a 3D model (``SpacecraftModelConfig``) to ``d``
    [m] (module docstring); returns what moved, as text."""
    d = np.asarray(d, dtype=float).reshape(3)
    moved = []
    if model is None:
        return moved
    for part in model.parts:
        part.position_b_m = _moved(part.position_b_m, d)
    if model.parts:
        moved.append(f"{len(model.parts)} part(s)")
    count = 0
    for item in model.equipment:
        if item.mount is not None and item.mount.position_m is not None and not item.mount.part:
            item.mount.position_m = _moved(item.mount.position_m, d)
            count += 1
    if count:
        moved.append(f"{count} mounted equipment")
    for pose in model.stowed:
        pose.position_b_m = _moved(pose.position_b_m, d)
    if model.stowed:
        moved.append(f"{len(model.stowed)} stowed pose(s)")
    if model.launcher is not None:
        model.launcher.origin_b_m = _moved(model.launcher.origin_b_m, d)
        moved.append("the launcher's separation plane")
    if model.mass_properties is not None:
        model.mass_properties.center_of_mass_b_m = _moved(model.mass_properties.center_of_mass_b_m, d)
        moved.append("the model's typed centre of mass")
    return moved


def _move_mount(mount, d: np.ndarray) -> bool:
    if mount is None or mount.position_m is None or mount.part:
        return False  # none, or given in a part's frame: it moves with the part
    mount.position_m = _moved(mount.position_m, d)
    return True


def move_mounts(devices, d) -> int:
    """Move the mounts of ``devices`` (anything with ``sensors``,
    ``actuators`` and ``rf_link``) to the origin ``d`` [m]: only the mounts,
    as the 3D model editor holds them; returns how many moved."""
    d = np.asarray(d, dtype=float).reshape(3)
    count = 0
    for device in list(getattr(devices, "sensors", None) or []) + list(getattr(devices, "actuators", None) or []):
        count += _move_mount(getattr(device, "mount", None), d)
    rf_link = getattr(devices, "rf_link", None)
    if rf_link is not None:
        count += _move_mount(getattr(rf_link, "antenna_mount", None), d)
    return count


def move_spacecraft_origin(sc, d) -> list[str]:
    """Move the origin of spacecraft ``sc`` to ``d`` [m], all but its 3D
    model (:func:`move_model_origin`); returns what moved, as text."""
    d = np.asarray(d, dtype=float).reshape(3)
    moved = []
    if _is_vector(getattr(sc, "center_of_mass_b_m", None)):
        sc.center_of_mass_b_m = _moved(sc.center_of_mass_b_m, d)
    count = 0
    for device in list(getattr(sc, "sensors", None) or []) + list(getattr(sc, "actuators", None) or []):
        touched = _move_mount(getattr(device, "mount", None), d)
        for key in DEVICE_POSITION_PARAMS:
            if _is_vector(device.params.get(key)):
                device.params[key] = _moved(device.params[key], d)
                touched = True
        count += touched
    if count:
        moved.append(f"{count} sensor(s) and actuator(s)")
    rf_link = getattr(sc, "rf_link", None)
    if rf_link is not None and _move_mount(getattr(rf_link, "antenna_mount", None), d):
        moved.append("the RF antenna")
    facets = getattr(sc, "facets", None) or []
    for facet in facets:
        facet.location_b = _moved(facet.location_b, d)
    if facets:
        moved.append(f"{len(facets)} facet(s)")
    tank = getattr(sc, "fuel_tank", None)
    if tank is not None:
        tank.tank_position_b_m = _moved(tank.tank_position_b_m, d)
        moved.append("the fuel tank")
    arrays = getattr(sc, "solar_arrays", None) or []
    for array in arrays:
        array.hinge_position_b = _moved(array.hinge_position_b, d)
    if arrays:
        moved.append(f"{len(arrays)} solar array hinge(s)")
    return moved


def move_origin(sc, d) -> list[str]:
    """Move the origin of spacecraft ``sc`` (its 3D model included) to
    ``d`` [m], given in its present body frame; returns what moved."""
    return move_model_origin(getattr(sc, "model", None), d) + move_spacecraft_origin(sc, d)


def shift_record_values(values: dict, d) -> dict:
    """An import record's ``values`` with each position from B moved as
    :func:`move_origin` moves the spacecraft's."""
    d = np.asarray(d, dtype=float).reshape(3)
    out = {}
    for path, value in values.items():
        match = _RECORD_POSITION.search(path)
        if match and isinstance(value, (int, float)) and not isinstance(value, bool):
            value = _clean(float(value) - float(d[int(match.group(2))]))
        out[path] = value
    return out
