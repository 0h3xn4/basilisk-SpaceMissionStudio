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
