# Packaging

This directory covers packaging SpaceMissionStudio into a real, installable,
out-of-the-box application for both Linux and Windows -- not just a
`pip install` a developer runs from a terminal. Two tiers exist for each
platform:

1. **A double-click installer** -- a `.deb` package on Linux
   (`build_deb.sh`), an Inno Setup wizard on Windows
   (`windows/spacemissionstudio.iss`). Both are self-contained: they carry
   a private Python 3.14 with Basilisk, SpaceMissionStudio, every Python
   package and the reference data (`bundle_python.py`, below). Installing
   needs no Python on the computer, no terminal and no internet: install,
   get a menu entry, click it.
2. **The scriptable install path** (`build_wheel.sh`/`install.sh` and
   their `.ps1` counterparts): installs from a checkout into a virtual
   environment made with the computer's own Python, downloading Basilisk
   and the packages from PyPI. For anyone who would rather script an
   install, and for Linux on ARM (aarch64), which has no installer.

**Basilisk version:** the installers bundle `bsk[all]==2.12.0`, the
version SpaceMissionStudio is qualified with
(`spacemissionstudio/dependencies.py`; `bundle_python.py`'s
`BASILISK_REQUIREMENT`). Change both together; `tests/test_dependencies.py`
fails when they differ.

## Closed-off/offline policy -- the kernel pre-fetch step

Real user requirement: "the app must be completely closed off and offline,
only exception is the installation process." SpaceMissionStudio itself makes
no network calls at runtime -- see `../spacemissionstudio/engine/kernels.py`'s
own "Closed-off/offline policy" docstring -- but it still depends on
Basilisk's SPICE/gravity-harmonics/magnetic-field support data, which
`engine.kernels.require_kernels()` normally fetches (via Basilisk's own
`pooch`-backed cache) the first time a scenario that needs a given file is
run. Deferring that first fetch to the user's first real run would violate
the offline policy, so:

* **The `.deb` and the Windows setup program** carry the data: every file
  of ALL_SUPPORT_DATA_FILES (SPICE kernels, gravity fields, the magnetic
  field model, albedo maps; 117 MB) and the Earth orientation files
  (36 MB) are fetched when the installer is BUILT, by `bundle_python.py`,
  and installed with it. The installing computer downloads nothing.
* **`install.sh`** / **`install.ps1`** call `engine.kernels.require_kernels()`
  once, right after SpaceMissionStudio is installed into the venv, and
  only when a Basilisk wheel was also given
  (`--basilisk-wheel`/`-BasiliskWheel`); non-fatal (a missing Basilisk
  build already means Run/Monte Carlo won't work) -- they print a status
  line either way, so the user knows whether a later `spacemissionstudio
  kernels-status` run (WITH internet access) is still needed.

Every later lookup then resolves from the installed files (or, for the
install scripts, Basilisk's own local cache), with no network touched at
all -- the install-time fetch is the first of two allowed exceptions to
the offline policy.

The second, relaxed later by a real user decision ("a one time fetch during
each startup of the app is also allowed, to store everything that is needed
locally so it can be used later again. But the user always should be asked if
they want to fetch/update"): each time the GUI starts, a **Fetch or
update reference data?** card on Home (`gui.startup_fetch_dialog.ReferenceDataCard`)
offers to re-check/refresh the same support-data kernels (a safety net
for a dev checkout or a cleared cache -- normally a no-op, since the
installer above already did this) and, separately, to fetch real
space-weather history from CelesTrak and the Earth orientation files
from NAIF.
None of them ever runs without the user clicking **Fetch now** first;
clicking **Not now** touches no network, same as before this existed. This is a GUI-only concern -- nothing
in `packaging/` needed to change for it.

## What's here

* **`bundle_python.py`** -- builds the private Python both installers
  ship (see "The bundled Python" below).

* **`release_notes.py`** -- writes the notes of a release draft from its
  CHANGELOG section and its built files; the release workflow runs it
  (`docs/developer/releasing.md`).

* **`build_wheel.sh`** -- builds `spacemissionstudio`'s own wheel + sdist
  (`python -m build`). Genuinely run here: `dist/spacemissionstudio-<version>-py3-none-any.whl`
  was built, installed into a throwaway venv, and its CLI entry point
  (`spacemissionstudio validate ...`) and GUI (`spacemissionstudio.gui.main_window.MainWindow`,
  constructed headless) were both exercised against the INSTALLED copy,
  not the checkout.

  A real bug was caught doing this: `spacemissionstudio/scenarios/*.json` (the
  two-body validation scenario) was silently missing from the built wheel,
  because `setuptools.packages.find()` only picks up Python packages
  (directories with `__init__.py`), and `scenarios/` has none. Fixed via
  `pyproject.toml`'s `[tool.setuptools.package-data]` -- re-verified by
  rebuilding and confirming the file is now present in the wheel and
  loadable from the installed copy.

  A second real bug was caught running this script TWICE in a row:
  `python -m build`'s own temp output directory (`./build/`, gitignored)
  is left behind after a run, and because Python inserts the current
  directory at the front of `sys.path` for both `-c` and `-m` invocations,
  that leftover directory silently SHADOWED the real installed `build`
  package on the next run (`ModuleNotFoundError`-adjacent: `No module
  named build.__main__`). Fixed by having the script clean `./build/`
  before it starts, and by checking installedness with `pip show build`
  instead of `python -c "import build"` (which was itself vulnerable to
  the same shadowing). Re-verified by running the script twice
  back-to-back after the fix.

* **`install.sh`** -- an end-user installer: creates a private venv,
  builds (or accepts) a spacemissionstudio wheel and installs it with the
  `gui` extra, optionally installs a vendored Basilisk wheel into the same
  venv (`--basilisk-wheel PATH_OR_URL`), writes a `spacemissionstudio` launcher
  script, and installs a `~/.local/share/applications/spacemissionstudio.desktop`
  entry (skippable with `--no-desktop-entry`). **Verified for 1.0.0**
  (2026-10-14, Ubuntu 24.04 container, Python 3.11, a fresh `$HOME`):
  `install.sh --basilisk-wheel "bsk[all]==2.12.0"` with the 1.0.0 wheel
  installed every pinned version of `constraints.txt` (bsk 2.12.0, numpy,
  PySide6, plotly, sgp4, pyerfa as listed), pre-fetched the support data
  and the Earth orientation files, and wrote the launcher, the desktop
  entry and the icon. The launcher reported 1.0.0 with Basilisk 2.12.0,
  validated all 28 templates, ran templates 01, 16 and 28, and ran the
  Monte Carlo template 09's 20 runs.

* **`constraints.txt`** -- the exact version of every package the
  installers ship; **`constraints-dev.txt`** -- the exact versions of the
  tools CI runs (pytest and its plugins, ruff, pip-audit, pre-commit).
  CI's `test` job checks both against the advisory databases
  (`pip-audit --no-deps`) and fails on a known vulnerability.

* **`spacemissionstudio.desktop.in`** -- the desktop-entry template `install.sh`
  fills in (`@INSTALL_PREFIX@` -> the venv's parent directory).
  `Icon=spacemissionstudio` now resolves to a real icon: `install.sh` renders
  `gui/icons.py`'s procedurally-drawn app icon (QPainter, no bitmap asset
  in the repo -- see that module's docstring) to
  `$XDG_DATA_HOME/icons/hicolor/256x256/apps/spacemissionstudio.png` (the
  standard hicolor icon theme location) right after writing the desktop
  entry, using the `offscreen` Qt platform plugin so no display is needed
  even on a headless install. Non-fatal if it fails (e.g. no Qt platform
  plugins present at all) -- the desktop entry still installs, just with
  the icon theme's generic fallback.

## The real installers

**Release files in CI.** `.github/workflows/spacemissionstudio-release.yml`
builds the release files of a tag (`spacemissionstudio-vX.Y.Z`) on
GitHub's runners and attaches them to its release, a draft when the
release does not exist yet (`docs/developer/releasing.md`, sections 5
and 6):

| Platform | Files | Installed and run in the workflow |
|---|---|---|
| Linux (x86_64, `ubuntu-24.04`) | wheel, sdist, `.deb`, `SHA256SUMS-linux` | `dpkg -i` of the `.deb` with the network cut off (`unshare --net`), then as the runner's user, still offline and with an empty support-data cache: `--version`, `kernels-status`, every template validated, template 01 run from the bundled kernels, the Earth orientation files found, the main window opened in Inter |
| Windows (x64, `windows-latest`) | the setup program (the bundled Python with that wheel), `SHA256SUMS-windows` | silent install (`/VERYSILENT /CURRENTUSER`); with an empty support-data cache, the same checks with one template |

macOS is not supported (removed on 2026-10-21 by the user's decision). The workflow's files are
built on the runners, so their checksums differ
from a local build of the same commit; the checksums on a release are
those in its `SHA256SUMS-*` files. 1.0.0 was built locally, before the
workflow existed. 1.1.0 was built and checked locally ("Verified for
1.1.0" below), but its published files are the workflow's builds from the
tag, with the checksums of its `SHA256SUMS-*` files (SRelD).

### The `.deb` package (Linux)

`build_deb.sh` produces `spacemissionstudio_<version>_amd64.deb`, a
self-contained Debian/Ubuntu package:

- `/opt/spacemissionstudio/python`: the bundled Python (`bundle_python.py`
  with `--prefix /opt/spacemissionstudio/python`), with Basilisk, the
  wheel, every package, the support data and the Earth orientation files;
- `/usr/bin/spacemissionstudio`: a launcher that runs that Python
  isolated (`-I -m spacemissionstudio.cli`);
- the desktop entry, and the menu icon, rendered from `gui/icons.py` when
  the package is built.

Every file is a package file, so dpkg removes them all. `postinst` only
removes the virtual environment packages up to 1.1.0 created and updates
the desktop and icon caches; it downloads nothing. `Depends` lists the
X11, OpenGL, font and sound libraries Qt loads from the system (a desktop
has them) and glibc 2.34 or newer (PySide6 6.11's wheels are
`manylinux_2_34`): Ubuntu 22.04, Debian 12 or later.

**Verified for the self-contained package:** see "The bundled Python"
below for what was measured.

The two sections below record the earlier, venv-based package (up to
1.1.0), which needed a system Python 3.11 and internet access during
`apt install`.

**Verified for 1.1.0** (2026-10-20, Ubuntu 24.04 container, Python
3.11, as root), with the files built from a clean checkout of commit
`1db38b521` (the release records with UI overhaul M1, SRelD issue 8).
This section was written after the build; this file is in neither the
wheel nor the sdist, so the files match the commit that records them:

- `build_wheel.sh` and `build_deb.sh` built
  `spacemissionstudio-1.1.0-py3-none-any.whl`, the sdist and
  `spacemissionstudio_1.1.0_all.deb`. The wheel holds the five font
  files, their two OFL texts, the 35 Lucide icons and Lucide's licence,
  and no IBM Plex file. Their SHA-256:

  ```
  28de266c634df2578427900e13ebfb29108c29a835909c148cb9f72ea6d1f253  spacemissionstudio-1.1.0-py3-none-any.whl
  48f726c51fff1bfafc64ad60317cdeca8b94f624d595911a55b98f932332eabe  spacemissionstudio-1.1.0.tar.gz
  09dbc7d8454e42de2590ed172c3c641945dd0b38536fe6f417ef141478289bbe  spacemissionstudio_1.1.0_all.deb
  ```
- **Upgrade from 1.0.0:** the published 1.0.0 package, downloaded from
  its GitHub release and checked against its `SHA256SUMS-linux`, was
  installed first on a purged system (it reported 1.0.0). Then `apt-get
  install -y ./spacemissionstudio_1.1.0_all.deb` reported "Unpacking
  spacemissionstudio (1.1.0) over (1.0.0)". `postinst` rebuilt
  `/opt/spacemissionstudio/venv` with `bsk[all]==2.12.0` and the bundled
  wheel.
- The installed tool (`/usr/bin/spacemissionstudio`):
  - `--version` gave SpaceMissionStudio 1.1.0 and Basilisk 2.12.0, and
    `kernels-status` found all nine support files;
  - all 31 templates validated;
  - templates 01 and 22 ran, and 22's `provenance.json` records 1.1.0;
  - the Monte Carlo template 09 (20 runs, one thread) ran through the
    GUI's `MonteCarloWorker` from the installed package, offscreen: no
    failed run, 20 run files (K-18);
  - the GUI started (offscreen) with Inter at 13 px as its font, Inter and
    JetBrains Mono registered and the Run icon drawn; with the start-up
    data prompt skipped, the dark theme applied live in 0.37-0.42 s with
    no style-sheet warning, and the window stayed up for 25 s.
- Not done for 1.1.0: an install by hand on a desktop, with the app
  opened from the application menu.

**Verified for 1.0.0** (2026-10-14, Ubuntu 24.04 container, Python
3.11, as root):

- `build_wheel.sh` and `build_deb.sh` built
  `spacemissionstudio-1.0.0-py3-none-any.whl`, the sdist and
  `spacemissionstudio_1.0.0_all.deb`.
- `apt install ./spacemissionstudio_1.0.0_all.deb` completed: `postinst`
  created `/opt/spacemissionstudio/venv`, installed `bsk[all]==2.12.0`
  from PyPI and the bundled wheel, pre-fetched the support data and the
  Earth orientation files, and wrote `/usr/bin/spacemissionstudio` and
  the desktop entry.
- The installed tool: `--version` gave SpaceMissionStudio 1.0.0 and
  Basilisk 2.12.0; `kernels-status` found every kernel; all 28 templates
  validated; templates 01 and 22 ran (22's `provenance.json` records
  1.0.0); the Monte Carlo template 09 ran its 20 runs; the GUI started
  (offscreen) and stayed up.
- Not done for 1.0.0: an install by hand on a desktop, with the app
  opened from the application menu.

Uninstalling (`apt remove`/`apt purge spacemissionstudio`) removes
everything: the package's own files, and whatever else is left under
`/opt/spacemissionstudio` (`postrm`: bytecode Python wrote when the tool
was run as root, or a venv left by a package up to 1.1.0).

**Coming from 3.0.0** (the earlier numbering): apt sees 1.0.0 as older.
Tried on 2026-10-14: over an installed 3.0.0 `.deb`, `apt-get install -y
./spacemissionstudio_1.0.0_all.deb` refused the downgrade ("Packages were
downgraded and -y was used without --allow-downgrades"); after `apt
remove spacemissionstudio` the same command installed 1.0.0, which then
reported 1.0.0 with Basilisk 2.12.0.

**The published 1.0.0 files.** The final wheel, sdist and `.deb` were
rebuilt from the release commit `f288e0c73` and the `.deb` installed
again (it reported 1.0.0 with Basilisk 2.12.0, validated the 28
templates and ran template 01). Those are the files attached to the
[1.0.0 release](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/tag/spacemissionstudio-v1.0.0):
GitHub's SHA-256 digest of each attached file equals the built file's
(`SHA256SUMS-linux`).

### The Windows installer (Inno Setup)

`windows/spacemissionstudio.iss` is an [Inno Setup](https://jrsoftware.org/isinfo.php)
script producing `spacemissionstudio-<version>-setup.exe`: a wizard --
Welcome, licence, install location, Install, an optional "launch now"
checkbox on Finish. It is self-contained: it installs the bundled Python
(`bundle_python.py`, with Basilisk, the wheel, every package, the support
data and the Earth orientation files) to `{app}\python`, so the computer
needs no Python and no internet. It installs per user (`{localappdata}`,
no administrator rights) and creates a Start Menu entry (plus an optional
desktop shortcut) that starts the GUI with `pythonw.exe -I` (no console
window). Two hidden steps after copying the files: the bytecode is
compiled for the folder chosen, and the Earth orientation manifest is
pointed at it. An upgrade first removes the previous `python` folder and
what setups up to 1.1.0 left (`venv`, `dist`, `bootstrap_env.ps1`,
`constraints.txt`); uninstalling removes `{app}\python`.

Building it (on Windows, with Inno Setup 6 and Python 3.14 or later
installed, and internet access):

```powershell
cd SpaceMissionStudio
powershell -File packaging\build_wheel.ps1 packaging\windows\dist
python packaging\bundle_python.py --platform windows --dest packaging\windows\python --wheel (Get-ChildItem packaging\windows\dist\spacemissionstudio-*.whl).FullName
ISCC packaging\windows\spacemissionstudio.iss
```

**Built and installed in CI.** The workflow
`.github/workflows/spacemissionstudio-windows-installer.yml` does this on
a Windows runner. Started by hand, it bundles the wheel attached to a
release, checked against that release's `SHA256SUMS-linux`; a push
bundles a wheel built from the pushed commit, since the release it
belongs to may not exist yet. It compiles the script with Inno
Setup, then installs the program silently (`/VERYSILENT /CURRENTUSER`).
It then runs the installed tool with an empty support-data cache:
import, `kernels-status`, `validate`, a run of template 01 from the
bundled kernels, and the Earth orientation files found. The setup program, its checksum
(`SHA256SUMS-windows`) and the install log are the run's artifact. Run
it from the Actions tab ("SpaceMissionStudio Windows installer", with the
release tag); with "attach" ticked, a separate job, the only one with
write access, also uploads the setup program and `SHA256SUMS-windows` to
the release, replacing earlier copies. A push to `packaging/windows/`,
`bundle_python.py` or `constraints.txt` builds and tests without
attaching. It first passed on
2026-10-12 ([run 38315713727](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/runs/38315713727)). Not yet done: the wizard clicked
through by hand, and the GUI opened from the Start Menu shortcut, on a
real Windows 10/11 machine.

## Windows support (the scriptable install path)

Not the Inno Setup wizard above -- this is `build_wheel.ps1`/`install.ps1`,
the Windows counterpart of `build_wheel.sh`/`install.sh` (tier 2 from the
top of this file: scriptable, for anyone who'd rather not use a GUI
installer). Direct PowerShell ports --
same steps, same flags (`-Prefix`/`-BasiliskWheel`/`-SpaceMissionStudioWheel`/`-NoShortcut`
instead of `--prefix`/`--basilisk-wheel`/`--spacemissionstudio-wheel`/
`--no-desktop-entry`), same two already-verified bugs from the Linux
side pre-emptively fixed (the `scenarios/*.json` package-data glob is in
`pyproject.toml`, platform-independent; the stale-`./build/`-directory
shadowing fix is ported into `build_wheel.ps1` unchanged, since it's
about `python -m build`'s own behavior, not the shell). Windows'
equivalent of a `.desktop` entry is a Start Menu shortcut (`.lnk`),
created via the standard `WScript.Shell` COM object at
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\SpaceMissionStudio.lnk`.

**Honesty note, matching this project's own discipline elsewhere:**
these two scripts have NOT been run against a real Windows 11 machine --
this development sandbox is Linux-only, with no Windows environment
available at any point in this project's history. They were written
against documented, standard PowerShell/`venv`/`pip`/`WScript.Shell`
behavior and against `build_wheel.sh`/`install.sh`'s own
already-verified logic (matched step-for-step), and reviewed for syntax
by hand since no `pwsh`/`powershell.exe` was available in this sandbox
to actually execute them either -- but "written carefully" is not the
same claim as "run and confirmed working" that the rest of this
directory makes for the Linux scripts. One specific, known gap: the
Start Menu shortcut does not get a custom icon (`gui/icons.py`'s
`ensure_icon_file()` always writes PNG data -- see that function's own
docstring -- and a `.lnk`'s `IconLocation` needs a real `.ico`/`.exe`/
`.dll`; rather than ship an icon file that wouldn't actually resolve,
the shortcut just uses `spacemissionstudio.exe`'s own embedded icon). If you
run these on a real Windows 11 machine, please report anything that
doesn't work as documented here.

What *is* run on Windows: the application itself. CI installs it with
`pip` on GitHub's `windows-latest` runner, with Basilisk 2.12.0 and the
reference data, and runs the full test suite there on every change
(`.github/workflows/spacemissionstudio.yml`, job `platforms`), and the
setup program is built, installed and run in CI (above). Only these two
scripts are unrun.

## The bundled Python (`bundle_python.py`)

Both installers carry the same kind of folder, built by
`bundle_python.py` on the platform the installer is for (pip installs
that platform's binary wheels):

1. **CPython 3.14.8** from python-build-standalone release 20261013,
   the relocatable `install_only_stripped` build (`PYTHON_BUILDS`). The
   archive is checked against its pinned SHA-256 before it is unpacked;
   a mismatch stops the build.
2. **Basilisk and the app:** `bsk[all]==2.12.0`, then the wheel with its
   `gui` extra, both with `constraints.txt`, by the bundled Python's own
   pip run isolated (`-I`), so nothing from the build machine's user
   site-packages gets in.
3. **The reference data:** Basilisk's own checked fetch of every file in
   `engine.kernels.ALL_SUPPORT_DATA_FILES` into an empty cache, moved to
   `site-packages/supportData`, the folder Basilisk's
   `dataFetcher.find_local_support_data()` reads before its download
   cache; then the Earth orientation files into
   `earth_orientation.SYSTEM_DIR` (`share/spacemissionstudio/earth_orientation`).
   Both made world-readable (pooch writes 0600).
4. **An offline check:** with sockets refused and an empty download
   cache, every support file must resolve to the bundle and the Earth
   orientation files must be found; otherwise the build stops.
5. **With `--prefix`** (the `.deb`): the bytecode is recompiled as if at
   that folder (tracebacks name the installed files) and the Earth
   orientation manifest's paths are pointed there. The Windows setup
   program does both at install time, for the folder chosen.
6. **`SPACEMISSIONSTUDIO_RUNTIME.json`** in the folder records the CPython
   archive and its SHA-256, the Python, SpaceMissionStudio and PySide6
   versions, every installed package (`pip list --format=freeze`) and
   every data file with its size and SHA-256.

The data is as current as the build: the Earth orientation files carry
data up to their last datum (`earth-orientation` status, the **Reference
data** dialog). A user's own newer download goes to their cache and is
used first; the installed copy is never changed.

Licences of everything the folder contains:
[`docs/THIRD_PARTY_ASSETS.md`](../docs/THIRD_PARTY_ASSETS.md), "In the
installers".

**Verified on Linux (2026-10-20, Ubuntu 24.04 container, as root to
install and as an ordinary user to run),** with the package built from
the working tree of the commit that adds this section, before this
section was written (this file is not in the package; the version in
its files is still 1.1.0):

- `build_deb.sh` took 6.6 minutes (CPython archive already downloaded)
  and built `spacemissionstudio_1.1.0_amd64.deb`: 446,990,484 bytes,
  `Installed-Size` 1,654,980 KiB, 41 packages and 14 data files in
  `SPACEMISSIONSTUDIO_RUNTIME.json`.
- **Upgrade over the venv-based package:** with the earlier 1.1.0 `_all`
  package installed, `unshare --net dpkg -i` (no network) unpacked the
  new package over it in 25 s. `postinst` removed
  `/opt/spacemissionstudio/venv`; the old wheel and `constraints.txt` went
  with the old package, and dpkg took over `/usr/bin/spacemissionstudio`
  and the icon.
- **Purge and fresh install:** `dpkg --purge` left no
  `/opt/spacemissionstudio`, launcher or icon. `unshare --net dpkg -i`
  then installed the package with no network.
- **Run offline as an ordinary user** (`unshare --net su <user>`, an
  empty `HOME` and `BSK_SUPPORT_DATA_CACHE` pointing at an empty folder):
  `--version` gave SpaceMissionStudio 1.1.0, Basilisk 2.12.0, Python
  3.11.17; `kernels-status` found all nine support files in the bundle;
  all 31 templates validated; templates 01 and 22 ran, 22's
  `provenance.json` naming the bundled SPICE kernels and `GGM03S.txt`
  and the ITRF93 Earth frame; the Earth orientation files were found; the
  main window opened (offscreen) in Inter. Nothing was downloaded: no
  Basilisk cache was created.
- Not done: an install by hand on a desktop, with the app opened from the
  menu; a Debian 12 or Ubuntu 22.04 machine.

**Verified on Windows (2026-10-20, `windows-latest`, the release
workflow's pull-request run for this change,
[run 39504407640](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/actions/runs/39504407640)):**
`bundle_python.py --platform windows` built the bundle in the runner's
short temporary folder; Inno Setup compiled it in 143 s into
`spacemissionstudio-1.1.0-setup.exe` (about 395 MB); the silent install
(`/VERYSILENT /CURRENTUSER`) took 72 s. With an empty support-data cache
the installed tool reported 1.1.0, `kernels-status` found all nine files
in `{app}\python\Lib\site-packages\supportData`, template 01 validated
and ran from them, the Earth orientation files were found (the run's
note: "high accuracy until 2026-12-28"), and the main window opened
(offscreen) in Inter. The Windows installer workflow passed the same
checks on the push. Not done: the wizard clicked through by hand, on a
real Windows 10/11 machine (this sandbox has no Windows).

---

**Next:** [Getting started](../docs/getting-started.md) ·
[Documentation index](../docs/README.md)
