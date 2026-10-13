# Architecture

How SpaceMissionStudio's code is organised, in one page. The full design
is in the Software Design Document,
[`compliance/docs/SDD.md`](../../compliance/docs/SDD.md), and every module
is listed in
[`compliance/docs/SDD_components.md`](../../compliance/docs/SDD_components.md)
(generated, so it is always complete).

## Layers

The tool is one Python package, `spacemissionstudio`, in three layers.
Each layer uses only the layers below it.

```
   gui/ (PySide6 windows)        cli.py (headless commands)
            \                        /
             v                      v
   engine/  simulation service, analyses, data and exchange
            (imports Basilisk only where a simulation is built)
             |
             v
   schema/  the scenario data model and its validation
   data/    bundled data files (space weather, device catalog)
```

| Package | What it holds | Needs Basilisk |
|---|---|---|
| `schema/` | The scenario model (`Scenario`, `SpacecraftConfig`, `OrbitIC`, ...) as dataclasses, its validation, file migrations, the Mission Sequence commands and reference checks | No |
| `engine/` | `service.SimulationService` builds and runs a Basilisk simulation; `long_run` chains runs past 100 days; `mission_engine` runs a Mission Sequence; analyses (lifetime, budgets, Monte Carlo, link budget, formations, constellations); data and exchange (space weather, Earth orientation, kernels, CCSDS, TLE, results, events) | Only the modules that build a simulation, and they import it inside functions |
| `gui/` | The PySide6 application: editors, the Results and analysis tabs, the workers that run things in the background | No (it opens without Basilisk; runs need it) |
| `cli.py` | The `spacemissionstudio` command, over the same `engine` calls as the GUI | Only for commands that run something |
| `fsw_export/` | Exports a spacecraft's attitude flight software as a standalone C project | Only to record a run |
| `sil/` | Software in the loop: the transport contract, the session, the runner, the comparison report | Only to run |

Nothing is duplicated between the GUI and the CLI: both call `schema` and
`engine`.

## What a run does

1. The scenario JSON file is read and validated
   (`schema.load_scenario`, `Scenario.validate`). An invalid field raises
   `ScenarioValidationError`, naming it, before anything is built.
2. `SimulationService` builds one Basilisk simulation: one process, one
   task at the scenario's dynamics step, with SPICE, the environment
   models, the spacecraft, its flight software and recorders.
3. The simulation runs in chunks (`run_live`). After each chunk the GUI
   updates the live plot and checks for **Cancel Run**, so a cancel takes
   effect at the next chunk and keeps the results so far.
4. The recorded messages become a `ResultSet` of `TimeSeries`
   (`engine/results.py`), plus events and warnings.
5. The CLI writes them as CSV files with `provenance.json`; the GUI shows
   them in the Results, Events and other tabs.

Runs longer than about 100 days are split into segments, each a fresh
simulation started from the previous one's final state, because
Basilisk's 64-bit nanosecond clock limits one simulation to about 104
days (`engine/long_run.py`).

## Threads and processes

- The GUI thread handles only the interface. Every long operation (a run,
  a Monte Carlo batch, a download) runs in its own worker thread and
  reports through Qt signals.
- A Monte Carlo batch with more than one thread uses a process pool; each
  run is contained in its own process.
- Vizard is a separate program, fed by a save file or a live stream.

## Where things live

| You want | Look in |
|---|---|
| A scenario field and its meaning | `schema/scenario.py` (each field's comment), and the generated field list [`compliance/docs/ICD_scenario_fields.md`](../../compliance/docs/ICD_scenario_fields.md) |
| How a feature maps to Basilisk modules | `engine/service.py` and `engine/fsw.py` |
| The CLI's commands and exit codes | `cli.py`, and [`compliance/docs/ICD_cli.md`](../../compliance/docs/ICD_cli.md) |
| Every external interface | [`compliance/docs/ICD.md`](../../compliance/docs/ICD.md) |
| Why something is the way it is | [`HISTORY.md`](../../HISTORY.md), the development log |
| What is required, and how it is verified | [`compliance/docs/SRS.md`](../../compliance/docs/SRS.md), [`compliance/docs/SVS.md`](../../compliance/docs/SVS.md) |

## Design rules

- **Basilisk is used, never changed.** Every capability maps to a
  Basilisk module or is the tool's own code, said to be so.
- **Validation before building.** Errors name the field and happen before
  anything runs.
- **Results are never invented.** A data file that does not cover the run
  is refused, not extrapolated.
- **No network without asking.** See the [FAQ](../faq.md#does-it-need-the-internet).

---

**Next:** [Developer guide](README.md) · [Releasing](releasing.md) ·
[Software Design Document](../../compliance/docs/SDD.md)
