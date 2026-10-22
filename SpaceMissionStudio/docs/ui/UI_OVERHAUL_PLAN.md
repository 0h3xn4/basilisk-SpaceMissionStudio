# UI overhaul plan: SpaceMissionStudio

Phase 1 of [`UI_OVERHAUL.md`](UI_OVERHAUL.md): the audit and the plan. No GUI
code has changed. Implementation starts after you approve this plan, one
milestone per session.

**Contents**

1. [What was read and measured](#1-what-was-read-and-measured)
2. [Inventory](#2-inventory)
3. [Performance baseline](#3-performance-baseline)
4. [Findings per screen](#4-findings-per-screen)
5. [Information architecture](#5-information-architecture)
6. [Theme package and components](#6-theme-package-and-components)
7. [Milestones and acceptance criteria](#7-milestones-and-acceptance-criteria)
8. [Risks](#8-risks)
9. [Questions for you](#9-questions-for-you)
10. [Decisions taken without asking](#10-decisions-taken-without-asking)

Screenshot references such as **[L012]** mean
`screenshots/before/light/012_*.png`. The dark set in
`screenshots/before/dark/` uses the same numbers, so **[D012]** is the same
screen in the dark theme. [`screenshots/before/light/INDEX.txt`](screenshots/before/light/INDEX.txt)
lists every file.

---

## 1. What was read and measured

- **Documents.**
  - Read: `CONTRIBUTING.md`, `docs/developer/README.md`,
    `docs/reference/capabilities.md` and `docs/reference/limitations.md`.
  - Also read the earlier design records that this overhaul replaces:
    `docs/DESIGN.md` (the Carbon design system), `docs/ux-standard.md`,
    `docs/ux-audit.md`, `docs/ux_audit.md`, `docs/ux_guidelines_gap.md` and
    `docs/ux_roadmap.md`.
  - Not present in the repository: `CLAUDE.md`, `docs/DECISIONS.md` and
    `docs/developer/operations-roadmap.md`. M1 creates the first two. The third
    is a question for you: see [Q6](#9-questions-for-you).
- **Code.** The whole GUI package was read: `spacemissionstudio/gui/`, 69
  files and 29,129 lines. The largest files are:

  | File | Lines |
  |---|---:|
  | `spacecraft_editor.py` | 3108 |
  | `main_window.py` | 2300 |
  | `template_wizard.py` | 2189 |
  | `results_widget.py` | 1879 |
  | `mission_sequence_editor.py` | 1230 |
  | `scenario_editor.py` | 985 |
  | `theme.py` | 970 |

- **Screenshot harness.** [`scripts/capture_ui_screens.py`](../../scripts/capture_ui_screens.py)
  runs offscreen, in one theme per process.
  - **Example project:** template 23, the complete small satellite.
  - **Screens:** every scenario-tree node before and after a run; every
    main, Results and side tab; every menu.
  - **States:** run in progress, stale results, an invalid field and its
    Problems row, a second run with Compare, End of Life computed (template
    22), and a Monte Carlo batch (template 09).
  - **Other views:** the JSON view, and windows at 1280×720 and 2560×1440.
  - **Dialogs:** every dialog class (21) plus the message boxes, each grabbed
    while open. Modal ones are grabbed and then closed.
  - The run history goes to a temporary folder, not `~/.spacemissionstudio`.
  - It wrote 115 PNGs per theme to `docs/ui/screenshots/before/`.
- **Performance probe.** [`scripts/measure_ui_baseline.py`](../../scripts/measure_ui_baseline.py)
  uses a 2 ms heartbeat timer on the GUI thread. Any gap between ticks is a
  stall: time in which the window can neither repaint nor take input.
  - Startup is measured in three fresh processes.
  - Each interaction reports its synchronous call time and the longest stall
    in the 1–3 s after it.
  - Raw numbers are in [`perf_baseline.json`](perf_baseline.json).

## 2. Inventory

### 2.1 Screens

| Where | Screens today |
|---|---|
| Window chrome | Menu bar (File, Edit, Run, Analyses, Tools, View, Help), two toolbar rows, scenario title bar with save and run state, run progress strip, stale-results banner, status bar (message, Basilisk version, reference data, Earth orientation, frames) |
| Main tabs | Scenario, Results, Events, Compare, Log |
| Scenario tab (tree + page) | Templates; Scenario; Environment; Spacecraft › *sc* › Orbit/mass, Sensors/actuators, Attitude control, Power/propulsion/link budget, 3D model, Vizard model, Budget (AD10); Ground stations › *gs*; Mission sequence; Monte Carlo; JSON; Analyses › End of Life, Budget, Flight Software |
| Results tab | Plots, Dashboard, Output, Monte Carlo (only after a batch) |
| Side dock | Inspector, Explain, Problems |
| Under the editor | Validation strip ("valid", warnings) |

### 2.2 Dialogs and windows

All 21 `QDialog` subclasses, plus the message boxes:

| Dialog | Opened from | Kind |
|---|---|---|
| `SpacecraftEditorDialog` | Add spacecraft, also embedded in the tree | Editor (large, tabbed) |
| `_ItemEditorDialog` | Sensors/actuators › Add/Edit | Editor |
| `GroundStationEditorDialog` | Ground stations › Add/Edit | Editor |
| `_CommandEditorDialog` | Mission sequence | Editor |
| `_DispersionEditorDialog` | Monte Carlo › Add/Edit | Editor |
| `PropagationSetupDialog` | Embedded as the Environment page | Editor |
| `ModelEditorDialog` (+ `_ImportOptionsDialog`) | 3D model, Tools › 3D Model | Editor with a WebGL view |
| `BoxFacetDialog` | Facet model › Box + array | Generator |
| `SpacecraftTemplateDialog` | Add from preset | Picker |
| `WalkerConstellationDialog`, `PhasingFormationDialog`, `RoeFormationDialog` | Spacecraft list generators | Generators |
| `TemplateCustomizeWizard` | Templates › Customize… | Wizard |
| `OrbitSwitchDialog` | Changing the orbit type | Confirmation with a choice |
| `SilRunDialog` | Flight Software › SIL | Run options |
| `VizardDialog` | Run › Vizard Configuration… | Settings |
| `StartupFetchDialog` | First start | Consent |
| Reference data dialog (`DataPanelWidget`) | Tools › Reference Data…, status bar | Settings, downloads |
| `CommandPalette` | Ctrl+K | Popup |
| `ShortcutsDialog`, `ManualDialog` | Help | Help |
| About, discard confirmation, autosave recovery, Vizard location | Message boxes | Message |

### 2.3 Styles

- **Theme.** `theme.py` (970 lines) holds two palettes: Carbon g10 (light)
  and g100 (dark).
  - Its QSS is built from f-strings over `PALETTE`.
  - The SVG glyphs in `assets/` are re-tinted per theme.
  - IBM Plex Sans and Mono are bundled as `.woff`.
  - A theme change applies only at the next start ("applies at next start"
    in View › Theme).
- **Per-widget style sheets:** 107 `setStyleSheet` calls in 26 files (106
  outside `theme.py`).
  - The largest users are `mission_dashboard_widget` (22),
    `scenario_explainer_widget` (10), `template_wizard` (8),
    `spacecraft_editor` (7) and `fsw_workbench_widget` (7).
  - Every one of them fixes colour, size or weight outside the theme.
- **Hex colours outside `theme.py`:** 9.
  - `icons.py` (4): the procedurally drawn application icon.
  - `model_view_widget.py` (3) and `model_editor_dialog.py` (2): 3D-view
    colours.
- **Pixel and point sizes outside `theme.py`:** 61 lines in 24 files. The worst are
  `sensor_actuator_editor` (8), `results_widget` (8), `icons` (7),
  `template_wizard` (5) and `scenario_explainer_widget` (5).
- **Fonts set in code.**
  - `results_widget` injects an `@font-face` for Plex into the plot pages.
  - `mission_sequence_editor` uses `setFamily("monospace")`, a system font.
  - The diagram widgets (`formation_diagram_widget`, `roe_diagram_widget`)
    scale point sizes in code.
- **Icons.** There are 23 hand-drawn SVGs in `assets/`: toolbar, mission
  sequence steps, and combo/spin/check glyphs. There is no icon set, and many
  actions have no icon.
- **Plots.**
  - Plotly figures are styled in `results_widget` and `compare_widget` from
    `PALETTE` and a Carbon-derived categorical order.
  - There is no Plotly template object.

### 2.4 Tables

There is no model/view anywhere: no `QTableView` and no
`QAbstractTableModel`. The tables are 14 `QTableWidget` construction sites in 13 files, 2
`QTreeWidget`s (the scenario page tree and the plot catalog) and 13
`QListWidget`s.

| Table | Typical rows | Could be large |
|---|---:|---|
| `mission_output_widget` (Output) | series × reports, ~30–300 | **yes**: one row per series per report command |
| `event_timeline_widget._EventTable` (Events) | passes + eclipses + burns + modes; tens for a day, **thousands for a 1-year run** | **yes** |
| `monte_carlo_results_widget` | runs × quantities, up to 1000 runs | **yes** |
| `compare_widget` (inputs and summary diff) | ~10–200 | medium |
| `data_panel_widget` (reference data) | 15 | no |
| `budget_widget` (budget, launch delays, altitude trade) | ~10–40 | no |
| `readout_panel` (plot readout) | shown plots × columns | no, but it refreshes on every cursor move |
| `data_handling_editor._TableEditor` (instruments, ROE targets) | ~1–20 | no |
| `facet_editor` | 6–30 | no |
| `help_dialog` (shortcuts) | ~40 | no |
| `results_widget` (series info dialog) | ~5 | no |
| `scenario_explainer_widget` | ~5–20 | no, but it is rebuilt on every edit |
| `sil_comparison_widget` | ~10–50 | no |

### 2.5 Work on the GUI thread

This list comes from reading the code. The probe in §3 measures it.

- **On every keystroke in any field** (measured in §3 at 10–54 ms):
  `MainWindow._refresh_scenario_explainer`.
  It runs synchronously through the `ScenarioEditorWidget.changed` signal,
  with no debounce, and does all of this:
  - builds the whole `Scenario` (`to_scenario()`, which validates);
  - re-runs the explainer (`engine.scenario_explainer`, with pass prediction);
  - hashes the scenario for the stale banner;
  - refreshes the top bar;
  - pushes the scenario into the End of Life, Budget, Flight Software and
    Monte Carlo widgets.

  Autosave and undo snapshots are already debounced.
- **When a run ends:**
  - `RunHistory.add` → `run_store.save` writes the whole result to disk;
  - `run_store.prune`;
  - the results widget builds its catalog and every shown Plotly figure, then
    serialises it to HTML and writes it to a temporary file;
  - the event timeline extracts events and fills its `QTableWidget`;
  - Output, Dashboard and Compare are refreshed.
- **When Compare or the run history is opened:**
  `run_store.load_index` / `load_result` read saved runs from disk.
- **When a template or file is opened:**
  - parsing, migrating and validating the JSON;
  - building the editor pages. Each spacecraft and station form is a full
    `SpacecraftEditorDialog` or `GroundStationEditorDialog`, built when its
    node is first shown (§3: 383 ms for a spacecraft);
  - the explainer refresh above.
- **When a plot is shown or the layout changes:** a full HTML page and
  `setHtml`/`load`, which reloads `plotly.min.js` (4.8 MB) for every
  page.
- **Startup:** every tab, and the two `QWebEngineView`s of the main window
  (Plots, Compare), are created eagerly in `MainWindow.__init__`. The third
  web view, the 3D model, is created only when the model editor opens. No
  `QWebEngineProfile` is set, so all of them share the default profile.
- **Already in workers, and kept there:** simulations (`run_worker`, a
  `QThread`), Monte Carlo batches, End of Life, budget sweeps, reference-data
  downloads, Vizard download and SIL runs.

## 3. Performance baseline

Measured with [`scripts/measure_ui_baseline.py`](../../scripts/measure_ui_baseline.py).
Conditions:

- Linux container, 4 CPUs, offscreen, WebEngine in software rendering, a
  1440×900 window and the light theme.
- The raw results, with three startup runs, are in
  [`perf_baseline.json`](perf_baseline.json).
- The figures are this machine's. They are the before-values that M9 must
  beat, re-measured on the same kind of machine.
- WebEngine paints in its own process, so plot rendering time is not counted.
  Only the GUI thread's time is.

**Startup to the first interactive window: 1.69–1.97 s.**

| Stage | ms |
|---|---:|
| Interpreter to script | 31–38 |
| Import PySide6 | 61–74 |
| Import the GUI package | 295–309 |
| `QApplication` + theme | 11–13 |
| **`MainWindow` constructor** | **1250–1504** |
| `show()` + first event-loop turn | 38–42 |

The constructor is about 75 % of startup: every tab, the scenario editor
and both main-window web views are built before the window shows.

**Interactions longer than the 50 ms budget** (the longest stall seen by the
heartbeat):

| Interaction | Longest stall [ms] |
|---|---:|
| Switching the theme on the open window (`apply_theme`), which the brief requires to be live | **3775–4019** |
| First visit to a spacecraft page (the page is built then) | 383 |
| Opening a template: template 09 first time; template 23; all 31 in a row | 376; 129–154; 65–216 |
| Opening the spacecraft editor dialog | 318 |
| The end of a run (results, events, run store), template 23 | 256 (2 stalls over budget during a 5 s run) |
| Showing a plot (Results › Plots) | 31–155 (1 of 4 over budget) |
| One keystroke in a field, worst templates (21, 26) | 53–54 (max); median 32–35 |

**Within budget:**

| Interaction | Range |
|---|---|
| Switching main, Results and side tabs, before and after a run | 3–15 ms |
| Switching scenario pages other than the first visit to a spacecraft | 3–33 ms |
| Searching the plot catalog | 10 ms |
| One keystroke in most templates | median 10–39 ms, max ≤ 49 ms |

**What this means for the plan.**

- **Keystrokes.** The per-keystroke refresh is close to the limit rather
  than far over it, and it grows with the number of spacecraft and with the
  analyses enabled. A 250 ms debounce, plus building the explainer in a
  worker (M4), gives headroom for larger scenarios.
- **Biggest single problem.** It is the live theme switch at about 4 s,
  because the whole application stylesheet is re-applied to every widget.
  M1 generates one stylesheet and applies it once at the application level,
  with no per-widget `setStyleSheet` (§2.3). Its acceptance criterion is a
  switch in under 100 ms. If restyling every widget cannot meet that,
  M1 records the measured value, keeping the switch fast at least for the
  palette and the plot template.
- **Startup.** Lazy areas (M2) and lazy web views (M6, M7) target the
  constructor's 1.3–1.5 s.
- **Debug timing log.** M2 adds an optional timing log: a heartbeat like
  the probe's, enabled by `SMS_UI_TIMING=1`, that logs every stall over
  50 ms with the action that caused it.

## 4. Findings per screen

Each finding is tagged with the user's words from the brief: *outdated*,
*sluggish*, *cluttered*, *convoluted*, *raw* or *unattractive*. The tags say
what each finding is evidence of.

### 4.1 Window chrome (every screenshot, e.g. [L003], [L059])

- **Cluttered.**
  - Two toolbar rows hold 13 text buttons. Vizard Configuration, Launch Vizard
    and Check Reference Data take a whole second row for rare actions.
  - The window spends about 205 px (23 % of a 900 px window) on menus,
    toolbars, title row and tab bars before any content.
  - Status appears in three places: the run chip at the top right ("No run
    yet", "Run 1: done in 13 s"), the title line ("not run yet") and the
    status-bar message.
- **Convoluted.**
  - There are three levels of tabs: main tabs, Results sub-tabs and the
    plot-layout controls. On top of that there is a separate side dock with
    its own tabs.
  - "Analyses" (End of Life, Budget) is both a menu and a group inside the
    Scenario tree. "Flight Software" is in Tools and also in the Analyses tree
    group.
  - Problems are shown in the side dock, while the validation strip under the
    editor shows the same text again ([L003], [L069]).
- **Inconsistent.**
  - The status bar reads "Opened /home/user/…/scenarios/te" truncated
    ([L003]).
  - The Explain tab says "The scenario has a problem" on the empty new
    scenario ([L001]); the strip says why, but Explain does not.
  - "Problems (1)" is shown for a *warning* on a valid scenario ([L003]), and
    there is no severity roll-up.
- **Outdated.**
  - The look is Carbon's g10/g100: grey bars, blue outline buttons
    everywhere, and blue bottom-border tabs.
  - The dark theme exists, but switching applies only at the next start.

### 4.2 Templates ([L001], [L002])

- **Raw.** It is a plain list of 31 numbered names
  ("01 - Two-body circular orbit"). There is no mission type, orbit summary
  or one-line description until a row is selected.
- **Convoluted.**
  - "Open Template" is disabled until a row is selected.
  - The hint says "Double-click to open. Customize… changes settings first."
  - There are no recent scenarios, and no "New blank scenario" next to the
    templates (it is under File and the toolbar).
- **Cluttered.** It lives as a node inside the Scenario tree, so the
  scenario's sections appear beside a gallery that is not part of the
  scenario.

### 4.3 Scenario editor (tree + page) ([L003]–[L021], [L040]–[L058])

- **Good, keep.** A section list on the left with a focused form on the
  right already exists (UX audit U-01). The forms show units in labels, and
  inline validation exists.
- **Cluttered.**
  - Forms are boxes inside boxes: a framed page, framed groups (Gravity,
    Simulation settings, Orbit initial condition), and framed scroll areas
    inside them ([L004], [L007]).
  - The checkable groups (Power budget, Station keeping, Delta-V budget) show
    every disabled field at full size ([L010], [L013]), so the page is mostly
    greyed-out inputs.
- **Raw.**
  - Units are in the label text ("Panel area [m^2]", "Battery capacity
    [W*hr]") instead of a field suffix, and the spelling is ASCII ("m^2",
    "kg*m^2").
  - Numbers are left-aligned in proportional Plex with a fixed 4–6 decimals
    ("0.000000", "6928.000").
  - Third-body perturbers are a scrolling checkbox list in lower case
    ("mercury", "mars barycenter") ([L004]).
- **Sluggish and broken.** The Power/propulsion page is wider than its
  column and scrolls sideways at 1440 px. The horizontal scroll bar is
  visible and fields are cut off at the right ([L010], [L047]).
- **Convoluted.**
  - Sensors and actuators are two plain lists of "kind: name" with Add…,
    Edit… and Remove buttons that open a modal dialog ([L008]).
  - The mission-sequence step editor is a modal dialog.
  - The page names are truncated in the tree ("Power / propulsion ...").
  - Budget (AD10) appears both per spacecraft and again under Analyses ›
    Budget.
- **Inconsistent.**
  - Section headers use three styles: bold page title ("Scenario"), framed
    group titles, and checkable group titles.
  - The Mission sequence page has its title flush against the frame edge
    ([L016]).
- **JSON view ([L018])** is a separate tree node, not a toggle of the current
  page.

### 4.4 Run ([L038], toolbar)

- **Good, keep.** One primary Run (Ctrl+R) with a mode choice, a progress
  strip with Cancel (Esc), and the run in a worker.
- **Raw.**
  - The progress bar is indeterminate (a bouncing segment) even though the
    worker knows sim time against end time ([L038]).
  - "Single run ▾" is a text button with a small caret.
- **Convoluted.**
  - Run options are spread over the Run menu: Live plot, Vizard
    Configuration…, Launch Vizard, Check Reference Data, Open Monte Carlo
    Results… and Clear Time Cursor.
  - SIL runs are started from Flight Software › SIL dialog, not from Run.
  - Every Monte Carlo run opens a modal folder picker for its archive
    directory, then a second modal question when that folder already holds a
    batch. The screenshot harness waited on the picker until it answered it
    in code. The plan moves the archive folder into the Run area's Monte
    Carlo options, as a remembered field with Browse…, and keeps the
    overwrite question as the one destructive confirmation.
- **Missing.**
  - There is no run history view. Runs exist only as the Compare tab's pick
    list.
  - The Log tab is empty after a run ([L064]): "Nothing logged yet in this
    session." The engine logs nothing at INFO during a normal run, so the user
    sees no record of it. The GUI itself can log start, end, duration,
    warnings and the saved path. That is a UI change; the engine is not
    touched.

### 4.5 Results › Plots ([L059], [L069])

- **Cluttered.**
  - About 230 px of controls stand above the first plot: layout, x-axis,
    event toggles, a row of suggested plots, four export buttons, a
    provenance line and two provenance warnings, all before the plot.
  - The catalog, its search and the readout table share a 250 px column, so
    each is cramped ([L059]): the readout header is cut, and catalog items
    are cut off.
- **Raw.**
  - The eclipse band is orange, a status-like colour used for data.
  - The axis text is small grey Plex and there is no unit-bearing tick format.
  - The provenance and warnings are always on screen as body text.
- **Sluggish.** Every plot change rebuilds and reloads a whole HTML page with
  plotly.js (§3).

### 4.6 Results › Dashboard and Output ([L060], [L061])

- **Raw.**
  - The Dashboard is an empty white page with one centred line for any
    scenario without comms pointing ([L060]).
  - Output is a `QTableWidget` with proportional, mixed-precision numbers
    ("-5.14757e-07", "0.419172", "nan", "+nan") ([L061]). Units are in the
    quantity text and the headers are two-line.
- **Missing.** There is no overview. The run summary figures that
  `engine.run_summary` already computes (delta-V, propellant used, lowest
  link margin, lowest battery charge, passes, contact time, eclipses, eclipse
  time, data downlinked) appear only in Compare.

### 4.7 Events ([L025], [L062])

- **Good, keep.** It already has a Gantt-style timeline with a table, filters,
  search (Ctrl+F) and CSV export.
- **Raw.**
  - The legend is coloured squares beside checkboxes.
  - Lanes are labelled "smallsat-1 eclipse" and "berlin-gs - smallsat-1".
  - The axis is in hours of elapsed time, not UTC.
  - Timestamps have no `Z` ("2030-01-01 08:40:22").
  - There is no zoom or pan beyond "Fit".
- **Cluttered.** Two lines of prose summary sit above the chart ("1 pass, 1
  eclipse. No burns: no station-keeping or formation control. No modes…").

### 4.8 Compare ([L026], [L063], `*_results_compared`, `*_compare_two_runs`)

- **Raw.** Before two runs exist it is an empty page with one centred
  sentence ([L063]).
- **Convoluted.** Compare is a peer of Results instead of a mode of Results.

### 4.9 Log ([L027], [L064])

- **Raw.**
  - The log is a monospace `QPlainTextEdit` with system-font fallback; the
    mono font is Plex Mono.
  - Level is a combo box. There is no severity colouring and no copy of a
    single record.
- **Missing.** It has no records of runs (see §4.4).

### 4.10 Side dock: Inspector, Explain, Problems ([L028]–[L030], [L065]–[L067])

- **Convoluted.**
  - Three different jobs share one dock. The Inspector shows details of the
    current selection, Explain is a scenario summary, and Problems is the
    validation list.
  - Explain is the default tab, so the inspector is hidden behind it.
- **Raw.**
  - Explain uses pill badges in accent blue for facts ("Sun pointing",
    "Drag"), so blue means "fact" there and "action" elsewhere.
  - The stat tiles wrap their text ("Degree-10 Earth + Sun/ Moon"; "SSO
    97.59 deg, 550 km alt").
  - Problems is a list of coloured text lines without icons, IDs, objects,
    or sorting by severity.

### 4.11 Analyses: End of Life, Budget, Flight Software ([L019]–[L021], `*_end_of_life_computed`)

- **Cluttered.** Budget has three buttons, an altitude list and a disabled
  "Copy as CSV" on one row above an empty table with no empty state ([L020]).
- **Inconsistent.**
  - Flight Software mixes export, SIL and a report button.
  - Its status chip ("Not exported") is grey-on-grey ([L021]).

### 4.12 Dialogs ([L081]–[L115])

- **Convoluted.** Seven editors are modal dialogs: spacecraft, device, ground
  station, mission step, dispersion, 3D model and SIL options. In each case
  the brief asks for inline editing or the inspector. The spacecraft editor
  dialog duplicates the tree pages.
- **Cluttered.** The spacecraft editor dialog is the scenario editor's pages
  again as tabs, several of them scrolling far past the window
  (`*_dialog_spacecraft_*_end`).
- **Raw.**
  - The About and discard confirmations are plain `QMessageBox`es
    ([L114], [L115]).
  - The command palette ([L106]) is a flat list of "Menu > Item" with the
    shortcut appended to the text, not aligned. It has no categories and
    no search of scenario objects or settings.
  - The device editor ([L093]) shows the raw kind ("star_tracker").
    "Start from a real device" sits in an empty left column, with the
    catalogue picker at the bottom ("-- none (custom values) --") and a
    disabled "Apply device values"; most of the dialog is empty.

### 4.13 Window sizes (`*_window_1280x720_*`, `*_window_2560x1440_*`)

- At 1280×720 the plot area shrinks to roughly a third of the window because
  of the fixed chrome and control rows.
- At 2560×1440 the forms stretch input fields across the full width.

### 4.14 Dark theme ([D…])

- The dark theme is complete (iteration 7a), but its surfaces are close
  together (Carbon g100 #161616/#262626).
- Plots use the same categorical order in both themes. The dark theme is not
  separately validated against its surface.
- The selected "Suggested" chip is accent text on an accent-tinted fill. That
  is low contrast in dark ([D059]) and at the edge in light ([L059]).
- The eclipse band is a brown-orange wash over the whole plot area ([D059]).
- The Monte Carlo failure chip ("3 runs failed") is dark red on near-black
  ([D079]).

### 4.15 A defect found by the harness (not a UI issue)

- **Monte Carlo from the GUI fails every run when `thread_count` is 1.**
  Template 09 uses 1, which is also the schema default. The harness's batch
  of template 09 ended "3 of 3 runs failed" ([L079], [D079]).
- **Cause.** `gui/run_worker.MonteCarloWorker` runs the batch on a
  `QThread`. With one thread, Basilisk's
  `utilities/MonteCarlo/Controller.py:787` runs each case in-process and
  calls `signal.signal(SIGINT, SIG_IGN)`. Python allows that only on the
  main thread, so it raises `ValueError: signal only works in main thread of
  the main interpreter`.
- **Probably not affected (not tested here):** the CLI, which runs on the
  main thread, and `thread_count` > 1, where each case runs in a pool
  process.
- **Fixed on 2026-10-20, before M1** ([Q9](#9-questions-for-you)), as
  SRelD K-18.
  - The GUI now runs the batch in a spawned child process
    (`gui/monte_carlo_process.py`), where the controller runs on a main
    thread.
  - Its log records come back to the GUI's Log view.
  - Basilisk and the batch's files are unchanged.
  - The regression test, `tests/gui/test_run_worker.py::test_monte_carlo_worker_runs_a_single_thread_batch`,
    failed before the fix.

### 4.16 Gaps against the brief that are not screens

- **No 3D orbit view and no ground-track map in the GUI.** Vizard provides 3D
  outside the app. The brief's "ground track map and 3D orbit view must stay
  fluid" therefore applies only to the 3D *model* view, which uses WebGL
  `Mesh3d`. Neither view is added in this overhaul ([Q5](#9-questions-for-you)).
- **No recent-files list.**
- **No UI-scale setting.**
- **No reduce-motion setting.**
- **Live theme switch** is missing (it applies at next start).
- **No debug timing log.**

## 5. Information architecture

### 5.1 The shell

```
┌────┬────────────────────────────────────────────────────────────────────┐
│    │ Top bar: Project name ● saved/unsaved · rev a1b2c3 · Home › Scenario │
│ R  │          › smallsat-1 › Orbit                       [⌘K Search…]   │
│ a  ├───────────────────────────────────────────────┬────────────────────┤
│ i  │ Central workspace (area page; tabs + splitters)│ Inspector          │
│ l  │                                               │ (selection,         │
│    │                                               │  edited in place)   │
│    ├───────────────────────────────────────────────┴────────────────────┤
│    │ Problems panel (collapsible: severity · ID · object · message)      │
├────┴────────────────────────────────────────────────────────────────────┤
│ Status: jobs ▸ Run 2 43 % [×] · Last run 13 s ✓ · Offline · BSK 2.12.0 · │
│         Reference data OK · EOP to 2026-12-18 · EME2000·ITRF93·UTC        │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Rail areas, top to bottom:** Home, Scenario, Run, Results, Timeline,
  Reports. Settings is pinned at the bottom with Help.
  - The rail is built from a registry (`areas.register(id, icon, label,
    page_factory, order)`). A future **Operations** area (operational state,
    pass plans, alerts) is one more registry entry between Timeline and
    Reports, with no change to the shell.
  - The Problems panel and the status-bar job list are shared services, so
    Operations alerts use the same severity model.
- The **menu bar is removed** (macOS, whose native menu this kept, is no
  longer supported: the user's decision of 2026-10-21).
  - Every action lives in one `ActionRegistry`: id, label, icon, shortcut,
    area and handler.
  - The command palette, menus, tooltips ("Run (Ctrl+R)") and the shortcut
    list are all generated from the registry, so they cannot disagree.
  - Decided ([Q2](#9-questions-for-you)): no menu bar on Linux and Windows.

### 5.2 Every current element and its new place

| Today | New place |
|---|---|
| **File** › New | Home › New blank scenario; palette; Ctrl+N |
| File › Open… | Home › Open…; palette; Ctrl+O |
| File › Save, Save As… | Top bar save state (click = save); palette; Ctrl+S, Ctrl+Shift+S |
| File › Quit | Window close; palette; Ctrl+Q |
| **Edit** › Undo, Redo | Top bar (icons); palette; Ctrl+Z, Ctrl+Shift+Z |
| **Run** › Run (Ctrl+R) | Top bar primary **Run** button, available from every area; Run area |
| Run › Run mode (Single, Monte Carlo, SIL) | Run area: segmented control **Single · Monte Carlo · SIL** beside Run |
| Run › Cancel Run (Esc) | Status-bar job ▸ Cancel; Run area; Esc |
| Run › Live plot | Run area option (toggle) |
| Run › Check Reference Data | Settings › Reference data; status-bar indicator |
| Run › Vizard Configuration… | Run area › Visualisation options (inline) |
| Run › Launch Vizard | Run area › Visualisation; Results inspector for a run |
| Run › Open Monte Carlo Results… | Run area › History (a batch row) → Results › Monte Carlo |
| Monte Carlo archive-folder picker (modal, every batch) | Run area › Monte Carlo options: archive folder field with Browse…, remembered per scenario; the overwrite question stays modal |
| Run › Clear Time Cursor | Results/Timeline toolbar; Alt+Backspace |
| **Analyses** › End of Life, Budget | Run area › Analyses (each runs as a job) → results in Results › End of Life, Budget |
| **Tools** › 3D Model… | Scenario › *spacecraft* › 3D model (inline page) |
| Tools › Flight Software | Reports › Flight software (export); SIL comparison in Results |
| Tools › Reference Data… | Settings › Reference data |
| **View** › Side Panel, Inspector, Explain, Problems | Inspector toggle (Ctrl+I), Problems toggle (Ctrl+J); Explain becomes Scenario › Overview |
| View › Reset Layout | Settings › Layout › Reset; palette |
| View › Time Cursor ▸ | Results/Timeline toolbar; palette |
| View › Theme ▸ | Settings › Appearance (live); palette "Toggle theme" |
| **Help** › User manual | Help (rail bottom) › Manual, a non-modal viewer; F1 |
| Help › Keyboard shortcuts | Settings › Keyboard; palette "Shortcuts"; Ctrl+/ |
| Help › Command palette | Ctrl+K; top-bar search field |
| Help › About | Settings › About |
| **Toolbar row 1**: New, Open, Save, Run, Single run ▾, Cancel, Live plot, 3D Model | See the rows above; the toolbar is removed |
| **Toolbar row 2**: Vizard Configuration, Launch Vizard, Check Reference Data | See the rows above; the toolbar is removed |
| Title bar (name, save state, from template, run state chip) | Top bar (name, save state, revision, breadcrumbs); run state moves to the status bar |
| Run progress strip | Status-bar job with determinate progress and cancel; detail in the Run area |
| Stale-results banner | A thin bar at the top of Results/Timeline with **Re-run** |
| Status bar items | Status bar (kept; plus jobs, last run, offline indicator) |
| Validation strip under the editor | Removed; the Problems panel holds it, and the inline field messages stay |
| **Scenario tab** › Templates | **Home** › Templates gallery |
| Scenario › Scenario, Environment, Spacecraft…, Ground stations…, Mission sequence, Monte Carlo | **Scenario** area section list (same nodes, same order) |
| Scenario › JSON | Scenario area toggle **Form · JSON** in the page header (validated before applying) |
| Scenario › Analyses › End of Life, Budget | Run › Analyses (inputs) and Results › End of Life, Budget (outputs); see [Q3](#9-questions-for-you) |
| Scenario › Analyses › Flight Software | Reports › Flight software |
| Spacecraft › Budget (AD10) inputs | Stays in Scenario › *spacecraft* › Budget (inputs) |
| **Results** › Plots | Results › Plots |
| Results › Dashboard | Results › Telemetry (shown only when the run has it) |
| Results › Output | Results › Reports output (the mission-sequence reports) |
| Results › Monte Carlo | Results › Monte Carlo (when the run is a batch) |
| (none) | **Results › Overview**: metric cards from `engine.run_summary` |
| **Events** tab | **Timeline** area |
| **Compare** tab | Results › Compare (pick a run in the run switcher) |
| **Log** tab | Run › Log |
| Side **Inspector** | Right inspector |
| Side **Explain** | Scenario › Overview (first section), and the inspector when nothing is selected |
| Side **Problems** | Bottom Problems panel; error/warning counts in the status bar and top bar |
| `SpacecraftEditorDialog` (Add spacecraft) | Inline: Add creates a node and opens its page |
| `_ItemEditorDialog` (device) | Inspector: the selected device's fields |
| `GroundStationEditorDialog` | Inline page (as the tree page today) |
| `_CommandEditorDialog` | Inspector for the selected step (the list stays on the page) |
| `_DispersionEditorDialog` | Inline table row and inspector |
| `PropagationSetupDialog` | Scenario › Environment (already embedded) |
| `ModelEditorDialog` | Scenario › *spacecraft* › 3D model page; 3D view lazy and opt-in |
| `_ImportOptionsDialog` | Kept modal: one step of a file import |
| `BoxFacetDialog` | Inline popover on the facet table |
| `SpacecraftTemplateDialog` | Add spacecraft ▾ popover gallery |
| Walker, Phasing, ROE generators | Kept as wizards (multi-step, they replace spacecraft); restyled |
| `TemplateCustomizeWizard` | Kept as a wizard, opened from a Home card's **Customize** |
| `OrbitSwitchDialog` | Kept modal: it can overwrite orbit values |
| `SilRunDialog` | Run area › SIL options (inline, shown in SIL mode) |
| `VizardDialog` | Run area › Visualisation options |
| `StartupFetchDialog` | Home first-run card + Settings › Reference data (no modal on start) |
| Reference data dialog | Settings › Reference data |
| `CommandPalette` | Restyled; searches commands, scenario objects (spacecraft, stations, steps, fields), settings, runs |
| `ShortcutsDialog` | Settings › Keyboard (generated) |
| `ManualDialog` | Help viewer (non-modal) |
| About box | Settings › About |
| Discard-changes and autosave-recovery boxes | Kept modal (destructive), restyled |
| Toasts (`feedback.py`) | Kept; restyled; motion 150 ms |

### 5.3 Exports in one place

Every export is listed in **Reports** with its format, default destination,
the provenance attached and the last time it was written:

- plot CSV, PNG, SVG and "Export all";
- events CSV;
- output CSV;
- Monte Carlo table CSV;
- budget CSV;
- flight-software C project;
- SIL report;
- Vizard save file;
- `.obj` model.

The per-view buttons stay, as one **Export** button per view that opens the
same export sheet. The output files themselves do not change (byte-identical).

## 6. Theme package and components

- **`gui/theme/` package** (replaces `theme.py`):
  - `tokens.py`: the brief's token table, verbatim, plus the derived
    selected, diff and status tokens.
  - `type.py`: the size and weight scale.
  - `qss.py`: the QSS generator.
  - `plotly_template.py`, `palettes.py` (an 8-colour CVD-safe categorical
    palette, validated), `icons.py` (a Lucide loader tinted from tokens) and
    `fonts.py` (`QFontDatabase` registration).
  - `apply.py`: `apply_theme(app, mode)`, live, followed by a
    `ThemeChanged` signal that web views and painted widgets listen to.
- **Assets:**
  - `gui/assets/fonts/` holds Inter (400/500/600) and JetBrains Mono
    (400/500), with `OFL.txt` for each.
  - `gui/assets/icons/lucide/` holds only the icons used, with
    `LICENSE` (ISC).
  - IBM Plex and the Carbon glyphs are removed.
- **Tabular figures:** `QFont.setFeature("tnum")` works on the installed Qt
  6.11. `pyproject.toml` allows PySide6 ≥ 6.6, so on 6.6 the numeric columns
  fall back to JetBrains Mono, as the brief says.
- **Components module** (`gui/components/`):
  - buttons (primary, secondary, ghost, danger);
  - `NumberField` (unit suffix, right-aligned, tnum, inline message);
  - `SegmentedControl`, `StatusBadge`, `EmptyState`, `Toast`, `JobProgress`;
  - `DataTable` (`QTableView` + `QSortFilterProxyModel`, sticky header,
    numeric right-aligned, copy as TSV, column menu, hover);
  - `SectionList`, `Inspector`, `ProblemsPanel`.

  Screens are rebuilt from these; nothing styles itself.
- **Plotly:** one template object from the tokens. Plot pages load the
  plotly.js bundled in the `plotly` package once, into one persistent page per
  view. Updates go through `Plotly.react` via `runJavaScript`, not a page
  reload.
- **Enforcement tests (M1):**
  - no hex, font family or pixel size in GUI code outside `gui/theme/`;
  - WCAG AA contrast over every text/background token pair in both themes;
  - no Qt stylesheet warnings when every screen opens in both themes.

## 7. Milestones and acceptance criteria

Every milestone also has to meet all of these:

- the whole test suite passes (see [Q1](#9-questions-for-you) for GUI tests
  that reach into widgets that change);
- golden files and CLI behaviour are unchanged;
- `ruff` is clean;
- the screenshot harness is re-run, and its differences are noted in the
  session summary;
- the CHANGELOG "Unreleased" section is updated, plus `docs/DECISIONS.md`
  for every decision taken.

| # | Milestone | Acceptance criteria |
|---|---|---|
| **M1** | **Foundation**: theme package, tokens, generated QSS, Inter + JetBrains Mono, Lucide, live theme switch, Plotly template, enforcement tests, Carbon removed | The token table matches the brief (or each change is recorded). Fonts register from the package on Linux, Windows and macOS (CI). The theme switches live in under 100 ms (today about 4 s), with every open view restyled, plots included. The hard-coded-style test passes over the whole GUI package (existing literals moved behind tokens). The contrast test passes in both themes. No IBM Plex file or Carbon name remains in code; the docs say "Carbon" only in history. `CLAUDE.md` holds the design rules. `docs/DECISIONS.md` and a licence report for the fonts and icons exist. The look changes; the layout does not. |
| **M2** | **Shell**: nav rail, top bar, Ctrl+K palette (commands, objects, settings), inspector, Problems panel, status bar with jobs, action registry, layout persistence, shortcuts | Every row of §5.2 is reachable (an automated test walks the action registry and the §5.2 mapping). Menu and toolbar actions all exist in the registry with their shortcuts. Problems show severity, ID, object and message, sort by severity and jump to the field. The status bar shows running jobs with progress and Cancel. Layout (rail collapsed, splitter sizes, inspector and Problems visibility) is restored per project. Keyboard-only walk of the shell passes. Existing screens are hosted unchanged inside their areas. |
| **M3** | **Home and templates** | Cards for all 31 templates with mission type, orbit summary and one line. All three come from the template files themselves: the description's first sentence, the orbit and the attitude mode. No new metadata is invented. Also: recent scenarios (QSettings, last 10, missing files marked); "New blank scenario"; Customize opens the wizard; a first-run card replaces the start-up download modal. No thumbnails ([Q4](#9-questions-for-you)). |
| **M4** | **Scenario editor** | Section list + focused form for every schema section. `NumberField` with unit suffixes everywhere: same values and same file output, round-trip tested. No boxes in boxes. Optional groups collapse their fields when off. The Power page fits 1280 px without horizontal scroll. A Form/JSON toggle that validates before applying. Device, ground-station, mission-step and dispersion editing is inline or in the inspector, with their modal dialogs removed. The unsaved-changes indicator works. Undo/redo through `QUndoStack` if it fits the existing `ScenarioHistory`, which otherwise stays. Explain becomes Scenario › Overview. The explainer refresh is debounced (250 ms) and moved off the GUI thread: no keystroke stalls more than 50 ms on any template (today 54 ms max). |
| **M5** | **Run and logs** | Run area: mode segmented control, Run (Ctrl+R), options inline (live plot, Vizard, SIL), and determinate progress where the worker knows sim time. History lists runs with a status badge, duration, mode and a provenance popover, loaded in a worker. The Log shows records for each run (start, end, warnings, saved path: logged by the GUI) in JetBrains Mono, with level filter, search and copy. Saving and pruning runs moves to a worker: the end of a run causes no stall over 50 ms (today 256 ms). |
| **M6** | **Results overview and analysis views** | Overview metric cards from `engine.run_summary`. A card is coloured only where a threshold exists in the scenario or config: link margin < 0 dB (the margin already includes `required_ebno_db`), and battery charge reaching 0. Everything else stays neutral. Plots, Output (a `DataTable`), Telemetry, Monte Carlo (a `DataTable`), Compare (a run switcher), End of Life and Budget are all rebuilt from components. Provenance moves to an info popover. Plot pages are persistent, with plotly.js loaded once, and switching plots stalls less than 50 ms (today up to 155 ms). |
| **M7** | **Timeline and plots** | Timeline rebuilt: UTC axis with `Z`; lanes per ground station and event type; zoom/pan (wheel, drag, keys); the time cursor linked to plots; the table as a `DataTable` that handles 10,000 events without a stall over 50 ms. Plots: the Plotly template, a linked time cursor across the grid, display decimation only (exports unchanged, tested). The 3D model view is lazy and opt-in, and the GUI stays fluid with `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu`. |
| **M8** | **Reports/Exports and Settings** | The Reports area lists every export of §5.3 with format, destination and provenance. Export files are byte-identical to 1.1.0 (tests compare them). Settings: appearance (theme follow-OS/dark/light, UI scale 90/100/110/125 %, reduce motion), reference data, Vizard location, layout reset, keyboard (generated) and About. |
| **M9** | **Final**: performance pass, accessibility pass, after-screenshots, BEFORE_AFTER.md, user-guide screenshots, CHANGELOG, version 1.2.0 | Every interaction of §3 meets 50 ms, or the plan records why not with the measured value. Startup to interactive is faster than the baseline (1.69–1.97 s), and the first visit to any page stalls less than 50 ms (today 383 ms for a spacecraft). Keyboard-only walk of every area passes. `docs/ui/screenshots/after/` and `docs/ui/BEFORE_AFTER.md` exist. User-guide images are replaced. Compliance documents that cite screenshots or the Carbon restyle get their references updated (claims untouched). The version is 1.2.0 in all version files, with a CHANGELOG section describing the new UI. |

**Status.**

- **M1 (2026-10-20):** done except one criterion, and released in 1.1.0
  (the user's decision of 2026-10-20; Q7 below). Applying a theme live
  takes 0.51-0.55 s on a new main window and 2.4 s after every page has
  been visited (before M1: 1.31-1.44 s and 6.1-6.5 s), not under 100 ms: Qt
  re-polishes every widget, most of them hidden. The criterion moves to M2
  with these values (`docs/DECISIONS.md`).
- **M2, split before starting (2026-10-21; §8, "Scope"):**
  - **M2a, the shell:**
    - the action registry;
    - the navigation rail with its areas;
    - the top bar (save state, undo and redo, Run with its mode, the
      Ctrl+K field and breadcrumbs);
    - the command palette, the shortcut list and the tooltips generated
      from the registry;
    - a Settings area;
    - the menu bar and both toolbars removed;
    - the §5.2 reachability test.
  - **M2b, the panels:**
    - the bottom Problems panel (severity, ID, object, message, sorted,
      jump to the field);
    - the status-bar job list with progress and Cancel;
    - the right inspector without the side tabs;
    - layout persistence per project;
    - the keyboard-only walk test;
    - the theme switch criterion carried over from M1.

  M2a hosts the existing screens unchanged: a §5.2 row whose new form
  needs a rebuilt screen (inline editors, Results › Overview, Run history)
  stays where it is until its milestone, and the reachability test records
  where each row is reached now.
- **M2a (2026-10-21): done.** Of M2's criteria it meets these:
  - every row of §5.2 is reachable
    (`tests/gui/test_shell_reachability.py`, which reads the table from
    this plan);
  - every menu and toolbar command is in the registry with its shortcut
    (`tests/gui/test_design_rules.py`, the shortcut table);
  - the existing screens are hosted unchanged.

  The rest is M2b's: the Problems panel, the status-bar jobs, layout
  persistence per project, the keyboard-only walk and the theme switch
  time. Not yet updated: two template descriptions still say "the Events
  tab" (templates are M3), and `compare_tab.png` and `monte_carlo_tab.png`
  in the documentation still show the toolbars (their capture needs runs
  that `scripts/capture_screenshots.py` does not make).
- **M2b (2026-10-21): done, except the theme switch time.** With M2a,
  M2 meets these criteria (`tests/gui/test_panels.py`):
  - Problems shows severity, ID, object and message, sorts by severity
    (errors first, any column on its heading) and goes to the field
    (Enter or a double-click);
  - the status bar shows the running job with its progress and Cancel;
  - the layout (rail collapsed, the main splitters, the inspector's and
    Problems' visibility) is restored per project;
  - a keyboard-only walk of the shell passes.

  Not met: the theme switch takes 0.42–0.47 s on a new window and
  0.73–0.84 s once every page has been visited, not under 100 ms. Nearly
  all of it is Qt's `setStyleSheet` over every widget alive. The
  criterion moves to M9's performance pass, after M4–M8 build their pages
  when first shown (`docs/DECISIONS.md`, M2b). The validation strip under
  the editor (§5.2: removed) stays until M4 rebuilds the editor; Problems
  already lists what it says.

- **M3 (2026-10-22): done.** It meets every criterion of its row
  (`tests/gui/test_home.py`):
  - a card for each of the 31 templates with its mission type (the
    attitude mode, with the pointing mode, and the number of
    spacecraft), orbit summary (the central body and the first
    spacecraft's orbit) and one line (the description's first sentence),
    all read from the template file, with no metadata added;
  - recent scenarios: `QSettings`, the last 10, a missing file marked
    "(missing)" with an icon;
  - New blank scenario; Customize... on each card and in the details
    opens the wizard;
  - the reference-data card on Home replaces the start-up dialog; it
    still asks at every start, as the user decided;
  - no thumbnails (Q4).

  Not met, from the rules every milestone follows: Home's first show
  takes 64–135 ms (`develop`'s list: 19–29 ms), over design rule 6's
  50 ms. It is part of start-up, since the window opens on Home, and
  M9's first-visit criterion holds it (`docs/DECISIONS.md`, M3).

  Also done, left over from M2a:
  - the template descriptions name the Timeline (templates 22, 26 and
    29);
  - `compare_tab.png` and `monte_carlo_tab.png` are captured by
    `scripts/capture_screenshots.py`, which now makes those runs.

- **M4, split before starting (2026-10-22; §8, "Scope"):**
  - **M4a, the forms:**
    - `NumberField` with unit suffixes in every form, the same values
      and the same file output, round-trip tested;
    - no boxes in boxes;
    - optional groups collapse their fields when off;
    - the Power page fits 1280 px without horizontal scroll;
    - the unsaved-changes indicator.
  - **M4b, the editing flow:**
    - the Form/JSON toggle that validates before applying;
    - device, ground-station, mission-step and dispersion editing inline
      or in the inspector, their modal dialogs removed;
    - undo and redo (`QUndoStack` if it fits `ScenarioHistory`);
    - Explain as Scenario › Overview, its refresh debounced (250 ms) and
      off the GUI thread.

  M4a changes how every field looks and reads; M4b changes how the
  editor is driven. Each is one pull request a reviewer can follow.
- **M4a (2026-10-22): done.** It meets its part of M4's criteria
  (`tests/gui/test_forms.py`):
  - number fields with unit suffixes in every form, the same values and
    the same file: every template is written back byte for byte after
    every page is shown;
  - no boxes in boxes: no framed panel or nested scroll area on any page
    of any template (already true after M1; now tested);
  - optional groups collapse their fields when off;
  - the Power page, and every other Scenario page of every template,
    fits 1280 x 720 with the inspector shown, with no horizontal scroll;
  - the unsaved-changes indicator follows an edit until it is saved.

**Order and size.**

- M1 and M2 are the largest. Each touches every screen's styling or hosting,
  but not its contents.
- M3–M8 are each about one screen family.
- M4 and M6 are the heaviest of the screen milestones.

## 8. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| **GUI tests that reach into widgets** (937 GUI tests in 79 files; 21 files read rows through `.item(...)` of a `QTableWidget`, `QListWidget` or `QTreeWidget`; 8 use tab texts; 2–3 use `main_tabs`, `side_tabs` or `results_views`) | "Every existing test passes unchanged" cannot hold literally once tables become `QTableView` and tabs become rail areas | [Q1](#9-questions-for-you). Proposal: keep every behavioural assertion, port only the widget access, and log each change in `docs/ui/TEST_CHANGES.md` with old and new lines. Non-GUI tests and golden files are untouched. |
| **Tests that assert Carbon itself** (`tests/gui/test_theme.py` checks the g10 hex values and the four Plex files; `test_dark_theme.py` checks g100 pairs) | They fail by design when Carbon is removed, which the brief requires | Replaced by the token, contrast and font tests of M1, and recorded in TEST_CHANGES.md ([Q1](#9-questions-for-you)). |
| Live theme switch with web views | Plot pages keep old colours | Plot pages subscribe to `ThemeChanged` and re-apply the template with `Plotly.relayout`. Tested. |
| Moving work off the GUI thread (explainer, run store) | Races: a stale explainer result arrives after a newer edit | Requests carry a generation number and late results are dropped. Workers get only an immutable `Scenario` copy. The engine code is unchanged. |
| WebEngine in software rendering (WSL2) | The 3D model view (WebGL) is slow | It is created lazily, behind a "Show 3D view" action. Plots stay SVG `scatter`, which they already are. |
| Font rendering differences across platforms | Layout tests measured with Plex fail | The width tests (1280 px, 2560 px) are re-measured with Inter in CI on all three platforms in M1. |
| Removing the menu bar | Users who navigate by menus lose that path | Every item is in the palette and the rail; [Q2](#9-questions-for-you). |
| Moving Analyses (End of Life, Budget) out of the Scenario tree | Users look for them where they were | The palette finds them by the old names; the CHANGELOG and manual explain; [Q3](#9-questions-for-you). |
| Scope: 29k lines of GUI | Sessions overrun | One milestone per session. A milestone may split (M4a/M4b) and the split is recorded before starting. |
| Licence and supply of Inter, JetBrains Mono and Lucide | They must be fetched once at development time | Fetched from the projects' own release archives, with checksums and licences recorded in the licence report. Nothing is fetched at runtime. |

## 9. Questions for you

**Answered on 2026-10-20.** The questions stay below as asked.

| # | Decision |
|---|---|
| Q1 | Approved: GUI tests may change how they reach widgets, keeping every behavioural assertion. Each change is listed in `docs/ui/TEST_CHANGES.md`. Non-GUI tests and output tests stay unchanged. The Carbon tests are replaced by the token, contrast and font tests. |
| Q2 | The menu bar is removed on Linux and Windows. macOS keeps its native menu, generated from the action registry. (2026-10-21: macOS is no longer supported.) |
| Q3 | End of Life and Budget inputs go in Run › Analyses, and their results in Results (§5.2). |
| Q4 | Home cards are text only: mission type, orbit summary and one line, all read from the template files. No thumbnails. |
| Q5 | No ground-track or 3D orbit view in this overhaul. Runs do not record the sub-satellite latitude and longitude, so a ground track would need new computation, which a UI-only overhaul excludes. It is proposed as a later feature. |
| Q6 | No suite theme package was supplied, so M1 uses the brief's token table verbatim. The Operations slot is designed generically (§5.1: one registry entry, plus the shared Problems and jobs services), because no operations roadmap exists. |
| Q7 | The version is 1.2.0. On 2026-10-20 the user chose to publish 1.1.0 from `develop`, so M1 ships in 1.1.0; the later milestones go to 1.2.0. |
| Q8 | Both themes' screenshots are kept in the repository, before and after. |
| Q9 | Fixed before M1 (§4.15). |


1. **Tests that touch widget internals.** "Every existing test must pass
   unchanged" conflicts with "remove Carbon" (`test_theme.py` asserts Carbon
   colours and Plex files) and with model/view tables and the new shell,
   because 21 GUI test files read rows through `.item(...)`.
   - **Proposal:** non-GUI tests and every golden/output test stay byte-for-byte
     unchanged.
   - GUI tests keep every behavioural assertion; only the way they reach a
     widget changes.
   - The Carbon-specific tests are replaced by the token, contrast and font
     tests.
   - Each change is listed in `docs/ui/TEST_CHANGES.md`.
   - Is that acceptable?
2. **Menu bar on Linux and Windows.** Remove it, with every action in the
   rail, top bar and Ctrl+K, and the native macOS menu kept? Or keep a
   minimal File/Edit/Help menu?
3. **End of Life and Budget.** Today they sit in the Scenario tree with their
   inputs and results on one page. The plan puts their inputs in Run ›
   Analyses and results in Results. Alternatively both could stay together as
   Results pages with a Compute button. Which matches how you use them?
4. **Template thumbnails.** Should the Home cards show an offline-generated
   thumbnail (a small orbit sketch drawn from each template's elements at
   build time), or text only?
5. **Ground track and 3D orbit view.** The GUI has neither (Vizard does 3D
   outside the app). The brief says they "must stay fluid". Add a ground-track
   plot as part of M7 (a new view of data the run already records), or leave
   both out of this overhaul?
6. **Suite theme package and operations roadmap.** Does SystemDesignStudio or
   HarnessDesignStudio already have a finished theme package from this
   overhaul? If so, please share it and M1 will reuse its tokens verbatim.
   Also, `docs/developer/operations-roadmap.md` does not exist; is there an
   operations roadmap the Operations slot should be designed against?
7. **Version.** The brief's example is 2.0.0 → 2.1.0, but the current
   release is 1.1.0, so the next minor is **1.2.0**. Confirm.
8. **Screenshots in git.** The before-set is 28 MB in 230 PNGs (two
   themes). The after-set will be about the same. Keep both in the
   repository, or keep only the light theme, or store them as a release asset?
9. **The Monte Carlo defect of §4.15.** It affects release 1.1.0. Fix it
   now as a separate bug-fix PR, before M1? My recommendation is a
   `QProcess` running the batch: it keeps the GUI responsive and can be
   cancelled. If not, the overhaul leaves it as it is.

## 10. Decisions taken without asking

These will be recorded in `docs/DECISIONS.md` in M1, each with a one-line
rationale.

- **plotly.js.** Use the copy the `plotly` package already ships
  (`plotly/package_data/plotly.min.js`, offline). Do not copy it into
  `spacemissionstudio`: it is already bundled with a GUI dependency
  (`plotly>=5.0`, not pinned today), and a second copy would add 4.8 MB.
  M1 asks whether to pin plotly and PySide6 in the GUI extra (see the
  licence report).
- **No new runtime dependencies.** Inter, JetBrains Mono and Lucide are
  assets, not packages. There is no SBOM in the repository today, so M1 adds
  `docs/THIRD_PARTY_ASSETS.md` as the licence report and records the plotly
  and PySide6 versions in it.
- **Status colours.** Use the brief's Astro values. Lightness is tuned only
  where the contrast test fails, and each tuned value is recorded.
- **Categorical plot palette.** Use 8 hues, validated for CVD separation
  against both surfaces, and distinct from the status hues.
- **Recent scenarios** are stored in `QSettings` (organisation "AVSLab",
  already set). This is not a file-format change.
- **Run-start and run-end log records** are emitted by the GUI's run
  controller, not the engine.
- **`docs/DESIGN.md`** is rewritten for the new system in M1. The Carbon
  version stays in git history and in a short "superseded" note.
