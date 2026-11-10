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
"""The IDM-CIC test fixtures: hand-written, synthetic ``model.xml`` texts
(``tests/data/idm/<name>/model.xml``; made-up names and values, nothing
from IDM-CIC's examples), zipped into ``.idm`` files at test time."""

import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "idm"


def model_xml(name: str = "demosat") -> str:
    """The fixture's ``model.xml`` text."""
    return (DATA / name / "model.xml").read_text(encoding="utf-8")


def write_idm(path: Path, text: str | None = None, entry: str = "model.xml", bom: bool = True,
              extra: dict | None = None) -> Path:
    """``path`` as a ``.idm`` (ZIP) holding ``text`` (the demosat model by
    default) as ``entry``, with a UTF-8 byte-order mark as IDM-CIC writes
    it, and any ``extra`` entries ``{name: bytes}``."""
    text = model_xml() if text is None else text
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(entry, (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path
