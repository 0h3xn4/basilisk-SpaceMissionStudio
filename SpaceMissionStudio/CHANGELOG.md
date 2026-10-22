# Changelog

What changed in SpaceMissionStudio, release by release, newest first.
Each entry is a short summary; [`HISTORY.md`](HISTORY.md) has the full
story behind every change (why, how it was found, how it was tested).

The version follows [semantic versioning](https://semver.org): a major
version breaks something you rely on, a minor one adds features, a patch
fixes bugs.

## Unreleased

- **A new shell: a navigation rail instead of menus and toolbars** (UI
  overhaul M2a). The window has no menu bar and no toolbar any more:
  - **The rail** on the left holds the areas: **Home** (Start from
    scratch and the templates), **Scenario** (the scenario tree),
    **Run** (the run controls, End of Life, Budget and the Log),
    **Results** (Plots, Dashboard, Output, Monte Carlo and Compare),
    **Timeline** (the events), **Reports** (Flight Software), and at the
    bottom **Settings** and **Help**. `Ctrl+1` to `Ctrl+6` open the six
    areas; the rail's last button shows them as icons only.
  - **The top bar** has the scenario's name and state, where you are
    ("Scenario › Spacecraft › sat-1"), Undo and Redo, a save button that
    shows the save state, **Run** with its mode, and the search field of
    the command palette.
  - **Every command** is in one registry: the command palette (`Ctrl+K`),
    the area headers, the top bar, the shortcut list and every tooltip
    ("Save (Ctrl+S)") come from it. The palette also finds a command by
    its old name ("events" finds the Timeline), the spacecraft and
    ground stations, and the Settings sections.
  - **Settings** holds the theme, the reference data, the layout, the
    keyboard shortcuts (`Ctrl+/`) and About; they were in the View and
    Help menus.
  - New shortcuts: `Ctrl+I` the Inspector, `Ctrl+J` Problems.

  The screens themselves are unchanged; what a run computes and every
  file the app writes are the same. Two engine messages still name
  "Tools > Reference Data": the palette finds that command by that name.

- **Problems at the bottom, the run in the status bar** (UI overhaul M2b):
  - **The Problems panel** is a table at the bottom of the window
    (`Ctrl+J`): severity, the field it is about, the object (scenario,
    spacecraft, ground station, ...) and the message. Errors come first,
    a column heading sorts by it, `Ctrl+C` copies the selected rows, and
    `Enter` or a double-click goes to the field. The status bar always
    counts the errors and warnings, and the top bar shows the count while
    there are any; a click on either opens the panel.
  - **The run** shows in the status bar: what it is doing, its progress,
    the time so far and left, **Cancel** (`Esc`) and its state ("Run 2:
    done in 6 s").
  - **Inspector and Explain** are two panels on the right, one above the
    other, instead of tabs. `Ctrl+I` shows and hides the Inspector.
  - **The layout is kept for each scenario file:** the panels, the rail
    and the dividers come back when you open the file again.

  A layout saved by an earlier version is ignored once.

- **Home: template cards, recent scenarios, no start-up dialog** (UI
  overhaul M3):
  - **A card per template** says what the template is, all read from
    the template file: Orbit only or Full attitude (with its pointing
    mode) and how many spacecraft; the central body and the orbit
    ("Earth · 550 km circular · i 97.6 deg · Sun-synchronous"); and the
    first sentence of its description. A filter narrows the cards. Click
    a card for its whole description, with **Open template** and
    **Customize...**; each card has its own **Open** and
    **Customize...** too. The keyboard reaches the cards with `Tab`, the
    arrow keys move between them and `Enter` opens one.
  - **Recent scenarios:** the last 10 scenario files you opened or saved,
    newest first. A file that was moved or deleted is marked
    "(missing)". `Delete` takes one off the list and **Clear** empties
    it.
  - **New blank scenario** and **Open a scenario file...** are beside
    them.
  - **No dialog at start-up:** the question whether to fetch or update
    the reference data is a card at the top of Home, with the same
    choices. **Fetch now** downloads while you carry on; **Not now**
    downloads nothing.
  - Templates 22, 26 and 29 named the Events tab in their descriptions;
    they name the Timeline now.

  What a run computes and every file the app writes are the same.

## 1.2.0 (2026-10-21)

Starting a mission from an empty scenario is now a choice of its own: the
Templates page opens with a blank scenario, and its Scenario page shows
the steps to a first run and everything else the tool does, each with a
button to where it is set. The calculations are unchanged, so scenario
files and their results are the same as with 1.1.1. The installers are
built as 1.1.1's were, with the same Python, Basilisk and space weather;
the Earth orientation files in them are as current as their build.

SpaceMissionStudio supports Linux and Windows. macOS, which never had an
installer, is no longer supported.

- **Starting a mission from scratch, guided.** The Templates page now
  opens with **Start from scratch** (**New blank scenario**), above the
  templates; before, an empty scenario was only File > New Scenario. A
  blank scenario starts in *Orbit only*, the simplest mode, and its
  Scenario page has a **Build your mission** guide:
  - the steps to a first run (Scenario, Environment, Spacecraft, Ground
    stations, Run), each with its state (*Needed*, *Optional*, *Done*,
    *Ready*) and a button to its page;
  - **There is more**: Full attitude (with **Switch to Full attitude**),
    the mission sequence, constellations and formations, Monte Carlo, the
    analyses, other central bodies and the worked examples, each with a
    button to where it is.

  The guide is open for a scenario without spacecraft and folded (**Show
  guide**) for an opened one. The Spacecraft page says what to do while
  it has no spacecraft, with **Add...** as its primary button, and Edit
  and Remove wait for a selection. A hint that pointed to a "Spacecraft >
  Add..." menu, which does not exist, now names the Spacecraft page.
- **macOS is no longer supported.** SpaceMissionStudio runs on Linux and
  Windows. The macOS CI job and the release workflow's macOS check are
  gone, and so is the app's macOS-only code: downloading Vizard for
  macOS and starting it from its `.app` bundle. The documents now name
  Linux and Windows only (`docs/DECISIONS.md`, "macOS removed").
- **Clearer release notes.** A release draft now opens with what the
  release is for, then who should update, the downloads with their sizes,
  how to install or upgrade on each system, how to check a download (with
  the installers' SHA-256), what is new, what the installers contain, how
  the files were checked, and the known limits. Before, it was the
  CHANGELOG entry under a few file lines. Written by
  `packaging/release_notes.py` (`docs/developer/releasing.md`).

### Who should update

- Anyone who builds missions from an empty scenario: the guide shows the
  steps and the rest of the tool.
- Everyone else when convenient: nothing 1.1.1 computes changes. On
  Linux, `apt install ./spacemissionstudio_1.2.0_amd64.deb` replaces the
  1.1.1 package (1.1.1 was tested offline the same way over 1.1.0). On
  Windows, run the 1.2.0 setup over 1.1.1.

### Known limits

- On Windows, a software-in-the-loop session that drops thousands of
  steps may stop with "the flight software took no STEP for 10 s". Seen
  only in CI, cause not known (SRelD K-14).
- A theme change takes about half a second, up to 2.4 s after every page
  has been visited (SRelD K-19).

## 1.1.1 (2026-10-21)

The installers bring everything with them; the app itself is unchanged,
so scenario files and results are the same as with 1.1.0. On Linux,
`apt install ./spacemissionstudio_1.1.1_amd64.deb` replaces the 1.1.0
package (tested offline over it, in a container); on Windows, running the
1.1.1 setup over 1.1.0 removes 1.1.0's environment first (not yet tried
on a Windows machine).

- **Self-contained installers.** The Linux `.deb` and the Windows setup
  program now bring their own Python 3.11 with Basilisk 2.12.0, PySide6
  and every other package, plus the support data (SPICE kernels, gravity
  fields, magnetic field model, albedo maps) and the Earth orientation
  files. Installing needs no Python on the computer and no internet: the
  1.1.0 setup program stopped with "needs Python 3.11 or later" when
  none was on `PATH`, and both 1.1.0 installers downloaded Basilisk and
  the data while installing. The `.deb` is now
  `spacemissionstudio_<version>_amd64.deb` (about 450 MB; 1.65 GB
  installed) and needs glibc 2.34 or newer (Ubuntu 22.04, Debian 12 or
  later). Built by `packaging/bundle_python.py`; the release workflow
  installs the `.deb` with the network cut off and runs it offline, and
  the Windows setup with an empty support-data cache.
- **A test fixed:** `test_autosave.py` failed now and then on Windows CI
  when an earlier GUI test had left a main window open: its autosave
  timer wrote into the recovery file the test had just pointed at a
  temporary folder. The test now stops such timers first
  (`docs/ui/TEST_CHANGES.md`).

## 1.1.0 (2026-10-20)

A new look whose theme switches live, formations in relative orbital
elements, navigation from a camera (around Mars, and around asteroid Eros
from its landmarks), Eros itself, reflected sunlight on the sun sensors
and Mars's gravity field, plus fixes found along the way. Scenario files
of 1.0.0 open unchanged, and `apt` and `pip` upgrade 1.0.0 in place. 31
templates (three new: 29, 30, 31). Linux, like 1.0.0. Details below,
newest first; the full story of each is in [`HISTORY.md`](HISTORY.md).

- **A new look, and the theme switches live (UI overhaul M1).** The IBM
  Carbon theme and IBM Plex are replaced by the token set of the overhaul
  brief (`docs/ui/UI_OVERHAUL.md`): neutral surfaces with one blue
  accent, Inter for the interface and JetBrains Mono for values and code
  (both bundled), Lucide icons tinted from the theme, 6 and 8 px corners,
  frameless group boxes. Status keeps one meaning (critical, serious,
  caution, normal, standby, off) and is always written out. Every text
  and icon colour passes WCAG 2.2 AA in both themes, tested. View > Theme
  now applies at once to every open view, plots included, instead of at
  the next start; with System it follows the desktop while the app runs.
  Plots take a template from the theme and a new eight-colour palette,
  checked for colour-vision deficiency between neighbouring series and
  kept apart from every status colour. Applying a theme takes 0.5 s on a
  new window and 2.4 s after every page has been visited (the earlier
  restyle: 1.3 s and 6.1-6.5 s on the same machine), not yet the brief's
  0.1 s; the overhaul's next steps reduce the number of live widgets
  (`docs/ui/UI_OVERHAUL_PLAN.md`). The layout, what the tool computes,
  its files and its command line are unchanged. Decisions:
  `docs/DECISIONS.md`; licences: `docs/THIRD_PARTY_ASSETS.md`.
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
