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
"""The declared parameters, one section per area (transparency audit,
Phase 3a). The areas move in one at a time, each proven by the
regression baseline to change no number: the propellant budget, the
orbital lifetime, the RF link and data handling, how a run's results are
read, the dynamics' run control, the environment's data rules, then the
orbit controllers.

"AD10" is ESA's "Guidelines for the computation of the Delta-V and
Propellant Mass budgets", EOP-FM/2024-07-177, issue 3.0.
"""

from .registry import Parameter, register

# The percentiles of MSFC's solar-activity prediction (engine.spaceweather.MSFC_PERCENTILES), the only ones
# a forecast can be resolved at.
_MSFC_PERCENTILES = (95.0, 50.0, 5.0)

# -- propellant budget (engine.propellant_budget) ---------------------------------------------

register(
    Parameter("propellant_budget.cam_count_factor", 4.0, "[-]",
              "The number of collision avoidances entered is multiplied by this.",
              "AD10 Sec. 5.6", "AD10's margin on the collision-avoidance count, which DRAMA estimates.",
              minimum=1.0, maximum=100.0),
    Parameter("propellant_budget.cam_sma_change_m", 100.0, "[m]",
              "The semi-major axis change of one collision avoidance: up by this, then back.",
              "AD10 Sec. 6.2.4", minimum=0.0, maximum=100000.0),
    Parameter("propellant_budget.attitude_propellant_factor", 2.0, "[-]",
              "The attitude-control propellant entered is multiplied by this (2: +100 %).",
              "AD10 Sec. 5.6", minimum=1.0, maximum=10.0),
    Parameter("propellant_budget.controlled_last_burn_margin", 0.15, "[-]",
              "A controlled re-entry's last burn is increased by this fraction (0.15: +15 %).",
              "AD10 Sec. 5.6", minimum=0.0, maximum=1.0),
    Parameter("propellant_budget.residual_fraction", 0.01, "[-]",
              "The propellant left unusable in the tank, as a fraction of the tank's load.",
              "AD10 Sec. 5.8", "AD10's summary table prints 10 %; its equations give 1 %, which is used.",
              minimum=0.0, maximum=0.5),
    Parameter("propellant_budget.uncertainty_fraction", 0.02, "[-]",
              "The loading and gauging uncertainty, as a fraction of the tank's load.",
              "AD10 Secs. 5.8, 6.4", "AD10's summary table prints 20 %; its equations give 2 %, which is used.",
              minimum=0.0, maximum=0.5),
    Parameter("propellant_budget.eol_drag_coeff", 2.2, "[-]",
              "The drag coefficient of the end-of-life disposal estimate.",
              "AD10 Sec. 5.2", minimum=0.1, maximum=10.0),
    Parameter("propellant_budget.operations_drag_coeff", 3.0, "[-]",
              "The drag coefficient AD10 asks for in operations; a run or estimate with another is noted.",
              "AD10 Sec. 5.2", "3.0 for spacecraft, 2.2 for CubeSats; the note names both.",
              minimum=0.1, maximum=10.0),
    Parameter("propellant_budget.operations_percentile", 95.0, "[%]",
              "The MSFC solar-activity percentile of the in-plane drag estimate and the launch-delay sweep; a run "
              "with another is noted.", "AD10 Sec. 5.9", "MSFC publishes the 95th, 50th and 5th percentiles only.",
              choices=_MSFC_PERCENTILES),
    Parameter("propellant_budget.eol_percentile", 50.0, "[%]",
              "The MSFC solar-activity percentile of the end-of-life disposal estimate.",
              "AD10 Sec. 5.9", "MSFC publishes the 95th, 50th and 5th percentiles only.", choices=_MSFC_PERCENTILES),
    Parameter("propellant_budget.geo_graveyard_base_m", 235e3, "[m]",
              "A GEO graveyard orbit is raised by this plus geo_graveyard_per_cr_a_m * Cr * A / m.",
              "AD10 Sec. 6.3.1.3 (IADC)", minimum=0.0),
    Parameter("propellant_budget.geo_graveyard_per_cr_a_m", 1000e3, "[m per (m^2/kg)]",
              "The GEO graveyard raise per unit of Cr * A / m.", "AD10 Sec. 6.3.1.3 (IADC)", minimum=0.0),
    Parameter("propellant_budget.convergence_kg", 0.1, "[kg]",
              "The budget iterates until the propellant total changes by less than this.",
              "AD10 Sec. 6.5", minimum=1e-6, maximum=100.0),
    Parameter("propellant_budget.max_iterations", 50, "[-]",
              "The most iterations before the budget is reported as not settled.",
              "SpaceMissionStudio's own choice", "Far more than the 3 to 6 a budget takes to settle.", kind="integer",
              minimum=1, maximum=10000),
    Parameter("propellant_budget.launch_delays_years", (0.0, 1.0, 2.0, 3.0, 4.0, 5.0), "[year]",
              "The launch delays the launch-delay sweep and the altitude trade repeat the budget for.",
              "AD10 Sec. 5.5", "AD10 asks for launches up to 5 years late.", kind="number list",
              minimum=0.0, maximum=30.0),
    Parameter("propellant_budget.scaled_run_ratio", 1.05, "[-]",
              "A last run shorter than the mission by more than this ratio has its orbit control scaled up to "
              "the mission, and is noted as scaled.", "SpaceMissionStudio's own choice",
              "5 %: a run of the whole mission ends a few steps short of it.", minimum=1.0, maximum=2.0),
    Parameter("propellant_budget.altitude_step_km", 50.0, "[km]",
              "The spacing of the five altitudes an altitude trade takes when none are given.",
              "SpaceMissionStudio's own choice", minimum=1.0, maximum=1000.0),
    Parameter("propellant_budget.altitude_floor_km", 250.0, "[km]",
              "The lowest altitude an altitude trade takes when none are given.", "SpaceMissionStudio's own choice",
              "Below about 250 km an orbit decays within weeks.", minimum=100.0, maximum=2000.0),
)

# -- orbital lifetime (engine.lifetime) ---------------------------------------------------------

register(
    Parameter("lifetime.reentry_altitude_km", 120.0, "[km]",
              "A perigee at or below this counts as re-entry: the lifetime ends there.",
              "Common practice for orbit-averaged decay estimates",
              "Below about 120 km an orbit lasts days at most. A full simulation run has its own criterion, "
              "on the simulated altitude: dynamics.reentry_altitude_km (100 km).",
              minimum=60.0, maximum=300.0),
    Parameter("lifetime.ring_points", 16, "[-]",
              "The points spread evenly around the orbit (in mean anomaly) the drag is averaged over at each step.",
              "SpaceMissionStudio's own choice",
              "With 16, the estimate is within 3 % of full Basilisk decay runs (tests/test_lifetime.py).",
              kind="integer", minimum=4, maximum=360),
    Parameter("lifetime.max_step_s", 86400.0, "[s]",
              "The longest decay step; it shortens as the orbit nears re-entry.",
              "SpaceMissionStudio's own choice", "A day: the density follows the space weather's daily values.",
              minimum=600.0, maximum=864000.0),
    Parameter("lifetime.max_perigee_drop_fraction", 0.01, "[-]",
              "The largest fraction of the perigee height left above re-entry that one step may lose.",
              "SpaceMissionStudio's own choice", minimum=1e-4, maximum=0.5),
    Parameter("lifetime.zero_debris_years", 5.0, "[year]",
              "The first disposal rule a lifetime is checked against: re-entry within this many years.",
              "ESA Zero Debris approach; the FCC's 5-year rule", minimum=0.1, maximum=100.0),
    Parameter("lifetime.iadc_years", 25.0, "[year]",
              "The second disposal rule a lifetime is checked against: re-entry within this many years.",
              "IADC Space Debris Mitigation Guidelines; ISO 24113", minimum=0.1, maximum=100.0),
    Parameter("lifetime.makeup_step_s", 21600.0, "[s]",
              "The sampling step of the drag make-up estimate (the in-plane control a station keeper spends).",
              "SpaceMissionStudio's own choice", "Six hours: four samples a day of the daily space weather.",
              minimum=600.0, maximum=864000.0),
    Parameter("lifetime.default_drag_coeff", 2.2, "[-]",
              "The drag coefficient a lifetime estimate starts with, before 'the spacecraft's own' is chosen.",
              "ESA AD10 Sec. 5.2 (end of life)", minimum=0.1, maximum=10.0),
    Parameter("lifetime.default_forecast_percentile", 50.0, "[%]",
              "The MSFC solar-activity percentile a lifetime estimate starts with.",
              "ESA AD10 Sec. 5.9 (end of life)", "MSFC publishes the 95th, 50th and 5th percentiles only.",
              choices=_MSFC_PERCENTILES),
    Parameter("lifetime.default_horizon_years", 30.0, "[year]",
              "How far a lifetime estimate looks ahead unless another is given.",
              "SpaceMissionStudio's own choice", "Past the 25-year guideline, so both rules can be decided.",
              minimum=0.1, maximum=100.0),
    Parameter("lifetime.default_deorbit_perigee_km", 250.0, "[km]",
              "The perigee the End of Life page's deorbit burn starts with.", "SpaceMissionStudio's own choice",
              minimum=130.0, maximum=2000.0),
)

# -- RF link (engine.link_budget) and data handling (engine.data_handling) -----------------------

register(
    Parameter("link.required_margin_db", 0.0, "[dB]",
              "The link closes while its Eb/N0 margin (over the required Eb/N0) is at least this: the simulated "
              "downlink is allowed, Vizard shows the link OK, and a lower margin is marked on the dashboard and "
              "the results overview.", "SpaceMissionStudio's own choice",
              "0 dB: the link closes with nothing to spare. Projects usually require a few dB; set that here.",
              minimum=-20.0, maximum=30.0),
    Parameter("link.pointing_loss_coeff_db", 12.0, "[dB]",
              "The pointing loss of a 'fixed' antenna with a beamwidth: this * (off-boresight angle / beamwidth)^2.",
              "Parabolic main-lobe approximation, as in Wertz & Larson, Space Mission Analysis and Design, ch. 13",
              "12 dB puts the loss at 3 dB half a beamwidth off boresight, the beamwidth's definition.",
              minimum=0.0, maximum=100.0),
    Parameter("link.max_pointing_loss_db", 30.0, "[dB]",
              "The most pointing loss a 'fixed' antenna's approximation gives; a larger angle is held at this.",
              "SpaceMissionStudio's own choice",
              "The approximation holds near boresight only; at 30 dB below the peak the link does not close.",
              minimum=0.0, maximum=200.0),
    Parameter("data_handling.packet_size_bits", 1.0e6, "[bit]",
              "The size of the packets the transmitter takes from the memory.",
              "Basilisk's examples/scenarioGroundDownlink.py", minimum=1.0, maximum=1.0e12),
    Parameter("data_handling.explainer_pass_minutes", 10.0, "[min]",
              "The pass length of the scenario explanation's 'Gbit per pass' note; a run's passes are predicted.",
              "SpaceMissionStudio's own choice", "A typical low Earth orbit pass.", minimum=0.1, maximum=1440.0),
)

# -- reading a run's results (engine.run_summary, engine.events, gui.results_overview, -------------
# -- gui.mission_dashboard_widget). Read back from a run's provenance, so a run shown later is judged by
# -- the values it was run with.

register(
    Parameter("results.sma_window_orbits", 1.0, "[orbit]",
              "The mean semi-major axis change averages over this many orbits at the start and at the end of a "
              "run; a run shorter than twice this has none.", "SpaceMissionStudio's own choice",
              "One orbit takes out what first-order mean elements leave of the orbital-period wobble.",
              minimum=0.1, maximum=100.0),
    Parameter("results.umbra_sunlight_fraction", 0.01, "[-]",
              "An eclipse whose lowest sunlight is below this fraction is listed as umbra, else as penumbra.",
              "SpaceMissionStudio's own choice", "1 %: the Sun fully hidden, within the shadow model's accuracy.",
              minimum=0.0, maximum=1.0),
    Parameter("results.pointing_converged_deg", 5.0, "[deg]",
              "The mission dashboard reads the comms pointing as converged below this pointing error, as "
              "slewing above it.", "SpaceMissionStudio's own choice", minimum=0.01, maximum=180.0),
    Parameter("results.battery_critical_fraction", 0.0, "[-]",
              "The results overview marks the lowest battery charge as critical at or below this fraction of the "
              "battery's capacity (0: only an empty battery).", "SpaceMissionStudio's own choice",
              "A project with a depth-of-discharge limit sets it here, e.g. 0.3 for 70 % depth of discharge.",
              minimum=0.0, maximum=1.0),
)

# -- the dynamics' run control (engine.service) --------------------------------------------------

register(
    Parameter("dynamics.integrator_relative_tolerance", 1e-10, "[-]",
              "The relative error tolerance of the adaptive integrators (rkf45, rkf78).",
              "SpaceMissionStudio's own choice (audit E3)",
              "Basilisk's 1e-4 let a 300 s step pass unrefined: a one-day two-body run was 384 m off Kepler's "
              "solution; at 1e-10 it is 11 m. Steps of 30 s or less are unaffected.",
              minimum=1e-14, maximum=1e-3),
    Parameter("dynamics.integrator_absolute_tolerance", 1e-8, "[m, m/s, rad]",
              "The absolute error tolerance of the adaptive integrators, one value for every state.",
              "Basilisk's default", minimum=1e-14, maximum=1e-2),
    Parameter("dynamics.reentry_altitude_km", 100.0, "[km]",
              "A run stops (or, without drag, warns) once a spacecraft's altitude is below this: the run's re-entry.",
              "SpaceMissionStudio's own choice",
              "Not the lifetime's 120 km (lifetime.reentry_altitude_km): that one is on the orbit-averaged perigee, "
              "this one on the simulated altitude, at which the run can no longer be integrated sensibly.",
              minimum=60.0, maximum=300.0),
    Parameter("dynamics.reentry_check_s", 21600.0, "[s]",
              "How often a run with drag checks for re-entry while every perigee is high.",
              "SpaceMissionStudio's own choice", "Six hours: a high orbit cannot re-enter between two checks.",
              minimum=60.0, maximum=86400.0),
    Parameter("dynamics.reentry_near_perigee_km", 200.0, "[km]",
              "Below this perigee altitude a run with drag checks for re-entry every reentry_near_check_s.",
              "SpaceMissionStudio's own choice", minimum=100.0, maximum=2000.0),
    Parameter("dynamics.reentry_near_check_s", 300.0, "[s]",
              "How often a run checks for re-entry once a perigee is low: the precision of the re-entry time.",
              "SpaceMissionStudio's own choice", minimum=1.0, maximum=21600.0),
    Parameter("dynamics.conservation_tolerance", 0.01, "[-]",
              "A two-body run warns when its orbital energy or angular momentum drifts by more than this "
              "fraction.", "SpaceMissionStudio's own choice",
              "1 %: a check for a numerical blow-up, not a grade of the integrator's accuracy.",
              minimum=1e-12, maximum=1.0),
)

# -- the environment's data rules (engine.spaceweather, engine.scenario_checks) ------------------

register(
    Parameter("space_weather.msfc_repeat_months", 132, "[month]",
              "Past the end of MSFC's solar-activity prediction its last this many months repeat, for runs and "
              "lifetimes that look further ahead.", "ESA AD10 Sec. 5.9",
              "132 months: one solar cycle. A table must hold at least this many months.",
              kind="integer", minimum=12, maximum=600),
    Parameter("tle.age_warning_days", 3.0, "[day]",
              "The scenario checks warn when a TLE's epoch is further than this from the scenario epoch: SGP4's "
              "accuracy drops with the span it propagates over.", "SpaceMissionStudio's own choice",
              minimum=0.0, maximum=3650.0),
)

# -- orbit controllers (engine.orbit_maintenance, engine.geo_station_keeping) -----------------

register(
    Parameter("orbit_control.eccentricity_gate_factor", 2.5, "[-]",
              "With eccentricity-neutral burns, a new firing may start only while the burn's accumulated "
              "eccentricity change stays within the larger of one orbit's excursion under continuous thrust and "
              "this many times twice the change one firing makes.", "SpaceMissionStudio's own choice",
              "Ported with the controller; the code records no derivation for 2.5. Smaller holds back more "
              "firings and keeps the eccentricity closer to its start; larger fires more often.",
              minimum=0.5, maximum=20.0),
    Parameter("orbit_control.min_impulse_skip_fraction", 0.5, "[-]",
              "A burn needing less than one minimum firing (thrust x minimum on-time) is rounded up to one if it "
              "needs at least this fraction of it, and skipped otherwise.", "SpaceMissionStudio's own choice",
              "Half: the burn is rounded to the nearer of no firing and one firing.",
              minimum=0.0, maximum=1.0),
    Parameter("orbit_control.phasing_non_convergent_cycles", 2, "[-]",
              "Phasing keeping suspends its corrections after this many full correction cycles in a row that "
              "end outside the tolerance, rather than burn propellant into a correction that does not converge.",
              "SpaceMissionStudio's own choice",
              "Two, not one: a single cycle can end outside the tolerance from the smoothing window's noise at a "
              "cycle boundary; two in a row cannot.", kind="integer", minimum=1, maximum=50),
    Parameter("orbit_control.relative_sma_trim_m", 25.0, "[m]",
              "Phasing keeping trims a difference of the follower's and chief's one-orbit-mean semi-major axes "
              "larger than this on its own (a reboost only one of them made), whatever the phase error.",
              "SpaceMissionStudio's own choice",
              "Far above the 0.1 m the one-orbit mean measures under J2, and a small part of the 5 km a lone "
              "reboost leaves.", minimum=0.1, maximum=10000.0),
    Parameter("geo_station_keeping.max_half_arc_deg", 60.0, "[deg]",
              "A north-south burn is centred on a node and spans at most this much of the orbit on each side; "
              "a correction needing more is finished at later nodes.", "SpaceMissionStudio's own choice",
              "Thrust off the node changes the inclination by the cosine of the angle from it: at 60 deg, "
              "half as much.", minimum=1.0, maximum=90.0),
    Parameter("geo_station_keeping.inclination_reset_fraction", 0.25, "[-]",
              "A north-south maneuver, started when the inclination passes its limit, brings it down to this "
              "fraction of the limit.", "SpaceMissionStudio's own choice",
              "The code records no derivation for a quarter. A smaller fraction makes each maneuver larger and "
              "the next one later.", minimum=0.0, maximum=0.95),
    Parameter("geo_station_keeping.fit_interval_s", 600.0, "[s]",
              "How often the east-west control fits its last sidereal day of longitude samples (a line plus the "
              "daily libration) for the longitude and drift rate.", "SpaceMissionStudio's own choice",
              "Ten minutes: the drift changes over days, and the fit costs a least-squares solve.",
              minimum=1.0, maximum=86400.0),
    Parameter("geo_station_keeping.drift_stop_fraction", 0.25, "[-]",
              "When the Earth's triaxiality is already pulling the satellite back into its box, a burn stops "
              "its drift only if it would otherwise travel more than this fraction of the deadband further "
              "out first.", "SpaceMissionStudio's own choice",
              "A quarter of the box: smaller overshoots are left to the triaxiality to turn around.",
              minimum=0.0, maximum=10.0),
    Parameter("geo_station_keeping.ns_completion_fraction", 0.9, "[-]",
              "A north-south burn that delivered at least this fraction of the delta-V it needed ends the "
              "maneuver; one cut shorter (started mid-arc) is finished at the next node.",
              "SpaceMissionStudio's own choice",
              "Nine tenths: otherwise the inclination's short-period wobble would ask for a touch-up at every "
              "node.", minimum=0.1, maximum=1.0),
)

register(
    Parameter("roe_formation.holding_check_fraction", 0.25, "[orbit]",
              "The impulsive law looks at the formation again this many orbits after a decision that planned "
              "nothing, and this long after a burn while a drift is under way.", "SpaceMissionStudio's own choice",
              "No derivation recorded. Shorter catches an error sooner and decides more often; longer lets an "
              "error grow further before it is corrected.", minimum=0.01, maximum=5.0),
    Parameter("roe_formation.glide_orbits", 3.0, "[orbit]",
              "A drift's relative semi-major axis is cut back as the target nears, so that the rest of the "
              "along-track offset closes in no less than this many orbits.", "SpaceMissionStudio's own choice",
              "No derivation recorded. The stop burns take time to fire, and the mean longitude keeps drifting "
              "until they do; a slower end makes where it stops more certain.", minimum=0.5, maximum=50.0),
    Parameter("roe_formation.direct_dl_factor", 5.0, "[-]",
              "An along-track offset up to this many along-track tolerances is corrected directly, with burns "
              "over the next two orbits that set the relative semi-major axis, the e vector and the mean "
              "longitude together; a larger one drifts.", "SpaceMissionStudio's own choice",
              "No derivation recorded.", minimum=1.0, maximum=100.0),
    Parameter("roe_formation.eclipse_retries", 3, "[-]",
              "A planned burn that meets eclipse waits an orbit and tries again at the same place; after this "
              "many tries the plan is dropped and made again.", "SpaceMissionStudio's own choice",
              "No derivation recorded. The controller learns where the last orbit was in eclipse, so a new "
              "plan usually avoids it.", kind="integer", minimum=1, maximum=20),
    Parameter("roe_formation.drag_min_orbits", 4.0, "[orbit]",
              "With differential drag, the decay of the relative semi-major axis is fitted only once this many "
              "orbits of data are in since the last burn or jump.", "SpaceMissionStudio's own choice",
              "Shorter fits are biased by the orbit's own oscillation of the mean elements; the code records "
              "no derivation for four.", minimum=1.0, maximum=100.0),
    Parameter("roe_formation.drag_jump_m", 0.1, "[m]",
              "A change of the relative semi-major axis (times the chief's) larger than this between two samples "
              "starts a new stretch of the decay fit: a burn the controller did not make, such as the chief's "
              "reboost.", "SpaceMissionStudio's own choice",
              "No derivation recorded.", minimum=0.001, maximum=100.0),
    Parameter("roe_formation.drag_hold_fraction", 0.6, "[-]",
              "A differential-drag cycle sets the relative semi-major axis and mean longitude so that both swing "
              "about their targets within this fraction of their tolerances.", "SpaceMissionStudio's own choice",
              "No derivation recorded.", minimum=0.1, maximum=1.0),
    Parameter("roe_formation.drag_lookahead_orbits", 2.0, "[orbit]",
              "A drag cycle's hold check propagates the relative semi-major axis and mean longitude this many "
              "orbits ahead, decay included, about when a correction's last burn would fire.",
              "SpaceMissionStudio's own choice", "No derivation recorded; a correction's burns span about two "
              "orbits.", minimum=0.0, maximum=20.0),
    Parameter("roe_formation.drag_trigger_fraction", 0.7, "[-]",
              "A drag cycle is corrected when the relative semi-major axis or the mean longitude, propagated "
              "drag_lookahead_orbits ahead, would be past this fraction of its tolerance: just after the "
              "cycle's end, never at its turn.", "SpaceMissionStudio's own choice",
              "No derivation recorded. Above drag_hold_fraction, so a cycle is not corrected at its turn.",
              minimum=0.1, maximum=1.0),
    Parameter("roe_formation.drag_significance_fraction", 0.5, "[-]",
              "A differential-drag decay is compensated only when it would move the mean longitude by more than "
              "this fraction of its tolerance over the correction window; a smaller one, such as the estimate's "
              "scatter for twin spacecraft, is left to the ordinary corrections.",
              "SpaceMissionStudio's own choice", "No derivation recorded.", minimum=0.01, maximum=10.0),
    Parameter("roe_formation.slow_drift_fraction", 0.25, "[-]",
              "A drift ends at a slow relative semi-major axis: the larger of this fraction of the semi-major "
              "axis tolerance and the drift whose stop steps fit the along-track tolerance.",
              "SpaceMissionStudio's own choice", "No derivation recorded.", minimum=0.01, maximum=5.0),
    Parameter("roe_formation.stop_band_factor", 1.5, "[-]",
              "A drift is stopped, once stopping brings the mean longitude to the target, only when its relative "
              "semi-major axis is within this factor of the slow drift.", "SpaceMissionStudio's own choice",
              "No derivation recorded. With cutback_band_factor, it keeps a drift from being planned again at "
              "each check.", minimum=1.0, maximum=10.0),
    Parameter("roe_formation.cutback_band_factor", 1.25, "[-]",
              "A drift is cut back to the glide-in drift (glide_orbits) only when it is more than this factor of "
              "it; within the band it is held.", "SpaceMissionStudio's own choice",
              "No derivation recorded. With stop_band_factor, it keeps a drift from being planned again at each "
              "check.", minimum=1.0, maximum=10.0),
    Parameter("roe_formation.stop_reached_fraction", 0.5, "[-]",
              "Stopping a drift is taken to bring the mean longitude to the target when it would end past the "
              "target or within this fraction of the along-track tolerance of it.",
              "SpaceMissionStudio's own choice", "No derivation recorded.", minimum=0.01, maximum=1.0),
    Parameter("roe_formation.min_check_s", 60.0, "[s]",
              "While a drift is held, the controller looks again before its stop is due, but no sooner than "
              "this.", "SpaceMissionStudio's own choice", "No derivation recorded.", minimum=1.0, maximum=3600.0),
    Parameter("roe_formation.replan_shift_fraction", 0.25, "[-]",
              "A drift's burns set the relative semi-major axis one by one, so the mean longitude ends up "
              "elsewhere than planned: the plan is made again from where they lead when that shift is more than "
              "this fraction of the along-track tolerance.", "SpaceMissionStudio's own choice",
              "No derivation recorded.", minimum=0.01, maximum=10.0),
)


register(
    Parameter("flight_software.thruster_min_fire_time_s", 0.002, "[s]",
              "The attitude thrusters' Schmitt trigger (Basilisk's thrFiringSchmitt): the shortest on-time it "
              "commands. A shorter request fires for this long or not at all, by thruster_level_on and "
              "thruster_level_off.",
              "Basilisk's examples/scenarioAttitudeFeedback2T_TH.py",
              "The example's value for its attitude-control thrusters; it is not derived for this app's "
              "thrusters.", minimum=1e-4, maximum=10.0),
    Parameter("flight_software.thruster_level_on", 0.75, "[-]",
              "The Schmitt trigger turns a thruster on (for the minimum fire time) when a request shorter than "
              "the minimum fire time is at least this fraction of it.", "Basilisk's examples/scenarioAttitudeFeedback2T_TH.py",
              "The example's value.", minimum=0.0, maximum=1.0),
    Parameter("flight_software.thruster_level_off", 0.25, "[-]",
              "The Schmitt trigger turns a thruster off when a request shorter than the minimum fire time is "
              "at most this fraction of it; between the two levels the thruster keeps its last state.", "Basilisk's examples/scenarioAttitudeFeedback2T_TH.py",
              "The example's value. It must be below thruster_level_on.", minimum=0.0, maximum=1.0),
)

register(
    Parameter("navigation.opnav_ukf_alpha", 0.02, "[-]",
              "Optical navigation's filter (Basilisk's relativeODuKF): the spread of the unscented transform's "
              "sigma points.", "Basilisk's relativeODuKF unit test and examples/OpNavScenarios",
              "Their value.", minimum=1e-4, maximum=1.0),
    Parameter("navigation.opnav_ukf_beta", 2.0, "[-]",
              "Optical navigation's filter: the unscented transform's weight on the prior's distribution.", "Basilisk's relativeODuKF unit test and examples/OpNavScenarios",
              "Their value.", minimum=0.0, maximum=10.0),
    Parameter("navigation.opnav_ukf_kappa", 0.0, "[-]",
              "Optical navigation's filter: the unscented transform's secondary scaling.",
              "Basilisk's relativeODuKF unit test and examples/OpNavScenarios", "Their value.",
              minimum=-10.0, maximum=10.0),
    Parameter("navigation.opnav_ukf_noise_scale", 1.0, "[-]",
              "Optical navigation's filter: relativeODuKF's noiseSF, which its header calls the scale factor "
              "for measurement noise (it scales the sigma points' spread in the measurement update).",
              "Basilisk's relativeODuKF unit test", "Its value.", minimum=1e-3, maximum=1e3),
    Parameter("navigation.landmark_filter_max_step_s", 60.0, "[s]",
              "Landmark navigation's filter propagates its state between measurements with RK4 steps no longer "
              "than this.", "SpaceMissionStudio's own choice", "No derivation recorded.",
              minimum=1.0, maximum=3600.0),
)


register(
    Parameter("checks.pass_step_s", 30.0, "[s]",
              "The pre-run pass prediction samples each station's elevation this often.",
              "SpaceMissionStudio's own choice",
              "A LEO pass above 10 deg lasts several minutes (the code's comment); no derivation recorded for "
              "30 s.", minimum=1.0, maximum=600.0),
    Parameter("checks.pass_horizon_days", 7.0, "[day]",
              "Passes are predicted over the run up to this long; a longer run's passes are counted over this "
              "much (\"in the first week\").", "SpaceMissionStudio's own choice",
              "Keeps the check fast on long runs (the code's comment).", minimum=0.1, maximum=365.0),
    Parameter("checks.pass_lookahead_days", 2.0, "[day]",
              "When a station has no pass in the run, the prediction looks this far past it for the first one.",
              "SpaceMissionStudio's own choice", "No derivation recorded.", minimum=0.0, maximum=30.0),
    Parameter("checks.many_samples", 1_000_000, "[-]",
              "Recording every step is flagged when a series would hold more samples than this.",
              "SpaceMissionStudio's own choice",
              "About 1.7 MB per simulated day at full recording for one LEO spacecraft (the code's comment); "
              "no derivation recorded for the limit.", kind="integer", minimum=1000, maximum=1_000_000_000),
    Parameter("checks.coarse_recording_factor", 3.0, "[-]",
              "Recording is flagged as too coarse for the passes when the shortest predicted pass (over the "
              "first day) lasts no more than this many recording intervals.", "SpaceMissionStudio's own choice",
              "No derivation recorded.", minimum=1.0, maximum=100.0),
    Parameter("checks.long_step_s", 60.0, "[s]",
              "A dynamics step longer than this is flagged: the orbit loses accuracy whatever the integrator's "
              "tolerance.", "SpaceMissionStudio's measurement (audit E3, 2026-10-27)",
              "In a one-day two-body run at 7000 km against Kepler, the position error was under 2 cm at 60 s, "
              "0.9 m at 120 s, 11 m at 300 s and 8.6 km at 1800 s.", minimum=1.0, maximum=3600.0),
    Parameter("checks.late_first_pass_fraction", 0.5, "[-]",
              "A station whose first pass comes later than this fraction of the run is flagged.",
              "SpaceMissionStudio's own choice", "No derivation recorded.", minimum=0.0, maximum=1.0),
    Parameter("checks.css_facing_min_cosine", 0.5, "[-]",
              "A coarse sun sensor counts as facing the Sun-pointing axis when the cosine of the angle between "
              "its normal and the axis is above this (0.5: within 60 deg); with none facing it, the spacecraft "
              "is flagged.", "SpaceMissionStudio's own choice", "No derivation recorded.",
              minimum=-1.0, maximum=1.0),
)


register(
    Parameter("explain.sso_tolerance_deg", 0.1, "[deg]",
              "Explain labels a classical-elements orbit Sun-synchronous when its inclination is within this of "
              "the Sun-synchronous inclination at its own semi-major axis and eccentricity.",
              "SpaceMissionStudio's own choice",
              "Wide enough for the 2-decimal rounding of the templates' inclinations, narrow enough that an "
              "unrelated inclination (51.6 deg) never matches (the code's comment).", minimum=0.0, maximum=10.0),
    Parameter("explain.differential_drag_fraction", 0.05, "[-]",
              "Explain notes differential drag in an ROE formation when the follower's flat-plate ballistic "
              "coefficient (Cd A / dry mass) differs from the chief's by more than this fraction of the larger.",
              "SpaceMissionStudio's own choice", "No derivation recorded.", minimum=0.0, maximum=1.0),
    Parameter("explain.passive_safety_margin_m", 1.0, "[m]",
              "Explain calls an ROE target not passively safe when the closest radial/cross-track approach of "
              "the two orbits is no more than this.", "SpaceMissionStudio's own choice",
              "No derivation recorded.", minimum=0.0, maximum=1e4),
    Parameter("explain.camera_axis_tolerance_deg", 1.0, "[deg]",
              "Explain warns when locationPointing's pointing axis (pHat_B) is further than this from the "
              "optical navigation camera's boresight.", "SpaceMissionStudio's own choice",
              "No derivation recorded.", minimum=0.0, maximum=90.0),
)
