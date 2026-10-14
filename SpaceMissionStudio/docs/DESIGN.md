# SpaceMissionStudio design system

The reference for how the app looks and behaves: its colour tokens, type,
layout, components, message and feedback patterns, and keyboard model.
It describes what the code does today. Where a rule is checked by a test,
the test is named; where the app falls short of `docs/ux-standard.md`,
the gap is listed under [Known gaps](#known-gaps) rather than glossed
over.

- **Standard:** `docs/ux-standard.md` (the goals).
- **Audit:** `docs/ux-audit.md` (the findings and each iteration's changes).
- **Single source of truth:** `spacemissionstudio/gui/theme.py`. It builds
  the QSS stylesheet and the `QPalette`. Widgets take colours from
  `theme.PALETTE` and never pick their own.

## Contents

1. [Foundations](#foundations): colour, status colours, data colours,
   type, layout, icons
2. [Components](#components)
3. [Patterns](#patterns): messages, feedback, keyboard, themes, long
   operations, empty states
4. [Rules for new code](#rules-for-new-code)
5. [Checking a change](#checking-a-change)
6. [Known gaps](#known-gaps)

## Foundations

### Colour

The app follows IBM's Carbon design system:

- **Light theme:** Carbon g10 (`theme.LIGHT`).
- **Dark theme:** Carbon g100 (`theme.DARK`), under the same keys.

`theme.PALETTE` is one dict. `select_palette(theme)` fills it in place
before the main window is built. Widgets read it when they are built, so
a theme change applies at the next start.

Where Carbon g100 has no token, the dark theme uses the hue's 90 step as
the fill and its 30 step as the text on it. This applies to the
notification backgrounds, which g100 makes one grey, and keeps a toast's
or banner's colour readable.

| Token | Light (g10) | Dark (g100) | Carbon token / use |
|---|---|---|---|
| `bg` | `#F4F4F4` | `#161616` | background |
| `surface` | `#FFFFFF` | `#262626` | layer-01: tiles, group boxes, tab panes, popups |
| `surface_alt` | `#F4F4F4` | `#393939` | layer-02 (on layer-01): status bar, recessed panels, disabled fields |
| `field` | `#F4F4F4` | `#393939` | field-02: inputs on layer-01 |
| `hover` | `#E8E8E8` | `#333333` | layer-hover-01 |
| `selected` | `#E0E0E0` | `#393939` | layer-selected-01 (selected rows and list items) |
| `border` | `#E0E0E0` | `#393939` | border-subtle-01 |
| `border_strong` | `#8D8D8D` | `#6F6F6F` | border-strong-01 (field bottom rules, checkbox outlines) |
| `field_edge` | `#C6C6C6` | `#525252` | gray 30: a field's other three edges (not Carbon; see the fields rule) |
| `text` | `#161616` | `#F4F4F4` | text-primary (also icon-primary) |
| `text_muted` | `#525252` | `#C6C6C6` | text-secondary |
| `text_disabled` | `#C6C6C6` | `#6F6F6F` | text-disabled |
| `disabled_fill` | `#C6C6C6` | `#525252` | button-disabled |
| `on_disabled_fill` | `#8D8D8D` | `#8D8D8D` | text-on-color-disabled |
| `accent` | `#0F62FE` | `#0F62FE` | interactive, button-primary, border-interactive (fills, indicators) |
| `accent_text` | `#0F62FE` | `#78A9FF` | link-primary: blue text and the tertiary buttons' outline |
| `focus` | `#0F62FE` | `#FFFFFF` | focus: the 2 px outline of the focused field or button |
| `accent_hover` | `#0050E6` | `#0050E6` | button-primary-hover |
| `accent_pressed` | `#002D9C` | `#002D9C` | button-primary-active |
| `accent_soft` | `#D0E2FF` | `#002D9C` | highlight (text selection, soft accent) |
| `on_accent` | `#FFFFFF` | `#FFFFFF` | text-on-color |
| `inverse` | `#393939` | `#F4F4F4` | background-inverse (tooltips) |
| `on_inverse` | `#FFFFFF` | `#161616` | text-inverse: tooltip text |
| `icon_inverse` | `#FFFFFF` | `#161616` | icon-inverse: the tick on a ticked box (filled with icon-primary, "text") |
| `danger` | `#DA1E28` | `#FA4D56` | support-error |
| `success` | `#24A148` | `#42BE65` | support-success |
| `warning` | `#8E6A00` | `#F1C21B` | yellow 60: warning TEXT (support-warning #F1C21B is too light for text) |
| `warning_fill` | `#F1C21B` | `#F1C21B` | support-warning (fills, never text) |
| `danger_soft` | `#FFF1F1` | `#520408` | notification-background-error |
| `success_soft` | `#DEFBE6` | `#022D0D` | notification-background-success |
| `warning_soft` | `#FCF4D6` | `#302400` | notification-background-warning |
| `info_soft` | `#EDF5FF` | `#001D6C` | notification-background-info |
| `success_text` | `#0E6027` | `#6FDC8C` | green 70: text on success_soft (support-success is a fill colour) |
| `danger_text` | `#A2191F` | `#FFB3B8` | red 70: text on danger_soft |
| `info_text` | `#0043CE` | `#A6C8FF` | blue 70 (support-info): text on info_soft |
| `info` | `#0043CE` | `#4589FF` | support-info: the info toast's rule |
| `tag_success_bg` | `#A7F0BA` | `#0E6027` | green tag (green 20 / 70) |
| `tag_success_text` | `#0E6027` | `#A7F0BA` | green tag (green 20 / 70) |
| `tag_danger_bg` | `#FFD7D9` | `#A2191F` | red tag (red 20 / 70) |
| `tag_danger_text` | `#A2191F` | `#FFD7D9` | red tag (red 20 / 70) |
| `tag_accent_bg` | `#D0E2FF` | `#0043CE` | blue tag (blue 20 / 70) |
| `tag_accent_text` | `#0043CE` | `#D0E2FF` | blue tag (blue 20 / 70) |

The table is checked against `theme.py` by
`tests/gui/test_design_rules.py`. A token added, removed or changed
there fails the test until this table says the same.

**Contrast.** Every pair the stylesheet and the widgets draw is tested in
both themes (`tests/gui/test_dark_theme.py::test_every_pair_the_app_draws_is_readable`):

- text on its backgrounds: at least 4.5:1;
- indicators and outlines (focus, accent, success): at least 3:1;
- a field's bottom rule: at least 1.5:1.

These are WCAG 2.1 criteria 1.4.3 and 1.4.11.

**Other theme tests.**

- Both themes have the same keys (`test_both_themes_have_the_same_keys`).
- A dark window has no light-theme colour left in its stylesheets
  (`test_a_dark_window_has_no_light_colour_left`).

### Status colours

A status colour means one thing everywhere. It never decorates and never
stands alone: a status is always written out as well (a tag's text, a
problem's "Error:" or "Warning:", a toast's words).

| Meaning | Text | Fill / tag | Where |
|---|---|---|---|
| Error, failed, blocks a run | `danger`, `danger_text` | `danger_soft`, `tag_danger_*` | Problems, field errors, error toasts, a failed run's chip, the red tree counts |
| Warning, look at this | `warning` | `warning_soft`, `warning_fill` | Plausibility warnings, out-of-range values, warning toasts, the yellow tree counts |
| Success, done | `success_text` | `success_soft`, `tag_success_*` | Success toasts, a finished run's chip, met rules |
| Information, selection | `info_text`, `accent_text` | `info_soft`, `tag_accent_*` | Info toasts, Explain badges |
| Neutral | `text` | `selected` | Muted tags |

**Badges** (`gui/badges.py`) are pairs of token names:

- `MUTED`, `SUCCESS`, `DANGER`, `ACCENT`, `WARNING`;
- `badge_style(pair)` looks the pair up when the badge is styled, so it
  takes the theme in use.

**Problem counts in the scenario tree** (`PageTree.set_problem_count`):

- yellow when every problem is a warning;
- red when at least one is an error;
- a tooltip counts each kind.

### Data colours

`theme.SERIES_COLORS` holds eight categorical hues: Carbon's cyan 50,
orange 50, purple 60, yellow 50, teal 50, orange 60, blue 50 and
magenta 60.

- **Order:** fixed, assigned in order and never cycled.
- **Validated:** with the dataviz palette validator, on the white chart
  surface and on the dark one (#262626), unchanged in both themes, so a
  series keeps its colour.
- **No red or green:** they mean error and success.

The 3D view's body axes use x red, y green, z blue. That is an identity
convention, not a status, and is listed in the colour exceptions below.

### Type

| Use | Font | Size | Weight |
|---|---|---|---|
| Body, forms, tables | IBM Plex Sans | 14 px (10.5 pt at 96 dpi), 0.16 px tracking | 400 |
| Headings, selected tabs, section titles | IBM Plex Sans | 14 px | 600 |
| Top bar scenario name | IBM Plex Sans | 16 px | 600 |
| A field's error or warning line | IBM Plex Sans | 12 px | 400 |
| The Log | IBM Plex Mono | 14 px | 400 |

- **Font files:** the WOFF files ship unmodified under the SIL Open Font
  License (`gui/assets/fonts/`).
- **Fallback:** where Qt cannot load them (PySide6 older than 6.7), the
  platform font is used.
- **Tests:** `tests/gui/test_theme.py::test_ibm_plex_is_loaded_and_set_as_the_application_font`.

### Layout

The app shell:

- **Top bar:** the scenario name, its state (unsaved, from a template or
  a file), the last run and a run status chip.
- **Toolbars:** Run is the one primary (filled blue) button.
- **Workspace tabs:** Scenario, Results, Events, Compare, Log.
- **Scenario tab:** the scenario tree on the left. Each spacecraft has a
  node per part of its editor.
- **Side panel (a dock):** Inspector, Explain, Problems.
- **Status bar:** Basilisk version, reference data, Earth orientation
  data, frames.
- **Layout memory:** View > Reset Layout restores the docks; the layout
  is kept between sessions.

| Measure | Value | Where |
|---|---|---|
| Smallest window the views are checked at | 1280 x 720 px | `scripts/capture_screenshots.py --size` |
| Widest a form, a list editor or the template list grows | 960 px (`theme.CONTENT_MAX_WIDTH_PX`) | `scenario_editor._page`, the embedded forms, End of Life, Templates |
| Scenario tree | at least 170 px, 220 px to start | `gui/page_tree.py` |
| Results plot list | 16 % of the pane, 250 to 400 px, until the user drags the divider | `gui/results_widget.py` |
| Toast | at most 360 px wide, 16 px from the window's edge, 8 px apart | `gui/feedback.py` |

**What keeps the full width:** plots, tables, the event timeline, the
JSON view, Compare and the model editor. A form keeps the left edge, and
the Scenario form sits at the top of its page.

**Corners:** square (Carbon), except badges, which are rounded tags.

**Fields:** filled, with a bottom rule and a 2 px focus outline.

**Light edge on the other three sides of a field:** the one deviation
from Carbon, so editable values read as boxes
(`tests/gui/test_input_borders.py`).

### Icons

- **Glyphs:** the stylesheet's arrows, ticks and radio dots are SVGs in
  `gui/assets/`, drawn in the light theme's colours
  (`tests/gui/test_theme.py::test_svg_asset_colors_match_the_palette`).
- **Dark theme:** `theme.themed_asset` recolours them
  (`test_glyphs_are_recoloured_for_the_dark_theme`).
- **Toolbars:** every toolbar action has an icon
  (`test_every_toolbar_action_has_an_icon`). The toolbars show its text
  beside it (`ToolButtonTextBesideIcon`).
- **App icon:** drawn in code (`gui/icons.py`) in its own brand colours,
  listed among the colour exceptions.

## Components

| Component | Code | Use it for |
|---|---|---|
| Page tree | `page_tree.PageTree`: `add_page`, `add_section`, `set_problem_count`, `show_page`, `show_section` | A view with several forms: one node per form, sections per part, problem counts on nodes |
| Embedded form | `page_tree.embed_dialog`, then `setMaximumWidth(CONTENT_MAX_WIDTH_PX)` | A dialog's form shown as a page: no window, no OK/Cancel, long rows wrap |
| Form fields | `widgets.SpinBox`, `DoubleSpinBox`, `PreciseDoubleSpinBox`, `ComboBox` | Numbers and choices: they ignore the mouse wheel unless focused, keep a value from a file that is outside their range (and mark it), and show full precision |
| Field map | each form's `field_widget(path)`, `field_title(code)`, `problem_text(message)` | Where a field is, and what it is called, for Problems and for messages |
| List editor | a list with Add / Edit / Remove at their own width, left-aligned | Spacecraft, stations, sensors, actuators, dispersions |
| Badge / tag | `badges.badge_style(badges.SUCCESS)` and the other pairs | A state in a word: Explain, the dashboard, rule results |
| Toast | `feedback.report(widget, text, kind)` | Something finished or failed, not tied to a field |
| Problem banner | `feedback.ProblemBanner` | Above a form: what is wrong in it |
| Stale results banner | `feedback.StaleResultsBanner` | Above the run views: the results no longer match the scenario, with Re-run |
| Field error | `feedback.show_field_error(widget, message, warning=False)`, `clear_field_error`, `clear_on_edit` | Under the field the problem is about, and the field marked |
| Dialog error | `feedback.show_dialog_error(dialog, text)` | A dialog's own problem, above its buttons |
| Problems | `workspace_panels.ProblemsWidget` | Every problem; double-click jumps to the field |
| Inspector | `workspace_panels.InspectorWidget` | The focused field: label, value, range, help |
| Time cursor | `time_cursor.TimeCursor`, `ResultsWidget.cursor_actions` | One time shared by the plots, the timeline, the dashboard and the output |
| Event table | `event_timeline_widget._EventTable` | Events, sortable; Ctrl+C copies the selection as TSV |

## Patterns

### Messages

A message says what is wrong and what to do, in the user's terms.

**Field names.** In the GUI a message names a field by its form label,
after its section: "my-sat: Station keeping: Reboost thrust [N] must be
> 0".

- **How:** `gui/field_text.py` replaces the codes when the message is
  shown.
- **Unchanged:** the message itself, the command line and the Log keep
  the scenario file's names (`station_keeping.thrust_n`), which is where
  a user fixes them by hand.
- **Orbit messages** start "Orbit (Classical elements): ...".
- **A section is named once** in a message.

**Units.** A label carries its unit in brackets ("Dry mass [kg]"); a
dimensionless value has "[-]".

**One line first.**

- A toast shows the message's first line whole.
- Long paths wrap inside its 360 px (a zero-width space after each `/`
  or `\`, in the displayed text only).
- A multi-line error or warning adds "(more in the Log)", and the Log
  has all of it.

**Confirmations name the object and the consequence** ("Replace the
earlier export?"). They are the only message boxes the app uses.

### Feedback: which one

| Situation | Use | Never |
|---|---|---|
| A field's value is wrong | Field error + the form's banner + a Problems row | A message box |
| A value from a file is outside a field's range | The field shows the nearest value, is marked as a warning, and Problems says which value the scenario keeps | Clamping silently |
| A routine action finished (saved, exported) | Success toast | A message box |
| An action failed (a file cannot be read) | Error toast; full text in the Log | A message box |
| A dialog's input cannot be used | Dialog error above its buttons; the dialog stays open | Closing the dialog |
| A run failed | The run chip says so; the Log opens at the error | |
| Results no longer match the scenario | Stale results banner with Re-run | Silent stale plots |
| Something cannot be undone | A confirmation that names the object and the consequence | Proceeding without asking |

**Toast durations** (`feedback._REPORT_TOAST_MS`):

| Kind | Duration |
|---|---|
| error | 6 s |
| warning | 6 s |
| info | 4.5 s |
| success | 3 s |

**Status bar:** `report` also writes the message there.

### Keyboard

Every command is in a menu, and every menu command with a shortcut shows
it. Help > Keyboard Shortcuts lists them all, submenus included.
Help > Command Palette (Ctrl+K) finds, by name:

- the menus' commands (not those in submenus);
- the Scenario tree's pages;
- the tabs and panels;
- the templates;
- the plotted series.

Commands with a **standard key** take the platform's own key for it
(Qt's `QKeySequence.StandardKey`), so their keys differ between systems.
The table gives them as Qt binds them without a desktop theme (the CI's
offscreen platform). On macOS, Redo is Ctrl+Shift+Z and Quit is Ctrl+Q
(seen in CI). Qt's documentation gives Ctrl+Shift+Z for Redo on GNOME
and KDE too.

| Command | Keys | Standard key |
|---|---|---|
| File > New Scenario | Ctrl+N | New |
| File > Open... | Ctrl+O | Open |
| File > Save | Ctrl+S | Save |
| File > Save As... | Ctrl+Shift+S | SaveAs |
| File > Quit | none | Quit |
| Edit > Undo | Ctrl+Z | Undo |
| Edit > Redo | Ctrl+Y | Redo |
| Run > Run | Ctrl+R | - |
| Run > Cancel Run | Esc | - |
| Run > Clear Time Cursor | Alt+Backspace | - |
| View > Time Cursor > Next Sample | Alt+Right | - |
| View > Time Cursor > Previous Sample | Alt+Left | - |
| View > Time Cursor > Ten Samples On | Alt+Shift+Right | - |
| View > Time Cursor > Ten Samples Back | Alt+Shift+Left | - |
| View > Time Cursor > Next Event | Alt+PgDown | - |
| View > Time Cursor > Previous Event | Alt+PgUp | - |
| View > Time Cursor > Start of the Run | Alt+Home | - |
| View > Time Cursor > End of the Run | Alt+End | - |
| Help > User Manual | F1 | - |
| Help > Command Palette... | Ctrl+K | - |

The table is checked against the menus by `tests/gui/test_design_rules.py`;
a standard key is checked against the running platform's binding.

**Shortcuts inside a view:**

| Where | Keys | Does |
|---|---|---|
| Events | Ctrl+F | Search the events |
| Events | Esc | Clear the search |
| Events table | Ctrl+C | Copy the selected rows as TSV |
| Mission Sequence list | Alt+Up, Alt+Down | Move the step |
| Mission Sequence list | Delete | Remove the step |
| Scenario tree | Up, Down | Pass through a group or a page's sections in the key's direction |

**Tab order.** A Tab walk of Templates, the Scenario page, a spacecraft's
page, Results, Events, Log, End of Life and Budget at 1280 x 720
(iteration 7b) found:

- every visible field, button and list is in the chain, in reading order;
- toolbar buttons are not in it (Qt's default), but each of their
  commands is in a menu.

### Themes

View > Theme offers System, Light and Dark:

- **System** follows the desktop (`QStyleHints.colorScheme`).
- **Storage:** `~/.spacemissionstudio/settings.ini`, key
  `appearance/theme`.
- **When it applies:** the next start, because widgets read the palette
  when they are built.

### Long operations

Every slow job runs in a `QThread` worker, so the window never waits
on it:

- **Simulations:** a progress strip and Cancel (Esc).
- **The AD10 budget's sweeps:** their button turns into Cancel while
  they run.
- **Lifetime estimates and reference-data downloads:** run in workers
  too.

A widget that owns a worker has `wait_for_worker()`:

- `MainWindow` calls it on close;
- tests call it before a widget is destroyed, because destroying a
  running `QThread` aborts the process.

### Empty states

An empty view says why it is empty and what fills it, for example:

- **Results Dashboard:** "No live telemetry yet. Run a scenario with
  Comms pointing (e.g. template 19) to see it here."
- **Output:** why it is empty after a run without Report steps.
- **Log:** "Nothing logged yet in this session."
- **Explain, while the scenario does not validate:** "The scenario has
  a problem (see Problems): fix it to see its summary here."

## Rules for new code

| Rule | Checked by |
|---|---|
| No colour literal in `gui/` outside `theme.py`; take colours from `theme.PALETTE` (the exceptions are listed in the test, each with its reason) | `tests/gui/test_design_rules.py::test_no_hard_coded_colour_outside_the_theme` |
| A new colour token goes into both `LIGHT` and `DARK`, and into the table above | `test_both_themes_have_the_same_keys`, `tests/gui/test_design_rules.py` |
| A colour pair a widget draws is added to the contrast test | `tests/gui/test_dark_theme.py` |
| A new spacecraft number has a labelled widget in the spacecraft form's `field_widget` map | `tests/gui/test_field_text.py::test_every_numeric_spacecraft_field_has_a_title` |
| A validation message starts with what it is about (`<spacecraft>: <field path> ...`, `sim_settings.<field> ...`) so the GUI can locate and label it | `tests/gui/test_field_text.py::test_no_template_message_shows_a_field_code` |
| A form grows no wider than `CONTENT_MAX_WIDTH_PX` | `tests/gui/test_wide_screen.py` |
| Validation is never a message box; a message box only confirms | `tests/gui/test_messages.py::test_no_information_warning_or_critical_message_box_is_left` |
| A menu command with a shortcut is in the table above | `tests/gui/test_design_rules.py::test_the_shortcut_table_matches_the_menus` |
| A widget with a worker thread waits for it before it is destroyed | `tests/gui/test_lifetime_widget.py`, `test_budget_widget.py`, `test_data_panel_widget.py` |
| Help text is short and plain | `tests/gui/test_label_text.py` |
| Every input box has a visible border in both themes | `tests/gui/test_input_borders.py` |

## Checking a change

Each view is checked against the standard's list:

- keyboard only;
- light and dark;
- long names and 10-year runs;
- empty and error states;
- 1280 x 720 and 2560 x 1440;
- the tests;
- no new colour literal.

The screenshots come from an offscreen `QApplication`:

```bash
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py out/light --theme light --size 1280x720
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py out/dark --theme dark --size 2560x1440
```

`scripts/capture_ux_audit.py` captures the template 22 walk-through the
audit uses.

## Known gaps

Where the app does not yet meet `docs/ux-standard.md`:

- **Tables** (audit U-38) are `QTableWidget` in several views, not one
  `QTableView` component.
  - Their alignment and precision vary.
  - Only the Events table copies as TSV.
  - Numbers use Plex Sans without tabular figures.
- **The JSON page** uses the platform's fixed-width font, not IBM Plex
  Mono.
- **No dedicated shortcut sheet key.** The standard asks for `?` or
  Ctrl+/; Help > Keyboard Shortcuts has no shortcut of its own. Ctrl+K
  finds it.
- **Spacing:** there is no single spacing scale. Paddings come from
  Carbon's components (4/6/8/12/16 px and others), not from a 4/8 px
  token set.
- **Icons:** toolbar icons are the stylesheet's SVGs and Qt's, not one
  icon set.
- **Vizard** (audit U-37) still has two toolbar actions and no
  connection status chip.
