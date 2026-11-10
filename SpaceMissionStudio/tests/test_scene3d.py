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

"""The scene the built-in 3D view draws (``engine.scene3d``): the Earth's
rotation angle and the Sun's direction against published values, the
attitude from the run's MRPs, and a run's spacecraft, stations and frames
placed from its own series."""

import math
from datetime import datetime

import numpy as np
import pytest

from spacemissionstudio import api
from spacemissionstudio.constants import EARTH_EQUATORIAL_RADIUS_M
from spacemissionstudio.engine import scene3d
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.schema.scenario import GroundStationConfig

_RADIUS_M = 7000e3  # [m] circular orbit radius of the synthetic run
_PERIOD_S = 2.0 * math.pi * math.sqrt(_RADIUS_M ** 3 / 3.986004418e14)  # [s]


def test_the_earth_rotation_angle_at_j2000():
    """IERS 2010 eq. 5.15: at JD(UT1) 2451545.0 the angle is
    2 pi x 0.7790572732640, 280.4606 degrees; it gains one turn plus
    0.00273781191135448 of a turn a day."""
    era = scene3d.earth_rotation_angle(np.array([2451545.0, 2451546.0]))
    assert math.degrees(era[0]) == pytest.approx(280.46061837504, abs=1e-9)
    assert math.degrees(era[1] - era[0]) == pytest.approx(360.0 * 0.00273781191135448, abs=1e-6)


@pytest.mark.parametrize("moment,right_ascension_deg,declination_deg", [
    (datetime(2030, 3, 20, 13, 51), 0.0, 0.0),  # March equinox 2030 (US Naval Observatory)
    (datetime(2030, 6, 21, 7, 31), 90.0, 23.436),  # June solstice 2030
])
def test_the_sun_direction_at_an_equinox_and_a_solstice(moment, right_ascension_deg, declination_deg):
    """Within 0.05 degrees of the Sun's position at the 2030 equinox and
    solstice."""
    direction = scene3d.sun_direction_eci(scene3d.julian_date(moment, np.array([0.0])))[0]
    assert np.linalg.norm(direction) == pytest.approx(1.0)
    assert math.degrees(math.asin(direction[2])) == pytest.approx(declination_deg, abs=0.05)
    ra = math.degrees(math.atan2(direction[1], direction[0])) % 360.0
    assert min(abs(ra - right_ascension_deg), 360.0 - abs(ra - right_ascension_deg)) < 0.05


def test_the_attitude_matrix_from_mrps():
    """sigma = tan(phi/4) about z: [BN] is the rotation by phi about z; the
    same matrices the model analyses use."""
    from spacemissionstudio.analyses.run_geometry import mrp_to_dcm as analyses_dcm

    phi = math.radians(90.0)
    dcm = scene3d.mrp_to_dcm(np.array([[0.0, 0.0, math.tan(phi / 4.0)]]))[0]
    np.testing.assert_allclose(dcm, [[0, 1, 0], [-1, 0, 0], [0, 0, 1]], atol=1e-12)
    sigma = np.array([[0.1, -0.2, 0.3], [0.5, 0.4, -0.6]])
    np.testing.assert_allclose(scene3d.mrp_to_dcm(sigma), analyses_dcm(sigma), atol=1e-12)


def _run(with_attitude: bool, samples: int = 400):
    scenario = api.load(api.template("01_two_body_circular_orbit"))
    scenario.ground_stations = [GroundStationConfig(name="equator-gs", latitude_deg=0.0, longitude_deg=0.0)]
    name = scenario.spacecraft[0].name
    t = np.linspace(0.0, _PERIOD_S, samples)
    angle = 2.0 * math.pi * t / _PERIOD_S
    result = ResultSet(scenario_name=scenario.name)
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"),
                          np.column_stack([_RADIUS_M * np.cos(angle), _RADIUS_M * np.sin(angle), 0 * t]), units="m"))
    if with_attitude:
        sigma = np.column_stack([0 * t, 0 * t, np.tan(angle / 4.0)])  # B turns with the orbit about z
        result.add(TimeSeries(f"{name}.attitude_sigma_BN", t, ("s1", "s2", "s3"), sigma))
    return scenario, result, name


def test_a_run_is_placed_from_its_own_series():
    """One time grid over the run; positions are the run's (km), the
    attitude its nearest MRP; no 3D model: a 1 m cube, said so in no note;
    the station on the Earth's surface; the scene holds every path."""
    scenario, result, name = _run(with_attitude=True)
    scene = scene3d.build_scene(scenario, result, max_frames=100)
    assert scene.body == "earth" and scene.body_radius_km == pytest.approx(EARTH_EQUATORIAL_RADIUS_M / 1000.0)
    assert len(scene.times_s) == 100 and scene.times_s[-1] == pytest.approx(_PERIOD_S)
    craft = scene.crafts[0]
    assert craft.name == name and craft.position_km.shape == (100, 3)
    np.testing.assert_allclose(np.linalg.norm(craft.position_km, axis=1), _RADIUS_M / 1000.0, rtol=1e-3)
    half_turn = np.argmin(np.abs(scene.times_s - _PERIOD_S / 2.0))
    np.testing.assert_allclose(craft.dcm_BN[half_turn], np.diag([-1.0, -1.0, 1.0]), atol=0.05)
    assert craft.vertices_km.shape == (8, 3) and craft.size_km == pytest.approx(0.001)
    assert len(craft.face_colors) == len(craft.triangles) == 12
    (station, point), = scene.stations
    assert station == "equator-gs" and np.linalg.norm(point) == pytest.approx(scene.body_radius_km, rel=1e-6)
    assert scene.extent_km == pytest.approx(1.1 * _RADIUS_M / 1000.0, rel=1e-6)
    assert scene.sun_direction_N.shape == (100, 3) and scene.body_rotation_rad.shape == (100,)
    assert scene.notes == []


def test_a_run_without_attitude_says_so():
    scenario, result, name = _run(with_attitude=False)
    scene = scene3d.build_scene(scenario, result)
    assert scene.crafts[0].dcm_BN is None
    assert any("no attitude" in note for note in scene.notes)
    assert len(scene.times_s) == 400  # fewer samples than the frame limit: one frame each


def test_a_run_without_positions_cannot_be_shown():
    scenario, _result, _name = _run(with_attitude=False)
    with pytest.raises(ValueError, match="no spacecraft positions"):
        scene3d.build_scene(scenario, ResultSet(scenario_name=scenario.name))


def test_a_spacecraft_is_drawn_from_its_3d_model():
    """Template 28's octagonal bus: every visible part's triangles, each
    with its part's colour, in the body frame."""
    path = api.template("28_octagonal_bus_3d_model")
    scenario = api.load(path)
    vertices, triangles, colours, notes = scene3d.spacecraft_mesh(scenario.spacecraft[0], path.parent)
    assert notes == [] and len(vertices) > 8 and len(colours) == len(triangles)
    assert triangles.max() < len(vertices) and len(set(colours)) > 1
    assert np.ptp(vertices, axis=0).max() < 20.0  # [m] a spacecraft, in metres


def test_the_moon_against_meeus_example_47a():
    """Meeus, Astronomical Algorithms (2nd ed.), example 47.a, 1992-04-12
    0h TD (JD 2448724.5): longitude 133.162655 deg, latitude -3.229126 deg,
    distance 368409.7 km. The Almanac's low-precision formula is within its
    stated 0.3 deg, 0.2 deg and 0.3 % (it gives 133.257 deg, -3.307 deg,
    368077 km)."""
    longitude, latitude, distance = scene3d.moon_ecliptic(np.array([2448724.5]))
    assert longitude[0] == pytest.approx(133.162655, abs=0.3)
    assert latitude[0] == pytest.approx(-3.229126, abs=0.2)
    assert distance[0] == pytest.approx(368409.7, rel=0.003)
    position = scene3d.moon_position_eci(np.array([2448724.5]))[0]
    assert np.linalg.norm(position) == pytest.approx(distance[0])
    # Meeus 47.a also gives the apparent right ascension 134.688470 deg and
    # declination 13.768368 deg (true equator of date; nutation and
    # aberration, about 0.01 deg, are left out here).
    assert math.degrees(math.atan2(position[1], position[0])) == pytest.approx(134.688470, abs=0.35)
    assert math.degrees(math.asin(position[2] / np.linalg.norm(position))) == pytest.approx(13.768368, abs=0.25)


def test_mesh_normals_keep_hard_edges_and_smooth_gentle_ones():
    """A cube's corners take their own face's normal (90 degree edges);
    two faces meeting at 10 degrees share an averaged normal along their
    edge."""
    vertices, triangles = scene3d._cube(1.0)
    positions, normals = scene3d.mesh_normals(vertices, triangles)
    assert positions.shape == normals.shape == (36, 3)
    corners = vertices[triangles]
    faces = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    faces /= np.linalg.norm(faces, axis=1)[:, None]
    np.testing.assert_allclose(normals.reshape(12, 3, 3), np.repeat(faces[:, None, :], 3, axis=1), atol=1e-12)
    tilt = math.radians(10.0)
    vertices = np.array([[0, 0, 0], [0, 1, 0], [-1, 0, 0], [math.cos(tilt), 0, math.sin(tilt)]], float)
    _positions, normals = scene3d.mesh_normals(vertices, np.array([[0, 1, 2], [0, 3, 1]]))
    shared = normals[0]  # vertex 0, on the shared edge
    assert math.degrees(math.acos(shared @ np.array([0.0, 0.0, 1.0]))) == pytest.approx(5.0, abs=0.01)
    np.testing.assert_allclose(normals[2], [0.0, 0.0, 1.0], atol=1e-12)  # vertex 2: its face only


def test_the_ground_track_and_a_station_s_line_of_sight():
    """The point under a spacecraft on the x axis is at 0 deg, 0 deg; a
    quarter turn of the Earth later it is at -90 deg longitude. A station
    at 0 deg, 0 deg sees a spacecraft straight above at 90 deg elevation
    and one a quarter of the way round below its horizon."""
    above = np.array([[7000.0, 0.0, 0.0], [7000.0, 0.0, 0.0], [0.0, 0.0, 7000.0]])
    track = scene3d.ground_track_deg(above, np.array([0.0, math.pi / 2.0, 0.0]))
    np.testing.assert_allclose(track, [[0.0, 0.0], [0.0, -90.0], [90.0, 0.0]], atol=1e-9)
    station = np.array([6378.137, 0.0, 0.0])
    up = scene3d.geodetic_up(0.0, 0.0)
    elevation = scene3d.elevation_deg(station, up, np.zeros(2), np.array([[7000.0, 0.0, 0.0], [0.0, 7000.0, 0.0]]))
    assert elevation[0] == pytest.approx(90.0) and elevation[1] < 0.0
    turned = scene3d.elevation_deg(station, up, np.array([math.pi / 2.0]), np.array([[0.0, 7000.0, 0.0]]))
    assert turned[0] == pytest.approx(90.0)


def test_altitude_above_the_ellipsoid():
    """WGS-84: 621.863 km above the equator at 7000 km, 643.248 km above
    the pole (polar radius 6356.752 km); a sphere: the radius subtracted."""
    flattening = 1.0 / 298.257223563
    heights = scene3d.altitude_km(np.array([[7000.0, 0.0, 0.0], [0.0, 0.0, 7000.0]]), 6378.137, flattening)
    np.testing.assert_allclose(heights, [621.863, 7000.0 - 6356.752314], atol=1e-6)
    assert scene3d.altitude_km(np.array([[0.0, 3000.0, 4000.0]]), 3396.2)[0] == pytest.approx(5000.0 - 3396.2)


def test_the_scene_carries_what_the_page_draws():
    """Velocity (the path's derivative without a velocity series), speed
    and altitude, the ground track, the Moon, and each station's line of
    sight: visible exactly when the elevation is at or above the station's
    minimum elevation (10 deg by default)."""
    scenario, result, _name = _run(with_attitude=True)
    scene = scene3d.build_scene(scenario, result, max_frames=200)
    craft = scene.crafts[0]
    speed = math.sqrt(3.986004418e14 / _RADIUS_M) / 1000.0  # [km/s]
    np.testing.assert_allclose(np.linalg.norm(craft.velocity_km_s[5:-5], axis=1), speed, rtol=1e-3)
    np.testing.assert_allclose(craft.altitude_km, _RADIUS_M / 1000.0 - EARTH_EQUATORIAL_RADIUS_M / 1000.0,
                               atol=0.5)  # an equatorial orbit; frames between samples are on chords
    assert craft.ground_track_deg.shape == (len(craft.path_km), 2)
    np.testing.assert_allclose(craft.ground_track_deg[:, 0], 0.0, atol=1e-9)
    assert craft.face_rgb.shape == (12, 3) and craft.equipment == []
    assert scene.moon_position_km.shape == (200, 3)
    assert 356000.0 < np.linalg.norm(scene.moon_position_km[0]) < 407000.0  # [km] perigee to apogee
    assert scene.station_min_elevation_deg == [10.0] and scene.station_visible.shape == (1, 1, 200)
    (_station, point), = scene.stations
    elevation = scene3d.elevation_deg(point, scene3d.geodetic_up(0.0, 0.0), scene.body_rotation_rad,
                                      craft.position_km)
    np.testing.assert_array_equal(scene.station_visible[0, 0], elevation >= 10.0)
    assert scene.station_visible.any() and not scene.station_visible.all()


def test_the_mounted_equipment_is_placed_in_the_body_frame():
    """Template 32: the star tracker's 20 deg field of view and the
    thruster's 15 deg plume, each with a unit boresight, in kilometres."""
    scenario = api.load(api.template("32_smallsat_design_checks"))
    items = {item["name"]: item for item in scene3d.equipment(scenario.spacecraft[0])}
    assert items["st-1"]["fov_deg"] == 20.0 and items["sk thruster"]["plume_half_deg"] == 15.0
    for item in items.values():
        assert np.linalg.norm(item["boresight"]) == pytest.approx(1.0)
        assert np.all(np.abs(item["position_km"]) < 0.01)  # [km] on a small satellite
