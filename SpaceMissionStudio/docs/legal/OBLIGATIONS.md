# Third-party licences: obligations and what M1 found

Milestone M1 of [`PHASE1_PLAN.md`](PHASE1_PLAN.md). Not legal advice. The tool
that keeps this correct is `packaging/legal/licences.py`
([`packaging/legal/README.md`](../../packaging/legal/README.md)); the reference
data are in [`DATA_TERMS.md`](DATA_TERMS.md).

## Corrections to the plan

Facts the plan got wrong or missed, found while building M1:

* An SBOM generator already exists (`packaging/bundle_python.py`, from the
  hashed-installs change): CycloneDX, with each package's source file and hash.
  It does not tie licences to files or check that licence texts travel. The new
  tool complements it.
* The wheel does carry `LICENSE` (in `.dist-info/licenses/`). The plan said it
  might not.
* The app icon is drawn by code (`gui/icons.py`, `ensure_icon_file`), not a
  missing file. Milestone M5 can render it for the site.

## What the check found

| Finding | Where | Action taken |
|---|---|---|
| **No licence text for Qt.** PySide6, PySide6_Essentials, PySide6_Addons and shiboken6 (Qt 6.11.2, LGPL-3.0) carry none in the wheels, and the installers redistribute them. | the bundled Python | The bundle now ships `licenses/LGPL-3.0-only.txt` (SPDX text) and `QT_NOTICE.txt` (draft, D8). |
| **No licence texts for the libraries inside CPython.** The Python build links OpenSSL, SQLite, libffi, expat, mpdecimal, XZ, bzip2, zlib, zstd, libedit, ncurses, libuuid, Berkeley DB, Tcl/Tk and Tix, X11 libraries; its `install_only` archive has none of the texts. The `.deb` copyright file only points to python-build-standalone's documentation. | the bundled Python | The 18 texts are vendored in `packaging/legal/texts/` (from the release's full archive, SHA-256 recorded; zstd from the project) and copied to `licenses/`. |
| **Unused extension modules ship with their libraries:** `_tkinter` (Tcl/Tk 9, Tix, X11), `_dbm` (Berkeley DB 5.3, an Oracle licence). The app uses none of them. | the bundled Python | Texts included. Removing the modules would shrink the notices; that changes packaging contents: **D9**. |
| **Fourteen Python packages state no usable licence in their metadata** (licence field empty or only a classifier "BSD License"). | the bundle | Each is resolved in `overrides.json` with the evidence (the licence file read, 2026-11-09). |
| **Reference data without a stated term, or restricted.** | the installers, the wheel | See `DATA_TERMS.md` D1 to D7. The Linux bundle build **stops** on the ITU file (`restricted`) until you decide D1. |
| **The Qt source offer is not made yet.** | releases | Plan below; **D8**. |
| **GPL-only Qt modules** may sit inside PySide6_Addons (Qt Graphs, Qt Quick 3D, and others). Not read from the Addons wheel, which did not finish downloading here. | the bundle | Open. Check on the first full build and decide whether to remove unused modules (**D9**). |

## Obligations by licence family

| Licence | Components | What redistribution needs | How the package meets it |
|---|---|---|---|
| EUPL-1.2 | the app (from the release after 2.6.0) | the licence text and the notices with every copy; "Licensed under the EUPL" after the copyright notice | `LICENSE`, `LICENSE.de` in every package; the header of every source file |
| ISC | the app up to 2.6.0, Basilisk, Lucide | copyright notice and permission notice in all copies | `LICENSE`; Basilisk's text inside the FSW zip and in the notices |
| MIT, BSD-2/3, 0BSD, Zlib | most Python packages, libffi, expat, XZ, zlib, zstd | keep the notice (BSD: also in documentation for binaries) | texts in each `.dist-info` and in `licenses/`; all in `THIRD_PARTY_NOTICES` |
| Apache-2.0 | OpenSSL 3, requests, tornado, packaging (dual) | licence copy; keep NOTICE files | `licenses/LICENSE.openssl-3.txt`; dist-info texts |
| MPL-2.0 | certifi, tqdm | licence copy; source of the MPL files available | the sources are on PyPI (sdist); texts shipped |
| PSF-2.0 and related | CPython, matplotlib (own PSF-based licence) | keep copyright and licence | `lib/python3.14/LICENSE.txt` |
| OFL-1.1 | Inter, JetBrains Mono | licence text with the fonts; font name rules (no sale alone) | `OFL.txt` beside each font; the fonts are unmodified |
| LGPL-3.0 | Qt, PySide6, shiboken6 | licence text and a prominent notice; the libraries replaceable; **the exact corresponding source** available | text and notice added (above). The libraries stay separate shared files. Source: the plan below. |
| public domain and permissive "other" | SQLite, NAIF kernels, WMM | per the provider (acknowledgement, 17 U.S.C. 403 notice) | `DATA_TERMS.md`; the notices carry the credits |

## Plan for the Qt source (needs your approval, D8)

1. Attach the exact archives to every GitHub release that ships an installer:
   `qtbase-everywhere-src-6.11.2.tar.xz` (about 48 MB), `qtwebengine-everywhere-src-6.11.2.tar.xz`
   (about 554 MB), the other Qt submodules the PySide6 wheels contain, the PySide6 6.11.2 sdist, with SHA-256.
   The release workflow would download them from `download.qt.io` and compare the checksums that
   Qt publishes. The sizes are from Qt's 6.11.3 listing; the 6.11.2 listing is to be read when the step is built.
2. Alternative: a written offer in `QT_NOTICE.txt` plus the `download.qt.io` links (already in the draft). Qt's own
   page allows "a written offer with instructions on how to get the source code", but it is the weaker course.
3. Either way the Qt CVE patch files that Qt publishes for 6.11 are part of the "corresponding source" question
   for a lawyer.

## Windows

The Windows list is not read yet: python-build-standalone's Windows build links other libraries, and its tree has
other file names. The first Windows installer build runs the gate in `warn` mode and prints the files no component owns.
Each becomes an entry in `components.json`, after which the Windows gate can fail like the Linux one.

## EUPL compatibility (M2)

My reading, component by component; **not legal advice**, for a lawyer to confirm.
The EUPL applies to SpaceMissionStudio's own work (the Work and Derivative
Works, EUPL Article 1). The other components are separate works that the
packages carry beside it, each under its own licence; none of their code is
copied into the app's files (M2 scan).

| Licence family | Components | In the EUPL-1.2 Appendix? | Reading |
|---|---|---|---|
| LGPL-3.0 | Qt, PySide6, shiboken6 | yes (LGPL v3) | used as separate, replaceable shared libraries; the LGPL obligations above apply to them |
| MPL-2.0 | certifi, tqdm (part) | yes (MPL v2) | separate packages, unchanged |
| ISC, MIT, BSD-2/3, 0BSD, Zlib, bzip2, TCL, MIT-CMU, PSF-2.0 and related, Apache-2.0 | Basilisk, CPython and its libraries, most Python packages, Lucide | no | notice-only licences; they ask for their notices to travel, which `THIRD_PARTY_NOTICES` does; nothing in them restricts the licence of a separate work beside them |
| OFL-1.1 | Inter, JetBrains Mono | no | fonts shipped unchanged with their licence; OFL forbids selling the fonts alone, which the project does not do |
| GPL-only Qt modules | possibly inside PySide6_Addons | yes (GPL v3) | not used by the app; whether they are in the installer is open (D9) |
| Data terms | NAIF, WMM, CelesTrak and others | not licences | `DATA_TERMS.md`; the ITU file is restricted (D1) |

Basilisk's ISC condition (its notices in all copies) is met by the
unchanged `LICENSE` inside the flight-software source zip, Basilisk's own
`.dist-info` in the installers, and `THIRD_PARTY_NOTICES`.

## Proposals waiting for approval

* **P1: the generated C project's notice.** The flight-software export
  writes C files whose header (`fsw_export/templates/_isc_c.txt` and the
  templates) still names the AVS Lab and ISC, and a README that says the
  generated files carry "the same ISC licence". This is generated output, so
  I did not change it. Options: (a) leave it (the user who generates the
  project owns its use); (b) name the app's licensor and EUPL-1.2 for the
  template code; (c) state no licence for generated code and let the user
  choose. A lawyer should advise; (b) or (c) changes the export's output and
  its golden files.

## Decisions waiting for you

| # | Decision |
|---|---|
| D1 to D7 | the data items in `DATA_TERMS.md` |
| D8 | Approve the wording of `QT_NOTICE.txt` and the Qt source plan (attach archives, or a written offer) |
| D9 | Remove unused modules from the installers (`_tkinter` with Tcl/Tk, `_dbm`, GPL-only Qt modules)? Smaller notices and less licence risk; it changes what the installers contain. |
