# Third-party assets and GUI dependencies

The licence report for what the GUI bundles or needs (the brief's
"SBOM/licence report", `docs/ui/UI_OVERHAUL.md`). Everything listed is
used offline: nothing is fetched at run time. A change to any row is
recorded here and in `docs/DECISIONS.md`.

## Bundled in the package

| Asset | Version | Licence | Files | Source |
|---|---|---|---|---|
| Inter | 4.1 | SIL Open Font License 1.1 | `gui/assets/fonts/inter/Inter-{Regular,Medium,SemiBold}.ttf`, `OFL.txt` | <https://github.com/rsms/inter/releases/tag/v4.1> (`Inter-4.1.zip`, `extras/ttf/`) |
| JetBrains Mono | 2.304 | SIL Open Font License 1.1 | `gui/assets/fonts/jetbrains-mono/JetBrainsMono-{Regular,Medium}.ttf`, `OFL.txt` | <https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304> (`JetBrainsMono-2.304.zip`, `fonts/ttf/`) |
| Lucide icons | 1.52.0 (`lucide-static`) | ISC; the icons derived from Feather also MIT (both texts in `LICENSE`) | 45 SVGs in `gui/assets/icons/lucide/`, `LICENSE` | npm `lucide-static@1.52.0` (`package/icons/`) |

- **Unmodified.** The font files are the release's own TTFs (the one
  change to a licence text: a trailing space on line 21 of JetBrains Mono's
  `OFL.txt`, removed for the repository's whitespace check); the icons are
  the package's SVGs, each still carrying its `@license lucide-static
  v1.52.0 - ISC` comment. The GUI tints an icon at run time by replacing
  `currentColor` in memory or in a temporary copy, never in the package.
- **TTF, not WOFF2:** Qt's font database reads TrueType on every platform;
  WOFF2 support depends on how Qt was built.
- **The icons bundled:** activity, box, check, chevron-down, chevron-right,
  chevron-up, circle-alert, circle-check, circle-dot, circle-minus,
  circle-stop, circle-x, code, dices, file-check, file-plus, file-text,
  folder-open, git-branch, info, monitor-play, moon, octagon-alert, orbit,
  play, repeat, rocket, route, save, search, sliders-horizontal, sun,
  triangle-alert, variable, x. Of these, check, the chevrons, code, info,
  moon, search, x and the three alert icons (Feather's `alert-*`) are
  derived from Feather (MIT).
- **Added in M2a** (the navigation rail and the top bar), from the same
  archive, checked again against the SHA-256 and npm integrity below:
  chart-gantt, chart-line, circle-help, file-output, house,
  panel-left-close, panel-left-open, redo-2, settings, undo-2. The ISC
  and MIT texts in `LICENSE` cover them; which of these ten derive from
  Feather was not checked.
- **Removed in 1.1.0:** IBM Plex Sans and Mono (`.woff`, SIL OFL 1.1) and
  the app's 23 hand-drawn SVG glyphs.

### Checksums (SHA-256)

Archives as downloaded:

| Archive | SHA-256 |
|---|---|
| `Inter-4.1.zip` | `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e` |
| `JetBrainsMono-2.304.zip` | `6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf` |
| `lucide-static-1.52.0.tgz` | `4d2aa079171e4eba4c704844b8b0c9edb6e4cfb2fb8bd86f7b14353994f04a87` (npm integrity `sha512-0zZYihAze4ZmUCcyNa9OkWYqn/Y5f9AdTh02AZIxMtP5ravcTTfoSIAnUPBH6ZvKxt+ZW28JB0ldzLRyD82fcw==`, checked) |

Files in the package:

| File | SHA-256 |
|---|---|
| `fonts/inter/Inter-Regular.ttf` | `40d692fce188e4471e2b3cba937be967878f631ad3ebbbdcd587687c7ebe0c82` |
| `fonts/inter/Inter-Medium.ttf` | `97ad806f526e41546d46365bb3a393145f75b7b1568913db74549ad8b8dba872` |
| `fonts/inter/Inter-SemiBold.ttf` | `78a843fade9d4612a5567302fb595b56976eb5fcebf4fea5a5912d638bafcde3` |
| `fonts/inter/OFL.txt` | `262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a` |
| `fonts/jetbrains-mono/JetBrainsMono-Regular.ttf` | `a0bf60ef0f83c5ed4d7a75d45838548b1f6873372dfac88f71804491898d138f` |
| `fonts/jetbrains-mono/JetBrainsMono-Medium.ttf` | `31c92d01a8a08528b718a43addf0ad3df0af2ca4b7b3290a452f70f358e14d3d` |
| `fonts/jetbrains-mono/OFL.txt` | `60d55f23c6ce05a81099a762cb67ca2c9b6ea251c7912720998b4c89ebfd4faa` (the release's text with one trailing space removed, for the repository's whitespace check) |

## Used from installed packages (not copied)

| Package | Version range (`gui` extra) | Version verified | Licence | Used for |
|---|---|---|---|---|
| PySide6 (Qt for Python) | `>=6.6` | 6.11.2 (Qt 6.11.2) | LGPL-3.0 (Qt and PySide6, as installed from PyPI) | Widgets, `QtSvg` (icon rendering), Qt WebEngine (plots) |
| plotly | `>=5.0` | 7.1.0 | MIT | Figures; `plotly.min.js` loaded from `plotly/package_data/` by local file URL |

No new run-time dependency came with the new look (1.1.0) or the new
interface (1.3.0): the fonts and icons are files, not packages. `plotly.min.js` is not copied into the
package (it already ships with plotly; a copy would add 4.8 MB).

## In the installers (the bundled Python)

The `.deb` and the Windows setup program carry a whole Python
environment (`packaging/bundle_python.py`), so they redistribute what is
installed in it. The exact versions of each build are in its
`SPACEMISSIONSTUDIO_RUNTIME.json` (in the bundled Python's folder:
`/opt/spacemissionstudio/python` on Linux, `{app}\python` on Windows),
which also lists every data file with its SHA-256.

| Component | Version | Licence | Source |
|---|---|---|---|
| CPython | 3.11.17 | PSF-2.0 (text: `lib/python3.11/LICENSE.txt`, `Lib\LICENSE.txt` on Windows) | python-build-standalone 20261013, `install_only_stripped`, SHA-256 pinned in `bundle_python.py` |
| Libraries CPython is built with (OpenSSL, SQLite, libffi, XZ, zlib, ...) | as in that build | as documented by python-build-standalone ("Licensing" in its `docs/running.rst`): it builds against libedit, not readline, and leaves out `_gdbm`, so no GPL library is linked | same archive |
| Basilisk (`bsk`, `bsk-opnav`) | 2.12.0 | ISC | PyPI wheel |
| PySide6, PySide6-Essentials, PySide6-Addons, shiboken6 (Qt 6.11.2) | 6.11.2 | LGPL-3.0-only (offered also under GPL-2.0/3.0) | PyPI wheels, unmodified; Qt stays in separate shared libraries in `site-packages/PySide6`, which a user can replace |
| numpy | 2.4.6 | BSD-3-Clause (with 0BSD, MIT, Zlib, CC0-1.0 parts) | PyPI |
| pandas, matplotlib, contourpy, kiwisolver, cycler, pyparsing, fonttools, pillow, python-dateutil, six, bokeh, Jinja2, MarkupSafe, tornado, xyzservices, narwhals, PyYAML | from `constraints.txt` or as resolved | BSD, MIT, PSF (matplotlib), MIT-CMU (pillow), Apache-2.0 (tornado; dateutil partly) | PyPI (dependencies of `bsk[all]`) |
| plotly, sgp4, pyerfa, platformdirs | from `constraints.txt` or as resolved | MIT, MIT, BSD-3-Clause, MIT | PyPI (SpaceMissionStudio's own dependencies) |
| pooch, requests, urllib3, idna, charset-normalizer, certifi, tqdm, protobuf, packaging, colorama | from `constraints.txt` or as resolved | BSD-3-Clause, Apache-2.0, MIT, BSD-3-Clause, MIT, MPL-2.0, MPL-2.0 and MIT, BSD-3-Clause, Apache-2.0 or BSD-2-Clause, BSD | PyPI |
| pip, setuptools | as in the build | MIT | PyPI |

The licences above are each package's own metadata in the bundle
(`License-Expression`, else its licence classifiers), read on
2026-10-20 from a Linux build. Each package's licence text is in its
`*.dist-info` folder.

**Data files in the installers** (fetched while building, with
Basilisk's own registry checksums or, for the Earth orientation files,
the tool's own check), the same files the install scripts and the
Reference data dialog download:

| Data | Files | Source |
|---|---|---|
| SPICE kernels | `naif0012.tls`, `de430.bsp`, `de-403-masses.tpc`, `pck00010.tpc` | NASA NAIF, `naif.jpl.nasa.gov/pub/naif/generic_kernels/` (the URLs Basilisk's registry gives) |
| Gravity fields, magnetic field (WMM-2025), albedo maps | `GGM03S.txt`, `GGM2BData.txt`, `WMM2025.COF`, `Earth_ALB_2018_CERES_All_5x5.csv`, `Mars_ALB_TES_5x5.csv` | Basilisk's `supportData` folder (`raw.githubusercontent.com/AVSLab/basilisk/.../supportData/`), the files Basilisk itself downloads |
| Earth orientation | the current `earth_*_combined.bpc` and `earth_latest_high_prec.bpc`, with their comment files | NASA NAIF, `naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/` |
