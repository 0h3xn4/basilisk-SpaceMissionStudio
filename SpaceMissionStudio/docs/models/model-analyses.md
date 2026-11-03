# Analyses built on the 3D model

What SpaceMissionStudio computes from a spacecraft's 3D model and its
mounted equipment, how, and from what sources. Every value used is cited
here or in `config/materials.py`; what could not be sourced is left out
and listed in [decision D-12](../developer/model-analyses-decisions.md).
The design is [model-analyses-design.md](../developer/model-analyses-design.md).

None of this changes how Basilisk computes drag, solar radiation pressure
or anything else: the analyses read what the run computed, or compute
from the model on their own. Drag and SRP have no self-shadowing.

## Ray casting

Every geometric analysis casts rays against the model's parts
(`model3d/raycast.py`):

- exact intersections for boxes, panels, prisms, cylinders, cones and
  spheres, in each part's own frame;
- imported meshes as triangles (Möller–Trumbore) in a bounding-volume
  hierarchy;
- a cone (a field of view, a plume) sampled uniformly in solid angle on a
  Fibonacci spiral, and a face sampled uniformly over its true surface;
- the blocked or shaded fraction reported with its binomial standard error
  `sqrt(f (1 - f) / N)`, `N` the samples (`model_analyses.samples`,
  default 256).

A model with a part that could not be built (an unreadable mesh file, a
missing group) is not analysed: the analysis stops and names the part,
because the part would otherwise be missing from every view, shadow and
fragment without a word.

## Design checks (no run)

| Check | What it computes | Finding |
|---|---|---|
| Field of view | The fraction of each mounted sensor's, camera's and antenna's cone the model's parts block, deployed and stowed | `design.fov_obstructed` |
| Thrusters | Each thruster's force and torque at full thrust about the centre of mass at the beginning of life (fuel tank full) and the end (empty), and the 6 x N matrix's rank | none |
| Plume | The fraction of a cone of the user's half-angle along minus the thrust that meets parts: geometry only | `design.plume_impingement` |
| Mass budget | Each part's and unit's growth allowance from AIAA S-120-2006 by maturity and subsystem (decision D-13), an optional system margin, the propellant, against a user mass limit | `design.mass_over_limit` |
| Launcher | The stowed configuration's largest distance outside a cylinder, box or profile envelope, and the mass and centre of mass against its limits | `design.envelope_protrusion`, `design.launcher_limit` |

Stiffness and fundamental frequencies need a structural model: they are
not checked.

## Disturbance torques (in the run)

Recorded each step for a spacecraft with
`model_analyses.disturbance_torques` (decisions D-07, D-19): the
aerodynamic and SRP torques Basilisk's effectors computed, moved to the
centre of mass; the gravity gradient `3 mu / R^5 r x (I r)`; the residual
dipole `m x B` with WMM. The budget gives each source's largest and mean
magnitude, its orbit average, the momentum (the integrated torque), the
largest momentum in one orbit, and the analytical worst cases
(`analyses/disturbances.py`). Wheels and magnetorquers smaller than the
need are findings (`design.wheel_capacity`, `design.dipole_capacity`),
with no margin (decision D-18).

## After the run

| Analysis | Series | Method |
|---|---|---|
| Sensor blinding | `<sc>.blinding.<item>`, `<sc>.blinding.all_star_trackers` | The boresight within the exclusion angle plus the body's angular radius of the Sun (when lit), the central body (plus `earth_atmosphere_km`) or the Moon (when tracked) |
| Antenna obstruction | `<station>.access_to_<sc>.antenna_obstructed` | During each pass, a ray from the antenna to the station against the model |
| Array shading | `<sc>.shading.<item>`, `<sc>.shading.power` | The solar-cell face's light from the Sun, shaded by other parts (0 in umbra, where no ray is cast); its power with the power budget's efficiency |
| Exposure | `<sc>.exposure.ao_flux`, `<sc>.exposure.sun_factor` | Atomic-oxygen flux `n_O v cos(alpha)` with `n_O = rho / m_O` (an upper bound, D-08); equivalent sun hours |
| Brightness | `<site>.brightness_of_<sc>.visual_magnitude` | Diffuse (Lambert) reflection of the lit facets toward a dark site, `m_sun = -26.74` |

## Parameters

| Parameter | Default | Unit | Controls | Source |
|---|---|---|---|---|
| `observer_sun_depression_deg` | 0 | deg | A site counts as dark while the Sun is at least this far below its horizon | Geometric sunset by definition (D-17) |
