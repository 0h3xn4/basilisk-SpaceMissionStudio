# See it in 3D (Vizard)

How to watch a run in Vizard, the separate 3D viewer from the AVS Lab
(the Basilisk team): live while it runs, or as a playback file afterwards.

Vizard is optional. The plots already show everything as numbers.

## Get Vizard

**Launch Vizard** (the Run area). If the app cannot find Vizard, a **Vizard not
found** dialog offers:

- **Download Vizard**: fetches AVS's own pre-built copy for your system
  from `hanspeterschaub.info` into `~/.cache/SpaceMissionStudio/vizard/`.
  It downloads only when you click this button.
- **Browse...**: point it at a Vizard you already have.

The app remembers where Vizard is.

## Watch a run

1. **Vizard Configuration...** (the Run area) and choose how the next run feeds
   Vizard:
   - **Write a .bin playback file to open in Vizard afterward**, or
   - **Live-stream to a Vizard instance already running on this machine**
     (start Vizard first with **Launch Vizard** (the Run area)).
2. Choose what to show: **Camera starts locked on** (the central body by
   default, or a spacecraft), **Show each spacecraft's orbit**, **Show the
   flown path**, **Show ground tracks**.
3. **Run** (`Ctrl+R`).
4. After a run that wrote a playback file, **Open in Vizard** in
   Results opens it.

Vizard cannot follow the app's time cursor.

## From the command line

```bash
spacemissionstudio run scenario.json --out-dir out --vizard-save-file out/run.bin
spacemissionstudio run scenario.json --out-dir out --vizard-live-stream
```

## Limits

Live streaming and playback files are limited to runs of up to 100 days.
Vizard shows the RF link and the Mission Dashboard values for a
comms-pointing spacecraft (template 19), and a formation follower's
delta-V and separation from its chief (templates 05 and 29; an ROE
formation also shows its closest radial/cross-track approach). A spacecraft's own look comes
from its [3D model](3d-model.md), or from a model file set on the
spacecraft page's **Vizard model** tab.

**More detail:** User Manual section 9,
[3D visualization with Vizard](../../USER_MANUAL.md#9-3d-visualization-with-vizard).

---

**Next:** [Read the results](read-the-results.md) ·
[Flight software and SIL](flight-software-and-sil.md)
