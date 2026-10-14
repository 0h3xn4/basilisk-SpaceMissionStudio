# SpaceMissionStudio: Software Release Document (SRelD)

DRD: ECSS-E-ST-40C Annex G
Document: SMS-SRelD, issue 4, 2026-10-14. Remediation R14.

**Status:** release **1.0.0**, prepared; not yet published.
- On 2026-10-14 the user chose to renew the tool and restart its
  numbering at 1.0.0. The releases made before (1.0.0, 1.1.0, 2.0.0
  and 3.0.0 of the earlier numbering) are withdrawn: on 2026-10-14 the
  repository had no releases and no tags left.
- 1.0.0 is released for Linux. Windows and macOS follow in a later
  release (the user's decision, 2026-10-14; 5.2, K-14).
- To be tagged `spacemissionstudio-v1.0.0` (not signed, D-13) on the
  merge of the release pull request into `develop`; GitHub release
  <https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.0.0>.

## 1 Introduction (G.2.1<1>)

This SRelD describes release 1.0.0 of SpaceMissionStudio in
`0h3xn4/basilisk-SpaceMissionStudio`: what it contains, what changed since the last build
before the renewal (3.0.0 of the earlier numbering, commit `a84ae3784`), what is known to be
wrong, and how to use it.

## 2 Applicable and reference documents (G.2.1<2>)

| Ref. | Document |
|---|---|
| RD1 | `HISTORY.md`: the change log, with an entry per change |
| RD2 | SVR (`SVR.md`): the verification and validation results of this candidate |
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
| Baseline | The merge of the release pull request into `develop`, tagged `spacemissionstudio-v1.0.0` (recorded here once published). Last build before the renewal: 3.0.0 of the earlier numbering, commit `a84ae3784`, 2026-10-12. |
| Reused software baseline | Basilisk 2.12.0 (PyPI), numpy, sgp4, pyerfa, PySide6, plotly (RD3); the tested versions are pinned in `packaging/constraints.txt` |
| Platform | Python 3.11 or newer |
| Delivery | Attached to the GitHub release: the wheel and sdist (`packaging/build_wheel.sh`), the Debian package (`packaging/build_deb.sh`) and `SHA256SUMS-linux`, checked after download. No Windows setup program in 1.0.0 (K-14) |
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
| K-09 | 988 of 1488 unit and integration tests have no docstring | Weaker test documentation | `SUITP_test_cases.md` |
| K-12 | The Windows setup program is built, installed silently and the installed tool run on a GitHub Windows runner, including the installer's Python version check; the wizard has not been clicked through by hand and the GUI not opened on a real Windows machine. The graceful SIL close (M15) has not run on Windows. 1.0.0 does not ship the setup program (K-14) | Unknown for interactive use on Windows | `AUDIT.md` sections 5 and 6; `packaging/README.md` |
| K-13 | Closed: the bundled CelesTrak space weather (observations to 2025-07-20) was refreshed for this release: observations to 2026-10-11, updated 2026-10-12. Results of drag runs dated after 2025-07-20 change, because observed solar activity replaces the earlier forecasts | – | `spacemissionstudio/data/spaceweather/README.md` |
| K-14 | Open: platform test failures. On Windows, two tests fail intermittently in CI (PR #64, 2026-10-14; each passed on the same commit in another run). `test_the_altitude_trade_runs_its_altitudes_in_parallel_processes`: a worker hit a Basilisk error whose exception cannot be pickled, so its message is lost (cause not yet known; suspected: the cached space-weather file opened by one worker while another replaces it). `test_a_step_without_deadline_waits_while_earlier_steps_are_still_answered`: its fake flight software went over the 0.3 s step timeout on a loaded runner (a test margin). On macOS (PR #65, 2026-10-14), `test_forms_stay_at_a_readable_width` and `test_a_template_row_keeps_its_customize_button_close` fail their own precondition: Qt's `cocoa` platform fits the 2560 x 1440 test window to the runner's screen, so the page is 618 px wide and there is no wide screen to check (a test set-up problem, not the layout). By the user's decision 1.0.0 is a Linux release; Windows and macOS are fixed and released later | Windows: an altitude trade with several workers may fail with an unexplained error. macOS: the wide-screen layout is not checked in CI | PR #64 and #65 comments |

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
