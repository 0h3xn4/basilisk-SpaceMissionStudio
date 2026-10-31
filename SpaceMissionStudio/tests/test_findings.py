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
"""Structured warnings (engine.findings, the transparency plan's Phase
5a): every pre-run check names its rule, what it found and its limit,
and reads as the warning it always was."""

import json
import pickle
import re
from pathlib import Path

import pytest

from spacemissionstudio import cli
from spacemissionstudio.config import registry
from spacemissionstudio.engine import scenario_checks
from spacemissionstudio.engine.findings import RULES, Finding, explanation_lines
from spacemissionstudio.schema import load_scenario

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"


def _flagged_scenario():
    """Template 19 with a late first pass and a long step."""
    scenario = load_scenario(next(_TEMPLATES.glob("19_*.json")))
    scenario.epoch_utc = "2030-01-01T00:00:00"  # the first pass at about 8.2 h
    scenario.sim_settings.duration_days = 0.5  # [day]
    scenario.sim_settings.dynamics_task_rate_s = 120.0  # [s]
    return scenario


def test_each_rule_is_complete_and_names_a_real_parameter():
    """Every rule says what it is, why, how to fix and how to override;
    one whose limit is a parameter names a registered one."""
    for rule_id, rule in RULES.items():
        assert rule.rule_id == rule_id
        assert all(text.strip().endswith(".") for text in (rule.rule, rule.why, rule.fix, rule.override)), rule_id
        if rule.parameter is not None:
            registry.parameter(rule.parameter)  # raises for an unknown name


def test_every_rule_is_used_by_a_check_and_every_check_names_a_rule():
    """No rule is left without a check or a run's warning
    (tests/test_run_findings.py), and no warning of the pre-run checks is a
    plain string: each names a rule in the table."""
    source = (Path(scenario_checks.__file__)).read_text(encoding="utf-8")
    package = Path(scenario_checks.__file__).resolve().parents[1]
    run_sources = ("engine/service.py", "engine/long_run.py", "engine/results.py", "engine/spaceweather.py",
                   "engine/environment_models.py", "engine/earth_orientation.py", "engine/lifetime.py",
                   "dependencies.py")
    used = set()
    for text in (source, *((package / name).read_text(encoding="utf-8") for name in run_sources)):
        used |= set(re.findall(r'"([a-z_]+\.[a-z_]+)"(?=[),])', text)) & set(RULES)
    assert used == set(RULES)
    assert "warnings.append(f\"" not in source and "warnings.append(\"" not in source
    for line in source.splitlines():
        if "leaves out ~" in line:  # gravity_fidelity_notes: Explain's notes, not warnings
            continue
        assert not re.match(r"\s+return \[f?\"", line), line


def test_a_finding_reads_as_its_warning_and_carries_its_rule():
    """The warnings of a flagged scenario are the same text as before, each
    with its rule, what it found and the limit it was compared with."""
    warnings = scenario_checks.scenario_warnings(_flagged_scenario())
    assert "berlin-gs: the first pass only comes at 8.2 h of a 12.0 h run" in warnings
    by_rule = {w.rule_id: w for w in warnings}
    late, step = by_rule["passes.late_first"], by_rule["step.long"]
    assert (late.actual, late.limit) == ("0.68 of the run", "0.5")
    assert (step.actual, step.limit) == ("120 s", "60 s")
    assert step.rule.parameter == "checks.long_step_s"
    assert json.loads(json.dumps(warnings)) == [str(w) for w in warnings]  # files hold the text, as before
    copy = pickle.loads(pickle.dumps(step))  # Monte Carlo workers send results between processes
    assert (copy, copy.rule_id, copy.actual, copy.limit) == (step, "step.long", "120 s", "60 s")
    record = step.to_dict()
    assert record["rule_id"] == "step.long" and record["limit"] == "60 s"
    assert record["parameter"] == "checks.long_step_s" and record["message"] == str(step)
    with pytest.raises(KeyError):
        Finding("text", "no.such_rule")


def test_a_failing_check_is_a_finding_of_its_own(monkeypatch):
    """A check that raises reports "check not run" under its own rule."""
    def broken(_scenario):
        raise RuntimeError("boom")

    monkeypatch.setattr(scenario_checks, "_step_warnings", broken)
    warnings = scenario_checks.scenario_warnings(_flagged_scenario())
    failed = [w for w in warnings if w.startswith("check not run: step")]
    assert len(failed) == 1 and failed[0].rule_id == "check.not_run"


def test_the_explanation_gives_the_rule_its_values_and_the_parameter():
    step = next(w for w in scenario_checks.scenario_warnings(_flagged_scenario()) if w.rule_id == "step.long")
    lines = explanation_lines(step)
    assert lines[0] == f"rule step.long: {RULES['step.long'].rule}"
    assert lines[1] == "found 120 s; limit 60 s"
    assert lines[2].startswith("why: ") and lines[3].startswith("fix: ")
    assert lines[4].startswith("override: ") and "checks.long_step_s" in lines[4]
    assert explanation_lines("a plain warning") == []


def test_validate_explain_prints_each_warnings_rule(tmp_path, capsys):
    """``validate --explain`` follows each warning with its rule;
    ``validate`` alone prints the warnings as before."""
    path = tmp_path / "flagged.json"
    _flagged_scenario().save(path)
    assert cli.main(["validate", str(path)]) == 0
    plain = capsys.readouterr().out
    assert "WARNING: berlin-gs: the first pass only comes at 8.2 h" in plain and "rule " not in plain
    assert cli.main(["validate", str(path), "--explain"]) == 0
    explained = capsys.readouterr().out
    assert "  rule passes.late_first: " in explained and "  found 0.68 of the run; limit 0.5" in explained
    assert "  rule step.long: " in explained and "checks.long_step_s" in explained
    for line in plain.splitlines():
        assert line in explained.splitlines()  # every plain line is still there
