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
r"""Optical navigation from a planet's disk: the camera geometry.

Pure numpy, no Basilisk; ``engine.optical_navigation`` runs it in a
simulation. This module is the tool's own code.

**What it models.** No image is rendered (Basilisk's ``camera`` module only
corrupts images Vizard renders, and no Vizard runs in a headless run).
Instead the measurement an image-processing step such as Basilisk's
``houghCircles`` would report is computed from the true geometry: where
the centre of the planet's disk falls on the detector (pixel and line) and
the disk's apparent radius in pixels, with Gaussian noise added by the
caller. Basilisk's ``pixelLineConverter`` turns that back into a position,
and ``relativeODuKF`` filters it.

**Camera model** (the one ``pixelLineConverter`` inverts, in Basilisk
2.12's ``pixelLineConverter.c``). The camera frame C has its boresight
along +z. ``fieldOfView`` is edge to edge along the image's y (line)
axis; along x it is taken as ``fieldOfView * width / height``. One pixel
spans ``X = 2 tan(fov * w / h / 2) / w`` and ``Y = 2 tan(fov / 2) / h`` of
the image plane at unit distance. A direction ``(x, y, z)`` in C lands at::

    pixel = (x / z) / X + w / 2 - 0.5
    line  = (y / z) / Y + h / 2 - 0.5

and a sphere of radius ``R`` at distance ``d`` has the apparent radius
``tan(asin(R / d)) / X`` pixels (``pixelLineConverter`` takes the range as
``R / sin(atan(X rho))``, so it uses X for both axes).

**Bodies.** ``pixelLineConverter`` and ``relativeODuKF`` know three bodies
by number: 1 Earth, 2 Mars, 3 Jupiter, with Basilisk's ``REQ_*`` radii and
``MU_*`` values. The tool flies Mars and Jupiter as their system
barycentres (``schema.scenario.SUPPORTED_CENTRAL_BODIES``), which is what
the two numbers stand for here.

**A usable image** (:func:`project_body`): the body in front of the
camera, its whole disk on the detector, and at least ``min_radius_px``
across; and (:func:`phase_angle`) the camera on the lit side, the
Sun-body-spacecraft angle at most a limit. The offset of a crescent's
centre from the disk's centre, which a real image processing step would
see, is not modelled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

# pixelLineConverter / relativeODuKF body numbers (planetIds, planetIdInit)
BODY_IDS = {"earth": 1, "mars barycenter": 2, "jupiter barycenter": 3}
# [m] Basilisk 2.12 astroConstants REQ_EARTH, REQ_MARS, REQ_JUPITER: the radii
# pixelLineConverter takes the range from
BODY_RADIUS_M = {"earth": 6378.1366e3, "mars barycenter": 3396.19e3, "jupiter barycenter": 71492.0e3}


def _tilde(v: Sequence[float]) -> np.ndarray:
    x, y, z = v
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def mrp_to_dcm(sigma: Sequence[float]) -> np.ndarray:
    """The direction cosine matrix [BN] of the MRP ``sigma`` (Schaub and
    Junkins; Basilisk's ``MRP2C``)."""
    s = np.asarray(sigma, dtype=float)
    s2 = float(s @ s)
    t = _tilde(s)
    return np.eye(3) + (8.0 * t @ t - 4.0 * (1.0 - s2) * t) / (1.0 + s2) ** 2


def dcm_to_mrp(dcm: np.ndarray) -> np.ndarray:
    """The MRP (|sigma| <= 1) of a direction cosine matrix, through the
    quaternion with the largest component (Sheppard's method)."""
    c = np.asarray(dcm, dtype=float)
    trace = float(np.trace(c))
    b = np.array([trace, c[0, 0], c[1, 1], c[2, 2]])
    k = int(np.argmax(b))
    if k == 0:
        b0 = 0.5 * math.sqrt(1.0 + trace)
        q = np.array([b0, (c[1, 2] - c[2, 1]) / (4.0 * b0), (c[2, 0] - c[0, 2]) / (4.0 * b0),
                      (c[0, 1] - c[1, 0]) / (4.0 * b0)])
    else:
        i = k - 1
        j, m = (i + 1) % 3, (i + 2) % 3
        bi = 0.5 * math.sqrt(1.0 + 2.0 * c[i, i] - trace)
        q = np.zeros(4)
        q[1 + i] = bi
        q[0] = (c[j, m] - c[m, j]) / (4.0 * bi)
        q[1 + j] = (c[i, j] + c[j, i]) / (4.0 * bi)
        q[1 + m] = (c[m, i] + c[i, m]) / (4.0 * bi)
    if q[0] < 0.0:
        q = -q
    return q[1:] / (1.0 + q[0])


def pixel_scales(fov_rad: float, resolution: Sequence[int]) -> Tuple[float, float]:
    """``(X, Y)``: one pixel's size on the image plane at unit distance, in
    x and y (module docstring)."""
    width, height = resolution
    return (2.0 * math.tan(fov_rad * width / height / 2.0) / width,
            2.0 * math.tan(fov_rad / 2.0) / height)


@dataclass(frozen=True)
class CircleMeasurement:
    """Where a body's disk is on the detector: its centre [pixel, line]
    and apparent radius [px]; ``valid`` and, when not, ``reason``."""

    pixel: float  # [px] x of the disk's centre
    line: float  # [px] y of the disk's centre
    radius_px: float  # [px]
    valid: bool
    reason: str = ""  # why the image is not usable ("" when valid)


def project_body(r_BN_N: Sequence[float], dcm_CN: np.ndarray, radius_m: float, fov_rad: float,
                 resolution: Sequence[int], min_radius_px: float) -> CircleMeasurement:
    """The disk of a sphere of ``radius_m`` [m] at the origin, seen from a
    spacecraft at ``r_BN_N`` [m] through a camera with attitude ``dcm_CN``
    (module docstring). Not valid when the body is behind the camera, its
    disk is not wholly on the detector, or it is under ``min_radius_px``."""
    r = np.asarray(r_BN_N, dtype=float)
    distance = float(np.linalg.norm(r))  # [m]
    if distance <= radius_m:
        return CircleMeasurement(math.nan, math.nan, math.nan, False, "inside the body")
    to_body_C = np.asarray(dcm_CN) @ (-r)
    if to_body_C[2] <= 0.0:
        return CircleMeasurement(math.nan, math.nan, math.nan, False, "behind the camera")
    x_scale, y_scale = pixel_scales(fov_rad, resolution)
    width, height = resolution
    pixel = to_body_C[0] / to_body_C[2] / x_scale + width / 2.0 - 0.5
    line = to_body_C[1] / to_body_C[2] / y_scale + height / 2.0 - 0.5
    radius_px = math.tan(math.asin(radius_m / distance)) / x_scale
    if radius_px < min_radius_px:
        return CircleMeasurement(pixel, line, radius_px, False, "too small")
    if (pixel - radius_px < -0.5 or pixel + radius_px > width - 0.5
            or line - radius_px < -0.5 or line + radius_px > height - 0.5):
        return CircleMeasurement(pixel, line, radius_px, False, "not wholly in the image")
    return CircleMeasurement(pixel, line, radius_px, True)


def position_from_circle(pixel: float, line: float, radius_px: float, dcm_CN: np.ndarray, radius_m: float,
                         fov_rad: float, resolution: Sequence[int]) -> np.ndarray:
    """The spacecraft's position [m] relative to the body that a disk
    measurement gives: ``pixelLineConverter``'s computation, for checking
    :func:`project_body` without Basilisk."""
    x_scale, y_scale = pixel_scales(fov_rad, resolution)
    width, height = resolution
    direction_C = np.array([(pixel - width / 2.0 + 0.5) * x_scale, (line - height / 2.0 + 0.5) * y_scale, 1.0])
    to_spacecraft_C = -direction_C / np.linalg.norm(direction_C)
    distance = radius_m / math.sin(math.atan(x_scale * radius_px))
    return np.asarray(dcm_CN).T @ to_spacecraft_C * distance


def phase_angle(r_BN_N: Sequence[float], r_SN_N: Sequence[float]) -> float:
    """The Sun-body-spacecraft angle [rad] with the body at the origin:
    0 when the camera sees the full lit disk, pi when it sees the night side."""
    to_spacecraft = np.asarray(r_BN_N, dtype=float)
    to_sun = np.asarray(r_SN_N, dtype=float)
    cosine = float(to_spacecraft @ to_sun) / (np.linalg.norm(to_spacecraft) * np.linalg.norm(to_sun))
    return math.acos(max(-1.0, min(1.0, cosine)))


def pointing_dcm_CN(r_BN_N: Sequence[float], v_BN_N: Sequence[float]) -> np.ndarray:
    """A camera attitude [CN] with the boresight (+z) on the body's centre
    and +x along the direction of motion across it (for an orbit-only run,
    where the camera points perfectly)."""
    r = np.asarray(r_BN_N, dtype=float)
    v = np.asarray(v_BN_N, dtype=float)
    z = -r / np.linalg.norm(r)
    h = np.cross(r, v)
    x = np.cross(h, r)
    x = x / np.linalg.norm(x) if np.linalg.norm(x) > 0.0 else _any_perpendicular(z)
    y = np.cross(z, x)
    return np.vstack([x, y, z])


def _any_perpendicular(z: np.ndarray) -> np.ndarray:
    axis = np.eye(3)[int(np.argmin(np.abs(z)))]
    x = np.cross(axis, z)
    return x / np.linalg.norm(x)


def body_attitude(dcm_CN: np.ndarray, sigma_CB: Sequence[float]) -> np.ndarray:
    """The spacecraft attitude MRP sigma_BN that gives the camera ``dcm_CN``
    with the camera mounted at ``sigma_CB``: [BN] = [CB]^T [CN]."""
    return dcm_to_mrp(mrp_to_dcm(sigma_CB).T @ np.asarray(dcm_CN))


def camera_dcm_CN(sigma_BN: Sequence[float], sigma_CB: Sequence[float]) -> np.ndarray:
    """The camera's attitude [CN] = [CB][BN] on a spacecraft at ``sigma_BN``."""
    return mrp_to_dcm(sigma_CB) @ mrp_to_dcm(sigma_BN)


def noisy(measurement: CircleMeasurement, center_sigma_px: float, radius_sigma_px: float,
          rng: np.random.Generator) -> CircleMeasurement:
    """The measurement with zero-mean Gaussian noise on its centre and
    radius (1 sigma in pixels); an invalid one is returned as is."""
    if not measurement.valid:
        return measurement
    dx, dy = rng.normal(0.0, center_sigma_px, 2) if center_sigma_px > 0.0 else (0.0, 0.0)
    dr = rng.normal(0.0, radius_sigma_px) if radius_sigma_px > 0.0 else 0.0
    return CircleMeasurement(measurement.pixel + float(dx), measurement.line + float(dy),
                             max(measurement.radius_px + float(dr), 1e-6), True)


def body_id(central_body: str) -> Optional[int]:
    """``pixelLineConverter``'s number for a central body, or None."""
    return BODY_IDS.get(central_body)
