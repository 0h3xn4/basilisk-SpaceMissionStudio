# Changelog

What changed in SpaceMissionStudio, release by release, newest first.
Each entry is a short summary; [`HISTORY.md`](HISTORY.md) has the full
story behind every change (why, how it was found, how it was tested).

The version follows [semantic versioning](https://semver.org): a major
version breaks something you rely on, a minor one adds features, a patch
fixes bugs.

## Unreleased

**Breaking (2.0.0): Python 3.14 only.** SpaceMissionStudio now needs
Python 3.14; 3.11 to 3.13 are no longer supported (`requires-python =
">=3.14"`). The `.deb` and the Windows setup program bring their own
Python, now 3.14.8, so their users need do nothing. Installing from
source or with `install.sh`/`install.ps1` needs Python 3.14 on the
computer: Ubuntu 24.04 ships 3.12 and Debian 12 ships 3.11, so use the
`.deb` or a Python from python.org or `uv`. CI tests 3.14 only. Basilisk
2.12.0 and PySide6 6.11 do not install on 3.15 yet. The code was
modernised for 3.14 by ruff's upgrade rules (built-in generics, `X | None`,
`datetime.UTC`); nothing it computes changes.

- **A software-in-the-loop run on Windows no longer stops while the
  flight software is still answering:** when the flight software fell
  thousands of steps behind (steps past their deadline), the run could
  stop with "the flight software took no STEP for 10 s" although it was
  answering all the while: the send's time limit counted only bytes the
  program took, and Windows lets a full socket take nothing for longer.
  Bytes it sends now count too; a program that neither reads nor answers
  still stops the run after the step timeout.
- **The propellant budget no longer overestimates propellant:** each
  contributor took the phase's starting mass times `exp(dV / Ve) - 1`,
  the rocket equation's form for the mass *after* a burn. Each now takes
  the mass before it, `m * (1 - exp(-dV / Ve))`, in order. For 150 kg
  dry at Isp 220 s, a 100 m/s transfer was budgeted 5 % too high and a
  1 km/s transfer 2.5 times too high (232 kg, now 93 kg); from about
  1.4 km/s there was no total at all ("did not settle"). Every budget
  with a burn comes out lower; the larger the delta-V, the larger the
  change (5 % at 100 m/s). Found by the audit of 2026-10-27.
- **Lifetime, End of Life and the budget's disposal are right at the
  critical inclination:** the J2 mean elements they start from came from
  a first-order map that is singular at 63.435 deg and 116.565 deg. A
  600 km orbit there was reported to re-enter at once ("0.00 years,
  5-year rule: met"), and a Molniya orbit stopped with an error. The map
  is now blended from its values at the edges of a 1 deg band around
  those values: the same orbit stays up for over 30 years, as at 60 deg,
  and a 300 km decay at 63.435 deg is estimated at 34.8 days, as a full
  Basilisk run finds. The mean-element plots there are finite too. Results elsewhere are
  unchanged. Found by the audit of 2026-10-27.
- **Save no longer writes over a built-in template:** after opening a
  template from Home, **Save** (Ctrl+S) wrote to the template's own file
  (where the folder is writable: a Windows install, or from source). It
  now opens **Save As**, starting in the home folder under the
  template's name, and a save into the templates folder is refused. The
  User Manual already said a template is never overwritten. Found by the
  audit of 2026-10-27.
- **A run outside the Earth orientation files no longer ends the
  program:** a run whose dates the installed IERS files do not cover
  (an epoch before 1962, or after 2027 with only the high-precision file)
  stopped inside SPICE, taking the window and any unsaved edits with it.
  The files are now used only for a run they cover; otherwise the run
  uses the IAU model, and both **validate** and the run say so ("the
  installed IERS files cover 1962-01-19 to 2126-11-03, not this run"). A
  Mission Sequence that would propagate past the files' end stops with a
  message instead. Found by the audit of 2026-10-27.
- **Limits a shared scenario cannot get round:** an `if` or `while`
  condition can no longer format a text with `%` (a field width built a
  text of any length, up to gigabytes); `%` on numbers is still the
  remainder. A Monte Carlo batch is limited to 100 000 runs and 256
  processes, and uses at most one process per CPU (the Overview says so
  when it asks for more). Found by the audit of 2026-10-27.
- **The script-block consent shows all of the code:** **Run script
  blocks?** listed only the first 600 characters of each block, with no
  sign of the cut, and Yes ran all of it. **Show Details...** now lists
  every block in full, with its length and SHA-256.
- **Generated constellations and formations keep their spacing:** when
  the scenario's gravity includes J2 (degree 2 or more), **Generate
  Walker constellation...**, **Generate phasing formation...** and their
  command-line versions now place each satellite by its mean elements
  (stored as osculating elements with a true anomaly). With equal
  osculating elements, as before, two Walker satellites 90 deg apart at
  550 km closed to 76 deg in a day, and a 50 km phasing follower was at
  38 km. With point-mass gravity nothing changes. Templates 04 and 05
  are unchanged. Found by the audit of 2026-10-27.
- **Mean elements for equatorial orbits:** the J2 mean-element map no
  longer divides by zero at 0 deg inclination, and is continuous across
  the critical inclination.
- **Long dynamics steps are more accurate, and flagged:** the rkf45 and
  rkf78 integrators kept Basilisk's default error tolerance (relative
  1e-4), which let a long step through unchecked: a one-day two-body
  orbit was 384 m off Kepler's solution at a 300 s step and 173 km at
  1800 s. They now work to a relative error of 1e-10 (11 m and 8.6 km),
  and the run's provenance records both tolerances. Above a 60 s step the
  rest of the error comes from what is refreshed only once per step, so
  Explain and `validate` now warn there. Found by the audit of
  2026-10-27. 28 of the 31 templates give the same results to the last
  digit; the three that fire attitude thrusters (11, 12, 17) change.
  Their 20-40 ms pulses fall inside a 0.5-1 s step, and the default
  tolerance stepped over most of them: template 17's fuel tank drained
  0.3 g where it drains about 14 g (13.6 g at 1e-12), and its description
  now says so. 12's wheel speeds and 17's attitude are now closer to a run
  at 1e-12; 11 is as close as before.
- **Each sensor draws its own noise:** every sensor noise model kept
  Basilisk's default seed, so they all drew the same random sequence: two
  identical noisy sun sensors on one spacecraft gave identical readings
  (their noise correlated at 1.0), and the noise repeated across sensors,
  spacecraft and the segments of a long run. Each model now gets its own
  seed, derived from a new scenario setting, **Random seed**
  (`sim_settings.seed`, default 0), and its name; the twin sensors' noise
  now correlates at 0.03. The same scenario still gives the same run; a
  navigation error's own seed is kept. The run's provenance lists every
  seed. In the templates only noisy sensor readings change (07, 20, 23,
  26, 27, 28); everything else, the attitude included, is the same to the
  last digit. Two Monte Carlo batches still draw the same samples: that
  seeding is in Basilisk (known issue K-24). Found by the audit of
  2026-10-27.
- **Known vulnerabilities checked in CI:** the installers shipped
  certifi 2026.7.22 and pillow 12.2.0, which pip-audit matched to 1 and 52
  published advisories. certifi is now 2026.10.23, with none. pillow stays
  at 12.2.0: the qualified Basilisk (2.12.0) allows no later version. Its
  52 advisories are all about decoding a crafted image, and nothing in
  SpaceMissionStudio or the Basilisk modules it uses decodes an image
  with pillow (known issue K-25). CI now checks every pinned package, and
  every tool it runs, against those advisory databases and fails on any
  match not listed, with its reason, in `packaging/audit-exceptions.txt`;
  the tools themselves (pytest and its plugins, ruff, pip-audit,
  pre-commit) are pinned in `packaging/constraints-dev.txt`, and the main
  workflow is read-only. The release workflow runs the whole test suite
  on the tag before it attaches anything. The `.deb`'s copyright file now
  names each part it bundles with its own licence (CPython, Qt, the
  fonts, the icons, the reference data) and this repository as the
  source. Found by the audit of 2026-10-27.
- **Save from the unsaved-changes question:** closing, opening or
  starting a scenario with unsaved changes offered only Discard and
  Cancel; it now offers Save too (the default), which saves the scenario
  (asking where for one with no file) and then goes ahead. A cancelled
  Save As keeps the window and the changes.
- **A failed read of the reference data is reported:** if the start-up
  read of the reference data files failed, the Reference data panel kept
  "Reading the reference data files..." for good. It now says why, with a
  Retry button, and the status bar shows "Reference data: not read".
- **No held space weather after the Duration:** a Mission Sequence can
  run longer than the scenario's Duration, but the space weather its drag
  reads was loaded only for the Duration and 10 days either side. Past
  that, Basilisk held the last day's values, for as long as the run went
  on, with nothing in the results to say so (a 15-day sequence in a
  0.1-day Duration: 5 days on held values). Such a run now stops before
  it goes there, with a message to set the Duration to cover the
  sequence. Runs inside the loaded days, and every template, are
  unchanged.
- **The run's length with a Mission Sequence:** a sequence's steps, not
  the Duration, decide how long a run is, but Overview showed the
  Duration: template 23 said 2.4 h and 2 passes, and its run lasts 1.26
  h with one. Overview's Duration now shows the sequence's own length
  ("58 min + 2 event or condition stops (sequence)"; 14.4 h for template
  08, 83 min for 16, as their runs last), passes are counted over it, or
  said to be counted "in the Duration" when event stops leave it open,
  and a note under the Duration field says the same. Found by the audit
  of 2026-10-27 (G4).
- **Toasts fade out every time:** a toast shown for 2 s or more could
  vanish without its fade-out. Its two timers (the fade-out, then the
  dismissal 150 ms later) are coarse at that length, accurate to 5 %, and
  could fire the wrong way round. The fade-out now starts the dismissal.
  Found when a GUI test failed on CI.
- **Monte Carlo off, said before Run:** with Monte Carlo as the run mode
  but the scenario's Monte Carlo off, Run said so only after the click.
  The Run page's Monte Carlo options now say it is off, with **Enable
  Monte Carlo**, which turns it on and opens Scenario > Monte Carlo for
  its runs and dispersions. Found by the audit of 2026-10-27 (G5).
- **Exports no longer hold the window:** Results' **Export CSV** and
  **Export all** wrote their files in the click handler, about a second
  per long series, with no progress and no way to stop. They are written
  in the background now; beside the buttons the export says how far it is
  ("Exporting 3 of 40 files...") with **Cancel**, which stops before the
  next file and keeps the ones written. The files are the same, byte for
  byte. Found by the audit of 2026-10-27 (G2).
- **A Monte Carlo batch can be cancelled:** a batch ran to the end, and
  the window would not close while it ran. **Cancel** (or Esc) now stops
  it: the processes running it end, the runs finished stay in the archive
  folder, and the Monte Carlo view opens on them. Closing the window
  during a batch asks **Cancel and close** or **Keep running**. Found by
  the audit of 2026-10-27 (G3).
- **Field and check box borders meet WCAG 1.4.11:** the borders of
  input fields, check boxes and radio buttons were 1.4 to 1.6:1 against
  their backgrounds, under the 3:1 WCAG asks for the boundary that
  identifies a control. A new token, `border.control` (#88898C light,
  #6B6D71 dark), gives at least 3.08:1 against every background a control
  sits on, and the contrast test now covers it. Found by the audit of
  2026-10-27 (G7).
- **No plot error when a Monte Carlo batch starts:** the batch's thread
  imports pandas (through Basilisk's Monte Carlo controller), and a plot
  drawn on the window's thread at that moment could fail with "partially
  initialized module 'pandas'": plotly takes the module without waiting
  for the import. The window now imports pandas itself when it makes the
  batch's worker, once, about 0.25 s. Found when CI failed on it
  (Windows).
- **tornado 6.6:** three advisories published against tornado 6.5.10
  (CVE-2026-116577, CVE-2026-115927, CVE-2026-116578; fixed in 6.6) made
  CI's dependency audit fail. tornado comes with bokeh, which needs 6.2 or
  later; the pin is now 6.6.
- **An export that ends after its view is gone does nothing:** the end
  of an export (written off the window's thread since G2) called the
  results view through lambdas, which Qt does not disconnect when the view
  is deleted: the end of an export that outlived its view raised
  "Internal C++ object already deleted". It now reaches the view's own
  methods, which Qt disconnects with it. Found when CI failed on it.
- **More room for results on a small screen:** at 1280 x 720 the
  Inspector (380 px wide) and the Problems panel (140 px tall) left the
  plot 545 x 339 px. A new window now starts without the Problems panel,
  which opens when an edit makes the scenario invalid (and, as before,
  when a run cannot start), and, on a screen narrower than 1600 px,
  without the Inspector: the plot is 931 x 485 px. `Ctrl+J` and `Ctrl+I`
  show them; a layout kept from before is unchanged. The Inspector shows
  fields only: a focused button, tab or rail entry showed "Value -,
  Allowed -, Help -", and now shows its empty state. Found by the audit
  of 2026-10-27 (G8).
- **No traceback for JSON Python cannot read:** a scenario nested deeper
  than Python's JSON parser goes, or holding an integer of more than 4300
  digits, gave a RecursionError or ValueError traceback; it is now a
  refusal naming the file (exit 1). A recovery copy of that kind, or with
  a null scenario or a spacecraft that is not an object, raised at every
  start and recovery was never offered; it is now ignored. A fuzz test
  mangles every template 20 ways and checks that the loader only ever
  refuses (audit R5).
- **`lifetime --max-years` up to 100 years:** 1e6 overflowed the date (a
  traceback) and -5 exited 3; out-of-range values are now a usage error
  (exit 2) naming the range, the GUI's limit of 100 years (audit R6).
- **Exit status 4 for an internal error:** an unexpected exception
  printed a traceback and exited 1, the status of an invalid input, so a
  script could not tell a fault from a bad file. It is now one line,
  `INTERNAL ERROR: ...`, naming the log file that holds the traceback,
  and status 4 (ICD-02; audit R13).
- **`run` checks its output folder first:** a folder it cannot write
  (`--out-dir /etc/passwd/x`) was found only after the whole simulation;
  it is now refused before the run starts (exit 3). A folder holding
  files from an earlier run kept them next to the new results with no
  word; `run` now names them in a `WARNING` (audit R7, R8).
- **Names of at most 64 characters:** a 300-character spacecraft name
  validated, ran, and then failed to become a file name (exit 3); names of
  spacecraft, parts, sensors, actuators and ground stations longer than
  64 characters are now refused by `validate` (audit R8).
- **Size limits on inputs:** a scenario file over 20 MB, more than 1000
  spacecraft (also in `generate-constellation`, where 10 million ran for
  over a minute), a description over 100 000 characters and a dynamics
  step below 0.001 s are refused (exit 1); `ccsds-validate` and
  `ccsds-import` read at most 500 MB, where `/dev/zero` was killed for
  memory (exit 137) (audit R9).
- **Temporary folders are cleaned up:** a live Vizard stream's folder of
  3D models was never removed; it now goes when the app exits. The plot,
  Compare and 3D-model pages' folders went at a normal exit but stayed
  when the app was killed or crashed (the audit found hundreds). Each
  folder's name now carries its process id, and the GUI removes, in the
  background as it starts, those whose process has ended, and those
  named the old way that have not changed for a day (audit R14).
- **A file of the wrong shape says where:** `spacecraft: {"a": 1}` was
  refused as "dictionary update sequence element #0 has length 1; 2 is
  required". A part in the wrong shape, a missing field or an unknown one
  is now refused naming its place and what was expected, e.g.
  `spacecraft[0].sensors must be a list ([...]), not text` or
  `spacecraft[0].orbit: unexpected field 'warp'` (audit R5, notes).
- **Coverage counts Monte Carlo's worker processes:** they were not
  measured; they are now (`[tool.coverage.run]` in `pyproject.toml`): 29
  more lines covered, Monte Carlo's worker process 64.7 % to 82.4 %. `cli.py` stays at
  75.7 %: its tests already run in the test process, so what it lacks is
  tests, of `earth-orientation`, `monte-carlo` and `ccsds-import` above
  all (audit R11).
- **A regression baseline of every template:** `tests/test_golden_outputs.py`
  checks that all 31 templates still give the outputs recorded in
  `tests/golden/`: every series, event, warning and summary figure of a
  run capped at 6 hours, the Explain text, the lifetime of each drag
  spacecraft, every budget or its refusal, and a Monte Carlo batch. A
  number may now change only with an entry in the new `docs/changes.md`
  (transparency plan, Phase 1a). Numbers are compared within what two
  computers disagree on: on Linux, where it is written, 1e-6 of each
  quantity's scale, with floors for ill-conditioned values and angles
  modulo 2*pi; on Windows 1 %, with sensor noise (another random draw
  there) compared by its count only.
- **The provenance names recorder seeds the same on Windows:** they were
  keyed by the compiler's spelling of the message type
  (`Rec:class <struct SCStatesMsg` on Windows, `Rec:SCStatesMsg` on Linux).
  Recorders use no random numbers, so no result changes.
- **The orbit number and the mean semi-major axis change use the run's
  own central body:** both took Earth's GM for every body. Template 31
  (Eros) showed 220 582.58 orbits over its 2 days, now 2.58; a 400 km
  Mars orbit recorded every 600 s counted 312.41 orbits for 24.41. Earth
  runs are unchanged. The run's provenance now records `central_body` and
  `central_body_mu_m3_s2` (audit 3.1, 3.14; `docs/changes.md`).
- **The ROE formation controller's delta-V is in the run's delta-V
  figure:** it was left out; template 29's follower over 4 days showed
  0.000 m/s, now 0.588 m/s (audit 3.5).
- **Exit statuses as ICD-02 gives them:** `fsw-status` with an export no
  longer up to date and `sil --max-error` over the limit exit 5 (new: the
  command ran, its check did not pass), not 2, the status of a missing
  component; `monte-carlo` with a failed run exits 3, not 4 (an internal
  error); `kernels-status` with a kernel missing exits 2, not 1. A script
  that tested for 2 after `fsw-status` or `sil` must now test for 5 (audit
  3.2).
- **A run on predicted Earth orientation says so in its warnings:** the
  note was in the Explain tab only (audit 3.6).
- **A check that cannot run says so:** a pre-run or plausibility check
  that failed was dropped without a word and looked passed; it now shows
  `check not run: <name> (<error>)` (audit 3.11).
- **A stop epoch across a leap second counts it:** `propagate` to a stop
  epoch ran the UTC difference, a second short across a leap second; it
  now runs the TDB time the simulation counts (audit 3.13).
- **A run over 100 days records the whole run's provenance:** it kept the
  first segment's, with the hash of a modified copy of the scenario and
  the first segment's seeds only (audit 3.3).
- **The control gains shown are the gains applied:** an unticked K or P
  showed 3.5 and 30, while the controller uses them scaled by the
  spacecraft's mean moment of inertia / 900 kg*m^2 (0.039 and 0.33 for the
  default 10 kg*m^2 spacecraft, 90 times less). The form now shows the
  applied values, follows an inertia edit, and says how they are worked
  out. Nothing the controller does changes (transparency audit 3.4).
- **A new dispersion starts at the spacecraft's own value:** an untouched
  **Add** gave dry mass uniform in [0, 1] kg, written as the mass itself,
  so every run flew a spacecraft of under 1 kg. It now starts at the
  spacecraft's own dry mass (or drag or radiation-pressure coefficient)
  with no spread, and the note says to widen it (audit 3.7).
- **A new ground station's receive gain is the schema's, 0 dBi:** the
  editor started at 45 dBi, so a station made in the GUI and one written in
  a file without the field closed a link 45 dB apart. Stations already in
  a scenario keep their value (audit 3.9).
- **Corrected help:** the semi-major axis tooltip said ~6778 km was a
  ~500 km orbit of ~95 min; it is 400 km and 92.6 min (audit 3.8). The
  `RFLinkConfig` documentation said the link budget had no pointing loss
  and no effect on the simulation; both exist (audit 3.10).
- **A run warning's tooltip fits the warning:** every warning had the
  tooltip blaming numerical drift, a re-entry or space-weather one too;
  only a conservation-drift warning has it now (audit 3.12).

- **A run keeps what it was run from:** `run` writes `scenario_as_run.json`
  beside its results, the scenario as run after an older file was brought
  up to date; running it again runs the same scenario. `provenance.json`
  now also names the file given and the SHA-256 of its bytes, lists the
  run's warnings (`run_warnings`), and records the MSFC prediction a run
  past the observed space weather used. A run started in the GUI from a
  saved file with no unsaved edits records the file too (transparency
  plan, Phase 2a, 2b, 2d, 2f).
- **Every data file is hashed:** a file over 32 MB (`de430.bsp`, 114 MB)
  was recorded by size only; it is now hashed once and its SHA-256 kept
  while its path, size and modification time stay the same. Installed
  Earth orientation and small-body kernels are hashed at every run and
  compared with their install: a changed one gives a run warning.
- **A lifetime and a budget can be exported, with what they came from:**
  `lifetime --out FILE.json` and `budget --out FILE.json` write the
  inputs, the values used that are not in the scenario file (the drag
  area and coefficient, the re-entry perigee, the budget's rules and
  margins), the results (a lifetime with its decay), the notes and the
  provenance: versions, the file given and its SHA-256, and each
  space-weather file read with its SHA-256 (transparency plan, Phase 2g).
- **A Monte Carlo batch and a SIL report record their provenance:** a
  batch's `archive.provenance.json` now names the file given and gives
  what every run shares (integrator, tolerances, time step, frames, data
  files); each run's seeds stay in its `run<N>.json`. A SIL report now has
  the versions, the scenario's SHA-256, the time and the run's own record.
- **A run records the values it used that the file does not give:**
  `provenance.json` gains `effective_defaults`: each key a sensor's,
  actuator's, command's, `fsw_params` or `control_params` dictionary
  leaves out, with the value the engine applied (the inertia-scaled
  attitude gains, a sun sensor's 90 deg field of view, ...). It also gains
  `device_parameters`, each reaction wheel's and thruster's values from
  Basilisk's factory (inertia, torque, thrust, Isp, ...). A file written by an
  older version is no longer brought up to date silently: `validate` lists
  each value its migration changed (`MIGRATED:`), and the run records them
  (`scenario_file_migrations`) (transparency plan, Phase 2c).
- **Reproduce a result from its folder:** `run --bundle` (and, in the GUI,
  Results › Plots › **Export all...** › **Reproduction bundle...**) writes a
  folder that holds the results, the provenance, the scenario as run and
  copies of the files it refers to, with the space-weather files the run
  read. `spacemissionstudio reproduce FOLDER --out-dir DIR` runs it again
  and compares every series, within 1e-6 of each column's scale by
  default (`--rtol`). It names what differs (series, versions, platform,
  reference-data files) and exits 5 when a series does not agree
  (transparency plan, Phase 2h).
- The user manual said `sil --max-error` exits 2 over its limit; it exits 5
  since the exit codes were made consistent with ICD-02.
- **Change a rule without editing code:** the propellant budget's rules
  and margins are named parameters (`propellant_budget.cam_count_factor`,
  `residual_fraction`, ... 18 in all), each with its unit, source and
  limits. A scenario names a project configuration file
  (`config_file`, YAML) that changes them. `spacemissionstudio assumptions`
  lists them with the values in effect and marks the changed ones.
  `validate` says which file changes them, and every run, budget and
  lifetime record names the file, its SHA-256 and each value changed. The
  budget's margin labels follow the values ("5% of tank"). Each model is
  documented in `docs/models/`, starting with the propellant budget
  (transparency plan, Phase 3a, 3b). PyYAML is now a declared dependency.
- **The orbital lifetime's rules are parameters too:** the 120 km re-entry
  perigee, the decay's step control and drag ring, the 5- and 25-year
  rules, the drag make-up step, and the defaults `lifetime` and the End
  of Life page start from (Cd 2.2, the 50th percentile, 30 years, a 250
  km deorbit perigee): 11 in all, documented in
  `docs/models/lifetime.md`. The rules' labels and plot marks follow
  their values. A solar-activity percentile parameter now takes only
  MSFC's 95, 50 and 5, which a forecast can be resolved at; the budget's
  two accepted any value from 5 to 95 and failed later.
- **A project can require a link margin:** the link closes at a margin of
  at least `link.required_margin_db` (0 dB unless set), in the simulated
  downlink, Vizard's link status, the mission dashboard and the results
  overview alike. The "fixed" antenna's pointing loss (12 dB per
  (angle / beamwidth)^2, at most 30 dB), the transmitter's packet size
  and the explanation's pass length are parameters too, documented with
  the power model in `docs/models/link-data-and-power.md`.
- **A project can set a depth-of-discharge limit:** Results › Overview
  marks the battery when its lowest charge falls to
  `results.battery_critical_fraction` of its capacity (0, an empty
  battery, unless set). How a run's figures and events are read is
  documented in `docs/models/reading-results.md`. The window of the mean
  semi-major axis change, the umbra threshold and the dashboard's
  converged pointing are parameters too. A run is judged by the values it
  was run with.
- **A project can set the integrator's tolerances:** the adaptive
  integrators' relative (1e-10) and absolute (1e-8) tolerances, the
  re-entry checks of a run with drag (every 6 h, every 300 s below a 200 km
  perigee) and the two-body runs' 1 % conservation warning are
  parameters, documented in `docs/models/dynamics-run-control.md`.
- **MSFC's 132-month repeat and the TLE age warning are parameters:**
  `docs/models/environment-and-data.md` documents them with the
  environment data's fixed rules and why each is fixed. Every area of
  the transparency plan's Phase 3a is now in the registry: 46 parameters.
- **One set of physical constants:** every calculation of SpaceMissionStudio's
  own takes Basilisk's Earth and Sun constants from one module, as the
  simulation does. Five sets were in the code; the four that differed now
  agree. No printed number changes; the measured differences are in
  `docs/changes.md`. The scenario checks' re-entry follows
  `lifetime.reentry_altitude_km`, and the run's 100 km is the parameter
  `dynamics.reentry_altitude_km`. See `docs/models/constants.md`.
- **Scenario › Assumptions:** every parameter with the value in effect,
  its unit and source; the project configuration file the scenario names,
  chosen or created there; and a value set there, checked and written into
  the file on its own line, so the file's comments stay.
- **Fixed: the pass predictions and GEO elements for an epoch before
  2017** turned the Earth by a fixed 37 leap seconds, too far by 0.0042
  deg per leap second missing (0.0125 deg for 2010). They now count the
  leap seconds of the date. The Earth's rotation rate everywhere is
  SPICE's (pck00010), and the last copies of the constants (g0 in seven
  modules, the speed of light, the ODM writer's GM) take the one set. A
  lifetime changes by 2e-8 of itself at most; `docs/changes.md` has the
  digits. `docs/models/README.md` now lists the models whose rules are not
  yet parameters.
- **The orbit controllers' rules are parameters:** 9 of them, for the
  thruster's firing gate and minimum impulse bit, phasing keeping's
  divergence guard and trim, and GEO station keeping's burn arc,
  inclination target, drift fit, drift stop and maneuver end. A project
  configuration file changes them. GEO station keeping's J22 and lambda22
  now come from the GGM03S field the run loads (they had no recorded
  source). See `docs/models/orbit-control.md`.
- **How each budget number was computed:** `budget --explain` prints, for
  every row's delta-V and propellant and for the exhaust speed, dry mass
  and total, the equation and its AD10 section. It also prints each input
  with its unit and where it came from: the scenario file, a named
  parameter, a constant, the last run's series, or another number of the
  budget. `budget --out` writes the same traces in the JSON. The numbers
  are unchanged.
- **How each lifetime figure was computed:** `lifetime --explain` prints
  the traces of the mean orbit, the mass, the ballistic coefficient, the
  deorbit burn, the lifetime and each rule's verdict. `lifetime --out`
  writes them.
- **`link-budget`:** a new command. It gives the downlink's Eb/N0 budget,
  by default at the longest range of a pass (the station's minimum
  elevation), or at `--range-km`. Each figure, from EIRP to the margin, and
  whether the link closes; `--explain` gives how each was computed, and
  `--out` writes it as JSON. It needs no Basilisk.
- **Show calculation, and the Calculation panel:** the Budget and End of
  Life pages, and the Dashboard's link budget, have a **Show
  calculation** button. It opens the Calculation panel, a tab beside the
  Inspector: the number's equation and standard, each input with its
  unit and source, and an **Open** button to each input that is itself
  computed; **Back** returns and **Copy** copies it as text. On the
  Budget page it explains the selected row, or the total. A new window
  starts without the panel; View > Calculation in the command palette
  shows it. The panels' layout saved by an earlier version is not
  restored, once: they start as in a new window (the rail and the
  dividers are restored as before).
- **How the power and data figures were read:** the Dashboard's Power
  card has **Show calculation**. It shows the battery charge and net power
  with the series and sample read at the time cursor, and the state of
  charge, 100 x charge / capacity with the capacity from the scenario. A
  run's data totals (generated, downlinked, lost, on board at the end,
  memory full) carry their ledger series and sample, and `run --explain`
  prints them. The figures are unchanged.
- **How each event was found:** **Show calculation** on the Timeline
  opens the selected event's trace. It gives the series and the rule that
  says the event is on, the samples it starts and ends on, and the samples
  either side, so you see how precisely its times are known. **Open**
  then shows how its delta-V, data, elevation or lowest sunlight was
  read. The events and `events.csv` are unchanged.
- **The ROE formation guidance's rules are parameters:** 9 of them, for
  how often it looks, when an along-track error drifts, how a drift ends,
  eclipse retries and the differential-drag estimate and cycle. A project
  configuration file changes them. See `docs/models/roe-formation.md`,
  which also lists the guidance's values not yet parameters.
- **Tests:** the SIL deadline test no longer fails when a loaded Windows
  runner answers its first step in more than 50 ms (it now allows 0.2 s,
  and checks that missed deadlines are dropped steps).
- **Everything a run recorded, in one window:** the Provenance popover
  (Results > Overview, Run > History) has **Show everything recorded**.
  It opens the whole record as a tree in groups: software, run, seeds,
  scenario, data files, time scales, frames, configuration. It shows
  every value in full: each data file's SHA-256, every model's seed,
  each series' frame. The popover only counted them ("5 entries"). A
  filter finds a name or value, and **Copy as JSON** copies the record.
- **How each headline figure of a run was computed:** click a card on
  Results > Overview (or focus it and press Enter) to see its figure's
  calculation: the series it was read from, at which sample or time, the
  parameters and constants, and the values on the way (each controller's
  delta-V, each tank, each station's passes, the averaging windows of the
  semi-major axis). `run --explain` prints the same after a run. The
  figures are unchanged.
- **Fixed: a lifetime that reached the ground within one step raised an
  error.** With the exponential atmosphere and a deorbit burn, for
  instance, the estimate failed with "M2E() received e = 5.9e+26". It now
  re-enters in that step and says the re-entry time is known to within
  it.

## 1.3.1 (2026-10-27)

A faster window. Changing the theme, opening a template and the end of
the first run each held the window noticeably; this release shortens all
three. Nothing the tool computes changes: scenario files, the command
line, every exported file and every result are the same as with 1.3.0.

- **A faster theme switch, again:** a message about a spacecraft whose
  page had not been opened was worded from a hidden spacecraft form, kept
  for the session once any template from 08 on was opened: about 1,000
  widgets that every theme switch restyled. The titles are now read from
  such a form once, kept as text, and the form deleted. A switch takes
  about 0.36 s where it took 0.53 s (all templates opened, then template
  23); the messages read as before.
- **Opening a template is faster:** 72-134 ms where it took 82-459 ms
  (the median of the 31 templates 94 ms, was 111). A scenario loaded is
  checked once instead of four times; the titles for messages about a
  spacecraft are read once start-up has settled, a part of the form per
  moment, instead of all at once (0.4 s) when the first such message
  appeared (template 08); the check of the space-weather data's dates no
  longer looks through all 25,000 days on every edit.
- **The first run's end no longer pauses:** the first run of a session
  held the window 0.2-0.3 s while its first plot was drawn, the time
  plotly takes to load its figure classes on first use. They are now
  loaded in the background once start-up has settled; the longest pause
  at the end of a run is 27-38 ms, first run or not.

### Who should update

- Everyone who uses the window: it pauses less. On Linux,
  `apt install ./spacemissionstudio_1.3.1_amd64.deb` replaces the 1.3.0
  package; on Windows, run the 1.3.1 setup over 1.3.0.
- Scripts and pipelines that use only the command line gain nothing from
  this release.

### Known limits

- Some actions still hold the window for longer than the 50 ms the
  interface aims at: changing the theme (about 0.4 s), the first visit to
  a spacecraft page (0.15-0.2 s) and opening a template (0.07-0.13 s)
  (SRelD K-19, K-23). A run that ends in the first seconds after start-up
  can still pause for up to 0.3 s.
- On Windows, a software-in-the-loop session that drops thousands of
  steps may stop with "the flight software took no STEP for 10 s". Seen
  only in CI, cause not known (SRelD K-14).

## 1.3.0 (2026-10-26)

A new interface. The window has a navigation rail in place of menus and
toolbars, a command palette (`Ctrl+K`), a Problems panel and an inspector;
forms show units in their fields and edit in place; Results opens on an
overview of the run; tables copy, sort and filter alike; the Timeline
takes a year of events; Reports lists every export; Settings adds the UI
scale, reduce motion and the Vizard location. What the tool computes, its
files, its command line and every file it writes are unchanged (the
exports are tested byte for byte against 1.1.0 and 1.2.0). It starts
faster than the interface before it and switches theme, plots and pages
with shorter pauses; `docs/ui/BEFORE_AFTER.md` has the measurements,
including the ones that did not meet their target. Scenario files are
the same as with 1.2.0, and so are their results, except drag on dates
the refreshed space weather changed (below).

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
  file the app writes are the same.

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

- **Forms: units in the fields, optional groups that fold away** (UI
  overhaul M4a):
  - **Every number shows its unit after it**, right-aligned: "550.0 km",
    "97.59°", "1.000 m²", "300.00 Wh". Labels are the name alone. Messages
    still name a field with its unit, "Dry mass [kg]".
  - **An optional group** (Station keeping, Power budget, ROE formation,
    ...) **shows only its title while it is off**, instead of every field
    greyed out; Monte Carlo off says what turning it on does.
  - **No page of the Scenario editor scrolls sideways** in a 1280 px
    window with the inspector open: long rows put their field under the
    label, and rows of buttons wrap. The Power page and the Spacecraft
    page did scroll.
  - The Customize wizard shows its units the same way.

  Every value and every file the app writes are the same: each template
  is written back byte for byte after every page has been shown.

- **Editing without dialogs; Explain as the scenario's Overview** (UI
  overhaul M4b):
  - **Explain is Scenario › Overview**, the first node of the scenario
    tree, instead of a panel beside the inspector. It follows an edit a
    quarter of a second after you stop typing and is worked out in the
    background, so typing never waits for it. Its name says what there is
    to check: "Overview (1 to check)". View › Explain opens it.
  - **Form · JSON**, at the top of the Scenario area, replaces the tree's
    JSON page. Back to Form applies the text, and is refused while it does
    not parse or validate; **Discard** puts the scenario's text back.
  - **Devices and dispersions are edited under their list**, as you type,
    instead of in a dialog. A value that does not apply (a name already
    taken) is not applied, and the form says why.
  - **Add** adds a spacecraft, ground station, device or dispersion at
    once and opens it. Remove or Undo take it back.
  - A closed window no longer autosaves.

  What a run computes and every file the app writes are unchanged.

- **Run › History and a record of every run** (UI overhaul M5a):
  - **History**, in the Run area, lists every run, newest first: its
    status (Done, Cancelled, Failed), mode, start (UTC), how long it took
    and whether it is saved, with its provenance one click away. Failed
    runs and Monte Carlo batches are listed for the session they ran in.
  - **The Log records each run:** its start, its end and length, its
    warnings, and where it is saved. **Copy** copies what it shows.
  - **The end of a run waits less:** the run is saved, and old runs
    pruned, in the background; the plots are drawn once, and Compare when
    it is opened. On template 23 the window is held about half as long
    (152-163 ms, was 301-323 ms).

  What a run computes and every file the app writes are unchanged.

- **The run options on one page** (UI overhaul M5b):
  - **The run mode** is a segmented control in the Run area's header,
    **Single · Monte Carlo · SIL**; the top bar keeps its menu beside Run.
  - **Run › Run**, the Run area's first page, holds what the next run
    uses, for the mode chosen, and applies each change at once:
    **Live plot** and the **Vizard** options (they were a dialog) for a
    single run and a SIL run; the **archive folder** of a Monte Carlo
    batch, with Browse..., remembered for each scenario (left empty, Run
    asks for one, as before); the **spacecraft and program** of a SIL run
    (they were two dialogs). The overwrite question for an earlier batch
    stays.

  What a run computes and every file the app writes are unchanged.

- **Results › Overview, and plots that switch at once** (UI overhaul M6a):
  - **Overview**, the first view of Results, shows the run's headline
    figures as cards (delta-V, propellant, link margin, battery, passes,
    eclipses, data downlinked, ...). A card turns red, with an icon and its
    reason, only for a link margin below 0 dB or an empty battery.
    **Provenance** shows what produced the run.
  - **Plots** stay in one page: plotly.js is loaded once, and showing
    another plot, changing the layout or the time axis redraws in place.
    A plot appears about four times sooner (about 110 ms, was about
    415 ms on template 23), and switching holds the window at most
    35 ms (was up to 304 ms).
  - Shorter pauses now and then: Python's full garbage collections no
    longer walk everything start-up made (one took about 0.2 s; after a
    run, about 0.07 s is left).

  What a run computes and every file the app writes are unchanged.

- **One kind of table, and a shorter end of a run** (UI overhaul M6b):
  - The tables of Output, Monte Carlo, Compare and Budget work alike:
    `Ctrl+C` copies the rows as tab-separated text with the headings,
    right-clicking a heading shows or hides its column, numbers are
    right-aligned with their unit in the heading.
  - The end of a run is shown in steps, and the run is saved a moment
    after: each step holds the window 17-36 ms, where the whole end of a
    run held it 100-130 ms on template 23 (the longest pause after a run
    is now about 50 ms, more when Python collects garbage then).

  What a run computes and every file the app writes are unchanged.

- **A Timeline for long runs** (UI overhaul M7):
  - Ten thousand events (a year of passes) show, filter and sort without
    a pause: about 40 ms at most (it was 0.7 s to show them and over 2 s a
    search keystroke).
  - The axis is in UTC with `Z` ("08:00Z", the date at midnight) when the
    run has an epoch.
  - Move along it with Shift+wheel, the arrow keys or a right-button
    drag; zoom with the wheel or `+` and `-`; `0` fits the whole run.

  What a run computes and every file the app writes are unchanged.

- **Every export in one place; three new settings** (UI overhaul M8):
  - **Reports › Exports** lists every file the app writes, with its
    format, the view and button that make it, its default destination,
    the provenance written with it and when this computer last wrote one
    (UTC). A double-click opens the view that makes it.
  - The exported files are the same as 1.1.0's, byte for byte: a new test
    writes each of them (the results, events, mission output, Monte
    Carlo and budget CSVs, the `.obj` model, the SIL report) and compares
    them with the files 1.1.0 wrote. PNG and SVG plots, the
    flight-software project and the Vizard file are not in it (the web
    engine draws the plots; the project has its own test against
    Basilisk; Basilisk writes the Vizard file).
  - **Settings › Appearance:** the **UI scale** (90, 100, 110 or 125 %,
    from the next start) and **Reduce motion** (notifications appear and
    go without their 150 ms fade). **Settings › Vizard:** the Vizard
    program, with **Browse...** and **Clear**.

  What a run computes and every file the app writes are unchanged.

- **A faster start, and every area by keyboard** (UI overhaul M9):
  - The window appears in about 1.9 s where it took 2.5-2.8 s on the
    same machine before the overhaul: the reference data files are read
    in the background, and the status bar fills in a moment later.
  - Tab reaches every control of every area. It could not leave the
    scenario's description before (Tab typed into it); now it moves on,
    as it does from read-only tables.
  - The spacecraft page and the spacecraft editor open faster (456 and
    381 ms, from 541 and 415 ms), though still not at once.
- **The documentation follows the new interface:** the User Manual, the
  how-to guides, the READMEs, the FAQ, troubleshooting, tips, the
  glossary, the template catalog and the user manual of the compliance
  set name the areas and pages of 1.3.0 (no more menus, Explain is
  **Scenario > Overview**, a spacecraft's parts are pages of the
  scenario tree); 31 templates, not 28 or 29. Template 22's description
  and two notes in the window said the same.
- **Fixed:** `Alt+Backspace` did nothing once there was an edit to undo:
  it was both Clear Time Cursor's key and, on Linux and Windows, one of
  Undo's. It is Clear Time Cursor's alone now; Undo keeps `Ctrl+Z`. The
  support-data error and the Earth orientation warning name **Settings >
  Reference data**, no longer a Tools menu.
- **A faster theme switch:** every switch restyled every widget twice
  (the Fusion style was set again before the new style sheet); it now
  does so once, which halves it: about 1 s where it was 2 s with a
  template run and the spacecraft editor opened, about 0.5 s otherwise.
- **A spacecraft's page opens faster:** it builds its Orbit / mass section
  first and the others just after, one at a time, so the first visit
  pauses for about 0.16 s where it took 0.4 s.
- **Bundled space weather refreshed:** CelesTrak's `SW-All.txt` updated
  2026-10-25 23:32 UTC, observations to 2026-10-24 and its daily forecast
  to 2026-12-07 (it was 2026-10-18 and 2026-12-02). CelesTrak revised its
  values from 2026-09-09 on and the first two months of the monthly
  forecast (2027-01, 2027-02), so drag on those dates changes; runs that
  start later, such as every template (2030), do not. NASA MSFC's
  October 2026 prediction is unchanged.

### Who should update

- Everyone who uses the window: the interface is new throughout (the
  User Manual shows it). Nothing 1.2.0 computes changes: scenario files,
  the command line and every exported file are the same, and so are
  results, except drag on dates the refreshed space weather changed
  (2026-09-09 to 2026-12-07, and 2027-01 to 2027-02).
- On Linux, `apt install ./spacemissionstudio_1.3.0_amd64.deb` replaces
  the 1.2.0 package; on Windows, run the 1.3.0 setup over 1.2.0.
- Scripts and pipelines that use only the command line gain nothing from
  this release.

### Known limits

- Some actions still hold the window for longer than the 50 ms the
  interface aims at: changing the theme (0.5-1 s), opening a template
  (0.2-0.5 s), the first visit to a spacecraft page (0.15-0.2 s) and the end
  of a run (0.5 s) (SRelD K-19, K-23).
- On Windows, a software-in-the-loop session that drops thousands of
  steps may stop with "the flight software took no STEP for 10 s". Seen
  only in CI, cause not known (SRelD K-14).

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
