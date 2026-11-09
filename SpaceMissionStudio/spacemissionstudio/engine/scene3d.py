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
"""The 3D scene of a run: what the built-in 3D view (``gui.mission_view_widget``)
draws, computed from the run's own results. No new physics: positions and
attitudes are the run's series, sampled on one time grid.

* **Frame:** the run's inertial frame N, centred on the central body, in
  kilometres.
* **The central body:** a sphere of its equatorial radius. For Earth it
  turns with the Earth rotation angle (IERS 2010, eq. 5.15, UT1 taken as
  UTC: a visual approximation, about 0.4 degrees from the true Earth-fixed
  frame in 2030 since precession is left out) and is shaded by Basilisk's
  albedo map when the support data holds it, so oceans, land and clouds
  show. Ground stations turn with it.
* **The Sun:** for Earth-centred runs, the direction from the Astronomical
  Almanac's low-precision solar position (about 0.01 degrees from 1950 to
  2050), used for the lighting and drawn as an arrow; for a run around
  the Sun, the origin.
* **Spacecraft:** each one's ``position_N``, its attitude ``attitude_sigma_BN``
  when the run recorded one (else drawn aligned with N, and said so), its
  3D model's parts when it has one (else a 1 m cube), its full path.

:func:`build_scene` is Basilisk-free and returns plain arrays, so the view
and the tests use the same numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from ..constants import CENTRAL_BODY_EQUATORIAL_RADIUS_KM
from ..schema.epochs import parse_epoch_utc

#: At most this many frames are kept for playback (spread evenly over the
#: run); the path line keeps up to ``MAX_PATH_POINTS``.
MAX_FRAMES = 1500  # [-]
MAX_PATH_POINTS = 4000  # [-]
_J2000_JD = 2451545.0  # [day] Julian date of J2000.0
_UNIX_EPOCH_JD = 2440587.5  # [day] Julian date of 1970-01-01T00:00:00
_DEFAULT_SIZE_M = 1.0  # [m] edge of the cube drawn for a spacecraft without a 3D model


@dataclass
class Craft:
    """One spacecraft as drawn."""

    name: str
    position_km: np.ndarray  # (n, 3) on the scene's frames
    path_km: np.ndarray  # (m, 3) the whole path, for the orbit line
    dcm_BN: np.ndarray | None  # (n, 3, 3), or None without an attitude
    vertices_km: np.ndarray  # (k, 3) body frame, true size
    triangles: np.ndarray  # (t, 3)
    face_colors: list[str]  # per triangle, "rgb(r,g,b)"
    size_km: float  # the model's largest extent
    notes: list[str] = field(default_factory=list)


@dataclass
class Scene:
    """Everything the 3D view draws, on ``times_s`` (seconds from the epoch)."""

    epoch_utc: str
    times_s: np.ndarray  # (n,)
    body: str
    body_radius_km: float
    body_rotation_rad: np.ndarray | None  # (n,) angle of the body-fixed frame about N's z, or None
    body_albedo: np.ndarray | None  # (lat, lon) grid from -90 and -180 deg, or None
    crafts: list[Craft]
    stations: list[tuple[str, np.ndarray]]  # name, body-fixed position [km]
    sun_direction_N: np.ndarray | None  # (n, 3) unit vectors, or None
    extent_km: float  # half-width of a box holding the body and every path
    notes: list[str] = field(default_factory=list)


def julian_date(epoch: datetime, seconds: np.ndarray) -> np.ndarray:
    """Julian dates (UTC) of ``seconds`` after ``epoch`` (naive UTC)."""
    base = (epoch - datetime(1970, 1, 1)).total_seconds() / 86400.0 + _UNIX_EPOCH_JD
    return base + np.asarray(seconds, dtype=float) / 86400.0


def earth_rotation_angle(jd_ut1: np.ndarray) -> np.ndarray:
    """Earth rotation angle [rad], IERS Conventions 2010 eq. (5.15)."""
    du = np.asarray(jd_ut1, dtype=float) - _J2000_JD
    turns = 0.7790572732640 + 1.00273781191135448 * du
    return 2.0 * np.pi * np.mod(turns, 1.0)


def sun_direction_eci(jd: np.ndarray) -> np.ndarray:
    """Unit vectors to the Sun from the Earth in the mean equator and
    equinox frame (J2000 within this accuracy): the Astronomical Almanac's
    low-precision formula, about 0.01 degrees from 1950 to 2050."""
    n = np.asarray(jd, dtype=float) - _J2000_JD
    mean_longitude = np.radians(280.460 + 0.9856474 * n)
    anomaly = np.radians(357.528 + 0.9856003 * n)
    ecliptic_longitude = mean_longitude + np.radians(1.915) * np.sin(anomaly) + np.radians(0.020) * np.sin(
        2.0 * anomaly)
    obliquity = np.radians(23.439 - 0.0000004 * n)
    return np.column_stack([np.cos(ecliptic_longitude), np.cos(obliquity) * np.sin(ecliptic_longitude),
                            np.sin(obliquity) * np.sin(ecliptic_longitude)])


def mrp_to_dcm(sigma: np.ndarray) -> np.ndarray:
    """``[BN]`` of each MRP set in ``sigma`` (n, 3) (Schaub & Junkins)."""
    sigma = np.asarray(sigma, dtype=float).reshape(-1, 3)
    s2 = np.einsum("ij,ij->i", sigma, sigma)
    tilde = np.zeros((len(sigma), 3, 3))
    tilde[:, 0, 1], tilde[:, 0, 2], tilde[:, 1, 2] = -sigma[:, 2], sigma[:, 1], -sigma[:, 0]
    tilde[:, 1, 0], tilde[:, 2, 0], tilde[:, 2, 1] = sigma[:, 2], -sigma[:, 1], sigma[:, 0]
    square = tilde @ tilde
    return np.eye(3) + (8.0 * square - 4.0 * (1.0 - s2)[:, None, None] * tilde) / ((1.0 + s2) ** 2)[:, None, None]


def _sample(series, times_s: np.ndarray) -> np.ndarray:
    """``series`` (a TimeSeries) at ``times_s``, linearly between samples."""
    return np.column_stack([np.interp(times_s, series.time_s, series.data[:, column])
                            for column in range(series.data.shape[1])])


def _attitude(series, times_s: np.ndarray) -> np.ndarray:
    """DCMs at ``times_s``: the nearest recorded attitude (an MRP switching
    to its shadow set cannot be interpolated component-wise)."""
    index = np.clip(np.searchsorted(series.time_s, times_s), 0, len(series.time_s) - 1)
    earlier = np.clip(index - 1, 0, len(series.time_s) - 1)
    nearer = np.where(np.abs(series.time_s[earlier] - times_s) < np.abs(series.time_s[index] - times_s),
                      earlier, index)
    return mrp_to_dcm(series.data[nearer, :3])


def _rgb(color) -> str:
    red, green, blue = (int(round(255 * max(0.0, min(1.0, c)))) for c in color[:3])
    return f"rgb({red},{green},{blue})"


def _cube(size_m: float):
    h = size_m / 2.0
    vertices = np.array([[x, y, z] for x in (-h, h) for y in (-h, h) for z in (-h, h)])
    triangles = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                          [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    return vertices, triangles


def spacecraft_mesh(sc, base_dir=None) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """Body-frame vertices [m], triangles, a colour per triangle and notes:
    the visible parts of the spacecraft's 3D model, or a 1 m cube."""
    notes: list[str] = []
    model = getattr(sc, "model", None)
    if model is not None:
        try:
            from ..model3d.model import derive

            derived = derive(model, base_dir)
        except Exception as exc:  # noqa: BLE001 -- a model that cannot be built is drawn as a cube, with the reason
            notes.append(f"{sc.name}: its 3D model could not be built ({exc}); drawn as a 1 m cube")
        else:
            vertices, triangles, colors = [], [], []
            offset = 0
            for part in derived.parts:
                if part.mesh is None or not part.visible or not len(part.mesh.triangles):
                    continue
                vertices.append(part.mesh.vertices)
                triangles.append(part.mesh.triangles + offset)
                colors += [_rgb(part.color)] * len(part.mesh.triangles)
                offset += len(part.mesh.vertices)
            if vertices:
                return np.vstack(vertices), np.vstack(triangles), colors, notes
            notes.append(f"{sc.name}: its 3D model has no visible part; drawn as a 1 m cube")
    vertices, triangles = _cube(_DEFAULT_SIZE_M)
    return vertices, triangles, ["rgb(176,184,196)"] * len(triangles), notes


def earth_albedo_map() -> np.ndarray | None:
    """Basilisk's Earth albedo map (CERES, 5 x 5 degrees) from the local
    support data, rows from -90 deg latitude, columns from -180 deg
    longitude; None when it is not installed. Never downloads."""
    try:
        from Basilisk.utilities.supportDataTools.dataFetcher import DataFile

        from .kernels import KernelError, cached_path

        path = cached_path(DataFile.AlbedoData.Earth_ALB_2018_CERES_All_5x5)
        grid = np.loadtxt(path, delimiter=",")
    except (ImportError, OSError, ValueError, KernelError, AttributeError):
        return None
    return grid if grid.ndim == 2 and grid.shape[0] >= 2 and grid.shape[1] >= 2 else None


def build_scene(scenario, result, *, base_dir=None, max_frames: int = MAX_FRAMES,
                albedo: np.ndarray | None = None) -> Scene:
    """The scene of ``result`` (a ResultSet of ``scenario``). ``albedo``
    is the body's map when the caller already read it (the view reads it
    once, off the GUI thread)."""
    from .geodesy import ellipsoid_for, geodetic_to_pcpf

    notes: list[str] = []
    crafts_series = []
    for sc in scenario.spacecraft:
        position = result.series.get(f"{sc.name}.position_N")
        if position is None or not len(position.time_s):
            notes.append(f"{sc.name}: no positions in this run")
            continue
        crafts_series.append((sc, position))
    if not crafts_series:
        raise ValueError("the run recorded no spacecraft positions to show")

    start = max(float(p.time_s[0]) for _, p in crafts_series)
    end = min(float(p.time_s[-1]) for _, p in crafts_series)
    if end < start:
        end = start
    count = int(min(max_frames, max(len(p.time_s) for _, p in crafts_series)))
    times = np.linspace(start, end, max(count, 1))

    central = scenario.gravity.central_body
    radius_km = float(CENTRAL_BODY_EQUATORIAL_RADIUS_KM.get(central, 0.0))
    epoch = parse_epoch_utc(scenario.epoch_utc)
    jd = julian_date(epoch, times)

    crafts: list[Craft] = []
    extent = radius_km
    for sc, position in crafts_series:
        stride = max(1, len(position.time_s) // MAX_PATH_POINTS)
        path_km = position.data[::stride, :3] / 1000.0
        vertices_m, triangles, colors, craft_notes = spacecraft_mesh(sc, base_dir)
        attitude = result.series.get(f"{sc.name}.attitude_sigma_BN")
        if attitude is None:
            craft_notes.append(f"{sc.name}: no attitude in this run; drawn aligned with the inertial axes")
        size_km = float(np.max(np.ptp(vertices_m, axis=0))) / 1000.0
        crafts.append(Craft(
            name=sc.name, position_km=_sample(position, times)[:, :3] / 1000.0, path_km=path_km,
            dcm_BN=None if attitude is None else _attitude(attitude, times), vertices_km=vertices_m / 1000.0,
            triangles=triangles, face_colors=colors, size_km=max(size_km, 1e-6), notes=craft_notes))
        extent = max(extent, float(np.max(np.linalg.norm(path_km, axis=1))))
        notes += craft_notes

    rotation = earth_rotation_angle(jd) if central == "earth" else None
    stations = []
    if central == "earth" and radius_km > 0.0:
        ellipsoid = ellipsoid_for(central, radius_km * 1000.0)
        for station in getattr(scenario, "ground_stations", None) or []:
            point = geodetic_to_pcpf(math.radians(station.latitude_deg), math.radians(station.longitude_deg),
                                     station.altitude_m, ellipsoid)
            stations.append((station.name, point / 1000.0))
    if central == "earth":
        sun = sun_direction_eci(jd)
    elif central == "sun":
        sun = None
        notes.append("The Sun is the central body, at the origin")
    else:
        sun = None
        notes.append(f"No Sun direction is drawn around {central}")
    return Scene(epoch_utc=scenario.epoch_utc, times_s=times, body=central, body_radius_km=radius_km,
                 body_rotation_rad=rotation, body_albedo=albedo if central == "earth" else None,
                 crafts=crafts, stations=stations, sun_direction_N=sun, extent_km=1.1 * extent, notes=notes)
