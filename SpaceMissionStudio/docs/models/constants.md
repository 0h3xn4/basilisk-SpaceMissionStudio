# Physical constants

The one set of physical constants SpaceMissionStudio's own calculations
use: Basilisk's, from `architecture/utilities/astroConstants.h`, which
every simulated orbit already uses. Code: `spacemissionstudio/constants.py`.
`tests/test_constants.py` checks each value against Basilisk's own and
checks that every analysis takes them from there.

These include:
- the lifetime estimate and the propellant budget;
- the orbit design (Sun-synchronous inclination, repeat ground tracks);
- the constellation and formation generators and the template wizard;
- the scenario checks, including the pass predictions, the orbit
  warnings and the gravity-truncation estimate;
- the environment estimates, including the sensors' solar flux;
- optical navigation.

So an estimate and a run of the same orbit agree on the Earth they are
about.

## The set

| Constant | Value | Unit | Basilisk's name |
|---|---|---|---|
| Earth's GM | 398 600.436e9 | [m^3/s^2] | `MU_EARTH` |
| Earth's equatorial radius | 6 378 136.6 | [m] | `REQ_EARTH` (from SPICE) |
| Earth's J2 | 1082.616e-6 | [-] | `J2_EARTH` |
| Earth's rotation rate | 2 pi / 23.9345 h | [rad/s] | `OMEGA_EARTH` |
| Astronomical unit | 149 597 870 693 | [m] | `AU2M` |
| Solar flux at 1 AU | 1361 | [W/m^2] | `SOLAR_FLUX_EARTH` (ECSS-E-ST-10-04C Table 6-2 gives the same) |
| Equatorial radii of the Sun, Mercury, Venus, the Moon, Mars, Jupiter | 695 000; 2439.7; 6051.8; 1737.4; 3396.19; 71 492 | [km] | `REQ_*` |
| Mars's J2 | 1960.45e-6 | [-] | `J2_MARS` |

They are constants, not parameters: a project does not change the
Earth. A study with another set changes them in this one file, and the
test then shows where it departs from the simulation's.

## What was unified (2026-10-30)

Before Phase 3c the code held five sets. `docs/changes.md` gives the
before and after values.

| Where | Before | Now |
|---|---|---|
| The lifetime, the budget, the orbit design, the generators, the wizard, optical navigation | Basilisk's, each a copy of its own | The one set |
| Scenario checks: pass predictions and orbit warnings | GM 3.986004415e14 (GGM03S's, labelled as Basilisk's), J2 1.0826e-3; WGS-84's 6 378 137 m for "inside Earth" and the perigee | The one set |
| Scenario checks: "re-enters within about an orbit" | 120 km of their own | `lifetime.reentry_altitude_km` |
| Gravity-truncation estimate (Explain's gravity fidelity) | GGM03S's GM, radius 6 378 136.3 m and J2 1.08263e-3 | The one set |
| Sensor solar flux and its distance scaling | IAU 2012's AU, 149 597 870 700 m | Basilisk's, 149 597 870 693 m |

## Not in the set, and why

- **The gravity field files' own reference values** (GGM03S, GGM2B): the
  field's coefficients are defined with them. `engine.gravity_field`
  rescales the coefficients to Basilisk's radius.
- **WGS-84's ellipsoid** (6 378 137 m, 1/298.257223563): it defines
  geodetic latitude and height, for stations and the atmosphere's lookup.
  It describes a shape, not a gravity constant.
- **The mean elements' J2:** Basilisk's `J2_EARTH`, the standard input of
  the first-order map. The propagated field's own C20 differs slightly,
  and the map is not a model of that field.
- **Constants inside Basilisk's modules**, which SpaceMissionStudio does
  not change: for instance the faceted SRP's 1368 W/m^2 (the cannonball
  SRP and the solar panels use 1361), and sensorThermal's 1366 W/m^2,
  which `engine.environment_models` corrects for.
- **The re-entry altitudes:** two criteria, both parameters. A run stops
  when the simulated altitude is below `dynamics.reentry_altitude_km`
  (100 km). A lifetime ends when the orbit-averaged perigee reaches
  `lifetime.reentry_altitude_km` (120 km), from where the orbit lasts
  days at most.
