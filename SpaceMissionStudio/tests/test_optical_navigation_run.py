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
"""Optical navigation flown in Basilisk (engine.optical_navigation): an
18 000 km x 0.2 Mars orbit (the Mars barycentre, the Sun as a third body)
with a 40 deg, 512 x 512 px camera. Each check compares what the chain
reports with the truth: with no pixel noise Basilisk's pixelLineConverter
gives the true position from every image; with noise the filter
(relativeODuKF) converges and its 3-sigma bounds hold the error; the
night side is not used; with attitude the camera points with
locationPointing; and the series are the promised ones."""

from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.requires_basilisk

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
DAY_S = 86400.0  # [s]
PREFIX = "sat-1.optical_navigation."


def _scenario(days, template="01_two_body_circular_orbit.json", **camera):
    from spacemissionstudio.schema import GravityConfig, OpticalNavigationConfig, load_scenario

    scenario = load_scenario(_TEMPLATES / template)
    scenario.gravity = GravityConfig(central_body="mars barycenter", third_body_perturbers=["sun"])
    sc = scenario.spacecraft[0]
    sc.enable_drag = False
    sc.orbit.semi_major_axis_km = 18000.0  # [km]
    sc.orbit.eccentricity = 0.2  # [-]
    sc.orbit.inclination_deg = 30.0  # [deg]
    sc.optical_navigation = OpticalNavigationConfig(**camera)
    scenario.sim_settings.duration_days = days
    return scenario


def _fly(scenario):
    from spacemissionstudio.engine.service import SimulationService

    scenario.validate()
    return SimulationService(scenario).run()


@pytest.fixture(scope="module")
def noiseless():
    return _fly(_scenario(0.5, center_noise_px=0.0, radius_noise_px=0.0, max_phase_angle_deg=180.0))


@pytest.fixture(scope="module")
def converging():
    return _fly(_scenario(2.0, initial_position_sigma_m=50.0e3, initial_velocity_sigma_mps=5.0))


def test_without_noise_every_image_gives_the_true_position(noiseless):
    """With no pixel noise and every image used, pixelLineConverter's
    position is the true one within a millimetre at 14 000 to 22 000 km,
    and the filter stays within 20 m (the Sun's pull is in the run, not in
    the filter's two-body model)."""
    state = noiseless.series[PREFIX + "measurement_state"].data[:, 0]
    assert np.all(state == 0)
    assert np.nanmax(noiseless.series[PREFIX + "measurement_error"].data[:, 3]) < 1.0e-3  # [m]
    error = noiseless.series[PREFIX + "position_error"].data[:, 3]
    assert np.max(error[1:]) < 20.0  # [m] after the first update
    distance = noiseless.series[PREFIX + "range"].data[:, 0]
    assert 14.0e6 < distance.min() and distance.max() < 22.0e6  # [m]


def test_the_filter_converges_inside_its_bounds(converging):
    """From a 50 km, 5 m/s (1 sigma) start (68 km off), with 0.5 px noise and
    the night side left out (45 % of the images used): after day 1.5 the
    position error is under 10 km (2.7 km measured; one image alone is
    good to 47 km median at this range), and over the two days at least
    90 % of the position-axis errors are inside the filter's 3-sigma
    bounds (95 % measured: a little optimistic)."""
    error = converging.series[PREFIX + "position_error"]
    sigma3 = converging.series[PREFIX + "position_3sigma"].data
    late = error.time_s >= 1.5 * DAY_S
    assert np.max(error.data[late, 3]) < 10.0e3  # [m]
    assert np.mean(np.abs(error.data[:, :3]) <= sigma3) >= 0.90
    single = converging.series[PREFIX + "measurement_error"].data[:, 3]
    assert np.nanmedian(single) > np.median(error.data[late, 3])  # the filter beats one image


def test_the_night_side_is_not_used(converging):
    """An image from beyond 90 deg phase is marked night side (state 4) and
    has no measurement; every used image is from 90 deg or less."""
    state = converging.series[PREFIX + "measurement_state"].data[:, 0]
    phase = converging.series[PREFIX + "phase_angle"].data[:, 0]
    measurement = converging.series[PREFIX + "measurement"].data
    assert np.all(state[phase > 90.0] == 4)
    assert np.all(phase[state == 0] <= 90.0)
    assert np.all(np.isnan(measurement[state != 0]))
    assert 0.2 < np.mean(state == 0) < 0.8


def test_the_same_seed_gives_the_same_run(noiseless):
    """Two runs with the same seed give identical estimates; another seed
    gives a different start."""
    first = _fly(_scenario(0.05, seed=3)).series[PREFIX + "position_error"].data
    again = _fly(_scenario(0.05, seed=3)).series[PREFIX + "position_error"].data
    other = _fly(_scenario(0.05, seed=4)).series[PREFIX + "position_error"].data
    assert np.array_equal(first, again)
    assert not np.array_equal(first[0], other[0])


def test_with_attitude_the_spacecraft_points_the_camera():
    """In a full-attitude run (template 15's spacecraft) with locationPointing
    on the Mars barycentre along the camera boresight, the images after the
    slew are used and the disk sits within 2 px of the image centre."""
    scenario = _scenario(0.02, template="15_celestial_body_pointing.json", max_phase_angle_deg=180.0)
    sc = scenario.spacecraft[0]
    sc.enable_srp = False
    sc.power = None
    sc.fsw_params = {"target_body": "mars barycenter", "pHat_B": [0.0, 0.0, 1.0]}
    result = _fly(scenario)
    state = result.series[PREFIX + "measurement_state"]
    measurement = result.series[PREFIX + "measurement"].data
    after = state.time_s >= 600.0  # [s] the slew is over
    assert np.all(state.data[after, 0] == 0)
    assert np.max(np.abs(measurement[after, :2] - 255.5)) < 2.0  # [px]


def test_the_series_are_the_promised_ones(noiseless):
    """Every series engine.series_names promises is recorded."""
    from spacemissionstudio.engine.series_names import expected_series_names

    names = [n for n in expected_series_names(_scenario(0.5)) if ".optical_navigation." in n]
    assert len(names) == 9 and all(n in noiseless.series for n in names)
