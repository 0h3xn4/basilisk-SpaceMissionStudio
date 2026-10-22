# SpaceMissionStudio design system

The reference for how the app looks and behaves: its colour tokens, type,
layout, components, message and feedback patterns, and keyboard model.
It describes what the code does today. Where a rule is checked by a test,
the test is named; where the app falls short of `docs/ux-standard.md`,
the gap is listed under [Known gaps](#known-gaps) rather than glossed
over.

- **Standard:** `docs/ux-standard.md` (the goals).
- **Audit:** `docs/ux-audit.md` (the findings and each iteration's changes).
- **Brief:** `docs/ui/UI_OVERHAUL.md` (the design language this follows)
  and `docs/ui/UI_OVERHAUL_PLAN.md` (its milestones).
- **Single source of truth:** the theme package
  `spacemissionstudio/gui/theme/`. Its tokens generate the application
  style sheet, the `QPalette`, the Plotly template, the chart palette and
  the icon tints. No widget picks a colour, a font or a size of its own.
- **Decisions:** `docs/DECISIONS.md`; licences: `docs/THIRD_PARTY_ASSETS.md`.

This replaces the Carbon-based system of 1.0 and 1.1 (IBM Carbon g10/g100
colours and IBM Plex), which stays in git history.

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

Calm, neutral surfaces with one accent; colour only where it means
something. The tokens are the brief's table, the same in
SpaceMissionStudio, SystemDesignStudio and HarnessDesignStudio
(`theme/tokens.py`, `BRIEF`). Values changed to pass WCAG 2.2 AA are in
`tokens.ADJUSTED` and in `docs/DECISIONS.md`; everything else is derived
from the table (`tokens.tokens(mode)`).

- **Accent:** the primary action, the selection and the focus ring only.
- **Surfaces, not lines:** areas differ by background (canvas, surface,
  raised) and spacing; borders are 1 px and subtle, for inputs, table
  headers, panels and splitters. Group boxes have no frame: their title
  is a heading.
- **Themes:** light and dark, following the system by default, switched
  live (Settings > Appearance).

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg.canvas` | `#F7F7F8` | `#0B0D10` | window background (the brief) |
| `bg.surface` | `#FFFFFF` | `#111418` | lists, tables, cards, plots (the brief) |
| `bg.raised` | `#FFFFFF` | `#171B21` | menus, popups, tooltips (the brief; light: plus a border, Qt draws no shadows) |
| `bg.hover` | `#F0F1F3` | `#1D222A` | hovered rows and controls (the brief) |
| `border.subtle` | `#E4E5E9` | `#222832` | panel and table edges, splitters (the brief) |
| `border.strong` | `#D0D3D9` | `#2E3540` | input borders, check boxes (the brief) |
| `text.primary` | `#16181D` | `#E7E9EC` | body text (the brief) |
| `text.secondary` | `#50565F` | `#A1A8B3` | hints, labels, axis text (the brief) |
| `text.muted` | `#666D77` | `#868E9A` | placeholders, the off status (the brief; adjusted, see DECISIONS) |
| `accent` | `#2563EB` | `#4C8DFF` | the primary action, selection and focus only (the brief) |
| `bg.selected` | `#E9EFFD` | `#1A273D` | selected rows: the accent at 10 % (light) or 16 % (dark) over bg.surface |
| `bg.field` | `#FFFFFF` | `#111418` | inputs: bg.surface |
| `border.focus` | `#2563EB` | `#4C8DFF` | the 2 px focus ring: the accent |
| `text.disabled` | `#A6A7A9` | `#626569` | disabled text: text.primary at 38 % |
| `text.on_accent` | `#FFFFFF` | `#0B0D10` | text on the accent fill (dark: the canvas, white is 3.2:1) |
| `text.link` | `#2563EB` | `#4C8DFF` | links: the accent |
| `accent.hover` | `#2159D4` | `#5E98FF` | primary button hover |
| `accent.pressed` | `#1E4FBC` | `#70A4FF` | primary button pressed |
| `accent.soft` | `#CFDDFB` | `#253D67` | text selection in fields |
| `status.critical` | `#FF4D4F` | `#FF4D4F` | critical: icons and indicators (3:1) |
| `status.critical.text` | `#DA2331` | `#FF4D4F` | critical: words (4.5:1) |
| `status.critical.soft` | `#FFF3F3` | `#371D21` | critical: tinted background |
| `status.serious` | `#E16F18` | `#FF8A3D` | serious: icons and indicators (3:1) |
| `status.serious.text` | `#BD4E00` | `#FF8A3D` | serious: words (4.5:1) |
| `status.serious.soft` | `#FDF5EF` | `#37271E` | serious: tinted background |
| `status.caution` | `#BE8400` | `#F5B83D` | caution: icons and indicators (3:1) |
| `status.caution.text` | `#9E6500` | `#F5B83D` | caution: words (4.5:1) |
| `status.caution.soft` | `#FAF6ED` | `#352E1E` | caution: tinted background |
| `status.normal` | `#00A45D` | `#3DD68C` | normal: icons and indicators (3:1) |
| `status.normal.text` | `#00833F` | `#3DD68C` | normal: words (4.5:1) |
| `status.normal.soft` | `#EDF9F4` | `#18332B` | normal: tinted background |
| `status.standby` | `#3496D5` | `#56B4F5` | standby: icons and indicators (3:1) |
| `status.standby.text` | `#0077B4` | `#56B4F5` | standby: words (4.5:1) |
| `status.standby.soft` | `#F1F8FC` | `#1C2E3B` | standby: tinted background |
| `status.off` | `#666D77` | `#868E9A` | off: icons and indicators (3:1) |
| `status.off.text` | `#666D77` | `#868E9A` | off: words (4.5:1) |
| `status.off.soft` | `#F0F1F3` | `#1D222A` | off: tinted background |
| `diff.added` | `#EDF9F4` | `#18332B` | diff background: normal tint |
| `diff.removed` | `#FFF3F3` | `#371D21` | diff background: critical tint |
| `diff.changed` | `#FAF6ED` | `#352E1E` | diff background: caution tint |
| `shadow` | `#16181D` | `#000000` | floating elements' shadow colour |

The table is checked against the theme package by
`tests/gui/test_design_rules.py::test_the_token_table_matches_the_theme`.

Widgets written before the token table read the role names in
`theme.PALETTE` (`text_muted`, `danger_soft` ...). Each role stands for
one token (`theme/state.py`, `ROLES`); new code uses the token names
(`theme.TOKENS["text.secondary"]`).

**Contrast.** Every pair the GUI draws is listed in
`tokens.CONTRAST_PAIRS` and tested in both themes
(`tests/gui/test_dark_theme.py::test_every_pair_the_app_draws_meets_wcag_aa`):

- text (primary, secondary, muted, links, status words) on every
  background it is drawn on: at least 4.5:1;
- icons, indicators and the focus ring: at least 3:1.

These are WCAG 2.2 criteria 1.4.3 and 1.4.11. Borders between surfaces
are deliberately low-contrast (the brief's 1 px subtle borders); an input
is also told apart by its fill and its hover and focus states.

### Status colours

The Astro UXDS taxonomy: critical, serious, caution, normal, standby, off.
A status colour means one thing everywhere, is the only coloured thing on
a neutral screen, and never stands alone: a status is always written out
as well (a badge's text, a problem's "Error:" or "Warning:", a toast's
words).

| Status | Means | Icon / indicator | Words | Tint |
|---|---|---|---|---|
| critical | error, failed, blocks a run | `status.critical` | `status.critical.text` | `status.critical.soft` |
| serious | a serious condition | `status.serious` | `status.serious.text` | `status.serious.soft` |
| caution | warning, look at this | `status.caution` | `status.caution.text` | `status.caution.soft` |
| normal | success, done, met | `status.normal` | `status.normal.text` | `status.normal.soft` |
| standby | information, in progress | `status.standby` | `status.standby.text` | `status.standby.soft` |
| off | neutral, not known | `status.off` (text.muted) | `status.off.text` | `status.off.soft` |

**Badges** (`gui/badges.py`): `set_badge(label, kind)` with
`MUTED` (off), `SUCCESS` (normal), `DANGER` (critical), `ACCENT`
(standby) or `WARNING` (caution); the style sheet's `[badge=...]` rules
draw them.

**Problem counts in the scenario tree** (`PageTree.set_problem_count`):
caution when every problem is a warning, critical when at least one is an
error; a tooltip counts each kind.

### Data colours

`theme.SERIES_COLORS` is the theme's 8-colour categorical palette
(`theme/palettes.py`), stepped for each theme's surface:

- **Order:** fixed, assigned in order and never cycled.
- **Validated** with the data-visualisation palette validator for adjacent
  pairs (lines, bars): worst colour-vision-deficiency Delta E 14.3 (light)
  and 14.8 (dark), every colour at least 3:1 against its surface.
- **Distinct from status and the accent:** every colour is at least
  Delta E 8 from each status colour and from the accent
  (`tests/gui/test_theme.py::test_the_categorical_palette_is_distinct_and_readable`).
- **A legend always:** with all 28 pairs side by side (a scatter of eight
  groups) two pairs fall below the floors, so colour is never the only cue.

The 3D view's body axes use x red, y green, z blue
(`palettes.AXIS_COLOURS`): an identity convention for geometry, not a
status.

**Plots** take the Plotly template from the tokens
(`theme/plotly_template.py`): Inter, transparent backgrounds over
`bg.surface`, gridlines in `border.subtle`, axis text in
`text.secondary`, hover labels on `bg.raised`. Axis titles carry their
units. The time cursor is drawn in the accent: it is a selection.

### Type

| Use | Font | Size | Weight |
|---|---|---|---|
| Caption | Inter | 11 px | 400 |
| Small text, table cells, field messages, the status bar | Inter | 12 px | 400 |
| Body (the base) | Inter | 13 px | 400 |
| Buttons, tabs | Inter | 13 px | 500 |
| Section title, scenario name | Inter | 15 px | 600 |
| Page title | Inter | 18 px | 600 |
| Display (rare) | Inter | 22 px | 600 |
| Numbers in tables, IDs, code, logs | JetBrains Mono, or Inter with tabular figures | 12 px | 400 |

- **Weights:** 400, 500 and 600 only.
- **Files:** Inter 4.1 and JetBrains Mono 2.304 as TTF, unmodified, under
  the SIL Open Font License 1.1 (`gui/assets/fonts/<family>/`), registered
  with `QFontDatabase` at start-up; the GUI never depends on a system font.
- **Tabular figures:** `theme.numeric_font()` switches on Inter's `tnum`
  where Qt supports font features (6.7 and later), and uses JetBrains
  Mono otherwise.
- **Roles:** a label's size and weight come from its role
  (`theme.set_role(label, role="section-title")`), not from code.
- **Tests:** `tests/gui/test_theme.py::test_the_bundled_fonts_register_and_are_the_application_font`.

### Layout

The app shell (`gui/shell.py`, `gui/app_shell.py`; M2a), with no menu
bar and no toolbar:

- **Navigation rail:** Home, Scenario, Run, Results, Timeline and
  Reports (Ctrl+1 to Ctrl+6), Settings and Help at the bottom; icon and
  label, or icons only (its last button).
- **Area header:** the area's title and its commands as buttons (Run's
  run controls, Scenario's 3D Model...).
- **Top bar:**
  - the scenario name, its state (unsaved, from a template or a file)
    and the last run, with the breadcrumbs (area › page) under them;
  - Undo, Redo, Save (it shows the save state), Run (the one primary,
    accent, button) with its mode, the command search (Ctrl+K) and,
    while there are any, the problem count.
- **Home (M3, `gui/load_scenario_widget.py`):** while it asks, the
  reference-data card across the top (it replaced the start-up dialog);
  then three columns: Start (New blank scenario, the recent scenarios
  with their empty state, Open), the template cards in as many columns
  as fit (at least 264 px each) with a filter, and the selected card's
  whole description with Open template (the page's one accent button)
  and Customize. A card is a `card` surface: hover `bg.hover`, selected
  `bg.selected` with an accent edge, focus the 2 px ring; its three
  lines (attitude mode, orbit, the description's first sentence) are
  read from the template file. The cards are one Tab stop; the arrow
  keys, Home and End move between them, Enter opens.
- **Scenario area:** the scenario tree on the left. Each spacecraft has a
  node per part of its editor.
- **Forms (M4a, `gui/widgets.py`, `gui/units.py`):** a number field
  (`NumberField`, or any spin box `finish_form` styles) carries its unit as
  a suffix, typeset ("550.0 km", "97.59°", "1.000 m²", "300.00 Wh"),
  right-aligned in tabular figures, at most 224 px wide (128 px each in a
  row of several, shrinking to 72 px on a narrow page). The label is the
  name alone; messages still name the field "Name [unit]", the label's
  full text kept on it. A row too wide for its form puts its field under
  its label. An optional (checkable) group shows only its title while
  off. Rows of buttons or boxes wrap (`flow_row`) instead of widening the
  page. No framed panel and no scroll area inside a page.
- **Inspector, on the right:** one dock, the focused field (Ctrl+I). No
  tabs. Explain is the Scenario tree's first node, Overview (M4b): asked
  for 250 ms after an edit and computed in a `QThread`, an overtaken
  answer dropped.
- **Form · JSON:** a segmented control in the Scenario area's header;
  JSON mode shows the text in place of the tree. Back to Form applies a
  waiting edit and is refused while the text does not apply (Discard).
- **Lists edit inline:** a device's or dispersion's form is under its list
  (`gui.inline_form.InlineForm`), applied 300 ms after the last edit once
  it validates, the reason above the form when it does not. Add creates
  the item and opens it; no modal dialog.
- **Problems panel, at the bottom (Ctrl+J):** a `QTableView` over
  `ProblemsModel`: Severity (icon and word), ID (the field path), Object,
  Message; errors first, any column sorts, Ctrl+C copies TSV, Enter or a
  double-click goes to the field. Its counts are on its title, in the
  status bar and the top bar.
- **Status bar:** the run job (phase, progress, time so far and left,
  Cancel) while a run goes, the run state chip otherwise; then the problem count
  (it opens Problems), Basilisk version, reference data, Earth
  orientation data, frames.
- **Layout memory:** Settings > Layout > Reset Layout restores the panels
  and the rail. The layout (docks, rail, the main splitters) is kept per
  scenario file, and for the window between sessions (`layout.ini`).
- **Commands:** every command is in one registry (`gui/actions.py`):
  the command palette, the area headers, the top bar, the shortcut list
  and every tooltip ("Save (Ctrl+S)", then what it does) come from it.

| Measure | Value | Where |
|---|---|---|
| Grid | 4 px: 4, 8, 12, 16, 24, 32 | `theme.SPACE` |
| Control height | 32 px (28 px compact: header and top-bar buttons) | `theme.CONTROL_HEIGHT` |
| Table rows | 26 px | `theme.ROW_HEIGHT` |
| Corner radius | 6 px controls, 8 px panels, popovers and dialogs | `theme.RADIUS` |
| Focus ring | 2 px, the accent | `theme/qss.py` |
| Smallest window the views are checked at | 1280 x 720 px | `scripts/capture_screenshots.py --size` |
| Widest a form or a list editor grows | 960 px (`theme.CONTENT_MAX_WIDTH_PX`) | `scenario_editor._page`, the embedded forms, End of Life |
| Number field | at most 224 px; 128 px each in a row of several, 72 px at least | `widgets.NUMBER_FIELD_MAX_WIDTH_PX`, `VECTOR_FIELD_MAX_WIDTH_PX`, `VECTOR_FIELD_MIN_WIDTH_PX` |
| Scenario tree | at least 170 px, 220 px to start | `gui/page_tree.py` |
| Results plot list | 16 % of the pane, 250 to 400 px, until the user drags the divider | `gui/results_widget.py` |
| Toast | at most 360 px wide, 16 px from the window's edge, 8 px apart | `gui/feedback.py` |

**What keeps the full width:** plots, tables, the event timeline, the
JSON view, Compare and the model editor. A form keeps the left edge, and
the Scenario form sits at the top of its page.

**Fields:** a 1 px `border.strong` edge on `bg.field`, 6 px corners; hover
darkens the edge, focus draws the 2 px accent ring; an error or warning
draws a 2 px status ring (`tests/gui/test_input_borders.py`).

**Shadows:** Qt style sheets cannot draw them; floating elements (menus,
popovers, tooltips) are `bg.raised` with a 1 px border instead.

### Icons

- **One set:** Lucide (ISC licence), only the icons the GUI uses, in
  `gui/assets/icons/lucide/` with its licence.
- **Tinted from the tokens when drawn:** `theme.icon(name, ink)` returns
  a `QIcon` whose engine looks the colour up each time it paints, so an
  icon follows a live theme change; a disabled icon takes
  `text.disabled`. The style sheet's arrows and ticks are tinted copies
  (`theme/icons.py`, `icon_file`).
- **Sizes:** 16 px in the interface, 20 px in the navigation rail.
- **Command buttons:** every button of the top bar and the area headers
  has an icon, the run-mode drop-downs aside
  (`tests/gui/test_theme.py::test_every_command_button_has_an_icon`): Run
  in the accent, Cancel in critical, the rest in `text.secondary`.
- **App icon:** drawn in code (`gui/icons.py`) in `palettes.APP_ICON`.

## Components

| Component | Code | Use it for |
|---|---|---|
| Page tree | `page_tree.PageTree`: `add_page`, `add_section`, `set_problem_count`, `show_page`, `show_section` | A view with several forms: one node per form, sections per part, problem counts on nodes |
| Embedded form | `page_tree.embed_dialog`, then `setMaximumWidth(CONTENT_MAX_WIDTH_PX)` | A dialog's form shown as a page: no window, no OK/Cancel, long rows wrap |
| Form fields | `widgets.SpinBox`, `DoubleSpinBox`, `PreciseDoubleSpinBox`, `ComboBox` | Numbers and choices: they ignore the mouse wheel unless focused, keep a value from a file that is outside their range (and mark it), and show full precision |
| Field map | each form's `field_widget(path)`, `field_title(code)`, `problem_text(message)` | Where a field is, and what it is called, for Problems and for messages |
| List editor | a list with Add / Edit / Remove at their own width, left-aligned | Spacecraft, stations, sensors, actuators, dispersions |
| Badge / tag | `badges.set_badge(label, badges.SUCCESS)` and the other kinds | A state in a word: Explain, the dashboard, rule results |
| Role | `theme.set_role(widget, role=..., tone=..., badge=...)` | A label's or frame's look from the style sheet: caption, heading, section-title, mono, empty, hint, card; a status tone |
| Toast | `feedback.report(widget, text, kind)` | Something finished or failed, not tied to a field |
| Problem banner | `feedback.ProblemBanner` | Above a form: what is wrong in it |
| Stale results banner | `feedback.StaleResultsBanner` | Above the run views: the results no longer match the scenario, with Re-run |
| Field error | `feedback.show_field_error(widget, message, warning=False)`, `clear_field_error`, `clear_on_edit` | Under the field the problem is about, and the field marked |
| Dialog error | `feedback.show_dialog_error(dialog, text)` | A dialog's own problem, above its buttons |
| Problems | `workspace_panels.ProblemsWidget` (`ProblemsModel`, `ProblemsTable`) | Every problem with severity, ID, object and message; Enter or double-click jumps to the field |
| Inspector | `workspace_panels.InspectorWidget` | The focused field: label, value, range, help |
| Time cursor | `time_cursor.TimeCursor`, `ResultsWidget.cursor_actions` | One time shared by the plots, the timeline, the dashboard and the output |
| Command | `actions.ActionRegistry.add(id, text, handler, category=, area=, shortcut=, tip=)` | Every command of the window: its palette entry, header and top-bar buttons, tooltip ("Save (Ctrl+S)") and shortcut row come from it |
| Area | `shell.Shell.register(id, icon, label, content, order)`, `AreaPage.add_command(action)` | A top-level area of the navigation rail, hosting a screen, with its commands in its header |
| Elided label | `app_shell.ElidedLabel` | One line that ends in "..." rather than widening the window; the whole text is its tooltip |
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

Every command is in the action registry, and every command with a
shortcut shows it in its tooltip. Keyboard Shortcuts (Ctrl+/, Settings >
Keyboard) lists them all. The command palette (Ctrl+K, the top bar's
search) finds, by name or an older name ("events" finds the Timeline):

- the registry's commands;
- the areas and the pages of Run and Results;
- the Scenario tree's pages, its spacecraft and ground stations;
- the panels (Inspector, Problems) and the Settings sections;
- the templates;
- the plotted series.

Commands with a **standard key** take the platform's own key for it
(Qt's `QKeySequence.StandardKey`), so their keys differ between systems.
The table gives them as Qt binds them without a desktop theme (the CI's
offscreen platform). Qt's documentation gives Ctrl+Shift+Z for Redo on
GNOME and KDE.

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
| View > Inspector | Ctrl+I | - |
| View > Problems | Ctrl+J | - |
| Time Cursor > Next Sample | Alt+Right | - |
| Time Cursor > Previous Sample | Alt+Left | - |
| Time Cursor > Ten Samples On | Alt+Shift+Right | - |
| Time Cursor > Ten Samples Back | Alt+Shift+Left | - |
| Time Cursor > Next Event | Alt+PgDown | - |
| Time Cursor > Previous Event | Alt+PgUp | - |
| Time Cursor > Start of the Run | Alt+Home | - |
| Time Cursor > End of the Run | Alt+End | - |
| Help > User Manual | F1 | - |
| Help > Keyboard Shortcuts | Ctrl+/ | - |
| Help > Command Palette... | Ctrl+K | - |
| Go > Go to Home | Ctrl+1 | - |
| Go > Go to Scenario | Ctrl+2 | - |
| Go > Go to Run | Ctrl+3 | - |
| Go > Go to Results | Ctrl+4 | - |
| Go > Go to Timeline | Ctrl+5 | - |
| Go > Go to Reports | Ctrl+6 | - |

The Time Cursor commands work while Results has the focus. The table is
checked against the registry by `tests/gui/test_design_rules.py`; a
standard key is checked against the running platform's binding.

**Shortcuts inside a view:**

| Where | Keys | Does |
|---|---|---|
| Events | Ctrl+F | Search the events |
| Events | Esc | Clear the search |
| Events table | Ctrl+C | Copy the selected rows as TSV |
| Mission Sequence list | Alt+Up, Alt+Down | Move the step |
| Mission Sequence list | Delete | Remove the step |
| Scenario tree | Up, Down | Pass through a group or a page's sections in the key's direction |
| Home, template cards | Arrows, Home, End | Move between the cards |
| Home, template cards | Enter | Open the card's template |
| Home, recent scenarios | Delete | Take the scenario off the list |

**Tab order.** A Tab walk of Templates, the Scenario page, a spacecraft's
page, Results, Events, Log, End of Life and Budget at 1280 x 720
(iteration 7b) found:

- every visible field, button and list is in the chain, in reading order;
- since M2a the toolbars are gone; the rail, the area headers and the top
  bar are buttons in the chain, and every command has a shortcut or a
  palette entry. The keyboard-only walk of the shell is M2b's.

### Themes

Settings > Appearance offers System, Light and Dark:

- **System** follows the desktop (`QStyleHints.colorScheme`).
- **Storage:** `~/.spacemissionstudio/settings.ini`, key
  `appearance/theme`.
- **When it applies:** at once. `theme.apply_theme(app, mode)` sets the
  palette and the one application style sheet and emits
  `theme.signals.changed`; plots, diagrams and item colours connect to it
  and redraw (`theme.on_change`, `theme/items.py`). With System, a change
  of the desktop's scheme applies while the app runs.
- **Time:** about 0.5 s on a new main window with a scenario open, 2.4 s
  after every page has been visited (before M1: 1.3 s and 6.1-6.5 s on the
  same machine); Qt re-polishes every widget, most of them hidden. The
  brief's 100 ms needs fewer live widgets, which the shell's lazy areas
  (M2) bring (`docs/DECISIONS.md`).

### Long operations

Every slow job runs in a `QThread` worker, so the window never waits
on it:

- **Simulations:** a job in the status bar with progress and Cancel (Esc, in its tooltip).
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
| No colour, CSS size, font family or style sheet in `gui/` outside `gui/theme/`; take tokens, fonts and roles from the theme (the exceptions are listed in the test, each with its reason) | `tests/gui/test_design_rules.py::test_no_hard_coded_style_outside_the_theme` |
| A new token is derived in `theme/tokens.py` for both themes, and is in the table above | `tests/gui/test_theme.py::test_both_themes_have_the_same_tokens_and_the_selected_tint`, `tests/gui/test_design_rules.py` |
| A colour pair a widget draws is in `tokens.CONTRAST_PAIRS` | `tests/gui/test_dark_theme.py` |
| Whatever paints a colour itself redraws on `theme.signals.changed` | `tests/gui/test_dark_theme.py::test_a_live_switch_restyles_every_open_view` |
| The style sheet parses without a Qt warning | `tests/gui/test_theme.py::test_the_style_sheet_parses_without_qt_warnings` |
| A new spacecraft number has a labelled widget in the spacecraft form's `field_widget` map | `tests/gui/test_field_text.py::test_every_numeric_spacecraft_field_has_a_title` |
| A validation message starts with what it is about (`<spacecraft>: <field path> ...`, `sim_settings.<field> ...`) so the GUI can locate and label it | `tests/gui/test_field_text.py::test_no_template_message_shows_a_field_code` |
| A form grows no wider than `CONTENT_MAX_WIDTH_PX` | `tests/gui/test_wide_screen.py` |
| Validation is never a message box; a message box only confirms | `tests/gui/test_messages.py::test_no_information_warning_or_critical_message_box_is_left` |
| A command with a shortcut is in the table above | `tests/gui/test_design_rules.py::test_the_shortcut_table_matches_the_registry` |
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
- no new colour, size or font literal.

The screenshots come from an offscreen `QApplication`:

```bash
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py out/light --theme light --size 1280x720
QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py out/dark --theme dark --size 2560x1440
```

`scripts/capture_ux_audit.py` captures the template 22 walk-through the
audit uses.

## Known gaps

Where the app does not yet meet `docs/ui/UI_OVERHAUL.md` (each is a later
milestone of `docs/ui/UI_OVERHAUL_PLAN.md`):

- **Live theme switch time:** 0.5-2.4 s, not the brief's 100 ms (M2:
  lazy areas).
- **Tables** (audit U-38) are `QTableWidget` in several views, not one
  `QTableView` component (M6): alignment and precision vary, only the
  Events table copies as TSV, and only cells built with
  `theme.numeric_font()` use tabular figures.
- **Spacing:** the 4 px grid is in the style sheet; layouts built in code
  still set their own margins (M2-M8 rebuild the screens from
  components).
- **Motion and UI scale** (the brief's 120-180 ms transitions, reduce
  motion, 90-125 % scale) come with Settings (M8).
- **Vizard** (audit U-37) still has two commands in the Run area's
  header and no connection status chip.
