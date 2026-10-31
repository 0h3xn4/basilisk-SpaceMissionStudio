# ROE formation guidance

How the ROE formation controller decides when and how to fire: it holds
a follower at, or moves it between, targets in relative orbital elements
(ROE). This page covers the tool's own guidance, the `"impulsive"` law.
The `"continuous"` law is Basilisk's `meanOEFeedback`, run unmodified.

Code: `spacemissionstudio/engine/roe_formation.py` (the controller) and
`engine/roe.py` (the ROE math). The scenario sets the targets, the
tolerances, the correction window, the largest drift and the drag
estimate's window (`roe_formation`). The parameters below are the rules
inside the guidance. How to set up a formation:
[Fly a formation with relative orbital elements](../user-manual/roe-formation.md).

## Measurement

Each step, both spacecraft's osculating states become mean elements with
Basilisk's `orbitalMotion.clMeanOscMap` (first-order J2), and the mean
ROE are taken from those. These are truth states: there is no relative
navigation filter.

## Decisions

The controller decides at a decision point. While the formation is inside
its tolerances, a decision point comes every `holding_check_fraction` of an
orbit (a quarter). After a correction's last burn, the next one comes an
orbit later, or the same fraction later during a drift. At each decision
point the mean ROE are compared with the active target:

- **A small along-track error** is corrected directly. That means up to
  `direct_dl_factor` along-track tolerances (5), or a relative semi-major
  axis or e vector out of tolerance. Along-track burns over the next two
  orbits set the relative semi-major axis, the e vector and the mean
  longitude together.
- **A larger along-track error drifts:** burns set a drift relative
  semi-major axis, capped by the scenario's `max_drift_m`. The burns set
  it one by one, so the mean longitude ends up elsewhere than planned:
  when that shift is more than `replan_shift_fraction` of the along-track
  tolerance (0.25), the plan is made again from where they lead.
- **How a drift ends:**
  - **Gliding in:** as the target nears, the drift is cut back so the
    rest closes in no less than `glide_orbits` (3).
  - **The slow drift:** it is never cut below the slow drift. That is the
    larger of `slow_drift_fraction` of the semi-major axis tolerance
    (0.25) and the drift whose stop steps fit the along-track tolerance.
  - **Bands:** it is cut back only when more than `cutback_band_factor`
    times the glide-in drift (1.25), and stopped only when within
    `stop_band_factor` times the slow drift (1.5). Between them it is
    held, so it is not planned again at each check.
  - **The stop:** it is stopped once stopping there would bring the mean
    longitude past the target, or within `stop_reached_fraction` of the
    along-track tolerance of it (0.5).
  - **Looking again:** while it is held, the controller looks again
    before the stop is due, but no sooner than `min_check_s` (60 s).
- **An inclination vector out of tolerance** gets one cross-track burn.

Each burn is fired as an arc centred on its planned place on the orbit.
The controller records where the last orbit was in eclipse and plans
burns only in sunlight. A burn that still meets eclipse waits an orbit.
After `eclipse_retries` tries (3), the plan is dropped and made again.

## Differential drag

With `differential_drag` set, the controller fits the decay of the mean
relative semi-major axis over the scenario's `drag_estimate_window_days`:
- **Fresh stretches:** a new one starts after each burn, and after any
  change between two samples above `drag_jump_m` (0.1 m, times the
  chief's semi-major axis), such as the chief's reboost.
- **When the fit is used:** once `drag_min_orbits` of data are in (4).
  Shorter fits are biased by the oscillation the mean-element map leaves.

A decay is compensated only when it would move the mean longitude by more
than `drag_significance_fraction` of its tolerance (0.5) over the
correction window. If it would, each
correction sets a drag cycle: the relative semi-major axis and the mean
longitude swing about their targets, both inside `drag_hold_fraction` of
their tolerances (0.6). A hold check propagates both
`drag_lookahead_orbits` ahead (2), decay included. It corrects when
either would be past `drag_trigger_fraction` of its tolerance (0.7).

## Rules and parameters

Each is a named parameter, `roe_formation.<name>`. `spacemissionstudio
assumptions --area roe_formation` lists the values in effect, and a
project configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)). The
controller reads them once, when the run builds it.

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `roe_formation.holding_check_fraction` | 0.25 | [orbit] | How long after a decision that planned nothing (or after a burn during a drift) the formation is looked at again | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.glide_orbits` | 3 | [orbit] | The least time the end of a drift takes: the drift is cut back to it as the target nears | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.direct_dl_factor` | 5 | [-] | The largest along-track error, in along-track tolerances, corrected without a drift | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.eclipse_retries` | 3 | [-] | How many times a burn may meet eclipse before its plan is dropped | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.drag_min_orbits` | 4 | [orbit] | The data the decay fit needs before it is used | SpaceMissionStudio's own choice (no derivation recorded for four) |
| `roe_formation.drag_jump_m` | 0.1 | [m] | The change between two samples that starts a new stretch of the decay fit | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.drag_hold_fraction` | 0.6 | [-] | The share of the tolerances a drag cycle may use | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.drag_lookahead_orbits` | 2 | [orbit] | How far ahead a drag cycle's hold check looks | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.drag_trigger_fraction` | 0.7 | [-] | The share of a tolerance, that far ahead, that starts a correction | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.drag_significance_fraction` | 0.5 | [-] | The share of the along-track tolerance a decay must move the mean longitude by, over the correction window, to be compensated | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.slow_drift_fraction` | 0.25 | [-] | The slow drift a drift ends at, as a share of the semi-major axis tolerance (when that is the larger) | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.stop_band_factor` | 1.5 | [-] | How close to the slow drift a drift must be before it is stopped | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.cutback_band_factor` | 1.25 | [-] | How far above the glide-in drift a drift must be before it is cut back | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.stop_reached_fraction` | 0.5 | [-] | How close to the target, in along-track tolerances, a stop must bring the mean longitude | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.min_check_s` | 60 | [s] | The earliest the controller looks again while a drift is held | SpaceMissionStudio's own choice (no derivation recorded) |
| `roe_formation.replan_shift_fraction` | 0.25 | [-] | The shift of the mean longitude, in along-track tolerances, that makes a drift plan be made again | SpaceMissionStudio's own choice (no derivation recorded) |

**Not parameters:**
- **The burn scheduling margins:** a burn at least half a burn part plus
  1 s ahead, and burns at least 1.5 burn parts apart. They keep burns
  from overlapping.
- **The eclipse record:** 72 bins of argument of latitude (5 deg each).
- **Placing the follower:** `follower_orbit`'s six iterations of the
  mean-to-osculating correction, below a millimetre in two.
- **The physical constants:** the Earth's J2 and radius, from the
  gravity model ([Physical constants](constants.md)).

## Assumptions

- **Truth states:** both spacecraft's states are known exactly; there is
  no relative navigation.
- **First-order J2 mean elements:** the guidance plans with the J2
  state transition matrix for near-circular orbits. The chief must be
  near-circular (eccentricity up to 0.01) and not equatorial.
- **Ideal thrust:** an inertial force at full thrust, with no slew to
  point the thruster; no thrust in eclipse.
- **A steady drag decay:** the decay is planned as constant. Its changes
  within a day are corrected as errors, and so is all of it during a
  drift.

## Checked against

- `tests/test_roe.py`: the ROE math, the drift and its stop, eclipse
  avoidance, burn splitting, the decay estimator and the drag cycle.
- `tests/test_roe_formation_run.py`: formations flown in Basilisk, held
  inside their tolerances and reconfigured to a safe helix.
- `tests/test_config.py`: each parameter changes the decision it
  controls, and the run gives the controller its scenario.
