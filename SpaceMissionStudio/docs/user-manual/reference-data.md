# Manage the reference data, and work offline

How to see which data files the app uses, update them, install them from
disk on a machine without internet, and undo an update.

## What the app needs

| Data | Used for | Comes from | Size |
|---|---|---|---|
| SPICE kernels (leap seconds, planet positions, masses, orientations) | Time, Sun and Moon positions | NAIF | about 116 MB with the next three |
| Gravity fields (GGM03S, GGM2B) | Earth's and Mars's detailed gravity | the Basilisk repository | |
| Magnetic model (WMM2025) | Torque rods, magnetometers | the Basilisk repository | |
| Albedo maps (Earth CERES, Mars TES) | Reflected sunlight on the sun sensors | the Basilisk repository | |
| Atmosphere profiles (U.S. Standard Atmosphere 1976, Earth-GRAM 2016 and NRLMSISE-00 nominal profiles) | The tabular atmosphere (`atmosphere_model` "tabular") | the Basilisk repository | |
| Space weather (observed F10.7 and Ap) | Atmospheric density, so drag | CelesTrak; a copy is bundled | about 3 MB |
| Solar-activity prediction | Drag after the observed record ends | NASA MSFC; bundled | small |
| Earth orientation (IERS-based NAIF Earth PCKs) | Measured Earth rotation | NAIF | about 36 MB |
| 433 Eros ephemeris and shape model | A run around Eros ([small bodies](small-body-navigation.md)) | NAIF and the Basilisk repository; downloaded on request | about 5 MB |
| ITU-R P.676-13, data file Part 1 | The atmospheric gases' attenuation of the radio link, when a project chooses it (`link.atmospheric_loss`) | the ITU; the installers fetch it | 44 kB |

Runs never download anything. Space weather is always real data: the
observed record, then MSFC's prediction. There is no synthetic profile.

## Check what you have

Open the **Reference data** window (**Check Reference Data** (the Run area), **Settings > Reference data**, or the reference data entry in the status bar). It lists every
file with its status (ok, missing, out of date), the dates it covers,
where it came from and its SHA-256. From the command line:

```bash
spacemissionstudio kernels-status        # downloads any missing support file, then lists them
spacemissionstudio earth-orientation     # lists the Earth orientation files
spacemissionstudio spaceweather-resolve scenario.json   # which space-weather data a run would use
```

## Update

Each time the GUI starts, a **Fetch or update reference data?** card on
**Home** offers to fetch
the support data, CelesTrak's latest space weather and the Earth
orientation files. Tick what you want and press **Fetch now**, or
**Not now**: nothing is downloaded then.

At any time, in the **Reference data** window, **Download...** offers five downloads: *Support
data*, *Space weather*, *Earth orientation*, *Small bodies* and *Gaseous
attenuation* (ITU-R P.676-13 Part 1). Each asks first, naming
the source, the files and their size; the default is No. Afterwards it
says what changed.

From the command line: `spacemissionstudio kernels-status` (support data),
`spacemissionstudio earth-orientation --fetch`, `spacemissionstudio
small-bodies --fetch` and `spacemissionstudio gaseous-attenuation --fetch`. Part 1 is installed only if it is the ITU's
file, byte for byte (its size and SHA-256 are in the code).

Hosts to allow through a firewall: `naif.jpl.nasa.gov`,
`raw.githubusercontent.com`, `celestrak.org`, `www.itu.int`, and
`pypi.org` for the install itself.

## Work offline

1. On a machine with internet, install the app and fetch the data
   (above). Copy the files you need, for example from
   `~/.cache/SpaceMissionStudio/earth_orientation/` or a CelesTrak
   `SW-All.csv`.
2. On the offline machine, **Import file...** in the **Reference data**
   window installs a
   space-weather, Earth orientation, Eros ephemeris or ITU-R P.676-13
   Part 1 file from disk. From the command line: `spacemissionstudio
   earth-orientation --import FILE.bpc`, `spacemissionstudio
   small-bodies --import FILE`, `spacemissionstudio
   gaseous-attenuation --import FILE.txt`.
3. Support data (SPICE kernels, gravity, magnetic model, albedo maps,
   atmosphere profiles) goes into
   Basilisk's own cache; copy that folder (`kernels-status` prints where
   it is).

Without Earth orientation files, runs use a simpler Earth rotation model
and say so. Without the support data, Run stops and names the missing
file.

## Undo an update

**Roll back...** in the **Reference data** window puts back the version that the last download or
import replaced. From the command line: `spacemissionstudio
earth-orientation --rollback`.

## Where files are kept

| What | Where |
|---|---|
| Support data | Installed with the `.deb` or the Windows setup: inside the install folder (`.../site-packages/supportData/`). Otherwise Basilisk's cache, for example `~/.cache/bsk_support_data/` |
| Space-weather downloads | `~/.cache/SpaceMissionStudio/spaceweather/` |
| Earth orientation | Downloads and imports: `~/.cache/SpaceMissionStudio/earth_orientation/`, used first. The installers also put a copy, as current as the installer, inside the install folder |
| ITU-R P.676-13 Part 1 | Downloads and imports: `~/.cache/SpaceMissionStudio/itu_p676/`, used first. The installers also put a copy inside the install folder |
| Eros ephemeris | `~/.cache/SpaceMissionStudio/small_bodies/` (the shape model goes into Basilisk's cache, with the support data) |

**More detail:** User Manual section 7, the **Reference data** paragraph of
[Reading the results](../../USER_MANUAL.md#7-reading-the-results).

---

**Next:** [Troubleshooting](../troubleshooting.md) ·
[FAQ](../faq.md)
