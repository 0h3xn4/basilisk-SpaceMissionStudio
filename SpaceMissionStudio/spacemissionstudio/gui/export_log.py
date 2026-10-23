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


"""When this machine last wrote each export (UI overhaul M8): Reports ›
Exports shows it. Each view records an export once its files are written;
the time and the path go in the app's settings, never in an export file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QObject, QSettings, Signal


class _Signals(QObject):
    changed = Signal(str)  # the export recorded


signals = _Signals()


def _settings() -> QSettings:
    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


def record(kind: str, path) -> None:
    """``kind`` (a key of ``exports_page.EXPORTS``) was written to ``path`` now."""
    settings = _settings()
    settings.setValue(f"exports/{kind}/time", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    settings.setValue(f"exports/{kind}/path", str(path))
    settings.sync()
    signals.changed.emit(kind)


def last(kind: str) -> Optional[Tuple[str, str]]:
    """(UTC time with Z, path) of the last ``kind`` written, or None."""
    settings = _settings()
    when = settings.value(f"exports/{kind}/time", "")
    return (str(when), str(settings.value(f"exports/{kind}/path", ""))) if when else None
