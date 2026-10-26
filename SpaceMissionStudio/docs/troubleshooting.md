# Troubleshooting

What to do when installing or running SpaceMissionStudio goes wrong,
listed by the message you see. The messages are quoted exactly.

## Contents

- [Installing](#installing)
- [Starting the app](#starting-the-app)
- [Reference data](#reference-data)
- [Running a scenario](#running-a-scenario)
- [Scenario files](#scenario-files)
- [Messages that are normal](#messages-that-are-normal)
- [Reporting a problem](#reporting-a-problem)

## Installing

### `pip` cannot find `bsk`

Basilisk 2.12.0 has prebuilt wheels only for:

- Linux x86_64 and aarch64 with glibc 2.28 or newer (`ldd --version`
  shows yours);
- Windows x86_64;
- Python 3.11 to 3.14 (`python3 --version`).

On anything else (an older Linux such as Ubuntu 18.04) pip
finds no wheel. Use a newer system, or build Basilisk from source
([Basilisk's build guide](../../docs/source/Build.rst); rarely needed).

### Behind a company firewall or proxy

`pip` and the reference-data downloads honour the usual `HTTPS_PROXY`
environment variable; set it before installing. The hosts to allow:

| Host | For |
|---|---|
| `pypi.org`, `files.pythonhosted.org` | Installing Basilisk and the Python packages |
| `naif.jpl.nasa.gov` | SPICE kernels and Earth orientation files |
| `raw.githubusercontent.com` | The gravity field and magnetic model |
| `hanspeterschaub.info` | Basilisk's backup for the support data; Vizard |
| `celestrak.org` | Newer space weather, only if you ask for it |

### Windows: "running scripts is disabled on this system"

PowerShell refuses to run `Activate.ps1`. Allow scripts you start
yourself, for your account only, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Starting the app

### Linux: `ImportError: libEGL.so.1` (or another `.so`) when the GUI starts

A minimal system is missing Qt's libraries. On Debian or Ubuntu:

```bash
sudo apt-get install libegl1 libopengl0 libxcb-cursor0 libgl1 libxkbcommon0
```

### The Results plot stays blank

The plots draw in an embedded web view (Qt WebEngine), which needs a few
more libraries on minimal Linux systems. On Debian or Ubuntu:

```bash
sudo apt-get install libnss3 libatk-bridge2.0-0 libgbm1
```

### The 3D model view says "WebGL is not supported", or stays blank

The 3D model editor draws with WebGL. The app already lets Chromium use
software rendering where there is no usable GPU (a virtual machine, a
remote desktop). If you set `QTWEBENGINE_CHROMIUM_FLAGS` yourself, the
app keeps exactly yours: add `--ignore-gpu-blocklist` to them. The model
still works without the view: the mass properties and facets are shown
in the tabs below it.

### "(not qualified)" after the Basilisk version in the status bar

A Basilisk version other than 2.12.0 is installed. Runs still work, but
outside what the app was verified against. To go back:
`pip install "bsk[all]==2.12.0"`.

## Reference data

### `FAIL  naif0012.tls: Support data file not found via pooch: ...`

`kernels-status` could not download a file, usually because there is no
internet (it tries NAIF first, then Basilisk's backup host). Connect once
and run `spacemissionstudio kernels-status` again, or install the files
from disk ([work offline](user-manual/reference-data.md#work-offline)).

### `ERROR: run failed: support-data file GGM03S.txt is not installed (...)`

The full message continues: "SpaceMissionStudio does not download during
a run: download it from the Reference data dialog (Settings > Reference
data, Download... > Support data) or with `spacemissionstudio
kernels-status`." Do one of those two, then run again. The dialog opens
from **Settings > Reference data** > **Reference Data...**, by clicking
the reference-data item in the status bar, or with **Reference Data...**
in the command palette (`Ctrl+K`).

### `Earth orientation: no IERS files installed -- the Earth-fixed frame is IAU_EARTH (about 160 m/day of error at 400 km); Settings > Reference data downloads them`

Explain (Scenario › Overview) shows this, and a run reports `Earth orientation: IAU
rotation model, no IERS data installed`. The measured Earth orientation
files are missing, so the run uses the simpler IAU model. Run
`spacemissionstudio earth-orientation --fetch`, or, in the **Reference
data** dialog (**Settings > Reference data** > **Reference Data...**),
**Download... > Earth orientation**.

## Running a scenario

### `ERROR: Basilisk is not installed/built (No module named 'Basilisk') -- see SpaceMissionStudio/README.md`

Or, in the GUI, Run says Basilisk is not installed. The GUI works without
Basilisk; runs need it. Activate your environment
(`source .venv/bin/activate`, or `.venv\Scripts\Activate.ps1` on Windows)
and run `pip install "bsk[all]==2.12.0"`. With an installer: reinstall
while connected to the internet.

### Run is not available

Look at the message at the bottom of the **Scenario** area: it names the
field to fix; the **Problems** panel (`Ctrl+J`) lists every problem. **✓ valid** means you can run.

### A run takes too long, or you started the wrong one

**Cancel** in the status bar (`Esc`, or **Cancel Run**) stops it
safely at the next checkpoint and keeps the results so far. It is not
instant. A Monte Carlo batch cannot be cancelled part way.

### A long run fills memory

Set **Record every** on the scenario tree's **Environment** page (for example 600 s).
Five years of LEO station keeping took about 50 minutes and 450 MB with
it.

### A run with script blocks is refused

```text
1 script_block(s) (...) run unrestricted Python from the scenario file. Read the code first, then pass --allow-scripts to run it.
```

The scenario's Mission Sequence contains Python code. Read it; if you
trust it, add `--allow-scripts` (the GUI asks instead).

## Scenario files

`spacemissionstudio validate` (and **Open...** (Ctrl+O)) name the problem:

| Message | Means |
|---|---|
| `INVALID: f.json: not valid JSON (Expecting property name enclosed in double quotes: line 1 column 3 (char 2))` | The file is not JSON; the position is given |
| `INVALID: f.json: spacecraft[0].dry_mass_kg: expected a number, got text` | A value has the wrong type; the field is named |
| `INVALID: my-sat: dry_mass_kg must be in (0, 1e6] -- if your intended value is outside this range, check for a units mixup (e.g. g instead of kg)` | A value is out of range |
| `INVALID: f.json: could not read file (No such file or directory)` | Wrong path |

`ccsds-import` refuses a message whose epoch differs from the scenario's:

```text
ERROR: the OPM state is at 2030-01-01T08:30:00 UTC, the scenario epoch is 2030-02-01T00:00:00; pass --set-epoch to move the scenario epoch to the OPM's
```

## Messages that are normal

| Message | Why |
|---|---|
| `INFO ... Logging to ~/.spacemissionstudio/logs/...log` | Every command says where its log file is |
| `INFO matplotlib.font_manager: ... generated new fontManager` | The first run builds a font cache, once |
| `WARNING: space weather uses MSFC's prediction (oct2026f10-prd.txt), 50th percentile F10.7 and Ap` | The run is past the end of the observed space-weather record, so drag uses NASA MSFC's prediction |
| `WARNING: past 2041-10 MSFC's last 132 months repeat (ESA AD10 Sec. 5.9)` | A long lifetime estimate runs past MSFC's prediction; its last solar cycle is repeated |
| `N: Download is performed unsandboxed as root, as file '.../spacemissionstudio_<version>_amd64.deb' couldn't be accessed by user '_apt'` | apt's notice when the `.deb` is in a folder its `_apt` user cannot read, such as your home folder. The install still succeeds. To avoid the notice, copy the `.deb` to `/tmp` and install it from there |

## Reporting a problem

Include:

- the log file named in the error dialog (in `~/.spacemissionstudio/logs/`);
- the versions, from **Settings > About** or
  `spacemissionstudio --version`;
- the scenario file, if you can share it.

The [FAQ](faq.md) answers questions that are not errors.

---

**Next:** [FAQ](faq.md) ·
[Getting started](getting-started.md) ·
[Documentation index](README.md)
