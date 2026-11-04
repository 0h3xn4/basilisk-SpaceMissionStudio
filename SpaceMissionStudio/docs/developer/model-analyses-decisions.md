# Analyses built on the 3D model: decision log

Every non-trivial choice made while building the feature
(`feature/model-analyses`), with the alternatives and why. The design is
[model-analyses-design.md](model-analyses-design.md).

## D-01: The "UI only during the overhaul" rule of `CLAUDE.md` does not apply

- **Chosen:** change the engine, the schema, the CLI and the outputs as
  the brief requires.
- **Alternatives:** keep to the rule, which would make the brief
  impossible.
- **Why:**
  - The rule dates from the UI overhaul, finished in 1.3.0. Releases 2.0.0
    and its transparency work changed all of these since.
  - The brief explicitly asks for scenario data, CLI commands and new
    outputs.
- **Kept from the rule's intent:** every existing template's outputs and
  golden files stay byte-identical. New series and events appear only for
  a spacecraft that opts in (`model_analyses`).

## D-02: Parts are identified by their name

- **Chosen:** a part's unique `name` is its stable identifier, as today.
  A face is `(part name, face name)`, with the face names `derive()`
  already gives (`+x`, `side 3`, `plane 2`, ...). Renaming a part goes
  through `schema.references.rename_part`, which updates every mount,
  pose, face property and equipment item that names it.
- **Alternatives:** add a generated `id` (a UUID) to every part, with a
  migration.
- **Why:**
  - Names are already unique, validated, and kept across save and load.
  - The app follows renames the same way for spacecraft and ground
    stations.
  - An `id` field would rewrite every saved model and template file, and
    would still need the same reference handling.
  - Reordering parts, which the editor cannot do today, changes nothing.
  - Deleting a part leaves a dangling reference, which validation
    reports by name.
- **Not stable:** face names of an imported mesh (`plane k`, ranked by
  area) change when the mesh or its scale changes, so a face property
  names one of the shape's face groups. For a mesh part, a property is
  per part only.

## D-03: Mounting extends the existing definitions; new items only for what has none

- **Chosen:**
  - An optional `mount` on `SensorConfig` and `ActuatorConfig`, and
    `antenna_mount` on `RFLinkConfig`.
  - A mount takes what the definition already has (a thruster's `r_B` and
    `tHat_B`, a sun sensor's `nHat_B` and `fov_deg`, the antenna's
    boresight and beamwidth) and adds only what is missing.
  - `model.equipment` holds items the scenario has no definition for: a
    payload camera, an orbit-thruster nozzle, a solar-cell panel, a
    radiator, a unit.
- **Alternatives:** one parallel list of all equipment.
- **Why:** the brief asks to reuse the existing definitions. A parallel
  list would let a sensor's direction in the dynamics and in the checks
  disagree.

## D-04: Model parts do not articulate

- **Chosen:**
  - The checks use the deployed and the stowed configurations, and the
    run analyses the deployed one.
  - The flexible arrays' small deflections (`hingedRigidBodyStateEffector`)
    are not followed by the model parts drawn for them.
- **Alternatives:** add hinges and drive angles to the model.
- **Why:**
  - The model has no hinges, and no Basilisk solar-array drive or
    articulated facet is used (`setNumArticulatedFacets(0)`).
  - Adding articulation would be a new dynamics feature, beyond the
    brief.
- **Recorded in:** the limitations.

## D-05: Stowed configurations are for static checks only

- **Chosen:** no mass-property switch at a deployment event in the
  Mission Sequence.
- **Why:**
  - Basilisk's hub takes `mHub`, `IHubPntBc_B` and `r_BcB_B` as properties
    that can be written between steps through its public API. Writing new
    values mid-run is a step change of the inertia and centre of mass
    with no exchange of angular momentum between the bus and the moving
    parts: the attitude would carry the wrong momentum after it.
  - A physical deployment needs the parts as state effectors (hinged
    bodies), which the model does not have (D-04).

## D-06: Ray casting is exact per primitive, triangles only for meshes

- **Chosen:** analytic intersection with boxes, panels, prisms, cylinders,
  cones and spheres in each part's frame, and Möller–Trumbore with a BVH
  for imported meshes.
- **Alternatives:** tessellate everything and cast against triangles.
- **Why:**
  - Exact for curved shapes, where tessellation errs by up to
    `r (1 - cos(pi / n))`.
  - Fewer tests per ray.
  - It validates against analytic intersections, as the brief asks.

## D-07: The run analyses are post-processing, except the torques

- **Chosen:**
  - Blinding, antenna obstruction, shading, exposure and brightness are
    computed from a finished run (`_extract_results`), like the link
    margin.
  - The disturbance torques are recorded in the run, because Basilisk
    computes them only during it.
- **Why:**
  - The brief prefers post-processing where nothing feeds back into the
    dynamics.
  - Basilisk's effector forces and torques exist only during the
    integration.

## D-08: Atomic-oxygen number density is an upper bound

- **Chosen:** `n_O = rho / m_O`, all the neutral mass density counted as
  atomic oxygen.
- **Alternatives:**
  - a species model, which needs NRLMSISE-00 species output. Basilisk's
    `msisAtmosphere` gives the total density and the temperature only;
  - a fixed oxygen fraction, which could not be sourced for all
    altitudes and solar conditions.
- **Why:** it uses the density the run used for drag, as the brief asks,
  and it errs on the side of more erosion. It is labelled as an upper
  bound in the results and the docs.

## D-09: Shading is reported beside the power budget, not fed into it

- **Chosen:** the shaded solar-cell faces' power is computed after the run
  (`<sc>.shading.power`, unshaded and shaded) and the energy lost is
  reported beside the power budget. The run's own power (Basilisk's
  `simpleSolarPanel`) is not changed.
- **Alternative, planned first:** an in-run module multiplying the body
  panel's `panelEfficiency` by `1 - f_shade` each step, as the degradation
  module does.
- **Why it was dropped:** the efficiency is already written each step by
  the degradation module at priority 51, just before the panels at 50; a
  module that multiplied it would have to run strictly between the two,
  which integer task priorities cannot express without moving the
  degradation module, a change to existing behaviour. The body panel is
  also not a face of the model, so which faces shade it would be a guess.
  The brief allows presenting the shading alongside.

## D-10: Brightness is diffuse only

- **Chosen:** Lambertian reflection from `diffuse_coeff`.
- **Alternatives:** add a specular term from `specular_coeff`.
- **Why:**
  - A specular glint depends on surface flatness and the exact
    Sun–observer geometry.
  - It cannot be validated here without measured light curves.
  - The brief allows specular only if justified and validated.

## D-11: No launcher envelope in the library yet

- **Chosen:** the envelope library (`config/envelopes.py`) is empty, and a
  launcher check takes a user-defined cylinder, box or profile with its
  own limits and source.
- **Why:**
  - The Moog ESPA and SpaceX Rideshare user's guides could not be
    reached from the environment this was built in.
  - The only ESPA figures found were on a NASA GSFC slide, and they
    disagree with the commonly quoted envelope (24 x 24 x 38 in against
    24 x 28 x 38 in).
  - The brief says to leave out any envelope that cannot be sourced.
- **Adding one later:** add an `Envelope` with its source.

## D-12: Values that could not be verified are left out

What could not be read in a primary source was not given a default:

- the ESA margin philosophy (SRE-PA/2011.097) and ANSI/AIAA S-120A-2015
  percentages;
- the ESPA and rideshare envelopes (D-11);
- star-tracker Sun, Earth and Moon exclusion angles (no default: the user
  enters them, and the template cites the field of view it uses);
- the ISO 24113:2023, ESA and French casualty-risk thresholds;
- the SMAD aerodynamic and magnetic worst-case constants and the
  `h = T P 0.707 / 4` rule;
- the UN world population (so no default population density, D-16);
- re-entry emissivities (D-14).

**Where the sources were read:** only NASA's technical reports server
(NTRS) and nasa.gov could be reached. Every value used comes from a NASA
document read there, cited per value in `config/materials.py` and
`docs/models/`. `docs/developer/model-analyses-sources.md` lists the
reads.

## D-13: Mass growth allowance from AIAA S-120-2006

- **Chosen:** the mass budget's default policy is AIAA S-120-2006's mass
  growth allowance table: six maturity codes (estimated to measured) by
  eleven subsystem columns, electronics split by unit mass. It is taken
  from NASA GRC COMPASS report CD-2012-72, Table 2.3, which reproduces it.
- **Subsystem:** a part's `subsystem` picks the column. A subsystem that
  is no S-120 column takes the row's largest allowance (the conservative
  choice), and the report says so.
- **System margin:** optional and user-set, default none. The 30 % that
  COMPASS adds is the COMPASS team's practice, not the standard's.
- **Not used:** ESA's margin philosophy, which could not be read (D-12).

## D-14: Re-entry re-radiation is bracketed, not assumed

- **The problem:** DAS 3.0's material table gives no emissivity, and no
  read source gave one at re-entry temperatures.
- **Chosen:** each fragment is computed twice:
  - without re-radiation, which heats it most and is the demise-prone
    bound;
  - with an emissivity of 1, the largest re-radiation and the survival-
    prone bound. Rochelle et al. (NTRS 19970040121) used 1.0 and 0.3 as
    parametric emittances.

  The casualty area and risk reported are those of the survival-prone
  bound, the conservative one, and the other is shown beside it.

## D-15: The Sutton–Graves constant is derived from the 1971 report

- **Chosen:** `k = K_air / (2 sqrt(p_atm)) = 1.748e-4 kg^0.5 / m`, from
  Sutton & Graves's `K_air = 0.1113 kg / (s m^1.5 atm^0.5)` (NASA TR
  R-376, Table II). It assumes `p_stag = rho V^2` and
  `h_s - h_w = V^2 / 2`, as Carroll et al. (NTRS 20220018610) state for
  the simplified form.
- **Why:** the often-quoted 1.7415e-4 could not be found in a read source.
  The derivation is in `docs/models/reentry.md`.

## D-16: The population density is the user's

- **Chosen:** the casualty expectation `E_c = A_c * rho_pop` needs a
  population density the user enters. Without one, the page gives the
  casualty area, and says the risk needs the density.
- **Why:**
  - DAS uses inclination- and year-dependent population tables, which
    are not available here.
  - The UN population needed for a global mean could not be read
    (D-12).

## D-17: "Observer in darkness" is the Sun below a set depression angle

- **Chosen:** the brightness is computed while the Sun is below the
  observer's horizon by at least a parameter, by default 0 deg (geometric
  sunset).
- **Why:** 0 deg is a definition rather than a sourced darkness level. The
  twilight definitions (civil 6 deg, nautical 12 deg, astronomical 18 deg
  below the horizon) could not be read in a primary source here, so the
  user sets one of them.

## D-18: Wheel and magnetorquer sizing flags a shortfall, with no margin

- **Chosen:** the wheels' momentum capacity per body axis and the
  magnetorquers' dipole are compared with what the disturbances need, and
  a ratio below 1 is a finding. The ratio is shown, so a margin can be
  read off it.
- **Alternatives:** require a margin above 1 (a factor on the momentum
  per orbit), as handbooks do.
- **Why:** no margin factor for wheel or magnetorquer sizing could be read
  in a primary source here (the SMAD rules of thumb are among the values
  not verified, D-12). Flagging only a shortfall needs no number.
- **The dipole needed** is `|H_orbit| / (P |B|_mean)`, the least that
  could remove one orbit's momentum with the field always perpendicular:
  a lower bound, said so in the finding.

## D-19: The disturbance torques are recorded by an app module, from Basilisk's own values

- **Chosen:** a Python `SysModel` (`engine/disturbance_recorder.py`),
  added only for a spacecraft with `model_analyses.disturbance_torques`,
  after the spacecraft in the task. It reads the drag and SRP effectors'
  public `forceExternal_B` and `torqueExternalPntB_B` and moves the
  torque to the centre of mass (`T_c = T_B - r_CB x F`). It computes the
  gravity-gradient torque from the state (SP-8024's vector form) and the
  residual-dipole torque from WMM, which is added to the run only for a
  non-zero dipole.
- **Alternatives:** record Basilisk's `gravityGradientOutMsg`, which
  exists only when the run applies the gravity-gradient effector; compute
  the facet torques again in the app.
- **Why:**
  - Drag and SRP stay as Basilisk computes them, unchanged, as the brief
    requires; nothing recorded is fed back.
  - The gravity gradient is wanted whether or not the run applies it, and
    on the same instants as the others.
  - The effectors' attributes hold their last evaluation of the step (the
    integrator's final stage), within a step of the step's end.
- **Not followed:** the centre of mass and inertia are the hub's; moving
  propellant and flexible arrays do not change them here.

## D-20: Template 32's design values are an example, its envelope illustrative

- **Chosen:** template 32's dimensions, masses, mounts, plume half-angle
  and launcher envelope are the example spacecraft's design, as in every
  template; the envelope is labelled "an illustrative envelope for this
  template, not a launcher's" in its `source`. The star tracker's 20 deg
  field of view is the Terma T1's (NASA/TP-20250000142, Table 5-5). The
  growth allowances are the library's (D-13).
- **Not given:** exclusion angles (none sourced, D-12), a mass limit and
  launcher mass or centre-of-mass limits (no launcher's could be read,
  D-11).
- **Why:** the brief asks every default, limit and material property to
  be sourced; a template's own design inputs are not defaults, but the
  envelope looks like a launcher's limit, so it says it is not one.

## D-21: The 3D model editor does not yet edit equipment or draw cones

*Superseded by D-24 for the equipment, the stowed poses and the cones.*

- **Chosen:** mounts, equipment, stowed poses, materials, maturity, face
  properties, the mass budget and the launcher are edited in the scenario
  file (the Scenario's JSON view, which validates them with their
  messages); the spacecraft editor's 3D model page edits the run analyses
  (`model_analyses`). The 3D model editor does not yet have Equipment and
  Stowed tabs, nor draw the fields of view and plume cones.
- **Why:** the time went to the analyses, their validation and their
  outputs; every analysis is reachable in the GUI (Design Checks, Model
  Analyses, End of Life), the CLI and the API. The editor tabs are the
  first follow-up (`docs/reference/limitations.md`).
- **The bus presets** (`engine/spacecraft_templates.py`, 100 to 500 kg)
  are left as they are: giving them a 3D model would replace their box
  facets and mass properties with the model's, which changes their runs'
  results; the brief allows updating them only where results do not
  change.

## D-22: Three commits by kind, not one per step

- **Chosen:** the branch is committed as the developer documents (design,
  decisions, progress, sources), then the code with its tests and the
  generated compliance documents, then the user documentation and the
  V&V record. The full suite and coverage ran on the final state before
  the commits.
- **Alternative:** a commit per step of the plan, each passing the suite.
- **Why:** the steps share files (`cli.py`, `api.py`, `engine/findings.py`,
  `engine/service.py`, the main window, the parameter registry and its
  test), so per-step commits made afterwards would need partial staging
  that no suite run had checked. A commit whose state was never tested
  would be worse than a larger one that was. This deviates from the
  brief's "small reviewable commits"; the progress file's step list is
  the reading order for review.

## D-23: Review fixes, and one finding left as it is

A review of the branch (PR #209) found seven points.

- **Fixed:**
  - A part that could not be built was missing from the scene, so the
    analyses ran without it, and the re-entry estimate left its mass out.
    The analyses now refuse such a model and name the part
    (`analyses.common.derived_and_scene`).
  - The exposure table's materials were looked up without the scenario's
    folder, so a mesh given by a relative path had none. `report()` now
    takes the folder, and defaults to the scenario file's.
  - A segmented run (past 100 days) sized the wheels and magnetorquers
    once per segment. The whole run's budget now replaces those findings
    (`engine.long_run`).
  - Array shading cast rays in umbra, where the flux is zero. It no
    longer does, and its shaded fraction there is 0. Template 32's golden
    file was re-recorded for this, and its power is unchanged.
  - Antenna obstruction paired a pass time with the next sample rather
    than the nearest one.
  - The editor's checks at every edit cast the design checks' rays
    again for spacecraft that had not changed. Their findings are now
    kept per spacecraft content.
- **Left as it is:** the re-entry descent's fixed 0.05 s RK4 step. A
  very light fragment with a large surface, falling at under 1 m/s,
  takes many steps to reach the ground. For template 28's parts (about
  0.3 m^2/kg) it takes seconds. An adaptive step, or stopping once
  nothing more can melt, would change the validated numbers, and either
  would need its own validation case. Recorded as a limitation.

## D-24: The 3D model editor's Equipment and Stowed tabs, and the cones

- **Chosen:** two tabs beside Mass properties and Surfaces
  (`gui/model_equipment_tabs.py`):
  - **Equipment** edits the model's own items (`model.equipment`) and
    the mounts of the spacecraft's sensors, actuators and RF antenna.
    The editor is given a copy of the devices and returns their
    mounts. The spacecraft editor copies them back
    (`apply_device_mounts`, `SensorActuatorListWidget.set_mounts`).
  - A device's position and boresight are optional: left unticked,
    they come from the device's definition (D-03).
  - **Stowed** gives the selected part a stowed pose, and switches the
    view between the deployed and stowed configurations.
  - The view draws each field of view as a translucent cone along the
    boresight, each plume as a cone along minus the boresight, and
    other items as a short line. The selected item is drawn stronger.
    A cone has a constant slant length (45 % of the model's largest
    size), so a field of view wider than 180 deg opens backwards
    rather than flattening.
- **Fixed with it:**
  - Renaming a part in the editor left the mounts, stowed poses and
    face properties that named it dangling, and OK then refused the
    model. They now follow the part (`schema.references.rename_part`).
  - Deleting a part that carries equipment is refused, naming the
    equipment. Its stowed pose and face properties go with it.
  - The spacecraft editor dropped the RF link's `antenna_mount` on OK.
    It is now kept.
- **Not in this step:** materials, face properties, the mass budget's
  policy and the launcher envelope are still edited in the scenario
  file's JSON view.
- **Alternative:** a mount group in each device's own form (the sensor
  and actuator editors). It was not taken: a mount is about the model's
  geometry, and needs the parts and the view to set it well.

## D-25: The rest of the model in the 3D model editor

- **Chosen** (`gui/model_property_tabs.py`):
  - **The part form** gives each part:
    - a material (the library's, then the model's own);
    - a maturity category of the mass budget's policy;
    - a subsystem;
    - per face, a material and reflection coefficients in place of
      the part's. A blank cell keeps the part's, and a face with
      nothing of its own has no entry.
  - **Materials** edits the model's own materials.
    - The erosion yield is shown in units of 1e-24 cm^3/atom, so a
      typical value reads 3.0 rather than a long string of zeros.
    - A rename follows the parts and faces that use the material.
    - A material in use cannot be deleted, and a library name is
      refused.
  - **Budget and launcher** edits the mass budget (policy, system
    margin, mass limit and its source) and the launcher envelope (a
    library envelope, or a custom cylinder, box or profile, with its
    plane, axis, limits and source). Each is a checkable group:
    unticked, the model has none.
- **Fixed with it:** the bottom tabs are now in scroll areas. Since
  D-24 added the Equipment tab, the tallest tab's form squeezed the
  parts list, the part form and the 3D view to about 150 px at
  1600 x 900. The `model_editor.png` screenshot is re-captured with the
  seven tabs.
- **Result:** nothing in a model needs the JSON view any more. The
  limitations page keeps only the empty launcher library (D-11).
