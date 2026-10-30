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
regression baseline to change no number: the propellant budget first.

"AD10" is ESA's "Guidelines for the computation of the Delta-V and
Propellant Mass budgets", EOP-FM/2024-07-177, issue 3.0.
"""

from .registry import Parameter, register

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
              "with another is noted.", "AD10 Sec. 5.9", minimum=5.0, maximum=95.0),
    Parameter("propellant_budget.eol_percentile", 50.0, "[%]",
              "The MSFC solar-activity percentile of the end-of-life disposal estimate.",
              "AD10 Sec. 5.9", minimum=5.0, maximum=95.0),
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
