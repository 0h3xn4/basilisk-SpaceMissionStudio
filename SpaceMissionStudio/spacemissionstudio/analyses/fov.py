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
"""Field-of-view obstruction (static): for each mounted sensor, camera
and antenna, how much of its field of view the model's own parts block, and
which parts, in the deployed and the stowed configuration.

The cone of directions from the item's position, about its boresight, with
half the field of view, is sampled uniformly in solid angle
(:meth:`~spacemissionstudio.model3d.raycast.Scene.cone_blockage`); the part
the item is mounted on is ignored, so a sensor head inside its own box sees
out. The blocked fraction is of solid angle, with its binomial standard
error. Model parts do not articulate (decision D-04): "over its range of
motion" is the two configurations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import common

#: Kinds of mounted item that look out through a field of view.
VIEWING_KINDS = ("star_tracker", "coarse_sun_sensor", "sun_sensor", "camera", "antenna")


@dataclass
class Obstruction:
    """One item's field of view in one configuration."""

    spacecraft: str
    item: str
    kind: str
    configuration: str
    field_of_view_deg: float  # [deg] full cone angle
    blocked_fraction: float  # [-] of the field of view's solid angle
    by_part: dict  # part -> [-] of the field of view
    standard_error: float  # [-]
    samples: int


@dataclass
class FovReport:
    """Every viewing item's obstruction, and those that could not be
    checked, with the reason."""

    obstructions: list = field(default_factory=list)  # list[Obstruction]
    skipped: list = field(default_factory=list)  # (item, reason)

    def rows(self) -> list[dict]:
        return [{"spacecraft": o.spacecraft, "item": o.item, "kind": o.kind, "configuration": o.configuration,
                 "field_of_view_deg": o.field_of_view_deg, "blocked_percent": 100.0 * o.blocked_fraction,
                 "standard_error_percent": 100.0 * o.standard_error,
                 "blocking_parts": "; ".join(f"{p} {100.0 * f:.1f} %" for p, f in o.by_part.items()),
                 "samples": o.samples} for o in self.obstructions]


def fov_obstruction(sc, configurations=("deployed", "stowed"), samples: int | None = None,
                    base_dir=None) -> FovReport:
    """:class:`FovReport` for spacecraft ``sc`` (a ``SpacecraftConfig``).
    The stowed configuration is checked only when the model has one."""
    report = FovReport()
    if sc.model is None:
        report.skipped.append(("all", "the spacecraft has no 3D model"))
        return report
    count = common.samples_for(sc, samples)
    for configuration in configurations:
        if configuration == "stowed" and not sc.model.stowed:
            continue
        scene = common.scene(sc, configuration, base_dir)
        for item in common.mounted(sc, configuration):
            if item.kind not in VIEWING_KINDS:
                continue
            missing = [name for name, value in (("a position", item.position_b_m), ("a boresight", item.boresight_b),
                                                ("a field of view", item.field_of_view_deg)) if value is None]
            if missing:
                if configuration == "deployed":
                    report.skipped.append((item.name, "its mount gives no " + " or ".join(missing)))
                continue
            half = math.radians(min(item.field_of_view_deg, 360.0) / 2.0)
            exclude = (item.part,) if item.part else ()
            blockage = scene.cone_blockage(item.position_b_m, item.boresight_b, half, count, exclude)
            report.obstructions.append(Obstruction(sc.name, item.name, item.kind, configuration,
                                                   item.field_of_view_deg, blockage.fraction, blockage.by_part,
                                                   blockage.standard_error, blockage.samples))
    return report
