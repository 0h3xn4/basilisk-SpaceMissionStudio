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
"""Structured warnings (the transparency plan, Phase 5a): each warning
names the rule it comes from.

A :class:`Finding` is the warning's text, as before, so every list of
warnings, file and message is unchanged. It also carries:

* ``rule_id``, the rule's name in :data:`RULES`;
* ``actual``, the value the rule found (with its unit), if it has one;
* ``limit``, the value it was compared with (with its unit), if it has one.

A :class:`Rule` says what the rule is, why it matters, how to fix what it
found and how to override it, and names the parameter that sets its
limit, if one does. :func:`explanation_lines` gives all of it as text, as
``spacemissionstudio validate --explain`` prints it.

Pre-run checks never block a run: a warning is advice. The run refuses
only what it cannot do, and says so in its own error. A run's own
warnings (re-entry, a drift, the space-weather sources read) are
findings too: they say how to read its results.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """One rule a check applies."""

    rule_id: str
    rule: str  # what the rule is
    why: str  # why it matters
    fix: str  # how to fix what it found
    override: str = "A warning does not stop the run: run it as it is if the setup is intended."
    parameter: str | None = None  # the parameter that sets the limit, if one does


class Finding(str):
    """A warning's text, with the rule it comes from (module docstring)."""

    rule_id: str
    actual: str | None
    limit: str | None

    def __new__(cls, message: str, rule_id: str, actual: str | None = None, limit: str | None = None):
        if rule_id not in RULES:
            raise KeyError(f"no rule {rule_id!r}")
        finding = super().__new__(cls, message)
        finding.rule_id, finding.actual, finding.limit = rule_id, actual, limit
        return finding

    def __getnewargs__(self):  # pickling (Monte Carlo workers): rebuild with the rule
        return str(self), self.rule_id, self.actual, self.limit

    @property
    def rule(self) -> Rule:
        return RULES[self.rule_id]

    def to_dict(self) -> dict:
        """The warning and its rule as a record."""
        rule = self.rule
        record = {"message": str(self), "rule_id": self.rule_id, "rule": rule.rule, "why": rule.why,
                  "fix": rule.fix, "override": rule.override}
        if self.actual is not None:
            record["actual"] = self.actual
        if self.limit is not None:
            record["limit"] = self.limit
        if rule.parameter is not None:
            record["parameter"] = rule.parameter
        return record


def explanation_lines(warning: str) -> list[str]:
    """The rule behind ``warning``, one line per part; nothing for a plain
    string (a warning that has no rule yet)."""
    if not isinstance(warning, Finding):
        return []
    rule = warning.rule
    lines = [f"rule {rule.rule_id}: {rule.rule}"]
    if warning.actual is not None or warning.limit is not None:
        found = []
        if warning.actual is not None:
            found.append(f"found {warning.actual}")
        if warning.limit is not None:
            found.append(f"limit {warning.limit}")
        lines.append("; ".join(found))
    lines.append(f"why: {rule.why}")
    lines.append(f"fix: {rule.fix}")
    override = rule.override
    if rule.parameter is not None:
        override += f" The limit is the parameter {rule.parameter} (spacemissionstudio assumptions)."
    lines.append(f"override: {override}")
    return lines


# The override of a finished run's warnings.
_RESULT = "It is about the run as made: read its results with it in mind."

RULES: dict[str, Rule] = {rule.rule_id: rule for rule in (
    Rule("check.not_run", "A check that fails to run says so, with the reason.",
         "Otherwise it would look passed.",
         "Correct the field the reason points to; the log has the full traceback.",
         override="It cannot be silenced: the check runs again on the next edit."),
    Rule("small_body.ephemeris_missing", "A run about a small body needs its ephemeris installed.",
         "Without it the run stops at once.",
         "Download it in Reference data (Small bodies), or run 'spacemissionstudio small-bodies --fetch'.",
         override="The run cannot start without it."),
    Rule("small_body.shape_missing", "Polyhedral gravity needs the body's shape model installed.",
         "Without it the run stops at once.",
         "Download it in Reference data (Small bodies), or turn polyhedral gravity off.",
         override="The run cannot start without it."),
    Rule("orbit.inside_body", "An initial position must be outside the Earth.",
         "The spacecraft would start underground.", "Correct the position (in km from the Earth's centre)."),
    Rule("orbit.escape", "An initial state must give a closed orbit (negative orbital energy).",
         "An escape trajectory is rarely meant; a units mistake (m for km) gives one.",
         "Check the position and velocity and their units (km and km/s)."),
    Rule("orbit.perigee_below_surface", "An initial perigee must be above the Earth's surface.",
         "The orbit passes through the Earth.", "Raise the perigee (the semi-major axis or the eccentricity)."),
    Rule("orbit.perigee_reentry", "An initial perigee below the re-entry altitude re-enters within about an orbit.",
         "The run ends almost at once.", "Raise the perigee.", parameter="lifetime.reentry_altitude_km"),
    Rule("space_weather.unreadable", "Drag with NRLMSISE-00 needs readable space-weather data.",
         "The run is refused without it.", "Download the data in Reference data, or choose another source.",
         override="The run cannot start without it."),
    Rule("space_weather.starts_late", "The space-weather data must start by the epoch.",
         "The run is refused.", "Move the epoch, or install data that covers it.",
         override="The run cannot start without it."),
    Rule("space_weather.ends_early", "The space-weather data must last to the run's end.",
         "The run is refused.", "Shorten the run, or install data that covers it.",
         override="The run cannot start without it."),
    Rule("earth_orientation.none", "An Earth-fixed frame (J2 and above, or ground stations) uses the IERS files.",
         "Without them it is IAU_EARTH, about 160 m/day off at 400 km.",
         "Download them in Settings > Reference data."),
    Rule("earth_orientation.not_covered", "The installed IERS files must cover the run.",
         "Outside them the Earth-fixed frame is IAU_EARTH, about 160 m/day off at 400 km.",
         "Download newer files in Settings > Reference data, or move the run into their span."),
    Rule("earth_orientation.predicted", "High-accuracy Earth orientation ends where the IERS files' data do.",
         "After that the run uses predicted values, of lower accuracy.",
         "Download newer files, or end the run before the date."),
    Rule("model.problem", "A spacecraft's 3D model must build.", "Its mass properties and facets come from it.",
         "Open the model (3D Model... in the app) and correct what the message names."),
    Rule("model.stale", "A spacecraft's applied 3D-model values must match its model.",
         "The run uses the stored values, not the model's.",
         "Open the model (3D Model... in the app) and press OK to apply it again, run "
         "'spacemissionstudio model --apply', or turn off applying it."),
    Rule("tle.unreadable", "A TLE orbit must propagate with SGP4.", "The spacecraft has no initial state.",
         "Correct the two TLE lines."),
    Rule("tle.age", "A TLE far from the scenario epoch is flagged.",
         "SGP4 propagates the TLE to the epoch (ECSS-E-ST-10-09C 5.3.1b), and its accuracy drops with the span.",
         "Use a TLE closer to the epoch.", parameter="tle.age_warning_days"),
    Rule("gravity.drag_point_mass", "Drag with point-mass gravity is flagged.",
         "J2 is far larger than drag, so the drag result is dominated by the missing term.",
         "Set the gravity degree to 2 or more."),
    Rule("recording.every_step", "Recording every step of a long run is flagged.",
         "It fills memory and the result files.", "Set 'Record every' (e.g. 600 s).", parameter="checks.many_samples"),
    Rule("recording.coarse", "Recording much coarser than the passes is flagged.",
         "A pass shorter than a few recording intervals shows coarsely or not at all.",
         "Record more often.", parameter="checks.coarse_recording_factor"),
    Rule("step.long", "A dynamics step above the limit is flagged.",
         "The orbit loses accuracy whatever the integrator tolerance (audit E3).",
         "Use a shorter step, and 'Record every' to keep fewer samples.", parameter="checks.long_step_s"),
    Rule("monte_carlo.processes", "Monte Carlo runs at most one process per CPU.",
         "Asking for more does not run more at once.", "Ask for no more processes than CPUs."),
    Rule("passes.late_first", "A station whose first pass comes late in the run is flagged.",
         "Until then the run has no contact with it.", "Move the epoch or lengthen the run.",
         parameter="checks.late_first_pass_fraction"),
    Rule("passes.none_in_run", "A station with no pass in the run is flagged, with when the first comes.",
         "The run has no contact with it.", "Move the epoch or lengthen the run.",
         parameter="checks.pass_horizon_days"),
    Rule("passes.none_in_lookahead", "A station with no pass in the run or the look-ahead after it is flagged.",
         "The orbit may never be in view of it.", "Check the orbit and the station's minimum elevation.",
         parameter="checks.pass_lookahead_days"),
    Rule("formation.hill_pd_hold", "A hill_pd follower's thruster must hold its separation.",
         "A saturated PD law in orbit diverges.", "Use the mean_oe or drift_orbit law, or a stronger thruster."),
    Rule("formation.hill_pd_start", "A hill_pd follower's thruster must meet its law's command at the start.",
         "A saturated PD law can diverge.", "Start closer to the reference, lower the gain, or use another law."),
    Rule("navigation.restart", "A long run in segments restarts each segment's navigation errors at zero.",
         "Basilisk keeps simpleNav's error state private and clears it at each reset.",
         "Accept it, or shorten the run so it needs no segments."),
    Rule("sensors.sun_sensor_facing", "A Sun-pointing spacecraft needs a sun sensor facing the Sun-pointing axis.",
         "Otherwise none sees the Sun once pointed.", "Turn a sun sensor's normal toward the axis.",
         parameter="checks.css_facing_min_cosine"),
    Rule("facets.unused", "Facets are used only by drag and SRP.", "With both off they change nothing.",
         "Turn on drag or SRP, or remove the facets."),
    Rule("station_keeping.no_drag", "Altitude station keeping needs drag to trip its deadband.",
         "With drag off the average altitude barely drifts.", "Turn on drag, or remove station keeping."),
    # A run's own warnings (engine.service, engine.long_run, engine.results).
    Rule("run.small_body_impact", "A spacecraft inside the small body's shape has hit it.",
         "The run integrates on through the body, so its results after the impact are not physical.",
         "Check the initial orbit and the maneuvers, or end the run before the impact.", override=_RESULT),
    Rule("run.propellant_depleted", "Station keeping whose propellant runs out makes no more burns.",
         "From then on the orbit is not controlled.", "Carry more propellant, or shorten the run.",
         override=_RESULT),
    Rule("run.reentry_stopped", "A run stops when a spacecraft is below the run's re-entry altitude.",
         "Integrating on through the atmosphere would give non-physical results and could lose the whole run.",
         "Raise the orbit, or accept the re-entry: its time is known to within one check.", override=_RESULT,
         parameter="dynamics.reentry_altitude_km"),
    Rule("run.reentry_after", "A spacecraft below the run's re-entry altitude has re-entered.",
         "Its results after that are not physical.", "Raise the orbit, or end the run before the re-entry.",
         override=_RESULT, parameter="dynamics.reentry_altitude_km"),
    Rule("run.energy_drift", "A two-body-only run's orbital energy must keep its first value to within the "
         "tolerance.", "Two-body gravity conserves it exactly: a drift this large flags a numerical blow-up, "
         "such as too long a step, not physics.", "Use a smaller dynamics step or a higher-order integrator.",
         override=_RESULT, parameter="dynamics.conservation_tolerance"),
    Rule("run.momentum_drift", "A two-body-only run's angular momentum must keep its first value to within the "
         "tolerance.", "Two-body gravity conserves it exactly: a drift this large flags a numerical blow-up, "
         "such as too long a step, not physics.", "Use a smaller dynamics step or a higher-order integrator.",
         override=_RESULT, parameter="dynamics.conservation_tolerance"),
    Rule("space_weather.daily_forecast", "A run that reads CelesTrak's 45-day forecast says so.",
         "Those days are a forecast, not observations.", "Accept it, or move the run into the observed days.",
         override=_RESULT),
    Rule("space_weather.monthly_forecast", "A run that reads NOAA's monthly F10.7 forecast says so.",
         "It fills months MSFC's prediction does not reach, with Ap held at the observed mean.",
         "Install MSFC's prediction in Reference data, or move the run into the months it covers.",
         override=_RESULT),
    Rule("space_weather.msfc_prediction", "A run that reads MSFC's prediction says so, with its percentile.",
         "Those days are a prediction at the percentile the scenario chooses, not observations.",
         "Choose the percentile the analysis needs (95, 50 or 5).", override=_RESULT),
    Rule("space_weather.msfc_repeated", "Past the end of MSFC's prediction its last months repeat.",
         "Those days repeat a past solar cycle (ESA AD10 Sec. 5.9), not a prediction.",
         "Install a newer MSFC prediction, or shorten the run.", override=_RESULT,
         parameter="space_weather.msfc_repeat_months"),
    Rule("magnetic_field.wmm_validity", "The magnetic field model (WMM) is valid for 5 years from its epoch.",
         "Outside those years magnetometer readings and torque-rod control use an extrapolated field.",
         "Use a WMM coefficient file whose years cover the run, or move the run.", override=_RESULT),
    Rule("data.changed_since_install", "A data file a run reads must be the one installed.",
         "Its SHA-256 differs from the one recorded when it was installed, so the run may not be reproduced.",
         "Reinstall it in Reference data.", override=_RESULT),
    Rule("lifetime.space_weather_ends", "A lifetime estimate looks ahead only as far as the real space-weather "
         "data goes.", "Past it there is no density to decay the orbit with: nothing is made up.",
         "Install space-weather data that reaches further, or read the estimate as covering the shorter span.",
         override=_RESULT),
    Rule("lifetime.ground_in_step", "An orbit that reaches the ground within one decay step re-enters within it.",
         "The re-entry time is known to within that step.", "Accept it: the step is the estimate's own.",
         override=_RESULT),
)}
