# Changelog

What changed in SpaceMissionStudio, release by release, newest first.
Each entry is a short summary; [`HISTORY.md`](HISTORY.md) has the full
story behind every change (why, how it was found, how it was tested).

The version follows [semantic versioning](https://semver.org): a major
version breaks something you rely on, a minor one adds features, a patch
fixes bugs.

## 1.1.0 (2026-10-20)

Formations in relative orbital elements, navigation from a camera
(around Mars, and around asteroid Eros from its landmarks), Eros itself,
reflected sunlight on the sun sensors and Mars's gravity field, plus
fixes found along the way. Scenario files of 1.0.0 open unchanged, and
`apt` and `pip` upgrade 1.0.0 in place. 31 templates (three new: 29, 30,
31). Linux, like 1.0.0. Details below, newest first; the full story of
each is in [`HISTORY.md`](HISTORY.md).

- **Monte Carlo from the GUI works with one thread.** With `thread_count`
  1, the default and template 09's setting, every run of a GUI batch
  failed ("signal only works in main thread"). Basilisk's Monte Carlo
  controller needs a main thread, and the GUI ran the batch on a worker
  thread. The GUI now runs the batch in a child process. The command line
  was not affected (it runs on its main thread), and batch results are
  unchanged.
- **Bundled space weather refreshed:** CelesTrak's observations to
  2026-10-18 and its daily forecast to 2026-12-02 (was: to 2026-10-11).
  Drag runs dated after 2026-10-11 change slightly.
- **The command line refuses `nan` and `inf`** for every number option,
  with a usage message; some of them ended in a Basilisk traceback.
  `generate-roe-formation --safe` refuses negative sizes.
- **The spacecraft editor's Power tab fits a 1280 px window** with an ROE
  formation (it scrolled sideways).
- **Mars gravity field.** Spherical-harmonics gravity now works around
  Mars too, with the GGM2B field from Basilisk's data up to degree 80
  (gravity settings: **Enable spherical-harmonics gravity (Earth, Mars)**).
  Every field now uses the reference radius of its own file: Basilisk
  put the planet's radius in its place, which made Mars's J2 0.05 % too
  weak (Earth's 1e-7). A 400 km Earth orbit with a degree-20 field
  moves by about 0.16 m in a day.
- **Albedo on the sun sensors.** With **Reflected sunlight on the sun
  sensors** (gravity settings), coarse sun sensors around Earth or Mars
  also see the sunlight the planet reflects, from Basilisk's albedo module
  with the measured CERES (Earth) or TES (Mars) albedo map. An
  Earth-facing sensor can see a quarter of the direct sunlight; in
  template 14 it pulls the estimated Sun direction about 16 deg off.
  Each sensor's albedo is plotted.
- **Sun sensors are dark in eclipse.** Coarse sun sensors read the Sun
  through the Earth in its shadow, and the sun heading estimated from them
  stayed right. They now read zero there, as real sensors do: the
  estimate is lost in the shadow and back when the spacecraft leaves it.
  Template 14 now runs for a whole orbit and shows this.
- **Thermal sensors away from Earth.** A thermal sensor took the
  sunlight at Earth's distance from the Sun whatever the spacecraft
  orbited, so around Mars it absorbed about twice the real sunlight, and
  around Venus too little. It now takes the sunlight at the spacecraft's
  own distance from the Sun. Runs around Earth and the Moon are
  unchanged.
- **Asteroid 433 Eros as a central body.** Its real position (a JPL
  Horizons solution from NAIF, 1900 to 2100), its 5.27 h rotation and,
  with **Gravity from the shape model**, the gravity of its NEAR shape
  (Basilisk's polyhedral gravity) instead of a point mass. Download the
  two files in Reference data (**Small bodies**). Positions are also given
  in Eros's frame, and an orbit into the asteroid is reported as an impact.
- **Landmark navigation.** A spacecraft around Eros can carry a camera
  that sees landmarks on the surface (Basilisk's `pinholeCamera`), and a
  Kalman filter estimates its orbit from their pixels. New template 31:
  from 100 m off to 0.35 m (median) in a 35 km orbit. A how-to page
  explains the settings and the results.
- **SIL runs no longer stop when the simulator itself stalls.** A send to the
  flight software gave up as soon as its time ran out, even when the flight
  software was taking data and only the simulator had been slow (a loaded
  computer, a debugger). It now counts from the last data taken and tries once
  more before reporting that the flight software took nothing.
- **Optical navigation.** A spacecraft can carry a camera that sees the
  central body (Earth, Mars or Jupiter) and estimate its own orbit from
  where the planet's disk falls in each image and how large it is, with
  Basilisk's `pixelLineConverter` and `relativeODuKF`. Images from the night
  side are left out. New template 30 navigates around Mars: from 68 km off
  to within 2 km in a day. A how-to page explains the settings and the
  results.
- **Template 29's note** no longer says the ROE guidance has no
  differential drag: it compensates it now (below).
- **Runs around Mars and Jupiter work.** A scenario around `mars` or
  `jupiter` (or with them as third bodies) passed its checks and then
  failed: around Mars the whole app closed. The bundled planet ephemeris
  has the Mars and Jupiter system barycentres only, so the app now offers
  **mars barycenter** and **jupiter barycenter** and tells you to use them
  when a file names the old ones.
- **ROE formations compensate differential drag.** When a follower feels
  more or less drag than its chief, the impulsive law measures how fast
  their relative semi-major axis decays and sets it so the along-track
  offset swings evenly about its target between corrections. With three
  times the chief's drag area, a 3-day hold stays within 13 m along-track
  (27 m before) for half the burns and less delta-V. On by default
  (**Compensate differential drag**); twin spacecraft fly as before. The
  Explain tab says when a follower's drag differs from its chief's.
- **ROE formations in Vizard.** A follower in an ROE formation gets live
  panels for its delta-V, its radial, along-track and cross-track
  separation from the chief, and its closest radial/cross-track
  approach.
- **Altitude trade errors keep their message.** When Basilisk stopped
  one of the parallel workers with an error, the trade failed with a
  pickling error that hid it. It now names the altitude and Basilisk's
  message. Two workers writing the same space-weather window no longer
  replace each other's file.
- **Relative orbital elements (third part): the generator, the diagram
  and template 29.** **Generate ROE formation...** under the Spacecraft
  list adds a follower placed on a passively safe helix or on six typed
  ROE, with the closest approach shown as you type. The Explain tab draws
  each target's eccentricity and inclination vectors and the path around
  the chief. New template 29 moves a follower from 2 km behind its chief
  to a passively safe 300 m helix. A how-to page, a User Manual section
  and glossary entries explain ROE and passive safety.
- **Relative orbital elements (second part): ROE formations fly.** A
  follower holds, or moves between, its ROE targets with either law:
  - *impulsive*: the tool's own guidance plans along-track and
    cross-track burns with the J2 model, avoids eclipse, splits long
    burns, and drifts to the along-track offset, gliding in so it does
    not overshoot;
  - *continuous*: Basilisk's `meanOEFeedback` with the ROE target as its
    element target (default gain 25000; phasing keeping's 2500 lets
    metre-scale errors grow).

  Results gain `{spacecraft}.roe_formation.*` series, the Events tab
  shows ROE burns and drifts, the budget counts their delta-V as
  formation keeping, and Explain describes each target and its
  passive-safety margin. New command `generate-roe-formation` places a
  follower at the requested ROE from the chief's mean elements.
- **Relative orbital elements (first part):** a follower's scenario
  file can describe a formation in quasi-nonsingular relative orbital
  elements (ROE, in metres), with a schedule of targets, and the
  spacecraft editor has a form for it with a passively safe formation
  helper. The math (the J2 state transition matrix, the impulsive burns,
  the passive-safety margin) is in place and tested.
- **Documentation brought up to date with the app:** menu, tab and page
  names (End of Life, Budget and Flight Software are pages under
  Analyses and Tools; the Data tab is now the Reference data dialog;
  Monte Carlo runs from the run mode beside Run), the template count
  (then 28), sample command output, and the records of the published 1.0.0
  release.
- **Messages and tooltips** that named the old Data tab or Run Monte
  Carlo... now name the Reference data dialog and the Monte Carlo run
  mode.

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
