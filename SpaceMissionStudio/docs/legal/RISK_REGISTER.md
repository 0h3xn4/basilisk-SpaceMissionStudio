# Legal risk register

Milestone M4 of [`PHASE1_PLAN.md`](PHASE1_PLAN.md) (§10 there lists the
areas). Status of 2026-11-10. **Not legal advice.** The owner decided not
to involve a lawyer (`docs/DECISIONS.md`, the owner's answers of
2026-11-10, Q5). Every point below that the plan gave to a lawyer is
therefore marked **owner's accepted risk**: the risk is known and
written down, and no lawyer has checked it.

Each entry has the facts, what was done, and what is open. "Owner" means
a step that only the repository owner can take (a setting, an e-mail, a
decision). Sources are the ones named in the plan and in
[`OBLIGATIONS.md`](OBLIGATIONS.md), [`DATA_TERMS.md`](DATA_TERMS.md) and
[`PROVENANCE.md`](PROVENANCE.md).

## Summary

| # | Area | State | Open for the owner |
|---|---|---|---|
| R1 | Liability for the use of results | EUPL Articles 7 and 8 apply; no-warranty sentence (W2) in the READMEs, the manual and the About box; W3 rejected | none (owner's accepted risk) |
| R2 | Export control | everything is public; no classification made | ask BAFA, or accept the risk |
| R3 | Third-party data in the repository | terms read where reachable (D1 to D7) | D2 to D7 |
| R4 | Standards text (ECSS, CCSDS) | ECSS forbids reproduction without consent | D3, D5 |
| R5 | Name and trademarks | no register search made | run the searches |
| R6 | Personal data and secrets | scanned: no secret; one third-party address in test data | none required |
| R7 | Privacy inside the app | no telemetry; two places store a user name or a path; P2 declined | none (owner's accepted risk) |
| R8 | Security and supply chain | `SECURITY.md`, signed provenance, hashes | switch on private reporting |
| R9 | Contributions | sign-off checked for forks | none |
| R10 | Repository presentation | non-affiliation sentence (W1) in the READMEs and the manual | none |
| R11 | Third-party files in the installers | Linux gate fails on any gap; Microsoft runtime verified (D10); Windows gate in warn mode until a full build is clean | switch the Windows gate to fail mode |
| R12 | Non-commercial status | a test fails on funding links | none |
| R13 | Website | cancelled (Q7) | none |

## R1 Liability for the use of results

**Facts.** The app is licensed under the EUPL-1.2. Its Article 7
(Disclaimer of Warranty) and Article 8 (Disclaimer of Liability) apply
to every copy. Article 8 keeps the licensor liable for damage caused
directly to natural persons and under statutory product liability
law. The app can generate a flight-software C project (`fsw_export/`).
[`docs/reference/limitations.md`](../reference/limitations.md) lists
the model limits. The README says the compliance records are "not a
certification".

**Done.** Three short sentences are drafted for approval: no warranty,
not qualified for flight, and non-affiliation. Each draft lists where it
could go and what that changes. See [`WORDING_DRAFTS.md`](WORDING_DRAFTS.md).
Nothing has been inserted.

**Decided (owner, 2026-11-10).** W1 and W2 are approved and used: the
READMEs and the user manual's introduction carry both sentences, and the
About box carries W2 (`legal.NO_WARRANTY`, tested). W3 (the generated
flight-software project's README) is rejected: the generated project is
unchanged.

**Open.** How Article 8 applies to a free, non-commercial project is an
**owner's accepted risk**.

## R2 Export control

**Facts.** Plan §8: Category 9 of Annex I of Regulation (EU) 2021/821
(text read on BAFA's site) lists spacecraft equipment (9A004) and
software specially designed for its development (9D001). The General
Technology Note excludes information "in the public domain". The
repository and its releases are public, and nothing is kept private.
The app simulates spacecraft orbits and attitude control and generates
C code from Basilisk's open flight-software modules. No classification
was made. That judgement belongs to BAFA.

**Done.** Nothing private exists. Everything stays public.

**Open.** The owner can ask BAFA for a ruling on the app. If the owner
does not ask, this is an **owner's accepted risk**.

## R3 Third-party data in the repository

**Facts.** See [`DATA_TERMS.md`](DATA_TERMS.md):

- **ITU file (D1):** no longer bundled (decided).
- **CelesTrak `SW-All.txt` (D2):** no stated term.
- **Basilisk support data (D4):** seven files without a found term.
- **CCSDS example messages (D5):** the site could not be read from the sandbox.
- **MSFC table (D6):** no statement for this file.
- **IERS excerpt (D7):** no term found.

The NAIF kernels and the WMM are verified. The secrets scan (R6) also
found one person's e-mail address in the header of the IERS excerpt
(`tests/data/validation/eopc04_excerpt.txt`). It is part of the file as
the provider published it.

**Done.** The provider terms were read where they were reachable. The
licence gate marks each data set as `verified`, `open` or `restricted`.

**Open.** D2 to D7: the owner writes to each provider, or decides to
replace the file with synthetic data. Until then, this is an **owner's
accepted risk**.

## R4 Standards text

**Facts.** `compliance/requirements/*.csv` quotes ECSS and CCSDS clause
text. ECSS: "No ECSS document may be reproduced in any form without the
explicit consent of ESA." The CCSDS terms were not read (the site was
blocked).

**Open.** D3 and D5. The options are to ask for consent, or to replace
the quoted text with clause numbers and titles. A replacement changes
the compliance tooling, so it waits for the owner's yes. Until then, this
is an **owner's accepted risk**.

## R5 Name and trademarks

**Facts.** Plan §10 R5: no product, company or mark called
"SpaceMissionStudio" or "Space Mission Studio" was found by a web
search. The search found two similar names: `spacestudio` (Exotrail),
and a USPTO record SPACESTUDIO, serial 79368484. These are leads from
search snippets, not from the registers.

**Open.** The owner searches the registers. Plan §10 R5 lists TMview,
DPMAregister, EUIPO, USPTO and WIPO, and the search terms. Whether the
names can be confused is an **owner's accepted risk**.

## R6 Personal data and secrets

**Facts (scan of 2026-11-10).**

- **Working tree:** `detect-secrets` 1.5.0 scanned `SpaceMissionStudio/`,
  `.github/`, `README.md` and `SECURITY.md` with all files. It reported
  158 hits. All are false positives: SHA-256 values, a Git revision, a
  test token (`0123456789abcdef...`) and the cache tag of an untracked
  `.ruff_cache`. No secret was found.
- **History:** the full history was fetched (not shallow). A regex scan
  read every line added in the 558 commits that touch
  `SpaceMissionStudio/`, the app's workflows or the README. It looked for
  GitHub, AWS, Google, Slack, OpenAI and Anthropic tokens, private keys,
  JWTs and assignments to `password` or `token`. Result: no secret. The
  only hits were two invented example strings in `HISTORY.md` and the test
  token above.
- **E-mail addresses in history:**
  - **Commit metadata:** the address of the author `ohexna`, taken to be
    the owner (plan Q3). It stays: removing it would rewrite history,
    which only the owner can decide.
  - **Vendored licence texts:** the authors of zlib, libX11 and Berkeley DB.
  - **Organisations' contact addresses** in `DATA_TERMS.md`.
  - **The IERS excerpt (R3).**
  - **The root README:** addresses from upstream Basilisk's README.
- **Paths:** `/home/user/` appears in GMAT scripts and two tests. This is
  the build sandbox's own path, not a person's.

**Done.** Nothing needed a fix in the tree. History is not rewritten.

**Open.** None required.

## R7 Privacy inside the app

**Facts.**

- **Network:** [`docs/reference/network.md`](../reference/network.md)
  says there is no telemetry, no crash upload and no update check.
  Downloads happen only when the user starts them, and only from the
  listed hosts. `scripts/network_audit.py` checks this in the `linux` job
  of the `SpaceMissionStudio` workflow. That job passed on the last commit
  of PR #243. The audit needs Basilisk, so it was not run again here.
- **Provenance:** the output provenance (`output_provenance.py`) records
  versions, hashes, the scenario name and the file name. It records no
  path, user name or host name.
- **Two places store personal data in files that users may share:**
  - **Edit history:** `history.default_author()` writes the operating
    system's user name as the author into `*.history.jsonl` and into
    import records, until a name is set in Settings.
  - **Import records:** `ImportRecord.source` (`ccsds-import`,
    `idm-import`) stores the imported file's absolute path, which often
    contains the user's home folder name.
- **Local files:** logs, settings and autosaves stay in
  `~/.spacemissionstudio/` and are never sent anywhere.

**Proposal P2, declined (owner, 2026-11-10).** The proposal was: use an
empty author until the user sets one, and store the import source as a
path relative to the scenario, or as the file name only. The owner
declined it: the author name and the absolute import paths stay as they
are, and scenario files and CLI output are unchanged. That a shared
scenario file can carry the user's account name and home folder is an
**owner's accepted risk**.

## R8 Security and supply chain

**Facts and done.**

- **`SECURITY.md`** is at the repository root (Q1). Reports go through
  GitHub's private vulnerability reporting.
- **Signed provenance:** from the next release, the release workflow
  signs a build provenance for every built file with `actions/attest`
  (Sigstore, free for a public repository).
- **Checksums:** every release keeps its SHA-256 lists.
- **Dependencies:** they are pinned and installed hash-checked
  (`packaging/constraints-hashes.txt`), and `pip-audit` runs in CI.
- **Windows code signing:** the setup program is not code-signed.
  Authenticode certificates cost money, so this is proposed only, not
  adopted ("everything must remain completely free", Q7).

**Open.** The owner switches on **private vulnerability reporting**
(repository Settings › Code security). Until then, the link in
`SECURITY.md` does not work.

## R9 Contributions

**Facts and done.**

- **Licence of contributions:** `CONTRIBUTING.md` says contributions are
  accepted under the EUPL-1.2.
- **PR template:** the root template asks for a `Signed-off-by:` line
  under the Developer's Certificate of Origin 1.1 (Q1).
- **Sign-off check:** the workflow `spacemissionstudio-signoff.yml` checks
  the sign-off for pull requests from forks. The maintainer's own
  branches are not checked, because a sign-off is a personal statement
  and the maintainer's commits are written with an AI tool.

**Open.** None.

## R10 Repository presentation

**Facts.** The README calls the compliance records "not a certification".
The data documentation already says that the project is not affiliated
with CNES. No third-party logo is shown.

**Done (owner's approval, 2026-11-10).** The non-affiliation sentence
(W1) and the no-warranty sentence (W2) are in both READMEs and the user
manual's introduction.

## R11 Third-party files in the installers

**Facts and done.**

- **Linux:** the licence gate runs on every build and fails on any file
  without an owner, any licence off the allowlist, or a missing text. The
  Linux `.deb` passes, with warnings only for open data terms.
- **Windows:** before M4, the gate printed 633 problems on Windows. Three
  defects caused them:
  - matching ignored case on Windows, so the Tcl pattern `lib/thread*`
    claimed `Lib/threading.py`;
  - the components did not know the Windows layout of CPython;
  - tzdata had no known licence.

  All three are fixed. A test now runs the gate on the Windows layout.
- **Microsoft C++ runtime:** the Windows build of CPython carries
  `vcruntime140.dll` and `vcruntime140_1.dll`. CPython's Windows
  `LICENSE.txt` has a section on "Microsoft Distributable Code". It says
  that redistributing the Windows build complies with Microsoft's terms,
  provided the distributor does not:
  - alter Microsoft's notices;
  - use Microsoft's trademarks in a program's name or to suggest
    endorsement;
  - ship the files for a non-Microsoft platform;
  - include them in malicious, deceptive or unlawful programs.

  The project does none of these. Microsoft's own terms were not read.
  The component's redistribution status is `open` (a warning).
- **Earlier installers:** releases up to 2.6.0 carried the same Windows
  files and the ITU file.

**Open.**

- **D10, decided (owner, 2026-11-10): yes.** The project relies on
  CPython's statement for the Microsoft runtime; its redistribution
  status is `verified`, with this decision as the basis
  (`packaging/legal/components.json`). That Microsoft's own terms were
  not read is an **owner's accepted risk**.
- **Windows gate mode:** the Windows gate stays in warn mode until a
  full Windows build shows only warnings. Then it fails like the Linux
  gate.

## R12 Non-commercial status

**Facts and done.** No price, sale, donation or sponsorship was found
(plan §9). `tests/test_signoff.py::test_the_project_takes_no_money`
fails if a `FUNDING.yml` appears, or if the package metadata names a
funding or sponsor link.

**Open.** None. Whether the EU Cyber Resilience Act or the Product
Liability Directive treats the project as outside commercial activity
was not read: EUR-Lex was not reachable (plan F7). This is an **owner's
accepted risk**.

## R13 Website

Cancelled: no website, no hosting (Q7).

## Owner's to-do list

1. Switch on private vulnerability reporting (R8).
2. ~~Approve, change or reject the wording drafts (R1, R10).~~ Done
   2026-11-10: W1 and W2 approved, W3 rejected.
3. ~~Decide D10, the Microsoft runtime (R11).~~ Done 2026-11-10: yes.
4. ~~Decide P2, the author name and import paths (R7).~~ Done
   2026-11-10: declined.
5. Optional: write to the data providers (D2 to D7), ask ECSS (D3), search
   the trademark registers (R5), and ask BAFA (R2).
