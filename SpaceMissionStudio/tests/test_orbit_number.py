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
"""The orbit number, the Results plots' third time axis (docs/ux-audit.md
U-26), and the plot catalog's groups (U-24)."""

import math

import numpy as np
import pytest

from spacemissionstudio.engine import orbit_number
from spacemissionstudio.engine.propellant_budget import MU_EARTH_M3_S2
from spacemissionstudio.engine.results import ResultSet, TimeSeries

_RADIUS = 6928.137e3  # [m] a 550 km circular orbit
_PERIOD = 2.0 * math.pi * math.sqrt(_RADIUS ** 3 / MU_EARTH_M3_S2)  # [s]


def _circular(time_s, inclination_deg=97.6, u0_deg=0.0, raan_deg=30.0):
    """Positions [m] and velocities [m/s] of a circular orbit, argument of latitude u0 at t = 0."""
    n = 2.0 * math.pi / _PERIOD  # [rad/s]
    u = math.radians(u0_deg) + n * np.asarray(time_s)
    i, raan = math.radians(inclination_deg), math.radians(raan_deg)
    node = np.array([math.cos(raan), math.sin(raan), 0.0])
    ahead = np.array([-math.sin(raan) * math.cos(i), math.cos(raan) * math.cos(i), math.sin(i)])
    r = _RADIUS * (np.cos(u)[:, None] * node + np.sin(u)[:, None] * ahead)
    speed = _RADIUS * n  # [m/s]
    v = speed * (-np.sin(u)[:, None] * node + np.cos(u)[:, None] * ahead)
    return r, v


def test_the_number_counts_turns_from_the_ascending_node():
    """A quarter of the way round at the epoch reads 0.25; three orbits
    later 3.25; it rises steadily in between."""
    time_s = np.linspace(0.0, 3.0 * _PERIOD, 400)  # [s]
    r, v = _circular(time_s, u0_deg=90.0)
    numbers = orbit_number.orbit_numbers(time_s, r, v)
    assert numbers[0] == pytest.approx(0.25, abs=1e-9)
    assert numbers[-1] == pytest.approx(3.25, abs=1e-9)
    assert np.all(np.diff(numbers) > 0)


def test_a_sample_once_an_orbit_still_counts_every_turn():
    """Recorded once per orbit and a bit (a geostationary satellite logged
    daily): the mean motion says how many turns each step made."""
    time_s = np.arange(6) * 1.1 * _PERIOD  # [s]
    r, v = _circular(time_s)
    numbers = orbit_number.orbit_numbers(time_s, r, v)
    assert numbers == pytest.approx(np.arange(6) * 1.1, abs=1e-9)


def test_an_equatorial_orbit_counts_from_the_x_axis():
    """No ascending node: the angle is measured from inertial X, and the
    note says so."""
    time_s = np.linspace(0.0, _PERIOD, 50)  # [s]
    r, v = _circular(time_s, inclination_deg=0.0, raan_deg=0.0, u0_deg=45.0)
    numbers = orbit_number.orbit_numbers(time_s, r, v)
    assert numbers[0] == pytest.approx(0.125, abs=1e-9)
    assert numbers[-1] == pytest.approx(1.125, abs=1e-9)
    result = ResultSet("test")
    result.add(TimeSeries("sat.position_N", time_s, ("x", "y", "z"), r, units="m"))
    result.add(TimeSeries("sat.velocity_N", time_s, ("x", "y", "z"), v, units="m/s"))
    assert "X axis" in orbit_number.reference_note(result, "sat")


def test_the_result_helpers_pick_a_spacecraft_with_both_vectors():
    """The preferred spacecraft when it recorded position and velocity,
    else the first that did; none without them."""
    time_s = np.linspace(0.0, _PERIOD, 20)  # [s]
    r, v = _circular(time_s)
    result = ResultSet("test")
    result.add(TimeSeries("lone.position_N", time_s, ("x", "y", "z"), r, units="m"))
    for name in ("chief", "deputy"):
        result.add(TimeSeries(f"{name}.position_N", time_s, ("x", "y", "z"), r, units="m"))
        result.add(TimeSeries(f"{name}.velocity_N", time_s, ("x", "y", "z"), v, units="m/s"))
    assert orbit_number.reference_spacecraft(result, "deputy") == "deputy"
    assert orbit_number.reference_spacecraft(result, "lone") == "chief"
    assert orbit_number.reference_spacecraft(ResultSet("empty")) is None
    times, numbers = orbit_number.for_result(result, "chief")
    assert len(times) == len(numbers) == 20 and numbers[-1] == pytest.approx(1.0, abs=1e-9)
    assert orbit_number.for_result(result, "lone") is None
    assert orbit_number.reference_note(result, "chief") == "from the ascending node"


@pytest.mark.parametrize("name, columns, group", [
    ("sat.position_N", ("x", "y", "z"), "Orbit"),
    ("sat.orbit_elements_mean.raan", ("raan",), "Orbit"),
    ("sat.station_keeping.altitude", ("raw", "smoothed"), "Orbit"),
    ("sat.station_keeping.delta_v", ("cumulative_delta_v",), "Propellant"),
    ("sat.fuel_mass_remaining", ("fuel_mass_remaining",), "Propellant"),
    ("sat.body_rate_omega_BN_B", ("x", "y", "z"), "Attitude"),
    ("sat.navigation_error.position", ("position",), "Orbit"),
    ("sat.navigation_error.attitude", ("attitude",), "Attitude"),
    ("sat.battery_charge", ("charge",), "Power"),
    ("sat.solar_array.wing.power", ("power",), "Power"),
    ("sat.solar_array.wing.deflection", ("deflection",), "Attitude"),
    ("gs.access_to_sat.elevation", ("elevation",), "Link"),
    ("sat.data_handling.stored", ("total",), "Data"),
    ("sat.actuator.rw1.motor_temperature", ("temperature",), "Thermal"),
    ("sat.sensor.panel_temp", ("temperature",), "Thermal"),
    ("sat.sensor.mag", ("x", "y", "z"), "Sensors"),
    ("sat.monte_carlo.spread", ("radial",), "Monte Carlo"),
    ("sat.something_new", ("value",), "Other"),
])
def test_every_series_has_a_catalog_group(name, columns, group):
    """The catalog groups (docs/ux-standard.md, "Results")."""
    from spacemissionstudio.plot_categories import PLOT_GROUPS, plot_group

    series = TimeSeries(name, [0.0, 1.0], columns, np.zeros((2, len(columns))))
    assert plot_group(name, series) == group and group in PLOT_GROUPS
