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

"""Orbit number: the Results plots' third time axis (docs/ux-audit.md U-26).

The orbit number counts revolutions from the ascending node: it is the
argument of latitude ``u`` (the angle from the ascending node to the
spacecraft, in the orbit plane) unwrapped and divided by a full turn.
Orbit 0 is the one in progress at the epoch, so the number at the epoch
is ``u / 360 deg`` (0.25 a quarter of the way round), and each ascending
node starts the next whole number. It comes from the recorded inertial
position and velocity alone, so it follows a decaying or manoeuvring
orbit as it was flown.

An equatorial orbit has no ascending node; its angle is then measured
from the inertial X axis (and :func:`reference_note` says so).

The angle is unwrapped with the mean motion: between two samples the
spacecraft goes round by about ``n * dt`` (``n`` from the vis-viva
semi-major axis), and the whole number of turns closest to that is
added. So a recording interval of a whole orbit or more (one sample a
day of a geostationary satellite) still counts every turn.

The mean motion uses the central body's gravitational parameter as the run
recorded it (:func:`central_body_mu`). In 1.3.1 and earlier Earth's was used for every
body, which added hundreds of spurious orbits to a sparsely recorded Mars or
Eros run (audit 3.1).

Basilisk-free: numpy and :class:`engine.results.ResultSet` only, except for
runs recorded before the provenance kept the GM (see :func:`central_body_mu`).
"""

from __future__ import annotations

import math

import numpy as np

from .propellant_budget import MU_EARTH_M3_S2
from .results import ResultSet

_TURN = 2.0 * math.pi  # [rad]
# |n| below this fraction of |h|: the orbit is equatorial for the node
# direction (inclination under ~0.06 deg), and the X axis is used instead.
_EQUATORIAL_NODE_FRACTION = 1e-3  # [-]
_NODE_SNAP_RAD = 1e-9  # [rad] closer than this below a full turn is the node itself


def _is_equatorial(r: np.ndarray, v: np.ndarray) -> bool:
    h = np.cross(r, v)
    node = np.cross(np.array([0.0, 0.0, 1.0]), h)
    return bool(np.all(np.linalg.norm(node, axis=1) < _EQUATORIAL_NODE_FRACTION * np.linalg.norm(h, axis=1)))


def argument_of_latitude(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """``u`` [rad] in [0, 2 pi) of each sample of positions ``r`` [m] and
    velocities ``v`` [m/s] (``(n, 3)`` arrays, inertial frame)."""
    r = np.asarray(r, dtype=float).reshape(-1, 3)
    v = np.asarray(v, dtype=float).reshape(-1, 3)
    h = np.cross(r, v)
    h_hat = h / np.linalg.norm(h, axis=1, keepdims=True)
    node = np.cross(np.array([0.0, 0.0, 1.0]), h)
    node_norm = np.linalg.norm(node, axis=1, keepdims=True)
    equatorial = node_norm[:, 0] < _EQUATORIAL_NODE_FRACTION * np.linalg.norm(h, axis=1)
    node_hat = np.where(equatorial[:, None], np.array([1.0, 0.0, 0.0]), node / np.where(node_norm > 0, node_norm, 1.0))
    in_plane = np.cross(h_hat, node_hat)  # 90 deg ahead of the node, in the orbit plane
    u = np.mod(np.arctan2(np.sum(r * in_plane, axis=1), np.sum(r * node_hat, axis=1)), _TURN)
    # At the node itself rounding gives -1e-16 rad, which wraps to a full turn.
    return np.where(u > _TURN - _NODE_SNAP_RAD, 0.0, u)


def orbit_numbers(time_s: np.ndarray, r: np.ndarray, v: np.ndarray, mu: float = MU_EARTH_M3_S2) -> np.ndarray:
    """The orbit number of each sample (see the module docstring):
    ``time_s`` [s] increasing, ``r`` [m] and ``v`` [m/s] inertial ``(n, 3)``,
    ``mu`` [m^3/s^2] the central body's gravitational parameter."""
    time_s = np.asarray(time_s, dtype=float)
    r = np.asarray(r, dtype=float).reshape(-1, 3)
    v = np.asarray(v, dtype=float).reshape(-1, 3)
    u = argument_of_latitude(r, v)
    if len(u) < 2:
        return u / _TURN
    radius = np.linalg.norm(r, axis=1)
    inverse_a = 2.0 / radius - np.sum(v * v, axis=1) / mu  # [1/m] vis-viva; <= 0 means not bound
    mean_motion = np.sqrt(mu * np.clip(inverse_a, 0.0, None) ** 3)  # [rad/s]
    expected = 0.5 * (mean_motion[1:] + mean_motion[:-1]) * np.diff(time_s)  # [rad] turn expected each step
    raw = np.diff(u)  # [rad] in (-2 pi, 2 pi)
    steps = raw + _TURN * np.round((expected - raw) / _TURN)
    return np.concatenate([[u[0]], u[0] + np.cumsum(steps)]) / _TURN


def reference_spacecraft(result: ResultSet | None, preferred: str | None = None) -> str | None:
    """The spacecraft whose orbit numbers the axis: ``preferred`` when it
    recorded its position and velocity, else the first that did."""
    if result is None:
        return None
    names = [name[: -len(".position_N")] for name in result.series if name.endswith(".position_N")]
    names = [name for name in names if f"{name}.velocity_N" in result.series]
    if preferred in names:
        return preferred
    return names[0] if names else None


def central_body_mu(result: ResultSet | None) -> float:
    """The central body's gravitational parameter [m^3/s^2] of the run in
    ``result``: the one its provenance recorded; for a run recorded before
    it was kept (1.3.1 and earlier), Basilisk's for the body its inertial
    frame is centred on; Earth's when neither is known."""
    provenance = getattr(result, "provenance", None)
    if provenance is None:
        return MU_EARTH_M3_S2
    if provenance.central_body_mu_m3_s2 > 0.0:
        return provenance.central_body_mu_m3_s2
    origin = str(provenance.frames.get("N", {}).get("origin", ""))
    body = origin.removesuffix(" centre of mass").lower()
    if body in ("", "earth"):
        return MU_EARTH_M3_S2
    try:
        from .orbit_conversion import OrbitConversionError
        from .orbit_conversion import central_body_mu as basilisk_mu
    except ImportError:  # pragma: no cover - the package always has it
        return MU_EARTH_M3_S2
    try:
        return basilisk_mu(body)
    except OrbitConversionError:
        return MU_EARTH_M3_S2


def for_result(result: ResultSet | None, spacecraft: str | None):
    """``(time_s, orbit_number)`` of ``spacecraft`` in ``result``, or None
    when it did not record its position and velocity (or recorded fewer
    than two samples)."""
    if result is None or spacecraft is None:
        return None
    position = result.series.get(f"{spacecraft}.position_N")
    velocity = result.series.get(f"{spacecraft}.velocity_N")
    if position is None or velocity is None or len(position.time_s) < 2:
        return None
    count = min(len(position.time_s), len(velocity.time_s))
    time_s = np.asarray(position.time_s[:count], dtype=float)
    return time_s, orbit_numbers(time_s, position.data[:count, :3], velocity.data[:count, :3],
                                 mu=central_body_mu(result))


def reference_note(result: ResultSet | None, spacecraft: str | None) -> str:
    """How the axis counts, for its title: "from the ascending node", or
    "from the X axis" for an equatorial orbit."""
    if result is None or spacecraft is None:
        return ""
    position = result.series.get(f"{spacecraft}.position_N")
    velocity = result.series.get(f"{spacecraft}.velocity_N")
    if position is None or velocity is None:
        return ""
    count = min(len(position.time_s), len(velocity.time_s))
    equatorial = _is_equatorial(position.data[:count, :3], velocity.data[:count, :3])
    return "from the inertial X axis (equatorial orbit)" if equatorial else "from the ascending node"
