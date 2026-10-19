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

"""Turns a :class:`schema.scenario.Scenario` into a short, STRUCTURED
"recipe" summary (:func:`explain` -> :class:`ScenarioExplanation`) the
GUI renders as stat tiles / colored badges / a per-spacecraft table /
a formation-geometry diagram (:class:`FormationDiagram`, drawn by
``gui.formation_diagram_widget.FormationDiagramWidget``) -- never as
prose. Basilisk-free, independently-testable (same precedent as
:mod:`engine.constellation`'s own docstring describes about itself).

This is the "what is this scenario actually doing, at a glance" layer a
real user asked for directly: the app's bundled templates demonstrate
real fidelity, but a hand-built scenario had no equivalent "here's what
you've configured" summary anywhere in the GUI -- only the hand-written,
narrative ``description`` text the bundled templates carry (which a
from-scratch scenario never has). This module is the ALWAYS-CURRENT,
terse counterpart: it reads the scenario's actual current fields on
every call, never narrative/pedagogical prose.

**Design discipline (do not regress this into prose or a bullet-point
wall -- both were tried and explicitly rejected by a real user before
this structured shape was settled on):** every ``StatTile.value``/
``Badge.label``/``note`` string is ONE short, scannable fragment ("Sun
-synchronous, 97.4 deg" -- not a sentence explaining WHY). Where a term
genuinely needs a definition (Sun-synchronous orbit, spherical-harmonics
gravity, third-body perturbation, phasing), this module does not inline
an explanation -- it points at ``USER_MANUAL.md``'s own glossary
(Section 12) by name, exactly as a bundled template's own hand-written
``description`` text already does elsewhere in this project.

:func:`explain` must NEVER raise -- it is called on every keystroke in
the GUI, often against a mid-edit/genuinely invalid scenario -- and it
builds each section/row CONDITIONALLY, so a trivial from-scratch scenario
renders a short tile row and maybe one badge, not a wall of empty
sections.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from typing import Dict, List, Tuple

from ..schema.epochs import parse_epoch_utc
from . import earth_orientation
from .orbit_design import sun_synchronous_inclination_deg
from .roe import min_radial_normal_separation
from .scenario_checks import gravity_fidelity_notes, pass_summary, scenario_warnings

_logger = logging.getLogger(__name__)

_EARTH_REQUATOR_KM = 6378.1366  # [km] -- same reference value as engine.orbit_design's own
# [km] equatorial radius of each central body, Basilisk 2.12's astroConstants REQ_* values
_BODY_RADIUS_KM = {"sun": 695000.0, "mercury": 2439.7, "venus": 6051.8, "earth": 6378.1366, "moon": 1737.4,
                   "mars": 3396.19, "mars barycenter": 3396.19, "jupiter": 71492.0}

# How close a classical-elements orbit's own inclination must be to the
# computed Sun-synchronous value (at its own semi-major axis/eccentricity)
# to call it "Sun-synchronous" -- wide enough to tolerate the 2-decimal
# rounding every bundled template's own inclination_deg already carries
# (see engine.orbit_design.sun_synchronous_inclination_deg's own comment),
# narrow enough that an unrelated inclination (e.g. 51.6 deg) never matches.
_SSO_TOLERANCE_DEG = 0.1


@dataclass
class StatTile:
    label: str
    value: str


@dataclass
class Badge:
    label: str
    kind: str = "neutral"  # "neutral" | "accent" | "success" | "warning"
    spacecraft: str = ""  # set on a 3D model's badge: the GUI opens that spacecraft's model on a click


@dataclass
class SpacecraftFactRow:
    name: str
    facts: Dict[str, str] = field(default_factory=dict)  # short column_label -> value


@dataclass
class ExplanationSection:
    title: str
    badges: List[Badge] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)  # short relational one-liners only, rare


@dataclass
class FormationDiagram:
    """Everything a along-track phasing-keeping diagram needs to depict
    the real control mechanism -- a target separation held within a
    hysteresis band, not just the two names involved. Deliberately holds
    only ``PhasingKeepingConfig`` fields that are already fixed at
    scenario-design time (no live telemetry -- that's
    ``mission_dashboard_widget``'s job, which needs an actual run):
    ``target_separation_km`` is the FIRST entry of a schedule (the
    initial/current target); ``tolerance_fraction`` is the outer "trigger
    a correction" band, ``restore_tolerance_fraction`` the inner,
    tighter "stop correcting, settled" band -- together they're the
    actual deadband/hysteresis control law, not just one number.
    """

    chief_name: str
    follower_name: str
    target_separation_km: float
    tolerance_fraction: float
    restore_tolerance_fraction: float


@dataclass
class RoeDiagram:
    """An ROE formation's targets, for the e/i-vector diagram
    (``gui.roe_diagram_widget``): each target's start day and its six
    relative orbital elements [m], in ``engine.roe.ROE_LABELS`` order."""

    chief_name: str
    follower_name: str
    targets: List[Tuple[float, List[float]]]  # (start day, a times the ROE [m])


@dataclass
class ScenarioExplanation:
    headline: str
    stat_tiles: List[StatTile] = field(default_factory=list)
    sections: List[ExplanationSection] = field(default_factory=list)
    spacecraft_table: List[SpacecraftFactRow] = field(default_factory=list)  # empty if < 2 spacecraft
    formation_diagrams: List[FormationDiagram] = field(default_factory=list)  # one per phasing_keeping spacecraft
    roe_diagrams: List[RoeDiagram] = field(default_factory=list)  # one per roe_formation spacecraft


def _models_oblateness(gravity) -> bool:
    """Sun-synchronous precession comes from Earth's J2, so it only exists
    when the gravity model includes it (degree 2 or more)."""
    return (gravity is not None and getattr(gravity, "central_body", "") == "earth"
            and (getattr(gravity, "central_body_degree", 0) or 0) >= 2)


def _is_sun_synchronous(orbit, gravity) -> bool:
    if not _models_oblateness(gravity):
        return False
    if getattr(orbit, "type", None) != "classical_elements":
        return False
    sma = orbit.semi_major_axis_km
    inc = orbit.inclination_deg
    if not sma or inc is None or sma <= 0:
        return False
    try:
        target = sun_synchronous_inclination_deg(sma, orbit.eccentricity or 0.0)
    except (ValueError, ArithmeticError, ZeroDivisionError):
        return False
    return abs(inc - target) <= _SSO_TOLERANCE_DEG


def _orbit_summary(orbit, gravity) -> str:
    orbit_type = getattr(orbit, "type", None)
    if orbit_type == "classical_elements":
        sma = orbit.semi_major_axis_km
        inc = orbit.inclination_deg
        if sma is None or inc is None:
            return "Classical elements"
        label = "SSO" if _is_sun_synchronous(orbit, gravity) else "Classical"
        # Above the central body, not always Earth (audit L21).
        altitude_km = sma - _BODY_RADIUS_KM.get(getattr(gravity, "central_body", "earth"), _EARTH_REQUATOR_KM)
        return f"{label} {inc:g} deg, {altitude_km:.0f} km alt"
    if orbit_type == "cartesian":
        return "Cartesian state"
    if orbit_type == "tle":
        return "TLE"
    return "Orbit"


# Plain names for the attitude modes (shown instead of their code names).
_FSW_MODE_NAMES = {
    "inertial3D": "Inertial hold",
    "hillPoint": "Orbit-frame (nadir) pointing",
    "velocityPoint": "Velocity pointing",
    "sunSafePoint": "Sun pointing",
    "locationPointing": "Target pointing",
}


def _mode_name(fsw_mode: str) -> str:
    return _FSW_MODE_NAMES.get(fsw_mode, fsw_mode)


def _gravity_summary(gravity) -> str:
    body = gravity.central_body.capitalize()
    if gravity.central_body_degree <= 0:
        body_part = f"Point-mass {body}"
    else:
        body_part = f"Degree-{gravity.central_body_degree} {body}"
    if gravity.third_body_perturbers:
        return f"{body_part} + {'/'.join(b.capitalize() for b in gravity.third_body_perturbers)}"
    return body_part


def _spacecraft_control_summary(sc) -> str:
    parts = []
    if sc.fsw_mode:
        parts.append(_mode_name(sc.fsw_mode))
    if sc.station_keeping is not None:
        parts.append("station-keeping")
    if sc.geo_station_keeping is not None:
        parts.append("GEO station-keeping")
    if sc.phasing_keeping is not None:
        parts.append("phasing-keeping")
    if sc.roe_formation is not None:
        parts.append(f"ROE formation ({sc.roe_formation.control_law})")
    if sc.constant_thrust is not None:
        parts.append("constant-thrust")
    if sc.momentum_dumping is not None:
        parts.append("RW desat (thrusters)")
    if sc.magnetic_momentum_management is not None:
        parts.append("RW desat (torque rods)")
    if not parts:
        return "none"
    return ", ".join(parts)


def _spacecraft_propellant_kg(sc) -> float:
    total = 0.0
    if sc.station_keeping is not None:
        total += sc.station_keeping.propellant_kg
    if sc.geo_station_keeping is not None:
        total += sc.geo_station_keeping.propellant_kg
    if sc.constant_thrust is not None:
        total += sc.constant_thrust.propellant_kg
    if sc.fuel_tank is not None:
        total += sc.fuel_tank.propellant_mass_kg
    return total


def _roe_notes(scenario) -> List[str]:
    """Each ROE target in words: where the follower sits and how close the
    two can come in the radial/cross-track plane (passive safety)."""
    notes = []
    for sc in scenario.spacecraft:
        if sc.roe_formation is None:
            continue
        for index, target in enumerate(sc.roe_formation.targets):
            da, dl, dex, dey, dix, diy = target.roe_m
            margin = min_radial_normal_separation(target.roe_m, 1.0)  # [m] the ROE are in metres
            safety = (f"closest radial/cross-track approach {margin:.0f} m" if margin > 1.0
                      else "the orbits cross in the radial/cross-track plane: not passively safe")
            notes.append(f"{sc.name} from day {target.start_day:g}: {abs(dl):.0f} m "
                         f"{'ahead of' if dl >= 0 else 'behind'} {sc.roe_formation.chief_spacecraft}, "
                         f"{math.hypot(dex, dey):.0f} m radial and {math.hypot(dix, diy):.0f} m cross-track "
                         f"motion; {safety}" + ("" if abs(da) < 1e-9 else f"; relative semi-major axis {da:g} m"))
        chief = next((c for c in scenario.spacecraft if c.name == sc.roe_formation.chief_spacecraft), None)
        note = _differential_drag_note(sc, chief) if chief is not None else None
        if note:
            notes.append(note)
    return notes


def _ballistic_coefficient(sc) -> float:
    """Drag coefficient x area / dry mass [m^2/kg] of flat-plate drag (0 without drag)."""
    return sc.drag_coeff * sc.drag_area_m2 / sc.dry_mass_kg if sc.enable_drag else 0.0


def _differential_drag_note(follower, chief) -> str | None:
    """Whether the follower's flat-plate drag differs from the chief's by
    more than 5 %, and what the ROE guidance does about it; ``None`` when
    it does not, or when either uses facets (attitude-dependent area)."""
    if follower.facets or chief.facets or not (follower.enable_drag or chief.enable_drag):
        return None
    mine, theirs = _ballistic_coefficient(follower), _ballistic_coefficient(chief)
    if abs(mine - theirs) <= 0.05 * max(mine, theirs):
        return None
    config = follower.roe_formation
    if config.control_law != "impulsive":
        handling = "the continuous law's feedback corrects it"
    elif config.differential_drag:
        handling = "the guidance measures the decay it causes and compensates it"
    else:
        handling = "corrected as an error ('Compensate differential drag' is off)"
    return (f"{follower.name}: drag coefficient x area / dry mass {mine:.4f} m^2/kg against "
            f"{chief.name}'s {theirs:.4f}: differential drag; {handling}")


def _formation_section(scenario) -> ExplanationSection | None:
    badges: List[Badge] = []
    if any(sc.station_keeping is not None for sc in scenario.spacecraft):
        badges.append(Badge("Station-keeping", "accent"))
    if any(sc.geo_station_keeping is not None for sc in scenario.spacecraft):
        badges.append(Badge("GEO station-keeping (E-W, N-S)", "accent"))
    if any(sc.phasing_keeping is not None for sc in scenario.spacecraft):
        badges.append(Badge("Phasing-keeping", "accent"))
    laws = {sc.phasing_keeping.control_law for sc in scenario.spacecraft if sc.phasing_keeping is not None}
    for law, label in (("mean_oe", "Basilisk mean-element feedback"), ("hill_pd", "Basilisk Hill-frame PD")):
        if law in laws:
            badges.append(Badge(label, "accent"))
    roe_laws = {sc.roe_formation.control_law for sc in scenario.spacecraft if sc.roe_formation is not None}
    for law, label in (("impulsive", "ROE formation (impulsive)"),
                       ("continuous", "ROE formation (Basilisk mean-element feedback)")):
        if law in roe_laws:
            badges.append(Badge(label, "accent"))
    if any(sc.constant_thrust is not None for sc in scenario.spacecraft):
        badges.append(Badge("Constant thrust", "accent"))
    if not badges:
        return None
    notes = _roe_notes(scenario)
    no_station_keeping = [sc.name for sc in scenario.spacecraft
                           if sc.phasing_keeping is not None and sc.station_keeping is None]
    if no_station_keeping:
        notes.append(f"{', '.join(no_station_keeping)}: phasing keeping needs station-keeping on the same "
                     "spacecraft (User Manual Sec. 12)")
    return ExplanationSection(title="Formation / orbit maintenance", badges=badges, notes=notes)


def _attitude_section(scenario) -> ExplanationSection | None:
    modes = sorted({sc.fsw_mode for sc in scenario.spacecraft if sc.fsw_mode})
    comms_pointing_count = sum(1 for sc in scenario.spacecraft if sc.comms_pointing is not None)
    if not modes and not comms_pointing_count:
        return None
    badges = [Badge(_mode_name(mode), "accent") for mode in modes]
    if comms_pointing_count:
        badges.append(Badge("Comms pointing", "accent"))
    if any(sc.navigation_error is not None and sc.navigation_error.any_error for sc in scenario.spacecraft):
        badges.append(Badge("Navigation error", "accent"))
    return ExplanationSection(title="Attitude control", badges=badges)


def _environment_section(scenario) -> ExplanationSection | None:
    badges: List[Badge] = []
    if any(_is_sun_synchronous(sc.orbit, scenario.gravity) for sc in scenario.spacecraft):
        badges.append(Badge("Sun-synchronous", "accent"))
    if any(sc.enable_drag for sc in scenario.spacecraft):
        badges.append(Badge("Drag", "accent"))
    if any(sc.enable_srp for sc in scenario.spacecraft):
        badges.append(Badge("Solar radiation pressure", "accent"))
    if any(sc.enable_gravity_gradient for sc in scenario.spacecraft):
        badges.append(Badge("Gravity gradient", "accent"))
    if any(sc.facets and (sc.enable_drag or sc.enable_srp) for sc in scenario.spacecraft):
        badges.append(Badge("Facet model (drag/SRP torques)", "accent"))
    for sc in scenario.spacecraft:
        if sc.model is not None:
            badges.append(Badge(f"{sc.name}: 3D model, {len(sc.model.parts)} parts", "neutral", spacecraft=sc.name))
    notes = gravity_fidelity_notes(scenario)
    for sc in scenario.spacecraft:
        offset = math.sqrt(sum(float(v) ** 2 for v in sc.center_of_mass_b_m))
        if offset > 0.0:
            notes.append(f"{sc.name}: center of mass {100.0 * offset:.1f} cm from B")
    if getattr(scenario.gravity, "central_body", "") == "earth":
        notes += _earth_frame_notes(scenario)
    if not badges:
        return None
    return ExplanationSection(title="Environment", badges=badges, notes=notes)


def _earth_frame_notes(scenario) -> List[str]:
    """The Earth-fixed frame a run will use and its accuracy
    (engine.earth_orientation, ECSS-E-ST-10-09C 5.4.9f)."""
    try:
        start = parse_epoch_utc(scenario.epoch_utc)
        if start.tzinfo is not None:
            start = start.astimezone(timezone.utc).replace(tzinfo=None)
        kernels = earth_orientation.installed()
        notes = earth_orientation.notes(start, start + timedelta(days=scenario.sim_settings.duration_days), kernels)
    except Exception:  # noqa: BLE001 -- a half-edited scenario must never break the Explain tab
        return []
    return notes or [f"Earth orientation: {earth_orientation.EARTH_FIXED_FRAME} from IERS data"]


def _power_comms_section(scenario) -> ExplanationSection | None:
    badges: List[Badge] = []
    if any(sc.power is not None for sc in scenario.spacecraft):
        badges.append(Badge("Power budget", "accent"))
    if any(sc.rf_link is not None for sc in scenario.spacecraft):
        badges.append(Badge("RF link budget", "accent"))
    if not badges:
        return None
    return ExplanationSection(title="Power & comms", badges=badges)


def _solar_array_section(scenario) -> ExplanationSection | None:
    """Flexible arrays (engine.solar_arrays): their mass and first mode, and
    a warning when the recorded samples are too sparse to show the flexing
    (it then aliases into a slower false oscillation)."""
    with_arrays = [sc for sc in scenario.spacecraft if sc.solar_arrays]
    if not with_arrays:
        return None
    badges = [Badge("Flexible solar arrays", "accent")]
    notes = []
    settings = scenario.sim_settings
    sample_s = settings.record_interval_s if settings.record_interval_s > 0 else settings.dynamics_task_rate_s  # [s]
    for sc in with_arrays:
        mass_kg = sum(a.mass_kg for a in sc.solar_arrays)  # [kg]
        lowest_hz = min(a.first_mode_hz for a in sc.solar_arrays)  # [Hz]
        count = len(sc.solar_arrays)
        notes.append(f"{sc.name}: {count} array{'s' if count > 1 else ''}, {mass_kg:g} kg, first mode from "
                     f"{lowest_hz:.3g} Hz")
        fastest_hz = max(a.first_mode_hz for a in sc.solar_arrays)  # [Hz] hub fixed; free, it is higher
        if fastest_hz > 0.5 / sample_s:
            badges.append(Badge(f"{sc.name}: samples every {sample_s:g} s alias the flexing", "warning"))
    return ExplanationSection(title="Flexible solar arrays", badges=badges, notes=notes)


_PASS_MINUTES = 10.0  # [min] a typical LEO pass, for the "per pass" figure only


def _data_handling_section(scenario) -> ExplanationSection | None:
    """What the instruments produce, how long the memory lasts and what a
    pass can carry (engine.data_handling) -- arithmetic on the settings,
    before any run."""
    with_data = [sc for sc in scenario.spacecraft if sc.data_handling is not None]
    if not with_data:
        return None
    badges = [Badge("Data handling", "accent")]
    patterns = {sc.rf_link.antenna_pattern for sc in with_data if sc.rf_link is not None}
    if "cosine" in patterns:
        badges.append(Badge("Patch antenna", "neutral"))
    if "table" in patterns:
        badges.append(Badge("Antenna gain table", "neutral"))
    notes = []
    for sc in with_data:
        dh = sc.data_handling
        rate_bps = sum(i.data_rate_bps for i in dh.instruments)  # [bit/s]
        per_day_gbit = rate_bps * 86400.0 / 1e9  # [Gbit/day]
        free_gbit = dh.storage_capacity_gbit - sum(i.initial_data_gbit for i in dh.instruments)  # [Gbit]
        hours = free_gbit * 1e9 / rate_bps / 3600.0 if rate_bps > 0 else float("inf")  # [h]
        notes.append(f"{sc.name}: {per_day_gbit:.3g} Gbit/day; memory full in {hours:.3g} h")
        if sc.rf_link is None:
            badges.append(Badge(f"{sc.name}: no downlink (no RF link)", "warning"))
        elif not scenario.ground_stations:
            badges.append(Badge(f"{sc.name}: no ground station to downlink to", "warning"))
        else:
            per_pass_gbit = sc.rf_link.data_rate_bps * _PASS_MINUTES * 60.0 / 1e9  # [Gbit]
            notes.append(f"{sc.name}: {sc.rf_link.data_rate_bps / 1e6:.3g} Mbit/s, "
                         f"{per_pass_gbit:.3g} Gbit per {_PASS_MINUTES:g}-min pass")
    return ExplanationSection(title="Data handling", badges=badges, notes=notes)


def _ground_stations_section(scenario) -> ExplanationSection | None:
    if not scenario.ground_stations:
        return None
    try:
        passes = pass_summary(scenario)  # predicted from the initial orbits -- see engine.scenario_checks
    except Exception:  # noqa: BLE001 -- explain() must never raise
        passes = []
    return ExplanationSection(
        title="Ground stations",
        badges=[Badge(gs.name, "neutral") for gs in scenario.ground_stations],
        notes=passes,
    )


def _checks_section(scenario) -> ExplanationSection | None:
    """Setups that can't do what they're configured for -- shown first, so
    they are seen before a long run (see engine.scenario_checks)."""
    warnings = scenario_warnings(scenario)
    if not warnings:
        return None
    return ExplanationSection(
        title="Check before running",
        badges=[Badge(f"{len(warnings)} to check", "warning")],
        notes=warnings,
    )


def _formation_diagrams(scenario) -> List[FormationDiagram]:
    diagrams = []
    for sc in scenario.spacecraft:
        pk = sc.phasing_keeping
        # The diagram shows the drift-orbit law's trigger/restore band; the
        # Basilisk laws (engine.formation_control) have no band.
        if pk is None or not pk.target_separation_km or pk.control_law != "drift_orbit":
            continue
        diagrams.append(FormationDiagram(
            chief_name=pk.chief_spacecraft,
            follower_name=sc.name,
            target_separation_km=pk.target_separation_km[0],
            tolerance_fraction=pk.tolerance_fraction,
            restore_tolerance_fraction=pk.restore_tolerance_fraction,
        ))
    return diagrams


def _roe_diagrams(scenario) -> List[RoeDiagram]:
    return [RoeDiagram(chief_name=sc.roe_formation.chief_spacecraft, follower_name=sc.name,
                       targets=[(t.start_day, list(t.roe_m)) for t in sc.roe_formation.targets])
            for sc in scenario.spacecraft if sc.roe_formation is not None and sc.roe_formation.targets]


def _monte_carlo_section(scenario) -> ExplanationSection | None:
    mc = scenario.monte_carlo
    if not mc.enabled:
        return None
    return ExplanationSection(
        title="Monte Carlo",
        badges=[Badge(f"{mc.num_runs} runs", "accent")],
    )


def _duration_label(days: float) -> str:
    """"2.25 h" rather than "0.09375 d" for short runs; minutes under an
    hour, days from 2 d up."""
    if days < 1.0 / 24.0:
        return f"{round(days * 1440.0, 1):g} min"
    if days < 2.0:
        return f"{round(days * 24.0, 2):g} h"
    return f"{round(days, 2):g} d"


def explain(scenario) -> ScenarioExplanation:
    """Never raises -- called on every keystroke in the GUI, often
    against a mid-edit/invalid scenario.
    """
    try:
        return _explain(scenario)
    except Exception:  # noqa: BLE001 -- see docstring: must never raise
        _logger.debug("Explain tab: the scenario could not be explained", exc_info=True)
        return ScenarioExplanation(headline=getattr(scenario, "name", "") or "(unnamed scenario)")


def _explain(scenario) -> ScenarioExplanation:
    spacecraft = scenario.spacecraft

    stat_tiles = [
        StatTile("Spacecraft", str(len(spacecraft))),
        StatTile("Duration", _duration_label(scenario.sim_settings.duration_days)),
        StatTile("Gravity", _gravity_summary(scenario.gravity)),
    ]
    if len(spacecraft) == 1:
        stat_tiles.append(StatTile("Orbit", _orbit_summary(spacecraft[0].orbit, scenario.gravity)))
    if scenario.simulation_mode != "full_attitude":
        stat_tiles.append(StatTile("Mode", "Orbit only"))

    # One section that fails (a half-edited scenario) is left out and
    # logged; it used to blank the whole tab, with nothing logged (L21).
    sections = []
    for build in (_checks_section, _formation_section, _attitude_section, _environment_section,
                  _power_comms_section, _data_handling_section, _solar_array_section, _ground_stations_section,
                  _monte_carlo_section):
        try:
            section = build(scenario)
        except Exception:  # noqa: BLE001 -- see explain(): the tab must never break
            _logger.debug("Explain tab: %s failed; the section is left out", build.__name__, exc_info=True)
            continue
        if section is not None:
            sections.append(section)

    spacecraft_table: List[SpacecraftFactRow] = []
    if len(spacecraft) >= 2:
        # Spacecraft with identical facts share one row (a 6-satellite
        # constellation used to repeat the same row six times).
        groups: dict = {}
        for sc in spacecraft:
            propellant_kg = _spacecraft_propellant_kg(sc)
            facts = {
                "Orbit": _orbit_summary(sc.orbit, scenario.gravity),
                "Control": _spacecraft_control_summary(sc),
                "Propellant": f"{propellant_kg:g} kg" if propellant_kg > 0 else "-",
            }
            groups.setdefault(tuple(facts.items()), (facts, []))[1].append(sc.name)
        for facts, names in groups.values():
            if len(names) > 2:
                label = f"{names[0]} ... {names[-1]} ({len(names)})"
            else:
                label = ", ".join(names)
            spacecraft_table.append(SpacecraftFactRow(name=label, facts=facts))

    return ScenarioExplanation(
        headline=scenario.name or "(unnamed scenario)",
        stat_tiles=stat_tiles,
        sections=sections,
        spacecraft_table=spacecraft_table,
        formation_diagrams=_formation_diagrams(scenario),
        roe_diagrams=_roe_diagrams(scenario),
    )
