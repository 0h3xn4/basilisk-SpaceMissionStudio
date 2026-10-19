# Known limitations

What SpaceMissionStudio does not do, or does only in part, and why.
Each item was checked against Basilisk's own source.

* **Four integrators.** The app offers Basilisk's `svIntegratorEuler`,
  `svIntegratorRK2`, `svIntegratorRKF45` and `svIntegratorRKF78`
  (`schema.scenario.SimSettings`, `engine.service._INTEGRATORS`);
  `"rkf78"` is the default. Basilisk 2.12.0 has more (RK4 and other
  Runge-Kutta variants), which the app does not offer yet.
* **Spherical-harmonics gravity is Earth-only in `service.py`**
  (GGM03S). Other central bodies
  are limited to point-mass gravity (`central_body_degree=0`) until a
  later phase adds their gravity-field files.
* **Magnetometer sensors are Earth-only** (`magneticFieldWMM`, same
  reasoning as spherical-harmonics gravity) -- `engine.fsw` raises a clear
  error for a magnetometer on any other central body rather than silently
  producing a sensor with no field to read.
* **Both actuator kinds beyond `"reaction_wheel"` are wired up, each for
  a specific role**: `"thruster"` either as primary attitude control
  (real `thrusterDynamicEffector` + `thrForceMapping` + `thrFiringSchmitt`
  -- a spacecraft uses `"reaction_wheel"` OR `"thruster"` for control, not
  both) or, together with `"reaction_wheel"`, as `MomentumDumpingConfig`'s
  desaturation hardware; `"magnetic_torque_rod"` ONLY as
  `MagneticMomentumManagementConfig`'s desaturation hardware (continuous
  RW momentum biasing via the real geomagnetic field, not a discrete
  burst) -- there is no standalone magnetic-torque-rod attitude-control/
  detumble mode, so a `"magnetic_torque_rod"` actuator without
  `magnetic_momentum_management` set is rejected early with a specific
  error.
* **The attitude control loop closes on the true state by default.**
  `simpleNav` is in the loop (not raw `scStateOutMsg`); its error is
  zero unless you turn on **Navigation error** (User Manual section 6,
  "Navigation error"), which adds a bounded random-walk error to the
  attitude, rate, Sun heading, position and velocity. `fsw_mode: sunSafePoint`'s
  `fsw_params['use_css_estimation']` is the one exception: it drives the
  controller from a real `cssWlsEst` weighted-least-squares estimate
  computed from a dedicated `coarse_sun_sensor` cluster, not truth (see
  `14_css_sun_heading_estimation.json`). A full attitude DETERMINATION
  filter (star tracker + rate gyro + reaction-wheel speeds through
  Basilisk's `inertialUKF`) is deliberately not built -- no clean shipped
  Basilisk example was found to verify one against safely.
* **`engine.fsw.DEFAULT_MRP_GAINS` (`K=3.5`, `P=30.0`), lifted directly
  from Basilisk's own `examples/BskSim` reference, is tuned for a
  900 kg*m^2 spacecraft** running its FSW task at a 0.1s rate -- applied
  unscaled to a much smaller spacecraft (this schema's own default
  inertia is 10 kg*m^2), the resulting discrete-time control update
  reliably diverges to NaN within seconds. **No longer a trap for a new
  spacecraft**: `engine.fsw.build_mrp_feedback` now auto-scales K/P by
  that spacecraft's own `inertia_kg_m2` relative to the 900 kg*m^2
  reference (`_default_mrp_gains_for_inertia`) whenever
  `SpacecraftConfig.control_params` doesn't explicitly set `K`/`P` --
  confirmed against a real Basilisk build to converge cleanly even at the
  schema's own coarse `dynamics_task_rate_s` default, where the unscaled
  reference gains diverge (`tests/test_default_mrp_gain_scaling.py`).
  This was previously applied only by hand, to specific templates
  (`07_attitude_pointing_with_adcs_hardware.json`,
  `14_css_sun_heading_estimation.json`'s explicit scaled
  `control_params`; `06_attitude_pointing_basic.json`'s finer task rate)
  before it was generalized into `engine.fsw` itself for every
  spacecraft -- those templates' own explicit choices are now redundant
  but harmless. Passing explicit `control_params={"K": ..., "P": ...}`
  still overrides this unscaled, same as always -- that choice stays on
  you.
* **Monte Carlo dispersions** cover dry mass, starting attitude, orbital
  elements, inertia, body rate and the drag and SRP coefficients (User
  Manual section 10). Raw Cartesian position/velocity dispersion is
  deliberately NOT offered: Basilisk's Cartesian dispersion classes
  replace each component with an absolute random value, not a
  perturbation around the nominal orbit; the orbit varies as orbital
  elements instead. The Monte Carlo view tracks position and velocity
  only (attitude, wheel speeds and other series are not kept per run).
* **`monte_carlo.thread_count > 1`** has been run in this project's Linux
  environment (template 25 and three-run batches with 3 threads, Basilisk
  2.12.0); the schema default stays `1`.
* **Monte Carlo retains a fixed set of data per run** (each spacecraft's
  position/velocity) -- there is no per-run custom retention-policy
  selection in the schema yet.
* **No Jacchia-Roberts atmosphere model, no Earth-albedo/IR radiation
  pressure, no `TabularAtmosphere` (user-supplied density table).** All
  three were real user questions/requests, checked directly against
  Basilisk's own source (not assumed) before answering:
  * Jacchia-Roberts genuinely doesn't exist anywhere in Basilisk (checked
    `src/simulation/environment/` -- only `ExponentialAtmosphere`,
    `MsisAtmosphere`, `TabularAtmosphere` do); `atmosphere_model` offers
    the first two (see [Orbital dynamics & propagation](capabilities.md#orbital-dynamics--propagation)), not the
    one that doesn't exist.
  * Basilisk's `earthRadiationModel` module computes Earth albedo/IR
    flux, but its own payload comment names `facetERPDynamicEffector` as
    the consumer that turns that flux into an actual orbital force --
    and that module doesn't exist in this Basilisk build either (checked
    the source tree and the installed package). Wiring this up for real
    would mean writing a brand-new, never-before-exercised force
    -effector from scratch (the same `extForceTorque` manual-force
    -injection pattern this project's own thrust controllers use, plus
    the standard flux/c * area * Cr formula solar SRP already uses) --
    deliberately not done this round; real user decision, not a gap that
    slipped through unnoticed.
  * `TabularAtmosphere` (a user-supplied altitude/density CSV) would need
    a new file-upload schema/GUI concept of its own -- out of scope for
    the atmosphere-model-choice work that added `ExponentialAtmosphere`
    as the second option.

* **3D models (`spacemissionstudio.model3d`).**
  * Basilisk's facet effectors treat every facet as exposed whenever it
    faces the flow or the Sun: one part shading another is not modelled.
    Faces where parts touch can be left out per part.
  * Cylinders, cones and spheres give flat facets with the true curved
    area shared out (16 by default); their mass properties are exact.
  * An imported mesh gives one facet per flat plane; a curved mesh gives
    many, and over 200 facets the model's facets are not applied.
  * A *solid* mass distribution needs a closed mesh; an open one can only
    be a *shell*.
  * The center of mass is fixed: propellant draining does not move it.
  * The model's orientation in Vizard follows Vizard's source (its
    importer mirrors x); it has not been looked at in a running Vizard.
  * Facets apply only in full-attitude runs; an orbit-only run keeps
    `drag_area_m2` and `srp_area_m2`.

* **ROE formations (`engine.roe`, `engine.roe_formation`).**
  * The chief must be near-circular (eccentricity up to 0.01) and
    inclined: the guidance is the near-circular one (D'Amico) and the
    inclination vector needs a node.
  * Earth only, with J2 in the gravity model: the mean elements and the
    J2 state transition matrix are Earth's J2 theory. Higher harmonics,
    the Sun and the Moon act in the run but not in the guidance.
  * Differential drag: the impulsive law compensates the steady decay of
    the relative semi-major axis it measures; how it changes within a
    day (day and night, solar activity), and all of it during a drift,
    are corrected as errors, after the fact. The estimate needs four
    orbits of data first. The continuous law has no compensation: its
    feedback corrects the decay.
  * One run of at most 100 days; ROE formations are not split into
    segments.
  * A follower cannot have both an ROE formation and phasing keeping.
  * The impulsive law fires only in sunlight: a burn whose location is in
    eclipse waits for another, and the formation can move meanwhile
    (template 29's along-track offset slips 2 km this way).

## Planned, not yet built

Scoped from real use, with the detail in
[`HISTORY.md`](../../HISTORY.md):

* **`engine.constellation`'s Walker generator doesn't auto-wire
  `PhasingKeepingConfig`** for the satellites it produces -- each
  follower's chief/target-separation still needs setting up by hand in
  the spacecraft editor afterward. A natural, well-scoped follow-on once
  that manual step is felt to be tedious in practice: the generator
  already knows each plane's membership and phase ordering, so it could
  assign chief = "first satellite in the plane" and a sensible default
  target separation automatically.
* **A live NUMERIC link-margin gauge in Vizard** -- still deliberately
  not built: Vizard's `GenericStorage` only accepts Battery/DataStorage/
  FuelTank-shaped messages, and forcing a dB margin value (which can be
  legitimately negative) through would need a fabricated adapter message
  with no natural floor/ceiling -- the same bug class the RTN separation
  panels already hit once and had fixed (see `HISTORY.md`). What WAS
  built instead, per direct user feedback that the Mission Dashboard's
  live telemetry "shall also be in the vizard live visualization, not
  only in the GUI itself": a colored "Link status" `GenericSensor` badge
  (link OK vs. no/degraded link, computed live from the exact same
  `engine.link_budget.link_margin_db` the GUI uses), plus "Mode" and
  "Pointing Error" panels for the rest of that same dashboard -- see
  `engine.vizard`'s own "Live-data panels" docstring section. The exact
  dB breakdown still only appears in the GUI's dashboard; if a live
  NUMBER (not just a status) is wanted in Vizard too, the right path
  remains a real custom Vizard protobuf message/panel type, not a reused
  `GenericStorage` shape.

Beyond these, the list above is the rest of the map: spherical-harmonics
gravity and magnetometers away from Earth, and richer Monte Carlo
retention.

---

**Next:** [Capabilities and verification](capabilities.md) ·
[FAQ](../faq.md) ·
[Documentation index](../README.md)
