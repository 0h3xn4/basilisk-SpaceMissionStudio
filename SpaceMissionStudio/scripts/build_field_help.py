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

"""Write ``spacemissionstudio/schema/field_help.json``: for each scenario
record (the dataclasses of ``spacemissionstudio/schema/scenario.py``), the
comment its source gives each field (unit, range, meaning): the comment
at the end of the field's line, with the comment lines under it that go
on in lower case, else the comment lines just above it; for a mission
step (``schema/command.py``'s ``Command``), its docstring's "Args:".

The JSON page's completion and hover help read it (``schema/fields.py``,
decision JE-05 of ``docs/developer/json-editor.md``): an installed
program has no source to read the comments from. The code is the
definition; ``tests/test_schema_fields.py`` checks that the file is what
this script writes. Usage::

    python scripts/build_field_help.py
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from spacemissionstudio.schema import command, scenario  # noqa: E402

OUTPUT = ROOT / "spacemissionstudio" / "schema" / "field_help.json"
_FIELD = re.compile(r"^    ([a-z_][a-z0-9_]*)\s*:\s*[^=#]+(?:=[^#]*)?(?:#\s*(.*))?$")
_COMMENT = re.compile(r"^    #\s?(.*)$")


def _help(cls) -> dict[str, str]:
    """``{field: comment}`` from ``cls``'s source (module docstring)."""
    names = {f.name for f in dataclasses.fields(cls)}
    found: dict[str, str] = {}
    above: list[str] = []
    continuing = ""  # the field whose end-of-line comment the next comment lines may go on with
    for line in inspect.getsource(cls).splitlines():
        comment = _COMMENT.match(line)
        if comment:
            words = comment.group(1).strip()
            if continuing and not above and words[:1].islower():  # the end-of-line comment goes on
                found[continuing] += " " + words
            else:
                continuing = ""
                above.append(words)
            continue
        field = _FIELD.match(line)
        continuing = ""
        if field and field.group(1) in names and field.group(1) not in found:
            own = (field.group(2) or "").strip()
            text = own or " ".join(part for part in above if part)
            if text:
                found[field.group(1)] = text
                continuing = field.group(1) if own else ""
        above = []
    return {name: " ".join(text.split()) for name, text in found.items()}


def _docstring_args(cls) -> dict[str, str]:
    """``{field: text}`` from the "Args:" section of ``cls``'s docstring
    (a record whose fields are described there, as ``Command``'s)."""
    found: dict[str, str] = {}
    lines = (inspect.getdoc(cls) or "").splitlines()
    if "Args:" not in lines:
        return found
    current = ""
    for line in lines[lines.index("Args:") + 1:]:
        entry = re.match(r"^    ([a-z_]+): (.*)$", line)
        if entry:
            current = entry.group(1)
            found[current] = entry.group(2)
        elif line.startswith("        ") and current:
            found[current] += " " + line.strip()
        elif line.strip():
            break
    return {name: " ".join(text.split()) for name, text in found.items()}


def build() -> dict:
    """``{record class name: {field: comment}}``, sorted."""
    records = {name: cls for name, cls in vars(scenario).items()
               if inspect.isclass(cls) and dataclasses.is_dataclass(cls) and cls.__module__ == scenario.__name__}
    found = {name: dict(sorted(_help(cls).items())) for name, cls in sorted(records.items())}
    found["Command"] = dict(sorted(_docstring_args(command.Command).items()))
    return dict(sorted(found.items()))


def text() -> str:
    return json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    OUTPUT.write_text(text(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
