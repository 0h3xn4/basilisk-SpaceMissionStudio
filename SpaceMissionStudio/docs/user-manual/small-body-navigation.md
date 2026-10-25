# Fly around an asteroid and navigate from its landmarks

How to put a spacecraft in orbit around asteroid 433 Eros, with the gravity
of its real shape, and let a navigation filter estimate the orbit from
landmarks a camera sees on the surface.

Template **31** does this: a 35 km orbit over Eros's poles, a filter that
starts 100 m off and is within 0.35 m (median) for two days.

## Get the Eros files first

A run around Eros needs two files that the app does not ship:

* the **ephemeris** `eros_1900_2100.bsp` (4.6 MB): where Eros is, from
  1900 to 2100, a JPL Horizons n-body solution from NAIF's generic
  kernels; checked against its SHA-256 before it is used;
* the **shape model** `eros007790.tab` (0.5 MB): Gaskell's NEAR shape,
  3897 vertices and 7790 facets, from Basilisk's support data.

Download them in **Reference data** (**Download...**, **Small bodies**;
it asks first and names the sources), or run
`spacemissionstudio small-bodies --fetch`. Without internet, copy
`eros_1900_2100.bsp` from another computer and use **Import file...**
or `spacemissionstudio small-bodies --import FILE`. **Scenario > Overview**
lists either file when it is missing.

## What it models

**Where Eros is and how it turns.** Eros is a SPICE body like the
planets, and the centre of the run's frame. It turns once every 5.27 h
about its pole (pck00010's rotation model, frame `IAU_EROS`).

**Its gravity.** With **Gravity from the shape model** (the **Environment**
page), Basilisk's `polyhedralGravityModel` computes the pull of the
shape at constant density, with Eros's GM of 4.463e-4 km³/s² (from the
kernel's Horizons header). Close to an elongated body this differs from a
point mass by tens of percent: in template 31 the shape alone moves the
probe between 35.0 and 38.0 km from the centre. Without the box, Eros is a
point mass.

**Impacts.** A position inside the shape is reported as a hit, with its
time; the run integrates on through the body, so later results are not
physical.

**Landmark navigation** (the spacecraft's **Power / propulsion / link budget** page,
**Landmark navigation**):

* Landmarks are placed on facets of the shape, spread evenly by area.
* Basilisk's `pinholeCamera` reports the whole pixel of each landmark it
  sees: in front of the camera, facing it, on the detector, and with the
  Sun at least **Lowest Sun elevation** above the landmark's horizon.
* The app's own Kalman filter estimates position and velocity from the
  pixels. It predicts with the shape's gravity and Eros's spin, and
  measures each pixel from its centre: the rounding to whole pixels
  alone is 0.29 px (1 sigma), and **Added pixel noise** comes on top.

## Set it up

1. On the **Environment** page: **Central body** `eros`, tick **Gravity from
   the shape model**, and tick `sun` among the third bodies (the camera
   needs the light).
2. Give the spacecraft an orbit around Eros: classical elements with a
   semi-major axis of a few tens of kilometres. Eros's pole is at RA
   11.35 deg, Dec 17.22 deg, so inclination 90 deg and RAAN 11.35 deg give
   an orbit over its poles (template 31).
3. On the spacecraft's **Power / propulsion / link budget** page, tick
   **Landmark navigation** and set the **Landmarks**, the camera (**Field
   of view** across the image's width, **Resolution**, **Camera
   mounting**), **Image every [s]**, the noise and the filter's start.

**Pointing.** In an orbit-only run the camera points at Eros's centre.
With attitude, the spacecraft's attitude points it: use
**locationPointing** on Eros with the pointing axis along the camera's
boresight. **Scenario > Overview** warns when it is missing, and gives the
orbit period in turns of Eros and the metres per pixel on the surface.

## Read the results

* `{spacecraft}.position_P`: the position in Eros's frame;
  `{spacecraft}.small_body.distance`: from its centre.
* Under `{spacecraft}.landmark_navigation.` (plot group **Sensors**):
  `.position_error`, `.velocity_error` (the estimate minus the truth),
  `.position_3sigma`, `.velocity_3sigma` (the filter's own bounds),
  `.landmarks_seen` per image and `.residual_rms` (the pixel residuals
  before each update).

In template 31: 5.5 m after the first image, 0.35 m (median) after it, up
to 4.8 m just after the stretches over the night side (22 of 289 images
see no landmark), inside the filter's 3-sigma; about 18 landmarks per
image; residuals of 0.28 px. With 1 px of added noise the residuals are
about 1 px and the error about 5 m (median over the first half day).

## Limits

* 433 Eros only, and only as the central body; one run of at most 100
  days, inside 1900 to 2100.
* The gravity is the shape at constant density. NEAR's tracking found
  Eros's interior close to uniform (Miller et al. 2002, *Icarus* 155),
  but not exactly.
* Basilisk's camera does not check whether other terrain hides a landmark,
  and no image is rendered: the pixels come from the geometry.
* The filter knows the shape, Eros's GM and spin, the spacecraft's attitude
  and the landmark positions exactly; the Sun's pull and light pressure
  act in the run but not in the filter (its process noise covers them).
  Real navigation has errors in all of these, so the results are
  optimistic.
* Eros's shadow is a sphere of its mean radius (8.42 km): Basilisk's
  eclipse model takes only spheres.
* A simulated day takes about 2 minutes of computing.

**More detail:** User Manual section 6,
[Small bodies and landmark navigation](../../USER_MANUAL.md#small-bodies-and-landmark-navigation).

---

**Next:** [Optical navigation](optical-navigation.md) ·
[How-to guides](README.md)
