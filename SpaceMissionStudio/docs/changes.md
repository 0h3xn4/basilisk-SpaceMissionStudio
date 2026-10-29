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
