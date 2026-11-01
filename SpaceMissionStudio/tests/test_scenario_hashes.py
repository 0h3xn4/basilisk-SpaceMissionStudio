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
