# Dynamics: integration and run control

How a run is integrated and watched while it runs:
- the integrator's error tolerances;
- the checks for re-entry;
- the bodies that shadow a spacecraft from the Sun;
- the energy and momentum check of two-body runs.

Code: `spacemissionstudio/engine/service.py`, `engine/results.py`. How to
set the integrator and the step: the User Manual's section 6, "A tour of
the Scenario Editor", under **Environment**.

The models themselves are Basilisk's: gravity, drag, solar radiation
pressure, third bodies and the rest. The transparency audit's Appendix A
lists their settings and constants; SpaceMissionStudio's own calculations
use one set of physical constants, Basilisk's ([Physical constants](constants.md)).

## Integration

The scenario chooses the integrator (`sim_settings.integrator`) and the
dynamics step (`sim_settings.dynamics_task_rate_s`). These are Basilisk's
integrators:
- **Euler and RK2** take one fixed step per dynamics step.
- **RKF45 and RKF78** are adaptive. They split a dynamics step until the
  estimated error of every state is within

      absolute + relative * |state|

  with `integrator_relative_tolerance` (1e-10) and
  `integrator_absolute_tolerance` (1e-8, in the state's own unit: m, m/s,
  rad, ...).

Why 1e-10: Basilisk's own default relative tolerance, 1e-4, lets a long
step pass unsplit. A one-day two-body run at a 300 s step was 384 m off
Kepler's solution with it, and is 11 m off at 1e-10 (audit E3). Steps of
30 s or less, which every template uses, met the default in one step
already; their results are the same either way.

The run's `provenance.json` records the tolerances it used
(`integrator_relative_tolerance`, `integrator_absolute_tolerance`).

## Re-entry

A run with drag is executed in chunks, and between chunks each
spacecraft's altitude is checked:
- every `reentry_check_s` (6 h) while every perigee is high;
- every `reentry_near_check_s` (300 s) once a perigee is below
  `reentry_near_perigee_km` (200 km).

When a spacecraft is below `reentry_altitude_km` (100 km), the run stops
there and says so; the re-entry time is known to within one check.
Integrating on through the atmosphere would give non-physical results and
could lose the whole run. The chunks do not change the trajectory:
Basilisk integrates the same steps either way.

This is the run's criterion, on the simulated altitude. The lifetime
estimate's is different: the orbit-averaged perigee reaching
`lifetime.reentry_altitude_km` (120 km), from where an orbit lasts days at
most ([Physical constants](constants.md), "The re-entry altitudes").

## Shadows: `shadowing_bodies`

Which bodies shadow a spacecraft from the Sun, and so its sunlight
(`<spacecraft>.eclipse.illumination_factor`): the eclipse events, the
solar panels, solar radiation pressure, the sun and thermal sensors and
the eclipse-gated thrusters all read it. `dynamics.shadowing_bodies`
chooses, by name ([Selectable models](README.md#selectable-models)):

```yaml
parameters:
  dynamics.shadowing_bodies: tracked_bodies   # [-] or central_body (default)
```

- **The central body** (`central_body`, default): one Basilisk eclipse
  module with the central body, as before the choice existed. In a
  heliocentric run that one module has every tracked body but the Sun,
  and takes the shadow of the one nearest the spacecraft. So no other
  body shadows an Earth orbiter: no lunar eclipse. Checked against
  `tests/test_shadows.py` (a spacecraft in the Moon's umbra is lit).
- **Every tracked body** (`tracked_bodies`): the central body's module,
  and one more eclipse module for each other tracked body but the Sun,
  each with that one body. One module with several bodies would take only
  the nearest one's shadow: around the Earth, always the Earth's. A
  spacecraft's sunlight is the product of the fractions each body leaves.
  Checked against `tests/test_shadows.py` (a spacecraft 20 000 km behind
  the Moon, away from the Sun, is in its umbra throughout: sunlight 0).

Assumptions of both: the bodies are spheres of their equatorial radius,
with a conical umbra and penumbra and the Sun's disk overlap for partial
shadow (Basilisk's eclipse module, `src/simulation/environment/eclipse`).
Of every tracked body:

- Two bodies shading the Sun at once are combined as independent: the
  product of their fractions. It is exact whenever no more than one body
  shades.
- A tracked body whose radius Basilisk's eclipse does not know by name (a
  small body other than the central one) cannot shadow; the run warns.
  The bodies it knows: Mercury, Venus, the Earth, the Moon, Mars (and its
  barycenter), Jupiter's barycenter, Saturn, Uranus, Neptune.
- Each extra body adds one Basilisk module, and one Python module per
  spacecraft: a slower run.

A run with every tracked body records `models` in its provenance: the
model, its method and references, the bodies that shadow, and those that
cannot. A run with the default records none, as before.

## The conservation check

A spacecraft whose run is two-body only has these properties exactly
conserved:
- no perturbation;
- no thrust;
- a point-mass central body.

The check takes its specific orbital energy and angular momentum at each
sample. When either drifts from its first value by more than
`conservation_tolerance` (1 %), the run warns. That flags a numerical
blow-up, such as too long a step; it is not a grade of the integrator's
accuracy, which is far finer.

## Rules and parameters

Each is a named parameter, `dynamics.<name>`.
`spacemissionstudio assumptions --area dynamics` lists the values in
effect, and a project configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `integrator_relative_tolerance` | 1e-10 | [-] | The adaptive integrators' relative tolerance | SpaceMissionStudio's own choice (audit E3) |
| `integrator_absolute_tolerance` | 1e-8 | [m, m/s, rad] | Their absolute tolerance, one value for every state | Basilisk's default |
| `reentry_altitude_km` | 100 | [km] | The altitude below which a run counts a spacecraft as re-entered | SpaceMissionStudio's own choice |
| `shadowing_bodies` | `central_body` | [-] | The bodies that shadow a spacecraft from the Sun (above) | SpaceMissionStudio's own choice |
| `reentry_check_s` | 21 600 | [s] | The re-entry check's interval while perigees are high | SpaceMissionStudio's own choice |
| `reentry_near_perigee_km` | 200 | [km] | The perigee below which the checks come often | SpaceMissionStudio's own choice |
| `reentry_near_check_s` | 300 | [s] | The re-entry check's interval near re-entry: the precision of the re-entry time | SpaceMissionStudio's own choice |
| `conservation_tolerance` | 0.01 | [-] | The energy and momentum drift a two-body run warns at | SpaceMissionStudio's own choice |

**Not parameters:**
- **The physical constants** ([Physical constants](constants.md)).
- **The segment length of runs over 100 days** (90 days): Basilisk's
  clock holds about 104 days, and segments only need to fit in it.
- **The order of the modules within a step:** fixed by what each module
  reads.

## Assumptions

- One absolute tolerance for every state, whatever its unit.
- Re-entry is judged from the geocentric altitude above the central
  body's equatorial radius.

## Checked against

- `tests/test_two_body_validation.py`: a one-day run at a 300 s step
  within 50 m of Kepler's solution, and the tolerances in its provenance.
- `tests/test_config.py`: each parameter changes what it controls.
