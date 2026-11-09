# See it in 3D

How to watch a run in 3D: in the app's own **3D View**, or, if you have
one you built or checked yourself, in Vizard.

## The 3D View

**Results › 3D View** shows the last run. It is part of the app: nothing
to install, nothing downloaded, nothing sent anywhere.

- **What it shows:** the central body (Earth shaded by Basilisk's albedo
  map and turning), each spacecraft's path, the spacecraft (its
  [3D model](3d-model.md), or a 1 m cube without one) turned by the
  run's attitude, the ground stations and the Sun's direction.
- **Play** plays the run. The speed beside it is simulated time per
  second; it starts at the speed that plays the whole run in about 30 s.
- **The slider** picks a time. It and the shared time cursor move
  together: click a plot or the Timeline and the view follows; pause or
  drag here and the plots' cursor follows.
- **Whole orbit** draws the spacecraft larger than they are, so they can
  be seen; the note under the controls says by how much. **Paths**
  shows or hides their paths.
- **Follow** a spacecraft shows it at its true size, centred, with its
  body axes (x red, y green, z blue) and arrows to the Sun and to nadir.
- Drag to turn the view, scroll to zoom.

A spacecraft without an attitude in the run (a translation-only run) is
drawn aligned with the inertial axes, and the note says so. The Earth's
turning and the Sun's direction are drawn from standard formulas (the
Earth rotation angle, the Astronomical Almanac's solar position), close
enough to see where things are, not to measure them: the plots and
exports hold the run's numbers.

## Vizard (optional)

Vizard is AVS Lab's separate 3D program. **SpaceMissionStudio does not
download it or look for it:** the build AVS Lab publishes has Unity
Analytics switched on, which sends usage data to Unity
([Network use](../reference/network.md#vizard)). A Vizard you built from
its source or checked yourself can still be used:

1. **Settings > Vizard > Browse...**: choose it. Only that one is ever
   started.
2. On **Run > Run**, in the **Vizard** section, choose how the next run
   feeds Vizard:
   - **Write a .bin playback file to open in Vizard afterward**, or
   - **Live-stream to a Vizard instance already running on this machine**;
     **Run** starts your Vizard if it is not running.
3. Choose what to show: **Camera starts locked on**, **Show each
   spacecraft's orbit**, **Show the flown path**, **Show ground tracks**.
4. After a run that wrote a playback file, **Open in Vizard** in Results
   opens it.

With no Vizard chosen, **Launch Vizard** offers the 3D View or
**Browse...**.

## From the command line

The command line writes the playback file or streams; it never starts or
downloads Vizard:

```bash
spacemissionstudio run scenario.json --out-dir out --vizard-save-file out/run.bin
spacemissionstudio run scenario.json --out-dir out --vizard-live-stream
```

## Limits

- The 3D View shows the last run, after it ends; it keeps up to 1,500
  frames spread over the run.
- Live streaming and Vizard playback files are limited to runs of up to
  100 days.

**More detail:** User Manual section 9,
[3D visualization](../../USER_MANUAL.md#9-3d-visualization).

---

**Next:** [Read the results](read-the-results.md) ·
[Flight software and SIL](flight-software-and-sil.md)
