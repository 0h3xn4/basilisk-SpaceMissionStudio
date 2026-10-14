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
"""A validation message as a form shows it: each field code in it
("station_keeping.thrust_n", "sim_settings.duration_days") replaced by the
label the form gives that field, after its section's title ("Station
keeping: Reboost thrust [N]"). The messages themselves keep their codes:
the command line, the Log and the scenario file speak in them.

A form passes :func:`labelled` its own lookup from a code to a field's
title; a code it does not know stays as it is.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from PySide6.QtWidgets import QGroupBox, QWidget

from .workspace_panels import field_label

# A word made of lower-case parts joined by "_" or ".": not inside a file
# name or path (a neighbouring "-", "/", "\\" or "."), a quoted key or an
# indexed name ("params['rw_type']"), nor a call. A word with neither "_"
# nor "." is plain English ("eccentricity") and is left alone.
_CODE = re.compile(r"(?<![\w.\-/\\'\"])[a-z][a-z0-9]*(?:[_.][a-z][a-z0-9]*|_[0-9]+)*(?![\w\-/\\'\"(\[]|\.\w)")


def section_title(widget: Optional[QWidget]) -> str:
    """The title of the nearest group box around ``widget``, up to its
    first " (" or ":": "Station keeping" for "Station keeping (altitude
    maintenance, delta-V + fuel tracking)"."""
    node = widget
    while node is not None:
        if isinstance(node, QGroupBox) and node.title():
            return _short(node.title())
        node = node.parentWidget()
    return ""


def field_title(widget: Optional[QWidget]) -> str:
    """The field's label after its section's title ("Station keeping:
    Reboost thrust [N]"), its label alone when it has no section or the
    label already names it, or the section alone for a section's own box;
    "" when the form gives it no label."""
    if widget is None:
        return ""
    if isinstance(widget, QGroupBox):
        return _short(widget.title())
    label = _plain(field_label(widget)).split(" (")[0].strip()  # "Restore tolerance [-] (fraction of target)"
    if not label:
        return ""
    section = section_title(widget.parentWidget())
    if section and not label.lower().startswith(section.lower()):
        return f"{section}: {label}"
    return label


def attribute_title(owner: QWidget, code: str, section: str, aliases: Optional[dict] = None) -> str:
    """The title of ``owner``'s widget for a field of ``section``
    ("constellation.num_planes" or "num_planes": ``owner.num_planes``,
    or the attribute ``aliases`` names for it), or ""."""
    if code.startswith(section + "."):
        code = code[len(section) + 1:]
    if "." in code:
        return ""
    widget = getattr(owner, (aliases or {}).get(code, code), None)
    return field_title(widget) if isinstance(widget, QWidget) else ""


def labelled(text: str, title_for: Callable[[str], str]) -> str:
    """``text`` with each field code ``title_for`` gives a title replaced
    by that title. A code without a section ("target_altitude_km" in
    "station_keeping.deadband_km must be < target_altitude_km") is first
    looked up in the section of the dotted code before it; a title whose
    section an earlier one named drops it ("Fuel tank: Propellant mass
    [kg] must be between 0 and Tank capacity [kg]")."""
    sections: list = []
    named: set = set()

    def title_of(code: str) -> str:
        if "." in code:
            sections.append(code.rsplit(".", 1)[0])
        elif sections:
            title = title_for(f"{sections[-1]}.{code}")
            if title:
                return title
        return title_for(code)

    def replace(match: re.Match) -> str:
        code = match.group(0)
        if "_" not in code and "." not in code:
            return code
        title = title_of(code)
        if not title:
            return code
        section, _, label = title.rpartition(": ")
        if section in named:
            return label
        if section:
            named.add(section)
        return title

    return _CODE.sub(replace, text)


def _plain(text: str) -> str:
    """``text`` without its mnemonic "&" ("&&" is a shown "&")."""
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


def _short(title: str) -> str:
    return re.split(r" \(|:", _plain(title), maxsplit=1)[0].strip()
