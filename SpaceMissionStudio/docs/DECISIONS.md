# Decisions

Choices made where the brief (`docs/ui/UI_OVERHAUL.md`) or the plan
(`docs/ui/UI_OVERHAUL_PLAN.md`) is silent, each with a one-line rationale.
The user's own answers to the plan's questions are in the plan's §9.
Newest milestone first.

## Flight software and navigation rules (2026-10-31)

- **One page for two areas:** `flight_software.*` and `navigation.*`
  share `docs/models/flight-software-and-navigation.md`, as `link.*` and
  `data_handling.*` share theirs: the page is about the onboard chain.
- **The trigger is tested on Basilisk's module:** the case drives
  `thrFiringSchmitt` with four requests and compares the on-times it
  commands, so the test shows each value changes what the thrusters do,
  not only that it was passed.
- **The filter settings are tested on the run's build:** running
  `relativeODuKF` long enough to tell 0.02 from 0.1 would take a full
  optical navigation run per case; the case checks that the run builds
  the filter with the scenario's values. The filter itself is Basilisk's.
- **What cancels is not a parameter:** the focal length cannot change a
  result, so a parameter for it would suggest a choice that has no
  effect. A test shows it cancels.

## The rest of the ROE guidance's rules (2026-10-31)

- **The physics stays in the code:** `1.5 n da` (how fast the mean
  longitude moves for a relative semi-major axis) and `3/4 n da_dot t^2`
  (its drift under a steady decay) are equations, not choices; only the
  thresholds compared with them are parameters.
- **`drag_is_significant` keeps its signature:** `fraction` is optional
  and defaults to the parameter's default, so the ROE math can be called
  without a configuration (its own tests do); the controller passes the
  scenario's value.

## The ROE guidance's rules, as parameters (2026-10-31)

- **Nine now, the rest next:** the guidance's named constants become
  parameters first. The values written inline in the drift logic (its
  slow end, the 1.25 and 1.5 bands, the 60 s earliest look-again, the
  re-plan shift) and `roe.drag_is_significant`'s half tolerance are
  listed on the model page and follow in a second step, so each step
  stays small and its tests specific.
- **Not parameters:** the burn scheduling margins (half a burn part plus
  1 s ahead, 1.5 burn parts apart), the 72-bin eclipse record and
  `follower_orbit`'s six iterations. They keep burns apart and set
  numerical resolution; they are not tuning a project would change.
- **"No derivation recorded":** the code's comments say what each rule
  does, not why its value; the parameters say so rather than give a
  reason no one wrote down.

## The mean elements' trace (2026-10-30)

- **One trace for the series, not one per sample:** every sample goes
  through the same map with the same radius and J2. What differs between
  samples is only the band each falls in, so the trace counts them.
- **The bands are constants, not parameters:** they handle the map's
  singularity (Environment and data, "Fixed rules"). The trace names
  them as `constant:`.
- **Reached from the figure that uses it:** the semi-major axis change
  carries it as a related trace (`Figure.related`), so the Calculation
  panel opens it from there.

## The power and data traces (2026-10-30)

- **Read, not recomputed:** the power is Basilisk's (`simpleBattery`),
  and the data totals are the ledger's. Their traces name the series and
  the sample, not an equation SpaceMissionStudio does not apply. Only the
  state of charge is SpaceMissionStudio's arithmetic, and its trace says
  so.
- **One place for the sample and the formula:** the dashboard's
  last-sample-at-or-before-the-cursor and the state of charge moved to
  `engine.power_state`. The dashboard and the trace use them, so the trace
  states what the card shows.
- **Not yet:** the scenario explanation's pre-run data estimates (data
  per day, memory fill time, data per pass). They are arithmetic on the
  settings and show as text in Scenario › Overview, where the Calculation
  panel does not reach yet.

## The events' traces (2026-10-30)

- **Made when asked, not kept on each event:** a run can have 10,000
  events, and the Timeline must stay instant. `events.trace_of` reads the
  run again for the one event asked about. `Event` is unchanged, so the
  regression baseline and `events.csv` (byte for byte against 1.1.0) are
  too.
- **One set of rules:** the burn and mode rules became tables
  (`_BURN_SOURCES`, `_MODE_SOURCES`) and each rule a function, used by
  extraction and by the trace alike, so the trace cannot state a
  different rule. A test finds every event again from its trace.
- **The samples either side are shown:** they bound when the event began
  and ended, which is what an engineer asks of an event from a run
  recorded every minute.
- **No `--explain` for events:** a long run has thousands; `events.csv`
  lists them, and the rule of each kind is on the models page.

## The provenance view (2026-10-30)

- **A window from the popover, not a bigger popover:** the popover stays
  the quick look the overview and History had; the full record (hundreds
  of rows with the frames and seeds) needs room, a filter and Copy.
- **A tree in fixed groups, with "Other" for the rest:** the groups follow
  what an engineer looks for (software, run, seeds, scenario, data files,
  time scales, frames, configuration). A key no group names, from a newer
  record, still shows, under Other, so nothing recorded is hidden.
- **Numbers in full (`repr`):** a provenance value is evidence, so a GM
  or a tolerance is shown as recorded, not rounded.
- **The record as `provenance.json` holds it**, the run's warnings
  included, so the window and the file agree.

## The run summary's traces (2026-10-30)

- **The card itself opens the calculation, not a button on it:** eleven
  cards with a button each would crowd the overview. A card with a trace
  takes the focus, shows a hand pointer and the tooltip "Show how this
  was computed", and answers Enter and Space as well as a click.
- **`run --explain`, not a new command:** no command reads a run's CSV
  files back, and the figures are worked out at the end of the run, so
  `run` prints them when asked. Its default output is unchanged.
- **The central body's GM says where it came from:**
  `orbit_number.central_body_mu_and_source` gives the value and its
  source together, so the trace cannot name a different GM from the one
  used.
- **Inputs that are whole series are named in the sources of the values
  read from them** (the first window's mean, the median), not given a
  value of their own: a series has no single value to show.

## The Calculation panel (2026-10-30)

- **Named "Calculation", not "Explain":** Explain (Scenario > Overview)
  already says what a scenario does. The plan's "Explain drawer" says how
  a number was computed, so its button is **Show calculation** and its
  panel **Calculation**.
- **A dock beside the Inspector, hidden until asked for:** the default
  window stays as it was; the panel opens from the number, and the
  layout's reset hides it again, as it does Problems.
- **Two lines per input, not a table:** in a side panel the shared table
  cut off the sources, the point of the panel. Each input gives its value
  and meaning, with its source under it.
- **One explanation per page:** a page sends the trace asked about first,
  with every other trace of the same calculation, so **Open** follows an
  input to its own calculation without asking the page again.
- **The Dashboard's link at the time cursor:** the panel's range and
  pointing error are the run's at the cursor (`last run:`), so it
  explains the figures on screen.
- **The window layout's version goes from 4 to 5:** a new dock; a layout
  saved before would leave it out of place.

## The link budget's traces (2026-10-30)

- **A command, not only traces:** a run's link margin is a time series,
  and a design review asks for one budget. `link-budget` gives it at the
  case that sizes the link: the longest range of a pass, at the station's
  minimum elevation. Any other range can be given.
- **The traces are built beside the breakdown, not inside it:** the
  breakdown is evaluated every step of a run, and the traces would cost
  there for nothing. `link_budget_traces` takes its values from the same
  breakdown, so the two cannot differ.
- **Boltzmann's constant stays -228.6 dBW/K/Hz,** as link budgets write it
  (10 log10 of 1.380649e-23 is -228.599). The trace says so.

## The lifetime's traces (2026-10-30)

- **A seventh source kind, `option:`**: the lifetime's drag coefficient,
  solar-activity percentile, look-ahead and deorbit perigee are the
  analysis's own settings, from the command line or the End of Life page,
  each with a parameter as its default. They are neither the scenario's
  nor a parameter's when given.
- **A decay that reaches the ground within a step re-enters there:** the
  step stays at least an orbit, which the orbit-averaged rates need. The
  re-entry time is then known to within that step, which the warning
  gives. Shorter steps near the end would change every lifetime's last
  digits; this changes only the cases that raised.

## The budget's calculation traces (2026-10-30)

The transparency plan's Phase 4a and 4c, first model.

- **The calculation writes its own trace, from the values it computes
  with:** a trace rebuilt afterwards could describe a different
  calculation than the one that ran. `tests/test_trace.py` then
  recomputes each number from its trace's inputs alone, so a trace that
  drifts from the code fails.
- **One trace type for every model** (`engine.trace`): quantity, equation,
  reference, inputs, intermediates and notes, each input with a unit and a
  source of one of six kinds (`scenario:`, `parameter:`, `constant:`,
  `last run:`, `computed:`, `trace:`). The lifetime, link and run-summary
  traces will use the same type, and the GUI's Explain drawer (4b) shows
  any of them.
- **A solver's result is traced to its inputs, not its steps:** the
  disposal burn (a bisection on the lifetime) and the drag make-up name
  the model and every input; the lifetime's own trace will show inside.
- **The baseline records the numbers, not the traces:** the traces
  restate them. They are left out of the regression fingerprint, which
  would otherwise change with every rewording, and checked by their own
  tests.
- **`--explain` is opt-in:** the default table is as it was.

## The orbit controllers' rules, as parameters (2026-10-30)

The transparency plan's Phase 3a, the first area the coverage check
found missing.

- **The controllers' internal rules are a project's, the targets already
  were:** a scenario sets each controller's deadband, thrust and
  propellant. Its decisions inside (when a firing may start, when a burn
  is not worth firing, when phasing gives up, how far a GEO burn
  reaches) are tuning a project may change for its own bus, so they are
  parameters.
- **Two values say "no derivation recorded":** the firing gate's 2.5 and
  the GEO inclination target's quarter. Their parameters say so rather
  than give a reason no one wrote down.
- **J22 and lambda22 are constants, taken from the field:** they describe
  the Earth. The run's gravity is GGM03S, so the controller plans with
  GGM03S's own degree-2 order-2 term. The old values had no recorded
  source and differ from the field's by 2.7e-5 and 0.0009 deg.
- **The ROE guidance is its own area,** next: it has about 15 rules of
  its own and its own model page to write.

## The rest of the one set of constants (2026-10-30)

The first step of the transparency plan's Phase 4: the audit's Section 4
checked against the registry before the traces are built on it.

- **The Earth's rotation is SPICE's, not astroConstants.h's:** the
  decision was Basilisk's constants because the simulation uses them. For
  the Earth's rotation the simulation uses SPICE (pck00010, or ITRF93
  where installed), and the header's `OMEGA_EARTH` is a rounded sidereal
  day, 1.2e-6 slow. That is 4.3e-4 deg a day, which GEO station keeping
  (which already had a better value) would fit as drift. The rule behind
  the decision, agreeing with the simulation, picks pck00010's rate.
- **Time from `time_system`, not a constant:** TT - UTC is not a constant
  (it was 37 leap seconds only since 2017), and the module that converts
  the scenario's epoch for the run already has ERFA's table.
- **The registry's gaps are listed, not filled in this step:** orbit
  controllers, flight software and navigation, the pre-run checks and the
  mission sequence. Each is an area of its own, a pull request each with
  its model page (`docs/models/README.md`, "Not yet covered"); the checks
  go with Phase 5a's structured warnings, which need their limits named.

## The Assumptions page (2026-10-30)

The transparency plan's Phase 3d.

- **A page of the scenario, not a dialog:** the configuration belongs to
  the scenario that names it, so the page is a node of the editor's tree.
  It shows only when chosen, which keeps the default view as it was.
- **The file is edited, not rewritten:** a project's configuration file
  carries its reasons as comments ("our tanks: 5 % measured"). Writing
  the parameters out anew would lose them, so the page changes one line at
  a time and checks that the file still reads.
- **Values are set below the table, not in it:** the selected
  parameter's details (what it controls, its source, its limits) need the
  room, and a single field with Set makes clear when the file is written.
- **The JSON view stays:** it still edits `config_file`, as before.

## One set of physical constants (2026-10-30)

The transparency plan's Phase 3c; the user's answer to the audit's
Section 10, question 2: one set, every changed number recorded.

- **Basilisk's set:** every simulated orbit uses it, so an estimate and a
  run of the same orbit agree on the Earth they describe. A more recent
  set (IAU 2012's AU, GGM03S's GM) would make the estimates disagree with
  the simulation they estimate, by more than they gain.
- **Constants, not parameters:** a project does not change the Earth. A
  study with another set edits one file, and `tests/test_constants.py`
  then shows where it departs from the simulation's.
- **Left as they are, each for a reason** (`docs/models/constants.md`):
  - the gravity files' own reference values;
  - WGS-84's ellipsoid, for geodetic latitude and height;
  - the mean elements' J2;
  - constants inside Basilisk's modules.
- **Two re-entry altitudes, kept:** they are two criteria, not one value
  twice. The run stops on the simulated altitude (100 km, now a
  parameter); the lifetime ends on the orbit-averaged perigee (120 km).
  Unifying them would make one of the two wrong.
- **The baseline is not rewritten:** the largest change in a recorded
  run output is 1.1e-10 of its scale, far below the baseline's 1e-6.
  `docs/changes.md` records it with its digits.

## The environment's data rules, as parameters (2026-10-30)

The transparency plan's Phase 3a, last area.

- **Two of the environment's rules are a project's:** MSFC's 132-month
  repeat, which AD10 sets but a project with its own solar-cycle
  assumption may change, and the TLE age warning.
- **The rest are the data's or the mathematics':**
  - **The Earth-orientation accuracy window:** NAIF states it for its
    predicted file; a project cannot make the prediction better.
  - **The mean-element bands:** the handling of the map's singularities,
    with no physical meaning to tune; they sit inside pure functions used
    by the generators, the lifetime and the runs alike.
  - **WMM's validity:** the model's release rule.
  - **The panel's stale flag:** it covers the whole app, not a scenario.

  Each is documented, with its reason, on the model page.

## The dynamics' integration and run control, as parameters (2026-10-30)

The transparency plan's Phase 3a, fifth area. The dynamics are split in
two: run control here; the environment's data rules next.

- **The tolerances are a project's to choose:** 1e-10 was chosen for long
  steps (audit E3), and a project trading accuracy for speed, or wanting
  more, now sets it. The provenance records the run's own.
- **The re-entry checks' cadence is a parameter, not the trajectory's:**
  the chunks do not change what Basilisk integrates (the same final
  position to the millimetre in every case measured), only how precisely
  the re-entry time is known.
- **Not parameters:**
  - the 100 km re-entry altitude, which Phase 3c reconciles with the
    lifetime's 120 km;
  - the long run's 90-day segments, which only have to fit Basilisk's
    104-day clock;
  - the order of the modules within a step.

## How a run's results are read, as parameters (2026-10-30)

The transparency plan's Phase 3a, fourth area: the run summary, the
events, and the overview's and dashboard's marks.

- **A run is judged by its own values:** each value is read back from the
  run's provenance, not from the configuration open now. A run kept in the
  history and shown a week later, after the project changed its file,
  still reads as it did. The dashboard reads the scenario of the run it
  shows, which carries that run's configuration.
- **The battery limit is a share of the capacity:** a limit in W*h would
  differ for every battery. 0 keeps "Battery empty"; a project with a
  depth-of-discharge limit (Section 7 lists one as missing) sets 0.3 for
  70 %. It marks the result only: Basilisk's battery still runs to 0.
  Without the scenario as run (no capacity), only an empty battery is
  marked.
- **Not parameters:**
  - an eclipse is any sunlight below 1 (a definition, not a choice);
  - a pass is `has_access` on (the station's elevation mask, a scenario
    input, decides it);
  - unit conversions.

## The link's and data handling's rules as parameters (2026-10-30)

The transparency plan's Phase 3a, third area.

- **A required margin, at 0 dB:** the link closes at a margin of at
  least `link.required_margin_db`. The default keeps today's 0 dB, so no
  number changes; a project that requires 3 dB sets it. The audit asked
  for one (Section 7 and Appendix B: "no required-margin policy").
- **One rule wherever the link is judged:** the simulated downlink, the
  Vizard status, the dashboard and the overview card use the same
  `link_budget.link_closes`, so they cannot disagree. A run shown in the
  overview is judged by the value it was run with, read from its
  provenance, not by the configuration open now.
- **Only the "fixed" pattern's loss is a parameter:** the patch and the
  gain table take their shape from the antenna's own inputs, which are
  the scenario's. The 0.05° grid of the reported beamwidth is numerical
  and stays as it is, documented.
- **Constants stay constants:** c, Boltzmann's constant and Basilisk's
  solar flux are not engineering choices. Phase 3c gathers the physical
  constants; the solar flux and the AU are in Basilisk's C++ modules,
  which this tool does not change.
- **Power has no parameter:** every value of the power model is the
  scenario's (panel, battery, loads) or Basilisk's. Its page documents
  the model instead.
- **GUI starting values of new spacecraft groups wait:** the panel
  efficiency 0.29 and the other values a new group starts with are
  scenario defaults, saved in the file once set; they are the scenario
  defaults' area, not a rule's.

## The lifetime's rules as parameters (2026-10-30)

The transparency plan's Phase 3a, second area.

- **The estimate's defaults are parameters:** the drag coefficient,
  percentile, horizon and deorbit perigee that `lifetime` and the End of
  Life page start from are what a project most often wants as its own.
  The CLI's options default to unset and take them per scenario. The page
  sets its controls to them when they change, and not on every edit,
  which would undo the user's own choices.
- **The input limit stays a limit:** `MAX_HORIZON_YEARS` (100 years) bounds
  what the estimate accepts; it is not an assumption of the model.
- **Two re-entry altitudes, kept for now:** the lifetime's 120 km is a
  parameter; the run's 100 km is not yet. Phase 3c reconciles them, as a
  recorded change of numbers.
- **Choices, not only limits:** a percentile parameter takes only MSFC's
  95, 50 and 5, the only ones a forecast can be resolved at. The budget's
  two percentiles, merged with limits 5 to 95, accepted 60 and failed at
  run time; a value outside the choices is now refused when the file is
  read.
- **A GUI default's test is the page's:** the deorbit perigee acts only on
  the End of Life page, so its case is a test of that page, which the
  registry's guard test names.

## The parameter registry and project configuration (2026-10-30)

The transparency plan's Phase 3a and 3b (`docs/transparency_audit.md` 9.2),
for the first area, the propellant budget; Section 10.1 decided YAML.

- **One declaration per parameter:** `config/parameters.py` declares
  each with its name, default, unit, what it controls, source, rationale
  and limits. The code reads the value in effect (`registry.value`); the
  module constants are gone, so there is no second copy to drift. Earth's
  GM and radius stay constants until Phase 3c chooses one set.
- **Named, never found:** a scenario names its file (`config_file`). A
  configuration file lying in the folder changes nothing unless a
  scenario names it, so no result depends on a file nobody chose.
- **Read where the scenario is loaded, carried with it:** the file is read
  by `load_scenario` and by the GUI editor's `to_scenario()`, both of which
  know the scenario's folder, into `Scenario.configuration`. That field is
  never saved (`init=False`, dropped from `to_dict`), never compared, and
  left out of the scenario's hash. It travels with the scenario object
  into Monte Carlo workers (pickled), long-run segments (copied) and the
  altitude trade's processes; a context variable would not survive a
  Windows `spawn`.
- **The hash and the record:** `config_file` is written only when set,
  so every scenario without one saves, and hashes, exactly as before. When
  set, the scenario's hash covers the name, not the file's values; the run's provenance records the
  file's SHA-256 and each value it changes, with its default. A bundle
  copies the file. Two runs of one scenario with different files share a
  scenario hash and differ in `configuration`.
- **Refused, not ignored:** a file that cannot be read, a name the
  registry does not know, or a value outside a parameter's limits makes
  the scenario invalid, naming the file and the parameter. A relative
  `config_file` in a scenario not saved yet is refused, not read from the
  working folder.
- **The defaults file, commented out:** `config/defaults.yaml` is
  generated from the registry and lists every parameter with its default,
  unit, source and limits, each line commented. A copy changes nothing
  until a line is uncommented, so starting a project file cannot change
  a result by accident.
- **Labels follow the values:** the budget's margin labels and notes ("1%
  of tank", "x4 count") are worked out from the values in effect, so a
  changed margin is never labelled with the default. At the defaults they
  read as before, character for character.
- **A test sets each parameter:** `test_config.py` sets each budget
  parameter and checks that what it controls changes, and fails when a
  parameter is declared without such a case (the plan's 9.4).
- **PyYAML declared:** it already shipped with Basilisk's `bsk[all]`
  (6.0.3 in the installers); it is now a core dependency, as the
  configuration needs it whatever Basilisk pulls in.

## Reproduction bundles (2026-10-29)

The transparency plan's Phase 2h (`docs/transparency_audit.md` 9.2;
definition of done: "reproduce a colleague's result from an exported
file").

- **A run folder, extended:** a bundle is the folder `run --out-dir`
  already writes (results, provenance, scenario as run), with `inputs/` and
  `bundle.json`. Copying the files at once is what makes a folder that
  can travel. `--bundle` is opt-in, as a model's meshes can be large.
- **What is copied:** the files the scenario refers to, and the
  space-weather files the run read, because for the `"bundled"` source they
  depend on the computer (the shipped file or a newer download). The
  installed reference data is not: `de430.bsp` is 114 MB, and its hash in
  `provenance.json` is enough to say whether a computer has the same.
- **The scenario's hash is checked before its paths are changed:** the
  scenario as run is checked against `scenario_sha256`; only then are its
  references pointed at the bundle's copies, and each substitution is
  reported. The copies' SHA-256 are checked against the manifest. So the
  new run is the same scenario on the same file contents, at other paths.
- **Compared as written:** both runs' series are compared from their CSV
  files, 9 significant digits each, column by column, as a fraction of the
  column's largest magnitude. The default 1e-6 is the regression
  baseline's general rule, found to hold for well-conditioned outputs
  across computers (3.8e-7 measured). Like that rule, it does not hold for
  a noisy sensor across C++ standard libraries, and the report says when
  the platform differs.
- **A verdict and the reasons:** the exit code is 0 or 5 on the series
  alone, and the report lists the versions, platform, reference-data files
  and event counts that differ, for the reader to judge. A different
  Basilisk version is reported, not refused.

## The effective configuration (2026-10-29)

The transparency plan's Phase 2c (`docs/transparency_audit.md` 9.2; gaps C
(a) and (h), 4.2 "Engine defaults behind open `params`", 5 "Silent
migrations").

- **Noted where the engine reads, not listed beside it:** each open
  `params` dictionary is wrapped at build time in a `RecordedParams` that
  notes the keys read and missing, with the default the reader passed. A
  separate list of the 36 defaults would be a second copy free to drift
  from the code. The note is of what this run read: a key that only one
  mode reads appears only when that mode runs.
- **In place, after validation:** the dictionaries are wrapped in the
  scenario being run, after `validate()`, so only the engine's reads are
  noted. The service does not copy its scenario: the mission engine and
  Monte Carlo share it. Every caller hands the service a scenario of its
  own (the GUI's `to_scenario()`, a loaded file, a segment's copy), so no
  editor holds the dictionaries replaced. A `RecordedParams` is still a
  `dict` with the same items: equal to one, saved and pickled as one.
- **`None` kept, and explained:** a default of `None` means the engine
  sets nothing and the Basilisk module keeps its own value. The record
  says so (`effective_config_note`) rather than leaving the key out. The
  Basilisk value itself is not read back; for the devices it is.
- **Devices read back from Basilisk:** a named wheel or thruster takes its
  values from Basilisk's factory. They are read from the devices the
  factory made, in Basilisk's SI units, not looked up in its source, so
  the record is what the simulation flew.
- **Migrations from the file, beside its hash:** loading an older file
  changes values (a v1 `"celestrak"` source becomes `"bundled"`). The
  changes are worked out from the file's bytes with the file's hash
  (`output_provenance.scenario_file_record`), so they are recorded exactly
  when the file is: by `run`, and by the GUI for a run of an unchanged
  file. `validate` prints them.

## The records of a lifetime, a budget, a batch and a SIL run (2026-10-29)

The transparency plan's Phase 2g (`docs/transparency_audit.md` 9.2, gap 8):
the outputs that are not a run's.

- **A file on request, the printout unchanged:** `lifetime` and `budget`
  print as before, and `--out FILE.json` writes the record. Scripts that
  read the printout keep working, and the record has room for what a
  table cannot hold: the decay curve, the rules, the data files.
- **What the code used, named as in the code:** a record's `model` gives
  the values that are not in the scenario file under their names in the
  code (`REENTRY_ALTITUDE_KM`, `CAM_COUNT_FACTOR`, ...), so a reader can
  find each one. They stay constants for now; the parameter registry
  (Phase 3) is where they become editable.
- **What the decay used, kept on the result:** `EndOfLife` keeps the area,
  drag coefficient and space-weather files it used, and `Budget` the files
  its drag estimates read. Working them out again for the export would be
  a second copy of the rule, free to drift from the first.
- **The baseline leaves the data files out:** they are paths, sizes and
  hashes of this computer's files, as the run provenance's `data_files`
  already were. The area and drag coefficient are numbers of the result
  and are compared.
- **A batch's record is built after the batch:** the nominal run is built
  but not run (`SimulationService.nominal_provenance`, 0.2 s for template
  25), after `executeSimulations`, because the Controller forks its
  workers from this process, and a Basilisk simulation left over before
  that can hang them. It is written by `run_monte_carlo` itself, so the
  CLI and the GUI's child process write the same record.
- **No seeds in a batch's record:** Basilisk's Controller draws each run's
  seeds and writes them to its `run<N>.json`, and those are the ones used
  (`assign_rng_seeds` keeps a seed already set). The nominal run's seeds
  would be seeds no run used, so the record says where the real ones are.
- **The SIL report records its run:** the run flown in SIL is a copy of the
  scenario without its Mission Sequence or Monte Carlo, so the report keeps
  both hashes: the scenario's at the top and the run's under `run`.
- **Not yet in the GUI:** the End of Life page has no export, and the
  Budget page copies its table with the scenario lines. Their exports
  belong to Phase 9a (open data), which will reuse these records.

## The run record (2026-10-29)

The transparency plan's Phase 2a, 2b, 2d and 2f (`docs/transparency_audit.md`
9.2): what a colleague needs to re-run a result.

- **The scenario as run, not only its hash:** `run` writes
  `scenario_as_run.json`, the migrated scenario as the app saves it. Its
  canonical JSON hashes to `scenario_sha256`, so the file and the record
  check each other. The GUI's exports do not write it yet: the
  reproduction bundle (Phase 2h) will cover the GUI.
- **Both hashes:** `scenario_sha256` (the scenario as run, after migration)
  and `scenario_file_sha256` (the bytes given). Two files that differ only
  in layout, or an old file and its migrated form, share the first and not
  the second. The GUI records the file only when the run starts from it
  unchanged; after an edit the file is not what ran, and an empty field is
  more honest than a stale hash.
- **Large files hashed once:** hashing `de430.bsp` took 8.2 s on this
  computer. A file over 32 MB is hashed on first use and its hash kept in
  `~/.cache/SpaceMissionStudio/file_hashes.json`, keyed by path, size and
  modification time, as git's index trusts a file; the record says
  `sha256_cached`. A file changed in place with its size and time kept
  would not be noticed: that is the assumption made.
- **Installed kernels re-hashed:** an Earth orientation or small-body
  kernel was trusted on its install manifest. It is now hashed at run time
  (under 32 MB each, the Eros SPK about 5 MB) and a mismatch is a run
  warning, not an error: the run still uses the file, and says so.
- **Warnings in the record, not in the run record:** `run_warnings` is
  added to the exported `provenance.json` and the Timeline and Output
  sidecars, not to `RunProvenance`: the warnings are what the run found,
  the provenance how it was made. Plot images keep the record without
  them.

## GUI defects of the transparency audit (2026-10-29)

The transparency plan's Phase 1b for the GUI (`docs/transparency_audit.md`
3.4, 3.7, 3.8, 3.9, 3.10, 3.12).

- **3.4, shown not changed:** the inertia scaling of the default gains is
  kept (the unscaled gains diverge for small spacecraft, HISTORY.md); the
  form shows the scaled values and the line above it the derivation. The
  defaults and their scaling moved to `engine.control_gains`, which needs no
  Basilisk, so the GUI computes them as the engine does instead of keeping
  a copy.
- **3.7, no spread rather than a guessed one:** a new dispersion starts
  at the spacecraft's own value with zero width. A percentage would be an
  assumption nobody made; zero width disperses nothing until the user sets
  a spread, and the note says so.
- **3.9, the schema's default wins:** the GUI now takes a new station's
  defaults from `GroundStationConfig`, so the receive gain is 0 dBi in
  both. Changing the schema to 45 dBi instead would change every scenario
  file written without the field; the templates that use a link set their
  own gain (35 dBi or 0 dBi).

## Engine and command-line defects (2026-10-29)

The transparency plan's Phase 1b (`docs/transparency_audit.md` 3.1-3.3,
3.5, 3.6, 3.11, 3.13 and 3.14); the GUI and default defects (3.4, 3.7-3.10,
3.12) follow in their own change.

- **The run keeps its central body and GM** (`central_body`,
  `central_body_mu_m3_s2` in the provenance): the orbit-number axis and the
  mean semi-major axis change take the GM from the run itself, not from a
  constant. A record written before (no GM) falls back to the body its
  inertial frame names, and to Earth's GM when that is Earth or unknown, so
  every Earth run reads as before.
- **Exit status 5 for a check that ran and did not pass** (`fsw-status`,
  `sil --max-error`): they returned 2, which ICD-02 gives a missing
  component or a usage error, so a script could not tell "stale export"
  from "no Basilisk". A new status was chosen over reusing 1 (an input
  error) because the input was fine. `monte-carlo` with a failed run
  returns 3 (a run failed), not 4 (an internal error), and `kernels-status`
  with a kernel missing returns 2 (a missing component), not 1.
- **The predicted Earth orientation note reaches the run's warnings:** it
  was shown in the Explain tab only. No reason was recorded for keeping it
  out of the run (#124 added the filter with the coverage notes), and a
  run that uses predicted values has a larger Earth-fixed error, which the
  user should see with the results.
- **A check that fails says so:** the pre-run and plausibility checks
  dropped an exception without a word, so a check that could not run looked
  passed. It is now one line, `check not run: <name> (<error>)`, and the
  traceback goes to the log; the checks still never raise.
- **A stop epoch counts TDB seconds:** the simulation clock counts TDB
  seconds since the epoch, so the time to a stop epoch is now the TDB time
  between the two, leap seconds included (`time_system.tdb_seconds_between`).
- **A split run's provenance is the whole run's:** the scenario hash of the
  file as given (not of segment 0's copy), every segment's seeds, and the
  real space-weather file, with the whole-span file built from it kept as
  `space_weather_resolved`.

## Regression baseline (2026-10-29)

The transparency plan's Phase 1a (`docs/transparency_audit.md` 9.2).

- **Fingerprints, not whole outputs:** each column of each series is kept
  as its first, last, least, greatest and mean value and 11 evenly spaced
  samples. 1.4 MB for 31 templates, where the full CSVs are hundreds of MB,
  and a change anywhere in a column moves at least its mean.
- **Runs capped at 6 hours of simulated time:** the full templates take
  about 20 minutes one after another; capped, the baseline takes 8 min 57 s
  here, 2 min 54 s on 8 test workers. A Mission Sequence runs in full
  (at most 14.4 h), since its steps set the length.
- **Compared within what two computers disagree on, rule by rule**
  (`tests/golden_capture.py`, "How numbers are compared"). A first
  tolerance of 1e-9 of each quantity's scale held here (two runs gave
  identical fingerprints) but failed on CI: 22 templates on Linux, all 31
  on Windows. CI's two Linux runs agreed with each other byte for byte;
  every difference was traced:
  - last bits amplified by ill-conditioned quantities: the angles of a
    circular orbit (an arccos near 1 gives 0 or 2^-26 = 1.5e-8 rad), the
    eccentricity of a circular orbit (2e-15), a mean semi-major axis
    change (a difference of two means of 7000 km), the relative orbit
    elements made from those angles (0.1 m);
  - angles wrapping at 2*pi (a RAAN of 0 against 6.283185);
  - sensor noise: Basilisk's GaussMarkov draws from
    `std::normal_distribution`, whose algorithm each C++ standard library
    chooses, so Windows (MSVC) and Linux draw different noise from the same
    seed, and a spacecraft that closes its attitude loop through its
    sensors carries it into its wheels (4.8e-6 of scale);
  - recorder seed keys spelled by the compiler (a defect, fixed below).

  The rules: 1e-6 of the quantity's scale (well-conditioned outputs
  differed by at most 3.8e-7); absolute floors by unit, about ten times the
  largest difference measured (1e-6 rad, 1e-12 for eccentricity, 1 m for
  relative orbit elements); wrapping angles modulo 2*pi, first, last and
  samples only; a sensor output from another standard library by its
  count only. Every CI difference was replayed through these rules: none
  is reported, and CI's Linux jobs passed.
- **Off the recording platform, a coarse check (1 %):** the second Windows
  run found template 21's magnetorquer and wheel outputs 7.6e-4 of scale
  away, where the first Windows run had matched them within 1e-9. Each
  commit gave the same values on both of its Windows runs, so Windows
  repeats itself per commit; the only engine change between the two
  commits was the recorder seed names, and on Linux changing every
  recorder seed, or running all 30 other templates first in the same
  process, leaves template 21 bit-identical. **The cause was not found.**
  A switching controller (momentum dumping) amplifies any last-bit
  difference, so no small bound can be given. On another C++ standard
  library every number is therefore held to 1e-2 of its scale; texts,
  counts, events and warnings still match exactly. The fine check is
  Linux's, where the baseline is written and the developers and CI run it.
- **What this costs:** a change smaller than 1e-6 of a quantity's scale is
  not caught on Linux (a 1.5e-8 change of Earth's GM moves a 6-hour LEO
  position by about 2e-7 of its scale), nor one under 1 % on Windows. A
  Linux computer whose math library rounds differently could in principle
  also shift template 21's switches; none has so far (this computer and
  CI's Linux runners).
- **Recorder seed keys the same on every platform** (`engine.seeds.model_key`):
  Basilisk names a recorder after the message type as the compiler spells
  it ("Rec:SCStatesMsg" with GCC, "Rec:class <struct SCStatesMsg" with
  MSVC), so the provenance listed different keys on Windows. Recorders draw
  no random numbers: no result changes.
- **Isolated as every test is:** the capture runs in a home of its own (no
  downloaded space weather, no installed Earth orientation files), so the
  update script and the test compute the same thing.
- **Budgets with an Isp of 220 s on templates 22 and 26** as well:
  26 of the 31 templates have no orbit thruster, so their budget is
  refused; the refusal is recorded, and these two also exercise the
  drag-driven budget.
- **`docs/changes.md` starts empty:** the baseline changes no number.

## Transparency plan (2026-10-29)

The user's answers to `docs/transparency_audit.md` Section 10, recorded there in 10.1.

- **YAML for configuration:** comments and units can sit next to each value; PyYAML already
  ships in the installers.
- **One set of constants, with each changed number recorded:** today three sets of Earth
  constants and two solar fluxes give slightly different numbers in different views.
- **Change history in a sidecar file:** the scenario stays a clean input for version control.
- **Author from Settings, defaulting to the operating-system user name:** the audit gave no
  recommendation here. This reading works without setup and can be corrected by the user.
- **Defect 3.4:** the GUI shows the gains applied after inertia scaling. The scaling is kept,
  because the unscaled gains diverge for small spacecraft (HISTORY.md).

## Temporary folders and refusals of the wrong shape (2026-10-29)

The audit's R14 and a note under R5.

- **Removed when their process has ended, not only at exit:** the audit
  proposed `atexit`, but the page folders already went at a normal exit
  (`TemporaryDirectory`) and the icons' folder, which used `atexit`,
  leaked with them: what leaks is a killed or crashed process, which runs
  no exit code. So each name carries the process id, and the next start
  removes the folders of processes that have ended. A process that cannot
  be checked counts as running: a folder in use is never removed.
- **The old names, after a day:** a folder named before this change
  cannot be traced to its process; it is removed once it has not changed
  for a day, as only a session of the old version still running could
  use it.
- **At GUI start, in the background:** the GUI makes all the page folders;
  1014 folders took 10.4 s to remove here, so a thread does it. The CLI
  makes only Vizard's folder, removed at exit; a crashed CLI run's is
  removed at the next GUI start.
- **Coverage of Monte Carlo's workers, set in `pyproject.toml`:** the
  audit read `cli.py`'s 74 % as CLI tests in unmeasured subprocesses.
  They call `cli.main` in the test process; what went unmeasured is Monte
  Carlo's `multiprocessing` workers. Measuring them costs no time (9 min
  41 s against 10 min 18 s) and needs `branch` and `source` in the
  configuration, or the processes' data cannot be combined (the first try
  failed so). Coverage's `patch = ["subprocess"]` adds 3 lines more but
  also starts coverage in pytest-xdist's workers: 6 data files were left
  after the run, one half-written, which a later local run would try to
  combine. The missing CLI tests are a separate change.
- **Refusals keep "malformed scenario structure":** the SUM's message
  table, the JSON view and scripts read it; the part in brackets now says
  where and what instead of Python's own message.

## Output folder and input limits (2026-10-29)

The audit's R7, R8 and R9.

- **A used output folder is named, not refused:** the audit offered
  refusing a non-empty folder unless `--overwrite` is given, or removing
  the files of the previous `provenance.json`. `--out-dir` defaults to
  `results`, so refusing would break every second run of a script that
  never set it; and `provenance.json` does not list the files a run wrote,
  so nothing says which old files are safe to delete. `run` therefore
  writes as before and ends with a `WARNING` naming the files it did not
  write.
- **The output folder is probed, not only created:** `mkdir` succeeds on
  a folder that exists but is read-only; a temporary file written and
  removed in it is the check that matches what the run will do.
- **Limits far above any real scenario:** the templates have at most 6
  spacecraft, files of at most 27 KB, steps of at least 0.1 s and names of
  at most 11 characters. The limits (1000 spacecraft, 20 MB, 0.001 s, 64
  characters, a description of 100 000 characters) only stop a mistyped
  or damaged input; 0.001 s is the GUI's own least step. A file over the
  limit is refused after reading one byte more than the limit, never
  whole.
- **500 MB for a CCSDS message:** a long, finely sampled OEM is
  legitimately large, so the limit is far above a scenario's.

## Parser, look-ahead and exit codes (2026-10-29)

The audit's R5, R6 and R13.

- **A new exit status, 4, for an internal error:** 1 means invalid input
  in ICD-02 and 3 a failed run; a fault in the tool itself is neither,
  and a script deciding whether to retry or fix its file needs to tell
  them apart. The traceback goes to the log file only (its DEBUG level),
  so the terminal shows one line; without a log file it is printed.
- **`--max-years` refused by argparse (status 2):** the same as every
  other bounded option (`--oem-stride 0`, `--altitudes`); the audit asked
  for 1, but ICD-02 gives 2 to a usage error, which this is.
- **100 years, the GUI's limit:** the engine and the CLI now share it;
  the 25-year guideline needs far less, and past 100 years the solar
  cycle forecast only repeats.

## Room for results at 1280 x 720 (2026-10-28)

The audit's G8: "Inspect fields only; collapse the Inspector on small
windows; open Problems on errors only."

- **By the screen, not the window:** the window opens at 1400 x 850, so a
  rule on the window's own width would hide the Inspector on every
  screen. A screen narrower than 1600 px is where the window cannot be
  wider; there the Inspector starts hidden.
- **Only for a new layout:** a layout the app kept (the window's or a
  project's) is applied as it was, so nobody loses a panel they chose to
  keep. Reset Layout gives the new window's panels.
- **An edit's first error opens Problems, nothing else:** the blank
  scenario opens with an error (no spacecraft yet), and opening the panel
  for it, or for a file opened with one, would undo the room it gives. A second error,
  or a warning, only adds to the counts in the status bar and the top
  bar; a panel the user closed stays closed until the scenario is valid
  again. A run that cannot start still opens it.
- **Fields only, and a box's own line edit is its box:** the Inspector
  describes a value: its range and help. A button or a tab has neither,
  so it shows the empty state rather than dashes.

## Control borders at 3:1 (2026-10-28)

The audit's G7: "A control-border token of at least 3:1, added to
CONTRAST_PAIRS."

- **A new token, not a darker border.strong:** border.strong also draws
  panels, toasts and buttons, where it separates surfaces (the design
  rules' "very few lines"); a field or a check box is identified by its
  border, a button by its label.
- **text.primary over the surface, the least share that passes:** the
  same derivation as the other tokens; 51 % light and 42 % dark give
  3.08:1 at worst (on bg.hover), so the borders stay as quiet as the rule
  allows.
- **Disabled controls keep border.subtle:** WCAG 1.4.11 exempts inactive
  components, and the fainter border says that they are.

## A Monte Carlo batch can be cancelled (2026-10-28)

The audit's G3: "Terminate the child process, keep finished cases, offer
'Cancel and close'."

- **The child ends its own processes, then itself:** Basilisk's
  Controller has no way to stop part way, and it starts a pool, a data
  writer and a manager from the batch's child; terminating the child
  alone would leave them running (on Windows, nothing would end them).
  A thread in the child waits for a cancel event and ends every process
  it started; the GUI terminates the child only if that takes over 15 s.
- **The runs finished are summarized by a second, short child:** the run
  files are pickles, read only by the kind of process that had them
  written (security analysis S-04), as the batch does at its end. A file
  cut short by the cancel is skipped. Runs not finished are not listed as
  failed: they were stopped.
- **Closing asks, Keep running the default:** a batch can be hours of
  work; closing by accident must not end it.

## Exports off the GUI thread (2026-10-28)

The audit's G2: "Move them to a worker, as the flight software export
already does."

- **A worker per export, the files only:** the folder dialog and the
  plots' rendering (in the page) stay where they are; what took the time
  was decoding the images and writing the files.
- **Cancel between files, not inside one:** a file is never left half
  written; the ones written stay, and the message says how many.
- **What the files hold is taken when the export starts:** the shown
  plots, their series and the run's provenance, so a new run arriving
  meanwhile does not mix into it.
- **Progress beside the buttons, not in the status bar:** the status bar's
  job strip is the run's; an export is the Results page's own.
- **The window waits for an export when it closes** (seconds at most),
  as it does for the reference data read.

## Monte Carlo off, said before Run (2026-10-28)

The audit's G5: "Let the mode decide, or show an inline 'Enable' banner
before the click."

- **The banner, not the mode deciding:** Scenario > Monte Carlo > Enabled
  is saved in the scenario (a file can carry its dispersions, off, for a
  later batch), and the run mode is not; letting the mode switch it would
  change the file by picking a mode. Enable stays one click, on the Run
  page, and goes to the page where the batch still needs its dispersions.
- **Run is not disabled:** it still says why, as before, for a click made
  anyway (from the toolbar or Ctrl+R, where the note is not seen).

## The run's length with a Mission Sequence (2026-10-28)

The audit's G4: "Say so on the Duration field; make Overview reflect the
sequence."

- **From the steps, without running:** durations add up, an epoch stop
  ends at its epoch; an event stop, or an if/while with a propagate in
  it, ends only when it runs, so it is counted ("+ 2 event or condition
  stops") rather than guessed.
- **Passes over the sequence when it is known,** else over the Duration,
  said so: predicting where an event stop ends would need the run.
- **The Duration field is kept:** it still sets how far the space
  weather and the checks reach, which the note says.

## Space weather past the Duration (2026-10-28)

Found while checking the audit's G4 (the Duration does not limit a run
with a Mission Sequence).

- **Refuse, not extend:** the length of a sequence with event stops or
  loops is not known before it runs, so the loaded span cannot be sized
  to it; a run that would leave it stops, as one past the Earth
  orientation files already does (R1). The message says what to set.
- **An event search is checked where it stopped:** checked at its bound
  (10 x the Duration, at least 10 days), almost every search with drag
  would be refused though it stops long before; where it stopped is what
  used the data. In the CLI's unchunked search that is after the step, so
  its results are not kept; the GUI's search runs in chunks, each checked
  before it runs.

## GUI fixes from the audit, batch 1 (2026-10-28)

- **G6, Save as the default button:** what most editors do; Enter keeps
  the work. Qt's standard buttons, so the platform names them (Save,
  Discard, Cancel; "Don't Save" on macOS styles).
- **G10, Retry in the panel, a note in the status bar:** the status bar
  button already opens the panel; a second Retry there would be one more
  control for a rare failure.
- **G9, not changed:** Spacecraft › Edit in the main window already opens
  the spacecraft's page in the tree (set since U-01); the modal dialog
  the review cited is the list's fallback when it has no page to open,
  used only by its own tests.

## Dependency security (2026-10-28)

The audit's "next" row for R10 to R12: "Update Pillow and certifi;
pip-audit in CI; pin CI tools; tests required on the release tag; fix
Debian copyright" (testing 3.11 and 3.13 no longer applies: 2.0.0 needs
3.14).

- **pillow kept at 12.2.0, its advisories listed:** bsk 2.12.0 requires
  pillow <= 12.2.0, so pip cannot install 13.0.0 (the first without them)
  with the qualified Basilisk, and installing it against Basilisk's own
  requirement is not this project's to do. The 52 advisories are in
  `packaging/audit-exceptions.txt`, each by ID and for pillow 12.2.0
  only; any other advisory still fails CI, and a test fails if pillow
  moves while the list stays (K-25).
- **pip-audit on the pin files, `--no-deps`:** they list every package
  exactly, so the audit sees what the installers ship, not what a runner
  happens to resolve. In the `test` job (required), after the tests and run
  whatever happened before them (`if: always()`), so a new advisory fails
  the job without hiding the test results.
- **The dev tools in their own file:** `constraints.txt` stays the set
  the installers ship; `constraints-dev.txt` holds the tools and what
  they need, resolved against it.
- **Tests on the tag by calling the main workflow** (`workflow_call`,
  with the tag as `ref`): the same jobs as every pull request, with
  nothing to keep in step; `attach` needs them.
- **Copyright by part, last match wins:** the format's own rule; a test
  resolves sample paths of each part to their licence.

## Random seeds (2026-10-28)

The audit's E5: "Derive one seed per sensor from scenario, spacecraft,
sensor and segment; record the seeds in provenance."

- **One scenario seed, `sim_settings.seed` (default 0):** a user can ask
  for another realisation of the noise; the same file still gives the
  same run. Optional with a default, so older files load unchanged.
- **Every model, by name, after the build:** the seeds are set on every
  model still on Basilisk's default, by its ModelTag (the spacecraft and
  sensor names), not in each sensor builder, so a noisy module added
  later is covered too. Seeds set on purpose (a navigation error's own,
  Monte Carlo's) are kept.
- **SHA-256 of the scenario seed and the name:** independent of the order
  the models are built in, and the same on every platform.
- **0 to 2**31 - 1:** what the GUI's spin box holds; Basilisk's RNGSeed is
  32-bit.
- **Monte Carlo batches not changed (K-24):** Basilisk's controller seeds
  each run from its run number; changing that means changing Basilisk.

## The integrator's tolerances (2026-10-28)

The audit's E3: "Set tolerances (about 1e-10 relative) or expose them;
warn above about 60 s; record both in provenance."

- **Fixed values, not a scenario field:** relative 1e-10, absolute 1e-8
  (Basilisk's default). One measured setting serves every template, and
  a new field would change the scenario format for a value nobody has
  needed to change. Provenance records both.
- **Absolute 1e-8 kept:** 1e-10 changed nothing measurable (300 s: 11.3
  against 11.4 m).
- **A warning above 60 s, not a refusal:** under 2 cm after a day at
  60 s, 0.9 m at 120 s; a long step can be a deliberate quick look.
- **Template 17's description corrected, not its scenario:** its fuel
  use was the integrator's error; the scenario was right.

## Python 3.14 only (2026-10-27)

The user: "Drop support for every Python version older than 3.14. The
project should target Python 3.14+ only, everywhere", with three answers:
SpaceMissionStudio only (Basilisk's own packaging and workflows are the
framework's), after the open PRs merged, released as 2.0.0.

- **3.14, not "3.14 and newer" in CI:** Basilisk 2.12.0 and PySide6 6.11
  declare `<3.15`; there is no newer Python the tool installs on.
- **The installers' Python:** CPython 3.14.8 from the same
  python-build-standalone release (20261013) as 3.11.17 was, with the
  digests from that release's `SHA256SUMS` (whose 3.11.17 lines match the
  digests pinned before).
- **sgp4 without its C extension:** no sgp4 release has a 3.14 wheel, so
  pip installs its pure-Python form: the same SGP4 algorithm, slower; the
  TLE tests pass.
- **`from __future__ import annotations` kept:** removing it changes when
  annotations are evaluated (PEP 649), which `schema.scenario`'s type
  check reads; it is not an old-version shim.
- **ruff's upgrade rules once, not in the lint set:** `ruff check --select
  UP --fix` rewrote 1717 places; the leftovers it cannot fix safely stay
  (two `%` formats, one is a JavaScript string; a `Union` alias of Qt
  classes). UP is not added to the configured rules.
- **Records:** requirement and plan documents say 3.14 from today; the
  verification records (SVR, measurements, SRelD of 1.3.1) keep what was
  tested then.

## Generators by mean elements; a continuous map (2026-10-27)

The user: "Merge them all, continue as per your recommendations" (the
audit's E4). It changes the orbits the Walker and phasing generators
write, when the run models J2.

- **Mean elements only when the run has J2:** with point-mass gravity
  (the default) osculating and mean elements are the same, and mapping
  with J2 would put the satellites off by the short-period terms. So the
  generators take `j2` from `constellation.simulated_j2(central_body,
  degree)`: the body's J2 for degree 2 or more, else 0 (the pattern is
  written as before).
- **Placed like the ROE follower:** `mean_elements.osculating_from_mean`
  maps mean to osculating and corrects until mapping back gives the mean
  elements, as `roe_formation.follower_orbit` does, but in equinoctial
  elements (with the retrograde factor), which stay defined for circular
  and equatorial orbits.
- **A blend, not the nearer edge:** placing two satellites needs the map
  to be consistent on both sides of 63.435 deg. With the nearer edge the
  chief (just above) and the follower's mean elements (just below) used
  different edges: 224 m of semi-major axis, a follower 30 km off in a
  day. Blending the two edges' maps by distance keeps it continuous, and
  is closer to the orbit average (0.014 km of perigee for the 600 km
  orbit, was 0.4; the 300 km lifetime 34.82 days against the run's 34.82,
  was 34.46). It costs two Basilisk map calls in the band.
- **An equatorial band:** `clMeanOscMap` divides by `tan i` (an error at
  0 deg). Below 1 deg (above 179) it is evaluated at 1 deg (179) and the
  inclination carried across, turning node and perigee by 180 deg when
  that crosses 0.
- **Templates 04 and 05 unchanged:** regenerating them changes their
  stored orbits and documented results (template 05 holds 50 km within
  5 km); that is a separate change.

## Earth orientation files only for the runs they cover (2026-10-27)

The user: "Continue as per your recommendations" (the audit's critical
findings first).

- **The coverage from the file itself:** `pck_coverage` reads the DAF
  summary records of a binary PCK (the start and end time of each
  segment) without SPICE; a file it cannot read, or whose segments point
  past its end (a truncated download), counts as covering nothing. Read
  once per file version (0.15 ms; the checks while editing ask on every
  edit).
- **All or nothing per run:** the files are loaded when together they
  cover the whole run (`covering`); otherwise none is, and the run uses
  IAU_EARTH, as with no files installed, saying why. Loading them for
  part of a run would end it in SPICE at the first uncovered step.
- **A Mission Sequence's end is not known in advance:** every stop time
  is checked against the end of the files' coverage
  (`SimulationService.check_stop_time`, called before each
  `ConfigureStopTime` in the service and the mission engine) and refused
  with a message past it.
- **Not SPICE's RETURN error action:** with it a lookup outside the files
  would give a run silently wrong frames, which is worse than stopping.
- **Kept for later:** `earth-orientation --import` still checks only the
  header; such a file is now never loaded (it covers nothing), but the
  import could refuse it. Its tests use header-only fake files, so this
  waits for a change of its own.

## A template is a source, not a file to save over (2026-10-27)

The user: "Continue as per your recommendations" (the audit's critical
findings first).

- **Guarded at the save, not at the open:** a template opened from Home
  stays the scenario's current path, so the top bar's "template 22", the
  layout kept per scenario, the Monte Carlo archive folder and the folder
  relative mesh paths resolve against all stay as they are. **Save** on
  a template goes to **Save As** instead, and **Save As** refuses the
  templates folder (`_is_template` in `gui/main_window.py`).
- **Where Save As starts:** the home folder under the template's file
  name, so the user's copy keeps the template's recognisable name until
  they change it.

## Mean elements at the critical inclination (2026-10-27)

The user: "Continue as per your recommendations" (the audit's critical
findings first). It changes what the tool computes, near the critical
inclination only; the overhaul's "UI only" rule covered the overhaul,
which has ended.

- **Basilisk's map, evaluated at the band's edge:** within 1 deg of
  63.435 or 116.565 deg, `clMeanOscMap` is called at the nearer edge and
  the inclination difference carried across (`engine/mean_elements.py`),
  both ways (osculating to mean for the lifetime's start, mean to
  osculating for its density ring) and for the mean-element series of a
  run. Outside the band it is Basilisk's map, bit for bit, so nothing
  else changes.
- **Not an orbit-averaged map everywhere:** averaging the J2 motion over
  an orbit has no singular terms and is the test's reference, but it
  would change every lifetime slightly and cost a propagation per state;
  the edge evaluation agrees with it within 0.4 km of perigee (600 km
  orbit) and 0.7 km (Molniya) across the band.
- **1 deg:** at the edges (62.4 and 64.4 deg) the plain map is within
  about 1 km of the average for a Molniya orbit (0.5 km at 62 deg, 1.1 km
  at 63.9 deg); nearer the critical value it grows (17 km at 63.4 deg).
  Narrower bands were not tried.

## The propellant budget's rocket equation (2026-10-27)

The user: "Continue as per your recommendations", after the audit of
2026-10-27 recommended fixing its critical findings first. This is the
first change since the UI overhaul (1.3.0) to what the tool computes; the
overhaul's "UI only" rule covered the overhaul, which has ended.

- **The mass before each burn:** the budget applied `m * (exp(dV / Ve) - 1)`
  with `m` the phase's starting mass. That form is the rocket equation
  only for the mass after the burn; from the mass before it the
  propellant is `m * (1 - exp(-dV / Ve))`. With the total propellant in
  the starting mass, the old form gave `P = (D + P)(e^x - 1)`, which has
  no solution from `e^x = 2`. The guideline's own text was not consulted
  (it is not in the repository); the physics decides, and the module
  docstring says what changed.
- **In order:** each contributor burns from the mass the ones before it
  left, so the total is the rocket equation for the whole mission
  whatever the order of the rows; a row with a given propellant (from a
  run, attitude control, ignitions) lowers the mass too.

## The first run's end without plotly's first-use cost (2026-10-26)

The user: "Continue" (the next item offered: the end of a run, K-23).

- **Plotly warmed in a worker:** plotly builds its figure classes, their
  validators and narwhals' plugins on first use; the first run's first
  plot paid 0.2-0.3 s for it on the GUI thread. When the start-up read has
  finished, `_FigureWarmUp` (beside `_SpaceWeatherWarmUp`, kept and
  stopped the same way) builds and serialises one small figure laid out
  as the Results page lays one out (`results_widget.warm_up_figures`):
  plain Python, nothing of Qt, its figure thrown away. A run that ends
  before the warm-up has (a few seconds after start-up) still pays for
  what is not loaded yet, as before.
- **Kept:** the pauses after the last step of a run's end (25-55 ms on
  `develop`, 25-38 ms here) are Qt's own event processing while the
  workers save the run, summarise it for Overview and explain it; no
  Python on the GUI thread stands out in them.

## Opening a template faster (2026-10-26)

The user: "Continue" (the next item offered: opening a template, K-23).

- **One check per scenario loaded:** `from_scenario` sets each field, and
  each set was an edit that validated the whole scenario; it now fills
  every field, then validates once (`ScenarioEditorWidget._loading`).
  The problems shown are those the last of the four checks gave.
- **The labels prepared at idle:** the titles for messages about a
  spacecraft are the same for every editor, so they are kept per process
  (`spacecraft_editor._label_titles`). When start-up has settled (the
  reference data read), the main window starts their form as its hidden
  child; it builds a section per event-loop turn, as a page's form does,
  and is read and deleted when complete. A title asked for first still
  finishes the form at once. Its longest turn is the Power section,
  about 0.1 s, once per process, while nothing else happens.
- **The last observed day kept on the data:** `real_data_path` looked
  through every day of each space-weather file for its last observed
  day on every edit-time check (10 ms); `CelestrakData.last_observed`
  finds it once. The engine's result is the same day; nothing computed
  changes.
- **No window size for an embedded Environment form:** like a page's
  spacecraft form, it takes the page's size, so the content is no longer
  measured for a window (8 ms per open).
- **Kept:** the Environment form is still rebuilt on each load (about
  30 ms, with 12 ms of it taking the old form out of the window); loading
  new values into the same form would need a second way to fill it,
  kept in step with the constructor.

## The messages' titles without a hidden form (2026-10-26)

The user: "yes, remove the hidden label form" (K-19).

- **Titles kept as text, the form deleted:** a message about a spacecraft
  whose page has no form was worded from a new spacecraft form built
  for that and kept hidden. `SpacecraftLabels` builds one at the first
  title asked for, reads the title of every code of the schema (197:
  the spacecraft's fields, its sections' fields, the orbit's), keeps
  them and deletes the form. The titles are the same (a test compares
  them with a form's for every code and for template 18's messages).
- **A code outside the schema** (a key of `fsw_params`, a list item's
  field) builds a form once for it; its title is kept too.
- **Most words need no form:** `field_title` answers "" at once for a
  word that names no spacecraft field; that part is now a function both
  use, as is `problem_text`, so the two cannot drift apart.
- **The ground station's label form stays:** it is small.

## The spacecraft page, a section at a time (2026-10-26)

The user: "yes, build the spacecraft page a section at a time" (K-23).

- **The code of each section moved unchanged** into its own method; the
  pages are made first, in their tab order. A script cut the constructor
  at its section headers, so no line inside a section was retyped.
- **Built in the order they always were:** a section's code may use the
  widgets of the sections before it (it ran after them before). So
  showing a later section builds every section before it too.
- **Orbit / mass at once, the rest one per event-loop turn:** the page
  is complete about a second after it is shown, so a run, an undo or a
  save never meets a half-built form in practice. When something does
  read a field of a section not built yet (`to_dataclass()`,
  `field_widget()`, a handler), `__getattr__` builds the rest first: no
  reader needs to know.
- **Not left unbuilt until visited:** `to_dataclass()` reads every
  section after every edit; keeping a section unbuilt would mean
  reading its fields from the config instead, field by field, where a
  field put in the wrong section would quietly lose an edit.
- **The orbit-only adjustments apply per section**, each group once,
  as its section is built; `finish_form` runs per section.
- **The dialog used on its own builds every section at once:** it sizes
  itself from all of them.
- **No gain for the theme switch:** every section is built a second
  later and Qt restyles them all (K-19 stays).

## The theme switch (2026-10-26)

The user: "yes, start on the theme switch" (K-19).

- **Set Fusion only while no sheet is set:** with a style sheet set,
  `app.style()` is Qt's style-sheet style and its `name()` is empty, so
  the check for Fusion failed on every switch and set it again, a full
  restyle before the sheet's. The sheet only ever goes on top of Fusion.
- **The sheet is still cleared before the new one:** measured again, a
  switch without clearing took 3.5-4.1 s, against about 0.5 s with it.
- **What is left is per widget, not per rule:** a one-rule sheet costs
  about 0.3 s of the 0.5 s; the full 195-rule sheet adds 0.1-0.15 s. Only
  97 of about 2,700 widgets are shown, but Qt restyles every one. Fewer
  hidden widgets (the spacecraft page built a section at a time) is the
  next step; trimming the sheet would gain little.

## After the overhaul (2026-10-25)

The user: "fix the engine messages and the shortcut conflict".

- **Engine messages name Settings > Reference data:** the M2a decision
  kept "Tools > Reference Data" in two engine messages because the engine
  did not change during the overhaul. The overhaul is done and the user
  asked for it: the support-data error and the Earth orientation warning
  now name where the dialog is. Text only; nothing the engine computes
  changes, and no output file carries either message.
- **Alt+Backspace is Clear Time Cursor's alone:** Qt's standard Undo keys
  include Alt+Backspace on Linux and Windows, and a key bound to two
  enabled actions fires neither ("Ambiguous shortcut overload"), so once
  there was anything to undo, Alt+Backspace did nothing. Undo keeps its
  other standard keys (`Ctrl+Z`); Clear Time Cursor keeps Alt+Backspace,
  the key the manual, tips and DESIGN document. A test now checks that no
  two commands share a key.

## M9 Final pass (2026-10-22)

Recorded after measuring, before the changes. `scripts/measure_ui_baseline.py`
was run on this machine for both the code the plan's baseline was taken on
(`66949b4`) and M8: the machine is slower than when the plan was written
(the same code now starts in 2.5-2.8 s, not 1.69-1.97 s), so M9 compares
the two on this machine, in the same session, as the plan's §3 asks ("re-
measured on the same kind of machine").

- **Before and after on one machine:** `docs/ui/perf_after.json` holds the
  M9 run and `docs/ui/perf_baseline_rerun.json` the baseline code's run
  of the same day; BEFORE_AFTER.md compares those two, and quotes the
  plan's original figures beside them.
- **The spacecraft forms:** M8 made the first visit to a spacecraft page
  and the editor dialog slower than before the overhaul (671 against 541
  ms; 554 against 415 ms). Each tab page was built, then moved into its
  scroll area, then into the tabs, and the embedded dialog turned into a
  widget last: each move restyles the whole tree under the app's style
  sheet. Pages are now placed before they are filled, and an embedded
  form is a widget from its first line; an embedded form skips measuring
  its tabs for a window size it never takes.
- **Start-up:** the reference data inventory (1.5 s of the window's
  constructor: importing Basilisk, parsing the space-weather file, hashing
  files) was computed twice on the GUI thread, for the Reference data
  dialog and the status bar. It is now read once, after the window is up,
  in a spawned child process (`gui/reference_data_process.py`, as the
  Monte Carlo batch runs): on a worker thread it still held the
  interpreter for most of that time, stalling the new window for up to
  0.7 s. The child returns the Basilisk version with the files, so the
  status bar does not import Basilisk on the GUI thread either. The status
  bar and the dialog fill in when it is done (about 1.5 s later); the
  dialog's Refresh and the refresh after a download stay synchronous, as
  before. Closing the window ends the child (it only reads). Checking a
  scenario's dates needs the space-weather file parsed in the window's
  own process, which the old start-up did as a side effect: without it
  the first scenario opened took 0.5 s longer. A worker thread parses it
  once the child has answered; part of that parse holds the interpreter,
  so it costs one stall of about 0.2 s, about 1.3 s after the window
  appears, where it cost 0.5 s on the first open.
- **The 50 ms first visit** is not reachable for the spacecraft page
  without building its tabs lazily, a rewrite of a 2,000-line editor whose
  tabs read each other's fields: not done; the measured value is recorded.
- **Keyboard-only walk** (`tests/gui/test_keyboard_walk.py`, new): each
  area by its shortcut, then Tab must reach every control in it that takes
  the keyboard, and never land on a hidden widget. An exclusive group of
  buttons (radio buttons, a segmented control) is one stop, chosen with the
  arrows, as in Qt. It found a keyboard trap: Tab in the scenario's
  description typed a tab instead of leaving it, so nothing after it (the
  Form · JSON toggle, the area's commands, the rest of the page) could be
  reached by Tab. Plain-text boxes now pass Tab on (as the JSON view and
  the script and parameter boxes already did), and read-only tables do
  too (the arrows move in them); tables that are edited (facets, data
  handling) keep Tab from cell to cell, which leaves the table after the
  last cell.
- **The garbage collector after a run** (70-83 ms full collections, held
  from M6b): not changed. Tuning the collector's thresholds would move the
  pauses, not remove them, and freezing the run's objects would keep them
  alive for the session; recorded with the end of a run's measurement.
- **Version:** the plan says 1.2.0, written before 1.1.1 and 1.2.0 were
  released (2026-10-21). The UI overhaul's release is **1.3.0** in every
  version file. Tagging and releasing stay the user's.

## M8 Reports, exports and Settings (2026-10-22)

Recorded before coding, after reading the exports of §5.3, the Reports
area (Flight Software only) and the Settings page (appearance, reference
data, layout, keyboard and About as commands).

- **Reports › Exports**, the area's first page: every export of §5.3 in a
  `DataTable`: what it writes, its format, where it is made (the view and
  its button), the default destination, the provenance written beside
  it, and when this machine last wrote one (UTC). Enter or a double-click
  opens the view that makes it. The time is kept by a small export log
  (`gui/export_log.py`, the app's settings, not any file it writes),
  which each export records after it succeeds.
- **The per-view Export buttons stay as they are.** The plan's "one
  Export button per view opening the same export sheet" would move every
  view's buttons for no new export; Reports › Exports is the one place
  that lists them all. Recorded here as not done.
- **Export files byte-identical to 1.1.0, tested:** a script
  (`scripts/make_export_references.py`) writes each export the GUI makes
  from fixed inputs, through the same engine and widget functions; run on
  1.1.0's code (commit `1c7d76f`, the 1.1.0 release) it wrote the
  references, kept in `tests/data/exports_1_1_0.zip` (a zip: the
  repository's line-ending and end-of-file rules would change a CSV's
  CRLF or a file that ends without a newline), and a test runs it on this
  code and compares every byte. The `.obj` comes from a model of simple
  shapes made in the script (no template has a model). Run on 1.2.0's code
  (commit `c92f900`, the latest release) the script writes the same
  bytes. Covered: the results CSVs (with their
  provenance), the events CSV, the Mission Output CSV, the Monte Carlo
  table, the budget CSV, the `.obj` model and the SIL report. Not
  covered, with the reason: the PNG and SVG plots (drawn by the web
  engine, not by this code), the flight-software project (already
  checked byte for byte against Basilisk's files by `test_fsw_export.py`)
  and the Vizard file (written by Basilisk during a run).
- **Settings › Appearance** adds:
  - **UI scale** 90, 100, 110 or 125 %, applied at the next start
    (`QT_SCALE_FACTOR` is read once, before the window exists; a live
    change would need every size in the theme recomputed and every page
    laid out again). The page says so.
  - **Reduce motion:** toasts fade in and out over 150 ms (the design's
    120-180 ms); with reduce motion on they appear and go at once. It is
    the only motion the app has.
- **Settings › Vizard:** the Vizard program's location, with Browse and
  Clear (the one `vizard_launcher` remembers).

## M7 Timeline and plots (2026-10-22)

Recorded before coding, after reading the Timeline and timing it with
10,000 events (`scripts/measure_timeline.py`, new; synthetic passes and
eclipses over a year, given to the Timeline's own entry point): showing
them held the window about 730 ms, a search keystroke 2.3-2.6 s, clearing
it about 1.5 s, a zoom 1.6-1.7 s. The table builds a `QTableWidgetItem`
per cell and sorts them in Python; the timeline draws every event on
every paint and looks for the one under the pointer among all of them.

- **The table is a `DataTable` whose rows are made when shown:** the
  events in a sequence that formats a row when the view asks for it, and
  sorts itself by each column's values with NumPy (a header click), so
  neither filling nor sorting walks every cell. Its text, columns and
  export stay as they are.
- **The search** matches against each event's text made once per run, not
  on every keystroke.
- **The timeline draws what it can show:** per lane, the events in view
  (found by bisection), merged where they fall on the same pixels; the
  event under the pointer is found by bisection too.
- **A UTC axis with `Z`** when the run has an epoch (ticks at round UTC
  times: "08:00Z", the date at midnight), elapsed time without one.
- **Zoom and pan:** the wheel zooms around the pointer (as now);
  Shift+wheel, a horizontal wheel and a right- or middle-button drag pan;
  `+`/`-` zoom, the arrow keys pan, `0` or Home fits. A left click or drag
  still sets the time cursor, which the plots share (as now).
- **Lanes** stay one per spacecraft and kind, a pass's per station and
  spacecraft (as now).
- **Plots:** the display decimation (`_MAX_PLOT_POINTS_PER_LINE`) and the
  time cursor linked across the grid are already there and tested; M7
  adds a test that an export writes every sample.
- **Measured after** (`scripts/measure_timeline.py`, three runs): showing
  10,000 events held the window 35-38 ms, a search keystroke 37-39 ms,
  clearing it about 10 ms, a zoom 5-8 ms, a paint 7-13 ms; at most
  39.4 ms. Met ("without a stall over 50 ms"). Besides the lazy rows and
  the lanes, it took: column widths from font metrics over the first
  rows (Qt's own sizing asked for every role of every sampled cell), no
  filter proxy for a table its owner filters (the proxy called Python
  once a row), one UTC conversion per 128 rows shown (each call costs
  about 4 ms whatever its length), and the axis's UTC span converted once
  a run, interpolated between its ends (TDB - UTC drifts milliseconds
  over a run; the labels are to the minute).
- **The 3D model view** is already created only in the 3D model editor,
  opened on request: lazy and opt-in as asked. Every measurement in this
  overhaul runs with software rendering (offscreen, no GPU), the case
  `--disable-gpu` forces.

## M6b The tables and analysis views (2026-10-22)

Recorded before coding, after reading Output, Monte Carlo, Compare, End
of Life, Budget and the Dashboard, and timing the end of a run (template
23, the second and third runs of a session: 81-132 ms in one slot, of
which showing the Output page 32-54 ms, the results view 20-33 ms and
filling Output's table 12-22 ms).

- **One `DataTable` component** (`gui/data_table.py`): a `QTableView`
  over a `QAbstractTableModel` with the table rules (CLAUDE.md, Tables):
  a sticky header, numeric columns right-aligned in the numeric font with
  their unit in the header, Ctrl+C and Copy as TSV, a column-visibility
  menu on the header, row hover, no zebra, and an empty state with its
  primary action. Filtering is a predicate the view gives it (Output's
  filter shows report columns or rows); sorting is on where rows have no
  order of their own. Group rows span the table.
- **Output and Monte Carlo move onto it.** Each keeps its text, its
  filter and its export as they are; a test that read a `QTableWidget`
  item reads the table's cell or header instead (TEST_CHANGES).
- **Compare, End of Life, Budget and the Dashboard (Telemetry)**, as
  built: Budget's three tables and Compare's three are a `DataTable`
  (Budget's worst case a bold row, a row picked with `row_chosen`;
  Compare's "(same)" cells muted). Compare's run switcher is its list of
  runs to tick, as before. End of Life already shows its results as
  tiles, and the Dashboard's group boxes are headings, not frames, since
  M4a's style sheet: both are kept as they are.
- **The end of a run, as built:** shown in steps, one an event-loop turn
  4 ms apart (the results view; the dashboard, timeline, run record and
  analyses; Output; the view shown), each 17-31 ms after the first run of
  a session. The run's save starts 1 s later (its zip writing shares the
  interpreter with the GUI thread and doubled the steps' time beside
  them). A new run, clearing the views or closing takes the steps left.
  Tables size their columns once when filled (ResizeToContents measured
  every cell at every layout).
- **Measured after** (`scripts/measure_run_end.py`, template 23, two
  sessions of three runs): the run's own slot 21-36 ms after the first run
  (was 102-110 ms); the longest stall in the 3 s after it 47-57 ms in most
  runs, up to 151 ms when a full garbage collection (71-83 ms) fell in it.
  **Not met** ("no stall over 50 ms"): the remainder is the collector and
  the Overview's worker sharing the interpreter; M9's performance pass
  holds it. The first run of a session: 197-268 ms (the first results
  view and figure).

## M6 Results overview and analysis views (2026-10-22)

Recorded before coding, after reading the Results views and timing a plot
switch (`scripts/measure_plot_switch.py`, new; template 23, twelve plots
shown one after the other in the selected cell, two runs on M5b's code):
each switch held the window 59-97 ms (median 72-76 ms), the first one, a
three-line plot, 275-304 ms; the plot was drawn about 400 ms after the
click (354-692 ms). Nearly all of it is building the Plotly figure in
Python (its two `update_layout` calls validate every property), then
writing the page and reloading it with plotly.js.

- **Split before starting, as M4 and M5 were (§8, "Scope"):**
  - **M6a, the Overview and the plot view:** Results › Overview with the
    run's metric cards and its provenance in a popover; the plot page
    persistent, plotly.js loaded once; switching plots under 50 ms, which
    is also what is left of the end of a run's stall (M5a).
  - **M6b, the tables and analysis views:** Output and Monte Carlo as a
    `DataTable` (a `QTableView` with the table rules), Compare's run
    switcher, End of Life, Budget and Telemetry from the components.
- **Overview cards come from `engine.run_summary.summarize`,** as
  Compare's summary does: one card per figure, its label, value and unit
  (in the header of no table: on the card). A card is coloured only where
  the scenario sets the threshold: the lowest link margin below 0 dB (the
  margin already includes the required Eb/N0) and the battery's lowest
  charge at 0 are critical, with an icon and a word; every other card is
  neutral. The figures are computed off the GUI thread.
- **One persistent plot page:** loaded once with plotly.js; a change of
  plots, layout or theme sends the figures' JSON to it (`Plotly.react`),
  with no reload. The page tells the view when a plot is drawn (and
  whether Plotly drew it without an error). A theme switch loads the page
  again (its fonts and surface).
- **Figures are built once and kept** per plot until the result, the
  theme, the x axis, the comparison or the event bands change; showing
  another plot builds only that one. A figure is built in one validated
  construction (its traces and layout together), with the same JSON as
  before (checked on every plot of a template 23 run, three x axes, both
  themes: the same objects; only the order of keys in the text differs,
  and no file holds that text), so exports and every saved image are
  unchanged.
- **The layout is saved after the click,** not in it (a timer; the
  QSettings write took about 15 ms). Reading a saved layout, hiding the
  view and quitting write what is pending first.
- **Start-up's objects leave the garbage collector's full collections**
  (`gc.freeze()` once the window is up, after a collection). A full
  collection walked them all: 190-234 ms on the GUI thread wherever it
  fell, a plot switch or a keystroke. Freezing again after each run would
  keep a whole simulation's cyclic garbage for good, so it is done once.
- **Measured after** (`scripts/measure_plot_switch.py`, which freezes as
  the app does; four runs, 48 switches): a switch holds the window at
  most 34.4 ms (median 19-22 ms), and the plot is drawn after about
  110 ms (median 106-126 ms; was about 415 ms). Met.
- **The end of a run stays held, now for M6b** (`scripts/measure_run_end.py`):
  102-110 ms after the first run of a session (M5a: 152-163 ms; the first
  311 ms, was 519 ms). Of what is left, the Output page (filling its
  command table and showing it) is about half; M6b rebuilds it as a
  `DataTable`.

## M5b The Run area's controls (2026-10-22)

Recorded before coding, after reading the run mode menu, the Vizard
dialog, the SIL prompts and the Monte Carlo folder picker.

- **A Run page, first in the Run area,** holds what the next run uses,
  for the mode chosen: the options that were menu entries and dialogs.
  End of Life, Budget, History and the Log stay beside it.
- **The mode is a segmented control, Single · Monte Carlo · SIL,** in the
  Run area's header, replacing its "Single run ▾" menu button. The top
  bar keeps its compact mode menu: it is on every area, where three
  segments would take the room of the title.
- **Single:** Live plot as a check box (the same command as before, with
  its palette entry), and the Vizard options as a form on the page,
  applied as they are edited (the dialog's form, embedded). Vizard
  Configuration opens the page there; Launch Vizard stays a command.
- **Monte Carlo:** the archive folder as a field with Browse...,
  remembered per scenario (by its file, or its name when unsaved); Run
  uses it without asking. An empty field still asks with the folder
  picker (a chooser, not a question). Overwriting a folder that holds a
  batch stays a confirmation, the one destructive question (§5).
- **SIL:** the spacecraft whose flight software runs (those that can be
  exported) and the run's options (the SIL dialog's form, embedded), on
  the page; Run starts it without a prompt. With none that can be
  exported, the page says why and where to fix it.
- **The header's Live plot and Vizard Configuration buttons go:** they
  are on the page. Their commands stay in the palette.

## M5 Run and logs (2026-10-22)

Recorded before coding, after reading the run, the run store and the
Log, and timing the end of a run (template 23, a second run in the same
window: 286 ms in one slot, of which the results view 75 ms, the run
list 75 ms, Compare 58 ms, saving and pruning 22 ms; the first run of a
session 978 ms).

- **Split before starting, as M4 was (§8, "Scope"):**
  - **M5a, the end of a run and its record:** saving and pruning in a
    worker; the rest of the end of a run broken into steps, none of which
    holds the window long; History (the runs, loaded in a worker); the
    Log's records of each run, in JetBrains Mono, with its filter, search
    and copy.
  - **M5b, the Run area's controls:** the mode as a segmented control,
    and the options inline (Live plot, Vizard, the Monte Carlo archive
    folder, SIL) instead of menus and dialogs.

  Each is one pull request a reviewer can follow; M5a carries M5's
  performance criterion.
- **History needs no new file field.** A saved run already has when it
  started (its provenance's `run_started_utc`) and finished, whether it
  was cancelled, and its provenance: the duration and the status come
  from them. File formats stay as they are (the overhaul's rule). Runs
  that failed, and Monte Carlo batches, are not in the run store; History
  lists them for the session they ran in, from memory.
- **The results view stays as it is in M5:** it rebuilds its plots when a
  run ends, and M6 rebuilds that view. M5 moves it to its own step after
  the others, so it is the only one that can hold the window; what it
  costs is measured and written down.
- **Measured after:** the end of a run holds the window 152-163 ms (was
  301-323 ms; the first run of a session 519 ms, was 788 ms), nearly all
  of it the results view's figure. Not met; M6 holds it.
- **Compare is refreshed when it is shown,** not at the end of every run
  (its plot cost 58-113 ms there); the results view redraws in
  `set_runs` only when the run compared changes.
- **History's double-click compares** the run with the one shown in
  Results: Results shows one run at a time, and drawing another dashed
  beside it is what it already does.
- **The Log's run records come from the GUI** (`spacemissionstudio.run`):
  the engine logs nothing at INFO during a normal run, and it is not
  touched.

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
- **Not met, recorded:** the keystroke itself is at most 47.2 ms (M4a:
  86.4 ms), but a stall over 50 ms still follows a keystroke on about
  one template pass in 40, at up to 77.3 ms, not on the same template
  twice across sweeps (M4a's code: up to 140.5 ms). The garbage
  collector, the autosave and the rendering are ruled out; the cause is
  not found. M9's performance pass holds it (the plan's §7 status has
  the numbers).
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
