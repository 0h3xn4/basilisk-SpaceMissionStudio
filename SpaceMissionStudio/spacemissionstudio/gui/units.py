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
"""Units as a field shows them (UI overhaul M4a): the code's ASCII
spelling ("m^2", "kg*m^2", "deg") as the suffix a number field carries
("m²", "kg·m²", "°").

Only the display changes. Field names in files, messages naming a field
("Drag area [m^2]", ``gui.field_text``) and every exported unit keep
their spelling.
"""

from __future__ import annotations

import re

# The units a form label may carry, and how a field shows each. A unit
# not listed here is left in its label: a bracket can hold other things
# (a JSON key, "lo, hi").
_DISPLAY = {
    "-": "",  # dimensionless: no suffix
    "deg": "°", "deg/s": "°/s", "rad": "rad", "rad/s": "rad/s", "rad/s^2": "rad/s²",
    "m": "m", "km": "km", "m^2": "m²", "m^3": "m³", "km^2": "km²",
    "m/s": "m/s", "km/s": "km/s", "m/s^2": "m/s²", "km/s^2": "km/s²", "m/s^1.5": "m/s^1.5",
    "s": "s", "ms": "ms", "min": "min", "h": "h", "hr": "h", "day": "days", "days": "days", "y": "years",
    "kg": "kg", "g": "g", "kg m^2": "kg·m²", "kg*m^2": "kg·m²", "kg/s": "kg/s",
    "N": "N", "mN": "mN", "N*m": "N·m", "N m": "N·m", "N*m*s": "N·m·s", "N m s": "N·m·s",
    "W": "W", "W*hr": "Wh", "Wh": "Wh", "V": "V", "A": "A", "A*m^2": "A·m²", "A m^2": "A·m²",
    "T": "T", "nT": "nT", "K": "K", "degC": "°C",
    "Hz": "Hz", "GHz": "GHz", "MHz": "MHz", "1/s": "1/s", "1/s^2": "1/s²",
    "dB": "dB", "dBi": "dBi", "dBW": "dBW", "dB-Hz": "dB-Hz", "dBm": "dBm",
    "bit": "bit", "kbit/s": "kbit/s", "Mbit/s": "Mbit/s", "Gbit": "Gbit",
    "px": "px", "%": "%", "RPM": "RPM", "steps": "steps",
    "m^2/s^3 per kg": "m²/s³ per kg",
}

# "Name [unit]" or "Name [unit] (more)": the unit and the rest around it.
_LABEL_UNIT = re.compile(r"^(?P<name>.*?)\s*\[(?P<unit>[^\[\]]+)\]\s*(?P<rest>.*)$")


def display(unit: str) -> str | None:
    """How a field shows ``unit`` ("" for a dimensionless one), or None
    for a unit not known here."""
    return _DISPLAY.get(unit.strip())


def suffix(unit: str) -> str:
    """The suffix a number field carries for ``unit`` (by its display):
    "" for none, "°" right after the number, " km" after a space."""
    shown = display(unit)
    if shown is None:
        shown = unit.strip()
    if not shown:
        return ""
    return shown if shown in ("°", "°/s", "%") else f" {shown}"


def split_label(text: str) -> tuple[str, str | None]:
    """("Name (more)", "unit") for a label "Name [unit] (more)" with a known
    unit, else (text, None)."""
    match = _LABEL_UNIT.match(text)
    if match is None or display(match.group("unit")) is None:
        return text, None
    name, rest = match.group("name").strip(), match.group("rest").strip()
    return (f"{name} {rest}" if rest else name), match.group("unit").strip()
