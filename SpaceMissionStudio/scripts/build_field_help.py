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

"""Write ``spacemissionstudio/schema/field_help.json``: for each scenario
record (the dataclasses of ``spacemissionstudio/schema/scenario.py``), the
comment its source gives each field (unit, range, meaning): the comment
at the end of the field's line, with the comment lines under it that go
on in lower case, else the comment lines just above it.

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

from spacemissionstudio.schema import scenario  # noqa: E402

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


def build() -> dict:
    """``{record class name: {field: comment}}``, sorted."""
    records = {name: cls for name, cls in vars(scenario).items()
               if inspect.isclass(cls) and dataclasses.is_dataclass(cls) and cls.__module__ == scenario.__name__}
    return {name: dict(sorted(_help(cls).items())) for name, cls in sorted(records.items())}


def text() -> str:
    return json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    OUTPUT.write_text(text(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
