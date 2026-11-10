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


"""Every export the GUI writes stays byte-identical to 1.1.0's (UI
overhaul M8): ``scripts/make_export_references.py`` writes them from fixed
inputs through the functions the GUI calls, and this compares each file
with the one 1.1.0 wrote (``tests/data/exports_1_1_0.zip``, written on
Linux). On Windows, files written in text mode end lines with CRLF, as
1.1.0's did there, so the comparison there ignores line endings.

Since 2026-10-28 a provenance record also holds the integrator's
tolerances (audit E3) and the run's seeds (E5), and since 2026-10-29 the
central body and its GM (transparency audit 3.1), the scenario file and
its hash, and the run's warnings (Phase 2b, 2f), and the effective
configuration (Phase 2c), and the project configuration (Phase 3b); and
the SIL report its provenance (Phase 2g). The two provenance files and the SIL report are
compared without those keys, which must be there; everything else in them,
and every other file, is still 1.1.0's byte for byte. Since 2026-11-03 the
Monte Carlo table is written with a provenance file beside it (Phase 9),
a new file 1.1.0 did not write: it is checked on its own."""

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
    for name in _NEW_FILES:  # written since 1.1.0, beside a file 1.1.0 wrote: there, and JSON
        assert name in written and json.loads((tmp_path / name).read_text(encoding="utf-8")), name
    written = [name for name in written if name not in _NEW_FILES]
    with zipfile.ZipFile(_REFERENCES) as references:
        assert written == sorted(references.namelist())
        for name in written:
            content = (tmp_path / name).read_bytes()
            if name.endswith("provenance.json"):
                content = _without_new_keys(content, name)
            elif name == "sil_report.json":
                content = _without_sil_provenance(content)
            assert _same_lines(content) == _same_lines(references.read(name)), name


# Files written since 1.1.0: the Monte Carlo table's provenance (Phase 9).
_NEW_FILES = ("monte_carlo_runs.csv.provenance.json",)

# Keys a provenance record gained after 1.1.0, removed before comparing.
_NEW_PROVENANCE_KEYS = ("integrator_relative_tolerance", "integrator_absolute_tolerance", "rng_seed", "rng_seeds",
                        "central_body", "central_body_mu_m3_s2", "scenario_file", "scenario_file_sha256",
                        "run_warnings", "effective_defaults", "effective_config_note", "device_parameters",
                        "scenario_file_migrations", "configuration")


def _without_new_keys(content: bytes, name: str) -> bytes:
    """``content``, a provenance file, without the keys added since 1.1.0,
    written as the record is written (``json.dumps(..., indent=2)``)."""
    record = json.loads(content)
    assert all(key in record for key in _NEW_PROVENANCE_KEYS), name
    for key in _NEW_PROVENANCE_KEYS:
        del record[key]
    return (json.dumps(record, indent=2) + ("\n" if content.endswith(b"\n") else "")).encode()


def _without_sil_provenance(content: bytes) -> bytes:
    """``content``, the SIL report, without its ``provenance`` (added since
    1.1.0), written as the report is written (``SilReport.to_json``)."""
    report = json.loads(content)
    del report["provenance"]
    return (json.dumps(report, indent=1, sort_keys=True, allow_nan=False)
            + ("\n" if content.endswith(b"\n") else "")).encode()


def _same_lines(content: bytes) -> bytes:
    """``content`` as it is; on Windows, with CRLF read as LF (see above)."""
    return content.replace(b"\r\n", b"\n") if os.name == "nt" else content
