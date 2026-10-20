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
| Lucide icons | 1.52.0 (`lucide-static`) | ISC; the icons derived from Feather also MIT (both texts in `LICENSE`) | 35 SVGs in `gui/assets/icons/lucide/`, `LICENSE` | npm `lucide-static@1.52.0` (`package/icons/`) |

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
- **Removed in 1.2.0:** IBM Plex Sans and Mono (`.woff`, SIL OFL 1.1) and
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

No new run-time dependency came with the 1.2.0 interface: the fonts and
icons are files, not packages. `plotly.min.js` is not copied into the
package (it already ships with plotly; a copy would add 4.8 MB).
