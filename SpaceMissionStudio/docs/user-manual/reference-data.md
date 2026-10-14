# Manage the reference data, and work offline

How to see which data files the app uses, update them, install them from
disk on a machine without internet, and undo an update.

## What the app needs

| Data | Used for | Comes from | Size |
|---|---|---|---|
| SPICE kernels (leap seconds, planet positions, masses, orientations) | Time, Sun and Moon positions | NAIF | about 116 MB with the next two |
| Gravity field (GGM03S) | Earth's detailed gravity | the Basilisk repository | |
| Magnetic model (WMM2025) | Torque rods, magnetometers | the Basilisk repository | |
| Space weather (observed F10.7 and Ap) | Atmospheric density, so drag | CelesTrak; a copy is bundled | about 3 MB |
| Solar-activity prediction | Drag after the observed record ends | NASA MSFC; bundled | small |
| Earth orientation (IERS-based NAIF Earth PCKs) | Measured Earth rotation | NAIF | about 36 MB |

Runs never download anything. Space weather is always real data: the
observed record, then MSFC's prediction. There is no synthetic profile.

## Check what you have

Open the **Reference data** dialog (**Run > Check Reference Data**, **Tools > Reference Data...**, or the reference data entry in the status bar). It lists every
file with its status (ok, missing, out of date), the dates it covers,
where it came from and its SHA-256. From the command line:

```bash
spacemissionstudio kernels-status        # downloads any missing support file, then lists them
spacemissionstudio earth-orientation     # lists the Earth orientation files
spacemissionstudio spaceweather-resolve scenario.json   # which space-weather data a run would use
```

## Update

Each time the GUI starts, a **Fetch/update data?** dialog offers to fetch
the support data, CelesTrak's latest space weather and the Earth
orientation files. Tick what you want and press **Fetch now**, or
**Skip**: nothing is downloaded then.

At any time, in the **Reference data** dialog, **Download...** offers three downloads: *Support
data*, *Space weather* and *Earth orientation*. Each asks first, naming
the source, the files and their size; the default is No. Afterwards it
says what changed.

From the command line: `spacemissionstudio kernels-status` (support data)
and `spacemissionstudio earth-orientation --fetch`.

Hosts to allow through a firewall: `naif.jpl.nasa.gov`,
`raw.githubusercontent.com`, `celestrak.org`, and `pypi.org` for the
install itself.

## Work offline

1. On a machine with internet, install the app and fetch the data
   (above). Copy the files you need, for example from
   `~/.cache/SpaceMissionStudio/earth_orientation/` or a CelesTrak
   `SW-All.csv`.
2. On the offline machine, **Import file...** in the **Reference data**
   dialog installs a
   space-weather or Earth orientation file from disk. From the command
   line: `spacemissionstudio earth-orientation --import FILE.bpc`.
3. Support data (SPICE kernels, gravity, magnetic model) goes into
   Basilisk's own cache; copy that folder (`kernels-status` prints where
   it is).

Without Earth orientation files, runs use a simpler Earth rotation model
and say so. Without the support data, Run stops and names the missing
file.

## Undo an update

**Roll back...** in the **Reference data** dialog puts back the version that the last download or
import replaced. From the command line: `spacemissionstudio
earth-orientation --rollback`.

## Where files are kept

| What | Where |
|---|---|
| Support data | Basilisk's cache, for example `~/.cache/bsk_support_data/` |
| Space-weather downloads | `~/.cache/SpaceMissionStudio/spaceweather/` |
| Earth orientation | `~/.cache/SpaceMissionStudio/earth_orientation/` |
| Vizard download | `~/.cache/SpaceMissionStudio/vizard/` |

**More detail:** User Manual section 7, the **Reference data** paragraph of
[Reading the Results tab](../../USER_MANUAL.md#7-reading-the-results-tab).

---

**Next:** [Troubleshooting](../troubleshooting.md) ·
[FAQ](../faq.md)
