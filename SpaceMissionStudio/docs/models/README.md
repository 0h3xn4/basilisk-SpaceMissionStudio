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

Every calculation uses one set of physical constants, Basilisk's:
[Physical constants](constants.md). The values each model uses that are
neither parameters nor constants are named on its page; the
[transparency audit](../transparency_audit.md), Section 4, lists them all
with file and line. Until then their values are
listed, with file and line, in the
[transparency audit](../transparency_audit.md), Section 4.
