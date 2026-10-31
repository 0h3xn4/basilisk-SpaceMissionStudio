# Orbit control: station keeping, phasing and GEO station keeping

How the run's orbit controllers decide when to fire:
- altitude station keeping;
- the thruster's firing model, shared by station keeping and phasing;
- phasing keeping, which holds a follower at its along-track separation
  from a chief;
- GEO station keeping, which holds a longitude box and an inclination
  limit.

Code: `spacemissionstudio/engine/orbit_maintenance.py`,
`engine/geo_station_keeping.py`. The scenario sets each controller's
targets, thrust, specific impulse and propellant
(`station_keeping`, `phasing_keeping`, `geo_station_keeping`); the
parameters below are the rules inside the controllers. The ROE formation
controller's guidance has its own page:
[ROE formation guidance](roe-formation.md).

The controllers apply their thrust as an ideal inertial force through
Basilisk's `extForceTorque`. Each tracks its propellant with the rocket
equation, g0 being the standard 9.80665 m/s^2
([Physical constants](constants.md)), and feeds the mass back into the
simulation every step.

## Altitude station keeping

The orbit-averaged altitude, a boxcar over one orbital period, is kept
no more than `deadband_km` below `target_altitude_km`. When it falls
below that, a reboost along the velocity starts; it ends when the
average is back at the target. With an
`eclipse_sunlit_threshold`, thrust is allowed only while the
illumination is above it, as for a solar-electric bus.

## The firing model

One physical thruster serves station keeping and phasing:
- **Minimum on-time** (`min_on_time_s`): a firing lasts at least this
  long. A burn needing less than one minimum firing is rounded up to one
  if it needs at least `min_impulse_skip_fraction` (0.5) of it, and
  skipped otherwise.
- **Eccentricity-neutral burns** (`eccentricity_neutral_burns`):
  tangential thrust at argument of latitude u changes the eccentricity
  vector by about (2 dv / v)(cos u, sin u). Eclipse gating cuts the same
  arc out of every orbit, so a reboost over many orbits would add
  eccentricity. With this on, a new firing starts only while the
  maneuver's accumulated change stays within the larger of:
  - 4 a / (v n), the circle continuous thrust traces in one orbit;
  - `eccentricity_gate_factor` (2.5) times 2 a t / v, twice the change
    one firing of duration t makes.

  Here a is the thrust's acceleration, v the speed and n the mean motion.

## Phasing keeping

The follower's along-track phase from its chief is held within
`tolerance_fraction` of the target separation. A correction raises or
lowers the follower's orbit by

    delta_a = error * a / (1.5 n T)

so that it drifts back over `correction_window_days` (T), then restores
the semi-major axis. Two rules guard it:
- **Divergence:** after `phasing_non_convergent_cycles` (2) full
  correction cycles in a row that end outside the tolerance, corrections
  are suspended. Burning on would spend propellant on a correction that
  does not converge, typically because the follower's orbit is too far
  from the near-circular one the drift law assumes. A new target in the
  separation schedule starts afresh.
- **Trim:** a difference of the two one-orbit-mean semi-major axes larger
  than `relative_sma_trim_m` (25 m) is trimmed on its own, whatever the
  phase error. This catches a reboost only one spacecraft made, for
  example. The same value decides when a correction finer than one
  minimum firing is flown as one firing out and one back.

## GEO station keeping

Longitude and inclination are measured in the Earth's rotating frame,
from the central body's SPICE state.

**East-west.** The controller fits the last sidereal day of longitude
samples with a line plus the daily libration. It refits every
`fit_interval_s` (600 s), giving the longitude and drift rate. When the
satellite leaves its box heading outward:
- if the Earth's triaxiality accelerates it outward, a burn sends it
  back across the box on a parabola that just reaches the far edge;
- if the triaxiality already pulls it back, a burn stops the drift only
  if the satellite would otherwise travel more than `drift_stop_fraction`
  (0.25) of the deadband further out.

The longitude acceleration is

    lambda_ddot = 18 omega^2 J22 (R / a)^2 sin(2 (lambda - lambda22))

with the Earth's J22 and lambda22 from the GGM03S field the run loads
([Physical constants](constants.md)). A tangential delta-V changes the
drift rate by -3 dv / a.

**North-south.** When the inclination passes `inclination_max_deg`, a
burn centred on the next node brings it down to
`inclination_reset_fraction` (0.25) of the limit. The burn spans at most
`max_half_arc_deg` (60 deg) on each side of the node; the rest is
flown at later nodes. A burn that delivered at least
`ns_completion_fraction` (0.9) of its delta-V ends the maneuver. Burns
are not eclipse-gated: GEO station-keeping thrusters are usually chemical.

## Rules and parameters

Each is a named parameter: `orbit_control.<name>` or
`geo_station_keeping.<name>`. `spacemissionstudio assumptions --area
orbit_control` (or `--area geo_station_keeping`) lists the values in
effect, and a project configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `orbit_control.eccentricity_gate_factor` | 2.5 | [-] | How much eccentricity change a new firing may add, in single firings' worth | SpaceMissionStudio's own choice (no derivation recorded) |
| `orbit_control.min_impulse_skip_fraction` | 0.5 | [-] | The fraction of a minimum firing a burn must need to be fired rather than skipped | SpaceMissionStudio's own choice |
| `orbit_control.phasing_non_convergent_cycles` | 2 | [-] | Cycles ending outside the tolerance before phasing suspends itself | SpaceMissionStudio's own choice |
| `orbit_control.relative_sma_trim_m` | 25 | [m] | The relative semi-major axis phasing trims on its own | SpaceMissionStudio's own choice |
| `geo_station_keeping.max_half_arc_deg` | 60 | [deg] | The longest north-south burn arc each side of a node | SpaceMissionStudio's own choice |
| `geo_station_keeping.inclination_reset_fraction` | 0.25 | [-] | The inclination a north-south maneuver aims for, as a fraction of the limit | SpaceMissionStudio's own choice (no derivation recorded) |
| `geo_station_keeping.fit_interval_s` | 600 | [s] | How often the east-west drift fit is redone | SpaceMissionStudio's own choice |
| `geo_station_keeping.drift_stop_fraction` | 0.25 | [-] | The overshoot, as a fraction of the deadband, that a drift-stopping burn prevents | SpaceMissionStudio's own choice |
| `geo_station_keeping.ns_completion_fraction` | 0.9 | [-] | The fraction of its delta-V that ends a north-south maneuver | SpaceMissionStudio's own choice |

**Not parameters:**
- **The physical constants**, including the Earth's J22 and lambda22
  ([Physical constants](constants.md)).
- **The empty-tank floor** (1e-9 kg): below it, thrust stops and the run
  warns once. It is a numerical zero, not a rule.
- **The one-orbit smoothing window:** an orbit's average removes the
  orbit's own oscillation, which is what the controllers' laws assume.

## Assumptions

- The thrust is an ideal inertial force. The spacecraft does not slew to
  point its thruster, and an orbit-only run has no attitude.
- Phasing's drift law is linear and near-circular.
- GEO station keeping plans with the triaxiality term alone; the Sun and
  Moon act on the orbit in the run, not in the plan.

## Checked against

- `tests/test_orbit_maintenance.py` and `tests/test_geo_station_keeping.py`:
  the controllers' decisions, the divergence guard, the drift fit, the
  stable and unstable longitudes.
- `tests/test_constants.py`: J22 and lambda22 against the GGM03S file.
- `tests/test_config.py`: each parameter changes what it controls, and
  the run gives each controller its scenario.
