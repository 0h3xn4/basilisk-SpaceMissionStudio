# Reading a run's results

How SpaceMissionStudio turns a run's recorded series into the figures,
events and status marks you read:
- the headline figures (Results › Overview, Compare, `run`);
- the events (Timeline, `events.csv`);
- the critical marks on the overview's cards;
- the mission dashboard's badges.

Code: `spacemissionstudio/engine/run_summary.py`, `engine/events.py`,
`gui/results_overview.py` and `gui/mission_dashboard_widget.py`. How to use
them: [Read the results](../user-manual/read-the-results.md).

Nothing here is simulated or estimated: each figure and event is read
from what the run recorded, and appears only when the run recorded what
it comes from.

## The run's own values

A run is read with the values it was run with. The parameters below, and
`link.required_margin_db`
([RF link, data handling and power](link-data-and-power.md)), are read
back from the run's provenance (`configuration`). A run kept in the
history and shown later is judged by its own rules, not by the
configuration open now. A run without provenance uses the defaults.

## Headline figures

| Figure | Read from |
|---|---|
| Run length [h] | The last recorded sample |
| Delta-V [m/s] | The cumulative delta-V of the station-, GEO-, phasing-keeping, constant-thrust and ROE formation controllers, at the end |
| Propellant used [kg] | The drop of every recorded propellant mass (the controllers' tanks, the fuel tank) |
| Mean semi-major axis change [km] | The mean semi-major axis averaged over the last `sma_window_orbits` (1) orbits, minus its average over the first. None for a run shorter than two windows |
| Lowest link margin [dB] | The lowest margin while a station is in view |
| Lowest battery charge [W*h] | The battery's lowest stored energy |
| Passes, contact time [min] | The pass events below |
| Eclipses, eclipse time [min] | The eclipse events below |
| Data downlinked [Gbit] | The data-handling ledger, at the end |

**The mean semi-major axis change** averages over whole orbits.
First-order mean elements still wobble at the orbital period, so a
difference of two single samples would carry that wobble. The
orbit's period comes from the median semi-major axis and the central
body's GM, as the run recorded it.

### How each figure was computed

Each figure carries its trace (`engine.trace`), written by the summary
from the values it computed with:
- the equation, for example `da = (mean of a over the last window - mean
  of a over the first) / 1000`, with `window = N * 2 pi sqrt(a_med^3 /
  mu)`;
- each input with its unit and source: the series it was read from
  (`last run:`) and which sample (its last, its first, or the time of
  the lowest value), the parameter (`parameter:
  results.sma_window_orbits`), or the constant;
- the values on the way: each controller's delta-V, each tank's mass at
  the start and the end, the passes and contact time per station, the
  umbra and penumbra eclipses.

The semi-major axis change also opens how the mean elements were made
([Environment and data](environment-and-data.md), "Fixed rules").

The central body's GM is the run's own when its provenance recorded it.
Otherwise it is Basilisk's for the body the run's frame is centred on,
or the Earth's, and the trace says which.

`run --explain` prints the figures and their traces after the run. In
the app, a card of Results › Overview opens its figure's trace in the
Calculation panel. `tests/test_trace.py` recomputes each figure from its
trace's inputs alone.

## Events

Each event is a contiguous run of samples in which a recorded series says
the event is on, from its first to its last such sample.

- **Pass:** a station's `has_access` is on. The detail gives the highest
  elevation.
- **Eclipse:** the illumination factor is below 1, so any shading counts.
  It is listed as **umbra** when its lowest sunlight is below
  `umbra_sunlight_fraction` (1 %), else as **penumbra** with its lowest
  sunlight.
- **Burn:** a station-keeping controller's burn flag (east-west and
  north-south for GEO), or a phasing or ROE formation controller's burn
  state. Each carries the delta-V it gave.
- **Thruster firing:** any thruster's on-time is above zero.
- **Mode:** comms pointing (ground station or Sun), and the phasing and
  ROE controllers' drifts.
- **Downlink:** a window in which the link closes and data went down, with
  how much.

### How each event was found

`events.trace_of(result, event)` gives an event's trace (`engine.trace`),
from the run, when it is asked for:
- **The span:** the series and its rule (for example `has_access != 0`,
  `illumination_factor < 1`, `round(state) == 1` for a phasing burn), the
  first and last samples where the rule is true (`t_start`, `t_end`), and
  the samples either side where it is false (`t_before`, `t_after`). The
  event began between `t_before` and `t_start` and ended between `t_end`
  and `t_after`: its times are known to within a recording interval.
- **What it carries:**
  - a burn's delta-V: the controller's cumulative delta-V at the sample
    after the burn less at the sample before it;
  - a downlink's data: the data downlinked by the window's last sample
    less by the sample before it;
  - a pass's highest elevation, at its sample;
  - an eclipse's lowest sunlight at its sample, and umbra or penumbra
    against `umbra_sunlight_fraction`.

Extraction and the trace use the same rules (`_BURN_SOURCES`,
`_MODE_SOURCES` and the `_on_*` functions). `tests/test_trace.py` finds
every event of a run again from its trace alone. In the app, **Show
calculation** on the Timeline opens the selected event's trace.
`events.csv` is unchanged.

## Critical marks

A card on Results › Overview is neutral unless the run crosses a limit
the scenario or the project sets. A critical card shows an icon and its
words, as well as a colour.

- **Link margin:** the lowest margin below `link.required_margin_db`
  (0 dB): "Link margin below 0 dB".
- **Battery:** the lowest charge at or below `battery_critical_fraction`
  (0) of the battery's capacity. At 0 this means an empty battery:
  "Battery empty". With a project's depth-of-discharge limit, for example
  0.3, it reads "Battery at or below 30% of capacity". The capacity is the
  scenario's as run; without it, only an empty battery is critical.

The mission dashboard reads the moment under the time cursor:
- **Pointing:** "Converged" while the comms-pointing error is below
  `pointing_converged_deg` (5°), else "Slewing".
- **Link:** "Link OK" while the link closes by `link.required_margin_db`.
- **Battery:** the state of charge, as a share of the capacity from 0 to
  100 %. The net power is marked critical while negative.

## The run's warnings

A run's warnings say how to read its results; none changes them. Each
names its rule (`engine/findings.py`): what the rule is, what it found
against its limit, why it matters and the fix. Results' warning note
shows them on hover, and `run --explain` and `lifetime --explain` print
them. A saved run keeps them (`run.json`'s `warning_rules`, beside the
text).

| Warning | Rule | Given when | Limit |
|---|---|---|---|
| A re-entry, the run stopped | `run.reentry_stopped` | a spacecraft is below the run's re-entry altitude | `dynamics.reentry_altitude_km` ([Dynamics](dynamics-run-control.md)) |
| A re-entry in the recorded series | `run.reentry_after` | a recorded altitude is below it, the run not stopped | `dynamics.reentry_altitude_km` |
| Energy or angular momentum drifted | `run.energy_drift`, `run.momentum_drift` | a two-body-only run drifts by more than the tolerance | `dynamics.conservation_tolerance` |
| A small-body impact | `run.small_body_impact` | a spacecraft is inside the small body's shape | none |
| Propellant ran out | `run.propellant_depleted` | station keeping's propellant runs out | none |
| The space weather read | `space_weather.daily_forecast`, `space_weather.monthly_forecast`, `space_weather.msfc_prediction`, `space_weather.msfc_repeated` | the run reads a forecast, a prediction or MSFC's repeated months | `space_weather.msfc_repeat_months` for the repeat ([Environment data](environment-and-data.md)) |
| The Earth orientation | `earth_orientation.none`, `earth_orientation.not_covered`, `earth_orientation.predicted` | no IERS data, files that do not cover the run, or predicted values | none |
| The magnetic field model | `magnetic_field.wmm_validity` | the run is outside the WMM's 5 years | none |
| A data file changed | `data.changed_since_install` | a file read is not the one installed (SHA-256) | none |
| The lifetime's look-ahead | `lifetime.space_weather_ends` | the real space-weather data ends before the horizon | none ([Orbital lifetime](lifetime.md)) |
| The lifetime's last step | `lifetime.ground_in_step` | the orbit reaches the ground within one decay step | none |

## Rules and parameters

Each is a named parameter, `results.<name>`.
`spacemissionstudio assumptions --area results` lists the values in
effect, and a project configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `sma_window_orbits` | 1 | [orbit] | The averaging window of the mean semi-major axis change, at each end of the run | SpaceMissionStudio's own choice |
| `umbra_sunlight_fraction` | 0.01 | [-] | The lowest sunlight below which an eclipse is umbra | SpaceMissionStudio's own choice |
| `pointing_converged_deg` | 5 | [deg] | The dashboard's converged pointing error | SpaceMissionStudio's own choice |
| `battery_critical_fraction` | 0 | [-] | The share of capacity at or below which the overview marks the battery critical | SpaceMissionStudio's own choice |

## Assumptions

- A figure is only as fine as the run's recording interval: a pass or an
  eclipse starts and ends on recorded samples.
- The battery limit is a reading of the result, not a constraint on the
  simulation: Basilisk's battery still runs down to 0.

## Checked against

- `tests/test_run_summary.py`: the figures against hand-built runs,
  including the semi-major axis averaging and a central body other than
  the Earth.
- `tests/test_events.py`: each kind of event against hand-built series.
- `tests/gui/test_results_overview.py` and
  `tests/gui/test_mission_dashboard_widget.py`: the marks and badges.
- `tests/test_run_findings.py`: every warning of a run names its rule,
  and a saved run keeps it.
