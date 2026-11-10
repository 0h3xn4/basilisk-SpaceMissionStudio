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
"""The 3D scene of a run: what the built-in 3D view (``gui.mission_view_widget``)
draws, computed from the run's own results. No new physics: positions and
attitudes are the run's series, sampled on one time grid; everything else
is geometry for display.

* **Frame:** the run's inertial frame N, centred on the central body, in
  kilometres.
* **The central body:** a sphere of its equatorial radius. For Earth it
  turns with the Earth rotation angle (IERS 2010, eq. 5.15, UT1 taken as
  UTC: a visual approximation, about 0.4 degrees from the true Earth-fixed
  frame in 2030 since precession is left out). Ground stations and the
  ground track turn with it.
* **The Sun:** for Earth-centred runs, the direction from the Astronomical
  Almanac's low-precision solar position (about 0.01 degrees from 1950 to
  2050), used for the lighting; for a run around the Sun, the origin.
* **The Moon:** for Earth-centred runs, its position from the Astronomical
  Almanac's low-precision lunar formula (:func:`moon_position_eci`).
* **Spacecraft:** each one's ``position_N``, its attitude ``attitude_sigma_BN``
  when the run recorded one (else drawn aligned with N, and said so), its
  3D model's parts when it has one (else a 1 m cube) with normals for
  shading (:func:`mesh_normals`), its mounted equipment (fields of view,
  thruster plumes), its full path, its ground track, its altitude and
  speed.
* **Ground stations:** each one's line of sight to each spacecraft, frame
  by frame: the spacecraft's elevation above the station's horizon at or
  above the station's ``min_elevation_deg`` (:func:`elevation_deg`).

:func:`build_scene` is Basilisk-free and returns plain arrays, so the view
and the tests use the same numbers. It is :func:`empty_scene` (the body,
the spacecraft's models, the stations) plus :func:`extend_scene` (the
frames and what follows from them); a run shown live
(``engine.live_view``) is built the same way, its frames added as they
come.
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
CREASE_DEG = 30.0  # [deg] faces meeting at a sharper angle than this keep a hard edge
_J2000_JD = 2451545.0  # [day] Julian date of J2000.0
_UNIX_EPOCH_JD = 2440587.5  # [day] Julian date of 1970-01-01T00:00:00
_DEFAULT_SIZE_M = 1.0  # [m] edge of the cube drawn for a spacecraft without a 3D model
_EARTH_RADIUS_KM = 6378.14  # [km] the Earth radius of the Almanac's lunar parallax
_DEFAULT_RGB = (176 / 255.0, 184 / 255.0, 196 / 255.0)  # [-] the cube's grey


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
    face_rgb: np.ndarray | None = None  # (t, 3) per triangle, 0 to 1
    velocity_km_s: np.ndarray | None = None  # (n, 3) on the scene's frames
    altitude_km: np.ndarray | None = None  # (n,) above the body's ellipsoid (Earth) or sphere
    ground_track_deg: np.ndarray | None = None  # (m, 2) geocentric latitude, longitude of the path's points
    equipment: list[dict] = field(default_factory=list)  # mounted items with a direction (body frame, km)


@dataclass
class Scene:
    """Everything the 3D view draws, on ``times_s`` (seconds from the epoch)."""

    epoch_utc: str
    times_s: np.ndarray  # (n,)
    body: str
    body_radius_km: float
    body_rotation_rad: np.ndarray | None  # (n,) angle of the body-fixed frame about N's z, or None
    crafts: list[Craft]
    stations: list[tuple[str, np.ndarray]]  # name, body-fixed position [km]
    sun_direction_N: np.ndarray | None  # (n, 3) unit vectors, or None
    extent_km: float  # half-width of a box holding the body and every path
    notes: list[str] = field(default_factory=list)
    moon_position_km: np.ndarray | None = None  # (n, 3) Earth-centred runs only
    station_min_elevation_deg: list[float] = field(default_factory=list)  # [deg] per station
    station_visible: np.ndarray | None = None  # (stations, crafts, n) line of sight
    station_up: list[np.ndarray] = field(default_factory=list)  # [-] each station's local vertical, body-fixed
    flattening: float = 0.0  # [-] of the central body's ellipsoid


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


def moon_ecliptic(jd: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The Moon's geocentric ecliptic longitude [deg], latitude [deg] and
    distance [km], mean equinox of date: the Astronomical Almanac's
    low-precision formula (section D), about 0.3 degrees in longitude,
    0.2 degrees in latitude and 0.003 degrees in horizontal parallax
    (about 0.3 % of the distance) from 1950 to 2050."""
    t = (np.asarray(jd, dtype=float) - _J2000_JD) / 36525.0
    d = np.radians
    longitude = (218.32 + 481267.881 * t + 6.29 * np.sin(d(135.0 + 477198.87 * t))
                 - 1.27 * np.sin(d(259.3 - 413335.36 * t)) + 0.66 * np.sin(d(235.7 + 890534.22 * t))
                 + 0.21 * np.sin(d(269.9 + 954397.74 * t)) - 0.19 * np.sin(d(357.5 + 35999.05 * t))
                 - 0.11 * np.sin(d(186.5 + 966404.03 * t)))
    latitude = (5.13 * np.sin(d(93.3 + 483202.02 * t)) + 0.28 * np.sin(d(228.2 + 960400.89 * t))
                - 0.28 * np.sin(d(318.3 + 6003.15 * t)) - 0.17 * np.sin(d(217.6 - 407332.21 * t)))
    parallax = (0.9508 + 0.0518 * np.cos(d(135.0 + 477198.87 * t)) + 0.0095 * np.cos(d(259.3 - 413335.36 * t))
                + 0.0078 * np.cos(d(235.7 + 890534.22 * t)) + 0.0028 * np.cos(d(269.9 + 954397.74 * t)))
    return np.mod(longitude, 360.0), latitude, _EARTH_RADIUS_KM / np.sin(d(parallax))


def moon_position_eci(jd: np.ndarray) -> np.ndarray:
    """The Moon's position [km] from the Earth's centre, equatorial
    (equator and equinox of date, within the formula's accuracy of J2000
    for display): :func:`moon_ecliptic` turned by the mean obliquity."""
    longitude, latitude, distance = moon_ecliptic(jd)
    lam, beta = np.radians(longitude), np.radians(latitude)
    obliquity = np.radians(23.439 - 0.0000004 * (np.asarray(jd, dtype=float) - _J2000_JD))
    x = np.cos(beta) * np.cos(lam)
    y = np.cos(obliquity) * np.cos(beta) * np.sin(lam) - np.sin(obliquity) * np.sin(beta)
    z = np.sin(obliquity) * np.cos(beta) * np.sin(lam) + np.cos(obliquity) * np.sin(beta)
    return distance[:, None] * np.column_stack([x, y, z])


def mrp_to_dcm(sigma: np.ndarray) -> np.ndarray:
    """``[BN]`` of each MRP set in ``sigma`` (n, 3) (Schaub & Junkins)."""
    sigma = np.asarray(sigma, dtype=float).reshape(-1, 3)
    s2 = np.einsum("ij,ij->i", sigma, sigma)
    tilde = np.zeros((len(sigma), 3, 3))
    tilde[:, 0, 1], tilde[:, 0, 2], tilde[:, 1, 2] = -sigma[:, 2], sigma[:, 1], -sigma[:, 0]
    tilde[:, 1, 0], tilde[:, 2, 0], tilde[:, 2, 1] = sigma[:, 2], -sigma[:, 1], sigma[:, 0]
    square = tilde @ tilde
    return np.eye(3) + (8.0 * square - 4.0 * (1.0 - s2)[:, None, None] * tilde) / ((1.0 + s2) ** 2)[:, None, None]


def rotate_z(vectors: np.ndarray, angle_rad: np.ndarray) -> np.ndarray:
    """Each of ``vectors`` (n, 3) turned by its ``angle_rad`` (n,) about z
    (a body-fixed vector to N, for the body's rotation angle)."""
    vectors = np.asarray(vectors, dtype=float)
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.column_stack([c * vectors[:, 0] - s * vectors[:, 1], s * vectors[:, 0] + c * vectors[:, 1],
                            vectors[:, 2]])


def mesh_normals(vertices: np.ndarray, triangles: np.ndarray,
                 crease_deg: float = CREASE_DEG) -> tuple[np.ndarray, np.ndarray]:
    """Per-corner ``(positions, normals)``, each (3 t, 3), of a triangle
    mesh, for shading: a corner's normal is the area-weighted mean of the
    normals of the faces at its vertex that meet its own face at less
    than ``crease_deg`` (smooth across a curved surface, a hard edge where
    a box turns a corner). A face without area gets its neighbours' or
    the +z normal."""
    vertices = np.asarray(vertices, dtype=float)
    triangles = np.asarray(triangles, dtype=int).reshape(-1, 3)
    corners = vertices[triangles]  # (t, 3, 3)
    weighted = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])  # twice the area
    area = np.linalg.norm(weighted, axis=1)
    unit = np.divide(weighted, area[:, None], out=np.zeros_like(weighted), where=area[:, None] > 0.0)
    cos_crease = math.cos(math.radians(crease_deg))
    faces_at: dict[int, list[int]] = {}
    for face, corner_vertices in enumerate(triangles):
        for vertex in corner_vertices:
            faces_at.setdefault(int(vertex), []).append(face)
    normals = np.zeros((len(triangles), 3, 3))
    for face, corner_vertices in enumerate(triangles):
        for corner, vertex in enumerate(corner_vertices):
            around = np.array(faces_at[int(vertex)])
            keep = around[unit[around] @ unit[face] >= cos_crease] if area[face] > 0.0 else around
            total = weighted[keep].sum(axis=0)
            length = np.linalg.norm(total)
            normals[face, corner] = total / length if length > 0.0 else (0.0, 0.0, 1.0)
    return corners.reshape(-1, 3), normals.reshape(-1, 3)


def ground_track_deg(position_km: np.ndarray, rotation_rad: np.ndarray) -> np.ndarray:
    """Geocentric latitude and longitude [deg] (n, 2), longitude in
    [-180, 180), of the points under ``position_km`` (n, 3, frame N) on a
    body turned by ``rotation_rad`` (n,)."""
    fixed = rotate_z(position_km, -np.asarray(rotation_rad, dtype=float))
    latitude = np.degrees(np.arctan2(fixed[:, 2], np.hypot(fixed[:, 0], fixed[:, 1])))
    longitude = np.mod(np.degrees(np.arctan2(fixed[:, 1], fixed[:, 0])) + 180.0, 360.0) - 180.0
    return np.column_stack([latitude, longitude])


def geodetic_up(latitude_deg: float, longitude_deg: float) -> np.ndarray:
    """The unit normal of the ellipsoid (the local vertical) at a geodetic
    latitude and longitude, body-fixed."""
    lat, lon = math.radians(latitude_deg), math.radians(longitude_deg)
    return np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])


def elevation_deg(station_km: np.ndarray, up: np.ndarray, rotation_rad: np.ndarray,
                  position_km: np.ndarray) -> np.ndarray:
    """Elevation [deg] (n,) of ``position_km`` (n, 3, frame N) above the
    horizon of a station at body-fixed ``station_km`` with local vertical
    ``up``, the body turned by ``rotation_rad`` (n,)."""
    count = len(position_km)
    site = rotate_z(np.tile(station_km, (count, 1)), rotation_rad)
    vertical = rotate_z(np.tile(up, (count, 1)), rotation_rad)
    line = np.asarray(position_km, dtype=float) - site
    distance = np.linalg.norm(line, axis=1)
    sine = np.divide(np.einsum("ij,ij->i", line, vertical), distance, out=np.zeros(count), where=distance > 0.0)
    return np.degrees(np.arcsin(np.clip(sine, -1.0, 1.0)))


def altitude_km(position_km: np.ndarray, equatorial_radius_km: float, flattening: float = 0.0) -> np.ndarray:
    """Height [km] (n,) of ``position_km`` (n, 3) above an ellipsoid of
    revolution about z (a sphere when ``flattening`` is 0); the frame's
    turn about z does not matter. Bowring's iteration, three steps
    (millimetres for orbits)."""
    position_km = np.asarray(position_km, dtype=float)
    a = float(equatorial_radius_km)
    e2 = flattening * (2.0 - flattening)
    p = np.hypot(position_km[:, 0], position_km[:, 1])
    z = position_km[:, 2]
    if e2 == 0.0:
        return np.hypot(p, z) - a
    latitude = np.arctan2(z, p * (1.0 - e2))
    for _ in range(3):
        n = a / np.sqrt(1.0 - e2 * np.sin(latitude) ** 2)
        height = np.where(np.abs(latitude) < np.pi / 4, p / np.cos(latitude) - n,
                          z / np.sin(np.where(latitude == 0.0, 1.0, latitude)) - n * (1.0 - e2))
        latitude = np.arctan2(z, p * (1.0 - e2 * n / (n + height)))
    n = a / np.sqrt(1.0 - e2 * np.sin(latitude) ** 2)
    return np.where(np.abs(latitude) < np.pi / 4, p / np.cos(latitude) - n,
                    z / np.sin(np.where(latitude == 0.0, 1.0, latitude)) - n * (1.0 - e2))


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


def _rgb_floats(colors: list[str]) -> np.ndarray:
    """``"rgb(r,g,b)"`` strings as (t, 3) floats from 0 to 1."""
    if not colors:
        return np.zeros((0, 3))
    return np.array([[int(v) / 255.0 for v in c[c.index("(") + 1:c.index(")")].split(",")] for c in colors])


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
    return vertices, triangles, [_rgb(_DEFAULT_RGB)] * len(triangles), notes


def equipment(sc) -> list[dict]:
    """The mounted items of ``sc`` that point somewhere (``model3d.equipment``):
    name, kind, position [km] and unit boresight in the body frame, the
    full field-of-view angle [deg] (or None) and the plume half-angle
    [deg] (or None). An item without a position sits at point B."""
    try:
        from ..model3d.equipment import mounted_items

        items = mounted_items(sc)
    except Exception:  # noqa: BLE001 -- equipment that cannot be placed is not drawn; the run is not affected
        return []
    found = []
    for item in items:
        if item.boresight_b is None:
            continue
        boresight = np.asarray(item.boresight_b, dtype=float)
        if not np.all(np.isfinite(boresight)) or np.linalg.norm(boresight) == 0.0:
            continue
        position = np.zeros(3) if item.position_b_m is None else np.asarray(item.position_b_m, dtype=float)
        found.append({"name": item.name, "kind": item.kind, "position_km": position / 1000.0,
                      "boresight": boresight / np.linalg.norm(boresight),
                      "fov_deg": None if item.field_of_view_deg is None else float(item.field_of_view_deg),
                      "plume_half_deg": None if item.plume_half_angle_deg is None
                      else float(item.plume_half_angle_deg)})
    return found


def _body_frames(central: str, epoch: datetime, times_s: np.ndarray):
    """The central body's rotation angle [rad] (Earth only, else None),
    the Sun direction and the Moon's position [km] (Earth-centred runs
    only, else None) at ``times_s``."""
    if central != "earth":
        return None, None, None
    jd = julian_date(epoch, times_s)
    return earth_rotation_angle(jd), sun_direction_eci(jd), moon_position_eci(jd)


def empty_scene(scenario, crafts: list[tuple[object, bool]], *, base_dir=None) -> Scene:
    """The scene of ``scenario`` without a frame: its central body,
    stations, notes and ``crafts`` (each a spacecraft config and whether
    the run records its attitude), with their models and equipment.
    :func:`extend_scene` adds the frames."""
    from .geodesy import ellipsoid_for, geodetic_to_pcpf

    central = scenario.gravity.central_body
    radius_km = float(CENTRAL_BODY_EQUATORIAL_RADIUS_KM.get(central, 0.0))
    ellipsoid = ellipsoid_for(central, radius_km * 1000.0)
    earth = central == "earth"
    notes: list[str] = []
    built: list[Craft] = []
    for sc, has_attitude in crafts:
        vertices_m, triangles, colors, craft_notes = spacecraft_mesh(sc, base_dir)
        if not has_attitude:
            craft_notes.append(f"{sc.name}: no attitude in this run; drawn aligned with the inertial axes")
        size_km = float(np.max(np.ptp(vertices_m, axis=0))) / 1000.0
        built.append(Craft(
            name=sc.name, position_km=np.zeros((0, 3)), path_km=np.zeros((0, 3)),
            dcm_BN=np.zeros((0, 3, 3)) if has_attitude else None, vertices_km=vertices_m / 1000.0,
            triangles=triangles, face_colors=colors, size_km=max(size_km, 1e-6), notes=craft_notes,
            face_rgb=_rgb_floats(colors), velocity_km_s=np.zeros((0, 3)),
            altitude_km=np.zeros(0) if radius_km > 0.0 else None,
            ground_track_deg=np.zeros((0, 2)) if earth else None, equipment=equipment(sc)))
        notes += craft_notes

    stations, ups, minimum = [], [], []
    if earth and radius_km > 0.0:
        for station in getattr(scenario, "ground_stations", None) or []:
            point = geodetic_to_pcpf(math.radians(station.latitude_deg), math.radians(station.longitude_deg),
                                     station.altitude_m, ellipsoid) / 1000.0
            stations.append((station.name, point))
            ups.append(geodetic_up(station.latitude_deg, station.longitude_deg))
            minimum.append(float(station.min_elevation_deg))
    if central == "sun":
        notes.append("The Sun is the central body, at the origin")
    elif not earth:
        notes.append(f"No Sun direction is drawn around {central}")
    return Scene(epoch_utc=scenario.epoch_utc, times_s=np.zeros(0), body=central, body_radius_km=radius_km,
                 body_rotation_rad=np.zeros(0) if earth else None, crafts=built, stations=stations,
                 sun_direction_N=np.zeros((0, 3)) if earth else None, extent_km=1.1 * radius_km, notes=notes,
                 moon_position_km=np.zeros((0, 3)) if earth else None, station_min_elevation_deg=minimum,
                 station_visible=np.zeros((len(stations), len(built), 0), dtype=bool), station_up=ups,
                 flattening=ellipsoid.flattening)


def extend_scene(scene: Scene, times_s: np.ndarray, position_km: np.ndarray, velocity_km_s: np.ndarray,
                 dcm_BN: list, *, grow_path: bool = True) -> Scene:
    """Add frames at ``times_s`` (n,) to ``scene``, in place: each
    spacecraft's position [km] and velocity [km/s] (n, k, 3) and DCM
    ``[BN]`` (a (n, 3, 3) array per spacecraft, None for one without an
    attitude); from them, as for a whole run, the body's rotation, the Sun,
    the Moon, the altitudes and the stations' line of sight; with
    ``grow_path``, the frames' positions also extend each path and ground
    track (a live run: its path is its frames). Returns ``scene``."""
    times_s = np.asarray(times_s, dtype=float)
    position_km = np.asarray(position_km, dtype=float).reshape(len(times_s), len(scene.crafts), 3)
    velocity_km_s = np.asarray(velocity_km_s, dtype=float).reshape(len(times_s), len(scene.crafts), 3)
    rotation, sun, moon = _body_frames(scene.body, parse_epoch_utc(scene.epoch_utc), times_s)
    scene.times_s = np.concatenate([scene.times_s, times_s])
    if rotation is not None:
        scene.body_rotation_rad = np.concatenate([scene.body_rotation_rad, rotation])
        scene.sun_direction_N = np.concatenate([scene.sun_direction_N, sun])
        scene.moon_position_km = np.concatenate([scene.moon_position_km, moon])
    extent = scene.extent_km / 1.1  # [km]
    for k, craft in enumerate(scene.crafts):
        position = position_km[:, k]
        craft.position_km = np.concatenate([craft.position_km, position])
        craft.velocity_km_s = np.concatenate([craft.velocity_km_s, velocity_km_s[:, k]])
        if craft.dcm_BN is not None:
            craft.dcm_BN = np.concatenate([craft.dcm_BN, np.asarray(dcm_BN[k], dtype=float).reshape(-1, 3, 3)])
        if craft.altitude_km is not None:
            craft.altitude_km = np.concatenate([craft.altitude_km, altitude_km(position, scene.body_radius_km,
                                                                                 scene.flattening)])
        if grow_path:
            craft.path_km = np.concatenate([craft.path_km, position])
            if craft.ground_track_deg is not None and rotation is not None:
                craft.ground_track_deg = np.concatenate([craft.ground_track_deg, ground_track_deg(position, rotation)])
            if len(position):
                extent = max(extent, float(np.max(np.linalg.norm(position, axis=1))))
    scene.extent_km = 1.1 * extent
    visible = [[elevation_deg(point, up, rotation, position_km[:, k]) >= minimum for k in range(len(scene.crafts))]
               for (_name, point), up, minimum in zip(scene.stations, scene.station_up,
                                                      scene.station_min_elevation_deg)]
    scene.station_visible = np.concatenate([scene.station_visible, np.array(visible, dtype=bool).reshape(
        len(scene.stations), len(scene.crafts), len(times_s))], axis=2)
    return scene


def build_scene(scenario, result, *, base_dir=None, max_frames: int = MAX_FRAMES) -> Scene:
    """The scene of ``result`` (a ResultSet of ``scenario``)."""
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

    attitudes = [result.series.get(f"{sc.name}.attitude_sigma_BN") for sc, _ in crafts_series]
    scene = empty_scene(scenario, [(sc, attitude is not None) for (sc, _), attitude in zip(crafts_series, attitudes)],
                        base_dir=base_dir)
    scene.notes = notes + scene.notes
    positions, velocities = [], []
    for sc, position in crafts_series:
        position_km = _sample(position, times)[:, :3] / 1000.0
        velocity = result.series.get(f"{sc.name}.velocity_N")
        if velocity is not None and len(velocity.time_s):
            velocity_km_s = _sample(velocity, times)[:, :3] / 1000.0
        elif len(times) > 1 and times[-1] > times[0]:
            velocity_km_s = np.gradient(position_km, times, axis=0)
        else:
            velocity_km_s = np.zeros_like(position_km)
        positions.append(position_km)
        velocities.append(velocity_km_s)
    extend_scene(scene, times, np.stack(positions, axis=1), np.stack(velocities, axis=1),
                 [None if attitude is None else _attitude(attitude, times) for attitude in attitudes], grow_path=False)

    epoch = parse_epoch_utc(scenario.epoch_utc)
    extent = scene.body_radius_km  # [km]
    for craft, (_sc, position) in zip(scene.crafts, crafts_series):
        stride = max(1, len(position.time_s) // MAX_PATH_POINTS)
        craft.path_km = position.data[::stride, :3] / 1000.0
        if scene.body_rotation_rad is not None:
            path_jd = julian_date(epoch, position.time_s[::stride])
            craft.ground_track_deg = ground_track_deg(craft.path_km, earth_rotation_angle(path_jd))
        extent = max(extent, float(np.max(np.linalg.norm(craft.path_km, axis=1))))
    scene.extent_km = 1.1 * extent
    return scene
