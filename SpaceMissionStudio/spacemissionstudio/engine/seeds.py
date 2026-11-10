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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""Random seeds for a run: one per model, derived from the scenario's.

Every Basilisk SysModel has an ``RNGSeed`` (``sys_model.h``), 0x1badcad1
until set. Every sensor noise model kept it, so all of them drew the same
sequence: two identical sun sensors gave identical readings, and noise
repeated across sensors, spacecraft and run segments (audit E5,
2026-10-27). :func:`assign_rng_seeds` gives each model its own seed from
``sim_settings.seed`` and the model's name; the same scenario still gives
the same run. Basilisk-free (it reads and sets attributes only), so
:mod:`engine.long_run` can use it too.
"""

from __future__ import annotations

import hashlib
import re

# Every Basilisk SysModel's RNGSeed until set (sys_model.h).
BASILISK_DEFAULT_RNG_SEED = 0x1badcad1


RNG_SEED_NOTE = (
    "each model's RNGSeed is derived from the scenario's seed (sim_settings.seed) and the model's name "
    "(SHA-256); a navigation error's own seed is kept, and a Monte Carlo run disperses them per run"
)


def derived_seed(base: int, key: str) -> int:
    """A 32-bit seed for ``key`` (a model's name) from the run's seed
    ``base``: the first four bytes of SHA-256 of both."""
    return int.from_bytes(hashlib.sha256(f"{base}:{key}".encode()).digest()[:4], "big")


def model_key(tag: str) -> str:
    """The name a model's seed is derived from: its ModelTag, except that a
    recorder's ("Rec:" and the message type as the C++ compiler spells it:
    "Rec:SCStatesMsg" with GCC, "Rec:class <struct SCStatesMsg" with MSVC)
    is "Rec:" and the type's own name on every platform. The provenance then
    lists the same keys on Windows and Linux (found by the regression
    baseline, PR #150). Recorders draw no random numbers, so their seeds
    change nothing a run computes."""
    if tag.startswith("Rec:"):
        names = re.findall(r"[A-Za-z_]\w*", tag[len("Rec:"):])
        if names:
            return "Rec:" + names[-1]
    return tag


def assign_rng_seeds(sim, base: int) -> dict[str, int]:
    """Give every model in ``sim``'s tasks that still has Basilisk's default
    RNGSeed its own seed, derived from ``base`` and its ModelTag (or its
    place in the task list when it has none); a seed set on purpose (a
    navigation error's own seed, a Monte Carlo run's dispersed seeds) is
    kept. Returns ``{name: seed}`` for the provenance."""
    seeds: dict[str, int] = {}
    for i, task in enumerate(sim.TaskList):
        for j, model in enumerate(task.TaskModels):
            if getattr(model, "RNGSeed", None) != BASILISK_DEFAULT_RNG_SEED:
                continue
            key = model_key(getattr(model, "ModelTag", "")) or f"TaskList[{i}].TaskModels[{j}]"
            name, count = key, 1
            while name in seeds:  # two models with one tag: the second is "tag#2"
                count += 1
                name = f"{key}#{count}"
            model.RNGSeed = seeds[name] = derived_seed(base, name)
    return seeds
