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


"""A mission-sequence command can be disabled (docs/ux-audit.md U-15): it
is left out of the run as if commented out, still validated, and saved
only when disabled, so older files and templates are unchanged."""

import dataclasses
import json
from pathlib import Path

import pytest

from spacemissionstudio.schema.command import Command, report_before_propagate_errors, runs_sequence, script_blocks
from spacemissionstudio.schema.scenario import Scenario, ScenarioValidationError, load_scenario

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"


def _scenario(*commands):
    """Template 22 (one LEO spacecraft) with ``commands`` as its sequence."""
    base = load_scenario(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return dataclasses.replace(base, mission_sequence=list(commands))


def _propagate(days=1.0, enabled=True):  # [day]
    return Command(kind="propagate", params={"stop_condition": "duration", "duration_days": days}, enabled=enabled)


def test_enabled_is_saved_only_when_false():
    """A saved command carries ``enabled`` only when it is disabled, and
    loads back the same."""
    scenario = _scenario(_propagate(), Command(kind="if", params={"condition": "t_s > 0"},
                                               children=[_propagate(enabled=False)]))
    data = scenario.to_dict()
    assert "enabled" not in data["mission_sequence"][0]
    assert data["mission_sequence"][1]["children"][0]["enabled"] is False
    again = Scenario.from_dict(json.loads(json.dumps(data)))
    assert [c.enabled for c in again.mission_sequence] == [True, True]
    assert again.mission_sequence[1].children[0].enabled is False


def test_templates_save_unchanged():
    """Every template saves back to exactly the text it was loaded from:
    nothing gains an ``enabled`` key."""
    from spacemissionstudio.schema.scenario import scenario_text

    for path in sorted(_TEMPLATES.glob("*.json")):
        assert scenario_text(load_scenario(path)) == path.read_text(encoding="utf-8"), path.name


def test_a_non_boolean_enabled_is_an_error():
    """``"enabled": "no"`` in a file names the command and the field."""
    errors = Command.from_dict({"kind": "propagate", "enabled": "no",
                                "params": {"stop_condition": "duration", "duration_days": 1.0}}).validate("m[0]")
    assert errors == ["m[0]: enabled 'no' must be true or false"]


def test_a_disabled_command_is_still_validated():
    """Disabling a broken command does not hide its problem."""
    scenario = _scenario(_propagate(days=0.0, enabled=False))  # [day]
    with pytest.raises(ScenarioValidationError, match="duration_days"):
        scenario.validate()


def test_runs_sequence_needs_one_enabled_top_level_command():
    """A sequence whose commands are all disabled runs like an empty one."""
    assert not runs_sequence([])
    assert not runs_sequence([_propagate(enabled=False)])
    assert runs_sequence([_propagate(enabled=False), _propagate()])


def test_disabled_scripts_need_no_consent():
    """Only scripts that run are listed for consent; paths keep their
    index in the file."""
    script = Command(kind="script_block", params={"code": "x = 1"})
    off = Command(kind="script_block", params={"code": "x = 2"}, enabled=False)
    inside_off = Command(kind="if", params={"condition": "True"}, children=[script], enabled=False)
    assert [path for path, _ in script_blocks([off, script, inside_off])] == ["mission_sequence[1]"]


def test_a_disabled_propagate_does_not_count_before_a_report():
    """A report after a disabled propagate still has nothing recorded."""
    report = Command(kind="report", params={"series": []})
    assert report_before_propagate_errors([_propagate(enabled=False), report]) == [
        "mission_sequence[1]: this report runs before any propagate, so nothing has been recorded yet -- add a "
        "propagate command before it"]
    assert report_before_propagate_errors([_propagate(), report]) == []


def test_disabled_propagates_do_not_count_toward_the_time_limit():
    """The one-run time limit adds up only the propagates that run."""
    long_off = _propagate(days=500.0, enabled=False)  # [day]
    _scenario(long_off, _propagate()).validate()
    with pytest.raises(ScenarioValidationError, match="add up to"):
        _scenario(_propagate(days=500.0)).validate()  # [day]
