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
r"""Optical navigation in a run (``schema.scenario.OpticalNavigationConfig``):
a camera model, Basilisk's ``pixelLineConverter`` and Basilisk's
``relativeODuKF``, on a task of their own that runs once per
``measurement_interval_s``, after the dynamics.

1. :class:`OpNavCamera` (the tool's own code, ``engine.opnav``) reads the
   spacecraft's true state and the Sun's, points the camera (perfectly at
   the central body in an orbit-only run; through the spacecraft's attitude
   and ``camera_mrp_cb`` otherwise) and writes the disk measurement an
   image processing step would report (``OpNavCirclesMsg``: centre, radius,
   their noise variance), the camera's ``CameraConfigMsg`` and the
   attitude the converter reads (``NavAttMsg``: the true attitude, so
   attitude knowledge is perfect). An image with the body behind the
   camera, off the detector, too small or seen from beyond
   ``max_phase_angle_deg`` is marked not valid.
2. ``pixelLineConverter`` (Basilisk, unmodified) turns the disk into a
   position relative to the body, with its covariance.
3. ``relativeODuKF`` (Basilisk, unmodified) filters those positions with
   two-body dynamics around the body. It starts from the true initial
   state plus one seeded draw of the initial sigmas, with that covariance.
   It adds the process noise at each of its time updates: Basilisk's
   filter does one at a valid measurement and one at the task's own time,
   so twice per valid image.

The three run once per image, so each image is filtered once
(``pixelLineConverter`` writes on every call, and the filter takes every
new valid write). Recorders after the filter log its estimate at the
same times the camera logs the truth.
"""

from __future__ import annotations

import math

import numpy as np

from Basilisk.architecture import messaging, sysModel
from Basilisk.fswAlgorithms import pixelLineConverter, relativeODuKF
from Basilisk.utilities import macros

from ..config import registry
from ..schema.scenario import OpticalNavigationConfig
from . import opnav
from .results import TimeSeries

VALID = 0  # measurement_state: a usable image
BEHIND = 1  # measurement_state: the body behind the camera
OFF_IMAGE = 2  # measurement_state: the disk not wholly on the detector
TOO_SMALL = 3  # measurement_state: the disk under min_radius_px
NIGHT_SIDE = 4  # measurement_state: phase angle over max_phase_angle_deg
INSIDE = 5  # measurement_state: inside the body
_STATES = {"": VALID, "behind the camera": BEHIND, "not wholly in the image": OFF_IMAGE, "too small": TOO_SMALL,
           "inside the body": INSIDE}
_MIN_SIGMA_PX = 1.0e-3  # [px] the variance written is never zero: the filter takes a Cholesky factor of it
_TASK_PRIORITY = -10  # after the dynamics task (priority -1) at the same time


class OpNavCamera(sysModel.SysModel):
    """The camera model (module docstring, step 1)."""

    def __init__(self, name: str, config: OpticalNavigationConfig, central_body: str, ideal_pointing: bool):
        super().__init__()
        self.ModelTag = name
        self.config = config
        self.idealPointing = ideal_pointing
        self.bodyId = opnav.BODY_IDS[central_body]
        self.bodyRadiusM = opnav.BODY_RADIUS_M[central_body]  # [m]
        self.fovRad = math.radians(config.field_of_view_deg)  # [rad]
        self.resolution = tuple(config.resolution_px)  # [px]
        self.sigmaCB = np.asarray(config.camera_mrp_cb, dtype=float)
        self.maxPhaseRad = math.radians(config.max_phase_angle_deg)  # [rad]
        self.rng = np.random.default_rng(config.seed)

        self.scStateInMsg = messaging.SCStatesMsgReader()
        self.sunStateInMsg = messaging.SpicePlanetStateMsgReader()
        self.circlesOutMsg = messaging.OpNavCirclesMsg()
        self.cameraConfigOutMsg = messaging.CameraConfigMsg()
        self.attOutMsg = messaging.NavAttMsg()

        self.tLog: list = []  # [s]
        self.truthPositionLog: list = []  # [m] r_BN_N relative to the central body
        self.truthVelocityLog: list = []  # [m/s]
        self.measurementLog: list = []  # [px] pixel, line, radius (noisy; nan when not valid)
        self.stateLog: list = []  # VALID ... INSIDE
        self.phaseAngleLog: list = []  # [rad]

    def camera_payload(self) -> messaging.CameraConfigMsgPayload:
        payload = messaging.CameraConfigMsgPayload()
        payload.cameraID = 1
        payload.isOn = 1
        payload.fieldOfView = self.fovRad
        payload.resolution = list(self.resolution)
        payload.sigma_CB = self.sigmaCB.tolist()
        payload.renderRate = int(macros.sec2nano(self.config.measurement_interval_s))
        return payload

    def Reset(self, CurrentSimNanos):
        self.cameraConfigOutMsg.write(self.camera_payload(), CurrentSimNanos, self.moduleID)

    def UpdateState(self, CurrentSimNanos):
        state = self.scStateInMsg()
        r = np.array(state.r_BN_N)  # [m]
        v = np.array(state.v_BN_N)  # [m/s]
        if self.idealPointing:
            dcm_CN = opnav.pointing_dcm_CN(r, v)
            sigma_BN = opnav.body_attitude(dcm_CN, self.sigmaCB)
        else:
            sigma_BN = np.array(state.sigma_BN)
            dcm_CN = opnav.camera_dcm_CN(sigma_BN, self.sigmaCB)
        disk = opnav.project_body(r, dcm_CN, self.bodyRadiusM, self.fovRad, self.resolution,
                                  self.config.min_radius_px)
        code = _STATES[disk.reason]
        phase = math.nan
        if self.sunStateInMsg.isLinked():
            phase = opnav.phase_angle(r, np.array(self.sunStateInMsg().PositionVector))
            if disk.valid and phase > self.maxPhaseRad:
                code = NIGHT_SIDE
        measured = opnav.noisy(disk, self.config.center_noise_px, self.config.radius_noise_px, self.rng)

        circles = messaging.OpNavCirclesMsgPayload()
        circles.timeTag = CurrentSimNanos
        circles.cameraID = 1
        circles.valid = 1 if code == VALID else 0
        circles.planetIds = [float(self.bodyId)]
        circles.circlesCenters = [measured.pixel, measured.line] if code == VALID else [0.0, 0.0]
        circles.circlesRadii = [measured.radius_px] if code == VALID else [0.0]
        center_var = max(self.config.center_noise_px, _MIN_SIGMA_PX) ** 2  # [px^2]
        radius_var = max(self.config.radius_noise_px, _MIN_SIGMA_PX) ** 2  # [px^2]
        circles.uncertainty = [center_var, 0.0, 0.0, 0.0, center_var, 0.0, 0.0, 0.0, radius_var]
        self.circlesOutMsg.write(circles, CurrentSimNanos, self.moduleID)
        self.cameraConfigOutMsg.write(self.camera_payload(), CurrentSimNanos, self.moduleID)
        attitude = messaging.NavAttMsgPayload()
        attitude.timeTag = CurrentSimNanos * macros.NANO2SEC
        attitude.sigma_BN = list(sigma_BN)
        self.attOutMsg.write(attitude, CurrentSimNanos, self.moduleID)

        self.tLog.append(CurrentSimNanos * macros.NANO2SEC)
        self.truthPositionLog.append(r)
        self.truthVelocityLog.append(v)
        self.measurementLog.append([measured.pixel, measured.line, measured.radius_px] if code == VALID
                                   else [math.nan] * 3)
        self.stateLog.append(code)
        self.phaseAngleLog.append(phase)


class OpticalNavigation:
    """One spacecraft's optical navigation chain, built by
    :func:`build_optical_navigation`."""

    def __init__(self, camera, converter, odFilter, navRecorder, filterRecorder, opNavRecorder):
        self.camera = camera
        self.converter = converter
        self.filter = odFilter
        self.navRecorder = navRecorder
        self.filterRecorder = filterRecorder
        self.opNavRecorder = opNavRecorder


def initial_filter_state(r0_m, v0_mps, config: OpticalNavigationConfig) -> np.ndarray:
    """The filter's starting state: the true one plus one draw of the
    initial sigmas (its own seeded stream, apart from the pixel noise)."""
    rng = np.random.default_rng([config.seed, 1])
    error = np.concatenate([rng.normal(0.0, config.initial_position_sigma_m, 3),
                            rng.normal(0.0, config.initial_velocity_sigma_mps, 3)])
    return np.concatenate([np.asarray(r0_m, dtype=float).reshape(3), np.asarray(v0_mps, dtype=float).reshape(3)]) + error


def build_optical_navigation(scSim, process, tag: str, sc_object, sun_state_msg, config: OpticalNavigationConfig,
                             central_body: str, ideal_pointing: bool, scenario=None) -> OpticalNavigation:
    """Builds the chain (module docstring) on a new task of ``process``
    running every ``config.measurement_interval_s``. The filter's sigma
    point and noise-scale settings are the parameters
    ``navigation.opnav_ukf_*`` for ``scenario`` (``config.parameters``)."""
    task_name = f"{tag}OpNavTask"
    process.addTask(scSim.CreateNewTask(task_name, macros.sec2nano(config.measurement_interval_s)), _TASK_PRIORITY)

    camera = OpNavCamera(f"{tag}OpNavCamera", config, central_body, ideal_pointing)
    camera.scStateInMsg.subscribeTo(sc_object.scStateOutMsg)
    if sun_state_msg is not None:
        camera.sunStateInMsg.subscribeTo(sun_state_msg)
    scSim.AddModelToTask(task_name, camera, 30)

    converter = pixelLineConverter.pixelLineConverter()
    converter.ModelTag = f"{tag}PixelLineConverter"
    converter.cameraConfigInMsg.subscribeTo(camera.cameraConfigOutMsg)
    converter.circlesInMsg.subscribeTo(camera.circlesOutMsg)
    converter.attInMsg.subscribeTo(camera.attOutMsg)
    scSim.AddModelToTask(task_name, converter, 20)

    od_filter = relativeODuKF.relativeODuKF()
    od_filter.ModelTag = f"{tag}RelativeODuKF"
    od_filter.opNavInMsg.subscribeTo(converter.opNavOutMsg)
    od_filter.planetIdInit = opnav.BODY_IDS[central_body]
    od_filter.alpha = registry.value("navigation.opnav_ukf_alpha", scenario)  # [-]
    od_filter.beta = registry.value("navigation.opnav_ukf_beta", scenario)  # [-]
    od_filter.kappa = registry.value("navigation.opnav_ukf_kappa", scenario)  # [-]
    od_filter.noiseSF = registry.value("navigation.opnav_ukf_noise_scale", scenario)  # [-]
    od_filter.stateInit = initial_filter_state(sc_object.hub.r_CN_NInit, sc_object.hub.v_CN_NInit, config).tolist()
    sigma_r, sigma_v = config.initial_position_sigma_m, config.initial_velocity_sigma_mps  # [m], [m/s]
    od_filter.covarInit = np.diag([sigma_r ** 2] * 3 + [sigma_v ** 2] * 3).flatten().tolist()  # [m^2], [m^2/s^2]
    q_r = (config.process_noise_position_m / 1000.0) ** 2  # [km^2]: the filter's own units
    q_v = (config.process_noise_velocity_mps / 1000.0) ** 2  # [km^2/s^2]
    od_filter.qNoise = np.diag([q_r] * 3 + [q_v] * 3).flatten().tolist()
    scSim.AddModelToTask(task_name, od_filter, 10)

    nav_recorder = od_filter.navStateOutMsg.recorder()
    filter_recorder = od_filter.filtDataOutMsg.recorder()
    opnav_recorder = converter.opNavOutMsg.recorder()
    for recorder in (nav_recorder, filter_recorder, opnav_recorder):
        scSim.AddModelToTask(task_name, recorder, 0)
    chain = OpticalNavigation(camera, converter, od_filter, nav_recorder, filter_recorder, opnav_recorder)
    chain.taskName = task_name
    return chain


def result_series(name: str, chain: OpticalNavigation) -> list[TimeSeries]:
    """The chain's telemetry as ``{name}.optical_navigation.*`` series."""
    camera = chain.camera
    t_s = np.asarray(camera.tLog)
    count = len(t_s)
    truth_r = np.asarray(camera.truthPositionLog).reshape(-1, 3)
    truth_v = np.asarray(camera.truthVelocityLog).reshape(-1, 3)
    estimate_r = np.asarray(chain.navRecorder.r_BN_N).reshape(-1, 3)[-count:] if count else np.zeros((0, 3))
    estimate_v = np.asarray(chain.navRecorder.v_BN_N).reshape(-1, 3)[-count:] if count else np.zeros((0, 3))
    covariance = np.asarray(chain.filterRecorder.covar).reshape(-1, 6, 6)[-count:] if count else np.zeros((0, 6, 6))
    measured_r = np.asarray(chain.opNavRecorder.r_BN_N).reshape(-1, 3)[-count:] if count else np.zeros((0, 3))
    states = np.asarray(camera.stateLog, dtype=float)
    measured_error = np.where((states == VALID)[:, None], measured_r - truth_r, np.nan)
    sigma3 = 3.0 * np.sqrt(np.clip(np.diagonal(covariance, axis1=1, axis2=2), 0.0, None))  # [m], [m/s]
    prefix = f"{name}.optical_navigation"
    axes = ("x", "y", "z")
    position_error = estimate_r - truth_r
    velocity_error = estimate_v - truth_v
    return [
        TimeSeries(f"{prefix}.position_error", t_s, axes + ("norm",),
                   np.column_stack([position_error, np.linalg.norm(position_error, axis=1)]), units="m"),
        TimeSeries(f"{prefix}.velocity_error", t_s, axes + ("norm",),
                   np.column_stack([velocity_error, np.linalg.norm(velocity_error, axis=1)]), units="m/s"),
        TimeSeries(f"{prefix}.position_3sigma", t_s, axes, sigma3[:, :3], units="m"),
        TimeSeries(f"{prefix}.velocity_3sigma", t_s, axes, sigma3[:, 3:], units="m/s"),
        TimeSeries(f"{prefix}.measurement", t_s, ("pixel", "line", "radius"),
                   np.asarray(camera.measurementLog, dtype=float).reshape(-1, 3), units="px"),
        TimeSeries(f"{prefix}.measurement_error", t_s, axes + ("norm",),
                   np.column_stack([measured_error, np.linalg.norm(measured_error, axis=1)]), units="m"),
        TimeSeries(f"{prefix}.measurement_state", t_s, ("state",), states, units="-"),
        TimeSeries(f"{prefix}.range", t_s, ("range",), np.linalg.norm(truth_r, axis=1), units="m"),
        TimeSeries(f"{prefix}.phase_angle", t_s, ("phase_angle",),
                   np.degrees(np.asarray(camera.phaseAngleLog, dtype=float)), units="deg"),
    ]
