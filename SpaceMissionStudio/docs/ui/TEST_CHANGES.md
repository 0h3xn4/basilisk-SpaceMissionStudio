# Test changes during the UI overhaul

The user approved (plan §9, Q1): GUI tests may change how they reach a
widget but keep every behavioural assertion; the Carbon tests are replaced
by token, contrast and font tests; non-GUI and output tests stay
unchanged. Every change to an existing test is listed here, per milestone.

## M1 Foundation

No test outside `tests/gui/` changed. No golden or output file changed.

### Replaced: the Carbon tests

| File | Before (Carbon) | Now | Assertions kept |
|---|---|---|---|
| `tests/gui/test_theme.py` | Carbon g10 hex values, the four IBM Plex `.woff` files at 10.5 pt, the hand-drawn SVG glyphs' colours | The token table against the brief (with each adjustment recorded in `docs/DECISIONS.md`), the same token names in both themes, Inter and JetBrains Mono registered from the package and Inter 13 px as the application font, no Plex or Carbon left, tabular figures, every Lucide icon present with its licence, icons following the theme, the palette and sheet set by `apply_theme`, every file the sheet references present, no Qt style sheet warning on the main window and a scenario in both themes, the Plotly template from the tokens, the categorical palette distinct and readable, `set_role` restyling a shown widget | Applying sets the palette and a sheet; Mid is readable text (the user-reported regression); applying twice is harmless; every referenced asset exists; every toolbar action has an icon; the bundled font loads and is the application font; plots and the event timeline share the series colours |
| `tests/gui/test_dark_theme.py` | 34 Carbon pairs at 4.5:1, 3:1 or 1.5:1; glyph recolouring; no light-only colour in any widget's own sheet; View > Theme "applies at the next start" | 77 token pairs per theme at WCAG 2.2 AA (`tokens.CONTRAST_PAIRS`), the contrast formula, the role palette's keys and in-place selection, the setting and System, a live switch that restyles the open main window (one sheet, no per-widget sheets, canvas, badge and plot pages in the dark tokens), View > Theme applying at once, item colours following a switch | Both themes have the same keys; every pair the app draws is readable; selecting fills the one dict; the setting is kept and System follows the platform; a dark window holds no light-only colour; badges and plot pages take the dark tokens |

**One behaviour changed on purpose:** `test_view_theme_remembers_the_choice_for_the_next_start`
asserted the message "It applies when SpaceMissionStudio next starts."
The brief requires the theme to switch live, so the test
(`test_view_theme_applies_the_choice_at_once`) now asserts that the theme
is applied at once and that the message says it is shown now.

### Changed: how a test reaches the widget

| Test | Before | Now | Why |
|---|---|---|---|
| `tests/gui/test_design_rules.py::test_the_token_table_matches_the_theme` | Read `LIGHT`/`DARK` role keys and DESIGN.md's Carbon table | Reads every token of `theme.tokens` and DESIGN.md's token table | The table lists tokens now; still "the document's table equals the code's" |
| `tests/gui/test_design_rules.py::test_no_hard_coded_colour_outside_the_theme` | Colours in strings outside `theme.py` (top-level modules only) | `test_no_hard_coded_style_outside_the_theme`: colours, CSS sizes, weights and font families in strings, Qt colour names, and font-size, font-family and style-sheet calls in code, in every module under `gui/` outside `gui/theme/` | The brief's "no hex colour, font family or pixel size outside the theme package"; stricter than before |
| `tests/gui/test_feedback.py::test_toast_kind_selects_a_different_color` | Compared two toasts' own style sheets | Compares their `tone` property (the application sheet styles `QLabel[role="toast"][tone=...]`) | No widget has a sheet of its own any more |
| `tests/gui/test_load_scenario_widget.py::test_the_selected_templates_title_stays_readable` | The title's own sheet ended in `font-weight: 600;` | Applies the theme, then checks the title's `role` is `strong` and its font is semibold; the 4.5:1 contrast check is unchanged | Same reason |
| `tests/gui/test_template_wizard.py::test_wizard_fits_without_sideways_scrolling_with_large_fonts` | Scaled the application font's point size by 1.5 | Scales its pixel size when the font is set in pixels (the theme's 13 px), its point size otherwise | Qt reports -1 for the point size of a pixel-sized font, so the old scaling set no larger font at all |

### Wording only

- `tests/gui/test_roe_formation_editor.py`, `tests/gui/test_stale_results_and_window_size.py`:
  docstrings name the bundled font instead of IBM Plex.

### Added

- `tests/gui/conftest.py`: the `restored_theme` fixture (restores the
  application's font, palette, sheet and the light tokens after a test
  that applies a theme).

## Between M1 and M2 (release 1.1.1)

### Changed: test isolation only

| Test | Before | Now | Why |
|---|---|---|---|
| `tests/test_autosave.py` (autouse fixture `_isolated_recovery_file`) | Pointed the recovery file at the test's `tmp_path` | Also stops the autosave timer of every main window still open in the process, before pointing the file there | pytest-qt processes Qt events after each test's set-up, so the overdue 30 s tick of a window an earlier GUI test left open wrote its scenario into this test's recovery file (`test_read_with_no_recovery_file_returns_none` failed on Windows CI, PR #89). Reproduced with a window holding template 22, as in the CI failure; no assertion changed |
