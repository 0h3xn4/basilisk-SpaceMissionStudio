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

**How a number was computed:** the propellant budget's, the orbital
lifetime's and the link budget's numbers, and a run's headline figures,
carry their calculation trace:
the equation, the inputs with their units and sources, and the standard's
clause. The command line prints them (`budget --explain`, `lifetime
--explain`, `link-budget --explain`, `run --explain` for the run's
headline figures); in the app, **Show calculation** on the Budget and End
of Life pages and the Dashboard's link, and a card of Results › Overview,
open them in the Calculation panel ("How each ... was computed" on
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
| ROE formation guidance | about 15 thresholds: the holding check, glide orbits, the direct-correction factor, the drag estimate's minimum span, hold and trigger fractions, eclipse retries | Phase 3a, ROE guidance |
| Flight software and navigation | thruster firing (Schmitt trigger 0.75/0.25, 2 ms); the momentum-dump mapping threshold; the landmark camera's 25 mm focal length; the UKF's alpha, beta, kappa | Phase 3a, flight software |
| Pre-run checks, Explain and the mission sequence | pass-prediction sampling (30 s, 7 days); the coarse-recording, late-pass and CSS-facing rules; Explain's SSO, drag and camera tolerances; Lambert's 1 m/s convergence | Phase 3a, checks (with Phase 5a's structured warnings) |
| Monte Carlo statistics | the 1-sigma spread uses the population standard deviation | Phase 6b (a choice of statistic) |

Numerical settings that set no result are not parameters: download
limits, timeouts, task priorities, iteration caps, plotting limits. The
audit's tables mark them "own" or "Internal".
