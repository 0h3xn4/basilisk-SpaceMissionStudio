# Changelog

What changed in SpaceMissionStudio, release by release, newest first.
Each entry is a short summary; [`HISTORY.md`](HISTORY.md) has the full
story behind every change (why, how it was found, how it was tested).

The version follows [semantic versioning](https://semver.org): a major
version breaks something you rely on, a minor one adds features, a patch
fixes bugs.

## Unreleased

**Breaking (2.0.0): Python 3.14 only.** SpaceMissionStudio now needs
Python 3.14; 3.11 to 3.13 are no longer supported (`requires-python =
">=3.14"`). The `.deb` and the Windows setup program bring their own
Python, now 3.14.8, so their users need do nothing. Installing from
source or with `install.sh`/`install.ps1` needs Python 3.14 on the
computer: Ubuntu 24.04 ships 3.12 and Debian 12 ships 3.11, so use the
`.deb` or a Python from python.org or `uv`. CI tests 3.14 only. Basilisk
2.12.0 and PySide6 6.11 do not install on 3.15 yet. The code was
modernised for 3.14 by ruff's upgrade rules (built-in generics, `X | None`,
`datetime.UTC`); nothing it computes changes.

- **A software-in-the-loop run on Windows no longer stops while the
  flight software is still answering:** when the flight software fell
  thousands of steps behind (steps past their deadline), the run could
  stop with "the flight software took no STEP for 10 s" although it was
  answering all the while: the send's time limit counted only bytes the
  program took, and Windows lets a full socket take nothing for longer.
  Bytes it sends now count too; a program that neither reads nor answers
  still stops the run after the step timeout.
- **The propellant budget no longer overestimates propellant:** each
  contributor took the phase's starting mass times `exp(dV / Ve) - 1`,
  the rocket equation's form for the mass *after* a burn. Each now takes
  the mass before it, `m * (1 - exp(-dV / Ve))`, in order. For 150 kg
  dry at Isp 220 s, a 100 m/s transfer was budgeted 5 % too high and a
  1 km/s transfer 2.5 times too high (232 kg, now 93 kg); from about
  1.4 km/s there was no total at all ("did not settle"). Every budget
  with a burn comes out lower; the larger the delta-V, the larger the
  change (5 % at 100 m/s). Found by the audit of 2026-10-27.
- **Lifetime, End of Life and the budget's disposal are right at the
  critical inclination:** the J2 mean elements they start from came from
  a first-order map that is singular at 63.435 deg and 116.565 deg. A
  600 km orbit there was reported to re-enter at once ("0.00 years,
  5-year rule: met"), and a Molniya orbit stopped with an error. The map
  is now blended from its values at the edges of a 1 deg band around
  those values: the same orbit stays up for over 30 years, as at 60 deg,
  and a 300 km decay at 63.435 deg is estimated at 34.8 days, as a full
  Basilisk run finds. The mean-element plots there are finite too. Results elsewhere are
  unchanged. Found by the audit of 2026-10-27.
- **Save no longer writes over a built-in template:** after opening a
  template from Home, **Save** (Ctrl+S) wrote to the template's own file
  (where the folder is writable: a Windows install, or from source). It
  now opens **Save As**, starting in the home folder under the
  template's name, and a save into the templates folder is refused. The
  User Manual already said a template is never overwritten. Found by the
  audit of 2026-10-27.
- **A run outside the Earth orientation files no longer ends the
  program:** a run whose dates the installed IERS files do not cover
  (an epoch before 1962, or after 2027 with only the high-precision file)
  stopped inside SPICE, taking the window and any unsaved edits with it.
  The files are now used only for a run they cover; otherwise the run
  uses the IAU model, and both **validate** and the run say so ("the
  installed IERS files cover 1962-01-19 to 2126-11-03, not this run"). A
  Mission Sequence that would propagate past the files' end stops with a
  message instead. Found by the audit of 2026-10-27.
- **Limits a shared scenario cannot get round:** an `if` or `while`
  condition can no longer format a text with `%` (a field width built a
  text of any length, up to gigabytes); `%` on numbers is still the
  remainder. A Monte Carlo batch is limited to 100 000 runs and 256
  processes, and uses at most one process per CPU (the Overview says so
  when it asks for more). Found by the audit of 2026-10-27.
- **The script-block consent shows all of the code:** **Run script
  blocks?** listed only the first 600 characters of each block, with no
  sign of the cut, and Yes ran all of it. **Show Details...** now lists
  every block in full, with its length and SHA-256.
- **Generated constellations and formations keep their spacing:** when
  the scenario's gravity includes J2 (degree 2 or more), **Generate
  Walker constellation...**, **Generate phasing formation...** and their
  command-line versions now place each satellite by its mean elements
  (stored as osculating elements with a true anomaly). With equal
  osculating elements, as before, two Walker satellites 90 deg apart at
  550 km closed to 76 deg in a day, and a 50 km phasing follower was at
  38 km. With point-mass gravity nothing changes. Templates 04 and 05
  are unchanged. Found by the audit of 2026-10-27.
- **Mean elements for equatorial orbits:** the J2 mean-element map no
  longer divides by zero at 0 deg inclination, and is continuous across
  the critical inclination.
- **Long dynamics steps are more accurate, and flagged:** the rkf45 and
  rkf78 integrators kept Basilisk's default error tolerance (relative
  1e-4), which let a long step through unchecked: a one-day two-body
  orbit was 384 m off Kepler's solution at a 300 s step and 173 km at
  1800 s. They now work to a relative error of 1e-10 (11 m and 8.6 km),
  and the run's provenance records both tolerances. Above a 60 s step the
  rest of the error comes from what is refreshed only once per step, so
  Explain and `validate` now warn there. Found by the audit of
  2026-10-27. 28 of the 31 templates give the same results to the last
  digit; the three that fire attitude thrusters (11, 12, 17) change.
  Their 20-40 ms pulses fall inside a 0.5-1 s step, and the default
  tolerance stepped over most of them: template 17's fuel tank drained
  0.3 g where it drains about 14 g (13.6 g at 1e-12), and its description
  now says so. 12's wheel speeds and 17's attitude are now closer to a run
  at 1e-12; 11 is as close as before.
- **Each sensor draws its own noise:** every sensor noise model kept
  Basilisk's default seed, so they all drew the same random sequence: two
  identical noisy sun sensors on one spacecraft gave identical readings
  (their noise correlated at 1.0), and the noise repeated across sensors,
  spacecraft and the segments of a long run. Each model now gets its own
  seed, derived from a new scenario setting, **Random seed**
  (`sim_settings.seed`, default 0), and its name; the twin sensors' noise
  now correlates at 0.03. The same scenario still gives the same run; a
  navigation error's own seed is kept. The run's provenance lists every
  seed. In the templates only noisy sensor readings change (07, 20, 23,
  26, 27, 28); everything else, the attitude included, is the same to the
  last digit. Two Monte Carlo batches still draw the same samples: that
  seeding is in Basilisk (known issue K-24). Found by the audit of
  2026-10-27.
- **Known vulnerabilities checked in CI:** the installers shipped
  certifi 2026.7.22 and pillow 12.2.0, which pip-audit matched to 1 and 52
  published advisories. certifi is now 2026.10.23, with none. pillow stays
  at 12.2.0: the qualified Basilisk (2.12.0) allows no later version. Its
  52 advisories are all about decoding a crafted image, and nothing in
  SpaceMissionStudio or the Basilisk modules it uses decodes an image
  with pillow (known issue K-25). CI now checks every pinned package, and
  every tool it runs, against those advisory databases and fails on any
  match not listed, with its reason, in `packaging/audit-exceptions.txt`;
  the tools themselves (pytest and its plugins, ruff, pip-audit,
  pre-commit) are pinned in `packaging/constraints-dev.txt`, and the main
  workflow is read-only. The release workflow runs the whole test suite
  on the tag before it attaches anything. The `.deb`'s copyright file now
  names each part it bundles with its own licence (CPython, Qt, the
  fonts, the icons, the reference data) and this repository as the
  source. Found by the audit of 2026-10-27.
- **Save from the unsaved-changes question:** closing, opening or
  starting a scenario with unsaved changes offered only Discard and
  Cancel; it now offers Save too (the default), which saves the scenario
  (asking where for one with no file) and then goes ahead. A cancelled
  Save As keeps the window and the changes.
- **A failed read of the reference data is reported:** if the start-up
  read of the reference data files failed, the Reference data panel kept
  "Reading the reference data files..." for good. It now says why, with a
  Retry button, and the status bar shows "Reference data: not read".
- **No held space weather after the Duration:** a Mission Sequence can
  run longer than the scenario's Duration, but the space weather its drag
  reads was loaded only for the Duration and 10 days either side. Past
  that, Basilisk held the last day's values, for as long as the run went
  on, with nothing in the results to say so (a 15-day sequence in a
  0.1-day Duration: 5 days on held values). Such a run now stops before
  it goes there, with a message to set the Duration to cover the
  sequence. Runs inside the loaded days, and every template, are
  unchanged.

## 1.3.1 (2026-10-27)

A faster window. Changing the theme, opening a template and the end of
the first run each held the window noticeably; this release shortens all
three. Nothing the tool computes changes: scenario files, the command
line, every exported file and every result are the same as with 1.3.0.

- **A faster theme switch, again:** a message about a spacecraft whose
  page had not been opened was worded from a hidden spacecraft form, kept
  for the session once any template from 08 on was opened: about 1,000
  widgets that every theme switch restyled. The titles are now read from
  such a form once, kept as text, and the form deleted. A switch takes
  about 0.36 s where it took 0.53 s (all templates opened, then template
  23); the messages read as before.
- **Opening a template is faster:** 72-134 ms where it took 82-459 ms
  (the median of the 31 templates 94 ms, was 111). A scenario loaded is
  checked once instead of four times; the titles for messages about a
  spacecraft are read once start-up has settled, a part of the form per
  moment, instead of all at once (0.4 s) when the first such message
  appeared (template 08); the check of the space-weather data's dates no
  longer looks through all 25,000 days on every edit.
- **The first run's end no longer pauses:** the first run of a session
  held the window 0.2-0.3 s while its first plot was drawn, the time
  plotly takes to load its figure classes on first use. They are now
  loaded in the background once start-up has settled; the longest pause
  at the end of a run is 27-38 ms, first run or not.

### Who should update

- Everyone who uses the window: it pauses less. On Linux,
  `apt install ./spacemissionstudio_1.3.1_amd64.deb` replaces the 1.3.0
  package; on Windows, run the 1.3.1 setup over 1.3.0.
- Scripts and pipelines that use only the command line gain nothing from
  this release.

### Known limits

- Some actions still hold the window for longer than the 50 ms the
  interface aims at: changing the theme (about 0.4 s), the first visit to
  a spacecraft page (0.15-0.2 s) and opening a template (0.07-0.13 s)
  (SRelD K-19, K-23). A run that ends in the first seconds after start-up
  can still pause for up to 0.3 s.
- On Windows, a software-in-the-loop session that drops thousands of
  steps may stop with "the flight software took no STEP for 10 s". Seen
  only in CI, cause not known (SRelD K-14).

## 1.3.0 (2026-10-26)

A new interface. The window has a navigation rail in place of menus and
toolbars, a command palette (`Ctrl+K`), a Problems panel and an inspector;
forms show units in their fields and edit in place; Results opens on an
overview of the run; tables copy, sort and filter alike; the Timeline
takes a year of events; Reports lists every export; Settings adds the UI
scale, reduce motion and the Vizard location. What the tool computes, its
files, its command line and every file it writes are unchanged (the
exports are tested byte for byte against 1.1.0 and 1.2.0). It starts
faster than the interface before it and switches theme, plots and pages
with shorter pauses; `docs/ui/BEFORE_AFTER.md` has the measurements,
including the ones that did not meet their target. Scenario files are
the same as with 1.2.0, and so are their results, except drag on dates
the refreshed space weather changed (below).

- **A new shell: a navigation rail instead of menus and toolbars** (UI
  overhaul M2a). The window has no menu bar and no toolbar any more:
  - **The rail** on the left holds the areas: **Home** (Start from
    scratch and the templates), **Scenario** (the scenario tree),
    **Run** (the run controls, End of Life, Budget and the Log),
    **Results** (Plots, Dashboard, Output, Monte Carlo and Compare),
    **Timeline** (the events), **Reports** (Flight Software), and at the
    bottom **Settings** and **Help**. `Ctrl+1` to `Ctrl+6` open the six
    areas; the rail's last button shows them as icons only.
  - **The top bar** has the scenario's name and state, where you are
    ("Scenario › Spacecraft › sat-1"), Undo and Redo, a save button that
    shows the save state, **Run** with its mode, and the search field of
    the command palette.
  - **Every command** is in one registry: the command palette (`Ctrl+K`),
    the area headers, the top bar, the shortcut list and every tooltip
    ("Save (Ctrl+S)") come from it. The palette also finds a command by
    its old name ("events" finds the Timeline), the spacecraft and
    ground stations, and the Settings sections.
  - **Settings** holds the theme, the reference data, the layout, the
    keyboard shortcuts (`Ctrl+/`) and About; they were in the View and
    Help menus.
  - New shortcuts: `Ctrl+I` the Inspector, `Ctrl+J` Problems.

  The screens themselves are unchanged; what a run computes and every
  file the app writes are the same.

- **Problems at the bottom, the run in the status bar** (UI overhaul M2b):
  - **The Problems panel** is a table at the bottom of the window
    (`Ctrl+J`): severity, the field it is about, the object (scenario,
    spacecraft, ground station, ...) and the message. Errors come first,
    a column heading sorts by it, `Ctrl+C` copies the selected rows, and
    `Enter` or a double-click goes to the field. The status bar always
    counts the errors and warnings, and the top bar shows the count while
    there are any; a click on either opens the panel.
  - **The run** shows in the status bar: what it is doing, its progress,
    the time so far and left, **Cancel** (`Esc`) and its state ("Run 2:
    done in 6 s").
  - **Inspector and Explain** are two panels on the right, one above the
    other, instead of tabs. `Ctrl+I` shows and hides the Inspector.
  - **The layout is kept for each scenario file:** the panels, the rail
    and the dividers come back when you open the file again.

  A layout saved by an earlier version is ignored once.

- **Home: template cards, recent scenarios, no start-up dialog** (UI
  overhaul M3):
  - **A card per template** says what the template is, all read from
    the template file: Orbit only or Full attitude (with its pointing
    mode) and how many spacecraft; the central body and the orbit
    ("Earth · 550 km circular · i 97.6 deg · Sun-synchronous"); and the
    first sentence of its description. A filter narrows the cards. Click
    a card for its whole description, with **Open template** and
    **Customize...**; each card has its own **Open** and
    **Customize...** too. The keyboard reaches the cards with `Tab`, the
    arrow keys move between them and `Enter` opens one.
  - **Recent scenarios:** the last 10 scenario files you opened or saved,
    newest first. A file that was moved or deleted is marked
    "(missing)". `Delete` takes one off the list and **Clear** empties
    it.
  - **New blank scenario** and **Open a scenario file...** are beside
    them.
  - **No dialog at start-up:** the question whether to fetch or update
    the reference data is a card at the top of Home, with the same
    choices. **Fetch now** downloads while you carry on; **Not now**
    downloads nothing.
  - Templates 22, 26 and 29 named the Events tab in their descriptions;
    they name the Timeline now.

  What a run computes and every file the app writes are the same.

- **Forms: units in the fields, optional groups that fold away** (UI
  overhaul M4a):
  - **Every number shows its unit after it**, right-aligned: "550.0 km",
    "97.59°", "1.000 m²", "300.00 Wh". Labels are the name alone. Messages
    still name a field with its unit, "Dry mass [kg]".
  - **An optional group** (Station keeping, Power budget, ROE formation,
    ...) **shows only its title while it is off**, instead of every field
    greyed out; Monte Carlo off says what turning it on does.
  - **No page of the Scenario editor scrolls sideways** in a 1280 px
    window with the inspector open: long rows put their field under the
    label, and rows of buttons wrap. The Power page and the Spacecraft
    page did scroll.
  - The Customize wizard shows its units the same way.

  Every value and every file the app writes are the same: each template
  is written back byte for byte after every page has been shown.

- **Editing without dialogs; Explain as the scenario's Overview** (UI
  overhaul M4b):
  - **Explain is Scenario › Overview**, the first node of the scenario
    tree, instead of a panel beside the inspector. It follows an edit a
    quarter of a second after you stop typing and is worked out in the
    background, so typing never waits for it. Its name says what there is
    to check: "Overview (1 to check)". View › Explain opens it.
  - **Form · JSON**, at the top of the Scenario area, replaces the tree's
    JSON page. Back to Form applies the text, and is refused while it does
    not parse or validate; **Discard** puts the scenario's text back.
  - **Devices and dispersions are edited under their list**, as you type,
    instead of in a dialog. A value that does not apply (a name already
    taken) is not applied, and the form says why.
  - **Add** adds a spacecraft, ground station, device or dispersion at
    once and opens it. Remove or Undo take it back.
  - A closed window no longer autosaves.

  What a run computes and every file the app writes are unchanged.

- **Run › History and a record of every run** (UI overhaul M5a):
  - **History**, in the Run area, lists every run, newest first: its
    status (Done, Cancelled, Failed), mode, start (UTC), how long it took
    and whether it is saved, with its provenance one click away. Failed
    runs and Monte Carlo batches are listed for the session they ran in.
  - **The Log records each run:** its start, its end and length, its
    warnings, and where it is saved. **Copy** copies what it shows.
  - **The end of a run waits less:** the run is saved, and old runs
    pruned, in the background; the plots are drawn once, and Compare when
    it is opened. On template 23 the window is held about half as long
    (152-163 ms, was 301-323 ms).

  What a run computes and every file the app writes are unchanged.

- **The run options on one page** (UI overhaul M5b):
  - **The run mode** is a segmented control in the Run area's header,
    **Single · Monte Carlo · SIL**; the top bar keeps its menu beside Run.
  - **Run › Run**, the Run area's first page, holds what the next run
    uses, for the mode chosen, and applies each change at once:
    **Live plot** and the **Vizard** options (they were a dialog) for a
    single run and a SIL run; the **archive folder** of a Monte Carlo
    batch, with Browse..., remembered for each scenario (left empty, Run
    asks for one, as before); the **spacecraft and program** of a SIL run
    (they were two dialogs). The overwrite question for an earlier batch
    stays.

  What a run computes and every file the app writes are unchanged.

- **Results › Overview, and plots that switch at once** (UI overhaul M6a):
  - **Overview**, the first view of Results, shows the run's headline
    figures as cards (delta-V, propellant, link margin, battery, passes,
    eclipses, data downlinked, ...). A card turns red, with an icon and its
    reason, only for a link margin below 0 dB or an empty battery.
    **Provenance** shows what produced the run.
  - **Plots** stay in one page: plotly.js is loaded once, and showing
    another plot, changing the layout or the time axis redraws in place.
    A plot appears about four times sooner (about 110 ms, was about
    415 ms on template 23), and switching holds the window at most
    35 ms (was up to 304 ms).
  - Shorter pauses now and then: Python's full garbage collections no
    longer walk everything start-up made (one took about 0.2 s; after a
    run, about 0.07 s is left).

  What a run computes and every file the app writes are unchanged.

- **One kind of table, and a shorter end of a run** (UI overhaul M6b):
  - The tables of Output, Monte Carlo, Compare and Budget work alike:
    `Ctrl+C` copies the rows as tab-separated text with the headings,
    right-clicking a heading shows or hides its column, numbers are
    right-aligned with their unit in the heading.
  - The end of a run is shown in steps, and the run is saved a moment
    after: each step holds the window 17-36 ms, where the whole end of a
    run held it 100-130 ms on template 23 (the longest pause after a run
    is now about 50 ms, more when Python collects garbage then).

  What a run computes and every file the app writes are unchanged.

- **A Timeline for long runs** (UI overhaul M7):
  - Ten thousand events (a year of passes) show, filter and sort without
    a pause: about 40 ms at most (it was 0.7 s to show them and over 2 s a
    search keystroke).
  - The axis is in UTC with `Z` ("08:00Z", the date at midnight) when the
    run has an epoch.
  - Move along it with Shift+wheel, the arrow keys or a right-button
    drag; zoom with the wheel or `+` and `-`; `0` fits the whole run.

  What a run computes and every file the app writes are unchanged.

- **Every export in one place; three new settings** (UI overhaul M8):
  - **Reports › Exports** lists every file the app writes, with its
    format, the view and button that make it, its default destination,
    the provenance written with it and when this computer last wrote one
    (UTC). A double-click opens the view that makes it.
  - The exported files are the same as 1.1.0's, byte for byte: a new test
    writes each of them (the results, events, mission output, Monte
    Carlo and budget CSVs, the `.obj` model, the SIL report) and compares
    them with the files 1.1.0 wrote. PNG and SVG plots, the
    flight-software project and the Vizard file are not in it (the web
    engine draws the plots; the project has its own test against
    Basilisk; Basilisk writes the Vizard file).
  - **Settings › Appearance:** the **UI scale** (90, 100, 110 or 125 %,
    from the next start) and **Reduce motion** (notifications appear and
    go without their 150 ms fade). **Settings › Vizard:** the Vizard
    program, with **Browse...** and **Clear**.

  What a run computes and every file the app writes are unchanged.

- **A faster start, and every area by keyboard** (UI overhaul M9):
  - The window appears in about 1.9 s where it took 2.5-2.8 s on the
    same machine before the overhaul: the reference data files are read
    in the background, and the status bar fills in a moment later.
  - Tab reaches every control of every area. It could not leave the
    scenario's description before (Tab typed into it); now it moves on,
    as it does from read-only tables.
  - The spacecraft page and the spacecraft editor open faster (456 and
    381 ms, from 541 and 415 ms), though still not at once.
- **The documentation follows the new interface:** the User Manual, the
  how-to guides, the READMEs, the FAQ, troubleshooting, tips, the
  glossary, the template catalog and the user manual of the compliance
  set name the areas and pages of 1.3.0 (no more menus, Explain is
  **Scenario > Overview**, a spacecraft's parts are pages of the
  scenario tree); 31 templates, not 28 or 29. Template 22's description
  and two notes in the window said the same.
- **Fixed:** `Alt+Backspace` did nothing once there was an edit to undo:
  it was both Clear Time Cursor's key and, on Linux and Windows, one of
  Undo's. It is Clear Time Cursor's alone now; Undo keeps `Ctrl+Z`. The
  support-data error and the Earth orientation warning name **Settings >
  Reference data**, no longer a Tools menu.
- **A faster theme switch:** every switch restyled every widget twice
  (the Fusion style was set again before the new style sheet); it now
  does so once, which halves it: about 1 s where it was 2 s with a
  template run and the spacecraft editor opened, about 0.5 s otherwise.
- **A spacecraft's page opens faster:** it builds its Orbit / mass section
  first and the others just after, one at a time, so the first visit
  pauses for about 0.16 s where it took 0.4 s.
- **Bundled space weather refreshed:** CelesTrak's `SW-All.txt` updated
  2026-10-25 23:32 UTC, observations to 2026-10-24 and its daily forecast
  to 2026-12-07 (it was 2026-10-18 and 2026-12-02). CelesTrak revised its
  values from 2026-09-09 on and the first two months of the monthly
  forecast (2027-01, 2027-02), so drag on those dates changes; runs that
  start later, such as every template (2030), do not. NASA MSFC's
  October 2026 prediction is unchanged.

### Who should update

- Everyone who uses the window: the interface is new throughout (the
  User Manual shows it). Nothing 1.2.0 computes changes: scenario files,
  the command line and every exported file are the same, and so are
  results, except drag on dates the refreshed space weather changed
  (2026-09-09 to 2026-12-07, and 2027-01 to 2027-02).
- On Linux, `apt install ./spacemissionstudio_1.3.0_amd64.deb` replaces
  the 1.2.0 package; on Windows, run the 1.3.0 setup over 1.2.0.
- Scripts and pipelines that use only the command line gain nothing from
  this release.

### Known limits

- Some actions still hold the window for longer than the 50 ms the
  interface aims at: changing the theme (0.5-1 s), opening a template
  (0.2-0.5 s), the first visit to a spacecraft page (0.15-0.2 s) and the end
  of a run (0.5 s) (SRelD K-19, K-23).
- On Windows, a software-in-the-loop session that drops thousands of
  steps may stop with "the flight software took no STEP for 10 s". Seen
  only in CI, cause not known (SRelD K-14).

## 1.2.0 (2026-10-21)

Starting a mission from an empty scenario is now a choice of its own: the
Templates page opens with a blank scenario, and its Scenario page shows
the steps to a first run and everything else the tool does, each with a
button to where it is set. The calculations are unchanged, so scenario
files and their results are the same as with 1.1.1. The installers are
built as 1.1.1's were, with the same Python, Basilisk and space weather;
the Earth orientation files in them are as current as their build.

SpaceMissionStudio supports Linux and Windows. macOS, which never had an
installer, is no longer supported.

- **Starting a mission from scratch, guided.** The Templates page now
  opens with **Start from scratch** (**New blank scenario**), above the
  templates; before, an empty scenario was only File > New Scenario. A
  blank scenario starts in *Orbit only*, the simplest mode, and its
  Scenario page has a **Build your mission** guide:
  - the steps to a first run (Scenario, Environment, Spacecraft, Ground
    stations, Run), each with its state (*Needed*, *Optional*, *Done*,
    *Ready*) and a button to its page;
  - **There is more**: Full attitude (with **Switch to Full attitude**),
    the mission sequence, constellations and formations, Monte Carlo, the
    analyses, other central bodies and the worked examples, each with a
    button to where it is.

  The guide is open for a scenario without spacecraft and folded (**Show
  guide**) for an opened one. The Spacecraft page says what to do while
  it has no spacecraft, with **Add...** as its primary button, and Edit
  and Remove wait for a selection. A hint that pointed to a "Spacecraft >
  Add..." menu, which does not exist, now names the Spacecraft page.
- **macOS is no longer supported.** SpaceMissionStudio runs on Linux and
  Windows. The macOS CI job and the release workflow's macOS check are
  gone, and so is the app's macOS-only code: downloading Vizard for
  macOS and starting it from its `.app` bundle. The documents now name
  Linux and Windows only (`docs/DECISIONS.md`, "macOS removed").
- **Clearer release notes.** A release draft now opens with what the
  release is for, then who should update, the downloads with their sizes,
  how to install or upgrade on each system, how to check a download (with
  the installers' SHA-256), what is new, what the installers contain, how
  the files were checked, and the known limits. Before, it was the
  CHANGELOG entry under a few file lines. Written by
  `packaging/release_notes.py` (`docs/developer/releasing.md`).

### Who should update

- Anyone who builds missions from an empty scenario: the guide shows the
  steps and the rest of the tool.
- Everyone else when convenient: nothing 1.1.1 computes changes. On
  Linux, `apt install ./spacemissionstudio_1.2.0_amd64.deb` replaces the
  1.1.1 package (1.1.1 was tested offline the same way over 1.1.0). On
  Windows, run the 1.2.0 setup over 1.1.1.

### Known limits

- On Windows, a software-in-the-loop session that drops thousands of
  steps may stop with "the flight software took no STEP for 10 s". Seen
  only in CI, cause not known (SRelD K-14).
- A theme change takes about half a second, up to 2.4 s after every page
  has been visited (SRelD K-19).

## 1.1.1 (2026-10-21)

The installers bring everything with them; the app itself is unchanged,
so scenario files and results are the same as with 1.1.0. On Linux,
`apt install ./spacemissionstudio_1.1.1_amd64.deb` replaces the 1.1.0
package (tested offline over it, in a container); on Windows, running the
1.1.1 setup over 1.1.0 removes 1.1.0's environment first (not yet tried
on a Windows machine).

- **Self-contained installers.** The Linux `.deb` and the Windows setup
  program now bring their own Python 3.11 with Basilisk 2.12.0, PySide6
  and every other package, plus the support data (SPICE kernels, gravity
  fields, magnetic field model, albedo maps) and the Earth orientation
  files. Installing needs no Python on the computer and no internet: the
  1.1.0 setup program stopped with "needs Python 3.11 or later" when
  none was on `PATH`, and both 1.1.0 installers downloaded Basilisk and
  the data while installing. The `.deb` is now
  `spacemissionstudio_<version>_amd64.deb` (about 450 MB; 1.65 GB
  installed) and needs glibc 2.34 or newer (Ubuntu 22.04, Debian 12 or
  later). Built by `packaging/bundle_python.py`; the release workflow
  installs the `.deb` with the network cut off and runs it offline, and
  the Windows setup with an empty support-data cache.
- **A test fixed:** `test_autosave.py` failed now and then on Windows CI
  when an earlier GUI test had left a main window open: its autosave
  timer wrote into the recovery file the test had just pointed at a
  temporary folder. The test now stops such timers first
  (`docs/ui/TEST_CHANGES.md`).

## 1.1.0 (2026-10-20)

A new look whose theme switches live, formations in relative orbital
elements, navigation from a camera (around Mars, and around asteroid Eros
from its landmarks), Eros itself, reflected sunlight on the sun sensors
and Mars's gravity field, plus fixes found along the way. Scenario files
of 1.0.0 open unchanged, and `apt` and `pip` upgrade 1.0.0 in place. 31
templates (three new: 29, 30, 31). Linux, like 1.0.0. Details below,
newest first; the full story of each is in [`HISTORY.md`](HISTORY.md).

- **A new look, and the theme switches live (UI overhaul M1).** The IBM
  Carbon theme and IBM Plex are replaced by the token set of the overhaul
  brief (`docs/ui/UI_OVERHAUL.md`): neutral surfaces with one blue
  accent, Inter for the interface and JetBrains Mono for values and code
  (both bundled), Lucide icons tinted from the theme, 6 and 8 px corners,
  frameless group boxes. Status keeps one meaning (critical, serious,
  caution, normal, standby, off) and is always written out. Every text
  and icon colour passes WCAG 2.2 AA in both themes, tested. View > Theme
  now applies at once to every open view, plots included, instead of at
  the next start; with System it follows the desktop while the app runs.
  Plots take a template from the theme and a new eight-colour palette,
  checked for colour-vision deficiency between neighbouring series and
  kept apart from every status colour. Applying a theme takes 0.5 s on a
  new window and 2.4 s after every page has been visited (the earlier
  restyle: 1.3 s and 6.1-6.5 s on the same machine), not yet the brief's
  0.1 s; the overhaul's next steps reduce the number of live widgets
  (`docs/ui/UI_OVERHAUL_PLAN.md`). The layout, what the tool computes,
  its files and its command line are unchanged. Decisions:
  `docs/DECISIONS.md`; licences: `docs/THIRD_PARTY_ASSETS.md`.
- **Monte Carlo from the GUI works with one thread.** With `thread_count`
  1, the default and template 09's setting, every run of a GUI batch
  failed ("signal only works in main thread"). Basilisk's Monte Carlo
  controller needs a main thread, and the GUI ran the batch on a worker
  thread. The GUI now runs the batch in a child process. The command line
  was not affected (it runs on its main thread), and batch results are
  unchanged.
- **Bundled space weather refreshed:** CelesTrak's observations to
  2026-10-18 and its daily forecast to 2026-12-02 (was: to 2026-10-11).
  Drag runs dated after 2026-10-11 change slightly.
- **The command line refuses `nan` and `inf`** for every number option,
  with a usage message; some of them ended in a Basilisk traceback.
  `generate-roe-formation --safe` refuses negative sizes.
- **The spacecraft editor's Power tab fits a 1280 px window** with an ROE
  formation (it scrolled sideways).
- **Mars gravity field.** Spherical-harmonics gravity now works around
  Mars too, with the GGM2B field from Basilisk's data up to degree 80
  (gravity settings: **Enable spherical-harmonics gravity (Earth, Mars)**).
  Every field now uses the reference radius of its own file: Basilisk
  put the planet's radius in its place, which made Mars's J2 0.05 % too
  weak (Earth's 1e-7). A 400 km Earth orbit with a degree-20 field
  moves by about 0.16 m in a day.
- **Albedo on the sun sensors.** With **Reflected sunlight on the sun
  sensors** (gravity settings), coarse sun sensors around Earth or Mars
  also see the sunlight the planet reflects, from Basilisk's albedo module
  with the measured CERES (Earth) or TES (Mars) albedo map. An
  Earth-facing sensor can see a quarter of the direct sunlight; in
  template 14 it pulls the estimated Sun direction about 16 deg off.
  Each sensor's albedo is plotted.
- **Sun sensors are dark in eclipse.** Coarse sun sensors read the Sun
  through the Earth in its shadow, and the sun heading estimated from them
  stayed right. They now read zero there, as real sensors do: the
  estimate is lost in the shadow and back when the spacecraft leaves it.
  Template 14 now runs for a whole orbit and shows this.
- **Thermal sensors away from Earth.** A thermal sensor took the
  sunlight at Earth's distance from the Sun whatever the spacecraft
  orbited, so around Mars it absorbed about twice the real sunlight, and
  around Venus too little. It now takes the sunlight at the spacecraft's
  own distance from the Sun. Runs around Earth and the Moon are
  unchanged.
- **Asteroid 433 Eros as a central body.** Its real position (a JPL
  Horizons solution from NAIF, 1900 to 2100), its 5.27 h rotation and,
  with **Gravity from the shape model**, the gravity of its NEAR shape
  (Basilisk's polyhedral gravity) instead of a point mass. Download the
  two files in Reference data (**Small bodies**). Positions are also given
  in Eros's frame, and an orbit into the asteroid is reported as an impact.
- **Landmark navigation.** A spacecraft around Eros can carry a camera
  that sees landmarks on the surface (Basilisk's `pinholeCamera`), and a
  Kalman filter estimates its orbit from their pixels. New template 31:
  from 100 m off to 0.35 m (median) in a 35 km orbit. A how-to page
  explains the settings and the results.
- **SIL runs no longer stop when the simulator itself stalls.** A send to the
  flight software gave up as soon as its time ran out, even when the flight
  software was taking data and only the simulator had been slow (a loaded
  computer, a debugger). It now counts from the last data taken and tries once
  more before reporting that the flight software took nothing.
- **Optical navigation.** A spacecraft can carry a camera that sees the
  central body (Earth, Mars or Jupiter) and estimate its own orbit from
  where the planet's disk falls in each image and how large it is, with
  Basilisk's `pixelLineConverter` and `relativeODuKF`. Images from the night
  side are left out. New template 30 navigates around Mars: from 68 km off
  to within 2 km in a day. A how-to page explains the settings and the
  results.
- **Template 29's note** no longer says the ROE guidance has no
  differential drag: it compensates it now (below).
- **Runs around Mars and Jupiter work.** A scenario around `mars` or
  `jupiter` (or with them as third bodies) passed its checks and then
  failed: around Mars the whole app closed. The bundled planet ephemeris
  has the Mars and Jupiter system barycentres only, so the app now offers
  **mars barycenter** and **jupiter barycenter** and tells you to use them
  when a file names the old ones.
- **ROE formations compensate differential drag.** When a follower feels
  more or less drag than its chief, the impulsive law measures how fast
  their relative semi-major axis decays and sets it so the along-track
  offset swings evenly about its target between corrections. With three
  times the chief's drag area, a 3-day hold stays within 13 m along-track
  (27 m before) for half the burns and less delta-V. On by default
  (**Compensate differential drag**); twin spacecraft fly as before. The
  Explain tab says when a follower's drag differs from its chief's.
- **ROE formations in Vizard.** A follower in an ROE formation gets live
  panels for its delta-V, its radial, along-track and cross-track
  separation from the chief, and its closest radial/cross-track
  approach.
- **Altitude trade errors keep their message.** When Basilisk stopped
  one of the parallel workers with an error, the trade failed with a
  pickling error that hid it. It now names the altitude and Basilisk's
  message. Two workers writing the same space-weather window no longer
  replace each other's file.
- **Relative orbital elements (third part): the generator, the diagram
  and template 29.** **Generate ROE formation...** under the Spacecraft
  list adds a follower placed on a passively safe helix or on six typed
  ROE, with the closest approach shown as you type. The Explain tab draws
  each target's eccentricity and inclination vectors and the path around
  the chief. New template 29 moves a follower from 2 km behind its chief
  to a passively safe 300 m helix. A how-to page, a User Manual section
  and glossary entries explain ROE and passive safety.
- **Relative orbital elements (second part): ROE formations fly.** A
  follower holds, or moves between, its ROE targets with either law:
  - *impulsive*: the tool's own guidance plans along-track and
    cross-track burns with the J2 model, avoids eclipse, splits long
    burns, and drifts to the along-track offset, gliding in so it does
    not overshoot;
  - *continuous*: Basilisk's `meanOEFeedback` with the ROE target as its
    element target (default gain 25000; phasing keeping's 2500 lets
    metre-scale errors grow).

  Results gain `{spacecraft}.roe_formation.*` series, the Events tab
  shows ROE burns and drifts, the budget counts their delta-V as
  formation keeping, and Explain describes each target and its
  passive-safety margin. New command `generate-roe-formation` places a
  follower at the requested ROE from the chief's mean elements.
- **Relative orbital elements (first part):** a follower's scenario
  file can describe a formation in quasi-nonsingular relative orbital
  elements (ROE, in metres), with a schedule of targets, and the
  spacecraft editor has a form for it with a passively safe formation
  helper. The math (the J2 state transition matrix, the impulsive burns,
  the passive-safety margin) is in place and tested.
- **Documentation brought up to date with the app:** menu, tab and page
  names (End of Life, Budget and Flight Software are pages under
  Analyses and Tools; the Data tab is now the Reference data dialog;
  Monte Carlo runs from the run mode beside Run), the template count
  (then 28), sample command output, and the records of the published 1.0.0
  release.
- **Messages and tooltips** that named the old Data tab or Run Monte
  Carlo... now name the Reference data dialog and the Monte Carlo run
  mode.

## 1.0.0 (2026-10-14)

The first release of the renewed SpaceMissionStudio. The version numbers
used before the renewal are withdrawn; how the tool got here is in
[`HISTORY.md`](HISTORY.md).

**What it does** (details: [Capabilities](docs/reference/capabilities.md))
- **Scenarios** in a versioned JSON format, edited in a tree of forms
  that check values as you type and name each problem by its form label;
  28 templates to start from, from a blank scenario to formations, a
  constellation and an octagonal bus built from a 3D model.
- **Simulation on Basilisk 2.12.0**: orbit or full attitude; gravity
  fields, third bodies, drag (NRLMSISE-00 driven by real space weather
  only: CelesTrak's observations and forecast, then NASA MSFC's
  prediction), solar pressure, faceted drag and pressure, flexible solar
  arrays, fuel tanks, sensors and actuators from a catalogue of real
  devices, attitude determination and control, power, sensor
  temperatures, and data handling with ground-station links.
- **Mission design**: a Mission Sequence (propagate, burns, stop
  conditions, reports), station keeping (LEO altitude, GEO longitude and
  inclination), formation flying with Basilisk's formation modules,
  Walker constellations, Lambert transfers, TLE import with SGP4, and
  CCSDS orbit data messages (OPM, OMM, OEM) in and out.
- **Analysis**: plots in a grid with a shared time cursor, events
  (passes, eclipses, burns, modes) on a timeline, run history and run
  comparison, Monte Carlo batches with their statistics, long runs past
  Basilisk's 104-day limit, end of life and deorbit checks, and ESA
  AD10-style delta-V and propellant budgets with launch-delay and
  altitude trades.
- **3D spacecraft models** built from shapes or `.obj` files, giving the
  mass, center of mass, inertia, drag and pressure facets and the
  Vizard look.
- **Flight software export** of the simulated flight software as C, and
  **software in the loop** against your own flight software over a
  documented link.
- **Vizard** visualization, live or saved.
- **The app**: light and dark themes, use by keyboard alone, layouts for
  wide screens, a bundled user manual, and a command line
  (`spacemissionstudio`) for everything that runs without the window.
  Offline by design: nothing is downloaded without your consent.

**Platforms**
- **Linux**: this release. The `.deb`, the wheel and `install.sh` are
  verified (see [`packaging/README.md`](packaging/README.md)).
- **Windows and macOS**: the test suite runs in CI on both. Not yet
  fixed: two intermittent test failures on Windows (an altitude-trade
  worker's error that does not reach the main process, and a software in
  the loop timing test with too small a margin), and on macOS two
  wide-screen layout tests that get a window no wider than the runner's
  screen. Installers for them
  follow in a later release; until then, install from source
  ([Getting started](docs/getting-started.md), path C).

**Coming from a build before the renewal** (3.0.0 or earlier): `pip` and
`apt` see 1.0.0 as older, so remove the old one first
(`sudo apt remove spacemissionstudio`, or `pip uninstall
spacemissionstudio`). Scenario files from it open unchanged.
