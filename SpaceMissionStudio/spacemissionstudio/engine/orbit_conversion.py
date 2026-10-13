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

"""Converts a spacecraft's initial orbit from one form to another
(docs/ux-audit.md U-14), so switching the orbit type in the editor can keep
the same orbit:

- classical elements -> Cartesian state, and back;
- a TLE -> Cartesian state or classical elements at the scenario epoch
  (SGP4, TEME -> EME2000, as the run does: :mod:`engine.tle`).

Nothing converts to a TLE: a TLE holds SGP4 mean elements fitted to
tracking data, which an osculating state does not give.

The conversion uses Basilisk's own ``orbitalMotion`` (``elem2rv``,
``rv2elem``, ``M2E``/``E2f``/``f2E``/``E2M``) and the central body's
``mu`` from ``simIncludeGravBody``, the functions and constants the run uses
(see ``engine.service._orbit_ic_to_rv``), so a converted orbit starts the
run where the original would have. Without Basilisk it raises
:class:`OrbitConversionError`.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from ..schema.scenario import OrbitIC
from . import tle


class OrbitConversionError(ValueError):
    """The orbit cannot be converted; the message says why."""


def _basilisk():
    try:
        from Basilisk.utilities import orbitalMotion, simIncludeGravBody
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise OrbitConversionError(f"converting an orbit needs Basilisk, which is not available: {exc}") from exc
    return orbitalMotion, simIncludeGravBody


def central_body_mu(central_body: str) -> float:
    """The central body's gravitational parameter [m^3/s^2], from Basilisk."""
    _orbital_motion, sim_include_grav_body = _basilisk()
    try:
        return float(sim_include_grav_body.gravBodyFactory().createBodies([central_body])[central_body].mu)
    except (KeyError, RuntimeError) as exc:
        raise OrbitConversionError(f"no gravitational parameter for central body {central_body!r}: {exc}") from exc


def _degrees(angle_rad: float) -> float:
    """An angle in [0, 360) deg."""
    value = math.degrees(angle_rad) % 360.0
    return 0.0 if math.isclose(value, 360.0) else value


def state_km(orbit: OrbitIC, central_body: str = "earth", epoch_utc: Optional[str] = None):
    """``(position_km, velocity_km_s)`` lists for ``orbit``, in the frame the
    run starts it in (EME2000 for Earth). A TLE needs ``epoch_utc``."""
    if orbit.type == "cartesian":
        return list(orbit.position_km), list(orbit.velocity_km_s)
    if orbit.type == "tle":
        if not epoch_utc:
            raise OrbitConversionError("a TLE is converted at the scenario epoch, and there is none")
        if central_body != "earth":
            raise OrbitConversionError(f"a TLE describes an Earth orbit, not one about {central_body!r}")
        try:
            state = tle.state_at(orbit.tle_line1, orbit.tle_line2, epoch_utc)
        except (tle.TLEError, ValueError) as exc:
            raise OrbitConversionError(f"the TLE cannot be propagated to the epoch: {exc}") from exc
        return [float(v) / 1e3 for v in state.r_m], [float(v) / 1e3 for v in state.v_m_s]
    orbital_motion, _ = _basilisk()
    e = orbit.eccentricity
    if not 0.0 <= e < 1.0 or not orbit.semi_major_axis_km or orbit.semi_major_axis_km <= 0.0:
        raise OrbitConversionError("only an elliptical orbit (0 <= e < 1, a > 0) is converted")
    oe = orbital_motion.ClassicElements()
    oe.a = orbit.semi_major_axis_km * 1e3  # [m]
    oe.e = e
    oe.i = math.radians(orbit.inclination_deg)
    oe.Omega = math.radians(orbit.raan_deg)
    oe.omega = math.radians(orbit.arg_periapsis_deg)
    if orbit.anomaly_type == "mean":
        oe.f = orbital_motion.E2f(orbital_motion.M2E(math.radians(orbit.mean_anomaly_deg), e), e)
    else:
        oe.f = math.radians(orbit.true_anomaly_deg)
    r_m, v_m_s = orbital_motion.elem2rv(central_body_mu(central_body), oe)
    return [float(v) / 1e3 for v in r_m], [float(v) / 1e3 for v in v_m_s]


def to_cartesian(orbit: OrbitIC, central_body: str = "earth", epoch_utc: Optional[str] = None) -> OrbitIC:
    """``orbit`` as a Cartesian state."""
    position_km, velocity_km_s = state_km(orbit, central_body, epoch_utc)
    return OrbitIC(type="cartesian", position_km=position_km, velocity_km_s=velocity_km_s)


def to_classical(orbit: OrbitIC, central_body: str = "earth", epoch_utc: Optional[str] = None,
                 anomaly_type: str = "true") -> OrbitIC:
    """``orbit`` as osculating classical elements, its anomaly as
    ``anomaly_type`` ("true" or "mean"). For a circular orbit Basilisk puts
    the argument of latitude in the anomaly and the argument of periapsis at
    0, and for an equatorial one the RAAN at 0."""
    orbital_motion, _ = _basilisk()
    position_km, velocity_km_s = state_km(orbit, central_body, epoch_utc)
    r_m = np.array(position_km, dtype=float) * 1e3
    v_m_s = np.array(velocity_km_s, dtype=float) * 1e3
    if not np.linalg.norm(r_m) > 0.0:
        raise OrbitConversionError("the position is zero")
    oe = orbital_motion.rv2elem(central_body_mu(central_body), r_m, v_m_s)
    if not 0.0 <= oe.e < 1.0 or oe.a <= 0.0:
        raise OrbitConversionError(f"this state is not an elliptical orbit (e = {oe.e:.4g}): it has no classical "
                                   "elements of the kind the editor takes")
    if anomaly_type == "mean":
        anomaly = {"mean_anomaly_deg": _degrees(orbital_motion.E2M(orbital_motion.f2E(oe.f, oe.e), oe.e))}
    else:
        anomaly = {"true_anomaly_deg": _degrees(oe.f)}
    return OrbitIC(type="classical_elements", semi_major_axis_km=float(oe.a) / 1e3, eccentricity=float(oe.e),
                   inclination_deg=math.degrees(float(oe.i)), raan_deg=_degrees(oe.Omega),
                   arg_periapsis_deg=_degrees(oe.omega), anomaly_type=anomaly_type, **anomaly)


def convert(orbit: OrbitIC, to_type: str, central_body: str = "earth", epoch_utc: Optional[str] = None,
            anomaly_type: str = "true") -> OrbitIC:
    """``orbit`` as ``to_type``; :class:`OrbitConversionError` when it cannot
    be (to a TLE, always)."""
    if to_type == "cartesian":
        return to_cartesian(orbit, central_body, epoch_utc)
    if to_type == "classical_elements":
        return to_classical(orbit, central_body, epoch_utc, anomaly_type)
    raise OrbitConversionError("nothing converts to a TLE: a TLE holds SGP4 mean elements fitted to tracking "
                               "data; paste the satellite's two lines instead")
