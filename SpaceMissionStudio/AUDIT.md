# Pre-release audit

A final-gate audit of everything this fork adds to Basilisk: the
SpaceMissionStudio application and its CLI, the exported flight software,
the scripts, packaging, compliance tools, examples, CI and documentation.
Basilisk itself (everything outside `SpaceMissionStudio/` and the fork's
CI workflow) is out of scope: it is upstream code, used and never
changed.

Baseline: `develop` at `f2f0ce140` (2026-10-12), Basilisk 2.12.0, Python
3.11, PySide6 6.11.2.

## 1. Map of the tools

### 1.1 What ships

| Tool | Entry point | Input | Output | Needs |
|---|---|---|---|---|
| **GUI** | `spacemissionstudio gui` (`gui/app.py`, `gui/main_window.py`) | scenario JSON (or a template), user edits | scenario JSON, CSV/PNG/SVG/JSON exports with provenance, Vizard save files, FSW exports | PySide6 + plotly; Basilisk to run |
| **CLI** (`spacemissionstudio`, `cli.py`) | 17 subcommands, below | scenario JSON, CCSDS KVN files, FSW binaries | CSV + `provenance.json` + `events.csv`, OEM/OPM, updated scenarios, reports; exit codes | numpy, sgp4, pyerfa; Basilisk for the commands that simulate |
| **Python API** | `import spacemissionstudio` (`schema`, `engine`) and `examples/*.py` | dataclasses or JSON | `ResultSet`, analysis results | as above |
| **Exported flight software** | `fsw_export/` writes a CMake C project: `fsw_host` (replay, unit tests, `sil` mode), `fsw_adapter_host` | the scenario's FSW configuration, a recorded run | C sources (Basilisk 2.12.0 FSW modules unchanged), `ICD.md`, `TRACEABILITY.md`, `MANIFEST` | a C compiler, CMake |
| **SIL** (`sil/`) | GUI **Run SIL...**, CLI `sil` | a host binary speaking the SIL contract v1 | comparison report (JSON/CSV), exit 2 over `--max-error` | Basilisk; Unix socket (Linux/macOS) or loopback TCP (Windows) |
| **Installers** (`packaging/`) | `install.sh`, `install.ps1`, `build_deb.sh`, `windows/spacemissionstudio.iss` + `bootstrap_env.ps1`, `build_wheel.sh/.ps1` | a checkout or a wheel | a private venv, launcher, `.deb`, `setup.exe` | internet once |
| **Developer scripts** (`scripts/`) | `_generate_templates.py`, `sync_help.py`, `capture_screenshots.py`, `vendor_basilisk_fsw.py`, `print_core_backtraces.sh` | the package | templates, help copy, screenshots, the vendored FSW zip, CI backtraces | dev environment |
| **Compliance tools** (`compliance/tools/`) | 13 scripts (`check_drds`, `build_*`, `metrics`, ...) | code, tests, JUnit/coverage | generated `compliance/docs/*`, matrices, metrics | dev environment |
| **CI** | `.github/workflows/spacemissionstudio.yml` | push/PR | lint, compliance drift, tests + coverage on Linux, offline tests, Windows/macOS suites | GitHub runners |

### 1.2 CLI commands

| Command | What it does | Basilisk |
|---|---|---|
| `validate` | load + validate a scenario | no |
| `run` | simulate headlessly; CSV, events, provenance; `--oem`, Vizard options, `--allow-scripts` | yes |
| `monte-carlo` | run a batch, archive retained runs | yes |
| `lifetime` | orbit-averaged re-entry estimate, deorbit perigee, 5/25-year rules | no (own model) |
| `budget` | AD10-style delta-V/propellant budget; `--run`, `--launch-delays`, `--altitudes` | `--run`, trades |
| `kernels-status` | fetch/check SPICE, gravity, magnetic data | downloads |
| `earth-orientation` | `--fetch`, `--import`, `--rollback` NAIF Earth PCKs | downloads |
| `ccsds-validate` / `ccsds-export` / `ccsds-import` | CCSDS 502.0-B-3 OPM/OMM/OEM KVN | export: yes |
| `export-fsw` / `fsw-status` | C flight-software export and its staleness | export: yes |
| `sil` | software-in-the-loop run against a binary | yes |
| `spaceweather-resolve` | which space-weather file and percentile a scenario uses | no |
| `generate-constellation` | Walker delta/star constellation from a template | no |
| `generate-phasing-formation` | follower spacecraft for a phasing formation | yes |
| `gui` | start the GUI | no |

### 1.3 How the pieces fit

- `schema/` (dataclasses, validation, migrations, mission-sequence
  commands, reference checks) is the single data model. GUI and CLI both
  go through it, then through `engine/`.
- `engine/service.py` builds one Basilisk simulation per run (SPICE,
  gravity, atmosphere + space weather, SRP, spacecraft, effectors, FSW
  from `engine/fsw.py`, recorders) and runs it in chunks. `long_run.py`
  chains segments past Basilisk's 104-day clock limit; `mission_engine.py`
  runs a Mission Sequence; `monte_carlo.py` fans runs out to processes.
- Analyses that do not simulate: `lifetime.py`, `propellant_budget.py`,
  `link_budget.py`, `constellation.py`, `orbit_design.py`,
  `scenario_checks.py`, `scenario_explainer.py`.
- Data and exchange: `spaceweather.py` (bundled CelesTrak record + MSFC
  prediction, opt-in fetch), `earth_orientation.py`, `kernels.py`,
  `ccsds_odm.py`, `tle.py`, `results.py`, `events.py`,
  `output_provenance.py`.
- `gui/` runs every long operation in a worker thread (`run_worker.py`
  and others) and shows results in the Results, Events, Mission
  Dashboard, Mission Output, Data, Explain, End of Life, Budget, Flight
  Software and Monte Carlo tabs.
- The app is offline by design: downloads only on request
  (`_offline.py`, the startup **Fetch/update data?** dialog, the Data
  tab); bundled space-weather data; results never extrapolated.

### 1.4 Intended behaviour I will audit against

- Every invalid input is refused with a message naming the field, before
  anything is built; nothing fails silently.
- Exports carry provenance; results are never invented or extrapolated.
- No network access unless asked; scripts in a Mission Sequence run only
  with consent.
- GUI and CLI give the same answers for the same scenario.
- The docs, the in-app manual and `--help` describe what the code does.
- Linux, Windows and macOS (Apple silicon) behave the same, within the
  documented limits.

## 2. Findings

The findings below are as reported before any fix; section 5 gives what
was done about each. Each finding gives where, how bad, what is wrong,
why it matters, the proposed fix, and the evidence:

- **run**: reproduced by running the tool (inputs kept in the audit scratch folder);
- **measured**: shown with a short numerical check;
- **read**: found by reading the code, not reproduced.

**BC** marks a fix that changes behaviour a user could notice, such as
refusing a file that loads today. These need your agreement (section 4).

Severity scale:

| Severity | Meaning |
|---|---|
| Critical | Corrupts or loses data, or is a practical security hole, in normal use |
| High | Silently wrong results, an unrecoverable hang, or a scenario file able to act outside the tool |
| Medium | A crash or traceback on realistic input, or wrong results on a less common path |
| Low | Robustness, cosmetics, stale documentation, performance |

**No finding is rated critical.** The worst ones are high: silent wrong
results, a GUI hang that cannot be recovered without killing the app, and
file writes outside the output folder. Each needs an unusual input or a
less common feature combination to trigger.

### 2.1 High

**H1. Monte Carlo ignores the Mission Sequence (silent wrong results).**
`engine/monte_carlo.py:429-438`. `_execute_sim` only initialises the
simulation and propagates `duration_days`; it never runs the
`MissionEngine`. A scenario with burns therefore produces a Monte Carlo
batch without the burns, and reports "All runs succeeded". Template 08
(orbit raise) with Monte Carlo on: every run stays at a maximum radius of
6778.7 km, while `run` on the same file reaches 6957.6 km. The manual
(Section 10) does not say the sequence is skipped. *Fix:* either run the
Mission Sequence inside each Monte Carlo run (script blocks still need
consent), or refuse Monte Carlo with a Mission Sequence in `validate`.
**BC; your choice (Q1).** *Evidence:* run.

**H2. Some actuator settings pass validation and then make Basilisk
call `exit(1)`; the GUI hangs.** `schema/scenario.py:1455-1568`,
`engine/fsw.py:819-944`, `gui/run_worker.py:119-160`.
- *What passes validation:* an unknown `rw_type` or `thruster_type`, and
  a custom wheel with `u_max <= 0`.
- *What Basilisk does then:* `rwFactory`/`thrusterFactory` call `exit(1)`.
  It prints "RW type Bogus is not implemented", "Thruster type Bogus is
  not implemented", or "RW is being setup with non-positive u_max".
- *CLI:* exits with status 1.
- *GUI:* the run thread receives `SystemExit` and dies without emitting
  `failed` or `finished`. The window stays at "Running…" with no message.
  `closeEvent` (main_window.py:1636-1643) then refuses to close ("still
  running"), so the user must kill the app and loses unsaved work. The
  Monte Carlo, flight-software export and SIL workers share the gap.

*Fix:*
1. Validate `rw_type`/`thruster_type` against the factory's own names.
2. Range-check the numbers the factories exit on (u_max, Js, Omega_max,
   maxMomentum, MaxThrust, steadyIsp).
3. Catch `SystemExit` in every worker around the Basilisk build and
   report it as a failure.

**BC** (such files are refused at load). *Evidence:* run (CLI; GUI
worker offscreen: no signal within 60 s).

**H3. A spacecraft or station name can steer output files outside the
output folder.** `schema/scenario.py:1289` (names only checked
non-empty); file names are built from names in `engine/results.py:265`
(CSV), `cli.py` `run --oem` and `ccsds-export`, and events. A
spacecraft named `../../escaped` validates, and `run --out-dir
trav/a/b/out --oem` wrote `escaped.*.csv` and `escaped.oem` into
`trav/a`, two levels up. The tool treats scenario files from other
people as untrusted (script blocks need consent), but a shared file can
place `.csv`/`.oem`/`.opm` files anywhere the user can write. Names
containing `.` also break the `"<spacecraft>.<field>"` series naming (read, not run).
Two names that differ only in punctuation ("sat 1", "sat-1") also
collide in Monte Carlo (`monte_carlo.py:226-239`): a dispersion silently
lands on the other spacecraft. *Fix:* refuse `/`, `\`, `..`, a leading
`.`, control characters and `.` in names (validate, GUI, wizards); build
every file name through one sanitiser that refuses to leave the output
folder; refuse name pairs that collide after sanitising. **BC** (odd
names in existing files are refused; a one-line migration could rename
them). *Evidence:* run.

**H4. Vizard download: a disk or permission error leaves a modal dialog
that never closes.** `gui/vizard_launcher.py:439-449` (worker catches
only `VizardFetchError`), `:279-326` (raw `OSError` from writing,
`rmtree`, extraction, `chmod`), `gui/main_window.py:1129-1160` (nested
event loop waits for a signal). With an `OSError` inside the download,
neither `finished_ok` nor `failed` fires. The "Downloading Vizard…"
dialog stays up, and its Cancel button does nothing. *Fix:* catch every
exception in the worker and emit `failed`; wrap those `OSError`s as
`VizardFetchError`. Also stream the download to its `.part` file instead
of holding up to 2 GiB in memory (low). *Evidence:* run (offscreen,
still waiting after 8 s).

### 2.2 Medium

**M1. Magnetic field evaluated at 2019, whatever the scenario epoch.**
`engine/fsw.py:1247-1265`. `magneticFieldWMM.epochInMsg` is never
connected and no `epochDateFractionalYear` is set, so Basilisk uses its
default epoch, 2019-01-01 (`simDefinitions.h`), plus elapsed time. Each
spacecraft's position is still converted to Earth-fixed axes with the
real rotation, so the error is the field's secular change between 2019
and the scenario date. At a LEO point with the bundled WMM2025
coefficients:

| Scenario epoch | Magnitude error | Direction error |
|---|---|---|
| 2026 | 1.18 % | 0.68° |
| 2030 | 1.86 % | 1.07° |

This affects magnetometers and torque-rod momentum management, and
nothing reports it. The `fsw.py:62-65` docstring says leaving it out
"does not break anything". WMM2025 is also valid only until 2030.
*Fix:* subscribe it to the gravity factory's epoch message, as the
atmosphere already is (`service.py:1032-1037`); add a run warning past
the model's validity. **BC** (magnetic results change slightly).
*Evidence:* measured.

**M2. The condition evaluator's limits apply per operation, so a
condition can hang the app or exhaust memory.** `schema/command.py:423-431`. `('x'*1000000)*1000`
builds a 1 GB string in 5.4 s; `((9**999)**999)**999` has about 9.5e8
digits. If/while conditions run without script consent, so a shared
file can do what security analysis S-12 says is prevented. *Fix:* cap the
result size (length of a repeated text or list; bit length after `**`,
`*` and `<<`). *Evidence:* measured.

**M3. Mission Sequence time is not bounded.** `schema/scenario.py:2119-2129`,
`engine/mission_engine.py:310-544`. Only `duration_days > 100` is refused
with a sequence. The propagate durations, stop epochs, while loops and
the event search cap (10 × duration) are not limited. A file with
`duration_days = 1` and two 60-day propagates validates and runs past
Basilisk's 104-day `nanoToSec` limit. In my two-body (120 d) and
gravity-field plus Sun/Moon (108 d) runs no NaN appeared, so the
documented failure did not show for those models. It is still outside
the limit the schema documents. *Fix:* refuse a target past 100 days in
`_advance_to`/`_run_propagate_event`, and check the sum of fixed
durations in `validate`. **BC.** *Evidence:* run (accepted; effect not
reproduced).

**M4. Station keeping logs "propellant depleted" every step.**
`engine/orbit_maintenance.py:683-684`. 1259 lines in a 0.5-day run; a
multi-year run that empties its tank prints millions. The GEO controller
does the opposite: it goes silent when its tank is empty
(`geo_station_keeping.py:243`). *Fix:* warn once per depletion and add a
result warning, in both controllers. *Evidence:* run.

**M5. A phasing formation with a negative along-track distance flies the
follower to the other side.** `engine/formation.py:337`,
`gui/phasing_formation_dialog.py:176`, `cli.py:1026`. Negative values
are accepted. The follower is placed behind the chief but targeted at
`abs(x)` ahead, so the controller starts with a 2|x| error and spends
delta-V crossing over. *Fix:* require `along_track_km > 0` (validate,
GUI minimum, CLI). **BC.** *Evidence:* read.

**M6. Report series from ground-station access are refused.**
`schema/references.py:117-128`. The Report pick-list offers
`berlin-gs.access_to_my-sat.azimuth`, but validation treats the first
segment as a spacecraft: "spacecraft 'berlin-gs' is not one of this
scenario's spacecrafts". The word "spacecrafts" is also wrong
(`scenario.py:2227`, `validation.py:117`). *Fix:* resolve the owner
through `series_names`. *Evidence:* run.

**M7. A '…Z' epoch half works.** `schema/scenario.py:2033`.
`fromisoformat` accepts `Z` and `+hh:mm` on Python 3.11+, but several
modules subtract the epoch from naive datetimes:
- `orbit_design.raan_for_ltan_deg` raises a TypeError, which breaks the
  GUI "RAAN for LTAN" helper (run);
- a Mission Sequence stop epoch is affected (`mission_engine.py:319-321`);
- `ccsds-import` compares an offset epoch 2 h out (`cli.py:578-579`).

On Python 3.9/3.10 the same file is refused (see M8). *Fix:* one
`parse_epoch_utc` helper used everywhere, accepting `Z` and converting
offsets to UTC. *Evidence:* run (helper) and read.

**M8. The declared `requires-python >= 3.9` is not tested and partly
broken.** `pyproject.toml:6`; the CI workflow tests only 3.11. On Python
3.10.20 without Basilisk or PySide6: 1227 passed, 10 failed, 1 error.
- 6 failures come from '…Z' epochs, which 3.10 rejects. Users on 3.9/3.10
  have the same problem with such files.
- 4 failures are tests that need Basilisk or PySide6 but fail instead of
  skipping (`test_offline.py::test_validate_and_export_a_template_offline`,
  `test_output_provenance.py::test_png_keeps_its_image_and_carries_the_record`,
  `test_planet_rotation.py::test_nearest_rotation_…`,
  `test_solar_arrays.py::test_the_hub_carries_…`).

*Fix:* the M7 helper; markers on those four tests; then either add 3.9
to CI or raise `requires-python` (Q4). *Evidence:* run.

**M9. GUI Save does not report a failed save.** `gui/main_window.py:995-1005`.
An `OSError` from `Scenario.save` (unwritable folder, a file in the
path) is raised inside the Qt slot: it is logged, but no message is
shown. `Scenario.save` (`scenario.py:2311-2315`) also truncates before
writing, so a crash or full disk mid-save destroys the previous good
file, and it creates missing folders silently. *Fix:* show "Could not
save"; write to a temporary file in the same folder and `os.replace`
it. *Evidence:* run (offscreen) and read.

**M10. Monte Carlo can show a previous batch as the new one.**
`engine/monte_carlo.py:503-506`, `gui/main_window.py:1595-1615`. The
summary is written only if at least one run succeeded. In a reused
folder whose runs all fail, the old `batch_results.*` stay, and the GUI
opens them as this batch's results. Stale `run{N}` files from a larger
earlier batch also stay. *Fix:* require an empty folder (or explicit
overwrite), or remove the old summary first. **BC.** *Evidence:* read.

**M11. An unwritable home directory stops every command.**
`logging_setup.py:103`. With `HOME=/proc`, even `validate` dies with a
traceback while creating `~/.spacemissionstudio/logs`. *Fix:* fall back
to stderr logging with one warning. *Evidence:* run.

**M12. Bad user data files give tracebacks instead of messages.**
- `space_weather.local_file_path` pointing at a folder or a binary file
  validates OK. `spaceweather-resolve` reports it cleanly, but
  `lifetime` dies with UnicodeDecodeError, because
  `lifetime.py:371` catches only SpaceWeatherError
  (`engine/spaceweather.py:454-596`; `open()` also uses the locale
  encoding). *Evidence:* run.
- `ccsds-import` with a missing or folder message (`cli.py:561-567`)
  gives a traceback. *Evidence:* run.
- `earth-orientation --import` with a missing file
  (`engine/earth_orientation.py:211-224`) gives a traceback, and a
  failed import leaves `.part` files. *Evidence:* run.
- `run --out-dir` under a file (`cli.py:153-175`) gives a traceback.
  *Evidence:* run.
- `lifetime --max-years -5` gives a BasiliskError traceback and leaves
  an end-before-start cache file. *Evidence:* run.

*Fix:* convert these to the module's own error type, catch them in the
CLI, read user files as UTF-8, and range-check `--max-years`.

**M13. A CCSDS OPM centred on another body is imported as Earth-centred.**
`engine/ccsds_odm.py:911-926`, `cli.py:561-590`. An OPM with
`CENTER_NAME = MARS` imports into an Earth scenario with no warning. A
TLE orbit is also accepted for a non-Earth central body. *Fix:* refuse a
CENTER_NAME other than the scenario's central body, and refuse TLE/OMM
unless the central body is Earth. **BC.** *Evidence:* run.

**M14. Dependencies are not pinned for a release.** `pyproject.toml:21-46`;
`packaging/install.sh:96`, the Debian package and the Windows bootstrap;
CI workflow lines 87, 134 and 240. Only lower bounds are set (Basilisk
excepted, `bsk==2.12.0`), so every install takes the newest PySide6,
plotly and numpy. A release is not reproducible, and a future PySide6
can break installs. *Fix:* ship a tested constraints file and use it in
the installers and CI. *Evidence:* read.

**M15. SIL on Windows can lose the flight software's error message.**
`fsw_export/templates/fsw_log.c:117-125`, `fsw_sil.c:393-398`. On
BSK_ERROR the program sends ERROR and calls `exit(70)` without closing
its socket. On Windows the abortive close (WinError 10054) can drop the
frame, so the user sees "link failed" instead of the error, and the CI
test of this path is flaky there (known from PR #42). *Fix:* shut down
the send side and close before `exit`. *Evidence:* read (and PR #42 CI).

**M16. Validation accepts values that fail or misbehave at run time.**

| Accepted by `validate` | What happens at run time | Evidence |
|---|---|---|
| NaN in a cartesian position or a classical element; `semi_major_axis_km = Infinity` | Basilisk misbehaves | run (`scenario.py:257-260, 1332-1333`) |
| A thruster with `tHat_B = [0, 0, 0]` or negative `MaxThrust` | Basilisk misbehaves | run (`scenario.py:1547-1568`) |
| A wheel motor starting at −300 °C | `motorThermal` exits at or below absolute zero, per the schema's own comment | run (`scenario.py:1526-1546`) |
| A malformed TLE | "TLE line 1 has 25 characters" | run |
| A comms-pointing spacecraft with actuators | Fails with the contradictory "Set fsw_mode" | read (`service.py:1329-1334`) |
| A thermal sensor without the Sun | Fails at build | read (`service.py:928-945`) |
| A phasing chief whose orbit is not classical elements | Fails at build | read (`service.py:1611`) |

All of these break the rule "every invalid input is refused before
anything is built". *Fix:* move each check into `validate`, using
`_is_direction_vector` and finite-number checks. **BC.**

### 2.3 Low

| ID | Where | What | Proposed fix | Evidence |
|---|---|---|---|---|
| L1 | `engine/mission_engine.py:860` | `exec(code, globals, context)`: on Python < 3.12 a list comprehension or `def` in a script block cannot see `spacecraft`, `t_s` (NameError) | one namespace dict | run |
| L2 | `engine/lifetime.py:592` | after a retro burn at apogee the argument of perigee is turned 180° (should stay); flips the perigee latitude in the post-burn decay | keep omega when e > 0 | measured |
| L3 | `engine/lifetime.py:302-322` | a cancelled decay returns as if decided (no caller cancels today) | raise LifetimeError("cancelled") | read |
| L4 | `engine/lifetime.py:551` | lifetime after a run adds the initial fuel-tank load, not what is left | use the run's remaining tank mass | read |
| L5 | `engine/propellant_budget.py:744-749` | altitude-trade Cancel waits for the running sweeps (`with` waits on shutdown) | poll with a timeout; terminate workers | read |
| L6 | `cli.py` ccsds-export | OPM `MASS` is the dry mass (120 kg written for a 122 kg spacecraft) | write dry + propellant | run |
| L7 | `cli.py:866` | `--oem-stride 0` / `-3` accepted silently | argparse minimum 1 | run |
| L8 | `cli.py:404-407` | `budget --altitudes` silently overrides `--launch-delays` | mutually exclusive group | read |
| L9 | `cli.py:671-674`, `:747`, `:815`, `:285` | sil report and generate-* saves and Monte Carlo sidecar: write errors not caught | catch OSError | read |
| L10 | `cli.py` main | Ctrl-C prints a traceback | catch KeyboardInterrupt, exit 130 | read |
| L11 | `cli.py:70-82` | `validate` prints none of the GUI's plausibility warnings (perigee below ground, unusable TLE, no pass) | print them as WARNING lines | read |
| L12 | `schema/scenario.py:2407` | scenario files read with the locale encoding (Windows: mojibake or a UnicodeDecodeError traceback for hand-edited UTF-8 files) | `encoding="utf-8"`, also in `results.py:171` | read |
| L13 | `gui/autosave.py:146` | a non-UTF-8 recovery file raises at start-up | catch UnicodeDecodeError | run |
| L14 | `schema/references.py:153-170` | renaming a spacecraft misses `fsw_exports[].spacecraft` and condition strings; renaming a station misses its report series | extend the rename | read |
| L15 | `engine/vizard.py:731-732` | Vizard save-folder errors escape as raw OSError | wrap in VizardError | read |
| L16 | `src/utilities/vizSupport.py:830,912` (Basilisk) | `instrumentGuiSettingList` is never cleared between runs in one GUI session, so each Vizard run re-sends earlier runs' settings | needs a decision: clearing it touches a Basilisk module list (Q3) | read |
| L17 | `engine/geo_station_keeping.py:212` | `list.pop(0)` per step over a day of samples | `collections.deque` | read |
| L18 | `engine/kernels.py:154-161` | de430 (114 MB) SHA-256 hashed twice per build, about 1 s per run, segment and Monte Carlo case | cache the hash by size and mtime | read |
| L19 | `engine/earth_orientation.py:117-127, 193-205` | a manifest with an unknown key breaks every build; a failed fetch leaves `.part` | tolerate extra keys; clean up | read |
| L20 | `engine/ccsds_odm.py:563, 893-895` | equal consecutive OEM epochs accepted; empty series raises IndexError | refuse; guard | read |
| L21 | `engine/scenario_explainer.py:162, 436-443` | Explain tab: Earth radius used for any central body; any section error blanks the tab with no log | body radius; per-section guard + log | read |
| L22 | `fsw_export/generate.py:859-870` | a failed export leaves files without `manifest.json`; the next export then refuses the folder | write to a temp sibling, rename | read |
| L23 | `sil/runner.py:326` | Listener created outside the try (raw OSError) | move inside | read |
| L24 | `_offline.py:92-114` | the import-containment finder is not re-entrant: imported twice, two finders recurse (RecursionError, seen under a narrowed `--cov`) | re-entrancy guard | run |
| L25 | `logging_setup.py:110` | log file names have 1-second resolution; logs are never pruned | add pid; keep the last N | read |
| L26 | `dependencies.py:86` | `file_record` PermissionError after `stat()` | catch | read |
| L27 | `engine/service.py:300-335, 937-952` | GEO station-keeping thrust not counted in the two-body energy check; heliocentric eclipse uses the Sun as occulter | include; skip | read |
| L28 | `engine/mission_engine.py:548-691` | maneuvers and Lambert burns change velocity only (no propellant); the manual does not say so | document | read |
| L29 | schema | Monte Carlo bounds and run count not range-checked; version-0 files get "bug in SpaceMissionStudio"; `forecast_percentile` as text gives a plain ValueError | checks and messages | read |
| L30 | docs and docstrings | stale: `service.py:19-148`, `monte_carlo.py:132-156`, `orbit_maintenance.py:18-48`, `command.py:24`, `cli.py:33-40`, `plot_categories.py:24-31` (cites a non-existent report.py), `scenario_explainer.py` ("20 templates"; there are 27), `device_catalog.py:19-24, 70-73, 89` (says European only; has entries from India, Japan, Canada, Israel, Taiwan, South Africa and Ukraine; cites a function that does not exist), `packaging/install.sh:26-36` ("Basilisk-wheel path not verified") | update | read |

### 2.4 Checked and found sound

- **Full test suite:** 2721 passed, 10 skipped (Python 3.11, Basilisk
  2.12.0, PySide6 6.11.2, 8 min).
- **Static and generated checks:**
  - `ruff check`: clean.
  - The 5 compliance generators: no drift.
  - Regenerating all 27 templates: byte-identical files.
  - `sync_help`: the help copy is in sync.
- **GUI round trips:** all 27 templates loaded into the Scenario Editor
  and read back gave 0 differences. All 35 spacecraft opened in the
  Edit dialog and closed with OK gave 0 differences. The earlier
  data-loss class is closed.
- **Device catalog:** all 39 entries validate in a scenario. The 17
  refusals are the designed one-actuator-type rules.
- **Spacecraft templates:** the inertias recomputed from the box sizes
  are correct.
- **SIL:**
  - The session token is checked (HMAC compare).
  - The binary is re-hashed just before launch.
  - The socket folder is private (0700).
  - The contract parser checks lengths, CRC and port layouts.
- **Flight-software export:**
  - User text is escaped in C and CMake.
  - Removing a previous export cannot leave the folder.
  - The C templates have no `strcpy`/`strcat`/`sprintf`/unbounded scans
    (AGENTS rule 6).
- **Vizard archive extraction** refuses entries that leave the folder.
- **Long runs:** joins drop the duplicate boundary sample, and the epoch
  time zone is normalised.
- **Hyperbolic orbits** are refused. Unknown `--spacecraft` gives a
  clean error. `--altitudes` and `--drag-coeff` are range-checked.
- **Coverage:** 90.0 % of statements on 3.11. That run's tracer misses
  Python simulation modules called from Basilisk, which is why
  `geo_station_keeping` shows 37 % although its test fires real burns.
  `compliance/unreached_code.md` is measured with `COVERAGE_CORE=sysmon`
  on 3.12, which does see them, as that file says.

### 2.5 Not verified

- **Mission Sequences past 104 days with drag or eclipse:** I ran only
  the two cheaper models (M3).
- **The Vizard effect of L16:** it needs a Vizard display.
- **The Windows and macOS behaviour of M12, L12 and M15:** I tested on
  Linux only; the Windows claims come from code reading and the PR #42
  CI logs.
- **A clean install from scratch:** this belongs to the release check,
  after the fixes.
- **GUI code at line level:** I read the workers, main window flows,
  autosave, exports and Vizard fetch, ran the editor round trips and
  swept for swallowed exceptions. I did not read every line of the 20.7k
  lines of editors and widgets the way I read `engine/` and `schema/`.

### 2.6 Found while fixing

These came up after the report was approved, while fixing the findings
above.

**H5. A Monte Carlo batch can hang for ever after an earlier run in the
same process.** `engine/monte_carlo.py` (`run_monte_carlo`), Basilisk's
`Controller.executeSimulations`. The Controller forks a data-writer
process (and, with `thread_count > 1`, its workers) from the calling
process. If an earlier run's Basilisk simulation is still in memory as
uncollected garbage, the garbage collector in the child destroys it.
`SimModel`'s destructor then waits in `pthread_cond_destroy` on thread
state copied from the parent, and nothing ever releases it. In the test
suite the batch hung after earlier tests had run simulations. A py-spy
dump of the hung child showed it in
`SimModel::~SimModel → deleteThreads → pthread_cond_destroy`, called
from Basilisk's `DataWriter.run`. In the GUI, a normal run followed by a
Monte Carlo batch is the same situation. *Fix:* `gc.collect()` in the
parent just before the Controller forks, with a test that fails without
it. No Basilisk change. *Evidence:* run (hang reproduced, stack captured,
fixed).

**M17. A Monte Carlo folder with only file-manager clutter is
"not empty".** The empty-folder rule added for M10 counted `.DS_Store`,
`Thumbs.db`, `desktop.ini` and hidden folders as other files. *Fix:*
these are ignored. *Evidence:* run.

## 3. Method

- **What I read:**
  - Every file in `schema/`, `engine/`, `sil/` and `cli.py`, and the
    top-level package modules, line by line.
  - In `fsw_export/`, the parts that write files, build C literals and
    check exportability.
  - The C templates, by grep for unsafe calls and by reading their
    error paths.
- **GUI:** as in 2.5.
- **Other sources:** `pyproject.toml`, the installers and CI workflow,
  and the developer and user docs where findings touched them.
- **What I ran:** each finding marked "run", with the commands and the
  outcome given in its entry.
- **Environments:** the full suite on 3.11; the Basilisk-free part on
  3.10.

Working notes, inputs and scripts are in the session scratch folder
(`audit/notes.md`, `audit/run/`).

## 4. Decisions needed before fixing

- **Q1. Monte Carlo with a Mission Sequence (H1):** run the sequence in
  every Monte Carlo run, or refuse the combination?
- **Q2. Behaviour changes (BC):** may I refuse, at load time, files that
  load today?
  - H2: unknown wheel or thruster types; non-positive limits.
  - H3: names containing `/`, `\`, `..`, `.` or control characters,
    perhaps with a migration that renames them.
  - M3: Mission Sequences longer than 100 days.
  - M5: negative along-track distances.
  - M13: OPMs centred on another body; TLEs around other bodies.
  - M16: the values in its table.
  - M10: refusing a non-empty Monte Carlo folder.
- **Q3. Vizard settings list (L16):** clear Basilisk's
  `vizSupport.instrumentGuiSettingList` from our side before each run? It
  is a module-level list in Basilisk; clearing it changes no Basilisk
  file, but it does reach into its state. Or leave it and note it as a
  known issue?
- **Q4. Python support (M8):** keep `>= 3.9` and add 3.9 to CI, or raise
  the minimum (3.11 is all CI tests today)?
- **Q5. Release version:** the code is 2.0.0 with a large "Unreleased"
  changelog section (flight-software export, SIL, CCSDS, budgets, …).
  Which number should this release carry?
- **Q6. Device catalog (L30):** are the non-European catalog entries
  (from your supplier database) meant to stay?

## 5. Fix status

The answers to section 4: Q1 run the sequence; Q2 behaviour changes
accepted; Q3 clear the list before each run; Q4 Python 3.11 minimum; Q5
release 3.0.0; Q6 remove the non-European entries.

Every finding in section 2 is fixed. Each fix has a test whose
docstring names the finding (`grep -rn "Audit L12" tests/`), except:

- L28 and L30: documentation only (L30's catalog part has a test);
- L17: a performance change (`deque` instead of `list.pop(0)`) with the
  same behaviour, covered by the existing GEO station-keeping tests;
- M15: the lost ERROR frame is a Windows connection reset, which Linux
  does not reproduce. The SIL tests with a BSK_ERROR pass on Linux; the
  fix has not run on Windows.

Where the fix differs from the proposal:

| Finding | What was done instead |
|---|---|
| H3 | No migration renames old names; a file with such a name is refused with a message giving the rule. |
| M8 | Python 3.11 minimum (Q4), not 3.9 in CI. |
| L16 | Our side empties `vizSupport.instrumentGuiSettingList` in place before each Vizard run (Q3); no Basilisk file is changed. |
| L22 | The new export is generated in memory before the earlier one is removed; a failed write removes what it wrote. No temporary sibling folder. |
| L25 | Logs carry the process id, and only the newest 100 are kept: a behaviour change (logs used to be kept for ever). |
| L27 | A heliocentric run casts shadows only from the other tracked bodies. With none, there is no eclipse model (Basilisk's cannot run without a planet) and the spacecraft is always lit. Validation now accepts SRP or power around the Sun. |
| L30 (Q6) | The Ukraine entry stays: Ukraine is in Europe, which the catalog defines geographically. The audit's list named it in error. Seven entries removed (India, Taiwan, South Africa x2, Canada, Israel, Japan); 32 remain. |

Found while fixing, beyond section 2.6: the security analysis S-01 now
covers Monte Carlo (it flies the sequence since H1), and S-14 the new
export order (L22).

The release check (tests, clean install, what is still unverified) is in
section 6.

