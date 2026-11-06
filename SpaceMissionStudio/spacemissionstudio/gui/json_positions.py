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

"""Where each value of a scenario's JSON text is, for the JSON page's
editor (``gui/json_view.py``, decision JE-01 of
``docs/developer/json-editor.md``). No Qt here.

:func:`tokens` splits a text into JSON tokens (strings, numbers, the
literals ``true``/``false``/``null``, punctuation), each with its place.
:func:`index` reads the text's values with their places: every value by
its path (a tuple of keys and list indices, as ``json.loads`` would give
them), with the place of its key, when it has one, and of the value
itself. It reads as far as the text is JSON and stops there, so a text
being typed still gives what comes before the mistake.

:func:`json_path` turns where a problem is (``problem_location.locate``:
an area, a spacecraft or ground station name, a field path such as
``sensors[gyro].mount.position_m[0]``) into a path in the text's data,
the deepest that exists; :func:`mark_span` says which characters to mark
for a path. :func:`matching_bracket` finds the bracket that closes or
opens the one at a place, skipping brackets inside strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from .problem_location import GROUND_STATION, MISSION_SEQUENCE, PROPAGATION, SCENARIO, SPACECRAFT, ProblemLocation

#: A JSON token: a string (closed, or open to the end of the line), a number, a literal, a punctuation mark.
_TOKEN = re.compile(r'"(?:[^"\\\n]|\\.)*"?|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}\[\]:,]')
_SPACE = re.compile(r"\s*")


@dataclass(frozen=True)
class Token:
    """One token: ``kind`` is "key" (a string followed by a colon),
    "string", "number", "literal" or "punctuation"; ``start`` and ``end``
    are character offsets, the end excluded."""

    kind: str
    start: int
    end: int


def tokens(text: str) -> list[Token]:
    """The JSON tokens of ``text`` in order; characters that start none
    (a stray letter) are skipped. A string is a key when the next token
    is a colon."""
    found = []
    for match in _TOKEN.finditer(text):
        value = match.group(0)
        if value[0] == '"':
            kind = "string"
        elif value in ("true", "false", "null"):
            kind = "literal"
        elif value in "{}[]:,":
            kind = "punctuation"
        else:
            kind = "number"
        found.append(Token(kind, match.start(), match.end()))
    for i, token in enumerate(found[:-1]):
        nxt = found[i + 1]
        if token.kind == "string" and nxt.kind == "punctuation" and text[nxt.start] == ":":
            found[i] = Token("key", token.start, token.end)
    return found


@dataclass(frozen=True)
class Node:
    """A value of the text: its ``path``, the place of its key (None for a
    list item or the whole document) and of the value, as character
    offsets (end excluded), and its ``kind`` ("object", "array", "string",
    "number", "literal")."""

    path: tuple
    key_start: int | None
    key_end: int | None
    start: int
    end: int
    kind: str


class _Stop(Exception):
    """The text stops being JSON here."""


class _Reader:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.nodes: dict[tuple, Node] = {}

    def skip(self) -> None:
        self.pos = _SPACE.match(self.text, self.pos).end()

    def peek(self) -> str:
        self.skip()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def expect(self, char: str) -> None:
        if self.peek() != char:
            raise _Stop
        self.pos += 1

    def string(self) -> tuple[int, int, str]:
        self.skip()
        match = _TOKEN.match(self.text, self.pos)
        if match is None or match.group(0)[0] != '"' or len(match.group(0)) < 2 or match.group(0)[-1] != '"':
            raise _Stop
        self.pos = match.end()
        return match.start(), match.end(), _unquote(match.group(0))

    def value(self, path: tuple, key: tuple | None) -> None:
        char = self.peek()
        start = self.pos
        if char == "{":
            self.pos += 1
            kind = "object"
            self.nodes[path] = Node(path, *(key or (None, None)), start, len(self.text), kind)  # until closed
            if self.peek() != "}":
                while True:
                    key_start, key_end, name = self.string()
                    self.expect(":")
                    self.value(path + (name,), (key_start, key_end))
                    if self.peek() == ",":
                        self.pos += 1
                        continue
                    break
            self.expect("}")
        elif char == "[":
            self.pos += 1
            kind = "array"
            self.nodes[path] = Node(path, *(key or (None, None)), start, len(self.text), kind)
            if self.peek() != "]":
                i = 0
                while True:
                    self.value(path + (i,), None)
                    i += 1
                    if self.peek() == ",":
                        self.pos += 1
                        continue
                    break
            self.expect("]")
        elif char == '"':
            self.string()
            kind = "string"
        else:
            match = _TOKEN.match(self.text, self.pos)
            if match is None or match.group(0)[0] in '"{}[]:,':
                raise _Stop
            self.pos = match.end()
            kind = "literal" if match.group(0) in ("true", "false", "null") else "number"
        self.nodes[path] = Node(path, *(key or (None, None)), start, self.pos, kind)


def _unquote(literal: str) -> str:
    import json

    try:
        return json.loads(literal)
    except ValueError:
        return literal[1:-1]


def index(text: str) -> dict[tuple, Node]:
    """Every value of ``text`` by its path (module docstring). A value
    still open where the text stops being JSON ends at the end of the
    text."""
    reader = _Reader(text)
    try:
        reader.value((), None)
    except _Stop:
        pass
    return reader.nodes


# A field path's parts: a name, then [index], [name] or ['key'] parts, separated by dots.
_PART = re.compile(r"\.?([A-Za-z_]\w*)|\[(\d+)\]|\[['\"]([^'\"]*)['\"]\]|\[([^\]]*)\]")


@dataclass(frozen=True)
class Named:
    """A list item given by its ``name`` (``sensors[gyro]``)."""

    name: str


def field_parts(path: str) -> list:
    """The parts of a field path: ``sensors[gyro].mount.position_m[0]`` ->
    ``["sensors", Named("gyro"), "mount", "position_m", 0]``; a quoted
    key (``fsw_params['target']``) is a key."""
    parts: list = []
    for match in _PART.finditer(path):
        name, number, quoted, named = match.groups()
        if name is not None:
            parts.append(name)
        elif number is not None:
            parts.append(int(number))
        elif quoted is not None:
            parts.append(quoted)
        else:
            parts.append(Named(named))
    return parts


def _base(location: ProblemLocation, data) -> tuple | None:
    if location.area in (SCENARIO, PROPAGATION, MISSION_SEQUENCE):
        return ()
    key = {SPACECRAFT: "spacecraft", GROUND_STATION: "ground_stations"}.get(location.area)
    if key is None or not isinstance(data, dict) or not isinstance(data.get(key), list):
        return None
    index_of = next((i for i, item in enumerate(data[key]) if isinstance(item, dict)
                     and item.get("name") == location.name), None)
    return None if index_of is None else (key, index_of)


def json_path(location: ProblemLocation | None, data) -> tuple | None:
    """The path in ``data`` (the text's ``json.loads``) of the place a
    problem is about: the deepest part of its field path that exists
    (a list item named by its ``name``, an index, a key); None when the
    problem names no spacecraft, station or section the data has."""
    if location is None:
        return None
    path = _base(location, data)
    if path is None:
        return None
    node = data
    for key in path:
        node = node[key]
    for part in field_parts(location.path):
        if isinstance(part, Named):
            if not isinstance(node, list):
                break
            found = next((i for i, item in enumerate(node) if isinstance(item, dict) and item.get("name") == part.name),
                         None)
            if found is None:
                break
            part = found
        if isinstance(node, dict) and isinstance(part, str) and part in node:
            node = node[part]
        elif isinstance(node, list) and isinstance(part, int) and 0 <= part < len(node):
            node = node[part]
        else:
            break
        path += (part,)
    return path


def mark_span(nodes: dict[tuple, Node], path: tuple) -> tuple[int, int] | None:
    """The characters to mark for the value at ``path``: a plain value
    itself; an object or a list by its key (not the whole block), or,
    for a list item, its ``name`` value, else its opening bracket. None
    for the whole document or a path not in ``nodes``."""
    node = nodes.get(path)
    if node is None or not path:
        return None
    if node.kind not in ("object", "array"):
        return node.start, node.end
    if node.key_start is not None:
        return node.key_start, node.key_end
    name = nodes.get(path + ("name",))
    if name is not None and name.kind == "string":
        return name.start, name.end
    return node.start, node.start + 1


_OPEN, _CLOSE = "{[", "}]"


def matching_bracket(text: str, position: int) -> int | None:
    """The offset of the bracket matching the one at ``position`` (a
    bracket outside a string), or None."""
    marks = [(t.start, text[t.start]) for t in tokens(text) if t.kind == "punctuation" and text[t.start] in "{}[]"]
    i = next((k for k, (place, _char) in enumerate(marks) if place == position), None)
    if i is None:
        return None
    char = marks[i][1]
    forward = char in _OPEN
    pair = _CLOSE[_OPEN.index(char)] if forward else _OPEN[_CLOSE.index(char)]
    depth = 0
    for place, c in (marks[i:] if forward else reversed(marks[:i + 1])):
        if c == char:
            depth += 1
        elif c == pair:
            depth -= 1
            if depth == 0:
                return place
    return None
