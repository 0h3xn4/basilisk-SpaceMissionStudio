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
"""Structured errors for the scenario file's limits (engine.findings, the
transparency plan's Phase 5a): a scenario past one is refused with the
message it always had, and the error names the limit's rule, the value
found and the limit."""

import copy
from pathlib import Path

import pytest

from spacemissionstudio import cli
from spacemissionstudio.engine.constellation import WalkerConstellationRequest
from spacemissionstudio.engine.findings import RULES, explanation_lines
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import MAX_SCENARIO_FILE_BYTES, ScenarioValidationError, problem_text
from spacemissionstudio.schema.validation import validate_all

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"


def _template(prefix):
    return load_scenario(next(_TEMPLATES.glob(f"{prefix}_*.json")))


def _too_long_run(s):
    s.sim_settings.duration_days = 4000.0  # [day]


def _too_short_step(s):
    s.sim_settings.dynamics_task_rate_s = 0.0001  # [s]


def _too_many_spacecraft(s):
    s.spacecraft = [copy.deepcopy(s.spacecraft[0]) for _ in range(1001)]
    for index, sc in enumerate(s.spacecraft):
        sc.name = f"sat-{index}"


def _too_long_description(s):
    s.description = "x" * 100_001


def _too_long_name(s):
    s.spacecraft[0].name = "s" * 65


def _too_many_runs(s):
    s.monte_carlo.num_runs = 100_001


def _too_many_processes(s):
    s.monte_carlo.thread_count = 257


# (template, edit, rule, the value found, the limit, words of the message as before)
_CASES = [
    ("01", _too_long_run, "schema.duration_max", "4000 days", "3660 days", "must be <= 3660 days"),
    ("01", _too_short_step, "schema.step_min", "0.0001 s", "0.001 s", "must be at least 0.001 s"),
    ("01", _too_many_spacecraft, "schema.spacecraft_max", "1001 spacecraft", "1000", "1001 spacecraft; at most 1000"),
    ("01", _too_long_description, "schema.description_max", "100001 characters", "100000 characters",
     "is 100001 characters; at most 100000"),
    ("01", _too_long_name, "schema.name_length", "65 characters", "64 characters", "so at most 64"),
    ("01", _too_many_runs, "schema.monte_carlo_runs", "100001", "100000", "between 1 and 100000, got 100001"),
    ("01", _too_many_processes, "schema.monte_carlo_threads", "257", "256", "between 1 and 256, got 257"),
]


@pytest.mark.parametrize(("prefix", "change", "rule_id", "actual", "limit", "words"), _CASES,
                         ids=[case[2] for case in _CASES])
def test_a_scenario_past_a_limit_names_its_rule(prefix, change, rule_id, actual, limit, words):
    """The error's message is as before; it carries the limit's rule, the
    value found and the limit, and validate_all lists it with them."""
    scenario = _template(prefix)
    change(scenario)
    with pytest.raises(ScenarioValidationError, match=words) as raised:
        scenario.validate()
    finding = problem_text(raised.value)
    assert finding == str(raised.value)
    assert (finding.rule_id, finding.actual, finding.limit) == (rule_id, actual, limit)
    (listed,) = validate_all(scenario)
    assert listed.rule_id == rule_id


def test_the_other_limits_name_their_rules():
    """The single-run limit, a data instrument's name, an ROE chief's
    eccentricity and a generated constellation's size."""
    roe = _template("29")
    roe.sim_settings.duration_days = 150.0  # [day]
    with pytest.raises(ScenarioValidationError, match="roe_formation runs at most 100 days") as raised:
        roe.validate()
    assert (problem_text(raised.value).rule_id, problem_text(raised.value).limit) == ("schema.single_run", "100 days")
    roe = _template("29")
    chief = next(sc for sc in roe.spacecraft if sc.roe_formation is None)
    chief.orbit.eccentricity = 0.02  # [-]
    with pytest.raises(ScenarioValidationError, match="must be near-circular") as raised:
        roe.validate()
    assert (problem_text(raised.value).rule_id, problem_text(raised.value).actual) == (
        "schema.roe_chief_eccentricity", "0.02")
    data = _template("26")
    instrument = next(sc.data_handling for sc in data.spacecraft if sc.data_handling is not None).instruments[0]
    instrument.name = "i" * 128
    with pytest.raises(ScenarioValidationError, match="needs a name of 1 to 127 characters") as raised:
        data.validate()
    assert problem_text(raised.value).rule_id == "schema.data_name_length"
    instrument.name = ""  # an empty name: refused as before, with no limit to name
    with pytest.raises(ScenarioValidationError) as raised:
        data.validate()
    assert raised.value.finding is None
    request = WalkerConstellationRequest(total_satellites=1002, num_planes=2, phasing_factor=0, altitude_km=550.0,
                                         inclination_deg=53.0)
    with pytest.raises(ScenarioValidationError, match="a scenario's limit") as raised:
        request.validate()
    assert problem_text(raised.value).rule_id == "schema.spacecraft_max"


def test_a_check_without_a_limit_has_no_rule():
    """A plain validity check (here, a negative dry mass) is refused as
    before, with no rule."""
    scenario = _template("01")
    scenario.sim_settings.duration_days = -1.0  # [day]
    with pytest.raises(ScenarioValidationError) as raised:
        scenario.validate()
    assert raised.value.finding is None and problem_text(raised.value) == str(raised.value)
    assert explanation_lines(problem_text(raised.value)) == []


def test_validate_explain_gives_the_limits_rule(tmp_path, capsys):
    """An invalid file is refused with exit status 1 as before; with
    ``--explain`` the limit's rule follows the INVALID line."""
    big = tmp_path / "big.json"
    big.write_bytes(b" " * (MAX_SCENARIO_FILE_BYTES + 1))
    assert cli.main(["validate", str(big)]) == 1
    plain = [line for line in capsys.readouterr().err.splitlines() if " INFO " not in line]  # the log's start
    assert plain == [f"INVALID: {big}: larger than 20 MB: not a scenario file"]
    assert cli.main(["validate", str(big), "--explain"]) == 1
    explained = [line for line in capsys.readouterr().err.splitlines() if " INFO " not in line]
    assert explained[0] == plain[0]
    assert explained[1] == f"  rule schema.file_size_max: {RULES['schema.file_size_max'].rule}"
    assert explained[2] == f"  found more than {MAX_SCENARIO_FILE_BYTES} bytes; limit {MAX_SCENARIO_FILE_BYTES} bytes"
    assert explained[-1].startswith("  override: It cannot be overridden")
