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
"""The disturbance torque budget of a run (model analyses), from the
torques recorded in it (``engine.disturbance_recorder``).

For each source (aerodynamic, solar radiation pressure, gravity gradient,
residual dipole) and their sum: the series, its largest magnitude, the
time average of the magnitude, and the orbit-average vector (over the
last whole orbit, or the run when it is shorter). The momentum is the
integral of the total torque in the body frame (trapezoidal rule), what
the wheels of a spacecraft holding its attitude absorb: its largest
magnitude over the run, its value at the end, and the largest over any
one orbit (each whole orbit from the run's start).

**Analytical worst cases**, to set the recorded values against:

- gravity gradient ``3 mu / (2 r_p^3) |I_max - I_min|``, at the run's
  smallest orbit radius, the largest the vector form (NASA SP-8024) gives
  over all attitudes (the principal axes at 45 deg to the radius);
- solar radiation pressure ``P A (1 + q) L`` (NASA TP-3289): ``P`` the
  solar flux over the speed of light at 1 AU, ``A`` the facets' largest
  projected area over all directions, ``q`` their area-weighted
  reflectance (specular plus diffuse), ``L`` the largest distance from the
  centre of mass to the centre of pressure of the facets lit from one
  direction (directions sampled on a sphere);
- aerodynamic: the run's largest aerodynamic force times the same
  largest centre-of-pressure distance;
- residual dipole ``|m| max |B|``, with the run's field.

**Sizing.** The wheels' momentum capacity along each body axis
(``sum h_max |g . e|``, ``h_max`` from Basilisk's ``rwFactory`` for the
wheel type or the ``maxMomentum`` given) against the largest momentum per
orbit along it; the magnetorquers' dipole along each axis against
``|H_orbit| / (P_orbit |B|_mean)``, the least dipole that could remove one
orbit's momentum with the field at its mean and always perpendicular (a
lower bound). A ratio below 1 is a finding; no margin above 1 is
required, since none could be sourced (decision D-18).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..constants import SOLAR_FLUX_1AU_W_M2, SPEED_OF_LIGHT_M_S
from ..engine.disturbance_recorder import SOURCES

LABELS = {"aero": "aerodynamic", "srp": "solar radiation pressure", "gravity_gradient": "gravity gradient",
          "magnetic": "residual dipole", "total": "total"}
_DIRECTIONS = 2000  # [-] directions sampled for the centre-of-pressure distance
# A run "of whole orbits" may end this fraction of an orbit short: the period
# from the first state differs from the run's own by its rounding.
_PERIOD_TOLERANCE = 1e-6


@dataclass
class SourceSummary:
    source: str
    max_n_m: float  # [N*m] largest magnitude
    mean_n_m: float  # [N*m] time average of the magnitude
    orbit_average_n_m: np.ndarray  # [N*m] body frame
    analytic_worst_n_m: float | None = None  # [N*m]
    analytic_note: str = ""


@dataclass
class DisturbanceBudget:
    spacecraft: str
    period_s: float  # [s] orbit period
    duration_s: float  # [s]
    sources: dict = field(default_factory=dict)  # source -> SourceSummary, with "total"
    time_s: np.ndarray | None = None
    momentum_n_m_s: np.ndarray | None = None  # (n, 3) [N*m*s] integral of the total torque
    momentum_per_orbit_n_m_s: np.ndarray | None = None  # [N*m*s] largest |component| over one whole orbit
    whole_orbits: int = 0
    wheel_capacity_n_m_s: np.ndarray | None = None  # [N*m*s] per body axis
    dipole_available_a_m2: np.ndarray | None = None  # [A*m^2] per body axis
    dipole_needed_a_m2: np.ndarray | None = None  # [A*m^2] per body axis, a lower bound
    notes: list = field(default_factory=list)

    @property
    def momentum_end_n_m_s(self) -> float:
        return float(np.linalg.norm(self.momentum_n_m_s[-1])) if len(self.momentum_n_m_s) else 0.0

    @property
    def momentum_max_n_m_s(self) -> float:
        return float(np.linalg.norm(self.momentum_n_m_s, axis=1).max()) if len(self.momentum_n_m_s) else 0.0

    def required_momentum_n_m_s(self) -> np.ndarray:
        """Per body axis: the largest momentum over one whole orbit, or over
        the run when it is shorter than an orbit."""
        if self.momentum_per_orbit_n_m_s is not None:
            return self.momentum_per_orbit_n_m_s
        return np.abs(self.momentum_n_m_s).max(axis=0)

    def wheel_ratio(self) -> np.ndarray | None:
        if self.wheel_capacity_n_m_s is None:
            return None
        required = self.required_momentum_n_m_s()
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(required > 0.0, self.wheel_capacity_n_m_s / required, np.inf)

    def dipole_ratio(self) -> np.ndarray | None:
        if self.dipole_available_a_m2 is None or self.dipole_needed_a_m2 is None:
            return None
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.dipole_needed_a_m2 > 0.0, self.dipole_available_a_m2 / self.dipole_needed_a_m2,
                            np.inf)

    def rows(self) -> list[dict]:
        rows = []
        for source, summary in self.sources.items():
            rows.append({"source": LABELS[source], "max_n_m": summary.max_n_m, "mean_n_m": summary.mean_n_m,
                         "orbit_average_n_m": " ".join(f"{v:.4g}" for v in summary.orbit_average_n_m),
                         "analytic_worst_n_m": summary.analytic_worst_n_m, "analytic": summary.analytic_note})
        return rows

    def findings(self) -> list:
        from ..engine.findings import Finding

        found = []
        axes = "xyz"
        ratio = self.wheel_ratio()
        if ratio is not None:
            required = self.required_momentum_n_m_s()
            for k in np.flatnonzero(ratio < 1.0):
                found.append(Finding(
                    f"{self.spacecraft}: the wheels hold {self.wheel_capacity_n_m_s[k]:.3g} N*m*s along body "
                    f"{axes[k]}, less than the {required[k]:.3g} N*m*s the disturbances build up "
                    + ("per orbit" if self.momentum_per_orbit_n_m_s is not None else "over the run"),
                    "design.wheel_capacity", actual=f"{required[k]:.3g} N*m*s",
                    limit=f"{self.wheel_capacity_n_m_s[k]:.3g} N*m*s"))
        ratio = self.dipole_ratio()
        if ratio is not None:
            for k in np.flatnonzero(ratio < 1.0):
                found.append(Finding(
                    f"{self.spacecraft}: the magnetorquers give {self.dipole_available_a_m2[k]:.3g} A*m^2 along body "
                    f"{axes[k]}, less than the {self.dipole_needed_a_m2[k]:.3g} A*m^2 needed at least to remove one "
                    "orbit's momentum", "design.dipole_capacity", actual=f"{self.dipole_needed_a_m2[k]:.3g} A*m^2",
                    limit=f"{self.dipole_available_a_m2[k]:.3g} A*m^2"))
        return found


def integrate(time_s: np.ndarray, torque: np.ndarray) -> np.ndarray:
    """The running trapezoidal integral of ``torque`` (n, 3) over ``time_s``."""
    if len(time_s) < 2:
        return np.zeros((len(time_s), 3))
    steps = 0.5 * (torque[1:] + torque[:-1]) * np.diff(time_s)[:, None]
    return np.vstack([np.zeros((1, 3)), np.cumsum(steps, axis=0)])


def _orbit_period_s(result, name: str, mu: float) -> float:
    r = np.asarray(result.series[f"{name}.position_N"].data[0], dtype=float)
    v = np.asarray(result.series[f"{name}.velocity_N"].data[0], dtype=float)
    energy = 0.5 * float(v @ v) - mu / float(np.linalg.norm(r))  # [m^2/s^2]
    if energy >= 0.0:
        return math.inf
    a = -mu / (2.0 * energy)  # [m]
    return 2.0 * math.pi * math.sqrt(a ** 3 / mu)


def _sphere(count: int) -> np.ndarray:
    k = np.arange(count) + 0.5
    z = 1.0 - 2.0 * k / count
    phi = math.pi * (1.0 + math.sqrt(5.0)) * k
    rho = np.sqrt(1.0 - z * z)
    return np.column_stack([rho * np.cos(phi), rho * np.sin(phi), z])


def facet_geometry(sc) -> tuple[float, float, float]:
    """``(A_max [m^2], L_max [m], q [-])`` of the spacecraft's facets: the
    largest projected area over all directions, the largest distance from
    the centre of mass to the centre of pressure of the facets facing one
    direction, and the area-weighted reflectance."""
    if not sc.facets:
        return 0.0, 0.0, 0.0
    areas = np.array([f.area_m2 for f in sc.facets], dtype=float)
    normals = np.array([np.asarray(f.normal_b, float) / np.linalg.norm(f.normal_b) for f in sc.facets])
    locations = np.array([f.location_b for f in sc.facets], dtype=float)
    reflect = np.array([f.specular_coeff + f.diffuse_coeff for f in sc.facets], dtype=float)
    centre = np.asarray(sc.center_of_mass_b_m, dtype=float)
    projected = np.clip(_sphere(_DIRECTIONS) @ normals.T, 0.0, None) * areas  # (directions, facets) [m^2]
    totals = projected.sum(axis=1)
    lit = totals > 0.0
    pressure_centres = (projected[lit] @ locations) / totals[lit, None]
    distance = float(np.linalg.norm(pressure_centres - centre, axis=1).max()) if lit.any() else 0.0
    return float(totals.max()), distance, float((areas * reflect).sum() / areas.sum())


def _wheel_capacity(sc) -> np.ndarray | None:
    wheels = [a for a in sc.actuators if a.kind == "reaction_wheel"]
    if not wheels:
        return None
    capacity = np.zeros(3)
    for wheel in wheels:
        params = wheel.params or {}
        h_max = params.get("maxMomentum")
        if h_max is None or params.get("rw_type", "custom") != "custom":
            h_max = _factory_momentum(params) or h_max
        axis = np.asarray(params["gsHat_B"], dtype=float)
        capacity += float(h_max or 0.0) * np.abs(axis / np.linalg.norm(axis))
    return capacity


def _factory_momentum(params) -> float | None:
    """A wheel's maxMomentum as Basilisk's rwFactory sets it, or None."""
    try:
        from Basilisk.utilities import simIncludeRW

        from ..engine.fsw import _coerce_rw_kwargs

        factory = simIncludeRW.rwFactory()
        wheel = factory.create(params.get("rw_type", "custom"), [float(v) for v in params["gsHat_B"]],
                               **_coerce_rw_kwargs(params))
        return float(wheel.Js * wheel.Omega_max) if not wheel.maxMomentum else float(wheel.maxMomentum)
    except (ImportError, SystemExit, KeyError, TypeError, ValueError, AttributeError):
        return None


def _dipole_available(sc) -> np.ndarray | None:
    rods = [a for a in sc.actuators if a.kind == "magnetic_torque_rod"]
    if not rods:
        return None
    available = np.zeros(3)
    for rod in rods:
        axis = np.asarray(rod.params["gtHat_B"], dtype=float)
        available += float(rod.params["max_dipole_a_m2"]) * np.abs(axis / np.linalg.norm(axis))
    return available


def disturbance_budget(result, sc) -> DisturbanceBudget | None:
    """:class:`DisturbanceBudget` of spacecraft ``sc`` (a ``SpacecraftConfig``)
    in ``result``, or None when the run did not record its torques."""
    from ..engine.orbit_number import central_body_mu

    name = sc.name
    prefix = f"{name}.disturbance."
    if f"{prefix}total_torque" not in result.series:
        return None
    t = np.asarray(result.series[f"{prefix}total_torque"].time_s, dtype=float)
    mu = central_body_mu(result)
    period = _orbit_period_s(result, name, mu)
    budget = DisturbanceBudget(name, period, float(t[-1] - t[0]) if len(t) else 0.0, time_s=t)
    whole = math.isfinite(period) and budget.duration_s >= period * (1.0 - _PERIOD_TOLERANCE)
    last = t >= t[-1] - period * (1.0 + _PERIOD_TOLERANCE) if whole else np.ones(len(t), bool)
    if not whole:
        budget.notes.append("the run is shorter than an orbit: the orbit averages and the momentum are the run's")
    field_b = result.series[f"{prefix}magnetic_field_body"].data
    for source in (*SOURCES, "total"):
        torque = np.asarray(result.series[f"{prefix}{source}_torque"].data, dtype=float)
        magnitude = np.linalg.norm(torque, axis=1)
        mean = float(np.trapezoid(magnitude, t) / budget.duration_s) if budget.duration_s > 0 else float(
            magnitude.mean())
        window = t[last]
        average = (np.trapezoid(torque[last], window, axis=0) / (window[-1] - window[0])
                   if len(window) > 1 and window[-1] > window[0] else torque[last].mean(axis=0))
        budget.sources[source] = SourceSummary(source, float(magnitude.max()), mean, average)
    total = np.asarray(result.series[f"{prefix}total_torque"].data, dtype=float)
    budget.momentum_n_m_s = integrate(t, total)
    if whole:
        starts = np.arange(t[0], t[-1] - period * (1.0 - _PERIOD_TOLERANCE), period)
        budget.whole_orbits = len(starts)
        worst = np.zeros(3)
        for start in starts:
            inside = (t >= start - 1e-9) & (t <= start + period * (1.0 + _PERIOD_TOLERANCE))
            span = budget.momentum_n_m_s[inside] - budget.momentum_n_m_s[inside][0]
            worst = np.maximum(worst, np.abs(span).max(axis=0))
        budget.momentum_per_orbit_n_m_s = worst
    _analytic(budget, result, sc, mu, field_b)
    budget.wheel_capacity_n_m_s = _wheel_capacity(sc)
    budget.dipole_available_a_m2 = _dipole_available(sc)
    field_mean = float(np.linalg.norm(field_b, axis=1).mean()) if len(field_b) else 0.0
    if budget.dipole_available_a_m2 is not None and field_mean > 0.0:
        window_s = period if budget.momentum_per_orbit_n_m_s is not None else max(budget.duration_s, 1e-9)  # [s]
        budget.dipole_needed_a_m2 = budget.required_momentum_n_m_s() / (window_s * field_mean)
    elif budget.dipole_available_a_m2 is not None:
        budget.notes.append("no magnetic field recorded (no residual dipole set): the magnetorquers are not sized")
    if not sc.facets:
        budget.notes.append("no facets: the aerodynamic and SRP torques are those of Basilisk's cannonball models, "
                            "whose force acts at the body origin")
    return budget


def _analytic(budget, result, sc, mu, field_b) -> None:
    from ..engine.orbit_conversion import OrbitConversionError  # noqa: F401 -- the module the mu came from

    radius = float(np.linalg.norm(result.series[f"{sc.name}.position_N"].data, axis=1).min())  # [m]
    moments = np.linalg.eigvalsh(np.asarray(sc.inertia_kg_m2, dtype=float).reshape(3, 3))  # [kg*m^2]
    gg = 3.0 * mu / (2.0 * radius ** 3) * float(moments[-1] - moments[0])
    budget.sources["gravity_gradient"].analytic_worst_n_m = gg
    budget.sources["gravity_gradient"].analytic_note = (f"3 mu / (2 r^3) |I_max - I_min| at r = "
                                                        f"{radius / 1000.0:.1f} km")
    area, distance, q = facet_geometry(sc)
    if sc.facets:
        pressure = SOLAR_FLUX_1AU_W_M2 / SPEED_OF_LIGHT_M_S  # [N/m^2]
        budget.sources["srp"].analytic_worst_n_m = pressure * area * (1.0 + q) * distance
        budget.sources["srp"].analytic_note = (f"P A (1 + q) L, A = {area:.3g} m^2, q = {q:.2f}, L = {distance:.3g} m"
                                               " (NASA TP-3289)")
        force = float(np.linalg.norm(result.series[f"{sc.name}.disturbance.aero_force"].data, axis=1).max())
        budget.sources["aero"].analytic_worst_n_m = force * distance
        budget.sources["aero"].analytic_note = f"largest force {force:.3g} N times L = {distance:.3g} m"
    dipole = float(np.linalg.norm(sc.model_analyses.residual_dipole_a_m2))
    field_max = float(np.linalg.norm(field_b, axis=1).max()) if len(field_b) else 0.0
    budget.sources["magnetic"].analytic_worst_n_m = dipole * field_max
    budget.sources["magnetic"].analytic_note = f"|m| max |B| = {dipole:g} A*m^2 x {field_max:.3g} T"
