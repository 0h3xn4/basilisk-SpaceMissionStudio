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
"""Poses as 4 x 4 homogeneous transforms (double precision).

A position (``Position``) places a child frame in its parent: a
translation ``(x, y, z)`` [m] and three rotations [deg] about the axes
its ``rotationOrder`` names (``Rx_Ry_Rz``: about x, then y, then z), each
about the axes as already turned (intrinsic), right-handed and active,
so ``R = R1 @ R2 @ R3``. With ``Translation_Rotation`` the frame moves
first and then turns about its new origin (``x_parent = t + R x``); with
``Rotation_Translation`` it turns first and then moves along its turned
axes (``x_parent = R (t + x)``). These conventions were fixed against
the example models (design note, section 4); IDM-CIC's text does not
state all of them.

An articulation turns (``Rotation``, [deg]) or moves (``Translation``,
[m]) a coordinate system about or along one of its own axes, after its
position: ``frame = parent @ position @ articulation``.
"""

from __future__ import annotations

import math

import numpy as np

from .errors import IdmError

AXES = {"X": 0, "Y": 1, "Z": 2}
ROTATION_ORDERS = ("Rx_Ry_Rz", "Rx_Rz_Ry", "Ry_Rx_Rz", "Ry_Rz_Rx", "Rz_Rx_Ry", "Rz_Ry_Rx",
                   "Rx_Ry_Rx", "Rx_Rz_Rx", "Ry_Rx_Ry", "Ry_Rz_Ry", "Rz_Rx_Rz", "Rz_Ry_Rz")
TRANSFORMATION_ORDERS = ("Translation_Rotation", "Rotation_Translation")


def identity() -> np.ndarray:
    return np.eye(4)


def axis_rotation(axis: str, angle_deg: float) -> np.ndarray:
    """The 3 x 3 rotation by ``angle_deg`` [deg] about ``axis`` ("X", "Y" or
    "Z"), right-handed."""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    k = AXES[axis.upper()]
    r = np.eye(3)
    i, j = (k + 1) % 3, (k + 2) % 3
    r[i, i], r[i, j], r[j, i], r[j, j] = c, -s, s, c
    return r


def rotation(order: str, angles_deg) -> np.ndarray:
    """``R1 @ R2 @ R3`` for ``order`` (one of :data:`ROTATION_ORDERS`)."""
    if order not in ROTATION_ORDERS:
        raise IdmError(f"rotation order {order!r} is not one of {', '.join(ROTATION_ORDERS)}")
    axes = [part[1].upper() for part in order.split("_")]
    r = np.eye(3)
    for axis, angle in zip(axes, angles_deg, strict=True):
        r = r @ axis_rotation(axis, angle)
    return r


def pose(translation_m, order: str, angles_deg, transformation_order: str = "Translation_Rotation") -> np.ndarray:
    """The 4 x 4 transform of a position (module docstring)."""
    if transformation_order not in TRANSFORMATION_ORDERS:
        raise IdmError(f"transformation order {transformation_order!r} is not one of "
                       f"{', '.join(TRANSFORMATION_ORDERS)}")
    r = rotation(order, angles_deg)
    t = np.asarray(translation_m, dtype=float)
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = t if transformation_order == "Translation_Rotation" else r @ t
    return m


def articulation(kind: str, axis: str, value: float) -> np.ndarray:
    """The 4 x 4 transform of an articulation: ``kind`` "rotation" by
    ``value`` [deg] or "translation" by ``value`` [m], about or along ``axis``."""
    if axis.upper() not in AXES:
        raise IdmError(f"articulation axis {axis!r} is not X, Y or Z")
    m = np.eye(4)
    if kind == "rotation":
        m[:3, :3] = axis_rotation(axis, value)
    elif kind == "translation":
        m[AXES[axis.upper()], 3] = value
    else:
        raise IdmError(f"articulation kind {kind!r} is not rotation or translation")
    return m


def inverse(m: np.ndarray) -> np.ndarray:
    """The inverse of a rigid transform."""
    out = np.eye(4)
    r = m[:3, :3]
    out[:3, :3] = r.T
    out[:3, 3] = -r.T @ m[:3, 3]
    return out


def roll_pitch_yaw_deg(r: np.ndarray) -> list:
    """``[roll, pitch, yaw]`` [deg] with ``r = Rz(yaw) @ Ry(pitch) @ Rx(roll)``
    (the 3D model's convention), pitch in [-90, 90]."""
    r = np.asarray(r, dtype=float)
    sp = -float(np.clip(r[2, 0], -1.0, 1.0))
    pitch = math.asin(sp)
    if abs(sp) < 1.0 - 1.0e-12:
        roll = math.atan2(r[2, 1], r[2, 2])
        yaw = math.atan2(r[1, 0], r[0, 0])
    else:  # gimbal lock: roll and yaw turn about the same axis; all of it goes to yaw
        roll = 0.0
        yaw = math.atan2(-r[0, 1], r[1, 1])
    return [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]
