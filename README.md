<p align="center">
  <img src="SpaceMissionStudio/docs/images/banner.svg" alt="SpaceMissionStudio: satellite mission analysis, built on the Basilisk astrodynamics framework" width="960">
</p>

# SpaceMissionStudio

[![CI](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/workflows/spacemissionstudio.yml/badge.svg?branch=develop)](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/workflows/spacemissionstudio.yml)
[![Version 1.0.0](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.0.0)
![Basilisk 2.12.0](https://img.shields.io/badge/Basilisk-2.12.0-informational)
![Licence ISC](https://img.shields.io/badge/licence-ISC-green)

This repository is a fork of [Basilisk](https://github.com/AVSLab/basilisk),
the astrodynamics framework from the AVS Lab, with a desktop app for
satellite mission analysis added in [`SpaceMissionStudio/`](SpaceMissionStudio/).
Basilisk itself is unchanged: its README follows below, under
[Original Basilisk README](#original-basilisk-readme).

![The Scenario tab with template 22 loaded; the Explain page on the right summarises the orbit, the environment and the predicted ground passes](SpaceMissionStudio/docs/images/scenario_editor_tab.png)

## What it is

SpaceMissionStudio lets you design a satellite mission in forms, run it,
and read the results, without writing code. Every number comes from
Basilisk; SpaceMissionStudio adds the windows, scenario files, plots,
checks and analysis around it. Start from one of 28 template missions, or
build your own, then look at orbits, ground passes, eclipses, pointing,
battery, link margin, lifetime and propellant.

> **AI authorship.** SpaceMissionStudio was written by Claude
> (Anthropic's AI model) through Claude Code: its code, tests and
> documentation. A person reviewed the work, decided what to build next
> and approved what was merged.

## Quick start

**Linux:** the [1.0.0 release](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.0.0)
has a `.deb` installer (`sudo apt install ./spacemissionstudio_1.0.0_all.deb`)
and the wheel. 1.0.0 has no Windows or macOS installer yet.

**From source**, on Linux or macOS with Python 3.11 or newer (Windows: see
[Getting started](SpaceMissionStudio/docs/getting-started.md)):

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
| Install it, step by step, on any system | [Getting started](SpaceMissionStudio/docs/getting-started.md) |
| Do a specific task ("How do I…?") | [How-to guides](SpaceMissionStudio/docs/user-manual/README.md) |
| Learn the app from the beginning | [User Manual](SpaceMissionStudio/USER_MANUAL.md), also in the app (**Help > User Manual**, `F1`) |
| Learn by example | The [template catalog](SpaceMissionStudio/spacemissionstudio/scenarios/templates/README.md) and the [Python examples](SpaceMissionStudio/examples/README.md) |
| Fix a problem | [Troubleshooting](SpaceMissionStudio/docs/troubleshooting.md) and the [FAQ](SpaceMissionStudio/docs/faq.md) |
| Look up a term | [Glossary](SpaceMissionStudio/docs/glossary.md) |
| See every document | [Documentation index](SpaceMissionStudio/docs/README.md) |
| Contribute to the app | [Contributing](SpaceMissionStudio/CONTRIBUTING.md) and the [developer guide](SpaceMissionStudio/docs/developer/README.md) |
| Use Basilisk itself | The [original Basilisk README](#original-basilisk-readme) below |

## Features

- **Scenarios** as plain JSON, edited in a tree of forms and checked as
  you type; orbits from elements, position and velocity, or a TLE.
- **Orbits:** detailed Earth gravity, Sun and Moon, drag from real space
  weather, solar pressure, measured Earth orientation, runs of up to
  about 10 years.
- **Pointing:** five pointing modes, real sensors and actuators, momentum
  unloading, navigation error, surface facets, flexible solar arrays.
- **3D models** of the spacecraft, built from shapes or imported `.obj`
  files, giving its mass, center of mass, inertia and surfaces.
- **Orbit keeping:** LEO and GEO station keeping, formations with three
  control laws, Walker constellations.
- **Mission Sequence:** burns, Lambert transfers, reports, conditions,
  stopping on events such as a ground pass.
- **Analysis:** passes, eclipses, power, link margin, onboard data,
  thermal, Monte Carlo, orbital lifetime, ESA AD10-style propellant
  budgets.
- **Results:** interactive plots, an events timeline, a shared time
  cursor, run comparison, CSV, PNG and SVG export, provenance on every
  output.
- **Exchange:** CCSDS orbit messages; flight-software export as a C
  project; software-in-the-loop testing.
- **3D view** in Vizard; a **command line** for every analysis; a
  **Python API**; light and dark themes; **offline by design**.

Details: [Capabilities and verification](SpaceMissionStudio/docs/reference/capabilities.md).

## Requirements

| | |
|---|---|
| System | Linux x86_64 or aarch64 (glibc 2.28 or newer); from source also Windows 10 or 11 x86_64 and macOS 11 or newer on Apple silicon |
| Python | 3.11 or newer; CI tests 3.11 (Basilisk's wheels go up to 3.14) |
| Basilisk | 2.12.0, from PyPI |
| Disk | About 1.6 GB, including the reference data |
| Internet | Once, to install and fetch the reference data |

## Licence and status

- **Licence:** ISC, the same as Basilisk ([`LICENSE`](LICENSE),
  [`SpaceMissionStudio/LICENSE`](SpaceMissionStudio/LICENSE)).
- **Version:** 1.0.0 ([release](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.0.0),
  [changelog](SpaceMissionStudio/CHANGELOG.md)), the first release of the
  renewed tool; the version numbers used before the renewal are withdrawn.
- **Platforms:** 1.0.0 is a Linux release: the `.deb`, the wheel and
  `install.sh` were built, installed and run end to end with Basilisk
  2.12.0 ([`packaging/README.md`](SpaceMissionStudio/packaging/README.md)).
  The test suite also runs in CI on Windows and macOS, where a few test
  failures are not yet fixed; their installers follow in a later release.
- **Known gaps:** [Known limitations](SpaceMissionStudio/docs/reference/limitations.md).

## Related tools

| Tool | Relation |
|---|---|
| [Basilisk](https://github.com/AVSLab/basilisk) | The simulation engine; this repository is its fork |
| [Vizard](docs/source/Vizard/VizardDownload.rst) | Basilisk's 3D viewer; the app streams to it or writes playback files |
| [GMAT](https://sourceforge.net/projects/gmat/) | NASA's mission analysis tool; used as a reference to validate the app |

## What this fork adds

Everything else in the repository is upstream Basilisk, unchanged.

| Path | What it is |
|---|---|
| [`SpaceMissionStudio/`](SpaceMissionStudio/) | The app: code, tests, documentation, packaging, compliance records |
| [`.github/workflows/spacemissionstudio.yml`](.github/workflows/spacemissionstudio.yml) | CI for the app (Linux, Windows, macOS) |
| [`.github/workflows/spacemissionstudio-windows-installer.yml`](.github/workflows/spacemissionstudio-windows-installer.yml) | Builds, installs and runs the Windows setup program on a Windows runner |
| [`docs/upstream/`](docs/upstream/README.md) | An untouched copy of the upstream README, for syncing, and a note on it |
| `README.md` (this file) | The part above this line; the upstream README follows unchanged |
| `.gitignore` | One blank line |

The app installs Basilisk from PyPI; it does not build or use the
Basilisk sources in [`src/`](src/). How to take in new upstream releases:
[Keeping up with upstream Basilisk](SpaceMissionStudio/docs/developer/upstream-sync.md).

**[Jump to the original Basilisk README](#original-basilisk-readme)**

---

# Original Basilisk README

The rest of this file is the README of upstream Basilisk
([AVSLab/basilisk](https://github.com/AVSLab/basilisk)) at commit
[`c1bf0d7d6`](https://github.com/AVSLab/basilisk/commit/c1bf0d7d67df7ae5bb74cd008d4c79cc3d106063)
(2026-10-02, the fork point), unchanged except that its headings are one
level lower. An untouched copy is in
[`docs/upstream/README.upstream.md`](docs/upstream/README.upstream.md).

<!-- BEGIN UPSTREAM README -->
## README

### Basilisk

* [Summary of Basilisk](docs/source/index.rst)
* [Release Notes](docs/source/Support/bskReleaseNotes.rst)

#### Installation

Basilisk can be installed in two ways, either from PyPI or by building from
source.

For most users, installing from PyPI is the easiest and fastest way to get
started. Building from source is recommended if you need to link to external
C++ modules or want to customize the build configuration.

##### Install from PyPI

The easiest way to get started with Basilisk is to install the prebuilt wheel
from [PyPI](https://pypi.org/project/bsk/):

```bash
pip install "bsk[all]"
```

This installs the latest stable version with the core Basilisk wheel and all
optional Basilisk component wheels. MuJoCo is included in the core wheel, while
optical navigation is installed through the optional component package. See the
[install](docs/source/Install.rst) docs for supported platforms and additional
details about the wheels.

If you need a smaller installation and do not use optional Basilisk components,
install only the core wheel:

```bash
pip install bsk
```

If you also want the optional Python dependencies used by example scripts, install:

```bash
pip install "bsk[all,examples]"
```

##### Build from Source

If you need to use external C++ modules or want to customize the build, follow
the platform-specific setup instructions:

* [Setup a macOS Development Environment](docs/source/Build/installOnMacOS.rst)

* [Setup a Linux Development Environment](docs/source/Build/installOnLinux.rst)

* [Setup a Windows Development Environment](docs/source/Build/installOnWindows.rst)

See the [Build from Source docs](docs/source/Build.rst) for full details.

##### Containers

Basilisk container images are published to:

* [GHCR](https://ghcr.io/avslab/basilisk)

Published tags follow this policy:

* `v*` (for example `v2.9.0`) and `latest` for release tags

Images are multi-architecture (`linux/amd64`, `linux/arm64`).

Quick start:

```bash
docker pull ghcr.io/avslab/basilisk:latest
docker run --rm ghcr.io/avslab/basilisk:latest
```

For more details, see [container docs](docs/source/Build/containers.rst).

#### Basilisk Development guidelines

* [Contributing](CONTRIBUTING.md)
* [Coding Guidelines](docs/source/Support/Developer/CodingGuidlines.rst)

#### Getting Started

To get started with Basilisk (BSK), several tutorial python files are provided in the installed package.  Within this
web page documentation site, they are listed and discussed in the [integrated example script](docs/source/examples/index.rst) page.

The documentation lists the scenarios in an order that facilitates learning basic BSK features. The python scripts
are stored in the repository under `basilisk/examples`. A good start would be to run `scenarioBasicOrbit.py`.

If you downloaded Basilisk through `pip install "bsk[all]"`, then you can download all examples to the local folder using the command line `bskExamples`.

To play with the tutorials, it is suggested the user makes a copy of these tutorial files, and use the copies in order
to learn, test and experiment. Copy the folder `basilisk/examples` into a
new folder, and change to that directory.
To run the default scenario of `scenarioBasicOrbit`, in the directory of the
copied tutorials, execute the python script: `python scenarioBasicOrbit.py`

Now, when you want to use a tutorial, navigate inside that folder, and edit and execute the *copied* integrated tests.

Any new BSK module development should not occur within the BSK folder as this will be updated rapidly.  Rather,
new FSW algorithm or simulation code modules should be created in a custom folder outside of the BSK directory.
See the [building custom modules](docs/source/Build/buildExtModules.rst) web page
for more information.

To use the standalone 3D Visualization, download the [Vizard](docs/source/Vizard/VizardDownload.rst).
This is in development, but does provide a 3D view of many of the simulation states.

#### Who do I talk to?

Questions and answers are fielded in the project's [Github Discussions](https://github.com/AVSLab/basilisk/discussions).
<!-- END UPSTREAM README -->
