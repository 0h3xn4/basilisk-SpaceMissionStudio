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
"""Where the licence texts of an installed SpaceMissionStudio are, for
Help › Third-Party Licences (``gui.licences_dialog``) and the About box.

The files are found, not written: a source checkout has ``LICENSE``,
``LICENSE.de`` and ``THIRD_PARTY_NOTICES`` beside ``pyproject.toml``; an
installed wheel has them in its ``.dist-info/licenses/``; the installers'
bundled Python also has ``THIRD_PARTY_NOTICES.txt`` at its top, the full list
of everything the installer carries (``packaging/legal/README.md``). No
network, no Qt.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

#: The app's own licence, as the About box states it.
LICENCE_NAME = "European Union Public Licence v. 1.2 (EUPL-1.2)"
COPYRIGHT = "Copyright (c) 2026 0h3xn4"
#: The last release published under the ISC licence.
LAST_ISC_RELEASE = "2.6.0"

_CHECKOUT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class LicenceFile:
    """One text to show: its title and where it is."""

    title: str
    path: Path


def _distribution_file(name: str) -> Path | None:
    """A file of the installed ``spacemissionstudio`` distribution's
    ``licenses/`` folder, if it is installed and has it."""
    try:
        files = metadata.distribution("spacemissionstudio").files or []
    except metadata.PackageNotFoundError:
        return None
    for entry in files:
        if entry.name == name and "licenses" in entry.parts:
            path = Path(entry.locate())
            if path.is_file():
                return path
    return None


def _first(*candidates: Path | None) -> Path | None:
    return next((path for path in candidates if path is not None and path.is_file()), None)


def licence_files(prefix: Path | None = None, checkout: Path | None = None) -> list[LicenceFile]:
    """The licence texts found, in the order they are shown: the app's licence
    (English, then German), then the third-party notices; the installers'
    full notices are preferred over the wheel's list of its own assets.
    ``prefix`` and ``checkout`` are for tests (default: ``sys.prefix`` and
    the source folder this module was imported from)."""
    prefix = Path(sys.prefix) if prefix is None else prefix
    checkout = _CHECKOUT if checkout is None else checkout
    found = []
    for title, name in (("Licence (English)", "LICENSE"), ("Licence (Deutsch)", "LICENSE.de")):
        path = _first(_distribution_file(name), checkout / name)
        if path is not None:
            found.append(LicenceFile(title, path))
    notices = _first(prefix / "THIRD_PARTY_NOTICES.txt", _distribution_file("THIRD_PARTY_NOTICES"),
                     checkout / "THIRD_PARTY_NOTICES")
    if notices is not None:
        found.append(LicenceFile("Third-party notices", notices))
    return found


def about_html() -> str:
    """The licence lines of the About box (rich text)."""
    return (f"{COPYRIGHT}. Licensed under the EUPL ({LICENCE_NAME}).<br>"
            f"Releases up to and including {LAST_ISC_RELEASE} were published under the ISC licence. "
            "Basilisk, which SpaceMissionStudio uses, keeps its own ISC licence and copyright holders.<br>"
            "The licences of everything the package contains: Help › Third-Party Licences.")
