# SpaceMissionStudio: Software Release Document (SRelD)

DRD: ECSS-E-ST-40C Annex G
Document: SMS-SRelD, issue 5, 2026-10-14. Remediation R14.

**Status:** release **1.0.0**, published 2026-10-14 (21:06 UTC).
- On 2026-10-14 the user chose to renew the tool and restart its
  numbering at 1.0.0. The releases made before (1.0.0, 1.1.0, 2.0.0
  and 3.0.0 of the earlier numbering) are withdrawn: on 2026-10-14 the
  repository had no releases and no tags left.
- 1.0.0 is released for Linux. Windows and macOS follow in a later
  release (the user's decision, 2026-10-14; 5.2, K-14).
- Tagged `spacemissionstudio-v1.0.0` (not signed, D-13) on commit
  `f288e0c73`, the merge of the release pull request (#68) into
  `develop`. GitHub release "SpaceMissionStudio 1.0.0", published by
  the user:
  <https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.0.0>.
- Its four files (the wheel, the sdist, the `.deb` and
  `SHA256SUMS-linux`) have the SHA-256 digests GitHub reports for them,
  and these equal the files built and installed for the release
  (`packaging/README.md`). The files were not downloaded back from the
  release.

## 1 Introduction (G.2.1<1>)

This SRelD describes release 1.0.0 of SpaceMissionStudio in
`0h3xn4/basilisk-SpaceMissionStudio`: what it contains, what changed since the last build
before the renewal (3.0.0 of the earlier numbering, commit `a84ae3784`), what is known to be
wrong, and how to use it.

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
| Baseline | Commit `f288e0c73` (`f288e0c7323b99fa26c2a5cb73d3f9c5bcfc9e5e`), the merge of the release pull request into `develop`, tagged `spacemissionstudio-v1.0.0`. Last build before the renewal: 3.0.0 of the earlier numbering, commit `a84ae3784`, 2026-10-12. |
| Reused software baseline | Basilisk 2.12.0 (PyPI), numpy, sgp4, pyerfa, PySide6, plotly (RD3); the tested versions are pinned in `packaging/constraints.txt` |
| Platform | Python 3.11 or newer |
| Delivery | Attached to the GitHub release: the wheel and sdist (`packaging/build_wheel.sh`), the Debian package (`packaging/build_deb.sh`) and `SHA256SUMS-linux`. GitHub's digest of each published file equals the SHA-256 of the file built and installed (status above). No Windows setup program in 1.0.0 (K-14) |
| Documentation | SUM and `USER_MANUAL.md`; the documents in `compliance/docs/` |
| Basilisk framework | Unchanged. Against `develop`, the branch changes only `SpaceMissionStudio/` and `.github/workflows/spacemissionstudio.yml` (`git diff --name-only origin/develop HEAD`). |

## 5 Status of the software configuration item

### 5.1 Evolution since previous version (G.2.1<5.1>)

`CHANGELOG.md` 1.0.0 describes the release as a whole. Against the last
build before the renewal (3.0.0, commit `a84ae3784`), the changes are in
RD1 from "Release 3.0.0" on. In summary:

**Features:**
- 3D spacecraft models (shapes and `.obj` groups) giving the mass,
  center of mass, inertia, facets and Vizard look, with an editor and
  template 28; the center of mass is now Basilisk's `r_BcB_B`;
- the UX work of `docs/ux-audit.md`: a new workspace and top bar; the
  scenario as a tree of forms; problems that take you to the field and
  name it by its form label; the Mission Sequence as a list, with steps
  that can be left out; a JSON page; one Run with a progress strip;
  named runs, toasts in place of most message boxes; a plot workspace
  with a shared time cursor; a searchable Events table; runs saved to
  disk and a Compare tab; a dark theme; use by keyboard alone; layouts
  for wide screens; the design system in `docs/DESIGN.md`;
- SIL runs started from Run.

**Fixed:** values from a file outside a field's range are flagged
instead of cut to the range; a problem in one form no longer hides the
others; switching the orbit type no longer changes the orbit silently;
PNG and SVG export of a plot.

**Changes users notice:** the main window's layout; `pip` and `apt` see
1.0.0 as older than the earlier 3.0.0, so that build is to be removed
before installing this one. Scenario files are unchanged.

### 5.2 Known problems and limitations (G.2.1<5.2>)

**Known problems (no SPR system exists, so these stand in for SPRs):**

| # | Problem | Effect | Ref. |
|---|---|---|---|
| K-01 | Closed: the drag figures published before F-07 and F-09 (5-year runs, re-entry from 300 km, launch-delay sweep, altitude trade, disposal, templates 05 and 21) were re-measured on Basilisk 2.12.0. Station-keeping and trade figures fall 12-20 %; HISTORY, the template 05 and 21 descriptions, the template 21 claim test and the drag make-up docstring now give the new values. The bundled space weather has also changed since some were published, and the re-measurement does not separate the two; the disposal figures move both ways, not explained | – | `compliance/drag_remeasure.md`; HISTORY.md |
| K-02 | The drag case of V-04 has an unexplained 1.6 % decay difference from GMAT (within tolerance) | Drag results carry it | `phase3_log.md` |
| K-03 | The time argument is TDB, not TAI (F-05) | About 0.1 m/day in LEO | `phase3_log.md` |
| K-04 | The field's GM and radius are the body's, not the field file's (F-03) | Centimetres per day | `phase3_log.md` |
| K-05 | During a live stream Vizard, a separate program, listens on port 5556; the tool opens no port. Earlier issues of the security analysis wrongly said Basilisk binds 5556 and 5570 on all interfaces | Exposure depends on Vizard's own binding, not checked | security analysis S-06 (corrected, decision 17) |
| K-06 | The Windows installer was not run by hand; 1.0.0 does not ship it (K-14) | Unknown | SValP 9 |
| K-07 | Closed (decision 19): SRS-P-09 and SRS-R-02 measured and met on the reference PC | – | SVR; `compliance/performance.md` |
| K-10 | Closed: the test suite failed on Windows (34 tests) and macOS (10 tests) in CI run 20. Four causes were tool defects (F-09 to F-12, fixed); the rest were tests that assumed Linux. Since commit `41b73b1c3` the suite passes on all three (2259 passed, 11 skipped, 0 failed; run 37854361784). The GUI has not been used by hand on Windows or macOS | – | SVR 4.6; `review_log.md` |
| K-11 | F-09, fixed: parallel runs could read a half-written space-weather file. Altitude trades with more than one worker and Monte Carlo runs with NRLMSISE-00 drag, made before the fix, may have used wrong solar activity | Those results are to be re-run | `review_log.md` F-09 |
| K-08 | Closed: the PNG/SVG export polled the page with overlapping asynchronous queries; a late timer tick read the cleared state (the CI tracebacks), and several answers could save the file twice. One query at a time now, late answers ignored (F-12) | – | `review_log.md` F-12 |
| K-09 | 1056 of the 2135 unit and integration test functions have no docstring (on 2026-10-14) | Weaker test documentation | `SUITP_test_cases.md` |
| K-12 | The Windows setup program is built, installed silently and the installed tool run on a GitHub Windows runner, including the installer's Python version check; the wizard has not been clicked through by hand and the GUI not opened on a real Windows machine. The graceful SIL close (M15) has not run on Windows. 1.0.0 does not ship the setup program (K-14) | Unknown for interactive use on Windows | `AUDIT.md` sections 5 and 6; `packaging/README.md` |
| K-13 | Closed: the bundled CelesTrak space weather (observations to 2025-07-20) was refreshed for this release: observations to 2026-10-11, updated 2026-10-12. Results of drag runs dated after 2025-07-20 change, because observed solar activity replaces the earlier forecasts | – | `spacemissionstudio/data/spaceweather/README.md` |
| K-14 | Addressed, under watch: platform test failures. On Windows, two tests fail intermittently in CI (PR #64, 2026-10-14; each passed on the same commit in another run). `test_the_altitude_trade_runs_its_altitudes_in_parallel_processes`: a worker hit a Basilisk error whose exception cannot be pickled, so its message is lost (cause not yet known; suspected: the cached space-weather file opened by one worker while another replaces it). `test_a_step_without_deadline_waits_while_earlier_steps_are_still_answered`: its fake flight software went over the 0.3 s step timeout on a loaded runner (a test margin). On macOS (PR #65, 2026-10-14), `test_forms_stay_at_a_readable_width` and `test_a_template_row_keeps_its_customize_button_close` fail their own precondition: Qt's `cocoa` platform fits the 2560 x 1440 test window to the runner's screen, so the page is 618 px wide and there is no wide screen to check (a test set-up problem, not the layout). Fixed on the ROE branch (PR #73, commit `f601576c1`, 2026-10-18): the test window is laid out with `WA_DontShowOnScreen`, which the screen does not constrain, and the fixture asserts its 2560 x 1440 size; macOS CI then passed both (3347 passed, 0 failed, 11 skipped, run 39165811899). On the release commit `f288e0c73` (run 38633749308) Windows passed (3224 passed, 16 skipped) and macOS failed these two (3229 passed, 2 failed, 11 skipped). By the user's decision 1.0.0 is a Linux release; Windows and macOS are fixed and released later. Windows pair addressed on 2026-10-18 (after PR #73): the SIL test's step timeout is 1 s against 30 ms answers (it was 0.3 s against 20 ms), and the altitude trade's lost message is a confirmed bug, now fixed: Basilisk's `BasiliskError` cannot be pickled (its module `_bskLogging` does not import by that name), so any Basilisk error in a worker arrived as a pickling error. Workers now send such an error as a `BudgetError` with its type, message and traceback. The suspected cause is removed too: a complete space-weather file is no longer replaced by a second worker's copy, which on Windows could meet the first worker opening it. The Basilisk error behind the 2026-10-14 failure was never seen, so its cause is not confirmed; if it recurs, its message now shows. macOS, 2026-10-19 (PR #75, run 39218996167): `test_the_keys_work_where_results_has_the_focus` timed out waiting for its window to become active (passed on the PR's previous commit). On macOS activation is per application, and the parallel test workers are separate processes whose windows can keep it from this one; the test now sets Qt's active window itself (`QApplication.setActiveWindow`), which is what the shortcut map checks. Not reproducible on Linux (offscreen activates every shown window); confirmed only by the next macOS CI runs. Windows, 2026-10-19 (PR #76, job 118026573080): `test_thousands_of_dropped_steps_never_block_the_link[tcp]` failed with "the flight software took no STEP for 10 s" at step 16172 of 20000; the other Windows job on the same commit and the one re-run passed. The fake flight software was waiting to read when the link closed, so the simulation side's send found the socket not writable for 10 s, or did not run for that long. Cause not confirmed: not reproduced on Linux in 60 runs under CPU overload. A related defect was confirmed and fixed: `SocketTransport.send` gave up as soon as its time had run out, before trying the socket again, so a stall of the simulation's own process counted as the flight software's silence. The send now counts its time from the last bytes the peer took and tries once more without waiting before it gives up (`test_a_stall_of_this_process_is_not_the_peers_silence`, which fails on the previous code). Whether this was the Windows failure is confirmed only if it does not recur | Windows: an altitude trade with several workers may have failed with an unexplained error; a recurrence now names the error. macOS: the wide-screen layout was not checked in CI until PR #73 | PR #64 and #65 comments |
| K-15 | Fixed (2026-10-19): a run around, or with a third body, `mars` or `jupiter` passed validation and then failed. The bundled DE430 ephemeris has the Mars and Jupiter system barycentres, not the planets: a `mars` run stopped the whole process with `SPICE(SPKINSUFFDATA)` (the GUI runs in its own process, so the app closed), and Basilisk has no body named `jupiter`. The schema now offers `mars barycenter` and `jupiter barycenter` (Basilisk gives them the planet's mass and radius) and refuses the two old names with the one to use; a test flies every offered body | A scenario with `mars` or `jupiter` could not be run, and in the GUI closed the app; no result was ever produced with them | `tests/test_central_bodies.py`; HISTORY.md |
| K-16 | Fixed (2026-10-19): a thermal sensor's heat balance used the solar flux at Earth's distance from the Sun on the epoch, whatever the central body. Basilisk's `sensorThermal` assumes 1366 W/m^2 at any distance, and the tool's correction of it took Earth's flux. The flux is now the one at the spacecraft's own distance from the Sun when the run starts (SPICE), for every central body | Thermal sensors around the Sun, Mercury or Venus ran too cold, and around Mars, Jupiter or Eros too hot: around Mars on 2030-01-01 they absorbed 1408 W/m^2 instead of 713 W/m^2. Runs around Earth or the Moon are unchanged | `tests/test_sensor_thermal_flux.py`; HISTORY.md |
| K-17 | Fixed (2026-10-19): coarse sun sensors read the Sun in the planet's shadow. Basilisk's `coarseSunSensor` takes the eclipse as an optional input and, with it unlinked, counts itself fully lit; the tool linked it for thermal sensors and solar panels but not for sun sensors. Both the per-sensor telemetry and the cluster behind the CSS sun-heading estimate now take the spacecraft's eclipse message | In eclipse, sun-sensor telemetry was as in sunlight (template 14: 0.73 in Earth's shadow, now 0.0), and the CSS sun-heading estimate kept the true Sun direction, which real sensors cannot see. Runs that never enter a shadow are unchanged | `tests/test_template_claims.py::test_14_css_estimate_settles_on_the_sun_axis_and_is_lost_in_the_shadow`; HISTORY.md |

**Waivers and deviations:** D-01 to D-13 (RD4). D-08 to D-13 are signed; D-01 to D-07
are not (decision 14, H08).

## 6 Operational aspects (G.2.1<6>)

- **Use Python 3.11 or newer and Basilisk 2.12.0.** Other Basilisk
  versions run, but with a warning: their results are not covered by
  the validation. The installers install the versions in
  `packaging/constraints.txt`.
- **Install the IERS-based Earth orientation files** for any run with a
  gravity field:
  - start-up prompt, or
  - `spacemissionstudio earth-orientation --fetch`.

  Without them, the Earth frame costs about 160 m/day at degree 20.
- **Re-run drag-dependent studies made with earlier versions.** F-07
  changes drag.
- **Run script blocks only from scenarios you trust and have read**
  (SUM 9.9).
- **Exchanging OEMs with GMAT R2026a:** use
  `run --oem-interpolation lagrange`, and convert to version 1.0
  (F-08).

## 7 Future evolutions (G.2.1<7>)

Planned, in order:
1. Windows and macOS: fix K-14, then release their installers.
2. The human actions of RD4: reviews, PA organisation, signatures.

Dropping the two Basilisk workarounds also depends on Basilisk: they go
once a qualified Basilisk release fixes F-01 and F-07 (H10).
