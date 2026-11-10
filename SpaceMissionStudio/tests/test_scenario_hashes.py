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
"""Every template saves, and hashes, as it did when this baseline was
recorded (2026-11-01, before Phase 5b's value marks): a field added to the
scenario file that a template does not use must not change its saved text
or the scenario hash its runs record (``tests/data/scenario_hashes.json``)."""

import hashlib
import json
from pathlib import Path

import pytest

from spacemissionstudio.output_provenance import scenario_sha256
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import scenario_text

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_BASELINE = json.loads((Path(__file__).resolve().parent / "data" / "scenario_hashes.json").read_text(encoding="utf-8"))


def test_the_baseline_covers_every_template():
    assert sorted(_BASELINE) == sorted(path.stem for path in _TEMPLATES.glob("*.json"))


@pytest.mark.parametrize("stem", sorted(_BASELINE))
def test_a_template_saves_and_hashes_as_recorded(stem):
    scenario = load_scenario(_TEMPLATES / f"{stem}.json")
    assert hashlib.sha256(scenario_text(scenario).encode("utf-8")).hexdigest() == _BASELINE[stem]["saved_text_sha256"]
    assert scenario_sha256(scenario) == _BASELINE[stem]["scenario_sha256"]
