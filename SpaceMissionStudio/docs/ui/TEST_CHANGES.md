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

## Between M1 and M2: macOS removed (2026-10-21)

### Changed: a removed feature (the user's decision, `docs/DECISIONS.md`)

| Test | Before | Now | Why |
|---|---|---|---|
| `tests/gui/test_vizard_launcher.py::test_launch_resolves_macos_app_bundle_to_its_inner_binary` and `::test_launch_raises_a_clear_error_for_an_empty_macos_bundle` | A `.app` bundle was started through its `Contents/MacOS` binary; an empty one was refused | `test_launch_treats_an_app_bundle_path_like_any_other` and `test_launch_no_longer_inspects_an_empty_app_bundle`: either path is started as given, even with the platform reported as macOS | macOS support was removed, and with it the bundle handling: each test now checks the new behaviour for the same input |
| `tests/gui/test_vizard_launcher.py::test_download_url_for_platform_covers_all_three` | Checked the macOS, Windows and Linux downloads | `test_download_url_for_platform_covers_windows_and_linux`: Windows and Linux, and that no download is for macOS | The macOS download was removed |
| `tests/gui/test_vizard_launcher.py::test_launch_starts_the_given_executable_directly_on_non_macos` | Its name | `test_launch_starts_the_given_executable_directly_on_linux`; the body is unchanged | Name only |

### Added: a mission from scratch (2026-10-21)

- `tests/gui/test_mission_guide.py`: the Templates page's Start from
  scratch, the Orbit-only blank scenario, the guide's states, buttons and
  folding, and the Spacecraft page's empty state. No existing test
  changed.

## M2a Shell

No test outside `tests/gui/` changed. No golden or output file changed.
The menu bar, the two toolbars and the main tabs are gone; each test below
reaches the same behaviour through the action registry, the navigation
rail's areas, the top bar or the Settings area.

### Changed: how a test reaches the widget

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_main_window.py::test_toolbar_actions_are_all_visible` | Each command on one of the two toolbars, its button visible | Save, Run and the run mode visible in the top bar; Run, Cancel, Live plot, the Vizard commands and Check Reference Data visible in the Run area's header; New and Open as Home's own buttons; the run modes in the mode buttons' menu | Every former toolbar command is a visible button; the modes, Monte Carlo among them, are beside Run |
| `test_workspace.py::test_the_main_tabs_and_what_they_hold` | `test_the_areas_and_what_they_hold`: five main tab names, the tree with Templates and Analyses, Results' three tabs | The rail's areas; Home holds the Templates page; the tree without Templates and Analyses; Run holds End of Life, Budget and Log; Results also Compare; Timeline and Reports | Each screen is where the shell puts it; the tree's own nodes, per spacecraft and station; the side panel; a template opens the editor |
| `test_workspace.py::test_show_view_selects_every_level` | `main_tabs.currentWidget()` | `shell.current_area()` | `show_view()` reaches a page in a scroll area, a Results view and a side panel page |
| `test_workspace.py::test_the_view_analyses_and_tools_menus` | `test_the_view_analyses_and_tools_commands`: the View menu's texts; triggered menu entries | The View category's commands (plus Navigation: Icons Only and the three themes, which were a submenu); the same commands triggered from the registry | Budget, Flight Software and Reference Data open their pages; Problems opens its panel page |
| `test_workspace.py::test_the_3d_model_entry_is_on_the_main_toolbar` | `test_the_3d_model_entry_is_in_the_scenario_header`: after Live plot on the toolbar, and in the Tools menu | A visible button in the Scenario area's header, and a Tools command | The model editor's entry is visible outside the spacecraft editor |
| `test_command_palette.py::test_the_main_window_lists_its_menus_and_tabs_on_ctrl_k` | `test_the_main_window_lists_its_commands_and_areas_on_ctrl_k`: "Go to tab > Events" | "Go to > Timeline", found by typing "events" | Ctrl+K; "Run > Run" listed; the palette not listing itself; going there shows the events; templates listed |
| `test_scenario_tree.py::test_the_palette_goes_to_every_node` | "Go to tab > Scenario > ..." and "Analyses > Budget" in the tree | "Go to > Scenario > Spacecraft > my-sat" and "Go to > Run > Budget" | Every node, and the analyses, are palette entries |
| `test_tree_sections.py::test_the_palette_goes_to_a_tab` | `main_tabs.currentWidget() is editor` | The Scenario area is shown and the current view is the editor | The entry opens the spacecraft's Budget (AD10) tab |
| `test_mission_guide.py::test_the_guide_buttons_open_the_analyses_and_the_templates` | The tree's End of Life and Templates nodes | The current view is End of Life (Run) and Templates (Home) | Analyses and Worked examples open those pages |
| `test_keyboard_cursor.py::test_the_cursor_commands_are_in_the_view_menu_and_the_shortcut_list` | `test_the_cursor_commands_are_in_the_registry_and_the_shortcut_list`: View > Time Cursor's submenu; the shortcuts dialog | The Time Cursor category; Settings > Keyboard's table | Eight moves with their keys; Next Event Alt+PgDown and Clear Time Cursor Alt+Backspace listed |
| `test_help.py::test_help_menu_offers_the_manual_on_f1_and_the_shortcuts` | `test_help_offers_the_manual_on_f1_and_the_shortcuts`: the shortcuts dialog built from the menus | Settings > Keyboard's table; also checks the rail's Help button is the manual command | F1 opens the manual; Ctrl+R and F1 are listed |
| `test_design_rules.py::test_the_shortcut_table_matches_the_menus` | `test_the_shortcut_table_matches_the_registry`: every menu command with a shortcut | Every registry command with a shortcut ("Category > Command") | DESIGN.md's table equals the code's, standard keys per platform |
| `test_theme.py::test_every_toolbar_action_has_an_icon` | `test_every_command_button_has_an_icon`: every toolbar action | Every command button of the top bar and the area headers, the run-mode drop-downs aside (it passed vacuously once the toolbars were gone) | Every command button has an icon |
| `test_theme.py::test_the_style_sheet_parses_without_qt_warnings` | Walked the main tabs | Walks the rail's areas | No style sheet warning on every screen in both themes |
| `test_input_borders.py` (`_check`) | Walked every tab widget | For the main window, also walks the rail's areas, then the tab widgets of the area shown (the main tabs were one of them) | Every input of the main window, and of every dialog, has a visible border |

### Removed with the code it tested

- `gui.help_dialog.ShortcutsDialog` and `shortcut_rows`: the shortcut list
  is Settings > Keyboard, generated from the registry; the two tests that
  built the dialog now read that table (rows above).

### Added

- `tests/gui/test_shell.py`: the registry (tooltips, ids and areas, a
  view's own actions, the shortcut list's order), the rail (a later area
  slotting into its place, the rail following the area shown, Ctrl+1 to
  Ctrl+6, collapsing), Home at start and the Scenario area after opening a
  template, the breadcrumbs, the save button, the top bar's commands and
  search, a long name eliding instead of widening the window, and the
  Settings area.
- `tests/gui/test_shell_reachability.py`: every row of the plan's §5.2,
  read from the plan, reachable in the shell (74 rows), and no menu bar,
  no toolbar, every command on the window.
- `tests/gui/test_command_palette.py::test_keywords_find_an_entry_by_another_name`.
