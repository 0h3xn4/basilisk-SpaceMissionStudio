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
| RF link budget, onboard data and power | [RF link, data handling and power](link-data-and-power.md) | `link.*`, `data_handling.*` |
| A run's figures, events, critical marks and dashboard badges | [Reading a run's results](reading-results.md) | `results.*` |
| The integrator's tolerances, the re-entry checks, the conservation check | [Dynamics: integration and run control](dynamics-run-control.md) | `dynamics.*` |
| Space weather past the prediction, Earth orientation, TLEs, mean elements | [Environment data](environment-and-data.md) | `space_weather.*`, `tle.*` |
| Altitude station keeping, the thruster's firing model, phasing keeping, GEO station keeping | [Orbit control](orbit-control.md) | `orbit_control.*`, `geo_station_keeping.*` |
| ROE formation guidance: decisions, drifts, eclipse retries, differential drag | [ROE formation guidance](roe-formation.md) | `roe_formation.*` |
| The attitude thrusters' Schmitt trigger, optical and landmark navigation's filters | [Flight software and navigation](flight-software-and-navigation.md) | `flight_software.*`, `navigation.*` |
| The pre-run checks: pass prediction, recording, step, late pass, sun sensor | [Pre-run checks](pre-run-checks.md) | `checks.*` |
| Explain's labels and notes; the mission sequence's numerical settings | [Explain and the mission sequence](explain.md) | `explain.*` |

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

## Not yet covered

A check of the audit's Section 4 against the registry (2026-10-30) found
these models with rules that are still values in the code, and no page
here yet. Until each has its page, its values are listed with file and
line in the audit's Appendix B, Sections 1.3 to 1.8, and Appendix A,
Sections 1h and 1i.

| Models | Rules still in the code (examples) | To be done |
|---|---|---|
| Monte Carlo statistics | the 1-sigma spread uses the population standard deviation | Phase 6b (a choice of statistic) |

Numerical settings that set no result are not parameters: download
limits, timeouts, task priorities, iteration caps, plotting limits. The
audit's tables mark them "own" or "Internal".
