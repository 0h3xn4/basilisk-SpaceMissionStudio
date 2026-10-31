# Flight software and navigation

The rules inside the run's flight software and navigation filters that a
scenario does not set:
- the attitude thrusters' Schmitt trigger;
- optical navigation's filter (Basilisk's `relativeODuKF`);
- landmark navigation's filter (the tool's own).

The scenario sets the control gains, the modes, the sensors and each
navigation chain's camera, noise, intervals and initial uncertainty
(`fsw_mode`, `control_params`, `fsw_params`, `optical_navigation`,
`landmark_navigation`). The User Manual describes those.

Code: `spacemissionstudio/engine/fsw.py`,
`engine/optical_navigation.py`, `engine/landmark_navigation.py`,
`engine/landmarks.py`.

## The attitude thrusters' Schmitt trigger

With thrusters for attitude control, `mrpFeedback`'s torque is mapped to
each thruster's force (`thrForceMapping`, all three body axes). Basilisk's
`thrFiringSchmitt` then turns each force into an on-time for the control
period:
- **A request of at least `thruster_min_fire_time_s`** (2 ms) is fired as
  asked, up to the whole period.
- **A shorter request** fires for the minimum fire time or not at all:
  - **on** when it is at least `thruster_level_on` of the minimum (0.75);
  - **off** when it is at most `thruster_level_off` of it (0.25);
  - **between the two**, the thruster keeps its last state.

The defaults are Basilisk's `examples/scenarioAttitudeFeedback2T_TH.py`
for its attitude-control thrusters. They are not derived for this app's
thrusters.

## Optical navigation's filter

`relativeODuKF` (Basilisk, unmodified) filters the positions
`pixelLineConverter` gives with two-body dynamics about the central body.
Its unscented transform's settings:
- `opnav_ukf_alpha` (0.02), the spread of the sigma points;
- `opnav_ukf_beta` (2), the weight on the prior's distribution;
- `opnav_ukf_kappa` (0), the secondary scaling;
- `opnav_ukf_noise_scale` (1), `noiseSF`, which Basilisk's header calls
  the scale factor for measurement noise.

The defaults are those of Basilisk's own `relativeODuKF` unit test and
`examples/OpNavScenarios`.

## Landmark navigation's filter

The tool's extended Kalman filter (`landmarks.LandmarkFilter`) predicts
to each image with the shape's gravity and the body's spin. It integrates
the state and its transition matrix with RK4, in steps no longer than
`landmark_filter_max_step_s` (60 s), then updates with the landmarks
seen.

## Rules and parameters

Each is a named parameter: `flight_software.<name>` or
`navigation.<name>`. `spacemissionstudio assumptions --area
flight_software` (or `--area navigation`) lists the values in effect,
and a project configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)). The run
reads them when it builds each module.

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `flight_software.thruster_min_fire_time_s` | 0.002 | [s] | The shortest on-time the Schmitt trigger commands | Basilisk's `examples/scenarioAttitudeFeedback2T_TH.py` |
| `flight_software.thruster_level_on` | 0.75 | [-] | The share of the minimum fire time a short request needs to fire | Same example |
| `flight_software.thruster_level_off` | 0.25 | [-] | The share at or below which a short request turns the thruster off | Same example |
| `navigation.opnav_ukf_alpha` | 0.02 | [-] | The spread of `relativeODuKF`'s sigma points | Basilisk's `relativeODuKF` unit test and `examples/OpNavScenarios` |
| `navigation.opnav_ukf_beta` | 2 | [-] | The weight on the prior's distribution | Same |
| `navigation.opnav_ukf_kappa` | 0 | [-] | The secondary scaling | Same |
| `navigation.opnav_ukf_noise_scale` | 1 | [-] | `relativeODuKF`'s `noiseSF` | Basilisk's `relativeODuKF` unit test |
| `navigation.landmark_filter_max_step_s` | 60 | [s] | The longest RK4 step of the landmark filter's prediction | SpaceMissionStudio's own choice (no derivation recorded) |

**Not parameters:**
- **The momentum-dump mapping's `angErrThresh` (3.15):** above pi it
  switches off the mapping's output scaling, which momentum dumping needs
  (Basilisk's `examples/scenarioMomentumDumping.py`). It is a switch, not
  a tuning value.
- **The thruster mapping's control axes:** all three body axes; the app
  builds one thruster cluster per spacecraft.
- **The landmark camera's focal length (25 mm):** the pixel pitch is
  derived from it and the field of view, so the pinhole model's ratio
  f / w, and every pixel, are the same for any focal length (checked:
  `tests/test_landmarks.py::test_the_focal_length_sets_no_result`).
- **Rounding to whole pixels:** the landmark filter takes its noise as
  1/sqrt(12) px, the standard deviation of rounding. It is exact, not a
  choice.
- **The smallest variance optical navigation writes** (1e-3 px): a
  numerical floor, since the filter takes a Cholesky factor of it.
- **Task priorities:** both navigation chains run after the dynamics.

## Assumptions

From the [transparency audit](../transparency_audit.md), Section 2:
- **The attitude loop is closed on `simpleNav`:** truth, or truth plus
  the scenario's navigation error. The star tracker, IMU, magnetometer and
  CSS models are telemetry, except the CSS estimate when
  `fsw_params.use_css_estimation` is set.
- **The flight software's inertia is the truth's:** there is no model
  uncertainty.
- **Optical navigation's attitude knowledge is perfect**, and its filter
  uses two-body dynamics.
- **Landmark navigation knows the attitude and the body's orientation
  exactly**, and its landmark map is the camera's.

## Checked against

- `tests/test_config.py`:
  - each parameter changes what it controls: the on-times
    `thrFiringSchmitt` commands for a set of requests, the filter the run
    builds for template 30, the landmark filter's steps;
  - set to its default, each leaves that as it was.
- `tests/test_landmarks.py`: the landmark filter finds the orbit from
  landmark pixels; the focal length sets no result.
- `tests/test_optical_navigation_run.py`, `tests/test_landmark_navigation_run.py`:
  the chains in Basilisk runs.
