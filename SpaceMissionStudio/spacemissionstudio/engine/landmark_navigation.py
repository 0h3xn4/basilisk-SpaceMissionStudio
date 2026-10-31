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
r"""Landmark navigation in a run (``schema.scenario.LandmarkNavigationConfig``):
Basilisk's ``pinholeCamera`` and the tool's filter (``engine.landmarks``),
on a task of their own that runs once per ``measurement_interval_s``,
after the dynamics.

1. :class:`LandmarkCameraInputs` (the tool's own) writes what
   ``pinholeCamera`` reads. That module takes the body's ephemeris
   position as measured from the Sun (its Sun direction is minus that
   position) and the spacecraft's position in the same frame; the run's
   SPICE origin is the body itself, so both are written shifted by the
   body's position from the Sun (minus the Sun's SPICE position). The
   attitude is the spacecraft's, or, in an orbit-only run, the one that
   points the camera at the body's centre.
2. ``pinholeCamera`` (Basilisk, unmodified) reports the whole pixel of
   every landmark it sees.
3. :class:`LandmarkNavigationFilter` (the tool's own) adds the optional
   pixel noise and runs :class:`engine.landmarks.LandmarkFilter`: it
   predicts to the image's time with the shape's gravity and the body's
   spin, then updates with the landmarks seen. Attitude knowledge and the
   body's orientation are exact; the landmark map is the camera's.
"""

from __future__ import annotations

import math

import numpy as np

from Basilisk.architecture import messaging, sysModel
from Basilisk.simulation import pinholeCamera
from Basilisk.utilities import RigidBodyKinematics as rbk
from Basilisk.utilities import macros

from ..config import registry
from ..schema.scenario import LandmarkNavigationConfig
from . import landmarks
from .polyhedron import Polyhedron
from .results import TimeSeries
from .small_bodies import SmallBody

_TASK_PRIORITY = -10  # after the dynamics task (priority -1) at the same time


class LandmarkCameraInputs(sysModel.SysModel):
    """Heliocentric copies of the body's and the spacecraft's states for
    ``pinholeCamera`` (module docstring, step 1)."""

    def __init__(self, name: str, config: LandmarkNavigationConfig, ideal_pointing: bool):
        super().__init__()
        self.ModelTag = name
        self.scStateInMsg = messaging.SCStatesMsgReader()
        self.sunStateInMsg = messaging.SpicePlanetStateMsgReader()
        self.bodyStateInMsg = messaging.SpicePlanetStateMsgReader()
        self.ephemerisOutMsg = messaging.EphemerisMsg()
        self.scStateOutMsg = messaging.SCStatesMsg()
        self.idealPointing = ideal_pointing
        self.dcmCB = rbk.MRP2C(np.asarray(config.camera_mrp_cb, dtype=float))
        self.tLog: list[float] = []
        self.truthPositionLog: list[np.ndarray] = []
        self.truthVelocityLog: list[np.ndarray] = []

    def UpdateState(self, CurrentSimNanos):
        state = self.scStateInMsg()
        r = np.array(state.r_BN_N)  # [m] from the body's centre
        v = np.array(state.v_BN_N)  # [m/s]
        body_from_sun = -np.array(self.sunStateInMsg().PositionVector)  # [m]
        dcm_PN = np.array(self.bodyStateInMsg().J20002Pfix)
        if self.idealPointing:
            dcm_BN = self.dcmCB.T @ landmarks.nadir_dcm_CN(r, v)
            sigma_BN = rbk.C2MRP(dcm_BN)
        else:
            sigma_BN = np.array(state.sigma_BN)
        ephemeris = messaging.EphemerisMsgPayload()
        ephemeris.r_BdyZero_N = body_from_sun.tolist()
        ephemeris.sigma_BN = list(rbk.C2MRP(dcm_PN))
        ephemeris.timeTag = CurrentSimNanos * macros.NANO2SEC
        self.ephemerisOutMsg.write(ephemeris, CurrentSimNanos, self.moduleID)
        shifted = messaging.SCStatesMsgPayload()
        shifted.r_BN_N = (r + body_from_sun).tolist()
        shifted.v_BN_N = v.tolist()
        shifted.sigma_BN = list(sigma_BN)
        self.scStateOutMsg.write(shifted, CurrentSimNanos, self.moduleID)
        self.tLog.append(CurrentSimNanos * macros.NANO2SEC)
        self.truthPositionLog.append(r)
        self.truthVelocityLog.append(v)


class LandmarkNavigationFilter(sysModel.SysModel):
    """Runs :class:`engine.landmarks.LandmarkFilter` on the camera's
    landmark messages (module docstring, step 3)."""

    def __init__(self, name: str, config: LandmarkNavigationConfig, body: SmallBody, shape: Polyhedron,
                 landmarks_P: np.ndarray, r0_m, v0_mps, scenario=None):
        super().__init__()
        self.ModelTag = name
        self.attitudeInMsg = messaging.SCStatesMsgReader()
        self.bodyStateInMsg = messaging.SpicePlanetStateMsgReader()
        self.landmarkInMsgs: list[messaging.LandmarkMsgReader] = []
        self.dcmCB = rbk.MRP2C(np.asarray(config.camera_mrp_cb, dtype=float))
        self.pixelNoise = config.pixel_noise_px
        self.rng = np.random.default_rng([config.seed, 3])
        f_over_w = landmarks.FOCAL_LENGTH_M / landmarks.pixel_pitch_m(math.radians(config.field_of_view_deg),
                                                                     config.resolution_px[0])
        pixel_sigma = math.hypot(landmarks.QUANTIZATION_SIGMA_PX, config.pixel_noise_px)  # [px]
        x0 = landmarks.initial_state(r0_m, v0_mps, config.initial_position_sigma_m,
                                     config.initial_velocity_sigma_mps, config.seed)
        self.filter = landmarks.LandmarkFilter(shape, body.gm_m3_s2, body.spin_rad_s, landmarks_P, x0,
                                               config.initial_position_sigma_m, config.initial_velocity_sigma_mps,
                                               config.process_noise_mps2_per_sqrt_hz, pixel_sigma, f_over_w,
                                               registry.value("navigation.landmark_filter_max_step_s", scenario))
        self.lastNanos = None
        self.lastDcmPN = None
        self.tLog: list[float] = []
        self.estimateLog: list[np.ndarray] = []
        self.sigmaLog: list[np.ndarray] = []
        self.seenLog: list[int] = []
        self.residualLog: list[float] = []

    def Reset(self, CurrentSimNanos):
        self.lastNanos = None

    def UpdateState(self, CurrentSimNanos):
        dcm_PN = np.array(self.bodyStateInMsg().J20002Pfix)
        if self.lastNanos is not None:
            self.filter.propagate((CurrentSimNanos - self.lastNanos) * macros.NANO2SEC, self.lastDcmPN)
        self.lastNanos, self.lastDcmPN = CurrentSimNanos, dcm_PN
        dcm_CN = self.dcmCB @ rbk.MRP2C(np.array(self.attitudeInMsg().sigma_BN))
        indices, pixels = [], []
        for index, reader in enumerate(self.landmarkInMsgs):
            payload = reader()
            if payload.isVisible:
                indices.append(index)
                pixels.append([float(payload.pL[0]), float(payload.pL[1])])
        pixels = np.asarray(pixels, dtype=float).reshape(-1, 2)
        if self.pixelNoise > 0.0 and len(pixels):
            pixels = pixels + self.rng.normal(0.0, self.pixelNoise, pixels.shape)
        update = self.filter.update(indices, pixels, dcm_PN, dcm_CN)
        self.tLog.append(CurrentSimNanos * macros.NANO2SEC)
        self.estimateLog.append(self.filter.x.copy())
        self.sigmaLog.append(np.sqrt(np.clip(np.diag(self.filter.P), 0.0, None)))
        self.seenLog.append(update.used)
        self.residualLog.append(update.residual_rms_px)


class LandmarkNavigation:
    """One spacecraft's landmark navigation chain, built by
    :func:`build_landmark_navigation`."""

    def __init__(self, inputs, camera, navFilter, landmarks_P, normals_P):
        self.inputs = inputs
        self.camera = camera
        self.filter = navFilter
        self.landmarks_P = landmarks_P
        self.normals_P = normals_P


def configure_camera(camera, config: LandmarkNavigationConfig) -> None:
    """``pinholeCamera`` settings for ``config``'s field of view and detector."""
    nx, ny = config.resolution_px
    camera.f = landmarks.FOCAL_LENGTH_M  # [m]
    camera.nxPixel = float(nx)  # [px]
    camera.nyPixel = float(ny)  # [px]
    camera.wPixel = landmarks.pixel_pitch_m(math.radians(config.field_of_view_deg), nx)  # [m]
    camera.dcm_CB = rbk.MRP2C(np.asarray(config.camera_mrp_cb, dtype=float)).tolist()
    camera.maskSun = math.radians(config.min_sun_elevation_deg)  # [rad]


def build_landmark_navigation(scSim, process, tag: str, sc_object, sun_state_msg, body_state_msg,
                              config: LandmarkNavigationConfig, body: SmallBody, shape: Polyhedron,
                              ideal_pointing: bool, scenario=None) -> LandmarkNavigation:
    """Builds the chain (module docstring) on a new task of ``process``
    running every ``config.measurement_interval_s``."""
    task_name = f"{tag}LandmarkNavTask"
    process.addTask(scSim.CreateNewTask(task_name, macros.sec2nano(config.measurement_interval_s)), _TASK_PRIORITY)

    inputs = LandmarkCameraInputs(f"{tag}LandmarkCameraInputs", config, ideal_pointing)
    inputs.scStateInMsg.subscribeTo(sc_object.scStateOutMsg)
    inputs.sunStateInMsg.subscribeTo(sun_state_msg)
    inputs.bodyStateInMsg.subscribeTo(body_state_msg)
    scSim.AddModelToTask(task_name, inputs, 30)

    landmarks_P, normals_P = landmarks.place_landmarks(shape, config.landmark_count, config.seed)
    camera = pinholeCamera.PinholeCamera()
    camera.ModelTag = f"{tag}PinholeCamera"
    configure_camera(camera, config)
    for position, normal in zip(landmarks_P, normals_P):
        camera.addLandmark(position.tolist(), normal.tolist())
    camera.ephemerisInMsg.subscribeTo(inputs.ephemerisOutMsg)
    camera.scStateInMsg.subscribeTo(inputs.scStateOutMsg)
    scSim.AddModelToTask(task_name, camera, 20)

    nav_filter = LandmarkNavigationFilter(f"{tag}LandmarkNavFilter", config, body, shape, landmarks_P,
                                          sc_object.hub.r_CN_NInit, sc_object.hub.v_CN_NInit, scenario=scenario)
    nav_filter.attitudeInMsg.subscribeTo(inputs.scStateOutMsg)
    nav_filter.bodyStateInMsg.subscribeTo(body_state_msg)
    for message in camera.landmarkOutMsgs:
        reader = messaging.LandmarkMsgReader()
        reader.subscribeTo(message)
        nav_filter.landmarkInMsgs.append(reader)
    scSim.AddModelToTask(task_name, nav_filter, 10)
    chain = LandmarkNavigation(inputs, camera, nav_filter, landmarks_P, normals_P)
    chain.taskName = task_name
    return chain


def result_series(name: str, chain: LandmarkNavigation) -> list[TimeSeries]:
    """The chain's telemetry as ``{name}.landmark_navigation.*`` series."""
    inputs, nav = chain.inputs, chain.filter
    count = len(nav.tLog)
    t_s = np.asarray(nav.tLog)
    truth_r = np.asarray(inputs.truthPositionLog).reshape(-1, 3)[-count:] if count else np.zeros((0, 3))
    truth_v = np.asarray(inputs.truthVelocityLog).reshape(-1, 3)[-count:] if count else np.zeros((0, 3))
    estimate = np.asarray(nav.estimateLog).reshape(-1, 6)
    sigma3 = 3.0 * np.asarray(nav.sigmaLog).reshape(-1, 6)  # [m], [m/s]
    prefix = f"{name}.landmark_navigation"
    axes = ("x", "y", "z")
    position_error = estimate[:, :3] - truth_r
    velocity_error = estimate[:, 3:] - truth_v
    return [
        TimeSeries(f"{prefix}.position_error", t_s, axes + ("norm",),
                   np.column_stack([position_error, np.linalg.norm(position_error, axis=1)]), units="m"),
        TimeSeries(f"{prefix}.velocity_error", t_s, axes + ("norm",),
                   np.column_stack([velocity_error, np.linalg.norm(velocity_error, axis=1)]), units="m/s"),
        TimeSeries(f"{prefix}.position_3sigma", t_s, axes, sigma3[:, :3], units="m"),
        TimeSeries(f"{prefix}.velocity_3sigma", t_s, axes, sigma3[:, 3:], units="m/s"),
        TimeSeries(f"{prefix}.landmarks_seen", t_s, ("count",), np.asarray(nav.seenLog, dtype=float), units="-"),
        TimeSeries(f"{prefix}.residual_rms", t_s, ("rms",), np.asarray(nav.residualLog, dtype=float), units="px"),
    ]
