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
"""What a value that replaces a computed one changes (the transparency
plan, Phase 5b: "the tool re-validates, explains the consequence").

:func:`consequences` gives, for a mark whose field no longer holds the
value computed, short sentences on what that changes. Earth orbits'
classical elements get their physics:

* an inclination: the J2 drift of the node at the value used against the
  value computed; when that was Sun-synchronous, how far the node now
  drifts from the Sun;
* a RAAN computed for a local time of the ascending node: how far the
  node's local time moves;
* a semi-major axis: how the period changes.

Any other value gets its difference from the one computed. Nothing here
runs a simulation; the formulas are first-order J2 and two-body
(:mod:`engine.orbit_design`).
"""

from __future__ import annotations

from ..config import registry
from ..schema.scenario import resolve_value_path
from . import orbit_design


#: A field name's unit suffix, as the schema names its fields.
_UNITS = (("_deg", "deg"), ("_km", "km"), ("_kg", "kg"), ("_m2", "m^2"), ("_m", "m"), ("_s", "s"),
          ("_days", "day"), ("_w", "W"), ("_n", "N"), ("_db", "dB"), ("_bps", "bit/s"))


def _unit(name: str) -> str:
    return next((unit for suffix, unit in _UNITS if name.endswith(suffix)), "")


def _orbit(scenario, path: str):
    """The orbit a ``spacecraft[...].orbit.<field>`` mark is on, when it is
    an Earth orbit given as classical elements; else None."""
    if ".orbit." not in path or scenario.gravity.central_body != "earth":
        return None
    record, _name = resolve_value_path(scenario, path)
    if getattr(record, "type", None) != "classical_elements" or not record.semi_major_axis_km:
        return None
    return record


def consequences(scenario, mark) -> list[str]:
    """Sentences on what the scenario's value at ``mark.path`` changes
    against ``mark.value``; none while they are equal, or when the path no
    longer resolves."""
    try:
        record, name = resolve_value_path(scenario, mark.path)
    except ValueError:
        return []
    used = getattr(record, name)
    if not isinstance(used, (int, float)) or used == mark.value:
        return []
    difference = f"{used - mark.value:+g} {_unit(name)} from the value computed".replace("  ", " ")
    orbit = _orbit(scenario, mark.path)
    if orbit is None:
        return [difference.capitalize()]
    a, e = orbit.semi_major_axis_km, orbit.eccentricity or 0.0  # [km], [-]
    try:
        if name == "inclination_deg":
            used_rate = orbit_design.nodal_rate_deg_per_day(a, e, used)  # [deg/day]
            computed_rate = orbit_design.nodal_rate_deg_per_day(a, e, mark.value)  # [deg/day]
            lines = [f"The node drifts {used_rate:+.4f} deg/day under J2, {computed_rate:+.4f} at the value "
                     "computed"]
            if "Sun-synchronous" in mark.source:
                off = used_rate - orbit_design.SUN_MEAN_MOTION_DEG_PER_DAY  # [deg/day]
                drift = (f"the node moves {off:+.4f} deg/day against the Sun, so its local time moves "
                         f"{off * 4.0:+.2f} min/day ({off * 4.0 * 365.25 / 60.0:+.1f} h a year)")
                tolerance = registry.value("explain.sso_tolerance_deg", scenario)  # [deg] Explain's SSO label
                if abs(used - orbit_design.sun_synchronous_inclination_deg(a, e)) > tolerance:
                    lines.append(f"Not Sun-synchronous: {drift}")
                else:
                    lines.append(f"Still Sun-synchronous to Explain's {tolerance:g} deg (explain.sso_tolerance_deg); "
                                 f"{drift}")
            return lines
        if name == "raan_deg" and "LTAN" in mark.source:
            shift = ((used - mark.value + 180.0) % 360.0) - 180.0  # [deg], the shorter way round
            return [f"The ascending node's local time moves {shift / 15.0 * 60.0:+.0f} min from the one chosen "
                    "(15 deg of RAAN per hour)"]
        if name == "semi_major_axis_km":
            change = orbit_design.orbital_period_s(used) - orbit_design.orbital_period_s(mark.value)  # [s]
            return [f"The period changes by {change:+.1f} s ({difference})"]
    except (ValueError, ArithmeticError):
        return [difference.capitalize()]
    return [difference.capitalize()]
