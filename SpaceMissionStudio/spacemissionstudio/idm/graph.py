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
"""An IDM-CIC ``model.xml`` as a graph of objects.

Every element that carries a ``fullId`` (or holds fields of its own) is
an object (:class:`Node`). Its child elements are its fields: text
(``<name>Panel</name>``), a nested object (``<position><Position .../>``),
a collection (``<shapes maxId="1"><Array>...</Array></shapes>``) or
references to objects elsewhere (``<unit><Equipment ref="..."/></unit>``).
One pass indexes every object by ``fullId``; references are looked up
when they are followed, so a reference the import does not need never
stops it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .errors import IdmError

#: Element nesting deeper than this is refused (the examples go to about 40).
MAX_DEPTH = 400
_DOCTYPE = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


@dataclass(eq=False)
class Node:
    """One object of the model: its element name (``tag``), its ``id`` and
    ``fullId``, its text fields, nested objects and references, and the
    object it sits in (``owner``)."""

    tag: str
    id: str = ""
    full_id: str = ""
    values: dict = field(default_factory=dict)  # {field: text}
    objects: dict = field(default_factory=dict)  # {field: [Node]}
    refs: dict = field(default_factory=dict)  # {field: [fullId]}
    owner: Node | None = None
    owner_field: str = ""

    def text(self, name: str, default: str | None = None) -> str | None:
        """The text of field ``name``, or ``default``."""
        return self.values.get(name, default)

    def many(self, name: str) -> list:
        """The objects of field ``name`` (a collection or one nested object)."""
        return self.objects.get(name, [])

    def one(self, name: str) -> Node | None:
        """The first object of field ``name``, or None."""
        found = self.objects.get(name)
        return found[0] if found else None

    def ref(self, name: str) -> str | None:
        """The first ``fullId`` field ``name`` refers to, or None."""
        found = self.refs.get(name)
        return found[0] if found else None

    def ref_list(self, name: str) -> list:
        """Every ``fullId`` field ``name`` refers to."""
        return self.refs.get(name, [])

    def __repr__(self) -> str:
        return f"Node({self.tag} {self.full_id or self.id!r})"


@dataclass
class Graph:
    """The parsed model: the root object, the objects by ``fullId``, the
    model version (``IdmData``'s ``version``) and what was noticed."""

    root: Node
    index: dict
    version: str = ""
    duplicates: int = 0

    def get(self, full_id: str, why: str = "") -> Node:
        """The object ``full_id`` names; :class:`IdmError` when there is none."""
        node = self.index.get(full_id)
        if node is None:
            raise IdmError(f"the model refers to {full_id!r}{' (' + why + ')' if why else ''}, which it does not "
                           "contain: the file is damaged or incomplete")
        return node

    def find(self, full_id: str | None) -> Node | None:
        """The object ``full_id`` names, or None."""
        return self.index.get(full_id) if full_id else None

    def follow(self, node: Node, name: str) -> Node | None:
        """The object ``node``'s field ``name`` refers to, or None when it
        refers to none; :class:`IdmError` when it refers to a missing one."""
        target = node.ref(name)
        return self.get(target, f"{node.full_id or node.tag}.{name}") if target else None

    def iter(self, tag: str | None = None):
        """Every object (of element name ``tag``), in file order."""
        stack = [self.root]
        while stack:
            node = stack.pop()
            if tag is None or node.tag == tag:
                yield node
            for name in reversed(list(node.objects)):
                stack.extend(reversed(node.objects[name]))


def parse(text: str) -> Graph:
    """The graph of ``model.xml``'s text. Refuses document type
    declarations and entities (a model has none), so no entity expansion
    can happen."""
    if _DOCTYPE.search(text):
        raise IdmError("model.xml declares a document type or entities, which an IDM-CIC model does not: refused")
    try:
        # Not defusedxml (not a dependency): the document type check above refuses entity declarations, and the
        # expat Python ships with (2.4.1 and later) limits entity amplification in any case.
        element = ET.fromstring(text)  # noqa: S314
    except ET.ParseError as exc:
        raise IdmError(f"model.xml is not well-formed XML: {exc}") from None
    if element.tag != "IDM":
        raise IdmError(f"model.xml's root element is <{element.tag}>, not <IDM>: not an IDM-CIC model")
    index: dict = {}
    counter = {"duplicates": 0}
    root = _node(element, None, "", index, counter, 0)
    data = element.find("IdmData")
    version = data.get("version", "") if data is not None else ""
    return Graph(root, index, version, counter["duplicates"])


def _is_reference(element) -> bool:
    return "ref" in element.attrib and len(element) == 0


def _node(element, owner, owner_field: str, index: dict, counter: dict, depth: int) -> Node:
    if depth > MAX_DEPTH:
        raise IdmError(f"model.xml nests elements more than {MAX_DEPTH} deep: refused")
    node = Node(element.tag, element.get("id", ""), element.get("fullId", ""), owner=owner, owner_field=owner_field)
    if node.full_id:
        if node.full_id in index:
            counter["duplicates"] += 1
        else:
            index[node.full_id] = node
    for child in element:
        name = child.tag
        items = list(child)
        if not items:
            if _is_reference(child):  # a bare reference as a field (not seen, but harmless)
                node.refs.setdefault(name, []).append(child.get("ref"))
            else:
                node.values[name] = (child.text or "").strip()
            continue
        if len(items) == 1 and items[0].tag == "Array":
            items = list(items[0])
        for item in items:
            if _is_reference(item):
                node.refs.setdefault(name, []).append(item.get("ref"))
            else:
                node.objects.setdefault(name, []).append(_node(item, node, name, index, counter, depth + 1))
    return node
