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
