# Analyses built on the 3D model: progress

Branch `feature/model-analyses`, from `develop` at `6608682a3` (2.0.0).
Status: complete; merged and released in 2.1.0 (2026-11-04). The rest of
this file is the record as kept during the work.
Re-read this file first after an interruption. Design:
[model-analyses-design.md](model-analyses-design.md); decisions:
[model-analyses-decisions.md](model-analyses-decisions.md).

## Plan (mirrors the design, section 7)

| # | Step | State |
|---|---|---|
| 0 | Investigation, design, decision log, progress file | done |
| 1 | Schema: mounts, equipment, poses, materials, face properties, mass budget, launcher, model_analyses; validation, references, rename_part | done |
| 2 | `model3d/raycast.py` with analytic tests | done |
| 3 | `model3d/equipment.py`, stowed derive, `config/materials.py` | done |
| 4 | Static checks: fov, thrusters, mass budget, launcher; CLI `check-design`, API, findings, Run › Design Checks | done |
| 5 | Run analyses: disturbance recorder, blinding, antenna obstruction, shading, exposure, brightness; series, events, CLI `model-analyses`, API, Results › Model Analyses | done (shading in the power budget dropped, D-09) |
| 6 | Re-entry casualty estimate on End of Life; CLI `reentry`, API | done |
| 7 | 3D model editor: Equipment and Stowed tabs, cones | done after the merge (D-24); materials, face properties, the mass budget's policy and the launcher followed in D-25 |
| 8 | Template 32 on the 300 kg bus; template claims; bus presets | done (presets unchanged, D-20) |
| 9 | Docs, V&V records, generated docs, full suite, coverage, Basilisk path check | done; final suite and commits below |

## Done

- Step 0 (2026-11-03): investigations, design, decision log; sourcing
  (`model-analyses-sources.md`).
- Steps 1-3: schema fields (all optional, written only when set),
  `rename_part`, ray casting, mounted equipment, stowed mass properties,
  the material library, AIAA S-120-2006 margins.
- Step 4: `analyses/` design checks, five `design.*` rules in the
  plausibility checks, `check-design`, `api.design_checks`, Run › Design
  Checks, record and tables with provenance.
- Step 5: `engine/disturbance_recorder.py` (D-19) and
  `analyses/disturbances.py`; ephemeris and station recorders and the
  observer sites in the run; `analyses/run_geometry.py`, `blinding.py`,
  `shading.py`, `exposure.py`, `brightness.py`, `run_analyses.py`; three
  Timeline event kinds; `model-analyses`, `api.model_analyses`, Results ›
  Model Analyses; the spacecraft editor's Model analyses group.
- Step 6: `analyses/reentry.py`, `reentry`, `api.reentry`, End of Life's
  re-entry section; parameters `reentry.*` and
  `analyses.observer_sun_depression_deg`.
- Step 8: template 32 with golden file, hash and claims.
- Step 9: `docs/models/model-analyses.md`, `reentry.md`, `materials.md`;
  the how-to `docs/user-manual/model-analyses.md`; the User Manual, the 3D
  model guide, capabilities, limitations, glossary, CHANGELOG
  (Unreleased); SRS-F-25 to F-27 and their SDD mapping;
  `compliance/validation/model-analyses-vv.md`.

## Checks

- Full suite 1 (2026-11-03, before steps 5-9 were complete): 4468 passed,
  2 failed (`model_analyses` had no place in the spacecraft editor; fixed
  by its Model analyses group).
- Full suite 2 (a copy, after step 6 and the GUI): 4496 passed, 3 failed:
  the Ray samples field had no unit (fixed); two dependency tests read
  `../.github`, which the copy lacked (they pass in the worktree).
- Full suite 3 (the worktree): 4517 passed, 13 failed, all from template
  32 meeting the template machinery: no wizard spec, a description
  without "Try changing", Home's count, the ephemeris series missing from
  the series prediction, raw mount names in the wizard, and a real defect:
  the sensor and actuator editor dropped a `mount` when it rebuilt the
  item. All fixed.
- Full suite 4 (final state, 2026-11-03): **4530 passed, 0 failed**, in
  34 min 51 s; coverage 94.21 % of statements, 85.55 % of branches (CI
  thresholds 90 % and 80 %). Ruff, pre-commit and the compliance tools'
  checks (`check_drds`: 0 problems) pass.
- The Basilisk path check: `git diff --name-only develop...HEAD` and the
  working tree list only `SpaceMissionStudio/` paths. The local `develop`
  ref was at 1.3.1 (stale), which made the check list 2.0.0's own files;
  it was moved to `origin/develop` (6608682a3) before checking, locally
  only.

## Next

- The commits (D-22).
- Follow-ups: the 3D model editor's Equipment and Stowed tabs and the
  cones in its view (D-21), done on `feature/model-editor-equipment`
  (D-24).

## Known issues

- PR #207 (the 2.0.0 publication record, documents only) was open on
  `develop` and not merged: the brief says not to merge into `develop`.
  It was merged on 2026-11-03.
