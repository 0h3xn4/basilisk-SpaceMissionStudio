# ECSS / CCSDS compliance work

Audit, review and update of SpaceMissionStudio against five standards, as
far as software and documentation can achieve. Basilisk is reused,
unmodified software throughout (ECSS-Q-ST-80C reuse); nothing here changes
it.

| Standard | Edition used | Requirements file |
|---|---|---|
| ECSS-E-ST-40C Software | Rev.1, 30 April 2025 | `requirements/ECSS-E-ST-40C.csv` (783) |
| ECSS-Q-ST-80C Software product assurance | Rev.2, 30 April 2025 | `requirements/ECSS-Q-ST-80C.csv` (347) |
| ECSS-E-ST-10-09C Reference coordinate systems | 31 July 2008 | `requirements/ECSS-E-ST-10-09C.csv` (92) |
| ECSS-E-ST-10-04C Space environment | Rev.1, 15 June 2020 | `requirements/ECSS-E-ST-10-04C.csv` (152) |
| CCSDS 502.0-B Orbit Data Messages | B-3, April 2023 | `requirements/CCSDS-502.0-B-3.csv` (715) |

The task named the standards without issue; the editions above are the
ones supplied, and every requirement ID and text here comes from them.

## Layout

* `requirements/` -- every requirement, one CSV per standard (Phase 0).
* `phase0_tailoring.md` -- criticality category proposal and tailoring.
* `PROGRESS.md` -- where the work stands, to resume across sessions.
* `tools/extract_requirements.py` -- regenerates the CSVs from the
  standards' text.
* `tools/` -- also the generators and checks CI runs: `build_icd_schema.py`,
  `build_sdd_components.py`, `build_test_specs.py`, `build_traceability.py`,
  `build_ics.py`, `build_matrix.py`, `check_drds.py` and `metrics.py`; and,
  run by hand, `measure_performance.py`, `remeasure_drag.py` and
  `unreached_code.py`.
* `audit/` -- the assessment rules `tools/build_matrix.py` reads;
  `validation/` -- the GMAT scripts and the generator of the validation
  references (`validation/make_gmat_references.py`), and the
  verification record of the analyses built on the 3D model
  (`validation/model-analyses-vv.md`).

* `gap_analysis.md`, `compliance_matrix.csv` (Phase 1; rebuilt by CI from
  `audit/`), `traceability_matrix.csv`, `ics_ccsds_502.csv`.
* `deviations.md` -- deviations D-01 to D-13 (D-08 to D-13 signed).
* `phase2_log.md`, `phase3_log.md` -- implementation and validation logs.
* `docs/` -- the DRD-based documents (Phase 4): SRS, ICD, SDD, CSD, SRF,
  SVerP, SValP, SUITP, SVS, SVR, SUM, SRelD, SDP, SMP, SPAP, SPAMR, the
  coding standard and the security analysis. `*_fields.md`, `*_cli.md`, `*_components.md` and
  `*_test_cases.md` are generated from the code by `tools/`; CI fails when
  they are out of date, and `tools/check_drds.py` checks every DRD section.
* `docs/dependability_safety_analysis.md` -- category C sign-off and failure modes (H04).
* `human_actions.md` -- what needs people (H01 to H13).
* `reviews/code_review_guide.md` -- the guide for the independent code review (H06).
* `review_log.md` -- findings of the whole-tool review (F-09 on).
* `performance.md` -- run time and memory on the reference PC (H13; `tools/measure_performance.py`).
* `metrics.md`, `metrics.json` -- the product metrics (`tools/metrics.py`).
* `unreached_code.md` -- the statements the tests do not execute
  (`tools/unreached_code.py`; reviewed in `review_log.md`).
* `drag_remeasure.md`, `drag_remeasure.json` -- drag figures re-measured
  after F-07 and F-09 (`tools/remeasure_drag.py`; SRelD K-01).
* `summary_report.md` -- the audit's result.

## Requirement CSV columns

| Column | Meaning |
|---|---|
| `ID` | ECSS: clause + letter (`5.2.2.1a`), the form ECSS-E-ST-40C Table R-1 uses; DRD contents add the DRD section (`D.2.1<5.2>a`). CCSDS: `CCSDS-502.0-B-3 <paragraph>`, and `ICS-<message>-<item>` for the Annex A conformance items. |
| `clause` | clause or paragraph of the standard |
| `requirement_text` | CCSDS: the text, abbreviated past 500 characters ("..."). ECSS: a reference, "<standard> <ID>: wording not reproduced (ECSS copyright); see the standard" (ECSS documents may not be reproduced without ESA's consent; `docs/legal/DATA_TERMS.md` D3) |
| `type` | process / product / functional / documentation (also: deleted, table) -- first pass, rule-based |
| `applicability` | first pass for the intended use and the proposed criticality category C; `basis` says which rule decided it |
| `earm_id` | the ECSS EARM identifier (ECSS-E-ST-40C, -Q-ST-80C, -E-ST-10-04C) |
| `level` | shall / should / may (ECSS); shall / should, or mandatory / optional / conditional for CCSDS conformance items |
| `crit_A` .. `crit_D` | ECSS-E-ST-40C Table R-1 and ECSS-Q-ST-80C Table D-2 cells, conditions kept as text |
| `page` | page of the PDF the requirement starts on |

`type` and `applicability` are a first pass: the gap analysis (Phase 1)
reviews them requirement by requirement and records the final decision in
`compliance_matrix.csv`.

## Regenerating the CSVs

The standards are licensed documents and are not kept in this repository.
Extract their text page by page (pages joined by `=== PAGE BREAK ===`, one
file per standard named as in `STANDARDS` in the tool), e.g. with pypdf:

```python
import pypdf
reader = pypdf.PdfReader("ECSS-E-ST-40C.pdf")
reader.decrypt("")  # the ECSS and CCSDS PDFs carry permission-only encryption
text = "\n\n=== PAGE BREAK ===\n\n".join(page.extract_text() or "" for page in reader.pages)
```

then run `python compliance/tools/extract_requirements.py <text dir>`.
