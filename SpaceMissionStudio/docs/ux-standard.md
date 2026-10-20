# UX/UI Standard — SpaceMissionStudio

You are redesigning the UX/UI of **SpaceMissionStudio**, a desktop app for satellite mission
analysis built on Basilisk. The current UI is clunky, unintuitive and visually poor. Your job is
to make it feel like a professional engineering tool that a mission analyst would choose over
GMAT or a Jupyter notebook for day-to-day work, without changing what Basilisk computes.

## The tool, as it exists
- Workflow: **Load Scenario** (27 templates) → **Scenario Editor** (forms over a JSON scenario,
  validated as you type, with an **Explain** tab) → **Run** (`Ctrl+R`) → **Results** (plots)
  and **Events** (passes, eclipses, burns, conditions) → **Compare** runs → **Export**
  (CSV, PNG, SVG, CCSDS, C project).
- Content: orbits (elements / state vector / TLE), environment (gravity, drag, SRP, EOP),
  pointing modes, station keeping, formations, constellations, Mission Sequence (burns,
  Lambert, conditions, stop-on-event), analyses (passes, eclipses, power, link, data, thermal,
  Monte Carlo, lifetime, propellant), 3D view via Vizard.
- Users: mission/GNC/systems engineers running many variants of a scenario and comparing them.
- Stack: Python desktop GUI (assumed Qt / PySide6 — **confirm from the code before starting**;
  if it is something else, translate the Qt-specific rules below to the equivalent).

## Non-negotiable principles
1. **Numbers are sacred.** Every quantity shows unit, frame (ECI/ECEF/LVLH), epoch and
   time system (UTC / TAI / mission elapsed time). Never round away significant digits.
   Keep the existing provenance on every output and make it visible (tooltip or inspector).
2. **State is always visible.** Dirty scenario, results stale relative to scenario, run in
   progress, which run is displayed, which template it came from.
3. **Nothing silent.** Every action gives specific feedback. Destructive actions are undoable
   or confirmed with a sentence that names the object and the consequence.
4. **Keyboard-first.** All functions reachable by keyboard; shortcuts shown in menus;
   `?` or `Ctrl+/` opens a shortcut sheet; `Ctrl+K` opens a command palette (open template,
   run, jump to parameter, show plot…).
5. **Density with hierarchy.** One well-structured screen beats five sparse tabs.
6. **One way to do each thing.** Same component, same behaviour, everywhere.
7. **Fast.** UI reacts in <100 ms; simulations run in a worker thread with progress, ETA
   and cancel; the window never freezes.

## Target layout (app shell)
- **Top bar:** scenario name · revision/dirty marker · last run time · Run button (primary,
  single) · run status chip (idle / running 43 % / done / failed).
- **Left panel (collapsible):** scenario tree — Spacecraft, Orbit, Environment, Pointing,
  Mission Sequence, Analyses, Ground Stations. Selecting a node shows its form in the main area.
  Nodes with validation problems get a red/amber badge with a count.
- **Main area:** tabbed workspace: *Scenario*, *Results*, *Events*, *Compare*, *Log*.
- **Right panel (dockable):** *Inspector* (details of selected parameter, help text, source,
  allowed range), *Explain* (the existing summary), *Problems* (validation list; double-click
  jumps to the field).
- **Bottom status bar:** Basilisk version · kernels status · EOP data date · active frames.
- Dock layout persists via `QSettings`; **View > Reset layout** restores defaults.

## Screen-by-screen

### Load Scenario (template gallery)
- Replace a plain list with a searchable, filterable gallery: tags (LEO/GEO/formation/
  pointing/propellant…), one-line description, small orbit thumbnail if cheap, "what you
  learn from it". Recent and user scenarios appear first.
- Primary action: **Open**. Secondary: **Open as copy**. Double-click opens.
- Show "Starter" templates first for new users; remember the last used tab/filter.

### Scenario Editor
- Form per tree node, not one giant scrolling page. Label above field, unit as suffix,
  help text under the field, allowed range shown; validation on edit (debounced) with the
  message beside the field *and* in the Problems panel.
- Orbit entry: segmented control for Elements / State vector / TLE; converting between them
  is explicit ("Convert to elements") and shows the conversion, never silent.
- Numeric fields accept scientific notation and `km`/`m` suffixes where the unit is unambiguous;
  show the stored value in the inspector.
- Mission Sequence: an ordered list with drag-reorder *and* move up/down buttons, inline
  enable/disable, type icon + label, selected step edited in the inspector. Conditions and
  stop-on-event shown as readable sentences ("Stop at first pass over Berlin").
- Keep a **raw JSON** view as a secondary tab with the same validation, synced both ways.
- Undo/redo via `QUndoStack` for every edit.

### Run
- One **Run** action everywhere (toolbar, menu, `Ctrl+R`). Running shows a non-modal progress
  bar with phase ("Propagating… 3.2 of 10 years"), elapsed, ETA and Cancel.
- After a run: results tab activates automatically unless the user is typing in the editor;
  a toast reports duration and number of events; failures open the Log tab at the error.
- If the scenario changes after a run, Results shows a persistent "Results are from a previous
  scenario version" banner with a Re-run button.

### Results (plots)
- Plot workspace with a plot **catalog** (search box, grouped: Orbit, Attitude, Power, Link,
  Thermal, Propellant, Monte Carlo) and a grid of selected plots; layout (1×1, 2×2, 1×3…)
  selectable and saved per scenario.
- **Shared time cursor** across all plots; hover shows values of every series at that time in
  a readout panel with units; `Ctrl` drag zooms, double-click resets, linked x-axes.
- Time axis offers UTC, mission elapsed time, and orbit number; switch applies to all plots.
- Events (eclipses, passes, burns) drawn as shaded bands / markers on plots, toggleable.
- Legend entries are clickable (hide/solo). Series colours come from the theme and are stable
  across runs so Compare is readable.
- Export: PNG/SVG/CSV from a plot's own menu; one "Export all" action.
- Use **pyqtgraph** (or keep matplotlib only if already fast) for interactive time series;
  decimate at display resolution so 10-year runs pan smoothly.

### Events
- A table *and* a timeline (Gantt-style lanes per event type) in a splitter.
- Filters by type and ground station; search; columns: type, start (UTC), end, duration,
  max elevation / depth as applicable, with units in headers. Click a row → plots' cursor
  jumps to it and the row is highlighted in the timeline.
- Export CSV; copy selection as TSV.

### Compare
- Pick two or more runs; show (a) a scenario **diff** (changed parameters, old → new) and
  (b) overlaid plots and event tables with run names in the legend. Differences in scalar
  summaries (lifetime, Δv used, min margin) in a side-by-side table with the delta column.

### Vizard / 3D
- One clearly labelled action "Open in Vizard"; show status (connected / not installed) and
  the exact path or download link when not found. Never fail silently.

## Shared components
- **Tables:** `QTableView` + `QAbstractTableModel` (never `QTableWidget` for data); sticky
  headers; sortable/filterable; numbers right-aligned with tabular figures and fixed precision
  per column; unit in header; `Ctrl+C` copies TSV; `Ctrl+A`; context-menu export.
- **Forms:** `QFormLayout` or grid on a 4/8 px scale; `QValidator` + inline error label;
  never a `QMessageBox` for validation. Never clear a form on error.
- **Problems panel:** severity icon + text + location; double-click jumps; counts in tree.
- **Empty states:** every empty table/plot/list says what is missing and what to do
  ("No run yet — press Ctrl+R").
- **Long operations:** worker thread (`QThread`/`QThreadPool`), progress + cancel, never a
  frozen window.

## Visual system
- One theme module as the single source of truth (colours, spacing, fonts, radii) generating
  both `QPalette` and the app QSS. No scattered `setStyleSheet` calls, no hard-coded colours.
- Light and dark themes, following the OS by default, switchable in View.
- Fonts: Inter for UI, JetBrains Mono for numbers/IDs/JSON, both shipped with the app
  (1.1.0; IBM Plex before, superseded by `docs/ui/UI_OVERHAUL.md`). Tabular figures in all
  numeric cells.
- Type scale 12/13/16/20 px. Spacing scale 4/8/12/16/24/32 px.
- Colour carries meaning only: status (nominal/caution/warning/critical/unknown), selection,
  focus. Status colours colour-blind safe and paired with icon/text. One accent colour for the
  primary action. No gradients, no shadows beyond what Qt draws.
- Icons: a single SVG set (e.g. Lucide or Tabler), 16/20 px, always with a tooltip and, for
  toolbar buttons, a visible label on hover; no icon-only buttons without a tooltip.
- High-DPI: scalable icons only, no fixed pixel sizes for text.

## Anti-patterns to remove (look for these in the audit)
- Giant scrolling forms with every parameter on one page.
- Modal dialogs for things that fit in an inspector; nested modals.
- Numbers without units or frames; precision that varies within a column.
- Results that can be stale without saying so.
- Icon-only toolbar buttons; inconsistent button sizes; multiple primary buttons per view.
- Blocking the UI during a run; `QMessageBox` for routine information.
- Plots with default matplotlib styling, unreadable legends, unlinked axes.
- Tabs that hide the fact that nothing is loaded yet.

## How to work
1. **Audit first.** Walk every screen (use the template 22 flow from the README as the
   script). Produce `docs/ux-audit.md`: issue · severity (blocks work / slows work /
   cosmetic) · proposed fix · screenshot reference. Stop and wait for approval.
2. **Order of work:** app shell & navigation → Scenario Editor forms + Problems panel →
   Run feedback → Results/Events/Compare → visual polish (theme, icons, fonts). Do not start
   with colours.
3. **One screen or component per iteration.** Show before/after screenshots (automate with
   an offscreen `QApplication` render if possible), one line per decision, then ask.
4. **Never change simulation semantics** or scenario file format without saying so explicitly.
5. **Acceptance checklist per view:** keyboard-only pass · dark and light theme · long names
   and 10-year runs · empty state · error state · window at 1280×720 and 2560×1440 ·
   all existing tests pass · no new hard-coded colours.
6. Write `docs/DESIGN.md` documenting tokens, components, status colours and shortcuts.
7. When unsure about an astrodynamics convention (frames, sign of RAAN, time systems), ask.
