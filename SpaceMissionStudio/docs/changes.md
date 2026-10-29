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

*No entries yet: the baseline was recorded on 2026-10-29 (develop
20d80d67a), with no change of any number.*
