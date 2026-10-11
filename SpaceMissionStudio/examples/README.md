# Python examples

Short scripts that use SpaceMissionStudio from Python, without the GUI.
Each shows one part of the tool and prints what it found. Every script
is run by `tests/test_examples.py`, so they keep working.

Run them from the `SpaceMissionStudio` folder, with the environment you
installed SpaceMissionStudio into active (see
[Getting started](../docs/getting-started.md)). Each one takes `--help`.
The times below were measured in a clean install on a 4-core Linux
machine; allow more on a slower one.

| Script | Shows | Needs Basilisk | Takes about |
|---|---|---|---|
| [`build_a_scenario.py`](build_a_scenario.py) | Building a scenario from the schema's dataclasses: an orbit, a spacecraft, a ground station. It validates the scenario, saves it as JSON for the GUI or CLI, and prints the Explain tab's summary. | no | 1 s |
| [`run_a_template.py`](run_a_template.py) | Running any bundled template (or your own file) and reading its results: time series, events (passes, eclipses), CSV export. | yes | 5 to 10 s |
| [`hohmann_transfer.py`](hohmann_transfer.py) | A Mission Sequence in code: burn, coast until apoapsis, burn again. The result is checked against the textbook Hohmann transfer. | yes | 5 s |
| [`altitude_lifetime_sweep.py`](altitude_lifetime_sweep.py) | A parameter sweep: orbital lifetime at several altitudes, with real solar activity, checked against the 5-year disposal rule. | yes | under a minute |
| [`monte_carlo_spread.py`](monte_carlo_spread.py) | Running template 25's Monte Carlo batch and reading its summary back: the spread along, across and out of the orbit, day by day (the GUI's Monte Carlo tab shows the same). | yes | about 2 minutes |

```bash
python3 examples/build_a_scenario.py my_first_mission.json
spacemissionstudio run my_first_mission.json --out-dir out    # or open it in the GUI
python3 examples/run_a_template.py 23
python3 examples/hohmann_transfer.py --from-km 550 --to-km 700
python3 examples/altitude_lifetime_sweep.py --altitudes 400,450,500,550
python3 examples/monte_carlo_spread.py --runs 20 --archive mc_out
```

## What you should see

Every script first prints an `INFO ... Logging to ...` line; that is
normal. The scripts that run Basilisk also print a note that the space
weather uses NASA MSFC's prediction (the templates are set in 2030).

**`build_a_scenario.py my_first_mission.json`** prints the Explain
summary and saves the file:

```text
My first mission
  Spacecraft: 1
  Duration: 24 h
  Gravity: Degree-10 Earth + Sun/Moon
  Orbit: SSO 97.59 deg, 550 km alt
  ...
  Ground stations: berlin-gs
    berlin-gs: 4 passes, first at 10 min for 8 min (peak 60 deg)
Saved my_first_mission.json
```

**`run_a_template.py 22`** prints each series' first and last value, then
the events, ending with:

```text
event: pass over berlin-gs (my-sat) 10.5-18.0 min
event: eclipse (umbra) (my-sat) 24.0-58.5 min
...
my-sat: distance from Earth's centre 6920.4-6928.5 km
```

With `23` it also prints the Mission Sequence's two reports:
`report 'Pass start' at 10.4 min` and `report 'Pass end' at 18.2 min`.

**`hohmann_transfer.py --from-km 550 --to-km 700`**:

```text
Textbook: burns of 40.51 and 40.29 m/s, 48.6 min apart
 At apoapsis: t =   48.7 min, altitude 700.0 km
         End: t =  147.3 min, altitude 700.0 km
Final orbit: altitude 699.69 to 700.31 km (target 700 km)
```

**`altitude_lifetime_sweep.py --altitudes 400,450,500,550`**:

```text
 altitude      lifetime  within 5 years?
   400 km       2.65 yr  yes
   450 km       4.37 yr  yes
   500 km       6.83 yr  no
   550 km      17.26 yr  no
```

**`monte_carlo_spread.py --runs 20 --archive mc_out`** (the values are
drawn at random, so your numbers may differ a little):

```text
20 runs; drag coefficients drawn between 2.22 and 2.98
day  1.00: 1-sigma   150.2 km along track,  1.03 km radial,  0.70 km cross-track
day  2.00: 1-sigma   298.7 km along track,  1.32 km radial,  1.38 km cross-track
day  3.00: 1-sigma   448.0 km along track,  0.78 km radial,  2.00 km cross-track
```

## Where things live

All five use the same few entry points:

| You want to | Use |
|---|---|
| Describe a mission | `spacemissionstudio.schema.scenario`: `Scenario`, `SpacecraftConfig`, `OrbitIC`, `GroundStationConfig` and friends. |
| Read or write a scenario file | `spacemissionstudio.schema.load_scenario(path)`, `Scenario.save(path)`, `Scenario.validate()` |
| Plan an orbit | `spacemissionstudio.engine.orbit_design`: Sun-synchronous inclination, RAAN for a local time, GEO elements |
| Run it | `spacemissionstudio.engine.service.SimulationService(scenario).run()`. With a Mission Sequence: `engine.mission_engine.MissionEngine(scenario, service=...).run()` |
| Read results | `ResultSet.series[name]`, a `TimeSeries` with `time_s`, `data`, `columns`, `units`; `ResultSet.export_csv(folder)` |
| List events | `spacemissionstudio.engine.events.extract_events(result)` |
| Summarize a scenario | `spacemissionstudio.engine.scenario_explainer.explain(scenario)` (the Explain tab) |
| Estimate lifetime | `spacemissionstudio.engine.lifetime.spacecraft_lifetime(scenario, name)` (the End of Life tab) |
| Monte Carlo | `spacemissionstudio.engine.monte_carlo.run_monte_carlo(scenario, scenario.monte_carlo, folder)`; read the results with `spacemissionstudio.engine.monte_carlo_results.load(folder)` |

Series names follow `<spacecraft>.<quantity>` (`my-sat.position_N`) or
`<station>.access_to_<spacecraft>.<quantity>`; the Results tab's
**Series** list shows the same names. Positions are in metres, in the
inertial frame (`_N`), and times are seconds since the scenario's epoch.

---

**Next:** [Use the command line](../docs/user-manual/command-line.md) ·
[Template catalog](../spacemissionstudio/scenarios/templates/README.md) ·
[Documentation index](../docs/README.md)
