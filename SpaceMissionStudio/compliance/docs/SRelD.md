# SpaceMissionStudio: Software Release Document (SRelD)

DRD: ECSS-E-ST-40C Annex G
Document: SMS-SRelD, issue 12, 2026-10-21. Remediation R14.

**Status:** release **1.2.0**, published 2026-10-21 (17:20 UTC):
starting a mission from scratch, guided (the user's request and decision
of 2026-10-21, HISTORY "A mission from scratch, guided"), and the end of
macOS support (the user's decision of the same day, `docs/DECISIONS.md`).
What the tool computes is unchanged from 1.1.1: the changes to the engine,
the schema and the SIL transport since then are in comments only, and
the golden files are unchanged. Merging the release pull request, tagging
and publishing were the user's (decision of 2026-10-19, HISTORY "Towards
release 1.1.0").
- 1.2.0 ships the wheel, the sdist, the Linux `.deb` and the Windows
  setup program, built as 1.1.1's were (`packaging/` is unchanged but for
  `release_notes.py` and its README). macOS is not supported.
- Tagged `spacemissionstudio-v1.2.0` (a lightweight tag, not signed,
  D-13) on commit `c92f90040` (`c92f9004075bb28bbad361d55408b827670c0e1a`),
  the merge of the release pull request (#94) into `develop`. GitHub
  release "Space Mission Studio 1.2.0", published by the user:
  <https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.2.0>.
  It was created at 17:17 UTC and published at 17:20, before the release
  workflow had attached anything, so it was public without files or notes
  until the workflow finished at 17:33.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 39642864007](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/runs/39642864007),
  on `c92f90040`; jobs linux, windows and attach passed). GitHub's SHA-256
  digests: `.deb` (`spacemissionstudio_1.2.0_amd64.deb`, 446 730 028
  bytes) `92760538...0809`, setup program
  (`spacemissionstudio-1.2.0-setup.exe`, 394 968 402 bytes)
  `747bdee3...f3bc`, wheel (4 066 610 bytes) `db73117d...3d23`, sdist
  (4 177 942 bytes) `6b940d87...8a5d`, `SHA256SUMS-linux`
  `50ec7c8c...c4ed`, `SHA256SUMS-windows` `fec5c2f8...46e0`. The attach
  job checked every file against the two checksum files.
- The release notes are the first the workflow wrote itself
  (`packaging/release_notes.py`, from `CHANGELOG.md` 1.2.0; 6684
  characters). The installers' SHA-256 in them equal GitHub's digests
  above.

**Previous release:** 1.1.1, published 2026-10-21 (11:44 UTC), the
self-contained installers:
- Tagged `spacemissionstudio-v1.1.1` (annotated, not signed, D-13; tag
  object `40ddd47b1`) on commit `57a54ae92`
  (`57a54ae923a59be6301e1b5e5de8701598fd9996`), the merge of the release
  pull request (#90) into `develop`. GitHub release "Space Mission Studio
  1.1.1", published by the user:
  <https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.1.1>.
  A first tag and release, made before the release workflow had attached
  anything, were deleted by the user and the tag pushed again.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 39575072165](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/runs/39575072165)).
  GitHub's SHA-256 digests: `.deb` (`spacemissionstudio_1.1.1_amd64.deb`,
  446 895 932 bytes) `05f949f0...35a0`, setup program
  (`spacemissionstudio-1.1.1-setup.exe`, 395 017 481 bytes)
  `bf56ae39...9714`, wheel `c420515e...b509`, sdist `ac2cff10...43ff`,
  `SHA256SUMS-linux` `c5bdb53f...1f56`, `SHA256SUMS-windows`
  `f5f0d80d...c6de7`. The attach job checked every file against the two
  checksum files.
- Its release notes are those written for the user to paste (HISTORY,
  "Release notes that read like release notes").

Earlier: 1.1.0, published 2026-10-20 (tag `spacemissionstudio-v1.1.0` on
`1f8ad1663`, PR #86); its installers set up a virtual environment while
installing, needing internet access and, for the setup program, Python
3.11 on `PATH` (K-20).

## 1 Introduction (G.2.1<1>)

This SRelD describes release 1.2.0 of SpaceMissionStudio in
`0h3xn4/basilisk-SpaceMissionStudio`: what it contains, what changed since 1.1.1
(commit `57a54ae92`), what is known to be wrong, and how to use it.

## 2 Applicable and reference documents (G.2.1<2>)

| Ref. | Document |
|---|---|
| RD1 | `HISTORY.md`: the change log, with an entry per change |
| RD2 | SVR (`SVR.md`): the verification and validation results of this release |
| RD3 | SRF (`SRF.md`): the reused software baseline |
| RD4 | `compliance/deviations.md`, `compliance/human_actions.md` |
| RD5 | SUM (`SUM.md`) |

## 3 Terms, definitions and abbreviated terms (G.2.1<3>)

| Term | Meaning |
|---|---|
| SPR | Software problem report: here, a known open problem listed in 5.2 (no SPR system exists yet, H05) |
| SW&D | Software waiver and deviation: the deviations D-01 to D-13 |

## 4 Software release overview (G.2.1<4>)

| Item | Value |
|---|---|
| Configuration item | SpaceMissionStudio (`SpaceMissionStudio/` in the repository) |
| Baseline | Commit `c92f90040` (`c92f9004075bb28bbad361d55408b827670c0e1a`), the merge of the release pull request (#94) into `develop`, tagged `spacemissionstudio-v1.2.0`. Previous release: 1.1.1, commit `57a54ae92` (`57a54ae923a59be6301e1b5e5de8701598fd9996`), tagged `spacemissionstudio-v1.1.1`. |
| Reused software baseline | Basilisk 2.12.0 (PyPI), numpy, sgp4, pyerfa, PySide6, plotly (RD3); the tested versions are pinned in `packaging/constraints.txt`. Bundled with the GUI as files, not packages: Inter 4.1 and JetBrains Mono 2.304 (SIL OFL 1.1) and 35 Lucide icons from lucide-static 1.52.0 (ISC), with versions, sources and checksums in `docs/THIRD_PARTY_ASSETS.md`. The installers also carry CPython 3.11.17 (python-build-standalone 20261013, SHA-256 pinned) with every installed package and the reference data; each build lists them in its `SPACEMISSIONSTUDIO_RUNTIME.json`, and `docs/THIRD_PARTY_ASSETS.md` ("In the installers") gives their licences |
| Platform | The installers: Linux x86_64 with glibc 2.34 or newer (`.deb`), Windows 10/11 x64; no Python needed. From source: Python 3.11 or newer |
| Delivery | Attached to the GitHub release by the release workflow (`.github/workflows/spacemissionstudio-release.yml`): the wheel and sdist, the Debian package `spacemissionstudio_1.2.0_amd64.deb`, the Windows setup program `spacemissionstudio-1.2.0-setup.exe` (not signed, D-13), `SHA256SUMS-linux` and `SHA256SUMS-windows` |
| Documentation | SUM and `USER_MANUAL.md`; the documents in `compliance/docs/` |
| Basilisk framework | No Basilisk source, module or test changed. Since 1.1.1 the changes outside `SpaceMissionStudio/` (`git diff --name-only 57a54ae92 HEAD`) are the SpaceMissionStudio workflows (`.github/workflows/spacemissionstudio-*.yml`), the fork's `README.md` and, by the user's decisions of 2026-10-21 (PR #93), Basilisk's own CI: its workflows lost their macOS jobs (the docs, the docs deployment and the canary build run on Linux, the docs action installs Doxygen with apt), with a release-note snippet, and eight documentation paths whose letter case differed from their files (two module `.rst` files, the Vizard GUI page, two example scenarios' docstrings) were corrected so the docs build on Linux. The installers carry Basilisk 2.12.0 from PyPI, not this repository's framework, and add its support data next to the installed package, in the folder its own `dataFetcher` reads |

## 5 Status of the software configuration item

### 5.1 Evolution since previous version (G.2.1<5.1>)

`CHANGELOG.md` 1.2.0 lists the changes since 1.1.1 (commit `57a54ae92`);
RD1 has the full story ("A mission from scratch, guided", "macOS
removed", "Release notes that read like release notes"). In summary:

**GUI:** the Templates page opens with **Start from scratch**; a blank
scenario starts in *Orbit only*; its Scenario page has the **Build your
mission** guide (the steps to a first run with their state, and the rest
of the tool with a button to each page; `gui/mission_guide.py`,
`tests/gui/test_mission_guide.py`). The Spacecraft page has an empty
state, and Edit and Remove wait for a selection.

**Platforms:** macOS is no longer supported: the macOS CI job, the
release workflow's macOS check and the app's macOS-only code (Vizard's
macOS download and `.app` handling) are gone.

**Release workflow:** the notes are written by `packaging/release_notes.py`
from the CHANGELOG section, with the files' sizes and the installers'
SHA-256; the attach job alone waits for an earlier release run.

**Fixed:** a hint that pointed to a "Spacecraft > Add..." menu, which
does not exist, now names the Spacecraft page.

**Still open:** K-14 (PR #91 added the diagnostics a recurrence would
show) and K-22.

**Changes users notice:** the start-from-scratch choice and the guide; a
blank scenario (File > New Scenario included) now starts in *Orbit only*.
Scenario files and their results are the same as with 1.1.1.

### 5.2 Known problems and limitations (G.2.1<5.2>)

**Known problems (no SPR system exists, so these stand in for SPRs):**

| # | Problem | Effect | Ref. |
|---|---|---|---|
| K-01 | Closed: the drag figures published before F-07 and F-09 (5-year runs, re-entry from 300 km, launch-delay sweep, altitude trade, disposal, templates 05 and 21) were re-measured on Basilisk 2.12.0. Station-keeping and trade figures fall 12-20 %; HISTORY, the template 05 and 21 descriptions, the template 21 claim test and the drag make-up docstring now give the new values. The bundled space weather has also changed since some were published, and the re-measurement does not separate the two; the disposal figures move both ways, not explained | – | `compliance/drag_remeasure.md`; HISTORY.md |
| K-02 | The drag case of V-04 has an unexplained 1.6 % decay difference from GMAT (within tolerance) | Drag results carry it | `phase3_log.md` |
| K-03 | The time argument is TDB, not TAI (F-05) | About 0.1 m/day in LEO | `phase3_log.md` |
| K-04 | Radius part closed (2026-10-19): Basilisk put the body's radius in place of the field file's (F-03), which scaled Mars's GGM2B J2 by 4.8e-4 and Earth's by 1e-7. The tool now rescales the coefficients so that the file's field is applied (`engine/gravity_field.py`, `tests/test_gravity_field.py`). The field's GM is still the body's (D-07) | GM: 1.4e-8 (Earth) and 1.4e-6 (Mars) on the harmonic terms | `phase3_log.md` F-03 |
| K-05 | During a live stream Vizard, a separate program, listens on port 5556; the tool opens no port. Earlier issues of the security analysis wrongly said Basilisk binds 5556 and 5570 on all interfaces | Exposure depends on Vizard's own binding, not checked | security analysis S-06 (corrected, decision 17) |
| K-06 | The Windows setup program has not been run by hand on a Windows machine; 1.1.0 to 1.2.0 ship it, built, installed silently and run on a GitHub Windows runner (K-12) | Unknown for interactive use | SValP 9 |
| K-07 | Closed (decision 19): SRS-P-09 and SRS-R-02 measured and met on the reference PC | – | SVR; `compliance/performance.md` |
| K-10 | Closed: the test suite failed on Windows (34 tests) and macOS (10 tests) in CI run 20. Four causes were tool defects (F-09 to F-12, fixed); the rest were tests that assumed Linux. Since commit `41b73b1c3` the suite passes on all three (2259 passed, 11 skipped, 0 failed; run 37854361784). The GUI has not been used by hand on Windows or macOS | – | SVR 4.6; `review_log.md` |
| K-11 | F-09, fixed: parallel runs could read a half-written space-weather file. Altitude trades with more than one worker and Monte Carlo runs with NRLMSISE-00 drag, made before the fix, may have used wrong solar activity | Those results are to be re-run | `review_log.md` F-09 |
| K-08 | Closed: the PNG/SVG export polled the page with overlapping asynchronous queries; a late timer tick read the cleared state (the CI tracebacks), and several answers could save the file twice. One query at a time now, late answers ignored (F-12) | – | `review_log.md` F-12 |
| K-09 | Closed (2026-10-19): 1054 of the 2314 unit and integration test functions had no docstring. Every one now has a docstring stating what it checks, read from its body; no test code changed (each file's syntax tree without docstrings equals the one before) | – | `SUITP_test_cases.md`; HISTORY.md |
| K-12 | The Windows setup program is built, installed silently and the installed tool run on a GitHub Windows runner (1.1.1: with an empty support-data cache, the GUI opened offscreen); the wizard has not been clicked through by hand and the GUI not opened on a real Windows machine, and an upgrade over an installed 1.1.0 has not been tried. The graceful SIL close (M15) has not run on Windows | Unknown for interactive use on Windows | `AUDIT.md` sections 5 and 6; `packaging/README.md` |
| K-13 | Closed: the bundled CelesTrak space weather (observations to 2025-07-20) was refreshed for this release: observations to 2026-10-11, updated 2026-10-12. Refreshed again on 2026-10-19 for the next release: observations to 2026-10-18, CelesTrak's daily forecast to 2026-12-02, updated 2026-10-19 20:34 UTC. Results of drag runs dated after 2025-07-20 change, because observed solar activity replaces the earlier forecasts | – | `spacemissionstudio/data/spaceweather/README.md` |
| K-14 | Addressed, under watch: platform test failures. On Windows, two tests fail intermittently in CI (PR #64, 2026-10-14; each passed on the same commit in another run). `test_the_altitude_trade_runs_its_altitudes_in_parallel_processes`: a worker hit a Basilisk error whose exception cannot be pickled, so its message is lost (cause not yet known; suspected: the cached space-weather file opened by one worker while another replaces it). `test_a_step_without_deadline_waits_while_earlier_steps_are_still_answered`: its fake flight software went over the 0.3 s step timeout on a loaded runner (a test margin). On macOS (PR #65, 2026-10-14), `test_forms_stay_at_a_readable_width` and `test_a_template_row_keeps_its_customize_button_close` fail their own precondition: Qt's `cocoa` platform fits the 2560 x 1440 test window to the runner's screen, so the page is 618 px wide and there is no wide screen to check (a test set-up problem, not the layout). Fixed on the ROE branch (PR #73, commit `f601576c1`, 2026-10-18): the test window is laid out with `WA_DontShowOnScreen`, which the screen does not constrain, and the fixture asserts its 2560 x 1440 size; macOS CI then passed both (3347 passed, 0 failed, 11 skipped, run 39165811899). On the release commit `f288e0c73` (run 38633749308) Windows passed (3224 passed, 16 skipped) and macOS failed these two (3229 passed, 2 failed, 11 skipped). By the user's decision 1.0.0 is a Linux release; Windows and macOS are fixed and released later. Windows pair addressed on 2026-10-18 (after PR #73): the SIL test's step timeout is 1 s against 30 ms answers (it was 0.3 s against 20 ms), and the altitude trade's lost message is a confirmed bug, now fixed: Basilisk's `BasiliskError` cannot be pickled (its module `_bskLogging` does not import by that name), so any Basilisk error in a worker arrived as a pickling error. Workers now send such an error as a `BudgetError` with its type, message and traceback. The suspected cause is removed too: a complete space-weather file is no longer replaced by a second worker's copy, which on Windows could meet the first worker opening it. The Basilisk error behind the 2026-10-14 failure was never seen, so its cause is not confirmed; if it recurs, its message now shows. macOS, 2026-10-19 (PR #75, run 39218996167): `test_the_keys_work_where_results_has_the_focus` timed out waiting for its window to become active (passed on the PR's previous commit). On macOS activation is per application, and the parallel test workers are separate processes whose windows can keep it from this one; the test now sets Qt's active window itself (`QApplication.setActiveWindow`), which is what the shortcut map checks. Not reproducible on Linux (offscreen activates every shown window); confirmed only by the next macOS CI runs. Windows, 2026-10-19 (PR #76, job 118026573080): `test_thousands_of_dropped_steps_never_block_the_link[tcp]` failed with "the flight software took no STEP for 10 s" at step 16172 of 20000; the other Windows job on the same commit and the one re-run passed. The fake flight software was waiting to read when the link closed, so the simulation side's send found the socket not writable for 10 s, or did not run for that long. Cause not confirmed: not reproduced on Linux in 60 runs under CPU overload. A related defect was confirmed and fixed: `SocketTransport.send` gave up as soon as its time had run out, before trying the socket again, so a stall of the simulation's own process counted as the flight software's silence. The send now counts its time from the last bytes the peer took and tries once more without waiting before it gives up (`test_a_stall_of_this_process_is_not_the_peers_silence`, which fails on the previous code). Whether this was the Windows failure is confirmed only if it does not recur. It recurred on 2026-10-21 (PR #90, job 119083739177, on the 1.1.1 release commit `9dca37d5f`): the same message at step 10907 of 20000, and again the fake flight software was waiting to read when the link closed. So the send's stall handling was not the cause, and the cause is still not known. Not a Basilisk thread holding Python's interpreter lock: a Basilisk run in a second thread let the other thread run at least every 0.03 s (measured on Linux). Only this test has shown it (20000 steps, every one dropped, over TCP on a Windows runner); it may also stop a Windows SIL session that drops thousands of steps, with "the flight software took no STEP for 10 s". Not reproduced since (PR #91, 2026-10-21): the test alone passed 240 times on `windows-latest` (four workers side by side, two processes keeping the CPU busy) and the whole suite passed seven times on Windows (six runs of the new workflow "SpaceMissionStudio SIL stress (Windows)" and the platforms job). On a stall the test now fails with the state of both ends of the link: frames sent and dropped, bytes received and not read, the socket buffer sizes, what the fake flight software last did, when, and its stack, and the last `select()` calls of the send. The next recurrence names its cause | Windows: an altitude trade with several workers may have failed with an unexplained error; a recurrence now names the error. macOS: the wide-screen layout was not checked in CI until PR #73 | PR #64 and #65 comments |
| K-15 | Fixed (2026-10-19): a run around, or with a third body, `mars` or `jupiter` passed validation and then failed. The bundled DE430 ephemeris has the Mars and Jupiter system barycentres, not the planets: a `mars` run stopped the whole process with `SPICE(SPKINSUFFDATA)` (the GUI runs in its own process, so the app closed), and Basilisk has no body named `jupiter`. The schema now offers `mars barycenter` and `jupiter barycenter` (Basilisk gives them the planet's mass and radius) and refuses the two old names with the one to use; a test flies every offered body | A scenario with `mars` or `jupiter` could not be run, and in the GUI closed the app; no result was ever produced with them | `tests/test_central_bodies.py`; HISTORY.md |
| K-16 | Fixed (2026-10-19): a thermal sensor's heat balance used the solar flux at Earth's distance from the Sun on the epoch, whatever the central body. Basilisk's `sensorThermal` assumes 1366 W/m^2 at any distance, and the tool's correction of it took Earth's flux. The flux is now the one at the spacecraft's own distance from the Sun when the run starts (SPICE), for every central body | Thermal sensors around the Sun, Mercury or Venus ran too cold, and around Mars, Jupiter or Eros too hot: around Mars on 2030-01-01 they absorbed 1408 W/m^2 instead of 713 W/m^2. Runs around Earth or the Moon are unchanged | `tests/test_sensor_thermal_flux.py`; HISTORY.md |
| K-17 | Fixed (2026-10-19): coarse sun sensors read the Sun in the planet's shadow. Basilisk's `coarseSunSensor` takes the eclipse as an optional input and, with it unlinked, counts itself fully lit; the tool linked it for thermal sensors and solar panels but not for sun sensors. Both the per-sensor telemetry and the cluster behind the CSS sun-heading estimate now take the spacecraft's eclipse message | In eclipse, sun-sensor telemetry was as in sunlight (template 14: 0.73 in Earth's shadow, now 0.0), and the CSS sun-heading estimate kept the true Sun direction, which real sensors cannot see. Runs that never enter a shadow are unchanged | `tests/test_template_claims.py::test_14_css_estimate_settles_on_the_sun_axis_and_is_lost_in_the_shadow`; HISTORY.md |
| K-18 | Fixed in 1.1.0 (2026-10-20, before its publication): a Monte Carlo batch started from the GUI with `thread_count` 1 (the default, and template 09) failed every run. Basilisk's `MonteCarlo.Controller` calls `signal.signal()` at the start of each case, which Python allows only on a process's main thread, and with one thread the controller runs the cases in the calling process: the GUI's worker `QThread`. The GUI now runs the batch in a spawned child process (`gui/monte_carlo_process.py`); Basilisk is unchanged | In 1.0.0 and the first 1.1.0 candidate, GUI batches with one thread produced no results ("N of N runs failed"). The command line runs batches on its main thread and is not affected; with more than one thread each case runs in a pool process, so GUI batches should not have been affected either (read from the controller, not re-run on 1.1.0). Found by the UI screenshot harness | `tests/gui/test_run_worker.py::test_monte_carlo_worker_runs_a_single_thread_batch`; HISTORY.md |
| K-19 | Limitation (2026-10-20): applying a theme (View > Theme, or a change of the desktop's scheme with System) takes 0.51-0.55 s on a new main window with a scenario open and 2.4 s after every page has been visited, measured on one Linux container (before M1, on the same machine: 1.31-1.44 s and 6.1-6.5 s). The overhaul brief's target is 0.1 s. Qt re-polishes every widget, most of them on hidden pages; the overhaul's next milestone reduces the number of live widgets | The window does not respond for that time after a theme change | `docs/DECISIONS.md`; `docs/ui/UI_OVERHAUL_PLAN.md` section 7 |
| K-20 | Fixed in 1.1.1 (2026-10-20): the 1.1.0 installers built a virtual environment while installing. The setup program stopped before its wizard when no Python 3.11 was on `PATH` ("SpaceMissionStudio needs Python 3.11 or later, which was not found"), and both needed internet access. The `.deb`'s `postinst` also fetched the SPICE kernels as root, into root's own cache (`~/.cache/bsk_support_data` of root), so every other user had no kernels until they downloaded them. The 1.1.1 installers carry their own Python and the data, in the folder Basilisk's `dataFetcher` reads for every user | 1.1.0: no install on a Windows machine without Python 3.11 on `PATH`; no offline install; Linux users other than root had to download the kernels | `packaging/README.md`, "The bundled Python"; HISTORY.md |
| K-21 | Fixed (2026-10-21): `test_autosave.py::test_read_with_no_recovery_file_returns_none` failed now and then on Windows CI (PR #89). A main window an earlier GUI test had left open kept its 30 s autosave timer; pytest-qt processes Qt events after each test's set-up, so the overdue tick wrote that window's scenario into the recovery file the test had just pointed at its temporary folder. Reproduced with a window holding template 22, as in the failure; the test now stops such timers first. A test defect: the app writes its recovery file only where it should | None for users | `docs/ui/TEST_CHANGES.md`; HISTORY.md |
| K-22 | Open (2026-10-21): on Windows CI a test worker crashed with "Windows fatal exception: access violation" in `tests/gui/test_template_wizard.py::test_wizard_is_sized_to_fit_its_own_busiest_page_not_a_flat_default[17_fuel_tank_depletion.json]` (PR #91, job 119157936897, commit `895ebcb96`); the other 3557 tests passed. The Python stack ends in pytest's call of the test, with no frame inside it, so the crash came in native code as the test returned, most likely when Python freed a Qt object whose C++ side Qt had already deleted. Seen once: the other seven whole-suite Windows runs of the same commit passed, and the file passed three times on Linux. The test and the wizard did not change in that PR. Cause not known | A crash of this kind could also end the app on Windows; none has been reported | PR #91 comment; HISTORY.md |

**Waivers and deviations:** D-01 to D-13 (RD4). D-08 to D-13 are signed; D-01 to D-07
are not (decision 14, H08).

## 6 Operational aspects (G.2.1<6>)

- **Use the installers, or Python 3.11 or newer with Basilisk 2.12.0.**
  The installers carry Python 3.11.17, Basilisk 2.12.0 and the versions
  in `packaging/constraints.txt`. Other Basilisk versions run, but with a
  warning: their results are not covered by the validation.
- **Earth orientation:** the installers carry the IERS-based files as
  current as their build; for later runs, fetch newer ones:
  - start-up prompt, or
  - `spacemissionstudio earth-orientation --fetch`.

  Installed from source, install them before any run with a gravity
  field. Without them, the Earth frame costs about 160 m/day at degree 20.
- **Re-run drag-dependent studies made with earlier versions.** F-07
  changes drag.
- **Run script blocks only from scenarios you trust and have read**
  (SUM 9.9).
- **Exchanging OEMs with GMAT R2026a:** use
  `run --oem-interpolation lagrange`, and convert to version 1.0
  (F-08).

## 7 Future evolutions (G.2.1<7>)

Planned, in order:
1. Windows: fix K-14 and K-22, and run the installers by hand (K-06,
   K-12).
2. The human actions of RD4: reviews, PA organisation, signatures.

Dropping the two Basilisk workarounds also depends on Basilisk: they go
once a qualified Basilisk release fixes F-01 and F-07 (H10).
