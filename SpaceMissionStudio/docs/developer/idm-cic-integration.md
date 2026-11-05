# IDM-CIC import: design

Status: **implemented** (`spacemissionstudio/idm/`, `idm_import.py`,
`idm-info` and `idm-import`, the 3D model editor's **Import IDM-CIC
model...**; requirement SRS-F-28; user page
[Import a spacecraft from IDM-CIC](../user-manual/idm-cic.md)). Sections 1
to 13 are the design as proposed; **section 14 records what was decided
when it was built**, and wins where they differ. This page describes how
SpaceMissionStudio builds or updates a scenario's spacecraft from a model
made in IDM-CIC, the concurrent-engineering tool of CNES (IDM-CIC and IDM
View are © CNES). SpaceMissionStudio is not affiliated with, endorsed or
supported by CNES.

Scope, as agreed: the **import** only. The CIC ephemeris and attitude
**export** is left out until a description of the CIC file formats is
available (section 11).

## 1. Ground rules

- **Our own words, our own code.** Nothing from the CNES documentation is
  reproduced here or in the code: no copied text, tables, field
  descriptions or examples. Element and attribute names are used because
  the code has to read them. The importer reads the `.idm` file with our
  own code; it uses no CNES library, API or plug-in, and needs no CNES
  software installed.
- **No CNES files in the repository.** No specification, guide, sample
  model, picture, STEP file or plug-in data is committed. Test fixtures are
  small synthetic `.idm` files written by hand with made-up values, never
  derived from a CNES sample or a real project. `.gitignore` refuses `.idm`
  files anywhere but the fixtures folder (section 10). Before every commit
  the staged files are checked for anything from the reference material.
- **The licence has not been read.** The IDM-CIC licence text was not
  available for this design. Implementation should not start until it has
  been read and found compatible with this plan (section 12, question 1).
- **No guessing.** Where the specification is silent and the example
  models do not settle a question, the design says so and asks
  (section 12) rather than inventing a convention.
- **Offline and deterministic.** The same file gives the same scenario,
  byte for byte. Nothing is downloaded.

## 2. What the format holds (verified)

These findings come from the XML model specification, version 3.4.0.19,
and from 16 example models read in a scratch folder outside the
repository. They are summarised in our own words. "Confirmed" means both
the specification and the examples agree.

| Point | Finding |
|---|---|
| Container | A ZIP archive. The model is `model.xml` at the root: confirmed, present in every example. Optional folders hold embedded files (pictures, STEP models, scenario data files, textures) and third-party data (`managedData/`). Some archives name entries with `\` separators: normalise to `/`. The embedded-files folder is spelt with different capitalisation in places: match it case-insensitively. A file without `model.xml` is refused with a clear message. |
| Encoding | The specification says UTF-8 without a byte-order mark and no XML declaration; every example has a byte-order mark and Windows line endings. Read as UTF-8 and skip a BOM if present. |
| Versions | The examples carry model versions 3.4.1.1 and 3.5.0.32; the specification describes 3.4.0.19. A 3.5 example uses a shape type (`FilledBox`) the 3.4 specification does not describe. The importer targets 3.4.x and warns on other versions. |
| Identity | Every object written in full carries a `fullId`, a path of `alias.id` segments joined by `_`; the system's own `fullId` is empty. Elsewhere the object appears as an empty element of its type with a `ref` attribute holding that `fullId`. In every example all references resolve and no `fullId` repeats. The XML element name, not the alias, gives the type (some aliases are shared). References are resolved in a second pass. `fullId` is the key for re-import, never names. |
| Structure | The system holds elements (e.g. a platform, an instrument). Each element relates to subsystems, which hold unit definitions (`Equipment`, `Assembly`) and their placed copies. A placed copy made by the user is an *instance* (`EquipmentInstance`, `AssemblyInstance`) with its own position; the copies an assembly instance generates of its contents are *occurrences* (`EquipmentOccurrence`, `AssemblyOccurrence`) without a position of their own, placed through the chain back to the instance they copy. Assemblies nest. Tanks and thrusters are **not** unit types: a tank is an equipment with a `Tank` shape, and the model itself has no thruster data (row "Thrusters"). |
| Mounting | An element is mounted on another when the root coordinate system of the first has a parent coordinate system in the second; chains of three elements occur. Instances can also hang from a coordinate system of another element. |
| Positions | A position is a translation (m), three rotation angles (deg), the order of the rotation axes (12 orders, including repeated-axis orders) and whether the translation or the rotation comes first. All examples use translation first; they use five of the rotation orders. **Whether the rotations are about fixed or moving axes, and in which sense, is not stated anywhere** (section 12, question 2). |
| Articulations | A coordinate system can carry a rotation or translation articulation about one of its axes, with a default value, limits and a value per configuration. (Trajectory articulations exist in the specification but in no example.) Where the articulation applies relative to the coordinate system's own position is not stated (question 2). |
| Numbers | Decimal comma, optional exponent (`1,2E-05`), no thousands separator; booleans `True`/`False`; colours `RGB(r,g,b)`; dates day/month/year with time, no time zone. Some third-party files use a decimal point. Parsing is explicit and never locale-dependent. |
| Units | Lengths m, angles deg, masses kg, area density kg/m², volume density kg/m³, inertia kg·m², margins and filling levels as fractions. Power and temperature have no stated unit (the examples read as W and °C). |
| Formulas | Formulas are stored separately from the values they drive; the driven value is stored. The importer reads stored values and ignores formulas. |
| Mass properties | Per equipment, either manual (mass, centre of gravity and inertia typed in) or from geometry (each shape has a mass: total, per area or per volume). **IDM-CIC's computed results are not stored**: no system, element or equipment total. In the examples, the manual centre of gravity and inertia are zero on every equipment, and the stored manual mass of a geometry-based equipment matches the sum of its shape masses in most cases (a cache, sometimes stale). The point the manual inertia is taken about, and its sign convention for products, are not stated (question 3). |
| Margins | Equipment margins tied to maturity levels (5 to 20 %), element margins, a system propellant margin, and forced subsystem masses. How IDM-CIC stacks them is not stated. |
| Tanks | A `Tank` shape is a cylinder closed by hemispheres: radius, straight length, wall thickness, propellant capacity (kg) and maximum filling. Each placed tank has a filling fraction in the reference configuration and one per saved configuration. No propellant type or density is stored. |
| Thrusters | Nothing in `model.xml`. Three examples carry a separate `managedData/propulsion.xml` with thrust and specific impulse per thruster mode, linked to equipment occurrences. That file is third-party data **not described by the specification**; its format is known only from the examples, and one example's copy is an older, inconsistent layout (question 5). No thrust direction is stored anywhere. |
| Shapes | Wires (lines, arcs), surfaces (rectangles, discs, cylinders, cones, spheres, paraboloids, pipes...), solids (boxes, filled and hollow cylinders, cones, spheres, tori, paraboloids, extruded triangles and quadrangles, extruded paths), tanks, labels, Boolean operations (union, difference, intersection, section planes) and embedded STEP or Collada models. The local origin and axis of each primitive are only partly described in the text available (question 4). |
| Configurations | A configuration enables elements and optional units and sets tank fillings, articulation values and variable values. The reference configuration is not stored: it is the set of default values. |
| Modes and power | Equipment power modes (power and dissipation), element modes, system modes with duty cycles, and per-instance mappings between them. |
| Surfaces | Materials are visual only (colour, specular reflection, emission, textures). **No thermo-optical or aerodynamic property** exists in the format or the examples. |
| User data | User-defined properties per object type, free properties per object, variables and categories. None of the examples carries surface, aerodynamic or propulsion data in them. |
| Scenarios | A scenario can name trajectory and attitude data files stored in the archive; one example does. Out of scope (section 11). |

## 3. Where the data lands in SpaceMissionStudio

SpaceMissionStudio's spacecraft already has a 3D model
(`SpacecraftModelConfig`): parts in the body frame with a mass each,
mounted equipment, a stowed configuration, materials and a mass budget.
The model is *applied* to the spacecraft's own fields (`dry_mass_kg`,
`center_of_mass_b_m`, `inertia_kg_m2`, `facets`), which drive Basilisk.
The importer therefore builds a **3D model** and lets the existing apply
step write the spacecraft fields; it does not write those fields itself.

| IDM-CIC | Scenario field | Basilisk use | Conversion and notes |
|---|---|---|---|
| Shape on an equipment instance or occurrence (a supported primitive, section 4) | `model.parts[]` with `shape`, `dimensions_m`, `position_b_m`, `rotation_deg`, `mass_kg`, `distribution` | hub mass, centre of mass and inertia (`spacecraft.Spacecraft`) through `model3d.apply` | Pose composed through the whole chain into the body frame (section 4); rotation matrix converted to the model's roll-pitch-yaw (3-2-1) angles; mass from the shape's mass definition; solids `solid`, surfaces `shell` |
| Shape that is not a supported primitive | `model.parts[]` as a generated mesh (section 4), or a point mass with a warning | as above | Never silently dropped |
| Equipment with manual mass properties | `model.equipment[]` of kind `unit` with `mass_kg` at the transformed centre of gravity | hub mass properties | A manual inertia (zero in every example) is reported, not applied, until question 3 is answered |
| `Tank` shape and its filling | tank wall as a part; propellant into `fuel_tank` (`propellant_mass_kg`, `max_propellant_mass_kg`, `tank_position_b_m`) | `fuelTank.FuelTank` | Propellant = filling × capacity. The scenario's tank is a point mass today (no geometry), so the propellant's own inertia is lost: gap, see section 7 |
| Thruster equipment | `actuators[]` of kind `thruster`: `r_B`, `tHat_B`, `MaxThrust`, `steadyIsp` | `thrusterDynamicEffector` | Position from the instance; direction and performance open (section 7, question 5) |
| Configuration chosen at import | the deployed poses (`parts[].position_b_m`, `rotation_deg`) | as above | Articulation values of that configuration applied |
| A second configuration (e.g. launch) | `model.stowed[]` poses for the parts whose pose differs | launcher envelope check, stowed mass properties | Optional |
| Equipment maturity margin | reported in the import summary | none | The scenario's margin policy (AIAA S-120-2006) uses other categories: not mapped silently (question 6) |
| Element and equipment names, subsystem | part and equipment names, `subsystem` | none | Names are labels; `fullId` is the key |
| Visual material colour | `parts[].color` | Vizard | Visual only |
| Power modes | none | none | No operating-mode concept in the scenario (section 8) |
| Surface coefficients | none in the source | `facetDragDynamicEffector`, `facetSRPDynamicEffector` | Supplied by the user (section 6) |

Gaps on the SpaceMissionStudio side: no tank geometry, no power modes, no
per-part identity for re-import, an import record that knows only orbits.
Gaps on the IDM-CIC side: no surface coefficients, no thruster direction
or performance in the model, no stored mass totals to check against.

## 4. Frames and mass properties

**Composition.** For every equipment instance or occurrence, its pose in
the body frame is the product of the poses along its chain: shape in
equipment, equipment in its parent coordinate system, each coordinate
system in its parent (with its articulation value for the configuration),
up through assemblies and mounted elements to the body frame. Occurrences
take the position of the instance they copy, re-hung in the assembly
instance's copied coordinate systems. The composition is done once, in
the mapping layer, as 4 × 4 homogeneous transforms in double precision.

**Body frame.** The body frame is the root coordinate system of one
element, chosen at import (`--body-element`); by default the element the
others are mounted on. An element that is not part of the spacecraft (a
fairing, an "orbit" element holding the Earth and Sun used for
visualisation in one example) is left out, with a note. Elements disabled
in the chosen configuration are left out.

**Who computes the mass properties.** IDM-CIC does not store its computed
values, so the importer computes them from the shapes, and the existing
3D-model code combines them (parallel-axis theorem about the combined
centre of mass, `model3d.mass_properties.combine`):

- **Supported directly** (the scenario's own shapes, exact mass
  properties): box, full filled cylinder, full filled cone with a point
  (top radius zero), filled sphere, rectangle and thin plate (as a panel
  shell).
- **Supported by a generated mesh** (closed triangle mesh written by our
  code from the shape's parameters, mass properties by the existing exact
  mesh integrals): hollow cylinders, truncated and hollow cones, hollow
  spheres, partial revolutions, extruded triangles and quadrangles, tanks
  (wall and propellant separately), tori, paraboloids. Meshes are written
  as `.obj` files beside the scenario, like an imported `.obj` today, with
  their SHA-256.
- **Not supported**: Boolean operations, section planes, STEP and Collada
  models, labels, wires (zero mass in the examples), pipes along paths.
  Their mass (from the mass definition, which is known regardless of the
  geometry) is placed as a point mass at the shape's origin, and the part
  is listed in the import summary as an approximation with the reason. No
  shape is dropped without a word.

A shape with an area density gets its mass from its area; one with a
volume density from its volume; both computed by our code. The stored
"manual mass" cache of a geometry-based equipment is compared with the sum
of its shape masses and a difference is reported, since IDM-CIC itself
may hold a stale value.

**Margins.** The scenario receives nominal masses (no margins). The
margins found are listed in the summary and kept with the import record,
so a later mass budget can use them (question 6).

## 5. Configurations and articulations

- **Default:** the reference configuration (all default values: default
  articulation angles, default fillings, default optional-unit state).
- `--configuration <id>` picks a saved configuration instead.
- `--stowed-configuration <id>` (optional) imports a second configuration
  as the scenario's stowed poses: every part whose body-frame pose differs
  gets a `model.stowed` entry. This is how a launch configuration with
  folded arrays becomes the stowed configuration the launcher check uses.
- Tank fillings come from the configuration that sets the deployed poses.
- A configuration's articulation values override the defaults; a value
  set on a specific occurrence overrides its definition's.

## 6. Facets and surface coefficients

The source has no surface coefficients, and the rule is: never a silent
default. So the importer:

- builds the parts with `in_surface_model` on for solids and surfaces;
- sets `model.apply_facets` **off** on first import, so drag and solar
  pressure keep the spacecraft's existing (cannonball or facet) model;
- lists in the summary that surface coefficients are needed, and where to
  give them: per part or per face in the 3D model editor (part form,
  Per face), or per material (`model.materials` with a source, mapped by
  IDM-CIC visual material name if the user wishes, question 7);
- refuses to turn facets on (`--apply-facets`) while a surface part still
  has no coefficients of the user's.

The scenario caps a model at 200 facets; a detailed model can exceed it.
The summary then says so and suggests which parts to leave out of the
surface model (the largest areas are kept by default only if the user
asks, question 7).

## 7. Propulsion

- **Tanks.** Propellant mass and position as above. The scenario's tank
  is a point mass today: Basilisk's tank models can take a geometry, but
  the scenario does not carry one. Proposed schema addition (optional,
  written only when set): `fuel_tank.geometry` with the tank's radius and
  straight length, so the propellant's inertia is right (question 8). The
  wall is a part like any other.
- **Thrusters.** Position from the placed thruster equipment. Direction:
  not stored; IDM-CIC models a nozzle as a cone shape, so the direction
  could be taken along that cone's axis, but this is an inference
  (question 5). Performance: from `managedData/propulsion.xml` only if
  you decide that reading this undocumented third-party file is
  acceptable and its format is confirmed (question 5); otherwise
  placeholders (`MaxThrust` and `steadyIsp` marked as placeholders with a
  pre-run warning), never silent values.

## 8. Power modes

The scenario has no operating modes: one constant bus load, plus a
communications load while pointing at a station and a transmitter load
while sending. Mapping IDM-CIC's modes would need a new scenario concept
(modes and a mode timeline). Proposed: not imported now; the summary
lists the modes, their equipment powers and dissipations, and the total
per mode, so the user can choose a bus load. A modes feature is a
separate design (question 9).

*Since then (section 16):* still no modes in the scenario, but the user
can set the constant bus load from one system mode's total or the
duty-cycle average, and the panel area and normal from the solar arrays.

## 9. Provenance and re-import

**Provenance.** Each import writes an `ImportRecord` (existing machinery):
`target` `"model"`, `format` `"idm_cic"`, the file's absolute path and
SHA-256, the model version and last-modification date it declares, the
configuration(s) used, and the values written (`{field path: value}`).
Each imported part and equipment item carries the `fullId` of its source
(instance or occurrence plus shape) in a new optional field (section 10).
The import is saved through the change history with its source
(`spacemissionstudio import idm`), and pre-run checks already warn when
the source file has changed or gone.

**Re-import** (same spacecraft, same or newer `.idm`):

1. Match parts and equipment by `fullId`, never by name.
2. For each field the previous import wrote: if its current value still
   equals the imported one, update it; if the user edited it, keep the
   edit and report it.
3. New source objects are added. Objects gone from the source are
   **flagged, not deleted**: kept, listed in the summary, and a pre-run
   warning names them until the user removes them.
4. A summary lists added, updated, kept-as-edited, gone and unmapped
   objects, and exits non-zero only on a parse error.

Values the user typed that were never imported are never touched.

## 10. Structure and schema

**Parser** (`spacemissionstudio/idm/`, no scenario knowledge):

- `archive.py`: open the ZIP, find `model.xml` and other entries with
  normalised separators, read UTF-8 with or without a BOM, size limits.
- `values.py`: comma decimals, exponents, booleans, colours, dates, enums.
- `graph.py`: one pass to index every object by `fullId`, a second to
  resolve references; refuses duplicates and dangling references.
- `model.py`: typed dataclasses (system, element, subsystem, equipment,
  assembly, instance, occurrence, coordinate system, articulation, shape,
  tank, configuration, power mode) with SI units, built from the graph.
- `frames.py`: positions to transforms, per rotation order and
  transformation order, and the chain composition.
- `shapes.py`: our parameterisation of the primitives, their mass
  properties and meshes.

**Mapping** (`spacemissionstudio/idm_import.py`): turns the typed model
into a `SpacecraftModelConfig`, a fuel tank, thrusters and an import
record, and merges into an existing scenario (section 9). It returns a
summary object the CLI and GUI both print.

**CLI:** `spacemissionstudio idm-import FILE.idm SCENARIO --spacecraft
NAME [--configuration ID] [--stowed-configuration ID] [--body-element ID]
[--apply-facets] [--out]`, following `ccsds-import`, plus
`spacemissionstudio idm-info FILE.idm` to list elements, configurations
and unsupported shapes without writing anything. **GUI:** an *Import
IDM-CIC model...* entry beside *Import .obj...* in the 3D model editor,
with a preview of the summary before applying, run off the GUI thread.

**Schema additions** (all optional, written only when set, so existing
scenarios save and hash as before; no schema-version bump):

- `ImportRecord`: target `"model"`, format `"idm_cic"`.
- `ModelPartConfig.source_id` and `MountedEquipmentConfig.source_id`: the
  source object's `fullId`.
- `fuel_tank.geometry` (question 8).

**Repository hygiene:** `.gitignore` refuses `*.idm` (any case) except
under `SpaceMissionStudio/tests/data/idm/`, which will hold only the
hand-written synthetic fixtures.

## 11. Out of scope

- The CIC ephemeris and attitude export (no format description at hand).
- Importing the trajectory and attitude files embedded in IDM-CIC
  scenarios, and SIMU-CIC mission scenarios (follow-ups).
- Writing back into `.idm` files, running as an IDM-CIC plug-in.

## 12. Risks and open questions

1. **Licence.** The IDM-CIC licence has not been read. Please provide it
   before implementation starts; if it restricts reading or converting
   models, the plan changes.
2. **Rotation convention.** Whether the three rotations are about fixed or
   moving axes, their sense, and where an articulation applies are not
   stated, and the examples cannot settle it without IDM-CIC's own
   numbers. Proposed check: you build one small model in IDM-CIC (a box
   offset and turned by two different angles, a hinged panel) and send its
   mass, centre of gravity and inertia report; the importer's convention
   is fixed by matching it, and the synthetic fixtures encode the result.
3. **Manual inertia.** About which point, in which frame, and with which
   sign for the products? Every example has zero manual inertia, so this
   is untested; until answered, a non-zero manual inertia is reported and
   not applied.
4. **Primitive origins.** The figures that show each shape's origin and
   axes were not in the text available. The same small IDM-CIC model
   (with a cylinder, a cone and an extruded triangle) would fix them.
5. **Thrusters.** Is reading `managedData/propulsion.xml` acceptable
   (third-party data, undocumented, inferred from examples)? And should
   the thrust direction follow the nozzle cone's axis?
6. **Margins.** Map IDM-CIC maturity levels into the scenario's mass
   budget (a new margin policy for IDM-CIC's levels), or only report them?
7. **Surfaces.** Map coefficients by IDM-CIC visual material name? Choose
   facet parts automatically when the 200-facet cap is exceeded?
8. **Tank geometry.** Add the optional `fuel_tank.geometry` to the
   scenario (a schema addition), or keep the point-mass tank?
9. **Power modes.** Report only (proposed), or design a modes feature?
10. **Validation data.** No example stores IDM-CIC's totals. "Within
    stated tolerances" needs IDM-CIC's mass, centre-of-gravity and inertia
    report for at least one model with real masses, per configuration.
11. **Versions.** The examples are newer than the specification (3.4.1.1,
    3.5.0.32), and 3.5 adds at least one shape type. Is 3.4 the version to
    support?

Risks: models far larger than the examples (thousands of occurrences;
the parser streams nothing, so memory is the limit, set at a file-size
cap); Boolean-heavy library models, whose mass properties stay
approximate; and the facet cap.

## 13. Phases after approval

1. Parser and typed model, with the synthetic fixtures (comma decimals and
   exponents, nested assemblies, an element on an element, every rotation
   and transformation order, manual and geometric mass properties, tanks
   filled differently per configuration, an articulated part, a thruster
   with and without propulsion data, a missing `model.xml`).
2. Mapping: mass properties, then propulsion, then geometry and facets,
   each with hand-calculated checks.
3. Re-import and the summary.
4. CLI, GUI entry, user-manual page (crediting CNES, the supported version
   and what is not imported), capabilities, limitations, changelog.

## 14. Decisions taken when building it

The questions of section 12 were settled as follows, without input from
CNES or from IDM-CIC itself (no CNES software was run). Each is a
decision of this project, reversible when better information comes.

| # | Decision | Why |
|---|---|---|
| IDM-01 | **Rotations**: `R = R1 R2 R3` about the axes the order names, each about the axes already turned (intrinsic), right-handed, active. `Translation_Rotation`: `x_parent = t + R x`; `Rotation_Translation`: `x_parent = R (t + x)`. | Fixed against the example models: truss members, panels and hinge frames only meet their neighbours under this reading. Encoded in the synthetic fixture (`tests/test_idm_import.py`'s two pointers). |
| IDM-02 | **Articulations** turn or move a coordinate system about or along its own axis after its position: `frame = parent @ position @ articulation`. A copy's own value for the configuration wins over its origin's, then over the definition's default. | Hinged panels in the examples swing about their edge only this way. |
| IDM-03 | **Shape origins**: box, extruded triangle and quadrangle, rectangle: a corner, `d1` along +x, width along +y, thickness along +z. Revolution shapes and the tank: axis +z, base at the origin, height `d3` (negative: along -z). Spheres and tori centred. Hollow thicknesses inward. The tank: cylinder from 0 to `d3`, hemispheres beyond. | Box and cylinder origins fixed against the examples; the others assumed and reported as such ("corner convention assumed"). |
| IDM-04 | **Physical units** are the element's unit instances and the occurrences inside assembly instances; the templates inside an assembly's definition never count. | Counting both doubles every assembly's mass. |
| IDM-05 | **Body frame**: the root coordinate system of one element; by default the heaviest element (with what it carries) that is not mounted on another enabled element, stepping down to its heaviest child while it has no mass of its own (an "orbit" element). The elements whose mounting chain reaches it are imported; the others are left out with the reason. | The examples' spacecraft hang on an orbit element or carry a fairing; neither belongs in the spacecraft's mass. |
| IDM-06 | **Manual inertia** is reported, not applied (question 3). | Its reference point and axes are not stated; every example has zero. |
| IDM-07 | **Margins and maturity levels** are reported only (question 6); the model gets nominal masses and the parts no maturity category. | The scenario's margin policy (AIAA S-120-2006) uses other categories; mapping them silently would invent data. |
| IDM-08 | **Tanks**: the wall is a mesh part; the propellant (filling x capacity, of the chosen configuration) a hidden solid part filling the wall's cavity, so it counts in the mass properties with its own inertia. No `fuel_tank` is written and no `fuel_tank.geometry` added (question 8). | The scenario's fuel tank needs a thruster and is a point mass; the 3D model already carries geometry and inertia. |
| IDM-09 | **Thrusters and `managedData/propulsion.xml`** are not read (question 5). | The file is undocumented; reading it would mean inferring a third party's format. |
| IDM-10 | **Power modes** were not imported or reported (question 9). Superseded by IDM-24: they are reported, and one system mode's total (or the duty-cycle average) can be the bus load. | No operating-mode concept in the scenario. |
| IDM-11 | **Facets** are off: imported parts are left out of the surface model unless `--apply-facets` (or the dialog's box) puts the boxes, cylinders, cones and spheres in, with the default coefficients (question 7). | The file has no surface coefficients; meshes would exceed the facet cap. |
| IDM-12 | **Unsupported shapes** (STEP, Collada, pipes, labels, paths, intersections and section planes) become point masses at the shape's origin (or the centroid of the Boolean bodies before the unsupported operation); wires without mass are dropped silently, with mass they are points. A shape whose every layer is hidden by default and that has no mass (a field of view, a keep-out zone) is left out; one with mass is kept, hidden. | Nothing is dropped without a word; visual aids are not structure. |
| IDM-13 | **Boolean operations**: union adds and difference subtracts, as a mesh with the removed body wound inward, so the volume integrals are exact when the bodies do not overlap or lie inside. | The examples' Booleans are panels with holes and stiffeners. |
| IDM-14 | **Meshes**: one `.obj` per spacecraft, `models/<spacecraft>_idm.obj` beside the scenario, one group per shape definition; full revolutions scale their radii so each circle's polygon keeps the circle's area (cylinders and cones exact in volume; spheres and tori within 0.3 %). | Exact where cheap, bounded elsewhere. |
| IDM-15 | **Versions** 3.4 and 3.5 are read; any other is read with a note (question 11). `FilledBox` (3.5) is read as a box. | The examples are 3.4.1.1 and 3.5.0.32. |
| IDM-16 | **Re-import** compares groups of values (geometry; mass and distribution; position; rotation; stowed pose; a point mass's mass; its position) with what the last import wrote: equal, the new values are taken; edited since, kept and reported. Items whose `fullId` is gone are kept and flagged (`import.source_item_gone`); the meshes they use are kept in the rewritten `.obj`. | Never overwrite an edit, never delete. |
| IDM-17 | **XML safety**: `ElementTree` with any document type or entity declaration refused before parsing (Python's expat also bounds entity expansion); the file and `model.xml` sizes are capped. `defusedxml` is not a dependency. | A model never declares a DTD; refusing one removes the entity attacks. |
| IDM-18 | **The licence** of IDM-CIC was not available to read (question 1). The reader uses the format's published description only for element names and meanings; no CNES text, file or example is in the repository; the test fixtures are written by hand. Listed in the known limitations. | The brief's rules. |

| IDM-19 | **Devices are found by name** (`idm_devices`, section 15): an equipment's name, in English or French with accents ignored, names a device kind; a part of a device (electronics, support, mechanism, a thermal cone) and the structure, thermal and harness subsystems name none. | The file has no device type: only the names say what an equipment is. The rules were checked against the names of the sample models (not committed). |
| IDM-20 | **A device's axis** is an axis of its equipment frame, +z unless the user chooses another. | IDM-03 builds revolution shapes along +z; in the samples, the wheels' +z axes form a pyramid and the magnetorquers' lie along the three body axes. The file has no boresight. |
| IDM-21 | **Values come from a catalog product or from Basilisk's defaults, never from an estimate.** A sensor without a product runs with the defaults, and `import.device_defaults` says so until its values are set; wheels and magnetorquers are added only with a product (Basilisk builds neither without values the file does not give); thrusters, solar arrays and batteries are listed, not added. | The file states no performance; the user asked for nothing to be invented. |
| IDM-22 | **A device the spacecraft cannot take as it is** (its own validation fails with it, e.g. a magnetorquer without magnetic momentum management) is left out, with the validator's reason. | Adding it would make the scenario invalid, and the import is refused whole. |
| IDM-24 | **The bus load from the power modes** (section 16): a system mode's total is the power of the imported units in it, through the element mode of the unit's element the system mode links, else the unit's own system-mode mapping; a mapping's power mode's power, or its custom power. A unit with power modes that no mapping covers counts 0 W and is counted in the record. The duty-cycle average only when the duty cycles add up to one (within 1e-6). Watts. The user chooses the mode; nothing is set by default. | The format describes both mappings and says an element linked through an element mode has no direct ones; the description gives no unit, and the samples' values (a wheel about 10, a magnetometer about 1) are watts. The scenario has one constant load, so which mode matters is the user's call. |
| IDM-25 | **The panel from the solar arrays** (section 16): for each solar array unit, its largest flat shape (a box whose thinnest side is at most a tenth of the next, or a plane surface), the others taken as its layers; the panels grouped by normal line (within 1 deg, either sense), the largest group's area and line; the side carrying the cells chosen by the user. | The power model takes one panel area and one normal; the file does not say which side carries the cells. In the samples a panel is a thin box with cover layers of the same outline. |
| IDM-26 | **A power budget made by the import** (the spacecraft had none, the panels chosen) takes the spacecraft editor's panel efficiency and battery, recorded, and `import.power_defaults` warns until they are set. A bus load alone does not make one. | A new budget needs an efficiency and a battery the file does not give; the editor's values are the ones a user would start from, and the warning keeps them from passing for the spacecraft's. |
| IDM-23 | **Re-import of devices** adds only the units no earlier import added a device for (the record names each device's unit); devices already added are left as they are. | A device's values are the user's once added; the record keeps what was imported for comparison. |

Validation (question 10) remains open: no example stores IDM-CIC's own
totals, so the importer's mass properties are checked against hand
calculations on the synthetic fixture, not against IDM-CIC. A model's
mass, centre-of-gravity and inertia report from IDM-CIC would close it.

## 15. Devices found by name

Added after the user asked whether the import could find the sensors,
actuators and power equipment of a model, so that they need not be
typed in again. `spacemissionstudio/idm_devices.py`:

- `classify(name, subsystem)`: the device kind a name names (decision
  IDM-19), first rule first: star tracker, magnetorquer, magnetometer,
  sun sensor, gyro or IMU, reaction wheel, thruster, solar array, battery.
- `detect(model, placement, body)`: each placed unit of the elements
  carried by the body element whose name names a device, with its mass,
  its position (the unit's origin, or its manual centre of gravity) and
  its axes in the body frame, and the catalog product its name names
  (`catalog_product`: the product name as whole words, with one word
  that is not generic).
- `default_choices`, `build_devices`: the sensors and actuators to add,
  each axis parameter (`nHat_B`, `gsHat_B`, `gtHat_B`) and mount from the
  chosen axis (IDM-20), the product's values or none (IDM-21).
- `keep_fitting`: each device tried against the spacecraft's own
  validation (IDM-22).
- `unset_devices`: the devices still on Basilisk's defaults, for the
  `import.device_defaults` pre-run warning.

`idm_import.plan` lists the devices found (`Plan.devices`, the summary),
and `idm_import.add_devices` adds those chosen and records them as an
import of target `devices` (re-import: IDM-23). In the GUI the import
dialog's **Devices found** table makes the choices; the 3D model editor
keeps them, and the spacecraft list or the spacecraft dialog adds the
devices on the editor's OK, since only they hold the whole spacecraft.
On the command line, `idm-import --devices` takes the default choices.

A property mapping for performance values the team keeps in the model's
own properties (wheels and batteries without a catalog product) is the
next step.

## 16. Power from the model

Added with section 15, for the power equipment. `spacemissionstudio/idm/power.py`
reads, without changing the model:

- `system_modes(model)`: each `SystemMode` definition, its name and
  duty cycle (a fraction, as the format describes it).
- `mode_powers(model, units)`: for each system mode, the power of each
  placed unit (decision IDM-24): its `ElementToEquipmentPowerMode`
  whose `elementMode` the system mode links (from the system mode's
  `elementModes` or the element mode's `systemModes`), else its
  `SystemToEquipmentPowerMode` for that system mode; the mapping's
  `powerMode` power, or its `customPower`. A unit whose equipment has
  power modes and that no mapping covers is listed as not stated.
- `duty_cycle_average(powers)`: the weighted mean, or None when the duty
  cycles do not add up to one.
- `panels(placement, body_frame, units)` and `panel_groups(panels)`:
  the flat faces of the solar array units and their groups by normal
  line (IDM-25).

`idm_import.plan` puts these in `Plan.power` (a `PowerPlan`) and the
summary. `idm_import.apply_power(scenario, spacecraft, plan, choice)`
sets what a `PowerChoice` names (the bus load's mode or "average", the
panels, the normal's sign) in the spacecraft's `PowerConfig`, making one
when needed (IDM-26), and records it as an import of target `power`
(`schema.scenario.power_import_values`: each `power.<field>`, a list by
index). `unset_power` finds the budgets still on the editor's values,
for `import.power_defaults`. In the GUI the import dialog's **Power**
section makes the choice; the 3D model editor keeps it
(`power_import()`), and the spacecraft list or the spacecraft dialog
applies it on the editor's OK, as for the devices. On the command line,
`idm-import --bus-load MODE|average --solar-panels +|-`. The choice is
checked against the plan (`power_values`) before the model is merged, so
a mode the file does not have stops the import before anything is
written.
