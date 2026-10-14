# Changelog

What changed in SpaceMissionStudio, release by release, newest first.
Each entry is a short summary; [`HISTORY.md`](HISTORY.md) has the full
story behind every change (why, how it was found, how it was tested).

The version follows [semantic versioning](https://semver.org): a major
version breaks something you rely on, a minor one adds features, a patch
fixes bugs.

## 1.0.0 (2026-10-14)

The first release of the renewed SpaceMissionStudio. The version numbers
used before the renewal are withdrawn; how the tool got here is in
[`HISTORY.md`](HISTORY.md).

**What it does** (details: [Capabilities](docs/reference/capabilities.md))
- **Scenarios** in a versioned JSON format, edited in a tree of forms
  that check values as you type and name each problem by its form label;
  28 templates to start from, from a blank scenario to formations, a
  constellation and an octagonal bus built from a 3D model.
- **Simulation on Basilisk 2.12.0**: orbit or full attitude; gravity
  fields, third bodies, drag (NRLMSISE-00 driven by real space weather
  only: CelesTrak's observations and forecast, then NASA MSFC's
  prediction), solar pressure, faceted drag and pressure, flexible solar
  arrays, fuel tanks, sensors and actuators from a catalogue of real
  devices, attitude determination and control, power, sensor
  temperatures, and data handling with ground-station links.
- **Mission design**: a Mission Sequence (propagate, burns, stop
  conditions, reports), station keeping (LEO altitude, GEO longitude and
  inclination), formation flying with Basilisk's formation modules,
  Walker constellations, Lambert transfers, TLE import with SGP4, and
  CCSDS orbit data messages (OPM, OMM, OEM) in and out.
- **Analysis**: plots in a grid with a shared time cursor, events
  (passes, eclipses, burns, modes) on a timeline, run history and run
  comparison, Monte Carlo batches with their statistics, long runs past
  Basilisk's 104-day limit, end of life and deorbit checks, and ESA
  AD10-style delta-V and propellant budgets with launch-delay and
  altitude trades.
- **3D spacecraft models** built from shapes or `.obj` files, giving the
  mass, center of mass, inertia, drag and pressure facets and the
  Vizard look.
- **Flight software export** of the simulated flight software as C, and
  **software in the loop** against your own flight software over a
  documented link.
- **Vizard** visualization, live or saved.
- **The app**: light and dark themes, use by keyboard alone, layouts for
  wide screens, a bundled user manual, and a command line
  (`spacemissionstudio`) for everything that runs without the window.
  Offline by design: nothing is downloaded without your consent.

**Platforms**
- **Linux**: this release. The `.deb`, the wheel and `install.sh` are
  verified (see [`packaging/README.md`](packaging/README.md)).
- **Windows and macOS**: the test suite runs in CI on both. Not yet
  fixed: two intermittent test failures on Windows (an altitude-trade
  worker's error that does not reach the main process, and a software in
  the loop timing test with too small a margin), and on macOS two
  wide-screen layout tests that get a window no wider than the runner's
  screen. Installers for them
  follow in a later release; until then, install from source
  ([Getting started](docs/getting-started.md), path C).

**Coming from a build before the renewal** (3.0.0 or earlier): `pip` and
`apt` see 1.0.0 as older, so remove the old one first
(`sudo apt remove spacemissionstudio`, or `pip uninstall
spacemissionstudio`). Scenario files from it open unchanged.
