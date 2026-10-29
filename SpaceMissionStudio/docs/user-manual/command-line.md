# Use the command line

How to check, run and analyse scenarios without the GUI, for scripts,
batch jobs and CI. Every command uses the same engine as the app.

`spacemissionstudio --help` lists the commands; `spacemissionstudio
<command> --help` shows one command's options; `spacemissionstudio
--version` shows the SpaceMissionStudio, Basilisk and Python versions. A command that fails exits
with a non-zero status and prints `ERROR:` or `INVALID:` with the reason.

## Contents

- [Check and run](#check-and-run)
- [Analyse](#analyse)
- [Build scenarios](#build-scenarios)
- [3D models](#3d-models)
- [Orbit files (CCSDS)](#orbit-files-ccsds)
- [Flight software](#flight-software)
- [Reference data](#reference-data)

## Check and run

| Command | What it does |
|---|---|
| `validate scenario.json` | Checks the file without running it. Does not need Basilisk. |
| `run scenario.json --out-dir out` | Runs it and writes one CSV per quantity, `events.csv`, `provenance.json` and `scenario_as_run.json` |
| `monte-carlo scenario.json --archive-dir mc` | Runs the scenario's Monte Carlo batch and writes its provenance, `archive.provenance.json` |
| `gui` | Starts the app |

```console
$ spacemissionstudio validate spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json
OK: '22 - Starter: your first LEO satellite' -- 1 spacecraft, schema version 4, epoch 2030-01-01T08:30:00
```

Useful `run` options:

| Option | Does |
|---|---|
| `--oem` | Also writes each spacecraft's ephemeris as a CCSDS OEM file |
| `--vizard-save-file run.bin` | Writes a Vizard playback file |
| `--vizard-live-stream` | Streams to a Vizard that is already running |
| `--allow-scripts` | Runs the scenario's `script_block` commands. They are unrestricted Python: use it only for files you trust and have read. |

`scenario_as_run.json` is the scenario exactly as it was run, after an
older file was brought up to date: running it again runs the same
scenario. `provenance.json` names the file you gave and the SHA-256 of
its bytes, the SHA-256 of the scenario as run, every data file used with
its SHA-256, and the run's warnings (`run_warnings`). It also gives the
values used that your file does not give: the engine's defaults for the
keys a device's `params` leave out, with the value applied
(`effective_defaults`), and each wheel's and thruster's values from
Basilisk's catalogue (`device_parameters`).

A file written by an older version is brought up to date as it loads.
`validate` lists each value that changed in a `MIGRATED:` line, and the
run records them (`scenario_file_migrations`):

```console
$ spacemissionstudio validate old.json
OK: 'old' -- 1 spacecraft, schema version 4, epoch 2030-01-01T00:00:00
MIGRATED: schema 1 -> 2: space_weather.source 'celestrak' -> 'synthetic'
MIGRATED: schema 2 -> 3: space_weather.source 'synthetic' -> 'bundled'
```

`archive.provenance.json` in a Monte Carlo folder names the file you gave
and the SHA-256 of its bytes and of the scenario. Under `nominal_run` it
gives what every run shares: the integrator and its tolerances, the time
step, the central body, the frames and every data file with its SHA-256.
It gives no seeds: each run draws its own, and they are in its
`run<N>.json`.

`run` checks that it can write to `--out-dir` before it starts, and stops
with exit code 3 if it cannot. Give each run its own empty folder: if the
folder already holds files this run did not write, `run` names them in a
`WARNING` at the end, because they are not this run's results.

A scenario file is refused (`INVALID:`, exit code 1) if it is larger than
20 MB, has more than 1000 spacecraft, a description longer than 100 000
characters, a name (of a spacecraft, part, sensor, actuator or ground
station) longer than 64 characters, or a dynamics time step below 0.001 s. `lifetime --max-years` takes more
than 0 and at most 100 years, and a CCSDS file larger than 500 MB is not
read. These limits sit far above any real scenario; they stop a mistyped
or damaged file from filling the memory or the disk.

## Analyse

| Command | What it does |
|---|---|
| `lifetime scenario.json` | Re-entry date, and the 5-year and 25-year checks |
| `budget scenario.json` | Delta-V and propellant budget (ESA AD10 style) |
| `budget scenario.json --launch-delays` | The same, for launches 1 to 5 years late |
| `budget scenario.json --altitudes 400,450,500` | Which altitude fits the tank |
| `lifetime scenario.json --out life.json` | Also writes the lifetime as JSON |
| `budget scenario.json --out budget.json` | Also writes the budget as JSON |
| `spaceweather-resolve scenario.json` | Which space-weather file a run would use |

```console
$ spacemissionstudio lifetime spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json
my-sat: re-entry 2047-04-07, 17.26 years from 2030-01-01
  5-year rule: not met
  25-year guideline: met
WARNING: space weather uses MSFC's prediction (oct2026f10-prd.txt), 50th percentile F10.7 and Ap
WARNING: past 2041-10 MSFC's last 132 months repeat (ESA AD10 Sec. 5.9)
```

The two `WARNING` lines are normal: they say which space-weather data was
used. This took about 40 s.

With `--out`, `lifetime` and `budget` also write what they computed and
what from:

- `inputs`: the options you gave.
- `model`: the values used that are not in the scenario file. For a
  lifetime, the drag area and coefficient, the mass, the ballistic
  coefficient and the 120 km re-entry perigee. For a budget, its rules
  and margins, such as `CAM_COUNT_FACTOR` (4).
- `results`: the figures printed. A lifetime adds the perigee and apogee
  height over time (`decay`).
- `warnings` or `notes`: as printed.
- `provenance`: the tool and Basilisk versions, the file you gave and the
  SHA-256 of its bytes, the scenario's SHA-256, and each space-weather file
  read with its SHA-256. After `budget --run`, also the run's own record.

`--out` writes the budget itself. It does not go with `--launch-delays` or
`--altitudes` (exit code 2).

## Build scenarios

| Command | What it does |
|---|---|
| `generate-constellation in.json --out out.json --total-satellites 12 --planes 3 --phasing-factor 1 --altitude-km 780 --inclination-deg 86.4` | A Walker constellation from one spacecraft |
| `generate-phasing-formation in.json --out out.json --chief chief-1 --follower-name follower-1 --along-track-km 50` | A follower that holds a distance ahead of a chief |
| `generate-roe-formation in.json --out out.json --chief chief-1 --follower-name follower-1 --safe 0,300,300` | A follower in a formation of relative orbital elements: `--safe along,radial,cross[,phase]` [m, deg] for a passively safe helix, or `--roe` with the six ROE in metres; `--control-law impulsive` (default) or `continuous`. Clones the chief (or `--template-spacecraft`), whose station keeping provides the thruster |

## 3D models

A spacecraft's 3D model (the `model` block of a spacecraft in the
scenario file) gives its mass, center of mass, inertia and the facets
drag and solar pressure act on.

| Command | What it does |
|---|---|
| `model scenario.json` | Lists each model's parts, the mass properties and facets it gives, and whether the spacecraft's stored values still match |
| `model scenario.json --apply` | Writes those values into the scenario file |
| `model scenario.json --spacecraft sat-1 --export-obj sat.obj` | Writes the model as a Wavefront `.obj` (and `.mtl`), body frame, metres, +z up |

```console
$ spacemissionstudio model octagon.json
sat-1: 3D model, 2 part(s): bus (prism, 120 kg), dish (cone, 4 kg)
  mass properties (computed):
    mass 124 kg
    center of mass [0, 0, 0.0173029] m from B
    inertia about it [kg m^2]: Ixx 19.1419, Iyy 19.1419, Izz 16.0379, Ixy 0, Ixz 0, Iyz 0
    principal moments [kg m^2]: 16.0379, 19.1419, 19.1419
      axis 1: [0.0000, 0.0000, 1.0000] (0.0 deg from the nearest body axis)
      axis 2: [0.0000, 1.0000, 0.0000] (0.0 deg from the nearest body axis)
      axis 3: [1.0000, 0.0000, 0.0000] (0.0 deg from the nearest body axis)
  facets: 27, 5.59 m^2 in all; seen from +x 1.06, -x 1.06, +y 1.06, -y 1.06, +z 1.11, -z 1.11 m^2
  stored values: match the model
```

`validate` also warns when the stored values differ from the model. The
file formats are in the ICD (`compliance/docs/ICD.md`, 5.3.11).

## Orbit files (CCSDS)

| Command | What it does |
|---|---|
| `ccsds-validate file.opm ...` | Checks OPM, OMM or OEM files against the standard |
| `ccsds-export scenario.json --out dir` | Writes each spacecraft's starting state as an OPM |
| `ccsds-import file.opm scenario.json --spacecraft sat-1` | Sets a spacecraft's orbit from an OPM or OMM |

See [Orbit files](orbit-files.md).

## Flight software

| Command | What it does |
|---|---|
| `export-fsw scenario.json --spacecraft sat-1 --out dir` | Writes the attitude flight software as a C project |
| `fsw-status scenario.json` | Says whether recorded exports are up to date |
| `sil scenario.json --spacecraft sat-1 --binary prog` | Runs an external flight-software program in the loop |

The `sil --report` file also has a `provenance` section: the tool and
Basilisk versions, the scenario's SHA-256, the time, and the run's own
record under `run`.

See [Flight software and SIL](flight-software-and-sil.md).

## Reference data

| Command | What it does |
|---|---|
| `kernels-status` | Lists the SPICE kernels, gravity field and magnetic model, and whether each is installed |
| `earth-orientation` | Shows the Earth orientation files; `--fetch` downloads new ones, `--import` installs them from disk, `--rollback` undoes the last change |

See [Reference data](reference-data.md).

## Exit codes

A script can tell from the exit code what happened:

| Code | Means |
|---|---|
| 0 | Done |
| 1 | The input was refused (`INVALID:`); the message names what to correct |
| 2 | A component is missing (Basilisk, a SPICE kernel for `kernels-status`, PySide6 for `gui`), or the command line is wrong |
| 3 | The run or analysis failed, including a Monte Carlo batch in which a run failed |
| 4 | An internal error of SpaceMissionStudio; report it with the log file it names |
| 5 | The command ran, but its check did not pass: `fsw-status` found an export that is not up to date, or `sil --max-error` found a residual over the limit |

## From Python

The [examples](../../examples/README.md) call the same engine from
Python: build a scenario, run a template, sweep a parameter, read a Monte
Carlo batch.

**More detail:** `spacemissionstudio <command> --help` lists every option.

---

**Next:** [Orbit files](orbit-files.md) ·
[How-to guides](README.md)
