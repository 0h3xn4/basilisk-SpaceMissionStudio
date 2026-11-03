# Analyses built on the 3D spacecraft model: design

Status: design for the feature branch `feature/model-analyses`, written
before the feature code (Step 0 of the brief). The decisions behind it are
in [model-analyses-decisions.md](model-analyses-decisions.md), and the
progress in [model-analyses-progress.md](model-analyses-progress.md).

Target: spacecraft of 100 kg and above (ESPA-class microsatellites and
small satellites), with deployed arrays and antennas, star trackers,
propulsion and internal units. Nothing here changes Basilisk, or what
Basilisk computes; every analysis is SpaceMissionStudio's own code, using
Basilisk modules only through their public API.

## 1. What exists

### 1.1 The 3D model

- **Schema** (`schema/scenario.py`): `SpacecraftConfig.model` is a
  `SpacecraftModelConfig` holding `parts` (`ModelPartConfig`), `meshes`
  (imported `.obj` files), the mass-property source (computed, typed or
  imported) and three switches: apply the mass properties, apply the
  facets, use the model for Vizard.
- **Primitives:** box, prism (regular n-gon), cylinder, cone, sphere,
  panel (a thin box), and a group of an imported `.obj` mesh. Each shape
  has its own local frame, centred on its bounding box.
- **Placement:** `position_b_m` and `rotation_deg = [roll, pitch, yaw]`, a
  3-2-1 sequence (`R = Rz Ry Rx`, `x_B = R x_local + p`). Everything is in
  the body frame B, from point B.
- **Identity:** a part is identified by its `name`, unique within the
  model (validated) and free of path characters. There is no separate ID.
  Faces are not saved; `derive()` recomputes them on every call and names
  them `"<part>: <face>"`:
  - box: `+x ... -z`
  - prism, cylinder and cone: `side k`
  - sphere: `face k`
  - mesh: `plane k`, ranked by area
  - the named groups of `MODEL_SHAPE_FACES`, which `excluded_faces`
    refers to

  Names survive save and load (`asdict`), and the order of parts is kept.
  Mesh files are referred to by index into `model.meshes`; the editor
  renumbers them when a file is dropped.
- **Mass properties** (`model3d/mass_properties.py`): exact solid or shell
  integrals per part, combined about the centre of mass.
- **Facets:** from the outer faces (`surfaces.py`), at most 200. They
  carry each part's `drag_coeff`, `specular_coeff` and `diffuse_coeff`
  and become `FacetConfig`s. Basilisk's `facetDragDynamicEffector` and
  `facetSRPDynamicEffector` read them (`engine/service.py` 1431-1480).
  Shading between parts is explicitly not modelled
  (`surfaces.py`, `limitations.md`).
- **Deployables:** the model has no hinge, articulation or stowed state.
  Flexible arrays are a separate list (`SolarArrayConfig`), each a
  Basilisk `hingedRigidBodyStateEffector` at `hinge_position_b`, deploying
  along `deploy_direction_b`. Model parts drawn for an array have
  `counts_toward_mass` off. The 100/150/300/500 kg buses are presets
  (`engine/spacecraft_templates.py`) with box facets and no 3D model; only
  template 28 has a model.
- **Optical and material properties:** only the specular and diffuse
  fractions per part (per facet once applied); absorption is the rest.
  There is no material name, absorptance, emissivity or material library.
- **Vizard:** `engine/vizard.py` writes the visible parts as `.obj`.

### 1.2 Equipment

Sensors and actuators are generic `SensorConfig`/`ActuatorConfig` records
(`kind`, `name`, `params`):

| Equipment | Body-frame geometry today |
|---|---|
| Star tracker | None. Basilisk `starTracker` gets noise only, so the case frame is the body frame. There are no exclusion angles. |
| IMU, magnetometer | None |
| Coarse sun sensor | `params.nHat_B` and `fov_deg` |
| Thermal sensor | `params.nHat_B` |
| Optical and landmark navigation cameras | `camera_mrp_cb` (boresight +z of the camera frame) and `field_of_view_deg`, but no position |
| RF antenna (`rf_link`) | `antenna_boresight_b` and `antenna_beamwidth_deg`, but no position |
| Attitude thrusters (`actuators` of kind `thruster`) | `params.r_B` and `tHat_B` (the force direction on the spacecraft) |
| Orbit thrusters (station keeping and the others) | None: thrust is along the velocity or in an orbital frame |
| Reaction wheels | `gsHat_B`, optional `rWB_B`, `maxMomentum` |
| Magnetorquers | `gtHat_B` and `max_dipole_a_m2` |
| Body panel (`power`) | `panel_normal_b`, area, efficiency |
| Flexible arrays | Hinge, deploy direction, normal |
| Fuel tank (Basilisk `fuelTank`) | `tank_position_b_m` |

- **Power:** Basilisk's `simpleSolarPanel` computes it. The app's own
  `PanelDegradationModule` (a Python `SysModel` at priority 51) rewrites
  every panel's `panelEfficiency` each step. That is the precedent for an
  in-run shading factor written through the public API.
- **Propellant:** the Basilisk fuel tank moves the centre of mass itself.
  The orbit-control bookkeeping changes `hub.mHub` only.
- **Link:** the margin is post-processed from the recorded slant range,
  elevation and pointing error. The `_DownlinkGate` computes the
  off-boresight angle live.

### 1.3 Environment and outputs

- **Recorded:** none of drag, SRP, gravity gradient or magnetic field, as
  forces, torques or environment values. `facetDragDynamicEffector`,
  `facetSRPDynamicEffector` and `GravityGradientEffector` expose
  `forceExternal_B` and `torqueExternalPntB_B` (and
  `gravityGradientOutMsg`) through their public API, checked on Basilisk
  2.12.0.
- **WMM** (`magneticFieldWMM`) is built only for a magnetometer or
  magnetic momentum management.
- **MSIS** (`msisAtmosphere`) gives the total neutral density and the
  temperature only; there are no species.
- **Results:** `ResultSet` holds `TimeSeries` with names
  `<sc>.<quantity>` and ground-station pairs
  `<gs>.access_to_<sc>.<part>`, on elapsed TDB seconds. Attitude
  (`attitude_sigma_BN`) exists only for runs that model attitude.
  Eclipse (`eclipse.illumination_factor`) exists whenever the Sun is
  tracked. The Sun and Moon positions are not recorded.
- **Events** (`engine/events.py`): extractors over series. The Timeline,
  the plot bands, the toasts and `events.csv` read them.
- **End of Life** (`engine/lifetime.py`, `gui/lifetime_widget.py`): the
  lifetime, the disposal rules (5 and 25 years) with traces, and a JSON
  record. There is nothing on re-entry survival.
- **Patterns to follow:**
  - Problems: `findings.RULES` plus `scenario_checks`.
  - Parameters: the registry, each with a source and a test that sets it.
  - Exports: `output_provenance`, `exports_page.EXPORTS`.
  - CLI: `cmd_x` plus `build_parser`.
  - API: thin, lazily importing wrappers in `api.py`.
  - Records: `analysis_records`.
- **Golden baseline:** every template's series and events must stay
  byte-identical (`tests/test_golden_outputs.py`).

## 2. Shared foundation

### 2.1 Ray casting: `model3d/raycast.py`

- **`Scene`:** built from a `DerivedModel` (deployed or stowed), one
  entry per built part. Each entry keeps:
  - the part's index, name, shape and dimensions;
  - its body-to-local transform;
  - its body-frame bounding box;
  - for meshes, the welded triangles in a bounding-volume hierarchy
    (BVH).
- **Exact intersection per primitive,** in the part's local frame: the
  ray `o + t d` is mapped by `R^T (o - p)`, `R^T d`.
  - Box and panel: slabs.
  - Prism: its `2 + n` planes (convex polyhedron clipping).
  - Cylinder: the quadratic of the side plus the two caps.
  - Cone: the quadratic of the side between base and apex, plus the base.
  - Sphere: the quadratic.
  - Imported mesh: Möller–Trumbore against the triangles, through the
    BVH.

  Curved shapes are therefore hit where the true surface is, not where
  their drawn facets are.
- **Vectorised over rays:** every query takes `(N, 3)` origins and
  directions and returns, per ray, the nearest distance and the hit part's
  index (`-1` for none). A part list can be excluded, for example the
  part a sensor is mounted on.
- **Top-level culling:** a slab test on the parts' bounding boxes, so a
  ray only meets the parts whose box it crosses. The mesh BVH is built by
  median split on the triangle centroids, with at most 8 triangles per
  leaf. It is traversed breadth-first with numpy arrays, so a whole batch
  of rays descends together.
- **Queries:**
  - `visible(point, direction)`: is a point visible along a direction?
  - `cone_blockage(apex, axis, half_angle, samples)`: the blocked fraction
    of a cone, in total and per part. Directions are spread uniformly in
    solid angle over the spherical cap (a Fibonacci spiral). The result
    comes with the binomial standard error `sqrt(p(1-p)/N)`.
  - `face_shadow_fraction(face, direction, samples)`: the fraction of a
    face shaded from a direction, from stratified sample points on the
    face, offset by 1e-6 of the model size along the normal. The standard
    error is reported the same way.
- **Caching:** a `Scene` is cached per configuration and model hash.
  Over a run, a direction's results are cached by direction rounded to
  0.25 deg in the body frame, so an inertially fixed or Sun-pointing
  attitude computes once per distinct direction. The cache bin is a
  parameter, and its effect is part of the reported error.
- **Performance** is measured on the largest bus template (the new
  template 32, 300 kg) and recorded in `compliance/validation/`.

### 2.2 Mounted equipment: `model3d/equipment.py`

The existing definitions are reused, with mounting added to them:

- **`MountConfig`** is a new optional `mount` field on `SensorConfig` and
  `ActuatorConfig`, and an `antenna_mount` field on `RFLinkConfig`:
  - `part`: a part name, or empty;
  - `position_m`: in the part's local frame when `part` is set,
    otherwise in the body frame;
  - `boresight`: a unit vector in the same frame;
  - `field_of_view_deg`: the full cone angle;
  - `exclusion_sun_deg`, `exclusion_earth_deg`, `exclusion_moon_deg`:
    half-angles;
  - `earth_atmosphere_km`: the margin above the limb;
  - `plume_half_angle_deg`: thrusters.
- **Defaults from what already exists:**
  - Thrusters: position `r_B`, boresight `tHat_B`, the plume along
    `-tHat_B`.
  - Coarse sun and thermal sensors: `nHat_B` and `fov_deg`.
  - RF link: `antenna_boresight_b` and `antenna_beamwidth_deg`.

  A mount only adds what is missing, so nothing is defined twice.
- **`model.equipment`:** a list of `MountedEquipmentConfig` (`name`,
  `kind`, a mount, `mass_kg`, maturity) for equipment the scenario has no
  definition for: a payload camera, an orbit thruster's nozzle, a
  radiator, a generic unit. Its `kind` is one of `camera`, `antenna`,
  `thruster`, `star_tracker`, `sun_sensor`, `solar_cell`, `radiator`,
  `unit`.
- **`mounted_items(sc, configuration)`:** every mounted item with its
  body-frame position, boresight and angles, in the deployed or stowed
  configuration. A mount on a part moves with the part's pose.
- **Reference integrity:**
  - `schema/references.py` lists mounts and poses as references to parts.
    `rename_part` follows a rename everywhere, and the editor calls it.
  - Validation rejects a mount, pose, face property or equipment item
    that names a part the model does not have.
- **The 3D model editor** draws every mounted item as a marker, with its
  boresight and its field-of-view cone (or plume cone) as a translucent
  mesh, and has an **Equipment** tab.

### 2.3 Stowed and deployed configurations

- **`model.stowed`:** a list of `PartPoseConfig` (`part`, `position_b_m`,
  `rotation_deg`) that move parts to their stowed place. Parts not listed
  stay where they are.
- **`derive(model, configuration="deployed" | "stowed")`** builds either
  configuration, with its mass properties. The default stays `deployed`,
  so everything existing is unchanged.
- **The Mission Sequence:** no switch at a deployment event. Basilisk's
  hub takes `mHub`, `IHubPntBc_B` and `r_BcB_B` as fixed properties.
  Writing new values mid-run is a jump of the inertia with no exchange of
  angular momentum, so it would not model a deployment (decision D-05).
  Stowed configurations are for the static checks.

### 2.4 Surface and material properties: `model3d/materials.py`

- **Per part:** `material` (a library key or a user material name),
  optionally overridden per face through `model.face_properties`, a list
  of `{face, material, diffuse_coeff, specular_coeff}`.
- **Diffuse reflectance is the existing `diffuse_coeff`:** the fraction of
  sunlight reflected diffusely, which Basilisk's SRP already uses. It is
  reused for brightness rather than duplicated. A face override changes
  the applied facets too, so SRP and brightness stay consistent.
- **The library:** each entry may have:
  - density, melting temperature, heat of fusion and specific heat (for
    re-entry);
  - emissivity;
  - solar absorptance;
  - atomic-oxygen erosion yield.

  Each value has its own citation (`docs/models/materials.md`). A value
  that cannot be sourced is left out, not filled in: an analysis that
  needs it says so for that face or part.
- **User-defined entries** (`model.materials`) take the same fields, each
  with a free-text `source`.

## 3. The analyses

All the analysis code is in a new package, `spacemissionstudio/analyses/`,
one module per analysis. Each module:

- reads the scenario, plus a `ResultSet` where it needs a run;
- returns a dataclass with tables, series, findings and traces;
- builds no GUI.

Shared helpers:

- `analyses/geometry.py`: attitude from the results, body-frame
  directions to the Sun, the Moon, the Earth and the velocity relative to
  the atmosphere.
- `analyses/ephemeris.py`: Sun and Moon positions from SPICE through
  Basilisk's `pyswice`, with the kernels the run loaded (`de430.bsp`,
  `naif0012.tls`).

### 3.1 Two kinds of analysis

- **Static design checks** need only the scenario:
  - field-of-view obstruction (static);
  - thruster authority and plume impingement;
  - the mass budget;
  - launcher compatibility.

  They are on a new **Run › Design checks** page, in
  `spacemissionstudio check-design`, and in `api.design_checks()` and the
  per-check functions. Their problems go to the Problems panel.
- **Run analyses** need a finished run with attitude:
  - sensor blinding;
  - antenna obstruction during passes;
  - the disturbance-torque budget;
  - array shading;
  - atomic oxygen and UV exposure;
  - brightness.

  A spacecraft opts in with `SpacecraftConfig.model_analyses`
  (`ModelAnalysesConfig`): one switch per analysis, plus its inputs (the
  residual dipole, observer sites, the sampling density). Without it,
  nothing is recorded and nothing changes, so every existing template and
  golden file is untouched.
  - **Disturbance torques:** recorded during the run. A small recorder
    `SysModel` reads the Basilisk effectors' public `forceExternal_B` and
    `torqueExternalPntB_B` each step, and a message recorder takes
    `gravityGradientOutMsg` and the WMM field.
  - **The others:** post-processed in `_extract_results`, like the link
    margin, into series and events. They therefore reach the Plots, the
    Timeline, CSV export, `run` on the command line and the run store.
  - **The GUI:** a new **Results › Model analyses** tab shows them as
    tables and plots, with export.

### 3.2 Field of view and obstruction (`analyses/fov.py`)

- **Static:** for each mounted sensor, camera and antenna, `cone_blockage`
  from its position along its boresight, over its field of view, with the
  part it is mounted on excluded. The result is the blocked fraction, the
  parts that block it with their shares, and the standard error, in the
  deployed configuration and optionally the stowed one. Model parts do
  not articulate (decision D-04), so "over the range of motion" means the
  two configurations.
- **Over the run (`blinding`):** for each mount with exclusion angles, a
  sensor is blinded while:
  - the angle from its boresight to the Sun is below `exclusion_sun_deg`;
  - the angle to the Earth's limb is below `exclusion_earth_deg`. The
    limb is the Earth's angular radius `asin((R + h_atm) / r)` from the
    Earth's centre direction, with `R` the equatorial radius and `h_atm`
    the atmosphere margin;
  - the angle to the Moon, less its angular radius, is below
    `exclusion_moon_deg`.

  Series `<sc>.sensor.<name>.blinded` (0/1, with the cause as a code),
  events of kind `sensor_blinded` per sensor, and `trackers_all_blinded`
  when every star tracker is blinded at once. The summary gives each
  sensor's availability and the longest outage.
- **Antenna obstruction:** during each pass, the ray from the antenna to
  the ground station (the station's position in N, rotated into B by the
  attitude), checked with `visible`. Series
  `<gs>.access_to_<sc>.antenna_obstructed` (0/1), shown with the link
  margin. A pass's obstructed time is reported.

### 3.3 Disturbance torque budget (`analyses/disturbances.py`)

- **Recorded,** when `model_analyses.disturbance_torques` is on:
  - `<sc>.disturbance.aero_force_B` and `aero_torque_B`, from the facet or
    cannonball drag effector;
  - `srp_force_B` and `srp_torque_B`;
  - `gravity_gradient_torque_B`;
  - `<sc>.disturbance.magnetic_field_N`, from Basilisk's WMM.

  Torques about the centre of mass are
  `tau_c = tau_B - r_BcB x F_B`.
- **The magnetic torque** is `m x B_B`, with the user's residual dipole
  `m` (body frame, A*m^2) and `B_B` rotated from N by the attitude.
- **The report:** the time series, the worst case and the orbit average
  per source and in total. It also gives the momentum accumulated per
  orbit (the trapezoidal integral of the total torque in B, restarted
  each orbital period) and over the run.
- **Sizing:**
  - The wheel momentum needed is the largest per-orbit accumulation,
    compared with the wheels' `maxMomentum` projected on each body axis.
  - The magnetorquer dipole needed is the largest torque divided by the
    smallest field magnitude. This is the standard `D = T / B` sizing
    (SMAD 3rd ed., section 11.1), compared with the rods' maximum dipole.
  - A margin is `capacity / need - 1`, flagged when negative.
- **Analytical worst case** (SMAD 3rd ed. Table 11-9) for comparison:
  - gravity gradient `3 mu / (2 R^3) |I_max - I_min| sin(2 theta)`, with
    theta = 1 deg unless set;
  - SRP `F_s / c A_s (1 + q)(c_ps - c_g)`;
  - aero `1/2 rho C_d A V^2 (c_pa - c_g)`;
  - magnetic `D B`, with the dipole field `B = 2M / R^3`.

  The areas and centre-of-pressure offsets come from the model, and the
  stated assumptions go with the result.

### 3.4 Thrusters (`analyses/thrusters.py`)

- **Authority:** for every thruster with a position and direction
  (attitude thrusters, and orbit-thruster nozzles mounted as equipment),
  the torque arm `r - r_c` and the 6 x N matrix
  `[t; (r - r_c) x t] * F`.
- **Centre-of-mass drift** with propellant use: the matrix at the
  beginning of life (full tank at `tank_position_b_m`) and at the end of
  life (empty), with the change in each torque arm.
- **Plume impingement:** a user-set plume half-angle per thruster.
  `cone_blockage` from the nozzle along `-tHat` gives the fraction of the
  cone each part intercepts. This is geometry only, with no plume flow
  physics, and the page says so.

### 3.5 Mass budget (`analyses/mass_budget.py`)

- **Inputs:**
  - per part and per mounted unit: `maturity`, a category of the cited
    margin policy, and `subsystem`, for grouping;
  - `model.mass_budget`: the policy, the system margin, the mass limit,
    and the limit's source text.
- **The report:** the mass per part, per subsystem and in total, the
  maturity margin of each, the total with margins, the system margin, and
  the result against the limit. It is exported as CSV and JSON.

### 3.6 Launcher compatibility (`analyses/launcher.py`)

- **`model.launcher`:** the envelope (a cylinder, a box, or an
  axisymmetric polygonal profile `[(z, r), ...]`), placed by an axis and
  an origin in the body frame. Optional limits on the mass, the centre of
  mass's height above the separation plane, and its lateral offset.
- **The check:** every vertex of the stowed configuration's meshes, with
  curved parts at 128 segments for this check, is measured against the
  envelope. The report gives the protrusion of each part (the largest
  distance outside) and where it is. The largest error from faceting a
  radius `r` is `r (1 - cos(pi / n))`, which is reported.
- **A library of envelopes,** only those that can be sourced
  (`analyses/envelopes.py`, decision D-11).
- **Out of scope:** stiffness and fundamental frequency, which need a
  structural model. The page says so.

### 3.7 Solar array shading (`analyses/shading.py`)

- **The array panels** are model parts with a `solar_cell` equipment item
  attached, or a mount `kind = solar_cell`. Their lit faces are the faces
  whose normal points along the mount's boresight.
- **For each output step:** the shaded fraction of each panel by the
  other parts, from the Sun direction in B (`face_shadow_fraction`). Then
  the lost power `P_loss = S A eta cos(theta) f_shade * illumination`,
  using the efficiency and area of the power configuration the panel
  belongs to.
- **Outputs:** series `<sc>.shading.<item>` (shaded fraction, incidence
  cosine) and `<sc>.shading.power` (each cell's power, the totals
  unshaded and shaded), and the energy lost over the run.
- **Beside the power budget, not in it** (decision D-09): the run's own
  power is not changed.

### 3.8 Atomic oxygen and UV exposure (`analyses/exposure.py`)

- **The atomic-oxygen flux** on a face is `n_O v_rel max(0, n . v_hat)`.
  `v_rel = v_N - omega_E x r_N` is the velocity relative to the
  co-rotating atmosphere, and `n_O = rho / m_O`. This is an upper bound
  that counts all the neutral mass density as atomic oxygen, because
  Basilisk's MSIS gives no species (decision D-08).
- **Density:** from the same model the run used for drag, through the
  app's own `lifetime` density classes (NRLMSISE-00 from Basilisk's
  module, exponential, or tabular).
- **Shading:** of the ram direction by other parts, through
  `face_shadow_fraction`.
- **Fluence and erosion:** fluence per face is the time integral of the
  flux. The erosion depth is fluence times the erosion yield, only where
  the face's material has a sourced yield.
- **Equivalent sun hours** per face: the integral of
  `max(0, n . s) * illumination * (1 - shade) dt / 3600`.
- **Reported** per face and per material.

### 3.9 Brightness (`analyses/brightness.py`)

- **The model:** a diffuse (Lambertian) reflectance per face from
  `diffuse_coeff`. The flux ratio at the observer is
  `sum A rho cos(theta_s) cos(theta_o) / (pi d^2)` over faces lit and
  facing the observer, unshaded from both directions. The magnitude is
  `m = m_sun - 2.5 log10(ratio)`. No specular term: it cannot be
  validated here (decision D-10).
- **When it is computed:** for each ground station and optional
  observer site, only while the observer is in darkness (the Sun below
  the observer's horizon by at least a depression angle, a parameter
  with the default 0 deg, geometric sunset: decision D-17), the
  spacecraft is sunlit, and it is above the observer's horizon (minimum
  elevation).
- **Outputs:** series `<site>.brightness_of_<sc>.visual_magnitude` (NaN
  when not visible) and events of kind `visible` on the Timeline.

## 4. Re-entry casualty risk (`analyses/reentry.py`)

A simplified, object-oriented estimate in the manner of NASA's DAS, on
the End of Life page, labelled as preliminary.

1. **Break-up:** at the cited break-up altitude (a parameter), every part
   with mass becomes a fragment. Its shape, dimensions and mass come from
   the model, and its material from the part.
2. **Each fragment's trajectory:** planar flight over a spherical Earth
   with point-mass gravity, starting from a circular-orbit speed and a
   flight-path angle of zero (stated assumptions). The density is the US
   Standard Atmosphere 1976 table Basilisk ships, already in the app.
   The drag coefficient is 1 on the mean projected area: for any convex
   body tumbling randomly in Newtonian flow (`C_p = 2 cos^2`), the drag
   averaged over orientations is `q S / 4`. `S / 4` is the mean projected
   area (Cauchy's theorem), so `C_d = 1` on it. The derivation is in
   `docs/models/reentry.md`.
3. **Heating:** the Sutton–Graves stagnation-point flux
   `q_s = k sqrt(rho / R_n) V^3`, with `k = 1.748e-4 kg^0.5 / m` derived
   from Sutton and Graves's report (decision D-15).
   - The nose radius is that of the sphere with the same mean projected
     area.
   - With a local flux `q_s cos(theta)` over the windward side, the heat
     absorbed by a randomly tumbling convex body is also `q_s S / 4`.
   - Re-radiation `epsilon sigma S T^4` has no sourced emissivity at
     re-entry temperatures, so it is bracketed (decision D-14): each
     fragment is computed with none (demise-prone) and with
     `epsilon = 1` (survival-prone). The survival-prone bound is the one
     reported, the other beside it.
4. **Demise:** a lumped-mass energy balance from 300 K. The fragment
   demises when the absorbed energy reaches `m [c_p (T_m - T_0) + h_f]`.
   Partial melting leaves the mass not yet melted.
5. **Casualty:** a fragment that reaches the ground with more than the
   cited kinetic-energy threshold adds `(sqrt(A_h) + sqrt(A_i))^2` to the
   casualty area `A_c`, with `A_h` the cited human cross-section.
6. **Risk:** `E_c = A_c * rho_pop`. The population density is entered by
   the user, with no default (decision D-16); without it the casualty
   area is given alone. The risk is compared with the cited threshold and
   shown beside the disposal rules.

Stated as a preliminary estimate everywhere, not a substitute for DAS,
DRAMA or SESAM.

## 5. Basilisk modules used, all through their public API

- `facetDragDynamicEffector`, `facetSRPDynamicEffector`,
  `dragDynamicEffector`, `radiationPressure`: their `forceExternal_B` and
  `torqueExternalPntB_B` attributes, read after each step.
- `GravityGradientEffector.gravityGradientOutMsg`, recorded.
- `magneticFieldWMM`: built as the app already builds it for a
  magnetometer, its `envOutMsgs` recorded.
- `simpleSolarPanel.panelEfficiency`: written each step, as the existing
  degradation module does.
- `topLevelModules.pyswice` (`spkezr_c`, `furnsh_c`, `str2et_c`) for the
  Sun and Moon after a run.
- `msisAtmosphere` and the tabular atmosphere, through the app's existing
  lifetime density classes.

Nothing requires a change to Basilisk. Drag and SRP stay exactly as
Basilisk computes them: shadowing is applied only to the app's own
analyses.

## 6. Sources

Every default and library value is listed with its source in
`docs/models/materials.md`, `docs/models/model-analyses.md` and
`docs/models/reentry.md`. The parameters are in the registry, each with
its `source`. Values that could not be verified from a primary source
were left out (decision D-12 lists them).

## 7. Implementation order

1. Schema: `MountConfig`, `MountedEquipmentConfig`, `PartPoseConfig`,
   material and face properties, the mass-budget, launcher and
   model-analyses configs, all written only when set. Then validation,
   references and `rename_part`. Existing files stay byte-identical.
2. `model3d/raycast.py`, with the analytic tests per primitive.
3. `model3d/equipment.py`, stowed `derive`, `model3d/materials.py`.
4. Static checks: `fov`, `thrusters`, `mass_budget`, `launcher`. Then
   their CLI, API, findings and the Design checks page.
5. Run analyses: the ephemeris and geometry helpers, `blinding` and
   antenna obstruction, `disturbances` (with the recorders), `shading`
   (with the in-run module), `exposure`, `brightness`. Then series,
   events, CLI, API and the Model analyses tab.
6. Re-entry on End of Life.
7. The 3D model editor: the Equipment and Stowed tabs, materials and
   maturity, cones in the view.
8. Template 32 on the 300 kg bus, with template claims.
9. Documentation, compliance V&V records, generated documents, the full
   suite and coverage.
