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

"""engine.gravity_field: the central body's spherical-harmonics field
(Earth GGM03S, Mars GGM2B) keeps the reference radius of its file (SRelD
K-04). The attached model matches an independent numpy evaluation of the
file's field, Basilisk's own radius would differ from it by
``(R_body/R_file)^2 - 1`` on J2, and a Mars run turns the orbit's node
about Mars's pole at the J2 rate of the file."""

import math
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.schema import load_scenario

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"

# Basilisk 2.12's body constants (gravBodyFactory): equatorial radius and GM.
_BODIES = {
    "earth": (6378136.6, 3.986004415e14),  # [m], [m^3/s^2]
    "mars barycenter": (3396190.0, 4.2828314e13),  # [m], [m^3/s^2]
}
_DEGREE = 4  # degree and order of the comparison: zonal, tesseral and sectorial terms


def _field_path(body: str) -> Path:
    from spacemissionstudio.engine import gravity_field, kernels

    return kernels.cached_path(gravity_field.FIELD_FILES[body])


def _normalised_legendre(degree: int, sin_lat: float) -> np.ndarray:
    """Fully normalised associated Legendre functions P[n][m](sin_lat),
    without the Condon-Shortley phase (the geodesy convention of GGM03S and
    GGM2B), from the unnormalised recursion."""
    cos_lat = math.sqrt(1.0 - sin_lat ** 2)
    p = np.zeros((degree + 1, degree + 1))
    for m in range(degree + 1):
        p[m][m] = math.prod(range(1, 2 * m, 2)) * cos_lat ** m
        if m < degree:
            p[m + 1][m] = (2 * m + 1) * sin_lat * p[m][m]
        for n in range(m + 2, degree + 1):
            p[n][m] = ((2 * n - 1) * sin_lat * p[n - 1][m] - (n + m - 1) * p[n - 2][m]) / (n - m)
    for n in range(degree + 1):
        for m in range(n + 1):
            p[n][m] *= math.sqrt((2.0 - (m == 0)) * (2 * n + 1) * math.factorial(n - m) / math.factorial(n + m))
    return p


def _perturbing_potential(r: np.ndarray, c_bar, s_bar, gm: float, radius: float, degree: int) -> float:
    """sum over n = 2..degree of gm/r (radius/r)^n P[n][m] (C cos m lon + S
    sin m lon), with ``r`` in the body-fixed frame."""
    distance = float(np.linalg.norm(r))
    p = _normalised_legendre(degree, r[2] / distance)
    lon = math.atan2(r[1], r[0])
    total = 0.0
    for n in range(2, degree + 1):
        for m in range(n + 1):
            total += (radius / distance) ** n * p[n][m] * (c_bar[n][m] * math.cos(m * lon)
                                                           + s_bar[n][m] * math.sin(m * lon))
    return gm / distance * total


def _independent_field(r: np.ndarray, c_bar, s_bar, gm: float, radius: float, degree: int) -> np.ndarray:
    """The gradient of :func:`_perturbing_potential` by central differences."""
    step = 10.0  # [m]
    gradient = np.zeros(3)
    for k in range(3):
        offset = np.zeros(3)
        offset[k] = step
        gradient[k] = (_perturbing_potential(r + offset, c_bar, s_bar, gm, radius, degree)
                       - _perturbing_potential(r - offset, c_bar, s_bar, gm, radius, degree)) / (2.0 * step)
    return gradient


def _points(radius: float):
    """Body-fixed points 300 km to 2000 km above the reference radius, at
    several latitudes and longitudes."""
    for altitude, lat_deg, lon_deg in ((300e3, 10.0, 20.0), (800e3, -55.0, 140.0), (2000e3, 75.0, -100.0)):
        lat, lon = math.radians(lat_deg), math.radians(lon_deg)  # [rad]
        yield (radius + altitude) * np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon),
                                              math.sin(lat)])


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("body", sorted(_BODIES))
def test_the_attached_model_is_the_field_of_the_file(body):
    """The model field_model builds (evaluated by Basilisk with the body's
    radius) gives the perturbing acceleration of the file's own field:
    its coefficients at its own reference radius, with the body's GM
    (deviation D-07). Checked against an independent numpy evaluation to
    degree and order 4, to 1e-7."""
    from Basilisk.simulation.gravityEffector import loadGravFromFileToList

    from spacemissionstudio.engine import gravity_field

    body_radius, body_gm = _BODIES[body]
    path = _field_path(body)
    c_bar, s_bar, _, file_radius = loadGravFromFileToList(str(path), _DEGREE)
    model, field = gravity_field.field_model(path, _DEGREE, body_radius, body_gm)
    model.initializeParameters()
    assert field.reference_radius_m == file_radius
    for r in _points(file_radius):
        expected = _independent_field(r, c_bar, s_bar, body_gm, file_radius, _DEGREE)
        got = np.asarray(model.computeField(r.tolist(), _DEGREE, False)).ravel()
        assert np.linalg.norm(got - expected) < 1e-7 * np.linalg.norm(expected)


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("body", sorted(_BODIES))
def test_the_body_radius_alone_would_rescale_the_field(body):
    """Basilisk's own setup puts the body's radius in place of the file's
    (initializeParameters(body), reproduced here by setting radEquator):
    that scales the degree-2-dominated field by (R_body/R_file)^2, 4.8e-4
    too weak for Mars and 9e-8 too strong for Earth (within 10 % of that
    factor, the rest being degrees 3 and 4). The fix removes exactly that."""
    from Basilisk.simulation.gravityEffector import loadGravFromFileToList
    from Basilisk.simulation.sphericalHarmonicsGravityModel import SphericalHarmonicsGravityModel

    from spacemissionstudio.engine import gravity_field

    body_radius, body_gm = _BODIES[body]
    path = _field_path(body)
    c_bar, s_bar, _, file_radius = loadGravFromFileToList(str(path), _DEGREE)
    fixed, _ = gravity_field.field_model(path, _DEGREE, body_radius, body_gm)
    plain = SphericalHarmonicsGravityModel()
    plain.cBar, plain.sBar, plain.maxDeg = c_bar, s_bar, _DEGREE
    plain.radEquator, plain.muBody = body_radius, body_gm  # [m], [m^3/s^2]
    for model in (fixed, plain):
        model.initializeParameters()
    scale = (body_radius / file_radius) ** 2 - 1.0  # [-]
    assert abs(scale) > 5e-8
    for r in _points(file_radius):
        a_fixed = np.asarray(fixed.computeField(r.tolist(), _DEGREE, False)).ravel()
        a_plain = np.asarray(plain.computeField(r.tolist(), _DEGREE, False)).ravel()
        relative = np.linalg.norm(a_plain) / np.linalg.norm(a_fixed) - 1.0  # [-]
        assert relative == pytest.approx(scale, rel=0.1)


def _mars_scenario(degree: int):
    """Template 01 moved to a 500 km circular Mars orbit inclined about 45 deg
    to Mars's equator (Mars's pole is at 37.1 deg inclination and 47.6 deg
    node in N), for one day, recorded once a minute."""
    scenario = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json")
    scenario.gravity.central_body = "mars barycenter"
    scenario.gravity.central_body_degree = degree
    orbit = scenario.spacecraft[0].orbit
    orbit.semi_major_axis_km = 3900.0  # [km]
    orbit.inclination_deg = 82.1  # [deg]
    orbit.raan_deg = 47.6  # [deg]
    scenario.sim_settings.duration_days = 1.0  # [day]
    scenario.sim_settings.record_interval_s = 60.0  # [s]
    scenario.validate()
    return scenario


@pytest.mark.requires_basilisk
def test_a_mars_run_turns_the_node_about_mars_pole_at_the_ggm2b_j2_rate():
    """A day around Mars with the GGM2B field to degree 2: the orbit's node
    on Mars's equator (pole from the recorded planet orientation) turns at
    -1.5 n J2 (R/a)^2 cos i, with GGM2B's J2 and reference radius and a the
    mean of the osculating semi-major axis, within 1 % (first-order theory
    fitted to osculating states; it agrees to 0.7 %). The run records the
    field file as an input, and the field keeps its own radius."""
    from Basilisk.simulation.gravityEffector import loadGravFromFileToList

    from spacemissionstudio.engine.service import SimulationService

    service = SimulationService(_mars_scenario(degree=2))
    service.build(initialize=False)
    recorder = service._planet_state_out_msgs["mars barycenter"].recorder()
    service.scSim.AddModelToTask(service.dyn_task_name, recorder)
    service.initialize()
    result = service.run()

    assert service.gravity_field.path.name == "GGM2BData.txt"
    assert service.gravity_field.reference_radius_m == 3397e3  # [m]
    assert Path(service._data_files["gravity_field"]["path"]).name == "GGM2BData.txt"

    t = result.series["sat-1.position_N"].time_s  # [s]
    r = result.series["sat-1.position_N"].data  # [m]
    v = result.series["sat-1.velocity_N"].data  # [m/s]
    pole = np.asarray(recorder.J20002Pfix).reshape(-1, 3, 3)[0][2]
    h_hat = np.cross(r, v)
    h_hat /= np.linalg.norm(h_hat, axis=1)[:, None]
    cos_i = float(np.mean(h_hat @ pole))
    assert 0.6 < cos_i < 0.8  # about 45 deg to Mars's equator
    x_axis = np.cross(pole, [1.0, 0.0, 0.0])
    x_axis /= np.linalg.norm(x_axis)
    y_axis = np.cross(pole, x_axis)
    node = np.cross(pole[None, :], h_hat)
    node_rate = np.polyfit(t, np.unwrap(np.arctan2(node @ y_axis, node @ x_axis)), 1)[0]  # [rad/s]

    c_bar, _, _, radius = loadGravFromFileToList(str(service.gravity_field.path), 2)
    j2 = -math.sqrt(5.0) * c_bar[2][0]  # [-]
    a = float(np.mean(result.series["sat-1.orbit_elements.semi_major_axis"].data))  # [m]
    expected = -1.5 * math.sqrt(service.mu / a ** 3) * j2 * (radius / a) ** 2 * cos_i  # [rad/s]
    assert node_rate == pytest.approx(expected, rel=0.01)
