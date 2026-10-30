# Changes to computed results

Every change that moves a number SpaceMissionStudio computes is recorded
here, with the value before and after, so that a result from an earlier
version can be explained. It is the record the transparency plan asks for
(`docs/transparency_audit.md`, Section 9.1): a number changes only to fix a
defect or by a decision, never as a side effect of a refactor.

The regression baseline (`tests/test_golden_outputs.py`) fails on any
change. A change is entered here first; then the baseline is rewritten
(`docs/developer/README.md`, "The regression baseline").

Each entry gives: the date and pull request; what changed and why (the
defect, with its number in the audit, or the decision); the outputs
affected; their values before and after, for at least one template or
case; and how it was checked.

Newest first.

## 2026-10-30: the rest of the one set of constants (Phase 3c, completed)

**Numbers change; one is a defect.** Phase 3c left copies behind; checking
the audit's Section 4 against the registry found them. They now take
`spacemissionstudio.constants`:

- **The Earth's rotation angle in the pass predictions and the GEO
  elements counted a fixed 37 leap seconds** (`_TT_MINUS_UTC_S = 69.184`
  in `orbit_design` and `scenario_checks`). That is right only from 2017:
  for an earlier epoch the Earth was turned too far, by 0.0042 deg per
  missing leap second. For a 2010 epoch, 3 s short, the error is
  0.0125 deg, a quarter of a 0.05 deg GEO box. Both now take TDB from
  `time_system`, with the leap seconds of the date (ERFA's table), as
  the simulation does.
- **The Earth's rotation rate is SPICE's.** It is now the rate of
  pck00010's prime meridian (IAU 2009, 360.9856235 deg/day, the IAU_EARTH
  model the pass predictions and GEO elements already used). It replaces
  two values:
  - astroConstants.h's 2 pi / 23.9345 h, a rounded sidereal day 1.2e-6
    slow (the lifetime's co-rotating atmosphere);
  - GEO station keeping's own 7.2921159e-5 rad/s.
- **No number changes:** g0 (9.80665 m/s^2, in seven modules), the speed
  of light, the ODM writer's GM and Explain's body radii were copies of
  the same values.

| Output | Before | Now |
|---|---|---|
| GEO elements at 10 deg E (`orbit_design.geostationary_elements_deg`), true anomaly, epoch 2010-01-01T00:00:00 | 20.425889645703137 deg | 20.413355029420927 deg (-0.0125 deg: 3 leap seconds) |
| The same, epoch 2016-06-30T12:00:00 | 18.817643395159394 deg | 18.81346571771428 deg (-0.0042 deg: 1 leap second) |
| The same, epoch 2026-11-01T00:00:00 | 320.03916764538735 deg | 320.03916150983423 deg (-6.1e-6 deg: TDB - TT, 1.5 ms) |
| Earth rotation angle of the pass predictions, epoch 2010-01-01, t = 1 h | 23017.323058780818 rad | 23017.322840010493 rad (-2.2e-4 rad) |
| Lifetime, template 18 (`leo-sat-1`), 30-year look-ahead | 28131146.015538994 s | 28131145.524166778 s (-0.49 s of 326 days, -1.7e-8) |
| Lifetime, template 22 (`my-sat`) | 448726522.39818966 s | 448726512.5553172 s (-9.8 s of 14.2 years, -2.2e-8) |
| GEO station keeping's Earth rotation rate | 7.2921159e-5 rad/s | 7.292115373194001e-5 rad/s (-7.2e-8) |

Pass predictions, at their 30 s sampling, are unchanged for template 26
and for a copy of it moved to 2010. Every template's epoch is in 2030, so
the leap-second defect touched none of them. The regression baseline of
all 31 templates passes at its tolerance (0 of 31 differ), so it is not
rewritten. `tests/test_constants.py` now also fails if any module writes
one of the set's values as a number of its own.

## 2026-10-30: the Assumptions page (Phase 3d)

**No number changes.** A page of the scenario editor that shows the
parameters and writes the project configuration file; no calculation
changed, and the regression baseline of all 31 templates passes unchanged.

## 2026-10-30: one set of physical constants (Phase 3c)

**Numbers change, below what any output prints.** The decision (the
transparency audit's Section 10, question 2; `docs/models/constants.md`):
SpaceMissionStudio's own calculations take Basilisk's constants, the ones
every simulated orbit uses, from one module (`spacemissionstudio.constants`).
Five sets were in the code; the modules that already held Basilisk's values
keep them exactly (the same floating-point numbers), and these change:

| Output | Constant before | Constant now | Value before | Value now |
|---|---|---|---|---|
| Thermal sensor temperature (template 20, `sat-1.sensor.therm-1`), through the solar flux's distance scaling | AU 149 597 870 700 m (IAU 2012) | 149 597 870 693 m (Basilisk) | 81.14740754499958 °C | 81.14740753540956 °C (largest change over the run: 9.6e-9 °C, 1.1e-10 of the scale) |
| Solar flux at a given Sun distance (`environment_models.solar_flux_at_distance_w_m2`), e.g. at 1 IAU AU | as above | as above | 1361.0 W/m^2 | 1360.9999998726319 W/m^2 (-9.4e-11) |
| Gravity-truncation estimate (Explain's gravity fidelity), degree 0 at 400 km | GGM03S: GM 3.986004415e14 m^3/s^2, R 6 378 136.3 m, J2 1.08263e-3 | Basilisk: 3.98600436e14, 6 378 136.6 m, 1.082616e-3 | 0.02495128850121258 m/s^2 | 0.024950967858611308 m/s^2 (-1.3e-5) |
| The same, degree 20 at 400 km | as above | as above | 2.0382206775595973e-05 m/s^2 | 2.0382232312299818e-05 m/s^2 (+1.3e-6) |
| Scenario checks: pass predictions, orbit warnings | GM 3.986004415e14 (labelled as Basilisk's, which it is not), J2 1.0826e-3, WGS-84's 6 378 137 m for the surface | the one set | unchanged in every printed digit across all 31 templates (pass summary, fidelity notes, first three passes to 0.1 s, orbit warnings) | |

The regression baseline of all 31 templates passes unchanged at its
tolerance (1e-6 of each quantity's scale); the thermal sensor's change,
1.1e-10, is far below it, so the baseline is not rewritten.

Two rules change without changing a number at the defaults:
- the scenario checks' "re-enters within about an orbit" now uses
  `lifetime.reentry_altitude_km` instead of a 120 km of their own, which a
  project changing the parameter did not move;
- the run's 100 km re-entry altitude is the parameter
  `dynamics.reentry_altitude_km`, and its warnings print it.

## 2026-10-30: the environment's data rules, as parameters (Phase 3a)

**No number changes.** MSFC's 132-month repeat and the 3-day TLE age
warning are named parameters with the same values; the regression
baseline of all 31 templates passes unchanged. A resolved space-weather
file keeps its name at the default repeat, so cached files are reused.

## 2026-10-30: the dynamics' integration and run control, as parameters (Phase 3a)

**No number changes.** The adaptive integrators' tolerances (1e-10
relative, 1e-8 absolute), the re-entry checks (every 6 h, every 300 s
below a 200 km perigee) and the two-body runs' 1 % conservation check are
named parameters with the same values; the regression baseline of all 31
templates passes unchanged. The conservation warning writes its limit
from the value now ("{limit * 100:g}%"), "1%" as it printed before.

## 2026-10-30: how a run's results are read, as parameters (Phase 3a)

**No number changes.** The mean semi-major axis change's one-orbit window,
the 1 % sunlight that makes an eclipse umbra, the dashboard's 5° converged
pointing, and the overview's battery limit (empty, 0 of the capacity) are
named parameters with the same values; the regression baseline of all 31
templates passes unchanged, every figure and event as before.

## 2026-10-30: the link's and data handling's rules as parameters (Phase 3a)

**No number changes.** The link's closure rule (a margin of at least 0
dB), the "fixed" pattern's pointing loss (12 dB per (angle / beamwidth)^2,
at most 30 dB), the transmitter's 1 Mbit packets and the explanation's
10-minute pass are named parameters with the same values; the regression
baseline of all 31 templates passes unchanged, every link margin, closed
sample and downlinked bit as before.

The records are repaired: the headings of the registry's and the
reproduction bundles' entries below were lost when the entries above them
were added, and are restored.

## 2026-10-30: the lifetime's rules as parameters (Phase 3a)

**No number changes.** The lifetime's rules moved from module constants to
named parameters with the same values; the regression baseline of all 31
templates passes unchanged, every lifetime and re-entry date as before.

## 2026-10-30: the parameter registry, first area the propellant budget (Phase 3a, 3b)

**No number changes.** The budget's rules moved from module constants to
named parameters with the same values. The regression baseline of all 31
templates differs only in the run provenance's new `configuration` field
(no file, no overrides); every budget row, margin label, note and total is
as before. With no configuration file, every parameter has its default.

## 2026-10-29: reproduction bundles (Phase 2h)

**No number changes.** The bundle and `reproduce` read and write files
around a run; no engine code changed, and the regression baseline of all
31 templates passes unchanged.

## 2026-10-29: the effective configuration (Phase 2c)

**No number changes.** In the regression baseline, each of the 31
templates differs only in the four new provenance fields:
`effective_defaults`, `device_parameters`, `effective_config_note` and
`scenario_file_migrations`, the last empty because the baseline runs the
service directly. The record notes the defaults the engine already applied
and reads back the values Basilisk's factories already gave. It changes
none of them, and every series, event, figure and other record is as before.

## 2026-10-29: the records of a lifetime, a budget, a batch and a SIL run (Phase 2g)

**No number changes.** The regression baseline of all 31 templates differs
only in two new fields of each lifetime, `area_m2` and `drag_coeff`: the
area and drag coefficient the decay already used, now kept on the result
(14 templates have a spacecraft with drag). Every lifetime, re-entry date,
budget row and total is as before. The space-weather files a lifetime or
budget read (`data_files`) are left out of the baseline, as the run's are.

## 2026-10-29: the run record (Phase 2a, 2b, 2d, 2f)

**No number changes.** The regression baseline of all 31 templates differs
only in two new provenance fields, `scenario_file` and
`scenario_file_sha256` (empty in the baseline, which runs the service
directly). The data files' records, excluded from the baseline as they
differ from computer to computer, gain the SHA-256 of files over 32 MB and
of installed kernels, and the MSFC prediction file where a run used it.

## 2026-10-29: GUI defaults (audit 3.4, 3.7, 3.9)

**Saved scenarios:** no number changes. The regression baseline (31
templates) passes unchanged, and the gains the controller applies are the
same. What changes is what a user starts from in the GUI:

| Defect | Output | Case | Before | After |
|---|---|---|---|---|
| 3.4 | Attitude gain K and rate gain P shown when unticked | The default spacecraft (10 kg*m^2) | 3.5 and 30 (not what is applied) | 0.03889 and 0.3333 (applied, before and after) |
| 3.7 | A new dispersion from **Add** | A spacecraft of 150 kg dry mass | dry mass uniform in [0, 1] kg: every run 0 to 1 kg | dry mass uniform in [150, 150] kg: no spread until one is set |
| 3.9 | Receive gain of a new ground station made in the GUI | Any | 45 dBi | 0 dBi, the schema's default, as a station written without the field |

- **3.9:** a link margin to a station made in the GUI from now on is 45 dB
  lower than one made the same way before, until its gain is set. A
  station already in a scenario keeps its gain.
- Checked by the tests listed in `docs/ui/TEST_CHANGES.md` (each fails on
  the code before).

*No entries yet: the baseline was recorded on 2026-10-29 (develop
20d80d67a), with no change of any number.*

## 2026-10-29: engine and command-line defects (audit 3.1-3.3, 3.5, 3.6, 3.11, 3.13, 3.14)

**Templates:** no recorded number of any of the 31 templates changes. The
baseline differs only in two new provenance fields, `central_body` and
`central_body_mu_m3_s2` (template 01: `"earth"`, 3.98600436e14 m^3/s^2),
which the baseline now holds. Checked with
`scripts/update_golden_outputs.py` before the baseline was rewritten.

The fixes change results the capped runs do not reach (the orbit-number
axis is not in the baseline; template 29's ROE controller makes no burn
in the first 6 hours). Measured on the templates' full runs and on the cases
of the new tests:

| Defect | Output | Case | Before | After |
|---|---|---|---|---|
| 3.1 | Orbit-number axis | A circular 400 km Mars orbit over 2 days (24.41 orbits), recorded every 600 s | 312.41 | 24.41 |
| 3.1 | Orbit-number axis | The same, recorded every 1800 s | 216.41 | 24.41 |
| 3.1 | Orbit-number axis, at the end of the run | Template 31 (Eros), its full 2 days, recorded every 60 s | 220582.58 | 2.58 |
| 3.1 | Orbit-number axis, at the end of the run | Template 30 (Mars), its full 2 days, recorded every 60 s, also thinned to 600 or 1800 s (its 20 h orbit is sampled finely enough with either GM) | 2.40 | 2.40 |
| 3.14 | Run summary, mean semi-major axis change | A Mars orbit (period 7083 s, three orbits) whose mean semi-major axis falls 300 m over the run and wobbles 2 km at the orbit period; true change over the averaged span 0.200 km | -3.110 km | -0.200 km |
| 3.5 | Run summary, delta-V | Template 29 (ROE helix), its full 4 days: follower-1 | 0.000 m/s | 0.588 m/s |
| 3.13 | Time to a `propagate` stop epoch | From 2016-12-31T23:59:00 to 2017-01-01T00:01:00 UTC, across the leap second | 120 s | 121.00000004 s (the 4e-8 s is the TDB-TT term) |

- **3.1, 3.14:** the orbit period came from Earth's GM for every central
  body. Earth runs are unchanged: their GM is the same constant
  (3.98600436e14 m^3/s^2). A run recorded before the GM was kept takes it
  from the body its inertial frame names.
- **3.5:** the ROE formation controller's delta-V was left out of the
  run's delta-V figure; its propellant was already counted.
- **3.13:** any stop epoch not across a leap second moves by the change of
  TDB - UTC between the two epochs: at most about 3.3 ms, twice the
  1.66 ms amplitude of TDB - TT.
- **Not numbers:** a run on predicted Earth orientation now lists the note
  among its warnings (3.6); a check that could not run says
  `check not run: ...` (3.11); a run split into segments records the
  whole run's provenance (3.3); exit statuses change as ICD-02 now gives
  them (3.2: `monte-carlo` with a failed run 4 to 3, `kernels-status` with a
  kernel missing 1 to 2, `fsw-status` stale and `sil --max-error` over the
  limit 2 to 5).

Checked by the new tests listed in `docs/ui/TEST_CHANGES.md` (each fails
on the code before) and the regression baseline.

## 2026-10-29: the baseline

Recorded on develop 20d80d67a, with no change of any number.
