# Packaging

This directory covers packaging SpaceMissionStudio into a real, installable,
out-of-the-box application for both Linux and Windows -- not just a
`pip install` a developer runs from a terminal. Two tiers exist for each
platform:

1. **A real double-click installer** -- a `.deb` package on Linux
   (`build_deb.sh`), an Inno Setup wizard on Windows
   (`windows/spacemissionstudio.iss`). No terminal, no typed `pip`/`venv`
   commands for the end user: install, get a menu entry, click it, done.
2. **The scriptable install path** (`build_wheel.sh`/`install.sh` and
   their `.ps1` counterparts) these installers are themselves built on
   top of -- still useful directly for anyone who'd rather script an
   install or doesn't want a system-wide package manager entry.

**Basilisk version:** the installers pin `bsk[all]==2.12.0`, the version
SpaceMissionStudio is qualified with (`spacemissionstudio/dependencies.py`).
Change both together.

**A real update, made while building the `.deb` installer above:** this
development sandbox's Basilisk story has changed since earlier sections
of this file (and `../HISTORY.md`) were written. `pip install "bsk[all]"`
(Basilisk's own published PyPI wheel) now genuinely installs here --
confirmed directly, not assumed, by actually running it and then running
a real Basilisk build's `printBuildInfo()`. What's STILL blocked in this
sandbox specifically is network access to the NAIF SPICE kernel host
(`naif.jpl.nasa.gov`) and its backup mirror, needed for an actual
simulation RUN past kernel loading -- a narrower, later gap than "no
Basilisk at all". See "The `.deb` package" below for exactly what this
made possible to verify end-to-end for the first time.

## Closed-off/offline policy -- the kernel pre-fetch step

Real user requirement: "the app must be completely closed off and offline,
only exception is the installation process." SpaceMissionStudio itself makes
no network calls at runtime -- see `../spacemissionstudio/engine/kernels.py`'s
own "Closed-off/offline policy" docstring -- but it still depends on
Basilisk's SPICE/gravity-harmonics/magnetic-field support data, which
`engine.kernels.require_kernels()` normally fetches (via Basilisk's own
`pooch`-backed cache) the first time a scenario that needs a given file is
run. Deferring that first fetch to the user's first real run would violate
the offline policy, so all four installers below now call
`engine.kernels.require_kernels()` (with its default, ALL_SUPPORT_DATA_FILES,
covering every SPICE/gravity/magnetic-field file this app's code paths read)
once, right after spacemissionstudio itself is installed into the venv:

* **`install.sh`** / **`install.ps1`** -- only when a Basilisk wheel was
  also given (`--basilisk-wheel`/`-BasiliskWheel`); non-fatal (a missing
  Basilisk build already means Run/Monte Carlo won't work, so a failed
  pre-fetch here doesn't change that) -- prints a status line either way so
  the user knows whether a later `spacemissionstudio kernels-status` run
  (WITH internet access) is still needed before their first real run.
* **`deb/DEBIAN/postinst`** / **`windows/bootstrap_env.ps1`** -- always (both
  always install a real Basilisk build into the venv they create), so a
  failure here is FATAL, matching how both scripts already treat the
  Basilisk/spacemissionstudio install steps themselves: a scenario that can
  never actually run without its own kernels is exactly the kind of
  "configured but broken" state these installers should refuse to ship,
  not silently produce.

Every later `get_path()` call for the rest of that install's lifetime then
resolves from Basilisk's own local cache, with no network touched at all --
this install-time pre-fetch is the first of two allowed exceptions to the
offline policy.

The second, relaxed later by a real user decision ("a one time fetch during
each startup of the app is also allowed, to store everything that is needed
locally so it can be used later again. But the user always should be asked if
they want to fetch/update"): the GUI's `gui.startup_fetch_dialog` shows a
consent prompt once each time it starts, offering to re-check/refresh the
same support-data kernels (a safety net for a dev checkout or a cleared
cache -- normally a no-op, since the installer above already did this) and,
separately, to fetch real space-weather history from CelesTrak. Neither ever
runs without the user clicking "Fetch now" first; clicking "Skip" touches no
network, same as before this existed. This is a GUI-only concern -- nothing
in `packaging/` needed to change for it.

## What's here

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

### The `.deb` package (Linux)

`build_deb.sh` produces `spacemissionstudio_<version>_all.deb` -- a real
Debian/Ubuntu package. It bundles SpaceMissionStudio's own wheel (built the
same way `build_wheel.sh` always has) plus a small set of maintainer
scripts (`deb/DEBIAN/postinst`/`prerm`/`postrm`) and a desktop entry
(`deb/usr/share/applications/spacemissionstudio.desktop`); it does NOT bundle
Basilisk itself (see "The vendoring decision" below for why not) --
`postinst` creates a dedicated virtualenv at `/opt/spacemissionstudio/venv`
and pip-installs `bsk[all]` there the moment the package is configured
(`apt install`/`dpkg -i`'s normal "configure" step), which needs
internet access on the installing machine.

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

Uninstalling (`apt remove`/`apt purge spacemissionstudio`) also removes
the venv and the rendered icon (`postrm`): they are created at configure
time and are not part of the package's tracked files.

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
script producing `spacemissionstudio-<version>-setup.exe`: a real wizard --
Welcome, license, install-location, Install, an optional "launch now"
checkbox on Finish -- built on the exact same idea as the `.deb` above
(bundle SpaceMissionStudio's own wheel, create a venv, pip-install `bsk[all]`
at install time) via a companion script (`windows/bootstrap_env.ps1`)
the installer's `[Run]` step invokes. It checks for a working `python`
on `PATH` before the wizard even starts, and guides the user to
python.org (rather than failing silently) if none is found. Installs
per-user (`{localappdata}`, no admin/UAC prompt needed), and creates a
Start Menu entry (plus an optional desktop shortcut) that launches the
GUI directly via `pythonw.exe` (no console-window flash).

Building it (on a real Windows machine, with Inno Setup installed):

```powershell
cd SpaceMissionStudio
powershell -File packaging\build_wheel.ps1 packaging\windows\dist
ISCC packaging\windows\spacemissionstudio.iss
```

**Built and installed in CI.** The workflow
`.github/workflows/spacemissionstudio-windows-installer.yml` does this on
a Windows runner. Started by hand, it bundles the wheel attached to a
release, checked against that release's `SHA256SUMS-linux`; a push
bundles a wheel built from the pushed commit, since the release it
belongs to may not exist yet. It compiles the script with Inno
Setup, then installs the program silently (`/VERYSILENT /CURRENTUSER`).
It then runs the installed tool: import, `kernels-status`, `validate`,
and a run of template 01. The setup program, its checksum
(`SHA256SUMS-windows`) and the install log are the run's artifact. Run
it from the Actions tab ("SpaceMissionStudio Windows installer", with the
release tag); with "attach" ticked, a separate job, the only one with
write access, also uploads the setup program and `SHA256SUMS-windows` to
the release, replacing earlier copies. A push to `packaging/windows/`
or `constraints.txt` builds and tests without attaching. It first passed on
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
(`.github/workflows/spacemissionstudio.yml`, job `platforms`). Only the
installer and these two scripts are unrun.

## The vendoring decision (why Basilisk isn't bundled inside the installers)

Flagged since Phase 0's README: **vendor a prebuilt Basilisk wheel pinned
to a specific release/commit** as the default install path for end users,
keeping "build Basilisk from source" a documented, opt-in developer path
only. Building from source in an automated/sandboxed context is fragile
-- this project hit exactly that failure mode (a Conan Center network
block) before Phase 0 even started, and that specific block is STILL true
of this development sandbox today.

That's no longer the whole picture, though (corrected here, since an
earlier revision of this section conflated "can't build Basilisk from
source" with "no Basilisk wheel available at all" -- they turned out to
be two different things): AVS Lab already publishes Basilisk's wheel to
PyPI (`pip install "bsk[all]"`), and PyPI IS reachable from this
sandbox -- confirmed directly while building the `.deb` package above,
not assumed. So "vendor a Basilisk wheel" no longer needs a from-source
build at all; every installer in this directory (`install.sh`/`.ps1`,
the `.deb`, the Inno Setup installer) gets Basilisk the same simple way:
`pip install "bsk[all]"` at install time, needing only ordinary internet
access, not a Basilisk build toolchain anywhere.

What's genuinely still NOT done here: actually bundling a Basilisk
`.whl` FILE inside an installer (so install works fully offline, with no
PyPI access needed at all) -- `pip download "bsk[all]"` would produce
one, but doing that for every dependency, embedding the result, and
testing the fully-offline path is real, separate follow-on work, not
attempted blind here. `install.sh`/`install.ps1`'s `--basilisk-wheel`/
`-BasiliskWheel` flag already accepts a local `.whl` file for exactly
this purpose whenever someone does produce one (a pinned/older release,
a custom build, or an offline bundle) -- that RECEIVING end was already
built and (on Linux) verified; only producing the bundled file itself is
the open item.

## Producing a full offline installable bundle

Not built yet: the natural next step, now that "the vendored Basilisk
wheel" is just `pip download "bsk[all]"` away (see above), is doing
exactly that -- plus SpaceMissionStudio's own dependencies -- into a local
directory (`--no-deps` per package, or a `requirements.txt` with hashes)
so `install.sh`/the `.deb`/the Windows installer can all run fully
offline, with no PyPI access needed at install time. Flagged here rather
than attempted blind, per this project's "don't fabricate what can't be
verified" discipline -- the pieces (a bundled SpaceMissionStudio wheel, a
working `--basilisk-wheel`/`-BasiliskWheel` receiving end) are already
in place; only the "download everything into one bundle" step is
missing.

---

**Next:** [Getting started](../docs/getting-started.md) ·
[Documentation index](../docs/README.md)
