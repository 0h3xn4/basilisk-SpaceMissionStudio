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

"""Refactoring on the JSON page (decisions JE-07 to JE-09 of
``docs/developer/json-editor.md``). No Qt here.

- :func:`name_at` finds the name at a place: a spacecraft's, a ground
  station's or a 3D model part's own ``name``, or a field that refers to
  one (``schema.fields.REFERENCES``, a mission step's ``spacecraft`` or
  ``ground_station``, ``fsw_params.target_ground_station``).
- :func:`definition` is where that name is defined.
- :func:`rename` renames it and every reference to it with the same
  functions the forms use (``schema.references``), on the scenario the
  text holds, and gives the text back as the scenario file is written.
- :func:`format_text` lays the text out as the scenario file is (two
  spaces), keeping its keys' order and its values.
- :func:`unknown_keys` marks the keys a record does not have (text that
  cannot be applied says only which key, not where), and
  :func:`quick_fixes` offers what can replace a wrong key, a value that
  is not one of its choices, or a name that does not exist.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass

from ..schema import fields, references
from ..schema.scenario import name_error, parse_scenario_text, scenario_text
from . import json_positions

KINDS = ("spacecraft", "ground_station", "part")
_LABELS = {"spacecraft": "spacecraft", "ground_station": "ground station", "part": "part"}
_COMMAND_REFERENCES = {"spacecraft": "spacecraft", "ground_station": "ground_station"}


@dataclass(frozen=True)
class NameAt:
    """A name at a place: its ``kind`` (one of :data:`KINDS`), the
    ``name``, the spacecraft it belongs to (its index, for a part) and
    whether the place is where it is defined."""

    kind: str
    name: str
    spacecraft: int | None
    defined_here: bool

    @property
    def label(self) -> str:
        return _LABELS[self.kind]


def _value_path(text: str, position: int):
    """The path of the string value at ``position``, and the value."""
    nodes = json_positions.index(text)
    for path, node in nodes.items():
        if node.kind == "string" and node.start <= position <= node.end and path:
            try:
                return path, json.loads(text[node.start:node.end])
            except ValueError:
                return None
    return None


def name_at(text: str, position: int) -> NameAt | None:
    """The name at ``position`` (module docstring), or None."""
    found = _value_path(text, position)
    if found is None:
        return None
    path, value = found
    *parent, key = path
    if not isinstance(key, str) or not isinstance(value, str):
        return None
    record = fields.record_at(parent)
    craft = parent[1] if len(parent) >= 2 and parent[0] == "spacecraft" and isinstance(parent[1], int) else None
    if key == "name" and record is not None:
        kind = {"SpacecraftConfig": "spacecraft", "GroundStationConfig": "ground_station",
                "ModelPartConfig": "part"}.get(record.__name__)
        if kind is not None:
            return NameAt(kind, value, craft, True)
        return None
    if record is not None:
        refers = fields.REFERENCES.get((record.__name__, key))
        if refers in KINDS:
            return NameAt(refers, value, craft, False)
        return None
    if parent and parent[0] == "mission_sequence" and parent[-1] == "params" and key in _COMMAND_REFERENCES:
        return NameAt(_COMMAND_REFERENCES[key], value, None, False)
    if len(parent) == 3 and parent[0] == "spacecraft" and parent[2] == "fsw_params" and key == "target_ground_station":
        return NameAt("ground_station", value, None, False)
    return None


def definition(text: str, target: NameAt) -> tuple[int, int] | None:
    """The characters of the name's own ``name`` value, or None."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    nodes = json_positions.index(text)

    def named(items, prefix: tuple):
        for i, item in enumerate(items if isinstance(items, list) else []):
            if isinstance(item, dict) and item.get("name") == target.name:
                node = nodes.get(prefix + (i, "name"))
                return (node.start, node.end) if node is not None else None
        return None

    if target.kind == "spacecraft":
        return named(data.get("spacecraft"), ("spacecraft",))
    if target.kind == "ground_station":
        return named(data.get("ground_stations"), ("ground_stations",))
    crafts = data.get("spacecraft") or []
    if target.spacecraft is None or not 0 <= target.spacecraft < len(crafts):
        return None
    model = crafts[target.spacecraft].get("model") or {}
    return named(model.get("parts") if isinstance(model, dict) else None,
                 ("spacecraft", target.spacecraft, "model", "parts"))


def rename(text: str, target: NameAt, new_name: str) -> tuple[str, int]:
    """``(text, references updated)`` with ``target`` renamed
    ``new_name`` everywhere (module docstring). Raises ValueError with
    the reason when the text is not a scenario, the name cannot be used
    or is taken."""
    problem = name_error(target.label, new_name)
    if problem is not None:
        raise ValueError(str(problem))
    try:
        scenario = parse_scenario_text(text, "JSON view")
    except Exception as exc:  # noqa: BLE001 -- the text's own problem, said as it is
        raise ValueError(f"the text is not a scenario that can be read: {exc}") from None
    try:
        if target.kind == "spacecraft":
            count = references.rename_spacecraft(scenario, target.name, new_name)
        elif target.kind == "ground_station":
            count = references.rename_ground_station(scenario, target.name, new_name)
        else:
            if target.spacecraft is None or not 0 <= target.spacecraft < len(scenario.spacecraft):
                raise ValueError(f"no spacecraft holds the part {target.name!r}")
            count = references.rename_part(scenario.spacecraft[target.spacecraft], target.name, new_name)
    except references.ReferenceError as exc:
        raise ValueError(str(exc)) from None
    return scenario_text(scenario), count


def format_text(text: str) -> str:
    """The text laid out as the scenario file is (two spaces, one value a
    line), its keys' order and values kept. Raises ValueError when it is
    not JSON."""
    return json.dumps(json.loads(text), indent=2) + "\n"


def _span_of_member(text: str, nodes, path: tuple) -> tuple[int, int]:
    """The characters of the member at ``path`` with the comma that joins
    it to the next one (or the previous one, for the last)."""
    node = nodes[path]
    start, end = node.key_start, node.end
    rest = text[end:]
    stripped = rest.lstrip()
    if stripped.startswith(","):
        end += len(rest) - len(stripped) + 1
        tail = text[end:]
        end += len(tail) - len(tail.lstrip(" \t"))
        if text[end:end + 1] == "\n":
            end += 1
            line_start = text.rfind("\n", 0, start) + 1
            if not text[line_start:start].strip():
                start = line_start
    else:
        before = text[:start].rstrip()
        if before.endswith(","):
            start = len(before) - 1
    return start, end


def unknown_keys(text: str) -> list[tuple[str, str, int, int]]:
    """``(severity, message, start, end)`` for each key of a record that
    is not one of its fields."""
    nodes = json_positions.index(text)
    found = []
    for path, node in nodes.items():
        if not path or node.key_start is None or not isinstance(path[-1], str):
            continue
        record = fields.record_at(path[:-1])
        if record is None or nodes.get(path[:-1]) is None or nodes[path[:-1]].kind != "object":
            continue
        names = [f.name for f in fields.fields(record)]
        if path[-1] not in names:
            close = difflib.get_close_matches(path[-1], names, n=1)
            hint = f": did you mean {close[0]!r}?" if close else ""
            found.append(("error", f"{path[-1]!r} is not a field of {record.__name__}{hint} (Ctrl+. offers fixes)",
                          node.key_start, node.key_end))
    return found


@dataclass(frozen=True)
class Fix:
    """A quick fix: its ``label`` and the characters it replaces
    (``start`` to ``end``) with ``insert``."""

    label: str
    start: int
    end: int
    insert: str


def _closest_first(value: str, options) -> list[str]:
    options = [str(o) for o in options]
    if not options:
        return []
    close = difflib.get_close_matches(value, options, n=len(options), cutoff=0.0)
    return close or options


def quick_fixes(text: str, position: int, data=None) -> list[Fix]:
    """What can fix the key or value at ``position`` (module docstring)."""
    nodes = json_positions.index(text)
    for path, node in nodes.items():
        if not path or not isinstance(path[-1], str):
            continue
        record = fields.record_at(path[:-1])
        if record is None:
            continue
        key = path[-1]
        names = [f.name for f in fields.fields(record)]
        if node.key_start is not None and node.key_start <= position <= node.key_end and key not in names:
            taken = {p[-1] for p in nodes if len(p) == len(path) and p[:-1] == path[:-1]}
            fixes = [Fix(f"Change to {name!r}", node.key_start, node.key_end, json.dumps(name))
                     for name in difflib.get_close_matches(key, [n for n in names if n not in taken], n=3)]
            start, end = _span_of_member(text, nodes, path)
            return fixes + [Fix(f"Remove {key!r}", start, end, "")]
        if node.kind != "string" or not node.start <= position <= node.end:
            continue
        info = fields.field(record, key)
        if info is None:
            continue
        value = json.loads(text[node.start:node.end])
        options: list = []
        if info.choices and value not in info.choices:
            options = list(info.choices)
        elif info.refers:
            known = fields.names(data if data is not None else _loaded(text), info.refers, tuple(path[:-1]))
            if value not in known:
                options = known
        return [Fix(f"Use {option!r}", node.start, node.end, json.dumps(option))
                for option in _closest_first(value, options)]
    return []


def _loaded(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None
