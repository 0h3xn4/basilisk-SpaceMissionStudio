# Import a spacecraft from IDM-CIC

How to build a spacecraft's [3D model](3d-model.md), with its mass,
centre of mass and inertia, from a concurrent-engineering model made in
IDM-CIC, and how to bring later versions of that model in without losing
your own changes.

> SpaceMissionStudio reads IDM-CIC models (IDM-CIC is © CNES) with its
> own reader, written from the format's published description. It does
> not use, include or download any CNES software, and it is not
> affiliated with or endorsed by CNES. It only reads `.idm` files: it
> never writes them.

## What is imported

An IDM-CIC model (`.idm`) holds a system made of **elements** (a bus, a
payload module, an adapter), each with equipment placed in coordinate
systems, saved **configurations** (launch, operations...) and, for each
piece of equipment, its shapes and mass. The import builds the
spacecraft's 3D model from one configuration:

| In the IDM-CIC model | In the 3D model |
|---|---|
| A shape of an equipment (box, cylinder, cone, sphere, revolution solids and surfaces, extruded triangles and quadrangles, a tank, Boolean unions and differences) | A part, placed in the body frame, with the shape's mass (total, or per square or cubic metre times the area or volume) |
| An equipment whose mass is typed in rather than computed from its shapes | A point mass at its centre of gravity (the shapes come as massless parts, to see them) |
| A tank and its filling in the configuration | The tank wall as a part, and its propellant (filling x capacity) as a hidden solid part inside it |
| The articulations (hinges, slides) and optional equipment of the configuration | The parts where that configuration puts them; optional equipment only when the configuration enables it |
| A second configuration, for example the launch one | The stowed poses of the parts that are elsewhere in it, used by the launcher check |
| Mass margins and maturity levels | Listed in the import summary, not applied: the model gets nominal masses |

The **body frame** is the frame of one element, which you choose; by
default the heaviest element that the others hang on. The elements
mounted on it, directly or through others, come with it; an element that
is not mounted on it (a ground jig, an "orbit" element that only shows
the spacecraft) is left out, and the summary says why.

Sensors and actuators can be added too, from their names: see
[Devices found in the model](#devices-found-in-the-model). The power
budget's bus load and solar panel can be set from the model's power
modes and solar arrays: see
[Power from the model](#power-from-the-model).

Not imported: the performance of thrusters, batteries and solar cells,
the dissipation of the power modes, thermal data, scenarios (trajectories and attitudes), the
pictures and documents attached to the model, and surface coefficients
(the file has none: facets stay off unless you ask for them, with the
default coefficients). Shapes on layers that IDM-CIC hides by default and
that carry no mass (fields of view, keep-out zones) are left out.

## Import a model

In the 3D model editor (**Scenario › 3D Model...**), choose
**Import IDM-CIC model...**, pick the `.idm` file, and choose:

- **Configuration**: the one to import, or **Default values** (each
  articulation, filling and optional equipment at its default);
- **Stowed configuration** (optional): a second configuration whose poses
  become the stowed configuration;
- **Body element**: the element whose frame is the body frame;
- whether to build drag and solar pressure facets from the imported
  boxes, cylinders, cones and spheres;
- **Origin of the body frame** (see [The origin of the body
  frame](#the-origin-of-the-body-frame)).

![The import dialog: the model file, the configuration, the stowed configuration and the body element, and below what the import will do](../images/idm_import.png)

The dialog shows what the import will do before you apply it: the
elements imported and left out, the number of parts and point masses,
the mass, and every approximation. The scenario must be saved as your
own file first (not a built-in template, whose folder is not yours to
write to): the shapes that are not one of the model's own primitives are
written as meshes to `models/<spacecraft>_idm.obj` beside the scenario
file. If you started from a template, use **File › Save As** in the main
window (the editor can stay open) and import again.

From the command line:

```console
$ spacemissionstudio idm-info demosat.idm
$ spacemissionstudio idm-import demosat.idm scenario.json --spacecraft sat-1 \
      --configuration OPS --stowed-configuration LCH
```

`idm-info` lists the elements, configurations and approximations
without writing anything; `idm-import` writes the model, saves the
scenario through the change history and prints the same summary as the
dialog. Both accept `--body-element`; `idm-import` also `--apply-facets`,
`--origin element|cog` and `--out`.

## The origin of the body frame

By default the body frame's origin is the body element's own origin, as
in IDM-CIC: every position (parts, sensors, actuators, panels) reads as
it does there. The centre of gravity is then usually elsewhere, and the
import summary says where ("the centre of gravity is [0.35, -0.013,
-0.006] m from it"). The simulation is right either way: it takes the
centre of gravity from the origin (**Center of mass** on the spacecraft's
Mass page), so drag, solar pressure and thrust push about the true
centre of gravity.

Choose **The centre of gravity** to put the origin there instead. The
import computes the centre of gravity of the model as imported
(propellant included, as the configuration fills the tanks), to the
micrometre, and moves **every** position of the spacecraft with the
origin, so that they stay where they are on the spacecraft: the model's
parts, point masses, stowed poses and launcher plane, and the sensors,
actuators, thrusters, wheels, RF antenna, facets, fuel tank, solar array
hinges and the Vizard model's offset, including those you entered by
hand. A position given in a part's own frame moves with the part. The
centre of mass is then zero, and the summary lists what moved and by
how much.

The choice is kept: the next import of the model (a newer version, say)
puts the origin at the centre of gravity again, wherever that now is,
and moves everything by the difference. Choose **The body element's
frame** again to put everything back where IDM-CIC has it.

## Devices found in the model

An IDM-CIC model says what each equipment is called, which subsystem it
belongs to, its mass and where it sits. It does not say how the
equipment performs. The import reads the names, in English or French
(accents ignored), and the dialog's **Devices found** tab lists each
equipment whose name names a device:

| Found | Names such as | Added? |
|---|---|---|
| Star tracker | Star tracker, Senseur stellaire | Yes (the head only, not its electronics) |
| Gyro / IMU | Gyro, IMU, Gyromètre | Yes |
| Sun sensor | Sun sensor, SAS, Senseur solaire | Yes |
| Magnetometer | Magnetometer, Magnétomètre | Yes |
| Reaction wheel | Reaction wheel, Inertia wheel, Roue | With a catalog product |
| Magnetorquer | Magnetorquer, Magneto torquer, Magnétocoupleur | With a catalog product |
| Thruster | Thruster, Propulseur | Listed only |
| Solar array | Solar panel, Panneau solaire | Listed only |
| Battery | Battery, Batterie | Listed only |

A part of a device (a star tracker's electronics, a wheel's support, a
solar array's mechanism) and the equipment of the structure, thermal and
harness subsystems are not devices.

For each device, the table offers:

- **Add**: whether the import adds it to the spacecraft's Sensors or
  Actuators, at its place in the model;
- **Axis**: the device's boresight, spin axis or dipole axis. The
  device is already turned as its equipment is placed in the model (a
  wheel of a pyramid keeps its tilt); the axis says which direction of
  the equipment is the one that matters. **from the model** is chosen
  when the equipment's shapes show it: a field-of-view cone gives a
  sensor's boresight (from its tip toward its wide end) and its field of
  view, drawn in the 3D view; a cylinder gives a wheel's spin axis or a
  magnetorquer's rod axis. The tooltip names the shape and gives the
  vector. When the shapes show none (a gyro drawn as a box), it is +z of
  the equipment's frame, the axis IDM-CIC builds cylinders and cones
  along. You can choose any axis of that frame instead;
- **Catalog product**: a product from SpaceMissionStudio's device catalog.
  If the equipment's name includes a product's name ("Star tracker head
  ST200"), that product is chosen for you. The device takes its published
  values.

Nothing is estimated. A star tracker, gyro, sun sensor or magnetometer
without a product runs with Basilisk's defaults for its kind, and the
pre-run checks say so for each one until you set its values, choose a
product or map a property that gives them (`import.device_defaults`). A
reaction wheel or magnetorquer is added only with a product, or with
properties that give its torque and inertia, or its dipole: Basilisk
cannot build one without them, and the file has no field for them (see
[Values from your team's properties](#values-from-your-teams-properties)).
Thrusters, solar arrays and batteries are listed but not added: a
thruster's direction and thrust are not in the file, and the Power page
takes one panel area and one battery for the whole spacecraft (the solar
arrays' panels and the batteries' capacity property can set them: see
[Power from the model](#power-from-the-model)).

A device the spacecraft cannot take as it is (a magnetorquer without
magnetic momentum management, for example) is not added, and the
message after OK says why. The devices are added when you click **OK**
in the 3D model editor. In an orbit-only scenario, which simulates no
sensors or actuators, they are listed but not added.

A newer version of the model adds the devices that are new in it; a
device an earlier import added is left as it is, edits included. The
scenario records each added device, its values, the product or
"Basilisk's defaults", and the IDM-CIC unit it came from.

From the command line, `idm-import --devices` adds the devices that the
dialog would add by default, and `idm-info` lists the devices found.

## Power from the model

In IDM-CIC, an equipment can have **power modes** (Off, On, Standby...,
each with a power), and the system has **system modes** (Survival,
Downlink...) that put each equipment in one of its power modes, through
an element mode or directly, or give it a custom power. Each system mode
has a duty cycle: the share of the lifetime spent in it.

The import adds up, for each system mode, the power of the imported
equipment in it, and shows the totals in the summary. The duty-cycle
average is shown too, when the duty cycles add up to one (otherwise part
of the lifetime is not placed, and no average is given). An equipment
with power modes that a system mode does not put in any is counted as
0 W there, and the import record says how many there were. Powers are in
watts.

The import dialog's **Power** tab sets, if you tick them:

- **Set the bus load from** a system mode (or the duty-cycle average):
  the power budget's constant bus load becomes that total. The power
  budget has one constant load, so choose the mode that matters for the
  run: the one it spends most time in, or the worst case;
- **Set the panel area and normal** from the solar arrays found by name:
  the area is the largest flat face of each panel (a thin box or a flat
  surface; the other flat shapes of the same panel are taken as its
  layers), added up for the panels along one normal line, and the
  normal is that line in the body frame. The file does not say which
  side carries the cells, so you choose it (+ or -). Panels along other
  lines are left out, and the summary says how many lines there were;
- **Set the battery capacity** from the batteries' capacity property,
  added up, once you have mapped it on the **Properties** tab (see
  [Values from your team's properties](#values-from-your-teams-properties)).

Nothing is set unless you tick it. If the spacecraft has no power
budget, setting the panels makes one, with the spacecraft editor's panel
efficiency and battery (the battery's capacity from the file when you
set it): the file does not give them, and the pre-run
checks say so until you set them on the Power page
(`import.power_defaults`). A bus load alone needs a power budget to put
it in. The values are set when you click **OK** in the 3D model editor;
an orbit-only scenario simulates no power budget, and nothing is set.

The scenario records what was set and how (the system mode and its
number of equipment, the panels and the side you chose), and **Scenario
› Overview** shows a value you have changed since, as for the other
imported values.

From the command line, `idm-import --bus-load MODE` (a system mode's
name, or `average`), `--solar-panels +` or `-` and `--battery` do the
same, and `idm-info` lists the system modes with their totals and the
panels.

## Values from your team's properties

A team often keeps performance values in its IDM-CIC model as
**properties** of the equipment, its own or from its templates: "Max
torque" on a reaction wheel, "Capacity" on a battery, "Field of view" on
a sun sensor. Their names are the team's, and their values mostly carry
no unit ("12" may be mN·m or N·m), so the import reads none of them on
its own. The import dialog's **Properties** tab lists each property name
found on the devices' equipment, with its type, the devices that carry
it and its values. For each one you want, choose:

- **Use as**: the value it gives, among those its devices take;
- **Unit**: the unit its values are in.

| Use as | Units |
|---|---|
| Reaction wheel: maximum torque | N·m, mN·m |
| Reaction wheel: inertia about the spin axis | kg·m², g·cm² |
| Reaction wheel: maximum speed | RPM, rad/s |
| Reaction wheel: maximum momentum | N·m·s, mN·m·s |
| Magnetorquer: maximum dipole | A·m² |
| Star tracker: attitude noise (1-sigma) | arcsec, deg, rad |
| Gyro / IMU: rate noise (1-sigma) | rad/s, deg/s, deg/h |
| Sun sensor: full field of view | deg, rad |
| Battery: capacity | W·h, kW·h |

A unit is offered only when the property's type has the value's
dimension (an angle for a field of view, in degrees, the format's own
unit for angles); a property typed as something else (a speed typed as a
distance happens) or untyped has none, and you choose.

A device then takes the mapped values, over its catalog product's when
one is chosen. A reaction wheel or magnetorquer that its properties give
every value it needs (torque and inertia, or torque, maximum speed and
momentum; a dipole) can be added without a product, and is ticked for
you. A wheel takes its inertia or its maximum momentum, not both: map
one, and it replaces the other a product gives. A property mapped but
empty on an equipment is noted in its row and gives nothing. The import
record says, for each device, which values came from which property, in
which unit.

The mapping is kept with the import, so a newer version of the model is
read the same way, and the dialog shows it next time.

From the command line, give each mapping as
`--property-map 'NAME=KIND.PARAM[UNIT]'`, for example
`--property-map 'Max torque=reaction_wheel.u_max[mN*m]'`. Without the
option, the mapping of the spacecraft's last import is used;
`--property-map none` drops it. `idm-info` lists the properties found and
the values they can give.

## What is approximated

Every approximation is listed in the summary, by reason, with the parts
it concerns:

- Boolean operations: a union adds a body and a difference removes one,
  which is exact when united bodies do not overlap and removed bodies
  lie inside the rest. Other operations (intersections, section planes)
  put the shape's mass at a point.
- STEP and Collada models, pipes, labels and paths have no geometry here:
  their mass becomes a point mass at the shape's origin.
- Lines and arcs (wires) are points; with no mass they are left out.
- Curved shapes are drawn as triangle meshes whose circles keep their
  true area, so cylinders and cones have their exact volume; spheres and
  tori are within about 0.3 %.
- A shape's rounded edges and stretch factor are not modelled.
- A typed-in inertia matrix is reported, not applied (its reference point
  and axes are not stated in the file).

The conventions the reader uses (rotation order, shape origins) are in
the [design note](../developer/idm-cic-integration.md). They were fixed
against example models; if a part sits somewhere you do not expect,
please report it with the shape type.

## Import a newer version

Import the newer file the same way, into the same spacecraft. Each
imported part and point mass remembers the identifier (the `fullId`) of
the object it came from, so the import matches them even if you renamed
them:

- a value the file set last time and you have not changed is updated;
- a value you changed since is kept, and the summary lists it as
  **kept as edited**;
- new objects are added;
- an object the file no longer has is **kept, not deleted**: the summary
  lists it, and **Scenario › Overview** warns about it
  (`import.source_item_gone`) until you remove it or keep it as your own;
- values you added yourself (materials, maturity, face properties) are
  never touched.

## Where the values came from

The scenario records the import: the file's path and SHA-256, the model
version, the configurations and body element used, and each imported
value under the object's identifier. **Scenario › Overview** warns when
the file has changed since (`import.source_changed`) or is no longer
there (`import.source_missing`), and each run's provenance lists it.

---

**Next:** [3D model](3d-model.md) ·
[How-to guides](README.md)
