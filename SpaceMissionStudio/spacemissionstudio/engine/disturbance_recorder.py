#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""Disturbance torques recorded during a run (model analyses, decision
D-07), for a spacecraft with ``model_analyses.disturbance_torques``.

A Python ``SysModel`` that runs after the spacecraft has integrated each
step and records, about the centre of mass and in the body frame:

- **aerodynamic** and **solar radiation pressure** torques: what Basilisk's
  drag and SRP effectors computed (their public ``forceExternal_B`` and
  ``torqueExternalPntB_B``, about the body origin ``B``), moved to the
  centre of mass, ``T_c = T_B - r_CB x F``. They are Basilisk's own values,
  with no change (no self-shadowing): the effectors' last evaluation of
  the step, the integrator's final stage;
- **gravity gradient**: ``T = (3 mu / R^5) r_B x (I r_B)``, from the
  spacecraft's position relative to the central body and the hub's
  inertia about its centre of mass (NASA SP-8024's vector form), whether
  or not the run applies Basilisk's gravity-gradient effector;
- **residual dipole**: ``T = m x B_B``, with ``m`` the user's dipole and
  ``B`` the WMM field (Basilisk's ``magneticFieldWMM``) at the spacecraft.

Nothing it records is fed back to the dynamics. The centre of mass and
inertia are the hub's (the scenario's): moving propellant and flexible
arrays are not followed.
"""

from __future__ import annotations

import numpy as np

from .orbit_maintenance import LogThinner

#: Its priority in the dynamics task: after the spacecraft (10) and the
#: magnetic field model (default -1), so it reads this step's values.
PRIORITY = -10

SOURCES = ("aero", "srp", "gravity_gradient", "magnetic")


def _vector(value) -> np.ndarray:
    return np.asarray(value, dtype=float).reshape(3)


def _make_module():
    from Basilisk.architecture import sysModel
    from Basilisk.utilities import RigidBodyKinematics as rbk
    from Basilisk.utilities import macros

    class DisturbanceRecorderModule(sysModel.SysModel):
        """Records the four disturbance torques of one spacecraft (module
        docstring)."""

        def __init__(self, name, sc_object, mu, planet_state_msg, drag_effector, srp_effector, field_msg,
                     dipole_a_m2, record_interval_s):
            super().__init__()
            self.ModelTag = name
            self.stateMsg = sc_object.scStateOutMsg
            self.planetMsg = planet_state_msg
            self.mu = float(mu)  # [m^3/s^2]
            self.inertia = np.asarray(sc_object.hub.IHubPntBc_B, dtype=float).reshape(3, 3)  # [kg*m^2]
            self.rC = _vector(sc_object.hub.r_BcB_B)  # [m] centre of mass from B
            self.effectors = {"aero": drag_effector, "srp": srp_effector}
            self.fieldMsg = field_msg
            self.dipole = _vector(dipole_a_m2)  # [A*m^2] body frame
            self.logThinner = LogThinner(record_interval_s)
            self.tLog: list = []
            self.torqueLog = {source: [] for source in SOURCES}  # [N*m] about the centre of mass, body frame
            self.forceLog = {"aero": [], "srp": []}  # [N] body frame
            self.fieldLog: list = []  # [T] body frame

        def UpdateState(self, CurrentSimNanos):
            t = CurrentSimNanos * macros.NANO2SEC  # [s]
            if not self.logThinner.due(t):
                return
            state = self.stateMsg.read()
            dcm_bn = rbk.MRP2C(_vector(state.sigma_BN))
            for source, effector in self.effectors.items():
                if effector is None:
                    force, torque = np.zeros(3), np.zeros(3)
                else:
                    force = _vector(effector.forceExternal_B)  # [N]
                    torque = _vector(effector.torqueExternalPntB_B) - np.cross(self.rC, force)  # [N*m]
                self.forceLog[source].append(force)
                self.torqueLog[source].append(torque)
            r_n = _vector(state.r_BN_N)
            if self.planetMsg is not None:
                r_n = r_n - _vector(self.planetMsg.read().PositionVector)
            r_b = dcm_bn @ r_n
            radius = float(np.linalg.norm(r_b))  # [m]
            self.torqueLog["gravity_gradient"].append(
                3.0 * self.mu / radius ** 5 * np.cross(r_b, self.inertia @ r_b))
            if self.fieldMsg is not None:
                field_b = dcm_bn @ _vector(self.fieldMsg.read().magField_N)  # [T]
            else:
                field_b = np.zeros(3)
            self.fieldLog.append(field_b)
            self.torqueLog["magnetic"].append(np.cross(self.dipole, field_b))
            self.tLog.append(t)

    return DisturbanceRecorderModule


_MODULE = None


def DisturbanceRecorder(name, sc_object, mu, planet_state_msg, drag_effector, srp_effector,  # noqa: N802
                        field_msg, dipole_a_m2, record_interval_s=0.0):
    """A :class:`DisturbanceRecorderModule` (built on first use: Basilisk)."""
    global _MODULE
    if _MODULE is None:
        _MODULE = _make_module()
    return _MODULE(name, sc_object, mu, planet_state_msg, drag_effector, srp_effector, field_msg, dipole_a_m2,
                   record_interval_s)


def series(name: str, recorder) -> list:
    """The recorder's ``TimeSeries``: each source's torque, the total, the
    aerodynamic and SRP forces, and the field in the body frame."""
    from .results import TimeSeries

    t = np.asarray(recorder.tLog, dtype=float)
    axes = ("x", "y", "z")

    def stack(rows):
        return np.asarray(rows, dtype=float).reshape(len(t), 3)

    out = []
    total = np.zeros((len(t), 3))
    for source in SOURCES:
        values = stack(recorder.torqueLog[source])
        total += values
        out.append(TimeSeries(f"{name}.disturbance.{source}_torque", t, axes, values, units="N*m"))
    out.append(TimeSeries(f"{name}.disturbance.total_torque", t, axes, total, units="N*m"))
    for source in ("aero", "srp"):
        out.append(TimeSeries(f"{name}.disturbance.{source}_force", t, axes, stack(recorder.forceLog[source]),
                              units="N"))
    out.append(TimeSeries(f"{name}.disturbance.magnetic_field_body", t, axes, stack(recorder.fieldLog), units="T"))
    return out


#: The series :func:`series` makes for spacecraft ``name`` (engine.series_names).
def series_names(name: str) -> list[str]:
    return ([f"{name}.disturbance.{source}_torque" for source in SOURCES]
            + [f"{name}.disturbance.total_torque", f"{name}.disturbance.aero_force", f"{name}.disturbance.srp_force",
               f"{name}.disturbance.magnetic_field_body"])
