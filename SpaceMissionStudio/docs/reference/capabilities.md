# Capabilities and verification

Everything SpaceMissionStudio can do, mapped to the Basilisk modules that
do it, and what has been verified.

## Contents

- [Capabilities](#capabilities)
  - [Scenario model & data](#scenario-model--data)
  - [Orbital dynamics & propagation](#orbital-dynamics--propagation)
  - [Attitude, sensors & actuators](#attitude-sensors--actuators)
  - [3D spacecraft models](#3d-spacecraft-models)
  - [Flight-software export](#flight-software-export)
  - [Software in the loop](#software-in-the-loop)
  - [Mission planning](#mission-planning)
  - [Mission analysis](#mission-analysis)
  - [Automatic Sun-pointing / ground-station-pointing attitude switching](#automatic-sun-pointing--ground-station-pointing-attitude-switching)
  - [Orbit maintenance](#orbit-maintenance)
  - [Fuel tank](#fuel-tank)
  - [Vizard visualization](#vizard-visualization)
  - [Reusable starting points](#reusable-starting-points)
  - [Safe cancellation](#safe-cancellation)
  - [Long runs and end of life](#long-runs-and-end-of-life)
  - [Propellant budgets (ESA AD10 style)](#propellant-budgets-esa-ad10-style)
  - [GUI & CLI](#gui--cli)
- [Verification status](#verification-status)

## Capabilities

What's actually implemented, grouped by concern. The design rationale,
and the order each feature landed in, are in
[`HISTORY.md`](../../HISTORY.md).

### Scenario model & data

A versioned, human-readable JSON format
(spacecraft, orbit ICs in three forms -- classical elements with true or
mean anomaly, Cartesian, TLE --, gravity, ground stations, space
weather, sim settings, Monte Carlo dispersions, a GMAT/FreeFlyer-style
**Mission Sequence**), hand-written validation with specific error
messages, a schema-migration registry, and reference-integrity checking
(rename a spacecraft and every reference to it updates atomically;
deleting one that's still referenced is refused, listing exactly what
references it). No third-party schema library.

### Orbital dynamics & propagation

Central-body point-mass or Earth
spherical-harmonics gravity plus third-body point-mass perturbers,
atmospheric drag (Earth-only; a choice of NRLMSISE-00 or a simple
exponential model -- see `SpaceWeatherConfig.atmosphere_model`'s own
docstring for why not Jacchia-Roberts too: Basilisk has no such model)
and SRP (per spacecraft, on that spacecraft's own "Orbit / mass" tab),
a selectable integrator (`euler`/`rk2`/`rkf45`/`rkf78`), and osculating
Keplerian elements computed and exported alongside inertial
position/velocity at every sample -- plus, when a real J2 term is
actually modeled (Earth with spherical-harmonics degree >= 2), MEAN
(first-order-J2, osc -> mean) elements alongside the osculating ones,
via Basilisk's own `orbitalMotion.clMeanOscMap` (the same tool its
`meanOEFeedback` FSW module uses -- not a bespoke implementation).
NRLMSISE-00 drag takes its solar activity at one of three levels:
nominal (NASA MSFC's 50th-percentile prediction), conservative (its 95th
percentile, ESA AD10's operations case) or low (its 5th). The
conservative case follows the predicted solar cycle; it is not a
constant.

### Attitude, sensors & actuators

Every `fsw_mode` maps to a real
Basilisk FSW module chain (attitude nav/guidance/control), idealized or
real reaction-wheel actuation, and star tracker/IMU/coarse-sun-sensor/
magnetometer sensors (magnetometer is Earth-only). A `"thermal"` sensor
(`sensorThermal.SensorThermal`) models the real temperature of any
flat-plate component -- radiative absorption/emission driven by the
actual simulated attitude and (when shared with a power/eclipse-aware
spacecraft) real eclipse state, plus an optional internal power draw --
with its own measurement noise/bias/fault layer
(`tempMeasurement.TempMeasurement`). `"reaction_wheel"` actuators
separately gain an OPTIONAL per-wheel motor-thermal model
(`motorThermal.MotorThermal`, motor inefficiency/friction heat vs.
ambient dissipation) via the `motor_thermal_*` params. See template 20.
Deployed solar arrays can be flexible (`SpacecraftConfig.solar_arrays`):
each is a panel on a spring-damper hinge
(`hingedRigidBodyStateEffector`), whose swinging acts back on the
attitude and whose cells feed the power budget at the panel's own
deflected attitude. See template 27 and the User Manual, section 6.

### 3D spacecraft models

A spacecraft can carry a 3D model (`SpacecraftConfig.model`) built from
boxes, n-sided prisms (an octagonal bus), cylinders, cones, spheres and
thin panels, and from the groups of imported `.obj` files. Its mass,
center of mass and inertia are computed from the parts (or typed in, or
read from a JSON or CSV file), its parts' outer faces become the drag and
solar-pressure facets, and Vizard draws it. The center of mass is
Basilisk's hub offset (`hub.r_BcB_B`), so drag, sunlight and thrust act
about it, not about the body origin. The **3D model editor** shows the
model as it is built; `spacemissionstudio model` reports, applies and
exports it. See template 28 and
[Build a 3D model](../user-manual/3d-model.md).

### Flight-software export

The Flight Software tab and
`spacemissionstudio export-fsw` write a spacecraft's attitude flight
software as a standalone C99 project (`spacemissionstudio.fsw_export`):
the Basilisk C modules it runs, copied unchanged from Basilisk 2.12.0,
every parameter traced to its scenario field and GUI control, a
scheduler, a CMake build of a static library and a host program, an
interface control document, and unit and replay tests recorded from the
simulation. Every attitude template's export builds and reproduces the
simulation's flight software exactly (GCC and Clang, Linux). The scenario
records each export and flags it stale when its flight-software settings
change. User Manual section 6, "Exporting the flight software".

### Software in the loop

Run in SIL mode, or Run SIL... on the Flight Software page (or `spacemissionstudio sil`)
flies a spacecraft with an external flight-software program in
lock-step, over a versioned transport contract (`SIL_CONTRACT.md` in each export, a
local socket), and compares every command with the simulation's own
modules: per-signal residuals, round-trip and execution time, jitter,
dropped steps (`spacemissionstudio.sil`). Each export includes the host
harness and an adapter template for third-party C flight software. The
exported flight software in the loop reproduces the normal run bit for
bit. User Manual section 6, "Running the flight software in the loop".

### Mission planning

A GMAT/FreeFlyer-inspired Resources / Mission
Sequence / Output architecture: `propagate` (duration, epoch, or
event stop conditions: periapsis, apoapsis, or the start/end of the next
ground-station pass), `maneuver` (impulsive
delta-V, inertial/VNB/RTN), `lambert_transfer` (solves for the
impulsive delta-V that reaches a target position after a given time of
flight, via Basilisk's own `lambertPlanner`/`lambertSolver`/
`lambertValidator`), `assignment`, `report`, `if`/`while`
conditionals, and `script_block` commands, run by a real execution
engine (`engine.mission_engine.MissionEngine`) with a dedicated GUI
editor and output console.

### Mission analysis

Ground-station access analysis (has-access,
slant range, elevation, azimuth per station/spacecraft pair), a real
power budget (solar panel/battery/eclipse, driven by actual simulated
attitude and eclipse state, not a flat duty cycle), a downlink RF
link-margin estimate evaluated against real simulated slant range,
onboard data handling (instruments filling a memory and a transmitter
emptying it while the link to a station closes, with a patch antenna's
gain pattern applied to the real attitude; template 26, User Manual
section 6), and
Monte Carlo batch analysis (`Basilisk.utilities.MonteCarlo`: dry mass,
attitude, orbital elements, inertia, body rate, drag and SRP
coefficients), shown in the GUI's Monte Carlo tab (each run, the spread
along, across and out of the orbit, and a table of what each run drew).

### Automatic Sun-pointing / ground-station-pointing attitude switching

`SpacecraftConfig.comms_pointing` (`engine.fsw.build_comms_pointing`): a
small arbitrator `SysModel` that holds a spacecraft Sun-pointing (for
solar-panel power generation) by default, and switches it to point a
body-fixed antenna boresight at a named ground station instead, entirely
driven by that station's own REAL `groundLocation.GroundLocation` access
state -- never a manually-specified time window. Only the attitude
REFERENCE switches; the spacecraft's own integrated attitude state is
untouched, so the existing closed-loop `mrpFeedback` controller physically
slews across the transition rather than snapping instantly. An optional
`comms_power_w` draws extra battery power only while actually
ground-station-pointing, and `RFLinkConfig.antenna_beamwidth_deg` (when
set) feeds the spacecraft's own, actually-achieved pointing error into
`engine.link_budget`'s margin calculation as a parabolic-pattern
antenna-pointing-loss term -- so the link margin, gated on both real
access AND the spacecraft having actually switched modes, can show a
real "geometrically visible but not yet actually linked" period right at
each transition. See template 19.

### Orbit maintenance

Altitude/semi-major-axis station-keeping, GEO
east-west (longitude box) and north-south (inclination limit)
station-keeping measured in Earth's own rotating frame, and
constellation-wide phasing maintenance, both with real delta-V/
propellant bookkeeping (rocket-equation mass depletion fed back into
simulated spacecraft mass every tick) and eclipse-gated burns; a
constant-frame (VNB/RTN) continuous-thrust maneuver mode; a
Walker-pattern constellation generator (satellite count, planes,
phasing factor, altitude, inclination -> a full set of spacecraft with
pre-computed orbital elements); a **Generate phasing formation...**
wizard (`engine.formation`) that turns an existing chief spacecraft plus
a desired Radial/Transverse/Normal (Hill-frame) offset at epoch into a
new follower spacecraft with `phasing_keeping`/`station_keeping`
pre-wired -- the along-track (T) component becomes the actively-held
separation target; radial/cross-track (R/N) only set the follower's
starting geometry, since the phasing controller has no radial/
cross-track control authority (the wizard says so up front).

### Fuel tank

Real propellant depletion for `"thruster"` actuators
(`SpacecraftConfig.fuel_tank`, `engine.fsw.build_fuel_tank`): Basilisk's
own `fuelTank` state effector (`FuelTankModelUniformBurn`), tied to the
thruster hardware so it reads the SAME mass-flow rate the thruster
itself already computes (`mDot = F / (steadyIsp * g0)`) -- a materially
different, more physical mechanism than the orbit-maintenance
bookkeeping above (which is a hand-rolled Python estimate specific to
station-keeping/phasing/constant-thrust burns); this one is Basilisk's
own effector, including the resulting center-of-mass shift as
propellant depletes.

### Vizard visualization

Live-stream or `.bin` playback file, an
Earth-centered default camera view with orbit trace lines, live
data panels (battery charge, station-keeping propellant remaining,
delta-V used -- station-keeping and phasing-keeping reported as separate
panels, since both draw from one shared tank -- for a phasing formation,
the real chief/follower offset broken out into Radial/Transverse/Normal
panels (the same R/T/N terms the phasing-formation wizard itself uses,
not an abstract single number), ground-station access-window indicators,
and -- for a `comms_pointing` spacecraft -- a pointing-error bar plus
"Mode"/"Link status" badges mirroring the Mission Dashboard's own live
GUI telemetry -- all driven by real, already-simulated values, not
static snapshots, with Vizard's own native live current/max readout on
every panel), custom 3D models per spacecraft (a file of your own, cosmetic only, or the spacecraft's [3D model](#3d-spacecraft-models)), and a **Launch
Vizard** action that starts the external application itself (if it
cannot find Vizard, it offers to download AVS's own pre-built binary
when you click **Download Vizard**), not just configures what feeds
it.

### Reusable starting points

Four spacecraft "bus" templates
(100 kg ESPA-class, 150 kg microsatellite, 300 kg and 500 kg small
satellites) and
twenty-eight complete example scenarios: most cover one concept each,
several integrate a whole system, and four are starting points for your
own mission (the [template catalog](../../spacemissionstudio/scenarios/templates/README.md)).
Five Python scripts in [`examples/`](../../examples/README.md) use the
same layer from code.

### Safe cancellation

**Cancel** (`Esc`; **Run > Cancel Run**) cooperatively cancels an
in-progress run (or Mission Sequence, or SIL run; not a Monte Carlo
batch, which Basilisk's Controller cannot stop part way) between
simulation chunks or commands, keeping whatever partial results were
already produced -- never a forced kill that could leave Basilisk's C++
state mid-mutation.

### Long runs and end of life

Runs of up to about 10 years, chained
past Basilisk's ~104-day limit, with a "Record every" setting to keep
them in memory; and an **End of Life** tab (and `spacemissionstudio
lifetime`) estimating when a spacecraft re-enters, with or without a
deorbit burn, checked against the 5- and 25-year disposal rules. The
estimate agrees with full Basilisk decay runs to within ~2% in seconds.

### Propellant budgets (ESA AD10 style)

A Budget tab and
`spacemissionstudio budget`: delta-V and propellant per mission phase with
the guideline's margins, residuals and iteration, simulated orbit control
taken from the last run (or estimated from the drag), the disposal burn
sized for a 5-year lifetime, and a launch-delay sweep for launches up to
5 years late (`budget --launch-delays`), and an altitude trade of that
sweep against the tank (`budget --altitudes`, in parallel processes); solar activity from NASA MSFC's
prediction at the 95th/50th percentile. Templates use AD10's operations
drag coefficient, 3.0.

### GUI & CLI

A full PySide6 desktop shell (scenario editor,
Monte Carlo, live progress feedback, a real visual theme/icon/
toolbar) and an equivalent headless CLI (17 commands; see
[Use the command line](../user-manual/command-line.md)), both built on
the exact same `schema`/`engine` layer -- neither is a thin wrapper
around the other. Result plots are Plotly figures (a validated,
colorblind-safe categorical palette; a unified hover tooltip; plain
decimal axis ticks -- never matplotlib's scientific/offset notation)
rendered in an embedded `QWebEngineView`, with the epoch/elapsed-time
x-axis toggle and per-series km-unit conversion described above still
applying unchanged; see `results_widget.py`'s own module docstring for
why `QWebEngineView` over a static image, and "Verification status"
below for this migration's one open packaging caveat. A "Mission
Dashboard" tab (`mission_dashboard_widget.py`) shows the same live run
as a set of grouped status readouts (operating state, attitude, power,
RF link) instead of a plot, for a `comms_pointing`-configured
spacecraft -- fed from the exact same `RunWorker.progress`/
`finished_ok`/`cancelled` signals the Results tab already uses, so it
updates live during a run with no extra plumbing.

## Verification status

What has been run, and where. The detailed records are in
[`compliance/`](../../compliance/README.md): the software verification
report, the validation runs against GMAT, IERS and SOFA, and the
compliance matrix.

- **Every commit to the tool is tested in CI** (GitHub Actions), with
  Basilisk 2.12.0 installed and the reference data fetched:
  - on Ubuntu 24.04: lint, the full test suite with coverage (at least
    90 % of statements and 80 % of branches, enforced), the offline tests
    with no network at all, and the document and traceability checks;
  - on `windows-latest` and `macos-latest`: the full test suite.
- **The GUI is tested for real**, headless, with `pytest-qt`: forms,
  menus, dialogs and the plots in their embedded web view.
- **Template claims are re-checked.** `tests/test_template_claims.py`
  runs templates 03, 07, 08, 10-14, 16, 17, 19-24 and 26-28 in Basilisk and
  checks the headline numbers their descriptions quote; template 25 runs
  in `tests/test_examples.py`.
- **Long runs**: a real 5-year LEO station-keeping run and a 7-day run of
  template 05 with live Vizard were run to completion.
- **Packaging**: the Linux `.deb` and `install.sh` were built and
  installed end to end with Basilisk on Linux; the released 3.0.0 `.deb`
  was installed by hand on Ubuntu 24.04, where the GUI started and
  template 22 ran. The Windows setup program
  is built, installed and run in CI on a Windows runner, but not yet
  tried by hand; `install.ps1` has not been run;
  [`packaging/README.md`](../../packaging/README.md) says exactly what was
  run where. On a minimal Linux install, the plots' web view needs extra
  system libraries ([Troubleshooting](../troubleshooting.md#the-results-plot-stays-blank)).

---

**Next:** [Known limitations](limitations.md) ·
[Data, standards and the offline policy](data-and-standards.md) ·
[Documentation index](../README.md)
