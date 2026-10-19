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

"""gravity.albedo: the sunlight the central body reflects onto the coarse
sun sensors (Basilisk's albedo module with the CERES 2018 map of Earth or
the TES map of Mars). The sensors add exactly the recorded albedo to their
output, and the albedo matches an independent integral of the same map
(Lambertian reflection, written here in numpy)."""

import math
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.schema import ScenarioValidationError, load_scenario

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"


def _template_14(albedo: bool, central_body: str = "earth", use_css_estimation: bool = True):
    scenario = load_scenario(_TEMPLATES / "14_css_sun_heading_estimation.json")
    scenario.gravity.albedo = albedo
    scenario.sim_settings.record_interval_s = 10.0  # [s]
    sc = scenario.spacecraft[0]
    sc.fsw_params["use_css_estimation"] = use_css_estimation
    if central_body != "earth":
        scenario.gravity.central_body = central_body
        sc.orbit.semi_major_axis_km = 3900.0  # [km] about 500 km above Mars
        sc.orbit.eccentricity = 0.0
    scenario.validate()
    return scenario


def _run(scenario):
    from spacemissionstudio.engine.service import SimulationService

    service = SimulationService(scenario)
    return service, service.run()


def _independent_albedo(map_path: Path, radius_m: float, r_sc_p: np.ndarray, r_sun_p: np.ndarray,
                        dcm_np: np.ndarray, n_hat_n: np.ndarray, half_fov_rad: float) -> float:
    """sum over the map's cells of a f1 f2 f3 dA / (pi d^2): f1 the cosine
    of the Sun at the cell, f2 of the sensor at the cell, f3 of the cell at
    the sensor (zero outside its field of view). Rows run from the south
    pole north, columns from 180 deg W east; the planet is a sphere of
    ``radius_m``. Positions are relative to the planet, in N."""
    albedo_map = np.loadtxt(map_path, delimiter=",")  # [-]
    n_lat, n_lon = albedo_map.shape
    d_lat, d_lon = math.pi / n_lat, 2.0 * math.pi / n_lon  # [rad]
    lat = -0.5 * math.pi + (np.arange(n_lat) + 0.5) * d_lat  # [rad]
    lon = -math.pi + (np.arange(n_lon) + 0.5) * d_lon  # [rad]
    lat_g, lon_g = np.meshgrid(lat, lon, indexing="ij")
    dirs_p = np.stack([np.cos(lat_g) * np.cos(lon_g), np.cos(lat_g) * np.sin(lon_g), np.sin(lat_g)], axis=-1)
    area = radius_m ** 2 * d_lon * (np.sin(lat_g + 0.5 * d_lat) - np.sin(lat_g - 0.5 * d_lat))  # [m^2]
    normal_n = dirs_p @ dcm_np.T
    cell_n = radius_m * normal_n  # [m]
    to_sc = r_sc_p - cell_n  # [m]
    distance = np.linalg.norm(to_sc, axis=-1)  # [m]
    to_sc_hat = to_sc / distance[..., None]
    to_sun = r_sun_p - cell_n  # [m]
    f1 = np.einsum("ijk,ijk->ij", normal_n, to_sun / np.linalg.norm(to_sun, axis=-1)[..., None])
    f2 = np.einsum("ijk,ijk->ij", normal_n, to_sc_hat)
    f3 = -to_sc_hat @ n_hat_n
    lit_seen = (f1 > 0.0) & (f2 > 0.0) & (f3 >= math.cos(half_fov_rad))
    return float(np.sum((albedo_map * f1 * f2 * f3 * area / (math.pi * distance ** 2))[lit_seen]))


@pytest.mark.requires_basilisk
def test_each_sensor_adds_exactly_its_recorded_albedo():
    """Template 14 pointed by the true Sun direction (the attitude is then
    the same in both runs): with albedo on, every sensor's output is its
    output without albedo plus its recorded albedo, at every sample, and the
    Earth-facing sensors see a real share of it."""
    _, plain = _run(_template_14(albedo=False, use_css_estimation=False))
    _, lit = _run(_template_14(albedo=True, use_css_estimation=False))
    largest = 0.0
    for i in range(1, 9):
        name = f"sat-1.sensor.css-{i}"
        albedo = lit.series[f"{name}.albedo"].data.ravel()
        assert lit.series[name].data.ravel() == pytest.approx(plain.series[name].data.ravel() + albedo, abs=1e-12)
        assert (albedo >= 0.0).all()
        largest = max(largest, albedo.max())
    assert 0.1 < largest < 0.4  # [-] reflected / direct solar flux, Earth's albedo is about 0.3
    assert "sat-1.sensor.css-1.albedo" not in plain.series


def _run_and_check_against_independent_integral(scenario, map_name: str, radius_m: float, rel: float):
    """Runs ``scenario`` with recorders on the planet, the Sun and the
    spacecraft, and compares every sensor's recorded albedo, once a minute,
    with :func:`_independent_albedo` from the same states. Returns how many
    comparisons had a sunlit planet in view (albedo over 0.01)."""
    from Basilisk.utilities import RigidBodyKinematics as rbk
    from Basilisk.utilities.supportDataTools.dataFetcher import DataFile

    from spacemissionstudio.engine import kernels
    from spacemissionstudio.engine.service import SimulationService

    service = SimulationService(scenario)
    service.build(initialize=False)
    handle = service.spacecraft_handles["sat-1"]
    recorders = {
        "planet": service._planet_state_out_msgs[scenario.gravity.central_body].recorder(),
        "sun": service._sun_state_out_msg.recorder(),
        "state": handle.sc_object.scStateOutMsg.recorder(),
    }
    for recorder in recorders.values():
        service.scSim.AddModelToTask(service.dyn_task_name, recorder)
    service.initialize()
    result = service.run()
    map_path = kernels.cached_path(getattr(DataFile.AlbedoData, map_name))
    times = recorders["state"].times()  # [ns]
    seen = 0
    for k in range(0, len(times), 60):  # one sample a minute (1 s dynamics step)
        r_planet = np.array(recorders["planet"].PositionVector[k])  # [m]
        r_sc_p = np.array(recorders["state"].r_BN_N[k]) - r_planet  # [m]
        r_sun_p = np.array(recorders["sun"].PositionVector[k]) - r_planet  # [m]
        dcm_np = np.array(recorders["planet"].J20002Pfix[k]).reshape(3, 3).T
        dcm_bn = rbk.MRP2C(np.array(recorders["state"].sigma_BN[k]))
        for sensor in scenario.spacecraft[0].sensors:
            series = result.series[f"sat-1.sensor.{sensor.name}.albedo"]
            sample = np.searchsorted(series.time_s, times[k] * 1e-9)  # [s]
            if sample >= series.time_s.size or abs(series.time_s[sample] - times[k] * 1e-9) > 1e-6:
                continue
            n_hat_n = dcm_bn.T @ np.array(sensor.params["nHat_B"], float)
            expected = _independent_albedo(map_path, radius_m, r_sc_p, r_sun_p, dcm_np, n_hat_n,
                                           math.radians(sensor.params["fov_deg"] / 2.0))
            assert series.data[sample, 0] == pytest.approx(expected, rel=rel, abs=1e-5), (sensor.name, k)
            seen += expected > 0.01
    return seen


@pytest.mark.requires_basilisk
def test_earths_albedo_matches_an_independent_integral_of_the_ceres_map():
    """Over template 14's orbit, once a minute, each sensor's albedo equals
    the numpy integral of the CERES 2018 map from the same state, within
    1 % (Basilisk takes Earth as the authalic sphere with authalic cell
    bounds, the integral the mean-radius sphere)."""
    seen = _run_and_check_against_independent_integral(_template_14(albedo=True), "Earth_ALB_2018_CERES_All_5x5",
                                                       6371.0e3, 0.01)
    assert seen > 50


@pytest.mark.requires_basilisk
def test_mars_albedo_comes_from_the_tes_map():
    """Template 14 moved to a 500 km orbit around Mars: once a minute, the
    albedo matches the integral of the TES map within 1 %."""
    seen = _run_and_check_against_independent_integral(_template_14(albedo=True, central_body="mars barycenter"),
                                                       "Mars_ALB_TES_5x5", 3389.5e3, 0.01)
    assert seen > 50


def test_albedo_needs_a_mapped_body_and_the_sun():
    """No map for the Moon; without the Sun nothing is reflected."""
    scenario = load_scenario(_TEMPLATES / "14_css_sun_heading_estimation.json")
    scenario.gravity.albedo = True
    scenario.gravity.central_body = "moon"
    with pytest.raises(ScenarioValidationError, match="gravity.albedo needs a central body with an albedo map"):
        scenario.validate()
    scenario = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json")
    scenario.gravity.albedo = True
    scenario.gravity.third_body_perturbers = []
    with pytest.raises(ScenarioValidationError, match="gravity.albedo needs 'sun'"):
        scenario.validate()
