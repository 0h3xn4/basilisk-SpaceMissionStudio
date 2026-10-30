# Environment data: space weather, Earth orientation, TLEs

The rules SpaceMissionStudio applies to the environment's data, and the
checks it makes on it. Code:
- `spacemissionstudio/engine/spaceweather.py`;
- `engine/earth_orientation.py`, `engine/tle.py`;
- `engine/scenario_checks.py`, `engine/mean_elements.py`.

Where each file comes from, and how to update it:
[Reference data](../user-manual/reference-data.md) and
[Data and standards](../reference/data-and-standards.md).

## Space weather

NRLMSISE-00 needs F10.7 and Ap for each day of a run with drag, and for
10 days on either side. Each day is taken from the first source that has
it:

1. CelesTrak's observations, and its 45-day forecast after them.
2. MSFC's prediction, at the forecast percentile the scenario chooses
   (95, 50 or 5; ESA AD10 Sec. 5.9). The 13-month smoothed F10.7 serves
   as the day's value and as its 81-day average, and its Ap fills all
   eight 3-hour slots.
3. Past the end of MSFC's prediction, its last `msfc_repeat_months` (132)
   months repeat, one solar cycle, as AD10 Sec. 5.9 asks. A run that
   reaches there warns: "past 2041-10 MSFC's last 132 months repeat".
4. NOAA's monthly F10.7 forecast, for any month MSFC does not cover, with
   Ap held at the observed mean.

A run outside all of them is refused, with the dates the data covers.
Nothing is made up: there is no synthetic space weather.

A prediction table must hold at least 132 months (one cycle), and at
least as many as are repeated.

## TLEs

A TLE is propagated by SGP4 from its epoch to the scenario's, then turned
from TEME to EME2000. SGP4's accuracy falls with the span it propagates
over, so the scenario checks warn when the TLE's epoch is more than
`age_warning_days` (3 days, `tle.age_warning_days`) from the scenario's.

## Fixed rules, and why

These are properties of the data or of the mathematics, not choices a
project makes:

- **Earth orientation is high-accuracy until 10 weeks after its last
  datum:** NAIF's comment file for the predicted Earth orientation says
  so. Past it, the run says it is using predicted values of lower
  accuracy.
- **Mean elements near the critical inclination:** the first-order map
  between mean and osculating elements is singular at 63.435°. Within 1°
  of it, the map is blended from its values at the band's edges. Below 1°
  (or above 179°), it is evaluated at 1°. Placing a satellite by its mean
  elements inverts the map in six correction steps; two already bring the
  semi-major axis within a millimetre.
- **The magnetic field model (WMM) is valid for 5 years** from its epoch,
  by its release rule; past that a run warns.
- **The reference-data panel flags space weather older than 60 days** as
  out of date. This covers the whole app, not a scenario.

## Rules and parameters

Each is a named parameter. `spacemissionstudio assumptions --area
space_weather` and `--area tle` list the values in effect, and a project
configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `space_weather.msfc_repeat_months` | 132 | [month] | How many of MSFC's last months repeat past its prediction's end | ESA AD10 Sec. 5.9 |
| `tle.age_warning_days` | 3 | [day] | The TLE age at which the scenario checks warn | SpaceMissionStudio's own choice |

## Checked against

- `tests/test_spaceweather.py`: the MSFC table as published, its repeat,
  the order of the sources, and a run outside the data refused.
- `tests/test_tle.py`: the TLE checks and the age warning.
- `tests/test_mean_elements.py`: the map at and near the critical
  inclination.
