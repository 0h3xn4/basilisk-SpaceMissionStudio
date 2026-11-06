# Analyses built on the 3D model

How to mount equipment on a spacecraft's 3D model, describe its stowed
configuration and materials, and use the checks and analyses built on it.
The methods and their sources are in
[docs/models/model-analyses.md](../models/model-analyses.md) and
[docs/models/reentry.md](../models/reentry.md); template 32 shows them all.

The fields named below are those of the scenario file. In the app, the
3D model editor edits all of them: its **Equipment**, **Stowed**,
**Materials** and **Budget and launcher** tabs and the part form (see
[3D model](3d-model.md#equipment-stowed-configuration-materials-and-the-analyses)).
An [IDM-CIC import](idm-cic.md) brings in the parts, the stowed poses
and, with **Devices found**, the sensors and actuators at their places.

## Mount the equipment

What the scenario already defines is reused: a thruster's `r_B` and
`tHat_B`, a coarse sun sensor's `nHat_B` and `fov_deg`, the RF antenna's
boresight and beamwidth. Give a definition a `mount` (or the RF link an
`antenna_mount`) to add what it lacks: the part it sits on, its position
and boresight in that part's frame, its field of view, its Sun, Earth and
Moon exclusion angles, a thruster's plume half-angle. A mount on a part
moves with it to the stowed configuration.

Equipment the scenario has no definition for (a payload camera, an orbit
thruster's nozzle, a solar-cell panel, a radiator, a unit with mass) goes
in the model's `equipment` list, with its kind, mount and, if it has one,
its mass, subsystem and maturity.

## Stowed configuration, materials and maturity

- `model.stowed` gives a part's position and rotation when stowed; the
  rest stay where they are. The stowed configuration has its own mass
  properties, used by the launcher check.
- A part's `material` names a library material (`config/materials.py`,
  each value with its NASA source) or one of the model's own
  `materials`. A `face_properties` entry sets one face's material or
  optical coefficients.
- A part's `maturity` (estimated, layout, pre-release design, released
  design, existing hardware, measured) and `subsystem` choose its AIAA
  S-120-2006 growth allowance.
- Renaming a part renames every reference to it (`rename_part`); a
  reference to a part that is not there is refused.

## Check the design (no run)

**Run › Design Checks**, Check: the obstruction of each field of view
(deployed and stowed), the thrusters' torque arms and authority at the
beginning and end of life, plume impingement, the mass budget, and the
stowed spacecraft against the launcher envelope (`model.launcher`). The
findings also show in the Problems panel while you edit. Save... writes
the record and the tables. On the command line:

```
spacemissionstudio check-design my_mission.json --out design.json --tables design_tables
```

## Analyses of a run

Tick what the spacecraft needs in its editor's **3D model** tab, group
**Model analyses** (`model_analyses` in the file): disturbance torques,
sensor blinding, antenna obstruction, array shading (and, optionally, its
effect in the power budget), surface exposure, brightness from the ground
stations and your own observer sites. They need `full_attitude` mode. After
the run, **Results › Model Analyses** gives the tables and the momentum and
sizing summary, **Results › Plots** the series (`<sc>.disturbance.*`,
`<sc>.blinding.*`, `<sc>.shading.*`, `<sc>.exposure.*`,
`<site>.brightness_of_<sc>.visual_magnitude`) and the **Timeline** the
blinding, obstruction and visibility events. On the command line:

```
spacemissionstudio model-analyses my_mission.json --out analyses.json --tables analyses_tables
```

## Re-entry casualty (preliminary)

**Run › End of Life › Re-entry casualty (preliminary)**: give the parts
their materials, optionally a population density, and Estimate. Each part
breaks off at 78 km and is followed to the ground; the casualty area and,
with a density, the risk against 1:10,000 are given, with the
demise-prone bound beside the reported one. It is a preliminary estimate,
not a substitute for DAS, DRAMA or SESAM.

```
spacemissionstudio reentry my_mission.json --population-density 25 --out reentry.json
```

## From Python

`api.design_checks(scenario)`, `api.model_analyses(scenario, result)` and
`api.reentry(scenario, population_density_per_km2=...)`; `api.record`
turns each into its record. See [the Python API](../api.md).
