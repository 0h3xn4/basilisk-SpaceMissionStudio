# Provenance scan of SpaceMissionStudio

Milestone M3 of [`PHASE1_PLAN.md`](PHASE1_PLAN.md). Not legal advice. The
question: did third-party licence texts, copyright notices or code reach the
app's own files without the right attribution?

## Method

| Step | Tool and scope | Date |
|---|---|---|
| 1 | Line-similarity scan: every tracked text file of `SpaceMissionStudio/` (796 files; lines of 30 characters or more, comments, imports and licence boilerplate left out) against every tracked file of upstream Basilisk in this repository (2,442 files) | 2026-11-10 |
| 2 | `git log --diff-filter=R`: files moved into `SpaceMissionStudio/` from elsewhere | 2026-11-10 |
| 3 | ScanCode Toolkit 32.5.0 (licence list SPDX 3.27), `scancode -clpe` (licences, copyrights, packages, e-mails) over `git archive HEAD SpaceMissionStudio` at the M2 head: 1,548 files, 0 scan errors | 2026-11-10 |

ScanCode was installed with `pip install scancode-toolkit-mini` in its own
environment, Python 3.12; it needs `pluggy` 1.5.0 (1.7 cannot load its
plugins). The JSON result (4 MB) is not committed; the command above
reproduces it.

## Results

* **No third-party code in the app's files.** Step 1: no file shares more
  than 13 lines with Basilisk; the shared lines are Basilisk API calls (for
  example `spacecraft.Spacecraft()`, `orbitalMotion.ClassicElements()`, the
  `Reset`/`UpdateState` signature of a Python module). Step 2: no file was
  moved in from upstream. Step 3: every copyright notice in the app's source
  files is the project's own; third-party holders appear only in licence
  texts, notices, packaging records and the font files, where they belong.
* **One problem in the project's own header, fixed.** The first EUPL header
  (M2) also mentioned the ISC releases and Basilisk's licence; ScanCode read
  597 files as "EUPL-1.2 AND ISC". The header now names only the file's own
  licence (finding P-1).

## Findings

| # | Where (file:line) | What ScanCode or the scan found | Assessment | Action |
|---|---|---|---|---|
| P-1 | 610 source files, lines 10-14 | "EUPL-1.2 AND ISC" | the header text, not a second licence | **Fixed** in M2 (header names only the EUPL) |
| P-2 | `spacemissionstudio/fsw_export/templates/*.c`, `*.h`, `_isc_c.txt`: lines 2-16 | ISC, "Copyright (c) 2026, Autonomous Vehicle Systems Lab" | the text the export writes into the generated C project; the AVS Lab did not write these templates | **Open:** proposal P1 in `OBLIGATIONS.md` (changing it changes generated output) |
| P-3 | `spacemissionstudio/fsw_export/generate.py:222-224`, `documents.py:117,261-262`, `catalog.py:101` | ISC | the generated project's statement that Basilisk's files and the message files made from Basilisk's templates are ISC | Correct attribution; no action. The "generated files carry the same ISC licence" sentence (`documents.py:261-262`) is part of P1 |
| P-4 | `compliance/requirements/*.csv`, `compliance/compliance_matrix.csv` | copyright fragments (for example `CCSDS-502.0-B-3.csv:14`) | requirement text reproduced from ECSS and CCSDS standards | **Open:** decisions D3 and D5 in `DATA_TERMS.md` |
| P-5 | `tests/data/ccsds/*.txt` | (none detected) | ten example messages copied from CCSDS 502.0-B-3 Annex G (their README says so) | **Open:** D5 |
| P-6 | `tests/data/validation/eopc04_excerpt.txt:6` | a person's e-mail address | the IERS C04 file header, kept as published | **Open:** D7 (replace the fixture with synthetic data, or keep with attribution) |
| P-7 | `packaging/legal/*`, `spacemissionstudio/legal.py`, `gui/licences_dialog.py`, `gui/theme/fonts.py:20`, `gui/theme/icons.py:18`, `packaging/bundle_python.py:113,230,262`, `tests/test_dependencies.py`, `tests/test_hashed_installs.py`, `tests/test_legal.py`, `tests/test_licences_tool.py`, `tests/gui/test_licences_dialog.py`, `tests/gui/test_theme.py:120,126`, `tests/gui/test_main_window.py:1928` | licence names (ISC, MIT, LGPL-3.0, OFL-1.1, ...) | the licence tool, its data and tests, and docstrings that name the licence of a bundled asset | None: intended |
| P-8 | `packaging/legal/licences.py:24-25` | "JSON" licence | a false positive on the words "sbom.cdx.json" in the docstring | None |
| P-9 | `packaging/legal/texts/**`, `LICENSE`, `LICENSE.de`, `THIRD_PARTY_NOTICES`, the fonts' `OFL.txt`, Lucide's `LICENSE`, the `.deb` copyright file | third-party licences, holders and their e-mail addresses | licence texts and notices shipped on purpose (M1) | None: intended |
| P-10 | `HISTORY.md:5396` | "copyright 2025, NTNU" | a sentence that a Basilisk module (by NTNU) was **not** used | None |

## What the scan cannot show

A licence scanner finds texts and notices, and the similarity scan finds
copied lines. Neither proves that no code was rewritten from a source line
by line, or that an AI model did not reproduce code it learned from. The
README's AI-authorship note states how the code was written; a lawyer can
advise whether more is reasonable (risk register, M4).

## Status

No open finding about third-party **code**. Open items are owner decisions
already listed elsewhere: P1 (generated C project's notice), D3 and D5
(standards text), D7 (IERS fixture).
