# Phase 1 plan: legal groundwork and website

Status: DRAFT for your review. Written 2026-11-09. No code was written and
nothing was changed except this file. This is not legal advice. Every
statement of fact has a source (a file in this repository, or a URL read on
the date shown). `VERIFIED` means: read from the official page on 2026-11-09.
`OPEN` means: I could not read the source. `UNVERIFIED` means: secondary source.

## 0. Read this first: eight findings that change the brief

| # | Finding | Why it matters | Needs |
|---|---|---|---|
| F1 | **The app is at 2.5.0, not 1.3.0.** `pyproject.toml` says 2.5.0. GitHub has 13 releases, `spacemissionstudio-v1.0.0` to `-v2.5.0` (2026-10-14 to 2026-11-08). | "Releases up to and including 1.3.0 stay under ISC" is wrong. All 13 releases are ISC. The EUPL starts with the *next* release. | Your decision: next version number, and a release of its own (Q1). |
| F2 | **The app's copyright notice names the AVS Lab, not you.** 266 of 270 Python files, `SpaceMissionStudio/LICENSE`, the `.deb` copyright file and the packaging scripts say "Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder". Basilisk's own `LICENSE` says 2016. | The AVS Lab did not write the app. The EUPL needs a licensor. Today the files name someone else. | Your decision on the copyright line (Q2) and a lawyer check. |
| F3 | **Codeberg Pages forbids this project.** Terms of Use § 2 (1) 7: "You must not share projects that mostly consist of code written by "generative AI"-tools (including services such as *Claude*, *OpenAI Codex*)." I read this myself: `https://codeberg.org/codeberg/org/raw/branch/main/TermsOfUse.md` (VERIFIED). Your README says Claude wrote the code. | The brief's default host is not safe. The rule is about "projects"; a site repository holding only generated HTML might pass, but this site is built from this AI-written code and says so. The sanction is "immediate removal of the content together with a warning". | Your decision (Q5). My advice: do not use Codeberg unless Codeberg confirms in writing. |
| F4 | **GitHub Pages logs visitor IP addresses.** "When a GitHub Pages site is visited, the visitor's IP address is logged and stored for security purposes, regardless of whether the visitor has signed into GitHub or not." `https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages`, "Data collection" (VERIFIED). | Confirms the brief: no GitHub Pages. | None. |
| F5 | **Git history holds a personal e-mail address (commit metadata).** 24 commits that touch `SpaceMissionStudio/` have author `ohexna` (address in the commit metadata, left out here); 55 have author `Claude`. | The brief says: confirm that you are the only human author. I cannot confirm that `ohexna` is you. | You confirm (Q3). History rewrite is your decision only. |
| F6 | **Verbatim standards text is in the repository.** `compliance/requirements/*.csv` (about 2,100 rows) holds requirement text from ECSS-E-ST-40C, ECSS-Q-ST-80C, ECSS-E-ST-10-09C, ECSS-E-ST-10-04C and CCSDS 502.0-B-3. `tests/data/ccsds/*.txt` holds 10 example messages copied from CCSDS 502.0-B-3 Annex G. | These documents have copyright owners. I have not yet read their reproduction terms. | See Q7 (more hosts to allow) and §10 R4. |
| F7 | **Several official sources are not reachable from this sandbox.** EUR-Lex answers with a bot challenge (HTTP 202, empty page). I did not try to get past it. `spdx.org`, `tmdn.org` and `euipo.europa.eu` do not resolve. | CRA, Product Liability Directive and Annex I of the dual-use regulation are not read from EUR-Lex. See §8 for what is verified and what is open. | Q7. |
| F8 | **The change history records the OS user name.** `history.py:default_author()` uses `getpass.getuser()`. The name goes into `*.history.jsonl` beside each scenario file. | Personal data can leave the computer when a user shares a scenario. Changing the default would change app behaviour. | Proposal only (§10 R6). |

## 1. Third-party licences in every package (M1)

### 1.1 What the three packages hold (from the repository)

| Package | Built by | Holds (source file) |
|---|---|---|
| Wheel and sdist | `packaging/build_wheel.sh`; `pyproject.toml` | The app's Python, 5 font files + 2 OFL texts, the Lucide icons + `LICENSE`, 2 space-weather files, `help/` copy of the manual, `fsw_export/basilisk_fsw_sources.zip` (72 Basilisk files, with Basilisk's `LICENSE`), C/CMake templates. Dependencies come from PyPI at install. |
| Linux `.deb` | `packaging/build_deb.sh`, `bundle_python.py` | Everything above, plus a private CPython 3.14.8, Basilisk 2.12.0, PySide6/Qt 6.11.2 (with Qt WebEngine), all pinned Python packages, 117 MB of Basilisk support data, 36 MB of Earth-orientation files, ITU-R P.676-13 data. |
| Windows setup program | `packaging/windows/spacemissionstudio.iss`, `bundle_python.py` | The same bundle. Its licence page shows `SpaceMissionStudio/LICENSE`. |

Existing evidence to reuse: `docs/THIRD_PARTY_ASSETS.md` (hand-written table;
its own text says "which of these ten derive from Feather was not checked"),
`packaging/constraints.txt` (45 pinned packages), the `.deb` `copyright`
file (a stanza list), `SPACEMISSIONSTUDIO_RUNTIME.json` in each bundle (file
hashes), `pip-audit` in CI.

### 1.2 Inventory approach

1. Build each package in CI as today. Unpack the finished artefact (wheel, `.deb` with `dpkg-deb -x`, installer with `innoextract` or from the staging folder `bundle_python.py` fills).
2. Walk the unpacked tree. Record every *file* with its SHA-256, then group files into components: Python distributions (from each `*.dist-info/METADATA` and `licenses/`), CPython, Qt/PySide6 shared libraries, Qt WebEngine and its Chromium notices, fonts, icons, JS assets, data sets.
3. Write one SBOM per package in **CycloneDX 1.6 JSON** (tool: `cyclonedx-py`, stdlib-only glue for non-Python parts). Each component: name, version, supplier, SPDX licence expression, copyright holder, source URL, hashes. CycloneDX, not SPDX, because it carries file hashes and component types well; I can also emit SPDX if you prefer.
4. Files that match no component fail the build ("unknown file").
5. `THIRD_PARTY_NOTICES` is *generated* from the SBOM plus a hand-kept `licenses/overrides.yaml` (for components with a licence only on a web page). Licence texts come from the packages themselves; SPDX texts only where a package ships none.

### 1.3 Obligations and the CI check

* A table per component: licence, what it requires on redistribution, how the package meets it. Written to `docs/legal/OBLIGATIONS.md` (generated).
* **LGPL-3.0 (Qt, PySide6, shiboken6):** ship as separate shared libraries, unmodified, with the LGPL and GPL texts, and make the matching source available. I propose: attach the exact source archives (`PySide6-6.11.2` sdist, Qt 6.11.2 source tarballs `qtbase`, `qtwebengine`, ...) to each GitHub release, with SHA-256. Qt source archives are large (`qtwebengine` includes Chromium; size not checked yet). GitHub's limit per release file is not verified here. The alternative is a written offer plus a stable link to `download.qt.io`. A written offer is weaker. **Open:** the exact Qt WebEngine/Chromium notices file and where it sits in the PySide6 wheel (to be read in M1).
* **Reference data:** a table for every data file: provider, terms, redistribution right, citation. Today `THIRD_PARTY_ASSETS.md` lists sources but not terms for NAIF, WMM2025, CERES albedo, EarthGRAM, NRLMSISE-00, GGM03S/GGM2B. I will read each provider's terms in M1. If a right is unclear I stop and ask.
* **In-app display:** Help › About › Third-party licences, fed from the bundled notices file. A new GUI element, so it needs the design rules in `CLAUDE.md` and your approval of the wording (it contains no legal text from me; it only shows the file).
* **CI gate** (`.github/workflows/spacemissionstudio-licences.yml`, new): regenerate the SBOM for the wheel on every push; for the `.deb` and installer on every release build. Fail on: unknown licence; licence not on `docs/legal/licence-allowlist.txt`; a component without its licence text in the package; a package without `LICENSE`, `LICENSE.de`, Basilisk's `LICENSE` and `THIRD_PARTY_NOTICES`.

### 1.4 First list of items that need attention (found by reading, not yet by scanning)

| Item | Why |
|---|---|
| PySide6 / Qt 6.11.2, Qt WebEngine (Chromium) | LGPL-3.0; Chromium brings many more licences; source-offer duty. |
| certifi, tqdm (MPL-2.0) | File-level copyleft; source of the MPL files must be available (they are on PyPI). |
| python-build-standalone libs (OpenSSL, SQLite, libffi, XZ, zlib, ncurses/libedit, others) | `THIRD_PARTY_ASSETS.md` says "as documented by python-build-standalone"; I have not read it. The `.deb` copyright file points to it. |
| CPython `LICENSE.txt` | PSF-2.0 plus older licences; must be shipped (it is, per the `.deb` copyright file). |
| Lucide icons | The file says ISC + MIT for Feather-derived icons; 10 added icons were "not checked". |
| NAIF kernels, CelesTrak SW-All.txt, NASA MSFC file, ITU-R P.676-13 text, WMM2025, CERES, EarthGRAM, NRLMSISE-00, GGM03S/GGM2B | Redistribution terms not recorded. CelesTrak: README quotes Dr. Kelso (only the URL is asked). ITU-R: ITU copyright; redistribution of the data file by this project **needs a source** (`data-and-standards.md` says it is fetched at build time and bundled). |
| `fsw_export/basilisk_fsw_sources.zip` | 72 Basilisk files (ISC, AVS Lab © 2016) inside the wheel; ISC text is in the zip. Make sure the wheel itself carries it too. |
| Wheel metadata | `license = { text = "ISC" }` and no `license-files`; the wheel may not carry `LICENSE` at all. To check in M1 by listing the built wheel. |

## 2. Licence change to EUPL-1.2 (M2)

### 2.1 Authorship check (done as far as I can)

`git log -- SpaceMissionStudio` shows two author identities: `ohexna` (address in the commit metadata, left out here) (24 commits) and `Claude <noreply@anthropic.com>` (55). Co-author trailers: `Co-Authored-By: Claude ...` (Opus 5.5, Sonnet 5.5) and `Co-authored-by: Claude`. No other human. **Open:** is `ohexna` you? (Q3.) The upstream Basilisk commits before the fork are by others; they are outside `SpaceMissionStudio/`.

### 2.2 Basilisk-derived material

* I compared all 3,613 upstream files of 200 bytes or more (everything outside `SpaceMissionStudio/`, by SHA-1) with every file in `SpaceMissionStudio/`: **0 byte-identical copies**. This is only the first test.
* M2 adds: (a) a normalised line-level similarity scan (`difflib`/ScanCode) of every `SpaceMissionStudio/` source file against the upstream tree and against the 72 files in the FSW zip; (b) a read of `scripts/vendor_basilisk_fsw.py`, `spacemissionstudio/fsw_export/templates/*` and `examples/` (five scripts, possibly adapted from Basilisk examples, which AGENTS.md says exist); (c) a check of the pinned `bsk==2.12.0` wheel `LICENSE` against the zip's `LICENSE` (the zip's says "Copyright (c) 2016, Autonomous Vehicle Systems Lab"). Any hit: keep ISC + AVS Lab notice, header `EUPL-1.2 AND ISC` if adapted.
* The 266 files with the AVS Lab header need a decision (Q2). Basilisk's ISC condition covers only copied or adapted code. A header that gives the AVS Lab as holder of work it did not write is wrong whichever licence applies. Proposal: replace in all 266 files with your copyright line + `SPDX-License-Identifier: EUPL-1.2`, except files the scan marks as derived.

### 2.3 Steps

1. Download EUPL-1.2 English and German from the Commission and from SPDX; record URL, date, SHA-256. **Status:** a helper agent already fetched them (scratch only, not in the repository). The Commission text (14,152 bytes) and the SPDX text (13,792 bytes) differ only by a leading byte-order mark and some trailing whitespace on my comparison (VERIFIED by diff of whitespace-normalised lines). The brief says "byte for byte": the two official sources are not byte-identical to each other. **Decision for you (Q4):** use the Commission file as published (with BOM) or the SPDX file. I recommend the SPDX text, because it is the plain-text form used by tooling, and I record both hashes.
2. Add `LICENSE` (English), `LICENSE.de` (German), `LICENSES/` with SPDX texts for ISC, OFL-1.1, etc. (REUSE layout).
3. Replace the 266 headers (script, one commit, reviewable by diff). Headers carry `SPDX-License-Identifier`.
4. Update `pyproject.toml` (`license = "EUPL-1.2"`, `license-files`), the `.deb` copyright file, the Inno `.iss` licence page (EUPL + Basilisk ISC + notices), README (licence section, badge), `CONTRIBUTING.md`, About dialog, every place that says "ISC, like Basilisk" (grep list in M2).
5. README and CHANGELOG state: releases 1.0.0 to 2.5.0 are ISC; EUPL-1.2 from the next release; EUPL applies to the app only; Basilisk stays ISC.
6. Add a test that every source file has an SPDX header (CI).
7. Compatibility table (EUPL-1.2 vs each component) — see below.

### 2.4 Facts from the licence text (VERIFIED, 2026-11-09, text of EUPL-1.2 English; quotations)

* Article 5, attribution: "The Licensee shall keep intact all copyright, patent or trademarks notices and all notices that refer to the Licence and to the disclaimer of warranties."
* Article 5, compatibility: lets a licensee combine EUPL work with a work under a "Compatible Licence" listed in the Appendix and distribute under that licence.
* **Appendix list (VERIFIED):** GPL v2, v3; AGPL v3; OSL v2.1, v3.0; EPL v1.0; CeCILL v2.0, v2.1; MPL v2; **LGPL v2.1, v3**; CC BY-SA 3.0 (non-software); EUPL v1.1, v1.2; LiLiQ-R, LiLiQ-R+. ISC, MIT, BSD, Apache-2.0, PSF-2.0, OFL are **not** in the Appendix; they are permissive, and my reading is that the EUPL's own terms do not conflict with them. That is my reading, not a verified statement of the Commission. **Open:** the Commission's EUPL Q&A pages on permissive and LGPL combinations (not yet read). Lawyer item.
* Article 7: "the Work is provided under the Licence on an 'as is' basis and without warranties of any kind".
* Article 8: "Except in the cases of wilful misconduct or damages directly caused to natural persons, the Licensor will in no event be liable ... However, the Licensor will be liable under statutory product liability laws as far such laws apply to the Work."
* Article 14: litigation between other parties "will be subject to the exclusive jurisdiction of the competent court where the Licensor resides or conducts its primary business."
* Article 15: "this Licence shall be governed by the law of the European Union Member State where the Licensor has his seat, resides or has his registered office". For you: German law.
* **Consequence to tell the lawyer:** Article 8 keeps liability for "damages directly caused to natural persons" and under "statutory product liability laws". The warranty notice (§10 R1) cannot remove that.

## 3. AI authorship and provenance (M3)

* Keep the README note. Reuse it word for word on the site.
* Run **ScanCode Toolkit** (`pip install scancode-toolkit`, PyPI reachable: tool check pending) over `SpaceMissionStudio/` with licence, copyright, email and URL detection; run `reuse lint` after M2; run the similarity scan from §2.2. Output goes to `docs/legal/provenance/` (JSON + a table). Every match: file, line, proposal (remove, rewrite, attribute).
* Known likely matches already seen: the 266 AVS Lab headers; Lucide/Inter/JetBrains licence files (expected); CCSDS example messages and the standards CSVs (§0 F6); GMAT script patterns; IERS C04 excerpt (its header names a person's e-mail address; not repeated here).
* Notices name you as licensor only. No wording that implies Anthropic endorsement.
* A point for the lawyer, not for me: whether AI-generated code is protected by copyright at all, and what that means for the EUPL grant and for Article 6 (chain of authorship: the Licensor "guarantees that the copyright in the Original Work ... is owned by him/her or licensed to him/her"). I will not write about this in any user-facing text.

## 4. Real assets for the website (from the repository)

| Need | Path |
|---|---|
| Colour tokens | `spacemissionstudio/gui/theme/tokens.py` (light accent `#2563EB`, dark `#4C8DFF`; derived tokens by `mix()`; contrast pairs in `CONTRAST_PAIRS`) |
| Type and spacing | `gui/theme/typography.py` (sizes 11/12/13/15/18/22, weights 400/500/600) |
| Fonts | `gui/assets/fonts/inter/Inter-{Regular,Medium,SemiBold}.ttf` + `OFL.txt`; `gui/assets/fonts/jetbrains-mono/JetBrainsMono-{Regular,Medium}.ttf` + `OFL.txt`. TTF only; build.py converts nothing (no new tool); the site serves TTF (about 300 KB each family, to measure) or WOFF2 if `fonttools` + `brotli` are accepted as a build-time tool (Q10). |
| Rail icons (`main_window.py:789`) | Home `house`; Scenario `file-text`; Run `play`; Results `chart-line`; Timeline `chart-gantt`; Reports `file-output`; bottom: Help `circle-help`, Settings `settings`. SVGs in `gui/assets/icons/lucide/` with `LICENSE`. |
| App icon | **Does not exist.** `packaging/spacemissionstudio.desktop.in` says `Icon=spacemissionstudio`, but no such file is in the repository (searched all `*icon*` names). The Windows shortcuts use `python.exe`'s icon. The header of the site therefore shows the name only, or the banner's mark if `banner.svg` has one (to check). Making a new app icon is a design decision for you (Q13). |
| Banner | `docs/images/banner.svg` is **stale**: it sets text in IBM Plex Sans (removed from the app in 1.1.0, `THIRD_PARTY_ASSETS.md`) with hard-coded colours (`#002D9C`) and a drawn satellite mark. It does not match the Inter/token look. I will not reuse it on the site; the page header will use Inter and the tokens. Whether to update the banner in the README is your call. |
| Screenshot harness | `scripts/capture_ui_screens.py` (template 23, both themes, offscreen). Existing sets in `docs/ui/screenshots/{before,after}`. |
| Screenshots in docs | `docs/images/*.png` (scenario editor, budget, compare, etc.) |
| Facts | Version: `pyproject.toml`; Basilisk: `dependencies.py` (`2.12.0`); templates: 32 JSON files in `scenarios/templates/`; releases: `CHANGELOG.md`. |

No draft `site/index.html` exists in the repository, so there is no claude.ai draft to reuse. I will write the structure from your outline.

## 5. Facts the site will state, with source

| Statement | Source |
|---|---|
| Name, one-line description | `README.md` ("A desktop app for planning and simulating satellite missions, built on the Basilisk astrodynamics framework") |
| Basilisk 2.12.0 | `dependencies.py` `QUALIFIED_BASILISK_VERSION` |
| 32 templates | count of `scenarios/templates/*.json`; README says "32 template missions" |
| Offline installers (Linux `.deb`, Windows setup) with own Python, Basilisk, data | `packaging/README.md`, README "Platforms" |
| "Validated against GMAT" | **Not as worded.** `capabilities.md` says "the validation runs against GMAT, IERS and SOFA" and `README.md` says GMAT is "used as a reference to validate the app (time scales, propagation, CCSDS files)". The site will say: "Checked against GMAT for time scales, propagation and CCSDS files" and link `compliance/`. Your rule: no "validated" unless documentation says exactly that. |
| No telemetry, no update check, downloads only on request | `docs/reference/network.md` |
| Licence | README after M2 |
| AI-authorship note | README (verbatim) |
| Fonts and icons credits | `docs/THIRD_PARTY_ASSETS.md` |
| First-run steps | README "Quick start" (template 22, Run `Ctrl+R`, Results, Timeline). The README says "four ground passes over Berlin": **the site will not.** |
| Release pill | CHANGELOG section of the current version |

## 6. Page outline and screenshots

Your outline stands. Changes I propose:

1. Header, hero, four facts, area-by-area, get started, documentation, footer as you wrote. Facts row: "Basilisk 2.12.0", "32 templates", "Offline installers", "Checked against GMAT". The fourth is the wording above.
2. Hero visual: the draft orbit diagram does not exist. I propose a plain product screenshot instead, no diagram.
3. Screenshots from `capture_ui_screens.py`, template 23, with a temporary home directory. **Problem:** template 23 names "Berlin" in the Timeline, the link-budget page and the ground-station editor. Options for you (Q6): (a) use another template for screenshots, but 22 and 23 both use Berlin and templates must not change; (b) crop to avoid the station name; (c) use screens that do not show it (Home, Scenario ▸ Spacecraft, Results ▸ orbit plot, Reports). I advise (c) plus (b) for the Timeline.

| Section | Screenshot (light + dark) |
|---|---|
| Hero | Scenario area with template 23 loaded, spacecraft page |
| Home | Home with template cards (`001_start_templates`) |
| Scenario | Spacecraft ▸ Orbit & mass |
| Run | Run page during a run |
| Results | Results ▸ orbit plot (3D or ground track: check for the station name) |
| Timeline | Cropped Timeline without station labels |
| Reports | Reports page |

## 7. Hosting

### 7.1 Codeberg Pages (the brief's default)

VERIFIED 2026-11-09 from `docs.codeberg.org` and `codeberg.org/codeberg/org` (Terms, Privacy Policy, Imprint, FAQ), read by a helper agent and spot-checked by me (the AI clause and the log retention).

* Operator: Codeberg e.V., Arminiusstraße 2-4, 10551 Berlin; registered at Amtsgericht Charlottenburg, VR36929; non-profit since 2020-06-23 (Imprint).
* Servers: "All servers of Codeberg e. V. are physically located in Germany" (Privacy Policy § 4). The FAQ says most services run on own hardware in a rented facility in Berlin; backups and some tasks are at netcup GmbH and Hetzner Online GmbH.
* Logging: technical metadata includes IP address, browser and OS, date and time, URL and referrer. "When stored in logs, the IP address is truncated" and "not stored for more than 7 days or as required by German legislature" (Privacy Policy § 3.1(4), § 5(3)). **No Pages-specific statement exists** (OPEN).
* Service state: Pages moved to "git-pages" in December 2025; the old server stops serving on 2026-12-31 (`docs.codeberg.org/codeberg-pages/migrating-from-pages-v2/`). Docs are "work in progress". No availability guarantee (Terms § 3(3)).
* Deployment from GitHub Actions: possible with `git-pages-cli` and a token. The CLI documentation asks for `read:user` and `write:repository`. A token limited to one repository can only hold repository and issue scopes, so it may not work (needs a test; OPEN). The older Codeberg doc says tokens "grant full access to your account".
* **Against:** Terms § 2 (1) 7 (F3).

### 7.2 German alternative

*Filled in below when the research finishes.* See §7.3.

### 7.3 Facts on a German static host

PENDING_HOSTING_RESEARCH

### 7.4 My advice

Do not rely on Codeberg. Use a German host with logging off (or IPs not stored). Ask Codeberg's board (via `contact@codeberg.org`) whether the rule would apply to a repository that holds only the generated HTML, if you want Codeberg anyway; do not deploy before you have the answer in writing.

## 8. Official sources: what is verified and what is open

| Topic | Result |
|---|---|
| EUPL-1.2 text, Appendix, Articles 5, 7, 8, 14, 15 | VERIFIED (§2.4). German text fetched; title "OPEN-SOURCE-LIZENZ FÜR DIE EUROPÄISCHE UNION v. 1.2". URL of each download: not recorded by the helper; **I will re-fetch and record URLs and hashes at the start of M2.** |
| SPDX identifiers (`EUPL-1.2`, `ISC`, `OFL-1.1`, `LGPL-3.0-only`, `PSF-2.0`, `MIT-CMU`, `MPL-2.0`) | OPEN: `spdx.org` does not resolve. I will read `github.com/spdx/license-list-data` through `raw.githubusercontent.com` (reachable) in M1. |
| Cyber Resilience Act (EU) 2024/2847; Product Liability Directive (EU) 2024/2853 | OPEN. EUR-Lex gives a bot challenge. I stopped. Application dates in your note (CRA 11 Sep 2026 and 11 Dec 2027; PLD 9 Dec 2026) are **neither confirmed nor refuted.** |
| Dual-use Regulation (EU) 2021/821, Annex I | PARTLY VERIFIED through BAFA, which hosts the text of the current Annex I (OJ L, 14.11.2025, Delegated Regulation (EU) 2025/2003, `data.europa.eu/eli/reg_del/2025/2003/oj`): Category 9 "Luftfahrt, Raumfahrt und Antriebe" exists; 9A004 covers spacecraft and on-board and ground equipment; 9D001 covers "software" specially designed or modified for the development of equipment in 9A001-9A119, 9B or 9E003; the definition of „Allgemein zugänglich" (in the public domain): technology or software "available without restriction on its further dissemination (copyright restrictions do not remove public-domain status)" (my translation of the German text); the General Technology Note says the technology export restrictions "do not apply to public-domain information or basic scientific research". BAFA page of 2026-09-16: a new delegated regulation of 2026-09-14 updates Annex I; it is expected to apply from November 2026. I do **not** judge whether any app function is listed. |
| Trademark registers (DPMA, EUIPO, USPTO, WIPO) | OPEN: JavaScript search apps; two hosts do not resolve here. See §10 R5. |
| ECSS and CCSDS copyright terms | OPEN: hosts not allowed (Q7). |
| Hosting providers (Uberspace etc.) | see §7.3 |

## 9. Anything commercial found

Nothing to remove. I searched the repository text for donate, sponsor, buy, paypal, patreon, ko-fi, pricing, affiliate and newsletter: the only hits are unrelated words in IDM-CIC documentation. There is no `FUNDING.yml`, no price, no paid support. The repository's pull-request template and CODEOWNERS are Basilisk's (see §10 on `.github`).

## 10. Risk register, first version (facts only; nothing changed)

Format for each area: **Facts** / **Measures planned** / **Open and who decides**. The final file is `docs/legal/RISK_REGISTER.md`, built in M4.

**R1 Liability for use of results.** Facts: README/docs state no warranty only through the ISC text; the app can generate a flight-software C project (`fsw_export/`); `docs/reference/limitations.md` lists model limits; the compliance records say they are "not a certification". EUPL Art. 7 and 8 as in §2.4. Measures: propose (not insert) a short notice for README, docs, About dialog, first start (acknowledged once); a stronger notice for the C export and the generated project's README; the second changes generated output, so it waits for your approval. Open: wording is yours; a lawyer should check Art. 8 (liability for damage to natural persons and product liability stays).

**R2 Export control.** Facts: §8 (BAFA, Annex I). Code and docs are public in an open repository. The app simulates spacecraft, attitude control, and generates flight software (C code from Basilisk modules). Measures: keep everything public; nothing private; no tailored help to foreign organisations. I list features by Category 9 headings for BAFA in M4 without a verdict. Open: BAFA or a lawyer decides (you contact BAFA).

**R3 Third-party data in the repository.** Facts: `tests/data/ccsds/*` from CCSDS 502.0-B-3 Annex G; `tests/data/validation/eopc04_excerpt.txt` (IERS C04 as shipped with GMAT; header has a person's e-mail); GMAT scripts in `compliance/validation/gmat/` and their numeric outputs in `tests/data/validation/gmat/`; `spacemissionstudio/data/spaceweather/SW-All.txt` (CelesTrak; README: CelesTrak asks only for the URL) and the NASA MSFC file ("a NASA work, so not subject to copyright in the US"); IDM fixtures are declared synthetic. No real TLEs were found in templates (grep for `NORAD`, `OBJECT_NAME` found only CCSDS and compliance files). Measures: a table of source and terms for each; replace unclear data with synthetic data after your yes. Open: GMAT licence and the GMAT-output reuse; IERS terms; CCSDS reuse.

**R4 Standards text.** Facts: F6. `compliance/requirements/*.csv` has ECSS and CCSDS clause text. Measures: read the owners' reproduction terms (Q7); propose references plus short quotation only. Open: lawyer. Replacement would break the compliance tooling (`extract_requirements.py`, `build_matrix.py`) so I will not do it without your yes.

**R5 Name and trademarks.** Facts (web search, snippets only, not the registers): no third-party product, company or mark named "SpaceMissionStudio" or "Space Mission Studio" found. PyPI and npm have no such package (VERIFIED by HTTP 404 on 2026-11-09). **Similar:** `spacestudio` by Exotrail (France), mission-design and simulation software, on the Altair Partner Alliance; a Payload Space article reportedly says Exotrail's product names are trademarked; a USPTO record SPACESTUDIO, serial 79368484, class 042, found through a Justia page snippet. These are leads, not verified. Also "Mission Studio" (a web simulator, mirrored on GitHub). Measures: register search by hand (instructions below), report with links. Open: you run the register searches; a trade-mark lawyer judges likelihood of confusion with `spacestudio`.

Manual search steps: TMview (tmdn.org/tmview), DPMAregister (register.dpma.de), EUIPO eSearch plus, USPTO trademark search, WIPO Global Brand Database. For each: word "SPACEMISSIONSTUDIO" and "SPACE MISSION STUDIO", classes 9 and 42, "contains" and "similar".

**R6 Personal data and secrets.** Facts: no secrets found by a regex scan of the SMS history (GitHub-token, AWS key, private key, Slack token and password patterns: 0 hits); `gitleaks` is not installed and its release page is blocked here. Commit metadata holds a personal e-mail address. One third-party person's e-mail is in a test-data header (IERS). `HISTORY.md` mentions `/home/<user>/...` as a placeholder. In the app: `history.default_author()` writes the OS user name into `*.history.jsonl`; logs are in `~/.spacemissionstudio/logs/`; provenance files record versions and hashes (I saw no host name or user name in `output_provenance.py`; to confirm by a run in M4). Measures: run gitleaks or `detect-secrets` (PyPI) over tree and history in M4; fix the tree; report history. Open: history rewrite is your decision. The default-author change is an app change: proposal only.

**R7 Privacy inside the app.** Facts: `docs/reference/network.md`: no telemetry, no crash upload, no update check; downloads only on a user action, with listed hosts (raw.githubusercontent.com, naif.jpl.nasa.gov, lambda.gsfc.nasa.gov, hanspeterschaub.info, celestrak.org, ...); a guard and a CI network audit (`scripts/network_audit.py`) enforce it. Measures: re-run the audit in M4; make sure the user manual lists every action and destination; check that logs and exports hold no user name or home path. Open: none known.

**R8 Security and supply chain.** Facts: `pip-audit` runs in CI; dependencies pinned in `packaging/constraints.txt`; release builds make `SHA256SUMS-linux` and `SHA256SUMS-windows`; Windows installer is unsigned (stated in the workflow). No `SECURITY.md` anywhere in the repository. Measures: add `SECURITY.md` (private reporting through GitHub, which you must switch on); Sigstore signing of release files with the GitHub OIDC identity (free; to verify in M4); dependency scanning exists, extend to the SBOM; propose Windows code signing (costs money) without adopting it. Open: GitHub setting is yours. GitHub only shows a `SECURITY.md` at the repository root, `.github/` or `docs/` — **not** inside `SpaceMissionStudio/`. That is outside your folder (Q8).

**R9 Contributions.** Facts: `CONTRIBUTING.md` asks for an ISC header; the PR template (`.github/pull_request_template.md`) belongs to Basilisk and its text is about tickets and review. No DCO check exists. Measures: DCO sign-off check in the SMS workflow (new job, only for paths in `SpaceMissionStudio/`); `CONTRIBUTING.md` says contributions are accepted under EUPL-1.2. A PR-template line for DCO would change a Basilisk file (Q8).

**R10 Repository presentation.** Facts: README says "Licence ISC" in a badge; claims "validate the app" for GMAT (see §5); no third-party logo is shown in the README (not yet checked in the About box); "© CNES" is named only to state the origin of a file format (`data-and-standards.md`: "not affiliated with or endorsed by CNES" — that sentence already exists for CNES). Measures: wording review in M4; non-affiliation sentence for NASA, ESA, AVS Lab, CU Boulder, CNES. Open: your approval of the wording.

**R11 The Windows/Linux installers carry reference data.** Facts: `.deb` bundles 117 MB + 36 MB of data (Basilisk support data, NAIF, EOP, ITU). Terms for each not yet read. Part of M1.

**R12 Non-commercial status.** Facts: none found (§9). Measures: a CI grep for FUNDING files and price words; rule in `CONTRIBUTING.md`. Note: the CRA and Product Liability Directive text on "outside the course of a commercial activity" could not be read (F7).

**R13 Website privacy.** Facts: hosts in §7. Measures: M5-M6 as the brief says; `DATA_FACTS.md` after the host is chosen.

## 11. Milestones

| M | Content | Output | Your input |
|---|---|---|---|
| M1 | Inventory (3 SBOMs), notices, obligations, data-terms table, LGPL source plan, CI gate, About ▸ Third-party licences | `docs/legal/`, workflow, notices | Approve LGPL source attachment; approve About wording |
| M2 | EUPL change, headers, metadata, README, history statement | `LICENSE`, `LICENSE.de`, 266 headers | Q1-Q4; lawyer check on copyright line |
| M3 | Provenance scan and fixes | `docs/legal/provenance/` | Decisions on each replacement |
| M4 | Register measures: data, standards, secrets, app privacy, security, DCO, notices | `RISK_REGISTER.md`, `SECURITY.md`, workflows | Wording; GitHub settings |
| M5 | Website build (`site/build.py`, CSS from tokens, icons, fonts, screenshots, pages, CI freshness check) | `site/` | Screenshot choice (Q6) |
| M6 | Hosting and deployment | workflow, secret | Host choice, account, token; Impressum and Datenschutz texts |

Order note: M5 can run before M2-M4 if you want the site early, but its footer states the licence, so I prefer M1-M2 first.

## 12. Questions for you

1. Next version number, and does the licence change get its own release? (F1) My advice: yes, its own minor release.
2. Which copyright line goes in the files and `LICENSE`? (F2) For example "Copyright (c) 2026, <your name or pseudonym>". A name appears in every file and in the package; this makes it public. A lawyer should confirm the form.
3. Is `ohexna` (address in the commit metadata, left out here) you, and the only human author? Do you accept that the address stays in history (F5)?
4. EUPL text: use the Commission file or the SPDX file? (§2.3) My advice: SPDX text, with both hashes recorded.
5. Hosting: German host, or Codeberg after written confirmation? (F3)
6. Screenshots: option (c) plus crop for the Timeline? (§6)
7. May I add more hosts to the sandbox allowlist: `ecss.nl`, `public.ccsds.org`, `ccsds.org`, `www.itu.int` (already allowed), `www.cnes.fr`, `nssdc.gsfc.nasa.gov`, `qt.io`, `doc.qt.io`, `download.qt.io`, `registry.npmjs.org`; and do you accept that EUR-Lex stays unread until you provide the three texts (CRA, PLD, Annex I) or allow another official route?
8. `SECURITY.md` and the PR-template change live outside `SpaceMissionStudio/`. The brief says only this fork's README section and workflows may change there. Allow `SECURITY.md` at the root and a DCO line in the PR template, or keep them in `SpaceMissionStudio/` where GitHub will not show them?
9. Custom domain or not? (Changes the data facts.) My advice: no domain at first.
10. WOFF2 conversion at build time (adds `brotli` as a build-only tool), or serve the TTF files as they are?
11. Impressum and Datenschutz texts: when `DATA_FACTS.md` exists I will ask. Non-affiliation, no-warranty and not-for-operational-use wording: I will draft in M4; you approve.
12. May I save your brief as `docs/LEGAL_AND_WEBSITE.md` in the repository? It is not there now.
13. App icon: the site header shows the name only, or do you want a new app icon designed (it would also need to go into the app and the installers, which is an app change)?
