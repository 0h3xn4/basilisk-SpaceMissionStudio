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
read, then the dynamics' run control.

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
              "Below about 120 km an orbit lasts days at most. A full simulation run stops at 100 km "
              "(engine.service); Phase 3c of the transparency plan chooses one value for both.",
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
