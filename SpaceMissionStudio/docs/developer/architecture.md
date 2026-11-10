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
   config/  named parameters, selectable models, project configuration files
   data/    bundled data files (space weather)
```

`model3d/`, `analyses/`, `idm/`, the IDM-CIC mapping modules and
`ccsds_files.py` sit beside `engine/`, at its level: the GUI and the CLI
both call them, and they use `schema/`, `config/` and parts of `engine/`
(results, findings, the device catalogue, the CCSDS messages). The package also
ships the templates (`scenarios/templates/`) and the copy of the User
Manual the app shows (`help/`).

| Package | What it holds | Needs Basilisk |
|---|---|---|
| `schema/` | The scenario model (`Scenario`, `SpacecraftConfig`, `OrbitIC`, ...) as dataclasses, its validation, file migrations, the Mission Sequence commands and reference checks, and what the file can hold at each place for the JSON page's completion and help (`fields.py`, with each field's help generated into `field_help.json` by `scripts/build_field_help.py`) | No |
| `engine/` | `service.SimulationService` builds and runs a Basilisk simulation; `long_run` chains runs past 100 days; `mission_engine` runs a Mission Sequence; analyses (lifetime, budgets, Monte Carlo, link budget, formations, constellations); data and exchange (space weather, Earth orientation, kernels, CCSDS, TLE, results, events) | Only the modules that build a simulation, and they import it inside functions |
| `gui/` | The PySide6 application: the shell (navigation rail, areas, top bar, status bar, command registry), the theme package (`gui/theme/`), the editors (the JSON page's code editor among them: `code_editor.py`, `json_positions.py`, `json_assist.py`, `json_refactor.py`; design: [The JSON page as a code editor](json-editor.md)), the Run, Results, Timeline and Reports views, the workers that run things in the background | No (it opens without Basilisk; runs need it) |
| `config/` | The registry of named parameters (value, unit, source, limits: `registry.py`, `parameters.py`), the selectable models (`models.py`), and the YAML project configuration files a scenario names in `config_file` (`files.py`; `defaults.yaml` is generated) | No |
| `cli.py` | The `spacemissionstudio` command, over the same `engine` calls as the GUI | Only for commands that run something |
| `api.py` | The stable Python API for scripts (`load`, `validate`, `run`, `lifetime`, `budget`, `compare`, ...; reference in [`docs/api.md`](../api.md)), over the same `engine` calls | Only for the functions that run something |
| `network.py` | The only way the tool reaches the network: each download a purpose with its only hosts, the offline policy (the user's, an administrator's), the guard on all Python network use that the CLI and GUI turn on, and the network log ([Network use and offline mode](../reference/network.md)). A test fails if another module imports a networking library | No |
| `plugins.py`, `history.py`, `reproduction.py`, `output_provenance.py` | Plugins found by entry point (`spacemissionstudio.models`); a scenario's change history in a `.history.jsonl` file beside it; reproduction bundles (a run's folder that can run itself again); provenance inside output files | No |
| `dependencies.py`, `constants.py`, `logging_setup.py`, `temp_folders.py`, `_offline.py` | The qualified Basilisk version and its check; the physical constants the tool's own calculations use; logging to the terminal and `~/.spacemissionstudio/logs/`; the temporary folders and their clean-up; keeping Basilisk's import-time request off the network | No |
| `fsw_export/` | Exports a spacecraft's attitude flight software as a standalone C project | Only to record a run |
| `sil/` | Software in the loop: the transport contract, the session, the runner, the comparison report | Only to run |
| `model3d/` | 3D spacecraft models: shapes and `.obj` files, mass properties (and reading them from a file: `mass_import.py`), surface facets, mounted equipment, the stowed configuration, ray casting (`raycast.py`), moving the body frame's origin (`origin.py`), and applying them to a spacecraft | No (numpy only) |
| `analyses/` | Analyses built on the 3D model: the design checks (fields of view, thrusters and plumes, mass budget, launcher envelope), a run's model analyses (disturbance budget, blinding, obstruction, shading, exposure, brightness), the preliminary re-entry estimate, and their records and tables | Only for the device defaults (thrusters, wheels) and the atmosphere table, imported inside functions |
| `idm/` | Reading IDM-CIC models (`.idm` files; IDM-CIC is © CNES) with the tool's own code: the archive, its values, objects, frames and shapes, the power modes (`power.py`) and a team's properties (`properties.py`); it knows nothing of scenarios | No |
| `idm_import.py`, `idm_devices.py`, `idm_properties.py` | Mapping an IDM-CIC model into a spacecraft: the 3D model, mass properties, stowed poses, the power budget and the body frame's origin, re-imports that keep your edits (`idm_import.py`); the sensors and actuators found by name, with their axes, and the thrusters added to the 3D model from their plume cones (`idm_devices.py`); device and battery values from a team's properties (`idm_properties.py`). Design: [IDM-CIC import](idm-cic-integration.md) | No |
| `ccsds_files.py` | CCSDS orbit data message files for a scenario (validate, export, import, a run's OEM), shared by the CLI and the GUI; the messages themselves are `engine/ccsds_odm.py`'s | Only to export an OPM, imported inside a function |
| `plot_categories.py` | How each named result series is shown: title, axis label, unit, column names, display-only unit conversion | No |

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
   them in the Results, Timeline and other areas.

Runs longer than about 100 days are split into segments, each a fresh
simulation started from the previous one's final state, because
Basilisk's 64-bit nanosecond clock limits one simulation to about 104
days (`engine/long_run.py`).

## Threads and processes

- The GUI thread handles only the interface. Every long operation (a run,
  a Monte Carlo batch, a download) runs in its own worker thread and
  reports through Qt signals.
- In the app, a Monte Carlo batch runs in a child process
  (`gui/monte_carlo_process.py`), because Basilisk's controller must run
  on a process's main thread; with more than one thread it uses a process
  pool from there, each run in its own process. The start-up reading of
  the reference data also runs in a child process
  (`gui/reference_data_process.py`), so the window does not stall.

## Where things live

| You want | Look in |
|---|---|
| A scenario field and its meaning | `schema/scenario.py` (each field's comment; after changing one, run `scripts/build_field_help.py` so the JSON page's help follows), and the generated field list [`compliance/docs/ICD_scenario_fields.md`](../../compliance/docs/ICD_scenario_fields.md) |
| How a feature maps to Basilisk modules | `engine/service.py` and `engine/fsw.py` |
| An engineering value an analysis uses (its unit, source and default) | `config/parameters.py`, and the generated `config/defaults.yaml` |
| Scripting the tool from Python | `api.py` and [`docs/api.md`](../api.md) |
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
