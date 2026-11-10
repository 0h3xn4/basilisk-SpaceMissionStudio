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

"""Refactoring on the JSON page (``gui/json_refactor.py``, decisions JE-07
to JE-09): the name at a place, its definition, renaming with every
reference (the forms' own functions), formatting, keys a record does not
have, and quick fixes. Templates 05 (a chief and a follower) and 32 (3D
model parts named by mounts)."""

import json
from pathlib import Path

import pytest

from spacemissionstudio.gui import json_refactor as refactor
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import parse_scenario_text, scenario_text

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"


def _text(name: str) -> str:
    return scenario_text(load_scenario(_TEMPLATES / name))


_FORMATION = "05_formation_flying_phasing.json"
_PARTS = "32_smallsat_design_checks.json"


def _at(text: str, after: str, offset: int = 1) -> int:
    """A place just inside the string value that follows ``after``."""
    return text.index(after) + len(after) + offset


def test_the_name_at_a_place():
    """A reference (the chief), a definition (a spacecraft's name), a part
    named by a mount; nothing on a key, a number or another string."""
    text = _text(_FORMATION)
    chief = refactor.name_at(text, _at(text, '"chief_spacecraft": "'))
    assert (chief.kind, chief.name, chief.defined_here) == ("spacecraft", "chief-1", False)
    first = refactor.name_at(text, _at(text, '"spacecraft": [\n    {\n      "name": "'))
    assert first.kind == "spacecraft" and first.defined_here and first.spacecraft == 0
    assert refactor.name_at(text, text.index('"chief_spacecraft"') + 2) is None  # the key
    assert refactor.name_at(text, _at(text, '"dry_mass_kg": ', 0)) is None  # a number
    assert refactor.name_at(text, _at(text, '"epoch_utc": "')) is None  # a string that names nothing
    parts = _text(_PARTS)
    mounted = refactor.name_at(parts, _at(parts, '"part": "'))
    assert (mounted.kind, mounted.spacecraft, mounted.defined_here) == ("part", 0, False)


def test_the_definition_of_a_name():
    text = _text(_FORMATION)
    start, end = refactor.definition(text, refactor.name_at(text, _at(text, '"chief_spacecraft": "')))
    assert text[start:end] == '"chief-1"' and text.rfind('"name"', 0, start) > text.index('"spacecraft": [')
    parts = _text(_PARTS)
    target = refactor.name_at(parts, _at(parts, '"part": "'))
    start, end = refactor.definition(parts, target)
    assert json.loads(parts[start:end]) == target.name and '"parts": [' in parts[:start]
    assert refactor.definition("{not json", target) is None


def test_renaming_updates_every_reference():
    """The chief renamed from the follower's reference: both places, the
    scenario still reads; a name that cannot be a file name, or is
    taken, is refused with the reason."""
    text = _text(_FORMATION)
    target = refactor.name_at(text, _at(text, '"chief_spacecraft": "'))
    renamed, count = refactor.rename(text, target, "leader")
    scenario = parse_scenario_text(renamed, "test")
    assert count == 1 and [sc.name for sc in scenario.spacecraft].count("leader") == 1
    [follower] = [sc for sc in scenario.spacecraft if sc.phasing_keeping is not None]
    assert follower.phasing_keeping.chief_spacecraft == "leader"
    with pytest.raises(ValueError, match="cannot contain"):
        refactor.rename(text, target, "a/b")
    with pytest.raises(ValueError, match="already exists"):
        refactor.rename(text, target, "follower-1")
    with pytest.raises(ValueError, match="not a scenario"):
        refactor.rename("{}", target, "leader")


def test_renaming_a_part_updates_its_mounts():
    parts = _text(_PARTS)
    target = refactor.name_at(parts, _at(parts, '"part": "'))
    before = parts.count(json.dumps(target.name))
    renamed, count = refactor.rename(parts, target, "Head")
    assert count == before - 1 and renamed.count('"Head"') == before and json.dumps(target.name) not in renamed


def test_formatting_keeps_the_order_and_the_values():
    assert refactor.format_text('{"b":[1,2],"a":{"c":true}}') == '{\n  "b": [\n    1,\n    2\n  ],\n  "a": {\n' \
                                                                '    "c": true\n  }\n}\n'
    text = _text(_FORMATION)
    assert refactor.format_text(json.dumps(json.loads(text))) == text  # the saved layout
    with pytest.raises(ValueError):
        refactor.format_text('{"a": ')


def test_a_key_the_record_does_not_have_is_marked_and_fixed():
    """A misspelt key is marked with the field it is close to; the fixes
    change it or remove it (with its comma), the text staying JSON."""
    text = _text(_FORMATION).replace('"dry_mass_kg"', '"dry_mas_kg"', 1)
    [(severity, message, start, end)] = refactor.unknown_keys(text)
    assert severity == "error" and text[start:end] == '"dry_mas_kg"' and "did you mean 'dry_mass_kg'" in message
    fixes = refactor.quick_fixes(text, start + 2)
    assert [f.label for f in fixes] == ["Change to 'dry_mass_kg'", "Remove 'dry_mas_kg'"]
    for fix in fixes:
        fixed = text[:fix.start] + fix.insert + text[fix.end:]
        data = json.loads(fixed)
        assert "dry_mas_kg" not in data["spacecraft"][0]
    removed = fixes[1]
    data = json.loads(text[:removed.start] + text[removed.end:])
    assert "dry_mass_kg" not in data["spacecraft"][0] and "inertia_kg_m2" in data["spacecraft"][0]
    last = '{"spacecraft": [{"name": "a", "warp": 1}]}'  # the last member: its comma before goes
    [fix] = [f for f in refactor.quick_fixes(last, last.index("warp")) if f.label.startswith("Remove")]
    assert json.loads(last[:fix.start] + last[fix.end:]) == {"spacecraft": [{"name": "a"}]}
    assert refactor.unknown_keys(_text(_FORMATION)) == []


def test_a_value_that_is_not_a_choice_or_a_name_is_fixed():
    text = _text(_FORMATION).replace('"type": "classical_elements"', '"type": "clasical"', 1)
    fixes = refactor.quick_fixes(text, _at(text, '"type": "'))
    assert [f.label for f in fixes] == ["Use 'classical_elements'", "Use 'cartesian'", "Use 'tle'"]
    wrong = _text(_FORMATION).replace('"chief_spacecraft": "chief-1"', '"chief_spacecraft": "chief-2"')
    fixes = refactor.quick_fixes(wrong, _at(wrong, '"chief_spacecraft": "'))
    assert [f.label for f in fixes][0] == "Use 'chief-1'"
    assert refactor.quick_fixes(_text(_FORMATION), _at(_text(_FORMATION), '"chief_spacecraft": "')) == []


def test_a_step_param_its_kind_does_not_read_is_a_warning_with_fixes():
    """A maneuver's misspelt "fram" is marked as a warning (the step would
    ignore it), and fixed to "frame"; a value outside a step param's
    choices is fixed too. A device's params are not checked for keys."""
    text = json.dumps({"mission_sequence": [{"kind": "maneuver", "params": {"spacecraft": "a", "fram": "vnb"}}]},
                      indent=2)
    [(severity, message, start, end)] = refactor.unknown_keys(text)
    assert severity == "warning" and text[start:end] == '"fram"' and "did you mean 'frame'" in message
    assert "read by a 'maneuver' step" in message
    assert [f.label for f in refactor.quick_fixes(text, start + 2)] == ["Change to 'frame'", "Remove 'fram'"]
    wrong = json.dumps({"mission_sequence": [{"kind": "maneuver", "params": {"frame": "vbn"}}]})
    assert [f.label for f in refactor.quick_fixes(wrong, wrong.index("vbn"))][0] == "Use 'vnb'"
    device = json.dumps({"spacecraft": [{"name": "a", "sensors": [{"kind": "imu", "name": "g",
                                                                    "params": {"anything": 1}}]}]})
    assert refactor.unknown_keys(device) == []
    wheel = json.dumps({"spacecraft": [{"name": "a", "actuators": [{"kind": "reaction_wheel", "name": "w",
                                                                     "params": {"rw_type": "Honeywel_HR16"}}]}]})
    assert refactor.quick_fixes(wheel, wheel.index("Honeywel"))[0].label == "Use 'Honeywell_HR16'"
