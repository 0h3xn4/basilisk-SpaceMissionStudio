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
r"""Navigation from surface landmarks seen by a camera (numpy only).

The pixels come from Basilisk's ``pinholeCamera`` in a run
(``engine.landmark_navigation``); this module holds what the tool does with
them, with the same camera conventions as that module
(``pinholeCamera.cpp``):

* the camera's boresight is its +z axis; a landmark at ``d_C`` (camera
  frame, from the camera to the landmark) is at
  ``u = f d_x / (d_z w)``, ``v = f d_y / (d_z w)`` pixels from the image
  centre (``f`` focal length, ``w`` pixel pitch);
* the reported pixel is ``u`` rounded away from zero (``ceil`` above
  zero, ``floor`` below), so its centre is ``p - sign(p) / 2`` and the
  rounding is uniform over one pixel: a standard deviation of
  ``1 / sqrt(12)`` pixels;
* a landmark is seen when it is in front of the camera, its surface faces
  against the boresight, its pixel is on the detector and the Sun is more
  than the mask angle above its local horizon. Basilisk does not check
  whether other terrain hides it.

:class:`LandmarkFilter` is an extended Kalman filter for the spacecraft's
position and velocity relative to the body, in the inertial frame. It
predicts with the body's own constant-density polyhedral gravity
(``engine.polyhedron``) and the body turning uniformly about its pole,
and updates with every landmark seen in an image.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np

from .polyhedron import Polyhedron

QUANTIZATION_SIGMA_PX = 1.0 / math.sqrt(12.0)  # [px] rounding to whole pixels
FOCAL_LENGTH_M = 0.025  # [m] the camera model's focal length; the pixel pitch follows from the field of view
_MAX_STEP_S = 60.0  # [s] the filter's integration step


def place_landmarks(shape: Polyhedron, count: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """``count`` surface landmarks [m] and their outward normals: centres
    of distinct facets drawn with probability proportional to area, so
    they spread over the surface evenly."""
    areas = shape.facet_areas
    rng = np.random.default_rng([seed, 2])
    chosen = rng.choice(len(areas), size=min(count, len(areas)), replace=False, p=areas / areas.sum())
    return shape.facet_centers[chosen], shape.facet_normals[chosen]


def pixel_pitch_m(fov_x_rad: float, nx: int) -> float:
    """[m] the pixel pitch that gives ``fov_x_rad`` across ``nx`` pixels
    at :data:`FOCAL_LENGTH_M` (pinholeCamera: FOVx = 2 atan(nx w / 2f))."""
    return 2.0 * FOCAL_LENGTH_M * math.tan(0.5 * fov_x_rad) / nx


def rotation_z(angle_rad: float) -> np.ndarray:
    """Frame rotation about z by ``angle_rad``."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])


def body_dcm(dcm_PN0: np.ndarray, spin_rad_s: float, dt_s: float) -> np.ndarray:
    """The body frame ``dt_s`` after ``dcm_PN0`` for a uniform spin about
    the body's z axis (its pole)."""
    return rotation_z(spin_rad_s * dt_s) @ dcm_PN0


def project(landmarks_P: np.ndarray, r_N: np.ndarray, dcm_PN: np.ndarray, dcm_CN: np.ndarray,
            f_over_w: float) -> tuple[np.ndarray, np.ndarray]:
    """Unrounded pixels ``(n, 2)`` of landmarks [m, body frame] seen from
    ``r_N`` [m], and their camera-frame vectors ``d_C`` ``(n, 3)``."""
    d_N = landmarks_P @ dcm_PN - np.asarray(r_N, float)
    d_C = d_N @ dcm_CN.T
    return f_over_w * d_C[:, :2] / d_C[:, 2:3], d_C


def pixel_jacobian(d_C: np.ndarray, dcm_CN: np.ndarray, f_over_w: float) -> np.ndarray:
    """d (u, v) / d r_N ``(2n, 3)`` of the landmarks at camera-frame
    vectors ``d_C`` ``(n, 3)`` (:func:`project`)."""
    rows = []
    for d in d_C:
        du_dd = f_over_w * np.array([[1.0 / d[2], 0.0, -d[0] / d[2] ** 2],
                                     [0.0, 1.0 / d[2], -d[1] / d[2] ** 2]])
        rows.append(du_dd @ -dcm_CN)
    return np.vstack(rows)


def round_pixels(uv: np.ndarray) -> np.ndarray:
    """pinholeCamera's pixelisation: away from zero, and 1 for exactly 0."""
    rounded = np.where(uv > 0.0, np.ceil(uv), np.floor(uv))
    return np.where(uv == 0.0, 1.0, rounded)


def pixel_centres(pixels: np.ndarray) -> np.ndarray:
    """Where a rounded pixel's landmark most likely is: its centre."""
    return pixels - 0.5 * np.sign(pixels)


def visible(landmarks_P: np.ndarray, normals_P: np.ndarray, r_P: np.ndarray, boresight_P: np.ndarray,
            sun_P: np.ndarray, pixels: np.ndarray, resolution: Sequence[int], sun_mask_rad: float) -> np.ndarray:
    """pinholeCamera's rules (module docstring) for each landmark."""
    to_camera = np.asarray(r_P, float) - landmarks_P
    to_camera /= np.linalg.norm(to_camera, axis=1, keepdims=True)
    in_front = to_camera @ -boresight_P > 0.0
    facing = normals_P @ -boresight_P > 0.0
    on_detector = (np.abs(2.0 * pixels[:, 0]) <= resolution[0]) & (np.abs(2.0 * pixels[:, 1]) <= resolution[1])
    sun = np.asarray(sun_P, float) / np.linalg.norm(sun_P)
    lit = 0.5 * np.pi - np.arccos(np.clip(normals_P @ sun, -1.0, 1.0)) > sun_mask_rad
    return in_front & facing & on_detector & lit


@dataclass
class Update:
    """What one image did to the filter."""

    used: int  # landmarks in the update
    residual_rms_px: float  # [px] before the update; nan without landmarks


class LandmarkFilter:
    """EKF for ``x = [r_N, v_N]`` [m, m/s] relative to the body's centre.

    ``process_noise`` [m/s^1.5] is the spectral density of a white
    acceleration noise on each axis; ``pixel_sigma`` [px] the standard
    deviation of one pixel coordinate (rounding plus any added noise).
    """

    def __init__(self, shape: Polyhedron, mu: float, spin_rad_s: float, landmarks_P: np.ndarray,
                 x0: np.ndarray, sigma_r_m: float, sigma_v_mps: float, process_noise: float,
                 pixel_sigma: float, f_over_w: float):
        self.shape = shape
        self.mu = mu
        self.spin = spin_rad_s
        self.landmarks_P = np.asarray(landmarks_P, float)
        self.x = np.asarray(x0, float).reshape(6).copy()
        self.P = np.diag([sigma_r_m ** 2] * 3 + [sigma_v_mps ** 2] * 3)
        self.q = process_noise ** 2  # [m^2/s^3]
        self.R_px2 = pixel_sigma ** 2  # [px^2]
        self.f_over_w = f_over_w

    def _derivatives(self, x: np.ndarray, phi: np.ndarray, dcm_PN: np.ndarray):
        acceleration_P, gradient_P = self.shape.field_and_gradient(dcm_PN @ x[:3], self.mu)
        gradient_N = dcm_PN.T @ gradient_P @ dcm_PN
        a = np.zeros((6, 6))
        a[:3, 3:] = np.eye(3)
        a[3:, :3] = gradient_N
        return np.concatenate([x[3:], dcm_PN.T @ acceleration_P]), a @ phi

    def propagate(self, dt_s: float, dcm_PN0: np.ndarray) -> None:
        """Advance ``dt_s`` from a time whose body frame is ``dcm_PN0``
        (RK4 on the state and its transition matrix)."""
        if dt_s <= 0.0:
            return
        steps = max(1, math.ceil(dt_s / _MAX_STEP_S))
        h = dt_s / steps
        x, phi = self.x, np.eye(6)
        for k in range(steps):
            t0 = k * h
            frames = [body_dcm(dcm_PN0, self.spin, t0 + c * h) for c in (0.0, 0.5, 1.0)]
            k1x, k1p = self._derivatives(x, phi, frames[0])
            k2x, k2p = self._derivatives(x + 0.5 * h * k1x, phi + 0.5 * h * k1p, frames[1])
            k3x, k3p = self._derivatives(x + 0.5 * h * k2x, phi + 0.5 * h * k2p, frames[1])
            k4x, k4p = self._derivatives(x + h * k3x, phi + h * k3p, frames[2])
            x = x + h / 6.0 * (k1x + 2 * k2x + 2 * k3x + k4x)
            phi = phi + h / 6.0 * (k1p + 2 * k2p + 2 * k3p + k4p)
        q = self.q
        noise = np.zeros((6, 6))
        noise[:3, :3] = np.eye(3) * q * dt_s ** 3 / 3.0
        noise[:3, 3:] = noise[3:, :3] = np.eye(3) * q * dt_s ** 2 / 2.0
        noise[3:, 3:] = np.eye(3) * q * dt_s
        self.x = x
        self.P = phi @ self.P @ phi.T + noise
        self.P = 0.5 * (self.P + self.P.T)

    def update(self, indices: Sequence[int], pixels: np.ndarray, dcm_PN: np.ndarray, dcm_CN: np.ndarray) -> Update:
        """One image: the landmarks ``indices`` seen at rounded ``pixels``
        ``(n, 2)``, with the body and camera frames at that time."""
        if len(indices) == 0:
            return Update(0, math.nan)
        predicted, d_C = project(self.landmarks_P[list(indices)], self.x[:3], dcm_PN, dcm_CN, self.f_over_w)
        residual = (pixel_centres(np.asarray(pixels, float)) - predicted).reshape(-1)
        h = np.hstack([pixel_jacobian(d_C, dcm_CN, self.f_over_w), np.zeros((2 * len(d_C), 3))])
        s = h @ self.P @ h.T + np.eye(len(residual)) * self.R_px2
        gain = np.linalg.solve(s, h @ self.P).T
        self.x = self.x + gain @ residual
        joseph = np.eye(6) - gain @ h
        self.P = joseph @ self.P @ joseph.T + gain @ gain.T * self.R_px2
        self.P = 0.5 * (self.P + self.P.T)
        return Update(len(indices), float(np.sqrt(np.mean(residual ** 2))))


def initial_state(r0_m: np.ndarray, v0_mps: np.ndarray, sigma_r_m: float, sigma_v_mps: float,
                  seed: int) -> np.ndarray:
    """The true state plus one seeded draw of the initial sigmas."""
    rng = np.random.default_rng([seed, 1])
    error = np.concatenate([rng.normal(0.0, sigma_r_m, 3), rng.normal(0.0, sigma_v_mps, 3)])
    return np.concatenate([np.asarray(r0_m, float).reshape(3), np.asarray(v0_mps, float).reshape(3)]) + error


def nadir_dcm_CN(r_N: np.ndarray, v_N: np.ndarray) -> np.ndarray:
    """A camera frame with +z towards the body's centre and +x along the
    orbit normal crossed with the position (the opnav convention)."""
    z = -np.asarray(r_N, float) / np.linalg.norm(r_N)
    h = np.cross(r_N, v_N)
    x = np.cross(h, -z)
    x /= np.linalg.norm(x)
    return np.vstack([x, np.cross(z, x), z])


def landmark_count_in_view(landmarks_P: np.ndarray, normals_P: np.ndarray, r_N: np.ndarray, v_N: np.ndarray,
                           dcm_PN: np.ndarray, sun_N: np.ndarray | None, fov_x_rad: float,
                           resolution: Sequence[int], sun_mask_rad: float) -> int:
    """How many landmarks a nadir-pointed camera sees from ``r_N``; with
    ``sun_N`` None the Sun is straight behind the spacecraft."""
    dcm_CN = nadir_dcm_CN(r_N, v_N)
    f_over_w = FOCAL_LENGTH_M / pixel_pitch_m(fov_x_rad, resolution[0])
    uv, _ = project(landmarks_P, r_N, dcm_PN, dcm_CN, f_over_w)
    sun_P = dcm_PN @ (sun_N if sun_N is not None else np.asarray(r_N, float))
    seen = visible(landmarks_P, normals_P, dcm_PN @ r_N, dcm_PN @ dcm_CN[2], sun_P, round_pixels(uv), resolution,
                   sun_mask_rad)
    return int(seen.sum())
