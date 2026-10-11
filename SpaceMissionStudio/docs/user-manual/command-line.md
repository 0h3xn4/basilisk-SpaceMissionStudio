# Use the command line

How to check, run and analyse scenarios without the GUI, for scripts,
batch jobs and CI. Every command uses the same engine as the app.

`spacemissionstudio --help` lists the commands; `spacemissionstudio
<command> --help` shows one command's options. A command that fails exits
with a non-zero status and prints `ERROR:` or `INVALID:` with the reason.

## Contents

- [Check and run](#check-and-run)
- [Analyse](#analyse)
- [Build scenarios](#build-scenarios)
- [Orbit files (CCSDS)](#orbit-files-ccsds)
- [Flight software](#flight-software)
- [Reference data](#reference-data)

## Check and run

| Command | What it does |
|---|---|
| `validate scenario.json` | Checks the file without running it. Does not need Basilisk. |
| `run scenario.json --out-dir out` | Runs it and writes one CSV per quantity, `events.csv` and `provenance.json` |
| `monte-carlo scenario.json --archive-dir mc` | Runs the scenario's Monte Carlo batch |
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

## Analyse

| Command | What it does |
|---|---|
| `lifetime scenario.json` | Re-entry date, and the 5-year and 25-year checks |
| `budget scenario.json` | Delta-V and propellant budget (ESA AD10 style) |
| `budget scenario.json --launch-delays` | The same, for launches 1 to 5 years late |
| `budget scenario.json --altitudes 400,450,500` | Which altitude fits the tank |
| `spaceweather-resolve scenario.json` | Which space-weather file a run would use |

```console
$ spacemissionstudio lifetime spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json
My-sat: re-entry 2047-04-07, 17.26 years from 2030-01-01
  5-year rule: not met
  25-year guideline: met
WARNING: space weather uses MSFC's prediction (oct2026f10-prd.txt), 50th percentile F10.7 and Ap
WARNING: past 2041-10 MSFC's last 132 months repeat (ESA AD10 Sec. 5.9)
```

The two `WARNING` lines are normal: they say which space-weather data was
used. This took about 40 s.

## Build scenarios

| Command | What it does |
|---|---|
| `generate-constellation in.json --out out.json --total-satellites 12 --planes 3 --phasing-factor 1 --altitude-km 780 --inclination-deg 86.4` | A Walker constellation from one spacecraft |
| `generate-phasing-formation in.json --out out.json --chief chief-1 --follower-name follower-1 --along-track-km 50` | A follower that holds a distance ahead of a chief |

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

See [Flight software and SIL](flight-software-and-sil.md).

## Reference data

| Command | What it does |
|---|---|
| `kernels-status` | Lists the SPICE kernels, gravity field and magnetic model, and whether each is installed |
| `earth-orientation` | Shows the Earth orientation files; `--fetch` downloads new ones, `--import` installs them from disk, `--rollback` undoes the last change |

See [Reference data](reference-data.md).

## From Python

The [examples](../../examples/README.md) call the same engine from
Python: build a scenario, run a template, sweep a parameter, read a Monte
Carlo batch.

**More detail:** `spacemissionstudio <command> --help` lists every option.

---

**Next:** [Orbit files](orbit-files.md) ·
[How-to guides](README.md)
