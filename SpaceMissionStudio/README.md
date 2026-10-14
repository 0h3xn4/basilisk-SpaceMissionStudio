# SpaceMissionStudio

[![CI](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/workflows/spacemissionstudio.yml/badge.svg?branch=develop)](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/workflows/spacemissionstudio.yml)
![Version 3.0.0](https://img.shields.io/badge/version-3.0.0-blue)
![Basilisk 2.12.0](https://img.shields.io/badge/Basilisk-2.12.0-informational)
![Licence ISC](https://img.shields.io/badge/licence-ISC-green)

A desktop app for planning and simulating satellite missions, built on
the Basilisk astrodynamics framework.

![The Scenario Editor with template 22 loaded; the Explain tab on the right summarises the orbit, the environment and the predicted ground passes](docs/images/scenario_editor_tab.png)

## What it is

SpaceMissionStudio lets you design a satellite mission in forms, run it,
and read the results, without writing code. Every number comes from
[Basilisk](https://avslab.github.io/basilisk/) (AVS Lab, University of
Colorado Boulder); SpaceMissionStudio adds the windows, scenario files,
plots, checks and analysis around it. Each feature maps to a Basilisk
module, or is marked as the tool's own code.

Start from one of 27 template missions (a single orbit, a GEO slot, a
formation, a complete small satellite with power and a radio link), or
build your own, then look at orbits, ground passes, eclipses, pointing,
battery, link margin, lifetime and propellant.

> **AI authorship.** SpaceMissionStudio was written by Claude
> (Anthropic's AI model) through Claude Code: the application code, the
> tests, this documentation, [`HISTORY.md`](HISTORY.md) and the commits.
> A person reviewed the work, decided what to build next and approved
> what was merged, but did not write the code or the text. Anyone
> evaluating the project should know this from the start.

## Quick start

On Linux or macOS (Windows: see [Getting started](docs/getting-started.md)):

```bash
git clone https://github.com/0h3xn4/basilisk-SpaceMissionStudio.git
cd basilisk-SpaceMissionStudio/SpaceMissionStudio
python3 -m venv .venv
source .venv/bin/activate
pip install "bsk[all]==2.12.0"
pip install -e ".[gui]"
spacemissionstudio kernels-status
spacemissionstudio earth-orientation --fetch
spacemissionstudio gui
```

The app opens on **Templates**. Click **22 - Starter: your first LEO
satellite**, **Open Template**, then **Run** (`Ctrl+R`).
A few seconds later the **Results** tab shows the orbit and the
**Events** tab lists four ground passes over Berlin.

## Where to go next

| You want to | Read |
|---|---|
| Install it, step by step, on any system | [Getting started](docs/getting-started.md) |
| Do a specific task ("How do I…?") | [How-to guides](docs/user-manual/README.md) |
| Learn the app from the beginning | [User Manual](USER_MANUAL.md), also in the app (**Help > User Manual**, `F1`) |
| Learn by example | The [template catalog](spacemissionstudio/scenarios/templates/README.md) and the [Python examples](examples/README.md) |
| Fix a problem | [Troubleshooting](docs/troubleshooting.md) and the [FAQ](docs/faq.md) |
| Look up a term | [Glossary](docs/glossary.md) |
| See everything | [Documentation index](docs/README.md) |
| Contribute | [Contributing](CONTRIBUTING.md) and the [developer guide](docs/developer/README.md) |

## Features

- **Scenarios** as plain JSON: spacecraft, orbits (elements, position
  and velocity, or a TLE), gravity, ground stations, space weather, a
  Mission Sequence and Monte Carlo dispersions; checked as you type.
- **Orbits:** detailed Earth gravity, Sun and Moon, drag from real space
  weather, solar pressure, measured Earth orientation (ITRF93), runs of up
  to about 10 years.
- **Pointing:** five pointing modes, star trackers, IMUs, sun sensors,
  magnetometers, reaction wheels, thrusters, torque rods, momentum
  unloading, navigation error, surface facets and flexible solar arrays.
- **Orbit keeping:** LEO station keeping, GEO longitude and inclination
  boxes, formations with three control laws, Walker constellations.
- **Mission Sequence:** coast, burn, Lambert transfers, reports,
  conditions and loops, stopping on events such as a ground pass.
- **Analysis:** ground passes, eclipses, power, radio link margin,
  onboard data and downlink, thermal, Monte Carlo, orbital lifetime and
  deorbit, ESA AD10-style propellant budgets with launch-delay and
  altitude trades.
- **Results:** interactive plots, an events timeline, a time cursor
  shared by every view, run comparison, CSV, PNG and SVG export, and a
  provenance record on every output.
- **Exchange:** CCSDS OPM, OMM and OEM orbit messages; flight-software
  export as a standalone C project; software-in-the-loop testing of
  your own flight software.
- **3D view** in Vizard, live or played back.
- **Command line** for every analysis, and a Python API.
- **Offline by design:** nothing is downloaded without asking.

Details, and the Basilisk module behind each feature:
[Capabilities and verification](docs/reference/capabilities.md).

## Requirements

| | |
|---|---|
| System | Linux x86_64 or aarch64 (glibc 2.28 or newer), Windows 10 or 11 x86_64, macOS 11 or newer on Apple silicon |
| Python | 3.11 or newer; CI tests 3.11 (Basilisk's wheels go up to 3.14) |
| Basilisk | 2.12.0, installed from PyPI (`bsk`) |
| Disk | About 1.6 GB, including the reference data |
| Internet | Once, to install and fetch the reference data |

Installers (a Linux `.deb` and a Windows setup program) and install
scripts are in [`packaging/`](packaging/README.md).

## Licence and status

- **Licence:** ISC, the same as Basilisk ([`LICENSE`](LICENSE)).
- **Version:** 3.0.0 ([release](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/v3.0.0),
  [changelog](CHANGELOG.md)). Needs Python 3.11 or newer.
- **Tested** in CI on Linux, Windows and macOS with Basilisk 2.12.0;
  the Linux packages were installed and run end to end, and the 3.0.0
  `.deb` was installed by hand on Ubuntu 24.04 (the app started,
  template 22 ran). The Windows
  setup program is built, installed and run in CI on a Windows runner; it has not yet been tried by hand on a real Windows machine; `install.ps1` has not been run.
- **Known gaps:** [Known limitations](docs/reference/limitations.md).
- **Standards:** the project's ECSS and CCSDS records are in
  [`compliance/`](compliance/README.md). They are the project's own
  records, not a certification.

## Related tools

| Tool | Relation |
|---|---|
| [Basilisk](https://github.com/AVSLab/basilisk) | The simulation engine; this repository is a fork of it |
| [Vizard](https://avslab.github.io/basilisk/Vizard/Vizard.html) | Basilisk's 3D viewer; the app streams to it or writes playback files |
| [GMAT](https://sourceforge.net/projects/gmat/) | NASA's mission analysis tool; used as a reference to validate the app (time scales, propagation, CCSDS files) |

SpaceMissionStudio has no direct integration with other mission tools;
it exchanges data through the files listed in [Tips](docs/tips.md).

---

**Next:** [Getting started](docs/getting-started.md) ·
[Documentation index](docs/README.md)
