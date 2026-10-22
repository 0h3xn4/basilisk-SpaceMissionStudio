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
  view's own actions, the shortcut list's order, its window freed by
  reference count), the rail (a later area
  slotting into its place, the rail following the area shown, Ctrl+1 to
  Ctrl+6, collapsing), Home at start and the Scenario area after opening a
  template, the breadcrumbs, the save button, the top bar's commands and
  search, a long name eliding instead of widening the window, and the
  Settings area.
- `tests/gui/test_shell_reachability.py`: every row of the plan's §5.2,
  read from the plan, reachable in the shell (74 rows), and no menu bar,
  no toolbar, every command on the window.
- `tests/gui/test_command_palette.py::test_keywords_find_an_entry_by_another_name`.

## M2b Panels

No test outside `tests/gui/` changed. No golden or output file changed.
Problems moved from a list in the side panel to a table at the bottom.
Inspector and Explain are two docks instead of two tabs. The run progress
and the run chip moved from the top bar into the status bar. Each test
below reaches the same behaviour there.

### Changed: how a test reaches the widget

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_field_errors.py::_activate_error` (4 tests use it) | `problems.list.itemActivated.emit(problems.list.item(row))` | `problems.table.activated.emit(problems.index_of(row))` | The error's row opens its field |
| `test_field_errors.py::test_an_invalid_epoch_is_marked_at_its_field` | `problems_widget.list.item(0).text()` | `problems_widget.row_text(0)` ("Error: " and the message, as the list item read) | The first row is the epoch's error |
| `test_json_view.py::test_problems_open_the_json_page`, `test_mission_sequence_list.py::test_problems_open_the_step` | `problems.list.itemActivated.emit(problems.list.item(row))` | `problems.table.activated.emit(problems.index_of(row))` | The row opens the JSON page; the step |
| `test_workspace.py::test_problems_list_the_validation_error_and_warnings` | The side tab's text; `list.count()`, `list.item(0).text()`, `list.itemActivated` | The dock's title; `proxy.rowCount()`, `row_text(0)`, `table.activated` | "Problems (n)"; one row per problem, the error first; it opens the editor |
| `test_workspace.py::test_a_stale_model_problem_opens_the_model_editor` | `list.item(row).toolTip()`, `list.itemActivated` | `index_of(row).data(ToolTipRole)`, `table.activated` | The tooltip text; the row opens the model editor |
| `test_workspace.py::test_show_view_selects_every_level` | Problems is the side tab shown and the side dock is visible | The Problems dock is visible | `show_view` reaches a panel |
| `test_workspace.py::test_the_areas_and_what_they_hold` | The side tabs start with Inspector; the side dock holds Explain | The Inspector dock holds the inspector; the Explain dock holds Explain | Where each panel is |
| `test_workspace.py::test_the_layout_is_kept_and_reset` | After Reset Layout, Explain is the side tab shown | After Reset Layout, the Explain dock is visible | A hidden panel stays hidden in the next window; Reset Layout brings it back |
| `test_workspace.py::test_the_view_analyses_and_tools_commands` | The View commands start with "Side Panel"; View > Problems makes Problems the side tab | No "Side Panel" (the Inspector toggle replaces it, its keyword "side panel" finds it); the Problems dock is hidden, then View > Problems shows it | Every other View, Analyses and Tools command, in the same order, does what it did |
| `test_main_window.py::test_explain_tab_exists_and_shows_the_default_scenario_on_startup`, `test_explain_tab_title_counts_pre_run_warnings` | The side tab's index and text | The Explain dock's widget and title | "Explain", then "Explain (1 to check)" |
| `test_main_window.py::test_save_with_invalid_scenario_shows_error_and_does_not_write`, `test_run_with_invalid_scenario_shows_error_without_starting_worker`, `test_run_messages.py::test_an_invalid_scenario_opens_problems_at_the_field` | Problems is the side tab shown | The Problems dock is visible. It is shown in a new window, so `test_panels.py::test_a_refused_run_opens_a_hidden_problems_panel` checks that a hidden one opens | The problem is reported once and Problems opens |
| `test_run_messages.py::test_a_finished_run_says_its_name_length_and_events`, `test_a_failed_run_opens_the_log_at_its_errors`; `test_app_shell.py::test_the_chip_follows_a_finished_run`, `test_the_chip_shows_a_live_run_percentage`, `test_the_chip_shows_failed_and_cancelled_runs` | `window.top_bar.chip` | `window.run_chip` (in the status bar) | Every state and text of the chip |
| `test_shell_reachability.py`: the rows "View › Side Panel, Inspector, Explain, Problems", "Title bar (…, run state chip)", "Run progress strip", "Side **Problems**", and `_side` | The commands; the chip in the top bar; the strip above the areas; the side tab shown | The Inspector and Problems commands toggle their docks with `Ctrl+I` and `Ctrl+J`; the chip, the run job and the problem count are in the status bar; `_side` hides a panel and checks `show_view` shows it again | Every §5.2 row is reachable (74 rows) |
| `test_wheel_in_dialogs.py::test_mouse_wheel_changes_nothing[main-window]` | Wheeled over the window as shown (Home), then every tab widget | Also walks the rail's areas, as `test_input_borders.py` does since M2a; tab widgets not shown are skipped | The wheel changes no box, drop-down or tab. Before, Home's only target was the side tabs' bar, so without it the test failed its "nothing to wheel over" guard |

### Wording only

- `test_shell_reachability.py`: the comment on the validation strip says
  M4 removes it (`docs/DECISIONS.md`, M2b).

### Added

- `tests/gui/test_panels.py` (13 tests):
  - the Problems table: its columns, errors first, a heading sorting,
    the icon, Ctrl+C as TSV, the empty state;
  - the counts in the status bar and the top bar, and both opening the
    panel;
  - a refused run opening a hidden Problems panel;
  - Ctrl+J, the arrows and Enter reaching the field;
  - the run job in the status bar, with progress and Cancel, not widening
    the window and fitting a 1280 px window;
  - the inspector's two docks and Ctrl+I;
  - the layout kept per project, and after the window closes;
  - a keyboard-only walk of the shell.

## M3 Home and templates

No test outside `tests/gui/` changed. No golden or output file changed.
The Templates page's list became Home's template cards with a details
column, and the start-up dialog became a card on Home. Each test below
reaches the same behaviour there.

### Changed: how a test reaches the widget

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_load_scenario_widget.py::test_populates_one_item_per_bundled_template`, `test_a_malformed_template_is_skipped_not_crashed_on` | `list_widget.count()` | `len(widget.cards)` | One entry per template file; none for a malformed file |
| `test_load_scenario_widget.py::test_items_are_in_filename_order` | `list_widget.item(i).text()` | `card.name` | File-name order, from 01 |
| `test_load_scenario_widget.py::test_customize_clicked_is_independent_of_the_lists_current_selection`, `test_selecting_an_item_enables_open_and_shows_its_description`, `test_open_template_button_emits_the_matching_path`, `test_description_label_is_never_squeezed_below_its_needed_height` | `list_widget.setCurrentRow(n)` | `widget.select(n)` | The card's Customize acts on its own template; Open enabled and a description shown; Open emits the template's path; the description keeps its full height |
| `test_load_scenario_widget.py::test_double_click_opens_the_template` | `itemDoubleClicked.emit(item(2))`, first without a current row (nothing), then with one (opens) | `qtbot.mouseDClick(cards[2])` | A double-click opens that template, once; the double-clicked card is also selected (a card has no "double-click without a selection") |
| `test_load_scenario_widget.py::test_content_is_wrapped_in_a_resizable_scroll_area` | The page's only `QScrollArea` holds the description | `widget.description_scroll`, one of Home's three column scroll areas, holds it | The description is inside a resizable scroll area |
| `test_load_scenario_widget.py::test_selected_templates_title_and_description_are_visible_without_scrolling_the_tab` | `list_widget.setCurrentRow(4)`, `item(4).text()` | `select(4)`, `cards[4].name` | The selected title is in the details, near the top |
| `test_load_scenario_widget.py::test_the_selected_templates_title_stays_readable` | The selected row's title has role `strong` | The selected card's title has role `heading` (a card's title is always semibold), and the card is marked selected | 4.5:1 against the selection colour; semibold |
| `test_load_scenario_widget.py::test_left_pane_content_fits_a_default_window_without_horizontal_scrolling` | `minimumSizeHint().width() <= 560` (the Templates pane beside the old scenario tree, in a 1400 px window) | A 1280 x 720 main window with the inspector shown, the theme applied: the window keeps 1280 px and none of Home's three columns scrolls sideways | No horizontal scrolling at the default window. Home is the whole area since M2a, so the 560 px pane no longer exists |
| `test_load_scenario_widget.py::test_every_customize_button_is_inside_the_list` | `list_widget.viewport()`, `_rows` | `grid_scroll.viewport()`, `cards` | Every Customize... is inside the visible width |
| `test_wide_screen.py::test_a_template_row_keeps_its_customize_button_close` | The list at most `CONTENT_MAX_WIDTH_PX` wide; the row's Customize... within it | A card under two least card widths wide; its Customize... within the card, beside Open | On a 2560 px screen Customize... stays next to its template's title. The cards fill the width in columns instead of a 960 px column |
| `test_mission_guide.py::test_the_templates_page_offers_a_blank_scenario_first` | `page.layout().itemAt(0)` is Start from scratch | The first item of Home's first column (`start_scroll`) is Start from scratch | Start from scratch is the first choice; its button makes the blank scenario |
| `test_shell_reachability.py`, the row "`StartupFetchDialog`" | The dialog class exists; Reference Data is a command | Also: the reference-data card shows on Home with Fetch now enabled (`_reference_card`) | The row is reachable, where §5.2 puts it now |

### Added

- `tests/gui/test_home.py` (32 tests):
  - a card per template, its three lines read from the file (attitude
    mode and spacecraft count, central body and orbit, the description's
    first sentence), with examples (LEO, an eccentric orbit, GEO, Mars,
    Eros);
  - the first-sentence rule; the filter and its count; the columns
    following the width; the keyboard (one Tab stop, the arrows, Home,
    End, Enter); a card's Open; Customize from the details and from the
    window;
  - recent scenarios: the empty state, opening and saving listing a file
    first, templates not listed, the last 10, a list of one, a missing
    file marked and not opened, Delete and Clear, opening from the list;
  - the reference-data card: shown at start-up instead of a dialog, Not
    now fetching nothing, the dialog's items and defaults, Fetch now in a
    worker with its summary, nothing ticked, and the card taking only
    the height it needs;
  - the cards' text, which they paint themselves, in the new colours
    after a live theme switch.
