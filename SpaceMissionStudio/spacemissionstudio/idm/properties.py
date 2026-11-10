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

"""The properties a team keeps on an IDM-CIC equipment definition
(``docs/developer/idm-cic-integration.md``, section 17): its own
properties (``Property``, including the copies the categories it
implements give it) and its additional property values
(``AdditionalPropertyValue``, named and typed by their definition).

A property has a name, a value type (``Distance``, ``Mass``, ``Angle``...,
``DecimalWithoutUnit``, ``IntegerWithoutUnit``, ``Text``...) and a value,
which may be empty. The format's description gives no unit for the stored
value of a typed property, and none at all for ``DecimalWithoutUnit``:
which unit a value is in is for the user to say (``idm_properties``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import IdmError
from .values import number

#: Value types whose values are numbers.
NUMERIC_TYPES = ("Distance", "Angle", "Mass", "Area", "Volume", "Density", "AreaDensity", "MomentOfInertia",
                 "Velocity", "Time", "DecimalWithoutUnit", "IntegerWithoutUnit")


@dataclass(frozen=True)
class PropertyValue:
    """One property of an equipment: its name, value type, the value as
    written (None when empty) and as a number (None when it is not one),
    and where it was read (the property's ``fullId``)."""

    name: str
    value_type: str
    text: str | None
    number: float | None
    full_id: str


def _value(text: str | None, value_type: str, where: str) -> float | None:
    if text is None or not text.strip() or value_type not in NUMERIC_TYPES:
        return None
    try:
        return number(text, where)
    except IdmError:
        return None  # a number-typed value that does not read as one is listed as written, not used


def equipment_properties(model, equipment_full_id: str) -> list[PropertyValue]:
    """The properties of the equipment definition ``equipment_full_id``, in
    file order: its own, then its additional property values."""
    g = model.graph
    node = g.find(equipment_full_id)
    if node is None:
        return []
    found = []
    for prop in node.many("properties"):
        name = (prop.text("name") or prop.id or "").strip()
        value_type = prop.text("valueType") or "None"
        text = prop.text("value")
        found.append(PropertyValue(name, value_type, text, _value(text, value_type, prop.full_id), prop.full_id))
    for prop in node.many("additionalPropertyValues"):
        definition = g.find(prop.ref("additionalPropertyDefinition"))
        if definition is None:
            continue
        name = (definition.text("name") or definition.id or "").strip()
        value_type = definition.text("valueType") or "None"
        text = prop.text("value")
        found.append(PropertyValue(name, value_type, text, _value(text, value_type, prop.full_id), prop.full_id))
    return [p for p in found if p.name]
