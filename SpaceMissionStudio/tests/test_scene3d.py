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
