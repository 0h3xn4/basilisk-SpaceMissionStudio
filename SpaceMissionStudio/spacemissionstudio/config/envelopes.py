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
"""The launcher envelopes the launcher check offers by name
(``LauncherConfig.envelope``), each from a cited user's guide
(``docs/models/model-analyses.md``). An envelope that could not be sourced
is left out; a custom envelope is always available."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Envelope:
    """A sourced envelope: its shape and dimensions [m], as
    ``LauncherConfig`` takes them, its limits and its source."""

    key: str
    name: str
    shape: str  # "cylinder", "box" or "profile"
    source: str
    diameter_m: float | None = None  # [m]
    height_m: float | None = None  # [m]
    width_m: float | None = None  # [m]
    depth_m: float | None = None  # [m]
    profile: tuple = ()  # ((height_m, radius_m), ...)
    mass_limit_kg: float | None = None  # [kg]
    com_height_limit_m: float | None = None  # [m]
    com_lateral_limit_m: float | None = None  # [m]


#: The library, by key.
ENVELOPES: dict[str, Envelope] = {}
