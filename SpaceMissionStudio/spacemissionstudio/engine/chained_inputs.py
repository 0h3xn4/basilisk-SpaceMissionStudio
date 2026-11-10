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
"""What an analysis takes from the last run, shown before it computes
(the transparency plan, Phase 8b: chained inputs).

The orbital lifetime from the end of a run starts from the run's last
state and the propellant left (:func:`lifetime_inputs`, from the same
:func:`.lifetime.start_state` the estimate uses); the propellant budget
takes the orbit control and formation keeping the run flew, scaled to the
mission (:func:`budget_inputs`, from :func:`.propellant_budget.run_contributors`).
Each value has its unit and where it came from (:class:`.trace.Quantity`).
:func:`changed_since` lists what differs between the scenario the run
flew and the one being edited, so a stale run is seen before it is used.
"""

from __future__ import annotations

import math
from datetime import timedelta

from .trace import Quantity


def lifetime_inputs(run_scenario, result, spacecraft_name: str) -> list[Quantity]:
    """The start of the decay after the run in ``result``: the state's time,
    the mean perigee and apogee heights and inclination, the propellant
    left. Raises ``lifetime.LifetimeError`` as the estimate would."""
    from ..schema.epochs import parse_epoch_utc
    from . import lifetime

    state = lifetime.start_state(run_scenario, spacecraft_name, result)
    orbit = lifetime.mean_orbit_from_state(state.r_m, state.v_m_s)
    when = parse_epoch_utc(run_scenario.epoch_utc) + timedelta(seconds=state.elapsed_s)
    mean = f"computed: the mean elements (first-order J2) of {state.state_source.removeprefix('last run: ')}"
    found = [Quantity("time of the state", "t", f"{when:%Y-%m-%d %H:%M:%S} UTC", "[UTC]",
                      f"last run: its last sample, {state.elapsed_s / 86400.0:.3f} days after the epoch"),
             Quantity("mean perigee height", "h_p", orbit.perigee_altitude_km, "[km]", mean),
             Quantity("mean apogee height", "h_a", orbit.apogee_altitude_km, "[km]", mean),
             Quantity("mean inclination", "i", math.degrees(orbit.inclination_rad), "[deg]", mean),
             Quantity("orbit thruster's propellant", "m_p", state.propellant_kg, "[kg]", state.propellant_source)]
    if state.tank_kg is not None:
        found.append(Quantity("fuel tank's propellant", "m_tank", state.tank_kg, "[kg]", state.tank_source))
    return found


def budget_inputs(result, spacecraft_name: str, mission_years: float) -> list[Quantity]:
    """What the propellant budget takes from the run in ``result``: the run's
    length, its scale to ``mission_years``, and each contributor it flew
    (delta-V and propellant over the mission). Empty when the run flew
    none of them."""
    from .propellant_budget import run_contributors

    flown = run_contributors(result, spacecraft_name, mission_years)
    if flown is None:
        return []
    found = [Quantity("run length", "T_run", flown.run_days, "[day]", f"last run: {spacecraft_name}.position_N's "
                                                                       "first and last samples"),
             Quantity("scale to the mission", "k", flown.scale, "[-]",
                      f"computed: {mission_years:g} years / the run's length")]
    for key, label in (("in_plane", "in-plane orbit control"), ("out_of_plane", "out-of-plane orbit control"),
                       ("formation", "formation keeping")):
        pair = getattr(flown, key)
        if pair is None:
            continue
        series, _final, _tank, _used, _share = flown.flown_from[key]
        found.append(Quantity(f"{label}, delta-V", f"dV_{key}", pair[0], "[m/s]",
                              f"last run: {series}, last value, x k"))
        found.append(Quantity(f"{label}, propellant", f"m_{key}", pair[1], "[kg]",
                              "last run: the tank's propellant used, its share by delta-V, x k"))
    return found


def changed_since(run_scenario, scenario) -> list[tuple[str, object, object]]:
    """``(path, as run, now)`` for each value of the scenario that differs
    from the one the run flew; empty when the run is of this scenario."""
    from .scenario_diff import diff

    if run_scenario is None or scenario is None:
        return []
    return diff(run_scenario.to_dict(), scenario.to_dict())
