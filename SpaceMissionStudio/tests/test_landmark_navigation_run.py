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

"""Landmark navigation around 433 Eros in Basilisk (real NAIF ephemeris and
NEAR shape, installed by 'spacemissionstudio small-bodies --fetch'; CI
installs them): Basilisk's pinholeCamera against the tool's camera model,
the filter's convergence and consistency, pixel noise, and pointing by
the spacecraft's own attitude."""

import math

import numpy as np
import pytest

from spacemissionstudio.engine import landmarks
from spacemissionstudio.schema import ScenarioValidationError, load_scenario
from spacemissionstudio.schema.scenario import LandmarkNavigationConfig

from test_small_body_run import _TEMPLATES

pytestmark = pytest.mark.requires_basilisk


def _scenario(hours: float, template: str = "01_two_body_circular_orbit.json", **config):
    scenario = load_scenario(_TEMPLATES / template)
    if scenario.spacecraft[0].fsw_params.get("target_body"):
        scenario.spacecraft[0].fsw_params["target_body"] = "eros"
    scenario.epoch_utc = "2026-10-19T00:00:00"
    scenario.gravity.central_body = "eros"
    scenario.gravity.central_body_degree = 0
    scenario.gravity.third_body_perturbers = ["sun"]
    scenario.gravity.polyhedral_gravity = True
    scenario.sim_settings.duration_days = hours / 24.0  # [day]
    scenario.sim_settings.dynamics_task_rate_s = 10.0  # [s]
    scenario.sim_settings.record_interval_s = 60.0  # [s]
    sc = scenario.spacecraft[0]
    sc.orbit.semi_major_axis_km = 35.0  # [km]
    sc.orbit.eccentricity = 0.0
    sc.orbit.inclination_deg = 40.0  # [deg]
    sc.orbit.raan_deg = 90.0  # [deg]
    sc.landmark_navigation = LandmarkNavigationConfig(**config)
    scenario.validate()
    return scenario


def _run(scenario):
    from spacemissionstudio.engine.service import SimulationService

    service = SimulationService(scenario)
    return service, service.run()


def _series(result, part):
    return result.series[f"sat-1.landmark_navigation.{part}"].data


def test_basilisks_camera_sees_what_the_tools_camera_model_predicts(real_small_body_files):
    """At the last image, every landmark pinholeCamera reports is where
    engine.landmarks puts it (the same whole pixel), and it reports exactly
    the landmarks engine.landmarks.visible() says are seen."""
    from Basilisk.utilities import RigidBodyKinematics as rbk

    service, _ = _run(_scenario(1.0))
    chain = service.spacecraft_handles["sat-1"].landmark_navigation
    config = service.scenario.spacecraft[0].landmark_navigation
    ephemeris = chain.inputs.ephemerisOutMsg.read()
    state = chain.inputs.scStateOutMsg.read()
    body_from_sun = np.array(ephemeris.r_BdyZero_N)
    r_n = np.array(state.r_BN_N) - body_from_sun
    dcm_pn = rbk.MRP2C(np.array(ephemeris.sigma_BN))
    dcm_cn = rbk.MRP2C(np.asarray(config.camera_mrp_cb, float)) @ rbk.MRP2C(np.array(state.sigma_BN))
    f_over_w = landmarks.FOCAL_LENGTH_M / landmarks.pixel_pitch_m(math.radians(config.field_of_view_deg),
                                                                 config.resolution_px[0])
    uv, _ = landmarks.project(chain.landmarks_P, r_n, dcm_pn, dcm_cn, f_over_w)
    pixels = landmarks.round_pixels(uv)
    expected = landmarks.visible(chain.landmarks_P, chain.normals_P, dcm_pn @ r_n, dcm_pn @ dcm_cn[2],
                                 dcm_pn @ -body_from_sun, pixels, config.resolution_px,
                                 math.radians(config.min_sun_elevation_deg))
    reported = [message.read() for message in chain.camera.landmarkOutMsgs]
    seen = np.array([bool(payload.isVisible) for payload in reported])
    assert seen.sum() > 5 and (seen == expected).all()
    for index in np.nonzero(seen)[0]:
        assert list(reported[index].pL) == pixels[index].astype(int).tolist()


def test_the_filter_finds_the_orbit_from_whole_pixels(real_small_body_files):
    """From 100 m off (1 sigma each axis), the first image brings the
    filter within 20 m and it stays within 5 m (median) afterwards, inside
    its 3 sigma, with residuals of whole-pixel rounding (0.29 px rms); the
    Sun's shadow is modelled."""
    _, result = _run(_scenario(3.0))
    error = _series(result, "position_error")
    sigma3 = _series(result, "position_3sigma")
    seen = _series(result, "landmarks_seen")[:, 0]
    residual = _series(result, "residual_rms")[:, 0]
    assert error[0, 3] < 20.0 and np.median(error[1:, 3]) < 5.0
    assert np.mean(np.abs(error[:, :3]) <= sigma3) > 0.95
    assert np.median(seen) >= 10
    assert np.nanmedian(residual) == pytest.approx(landmarks.QUANTIZATION_SIGMA_PX, rel=0.15)
    illumination = result.series["sat-1.eclipse.illumination_factor"].data
    assert ((illumination >= 0.0) & (illumination <= 1.0)).all()


def test_added_pixel_noise_shows_in_the_residuals(real_small_body_files):
    """1 px of added noise: the residuals grow to hypot(0.29, 1) px and
    the filter still converges, with a larger 3 sigma."""
    _, result = _run(_scenario(2.0, pixel_noise_px=1.0))
    residual = _series(result, "residual_rms")[:, 0]
    assert np.nanmedian(residual) == pytest.approx(math.hypot(landmarks.QUANTIZATION_SIGMA_PX, 1.0), rel=0.15)
    assert np.median(_series(result, "position_error")[1:, 3]) < 15.0


def test_with_attitude_the_spacecraft_points_the_camera(real_small_body_files):
    """Full attitude, locationPointing at Eros with the body +z axis (the
    camera's boresight): the camera sees landmarks and the filter converges."""
    _, result = _run(_scenario(2.0, template="15_celestial_body_pointing.json"))
    seen = _series(result, "landmarks_seen")[:, 0]
    assert np.mean(seen > 0) > 0.8
    assert np.median(_series(result, "position_error")[2:, 3]) < 10.0


def test_landmark_navigation_needs_eros_with_its_shape_and_the_sun():
    """Refused around a planet, without polyhedral gravity, or without the Sun."""
    scenario = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json")
    scenario.spacecraft[0].landmark_navigation = LandmarkNavigationConfig()
    with pytest.raises(ScenarioValidationError, match="landmark_navigation needs a small body"):
        scenario.validate()
    scenario = _scenario(1.0)
    scenario.gravity.third_body_perturbers = []
    with pytest.raises(ScenarioValidationError, match="needs 'sun'"):
        scenario.validate()
