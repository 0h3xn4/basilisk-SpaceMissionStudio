# Changelog

What changed in SpaceMissionStudio, release by release, newest first.
Each entry is a short summary; [`HISTORY.md`](HISTORY.md) has the full
story behind every change (why, how it was found, how it was tested).

The version follows [semantic versioning](https://semver.org): a major
version breaks something you rely on, a minor one adds features, a patch
fixes bugs.

## Unreleased

**New features**
- **3D spacecraft models** (part 1: the model and what it drives). A
  spacecraft can carry a model built from boxes, n-sided prisms (an
  octagonal bus), cylinders, cones, spheres and thin panels, and from the
  groups of imported `.obj` files. From it come the mass, center of mass
  and inertia (or typed in, or read from a JSON or CSV file) and the drag
  and solar-pressure facets; Vizard shows the model. `spacemissionstudio
  model` reports a model, applies it to the scenario and exports `.obj`.
- **The 3D model editor** (spacecraft editor, **3D model** tab): a parts
  list, each part's settings, and the model in 3D; mass properties
  computed, typed in or imported; the facets it gives; an `.obj` export.
  Guide: `docs/user-manual/3d-model.md`.
- **Template 28, "Octagonal bus from a 3D model"**: a 300 kg satellite
  whose mass, center of mass (4.8 cm off its body origin), inertia,
  facets and Vizard look come from its parts; its wheels show the torque
  the offset center of mass gives. The other templates gain the new
  fields' defaults (`center_of_mass_b_m` at the origin, no model) and
  behave as before.
- **Center of mass.** A spacecraft's `center_of_mass_b_m` is now Basilisk's
  hub offset: drag, solar pressure and thrust get their torque about the
  center of mass, not about the body origin. Older files load with it at
  the origin, as before.

- **A top bar and a fuller status bar.** Above the tabs: the scenario's
  name, whether it has unsaved changes, where it came from (a template
  or a file), the last run, and a tag with the run state (running and
  its percentage, done and how long it took, failed, cancelled). In the
  status bar, always: the Basilisk version, the reference data (click to
  open the Data tab), the Earth orientation data's date and the frames
  (UX audit U-04, U-06, U-07).

**Fixed**
- Results no longer look current after the scenario changes: a banner
  above the run views says they are from a previous version, with
  **Re-run** (UX audit U-20).
- The window fits a 1280 x 720 screen again. The End of Life page
  scrolls, and the comparison controls in Results have their own row; a
  second run of a scenario with a long name used to need 1516 px of width
  (UX audit U-03).
- The spacecraft editor kept only the moments of inertia: a spacecraft's
  products of inertia (typed into the file) were set to 0 whenever it was
  opened and OK'd. They are now kept, and shown.
- The facet table kept only 6 significant digits: a facet with more (a
  computed one, or one typed into the file) was rounded whenever the
  spacecraft editor was opened and OK'd. It now keeps every digit.
- The app's web views (the Results plots, the 3D view) start Chromium with
  `--ignore-gpu-blocklist`, so WebGL works without a usable GPU.
- `spacemissionstudio --version` (or `-V`) prints the SpaceMissionStudio,
  Basilisk and Python versions, and says when the installed Basilisk is
  not the qualified 2.12.0 or is missing.

## 3.0.0 (2026-10-12)

[Release page](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/v3.0.0): the wheel, sdist, Linux `.deb`, Windows setup
program, and `SHA256SUMS-linux` and `SHA256SUMS-windows`.

Everything since 2.0.0, including the fixes from the pre-release audit
([`AUDIT.md`](AUDIT.md)).

**Breaking** (why this is a major version)
- **Python 3.11 or newer** is required (was 3.9); 3.11 is what the test
  suite and CI run.
- **Monte Carlo flies the Mission Sequence.** Every run of a batch now
  flies the scenario's Mission Sequence, as `run` does; before, the
  batch silently propagated for the set duration instead. A batch with
  script blocks needs consent (`monte-carlo --allow-scripts`, or Yes in
  the GUI), and `monte-carlo` refuses a folder that holds files other
  than an earlier batch unless given `--overwrite`.
- **Scenario files that load in 2.0.0 can be refused**, each with a
  message naming the field:
  - Spacecraft, station, sensor and actuator names cannot contain
    `/ \ : * ? " < > | .` or control characters, start or end with a
    space, or be a Windows device name; two names that collide are
    refused. Names become file names, and a name could write outside the
    output folder.
  - Unknown reaction-wheel and thruster types, and limits Basilisk would
    exit on (non-positive `u_max`, `MaxThrust`, ...).
  - Non-finite or zero orbit values, malformed TLEs, a TLE orbit around
    another body than Earth.
  - A Mission Sequence step longer than 100 days, a phasing formation
    with a negative along-track distance, a thermal sensor without the
    Sun, a phasing chief not given as classical elements,
    comms-pointing with actuators.
  - Monte Carlo counts that are not whole numbers, reversed or
    non-numeric bounds, a normal dispersion with a negative 1-sigma, and
    `schema_version` below 1.
- `ccsds-import` refuses an OPM centred on another body than the
  scenario's, and an OMM around another body than Earth.
- **Device catalog:** the seven entries made outside Europe were removed
  (32 remain).

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
  glossary, an FAQ and troubleshooting. Screenshots of every main tab, captured from
  the app by `scripts/capture_screenshots.py`.

**Changed**
- The bundled CelesTrak space weather is current: observations to
  2026-10-11 (before: 2025-07-20). Drag results for dates after
  2025-07-20 change, since measured solar activity replaces forecasts.
- Installers and CI install the tested dependency versions from
  `packaging/constraints.txt` (Basilisk 2.12.0, PySide6 6.11.2, ...).
- `validate` prints the GUI's plausibility warnings as `WARNING:` lines.
- The CLI exits with 130 on Ctrl-C and 3 on a file-system error, with a
  message instead of a traceback.
- Log files carry the process id, and only the newest 100 are kept.
- A heliocentric run is accepted with SRP or power; only the other
  tracked bodies cast shadows.
- A new look (IBM's Carbon design: IBM Plex fonts, flat panels).
- Templates fly 100 to 500 kg spacecraft; the CubeSat presets were
  replaced by 150, 300 and 500 kg buses.
- Templates use AD10's operations drag coefficient, 3.0.
- Script blocks in a Mission Sequence ask before they run; conditions no
  longer use Python's `eval()`.
- The mouse wheel no longer changes values in forms.
- `spacemissionstudio --help` opens with what the tool does and a few
  examples, instead of a paragraph about the code.

**Fixed** (the main ones; `HISTORY.md` and `AUDIT.md` list every one)
- The magnetic field was evaluated at 2019 whatever the scenario epoch.
- A Monte Carlo batch could hang after an earlier run in the same
  process; the GUI could show a previous batch as the new one.
- Wheel or thruster settings Basilisk exits on, and a failed Vizard
  download, could leave the GUI stuck at "Running..." or a dialog open.
- GUI Save reported nothing when the file could not be written; saves
  are now atomic.
- Report series of ground-station access were refused; a `...Z` epoch
  only half worked.
- Station keeping logged "propellant depleted" every step; it now warns
  once, also in the results.
- Bad data files, an unwritable home folder and non-UTF-8 files give
  messages instead of tracebacks.
- SIL on Windows could lose the flight software's last error message.
- Vizard re-sent earlier runs' instrument settings within one session.
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
