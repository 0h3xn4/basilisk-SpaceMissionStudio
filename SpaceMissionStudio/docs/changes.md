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
