# Verification and validation: analyses built on the 3D model

The record of how the model analyses (requirements SRS-F-25 to F-27) were
checked. Each case is a test that runs in the suite; the reference is a
hand calculation, an analytic result, Basilisk's own output or a
published formula, never the code under test. Measured 2026-11-03 on
Python 3.14.6, Basilisk 2.12.0, x86-64 with 4 cores.

## Ray casting (`tests/test_model_raycast.py`)

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| Distance along a ray to a box, panel, prism, cylinder, sphere and cone | Analytic intersection (a curved shape on its curve, not its facets) | 1e-12 m | Equal |
| Rays beside a cylinder's top, a sphere, a cone's apex | Miss | exact | All miss |
| A cone met on its apex and on its base | 4.5 m, 4.5 m | 1e-12 m | Equal |
| A box turned 90 deg and moved 3 m | 7.0 m | 1e-12 m | Equal |
| 2000 random rays: a box as a mesh against the box | The analytic box | 1e-12 m | Equal |
| 2000 random rays: a 256-segment sphere mesh against the sphere | Within the faceting's sagitta `1 - cos(pi/128)` | 30 x sagitta | Within |
| Face samples of every face of every shape | The face's true area | 1e-12 relative | Equal |
| Cone directions | Mean cosine of a uniform cap `(1 + cos a) / 2` | 1e-4 | Equal |
| A panel shading half a box face from above | 0.5 | 0.02 at 4096 samples | 0.5 |
| The same lit at 45 deg | 0 (the shadow slides off) | 1e-9 | 0 |
| A panel covering 0.3 of a face: convergence | 0.3 | error falls 16 -> 4096 samples, < 0.01 at 4096 | Falls |
| A panel over half of a 90 deg cone | 0.5 | 0.01 at 4096 | 0.5, standard error < 0.01 |

## Field of view (`tests/test_design_checks.py`, `tests/test_template_claims.py`)

| Case | Reference | Result |
|---|---|---|
| A camera 1 m above a panel, 40 deg field of view: footprint radius 0.985 tan 20 deg = 0.36 m inside the 1 m panel | 100 % blocked deployed, 0 % stowed | 100 %, 0 % |
| Template 32's star tracker, 20 deg, 10 deg below the arrays: convergence | The fraction settles; the standard error bounds the change | 5.47 +- 1.42 % (256 rays), 5.86 +- 0.37 % (4096), 5.78 +- 0.09 % (65 536) |
| Sun exclusion of a tracker 29.6 / 30.4 deg from the Sun with a 30 deg exclusion (the Sun's 0.27 deg radius added) (`tests/test_run_analyses.py`) | Blinded / not blinded; not in umbra | As expected |
| Sun-pointing spacecraft (template 28, +z at the Sun), tracker on +z with 30 deg Sun exclusion (live run) | Blinded whenever lit | 64.6 % of samples blinded by the Sun against 65.2 % sunlit (penumbra samples differ) |

## Disturbance torques (`tests/test_disturbance_torques.py`)

| Case | Reference | Tolerance | Result |
|---|---|---|---|
| Gravity gradient at 45 deg between the principal x and y axes, R = 7000 km | `3 mu / (2 R^3) (I_y - I_x)` (SP-8024 vector form), zero along an axis | 1e-12 relative | Equal |
| Residual dipole 2 A m^2 (z) in 30 uT (x) | 6e-5 N m along y | exact | Equal |
| A 1e-5 N force at (0.5, 0, 0) m, centre of mass at (0.1, 0, 0) m | `(0.4, 0, 0) x F` | exact | Equal |
| SRP on one 1 m^2 plate at (0.5, 0, 0) m in a run (Basilisk's facetSRP) | Torque `(r - r_c) x F` for Basilisk's force at every sample; `|F| = P A (1 + rho_s + 2 rho_d/3)` at the epoch's Sun distance | 1e-15 N m; 1 % | Equal; within 0.5 % |
| Momentum of a constant 1e-5 N m for two 6000 s orbits | 0.06 N m s per orbit, 0.12 over the run | 1e-12 | Equal |
| A torque 1e-5 sin(2 pi t / P) | Zero over an orbit; largest within one `2e-5 P / (2 pi)`; mean magnitude `2e-5 / pi` | 1e-3 | Equal |
| Sizing: 0.06 N m s per orbit against a 0.05 N m s wheel; 0.333 A m^2 needed against 0.2 | Findings `design.wheel_capacity`, `design.dipole_capacity` | | Both raised; none with 0.1 N m s and 1 A m^2 |
| SRP worst case of one 2 m^2 plate 1 m from the centre of mass | A = 2 m^2, L = 1 m, q = 0.5 | 1e-3 | Equal |
| Template 32, one orbit | Recorded gravity gradient at most its analytical worst case | | 7.96e-5 <= 8.48e-5 N m |

The aerodynamic torque has no separate analytic case: it is Basilisk's
facetDrag torque moved to the centre of mass by the same code as SRP,
checked above, and its worst case is the run's largest force times the
largest centre-of-pressure offset (recorded maxima stay below it in
templates 28 and 32).

## Thrusters (`tests/test_design_checks.py`)

| Case | Reference | Result |
|---|---|---|
| Two 2 N thrusters at x = +-0.5 m firing +y and -y | Forces cancel, 1 N m each about z; with 50 kg at z = 0.6 m on 300 kg the centre of mass at 0.0857 m adds +-0.171 N m about x, cancelling in the pair; rank 2 | Equal |
| A 45 deg plume cone 0.5 m above a panel's edge | Half the cone meets the panel | 0.5 +- 0.01 at 4096 rays |

## Mass budget and launcher (`tests/test_design_checks.py`)

| Case | Reference | Result |
|---|---|---|
| Template 28 parts with S-120 categories, a 3 kg electronics unit, a 2 kg unit of an unknown subsystem, 10 % system margin, 50 kg propellant | 58 + 4 + 0.9 + 1.1 kg growth; 1.1 x 369 + 50 = 455.9 kg; over a 420 kg limit | Equal; finding raised |
| Template 32 | 37.8 + 2.4 + 0.09 + 1.5 + 0.75 = 42.54 kg growth, 352.54 kg launch | Equal |
| Folded panels reaching 1.0 m below the origin, separation plane at -0.7 m | 0.3 m outside, below the plane | 0.3 m (1e-12) |
| A 1.5 m box: the dish apex at x = 0.8 m | 0.05 m outside in width | 0.05 m (1e-12) |
| Faceting error of the dish's 0.3 m radius at 128 sides | `0.3 (1 - cos(pi/128))` | Equal |
| Centre-of-mass height and lateral offset against limits | `z_c + 0.7`, `|x_c|`; three limit findings | Equal |

## Exposure and shading (`tests/test_run_analyses.py`)

| Case | Reference | Result |
|---|---|---|
| A ram-facing 1 m^2 face at 7.6 km/s in 1e-12 kg/m^3 for 3600 s | `rho / m_O v t` atoms/cm^2; erosion `F Y` with Kapton H's yield | Equal (1e-9) |
| Sun hours on a face toward the Sun for 3600 s at 1 AU | 1.0 h; 0 on a face away | Equal |
| Array cells under a panel covering half of them, Sun overhead; then at 60 deg | 0.5 shaded, `S A eta / 2`; 0 shaded, `S A eta cos 60` | Within 0.02 and 4 % |

## Brightness (`tests/test_run_analyses.py`)

| Case | Reference | Result |
|---|---|---|
| A 2 m sphere of 20 000 diffuse facets (rho_d 0.3) at 500 km, phase 80 deg | The Lambert sphere (Hostetler and Cowardin, NTRS 20190033905, Eq. 10) | Within 0.01 mag |
| A 1 m^2 plate facing the site, rho_d 0.5, the Sun 10 deg below the horizon | `m_sun - 2.5 log10(0.5 sin 10 deg / (pi H^2))` | Equal (1e-9) |
| Darkness: the Sun 10 deg down | Dark at 0 and 8 deg depression, not at 12; not seen in umbra | As expected |

## Re-entry (`tests/test_reentry.py`)

| Case | Reference | Result |
|---|---|---|
| The Sutton–Graves constant | `0.1113 / (2 sqrt(101325)) = 1.748e-4` | Equal (1e-3) |
| 2 kg with 0.2 m^2 of surface, no heating | Terminal speed `sqrt(2 m g / (rho_0 S/4))` at sea level, US76 rho_0 = 1.225 | Within 1 % |
| 1 kg of aluminium over 1 m^2 | Demises above 60 km | Yes |
| 200 kg over 1 m^2 | Survives at eps = 1; less left at eps = 0 | Yes |
| Casualty area and risk | `(0.6 + sqrt(S/4))^2` per fragment over 15 J; risk `A_c rho`; limit 1e-4 | Equal |

**Published reference case:** none was compared. No DAS case with
fragment-by-fragment results was accessible from where this was built.
The estimate is labelled preliminary for this reason too.

## Performance (`model3d/raycast.py`)

Template 32 (the 300 kg bus, six parts):

| Operation | Time |
|---|---|
| Scene build | 25 ms |
| One 20 deg cone, 256 / 4096 / 65 536 rays | 1.9 / 10.1 / 150 ms (about 0.4 M rays/s) |
| All design checks, 256 / 4096 rays per cone | 27 / 48 ms |
| One face's shading, 1024 samples | 3.4 ms |
| Template 32's run (one orbit, 1 s steps) with the disturbance torques and array shading | 12.9 s (the run alone about 3 s) |

Meshes: 100 000 rays against a 65 024-triangle sphere took 13.9 s
(7 k rays/s): the bounding-volume hierarchy is traversed in Python. A
large imported CAD model is the slow case; lower `model_analyses.samples`
for it.

## Coverage

The coverage thresholds (90 % of statements, 80 % of branches) are kept:
see the suite's report in the progress file.
