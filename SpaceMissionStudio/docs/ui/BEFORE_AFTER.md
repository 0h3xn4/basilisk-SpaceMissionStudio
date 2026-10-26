# Before and after the UI overhaul

What the overhaul (`docs/ui/UI_OVERHAUL_PLAN.md`, M1 to M9) changed, measured
and pictured. "Before" is the code the plan's baseline was taken on
(`66949b4`, the GUI of 1.1.0); "after" is M9 (1.3.0).

## How it was measured

[`scripts/measure_ui_baseline.py`](../../scripts/measure_ui_baseline.py), the
plan's own probe: a 2 ms heartbeat timer on the GUI thread; an interaction's
figure is the longest time the window could not repaint or take input
during it and in the settling time after it. Offscreen, software rendered,
a 1440 x 900 window, the light theme, template 23.

The machine is slower than when the plan was written: the same baseline
code that started in 1.69-1.97 s then starts in 2.50-2.78 s now. So both
were measured on this machine on the same day:
[`perf_baseline_rerun.json`](perf_baseline_rerun.json) (before) and
[`perf_after.json`](perf_after.json) (after). The plan's original figures
are in [`perf_baseline.json`](perf_baseline.json). Each figure is one run;
runs differ by about 10-20 % from each other.

## Start-up

| | Before [ms] | After [ms] |
|---|---:|---:|
| Launch to the first interactive window (three runs) | 2499-2780 | 1853-1871 |
| The main window's constructor | 1783-1928 | 977-1013 |

Met: faster than the baseline. The reference data files are now read in a
child process once the window is up (the status bar fills in about 1.5 s
later), and the space-weather file is parsed in a worker after that: one
stall of about 0.2 s about 1.3 s after the window appears.

## Interactions (the longest stall)

| Interaction | Before [ms] | After [ms] | Under 50 ms |
|---|---:|---:|:---:|
| Live theme switch to dark | 6108 | 2076 | no |
| Live theme switch to light | 6111 | 2121 | no |
| Opening template 23, first time | 170 | 156 | no |
| Opening template 09 (Monte Carlo) | 676 | 463 | no |
| Opening template 23 again | 175 | 222 | no |
| First visit to a spacecraft page | 541 | 456 | no |
| Opening the spacecraft editor dialog | 415 | 381 | no |
| Editing a field, Explain open | 54 | 31 | yes |
| Editing a field, Explain shown | 60 | 22 | yes |
| One keystroke, every template: median | 12.7-63.5 | 9.0-24.0 | yes |
| One keystroke, every template: worst | 97 | 35 | yes |
| Showing plots 1-4 (Results) | 46-52 | 13-26 | yes |
| Searching the plot catalog | 10 | 16 | yes |
| Moving between areas (after: the rail; before: the main tabs) | 5-20 | 17-53 | one of 14 over |
| Results pages | 10-17 | 11-38 | yes |
| Scenario pages other than a spacecraft's first visit | 3-29 | 4-30 | yes |
| A run of template 23 (longest stall during it) | 512 | 474 | no |

Not met, with the measured value: the live theme switch (the whole
application style sheet is applied to every widget, about 2 s), opening a
template (the forms are rebuilt for it), the first visit to a spacecraft
page and the spacecraft editor dialog (a 2,000-line editor built at once;
building its tabs only when shown would mean rewriting it), and the end
of a run (the results and events, and the garbage collector's full
collections after a run, 70-83 ms). Opening template 23 a second time and
moving between areas came out slower than before in this run; the areas
host more than the old tabs did (Results' overview, the Timeline's table).
`docs/DECISIONS.md` (M1-M9) records each of these.

**The spacecraft page after M9 (2026-10-26).** The page builds its
Orbit / mass section when first shown and the other six one per
event-loop turn after it, or when shown or read. The same probe on this
machine: the first visit's longest stall 403 ms before the change, 168
and 157 ms after it (two runs), two stretches over 50 ms each (the first
section, then the largest, Power / propulsion / link budget, about 0.1 s).
Still not met. The theme switch does not change: every section is built
a second later, and Qt restyles them all.

## Other targets of the plan

| Target | Result |
|---|---|
| Plot switch under 50 ms (M6a) | Met: 13-26 ms here, at most 34.4 ms in M6a's own measurement |
| 10,000 events in the Timeline without a stall over 50 ms (M7) | Met: at most 39.4 ms (`scripts/measure_timeline.py`) |
| Export files byte-identical to 1.1.0 (M8) | Met and tested (`tests/gui/test_export_files.py`); PNG, SVG, the flight-software project and the Vizard file are outside that comparison |
| Keyboard-only walk of every area (M9) | Met and tested (`tests/gui/test_keyboard_walk.py`); it found one keyboard trap (the scenario description), now fixed |
| Every text/background pair WCAG 2.2 AA in both themes (M1) | Met and tested (`tests/gui/test_dark_theme.py`) |
| Startup faster than the baseline (M9) | Met: 1.85-1.87 s against 2.50-2.78 s |
| First visit to any page under 50 ms (M9) | Not met: 456 ms for a spacecraft page (157-168 ms after M9, below); every other page 4-30 ms |

## Screens

The screenshot harness ([`scripts/capture_ui_screens.py`](../../scripts/capture_ui_screens.py),
template 23, both themes) took [`screenshots/before/`](screenshots/before/) on
the baseline code and [`screenshots/after/`](screenshots/after/) on M9: 116
and 124 shots per theme, listed in each folder's `INDEX.txt`. The pairs
below are the light theme; the dark theme's have the same names under
`dark/`.

| Screen | Before | After | What changed |
|---|---|---|---|
| Start: the templates | [before](screenshots/before/light/001_start_templates.png) | [after](screenshots/after/light/001_start_templates.png) | Home: template cards, recent scenarios, Start from scratch; the rail on the left |
| The scenario's own page | [before](screenshots/before/light/003_before_run_scenario_scenario.png) | [after](screenshots/after/light/005_before_run_scenario_scenario.png) | Units in the fields, no group boxes |
| A spacecraft: orbit and mass | [before](screenshots/before/light/007_before_run_scenario_spacecraft_smallsat_1_orbit_mass.png) | [after](screenshots/after/light/009_before_run_scenario_spacecraft_smallsat_1_orbit_mass.png) | The tree's sections are its tabs |
| A spacecraft: power, propulsion, link budget | [before](screenshots/before/light/010_before_run_scenario_spacecraft_smallsat_1_power_propulsion_link_budget.png) | [after](screenshots/after/light/012_before_run_scenario_spacecraft_smallsat_1_power_propulsion_link_budget.png) | Optional groups fold to their title while off |
| Explain | [before](screenshots/before/light/066_after_run_side_explain.png) | [after](screenshots/after/light/088_scenario_overview.png) | Explain is the scenario's Overview page |
| The menus | [before](screenshots/before/light/033_menu_run.png) | [after](screenshots/after/light/115_dialog_command_palette.png) | No menu bar: the command palette (Ctrl+K) and each area's commands |
| Results: the plots | [before](screenshots/before/light/059_after_run_results_plots.png) | [after](screenshots/after/light/064_after_run_results_plots.png) | One plot page, switched in place |
| Results: overview | (none) | [after](screenshots/after/light/063_after_run_results_overview.png) | New: the run's headline figures and its provenance |
| Results: dashboard | [before](screenshots/before/light/060_after_run_results_dashboard.png) | [after](screenshots/after/light/065_after_run_results_dashboard.png) |  |
| Results: mission output | [before](screenshots/before/light/061_after_run_results_output.png) | [after](screenshots/after/light/066_after_run_results_output.png) | A DataTable: numbers right-aligned, units in the headings |
| Compare | [before](screenshots/before/light/063_after_run_compare.png) | [after](screenshots/after/light/067_after_run_results_compare.png) | Compare is a view of Results |
| Events, now the Timeline | [before](screenshots/before/light/062_after_run_events.png) | [after](screenshots/after/light/068_after_run_timeline.png) | UTC axis with Z; zoom and pan |
| The log, now Run › Log | [before](screenshots/before/light/064_after_run_log.png) | [after](screenshots/after/light/062_after_run_run_log.png) |  |
| Run history | (none) | [after](screenshots/after/light/061_after_run_run_history.png) | New: every run kept |
| Inspector | [before](screenshots/before/light/065_after_run_side_inspector.png) | [after](screenshots/after/light/072_after_run_panel_inspector.png) | A panel on the right |
| Problems | [before](screenshots/before/light/067_after_run_side_problems.png) | [after](screenshots/after/light/073_after_run_panel_problems.png) | A table at the bottom: severity, ID, object, message |
| Monte Carlo results | [before](screenshots/before/light/079_monte_carlo_results.png) | [after](screenshots/after/light/085_monte_carlo_results.png) |  |
| The scenario as JSON | [before](screenshots/before/light/080_json_view.png) | [after](screenshots/after/light/086_json_view.png) | Form · JSON toggle |
| Keyboard shortcuts | [before](screenshots/before/light/107_dialog_keyboard_shortcuts.png) | [after](screenshots/after/light/116_settings_keyboard_shortcuts.png) | Settings › Keyboard, generated from the commands |
| Reports › Exports | (none) | [after](screenshots/after/light/069_after_run_reports_exports.png) | New: every export, with the time last written |
| Settings | (none) | [after](screenshots/after/light/071_after_run_settings.png) | New: theme, UI scale, reduce motion, Vizard, layout |
| 1280 x 720 | [before](screenshots/before/light/073_window_1280x720_results.png) | [after](screenshots/after/light/079_window_1280x720_results.png) | The smallest supported window |
