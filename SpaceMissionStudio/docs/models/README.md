# Models, rules and assumptions

One page per model: what it computes and how, every rule and margin it
applies with its value, unit and source, the assumptions it makes, and
what it does not cover. Each rule is a named parameter: `spacemissionstudio
assumptions` lists them with the values in effect, and a project
configuration file changes them without editing code
([Change a parameter](../user-manual/project-configuration.md)).

| Model | Page | Parameters |
|---|---|---|
| Delta-V and propellant budget (ESA AD10) | [Propellant budget](propellant-budget.md) | `propellant_budget.*` |
| Orbital lifetime, disposal rules and drag make-up | [Orbital lifetime](lifetime.md) | `lifetime.*` |
| RF link budget, onboard data and power | [RF link, data handling and power](link-data-and-power.md) | `link.*`, `data_handling.*`, `power.*` |
| A run's figures, events, critical marks and dashboard badges | [Reading a run's results](reading-results.md) | `results.*` |
| The integrator's tolerances, the re-entry checks, the conservation check | [Dynamics: integration and run control](dynamics-run-control.md) | `dynamics.*` |
| The atmosphere models and tables, space weather past the prediction, Earth orientation, TLEs, mean elements | [Environment data](environment-and-data.md) | `space_weather.*`, `tle.*` |
| Altitude station keeping, the thruster's firing model, phasing keeping, GEO station keeping | [Orbit control](orbit-control.md) | `orbit_control.*`, `geo_station_keeping.*` |
| ROE formation guidance: decisions, drifts, eclipse retries, differential drag | [ROE formation guidance](roe-formation.md) | `roe_formation.*` |
| The attitude thrusters' Schmitt trigger, optical and landmark navigation's filters | [Flight software and navigation](flight-software-and-navigation.md) | `flight_software.*`, `navigation.*` |
| The pre-run checks: pass prediction, recording, step, late pass, sun sensor | [Pre-run checks](pre-run-checks.md) | `checks.*` |
| Explain's labels and notes; the mission sequence's numerical settings | [Explain and the mission sequence](explain.md) | `explain.*` |
| A Monte Carlo batch's offsets and the statistic of its spread | [Monte Carlo statistics](monte-carlo-statistics.md) | `monte_carlo.*` |
| Analyses built on the 3D model: fields of view, thrusters, mass budget, launcher, disturbance torques, blinding, shading, exposure, brightness | [Analyses built on the 3D model](model-analyses.md) | `analyses.*` |
| The preliminary re-entry casualty estimate: break-up, demise, casualty area, risk | [Preliminary re-entry casualty estimate](reentry.md) | `reentry.*` |
| The scenario file's limits: run length, step, counts, sizes, names | [The scenario file's limits](scenario-limits.md) | none (constants) |
| Computed and overridden values: what is marked, its status, where it is recorded | [Computed and overridden values](value-marks.md) | none |

**How a number was computed:** the propellant budget's, the orbital
lifetime's and the link budget's numbers, a run's headline figures and
its events carry their calculation trace:
the equation, the inputs with their units and sources, and the standard's
clause. The command line prints them (`budget --explain`, `lifetime
--explain`, `link-budget --explain`, `run --explain` for the run's
headline figures); in the app, **Show calculation** on the Budget and End
of Life pages, the Dashboard's link and the Timeline, and a card of
Results › Overview, open them in the Calculation panel ("How each ... was computed" on
[Reading a run's results](reading-results.md),
[Propellant budget](propellant-budget.md),
[Orbital lifetime](lifetime.md) and
[RF link, data handling and power](link-data-and-power.md)). The other
models follow (the transparency plan, Phase 4).

Every calculation uses one set of physical constants, Basilisk's:
[Physical constants](constants.md). The values each model uses that are
neither parameters nor constants are named on its page; the
[transparency audit](../transparency_audit.md), Section 4, lists them all
with file and line.

## Selectable models

Where an analysis can be done more than one way, each way is a model,
declared once in `spacemissionstudio/config/models.py` with:

- its **name** (the value that selects it) and **title**;
- its **method**: what it computes and how, with the formula;
- its **inputs** and **outputs**;
- its **assumptions**;
- its **references**;
- its **evidence**: the tests that check it, which a test confirms exist.

A choice between models is a parameter like the others (its kind is
"model"): a project configuration file sets it by the model's name, the
Assumptions page and `spacemissionstudio assumptions` list it, and a name
that is not one of its models is refused when the file is read. The
default is the model the tool used before the choice existed, so no
result changes until a project chooses another. The model in effect is
recorded with the results it gives and named where they are shown.

| Choice | Models | Page |
|---|---|---|
| `monte_carlo.spread_statistic` | `population` (default), `sample` | [Monte Carlo statistics](monte-carlo-statistics.md) |
| `propellant_budget.margin_policy` | `ad10_equations` (default), `ad10_summary_table` | [Propellant budget](propellant-budget.md#the-margin-policy-margin_policy) |
| `dynamics.shadowing_bodies` | `central_body` (default), `tracked_bodies` | [Dynamics: integration and run control](dynamics-run-control.md#shadows-shadowing_bodies) |
| `link.atmospheric_loss` | `none` (default), `itu_r_p676` | [RF link, data handling and power](link-data-and-power.md#the-atmospheric-gases-atmospheric_loss) |
| `power.degradation` | `none` (default), `yearly_rate`, `radiation_dose` | [RF link, data handling and power](link-data-and-power.md#solar-array-degradation-degradation) |

The atmosphere is chosen in the scenario itself
(`space_weather.atmosphere_model`: `nrlmsise00`, `exponential` or
`tabular`, the tabular's profile in `space_weather.atmosphere_table`), as
it was before the registry: it is part of what the scenario describes,
and saved with it ([Environment data](environment-and-data.md#the-atmosphere)).

A model may also set other parameters: a margin policy is the set of
margins it gives. A value the project file sets itself replaces the
model's, and the records say which values a model set.

The re-entry criterion and the debris rules the plan names are
parameters already, each with its own criterion: the lifetime's
`lifetime.reentry_altitude_km` (120 km, on the orbit-averaged perigee)
and a run's `dynamics.reentry_altitude_km` (100 km, on the simulated
altitude); every lifetime is checked against both disposal rules,
`lifetime.zero_debris_years` (5) and `lifetime.iadc_years` (25). A choice
of model would add nothing a project file cannot already set.

### Models of your own (plugins)

A plugin, a Python package installed next to SpaceMissionStudio, can add
models to `link.atmospheric_loss`, `power.degradation` and
`propellant_budget.margin_policy`, with the same declaration as the
models above, and parameters and pre-run rules of its own. Each run
records the plugins loaded and names a plugin's model with its plugin.
A plugin cannot add what Basilisk simulates (a sensor, an actuator, a
flight-software mode, an atmosphere or shadow model). A plugin's models
are documented by its own package, not here:
[Add your own models and rules](../user-manual/plugins.md).

## Not yet covered

A check of the audit's Section 4 against the registry (2026-10-30) found
models with rules still in the code and no page here; the last of them,
the Monte Carlo statistics, has its page now. The audit's Appendix B,
Sections 1.3 to 1.8, and Appendix A, Sections 1h and 1i, list the values
with file and line.

Numerical settings that set no result are not parameters: download
limits, timeouts, task priorities, iteration caps, plotting limits. The
audit's tables mark them "own" or "Internal".
