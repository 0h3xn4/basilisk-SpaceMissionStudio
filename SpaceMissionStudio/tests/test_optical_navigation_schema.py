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
"""Tests for schema.scenario.OpticalNavigationConfig: it saves and loads,
each bad value is refused by name, the central body must be one
pixelLineConverter knows, the Sun must be in the run, and a run is one
Basilisk simulation. No Basilisk (the runs are in
test_optical_navigation_run.py)."""

from pathlib import Path

import pytest

from spacemissionstudio.schema import GravityConfig, OpticalNavigationConfig, load_scenario
from spacemissionstudio.schema.scenario import OPTICAL_NAVIGATION_BODIES, ScenarioValidationError

_TEMPLATE = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
             / "01_two_body_circular_orbit.json")


def _scenario(central_body="mars barycenter", third_bodies=("sun",), **camera):
    scenario = load_scenario(_TEMPLATE)
    scenario.gravity = GravityConfig(central_body=central_body, third_body_perturbers=list(third_bodies))
    sc = scenario.spacecraft[0]
    sc.enable_drag = False
    sc.orbit.semi_major_axis_km = 18000.0  # [km]
    sc.optical_navigation = OpticalNavigationConfig(**camera)
    return scenario


def test_optical_navigation_saves_and_loads_unchanged(tmp_path):
    """Every field survives a save and a load."""
    scenario = _scenario(field_of_view_deg=30.0, resolution_px=[1024, 768], camera_mrp_cb=[0.1, 0.0, 0.0],
                         measurement_interval_s=120.0, center_noise_px=0.3, radius_noise_px=0.7, min_radius_px=8.0,
                         max_phase_angle_deg=100.0, initial_position_sigma_m=5.0e3, initial_velocity_sigma_mps=2.0,
                         process_noise_position_m=0.5, process_noise_velocity_mps=1.0e-4, seed=9)
    scenario.validate()
    scenario.save(tmp_path / "opnav.json")
    loaded = load_scenario(tmp_path / "opnav.json")
    assert loaded.spacecraft[0].optical_navigation == scenario.spacecraft[0].optical_navigation


@pytest.mark.parametrize("overrides, message", [
    ({"field_of_view_deg": 0.0}, "field_of_view_deg must be a finite number > 0"),
    ({"field_of_view_deg": 180.0}, "field_of_view_deg must be under 180"),
    ({"resolution_px": [512]}, "resolution_px"),
    ({"resolution_px": [512, 8]}, "resolution_px"),
    ({"resolution_px": [512.0, 512.0]}, "resolution_px"),
    ({"camera_mrp_cb": [0.0, 0.0]}, "camera_mrp_cb"),
    ({"measurement_interval_s": -1.0}, "measurement_interval_s"),
    ({"center_noise_px": -0.1}, "center_noise_px must be a finite number >= 0"),
    ({"radius_noise_px": float("nan")}, "radius_noise_px"),
    ({"max_phase_angle_deg": 181.0}, "max_phase_angle_deg must be at most 180"),
    ({"initial_position_sigma_m": 0.0}, "initial_position_sigma_m"),
    ({"process_noise_velocity_mps": -1.0}, "process_noise_velocity_mps"),
    ({"seed": -1}, "seed must be a whole number"),
    ({"seed": True}, "seed must be a whole number"),
])
def test_each_bad_value_is_named(overrides, message):
    """Each invalid field is refused with a message that names it."""
    with pytest.raises(ScenarioValidationError, match=message):
        _scenario(**overrides).validate()


@pytest.mark.parametrize("body", ["moon", "venus", "sun"])
def test_a_body_pixel_line_converter_does_not_know_is_refused(body):
    """The Moon, Venus and the Sun have no number in pixelLineConverter or
    relativeODuKF: refused, naming the bodies that work."""
    third = [] if body == "sun" else ["sun"]
    with pytest.raises(ScenarioValidationError, match="optical_navigation needs gravity.central_body"):
        _scenario(central_body=body, third_bodies=third).validate()


@pytest.mark.parametrize("body", OPTICAL_NAVIGATION_BODIES)
def test_every_known_body_is_accepted(body):
    """Earth and the Mars and Jupiter barycentres are accepted."""
    _scenario(central_body=body).validate()


def test_the_sun_must_be_in_the_run():
    """Without the Sun there is no phase angle: refused."""
    with pytest.raises(ScenarioValidationError, match="needs 'sun' in gravity.third_body_perturbers"):
        _scenario(third_bodies=()).validate()


def test_a_run_longer_than_one_simulation_is_refused():
    """The filter is not carried between long-run segments: over 100 days
    is refused."""
    scenario = _scenario()
    scenario.sim_settings.duration_days = 101.0  # [day]
    with pytest.raises(ScenarioValidationError, match="optical_navigation runs at most 100 days"):
        scenario.validate()
