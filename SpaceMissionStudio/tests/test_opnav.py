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
"""Tests for engine.opnav, the camera geometry of optical navigation: the
MRP helpers against Basilisk's, the disk projection against its own
inverse and, in Basilisk, against pixelLineConverter, which must turn a
noise-free disk back into the true position."""

import math

import numpy as np
import pytest

from spacemissionstudio.engine import opnav

MARS = "mars barycenter"
FOV = math.radians(40.0)  # [rad] edge to edge along the image's y axis
RESOLUTION = (512, 512)  # [px]
R_BN_N = np.array([12000.0e3, -9000.0e3, 4000.0e3])  # [m] a Mars approach, 15.5 Mm out
V_BN_N = np.array([1.2e3, 2.1e3, -0.4e3])  # [m/s]


def _off_centre_camera(angle_deg=5.0):
    """A camera pointed at Mars and then turned ``angle_deg`` about its x
    axis, so the disk sits off the image centre."""
    turn = math.radians(angle_deg)
    c, s = math.cos(turn), math.sin(turn)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, s], [0.0, -s, c]]) @ opnav.pointing_dcm_CN(R_BN_N, V_BN_N)


@pytest.mark.parametrize("sigma", [[0.1, -0.2, 0.3], [0.0, 0.0, 0.0], [0.6, 0.5, -0.4]])
def test_mrps_and_dcms_round_trip(sigma):
    """An MRP to a direction cosine matrix and back gives the same MRP
    (inside the unit sphere), and the matrix is a rotation."""
    dcm = opnav.mrp_to_dcm(sigma)
    assert dcm @ dcm.T == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(dcm) == pytest.approx(1.0)
    assert opnav.dcm_to_mrp(dcm) == pytest.approx(sigma, abs=1e-12)


def test_pointing_puts_the_body_at_the_image_centre():
    """With the camera pointed at the body its disk is centred: pixel and
    line at (w - 1) / 2, the radius tan(asin(R / d)) / X."""
    dcm = opnav.pointing_dcm_CN(R_BN_N, V_BN_N)
    disk = opnav.project_body(R_BN_N, dcm, opnav.BODY_RADIUS_M[MARS], FOV, RESOLUTION, 5.0)
    assert disk.valid
    assert (disk.pixel, disk.line) == pytest.approx((255.5, 255.5), abs=1e-9)
    x_scale, _ = opnav.pixel_scales(FOV, RESOLUTION)
    expected = math.tan(math.asin(opnav.BODY_RADIUS_M[MARS] / np.linalg.norm(R_BN_N))) / x_scale
    assert disk.radius_px == pytest.approx(expected)


def test_the_disk_gives_back_the_position():
    """pixelLineConverter's computation (position_from_circle) turns an
    off-centre disk back into the spacecraft's position, to a millimetre."""
    dcm = _off_centre_camera()
    disk = opnav.project_body(R_BN_N, dcm, opnav.BODY_RADIUS_M[MARS], FOV, RESOLUTION, 5.0)
    assert disk.valid and abs(disk.line - 255.5) > 10.0
    position = opnav.position_from_circle(disk.pixel, disk.line, disk.radius_px, dcm, opnav.BODY_RADIUS_M[MARS],
                                          FOV, RESOLUTION)
    assert position == pytest.approx(R_BN_N, abs=1e-3)


@pytest.mark.parametrize("case, reason", [
    ("behind", "behind the camera"),
    ("far", "too small"),
    ("edge", "not wholly in the image"),
    ("inside", "inside the body"),
])
def test_an_unusable_image_says_why(case, reason):
    """Behind the camera, too small, cut by the image edge, or from inside
    the body: not valid, with the reason."""
    dcm = opnav.pointing_dcm_CN(R_BN_N, V_BN_N)
    position = R_BN_N
    if case == "behind":
        dcm = np.diag([1.0, -1.0, -1.0]) @ dcm
    elif case == "far":
        position = R_BN_N * 200.0
    elif case == "edge":
        dcm = _off_centre_camera(19.0)
    elif case == "inside":
        position = R_BN_N / np.linalg.norm(R_BN_N) * 1000.0e3
    disk = opnav.project_body(position, dcm, opnav.BODY_RADIUS_M[MARS], FOV, RESOLUTION, 5.0)
    assert not disk.valid and disk.reason == reason


def test_the_phase_angle_is_zero_with_the_sun_behind_the_camera():
    """Sun and spacecraft on the same side: 0; opposite sides: pi."""
    assert opnav.phase_angle(R_BN_N, 1e11 * R_BN_N) == pytest.approx(0.0, abs=1e-7)
    assert opnav.phase_angle(R_BN_N, -1e11 * R_BN_N) == pytest.approx(math.pi, abs=1e-7)


def test_the_body_attitude_carries_the_camera_mounting():
    """A spacecraft at body_attitude(dcm_CN, sigma_CB) has the camera at
    dcm_CN."""
    dcm_CN = _off_centre_camera()
    sigma_CB = [0.0, math.tan(math.radians(90.0) / 4.0), 0.0]  # [-] camera turned 90 deg about the body y axis
    sigma_BN = opnav.body_attitude(dcm_CN, sigma_CB)
    assert opnav.camera_dcm_CN(sigma_BN, sigma_CB) == pytest.approx(dcm_CN, abs=1e-12)


def test_noise_moves_only_valid_measurements():
    """Noise with a fixed seed is repeatable, has the asked spread over many
    draws, and leaves an invalid measurement untouched."""
    disk = opnav.CircleMeasurement(100.0, 200.0, 50.0, True)
    draws = [opnav.noisy(disk, 0.5, 0.2, np.random.default_rng(seed)) for seed in range(2000)]
    assert np.std([d.pixel for d in draws]) == pytest.approx(0.5, rel=0.05)
    assert np.std([d.radius_px for d in draws]) == pytest.approx(0.2, rel=0.05)
    assert opnav.noisy(disk, 0.5, 0.2, np.random.default_rng(7)) == opnav.noisy(disk, 0.5, 0.2,
                                                                                 np.random.default_rng(7))
    invalid = opnav.CircleMeasurement(math.nan, math.nan, math.nan, False, "too small")
    assert opnav.noisy(invalid, 0.5, 0.2, np.random.default_rng(1)) is invalid


@pytest.mark.requires_basilisk
def test_the_mrp_helpers_match_basilisk():
    """mrp_to_dcm is Basilisk's MRP2C, dcm_to_mrp its C2MRP."""
    from Basilisk.utilities import RigidBodyKinematics as rbk

    sigma = [0.2, -0.1, 0.35]
    assert opnav.mrp_to_dcm(sigma) == pytest.approx(np.array(rbk.MRP2C(sigma)), abs=1e-14)
    assert opnav.dcm_to_mrp(opnav.mrp_to_dcm(sigma)) == pytest.approx(np.array(rbk.C2MRP(rbk.MRP2C(sigma))),
                                                                      abs=1e-12)


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("body, distance_m", [(MARS, 15.5e6), ("earth", 60.0e6), ("jupiter barycenter", 900.0e6)])
def test_pixel_line_converter_turns_the_disk_back_into_the_position(body, distance_m):
    """Basilisk's own pixelLineConverter, given a noise-free disk from
    project_body, the camera's configuration and the spacecraft attitude
    body_attitude gives, outputs the true position within 1e-9 of the
    distance, for each body it knows."""
    from Basilisk.architecture import messaging
    from Basilisk.fswAlgorithms import pixelLineConverter
    from Basilisk.utilities import SimulationBaseClass, macros

    position = R_BN_N / np.linalg.norm(R_BN_N) * distance_m
    sigma_CB = [0.1, 0.0, -0.05]
    dcm_CN = _off_centre_camera(3.0)
    sigma_BN = opnav.body_attitude(dcm_CN, sigma_CB)
    disk = opnav.project_body(position, dcm_CN, opnav.BODY_RADIUS_M[body], FOV, RESOLUTION, 2.0)
    assert disk.valid

    sim = SimulationBaseClass.SimBaseClass()
    process = sim.CreateNewProcess("p")
    process.addTask(sim.CreateNewTask("t", macros.sec2nano(1.0)))
    module = pixelLineConverter.pixelLineConverter()
    sim.AddModelToTask("t", module)
    camera = messaging.CameraConfigMsgPayload()
    camera.fieldOfView = FOV
    camera.resolution = list(RESOLUTION)
    camera.sigma_CB = sigma_CB
    circles = messaging.OpNavCirclesMsgPayload()
    circles.circlesCenters = [disk.pixel, disk.line]
    circles.circlesRadii = [disk.radius_px]
    circles.planetIds = [opnav.BODY_IDS[body]]
    circles.uncertainty = [0.25, 0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.25]
    circles.valid = 1
    attitude = messaging.NavAttMsgPayload()
    attitude.sigma_BN = list(sigma_BN)
    messages = (messaging.CameraConfigMsg().write(camera), messaging.OpNavCirclesMsg().write(circles),
                messaging.NavAttMsg().write(attitude))
    module.cameraConfigInMsg.subscribeTo(messages[0])
    module.circlesInMsg.subscribeTo(messages[1])
    module.attInMsg.subscribeTo(messages[2])
    recorder = module.opNavOutMsg.recorder()
    sim.AddModelToTask("t", recorder)
    sim.InitializeSimulation()
    sim.ConfigureStopTime(0)
    sim.ExecuteSimulation()
    assert recorder.valid[-1] == 1
    assert np.array(recorder.r_BN_N[-1]) == pytest.approx(position, abs=1e-9 * distance_m)
