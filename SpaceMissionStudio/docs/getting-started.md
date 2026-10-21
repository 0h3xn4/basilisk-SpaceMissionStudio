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
| Windows | Windows 10 or 11, x86_64. The test suite passes on Windows in CI (two tests that failed intermittently are fixed and under watch, SRelD K-14). |
| macOS | macOS 11 or newer on Apple silicon (arm64), from source (path C) only. The test suite passes on macOS in CI. Intel Macs have no Basilisk wheel. |
| Python | None for the installers (path A): they bring their own Python 3.11. Paths B and C need Python 3.11 or newer (Windows: from [python.org](https://www.python.org/downloads/), on PATH). CI tests with 3.11; Basilisk 2.12.0 has wheels up to 3.14, and versions other than 3.11 and 3.12 have not been tested with the app. |
| Disk | About 1.7 GB: Python with Basilisk and Qt, 117 MB of reference data, 36 MB of Earth orientation files. |
| Internet | None for the installers. Paths B and C: once, while installing. After that the app runs offline and downloads nothing without asking. |

The app has two parts:

- **SpaceMissionStudio**: the windows, forms, plots and scenario files.
- **Basilisk**: the simulation engine from the AVS Lab at the University
  of Colorado Boulder, which computes every number. The app opens without
  it (you can build and save scenarios), but **Run** needs it.

## 2. Pick an install path

| Path | For | You type |
|---|---|---|
| **A. Installer** (`.deb` on Linux, setup program on Windows) | Using the app | Nothing: double-click |
| **B. Install script** (`packaging/install.sh` or `install.ps1`) | Using the app from a checkout of this repository | One command |
| **C. From source** with `pip` | macOS; developing; scripting from Python; running the tests | About eight commands |

All three give you Basilisk 2.12.0, the version the app is verified
against. Linux on ARM (aarch64) and macOS have no installer: use path B
or C.

## 3. Path A: the installer

From the [releases page](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases),
download the installer for your system with its checksum file, and check
it (`sha256sum -c SHA256SUMS-linux --ignore-missing` on Linux;
`Get-FileHash` in PowerShell on Windows). You can also build the
installers yourself: `packaging/build_deb.sh`, and on Windows
[Inno Setup](https://jrsoftware.org/isinfo.php) with
`packaging/windows/spacemissionstudio.iss`
([`packaging/README.md`](../packaging/README.md)).

The installers are self-contained: they bring their own Python, Basilisk
and the reference data, so they need no Python on the computer and no
internet. (This holds from 1.1.1 on. The 1.1.0 files still set up a
Python environment while installing: the 1.1.0 `.deb` downloads
Basilisk and the data, and the 1.1.0 Windows setup program also needs
Python 3.11 on PATH.)

**Linux** (x86_64; Ubuntu 22.04, Debian 12 or later): double-click
`spacemissionstudio_<version>_amd64.deb`, or:

```bash
sudo apt install ./spacemissionstudio_<version>_amd64.deb
```

A closing `N: Download is performed unsandboxed as root ...` line is a
harmless apt notice ([Troubleshooting](troubleshooting.md#messages-that-are-normal)).

**Windows 10/11** (x64): run `spacemissionstudio-<version>-setup.exe`.
It is not signed, so Windows asks before running it (**More info**, then
**Run anyway**). It installs for your user only, without administrator
rights, under `%LOCALAPPDATA%\SpaceMissionStudio`.

Then open **SpaceMissionStudio** from your application menu or the Start
Menu and go to [section 6](#6-check-that-it-works).

What was verified for the installers, and how:
[`packaging/README.md`](../packaging/README.md).

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

The first downloads 116 MB (SPICE kernels, the gravity fields and the
magnetic model) and lists nine files as `OK`. The second downloads the
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

- The status bar at the bottom shows the Basilisk version. "(not
  qualified)" after it means a version other than 2.12.0 is installed:
  runs still work, but outside what the app was verified against.
- **Run > Check Reference Data** opens the **Reference data** dialog: every file
  should be `ok`.
- **Help > About SpaceMissionStudio** shows the app's version
  (`spacemissionstudio --version` in a terminal).

## 7. Your first run

This runs template 22: one 150 kg satellite in a 550 km Sun-synchronous
orbit for one day, with a ground station in Berlin.

**In the GUI** (about a minute):

1. Start the app. Each time it starts, a **Fetch/update data?** dialog
   offers to check for newer reference data. **Skip** is fine once the
   data is installed; **Fetch now** downloads only what you tick.
2. The app opens on **Templates**. Click **22 - Starter: your first
   LEO satellite**; its description appears below the list.
3. Click **Open Template**. The **Scenario** tab shows the mission; the
   **Explain** page of the side panel says what it switches on, and predicts
   `berlin-gs: 4 passes`.
4. **Run** on the toolbar (`Ctrl+R`). It takes a few seconds.
5. The **Results** tab opens. Click "Inertial Position (ECI)" in the
   catalog on the left (search `position_N`) to see the orbit.
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
| Support data (SPICE, gravity, magnetic model) | Installers: inside the install folder (`.../site-packages/supportData/`). Otherwise Basilisk's cache, for example `~/.cache/bsk_support_data/`. `kernels-status` prints it |
| Earth orientation | Installers: inside the install folder (`.../share/spacemissionstudio/earth_orientation/`). Files you download go to `~/.cache/SpaceMissionStudio/earth_orientation/` and are used first |
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
