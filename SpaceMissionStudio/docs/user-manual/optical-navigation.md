# Navigate from camera images of a planet

How to give a spacecraft a camera that sees the central body, and let a
navigation filter estimate its orbit from the images.

Template **30** does this around Mars: the filter starts 68 km off and is
within 2 km by day 1.

## What it models

Each image is reduced to what an image-processing step finds in it:
where the centre of the planet's disk falls on the detector, and how
large the disk is. The app computes these from the true geometry and adds
pixel noise; **no image is rendered**. Then two Basilisk modules do the
navigation, unmodified:

* `pixelLineConverter` turns the disk into a position relative to the
  planet: the direction from its place in the image, the range from its
  size.
* `relativeODuKF`, an unscented Kalman filter with two-body dynamics
  around the planet, combines those positions into a position and
  velocity estimate.

The range comes from the disk's size, so it is the weak part: with 0.5 px
of radius noise and Mars 110 to 150 px in radius, one image is good to
about 50 km at 15 000 to 22 000 km. The filter combines many images and
does much better.

## Set it up

1. The central body must be **earth**, **mars barycenter** or **jupiter
   barycenter** (the bodies Basilisk's two modules know), with **sun**
   among the third bodies (the **Environment** page).
2. On the spacecraft's **Power / propulsion / link budget** page, tick
   **Optical navigation (camera on the central body)**.
3. Set the camera: **Field of view [deg]** (edge to edge along the
   image's height), **Resolution [px]**, and **Camera mounting** (an MRP;
   all zero: the camera looks along the body's +z axis).
4. Set the measurement: **Image every [s]**, the **Disk centre** and
   **Disk radius noise [px]**, the **Smallest usable disk [px]** and the
   **Largest phase angle [deg]** (the Sun-planet-camera angle; above 90 deg
   the camera sees mostly the night side, and the image is not used).
5. Set the filter's start: **Initial position** and **velocity
   uncertainty** (it starts one random draw of these off, with this
   uncertainty), the **Process noise**, and the **Random seed**.

**Pointing.** In an orbit-only run the camera points at the planet
perfectly. With attitude, the spacecraft's attitude points it: use
**locationPointing** on the central body, with the pointing axis
(`pHat_B`) along the camera's boresight. **Scenario > Overview** warns when
either is missing, and gives the disk's size at periapsis and apoapsis.

## Read the results

All under `{spacecraft}.optical_navigation.` (plot group **Sensors**):

* `.position_error`, `.velocity_error`: the filter's estimate minus the
  truth; `.position_3sigma`, `.velocity_3sigma`: its own 3-sigma bounds.
* `.measurement_error`: what one image alone gives, minus the truth.
* `.measurement`: the disk's centre and radius on the detector [px].
* `.measurement_state`: 0 used; 1 behind the camera; 2 not wholly in the
  image; 3 too small; 4 night side; 5 inside the body.
* `.range`, `.phase_angle`.

In template 30: 62 % of the images are used, one image is good to 56 km
(median), and the filter error is 1.6 km (median) after day 1, up to
12 km just after each night-side stretch, inside its own 3-sigma for 94 %
of the samples.

## Limits

* No image is rendered or processed. A real image of a crescent has its
  centre offset from the planet's; that is not modelled, so results on
  the lit side near 90 deg phase are optimistic.
* The attitude the converter uses is the true one (perfect attitude
  knowledge).
* Earth, Mars and Jupiter only, the last two as their system
  barycentres; one run of at most 100 days.
* The filter's dynamics are two-body around the planet. The Sun's pull
  and, for Earth, higher gravity terms act in the run but not in the
  filter; its process noise must cover them.
* Basilisk's filter adds the process noise at each of its time updates,
  two for each image used.

**More detail:** User Manual section 6,
[Optical navigation](../../USER_MANUAL.md#optical-navigation).

---

**Next:** [ROE formations](roe-formation.md) ·
[How-to guides](README.md)
