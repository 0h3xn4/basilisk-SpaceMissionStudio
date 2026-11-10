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
"""Values as IDM-CIC model files write them: decimal commas (``0,5``,
``1,2E-05``), ``True``/``False``, colours as ``RGB(r,g,b)`` and dates as
``dd/MM/yyyy HH:mm:ss``. Each reader takes the text and the field's name
for the error message."""

from __future__ import annotations

import math
import re
from datetime import datetime

from .errors import IdmError

_NUMBER = re.compile(r"[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?")
_RGB = re.compile(r"RGBA?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)")


def number(text, where: str = "a value", default: float | None = None) -> float:
    """``text`` as a finite float; a comma or a point is the decimal
    separator. ``default`` (when given) stands for a missing value."""
    if text is None or not str(text).strip():
        if default is not None:
            return default
        raise IdmError(f"{where}: no value")
    text = str(text).strip()
    if not _NUMBER.fullmatch(text):
        raise IdmError(f"{where}: {text!r} is not a number")
    value = float(text.replace(",", "."))
    if not math.isfinite(value):
        raise IdmError(f"{where}: {text!r} is not a finite number")
    return value


def boolean(text, where: str = "a value", default: bool | None = None) -> bool:
    """``True`` or ``False`` (any case)."""
    if text is None or not str(text).strip():
        if default is not None:
            return default
        raise IdmError(f"{where}: no value")
    lowered = str(text).strip().lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise IdmError(f"{where}: {text!r} is not True or False")


def color(text, default=(0.7, 0.7, 0.7)) -> tuple:
    """``RGB(r,g,b)`` (each 0 to 255) as ``(r, g, b)`` in 0..1;
    ``default`` for anything else (colours are only drawn)."""
    match = _RGB.fullmatch(str(text or "").strip())
    if match is None:
        return tuple(default)
    return tuple(min(255, int(match.group(k))) / 255.0 for k in (1, 2, 3))


def date(text) -> str:
    """``dd/MM/yyyy HH:mm:ss`` as ISO 8601 (``yyyy-mm-ddTHH:MM:SS``), or
    "" when there is none or it does not read."""
    try:
        return datetime.strptime(str(text or "").strip(), "%d/%m/%Y %H:%M:%S").isoformat()
    except ValueError:
        return ""
