# Third-party assets and GUI dependencies

The licence report for what the GUI bundles or needs (the brief's
"SBOM/licence report", `docs/ui/UI_OVERHAUL.md`). Everything listed is
used offline: nothing is fetched at run time. Since milestone M1 of the legal work,
the packages are also checked by `packaging/legal/licences.py`, which lists
every file and every licence text (`docs/legal/OBLIGATIONS.md`,
`docs/legal/DATA_TERMS.md`); this table stays the hand-written overview. A change to any row is
recorded here and in `docs/DECISIONS.md`.

## Bundled in the package

| Asset | Version | Licence | Files | Source |
|---|---|---|---|---|
| Inter | 4.1 | SIL Open Font License 1.1 | `gui/assets/fonts/inter/Inter-{Regular,Medium,SemiBold}.ttf`, `OFL.txt` | <https://github.com/rsms/inter/releases/tag/v4.1> (`Inter-4.1.zip`, `extras/ttf/`) |
| JetBrains Mono | 2.304 | SIL Open Font License 1.1 | `gui/assets/fonts/jetbrains-mono/JetBrainsMono-{Regular,Medium}.ttf`, `OFL.txt` | <https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304> (`JetBrainsMono-2.304.zip`, `fonts/ttf/`) |
| Lucide icons | 1.52.0 (`lucide-static`) | ISC; the icons derived from Feather also MIT (both texts in `LICENSE`) | 45 SVGs in `gui/assets/icons/lucide/`, `LICENSE` | npm `lucide-static@1.52.0` (`package/icons/`) |
| three.js (with its `OrbitControls`) | 0.187.0 | MIT (`THREE_LICENSE.txt`, the package's `LICENSE`) | `gui/assets/mission_view/three.bundle.min.js`, `THREE_LICENSE.txt` | npm `three@0.187.0`, bundled by esbuild 0.25.10 (`scripts/build_three_bundle.py`) |
| NASA Blue Marble (SVS 2915) | 2004 release | public domain (NASA SVS; credit in `NASA_IMAGES.txt`) | `gui/assets/mission_view/earth_day_4k.jpg`, `earth_day_2k.jpg` | <https://svs.gsfc.nasa.gov/2915>: `bluemarble-west-4096.png`, `bluemarble-east-4096.png` (`scripts/prepare_mission_view_textures.py`) |
| NASA Deep Star Maps 2020 (SVS 4851) | 2020 release | public domain (NASA SVS; credit in `NASA_IMAGES.txt`) | `gui/assets/mission_view/stars_4k.jpg`, `stars_2k.jpg`, `NASA_IMAGES.txt` | <https://svs.gsfc.nasa.gov/4851>: `starmap_2020_4k.exr` (same script) |

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
  folder-open, git-branch, info, moon, octagon-alert, orbit,
  play, repeat, rocket, route, save, search, sun,
  triangle-alert, variable, x (monitor-play and sliders-horizontal were
  removed with the commands that used them). Of these, check, the chevrons, code, info,
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
- **The 3D View's page (added after 2.6.0, `gui/assets/mission_view/`):**
  three.js is one classic script built from the pinned npm packages
  (`scripts/three_bundle/package-lock.json` holds npm's SHA-512 of every
  tarball; `npm ci --ignore-scripts`; esbuild `--bundle --minify
  --format=iife --global-name=THREE --legal-comments=eof`, so three.js's
  licence comment stays at the end of the bundle). `python
  scripts/build_three_bundle.py --check` rebuilds it and compares: the
  same bytes (checked 2026-11-10). A page opened from a `file://` URL
  cannot load ES modules, hence one script. The NASA images are resized
  copies: Blue Marble's two 4096 x 4096 halves (west: -180 to 0 degrees,
  east: 0 to 180 degrees, checked by eye) joined to 8192 x 4096 and
  resized to 4096 x 2048 (JPEG quality 88) and 2048 x 1024 (quality 85);
  the star map's half-float linear values clipped to [0, 1], encoded with
  the sRGB curve, 4096 x 2048 and (2 x 2 averaged) 2048 x 1024, JPEG
  quality 85, in NASA's orientation (right ascension 0 h in the middle,
  increasing to the left). Pillow 13.0.0 and OpenEXR 3.5.3 made them;
  neither is a dependency of the app. The page's own `mission_view.html`
  and `mission_view.js` are the app's code (EUPL-1.2). 4.4 MB in all.

### Checksums (SHA-256)

Archives as downloaded:

| Archive | SHA-256 |
|---|---|
| `Inter-4.1.zip` | `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e` |
| `JetBrainsMono-2.304.zip` | `6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf` |
| `lucide-static-1.52.0.tgz` | `4d2aa079171e4eba4c704844b8b0c9edb6e4cfb2fb8bd86f7b14353994f04a87` (npm integrity `sha512-0zZYihAze4ZmUCcyNa9OkWYqn/Y5f9AdTh02AZIxMtP5ravcTTfoSIAnUPBH6ZvKxt+ZW28JB0ldzLRyD82fcw==`, checked) |

| `three-0.187.0.tgz` | npm integrity `sha512-Qiu7R+Cmh8CstZsY1uJOSWnVlfo7ZtNLV7mF8Jltk3LB3AtDu9cRZlcnRKkAk8Y4z6KKw35z7Y7Urd7jWY8etA==` (in `scripts/three_bundle/package-lock.json`, checked by `npm ci`) |
| `bluemarble-west-4096.png` (SVS 2915) | `c9fab796a66645bf03537522d9c152bd8af9ef97081de177b6fee2cd25a945d7` |
| `bluemarble-east-4096.png` (SVS 2915) | `374c94c0d5060044c28fec4c72348cd15f5c06e039fc7a876cc241a0bd80798a` |
| `starmap_2020_4k.exr` (SVS 4851) | `69b841cd048c2ef35543eb1c5819b322530e78aa4b0cab97ec1de3ef56a4ddcd` |

The NASA originals were downloaded on 2026-11-10 from
`https://svs.gsfc.nasa.gov/vis/a000000/a002900/a002915/` and
`https://svs.gsfc.nasa.gov/vis/a000000/a004800/a004851/`.

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
| `mission_view/three.bundle.min.js` (769,928 bytes) | `cbe5b681be63dee0b83dda9946b5992c95be4372fddd8904789956d527a2ba4c` |
| `mission_view/THREE_LICENSE.txt` | `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc` |
| `mission_view/earth_day_4k.jpg` (1,066,107 bytes) | `32f859e19f9ad25cd9fbca17350fd73766a6985c95c5c7fef4378324af4527b8` |
| `mission_view/earth_day_2k.jpg` (259,363 bytes) | `7d5d8192d45944e0f196e21c80008de0853fa31b25a148fa8986cf236bb05c14` |
| `mission_view/stars_4k.jpg` (1,969,330 bytes) | `84a3c7f1c3e3bc1c599bf3ba79b64713c752d69f26fecd1bbd6075d295038b44` |
| `mission_view/stars_2k.jpg` (439,343 bytes) | `27ec5f012197a30cb34a8a68fadb71ba8e8cd175925c51eac36bcb5dc74a6da7` |

## Used from installed packages (not copied)

| Package | Version range (`gui` extra) | Version verified | Licence | Used for |
|---|---|---|---|---|
| PySide6 (Qt for Python) | `>=6.6` | 6.11.2 (Qt 6.11.2) | LGPL-3.0 (Qt and PySide6, as installed from PyPI) | Widgets, `QtSvg` (icon rendering), Qt WebEngine (plots, the 3D model view, Results › 3D View) |
| plotly | `>=5.0` | 7.1.0 | MIT | Figures and the 3D model view; `plotly.min.js` loaded from `plotly/package_data/` by local file URL (Results › 3D View no longer uses it) |
| PyYAML | `>=6.0` (a core dependency) | 6.0.3 | MIT | Project configuration files (`config/files.py`, transparency plan Phase 3b); it came with `bsk[all]` before it was declared |

No new run-time dependency came with the new look (1.1.0) or the new
interface (1.3.0): the fonts and icons are files, not packages. Nor with
the 3D model's analyses and the IDM-CIC import (2.1.0 to 2.5.0): the
IDM-CIC reader uses Python's own `zipfile` and `xml.etree`, and no CNES
software is bundled. Nor with the JSON page's code editor (2.5.0): it is
Qt's own text editor (`QPlainTextEdit`), not a bundled web editor. Nor with the 3D View's renderer: three.js is a bundled file built by a script, not a run-time package, and nothing is fetched from npm or NASA at run time. `plotly.min.js` is not copied into the
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
| CPython | 3.14.8 | PSF-2.0 (text: `lib/python3.14/LICENSE.txt`, `Lib\LICENSE.txt` on Windows) | python-build-standalone 20261013, `install_only_stripped`, SHA-256 pinned in `bundle_python.py` |
| Libraries CPython is built with (OpenSSL, SQLite, libffi, XZ, zlib, ...) | as in that build | as documented by python-build-standalone ("Licensing" in its `docs/running.rst`): it builds against libedit, not readline, and leaves out `_gdbm`, so no GPL library is linked | same archive |
| Basilisk (`bsk`, `bsk-opnav`) | 2.12.0 | ISC | PyPI wheel |
| PySide6, PySide6-Essentials, PySide6-Addons, shiboken6 (Qt 6.11.2) | 6.11.2 | LGPL-3.0-only (offered also under GPL-2.0/3.0) | PyPI wheels, unmodified; Qt stays in separate shared libraries in `site-packages/PySide6`, which a user can replace |
| numpy | 2.4.6 | BSD-3-Clause (with 0BSD, MIT, Zlib, CC0-1.0 parts) | PyPI |
| pandas, matplotlib, contourpy, kiwisolver, cycler, pyparsing, fonttools, pillow, python-dateutil, six, bokeh, Jinja2, MarkupSafe, tornado, xyzservices, narwhals, PyYAML | from `constraints.txt` or as resolved | BSD, MIT, PSF (matplotlib), MIT-CMU (pillow), Apache-2.0 (tornado; dateutil partly) | PyPI (dependencies of `bsk[all]`) |
| plotly, sgp4, pyerfa, platformdirs, PyYAML | from `constraints.txt` or as resolved | MIT, MIT, BSD-3-Clause, MIT, MIT | PyPI (SpaceMissionStudio's own dependencies; PyYAML also a dependency of `bsk[all]`) |
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
| Gravity fields, magnetic field (WMM-2025), albedo maps, tabular atmosphere profiles | `GGM03S.txt`, `GGM2BData.txt`, `WMM2025.COF`, `Earth_ALB_2018_CERES_All_5x5.csv`, `Mars_ALB_TES_5x5.csv`, `USStandardAtmosphere1976.csv`, `EarthGRAMNominal.txt`, `NRLMSISE00Nominal.txt` | Basilisk's `supportData` folder (`raw.githubusercontent.com/AVSLab/basilisk/.../supportData/`), the files Basilisk itself downloads |
| Earth orientation | the current `earth_*_combined.bpc` and `earth_latest_high_prec.bpc`, with their comment files | NASA NAIF, `naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/` |

ITU-R P.676-13's data file Part 1 is not in the installers (owner's decision,
`docs/legal/DATA_TERMS.md` D1); a user who chooses that model downloads it
from ITU.
