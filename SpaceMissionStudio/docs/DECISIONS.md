# Decisions

Choices made where the brief (`docs/ui/UI_OVERHAUL.md`) or the plan
(`docs/ui/UI_OVERHAUL_PLAN.md`) is silent, each with a one-line rationale.
The user's own answers to the plan's questions are in the plan's §9.
Newest milestone first.

## M4b Editing flow (2026-10-22)

Recorded before coding, after reading every editor and measuring the
refresh an edit triggers (`scripts/measure_ui_baseline.py`; a profile
of each part on all 31 templates).

- **Inline, not the inspector, for devices and dispersions.** The
  criterion allows either. The inspector already has one job (the
  focused field: label, value, range; M2), and a form there would give it
  two. The device and dispersion lists get their form under the list on
  the same page, as the mission sequence's step form already is: select
  a row and its form shows; an edit applies once it validates, after the
  same 300 ms settle as a spacecraft's page; a value that does not
  validate is marked at its field and not applied.
- **Add creates the item and opens it:** a spacecraft (from its
  template), a ground station, a device or a dispersion is added with
  its defaults and a name not yet taken, and its page or form opens.
  Nothing modal comes first; Remove and Undo take an unwanted one back.
- **Mission steps need no change:** their form has been inline since
  U-01. The plan's §5 table also suggests the inspector for them; the
  inspector point above applies.
- **Dialogs that make things stay dialogs:** the template picker, the
  Walker, phasing and ROE generators and the 3D model editor create or
  replace several values at once, from inputs that are not the
  scenario's. The brief keeps modal dialogs for multi-step work. The 3D
  model page is §5's, not M4's.
- **The list widgets keep their dialog for a list used on its own:** the
  app has no such use (each list lives in the Scenario editor, which
  edits inline), but their tests build them alone. Removing the path
  would remove those tests.
- **Undo stays `ScenarioHistory`.** Every way of editing (a form, a list,
  the JSON, a generator, Undo itself) ends in one scenario snapshot after
  the edit settles. `QUndoStack` wants a command per kind of edit with
  its own undo, which would re-implement what restoring a snapshot does
  for each of them; wrapping snapshots in commands would add only a
  `QUndoView`, which nothing shows. The criterion keeps
  `ScenarioHistory` when `QUndoStack` does not fit.
- **Form · JSON is a toggle in the Scenario area's header,** replacing
  the JSON node of the tree (§5 table). JSON mode shows the text in
  place of the tree and its page. Back to Form applies the text first,
  through the same parsing as opening a file. Text that does not parse
  or validate keeps JSON mode, with the problem in its banner and a
  Discard button that restores the scenario's text.
- **Explain is the tree's first node, "Overview",** and the Explain dock
  goes. View › Explain opens it. Its title counts what to check, as the
  dock's did. The plan's §5 also has the inspector show the summary when
  nothing is selected; that is not part of M4's criterion and is left
  out.
- **Only the explanation moves off the GUI thread,** because it is the
  cost: `engine.scenario_explainer.explain` takes up to 49 ms per edit
  (26_earth_observation_data_downlink), and rendering it 4–10 ms. Building
  the scenario, the stale-results check, the top bar and the analyses'
  inputs take under 1 ms together and stay immediate, so nothing else
  lags an edit. The explanation is asked for 250 ms after the last edit,
  computed in a `QThread` from the scenario built at that moment, and
  shown only if no later edit is waiting (an older answer is dropped).
- **Not met, recorded:** after this, one keystroke in 310 still left a
  62.9 ms stall in the 600 ms after it (template 12; not reproduced in
  40 more there, and M4a's code shows the same kind of outlier). The
  keystroke itself is at most 29.3 ms (M4a: 136.3 ms). M9's
  performance pass holds the stall.
- **A closed window stops its autosave and its explanation:** a window
  closed but not yet deleted autosaved its discarded scenario into
  whatever home the next test had (a test failed on it), and a waiting
  explanation could start a thread for a window going away.
- **Inline forms follow fields added later:** a device's Kind rebuilds
  its fields, which `watch_edits` had not connected; it now marks the
  fields it follows and connects new ones after each edit.

## M4a Forms (2026-10-22)

The user (2026-10-22): "once CI is green continue as per your
recommendations". M4 is split into M4a and M4b, recorded in the plan
before starting (§7 status; §8 allows a split).

- **M4a first: the forms; then M4b, the editing flow.** M4 is one of the
  two heaviest milestones (§7): every field of the editor changes how it
  shows its unit, and four dialogs become inline editors. Two pull
  requests keep each reviewable, as M2's did.
- **One walker, not 147 edited rows:** `finish_form(root)` runs at the
  end of each editor's constructor. For every form row labelled "Name
  [unit]" whose field holds numbers, it moves the unit into those fields'
  suffix and leaves "Name" as the label. Adding a row needs nothing more,
  and the rule cannot drift between forms. Only units listed in
  `gui/units.py` move; a bracket holding something else stays in its
  label (a JSON key, "lo, hi").
- **Units typeset in the field, ASCII elsewhere:** the field shows "m²",
  "kg·m²", "°", "Wh"; file names, field names, messages and exports keep
  the code's spelling. "days" stays a word rather than "d".
- **Messages keep "Name [unit]":** they name a field through its form
  label (`feedback.row_label`, `gui.field_text`). The walker keeps the
  label's full text on it (`sms_full_label`), so "Dry mass [kg] must be in
  (0, 1e6]" reads as before. The inspector names the field the same way.
- **`NumberField` is the existing full-precision spin box** with the number
  look: `PreciseDoubleSpinBox` already keeps every value exactly (a plain
  `QDoubleSpinBox` once rounded template values). The look is right
  alignment, tabular figures and a width cap of 224 px, so a number sits
  beside its label rather than across a 600 px field.
- **A row too wide for its form wraps its field under its label**
  (`QFormLayout.WrapLongRows`), and rows of buttons or boxes wrap
  (`flow_row`). Without this the Power page, the Spacecraft page (the
  three generator buttons) and template 29's ROE helper row scrolled
  sideways at 1280 px.
- **Boxes in a row of several are 128 px and may shrink to 72 px;** their
  size hint follows the widest value the range allows (a million metres),
  which made a row of four 530 px.
- **Optional groups collapse:** every checkable group shows only its title
  while off, and ticked again shows what it showed (rows another control
  hid stay hidden). Monte Carlo's switch is a check box, not a group; its
  page does the same, with one line on what turning it on does.
- **"No boxes in boxes" needed no change:** M1 made group boxes headings.
  An audit of every page of every template finds no framed panel and no
  scroll area inside a page; the test keeps it so.
- **The Customize wizard follows the same units:** its curated key
  settings' suffixes are typeset. A setting it labels from its field
  name has the unit token split off ("record_interval_s" was "Record
  interval s", now "Record interval" with "s").
- **Forms are walked through their widgets and layouts, never their
  `QLayoutItem`s:** Qt deletes a layout item without telling PySide6, and
  the item's Python wrapper can then be handed out for a new object at
  that address. On CI's Windows job a `QMenu`'s new `QAction` came back
  as a `QWidgetItem` after the walker had visited every row of every
  form. `widgets.form_rows` and `layout_widgets` use
  `getWidgetPosition`, `getLayoutPosition` and `indexOf` instead;
  `feedback.row_label` uses `labelForField`.
- **The third-body perturbers stay in lower case:** the list's text is
  the body's code, which tests read. Showing "Mercury" means a data role
  and ported tests, which is outside M4a's criteria.

## M3 Home and templates (2026-10-22)

The user: "start M3 here". Home is rebuilt: template cards, recent
scenarios, New blank scenario, Customize, and a card instead of the
start-up dialog.

- **Three columns, with the reference-data card across the top while it
  asks:**
  - **Start:** New blank scenario, the recent scenarios and Open;
  - **Templates:** the cards, in as many columns as the width holds;
  - **Details:** the selected template's whole description, with Open
    template and Customize....

  The details keep what the old page showed below its list (the
  description with "What to look at" and "Try changing"). A card has
  room for one sentence only.
- **A card's three lines, all read from the template file** (no metadata
  added, plan §7):
  - **mission type:** the attitude mode (`simulation_mode`: Orbit only or
    Full attitude) with the first spacecraft's pointing mode (its
    `fsw_mode`, named as Explain names it), and the number of
    spacecraft;
  - **orbit:** the central body, then the first spacecraft's orbit;
  - **one line:** the description's first sentence.
- **The orbit line, in detail:**
  - a circular orbit (e < 0.01) shows its altitude ("550 km circular");
  - another shows its periapsis and apoapsis altitudes ("941 × 35095
    km");
  - a small body shows the distance from its centre, as Explain does,
    since it has no single radius;
  - then the inclination to 0.1 deg, and "Sun-synchronous" where Explain
    calls the orbit so.

  The body radii and the Sun-synchronous test are Explain's own
  (`engine.scenario_explainer`), imported, not copied. Explain's own
  orbit line ("SSO 97.59 deg, 550 km alt") gives the altitude from the
  semi-major axis even for template 02 (e = 0.7). The card is new text,
  so it gives the periapsis and apoapsis instead. The engine is
  unchanged.
- **Template 19 names no pointing mode:** it points by its comms link
  (`comms_pointing`), not by an `fsw_mode`, and the card says only what
  the file says.
- **The first sentence ends at ".", "!" or "?" before a space,** not after
  "e.g.", "i.e." or "vs.". Template 29's "Sun-synchronous. follower-1"
  ends a sentence even though a lower-case name follows. The sentence
  wraps to at most four lines on the card and then elides; the whole
  sentence is the tooltip.
- **No thumbnails** (Q4).
- **A filter over the cards:** with 31 cards, typing ("monte carlo") is
  quicker than scrolling. Every word must match the title, the two
  summary lines or the description.
- **The cards are one Tab stop:**
  - the arrow keys, Home and End move between them, and Enter opens one;
  - a card's own Open and Customize... are mouse targets;
  - the details' Open template and Customize... are the next Tab stops.

  31 cards with two buttons each would have been 93 Tab stops.
- **Each card keeps its own Customize...:** users had missed one shared
  button that needed a selection first (the old page's history). The
  details have Customize... for the selected card too.
- **One accent button on the page:** Open template, in the details. New
  blank scenario, Open a scenario file... and the cards' buttons are not
  accented (design rule 1).
- **A selected card** is `bg.selected` with an accent edge; a focused card
  has the 2 px ring. On a selected card its buttons use `text.primary`:
  the link colour on `bg.selected` is under 4.5:1 in the light theme. No
  contrast pair is added.
- **Recent scenarios:**
  - the last 10, newest first;
  - kept with `QSettings` in the app's own `settings.ini`, where the
    theme is kept: one settings file, already isolated per test by
    `tests/conftest.py`. No scenario or project file changes;
  - a file is recorded when it is opened (`open_path`) or saved;
  - the built-in templates are not recorded: they have their cards;
  - a file that is gone is marked "(missing)" with a caution icon (text
    and icon, never colour alone), and opening it says so instead of
    failing;
  - `Delete` takes an entry off the list and **Clear** empties it; the
    files stay where they are.
- **The files are checked when Home is shown,** on the GUI thread: at most
  10 `is_file` calls on local paths. A path on an unreachable network
  share could stall it. A worker for 10 calls is more machinery than
  that risk is worth, so it is not used.
- **The empty state's action is Open a scenario file...**, directly under
  it. There is one Open button on the page, not one in the empty state
  and another above it.
- **The reference-data card replaces the start-up dialog** (§5.2):
  - it asks at every start: the user's standing decision says "the user
    always should be asked", and the plan's "first-run card" names where
    the question is asked, not how often;
  - it offers the same three items with the same defaults, built by one
    function (`choice_boxes`) for the card and the dialog;
  - **Fetch now** runs the same worker in the background, with the
    card's controls disabled and an indeterminate bar (each item reports
    only when it is done), and its summary is a toast;
  - **Not now** hides it and fetches nothing, as Skip did.

  The dialog and `maybe_run_startup_fetch` stay, with their tests. The
  window no longer shows them.
- **A window opened on a file** (the command line, or a recovered
  autosave) shows the Scenario area first. The card waits on Home, so the
  question is still asked but is not in view until Home is opened.
- **Closing the window during a fetch waits for it,** as it waits for the
  End of Life and Budget workers, so a file is not cut off mid-download.
- **Start from scratch stacks its button under its text:** the Start
  column is 220–280 px wide, too narrow for the text and the button side
  by side.
- **A card paints its title and two summary lines itself** (`_CardText`:
  the font, a colour token read at each paint, a height from the font
  metrics), instead of using word-wrapped `QLabel`s:
  - with the labels, Home's first show took 108–193 ms, measured offscreen
    on this machine (`develop`'s list: 19–29 ms), mostly the labels'
    height-for-width in the first layout;
  - with `_CardText` it takes 64–135 ms over four sets of runs. The
    cards' 62 buttons are a good part of the rest: 64–68 ms without them
    in a trial.
  - It is still over the 50 ms of design rule 6. Home is the page the
    window opens on, so this time is part of start-up: the window's first
    show took 184–246 ms against 98–121 ms on `develop`, with the
    labels. It is not a stall after start-up: Home stays built, and
    showing it again lays nothing out anew.
  - M9's criterion (the first visit to any page under 50 ms, start-up
    faster than the baseline) holds this value. Building the cards when
    first scrolled into view, or painting them in one view with a
    delegate, are the options there.
- **The names stay:** `LoadScenarioWidget` (also `HomePage`) and
  `MainWindow.load_scenario_widget`. Tests and scripts reach Home through
  them, and a rename would hide the real changes in noise.
- **Template descriptions** (left over from M2a): "the Events tab" is
  "the Timeline" in templates 22 and 26, "Events:" is "Timeline:" in 29,
  and "Explain, in the side panel" is "in the panel on the right" in 22.
  The template files changed only in those words; they are regenerated
  from `scripts/_template_descriptions.py`.
- **`compare_tab.png` and `monte_carlo_tab.png`** (left over from M2a)
  are now captured by `scripts/capture_screenshots.py`. It runs template
  22 a second time, two days long, as the manual's caption says, and
  template 25's batch into a temporary folder.

## M2a Shell (2026-10-21)

The user: "start M2 here". M2 is split into M2a and M2b, recorded in the
plan before starting (§7 status; §8 allows a split).

- **M2a first: the shell, then M2b the panels.** The shell changes every
  path to every screen; the panels each change one widget. Two pull
  requests keep each one reviewable.
- **Areas host the existing screens unchanged:**
  - Home: the Templates page.
  - Scenario: the scenario editor, without Templates and Analyses in its
    tree.
  - Run: the run options, End of Life, Budget and the Log.
  - Results: Plots, Dashboard, Output, Monte Carlo and Compare.
  - Timeline: the Events view.
  - Reports: Flight Software.
  - Settings: appearance, reference data, layout, keyboard and about.
  - Help: the manual.

  Rebuilding the screens is M3 to M8.
- **End of Life and Budget keep their inputs and results on one page, in
  Run:** Q3 puts the inputs in Run › Analyses and the results in Results.
  Splitting a page means rebuilding it (M6), so M2a moves each page whole
  to the area that holds its inputs.
- **Ctrl+1 to Ctrl+6 open the six areas:** the order of the rail, one key
  each, shown in the rail's tooltips. Settings and Help have the palette
  and F1.
- **The 10 icons added for the rail and top bar come from the same
  `lucide-static` 1.52.0 archive as the 35 bundled in M1,** checked
  against the archive's recorded SHA-256 and npm integrity:
  - chart-gantt, chart-line, circle-help, file-output, house;
  - panel-left-close, panel-left-open, redo-2, settings, undo-2.

- **The window opens on Home:** picking a template or a file is a new
  user's first move, as when the window opened on the Templates node.
- **Home's header has no buttons:** its page already has New blank
  scenario and Browse for a file...; New and Open are also `Ctrl+N`,
  `Ctrl+O` and palette commands.
- **The top bar's search is a button that opens the palette,** not a
  text field of its own: one palette, the one the shortcut opens.
- **The shortcut list shows a command's first key:** a standard key binds
  several on some platforms (Redo: Ctrl+Y, Ctrl+Shift+Z, ...); the first
  is the one to learn, as the old shortcuts dialog showed.
- **Settings > Keyboard is a `QTableWidget`,** as the dialog was; the
  `DataTable` component comes with the tables' rebuild (M6).
- **The saved layout's version is 2:** the toolbars are gone, so a layout
  saved by an earlier version is ignored once; the side panel starts
  where a new window has it.
- **Engine messages keep "Tools > Reference Data":** the engine does not
  change during the overhaul (`CLAUDE.md`). The palette lists that
  command under that name, so the message still leads to it; the
  troubleshooting page says where it now is.

## M2b Panels (2026-10-21)

The user: "start M2b here". M2b is the second half of M2 (above).

- **Problems is a bottom dock with a table:** a `QTableView` over
  `ProblemsModel`, as `CLAUDE.md` sets for tables. Its columns:
  - **Severity**: the word and an icon, colour never alone;
  - **ID**: the field path the message is about (`epoch_utc`,
    `dry_mass_kg`), "-" when it names none;
  - **Object**: Scenario, Propagation setup, the spacecraft's or ground
    station's name, Mission sequence or JSON;
  - **Message**: the text the Problems list showed before.

  The ID and the object come from `problem_location.locate`, which the
  jump to the field already used: nothing new is parsed. Errors come first,
  then the scenario's order; a heading sorts by its column.
- **No filter field or column menu on the Problems table yet:** it has
  four columns and a few rows. The `DataTable` component (M6) brings both
  to every table.
- **The counts:** on the panel's title ("Problems (2)"), always in the
  status bar ("1 error · 1 warning", "No problems") and in the top bar
  only while there are any; both buttons open the panel. Qt names a
  dock's toggle after its title, so the command is named "Problems" again
  after each count.
- **The run job and the chip are in the status bar,** before its other
  items, where §5.1 puts the jobs. The chip is hidden while the job is
  shown, because both said "Running 80 %"; afterwards it says how the run
  ended. One job at a time: Run is disabled while a run or a Monte Carlo
  batch goes, so the "job list" has one entry.
- **The status bar fits 1280 px during a run:**
  - the job's phase elides (80 to 320 px) and its bar is 72 px wide;
  - its button says **Cancel**, its key (Esc) in the tooltip, as
    `CLAUDE.md` puts shortcuts;
  - the Earth orientation and frames entries elide down to 48 px, their
    tooltips holding the whole text;
  - the job asks the status bar to lay it out again when its text grows
    (a `QStatusBar` does not notice on its own: the time was cut to
    "0:02 elap" in the harness's run-in-progress screen).

  Measured at 1280 px with the longest data text ("12 of 14 need
  attention") and "80 % · 0:40 elapsed · about 0:09 left", with the theme
  applied: the status bar's minimum is 1207 px. With the theme applied it
  was 1266 px before Cancel and the bar shrank, which left 14 px.
  The test measures with the theme applied: Qt's default point-size font
  measured twice as wide on the Windows runner (192 dpi, an 800 px screen),
  which says nothing about the app's own fonts.
- **The inspector is two docks, Inspector over Explain,** not one dock
  with tabs. Each one is shown, hidden and sized on its own. Explain leaves
  for Scenario › Overview in M4.
- **`Ctrl+I` and `Ctrl+J` toggle the Inspector and Problems panels,** as
  §5.2 sets; "Side Panel" is gone, its keyword finds the Inspector. A
  panel shown from the keyboard takes the focus, so its table is usable at
  once. Explain has its command and its palette entry, with no shortcut.
- **The validation strip under the editor stays until M4.** §5.2 removes
  it once Problems holds what it says. It is part of the scenario
  editor, which M4 rebuilds, and seven tests read it. Problems already
  lists the same problems.
- **The layout is kept per scenario file:** `layout.ini` keeps one group
  per file. The group is named by a SHA-256 of the file's resolved path,
  and its `path` entry names the file for whoever reads it. Each group
  holds:
  - the dock state (visibility and sizes);
  - whether the rail is collapsed;
  - the six main splitters (scenario tree, mission sequence, plots and
    their side, timeline, compare).

  It is saved when another scenario opens, on Save and on close. A file
  without a layout of its own keeps the layout shown: a new project starts
  from the last one. The window-wide layout is kept as before, for a new
  window.
- **The saved layout's version is 3:** the docks changed (Problems at the
  bottom, Explain its own dock), so a layout saved by M2a is ignored once.
- **The keyboard walk:**
  - Tab goes round the whole window and comes back to where it started
    (47 stops with Home shown).
  - The arrow keys move along the rail's areas, as in any group of
    exclusive buttons, and Space or Enter opens one.
  - The Problems table no longer holds Tab (`setTabKeyNavigation(False)`);
    the walk found that trap.
  - The Tab order follows the order the widgets were made in: rail,
    status bar, panels, top bar, area. A deliberate order is M9's
    accessibility pass.
- **The theme switch is not under 100 ms; the criterion moves to M9.**
  Measured on this branch, offscreen, on template 23:
  - 0.42–0.47 s on a new window (1508 widgets);
  - 0.73–0.84 s once every page has been visited (2529 widgets);
  - M1 measured 0.51–0.55 s and 2.4 s.

  Nearly all of it is Qt's `setStyleSheet`: 141 ms to clear the sheet,
  245 ms to set it. Setting it without clearing first takes 2.8–3.0 s.
  The Python redraw handlers take 1 ms. Under 100 ms needs fewer widgets
  alive: pages built when first shown, which the rebuilds of M4–M8 bring.
  M9's performance pass holds the criterion, with these values.

## A mission from scratch (2026-10-21)

The user: "why can't a user create a new blank project completely from
scratch in the tool? that is like one of the most important features to
have." It could (File > New Scenario), but nothing pointed to it and an
empty scenario showed only a red "needs at least one spacecraft". The
user's decision on the mode: "start with orbit only first, but it should
be clear to the user, that this is not the only option. The user shall
understand the full capabilities of the tool and shall not feel
completely lost."

- **A blank scenario starts in Orbit only,** at start-up and after File >
  New. The schema's default stays `full_attitude`: files without the
  field open as before.
- **"Start from scratch" is the Templates page's first choice:** the
  page where the app opens, and where people look for a way in.
- **The guide is on the Scenario page,** between the epoch and the
  description: a blank scenario's description is empty, and the guide is
  what to read there. It is open for a scenario without spacecraft and
  folded for one opened from a file, which keeps a template's
  description in view.
- **State as text in a status pill** (*Needed* caution, *Done* normal,
  *Optional* off): colour never alone (design rule 1).
- **"There is more" lists areas, not every option,** each with a button
  to where it is set, so the list stays short and each line leads
  somewhere.

## macOS removed (2026-10-21)

The user's decision: "please remove macOS completely and entirely, nobody
needs it." SpaceMissionStudio supports Linux and Windows only.

- **CI and releases:** the macOS row of the `platforms` job and the
  release workflow's macOS job are gone. Basilisk's own workflows lost
  macOS too (the user's decisions of 2026-10-21, after #92's checks
  waited on macOS runners that never came: "remove the macOS jobs from
  the framework workflow too", then "I dont want any macOS workflows
  left whatsoever"). The "Pull Request" workflow has no macOS
  build-and-test jobs; its `docs` job, the merge workflow's docs
  deployment and the canary build run on `ubuntu-24.04`, the docs action
  installing Doxygen and Graphviz with apt instead of Homebrew; the
  nightly, optional and publishing wheel workflows build no macOS
  wheels. That drops the framework's only Python 3.9 (minimum version)
  test run on pull requests; Linux and Windows test 3.14. The framework's
  own documentation, which describes macOS installs and the PyPI wheels,
  is unchanged.
- **The app:** the macOS-only code is gone: Vizard's macOS download and
  its `.app` bundle handling. Code that is plain POSIX (the Unix-domain
  SIL socket, skipping hidden files such as `.DS_Store` in a batch
  folder) stays: Linux uses it, and it changes no result. The exported
  flight-software sources keep "Linux, macOS" for their Unix-domain
  socket: they describe where the exported C code can run, and the export
  stays byte-identical.
- **Tests:** the two tests of the removed `.app` bundle handling now
  check that such a path is started as given, and the download test that
  there is no macOS download (`docs/ui/TEST_CHANGES.md`). No test is
  skipped or removed. No test had a macOS-only branch otherwise; comments
  that explain a test's set-up by what the macOS CI runner did keep that
  history, since the set-up still guards the other platforms.
- **Documents:** current statements of platform support say Linux and
  Windows. Dated records (HISTORY, earlier CHANGELOG entries, the audits
  and the SRelD's past known problems) keep what was true then.

## Self-contained installers (unreleased)

The user's request (2026-10-20), after the 1.1.0 setup program stopped
with "SpaceMissionStudio needs Python 3.11 or later, which was not found
on this system": make the installers self-contained, Linux too. macOS
has no installer, so it keeps the install script.

- **One private Python for both installers** (`packaging/bundle_python.py`):
  python-build-standalone's relocatable CPython, the same source on Linux
  and Windows, pinned by release and SHA-256 (the digests published for
  release 20261013). Python's own Windows "embeddable" package has no pip
  and no Linux counterpart.
- **CPython 3.11** (3.11.17): the version CI tests the app with.
- **Built, not installed, with the network:** Basilisk, the wheel and
  every package are installed into it when the installer is built, with
  `constraints.txt`; the installers only copy files. `SPACEMISSIONSTUDIO_RUNTIME.json`
  records what went in.
- **The support data goes into `site-packages/supportData`,** the folder
  Basilisk's own `dataFetcher.find_local_support_data()` reads before its
  download cache. No environment variable, no launcher wrapper, and no
  change to Basilisk (a data folder next to it, read by its own lookup).
  A file a user later downloads still goes to the user's cache.
- **The Earth orientation files** go into `earth_orientation.SYSTEM_DIR`
  (the install-wide folder), as the old installers fetched them, but at
  build time: they are as current as the build. A user's own newer files
  (`DEFAULT_DIR`) take precedence, as before. Their manifest's absolute
  paths are rewritten for the install folder (at build time for the
  `.deb`, by the setup program on Windows), with no engine change.
- **No downloads while installing:** `postinst` only removes the venv of
  packages up to 1.1.0; the setup program's Python check is gone.
- **The `.deb` is `amd64`,** with every file a package file (launcher and
  icon included), and `Depends` on the desktop libraries Qt loads and
  glibc 2.34 (PySide6 6.11 wheels are `manylinux_2_34`).
- **Bytecode names the installed files:** compiled for
  `/opt/spacemissionstudio/python` when the `.deb` is built, and for the
  chosen folder when the Windows setup runs (that folder is not known when
  it is built); hash-based and unchecked, so file times do not matter.
- **xz for the `.deb`, LZMA2 for the setup program:** the smallest files
  for a 1.6 GB install.
- **`install.sh` and `install.ps1` stay as they are** (a venv with the
  computer's Python): they install from a checkout and cover macOS.

## M1 Foundation (released in 1.1.0)

### Release

- **M1 ships in 1.1.0.** The user chose on 2026-10-20 to publish 1.1.0
  from `develop`, which holds M1, instead of from the commit before it
  (`b064bb9ef`). The version stays 1.1.0; the overhaul's later milestones
  and the version 1.2.0 (plan §9, Q7) follow.

### Carbon removed

- **The IBM Carbon theme (g10 and g100 colours, IBM Plex, square
  corners, filled fields with a bottom rule) is replaced** by the brief's
  token table, Inter and JetBrains Mono, Lucide icons, 6 and 8 px radii
  and 1 px borders. The brief requires it. `gui/theme.py` became the
  package `gui/theme/`. Carbon stays in git history, in HISTORY
  and in the CHANGELOG entry of 1.0.0.
- **The older role names stay readable** (`theme.PALETTE["text_muted"]`
  and the rest), each mapped to one token (`theme/state.py`, `ROLES`):
  40 modules read them, and a rename alongside a restyle would hide real
  changes in noise. New code uses token names.

### Tokens

- **The brief's table is used verbatim** (`tokens.BRIEF`); no suite theme
  package exists yet (plan §9, Q6).
- **Changed to pass WCAG 2.2 AA** (`tokens.ADJUSTED`). OKLab lightness was
  moved in 0.005 steps until the value passed on every background it is
  drawn on (canvas, surface, raised, hover, selected); hue and chroma were
  kept:
  - light `text.muted` `#7C838D` -> `#666D77`: 3.83:1 on `bg.surface`;
  - dark `text.muted` `#7A828E` -> `#868E9A`: 4.12:1 on `bg.hover` and
    3.86:1 on `bg.selected`;
  - light status colours, which the brief gives for a dark background
    (2.5-1.6:1 on white), are split into an icon value (3:1) and a text
    value (4.5:1). Icons: `status.critical` `#FF4D4F` (kept, 3.25:1),
    `status.serious` `#E16F18`, `status.caution` `#BE8400`,
    `status.normal` `#00A45D`, `status.standby` `#3496D5`. Text:
    `status.critical.text` `#DA2331`, `status.serious.text` `#BD4E00`,
    `status.caution.text` `#9E6500`, `status.normal.text` `#00833F`,
    `status.standby.text` `#0077B4`;
  - the dark theme's status colours pass as the brief gives them, as icon
    and as text.
- **Text on the accent** is white in the light theme and the dark canvas
  (`#0B0D10`) in the dark theme: white on `#4C8DFF` is 3.2:1.
- **Derived tokens:** `bg.selected` is the brief's accent at 10 % (light)
  or 16 % (dark) over the surface; status and diff tints are the status
  colour at 7 % (light) or 16 % (dark), the most that keeps the status
  text on its own tint at 4.5:1 (at 10 % light it was 4.36-4.44:1); text
  selection is the accent at 22 % / 34 %; disabled text is
  `text.primary` at 38 % (WCAG exempts inactive controls); the accent's
  hover and pressed steps mix 10 % and 20 % of black (light) or white
  (dark).
- **Borders stay low-contrast** (`border.strong` on the surface is 1.5:1):
  the brief asks for "1 px low-contrast borders"; an input is also told
  apart by its fill, its hover edge and its 2 px focus ring, and
  `tests/gui/test_input_borders.py` keeps every input's edge visible.
- **Tooltips are raised surfaces** (`bg.raised`, a 1 px border), not
  inverse: one floating-element style for menus, popovers and tooltips.
- **No shadows:** Qt style sheets cannot draw them; floating elements get
  a 1 px border instead. A `QGraphicsDropShadowEffect` is left to the
  components that need one (M2).

### Chart palette

- **Eight colours per theme, searched in OKLCH and checked with the
  data-visualisation palette validator** (`theme/palettes.py`). A first
  search that also kept the hue bands of every status colour out found no
  eight-colour set; the rule became "at least Delta E 8 from every status
  colour (icon and text values) and from the accent", which keeps a
  series from reading as a status while leaving enough hues.
  - light on `#FFFFFF`: `#AE59B4 #8A3600 #6C25A4 #236400 #00A596 #5283FE
    #B80040 #005F93`; worst adjacent CVD Delta E 14.3 (protan), worst
    adjacent normal-vision Delta E 20.8, all >= 3:1;
  - dark on `#111418`: `#CA4ED3 #B36C0D #8B63B6 #458604 #00A794 #3163F1
    #DA185B #007CB1`; worst adjacent CVD Delta E 14.8 (deutan),
    normal-vision 15.2, all >= 3:1;
  - with all 28 pairs side by side (scatter of eight groups) two pairs
    fall below the floors in each theme: every chart keeps a legend.
- **The time cursor is drawn in the accent**, not in the error red: it is
  a selection, and red is reserved for critical.

### Type and icons

- **Fonts as TTF, not WOFF2:** Qt reads TrueType everywhere; its WOFF2
  support depends on the build.
- **Weights bundled: Inter 400/500/600, JetBrains Mono 400/500;** no
  italics (none is used).
- **Tabular figures:** `theme.numeric_font()` uses Inter with `tnum` on
  Qt 6.7+, JetBrains Mono on older Qt (`pyproject.toml` allows 6.6).
- **Lucide, only the 35 icons used.** The app's names map to Lucide's
  (`theme/icons.py`): Run `play` in the accent, Cancel `circle-stop` in
  critical, Monte Carlo `dices`, Check kernels `file-check`, Vizard
  settings `sliders-horizontal`, Launch Vizard `monitor-play`, 3D model
  `box`; steps `orbit`, `rocket`, `route`, `variable`, `git-branch`,
  `repeat`, `file-text`, `code`.
- **Icons are tinted when drawn** by a `QIconEngine` that reads the token
  each paint, so a live theme change needs no icon to be set again.

### Style sheet

- **One application style sheet, no per-widget sheets.** A widget picks
  its look with dynamic properties (`role`, `tone`, `badge`, `variant`,
  `series`; `theme.set_role`). The 106 `setStyleSheet` calls outside the
  theme became properties; one is left, the swatch of a colour the user
  picked (`palettes.swatch_style`).
- **No `QWidget { ... }` rule:** text colour, selection and the font come
  from the application palette and font. The rule made Qt restyle every
  widget on a switch for nothing (45 ms of the switch).
- **Group boxes are headings, not frames** ("no boxes inside boxes").
- **Rich text** in labels takes its inline CSS from `theme/richtext.py`
  and is rebuilt on a theme change where it holds colours.
- **Item colours** (list, tree and table rows) are set through
  `theme/items.py`, which records the token on the item so `retint`
  recolours a view after a switch.
- **The hard-coded-style test covers strings and font calls:** colours,
  CSS sizes and weights, font families and style sheets outside
  `gui/theme/`. Integer layout margins in code are out of its scope until
  M2-M8 rebuild the screens from components.

### Live theme switch

- **`apply_theme` clears the sheet, then sets the new one:** measured on
  the main window (1,216 widgets), clearing then setting took 210-290 ms
  where swapping one sheet for the other took about 1,000 ms; Qt builds
  the new rules once instead of diffing every widget against the old.
- **Measured** (same machine, same day, the code before M1 (`b064bb9ef`) and this change run in
  turn; `scripts/measure_ui_baseline.py` and a paired script):
  - a fresh main window with template 19 open (1,360 widgets): 0.51-0.55 s,
    against 1.31-1.44 s before M1;
  - in the baseline script's sequence (every page visited, a run done,
    the spacecraft dialog opened): 2.4 s, against 6.1-6.5 s before M1 (the
    plan's 3.8-4.0 s was measured on a faster day).
- **The brief's 100 ms is not met in M1.** The time is Qt re-polishing
  every widget, and most of them are hidden (1,049 of the 1,216 of a new
  window: pages and tabs not shown). M2 hosts the screens in lazily
  created areas; the criterion is carried to M2 with these values.
- **Tried and not taken:** setting the sheet on the main window instead of
  the application halves the switch (200-250 ms on the fresh window) but
  leaves parentless dialogs and tooltips unstyled; revisited in M2.
- **`theme.on_change` holds callbacks weakly** and skips a widget Qt has
  already deleted: a closed dialog's redraw would otherwise raise on its
  deleted children at the next switch (found by the full test suite).
- **Plots redraw after the switch returns** (a zero-time timer), so the
  switch does not wait for the web pages to reload.
- **System follows the desktop live:** with View > Theme > System, a
  change of the platform's colour scheme applies at once.

### Dependencies and outputs

- **No new run-time dependency.** Inter, JetBrains Mono and Lucide are
  files (`docs/THIRD_PARTY_ASSETS.md`). PySide6 and plotly keep their
  ranges (`>=6.6`, `>=5.0`): nothing new depends on a newer version, and
  pinning them is a release decision, not a restyle one.
- **plotly.js is not copied** into the package: the copy in
  `plotly/package_data/` is already bundled with a GUI dependency, offline
  (a second copy would add 4.8 MB).
- **Data exports are unchanged; plot images take the new look.** A PNG or
  SVG of a plot has always taken the theme in use; its data, axes and
  units are the same.

### Records

- **Test changes** are listed in `docs/ui/TEST_CHANGES.md` (plan §9, Q1).
- **`docs/DESIGN.md` is rewritten** for the new system; the Carbon version
  stays in git history.
- **`CLAUDE.md`** (in `SpaceMissionStudio/`) holds the design rules every
  later session follows.

## Decisions from the plan (§10)

- **plotly.js** comes from the plotly package (above).
- **No new runtime dependencies** (above); the licence report is
  `docs/THIRD_PARTY_ASSETS.md`.
- **Status colours:** the brief's Astro values, tuned only where the
  contrast test fails, each tuned value listed above.
- **Categorical plot palette:** 8 hues, validated for CVD separation on
  both surfaces, distinct from the status hues (above).
- **Recent scenarios** (M3) are stored in `QSettings` (organisation
  "AVSLab"): not a file-format change.
- **Run-start and run-end log records** (M5) are emitted by the GUI's run
  controller, not the engine.
- **`docs/DESIGN.md`** is rewritten in M1 (above).
