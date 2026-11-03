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
    a model."""
    if sc.model is None:
        raise AnalysisError(f"{sc.name} has no 3D model")
    key = (model_hash(sc.model), configuration, str(base_dir))
    if key not in _SCENES:
        derived = model3d.derive(sc.model, base_dir=base_dir, configuration=configuration)
        if len(_SCENES) >= _MAX_SCENES:
            _SCENES.pop(next(iter(_SCENES)))
        _SCENES[key] = (derived, scene_from_model(sc.model, derived, configuration, base_dir))
    return _SCENES[key]


def scene(sc, configuration: str = "deployed", base_dir=None) -> Scene:
    return derived_and_scene(sc, configuration, base_dir)[1]


def mounted(sc, configuration: str = "deployed"):
    return equipment_module.mounted_items(sc, configuration)
