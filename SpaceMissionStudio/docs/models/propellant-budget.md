# Propellant budget

The delta-V and propellant budget of one spacecraft, in the manner of
ESA's guideline AD10, "Guidelines for the computation of the Delta-V and
Propellant Mass budgets" (EOP-FM/2024-07-177, issue 3.0). Section numbers
below are AD10's. Code: `spacemissionstudio/engine/propellant_budget.py`.
How to use it: [Lifetime and propellant budget](../user-manual/lifetime-and-budget.md).

## What it computes

The budget follows the mission's three phases. Each contributor gives a
delta-V, a propellant mass or both:

| Phase | Contributors |
|---|---|
| Beginning of life | Launcher injection errors (in-plane, out-of-plane, RAAN), orbit acquisition |
| Operations | Orbit transfers, in- and out-of-plane orbit control, collision avoidance, formation keeping, thruster attitude control, Hall thruster ignitions |
| End of life | Clearance, disposal (uncontrolled re-entry, controlled re-entry or GEO graveyard) |
| Propellant | Residual, loading uncertainty and gauging |

**Propellant of a burn** (Secs. 6.1.3, 6.2.7, 6.3.4): the rocket equation
from the mass before the burn,

    m_prop = m * (1 - exp(-dV / Ve)),   Ve = eta * Isp * g0

with `eta` the thruster efficiency (Sec. 5.11: `cos(thrust angle) *
cos(misalignment) * plume efficiency * modulation efficiency`) and
`g0 = 9.80665 m/s^2`. The contributors are taken in the order of the
table, each from the mass the ones before it left.

**Iteration** (Sec. 6.5): the mass at the beginning of life is the dry
mass plus the propellant total, which is not known yet. The budget starts
from the tank capacity (or zero) and repeats until the total changes by
less than `convergence_kg` (0.1 kg), at most `max_iterations` (50) times.

**Dry mass** (Sec. 5.10): the dry mass entered, plus the system margin
(`propellant_budget.system_margin_fraction` in the scenario, 15 %) unless
it already includes one.

## How each contributor is found

- **Entered** (`input`): the value given in the scenario's
  `propellant_budget` block.
- **From the last run** (`last run`; Sec. 6.2.7, "via simulation"):
  in- and out-of-plane control and formation keeping as flown. A run
  shorter than the mission by more than `scaled_run_ratio` (1.05) is
  scaled up to it (`last run, scaled`), with a note.
- **Estimated** (`estimated`): without a run, a LEO station keeper's
  in-plane control is the drag make-up of its held orbit over the mission
  (`engine.lifetime.drag_makeup`), at MSFC's `operations_percentile`
  (95th) and the spacecraft's drag coefficient. Against full five-year
  station-keeping runs it comes out about 5 % low, which the note says.
- **Computed** (`computed`):
  - injection errors: the larger of the semi-major-axis and
    eccentricity-vector corrections, and the inclination change (Sec. 6.1.1);
  - a collision avoidance: `cam_sma_change_m` (100 m) up and back, on a
    circular orbit at the operational semi-major axis (Sec. 6.2.4);
  - clearance: the semi-major axis lowered by the drop entered (Sec. 6.3.2);
  - an uncontrolled re-entry: an apogee burn lowering the perigee until
    the orbit's lifetime from the end of the mission is
    `disposal_lifetime_years` (5, Sec. 6.3.1.2), estimated with the
    lifetime model at MSFC's `eol_percentile` (50th) and Cd
    `eol_drag_coeff` (2.2), with the tumbling average area (Secs. 5.9,
    5.2, 5.3);
  - a GEO graveyard orbit: raised by `geo_graveyard_base_m +
    geo_graveyard_per_cr_a_m * Cr * A / m` (235 km + 1000 km per m^2/kg),
    as a Hohmann transfer (Sec. 6.3.1.3).

## Rules and margins

Each is a named parameter, `propellant_budget.<name>`. `spacemissionstudio
assumptions --area propellant_budget` lists the values in effect, and a
project configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `cam_count_factor` | 4 | [-] | Multiplies the number of collision avoidances entered | AD10 Sec. 5.6 |
| `cam_sma_change_m` | 100 | [m] | The semi-major axis change of one avoidance, up then back | AD10 Sec. 6.2.4 |
| `attitude_propellant_factor` | 2 | [-] | Multiplies the attitude-control propellant entered (+100 %) | AD10 Sec. 5.6 |
| `controlled_last_burn_margin` | 0.15 | [-] | Added to a controlled re-entry's last burn (+15 %) | AD10 Sec. 5.6 |
| `residual_fraction` | 0.01 | [-] | Unusable residual, as a fraction of the tank load | AD10 Sec. 5.8 |
| `uncertainty_fraction` | 0.02 | [-] | Loading and gauging uncertainty, as a fraction of the tank load | AD10 Secs. 5.8, 6.4 |
| `eol_drag_coeff` | 2.2 | [-] | Cd of the uncontrolled re-entry estimate | AD10 Sec. 5.2 |
| `operations_drag_coeff` | 3.0 | [-] | Cd AD10 asks for in operations; another is noted | AD10 Sec. 5.2 |
| `operations_percentile` | 95 | [%] | MSFC solar activity of the in-plane estimate and the launch-delay sweep; another in the run is noted | AD10 Sec. 5.9 |
| `eol_percentile` | 50 | [%] | MSFC solar activity of the re-entry estimate | AD10 Sec. 5.9 |
| `geo_graveyard_base_m` | 235 000 | [m] | The fixed part of the graveyard raise | AD10 Sec. 6.3.1.3 (IADC) |
| `geo_graveyard_per_cr_a_m` | 1 000 000 | [m per (m^2/kg)] | The graveyard raise per unit of Cr * A / m | AD10 Sec. 6.3.1.3 (IADC) |
| `convergence_kg` | 0.1 | [kg] | The iteration stops when the total changes by less | AD10 Sec. 6.5 |
| `max_iterations` | 50 | [-] | The most iterations before "did not settle" | SpaceMissionStudio's own choice |
| `launch_delays_years` | 0, 1, 2, 3, 4, 5 | [year] | The launches the launch-delay sweep and the altitude trade repeat the budget for | AD10 Sec. 5.5 |
| `scaled_run_ratio` | 1.05 | [-] | A run shorter than the mission by more than this is scaled up, and noted | SpaceMissionStudio's own choice |
| `altitude_step_km` | 50 | [km] | The spacing of an altitude trade's five default altitudes | SpaceMissionStudio's own choice |
| `altitude_floor_km` | 250 | [km] | The lowest default altitude of an altitude trade | SpaceMissionStudio's own choice |

The residual and uncertainty follow AD10's equations, 1 % and 2 %; its
summary table prints 10 % and 20 %, and the budget's notes say so.

**Constants**, not parameters: Earth's GM (398 600.436 km^3/s^2) and
equatorial radius (6378.1366 km), from the one set
([Physical constants](constants.md)), and standard gravity `g0`
(9.80665 m/s^2, by definition).

## Assumptions

- Every impulsive delta-V uses the circular speed at the operational
  semi-major axis.
- The burns are impulsive; finite-burn gravity losses outside the
  simulations are not included (Sec. 5.4).
- The injection-error correction takes the larger of the semi-major-axis
  and eccentricity corrections, not their sum.
- The drag make-up estimate holds the mass fixed at the start of the
  window.

## Not covered

- The number of collision avoidances: ESA's DRAMA computes it; enter it.
- Hybrid propulsion systems.
- Launch-date effects other than drag, such as the Moon's 18.6-year cycle
  in GEO north-south control.

## Outputs and records

The **Budget** page and `spacemissionstudio budget` print one row per
contributor with its phase, delta-V, propellant, margin and source, and
the notes. `budget --out FILE.json` writes the record: the inputs, the
rules in effect under their parameter names, the rows and totals, the
notes, and the provenance, including the project configuration file and
each value it changes.
