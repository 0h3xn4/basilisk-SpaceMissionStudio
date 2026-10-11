# Changelog

What changed in SpaceMissionStudio, release by release, newest first.
Each entry is a short summary; [`HISTORY.md`](HISTORY.md) has the full
story behind every change (why, how it was found, how it was tested).

The version follows [semantic versioning](https://semver.org): a major
version breaks something you rely on, a minor one adds features, a patch
fixes bugs.

## Unreleased

Everything since 2.0.0. The version number in the code is still 2.0.0.

**New features**
- **Flight-software export.** The **Flight Software** tab and
  `spacemissionstudio export-fsw` write a spacecraft's attitude flight
  software as a standalone C project (Basilisk 2.12.0's C modules,
  unchanged), with a CMake build, an interface control document, and
  unit and replay tests recorded from the simulation.
- **Software in the loop.** **Run SIL** and `spacemissionstudio sil` fly
  a spacecraft with an external flight-software program in lock-step and
  compare its commands with the simulation's own.
- **Navigation error.** Configurable errors on what the flight software
  is told (attitude, rate, Sun heading, position, velocity).
- **CCSDS orbit messages.** Read, validate and write OPM, OMM and OEM
  files (`ccsds-validate`, `ccsds-import`, `ccsds-export`, `run --oem`).
- **Earth orientation.** Measured Earth rotation (ITRF93) from NAIF's
  IERS-based files (`earth-orientation --fetch`).
- **Propellant budgets** in the style of ESA's AD10 guideline (**Budget**
  tab, `spacemissionstudio budget`), with launch-delay and altitude
  trades.
- **End of life.** Orbital lifetime and deorbit burns (**End of Life**
  tab, `spacemissionstudio lifetime`), checked against the 5- and 25-year
  rules.
- **Long runs.** Runs of up to about 10 years, split into segments past
  Basilisk's 104-day limit, with a recording interval.
- **Onboard data handling** and a patch-antenna downlink (template 26).
- **Flexible solar arrays** on spring-damper hinges (template 27).
- **Facet models** for attitude-dependent drag and solar pressure.
- **GEO station-keeping** in longitude and inclination.
- **Formation control** with Basilisk's mean-element (`meanOEFeedback`)
  and Hill-frame (`hillPoint`-based) laws (template 24).
- **Monte Carlo results in the app** (**Monte Carlo** tab) and more
  dispersions (orbit, inertia, rate, drag and SRP coefficients).
- **Real space weather only:** CelesTrak's record and NASA MSFC's
  prediction; the synthetic profile is gone.
- **The Data tab:** every reference file, with downloads that ask first,
  import from disk and rollback.
- **Events:** passes, eclipses, burns and mode changes, with a timeline
  and one time cursor shared by every tab.
- **Undo and redo, run comparison, a command palette** (`Ctrl+K`).
- **Provenance:** every run writes `provenance.json` with the software
  versions and checksums of every input.
- **New templates** 22 to 27, including two starting points for your own
  mission (22 and 23), and Python examples in `examples/`.
- **Documentation for newcomers:** a getting-started guide, the user
  manual in the app (**Help > User Manual**, `F1`), how-to pages, a
  glossary, an FAQ and troubleshooting.

**Changed**
- A new look (IBM's Carbon design: IBM Plex fonts, flat panels).
- Templates fly 100 to 500 kg spacecraft; the CubeSat presets were
  replaced by 150, 300 and 500 kg buses.
- Templates use AD10's operations drag coefficient, 3.0.
- Script blocks in a Mission Sequence ask before they run; conditions no
  longer use Python's `eval()`.
- The mouse wheel no longer changes values in forms.

**Fixed** (the main ones; `HISTORY.md` lists every one)
- Software in the loop: a run with a missed step deadline could hang.
- Scenario files with wrong-typed values are refused, naming the field.
- Malformed CCSDS messages give conformance errors instead of tracebacks.
- Two Basilisk accuracy defects worked around (found by the validation
  against GMAT, IERS and SOFA).
- Parallel runs could read a half-written space-weather file.
- Windows: export checksums and SIL timing.

**Compliance**
- ECSS-E-ST-40C, ECSS-Q-ST-80C, ECSS-E-ST-10-09C, ECSS-E-ST-10-04C and
  CCSDS 502.0-B-3: requirements, design, verification and compliance
  records in [`compliance/`](compliance/README.md).

## 2.0.0

**Breaking:** renamed from "missionStudio" to "SpaceMissionStudio".
Scenario files are unchanged; code and scripts that use the old names
must change:

| Before | After |
|---|---|
| Folder `missionStudio/` | `SpaceMissionStudio/` |
| `import missionstudio` | `import spacemissionstudio` |
| Command `missionstudio ...` | `spacemissionstudio ...` |
| Package `missionstudio` (PyPI, `.deb`) | `spacemissionstudio` |

Also:
- The Windows installer has a new application ID.
- `missionAnalysis/`, an older case study nothing depended on, was
  removed.

## 1.1.0

All additions; every 1.0.0 scenario file still loads unchanged.

- New actuators and effectors, each with a template: gravity-gradient
  torque (10), thruster attitude control (11), wheel momentum dumping
  with thrusters (12) or torque rods (13), and a fuel tank (17).
- Sun-heading estimation from coarse sun sensors (14) and pointing at a
  planet (15).
- The `lambert_transfer` Mission Sequence command (16).
- LEO station-keeping (18). Eighteen templates in all.
- A **Customize...** wizard for every template.
- The attitude controller's gains scale to the spacecraft's inertia, so
  a small spacecraft no longer diverges.
- Dialogs size themselves correctly; the Load Scenario tab no longer
  garbles on resize.
- The first user manual, with screenshots.

## 1.0.0

The first release.

- A complete end-to-end run on a real Basilisk installation (template 05,
  7 days, with live Vizard), after finding and fixing a crash in the
  Vizard live-data panels.
- Linux and Windows install scripts (`packaging/install.sh`,
  `install.ps1`).

---

**Next:** [Documentation index](docs/README.md) ·
[Development log](HISTORY.md)
