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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#


"""When this machine last wrote each export (UI overhaul M8): Reports ›
Exports shows it. Each view records an export once its files are written;
the time and the path go in the app's settings, never in an export file.
"""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Signal


class _Signals(QObject):
    changed = Signal(str)  # the export recorded


signals = _Signals()


def _settings() -> QSettings:
    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


def record(kind: str, path) -> None:
    """``kind`` (a key of ``exports_page.EXPORTS``) was written to ``path`` now."""
    settings = _settings()
    settings.setValue(f"exports/{kind}/time", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    settings.setValue(f"exports/{kind}/path", str(path))
    settings.sync()
    signals.changed.emit(kind)


def last(kind: str) -> tuple[str, str] | None:
    """(UTC time with Z, path) of the last ``kind`` written, or None."""
    settings = _settings()
    when = settings.value(f"exports/{kind}/time", "")
    return (str(when), str(settings.value(f"exports/{kind}/path", ""))) if when else None
