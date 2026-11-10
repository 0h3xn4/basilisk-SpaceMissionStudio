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
"""Check the Phase 4 documents in ``compliance/docs`` against their DRDs
(remediation R14).

Each document names its DRD on its first lines, as ``DRD: <standard>
Annex <letter>`` (for example ``DRD: ECSS-E-ST-40C Annex D``). Every section
of that DRD (the ``<n>`` / ``<n.m>`` of the requirement IDs in
``compliance/requirements/<standard>.csv``) must appear in the document as a
heading that ends with ``(<letter>.2.1<n>)`` and is followed by text. A
section may say why it is not applicable, or what it waits for (a human
action); it may not be missing or empty. Usage::

    python compliance/tools/check_drds.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
_DRD = re.compile(r"^DRD: (ECSS-[A-Z]-ST-[0-9-]+C) Annex ([A-Z])", re.MULTILINE)


def drd_sections(standard: str, annex: str) -> list:
    """Section identifiers of a DRD, in document order, e.g. ['1', '2', '4.1']."""
    sections = []
    with open(ROOT / "requirements" / f"{standard}.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            match = re.match(rf"^{annex}\.2\.1<([0-9.]+)>", row["ID"])
            if match and match.group(1) not in sections:
                sections.append(match.group(1))
    return sections


def check(path: Path) -> list:
    """Problems in one document (empty when it covers its DRD)."""
    text = path.read_text(encoding="utf-8")
    header = _DRD.search(text[:2000])
    if not header:
        return []
    standard, annex = header.groups()
    problems = []
    lines = text.splitlines()
    for section in drd_sections(standard, annex):
        marker = f"({annex}.2.1<{section}>)"
        index = next((i for i, line in enumerate(lines) if line.startswith("#") and line.rstrip().endswith(marker)),
                     None)
        if index is None:
            problems.append(f"{path.name}: no heading for {standard} {annex}.2.1<{section}>")
            continue
        body = []
        for line in lines[index + 1:]:
            if line.startswith("#"):
                break
            body.append(line.strip())
        if not any(body):
            problems.append(f"{path.name}: section {annex}.2.1<{section}> is empty")
    return problems


def main() -> int:
    documents = sorted(DOCS.glob("*.md"))
    problems, checked = [], []
    for path in documents:
        found = check(path)
        problems += found
        if _DRD.search(path.read_text(encoding="utf-8")[:2000]):
            checked.append(path.name)
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"{len(checked)} documents checked against their DRDs: {', '.join(checked) or 'none'}; "
          f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
