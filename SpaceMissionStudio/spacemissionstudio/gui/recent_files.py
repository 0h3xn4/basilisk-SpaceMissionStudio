#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
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
