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

r"""
The scenario file format: a versioned, human-readable JSON schema for
everything needed to define and run a mission-analysis case (spacecraft
config, orbit initial conditions, epoch, central body, sensors/actuators,
FSW mode, ground stations).

Deliberately dependency-light: standard-library ``dataclasses`` + hand
-written validation, not a pickled Python object and not a third-party
schema library (pydantic, etc.) -- consistent with keeping the backend
service layer's own dependency footprint small (Basilisk itself, plus
whatever the GUI needs, is already enough surface area). This module has
NO Basilisk import and is fully unit-testable without a Basilisk build --
see ``tests/test_scenario_schema.py``.

Versioning
----------
Every scenario file carries a top-level ``schema_version`` integer.
``load_scenario()`` runs the file through ``migrations.MIGRATIONS`` before
constructing a :class:`Scenario`, so old scenario files keep loading as the
schema grows -- see ``migrations.py``. Bump ``CURRENT_SCHEMA_VERSION`` and
add a migration function whenever a field is added, renamed, or removed in
a way that would break an older file.

Phase 0 scope note
-------------------
This schema is intentionally more complete than what Phase 0's
``engine.service.SimulationService`` actually consumes (see that module's
docstring for exactly what Phase 0 wires up: central-body point-mass/
spherical-harmonics gravity, one or more spacecraft with classical
-elements/Cartesian/TLE initial conditions, propagation only). Fields for
sensors, actuators, FSW modes, and ground stations are validated here and
carried through save/load round-trips starting now, precisely so the
schema does not need a disruptive reshape once Phase 2/3 start consuming
them -- retrofitting schema versioning after the fact is much more
painful than reserving the shape up front.
"""

from __future__ import annotations

import re

import dataclasses
import json
import math
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, UTC
from pathlib import Path
import typing
from typing import Any

from .epochs import parse_epoch_utc
from .tle_format import TLEError, check_lines
from .command import Command, command_dict, report_before_propagate_errors, runs_sequence

CURRENT_SCHEMA_VERSION = 4

# Limits on what a scenario may ask for (audit R9): far above any template
# (at most 6 spacecraft, 27 kB) and the editor's own ranges, so that a shared
# file cannot fill the memory or run for ever before it is refused.
MAX_SPACECRAFT = 1000
MAX_DESCRIPTION_CHARS = 100_000
MAX_SCENARIO_FILE_BYTES = 20_000_000  # [byte]
MIN_DYNAMICS_TASK_RATE_S = 0.001  # [s] the editor's least

# Central bodies (and third bodies) a run can use: Basilisk's
# simIncludeGravBody.gravBodyFactory names whose SPICE states the bundled
# planetary ephemeris (DE430, engine.kernels) holds -- see engine/service.py
# for where this list is consumed. DE430 has the Mars and Jupiter system
# barycentres, not the planets themselves, so those two are offered as
# their barycentres (Basilisk gives them the planet's own mass and radius):
# a run around "mars" stopped the whole process with SPICE(SPKINSUFFDATA),
# and Basilisk has no body named "jupiter" (UNRUNNABLE_BODIES).
SUPPORTED_CENTRAL_BODIES = (
    "sun", "mercury", "venus", "earth", "moon", "mars barycenter", "jupiter barycenter",
)
# Small bodies a run can orbit but not take as third bodies: their
# ephemeris is a separate NAIF kernel and their gravity can be a shape
# model (engine.small_bodies, engine.polyhedron).
SMALL_BODY_CENTRAL_BODIES = ("eros",)
# Central bodies with an albedo map in Basilisk's support data, and the
# map's file stem (DataFile.AlbedoData): CERES 2018, all-sky, for Earth;
# MGS TES for Mars. 5 x 5 deg cells.
ALBEDO_MAPS = {"earth": "Earth_ALB_2018_CERES_All_5x5", "mars barycenter": "Mars_ALB_TES_5x5"}
# The span the small bodies' ephemeris kernels cover (eros_1900_2100.bsp), UTC.
SMALL_BODY_EPHEMERIS_SPAN = {"eros": ("1900-01-01T00:00:00", "2100-01-01T00:00:00")}
# Central bodies optical navigation can use: the ones Basilisk's
# pixelLineConverter and relativeODuKF know by number (engine.opnav.BODY_IDS).
OPTICAL_NAVIGATION_BODIES = ("earth", "mars barycenter", "jupiter barycenter")
# Names an older file may hold that no run can use, and the body to use instead.
UNRUNNABLE_BODIES = {
    "mars": ("mars barycenter", "the bundled planetary ephemeris (DE430) has the Mars system barycentre, "
             "about 0.2 m from Mars's centre, not Mars itself"),
    "jupiter": ("jupiter barycenter", "the bundled planetary ephemeris (DE430) has the Jupiter system "
                "barycentre, not Jupiter itself, and Basilisk has no body named 'jupiter'"),
}


def _body_problem(where: str, name: str, small_bodies: bool = False) -> str:
    """Why ``name`` cannot be used at ``where``, naming the body to use instead."""
    if name in UNRUNNABLE_BODIES:
        instead, reason = UNRUNNABLE_BODIES[name]
        return f"{where} {name!r} cannot be run: {reason}; use {instead!r}"
    if name in SMALL_BODY_CENTRAL_BODIES and not small_bodies:
        return f"{where} {name!r} can only be the central body"
    allowed = SUPPORTED_CENTRAL_BODIES + (SMALL_BODY_CENTRAL_BODIES if small_bodies else ())
    return f"{where} {name!r} must be one of {allowed}"

ORBIT_IC_TYPES = ("classical_elements", "cartesian", "tle")

# classical_elements only: which anomaly field the user supplied (they're
# not interchangeable inputs -- mean anomaly needs Kepler's equation solved
# to get true anomaly, see engine.service._orbit_ic_to_rv).
ANOMALY_TYPES = ("true", "mean")

# Sensor/actuator/FSW-mode kinds engine.service.SimulationService actually
# wires up -- see that module's docstring for the exact Basilisk module
# each one maps to and for engine.fsw's guidance-chain construction.
# "reaction_wheel" (mrpFeedback + rwMotorTorque + reactionWheelStateEffector)
# and "thruster" (mrpFeedback + thrForceMapping + thrFiringSchmitt +
# thrusterDynamicEffector) are both real control-torque actuation paths --
# see SpacecraftConfig.validate() for why a spacecraft may use one or the
# other but not both. "magnetic_torque_rod" (MtbEffector + tamComm +
# mtbMomentumManagement) is wired up too, but ONLY for continuous
# reaction-wheel momentum management (see MagneticMomentumManagementConfig)
# -- there is no standalone attitude-control/detumble mode built on
# magnetic torque rods alone (Basilisk ships no ready-made B-dot-style
# controller for it), so a "magnetic_torque_rod" actuator with
# magnetic_momentum_management unset would simply never receive a
# command; SpacecraftConfig.validate() rejects that combination early
# rather than silently building a dead actuator (unlike Phase 0's drag/SRP
# flags, which stayed inert booleans, an actuator kind that silently did
# nothing would be a live foot-gun -- a spacecraft configured to detumble
# on magnetic torque rods that simply never fire).
SUPPORTED_SENSOR_KINDS = ("star_tracker", "imu", "coarse_sun_sensor", "magnetometer", "thermal")
SUPPORTED_ACTUATOR_KINDS = ("reaction_wheel", "thruster", "magnetic_torque_rod")

# The only maxMomentum values [N*m*s] simIncludeRW.rwFactory accepts for
# these named wheels; any other value, or none, makes rwFactory.create()
# call exit(1) and take the whole app down with it.
NAMED_RW_MAX_MOMENTUM_OPTIONS = {
    "Honeywell_HR12": (12.0, 25.0, 50.0),
    "Honeywell_HR14": (25.0, 50.0, 75.0),
    "Honeywell_HR16": (50.0, 75.0, 100.0),
}

# Every wheel and thruster type simIncludeRW.rwFactory /
# simIncludeThruster.thrusterFactory build (Basilisk 2.12.0, the methods of
# each factory class): any other name makes create() call exit(1).
RW_TYPES = ("custom", "Honeywell_HR16", "Honeywell_HR14", "Honeywell_HR12", "BCT_RWP015", "NanoAvionics_RW0")
THRUSTER_TYPES = ("MOOG_Monarc_1", "MOOG_Monarc_5", "MOOG_Monarc_22_6", "MOOG_Monarc_22_12", "MOOG_Monarc_90LT",
                  "MOOG_Monarc_90HT", "MOOG_Monarc_445", "SEP", "TEST_Thruster", "EPSS_C2", "Blank_Thruster")

# rwFactory.create() / thrusterFactory.create() keyword arguments by the type
# each must have (engine.fsw coerces the numbers to float): a wrong type, a
# non-positive limit, a zero betaStatic or a label over 5 characters makes
# the factory call exit(1) instead of raising (simIncludeRW.py,
# simIncludeThruster.py).
_RW_NUMBER_KWARGS = ("Omega", "Omega_max", "maxMomentum", "P_max", "betaStatic", "fCoulomb", "fStatic", "cViscous",
                     "u_min", "u_max", "Js")
_RW_POSITIVE_KWARGS = ("Omega_max", "maxMomentum", "Js")
_RW_BOOL_KWARGS = ("useRWfriction", "useMinTorque", "useMaxTorque")
_THRUSTER_NUMBER_KWARGS = ("areaNozzle", "steadyIsp", "MaxThrust", "thrusterMagDisp", "MinOnTime", "cutoffFrequency",
                           "MaxSwirlTorque")
_THRUSTER_POSITIVE_KWARGS = ("steadyIsp", "MaxThrust")
_THRUSTER_BOOL_KWARGS = ("useMinPulseTime",)


def _factory_param_errors(where: str, params: dict, numbers, positive, bools) -> list:
    """What in ``params`` would make a Basilisk device factory exit."""
    errors = []
    for key in numbers:
        if key in params and not _is_finite_number(params[key]):
            errors.append(f"{where}: params[{key!r}] must be a finite number, got {params[key]!r}")
        elif key in positive and key in params and params[key] <= 0:
            errors.append(f"{where}: params[{key!r}] must be > 0, got {params[key]!r}")
    for key in bools:
        if key in params and not isinstance(params[key], bool):
            errors.append(f"{where}: params[{key!r}] must be true or false, got {params[key]!r}")
    label = params.get("label")
    if label is not None and not (isinstance(label, str) and len(label) <= 5):
        errors.append(f"{where}: params['label'] must be text of at most 5 characters (Basilisk's limit)")
    return errors


def reaction_wheel_param_errors(where: str, params: dict) -> list:
    """What would make ``rwFactory.create()`` exit for these params."""
    errors = []
    rw_type = params.get("rw_type", "custom")
    if rw_type not in RW_TYPES:
        errors.append(f"{where}: params['rw_type'] {rw_type!r} must be one of {RW_TYPES}")
    errors += _factory_param_errors(where, params, _RW_NUMBER_KWARGS, _RW_POSITIVE_KWARGS, _RW_BOOL_KWARGS)
    if "RWModel" in params and not (isinstance(params["RWModel"], int) and not isinstance(params["RWModel"], bool)):
        errors.append(f"{where}: params['RWModel'] must be an integer")
    if _is_finite_number(params.get("betaStatic")) and params["betaStatic"] == 0:
        errors.append(f"{where}: params['betaStatic'] must not be 0 (positive turns Stribeck friction on, "
                      "negative off)")
    if _is_finite_number(params.get("u_max")) and params["u_max"] <= 0 and params.get("useMaxTorque", True):
        errors.append(f"{where}: params['u_max'] must be > 0 [N*m] (or set useMaxTorque false)")
    if _is_finite_number(params.get("u_min")) and params["u_min"] <= 0 and params.get("useMinTorque", False):
        errors.append(f"{where}: params['u_min'] must be > 0 [N*m] when useMinTorque is true")
    if "rWB_B" in params and not (isinstance(params["rWB_B"], list) and len(params["rWB_B"]) == 3
                                  and all(_is_finite_number(v) for v in params["rWB_B"])):
        errors.append(f"{where}: params['rWB_B'] must be 3 finite numbers [m]")
    return errors


def thruster_param_errors(where: str, params: dict) -> list:
    """What would make ``thrusterFactory.create()`` exit, or build a thruster
    that pushes along a NaN axis, for these params."""
    errors = []
    thruster_type = params.get("thruster_type", "Blank_Thruster")
    if thruster_type not in THRUSTER_TYPES:
        errors.append(f"{where}: params['thruster_type'] {thruster_type!r} must be one of {THRUSTER_TYPES}")
    errors += _factory_param_errors(where, params, _THRUSTER_NUMBER_KWARGS, _THRUSTER_POSITIVE_KWARGS,
                                    _THRUSTER_BOOL_KWARGS)
    if _is_finite_number(params.get("MinOnTime")) and params["MinOnTime"] < 0:
        errors.append(f"{where}: params['MinOnTime'] must be >= 0 [s]")
    for key in ("thrBlowDownCoeff", "ispBlowDownCoeff"):
        if key in params and not (isinstance(params[key], list) and all(_is_finite_number(v) for v in params[key])):
            errors.append(f"{where}: params[{key!r}] must be a list of finite numbers")
    r_B = params.get("r_B")
    if r_B is not None and not (isinstance(r_B, list) and all(_is_finite_number(v) for v in r_B)):
        errors.append(f"{where}: params['r_B'] must be 3 finite numbers [m]")
    tHat_B = params.get("tHat_B")
    if tHat_B is not None and len(tHat_B) == 3 and not _is_direction_vector(tHat_B):
        errors.append(f"{where}: params['tHat_B'] must be a non-zero, finite thrust direction")
    return errors


# "thermal" (sensorThermal.SensorThermal, optionally chained into
# tempMeasurement.TempMeasurement for measurement noise/bias/fault) models
# the temperature of any flat-plate component -- a generic thermal sensor,
# not tied to one specific piece of hardware the way star_tracker/imu/
# coarse_sun_sensor/magnetometer each map to a real physical device. Real
# radiative heating from the sun (gated on the real simulated attitude and,
# when a power/station_keeping/enable_srp spacecraft's own eclipse model is
# shared with it, real eclipse shadowing) plus any configured internal
# power-to-heat dissipation, not an analytical estimate -- see
# engine.fsw.attach_sensors's own "thermal" branch and
# engine.service.SimulationService.build()'s eclipse-sharing comment.
# "reaction_wheel" actuators separately gain an OPTIONAL motor-thermal
# model (motorThermal.MotorThermal, one per wheel) when a wheel's own
# params set the motor_thermal_* group below -- a reaction wheel's spin
# losses/friction generate real heat, independent of whether this
# spacecraft has any "thermal" sensor configured at all.
SUPPORTED_FSW_MODES = ("inertial3D", "hillPoint", "velocityPoint", "sunSafePoint", "locationPointing")
SUPPORTED_ANTENNA_PATTERNS = ("fixed", "cosine", "table")
_MIN_COSINE_GAIN_DBI = 10.0 * math.log10(2.0) - 1e-9  # [dBi] cos^0 over a hemisphere, the least a "cosine" pattern can have

# Phase 3: Monte Carlo dispersion quantities engine.monte_carlo actually
# builds a Basilisk.utilities.MonteCarlo.Dispersions class for, and which
# dispersion "kind" each quantity accepts -- see engine/monte_carlo.py's
# module docstring for exactly which Dispersions class each pairing maps
# to and why (e.g. a Cartesian position/velocity dispersion is deliberately
# NOT offered: Dispersions.UniformVectorCartDispersion/NormalVectorCartDispersion
# replace each component with an ABSOLUTE random value, not a perturbation
# around the nominal orbit, which would silently produce a physically
# nonsensical "dispersed" orbit).
#
# The orbit is dispersed as orbital elements around the spacecraft's own
# initial orbit (Dispersions.OrbitalElementDispersion), never as raw
# Cartesian components; the vector Cartesian classes are used only for the
# initial body rate, as a spread added to the nominal rate.
DISPERSION_QUANTITIES = ("dry_mass_kg", "attitude_sigma_bn", "orbit_elements", "inertia_kg_m2",
                         "angular_rate_bn_b", "drag_coeff", "srp_coeff")
DISPERSION_KINDS_BY_QUANTITY = {
    "dry_mass_kg": ("uniform", "normal"),
    "attitude_sigma_bn": ("uniform_euler_mrp",),
    "orbit_elements": ("normal", "uniform"),
    "inertia_kg_m2": ("normal",),
    "angular_rate_bn_b": ("normal", "uniform"),
    "drag_coeff": ("uniform", "normal"),
    "srp_coeff": ("uniform", "normal"),
}
# DispersionConfig.element_spread keys ("orbit_elements"), each a 1-sigma
# ("normal") or half-width ("uniform") around the nominal element.
ORBIT_ELEMENT_SPREAD_KEYS = ("semi_major_axis_km", "eccentricity", "inclination_deg", "raan_deg",
                             "arg_periapsis_deg", "true_anomaly_deg")
# Quantities whose "normal" kind takes a spread only (no mean): the vector
# and tensor ones, dispersed around their nominal values.
SPREAD_ONLY_DISPERSION_QUANTITIES = ("orbit_elements", "inertia_kg_m2", "angular_rate_bn_b")


class ScenarioValidationError(ValueError):
    """Raised by :meth:`Scenario.validate` (and the dataclass ``__post_init__``
    hooks it calls) with a specific, actionable message -- never a silent
    NaN or a bare ``KeyError``/``TypeError`` from malformed input, per the
    "clear error messages" requirement this project is built around.
    """


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioValidationError(message)


def _is_finite_number(value) -> bool:
    """True for a finite int or float (not a bool)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# Spacecraft, station, sensor and actuator names become file names (CSV, OEM,
# OPM, events, Monte Carlo archives) and the first parts of "<spacecraft>.<field>"
# series names. A name must not be able to leave the output folder or split a
# series name: no path separators or other characters Windows refuses in file
# names, no '.', no control characters, no leading/trailing spaces, and not a
# name Windows reserves for devices (audit H3).
_NAME_FORBIDDEN = set('/\\:*?"<>|.')
# A name and the longest series after it stay far inside a file name's 255
# characters: a 300-character name ran the whole simulation, then failed
# to write ("File name too long", audit R8).
MAX_NAME_CHARS = 64
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def name_error(what: str, name) -> str | None:
    """Why ``name`` cannot name a ``what`` (a spacecraft, ground station,
    sensor or actuator), or None when it can."""
    if not isinstance(name, str) or not name:
        return f"{what} name must not be empty"
    bad = sorted({ch for ch in name if ch in _NAME_FORBIDDEN or ord(ch) < 32 or ord(ch) == 127})
    if bad:
        shown = ", ".join(repr(ch) for ch in bad)
        return (f"{what} name {name!r} contains {shown}: names become file names, so they cannot contain "
                "/ \\ : * ? \" < > | . or control characters")
    if len(name) > MAX_NAME_CHARS:
        return (f"{what} name {name[:20]!r}... is {len(name)} characters: names become file names, "
                f"so at most {MAX_NAME_CHARS}")
    if name != name.strip():
        return f"{what} name {name!r} must not start or end with a space"
    if name.upper() in _WINDOWS_RESERVED:
        return f"{what} name {name!r} is a name Windows reserves for devices; choose another"
    return None


def _is_direction_vector(values) -> bool:
    """True for a 3-element ``[x, y, z]`` of finite numbers that is not the
    zero vector -- what every body-frame axis/direction field here needs.
    A zero or non-finite vector used to pass validation and only fail
    mid-run, once Basilisk normalized it into a NaN attitude/thrust axis.
    """
    try:
        components = [float(v) for v in values]
    except (TypeError, ValueError):
        return False
    return (len(components) == 3 and all(math.isfinite(v) for v in components)
            and math.sqrt(sum(v * v for v in components)) > 1e-12)


@dataclass
class OrbitIC:
    """One spacecraft's orbit initial condition, in exactly one of three
    forms. Only the fields for ``type`` need to be set; the others are
    left ``None`` and ignored -- this keeps the JSON readable (no
    all-fields-always-present clutter) while still being one dataclass, so
    ``engine.service.SimulationService`` has a single type to switch on.
    """

    type: str  # one of ORBIT_IC_TYPES

    # type == "classical_elements" (angles in degrees, matching the rest of
    # this codebase's convention -- see mission_config.py in ../missionAnalysis).
    # Exactly one of true_anomaly_deg/mean_anomaly_deg is used, chosen by
    # anomaly_type -- mean anomaly is the natural input for a mission
    # design spec (e.g. "M0 at epoch"), true anomaly for a specific
    # geometric snapshot; engine.service converts mean -> true via Kepler's
    # equation before calling elem2rv (which only accepts true anomaly).
    semi_major_axis_km: float | None = None
    eccentricity: float | None = None
    inclination_deg: float | None = None
    raan_deg: float | None = None
    arg_periapsis_deg: float | None = None
    anomaly_type: str = "true"  # one of ANOMALY_TYPES
    true_anomaly_deg: float | None = None
    mean_anomaly_deg: float | None = None

    # type == "cartesian" (inertial frame of the scenario's central body)
    position_km: list | None = None  # [x, y, z]
    velocity_km_s: list | None = None  # [vx, vy, vz]

    # type == "tle"
    tle_line1: str | None = None
    tle_line2: str | None = None

    def validate(self) -> None:
        _require(self.type in ORBIT_IC_TYPES,
                  f"orbit.type {self.type!r} must be one of {ORBIT_IC_TYPES}")
        if self.type == "classical_elements":
            # NaN and Infinity pass the comparisons below unnoticed (NaN) or
            # look valid (Infinity), and Basilisk then misbehaves (audit M16).
            for name in ("semi_major_axis_km", "eccentricity", "inclination_deg", "raan_deg", "arg_periapsis_deg",
                         "true_anomaly_deg", "mean_anomaly_deg"):
                value = getattr(self, name)
                _require(value is None or _is_finite_number(value),
                          f"classical_elements orbit: {name} must be a finite number, got {value!r}")
            _require(self.semi_major_axis_km is not None and self.semi_major_axis_km > 0,
                      "classical_elements orbit needs semi_major_axis_km > 0")
            _require(self.eccentricity is not None and 0.0 <= self.eccentricity < 1.0,
                      "classical_elements orbit needs 0 <= eccentricity < 1 (elliptical only)")
            for name in ("inclination_deg", "raan_deg", "arg_periapsis_deg"):
                _require(getattr(self, name) is not None, f"classical_elements orbit needs {name}")
            _require(self.anomaly_type in ANOMALY_TYPES,
                      f"orbit.anomaly_type {self.anomaly_type!r} must be one of {ANOMALY_TYPES}")
            anomaly_field = "true_anomaly_deg" if self.anomaly_type == "true" else "mean_anomaly_deg"
            _require(getattr(self, anomaly_field) is not None,
                      f"classical_elements orbit with anomaly_type={self.anomaly_type!r} needs {anomaly_field}")
        elif self.type == "cartesian":
            for name in ("position_km", "velocity_km_s"):
                value = getattr(self, name)
                _require(value is not None and len(value) == 3,
                          f"cartesian orbit needs {name} as a 3-element [x, y, z] list")
                _require(all(_is_finite_number(v) for v in value),
                          f"cartesian orbit: {name} must hold finite numbers, got {value!r}")
            _require(any(v != 0.0 for v in self.position_km), "cartesian orbit: position_km must not be [0, 0, 0]")
        elif self.type == "tle":
            _require(bool(self.tle_line1) and bool(self.tle_line2),
                      "tle orbit needs both tle_line1 and tle_line2")
            # The line format is checked here, not first by SGP4 at run
            # time (audit M16).
            try:
                check_lines(self.tle_line1, self.tle_line2)
            except TLEError as exc:
                raise ScenarioValidationError(f"tle orbit: {exc}") from None


@dataclass
class SensorConfig:
    """One sensor instance. ``kind`` is one of :data:`SUPPORTED_SENSOR_KINDS`
    (see the capability matrix for which Basilisk module each one maps to:
    ``starTracker``, ``imuSensor``, ``coarseSunSensor``, ``magnetometer``,
    ``sensorThermal`` -- see :data:`SUPPORTED_SENSOR_KINDS`'s own comment
    for ``"thermal"``'s extra ``tempMeasurement`` measurement-noise layer).
    ``params`` is an open dict of module-specific settings (noise std devs,
    mounting direction, ...) -- kept generic here rather than one dataclass
    per sensor type so new sensor kinds can be added without another schema
    migration; :meth:`SpacecraftConfig.validate` checks the kind-specific
    params it can check early (e.g. ``coarse_sun_sensor`` needs ``nHat_B``).

    ``simpleNav`` (the truth-to-navigation-message bridge every FSW mode
    needs) is deliberately NOT a selectable sensor kind here: engine.service
    creates exactly one automatically for any spacecraft with ``fsw_mode``
    set, since every FSW guidance mode needs it and it is not itself a
    piece of hardware the user configures.
    """

    kind: str
    name: str
    params: dict = field(default_factory=dict)


@dataclass
class ActuatorConfig:
    """One actuator instance. ``kind`` is one of
    :data:`SUPPORTED_ACTUATOR_KINDS`. See :class:`SensorConfig` for why
    ``params`` is an open dict, and the module-level note above
    :data:`SUPPORTED_ACTUATOR_KINDS` for why ``"thruster"``/
    ``"magnetic_torque_rod"`` are accepted here but rejected by
    engine.service at run time.
    """

    kind: str
    name: str
    params: dict = field(default_factory=dict)


@dataclass
class PowerConfig:
    """A spacecraft's power budget: a body-fixed solar panel, a constant
    "bus" housekeeping load, and a battery -- Basilisk's real
    ``simpleSolarPanel``/``simplePowerSink``/``simpleBattery`` modules
    (see ``engine.service``, ported from the same wiring pattern
    ``../missionAnalysis/power_budget.py`` already uses), not an
    analytical estimate: generated power depends on the scenario's actual
    simulated attitude (panel-normal-to-sun angle) and eclipse state, so
    this needs a spacecraft's orbit to actually pass through sunlight and
    shadow -- there is no separate "power budget mode" to turn on beyond
    setting this field. ``None`` (the default) means no power budget is
    simulated for that spacecraft at all, matching every scenario written
    before this field existed.
    """

    panel_area_m2: float  # [m^2] total deployed solar panel area
    panel_efficiency: float  # [-] fraction of incident solar power converted to electrical power, 0 < x <= 1
    panel_normal_b: list = field(default_factory=lambda: [0.0, 0.0, 1.0])  # body-frame unit vector
    bus_idle_power_w: float = 0.0  # [W] constant always-on avionics/thermal/ADCS housekeeping load
    battery_capacity_wh: float = 100.0  # [W*hr]
    battery_initial_soc: float = 1.0  # [-] initial state of charge, fraction of capacity, 0 <= x <= 1

    def validate(self, spacecraft_name: str) -> None:
        # Design-philosophy audit finding (docs/ux_audit.md, "units
        # enforced only by naming convention"): a plain, generous
        # upper-bound plausibility check -- 2000 m^2 is already far
        # larger than any real single spacecraft's solar array (ISS's
        # own combined 8 arrays total ~2500 m^2, and this field is ONE
        # spacecraft here) -- catches the likely magnitude typo (a
        # units mixup, e.g. cm^2 typed where m^2 was meant) without
        # rejecting anything physically real. Not a type-level unit
        # system (see that finding's own "decision needed" in
        # docs/ux_roadmap.md) -- just a sanity floor/ceiling, same
        # spirit as panel_efficiency's existing (0, 1] check just below.
        _require(0.0 < self.panel_area_m2 <= 2000.0,
                  f"{spacecraft_name}: power.panel_area_m2 must be in (0, 2000] m^2 -- if your intended "
                  "value is outside this range, check for a units mixup (e.g. cm^2 instead of m^2)")
        _require(0.0 < self.panel_efficiency <= 1.0,
                  f"{spacecraft_name}: power.panel_efficiency must be in (0, 1]")
        _require(_is_direction_vector(self.panel_normal_b),
                  f"{spacecraft_name}: power.panel_normal_b must be a non-zero, finite 3-element [x, y, z] list")
        _require(self.bus_idle_power_w >= 0, f"{spacecraft_name}: power.bus_idle_power_w must be >= 0")
        _require(0.0 < self.battery_capacity_wh <= 1.0e6,
                  f"{spacecraft_name}: power.battery_capacity_wh must be in (0, 1e6] W*hr -- if your "
                  "intended value is outside this range, check for a units mixup (e.g. Wh entered as J)")
        _require(0.0 <= self.battery_initial_soc <= 1.0,
                  f"{spacecraft_name}: power.battery_initial_soc must be in [0, 1]")


@dataclass
class RFLinkConfig:
    """A spacecraft's downlink transmitter, for a reported link-margin
    ESTIMATE only (``engine.link_budget``) -- a simplified free-space-path
    -loss Eb/N0 budget (no atmosphere/rain/pointing-loss/coding-gain
    terms), ported directly from ``../missionAnalysis``'s
    ``run_constellation_mission.py::_rf_link_margin_db()``. It is evaluated
    against the real simulated slant range from ``engine.service``'s
    ground-station access analysis, but it does NOT feed back into the
    simulated physics anywhere (no data-rate/duty-cycle simulation) --
    see :class:`PowerConfig` for what IS actually simulated. ``None`` (the
    default) means no link margin is computed for that spacecraft.
    """

    tx_power_w: float  # [W] downlink transmitter RF output power
    frequency_hz: float  # [Hz] downlink carrier frequency
    data_rate_bps: float  # [bit/s] downlink data rate
    tx_antenna_gain_dbi: float = 0.0  # [dBi] spacecraft downlink antenna gain
    implementation_loss_db: float = 2.0  # [dB] combined pointing/polarization/implementation loss
    required_ebno_db: float = 6.0  # [dB] required Eb/N0 for the assumed modulation/coding
    # [deg] half-power beamwidth of the spacecraft's downlink antenna pattern.
    # None (the default) keeps every existing scenario's exact prior behavior
    # (no pointing-loss term at all -- same as before this field existed).
    # Set together with CommsPointingConfig to make the link margin respond
    # to the spacecraft's own actual achieved antenna pointing error (see
    # engine.link_budget's module docstring for the parabolic-pattern
    # approximation this applies: L_point_dB = 12*(pointing_error_deg /
    # antenna_beamwidth_deg)^2, the standard textbook falloff for a
    # Gaussian/parabolic-reflector main lobe).
    antenna_beamwidth_deg: float | None = None
    # How the spacecraft antenna's gain falls off away from boresight, used
    # wherever the downlink is evaluated live (engine.data_handling's link
    # gate: a DataHandlingConfig, or any pattern other than "fixed"):
    #   "fixed"  -- tx_antenna_gain_dbi in every direction (minus the
    #               antenna_beamwidth_deg pointing loss above, if set);
    #   "cosine" -- a patch antenna: gain G0*cos^n(theta) in front of the
    #               ground plane, n from the peak gain (engine.link_budget.
    #               cosine_exponent), antenna_front_to_back_db below the
    #               peak behind it;
    #   "table"  -- antenna_gain_table, read off the antenna's datasheet.
    antenna_pattern: str = "fixed"
    # [off-boresight angle deg, gain dBi] pairs, angles rising from 0;
    # linear in dB between them, the last gain beyond the last angle.
    antenna_gain_table: list = field(default_factory=list)
    antenna_front_to_back_db: float = 15.0  # [dB] "cosine" only: gain behind the ground plane, below the peak
    # Body-frame boresight of the downlink antenna. None falls back to
    # comms_pointing.antenna_boresight_b; "cosine" and "table" need one of
    # the two, since the gain then depends on the real attitude.
    antenna_boresight_b: list | None = None

    def validate(self, spacecraft_name: str) -> None:
        # Generous plausibility ceiling (docs/ux_audit.md, "units
        # enforced only by naming convention") -- 10 kW is already far
        # above any real spacecraft downlink transmitter (typically well
        # under 100 W); catches a likely magnitude typo without
        # rejecting anything physically real.
        _require(0.0 < self.tx_power_w <= 1.0e4,
                  f"{spacecraft_name}: rf_link.tx_power_w must be in (0, 1e4] W -- if your intended value "
                  "is outside this range, check for a units mixup (e.g. mW instead of W)")
        _require(self.frequency_hz > 0, f"{spacecraft_name}: rf_link.frequency_hz must be > 0")
        _require(self.data_rate_bps > 0, f"{spacecraft_name}: rf_link.data_rate_bps must be > 0")
        _require(self.implementation_loss_db >= 0,
                  f"{spacecraft_name}: rf_link.implementation_loss_db must be >= 0")
        _require(self.antenna_beamwidth_deg is None or self.antenna_beamwidth_deg > 0,
                  f"{spacecraft_name}: rf_link.antenna_beamwidth_deg must be None or > 0")
        _require(self.antenna_pattern in SUPPORTED_ANTENNA_PATTERNS,
                  f"{spacecraft_name}: rf_link.antenna_pattern must be one of {SUPPORTED_ANTENNA_PATTERNS}")
        if self.antenna_pattern == "cosine":
            # cos^n over the forward hemisphere has directivity 2(n + 1):
            # n >= 0 needs a peak gain of at least 2 (3.01 dBi).
            _require(self.tx_antenna_gain_dbi >= _MIN_COSINE_GAIN_DBI,
                      f"{spacecraft_name}: rf_link.tx_antenna_gain_dbi must be >= 3.01 dBi for a \"cosine\" "
                      "(patch) pattern -- a lower peak gain is not a patch; use \"fixed\" or a gain table")
            _require(_is_finite_number(self.antenna_front_to_back_db) and self.antenna_front_to_back_db >= 0,
                      f"{spacecraft_name}: rf_link.antenna_front_to_back_db must be >= 0")
        if self.antenna_pattern == "table":
            table = self.antenna_gain_table
            _require(isinstance(table, list) and len(table) >= 2
                      and all(isinstance(row, (list, tuple)) and len(row) == 2
                              and all(_is_finite_number(v) for v in row) for row in table),
                      f"{spacecraft_name}: rf_link.antenna_gain_table needs at least two "
                      "[off-boresight angle deg, gain dBi] pairs")
            angles = [row[0] for row in table]
            _require(angles[0] == 0 and all(b > a for a, b in zip(angles, angles[1:])) and angles[-1] <= 180,
                      f"{spacecraft_name}: rf_link.antenna_gain_table angles must start at 0 deg and rise "
                      "to at most 180 deg")
        _require(self.antenna_boresight_b is None or _is_direction_vector(self.antenna_boresight_b),
                  f"{spacecraft_name}: rf_link.antenna_boresight_b must be None or a non-zero, finite "
                  "3-element [x, y, z] list")


@dataclass
class CommsPointingConfig:
    """Automatic, geometry-driven attitude mode switching between Sun
    -pointing (the spacecraft's normal operating state) and ground
    -station antenna pointing (whenever this spacecraft is in real,
    simulated access to ``target_ground_station``) --
    ``engine.fsw.build_comms_pointing``'s mode arbitrator.

    When set, this field OWNS the spacecraft's attitude control --
    ``fsw_mode`` must be left ``None`` (``Scenario.validate()`` enforces
    this), since there is no single static guidance mode to combine it
    with. Internally this builds BOTH a ``sunSafePoint`` chain (tracking
    the real, live sun ephemeris, same as setting ``fsw_mode:
    "sunSafePoint"`` directly would) and a ``locationPointing`` chain
    targeting ``target_ground_station`` (same as ``fsw_mode:
    "locationPointing"`` with ``fsw_params['target_ground_station']``
    would), then switches which one feeds the shared ``mrpFeedback``
    control loop based on the REAL ``groundLocation.GroundLocation``
    access state for that station -- never a fixed/manually-specified
    time window. Only the attitude REFERENCE switches; the spacecraft's
    own integrated attitude state is untouched by the switch itself, so
    the existing closed-loop controller physically slews from one
    target to the other across the transition, exactly like commanding
    any other new reference -- there is no instantaneous attitude jump.

    ``comms_power_w`` (if set) draws that much additional electrical
    power -- via its own ``simplePowerSink``, on top of whatever
    ``PowerConfig.bus_idle_power_w`` already draws -- for exactly as
    long as the ground-station-pointing mode is actually active, a
    stand-in for a downlink transmitter's own power draw. Requires
    ``SpacecraftConfig.power`` to also be set (nothing to draw from
    otherwise); leave ``comms_power_w`` at its default ``0.0`` to model
    the attitude-switching behavior alone with no extra power draw.
    """

    target_ground_station: str
    antenna_boresight_b: list = field(default_factory=lambda: [0.0, 0.0, 1.0])  # body-frame unit vector
    # None (the default) falls back to PowerConfig.panel_normal_b (the
    # solar panel's own normal is the natural Sun-pointing axis whenever
    # a power budget is also configured); with no power budget, falls
    # back to [0, 0, 1]. Set explicitly to point a DIFFERENT body axis
    # at the sun than the panel normal.
    sun_pointing_axis_b: list | None = None
    comms_power_w: float = 0.0  # [W] additional transmitter draw while ground-station-pointing is active

    def validate(self, spacecraft_name: str) -> None:
        _require(bool(self.target_ground_station),
                  f"{spacecraft_name}: comms_pointing.target_ground_station must not be empty")
        _require(_is_direction_vector(self.antenna_boresight_b),
                  f"{spacecraft_name}: comms_pointing.antenna_boresight_b must be a non-zero, finite 3-element "
                  "[x, y, z] list")
        _require(self.sun_pointing_axis_b is None or _is_direction_vector(self.sun_pointing_axis_b),
                  f"{spacecraft_name}: comms_pointing.sun_pointing_axis_b must be None or a non-zero, finite "
                  "3-element [x, y, z] list")
        _require(self.comms_power_w >= 0, f"{spacecraft_name}: comms_pointing.comms_power_w must be >= 0")


MAX_DATA_NAME_CHARS = 127  # Basilisk's DataNodeUsageMsgPayload.dataName is char[128]


@dataclass
class InstrumentConfig:
    """One source of onboard data -- a payload instrument, or the
    platform's housekeeping telemetry -- as Basilisk's
    ``simpleInstrument``: a constant data rate, so give the instrument's
    orbit-average rate if it does not run all the time."""

    name: str
    data_rate_bps: float  # [bit/s]
    power_w: float = 0.0  # [W] constant electrical draw; needs SpacecraftConfig.power when > 0
    initial_data_gbit: float = 0.0  # [Gbit] already in the instrument's memory partition at the start

    def validate(self, spacecraft_name: str) -> None:
        label = f"{spacecraft_name}: data_handling instrument {self.name!r}"
        _require(bool(self.name) and len(self.name) <= MAX_DATA_NAME_CHARS,
                  f"{spacecraft_name}: every data_handling instrument needs a name of 1 to "
                  f"{MAX_DATA_NAME_CHARS} characters")
        _require(_is_finite_number(self.data_rate_bps) and 0.0 < self.data_rate_bps <= 1.0e11,
                  f"{label}: data_rate_bps must be in (0, 1e11] bit/s")
        _require(_is_finite_number(self.power_w) and self.power_w >= 0, f"{label}: power_w must be >= 0")
        _require(_is_finite_number(self.initial_data_gbit) and self.initial_data_gbit >= 0,
                  f"{label}: initial_data_gbit must be >= 0")


@dataclass
class DataHandlingConfig:
    """Onboard data generation, storage and downlink (``engine.data_handling``),
    built from Basilisk's ``simpleInstrument``, ``partitionedStorageUnit``
    (one partition per instrument) and ``spaceToGroundTransmitter``.

    Data a full memory cannot take is lost. With ``SpacecraftConfig.rf_link``
    set, the transmitter downlinks at ``rf_link.data_rate_bps`` to any
    ground station whose link closes: in access, and with a non-negative
    Eb/N0 margin for the real slant range and the antenna's gain toward the
    station (``rf_link.antenna_pattern``). Without ``rf_link`` nothing is
    downlinked and the memory only fills.
    """

    storage_capacity_gbit: float  # [Gbit] 8 Gbit = 1 GB
    instruments: list = field(default_factory=list)  # InstrumentConfig
    transmitter_power_w: float = 0.0  # [W] DC draw while transmitting; needs SpacecraftConfig.power when > 0

    def validate(self, spacecraft_name: str) -> None:
        _require(_is_finite_number(self.storage_capacity_gbit) and 0.0 < self.storage_capacity_gbit <= 1.0e6,
                  f"{spacecraft_name}: data_handling.storage_capacity_gbit must be in (0, 1e6] Gbit")
        _require(len(self.instruments) > 0,
                  f"{spacecraft_name}: data_handling needs at least one instrument (housekeeping counts)")
        for instrument in self.instruments:
            instrument.validate(spacecraft_name)
        names = [instrument.name for instrument in self.instruments]
        _require(len(set(names)) == len(names), f"{spacecraft_name}: data_handling instrument names must be unique")
        initial = sum(instrument.initial_data_gbit for instrument in self.instruments)
        _require(initial <= self.storage_capacity_gbit,
                  f"{spacecraft_name}: data_handling instruments start with {initial:g} Gbit, more than the "
                  f"{self.storage_capacity_gbit:g} Gbit storage capacity")
        _require(_is_finite_number(self.transmitter_power_w) and self.transmitter_power_w >= 0,
                  f"{spacecraft_name}: data_handling.transmitter_power_w must be >= 0")

    @property
    def needs_power(self) -> bool:
        return self.transmitter_power_w > 0 or any(i.power_w > 0 for i in self.instruments)


@dataclass
class SolarArrayConfig:
    """A deployed solar array that flexes: a rigid flat panel on a
    torsional spring-damper hinge at its root (Basilisk's
    ``hingedRigidBodyStateEffector``, the Allard, Schaub and Piggott hinged
    panel model of a structure's first flexing mode). Its mass and inertia
    move with it and act on the hub, so slews and torques excite it and
    its oscillation shows in the hub's attitude.

    The hinge stiffness and damping come from ``first_mode_hz`` and
    ``damping_ratio``: the array's first bending frequency with the hub
    held fixed (cantilevered), as a structural analysis or test gives it.
    Free in orbit, the hub swings with the array, so the coupled frequency
    the run shows is somewhat higher.

    ``mass_kg`` is part of ``SpacecraftConfig.dry_mass_kg`` (the hub gets
    the rest); ``SpacecraftConfig.inertia_kg_m2`` is the hub's own, without
    the arrays. With ``generates_power`` and a power budget, the array is
    a solar panel of ``span_m * width_m`` facing ``normal_b``, following its
    own flexed orientation.
    """

    name: str
    mass_kg: float  # [kg]
    span_m: float  # [m] hinge to tip
    width_m: float  # [m] along the hinge
    hinge_position_b: list  # [m] body frame
    deploy_direction_b: list  # body-frame direction from the hinge to the tip
    normal_b: list  # body-frame normal of the cell side, perpendicular to deploy_direction_b
    first_mode_hz: float  # [Hz] first bending frequency, hub held fixed
    damping_ratio: float  # [-] of that mode
    initial_deflection_deg: float = 0.0  # [deg] about the hinge, positive toward normal_b
    initial_rate_deg_s: float = 0.0  # [deg/s]
    generates_power: bool = True

    def validate(self, spacecraft_name: str) -> None:
        label = f"{spacecraft_name}: solar array {self.name!r}"
        _require(bool(self.name), f"{spacecraft_name}: every solar array needs a name")
        for key in ("mass_kg", "span_m", "width_m", "first_mode_hz"):
            value = getattr(self, key)
            _require(_is_finite_number(value) and value > 0, f"{label}: {key} must be > 0")
        _require(self.span_m <= 100.0 and self.width_m <= 100.0,
                  f"{label}: span_m and width_m must be at most 100 m -- check for a units mixup")
        _require(self.first_mode_hz <= 100.0, f"{label}: first_mode_hz must be at most 100 Hz")
        _require(_is_finite_number(self.damping_ratio) and 0.0 <= self.damping_ratio < 1.0,
                  f"{label}: damping_ratio must be in [0, 1)")
        for key in ("hinge_position_b",):
            vector = getattr(self, key)
            _require(isinstance(vector, list) and len(vector) == 3 and all(_is_finite_number(v) for v in vector),
                      f"{label}: {key} must be a finite 3-element [x, y, z] list")
        for key in ("deploy_direction_b", "normal_b"):
            _require(_is_direction_vector(getattr(self, key)),
                      f"{label}: {key} must be a non-zero, finite 3-element [x, y, z] list")
        e = [v / math.sqrt(sum(c * c for c in self.deploy_direction_b)) for v in self.deploy_direction_b]
        n = [v / math.sqrt(sum(c * c for c in self.normal_b)) for v in self.normal_b]
        _require(abs(sum(a * b for a, b in zip(e, n))) < 1e-3,
                  f"{label}: normal_b must be perpendicular to deploy_direction_b (the hinge runs along both "
                  "faces' common edge)")
        for key in ("initial_deflection_deg", "initial_rate_deg_s"):
            _require(_is_finite_number(getattr(self, key)), f"{label}: {key} must be a finite number")
        _require(abs(self.initial_deflection_deg) < 90.0, f"{label}: initial_deflection_deg must be within 90 deg")


@dataclass
class StationKeepingConfig:
    """Automated altitude/semi-major-axis station-keeping for one
    spacecraft, with delta-V and propellant bookkeeping
    (``engine.orbit_maintenance``, ported from
    ``../missionAnalysis``'s ``AltitudeKeepingController``): fires a
    continuous low-thrust reboost burn (prograde, along the inertial
    velocity direction) whenever a smoothed altitude estimate decays past
    ``deadband_km`` below ``target_altitude_km``, holding the burn until
    altitude is restored -- simple deadband/hysteresis control, gated off
    during eclipse (approximates a solar-electric bus that can't run the
    thruster off battery alone) and inhibited once propellant is
    depleted. Propellant use is tracked via the rocket equation and fed
    back into the spacecraft's simulated mass every tick, so thrust-to
    -mass stays physically consistent as propellant burns off -- see
    ``SpacecraftConfig.dry_mass_kg``'s docstring for how that interacts
    with ``propellant_kg`` below.

    This assumes something is actually decaying the orbit -- with only
    point-mass gravity (this schema's default), altitude never decays and
    the burn simply never fires. Enable atmospheric drag
    (``SpacecraftConfig.enable_drag``) for this to have any effect.
    ``None`` (the default) means no station-keeping is simulated for that
    spacecraft.
    """

    target_altitude_km: float  # [km] altitude above the central body's equatorial radius to maintain
    deadband_km: float  # [km] how far below target_altitude_km before a reboost burn starts
    thrust_n: float  # [N] reboost thruster thrust
    isp_s: float  # [s] reboost thruster specific impulse
    propellant_kg: float  # [kg] initial propellant mass available for station-keeping
    eclipse_sunlit_threshold: float = 0.99  # [-] shadow factor above which the spacecraft is treated as sunlit
    # Thruster hardware/firing realism, shared by a co-located
    # phasing_keeping (one physical thruster) -- see
    # engine.orbit_maintenance.ThrusterOnTimeModel. 0.0 = an ideal thruster
    # that can fire for arbitrarily short times.
    min_on_time_s: float = 0.0  # [s] minimum firing duration (minimum impulse bit = thrust_n * min_on_time_s)
    # Gate firings so a multi-orbit, eclipse-interrupted burn doesn't
    # accumulate an eccentricity change (it waits for the balancing side
    # of the orbit instead).
    eccentricity_neutral_burns: bool = False

    def validate(self, spacecraft_name: str) -> None:
        _require(self.target_altitude_km > 0, f"{spacecraft_name}: station_keeping.target_altitude_km must be > 0")
        _require(math.isfinite(self.min_on_time_s) and 0.0 <= self.min_on_time_s <= 86400.0,
                  f"{spacecraft_name}: station_keeping.min_on_time_s must be in [0, 86400] s")
        _require(isinstance(self.eccentricity_neutral_burns, bool),
                  f"{spacecraft_name}: station_keeping.eccentricity_neutral_burns must be true or false")
        _require(0.0 < self.deadband_km < self.target_altitude_km,
                  f"{spacecraft_name}: station_keeping.deadband_km must be > 0 and < target_altitude_km")
        _require(self.thrust_n > 0, f"{spacecraft_name}: station_keeping.thrust_n must be > 0")
        _require(self.isp_s > 0, f"{spacecraft_name}: station_keeping.isp_s must be > 0")
        _require(self.propellant_kg >= 0, f"{spacecraft_name}: station_keeping.propellant_kg must be >= 0")
        _require(0.0 < self.eclipse_sunlit_threshold <= 1.0,
                  f"{spacecraft_name}: station_keeping.eclipse_sunlit_threshold must be in (0, 1]")


@dataclass
class GeoStationKeepingConfig:
    """GEO station-keeping (``engine.geo_station_keeping``): east-west
    control holds the longitude within ``longitude_deadband_deg`` of
    ``target_longitude_deg``, north-south control keeps the inclination
    below ``inclination_max_deg``. Both measured in Earth's own rotating
    frame. Earth only (it uses Earth's J22 term to plan east-west burns).
    """

    target_longitude_deg: float  # [deg] east longitude of the slot
    thrust_n: float  # [N]
    isp_s: float  # [s]
    propellant_kg: float  # [kg] initial propellant, on top of dry_mass_kg
    longitude_deadband_deg: float = 0.05  # [deg] half-width of the longitude box
    inclination_max_deg: float = 0.05  # [deg]

    def validate(self, spacecraft_name: str) -> None:
        where = f"{spacecraft_name}: geo_station_keeping"
        _require(-180.0 <= self.target_longitude_deg <= 360.0,
                  f"{where}.target_longitude_deg must be in [-180, 360] deg")
        _require(0.0 < self.longitude_deadband_deg <= 5.0, f"{where}.longitude_deadband_deg must be in (0, 5] deg")
        _require(0.0 < self.inclination_max_deg <= 10.0, f"{where}.inclination_max_deg must be in (0, 10] deg")
        _require(self.thrust_n > 0, f"{where}.thrust_n must be > 0")
        _require(self.isp_s > 0, f"{where}.isp_s must be > 0")
        _require(self.propellant_kg >= 0, f"{where}.propellant_kg must be >= 0")


SUPPORTED_THRUST_FRAMES = ("VNB", "RTN")


@dataclass
class ConstantThrustConfig:
    """Continuous (always-on), constant-magnitude thrust with a fixed
    DIRECTION IN A ROTATING FRAME (``frame``: ``"VNB"`` -- velocity/orbit
    -normal/binormal -- or ``"RTN"`` -- radial/transverse/orbit-normal;
    see ``engine.orbit_maintenance``'s ``_vnb_basis``/``_rtn_basis`` for
    the exact axis definitions), with delta-V and propellant bookkeeping
    (same rocket-equation approach as ``StationKeepingConfig`` -- see that
    class's docstring). Built for
    :data:`Scenario.simulation_mode`\\ 's ``"orbit_only"`` use case: a
    delta-V/propellant budget for a maneuver whose direction is defined
    relative to the orbit (e.g. always-prograde, or a fixed out-of-plane
    component) rather than needing any attitude model to point a specific
    body axis -- an INERTIALLY-fixed thrust direction would drift
    relative to the orbit as the spacecraft moves, which is why this is
    VNB/RTN-relative, re-evaluated every simulation tick from the
    spacecraft's current state, not a fixed inertial vector.

    Independent of ``StationKeepingConfig`` -- both may be set on the same
    spacecraft (separate propellant budgets/tanks, unlike
    ``StationKeepingConfig``/``PhasingKeepingConfig``'s deliberately
    shared one -- see ``PhasingKeepingConfig``'s docstring for that case)
    and not restricted to orbit-only mode; a full-attitude scenario can
    use this too if a simple always-on maneuver (rather than an
    altitude-deadband-triggered one) is what's wanted.

    ``None`` (the default) means no constant-frame thrust is simulated for
    that spacecraft.
    """

    frame: str = "VNB"  # one of SUPPORTED_THRUST_FRAMES
    direction: list = field(default_factory=lambda: [1.0, 0.0, 0.0])  # unit vector in `frame` [-]
    thrust_n: float = 0.01  # [N]
    isp_s: float = 1500.0  # [s]
    propellant_kg: float = 2.0  # [kg] initial propellant mass available

    def validate(self, spacecraft_name: str) -> None:
        _require(self.frame in SUPPORTED_THRUST_FRAMES,
                  f"{spacecraft_name}: constant_thrust.frame {self.frame!r} must be one of "
                  f"{SUPPORTED_THRUST_FRAMES}")
        _require(_is_direction_vector(self.direction),
                  f"{spacecraft_name}: constant_thrust.direction must be a non-zero, finite 3-element vector")
        _require(self.thrust_n > 0, f"{spacecraft_name}: constant_thrust.thrust_n must be > 0")
        _require(self.isp_s > 0, f"{spacecraft_name}: constant_thrust.isp_s must be > 0")
        _require(self.propellant_kg >= 0, f"{spacecraft_name}: constant_thrust.propellant_kg must be >= 0")


# PhasingKeepingConfig.control_law values: the drift-orbit controller
# (engine.orbit_maintenance) or one of Basilisk's formationFlying laws
# (engine.formation_control).
PHASING_CONTROL_LAWS = ("drift_orbit", "mean_oe", "hill_pd")


@dataclass
class PhasingKeepingConfig:
    """Constellation-wide phasing maintenance: holds this (follower)
    spacecraft's along-track separation from a ``chief_spacecraft`` at a
    target value via a drift-orbit maneuver (a temporary semi-major-axis
    offset, natural drift, then a restoring burn) --
    ``engine.orbit_maintenance.PhasingKeepingController``, ported from
    ``../missionAnalysis``'s controller of the same name. Built for
    exactly the constellations ``engine.constellation`` generates (a set
    of co-planar, same-altitude satellites), but works for any two
    spacecraft sharing an orbital plane and altitude.

    Requires ``station_keeping`` to ALSO be set on this same spacecraft:
    phasing and altitude-keeping share ONE physical thruster and
    propellant tank (this config deliberately has no
    ``thrust_n``/``isp_s``/``propellant_kg`` fields of its own --
    ``engine.service`` reads those from ``station_keeping`` instead, so
    there is no way for the two to accidentally disagree about the same
    hardware), with altitude-keeping taking priority whenever both want to
    fire on the same tick -- see the controller's own docstring for why.

    On a phasing follower, that ``station_keeping`` block holds altitude
    RELATIVE TO THE CHIEF, not to its own ``target_altitude_km``: it
    mirrors the chief's reboosts, and its ``deadband_km`` is how far below
    the chief's (smoothed) altitude it may fall before a safety reboost.
    Reboosting the two spacecraft independently was a real bug: one lone
    reboost leaves a km-scale semi-major-axis mismatch, which drifts the
    formation apart by degrees per day (see
    ``engine.orbit_maintenance.StationKeepingController``'s
    "Formation-follower mode" docstring). Give the chief its own
    ``station_keeping`` to hold the formation's altitude.

    ``target_separation_km`` is one or more along-track distances [km]
    ahead of the chief; with more than one entry, the target steps through
    them every ``reconfiguration_interval_days`` (holding at the last one
    once the list is exhausted) -- e.g. ``[1000, 500, 100]`` with
    ``reconfiguration_interval_days=90`` tightens the formation baseline
    roughly every 3 months. A single entry holds that separation for the
    whole mission. The remaining fields are maneuver-tuning knobs with
    reasonable ported defaults (``../missionAnalysis/mission_config.py``)
    -- widen ``tolerance_fraction``/``restore_tolerance_fraction`` for
    fewer, larger corrections, or narrow them for tighter formation
    -keeping at the cost of more frequent burns; there is no single
    "correct" answer, it depends on the mission's own ops concept.

    Caveat found by a real crash investigation: give this spacecraft's
    (and its ``chief_spacecraft``'s) orbit a small, deliberate, NONZERO
    ``eccentricity`` (e.g. ``0.001``) rather than exactly ``0.0``.
    ``engine.orbit_maintenance.PhasingKeepingController`` measures each
    spacecraft's along-track phase via ``orbitalMotion.rv2elem()``, which
    only trusts its stable near-circular formula below ``e < 1e-11`` --
    a genuinely circular scenario's real, propagated eccentricity (from
    third-body gravity, or this very controller's own commanded thrust)
    can easily drift just above that extremely tight threshold, at which
    point ``rv2elem()`` silently falls back to a formula that is
    numerically meaningless that close to zero eccentricity, feeding a
    garbage phasing error into this controller. See
    ``SpaceMissionStudio/HISTORY.md``'s "Template '05' crash" writeups for the
    full investigation (bundled template ``05_formation_flying_phasing``
    hit exactly this and was fixed the same way).
    """

    chief_spacecraft: str
    target_separation_km: list  # [km] one or more along-track distances ahead of the chief
    reconfiguration_interval_days: float = 90.0  # [day] only matters if target_separation_km has >1 entry
    tolerance_fraction: float = 0.10  # [-] trigger threshold, as a fraction of the current target separation
    restore_tolerance_fraction: float = 0.02  # [-] "close enough, stop drifting" threshold, same units
    # 3 days: a 50 km repositioning at ~550 km LEO costs ~0.13 m/s; the
    # delta-V of a correction scales roughly as 1 / window (21 days, the
    # old default, took three weeks to close any error).
    correction_window_days: float = 3.0  # [day] target time to null a fresh phasing error
    max_drift_days: float = 90.0  # [day] safety cap on the drift coast phase
    max_delta_semi_major_axis_km: float = 3.0  # [km] safety clamp on the drift-orbit SMA offset
    # Which flight-software law holds the separation (PHASING_CONTROL_LAWS;
    # engine.formation_control). "drift_orbit" is the controller described
    # above; "mean_oe" and "hill_pd" run Basilisk's own formationFlying
    # modules (meanOEFeedback, hillFrameRelativeControl) unmodified, their
    # force limited to this spacecraft's station_keeping thruster. The
    # tolerance, window and drift fields above apply to "drift_orbit" only.
    control_law: str = "drift_orbit"  # one of PHASING_CONTROL_LAWS: drift_orbit, mean_oe, hill_pd
    # meanOEFeedback outputs a force, so its K is this per-kilogram gain
    # times the follower's mass at the start of the run.
    mean_oe_gain: float = 2500.0  # [m^2/s^3] "mean_oe": diagonal of K per kg of spacecraft
    hill_position_gain: float = 2.0e-6  # [1/s^2] "hill_pd": diagonal of K
    hill_velocity_gain: float = 2.0e-3  # [1/s] "hill_pd": diagonal of P

    def validate(self, spacecraft_name: str) -> None:
        _require(bool(self.chief_spacecraft),
                  f"{spacecraft_name}: phasing_keeping.chief_spacecraft must not be empty")
        _require(self.chief_spacecraft != spacecraft_name,
                  f"{spacecraft_name}: phasing_keeping.chief_spacecraft cannot be the spacecraft itself")
        _require(len(self.target_separation_km) >= 1,
                  f"{spacecraft_name}: phasing_keeping.target_separation_km needs at least one entry")
        _require(all(d > 0 for d in self.target_separation_km),
                  f"{spacecraft_name}: phasing_keeping.target_separation_km entries must all be > 0")
        _require(self.reconfiguration_interval_days >= 0,
                  f"{spacecraft_name}: phasing_keeping.reconfiguration_interval_days must be >= 0")
        _require(0.0 < self.tolerance_fraction,
                  f"{spacecraft_name}: phasing_keeping.tolerance_fraction must be > 0")
        _require(0.0 < self.restore_tolerance_fraction,
                  f"{spacecraft_name}: phasing_keeping.restore_tolerance_fraction must be > 0")
        _require(self.correction_window_days > 0,
                  f"{spacecraft_name}: phasing_keeping.correction_window_days must be > 0")
        _require(self.max_drift_days > 0,
                  f"{spacecraft_name}: phasing_keeping.max_drift_days must be > 0")
        _require(self.max_delta_semi_major_axis_km > 0,
                  f"{spacecraft_name}: phasing_keeping.max_delta_semi_major_axis_km must be > 0")
        _require(self.control_law in PHASING_CONTROL_LAWS,
                  f"{spacecraft_name}: phasing_keeping.control_law {self.control_law!r} must be one of "
                  f"{PHASING_CONTROL_LAWS}")
        for field_name in ("mean_oe_gain", "hill_position_gain", "hill_velocity_gain"):
            value = getattr(self, field_name)
            _require(isinstance(value, (int, float)) and math.isfinite(value) and value > 0,
                      f"{spacecraft_name}: phasing_keeping.{field_name} must be a finite number > 0")


# RoeFormationConfig.control_law values (engine.roe_formation).
ROE_CONTROL_LAWS = ("impulsive", "continuous")
# The chief's largest eccentricity for ROE formations: the impulsive
# guidance (engine.roe) is the near-circular one.
ROE_MAX_CHIEF_ECCENTRICITY = 0.01  # [-]


@dataclass
class RoeTargetConfig:
    """One ROE target of a :class:`RoeFormationConfig`: from
    ``start_day`` (days after the epoch) on, the follower holds
    ``roe_m``, the six quasi-nonsingular relative orbital elements times
    the chief's semi-major axis (``engine.roe``)."""

    start_day: float = 0.0  # [day] from the epoch
    # [m] a*(da, dlambda, dex, dey, dix, diy): relative semi-major axis,
    # mean longitude, eccentricity vector, inclination vector
    roe_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


@dataclass
class RoeFormationConfig:
    """Formation flying in relative orbital elements (ROE): this
    (follower) spacecraft holds, or moves between, ROE targets relative to
    ``chief_spacecraft`` (``engine.roe`` for the math,
    ``engine.roe_formation`` for the controllers).

    ``targets`` is a schedule: each entry's ROE apply from its
    ``start_day`` on (the first at day 0); one entry holds that formation,
    more reconfigure it, e.g. an approach from 2 km behind to a passively
    safe helix.

    ``control_law``:

    * ``"impulsive"``: the tool's own guidance. When the mean ROE leave
      ``tolerance_m``, it plans along-track burns (relative semi-major
      axis, eccentricity vector and, for small errors, the mean longitude
      too), a cross-track burn (inclination vector), and for larger
      along-track errors a drift planned with the J2 state transition
      matrix, and fires them as short arcs at sunlit planned arguments of
      latitude. With ``differential_drag`` it estimates how fast drag
      changes the relative semi-major axis, over the last
      ``drag_estimate_window_days``, and sets that axis so the mean
      longitude swings evenly about its target between corrections.
    * ``"continuous"``: Basilisk's ``meanOEFeedback`` (Lyapunov feedback on
      mean equinoctial elements), its target the ROE target turned into
      element differences, refreshed every ``target_refresh_s``.

    Both fire the follower's ``station_keeping`` thruster and use its tank,
    as phasing keeping does; that controller stops holding altitude on its
    own (the ROE controller holds the relative semi-major axis). Needs a
    near-circular chief around Earth with J2 in the dynamics.
    """

    chief_spacecraft: str
    targets: list  # RoeTargetConfig, start_day increasing from 0
    control_law: str = "impulsive"  # one of ROE_CONTROL_LAWS
    # [m] "impulsive": how far each part of the mean ROE may stray before
    # a correction: a*|d(da)|, a*|d(dlambda)|, a*|d(de)|, a*|d(di)|
    tolerance_m: list = field(default_factory=lambda: [2.0, 20.0, 10.0, 10.0])
    correction_window_days: float = 1.0  # [day] "impulsive": time to bring the mean longitude back by drifting
    max_drift_m: float = 100.0  # [m] "impulsive": largest a*|da| held while drifting
    # [-] "impulsive": a burn longer than this fraction of an orbit is split
    # over several orbits, so it stays close to an impulse
    max_burn_fraction_of_orbit: float = 0.1
    # "impulsive": estimate the steady decay of the relative semi-major
    # axis that differential drag causes (from the measured mean ROE) and
    # plan the hold around it, once it is large enough to matter
    differential_drag: bool = True
    drag_estimate_window_days: float = 1.0  # [day] "impulsive": how far back the decay is fitted
    # [m^2/s^3] "continuous": diagonal of K per kg (as phasing_keeping.mean_oe_gain);
    # ten times phasing's default, which leaves metre-scale ROE errors growing
    continuous_gain: float = 25000.0
    target_refresh_s: float = 600.0  # [s] "continuous": how often the element target follows the chief's J2 drift

    def validate(self, spacecraft_name: str) -> None:
        prefix = f"{spacecraft_name}: roe_formation"
        _require(bool(self.chief_spacecraft), f"{prefix}.chief_spacecraft must not be empty")
        _require(self.chief_spacecraft != spacecraft_name,
                  f"{prefix}.chief_spacecraft cannot be the spacecraft itself")
        _require(self.control_law in ROE_CONTROL_LAWS,
                  f"{prefix}.control_law {self.control_law!r} must be one of {ROE_CONTROL_LAWS}")
        _require(isinstance(self.targets, list) and len(self.targets) >= 1,
                  f"{prefix}.targets needs at least one entry")
        previous = None
        for index, target in enumerate(self.targets):
            _require(isinstance(target, RoeTargetConfig), f"{prefix}.targets[{index}] must be an ROE target")
            _require(isinstance(target.start_day, (int, float)) and math.isfinite(target.start_day),
                      f"{prefix}.targets[{index}].start_day must be a finite number")
            _require(_finite_vector(target.roe_m, 6),
                      f"{prefix}.targets[{index}].roe_m must be 6 finite numbers [m]")
            if previous is None:
                _require(target.start_day == 0.0, f"{prefix}.targets[0].start_day must be 0")
            else:
                _require(target.start_day > previous,
                          f"{prefix}.targets[{index}].start_day must be later than the one before")
            previous = target.start_day
        _require(_finite_vector(self.tolerance_m, 4) and all(t > 0 for t in self.tolerance_m),
                  f"{prefix}.tolerance_m must be 4 finite numbers > 0 [m]")
        _require(isinstance(self.differential_drag, bool), f"{prefix}.differential_drag must be true or false")
        for field_name in ("correction_window_days", "max_drift_m", "max_burn_fraction_of_orbit",
                           "drag_estimate_window_days", "continuous_gain", "target_refresh_s"):
            value = getattr(self, field_name)
            _require(isinstance(value, (int, float)) and math.isfinite(value) and value > 0,
                      f"{prefix}.{field_name} must be a finite number > 0")
        _require(self.max_burn_fraction_of_orbit <= 0.5,
                  f"{prefix}.max_burn_fraction_of_orbit must be at most 0.5")


@dataclass
class OpticalNavigationConfig:
    """Optical navigation from the central body's disk (``engine.opnav``
    for the camera geometry, ``engine.optical_navigation`` for the run).

    A camera on the spacecraft sees the central body; every
    ``measurement_interval_s`` the tool computes where the body's disk
    falls on the detector and how large it is, from the true geometry with
    Gaussian pixel noise (no image is rendered: the measurement an image
    processing step would report). Basilisk's ``pixelLineConverter`` turns
    it into a position and ``relativeODuKF`` (an unscented Kalman filter
    with two-body dynamics) estimates position and velocity relative to
    the body. The filter starts from the true state off by one draw of
    ``initial_position_sigma_m`` / ``initial_velocity_sigma_mps`` (seeded).

    The central body must be one the two Basilisk modules know: Earth,
    the Mars barycentre or the Jupiter barycentre, and the Sun must be in
    the run (for the phase angle). In an orbit-only run the camera points
    at the body perfectly; with attitude, the spacecraft's attitude and
    ``camera_mrp_cb`` point it (point the boresight with
    ``locationPointing`` at the central body).
    """

    field_of_view_deg: float = 40.0  # [deg] edge to edge along the image's y (line) axis
    resolution_px: list = field(default_factory=lambda: [512, 512])  # [px] width, height
    # [-] MRP of the camera frame (boresight +z) relative to the body frame
    camera_mrp_cb: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    measurement_interval_s: float = 60.0  # [s] one image this often
    center_noise_px: float = 0.5  # [px] 1 sigma on the disk centre, each axis
    radius_noise_px: float = 0.5  # [px] 1 sigma on the disk radius
    min_radius_px: float = 5.0  # [px] a smaller disk is not used
    max_phase_angle_deg: float = 90.0  # [deg] Sun-body-camera angle above which the image is not used
    initial_position_sigma_m: float = 1000.0  # [m] 1 sigma, each axis: the filter's start and its error
    initial_velocity_sigma_mps: float = 1.0  # [m/s] 1 sigma, each axis
    # [m] and [m/s] 1 sigma of the process noise the filter adds at each of its time updates
    process_noise_position_m: float = 0.1
    process_noise_velocity_mps: float = 1.0e-3
    seed: int = 1  # pixel noise and the initial error

    def validate(self, spacecraft_name: str) -> None:
        prefix = f"{spacecraft_name}: optical_navigation"
        for field_name in ("field_of_view_deg", "measurement_interval_s", "min_radius_px", "max_phase_angle_deg",
                           "initial_position_sigma_m", "initial_velocity_sigma_mps"):
            value = getattr(self, field_name)
            _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                     and value > 0, f"{prefix}.{field_name} must be a finite number > 0")
        for field_name in ("center_noise_px", "radius_noise_px", "process_noise_position_m",
                           "process_noise_velocity_mps"):
            value = getattr(self, field_name)
            _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                     and value >= 0, f"{prefix}.{field_name} must be a finite number >= 0")
        _require(self.field_of_view_deg < 180.0, f"{prefix}.field_of_view_deg must be under 180")
        _require(self.max_phase_angle_deg <= 180.0, f"{prefix}.max_phase_angle_deg must be at most 180")
        _require(isinstance(self.resolution_px, list) and len(self.resolution_px) == 2
                 and all(isinstance(n, int) and not isinstance(n, bool) and n >= 16 for n in self.resolution_px),
                 f"{prefix}.resolution_px must be two whole numbers of at least 16 [px]")
        _require(_finite_vector(self.camera_mrp_cb, 3), f"{prefix}.camera_mrp_cb must be 3 finite numbers")
        _require(isinstance(self.seed, int) and not isinstance(self.seed, bool) and self.seed >= 0,
                 f"{prefix}.seed must be a whole number >= 0")


@dataclass
class LandmarkNavigationConfig:
    """Navigation from surface landmarks around a small body
    (``engine.landmarks`` for the camera geometry and the filter,
    ``engine.landmark_navigation`` for the run).

    ``landmark_count`` landmarks are placed on facets of the body's shape
    model (area-weighted, seeded). Every ``measurement_interval_s``
    Basilisk's ``pinholeCamera`` reports the whole pixel of each landmark
    it sees (in front of the camera, facing it, on the detector, the Sun
    at least ``min_sun_elevation_deg`` above the landmark's horizon; it
    does not check whether other terrain hides one). The tool's extended
    Kalman filter estimates position and velocity relative to the body
    from them, predicting with the shape's own gravity; it starts from the
    true state off by one draw of the initial sigmas (seeded).

    Needs a small body with ``gravity.polyhedral_gravity`` as the central
    body and the Sun in the run. In an orbit-only run the camera points at
    the body's centre; with attitude, the spacecraft's attitude and
    ``camera_mrp_cb`` point it.
    """

    landmark_count: int = 100
    field_of_view_deg: float = 30.0  # [deg] edge to edge along the image's width (x)
    resolution_px: list = field(default_factory=lambda: [1024, 1024])  # [px] width, height
    # [-] MRP of the camera frame (boresight +z) relative to the body frame
    camera_mrp_cb: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    measurement_interval_s: float = 600.0  # [s] one image this often
    pixel_noise_px: float = 0.0  # [px] 1 sigma added to each pixel coordinate, on top of the rounding
    min_sun_elevation_deg: float = 10.0  # [deg] a landmark in lower light is not seen
    initial_position_sigma_m: float = 100.0  # [m] 1 sigma, each axis: the filter's start and its error
    initial_velocity_sigma_mps: float = 0.05  # [m/s] 1 sigma, each axis
    # [m/s^1.5] spectral density of the filter's white acceleration noise, each axis
    process_noise_mps2_per_sqrt_hz: float = 1.0e-8
    seed: int = 1  # landmark placement, pixel noise and the initial error

    def validate(self, spacecraft_name: str) -> None:
        prefix = f"{spacecraft_name}: landmark_navigation"
        _require(isinstance(self.landmark_count, int) and not isinstance(self.landmark_count, bool)
                 and 1 <= self.landmark_count <= 1000, f"{prefix}.landmark_count must be a whole number from 1 to 1000")
        for field_name in ("field_of_view_deg", "measurement_interval_s", "initial_position_sigma_m",
                           "initial_velocity_sigma_mps"):
            value = getattr(self, field_name)
            _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                     and value > 0, f"{prefix}.{field_name} must be a finite number > 0")
        for field_name in ("pixel_noise_px", "process_noise_mps2_per_sqrt_hz"):
            value = getattr(self, field_name)
            _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                     and value >= 0, f"{prefix}.{field_name} must be a finite number >= 0")
        _require(self.field_of_view_deg < 180.0, f"{prefix}.field_of_view_deg must be under 180")
        value = self.min_sun_elevation_deg
        _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                 and -90.0 <= value < 90.0, f"{prefix}.min_sun_elevation_deg must be from -90 to under 90")
        _require(isinstance(self.resolution_px, list) and len(self.resolution_px) == 2
                 and all(isinstance(n, int) and not isinstance(n, bool) and n >= 16 for n in self.resolution_px),
                 f"{prefix}.resolution_px must be two whole numbers of at least 16 [px]")
        _require(_finite_vector(self.camera_mrp_cb, 3), f"{prefix}.camera_mrp_cb must be 3 finite numbers")
        _require(isinstance(self.seed, int) and not isinstance(self.seed, bool) and self.seed >= 0,
                 f"{prefix}.seed must be a whole number >= 0")


@dataclass
class MomentumDumpingConfig:
    """Periodic reaction-wheel momentum desaturation via this spacecraft's
    ``"thruster"`` actuators -- Basilisk's ``thrMomentumManagement`` +
    ``thrForceMapping`` (momentum-dump mode) + ``thrMomentumDumping``,
    firing thrusters ONLY to bleed off accumulated wheel momentum, never
    for primary attitude control (that stays on ``"reaction_wheel"``
    actuators via the existing control path -- see ``engine.fsw``'s
    module docstring for why the two would otherwise need a control
    -allocation module this app doesn't build).

    Requires BOTH ``"reaction_wheel"`` actuators AND ``"thruster"``
    actuators configured on this same spacecraft: reaction wheels for
    the control they're already doing, thrusters as the desaturation
    hardware. ``SpacecraftConfig.validate()`` otherwise REJECTS mixing
    the two actuator kinds on one spacecraft (see that method) -- this
    is the one case where mixing them is well-defined and required,
    since the two are not competing for the same torque authority.

    ``hs_max`` is the total reaction-wheel angular-momentum magnitude
    [N*m*s] that triggers a desaturation burn; a spacecraft with
    :class:`ActuatorConfig` ``"reaction_wheel"`` entries carrying
    ``maxMomentum`` params should typically set this somewhat below the
    sum of those wheels' capacities, so desaturation fires before any
    wheel actually saturates, not after.

    ``None`` (the default) means no desaturation is simulated -- reaction
    wheels accumulate momentum indefinitely for the whole run, exactly as
    before this feature existed.
    """

    hs_max: float  # [N*m*s] total RW angular momentum magnitude that triggers desaturation
    thr_min_fire_time: float = 0.02  # [s] thruster firing pulse resolution
    max_counter_value: int = 100  # [-] control periods to wait between desaturation firings

    def validate(self, spacecraft_name: str) -> None:
        _require(self.hs_max > 0, f"{spacecraft_name}: momentum_dumping.hs_max must be > 0")
        _require(self.thr_min_fire_time > 0, f"{spacecraft_name}: momentum_dumping.thr_min_fire_time must be > 0")
        _require(self.max_counter_value >= 1, f"{spacecraft_name}: momentum_dumping.max_counter_value must be >= 1")


@dataclass
class MagneticMomentumManagementConfig:
    """Continuous reaction-wheel momentum management via this
    spacecraft's ``"magnetic_torque_rod"`` actuators -- Basilisk's
    ``mtbMomentumManagement``, a materially different strategy from
    :class:`MomentumDumpingConfig`'s thruster-based threshold-and-burst
    approach: rather than waiting for total momentum to cross a
    threshold and firing a discrete pulse, this continuously biases the
    commanded RW motor torque (sitting between ``rwMotorTorque`` and the
    RW hardware) so each wheel's speed is driven toward its own entry in
    ``wheel_speed_biases_rad_s``, using whatever magnetic torque the
    real geomagnetic field (Basilisk's WMM model) allows at the
    spacecraft's current position -- see ``examples/scenarioMtbMomentumManagement.py``,
    the real, shipped example this is built from.

    The two desaturation strategies are mutually exclusive alternatives
    (different actuator hardware, different control law) -- a spacecraft
    uses one or the other, never both.

    Requires BOTH ``"reaction_wheel"`` actuators AND
    ``"magnetic_torque_rod"`` actuators configured on this same
    spacecraft (mirroring :class:`MomentumDumpingConfig`'s own
    requirement), and ``gravity.central_body == "earth"`` (Basilisk's
    WMM magnetic field model is Earth-only, same restriction as a
    ``"magnetometer"`` sensor -- see ``engine.fsw``'s module docstring).
    That central-body check is enforced twice: once here for immediate,
    in-dialog feedback, and once more at the engine layer
    (``engine.service.SimulationService.build()``) when the scenario
    actually runs, which is what this is mirroring -- see
    :meth:`Scenario.validate`'s own central_body != "earth" block,
    which checks this field (and the analogous ``"magnetometer"``
    sensor case) directly, since neither this class nor
    :class:`SensorConfig` has access to the scenario's own
    ``gravity.central_body`` on their own.

    ``wheel_speed_biases_rad_s`` needs exactly one entry per
    ``"reaction_wheel"`` actuator on this spacecraft, in the same order
    those actuators are listed -- Basilisk's ``mtbMomentumManagement``
    maps them positionally, not by name. ``None`` (the default) means no
    magnetic momentum management is simulated -- reaction wheels
    accumulate momentum indefinitely, exactly as before this feature
    existed.
    """

    wheel_speed_biases_rad_s: list  # [rad/s] one entry per reaction_wheel actuator, in listed order
    c_gain: float = 0.003  # [-] control gain mapping wheel speed error to desired magnetic torque

    def validate(self, spacecraft_name: str, num_reaction_wheels: int) -> None:
        _require(len(self.wheel_speed_biases_rad_s) == num_reaction_wheels,
                  f"{spacecraft_name}: magnetic_momentum_management.wheel_speed_biases_rad_s needs exactly "
                  f"{num_reaction_wheels} entries (one per reaction_wheel actuator), got "
                  f"{len(self.wheel_speed_biases_rad_s)}")
        _require(self.c_gain > 0, f"{spacecraft_name}: magnetic_momentum_management.c_gain must be > 0")


_NAV_CHANNELS = (  # (field prefix, unit, what it perturbs)
    ("attitude", "deg", "attitude"),
    ("rate", "deg/s", "body rate"),
    ("sun", "deg", "Sun heading"),
    ("position", "m", "position"),
    ("velocity", "m/s", "velocity"),
)


@dataclass
class NavigationErrorConfig:
    """Errors on what the flight software is told, by Basilisk's
    ``simpleNav`` (its Gauss-Markov error model, ``PMatrix`` and
    ``walkBounds``). Without this, the navigation messages are the true
    state.

    Each error, per axis, is a random walk: every flight-software step it
    changes by a normal draw of standard deviation ``<channel>_step`` and is
    held within ``<channel>_bound`` (Basilisk clamps at the bound). A
    channel with a step needs a bound: Basilisk treats a zero bound as no
    bound at all, and the error would drift without limit. Attitude and
    Sun-heading errors are small rotations, given here in degrees per axis
    (``simpleNav`` applies them as MRPs, ``tan(angle/4)``). ``seed`` is
    Basilisk's random-number seed (``None``: its default), so a run is
    repeatable.
    """

    attitude_step_deg: float = 0.0  # [deg] 1-sigma change per step, per axis
    attitude_bound_deg: float = 0.0  # [deg] per axis
    rate_step_deg_s: float = 0.0  # [deg/s]
    rate_bound_deg_s: float = 0.0  # [deg/s]
    sun_step_deg: float = 0.0  # [deg]
    sun_bound_deg: float = 0.0  # [deg]
    position_step_m: float = 0.0  # [m]
    position_bound_m: float = 0.0  # [m]
    velocity_step_m_s: float = 0.0  # [m/s]
    velocity_bound_m_s: float = 0.0  # [m/s]
    seed: int | None = None

    def channel(self, prefix: str) -> tuple:
        """``(step, bound)`` of one channel, in this config's units."""
        unit = next(u for p, u, _ in _NAV_CHANNELS if p == prefix).replace("/", "_")
        return getattr(self, f"{prefix}_step_{unit}"), getattr(self, f"{prefix}_bound_{unit}")

    def validate(self, spacecraft_name: str) -> None:
        for prefix, unit, label in _NAV_CHANNELS:
            step, bound = self.channel(prefix)
            for value, what in ((step, "step"), (bound, "bound")):
                _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                         and value >= 0.0,
                         f"{spacecraft_name}: navigation_error {label} {what} must be a number >= 0 [{unit}]")
            _require(step == 0.0 or bound > 0.0,
                     f"{spacecraft_name}: navigation_error {label} needs a bound > 0 when its step is set "
                     "(without one Basilisk lets the error grow without limit)")
        _require(self.attitude_bound_deg < 180.0 and self.sun_bound_deg < 180.0,
                 f"{spacecraft_name}: navigation_error attitude and Sun bounds must be below 180 deg")
        _require(self.seed is None or (isinstance(self.seed, int) and not isinstance(self.seed, bool)
                                       and 0 <= self.seed < 2 ** 32),
                 f"{spacecraft_name}: navigation_error seed must be an integer from 0 to 2^32 - 1")

    @property
    def any_error(self) -> bool:
        return any(self.channel(prefix)[0] > 0.0 for prefix, _, _ in _NAV_CHANNELS)


@dataclass
class FuelTankConfig:
    """Real propellant depletion for this spacecraft's ``"thruster"``
    actuators -- Basilisk's ``fuelTank`` state effector
    (``FuelTankModelUniformBurn``) tied to the thruster hardware via
    ``fuelTank.addThrusterSet()``, confirmed against
    ``examples/MultiSatBskSim/modelsMultiSat/BSK_MultiSatDynamics.py``'s
    own ``SetFuelTank()``. Every tick, the tank reads the SAME mass-flow
    rate (derived from each firing thruster's own ``steadyIsp`` and
    commanded thrust -- the standard rocket equation, ``mDot = F /
    (steadyIsp * g0)``) the thruster hardware itself already computes for
    its own physics, and depletes ``hub.mHub`` by exactly that amount --
    unlike this app's existing hand-rolled propellant bookkeeping
    (``engine.orbit_maintenance``'s station-keeping/phasing/
    constant-thrust controllers, which track an explicit-Euler rocket
    -equation estimate in Python and feed it back into ``hub.mHub``
    themselves), this is Basilisk's own state effector doing the real
    physics, including the resulting center-of-mass shift as propellant
    depletes (``r_TcT_TInit``), which the hand-rolled scalar-mass
    approach cannot capture at all.

    Requires at least one ``"thruster"`` actuator on this spacecraft --
    a tank with nothing drawing from it is schema-valid (just inert) in
    Basilisk itself, but almost certainly not what was intended, so this
    schema rejects it with a specific message instead.

    ``None`` (the default) means no fuel tank is simulated -- thrusters
    fire with unlimited propellant, exactly as before this feature
    existed (this app's pre-existing behavior for ACS/desaturation
    thrusters specifically; station-keeping/phasing/constant-thrust
    propellant bookkeeping is unrelated and unaffected either way).
    """

    propellant_mass_kg: float  # [kg] initial propellant mass loaded in the tank
    max_propellant_mass_kg: float  # [kg] tank capacity -- propellant_mass_kg must not exceed this
    tank_position_b_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # [m] r_TB_B, tank position in body frame

    def validate(self, spacecraft_name: str) -> None:
        _require(self.max_propellant_mass_kg > 0, f"{spacecraft_name}: fuel_tank.max_propellant_mass_kg must be > 0")
        _require(0.0 <= self.propellant_mass_kg <= self.max_propellant_mass_kg,
                  f"{spacecraft_name}: fuel_tank.propellant_mass_kg must be between 0 and "
                  "max_propellant_mass_kg")
        _require(len(self.tank_position_b_m) == 3,
                  f"{spacecraft_name}: fuel_tank.tank_position_b_m must be a 3-element [x, y, z] list [m]")


SUPPORTED_DISPOSALS = ("uncontrolled_reentry", "controlled_reentry", "graveyard", "none")


@dataclass
class PropellantBudgetConfig:
    """Inputs for a delta-V and propellant budget in the manner of ESA's
    AD10 guideline (EOP-FM/2024-07-177 v3.0; see
    engine/propellant_budget.py). Contributors left as None are taken
    from the spacecraft's last run (in- and out-of-plane orbit control,
    formation keeping); the rest are entered here or computed (collision
    avoidance, clearance, injection corrections, disposal)."""

    mission_years: float = 5.0  # [year] nominal operations from the epoch (AD10 Sec. 5.7)
    dry_mass_includes_margin: bool = False  # else the system margin below is added (Sec. 5.10)
    system_margin_fraction: float = 0.15  # [-] Sec. 5.10 default
    tank_capacity_kg: float = 0.0  # [kg] maximum propellant load (Sec. 5.8); 0 = the budget's own total
    isp_s: float | None = None  # [s] None = the orbit thruster's (station keeping etc.)
    thrust_angle_deg: float = 0.0  # [deg] thruster axis vs wanted thrust direction (Sec. 5.11)
    misalignment_deg: float = 0.0  # [deg] incl. attitude error while thrusting
    plume_efficiency: float = 1.0  # [-]
    modulation_efficiency: float = 1.0  # [-]
    # Beginning of life (Sec. 6.1), 2-sigma launcher injection errors
    injection_sma_error_km: float = 0.0  # [km]
    injection_eccentricity_error: float = 0.0  # [-] eccentricity-vector error to correct (frozen orbit)
    injection_inclination_error_deg: float = 0.0  # [deg]
    injection_raan_delta_v_m_s: float = 0.0  # [m/s] RAAN/MLST correction, strategy-specific
    orbit_acquisition_delta_v_m_s: float = 0.0  # [m/s]
    # Mission operations (Sec. 6.2); None = from the last run
    transfer_delta_v_m_s: float = 0.0  # [m/s]
    in_plane_control_delta_v_m_s: float | None = None  # [m/s]
    out_of_plane_control_delta_v_m_s: float | None = None  # [m/s]
    formation_delta_v_m_s: float | None = None  # [m/s]
    collision_avoidance_count: float = 0.0  # [-] e.g. from ESA DRAMA, before the x4 margin
    attitude_thruster_propellant_kg: float = 0.0  # [kg] before the 100% margin
    # End of life (Sec. 6.3)
    disposal: str = "uncontrolled_reentry"  # see SUPPORTED_DISPOSALS
    clearance_sma_drop_km: float = 0.0  # [km] AD10 suggests >= 5 km for formation flyers
    disposal_lifetime_years: float = 5.0  # [year] orbit lifetime after the disposal burn
    controlled_reentry_delta_v_m_s: float = 0.0  # [m/s] burns before the last
    controlled_reentry_last_burn_m_s: float = 0.0  # [m/s] the last burn, before its 15% margin
    hall_thruster_ignition_kg: float = 0.0  # [kg] cathode start-up losses over the mission

    def validate(self, spacecraft_name: str) -> None:
        where = f"{spacecraft_name}: propellant_budget"
        _require(0.0 < self.mission_years <= 30.0, f"{where}.mission_years must be in (0, 30]")
        _require(0.0 <= self.system_margin_fraction < 1.0, f"{where}.system_margin_fraction must be in [0, 1)")
        _require(self.tank_capacity_kg >= 0.0, f"{where}.tank_capacity_kg must be >= 0")
        _require(self.isp_s is None or self.isp_s > 0.0, f"{where}.isp_s must be > 0")
        _require(0.0 <= self.thrust_angle_deg < 90.0 and 0.0 <= self.misalignment_deg < 90.0,
                  f"{where}: thrust_angle_deg and misalignment_deg must be in [0, 90)")
        _require(0.0 < self.plume_efficiency <= 1.0 and 0.0 < self.modulation_efficiency <= 1.0,
                  f"{where}: plume_efficiency and modulation_efficiency must be in (0, 1]")
        for name in ("injection_sma_error_km", "injection_eccentricity_error", "injection_inclination_error_deg",
                     "injection_raan_delta_v_m_s", "orbit_acquisition_delta_v_m_s", "transfer_delta_v_m_s",
                     "collision_avoidance_count", "attitude_thruster_propellant_kg", "clearance_sma_drop_km",
                     "controlled_reentry_delta_v_m_s", "controlled_reentry_last_burn_m_s",
                     "hall_thruster_ignition_kg"):
            _require(getattr(self, name) >= 0.0, f"{where}.{name} must be >= 0")
        for name in ("in_plane_control_delta_v_m_s", "out_of_plane_control_delta_v_m_s", "formation_delta_v_m_s"):
            value = getattr(self, name)
            _require(value is None or value >= 0.0, f"{where}.{name} must be >= 0 (or unset: from the last run)")
        _require(self.disposal in SUPPORTED_DISPOSALS,
                  f"{where}.disposal {self.disposal!r} must be one of {SUPPORTED_DISPOSALS}")
        _require(0.0 < self.disposal_lifetime_years <= 25.0, f"{where}.disposal_lifetime_years must be in (0, 25]")


@dataclass
class FacetConfig:
    """One flat plate of the spacecraft's outer surface, for attitude
    -dependent drag and solar radiation pressure -- Basilisk's
    ``facetDragDynamicEffector``/``facetSRPDynamicEffector``. Each plate
    pushes only on its lit (or wind-facing) side, at its own centre of
    pressure, so the force depends on attitude and an offset between that
    centre and the centre of mass gives a disturbance torque. A two-sided
    panel (a solar array) is two facets with opposite normals.
    """

    name: str
    area_m2: float  # [m^2]
    normal_b: list  # [-] outward normal, body frame (normalized when built)
    location_b: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # [m] centre of pressure from point B
    drag_coeff: float = 2.2  # [-]
    specular_coeff: float = 0.3  # [-] fraction of sunlight reflected mirror-like
    diffuse_coeff: float = 0.1  # [-] fraction reflected diffusely; the rest is absorbed

    def validate(self, spacecraft_name: str) -> None:
        where = f"{spacecraft_name}: facet {self.name!r}"
        _require(bool(self.name), f"{spacecraft_name}: every facet needs a name")
        _require(isinstance(self.area_m2, (int, float)) and 0.0 < self.area_m2 <= 1.0e4,
                  f"{where}: area_m2 must be in (0, 1e4] m^2")
        _require(_is_direction_vector(self.normal_b),
                  f"{where}: normal_b must be a non-zero, finite 3-element body-frame vector")
        _require(isinstance(self.location_b, list) and len(self.location_b) == 3
                  and all(isinstance(v, (int, float)) and math.isfinite(v) for v in self.location_b),
                  f"{where}: location_b must be a finite 3-element [x, y, z] in m")
        _require(isinstance(self.drag_coeff, (int, float)) and 0.0 <= self.drag_coeff <= 10.0,
                  f"{where}: drag_coeff must be in [0, 10]")
        _require(0.0 <= self.specular_coeff <= 1.0 and 0.0 <= self.diffuse_coeff <= 1.0
                  and self.specular_coeff + self.diffuse_coeff <= 1.0,
                  f"{where}: specular_coeff and diffuse_coeff must each be in [0, 1] and sum to at most 1")


# A spacecraft's 3D model (SpacecraftModelConfig): the shapes it is built
# from and the dimensions each takes, in the order forms show them. The
# geometry itself (meshes, mass properties, facets) is model3d's; these
# names live here so validation needs no numpy.
MODEL_SHAPE_DIMENSIONS = {
    "box": ("x", "y", "z"),
    "prism": ("width_across_flats", "height"),
    "cylinder": ("diameter", "height"),
    "cone": ("base_diameter", "height"),
    "sphere": ("diameter",),
    "panel": ("width", "length", "thickness"),
    "mesh": (),
}
MODEL_SHAPES = tuple(MODEL_SHAPE_DIMENSIONS)
# The face names a part can leave out of the surface model; "sides" stands
# for all side faces of a prism, cylinder or cone.
MODEL_SHAPE_FACES = {
    "box": ("+x", "-x", "+y", "-y", "+z", "-z"),
    "prism": ("+z", "-z", "sides"),
    "cylinder": ("+z", "-z", "sides"),
    "cone": ("-z", "sides"),
    "sphere": (),
    "panel": ("+z", "-z"),
    "mesh": (),
}
MODEL_DISTRIBUTIONS = ("solid", "shell")
MASS_PROPERTIES_SOURCES = ("computed", "typed", "imported")
MESH_UNITS = ("m", "mm", "cm", "in")
MESH_UP_AXES = ("z", "y")


def _finite_vector(values, length: int = 3) -> bool:
    return (isinstance(values, list) and len(values) == length
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values))


@dataclass
class ModelMeshConfig:
    """An imported ``.obj`` file that a model's ``mesh`` parts come from.
    ``.obj`` files carry no unit or up direction, so both are recorded."""

    path: str  # absolute, or relative to the scenario file
    sha256: str = ""  # [-] of the file when it was imported; "" when not recorded
    units: str = "m"  # one of MESH_UNITS
    up_axis: str = "z"  # one of MESH_UP_AXES: "y" for files exported Y-up

    def validate(self, where: str) -> None:
        _require(isinstance(self.path, str) and bool(self.path.strip()), f"{where}: path must not be empty")
        _require(self.sha256 == "" or (len(self.sha256) == 64 and all(c in "0123456789abcdef" for c in self.sha256)),
                 f"{where}: sha256 must be empty or 64 lowercase hex digits")
        _require(self.units in MESH_UNITS, f"{where}: units {self.units!r} must be one of {MESH_UNITS}")
        _require(self.up_axis in MESH_UP_AXES, f"{where}: up_axis {self.up_axis!r} must be one of {MESH_UP_AXES}")


@dataclass
class ModelPartConfig:
    """One part of a 3D model: a simple shape, or a group of an imported
    mesh, placed in the body frame and given a mass and surface properties.

    The part's local frame is turned by ``rotation_deg = [roll, pitch,
    yaw]`` (yaw about z, then pitch about the new y, then roll about the
    new x) and moved by ``position_b_m``. ``scale`` applies to mesh parts
    only, in the mesh's own axes, before the rotation.
    """

    name: str
    shape: str  # one of MODEL_SHAPES
    dimensions_m: dict = field(default_factory=dict)  # [m] the keys MODEL_SHAPE_DIMENSIONS gives for the shape
    sides: int = 8  # prism only: an octagon by default
    segments: int = 16  # cylinder, cone, sphere: sides they are drawn and faceted with
    mesh_index: int | None = None  # mesh parts: index into SpacecraftModelConfig.meshes
    mesh_group: str = ""  # mesh parts: the group (o/g name) in that file
    position_b_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # [m]
    rotation_deg: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # [deg] roll, pitch, yaw (3-2-1)
    scale: list = field(default_factory=lambda: [1.0, 1.0, 1.0])  # [-] mesh parts only
    color: list = field(default_factory=lambda: [0.7, 0.7, 0.7])  # [-] RGB, each 0..1
    visible: bool = True
    mass_kg: float = 0.0  # [kg]
    distribution: str = "solid"  # "solid": through the volume; "shell": over the surface
    counts_toward_mass: bool = True  # False for a part whose mass is modelled elsewhere (a flexible array)
    in_surface_model: bool = True  # its outer faces become drag/SRP facets
    excluded_faces: list = field(default_factory=list)  # names from MODEL_SHAPE_FACES left out of the facets
    drag_coeff: float = 2.2  # [-]
    specular_coeff: float = 0.3  # [-]
    diffuse_coeff: float = 0.1  # [-]

    def validate(self, where: str, mesh_count: int) -> None:
        _require(name_error("part", self.name) is None, f"{where}: {name_error('part', self.name)}")
        where = f"{where}: part {self.name!r}"
        _require(self.shape in MODEL_SHAPES, f"{where}: shape {self.shape!r} must be one of {MODEL_SHAPES}")
        expected = set(MODEL_SHAPE_DIMENSIONS[self.shape])
        _require(set(self.dimensions_m) == expected,
                 f"{where}: a {self.shape} needs dimensions_m with exactly {sorted(expected)}, "
                 f"got {sorted(self.dimensions_m)}")
        for key, value in self.dimensions_m.items():
            _require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                     and 0.0 < value <= 1000.0, f"{where}: dimensions_m[{key!r}] must be in (0, 1000] m")
        _require(isinstance(self.sides, int) and 3 <= self.sides <= 64, f"{where}: sides must be 3 to 64")
        _require(isinstance(self.segments, int) and 8 <= self.segments <= 256, f"{where}: segments must be 8 to 256")
        if self.shape == "mesh":
            _require(isinstance(self.mesh_index, int) and 0 <= self.mesh_index < mesh_count,
                     f"{where}: mesh_index must name one of the model's {mesh_count} mesh file(s)")
            _require(bool(self.mesh_group), f"{where}: mesh_group must name a group of the mesh file")
        _require(_finite_vector(self.position_b_m), f"{where}: position_b_m must be a finite [x, y, z] in m")
        _require(_finite_vector(self.rotation_deg), f"{where}: rotation_deg must be a finite [roll, pitch, yaw]")
        _require(_finite_vector(self.scale) and all(v != 0.0 for v in self.scale),
                 f"{where}: scale must be three finite, non-zero factors")
        _require(_finite_vector(self.color) and all(0.0 <= v <= 1.0 for v in self.color),
                 f"{where}: color must be [r, g, b], each 0 to 1")
        _require(isinstance(self.mass_kg, (int, float)) and math.isfinite(self.mass_kg)
                 and 0.0 <= self.mass_kg <= 1.0e6, f"{where}: mass_kg must be in [0, 1e6]")
        _require(self.distribution in MODEL_DISTRIBUTIONS,
                 f"{where}: distribution {self.distribution!r} must be one of {MODEL_DISTRIBUTIONS}")
        allowed = MODEL_SHAPE_FACES[self.shape]
        bad = [face for face in self.excluded_faces if face not in allowed]
        _require(not bad, f"{where}: excluded_faces {bad} are not faces of a {self.shape}"
                 + (f" (it has {list(allowed)})" if allowed else ""))
        _require(isinstance(self.drag_coeff, (int, float)) and 0.0 <= self.drag_coeff <= 10.0,
                 f"{where}: drag_coeff must be in [0, 10]")
        _require(0.0 <= self.specular_coeff <= 1.0 and 0.0 <= self.diffuse_coeff <= 1.0
                 and self.specular_coeff + self.diffuse_coeff <= 1.0,
                 f"{where}: specular_coeff and diffuse_coeff must each be in [0, 1] and sum to at most 1")


@dataclass
class ModelMassPropertiesConfig:
    """Mass properties typed in, or imported from a file, instead of
    computed from the parts: about the center of mass, in body axes."""

    mass_kg: float  # [kg]
    center_of_mass_b_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # [m] from body point B
    inertia_kg_m2: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])  # about it
    source_file: str = ""  # imported: the file's name
    source_sha256: str = ""  # imported: its SHA-256

    def validate(self, where: str) -> None:
        _require(isinstance(self.mass_kg, (int, float)) and math.isfinite(self.mass_kg)
                 and 0.0 < self.mass_kg <= 1.0e6, f"{where}: mass_kg must be in (0, 1e6]")
        _require(_finite_vector(self.center_of_mass_b_m), f"{where}: center_of_mass_b_m must be a finite [x, y, z]")
        _require(_finite_vector(self.inertia_kg_m2, 9), f"{where}: inertia_kg_m2 must be 9 finite numbers (3x3)")


@dataclass
class SpacecraftModelConfig:
    """A spacecraft's 3D model (see ``spacemissionstudio.model3d``): parts
    built from simple shapes or imported ``.obj`` groups. Applying it
    (``model3d.model.apply``) writes what it derives into the spacecraft's
    own fields -- ``dry_mass_kg``, ``center_of_mass_b_m``, ``inertia_kg_m2``
    and ``facets`` -- which are what the simulation reads; the model is
    kept so it can be edited again. ``use_for_vizard`` shows the model in
    Vizard when ``vizard_model_path`` is not set."""

    parts: list = field(default_factory=list)  # list[ModelPartConfig]
    meshes: list = field(default_factory=list)  # list[ModelMeshConfig]
    mass_properties_source: str = "computed"  # one of MASS_PROPERTIES_SOURCES
    mass_properties: ModelMassPropertiesConfig | None = None  # for "typed" and "imported"
    apply_mass_properties: bool = True
    apply_facets: bool = True
    use_for_vizard: bool = True

    def validate(self, spacecraft_name: str) -> None:
        where = f"{spacecraft_name}: model"
        _require(bool(self.parts), f"{where} needs at least one part")
        names = [part.name for part in self.parts]
        _require(len(names) == len(set(names)), f"{where}: part names must be unique, got {names}")
        for k, mesh in enumerate(self.meshes):
            mesh.validate(f"{where}: meshes[{k}]")
        for part in self.parts:
            part.validate(where, len(self.meshes))
        _require(self.mass_properties_source in MASS_PROPERTIES_SOURCES,
                 f"{where}: mass_properties_source {self.mass_properties_source!r} must be one of "
                 f"{MASS_PROPERTIES_SOURCES}")
        if self.mass_properties_source != "computed":
            _require(self.mass_properties is not None,
                     f"{where}: mass_properties_source {self.mass_properties_source!r} needs mass_properties")
        if self.mass_properties is not None:
            self.mass_properties.validate(f"{where}: mass_properties")


@dataclass
class SpacecraftConfig:
    name: str
    orbit: OrbitIC
    # [kg] The spacecraft's mass WITHOUT station-keeping propellant. With
    # station_keeping unset (the default), this is simply the whole
    # spacecraft's simulated mass, exactly as before StationKeepingConfig
    # existed. With station_keeping set, engine.service initializes the
    # simulated mass to dry_mass_kg + station_keeping.propellant_kg, and
    # the station-keeping controller depletes it back toward dry_mass_kg
    # as propellant burns -- see StationKeepingConfig's docstring.
    dry_mass_kg: float = 100.0
    inertia_kg_m2: list = field(default_factory=lambda: [10.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0])
    # [m] The center of mass from body point B, in body axes (Basilisk's
    # hub.r_BcB_B); inertia_kg_m2 is about this point. Facet locations,
    # thruster and sensor positions stay measured from B, so an offset
    # here gives drag, SRP and thrust their torque about the center of mass.
    center_of_mass_b_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    sigma_bn_init: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    omega_bn_b_init_rad_s: list = field(default_factory=lambda: [0.0, 0.0, 0.0])

    # Perturbations -- Phase 0's service only ever consumes central-body
    # gravity; these flags are validated/round-tripped now and read starting
    # Phase 1, matching the "reserve the shape, don't wire it all up yet" note.
    enable_drag: bool = False
    drag_coeff: float = 2.2
    drag_area_m2: float = 1.0
    enable_srp: bool = False
    srp_coeff: float = 1.3
    srp_area_m2: float = 1.0
    # Optional flat-plate model of the outer surface (list[FacetConfig]).
    # When set, enabled drag and SRP use it (attitude-dependent forces plus
    # their torques) instead of the sphere-like drag_area_m2/drag_coeff and
    # srp_area_m2/srp_coeff above. Needs simulation_mode 'full_attitude'.
    facets: list = field(default_factory=list)

    # Torque from the central body's (and, if present, any third-body
    # perturber's) gravity gradient across the spacecraft's own mass
    # distribution -- Basilisk's real GravityGradientEffector, not an
    # approximation: it reads the spacecraft's actual simulated inertia/
    # position/attitude every tick (see engine.service), so it stays
    # correct through inertia changes (e.g. FuelTank depletion, once that
    # exists) rather than being computed once from initial conditions.
    # Negligible in LEO for an actively-controlled spacecraft (the RW/MRP
    # feedback loop simply rejects it as one more disturbance torque), but
    # real for anything coasting without active control (fsw_mode=None) or
    # in a large/elongated inertia configuration -- exactly the case this
    # schema previously had no way to model at all. False by default:
    # every scenario written before this field existed keeps its exact
    # previous dynamics.
    enable_gravity_gradient: bool = False

    sensors: list = field(default_factory=list)  # list[SensorConfig]
    actuators: list = field(default_factory=list)  # list[ActuatorConfig]
    # One of SUPPORTED_FSW_MODES, or None for no attitude control (attitude
    # still integrates -- see engine.service -- it just isn't commanded).
    fsw_mode: str | None = None
    # Mode-specific settings engine.fsw needs to build the guidance chain,
    # e.g. {"sigma_R0N": [...]} for "inertial3D" or
    # {"target_ground_station": "dsn-goldstone", "pHat_B": [0, 0, 1]} for
    # "locationPointing" -- see engine/fsw.py's per-mode builder docstrings
    # for the full set each mode reads.
    fsw_params: dict = field(default_factory=dict)
    # {"K": ..., "P": ...} MRP feedback control gains; see
    # engine.fsw.DEFAULT_MRP_GAINS for the defaults used when a key is absent.
    control_params: dict = field(default_factory=dict)

    power: PowerConfig | None = None
    rf_link: RFLinkConfig | None = None
    comms_pointing: CommsPointingConfig | None = None
    data_handling: DataHandlingConfig | None = None
    solar_arrays: list = field(default_factory=list)  # SolarArrayConfig: flexible, hinged arrays
    station_keeping: StationKeepingConfig | None = None
    geo_station_keeping: GeoStationKeepingConfig | None = None
    phasing_keeping: PhasingKeepingConfig | None = None
    roe_formation: RoeFormationConfig | None = None  # formation in relative orbital elements
    optical_navigation: OpticalNavigationConfig | None = None  # camera navigation from the central body's disk
    landmark_navigation: LandmarkNavigationConfig | None = None  # camera navigation from a small body's landmarks
    constant_thrust: ConstantThrustConfig | None = None
    momentum_dumping: MomentumDumpingConfig | None = None
    magnetic_momentum_management: MagneticMomentumManagementConfig | None = None
    # What simpleNav tells the flight software; None: the true state.
    navigation_error: NavigationErrorConfig | None = None
    fuel_tank: FuelTankConfig | None = None
    propellant_budget: PropellantBudgetConfig | None = None  # see engine/propellant_budget.py

    # Phase 5: PURELY COSMETIC Vizard display -- replaces this spacecraft's
    # default cube icon with a custom CAD model
    # (Basilisk.utilities.vizSupport.createCustomModel()). Never affects
    # simulated physics: mass properties, drag/SRP area, etc. still come
    # from dry_mass_kg/inertia_kg_m2/drag_area_m2/srp_area_m2 above, same
    # as when this is unset. None (the default) leaves Vizard's own
    # default icon in place.
    vizard_model_path: str | None = None  # path to a .obj file, or "CUBE"/"CYLINDER"/"SPHERE"
    vizard_model_offset_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    vizard_model_rotation_deg: list = field(default_factory=lambda: [0.0, 0.0, 0.0])  # 3-2-1 Euler (z,y,x)
    vizard_model_scale: list = field(default_factory=lambda: [1.0, 1.0, 1.0])
    # The spacecraft's 3D model, if one was built or imported in the model
    # editor; see SpacecraftModelConfig.
    model: SpacecraftModelConfig | None = None

    def validate(self) -> None:
        _require(name_error("spacecraft", self.name) is None, name_error("spacecraft", self.name) or "")
        # Generous plausibility ceiling (docs/ux_audit.md, "units
        # enforced only by naming convention") -- 1e6 kg is already far
        # above any single real spacecraft (the ISS, the largest
        # crewed structure ever assembled, is about 4.2e5 kg); catches a
        # likely magnitude typo (e.g. grams instead of kilograms)
        # without rejecting anything physically real.
        _require(0.0 < self.dry_mass_kg <= 1.0e6,
                  f"{self.name}: dry_mass_kg must be in (0, 1e6] -- if your intended value is outside "
                  "this range, check for a units mixup (e.g. g instead of kg)")
        _require(len(self.inertia_kg_m2) == 9, f"{self.name}: inertia_kg_m2 must have 9 elements (3x3, row-major)")
        # Real bug, found against a real (newer) Basilisk build: Basilisk's
        # own HubEffector::validateConfiguration() -- added after this
        # project's verified 2.12.0 baseline, see
        # src/architecture/utilities/avsEigenSupport.cpp's
        # eigenIsValidInertiaMatrix() -- now rejects an inertia tensor
        # whose principal moments violate the triangle inequality (no
        # rigid body's principal moment may exceed the sum of the other
        # two), previously only caught deep inside InitializeSimulation()
        # with a cryptic C++ message ("IHubPntBc_B is not a valid inertia
        # tensor") rather than at scenario-validation time. Confirmed
        # directly: tests/test_gravity_gradient.py shipped exactly this
        # mistake (diag(5, 10, 20): 5+10 < 20), undetected against 2.12.0.
        # Scoped to the diagonal case -- every inertia_kg_m2 across this
        # project's own bundled templates/scenarios is diagonal (confirmed
        # by sweeping all of them), and a diagonal matrix's diagonal
        # entries ARE its principal moments directly, with no eigenvalue
        # decomposition needed (this module deliberately has no numpy
        # dependency -- see its own "standalone, no Basilisk needed"
        # design). A fully general (off-diagonal-populated) tensor still
        # reaches Basilisk's own runtime check unvalidated here, just
        # without this earlier, clearer message.
        inertia_diag = (self.inertia_kg_m2[0], self.inertia_kg_m2[4], self.inertia_kg_m2[8])
        inertia_off_diag = (self.inertia_kg_m2[1], self.inertia_kg_m2[2], self.inertia_kg_m2[3],
                             self.inertia_kg_m2[5], self.inertia_kg_m2[6], self.inertia_kg_m2[7])
        if all(v == 0.0 for v in inertia_off_diag):
            ix, iy, iz = inertia_diag
            _require(ix > 0.0 and iy > 0.0 and iz > 0.0,
                      f"{self.name}: inertia_kg_m2's diagonal entries (principal moments) must be positive")
            _require(ix + iy >= iz and iy + iz >= ix and ix + iz >= iy,
                      f"{self.name}: inertia_kg_m2's diagonal entries ({ix:g}, {iy:g}, {iz:g}) violate the "
                      "triangle inequality -- no rigid body's principal moment of inertia can exceed the "
                      "sum of the other two; check for a units/axis mixup")
        _require(_finite_vector(self.center_of_mass_b_m)
                 and math.sqrt(sum(v * v for v in self.center_of_mass_b_m)) <= 100.0,
                 f"{self.name}: center_of_mass_b_m must be a finite [x, y, z] within 100 m of point B")
        if self.model is not None:
            self.model.validate(self.name)
        _require(len(self.sigma_bn_init) == 3, f"{self.name}: sigma_bn_init must have 3 elements")
        _require(len(self.omega_bn_b_init_rad_s) == 3, f"{self.name}: omega_bn_b_init_rad_s must have 3 elements")
        # drag_coeff/drag_area_m2/srp_coeff/srp_area_m2 feed straight into
        # Basilisk's exponentialAtmosphere drag effector/SRP effector as a
        # physical coefficient/projected area (engine.service) -- neither
        # effector itself rejects a non-positive value (no crash, no
        # exception), so a <= 0 area/coefficient here would otherwise
        # silently produce a reversed or zero drag/SRP force instead of a
        # clear error, including when the other three are left at their
        # schema defaults and only one was mistyped. Validated
        # unconditionally (not just when enable_drag/enable_srp is True)
        # so toggling either flag on later can't resurface an
        # already-invalid value unnoticed.
        _require(self.drag_coeff > 0, f"{self.name}: drag_coeff must be > 0")
        # Generous plausibility ceilings (docs/ux_audit.md, "units
        # enforced only by naming convention") -- 10,000 m^2 is already
        # far above any real spacecraft's cross-sectional area (even the
        # ISS's combined structure/arrays is a few thousand m^2); catches
        # a likely magnitude typo without rejecting anything real.
        _require(0.0 < self.drag_area_m2 <= 1.0e4,
                  f"{self.name}: drag_area_m2 must be in (0, 1e4] -- if your intended value is outside "
                  "this range, check for a units mixup (e.g. cm^2 instead of m^2)")
        _require(self.srp_coeff > 0, f"{self.name}: srp_coeff must be > 0")
        _require(0.0 < self.srp_area_m2 <= 1.0e4,
                  f"{self.name}: srp_area_m2 must be in (0, 1e4] -- if your intended value is outside "
                  "this range, check for a units mixup (e.g. cm^2 instead of m^2)")
        try:
            self.orbit.validate()
        except ScenarioValidationError as exc:  # name the spacecraft: the orbit's own messages cannot
            raise ScenarioValidationError(f"{self.name}: orbit: {exc}") from None

        _require(self.fsw_mode is None or self.fsw_mode in SUPPORTED_FSW_MODES,
                  f"{self.name}: fsw_mode {self.fsw_mode!r} must be None or one of {SUPPORTED_FSW_MODES}")
        if self.fsw_mode == "locationPointing":
            has_gs = bool(self.fsw_params.get("target_ground_station"))
            has_body = bool(self.fsw_params.get("target_body"))
            _require(has_gs != has_body,  # xor: exactly one target
                      f"{self.name}: fsw_mode 'locationPointing' needs exactly one of "
                      "fsw_params['target_ground_station'] or fsw_params['target_body']")
        if self.fsw_mode == "sunSafePoint" and self.fsw_params.get("use_css_estimation"):
            _require(any(s.kind == "coarse_sun_sensor" for s in self.sensors),
                      f"{self.name}: fsw_params['use_css_estimation'] is set but this spacecraft has no "
                      "'coarse_sun_sensor' sensors to estimate sun-heading from")
        if self.comms_pointing is not None:
            _require(self.fsw_mode is None,
                      f"{self.name}: comms_pointing and fsw_mode cannot both be set -- comms_pointing "
                      "already builds its own Sun-pointing/ground-station-pointing guidance chains "
                      f"internally (got fsw_mode={self.fsw_mode!r})")
            # Comms pointing drives an idealised torque, not actuators; with
            # actuators the run failed asking for fsw_mode, which this
            # check above forbids (audit M16).
            _require(not self.actuators,
                      f"{self.name}: comms_pointing commands an idealised control torque and cannot drive "
                      "actuators -- remove the actuators from this spacecraft, or use an fsw_mode instead")

        sensor_names = [s.name for s in self.sensors]
        _require(len(sensor_names) == len(set(sensor_names)),
                  f"{self.name}: sensor names must be unique, got {sensor_names}")
        for sensor in self.sensors:
            _require(bool(sensor.kind) and bool(sensor.name), f"{self.name}: every sensor needs kind and name")
            _require(name_error("sensor", sensor.name) is None, f"{self.name}: {name_error('sensor', sensor.name)}")
            _require(sensor.kind in SUPPORTED_SENSOR_KINDS,
                      f"{self.name}: sensor {sensor.name!r} kind {sensor.kind!r} must be one of "
                      f"{SUPPORTED_SENSOR_KINDS}")
            if sensor.kind == "coarse_sun_sensor":
                nHat_B = sensor.params.get("nHat_B")
                _require(nHat_B is not None and _is_direction_vector(nHat_B),
                          f"{self.name}: coarse_sun_sensor {sensor.name!r} needs params['nHat_B'] "
                          "as a non-zero, finite 3-element body-frame boresight unit vector")
            if sensor.kind == "thermal":
                nHat_B = sensor.params.get("nHat_B")
                _require(nHat_B is not None and _is_direction_vector(nHat_B),
                          f"{self.name}: thermal sensor {sensor.name!r} needs params['nHat_B'] "
                          "as a non-zero, finite 3-element body-frame face-normal unit vector")
                # Confirmed directly against sensorThermal.cpp's own Reset():
                # a non-positive sensorArea/sensorMass/sensorSpecificHeat, or
                # an absorptivity/emissivity outside (0, 1], each hard-exits
                # the whole process via bskLogger.bskError (not a catchable
                # exception) -- area/absorptivity/emissivity have no sane
                # Basilisk-side default (constructor sets them to -1)
                # precisely so a forgotten value is caught here instead of
                # silently building a sensor that can never radiate/absorb
                # anything. mass_kg/specific_heat_j_kg_k DO have real,
                # physically reasonable Basilisk defaults (1 kg, 890 J/kg/K,
                # aluminum) and so stay optional.
                area_m2 = sensor.params.get("area_m2")
                # Generous plausibility ceiling (docs/ux_audit.md, "units
                # enforced only by naming convention") on top of
                # sensorThermal's own required-positive check above --
                # 1000 m^2 is already far larger than any real
                # externally-mounted component's radiative surface.
                _require(area_m2 is not None and 0.0 < area_m2 <= 1000.0,
                          f"{self.name}: thermal sensor {sensor.name!r} needs params['area_m2'] in "
                          "(0, 1000] -- if your intended value is outside this range, check for a units "
                          "mixup (e.g. cm^2 instead of m^2)")
                mass_kg = sensor.params.get("mass_kg")
                if mass_kg is not None:
                    _require(0.0 < mass_kg <= 10000.0,
                              f"{self.name}: thermal sensor {sensor.name!r} params['mass_kg'] must be in "
                              "(0, 10000] if set -- if your intended value is outside this range, check "
                              "for a units mixup (e.g. g instead of kg)")
                absorptivity = sensor.params.get("absorptivity")
                _require(absorptivity is not None and 0.0 < absorptivity <= 1.0,
                          f"{self.name}: thermal sensor {sensor.name!r} needs params['absorptivity'] in (0, 1]")
                emissivity = sensor.params.get("emissivity")
                _require(emissivity is not None and 0.0 < emissivity <= 1.0,
                          f"{self.name}: thermal sensor {sensor.name!r} needs params['emissivity'] in (0, 1]")
                measurement_fault_mode = sensor.params.get("measurement_fault_mode", "none")
                _THERMAL_FAULT_MODES = ("none", "stuck_current", "stuck_value", "spiking")
                _require(measurement_fault_mode in _THERMAL_FAULT_MODES,
                          f"{self.name}: thermal sensor {sensor.name!r} has an unrecognized "
                          f"params['measurement_fault_mode'] {measurement_fault_mode!r} -- must be one of "
                          f"{_THERMAL_FAULT_MODES}")

        if self.geo_station_keeping is not None:
            self.geo_station_keeping.validate(self.name)
            _require(self.station_keeping is None and self.phasing_keeping is None,
                      f"{self.name}: geo_station_keeping replaces station_keeping and phasing_keeping -- "
                      "set only one of them")
        facet_names = [f.name for f in self.facets]
        _require(len(facet_names) == len(set(facet_names)),
                  f"{self.name}: facet names must be unique, got {facet_names}")
        for facet in self.facets:
            facet.validate(self.name)
        actuator_names = [a.name for a in self.actuators]
        _require(len(actuator_names) == len(set(actuator_names)),
                  f"{self.name}: actuator names must be unique, got {actuator_names}")
        for actuator in self.actuators:
            _require(bool(actuator.kind) and bool(actuator.name), f"{self.name}: every actuator needs kind and name")
            _require(name_error("actuator", actuator.name) is None,
                     f"{self.name}: {name_error('actuator', actuator.name)}")
            _require(actuator.kind in SUPPORTED_ACTUATOR_KINDS,
                      f"{self.name}: actuator {actuator.name!r} kind {actuator.kind!r} must be one of "
                      f"{SUPPORTED_ACTUATOR_KINDS}")
            if actuator.kind == "reaction_wheel":
                gsHat_B = actuator.params.get("gsHat_B")
                _require(gsHat_B is not None and _is_direction_vector(gsHat_B),
                          f"{self.name}: reaction_wheel {actuator.name!r} needs params['gsHat_B'] "
                          "as a non-zero, finite 3-element body-frame spin-axis unit vector")
                rw_errors = reaction_wheel_param_errors(f"{self.name}: reaction_wheel {actuator.name!r}", actuator.params)
                _require(not rw_errors, "; ".join(rw_errors))
                rw_type = actuator.params.get("rw_type", "custom")
                if rw_type == "custom":
                    # Confirmed directly against simIncludeRW.py's rwFactory.create(): the
                    # "custom" type's own method (unlike every named hardware type, e.g.
                    # "Honeywell_HR16") does nothing -- it relies entirely on these two
                    # kwargs. Missing either one makes rwFactory.create() call exit(1)
                    # directly (not a raised exception) -- which kills the whole
                    # SpaceMissionStudio process with no traceback, not just this one
                    # simulation run -- so this schema requires them explicitly instead
                    # of ever reaching that call with a bare rw_type="custom".
                    has_u_max_guard = (actuator.params.get("u_max") is not None
                                       or actuator.params.get("useMaxTorque") is False)
                    _require(has_u_max_guard,
                              f"{self.name}: reaction_wheel {actuator.name!r} uses rw_type='custom' (the "
                              "default) but has no params['u_max'] [N*m] -- rwFactory.create() hard-exits "
                              "the whole process (not a catchable error) on a non-positive u_max for a "
                              "default-saturating custom wheel; set params['u_max'], set "
                              "params['useMaxTorque']=False, or use a named params['rw_type'] (e.g. "
                              "'Honeywell_HR16') with its own built-in default instead")
                    has_inertia = (actuator.params.get("Js") is not None
                                   or (actuator.params.get("Omega_max") is not None
                                       and actuator.params.get("maxMomentum") is not None))
                    _require(has_inertia,
                              f"{self.name}: reaction_wheel {actuator.name!r} uses rw_type='custom' (the "
                              "default) but has no params['Js'] [kg*m^2] (spin-axis inertia) and no "
                              "params['Omega_max']+params['maxMomentum'] pair to derive it from -- "
                              "rwFactory.create() cannot build this wheel's inertia without one of those; "
                              "set one, or use a named params['rw_type'] with its own built-in default")
                    # Confirmed directly against simIncludeRW.py: giving Js
                    # AND the Omega_max+maxMomentum pair together is a
                    # SEPARATE exit(1) hard-crash (rwFactory.create() builds
                    # the wheel's inertia exactly one way, never both) --
                    # found by exactly this combination in a real, already
                    # -shipped params dict (engine.spacecraft_templates.py's
                    # _RW_EXAMPLE_PARAMS, fixed alongside this check).
                    _require(not (actuator.params.get("Js") is not None
                                  and actuator.params.get("Omega_max") is not None
                                  and actuator.params.get("maxMomentum") is not None),
                              f"{self.name}: reaction_wheel {actuator.name!r} uses rw_type='custom' (the "
                              "default) with params['Js'] AND both params['Omega_max']/params['maxMomentum'] "
                              "set -- rwFactory.create() hard-exits the whole process because it builds this "
                              "wheel's inertia exactly one way, never both; remove params['Js'] (let it be "
                              "derived from Omega_max/maxMomentum) or remove the Omega_max/maxMomentum pair")
                options = NAMED_RW_MAX_MOMENTUM_OPTIONS.get(rw_type)
                if options is not None:
                    max_momentum = actuator.params.get("maxMomentum")
                    _require(isinstance(max_momentum, (int, float)) and float(max_momentum) in options,
                              f"{self.name}: reaction_wheel {actuator.name!r} is a {rw_type}, which Basilisk "
                              f"builds only with params['maxMomentum'] set to one of {options} N*m*s (got "
                              f"{max_momentum!r}); for another size, use rw_type 'custom' with maxMomentum, "
                              "Omega_max and u_max")
                # Optional motor-thermal model (motorThermal.MotorThermal,
                # see engine.fsw.build_reaction_wheel_motor_thermal) -- an
                # all-or-nothing group, confirmed directly against
                # motorThermal.cpp's own Reset(): currentTemperature at or
                # below absolute zero (its constructor default, -273.15),
                # a non-positive ambientThermalResistance/motorHeatCapacity
                # (both default to -1.0), or an efficiency outside the
                # OPEN interval (0, 1) -- note 1.0 itself is rejected, not
                # just values above it; its own constructor default is
                # exactly 1.0, which would otherwise hard-exit the whole
                # process the moment ANY motor-thermal field was set -- all
                # hard-exit the whole process via bskLogger.bskError (not a
                # catchable exception), so every field in this group is
                # required together the moment any one of them is set,
                # rather than ever reaching Basilisk with a partially
                # -configured motor-thermal model.
                _MOTOR_THERMAL_KEYS = (
                    "motor_thermal_initial_temp_c", "motor_thermal_efficiency",
                    "motor_thermal_ambient_resistance_w_c", "motor_thermal_heat_capacity_j_c",
                )
                if any(key in actuator.params for key in _MOTOR_THERMAL_KEYS):
                    missing = [key for key in _MOTOR_THERMAL_KEYS if key not in actuator.params]
                    _require(not missing,
                              f"{self.name}: reaction_wheel {actuator.name!r} has some but not all of "
                              f"{_MOTOR_THERMAL_KEYS} set -- motorThermal.MotorThermal hard-exits the whole "
                              f"process on an unset field in this group; missing {missing}")
                    _require(_is_finite_number(actuator.params["motor_thermal_initial_temp_c"])
                             and actuator.params["motor_thermal_initial_temp_c"] > -273.15,
                             f"{self.name}: reaction_wheel {actuator.name!r} needs "
                             "params['motor_thermal_initial_temp_c'] above absolute zero (-273.15 C)")
                    efficiency = actuator.params["motor_thermal_efficiency"]
                    _require(0.0 < efficiency < 1.0,
                              f"{self.name}: reaction_wheel {actuator.name!r} needs "
                              "0 < params['motor_thermal_efficiency'] < 1 (1.0 itself is rejected by "
                              "motorThermal.MotorThermal, which models it as a real inefficiency)")
                    _require(actuator.params["motor_thermal_ambient_resistance_w_c"] > 0,
                              f"{self.name}: reaction_wheel {actuator.name!r} needs "
                              "params['motor_thermal_ambient_resistance_w_c'] > 0")
                    _require(actuator.params["motor_thermal_heat_capacity_j_c"] > 0,
                              f"{self.name}: reaction_wheel {actuator.name!r} needs "
                              "params['motor_thermal_heat_capacity_j_c'] > 0")
            if actuator.kind == "thruster":
                r_B = actuator.params.get("r_B")
                _require(r_B is not None and len(r_B) == 3,
                          f"{self.name}: thruster {actuator.name!r} needs params['r_B'] as a 3-element "
                          "body-frame location [m]")
                tHat_B = actuator.params.get("tHat_B")
                _require(tHat_B is not None and len(tHat_B) == 3,
                          f"{self.name}: thruster {actuator.name!r} needs params['tHat_B'] as a 3-element "
                          "body-frame thrust-direction unit vector [-]")
                _require(actuator.params.get("MaxThrust") is not None,
                          f"{self.name}: thruster {actuator.name!r} needs params['MaxThrust'] [N] -- "
                          "simIncludeThruster.thrusterFactory()'s own default (0.2 N) is easy to mistake "
                          "for a wiring bug rather than a deliberately tiny thruster, so this schema "
                          "requires it explicitly rather than silently falling back to it")
                thruster_errors = thruster_param_errors(f"{self.name}: thruster {actuator.name!r}", actuator.params)
                _require(not thruster_errors, "; ".join(thruster_errors))
            if actuator.kind == "magnetic_torque_rod":
                gtHat_B = actuator.params.get("gtHat_B")
                _require(gtHat_B is not None and _is_direction_vector(gtHat_B),
                          f"{self.name}: magnetic_torque_rod {actuator.name!r} needs params['gtHat_B'] as a "
                          "non-zero, finite 3-element body-frame dipole-axis unit vector [-]")
                _require(_is_finite_number(actuator.params.get("max_dipole_a_m2"))
                         and actuator.params["max_dipole_a_m2"] > 0,
                          f"{self.name}: magnetic_torque_rod {actuator.name!r} needs params['max_dipole_a_m2'] "
                          "> 0 [A*m^2] (maximum commandable dipole magnitude)")

        # engine.fsw/engine.service build exactly one PRIMARY control-torque
        # path per spacecraft (reaction wheels via rwMotorTorque, OR
        # thrusters via thrForceMapping/thrFiringSchmitt) -- mixing both for
        # primary control would need a control-allocation module (e.g.
        # Basilisk's torqueScheduler) this app does not build yet. The one
        # exception is momentum_dumping (below), where thrusters have a
        # DIFFERENT, non-competing job (bleeding off RW momentum, not
        # attitude control) -- so the mix is required there, not rejected.
        actuator_kinds_present = {a.kind for a in self.actuators}
        if (self.momentum_dumping is None
                and "reaction_wheel" in actuator_kinds_present and "thruster" in actuator_kinds_present):
            _require(False,
                      f"{self.name}: actuators mix 'reaction_wheel' and 'thruster' kinds -- only one control "
                      "-torque actuator type per spacecraft is simulated (unless momentum_dumping is set, which "
                      "requires exactly this mix); remove one kind's actuators, or set momentum_dumping")
        # "magnetic_torque_rod" has no PRIMARY attitude-control role in this
        # app at all (no B-dot-style detumble/pointing controller is built
        # -- see engine.fsw's module docstring) -- its only simulated job is
        # magnetic_momentum_management's continuous RW desaturation, so a
        # magnetic_torque_rod actuator with that config unset would simply
        # never receive a command.
        if "magnetic_torque_rod" in actuator_kinds_present:
            _require(self.magnetic_momentum_management is not None,
                      f"{self.name}: 'magnetic_torque_rod' actuators need magnetic_momentum_management set "
                      "(no other role for them is simulated); set it, or remove the magnetic_torque_rod "
                      "actuator(s)")

        if self.power is not None:
            self.power.validate(self.name)
        if self.rf_link is not None:
            self.rf_link.validate(self.name)
        if self.rf_link is not None and self.rf_link.antenna_pattern != "fixed":
            _require(self.rf_link.antenna_boresight_b is not None or self.comms_pointing is not None,
                      f"{self.name}: rf_link.antenna_pattern {self.rf_link.antenna_pattern!r} needs "
                      "rf_link.antenna_boresight_b (or comms_pointing's): the gain toward the station depends "
                      "on where the antenna points")
        for array in self.solar_arrays:
            array.validate(self.name)
        array_names = [array.name for array in self.solar_arrays]
        _require(len(set(array_names)) == len(array_names), f"{self.name}: solar array names must be unique")
        _require(sum(array.mass_kg for array in self.solar_arrays) < self.dry_mass_kg,
                  f"{self.name}: the solar arrays weigh as much as dry_mass_kg or more -- dry_mass_kg is the "
                  "whole dry spacecraft, arrays included")
        if self.data_handling is not None:
            self.data_handling.validate(self.name)
            _require(self.power is not None or not self.data_handling.needs_power,
                      f"{self.name}: data_handling draws power (an instrument's power_w or transmitter_power_w "
                      "> 0) but this spacecraft has no power budget -- add one, or set those to 0")
        if self.comms_pointing is not None:
            self.comms_pointing.validate(self.name)
            _require(self.power is not None or self.comms_pointing.comms_power_w == 0.0,
                      f"{self.name}: comms_pointing.comms_power_w > 0 needs this spacecraft's power "
                      "also set (nothing to draw that power from otherwise)")
        if self.station_keeping is not None:
            self.station_keeping.validate(self.name)
        if self.phasing_keeping is not None:
            _require(self.station_keeping is not None,
                      f"{self.name}: phasing_keeping requires station_keeping to also be set on this spacecraft "
                      "-- they share one physical thruster/propellant tank (see PhasingKeepingConfig's docstring)")
            self.phasing_keeping.validate(self.name)
        if self.roe_formation is not None:
            _require(self.station_keeping is not None,
                      f"{self.name}: roe_formation requires station_keeping to also be set on this spacecraft "
                      "-- the ROE controller fires its thruster and uses its tank")
            _require(self.phasing_keeping is None,
                      f"{self.name}: roe_formation and phasing_keeping both control the same formation -- "
                      "keep one of them")
            self.roe_formation.validate(self.name)
        if self.optical_navigation is not None:
            self.optical_navigation.validate(self.name)
        if self.landmark_navigation is not None:
            self.landmark_navigation.validate(self.name)
        if self.constant_thrust is not None:
            self.constant_thrust.validate(self.name)
        if self.momentum_dumping is not None:
            _require("reaction_wheel" in actuator_kinds_present,
                      f"{self.name}: momentum_dumping needs at least one 'reaction_wheel' actuator (momentum to "
                      "dump) on this spacecraft")
            _require("thruster" in actuator_kinds_present,
                      f"{self.name}: momentum_dumping needs at least one 'thruster' actuator (desaturation "
                      "hardware) on this spacecraft")
            # engine.service builds BOTH desaturation control paths with no
            # runtime guard against this -- two independent controllers would
            # silently fight over the same reaction wheels (confirmed by
            # direct audit: momentum_dumping and magnetic_momentum_management
            # are each handled in their own independent `if` block, not
            # elif). This schema check is what engine.service's own comment
            # ("Scenario.validate() guarantees these are mutually exclusive")
            # already assumed existed; it didn't until now.
            _require(self.magnetic_momentum_management is None,
                      f"{self.name}: momentum_dumping and magnetic_momentum_management are mutually exclusive "
                      "RW-desaturation strategies -- set at most one (both would independently command the "
                      "same reaction wheels)")
            self.momentum_dumping.validate(self.name)
        if self.magnetic_momentum_management is not None:
            _require("reaction_wheel" in actuator_kinds_present,
                      f"{self.name}: magnetic_momentum_management needs at least one 'reaction_wheel' actuator "
                      "(momentum to manage) on this spacecraft")
            _require("magnetic_torque_rod" in actuator_kinds_present,
                      f"{self.name}: magnetic_momentum_management needs at least one 'magnetic_torque_rod' "
                      "actuator (desaturation hardware) on this spacecraft")
            num_reaction_wheels = sum(1 for a in self.actuators if a.kind == "reaction_wheel")
            self.magnetic_momentum_management.validate(self.name, num_reaction_wheels)
        if self.navigation_error is not None:
            _require(self.fsw_mode is not None or self.comms_pointing is not None,
                     f"{self.name}: navigation_error needs attitude flight software (a pointing mode or comms "
                     "pointing): only then is there navigation to perturb")
            self.navigation_error.validate(self.name)
        if self.propellant_budget is not None:
            self.propellant_budget.validate(self.name)
        if self.fuel_tank is not None:
            _require("thruster" in actuator_kinds_present,
                      f"{self.name}: fuel_tank needs at least one 'thruster' actuator on this spacecraft to "
                      "draw propellant from")
            self.fuel_tank.validate(self.name)

        if self.vizard_model_path is not None:
            _require(bool(self.vizard_model_path.strip()), f"{self.name}: vizard_model_path must not be blank")
        _require(len(self.vizard_model_offset_m) == 3, f"{self.name}: vizard_model_offset_m must have 3 elements")
        _require(len(self.vizard_model_rotation_deg) == 3,
                  f"{self.name}: vizard_model_rotation_deg must have 3 elements")
        _require(len(self.vizard_model_scale) == 3, f"{self.name}: vizard_model_scale must have 3 elements")


@dataclass
class GravityConfig:
    central_body: str = "earth"
    central_body_degree: int = 0  # 0 == point-mass only
    third_body_perturbers: list = field(default_factory=list)  # e.g. ["sun", "moon"]
    # A small body's gravity from its shape model at constant density
    # (Basilisk's polyhedralGravityModel) instead of a point mass.
    polyhedral_gravity: bool = False
    # Sunlight the central body reflects onto the coarse sun sensors
    # (Basilisk's albedo module with the body's measured albedo map).
    albedo: bool = False

    def validate(self) -> None:
        _require(self.central_body in SUPPORTED_CENTRAL_BODIES + SMALL_BODY_CENTRAL_BODIES,
                  _body_problem("gravity.central_body", self.central_body, small_bodies=True))
        _require(isinstance(self.polyhedral_gravity, bool), "gravity.polyhedral_gravity must be true or false")
        _require(not self.polyhedral_gravity or self.central_body in SMALL_BODY_CENTRAL_BODIES,
                  f"gravity.polyhedral_gravity needs a small body with a shape model as the central body "
                  f"({', '.join(SMALL_BODY_CENTRAL_BODIES)}), not {self.central_body!r}")
        _require(isinstance(self.albedo, bool), "gravity.albedo must be true or false")
        _require(not self.albedo or self.central_body in ALBEDO_MAPS,
                  f"gravity.albedo needs a central body with an albedo map ({', '.join(ALBEDO_MAPS)}), "
                  f"not {self.central_body!r}")
        _require(self.central_body_degree >= 0, "gravity.central_body_degree must be >= 0")
        # The fields engine.gravity_field loads; checked here too so that
        # `spacemissionstudio validate` and Save refuse what a run would.
        field = GRAVITY_FIELDS.get(self.central_body)
        _require(self.central_body_degree == 0 or field is not None,
                  f"gravity.central_body_degree > 0 (spherical-harmonics gravity) needs a central body with a "
                  f"gravity field ({', '.join(GRAVITY_FIELDS)}), not {self.central_body!r} -- set "
                  f"central_body_degree = 0 (point mass)")
        if field is not None:
            _require(self.central_body_degree <= field[1],
                     f"gravity.central_body_degree must be <= {field[1]} (the {field[0]} field's maximum)")
        for name in self.third_body_perturbers:
            _require(name in SUPPORTED_CENTRAL_BODIES,
                      _body_problem("gravity.third_body_perturbers entry", name))


@dataclass
class GroundStationConfig:
    """A ground station. Coordinates are geodetic on the WGS-84 ellipsoid
    for Earth (planetocentric on a sphere for other bodies); longitude is
    east positive; see :mod:`engine.geodesy` (ECSS-E-ST-10-09C 5.4.6a)."""

    name: str
    latitude_deg: float  # [deg] geodetic latitude, north positive
    longitude_deg: float  # [deg] east positive
    altitude_m: float = 0.0  # [m] height above the ellipsoid
    min_elevation_deg: float = 10.0
    # Receive-side link-budget parameters -- only meaningful for a
    # spacecraft that also has RFLinkConfig set (see engine.link_budget);
    # harmless, unused defaults otherwise.
    rx_antenna_gain_dbi: float = 0.0  # [dBi] ground station receive antenna gain
    system_noise_temp_k: float = 290.0  # [K] ground receiver system noise temperature

    def validate(self) -> None:
        _require(name_error("ground station", self.name) is None, name_error("ground station", self.name) or "")
        _require(-90.0 <= self.latitude_deg <= 90.0, f"{self.name}: latitude_deg must be in [-90, 90]")
        _require(-180.0 <= self.longitude_deg <= 180.0, f"{self.name}: longitude_deg must be in [-180, 180]")
        _require(0.0 <= self.min_elevation_deg < 90.0, f"{self.name}: min_elevation_deg must be in [0, 90)")
        _require(self.system_noise_temp_k > 0, f"{self.name}: system_noise_temp_k must be > 0")


#: Central body -> (gravity field, its maximum degree and order); the files are
#: Basilisk's support data (engine.gravity_field).
GRAVITY_FIELDS = {"earth": ("GGM03S", 180), "mars barycenter": ("GGM2B", 80)}
MAX_GRAVITY_DEGREE = max(degree for _name, degree in GRAVITY_FIELDS.values())
SUPPORTED_SPACE_WEATHER_SOURCES = ("bundled", "local_file")
SUPPORTED_FORECAST_PERCENTILES = (95.0, 50.0, 5.0)  # [%] MSFC's published columns


@dataclass
class SpaceWeatherConfig:
    """See engine/spaceweather.py and engine/service.py. Real data only
    (user requirement): ``source`` is ``"bundled"`` (the default:
    CelesTrak's SW-All file shipped with the app -- observed since 1957,
    a 45-day forecast, NOAA's monthly F10.7 forecast to 2041 -- or a newer
    one the startup prompt downloaded) or ``"local_file"`` (your own
    CelesTrak ``.txt``/``.csv`` file, used only when
    ``local_file_path`` is set). SpaceMissionStudio never accesses the
    network at runtime. The ``"synthetic"`` profile of schema versions
    1-2 was removed; ``schema.migrations`` moves old files to
    ``"bundled"``.

    ``atmosphere_model`` selects which Basilisk atmosphere-density model
    ``engine.service`` builds for ``enable_drag`` spacecraft:
    ``"nrlmsise00"`` (the original, only model this project used to wire
    up -- needs the ``source``/``forecast_percentile`` space-weather machinery
    below) or ``"exponential"`` (Basilisk's ``ExponentialAtmosphere``, a
    simple per-planet scale-height model that ignores ``source``/
    ``forecast_percentile``/``local_file_path`` entirely -- no F10.7/Ap
    dependence at all). ``engine.service`` configures it with Basilisk's
    own ``simSetPlanetEnvironment.exponentialAtmosphere()`` helper (the
    same sea-level Earth baseDensity/scaleHeight a real shipped Basilisk
    example, ``examples/scenarioDragDeorbit.py``, uses for its own
    exponential-model deorbit case -- not hand-picked constants). Confirmed
    directly against real Basilisk (a standalone density-recorder run, not
    guessed) that a single sea-level exponential decay under-predicts
    density at typical LEO altitudes by many orders of magnitude compared
    to NRLMSISE-00 -- an inherent limitation of this simple model, not a
    wiring bug: pick ``"exponential"`` for speed/simplicity (e.g. a quick
    order-of-magnitude check with no space-weather dependency), never for
    an accurate drag/decay estimate, which needs ``"nrlmsise00"``. Real
    user question: "why can't I select the
    atmospheric drag model, other tools let me choose Jacchia-Roberts or
    NRLMSISE-00" -- Basilisk (checked directly against its own
    ``src/simulation/environment/`` tree, not assumed) ships exactly
    three atmosphere models: ``MsisAtmosphere`` (NRLMSISE-00),
    ``ExponentialAtmosphere``, and ``TabularAtmosphere`` (a user-supplied
    altitude/density table, not wired up here -- would need a new file
    -upload schema/GUI concept of its own, out of scope for this round).
    There is no Jacchia-Roberts model in Basilisk at all, so that specific
    option genuinely cannot be offered here.

    ``forecast_percentile`` sets how active the predicted Sun is: past
    the observations, every day uses NASA MSFC's prediction at its 95th
    (conservative: ESA AD10 Sec. 5.9 for operations), 50th (nominal; AD10
    for end of life) or 5th percentile. Observed days are always the
    observations. (Schema v3 also had a "conservative" ``activity_level``
    holding F10.7/Ap at a percentile of the historical record;
    ``schema.migrations`` turns it into the 95th percentile.)
    """

    source: str = "bundled"  # "bundled" | "local_file"
    local_file_path: str | None = None
    cache_dir: str | None = None  # defaults to engine.spaceweather's own cache dir when None
    atmosphere_model: str = "nrlmsise00"  # "nrlmsise00" | "exponential"
    # [%] which of MSFC's predicted percentiles drives the days past the
    # observations: 95 conservative (ESA AD10 Sec. 5.9, operations), 50
    # nominal (AD10, end of life), 5 low
    forecast_percentile: float = 50.0
    msfc_file_path: str | None = None  # your own MSFC prediction table; None = the one shipped with the app

    def validate(self) -> None:
        _require(self.source in SUPPORTED_SPACE_WEATHER_SOURCES,
                  f"space_weather.source {self.source!r} must be one of {SUPPORTED_SPACE_WEATHER_SOURCES}")
        if self.source == "local_file":
            _require(bool(self.local_file_path),
                      "space_weather.source is 'local_file' but local_file_path was not set")
        _require(self.atmosphere_model in ("nrlmsise00", "exponential"),
                  f"space_weather.atmosphere_model {self.atmosphere_model!r} must be 'nrlmsise00' or 'exponential'")
        # Text such as "95" gave a bare ValueError (audit L29).
        _require(_is_finite_number(self.forecast_percentile)
                  and float(self.forecast_percentile) in SUPPORTED_FORECAST_PERCENTILES,
                  f"space_weather.forecast_percentile {self.forecast_percentile!r} must be one of "
                  f"{SUPPORTED_FORECAST_PERCENTILES} (MSFC's published percentiles)")


@dataclass
class DispersionConfig:
    """One dispersed quantity for one spacecraft in a Monte Carlo batch --
    see :data:`DISPERSION_QUANTITIES`/:data:`DISPERSION_KINDS_BY_QUANTITY`
    for what's supported and ``engine/monte_carlo.py`` for how each pairing
    maps onto a ``Basilisk.utilities.MonteCarlo.Dispersions`` class.
    """

    spacecraft: str  # must match a SpacecraftConfig.name in this scenario
    quantity: str  # one of DISPERSION_QUANTITIES
    kind: str  # one of DISPERSION_KINDS_BY_QUANTITY[quantity]
    # [lo, hi]; required for "uniform"/"uniform_euler_mrp". In the quantity's
    # unit: kg, rad (Euler angles), [-] (coefficients), deg/s added to the
    # nominal rate ("angular_rate_bn_b"); for "inertia_kg_m2" an optional
    # clip [kg*m^2] on each diagonal offset.
    bounds: list | None = None  # [lo, hi] in the quantity's unit (User Manual section 10)
    mean: float | None = None  # required for "normal" on dry_mass_kg, drag_coeff, srp_coeff
    # required for "normal": kg, [-], kg*m^2 (each diagonal element of the
    # inertia), deg/s (each axis of the initial rate)
    std_deviation: float | None = None  # 1-sigma in the quantity's unit (User Manual section 10)
    # "orbit_elements": {key in ORBIT_ELEMENT_SPREAD_KEYS: spread}, in km,
    # [-] or deg; elements left out are not dispersed
    element_spread: dict | None = None  # "orbit_elements": {element key: spread}
    angle_std_deg: float | None = None  # [deg] "inertia_kg_m2": 1-sigma rotation that mixes in off-diagonal terms

    def validate(self) -> None:
        where = f"dispersion on {self.spacecraft}.{self.quantity}"
        _require(bool(self.spacecraft), "dispersion.spacecraft must not be empty")
        _require(self.quantity in DISPERSION_QUANTITIES,
                  f"dispersion.quantity {self.quantity!r} must be one of {DISPERSION_QUANTITIES}")
        allowed_kinds = DISPERSION_KINDS_BY_QUANTITY.get(self.quantity, ())
        _require(self.kind in allowed_kinds,
                  f"dispersion.kind {self.kind!r} for quantity {self.quantity!r} must be one of {allowed_kinds}")
        if self.quantity == "orbit_elements":
            spread = self.element_spread
            _require(isinstance(spread, dict) and spread,
                      f"{where}: needs element_spread, e.g. {{'semi_major_axis_km': 0.5}}")
            for key, value in spread.items():
                _require(key in ORBIT_ELEMENT_SPREAD_KEYS,
                          f"{where}: element_spread key {key!r} must be one of {ORBIT_ELEMENT_SPREAD_KEYS}")
                _require(_is_finite_number(value) and value >= 0,
                          f"{where}: element_spread[{key!r}] must be a finite number >= 0")
            return
        if self.kind in ("uniform", "uniform_euler_mrp"):
            _require(isinstance(self.bounds, (list, tuple)) and len(self.bounds) == 2,
                      f"{where}: kind {self.kind!r} needs bounds as a 2-element [lo, hi] list")
        if self.bounds is not None:
            # Reversed or non-numeric bounds reached Basilisk's sampler
            # unchecked (audit L29).
            _require(isinstance(self.bounds, (list, tuple)) and len(self.bounds) == 2
                      and all(_is_finite_number(value) for value in self.bounds),
                      f"{where}: bounds must be two finite numbers [lo, hi], got {self.bounds!r}")
            _require(self.bounds[0] <= self.bounds[1],
                      f"{where}: bounds [lo, hi] must have lo <= hi, got {self.bounds!r}")
        if self.kind == "normal":
            if self.quantity in SPREAD_ONLY_DISPERSION_QUANTITIES:
                _require(self.std_deviation is not None and _is_finite_number(self.std_deviation)
                          and self.std_deviation >= 0, f"{where}: kind 'normal' needs std_deviation >= 0")
            else:
                _require(self.mean is not None and self.std_deviation is not None,
                          f"{where}: kind 'normal' needs mean and std_deviation")
                _require(_is_finite_number(self.mean), f"{where}: mean must be a finite number")
                _require(_is_finite_number(self.std_deviation) and self.std_deviation >= 0,
                          f"{where}: std_deviation must be a finite number >= 0")
        if self.quantity == "inertia_kg_m2":
            _require(self.bounds is None or len(self.bounds) == 2,
                      f"{where}: bounds, if given, must be a 2-element [lo, hi] list")
            _require(self.angle_std_deg is None or (_is_finite_number(self.angle_std_deg)
                                                    and self.angle_std_deg >= 0),
                      f"{where}: angle_std_deg must be a finite number >= 0")


# A shared scenario must not start a billion runs or a million processes
# (audit R4): validate refuses more. The run itself uses at most one
# process per CPU (usable_thread_count).
MAX_MONTE_CARLO_RUNS = 100_000
MAX_MONTE_CARLO_THREADS = 256


def usable_thread_count(requested: int) -> int:
    """Processes a Monte Carlo batch runs in: ``requested``, but at most
    one per CPU (audit R4: more only compete for the same cores)."""
    return max(1, min(requested, os.cpu_count() or 1))


@dataclass
class MonteCarloConfig:
    """Batch execution settings -- see ``engine/monte_carlo.py``.
    ``thread_count`` > 1 runs the batch in parallel processes
    (``Basilisk.utilities.MonteCarlo.Controller``'s ``multiprocessing.Pool``),
    exercised by the test suite against Basilisk 2.12.0; the default stays
    ``1``. Every run flies the scenario's Mission Sequence when it has one.
    """

    enabled: bool = False
    num_runs: int = 10
    thread_count: int = 1
    verbose: bool = False
    dispersions: list = field(default_factory=list)  # list[DispersionConfig]

    def validate(self) -> None:
        # A float or text count reached the batch unchecked (audit L29).
        for key in ("num_runs", "thread_count"):
            value = getattr(self, key)
            _require(isinstance(value, int) and not isinstance(value, bool),
                      f"monte_carlo.{key} must be a whole number, got {value!r}")
        _require(1 <= self.num_runs <= MAX_MONTE_CARLO_RUNS,
                 f"monte_carlo.num_runs must be between 1 and {MAX_MONTE_CARLO_RUNS}, got {self.num_runs}")
        _require(1 <= self.thread_count <= MAX_MONTE_CARLO_THREADS,
                 f"monte_carlo.thread_count must be between 1 and {MAX_MONTE_CARLO_THREADS}, "
                 f"got {self.thread_count}")
        for dispersion in self.dispersions:
            dispersion.validate()


# Matches the svIntegrator* classes this Basilisk checkout actually ships
# (src/simulation/dynamics/Integrators/) -- verified by directly listing
# that directory, not assumed. There is deliberately no "rk4" option: this
# checkout has no svIntegratorRK4 (only Euler/RK2 fixed-step and the
# RKF45/RKF78 adaptive pair), and fabricating one here would violate the
# "map every feature to a module Basilisk actually provides" requirement
# this whole project is built around.
SUPPORTED_INTEGRATORS = ("euler", "rk2", "rkf45", "rkf78")


@dataclass
class SimSettings:
    duration_days: float = 1.0
    dynamics_task_rate_s: float = 10.0
    integrator: str = "rkf78"  # see SUPPORTED_INTEGRATORS
    # [s] How often results are recorded; 0 = every dynamics step. Long
    # runs need this: a 5-year run at a 30 s step is ~5 million samples per
    # series. Controller burn flags record "fired since the last sample", so
    # short burns still show; positions, angles and access flags are
    # snapshots, so anything shorter than this (e.g. a ground-station
    # pass) can fall between two samples.
    record_interval_s: float = 0.0
    # The run's random seed. Every model with a random generator (sensor
    # noise, navigation error, faults) gets its own seed derived from this
    # one and its name (engine.seeds.assign_rng_seeds), so two sensors
    # never draw the same noise, and the same scenario gives the same run.
    # Change it for another realisation of the noise.
    seed: int = 0

    # NOTE: gravity-field degree/order lives on GravityConfig.central_body_degree,
    # not here -- an earlier draft of this schema had a second,
    # SimSettings.earth_grav_degree field that duplicated it, which meant
    # the two could disagree (one saying "point-mass", the other holding a
    # stale nonzero degree) with no validation catching it. Fixed before
    # anything (the GUI, saved scenario files) came to depend on the
    # redundant field -- there is deliberately only one place to set this now.

    # _MAX_SINGLE_RUN_DAYS: a real Basilisk platform limit, not a
    # stylistic choice. Basilisk's own nanoToSec() (C++,
    # src/architecture/utilities/macroDefinitions.h) converts simulated
    # nanoseconds to a double, which can only exactly represent integers up
    # to 2**53 (DBL_MANT_DIG) -- 9007199254740992 ns, ~104.25 days. Past
    # that it prints a stderr error on EVERY call and returns NaN, which
    # poisons every downstream time-dependent calculation for the rest of
    # the run -- confirmed directly: a 180-day test run hit this and became
    # severely degraded. 100.0 days keeps a safety margin under the cliff.
    # A longer duration (up to _MAX_DURATION_DAYS) runs as a chain of
    # shorter simulations -- see engine/long_run.py -- which mission
    # sequences and phasing keeping cannot do (Scenario.validate()).
    _MAX_SINGLE_RUN_DAYS = 100.0  # [day]
    _MAX_DURATION_DAYS = 3660.0  # [day] about 10 years

    def validate(self) -> None:
        _require(self.duration_days > 0, "sim_settings.duration_days must be > 0")
        _require(self.duration_days <= self._MAX_DURATION_DAYS,
                  f"sim_settings.duration_days must be <= {self._MAX_DURATION_DAYS:g} days (about 10 years)")
        # 1 ms, the editor's least: 1e-9 s validated and asked for 86 400 billion steps a day (audit R9).
        _require(self.dynamics_task_rate_s >= MIN_DYNAMICS_TASK_RATE_S,
                  f"sim_settings.dynamics_task_rate_s must be at least {MIN_DYNAMICS_TASK_RATE_S:g} s")
        _require(0.0 <= self.record_interval_s <= 86400.0,
                  "sim_settings.record_interval_s must be in [0, 86400] s (0 = every dynamics step)")
        _require(self.integrator in SUPPORTED_INTEGRATORS,
                  f"sim_settings.integrator {self.integrator!r} must be one of {SUPPORTED_INTEGRATORS}")
        _require(isinstance(self.seed, int) and not isinstance(self.seed, bool) and 0 <= self.seed < 2 ** 31,
                  "sim_settings.seed must be a whole number from 0 to 2147483647")


@dataclass
class FswExportRecord:
    """Where a spacecraft's flight software was last exported
    (``spacemissionstudio.fsw_export``): the folder, and the configuration
    hash it was exported with, so the GUI can say when the scenario's
    flight-software settings have changed since (a stale export).
    ``parts`` holds one short hash per setting group, to name what changed.
    The export folder's own ``manifest.json`` holds the full provenance."""

    spacecraft: str
    path: str  # the export folder, absolute or relative to the scenario file
    config_digest: str  # 64 hex digits (fsw_export.digest.fsw_config_digest)
    exported_utc: str = ""
    basilisk_revision: str = ""
    parts: dict = field(default_factory=dict)  # setting group -> 16 hex digits

    def validate(self) -> None:
        _require(bool(self.spacecraft), "fsw_exports[].spacecraft must not be empty")
        _require(bool(self.path), f"fsw_exports[{self.spacecraft}].path must not be empty")
        _require(isinstance(self.config_digest, str) and re.fullmatch(r"[0-9a-f]{64}", self.config_digest) is not None,
                 f"fsw_exports[{self.spacecraft}].config_digest must be 64 lower-case hex digits")
        _require(isinstance(self.parts, dict), f"fsw_exports[{self.spacecraft}].parts must be a mapping")


SUPPORTED_SIMULATION_MODES = ("full_attitude", "orbit_only")


@dataclass
class Scenario:
    name: str
    epoch_utc: str  # ISO 8601, e.g. "2030-01-01T00:00:00" -- single source of
    # truth for time; TAI/TT/ET are DERIVED (see engine/time_system.py), never
    # separately stored, so they cannot drift out of sync with epoch_utc.
    # Chosen up front (the GUI's scenario editor puts it at the top of the
    # form, "before starting with anything else" per the feature request
    # this responds to): "full_attitude" (the default, and everything this
    # schema always supported) simulates attitude/sensors/actuators/FSW/
    # power normally. "orbit_only" is a beginner-friendly, deliberately
    # STRICTER mode for pure orbit-propagation questions (delta-V budgets,
    # orbit lifetime, station-keeping cadence, ...) where attitude doesn't
    # matter and modeling it is only friction: no spacecraft may set
    # fsw_mode/sensors/actuators/power in this mode (Scenario.validate()
    # rejects it with a specific error naming the offending spacecraft and
    # field, same "don't let something look configured that isn't" honesty
    # as everywhere else in this schema) -- the spacecraft is simulated as
    # a cannonball with SpacecraftConfig.drag_area_m2/srp_area_m2 as its
    # average cross-section. station_keeping/phasing_keeping/
    # constant_thrust remain available in EITHER mode: none of them need
    # attitude knowledge (their thrust directions are prograde or
    # orbit-frame-relative, not a commanded body axis).
    simulation_mode: str = "full_attitude"
    gravity: GravityConfig = field(default_factory=GravityConfig)
    spacecraft: list = field(default_factory=list)  # list[SpacecraftConfig], >= 1 required
    ground_stations: list = field(default_factory=list)  # list[GroundStationConfig]
    space_weather: SpaceWeatherConfig = field(default_factory=SpaceWeatherConfig)
    sim_settings: SimSettings = field(default_factory=SimSettings)
    monte_carlo: MonteCarloConfig = field(default_factory=MonteCarloConfig)
    # Ordered "Mission Sequence" commands (Propagate/Maneuver/Assignment/
    # Report/If/While/ScriptBlock -- see schema.command.Command), walked in
    # order by engine.mission_engine. Empty (the default) for every
    # scenario written before this field existed, and for any scenario
    # that still just wants "propagate once for sim_settings.duration_days"
    # -- engine.service.SimulationService's existing run()/run_live()
    # behavior is completely unchanged and is still what an empty
    # mission_sequence means; engine.mission_engine is an ADDITIVE,
    # separate execution path only used when this is non-empty.
    mission_sequence: list = field(default_factory=list)  # list[Command]
    fsw_exports: list = field(default_factory=list)  # list[FswExportRecord], at most one per spacecraft
    description: str = ""
    schema_version: int = CURRENT_SCHEMA_VERSION

    def _validate_small_body(self) -> None:
        """Checks for a run around a small body (``SMALL_BODY_CENTRAL_BODIES``)."""
        body = self.gravity.central_body
        first, last = (datetime.fromisoformat(part) for part in SMALL_BODY_EPHEMERIS_SPAN[body])
        start = parse_epoch_utc(self.epoch_utc)
        if start.tzinfo is not None:
            start = start.astimezone(UTC).replace(tzinfo=None)
        end = start + timedelta(days=self.sim_settings.duration_days)
        _require(first <= start and end <= last,
                  f"gravity.central_body {body!r}: its ephemeris covers {first:%Y-%m-%d} to {last:%Y-%m-%d}; "
                  f"this run goes from {start:%Y-%m-%d} to {end:%Y-%m-%d}")
        _require(not self.ground_stations,
                  f"gravity.central_body {body!r}: ground stations are only for planets, remove them")

    def validate(self) -> None:
        _require(bool(self.name), "scenario.name must not be empty")
        try:
            parse_epoch_utc(self.epoch_utc)
        except ValueError as exc:
            raise ScenarioValidationError(
                f"scenario.epoch_utc {self.epoch_utc!r} is not a valid ISO 8601 datetime "
                f"(e.g. '2030-01-01T00:00:00'): {exc}"
            ) from exc
        _require(self.simulation_mode in SUPPORTED_SIMULATION_MODES,
                  f"scenario.simulation_mode {self.simulation_mode!r} must be one of {SUPPORTED_SIMULATION_MODES}")
        self.gravity.validate()
        _require(len(self.spacecraft) >= 1, "scenario needs at least one spacecraft")
        _require(len(self.spacecraft) <= MAX_SPACECRAFT,
                  f"scenario has {len(self.spacecraft)} spacecraft; at most {MAX_SPACECRAFT}")
        _require(len(self.description) <= MAX_DESCRIPTION_CHARS,
                  f"scenario.description is {len(self.description)} characters; at most {MAX_DESCRIPTION_CHARS}")
        names = [sc.name for sc in self.spacecraft]
        _require(len(names) == len(set(names)), f"spacecraft names must be unique, got {names}")
        # Two names that differ only in case overwrite each other's files on
        # Windows, and two that differ only in punctuation share one
        # Monte Carlo accessor (engine.monte_carlo._accessor_name).
        folded: dict = {}
        for name in names:
            key = re.sub(r"\W+", "_", name).casefold()
            _require(key not in folded, f"spacecraft names {folded.get(key)!r} and {name!r} differ only in case or "
                                        "punctuation; their output files would collide -- rename one")
            folded[key] = name
        for sc in self.spacecraft:
            sc.validate()
        for record in self.fsw_exports:
            record.validate()
        exported = [record.spacecraft for record in self.fsw_exports]
        _require(len(exported) == len(set(exported)),
                 f"fsw_exports lists a spacecraft more than once: {exported}")
        flexible = [sc.name for sc in self.spacecraft if sc.solar_arrays]
        _require(not flexible or self.sim_settings.integrator in ("rkf45", "rkf78"),
                  f"{flexible[0] if flexible else ''}: flexible solar arrays need an adaptive integrator "
                  f"(rkf45 or rkf78) -- with {self.sim_settings.integrator!r} a hinge oscillating faster than the "
                  "step diverges")
        if self.simulation_mode == "orbit_only":
            for sc in self.spacecraft:
                _require(not sc.solar_arrays,
                          f"{sc.name}: solar arrays are set but scenario.simulation_mode is 'orbit_only' -- their "
                          "flexing moves the attitude 'full_attitude' mode simulates, or remove them")
                _require(sc.fsw_mode is None,
                          f"{sc.name}: fsw_mode is set but scenario.simulation_mode is 'orbit_only' -- attitude "
                          "control needs 'full_attitude' mode, or remove fsw_mode from this spacecraft")
                _require(not sc.sensors,
                          f"{sc.name}: sensors are set but scenario.simulation_mode is 'orbit_only' -- sensors "
                          "need 'full_attitude' mode, or remove them from this spacecraft")
                _require(not sc.actuators,
                          f"{sc.name}: actuators are set but scenario.simulation_mode is 'orbit_only' -- "
                          "actuators need 'full_attitude' mode, or remove them from this spacecraft")
                _require(not sc.facets,
                          f"{sc.name}: facets are set but scenario.simulation_mode is 'orbit_only' -- their "
                          "drag and SRP depend on the attitude 'full_attitude' mode simulates, or remove them")
                _require(sc.power is None,
                          f"{sc.name}: power is set but scenario.simulation_mode is 'orbit_only' -- a real solar"
                          "-panel power budget needs the simulated attitude 'full_attitude' mode provides, or "
                          "remove power from this spacecraft")
                _require(sc.rf_link is None or sc.rf_link.antenna_pattern == "fixed",
                          f"{sc.name}: rf_link.antenna_pattern {getattr(sc.rf_link, 'antenna_pattern', '')!r} "
                          "needs the simulated attitude 'full_attitude' mode provides -- use \"fixed\" in "
                          "'orbit_only' mode")
        gs_names = [gs.name for gs in self.ground_stations]
        _require(len(gs_names) == len(set(gs_names)), f"ground_station names must be unique, got {gs_names}")
        folded_gs = [name.casefold() for name in gs_names]
        _require(len(folded_gs) == len(set(folded_gs)),
                 f"ground_station names {gs_names} differ only in case; their output files would collide")
        for gs in self.ground_stations:
            gs.validate()
        for sc in self.spacecraft:
            target_gs = sc.fsw_params.get("target_ground_station") if sc.fsw_mode == "locationPointing" else None
            if target_gs is not None:
                _require(target_gs in gs_names,
                          f"{sc.name}: fsw_params['target_ground_station'] {target_gs!r} is not one of "
                          f"this scenario's ground_stations {gs_names}")
        for sc in self.spacecraft:
            if sc.comms_pointing is not None:
                _require(sc.comms_pointing.target_ground_station in gs_names,
                          f"{sc.name}: comms_pointing.target_ground_station "
                          f"{sc.comms_pointing.target_ground_station!r} is not one of this scenario's "
                          f"ground_stations {gs_names}")
        for sc in self.spacecraft:
            target_body = sc.fsw_params.get("target_body") if sc.fsw_mode == "locationPointing" else None
            if target_body is not None:
                spice_tracked = {self.gravity.central_body, *self.gravity.third_body_perturbers}
                _require(target_body in spice_tracked,
                          f"{sc.name}: fsw_params['target_body'] {target_body!r} needs a real SPICE "
                          f"ephemeris -- it must be gravity.central_body or one of "
                          f"gravity.third_body_perturbers, got {sorted(spice_tracked)}")
        for sc in self.spacecraft:
            if sc.phasing_keeping is not None:
                _require(sc.phasing_keeping.chief_spacecraft in names,
                          f"{sc.name}: phasing_keeping.chief_spacecraft {sc.phasing_keeping.chief_spacecraft!r} "
                          f"is not one of this scenario's spacecraft {names}")
                # Phasing reads the chief's semi-major axis from its elements;
                # any other orbit type failed at build (audit M16).
                chief = next(other for other in self.spacecraft if other.name == sc.phasing_keeping.chief_spacecraft)
                _require(chief.orbit.type == "classical_elements",
                          f"{sc.name}: phasing_keeping.chief_spacecraft {chief.name!r} must have a "
                          f"'classical_elements' orbit (phasing needs its semi-major axis), not {chief.orbit.type!r}")
                # meanOEFeedback maps osculating to mean elements with
                # Earth's J2; with point-mass gravity there is no J2 motion
                # for that mapping to remove, and it would add a false one.
                if sc.phasing_keeping.control_law == "mean_oe":
                    _require(self.gravity.central_body == "earth" and self.gravity.central_body_degree >= 2,
                              f"{sc.name}: phasing_keeping.control_law 'mean_oe' needs Earth's J2 in the "
                              "dynamics -- set gravity.central_body to 'earth' and central_body_degree to 2 "
                              "or more, or choose 'drift_orbit' or 'hill_pd'")
            if sc.optical_navigation is not None:
                # pixelLineConverter and relativeODuKF know these bodies by
                # number (engine.opnav.BODY_IDS); the phase angle needs the Sun.
                _require(self.gravity.central_body in OPTICAL_NAVIGATION_BODIES,
                          f"{sc.name}: optical_navigation needs gravity.central_body to be one of "
                          f"{OPTICAL_NAVIGATION_BODIES} (the bodies Basilisk's pixelLineConverter and "
                          f"relativeODuKF know), not {self.gravity.central_body!r}")
                _require("sun" in self.gravity.third_body_perturbers,
                          f"{sc.name}: optical_navigation needs 'sun' in gravity.third_body_perturbers "
                          "(the image is used only on the lit side)")
            if sc.landmark_navigation is not None:
                # The filter predicts with the shape's gravity; the lighting needs the Sun.
                _require(self.gravity.central_body in SMALL_BODY_CENTRAL_BODIES and self.gravity.polyhedral_gravity,
                          f"{sc.name}: landmark_navigation needs a small body ({', '.join(SMALL_BODY_CENTRAL_BODIES)}) "
                          "as gravity.central_body with gravity.polyhedral_gravity (landmarks sit on its shape)")
                _require("sun" in self.gravity.third_body_perturbers,
                          f"{sc.name}: landmark_navigation needs 'sun' in gravity.third_body_perturbers "
                          "(a landmark is seen only in sunlight)")
            if sc.roe_formation is not None:
                prefix = f"{sc.name}: roe_formation.chief_spacecraft {sc.roe_formation.chief_spacecraft!r}"
                _require(sc.roe_formation.chief_spacecraft in names,
                          f"{prefix} is not one of this scenario's spacecraft {names}")
                chief = next(other for other in self.spacecraft if other.name == sc.roe_formation.chief_spacecraft)
                # The ROE are taken from mean elements around the chief's
                # orbit, and the impulsive guidance is the near-circular one.
                _require(chief.orbit.type == "classical_elements",
                          f"{prefix} must have a 'classical_elements' orbit, not {chief.orbit.type!r}")
                _require((chief.orbit.eccentricity or 0.0) <= ROE_MAX_CHIEF_ECCENTRICITY,
                          f"{prefix} must be near-circular (eccentricity at most "
                          f"{ROE_MAX_CHIEF_ECCENTRICITY:g}), not {chief.orbit.eccentricity or 0.0:g}")
                _require(0.0 < (chief.orbit.inclination_deg or 0.0) < 180.0,
                          f"{prefix} must be inclined: the relative inclination vector needs a node")
                # Mean elements (clMeanOscMap) and the J2 state transition
                # matrix are Earth's J2 theory.
                _require(self.gravity.central_body == "earth" and self.gravity.central_body_degree >= 2,
                          f"{sc.name}: roe_formation needs Earth's J2 in the dynamics -- set "
                          "gravity.central_body to 'earth' and central_body_degree to 2 or more")
        # Past one Basilisk run's limit the run is split into segments
        # (engine/long_run.py); these two cannot be split.
        single_run_days = SimSettings._MAX_SINGLE_RUN_DAYS
        if self.sim_settings.duration_days > single_run_days:
            _require(self.gravity.central_body not in SMALL_BODY_CENTRAL_BODIES,
                      f"a run around {self.gravity.central_body!r} is one simulation, at most {single_run_days:g} "
                      "days (sim_settings.duration_days; longer, segmented runs are not verified around small "
                      "bodies) -- shorten the run")
            _require(not runs_sequence(self.mission_sequence),
                      f"sim_settings.duration_days is over {single_run_days:g} days, which a mission sequence "
                      "cannot run -- shorten the run or remove the mission sequence")
            for sc in self.spacecraft:
                _require(sc.phasing_keeping is None,
                          f"{sc.name}: phasing_keeping runs at most {single_run_days:g} days "
                          "(sim_settings.duration_days) -- shorten the run")
                _require(sc.roe_formation is None,
                          f"{sc.name}: roe_formation runs at most {single_run_days:g} days "
                          "(sim_settings.duration_days) -- shorten the run")
                _require(sc.optical_navigation is None,
                          f"{sc.name}: optical_navigation runs at most {single_run_days:g} days "
                          "(sim_settings.duration_days; its filter is not carried between segments) "
                          "-- shorten the run")
        # engine.service.SimulationService.build() raises a
        # SimulationServiceError for this same condition (power/
        # station_keeping/enable_srp all need the real eclipse shadow
        # factor, which needs a sun ephemeris) -- but that's an
        # engine-layer check that only runs when a scenario is actually
        # simulated. Mirrored here for the same reason
        # GravityConfig.validate() mirrors the central_body_degree/
        # central_body check above: without this, `spacemissionstudio
        # validate`/the GUI's live "valid" indicator would report a
        # clean bill of health for a scenario guaranteed to fail the
        # moment it's actually run (caught for real: two of this
        # project's own bundled templates had exactly this bug).
        needs_sun = any(sc.power is not None or sc.station_keeping is not None or sc.enable_srp
                         or sc.comms_pointing is not None
                         for sc in self.spacecraft)
        # A heliocentric run tracks the Sun as its central body (audit L27).
        sun_tracked = "sun" in self.gravity.third_body_perturbers or self.gravity.central_body == "sun"
        if needs_sun:
            _require(sun_tracked,
                      "a spacecraft has power, station_keeping, enable_srp, or comms_pointing configured, "
                      "but 'sun' is not one of gravity.third_body_perturbers -- simpleSolarPanel/the eclipse "
                      "gate/SRP/comms_pointing's own sunSafePoint chain all need a sun ephemeris. Add 'sun' "
                      "to gravity.third_body_perturbers, or remove power/station_keeping/enable_srp/"
                      "comms_pointing from every spacecraft")
        # A thermal sensor needs the Sun's position (sensorThermal); without
        # a tracked Sun the build failed (audit M16).
        for sc in self.spacecraft:
            thermal = [sensor.name for sensor in sc.sensors if sensor.kind == "thermal"]
            _require(not thermal or sun_tracked,
                      f"{sc.name}: thermal sensor {thermal[0] if thermal else ''!r} needs the Sun's position -- add "
                      "'sun' to gravity.third_body_perturbers")
        # Same mirroring reasoning as needs_sun just above:
        # engine.fsw.attach_sensors() raises an FswError for a
        # "magnetometer" sensor the moment gravity.central_body != "earth"
        # (magneticFieldWMM is only wired up for Earth) -- but that's an
        # engine-layer check that only runs when a scenario is actually
        # simulated. Mirrored here so validation can't report a clean
        # bill of health for a scenario guaranteed to fail at run time.
        if self.gravity.central_body != "earth":
            for sc in self.spacecraft:
                # A TLE describes an Earth orbit (SGP4, TEME); around another
                # body it was accepted and misread (audit M13).
                _require(sc.orbit.type != "tle",
                          f"{sc.name}: a TLE orbit describes an Earth orbit, but gravity.central_body is "
                          f"{self.gravity.central_body!r} -- give the orbit as cartesian or classical elements")
                _require(not any(sensor.kind == "magnetometer" for sensor in sc.sensors),
                          f"{sc.name}: has a 'magnetometer' sensor, but gravity.central_body is "
                          f"{self.gravity.central_body!r}, not 'earth' -- magneticFieldWMM (the only "
                          "magnetic-field model this app wires up) is Earth-only. Remove the magnetometer "
                          "sensor, or set gravity.central_body to 'earth'")
                # Same Earth-only WMM restriction, same mirroring reasoning
                # -- engine.service.SimulationService.build() raises this
                # exact condition (central_body != "earth" ->
                # self._mag_field_model stays None) as a
                # SimulationServiceError at run time (see that module's
                # own "needs an Earth central body" message); mirrored
                # here, same as magnetic_momentum_management's own
                # docstring already said it SHOULD be (it previously
                # pointed at this exact gap as deferred-to-engine-layer).
                _require(sc.magnetic_momentum_management is None,
                          f"{sc.name}: has magnetic_momentum_management configured, but gravity.central_body "
                          f"is {self.gravity.central_body!r}, not 'earth' -- magneticFieldWMM is Earth-only. "
                          "Remove magnetic_momentum_management, or set gravity.central_body to 'earth'")
                _require(sc.geo_station_keeping is None,
                          f"{sc.name}: geo_station_keeping is Earth-only (it plans east-west burns from "
                          f"Earth's J22 term), but gravity.central_body is {self.gravity.central_body!r}")
        if self.gravity.central_body in SMALL_BODY_CENTRAL_BODIES:
            self._validate_small_body()
        _require(not self.gravity.albedo or sun_tracked,
                  "gravity.albedo needs 'sun' in gravity.third_body_perturbers: the reflected light is the Sun's")
        self.space_weather.validate()
        self.sim_settings.validate()
        self.monte_carlo.validate()
        by_name = {sc.name: sc for sc in self.spacecraft}
        for dispersion in self.monte_carlo.dispersions:
            _require(dispersion.spacecraft in names,
                      f"monte_carlo dispersion.spacecraft {dispersion.spacecraft!r} is not one of "
                      f"this scenario's spacecraft {names}")
            sc = by_name[dispersion.spacecraft]
            where = f"monte_carlo dispersion on {sc.name}.{dispersion.quantity}"
            if dispersion.quantity in ("inertia_kg_m2", "angular_rate_bn_b"):
                _require(self.simulation_mode == "full_attitude",
                          f"{where}: attitude is not simulated in simulation_mode {self.simulation_mode!r}")
            if dispersion.quantity == "drag_coeff":
                _require(sc.enable_drag and not sc.facets,
                          f"{where}: needs enable_drag and no facets (facets carry their own coefficients)")
            if dispersion.quantity == "srp_coeff":
                _require(sc.enable_srp and not sc.facets,
                          f"{where}: needs enable_srp and no facets (facets carry their own coefficients)")

        # Mission sequence (schema.command.Command) -- structural
        # validation only (each command's own .validate() already
        # collects every problem IN that command into one combined
        # message here; raise-fast ACROSS commands, i.e. this stops at
        # the first bad command, same as every other check in this
        # method). schema.validation.validate_all() is the fully
        # -collecting, "every command's every problem" entry point --
        # see that module's docstring for why this method doesn't
        # attempt that itself.
        for i, command in enumerate(self.mission_sequence):
            command_errors = command.validate(f"mission_sequence[{i}]")
            _require(not command_errors, "; ".join(command_errors))
        order_errors = report_before_propagate_errors(self.mission_sequence)
        _require(not order_errors, "; ".join(order_errors))
        self._validate_sequence_time()
        # local import: schema.references only imports schema.scenario
        # under TYPE_CHECKING (never at runtime), so this has no real
        # import cycle to avoid -- kept local anyway, matching
        # load_scenario()'s own "from . import migrations" precedent, so
        # a future change to that TYPE_CHECKING guard can't silently
        # create one here.
        from .references import _PLURAL, _command_references

        for ref in _command_references(self.mission_sequence, "mission_sequence"):
            known = names if ref.resource_kind == "spacecraft" else gs_names
            _require(ref.name in known,
                      f"{ref.path}: {ref.resource_kind} {ref.name!r} is not one of this scenario's "
                      f"{_PLURAL[ref.resource_kind]} {sorted(known)}")

    def _validate_sequence_time(self) -> None:
        """A Mission Sequence is one Basilisk run, so its clock may not pass
        SimSettings._MAX_SINGLE_RUN_DAYS (audit M3). Fixed-duration
        propagates are added up (both branches of an ``if`` counted, a
        ``while`` body once) and every stop epoch is checked; how long a
        loop or an event search runs is checked as the sequence runs."""
        limit_days = SimSettings._MAX_SINGLE_RUN_DAYS  # [day]
        start = parse_epoch_utc(self.epoch_utc)

        def fixed_days(commands) -> float:
            total = 0.0  # [day]
            for command in commands:
                if not command.enabled:
                    continue
                params = command.params
                if command.kind == "propagate" and params.get("stop_condition", "duration") == "duration":
                    total += float(params.get("duration_days", 0.0))
                elif command.kind == "propagate" and params.get("stop_condition") == "epoch":
                    stop = parse_epoch_utc(params["stop_epoch_utc"])
                    days = (stop - start).total_seconds() / 86400.0  # [day]
                    _require(days <= limit_days,
                             f"mission_sequence: propagate.stop_epoch_utc {params['stop_epoch_utc']!r} is "
                             f"{days:.1f} days after the scenario epoch; a Mission Sequence runs at most "
                             f"{limit_days:g} days")
                total += fixed_days(command.children)
            return total

        total_days = fixed_days(self.mission_sequence)
        _require(total_days <= limit_days,
                 f"mission_sequence: its fixed-duration propagates add up to {total_days:.1f} days; a Mission "
                 f"Sequence runs at most {limit_days:g} days (one Basilisk run)")

    # -- (de)serialization -------------------------------------------------
    def to_dict(self) -> dict:
        data = asdict(self)
        data["mission_sequence"] = [command_dict(command) for command in self.mission_sequence]
        return data

    @staticmethod
    def from_dict(data: dict) -> Scenario:
        data = dict(data)  # shallow copy, don't mutate the caller's dict
        gravity = GravityConfig(**data.pop("gravity", {}))
        sim_settings = SimSettings(**data.pop("sim_settings", {}))
        space_weather = SpaceWeatherConfig(**data.pop("space_weather", {}))
        ground_stations = [GroundStationConfig(**gs) for gs in data.pop("ground_stations", [])]

        mc_data = dict(data.pop("monte_carlo", {}))
        dispersions = [DispersionConfig(**d) for d in mc_data.pop("dispersions", [])]
        monte_carlo = MonteCarloConfig(dispersions=dispersions, **mc_data)

        spacecraft = []
        for sc in data.pop("spacecraft", []):
            sc = dict(sc)
            orbit = OrbitIC(**sc.pop("orbit"))
            sensors = [SensorConfig(**s) for s in sc.pop("sensors", [])]
            facets = [FacetConfig(**f) for f in sc.pop("facets", [])]
            model_data = sc.pop("model", None)
            model = None
            if model_data is not None:
                model_data = dict(model_data)
                parts = [ModelPartConfig(**part) for part in model_data.pop("parts", [])]
                meshes = [ModelMeshConfig(**mesh) for mesh in model_data.pop("meshes", [])]
                mass_data = model_data.pop("mass_properties", None)
                mass_properties = ModelMassPropertiesConfig(**mass_data) if mass_data is not None else None
                model = SpacecraftModelConfig(parts=parts, meshes=meshes, mass_properties=mass_properties,
                                              **model_data)
            actuators = [ActuatorConfig(**a) for a in sc.pop("actuators", [])]
            power_data = sc.pop("power", None)
            power = PowerConfig(**power_data) if power_data is not None else None
            rf_link_data = sc.pop("rf_link", None)
            rf_link = RFLinkConfig(**rf_link_data) if rf_link_data is not None else None
            comms_pointing_data = sc.pop("comms_pointing", None)
            comms_pointing = CommsPointingConfig(**comms_pointing_data) if comms_pointing_data is not None else None
            solar_arrays = [SolarArrayConfig(**a) for a in sc.pop("solar_arrays", [])]
            data_handling_data = sc.pop("data_handling", None)
            data_handling = None
            if data_handling_data is not None:
                data_handling_data = dict(data_handling_data)
                instruments = [InstrumentConfig(**i) for i in data_handling_data.pop("instruments", [])]
                data_handling = DataHandlingConfig(instruments=instruments, **data_handling_data)
            station_keeping_data = sc.pop("station_keeping", None)
            station_keeping = StationKeepingConfig(**station_keeping_data) if station_keeping_data is not None else None
            geo_data = sc.pop("geo_station_keeping", None)
            geo_station_keeping = GeoStationKeepingConfig(**geo_data) if geo_data is not None else None
            phasing_keeping_data = sc.pop("phasing_keeping", None)
            phasing_keeping = PhasingKeepingConfig(**phasing_keeping_data) if phasing_keeping_data is not None else None
            roe_formation_data = sc.pop("roe_formation", None)
            roe_formation = None
            if roe_formation_data is not None:
                roe_formation_data = dict(roe_formation_data)
                targets = [RoeTargetConfig(**target) for target in roe_formation_data.pop("targets", [])]
                roe_formation = RoeFormationConfig(targets=targets, **roe_formation_data)
            optical_navigation_data = sc.pop("optical_navigation", None)
            optical_navigation = (OpticalNavigationConfig(**optical_navigation_data)
                                  if optical_navigation_data is not None else None)
            landmark_navigation_data = sc.pop("landmark_navigation", None)
            landmark_navigation = (LandmarkNavigationConfig(**landmark_navigation_data)
                                   if landmark_navigation_data is not None else None)
            constant_thrust_data = sc.pop("constant_thrust", None)
            constant_thrust = ConstantThrustConfig(**constant_thrust_data) if constant_thrust_data is not None else None
            momentum_dumping_data = sc.pop("momentum_dumping", None)
            momentum_dumping = (
                MomentumDumpingConfig(**momentum_dumping_data) if momentum_dumping_data is not None else None
            )
            magnetic_momentum_management_data = sc.pop("magnetic_momentum_management", None)
            magnetic_momentum_management = (
                MagneticMomentumManagementConfig(**magnetic_momentum_management_data)
                if magnetic_momentum_management_data is not None else None
            )
            navigation_error_data = sc.pop("navigation_error", None)
            navigation_error = (NavigationErrorConfig(**navigation_error_data)
                                if navigation_error_data is not None else None)
            fuel_tank_data = sc.pop("fuel_tank", None)
            fuel_tank = FuelTankConfig(**fuel_tank_data) if fuel_tank_data is not None else None
            budget_data = sc.pop("propellant_budget", None)
            propellant_budget = PropellantBudgetConfig(**budget_data) if budget_data is not None else None
            spacecraft.append(SpacecraftConfig(propellant_budget=propellant_budget, orbit=orbit, sensors=sensors, actuators=actuators,
                                                power=power, rf_link=rf_link, comms_pointing=comms_pointing,
                                                data_handling=data_handling, solar_arrays=solar_arrays,
                                                station_keeping=station_keeping,
                                                geo_station_keeping=geo_station_keeping,
                                                phasing_keeping=phasing_keeping, roe_formation=roe_formation,
                                                optical_navigation=optical_navigation,
                                                landmark_navigation=landmark_navigation,
                                                constant_thrust=constant_thrust,
                                                momentum_dumping=momentum_dumping,
                                                magnetic_momentum_management=magnetic_momentum_management,
                                                navigation_error=navigation_error,
                                                fuel_tank=fuel_tank, facets=facets, model=model,
                                                **sc))

        mission_sequence = [Command.from_dict(c) for c in data.pop("mission_sequence", [])]
        fsw_exports = [FswExportRecord(**r) for r in data.pop("fsw_exports", [])]

        return Scenario(
            gravity=gravity, sim_settings=sim_settings, space_weather=space_weather,
            ground_stations=ground_stations, spacecraft=spacecraft, monte_carlo=monte_carlo,
            mission_sequence=mission_sequence, fsw_exports=fsw_exports, **data,
        )

    def save(self, path: str | Path) -> None:
        """Validate, then write the scenario as JSON. The text goes to a
        temporary file in the same folder, which then replaces ``path`` in
        one step, so a failed or interrupted save leaves the previous file
        as it was (audit M9). Raises OSError when the file cannot be
        written."""
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = scenario_text(self)
        # mkstemp makes an owner-only file; keep the replaced file's mode, or
        # the usual rw-r--r-- for a new one.
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise


_TYPE_HINTS: dict[type, dict[str, Any]] = {}


def _describe(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, (list, tuple)):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return type(value).__name__


def _type_problem(value, annotation) -> str | None:
    """Why ``value`` (as read from JSON) does not fit ``annotation``, or None.
    Only the shapes JSON can get wrong are checked; anything else passes."""
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if annotation is typing.Any or annotation is object:
        return None
    if origin is typing.Union:
        if value is None and type(None) in args:
            return None
        problems = [_type_problem(value, a) for a in args if a is not type(None)]
        return None if any(p is None for p in problems) else problems[0]
    if annotation is float:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        return None if ok else f"expected a number, got {_describe(value)}"
    if annotation is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
        return None if ok else f"expected a whole number, got {_describe(value)}"
    if annotation is bool:
        return None if isinstance(value, bool) else f"expected true or false, got {_describe(value)}"
    if annotation is str:
        return None if isinstance(value, str) else f"expected text, got {_describe(value)}"
    if annotation is list or origin is list:
        if not isinstance(value, (list, tuple)):
            return f"expected a list, got {_describe(value)}"
        for index, item in enumerate(value):
            problem = _type_problem(item, args[0]) if args else None
            if problem:
                return f"item {index}: {problem}"
        return None
    if annotation is tuple or origin is tuple:
        return None if isinstance(value, (list, tuple)) else f"expected a list, got {_describe(value)}"
    if annotation is dict or origin is dict:
        return None if isinstance(value, dict) else f"expected an object, got {_describe(value)}"
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        return None if isinstance(value, annotation) else f"expected an object, got {_describe(value)}"
    return None


def _check_types(obj, path: str, errors: list[str]) -> None:
    """Every field of ``obj`` (a loaded dataclass) and of the dataclasses in
    it against its declared type, so a hand-edited file with, say, a list
    where a number belongs is refused naming the field, before validate()
    compares it with something."""
    hints = _TYPE_HINTS.get(type(obj))
    if hints is None:
        hints = _TYPE_HINTS[type(obj)] = typing.get_type_hints(type(obj), globals())
    for f in dataclasses.fields(obj):
        value, where = getattr(obj, f.name), f"{path}.{f.name}" if path else f.name
        problem = _type_problem(value, hints.get(f.name, typing.Any))
        if problem:
            errors.append(f"{where}: {problem}")
            continue
        if dataclasses.is_dataclass(value):
            _check_types(value, where, errors)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if dataclasses.is_dataclass(item):
                    _check_types(item, f"{where}[{index}]", errors)


class ScenarioJSONError(ScenarioValidationError):
    """The text is not valid JSON; ``line`` and ``column`` (from 1) say
    where, ``reason`` what is wrong there."""

    def __init__(self, message: str, line: int, column: int, reason: str) -> None:
        super().__init__(message)
        self.line, self.column, self.reason = line, column, reason


def scenario_text(scenario: Scenario) -> str:
    """``scenario`` as :meth:`Scenario.save` writes it."""
    return json.dumps(scenario.to_dict(), indent=2) + "\n"


def parse_scenario_text(text: str, source: str) -> Scenario:
    """A scenario file's text, parsed, migrated and type-checked but NOT
    validated (``load_scenario`` validates it; the editor's JSON view loads
    it into the editor, which shows its problems). Raises
    :class:`ScenarioJSONError` for text that is not JSON, and
    :class:`ScenarioValidationError` for one that is not a scenario; both
    messages start with ``source``."""
    from . import migrations  # local import: avoids a cycle at module load time

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScenarioJSONError(f"{source}: not valid JSON ({exc})", exc.lineno, exc.colno, exc.msg) from exc

    if not isinstance(raw, dict) or "schema_version" not in raw:
        raise ScenarioValidationError(f"{source}: missing required top-level 'schema_version' field")

    try:
        raw = migrations.migrate(raw)
        scenario = Scenario.from_dict(raw)
    except ScenarioValidationError:
        raise
    except (TypeError, KeyError, ValueError, AttributeError) as exc:
        raise ScenarioValidationError(f"{source}: malformed scenario structure ({exc})") from exc
    errors: list[str] = []
    _check_types(scenario, "", errors)
    if errors:
        raise ScenarioValidationError(f"{source}: " + "; ".join(errors[:10]))
    return scenario


def load_scenario(path: str | Path) -> Scenario:
    """Load, migrate (if needed), and validate a scenario file. Raises
    :class:`ScenarioValidationError` with a specific message on anything
    malformed -- never returns a partially-populated or silently-defaulted
    :class:`Scenario`.
    """
    path = Path(path)
    try:
        with path.open("rb") as stream:  # bounded: a 50 MB file, or /dev/zero, is refused, not read (audit R9)
            data = stream.read(MAX_SCENARIO_FILE_BYTES + 1)
        if len(data) > MAX_SCENARIO_FILE_BYTES:
            raise ScenarioValidationError(f"{path}: larger than {MAX_SCENARIO_FILE_BYTES // 1_000_000} MB: not a "
                                          "scenario file")
        text = data.decode("utf-8")  # as save() writes it, on every platform
    except OSError as exc:
        # Covers a missing file, a directory given by mistake, a
        # permissions error, etc. -- all "can't read this path" failures,
        # not just the literal FileNotFoundError case.
        raise ScenarioValidationError(f"{path}: could not read file ({exc.strerror or exc})") from exc
    except UnicodeDecodeError as exc:
        raise ScenarioValidationError(f"{path}: not a scenario file (not UTF-8 text: {exc.reason})") from exc
    scenario = parse_scenario_text(text, str(path))
    try:
        scenario.validate()
    except ScenarioValidationError:
        raise
    except (TypeError, KeyError, ValueError, AttributeError, OverflowError) as exc:
        # A wrong-typed value inside a free-form block (e.g. a device's params) that the type check above
        # cannot see: still a refusal naming the file, never a traceback.
        raise ScenarioValidationError(f"{path}: malformed value ({exc})") from exc
    return scenario
