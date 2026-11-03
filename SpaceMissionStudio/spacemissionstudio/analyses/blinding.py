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
"""Sensor blinding and antenna obstruction over a run (model analyses).

**Blinding.** A mounted item with exclusion angles (a star tracker,
camera or sensor) is blinded by a body when the angle between its
boresight and the body's centre is less than the exclusion angle plus the
body's angular radius:

- the Sun, while the spacecraft is not in umbra (the Sun's radius from
  ``constants``);
- the central body, its equatorial radius plus ``earth_atmosphere_km``
  when set (the bright limb);
- the Moon, when the run tracks it (its radius from ``constants``).

Each blinded item gives a series ``<sc>.blinding.<item>`` (columns sun,
earth, moon, blinded: 1 or 0), and the star trackers together
``<sc>.blinding.all_star_trackers`` (1 when every one is blinded). The
spacecraft's own parts in a field of view are the static check
(``fov``), not repeated here.

**Antenna obstruction.** During each pass (the station's ``has_access``),
a ray from the antenna to the station, in the body frame, is cast against
the model (the antenna's own part ignored): ``<station>.access_to_<sc>.
antenna_obstructed`` is 1 when a part is in the way.
"""

from __future__ import annotations

import math

import numpy as np

from ..constants import CENTRAL_BODY_EQUATORIAL_RADIUS_KM
from ..engine.results import TimeSeries

SUN_RADIUS_M = CENTRAL_BODY_EQUATORIAL_RADIUS_KM["sun"] * 1000.0  # [m]
MOON_RADIUS_M = CENTRAL_BODY_EQUATORIAL_RADIUS_KM["moon"] * 1000.0  # [m]
UMBRA = 1e-6  # [-] below this sunlight fraction the Sun is hidden


def _angle(boresight_b: np.ndarray, direction_b: np.ndarray) -> np.ndarray:
    return np.arccos(np.clip(direction_b @ boresight_b, -1.0, 1.0))


def blinding_series(geometry, items) -> tuple[list, list[str]]:
    """``(series, notes)`` for the mounted ``items`` with exclusion angles."""
    out, notes = [], []
    trackers = []
    boresights = [(item, np.asarray(item.boresight_b, dtype=float)) for item in items
                  if item.has_exclusions and item.boresight_b is not None]
    if not boresights:
        return out, notes
    n = len(geometry.time_s)
    if geometry.moon_n is None and any(item.exclusion_moon_deg is not None for item, _ in boresights):
        notes.append("the run does not track the Moon: Moon exclusions are not checked (add 'moon' to the "
                     "third-body perturbers)")
    sun_b = sun_distance = None
    if geometry.sun_n is not None:
        sun_b, sun_distance = geometry.unit_body(geometry.sun_n)
    elif any(item.exclusion_sun_deg is not None for item, _ in boresights):
        notes.append("the run does not track the Sun: Sun exclusions are not checked")
    earth_b, earth_distance = geometry.unit_body(geometry.central_n)
    moon_b = moon_distance = None
    if geometry.moon_n is not None:
        moon_b, moon_distance = geometry.unit_body(geometry.moon_n)
    for item, boresight in boresights:
        columns = np.zeros((n, 4))
        if item.exclusion_sun_deg is not None and sun_b is not None:
            limit = math.radians(item.exclusion_sun_deg) + np.arcsin(np.clip(SUN_RADIUS_M / sun_distance, 0, 1))
            columns[:, 0] = (_angle(boresight, sun_b) < limit) & (geometry.sunlight > UMBRA)
        if item.exclusion_earth_deg is not None:
            radius = geometry.central_radius_m + 1000.0 * (item.earth_atmosphere_km or 0.0)  # [m]
            limit = math.radians(item.exclusion_earth_deg) + np.arcsin(np.clip(radius / earth_distance, 0, 1))
            columns[:, 1] = _angle(boresight, earth_b) < limit
        if item.exclusion_moon_deg is not None and moon_b is not None:
            limit = math.radians(item.exclusion_moon_deg) + np.arcsin(np.clip(MOON_RADIUS_M / moon_distance, 0, 1))
            columns[:, 2] = _angle(boresight, moon_b) < limit
        columns[:, 3] = columns[:, :3].max(axis=1)
        out.append(TimeSeries(f"{geometry.spacecraft}.blinding.{item.name}", geometry.time_s,
                              ("sun", "earth", "moon", "blinded"), columns, units="-"))
        if item.kind == "star_tracker":
            trackers.append(columns[:, 3])
    if trackers:
        out.append(TimeSeries(f"{geometry.spacecraft}.blinding.all_star_trackers", geometry.time_s,
                              ("all_blinded",), np.min(np.column_stack(trackers), axis=1), units="-"))
    return out, notes


def obstruction_series(result, geometry, antenna, scene, stations) -> list:
    """``<station>.access_to_<sc>.antenna_obstructed`` for each station in
    ``stations`` the run recorded, during its passes."""
    out = []
    if antenna is None or antenna.position_b_m is None:
        return out
    origin = np.asarray(antenna.position_b_m, dtype=float)
    exclude = (antenna.part,) if antenna.part else ()
    for station in stations:
        prefix = f"{station}.access_to_{geometry.spacecraft}"
        access = result.series.get(f"{prefix}.has_access")
        where = result.series.get(f"{station}.station.position_N")
        if access is None or where is None:
            continue
        t = np.asarray(access.time_s, dtype=float)
        on = np.asarray(access.data, dtype=float)[:, 0] > 0.0
        blocked = np.zeros(len(t))
        if on.any():
            index = np.clip(np.searchsorted(geometry.time_s, t[on]), 0, len(geometry.time_s) - 1)
            station_n = np.column_stack([np.interp(t[on], where.time_s, np.asarray(where.data, float)[:, k])
                                         for k in range(3)])
            offset = station_n - geometry.position_n[index]
            direction_b = np.einsum("nij,nj->ni", geometry.dcm_bn[index], offset)
            direction_b /= np.linalg.norm(direction_b, axis=1)[:, None]
            distance, _part = scene.nearest(np.tile(origin, (len(direction_b), 1)), direction_b, exclude)
            blocked[on] = np.isfinite(distance)
        out.append(TimeSeries(f"{prefix}.antenna_obstructed", t, ("antenna_obstructed",), blocked, units="-"))
    return out
