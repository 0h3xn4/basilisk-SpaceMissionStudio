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
"""What the analyses share: the scene of a spacecraft's model (cached per
model and configuration), its mounted equipment, and the sampling density."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from ..model3d import equipment as equipment_module
from ..model3d import model as model3d
from ..model3d.raycast import Scene, scene_from_model

#: Ray samples per cone or face when a spacecraft sets none (model_analyses.samples).
DEFAULT_SAMPLES = 256

_SCENES: dict = {}  # (model hash, configuration, base_dir) -> (DerivedModel, Scene)
_MAX_SCENES = 16


class AnalysisError(Exception):
    """An analysis that cannot be made: what is missing, in words."""


def spacecraft(scenario, name: str | None = None):
    """The spacecraft named ``name`` (default: the first)."""
    if not scenario.spacecraft:
        raise AnalysisError("the scenario has no spacecraft")
    if name is None:
        return scenario.spacecraft[0]
    for sc in scenario.spacecraft:
        if sc.name == name:
            return sc
    raise AnalysisError(f"no spacecraft named {name!r}")


def samples_for(sc, samples: int | None = None) -> int:
    """The ray samples per cone or face: ``samples``, else the spacecraft's
    ``model_analyses.samples``, else :data:`DEFAULT_SAMPLES`."""
    if samples is not None:
        return int(samples)
    if sc.model_analyses is not None:
        return int(sc.model_analyses.samples)
    return DEFAULT_SAMPLES


def model_hash(model) -> str:
    return hashlib.sha256(json.dumps(asdict(model), sort_keys=True, default=str).encode()).hexdigest()


def derived_and_scene(sc, configuration: str = "deployed", base_dir=None):
    """``(DerivedModel, Scene)`` of ``sc``'s model in ``configuration``,
    cached by the model's content. Raises :class:`AnalysisError` without
    a model, or when one of its parts could not be built."""
    if sc.model is None:
        raise AnalysisError(f"{sc.name} has no 3D model")
    key = (model_hash(sc.model), configuration, str(base_dir))
    if key not in _SCENES:
        derived = model3d.derive(sc.model, base_dir=base_dir, configuration=configuration)
        if len(_SCENES) >= _MAX_SCENES:
            _SCENES.pop(next(iter(_SCENES)))
        _SCENES[key] = (derived, scene_from_model(sc.model, derived, configuration, base_dir))
    derived, found = _SCENES[key]
    # A part that could not be built (an unreadable mesh file) is missing from the scene: what it would block,
    # shade or add to the re-entry would be lost without a word, so no analysis is made on such a model.
    broken = [f"{part.name} ({part.error})" for part in derived.parts if part.mesh is None]
    if broken:
        raise AnalysisError(f"{sc.name}: the 3D model's part(s) {'; '.join(broken)} could not be built: "
                            "fix the model before analysing it")
    return derived, found


def scene(sc, configuration: str = "deployed", base_dir=None) -> Scene:
    return derived_and_scene(sc, configuration, base_dir)[1]


def mounted(sc, configuration: str = "deployed"):
    return equipment_module.mounted_items(sc, configuration)
