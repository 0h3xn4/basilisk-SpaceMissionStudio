# Explain and the mission sequence

The rules behind two kinds of output:
- **Explain** (Scenario › Overview): a structured summary of what a
  scenario does, rebuilt on every edit;
- **the mission sequence's numerical settings:** the values its commands
  use that a scenario does not set.

Code: `spacemissionstudio/engine/scenario_explainer.py`,
`engine/mission_engine.py`. Explain never raises: a half-edited scenario
gets a shorter summary, not an error. Its warnings come from the
[pre-run checks](pre-run-checks.md); the rules below are Explain's own.

## Explain's rules

- **The Sun-synchronous label:** a classical-elements orbit about a body
  whose gravity models J2 is labelled "SSO" when its inclination is
  within `sso_tolerance_deg` (0.1 deg) of the Sun-synchronous inclination
  at its own semi-major axis and eccentricity. The tolerance is wide
  enough for the 2-decimal rounding of the templates' inclinations and
  narrow enough that an unrelated inclination (51.6 deg) never matches.
- **Differential drag in an ROE formation:** Explain notes it when the
  follower's flat-plate ballistic coefficient (drag coefficient times
  area over dry mass) differs from the chief's by more than
  `differential_drag_fraction` (5 %) of the larger. With facets the
  area depends on the attitude, so no note is given.
- **Passive safety of an ROE target:** a target is "not passively safe"
  when the closest radial/cross-track approach of the two orbits is no
  more than `passive_safety_margin_m` (1 m); otherwise Explain gives that
  approach.
- **The optical navigation camera's axis:** with attitude, Explain warns
  when `locationPointing`'s pointing axis (`pHat_B`) is further than
  `camera_axis_tolerance_deg` (1 deg) from the camera's boresight.

## Rules and parameters

Each is a named parameter, `explain.<name>`. `spacemissionstudio
assumptions --area explain` lists the values in effect, and a project
configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `explain.sso_tolerance_deg` | 0.1 | [deg] | How close to Sun-synchronous an orbit must be to be labelled so | SpaceMissionStudio's own choice (the code's reason above) |
| `explain.differential_drag_fraction` | 0.05 | [-] | The ballistic-coefficient difference that gives the differential-drag note | SpaceMissionStudio's own choice (no derivation recorded) |
| `explain.passive_safety_margin_m` | 1 | [m] | The closest approach at or below which a target is not passively safe | SpaceMissionStudio's own choice (no derivation recorded) |
| `explain.camera_axis_tolerance_deg` | 1 | [deg] | How far the pointing axis may be from the camera's boresight | SpaceMissionStudio's own choice (no derivation recorded) |

**Not parameters:**
- **The aliasing badge's 0.5 per sample:** a flexing mode faster than
  half the sampling rate is aliased. That is Nyquist's limit, not a
  choice.

## The mission sequence's numerical settings

None of these is a parameter; each sets no result a project would tune:
- **Lambert's delta-V convergence tolerance (1 m/s, Basilisk's
  `examples/scenarioLambertSolver.py`):** Basilisk's `lambertValidator`
  compares the delta-V of successive solutions. The app's mini-simulation
  gives the solver the same state at each tick, so they always agree, and
  the tolerance cannot change the transfer (checked:
  `tests/test_lambert_transfer.py::test_the_convergence_tolerance_sets_no_result`,
  the same delta-V at 1e-6, 1 and 100 m/s).
- **The Lambert mini-simulation's cadence (30 s task, 2 ticks):** the
  example's; it never propagates dynamics.
- **Starting on an apsis (radial velocity below 1e-6 m/s):** a numerical
  zero. Rounding leaves about 1e-13 m/s at an apsis, and one dynamics
  step changes the radial velocity by about 1 m/s in LEO.
- **Caps that stop a runaway sequence with an error:** 10,000 iterations
  of a loop; an event search of 10 times the run (at least a day); the
  one-run limit of 100 days (one Basilisk run keeps time in nanoseconds
  and fails past about 104).
- **Abort granularity:** a long propagate is run in about 60 pieces, so
  Abort takes effect soon.

The defaults a mission sequence command carries (a Lambert transfer's
1000 m maximum distance from the target, its 0 m minimum orbit radius)
are the command's own fields, set in the mission sequence editor.

## Checked against

- `tests/test_scenario_explainer.py`: the summary of every template, a
  half-edited scenario.
- `tests/test_config.py`: each parameter changes what Explain says, and
  set to its default leaves it as it was.
- `tests/test_lambert_transfer.py`: the transfer reaches its target; the
  convergence tolerance sets no result.
