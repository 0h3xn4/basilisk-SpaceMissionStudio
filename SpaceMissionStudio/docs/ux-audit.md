# UX audit against the UX/UI Standard (2026-10-13)

This audit checks the app as it is on `develop` (after pull request #48) against
[the UX/UI Standard](ux-standard.md). It is step 1 of the standard's "How to work":
**no UI code has changed yet**. Work starts after approval of the decisions at the
end.

It builds on the earlier audits ([`ux_audit.md`](ux_audit.md),
[`ux_guidelines_gap.md`](ux_guidelines_gap.md)), which checked an older set of
guidelines. Most of what those found has been fixed; this audit covers what the new
standard adds.

## How it was done

- **Toolkit.** As the standard asks, I confirmed this from the code first: the app is
  PySide6 6.11.2 on Qt 6.11.2. The plots are Plotly, drawn in a `QWebEngineView`;
  they are neither matplotlib nor pyqtgraph.
- **The walk.** `scripts/capture_ux_audit.py` walks the README's template 22 flow
  offscreen. It captures:
  - the start page and the Scenario Editor;
  - every right-hand tab, before and after a run, and a run in progress;
  - stale results after an edit, and an invalid field;
  - the menus and the dialogs;
  - a comparison of two runs;
  - the window at 1280 x 720 and 2560 x 1440.

  The screenshots are in [`images/ux-audit/`](images/ux-audit/). Running the script
  again gives the "after" pictures.
- **The code.** I read it for what screenshots cannot show: the shortcuts, the tables,
  the message boxes, the stylesheets, the minimum sizes, and how orbit types switch.
- **Not done yet:** a keyboard-only pass and a dark-theme pass (the app has no dark
  theme). The keyboard pass is part of each view's acceptance check.

**Severity:**
- **Blocks work**: a user cannot do the task, or can be misled by what the app shows.
- **Slows work**: it can be done, but takes extra steps or searching.
- **Cosmetic**: looks or reads badly.

## Summary

| Severity | Count |
|---|---|
| Blocks work | 5 |
| Slows work | 28 |
| Cosmetic | 13 |

**The five that block work:**
1. Results are not marked stale after the scenario changes (U-20).
2. Switching orbit type silently changes the orbit (U-14).
3. The window cannot be 1280 x 720, and after a second run it needs 1516 px of width
   (U-03).
4. Validation errors show only at the bottom of the editor, not at the field (U-12).
5. A failed run's details appear only in a modal box, with no log view (U-23).

**The largest structural gaps:**
- There is no scenario tree. The editor is one long scrolling page with modal dialogs
  for most sections.
- Nine tabs crowd the right pane.
- There are no docks (Inspector, Problems).
- There is no dark theme.

**Already met:**
- Runs in a worker thread with Abort.
- One shared time cursor.
- Provenance shown under each plot.
- Undo and redo.
- A command palette (`Ctrl+K`).
- IBM Plex fonts.
- One icon set, with text on every toolbar button.
- The Events timeline and table.
- Plot decimation for long runs.
- Empty states on Results, Events, the Mission Dashboard and Flight Software.

## What already meets the standard

| Standard | Where |
|---|---|
| Simulations in a worker thread, the window never freezes, Cancel | `RunWorker`; **Run > Abort Run** |
| Provenance visible on outputs | The line under each plot (tool, Basilisk, integrator, step, time); provenance in every export ([`images/ux-audit/07_after_run_00_results.png`](images/ux-audit/07_after_run_00_results.png)) |
| Shared time cursor across views | `gui/time_cursor.py`: plots, Events timeline, dashboard, output; an Events row click moves it |
| Undo and redo for every edit | Edit > Undo/Redo over scenario snapshots (`gui/undo_history.py`). This is not `QUndoStack`, but the behaviour is the same |
| `Ctrl+K` command palette | Help > Command Palette ([`15_command_palette.png`](images/ux-audit/15_command_palette.png)) |
| Shortcuts shown in menus | File, Edit, Run, Help ([`05_menu_file.png`](images/ux-audit/05_menu_file.png)) |
| Events as a timeline and a table, kind filters, CSV | Events tab ([`07_after_run_03_events.png`](images/ux-audit/07_after_run_03_events.png)) |
| Decimation at display resolution | `results_widget._display_indices` (min-max per bucket) |
| Fonts | IBM Plex Sans and Mono bundled (`gui/assets/fonts/`) |
| Icons | One SVG set (`gui/icons.py`); toolbar buttons carry text |
| Scientific notation in numeric fields | `PreciseDoubleSpinBox.valueFromText` uses `float()` (`gui/widgets.py`) |
| Frames and time system on orbit inputs | "EME2000 (SPICE J2000) ... at the scenario epoch (UTC)" ([`13_spacecraft_00_orbit__mass.png`](images/ux-audit/13_spacecraft_00_orbit__mass.png)) |
| Template descriptions with "what you learn" | Load Scenario description pane ([`02_load_scenario_22.png`](images/ux-audit/02_load_scenario_22.png)) |

## Issues

Each row gives the issue, its severity, the proposed fix and the screenshot that
shows it.

### App shell and navigation

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-01 | **No scenario tree.** The Scenario Editor is one long scrolling page: Scenario, Propagation setup, Spacecraft, Ground stations, Mission sequence, Monte Carlo. Most sections open modal dialogs (U-11). Finding a parameter means scrolling, then opening a dialog, then a tab | Slows work | Left panel with a tree (Scenario, Spacecraft › each one, Orbit, Environment, Pointing, Mission Sequence, Analyses, Ground Stations). The selected node's form fills the main area. A node with problems gets a badge with a count | [`03_editor_top`](images/ux-audit/03_editor_top.png), [`03_editor_scrolled_1`](images/ux-audit/03_editor_scrolled_1.png) |
| U-02 | **Nine tabs in the right pane.** At 1440 px "Flight Software" is cut off and the tab bar scrolls. When it is selected, "Results" scrolls out of view | Slows work | Main area tabs as the standard lists them: *Scenario, Results, Events, Compare, Log*. Explain moves to a right dock. Data moves to the status bar and a dialog. End of Life and Budget become *Analyses* pages in the tree. The Mission Dashboard and Mission Output become views inside Results. Flight Software moves to a Tools menu and page (decision 2) | [`01_start`](images/ux-audit/01_start.png), [`07_after_run_08_flight_software`](images/ux-audit/07_after_run_08_flight_software.png) |
| U-03 | **The window cannot be 1280 x 720.** Its minimum height is 758 px; the End of Life form alone needs 560. After a second run, Results' "Compare with" row raises the minimum width to 1516 px, more than a 1366 px laptop screen. The left pane is then squeezed until its fields are cut off behind a horizontal scroll bar | Blocks work | Let the comparison row wrap or move into the Compare tab. Put tall forms in scroll areas. Add a test that resizes the window to 1280 x 720 after a run and a comparison, and checks it fits | [`11_window_small_results`](images/ux-audit/11_window_small_results.png), [`10_compare`](images/ux-audit/10_compare.png), [`18_mission_sequence`](images/ux-audit/18_mission_sequence.png) |
| U-04 | **No top bar.** Scenario name, dirty marker, last run time and a run status chip are missing; the name and `*` appear only in the window title. There are two toolbar rows with nine buttons | Slows work | A top bar as in the standard: name · dirty · last run · **Run** · status chip (idle / running 43 % / done / failed). Other actions go to menus and the palette | [`01_start`](images/ux-audit/01_start.png) |
| U-05 | **No docks and no saved layout.** There is no Inspector or Problems panel, no View menu and no **Reset layout** | Slows work | `QDockWidget`s for Inspector, Explain and Problems. Save the layout with `QSettings`. **View > Reset layout** | - |
| U-06 | **Status bar shows only messages.** The Basilisk version appears only when it is not the qualified one. There is no kernels status, no Earth orientation data date and no active frame | Slows work | Permanent status items: Basilisk version · reference data status (click opens Data) · Earth orientation date · frames | [`01_start`](images/ux-audit/01_start.png) |
| U-07 | **Which template a scenario came from is not shown** after opening it; only a passing toast and status message say so | Cosmetic | Show the source in the top bar ("from template 22") until it is saved under a new name | [`03_editor_top`](images/ux-audit/03_editor_top.png) |

### Load Scenario

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-08 | **The 28 templates are a plain list.** There is no search, tags or filter. The starter templates (22-25) are at the bottom. There are no recent or user scenarios. Every row repeats a "Customize..." link | Slows work | A gallery with a search box, tags (LEO, GEO, formation, pointing, propellant, ...) and the one-line description. Starter templates and recent files come first. **Open** is the primary action, **Open as copy** secondary, and double-click opens. Remember the last filter | [`01_start`](images/ux-audit/01_start.png), [`02_load_scenario_22`](images/ux-audit/02_load_scenario_22.png) |
| U-09 | **Empty grey description pane** when no template is selected | Cosmetic | An empty state: "Select a template to see what it shows" | [`01_start`](images/ux-audit/01_start.png) |

### Scenario Editor

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-10 | **One giant scrolling form.** The spacecraft list is a tall empty box holding one item, with six buttons under it | Slows work | One form per tree node (U-01) | [`03_editor_scrolled_1`](images/ux-audit/03_editor_scrolled_1.png) |
| U-11 | **Modal dialogs for what fits in a form, sometimes nested.** These open as dialogs: Propagation setup; the spacecraft editor, with 7 tabs, its sensor and actuator item editor inside it, and the 3D model editor inside that; ground stations; Mission Sequence commands; Monte Carlo dispersions | Slows work | Edit in the main area and the Inspector. Keep dialogs only for wizards, imports and the 3D model editor | [`12_propagation_setup`](images/ux-audit/12_propagation_setup.png), [`13_spacecraft_00_orbit__mass`](images/ux-audit/13_spacecraft_00_orbit__mass.png), [`14_ground_station`](images/ux-audit/14_ground_station.png) |
| U-12 | **Validation errors appear only under the editor**, with schema paths ("scenario.epoch_utc '2030-13-45T99:00:00' is not a valid ISO 8601 datetime"). The field itself is not marked and there is no Problems list. The message is visible only while the editor tab is shown | Blocks work | Show the error beside the field and mark the field. Add a Problems dock listing severity, text and location; double-click jumps to the field. Map each schema path to its widget. Messages use field labels and say how to fix | [`09_invalid_epoch`](images/ux-audit/09_invalid_epoch.png) |
| U-13 | **Units sit in labels, not as suffixes.** For example "Semi-major axis [km]" with spin arrows. Help text is only in tooltips, and allowed ranges are not shown | Slows work | Unit as the field suffix, help text under the field, range in the Inspector. Field suffixes `km`/`m` accepted where unambiguous; the stored value is shown in the Inspector | [`13_spacecraft_00_orbit__mass`](images/ux-audit/13_spacecraft_00_orbit__mass.png) |
| U-14 | **Switching the orbit type silently changes the orbit.** "Classical elements" / "Cartesian" / "TLE" is a combo over separate pages (`gui/orbit_ic_widget.py`, a `QStackedWidget`). Switching shows that page's own values; nothing is converted or said | Blocks work | A segmented control. Switching offers "Convert to state vector" (or elements), shows both sets, and applies only on confirmation. Without conversion, say that the other page's values will be used | [`13_spacecraft_00_orbit__mass`](images/ux-audit/13_spacecraft_00_orbit__mass.png) |
| U-15 | **Mission Sequence.** It is a tree with Add / Add Child / Edit / Remove / Move Up / Move Down. It has no drag reorder and no inline enable/disable, and steps are edited in a modal dialog | Slows work | A list with drag reorder and the move buttons, an enable checkbox per step, type icons, and the selected step edited in the Inspector. Stop conditions shown as sentences ("Stop at the first pass over berlin-gs") | [`18_mission_sequence`](images/ux-audit/18_mission_sequence.png) |
| U-16 | **No raw JSON view** | Slows work | A JSON tab with the same validation, synced both ways | - |
| U-17 | **The Propagation setup summary is read-only;** editing needs the modal dialog. The third-body checklist in that dialog shows only a few bodies at a time in a small box | Cosmetic | Becomes the Environment form (U-01) | [`12_propagation_setup`](images/ux-audit/12_propagation_setup.png) |

### Run

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-18 | **More than one way to run.** There are **Run Simulation** and **Run Monte Carlo** on the toolbar, and **Run SIL...** on the Flight Software tab. Each analysis has its own compute button (Estimate lifetime, Compute budget, Launch delays, Altitude trade) | Slows work | One **Run** action (toolbar, menu, `Ctrl+R`) with a mode: single run, Monte Carlo, SIL. Analyses run from their own Analyses pages with one consistent "Compute" button (decision 3) | [`07_after_run_06_end_of_life`](images/ux-audit/07_after_run_06_end_of_life.png), [`07_after_run_07_budget`](images/ux-audit/07_after_run_07_budget.png) |
| U-19 | **Progress shows only a percentage**, and only with Live Plot on, in a 120 px status-bar bar whose text is clipped. There is no phase ("Propagating... 3.2 of 10 days") and no ETA. Abort has no shortcut | Slows work | A progress strip under the top bar: phase, elapsed, ETA, **Cancel** (`Esc`). The status chip mirrors it | [`06_running`](images/ux-audit/06_running.png) |
| U-20 | **Results are not marked stale.** After the scenario is edited, or even made invalid, Results keep showing the old run with no notice | Blocks work | A persistent banner: "Results are from a previous version of this scenario" with **Re-run**. It compares the scenario's SHA-256 with the one the run's provenance already records | [`08_stale_results`](images/ux-audit/08_stale_results.png), [`09_invalid_epoch`](images/ux-audit/09_invalid_epoch.png) |
| U-21 | **The post-run toast** says "Run complete -- 19 result series": it does not give the duration or the number of events | Cosmetic | For example "Run complete in 6 s: 4 passes, 15 eclipses" | - |
| U-22 | **Which run is shown** is only the time in the provenance line. In Compare the current run is unnamed ("raan" against "raan (Run 1)") | Slows work | Name runs ("Run 2, 12:19") in the status chip, the plot subtitle and legends | [`10_compare`](images/ux-audit/10_compare.png) |

### Log

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-23 | **No log view.** A failed run opens a modal `QMessageBox.critical` with a pointer to the log file, which the user must open themselves | Blocks work | A *Log* tab with the run's log, filterable by level. A failure opens it at the error; the message box goes | - |

### Results

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-24 | **One plot at a time,** chosen from a combo of every series. There is no catalog grouped by category and no grid of plots | Slows work | A plot catalog (search; groups Orbit, Attitude, Power, Link, Thermal, Propellant, Monte Carlo, taken from the existing plot categories). A grid layout (1x1, 2x2, 1x3) saved per scenario, with linked x-axes | [`07_after_run_00_results`](images/ux-audit/07_after_run_00_results.png) |
| U-25 | **No readout panel.** Hover shows one plot's value; there is no panel with every series at the cursor time | Slows work | A readout panel beside the grid: each shown series' value at the cursor, with units | - |
| U-26 | **The time axis offers Elapsed time and Epoch (UTC)**, but not the orbit number | Cosmetic | Add "Orbit number"; one switch for all plots | [`07_after_run_00_results`](images/ux-audit/07_after_run_00_results.png) |
| U-27 | **Events are not drawn on plots** (no eclipse or pass bands) | Slows work | Shaded bands and markers from the event model, each kind toggleable | - |
| U-28 | **Plot library.** Plotly runs inside Qt WebEngine (a Chromium instance): one figure per web view, and the plots depend on WebEngine working on the machine ([Troubleshooting](troubleshooting.md#the-results-plot-stays-blank)) | Slows work | Decision 4 (taken: keep Plotly): build the grid as several figures in one web page, with one shared cursor and linked x-axes | - |
| U-29 | **No "Export all"**; export is per plot | Cosmetic | Export all shown plots (PNG/SVG/CSV) with provenance | - |
| U-30 | **The plot's epoch and time system are not shown** with Elapsed time | Slows work | Subtitle: "t0 = 2030-01-01 08:30:00 UTC" | [`07_after_run_00_results`](images/ux-audit/07_after_run_00_results.png) |

### Events

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-31 | **The table headers lack units and time system.** "Start" and "End" do not say UTC. "Duration" puts the unit in each cell ("7.5 min"). At 1440 px the Detail column is cut ("max ...") | Slows work | Headers "Start (UTC)", "Duration [min]", with right-aligned numbers at fixed precision. Detail split into columns such as "Max elevation [deg]" and "Lowest sunlight [%]" | [`07_after_run_03_events`](images/ux-audit/07_after_run_03_events.png), [`11_window_large_events`](images/ux-audit/11_window_large_events.png) |
| U-32 | **No search and no ground-station filter; no TSV copy** | Slows work | A search box and a station filter. `Ctrl+C` copies the selection as TSV | [`07_after_run_03_events`](images/ux-audit/07_after_run_03_events.png) |

### Compare

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-33 | **Compare is a combo in Results,** limited to one earlier run of this session, plus an "Input differences..." dialog. There is no Compare tab, no scalar summary with deltas, and runs are lost when the app closes | Slows work | A *Compare* tab: pick two or more runs; a scenario diff (old -> new); overlaid plots and event tables; a summary table (lifetime, delta-V, minimum margin) with a delta column. Keep runs on disk (decision 5) | [`10_compare`](images/ux-audit/10_compare.png) |

### Other tabs

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-34 | **Mission Output is empty with no message** for a scenario without a Mission Sequence; only a filter box shows | Slows work | Empty state: "No Mission Sequence in this scenario: reports appear here when it has one" | [`07_after_run_02_mission_output`](images/ux-audit/07_after_run_02_mission_output.png) |
| U-35 | **The Budget table is empty, with headers only,** until Compute | Cosmetic | Empty state naming the button | [`07_after_run_07_budget`](images/ux-audit/07_after_run_07_budget.png) |
| U-36 | **Data tab: the "Covers" column is cut** behind a horizontal scroll bar at 1440 px | Cosmetic | Wrap the column or show it in the Inspector | [`07_after_run_04_data`](images/ux-audit/07_after_run_04_data.png) |
| U-37 | **Vizard has two toolbar buttons** (Vizard Configuration, Launch Vizard) and an "Open in Vizard" button in Results. The connection state is not shown | Slows work | One "Open in Vizard" action with a status chip (connected / not installed / path). When Vizard is not found, show the path searched and the download action | [`01_start`](images/ux-audit/01_start.png) |

### Shared components

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-38 | **Data tables are `QTableWidget` in 11 modules.** None has `Ctrl+C` copy as TSV, and alignment and precision vary | Slows work | One table component: `QTableView` + `QAbstractTableModel`, sortable and filterable, numbers right-aligned in Plex Mono with fixed precision per column, the unit in the header, `Ctrl+C`/`Ctrl+A`, and a context-menu export | - |
| U-39 | **113 `QMessageBox` calls** (49 critical, 16 warning, 11 information), several for routine information | Slows work | Inline errors and toasts. Keep message boxes for confirming destructive actions, with a sentence that names the object and the consequence | - |
| U-40 | **Empty states are missing on** Mission Output, Budget and the template description (U-09, U-34, U-35) | Cosmetic | One empty-state component used everywhere | - |

### Keyboard

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-41 | **Shortcuts are missing.** The shortcut sheet exists (Help > Keyboard Shortcuts) but `?` and `Ctrl+/` do not open it. Abort, Live Plot, Monte Carlo and tab switching have no shortcuts | Slows work | `Ctrl+/` and `?` (outside text fields) open the sheet. `Esc` cancels a run. `Ctrl+1`...`Ctrl+5` switch the main tabs. `F6` cycles the panels | [`05_menu_run`](images/ux-audit/05_menu_run.png), [`05_menu_help`](images/ux-audit/05_menu_help.png) |
| U-42 | **The keyboard-only pass is not done** (focus order, reaching every control) | Slows work | Part of each view's acceptance check, with a test that tabs through each page | - |

### Visual system

| ID | Issue | Severity | Proposed fix | Screenshot |
|---|---|---|---|---|
| U-43 | **No dark theme**, and the app does not follow the OS | Cosmetic | Light and dark palettes from the theme module, OS-following by default, **View > Theme**. The plot hues need their own dark steps: an earlier check found 4 of the 8 failing the dataviz validator on a dark surface (HISTORY.md) | - |
| U-44 | **98 `setStyleSheet` calls outside `theme.py`** (`template_wizard.py` has 8). Hard-coded colours remain in `badges.py`, `feedback.py`, `icons.py` and `model_editor_dialog.py`. This blocks a dark theme | Cosmetic | Move every colour to theme tokens; generate the QSS and `QPalette` from them; add a test that finds no hex colour outside `theme.py` | - |
| U-45 | **Type scale.** The theme uses Carbon's 14 px base; the standard asks for 12/13/16/20 px | Cosmetic | Decision 1 | - |
| U-46 | **"Live Plot" looks like a pressed tab or selected toolbar item**, unlike the other buttons; its state is unclear | Cosmetic | A labelled toggle ("Live plot: on") in the Run options | [`01_start`](images/ux-audit/01_start.png) |

## Decisions needed

1. **Visual system.** The earlier decision restyled the app to IBM Carbon (g10 tokens,
   14 px base). The standard sets its own scale: 12/13/16/20 px type, a 4/8/12/16/24/32
   spacing scale, light and dark themes. **Proposed:** keep Carbon's colours and
   components, adopt the standard's type and spacing scales, and add a dark theme
   (Carbon g90/g100 tokens).
2. **Where today's nine tabs go.** **Proposed:**
   - *Explain*: a right dock.
   - *Data*: a status-bar item, plus a dialog for downloads and imports.
   - *End of Life* and *Budget*: Analyses pages in the tree.
   - *Mission Dashboard* and *Mission Output*: views in Results.
   - *Flight Software*: a Tools page.
   - *Monte Carlo results*: a Results view.
3. **One Run.** **Proposed:** **Run** with a mode (single, Monte Carlo, SIL) and
   `Ctrl+R` for the selected mode. The Analyses keep their own Compute buttons on their
   pages, since they are separate computations from the run.
4. **Plot library.** The standard prefers pyqtgraph. Plotly already decimates and
   exports SVG with provenance, but it needs Qt WebEngine and shows one figure per
   view. **Proposed:** move the Results grid to pyqtgraph, a new dependency
   (MIT-licensed, pure Python on PySide6). Exports move to pyqtgraph's SVG and PNG
   exporters, with the same provenance metadata.
5. **Keeping runs.** Comparing runs across sessions needs them on disk. **Proposed:**
   keep the last 10 runs per scenario in the user data folder (results and
   provenance), with a size cap and a "Delete runs" action.
6. **File format.** None of the proposed changes alter the scenario format or what
   Basilisk computes. U-14 adds a conversion between orbit types; the conversion uses
   the existing `orbitalMotion` functions, and the scenario still stores the chosen
   type.

## Decisions taken (2026-10-13)

1. Visual system: Carbon's colours and components, with the standard's type and
   spacing scales and a dark theme that follows the OS (as proposed).
2. Tabs: as proposed.
3. One Run (taken 2026-10-13, Run iteration): **Run with a mode** (Single run, Monte Carlo,
   SIL) and `Ctrl+R` for the selected mode, as proposed. The Analyses keep their own
   Compute buttons. The Flight Software page's per-spacecraft Run SIL... is gone (iteration
   4b): SIL runs only from Run in SIL mode, and the page says so.
4. Plot library: **keep Plotly**. The Results grid and readout are built on Plotly,
   with several figures in one web page; no new dependency.
5. Keeping runs on disk (taken 2026-10-14): **saved to disk**, so a session's runs come back the next
   time. Built in the Compare iteration (5c).
6. File format: no change (for information).

Start with the two blockers that need no structural decision: U-20 and U-03.

## Done

| Iteration | Issues | What changed |
|---|---|---|
| 1 (2026-10-13) | U-20, U-03 | A banner above the run views names stale results, with Re-run, by the scenario's SHA-256. The End of Life page scrolls. The comparison controls moved to their own row, and the combo is sized by characters, not by the longest run label. After two real runs of template 22 the window's minimum size went from 1516 px wide (and 758 px tall at start-up) to 1118 x 529 px. Tests: `tests/gui/test_stale_results_and_window_size.py` |
| 2a (2026-10-13) | U-04, U-06, U-07 | A top bar above the work area: the scenario's name · Unsaved changes / Unchanged / Saved / Not saved yet · where it came from ("from template 22", a file name) · the last run (time, state, length), and a status chip (No run yet, Running 43 % or Running 1:05, Done in 6 s, Failed, Cancelled) in the theme's status colours. Permanent status-bar items: the Basilisk version (warning style when not the qualified one), the reference data ("all N OK" or "k of N need attention"; clicking it opens the Data tab), the Earth orientation data's high-accuracy end date, and the frames (EME2000 · ITRF93 or IAU_EARTH · UTC). The two toolbars stay as they were: Run stays their one primary button (decision 3, one Run, comes with the Run feedback iteration). Tests: `tests/gui/test_app_shell.py` |
| 2b (2026-10-13) | U-02, U-05, U-23 (part), U-36 | Five main tabs: *Scenario* (Load Scenario, Scenario Editor, End of Life, Budget, Flight Software), *Results* (Plots, Dashboard, Output, and Monte Carlo when there is one), *Events*, *Compare* (the session's runs and the inputs that differ, with the overlay in Results) and *Log* (the session's log, by level and text; a failed run opens it at its warnings and errors). A side panel dock with *Inspector* (the focused field's label, value, range and help), *Explain* (now wrapping to the panel) and *Problems* (the validation error and plausibility warnings; double-click opens the editor). The reference data moved to a dialog opened from the status bar or Tools. Analyses, Tools and View menus; the layout is kept in `~/.spacemissionstudio/layout.ini`, and View > Reset Layout restores it. Separators between the status-bar entries. The stale-results banner shows over the run views only. The scenario tree (U-01) replaces the Scenario tab's own tabs in the Scenario Editor iteration. Tests: `tests/gui/test_workspace.py` |
| 3a (2026-10-13) | U-12, U-14 | Problems take you to the field: a double-click opens the Scenario Editor's field, or the spacecraft, ground station or propagation setup dialog at the field, with the problem in a banner; the field is marked red with the message under it, and the mark goes when it is edited. Scenario fields' messages start with their label. The dialogs' OK shows a problem the same way instead of a message box. An orbit's messages now name its spacecraft. The orbit type is a segmented control; switching asks, showing both sets: convert (Basilisk's `orbitalMotion` and `mu`; a TLE at the epoch), use the page's values, or cancel. Nothing converts to a TLE, and the question says why. Tests: `tests/test_problem_location.py`, `tests/gui/test_field_errors.py`, `tests/test_orbit_conversion.py`, `tests/gui/test_orbit_switch.py` |
| 3b (2026-10-13) | U-01, U-10, U-11, U-17 | The Scenario tab is the scenario tree: Templates, Scenario, Environment, Spacecraft (a node per spacecraft), Ground stations (a node per station), Mission sequence, Monte Carlo, and Analyses (End of Life, Budget, Flight Software), each node's page beside it. The environment (the former Propagation setup window and summary), each spacecraft and each station are edited in their pages, applied 300 ms after the last edit, with Undo; a page that does not validate marks the field, lists the problem and keeps the scenario from running. Nodes count their problems. A page's long form rows put the field under the label, so the window still fits 1280 x 720. Edit... in a list goes to the node; Add..., the templates and the generators stay dialogs. Tests: `tests/gui/test_page_tree.py`, `tests/gui/test_scenario_tree.py` |
| 3c (2026-10-13) | U-15, U-16 | The Mission Sequence is a list of steps, each a sentence with its kind's icon and a checkbox that leaves it out of the run (`Command.enabled`, saved only when false); the selected step's form beside it (under it on a narrow window), applied as you type; drag to reorder or nest in an `if`/`while`, Move up/down (Alt+Up/Down), Duplicate; a step's problem shown in red and opened from Problems. A JSON page in the scenario tree: the saved text, editable, applied through the same parsing as opening a file, kept in step with the other pages; broken JSON is marked at its line and blocks the run. Also: a file's value outside a field's range is kept and flagged instead of clamped, and every problem is listed when a form holds one. The standard's "edited in the Inspector" became a form beside the list, as for the other nodes since 3b. Tests: `tests/test_command_enabled.py`, `tests/gui/test_mission_sequence_list.py`, `tests/gui/test_json_view.py`, `tests/gui/test_out_of_range.py` |
| 4a (2026-10-13) | U-18, U-19, U-41 (Esc), U-46 | One **Run** (`Ctrl+R`) with a mode button beside it: Single run, Monte Carlo, SIL (decision 3); Run Monte Carlo left the toolbar and the menu. A progress strip under the top bar while a run goes: its phase ("Propagating: day 0.40 of 1", "Step 2 of 5: Burn 5 m/s on sat-1", "Monte Carlo: 37 of 200 cases done"), a bar, the time elapsed, about how long is left once there is enough to go on (2 % and 3 s), and **Cancel (Esc)**; Esc is Cancel Run's shortcut. Every run now reports its fraction, with Live plot on or off; a Mission Sequence reports its steps (`MissionEngine(on_step=...)`); a Monte Carlo batch is counted by its cases' files, and says it cannot be cancelled. Live plot is a labelled toggle ("Live plot: on"). Tests: `tests/gui/test_run_feedback.py` |
| 4b (2026-10-13) | U-21, U-22, U-23 (rest), U-39 (run path) | Runs are named: `RunRecord.name` ("Run 2, 12:19"), and the chip ("Run 2: done in 6 s"), the top bar ("Run 2 at 22:40, done, 6 s"), the provenance line and, when comparing, the shown run's traces ("raan (Run 2)") say which run. The post-run toast gives the length and the events ("Run 2 complete in 6 s: 4 passes, 15 eclipses"). The run path's message boxes are gone (14 of them: an invalid scenario, a run in progress, Vizard not connected, a live update or display that failed, a failed run, Monte Carlo off, a folder that is not empty, a batch that failed or had failed cases, closing during a run): `_report_run_problem` writes the message to the Log, shows a toast and the status bar, and opens where it is dealt with (Problems at the field, the Monte Carlo page, the Log at its errors). The Flight Software cards' Run SIL... is gone (decision 3 note); the page points to Run in SIL mode. File, save and Vizard launch messages keep their boxes for now (U-39, iteration 5). Tests: `tests/gui/test_run_messages.py` |
| 5a (2026-10-14) | U-24, U-25, U-26, U-27, U-28, U-29, U-30 | Results > Plots is a workspace: a plot **catalog** (`gui/plot_catalog.py`: groups Orbit, Attitude, Power, Link, Data, Thermal, Propellant, Sensors, Monte Carlo from `plot_categories.plot_group`; search by title, code name or group; a tick adds a plot to the grid, a click shows it in the selected cell; the access timeline is an entry under Link) and a **grid** of up to six plots (1 x 1 to 3 x 2) drawn as several Plotly figures in one page (`gui/plot_page.py`, decision 4) with linked x axes, the time cursor on every plot and a click to select the plot Save PNG/SVG act on. The layout fits the pane (cells near twice as wide as tall) and is kept per scenario in `~/.spacemissionstudio/layout.ini`. A **readout** under the catalog (`gui/readout_panel.py`): every shown series at the pointer or the cursor, with units. The X axis adds **Orbit number** (`engine/orbit_number.py`: revolutions from the ascending node, from the recorded position and velocity). **Event bands** from `engine.events` in the Events tab's colours, each kind switched on and off (at most 400 of a kind on one plot). "t0 = ... UTC" under each title on an elapsed-time or orbit axis. **Export all** (every shown plot as PNG or SVG, its series as CSV, `provenance.json`). The series and view boxes are gone. Tests: `tests/gui/test_plot_workspace.py`, `tests/test_orbit_number.py` |

## Proposed order of work

As the standard sets it, one screen or component per iteration, each with before and
after screenshots (`scripts/capture_ux_audit.py`) and its acceptance checklist.

1. **App shell:**
   - top bar and status chip;
   - main tabs;
   - docks (Inspector, Explain, Problems) with saved layout;
   - status bar;
   - minimum-size fix (U-01 to U-07, U-03 first).
2. **Scenario Editor:**
   - tree and per-node forms;
   - Problems panel and inline errors;
   - orbit-type conversion;
   - Mission Sequence list;
   - JSON view (U-10 to U-17).
3. **Run feedback:**
   - one Run;
   - progress strip;
   - stale-results banner;
   - Log tab;
   - toasts (U-18 to U-23).
4. **Results, Events, Compare** (U-24 to U-33).
5. **Shared table component and message boxes** (U-38 to U-40), applied as each view
   is touched.
6. **Visual polish:** theme tokens, dark theme, type scale, keyboard (U-41 to U-46).
   Then `docs/DESIGN.md`.

The first iteration I would propose is U-20 (stale results) together with U-03 (the
window fitting 1280 x 720). They are the two blockers that need no structural
decision.

---

**See also:** [UX/UI Standard](ux-standard.md) ·
[earlier UX audit](ux_audit.md) · [guidelines gap analysis](ux_guidelines_gap.md)
