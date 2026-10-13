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

"""Where a validation error or plausibility warning is fixed (docs/ux-audit.md
U-12). The messages come from ``Scenario.validate()`` and
``engine.scenario_checks``; they start with what they are about:

- ``scenario.<field> ...``: the Scenario Editor's own fields;
- ``sim_settings.<field>``, ``gravity.<field>``, ``space_weather.<field>``:
  the propagation setup;
- ``<spacecraft>: <field path> ...``: that spacecraft, its field when the
  message names one (``my-sat: dry_mass_kg must be ...``,
  ``my-sat: orbit: ... eccentricity ...``);
- ``<ground station>: <field> ...``: that ground station.

:func:`locate` turns a message into a :class:`ProblemLocation`. No Qt here;
the windows decide what to open for a location.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from ..schema.scenario import GroundStationConfig, OrbitIC, SpacecraftConfig

SCENARIO = "scenario"
PROPAGATION = "propagation"
SPACECRAFT = "spacecraft"
GROUND_STATION = "ground_station"

_PROPAGATION_SECTIONS = ("sim_settings", "gravity", "space_weather")
_SPACECRAFT_FIELDS = {f.name for f in dataclasses.fields(SpacecraftConfig)}
_STATION_FIELDS = {f.name for f in dataclasses.fields(GroundStationConfig)}
_ORBIT_FIELDS = [f.name for f in dataclasses.fields(OrbitIC) if f.name != "type"]
# A field path at the start of a message: "dry_mass_kg", "power.bus_idle_power_w",
# "fsw_params['target_ground_station']".
_PATH = re.compile(r"[A-Za-z_]\w*(?:\[[^\]]*\])?(?:\.[A-Za-z_]\w*(?:\[[^\]]*\])?)*")
# Plausibility warnings name no field; these words say which part they are about.
_WORDS = (("solar array", "solar_arrays"), ("instrument", "data_handling"), ("perigee", "orbit"), ("position", "orbit"), ("escape", "orbit"), ("TLE", "orbit"),
          ("facets", "facets"), ("sun sensor", "sensors"),
          ("navigation error", "navigation_error"), ("hill_pd", "phasing_keeping"), ("drag", "drag_coeff"))


@dataclass(frozen=True)
class ProblemLocation:
    """``area`` is one of the module's constants; ``name`` the spacecraft
    or ground station; ``path`` the dotted field path in that area ("" when
    the message names no field)."""

    area: str
    name: str = ""
    path: str = ""

    @property
    def field(self) -> str:
        """The path's top-level field: "power" for "power.bus_idle_power_w"."""
        return re.split(r"[.\[]", self.path, maxsplit=1)[0] if self.path else ""

    def describe(self) -> str:
        """Where to look, for a tooltip: "my-sat, orbit.eccentricity"."""
        where = {SCENARIO: "the scenario", PROPAGATION: "the propagation setup"}.get(self.area, self.name)
        return f"{where}, {self.path}" if self.path else where


def locate(text: str, spacecraft_names: Iterable[str] = (), station_names: Iterable[str] = ()) -> Optional[
        ProblemLocation]:
    """The location ``text`` is about, or None when it names none of the
    above. The longest matching name wins, so "sat-10" is not taken for
    "sat-1"."""
    if text.startswith("scenario."):
        match = _PATH.match(text, len("scenario."))
        return ProblemLocation(SCENARIO, path=match.group(0) if match else "")
    for section in _PROPAGATION_SECTIONS:
        if text.startswith(section + "."):
            match = _PATH.match(text)
            return ProblemLocation(PROPAGATION, path=match.group(0))
    named = [(name, SPACECRAFT) for name in spacecraft_names] + [(name, GROUND_STATION) for name in station_names]
    for name, area in sorted(named, key=lambda item: len(item[0]), reverse=True):
        if text.startswith(f"{name}: "):
            rest = text[len(name) + 2:]
            return ProblemLocation(area, name, _spacecraft_path(rest) if area == SPACECRAFT else _station_path(rest))
    return None


def _spacecraft_path(rest: str) -> str:
    if "3D model" in rest:  # its own messages, and fields that "differ from the 3D model"
        return "model"
    if rest.startswith("orbit: "):
        words = set(re.findall(r"\w+", rest))
        return next((f"orbit.{name}" for name in _ORBIT_FIELDS if name in words), "orbit")
    match = _PATH.match(rest)
    if match and re.split(r"[.\[]", match.group(0), maxsplit=1)[0] in _SPACECRAFT_FIELDS:
        return match.group(0)
    return next((field for word, field in _WORDS if word in rest), "")


def _station_path(rest: str) -> str:
    match = _PATH.match(rest)
    return match.group(0) if match and match.group(0) in _STATION_FIELDS else ""
