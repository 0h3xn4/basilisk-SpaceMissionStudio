# Environment data: the atmosphere, space weather, Earth orientation, TLEs

The rules SpaceMissionStudio applies to the environment's data, and the
checks it makes on it. Code:
- `spacemissionstudio/engine/spaceweather.py`;
- `engine/earth_orientation.py`, `engine/tle.py`;
- `engine/scenario_checks.py`, `engine/mean_elements.py`.

Where each file comes from, and how to update it:
[Reference data](../user-manual/reference-data.md) and
[Data and standards](../reference/data-and-standards.md).

## The atmosphere

A run with drag reads the density of one of three models, the scenario's
`space_weather.atmosphere_model` (Scenario › Environment, **Atmosphere
model**). Each is Basilisk's; the altitude it is given is the WGS-84
geodetic one (`engine/geodetic_atmosphere.py`).

| Model | Name | Density from | Use it for |
|---|---|---|---|
| NRLMSISE-00 | `nrlmsise00` (default) | the day's real space weather (below), position and time | any orbit: lifetimes, station keeping |
| Exponential | `exponential` | 1.217 kg/m^3 at sea level, 8.5 km scale height | a quick check only: far too thin above about 150 km |
| Tabular | `tabular` | a published profile, by altitude only | entry and low-altitude analyses within the table, a fixed reference profile |

The tabular model interpolates linearly in altitude one of the profiles
Basilisk ships (`supportData/AtmosphereData`, read by Basilisk's
`readAtmTable` and interpolated by its `TabularAtmosphere`); the scenario
names it in `space_weather.atmosphere_table`
(`engine/atmosphere_tables.py`):

| Table | Name | Altitudes | Made for |
|---|---|---|---|
| U.S. Standard Atmosphere, 1976 | `us_standard_1976` | -5 to 86 km | the standard's mid-latitude year-round mean; not defined above 86 km |
| Earth-GRAM 2016, nominal profile | `earthgram_2016_nominal` | 0 to 200 km | 40 deg N, 105.27 deg W, 2021-09-21 21 h; F10.7 230, Ap 16.3 |
| NRLMSISE-00, nominal profile | `nrlmsise00_nominal` | 0 to 499.5 km | 40 deg N, 40 deg E, 2021-04-01 21 h UT; the indices were ModelWeb's defaults, not recorded |

- **Sources:** the U.S. Standard Atmosphere, 1976 (NOAA, NASA, USAF;
  NOAA-S/T 76-1562); NASA's Earth-GRAM 2016; NRLMSISE-00 from NASA CCMC's
  ModelWeb; each table every 500 m, as Basilisk's
  `supportData/AtmosphereData/support/README.txt` and its Earth-GRAM
  namelist record.
- **Assumptions:** one column, the same everywhere and at every time: no
  latitude, local time or solar activity. Above the table's top, and
  below its bottom, the density is 0.
- **What it says:** a spacecraft with drag whose perigee is above the
  top gets the run warning `run.above_atmosphere_table`; a lifetime with
  the tabular model warns `lifetime.tabular_atmosphere` (an orbit above
  the top never decays). The run's provenance records the table's file
  and SHA-256 (`data_files.atmosphere_table`), and a lifetime's record
  names the table.
- **Checked against:** `tests/test_atmosphere_tables.py`: each table read
  by Basilisk's reader between the altitudes recorded here, the US
  Standard Atmosphere's sea level its defining 1.225 kg/m^3 and 288.15 K;
  a run at 300 km reading the NRLMSISE-00 profile's density at its
  altitude; zero drag and the warning above the US Standard's 86 km; a
  lifetime reading the same table.
- **Data:** the three files are support data, fetched once at
  installation with the rest (`engine.kernels`); a run never downloads.

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

  A run's mean elements are only for an Earth orbit with gravity of
  degree 2 or more. Their trace (`mean_elements.series_trace`) names:
  - Basilisk's `clMeanOscMap`;
  - the radius and J2 the run used (`EARTH_EQUATORIAL_RADIUS_M`,
    `EARTH_J2`: Basilisk's `radEquator` and `J2_EARTH`);
  - the two bands;
  - how many samples fell in each, and how many had no closed orbit.

  The mean semi-major axis change of Results › Overview opens it
  (**Open**), and `run --explain` prints it.
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
