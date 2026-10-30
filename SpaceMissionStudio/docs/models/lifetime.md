# Orbital lifetime

When a spacecraft re-enters under drag, whether that meets the disposal
rules, and the delta-V a station keeper spends holding its orbit against
drag. Code: `spacemissionstudio/engine/lifetime.py`. How to use it:
[Lifetime and propellant budget](../user-manual/lifetime-and-budget.md).

## What it computes

Simulating decades of decay step by step would take hours, so the
estimate follows the orbit's **mean elements**, one orbit-averaged drag
step at a time:

1. **Drag, averaged over the orbit:** the drag acceleration is computed at
   `ring_points` (16) points spread evenly around the orbit in mean
   anomaly, so their mean is a time average. The positions include J2's
   short-period terms (Basilisk's `clMeanOscMap`); without them the ring
   sits several km below the real path. Drag acts on the velocity
   relative to an atmosphere turning with the Earth.

       a_drag = -1/2 * (Cd * A / m) * rho * |v_rel| * v_rel

2. **The orbit's change:** Gauss's equations in vector form turn the
   averaged acceleration into the rates of the semi-major axis and the
   eccentricity vector. J2 turns the node and perigee at their secular
   rates.
3. **Steps:** at most `max_step_s` (a day). Near re-entry a step loses at
   most `max_perigee_drop_fraction` (1 %) of the perigee height left. Each
   step takes its rates half-way through: a plain step from the start lags
   the rising density and decays about 2 % slow.
4. **Re-entry:** the perigee reaching `reentry_altitude_km` (120 km); below
   that an orbit lasts days at most. Without re-entry the estimate stops
   at the horizon, or where the real space-weather data ends, which it
   says.

**Density** is the scenario's own model:
- NRLMSISE-00 (Basilisk's `msisAtmosphere`), driven by the space-weather
  file a simulation would use, at MSFC's prediction past the observations
  (the percentile chosen);
- or Basilisk's exponential model. That one is far too thin above about
  150 km, and the estimate says so.

**Area and drag coefficient:** the facets' tumbling average (sum of the
facet areas / 4, exact for a convex body) when the spacecraft has facets,
else its drag area. The drag coefficient is the one chosen: by default
`default_drag_coeff` (2.2, AD10's end-of-life value), or the spacecraft's
own.

**Disposal rules:** the lifetime meets a rule when the spacecraft
re-enters within its years: `zero_debris_years` (5) and `iadc_years`
(25). A rule is "not known" when the estimate did not look that far ahead.

**After a run, or with a deorbit burn:** from the end of a run, the
estimate starts from the run's last state with the propellant left. A
deorbit burn is one retrograde burn at apogee lowering the perigee, or as
far as the propellant allows.

**Drag make-up** (for the propellant budget): the along-track drag on the
held orbit, sampled every `makeup_step_s` (6 hours) over the window, with
the mass held fixed. Against full five-year Basilisk station-keeping runs
it comes out about 5 % low.

## Rules and parameters

Each is a named parameter, `lifetime.<name>`; `spacemissionstudio
assumptions --area lifetime` lists the values in effect, and a project
configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `reentry_altitude_km` | 120 | [km] | The perigee counted as re-entry | Common practice for orbit-averaged estimates |
| `ring_points` | 16 | [-] | The points the drag is averaged over at each step | SpaceMissionStudio's own choice: within 3 % of Basilisk decay runs |
| `max_step_s` | 86 400 | [s] | The longest step | SpaceMissionStudio's own choice: the space weather is daily |
| `max_perigee_drop_fraction` | 0.01 | [-] | The share of the remaining perigee height one step may lose | SpaceMissionStudio's own choice |
| `zero_debris_years` | 5 | [year] | The first disposal rule | ESA Zero Debris approach; FCC 5-year rule |
| `iadc_years` | 25 | [year] | The second disposal rule | IADC guidelines; ISO 24113 |
| `makeup_step_s` | 21 600 | [s] | The drag make-up's sampling step | SpaceMissionStudio's own choice |
| `default_drag_coeff` | 2.2 | [-] | The drag coefficient an estimate starts with (CLI `--drag-coeff`, End of Life page) | ESA AD10 Sec. 5.2 |
| `default_forecast_percentile` | 50 | [%] | The MSFC percentile an estimate starts with; one of 95, 50, 5 | ESA AD10 Sec. 5.9 |
| `default_horizon_years` | 30 | [year] | How far an estimate looks ahead unless told | SpaceMissionStudio's own choice: past the 25-year rule |
| `default_deorbit_perigee_km` | 250 | [km] | The End of Life page's deorbit perigee to start with | SpaceMissionStudio's own choice |

**Constants**, not yet parameters: Earth's GM, equatorial radius, J2 and
rotation rate, Basilisk's own (`engine/lifetime.py`). They join the one
set of constants the transparency plan chooses in Phase 3c, which also
reconciles the 120 km here with the 100 km at which a full simulation run
stops.

## Assumptions

- Mean elements, orbit-averaged drag and J2 secular rates only; no
  short-period effects on the decay beyond the ring's positions.
- Constant mass during the decay.
- Earth only.
- Sphere (cannonball) drag, or the tumbling average of the facets.
- No solar radiation pressure, third bodies or higher harmonics, which
  matter little for orbits that decay within decades.
- Earth rotation from GMST with UT1 = UTC.

## Checked against

Full Basilisk decay runs of template 18's spacecraft
(`tests/test_lifetime.py`): the re-entry date within 3 %. The density
matches the simulation's own atmosphere model at the same points.

## Outputs and records

`spacemissionstudio lifetime` and the **End of Life** page give:
- the re-entry date and lifetime;
- each rule's verdict;
- the mass at the start of the decay;
- the deorbit burn, if one was asked for.

`lifetime --out FILE.json` writes:
- the inputs;
- the drag used and the ballistic coefficient;
- the rules in effect under their parameter names;
- the decay curve;
- the warnings;
- the provenance, with the space-weather files read and the project
  configuration.
