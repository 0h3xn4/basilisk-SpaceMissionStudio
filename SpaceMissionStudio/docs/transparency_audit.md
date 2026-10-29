# Transparency audit (Phase 0)

**Status:** for review. No code has been changed. Nothing in this document has been implemented
yet. The implementation plan (Section 9) waits for your review.

**Scope:** SpaceMissionStudio 1.3.1+ (develop at 20d80d67a, 2026-10-29), the whole package
`spacemissionstudio/`: engine, schema, CLI, GUI, flight-software export, SIL and 3D models. About
74 000 lines in 191 modules. The Basilisk framework itself is outside the scope of changes, but
where SpaceMissionStudio relies on a Basilisk default, that default is listed.

**Reader:** spacecraft systems engineers and the people who will implement the plan. Every
finding gives a file and line (relative to `SpaceMissionStudio/spacemissionstudio/` unless the path
says otherwise), so it can be checked.

## Contents

1. [How the audit was done](#1-how-the-audit-was-done)
2. [Summary](#2-summary)
3. [Defects found during the audit](#3-defects-found-during-the-audit)
4. [Hard-coded constants, defaults, margins, thresholds and rules](#4-hard-coded-constants-defaults-margins-thresholds-and-rules)
5. [Hidden assumptions](#5-hidden-assumptions)
6. [Outputs shown without their derivation](#6-outputs-shown-without-their-derivation)
7. [Places where the user is forced into one option](#7-places-where-the-user-is-forced-into-one-option)
8. [Inputs and outputs exchanged with other tools and files](#8-inputs-and-outputs-exchanged-with-other-tools-and-files)
9. [Prioritized implementation plan](#9-prioritized-implementation-plan)
10. [Decisions needed from you](#10-decisions-needed-from-you)
- [Appendix A: Orbital dynamics, environment, time and frames](#appendix-a-orbital-dynamics-environment-time-and-frames)
- [Appendix B: Mission-analysis calculations](#appendix-b-mission-analysis-calculations)
- [Appendix C: Scenario schema, CLI, interfaces and reproducibility](#appendix-c-scenario-schema-cli-interfaces-and-reproducibility)
- [Appendix D: GUI](#appendix-d-gui)
- Companion file: [`transparency_audit_constants.csv`](transparency_audit_constants.csv), every numeric literal in the package

---

## 1. How the audit was done

1. **A mechanical inventory of every number in the code.** A script walked the syntax tree of
   every module and recorded each numeric literal with its file, line, enclosing definition, kind
   and any `[unit]` comment. It found 9888 literals. 6247 of them are trivial (0, ±1, 2, 0.5) and
   567 are screen layout or appearance. The remaining **3074** are listed in
   [`transparency_audit_constants.csv`](transparency_audit_constants.csv). Each row has a
   heuristic class: engineering value or rule (2441), unit conversion (198), formatting or
   rounding (95), index or count (312), status or version code (28). The class is a first sort
   for triage, not a verdict. The engineering rows still need to be judged one by one, which
   Phase 3 of the plan does.
2. **Four reviews by area**, each reading the code (no GUI was launched, no file changed):
   - **A.** Orbital dynamics, environment, time and frames.
   - **B.** Mission-analysis calculations: lifetime, budget, link, power, data, formations, Monte
     Carlo, flight software.
   - **C.** Scenario schema, CLI, every exchange with files, the network and the environment,
     reproducibility, scripting and extensibility.
   - **D.** GUI.

   Their full findings are Appendices A to D.
3. **Verification.** The findings that matter most were checked again against the code. Where a
   finding was in doubt, it was checked by running the code: the orbit-number defect (3.1) was
   reproduced numerically. Findings that were inferred and not checked are marked
   **unverified**. Values read from Basilisk's source are marked **(B)**. The reviewer read a
   2.13.0b0 source tree, while the tool is qualified with 2.12.0, so (B) values are unverified
   for 2.12.0.

What the audit does not do: it does not judge whether each model is adequate for a given
mission, and it does not re-validate numerical accuracy. Accuracy evidence lives in
`compliance/validation/` and `compliance/docs/SVR.md`.

---

## 2. Summary

### 2.1 The picture in numbers

| Item | Count | Where |
|---|---|---|
| Numeric literals that are not trivial and not layout | 3074 | CSV |
| ... of which carry a `[unit]` comment (engine / schema / GUI) | 23 % / 21 % / 5 % | CSV (units may also be in names) |
| Scenario fields (all visible and editable in the scenario file and the GUI's JSON mode) | 317 | C (a) |
| ... whose snake_case name never appears in the user documentation | 211 | C (a) |
| ... with no unit in the generated interface document (ICD) | 109 | C (a) |
| Validation rules in the schema | 361, 50 of them with a numeric limit that is stated only in the error message | C (a) |
| Engine defaults behind open `params` dictionaries, not written to the scenario file or the provenance | 36 in `engine/fsw.py`, plus Basilisk module and factory defaults | C (a), (h) |
| Hard-coded engineering values reviewed by hand (dynamics + analysis) | about 340 | A 1, B 1 |
| Hidden assumptions listed | about 85 | A 2, B 2 |
| Computed outputs reviewed in the GUI | 31 | D 1 |
| Pre-run checks with all four parts (rule, why it matters, actual vs limit, fix) | 3 of 28 | B 7 |
| Exchanges with files, the network, other programs or the environment | 38 | C (c) |

### 2.2 What already exists (the baseline to build on)

The tool is not a black box everywhere. The plan should extend what follows, not replace it:

- **Run provenance** (`engine/results.py:60-140`) records:
  - tool, Basilisk and dependency versions, and whether the Basilisk version is the qualified
    one;
  - run start, integrator, step and tolerances;
  - the seed and every derived model seed;
  - the scenario SHA-256;
  - every data file with its size and SHA-256 (32 MB and under);
  - time scales, frame definitions and the frame of each series.

  It is written next to CSV exports and embedded in PNG and SVG plots.
- **The propellant budget** (`engine/propellant_budget.py`, `gui/budget_widget.py`) is close to
  the target already: every row has a margin and a source column, every constant names its ESA
  AD10 section, and notes flag off-guideline settings.
- **Reference data panel** (`engine/reference_data.py`, `gui/data_panel_widget.py`): every data
  file with its source URL, size, SHA-256, coverage, install time and stale flag. Downloads only
  with consent, with manifests and rollback.
- **Flight-software export** (`fsw_export/`): a full hash manifest. Stale and modified exports are
  detected and named.
- **Scenario format**: every default is written into the saved file; unknown fields and wrong
  types are refused by name; saves are atomic.
- **Explain (Scenario › Overview)** with "Check before running" warnings, the gravity-fidelity
  note citing ECSS-E-ST-10-04C 4.2.1b, and ROE passive-safety notes.
- **The link-budget breakdown** on the mission dashboard (EIRP, FSPL, pointing loss, C/N0,
  Eb/N0, margin).
- **The device catalog** gives a source URL, heritage and the conversion arithmetic for each of
  its 32 entries.
- **Compare › Inputs**: a full input diff between two runs.
- **3D-model mass properties**: computed, typed or imported, with the source file's SHA-256 and a
  warning when out of date.
- **Refusals instead of silent extrapolation**: beyond Earth-orientation or space-weather
  coverage, a missing or corrupt kernel, NaN states.

### 2.3 The ten largest gaps against the definition of done

1. **A run folder cannot reproduce itself.** `run --out-dir` writes results and `provenance.json`
   but not the scenario. The recorded hash is of a canonical re-serialisation after migration, so
   it does not match `sha256sum` of the file (`output_provenance.py:80-84`). Values that come from
   engine defaults (open `params`, inertia-scaled control gains, Basilisk factory parameter sets)
   are recorded nowhere. Runs over 100 days record the first segment's provenance
   (`engine/long_run.py:203-204`).
2. **Most results cannot be traced from the GUI.** The Overview cards show a value and a unit;
   their derivation exists only in a code docstring (`engine/run_summary.py:20-41`). Lifetime
   results do not show the Cd, area, ballistic coefficient or the 120 km re-entry criterion used.
   The provenance popover reduces data-file hashes, frames and time scales to "N entries"
   (`gui/run_history_view.py:126-131`).
3. **Constants live in code**, often duplicated with different values:
   - three sets of Earth constants (μ, J2, radius);
   - two solar fluxes (1361 and 1368 W/m² (B));
   - three Earth radii behind the "altitude" shown in different views.

   Margins and thresholds (AD10 factors, 0 dB link closure, 120 km and 100 km re-entry, 5° pointing
   convergence, 0.99 sunlit threshold) cannot be changed without editing code.
4. **One fixed model in most places.** One ephemeris (DE430), one gravity field per body, one
   lifetime model, one margin policy (AD10), one link-loss model (free space only), one power
   model (no degradation), one shadow-casting body (the central body), sample-quantised event
   times.
5. **Hidden overrides.**
   - The CLI and GUI lifetime replace the spacecraft's Cd with 2.2, and the scenario's
     solar-activity percentile with 50, without printing either (`cli.py:455-458`).
   - The control gains the GUI shows (K 3.5, P 30) are not the ones applied: the engine scales
     them by inertia/900 (`engine/fsw.py:208-226`).
   - Old scenario files are migrated silently (`schema/migrations.py:47-99`).
   - "Bundled" space weather silently follows a newer download (`engine/spaceweather.py:631-652`).
6. **Warnings do not explain themselves.** Only 3 of 28 pre-run checks give the rule, why it
   matters, the actual against the limit, and the fix. Six omit a threshold the code applies. Any
   check that raises an exception is silently skipped (`engine/scenario_checks.py:304-312`).
   Every run warning gets the same "numerical drift" tooltip (`gui/results_widget.py:330-334`).
7. **No change history and no override flags.** Undo is in memory, unlabelled and lost on close.
   Values computed into fields (SSO inclination, RAAN for an LTAN, wizard altitudes, catalog
   presets) are not marked as computed or as overridden afterwards. The scenario has no author,
   revision or change log (`schema/scenario.py:2681-2722`).
8. **Some outputs have no provenance and no export:**
   - CLI `lifetime`, `budget` and the run summaries print with no provenance;
   - lifetime results cannot be exported at all;
   - the Monte Carlo runs CSV, Vizard files, the OBJ export and table copies carry no provenance;
   - the run warnings are not written with the CSV export (`engine/results.py:286-312`).
9. **Not extensible without code changes.** There is no plugin or registry mechanism. Sensor,
   actuator, model, rule and command kinds are closed lists in `schema/scenario.py` and
   `schema/command.py`.
10. **No API reference.** The Python API works and is exercised by five tested examples, but there
    is no reference documentation and no statement of what is stable (`engine/__init__.py` is
    empty). Run comparison, space-weather download and the template wizard exist only in the GUI.

---

## 3. Defects found during the audit

The audit found results that are wrong or misleading, beyond missing transparency. Per your
constraint, each will be fixed with a regression test first and a before/after record in
`docs/changes.md`. They are Phase 1 of the plan. None is fixed yet.

| # | Defect | Evidence | Effect |
|---|---|---|---|
| 3.1 | **Orbit-number axis uses Earth's μ for every central body** (`engine/orbit_number.py:81`, called without μ at `:124`) | **Reproduced numerically** on a circular 400 km Mars orbit over 2 days. Samples every 60 s and 300 s give 24.41, correct. Every 600 s gives **312.41**, every 1800 s gives **216.41** (true: 24.41) | Wrong orbit numbers on the Results x-axis for non-Earth runs recorded sparsely |
| 3.2 | **`monte-carlo` exits 4 when some runs fail** (`cli.py:364-366`); ICD-02 assigns 4 to an internal error since #146 | Read in the code | A script cannot tell a failed batch from a fault. `fsw-status` and `sil --max-error` similarly return 2, ICD-02's "missing component or usage error" (`cli.py:879, 917`) |
| 3.3 | **Runs over 100 days record segment 0's provenance**: scenario hash of a modified copy, segment 0's seeds, and the intermediate space-weather CSV instead of the original files (`engine/long_run.py:203-204, 247-258`) | Read in the code | The provenance of every long run is wrong in three fields |
| 3.4 | **Control gains shown are not the gains applied.** The GUI shows K = 3.5, P = 30 as the default; the engine applies them × trace(I)/3/900, so K = 0.039 and P = 0.33 for the default spacecraft (`engine/fsw.py:208-226`; `gui/param_form.py:176-190`) | Read in the code | An engineer reading the GUI gets gains 90 times too large for the default spacecraft |
| 3.5 | **The run summary's delta-V omits the ROE formation controller** (`engine/run_summary.py:67`; the controller writes `{sc}.roe_formation.delta_v`, `engine/roe_formation.py:820`) | Read in the code | Overview and Compare under-report delta-V for ROE formations; propellant is still right |
| 3.6 | **The "low-accuracy predicted Earth orientation" note never reaches run warnings**: only notes containing three specific phrases are passed on (`engine/service.py:2306-2307`) | Read in the code | A run on predicted EOP gives no warning in the results |
| 3.7 | **A new Monte Carlo dispersion defaults to dry mass uniform in [0, 1] kg**, written as an absolute value (`gui/monte_carlo_editor.py:152-153`; `engine/monte_carlo.py:245`) | Read in the code | An untouched "Add" makes every run a 0 to 1 kg spacecraft |
| 3.8 | **Wrong help text**: "~6778 km is a ~500 km-altitude LEO with a ~95 min period" (`gui/orbit_ic_widget.py:212`); 6778 km is 400 km altitude and a 92.6 min period | Arithmetic | Misleads users sizing an orbit |
| 3.9 | **Ground-station receive gain defaults differ**: 0 dBi in the schema (`schema/scenario.py:2375`), 45 dBi for a new station in the GUI (`gui/ground_station_editor.py:106`) | Read in the code | The same station, made two ways, closes a link differently by 45 dB |
| 3.10 | **The `RFLinkConfig` docstring is stale**: it says there is no pointing loss and no feedback into the physics (`schema/scenario.py:539-548`). Both exist (`:557-566`; `engine/data_handling.py:36-46`) | Read in the code | The generated ICD and API docs describe a model that is not the one run |
| 3.11 | **Pre-run checks that raise are silently dropped** (`engine/scenario_checks.py:304-312, 449-452`) | Read in the code | A broken check looks like a passed check |
| 3.12 | **One tooltip for every run warning**, blaming numerical drift (`gui/results_widget.py:330-334, 1014`) | Read in the code | A space-weather or re-entry warning is explained as an integrator problem |
| 3.13 | **A `stop_epoch_utc` step uses a UTC calendar difference on the elapsed-seconds clock** (`engine/mission_engine.py:342-345`) | Read in the code | Off by any leap second inserted between the two dates; minor |

Two further findings are model limitations rather than defects. They are listed as assumptions in
Section 5, for you to decide on:
- **Only the central body casts shadows** (`engine/service.py:997-1000`), so lunar eclipses of an
  Earth orbiter are not modelled even with the Moon as a third body.
- **Uncontrolled re-entry disposal is computed from the initial orbit**, not the end-of-life
  orbit (`engine/propellant_budget.py:269-270`).

---

## 4. Hard-coded constants, defaults, margins, thresholds and rules

### 4.1 Where to find every one

- **Every numeric literal**, with file and line, is in
  [`transparency_audit_constants.csv`](transparency_audit_constants.csv) (3074 rows).
- **The ones that matter for results** were reviewed by hand, with what each controls, whether
  the user can see it and change it, and the source the code cites:
  - dynamics and environment: Appendix A, Section 1 (about 150 rows in nine tables);
  - mission analysis: Appendix B, Section 1 (about 190 rows);
  - every scenario field default and every validation rule: Appendix C, tables A.0 to A.2;
  - every GUI default, suggestion and field range: Appendix D, Section 2.

### 4.2 The classes of hard-coded values

| Class | Examples (file:line) | Visible? | Editable without code? | Source given? |
|---|---|---|---|---|
| **Scenario defaults** (317 fields) | Cd 2.2, Cr 1.3, areas 1 m² (`schema/scenario.py:1813-1818`); step 10 s (`:2599`); min elevation 10° (`:2371`); link implementation loss 2 dB and required Eb/N0 6 dB (`:554-556`) | Yes: written into every saved file | **Yes** | Mostly no (24 have no unit comment; 211 are not in the user docs) |
| **Engine defaults behind open `params`** | CSS field of view 90°, sensor noise 0, `sHatBdyCmd` +Z, `minUnitMag` 0.1 (`engine/fsw.py:345, 412-413, 522-535`); Basilisk thruster Isp 100 s and MinOnTime 0.02 s when unset (B) | **No** | Only by knowing the key | No |
| **Physical constants** | μ⊕ 398600.436 km³/s² (Basilisk) vs 3.986004415e14 m³/s² (`engine/scenario_checks.py:54`, `engine/environment_models.py:57`); J2 1082.616e-6 vs 1.0826e-3 vs 1.08263e-3; Earth radius 6378.1366 / 6378.137 / 6378.0 km; solar flux 1361 vs 1368 W/m² (B); g0 9.80665 m/s² (11 literals in 7 modules); TT−UTC fixed at 69.184 s (`engine/orbit_design.py:129`, `engine/scenario_checks.py:57`) | No | No | Some (Basilisk, CODATA, IAU, ECSS) |
| **Margin policies** | AD10: CAM count ×4, attitude propellant +100 %, last controlled burn +15 %, residual 1 %, uncertainty 2 %, system margin 15 % (`engine/propellant_budget.py:88-102`; `schema/scenario.py:1521-1522`) | Yes (margin column) | System margin and inputs yes; factors **no** | **Yes** (AD10 sections) |
| **Pass/fail thresholds** | 5 and 25 years (`engine/lifetime.py:76-77`); link closed at margin ≥ 0 dB (`engine/data_handling.py:149`); battery empty at 0 W·h, link card at 0 dB (`gui/results_overview.py:49-57`); pointing "Converged" below 5° (`gui/mission_dashboard_widget.py:368`) | Labels only | **No** | Rules named (Zero Debris, IADC), values not cited |
| **Model thresholds** | Re-entry 120 km in the lifetime and budget (`engine/lifetime.py:70`), 100 km in the run (`engine/service.py:158`); umbra below 0.01 illumination (`engine/events.py:64`); thrust allowed above 0.99 illumination (`schema/scenario.py:845`); GEO J22 and λ22 (`engine/geo_station_keeping.py:79-80`) | Rarely | Some (sunlit threshold) | Mostly no |
| **Numerical settings** | Integrator tolerances 1e-10 / 1e-8 (`engine/service.py:117-118`); one task rate for all models; segment length 90 days (`engine/long_run.py:67`); CSV format `%.9g` (`engine/results.py:191`); plot thinning to 10 000 points (`gui/results_widget.py:256`) | Provenance (tolerances) or not at all | No | Own studies (tolerances: audit E3) |
| **Heuristics in controllers and guidance** | About 11 ROE guidance constants (`engine/roe_formation.py:141-155`); phasing gate factor 2.5 (`engine/orbit_maintenance.py:278-279`); GEO N-S burn to ¼ of the limit (`engine/geo_station_keeping.py:82`) | Docstrings | No | Rationale in comments, rarely a reference |
| **Validation limits** | 50 numeric limits, e.g. mission ≤ 30 years, disposal lifetime ≤ 25 years (`schema/scenario.py:1552, 1571`), panel ≤ 2000 m², Monte Carlo ≤ 100 000 runs | Only when violated | No | No |
| **GUI suggestions** | New spacecraft 100 kg and inertia diag(10) kg·m²; wizard ranges; constellation 12/3/1 at 780 km 86.4°; phasing dialog defaults that differ from the spacecraft editor's for the same quantity (deadband 15 vs 1 km, thrust 0.05 vs 0.01 N) | Yes | Yes | Rarely (Appendix D, Section 2) |
| **Catalog presets** (32 devices) | Thrust taken at the top of the published range (`engine/device_catalog.py:610, 631, 693, 727, 769`) | Yes, with source URL | Yes, after applying | **Yes**, but the applied device is not stored in the scenario |
| **Templates** (31 scenarios, 4 buses) | "Rounded, order-of-magnitude-reasonable … for illustration" (`engine/spacecraft_templates.py:39-48`) | Yes | Yes | Stated as illustrative |

---

## 5. Hidden assumptions

The full lists, with file and line, are Appendix A Section 2 (H1 to H40) and Appendix B Section 2.
The ones a reviewer is most likely to be asked about:

### 5.1 Dynamics and environment

| Assumption | Where | Visible? |
|---|---|---|
| One fixed-rate task for everything. SPICE states, eclipse, atmosphere, space weather, ground access, controllers and events are refreshed once per dynamics step; the adaptive integrator only sub-steps inside it | `engine/service.py:754-771` | Comments |
| The inertial frame is EME2000 centred on the central body **for every body**. Elements for Mars, Moon or Eros orbits are referred to Earth's mean equator, not the body's own | `engine/service.py:910`; `engine/frames.py:60-63` | Provenance only |
| The ephemeris is DE430; body GM and radii are Basilisk's constants, not the gravity field's | `engine/kernels.py:91-96`; `engine/gravity_field.py:35-37` | Docstring (deviation D-07) |
| No relativity, tides, albedo or IR radiation pressure on the orbit, thermal re-radiation; third bodies are point masses | `engine/service.py:773-791` | **Not stated as excluded** |
| Spherical harmonics with degree = order; fields only for Earth and Mars | `engine/gravity_field.py:74-81` | Validation message |
| Earth-fixed frame ITRF93 only if installed IERS files cover the run, else IAU_EARTH (about 160 m/day at 400 km) | `engine/service.py:852-887` | Warning in the fallback case; see 3.6 |
| Drag: cannonball with fixed Cd and area unless facets; the atmosphere co-rotates (zero wind) | `engine/service.py:1043-1051` | Zero wind not stated |
| Beyond observations, space weather is MSFC's 13-month-smoothed prediction: no storms, constant Ap in all 3-hour slots, the last 132 months repeated beyond the file | `engine/spaceweather.py:550-557, 672-691` | Warnings name the source, not the smoothing |
| Eclipse: conical shadow of a spherical occulter; only the central body | `engine/service.py:993-1025` | No |
| Ground access uses geocentric elevation; the plotted elevation is geodetic (up to 0.19° apart); no refraction or terrain mask | `engine/service.py:949-961, 2607-2614` | Docstring |
| Output elements are osculating two-body elements; mean elements are first-order J2-only (Basilisk J2), whatever field is propagated | `engine/service.py:335-463` | Docstring |
| Impulsive maneuvers and Lambert burns change velocity only: no mass change, no duration, not logged | `engine/mission_engine.py:584-607, 726-727` | Tooltip on the Δv fields |
| Event times are snapped to recorded samples or steps; no root finding; the maximum elevation is the largest sampled value | `engine/events.py:21-27, 100-106` | Docstring |
| Re-entry altitude is spherical (|r| − equatorial radius), up to 21 km off the geodetic value at the poles | `engine/service.py:2180-2218` | No |
| Long runs are restarted every 90 days; controller filters and noise sequences restart | `engine/long_run.py:28-48` | Docstring; a pre-run check warns for navigation errors |

### 5.2 Mission analysis

| Assumption | Where | Visible? |
|---|---|---|
| Lifetime: orbit-averaged mean-element decay (16 points), J2 secular only, constant mass, perigee ≤ 120 km is re-entry; Earth rotation via GMST with UT1 = UTC | `engine/lifetime.py:19-29, 70, 184-187, 594` | Caption "orbit-averaged drag" |
| The drag make-up estimate in the budget is about 5 % low against full runs, with no known cause | `engine/lifetime.py:443-450` | Budget note |
| Budget: impulsive rocket equation per contributor in a fixed order; every impulsive Δv uses the circular speed at the operational SMA; injection correction = max(SMA, e), not sum or RSS | `engine/propellant_budget.py:151-173, 397-457` | Partly (rows) |
| Link: free-space path loss only, one lumped implementation loss, perfect pointing unless configured; closed at ≥ 0 dB | `engine/link_budget.py:19-27`; `engine/data_handling.py:149` | Dashboard breakdown, not the rule |
| Power: constant efficiency, no degradation (BOL = EOL), no temperature or packing factor, one panel normal | Basilisk `simpleSolarPanel` (B) | No |
| Data: instruments produce a constant rate, always on; 1 Mbit packets | `engine/data_handling.py:26, 79` | Schema comment |
| Attitude control closes on the true state (plus the optional navigation error); star tracker, IMU, magnetometer models are telemetry only; flight software uses the true inertia | `engine/fsw.py:131-136, 783-792` | No |
| Orbit control thrust is an ideal inertial force averaged over the step; propellant by explicit Euler | `engine/orbit_maintenance.py:232-238`; `engine/propellant_bookkeeping.py:100` | Docstring |
| GEO E-W planning uses fixed J22 and λ22, not the propagated gravity field | `engine/geo_station_keeping.py:79-80` | No |
| Monte Carlo keeps position and velocity only; spreads are population 1-σ about the mean | `engine/monte_carlo.py:121-133`; `engine/monte_carlo_results.py:262-280` | Hint text |
| Pre-run pass prediction: Kepler plus secular J2, 30 s sampling, one week | `engine/scenario_checks.py:58-60, 159-173` | No |

### 5.3 Conventions and rounding

- **Time.** The simulation clock is TDB seconds since a UTC epoch. The epoch is truncated to 1 ms
  for SPICE (`engine/time_system.py:91`). No leap second after 2017-01-01 is modelled (`:97`).
  The CSV header says only `time_s` (`engine/results.py:188`), and the plot axis says
  "Elapsed time [hr]" (`gui/results_widget.py:1134`).
- **Precision.** CSV values are written with 9 significant digits. That is about 0.01 m at LEO
  radius, about 100 m for heliocentric positions, and 1 s time resolution after about 3 years
  (`engine/results.py:191`).
- **Rounding in suggestions.** SSO inclination and RAAN-for-LTAN are rounded to 0.01°
  (`engine/orbit_design.py:91, 126`).
- **Interpolation and thinning.** The readout panel interpolates linearly between samples
  (`gui/readout_panel.py:39-52`). Plots thin to 10 000 points per line (`gui/results_widget.py:256`).
- **"Altitude".** In Explain and in station keeping it is SMA or |r| minus the equatorial radius,
  not the perigee or geodetic altitude (`engine/scenario_explainer.py:187`;
  `engine/orbit_maintenance.py:607`).
- **Units.** Units are carried by field-name suffix, not by type. The GUI converts GHz↔Hz,
  Mbit/s↔bit/s, RPM↔rad/s and %↔fraction for display, without saying so (Appendix D, Section 4).

---

## 6. Outputs shown without their derivation

Full tables: Appendix A Section 3 (series and events), Appendix B Section 3 (analyses),
Appendix D Section 1 (31 GUI locations, rated for equation, inputs, intermediates and source).

| Output | Where shown | What is shown | What is missing |
|---|---|---|---|
| Overview cards (delta-V, propellant, mean SMA change, lowest link margin, battery, passes, eclipses, data) | `gui/results_overview.py:60-95` | Value and unit | Which series and rule each comes from (only in `engine/run_summary.py:20-41`); see 3.5 |
| Lifetime, re-entry date, 5/25-year verdicts | CLI `lifetime`; GUI End of Life (`gui/lifetime_widget.py:330-356`) | Date, years, verdict | Cd and area actually used, ballistic coefficient, density model and file, 120 km criterion, accuracy, Isp of the deorbit burn; no export |
| Propellant budget | CLI `budget`; GUI Budget | Rows with margin and source | Mass before each burn, Ve, speed and SMA used, disposal Cd 2.2 and 50th percentile, rocket-equation form |
| Launch-delay sweep, altitude trade | CLI and GUI tables | Per-case Δv and kg | The drag ratio per case (computed, not shown); no export |
| Link margin series, lowest margin | Plots, Compare | dB | Breakdown (only on the live dashboard), the station and time, the 0 dB rule |
| Mission dashboard link breakdown | `gui/mission_dashboard_widget.py:399-461` | Intermediates | The inputs (P_tx, G, losses, R, T_sys, required Eb/N0) and the equations; it is recomputed in the GUI, not read from the run |
| Orbital elements series | Plots, CSV | Name and unit | "Osculating", the GM and frame used |
| Mean elements | Plots, CSV | Name and unit | First-order, J2-only, critical-band blending |
| Events (passes, eclipses, burns) | Timeline, `events.csv` | Times and values | Detection rules (thresholds, elevation mask, sampling resolution) |
| Monte Carlo spreads | CLI, GUI | 1-σ R/S/W at the end | The statistic (population σ about the mean), samples used, percentiles, the effect of excluded failed runs |
| Pre-run pass prediction | Explain | Passes, first pass, peak | The model (Kepler + J2, 30 s, one week) |
| Explain stat tiles (orbit "SSO 97.4°, 550 km alt") | `gui/scenario_explainer_widget.py:349-351` | Labels | "Alt" is SMA minus equatorial radius |
| SIL "Max \|residual\|" | `gui/sil_comparison_widget.py:143` | A number | The unit: it is a maximum over signals with different units |
| Provenance popover | `gui/run_history_view.py:120-135` | Versions, settings, file names | Data-file hashes and sizes, time scales, frames, seeds ("N entries") |
| Run warnings | Plots label, Log | Text | Not on Overview, not in CSV exports; one generic tooltip (3.12) |

---

## 7. Places where the user is forced into one option

Full tables: Appendix A Section 4, Appendix B Section 4, Appendix D Section 3.

| Area | Fixed choice | Reasonable alternatives | Basilisk support |
|---|---|---|---|
| Ephemeris | DE430 | DE440/441; analytic | `spiceInterface` loads any SPK; `planetEphemeris` |
| Gravity field | GGM03S (Earth), GGM2B (Mars); degree = order | EGM2008, EIGEN-6C, J2-only, separate order, lunar field | Any coefficient file; J2-only files ship |
| Body constants | Basilisk μ and radius | Field-header GM, user values | Settable |
| Integrator tolerances | 1e-10 / 1e-8 | User-set | Already set through the API |
| Task structure | One rate for all models | Separate environment and FSW rates | Standard multi-task pattern |
| Shadowing bodies | Central body only | Add the Moon (third bodies) | `eclipse.addPlanetToModel` |
| Atmosphere | NRLMSISE-00 or exponential | Tabular (user table); JB2008, DTM | `TabularAtmosphere` exists, not wired |
| Long-term solar activity | MSFC 95/50/5 percentile | User profile, constant values, other forecasts | Any CSV in Basilisk's format |
| Event timing | Snapped to samples | Interpolated crossings | Post-processing |
| Mean-element theory | First-order J2 | Full Brouwer, numerical averaging | Post-processing |
| Re-entry criterion | 120 km (analysis), 100 km (run), spherical | User altitude, geodetic | Parameter |
| Lifetime model | Orbit-averaged decay | Full numerical propagation (already possible with a long run), semi-analytic | In-tool |
| Debris rules | 5 and 25 years | Mission-specific, ISO 24113:2023, probability of compliance | Parameter |
| Margin policy | ESA AD10 | AD10 summary-table variant (10 %/20 %), ECSS-E-ST-35, GSFC-STD-1000, SMAD, user-defined | Parameters |
| Disposal start | Initial orbit | End-of-run state, user EOL orbit | In-tool |
| Link losses | Free space + one lumped loss; closed at 0 dB | ITU-R P.676/P.618, polarisation, cable; required margin; MODCOD table | Basilisk `linkBudget` (not used by design) |
| Power | No degradation, one panel | Degradation per year, temperature, packing, several panels, DoD limit | Partly |
| ADCS sensing | Truth or the navigation-error model | Close the loop on the configured sensors | Basilisk FSW filters |
| Control gains | Basilisk example gains scaled by inertia | Bandwidth and damping design, shown | In-tool |
| Monte Carlo | 1-σ, r and v only, Basilisk run-index seeds | Percentiles, more series, a batch seed | Partly |
| Units | Fixed per quantity (km, deg, m/s…) | User display units | GUI only |
| Frames for input and plots | EME2000 | ECEF, RTN/LVLH views | Post-processing |
| Compare | Base = oldest run; elapsed hours only | Pick the base; UTC axis | GUI only |
| Run store | Newest 20 runs, pruned silently | Configurable, with notice | In-tool |

---

## 8. Inputs and outputs exchanged with other tools and files

All 38 exchanges are in Appendix C, Section (c), with direction, format, path, producer and
consumer, whether provenance is recorded, whether a change is detected, and whether it is visible.

### 8.1 Summary

| Exchange | Provenance recorded | Change detected |
|---|---|---|
| Scenario file in and out | Hash of a canonical re-serialisation after migration only | No |
| Scenario migration | **No** | n/a |
| Results CSV, `events.csv`, `command_summary.csv` | `provenance.json` beside them; warnings not included | n/a |
| CCSDS OEM, OPM/OMM export | Header comments with versions and scenario hash | n/a |
| CCSDS OPM/OMM import | **No**: the source is not kept | No |
| TLE | The TLE is in the scenario | n/a |
| Basilisk support data (SPICE, gravity, WMM, albedo) | Path, size, SHA-256 (≤ 32 MB; de430.bsp size only) | **Yes**, registry checksum every run |
| CelesTrak space weather | Path, size, SHA-256 | No upstream checksum; "bundled" follows the newest download silently |
| MSFC prediction | **No** (named in a warning only) | No |
| Resolved space-weather CSV | Keyed on source mtime and row count | Partly |
| Earth-orientation and Eros kernels | From the install manifest | **Size only** after install |
| 3D meshes | SHA-256 in the scenario | **Yes** |
| Mass-property file | Name and SHA-256 in the scenario | Not re-checked |
| Device catalog presets | **No** (values only) | n/a |
| Vizard files and stream | **No**; Vizard version not recorded | n/a |
| Vizard program download | SHA-256 computed, not compared | No |
| Flight-software export | **Full manifest** (best in the tool) | **Yes** (stale, modified) |
| SIL | Binary and configuration digests; no tool version or time | n/a |
| Monte Carlo archive | Versions and scenario hash; no data files, integrator or seeds | n/a |
| Run store, autosave, settings, logs | Scenario and provenance in the run store; no setting changes a result | n/a |
| Plot PNG and SVG | Full provenance embedded | n/a |
| Other GUI exports | Sidecar provenance; table copies have none | n/a |
| Network | User-consented downloads only; a Basilisk import-time request is blocked (`_offline.py`) | n/a |
| Environment variables | Four written; none read that change results | n/a |

### 8.2 Implicit or invisible exchanges

- **Automatic data choice.** "Bundled" space weather silently uses the newer of the shipped file
  and a downloaded one (`engine/spaceweather.py:631-652`).
- **Silent reuse.** A resolved space-weather CSV is reused when its row count matches.
- **Silent rewrite of old files.** An older scenario is migrated in memory, changing
  space-weather settings, and `validate` prints the new version.
- **Defaults not in the file.** Values come from engine and Basilisk defaults behind open `params`,
  and from Basilisk factory parameter sets for named wheels and thrusters.
- **Silent pruning.** The run store keeps 20 runs and removes older ones with only a log line.

---

## 9. Prioritized implementation plan

### 9.1 Principles for the work

- **Regression baseline before any refactor.** Golden outputs for every template capture the
  current results: CLI `run` CSVs and events, `lifetime`, `budget`, Explain text and Overview
  figures. Every later step must reproduce them, unless it fixes a recorded defect.
- **Defects are recorded.** Every change to a numerical result goes into `docs/changes.md` with
  the before and after values, and gets a test.
- **Small steps.** One principle or feature area per pull request, with passing tests and updated
  records after each.
- **Extend what exists.** The provenance record, the budget's margin and source columns, Explain,
  the Inspector, the reference-data panel and the FSW manifest.
- **Uncluttered by default.** Transparency is one click away (an Explain button, a drawer, a
  popover), not added to every screen.
- **Documentation alongside.** `docs/models/` gets one page per model, rule and assumption,
  written for systems engineers, as each area is done.

### 9.2 Phases

Effort: S is up to a day, M a few days, L a week or more, per pull request. Each phase lists the
requirements of the brief it serves.

| Phase | Content | Serves | Effort |
|---|---|---|---|
| **1. Baseline and defects** | 1a. Golden-output regression tests for all 31 templates (CLI run, lifetime, budget, Explain, Overview figures), tolerance 0. 1b. Fix defects 3.1-3.13, each with a test and a `docs/changes.md` entry. 1c. Exit codes consistent with ICD-02 (a "completed with failures" code). | Constraints; 12 | M + M + S |
| **2. Reproducibility** | 2a. `run` writes the scenario as run into `--out-dir`. 2b. Provenance records the hash of the file bytes as well as the canonical hash. 2c. Provenance records **the effective configuration**: every default applied that is not in the file (open `params`, scaled gains, Basilisk factory values, migration steps). 2d. The MSFC file and all data files are hashed, with large files hashed once and cached. 2e. Correct provenance for segmented runs. 2f. Run warnings in exports. 2g. Provenance for CLI `lifetime` and `budget`, the Monte Carlo archive and SIL reports. 2h. A `reproduce` CLI command and a "reproduction bundle" export (scenario, referenced files, provenance) that re-runs and compares. | 9, 10, 14 | M each; 2h L |
| **3. Externalized configuration and assumptions panel** | 3a. A registry of named parameters in code (`config/registry.py`): name, value, unit, what it controls, source, rationale, and validator. Every engineering constant judged in Section 4 moves into it, one area per PR, with the regression baseline proving no change. 3b. The registry's defaults are shipped as a commented YAML file. A project configuration file next to the scenario overrides any parameter, and a scenario can name its configuration. 3c. One set of Earth and Sun constants, chosen explicitly (this changes numbers and goes through `docs/changes.md`). 3d. An **Assumptions** page in the GUI and `assumptions` in the CLI listing the active model choices and parameters with their source, editable, and flagged when changed. The effective configuration goes into provenance. | 2, 3 | L (spread over several PRs) |
| **4. Explain any number** | 4a. A calculation-trace object (equation, inputs with units, intermediates, result, source and clause) produced by the analysis calculations: budget rows, lifetime, link budget, power, data, run-summary figures, mean elements, events. 4b. An Explain drawer in the GUI on every computed value (Overview cards, End of Life, Budget, dashboard, Timeline), one click away. 4c. The same trace in exports (JSON) and in the CLI (`--explain`). 4d. A provenance view that shows everything recorded (hashes, frames, time scales, seeds). | 1, 10 | L |
| **5. Explainable warnings and overrides** | 5a. Structured warnings: rule id, rule text, why it matters, actual value, limit, how to fix, how to override. All pre-run checks, schema rules with limits, run warnings. No silently dropped checks. 5b. Overrides: any computed or suggested value can be overridden with a justification. The tool re-validates, explains the consequence, and marks the value as overridden in every view and export. Values computed into fields (SSO inclination, wizard values, catalog presets) are marked as computed until edited. | 7, 12 | M + L |
| **6. Selectable models through a registry** | 6a. A model registry pattern: each model declares its name, inputs, outputs, assumptions, references and validation evidence, and the active choice is shown in results and provenance. 6b. First choices: re-entry criterion and debris rules; margin policy profiles (AD10, AD10 summary table, user); shadowing bodies; atmosphere (adding the tabular model); link losses with a required margin; power degradation; Monte Carlo statistics. 6c. A plugin entry point (`spacemissionstudio.models`) so users add models, rules and item kinds without editing core code. | 4, 13 | L |
| **7. Change history** | Edits recorded with old and new value, time, author and reason (optional, required for overrides), kept in a sidecar history file beside the scenario and shown in a History view. Undo labelled. | 8 | M |
| **8. Units, workflow and data links** | 8a. Every displayed value with its unit (SIL residuals, gains, dispersions); explicit conversions in the Inspector; an optional display-unit preference. 8b. A workflow view showing each step's inputs and outputs, with chained inputs (for example "from the end of the last run") shown and editable before computing. 8c. Imported values (CCSDS, TLE, catalog, mass properties, data files) shown with source and hash, flagged when the source changes. | 5, 6, 14 | M each |
| **9. Open data and scriptable API** | 9a. Export of every intermediate and final result as CSV or JSON (lifetime curve, sweeps, trades, Monte Carlo runs) with provenance. 9b. A documented, stable Python API (`spacemissionstudio.api`) for load, validate, run, lifetime, budget, trade studies and batch runs, with a reference page and examples tested in CI. CLI commands for what is GUI-only today (run comparison, space-weather download). | 10, 11 | M + L |
| **10. Model documentation** | `docs/models/` with one page per model, rule and assumption: what it computes, equations, inputs with units, assumptions, limits of validity, references, validation evidence, and how to change it. Written as each phase reaches the model; this phase finishes the rest. | Constraints | M, spread |

### 9.3 Order and why

1. **Phase 1 first.** Every later step needs a baseline that proves numbers did not move, and the
   defects make some results wrong today.
2. **Then Phase 2.** It gives the quickest gain on "reproduce a colleague's result from an
   exported file", and Phase 3's effective configuration builds on it.
3. **Phases 3 and 4 are the core of "trace any number" and "change any assumption without code".**
   They are the largest, and are split by area. Suggested order of areas: propellant budget
   (already closest), lifetime, link and power, run summary, then dynamics.
4. **Phases 5 to 9 follow**, in the order given, each delivering working software.

### 9.4 How the definition of done will be checked

| Criterion | Check |
|---|---|
| Trace any number in under a minute | A scripted walkthrough for each output in Section 6: one click opens its trace with equation, inputs, intermediates and source. Timed with an engineer who did not build the tool. |
| Change any assumption without editing code | Every row of the registry can be changed in the Assumptions page or the project YAML file, and the change shows in results and provenance. A test sets each parameter. |
| Reproduce a colleague's result from an exported file | `reproduce` on a bundle from another machine gives byte-identical CSVs (or identical within a stated tolerance across platforms), checked in CI on Linux and Windows. |
| Explain the result in a design review | The exported trace and `docs/models/` page give the equation, assumptions and reference for every reported figure. |

---

## 10. Decisions needed from you

1. **Configuration format.** I recommend YAML, with comments and units. PyYAML 6.0.3 already
   ships in the installers (`packaging/constraints.txt:49`), but SpaceMissionStudio does not
   declare it as a dependency yet, so it would be added. JSON is the alternative: no new
   dependency, but no comments, so the units and sources would go in separate keys.
2. **Changing constants that are inconsistent today** (three sets of Earth constants, two solar
   fluxes, the 100 km vs 120 km re-entry). Unifying them changes numbers slightly in some outputs.
   Is that acceptable as a recorded change in `docs/changes.md`? Or should the current values be
   kept per area and only made visible?
3. **Change-history storage.** A sidecar file next to the scenario (my recommendation: the
   scenario stays clean for version control) or a history section inside the scenario file?
4. **Author identity for the change history.** The operating-system user name, or a name set in
   Settings?
5. **Scope of the first selectable models** (Phase 6b). The list given is my suggestion; you may
   want others first, such as the margin policy your teams use.
6. **Defects 3.1 to 3.13.** Fix them all in Phase 1? 3.4 (the control gains) changes either what
   the GUI shows or what the engine applies. I suggest showing the applied, scaled gains rather
   than changing the physics.

---

## Appendix A: Orbital dynamics, environment, time and frames

*Detailed findings of review A, as written by the reviewer and checked as described in Section 1.*

Scope: `spacemissionstudio/engine/` service.py, environment_models.py, gravity_field.py,
geodetic_atmosphere.py, spaceweather.py, earth_orientation.py, planet_rotation.py, frames.py,
time_system.py, kernels.py, reference_data.py, small_bodies.py, polyhedron.py, geodesy.py,
orbit_conversion.py, mean_elements.py, tle.py, orbit_number.py, events.py, results.py,
series_names.py, long_run.py, landmarks.py, opnav.py, optical_navigation.py,
landmark_navigation.py, mission_engine.py; plus the matching dataclasses in `schema/scenario.py`.
All paths below are relative to `spacemissionstudio/`. Line numbers were checked against the
files at develop 20d80d67a.

Notation for the "Editable?" column:
- **JSON**: a scenario-file field. **GUI**: the field is referenced from a GUI editor
  (Propagation Setup dialog = `gui/propagation_setup_dialog.py`, Spacecraft editor =
  `gui/spacecraft_editor.py`, Ground station editor = `gui/ground_station_editor.py`). I found the
  field name in that file but did not trace every widget.
- **No**: hard-coded. Changing it needs a code edit.
- "Visible?" means the value can be seen in the GUI, the results or the provenance record.
  The source code alone does not count.

Basilisk-internal values marked (B) were read in a Basilisk **2.13.0b0** source tree in the
workspace (Basilisk's source tree). The tool is qualified with 2.12.0
(`dependencies.py:37`), so those (B) values are **unverified for 2.12.0**.

---

### 1. Hard-coded constants, defaults, margins, thresholds and rules

#### 1a. Integrator, task rates, run limits (service.py, schema, long_run.py, mission_engine.py)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| engine/service.py:117 | INTEGRATOR_RELATIVE_TOLERANCE | 1e-10 [-] | Relative error tolerance of rkf45/rkf78 | Yes: provenance `integrator_relative_tolerance` (service.py:2283). Not in the GUI banner (gui/results_widget.py:1024-1027) | No | Own study (comment 108-116: "audit E3", 384 m / 173 km errors with the Basilisk default) |
| engine/service.py:118 | INTEGRATOR_ABSOLUTE_TOLERANCE | 1e-8 [state units, mixed m, m/s, rad] | Absolute tolerance of the adaptive integrators. One value for every state (position, velocity, MRP, wheel speeds, ...) | Provenance only | No | "Basilisk's default" |
| engine/service.py:101-106 | _INTEGRATORS | euler, rk2, rkf45, rkf78 | Integrator classes available | Integrator name is shown in the GUI banner | JSON `sim_settings.integrator`, GUI Propagation Setup | Basilisk class list (schema/scenario.py:2587-2593) |
| schema/scenario.py:2600 | SimSettings.integrator default | "rkf78" | Default integrator | Yes | JSON/GUI | no source given |
| schema/scenario.py:2599 | SimSettings.dynamics_task_rate_s default | 10.0 [s] | The one dynamics task rate. It also sets the SPICE refresh, eclipse, atmosphere, ground access, controllers and event checks (service.py:754-771) | Yes (banner) | JSON/GUI | no source given |
| schema/scenario.py:84 | MIN_DYNAMICS_TASK_RATE_S | 0.001 [s] | Smallest allowed step | Validation message | No | "the editor's least" |
| schema/scenario.py:2607 | SimSettings.record_interval_s default | 0.0 [s] (= every step) | Recorder sampling. Also sets controller log thinning (service.py:1922) and link-gate/data-handling logs (1846, 1853) | GUI | JSON/GUI | n/a |
| schema/scenario.py:2645 | record_interval_s limit | [0, 86400] [s] | Validation | message | No | none |
| schema/scenario.py:2598 | SimSettings.duration_days default | 1.0 [day] | Run length | Yes | JSON/GUI | n/a |
| schema/scenario.py:2635 | _MAX_SINGLE_RUN_DAYS | 100.0 [day] | Longer runs are split into segments (long_run) | Messages | No | Basilisk nanoToSec 2^53 ns limit, about 104.25 d (comment 2623-2631) |
| schema/scenario.py:2636 | _MAX_DURATION_DAYS | 3660 [day] | Longest run allowed | Validation message | No | "about 10 years", no source |
| engine/long_run.py:67 | SEGMENT_DAYS | 90.0 [day] | Length of each segment of a long run | Not shown | No | "safely under" 104.25 d |
| engine/long_run.py:84 | segment length rule | floor(90 d / step) whole steps | Segment boundaries fall on step multiples | No | No | n/a |
| engine/long_run.py:272 | progress frames | 60 | Live updates across a segmented run | No | No | none |
| engine/service.py:153 | _LIVE_DEFAULT_FRAMES | 60 | Live-run chunks. It also limits how quickly Cancel takes effect | No | No | "round number" |
| engine/service.py:767 | dynProcess priority | 100 | Process priority | No | No | n/a |
| engine/service.py:911, 1020, 1025, 1054, 1086/1119, 1111, 1162, 1250/1255, 1267, 1349/1383/1424 | Task priorities | SPICE 500, shadow copy 460, mid-step orientation 450 (planet_rotation.py:53), space weather 400, geodetic proxy 395 (geodetic_atmosphere.py:45), atmosphere 390, wind 380, eclipse 370, effectors 100, power 50/40, spacecraft 10 | **Fixed order of operations inside each step** | No | No | comments only |
| schema/scenario.py:2613 | SimSettings.seed default | 0 | RNG seed, from which per-model seeds are derived | Provenance `rng_seed(s)` | JSON/GUI | n/a |

#### 1b. Gravity, central and third bodies

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| schema/scenario.py:2324-2326 | GravityConfig defaults | central_body "earth", degree 0 (point mass), no third bodies | Default gravity model | Explain tab `_gravity_summary` (scenario_explainer.py:210-223) | JSON/GUI (Propagation Setup, Spacecraft editor) | n/a |
| schema/scenario.py:94-96 | SUPPORTED_CENTRAL_BODIES | sun, mercury, venus, earth, moon, mars barycenter, jupiter barycenter (+ eros, line 100) | Bodies a run can use | Validation messages | No | DE430 contents (comment 86-93) |
| schema/scenario.py:2388 | GRAVITY_FIELDS | Earth GGM03S to degree 180; Mars GGM2B to degree 80 | Highest spherical-harmonic degree | Validation message | No | Field files |
| engine/gravity_field.py:52-55 | FIELD_FILES | Earth -> GGM03S, Mars barycenter -> GGM2BData | Which field file is used | provenance `data_files.gravity_field` (service.py:813) | No (no other field can be selected) | Basilisk support data |
| engine/gravity_field.py:74-81 | coefficient rescaling | C,S x (R_file/R_body)^n | Keeps the file's reference radius (6378136.3 m GGM03S, 3397 km GGM2B) while Basilisk evaluates with the body radius | docstring only | No | "SRelD K-04" |
| engine/gravity_field.py:35-37, 81 | GM | Basilisk's body GM, not the field's (1.4e-8 / 1.4e-6 relative difference) | Central-body GM | docstring only ("deviation D-07") | No | Documented deviation |
| (B) simIncludeGravBody.py:136-137 | Earth mu, radEquator | 398600.436 km^3/s^2; 6378.1366 km | GM and radius used everywhere (gravity, re-entry altitude, mean-element Req, ground station sphere radius) | Not displayed | No | Basilisk astroConstants.h |
| engine/service.py:819-835 | Mean-element gate | Mean elements only for Earth with degree >= 2 | Whether `.orbit_elements_mean.*` exists | Series simply absent otherwise | Indirect (degree) | Own rule |
| engine/service.py:835 | mean_elements_j2 | orbitalMotion.J2_EARTH = 1082.616e-6 (B) | J2 for mean-element mapping and formation controllers (1737, 1755) | No | No | Basilisk constant. Not the GGM03S C20 actually propagated |
| engine/service.py:834 | mean_elements_req | central_body.radEquator (6378136.6 m) | Req for the mean-element map | No | No | Basilisk |
| engine/service.py:398 | _MEAN_ELEMENTS_MIN_INCLINATION_RAD | 1e-9 [rad] | Inclination clamp before clMeanOscMap | No | No | own |
| engine/mean_elements.py:52 | CRITICAL_INCLINATION_RAD | acos(sqrt(0.2)) = 63.435 deg | Singularity of the first-order map | docstring | No | Theory |
| engine/mean_elements.py:55 | CRITICAL_BAND_RAD | 1 deg | Band where the map is blended from its edge values | No | No | own (audit 2026-10-27) |
| engine/mean_elements.py:58 | EQUATORIAL_BAND_RAD | 1 deg | Below this the map is evaluated at 1 deg | No | No | own |
| engine/mean_elements.py:61 | _PLACEMENT_ITERATIONS | 6 | Mean -> osculating inversion iterations | No | No | own |
| engine/service.py:1410-1424 | Gravity-gradient bodies | central body only | Gravity-gradient torque | No | No | Rationale in comment 1410-1416 |
| engine/small_bodies.py:89 | EROS.spin_rad_s | 1639.38864745 deg/day | Eros rotation, used in the landmark filter | No | No | pck00010 |
| engine/small_bodies.py:90 | EROS.gm_m3_s2 | 4.463e-4 km^3/s^2 | Eros GM (point mass and polyhedron) | No | No | Horizons header |
| engine/small_bodies.py:91 | EROS.mean_radius_m | 8.42 km | Eros shadow sphere (service.py:1021), "radEquator" (service.py:787) | No | No | Horizons header |
| engine/small_bodies.py:94-96 | EROS SPK size / SHA-256 / span | 4589568 B; sha 1389946d...; 1900-2100 | Kernel check | Reference data panel | No | NAIF |
| engine/polyhedron.py:150 | constant density | G*rho = mu / volume | Polyhedron gravity (Basilisk model too) | docstring | No | Werner and Scheeres 1997 |
| engine/polyhedron.py:109 | inside threshold | solid angle > 2 pi | Impact detection | Warning text | No | standard |
| engine/polyhedron.py:198 | shape units | km -> m (x1e3) | Shape file units assumed km | No | No | file convention |

#### 1c. Atmosphere and drag

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| schema/scenario.py:2449 | atmosphere_model default | "nrlmsise00" (or "exponential") | Density model | GUI combo (propagation_setup_dialog.py:442-462) | JSON/GUI | Basilisk models |
| (B) simSetPlanetEnvironment.py:32-34 | exponential Earth | baseDensity 1.217 kg/m^3, scaleHeight 8500 m, R 6378136.6 m | Exponential atmosphere | Docstring (schema 2414-2425); GUI label "simple" | No | Basilisk example values |
| (B) msisAtmosphere.cpp:31 | MSIS planetRadius | REQ_EARTH 6378136.6 m | Sphere used to compute altitude (corrected by the geodetic proxy) | No | No | Basilisk |
| engine/service.py:1117 | MSIS space-weather channels | 23 messages | Wiring | No | No | Basilisk interface |
| engine/service.py:1051 | wind model | ZeroWindModel = atmosphere co-rotating with the planet ((B) zeroWindModel.cpp:27) | Air velocity for drag | No | No | none |
| schema/scenario.py:1813-1815 | drag defaults | enable_drag False, drag_coeff 2.2 [-], drag_area_m2 1.0 [m^2] | Cannonball drag | GUI | JSON/GUI | no source given (Cd 2.2 is a common textbook value) |
| schema/scenario.py:1589 | FacetConfig.drag_coeff | 2.2 [-] | Per-facet drag | GUI facet editor | JSON/GUI | none |
| schema/scenario.py:1958 | drag_area limit | (0, 1e4] m^2 | Validation | message | No | none |
| engine/geodetic_atmosphere.py:64-75 + geodesy.py:155-164 | Geodetic proxy | density looked up at the WGS-84 geodetic altitude and latitude | Density lookup point | docstring only | No | "Phase 3 F-07" (10 % decay-rate error without it) |
| engine/geodesy.py:53-54 | WGS-84 a, 1/f | 6378137.0 m; 298.257223563 | Geodetic conversions (stations, atmosphere proxy) | Frames record "WGS-84" (frames.py:69) | No | NIMA TR8350.2 |
| engine/geodesy.py:111, 116 | pcpf_to_geodetic | 50 iterations max; 1e-13 rad convergence | Geodetic iteration | No | No | own |
| engine/service.py:158 | _REENTRY_ALTITUDE_M | 100 km | Re-entry: run stops (drag spacecraft) or a warning | Warning text names 100 km | No | no source given |
| engine/service.py:159 | _REENTRY_CHECK_S | 6 h [s] | Re-entry check cadence when perigee is high | No | No | none |
| engine/service.py:160 | _REENTRY_NEAR_PERIGEE_M | 200 km | Threshold for checking often | No | No | none |
| engine/service.py:161 | _REENTRY_NEAR_CHECK_S | 300 s | Re-entry check cadence when perigee is low | No | No | none |
| engine/long_run.py:281 | re-entry text | "below 100 km" written into the text, not taken from the constant | Warning text | Yes | No | duplicate of service.py:158 |

#### 1d. Space weather (spaceweather.py, schema)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| schema/scenario.py:2446 | source default | "bundled" | Which CelesTrak file | GUI | JSON/GUI | n/a |
| schema/scenario.py:2453 | forecast_percentile default | 50.0 [%] (95/50/5 only, 2391) | MSFC percentile used beyond observations | Warning names the percentile (spaceweather.py:798-799) | JSON/GUI | ESA AD10 Sec. 5.9 |
| engine/spaceweather.py:137 | BUNDLED_DATA_PATH | data/spaceweather/SW-All.txt (updated 2026-10-25) | Observed F10.7/Ap | Reference data panel, README | Replace via fetch/import | CelesTrak |
| engine/spaceweather.py:141 | MSFC_BUNDLED_PATH | oct2026f10-prd.txt | Long-term prediction | Reference data panel | JSON `msfc_file_path` / GUI | NASA MSFC |
| engine/spaceweather.py:142 | MSFC_PERCENTILES | (95, 50, 5) [%] | Allowed percentiles | Validation | No | MSFC columns |
| engine/spaceweather.py:143 | _MSFC_REPEAT_MONTHS | 132 [month] | Beyond the MSFC file the last 132 months repeat | Warning (801) | No | ESA AD10 Sec. 5.9 |
| engine/spaceweather.py:144 | _PAD_DAYS | 10 [day] | Data needed on each side of the run (MSIS history) | In the refusal message | No | own |
| engine/spaceweather.py:686 | MSFC day record | the same 13-month-smoothed F10.7 used for the daily and the 81-day value; the same Ap in all eight 3-h slots | Daily input to MSIS beyond observations | Warning only says "MSFC's prediction" | No | own construction |
| engine/spaceweather.py:550-557 | NOAA monthly fill | F10.7 from the NOAA monthly forecast. Ap = mean of all observed days in the file | Days MSFC does not cover | Warning with the Ap value (795-796) | No | "user decision" |
| engine/spaceweather.py:541-544 | long_term_ap | mean daily Ap 1957-present (computed) | As above | Warning text | No | computed |
| engine/spaceweather.py:449-454 | CSSI column slices | Ap 46-78, Ap_avg 78-82, F10.7_OBS 112-118, Ctr81 118-124 | Parsing the .txt format | No | No | CelesTrak format page |
| engine/spaceweather.py:547-548 | incomplete rows dropped | rows with any missing field are skipped | Data use | No | No | own |
| engine/spaceweather.py:109 | DEFAULT_CACHE_DIR | ~/.cache/SpaceMissionStudio/spaceweather | Resolved-file cache | No | JSON `cache_dir` | n/a |
| engine/spaceweather.py:132 | _MAX_DOWNLOAD_BYTES | 100 MB | Download cap | No | No | own |
| engine/spaceweather.py:254 | fetch timeout | 30 s | Network | No | No | own |
| engine/spaceweather.py:739-740 | replace retries | 20 x 0.05 s | Windows file locking | No | No | own |
| engine/reference_data.py:36 | SPACE_WEATHER_STALE_DAYS | 60 [day] | "out of date" flag in the reference panel | Yes (panel) | No | none |

#### 1e. Earth orientation, time scales, ephemerides, kernels

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| engine/kernels.py:91-96 | DEFAULT_KERNELS | naif0012.tls, de430.bsp, de-403-masses.tpc, pck00010.tpc | Ephemeris, leap seconds, orientation | provenance `data_files.spice:*` (service.py:839-840), reference panel | No (no DE440 or other ephemeris can be chosen) | Basilisk defaults |
| engine/earth_orientation.py:72-73 | EARTH_FIXED_FRAME / FALLBACK | "ITRF93" if covering IERS PCKs are installed, else "IAU_EARTH" | Earth-fixed frame (gravity field, stations, atmosphere) | provenance frames P axes (frames.py:57-58); warning only when IERS files are missing or do not cover the run | Indirect (install files) | NAIF |
| engine/earth_orientation.py:71 | HIGH_ACCURACY_AFTER_LAST_DATUM | 10 weeks | When predicted EOP counts as "low accuracy" | Explain tab note only (see Sec. 2) | No | NAIF comment file |
| engine/earth_orientation.py:286 | _J2000_UTC | TDB-UTC taken as 64.184 s | Converting PCK coverage times to UTC ("within a minute") | No | No | own approximation |
| engine/earth_orientation.py:67 | _MAX_DOWNLOAD_BYTES | 128 MB | Download cap | No | No | own |
| engine/earth_orientation.py:216 / 206 | fetch / listing timeouts | 300 s / 60 s | Network | No | No | own |
| engine/service.py:883-887 | IAU-model error note | "~160 m/day position error at degree 20, 400 km" | Warning text | Yes (warning) | No | "Phase 3 V-04" (GMAT comparison) |
| engine/time_system.py:96 | TT_MINUS_TAI_S | 32.184 [s] | Time scale | provenance `time_system` | No | definition |
| engine/time_system.py:97 | LAST_LEAP_SECOND_UTC | "2017-01-01" | Leap-second table end (later leap seconds not modelled) | provenance | No | ERFA / naif0012 |
| engine/time_system.py:91 | SPICE epoch string | epoch truncated (floor) to 1 ms | Scenario epoch passed to SPICE | No | No | own |
| engine/time_system.py:132 | TDB-TT day fraction | "adequate here" approximation | dtdb input | No | No | own |
| engine/time_system.py:156 | TDB-TT grid | evaluated every 6 h, linearly interpolated | UTC display of times | No | No | own (< 0.1 us stated) |
| engine/planet_rotation.py:71 | mid-step shift | -h/2 | Planet orientation the gravity model sees | docstring | No | "Phase 3 V-04" |
| engine/planet_rotation.py:59 | _nearest_rotation | one Newton polar step | Re-orthonormalisation | No | No | standard |
| engine/tle.py:65 | TLE_AGE_WARNING_DAYS | 3.0 [day] | Warning if the TLE epoch is far from the scenario epoch (scenario_checks.py:498) | Check message | No | none |
| engine/tle.py:104-112 | TEME -> EME2000 | IAU-76 precession, IAU-80 nutation, Eq = dpsi cos(eps), no 1994 terms, no frame bias | TLE conversion | provenance TRANSFORMATIONS (frames.py:83) | No | Vallado et al. 2006 |

#### 1f. Environment constants (environment_models.py)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? | Source |
|---|---|---|---|---|---|---|
| environment_models.py:47 | TOTAL_SOLAR_IRRADIANCE_W_M2 | 1361.0 W/m^2 | Sensor thermal flux; SRP estimate in checks | No | No | ECSS-E-ST-10-04C Table 6-2 |
| environment_models.py:48 | SPACE_SINK_TEMPERATURE_K | 3.0 K | (thermal) | No | No | ECSS-E-ST-10-04C 6.2.1c |
| environment_models.py:49 | STEFAN_BOLTZMANN | 5.670374419e-8 | Thermal correction | No | No | CODATA 2018 |
| environment_models.py:50 | SPEED_OF_LIGHT_M_S | 299792458 m/s | SRP estimate | No | No | definition |
| environment_models.py:51 | ASTRONOMICAL_UNIT_M | 149597870700 m | Flux scaling | No | No | IAU 2012 B2 |
| environment_models.py:54-55 | Basilisk sensorThermal constants | 1366 W/m^2; 5.76051e-8 | Corrected for | docstring | No | measured from Basilisk |
| environment_models.py:57-59 | _EARTH_GM, _EARTH_RADIUS, _EARTH_J2 | 3.986004415e14; 6378136.3 m; 1.08263e-3 | Gravity truncation estimate only. **Different from the GM (398600.436) and J2 (1082.616e-6) that the propagation and mean elements use** | No | No | GGM03S / none for J2 |
| environment_models.py:60 | _KAULA_MAX_DEGREE | 2000 | Truncation-error sum | No | No | own |
| environment_models.py:127 | Kaula's rule | 1e-5 / n^2 | Truncation-error estimate (scenario checks) | Check text | No | Kaula |
| environment_models.py:139 | degree_for max_degree | 180 | Suggested degree | Check text | No | own |
| environment_models.py:73-74 | Sun-distance formula | 357.528 + 0.9856003 d; 1.00014 - 0.01671 cos g - 0.00014 cos 2g | Earth-Sun distance for sensor solar flux at the epoch (service.py:1219) | No | No | Astronomical Almanac low-precision |
| environment_models.py:148 | WMM_VALIDITY_YEARS | 5.0 yr | WMM validity warning | Warning | No | WMM release rule |
| (B) radiationPressure.cpp:188 / astroConstants.h:53 | SOLAR_FLUX_EARTH | 1361.0 W/m^2 at 1 AU | Cannonball SRP force | No | No | Basilisk |
| (B) facetSRPDynamicEffector.cpp:27 | solarRadFlux | **1368.0 W/m^2** | Faceted SRP force (0.5 % higher than the cannonball model) | No | No | Basilisk |

#### 1g. SRP, eclipse, ground access

| File:line | Name | Value [unit] | Controls | Visible? | Editable? | Source |
|---|---|---|---|---|---|---|
| schema/scenario.py:1816-1818 | SRP defaults | enable_srp False, srp_coeff (Cr) 1.3 [-], srp_area 1.0 m^2 | Cannonball SRP | GUI | JSON/GUI | no source given |
| schema/scenario.py:1590-1591 | FacetConfig specular/diffuse | 0.3 / 0.1 [-] | Facet SRP optical properties | GUI facet editor | JSON/GUI | none |
| engine/service.py:997-1000 | occulter list | central body only (all other tracked bodies in a heliocentric run) | Which bodies cast shadows | No | No | own rule |
| engine/events.py:64 | _UMBRA_SHADOW_FACTOR | 0.01 [-] | "umbra" vs "penumbra" label | Event label | No | none |
| engine/events.py:164 | eclipse start | illumination < 1.0 | Eclipse event = any penumbra | No | No | own |
| schema/scenario.py:2371 | min_elevation_deg default | 10.0 [deg] | Access mask (Basilisk applies it to geocentric elevation) | GUI | JSON/GUI | none |
| engine/fsw.py:1264 (called from service.py:950) | maximumRange | -1 (none) | Access range limit | No | No | own |

#### 1h. Optical and landmark navigation

| File:line | Name | Value [unit] | Controls | Visible? | Editable? | Source |
|---|---|---|---|---|---|---|
| engine/opnav.py:69 | BODY_IDS | earth 1, mars bary 2, jupiter bary 3 | Bodies pixelLineConverter supports | Validation | No | Basilisk |
| engine/opnav.py:72 | BODY_RADIUS_M | 6378.1366 km, 3396.19 km, 71492 km | Spherical disk radius | No | No | Basilisk REQ_* |
| (B) relativeODuKF.c:233-235 | filter mu | MU_EARTH/MARS/JUPITER (km^3/s^2) | OD filter dynamics (two-body only) | No | No | Basilisk |
| engine/optical_navigation.py:208-211 | UKF alpha, beta, kappa, noiseSF | 0.02, 2.0, 0.0, 1.0 | UKF sigma points and noise scale | No | No | "as Basilisk's own test" |
| engine/optical_navigation.py:70 | _MIN_SIGMA_PX | 1e-3 px | Smallest variance written | No | No | own |
| engine/optical_navigation.py:71 / landmark_navigation.py:57 | task priority | -10 | Navigation runs after dynamics | No | No | own |
| schema/scenario.py:1202-1216 | OpticalNavigationConfig defaults | FOV 40 deg, 512x512 px, every 60 s, noise 0.5 px centre / 0.5 px radius, min radius 5 px, max phase 90 deg, initial sigma 1000 m / 1 m/s, Q 0.1 m / 1e-3 m/s, seed 1 | Opnav | GUI spacecraft editor | JSON/GUI | none |
| engine/landmarks.py:55 | QUANTIZATION_SIGMA_PX | 1/sqrt(12) px | Measurement noise for pixel rounding | No | No | uniform rounding |
| engine/landmarks.py:56 | FOCAL_LENGTH_M | 0.025 m | Camera focal length (pixel pitch is derived from it) | No | No | none |
| engine/landmarks.py:57 | _MAX_STEP_S | 60 s | Filter RK4 step | No | No | none |
| schema/scenario.py:1262-1274 | LandmarkNavigationConfig defaults | 100 landmarks, FOV 30 deg, 1024x1024, every 600 s, 0 px added noise, Sun mask 10 deg, initial sigma 100 m / 0.05 m/s, Q 1e-8 m/s^1.5, seed 1 | Landmark navigation | GUI | JSON/GUI | none |

#### 1i. Mission sequence, events, results

| File:line | Name | Value [unit] | Controls | Visible? | Editable? | Source |
|---|---|---|---|---|---|---|
| engine/mission_engine.py:101 | _WHILE_MAX_ITERATIONS | 10000 | While-loop cap | Error message | No | own |
| engine/mission_engine.py:110 | _EVENT_PROPAGATE_SAFETY_MULTIPLIER | 10 x max(duration, 1 d) | How far an event search runs | Error message | No | own |
| engine/mission_engine.py:132 | _PROPAGATE_CANCEL_CHECK_FRAMES | 60 | Cancel granularity | No | No | own |
| engine/mission_engine.py:159 | _APSIS_AT_START_M_S | 1e-6 m/s | Start on an apsis counts as being there | No | No | "finding F-10" |
| engine/mission_engine.py:490 | event check rate | = dynamics_task_rate_s | Event detection resolution | No | Indirect | own |
| engine/mission_engine.py:651-652 | Lambert defaults | max_distance_target 1000 m; min_orbit_radius 0 m | Lambert validator | GUI mission-sequence editor | JSON/GUI | none |
| engine/mission_engine.py:666, 710 | Lambert mini-sim | 30 s task, 60 s run (2 ticks) | Solver convergence check | No | No | scenarioLambertSolver.py |
| engine/mission_engine.py:694 | setDvConvergenceTolerance | 1.0 m/s | Lambert convergence | No | No | none |
| engine/mission_engine.py:692-693 | uncertainty | zero state and delta-V uncertainty | Lambert validator | No | No | own |
| engine/results.py:208 | _DEFAULT_CONSERVATION_TOLERANCE | 1 % | Energy / angular-momentum drift warning (two-body runs only) | Warning names the limit | No | "deliberately coarse" |
| engine/results.py:191 | CSV format | %.9g | Precision of exported numbers | Visible in the files | No | own |
| engine/orbit_number.py:54 | _EQUATORIAL_NODE_FRACTION | 1e-3 | Equatorial-orbit test (about 0.06 deg) | Axis title note | No | own |
| engine/orbit_number.py:48, 81 | mu | MU_EARTH 398600.436e9 (propellant_budget.py:86) | Orbit-number unwrapping | No | No | Basilisk |

---

### 2. Hidden assumptions

| # | Assumption | Where (file:line) | Visible to user? |
|---|---|---|---|
| H1 | **One fixed-rate task** for everything. The SPICE planet states, eclipse, atmosphere density, wind, space weather, ground access, controllers and Mission Sequence events are all refreshed once per `dynamics_task_rate_s`. The adaptive integrator only sub-steps inside a task step, so these inputs stay constant across it. | service.py:754-771, 911, 1025; mission_engine.py:490 | Docstring/comment only |
| H2 | Inertial frame N = SPICE J2000 (EME2000), centred on the **central body** (zeroBase), for every central body. Classical elements, Cartesian ICs and output elements are referred to the **Earth mean equator of J2000 even for Mars, Moon, Eros or Sun runs** (inclination is not relative to the body's own equator). | service.py:910; frames.py:60-63; service.py:300-316, 335-395 | Provenance frames record only. The GUI orbit editor does not say so (not verified in the GUI) |
| H3 | J2000 is treated as ICRF; no frame bias. | frames.py:61; tle.py:40-44 | Provenance |
| H4 | Ephemeris fixed to **DE430** (Mars and Jupiter as system barycentres, with the planet's mass and radius). | kernels.py:91-96; schema/scenario.py:86-93, 111-116 | Reference panel, validation messages |
| H5 | Body GMs and radii are **Basilisk astroConstants** (e.g. Earth 398600.436 km^3/s^2, 6378.1366 km), not the gravity-field header or the de-403-masses kernel. The kernel is loaded, but I did not verify whether spiceInterface overrides mu (**unverified**). | simIncludeGravBody (B):136-137; gravity_field.py:35-37 | Docstring (D-07) only |
| H6 | Third bodies are point masses only. No relativity, solid or ocean tides, Earth albedo or IR radiation pressure on the orbit, thermal re-radiation, or planetary oblateness of third bodies. | service.py:773-791 (only gravity, drag, SRP, gravity gradient effectors are built) | Not stated as excluded |
| H7 | Spherical harmonics: **degree = order** (a full square field to `central_body_degree`). Order cannot be chosen separately. Only Earth and Mars have fields; Moon, Venus and others are point mass. | gravity_field.py:74, 79; schema 2348-2355 | Validation message |
| H8 | Planet orientation inside a step is replaced by the **mid-step orientation with zero rate** (custom correction to Basilisk). Ground stations, atmosphere and guidance still read the unmodified end-of-step SPICE message. | planet_rotation.py:32-44, 77-89 | Docstring only |
| H9 | Earth-fixed frame is **ITRF93 only if installed IERS PCKs cover the whole run, else IAU_EARTH** (no polar motion, UT1 or nutation). A run that reaches **predicted (low-accuracy) EOP** gets a note from `earth_orientation.notes()`, but `_extract_results` only passes on notes containing "no IERS data" / "not this run" / "do not cover this run", so the **low-accuracy prediction note never reaches the run's warnings**. It appears only on the Explain tab, and only when that section has a badge. | service.py:852-887, 2306-2307; earth_orientation.py:384-394; scenario_explainer.py:353-391 | Partial |
| H10 | Other bodies use IAU rotation models (pck00010), e.g. IAU_MOON rather than the lunar PA/ME frames. | service.py:875 (planetFrames ""), frames.py:58 | Provenance frames text |
| H11 | Drag: **cannonball with a fixed Cd and area** unless facets are given; atmosphere **co-rotating** (zero wind); no thermospheric winds. Earth only. | service.py:1043-1051, 1330-1335 | Model names in GUI; zero wind not stated |
| H12 | NRLMSISE-00 density is looked up at the **WGS-84 geodetic altitude and latitude** through a proxy position (custom fix). The exponential model gets the proxy too. | service.py:1339-1344; geodetic_atmosphere.py | Docstring only |
| H13 | Space weather beyond observations + 45-day forecast: MSFC **13-month smoothed** monthly F10.7 and Ap. The same value is used as the daily and the 81-day F10.7, and in all eight 3-hour Ap slots, so there are **no storms and no 27-day rotation variation**. Months MSFC does not cover use NOAA's monthly F10.7 with Ap held at the 1957-present observed mean. Beyond MSFC the last 132 months repeat. Whether MSFC values are observed or 1-AU-adjusted flux, while they are written into the `F10.7_OBS` column, is **unverified**. | spaceweather.py:550-557, 584-600, 672-691 | Warnings name the source and percentile, not the smoothing |
| H14 | Space-weather days outside the run window: Basilisk `spaceWeatherData` "holds the last day's values". The tool refuses runs beyond the resolved span (start - 10 d to end + 10 d). | service.py:2006-2020; spaceweather.py:782-788 | Error message |
| H15 | SRP: cannonball (Cr x A, flux 1361 W/m^2 at 1 AU (B)) or facets (Basilisk flux **1368 W/m^2** (B)). Attitude-independent unless facets. No Earth albedo or IR on the orbit. | service.py:1356-1383 | Not shown |
| H16 | Eclipse: Basilisk `eclipse`, conical umbra/penumbra, **spherical occulter of equatorial radius** ((B) eclipse.cpp:158-213), uniform solar disk, no atmosphere. **Only the central body casts shadows** in non-heliocentric runs, so lunar eclipses of an Earth orbiter are not modelled even with "moon" as a third body. Eros is a sphere of 8.42 km for shadowing. | service.py:993-1025 | Not stated |
| H17 | Eclipses are recorded only if "sun" is tracked; ground access always. | service.py:993; events.py:311-312 | "missing kinds" message names the cause |
| H18 | Ground stations: placed on WGS-84; Basilisk access (`hasAccess`) uses **geocentric** elevation against `min_elevation_deg`, while the reported elevation/azimuth are converted to **geodetic** (difference up to about 0.19 deg). Pass start/end can therefore disagree slightly with the plotted elevation crossing the mask. No refraction, no terrain mask, no range limit. Non-Earth bodies use a sphere. | service.py:949-961, 2607-2614; geodesy.py:36-43; fsw.py:1258-1264 | Docstring only |
| H19 | geodesy.py docstring says longitude refers to "SPICE IAU_EARTH", but ITRF93 is used when IERS files are installed (documentation inconsistency). | geodesy.py:31-32 | n/a |
| H20 | Time: the simulation variable is **TDB seconds since the epoch**; the epoch is UTC; ERFA leap seconds (no leap second after 2017-01-01 is modelled). The epoch is truncated to ms for SPICE. | time_system.py:25-37, 91, 97 | Provenance `time_system` |
| H21 | **Mission Sequence `propagate ... stop_epoch_utc`** target = (stop_epoch - scenario_epoch) **in UTC seconds**, applied to a **TDB** clock. The mismatch is up to about 1.7 ms of TDB-TT plus any leap second inside the span. | mission_engine.py:342-351 | No |
| H22 | Segmented runs: each segment re-starts at `elapsed_to_utc(epoch, offset)` (TDB-correct), truncated to ms again at the SPICE string. Only Cartesian state, attitude, rates, wheel speeds, propellant, SOC and temperatures are carried. Controller filters and noise sequences restart. | long_run.py:28-48, 138-186, 256; time_system.py:91 | Module docstring only |
| H23 | Segmented runs: **provenance is the first segment's** (data files, epoch, time scales). The space-weather `data_file` there is the intermediate resolved CSV, not the CelesTrak/MSFC originals. | long_run.py:204, 133-135; service.py:1102 | No |
| H24 | TLE: SGP4 (WGS-72) from the TLE epoch to the scenario epoch, TEME -> EME2000 (IAU-76/80) **once at the epoch**. After that the orbit is propagated by Basilisk dynamics, not SGP4. | tle.py:19-48, 122-135; service.py:1151-1156 | Info log only (service.py:1155); provenance TRANSFORMATIONS |
| H25 | Mean anomaly input is converted with Basilisk's M2E/E2f (elliptical only, 0 <= e < 1). | service.py:307-315; schema 419-420 | Validation |
| H26 | **Output orbital elements are osculating two-body elements** from `rv2elem` with the central-body GM, in EME2000. Circular/equatorial degeneracies are folded into the anomaly. | service.py:335-395 | Docstring only |
| H27 | **Mean elements = first-order J2-only Brouwer-Lyddane-type map** (Basilisk `clMeanOscMap`), with J2_EARTH (Basilisk constant) and Req, regardless of the degree actually propagated or other perturbations. Blended within 1 deg of the critical inclination; evaluated at 1 deg near equatorial. Samples that are not closed orbits become NaN. | service.py:401-463, 819-835; mean_elements.py | Docstring only |
| H28 | Re-entry altitude = |r| - equatorial radius (**spherical**, up to about 21 km lower than geodetic at the poles). The run stops only for spacecraft with drag. Others get a "later results are not physical" warning. | service.py:2180-2218, 2313-2322 | Warning text |
| H29 | Mission Sequence script context `altitude_m` is spherical too. | mission_engine.py:853-864 | No |
| H30 | **Impulsive maneuvers / Lambert burns change velocity only: no mass or propellant decrement, no finite-burn duration.** | mission_engine.py:584-607, 726-727 | No |
| H31 | Lambert solutions use **two-body** dynamics with the central-body mu; perturbations are ignored. | mission_engine.py:611-727 | Docstring only |
| H32 | Event times (passes, eclipses, burns, apsides, pass start/end stop conditions) are **quantised to recorded samples / dynamics steps**: first and last "on" sample, no root finding or interpolation. Max elevation is the largest *sampled* value. | events.py:21-27, 100-106, 140-141; mission_engine.py:488-494, 580 | Events docstring only |
| H33 | `record_interval_s > 0` means snapshots. Passes shorter than the interval can be missed (the schema comment says so). | schema/scenario.py:2601-2606 | Schema/GUI tooltip (GUI unverified) |
| H34 | **Orbit-number axis uses Earth's mu for every central body.** For Mars, Moon, Sun or Eros the vis-viva mean motion is wrong, so the turn unwrapping (`np.round((expected - raw)/2 pi)`) can add spurious or missing orbits when samples are sparse. I did not run this; for Eros, Earth mu makes `inverse_a` about 2/r and the "expected" turns per sample far too large. | orbit_number.py:48, 81, 92-97, 112-124; gui/results_widget.py:1091 | No |
| H35 | Optical navigation: no rendered image; disk centre and radius from truth geometry plus Gaussian noise. Crescent offset not modelled. Spherical body with Basilisk radius. Attitude knowledge perfect. Filter is Basilisk's two-body relativeODuKF with Basilisk mu. | opnav.py:23-57; optical_navigation.py:23-45 | Module docstring |
| H36 | Landmark navigation: landmarks are facet centres drawn by area; no terrain occlusion; body orientation and attitude exact; EKF dynamics = constant-density polyhedron + uniform spin. **No SRP or solar gravity in the filter** although the truth may include them. | landmarks.py:18-42, 60-67, 119-129; landmark_navigation.py:33-37 | Docstrings |
| H37 | Conservation-drift diagnostic runs only for strictly two-body spacecraft and only flags drift above 1 %. A finite but inaccurate perturbed run gets no numerical-health warning. | service.py:250-286; results.py:195-254 | Warning text when triggered |
| H38 | Exponential atmosphere is a single sea-level exponential (1.217 kg/m^3, H = 8.5 km). The schema docstring itself says it under-predicts LEO density "by many orders of magnitude". | schema/scenario.py:2414-2425 | GUI label "simple, no space weather"; magnitude of error only in the schema docstring |
| H39 | Sensor solar flux is evaluated once: at the scenario epoch (Earth-Sun distance formula) for sensor setup, and for thermal sensors once from the Sun distance at t0. It is not updated during a run. | service.py:1219, 1952-1960 | No |
| H40 | WMM magnetic field only for Earth; outside 5-year validity a warning is given. | service.py:963-973; environment_models.py:156-179 | Warning |

---

### 3. Outputs shown without derivation

| Output (series / event / summary) | How it is computed (code) | What the user is told |
|---|---|---|
| `<sc>.orbit_elements.*` (a, e, i, RAAN, argp, true anomaly) | Per-sample `rv2elem` with central-body GM, EME2000 (service.py:335-395, 2340-2348) | Series name and unit only. "Osculating" is not stated in the name. Frame "N" in provenance `series_frames` (frames.py:98-99) |
| `<sc>.orbit_elements_mean.*` | First-order J2-only `clMeanOscMap` with Basilisk J2/Req, critical-band blending (service.py:401-463) | Name only. The J2-only, first-order nature and the band blending are not in output metadata |
| `<sc>.eclipse.illumination_factor` | Basilisk conical model, central-body occulter only (service.py:997-1025, 2449-2456) | Name/units only |
| Eclipse events (umbra/penumbra, "lowest sunlight") | factor < 1 starts the event; label "umbra" if min < 0.01 (events.py:149-165) | Labels only |
| Pass events and "max elevation" | Basilisk geocentric `hasAccess`; geodetic elevation; sampled maximum (events.py:128-146; service.py:2609-2614) | Labels only |
| `<gs>.access_to_<sc>.elevation/azimuth` | Geocentric SEZ rotated to geodetic (geodesy.py:132-152) | Frame "L" in provenance only |
| Burn events "delta-V" | Difference of cumulative delta-V series around the interval (events.py:117-125, 210-218) | Value only |
| Orbit-number time axis | Unwrapped argument of latitude with Earth-mu mean motion (orbit_number.py) | Axis note "from the ascending node / X axis" only |
| Re-entry warning "below 100 km" | Spherical altitude vs equatorial radius (service.py:2313-2322) | Threshold stated; spherical definition not stated |
| Conservation drift warning | Energy and |h| relative to first sample, 1 % limit (results.py:211-254) | Limit stated; tooltip in GUI |
| `<sc>.navigation_error.*` | Quaternion angle between nav and truth MRPs, etc. (service.py:466-498) | Docstring only |
| Optical/landmark `*_3sigma` | 3 x sqrt(diag P) of the filter covariance (optical_navigation.py:243; landmark_navigation.py:229) | Name only |
| `<sc>.small_body.distance`, impact warning | Polyhedron solid-angle containment (service.py:2220-2234) | Warning |
| `time_s` column in every CSV | TDB seconds since the UTC epoch (time_system.py:34-37) | **Only** in provenance.json `time_system`; the CSV header just says `time_s` (results.py:188) |
| Event CSV `start_utc/end_utc` | TDB -> UTC with ERFA, rounded to ms (events.py:355-371) | Column names only |
| Space-weather content of a run | Mix of observed / 45-day forecast / MSFC / NOAA (spaceweather.py:790-801) | Warnings name the sources, but **not which date ranges came from which source**, and not the smoothing |
| Mission-sequence `report` values | Last recorded sample of each series (mission_engine.py:777-812) | Report timestamp is current sim time, not the sample time (they can differ when `record_interval_s > 0`) |

---

### 4. Forced single options

| Item | Fixed choice | File:line | Reasonable alternatives | Shown in results? |
|---|---|---|---|---|
| Planetary ephemeris | DE430 | kernels.py:91-96 | DE440/DE441; analytic (Basilisk `planetEphemeris`) | Provenance file list only |
| Earth gravity field | GGM03S (Mars GGM2B); degree = order | gravity_field.py:52-55, 74 | EGM2008, EIGEN-6C, JGM-3; GGM03S-J2-only (in Basilisk support data); separate order; Moon/Venus fields | Explain tab "Degree-N Earth"; provenance file |
| Body GM/radius | Basilisk constants | simIncludeGravBody (B) | Field-header GM; user-supplied | No |
| Integrator tolerances | rel 1e-10, abs 1e-8 | service.py:117-118 | user-set tolerances | Provenance only |
| Task structure | one dynamics task for all models | service.py:767-771 | separate environment/FSW task rates | No |
| Third-body model | point mass, DE430 | service.py:775-791 | none needed (standard) | Explain tab |
| Shadow model | conical, spherical occulter, central body only | service.py:997-1025 | include Moon (third bodies) as occulters; cylindrical (faster); oblate Earth shadow | No |
| SRP flux | Basilisk constant (1361 / 1368 (B)) | (B) | time-varying TSI; user flux | No |
| Wind | zero wind (co-rotating) | service.py:1051 | HWM-14 (not in Basilisk) | No |
| Atmosphere | NRLMSISE-00 or exponential only | service.py:1071-1123 | Basilisk `TabularAtmosphere` (exists, not wired, schema 2430-2433); JB2008/DTM2020 (not in Basilisk) | Model choice not in provenance or banner (only the scenario hash) |
| Long-term solar activity | MSFC 13-month smoothed, percentile 95/50/5 | spaceweather.py | constant F10.7/Ap user values (removed by design, 82-84); Schatten; user-defined profile | Warning text |
| Earth orientation | ITRF93 via NAIF PCK, else IAU_EARTH | earth_orientation.py:72-73 | IERS EOP C04 + IAU 2006/2000A | Warning only in fallback case |
| Ground access elevation | Basilisk geocentric test | fsw.py:1263 | geodetic mask, refraction, terrain mask | No |
| Event timing | sample-quantised | events.py:100-106 | root-finding/interpolated crossings | No |
| Mean-element theory | first-order J2 `clMeanOscMap` | service.py:401-463 | Brouwer-Lyddane full; Kozai; numerical averaging | No |
| Element frame | EME2000 for all bodies | frames.py:60-63 | body-equator/IAU frames for non-Earth; TOD/TEME | Provenance |
| Re-entry criterion | 100 km spherical | service.py:158 | user threshold; geodetic altitude | Threshold in text |
| Opnav filter tuning | UKF alpha 0.02, beta 2, kappa 0 | optical_navigation.py:208-211 | user tuning | No |
| Landmark camera | f = 25 mm, RK4 60 s filter step | landmarks.py:56-57 | user values | No |
| CSV precision | %.9g | results.py:191 | user precision. 9 significant digits gives about 0.01 m at LEO radius, **about 100 m for heliocentric positions (1.5e11 m)**, and 1 s time resolution after about 3 years | No |
| Leap seconds | ERFA table, last 2017-01-01 | time_system.py:97 | updatable LSK | Provenance |
| Integrator list | Euler, RK2, RKF45, RKF78 | service.py:101-106 | (no RK4 in Basilisk 2.12 per comment) | Integrator in banner |

**Choices that exist but are not shown with results:** atmosphere model (`nrlmsise00` vs `exponential`), forecast percentile (only shown when the run uses MSFC data), gravity degree, third bodies, `record_interval_s`, Earth frame (only in provenance `frames` P axes), integrator tolerances. The GUI provenance banner shows only version, integrator, step and run time (gui/results_widget.py:1023-1028). provenance.json records the scenario SHA-256 but not these model choices as explicit fields. They can only be recovered by keeping the scenario file.

---

### 5. Data exchanges

| Item | Direction | Path / endpoint | Trigger | Provenance / hash recorded? | File:line |
|---|---|---|---|---|---|
| SPICE kernels naif0012, de430, de-403-masses, pck00010 | read | Basilisk pooch cache (`dataFetcher.POOCH.abspath`) or local support path | every build | `data_files["spice:<name>"]` with path, size, SHA-256 **only if <= 32 MB** (de430.bsp, about 114 MB, gets size only); checked against Basilisk registry hash once per process | kernels.py:167-208, 252-279; service.py:837-840; dependencies.py:44, 80-100 |
| Support data download | network -> cache | NAIF + raw.githubusercontent.com/AVSLab (Basilisk `get_path`) | user consent (startup prompt, Reference data dialog, `kernels-status`, installers) | Basilisk registry checksum | kernels.py:139-164; reference_data.py:64-70 |
| GGM03S.txt / GGM2BData.txt | read | Basilisk cache | degree > 0 | `data_files.gravity_field` | service.py:813; gravity_field.py:89 |
| WMM2025.COF | read | Basilisk cache | magnetometer/MTB with Earth | `data_files.magnetic_field` | service.py:971 |
| Albedo maps (CERES / TES) | read | Basilisk cache | gravity.albedo + CSS | `data_files.albedo_map` | service.py:1206-1207 |
| Eros SPK | read | ~/.cache/SpaceMissionStudio/small_bodies or `<sys.prefix>/share/spacemissionstudio/small_bodies` | eros central body | path, size, sha256, source (from manifest) | small_bodies.py:57-59, 153-167; service.py:841-851 |
| Eros SPK download | network | NAIF a_old_versions URL | user consent (`small-bodies --fetch`) | **size and SHA-256 hard-coded and checked** | small_bodies.py:93-96, 133-142, 182-203 |
| eros007790.tab shape | read | Basilisk cache | polyhedral gravity | `data_files.shape_model` | service.py:800 |
| IERS Earth PCKs (combined + high_prec .bpc, .cmt) | read | ~/.cache/SpaceMissionStudio/earth_orientation or `<sys.prefix>/share/...` | Earth in body list and coverage OK | path, size, sha256 (from manifest at install), source, last datum. At load time only **size** is re-checked, not the hash | earth_orientation.py:75-78, 134-161; service.py:862-875 |
| IERS PCK download | network | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/ (directory listing, newest combined file) | user consent | manifest with SHA-256; NAIF publishes no checksum, so only the DAF/PCK header is checked | earth_orientation.py:194-237, 124-127 |
| CelesTrak SW-All | read | bundled `data/spaceweather/SW-All.txt` **or** ~/.cache/.../spaceweather/SW-All.csv, **whichever has the later observed day** (silent automatic choice) | drag + nrlmsise00 | `data_files.space_weather` = **original CelesTrak/user file** (path, size, sha256 if <= 32 MB) | spaceweather.py:631-652; service.py:1102 |
| CelesTrak download | network | https://celestrak.org/SpaceData/SW-All.csv (also SW-Last5Years) with a **browser User-Agent string** | user consent | manifest JSON (source, sha256, dates); previous kept for rollback | spaceweather.py:114-127, 253-351 |
| MSFC prediction | read | bundled `oct2026f10-prd.txt` or `msfc_file_path` | days beyond observations | **Not in `data_files`** (only named in a warning); reference panel lists the bundled file with sha256 | spaceweather.py:665-669; reference_data.py:153-157 |
| Resolved Basilisk space-weather CSV | write + read | `<cache_dir>/real_<stem>_<mtime>_<msfc-tag>_p<pct>_<first>_<last>.csv` (default ~/.cache/SpaceMissionStudio/spaceweather) | each drag run | Name encodes source mtime/percentile/dates; **file itself not hashed into provenance**; reused if row count matches | spaceweather.py:802-808, 703-771 |
| Long-run whole-span space-weather file | write/read | as above, handed to segments as `local_file` | segmented runs | Recorded as the segment's `space_weather` data file (not the original) | long_run.py:120-135 |
| Vizard model .obj files | write | `<save>_models/` or temp folder removed at exit | Vizard with 3D model | mesh files recorded `model_mesh:*` | service.py:675-707 |
| Result CSVs | write | `<out_dir>/<series>.csv` (time_s + columns, %.9g) | export | `provenance.json` sidecar in the same folder; **ResultSet.warnings are not written by `export_csv`** (they are saved in the run store, run_store.py:134) | results.py:183-192, 286-312 |
| Events CSV | write | user path + `<file>.provenance.json` | export | sidecar | events.py:323-342; gui/event_timeline_widget.py:714-718 |
| Command summary CSV | write | user path | Mission Sequence | none in this module | results.py:347-372 |
| Environment | read | `Path.home()`, `sys.prefix` | always | n/a | spaceweather.py:109; earth_orientation.py:75-78; small_bodies.py:57-59 |
| Logs | write | Python logging (TLE age info, re-entry warning, last state on crash) | runs | n/a | service.py:1155, 2204, 2637-2700 |

Implicit or invisible items:
- (a) automatic newest-file choice between the bundled and downloaded space weather;
- (b) the reuse of cached resolved CSVs by row count only;
- (c) `_VERIFIED` hash cache, keyed on size and mtime;
- (d) the in-process `_LOADED` CelesTrak parse cache, keyed on path and mtime (spaceweather.py:516);
- (e) the Earth PCK manifest trusted on size only after install.

---

### 6. Existing transparency features (credit)

- **RunProvenance** (results.py:60-138; service.py:2276-2296, 2632-2634) records:
  - tool, Basilisk and qualified versions, dependency versions;
  - run start, integrator, step and tolerances;
  - RNG seeds and how they were derived;
  - scenario SHA-256;
  - data files with size and SHA-256;
  - time scales (UTC, TAI, TT, TDB offsets, last leap second, ERFA routines);
  - frame definitions, transformations, and the frame of each series.

  It is written as `provenance.json` next to exports.
- **Frames/time documentation in code**: frames.py:19-84 (naming convention, TEME->N, N->P), time_system.py:19-52 (TDB clock statement).
- **Warnings that name sources**:
  - space-weather source, percentile and MSFC repetition (spaceweather.py:792-801);
  - missing or non-covering IERS data, with an error estimate (service.py:876-887);
  - WMM validity (environment_models.py:156-179);
  - re-entry and small-body impact (service.py:2232-2234, 2317-2322);
  - two-body drift (results.py:241-253);
  - propellant depletion (service.py:2300-2305).
- **Refusals instead of silent extrapolation**:
  - beyond EOP coverage (service.py:1988-2004) and beyond space-weather coverage (2006-2020);
  - kernel missing or checksum mismatch (kernels.py:187-203);
  - Eros SPK hash check (small_bodies.py:133-142);
  - NaN state with a clear message (service.py:173-225, 379-387).
- **Reference data inventory** (reference_data.py): every file with source URL, size, SHA-256, install time, coverage and stale flag; download consent lists (64-82).
- **Offline policy**: no runtime downloads (kernels.py:167-205 `cached_path`).
- **Manifests and rollback** for downloaded space weather and EOP (spaceweather.py:315-401; earth_orientation.py:164-282).
- **Bundled data README** with source, update date and licence (data/spaceweather/README.md).
- **Documented corrections to Basilisk with measured impact** in module docstrings:
  - gravity reference radius (gravity_field.py:23-37);
  - geodetic atmosphere (geodetic_atmosphere.py:22-34);
  - mid-step planet orientation (planet_rotation.py:22-44);
  - TLE handling (tle.py:47-48);
  - mean-element singularity handling (mean_elements.py);
  - integrator tolerances (service.py:108-116).
- **Explain tab** summarises gravity and drag/SRP/gravity-gradient badges, with gravity fidelity notes (truncation vs SRP, scenario_checks.py:515-540).
- **events.missing_kinds** tells why an event kind is absent (events.py:306-320).
- **Series catalog prediction** (series_names.py) so users can see which outputs a scenario will produce.

---

### 7. Selectable-model candidates

| Candidate | What it would give | Basilisk support (as far as I know) |
|---|---|---|
| Gravity field file and separate order; Moon/Vesta fields | EGM/EIGEN fields; J2-only cases; lunar orbits | `GGM03S_J2_only`, `GGM2B_J2_only`, `VESTA20H` exist in the support-data enum ((B) dataFetcher.py:319-325); any coefficient file via `loadGravFromFileToList` |
| Atmosphere: tabular / user table | Mission-specific density profiles, other models exported as tables | `TabularAtmosphere` exists ((B) simulation/environment/TabularAtmosphere) |
| Occulting bodies list (Moon) | Lunar eclipses for Earth orbiters | `eclipse.addPlanetToModel` takes any SPICE body; only wiring needed |
| Ephemeris kernel choice (DE440) | Current JPL ephemeris | `spiceInterface` loads any SPK; kernel list is a parameter (kernels.py:252) |
| Analytic ephemeris option | Fast runs, no kernels | `planetEphemeris` module ((B) environment/planetEphemeris) |
| Magnetic field: centred dipole | Simple field / non-WMM epochs | `magneticFieldCenteredDipole` ((B)) |
| Solar flux model | Variable TSI / flux at spacecraft | `solarFlux` module ((B)) |
| Earth radiation (albedo/IR) pressure on the orbit | Higher-fidelity LEO perturbation | `earthRadiationModel` / `albedo` exist ((B)); a force effector would be needed (unverified) |
| Integrator tolerances in SimSettings | User control and visibility | `setRelativeTolerance`/`setAbsoluteTolerance` already used (service.py:124-127) |
| Separate environment/FSW task rates | Decouple ephemeris/atmosphere refresh from dynamics step | Standard Basilisk multi-task pattern |
| Mean-element theory selection (e.g. full Brouwer, Kozai, numerical averaging over one orbit) | Mean elements consistent with the propagated field | Not in Basilisk beyond `clMeanOscMap`; numerical averaging is plain post-processing |
| Event root-finding / interpolation | Sub-step pass, eclipse and apsis times | Post-processing on recorded states; Basilisk events only fire at task times |
| Re-entry threshold and geodetic altitude | User-defined interface altitude | Plain parameter |
| Space-weather profile option (constant F10.7/Ap, user CSV of monthly values) | Sensitivity studies | `spaceWeatherData` reads any CSV in its format (spaceweather.py:69-73) |
| Shadow model choice (cylindrical vs conical) | Comparison with other tools | Basilisk eclipse is conical only (unverified for other modules) |
| Ground station mask: geodetic elevation, refraction, terrain profile | Pass prediction matching operations tools | Basilisk `groundLocation` has min elevation only (as used); post-processing possible |
| Opnav UKF tuning, landmark camera focal length | Filter studies | Plain parameters already in Basilisk/own code |

---

#### Notable cross-checks and inconsistencies found

1. orbit_number.py always uses Earth's mu (H34): this looks like a bug for non-Earth central bodies. Found by reading the code; not run.
2. Low-accuracy predicted-EOP note is filtered out of run warnings (service.py:2306-2307) (H9).
3. Faceted SRP flux 1368 W/m^2 vs cannonball 1361 W/m^2 ((B) values) (H15).
4. Mean elements use Basilisk J2 = 1082.616e-6 and Req = 6378136.6 m, while the propagated GGM03S field has its own C20 and R = 6378136.3 m. environment_models.py uses J2 1.08263e-3 and GM 3.986004415e14. There are three different Earth constant sets in the code.
5. Mission Sequence epoch stop uses UTC differences on a TDB clock (H21).
6. Impulsive maneuvers are not logged and do not change mass (H30).
7. Segmented-run provenance is the first segment only and names the intermediate space-weather CSV (H23).
8. The MSFC file used by a run is not in `data_files` provenance (Sec. 5).
9. `export_csv` does not write the run warnings (results.py:286-312).
10. geodesy.py docstring names IAU_EARTH as the frame for longitude even when ITRF93 is used (H19).

---

## Appendix B: Mission-analysis calculations

*Detailed findings of review B, as written by the reviewer and checked as described in Section 1.*

Scope: `spacemissionstudio/engine/` modules lifetime, propellant_budget, propellant_bookkeeping,
link_budget, solar_arrays, data_budget, data_handling, orbit_design, orbit_maintenance,
geo_station_keeping, constellation, formation, formation_control, roe, roe_formation,
device_catalog, spacecraft_templates, facets, scenario_checks, scenario_explainer, monte_carlo,
monte_carlo_results, seeds, run_summary, scenario_diff, fsw, plus the configuring dataclasses in
`schema/scenario.py`. I checked how values are exposed in `cli.py` and the GUI widgets that show these
results (`gui/lifetime_widget.py`, `gui/budget_widget.py`, `gui/mission_dashboard_widget.py`,
`gui/spacecraft_editor.py`, `gui/ground_station_editor.py`, `gui/param_form.py`).

All paths are relative to `SpaceMissionStudio/spacemissionstudio/`. Line numbers come
from reading the files. "BSK" means Basilisk. I also read the Basilisk sources in
this repository's Basilisk `src/` where the app depends on their defaults.

Columns used in the item-1 tables:
- **Visible?**: the value, or a label naming it, appears in a CLI or GUI output. "Doc only" means
  it appears only in a docstring or code comment.
- **Editable? (how)**: JSON = a scenario-file field; GUI = a form field; CLI = a command-line option;
  "No" = hard-coded.
- **Source**: the standard or reference the code itself cites. "None given" means the code cites none.

---

### 1. Hard-coded constants, defaults, margins, thresholds and rules

#### 1.1 Orbital lifetime (`engine/lifetime.py`)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| lifetime.py:65-67 | MU_EARTH, REQ_EARTH, J2_EARTH | 398600.436e9 m^3/s^2; 6378136.6 m; 1082.616e-6 | Earth constants for decay, J2 rates, altitude | No | No | BSK astroConstants.h (comment L64) |
| lifetime.py:68 | OMEGA_EARTH_RAD_S | 2*pi/23.9345 h [rad/s] | Co-rotating atmosphere (relative wind) | No | No | None given |
| lifetime.py:70 | REENTRY_ALTITUDE_KM | 120 km | Re-entry criterion: decay stops when the perigee reaches 120 km | Doc only (not in CLI or GUI output) | No | None given |
| lifetime.py:71 | RING_POINTS | 16 points | Orbit-average sampling of drag | No | No | None given |
| lifetime.py:72-73 | MAX_STEP_S, _MAX_PERIGEE_DROP | 86400 s; 0.01 of remaining perigee height | Step control of the decay integration | No | No | None given (L302-304 claims a 2 % bias without the midpoint step) |
| lifetime.py:76 | ZERO_DEBRIS_YEARS | 5 yr | "5-year rule" pass/fail badge (CLI and GUI) | Label yes, value implied | No | Comment only: "ESA Zero Debris approach (and the FCC's 5-year rule)" |
| lifetime.py:77 | IADC_YEARS | 25 yr | "25-year guideline" badge | Label yes | No | Comment only: "IADC / ISO 24113 guideline" |
| lifetime.py:80 | MAX_HORIZON_YEARS | 100 yr | Upper limit of the look-ahead | Yes (CLI error text, GUI spin range) | Range limit only | None given (audit R6) |
| lifetime.py:300, 485, 534; cli.py:1243; gui/lifetime_widget.py:49 | max_years default | 30 yr | Look-ahead horizon | Yes (GUI field; CLI help) | CLI `--max-years`, GUI "Look ahead" | None given |
| lifetime.py:364, 433, 487, 535; cli.py:1245; lifetime_widget.py:217 | forecast_percentile default | 50 % (MSFC) | Solar activity used past the observations | Yes (GUI combo label "AD10 end of life") | CLI `--forecast-percentile` {95, 50, 5}, GUI combo | ESA AD10 Sec. 5.9 (docstring L368, L540) |
| cli.py:1247; lifetime_widget.py:224; lifetime.py:542 | Lifetime Cd default | 2.2, which **replaces the spacecraft's own Cd** by default | Ballistic coefficient of the decay | GUI combo label; CLI help. Results do not show which Cd was used | CLI `--drag-coeff X\|own`, GUI combo {2.2, own} | ESA AD10 Sec. 5.2 |
| lifetime.py:254 | exponential atmosphere | 1.217 kg/m^3 at the surface, 8500 m scale height | Density when `space_weather.atmosphere_model = "exponential"` | Yes: a warning says the lifetime is overstated (L372-374) | JSON/GUI model choice; the constants are fixed | BSK `exponentialAtmosphere` helper (docstring L250-252) |
| lifetime.py:187 | GMST formula | 280.46061837 + 360.98564736629 d [deg], with UT1 = UTC | Earth rotation fed to MSIS | No | No | None given (scenario_checks.py uses a different, IAU_EARTH rotation, L149-156) |
| lifetime.py:344, 584 | g0 | 9.80665 m/s^2 | Deorbit-burn rocket equation | No | No | None given (inline literal, not a named constant) |
| lifetime.py:123, 305, 388 | year length | 365.25 d | Converts years to seconds for horizons and lifetime | No | No | None given |
| lifetime.py:382 | pad | 11 d | Margin on space-weather data coverage | No | No | "the resolver's own padding, plus a day" |
| lifetime.py:403 | MAKEUP_STEP_S | 21600 s | Sampling step of the drag make-up (propellant budget) | No | API parameter only | None given |
| lifetime.py:427 | held_orbit iterations | 3 | Mean-radius correction of the held orbit | No | No | Comment: "converges in 2" |
| lifetime.py:357-359 | facet tumbling area | sum(area)/4; Cd area-weighted | Drag area whenever facets exist | Doc only | Indirect (facets) | Comment: "exact for a convex body" |
| lifetime.py:157, 178 | e floor, i clamp | 1e-7; [1e-9, pi-1e-9] rad | Numerical guards for clMeanOscMap | No | No | Code comments |
| lifetime.py:506 | DeorbitPlan.sufficient tolerance | 1e-6 km | Decides between "sufficient" and the not-enough-propellant note | No | No | None given |
| gui/lifetime_widget.py:48, 206 | deorbit perigee default and range | 250 km; 130-2000 km | GUI deorbit target | Yes | GUI | None given |

#### 1.2 Delta-V and propellant budget (`engine/propellant_budget.py`, `schema/scenario.py` PropellantBudgetConfig)

The docstring L19-22 cites ESA AD10 "Guidelines for the computation of the Delta-V and Propellant Mass
budgets", EOP-FM/2024-07-177 issue 3.0. Each constant names its AD10 section.

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| propellant_budget.py:85 | G0_M_S2 | 9.80665 m/s^2 | Ve = eta*Isp*g0 | No | No | None given |
| :86-87 | MU/REQ | BSK values | Circular speed, altitude | No | No | BSK astroConstants.h |
| :88 | CONVERGENCE_KG | 0.1 kg | Iteration stop on total propellant | Iteration count shown (GUI status, budget_widget.py:541) | No | AD10 Sec. 6.5 |
| :89 | CAM_SMA_CHANGE_M | 100 m up, then back | Delta-V of one collision avoidance | No (label shows only the count) | No | AD10 Sec. 6.2.4 |
| :90 | CAM_COUNT_FACTOR | x4 | Margin on the collision-avoidance count | Yes: row label "(N x 4)", margin "x4 count" | No | AD10 Sec. 5.6 |
| :91 | ATTITUDE_PROPELLANT_FACTOR | x2 (+100 %) | Thruster attitude-control propellant | Yes: margin "+100% propellant" | No | AD10 Sec. 5.6 |
| :92 | CONTROLLED_LAST_BURN_MARGIN | +15 % | Last burn of a controlled re-entry | Yes: margin "+15% on the last burn" | No | AD10 Sec. 5.6 |
| :93-94 | RESIDUAL / UNCERTAINTY | 1 % / 2 % of tank capacity | Residual and loading-uncertainty rows | Yes: margin text and a note saying the AD10 summary table prints 10 %/20 % (L390) | No | AD10 Secs. 5.8, 6.4 |
| :95 | EOL_DRAG_COEFF | 2.2 | Cd of the uncontrolled re-entry (disposal) solver | **No**: the disposal row shows the perigee and years, not the Cd | No | AD10 Sec. 5.2 |
| :96 | OPERATIONS_DRAG_COEFF | 3.0 | Only triggers a note when the run or estimate Cd differs | In the note | No | AD10 Sec. 5.2 |
| :97 | OPERATIONS_PERCENTILE | 95 % | Drag estimate of in-plane control; note when the run used another value | In the note | No | AD10 Sec. 5.9 |
| :98 | EOL_PERCENTILE | 50 % | Disposal lifetime solver | **No** | No | AD10 Sec. 5.9 |
| :99-100 | GEO graveyard | 235 km + 1000 km * Cr*A/m | Raise of the graveyard orbit | Yes: label "+N km" | Cr, A editable (spacecraft) | AD10 Sec. 6.3.1.3 |
| :101 | _MAX_ITERATIONS | 50 | Iteration cap | Note when hit (L459) | No | None given |
| :102 | LAUNCH_DELAYS_YEARS | 0,1,2,3,4,5 yr | Launch-delay sweep | Yes (table rows) | No (API parameter only) | AD10 Sec. 5.5 |
| :338, 355 | run-scaling flag | 1.05 | Labels a run shorter than the mission "last run, scaled" | Yes (source column and note) | No | None given |
| :273, 282, 286-287 | disposal solver | horizon = 1.5*target + 1 yr; perigee bisection from 140 km (120 + 20) to 2 km tolerance | Search for the uncontrolled re-entry perigee | Perigee result shown to 1 km in the label; the 2 km tolerance is not shown | No | None given |
| :289, 294 | Isp 1e9 s | dummy | Gets delta-V only from deorbit_burn | No | No | Internal |
| :623, 659-660 | ALTITUDE_STEP_KM; default altitudes | 50 km; 5 altitudes, floor 250 km | Altitude trade grid | GUI placeholder lists them (budget_widget.py:415) | CLI `--altitudes`, GUI text field | None given |
| cli.py `_altitudes_arg` | altitude range | 150-2000 km | CLI input limit | Error text | No | None given |
| :678 | SSO detection tolerance | 0.05 deg | Re-sets SSO inclination in the altitude trade | No | No | None given |
| :242 | GEO E-W share fallback | 0.5 | Split of propellant when the run's delta-V is 0 | No | No | None given |
| schema/scenario.py:1520 | mission_years | 5 yr | Mission length, EOL epoch, run scaling | GUI | JSON, GUI Budget tab | AD10 Sec. 5.7 |
| :1521-1522 | dry_mass_includes_margin / system_margin_fraction | False / 0.15 | Dry-mass system margin | GUI tooltip | JSON, GUI | AD10 Sec. 5.10 |
| :1523 | tank_capacity_kg | 0 = budget total | Base of residual and uncertainty; fit check | GUI | JSON, GUI | AD10 Sec. 5.8 |
| :1525-1528 | thrust angle, misalignment, plume and modulation efficiency | 0 deg, 0 deg, 1, 1 | eta = cos*cos*eta_plume*eta_mod (propellant_budget.py:137-140) | Efficiency shown | JSON, GUI | AD10 Sec. 5.11 |
| :1530-1534 | injection errors | 0 | BOL corrections | GUI | JSON, GUI | AD10 Sec. 6.1 ("2-sigma") |
| :1540-1541 | collision_avoidance_count, attitude_thruster_propellant_kg | 0 | CAM, ACS rows | GUI; note when CAM = 0 (L389) | JSON, GUI | AD10 6.2.4 (DRAMA) |
| :1543-1545 | disposal / disposal_lifetime_years | uncontrolled_reentry / 5 yr (validated (0, 25]) | EOL strategy | GUI | JSON, GUI | AD10 Sec. 6.3.1.2 |
| :1552, 1571 | validation limits | mission_years (0, 30]; disposal lifetime (0, 25] | Input limits | Error text | No | None given |

#### 1.3 Propellant bookkeeping and orbit controllers (`propellant_bookkeeping.py`, `orbit_maintenance.py`, `geo_station_keeping.py`, `formation_control.py`)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| propellant_bookkeeping.py:54, 71; orbit_maintenance.py:451, 960, 1729; geo_station_keeping.py:104; formation_control.py:128 | g0 default | 9.80665 m/s^2 | mdot = T/(Isp*g0) in every controller | No | No | None given |
| propellant_bookkeeping.py:98; orbit_maintenance.py:683, 1800; geo_station_keeping.py:247, 250 | empty-tank floor | 1e-9 kg | Propellant depleted: thrust inhibited, warning logged once | Run warning | No | Internal |
| orbit_maintenance.py:160 | _MAX_NON_CONVERGENT_CYCLES | 2 | Suspends drift-orbit phasing after 2 non-improving cycles | No (only `suspendedDueToNonConvergence`) | No | Rationale in comment, no reference |
| orbit_maintenance.py:171 | _RELATIVE_SMA_TRIM_TOLERANCE_M | 25 m | Relative-SMA trim threshold | No | No | Comment cites measured ~0.1 m noise |
| orbit_maintenance.py:278-279 | e-neutral gate tolerance | max(4a/(v n), 2.5*2*a*t/v) | Whether a new firing may start | No | Toggle only (`eccentricity_neutral_burns`) | Factor 4 derived in comment; **factor 2.5 unexplained** |
| orbit_maintenance.py:320-324 | minimum impulse bit rule | skip if < 0.5 bit, else round up to 1 bit | Small burns | No | `min_on_time_s` JSON/GUI | None given |
| orbit_maintenance.py:497, 1021; formation_control.py:160 | smoothing window | 1 orbit period at the target altitude | Boxcar on altitude, phase error, relative SMA | No | No | Ported from ../missionAnalysis |
| schema/scenario.py:845 (SK), formation.py:158 | eclipse_sunlit_threshold | 0.99 | Thrust allowed only above this illumination | GUI field | JSON, GUI, CLI `phasing --eclipse-sunlit-threshold` | None given ("approximates a solar-electric bus", L824-825) |
| schema/scenario.py:850 | min_on_time_s | 0 s (ideal) | Minimum firing | GUI | JSON, GUI | None given |
| orbit_maintenance.py:1426 | phasing law | deltaA = error*a/(1.5 n T) | Drift-orbit size | No | T = `correction_window_days` | Two-body mean-motion relation (comment) |
| orbit_maintenance.py:1310; formation_control.py:273 | Vizard gauge scale | 2 x target separation | Live gauges only | Vizard | No | Comment |
| schema/scenario.py:1018-1026 | Phasing defaults | reconfig 90 d; tolerance 0.10; restore 0.02; window 3 d; max drift 90 d; max dSMA 3 km | Drift-orbit controller | GUI | JSON, GUI, CLI `phasing` | "reasonable ported defaults (../missionAnalysis/mission_config.py)" L992-993; 3 d window rationale L1021-1023 |
| schema/scenario.py:1036-1038 | mean_oe_gain, hill gains | 2500 m^2/s^3 per kg; K 2e-6 1/s^2; P 2e-3 1/s | BSK meanOEFeedback / hillFrameRelativeControl | GUI | JSON, GUI | None given |
| formation_control.py:372-373 | mean_oe K scaling | K = gain x **initial** mass (not updated as propellant burns) | Lyapunov gain | No | Gain only | None given |
| geo_station_keeping.py:77 | _OMEGA_EARTH | 7.2921159e-5 rad/s | Longitude drift and daily fit | No | No | None given |
| geo_station_keeping.py:79-80 | _J22, _LAMBDA_22 | 1.81554e-6; -14.928 deg | Triaxiality acceleration used to plan E-W burns | No | No | **None given**; not tied to the gravity field the simulation uses |
| geo_station_keeping.py:81 | _MAX_HALF_ARC | 60 deg | Longest N-S burn arc per node | No | No | None given |
| geo_station_keeping.py:82 | _INCLINATION_RESET_FRACTION | 0.25 | N-S burn target: 1/4 of the limit | No | No | None given |
| geo_station_keeping.py:83 | _FIT_INTERVAL_S | 600 s | How often the E-W fit is redone | No | No | None given |
| geo_station_keeping.py:185 | overshoot rule | 0.25 x deadband | Stop-the-drift burn | No | No | None given |
| geo_station_keeping.py:305 | N-S completion | 0.9 x needed delta-V | Ends an N-S maneuver | No | No | None given |
| schema/scenario.py:884-885 | GEO box defaults | 0.05 deg longitude half-width; 0.05 deg inclination | GEO SK limits | GUI | JSON, GUI | None given |
| schema/scenario.py:933-935 | ConstantThrust defaults | 0.01 N, Isp 1500 s, 2 kg, VNB [1,0,0] | Continuous thrust | GUI | JSON, GUI | None given |

#### 1.4 RF link, data handling, power (`link_budget.py`, `data_handling.py`, `solar_arrays.py`, schema)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| link_budget.py:60 | _C_LIGHT_M_S | 299792458 m/s | FSPL | No | No | Physical constant |
| link_budget.py:61 | _K_BOLTZMANN_DBW_HZ | -228.6 dBW/K/Hz (rounded; 10 log10(1.380649e-23) = -228.599) | N0 | No (N0 itself is shown on the dashboard) | No | Comment gives the formula |
| link_budget.py:62 | _MAX_POINTING_LOSS_DB | 30 dB clamp | Pointing loss ceiling | Dashboard shows the loss value | No | Comment |
| link_budget.py:190 | pointing loss | 12 (theta/theta_3dB)^2 dB | Loss for the "fixed" pattern with a beamwidth set | Value shown, formula not | Beamwidth JSON/GUI | "standard parabolic-reflector/Gaussian-main-lobe approximation" (L154-157); no specific reference |
| link_budget.py:73-79 | cos^n patch | D0 = 2(n+1), n = G/2 - 1 | "cosine" pattern | No | Pattern choice JSON/GUI | Balanis, *Antenna Theory*, ch. 2 |
| link_budget.py:89-91 | HPBW search | 0.05 deg grid, -3 dB, 360 deg if never below | Reported beamwidth | Unverified where shown | No | None given |
| schema/scenario.py:554-556 | tx gain, implementation_loss_db, required_ebno_db | 0 dBi; **2 dB**; **6 dB** | EIRP loss and the Eb/N0 threshold | GUI fields | JSON, GUI | None given; the modulation and coding behind 6 dB are not stated |
| schema/scenario.py:581 | antenna_front_to_back_db | 15 dB | Patch back-lobe floor | GUI | JSON, GUI | None given |
| schema/scenario.py:2371, 2375-2376 | GS min_elevation_deg, rx gain, Tsys | 10 deg; **0 dBi** (JSON default); 290 K | Access mask, G/T | GUI | JSON, GUI | None given |
| gui/ground_station_editor.py:106, 114 | GUI new-station defaults | rx gain **45 dBi**; Tsys 290 K | Same fields | GUI | GUI | None given. **The GUI default (45 dBi) differs from the schema/JSON default (0 dBi).** |
| data_handling.py:149; fsw.py:696 | link-close rule | margin >= **0 dB** | Downlink allowed (gate); Vizard "link OK" | link_closed series | **No** (no required-margin policy) | None given |
| data_handling.py:79 | PACKET_SIZE_BITS | 1e6 bit | Transmitter packet | No | No | BSK examples/scenarioGroundDownlink.py |
| data_handling.py:78; data_budget.py:59; run_summary.py:73 | Gbit | 1e9 bit | Units | Yes | No | SI |
| scenario_explainer.py:428, 457 | _PASS_MINUTES | 10 min "typical LEO pass" | "Gbit per 10-min pass" note | Yes (the note says 10-min) | No | None given; not the predicted pass length |
| BSK astroConstants.h:53 (used by simpleSolarPanel.cpp:146) | SOLAR_FLUX_EARTH | 1361 W/m^2 x (1 AU/r)^2 | Solar panel power | No | No | BSK; environment_models.py:47 cites ECSS-E-ST-10-04C Table 6-2 for the same value |
| schema/scenario.py:503-508 | PowerConfig | efficiency required (GUI default 0.29, spacecraft_editor.py:850); idle load 0 W; battery 100 Wh; SOC 1.0 | Power budget | GUI | JSON, GUI | None given |
| schema/scenario.py:522, 530 | plausibility ceilings | panel <= 2000 m^2; battery <= 1e6 Wh | Units-typo guard | Error text with a "units mixup" hint | No | ISS array area (comment) |
| solar_arrays.py:79, 84, 91-92 | flex array model | uniform thin plate; d = span/2; k = J(2 pi f)^2; c = 2 zeta sqrt(kJ) with the hub fixed | Hinge spring and damper | Doc only | f, zeta JSON/GUI | Derivation in docstring L25-41 |
| solar_arrays.py:70 / scenario.py:806 | perpendicularity tolerance | 1e-3 | Validation | Error text | No | None given |

#### 1.5 Orbit design, constellation, formation, ROE

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| orbit_design.py:52-54 | J2, Req, mu | BSK values | SSO inclination | No | No | BSK (comment L44-49) |
| orbit_design.py:55 | _TROPICAL_YEAR_DAYS | 365.2421897 d | SSO node rate | No | No | None given |
| orbit_design.py:60 | DEFAULT_LTAN_HOUR | 10.5 h | Templates and wizard RAAN | Yes (wizard) | Wizard | "most common real operational choice" (no reference) |
| orbit_design.py:91, 126 | rounding | 0.01 deg | SSO inclination and RAAN returned rounded | No | No | Comment justifies it as "false precision" |
| orbit_design.py:107-114 | Sun RA | Almanac low-precision formula | RAAN for an LTAN | No | No | Astronomical Almanac / Vallado 5.1 |
| orbit_design.py:129; scenario_checks.py:57 | _TT_MINUS_UTC_S | 69.184 s (37 leap seconds) | GEO elements and pass prediction | No | No | Comment says "constant since 2017"; wrong if a new leap second is added |
| orbit_design.py:148-150 | IAU pole and prime meridian | alpha0 = -0.641T, delta0 = 90 - 0.557T, W = 190.147 + 360.9856235d | GEO elements | No | No | SPICE pck00010 |
| constellation.py:98-114 | equatorial radii, J2 table | e.g. Earth 6378.1366 km; Mars J2 1960.45e-6 | Altitude to SMA; mean/osculating mapping | No | No | BSK astroConstants.h (manually synced, L95-97) |
| constellation.py:189 | Walker RAAN spread | 360 deg (delta) / 180 deg (star) | Walker pattern | Pattern choice | CLI `constellation --pattern`, GUI | Vallado; Wertz SMAD (L28-29) |
| constellation.py:140-145 | Walker defaults | e = 0, argp = 0, RAAN offset 0 | Walker | CLI | CLI, GUI | None given |
| constellation.py:269 | separation to angle | theta = d/a (arc) | Along-track target | Doc only | No | Docstring |
| formation.py:139-161; cli.py `phasing` | PhasingFormationRequest defaults | along-track 50 km; SK deadband 2 km; thrust 0.05 N; **Isp 1500 s**; propellant 5 kg | Follower generator | CLI and GUI dialog | CLI, GUI | None given |
| formation.py:332-334 | R/N placement | zero relative velocity (hill2rv) | Initial follower state | Docstring and GUI dialog note (formation.py:78-93) | No | Documented limitation |
| schema/scenario.py:1074 | ROE_MAX_CHIEF_ECCENTRICITY | 0.01 | ROE validity | Error text | No | "near-circular guidance" |
| schema/scenario.py:1129-1143 | RoeFormation defaults | tolerance [2, 20, 10, 10] m; window 1 d; max drift 100 m; max burn fraction 0.1 orbit; drag window 1 d; continuous gain 25000; refresh 600 s | ROE controller | GUI | JSON, GUI | Comment on the gain only ("ten times phasing's default") |
| roe_formation.py:141-155 | internal heuristics | _SUNLIT_BINS 72 (5 deg); _ECLIPSE_RETRIES 3; _HOLDING_CHECK_FRACTION 0.25; _GLIDE_ORBITS 3; _DIRECT_DL_FACTOR 5; _PLACEMENT_ITERATIONS 6; _DRAG_MIN_ORBITS 4; _DRAG_JUMP_M 0.1 m; _DRAG_HOLD_FRACTION 0.6; _DRAG_LOOKAHEAD_ORBITS 2; _DRAG_TRIGGER_FRACTION 0.7 | Impulsive guidance decisions | Docstring L31-75 describes them | **No** | None given (design rationale in comments) |
| roe_formation.py:484-506 | drift factors | 0.25 tol, 1.25, 1.5, min check 60 s | Drift planning | No | No | None given |
| roe.py:598-599 | sunlit_locations | 3 locations, 5 deg grid, 20 deg min separation | Burn placement in sunlight | No | No | None given |
| roe.py:347, 334, 530, 544 | drag hold and correction thresholds | 0.6; 0.5 tol; 0.25 tol; 0.5 x fine | ROE guidance | No | No | Koenig et al. 2017 (method), thresholds not cited |
| roe.py:25-92 | ROE math | D'Amico 2010; Koenig, Guffanti, D'Amico JGCD 40(7) 2017; Gaias & D'Amico JGCD 38(6) 2015; D'Amico & Montenbruck JGCD 29(3) 2006 | STM, Gauss ROE, passive safety | Docstring | No | **Well cited** |

#### 1.6 Catalogs and templates (`device_catalog.py`, `spacecraft_templates.py`, `facets.py`)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| device_catalog.py:122-773 | CATALOG, 32 entries (8 star tracker, 11 thruster, 4 torque rod, 3 CSS, 2 IMU, 2 magnetometer, 2 RW) | per entry | Presets for sensor and actuator params | GUI picker shows manufacturer, notes, ITAR note | Preset is fully editable after selection (L31-36) | Each entry has `source_url`, heritage, procurement status; the "supplier database" is dated 07 Oct 2026 (L76-87) |
| device_catalog.py:142-147, 354-356 | star-tracker conversion | worse axis; n-sigma divided down to 1-sigma; isotropic `noise_arcsec` | Star-tracker noise | Notes | Yes | Datasheets, with derivations stated |
| device_catalog.py:172-178, 474-478 | gyro ARW conversion | ARW to per-step std **for a 1 s step**; "for another step dt, multiply by 1/sqrt(dt)" | IMU noise | Notes | Yes, but the app does **not** rescale for the actual step | Datasheets |
| device_catalog.py:237-243 | MM200 noise | 1.18 nT/sqrt(Hz) used directly as a per-sample std ("placeholder") | Magnetometer noise | Notes | Yes | Datasheet |
| device_catalog.py:519-534 | ZARM noise | tan(1 deg) x 45000 nT ~ 800 nT, "order-of-magnitude figure" | Magnetometer noise | Notes | Yes | Derived |
| device_catalog.py:539-541 | RW Js | H/Omega_max; **6000 RPM assumed** when the speed is not published | Wheel inertia | Notes | Yes | Datasheets |
| device_catalog.py:610, 631, 693, 727, 769 | "top of the published range" | e.g. B20 18 N (range 6.5-18 N); SVT01 0.1 N; ArianeGroup 1.1 N; REGULUS 0.65 mN; Strasspace 15 A m^2 | Thrust and dipole | Notes | Yes | Datasheets. Choosing the top of the range is **optimistic** |
| device_catalog.py:617, 631, 665, 741, 755; BSK src/utilities/simIncludeThruster.py:81, 84 | missing Isp / MinOnTime | Isp left unset, so BSK's default **steadyIsp = 100 s** and **MinOnTime = 0.020 s** apply | Propellant use with a fuel tank; pulse limits | Notes say "Isp not published" but **not** that 100 s is used | Yes (set steadyIsp) | BSK default |
| device_catalog.py (all thrusters, RW, CSS) | mounting placeholders | r_B/tHat_B/gsHat_B/nHat_B = [1,0,0] or [0,0,1] | Geometry | Notes | Yes | Placeholder |
| spacecraft_templates.py:78 | _RW_EXAMPLE_PARAMS | 6000 RPM, 0.2 N m, Js 0.028 kg m^2 | ESPA template wheels | Template | Yes | Mirrors the GUI example values |
| spacecraft_templates.py:84-86 | placeholder orbit | a 6878 km, e 0, i 97.4 deg | Every template | Yes | Yes | "SSO at ~500 km" |
| spacecraft_templates.py:125, 128 | Cd, Cr | 2.2, 1.3 | Drag and SRP | Yes | Yes | None given |
| spacecraft_templates.py:131-132 | star tracker, gyro noise | 5 arcsec; 1e-5 rad/s | Template sensors | Yes | Yes | None given |
| spacecraft_templates.py:154-218 | buses | 100/150/300/500 kg; panel eff. 0.29; idle 25/60/150/250 W; battery 150/300/700/1200 Wh; SOC 0.9; wheels 6/12/25 N m s; rods 15/30/50 A m^2 | Bus templates | Template description | Yes | "ROUNDED, ORDER-OF-MAGNITUDE-REASONABLE ... for illustration" (L39-48) |
| schema/scenario.py:1800-1818 | SpacecraftConfig defaults | 100 kg; I = diag(10); Cd 2.2; A 1 m^2; Cr 1.3; A_srp 1 m^2 | Every new spacecraft | GUI | JSON, GUI | None given |
| facets.py:38-40 | optical coefficients | bus (0.336, 0.139); array front (0.16, 0.16); back (0, 0.56) | Facet SRP | No | Per facet, JSON/GUI | BSK examples/scenarioSepMomentumManagement.py |
| facets.py:41 | DRAG_COEFF | 2.2 | Facet Cd | No | Per facet | "free-molecular flat plate, the usual LEO value"; no reference |

#### 1.7 Checks, explainer, Monte Carlo, seeds, summaries

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| scenario_checks.py:54, 56 | _MU, _J2 | **3.986004415e14** m^3/s^2; **1.0826e-3** | Pass prediction | No | No | Comment: "as Basilisk's simIncludeGravBody uses". These differ from lifetime.py and propellant_budget.py (398600.436e9, 1.082616e-3) |
| scenario_checks.py:58-60 | _STEP_S, _MAX_HORIZON_S, _LOOKAHEAD_S | 30 s; 7 d; 2 d | Pass prediction sampling and horizon | "in the first week" suffix shown | No | Comments |
| scenario_checks.py:136 | Kepler Newton iterations | 12 | Pass prediction | No | No | None |
| scenario_checks.py:339 | _MANY_SAMPLES | 1e6 per series | "every step is recorded" warning | Actual value shown, limit not | No | "~1.7 MB per simulated day" |
| scenario_checks.py:342 | _REENTRY_PERIGEE_KM | 120 km | "re-enters within about an orbit" warning | Limit not in message | No | Same value as lifetime |
| scenario_checks.py:566 | coarse-recording rule | shortest pass <= 3 x record interval | Warning | Rule not in message | No | None |
| scenario_checks.py:576 | _LONG_STEP_S | 60 s | Integration step warning | Yes, with evidence | No | Audit E3 measurements (L572-575) |
| scenario_checks.py:611 | late first pass | > 0.5 x run | Warning | Rule not in message | No | None |
| scenario_checks.py:669 | _NAV_BUILD_UP_STEPS | 0.41 | Navigation-error build-up time | Build-up time shown | No | Measured with simpleNav (L665-668) |
| scenario_checks.py:706 | CSS facing threshold | cos > 0.5 (60 deg) | Sun-sensor warning | Threshold not in message | No | None |
| tle.py:65 | TLE_AGE_WARNING_DAYS | 3 d | TLE age warning | Threshold not in message | No | ECSS-E-ST-10-09C 5.3.1b cited for propagation (scenario_checks.py:487-488) |
| scenario_explainer.py:81 | _SSO_TOLERANCE_DEG | 0.1 deg | "SSO" label | Label | No | Comment |
| scenario_explainer.py:297 | differential drag threshold | 5 % in Cd A/m (dry mass, flat plate) | ROE differential-drag note | Values shown | No | None |
| scenario_explainer.py:272 | passive safety threshold | <= 1 m means "not passively safe" | ROE note | Value shown | No | D'Amico & Montenbruck (via roe.py) |
| scenario_explainer.py:423 | aliasing badge | mode > 0.5/sample (Nyquist) | Warning badge | Badge | No | Implicit Nyquist |
| scenario_explainer.py:504 | camera axis tolerance | 1 deg | OpNav warning | Badge | No | None |
| schema/scenario.py:2566-2567 | MonteCarlo defaults | 10 runs, 1 thread | Batch size | GUI | JSON, GUI | None given |
| schema/scenario.py:2546-2547 | MC limits | 100000 runs, 256 threads | Validation | Error text | No | None |
| monte_carlo.py:517; BSK Controller.py:790 | seed dispersion | `setShouldDisperseSeeds(True)`; BSK seeds numpy with **run index x 10** | Per-run noise realizations | Seeds saved in run*.json | **No**: independent of `sim_settings.seed` (inferred from the code, not confirmed by a run) | BSK |
| monte_carlo.py:356-359 | inertia dispersion bounds | +/-inf unless set (BSK clips to +/-1 kg m^2 by default) | Inertia draws | No | JSON bounds | Docstring L92-95 |
| monte_carlo_results.py:58, 61 | MAX_SAMPLES, MAX_PLOTTED_RUNS | 2000 samples (strided); 100 runs plotted | Summary resolution and plots | No | No | Memory (comment) |
| monte_carlo_results.py:262, 280 | spread statistic | `np.std` (population, ddof = 0), 1-sigma | "1-sigma at the end" | Label "1-sigma" | No | None |
| schema/scenario.py:2613; seeds.py:108, 117-120 | seed | base 0; per model SHA-256("base:name")[:4]; BSK default 0x1badcad1 | Every sensor and noise model | Provenance tooltip (RNG_SEED_NOTE, results_widget.py) | JSON `sim_settings.seed`, GUI "Random seed" | Audit E5 (L93-99) |
| run_summary.py:110 | orbit period for averaging | uses **Earth mu** for every central body | "Mean SMA change" window | No | No | None |
| run_summary.py:135-171 | display decimals | 2/3/1/0 per figure | Compare tab | Yes | No | None |
| scenario_diff.py:207 | short() limit | 60 chars | Truncates diff values in display | "..." | No | None |

#### 1.8 Flight software and ADCS (`engine/fsw.py`)

| File:line | Name | Value [unit] | Controls | Visible? | Editable? (how) | Source |
|---|---|---|---|---|---|---|
| fsw.py:193 | DEFAULT_MRP_GAINS | K = 3.5, P = 30 | mrpFeedback reference gains | GUI shows 3.5 / 30 as the "default" (spacecraft_editor.py:193-194) | JSON/GUI `control_params` K, P | BSK examples/BskSim BSK_Fsw.py, tuned for 900 kg m^2 (L195-204) |
| fsw.py:205, 208-226 | inertia scaling | K, P multiplied by (trace(I)/3)/900 | **The gains actually applied** when K and P are unset | **No**: the GUI shows the unscaled 3.5/30 as the default (param_form.py:179, 186) while the run uses the scaled values (e.g. 0.039 / 0.33 for the default 10 kg m^2 inertia) | Set K, P explicitly | HISTORY.md (cited) |
| fsw.py:816-817 | Ki, integral_limit | -1 (integral off), 0 | mrpFeedback | GUI | JSON/GUI | "matching every example's default" |
| fsw.py:500, 522-524, 535 | guidance defaults | sigma_R0N = 0; sHatBdyCmd = +Z; minUnitMag 0.1; spin 0; pHat_B = +Z | Pointing modes | GUI param form | JSON/GUI `fsw_params` | BSK test_sunSafePoint.py (docstring L38-39) |
| fsw.py:345, 412, 1427 | CSS fov default | 90 deg full cone (45 deg half angle) | CSS model | GUI form | Params | None given |
| fsw.py:1357, 1381-1382, 413, 1428 | sensor noise defaults | 0 (noise-free) | Star tracker, IMU, CSS | GUI | Params | None |
| fsw.py:1058-1060 | thrFiringSchmitt | thrMinFireTime 0.002 s; level_on 0.75; level_off 0.25 | ACS thruster on-time logic | No | **No** | BSK examples/scenarioAttitudeFeedback2T_TH.py |
| fsw.py:1049, 1108 | controlAxes_B | all three body axes | Thruster mapping | No | No | Same example |
| fsw.py:1114 | angErrThresh | 3.15 (> pi) | Momentum-dump mapping mode | No | No | BSK examples/scenarioMomentumDumping.py |
| schema/scenario.py:1333-1334 | momentum dumping | thr_min_fire_time 0.02 s; max_counter_value 100 | Desaturation | GUI | JSON/GUI | None given |
| schema/scenario.py:1387 | mtb c_gain | 0.003 | Magnetic momentum management | GUI | JSON/GUI | BSK example (docstring) |
| fsw.py:270 | nav angle conversion | tan(angle/4) MRP | Navigation error | No | No | Exact relation |
| fsw.py:688 | pointing gauge capacity | 180 deg | Vizard | Vizard | No | Max principal angle |
| fsw.py:783-792 | VehicleConfig inertia | **identical to the truth inertia** | FSW model | Doc only | No | "this app has no separate FSW-vs-truth inertia model yet" |

---

### 2. Hidden assumptions (simplified equations, fixed sequences, rounding, conventions)

#### Lifetime (`lifetime.py`)
- **Mean-element orbit-averaged decay** (L19-29). Gauss's equations in vector form, averaged over 16
  points equally spaced in mean anomaly (L257-269). J2 enters as secular rates only (L272-277), plus
  short-period terms when the ring is built (L149-168). No SRP, no third bodies, no higher harmonics
  (L44-47). The integration is a fixed explicit midpoint scheme (L302-304, L317-319).
- **Drag model**: a sphere with the spacecraft's Cd and area, or the facet tumbling average
  (area = sum/4, Cd area-weighted, L354-360). The atmosphere co-rotates with zero wind (L261-262).
  The ballistic coefficient uses a **constant mass** over the whole decay (L594).
- **Re-entry is perigee <= 120 km** (L70, L308, L326). The code does not cite where this value
  comes from.
- **Deorbit**: one impulsive retrograde burn at apogee (L332-346), rocket equation with g0 9.80665.
  When propellant is short, it burns everything and reports the reached perigee (L583-587).
- Earth rotation for MSIS is a GMST polynomial with **UT1 = UTC** (L184-187). The MSIS epoch is
  rounded to whole seconds (L210).
- `drag_makeup` (used by the propellant budget) holds the mass fixed and turns the orbit only by
  J2 (L462-479). Its docstring states it comes out **about 5 % low** against full Basilisk
  station-keeping runs, without a known cause (L443-450). The budget note repeats this
  (propellant_budget.py:369-371).
- Solar activity is a single MSFC percentile for the whole look-ahead (L363-400). This is not a
  stochastic solar-cycle spread.

#### Propellant budget (`propellant_budget.py`)
- **Impulsive rocket equation per contributor, taken in a fixed order** (BOL, then operations, then
  EOL, then residual and uncertainty). Each contributor burns from the mass the previous ones left
  (L397-457).
- **All impulsive delta-Vs use the circular speed at the operational SMA** (L151-173): injection
  corrections, CAM, clearance and graveyard.
- Injection correction = **max(SMA correction, e-vector correction)**, not their sum or RSS. The
  inclination correction is decoupled from them (L155-163).
- Uncontrolled re-entry is computed **from the initial orbit (spacecraft.orbit), not the
  end-of-life orbit** (L269-270). The EOL mass is taken as dry + 3 % of the propellant
  (L433). The re-entry is solved once, in the first iteration (L432).
- Run contributors are scaled **linearly by duration** (L221). When station keeping and phasing
  share a tank, propellant is split by their delta-V share (L232-236). GEO E/W and N/S are split
  the same way (L240-244).
- The launch delay moves the launch by whole calendar years (29 Feb becomes 28 Feb) (L500-509).
  In-plane control is scaled by the ratio of drag make-ups (L589-601). Other flown contributors are
  kept unchanged.
- The altitude trade changes only the SMA and keeps the eccentricity. It re-sets the inclination
  for SSO when the original orbit was within 0.05 deg of SSO (L663-686).
- Residual and uncertainty use the 1 %/2 % equations rather than the 10 %/20 % in AD10's summary
  table (this is disclosed in a note).
- Not covered (docstring L67-70): the CAM count (entered by the user), finite-burn gravity losses,
  hybrid propulsion, and lunar-cycle effects.

#### Controllers (`orbit_maintenance.py`, `geo_station_keeping.py`, `formation_control.py`, `roe_formation.py`)
- Thrust is an **ideal inertial force** (`extForceTorque`), not body-fixed thrusters, and is
  averaged over the tick (orbit_maintenance.py:232-238). Station keeping thrusts along velocity
  (L733-736).
- Propellant is integrated with **explicit Euler, mdot = T/(Isp g0)** (propellant_bookkeeping.py:100).
  The Vizard gauge's closed-form Tsiolkovsky total is for display only (L53-67).
- Station-keeping "altitude" is **|r| - R_equator**, a spherical radius, not geodetic altitude
  (orbit_maintenance.py:607; schema L840 "above the central body's equatorial radius"). It is
  smoothed with a one-orbit boxcar, and a burn starts only once the window is full
  (L611-616, L664-670). Burns use hysteresis: start below target minus deadband, stop at target
  (L668-671).
- Eclipse gating: no thrust when illumination <= 0.99 (L303-305, L676). Constant thrust and GEO
  station keeping are **not** eclipse-gated (L1705-1723; geo docstring L60).
- Phasing: linearised deltaA = error*a/(1.5 n T) (L1426) and dv = deltaA v/(2a) (L1120). The phase
  error is the **true argument of latitude**, with a bias of about 2e accepted (L876-891). The
  error is a circular mean over one orbit (L1273). The SMA is osculating (vis-viva, L1243-1244).
- GEO: the E-W drift is fitted as a line plus a daily sine/cosine over one sidereal day
  (L166-177). The J22 parabola strategy (L179-189) uses hard-coded J22/lambda22, **not** the
  simulation's gravity coefficients. The N-S burn is node-centred along Earth's pole, with a
  small-angle sizing dv = v*(i - 0.25 i_max) (L289-292).
- Formation laws: `mean_oe` uses **K = gain x initial mass** (formation_control.py:372-373). The
  thrust request is clipped to `station_keeping.thrust_n` with its direction kept (L304). Navigation
  is the **truth state** (`simpleNav` without noise, L357-363). The docstring warns that a
  saturated PD law diverges (L71-76).
- ROE: first-order near-circular relative motion, a secular-J2 STM, and impulsive Gauss
  equations (roe.py:41-70). Differential drag is a constant-rate straight-line fit, and its effect
  on the e-vector is neglected (L72-86). Truth states, no relative-navigation filter
  (roe_formation.py:23-27). The first orbit's burns are planned as if sunlit (L55).

#### RF link, data, power
- Link budget: **free-space path loss only**. There are no atmospheric, rain, scintillation,
  polarisation or coding-gain terms (link_budget.py:19-27). Only one lumped
  `implementation_loss_db` exists, and nothing depends on elevation except range. G/T is formed
  from rx gain and Tsys.
- Pointing loss: for the "fixed" pattern, a parabolic 12(theta/theta_3dB)^2 law clamped at 30 dB
  (L184-191). Without `comms_pointing` or a boresight, **perfect pointing (0 deg) is assumed**
  (link_budget.py:284; data_handling.py:108, 122-123).
- **The link counts as closed at margin >= 0 dB**, with no required margin (data_handling.py:149;
  fsw.py:696).
- **Stale docstring contradiction**: `RFLinkConfig` says it is "no ... pointing-loss" and "does NOT
  feed back into the simulated physics anywhere" (schema/scenario.py:539-548). In fact the
  pointing loss exists (L557-566), and with `data_handling` the margin gates the simulated downlink
  (data_handling.py:36-46; schema L718-723).
- Data: instruments produce a **constant rate, always on** (data_handling.py:26; schema L692-693:
  "give the instrument's orbit-average rate"). An instrument's data for a step is refused whole when
  it does not fit (L197-203). Packets are 1 Mbit. The transmitter's power draw switches one step
  late (L59-60).
- Explainer: "memory full in X h" **ignores the downlink**, and "per pass" uses a fixed 10-min pass
  (scenario_explainer.py:447-459).
- Power: the BSK `simpleSolarPanel` gives P = 1361 W/m^2 x (AU/r)^2 x illumination x A x
  max(0, cos) x eta (BSK simpleSolarPanel.cpp:127-148). This means **no degradation (BOL = EOL), no
  temperature or packing factor, and one body-fixed panel normal**. The panel efficiency is
  constant. The battery is BSK `simpleBattery`: the capacity is clipped, and charge efficiency and
  DoD limit are not modelled (the efficiency part is unverified). The load is a constant idle sink
  plus switched sinks.
- Flexible arrays: the FSW inertia is the **undeflected** arrays plus the hub (solar_arrays.py:115-124).
  The array mass is taken out of `dry_mass_kg` (L95-112).

#### ADCS (`fsw.py`)
- **The attitude loop is closed on `simpleNav`** (truth, or truth plus the user's random-walk
  navigation error). The star tracker, IMU, magnetometer and CSS hardware models are **telemetry
  only**. They do not feed the controller (fsw.py:131-136; service.py:1197-1200). The single
  exception is the CSS WLS estimate, which feeds `sunSafePoint` when `fsw_params.use_css_estimation`
  is set (service.py:1462-1470).
- FSW inertia equals the truth inertia, so there is no model uncertainty (fsw.py:783-792).
- Default MRP gains are scaled linearly with mean inertia (L208-226). This keeps K/I and P/I at the
  BSK example's values but is not a designed bandwidth.
- `idealized` actuation has no saturation and no momentum (L827-840). RW and thruster defaults are
  whatever BSK's factories default to for omitted keys (L853-866, L948-964). For thrusters these
  are Isp 100 s and MinOnTime 0.02 s (BSK simIncludeThruster.py:80-86).

#### Checks, Monte Carlo, summaries
- Pass prediction: Kepler plus secular J2 only when degree >= 2, WGS-84 stations, IAU_EARTH
  rotation, and a fixed TT-UTC (scenario_checks.py:29-37, 149-156). It uses **mu/J2 values that
  differ** from the lifetime and budget modules (see 1.7).
- `scenario_warnings` **silently swallows an exception in any check** (scenario_checks.py:304-312;
  also plausibility_warnings L449-452). A check that crashes therefore produces no warning and no
  sign that it did not run.
- Monte Carlo: retention is **position and velocity only** (monte_carlo.py:121-133, 440-444).
  Drag and SRP coefficient dispersions act only on the **sphere (cannonball)** effectors
  (L100-103, 410-414). The spread is a population std about the batch mean in a curvilinear R/S/W
  frame (monte_carlo_results.py:31-39, 217-231). Altitude is above the equatorial radius
  (L253-256).
- Run summary: the **"Delta-V" figure omits the ROE formation controller**. `_DELTA_V_CONTROLLERS`
  (run_summary.py:67) lists station_keeping, geo_station_keeping, phasing_keeping and
  constant_thrust, but the ROE controller writes `{sc}.roe_formation.delta_v`
  (roe_formation.py:820). Propellant is still counted, because it comes from the shared tank.
  The orbit period for "mean SMA change" always uses Earth's mu (L110).

---

### 3. Outputs shown without derivation

| Output | Where | What is shown | What is missing |
|---|---|---|---|
| Lifetime, re-entry date, rule verdicts | CLI `lifetime` (cli.py:463-476); GUI End-of-Life tab (lifetime_widget.py:343-374, tiles, badges, perigee/apogee chart) | Re-entry date, years, mass, deorbit dV/kg, "met/not met/not known" | Cd actually used (default 2.2 replaces the spacecraft's own), area (facet sum/4 or sphere), ballistic coefficient, density model, percentile actually applied (GUI combo only), the 120 km re-entry altitude, 5/25-year thresholds stated only as labels, step method; no CSV export of the decay curve (unverified) |
| Deorbit burn | Same | dV, kg, reached perigee | Isp used, mass before the burn, the burn being at apogee (tooltip only) |
| Propellant budget | CLI `budget` (cli.py:581-590); GUI Budget tab (budget_widget.py:529-544); CSV copy | Per-row phase, contributor, dV, kg, margin, source; totals; dry mass incl. margin, Isp, efficiency, iterations; notes | Mass before each burn, Ve, the circular speed and SMA used, disposal Cd/percentile (2.2 / 50th), the bisection tolerance, the formula of each contributor. **Derivation is partly shown (best in this area)** |
| Launch-delay sweep / altitude trade | CLI tables (cli.py:479-494, 599-608); GUI tables (budget_widget.py:490-524) | Per case: launch date, in-plane dV, disposal dV, total dV, kg, fits tank | Drag ratio per case is computed (`DelayCase.drag_ratio`) but **not displayed**; source label "x1.23 (drag)" appears only in the row's source column after picking a case |
| Link margin series / lowest link margin | Results plots; Compare tab "Lowest link margin" (run_summary.py:151-154) | dB | Which station, which time, and the breakdown (except on the live mission dashboard) |
| Mission dashboard link breakdown | gui/mission_dashboard_widget.py:216-236, 448-455 | EIRP, FSPL, pointing loss, received power, N0, C/N0, Eb/N0, margin | Inputs (Ptx, G, L_impl, R, Tsys, required Eb/N0) are not shown next to them; the 0 dB closure rule is not stated |
| Data budget lines | CLI run (cli.py:156-157; data_budget.py:57-61) | Generated, downlinked, lost, on board [Gbit] | Rates, access time, link-closed time; `capacity_full` is really "data_lost > 0" (data_budget.py:53) |
| Explainer data-handling notes | scenario_explainer.py:447-459 | Gbit/day, memory-full hours, Gbit per 10-min pass | Formula and assumptions (no downlink in the fill time; fixed pass length) |
| Run summary figures | Compare tab (run_summary.py:118-172) | Delta-V, propellant used, mean SMA change, link margin, battery, passes, eclipses, data | The module docstring has a source table (L22-42), but it is a code docstring, not shown in the GUI (unverified where shown) |
| Monte Carlo summary | CLI (monte_carlo_results.py:310-318), GUI tab | 1-sigma final along-track, radial and cross-track offsets; failed runs; per-run table with drawn values and final offsets (run_table L286-301) | Statistic definition (population std, about the mean, curvilinear frame), sample count used (max 2000 strided), percentiles, convergence |
| Pass summary | Explain tab (scenario_checks.py:256-281) | Passes, first pass time, duration, peak elevation | Model (Kepler + J2 secular), 30 s sampling (timing resolution about +/-30 s) |
| SSO / RAAN-for-LTAN | Wizard | Inclination and RAAN rounded to 0.01 deg | J2-only first-order formula and true-Sun RA |
| Walker / phasing follower generation | CLI `constellation`, `phasing`; GUI dialogs | Generated orbits | The mean-to-osculating mapping is applied only when degree >= 2; this is silent (constellation.py:213-214; formation.py:290-305) |
| Controller gains (MRP) | Not shown | n/a | Actually applied K/P after inertia scaling |

Where derivation **is** shown: the propellant budget rows, margins, sources and notes; the
dashboard link breakdown; the gravity-fidelity note (shows omitted vs SRP acceleration and the
degree that matches, citing ECSS-E-ST-10-04C 4.2.1b, scenario_checks.py:546-548); the ROE notes
(components and closest approach, scenario_explainer.py:262-282); the device-catalog notes, which
give the conversion arithmetic; and the Monte Carlo per-run drawn values.

---

### 4. Forced single options

| Area | Single method/policy used | Reasonable alternatives not offered | Shown in results? |
|---|---|---|---|
| Lifetime model | Orbit-averaged mean-element drag + J2 (lifetime.py) | Full numerical propagation (the app could reuse its own Basilisk run); semi-analytic King-Hele; STELA-like long-term; DRAMA/OSCAR-style; Monte Carlo over solar activity | Not stated in outputs; GUI hint says "Orbit-averaged drag" (lifetime_widget.py:262) |
| Re-entry criterion | Perigee <= 120 km | User-set altitude (e.g. 100, 80 km); energy/altitude criteria | No |
| Disposal rules | Fixed 5 yr and 25 yr badges | User-selectable rule set (e.g. a mission-specific limit; ISO 24113:2023 update); tolerance/probability of compliance | Labels only |
| Solar activity | MSFC 95/50/5 percentiles (bundled tables) | Other forecast sources; solar-cycle scenarios; dispersion | Percentile combo in GUI/CLI |
| Atmosphere | NRLMSISE-00 or exponential | Tabular atmosphere (BSK ships `TabularAtmosphere`, not wired; schema docstring), JB2008, DTM | Model in scenario settings |
| Lifetime Cd | Default 2.2 replacing the spacecraft's Cd | Spacecraft's own (option exists), attitude-dependent, Cd from free-molecular model | **Not displayed in result** |
| Margin policy | ESA AD10 only (x4 CAM, +100 % ACS, +15 % last burn, 1 %/2 % residuals, 15 % system margin) | ECSS-E-ST-35, NASA/GSFC GOLD rules, SMAD margin tables, the AD10 summary-table 10 %/20 % variant, user-defined margins | Margin column shows the applied factor |
| Burn model in budget | Impulsive rocket equation in a fixed contributor order | Finite-burn/gravity-loss factor; low-thrust (Edelbaum) transfer delta-V; per-contributor Isp (e.g. separate ACS thruster) | No |
| Injection-correction combination | max(SMA, e) + separate inclination | Sum, RSS, combined optimal | No |
| Disposal orbit start | Initial orbit, not the EOL orbit | Run-end state (the lifetime tab already supports "End of last run") | No |
| Link loss model | FSPL + one lumped loss; 0 dB closure | ITU-R P.618/P.676 atmosphere and rain, polarisation, radome/cable, coding gain by MODCOD, elevation-dependent Tsys, user-required margin (e.g. 3 dB) | Breakdown on dashboard only |
| Pointing loss | 12(theta/theta3dB)^2 or cos^n or table | Gaussian/Bessel patterns, BSK `simpleAntenna`/`linkBudget` (deliberately not used, link_budget.py:38-47) | No |
| Power model | BSK simpleSolarPanel (constant eta, no degradation) | BOL/EOL degradation per year, radiation fluence, temperature coefficient, packing/cos-loss factor, multiple panels, DoD limit | No |
| Data model | Constant-rate always-on instruments, 1 Mbit packets | Duty-cycled instruments, scheduled downlink, compression ratio | No |
| SK altitude | Spherical |r| - R_eq | Geodetic altitude; mean SMA control | Doc only |
| GEO SK strategy | J22 parabola E-W; node-centred N-S | Combined E/W-eccentricity control, luni-solar N-S optimisation | No |
| ADCS sensing | Truth / simpleNav random walk; hardware sensors telemetry-only | Closing the loop on sensor models (star tracker + gyro filter) | Not stated in outputs |
| MRP gains | Linear inertia scaling of BSK example gains | Bandwidth/damping-based design (natural frequency, damping ratio) | No (GUI shows unscaled default) |
| MC statistics | Population 1-sigma, final epoch | Percentiles (e.g. 99.7 %), confidence intervals, convergence vs N, per-epoch envelopes | Label "1-sigma" |
| MC retention | r, v only | Attitude, propellant, link margin, battery, lifetime per run | No |
| MC drag/SRP dispersion | Sphere effectors only | Facet coefficients | No |
| Walker | delta/star only | Flower, Street-of-coverage, arbitrary RAAN spacing | Pattern shown |
| Thrust frames (constant thrust) | VNB/RTN | Inertial, Sun-relative | Frame shown |

---

### 5. Data exchanges

**Inputs read**
- The scenario JSON (all PropellantBudgetConfig, PowerConfig, RFLinkConfig, etc. fields).
- Space-weather files: bundled `data/spaceweather/SW-All.txt` and the MSFC prediction table
  `data/spaceweather/oct2026f10-prd.txt`. A user `local_file_path`, a `msfc_file_path` and a
  `cache_dir` are optional. These feed lifetime.py:363-400 and scenario_checks.py:382-393, and the
  coverage result is cached by file modification time.
- BSK support data: albedo maps (service.py:1205-1206), the WMM magnetic field, and SPICE kernels
  via `engine.kernels`. IERS Earth-orientation files via `engine.earth_orientation`
  (scenario_checks.py:403-437).
- The last run's `ResultSet` (in memory). Named series feed the propellant budget
  (`*.station_keeping.delta_v`, `*.propellant_remaining`, `*.geo_station_keeping.*`,
  `*.phasing_keeping.delta_v`, `*.roe_formation.delta_v`, propellant_budget.py:204-245), the
  lifetime "from end of last run" (`position_N`, `velocity_N`, `fuel_mass_remaining`,
  lifetime.py:525-568), run_summary and data_budget.
- In-code catalogs. `device_catalog.CATALOG` was transcribed from datasheets and from "a real
  user's supplier database ... dated 07 Oct 2026" (device_catalog.py:76-87). The database itself
  is not in the repository, so its provenance cannot be checked here.
  `spacecraft_templates.SPACECRAFT_TEMPLATES` and the Basilisk defaults behind the RW and thruster
  factories are also implicit inputs.
- Validation evidence the code cites but this audit did not inspect: `compliance/drag_remeasure.md`
  (lifetime.py:447), `tests/test_lifetime.py`, and `HISTORY.md` (MRP gain scaling, phasing fixes).

**Outputs written**
- Monte Carlo `archive_dir`: `MonteCarlo.data`, `run<i>.data` (gzip pickle), `run<i>.json`
  (drawn parameters and seeds), `*.scState.*.data`, `archive.provenance.json`, plus the pickle-free
  summary `batch_results.npz` / `batch_results.json` (monte_carlo.py:447-546;
  monte_carlo_results.py:99-131). The tool reads back pickles only from its own batch (S-04).
- CLI `run` writes CSV series, `events.csv`, optional CCSDS OEM, `command_summary.csv`, and the
  data-budget lines on stdout (cli.py:134-186).
- The budget table is copied to the clipboard as CSV with provenance lines
  (budget_widget.py:546-561). The lifetime results have no file export (unverified; none found in
  lifetime_widget.py).
- Seeds: `assign_rng_seeds` returns `{model: seed}` for provenance (seeds.py:123-140;
  service.py:1950).
- Altitude trade: spawns a multiprocessing pool, passing pickled scenario jobs between processes
  (propellant_budget.py:766-790).
- Consumers: Vizard live gauges read the controllers' `fuelTankOutMsg`, `deltaVOutMsg` and
  separation messages, which are documented as display-only (orbit_maintenance.py:45-61).

---

### 6. Transparency features already present (to credit)

1. **Propellant budget**: each AD10 constant names its section, and every row carries `margin` and
   `source` ("input", "computed", "last run", "last run, scaled", "estimated", "x1.23 (drag)").
   Notes flag off-guideline settings (wrong percentile or Cd in the run, a scaled run, a value
   counted as 0, no CAMs entered, the tank exceeded). The code also discloses that it departs from
   AD10's own summary table (1 %/2 % vs 10 %/20 %) and that the drag estimate is about 5 % low
   (propellant_budget.py:338-391, 459-461, 578-619). GUI tooltips cite AD10 sections
   (budget_widget.py:109-167), and the CSV export carries provenance.
2. **Link budget breakdown** dataclass (link_budget.py:123-173), shown stage by stage on the
   mission dashboard (mission_dashboard_widget.py:216-236). The pattern models cite Balanis.
3. **Device catalog honesty discipline** (device_catalog.py:38-93): each entry has a URL, an ITAR
   statement at an appropriate confidence level, conversions with the arithmetic shown, approximate
   values explicitly labelled as such, and a source level (primary or secondary).
4. **Lifetime**: a three-state verdict ("not known" when the horizon is too short,
   lifetime.py:133-136); warnings when data ends early or the exponential model overstates
   lifetime (L372-374, L391-394); known limits stated (L44-48); cancellation never returns a
   partial result (L309-311).
5. **Pre-run checks** (scenario_checks.py): 31 kinds of warning shown in the Explain tab's
   "Check before running" section. Some include evidence, for example the step-size warning, which
   quotes measured errors, and the gravity-fidelity note, which cites ECSS.
6. **ROE module** cites its literature precisely (roe.py:25-92). The explainer computes passive
   safety (scenario_explainer.py:262-282).
7. **Monte Carlo**: per-run drawn values with readable unit labels (monte_carlo.py:549-611), a
   per-run table of inputs and outcomes (monte_carlo_results.py:286-301), and failed runs listed.
   A pre-existing archive is never shown as the current batch (monte_carlo.py:486-501).
8. **Seeds**: deterministic, documented derivation and a provenance note (seeds.py:91-140).
9. **Run summary**: a docstring table of where each figure comes from, with the rule "never
   estimated" (run_summary.py:18-52). **Scenario diff** lists input differences between runs.
10. Schema validation messages give the field path and range, and in 5 cases a "units mixup" hint
    (schema/scenario.py:522-532, 593-595, 792-793).
11. Formation generator limitations are stated in the docstring and the GUI dialog
    (formation.py:78-93). Formation laws document their saturation and divergence risk
    (formation_control.py:71-76). There is a pre-run warning for it
    (scenario_checks.py:624-662).
12. Templates and catalogs are presets, not locks. Templates are labelled "for illustration"
    (spacecraft_templates.py:39-48).

---

### 7. Validation rules and warnings

#### 7.1 `engine/scenario_checks.py`: 31 kinds of message

| # | Line | Message (short) | States the rule? | Why it matters? | Actual vs limit? | How to resolve? |
|---|---|---|---|---|---|---|
| 1 | 324 | Small-body ephemeris not installed | Implicit | No ("stops at once" only in docstring) | n/a | Yes (download in Reference data) |
| 2 | 332 | Small-body shape model not installed | Implicit | No | n/a | Yes |
| 3 | 360 | Position inside Earth (N km from centre) | Implicit | No | Actual only | No |
| 4 | 365 | Escape trajectory | Yes | n/a | No | Hint (check units) |
| 5 | 373 | Perigee N km below surface | Yes | No | Actual only | No |
| 6 | 375 | Perigee at N km, re-enters within an orbit | **No** (120 km not stated) | Yes | Actual only | No |
| 7 | 416 | Space weather: <exception text> | Pass-through | - | - | - |
| 8 | 419 | SW data start after epoch, run refused | Yes | Yes (refused) | Date | No |
| 9 | 421 | SW data end before run ends, run refused | Yes | Yes | Date | No |
| 10 | 427 | No IERS files, IAU_EARTH used | Yes | Yes (~160 m/day) | n/a | Yes (Settings > Reference data) |
| 11 | 430 | IERS files don't cover the run | Yes | Yes | Coverage | Implicit |
| 12 | 435 | High accuracy until date | Yes | Yes (predicted values) | Date | No |
| 13 | 476 | 3D model errors/warnings | Pass-through | - | - | - |
| 14 | 479 | 3D-derived fields stale | Yes | Implicit | Field list | Yes (3 ways) |
| 15 | 496 | TLE error | Pass-through | - | - | - |
| 16 | 500 | TLE epoch N d from scenario epoch | **No** (3 d limit not stated) | Yes (SGP4 accuracy) | Actual only | No |
| 17 | 511 | Drag with point-mass gravity | Yes | Yes (J2 far larger) | n/a | Yes (degree >= 2) |
| 18 | 546 | Gravity degree leaves out more than SRP (ECSS-E-ST-10-04C 4.2.1b) | Yes, standard cited | Yes | **Yes** (both values) | **Yes** (degree N) |
| 19 | 558 | Every step recorded: N million samples | No (1e6 limit) | Yes (memory) | Actual only | Yes (600 s) |
| 20 | 568 | Passes as short as X but recorded every Y | No (3x rule) | Yes | Both values | Implicit |
| 21 | 585 | Dynamics step > 60 s | **Yes** | **Yes**, with measured errors | **Yes** | **Yes** |
| 22 | 596 | MC asks for N processes, CPU has M | Yes | Yes | Yes | Implicit |
| 23 | 612 | First pass only at X of a Y run | No (half-run rule) | No | Both | No |
| 24 | 616 | No pass in this run; first at X | Yes | Implicit | Actual | Yes (epoch/longer run) |
| 25 | 619 | No pass in run or 2 days after | Yes | Implicit | n/a | Yes (check orbit/min elevation) |
| 26 | 647 | hill_pd needs X m/s^2 to hold, thruster gives Y | Yes | Implicit | **Yes** | **Yes** (mean_oe or drift_orbit) |
| 27 | 659 | hill_pd starts X km off, asks Y > Z | Yes | Yes (can diverge) | **Yes** | No |
| 28 | 691 | Navigation errors restart at each of N segments, build-up T | Yes | Partial | Actual | No |
| 29 | 709 | No sun sensor faces the Sun-pointing axis | No (60 deg threshold) | Yes | No | No |
| 30 | 712 | Facets unused (drag and SRP off) | Yes | Yes | n/a | Implicit |
| 31 | 715 | SK deadband may never trip with drag off | Yes | Yes | Deadband shown | Implicit |

Totals for the 28 non-pass-through messages:
- States the numeric threshold or limit it applies: 5 (#18, 21, 22, 26, 27).
- Omits a numeric threshold the code applies: 6 (#6 120 km, #16 3 d, #19 1e6 samples, #20 3x
  interval, #23 half the run, #29 60 deg).
- Gives the reason: about 19.
- Shows the actual value: 17. Shows actual against limit: 5.
- Gives a fix: 12 explicit, about 5 implicit.
- Fully complete (rule, why, actual vs limit, fix): **3** (#18, #21, #26).
- **Any check that raises is silently skipped** (L304-312, 449-452).

#### 7.2 Other warnings and notes in my modules
- **Explainer warning badges (9)** (scenario_explainer.py:424, 453, 455, 491, 493, 497, 505, 519,
  545), plus the phasing-without-station-keeping note (L335). Most state the problem and some give
  the fix (for example "use locationPointing on it"). None state a threshold value (Nyquist, the
  1 deg camera tolerance).
- **Propellant-budget notes (about 18)**. These are good: they name the AD10 section and the
  required versus actual value (for example L345-349: "used MSFC's 50th percentile; AD10 Sec. 5.9
  asks for the 95th"), and say what to do ("run the whole mission for an AD10 budget").
  `BudgetError` messages (10) are specific and actionable (for example L328: "set
  propellant_budget.isp_s, or give it an orbit thruster").
- **Lifetime**: 2 warnings (L373-374, L392-393) and 10 `LifetimeError`s (for example L384, L390
  give the data dates; L546 gives the allowed range). The tank-shortfall note in the GUI gives
  actual against target (lifetime_widget.py:371-372).
- **Controllers**: propellant-depleted warnings (orbit_maintenance.py:686;
  geo_station_keeping.py:249) give the time but not the delta-V still required.
- **Monte Carlo**: 8 `MonteCarloError`s. They are specific and include resolutions (folder,
  `--overwrite`, `--allow-scripts`, max days).
- **Generators**: constellation.py has 12 `_require`s and formation.py has 20. Each gives the field
  and its range. One also explains the consequence (formation.py:171-173, audit M5).
- **Schema validation for the configs in scope: 124 `_require` messages** across 18 classes
  (PowerConfig 6, RFLinkConfig 11, CommsPointing 4, Instrument 4, DataHandling 5, SolarArray 10,
  StationKeeping 8, GeoSK 6, ConstantThrust 5, PhasingKeeping 12, RoeFormation 13,
  MomentumDumping 3, MagneticMM 2, NavigationError 4, FuelTank 3, PropellantBudget 10,
  Dispersion 15, MonteCarlo 3). They consistently give the field path and the allowed range.
  Five add a "units mixup" hint. A few give the physical reason, for example the cos^n directivity
  (L605-609) and the navigation error growing without bound (L1448-1450). None cite a source for
  the range limits, such as `mission_years` <= 30 or `disposal_lifetime_years` <= 25.

---

### 8. Selectable-model candidates

1. **Lifetime engine**: the current orbit-averaged model, or "propagate with the full Basilisk
   simulation" (long_run). Also: re-entry altitude as an input (default 120 km); Cd/area source
   shown and chosen explicitly; mass decreasing during decay; solar-activity Monte Carlo
   (5/50/95 envelope in one run).
2. **Debris-mitigation rule set**: selectable thresholds with their source (ESA Zero Debris 5 yr,
   FCC 5 yr, IADC/ISO 24113 25 yr, a custom value), and a probability of compliance.
3. **Margin policy profiles**: ESA AD10 (current), the AD10 summary-table variant (10 %/20 %
   residuals), ECSS-E-ST-35 propulsion margins, NASA GSFC-STD-1000 or SMAD tables, or user-defined.
   Each applied factor would be shown per row, which the current table already supports.
4. **Burn modelling in the budget**: impulsive (current), or a finite-burn gravity-loss factor,
   or low-thrust Edelbaum for transfers. Allow a separate Isp per contributor (ACS versus orbit
   thruster).
5. **Disposal start state**: initial orbit (current), end-of-run state, or a user-specified EOL
   orbit.
6. **Link model**: FSPL only (current), or FSPL plus ITU-R P.676 gaseous, P.618 rain and
   scintillation, and polarisation, cable and radome losses. A required link margin (for example
   3 dB) as the closure threshold, a MODCOD table for required Eb/N0, and an option for BSK's own
   `linkBudget`/`simpleAntenna`.
7. **Power model**: an annual degradation rate, an EOL/BOL factor, a temperature coefficient,
   packing and assembly factors, multiple panels or arrays, a battery DoD limit and charge
   efficiency.
8. **Data model**: duty-cycled instruments and a contact or downlink schedule, with predicted pass
   durations used in the explainer instead of a fixed 10 minutes.
9. **ADCS sensing**: truth (current), the simpleNav error model (current), or closing the loop on
   the configured sensors (star tracker + IMU filter). FSW inertia uncertainty (a truth/FSW
   mismatch). MRP gain design by bandwidth and damping ratio, with the applied gains displayed.
10. **Station-keeping reference**: spherical radius (current), geodetic altitude, or mean SMA.
11. **GEO station keeping**: J22 coefficients taken from the simulation's gravity field; a
    combined eccentricity-control strategy.
12. **Monte Carlo statistics**: percentiles, 3-sigma, convergence with N, and a seed tied to
    `sim_settings.seed`. Retention of user-selected series (attitude, propellant, margin, battery).
    Facet-coefficient dispersion.
13. **Pass prediction**: show the model used (Kepler + J2, 30 s sampling) or run with the full
    propagator; use one set of Earth constants throughout (scenario_checks.py uses a different
    mu/J2).
14. **Atmosphere**: add BSK `TabularAtmosphere` (user density table), which the schema docstring
    already identifies as available but not wired.

---

#### Notable defects and inconsistencies found (for follow-up)
- Lifetime CLI/GUI default Cd 2.2 overrides the spacecraft's Cd, and the result does not show
  which Cd was used (cli.py:1247; lifetime_widget.py:224).
- The GUI shows MRP default gains K = 3.5, P = 30, but the engine applies inertia-scaled gains
  (fsw.py:208-226 vs spacecraft_editor.py:193-194, param_form.py:179-186).
- Run-summary "Delta-V" omits ROE-formation delta-V (run_summary.py:67 vs roe_formation.py:820).
- The ground-station rx gain default differs: 0 dBi in the schema (scenario.py:2375) and 45 dBi
  for a new station in the GUI (ground_station_editor.py:106).
- The RFLinkConfig docstring is stale: it says there is no pointing loss and no physics feedback
  (scenario.py:539-548).
- Earth constants are inconsistent across modules (scenario_checks.py:54-56 vs lifetime.py:65-67).
- Uncontrolled-re-entry disposal is solved from the initial orbit, not the EOL orbit
  (propellant_budget.py:269-270).
- Catalog thrusters without a published Isp fall back to BSK's 100 s silently
  (simIncludeThruster.py:81).
- Scenario checks silently drop any check that raises (scenario_checks.py:304-312).

---

## Appendix C: Scenario schema, CLI, interfaces and reproducibility

*Detailed findings of review C, as written by the reviewer and checked as described in Section 1.*

Scope: `spacemissionstudio/schema/*.py`, `spacemissionstudio/cli.py`, and every input/output the tool exchanges with files, network, environment and other programs. Read-only audit of `SpaceMissionStudio/` at develop 20d80d67a (version `1.3.1`, `spacemissionstudio/__init__.py:11`, `pyproject.toml:3`). Nothing was executed except read-only `grep`/AST scripts over the sources; no simulation and no GUI were run. All paths below are relative to `SpaceMissionStudio/` unless they start with `/`.

Method notes (so the tables can be re-derived):

* Field and rule tables in (a) were produced by AST extraction of every `@dataclass` field and every `_require(...)` / `_collect(...)` call in `spacemissionstudio/schema/*.py` (by a script not kept in the repository), then cross-referenced against `compliance/docs/ICD_scenario_fields.md` (ICD), user docs (`USER_MANUAL.md`, `GETTING_STARTED.md`, `README.md`, `docs/**/*.md` excluding audit/UX-planning files), and `spacemissionstudio/gui/**/*.py`.
* "In GUI?" is a name-occurrence heuristic (the field name appears in that GUI module) plus spot checks; every scenario field is additionally editable as raw text through the Scenario editor's JSON mode (`gui/json_view.py:20-31`), and every GUI edit goes through the same `Scenario.validate()` (`gui/scenario_editor.py:96-100`, `gui/main_window.py:1688`). Treat a "yes" as "the GUI references it", not "a dedicated widget is proven to edit it"; the heuristic is marked where it was spot-checked.
* "UM mentions" = number of times the field name occurs in user docs (heuristic; a 0 means the snake_case field name never appears in user-facing docs, though the concept may be described in prose).

### Headline counts

| Item | Count | Source |
|---|---|---|
| Scenario/Command dataclass fields | 320 (317 in scenario JSON + 3 in `references.Reference`, an in-memory helper, not serialised) | AST over `schema/*.py` |
| Fields present in the generated ICD | 317 / 317 serialised fields; defaults match the source for all of them (57 differ only in formatting, e.g. `field(default_factory=list)` vs `[]`) | `compliance/docs/ICD_scenario_fields.md` |
| ICD rows with an empty "Unit / note" column | 109 of 317 (29 of them `float`/`int`), because the generator takes the unit only from the field's own source line, so a unit written on the preceding comment line is lost (e.g. `RoeFormationConfig.continuous_gain`, `scenario.py:1140-1142`, ICD line 437) | ICD |
| Numeric scalar defaults with no `[unit]` comment | 24 of 115 in `scenario.py`; 13 of them have no unit in the name either (e.g. `SpacecraftConfig.drag_coeff = 2.2`, `scenario.py:1814`; `SpaceWeatherConfig.forecast_percentile = 50.0`, `:2453`) | AST |
| Fields whose snake_case name never appears in user docs | 211 of 320 | grep |
| Validation rules (`_require` in `scenario.py`) | 340; plus 21 `_collect` rules in `command.py` and ~25 `errors.append` rules in `scenario.py:189-248` (device-factory params) | AST |
| Rules with a non-trivial numeric limit | 50; the limit is stated in user docs for only a handful (the file/size limits in `docs/user-manual/command-line.md:49-56`, the 100-day single-run limit in `docs/reference/limitations.md`, the ROE chief eccentricity); the plausibility ceilings (e.g. `panel_area_m2 <= 2000`, `tx_power_w <= 1e4`, `data_rate_bps <= 1e11`, `dry_mass_kg <= 1e6`) appear only in the error message (one appears as an example in `docs/troubleshooting.md:159`) | grep, see table A.3 |
| CLI subcommands | 22 (`cli.py:1188-1448`), all listed in the generated `compliance/docs/ICD_cli.md` | `cli.py` |
| External exchanges inventoried in (c) | 38 | below |
| Environment variables read or written | 4 written (`QTWEBENGINE_CHROMIUM_FLAGS`, `QT_SCALE_FACTOR`, the proxy variables during one Basilisk import, `SMS_SIL_TOKEN` for the SIL child); none read to change results | grep `os.environ` |

### Ten most important findings

1. **A CLI run folder cannot be reproduced from itself**: `run --out-dir` writes CSVs, `events.csv` and `provenance.json`, but not the scenario; provenance holds only a SHA-256 of a canonical re-serialisation after migration (`output_provenance.py:80-84`), which never equals `sha256sum` of the file and no CLI command prints it.
2. **Runs over 100 days record the wrong scenario hash and partial seeds**: the merged result keeps segment 0's provenance (`engine/long_run.py:203-204`), computed over a modified copy (`:247-258`, `service.py:737`).
3. **Hidden control gains**: with `control_params` unset the engine uses `K = 3.5 * mean(I)/900`, `P = 30 * mean(I)/900` (`engine/fsw.py:193-226`, `:811-817`), while the GUI shows 3.5 / 30 greyed out (`gui/spacecraft_editor.py:193-198`, `gui/param_form.py:176-190`); the values used are recorded nowhere.
4. **Open `params` dicts** (sensors, actuators, `fsw_params`, `control_params`, commands) fall back to 36+ engine defaults and Basilisk module defaults that are not in the file or the provenance (`engine/fsw.py` `params.get(...)`).
5. **Silent migrations change physics settings** (`schema/migrations.py:47-99`), and `validate` then prints the post-migration version (`cli.py:88-89`).
6. **"bundled" space weather is not pinned**: it uses the newer of the shipped and any downloaded file (`engine/spaceweather.py:631-652`); the MSFC prediction file used is not in `provenance.data_files` (`service.py:1102`).
7. **Reference-data integrity after install is size-only** for Earth-orientation and Eros kernels (`earth_orientation.py:159`, `small_bodies.py:165`, contradicting `small_bodies.py:36-37`), and files > 32 MB (de430.bsp) are recorded by size only (`dependencies.py:44`).
8. **Validation limits are undocumented**: 50 numeric-limit rules; the plausibility ceilings appear only in error messages; the generated ICD has 109 of 317 rows without a unit.
9. **CLI analysis outputs (`lifetime`, `budget`, run summaries) carry no provenance**, and `lifetime` silently replaces the spacecraft's `drag_coeff` (2.2) and the scenario's forecast percentile (50) without printing either (`cli.py:455-458`); exit codes 2 and 4 are reused for non-ICD meanings (`cli.py:366`, `:879`, `:917`).
10. **No change history or authorship** in the scenario (`scenario.py:2681-2722`); undo is in-memory only (`gui/undo_history.py`); no plugin mechanism; the Python API is usable and exercised by tested examples but has no reference documentation or stable surface (`engine/__init__.py` is empty).

Strengths worth stating: the schema writes every dataclass default explicitly, refuses unknown fields and wrong types by name, saves atomically; `provenance.json` is rich (versions, qualified flag, integrator tolerances, all derived RNG seeds, data-file hashes, frames, time scales); Basilisk support data is checksum-verified at every run; flight-software exports have full hash manifests with stale/modified detection (`fsw_export/records.py:81-109`); plot exports embed provenance.

### (a) Scenario schema

#### Findings (a)

1. **The schema is explicit and self-describing at the dataclass level.** `Scenario.to_dict()` is `dataclasses.asdict` (`schema/scenario.py:3060-3063`), so every dataclass field, including those left at their default, is written to the saved JSON (`scenario_text`, `:3289-3291`). A saved scenario file therefore pins every *schema* default. Unknown fields are refused by name (`_record`, `:3167-3180`), wrong JSON types are refused by name (`_check_types`, `:3258-3277`), the file read is bounded to 20 MB (`:3338-3342`), and saves are atomic via temp file + `os.replace` (`:3120-3143`).
2. **But four "open dict" fields carry no schema defaults at all**, and whatever a key is left out of them silently takes an engine or Basilisk default that is *not* written to the file: `SensorConfig.params` / `ActuatorConfig.params` (`:469`, `:484`), `SpacecraftConfig.fsw_params` and `control_params` (`:1851`, `:1854`), and `Command.params` (`command.py:151`). `engine/fsw.py` alone has 36 `params.get(key, default)` fall-backs (e.g. CSS `fov_deg` 90, `noise_std` 0, `sHatBdyCmd` [0,0,1], `min_unit_mag` 0.1: `engine/fsw.py:345,412-413,522-535`); unset device parameters fall to the Basilisk module's own constructor default (`engine/device_catalog.py:58-60` says so explicitly). See (d) and (h) for the MRP gains, the most consequential one.
3. **Units are mostly carried by field-name suffix, not by type.** 24 numeric defaults have no `[unit]` comment; 13 have no unit in the name either (A.1). The generated ICD loses units written on the line above a field (109 rows with an empty Unit/note column).
4. **Validation limits are not documented as such.** `ICD_scenario_fields.md` says "the full validation rules are each class's `validate()`" (its line 3). The user is told a limit only when it is violated, through the error message. 50 rules carry a numeric limit (A.2); only those listed with a doc reference in A.2 are stated in user docs.
5. **Two layers validate differently.** `Scenario.validate()` raises on the first problem (`_require`, `:313-315`); `schema.validation.validate_all()` collects every *mission-sequence* problem but still at most one *resource* problem (`schema/validation.py:24-48`). This asymmetry is stated in the docstring.
6. **Schema checks are weaker than the run-time checks in places.** `assignment.target` only needs a `.` (`command.py:270-275`), but the engine requires exactly three segments and a whitelist of `station_keeping|phasing_keeping|constant_thrust` x `thrust_n|isp_s` (`engine/mission_engine.py:140-153`, `:740-773`), so a scenario can validate and then fail mid-run. The inertia triangle-inequality check covers diagonal tensors only (`scenario.py:1923-1933`, stated in the comment).
7. **Migrations are silent and change values.** `migrations.migrate()` rewrites old files in memory: v1 `space_weather.source "celestrak"` -> `"synthetic"` (and `activity_level "conservative"` -> `"nominal"`), v2 `"synthetic"` -> `"bundled"`, v3 `activity_level "conservative"` -> `forecast_percentile = 95.0` and `activity_percentile` dropped (`schema/migrations.py:47-99`). Nothing tells the user: no warning is emitted by `parse_scenario_text` (`scenario.py:3294-3327`), no GUI module mentions migration (grep `migrat` in `gui/` finds only `autosave.py:160-162` and a docstring), and `spacemissionstudio validate` prints the *post*-migration `schema_version 4` (`cli.py:88-89`), hiding that the file was older. The file on disk is not rewritten until the next save.
8. **Epoch handling is documented and safe.** An epoch without zone is taken as UTC; `Z` and offsets are converted (`schema/epochs.py:33-45`).
9. **TLE input is format-checked at load** (69 columns, line numbers, checksums, catalogue match, epoch field; `schema/tle_format.py:38-53`), but not checked for age; age/plausibility are warnings from `engine.scenario_checks` (called by `cli.py:97-102`).
10. **Seeds live in three unrelated places**: `SimSettings.seed` (default 0, `scenario.py:2613`, range `[0, 2^31)`, `:2649`), `NavigationErrorConfig.seed` (default `None` = "Basilisk's default", `:1434`, range `[0, 2^32)`, `:1453`), `OpticalNavigationConfig.seed` and `LandmarkNavigationConfig.seed` (default 1, `:1216`, `:1274`, not derived from `SimSettings.seed`, used directly as `np.random.default_rng(config.seed)`, `engine/optical_navigation.py:88`, `engine/landmarks.py:65`). Changing `sim_settings.seed` does not change the camera-noise realisation.
11. **Scenario carries no authorship or change metadata.** `Scenario` has `name`, `description` and `schema_version` only (`scenario.py:2681-2722`); see (g).

#### A.0 Schema module constants and limits (`MAX_*`, `MIN_*`, enumerations)

| File:line | Constant | Value [unit] | Purpose | Documented to user? | GUI |
|---|---|---|---|---|---|
| scenario.py:76 | `CURRENT_SCHEMA_VERSION` | 4 | file version | ICD.md 5.3.1 | written automatically |
| scenario.py:81 | `MAX_SPACECRAFT` | 1000 | DoS limit | command-line.md:49-53 | n/a |
| scenario.py:82 | `MAX_DESCRIPTION_CHARS` | 100 000 [char] | DoS limit | command-line.md:49-53 | n/a |
| scenario.py:83 | `MAX_SCENARIO_FILE_BYTES` | 20 000 000 [byte] | DoS limit, enforced in `load_scenario` `:3338-3342` | command-line.md:49 ("20 MB") | n/a |
| scenario.py:84 | `MIN_DYNAMICS_TASK_RATE_S` | 0.001 [s] | least dynamics step | command-line.md:52 | spin box 0.001..1e6 (`gui/propagation_setup_dialog.py:357`) |
| scenario.py:94-96 | `SUPPORTED_CENTRAL_BODIES` | sun, mercury, venus, earth, moon, mars barycenter, jupiter barycenter | bodies in DE430 | reference/capabilities.md (prose) | combo |
| scenario.py:100 | `SMALL_BODY_CENTRAL_BODIES` | eros | small body | small-body-navigation.md | combo |
| scenario.py:104 | `ALBEDO_MAPS` | earth: CERES 2018 5x5, mars: TES 5x5 | albedo data stem | capabilities.md:76, limitations.md:80 | checkbox |
| scenario.py:106 | `SMALL_BODY_EPHEMERIS_SPAN` | eros 1900-01-01..2100-01-01 | ephemeris coverage check `:2732` | limitations.md (prose) | n/a |
| scenario.py:111-116 | `UNRUNNABLE_BODIES` | mars, jupiter -> barycenters | refusal with reason | message only | n/a |
| scenario.py:161-165 | `NAMED_RW_MAX_MOMENTUM_OPTIONS` | HR12 {12,25,50}, HR14 {25,50,75}, HR16 {50,75,100} [N*m*s] | Basilisk factory constraint | message only | sensor_actuator_editor |
| scenario.py:170-172 | `RW_TYPES`, `THRUSTER_TYPES` | 6 / 11 Basilisk factory names | the factory's own built-in parameter sets apply (not in the file) | message only | combo |
| scenario.py:202 | label length | <= 5 [char] | Basilisk device label | message only | form |
| scenario.py:269 | `_MIN_COSINE_GAIN_DBI` | 10 log10(2) - 1e-9 = 3.0103 [dBi] | cosine pattern floor | message only | form |
| scenario.py:333 | `MAX_NAME_CHARS` | 64 [char] | file-name safety | command-line.md:51 | inline check |
| scenario.py:685 | `MAX_DATA_NAME_CHARS` | 127 [char] | Basilisk `char[128]` | message only | form |
| scenario.py:1074 | `ROE_MAX_CHIEF_ECCENTRICITY` | 0.01 [-] | near-circular theory | roe-formation.md | n/a |
| scenario.py:2388 | `GRAVITY_FIELDS` | earth GGM03S max 180, mars GGM2B max 80 [degree] | spherical harmonics | ICD 5.3.1 ("0-180") | spin box range (`propagation_setup_dialog.py:224,284`) |
| scenario.py:2391 | `SUPPORTED_FORECAST_PERCENTILES` | 95, 50, 5 [%] | MSFC columns | user manual (prose) | combo |
| scenario.py:2546-2547 | `MAX_MONTE_CARLO_RUNS`, `MAX_MONTE_CARLO_THREADS` | 100 000; 256 | DoS limits; actual processes capped at CPU count (`usable_thread_count`, `:2550-2553`, logged only, `engine/monte_carlo.py:518-519`) | limitations.md:115-118 (both limits, and the per-CPU cap) | monte_carlo_editor |
| scenario.py:2593 | `SUPPORTED_INTEGRATORS` | euler, rk2, rkf45, rkf78 | Basilisk integrators | yes (prose) | combo |
| scenario.py:2635 | `SimSettings._MAX_SINGLE_RUN_DAYS` | 100.0 [day] | Basilisk ns-clock limit; longer runs are segmented | limitations.md, faq.md | n/a |
| scenario.py:2636 | `SimSettings._MAX_DURATION_DAYS` | 3660.0 [day] | ~10 years | faq.md / capabilities.md | spin box max (`propagation_setup_dialog.py:338`) |
| scenario.py:2677 | `SUPPORTED_SIMULATION_MODES` | full_attitude, orbit_only | mode | user manual | radio |
| command.py:89-91 | `SUPPORTED_COMMAND_KINDS` | propagate, maneuver, lambert_transfer, assignment, report, if, while, script_block | mission sequence | mission-sequence.md | mission_sequence_editor |
| command.py:400-408 | `_MAX_POWER_EXPONENT` 1000, `_MAX_CONDITION_LENGTH` 2000 [char], `_MAX_CONDITION_DEPTH` 50, `_MAX_REPEAT` 1e6, `_MAX_RESULT_LENGTH` 1e5, `_MAX_INTEGER_BITS` 4096 | condition-interpreter safety limits | not found by grep | n/a |
| command.py:197,237,255,258,263 | implicit param defaults | `stop_condition` "duration"; `frame` "inertial"; `num_revolutions` 0; `max_distance_target_m` 1000.0 [m]; `min_orbit_radius_m` 0.0 [m] | applied when the key is absent; not written to the file unless the GUI writes them (`gui/mission_sequence_editor.py:217,352-377` pre-fill the same values) | partly (mission-sequence.md) | yes |

#### A.2b Device-parameter rules outside `_require` (`scenario.py:189-248`)

These run inside `SpacecraftConfig.validate()` (`:2078-2079`, `:2186-2187`) and exist because the Basilisk factories call `exit(1)` instead of raising (comment `:174-178`).

| File:line | Rule | Limit [unit] | Documented? |
|---|---|---|---|
| scenario.py:192-196 | RW/thruster numeric kwargs finite; `Omega_max`, `maxMomentum`, `Js`, `steadyIsp`, `MaxThrust` > 0 | > 0 | message only |
| scenario.py:197-199 | bool kwargs must be bool | - | message only |
| scenario.py:200-202 | `label` <= 5 chars | 5 [char] | message only |
| scenario.py:210-211 | `rw_type` in `RW_TYPES` | enum | message only |
| scenario.py:213-214 | `RWModel` integer | - | message only |
| scenario.py:215-217 | `betaStatic` != 0 | != 0 | message only |
| scenario.py:218-221 | `u_max` > 0 [N*m] unless `useMaxTorque` false; `u_min` > 0 when `useMinTorque` | [N*m] | message only |
| scenario.py:222-224 | `rWB_B` 3 finite [m] | - | message only |
| scenario.py:233-234 | `thruster_type` in `THRUSTER_TYPES` | enum | message only |
| scenario.py:237-238 | `MinOnTime` >= 0 [s] | [s] | message only |
| scenario.py:239-247 | blow-down coefficient lists finite; `r_B` finite [m]; `tHat_B` non-zero | - | message only |
| scenario.py:2090-2122 | custom RW needs `u_max` (or `useMaxTorque` false), needs `Js` or (`Omega_max`+`maxMomentum`), not both | - | message only |
| scenario.py:2123-2130 | named RW: `maxMomentum` in the factory's option set | {12..100} [N*m*s] | message only |
| scenario.py:2147-2171 | motor-thermal group all-or-nothing; T0 > -273.15 [C]; 0 < efficiency < 1; resistance, heat capacity > 0 | [C], [-] | message only |
| scenario.py:2172-2187 | thruster needs `r_B`, `tHat_B`, `MaxThrust` (Basilisk default 0.2 N refused as ambiguous) | [m], [-], [N] | message only |
| scenario.py:2188-2196 | torque rod needs `gtHat_B`, `max_dipole_a_m2` > 0 [A*m^2] | [A*m^2] | message only |
| scenario.py:2024-2051 | thermal sensor: `nHat_B`; `area_m2` in (0, 1000] [m^2]; `mass_kg` in (0, 10000] [kg] if set; absorptivity, emissivity in (0, 1]; fault mode enum | [m^2], [kg] | message only |

#### A.1 Every dataclass field (default, unit, documentation, GUI)

Units: the `[...]` comment on the field's line, else the unit suffix of the name (marked `(name: ...)`); blank = no unit given anywhere on the line. ICD = present in `compliance/docs/ICD_scenario_fields.md` with the same default. UM = occurrences of the field name in user docs. GUI = GUI modules referencing the name (heuristic); *system-written* = set by the tool, not by the user.

| File:line | Class.field | Default | Unit | Comment on line | Documented? | In GUI? |
|---|---|---|---|---|---|---|
| command.py:149 | Command.kind | `(required)` |  |  | ICD; UM 25 | badges, compare_widget +33 |
| command.py:150 | Command.label | `None` |  |  | ICD; UM 46 | actions, app_shell +45 |
| command.py:151 | Command.params | `{}` |  |  | ICD; UM 1 | field_text, main_window +6 |
| command.py:152 | Command.children | `[]` |  |  | ICD; UM 1 | ground_station_editor, mission_sequence_editor +9 |
| command.py:153 | Command.enabled | `True` |  |  | ICD; UM 7 | command_palette, main_window +7 |
| references.py:74 | Reference.path | `(required)` | [1] | human-readable location, e.g. "spacecraft[1] ('sat-2').phasi | not serialised | n/a |
| references.py:75 | Reference.resource_kind | `(required)` |  | "spacecraft" \| "ground_station" | not serialised | n/a |
| references.py:76 | Reference.name | `(required)` |  | the name being referenced | not serialised | n/a |
| scenario.py:380 | OrbitIC.type | `(required)` |  | one of ORBIT_IC_TYPES | ICD; UM 44 | __init__, budget_widget +24 |
| scenario.py:389 | OrbitIC.semi_major_axis_km | `None` | (name: km) |  | ICD; UM 1 | budget_widget, constellation_dialog +7 |
| scenario.py:390 | OrbitIC.eccentricity | `None` |  |  | ICD; UM 16 | constellation_dialog, field_text +11 |
| scenario.py:391 | OrbitIC.inclination_deg | `None` | (name: deg) |  | ICD; UM 0 | budget_widget, constellation_dialog +7 |
| scenario.py:392 | OrbitIC.raan_deg | `None` | (name: deg) |  | ICD; UM 0 | monte_carlo_editor, orbit_ic_widget +2 |
| scenario.py:393 | OrbitIC.arg_periapsis_deg | `None` | (name: deg) |  | ICD; UM 0 | constellation_dialog, monte_carlo_editor +3 |
| scenario.py:394 | OrbitIC.anomaly_type | `"true"` |  | one of ANOMALY_TYPES | ICD; UM 0 | orbit_ic_widget, spacecraft_editor |
| scenario.py:395 | OrbitIC.true_anomaly_deg | `None` | (name: deg) |  | ICD; UM 0 | monte_carlo_editor, orbit_ic_widget +3 |
| scenario.py:396 | OrbitIC.mean_anomaly_deg | `None` | (name: deg) |  | ICD; UM 0 | orbit_ic_widget, spacecraft_editor +1 |
| scenario.py:399 | OrbitIC.position_km | `None` | [x, y, z] | [x, y, z] | ICD; UM 0 | orbit_ic_widget, spacecraft_editor |
| scenario.py:400 | OrbitIC.velocity_km_s | `None` | [vx, vy, vz] | [vx, vy, vz] | ICD; UM 0 | orbit_ic_widget, spacecraft_editor |
| scenario.py:403 | OrbitIC.tle_line1 | `None` |  |  | ICD; UM 0 | orbit_ic_widget, spacecraft_editor |
| scenario.py:404 | OrbitIC.tle_line2 | `None` |  |  | ICD; UM 0 | orbit_ic_widget, spacecraft_editor |
| scenario.py:467 | SensorConfig.kind | `(required)` |  |  | ICD; UM 25 | badges, compare_widget +33 |
| scenario.py:468 | SensorConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:469 | SensorConfig.params | `{}` |  |  | ICD; UM 1 | field_text, main_window +6 |
| scenario.py:482 | ActuatorConfig.kind | `(required)` |  |  | ICD; UM 25 | badges, compare_widget +33 |
| scenario.py:483 | ActuatorConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:484 | ActuatorConfig.params | `{}` |  |  | ICD; UM 1 | field_text, main_window +6 |
| scenario.py:503 | PowerConfig.panel_area_m2 | `(required)` | [m^2] | [m^2] total deployed solar panel area | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:504 | PowerConfig.panel_efficiency | `(required)` | [-] | [-] fraction of incident solar power converted to electrical | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:505 | PowerConfig.panel_normal_b | `[0.0, 0.0, 1.0]` |  | body-frame unit vector | ICD; UM 0 | sensor_actuator_editor, spacecraft_editor +1 |
| scenario.py:506 | PowerConfig.bus_idle_power_w | `0.0` | [W] | [W] constant always-on avionics/thermal/ADCS housekeeping lo | ICD; UM 0 | problem_location, spacecraft_editor +1 |
| scenario.py:507 | PowerConfig.battery_capacity_wh | `100.0` | [W*hr] | [W*hr] | ICD; UM 0 | mission_dashboard_widget, spacecraft_editor +2 |
| scenario.py:508 | PowerConfig.battery_initial_soc | `1.0` | [-] | [-] initial state of charge, fraction of capacity, 0 <= x <= | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:551 | RFLinkConfig.tx_power_w | `(required)` | [W] | [W] downlink transmitter RF output power | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:552 | RFLinkConfig.frequency_hz | `(required)` | [Hz] | [Hz] downlink carrier frequency | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:553 | RFLinkConfig.data_rate_bps | `(required)` | [bit/s] | [bit/s] downlink data rate | ICD; UM 0 | data_handling_editor, spacecraft_editor +2 |
| scenario.py:554 | RFLinkConfig.tx_antenna_gain_dbi | `0.0` | [dBi] | [dBi] spacecraft downlink antenna gain | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:555 | RFLinkConfig.implementation_loss_db | `2.0` | [dB] | [dB] combined pointing/polarization/implementation loss | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:556 | RFLinkConfig.required_ebno_db | `6.0` | [dB] | [dB] required Eb/N0 for the assumed modulation/coding | ICD; UM 1 | spacecraft_editor, wizard_settings |
| scenario.py:566 | RFLinkConfig.antenna_beamwidth_deg | `None` | (name: deg) |  | ICD; UM 1 | spacecraft_editor, template_wizard +1 |
| scenario.py:577 | RFLinkConfig.antenna_pattern | `"fixed"` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:580 | RFLinkConfig.antenna_gain_table | `[]` |  |  | ICD; UM 0 | data_handling_editor, spacecraft_editor +1 |
| scenario.py:581 | RFLinkConfig.antenna_front_to_back_db | `15.0` | [dB] | [dB] "cosine" only: gain behind the ground plane, below the  | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:585 | RFLinkConfig.antenna_boresight_b | `None` |  |  | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:663 | CommsPointingConfig.target_ground_station | `(required)` |  |  | ICD; UM 0 | mission_dashboard_widget, problem_location +1 |
| scenario.py:664 | CommsPointingConfig.antenna_boresight_b | `[0.0, 0.0, 1.0]` |  | body-frame unit vector | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:670 | CommsPointingConfig.sun_pointing_axis_b | `None` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:671 | CommsPointingConfig.comms_power_w | `0.0` | [W] | [W] additional transmitter draw while ground-station-pointin | ICD; UM 1 | spacecraft_editor, template_wizard +1 |
| scenario.py:695 | InstrumentConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:696 | InstrumentConfig.data_rate_bps | `(required)` | [bit/s] | [bit/s] | ICD; UM 0 | data_handling_editor, spacecraft_editor +2 |
| scenario.py:697 | InstrumentConfig.power_w | `0.0` | [W] | [W] constant electrical draw; needs SpacecraftConfig.power w | ICD; UM 0 | data_handling_editor, wizard_settings |
| scenario.py:698 | InstrumentConfig.initial_data_gbit | `0.0` | [Gbit] | [Gbit] already in the instrument's memory partition at the s | ICD; UM 0 | data_handling_editor, wizard_settings |
| scenario.py:726 | DataHandlingConfig.storage_capacity_gbit | `(required)` | [Gbit] | [Gbit] 8 Gbit = 1 GB | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:727 | DataHandlingConfig.instruments | `[]` |  | InstrumentConfig | ICD; UM 5 | data_handling_editor, spacecraft_editor +2 |
| scenario.py:728 | DataHandlingConfig.transmitter_power_w | `0.0` | [W] | [W] DC draw while transmitting; needs SpacecraftConfig.power | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:773 | SolarArrayConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:774 | SolarArrayConfig.mass_kg | `(required)` | [kg] | [kg] | ICD; UM 2 | lifetime_widget, mission_sequence_editor +6 |
| scenario.py:775 | SolarArrayConfig.span_m | `(required)` | [m] | [m] hinge to tip | ICD; UM 0 | solar_array_editor, wizard_settings |
| scenario.py:776 | SolarArrayConfig.width_m | `(required)` | [m] | [m] along the hinge | ICD; UM 0 | solar_array_editor, wizard_settings |
| scenario.py:777 | SolarArrayConfig.hinge_position_b | `(required)` | [m] | [m] body frame | ICD; UM 0 | solar_array_editor, wizard_settings |
| scenario.py:778 | SolarArrayConfig.deploy_direction_b | `(required)` |  | body-frame direction from the hinge to the tip | ICD; UM 0 | solar_array_editor, wizard_settings |
| scenario.py:779 | SolarArrayConfig.normal_b | `(required)` |  | body-frame normal of the cell side, perpendicular to deploy_ | ICD; UM 0 | facet_editor, solar_array_editor +1 |
| scenario.py:780 | SolarArrayConfig.first_mode_hz | `(required)` | [Hz] | [Hz] first bending frequency, hub held fixed | ICD; UM 0 | solar_array_editor, template_wizard +1 |
| scenario.py:781 | SolarArrayConfig.damping_ratio | `(required)` | [-] | [-] of that mode | ICD; UM 0 | solar_array_editor, template_wizard +1 |
| scenario.py:782 | SolarArrayConfig.initial_deflection_deg | `0.0` | [deg] | [deg] about the hinge, positive toward normal_b | ICD; UM 0 | solar_array_editor, wizard_settings |
| scenario.py:783 | SolarArrayConfig.initial_rate_deg_s | `0.0` | [deg/s] | [deg/s] | ICD; UM 0 | solar_array_editor, wizard_settings |
| scenario.py:784 | SolarArrayConfig.generates_power | `True` |  |  | ICD; UM 0 | solar_array_editor, wizard_settings |
| scenario.py:840 | StationKeepingConfig.target_altitude_km | `(required)` | [km] | [km] altitude above the central body's equatorial radius to  | ICD; UM 0 | field_text, phasing_formation_dialog +3 |
| scenario.py:841 | StationKeepingConfig.deadband_km | `(required)` | [km] | [km] how far below target_altitude_km before a reboost burn  | ICD; UM 0 | field_text, phasing_formation_dialog +3 |
| scenario.py:842 | StationKeepingConfig.thrust_n | `(required)` | [N] | [N] reboost thruster thrust | ICD; UM 2 | field_text, mission_sequence_editor +5 |
| scenario.py:843 | StationKeepingConfig.isp_s | `(required)` | [s] | [s] reboost thruster specific impulse | ICD; UM 0 | budget_widget, mission_sequence_editor +4 |
| scenario.py:844 | StationKeepingConfig.propellant_kg | `(required)` | [kg] | [kg] initial propellant mass available for station-keeping | ICD; UM 0 | budget_widget, lifetime_widget +4 |
| scenario.py:845 | StationKeepingConfig.eclipse_sunlit_threshold | `0.99` | [-] | [-] shadow factor above which the spacecraft is treated as s | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:850 | StationKeepingConfig.min_on_time_s | `0.0` | [s] | [s] minimum firing duration (minimum impulse bit = thrust_n  | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:854 | StationKeepingConfig.eccentricity_neutral_burns | `False` |  |  | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:880 | GeoStationKeepingConfig.target_longitude_deg | `(required)` | [deg] | [deg] east longitude of the slot | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:881 | GeoStationKeepingConfig.thrust_n | `(required)` | [N] | [N] | ICD; UM 2 | field_text, mission_sequence_editor +5 |
| scenario.py:882 | GeoStationKeepingConfig.isp_s | `(required)` | [s] | [s] | ICD; UM 0 | budget_widget, mission_sequence_editor +4 |
| scenario.py:883 | GeoStationKeepingConfig.propellant_kg | `(required)` | [kg] | [kg] initial propellant, on top of dry_mass_kg | ICD; UM 0 | budget_widget, lifetime_widget +4 |
| scenario.py:884 | GeoStationKeepingConfig.longitude_deadband_deg | `0.05` | [deg] | [deg] half-width of the longitude box | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:885 | GeoStationKeepingConfig.inclination_max_deg | `0.05` | [deg] | [deg] | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:931 | ConstantThrustConfig.frame | `"VNB"` |  | one of SUPPORTED_THRUST_FRAMES | ICD; UM 35 | app_shell, facet_editor +14 |
| scenario.py:932 | ConstantThrustConfig.direction | `[1.0, 0.0, 0.0]` | [-] | unit vector in `frame` [-] | ICD; UM 15 | formation_diagram_widget, param_form +6 |
| scenario.py:933 | ConstantThrustConfig.thrust_n | `0.01` | [N] | [N] | ICD; UM 2 | field_text, mission_sequence_editor +5 |
| scenario.py:934 | ConstantThrustConfig.isp_s | `1500.0` | [s] | [s] | ICD; UM 0 | budget_widget, mission_sequence_editor +4 |
| scenario.py:935 | ConstantThrustConfig.propellant_kg | `2.0` | [kg] | [kg] initial propellant mass available | ICD; UM 0 | budget_widget, lifetime_widget +4 |
| scenario.py:1016 | PhasingKeepingConfig.chief_spacecraft | `(required)` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1017 | PhasingKeepingConfig.target_separation_km | `(required)` | [km] | [km] one or more along-track distances ahead of the chief | ICD; UM 0 | formation_diagram_widget, phasing_formation_dialog +3 |
| scenario.py:1018 | PhasingKeepingConfig.reconfiguration_interval_days | `90.0` | [day] | [day] only matters if target_separation_km has >1 entry | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:1019 | PhasingKeepingConfig.tolerance_fraction | `0.10` | [-] | [-] trigger threshold, as a fraction of the current target s | ICD; UM 0 | formation_diagram_widget, phasing_formation_dialog +2 |
| scenario.py:1020 | PhasingKeepingConfig.restore_tolerance_fraction | `0.02` | [-] | [-] "close enough, stop drifting" threshold, same units | ICD; UM 0 | formation_diagram_widget, phasing_formation_dialog +2 |
| scenario.py:1024 | PhasingKeepingConfig.correction_window_days | `3.0` | [day] | [day] target time to null a fresh phasing error | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:1025 | PhasingKeepingConfig.max_drift_days | `90.0` | [day] | [day] safety cap on the drift coast phase | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:1026 | PhasingKeepingConfig.max_delta_semi_major_axis_km | `3.0` | [km] | [km] safety clamp on the drift-orbit SMA offset | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:1033 | PhasingKeepingConfig.control_law | `"drift_orbit"` |  | one of PHASING_CONTROL_LAWS: drift_orbit, mean_oe, hill_pd | ICD; UM 0 | phasing_formation_dialog, roe_formation_dialog +1 |
| scenario.py:1036 | PhasingKeepingConfig.mean_oe_gain | `2500.0` | [m^2/s^3] | [m^2/s^3] "mean_oe": diagonal of K per kg of spacecraft | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1037 | PhasingKeepingConfig.hill_position_gain | `2.0e-6` | [1/s^2] | [1/s^2] "hill_pd": diagonal of K | ICD; UM 0 | spacecraft_editor |
| scenario.py:1038 | PhasingKeepingConfig.hill_velocity_gain | `2.0e-3` | [1/s] | [1/s] "hill_pd": diagonal of P | ICD; UM 0 | spacecraft_editor |
| scenario.py:1084 | RoeTargetConfig.start_day | `0.0` | [day] | [day] from the epoch | ICD; UM 0 | roe_diagram_widget, roe_formation_editor +1 |
| scenario.py:1087 | RoeTargetConfig.roe_m | `[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]` | (name: m) |  | ICD; UM 0 | roe_diagram_widget, roe_formation_dialog +3 |
| scenario.py:1124 | RoeFormationConfig.chief_spacecraft | `(required)` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1125 | RoeFormationConfig.targets | `(required)` |  | RoeTargetConfig, start_day increasing from 0 | ICD; UM 5 | roe_diagram_widget, roe_formation_editor +2 |
| scenario.py:1126 | RoeFormationConfig.control_law | `"impulsive"` |  | one of ROE_CONTROL_LAWS | ICD; UM 0 | phasing_formation_dialog, roe_formation_dialog +1 |
| scenario.py:1129 | RoeFormationConfig.tolerance_m | `[2.0, 20.0, 10.0, 10.0]` | (name: m) |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1130 | RoeFormationConfig.correction_window_days | `1.0` | [day] | [day] "impulsive": time to bring the mean longitude back by  | ICD; UM 0 | phasing_formation_dialog, spacecraft_editor +1 |
| scenario.py:1131 | RoeFormationConfig.max_drift_m | `100.0` | [m] | [m] "impulsive": largest a*\|da\| held while drifting | ICD; UM 0 | spacecraft_editor |
| scenario.py:1134 | RoeFormationConfig.max_burn_fraction_of_orbit | `0.1` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1138 | RoeFormationConfig.differential_drag | `True` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1139 | RoeFormationConfig.drag_estimate_window_days | `1.0` | [day] | [day] "impulsive": how far back the decay is fitted | ICD; UM 0 | spacecraft_editor |
| scenario.py:1142 | RoeFormationConfig.continuous_gain | `25000.0` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1143 | RoeFormationConfig.target_refresh_s | `600.0` | [s] | [s] "continuous": how often the element target follows the c | ICD; UM 0 | spacecraft_editor |
| scenario.py:1202 | OpticalNavigationConfig.field_of_view_deg | `40.0` | [deg] | [deg] edge to edge along the image's y (line) axis | ICD; UM 0 | spacecraft_editor |
| scenario.py:1203 | OpticalNavigationConfig.resolution_px | `[512, 512]` | [px] | [px] width, height | ICD; UM 0 | spacecraft_editor |
| scenario.py:1205 | OpticalNavigationConfig.camera_mrp_cb | `[0.0, 0.0, 0.0]` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1206 | OpticalNavigationConfig.measurement_interval_s | `60.0` | [s] | [s] one image this often | ICD; UM 0 | spacecraft_editor |
| scenario.py:1207 | OpticalNavigationConfig.center_noise_px | `0.5` | [px] | [px] 1 sigma on the disk centre, each axis | ICD; UM 0 | spacecraft_editor |
| scenario.py:1208 | OpticalNavigationConfig.radius_noise_px | `0.5` | [px] | [px] 1 sigma on the disk radius | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1209 | OpticalNavigationConfig.min_radius_px | `5.0` | [px] | [px] a smaller disk is not used | ICD; UM 0 | spacecraft_editor |
| scenario.py:1210 | OpticalNavigationConfig.max_phase_angle_deg | `90.0` | [deg] | [deg] Sun-body-camera angle above which the image is not use | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1211 | OpticalNavigationConfig.initial_position_sigma_m | `1000.0` | [m] | [m] 1 sigma, each axis: the filter's start and its error | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1212 | OpticalNavigationConfig.initial_velocity_sigma_mps | `1.0` | [m/s] | [m/s] 1 sigma, each axis | ICD; UM 0 | spacecraft_editor |
| scenario.py:1214 | OpticalNavigationConfig.process_noise_position_m | `0.1` | (name: m) |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1215 | OpticalNavigationConfig.process_noise_velocity_mps | `1.0e-3` | (name: mps) |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1216 | OpticalNavigationConfig.seed | `1` |  | pixel noise and the initial error | ICD; UM 14 | propagation_setup_dialog, spacecraft_editor |
| scenario.py:1262 | LandmarkNavigationConfig.landmark_count | `100` |  |  | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1263 | LandmarkNavigationConfig.field_of_view_deg | `30.0` | [deg] | [deg] edge to edge along the image's width (x) | ICD; UM 0 | spacecraft_editor |
| scenario.py:1264 | LandmarkNavigationConfig.resolution_px | `[1024, 1024]` | [px] | [px] width, height | ICD; UM 0 | spacecraft_editor |
| scenario.py:1266 | LandmarkNavigationConfig.camera_mrp_cb | `[0.0, 0.0, 0.0]` |  |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1267 | LandmarkNavigationConfig.measurement_interval_s | `600.0` | [s] | [s] one image this often | ICD; UM 0 | spacecraft_editor |
| scenario.py:1268 | LandmarkNavigationConfig.pixel_noise_px | `0.0` | [px] | [px] 1 sigma added to each pixel coordinate, on top of the r | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1269 | LandmarkNavigationConfig.min_sun_elevation_deg | `10.0` | [deg] | [deg] a landmark in lower light is not seen | ICD; UM 0 | spacecraft_editor |
| scenario.py:1270 | LandmarkNavigationConfig.initial_position_sigma_m | `100.0` | [m] | [m] 1 sigma, each axis: the filter's start and its error | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1271 | LandmarkNavigationConfig.initial_velocity_sigma_mps | `0.05` | [m/s] | [m/s] 1 sigma, each axis | ICD; UM 0 | spacecraft_editor |
| scenario.py:1273 | LandmarkNavigationConfig.process_noise_mps2_per_sqrt_hz | `1.0e-8` | (name: hz) |  | ICD; UM 0 | spacecraft_editor |
| scenario.py:1274 | LandmarkNavigationConfig.seed | `1` |  | landmark placement, pixel noise and the initial error | ICD; UM 14 | propagation_setup_dialog, spacecraft_editor |
| scenario.py:1332 | MomentumDumpingConfig.hs_max | `(required)` | [N*m*s] | [N*m*s] total RW angular momentum magnitude that triggers de | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:1333 | MomentumDumpingConfig.thr_min_fire_time | `0.02` | [s] | [s] thruster firing pulse resolution | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1334 | MomentumDumpingConfig.max_counter_value | `100` | [-] | [-] control periods to wait between desaturation firings | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1386 | MagneticMomentumManagementConfig.wheel_speed_biases_rad_s | `(required)` | [rad/s] | [rad/s] one entry per reaction_wheel actuator, in listed ord | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:1387 | MagneticMomentumManagementConfig.c_gain | `0.003` | [-] | [-] control gain mapping wheel speed error to desired magnet | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:1424 | NavigationErrorConfig.attitude_step_deg | `0.0` | [deg] | [deg] 1-sigma change per step, per axis | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1425 | NavigationErrorConfig.attitude_bound_deg | `0.0` | [deg] | [deg] per axis | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1426 | NavigationErrorConfig.rate_step_deg_s | `0.0` | [deg/s] | [deg/s] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1427 | NavigationErrorConfig.rate_bound_deg_s | `0.0` | [deg/s] | [deg/s] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1428 | NavigationErrorConfig.sun_step_deg | `0.0` | [deg] | [deg] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1429 | NavigationErrorConfig.sun_bound_deg | `0.0` | [deg] | [deg] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1430 | NavigationErrorConfig.position_step_m | `0.0` | [m] | [m] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1431 | NavigationErrorConfig.position_bound_m | `0.0` | [m] | [m] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1432 | NavigationErrorConfig.velocity_step_m_s | `0.0` | [m/s] | [m/s] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1433 | NavigationErrorConfig.velocity_bound_m_s | `0.0` | [m/s] | [m/s] | ICD; UM 0 | spacecraft_editor (built by f-string, :2363-2371) |
| scenario.py:1434 | NavigationErrorConfig.seed | `None` |  |  | ICD; UM 14 | propagation_setup_dialog, spacecraft_editor |
| scenario.py:1495 | FuelTankConfig.propellant_mass_kg | `(required)` | [kg] | [kg] initial propellant mass loaded in the tank | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:1496 | FuelTankConfig.max_propellant_mass_kg | `(required)` | [kg] | [kg] tank capacity -- propellant_mass_kg must not exceed thi | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:1497 | FuelTankConfig.tank_position_b_m | `[0.0, 0.0, 0.0]` | [m] | [m] r_TB_B, tank position in body frame | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1520 | PropellantBudgetConfig.mission_years | `5.0` | [year] | [year] nominal operations from the epoch (AD10 Sec. 5.7) | ICD; UM 0 | budget_widget |
| scenario.py:1521 | PropellantBudgetConfig.dry_mass_includes_margin | `False` |  | else the system margin below is added (Sec. 5.10) | ICD; UM 0 | budget_widget |
| scenario.py:1522 | PropellantBudgetConfig.system_margin_fraction | `0.15` | [-] | [-] Sec. 5.10 default | ICD; UM 0 | budget_widget |
| scenario.py:1523 | PropellantBudgetConfig.tank_capacity_kg | `0.0` | [kg] | [kg] maximum propellant load (Sec. 5.8); 0 = the budget's ow | ICD; UM 0 | budget_widget |
| scenario.py:1524 | PropellantBudgetConfig.isp_s | `None` | [s] | [s] None = the orbit thruster's (station keeping etc.) | ICD; UM 0 | budget_widget, mission_sequence_editor +4 |
| scenario.py:1525 | PropellantBudgetConfig.thrust_angle_deg | `0.0` | [deg] | [deg] thruster axis vs wanted thrust direction (Sec. 5.11) | ICD; UM 0 | budget_widget |
| scenario.py:1526 | PropellantBudgetConfig.misalignment_deg | `0.0` | [deg] | [deg] incl. attitude error while thrusting | ICD; UM 0 | budget_widget |
| scenario.py:1527 | PropellantBudgetConfig.plume_efficiency | `1.0` | [-] | [-] | ICD; UM 0 | budget_widget |
| scenario.py:1528 | PropellantBudgetConfig.modulation_efficiency | `1.0` | [-] | [-] | ICD; UM 0 | budget_widget |
| scenario.py:1530 | PropellantBudgetConfig.injection_sma_error_km | `0.0` | [km] | [km] | ICD; UM 0 | budget_widget |
| scenario.py:1531 | PropellantBudgetConfig.injection_eccentricity_error | `0.0` | [-] | [-] eccentricity-vector error to correct (frozen orbit) | ICD; UM 0 | budget_widget |
| scenario.py:1532 | PropellantBudgetConfig.injection_inclination_error_deg | `0.0` | [deg] | [deg] | ICD; UM 0 | budget_widget |
| scenario.py:1533 | PropellantBudgetConfig.injection_raan_delta_v_m_s | `0.0` | [m/s] | [m/s] RAAN/MLST correction, strategy-specific | ICD; UM 0 | budget_widget |
| scenario.py:1534 | PropellantBudgetConfig.orbit_acquisition_delta_v_m_s | `0.0` | [m/s] | [m/s] | ICD; UM 0 | budget_widget |
| scenario.py:1536 | PropellantBudgetConfig.transfer_delta_v_m_s | `0.0` | [m/s] | [m/s] | ICD; UM 0 | budget_widget |
| scenario.py:1537 | PropellantBudgetConfig.in_plane_control_delta_v_m_s | `None` | [m/s] | [m/s] | ICD; UM 0 | budget_widget |
| scenario.py:1538 | PropellantBudgetConfig.out_of_plane_control_delta_v_m_s | `None` | [m/s] | [m/s] | ICD; UM 0 | budget_widget |
| scenario.py:1539 | PropellantBudgetConfig.formation_delta_v_m_s | `None` | [m/s] | [m/s] | ICD; UM 0 | budget_widget |
| scenario.py:1540 | PropellantBudgetConfig.collision_avoidance_count | `0.0` | [-] | [-] e.g. from ESA DRAMA, before the x4 margin | ICD; UM 0 | budget_widget |
| scenario.py:1541 | PropellantBudgetConfig.attitude_thruster_propellant_kg | `0.0` | [kg] | [kg] before the 100% margin | ICD; UM 0 | budget_widget |
| scenario.py:1543 | PropellantBudgetConfig.disposal | `"uncontrolled_reentry"` |  | see SUPPORTED_DISPOSALS | ICD; UM 4 | budget_widget, lifetime_widget |
| scenario.py:1544 | PropellantBudgetConfig.clearance_sma_drop_km | `0.0` | [km] | [km] AD10 suggests >= 5 km for formation flyers | ICD; UM 0 | budget_widget |
| scenario.py:1545 | PropellantBudgetConfig.disposal_lifetime_years | `5.0` | [year] | [year] orbit lifetime after the disposal burn | ICD; UM 0 | budget_widget |
| scenario.py:1546 | PropellantBudgetConfig.controlled_reentry_delta_v_m_s | `0.0` | [m/s] | [m/s] burns before the last | ICD; UM 0 | budget_widget |
| scenario.py:1547 | PropellantBudgetConfig.controlled_reentry_last_burn_m_s | `0.0` | [m/s] | [m/s] the last burn, before its 15% margin | ICD; UM 0 | budget_widget |
| scenario.py:1548 | PropellantBudgetConfig.hall_thruster_ignition_kg | `0.0` | [kg] | [kg] cathode start-up losses over the mission | ICD; UM 0 | budget_widget |
| scenario.py:1585 | FacetConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:1586 | FacetConfig.area_m2 | `(required)` | [m^2] | [m^2] | ICD; UM 0 | facet_editor, model_editor_dialog +3 |
| scenario.py:1587 | FacetConfig.normal_b | `(required)` | [-] | [-] outward normal, body frame (normalized when built) | ICD; UM 0 | facet_editor, solar_array_editor +1 |
| scenario.py:1588 | FacetConfig.location_b | `[0.0, 0.0, 0.0]` | [m] | [m] centre of pressure from point B | ICD; UM 0 | facet_editor, template_wizard +1 |
| scenario.py:1589 | FacetConfig.drag_coeff | `2.2` | [-] | [-] | ICD; UM 2 | facet_editor, lifetime_widget +6 |
| scenario.py:1590 | FacetConfig.specular_coeff | `0.3` | [-] | [-] fraction of sunlight reflected mirror-like | ICD; UM 0 | facet_editor, model_editor_dialog +1 |
| scenario.py:1591 | FacetConfig.diffuse_coeff | `0.1` | [-] | [-] fraction reflected diffusely; the rest is absorbed | ICD; UM 0 | facet_editor, model_editor_dialog +1 |
| scenario.py:1651 | ModelMeshConfig.path | `(required)` |  | absolute, or relative to the scenario file | ICD; UM 45 | app, app_shell +37 |
| scenario.py:1652 | ModelMeshConfig.sha256 | `""` | [-] | [-] of the file when it was imported; "" when not recorded | ICD; UM 0 | system-written |
| scenario.py:1653 | ModelMeshConfig.units | `"m"` |  | one of MESH_UNITS | ICD; UM 31 | constellation_dialog, facet_editor +20 |
| scenario.py:1654 | ModelMeshConfig.up_axis | `"z"` |  | one of MESH_UP_AXES: "y" for files exported Y-up | ICD; UM 0 | model_editor_dialog |
| scenario.py:1675 | ModelPartConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:1676 | ModelPartConfig.shape | `(required)` |  | one of MODEL_SHAPES | ICD; UM 39 | compare_widget, constellation_dialog +15 |
| scenario.py:1677 | ModelPartConfig.dimensions_m | `{}` | [m] | [m] the keys MODEL_SHAPE_DIMENSIONS gives for the shape | ICD; UM 0 | model_editor_dialog |
| scenario.py:1678 | ModelPartConfig.sides | `8` |  | prism only: an octagon by default | ICD; UM 3 | model_editor_dialog |
| scenario.py:1679 | ModelPartConfig.segments | `16` |  | cylinder, cone, sphere: sides they are drawn and faceted wit | ICD; UM 7 | model_editor_dialog, orbit_ic_widget +2 |
| scenario.py:1680 | ModelPartConfig.mesh_index | `None` |  | mesh parts: index into SpacecraftModelConfig.meshes | ICD; UM 0 | model_editor_dialog |
| scenario.py:1681 | ModelPartConfig.mesh_group | `""` |  | mesh parts: the group (o/g name) in that file | ICD; UM 0 | model_editor_dialog |
| scenario.py:1682 | ModelPartConfig.position_b_m | `[0.0, 0.0, 0.0]` | [m] | [m] | ICD; UM 0 | model_editor_dialog, template_wizard |
| scenario.py:1683 | ModelPartConfig.rotation_deg | `[0.0, 0.0, 0.0]` | [deg] | [deg] roll, pitch, yaw (3-2-1) | ICD; UM 0 | model_editor_dialog |
| scenario.py:1684 | ModelPartConfig.scale | `[1.0, 1.0, 1.0]` | [-] | [-] mesh parts only | ICD; UM 19 | __init__, app +14 |
| scenario.py:1685 | ModelPartConfig.color | `[0.7, 0.7, 0.7]` | [-] | [-] RGB, each 0..1 | ICD; UM 0 | app_shell, compare_widget +11 |
| scenario.py:1686 | ModelPartConfig.visible | `True` |  |  | ICD; UM 25 | app_shell, event_timeline_widget +15 |
| scenario.py:1687 | ModelPartConfig.mass_kg | `0.0` | [kg] | [kg] | ICD; UM 2 | lifetime_widget, mission_sequence_editor +6 |
| scenario.py:1688 | ModelPartConfig.distribution | `"solid"` |  | "solid": through the volume; "shell": over the surface | ICD; UM 1 | model_editor_dialog, monte_carlo_editor +2 |
| scenario.py:1689 | ModelPartConfig.counts_toward_mass | `True` |  | False for a part whose mass is modelled elsewhere (a flexibl | ICD; UM 0 | model_editor_dialog |
| scenario.py:1690 | ModelPartConfig.in_surface_model | `True` |  | its outer faces become drag/SRP facets | ICD; UM 0 | model_editor_dialog |
| scenario.py:1691 | ModelPartConfig.excluded_faces | `[]` |  | names from MODEL_SHAPE_FACES left out of the facets | ICD; UM 0 | model_editor_dialog |
| scenario.py:1692 | ModelPartConfig.drag_coeff | `2.2` | [-] | [-] | ICD; UM 2 | facet_editor, lifetime_widget +6 |
| scenario.py:1693 | ModelPartConfig.specular_coeff | `0.3` | [-] | [-] | ICD; UM 0 | facet_editor, model_editor_dialog +1 |
| scenario.py:1694 | ModelPartConfig.diffuse_coeff | `0.1` | [-] | [-] | ICD; UM 0 | facet_editor, model_editor_dialog +1 |
| scenario.py:1739 | ModelMassPropertiesConfig.mass_kg | `(required)` | [kg] | [kg] | ICD; UM 2 | lifetime_widget, mission_sequence_editor +6 |
| scenario.py:1740 | ModelMassPropertiesConfig.center_of_mass_b_m | `[0.0, 0.0, 0.0]` | [m] | [m] from body point B | ICD; UM 1 | model_editor_dialog, spacecraft_editor |
| scenario.py:1741 | ModelMassPropertiesConfig.inertia_kg_m2 | `[1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0...` | (name: kg_m2) | about it | ICD; UM 3 | model_editor_dialog, monte_carlo_editor +3 |
| scenario.py:1742 | ModelMassPropertiesConfig.source_file | `""` |  | imported: the file's name | ICD; UM 0 | model_editor_dialog |
| scenario.py:1743 | ModelMassPropertiesConfig.source_sha256 | `""` |  | imported: its SHA-256 | ICD; UM 0 | system-written |
| scenario.py:1762 | SpacecraftModelConfig.parts | `[]` | [ModelPartConfig] | list[ModelPartConfig] | ICD; UM 16 | app_shell, field_text +9 |
| scenario.py:1763 | SpacecraftModelConfig.meshes | `[]` | [ModelMeshConfig] | list[ModelMeshConfig] | ICD; UM 0 | model_editor_dialog |
| scenario.py:1764 | SpacecraftModelConfig.mass_properties_source | `"computed"` |  | one of MASS_PROPERTIES_SOURCES | ICD; UM 0 | model_editor_dialog, spacecraft_editor |
| scenario.py:1765 | SpacecraftModelConfig.mass_properties | `None` |  | for "typed" and "imported" | ICD; UM 0 | model_editor_dialog, model_view_widget +1 |
| scenario.py:1766 | SpacecraftModelConfig.apply_mass_properties | `True` |  |  | ICD; UM 0 | model_editor_dialog, spacecraft_editor |
| scenario.py:1767 | SpacecraftModelConfig.apply_facets | `True` |  |  | ICD; UM 0 | model_editor_dialog, spacecraft_editor |
| scenario.py:1768 | SpacecraftModelConfig.use_for_vizard | `True` |  |  | ICD; UM 0 | model_editor_dialog |
| scenario.py:1791 | SpacecraftConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:1792 | SpacecraftConfig.orbit | `(required)` |  |  | ICD; UM 223 | budget_widget, constellation_dialog +25 |
| scenario.py:1800 | SpacecraftConfig.dry_mass_kg | `100.0` | (name: kg) |  | ICD; UM 5 | budget_widget, monte_carlo_editor +4 |
| scenario.py:1801 | SpacecraftConfig.inertia_kg_m2 | `[10.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0,...` | (name: kg_m2) |  | ICD; UM 3 | model_editor_dialog, monte_carlo_editor +3 |
| scenario.py:1806 | SpacecraftConfig.center_of_mass_b_m | `[0.0, 0.0, 0.0]` | (name: m) |  | ICD; UM 1 | model_editor_dialog, spacecraft_editor |
| scenario.py:1807 | SpacecraftConfig.sigma_bn_init | `[0.0, 0.0, 0.0]` |  |  | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:1808 | SpacecraftConfig.omega_bn_b_init_rad_s | `[0.0, 0.0, 0.0]` | (name: rad_s) |  | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1813 | SpacecraftConfig.enable_drag | `False` |  |  | ICD; UM 0 | propagation_setup_dialog, spacecraft_editor +1 |
| scenario.py:1814 | SpacecraftConfig.drag_coeff | `2.2` |  |  | ICD; UM 2 | facet_editor, lifetime_widget +6 |
| scenario.py:1815 | SpacecraftConfig.drag_area_m2 | `1.0` | (name: m2) |  | ICD; UM 1 | scenario_editor, spacecraft_editor +2 |
| scenario.py:1816 | SpacecraftConfig.enable_srp | `False` |  |  | ICD; UM 0 | propagation_setup_dialog, spacecraft_editor +1 |
| scenario.py:1817 | SpacecraftConfig.srp_coeff | `1.3` |  |  | ICD; UM 2 | monte_carlo_editor, spacecraft_editor +1 |
| scenario.py:1818 | SpacecraftConfig.srp_area_m2 | `1.0` | (name: m2) |  | ICD; UM 1 | scenario_editor, spacecraft_editor +1 |
| scenario.py:1823 | SpacecraftConfig.facets | `[]` |  |  | ICD; UM 26 | facet_editor, model_editor_dialog +5 |
| scenario.py:1839 | SpacecraftConfig.enable_gravity_gradient | `False` |  |  | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1841 | SpacecraftConfig.sensors | `[]` | [SensorConfig] | list[SensorConfig] | ICD; UM 41 | ground_station_editor, main_window +9 |
| scenario.py:1842 | SpacecraftConfig.actuators | `[]` | [ActuatorConfig] | list[ActuatorConfig] | ICD; UM 31 | fsw_workbench_widget, ground_station_editor +8 |
| scenario.py:1845 | SpacecraftConfig.fsw_mode | `None` |  |  | ICD; UM 4 | fsw_workbench_widget, load_scenario_widget +4 |
| scenario.py:1851 | SpacecraftConfig.fsw_params | `{}` |  |  | ICD; UM 2 | problem_location, spacecraft_editor +2 |
| scenario.py:1854 | SpacecraftConfig.control_params | `{}` |  |  | ICD; UM 3 | spacecraft_editor, wizard_settings |
| scenario.py:1856 | SpacecraftConfig.power | `None` |  |  | ICD; UM 40 | main_window, mission_dashboard_widget +9 |
| scenario.py:1857 | SpacecraftConfig.rf_link | `None` |  |  | ICD; UM 0 | main_window, mission_dashboard_widget +3 |
| scenario.py:1858 | SpacecraftConfig.comms_pointing | `None` |  |  | ICD; UM 4 | fsw_workbench_widget, mission_dashboard_widget +3 |
| scenario.py:1859 | SpacecraftConfig.data_handling | `None` |  |  | ICD; UM 2 | problem_location, spacecraft_editor +2 |
| scenario.py:1860 | SpacecraftConfig.solar_arrays | `[]` |  | SolarArrayConfig: flexible, hinged arrays | ICD; UM 1 | problem_location, spacecraft_editor +2 |
| scenario.py:1861 | SpacecraftConfig.station_keeping | `None` |  |  | ICD; UM 3 | field_text, mission_sequence_editor +6 |
| scenario.py:1862 | SpacecraftConfig.geo_station_keeping | `None` |  |  | ICD; UM 0 | spacecraft_editor, template_wizard |
| scenario.py:1863 | SpacecraftConfig.phasing_keeping | `None` |  |  | ICD; UM 1 | mission_sequence_editor, phasing_formation_dialog +4 |
| scenario.py:1864 | SpacecraftConfig.roe_formation | `None` |  | formation in relative orbital elements | ICD; UM 4 | roe_formation_dialog, spacecraft_editor +1 |
| scenario.py:1865 | SpacecraftConfig.optical_navigation | `None` |  | camera navigation from the central body's disk | ICD; UM 4 | spacecraft_editor, template_wizard |
| scenario.py:1866 | SpacecraftConfig.landmark_navigation | `None` |  | camera navigation from a small body's landmarks | ICD; UM 4 | spacecraft_editor, template_wizard |
| scenario.py:1867 | SpacecraftConfig.constant_thrust | `None` |  |  | ICD; UM 0 | mission_sequence_editor, spacecraft_editor +1 |
| scenario.py:1868 | SpacecraftConfig.momentum_dumping | `None` |  |  | ICD; UM 0 | spacecraft_editor, template_wizard +1 |
| scenario.py:1869 | SpacecraftConfig.magnetic_momentum_management | `None` |  |  | ICD; UM 1 | spacecraft_editor, template_wizard +1 |
| scenario.py:1871 | SpacecraftConfig.navigation_error | `None` |  |  | ICD; UM 0 | problem_location, spacecraft_editor |
| scenario.py:1872 | SpacecraftConfig.fuel_tank | `None` |  |  | ICD; UM 1 | spacecraft_editor, template_wizard +1 |
| scenario.py:1873 | SpacecraftConfig.propellant_budget | `None` |  | see engine/propellant_budget.py | ICD; UM 0 | budget_widget, spacecraft_editor |
| scenario.py:1882 | SpacecraftConfig.vizard_model_path | `None` |  | path to a .obj file, or "CUBE"/"CYLINDER"/"SPHERE" | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1883 | SpacecraftConfig.vizard_model_offset_m | `[0.0, 0.0, 0.0]` | (name: m) |  | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1884 | SpacecraftConfig.vizard_model_rotation_deg | `[0.0, 0.0, 0.0]` | (name: deg) | 3-2-1 Euler (z,y,x) | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1885 | SpacecraftConfig.vizard_model_scale | `[1.0, 1.0, 1.0]` |  |  | ICD; UM 0 | spacecraft_editor, wizard_settings |
| scenario.py:1888 | SpacecraftConfig.model | `None` |  |  | ICD; UM 190 | data_table, exports_page +23 |
| scenario.py:2324 | GravityConfig.central_body | `"earth"` |  |  | ICD; UM 2 | constellation_dialog, load_scenario_widget +6 |
| scenario.py:2325 | GravityConfig.central_body_degree | `0` |  | 0 == point-mass only | ICD; UM 1 | propagation_setup_dialog, scenario_editor +3 |
| scenario.py:2326 | GravityConfig.third_body_perturbers | `[]` | ["sun", "moon"] | e.g. ["sun", "moon"] | ICD; UM 0 | propagation_setup_dialog, spacecraft_editor |
| scenario.py:2329 | GravityConfig.polyhedral_gravity | `False` |  |  | ICD; UM 1 | propagation_setup_dialog |
| scenario.py:2332 | GravityConfig.albedo | `False` |  |  | ICD; UM 9 | propagation_setup_dialog |
| scenario.py:2367 | GroundStationConfig.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:2368 | GroundStationConfig.latitude_deg | `(required)` | [deg] | [deg] geodetic latitude, north positive | ICD; UM 0 | ground_station_editor, wizard_settings |
| scenario.py:2369 | GroundStationConfig.longitude_deg | `(required)` | [deg] | [deg] east positive | ICD; UM 0 | ground_station_editor, wizard_settings |
| scenario.py:2370 | GroundStationConfig.altitude_m | `0.0` | [m] | [m] height above the ellipsoid | ICD; UM 2 | ground_station_editor, mission_sequence_editor +1 |
| scenario.py:2371 | GroundStationConfig.min_elevation_deg | `10.0` | (name: deg) |  | ICD; UM 0 | ground_station_editor, template_wizard +1 |
| scenario.py:2375 | GroundStationConfig.rx_antenna_gain_dbi | `0.0` | [dBi] | [dBi] ground station receive antenna gain | ICD; UM 0 | ground_station_editor, wizard_settings |
| scenario.py:2376 | GroundStationConfig.system_noise_temp_k | `290.0` | [K] | [K] ground receiver system noise temperature | ICD; UM 0 | ground_station_editor, wizard_settings |
| scenario.py:2446 | SpaceWeatherConfig.source | `"bundled"` |  | "bundled" \| "local_file" | ICD; UM 51 | __init__, app +21 |
| scenario.py:2447 | SpaceWeatherConfig.local_file_path | `None` |  |  | ICD; UM 0 | propagation_setup_dialog |
| scenario.py:2448 | SpaceWeatherConfig.cache_dir | `None` |  | defaults to engine.spaceweather's own cache dir when None | ICD; UM 0 | propagation_setup_dialog |
| scenario.py:2449 | SpaceWeatherConfig.atmosphere_model | `"nrlmsise00"` |  | "nrlmsise00" \| "exponential" | ICD; UM 2 | propagation_setup_dialog |
| scenario.py:2453 | SpaceWeatherConfig.forecast_percentile | `50.0` |  |  | ICD; UM 0 | lifetime_widget, propagation_setup_dialog |
| scenario.py:2454 | SpaceWeatherConfig.msfc_file_path | `None` |  | your own MSFC prediction table; None = the one shipped with  | ICD; UM 0 | propagation_setup_dialog |
| scenario.py:2479 | DispersionConfig.spacecraft | `(required)` |  | must match a SpacecraftConfig.name in this scenario | ICD; UM 381 | budget_widget, constellation_dialog +45 |
| scenario.py:2480 | DispersionConfig.quantity | `(required)` |  | one of DISPERSION_QUANTITIES | ICD; UM 14 | event_timeline_widget, mission_output_widget +4 |
| scenario.py:2481 | DispersionConfig.kind | `(required)` | [quantity] | one of DISPERSION_KINDS_BY_QUANTITY[quantity] | ICD; UM 25 | badges, compare_widget +33 |
| scenario.py:2486 | DispersionConfig.bounds | `None` | [lo, hi] | [lo, hi] in the quantity's unit (User Manual section 10) | ICD; UM 4 | event_timeline_widget, load_scenario_widget +6 |
| scenario.py:2487 | DispersionConfig.mean | `None` |  | required for "normal" on dry_mass_kg, drag_coeff, srp_coeff | ICD; UM 47 | ground_station_editor, mission_dashboard_widget +10 |
| scenario.py:2490 | DispersionConfig.std_deviation | `None` |  | 1-sigma in the quantity's unit (User Manual section 10) | ICD; UM 0 | monte_carlo_editor, template_wizard +1 |
| scenario.py:2493 | DispersionConfig.element_spread | `None` |  | "orbit_elements": {element key: spread} | ICD; UM 0 | monte_carlo_editor, template_wizard |
| scenario.py:2494 | DispersionConfig.angle_std_deg | `None` | [deg] | [deg] "inertia_kg_m2": 1-sigma rotation that mixes in off-di | ICD; UM 0 | monte_carlo_editor |
| scenario.py:2565 | MonteCarloConfig.enabled | `False` |  |  | ICD; UM 7 | command_palette, main_window +7 |
| scenario.py:2566 | MonteCarloConfig.num_runs | `10` |  |  | ICD; UM 0 | main_window, monte_carlo_editor +3 |
| scenario.py:2567 | MonteCarloConfig.thread_count | `1` |  |  | ICD; UM 3 | monte_carlo_editor, monte_carlo_process +1 |
| scenario.py:2568 | MonteCarloConfig.verbose | `False` |  |  | ICD; UM 0 | formation_diagram_widget, monte_carlo_editor +1 |
| scenario.py:2569 | MonteCarloConfig.dispersions | `[]` | [DispersionConfig] | list[DispersionConfig] | ICD; UM 11 | main_window, monte_carlo_editor +3 |
| scenario.py:2598 | SimSettings.duration_days | `1.0` | (name: days) |  | ICD; UM 1 | field_text, mission_sequence_editor +6 |
| scenario.py:2599 | SimSettings.dynamics_task_rate_s | `10.0` | (name: s) |  | ICD; UM 1 | propagation_setup_dialog, results_widget +2 |
| scenario.py:2600 | SimSettings.integrator | `"rkf78"` |  | see SUPPORTED_INTEGRATORS | ICD; UM 13 | mission_guide, propagation_setup_dialog +3 |
| scenario.py:2607 | SimSettings.record_interval_s | `0.0` | (name: s) |  | ICD; UM 1 | propagation_setup_dialog, wizard_settings |
| scenario.py:2613 | SimSettings.seed | `0` |  |  | ICD; UM 14 | propagation_setup_dialog, spacecraft_editor |
| scenario.py:2662 | FswExportRecord.spacecraft | `(required)` |  |  | ICD; UM 381 | budget_widget, constellation_dialog +45 |
| scenario.py:2663 | FswExportRecord.path | `(required)` |  | the export folder, absolute or relative to the scenario file | ICD; UM 45 | app, app_shell +37 |
| scenario.py:2664 | FswExportRecord.config_digest | `(required)` |  | 64 hex digits (fsw_export.digest.fsw_config_digest) | ICD; UM 0 | system-written |
| scenario.py:2665 | FswExportRecord.exported_utc | `""` |  |  | ICD; UM 0 | system-written |
| scenario.py:2666 | FswExportRecord.basilisk_revision | `""` |  |  | ICD; UM 0 | system-written |
| scenario.py:2667 | FswExportRecord.parts | `{}` |  | setting group -> 16 hex digits | ICD; UM 16 | system-written |
| scenario.py:2682 | Scenario.name | `(required)` |  |  | ICD; UM 94 | __init__, app +65 |
| scenario.py:2683 | Scenario.epoch_utc | `(required)` |  | ISO 8601, e.g. "2030-01-01T00:00:00" -- single source of | ICD; UM 1 | event_timeline_widget, main_window +7 |
| scenario.py:2703 | Scenario.simulation_mode | `"full_attitude"` |  |  | ICD; UM 1 | fsw_workbench_widget, load_scenario_widget +4 |
| scenario.py:2704 | Scenario.gravity | `GravityConfig()` |  |  | ICD; UM 67 | constellation_dialog, load_scenario_widget +11 |
| scenario.py:2705 | Scenario.spacecraft | `[]` | [SpacecraftConfig] | list[SpacecraftConfig], >= 1 required | ICD; UM 381 | budget_widget, constellation_dialog +45 |
| scenario.py:2706 | Scenario.ground_stations | `[]` | [GroundStationConfig] | list[GroundStationConfig] | ICD; UM 0 | ground_station_editor, mission_dashboard_widget +4 |
| scenario.py:2707 | Scenario.space_weather | `SpaceWeatherConfig()` |  |  | ICD; UM 0 | data_panel_widget, problem_location +3 |
| scenario.py:2708 | Scenario.sim_settings | `SimSettings()` |  |  | ICD; UM 2 | field_text, problem_location +5 |
| scenario.py:2709 | Scenario.monte_carlo | `MonteCarloConfig()` |  |  | ICD; UM 1 | main_window, mission_guide +8 |
| scenario.py:2719 | Scenario.mission_sequence | `[]` | [Command] | list[Command] | ICD; UM 0 | main_window, mission_guide +7 |
| scenario.py:2720 | Scenario.fsw_exports | `[]` | [FswExportRecord] | list[FswExportRecord], at most one per spacecraft | ICD; UM 0 | fsw_workbench_widget, scenario_editor |
| scenario.py:2721 | Scenario.description | `""` |  |  | ICD; UM 38 | constellation_dialog, load_scenario_widget +11 |
| scenario.py:2722 | Scenario.schema_version | `CURRENT_SCHEMA_VERSION` |  |  | ICD; UM 0 | system-written |

#### A.2 Every validation rule

Condition as written (literal limits in it); message abbreviated (`{}` = interpolated value). Documented? = whether the LIMIT (not just the field) is stated in user docs; established by grep for the number next to the field name, then checked by hand for the hits. GUI: every rule is enforced live by the GUI because the editor calls the same `validate()` (`gui/scenario_editor.py:96-100`); spin-box ranges sometimes differ (noted in A.4).

| File:line | Owner | Condition (limit) | Message (abbrev.) | Documented? |
|---|---|---|---|---|
| command.py:166 | Command.validate | `isinstance(self.enabled, bool)` | f"enabled {} must be true or false" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:188 | Command.validate | `not self.children` | f"kind {} does not accept children (only 'if'/'while' do)" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:198 | Command._validate_propagate | `stop_condition in SUPPORTED_STOP_CONDITIONS` | f"propagate.stop_condition {} must be one of {}" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:202 | Command._validate_propagate | `isinstance(duration_days, (int, float)) and duration_days > 0` | "propagate.duration_days must be a number > 0 when stop_condition is 'duration'" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:216 | Command._validate_propagate | `event_kind in SUPPORTED_EVENT_KINDS` | f"propagate.event_kind {} must be one of {} when " "stop_condition is 'event'" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:220 | Command._validate_propagate | `isinstance(spacecraft, str) and bool(spacecraft)` | "propagate.spacecraft must name the spacecraft this event is evaluated against when " "stop_condition is 'e... | No (command rules; enum names partly in mission-sequence.md) |
| command.py:225 | Command._validate_propagate | `isinstance(ground_station, str) and bool(ground_station)` | f"propagate.ground_station must name the station whose pass ends this propagate " f"when event_kind is {}" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:231 | Command._validate_maneuver | `isinstance(spacecraft, str) and bool(spacecraft)` | "maneuver.spacecraft must be a non-empty spacecraft name" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:234 | Command._validate_maneuver | `isinstance(delta_v_m_s, list) and len(delta_v_m_s) == 3 and all(isinstance(v, (int, float)) for v in delta_...` | "maneuver.delta_v_m_s must be a 3-element [x, y, z] list of numbers [m/s]" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:238 | Command._validate_maneuver | `frame in SUPPORTED_MANEUVER_FRAMES` | f"maneuver.frame {} must be one of {}" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:243 | Command._validate_lambert_transfer | `isinstance(spacecraft, str) and bool(spacecraft)` | "lambert_transfer.spacecraft must be a non-empty spacecraft name" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:246 | Command._validate_lambert_transfer | `isinstance(target_position_m, list) and len(target_position_m) == 3 and all(isinstance(v, (int, float)) for...` | "lambert_transfer.target_position_m must be a 3-element [x, y, z] list of numbers [m], " "inertial frame, r... | No (command rules; enum names partly in mission-sequence.md) |
| command.py:251 | Command._validate_lambert_transfer | `isinstance(time_of_flight_s, (int, float)) and time_of_flight_s > 0` | "lambert_transfer.time_of_flight_s must be a number > 0 -- time from THIS command's own " "execution until ... | No (command rules; enum names partly in mission-sequence.md) |
| command.py:256 | Command._validate_lambert_transfer | `isinstance(num_revolutions, int) and num_revolutions >= 0` | "lambert_transfer.num_revolutions must be an integer >= 0" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:259 | Command._validate_lambert_transfer | `isinstance(max_distance_target_m, (int, float)) and max_distance_target_m > 0` | "lambert_transfer.max_distance_target_m must be a number > 0 -- lambertValidator rejects " "the solution (z... | No (command rules; enum names partly in mission-sequence.md) |
| command.py:264 | Command._validate_lambert_transfer | `isinstance(min_orbit_radius_m, (int, float)) and min_orbit_radius_m >= 0` | "lambert_transfer.min_orbit_radius_m must be a number >= 0 -- lambertValidator rejects the " "solution if t... | No (command rules; enum names partly in mission-sequence.md) |
| command.py:272 | Command._validate_assignment | `isinstance(target, str) and "." in target` | "assignment.target must be a dotted path string, e.g. 'sat-1.station_keeping.thrust_n'" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:274 | Command._validate_assignment | `"value" in self.params` | "assignment.value is required" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:278 | Command._validate_report | `isinstance(series, list) and all(isinstance(s, str) for s in series)` | "report.series must be a list of series-name strings (empty list means 'snapshot everything')" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:283 | Command._validate_conditional | `isinstance(condition, str) and bool(condition.strip())` | f"{}.condition must be a non-empty expression string" | No (command rules; enum names partly in mission-sequence.md) |
| command.py:293 | Command._validate_script_block | `isinstance(code, str) and bool(code.strip())` | "script_block.code must be a non-empty string" | No (command rules; enum names partly in mission-sequence.md) |
| scenario.py:407 | OrbitIC.validate | `self.type in ORBIT_IC_TYPES` | f"orbit.type {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:415 | OrbitIC.validate | `value is None or _is_finite_number(value)` | f"classical_elements orbit: {} must be a finite number, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:417 | OrbitIC.validate | `self.semi_major_axis_km is not None and self.semi_major_axis_km > 0` | "classical_elements orbit needs semi_major_axis_km > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:419 | OrbitIC.validate | `self.eccentricity is not None and 0.0 <= self.eccentricity < 1.0` | "classical_elements orbit needs 0 <= eccentricity < 1 (elliptical only)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:422 | OrbitIC.validate | `getattr(self, name) is not None` | f"classical_elements orbit needs {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:423 | OrbitIC.validate | `self.anomaly_type in ANOMALY_TYPES` | f"orbit.anomaly_type {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:426 | OrbitIC.validate | `getattr(self, anomaly_field) is not None` | f"classical_elements orbit with anomaly_type={} needs {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:431 | OrbitIC.validate | `value is not None and len(value) == 3` | f"cartesian orbit needs {} as a 3-element [x, y, z] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:433 | OrbitIC.validate | `all(_is_finite_number(v) for v in value)` | f"cartesian orbit: {} must hold finite numbers, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:435 | OrbitIC.validate | `any(v != 0.0 for v in self.position_km)` | "cartesian orbit: position_km must not be [0, 0, 0]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:437 | OrbitIC.validate | `bool(self.tle_line1) and bool(self.tle_line2)` | "tle orbit needs both tle_line1 and tle_line2" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:522 | PowerConfig.validate | `0.0 < self.panel_area_m2 <= 2000.0` | f"{}: power.panel_area_m2 must be in (0, 2000] m^2 -- if your intended " "value is outside this range, chec... | No |
| scenario.py:525 | PowerConfig.validate | `0.0 < self.panel_efficiency <= 1.0` | f"{}: power.panel_efficiency must be in (0, 1]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:527 | PowerConfig.validate | `_is_direction_vector(self.panel_normal_b)` | f"{}: power.panel_normal_b must be a non-zero, finite 3-element [x, y, z] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:529 | PowerConfig.validate | `self.bus_idle_power_w >= 0` | f"{}: power.bus_idle_power_w must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:530 | PowerConfig.validate | `0.0 < self.battery_capacity_wh <= 1.0e6` | f"{}: power.battery_capacity_wh must be in (0, 1e6] W*hr -- if your " "intended value is outside this range... | No |
| scenario.py:533 | PowerConfig.validate | `0.0 <= self.battery_initial_soc <= 1.0` | f"{}: power.battery_initial_soc must be in [0, 1]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:593 | RFLinkConfig.validate | `0.0 < self.tx_power_w <= 1.0e4` | f"{}: rf_link.tx_power_w must be in (0, 1e4] W -- if your intended value " "is outside this range, check fo... | No |
| scenario.py:596 | RFLinkConfig.validate | `self.frequency_hz > 0` | f"{}: rf_link.frequency_hz must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:597 | RFLinkConfig.validate | `self.data_rate_bps > 0` | f"{}: rf_link.data_rate_bps must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:598 | RFLinkConfig.validate | `self.implementation_loss_db >= 0` | f"{}: rf_link.implementation_loss_db must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:600 | RFLinkConfig.validate | `self.antenna_beamwidth_deg is None or self.antenna_beamwidth_deg > 0` | f"{}: rf_link.antenna_beamwidth_deg must be None or > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:602 | RFLinkConfig.validate | `self.antenna_pattern in SUPPORTED_ANTENNA_PATTERNS` | f"{}: rf_link.antenna_pattern must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:607 | RFLinkConfig.validate | `self.tx_antenna_gain_dbi >= _MIN_COSINE_GAIN_DBI` | f"{}: rf_link.tx_antenna_gain_dbi must be >= 3.01 dBi for a \"cosine\" " "(patch) pattern -- a lower peak g... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:610 | RFLinkConfig.validate | `_is_finite_number(self.antenna_front_to_back_db) and self.antenna_front_to_back_db >= 0` | f"{}: rf_link.antenna_front_to_back_db must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:614 | RFLinkConfig.validate | `isinstance(table, list) and len(table) >= 2 and all(isinstance(row, (list, tuple)) and len(row) == 2 and al...` | f"{}: rf_link.antenna_gain_table needs at least two " "[off-boresight angle deg, gain dBi] pairs" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:620 | RFLinkConfig.validate | `angles[0] == 0 and all(b > a for a, b in zip(angles, angles[1:])) and angles[-1] <= 180` | f"{}: rf_link.antenna_gain_table angles must start at 0 deg and rise " "to at most 180 deg" | No |
| scenario.py:623 | RFLinkConfig.validate | `self.antenna_boresight_b is None or _is_direction_vector(self.antenna_boresight_b)` | f"{}: rf_link.antenna_boresight_b must be None or a non-zero, finite " "3-element [x, y, z] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:674 | CommsPointingConfig.validate | `bool(self.target_ground_station)` | f"{}: comms_pointing.target_ground_station must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:676 | CommsPointingConfig.validate | `_is_direction_vector(self.antenna_boresight_b)` | f"{}: comms_pointing.antenna_boresight_b must be a non-zero, finite 3-element " "[x, y, z] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:679 | CommsPointingConfig.validate | `self.sun_pointing_axis_b is None or _is_direction_vector(self.sun_pointing_axis_b)` | f"{}: comms_pointing.sun_pointing_axis_b must be None or a non-zero, finite " "3-element [x, y, z] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:682 | CommsPointingConfig.validate | `self.comms_power_w >= 0` | f"{}: comms_pointing.comms_power_w must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:702 | InstrumentConfig.validate | `bool(self.name) and len(self.name) <= MAX_DATA_NAME_CHARS` | f"{}: every data_handling instrument needs a name of 1 to " f"{} characters" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:705 | InstrumentConfig.validate | `_is_finite_number(self.data_rate_bps) and 0.0 < self.data_rate_bps <= 1.0e11` | f"{}: data_rate_bps must be in (0, 1e11] bit/s" | No |
| scenario.py:707 | InstrumentConfig.validate | `_is_finite_number(self.power_w) and self.power_w >= 0` | f"{}: power_w must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:708 | InstrumentConfig.validate | `_is_finite_number(self.initial_data_gbit) and self.initial_data_gbit >= 0` | f"{}: initial_data_gbit must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:731 | DataHandlingConfig.validate | `_is_finite_number(self.storage_capacity_gbit) and 0.0 < self.storage_capacity_gbit <= 1.0e6` | f"{}: data_handling.storage_capacity_gbit must be in (0, 1e6] Gbit" | No |
| scenario.py:733 | DataHandlingConfig.validate | `len(self.instruments) > 0` | f"{}: data_handling needs at least one instrument (housekeeping counts)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:738 | DataHandlingConfig.validate | `len(set(names)) == len(names)` | f"{}: data_handling instrument names must be unique" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:740 | DataHandlingConfig.validate | `initial <= self.storage_capacity_gbit` | f"{}: data_handling instruments start with {} Gbit, more than the " f"{} Gbit storage capacity" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:743 | DataHandlingConfig.validate | `_is_finite_number(self.transmitter_power_w) and self.transmitter_power_w >= 0` | f"{}: data_handling.transmitter_power_w must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:788 | SolarArrayConfig.validate | `bool(self.name)` | f"{}: every solar array needs a name" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:791 | SolarArrayConfig.validate | `_is_finite_number(value) and value > 0` | f"{}: {} must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:792 | SolarArrayConfig.validate | `self.span_m <= 100.0 and self.width_m <= 100.0` | f"{}: span_m and width_m must be at most 100 m -- check for a units mixup" | No |
| scenario.py:794 | SolarArrayConfig.validate | `self.first_mode_hz <= 100.0` | f"{}: first_mode_hz must be at most 100 Hz" | No |
| scenario.py:795 | SolarArrayConfig.validate | `_is_finite_number(self.damping_ratio) and 0.0 <= self.damping_ratio < 1.0` | f"{}: damping_ratio must be in [0, 1)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:799 | SolarArrayConfig.validate | `isinstance(vector, list) and len(vector) == 3 and all(_is_finite_number(v) for v in vector)` | f"{}: {} must be a finite 3-element [x, y, z] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:802 | SolarArrayConfig.validate | `_is_direction_vector(getattr(self, key))` | f"{}: {} must be a non-zero, finite 3-element [x, y, z] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:806 | SolarArrayConfig.validate | `abs(sum(a * b for a, b in zip(e, n))) < 1e-3` | f"{}: normal_b must be perpendicular to deploy_direction_b (the hinge runs along both " "faces' common edge)" | No |
| scenario.py:810 | SolarArrayConfig.validate | `_is_finite_number(getattr(self, key))` | f"{}: {} must be a finite number" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:811 | SolarArrayConfig.validate | `abs(self.initial_deflection_deg) < 90.0` | f"{}: initial_deflection_deg must be within 90 deg" | No |
| scenario.py:857 | StationKeepingConfig.validate | `self.target_altitude_km > 0` | f"{}: station_keeping.target_altitude_km must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:858 | StationKeepingConfig.validate | `math.isfinite(self.min_on_time_s) and 0.0 <= self.min_on_time_s <= 86400.0` | f"{}: station_keeping.min_on_time_s must be in [0, 86400] s" | No |
| scenario.py:860 | StationKeepingConfig.validate | `isinstance(self.eccentricity_neutral_burns, bool)` | f"{}: station_keeping.eccentricity_neutral_burns must be true or false" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:862 | StationKeepingConfig.validate | `0.0 < self.deadband_km < self.target_altitude_km` | f"{}: station_keeping.deadband_km must be > 0 and < target_altitude_km" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:864 | StationKeepingConfig.validate | `self.thrust_n > 0` | f"{}: station_keeping.thrust_n must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:865 | StationKeepingConfig.validate | `self.isp_s > 0` | f"{}: station_keeping.isp_s must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:866 | StationKeepingConfig.validate | `self.propellant_kg >= 0` | f"{}: station_keeping.propellant_kg must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:867 | StationKeepingConfig.validate | `0.0 < self.eclipse_sunlit_threshold <= 1.0` | f"{}: station_keeping.eclipse_sunlit_threshold must be in (0, 1]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:889 | GeoStationKeepingConfig.validate | `-180.0 <= self.target_longitude_deg <= 360.0` | f"{}.target_longitude_deg must be in [-180, 360] deg" | No |
| scenario.py:891 | GeoStationKeepingConfig.validate | `0.0 < self.longitude_deadband_deg <= 5.0` | f"{}.longitude_deadband_deg must be in (0, 5] deg" | No |
| scenario.py:892 | GeoStationKeepingConfig.validate | `0.0 < self.inclination_max_deg <= 10.0` | f"{}.inclination_max_deg must be in (0, 10] deg" | No |
| scenario.py:893 | GeoStationKeepingConfig.validate | `self.thrust_n > 0` | f"{}.thrust_n must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:894 | GeoStationKeepingConfig.validate | `self.isp_s > 0` | f"{}.isp_s must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:895 | GeoStationKeepingConfig.validate | `self.propellant_kg >= 0` | f"{}.propellant_kg must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:938 | ConstantThrustConfig.validate | `self.frame in SUPPORTED_THRUST_FRAMES` | f"{}: constant_thrust.frame {} must be one of " f"{}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:941 | ConstantThrustConfig.validate | `_is_direction_vector(self.direction)` | f"{}: constant_thrust.direction must be a non-zero, finite 3-element vector" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:943 | ConstantThrustConfig.validate | `self.thrust_n > 0` | f"{}: constant_thrust.thrust_n must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:944 | ConstantThrustConfig.validate | `self.isp_s > 0` | f"{}: constant_thrust.isp_s must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:945 | ConstantThrustConfig.validate | `self.propellant_kg >= 0` | f"{}: constant_thrust.propellant_kg must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1041 | PhasingKeepingConfig.validate | `bool(self.chief_spacecraft)` | f"{}: phasing_keeping.chief_spacecraft must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1043 | PhasingKeepingConfig.validate | `self.chief_spacecraft != spacecraft_name` | f"{}: phasing_keeping.chief_spacecraft cannot be the spacecraft itself" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1045 | PhasingKeepingConfig.validate | `len(self.target_separation_km) >= 1` | f"{}: phasing_keeping.target_separation_km needs at least one entry" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1047 | PhasingKeepingConfig.validate | `all(d > 0 for d in self.target_separation_km)` | f"{}: phasing_keeping.target_separation_km entries must all be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1049 | PhasingKeepingConfig.validate | `self.reconfiguration_interval_days >= 0` | f"{}: phasing_keeping.reconfiguration_interval_days must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1051 | PhasingKeepingConfig.validate | `0.0 < self.tolerance_fraction` | f"{}: phasing_keeping.tolerance_fraction must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1053 | PhasingKeepingConfig.validate | `0.0 < self.restore_tolerance_fraction` | f"{}: phasing_keeping.restore_tolerance_fraction must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1055 | PhasingKeepingConfig.validate | `self.correction_window_days > 0` | f"{}: phasing_keeping.correction_window_days must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1057 | PhasingKeepingConfig.validate | `self.max_drift_days > 0` | f"{}: phasing_keeping.max_drift_days must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1059 | PhasingKeepingConfig.validate | `self.max_delta_semi_major_axis_km > 0` | f"{}: phasing_keeping.max_delta_semi_major_axis_km must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1061 | PhasingKeepingConfig.validate | `self.control_law in PHASING_CONTROL_LAWS` | f"{}: phasing_keeping.control_law {} must be one of " f"{}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1066 | PhasingKeepingConfig.validate | `isinstance(value, (int, float)) and math.isfinite(value) and value > 0` | f"{}: phasing_keeping.{} must be a finite number > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1147 | RoeFormationConfig.validate | `bool(self.chief_spacecraft)` | f"{}.chief_spacecraft must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1148 | RoeFormationConfig.validate | `self.chief_spacecraft != spacecraft_name` | f"{}.chief_spacecraft cannot be the spacecraft itself" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1150 | RoeFormationConfig.validate | `self.control_law in ROE_CONTROL_LAWS` | f"{}.control_law {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1152 | RoeFormationConfig.validate | `isinstance(self.targets, list) and len(self.targets) >= 1` | f"{}.targets needs at least one entry" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1156 | RoeFormationConfig.validate | `isinstance(target, RoeTargetConfig)` | f"{}.targets[{}] must be an ROE target" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1157 | RoeFormationConfig.validate | `isinstance(target.start_day, (int, float)) and math.isfinite(target.start_day)` | f"{}.targets[{}].start_day must be a finite number" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1159 | RoeFormationConfig.validate | `_finite_vector(target.roe_m, 6)` | f"{}.targets[{}].roe_m must be 6 finite numbers [m]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1162 | RoeFormationConfig.validate | `target.start_day == 0.0` | f"{}.targets[0].start_day must be 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1164 | RoeFormationConfig.validate | `target.start_day > previous` | f"{}.targets[{}].start_day must be later than the one before" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1167 | RoeFormationConfig.validate | `_finite_vector(self.tolerance_m, 4) and all(t > 0 for t in self.tolerance_m)` | f"{}.tolerance_m must be 4 finite numbers > 0 [m]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1169 | RoeFormationConfig.validate | `isinstance(self.differential_drag, bool)` | f"{}.differential_drag must be true or false" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1173 | RoeFormationConfig.validate | `isinstance(value, (int, float)) and math.isfinite(value) and value > 0` | f"{}.{} must be a finite number > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1175 | RoeFormationConfig.validate | `self.max_burn_fraction_of_orbit <= 0.5` | f"{}.max_burn_fraction_of_orbit must be at most 0.5" | No |
| scenario.py:1223 | OpticalNavigationConfig.validate | `isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0` | f"{}.{} must be a finite number > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1228 | OpticalNavigationConfig.validate | `isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0` | f"{}.{} must be a finite number >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1230 | OpticalNavigationConfig.validate | `self.field_of_view_deg < 180.0` | f"{}.field_of_view_deg must be under 180" | No |
| scenario.py:1231 | OpticalNavigationConfig.validate | `self.max_phase_angle_deg <= 180.0` | f"{}.max_phase_angle_deg must be at most 180" | No |
| scenario.py:1232 | OpticalNavigationConfig.validate | `isinstance(self.resolution_px, list) and len(self.resolution_px) == 2 and all(isinstance(n, int) and not is...` | f"{}.resolution_px must be two whole numbers of at least 16 [px]" | No |
| scenario.py:1235 | OpticalNavigationConfig.validate | `_finite_vector(self.camera_mrp_cb, 3)` | f"{}.camera_mrp_cb must be 3 finite numbers" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1236 | OpticalNavigationConfig.validate | `isinstance(self.seed, int) and not isinstance(self.seed, bool) and self.seed >= 0` | f"{}.seed must be a whole number >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1278 | LandmarkNavigationConfig.validate | `isinstance(self.landmark_count, int) and not isinstance(self.landmark_count, bool) and 1 <= self.landmark_c...` | f"{}.landmark_count must be a whole number from 1 to 1000" | No |
| scenario.py:1283 | LandmarkNavigationConfig.validate | `isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0` | f"{}.{} must be a finite number > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1287 | LandmarkNavigationConfig.validate | `isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0` | f"{}.{} must be a finite number >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1289 | LandmarkNavigationConfig.validate | `self.field_of_view_deg < 180.0` | f"{}.field_of_view_deg must be under 180" | No |
| scenario.py:1291 | LandmarkNavigationConfig.validate | `isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and -90.0 <= value...` | f"{}.min_sun_elevation_deg must be from -90 to under 90" | No |
| scenario.py:1293 | LandmarkNavigationConfig.validate | `isinstance(self.resolution_px, list) and len(self.resolution_px) == 2 and all(isinstance(n, int) and not is...` | f"{}.resolution_px must be two whole numbers of at least 16 [px]" | No |
| scenario.py:1296 | LandmarkNavigationConfig.validate | `_finite_vector(self.camera_mrp_cb, 3)` | f"{}.camera_mrp_cb must be 3 finite numbers" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1297 | LandmarkNavigationConfig.validate | `isinstance(self.seed, int) and not isinstance(self.seed, bool) and self.seed >= 0` | f"{}.seed must be a whole number >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1337 | MomentumDumpingConfig.validate | `self.hs_max > 0` | f"{}: momentum_dumping.hs_max must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1338 | MomentumDumpingConfig.validate | `self.thr_min_fire_time > 0` | f"{}: momentum_dumping.thr_min_fire_time must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1339 | MomentumDumpingConfig.validate | `self.max_counter_value >= 1` | f"{}: momentum_dumping.max_counter_value must be >= 1" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1390 | MagneticMomentumManagementConfig.validate | `len(self.wheel_speed_biases_rad_s) == num_reaction_wheels` | f"{}: magnetic_momentum_management.wheel_speed_biases_rad_s needs exactly " f"{} entries (one per reaction_... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1394 | MagneticMomentumManagementConfig.validate | `self.c_gain > 0` | f"{}: magnetic_momentum_management.c_gain must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1445 | NavigationErrorConfig.validate | `isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0.0` | f"{}: navigation_error {} {} must be a number >= 0 [{}]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1448 | NavigationErrorConfig.validate | `step == 0.0 or bound > 0.0` | f"{}: navigation_error {} needs a bound > 0 when its step is set " "(without one Basilisk lets the error gr... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1451 | NavigationErrorConfig.validate | `self.attitude_bound_deg < 180.0 and self.sun_bound_deg < 180.0` | f"{}: navigation_error attitude and Sun bounds must be below 180 deg" | No |
| scenario.py:1453 | NavigationErrorConfig.validate | `self.seed is None or (isinstance(self.seed, int) and not isinstance(self.seed, bool) and 0 <= self.seed < 2...` | f"{}: navigation_error seed must be an integer from 0 to 2^32 - 1" | No |
| scenario.py:1500 | FuelTankConfig.validate | `self.max_propellant_mass_kg > 0` | f"{}: fuel_tank.max_propellant_mass_kg must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1501 | FuelTankConfig.validate | `0.0 <= self.propellant_mass_kg <= self.max_propellant_mass_kg` | f"{}: fuel_tank.propellant_mass_kg must be between 0 and " "max_propellant_mass_kg" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1504 | FuelTankConfig.validate | `len(self.tank_position_b_m) == 3` | f"{}: fuel_tank.tank_position_b_m must be a 3-element [x, y, z] list [m]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1552 | PropellantBudgetConfig.validate | `0.0 < self.mission_years <= 30.0` | f"{}.mission_years must be in (0, 30]" | No |
| scenario.py:1553 | PropellantBudgetConfig.validate | `0.0 <= self.system_margin_fraction < 1.0` | f"{}.system_margin_fraction must be in [0, 1)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1554 | PropellantBudgetConfig.validate | `self.tank_capacity_kg >= 0.0` | f"{}.tank_capacity_kg must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1555 | PropellantBudgetConfig.validate | `self.isp_s is None or self.isp_s > 0.0` | f"{}.isp_s must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1556 | PropellantBudgetConfig.validate | `0.0 <= self.thrust_angle_deg < 90.0 and 0.0 <= self.misalignment_deg < 90.0` | f"{}: thrust_angle_deg and misalignment_deg must be in [0, 90)" | No |
| scenario.py:1558 | PropellantBudgetConfig.validate | `0.0 < self.plume_efficiency <= 1.0 and 0.0 < self.modulation_efficiency <= 1.0` | f"{}: plume_efficiency and modulation_efficiency must be in (0, 1]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1565 | PropellantBudgetConfig.validate | `getattr(self, name) >= 0.0` | f"{}.{} must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1568 | PropellantBudgetConfig.validate | `value is None or value >= 0.0` | f"{}.{} must be >= 0 (or unset: from the last run)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1569 | PropellantBudgetConfig.validate | `self.disposal in SUPPORTED_DISPOSALS` | f"{}.disposal {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1571 | PropellantBudgetConfig.validate | `0.0 < self.disposal_lifetime_years <= 25.0` | f"{}.disposal_lifetime_years must be in (0, 25]" | No |
| scenario.py:1595 | FacetConfig.validate | `bool(self.name)` | f"{}: every facet needs a name" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1596 | FacetConfig.validate | `isinstance(self.area_m2, (int, float)) and 0.0 < self.area_m2 <= 1.0e4` | f"{}: area_m2 must be in (0, 1e4] m^2" | No |
| scenario.py:1598 | FacetConfig.validate | `_is_direction_vector(self.normal_b)` | f"{}: normal_b must be a non-zero, finite 3-element body-frame vector" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1600 | FacetConfig.validate | `isinstance(self.location_b, list) and len(self.location_b) == 3 and all(isinstance(v, (int, float)) and mat...` | f"{}: location_b must be a finite 3-element [x, y, z] in m" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1603 | FacetConfig.validate | `isinstance(self.drag_coeff, (int, float)) and 0.0 <= self.drag_coeff <= 10.0` | f"{}: drag_coeff must be in [0, 10]" | No |
| scenario.py:1605 | FacetConfig.validate | `0.0 <= self.specular_coeff <= 1.0 and 0.0 <= self.diffuse_coeff <= 1.0 and self.specular_coeff + self.diffu...` | f"{}: specular_coeff and diffuse_coeff must each be in [0, 1] and sum to at most 1" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1657 | ModelMeshConfig.validate | `isinstance(self.path, str) and bool(self.path.strip())` | f"{}: path must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1658 | ModelMeshConfig.validate | `self.sha256 == "" or (len(self.sha256) == 64 and all(c in "0123456789abcdef" for c in self.sha256))` | f"{}: sha256 must be empty or 64 lowercase hex digits" | No |
| scenario.py:1660 | ModelMeshConfig.validate | `self.units in MESH_UNITS` | f"{}: units {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1661 | ModelMeshConfig.validate | `self.up_axis in MESH_UP_AXES` | f"{}: up_axis {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1697 | ModelPartConfig.validate | `name_error("part", self.name) is None` | f"{}: {}" | command-line.md:49-53 |
| scenario.py:1699 | ModelPartConfig.validate | `self.shape in MODEL_SHAPES` | f"{}: shape {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1701 | ModelPartConfig.validate | `set(self.dimensions_m) == expected` | f"{}: a {} needs dimensions_m with exactly {}, " f"got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1705 | ModelPartConfig.validate | `isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0.0 < value <=...` | f"{}: dimensions_m[{}] must be in (0, 1000] m" | No |
| scenario.py:1707 | ModelPartConfig.validate | `isinstance(self.sides, int) and 3 <= self.sides <= 64` | f"{}: sides must be 3 to 64" | No |
| scenario.py:1708 | ModelPartConfig.validate | `isinstance(self.segments, int) and 8 <= self.segments <= 256` | f"{}: segments must be 8 to 256" | No |
| scenario.py:1710 | ModelPartConfig.validate | `isinstance(self.mesh_index, int) and 0 <= self.mesh_index < mesh_count` | f"{}: mesh_index must name one of the model's {} mesh file(s)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1712 | ModelPartConfig.validate | `bool(self.mesh_group)` | f"{}: mesh_group must name a group of the mesh file" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1713 | ModelPartConfig.validate | `_finite_vector(self.position_b_m)` | f"{}: position_b_m must be a finite [x, y, z] in m" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1714 | ModelPartConfig.validate | `_finite_vector(self.rotation_deg)` | f"{}: rotation_deg must be a finite [roll, pitch, yaw]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1715 | ModelPartConfig.validate | `_finite_vector(self.scale) and all(v != 0.0 for v in self.scale)` | f"{}: scale must be three finite, non-zero factors" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1717 | ModelPartConfig.validate | `_finite_vector(self.color) and all(0.0 <= v <= 1.0 for v in self.color)` | f"{}: color must be [r, g, b], each 0 to 1" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1719 | ModelPartConfig.validate | `isinstance(self.mass_kg, (int, float)) and math.isfinite(self.mass_kg) and 0.0 <= self.mass_kg <= 1.0e6` | f"{}: mass_kg must be in [0, 1e6]" | No |
| scenario.py:1721 | ModelPartConfig.validate | `self.distribution in MODEL_DISTRIBUTIONS` | f"{}: distribution {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1725 | ModelPartConfig.validate | `not bad` | f"{}: excluded_faces {} are not faces of a {}" + (f" (it has {})" if allowed else "") | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1727 | ModelPartConfig.validate | `isinstance(self.drag_coeff, (int, float)) and 0.0 <= self.drag_coeff <= 10.0` | f"{}: drag_coeff must be in [0, 10]" | No |
| scenario.py:1729 | ModelPartConfig.validate | `0.0 <= self.specular_coeff <= 1.0 and 0.0 <= self.diffuse_coeff <= 1.0 and self.specular_coeff + self.diffu...` | f"{}: specular_coeff and diffuse_coeff must each be in [0, 1] and sum to at most 1" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1746 | ModelMassPropertiesConfig.validate | `isinstance(self.mass_kg, (int, float)) and math.isfinite(self.mass_kg) and 0.0 < self.mass_kg <= 1.0e6` | f"{}: mass_kg must be in (0, 1e6]" | No |
| scenario.py:1748 | ModelMassPropertiesConfig.validate | `_finite_vector(self.center_of_mass_b_m)` | f"{}: center_of_mass_b_m must be a finite [x, y, z]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1749 | ModelMassPropertiesConfig.validate | `_finite_vector(self.inertia_kg_m2, 9)` | f"{}: inertia_kg_m2 must be 9 finite numbers (3x3)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1772 | SpacecraftModelConfig.validate | `bool(self.parts)` | f"{} needs at least one part" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1774 | SpacecraftModelConfig.validate | `len(names) == len(set(names))` | f"{}: part names must be unique, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1779 | SpacecraftModelConfig.validate | `self.mass_properties_source in MASS_PROPERTIES_SOURCES` | f"{}: mass_properties_source {} must be one of " f"{}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1783 | SpacecraftModelConfig.validate | `self.mass_properties is not None` | f"{}: mass_properties_source {} needs mass_properties" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1891 | SpacecraftConfig.validate | `name_error("spacecraft", self.name) is None` | name_error("spacecraft", self.name) or "" | command-line.md:49-53 (64-char names) |
| scenario.py:1898 | SpacecraftConfig.validate | `0.0 < self.dry_mass_kg <= 1.0e6` | f"{}: dry_mass_kg must be in (0, 1e6] -- if your intended value is outside " "this range, check for a units... | troubleshooting.md:159 (as an example error only) |
| scenario.py:1901 | SpacecraftConfig.validate | `len(self.inertia_kg_m2) == 9` | f"{}: inertia_kg_m2 must have 9 elements (3x3, row-major)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1928 | SpacecraftConfig.validate | `ix > 0.0 and iy > 0.0 and iz > 0.0` | f"{}: inertia_kg_m2's diagonal entries (principal moments) must be positive" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1930 | SpacecraftConfig.validate | `ix + iy >= iz and iy + iz >= ix and ix + iz >= iy` | f"{}: inertia_kg_m2's diagonal entries ({}, {}, {}) violate the " "triangle inequality -- no rigid body's p... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1934 | SpacecraftConfig.validate | `_finite_vector(self.center_of_mass_b_m) and math.sqrt(sum(v * v for v in self.center_of_mass_b_m)) <= 100.0` | f"{}: center_of_mass_b_m must be a finite [x, y, z] within 100 m of point B" | No |
| scenario.py:1939 | SpacecraftConfig.validate | `len(self.sigma_bn_init) == 3` | f"{}: sigma_bn_init must have 3 elements" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1940 | SpacecraftConfig.validate | `len(self.omega_bn_b_init_rad_s) == 3` | f"{}: omega_bn_b_init_rad_s must have 3 elements" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1952 | SpacecraftConfig.validate | `self.drag_coeff > 0` | f"{}: drag_coeff must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1958 | SpacecraftConfig.validate | `0.0 < self.drag_area_m2 <= 1.0e4` | f"{}: drag_area_m2 must be in (0, 1e4] -- if your intended value is outside " "this range, check for a unit... | No |
| scenario.py:1961 | SpacecraftConfig.validate | `self.srp_coeff > 0` | f"{}: srp_coeff must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1962 | SpacecraftConfig.validate | `0.0 < self.srp_area_m2 <= 1.0e4` | f"{}: srp_area_m2 must be in (0, 1e4] -- if your intended value is outside " "this range, check for a units... | No |
| scenario.py:1970 | SpacecraftConfig.validate | `self.fsw_mode is None or self.fsw_mode in SUPPORTED_FSW_MODES` | f"{}: fsw_mode {} must be None or one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1975 | SpacecraftConfig.validate | `has_gs != has_body` | f"{}: fsw_mode 'locationPointing' needs exactly one of " "fsw_params['target_ground_station'] or fsw_params... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1979 | SpacecraftConfig.validate | `any(s.kind == "coarse_sun_sensor" for s in self.sensors)` | f"{}: fsw_params['use_css_estimation'] is set but this spacecraft has no " "'coarse_sun_sensor' sensors to ... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1983 | SpacecraftConfig.validate | `self.fsw_mode is None` | f"{}: comms_pointing and fsw_mode cannot both be set -- comms_pointing " "already builds its own Sun-pointi... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1990 | SpacecraftConfig.validate | `not self.actuators` | f"{}: comms_pointing commands an idealised control torque and cannot drive " "actuators -- remove the actua... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1995 | SpacecraftConfig.validate | `len(sensor_names) == len(set(sensor_names))` | f"{}: sensor names must be unique, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1998 | SpacecraftConfig.validate | `bool(sensor.kind) and bool(sensor.name)` | f"{}: every sensor needs kind and name" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:1999 | SpacecraftConfig.validate | `name_error("sensor", sensor.name) is None` | f"{}: {}" | command-line.md:49-53 |
| scenario.py:2000 | SpacecraftConfig.validate | `sensor.kind in SUPPORTED_SENSOR_KINDS` | f"{}: sensor {} kind {} must be one of " f"{}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2005 | SpacecraftConfig.validate | `nHat_B is not None and _is_direction_vector(nHat_B)` | f"{}: coarse_sun_sensor {} needs params['nHat_B'] " "as a non-zero, finite 3-element body-frame boresight u... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2010 | SpacecraftConfig.validate | `nHat_B is not None and _is_direction_vector(nHat_B)` | f"{}: thermal sensor {} needs params['nHat_B'] " "as a non-zero, finite 3-element body-frame face-normal un... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2030 | SpacecraftConfig.validate | `area_m2 is not None and 0.0 < area_m2 <= 1000.0` | f"{}: thermal sensor {} needs params['area_m2'] in " "(0, 1000] -- if your intended value is outside this r... | No |
| scenario.py:2036 | SpacecraftConfig.validate | `0.0 < mass_kg <= 10000.0` | f"{}: thermal sensor {} params['mass_kg'] must be in " "(0, 10000] if set -- if your intended value is outs... | No |
| scenario.py:2041 | SpacecraftConfig.validate | `absorptivity is not None and 0.0 < absorptivity <= 1.0` | f"{}: thermal sensor {} needs params['absorptivity'] in (0, 1]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2044 | SpacecraftConfig.validate | `emissivity is not None and 0.0 < emissivity <= 1.0` | f"{}: thermal sensor {} needs params['emissivity'] in (0, 1]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2048 | SpacecraftConfig.validate | `measurement_fault_mode in _THERMAL_FAULT_MODES` | f"{}: thermal sensor {} has an unrecognized " f"params['measurement_fault_mode'] {} -- must be one of " f"{}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2055 | SpacecraftConfig.validate | `self.station_keeping is None and self.phasing_keeping is None` | f"{}: geo_station_keeping replaces station_keeping and phasing_keeping -- " "set only one of them" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2059 | SpacecraftConfig.validate | `len(facet_names) == len(set(facet_names))` | f"{}: facet names must be unique, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2064 | SpacecraftConfig.validate | `len(actuator_names) == len(set(actuator_names))` | f"{}: actuator names must be unique, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2067 | SpacecraftConfig.validate | `bool(actuator.kind) and bool(actuator.name)` | f"{}: every actuator needs kind and name" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2068 | SpacecraftConfig.validate | `name_error("actuator", actuator.name) is None` | f"{}: {}" | command-line.md:49-53 |
| scenario.py:2070 | SpacecraftConfig.validate | `actuator.kind in SUPPORTED_ACTUATOR_KINDS` | f"{}: actuator {} kind {} must be one of " f"{}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2075 | SpacecraftConfig.validate | `gsHat_B is not None and _is_direction_vector(gsHat_B)` | f"{}: reaction_wheel {} needs params['gsHat_B'] " "as a non-zero, finite 3-element body-frame spin-axis uni... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2079 | SpacecraftConfig.validate | `not rw_errors` | "; ".join(rw_errors) | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2092 | SpacecraftConfig.validate | `has_u_max_guard` | f"{}: reaction_wheel {} uses rw_type='custom' (the " "default) but has no params['u_max'] [N*m] -- rwFactor... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2102 | SpacecraftConfig.validate | `has_inertia` | f"{}: reaction_wheel {} uses rw_type='custom' (the " "default) but has no params['Js'] [kg*m^2] (spin-axis ... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2115 | SpacecraftConfig.validate | `not (actuator.params.get("Js") is not None and actuator.params.get("Omega_max") is not None and actuator.pa...` | f"{}: reaction_wheel {} uses rw_type='custom' (the " "default) with params['Js'] AND both params['Omega_max... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2126 | SpacecraftConfig.validate | `isinstance(max_momentum, (int, float)) and float(max_momentum) in options` | f"{}: reaction_wheel {} is a {}, which Basilisk " f"builds only with params['maxMomentum'] set to one of {}... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2153 | SpacecraftConfig.validate | `not missing` | f"{}: reaction_wheel {} has some but not all of " f"{} set -- motorThermal.MotorThermal hard-exits the whol... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2157 | SpacecraftConfig.validate | `_is_finite_number(actuator.params["motor_thermal_initial_temp_c"]) and actuator.params["motor_thermal_initi...` | f"{}: reaction_wheel {} needs " "params['motor_thermal_initial_temp_c'] above absolute zero (-273.15 C)" | No |
| scenario.py:2162 | SpacecraftConfig.validate | `0.0 < efficiency < 1.0` | f"{}: reaction_wheel {} needs " "0 < params['motor_thermal_efficiency'] < 1 (1.0 itself is rejected by " "m... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2166 | SpacecraftConfig.validate | `actuator.params["motor_thermal_ambient_resistance_w_c"] > 0` | f"{}: reaction_wheel {} needs " "params['motor_thermal_ambient_resistance_w_c'] > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2169 | SpacecraftConfig.validate | `actuator.params["motor_thermal_heat_capacity_j_c"] > 0` | f"{}: reaction_wheel {} needs " "params['motor_thermal_heat_capacity_j_c'] > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2174 | SpacecraftConfig.validate | `r_B is not None and len(r_B) == 3` | f"{}: thruster {} needs params['r_B'] as a 3-element " "body-frame location [m]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2178 | SpacecraftConfig.validate | `tHat_B is not None and len(tHat_B) == 3` | f"{}: thruster {} needs params['tHat_B'] as a 3-element " "body-frame thrust-direction unit vector [-]" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2181 | SpacecraftConfig.validate | `actuator.params.get("MaxThrust") is not None` | f"{}: thruster {} needs params['MaxThrust'] [N] -- " "simIncludeThruster.thrusterFactory()'s own default (0... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2187 | SpacecraftConfig.validate | `not thruster_errors` | "; ".join(thruster_errors) | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2190 | SpacecraftConfig.validate | `gtHat_B is not None and _is_direction_vector(gtHat_B)` | f"{}: magnetic_torque_rod {} needs params['gtHat_B'] as a " "non-zero, finite 3-element body-frame dipole-a... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2193 | SpacecraftConfig.validate | `_is_finite_number(actuator.params.get("max_dipole_a_m2")) and actuator.params["max_dipole_a_m2"] > 0` | f"{}: magnetic_torque_rod {} needs params['max_dipole_a_m2'] " "> 0 [A*m^2] (maximum commandable dipole mag... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2209 | SpacecraftConfig.validate | `False` | f"{}: actuators mix 'reaction_wheel' and 'thruster' kinds -- only one control " "-torque actuator type per ... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2220 | SpacecraftConfig.validate | `self.magnetic_momentum_management is not None` | f"{}: 'magnetic_torque_rod' actuators need magnetic_momentum_management set " "(no other role for them is s... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2230 | SpacecraftConfig.validate | `self.rf_link.antenna_boresight_b is not None or self.comms_pointing is not None` | f"{}: rf_link.antenna_pattern {} needs " "rf_link.antenna_boresight_b (or comms_pointing's): the gain towar... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2237 | SpacecraftConfig.validate | `len(set(array_names)) == len(array_names)` | f"{}: solar array names must be unique" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2238 | SpacecraftConfig.validate | `sum(array.mass_kg for array in self.solar_arrays) < self.dry_mass_kg` | f"{}: the solar arrays weigh as much as dry_mass_kg or more -- dry_mass_kg is the " "whole dry spacecraft, ... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2243 | SpacecraftConfig.validate | `self.power is not None or not self.data_handling.needs_power` | f"{}: data_handling draws power (an instrument's power_w or transmitter_power_w " "> 0) but this spacecraft... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2248 | SpacecraftConfig.validate | `self.power is not None or self.comms_pointing.comms_power_w == 0.0` | f"{}: comms_pointing.comms_power_w > 0 needs this spacecraft's power " "also set (nothing to draw that powe... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2254 | SpacecraftConfig.validate | `self.station_keeping is not None` | f"{}: phasing_keeping requires station_keeping to also be set on this spacecraft " "-- they share one physi... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2259 | SpacecraftConfig.validate | `self.station_keeping is not None` | f"{}: roe_formation requires station_keeping to also be set on this spacecraft " "-- the ROE controller fir... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2262 | SpacecraftConfig.validate | `self.phasing_keeping is None` | f"{}: roe_formation and phasing_keeping both control the same formation -- " "keep one of them" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2273 | SpacecraftConfig.validate | `"reaction_wheel" in actuator_kinds_present` | f"{}: momentum_dumping needs at least one 'reaction_wheel' actuator (momentum to " "dump) on this spacecraft" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2276 | SpacecraftConfig.validate | `"thruster" in actuator_kinds_present` | f"{}: momentum_dumping needs at least one 'thruster' actuator (desaturation " "hardware) on this spacecraft" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2287 | SpacecraftConfig.validate | `self.magnetic_momentum_management is None` | f"{}: momentum_dumping and magnetic_momentum_management are mutually exclusive " "RW-desaturation strategie... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2293 | SpacecraftConfig.validate | `"reaction_wheel" in actuator_kinds_present` | f"{}: magnetic_momentum_management needs at least one 'reaction_wheel' actuator " "(momentum to manage) on ... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2296 | SpacecraftConfig.validate | `"magnetic_torque_rod" in actuator_kinds_present` | f"{}: magnetic_momentum_management needs at least one 'magnetic_torque_rod' " "actuator (desaturation hardw... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2302 | SpacecraftConfig.validate | `self.fsw_mode is not None or self.comms_pointing is not None` | f"{}: navigation_error needs attitude flight software (a pointing mode or comms " "pointing): only then is ... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2309 | SpacecraftConfig.validate | `"thruster" in actuator_kinds_present` | f"{}: fuel_tank needs at least one 'thruster' actuator on this spacecraft to " "draw propellant from" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2315 | SpacecraftConfig.validate | `bool(self.vizard_model_path.strip())` | f"{}: vizard_model_path must not be blank" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2316 | SpacecraftConfig.validate | `len(self.vizard_model_offset_m) == 3` | f"{}: vizard_model_offset_m must have 3 elements" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2317 | SpacecraftConfig.validate | `len(self.vizard_model_rotation_deg) == 3` | f"{}: vizard_model_rotation_deg must have 3 elements" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2319 | SpacecraftConfig.validate | `len(self.vizard_model_scale) == 3` | f"{}: vizard_model_scale must have 3 elements" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2335 | GravityConfig.validate | `self.central_body in SUPPORTED_CENTRAL_BODIES + SMALL_BODY_CENTRAL_BODIES` | _body_problem("gravity.central_body", self.central_body, small_bodies=True) | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2337 | GravityConfig.validate | `isinstance(self.polyhedral_gravity, bool)` | "gravity.polyhedral_gravity must be true or false" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2338 | GravityConfig.validate | `not self.polyhedral_gravity or self.central_body in SMALL_BODY_CENTRAL_BODIES` | f"gravity.polyhedral_gravity needs a small body with a shape model as the central body " f"({}), not {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2341 | GravityConfig.validate | `isinstance(self.albedo, bool)` | "gravity.albedo must be true or false" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2342 | GravityConfig.validate | `not self.albedo or self.central_body in ALBEDO_MAPS` | f"gravity.albedo needs a central body with an albedo map ({}), " f"not {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2345 | GravityConfig.validate | `self.central_body_degree >= 0` | "gravity.central_body_degree must be >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2349 | GravityConfig.validate | `self.central_body_degree == 0 or field is not None` | f"gravity.central_body_degree > 0 (spherical-harmonics gravity) needs a central body with a " f"gravity fie... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2354 | GravityConfig.validate | `self.central_body_degree <= field[1]` | f"gravity.central_body_degree must be <= {} (the {} field's maximum)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2357 | GravityConfig.validate | `name in SUPPORTED_CENTRAL_BODIES` | _body_problem("gravity.third_body_perturbers entry", name) | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2379 | GroundStationConfig.validate | `name_error("ground station", self.name) is None` | name_error("ground station", self.name) or "" | command-line.md:49-53 |
| scenario.py:2380 | GroundStationConfig.validate | `-90.0 <= self.latitude_deg <= 90.0` | f"{}: latitude_deg must be in [-90, 90]" | No |
| scenario.py:2381 | GroundStationConfig.validate | `-180.0 <= self.longitude_deg <= 180.0` | f"{}: longitude_deg must be in [-180, 180]" | No |
| scenario.py:2382 | GroundStationConfig.validate | `0.0 <= self.min_elevation_deg < 90.0` | f"{}: min_elevation_deg must be in [0, 90)" | No |
| scenario.py:2383 | GroundStationConfig.validate | `self.system_noise_temp_k > 0` | f"{}: system_noise_temp_k must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2457 | SpaceWeatherConfig.validate | `self.source in SUPPORTED_SPACE_WEATHER_SOURCES` | f"space_weather.source {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2460 | SpaceWeatherConfig.validate | `bool(self.local_file_path)` | "space_weather.source is 'local_file' but local_file_path was not set" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2462 | SpaceWeatherConfig.validate | `self.atmosphere_model in ("nrlmsise00", "exponential")` | f"space_weather.atmosphere_model {} must be 'nrlmsise00' or 'exponential'" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2465 | SpaceWeatherConfig.validate | `_is_finite_number(self.forecast_percentile) and float(self.forecast_percentile) in SUPPORTED_FORECAST_PERCE...` | f"space_weather.forecast_percentile {} must be one of " f"{} (MSFC's published percentiles)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2498 | DispersionConfig.validate | `bool(self.spacecraft)` | "dispersion.spacecraft must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2499 | DispersionConfig.validate | `self.quantity in DISPERSION_QUANTITIES` | f"dispersion.quantity {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2502 | DispersionConfig.validate | `self.kind in allowed_kinds` | f"dispersion.kind {} for quantity {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2506 | DispersionConfig.validate | `isinstance(spread, dict) and spread` | f"{}: needs element_spread, e.g. {}}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2509 | DispersionConfig.validate | `key in ORBIT_ELEMENT_SPREAD_KEYS` | f"{}: element_spread key {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2511 | DispersionConfig.validate | `_is_finite_number(value) and value >= 0` | f"{}: element_spread[{}] must be a finite number >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2515 | DispersionConfig.validate | `isinstance(self.bounds, (list, tuple)) and len(self.bounds) == 2` | f"{}: kind {} needs bounds as a 2-element [lo, hi] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2520 | DispersionConfig.validate | `isinstance(self.bounds, (list, tuple)) and len(self.bounds) == 2 and all(_is_finite_number(value) for value...` | f"{}: bounds must be two finite numbers [lo, hi], got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2523 | DispersionConfig.validate | `self.bounds[0] <= self.bounds[1]` | f"{}: bounds [lo, hi] must have lo <= hi, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2527 | DispersionConfig.validate | `self.std_deviation is not None and _is_finite_number(self.std_deviation) and self.std_deviation >= 0` | f"{}: kind 'normal' needs std_deviation >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2530 | DispersionConfig.validate | `self.mean is not None and self.std_deviation is not None` | f"{}: kind 'normal' needs mean and std_deviation" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2532 | DispersionConfig.validate | `_is_finite_number(self.mean)` | f"{}: mean must be a finite number" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2533 | DispersionConfig.validate | `_is_finite_number(self.std_deviation) and self.std_deviation >= 0` | f"{}: std_deviation must be a finite number >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2536 | DispersionConfig.validate | `self.bounds is None or len(self.bounds) == 2` | f"{}: bounds, if given, must be a 2-element [lo, hi] list" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2538 | DispersionConfig.validate | `self.angle_std_deg is None or (_is_finite_number(self.angle_std_deg) and self.angle_std_deg >= 0)` | f"{}: angle_std_deg must be a finite number >= 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2575 | MonteCarloConfig.validate | `isinstance(value, int) and not isinstance(value, bool)` | f"monte_carlo.{} must be a whole number, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2577 | MonteCarloConfig.validate | `1 <= self.num_runs <= MAX_MONTE_CARLO_RUNS` | f"monte_carlo.num_runs must be between 1 and {}, got {}" | command-line.md / limitations.md (100 000 runs) |
| scenario.py:2579 | MonteCarloConfig.validate | `1 <= self.thread_count <= MAX_MONTE_CARLO_THREADS` | f"monte_carlo.thread_count must be between 1 and {}, " f"got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2639 | SimSettings.validate | `self.duration_days > 0` | "sim_settings.duration_days must be > 0" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2640 | SimSettings.validate | `self.duration_days <= self._MAX_DURATION_DAYS` | f"sim_settings.duration_days must be <= {} days (about 10 years)" | faq.md / capabilities.md (10 years) |
| scenario.py:2643 | SimSettings.validate | `self.dynamics_task_rate_s >= MIN_DYNAMICS_TASK_RATE_S` | f"sim_settings.dynamics_task_rate_s must be at least {} s" | command-line.md:49-53 |
| scenario.py:2645 | SimSettings.validate | `0.0 <= self.record_interval_s <= 86400.0` | "sim_settings.record_interval_s must be in [0, 86400] s (0 = every dynamics step)" | No |
| scenario.py:2647 | SimSettings.validate | `self.integrator in SUPPORTED_INTEGRATORS` | f"sim_settings.integrator {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2649 | SimSettings.validate | `isinstance(self.seed, int) and not isinstance(self.seed, bool) and 0 <= self.seed < 2 ** 31` | "sim_settings.seed must be a whole number from 0 to 2147483647" | No |
| scenario.py:2670 | FswExportRecord.validate | `bool(self.spacecraft)` | "fsw_exports[].spacecraft must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2671 | FswExportRecord.validate | `bool(self.path)` | f"fsw_exports[{}].path must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2672 | FswExportRecord.validate | `isinstance(self.config_digest, str) and re.fullmatch(r"[0-9a-f]{64}", self.config_digest) is not None` | f"fsw_exports[{}].config_digest must be 64 lower-case hex digits" | No |
| scenario.py:2674 | FswExportRecord.validate | `isinstance(self.parts, dict)` | f"fsw_exports[{}].parts must be a mapping" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2732 | Scenario._validate_small_body | `first <= start and end <= last` | f"gravity.central_body {}: its ephemeris covers {} to {}; " f"this run goes from {} to {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2735 | Scenario._validate_small_body | `not self.ground_stations` | f"gravity.central_body {}: ground stations are only for planets, remove them" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2739 | Scenario.validate | `bool(self.name)` | "scenario.name must not be empty" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2747 | Scenario.validate | `self.simulation_mode in SUPPORTED_SIMULATION_MODES` | f"scenario.simulation_mode {} must be one of {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2750 | Scenario.validate | `len(self.spacecraft) >= 1` | "scenario needs at least one spacecraft" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2751 | Scenario.validate | `len(self.spacecraft) <= MAX_SPACECRAFT` | f"scenario has {} spacecraft; at most {}" | command-line.md:49-53 |
| scenario.py:2753 | Scenario.validate | `len(self.description) <= MAX_DESCRIPTION_CHARS` | f"scenario.description is {} characters; at most {}" | command-line.md:49-53 |
| scenario.py:2756 | Scenario.validate | `len(names) == len(set(names))` | f"spacecraft names must be unique, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2763 | Scenario.validate | `key not in folded` | f"spacecraft names {} and {} differ only in case or " "punctuation; their output files would collide -- ren... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2771 | Scenario.validate | `len(exported) == len(set(exported))` | f"fsw_exports lists a spacecraft more than once: {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2774 | Scenario.validate | `not flexible or self.sim_settings.integrator in ("rkf45", "rkf78")` | f"{}: flexible solar arrays need an adaptive integrator " f"(rkf45 or rkf78) -- with {} a hinge oscillating... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2780 | Scenario.validate | `not sc.solar_arrays` | f"{}: solar arrays are set but scenario.simulation_mode is 'orbit_only' -- their " "flexing moves the attit... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2783 | Scenario.validate | `sc.fsw_mode is None` | f"{}: fsw_mode is set but scenario.simulation_mode is 'orbit_only' -- attitude " "control needs 'full_attit... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2786 | Scenario.validate | `not sc.sensors` | f"{}: sensors are set but scenario.simulation_mode is 'orbit_only' -- sensors " "need 'full_attitude' mode,... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2789 | Scenario.validate | `not sc.actuators` | f"{}: actuators are set but scenario.simulation_mode is 'orbit_only' -- " "actuators need 'full_attitude' m... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2792 | Scenario.validate | `not sc.facets` | f"{}: facets are set but scenario.simulation_mode is 'orbit_only' -- their " "drag and SRP depend on the at... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2795 | Scenario.validate | `sc.power is None` | f"{}: power is set but scenario.simulation_mode is 'orbit_only' -- a real solar" "-panel power budget needs... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2799 | Scenario.validate | `sc.rf_link is None or sc.rf_link.antenna_pattern == "fixed"` | f"{}: rf_link.antenna_pattern {} " "needs the simulated attitude 'full_attitude' mode provides -- use \"fix... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2804 | Scenario.validate | `len(gs_names) == len(set(gs_names))` | f"ground_station names must be unique, got {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2806 | Scenario.validate | `len(folded_gs) == len(set(folded_gs))` | f"ground_station names {} differ only in case; their output files would collide" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2813 | Scenario.validate | `target_gs in gs_names` | f"{}: fsw_params['target_ground_station'] {} is not one of " f"this scenario's ground_stations {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2818 | Scenario.validate | `sc.comms_pointing.target_ground_station in gs_names` | f"{}: comms_pointing.target_ground_station " f"{} is not one of this scenario's " f"ground_stations {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2826 | Scenario.validate | `target_body in spice_tracked` | f"{}: fsw_params['target_body'] {} needs a real SPICE " f"ephemeris -- it must be gravity.central_body or o... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2832 | Scenario.validate | `sc.phasing_keeping.chief_spacecraft in names` | f"{}: phasing_keeping.chief_spacecraft {} " f"is not one of this scenario's spacecraft {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2838 | Scenario.validate | `chief.orbit.type == "classical_elements"` | f"{}: phasing_keeping.chief_spacecraft {} must have a " f"'classical_elements' orbit (phasing needs its sem... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2845 | Scenario.validate | `self.gravity.central_body == "earth" and self.gravity.central_body_degree >= 2` | f"{}: phasing_keeping.control_law 'mean_oe' needs Earth's J2 in the " "dynamics -- set gravity.central_body... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2852 | Scenario.validate | `self.gravity.central_body in OPTICAL_NAVIGATION_BODIES` | f"{}: optical_navigation needs gravity.central_body to be one of " f"{} (the bodies Basilisk's pixelLineCon... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2856 | Scenario.validate | `"sun" in self.gravity.third_body_perturbers` | f"{}: optical_navigation needs 'sun' in gravity.third_body_perturbers " "(the image is used only on the lit... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2861 | Scenario.validate | `self.gravity.central_body in SMALL_BODY_CENTRAL_BODIES and self.gravity.polyhedral_gravity` | f"{}: landmark_navigation needs a small body ({}) " "as gravity.central_body with gravity.polyhedral_gravit... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2864 | Scenario.validate | `"sun" in self.gravity.third_body_perturbers` | f"{}: landmark_navigation needs 'sun' in gravity.third_body_perturbers " "(a landmark is seen only in sunli... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2869 | Scenario.validate | `sc.roe_formation.chief_spacecraft in names` | f"{} is not one of this scenario's spacecraft {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2874 | Scenario.validate | `chief.orbit.type == "classical_elements"` | f"{} must have a 'classical_elements' orbit, not {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2876 | Scenario.validate | `(chief.orbit.eccentricity or 0.0) <= ROE_MAX_CHIEF_ECCENTRICITY` | f"{} must be near-circular (eccentricity at most " f"{}), not {}" | roe-formation.md |
| scenario.py:2879 | Scenario.validate | `0.0 < (chief.orbit.inclination_deg or 0.0) < 180.0` | f"{} must be inclined: the relative inclination vector needs a node" | No |
| scenario.py:2883 | Scenario.validate | `self.gravity.central_body == "earth" and self.gravity.central_body_degree >= 2` | f"{}: roe_formation needs Earth's J2 in the dynamics -- set " "gravity.central_body to 'earth' and central_... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2890 | Scenario.validate | `self.gravity.central_body not in SMALL_BODY_CENTRAL_BODIES` | f"a run around {} is one simulation, at most {} " "days (sim_settings.duration_days; longer, segmented runs... | limitations.md:20 |
| scenario.py:2894 | Scenario.validate | `not runs_sequence(self.mission_sequence)` | f"sim_settings.duration_days is over {} days, which a mission sequence " "cannot run -- shorten the run or ... | limitations.md (100 days) |
| scenario.py:2898 | Scenario.validate | `sc.phasing_keeping is None` | f"{}: phasing_keeping runs at most {} days " "(sim_settings.duration_days) -- shorten the run" | limitations.md (100 days) |
| scenario.py:2901 | Scenario.validate | `sc.roe_formation is None` | f"{}: roe_formation runs at most {} days " "(sim_settings.duration_days) -- shorten the run" | limitations.md:176 |
| scenario.py:2904 | Scenario.validate | `sc.optical_navigation is None` | f"{}: optical_navigation runs at most {} days " "(sim_settings.duration_days; its filter is not carried bet... | limitations.md:41 |
| scenario.py:2926 | Scenario.validate | `sun_tracked` | "a spacecraft has power, station_keeping, enable_srp, or comms_pointing configured, " "but 'sun' is not one... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2936 | Scenario.validate | `not thermal or sun_tracked` | f"{}: thermal sensor {} needs the Sun's position -- add " "'sun' to gravity.third_body_perturbers" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2950 | Scenario.validate | `sc.orbit.type != "tle"` | f"{}: a TLE orbit describes an Earth orbit, but gravity.central_body is " f"{} -- give the orbit as cartesi... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2953 | Scenario.validate | `not any(sensor.kind == "magnetometer" for sensor in sc.sensors)` | f"{}: has a 'magnetometer' sensor, but gravity.central_body is " f"{}, not 'earth' -- magneticFieldWMM (the... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2967 | Scenario.validate | `sc.magnetic_momentum_management is None` | f"{}: has magnetic_momentum_management configured, but gravity.central_body " f"is {}, not 'earth' -- magne... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2971 | Scenario.validate | `sc.geo_station_keeping is None` | f"{}: geo_station_keeping is Earth-only (it plans east-west burns from " f"Earth's J22 term), but gravity.c... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2976 | Scenario.validate | `not self.gravity.albedo or sun_tracked` | "gravity.albedo needs 'sun' in gravity.third_body_perturbers: the reflected light is the Sun's" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2983 | Scenario.validate | `dispersion.spacecraft in names` | f"monte_carlo dispersion.spacecraft {} is not one of " f"this scenario's spacecraft {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2989 | Scenario.validate | `self.simulation_mode == "full_attitude"` | f"{}: attitude is not simulated in simulation_mode {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2992 | Scenario.validate | `sc.enable_drag and not sc.facets` | f"{}: needs enable_drag and no facets (facets carry their own coefficients)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:2995 | Scenario.validate | `sc.enable_srp and not sc.facets` | f"{}: needs enable_srp and no facets (facets carry their own coefficients)" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:3009 | Scenario.validate | `not command_errors` | "; ".join(command_errors) | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:3011 | Scenario.validate | `not order_errors` | "; ".join(order_errors) | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:3023 | Scenario.validate | `ref.name in known` | f"{}: {} {} is not one of this scenario's " f"{} {}" | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:3047 | Scenario._validate_sequence_time | `days <= limit_days` | f"mission_sequence: propagate.stop_epoch_utc {} is " f"{} days after the scenario epoch; a Mission Sequence... | n/a (structural/enum rule; enum lists are in ICD comments where given) |
| scenario.py:3055 | Scenario._validate_sequence_time | `total_days <= limit_days` | f"mission_sequence: its fixed-duration propagates add up to {} days; a Mission " f"Sequence runs at most {}... | n/a (structural/enum rule; enum lists are in ICD comments where given) |

### (b) The CLI (`spacemissionstudio/cli.py`)

Entry point `spacemissionstudio = "spacemissionstudio.cli:main"` (`pyproject.toml`, `[project.scripts]`). `main()` configures logging first (`cli.py:1461`), maps `KeyboardInterrupt` to 130, an unreported `OSError` to 3, and any other exception to `EXIT_INTERNAL_ERROR = 4` with the traceback in the log file (`cli.py:1464-1485`). The generated `compliance/docs/ICD_cli.md` lists all 22 commands below; `docs/user-manual/command-line.md` is the user guide.

#### B.1 Commands, options, defaults, and what is printed

| Command (cli.py) | Options and defaults (cli.py line) | What it writes / prints | Derivation shown? | Fixed choices |
|---|---|---|---|---|
| `validate` (82) | `scenario` | `OK: name -- N spacecraft, schema version V, epoch E`; NOTE for script blocks; `WARNING:` plausibility checks (`engine.scenario_checks`) | Version printed is post-migration (A finding 7) | - |
| `run` (187) | `--out-dir results` (1201); `--oem` off; `--oem-stride 1` (1204); `--oem-interpolation hermite` (1206, choices hermite/lagrange, degree 7 fixed in `engine/ccsds_odm.py:904`); `--vizard-save-file None`; `--vizard-live-stream`; `--vizard-camera-target None` (central body); `--vizard-no-orbit-lines`; `--vizard-trail`; `--vizard-ground-tracks`; `--allow-scripts` | one CSV per series + `provenance.json` (`engine/results.py:286-313`), optional `<sc>.oem`, `events.csv`, `command_summary.csv`; prints file list, `data:` lines, event count, `WARNING:` lines, stale-file warning (`cli.py:178-184`), station-keeping and constant-thrust summaries | Summaries print final-sample delta-V and `propellant_kg - final remaining` (`cli.py:287-289`, `:320-322`) with no source series or provenance on stdout | OEM frame EME2000, time system UTC, `OBJECT_ID "UNKNOWN"` (`engine/ccsds_odm.py:901-906`); no copy of the scenario is written to `--out-dir` |
| `monte-carlo` (327) | `--archive-dir monte_carlo_results` (1228); `--overwrite`; `--allow-scripts` | Basilisk Controller archive (`run*.json`, `run*.data`, `MonteCarlo.data`), `batch_results.json/.npz` (`engine/monte_carlo_results.py:100-119`), `archive.provenance.json` (`cli.py:350`) | summary lines | exits **4** when some runs fail (`cli.py:364-366`), the same code ICD-02 reserves for an internal error (`compliance/docs/ICD.md:58`, `cli.py:77-79`) |
| `lifetime` (442) | `--spacecraft` first; `--deorbit-perigee-km None`; `--max-years 30` (0, 100] (1243, `_max_years_arg` 513-519); `--forecast-percentile 50` choices 95/50/5 (1245); `--drag-coeff 2.2` or `own` (1247) | re-entry date, years, 5-year / 25-year verdicts, warnings | **Does not print the drag coefficient or percentile used.** By default the spacecraft's own `drag_coeff` and the scenario's `space_weather.forecast_percentile` are both *replaced* (`cli.py:455-458`, `engine/lifetime.py:590`); documented in `lifetime-and-budget.md:25` and the `--help` text, not in the output | 5 and 25 years (`lifetime.ZERO_DEBRIS_YEARS`, `IADC_YEARS`, `cli.py:472`) |
| `model` (371) | `--spacecraft`; `--apply`; `--export-obj PATH` | parts, mass properties, facets, stale fields; `--apply` rewrites the scenario file (`cli.py:431-438`) | yes (principal summary) | `.obj` body frame, metres, +z up (`cli.py:430`) |
| `budget` (554) | `--spacecraft` first; `--run`; `--launch-delays` xor `--altitudes [auto or KM,..]` (150..2000 km, `cli.py:532-541`) | budget table with `margin` and `source` per row (`cli.py:585-589`) | **source column shown** (good); no provenance on stdout | launch delays up to 5 years (`cli.py:596`) |
| `kernels-status` (615) | none | per-file OK/FAIL, path, mtime | - | **downloads missing support data** through Basilisk `get_path` (`engine/kernels.py:139-164`); the help says "fetch/check" (`cli.py:1276`) |
| `earth-orientation` (632) | `--fetch` xor `--import FILE..` xor `--rollback` | installed files with size, last datum, SHA-256 prefix, source | yes | NAIF URL fixed (`engine/earth_orientation.py:63`) |
| `small-bodies` (663) | `--fetch` xor `--import FILE` | ephemeris + shape status, SHA-256 prefix | yes | Eros only (`cli.py:669`) |
| `ccsds-validate` (707) | `files..` | conformance errors/warnings with clause | yes | 500 MB read limit (`cli.py:694`) |
| `ccsds-export` (729) | `--out` required | `<sc>.opm` (or `.omm` for TLE) with `COMMENT` provenance lines (`cli.py:748`, `:766-767`) | provenance = tool/Basilisk version, scenario SHA-256, time (`output_provenance.py:98-104`) | `OBJECT_ID "UNKNOWN"`, `EME2000`, `UTC` (`cli.py:760-761`); Earth GM fixed 398600.436 km^3/s^2 (`engine/ccsds_odm.py:51`), other bodies' GM from Basilisk (`cli.py:788-792`) |
| `ccsds-import` (795) | `message`, `scenario`, `--spacecraft` required, `--set-epoch`, `--out` (default **overwrite**) | rewrites the scenario's orbit (and epoch with `--set-epoch`) | notes printed | **no record of the source message (name/hash) is kept in the scenario** (`cli.py:821-824`) |
| `export-fsw` (831) | `--spacecraft`, `--out` required; `--steps None` (help: 200); `--overwrite`; `--record` | standalone C project + `manifest.json` (SHA-256 of every file, config digest, Basilisk version/revision, `exported_utc`; `fsw_export/generate.py:845-870`) | yes | - |
| `fsw-status` (862) | `scenario` | CURRENT/STALE/MODIFIED/MISSING per record | yes, names changed setting groups (`fsw_export/records.py:105-108`) | exits **2** when not current (`cli.py:878-880`), a code ICD-02 assigns to "missing component/usage error" |
| `sil` (883) | `--spacecraft`, `--binary` required; `--transport auto` (1334); `--deadline-ms None`; `--step-timeout 10` s; `--handshake-timeout 30` s; `--report`; `--residuals-csv`; `--max-error None` | summary lines; JSON report (binary SHA-256, FSW and scenario digests, `sil/report.py:64-90`) | yes | exits **2** on `--max-error` failure (`cli.py:914-917`), again overloading ICD-02's code 2 |
| `spaceweather-resolve` (921) | `scenario` | resolved CSV path and source file, warnings | yes | - |
| `generate-constellation` (944) | `--total-satellites`, `--planes`, `--phasing-factor`, `--altitude-km`, `--inclination-deg` required; `--pattern delta`; `--eccentricity 0`; `--arg-periapsis-deg 0`; `--raan-offset-deg 0`; `--name-prefix sat`; `--append`; `--template-spacecraft` | new scenario at `--out` | - | central body always from the scenario (`cli.py:966-973`); J2 from the scenario's gravity degree (`cli.py:979`) |
| `generate-phasing-formation` (996) | chief, follower name required; `--radial-km 0`, `--cross-track-km 0`; `--reconfiguration-interval-days 90`; `--tolerance-fraction 0.10`; `--restore-tolerance-fraction 0.02`; `--correction-window-days 3`; `--max-drift-days 90`; `--max-delta-semi-major-axis-km 3`; `--station-keeping-target-altitude-km` derived; `--station-keeping-deadband-km 2.0`; `--thrust-n 0.05`; `--isp-s 1500`; `--propellant-kg 5.0`; `--eclipse-sunlit-threshold 0.99`; `--min-on-time-s 0`; `--control-law drift_orbit` (1389-1418) | new scenario | - | **CLI-only defaults** (thrust 0.05 N, propellant 5 kg, deadband 2 km) differ from schema defaults (e.g. `ConstantThrustConfig.thrust_n 0.01`) and are written into the generated file, so they are visible afterwards |
| `generate-roe-formation` (1080) | `--roe a_da,..` xor `--safe along,radial,cross[,phase]` (phase default 90 deg, `cli.py:1107`); `--control-law impulsive` | new scenario, closest approach | yes (`cli.py:1124-1127`) | values rounded to 9 decimals (`cli.py:1106`) |
| `gui` (1131) | none | starts GUI | - | - |
| `-V/--version` (1191) | - | tool, Basilisk (+ qualified note), Python + platform (`cli.py:1157-1172`) | - | - |

#### Findings (b)

* **Exit codes are overloaded against the ICD.** ICD-02 defines 0/1/2/3/4 (`compliance/docs/ICD.md:58`). `monte-carlo` returns 4 for failed runs (`cli.py:366`), `fsw-status` and `sil --max-error` return 2 for a stale export / a residual failure (`cli.py:879`, `:917`), `kernels-status` returns 1 for a missing file (`cli.py:629`). A script cannot tell a fault from a failed batch by exit code.
* **Analysis outputs printed to stdout carry no provenance** (`lifetime`, `budget`, the `run` summaries), although `output_provenance.scenario_record()`'s docstring lists "a budget, a lifetime" as outputs it serves (`output_provenance.py:87-88`); it is used for them only in the GUI budget CSV (`gui/budget_widget.py:559`).
* **No CLI command downloads, imports or rolls back space weather**; that exists only in the GUI (startup dialog `gui/startup_fetch_dialog.py:165-171`, Reference data page), although the engine functions exist (`engine/spaceweather.py:253`, `:354`, `:368`).
* **No CLI command shows the scenario hash, diffs two scenarios or two provenance records**; `engine/scenario_diff.py` is used only by the GUI (`gui/compare_widget.py`, `gui/results_widget.py`).

### (c) Inputs and outputs exchanged with files, network, environment and other programs

"Provenance recorded?" = whether the source/version/hash of the input is written into a result or record. "Change detected?" = whether the tool notices that the input changed since it was recorded/installed.

| # | Exchange | Direction | Format | Path convention | Producer / consumer | Provenance recorded? | Change detected? | Visible to user? |
|---|---|---|---|---|---|---|---|---|
| 1 | Scenario file | in/out | UTF-8 JSON, indent 2, insertion order (`scenario.py:3289-3291`) | anywhere; templates in `spacemissionstudio/scenarios/templates/` (`gui/load_scenario_widget.py:96`) | GUI, CLI (`validate`, `run`, `model --apply`, `ccsds-import`, `export-fsw --record`, `generate-*`), engine | Run provenance holds its SHA-256 of `json.dumps(to_dict(), sort_keys=True)` (`output_provenance.py:80-84`) - **not the hash of the file bytes**, computed after migration | No (no stored hash/mtime) | yes |
| 2 | Scenario migration | in | in-memory rewrite | - | `schema/migrations.py:110-148` | no | n/a | **no** (A finding 7) |
| 3 | Results CSV | out | CSV, header `time_s,<col>_<unit>`, values `%.9g` (`engine/results.py:183-196`) | `<out>/<series>.csv` via `output_path` (`results.py:42-51`) | `ResultSet.export_csv` (CLI, GUI) | no (separate `provenance.json`) | n/a | yes |
| 4 | `provenance.json` | out | JSON (`RunProvenance.to_dict`, `engine/results.py:60-140`) | `<out>/provenance.json` (`results.py:304-309`) | `SimulationService._extract_results` (`engine/service.py:2275-2295`) | it is the record: tool & Basilisk versions, qualified flag, `run_started_utc`, integrator, step, integrator tolerances, `rng_seed` + per-model `rng_seeds`, dependency versions (bsk, numpy, sgp4, pyerfa, PySide6, plotly + Python + platform: `dependencies.py:40,68-77`), scenario SHA-256, `data_files`, time scales, frames, transformations, `series_frames` | n/a | yes (also a GUI popover, `gui/run_history_view.py:120-130`) |
| 5 | `events.csv` | out | CSV, times `%.3f` s + UTC, quantities `repr` (`engine/events.py:323-352`) | `<out>/events.csv` (`cli.py:158-162`) | derived from recorded series (`events.py:18-28`) | no (covered only by sitting next to `provenance.json`; comment `cli.py:158`) | n/a | yes |
| 6 | `command_summary.csv` | out | CSV long format (`results.py:347-372`) | `<out>/command_summary.csv` | MissionEngine report commands | no | n/a | yes |
| 7 | CCSDS OEM | out | KVN 3.0, shortest round-trip floats (`ccsds_odm.py:636-648`) | `<out>/<sc>.oem` | `oem_from_result` (`ccsds_odm.py:878-912`) | header `COMMENT`s = `RunProvenance.summary_lines()` (`ccsds_odm.py:908-910`); segment comment hard-codes "Planetary ephemeris DE430" (`:906`) | n/a | yes |
| 8 | CCSDS OPM/OMM export | out | KVN | `--out/<sc>.opm|.omm` | `cmd_ccsds_export` | `COMMENT` tool/Basilisk version, scenario SHA-256, time (`cli.py:748,766-767`) | n/a | yes |
| 9 | CCSDS OPM/OMM import | in | KVN, <= 500 MB (`cli.py:694-704`) | user path | `orbit_ic_from_odm` (`ccsds_odm.py:915-941`) | **no** (the orbit replaces the old one; the message name/hash is not stored) | no | notes printed |
| 10 | TLE | in | two 69-column lines in the scenario (`OrbitIC.tle_line1/2`) | pasted in GUI / OMM | `engine/tle.py` (SGP4 WGS-72, TEME -> EME2000 via ERFA, `tle.py:19-48`) | the TLE text itself is in the scenario; sgp4 and pyerfa versions in `dependency_versions` | n/a | yes |
| 11 | Basilisk support data (SPICE naif0012, de430, de-403-masses, pck00010; GGM03S, GGM2B; WMM; albedo maps) | in (download only when the user asks) | binary/text | Basilisk pooch cache (`dataFetcher.POOCH.abspath`) or local support path (`engine/kernels.py:183-188`) | `kernels.cached_path` at run time | `data_files["spice:<f>"]`, `gravity_field`, `magnetic_field`, `albedo_map` (`service.py:813,840,971,1207`): path, size, SHA-256 **only if <= 32 MB** (`dependencies.py:44,80-100`) -> de430.bsp (~114 MB, `reference_data.py:70`) is recorded by size only | **yes**: checked against Basilisk's pooch registry checksum, cached per (path, size, mtime) (`kernels.py:192-206`) | Settings > Reference data (`reference_data.py:106-127`), `kernels-status` |
| 12 | Space weather (CelesTrak SW-All) | in | CSV/TXT | bundled `spacemissionstudio/data/spaceweather/SW-All.txt` (`spaceweather.py:137`); downloaded `~/.cache/SpaceMissionStudio/spaceweather/SW-All.csv` + `.manifest.json` + `.previous` (`:109`, `:307-352`); or `local_file_path` | `spaceweather.resolve_for` | `data_files["space_weather"]` = path, size, SHA-256 of the CelesTrak file (`service.py:1102`); download manifest holds source URL, SHA-256, dates (`spaceweather.py:337-341`) | **no checksum exists upstream** ("CelesTrak publishes no checksums", `:320-321`); `source: "bundled"` silently uses **whichever of bundled/downloaded has the later observed day** (`spaceweather.py:631-652`) | stale flag after 60 days (`reference_data.py:36,146-152`); warnings name the file |
| 13 | MSFC solar-activity prediction | in | text table | bundled `data/spaceweather/oct2026f10-prd.txt` (`spaceweather.py:141`) or `msfc_file_path` | `_msfc_or_none` (`spaceweather.py:665-669`) | **not in `data_files`** (only the CelesTrak file is recorded, `service.py:1102`); its name appears in a warning string only when used (`spaceweather.py:798-799`) | no | Reference data lists it with SHA-256 (`reference_data.py:154-158`) |
| 14 | Resolved space-weather CSV (derived) | out/in | Basilisk CSV | `<cache>/real_<stem>_<mtime>[_msfc..]_p<pct>_<from>_<to>.csv` (`spaceweather.py:804-808`) | written once, re-used when row count matches (`:808-809`) | keyed by source **mtime**, not content hash | partly (row count only) | no |
| 15 | Earth orientation PCKs (NAIF) | in (download/import on request) | DAF/PCK + `.cmt` | `~/.cache/SpaceMissionStudio/earth_orientation/` + `manifest.json`, else `<sys.prefix>/share/spacemissionstudio/earth_orientation` (`earth_orientation.py:75-78`) | `earth_orientation.installed/covering`, loaded in `service.py:857-873` | `data_files["earth_orientation:<f>"]` with path, size, SHA-256, source, last datum **copied from the install manifest** (`service.py:869-871`), not re-hashed at run time | **size only** (`earth_orientation.py:159`) | Reference data, `earth-orientation`; frame used (ITRF93 vs IAU_EARTH) in `provenance.frames` |
| 16 | Small-body SPK (Eros) | in | DAF/SPK | `~/.cache/SpaceMissionStudio/small_bodies/` (`small_bodies.py:57`) | `small_bodies.installed` (`:153-167`) | path, size, SHA-256, source from the manifest (`service.py:849-851`) | SHA-256 against a pinned value **at install only** (`small_bodies.py:133-142`, `:171`); at use **size only** (`:165`), although the module docstring says "checked against the size and SHA-256 ... before it is used" (`:36-37`) | Reference data |
| 17 | Shape model `eros007790.tab` | in | text | Basilisk support data | `polyhedron.load` (`service.py:799-800`) | `data_files["shape_model"]` (`service.py:800`) | registry checksum via `cached_path` (`small_bodies.py:241-246`) | yes |
| 18 | 3D model `.obj` meshes | in | Wavefront OBJ/MTL | `ModelMeshConfig.path` absolute or relative to the scenario folder (`model3d/model.py:107-113`) | `model3d.derive` | `ModelMeshConfig.sha256` stored in the scenario at import (`scenario.py:1652`); Vizard runs also add `data_files["model_mesh:..."]` (`service.py:697-699`) | **yes**: warning "changed since it was imported" (`model3d/model.py:170-171`) | yes |
| 19 | Mass-property import | in | JSON/CSV | user path | `model3d/mass_import.py` | `source_file`, `source_sha256` stored (`scenario.py:1742-1743`, `mass_import.py:196`) | not re-checked (no comparison found) | yes |
| 20 | Device catalog presets | in (code) | Python data with datasheet URLs (`engine/device_catalog.py:102-120`) | - | GUI "Apply device values" (`gui/sensor_actuator_editor.py:679-686`) | **no**: only the values land in `params`; which catalog entry was applied is not stored | n/a | card in the dialog |
| 21 | Vizard `.bin` | out | Basilisk `vizSupport` format | `--vizard-save-file`; a non-`.bin` path becomes `<dir>/_VizFiles/<stem>_UnityViz.bin` (`engine/vizard.py:593-598`) | `enable_vizard` (`vizard.py:1084-1085`) | no | n/a | yes |
| 22 | Vizard live stream | out | TCP (vizInterface) | local | `vizard.py:1085` | no | n/a | yes |
| 23 | Vizard model files (temp) | out | OBJ | temp folder `spacemissionstudio_vizard_models_<pid>-*` (`temp_folders.py:45`, `service.py:690`) | `write_model_for_vizard` | mesh hashes in `data_files` | n/a | no |
| 24 | Vizard program download | in (network, on request) | zip, unversioned URL `https://hanspeterschaub.info/bskFiles/Vizard_*.zip` (`gui/vizard_launcher.py:161-164`) | `~/.cache/SpaceMissionStudio/vizard` (`:166`) | GUI only | size + SHA-256 computed after download and shown (`:256`, `:285-296`), **not compared with any expected value**; Vizard version not recorded in run provenance | no | status line |
| 25 | Flight-software export | out | C project, `manifest.json`, `capture.json`, ICD/TRACEABILITY/README.md | `--out` folder | `fsw_export/generate.py:840-889` | **best in the tool**: config digest, Basilisk version + revision, `exported_utc`, SHA-256 of every file (`generate.py:845-870`); `FswExportRecord` in the scenario (`scenario.py:2653-2674`) | **yes**: STALE (settings changed, names the groups) / MODIFIED (file hash mismatch) (`fsw_export/records.py:81-109`) | `fsw-status`, GUI badge |
| 26 | SIL child process | out/in | SIL contract frames over unix socket/TCP (`ICD.md` ICD-10) | binary path; log in temp `sms-sil-log-*` (`sil/runner.py:233-235`) | `sil/runner.py` | report holds binary SHA-256, FSW + scenario digests, contract version (`sil/report.py:64-90`); **no tool/Basilisk version or timestamp** in the report | n/a | yes |
| 27 | SIL environment | out | the parent's whole `os.environ` + `SMS_SIL_TOKEN` (`sil/runner.py:237-238`, `sil/contract.py:51`) | - | child process | no | n/a | no |
| 28 | Monte Carlo archive | out | Basilisk Controller pickles + JSON per run; `batch_results.json/.npz` (`monte_carlo_results.py:100-119`); `archive.provenance.json` | `--archive-dir` (`cli.py:350`, `gui/run_worker.py:263-264`) | `run_monte_carlo` (`engine/monte_carlo.py:447-545`) | `scenario_record`: tool/Basilisk/dependency versions, scenario SHA-256, time (`output_provenance.py:86-95`); **no data files, no integrator, no seeds** (per-run drawn values and RNG seeds are in Basilisk's `runN.json`) | n/a | yes |
| 29 | Run store | out/in | `run.json` (scenario as run, provenance, warnings, series metadata) + `series.npz` (`engine/run_store.py:18-30`, `:115-153`) | `~/.spacemissionstudio/runs/run-NNNN-<time>/` (`:74-76`) | GUI only (`gui/run_history.py`, `gui/main_window.py`) | yes (whole scenario + provenance) | n/a | Run history; **pruned automatically** to 20 runs / 2 GiB (`run_store.py:63-64`, `:235-249`), logged only |
| 30 | Autosave / recovery | out/in | JSON `{original_path, saved_at_utc, scenario}` (`gui/autosave.py:92-107`) | `~/.spacemissionstudio/autosave/recovery.json` (`:71-72`) | GUI timer, migrated on read (`:160-162`) | timestamp only | n/a | restore prompt |
| 31 | Settings | out/in | INI (QSettings) | `~/.spacemissionstudio/settings.ini` (theme, UI scale, reduce motion, recent files, last export per kind: `gui/theme/apply.py:59-105`, `gui/recent_files.py:36-55`, `gui/export_log.py:40-57`), `~/.spacemissionstudio/layout.ini` (`gui/main_window.py:1089`, `gui/results_widget.py:443`); Vizard path in the platform-default QSettings (`gui/vizard_launcher.py:351-377`) | GUI | n/a - **no setting found that changes a computed number** (keys listed by grep of `setValue`/`value`) | n/a | Settings page |
| 32 | Log files | out | text, DEBUG and up | `~/.spacemissionstudio/logs/spacemissionstudio_<UTC>_<pid>.log`, newest 100 kept (`logging_setup.py:76`, `:120`, `:176-188`) | CLI and GUI | timestamps; no run linkage (the run's provenance does not name the log file) | n/a | path printed on start ("Logging to", `:171`) |
| 33 | Temporary folders | out | various | system temp, prefixes `spacemissionstudio-plot-`, `sms-compare-`, `spacemissionstudio_model_view_`, `spacemissionstudio-icons-`, `spacemissionstudio_vizard_models_` + pid (`temp_folders.py:41-46`); left-overs removed at GUI start, untraced ones after 1 day (`:50`) | GUI/engine | n/a | n/a | no |
| 34 | Basilisk import-time GitHub HEAD request | out (network) | HTTPS | `github.com/AVSLab/basilisk/releases/tag/<v>` | Basilisk `dataFetcher` import; **blocked locally** by pointing proxy variables at a closed port during that import (`spacemissionstudio/_offline.py:18-35`, `:62-75`); consequence per that docstring: Basilisk falls back to its `develop` download URL for later consented downloads (unverified against Basilisk) | n/a | n/a | no |
| 35 | Network downloads (consented) | in | HTTPS, `urllib` with a browser User-Agent (`spaceweather.py:127`), size caps 100/128/16 MB (`spaceweather.py:132`, `earth_orientation.py:67`, `small_bodies.py:55`) | CelesTrak, NAIF, Basilisk repo, hanspeterschaub.info (`reference_data.py:64-82`) | user-started only (startup prompt, Reference data, CLI `--fetch`, `kernels-status`) | manifests (except support data, which rely on the pooch registry) | see rows 11-16 | consent text lists source and size (`reference_data.py:64-82`) |
| 36 | Environment variables written | out | - | `QTWEBENGINE_CHROMIUM_FLAGS` (only if unset, `gui/webengine_setup.py:45-50`), `QT_SCALE_FACTOR` (`gui/app.py:41-47`), proxy vars during one import (`_offline.py:62-75`), `SMS_SIL_TOKEN` (row 27) | - | none read to change a result (grep `os.environ|getenv`); Basilisk/pooch environment variables not inspected (**unverified**) | - | no |
| 37 | Plot exports PNG / SVG | out | PNG `tEXt` chunk with the full provenance JSON; SVG `<metadata>` (`output_provenance.py:43-77`, `gui/results_widget.py:1965-1973`) | user path | GUI | yes, embedded | n/a | yes |
| 38 | Other GUI exports (event timeline, mission output, budget CSV) | out | CSV + `<file>.provenance.json` sidecar, or quoted provenance lines | user path | `gui/event_timeline_widget.py:718`, `gui/mission_output_widget.py:326`, `gui/budget_widget.py:559` | yes | n/a | yes |

#### Findings (c)

* **Provenance coverage is good for simulation outputs and very good for FSW exports**; it is weakest for: CLI stdout analyses (lifetime, budget, run summaries), the SIL report (no tool version or time), the Monte Carlo archive (no reference data, no integrator), the CCSDS import (source not kept) and Vizard (program version not recorded).
* **Data-file change detection is uneven**: Basilisk support data is checksum-verified on every run (registry), meshes are hash-compared, FSW exports are hash-compared; Earth-orientation and Eros kernels are checked by size only after installation; CelesTrak data cannot be verified at all (no upstream checksum) and the "bundled" source silently follows the newest download.
* **Large files are recorded by size only** (`dependencies.py:42-44`), so `provenance.json` cannot prove which `de430.bsp` was used (the run did verify it against the registry, but that fact is not recorded).

### (d) Reproducibility: can a colleague re-run from the exported files alone?

**No, not from the CLI `run` output folder alone.** `--out-dir` holds CSVs, `events.csv`, optional OEM/`command_summary.csv` and `provenance.json` (`cli.py:134-184`); it does **not** hold the scenario itself. `provenance.json` holds only the scenario's SHA-256 (`engine/results.py:110`). The GUI's run store does keep the scenario as run (`engine/run_store.py:115-134`), but only in the user's home folder, pruned to 20 runs (`:63`, `:235-249`).

#### D.1 What is recorded (and where)

| Item | Recorded? | Where |
|---|---|---|
| SpaceMissionStudio version | yes | `provenance.spacemissionstudio_version` (`engine/results.py:79`) |
| Basilisk version, qualified version, qualified flag | yes | `results.py:80,107-108`; `dependencies.py:37` (2.12.0) |
| Basilisk git revision / build | **no** in runs (only in FSW exports: `fsw_export/generate.py:851`) | - |
| Python version, platform (`sys.platform`, machine), numpy, sgp4, pyerfa, PySide6, plotly | yes | `dependencies.py:68-77` |
| Other libraries (pooch, which verifies data; OS version; CPU; compiler) | **no** | - |
| Run start time | yes | `results.py:81` |
| Integrator, step, adaptive tolerances | yes | `results.py:82-87`; values `service.py:117-118` |
| Seeds | `sim_settings.seed` + every derived model seed (`results.py:91-92`, `engine/seeds.py:51-68`); nav/camera seeds are in the scenario | provenance + scenario |
| Scenario | **hash only**, of the canonical sorted-key JSON after migration (`output_provenance.py:80-84`), so `sha256sum scenario.json` will never match it; no CLI command prints it | `results.py:110` |
| Reference data files | path, size, SHA-256 (<= 32 MB) per file used | `results.py:111`; collected in `service.py:800-1207` |
| MSFC prediction file | **no** | row 13 |
| Earth frame actually used, frame/time definitions | yes | `results.py:116-119`, `engine/frames.py:54-74`, `engine/time_system.py:168-186` |
| Engine default values not in the scenario file (open `params` dicts, scaled MRP gains, Basilisk module defaults, factory built-in RW/thruster parameter sets) | **no** | A finding 2, (h) |
| Warnings of the run | yes in the run store (`run_store.py:134`), printed by CLI to stderr (`cli.py:167-168`); **not in `provenance.json`** | - |

#### D.2 Specific reproducibility gaps

1. **Runs longer than 100 days record the wrong scenario hash and incomplete seeds.** `long_run.run_segmented` builds each segment from a modified deep copy (epoch moved, `duration_days` set to the segment length, `space_weather` replaced by a `local_file` pointing at a derived CSV: `engine/long_run.py:247-258`, `:120-135`) and the merged result takes `provenance=part.provenance` from the **first segment** (`long_run.py:203-204`). So for a segmented run, `provenance.scenario_sha256` is the hash of segment 0's modified copy (computed in `service.py:737` over `self.scenario`), `rng_seeds` are segment 0's only (later segments use derived seeds, `long_run.py:222-234`), and `data_files["space_weather"]` names the derived cache CSV rather than the CelesTrak file. Verified by reading; not executed.
2. **Same scenario, different machine or day, different atmosphere data.** `source: "bundled"` picks the newer of the shipped file and any downloaded one (`spaceweather.py:631-652`), and the startup prompt re-downloads with `force=True` (`gui/startup_fetch_dialog.py:168`). The scenario file does not pin the data; `provenance.json` does record which file was used.
3. **Earth-fixed frame depends on what is installed.** ITRF93 if covering Earth-orientation PCKs are installed, else IAU_EARTH (`service.py:852-880`, frame set at `:856`/`:874`); recorded in `provenance.frames`, not chosen by the scenario.
4. **Monte Carlo draws do not depend on `sim_settings.seed`.** Basilisk's Controller reseeds `np.random` and `random` with `run index * 10` in each run (Basilisk `src/utilities/MonteCarlo/Controller.py:789-791` in this repository; the installed `bsk` 2.12.0 package was not available to check, **unverified there**). The tool sets `setShouldDisperseSeeds(True)` (`engine/monte_carlo.py:517`). A batch is therefore repeatable by run index, but there is no user-visible batch seed, and `archive.provenance.json` (`cli.py:350`) records no seeds; Basilisk's `runN.json` files do.
5. **Hidden defaults.** The control gains used when `control_params` lacks `K`/`P` are `3.5 * (trace(I)/3)/900` and `30 * (trace(I)/3)/900` (`engine/fsw.py:193-226`, `:811-817`); for the schema default inertia `diag(10,10,10)` that is K = 0.0389, P = 0.333, not the 3.5/30 the GUI shows (see (h)). These are not in the scenario or the provenance; reproducing needs the same tool version.
6. **Absolute paths in the scenario.** `space_weather.local_file_path`, `msfc_file_path`, `cache_dir` (`scenario.py:2447-2454`), `vizard_model_path` (`:1882`), and mesh paths (relative to the scenario folder or absolute, `model3d/model.py:107-113`) are machine-specific; a colleague must recreate them. `cache_dir` is an infrastructure path stored in the mission file.
7. **CSV precision**: 9 significant digits (`results.py:191`; stated in `ICD.md` 5.3.3). For `time_s` beyond 1e8 s (> ~3.2 years) this is 1 s resolution or worse; positions of 7e6 m resolve to 0.01 m.
8. **Monte Carlo thread count** is silently reduced to the CPU count (`scenario.py:2550-2553`); logged as a warning only (`engine/monte_carlo.py:518-519`). Unverified whether this can change results (Basilisk reseeds per run index, so probably not).

#### D.3 Minimum package a colleague needs today

The scenario JSON (as saved, plus any `.obj`/mass-property/space-weather/MSFC files it references at the same relative or absolute paths), the same SpaceMissionStudio version, the same Basilisk build, the same reference data (`provenance.data_files` lists them; for files > 32 MB only size is given), and for > 100-day runs nothing in the record identifies the original scenario by hash. There is no "export reproducibility bundle" command.

### (e) Scriptability

* **What exists.** Plain-Python, Basilisk-free schema: dataclasses plus `load_scenario`, `Scenario.validate`, `Scenario.save`, `validate_all`, reference renaming helpers, exported in `schema/__init__.py` `__all__` (`spacemissionstudio/schema/__init__.py`, the list ending with `validate_all`). The engine has no curated API: `spacemissionstudio/engine/__init__.py` is empty apart from the licence. Usable classes and functions, by reading: `engine.service.SimulationService(scenario, vizard_request=None, ...)` with `build()`, `run()`, `run_live()` (`engine/service.py:567`, `:574`, `:709`, `:2034`, `:2064`), `engine.mission_engine.MissionEngine(...).run()` (used at `cli.py:240-241`), `engine.monte_carlo.run_monte_carlo` (`:447`), `engine.lifetime.end_of_life` (`:533`), `engine.propellant_budget.compute_budget` (`cli.py:580`), `engine.ccsds_odm.*`, `engine.spaceweather.*`, `engine.results.ResultSet.export_csv`. The CLI itself imports a private function, `engine.service._orbit_ic_to_rv` (`cli.py:752`).
* **Documentation.** Five example scripts, each run by `tests/test_examples.py` (`examples/README.md:1-20`), and an architecture page (`docs/developer/architecture.md:30-60`). There is no API reference, no statement of which names are stable, and the ICD does not list the Python API as an interface (`compliance/docs/ICD.md` ICD-01..ICD-11).
* **GUI-only capabilities** (no CLI or documented API found): run history / run store and run comparison with input diff (`engine/scenario_diff.py`, used only by `gui/compare_widget.py`, `gui/results_widget.py`); space-weather download/import/rollback (row 12); Vizard program download/launch (`gui/vizard_launcher.py`); plot export with embedded provenance (`gui/results_widget.py:1965-1973`); event-timeline export; template wizard and device catalog presets; editing 3D models (the CLI `model` command reports, applies and exports only); autosave/undo.

### (f) Extensibility

* **No plugin mechanism.** No `entry_points`, plugin loader or extension registry in the package or `pyproject.toml` (grep `entry_points|plugin|REGISTRY|register`; the only "registry" hits are the GUI's own action registry `gui/actions.py:90` and Basilisk's pooch checksum registry). `[project.scripts]` declares only the CLI.
* **Closed enumerations.** Sensor kinds, actuator kinds, FSW modes, integrators, central bodies, command kinds, dispersion quantities, antenna patterns, disposals, RW/thruster factory types are fixed tuples in `schema/scenario.py` (`:94-172`, `:267-302`, `:1508`, `:2593`, `:2677`) and `command.py:89`, each mapped to hand-written engine code. Adding one requires editing core code.
* **What a user can add without editing code:** scenario files of their own (but the template gallery reads only the package folder, `gui/load_scenario_widget.py:96`); their own data files (`space_weather.local_file_path`, `msfc_file_path`, `.obj` meshes, mass-property files, imported Earth-orientation/Eros kernels); free-form keys in device `params` (the "Advanced" JSON box, `gui/param_form.py:28-31`); `script_block` mission-sequence commands running unrestricted Python, gated by `--allow-scripts` or a GUI confirmation (`command.py:356-375`, `cli.py:106-116`); an external flight-software binary through SIL (ICD-10).
* `SensorConfig`'s docstring states the open `params` dict was chosen "so new sensor kinds can be added without another schema migration" (`scenario.py:454-458`), but `SUPPORTED_SENSOR_KINDS` is still validated (`:2000-2002`), so a new kind still needs a code change.

### (g) Change history

* **Scenario metadata:** none for authorship or modification. `Scenario` has no author, created/modified time or revision field (`scenario.py:2681-2722`); only free-text `description` (`:2721`). The only timestamps written into a scenario are `FswExportRecord.exported_utc` and `basilisk_revision` (`:2665-2666`) and model import hashes (`:1652`, `:1743`).
* **Undo:** in-memory, linear, whole-scenario snapshots, 100 steps, unlabeled, cleared on load (`gui/undo_history.py:18-55`). Not persisted.
* **Autosave:** one recovery slot with `saved_at_utc` and `original_path` (`gui/autosave.py:71-110`), deleted on save/discard (`:113-128`). Not a history.
* **Run store:** each run's scenario and provenance are kept (`engine/run_store.py:115-153`), so a past run's inputs can be diffed in the GUI (`engine/scenario_diff.py:18-27`); oldest pruned after 20 runs or 2 GiB (`run_store.py:63-64`).
* **Export log:** the time and path of the last export of each kind in `settings.ini` (`gui/export_log.py:40-57`), "never in an export file" (`:22`).
* **Logs:** per-process log files, newest 100 kept (`logging_setup.py:176-188`).
* **Who changed what:** not recorded anywhere (no user name, no change list). The tool relies on the user's version control for scenario history.

### (h) Overrides of computed or suggested values

| Where | What is overridden | Flagged? |
|---|---|---|
| `gui/param_form.py:176-190` + `gui/spacecraft_editor.py:189-199` + `engine/fsw.py:208-226,811-817` | An unticked optional control gain shows the example value K = 3.5 / P = 30 (greyed out), but the engine then uses inertia-scaled gains (`DEFAULT * (trace(I)/3)/900`). Ticking it applies the typed value unscaled. | **No.** The tooltip says only "Unticked: the default is used" (`param_form.py:186`); the scaled values appear in neither the GUI, the scenario nor the provenance. Most significant transparency gap in this area. |
| same mechanism, sensor/actuator params (`gui/sensor_actuator_editor.py`, `engine/fsw.py` 36 `params.get` defaults) | Unticked optional device params show an example but the engine/Basilisk default applies | No (the displayed example may differ from the applied default; per parameter **unverified**) |
| `gui/sensor_actuator_editor.py:679-686` | Device-catalog preset values overwrite the form; the user may edit any of them afterwards | No record that a preset was applied or edited |
| `cli.py:455-458`, `engine/lifetime.py:590` | Lifetime replaces the spacecraft's `drag_coeff` with 2.2 and the scenario's forecast percentile with 50 unless `--drag-coeff own` / `--forecast-percentile` | Documented (`lifetime-and-budget.md:25`, `--help`); the output prints neither value (the percentile appears only inside an MSFC warning, `spaceweather.py:798-799`) |
| `engine/spaceweather.py:835-842` | `resolve_for(..., forecast_percentile=...)` overrides the scenario's value | caller-specific; see above |
| `model3d` apply / `stale_fields` (`model3d/model.py:309-325`) | Values derived from the 3D model vs hand-typed `dry_mass_kg`, inertia, CoM, facets; `mass_properties_source` records computed/typed/imported (`scenario.py:1764`) | **Yes**: `validate` prints stale-field warnings (`cli.py:97-102` via `engine/scenario_checks.py:477`), `model` prints them (`cli.py:422-423`), GUI shows them (`gui/spacecraft_editor.py:2193`). Not recorded in the run provenance. |
| `PropellantBudgetConfig` (`scenario.py:1535-1539`) | `None` = take from the last run, a number = user's value | **Yes**: each budget row prints its `source` (`cli.py:588`) |
| Mission-sequence `assignment` (`engine/mission_engine.py:731-773`) | Changes a live controller's `thrustN`/`ispS` mid-run | In the scenario file, so reproducible; not logged in results or provenance |
| `scenario.py:2550-2553` | Monte Carlo `thread_count` capped to CPU count | log warning only |
| `migrations.py:47-99` | Older files' space-weather settings rewritten | **No** (A finding 7) |
| `cli.py:815-821` (`ccsds-import --set-epoch`) | Scenario epoch replaced by the message's | Explicit flag required; not recorded in the file |
| `generate-phasing-formation` (`cli.py:1404`) | Station-keeping target altitude derived from the chief unless given | help text only; the derived value is written into the file |
| `engine/service.py:117-118` | Basilisk's default adaptive-integrator relative tolerance 1e-4 replaced by 1e-10 | Recorded in provenance (`results.py:86-87`); documented in the code comment (`service.py:108-116`); not user-selectable |
| Named RW/thruster types (`RW_TYPES`, `THRUSTER_TYPES`, `scenario.py:170-172`) | The Basilisk factory's built-in parameter set fills every value the user does not give | Not shown; values not in the scenario |

---

## Appendix D: GUI

*Detailed findings of review D, as written by the reviewer and checked as described in Section 1.*

Scope: 81 files, about 36k lines under
`SpaceMissionStudio/spacemissionstudio/gui`. I only read code. Nothing was launched or edited.
All paths below are relative to `spacemissionstudio/`. A "GUI" claim means the code that builds the widget.
"Unverified" marks behaviour I inferred from code without running it.

Question the audit asks of each item: can a systems engineer trace the number on screen back to
its inputs (with units), the equation or model, the assumptions, and its source?

Counts (from the code):

| Item | Count | How counted |
|---|---|---|
| Computed-output locations in the GUI reviewed | 31 | Section 1 table |
| Spin-box/range constructions (ranges act as input rules) | 252 | `grep _spin( / _double_spin( / _int_spin( / setRange( / NumberField(` in gui/ |
| Template-wizard curated fields (hard-coded min/max each) | 126 | `WizardField(` in `gui/template_wizard.py`, 31 template specs |
| Generated wizard fields: range ±1e15, display 3 decimals | all other numeric/bool scenario leaves | `gui/wizard_settings.py:402` |
| Tooltips (`setToolTip(`) | 355 | gui/ |
| User-visible references to standards (AD10, ECSS, IADC, MSFC, WGS-84) | 34 lines in 5 files | lifetime, budget, propagation, ground station, spacecraft editors |
| Message call sites: `report(` 58, `show_toast(` 41, `_report_run_problem(` 13, `show_dialog_error(` 11, `QMessageBox` 7, `show_field_error(` 5 | 135 | gui/ |
| Schema validation rules (`_require(`) behind GUI errors | 342 | `schema/*.py` |
| Pre-run plausibility/"check before running" append sites | 24 | `engine/scenario_checks.py` |

---

### 1. Outputs shown without derivation

Rating: **D** = derivation (equation/model) visible in the GUI. **I** = inputs with units visible.
**M** = intermediates visible. **S** = source/provenance visible. "-" = not shown.

| # | Output shown | Where (file:line) | D | I | M | S | Drill-down that exists / what is missing |
|---|---|---|---|---|---|---|---|
| 1 | Results › Overview metric cards (run length, delta-V, propellant used, mean SMA change, lowest link margin, lowest battery charge, passes/contact time, eclipses, data downlinked) | `gui/results_overview.py:60-95` (MetricCard), figures from `engine/run_summary.py:111-160` | - | - | - | partial | A card shows label, value and unit only: no tooltip, no click-through. The derivation rules live only in the engine docstring (`engine/run_summary.py:20-41`), for example "Mean SMA change = mean over last orbit minus mean over first orbit; none for runs < 2 orbits". The Provenance button (`results_overview.py:134-139`) gives versions and settings, not how each figure was computed. Hidden: delta-V adds the cumulative delta-V of four controllers (`run_summary.py:62`), and the orbit period behind the SMA averaging uses `MU_EARTH` (`run_summary.py:108`), even for a non-Earth central body (impact unverified). |
| 2 | Overview card status "Link margin below 0 dB" / "Battery empty" | `gui/results_overview.py:49-57` | - | - | - | - | The thresholds are hard-coded at 0 dB and 0 W·h. The docstring says "only the thresholds a scenario sets colour a card" (`:50-51`), but no scenario field sets them. No depth-of-discharge or required-margin policy is applied. |
| 3 | Overview provenance popover | `gui/run_history_view.py:120-135` (provenance_text), `:225-247` | n/a | n/a | n/a | partial | Scalar keys are shown in full (versions, integrator, step, tolerances, seed, `scenario_sha256`, qualification flag). Data files are listed **by name only**: the SHA-256 and sizes held in provenance (`engine/results.py:104-106`) are not shown (`run_history_view.py:126-127`). `time_system`, `frames`, `transformations`, `series_frames` and `rng_seeds` collapse to "N entries" (`:130-131`). |
| 4 | Plots: provenance line under the toolbar | `gui/results_widget.py:1017-1029` | n/a | partial | n/a | yes | Shows the versions, the integrator, the step and the run start (UTC). The tooltip is only `rng_seed_note`. |
| 5 | Plots: the curves themselves | `gui/results_widget.py:1158-1221`, decimation `:256, 275-296` | - | yes (axis title with unit) | - | yes | Each line is **thinned to 10,000 points by min-max decimation** (`_MAX_PLOT_POINTS_PER_LINE`, `:256`), and the plot does not say so (a code comment only, `:249-255`). The values under the hover tooltip are decimated samples. Display unit conversions are fixed per category (`plot_categories`). |
| 6 | Plot warnings label (⚠ lines) | `gui/results_widget.py:1007-1015`, `:330-334` | partial | - | - | - | **Every** run warning gets the same tooltip, "These spacecraft use two-body gravity only… a numerical-integration problem" (`_DRIFT_WARNING_TOOLTIP`), whatever the warning actually is. This can misattribute a cause. |
| 7 | Readout panel (value of each shown series at the cursor) | `gui/readout_panel.py:39-52`, `gui/results_widget.py:1754-1785` | - | yes (unit column) | - | - | Values are **linearly interpolated** between samples. Wrapping angles and "stepped" series (chosen by a heuristic: >50% of diffs are zero, `readout_panel.py:27-34`) use the last sample instead. The panel does not say which method a row used. The heading's time is elapsed TDB hours plus a UTC conversion. |
| 8 | Mission dashboard: SOC %, net power, battery charge | `gui/mission_dashboard_widget.py:375-397` | - | partial | - | - | SOC is **computed in the GUI** as `100·charge/capacity`, clamped to 0-100 % (`:382`). The capacity used is not shown. |
| 9 | Mission dashboard: "Converged"/"Slewing" badge | `gui/mission_dashboard_widget.py:362-373` | - | - | - | - | Hard-coded threshold of **5.0 deg** pointing error (`:368`), not shown and not configurable. |
| 10 | Mission dashboard: RF link budget (EIRP, FSPL, pointing loss, received power, N0, C/N0, Eb/N0, margin) | `gui/mission_dashboard_widget.py:399-461`, equations `engine/link_budget.py:161-168` | - | - | **yes** | - | Credit: the intermediates are shown. Not shown: the equations (EIRP includes −implementation loss, `link_budget.py:161`; pointing loss uses a 12(θ/θ3dB)² dB approximation, `:156`), and the inputs that close the budget (frequency, data rate, Tx power, Rx G, T_sys, required Eb/N0, implementation loss). The breakdown is **recomputed in the GUI** from the run's scenario copy (`main_window.py:2355, 2452`), not read from recorded data. No atmospheric, rain or polarisation loss terms exist. |
| 11 | Mission dashboard: link badge "Link degraded"/"Link OK" | `gui/mission_dashboard_widget.py:456-461` | - | - | yes | - | 0 dB threshold, hard-coded. |
| 12 | Scenario › Overview (Explain) stat tiles: Spacecraft, Duration, Gravity, Orbit ("SSO 97.4 deg, 550 km alt") | `gui/scenario_explainer_widget.py:349-351`, `engine/scenario_explainer.py:176-188, 644-652` | - | - | - | - | Tiles are plain label/value pairs with no tooltip. "alt" is **SMA minus equatorial radius**, not perigee altitude (`scenario_explainer.py:187`). An eccentric orbit is therefore labelled with a mean "altitude". |
| 13 | Explain: "Ground stations" predicted passes ("2 passes, first at 10 min for 8 min (peak 61 deg)") | `engine/scenario_checks.py:256-281`, `:159-173` | - | - | - | - | A pre-run prediction from a simplified sampled propagation, with J2 only when degree ≥ 2 (`:172`), capped at one week. The GUI note does not name the model, step or cap. |
| 14 | Explain: "Check before running" warnings, Overview node title "(N to check)" | `gui/scenario_explainer_widget.py:325`, `gui/main_window.py:1315-1320` | n/a | n/a | n/a | n/a | Credit: shown before running. See Section 6 for message quality. |
| 15 | End of Life: Re-entry date, Lifetime, Mass, Deorbit burn Δv + propellant | `gui/lifetime_widget.py:330-348` | partial | partial | - | partial | Shown: the choice of Cd (2.2 AD10 or the spacecraft's own), the solar percentile and the horizon. The caption says "Orbit-averaged drag with the scenario's atmosphere and space weather. See User Manual Sec. 11 and 12" (`:262-263`). Not shown: the Cd and area actually used when "spacecraft's own" is picked, the Isp used for the deorbit burn, the atmosphere model and file, the re-entry altitude value, and the accuracy (the manual's "about 2 %", `docs/user-manual/lifetime-and-budget.md:24`). Engine warnings do appear in the notes (`:356`). |
| 16 | End of Life: 5-year / 25-year badges ("met"/"not met"/"not known") | `gui/lifetime_widget.py:350-356` | - | - | - | partial | The rule names are shown. The badge does not state actual vs limit in one line, although the Lifetime tile shows the actual value. |
| 17 | End of Life: altitude chart | `gui/lifetime_widget.py:78-171` | - | yes (km, years) | - | - | The re-entry altitude is drawn as an **unlabelled dotted line** (`:147-151`). The legend covers perigee and apogee only. |
| 18 | Budget table (Phase, Contributor, Δv, Propellant, Margin, From) + status line + notes | `gui/budget_widget.py:535-547` | partial | partial | **yes** | **yes** | Best-in-app traceability. A "Margin" column and a "From" (source) column on each row, and a status line with dry mass, Isp, efficiency and iterations. Missing: the rocket-equation form, and mission years / system margin when the input group is unchecked (defaults are then used silently: `budget_widget.py:91-93` docstring; collapsed groups hide fields, `widgets.py:358-369`). |
| 19 | Budget launch-delay sweep and altitude trade tables | `gui/budget_widget.py:493-533` | - | yes (headers) | partial | - | "Fits tank" yes/no without the tank value in the row. The trade/sweep notes are shown. No CSV export of these two tables (only the main budget, `:549-561`). |
| 20 | Compare › Summary (figure, unit, base, other, Δ) | `gui/compare_widget.py:322-340` | - | partial | - | - | Δ is absolute only (no %). Each figure has the same lack of derivation as #1. |
| 21 | Compare › Inputs (every input that differs) | `gui/compare_widget.py:342-361` | n/a | yes | n/a | yes | Credit: a full input diff (`engine.scenario_diff`), with full values in tooltips. |
| 22 | Compare › Events (count × total min, Δ) | `gui/compare_widget.py:363-379` | - | yes | - | - | |
| 23 | Compare › Plots (overlay) | `gui/compare_widget.py:418-461` | - | yes | - | - | Aligned on **elapsed time [h] since each run's own epoch** (`:440, 451`). Runs with different epochs are overlaid without a note. |
| 24 | Timeline (Gantt + table: Start/End UTC, Duration, measured values with units) | `gui/event_timeline_widget.py:631-660` | - | yes | - | yes (export) | Credit: units and time system in each heading. The summary says why a kind is missing (`:569-570`). Not shown: the detection definitions (eclipse thresholds, elevation mask used, burn detection rules). |
| 25 | Mission Output (report commands; "Change" column) | `gui/mission_output_widget.py:19-31, 250` | - | yes | yes (before/after) | yes (export) | |
| 26 | Monte Carlo tiles: Runs, Failed, along-track/radial/cross-track spread (end), altitude range | `gui/monte_carlo_results_widget.py:182-195` | partial | - | - | partial | The hint says "Spreads are 1-sigma offsets from the mean of all runs: along the orbit, radially and across it" (`:164-165`). No percentiles, no confidence interval on σ for N runs, no batch seed. Failed runs are excluded from the statistics with no note on bias. Plots show only the first `MAX_PLOTTED_RUNS` runs, and the hint says so (credit, `:162-163`). |
| 27 | Monte Carlo Runs table (what each run drew, where it ended vs mean) | `gui/monte_carlo_results_widget.py:204-212` | - | partial | yes | - | |
| 28 | SIL comparison tiles: Steps, Dropped, **Max \|residual\|**, round trip p99, jitter, FSW step time | `gui/sil_comparison_widget.py:140-147` | - | - | - | yes (binary SHA in tooltip, `:138`) | "Max \|residual\|" is the maximum over signals **with different physical units**, shown with no unit (`:143`). The table has no unit column (`:39`). Signals that are zero in both reference and error are hidden (`:167`). No pass/fail tolerance. |
| 29 | Top bar "last run": "Run 2 at 14:05, done, 6 s" | `gui/main_window.py:1834-1835` | n/a | - | n/a | - | **Local wall-clock time** without a zone label (`time.strftime('%H:%M')`). Every other time in the app is labelled UTC. |
| 30 | Run › History (Started UTC, Duration) | `gui/run_history_view.py:76-103` | yes (duration = end − provenance start) | yes | n/a | yes | Credit. |
| 31 | Post-run toast "4 passes, 15 eclipses" | `gui/main_window.py:177-190, 2440` | - | - | - | - | |

Other drill-downs to credit precisely:

* **Inspector** (`gui/workspace_panels.py:131-183`): shows the focused field's label, value, allowed range (the spin box's range) and help (its tooltip). It does **not** show the default value or where the default comes from, and the "Allowed" range is the GUI box range, not necessarily the schema rule.
* **Input differences…** on Plots (`gui/results_widget.py:1512-1550`) and Compare › Inputs: a full input diff between two runs.
* **Stale-results banner** (`gui/feedback.py:494-502`, `gui/main_window.py:1476-1500`): says results come from an earlier scenario version, by SHA-256 of the scenario. Two gaps: (a) the Overview tab (`results_overview`) is **not** in the list of views that show the banner (`main_window.py:1495-1496`); (b) the hash covers only the scenario. A changed reference-data file (for example a startup space-weather update, see Section 3) does not mark results stale.
* **Run warnings** (`result.warnings`) are written to the Log (`main_window.py:1537-1538`) and to the Plots warnings label (#6). They do not appear on Overview.

---

### 2. Engineering defaults and suggestions in the GUI

"Origin shown?" means the GUI states why this value (standard, datasheet, reasoning).

| Value (default / range) | Where | Origin shown? | Note |
|---|---|---|---|
| New spacecraft: name `sat-1`, dry mass **100 kg** (range 0.001-1e6) | `gui/spacecraft_editor.py:430-433` | No | |
| Inertia diag **10 kg·m²** each; CoM 0 | `gui/spacecraft_editor.py:461-470` | No | The tooltip says "Assumed diagonal" (`:451-457`) while products are also shown (`:472-475`): contradictory text. |
| Cd range **0.1-10**; tooltip "~2.0-2.2 is a common default… a real value needs a shape-specific aerodynamic analysis" | `gui/spacecraft_editor.py:506-513` | Partial (help text) | Default from the schema `SpacecraftConfig.drag_coeff`. |
| Cr (SRP) range **0-3** | `gui/spacecraft_editor.py:530-537` | Tooltip explains 1 vs 2 | |
| MRP σ range ±1, ω range ±10 rad/s | `gui/spacecraft_editor.py:582-587` | Yes for σ (shadow-set reason, `:588-595`) | |
| Station keeping: target **500 km**, deadband **1 km**, thrust **0.01 N**, Isp **1500 s**, propellant **2 kg**, sunlit threshold **0.99**, min on-time 0 | `gui/spacecraft_editor.py:911-950` | Isp: "~1500-2000 s electric; ~200-300 s chemical" | Tooltips explain the trade-offs, not the source. |
| GEO SK: slot **10° E**, box **0.05°**, inc max **0.05°**, thrust **1 N**, Isp **220 s** ("~220 s for hydrazine"), propellant **50 kg** | `gui/spacecraft_editor.py:985-997` | Isp only | |
| Constant thrust: **0.01 N**, **1500 s**, **2 kg** | `gui/spacecraft_editor.py:1052-1061` | No | |
| Momentum dumping hs_max **50 N·m·s**; MMM c_gain **0.003** | `gui/spacecraft_editor.py:1373, 1437` | No | Gains have no unit in the label. |
| RF link: Tx **15 W**, **8.2 GHz** ("X-band"), **1 Mbit/s**, impl. loss **2 dB** ("common rough default"), required Eb/N0 **6 dB** | `gui/spacecraft_editor.py:1508-1545` | Partial | The implementation-loss tooltip says it lumps in "pointing error". A separate pointing-loss term also exists (`:1552-1560`), so the same loss can be **counted twice**, and the GUI does not warn about it. |
| Ground station: lat/lon **0,0**, mask **10°** ("5-10 deg common"), Rx gain **45 dBi**, T_sys **290 K** | `gui/ground_station_editor.py:78-118` | Mask only | 0,0 is open ocean. |
| Orbit IC: SMA **7000 km**; Cartesian **(7000,0,0) km / (0,7.5,0) km/s**; LTAN **DEFAULT_LTAN_HOUR** ("10.5 most common") | `gui/orbit_ic_widget.py:204, 273-280, 319-324` | LTAN yes | **Wrong help text**: "~6778 km is a ~500 km-altitude LEO with a ~95 min period" (`:212`). 6778 km is about 400 km altitude, with about a 92.6 min period. |
| SSO inclination / RAAN-for-LTAN buttons overwrite fields | `gui/orbit_ic_widget.py:250-281, 404-421` | Function named in tooltip | After the overwrite, the field shows nothing marking it as computed. |
| Propagation: harmonics default degree **2** when enabled | `gui/propagation_setup_dialog.py:118, 226, 309` | Conflicts with its own tooltip | The tooltip cites "ECSS-E-ST-10-04C 4.2.2a: Earth orbits need degree and order 70 or more" (`:233`). |
| Duration range 0.0001-**3660 days** ("about 10 years"); step 0.001-1e6 s; record 0-86400 s | `gui/propagation_setup_dialog.py:338, 357, 370`; `schema/scenario.py:2636` | Max: tooltip mentions >100 days chaining | |
| Integrator tolerances rel **1e-10**, abs **1e-8** (RKF45/78) | `engine/service.py:117-118` | Not in the editor; only in run provenance | Not editable. |
| Lifetime: deorbit perigee **250 km** (range **130-2000**), horizon **30 y** (1-100), Cd **2.2 (AD10 EoL)**, solar **50th pct (AD10)** | `gui/lifetime_widget.py:48-49, 206-233` | Cd and percentile: **yes** (AD10 Sec 5.2, 5.9) | 250 km and 30 y: no origin. |
| Budget (AD10): mission **5 y**, system margin **15 %** ("AD10 Sec 5.10"), residual 1 %, uncertainty 2 %, CAM ×4, attitude ×2, disposal lifetime ≤ **25 y** (range 0.1-25), clearance ≥5 km suggestion | `gui/budget_widget.py:104-170`; `schema/scenario.py:1520-1548` | **Yes** (AD10 sections in tooltips) | The 25-year cap on the field acts as a rule. |
| Monte Carlo: runs **10** (1-100,000), threads 1 (1-256) | `gui/monte_carlo_editor.py:446-460` | No | |
| **New dispersion via "Add"**: first quantity `dry_mass_kg`, kind `uniform`, **bounds [0, 1] kg**, mean 0, σ 1 | `gui/monte_carlo_editor.py:152-165, 364-381` | No | The dry-mass dispersion is written **absolutely** (`engine/monte_carlo.py:245`). An untouched "Add" therefore draws the dry mass between 0 and 1 kg. The units label shows only "kg" (`:83`), not absolute vs offset. |
| Constellation: T=12, P=3, F=1, **780 km**, **86.4°** | `gui/constellation_dialog.py:114-125` | No | Iridium-like values. No tooltips. |
| Phasing formation: chief target **550 km**, deadband **15 km**, thrust **0.05 N**, Isp 1500 s, propellant **5 kg**; follower along-track **50 km**, deadband **2 km**; tolerance 0.10 / restore 0.02; window 3 d; max drift 90 d | `gui/phasing_formation_dialog.py:132-261` | No | **Different defaults from the spacecraft editor for the same quantity** (SK deadband 1 km vs 15 km; thrust 0.01 vs 0.05 N; propellant 2 vs 5 kg). |
| ROE safe ellipse: radial/cross **300 m**, phase **90°** | `gui/roe_formation_dialog.py:148-154` | No | |
| 3D model "Add" parts: box 0.5 m / 10 kg, prism 80 kg, panel 1×2×0.03 m / 6 kg … | `gui/model_editor_dialog.py:62-69` | Comment only ("a sensible size and mass") | |
| Facet generator: box 1.2×1.2×1.5 m, array 2.5 m² | `gui/facet_editor.py:77-84` | No | |
| Blank scenario: Orbit only, epoch **2030-01-01T00:00:00** | `gui/scenario_editor.py:268, 930-940` | No | |
| Template wizard ranges, examples: LEO alt **200-2000 km** (`:605, 842`), Cd **1.0-4.0** (`:624, 1639`), Isp **50-5000 s** (`:571, 651, 907`), SMA **6500-100000 km** with e up to **0.9** (`:734, 747`), SSO SMA 6578-8378 (`:485`), GEO box 0.01-5° (`:545`) | `gui/template_wizard.py` | Hints only ("most satellites are 2.0 to 2.5") | The ranges allow a perigee below the surface (a=6500, e=0.9). This is caught only later by plausibility checks. |
| Wizard generated pages: every other numeric setting, range **±1e15**, display min 3 decimals | `gui/wizard_settings.py:398-407` | No | In effect no range rule. Not shown which values differ from the template. |
| Wizard "Altitude" fields use Earth radius **6378.1366 km** (`template_wizard.py:105, 259, 270`); explainer the same (`engine/scenario_explainer.py:70`); plausibility uses WGS-84 **6378.137** (`engine/scenario_checks.py:341`); template builders used **6378.0** (comment `template_wizard.py:96-104`) | multiple | No | Displayed "altitude" depends on which constant the view uses (up to ~137 m). The comment "NEVER used to compute a field's WRITE-BACK value" (`:98`) is contradicted by `_set_walker_altitude_km` (`:270`). |
| Sensor/actuator "Reset to template" example params; catalog "Apply device values" | `gui/sensor_actuator_editor.py:616-617, 679-690` | Catalog card: **source URL, heritage, "How the values were set"** (`:425-449`) | Once applied, the device identity is **not stored**: `SensorConfig`/`ActuatorConfig` hold only kind/name/params (`schema/scenario.py:466-468`). |
| Spacecraft presets "100-500 kg" | `gui/spacecraft_template_dialog.py:58-61`, `gui/mission_guide.py:68` | Description text only | Values are not listed before building. |

---

### 3. Forced single options / silent choices

| Item | Where | What the user cannot choose, or what happens silently |
|---|---|---|
| Inertial frame fixed to EME2000 for orbit input and results | `gui/orbit_ic_widget.py:73-78`; `gui/app_shell.py:437` | No other input frame (no ECEF, TOD, ICRF choice). Results are plotted as stored (`position_N`); no RTN/ECEF/LVLH view choice in Plots. |
| Classical elements are **osculating** only | `gui/orbit_ic_widget.py:240` | No mean-element input. |
| TLE always via SGP4 TEME→EME2000 | `gui/orbit_ic_widget.py:371-374` | |
| Integrators: euler, rk2, rkf45, rkf78 | `gui/propagation_setup_dialog.py:382`; `schema/scenario.py:2593` | **Tolerances fixed** (1e-10 / 1e-8, `engine/service.py:117-118`), not editable. |
| Atmosphere: NRLMSISE-00 or exponential | `gui/propagation_setup_dialog.py:446-447` | No Jacchia, JB2008 or DTM (the docstring says Basilisk has none). |
| Space weather "bundled": "**a newer copy from the startup download is used automatically**" | `gui/propagation_setup_dialog.py:469-470` | A silent data swap. The same scenario can give different results after a startup fetch, and the stale banner does not react (Section 1). |
| Solar activity: 50/95/5th percentile only | `gui/propagation_setup_dialog.py:488-503`; `gui/lifetime_widget.py:216-217` | |
| Gravity fields: GGM03S (Earth), GGM2B (Mars) only; harmonics disabled for other bodies | `gui/propagation_setup_dialog.py:270-312` | Credit: disabled with a tooltip, not silently. |
| Plausibility checks are Earth-only | `engine/scenario_checks.py:348-349` | Non-Earth scenarios get no orbit plausibility warnings, with no notice. |
| Plausibility checks run only when there are no validation errors | `gui/scenario_editor.py:1063-1065` | While any error exists, warnings are not shown. |
| Mission-sequence maneuver = **impulsive only**; frames inertial/VNB/RTN | `gui/mission_sequence_editor.py:297-300`; `schema/command.py:118` | Stated in the tooltip (credit). No finite-burn option. |
| Stop conditions: duration/epoch/event, 2 orbital events | `schema/command.py:94-98` | |
| Monte Carlo statistics: 1-σ spread from mean; plots of first N runs | `gui/monte_carlo_results_widget.py:160-165` | No percentiles, no choice of statistic. |
| Compare base = **oldest ticked run** | `gui/compare_widget.py:310`; docstring `:21-22` | The user cannot pick the base. |
| Compare overlay x-axis = elapsed hours only | `gui/compare_widget.py:440, 451` | Plots offer elapsed/UTC epoch/orbit number (`results_widget.py:414`); Compare does not. |
| Plot display units fixed per category (km for altitude, m/s for Δv, deg for angles) | `gui/results_widget.py:83-110` (docstring), `plot_categories.py:512-514` | No unit switch. Uncategorised series get a blanket m→km rule. |
| Plot export formats PNG/SVG/CSV | `gui/results_widget.py:1880-1951` | No PDF/HDF5/CCSDS from the Plots view. |
| Run store keeps the newest **20 runs**, ≤2 GB; older runs pruned **silently** | `engine/run_store.py:63-64`; `gui/run_history.py:259-260` | No toast or log line when a run is pruned. |
| Undo depth 100, in memory only | `gui/undo_history.py:31` | |
| Vizard download URL: Windows or Linux build; any non-Windows platform gets the **Linux zip** | `gui/vizard_launcher.py:161-164, 190-193` | macOS behaviour unverified. |
| Wizard applies some fields uniformly (all wheels, all thrusters, all Walker satellites) | `gui/template_wizard.py:201-208, 262-271, 286-291` | Explained in code comments; the dialog intro says it for some ("Applied to all three…", `:681`). |
| Template wizard writes RPM↔rad/s and altitude↔SMA conversions | `gui/template_wizard.py:318-332, 231-246` | Shown as RPM/altitude, stored differently. Not shown in the dialog. |

---

### 4. Units

| Issue | Where | Detail |
|---|---|---|
| Units are fixed; there is no unit-preference setting anywhere | `gui/settings_page.py:19-28` (sections: appearance, data, Vizard, layout, shortcuts) | `grep unit_system/preferred_unit` finds nothing. |
| Field units move from the label into the spin-box suffix (display only) | `gui/widgets.py:323-356`, `gui/units.py:19-26` | Credit: consistent, and messages keep "[unit]". |
| Implicit GUI conversions | `gui/spacecraft_editor.py:1511, 1518, 2700-2701` (GHz→Hz, Mbit/s→bit/s); `gui/template_wizard.py:318-332` (RPM↔rad/s); `gui/budget_widget.py:108, 297` (% ↔ fraction); `gui/template_wizard.py:421-429` (s → days) | The stored unit differs from the shown unit, and the dialog does not say so. |
| Same physical quantity in different units in different editors | initial body rate **rad/s** (`gui/spacecraft_editor.py:608`) vs MC rate dispersion **deg/s** (`gui/monte_carlo_editor.py:87`); attitude dispersion "**rad, as Euler angles**" (`:84`) vs MRP elsewhere; wheel speed **RPM** in wizard (`gui/wizard_settings.py:157`) vs bias **rad/s** (`:121`) | |
| Values without a unit | SIL "Max \|residual\|" tile and table (`gui/sil_comparison_widget.py:39, 143`); gains K, P, c_gain, mean_oe_gain (`gui/wizard_settings.py:113-116, 147-148`; `gui/spacecraft_editor.py:1188-1203, 1437`); MC dispersion Mean/Std/Bounds fields (unit only in a separate "Units" text row, `gui/monte_carlo_editor.py:178-181`); generated wizard settings without a `_META` entry (`gui/wizard_settings.py:357-365`) | |
| Non-standard unit text | "C" for temperature (`gui/wizard_settings.py:153-157`; not in `units._DISPLAY`, so it shows as " C"); "W*hr" in the dashboard (`gui/mission_dashboard_widget.py:378`) | |
| Time scales | Elapsed time is **TDB seconds** (`gui/results_widget.py:1121`), but the axis says "Elapsed time [hr]" (`:1134`). The status bar says "Frames: EME2000 · … · **UTC**" (`gui/app_shell.py:437`). The top bar uses **local time** unlabelled (`gui/main_window.py:1835`). |
| Epoch input "ISO 8601 UTC" with no zone suffix check shown | `gui/scenario_editor.py:268-279` | |
| Lifetime chart axes: "km" text label; x ticks "y"/"mo" | `gui/lifetime_widget.py:123-131` | Credit. |
| Credit: event table headings carry time system and unit | `gui/event_timeline_widget.py:631-643` | "Start (UTC)", "Duration [min]", "Max elevation [deg]". |
| Credit: CSV exports stay SI with elapsed seconds; the plot shows display units | `gui/results_widget.py:83-88`; tooltip `:602` ("SI units"); Output export tooltip `gui/mission_output_widget.py:141-143` | |

---

### 5. Workflow visibility (build → validate → run → results → analyse → export)

| Step | How it is shown | Inspect/edit intermediate? |
|---|---|---|
| Build | Scenario tree (Overview, Scenario, Environment, Spacecraft, Ground stations, Mission sequence, Monte Carlo) and the **Mission guide** with steps "1. Scenario … 5. Run", each with its state and a button (`gui/mission_guide.py:58-70`) | Form or **JSON mode** shows and edits the exact file text (`gui/json_view.py:19-30`). |
| Validate | Live: `revalidate()` on every edit (`gui/scenario_editor.py:1035-1073`); "✓ valid" / "⚠ first error (and N more: see Problems)"; per-node problem counts in the tree (`:776-834`); Problems dock | Yes, a double-click goes to the field. |
| Pre-run checks | Overview "(N to check)" (`gui/main_window.py:1315-1320`) | Read-only. |
| Run | Run mode segmented control Single/Monte Carlo/SIL (`gui/run_page.py:51`); progress strip with phase/fraction (`gui/main_window.py:1803-1820`); a refusal says why (`:2270-2325`). Script blocks need consent (`:2276-2278`). | **No.** The editor is not locked during a run (comment at `:2346-2355`). Intermediate state cannot be inspected or edited mid-run, except live plots (Single runs without a mission sequence, `:2330`). |
| Mission sequence intermediates | `report` commands → Results › Output (before/after columns) | Read-only. Values can only be changed through `assignment` steps in the sequence. |
| Results | Overview → Plots → Dashboard → Output → Compare; stale banner | Read-only. |
| Analyse | End of Life and Budget can start **"from the end of last run"** (`gui/lifetime_widget.py:299-305`; `gui/budget_widget.py:462-464`) | The chained input (last run's final orbit and propellant) is used but **not displayed** before computing. The Budget does not say whether the last run's scenario equals the current editor scenario; it checks only that the spacecraft name exists (`:462-464`). |
| Export | Reports › Exports lists every export with format, place, destination, provenance and last write (`gui/exports_page.py:38-75`) | |
| Gaps | The guide's 5 steps stop at "Run"; analyses and export are in a separate "There is more" list (`gui/mission_guide.py:72-88`). No single view shows the end-to-end chain for one result (scenario hash → run → derived analysis → export). |

---

### 6. Warnings and errors

Counts: GUI messages go through `report()` (58 sites), `show_toast()` (41), `_report_run_problem()` (13),
`show_dialog_error()` (11), `QMessageBox` (7), `show_field_error()` (5). Behind them are 342 schema `_require`
rules and 24 plausibility-check append sites. Toasts auto-dismiss after 3-6 s (`gui/feedback.py:67`), but
warnings and errors are also logged to Run › Log (`gui/feedback.py:187-205`).

| Example message | Where | Rule? | Why it matters? | Actual vs limit? | How to resolve? |
|---|---|---|---|---|---|
| "{owner}: {label} is {kept} in the file, outside this field's range ({min} to {max}): the box shows {shown}, the scenario keeps {kept} until you change it" | `gui/scenario_editor.py:1097-1099` | yes | implicit | **yes** | implicit |
| "space weather: the data end {last}, before the run ends -- the run is refused" | `engine/scenario_checks.py:416-417` | yes | yes (refused) | yes (date) | implicit |
| "Earth orientation: no IERS files installed -- the Earth-fixed frame is IAU_EARTH (about 160 m/day of error at 400 km); Settings > Reference data downloads them" | `engine/scenario_checks.py:423-424` | yes | **yes (quantified)** | n/a | **yes** |
| "{sc}: perigee is {x} km below Earth's surface" / "perigee at {x} km -- it re-enters within about an orbit" | `engine/scenario_checks.py:372-375` | yes | yes | actual only (limit 120 km not stated) | no |
| "position and velocity give an escape trajectory… (check the units: km and km/s)" | `engine/scenario_checks.py:365-366` | yes | yes | no | yes (hint) |
| Schema: "{sc}: rf_link.frequency_hz must be > 0"; "{prefix}.max_phase_angle_deg must be at most 180" | `schema/scenario.py:596, 1231` | yes | no | **limit only, no actual value** | no (field codes become form labels via `labelled()`, `gui/monte_carlo_editor.py:493-495`) |
| "Monte Carlo is off for this scenario: enable Monte Carlo and add at least one dispersion on the Monte Carlo page, then Run." | `gui/main_window.py:2577-2580` | yes | n/a | n/a | **yes** (and opens the page) |
| "Vizard is not connected: … the run would wait for it with no way to cancel. Use Launch Vizard (or turn the live stream off) first." | `gui/main_window.py:2319-2324` | yes | **yes** | n/a | **yes** |
| "{dir} holds other files: choose an empty folder for the Monte Carlo batch." | `gui/main_window.py:2598-2599` | yes | no | n/a | yes |
| Stale banner: "These results are from a previous version of this scenario. Re-run to see the current one." | `gui/feedback.py:496-497` | yes | implicit | no (which inputs differ is not shown; Compare › Inputs is) | yes (Re-run button) |
| Lifetime: "Not enough propellant for {t} km: the {x} kg left lowers the perigee to {p} km." | `gui/lifetime_widget.py:353-355` | yes | yes | **yes** | implicit |
| Plot warnings tooltip (any warning) "…usually means a numerical-integration problem… try a smaller dynamics step" | `gui/results_widget.py:330-334, 1014` | n/a | **may be wrong for non-drift warnings** | n/a | yes, generic |
| Run failure: "Run failed: {message}\n\nFull details logged to:\n{log file}" | `gui/main_window.py:157-171, 2483-2488` | depends | no | no | log path |
| Overview card "Link margin below 0 dB" / "Battery empty" | `gui/results_overview.py:53-56` | yes | implicit | actual shown, limit fixed | no |

Assessment: GUI-originated messages usually give the rule and how to fix it. Schema-originated messages give
the rule and the limit, but rarely the actual value or why it matters. Only `revalidate()` keeps one error
from each form plus **the first** scenario-level error (`gui/scenario_editor.py:1043-1050`): `Scenario.validate()`
raises on the first failure, so several independent scenario errors are found one at a time (verified in the
code path; runtime count unverified).

---

### 7. Overrides and change history

| Feature | Where | Flagged? | History? |
|---|---|---|---|
| Undo/redo: whole-scenario snapshots, one per settled edit (400 ms), 100 steps | `gui/undo_history.py:31-83`; `gui/main_window.py:126, 1421-1474` | Status bar says only "Undone."/"Redone." | **In memory only, with no labels, timestamps, author or reason.** Reset on open or new. |
| Autosave every 30 s to one recovery slot | `gui/main_window.py:135, 1363-1380`; `gui/autosave.py:65-67` | Restore prompt shows the UTC autosave time (`main_window.py:1393-1397`) | Single slot; cleared on save. Not a history. |
| Scenario file has **no change-log, author or revision field** | `schema/scenario.py:2682-2721` | n/a | None. Only the run provenance `scenario_sha256` ties a run to a version. |
| Computed values written into fields (SSO inclination, RAAN for LTAN, Sun-sync in constellation dialog, wizard altitude→SMA, 3D-model-derived mass/inertia/facets) | `gui/orbit_ic_widget.py:404-421`; `gui/constellation_dialog.py:174-180`; `gui/template_wizard.py:182-190` | **Not flagged** after writing | None. The user can then overwrite them freely, and nothing marks a value as "computed" or "overridden". |
| 3D model: computed vs **typed** vs **imported** mass properties | `gui/model_editor_dialog.py:597-700` | **Yes**: source label shows the file and SHA-256 (`:684`); plausibility warns when the applied values are out of date (`engine/scenario_checks.py:460-470`) | Best override handling in the app. |
| Budget "from last run" vs typed value per contributor | `gui/budget_widget.py:58-74` | Yes (checkbox) and "From" column in the output | |
| Lifetime Cd override: "2.2 (AD10)" vs "the spacecraft's own" | `gui/lifetime_widget.py:224-229` | Choice is visible | Not recorded with the result (no export). |
| Out-of-range values from a file are **kept, not clamped**, and warned | `gui/widgets.py:57-112`; `gui/scenario_editor.py:1088-1108` | **Yes** | |
| Values kept at full precision (no silent rounding) | `gui/widgets.py:19-31, 146-185` | n/a | Credit. |
| Template wizard: unchanged fields are not written; the template file is never modified | `gui/template_wizard.py:1984-1995, 2101-2102` | The dialog does **not** show which fields differ from the template | The result opens as an unsaved scenario. `_open_scenario` calls `_mark_clean()` (`gui/main_window.py:1737`), so wizard edits can be discarded on New/Open/Close **without the unsaved-changes prompt** (inferred from code order; unverified at runtime). No record of "derived from template X with changes Y". |
| Catalog device applied → params overwritten | `gui/sensor_actuator_editor.py:679-686` | Toast/none | Device identity is not persisted (Section 2). |
| Run History: every run with status, mode, start (UTC), duration, saved location; provenance popover | `gui/run_history_view.py:19-28, 255-341` | n/a | Runs only, not edits. Failed runs and batches are kept "this session only" (`gui/main_window.py:1570-1578`). |
| Export log: only the **last** time and path per export kind | `gui/export_log.py:39-55` | n/a | Not a history. |

---

### 8. Data imports and exports (and their provenance)

| Data | Direction | Where | Provenance |
|---|---|---|---|
| Scenario JSON open/save, recent files | in/out | `gui/main_window.py:1654-1787` | The file itself. Templates are read-only (`:1743-1765`). |
| Template "Customize" wizard | in (template) | `gui/template_wizard.py:2017-2186` | Not recorded in the result. |
| Reference data: SPICE kernels, gravity fields, magnetic model, space weather, IERS EOP, Eros ephemeris | download (consented), import, rollback | `gui/data_panel_widget.py:19-30, 46, 385-420`; `gui/startup_fetch_dialog.py:19-60` | **Table with Kind, File, Status, Covers, SHA-256 (not computed over 32 MB, `:367`), Installed, Source.** The consent prompt names the source, files and size. Strong. |
| Space-weather local file / MSFC prediction table | in | `gui/propagation_setup_dialog.py:477-516` | Path in the scenario; hash in run provenance `data_files`. |
| TLE lines | in | `gui/orbit_ic_widget.py:351-377` | TLE epoch and age vs scenario epoch shown (`:480-490`). |
| `.obj` meshes, mass-property files | in | `gui/model_editor_dialog.py:123, 684` | Mass file SHA-256 shown. |
| Monte Carlo results folder | in | `gui/monte_carlo_results_widget.py:136-152` | Folder name in the hint. No `RunProvenance` exists for MC (`engine/results.py:73-78`). |
| Plot data CSV (one file per series, SI) | out | `gui/results_widget.py:1805-1822` | `provenance.json` in the folder (`gui/exports_page.py:40-41`). |
| Plot PNG/SVG (single / Export all) | out | `gui/results_widget.py:1885-1975` | Embedded in the file (PNG text chunk, SVG metadata). Export all also writes per-series CSV and `provenance.json`. The **Plotly mode-bar camera button** (mode bar left enabled: `gui/plot_page.py:141, 202` only sets `displaylogo:false`) would save an image without that embedding (unverified whether QWebEngine completes such a download). |
| Events CSV (**filtered** rows only) | out | `gui/event_timeline_widget.py:697-719` | `<file>.provenance.json`. The filter (kinds, station, search) is **not recorded**. |
| Mission Output CSV (all reports, SI) | out | `gui/mission_output_widget.py:313-331` | `<file>.provenance.json`. |
| Monte Carlo runs CSV | out | `gui/monte_carlo_results_widget.py:219-244` | **None** (stated on the Exports page, `gui/exports_page.py:62-63`). |
| Budget "Copy as CSV" (clipboard) | out | `gui/budget_widget.py:549-561` | Appends `scenario_lines(self._scenario)`, the **current editor scenario**, which may differ from the scenario the budget was computed from if edited since. No last-run provenance. Sweep and trade tables are not exportable. |
| Lifetime results | - | `gui/lifetime_widget.py` | **No export at all.** |
| Any DataTable (Compare, Budget, Trade, MC, events) Ctrl+C TSV | clipboard | `gui/data_table.py:242-246, 293, 485`; `gui/run_history_view.py:209-216` | No provenance. |
| Vizard playback `.bin` / live stream | out | `gui/main_window.py:1587-1608, 2276-2307` | None (Exports page `:70-71`). |
| Vizard application download | in | `gui/vizard_launcher.py:155-164, 286-296` | URL, size and SHA-256 recorded in `download.json`, but **not verified** against a published checksum ("AVS publishes no checksum", `:289`). No version pin. |
| Flight-software C project export | out | `gui/fsw_workbench_widget.py:280-316` | `manifest.json`; up-to-date/stale/changed-on-disk badges (`:33-39`). |
| SIL report (JSON + residuals CSV) | out | `gui/sil_comparison_widget.py`; `gui/exports_page.py:68-69` | Binary and configuration SHA-256 in the report. |
| 3D model OBJ/MTL | out | `gui/model_editor_dialog.py`; `gui/exports_page.py:72` | None. |
| Run store `~/.spacemissionstudio/runs` | out (auto) | `gui/run_history.py`; `engine/run_store.py:63-64` | The run's provenance is saved. Pruned silently at 20 runs. |

---

### 9. Existing transparency features to credit

| Feature | Where | What it does well |
|---|---|---|
| Run provenance (versions, Basilisk qualified flag, integrator, step, tolerances, seeds, scenario SHA-256, data-file hashes, frames, time scales) | `engine/results.py:61-135`; GUI `gui/results_overview.py:134-139`, `gui/run_history_view.py:120-135`, `gui/results_widget.py:1017-1029` | Captured per run, embedded in every major export. ECSS-Q-ST-80C references in code. |
| Status bar: Basilisk version with "(not qualified)", reference data status, Earth orientation accuracy horizon, frames | `gui/app_shell.py:395-438`; `gui/main_window.py:478-484` | Always visible. |
| Reference data panel with SHA-256, coverage, source, install time, consented download, import, rollback | `gui/data_panel_widget.py:19-30` | Very strong data provenance. |
| Stale-results banner keyed on scenario SHA-256 | `gui/main_window.py:1476-1500`; `gui/feedback.py:471-502` | Undoing back to the run's scenario hides it. |
| Compare › Inputs and "Input differences…" | `gui/compare_widget.py:342-361`; `gui/results_widget.py:1512-1550` | Full input diff between runs. |
| Budget table with per-row Margin and From (source) columns, AD10 section references | `gui/budget_widget.py:282, 535-547, 96-167` | Closest thing to an auditable derivation in the GUI. |
| Lifetime: AD10 Cd 2.2 and MSFC percentile choices named with their standard | `gui/lifetime_widget.py:216-229` | |
| Propagation tooltips citing ECSS-E-ST-10-04C, AD10, MSFC; per-perturbation enables | `gui/propagation_setup_dialog.py:228-236, 488-503` | |
| Frame/time labels on orbit inputs ("EME2000 (SPICE J2000), central body, at the scenario epoch (UTC)"); WGS-84 labels on ground stations; MRP frame in label | `gui/orbit_ic_widget.py:73-78, 371-374`; `gui/ground_station_editor.py:82-90`; `gui/spacecraft_editor.py:606` | |
| Orbit-type switch dialog shows current, converted and the other page's values before committing | `gui/orbit_ic_widget.py:495-539` | |
| TLE epoch and age vs scenario epoch | `gui/orbit_ic_widget.py:480-490` | |
| No silent rounding; out-of-range file values kept and warned | `gui/widgets.py:19-112`; `gui/scenario_editor.py:1088-1108` | |
| JSON mode: the exact saved text, editable, validated | `gui/json_view.py:19-30` | |
| Inspector: field, value, allowed range, help | `gui/workspace_panels.py:131-183` | |
| Catalog device card with source URL, heritage, export control, "How the values were set" | `gui/sensor_actuator_editor.py:425-449` | |
| 3D model mass source (computed/typed/imported with SHA-256); products-of-inertia sign convention stated | `gui/model_editor_dialog.py:619, 684` | |
| Mission dashboard link-budget intermediates (EIRP … margin) | `gui/mission_dashboard_widget.py:449-455` | |
| Timeline headings with time system and units; "No X: why" notes | `gui/event_timeline_widget.py:569-570, 631-643` | |
| Reports › Exports table: every export, its provenance, and which have none | `gui/exports_page.py:38-75` | Honest about gaps (MC CSV, Vizard, OBJ). |
| Monte Carlo hint explains the statistic and the plotted subset | `gui/monte_carlo_results_widget.py:160-166` | |
| Explain "Check before running" warnings before a long run | `engine/scenario_explainer.py:564-574` | |
| Impulsive-burn assumption stated on the Δv fields | `gui/mission_sequence_editor.py:297-300` | |
| Rich tooltips (355) explaining physical meaning and trade-offs | throughout | They explain meaning; they rarely give the origin of the default value. |

---

### Top findings (ranked for systems engineers)

1. Overview metric cards (`gui/results_overview.py:60-95`) show bare value + unit. The derivation rules exist only in `engine/run_summary.py:20-41` and cannot be reached from the GUI.
2. The provenance popover hides data-file SHA-256 and frames/time-system details as "N entries" (`gui/run_history_view.py:126-131`), although they are recorded.
3. Hard-coded GUI thresholds: 0 dB margin, 0 W·h battery (`gui/results_overview.py:53-56`), 5° "Converged" (`gui/mission_dashboard_widget.py:368`). None are configurable or labelled.
4. MC "Add" dispersion default: uniform dry mass [0, 1] kg, applied absolutely (`gui/monte_carlo_editor.py:152-153, 364-381`; `engine/monte_carlo.py:245`).
5. Plots decimate to 10,000 points per line without telling the user (`gui/results_widget.py:256`). The readout interpolates without saying so (`gui/readout_panel.py:39-52`).
6. The warnings tooltip assigns a numerical-drift cause to every run warning (`gui/results_widget.py:330-334, 1014`).
7. The stale banner skips the Overview tab and ignores reference-data changes (`gui/main_window.py:1476-1500`), while bundled space weather is silently replaced by a startup download (`gui/propagation_setup_dialog.py:469-470`).
8. No edit history beyond an unlabelled in-memory undo. Computed or overwritten values are never flagged. Template, catalog and wizard origins are not persisted (`gui/undo_history.py`; `schema/scenario.py:466-468, 2682-2721`).
9. Inconsistent defaults and help: the harmonics default degree is 2 against the ECSS ≥70 the same tooltip cites (`gui/propagation_setup_dialog.py:118, 233`); the SMA tooltip says 6778 km ≈ "500 km, 95 min" (`gui/orbit_ic_widget.py:212`); SK defaults differ between the spacecraft editor and the phasing dialog; three different Earth radii feed displayed "altitudes".
10. Unit gaps: SIL "Max \|residual\|" mixes units with no unit shown (`gui/sil_comparison_widget.py:143`); rad/s vs deg/s for the same rate across editors; local time in the top bar vs UTC elsewhere (`gui/main_window.py:1835`); TDB elapsed axis labelled only "[hr]".
