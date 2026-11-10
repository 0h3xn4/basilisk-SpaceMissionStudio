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

"""Where each value of a scenario's JSON text is (``gui/json_positions.py``,
decision JE-01): the tokens, every value of every template at its place,
a text cut short, field paths, a problem's place, what is marked and the
matching bracket."""

import json
from pathlib import Path

import pytest

from spacemissionstudio.gui import json_positions as jp
from spacemissionstudio.gui.problem_location import (GROUND_STATION, MISSION_SEQUENCE, PROPAGATION, SCENARIO,
                                                     SPACECRAFT, ProblemLocation, locate)
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import scenario_text

_TEMPLATES = sorted((Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates").glob(
    "*.json"))

_TEXT = """{
  "name": "a [b] {c}",
  "n": -1.5e3,
  "ok": true,
  "list": [1, {"name": "gyro", "x": null}]
}
"""


def test_tokens_say_what_each_part_is():
    """A string before a colon is a key; brackets inside a string are not
    punctuation; a stray word starts no token."""
    found = [(t.kind, _TEXT[t.start:t.end]) for t in jp.tokens(_TEXT)]
    assert found[:6] == [("punctuation", "{"), ("key", '"name"'), ("punctuation", ":"), ("string", '"a [b] {c}"'),
                         ("punctuation", ","), ("key", '"n"')]
    assert ("number", "-1.5e3") in found and ("literal", "true") in found and ("literal", "null") in found
    assert [(t.kind, t.start) for t in jp.tokens('wat "open')] == [("string", 4)]  # an open string, to the line's end


@pytest.mark.parametrize("path", _TEMPLATES, ids=lambda p: p.stem)
def test_every_value_of_every_template_is_found_at_its_place(path):
    """For each template's saved text: every value json.loads gives is in
    the index, and its characters read back as that value; a member's key
    reads back as its name."""
    text = scenario_text(load_scenario(path))
    nodes = jp.index(text)

    def walk(value, where):
        node = nodes[where]
        assert json.loads(text[node.start:node.end]) == value
        if where and isinstance(where[-1], str):
            assert json.loads(text[node.key_start:node.key_end]) == where[-1]
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, where + (key,))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, where + (i,))

    walk(json.loads(text), ())


def test_a_text_cut_short_gives_what_comes_before():
    """A text that stops being JSON still gives its values up to there;
    the open object and list end at the end of the text."""
    text = '{"a": [1, 2, {"b": tru'
    nodes = jp.index(text)
    assert set(nodes) == {(), ("a",), ("a", 0), ("a", 1), ("a", 2)}
    assert nodes[("a",)].end == len(text) and nodes[("a", 1)].start == text.index("2")


def test_field_paths_are_split_into_keys_indices_and_names():
    assert jp.field_parts("sensors[gyro].mount.position_m[0]") == ["sensors", jp.Named("gyro"), "mount",
                                                                    "position_m", 0]
    assert jp.field_parts("fsw_params['target_ground_station']") == ["fsw_params", "target_ground_station"]
    assert jp.field_parts("mission_sequence[2].children[0]") == ["mission_sequence", 2, "children", 0]
    assert jp.field_parts("") == []


def test_a_problem_s_place_is_the_deepest_part_of_its_path_that_exists():
    """A spacecraft by its name, a list item by its name or index, a key;
    a part that does not exist stops the path there."""
    data = {"name": "s", "sim_settings": {"dt_s": 1.0},
            "spacecraft": [{"name": "a"}, {"name": "b", "sensors": [{"name": "gyro", "mount": {"position_m": [1, 2, 3]}}]}],
            "ground_stations": [{"name": "Kiruna", "min_elevation_deg": 5.0}],
            "mission_sequence": [{"name": "x"}, {"name": "y", "children": [{"name": "z"}]}]}
    assert jp.json_path(ProblemLocation(SPACECRAFT, "b", "sensors[gyro].mount.position_m[2]"), data) == (
        "spacecraft", 1, "sensors", 0, "mount", "position_m", 2)
    assert jp.json_path(ProblemLocation(SPACECRAFT, "b", "sensors[nope].mount"), data) == ("spacecraft", 1, "sensors")
    assert jp.json_path(ProblemLocation(SPACECRAFT, "b", "power.bus_idle_power_w"), data) == ("spacecraft", 1)
    assert jp.json_path(ProblemLocation(SPACECRAFT, "c", "dry_mass_kg"), data) is None
    assert jp.json_path(ProblemLocation(GROUND_STATION, "Kiruna", "min_elevation_deg"), data) == (
        "ground_stations", 0, "min_elevation_deg")
    assert jp.json_path(ProblemLocation(SCENARIO, path="name"), data) == ("name",)
    assert jp.json_path(ProblemLocation(PROPAGATION, path="sim_settings.dt_s"), data) == ("sim_settings", "dt_s")
    assert jp.json_path(ProblemLocation(MISSION_SEQUENCE, path="mission_sequence[1].children[0]"), data) == (
        "mission_sequence", 1, "children", 0)
    assert jp.json_path(None, data) is None


def test_a_real_message_is_placed_through_locate():
    """A message of the scenario's validation, as Problems lists it, lands
    on its value in the text."""
    scenario = load_scenario(_TEMPLATES[0])
    sat = scenario.spacecraft[0]
    text = scenario_text(scenario)
    message = f"{sat.name}: dry_mass_kg must be in (0, 1e6]"
    path = jp.json_path(locate(message, [sat.name], []), json.loads(text))
    start, end = jp.mark_span(jp.index(text), path)
    assert path == ("spacecraft", 0, "dry_mass_kg") and float(text[start:end]) == sat.dry_mass_kg


def test_what_is_marked_for_each_kind_of_value():
    """A plain value itself; an object or list by its key; a list item by
    its name, else its opening bracket; nothing for the whole text."""
    nodes = jp.index(_TEXT)

    def marked(path):
        span = jp.mark_span(nodes, path)
        return None if span is None else _TEXT[span[0]:span[1]]

    assert marked(("n",)) == "-1.5e3"
    assert marked(("list",)) == '"list"'
    assert marked(("list", 1)) == '"gyro"'
    assert marked(("list", 0)) == "1"
    assert marked(()) is None and marked(("absent",)) is None
    bare = jp.index('[{"x": 1}]')
    assert jp.mark_span(bare, (0,)) == (1, 2)  # an item with no name: its opening bracket


def test_the_matching_bracket_skips_brackets_in_strings():
    text = _TEXT
    open_list = text.index("[1,")
    close_list = text.rindex("]")
    assert jp.matching_bracket(text, open_list) == close_list
    assert jp.matching_bracket(text, close_list) == open_list
    assert jp.matching_bracket(text, 0) == text.rindex("}")
    assert jp.matching_bracket(text, text.index("[b]")) is None  # inside a string
    assert jp.matching_bracket(text, text.index('"n"')) is None  # not a bracket
    assert jp.matching_bracket("[[]", 0) is None  # never closed
