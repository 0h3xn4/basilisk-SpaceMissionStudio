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

"""The solar flux a thermal sensor's heat balance uses is the flux at the
spacecraft's own distance from the Sun, in a Basilisk run (template 15):
around Earth it matches the almanac formula of engine.environment_models,
around Mars a direct SPICE query of the spacecraft's distance from the
Sun."""

import math
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import environment_models
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import SensorConfig

pytestmark = pytest.mark.requires_basilisk

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"
_ABSORPTIVITY = 0.25  # [-] small enough that sensor_thermal_inputs does not rescale (scale 1)


def _initialized_with_a_thermal_sensor(central_body: str):
    """Template 15 (attitude, pointing at a body) around ``central_body``,
    with one thermal sensor, built and initialized."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = load_scenario(_TEMPLATES / "15_celestial_body_pointing.json")
    if central_body != "earth":
        scenario.gravity.central_body = central_body
        scenario.gravity.central_body_degree = 0
        scenario.gravity.third_body_perturbers = ["sun"]
        scenario.spacecraft[0].fsw_params["target_body"] = central_body
        scenario.spacecraft[0].orbit.semi_major_axis_km = 5000.0  # [km]
        scenario.spacecraft[0].orbit.eccentricity = 0.0
    elif "sun" not in scenario.gravity.third_body_perturbers:
        scenario.gravity.third_body_perturbers.append("sun")
    scenario.spacecraft[0].sensors.append(SensorConfig(kind="thermal", name="therm-1", params={
        "nHat_B": [0.0, 0.0, 1.0], "area_m2": 0.01, "absorptivity": _ABSORPTIVITY, "emissivity": 0.34}))
    scenario.validate()
    service = SimulationService(scenario)
    service.build()
    sc_object, thermal_models = service._sensor_thermal_models[0]
    module = thermal_models[0][0]
    flux = module.sensorAbsorptivity * environment_models.BASILISK_SENSOR_THERMAL_FLUX_W_M2 / _ABSORPTIVITY  # [W/m^2]
    return scenario, sc_object, flux


def test_around_earth_the_flux_is_the_almanac_flux_of_the_epoch():
    """Around Earth, the flux the sensor uses equals the solar flux at
    Earth's distance on the epoch (almanac formula, 1e-4 AU) to 0.1 %."""
    scenario, _, flux = _initialized_with_a_thermal_sensor("earth")
    assert flux == pytest.approx(environment_models.solar_flux_w_m2(scenario.epoch_utc), rel=1e-3)


def test_around_mars_the_flux_is_the_flux_at_mars():
    """Around Mars, the flux the sensor uses is the flux at the
    spacecraft's distance from the Sun, as SPICE gives it directly (not
    through Basilisk's messages), and well below Earth's."""
    from Basilisk.topLevelModules import pyswice

    from spacemissionstudio.engine import kernels, time_system

    scenario, sc_object, flux = _initialized_with_a_thermal_sensor("mars barycenter")
    # pyswice has a kernel pool of its own, apart from Basilisk's
    # spiceInterface: load the leap seconds and DE430 into it
    paths = [str(status.path) for status in kernels.require_cached(kernels.DEFAULT_KERNELS[:2])]
    for path in paths:
        pyswice.furnsh_c(path)
    try:
        et = pyswice.new_doubleArray(1)
        pyswice.str2et_c(time_system.utc_iso_to_spice_string(scenario.epoch_utc), et)
        position = pyswice.new_doubleArray(3)
        light_time = pyswice.new_doubleArray(1)
        pyswice.spkpos_c("SUN", pyswice.doubleArray_getitem(et, 0), "J2000", "NONE", "MARS BARYCENTER",
                         position, light_time)
    finally:
        for path in paths:
            pyswice.unload_c(path)
    r_sun_from_mars_m = 1e3 * np.array([pyswice.doubleArray_getitem(position, i) for i in range(3)])  # [m]
    r_sc_from_mars_m = np.array(sc_object.scStateOutMsg.read().r_BN_N)  # [m]
    distance_m = float(np.linalg.norm(r_sun_from_mars_m - r_sc_from_mars_m))  # [m]
    expected = environment_models.TOTAL_SOLAR_IRRADIANCE_W_M2 * (environment_models.ASTRONOMICAL_UNIT_M
                                                                   / distance_m) ** 2  # [W/m^2]
    assert flux == pytest.approx(expected, rel=1e-6)
    assert 1.38 < distance_m / environment_models.ASTRONOMICAL_UNIT_M < 1.67  # Mars's perihelion, aphelion
    assert flux < 0.55 * environment_models.solar_flux_w_m2(scenario.epoch_utc)
    assert not math.isnan(flux)
