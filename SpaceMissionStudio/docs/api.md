# The Python API

`spacemissionstudio.api` is the stable way to script SpaceMissionStudio:
load and check a scenario, run it, and compute what the app computes from
it. It uses the same engine as the app and the command line, so a number
from a script is the number the app shows.

The examples below are run by the tests (`tests/test_api.py`) exactly as
written, so they work with this version.

## Stability

`API_VERSION` is 1. Every name in `api.__all__` keeps its name, arguments
and meaning within an API version; a change that breaks a script raises
the version and is listed in the changelog. The objects the functions
return are the engine's own (`Scenario`, `ResultSet`, `EndOfLife`,
`Budget`, ...): their documented fields are part of the API, the ones
whose names start with `_` are not.

Without Basilisk, `template`, `load`, `validate`, `assumptions` and
`compare` work; the others need it.

## The functions

| Function | Returns | Does |
|---|---|---|
| `template(name)` | `Path` | A shipped template's file, by name |
| `load(path)` | `Scenario` | Reads and validates a scenario file, with its project configuration file |
| `validate(scenario)` | warnings | The pre-run checks (each a `Finding` with its `rule_id`); raises `ScenarioValidationError` when the scenario cannot run |
| `assumptions(scenario=None)` | `{name: value}` | Every named parameter with the value in effect |
| `run(scenario, out_dir=None)` | `ResultSet` | Runs it (its Mission Sequence when it has one); with `out_dir`, writes the CSVs and `provenance.json` |
| `summary(result)` | `[Figure]` | The headline figures (Results > Overview), each with its `trace` |
| `lifetime(scenario, spacecraft=None, result=None, **options)` | `EndOfLife` | The orbital lifetime (End of Life); from the end of `result` when given |
| `budget(scenario, spacecraft=None, result=None)` | `Budget` | The delta-V and propellant budget (ESA AD10) |
| `launch_delays(scenario, spacecraft=None, result=None)` | `LaunchDelaySweep` | The budget for launches up to five years late |
| `altitude_trade(scenario, spacecraft=None, altitudes_km=None, result=None)` | `AltitudeTrade` | The sweep at each altitude, against the tank |
| `monte_carlo(scenario, archive_dir)` | `MonteCarloBatch` | The scenario's Monte Carlo batch, archived with its provenance |
| `compare(a_scenario, a_result, b_scenario, b_result)` | `Comparison` | Two runs side by side (Results > Compare) |
| `record(scenario, analysis, ...)` | `dict` | A lifetime's, budget's, sweep's or trade's JSON record, as `--out` writes it |
| `write(path, data)` | `Path` | Writes a record as JSON |

## Load, check and run

```python
from spacemissionstudio import api

scenario = api.load(api.template("22_starter_first_leo_satellite"))
for warning in api.validate(scenario):
    print(warning.rule_id, warning)

scenario.sim_settings.duration_days = 0.05  # [day] a short run for the example
result = api.run(scenario, out_dir="starter_results")
for figure in api.summary(result):
    print(f"{figure.label}: {figure.text()} {figure.unit}")
print(result.provenance.scenario_sha256)
```

`out_dir` holds one CSV per series (SI units, elapsed TDB seconds since
the epoch) and `provenance.json`, as `spacemissionstudio run --out-dir`
writes them.

## Change an assumption

A project configuration file sets the parameters
([Change a parameter](user-manual/project-configuration.md)); a script can
read the values in effect:

```python
from spacemissionstudio import api

values = api.assumptions(api.load(api.template("22_starter_first_leo_satellite")))
print(values["lifetime.zero_debris_years"], values["propellant_budget.residual_fraction"])
```

## Analyses and their records

```python
from spacemissionstudio import api

scenario = api.load(api.template("22_starter_first_leo_satellite"))
scenario.space_weather.atmosphere_model = "exponential"  # fast for the example; the default is NRLMSISE-00
end = api.lifetime(scenario, max_years=5.0)
print(end.lifetime.reentered, end.lifetime.lifetime_years)
trace = end.traces["lifetime"]
print(trace.equation, [(q.name, q.value, q.unit, q.source) for q in trace.inputs])
api.write("lifetime.json", api.record(scenario, end))
```

The record holds the inputs, the model and its rules, the results with
how each was computed, the decay curve, the warnings and the provenance:
the same file `spacemissionstudio lifetime --out` writes.

## Compare two runs

```python
from spacemissionstudio import api

scenario = api.load(api.template("22_starter_first_leo_satellite"))
scenario.sim_settings.duration_days = 0.02  # [day]
first = api.run(scenario)
heavier = api.load(api.template("22_starter_first_leo_satellite"))
heavier.sim_settings.duration_days = 0.02  # [day]
heavier.spacecraft[0].dry_mass_kg += 10.0  # [kg]
second = api.run(heavier)
comparison = api.compare(scenario, first, heavier, second)
for path, a, b in comparison.scenario:
    print(path, a, "->", b)
api.write("comparison.json", comparison.to_dict())
```

The command line does the same for runs kept in the run store:
`spacemissionstudio run scenario.json --save`, `spacemissionstudio runs`,
`spacemissionstudio compare 1 2 --out comparison.json`.

---

**See also:** [Use the command line](user-manual/command-line.md) ·
[Documentation index](README.md)
