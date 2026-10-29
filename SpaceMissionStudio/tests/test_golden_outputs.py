"""The regression baseline (docs/transparency_audit.md, Phase 1a): every
template gives the outputs stored in ``tests/golden/``. See
``tests/golden_capture.py`` for what is captured and how it is compared.

A failure lists each output that changed. If the change is meant, record
each changed number in ``docs/changes.md`` (before and after) and rewrite the
baseline with ``python scripts/update_golden_outputs.py --write``.
"""

import json

import pytest

import golden_capture

pytestmark = pytest.mark.requires_basilisk


# About a minute or more each here (their budgets solve the re-entry), so
# "slow" as the repository marks such tests; CI runs them.
_SLOW = {"03_geo_station_keeping", "05_formation_flying_phasing", "24_formation_mean_element_control",
         "29_roe_formation_helix"}


@pytest.mark.parametrize("path", [pytest.param(p, marks=pytest.mark.slow) if p.stem in _SLOW else p
                                  for p in golden_capture.template_paths()], ids=lambda p: p.stem)
def test_every_template_gives_its_recorded_outputs(path, request):
    """Each template, run as ``spacemissionstudio run`` runs it (capped at
    6 hours of simulated time), with its lifetime, budget, Monte Carlo batch
    and Explain text, matches its stored fingerprint."""
    if path.stem.startswith("31_"):
        request.getfixturevalue("real_small_body_files")  # Eros needs the installed kernel, as its other tests do
    stored = golden_capture.GOLDEN / f"{path.stem}.json"
    golden = json.loads(stored.read_text(encoding="utf-8"))
    problems = golden_capture.compare(golden, golden_capture.capture(path))
    assert not problems, f"{len(problems)} output(s) of {path.name} changed:\n" + "\n".join(problems[:200])


def test_every_template_has_a_recorded_fingerprint():
    """No template is left out of the baseline, and none is recorded that no longer exists."""
    templates = {p.stem for p in golden_capture.template_paths()}
    recorded = {p.stem for p in golden_capture.GOLDEN.glob("*.json")}
    assert templates == recorded


def test_the_comparison_holds_each_number_to_its_own_scale():
    """A change of one part in 1e8 of a column's size is caught; one part in
    1e12 is not; text and counts must match exactly."""
    golden = {"min": -7.0e6, "max": 7.0e6, "first": 1.0, "samples": [1.0, 2.0], "label": "a"}
    assert golden_capture.compare(golden, dict(golden, first=1.0 + 7.0e6 * 1e-12)) == []
    assert golden_capture.compare(golden, dict(golden, first=1.0 + 7.0e6 * 1e-8))
    assert golden_capture.compare(golden, dict(golden, label="b"))
    assert golden_capture.compare(golden, dict(golden, samples=[1.0]))
