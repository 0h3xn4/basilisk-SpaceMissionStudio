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
"""A run's geometry for the model analyses after it (``run_analyses``):
on the spacecraft's recorded times, its position, its attitude (the
nearest recorded sample), and the directions and distances of the Sun,
the Moon and the central body (their SPICE states, recorded when an
analysis asks, interpolated linearly), with the sunlight fraction.

Numpy only: no Basilisk.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..constants import CENTRAL_BODY_EQUATORIAL_RADIUS_KM


def mrp_to_dcm(sigma: np.ndarray) -> np.ndarray:
    """``[BN]`` of each MRP set in ``sigma`` (n, 3) (Schaub & Junkins, the
    form Basilisk's ``MRP2C`` uses)."""
    sigma = np.asarray(sigma, dtype=float).reshape(-1, 3)
    s2 = np.einsum("ij,ij->i", sigma, sigma)
    tilde = np.zeros((len(sigma), 3, 3))
    tilde[:, 0, 1], tilde[:, 0, 2], tilde[:, 1, 2] = -sigma[:, 2], sigma[:, 1], -sigma[:, 0]
    tilde[:, 1, 0], tilde[:, 2, 0], tilde[:, 2, 1] = sigma[:, 2], -sigma[:, 1], sigma[:, 0]
    square = tilde @ tilde
    return np.eye(3) + (8.0 * square - 4.0 * (1.0 - s2)[:, None, None] * tilde) / ((1.0 + s2) ** 2)[:, None, None]


def nearest_sample(source_t: np.ndarray, t: np.ndarray) -> np.ndarray:
    """The index in ``source_t`` (sorted) of the sample nearest each of ``t``."""
    index = np.clip(np.searchsorted(source_t, t), 1, max(len(source_t) - 1, 1))
    left = np.clip(index - 1, 0, len(source_t) - 1)
    right = np.clip(index, 0, len(source_t) - 1)
    return np.where(np.abs(source_t[left] - t) <= np.abs(source_t[right] - t), left, right)


def _interp(series, t: np.ndarray) -> np.ndarray:
    data = np.asarray(series.data, dtype=float)
    return np.column_stack([np.interp(t, series.time_s, data[:, k]) for k in range(data.shape[1])])


@dataclass
class RunGeometry:
    spacecraft: str
    time_s: np.ndarray  # (n,) [s]
    position_n: np.ndarray  # (n, 3) [m] spacecraft
    dcm_bn: np.ndarray  # (n, 3, 3)
    central_n: np.ndarray  # (n, 3) [m] central body
    central_radius_m: float
    sun_n: np.ndarray | None  # (n, 3) [m]
    moon_n: np.ndarray | None
    sunlight: np.ndarray  # (n,) [-] 1 in full Sun, 0 in umbra (1 when not recorded)

    def to_body(self, vectors_n: np.ndarray) -> np.ndarray:
        """Vectors (n, 3) in the inertial frame, in the body frame."""
        return np.einsum("nij,nj->ni", self.dcm_bn, vectors_n)

    def unit_body(self, target_n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """``(unit direction in the body frame, distance [m])`` from the
        spacecraft to ``target_n`` (n, 3)."""
        offset = target_n - self.position_n
        distance = np.linalg.norm(offset, axis=1)
        return self.to_body(offset / distance[:, None]), distance


def run_geometry(result, sc_name: str, central_body: str) -> RunGeometry | None:
    """The :class:`RunGeometry` of ``sc_name``, or None when the run did not
    record its attitude."""
    attitude = result.series.get(f"{sc_name}.attitude_sigma_BN")
    position = result.series.get(f"{sc_name}.position_N")
    if attitude is None or position is None or len(position.time_s) == 0:
        return None
    t = np.asarray(position.time_s, dtype=float)
    dcm = mrp_to_dcm(np.asarray(attitude.data, dtype=float)[nearest_sample(np.asarray(attitude.time_s, float), t)])
    central = result.series.get(f"ephemeris.{central_body}.position_N")
    central_n = _interp(central, t) if central is not None else np.zeros((len(t), 3))
    sun = result.series.get("ephemeris.sun.position_N")
    moon = result.series.get("ephemeris.moon.position_N")
    light = result.series.get(f"{sc_name}.eclipse.illumination_factor")
    sunlight = (np.interp(t, light.time_s, np.asarray(light.data, float)[:, 0]) if light is not None
                else np.ones(len(t)))
    radius = CENTRAL_BODY_EQUATORIAL_RADIUS_KM.get(central_body, 0.0) * 1000.0  # [m]
    return RunGeometry(sc_name, t, np.asarray(position.data, dtype=float), dcm, central_n, radius,
                       _interp(sun, t) if sun is not None else None, _interp(moon, t) if moon is not None else None,
                       sunlight)
