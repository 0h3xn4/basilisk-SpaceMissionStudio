# The definition of done: how it is checked

The transparency work had four criteria
([transparency audit, Section 9.4](transparency_audit.md#94-how-the-definition-of-done-will-be-checked)).
This page says, for each, what checks it, where the evidence is, and
what is left to a person. It is the checklist for a design review of the
tool itself.

| Criterion | Checked by | Status |
|---|---|---|
| Trace any number in under a minute | The walkthrough below: every output of the audit's Section 6, and the one click that opens its calculation; the timing with an engineer who did not build the tool | Every output has its calculation; **the timing is the team's to do** (below) |
| Change any assumption without editing code | Every parameter of the registry is set by a test (`tests/test_config.py`: each parameter has a case, each choice each of its models); the Assumptions page and a project YAML file set them; the provenance records each value changed | Checked by the tests, on every commit |
| Reproduce a colleague's result from an exported file | `tests/test_reproduction.py::test_a_bundle_made_on_another_computer_reproduces_here`: a bundle made on Linux (`tests/data/bundles/linux_two_body`) is reproduced by `spacemissionstudio reproduce`, within 1e-6 of each series' scale, by CI on Linux and on Windows | Checked by CI, on both platforms |
| Explain the result in a design review | The calculation of every figure (the walkthrough below) with its equation, inputs, sources and standard; `docs/models/`, one page per model with its rules, assumptions and validation; the JSON records of every analysis (`--out`, **Export JSON...**, `spacemissionstudio.api.record`) | Documented; the review itself is the team's |

## Trace any number: the walkthrough

For each output of the audit's Section 6, where its calculation opens.
In the app it is one click on the output; on the command line one option.

| Output | In the app | On the command line |
|---|---|---|
| Results > Overview cards (delta-V, propellant, mean semi-major-axis change, lowest link margin, battery, passes, eclipses, data) | Click the card: the Calculation panel, with the series, the sample and the rule (the mean semi-major-axis change opens the mean elements' own calculation) | `run --explain` |
| Lifetime, re-entry date, 5- and 25-year verdicts | End of Life > **Show calculation**: the orbit, the mass, the ballistic coefficient (Cd and area used), the density model and files, the burn and each rule | `lifetime --explain`; `lifetime --out` |
| Propellant budget | Budget > **Show calculation** on a row (none selected: the total): the mass before the burn, the exhaust speed, the rocket equation, the margin and its source | `budget --explain`; `budget --out` |
| Launch-delay sweep, altitude trade | Budget: a case's row picks its budget, then **Show calculation**; each case's drag ratio is in the record | `budget --launch-delays --out`, `budget --altitudes --out` (every case) |
| Link margin, lowest margin, the Dashboard's link budget | Dashboard > **Show calculation** beside the link budget: EIRP, path loss, pointing loss, atmospheric gases, received power, noise, Eb/N0 and the required margin, with the run's range and elevation | `link-budget --explain` |
| Orbital elements, mean elements | The mean elements' calculation from the Overview card; the plots name osculating or mean (first-order J2) | `run --explain` |
| Events (passes, eclipses, burns) | Timeline > **Show calculation** on the event: the series and the rule that says it is on, the samples either side | `events.csv` has the times and values; the rule of each kind is in [Reading a run's results](models/reading-results.md#how-each-event-was-found) |
| Monte Carlo spreads | The Monte Carlo page names the statistic (population or sample) and the runs used | `monte-carlo` prints it; `archive.provenance.json` |
| Pre-run pass prediction, Explain's tiles | Scenario > Overview (Explain): the model and its parameters under each section | `validate` prints the pre-run warnings with their rules; the pass model is in [Pre-run checks](models/pre-run-checks.md) |
| SIL residuals | The SIL panel: each signal's unit; the largest residual names its signal | `sil` |
| Provenance | Results > Overview > **Provenance** > **Show everything recorded** | `provenance.json` |
| Run warnings | Each warning with its rule, why, the value found, the limit and the fix | Printed with its rule |

### The timing (the team's)

The criterion asks for under a minute, timed with an engineer who did not
build the tool. That needs a person. To run it: open template 22 and run
it; for each row above, start a stopwatch, find the output, open its
calculation, and stop when the engineer can name the equation and where
each input came from. Write the times in this table and keep it with the
review.

| Output | Time [s] | Engineer | Date |
|---|---|---|---|
| (each row above) | | | |

## Change any assumption

- Every named rule, margin and model is a parameter
  (`spacemissionstudio/config/parameters.py`, `config/models.py`), listed
  with its value, unit, source and rationale on the Assumptions page and
  by `spacemissionstudio assumptions`.
- `tests/test_config.py` has a case for every parameter that sets it and
  checks that the change reaches what it controls;
  `test_every_parameter_has_a_case_that_sets_it` fails for a parameter
  without one.
- A run, a lifetime, a budget and their records list each value the
  project file changed (`provenance.configuration`).
- Plugins add parameters, rules and models without editing the tool
  ([Add your own models and rules](user-manual/plugins.md)).

## Reproduce a colleague's result

- `spacemissionstudio run scenario.json --out-dir bundle --bundle` makes a
  bundle: the series, the scenario as run, the provenance, and a copy of
  every file the scenario refers to, with their SHA-256.
- `spacemissionstudio reproduce bundle --out-dir again` runs it again and
  compares every series within 1e-6 of its scale, and says what differs:
  versions, platform, data files.
- The test above reproduces a Linux bundle on each CI platform.

## Explain the result

- [Models, rules and assumptions](models/README.md): one page per model,
  with what it computes and how, its rules with values, units and
  sources, its assumptions, what it does not cover, and the tests that
  check it.
- The calculation of each figure, in the app and as text
  (**Copy**), and in each record's `traces`.
- [The Python API](api.md) for the same figures from a script.
