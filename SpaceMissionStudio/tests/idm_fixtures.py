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
