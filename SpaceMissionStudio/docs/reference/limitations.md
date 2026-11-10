# Known limitations

What SpaceMissionStudio does not do, or does only in part, and why.
Each item was checked against Basilisk's own source.

* **Four integrators.** The app offers Basilisk's `svIntegratorEuler`,
  `svIntegratorRK2`, `svIntegratorRKF45` and `svIntegratorRKF78`
  (`schema.scenario.SimSettings`, `engine.service._INTEGRATORS`);
  `"rkf78"` is the default. Basilisk 2.12.0 has more (RK4 and other
  Runge-Kutta variants), which the app does not offer yet.
* **Spherical-harmonics gravity for Earth and Mars only**
  (`engine.gravity_field`: GGM03S, GGM2B). The other central bodies are
  point masses (`central_body_degree=0`); Eros can use its shape model
  instead. The field's GM is Basilisk's for the body, not the file's
  (1.4e-8 apart for Earth, 1.4e-6 for Mars; deviation D-07). Mean
  elements stay Earth-only: they need the elements on the body's
  equator, and the run's frame is Earth's.
* **Small bodies and landmark navigation (`engine.small_bodies`,
  `engine.polyhedron`, `engine.landmarks`, `engine.landmark_navigation`).**
  * 433 Eros only, only as the central body; one run of at most 100 days
    (segmented runs are not verified around it), inside the ephemeris
    kernel's 1900 to 2100.
  * The shape's gravity is at constant density.
  * Eros's shadow is a sphere of its 8.42 km mean radius (Basilisk's
    eclipse model takes only spheres).
  * Basilisk's `pinholeCamera` does not check whether other terrain hides
    a landmark; no image is rendered.
  * The filter knows the shape, GM, spin, attitude and landmark positions
    exactly, and leaves out the Sun's pull and light pressure (its
    process noise covers them): results are optimistic.
* **Optical navigation (`engine.opnav`, `engine.optical_navigation`).**
  * No image is rendered or processed: the disk's centre and size are
    computed from the true geometry with Gaussian pixel noise. A
    crescent's centre, which real image processing finds offset from the
    planet's, is taken as the planet's, so results near 90 deg phase are
    optimistic.
  * Attitude knowledge is perfect (the converter reads the true
    attitude).
  * Earth, the Mars barycentre and the Jupiter barycentre only (the
    bodies Basilisk's `pixelLineConverter` and `relativeODuKF` know); one
    run of at most 100 days.
  * The filter's model is two-body: the Sun and higher gravity terms act
    in the run but not in it, and its 3-sigma bounds held 94-95 % of the
    axis errors in the measured runs, a little optimistic.
* **Mars and Jupiter are their system barycentres** (`"mars barycenter"`,
  `"jupiter barycenter"`): the bundled DE430 ephemeris has no state for
  the planets themselves. Basilisk gives each the planet's own mass and
  radius. The Mars barycentre is about 0.2 m from Mars's centre (Phobos
  and Deimos); Jupiter's is moved by the Galilean moons by up to about
  230 km (the sum of their mass ratios times their orbit radii), which
  matters for close Jupiter orbits.
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
  `14_css_sun_heading_estimation.json`). Albedo (the planet's reflected
  sunlight) reaches the coarse sun sensors only, from Earth or Mars: Basilisk's
  `simpleSolarPanel` takes no albedo, so solar arrays and the power budget
  see the Sun alone, and thermal sensors see no albedo or planet infrared.
  The albedo map is a 2018 annual mean (CERES) or a TES mean, not the
  clouds of the day. A full attitude DETERMINATION
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
  you. Since 2.0.0 the attitude form shows the gains applied, not the
  unscaled reference values.
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
  2.12.0); the schema default stays `1`. A batch uses at most one process
  per CPU, and validation refuses more than 256 processes or 100 000 runs.
* **Two Monte Carlo batches of the same scenario draw the same samples**:
  Basilisk's Monte Carlo controller seeds each run from its number
  (SRelD K-24).
* **Monte Carlo retains a fixed set of data per run** (each spacecraft's
  position/velocity) -- there is no per-run custom retention-policy
  selection in the schema yet.
* **No Jacchia-Roberts atmosphere model, no Earth-albedo/IR radiation
  pressure, no user-supplied density table.** All
  three were real user questions/requests, checked directly against
  Basilisk's own source (not assumed) before answering:
  * Jacchia-Roberts genuinely doesn't exist anywhere in Basilisk (checked
    `src/simulation/environment/` -- only `ExponentialAtmosphere`,
    `MsisAtmosphere`, `TabularAtmosphere` do); `atmosphere_model` offers
    those three (`nrlmsise00`, `exponential`, `tabular`; see [Orbital dynamics & propagation](capabilities.md#orbital-dynamics--propagation)), not the
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
  * A user-supplied altitude/density table would need a new file-upload
    schema/GUI concept of its own. The tabular atmosphere
    (`space_weather.atmosphere_model: tabular`) takes only the three
    published profiles Basilisk ships, by one altitude column: no
    latitude, local time or solar activity, and a density of 0 beyond
    the table's ends
    ([Environment data](../models/environment-and-data.md#the-atmosphere)).

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
  * Facets apply only in full-attitude runs; an orbit-only run keeps
    `drag_area_m2` and `srp_area_m2`.

* **IDM-CIC import (`spacemissionstudio.idm`, `idm_import`).**
  * Checked against hand calculations on a synthetic model, not against
    IDM-CIC's own mass report: no example model stores IDM-CIC's totals.
  * Some conventions are assumed and reported as such: the corner of
    extruded triangles and quadrangles, sphere and torus centres, inward
    thicknesses, the tank's straight part between z = 0 and its height.
  * Not modelled, mass kept as a point: STEP and Collada shapes, pipes,
    paths, labels, Boolean intersections and section planes. Rounded box
    edges and the stretch factor are ignored.
  * A typed-in inertia matrix, mass margins and maturity levels are
    reported, not applied; thermal data and the power modes'
    dissipation are not imported.
  * The power budget has one constant load: the import sets it to one
    system mode's total (or the duty-cycle average), not a mode
    timeline. An equipment a system mode does not set is counted as
    0 W. The panel area is the largest flat face of each solar array
    panel along one normal line; panels along other lines, and the side
    carrying the cells, are not read. A power budget the import makes
    has the editor's panel efficiency and battery until they are set.
  * Devices are found by their names only. A sensor without a catalog
    product runs with Basilisk's defaults until its values are set (the
    pre-run checks say so); wheels and magnetorquers are added only with
    a product or properties that give their values. A thruster goes to
    the 3D model's equipment for the design checks, not to the
    simulated actuators, and only by default when a plume cone shows its
    direction; its specific impulse is not read. Batteries are listed,
    not added; solar arrays can set the power budget's panel, and a
    battery's capacity property its battery.
  * A team's properties are read only when mapped, in the unit the user
    gives: the file states none for an untyped value, and the format's
    description none for a typed one. Ten values can be mapped (wheel
    torque, inertia, speed and momentum, magnetorquer dipole, star
    tracker and gyro noise, sun sensor field of view, thruster thrust,
    battery capacity).
  * The file has no boresight field: a device's axis is read from its
    shapes (a field-of-view cone, or a wheel's or magnetorquer's
    cylinder), else +z of its equipment frame. A cone's angle is the
    mount's field of view, shown in the 3D view; it does not set a sun
    sensor's simulated field of view, since a drawn cone may be a
    margin rather than the specification. A thruster's cone is read as
    its plume: the thruster sits at the cone's tip and pushes against
    it; a nozzle drawn as a cone larger than the plume would be read
    instead, with its throat as the start.
  * The body frame's origin is the body element's own unless the user
    puts it at the centre of gravity of the model as imported (to the
    micrometre); a position typed in a form that shows fewer decimals
    (the fuel tank's, to the millimetre) is moved to that precision.
  * Model versions 3.4 and 3.5 are read; others with a note. The
    IDM-CIC licence was not available to review; the reader uses only
    the format's published description.

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

* **Analyses built on the 3D model (`analyses/`, `model3d/raycast.py`).**
  Out of scope, by design:
  * any change to Basilisk, including self-shadowing in drag or solar
    radiation pressure: those stay as Basilisk computes them, and the
    shadowing here is the app's own analyses' only;
  * radiation doses and effects; structural analysis (stiffness and
    fundamental frequencies are not checked against a launcher); plume
    physics (the plume check is a cone of the user's half-angle);
    reaction-control (RCS) sizing; high-fidelity break-up; CubeSat
    checks (the target is 100 kg and above).

  Limits of what is done:
  * Model parts do not articulate: the checks use the deployed and the
    stowed configurations, the run analyses the deployed one, and a
    flexible array's deflection is not followed (decision D-04). There is
    no mass-property switch at a deployment in the Mission Sequence
    (D-05).
  * Ray-cast results are sampled: each comes with its standard error;
    raise `model_analyses.samples` to shrink it.
  * The atomic-oxygen density counts all the neutral density as oxygen,
    an upper bound (D-08); brightness is diffuse only (D-10); "dark" is
    the Sun below a depression angle, by default geometric sunset (D-17).
  * The disturbance torques use the hub's centre of mass and inertia:
    moving propellant and flexible arrays do not change them.
  * The launcher envelope library is empty: an envelope and its limits
    are the user's, with their source (D-11). No margin is required on
    the wheels and magnetorquers, only a shortfall flagged (D-18).
  * The re-entry estimate is preliminary and simplified (one lumped mass
    per part, a planar descent, the emissivity bracketed): not a
    substitute for DAS, DRAMA or SESAM. Its population density is the
    user's (D-16). Its descent takes a fixed 0.05 s step to the ground,
    so a very light part with a large surface (one that falls at under
    1 m/s) can take minutes to estimate (D-23). See
    [the method](../models/reentry.md).
  * Star-tracker Sun, Earth and Moon exclusion angles have no default:
    no datasheet could be read (D-12).
  * The launcher envelope library is empty (D-11): the 3D model
    editor's Budget and launcher tab takes the user's own envelope.

* **The JSON page (`gui/code_editor.py`, `gui/json_assist.py`,
  `gui/json_refactor.py`).**
  * Qt's own text editor (decision JE-01): no code folding, no multiple
    cursors, no minimap.
  * Completion offers what the scenario's records and the validation's
    choices allow; a device's `params` offer what its form offers for its
    kind and are not checked there, and a mission step's `params` its
    kind does not read are a warning (the run ignores them).
  * Rename (F2) covers spacecraft, ground stations and 3D model parts,
    as their forms do; devices and materials are renamed in their forms.

* **The 3D View (`engine/scene3d.py`, `gui/mission_view_widget.py`).**
  * A playback of the run's own series, not a renderer: at most 1,500
    frames, each spacecraft's attitude the nearest recorded one (an MRP
    that switches to its shadow set cannot be interpolated).
  * The Earth turns by the IERS Earth rotation angle, with UT1 taken as
    UTC and precession left out: about 0.4 degrees from the true
    Earth-fixed frame in 2030. Its colours are Basilisk's all-sky albedo
    map, mostly cloud, not a land map.
  * The Sun's direction (the Astronomical Almanac's formula, about 0.01
    degrees) is drawn for Earth-centred runs only; other central bodies
    are plain spheres that do not turn.
  * No instrument or camera views, no panels, and no view while the run
    is still going: it shows a run once it has ended.

## Planned, not yet built

The list above is the map: spherical-harmonics gravity and magnetometers
away from Earth, and richer Monte Carlo retention, among others.

## Known limits of 2.0.0

From the [changelog](../../CHANGELOG.md):

* **The bundled space weather is that of 1.3.0:** observations to
  2026-10-24 and CelesTrak's daily forecast to 2026-12-07. Before a drag
  study, fetch the current file: the **Fetch or update reference data?**
  card on Home, **Settings > Reference data**, or `spacemissionstudio
  spaceweather-download`.
* **Some actions hold the window for longer than the 50 ms the interface
  aims at:** changing the theme (about 0.4 s), the first visit to a
  spacecraft page and opening a template (SRelD K-19, K-23).
* **The installers ship pillow 12.2.0, which has published advisories**,
  all about decoding crafted image files, which SpaceMissionStudio does
  not do (SRelD K-25). The qualified Basilisk (2.12.0) allows no later
  version.
* **The last check of the definition of done is the team's:** timing an
  engineer who did not build the tool as they trace each number to its
  calculation ([the definition of done](../definition-of-done.md)).
* **Python 3.14 only:** 3.11 to 3.13 are no longer supported, and
  Basilisk 2.12.0 and PySide6 6.11 do not install on 3.15 yet.

---

**Next:** [Capabilities and verification](capabilities.md) ·
[FAQ](../faq.md) ·
[Documentation index](../README.md)
