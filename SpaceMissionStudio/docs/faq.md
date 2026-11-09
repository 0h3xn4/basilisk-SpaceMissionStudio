# Frequently asked questions

Short answers to the questions newcomers ask most, with links to the
details.

## Contents

- [What is SpaceMissionStudio?](#what-is-spacemissionstudio)
- [Do I need to know programming, or spaceflight?](#do-i-need-to-know-programming-or-spaceflight)
- [Which systems does it run on?](#which-systems-does-it-run-on)
- [Does it need the internet?](#does-it-need-the-internet)
- [Where does the space weather come from?](#where-does-the-space-weather-come-from)
- [How accurate is it?](#how-accurate-is-it)
- [Orbit only or full attitude?](#orbit-only-or-full-attitude)
- [How long can a run be, and how long does it take?](#how-long-can-a-run-be-and-how-long-does-it-take)
- [Can I exchange data with other tools?](#can-i-exchange-data-with-other-tools)
- [Can I use it from Python?](#can-i-use-it-from-python)
- [Does it comply with ECSS or CCSDS standards?](#does-it-comply-with-ecss-or-ccsds-standards)
- [Who wrote it, and under what licence?](#who-wrote-it-and-under-what-licence)
- [Why does every command print an INFO line?](#why-does-every-command-print-an-info-line)

## What is SpaceMissionStudio?

A desktop app for planning and simulating satellite missions: orbits,
pointing, power, radio links, station keeping, formations, lifetime and
propellant budgets, and the spacecraft's 3D model with its design
checks. Every number comes from
[Basilisk](https://avslab.github.io/basilisk/), the open-source
astrodynamics framework from the AVS Lab at the University of Colorado
Boulder. SpaceMissionStudio adds the windows, forms, plots, templates and
checks around it.

## Do I need to know programming, or spaceflight?

No. Start from one of the 32 templates and change it in forms
([Getting started](getting-started.md)). The [glossary](glossary.md)
explains the terms. Python is optional: for scripting and batch runs.

## Which systems does it run on?

Linux (x86_64 and aarch64, glibc 2.34 or newer) and Windows 10 and 11
(x86_64). The test suite runs on both in CI. There are installers for
Linux (x86_64) and Windows, which bring their own Python 3.14; installing
from source needs Python 3.14 (3.11 to 3.13 are no longer supported since
2.0.0). macOS is not supported. Details:
[Getting started, section 1](getting-started.md#1-what-you-need).

## Does it need the internet?

Not with the installers: from 1.1.1 they bring Python,
Basilisk and the reference data with them. Installed from source, it
needs the internet once, to install and fetch the reference data. Either
way it then runs offline:

- A run never downloads anything. If a file is missing, it stops and
  says which one.
- Nothing is downloaded without your say-so. Each time the GUI starts,
  a **Fetch or update reference data?** card on Home offers to check
  for newer reference data; **Not now** touches no network. The **Reference data** window's downloads ask
  first, naming the source, the files and the size, and default to No.
  Vizard downloads only when you click **Download Vizard**. On the
  command line, only `kernels-status`, `earth-orientation --fetch`,
  `small-bodies --fetch`, `gaseous-attenuation --fetch` and
  `spaceweather-download` download.
- Every file can also be installed from disk, for machines that never go
  online.

See [Reference data](user-manual/reference-data.md) and, for the
installers, [`packaging/README.md`](../packaging/README.md).

## Where does the space weather come from?

From real data only: CelesTrak's record of the observed solar flux
(F10.7) and geomagnetic index (Ap) and its 45-day forecast, bundled with
the app, then NASA MSFC's prediction of the solar cycle. There is no synthetic or made-up
profile. A run past the end of the record prints
`WARNING: space weather uses MSFC's prediction (...)`; that is expected.

## How accurate is it?

As accurate as Basilisk and its inputs. The app's own checks are in
[`compliance/`](../compliance/README.md): validation runs against GMAT,
IERS and SOFA reference values, and two Basilisk accuracy defects found
that way and worked around. Each template's catalog entry says what a
real run of it measured. Known gaps are listed in
[Known limitations](reference/limitations.md).

## Orbit only or full attitude?

*Orbit only* simulates where each spacecraft goes: fast, and enough for
orbits, drag, station keeping, formations and ground passes. *Full
attitude* also simulates which way it points, so sensors, wheels, torque
rods, pointing modes, surface facets and power become available; it is
slower. Start with orbit only and switch when you need pointing.

## How long can a run be, and how long does it take?

Up to about 10 years. Past 100 days the run is split into segments and
chained automatically. Set **Record every** for long runs, or the results
fill memory. Template 22 (one day, orbit only) takes about 5 s; five years
of LEO station keeping took about 50 minutes. Mission sequences, phasing
keeping, ROE formations, optical navigation, runs around a small body,
Monte Carlo and Vizard are limited to 100 days.

## Can I exchange data with other tools?

Yes, through standard files:

- orbits in and out as CCSDS OPM, OMM and OEM, and in as TLEs, in the
  app or on the command line
  ([Orbit files](user-manual/orbit-files.md));
- a spacecraft's 3D model, mass properties, sensors and actuators,
  thrusters (onto the 3D model), and the power budget's bus load and
  solar panel, in from an IDM-CIC model
  (`.idm`, read only; IDM-CIC is © CNES;
  [Import a spacecraft from IDM-CIC](user-manual/idm-cic.md)), and 3D
  shapes in and out as Wavefront `.obj`
  ([Build a 3D model](user-manual/3d-model.md));
- results as CSV in SI units;
- scenarios as plain JSON;
- the attitude flight software as a C project with an interface control
  document ([Flight software and SIL](user-manual/flight-software-and-sil.md)).

There is no direct link to other applications. [Tips](tips.md) lists
every file the app reads and writes.

## Can I use it from Python?

Yes. [`examples/`](../examples/README.md) builds a scenario in code, runs
templates, plans a Hohmann transfer, sweeps altitudes and reads a Monte
Carlo batch. `spacemissionstudio.api` loads, checks and runs a scenario
and computes its lifetime, budget, comparisons, design checks, model
analyses and re-entry estimate with the app's engine
([The Python API](api.md)). Every
command-line command uses the same engine
([Use the command line](user-manual/command-line.md)).

## Does it comply with ECSS or CCSDS standards?

The project keeps records of how it addresses ECSS-E-ST-40C,
ECSS-Q-ST-80C, ECSS-E-ST-10-09C, ECSS-E-ST-10-04C and CCSDS 502.0-B-3:
requirements, design, verification, a compliance matrix and the
deviations, in [`compliance/`](../compliance/README.md). These are the
project's own records, not a certification by an outside body.

## Who wrote it, and under what licence?

The application, its tests and its documentation were written by Claude,
Anthropic's AI model, through Claude Code; a person reviewed the work and
decided what to build and merge. It is distributed under the ISC licence,
the same as Basilisk ([`LICENSE`](../LICENSE)).

## Why does every command print an INFO line?

`INFO ... Logging to ~/.spacemissionstudio/logs/...log` tells you where
the log file for that command is. It is not an error. Other normal
messages are listed in
[Troubleshooting](troubleshooting.md#messages-that-are-normal).

---

**Next:** [Troubleshooting](troubleshooting.md) ·
[Glossary](glossary.md) ·
[Documentation index](README.md)
