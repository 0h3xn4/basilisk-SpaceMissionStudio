# Pre-run checks

The warnings a scenario gets before it runs. They flag setups that can't
do what they are configured for, so a run is not wasted:
- **Scenario › Overview (Explain)** shows the scenario checks below;
- **the editor's Problems panel** shows, while typing, the plausibility
  checks: an initial orbit that cannot be flown (inside the Earth, an
  escape, a perigee below the ground or the re-entry altitude), a run
  outside the installed reference data, a 3D model out of date;
- **`spacemissionstudio validate`** prints both.

Code: `spacemissionstudio/engine/scenario_checks.py`. The checks are
fast and never raise: a half-edited scenario gets no warning rather than
an error, and a check that fails says "check not run" with the reason.

## The pass prediction

Ground-station passes are predicted from each spacecraft's initial
orbit:
- **The orbit:** Kepler's orbit, plus J2's secular drift when the gravity
  model includes J2. Maneuvers, drag and higher-order gravity are
  ignored.
- **The stations:** on the WGS-84 ellipsoid, with the elevation measured
  from the ellipsoid normal (ECSS-E-ST-10-09C 5.4.6a).
- **The Earth's rotation:** the IAU_EARTH model SPICE uses (pck00010).
- **Sampling:** the elevation is sampled every `pass_step_s` (30 s), so a
  pass's start and end are known to that step and a high pass's peak can
  be up to about 1.5 deg low.
- **How far:** over the run, at most `pass_horizon_days` (7 days, "in the
  first week"). A station without a pass in the run is looked for
  `pass_lookahead_days` past it (2 days).

Earth only: a run about another body, or a TLE orbit that can't be read,
gets no prediction.

## The checks and their rules

Each warning names its rule (`engine/findings.py`): what the rule is,
what it found against its limit, why it matters, how to fix it and how
to override it. `spacemissionstudio validate --explain` prints them. A
warning never stops a run; the run itself refuses only what it cannot
do, and says so.

| Warning | Rule | It is given when | Parameters |
|---|---|---|---|
| A late first pass | `passes.late_first` | the first pass comes after `late_first_pass_fraction` of the run (0.5) | `late_first_pass_fraction` |
| No pass in the run | `passes.none_in_run` | none is predicted in the run; it says when the first comes | `pass_horizon_days` |
| No pass in the look-ahead either | `passes.none_in_lookahead` | none comes in the run or the look-ahead after it | `pass_lookahead_days` |
| Every step is recorded | `recording.every_step` | `Record every` is 0 and a series would hold more than `many_samples` samples (1,000,000) | `many_samples` |
| Recording too coarse for the passes | `recording.coarse` | the shortest pass predicted over the first day lasts no more than `coarse_recording_factor` recording intervals (3) | `coarse_recording_factor` |
| A long dynamics step | `step.long` | the step is longer than `long_step_s` (60 s) | `long_step_s` |
| No sun sensor faces the Sun-pointing axis | `sensors.sun_sensor_facing` | no coarse sun sensor's normal is within the angle whose cosine is `css_facing_min_cosine` (0.5, 60 deg) of the axis the spacecraft keeps on the Sun | `css_facing_min_cosine` |
| A TLE far from the epoch | `tle.age` | the TLE's epoch is more than `tle.age_warning_days` from the scenario's | ([Environment data](environment-and-data.md)) |
| Perigee below the re-entry altitude (a plausibility check) | `orbit.perigee_reentry` | the initial perigee is below `lifetime.reentry_altitude_km` | ([Orbital lifetime](lifetime.md)) |

Other checks have no threshold, each with its rule:
- **Plausibility:** `orbit.inside_body`, `orbit.escape`,
  `orbit.perigee_below_surface`; the reference data
  (`space_weather.unreadable`, `space_weather.starts_late`,
  `space_weather.ends_early`, `earth_orientation.none`,
  `earth_orientation.not_covered`, `earth_orientation.predicted`); the
  3D model (`model.problem`, `model.stale`).
- **The scenario:**
  - an unreadable TLE (`tle.unreadable`);
  - drag with point-mass gravity (`gravity.drag_point_mass`);
  - facets with drag and SRP off (`facets.unused`);
  - station keeping with drag off (`station_keeping.no_drag`);
  - navigation errors restarting at each segment of a long run
    (`navigation.restart`);
  - a hill_pd follower whose thruster can't hold its law
    (`formation.hill_pd_hold`, `formation.hill_pd_start`);
  - missing small-body data (`small_body.ephemeris_missing`,
    `small_body.shape_missing`);
  - more Monte Carlo processes than CPUs (`monte_carlo.processes`).
- **A check that fails:** it says "check not run" with the reason
  (`check.not_run`).

With a Mission Sequence the pass check is skipped: the run's length
comes from its commands.

## Rules and parameters

Each is a named parameter, `checks.<name>`. `spacemissionstudio
assumptions --area checks` lists the values in effect, and a project
configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `checks.pass_step_s` | 30 | [s] | The pass prediction's sample spacing | SpaceMissionStudio's own choice: a LEO pass above 10 deg lasts several minutes; no derivation recorded for 30 s |
| `checks.pass_horizon_days` | 7 | [day] | How far passes are counted | SpaceMissionStudio's own choice, to keep the check fast |
| `checks.pass_lookahead_days` | 2 | [day] | How far past the run the first pass is looked for | SpaceMissionStudio's own choice (no derivation recorded) |
| `checks.many_samples` | 1,000,000 | [-] | The samples per series above which recording every step is flagged | SpaceMissionStudio's own choice (about 1.7 MB per simulated day for one LEO spacecraft; no derivation recorded for the limit) |
| `checks.coarse_recording_factor` | 3 | [-] | How many recording intervals a pass must outlast | SpaceMissionStudio's own choice (no derivation recorded) |
| `checks.long_step_s` | 60 | [s] | The dynamics step above which the run is flagged | SpaceMissionStudio's measurement (audit E3): a one-day two-body run at 7000 km was under 2 cm off at 60 s, 0.9 m at 120 s, 11 m at 300 s, 8.6 km at 1800 s |
| `checks.late_first_pass_fraction` | 0.5 | [-] | How late in the run a first pass is flagged | SpaceMissionStudio's own choice (no derivation recorded) |
| `checks.css_facing_min_cosine` | 0.5 | [-] | How close to the Sun-pointing axis a sun sensor must face | SpaceMissionStudio's own choice (no derivation recorded) |

**Not parameters:**
- **The navigation build-up (0.41 flight-software steps per
  (bound/step)^2):** measured with Basilisk's `simpleNav` (40 seeds by 3
  axes, at four bound/step ratios: 0.30 to 0.41, the largest used). It
  states how long the errors take to grow back, a measured fact rather
  than a threshold.
- **Kepler's equation:** solved with 12 Newton iterations, far below the
  sampling's precision.
- **The coarse-recording check's one-day window:** it predicts the first
  day's passes only, to stay fast.

## Assumptions

- **The orbit as configured:** maneuvers, drag and higher-order gravity
  are ignored, so a prediction is typically within a minute over a few
  hours in LEO, and less exact later.
- **A sun sensor faces the axis or does not:** the check uses the sensor's
  normal only, not its field of view.

## Checked against

- `tests/test_scenario_checks.py`: template 19's passes against an
  independent Basilisk run with the WGS-84 site (10.4 to 18.2 min, peak
  61.6 deg), the Cartesian and element forms agreeing, each warning, a
  half-edited scenario, a failing check.
- `tests/test_config.py`: each parameter changes what the checks predict
  or flag, and set to its default leaves it as it was.
