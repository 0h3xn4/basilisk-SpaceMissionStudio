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
1.1.0's did there, so the comparison there ignores line endings.

Since 2026-10-28 a provenance record also holds the integrator's
tolerances (audit E3) and the run's seeds (E5), and since 2026-10-29 the
central body and its GM (transparency audit 3.1), the scenario file and
its hash, and the run's warnings (Phase 2b, 2f). The two provenance files
are compared without those keys, which must be there; everything else in them, and every
other file, is still 1.1.0's byte for byte."""

import json
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
            content = (tmp_path / name).read_bytes()
            if name.endswith("provenance.json"):
                content = _without_new_keys(content, name)
            assert _same_lines(content) == _same_lines(references.read(name)), name


# Keys a provenance record gained after 1.1.0, removed before comparing.
_NEW_PROVENANCE_KEYS = ("integrator_relative_tolerance", "integrator_absolute_tolerance", "rng_seed", "rng_seeds",
                        "central_body", "central_body_mu_m3_s2", "scenario_file", "scenario_file_sha256",
                        "run_warnings")


def _without_new_keys(content: bytes, name: str) -> bytes:
    """``content``, a provenance file, without the keys added since 1.1.0,
    written as the record is written (``json.dumps(..., indent=2)``)."""
    record = json.loads(content)
    assert all(key in record for key in _NEW_PROVENANCE_KEYS), name
    for key in _NEW_PROVENANCE_KEYS:
        del record[key]
    return (json.dumps(record, indent=2) + ("\n" if content.endswith(b"\n") else "")).encode()


def _same_lines(content: bytes) -> bytes:
    """``content`` as it is; on Windows, with CRLF read as LF (see above)."""
    return content.replace(b"\r\n", b"\n") if os.name == "nt" else content
