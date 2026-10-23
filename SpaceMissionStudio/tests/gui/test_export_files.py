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


"""Every export the GUI writes stays byte-identical to 1.1.0's (UI
overhaul M8): ``scripts/make_export_references.py`` writes them from fixed
inputs through the functions the GUI calls, and this compares each file
with the one 1.1.0 wrote (``tests/data/exports_1_1_0.zip``, written on
Linux). On Windows, files written in text mode end lines with CRLF, as
1.1.0's did there, so the comparison there ignores line endings."""

import os
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
_REFERENCES = _ROOT / "tests" / "data" / "exports_1_1_0.zip"


def test_every_export_is_byte_identical_to_1_1_0(qtbot, tmp_path):
    """The results CSVs and provenance, the events CSV, the Mission Output
    CSV and its provenance, the Monte Carlo table, the budget CSV, the
    ``.obj`` model and the SIL report: the same files, every byte."""
    from make_export_references import write_all

    written = write_all(tmp_path)
    with zipfile.ZipFile(_REFERENCES) as references:
        assert written == sorted(references.namelist())
        for name in written:
            assert _same_lines((tmp_path / name).read_bytes()) == _same_lines(references.read(name)), name


def _same_lines(content: bytes) -> bytes:
    """``content`` as it is; on Windows, with CRLF read as LF (see above)."""
    return content.replace(b"\r\n", b"\n") if os.name == "nt" else content
