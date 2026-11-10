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

"""Completion and help for the JSON page (decisions JE-04 to JE-06 of
``docs/developer/json-editor.md``). No Qt here.

:func:`completions` says what can be typed at a place of the scenario's
text (``json_positions.context_at``): at a key, the fields of the record
there (``schema.fields.record_at``) the object does not have yet, each
inserted with its default; at a value, the field's fixed choices, the
names it can refer to (a ground station, a spacecraft, a part, a
material: from the scenario as last read), or ``true``/``false``.
Only what starts with the text typed is offered, then what contains it.
:func:`help_at` describes the field whose key is at a place.

A device's ``params`` and a mission step's ``params`` hold keys that
depend on the ``kind`` beside them (:func:`fields_at`): a device's are
those its form offers (``sensor_actuator_editor``'s specs, with the
wheel and thruster models as choices), a step's those ``Command``
reads (``schema.fields.COMMAND_PARAMS``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from functools import cache

from ..schema import fields
from . import json_positions


@dataclass(frozen=True)
class Completion:
    """One thing to offer: its ``label``, the JSON text ``insert`` puts in
    place of the word typed, the part of it to select afterwards (``select``,
    as offsets into ``insert``: the value of a new key, to type over) and
    a description (``detail``)."""

    label: str
    insert: str
    detail: str = ""
    select: tuple[int, int] | None = None


@cache
def device_params(kind: str) -> tuple:
    """The parameters a device of ``kind`` takes, as its form offers them
    (``fields.FieldInfo``); () for a kind the form has none for."""
    from ..schema.scenario import RW_TYPES, THRUSTER_TYPES
    from .sensor_actuator_editor import _KIND_PARAM_SPECS

    choices = {"rw_type": RW_TYPES, "thruster_type": THRUSTER_TYPES}
    found = []
    for spec in _KIND_PARAM_SPECS.get(kind, []):
        example = spec.example
        kind_of = ("boolean" if isinstance(example, bool) else "number" if isinstance(example, (int, float))
                   else "array" if isinstance(example, list) else "string")
        found.append(fields.FieldInfo(spec.key, kind_of, json.dumps(example), spec.required, spec.help_text,
                                      tuple(choices.get(spec.key, ()))))
    return tuple(found)


def _kind_beside(text: str, path: tuple):
    """The ``kind`` of the object at ``path`` in ``text``, as far as it is read."""
    node = json_positions.index(text).get(tuple(path) + ("kind",))
    if node is None or node.kind != "string":
        return None
    return json.loads(text[node.start:node.end])


def fields_at(text: str, path) -> tuple | None:
    """The fields the object at ``path`` can hold: its record's, or for a
    device's or a mission step's ``params`` those of the kind beside it;
    None when nothing is known there."""
    path = tuple(path)
    record = fields.record_at(path)
    if record is not None:
        return fields.fields(record)
    if not path or path[-1] != "params":
        return None
    owner = fields.record_at(path[:-1])
    if owner is None:
        return None
    kind = _kind_beside(text, path[:-1])
    if owner.__name__ in ("SensorConfig", "ActuatorConfig") and isinstance(kind, str):
        return device_params(kind) or None
    if owner.__name__ == "Command":
        return fields.command_params(kind)
    return None


def field_at(text: str, path, key: str):
    """The ``fields.FieldInfo`` of ``key`` in the object at ``path``, or None."""
    found = fields_at(text, path)
    return next((f for f in found if f.name == key), None) if found else None


def _matching(items: list[Completion], prefix: str) -> list[Completion]:
    if not prefix:
        return items
    low = prefix.lower()
    first = [c for c in items if c.label.lower().startswith(low)]
    return first + [c for c in items if low in c.label.lower() and c not in first]


def completions(text: str, position: int, data=None) -> tuple[int, int, list[Completion]]:
    """``(start, end, completions)`` at ``position``: the characters a
    completion replaces and what is offered (module docstring). ``data`` is
    the scenario's JSON as last read, for the names a field refers to."""
    context = json_positions.context_at(text, position)
    if context is None:
        return position, position, []
    if context.kind == "key":
        known = fields_at(text, context.path)
        if known is None:
            return context.start, context.end, []
        items = []
        for info in known:
            if info.name in context.keys:
                continue
            key = json.dumps(info.name) + ": "
            value = fields.empty_value(info)
            items.append(Completion(info.name, key + value, info.describe(), (len(key), len(key) + len(value))))
        return context.start, context.end, _matching(items, context.prefix)
    *parent, key = context.path
    if not isinstance(key, str):
        return context.start, context.end, []
    info = field_at(text, parent, key)
    if info is None:
        return context.start, context.end, []
    if info.choices:
        values = list(info.choices)
    elif info.refers:
        values = fields.names(data, info.refers, tuple(parent))
    elif info.kind == "boolean":
        return context.start, context.end, _matching([Completion(v, v, info.describe()) for v in ("true", "false")],
                                                       context.prefix)
    else:
        values = []
    items = [Completion(v, json.dumps(v), info.describe()) for v in values]
    return context.start, context.end, _matching(items, context.prefix)


def help_at(text: str, position: int) -> str:
    """The description of the field whose key is at ``position``, or ""."""
    found = json_positions.key_at(text, position)
    if found is None:
        return ""
    path, key = found
    info = field_at(text, path, key)
    return info.describe() if info is not None else ""
