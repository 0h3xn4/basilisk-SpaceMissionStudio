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
"""The recent scenarios Home lists (UI overhaul plan §7, M3): the last
:data:`MAX_RECENT` scenario files opened or saved, newest first.

Kept with :class:`QSettings` in the app's own ``settings.ini`` (where the
theme choice is kept), not in any scenario or project file.
"""

from __future__ import annotations

from pathlib import Path

MAX_RECENT = 10  # the plan's "last 10"
_KEY = "recent/scenarios"


def _settings():
    from PySide6.QtCore import QSettings

    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


def _key(path: Path) -> str:
    """How two paths are compared: resolved, and case-blind on Windows."""
    resolved = str(Path(path).expanduser().resolve())
    return resolved.casefold() if Path("A") == Path("a") else resolved


def recent() -> list[Path]:
    """The recent scenario files, newest first (a missing one included)."""
    value = _settings().value(_KEY, [])
    if isinstance(value, str):  # an INI list of one reads back as a string
        value = [value]
    return [Path(text) for text in (value or []) if text][:MAX_RECENT]


def _store(paths: list[Path]) -> list[Path]:
    settings = _settings()
    settings.setValue(_KEY, [str(path) for path in paths[:MAX_RECENT]])
    settings.sync()
    return paths[:MAX_RECENT]


def remember(path: Path) -> list[Path]:
    """Put ``path`` first; the oldest past :data:`MAX_RECENT` drops off."""
    path = Path(path).expanduser().resolve()
    return _store([path] + [other for other in recent() if _key(other) != _key(path)])


def forget(path: Path) -> list[Path]:
    """Take ``path`` off the list."""
    return _store([other for other in recent() if _key(other) != _key(path)])


def clear() -> list[Path]:
    return _store([])
