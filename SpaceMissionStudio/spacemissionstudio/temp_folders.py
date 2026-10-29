#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
"""The temporary folders SpaceMissionStudio makes, and the removal of
those a process left behind (audit R14).

A folder is removed when its process exits normally (``TemporaryDirectory``
and ``atexit`` see to it), but not when the process is killed or crashes:
the audit found hundreds of plot and Compare folders in the temporary
folder. Each name now carries the process id (``spacemissionstudio-plot-
<pid>-<random>``), so :func:`remove_left_behind` can tell a folder whose
process has ended from one still in use, and the GUI calls it at start.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

#: The name prefixes of the folders made here; each name continues with
#: ``<pid>-`` and ``tempfile``'s random part.
PLOT_PAGE = "spacemissionstudio-plot-"
COMPARE_PAGE = "sms-compare-"
MODEL_VIEW_PAGE = "spacemissionstudio_model_view_"
ICONS = "spacemissionstudio-icons-"
VIZARD_MODELS = "spacemissionstudio_vizard_models_"
KINDS = (PLOT_PAGE, COMPARE_PAGE, MODEL_VIEW_PAGE, ICONS, VIZARD_MODELS)

#: A folder named before the process id was in the name cannot be traced
#: to its process; it is removed once it has not changed for this long.
UNTRACED_AGE_S = 86_400.0  # [s] one day


def _prefix(kind: str) -> str:
    return f"{kind}{os.getpid()}-"


def temporary_directory(kind: str) -> tempfile.TemporaryDirectory:
    """A ``TemporaryDirectory`` of ``kind``, removed when it is cleaned up,
    garbage-collected or the process exits."""
    return tempfile.TemporaryDirectory(prefix=_prefix(kind))


def folder_removed_at_exit(kind: str) -> Path:
    """A new folder of ``kind``, removed when the process exits."""
    folder = Path(tempfile.mkdtemp(prefix=_prefix(kind)))
    atexit.register(shutil.rmtree, folder, True)
    return folder


def _running(pid: int) -> bool:
    """Whether a process ``pid`` exists. When it cannot be told, ``True``:
    a folder in use is never removed."""
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER: no such process
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # signal 0: no signal, only the check
    except ProcessLookupError:
        return False
    except OSError:  # PermissionError: another user's process
        return True
    return True


def _left_behind(entry: os.DirEntry, now: float) -> bool:
    kind = next((kind for kind in KINDS if entry.name.startswith(kind)), None)
    if kind is None or not entry.is_dir(follow_symlinks=False):
        return False
    pid, dash, _ = entry.name[len(kind):].partition("-")  # tempfile's random part has no "-"
    if dash and pid.isdigit():
        return not _running(int(pid))
    return now - entry.stat(follow_symlinks=False).st_mtime > UNTRACED_AGE_S


def remove_left_behind(root: Path | None = None) -> int:
    """Remove the folders of :data:`KINDS` in ``root`` (the temporary
    folder) whose process has ended, and those named without a process id
    that have not changed for :data:`UNTRACED_AGE_S`. Only the current
    user's folders are touched. Returns how many were removed."""
    root = Path(tempfile.gettempdir()) if root is None else Path(root)
    now = time.time()
    uid = os.getuid() if hasattr(os, "getuid") else None
    removed = 0
    try:
        entries = list(os.scandir(root))
    except OSError:
        return 0
    for entry in entries:
        try:
            if not _left_behind(entry, now):
                continue
            if uid is not None and entry.stat(follow_symlinks=False).st_uid != uid:
                continue
        except OSError:
            continue
        shutil.rmtree(entry.path, ignore_errors=True)
        removed += not os.path.exists(entry.path)
    return removed
