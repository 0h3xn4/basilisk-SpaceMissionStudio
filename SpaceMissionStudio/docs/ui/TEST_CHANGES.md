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

## M4a Forms

No test outside `tests/gui/` changed. No golden or output file changed.
A form's unit moved from its label ("Duration [days]") into its number
field's suffix ("0.1000 days"), and an optional group shows only its title
while off. Each test below reaches the same value, label or button there.

### Changed: how a test reaches the widget

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_scenario_editor.py::_environment_labels` (used by `test_environment_form_has_labeled_rows`) | Each row's label text | Each row's label with its unit, as messages name it (the label's `sms_full_label` when the form moved the unit into the field, else its text) | Every Environment field has its own label: "Central body", "Integrator", "Dynamics task rate [s]", "Duration [days]", "Atmosphere model" |
| `test_wide_screen.py::test_list_buttons_keep_their_own_width` | Measured the dispersion list's Add on the Monte Carlo page as shown | Turns Monte Carlo on first, then measures it once shown | Add, Edit and Remove under each list are about a button's width, not a third of a wide page. With Monte Carlo off its page shows only its switch, so the list's buttons were hidden and had never been laid out (640 px, Qt's default) |
| `test_ground_station_editor.py::test_dialog_rejects_out_of_range_latitude` | `float(dialog.lat_deg.text())` | `float(dialog.lat_deg.cleanText())` (the text without the "°" suffix) | A latitude of 999 deg is kept by the box, shown as 90 and refused |

### Added

- `tests/gui/test_forms.py` (38 tests):
  - every template written back byte for byte after every page is shown,
    and every spacecraft through the spacecraft form unchanged;
  - no form label left with a unit its field can show, number fields
    right-aligned, examples of the units shown, messages still naming
    "Dry mass [kg]", the unit spellings;
  - an optional group collapsing and keeping its values, Monte Carlo off
    showing only its switch;
  - no Scenario page of any template scrolling sideways at 1280 x 720
    with the inspector shown, and none with a framed panel or a scroll
    area inside it;
  - the unsaved-changes indicator after a number edit, until saved.

## M4b Editing flow

No test outside `tests/gui/` changed. No golden or output file changed.
Explain moved from the inspector's dock to the Scenario tree's first node,
Overview, and its explanation now comes 250 ms after an edit, from a
worker. The tree's JSON node became the Form · JSON toggle. Devices and
dispersions are edited in a form under their list instead of a dialog.

### Changed: how a test reaches the widget

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_main_window.py::test_explain_tab_exists_and_shows_the_default_scenario_on_startup` | `window.explain_dock.widget()` and its title | The tree node holding the explainer (`window.overview_item`) and its title | Explain exists, is titled "Explain"/"Overview" with nothing to check, and shows its placeholder at start-up |
| `test_main_window.py::test_explain_tab_refreshes_on_edit`, `test_explain_tab_refreshes_on_new` | Read the explainer right after the edit | Wait for the explanation the edit asked for (`pending`), then read it | A headline and a stat tile after a valid spacecraft; the placeholder after New |
| `test_main_window.py::test_explain_tab_title_counts_pre_run_warnings` | The dock's title | The Overview node's text, after the explanation arrives | "1 to check" for template 19 moved to 2030 |
| `test_workspace.py::test_the_areas_and_what_they_hold` | `explain_dock.isAncestorOf(explainer)` | `page_tree.item_of(explainer) is overview_item` | Explain is in the window, in its own place |
| `test_workspace.py::test_the_layout_is_kept_and_reset` | `explain_dock.isVisible()` after Reset Layout | The explainer still in the tree after Reset Layout (no dock to hide) | Reset Layout brings the inspector back |
| `test_dark_theme.py::test_a_live_switch_restyles_every_open_view` | Read the explainer's badges after opening template 22, in its dock | Wait for its explanation; show Scenario › Overview before reading them | The badges are rebuilt from the dark tokens |
| `test_workspace.py::test_the_explain_badge_opens_the_model_editor` | Read the badges after opening template 28 | Wait for its explanation, then read them | The "3D model" badge opens the spacecraft's model editor |
| `test_panels.py::test_the_inspector_and_explain_are_panels_on_the_right_without_tabs` | The Explain dock on the right, without tabs | The explainer as the Overview node, without tabs | The inspector on the right, Problems at the bottom, no tabs, Ctrl+I and Ctrl+J |
| `test_panels.py::test_a_project_layout_outlives_the_window` | Hid and showed the Explain dock | Hides and shows the Problems dock | A project's layout is kept for the next window that opens it |
| `test_shell_reachability.py` rows "Side **Explain**" and "Scenario › JSON" | The Explain dock; the tree's JSON node | Scenario › Overview through View › Explain; the Form · JSON toggle in the Scenario area's header | Each row of the plan's table is reachable |
| `test_json_view.py::test_an_edit_in_the_json_applies_everywhere`, `test_problems_open_the_json_page` | `page_tree.current_page() is json_page` | `editor.json_mode` | The edit applies everywhere; Problems opens the JSON |
| `test_json_view.py::test_text_that_is_not_json_is_marked_and_blocks_the_run` | The JSON node's problem count | The toggle's JSON button, "JSON (1)" | The broken line is marked, Problems names it, the run is blocked, the fix clears it |
| `test_sensor_actuator_editor.py::test_add_via_dialog`, `test_edit_and_remove` | Filled the dialog `exec()` opened | Fill the form under the list, then apply it (`inline.flush()`) | The wheel with its spin axis is listed; Edit renames; Remove deletes |
| `test_monte_carlo_editor.py::test_dispersion_list_add_edit_remove` | Filled the dialog `exec()` opened | Fill the form under the list, then apply it | Add lists one, as one change; the edit keeps one; Remove deletes it |

### Changed: what M4b changes on purpose

| Test | Before | Now | Why |
|---|---|---|---|
| `test_workspace.py::test_the_areas_and_what_they_hold` | The tree's paths ended with "JSON" | They start with "Overview" and have no "JSON"; the toggle is in the area's header | The plan's §5 table: Explain becomes Scenario › Overview; JSON a toggle |
| `test_json_view.py::test_text_that_is_not_json_is_marked_and_blocks_the_run` | Leaving the JSON page kept the broken text | Leaving JSON mode is refused while the text does not apply; the text and its problem are kept | "A Form/JSON toggle that validates before applying" (M4's criterion) |
| `test_sensor_actuator_editor.py::test_add_via_dialog` | One change (the dialog's OK) | Two: the Add, then the form's edit | Add no longer waits for a dialog |
| `test_sensor_actuator_editor.py::test_rejects_duplicate_name_on_add` | A device added under a taken name was dropped, with a warning toast | Add gives a free name; renaming it to a taken one is not applied, and the form's banner says so; no warning toast (the Add's own aside), no box | The dialog it was dropped from is gone |
| `test_sensor_actuator_editor.py::test_add_via_dialog_shows_a_toast_and_selects_the_row` | The toast named the dialog's name | It names the name Add gave ("star_tracker-1") | The same |

### Wording only

- `test_mission_guide.py::test_the_spacecraft_page_has_an_empty_state_and_selection_bound_buttons`:
  the empty state says "Add builds one" (was "Add..."): Add opens no
  dialog now. `test_scenario_tree.py`: "Edit" in two docstrings.

### Added

- `tests/gui/test_editing_flow.py` (16 tests):
  - Overview first in the tree, View › Explain opening it, a file still
    opening on its Scenario page;
  - the explanation computed after the 250 ms wait in a worker thread,
    once for a burst of keystrokes, an overtaken one dropped, the
    placeholder at once for a scenario that does not validate, nothing
    after the window closes and no autosave either;
  - the toggle in the header, back to Form applying a waiting edit,
    refused for text that does not apply, Discard, a form problem
    leaving JSON mode;
  - a device's new kind followed, Remove and a reload dropping an edit
    not applied, a dispersion needing a spacecraft, a device edited
    inline reaching the scenario and undone, Add opening a new
    spacecraft's and station's page, with no dialog anywhere.
- `tests/gui/test_forms.py::test_the_inline_device_and_dispersion_forms_fit`.

## M5a The end of a run and its record

### Changed: how a test reaches the widget

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_compare_tab.py::test_runs_of_an_earlier_session_are_listed_and_read_back_when_ticked` | Read Compare right after the window was built | Shows Compare, then waits for its list (the runs are read in a worker, and Compare is refreshed when shown) | The two saved runs are listed, newest first, and read back only when ticked |
| `test_workspace.py::test_the_compare_tab_lists_runs_and_their_input_differences` | Read Compare, hidden, right after two runs | Shows Compare, then waits for its list | Both runs ticked, their input differences, Results' choice followed |

### Changed: what M5a changes on purpose

| Test | Before | Now | Why |
|---|---|---|---|
| `test_workspace.py::test_the_areas_and_what_they_hold` | The Run area's tabs: End of Life, Budget, Log | End of Life, Budget, History, Log | M5's criterion: a History of the runs |

### Added

- `tests/gui/test_run_record.py` (10 tests): a run saved in a worker and
  listed at once ("Saving..." then "Saved"), closing waiting for a save,
  Compare refreshed when shown and the results drawn once, History's
  rows (a run, a failed run and a batch, earlier runs read in a worker),
  the provenance popover and Copy, and the Log's records of a run and its
  Copy.

## M5b The Run area's controls

### Changed: how a test reaches the widget

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_main_window.py::test_toolbar_actions_are_all_visible` | Live plot and Vizard Configuration as buttons of the Run area's header; the header's "Single run ▾" button sharing the top bar's menu | Live plot and the Vizard options on Run › Run; the header's segmented control holding a segment per mode of the menu | Every run command is visible where it lives; the run modes are in the top bar's menu |
| `test_main_window.py::test_configure_vizard_sets_request` | Patched `VizardDialog.exec` to tick Live stream and accept | Vizard Configuration shows Run › Run; the test ticks Live stream in its form (applied as edited, no OK) | The request is set, with live stream on |
| `test_run_feedback.py::test_sil_mode_without_a_spacecraft_that_can_says_so` | Patched `ask_sil_options` (the program dialog) and checked it was not called | Patches `_launch_run` and checks no run starts | No run, and the Flight Software page is shown |
| `test_run_feedback.py::test_sil_mode_asks_for_the_program_and_runs` | Patched `ask_sil_options` to return options | Run shows Run › Run, which asks for the program; the test chooses an executable and ticks the consent there, then Run again (POSIX only: the executable bit, as `test_sil_widgets.py`) | The run starts with that spacecraft and the program chosen |
| `test_shell_reachability.py` rows "Run › Run mode", "Run › Live plot", "Run › Vizard Configuration…" | The header's mode button; the header's Live plot and Vizard buttons | The header's segmented control (its SIL segment); Run › Run's Live plot box and Vizard section | Each row's commands in the palette and its control shown in the Run area |
| `test_shell_reachability.py` row "Monte Carlo archive-folder picker" | The header's mode button | Run › Run's archive folder field and Browse..., in Monte Carlo mode | The Monte Carlo mode command, and the folder reached in the Run area |
| `test_theme.py::test_every_command_button_has_an_icon` | Exempted the top bar's and the header's mode buttons | Exempts the top bar's (the header's is gone; its segments are checkable buttons, not command buttons) | Every command button has an icon |

### Changed: what M5b changes on purpose

| Test | Before | Now | Why |
|---|---|---|---|
| `test_workspace.py::test_the_areas_and_what_they_hold` | The Run area's tabs: End of Life, Budget, History, Log | Run, End of Life, Budget, History, Log | M5's criterion: the run options inline, on a page of the Run area |

### Added

- `tests/gui/test_run_page.py` (6 tests): the segmented control and the
  run mode following each other (and the page its mode), Live plot as one
  setting on the page and in the palette, the Vizard options applied as
  edited, the Monte Carlo folder used without the picker and remembered
  per scenario, an empty folder falling back to the picker, and a SIL run
  without a confirmed program not starting and saying where to choose it.


## M6a The Overview and the plot view

### Changed: how a test reaches the widget

The plot page is loaded once and then takes each change without a reload
(M6a), so a test that waited for the page to load after a change
(`web_view.loadFinished`) now waits for the page to say the plots are
drawn (`plot_drawn`, carrying whether Plotly drew them without an error,
as `loadFinished` carried whether the page loaded). The assertions after
each wait are unchanged. The tests and fixtures (18):

| Test or fixture |
|---|
| `test_results_widget.py::test_a_page_reload_during_a_save_still_saves` |
| `test_results_widget.py::test_save_plot_as_png_writes_a_real_png_file` |
| `test_results_widget.py::test_save_plot_as_png_appends_extension_if_missing` |
| `test_results_widget.py::test_redraw_does_not_reenable_save_button_while_a_png_poll_is_in_flight` |
| `test_results_widget.py::test_save_plot_as_png_is_a_no_op_while_a_poll_is_already_in_flight` |
| `test_results_widget.py::test_save_plot_as_png_poll_state_resets_after_completion_allowing_a_later_save` |
| `test_results_widget.py::test_save_plot_as_svg_writes_a_real_svg_file` |
| `test_results_widget.py::test_save_plot_as_svg_appends_extension_if_missing` |
| `test_results_widget.py::test_save_png_and_save_svg_share_the_same_re_entrancy_guard` |
| `test_results_widget.py::test_redraw_does_not_reenable_save_svg_button_while_a_poll_is_in_flight` |
| `test_results_widget.py::test_access_timeline_renders_in_the_real_webview` |
| `test_results_widget.py::test_save_plot_default_name_is_access_timeline_in_that_view` |
| `test_results_widget.py::test_a_large_series_still_shows_when_selected` |
| `test_results_widget.py::test_plot_page_fills_the_view_without_a_scroll_bar` |
| `test_plot_workspace.py::test_the_grid_links_its_x_axes_in_the_page` |
| `test_plot_workspace.py::test_export_all_writes_every_plot_its_data_and_the_provenance` |
| `test_results_cursor.py::plot` |
| `test_results_cursor.py::test_on_a_utc_axis_the_cursor_round_trips_through_the_plotted_text` |

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_shell_reachability.py` row "(none)" (Results › Overview) | No check: nothing to reach before M6 | Results › Overview is shown in the Results area | The row of §5.2 is reachable |

### Changed: what M6a changes on purpose

| Test | Before | Now | Why |
|---|---|---|---|
| `test_workspace.py::test_the_areas_and_what_they_hold` | The Results area's tabs: Plots, Dashboard, Output, Compare | Overview, Plots, Dashboard, Output, Compare | M6's criterion: Overview metric cards from `engine.run_summary` |

### Added

- `tests/gui/test_plot_view.py` (5 tests): the page loaded once and each
  change (another plot, a plot added, another x axis) drawn in it; a
  figure built once until what it shows changes (the x axis, the theme);
  one construction giving the figure the earlier steps gave; the layout
  saved after the click and read back at once by another view; the
  start-up objects frozen out of full collections.
- `tests/gui/test_results_overview.py` (7 tests): the empty state's Run;
  a card per figure with its value and unit; critical only below the
  scenario's thresholds, with an icon and the words; the figures worked
  out off the GUI thread; a run shown while another is worked out wins;
  the provenance popover; a run ending shows its overview in the main
  window.

## M6b The tables and analysis views

### Changed: how a test reaches the widget

Output's and Monte Carlo's tables are a `DataTable` (a `QTableView` over a
model) instead of a `QTableWidget`; a test that read a `QTableWidget`
member reads the same thing through the table.

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_mission_output_widget.py::test_none_summary_clears_the_table` | `table.rowCount()` | `table.row_count()` | Rows before; none after, and the table hidden |
| `test_mission_output_widget.py::test_summary_shows_one_column_per_report_and_one_row_per_value` | `table.item(0, 0).toolTip()` | `table.cell_tooltip(0, 0)` | The first row's code name in its tooltip |
| `test_mission_output_widget.py::test_clear_empties_the_table` | `table.rowCount()` | `table.row_count()` | No rows after clear |
| `test_mission_output_widget.py::test_the_report_at_the_time_cursor_is_marked_and_a_header_click_moves_the_cursor` | `table.horizontalHeaderItem(n).font().bold()`, `table.horizontalHeader()` | `table.header_is_bold(n)`, `table.view.horizontalHeader()` | The report at the cursor in bold; a header click moves the cursor, the quantity column does not |
| `test_monte_carlo_results_widget.py::test_a_saved_batch_shows_tiles_plots_and_a_sortable_run_table` | `rowCount()`, `horizontalHeaderItem(c).text()`, `sortItems(1, ...)`, `item(r, 0).text()` | `row_count()`, `header_text(c)`, `sort_by(1, ...)`, `cell(r, 0)` | Five rows, the headers, a numeric sort by Cd |
| `test_monte_carlo_results_widget.py` (the spacecraft switch test) | `horizontalHeaderItem(columnCount() - 1).text()` | `header_text(column_count() - 1)` | The last column is the chosen spacecraft's |

The end of a run is shown in steps, one an event-loop turn (M6b). A test
that calls `_on_run_finished` or `_on_run_cancelled` directly and reads
the views at once now takes the steps first with `window.finish_run_end()`
(what a new run, clearing the views and closing do); the assertions after
it are unchanged:

| Test or helper |
|---|
| `test_main_window.py::test_run_finished_with_command_summary_shows_mission_output_tab` |
| `test_main_window.py::test_run_finished_without_command_summary_shows_results_tab` |
| `test_main_window.py::test_run_cancelled_updates_results_widget_and_status` |
| `test_main_window.py::test_run_cancelled_with_command_summary_shows_mission_output_tab` |
| `test_run_record.py::_finish_a_run` (five tests) |
| `test_stale_results_and_window_size.py::_finish_a_run` |
| `test_workspace.py::_finish_a_run` (two tests) |

Budget's three tables and Compare's three are a `DataTable` too (M6b); the
same reads, through the table:

| Test file | Before | Now | Assertions kept |
|---|---|---|---|
| `test_budget_widget.py` (four tests) | `rowCount()`, `item(r, c).text()`, `item(r, 0).font().bold()`, `selectRow(r)` | `row_count()`, `cell(r, c)`, `row_is_bold(r)`, `view.selectRow(r)` | The contributors, the worst case in bold, picking a launch date or an altitude shows its budget |
| `test_compare_tab.py` (`_row`, `_column` and four tests) | `horizontalHeaderItem(c).text()`, `columnCount()`, `item(r, c).text()`, `rowCount()`, `item(r, c).textAlignment()` | `header_text(c)`, `column_count()`, `cell(r, c)`, `row_count()`, `cell_alignment(r, c)` | The summary's deltas against the base, the inputs that differ, the events counted, numbers right-aligned |
| `test_workspace.py::test_the_compare_tab_lists_runs_and_their_input_differences` | `inputs_table.item(row, 0).text()`, `rowCount()` | `inputs_table.cell(row, 0)`, `row_count()` | The inputs that differ |

## M7 Timeline and plots

### Changed: how a test reaches the widget

The Timeline's table is a `DataTable` whose rows are made when shown and
sort themselves (M7); the tests read it through the table, and a row's
event through `row_event(row)` (it was the first cell's `UserRole`):

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_event_timeline_widget.py::_column` | `horizontalHeaderItem(c).text()`, `columnCount()` | `header_text(c)`, `column_count()` | The column of a heading |
| `test_event_timeline_widget.py::test_the_cursor_emits_only_when_it_moves` | `rowCount()`, `item(r, 0).data(UserRole)`, `item(1, 0).toolTip()`, `sortItems(2, ...)`, `item(0, 3).text()` | `row_count()`, `row_event(r).start_s`, `cell_tooltip(1, 0)`, `sort_by(2, ...)`, `cell(0, 3)` | Three rows earliest first, the detail on hover, durations sorted as numbers |
| `test_event_timeline_widget.py::test_kind_filters_hide_rows_in_the_table_and_the_timeline` | `rowCount()` | `row_count()` | Two rows, one lane |
| `test_event_timeline_widget.py::test_a_click_on_the_timeline_or_a_row_moves_the_shared_cursor` | `sortItems(0, ...)`, `_on_row_clicked(2, 0)` | `sort_by(0, ...)`, `_on_row_clicked(2)` | A row click moves the cursor to its event |
| `test_event_timeline_widget.py::test_no_result_shows_a_hint_and_disables_export` | `rowCount()` | `row_count()` | No rows |
| `test_event_timeline_widget.py::test_headings_carry_the_time_system_and_units_and_numbers_align_right` | `horizontalHeaderItem(2).text()`, `item(r, c).text()`, `item(r, c).textAlignment()` | `header_text(2)`, `cell(r, c)`, `cell_alignment(r, c)` | The headings, the UTC and hour texts, numbers right-aligned |
| `test_event_timeline_widget.py::test_search_and_the_station_filter_narrow_the_timeline_table_and_export` | `rowCount()` | `row_count()` | The rows each filter leaves |
| `test_event_timeline_widget.py::test_ctrl_c_copies_the_selected_rows_as_tsv_with_headings` | `table.selectRow(0)`, `setFocus()`, Ctrl+C on `table` | the same on `table.view` | The selected row as TSV with the headings |
| `test_event_timeline_widget.py::test_arrow_keys_on_the_table_move_the_cursor_and_ctrl_f_finds` | `setCurrentCell(0, 0)`, Down on `table`, `sortItems(2, ...)` | `view.setCurrentIndex(...)`, Down on `table.view`, `sort_by(2, ...)` | The rows move the cursor; a sort does not; Ctrl+F |

### Added

- `tests/gui/test_timeline_scale.py` (8 tests): 10,000 events with only
  the rows shown made; a header sorting them by value; the search
  narrowing them; merged spans a pixel and the event under the pointer;
  the UTC axis with Z, elapsed time without an epoch; zoom and pan by
  keys, Shift+wheel and a right-button drag; and an export keeping every
  sample of a line the plot thins.

## M8 Reports, exports and Settings

### Changed: how a test reaches the widget

The Reports area holds tabs (M8): **Exports**, then **Flight Software**.
The Flight Software page is reached through them:

| Test | Before | Now | Assertions kept |
|---|---|---|---|
| `test_workspace.py::test_the_areas_and_what_they_hold` | `shell.page("reports").content is window.flight_software_widget` | `shell.page("reports").content is window.reports_views`, its tabs `["Exports", "Flight Software"]` | The Reports area holds the Flight Software page |

### Changed: test isolation

- `tests/gui/conftest.py` gains an autouse fixture, `_isolated_export_log`:
  the export log (each export records when it was written, in the app's
  settings under the home directory) goes to a file outside the test's
  home. Two tests export into their home (`tmp_path`, which the root
  conftest makes the home) and list it:
  `test_plot_workspace.py::test_export_all_writes_every_plot_its_data_and_the_provenance`
  and the new `test_export_files.py`. Without the fixture they would see
  the app's settings file beside the exports. No assertion changes.

### Added

- `tests/gui/test_export_files.py` (1 test): every covered export (the
  results CSVs and provenance, the events CSV, the Mission Output CSV and
  provenance, the Monte Carlo table, the budget CSV, the `.obj` and
  `.mtl`, the SIL report) written by `scripts/make_export_references.py`
  and compared, byte for byte, with what 1.1.0 wrote
  (`tests/data/exports_1_1_0.zip`, written on Linux). On Windows, where
  files written in text mode end lines with CRLF (1.1.0's did too), the
  comparison ignores line endings; the script writes the budget's
  clipboard text as bytes, so no platform changes it.
- `tests/gui/test_reports_and_settings.py` (6 tests): Reports › Exports
  lists the twelve exports, never written at first; an export is logged
  with its UTC time and path; a row opens the view that makes it; the UI
  scale kept for the next start (and the environment's own winning);
  toasts fading unless motion is reduced; the Vizard location browsed
  and cleared.

## M9 Final pass

### Added

- `tests/gui/test_keyboard_walk.py` (8 tests): for each area (7), the
  area by its shortcut, then Tab reaches every control in it that takes
  the keyboard and never lands on a hidden widget, an exclusive group of
  buttons counting as one stop; and the Inspector names a focused control
  by what it shows, not its class name. No existing test changed.

## Release 1.3.0 preparation

- `test_reports_and_settings.py::test_toasts_fade_unless_motion_is_reduced`
  (new in M8) waited at most 650 ms for a 150 ms fade to end and 1.5 s
  for the toast to go; under a loaded full run (four workers) the fade
  took longer and the test failed once. Longer waits alone did not fix
  it (it failed again in CI with 5 s): the 600 ms toast was fully shown
  only from 150 ms to 450 ms, and a stall of more than 300 ms ran the
  fade-in's end and the fade-out's start in one pass, so the test never
  saw the toast without an effect. The first toast now shows for 3 s, the
  test also waits for the fade-out, and the waits are 2.5 s and 10 s. The
  assertions are unchanged except the added fade-out check: the toast
  fades in, the fade ends, it fades out and goes, and with reduce motion
  there is no fade. Under heavy load the test also found a bug in
  `feedback._fade`: a fade-in that ended after the fade-out began removed
  the fade-out's effect. It now removes only its own.

## After 1.3.1

- `tests/gui/conftest.py` gained a `pytest_sessionfinish` hook that
  deletes every top-level widget left over, with its web pages, before
  the test process exits. Without it, a run of the GUI tests ended in a
  segmentation fault after every test had passed: at exit the default
  web profile could go before a `QWebEngineView`'s page ("Release of
  profile requested but WebEnginePage still not deleted").
  `tests/gui/test_results_widget.py` alone crashed three runs in three
  (exit 139) and passes three in three with the hook (exit 0). Under
  xdist the crash showed as a worker that "crashed while running" its
  last test (`test_label_text.py::test_help_text_is_short_and_plain[spacecraft-07]`,
  two full runs in two on #127's branch). No test changed.

## Python 3.14 only: test cleanup (2026-10-27)

Approved by the user ("As per your recommendation") after the Phase 3
proposal. Each deleted test repeats another one exactly.

### Deleted (12)

- `test_scenario_schema.py`: `test_none_fsw_mode_is_valid`,
  `test_none_vizard_model_path_is_valid`,
  `test_monte_carlo_defaults_to_disabled_and_validates` and
  `test_mission_sequence_empty_does_not_affect_existing_validation`
  (each only `_minimal_scenario().validate()`, as
  `test_minimal_scenario_validates`);
  `test_thermal_sensor_with_no_mass_kg_set_still_validates` (as
  `test_thermal_sensor_with_required_params_validates`, which has no mass
  either).
- `test_command.py`: `test_maneuver_defaults_to_inertial_frame` and
  `test_lambert_transfer_defaults_num_revolutions_and_constraints` (the
  same command and assertion as `test_maneuver_valid` and
  `test_lambert_transfer_valid`).
- `gui/test_template_wizard.py`:
  `test_finishing_without_changes_reproduces_the_original_scenario`
  (template 03, one case of `test_every_spec_round_trips_with_no_edits`).
- `gui/test_vizard_launcher.py`:
  `test_fetch_vizard_rejects_a_response_over_the_size_cap` (contained in
  `test_a_cancelled_or_oversized_download_leaves_no_partial_file`, now
  cited by S-05 in `security_analysis.md`);
  `test_launch_omits_direct_comm_flag_when_not_given` (the app-bundle test
  asserts the same argument list).
- `test_spaceweather.py`: `test_resolve_unknown_source_raises` (the same
  path as `test_removed_sources_are_rejected_as_unknown`);
  `test_resolve_has_no_activity_level_any_more` (only that Python refuses
  an unknown keyword).

Kept although proposed: `test_launch_no_longer_inspects_an_empty_app_bundle`
is the only test that an empty `.app` is not refused.

### Changed

- `test_vizard_fuel_tank_panel.py::test_fuel_tank_panel_label_is_distinct_from_station_keepings_own_propellant_panel`
  asserted `"Fuel Tank" != "Propellant"`, two literals. It now builds the
  Vizard panels of one spacecraft with a fuel tank and station keeping,
  and checks both are there under different labels; renaming the
  station-keeping panel "Fuel Tank" makes it fail.
- The ten tests of what happens without Basilisk
  (`test_cli.py`: run, kernels-status, monte-carlo,
  generate-phasing-formation; `gui/test_main_window.py`: Run;
  `gui/test_run_worker.py`: run, live run, Monte Carlo;
  `gui/test_spacecraft_editor.py`: the phasing generator;
  `gui/test_startup_fetch_dialog.py`: the kernel fetch) were skipped
  wherever Basilisk is installed, so in CI always. They now run with
  Basilisk hidden (the `basilisk_unavailable` fixture). Running found the
  main-window test stale: it waited for a message box that U-39 replaced
  with the run's problem report; it now checks `window.run_problems`, as
  the other failed-run tests do. Same behaviour checked: one problem
  saying Basilisk is not installed, Run enabled again.
- `test_time_system.py::test_month_abbreviation_ignores_the_process_locale`
  skipped without `de_DE.UTF-8`, which no CI runner had. It tries the
  Windows names too, and CI's Linux test job generates the locale. With
  the old `strftime("%b")` it fails ("2030 MÄR 01").
- Ten tests of about a minute or more carry the new `slow` marker; CI
  runs them all.
- `tests/gui/conftest.py` gained `_closed_widgets_deleted_after_the_test`,
  an autouse fixture that runs Qt's deferred deletes after each GUI test.
  pytest-qt closes the widgets a test registered and calls
  `deleteLater()`, then only processes events, which does not delete
  them: the keyboard-walk tests' main window, web views included, lived
  on into the next test. On Python 3.14 the next test,
  `test_label_text.py`'s first case (`spacecraft-07`), crashed in its
  fixture's app-wide restyle (`apply_theme` → `setStyleSheet`), eight
  runs in eight; with the fixture, five in five pass. The same code on
  Python 3.13 (same PySide6 6.11.2, pytest-qt 4.5.0) did not crash. No
  test changed.
- `test_label_text.py::test_help_text_is_short_and_plain` and
  `test_input_borders.py::test_every_input_box_has_a_visible_border` skip
  a tab widget deleted while the dialog's tabs are walked. The main
  window's hidden label form (`spacecraft_editor.prepare_labels`, built a
  section per event-loop turn and deleted once read) was among the tab
  widgets collected first, and was deleted during the walk:
  "Internal C++ object (TabWidget) already deleted" for the main-window
  case run right after
  `test_keyboard_cursor.py::test_alt_backspace_clears_the_time_cursor_in_the_window`
  (also on `develop`, Python 3.13). The form is hidden, so no label or
  input of it was ever checked; nothing checked is left out.

## The integrator's tolerances (2026-10-28)

- `test_export_files.py::test_every_export_is_byte_identical_to_1_1_0`:
  a provenance record now holds the integrator's tolerances (audit E3).
  The two provenance files are compared without those two keys, which
  must be present; the rest of them, and every other file, is still
  1.1.0's byte for byte. The reference zip is unchanged.

## Random seeds (2026-10-28)

- `test_export_files.py`: the provenance files are also compared without
  the new `rng_seed` and `rng_seeds` keys (audit E5); the helper is
  renamed `_without_new_keys`. Every other byte is still 1.1.0's.
- Added `test_propagation_setup_dialog.py::test_the_random_seed_round_trips`.

## GUI fixes from the audit, batch 1 (2026-10-28)

- `test_messages.py::test_confirmations_name_the_object_and_the_consequence`:
  the unsaved-changes question's expected text is now "Save the changes
  to my mission first? Changes not saved cannot be recovered." (it offers
  Save, audit G6); the test still checks that it names the scenario and
  the consequence.
- Added `test_main_window.py::test_save_in_the_unsaved_changes_question_saves_then_goes_ahead`
  and, in `test_data_panel_widget.py`,
  `test_a_failed_read_in_the_child_comes_back_as_its_message` and
  `test_a_failed_read_is_shown_with_retry_and_retry_reads_again` (G10).

## The run's length with a Mission Sequence (2026-10-28)

- Added `test_scenario_editor.py::test_the_duration_says_when_the_mission_sequence_decides`
  (audit G4). No existing test changed.

## Toasts fade out every time (2026-10-28)

- Added `test_feedback.py::test_a_toast_fades_out_before_it_is_dismissed_whatever_order_its_timers_fire`.
  No existing test changed.

## Monte Carlo off, said before Run (2026-10-28)

- Added `test_main_window.py::test_the_run_page_says_monte_carlo_is_off_before_run`
  (audit G5). No existing test changed.

## Exports off the GUI thread (2026-10-28)

- `test_results_widget.py::test_export_writes_csv_files`: the export is
  written by a worker now (audit G2), so the test waits for its report
  (`qtbot.waitUntil`) before it reads the folder; what it checks is
  unchanged.
- `test_timeline_scale.py::test_an_export_keeps_every_sample_the_plot_thins`:
  the same; it waits for the export (`wait_for_export()`) before it reads
  the CSV.
- Added `test_results_widget.py::test_an_export_runs_off_the_gui_thread_with_progress_and_cancel`
  and `test_results.py::test_result_set_export_csv_reports_progress_and_can_be_stopped`.

## A Monte Carlo batch can be cancelled (2026-10-28)

- Added `test_main_window.py::test_a_running_monte_carlo_batch_can_be_cancelled_and_the_window_closed`
  and, in `test_run_worker.py`,
  `test_a_monte_carlo_batch_can_be_cancelled_keeping_the_runs_finished` (1
  and 2 threads) and `test_cancel_ends_the_processes_the_batch_started_too`
  (audit G3). No existing test changed.

## Control borders at 3:1 (2026-10-28)

- Added `test_dark_theme.py::test_fields_and_check_boxes_have_a_border_of_three_to_one`
  (audit G7). No existing test changed; `test_design_rules.py`'s token
  table check reads the new row of `docs/DESIGN.md`.

## The export test's race (2026-10-28)

| Test | Before | Now | Why |
|---|---|---|---|
| `test_results_widget.py::test_an_export_runs_off_the_gui_thread_with_progress_and_cancel` | Read "Exporting 1 of 2" as soon as the worker began its first file; opened the worker's gate only after its asserts | Waits for the label to say it (up to 10 s), then checks the same things; the gate opens in a `finally` | The progress signal is queued across threads, so the label can still say "Exporting..." when the file is begun: 6 of 64 runs failed under load (8 workers), 0 of 128 now. A failed assert also left the worker writing into the next test's event loop (`test_run_record.py` failed with the export's "already deleted" error). Same assertions |

## A Monte Carlo batch and pandas (2026-10-28)

- Added `test_run_worker.py::test_a_monte_carlo_worker_imports_pandas_on_the_thread_that_makes_it`.

## An export that outlives its view (2026-10-28)

- Added `test_results_widget.py::test_an_export_that_ends_after_its_widget_is_gone_touches_nothing`.
  No existing test changed.

## Room for results at 1280 x 720 (2026-10-28)

A new window starts without the Problems panel and, on a screen narrower
than 1600 px (the offscreen test screen is 800 px), without the
Inspector; the Inspector shows fields only (audit G8).

### Changed: a test's precondition, no assertion

| Test | Before | Now | Why |
|---|---|---|---|
| `test_panels.py::test_ctrl_i_shows_and_hides_the_inspector`, `::test_each_project_keeps_its_own_layout`, `test_workspace.py::test_the_layout_is_kept_and_reset`, `test_load_scenario_widget.py::test_left_pane_content_fits_a_default_window_without_horizontal_scrolling` | A new window had the Inspector shown | The new `wide_screen` fixture (`tests/gui/conftest.py`) sets the 1600 px limit to 0, so the window starts with the Inspector shown, as on a wide screen | Each tests something with the Inspector shown (hiding and showing it, keeping it in a layout, Reset Layout bringing it back, Home fitting beside it); the assertions are unchanged |
| `test_panels.py::test_a_keyboard_only_walk_of_the_shell` | `Ctrl+J` hid the open Problems panel, then showed it with the focus in it | Asserts it starts hidden, then `Ctrl+J` shows it with the focus in it, hides it, and shows it again with the focus in it | Problems starts hidden; the same three behaviours are checked, in the order the new start allows |

### Changed: test isolation only

| Test | Before | Now | Why |
|---|---|---|---|
| `test_forms.py` (module fixture `_shared_window`) | Its window was made before any test's home was patched, so it read and wrote the real `~/.spacemissionstudio/layout.ini`; the Inspector was shown when that file said so | The window has a home of its own (a module temporary folder) and shows the Inspector itself | CI (an empty home) failed all 31 `test_every_page_of_the_template` cases on this change, while a machine with a kept layout passed; reproduced with an empty `HOME`. The walk is at 1280 px with the Inspector shown, as its docstring says; no assertion changed |
| `test_shell_reachability.py` (module fixture `window`) | The same: the real home's layout read and written | A home of its own | The same leak; its tests passed either way; no assertion changed |

### One behaviour changed on purpose

`test_keyboard_walk.py::test_the_inspector_names_a_focused_control_by_what_it_shows`
asserted that a focused tab bar was named "Plots" (by its current tab,
never "_TabBar"). The audit asks the Inspector to show fields only, so
the test now asserts the empty state for a tab bar, and still that it is
never named "_TabBar".

### Added

- `test_panels.py::test_an_edit_that_makes_the_scenario_invalid_opens_the_problems_panel`,
  `::test_a_new_window_on_a_small_screen_starts_without_the_inspector` and
  `::test_the_inspector_shows_fields_only`: each fails on the code before
  (checked).

## Parser, look-ahead and exit codes (2026-10-29)

- Added `test_scenario_schema.py::test_json_nested_too_deeply_for_the_parser_is_a_refusal`,
  `::test_json_with_a_number_too_long_for_python_is_a_refusal`
  and `::test_no_template_however_mangled_gets_past_the_loader_as_anything_but_a_refusal`,
  `test_autosave.py::test_a_recovery_file_the_loader_would_refuse_is_ignored_not_raised`,
  and `test_cli.py::test_an_internal_error_has_its_own_status_and_names_the_log`
  and `::test_lifetime_refuses_a_look_ahead_outside_one_hundred_years` (audit R5,
  R6, R13). The engine's refusal keeps the words
  `test_lifetime.py::test_a_lookahead_that_is_not_positive_is_refused` matches.

| Test | Before | Now | Why |
|---|---|---|---|
| `test_cli.py::test_generate_phasing_formation_passes_every_request_field_through` | Its stand-in generator raised `_Captured` to stop the command, and the test expected it to leave `main` | Expects `main` to return `EXIT_INTERNAL_ERROR` (4) | `main` now reports any unexpected exception as an internal error (R13); the stand-in still stops the command, and the same request fields are asserted |

## Output folder and input limits (2026-10-29)

- Added `test_scenario_schema.py::test_a_name_longer_than_sixty_four_characters_is_refused_at_validation`,
  `::test_a_scenario_that_asks_for_too_much_is_refused` and
  `::test_a_scenario_file_larger_than_the_limit_is_refused_unread`,
  `test_constellation.py::test_more_satellites_than_a_scenario_holds_are_refused_before_any_is_made`,
  and `test_cli.py::test_run_refuses_an_output_folder_it_cannot_write_before_the_simulation`,
  `::test_a_run_into_a_used_folder_names_the_files_it_did_not_write` and
  `::test_ccsds_messages_larger_than_the_limit_are_refused_unread` (audit
  R7, R8, R9). No existing test changed.

## Temporary folders and refusals of the wrong shape (2026-10-29)

- Added `test_temp_folders.py` (5 tests) and
  `test_scenario_schema.py::test_a_file_of_the_wrong_shape_is_refused_naming_where`
  (8 cases) (audit R14 and R5's notes). Each fails on the code before
  (checked).

| Test | Before | Now | Why |
|---|---|---|---|
| `test_scenario_schema.py::test_load_scenario_rejects_an_unknown_field_naming_it` | Matched Python's `unexpected keyword argument 'bogus_field'` | Matches `unexpected field 'bogus_field'` | The refusal now names the field in its own words and says where (`spacecraft[0]: unexpected field 'bogus_field', not one this version knows`); the test still checks that the field is named |

## Regression baseline (2026-10-29)

- Added `test_golden_outputs.py`: `::test_every_template_gives_its_recorded_outputs`
  (31 cases, one per template; 03, 05, 24 and 29 marked `slow`),
  `::test_every_template_has_a_recorded_fingerprint` and
  `::test_the_comparison_holds_each_number_to_its_own_scale`,
  `::test_an_ill_conditioned_angle_is_held_to_its_floor_and_compares_modulo_two_pi`
  `::test_sensor_noise_compares_value_by_value_only_on_the_library_that_recorded_it`
  and `::test_on_another_library_numbers_are_held_to_one_percent`,
  with the helper `tests/golden_capture.py` and the data in
  `tests/golden/`; and `test_seeds.py::test_a_recorders_seed_key_reads_the_same_on_every_platform`.
  No existing test changed.

## Engine and command-line defects (2026-10-29)

- Added `test_orbit_number.py::test_a_mars_orbit_counts_its_own_turns_however_sparsely_recorded`
  (3 cases), `::test_a_run_recorded_before_the_gm_was_kept_uses_earths_for_an_earth_run`
  and `::test_a_mars_run_recorded_before_the_gm_was_kept_takes_mars_from_its_frames`
  (audit 3.1), `test_run_summary.py::test_the_delta_v_includes_the_roe_formation_controller`
  (3.5) and `::test_the_semi_major_axis_change_averages_over_the_central_bodys_own_orbit`
  (3.14), `test_long_run.py::test_a_split_run_records_the_whole_runs_provenance` (3.3),
  `test_earth_orientation.py::test_a_run_on_predicted_earth_orientation_says_so_in_its_warnings`
  (3.6), `test_scenario_checks.py::test_a_check_that_fails_says_so_instead_of_passing_silently`
  (3.11), `test_mission_engine.py::test_a_stop_epoch_across_a_leap_second_counts_it` (3.13),
  and `test_cli.py::test_a_monte_carlo_batch_with_a_failed_run_exits_3` and
  `::test_kernels_status_with_a_missing_kernel_exits_2` (3.2). Each fails on
  the code before (checked: 13 failed).

| Test | Before | Now | Why |
|---|---|---|---|
| `test_sil.py::test_the_cli_runs_sil_writes_the_report_and_gates_on_the_error` | `sil --max-error` over the limit expected exit 2 | Expects `cli.EXIT_CHECK_FAILED` (5) | 2 is a missing component or a usage error in ICD-02; a check that ran and did not pass now has its own status (audit 3.2). The same failure is asserted |
| `test_fsw_export.py::test_the_cli_exports_and_records` | `fsw-status` on a stale export expected exit 2 | Expects `cli.EXIT_CHECK_FAILED` (5) | As above |
| `test_offline.py::test_validate_and_export_a_template_offline` | `kernels-status` accepted 0 or 1 | Accepts 0 or 2 | A missing kernel is a missing component, 2 in ICD-02, not an input error (audit 3.2) |
| `test_results.py::test_result_set_export_csv_with_provenance_writes_sidecar_json` | Expected the provenance record's fields up to `series_frames` | Also expects `central_body` ("") and `central_body_mu_m3_s2` (0.0) | The record now keeps the run's central body and GM (audit 3.1); the test still checks every field the file holds |
| `tests/gui/test_export_files.py::test_every_export_is_byte_identical_to_1_1_0` | Removed the four provenance keys added since 1.1.0 before comparing | Also removes `central_body` and `central_body_mu_m3_s2`, which must be there | As above; every other byte is still compared with 1.1.0's, as for the earlier keys |

## GUI defects of the transparency audit (2026-10-29)

- Added `tests/gui/test_spacecraft_editor.py::test_unticked_control_gains_show_the_gains_the_engine_applies`
  (3.4), `tests/gui/test_monte_carlo_editor.py::test_a_new_dispersion_starts_at_the_spacecrafts_own_value_with_no_spread`
  and `::test_the_scenario_editor_gives_the_dispersions_each_spacecrafts_own_values`
  (3.7), `tests/gui/test_orbit_ic_widget.py::test_the_semi_major_axis_help_gives_the_right_altitude_and_period`
  (3.8), `test_scenario_schema.py::test_the_rf_link_docstring_describes_the_model_that_is_run`
  (3.10) and `tests/gui/test_results_widget.py::test_a_run_warning_gets_the_drift_explanation_only_when_it_is_a_drift_warning`
  (3.12). Each fails on the code before (checked).

| Test | Before | Now | Why |
|---|---|---|---|
| `tests/gui/test_ground_station_editor.py::test_dialog_default` | A new station had a 45 dBi receive gain | 0 dBi, and the whole station equals `GroundStationConfig`'s defaults | A new station now takes the schema's defaults (audit 3.9); the other defaults (gs-1, 10 deg, 290 K) are still asserted |

## The run record (2026-10-29)

- Added `test_dependencies.py::test_a_large_file_is_hashed_once_and_its_hash_kept_until_it_changes`
  and `::test_an_installed_file_is_hashed_again_and_a_changed_one_is_warned_of`
  (Phase 2d), `test_spaceweather.py::test_the_resolution_names_the_msfc_table_only_when_the_run_needs_it`
  and `test_long_run.py::test_a_split_run_and_a_whole_run_record_the_msfc_table_they_used`
  (2d), `test_cli.py::test_run_keeps_the_scenario_as_run_and_the_file_it_came_from`
  (2a, 2b, 2f), `test_results.py::test_the_exported_provenance_lists_the_runs_warnings`
  (2f) and `tests/gui/test_main_window.py::test_a_run_from_an_unchanged_file_records_the_file_and_an_edited_one_does_not`
  (2b). Each fails on the code before (checked: 7 failed).

| Test | Before | Now | Why |
|---|---|---|---|
| `test_results.py::test_result_set_export_csv_with_provenance_writes_sidecar_json` | Expected the record's fields up to `central_body_mu_m3_s2` | Also expects `scenario_file`, `scenario_file_sha256` ("") and `run_warnings` ([]) | The record names the file run and the export lists the warnings; the test still checks every field the file holds |
| `tests/gui/test_export_files.py::test_every_export_is_byte_identical_to_1_1_0` | Removed the six provenance keys added since 1.1.0 before comparing | Also removes `scenario_file`, `scenario_file_sha256` and `run_warnings`, which must be there | As above; every other byte is still compared with 1.1.0's |
