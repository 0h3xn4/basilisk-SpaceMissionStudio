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
"""Copy the user manual and its images into the package, so installs carry
the help the app shows offline (UX/UI guidelines, "help built in").

``USER_MANUAL.md`` and ``docs/images/`` stay the source; the copy in
``spacemissionstudio/help/`` is package data. ``tests/test_help.py`` fails
when the copy is out of date: run this script after editing the manual.

Usage::

    python scripts/sync_help.py
"""

import re
import shutil
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent
MANUAL = TOOL / "USER_MANUAL.md"
HELP = TOOL / "spacemissionstudio" / "help"
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def manual_images(text: str) -> list:
    """Relative paths of the images the manual shows."""
    return [path for path in IMAGE.findall(text) if not path.startswith(("http://", "https://"))]


def main() -> int:
    text = MANUAL.read_text(encoding="utf-8")
    if HELP.exists():
        shutil.rmtree(HELP)
    HELP.mkdir(parents=True)
    shutil.copyfile(MANUAL, HELP / MANUAL.name)
    for relative in manual_images(text):
        target = HELP / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TOOL / relative, target)
    print(f"copied {MANUAL.name} and {len(manual_images(text))} image(s) to {HELP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
