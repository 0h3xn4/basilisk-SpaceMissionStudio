# CLAUDE.md: rules for work on SpaceMissionStudio

Read `CONTRIBUTING.md` and `docs/developer/README.md` first. The GUI is
being overhauled milestone by milestone (`docs/ui/UI_OVERHAUL.md`, the
brief; `docs/ui/UI_OVERHAUL_PLAN.md`, the plan). Every session that
touches the GUI follows the design rules below; where they and older
documents disagree, these win.

## Hard rules

- **UI only during the overhaul:** no change to computation, the engine,
  scenario or project file formats, CLI commands and flags, or any
  generated output file. Every existing test passes; golden files stay
  byte-identical. GUI tests may change only how they reach a widget, each
  change logged in `docs/ui/TEST_CHANGES.md`.
- **Do not modify the Basilisk framework** (anything outside
  `SpaceMissionStudio/`): no edits, patches or monkey-patching.
- **PySide6 only:** no web frontend, no Electron/Tauri, no third-party Qt
  theme package.
- **Offline:** every font, icon and script is bundled; nothing is fetched
  at run time, no CDN.
- **Dependencies:** prefer none. Anything new is permissively licensed,
  pinned, in the `gui` extra only, and recorded in `docs/DECISIONS.md` and
  `docs/THIRD_PARTY_ASSETS.md`.
- **Decisions:** where the brief is silent, take the simplest option and
  record it in `docs/DECISIONS.md` with a one-line rationale; ask where a
  choice changes a workflow users rely on.
- **Never claim compliance without evidence;** a target that is not met
  is written down with the measured value.

## Design rules

**Character:** calm, dense, precise. Quiet neutral surfaces, crisp type,
very few lines, colour only where it means something.

1. **Colour means something.** The interface is neutral. The accent is
   for the primary action, selection and focus only. Status colours
   (critical, serious, caution, normal, standby, off) are for status
   only, always with an icon or text, never colour alone.
2. **Surfaces, not lines.** Separate areas by background (`bg.canvas`,
   `bg.surface`, `bg.raised`) and spacing. Borders are 1 px and subtle,
   for inputs, table headers, panels and splitters. No boxes in boxes, no
   group-box frames.
3. **Density with order:** a strict 4 px grid (4, 8, 12, 16, 24, 32);
   controls 32 px (28 px compact); table rows 26 px.
4. **Precision:** every number shows its unit (field suffix or column
   header), right-aligned with tabular figures, consistent significant
   figures per quantity; timestamps ISO 8601 UTC with `Z`; values, IDs
   and table selections copyable.
5. **Keyboard first:** Ctrl+K command palette, shortcuts for frequent
   actions shown in tooltips and menus, visible focus everywhere.
6. **Never freeze:** nothing over about 50 ms on the GUI thread;
   simulations, generation, imports, file I/O and checks in workers with
   progress and cancel; heavy tabs and every `QWebEngineView` created
   lazily; typing-triggered recomputation debounced (about 250 ms).

## How the code applies them

- **One source of truth: `spacemissionstudio/gui/theme/`.** Tokens
  (`tokens.py`), type and spacing (`typography.py`), chart palette
  (`palettes.py`), fonts (`fonts.py`), icons (`icons.py`), the generated
  style sheet (`qss.py`), the Plotly template (`plotly_template.py`),
  `apply_theme` and the `changed` signal (`apply.py`). `docs/DESIGN.md`
  describes it.
- **No colour, font family, CSS size or style sheet in GUI code outside
  `gui/theme/`** (`tests/gui/test_design_rules.py` enforces it). Read
  `theme.TOKENS["text.secondary"]`; give a widget its look with
  `theme.set_role(widget, role=..., tone=..., badge=...)`; use
  `theme.ui_font(size, weight)`, `theme.mono_font()`,
  `theme.numeric_font()`; icons with `theme.icon(name, ink)` (Lucide,
  bundled).
- **Live theme switch:** the whole UI restyles at once. Anything that
  paints a colour itself (plots, diagrams, item colours, rich text)
  redraws on `theme.on_change(...)`; item colours go through
  `theme.items.tint` / `retint`.
- **Contrast:** every text/background pair the GUI draws is in
  `tokens.CONTRAST_PAIRS` and passes WCAG 2.2 AA in both themes
  (`tests/gui/test_dark_theme.py`). A new pair is added there.
- **Type:** Inter for the UI, JetBrains Mono for numbers in tables, IDs,
  code and logs. Sizes 11 caption, 12 small and table, 13 body, 15
  section title, 18 page title, 22 display. Weights 400, 500, 600 only.
- **Shape:** radius 6 px for controls, 8 px for panels, popovers and
  dialogs; 2 px accent focus ring; shadows only on floating elements.
- **Icons:** Lucide only, 16 px in the UI, 20 px in the navigation rail.
- **Motion:** 120-180 ms ease-out for hover, panel open/close and toasts;
  never animate data values or plots; respect "reduce motion".
- **Plots:** the Plotly template from the tokens; axis titles with units;
  the 8-colour categorical palette in fixed order, never cycled; a legend
  for more than one series.
- **Shell (M2 onward):** left navigation rail, top bar with Ctrl+K,
  central tabs and splitters, right inspector, status bar with jobs,
  collapsible Problems panel. Modal dialogs only for destructive
  confirmations and multi-step wizards; success feedback is a toast;
  every list and table has an empty state with its primary action.
- **Tables:** `QTableView` + `QAbstractTableModel`, sortable and
  filterable, sticky header, numeric columns right-aligned with units in
  the header, copy as TSV, column-visibility menu, row hover, no zebra.

## Checks before a commit

- `ruff check spacemissionstudio scripts tests`
- `QT_QPA_PLATFORM=offscreen python -m pytest tests -q -n auto -p no:cacheprovider`
- the compliance generators leave `compliance/docs` unchanged
  (`compliance/tools/build_icd_schema.py`, `build_sdd_components.py`,
  `build_test_specs.py`) and `compliance/tools/check_drds.py` passes;
- `python scripts/sync_help.py` after a change to `USER_MANUAL.md`;
- the screenshot harness (`scripts/capture_ui_screens.py`) at the end of a
  milestone, with the differences noted;
- CHANGELOG "Unreleased" and `docs/DECISIONS.md` updated.
