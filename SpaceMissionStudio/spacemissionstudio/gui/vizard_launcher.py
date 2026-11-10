#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""Starting the external Vizard application -- a separate, non-Python
Unity program -- for a user who chose one.

**SpaceMissionStudio does not download or look for Vizard** (2026-11-09,
the user's decision): the build AVS Lab publishes enables Unity Analytics,
which sends usage data to Unity. The 3D view built into the app
(Results › 3D View, ``gui.mission_view_widget``) shows a run with nothing
sent anywhere. A Vizard the user built or checked themselves can still be
used: they choose it (**Settings > Vizard > Browse...**, or **Browse...**
when it is needed), :func:`remember_vizard_executable` keeps it, and
:func:`find_vizard_executable` returns only that choice. A location inside
the folder the former download used (:data:`FORMER_DOWNLOAD_DIR`) is
ignored, so a copy downloaded by an earlier version is never started.

Feeding Vizard a run (a playback ``.bin`` file or a live stream) is
``engine.vizard``'s job, wired through ``SimulationService`` via
``gui.vizard_dialog.VizardRequest``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSettings

_SETTINGS_KEY = "vizard/executable_path"

# engine.vizard/SimulationService never overrides vizInterface's own
# reqComProtocol="tcp"/reqComAddress="0.0.0.0"/reqPortNumber="5556"
# defaults. In Basilisk 2.12.0 vizInterface *connects* to that address
# (it opens no port of its own outside broadcast mode; the "binds" wording
# in docs/source/Vizard/vizardAdvanced/vizardLiveComm.rst does not match
# the code -- security analysis S-06), so Vizard is the side that listens,
# here on the local machine. This is that address. Passed to
# :func:`launch_vizard`
# as its ``-directComm`` command-line argument (see
# docs/source/Vizard/vizardAdvanced/vizardCommandLine.rst) so Vizard
# connects automatically instead of sitting on its own manual "Load Data
# Using One of the Following" launcher screen waiting for the user to
# type this address in by hand and click "Start Visualization" --
# direct user feedback: a live-stream run appeared to "do nothing" and
# then froze with Abort having no effect, because Basilisk's
# InitializeSimulation() blocks (inside native C++, no Python-level
# hook -- see gui.main_window.MainWindow.on_run()'s own comment) waiting
# for exactly that handshake, which never arrived.
DEFAULT_LIVE_STREAM_ADDRESS = "tcp://localhost:5556"

# The actual launchable binary/bundle name Vizard's own Unity build
# produces per platform (see VizardDownload.rst's Vizard_<platform>.zip
# contents) -- used to search candidate directories.
if sys.platform.startswith("win"):
    _EXECUTABLE_NAME = "Vizard.exe"
else:
    _EXECUTABLE_NAME = "Vizard.x86_64"


#: Where SpaceMissionStudio up to 2.5.0 unpacked AVS Lab's Vizard when
#: asked to download it. A remembered location inside it is ignored.
FORMER_DOWNLOAD_DIR = Path.home() / ".cache" / "SpaceMissionStudio" / "vizard"


def _inside_former_download(path: Path) -> bool:
    try:
        path.resolve().relative_to(FORMER_DOWNLOAD_DIR.resolve())
    except (OSError, ValueError):
        return False
    return True


def find_vizard_executable(settings: QSettings | None = None) -> Path | None:
    """The Vizard the user chose, if it still exists and is not a copy the
    former download put in :data:`FORMER_DOWNLOAD_DIR`; else ``None``.
    Nothing is searched for."""
    settings = settings if settings is not None else QSettings()
    remembered = settings.value(_SETTINGS_KEY, "", type=str)
    if remembered:
        path = Path(remembered)
        if path.exists() and not _inside_former_download(path):
            return path
    return None


def remember_vizard_executable(path: Path, settings: QSettings | None = None) -> None:
    """Persists ``path`` so the next :func:`find_vizard_executable` call
    (in this run or a future one) returns it directly, without needing to
    guess or ask the user again.
    """
    settings = settings if settings is not None else QSettings()
    settings.setValue(_SETTINGS_KEY, str(path))


def remembered_vizard_executable(settings: QSettings | None = None) -> str:
    """The location remembered (Settings > Vizard), or "" when none is."""
    settings = settings if settings is not None else QSettings()
    return settings.value(_SETTINGS_KEY, "", type=str)


def forget_vizard_executable(settings: QSettings | None = None) -> None:
    """Forget the remembered location: Vizard is looked for in the usual places again."""
    settings = settings if settings is not None else QSettings()
    settings.remove(_SETTINGS_KEY)


def launch_vizard(executable_path: Path, direct_comm_address: str | None = None,
                  load_file: Path | None = None) -> subprocess.Popen[bytes]:
    """Starts Vizard as a background process and returns the
    :class:`subprocess.Popen` handle so the caller can poll whether it's
    still running (``.poll() is None``).

    Args:
        direct_comm_address: when given (typically
            :data:`DEFAULT_LIVE_STREAM_ADDRESS`), passed as Vizard's own
            ``-directComm <address>`` command-line argument (see
            ``docs/source/Vizard/vizardAdvanced/vizardCommandLine.rst``)
            so it connects to a live-stream automatically instead of
            sitting on its manual launcher screen -- see this module's
            own ``DEFAULT_LIVE_STREAM_ADDRESS`` comment for why. ``None``
            (the default) launches Vizard with no arguments, exactly as
            before.
        load_file: a playback file Vizard opens at start (its ``-loadFile``
            argument, ``vizardCommandLine.rst``): the Results tab's "Open in
            Vizard" for the last run's file.
    """
    args = [str(executable_path)]
    if direct_comm_address:
        args += ["-directComm", direct_comm_address]
    if load_file is not None:
        args += ["-loadFile", str(load_file)]
    return subprocess.Popen(args)  # noqa: S603 -- argument list, no shell; the user's chosen Vizard executable
