# Getting started

From nothing to your first simulated orbit: install the app, check it
works, run a first mission and know what you should see.

## Contents

1. [What you need](#1-what-you-need)
2. [Pick an install path](#2-pick-an-install-path)
3. [Path A: the installer](#3-path-a-the-installer)
4. [Path B: the install script](#4-path-b-the-install-script)
5. [Path C: from source, step by step](#5-path-c-from-source-step-by-step)
6. [Check that it works](#6-check-that-it-works)
7. [Your first run](#7-your-first-run)
8. [Where things are kept](#8-where-things-are-kept)
9. [If something goes wrong](#9-if-something-goes-wrong)

## 1. What you need

| | |
|---|---|
| Linux | x86_64 or aarch64 with glibc 2.28 or newer (Ubuntu 20.04, Debian 10, RHEL 8 or later). Tested in CI on Ubuntu 24.04. |
| Windows | Windows 10 or 11, x86_64. The test suite runs on Windows in CI, and the setup program is built, installed and run there; it has not yet been tried by hand on a real Windows machine. |
| macOS | macOS 11 or newer on Apple silicon (arm64), from source (path C) only. The test suite runs on macOS in CI. Intel Macs have no Basilisk wheel. |
| Python | 3.11 or newer, for every path: the installers set up the app with the Python already on the computer (Windows: `python` on PATH, from [python.org](https://www.python.org/downloads/)). CI tests with 3.11; Basilisk 2.12.0 has wheels up to 3.14, and versions other than 3.11 and 3.12 have not been tested with the app. |
| Disk | About 1.6 GB: 1.4 GB for the Python environment (Basilisk and Qt), 116 MB of reference data, 36 MB of Earth orientation files. |
| Internet | Once, while installing. After that the app runs offline and downloads nothing without asking. |

The app has two parts:

- **SpaceMissionStudio**: the windows, forms, plots and scenario files.
- **Basilisk**: the simulation engine from the AVS Lab at the University
  of Colorado Boulder, which computes every number. The app opens without
  it (you can build and save scenarios), but **Run** needs it.

## 2. Pick an install path

| Path | For | You type |
|---|---|---|
| **A. Installer** (`.deb` on Linux, `-setup.exe` on Windows) | Using the app | Nothing: double-click |
| **B. Install script** (`packaging/install.sh` or `install.ps1`) | Using the app from a checkout of this repository | One command |
| **C. From source** with `pip` | macOS; developing; scripting from Python; running the tests | About eight commands |

All three install Basilisk 2.12.0, the version the app is verified
against.

## 3. Path A: the installer

Both installers are published with each release. From the
[3.0.0 release](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/v3.0.0), download:

- **Linux:** `spacemissionstudio_3.0.0_all.deb` and `SHA256SUMS-linux`;
  check with `sha256sum -c SHA256SUMS-linux --ignore-missing`.
- **Windows:** `spacemissionstudio-3.0.0-setup.exe` and
  `SHA256SUMS-windows`; check in PowerShell with
  `Get-FileHash .\spacemissionstudio-3.0.0-setup.exe` and compare the
  hash with the one in `SHA256SUMS-windows`. The program is not signed,
  so Windows SmartScreen may warn about an unknown publisher.

You can also build them yourself: the `.deb` with
`packaging/build_deb.sh`, the setup program with
[Inno Setup](https://jrsoftware.org/isinfo.php) from
`packaging/windows/spacemissionstudio.iss`.

**Linux:** double-click `spacemissionstudio_3.0.0_all.deb`, or:

```bash
sudo apt install ./spacemissionstudio_3.0.0_all.deb
```

A closing `N: Download is performed unsandboxed as root ...` line is a
harmless apt notice ([Troubleshooting](troubleshooting.md#messages-that-are-normal)).

**Windows:** double-click `spacemissionstudio-3.0.0-setup.exe` and follow
the wizard.

The installer downloads Basilisk and the reference data once. Then open
**SpaceMissionStudio** from your application menu or Start Menu and go to
[section 6](#6-check-that-it-works).

The 3.0.0 `.deb` was installed by hand on Ubuntu 24.04, where the app
started and template 22 ran. The Windows setup program is
built, installed and run in CI on a Windows runner; it has not yet been tried by hand on a real Windows machine; please report anything that goes wrong. Details: [`packaging/README.md`](../packaging/README.md).

## 4. Path B: the install script

From the `SpaceMissionStudio` folder of a checkout:

```bash
packaging/install.sh --basilisk-wheel "bsk[all]==2.12.0"            # Linux
```

```powershell
packaging\install.ps1 -BasiliskWheel "bsk[all]==2.12.0"             # Windows PowerShell
```

Either one makes a private Python environment, installs both parts and
the reference data into it, and adds a launcher (a desktop entry on Linux,
a Start Menu shortcut on Windows). The Linux script has been run end to
end; the Windows script has not yet been run on a real Windows machine.

## 5. Path C: from source, step by step

**1. Get the code** and open a terminal in its `SpaceMissionStudio`
folder:

```bash
git clone https://github.com/0h3xn4/basilisk-SpaceMissionStudio.git
cd basilisk-SpaceMissionStudio/SpaceMissionStudio
```

**2. Make a private Python environment**, so nothing touches your system
Python:

| Linux and macOS | Windows (PowerShell) |
|---|---|
| `python3 -m venv .venv` | `python -m venv .venv` |
| `source .venv/bin/activate` | `.venv\Scripts\Activate.ps1` |

Your prompt now starts with `(.venv)`. Activate again in every new
terminal. (Windows refuses to run `Activate.ps1`? See
[Troubleshooting](troubleshooting.md#windows-running-scripts-is-disabled-on-this-system).)

**3. Install Basilisk** as a prebuilt wheel (no compiler needed; 1.5 to 7
minutes in our tests, most of it downloading):

```bash
pip install "bsk[all]==2.12.0"
```

**4. Install SpaceMissionStudio** with its GUI (about a minute):

```bash
pip install -e ".[gui]"
```

Use `".[dev,gui]"` instead if you also want to run the tests.

**5. Fetch the reference data** (once):

```bash
spacemissionstudio kernels-status
spacemissionstudio earth-orientation --fetch
```

The first downloads 116 MB (SPICE kernels, the gravity field and the
magnetic model) and lists six files as `OK`. The second downloads the
measured Earth orientation files (36 MB) and ends with:

```text
Earth-fixed frame: ITRF93; high accuracy until 2026-12-18, predicted after.
```

(the date moves with each update). Without these files runs still work,
with a simpler Earth rotation model, and say so.

Every command first prints a line like
`INFO ... Logging to ~/.spacemissionstudio/logs/...log`. That is normal.

## 6. Check that it works

```console
$ spacemissionstudio validate spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json
OK: '22 - Starter: your first LEO satellite' -- 1 spacecraft, schema version 4, epoch 2030-01-01T08:30:00
```

Then start the GUI (installed apps: from the menu; from source:
`spacemissionstudio gui`) and check:

- The status bar at the bottom shows the Basilisk version. "Basilisk
  version not qualified" means a version other than 2.12.0 is installed:
  runs still work, but outside what the app was verified against.
- **Run > Check Reference Data** opens the **Data** tab: every file
  should be `ok`.
- **Help > About SpaceMissionStudio** shows the app's version.

## 7. Your first run

This runs template 22: one 150 kg satellite in a 550 km Sun-synchronous
orbit for one day, with a ground station in Berlin.

**In the GUI** (about a minute):

1. Start the app. Each time it starts, a **Fetch/update data?** dialog
   offers to check for newer reference data. **Skip** is fine once the
   data is installed; **Fetch now** downloads only what you tick.
2. The app opens on **Load Scenario**. Click **22 - Starter: your first
   LEO satellite**; its description appears below the list.
3. Click **Open Template**. The **Scenario Editor** shows the mission; the
   **Explain** tab on the right says what it switches on, and predicts
   `berlin-gs: 4 passes`.
4. **Run > Run Simulation** (`Ctrl+R`). It takes a few seconds.
5. The **Results** tab opens. Pick `my-sat.position_N` in **Series** to
   see the orbit.
6. Open the **Events** tab: four Berlin passes (the first about 10 to 18
   minutes in) and fifteen eclipses of about 35 minutes each.
7. **File > Save As...** to keep your own copy before changing anything.

**From the command line:**

```console
$ spacemissionstudio run spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json --out-dir out
Running '22 - Starter: your first LEO satellite' (1 spacecraft, 1.0 day(s), rkf78)...
Wrote 20 result file(s) to out:
  berlin-gs.access_to_my-sat.azimuth: out/berlin-gs.access_to_my-sat.azimuth.csv
  ...
  my-sat.position_N: out/my-sat.position_N.csv
  my-sat.velocity_N: out/my-sat.velocity_N.csv
  provenance: out/provenance.json
  events (19): out/events.csv
WARNING: space weather uses MSFC's prediction (oct2026f10-prd.txt), 50th percentile F10.7 and Ap
```

The `WARNING` is normal: the mission is in 2030, after the observed
space-weather record ends, so drag uses NASA MSFC's prediction. `out/`
now holds one CSV per quantity (time in seconds, values in SI units),
`events.csv`, and `provenance.json` (which software versions, reference
files and scenario produced the numbers).

**From Python:** `python3 examples/build_a_scenario.py my_first_mission.json`
builds a scenario in code; [the examples](../examples/README.md) show more.

## 8. Where things are kept

| What | Where (Windows: under `%USERPROFILE%` instead of `~`) |
|---|---|
| Your scenarios | Wherever you save them: plain `.json` files |
| Bundled templates | `spacemissionstudio/scenarios/templates/` (the app never overwrites them) |
| Autosave | `~/.spacemissionstudio/autosave/` |
| Log files | `~/.spacemissionstudio/logs/`; error dialogs name the current one |
| Support data (SPICE, gravity, magnetic model) | Basilisk's cache, for example `~/.cache/bsk_support_data/`; `kernels-status` prints it |
| Earth orientation | `~/.cache/SpaceMissionStudio/earth_orientation/` |
| Space-weather downloads | `~/.cache/SpaceMissionStudio/spaceweather/` (only if you ask for newer data than the bundled copy) |
| Vizard, if downloaded | `~/.cache/SpaceMissionStudio/vizard/` |

## 9. If something goes wrong

The three most common problems:

- **"Basilisk is not installed/built" when you click Run.** Activate the
  environment and run `pip install "bsk[all]==2.12.0"`.
- **Linux: `ImportError: libEGL.so.1` when the GUI starts**, or a blank
  plot: install Qt's system libraries (see
  [Troubleshooting](troubleshooting.md#linux-importerror-libeglso1-or-another-so-when-the-gui-starts)).
- **`pip` cannot find `bsk`:** your Python or platform has no Basilisk
  wheel (see [section 1](#1-what-you-need)).

Everything else: [Troubleshooting](troubleshooting.md).

---

**Next:** [Run a template](user-manual/run-a-template.md) ·
[How-to guides](user-manual/README.md) ·
[FAQ](faq.md)
