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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Thruster placement and plume impingement (static).

**Authority.** For every thruster with a position and a direction -- the
attitude thrusters (``actuators`` of kind ``thruster``) and thruster
nozzles mounted as equipment -- the torque arm about the centre of mass,
``r - r_c``, and the 6 x N matrix whose column ``i`` is the force and the
torque of thruster ``i`` at full thrust: ``F_i [t_i; (r_i - r_c) x t_i]``
(``t`` the direction of the force on the spacecraft, Basilisk's
``tHat_B``). A thruster with no thrust value counts 1 N (the column is per
newton) and says so.

**Centre-of-mass drift.** The matrix at the beginning of life, with the
fuel tank (``fuel_tank``: Basilisk's ``fuelTank`` at ``tank_position_b_m``)
full, and at the end of life, empty: the centre of mass moves from
``(m_dry c_dry + m_p r_tank) / (m_dry + m_p)`` to ``c_dry``. Station-keeping
propellant has no position in the scenario, so it moves nothing here.

**Plume impingement.** A geometric check only: a cone of the user's
half-angle from the nozzle along minus the force direction, intersected
with the model's parts by ray casting (the part the thruster is mounted on
ignored). It reports which parts the cone meets and the fraction of its
solid angle each takes. No plume flow physics (expansion, density, heating
or contamination) is modelled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import common


@dataclass
class ThrusterColumn:
    name: str
    position_b_m: np.ndarray  # [m]
    direction_b: np.ndarray  # [-] force on the spacecraft
    thrust_n: float  # [N]
    thrust_known: bool
    arm_bol_m: np.ndarray  # [m] r - r_c at the beginning of life
    arm_eol_m: np.ndarray  # [m] at the end of life


@dataclass
class ThrusterAuthority:
    """The thruster set's force and torque authority, at the beginning and
    the end of life."""

    spacecraft: str
    columns: list = field(default_factory=list)  # list[ThrusterColumn]
    com_bol_b_m: np.ndarray | None = None  # [m]
    com_eol_b_m: np.ndarray | None = None  # [m]
    propellant_kg: float = 0.0  # [kg] in the fuel tank at the beginning of life
    matrix_bol: np.ndarray | None = None  # (6, N): [N] then [N*m]
    matrix_eol: np.ndarray | None = None
    notes: list = field(default_factory=list)

    def rank(self, which: str = "bol") -> int:
        matrix = self.matrix_bol if which == "bol" else self.matrix_eol
        return int(np.linalg.matrix_rank(matrix)) if matrix is not None and matrix.size else 0

    def rows(self) -> list[dict]:
        rows = []
        for k, c in enumerate(self.columns):
            rows.append({"thruster": c.name, "thrust_n": c.thrust_n,
                         "torque_bol_n_m": [float(v) for v in self.matrix_bol[3:, k]],
                         "torque_eol_n_m": [float(v) for v in self.matrix_eol[3:, k]],
                         "arm_bol_m": [float(v) for v in c.arm_bol_m], "arm_eol_m": [float(v) for v in c.arm_eol_m],
                         "arm_change_m": float(np.linalg.norm(c.arm_eol_m - c.arm_bol_m))})
        return rows


def _factory_thrust(params) -> float | None:
    """A named Basilisk thruster type's MaxThrust from its factory (public
    API), or None without Basilisk."""
    kind = params.get("thruster_type")
    if not kind:
        return None
    try:
        from Basilisk.utilities import simIncludeThruster
    except ImportError:
        return None
    try:
        factory = simIncludeThruster.thrusterFactory()
        thruster = factory.create(kind, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        return float(thruster.MaxThrust)
    except Exception:  # noqa: BLE001 -- an unknown type is reported as "per newton"
        return None


def centres_of_mass(sc) -> tuple[np.ndarray, np.ndarray, float]:
    """``(c_bol, c_eol, propellant)``: the centre of mass with the fuel tank
    full and empty, and the propellant [kg]."""
    c_dry = np.asarray(sc.center_of_mass_b_m, dtype=float)
    m_dry = float(sc.dry_mass_kg)
    if sc.fuel_tank is None or sc.fuel_tank.propellant_mass_kg <= 0.0:
        return c_dry, c_dry, 0.0
    m_p = float(sc.fuel_tank.propellant_mass_kg)
    r_tank = np.asarray(sc.fuel_tank.tank_position_b_m, dtype=float)
    return (m_dry * c_dry + m_p * r_tank) / (m_dry + m_p), c_dry, m_p


def thruster_authority(sc) -> ThrusterAuthority:
    """:class:`ThrusterAuthority` of spacecraft ``sc``."""
    result = ThrusterAuthority(sc.name)
    c_bol, c_eol, propellant = centres_of_mass(sc)
    result.com_bol_b_m, result.com_eol_b_m, result.propellant_kg = c_bol, c_eol, propellant
    params_of = {a.name: a.params or {} for a in sc.actuators if a.kind == "thruster"}
    for item in common.mounted(sc):
        if item.kind != "thruster":
            continue
        if item.position_b_m is None or item.boresight_b is None:
            result.notes.append(f"{item.name}: no position or direction, left out")
            continue
        thrust = item.thrust_n
        if thrust is None and item.name in params_of:
            thrust = _factory_thrust(params_of[item.name])
        known = thrust is not None
        if not known:
            result.notes.append(f"{item.name}: no thrust value, its column is per newton")
            thrust = 1.0  # [N]
        result.columns.append(ThrusterColumn(item.name, item.position_b_m, item.boresight_b, float(thrust), known,
                                             item.position_b_m - c_bol, item.position_b_m - c_eol))
    if propellant == 0.0:
        result.notes.append("no fuel tank with propellant: the centre of mass does not move")
    if sc.station_keeping is not None or sc.constant_thrust is not None:
        result.notes.append("station-keeping and constant-thrust propellant have no position: they move no "
                            "centre of mass here")

    def matrix(arms):
        columns = [np.concatenate([c.thrust_n * c.direction_b, c.thrust_n * np.cross(arm, c.direction_b)])
                   for c, arm in zip(result.columns, arms)]
        return np.column_stack(columns) if columns else np.zeros((6, 0))

    result.matrix_bol = matrix([c.arm_bol_m for c in result.columns])
    result.matrix_eol = matrix([c.arm_eol_m for c in result.columns])
    return result


@dataclass
class PlumeImpingement:
    """One thruster's plume cone against the model."""

    spacecraft: str
    thruster: str
    half_angle_deg: float  # [deg]
    blocked_fraction: float  # [-] of the cone's solid angle
    by_part: dict  # part -> [-]
    standard_error: float  # [-]
    samples: int


def plume_impingement(sc, samples: int | None = None, base_dir=None) -> tuple[list, list]:
    """``(impingements, skipped)``: :class:`PlumeImpingement` for every
    thruster with a plume half-angle, and ``(thruster, reason)`` for those
    without one. Deployed configuration."""
    found, skipped = [], []
    if sc.model is None:
        return found, [("all", "the spacecraft has no 3D model")]
    scene = common.scene(sc, "deployed", base_dir)
    count = common.samples_for(sc, samples)
    for item in common.mounted(sc):
        if item.kind != "thruster":
            continue
        if item.plume_half_angle_deg is None or item.position_b_m is None or item.boresight_b is None:
            skipped.append((item.name, "no plume half-angle, position or direction"))
            continue
        exclude = (item.part,) if item.part else ()
        blockage = scene.cone_blockage(item.position_b_m, -item.boresight_b, math.radians(item.plume_half_angle_deg),
                                       count, exclude)
        found.append(PlumeImpingement(sc.name, item.name, item.plume_half_angle_deg, blockage.fraction,
                                      blockage.by_part, blockage.standard_error, blockage.samples))
    return found, skipped
