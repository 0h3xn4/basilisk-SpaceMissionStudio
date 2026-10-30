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

"""Delta-V and propellant budgets in the manner of ESA's guideline AD10,
"Guidelines for the computation of the Delta-V and Propellant Mass
budgets" (EOP-FM/2024-07-177, issue 3.0). Section numbers below refer to
it; the guideline itself is not reproduced here.

The budget follows the mission's three phases -- beginning of life
(injection-error correction, orbit acquisition), operations (transfers,
in- and out-of-plane control, collision avoidance, formation keeping,
thruster attitude control) and end of life (clearance, disposal) -- then
adds the propellant residual and loading uncertainty, and iterates the
total propellant until it changes by less than 0.1 kg (Sec. 6.5).

* **Propellant per contributor** (Secs. 6.1.3, 6.2.7, 6.3.4): the rocket
  equation from the mass before the burn, ``m * (1 - exp(-dV / Ve))``,
  with ``Ve = eta * Isp * g0`` and the thruster efficiency ``eta`` of
  Sec. 5.11; the contributors are taken in order, each from the mass the
  ones before it left. (Until 1.3.1 each took the phase's starting mass
  times ``exp(dV / Ve) - 1``, the form for the mass *after* a burn: too
  much propellant, 5 % at 100 m/s and 2.5 times at 1 km/s (150 kg dry, Isp 220 s),
  and no total at all from about ``Ve * ln 2``.)
* **From simulation** (Sec. 6.2.7: in-plane control "via simulation"):
  in- and out-of-plane control and formation keeping are taken from the
  spacecraft's last run -- delta-V and propellant as flown, so the mass
  evolution is the simulation's -- scaled up when the run is shorter than
  the mission, and flagged unless the run used AD10's operations settings
  (MSFC 95th percentile, Sec. 5.9; Cd 3.0, Sec. 5.2). Without a run, a
  LEO station keeper's in-plane control is estimated from the drag on its
  held orbit (:func:`.lifetime.drag_makeup`, MSFC 95th percentile).
* **Launch delays** (Sec. 5.5): :func:`launch_delay_sweep` repeats the
  budget for launches up to 5 years late. In-plane control follows the
  solar activity of each window (the run's figure times the drag make-up
  ratio of the two windows), and the disposal is re-solved from each end
  of life.
* **Margins** (Sec. 5.6): collision-avoidance count x4, thruster attitude
  control propellant +100%, a controlled re-entry's last burn +15%;
  residual 1% and uncertainty 2% of the tank's maximum load (Secs. 5.8,
  6.4 -- the summary table prints 10% and 20%; the equations are used and
  the difference is noted); dry-mass system margin 15% unless the dry
  mass already includes one (Sec. 5.10).
* **Computed contributors:** a collision avoidance is +100 m then -100 m
  of semi-major axis (Sec. 6.2.4); clearance drops the semi-major axis
  (Sec. 6.3.2); an uncontrolled re-entry lowers the perigee until the
  orbit lifetime is ``disposal_lifetime_years`` (5, the LEO protected-
  region rule of Sec. 6.3.1.2), estimated with :mod:`.lifetime` at MSFC's
  50th percentile and Cd 2.2 (Secs. 5.9, 5.2) and the tumbling average
  area (Sec. 5.3); a GEO graveyard orbit is raised by
  ``235 + 1000 * Cr * A / m`` km (Sec. 6.3.1.3), as a Hohmann transfer.

Not covered: the number of collision avoidances (ESA's DRAMA computes it;
enter it), finite-burn gravity losses outside the simulations (Sec. 5.4),
hybrid propulsion systems, and launch-date effects other than drag (e.g.
the Moon's 18.6-year cycle in GEO north-south control).
"""

from __future__ import annotations

import math
import pickle
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from collections.abc import Callable

from .. import constants
from ..config import registry
from ..schema.epochs import parse_epoch_utc
from ..schema.scenario import PropellantBudgetConfig
from .trace import Quantity, Trace

G0_M_S2 = constants.STANDARD_GRAVITY_M_S2  # [m/s^2]
MU_EARTH_M3_S2 = constants.EARTH_GM_M3_S2  # [m^3/s^2] the one set (spacemissionstudio.constants)
REQ_EARTH_M = constants.EARTH_EQUATORIAL_RADIUS_M  # [m]
# The budget's rules and margins are named parameters (config.parameters,
# "propellant_budget"): AD10's values by default, a project's own where its
# configuration file sets them (transparency audit, Phase 3a).


def rule(name: str, scenario=None):
    """The value of ``propellant_budget.<name>`` in effect for ``scenario``."""
    return registry.value(f"propellant_budget.{name}", scenario)


class BudgetError(Exception):
    """A budget this module cannot compute (e.g. no thruster Isp)."""


@dataclass
class BudgetRow:
    phase: str  # "Beginning of life", "Operations", "End of life", "Propellant"
    contributor: str
    delta_v_m_s: float | None  # [m/s] None for propellant-only rows
    propellant_kg: float  # [kg]
    margin: str = "-"
    source: str = "input"  # "input", "computed", "last run", "last run, scaled"
    # How the two numbers were reached (engine.trace, transparency plan Phase 4a): equation, inputs, reference.
    # Not compared: a row is its numbers.
    delta_v_trace: Trace | None = field(default=None, compare=False, repr=False)
    propellant_trace: Trace | None = field(default=None, compare=False, repr=False)


@dataclass
class Budget:
    rows: list[BudgetRow]
    dry_mass_kg: float  # [kg] including the system margin
    isp_s: float  # [s]
    efficiency: float  # [-]
    iterations: int
    notes: list[str] = field(default_factory=list)
    # The space-weather files the drag estimates read (transparency audit,
    # Phase 2g): the in-plane make-up and the uncontrolled re-entry.
    data_files: dict = field(default_factory=dict)
    # How the budget-wide numbers were reached (engine.trace): "efficiency", "exhaust_speed", "dry_mass",
    # "total_propellant".
    traces: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def total_delta_v_m_s(self) -> float:
        return sum(r.delta_v_m_s for r in self.rows if r.delta_v_m_s is not None)

    @property
    def total_propellant_kg(self) -> float:
        return sum(r.propellant_kg for r in self.rows)


def thruster_efficiency(config: PropellantBudgetConfig) -> float:
    """``eta = cos(alpha) * eta_mis * eta_plume * eta_mod`` (Sec. 5.11)."""
    return (math.cos(math.radians(config.thrust_angle_deg)) * math.cos(math.radians(config.misalignment_deg))
            * config.plume_efficiency * config.modulation_efficiency)


def propellant_for(mass_kg: float, delta_v_m_s: float, exhaust_m_s: float) -> float:
    """The propellant [kg] a burn of ``delta_v_m_s`` uses from ``mass_kg``,
    the mass before it: ``m * (1 - exp(-dV / Ve))`` (Secs. 6.1.3, 6.2.7,
    6.3.4). From the mass after the burn the same amount is
    ``m * (exp(dV / Ve) - 1)``."""
    return mass_kg * -math.expm1(-delta_v_m_s / exhaust_m_s)


def _circular_speed(a_m: float) -> float:
    return math.sqrt(MU_EARTH_M3_S2 / a_m)


def injection_delta_v(config: PropellantBudgetConfig, a_m: float):
    """(in-plane, out-of-plane) injection-error correction [m/s] (Sec.
    6.1.1): the larger of the semi-major-axis and eccentricity-vector
    corrections, and the inclination change, decoupled."""
    v = _circular_speed(a_m)
    sma = v * config.injection_sma_error_km * 1e3 / (2.0 * a_m)  # two-burn semi-major axis change
    ecc = v * config.injection_eccentricity_error / 2.0  # two-burn eccentricity-vector change
    inclination = 2.0 * v * math.sin(math.radians(config.injection_inclination_error_deg) / 2.0)
    return max(sma, ecc), inclination


def collision_avoidance_delta_v(a_m: float, sma_change_m: float | None = None) -> float:
    """One avoidance (Sec. 6.2.4): +``sma_change_m`` of semi-major axis
    (default ``cam_sma_change_m``, 100 m), then back [m/s]."""
    sma_change_m = rule("cam_sma_change_m") if sma_change_m is None else sma_change_m
    return 2.0 * _circular_speed(a_m) * sma_change_m / (2.0 * a_m)


def clearance_delta_v(a_m: float, drop_km: float) -> float:
    """Lowering the semi-major axis by ``drop_km`` (Sec. 6.3.2) [m/s]."""
    return _circular_speed(a_m) * drop_km * 1e3 / (2.0 * a_m)


def graveyard_delta_v(a_m: float, srp_coeff: float, srp_area_m2: float, dry_mass_kg: float, scenario=None):
    """(delta-V [m/s], raise [m]) of a Hohmann transfer to the GEO graveyard
    orbit, ``235 + 1000 * Cr * A / m`` km up by default (Sec. 6.3.1.3;
    ``geo_graveyard_base_m`` and ``geo_graveyard_per_cr_a_m`` for
    ``scenario``)."""
    raise_m = rule("geo_graveyard_base_m", scenario) + \
        rule("geo_graveyard_per_cr_a_m", scenario) * srp_coeff * srp_area_m2 / dry_mass_kg
    r1, r2 = a_m, a_m + raise_m
    dv1 = _circular_speed(r1) * (math.sqrt(2.0 * r2 / (r1 + r2)) - 1.0)
    dv2 = _circular_speed(r2) * (1.0 - math.sqrt(2.0 * r1 / (r1 + r2)))
    return dv1 + dv2, raise_m


def _orbit_thruster_isp(spacecraft) -> float | None:
    for block in (spacecraft.station_keeping, spacecraft.geo_station_keeping, spacecraft.constant_thrust):
        if block is not None:
            return block.isp_s
    return None


@dataclass
class RunContributors:
    """What the last run flew, per mission phase contributor."""

    run_days: float  # [day]
    scale: float  # [-] mission duration / run duration (>= 1 means scaled up)
    in_plane: tuple | None = None  # (delta-V [m/s], propellant [kg]) over the mission
    out_of_plane: tuple | None = None
    formation: tuple | None = None
    # How each was taken from the run, for its trace: {contributor: (delta-V series, its final value [m/s],
    # propellant series, propellant used [kg], share of it [-])}
    flown_from: dict = field(default_factory=dict, compare=False)


def _final(result, name: str) -> float | None:
    series = result.series.get(name)
    return float(series.data[-1, 0]) if series is not None and len(series.data) else None


def _used(result, name: str) -> float | None:
    series = result.series.get(name)
    return float(series.data[0, 0] - series.data[-1, 0]) if series is not None and len(series.data) else None


def run_contributors(result, spacecraft_name: str, mission_years: float) -> RunContributors | None:
    """Orbit control and formation keeping as flown in ``result``, scaled
    to ``mission_years`` when the run is shorter."""
    position = result.series.get(f"{spacecraft_name}.position_N")
    if position is None or len(position.time_s) < 2:
        return None
    run_s = float(position.time_s[-1] - position.time_s[0])  # [s]
    scale = mission_years * 365.25 * 86400.0 / run_s if run_s > 0.0 else 1.0
    prefix = spacecraft_name
    contributors = RunContributors(run_s / 86400.0, scale)

    sk_dv = _final(result, f"{prefix}.station_keeping.delta_v")
    pk_dv = _final(result, f"{prefix}.phasing_keeping.delta_v")
    if pk_dv is None:  # an ROE formation fires the same thruster (engine.roe_formation)
        pk_dv = _final(result, f"{prefix}.roe_formation.delta_v")
    sk_used = _used(result, f"{prefix}.station_keeping.propellant_remaining")
    if sk_dv is not None:
        # formation keeping fires the station-keeping thruster from the same tank: split by delta-V
        total_dv = sk_dv + (pk_dv or 0.0)
        share = sk_dv / total_dv if total_dv > 0.0 else 1.0
        contributors.in_plane = (sk_dv * scale, (sk_used or 0.0) * share * scale)
        tank = f"{prefix}.station_keeping.propellant_remaining"
        contributors.flown_from["in_plane"] = (f"{prefix}.station_keeping.delta_v", sk_dv, tank, sk_used or 0.0, share)
        if pk_dv is not None:
            contributors.formation = (pk_dv * scale, (sk_used or 0.0) * (1.0 - share) * scale)
            series = (f"{prefix}.phasing_keeping.delta_v" if f"{prefix}.phasing_keeping.delta_v" in result.series
                      else f"{prefix}.roe_formation.delta_v")
            contributors.flown_from["formation"] = (series, pk_dv, tank, sk_used or 0.0, 1.0 - share)
    ew_dv = _final(result, f"{prefix}.geo_station_keeping.east_west.delta_v")
    ns_dv = _final(result, f"{prefix}.geo_station_keeping.north_south.delta_v")
    geo_used = _used(result, f"{prefix}.geo_station_keeping.propellant_remaining")
    if ew_dv is not None and ns_dv is not None:
        total = ew_dv + ns_dv
        ew_share = ew_dv / total if total > 0.0 else 0.5
        contributors.in_plane = (ew_dv * scale, (geo_used or 0.0) * ew_share * scale)
        contributors.out_of_plane = (ns_dv * scale, (geo_used or 0.0) * (1.0 - ew_share) * scale)
        tank = f"{prefix}.geo_station_keeping.propellant_remaining"
        contributors.flown_from["in_plane"] = (f"{prefix}.geo_station_keeping.east_west.delta_v", ew_dv, tank,
                                               geo_used or 0.0, ew_share)
        contributors.flown_from["out_of_plane"] = (f"{prefix}.geo_station_keeping.north_south.delta_v", ns_dv, tank,
                                                   geo_used or 0.0, 1.0 - ew_share)
    return contributors


def _operational_sma_m(spacecraft) -> float:
    orbit = spacecraft.orbit
    if orbit.type == "classical_elements":
        return orbit.semi_major_axis_km * 1e3
    from .service import _orbit_ic_to_rv

    r_m, v_m_s = _orbit_ic_to_rv(MU_EARTH_M3_S2, orbit)
    r = math.sqrt(sum(x * x for x in r_m))
    v2 = sum(x * x for x in v_m_s)
    return 1.0 / (2.0 / r - v2 / MU_EARTH_M3_S2)


def uncontrolled_reentry_delta_v(scenario, spacecraft, eol_utc, mass_kg: float, target_years: float):
    """(delta-V [m/s], perigee [km], lifetime [year], notes, data files) of
    one apogee burn lowering the perigee until the orbit lifetime from
    ``eol_utc`` is ``target_years`` (Sec. 6.3.3), at MSFC's 50th
    percentile, Cd 2.2 and the tumbling average area (Secs. 5.9, 5.2,
    5.3). Zero when the orbit already decays in time. The data files are
    the space-weather files read (:func:`.lifetime.space_weather_files`);
    a replacement solver may return the first four only."""
    from . import lifetime as lt
    from .service import _orbit_ic_to_rv

    r_m, v_m_s = _orbit_ic_to_rv(lt.MU_EARTH_M3_S2, spacecraft.orbit)
    orbit = lt.mean_orbit_from_state(r_m, v_m_s)
    area_m2, _cd = lt.drag_properties(spacecraft)
    ballistic = rule("eol_drag_coeff", scenario) * area_m2 / mass_kg  # [m^2/kg]
    horizon_years = target_years * 1.5 + 1.0
    density, horizon_years, notes = lt.density_for_scenario(scenario, eol_utc, horizon_years,
                                                            forecast_percentile=rule("eol_percentile", scenario))
    files = getattr(density, "data_files", {})

    def years_from(start_orbit, horizon=horizon_years):
        result = lt.propagate_decay(start_orbit, eol_utc, ballistic, density, horizon, scenario=scenario)
        return result.lifetime_years if result.reentered else math.inf

    def in_time(start_orbit):  # stops at the target: no need to follow a slower decay further
        return years_from(start_orbit, min(horizon_years, target_years * 1.001)) <= target_years

    if in_time(orbit):
        return 0.0, orbit.perigee_altitude_km, years_from(orbit), notes, files
    low_km, high_km = lt.rule("reentry_altitude_km", scenario) + 20.0, orbit.perigee_altitude_km  # [km]
    while high_km - low_km > 2.0:  # [km]
        middle_km = 0.5 * (low_km + high_km)
        _dv, _kg, lowered = lt.deorbit_burn(orbit, middle_km, mass_kg, 1.0e9)
        if in_time(lowered):
            low_km = middle_km
        else:
            high_km = middle_km
    delta_v, _kg, lowered = lt.deorbit_burn(orbit, low_km, mass_kg, 1.0e9)
    return delta_v, low_km, years_from(lowered), notes, files


def _drag_makeup(scenario, spacecraft, start_utc, years, forecast_percentile, drag_coeff=None,
                 should_cancel=None):
    from . import lifetime as lt

    return lt.drag_makeup(scenario, spacecraft, start_utc, years, forecast_percentile, drag_coeff,
                          should_cancel=should_cancel)


def _estimates_in_plane(spacecraft) -> bool:
    """A LEO station keeper flying through drag."""
    return spacecraft.station_keeping is not None and spacecraft.enable_drag


# -- traces (engine.trace, transparency plan Phase 4a) ---------------------------------------------

_DELTA_V = "[m/s]"


def _entry(name: str, symbol: str, value, unit: str, field_name: str) -> Quantity:
    return Quantity(name, symbol, value, unit, f"scenario: propellant_budget.{field_name}")


def _rule_input(name: str, symbol: str, unit: str, parameter: str, scenario) -> Quantity:
    return Quantity(name, symbol, rule(parameter, scenario), unit, f"parameter: propellant_budget.{parameter}")


def _of(trace: Trace, symbol: str | None = None) -> Quantity:
    """``trace``'s result as an input of another trace."""
    return Quantity(trace.quantity, symbol or trace.symbol, trace.value, trace.unit, f"trace: {trace.quantity}")


def _entered_trace(contributor: str, value: float, field_name: str | None, unit: str = _DELTA_V,
                   symbol: str = "dV") -> Trace:
    if field_name is None:
        return Trace(contributor, symbol, value, unit, f"{symbol} = 0", "no value",
                     notes=("no value entered and none in the last run: counted as 0",))
    return Trace(contributor, symbol, value, unit, f"{symbol} = entered", "the scenario",
                 inputs=(_entry("entered", symbol, value, unit, field_name),))


def _flown_trace(contributor: str, value: float, kg: float | None, flown: RunContributors, key: str,
                 mission_years: float):
    """(delta-V trace, propellant trace or None) of a contributor taken from
    the last run (AD10 Sec. 6.2.7, "via simulation")."""
    scale = Quantity("mission over run duration", "k", flown.scale, "[-]",
                     f"computed: k = T_mission / T_run, T_mission = {mission_years:g} year, "
                     f"T_run = {flown.run_days:.6g} day")
    if key not in flown.flown_from:  # contributors given without the run's series (a caller's own)
        given = Trace(contributor, "dV", value, _DELTA_V, "dV = dV_run * k", "ESA AD10 Sec. 6.2.7 (via simulation)",
                      inputs=(Quantity("delta-V the run flew", "dV_run", value / flown.scale, _DELTA_V,
                                       "last run: as given, the series not named"), scale))
        return given, None if kg is None else Trace(
            f"{contributor}, propellant", "m_p", kg, "[kg]", "m_p = entered", "ESA AD10 Sec. 6.2.7 (via simulation)",
            inputs=(Quantity("propellant the run used, scaled", "m_p", kg, "[kg]",
                             "last run: as given, the series not named"),))
    series, run_dv, tank, used_kg, share = flown.flown_from[key]
    dv_trace = Trace(contributor, "dV", value, _DELTA_V, "dV = dV_run * k", "ESA AD10 Sec. 6.2.7 (via simulation)",
                     inputs=(Quantity("delta-V the run flew", "dV_run", run_dv, _DELTA_V, f"last run: {series}"),
                             scale))
    if kg is None:
        return dv_trace, None
    kg_trace = Trace(f"{contributor}, propellant", "m_p", kg, "[kg]", "m_p = dm_tank * s * k",
                     "ESA AD10 Sec. 6.2.7 (via simulation)",
                     inputs=(Quantity("propellant the run used from the tank", "dm_tank", used_kg, "[kg]",
                                      f"last run: {tank}, first minus last"),
                             Quantity("this contributor's share of the tank, by delta-V", "s", share, "[-]",
                                      "computed: from the run's delta-V of each controller firing the thruster"),
                             scale))
    return dv_trace, kg_trace


def compute_budget(scenario, spacecraft_name: str, result=None, run_scenario=None,
                   reentry_solver=uncontrolled_reentry_delta_v, in_plane: tuple | None = None,
                   makeup=_drag_makeup, flown: RunContributors | None = None) -> Budget:
    """The budget of one spacecraft (see this module's docstring).
    ``result``/``run_scenario``: the last run and the scenario it ran,
    for the simulated contributors; ``in_plane``: (delta-V [m/s],
    propellant [kg] or None, source, note) in place of the entered, flown
    or estimated in-plane control; ``flown``: the run's contributors
    already taken out of ``result`` (:func:`run_contributors`);
    ``reentry_solver`` and ``makeup`` (:func:`.lifetime.drag_makeup`) are
    replaceable for tests."""
    spacecraft = next((sc for sc in scenario.spacecraft if sc.name == spacecraft_name), None)
    if spacecraft is None:
        raise BudgetError(f"no spacecraft named {spacecraft_name!r}")
    config = spacecraft.propellant_budget or PropellantBudgetConfig()
    isp_s = config.isp_s or _orbit_thruster_isp(spacecraft)
    if not isp_s:
        raise BudgetError(f"{spacecraft_name}: set propellant_budget.isp_s, or give it an orbit thruster")
    efficiency = thruster_efficiency(config)
    exhaust_m_s = efficiency * isp_s * G0_M_S2  # [m/s]
    dry_kg = spacecraft.dry_mass_kg * (1.0 if config.dry_mass_includes_margin else 1.0 + config.system_margin_fraction)
    a_m = _operational_sma_m(spacecraft)
    notes: list[str] = []
    data_files: dict = {}
    traces = {
        "efficiency": Trace("Thruster efficiency", "eta", efficiency, "[-]",
                            "eta = cos(alpha) * cos(beta) * eta_plume * eta_mod", "ESA AD10 Sec. 5.11",
                            inputs=(_entry("thrust angle", "alpha", config.thrust_angle_deg, "[deg]", "thrust_angle_deg"),
                                    _entry("misalignment", "beta", config.misalignment_deg, "[deg]", "misalignment_deg"),
                                    _entry("plume efficiency", "eta_plume", config.plume_efficiency, "[-]",
                                           "plume_efficiency"),
                                    _entry("modulation efficiency", "eta_mod", config.modulation_efficiency, "[-]",
                                           "modulation_efficiency"))),
        "dry_mass": Trace("Dry mass with the system margin", "m_dry", dry_kg, "[kg]",
                          "m_dry = m_sc" if config.dry_mass_includes_margin else "m_dry = m_sc * (1 + f_sys)",
                          "ESA AD10 Sec. 5.10",
                          inputs=(Quantity("the spacecraft's dry mass", "m_sc", spacecraft.dry_mass_kg, "[kg]",
                                           "scenario: dry_mass_kg"),
                                  _entry("system margin", "f_sys", config.system_margin_fraction, "[-]",
                                         "system_margin_fraction")),
                          notes=("the dry mass entered already includes the margin",)
                          if config.dry_mass_includes_margin else ()),
    }
    isp_source = ("scenario: propellant_budget.isp_s" if config.isp_s
                  else "scenario: the orbit thruster's isp_s (station_keeping, geo_station_keeping or constant_thrust)")
    traces["exhaust_speed"] = Trace("Effective exhaust speed", "Ve", exhaust_m_s, _DELTA_V, "Ve = eta * Isp * g0",
                                    "ESA AD10 Sec. 5.11",
                                    inputs=(_of(traces["efficiency"]),
                                            Quantity("specific impulse", "Isp", isp_s, "[s]", isp_source),
                                            Quantity("standard gravity", "g0", G0_M_S2, "[m/s^2]",
                                                     "constant: STANDARD_GRAVITY_M_S2")))
    q_a = Quantity("operational semi-major axis", "a", a_m, "[m]",
                   "scenario: orbit.semi_major_axis_km" if spacecraft.orbit.type == "classical_elements"
                   else "computed: from the scenario's initial state")
    q_v = Quantity("circular speed at a", "v", _circular_speed(a_m), _DELTA_V,
                   f"computed: v = sqrt(mu / a), mu = {MU_EARTH_M3_S2:.10g} m^3/s^2 (constant: EARTH_GM_M3_S2)")
    # The rules and margins in effect (config.parameters, "propellant_budget").
    operations_percentile = rule("operations_percentile", scenario)  # [%]
    operations_cd = rule("operations_drag_coeff", scenario)  # [-]
    scaled_ratio = rule("scaled_run_ratio", scenario)  # [-]
    cam_factor = rule("cam_count_factor", scenario)  # [-]
    attitude_factor = rule("attitude_propellant_factor", scenario)  # [-]
    last_burn_margin = rule("controlled_last_burn_margin", scenario)  # [-]
    residual = rule("residual_fraction", scenario)  # [-]
    uncertainty = rule("uncertainty_fraction", scenario)  # [-]
    convergence_kg = rule("convergence_kg", scenario)  # [kg]
    max_iterations = rule("max_iterations", scenario)

    if flown is None and result is not None:
        flown = run_contributors(result, spacecraft_name, config.mission_years)
    if flown is not None:
        if flown.scale > scaled_ratio:
            notes.append(f"the last run covered {flown.run_days:.0f} days; its orbit control is scaled "
                         f"x{flown.scale:.1f} to {config.mission_years:g} years -- run the whole mission for "
                         "an AD10 budget")
        settings = run_scenario or scenario
        run_sc = next((sc for sc in settings.spacecraft if sc.name == spacecraft_name), spacecraft)
        if settings.space_weather.forecast_percentile != operations_percentile:
            notes.append(f"the last run used MSFC's {settings.space_weather.forecast_percentile:g}th percentile; "
                         f"AD10 Sec. 5.9 asks for the {operations_percentile:g}th for operations")
        if run_sc.enable_drag and run_sc.drag_coeff != operations_cd and not run_sc.facets:
            notes.append(f"the last run used Cd {run_sc.drag_coeff:g}; AD10 Sec. 5.2 asks for "
                         f"{operations_cd:g} in operations (2.2 for CubeSats)")

    def simulated(entered, flown_pair, label, contributor, field_name, key):
        """(delta-V, propellant or None, source, delta-V trace, propellant trace or None)"""
        if entered is not None:
            return entered, None, "input", _entered_trace(contributor, entered, field_name), None
        if flown_pair is not None:
            dv_trace, kg_trace = _flown_trace(contributor, flown_pair[0], flown_pair[1], flown, key,
                                              config.mission_years)
            return (flown_pair[0], flown_pair[1], "last run, scaled" if flown.scale > scaled_ratio else "last run",
                    dv_trace, kg_trace)
        if label:
            notes.append(f"{label}: no value entered and none in the last run -- counted as 0")
        return 0.0, None, "input", _entered_trace(contributor, 0.0, None), None

    if in_plane is not None:
        ip_dv, ip_kg, ip_source, ip_note = in_plane
        if ip_note:
            notes.append(ip_note)
        ip_trace = Trace("In-plane orbit control", "dV", ip_dv, _DELTA_V,
                         f"dV = the launch-delay sweep's or altitude trade's figure for this case ({ip_source})",
                         "ESA AD10 Sec. 5.5", notes=(ip_note,) if ip_note else ())
        ip_kg_trace = None
    elif (config.in_plane_control_delta_v_m_s is None and (flown is None or flown.in_plane is None)
          and _estimates_in_plane(spacecraft) and scenario.gravity.central_body == "earth"):
        estimate = makeup(scenario, spacecraft, _parse_epoch(scenario.epoch_utc), config.mission_years,
                          operations_percentile)
        ip_dv, ip_kg, ip_source = estimate.delta_v_m_s, None, "estimated"
        ip_kg_trace = None
        ip_trace = Trace("In-plane orbit control", "dV", ip_dv, _DELTA_V,
                         "dV = sum over the mission of |a_drag| * dt, on the held orbit (engine.lifetime.drag_makeup)",
                         "SpaceMissionStudio's estimate (docs/models/propellant-budget.md, \"Estimated\")",
                         inputs=(Quantity("held altitude", "h", estimate.altitude_km, "[km]",
                                          "scenario: station_keeping.target_altitude_km"),
                                 _entry("mission duration", "T", config.mission_years, "[year]", "mission_years"),
                                 _rule_input("solar activity: MSFC percentile", "P", "[%]", "operations_percentile",
                                             scenario),
                                 Quantity("drag coefficient", "Cd", lifetime_cd(spacecraft), "[-]",
                                          "scenario: drag_coeff (or the facets')")),
                         notes=("full station-keeping runs spent about 5 % more; run the mission for the simulated "
                                "figure",))
        data_files.update(getattr(estimate, "data_files", {}))
        notes.append(f"in-plane control estimated from the drag at {estimate.altitude_km:.0f} km (NRLMSISE-00, "
                     f"MSFC {operations_percentile:g}th percentile, Cd {lifetime_cd(spacecraft):g}); full runs "
                     "spent ~5% more -- run the mission for the simulated figure")
        if lifetime_cd(spacecraft) != operations_cd:
            notes.append(f"the estimate uses Cd {lifetime_cd(spacecraft):g}; AD10 Sec. 5.2 asks for "
                         f"{operations_cd:g} in operations (2.2 for CubeSats)")
        notes.extend(f"in-plane estimate: {w}" for w in estimate.warnings)
    else:
        ip_dv, ip_kg, ip_source, ip_trace, ip_kg_trace = simulated(
            config.in_plane_control_delta_v_m_s, flown and flown.in_plane,
            "in-plane control" if spacecraft.station_keeping or spacecraft.geo_station_keeping else "",
            "In-plane orbit control", "in_plane_control_delta_v_m_s", "in_plane")
    oop_dv, oop_kg, oop_source, oop_trace, oop_kg_trace = simulated(
        config.out_of_plane_control_delta_v_m_s, flown and flown.out_of_plane, "", "Out-of-plane orbit control",
        "out_of_plane_control_delta_v_m_s", "out_of_plane")
    form_dv, form_kg, form_source, form_trace, form_kg_trace = simulated(
        config.formation_delta_v_m_s, flown and flown.formation,
        "formation keeping" if spacecraft.phasing_keeping or spacecraft.roe_formation else "",
        "Constellation/formation keeping", "formation_delta_v_m_s", "formation")
    lie_ip, lie_oop = injection_delta_v(config, a_m)
    v_m_s = q_v.value
    lie_ip_trace = Trace("Launcher injection errors, in-plane", "dV", lie_ip, _DELTA_V,
                         "dV = max(v * da / (2 a), v * de / 2)", "ESA AD10 Sec. 6.1.1",
                         inputs=(_entry("injection error in semi-major axis", "da", config.injection_sma_error_km * 1e3,
                                        "[m]", "injection_sma_error_km"),
                                 _entry("injection error in eccentricity", "de", config.injection_eccentricity_error,
                                        "[-]", "injection_eccentricity_error"),
                                 q_a, q_v),
                         intermediates=(Quantity("semi-major-axis correction, two burns", "dV_a",
                                                 v_m_s * config.injection_sma_error_km * 1e3 / (2.0 * a_m), _DELTA_V,
                                                 "computed"),
                                        Quantity("eccentricity-vector correction, two burns", "dV_e",
                                                 v_m_s * config.injection_eccentricity_error / 2.0, _DELTA_V,
                                                 "computed")))
    lie_oop_trace = Trace("Launcher injection errors, out-of-plane", "dV", lie_oop, _DELTA_V,
                          "dV = 2 v sin(di / 2)", "ESA AD10 Sec. 6.1.1",
                          inputs=(_entry("injection error in inclination", "di", config.injection_inclination_error_deg,
                                         "[deg]", "injection_inclination_error_deg"), q_a, q_v))
    cam_count = config.collision_avoidance_count * cam_factor
    cam_sma_m = rule("cam_sma_change_m", scenario)  # [m]
    cam_dv = cam_count * collision_avoidance_delta_v(a_m, cam_sma_m)
    cam_trace = Trace(f"Collision avoidance ({config.collision_avoidance_count:g} x {cam_factor:g})", "dV", cam_dv,
                      _DELTA_V, "dV = N * f * 2 * v * dA / (2 a)   (dA up, then back)", "ESA AD10 Secs. 6.2.4, 5.6",
                      inputs=(_entry("collision avoidances entered", "N", config.collision_avoidance_count, "[-]",
                                     "collision_avoidance_count"),
                              _rule_input("margin on the count", "f", "[-]", "cam_count_factor", scenario),
                              _rule_input("semi-major-axis change of one avoidance", "dA", "[m]", "cam_sma_change_m",
                                          scenario),
                              q_a, q_v))
    if config.collision_avoidance_count == 0.0:
        notes.append("no collision avoidances entered -- AD10 Sec. 6.2.4 takes their number from ESA's DRAMA")
    notes.append(f"residual and uncertainty are {residual * 100:g}% and {uncertainty * 100:g}% of the tank load "
                 "(AD10 Secs. 5.8, 6.4; its summary table prints 10% and 20%)")

    eol_utc = _parse_epoch(scenario.epoch_utc) + timedelta(days=config.mission_years * 365.25)
    reentry = None  # computed once: (delta-V, perigee, lifetime)
    propellant_kg = config.tank_capacity_kg  # [kg] initial guess (Sec. 6)
    rows: list[BudgetRow] = []
    initial_kg = propellant_kg  # [kg]
    for iteration in range(1, max_iterations + 1):
        rows = []
        load_kg = propellant_kg  # [kg] this iteration's propellant load
        mass = dry_kg + propellant_kg  # beginning of life

        def add(phase, contributor, delta_v, kg=None, margin="-", source="computed", trace=None, kg_trace=None):
            nonlocal mass  # each contributor burns from what the ones before it left
            if kg is None:
                kg = propellant_for(mass, delta_v, exhaust_m_s)
                above = sum(r.propellant_kg for r in rows)  # [kg]
                kg_trace = Trace(f"{contributor}, propellant", "m_p", kg, "[kg]", "m_p = m * (1 - exp(-dV / Ve))",
                                 "ESA AD10 Secs. 6.1.3, 6.2.7, 6.3.4",
                                 inputs=(_of(trace), _of(traces["exhaust_speed"])),
                                 intermediates=(Quantity("mass before the burn", "m", mass, "[kg]",
                                                         f"computed: m = m_dry + m_load - m_above, m_dry = {dry_kg:.10g} kg, "
                                                         f"m_load = {load_kg:.10g} kg (iteration {iteration}), "
                                                         f"m_above = {above:.10g} kg (the rows above)"),))
            rows.append(BudgetRow(phase, contributor, delta_v, kg, margin, source, trace, kg_trace))
            mass -= kg

        phase = "Beginning of life"
        add(phase, "Launcher injection errors, in-plane", lie_ip, trace=lie_ip_trace)
        add(phase, "Launcher injection errors, out-of-plane", lie_oop, trace=lie_oop_trace)
        if config.injection_raan_delta_v_m_s:
            add(phase, "Launcher injection errors, RAAN", config.injection_raan_delta_v_m_s, source="input",
                trace=_entered_trace("Launcher injection errors, RAAN", config.injection_raan_delta_v_m_s,
                                     "injection_raan_delta_v_m_s"))
        add(phase, "Orbit acquisition", config.orbit_acquisition_delta_v_m_s, source="input",
            trace=_entered_trace("Orbit acquisition", config.orbit_acquisition_delta_v_m_s,
                                 "orbit_acquisition_delta_v_m_s"))

        phase = "Operations"
        add(phase, "Orbit transfers", config.transfer_delta_v_m_s, source="input",
            trace=_entered_trace("Orbit transfers", config.transfer_delta_v_m_s, "transfer_delta_v_m_s"))
        add(phase, "In-plane orbit control", ip_dv, ip_kg, source=ip_source, trace=ip_trace, kg_trace=ip_kg_trace)
        add(phase, "Out-of-plane orbit control", oop_dv, oop_kg, source=oop_source, trace=oop_trace,
            kg_trace=oop_kg_trace)
        add(phase, f"Collision avoidance ({config.collision_avoidance_count:g} x {cam_factor:g})", cam_dv,
            margin=f"x{cam_factor:g} count", source="computed", trace=cam_trace)
        add(phase, "Constellation/formation keeping", form_dv, form_kg, source=form_source, trace=form_trace,
            kg_trace=form_kg_trace)
        attitude_kg = config.attitude_thruster_propellant_kg * attitude_factor  # [kg]
        add(phase, "Attitude control by thrusters", None, attitude_kg,
            margin=f"+{(attitude_factor - 1.0) * 100:g}% propellant", source="input",
            kg_trace=Trace("Attitude control by thrusters, propellant", "m_p", attitude_kg, "[kg]",
                           "m_p = m_att * f", "ESA AD10 Sec. 5.6",
                           inputs=(_entry("attitude-control propellant entered", "m_att",
                                          config.attitude_thruster_propellant_kg, "[kg]",
                                          "attitude_thruster_propellant_kg"),
                                   _rule_input("margin", "f", "[-]", "attitude_propellant_factor", scenario))))
        if config.hall_thruster_ignition_kg:
            add(phase, "Hall thruster ignitions", None, config.hall_thruster_ignition_kg, source="input",
                kg_trace=_entered_trace("Hall thruster ignitions, propellant", config.hall_thruster_ignition_kg,
                                        "hall_thruster_ignition_kg", "[kg]", "m_p"))

        phase = "End of life"
        if config.clearance_sma_drop_km:
            label = f"Clearance ({config.clearance_sma_drop_km:g} km lower)"
            clearance = clearance_delta_v(a_m, config.clearance_sma_drop_km)
            add(phase, label, clearance,
                trace=Trace(label, "dV", clearance, _DELTA_V, "dV = v * dA / (2 a)", "ESA AD10 Sec. 6.3.2",
                            inputs=(_entry("semi-major-axis drop", "dA", config.clearance_sma_drop_km * 1e3, "[m]",
                                           "clearance_sma_drop_km"), q_a, q_v)))
        if config.disposal == "uncontrolled_reentry":
            if reentry is None:
                left_kg = dry_kg + (residual + uncertainty) * max(propellant_kg, 0.0)
                reentry_iteration = iteration
                dv, perigee_km, years, reentry_notes, *read = reentry_solver(scenario, spacecraft, eol_utc, left_kg,
                                                                             config.disposal_lifetime_years)
                reentry = (dv, perigee_km, years)
                for files in read:  # the data files, when the solver names them
                    data_files.update(files)
                notes.extend(f"disposal: {n}" for n in reentry_notes)
            label = (f"Uncontrolled re-entry (no burn: re-enters in {reentry[2]:.1f} y)" if reentry[0] == 0.0
                     else f"Uncontrolled re-entry (perigee to {reentry[1]:.0f} km: {reentry[2]:.1f} y)")
            add(phase, label, reentry[0], trace=Trace(
                label, "dV", reentry[0], _DELTA_V,
                "dV = 0: the orbit already re-enters within T" if reentry[0] == 0.0 else
                "dV: the apogee burn lowering the perigee to h_p, the highest perigee (to 2 km) from which the "
                "orbit's lifetime from the end of the mission is at most T (engine.lifetime)",
                "ESA AD10 Secs. 6.3.3, 6.3.1.2, 5.2, 5.3, 5.9",
                inputs=(_entry("disposal lifetime", "T", config.disposal_lifetime_years, "[year]",
                               "disposal_lifetime_years"),
                        Quantity("mass at the end of the mission", "m_EOL", left_kg, "[kg]",
                                 f"computed: m_dry + (f_res + f_unc) * m_load, iteration {reentry_iteration}"),
                        _rule_input("drag coefficient", "Cd", "[-]", "eol_drag_coeff", scenario),
                        _rule_input("solar activity: MSFC percentile", "P", "[%]", "eol_percentile", scenario),
                        Quantity("end of the mission", "t_EOL", eol_utc.isoformat(), "[UTC]",
                                 "computed: epoch + propellant_budget.mission_years")),
                intermediates=(Quantity("perigee at the end of the mission" if reentry[0] == 0.0
                                        else "perigee after the burn", "h_p", reentry[1], "[km]",
                                        "computed: the mean orbit" if reentry[0] == 0.0 else "computed: bisection"),
                               Quantity("lifetime from there", "L", reentry[2], "[year]", "computed: engine.lifetime"))))
        elif config.disposal == "controlled_reentry":
            last = config.controlled_reentry_last_burn_m_s * (1.0 + last_burn_margin)
            total = config.controlled_reentry_delta_v_m_s + last  # [m/s]
            add(phase, "Controlled re-entry", total,
                margin=f"+{last_burn_margin * 100:g}% on the last burn", source="input",
                trace=Trace("Controlled re-entry", "dV", total, _DELTA_V, "dV = dV_before + dV_last * (1 + f)",
                            "ESA AD10 Sec. 5.6",
                            inputs=(_entry("delta-V before the last burn", "dV_before",
                                           config.controlled_reentry_delta_v_m_s, _DELTA_V,
                                           "controlled_reentry_delta_v_m_s"),
                                    _entry("last burn", "dV_last", config.controlled_reentry_last_burn_m_s, _DELTA_V,
                                           "controlled_reentry_last_burn_m_s"),
                                    _rule_input("margin on the last burn", "f", "[-]", "controlled_last_burn_margin",
                                                scenario))))
        elif config.disposal == "graveyard":
            dv, raise_m = graveyard_delta_v(a_m, spacecraft.srp_coeff, spacecraft.srp_area_m2, dry_kg, scenario)
            label = f"Graveyard orbit (+{raise_m / 1e3:.0f} km)"
            r2 = a_m + raise_m  # [m]
            add(phase, label, dv, trace=Trace(
                label, "dV", dv, _DELTA_V,
                "dr = dr0 + k * Cr * A / m_dry;  dV = v1 (sqrt(2 r2 / (r1 + r2)) - 1) + v2 (1 - sqrt(2 r1 / (r1 + r2)))"
                ", r1 = a, r2 = a + dr", "ESA AD10 Sec. 6.3.1.3",
                inputs=(_rule_input("base raise", "dr0", "[m]", "geo_graveyard_base_m", scenario),
                        _rule_input("raise per area-to-mass", "k", "[m per (m^2/kg)]", "geo_graveyard_per_cr_a_m",
                                    scenario),
                        Quantity("radiation-pressure coefficient", "Cr", spacecraft.srp_coeff, "[-]",
                                 "scenario: srp_coeff"),
                        Quantity("radiation-pressure area", "A", spacecraft.srp_area_m2, "[m^2]",
                                 "scenario: srp_area_m2"),
                        _of(traces["dry_mass"]), q_a),
                intermediates=(Quantity("raise", "dr", raise_m, "[m]", "computed"),
                               Quantity("circular speed at r1", "v1", _circular_speed(a_m), _DELTA_V, "computed"),
                               Quantity("circular speed at r2", "v2", _circular_speed(r2), _DELTA_V, "computed"))))

        tank_kg = config.tank_capacity_kg or propellant_kg
        tank = (_entry("tank capacity", "m_tank", tank_kg, "[kg]", "tank_capacity_kg") if config.tank_capacity_kg
                else Quantity("tank load: this iteration's total", "m_tank", tank_kg, "[kg]",
                              f"computed: iteration {iteration} (no tank_capacity_kg entered)"))
        for contributor, fraction, parameter, clause in (
                ("Residual", residual, "residual_fraction", "ESA AD10 Sec. 5.8"),
                ("Loading uncertainty and gauging", uncertainty, "uncertainty_fraction", "ESA AD10 Sec. 6.4")):
            rows.append(BudgetRow("Propellant", contributor, None, fraction * tank_kg, f"{fraction * 100:g}% of tank",
                                  "computed", None,
                                  Trace(f"{contributor}, propellant", "m_p", fraction * tank_kg, "[kg]",
                                        "m_p = f * m_tank", clause,
                                        inputs=(_rule_input("fraction of the tank", "f", "[-]", parameter, scenario),
                                                tank))))
        new_kg = sum(r.propellant_kg for r in rows)
        converged = abs(new_kg - propellant_kg) < convergence_kg
        propellant_kg = new_kg
        if converged:
            break
    else:
        notes.append(f"the propellant total did not settle within {max_iterations} iterations")
    if config.tank_capacity_kg and propellant_kg > config.tank_capacity_kg:
        notes.append(f"the budget ({propellant_kg:.2f} kg) exceeds the tank ({config.tank_capacity_kg:g} kg)")
    traces["total_propellant"] = Trace(
        "Propellant", "m_p", sum(r.propellant_kg for r in rows), "[kg]",
        "m_p = sum of the rows' propellant; iterated from m_p0, each iteration's load the last one's total, until it "
        "changes by less than e", "ESA AD10 Sec. 6.5",
        inputs=(Quantity("starting load", "m_p0", initial_kg, "[kg]",
                         "scenario: propellant_budget.tank_capacity_kg (0: none entered)"),
                _rule_input("convergence", "e", "[kg]", "convergence_kg", scenario),
                _rule_input("most iterations", "n_max", "[-]", "max_iterations", scenario)),
        intermediates=(Quantity("iterations", "n", iteration, "[-]", "computed"),))
    return Budget(rows, dry_kg, isp_s, efficiency, iteration, notes, data_files, traces)


def lifetime_cd(spacecraft) -> float:
    """The drag coefficient the drag estimates use (the facets' area-
    weighted mean when set)."""
    if spacecraft.facets:
        total = sum(f.area_m2 for f in spacecraft.facets)  # [m^2]
        return round(sum(f.area_m2 * f.drag_coeff for f in spacecraft.facets) / total, 6)
    return spacecraft.drag_coeff


@dataclass
class DelayCase:
    """The budget for one launch date (:func:`launch_delay_sweep`)."""

    delay_years: float  # [year]
    launch_utc: datetime
    budget: Budget
    drag_ratio: float | None = None  # [-] drag make-up against the planned launch, when used

    def delta_v_of(self, phase: str, contributor_start: str) -> float:
        return sum(r.delta_v_m_s or 0.0 for r in self.budget.rows
                   if r.phase == phase and r.contributor.startswith(contributor_start))


@dataclass
class LaunchDelaySweep:
    spacecraft_name: str
    cases: list[DelayCase]
    notes: list[str] = field(default_factory=list)

    @property
    def worst(self) -> DelayCase:
        """The launch date needing the most propellant."""
        return max(self.cases, key=lambda case: case.budget.total_propellant_kg)


def _years_later(when: datetime, years: float) -> datetime:
    """``when`` moved by whole calendar years (same date and time of day:
    the Sun is back where it was, so an SSO's local time is kept; 29 Feb
    becomes 28 Feb), plus any fraction as 365.25-day years."""
    whole = int(math.floor(years))
    try:
        moved = when.replace(year=when.year + whole)
    except ValueError:  # 29 February
        moved = when.replace(year=when.year + whole, day=28)
    return moved + timedelta(days=(years - whole) * 365.25)


def years_late(delay_years: float) -> str:
    """"planned launch", "1 year late", "2.5 years late"."""
    if delay_years == 0.0:
        return "planned launch"
    return f"{delay_years:g} year{'' if delay_years == 1.0 else 's'} late"


def _launched_later(scenario, years: float):
    import copy

    later = copy.deepcopy(scenario)
    later.epoch_utc = _years_later(_parse_epoch(scenario.epoch_utc), years).isoformat()
    return later


def launch_delay_sweep(scenario, spacecraft_name: str, result=None, run_scenario=None,
                       delays_years=None, reentry_solver=uncontrolled_reentry_delta_v,
                       makeup=_drag_makeup, progress: Callable[[float, str], None] | None = None,
                       should_cancel: Callable[[], bool] | None = None, flown: RunContributors | None = None,
                       reference_drag_m_s: float | None = None) -> LaunchDelaySweep:
    """The budget for the planned launch and for launches ``delays_years``
    later (Sec. 5.5: up to 5 years), the mission keeping its length.

    In-plane control of a LEO station keeper follows each window's solar
    activity: the last run's figure (or the entered one) times the drag
    make-up of the delayed window over the planned one, both at the run's
    own percentile and drag coefficient; with neither, the drag estimate
    itself at the 95th percentile. Other entered and flown contributors
    are kept; the disposal is re-solved from each end of life.

    ``flown``: the run's contributors already taken out of ``result``.
    ``reference_drag_m_s``: the drag make-up of the orbit and launch the
    entered or flown figure belongs to, when that is not this scenario's
    planned launch (:func:`altitude_trade`); every case is then scaled
    against it."""
    spacecraft = next((sc for sc in scenario.spacecraft if sc.name == spacecraft_name), None)
    if spacecraft is None:
        raise BudgetError(f"no spacecraft named {spacecraft_name!r}")
    config = spacecraft.propellant_budget or PropellantBudgetConfig()
    if delays_years is None:
        delays_years = rule("launch_delays_years", scenario)
    delays = sorted(set(float(d) for d in delays_years) | {0.0})
    notes: list[str] = []
    steps = len(delays) * 2  # a drag estimate and a budget per launch date
    done = [0]

    def advance(label):
        if should_cancel is not None and should_cancel():
            raise BudgetError("cancelled")
        if progress is not None:
            progress(done[0] / steps, label)
        done[0] += 1

    if flown is None and result is not None:
        flown = run_contributors(result, spacecraft_name, config.mission_years)
    reference = None  # (delta-V [m/s], propellant [kg] or None, source) the ratios scale
    if config.in_plane_control_delta_v_m_s is not None:
        reference = (config.in_plane_control_delta_v_m_s, None, "input")
    elif flown is not None and flown.in_plane is not None:
        reference = (flown.in_plane[0], flown.in_plane[1], "last run")
    follows_drag = _estimates_in_plane(spacecraft) and scenario.gravity.central_body == "earth"
    if reference is not None:
        settings = run_scenario or scenario
        run_sc = next((sc for sc in settings.spacecraft if sc.name == spacecraft_name), spacecraft)
        percentile, drag_coeff = settings.space_weather.forecast_percentile, lifetime_cd(run_sc)
    else:
        percentile, drag_coeff = rule("operations_percentile", scenario), lifetime_cd(spacecraft)
    if not follows_drag:
        notes.append("no drag-driven station keeping: in-plane control is the same for every launch date")

    base_drag = reference_drag_m_s  # [m/s]
    cases: list[DelayCase] = []
    for delay in delays:
        later = _launched_later(scenario, delay)
        launch_utc = _parse_epoch(later.epoch_utc)
        advance(f"drag for a launch {years_late(delay)}" if delay else "drag for the planned launch")
        in_plane, ratio = None, None
        if follows_drag:
            later_sc = next(sc for sc in later.spacecraft if sc.name == spacecraft_name)
            estimate = makeup(later, later_sc, launch_utc, config.mission_years, percentile, drag_coeff,
                              should_cancel)
            notes.extend(w for w in estimate.warnings if w not in notes)
            if base_drag is None:
                base_drag = estimate.delta_v_m_s
            ratio = estimate.delta_v_m_s / base_drag if base_drag > 0.0 else 1.0
            if reference is None:
                in_plane = (estimate.delta_v_m_s, None, "estimated", "")
            elif delay == 0.0 and reference_drag_m_s is None:
                in_plane = None  # the planned launch is the plain budget
            else:
                dv, _kg, source = reference  # propellant from this launch's own mass, not scaled
                in_plane = (dv * ratio, None, f"{source} x{ratio:.2f} (drag)", "")
        advance(f"budget for a launch {years_late(delay)}" if delay else "budget for the planned launch")
        # the run's other contributors are kept as flown
        budget = compute_budget(later, spacecraft_name, None, run_scenario, reentry_solver, in_plane, makeup, flown)
        cases.append(DelayCase(delay, launch_utc, budget, ratio))
    if progress is not None:
        progress(1.0, "done")
    if reference is not None and follows_drag:
        notes.append(f"in-plane control scaled by each window's drag make-up (NRLMSISE-00, MSFC "
                     f"{percentile:g}th percentile, Cd {drag_coeff:g}) against the planned launch")
    elif follows_drag:
        notes.append(f"in-plane control estimated from the drag (NRLMSISE-00, MSFC {percentile:g}th "
                     "percentile); full runs spent ~5% more")
    worst = max(cases, key=lambda case: case.budget.total_propellant_kg)
    notes.append(f"worst case: launch {worst.launch_utc:%Y-%m-%d} ({years_late(worst.delay_years)}), "
                 f"{worst.budget.total_propellant_kg:.2f} kg")
    tank = config.tank_capacity_kg
    if tank and worst.budget.total_propellant_kg > tank:
        notes.append(f"the worst case exceeds the tank ({tank:g} kg)")
    return LaunchDelaySweep(spacecraft_name, cases, notes)


@dataclass
class AltitudeCase:
    """The launch-delay sweep at one operational altitude (:func:`altitude_trade`)."""

    altitude_km: float  # [km] above the equatorial radius
    inclination_deg: float  # [deg] (re-set for a Sun-synchronous orbit)
    sweep: LaunchDelaySweep

    @property
    def worst(self) -> DelayCase:
        return self.sweep.worst


@dataclass
class AltitudeTrade:
    spacecraft_name: str
    tank_kg: float | None  # [kg] what the worst case is held against
    altitudes: list[AltitudeCase]
    notes: list[str] = field(default_factory=list)

    def fits(self, case: AltitudeCase) -> bool | None:
        """Whether the worst launch date's propellant fits the tank."""
        return None if not self.tank_kg else case.worst.budget.total_propellant_kg <= self.tank_kg

    @property
    def lowest_fitting(self) -> AltitudeCase | None:
        fitting = [case for case in self.altitudes if self.fits(case)]
        return min(fitting, key=lambda case: case.altitude_km) if fitting else None


def default_altitudes_km(altitude_km: float, scenario=None) -> list[float]:
    """Five altitudes around ``altitude_km`` [km], ``altitude_step_km``
    apart (50 km), from ``altitude_floor_km`` (250 km) up, as in effect for
    ``scenario``."""
    step_km, floor_km = rule("altitude_step_km", scenario), rule("altitude_floor_km", scenario)  # [km]
    centre = step_km * round(altitude_km / step_km)
    low = max(floor_km, centre - 2.0 * step_km)  # [km]
    return [low + k * step_km for k in range(5)]


def _at_altitude(scenario, spacecraft_name: str, altitude_km: float):
    """``scenario`` with the spacecraft's orbit (and station-keeping
    target) at ``altitude_km``; a Sun-synchronous inclination is re-set
    for the new altitude, so the orbit stays Sun-synchronous."""
    import copy

    from .orbit_design import sun_synchronous_inclination_deg

    moved = copy.deepcopy(scenario)
    spacecraft = next(sc for sc in moved.spacecraft if sc.name == spacecraft_name)
    orbit = spacecraft.orbit
    if orbit.type != "classical_elements":
        raise BudgetError(f"{spacecraft_name}: an altitude trade needs the orbit as classical elements")
    try:
        was_sso = abs(orbit.inclination_deg - sun_synchronous_inclination_deg(
            orbit.semi_major_axis_km, orbit.eccentricity)) < 0.05  # [deg]
    except ValueError:  # no Sun-synchronous inclination at that altitude
        was_sso = False
    orbit.semi_major_axis_km = REQ_EARTH_M / 1e3 + altitude_km  # [km]
    if was_sso:
        orbit.inclination_deg = sun_synchronous_inclination_deg(orbit.semi_major_axis_km, orbit.eccentricity)
    if spacecraft.station_keeping is not None:
        spacecraft.station_keeping.target_altitude_km = altitude_km
    return moved, orbit.inclination_deg


def _sweep_at(job):
    """One altitude's sweep: a process-pool job, so module-level."""
    scenario, name, altitude_km, run_scenario, delays, flown, reference_drag = job[:7]
    solvers = job[7] if len(job) > 7 else {}
    moved, inclination = _at_altitude(scenario, name, altitude_km)
    sweep = launch_delay_sweep(moved, name, None, run_scenario, delays, flown=flown,
                               reference_drag_m_s=reference_drag, **solvers)
    return AltitudeCase(altitude_km, inclination, sweep)


def _sweep_in_worker(job):
    """:func:`_sweep_at` in a pool worker. An error the pool cannot pickle
    back to this process (Basilisk's ``BasiliskError``: its module,
    ``_bskLogging``, does not import by that name) arrives as a
    ``BudgetError`` with its type, message and traceback, instead of a
    pickling error that loses them (SRelD K-14)."""
    try:
        return _sweep_at(job)
    except Exception as exc:
        try:
            pickle.dumps(exc)
        except Exception:
            raise BudgetError(f"{job[2]:g} km: {type(exc).__name__}: {exc}\n{traceback.format_exc()}") from None
        raise


def altitude_trade(scenario, spacecraft_name: str, altitudes_km=None, result=None, run_scenario=None,
                   delays_years=None, workers: int | None = None,
                   reentry_solver=uncontrolled_reentry_delta_v, makeup=_drag_makeup,
                   progress: Callable[[float, str], None] | None = None,
                   should_cancel: Callable[[], bool] | None = None) -> AltitudeTrade:
    """The launch-delay sweep (:func:`launch_delay_sweep`) at each of
    ``altitudes_km`` [km] (default: :func:`default_altitudes_km` around
    the spacecraft's own): the worst launch date's propellant per
    altitude, against the tank (``propellant_budget.tank_capacity_kg``,
    else the station-keeping propellant).

    An entered or flown in-plane figure belongs to the scenario's own
    altitude and planned launch; every other case scales it by its drag
    make-up against that one. Without either, each case is its own drag
    estimate (95th percentile). The altitudes run in parallel processes
    (``workers``, default one per CPU; 1 runs them here, in order)."""
    spacecraft = next((sc for sc in scenario.spacecraft if sc.name == spacecraft_name), None)
    if spacecraft is None:
        raise BudgetError(f"no spacecraft named {spacecraft_name!r}")
    if spacecraft.orbit.type != "classical_elements":
        raise BudgetError(f"{spacecraft_name}: an altitude trade needs the orbit as classical elements")
    config = spacecraft.propellant_budget or PropellantBudgetConfig()
    own_km = spacecraft.orbit.semi_major_axis_km - REQ_EARTH_M / 1e3  # [km]
    altitudes = sorted(float(a) for a in (altitudes_km or default_altitudes_km(own_km, scenario)))
    flown = run_contributors(result, spacecraft_name, config.mission_years) if result is not None else None
    reference_drag = None  # [m/s] drag make-up of the scenario's own orbit and launch
    if config.in_plane_control_delta_v_m_s is not None or (flown is not None and flown.in_plane is not None):
        if _estimates_in_plane(spacecraft) and scenario.gravity.central_body == "earth":
            if progress is not None:
                progress(0.0, "drag at the scenario's own altitude")
            settings = run_scenario or scenario
            run_sc = next((sc for sc in settings.spacecraft if sc.name == spacecraft_name), spacecraft)
            reference_drag = makeup(scenario, spacecraft, _parse_epoch(scenario.epoch_utc), config.mission_years,
                                    settings.space_weather.forecast_percentile, lifetime_cd(run_sc),
                                    should_cancel).delta_v_m_s
    solvers = {} if (reentry_solver is uncontrolled_reentry_delta_v and makeup is _drag_makeup) else \
        {"reentry_solver": reentry_solver, "makeup": makeup}
    jobs = [(scenario, spacecraft_name, a, run_scenario, delays_years, flown, reference_drag, solvers)
            for a in altitudes]
    cases: list[AltitudeCase] = []

    def report(case):
        cases.append(case)
        if progress is not None:
            progress(len(cases) / len(jobs), f"{case.altitude_km:g} km done")

    if workers == 1 or solvers or len(jobs) == 1:
        for job in jobs:
            if should_cancel is not None and should_cancel():
                raise BudgetError("cancelled")
            report(_sweep_at(job))
    else:
        import multiprocessing
        import os

        count = min(len(jobs), workers or os.cpu_count() or 1)
        # spawn: a clean interpreter per worker (forking a process running Qt
        # or Basilisk threads is unsafe). A Pool, unlike ProcessPoolExecutor,
        # can be terminated: Cancel stops the running sweeps at once instead
        # of waiting for them (audit L5); cancellation is polled every 0.2 s.
        pool = multiprocessing.get_context("spawn").Pool(count)
        try:
            pending = [pool.apply_async(_sweep_in_worker, (job,)) for job in jobs]
            while pending:
                if should_cancel is not None and should_cancel():
                    raise BudgetError("cancelled")
                pending[0].wait(0.2)  # [s]
                for done in [job for job in pending if job.ready()]:
                    pending.remove(done)
                    report(done.get())
            pool.close()
        except BaseException:
            pool.terminate()
            raise
        finally:
            pool.join()
    cases.sort(key=lambda case: case.altitude_km)
    tank = config.tank_capacity_kg or (spacecraft.station_keeping.propellant_kg
                                       if spacecraft.station_keeping is not None else None)
    trade = AltitudeTrade(spacecraft_name, tank, cases)
    for case in cases:
        trade.notes.extend(n for n in case.sweep.notes if not n.startswith("worst case") and n not in trade.notes)
    if reference_drag is not None:
        trade.notes.append(f"in-plane control: the scenario's own figure scaled by each case's drag against its "
                           f"own {own_km:.0f} km and planned launch")
    if tank:
        best = trade.lowest_fitting
        trade.notes.append(f"lowest altitude whose worst launch fits the {tank:g} kg tank: "
                           f"{best.altitude_km:g} km" if best is not None
                           else f"no altitude here fits the {tank:g} kg tank")
    return trade


def _parse_epoch(epoch_utc: str):

    when = parse_epoch_utc(epoch_utc)
    return when.astimezone(UTC).replace(tzinfo=None) if when.tzinfo is not None else when
