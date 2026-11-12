#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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

"""ECSS documents may not be reproduced without ESA's consent
(docs/legal/DATA_TERMS.md section 8, decision D3; risk register R4): the
compliance requirement lists keep each ECSS requirement's clause,
identifier and the audit's own columns, and point to the standard
instead of quoting it. These tests keep the wording out."""

import csv
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_COMPLIANCE = _ROOT / "compliance"
_spec = importlib.util.spec_from_file_location("extract_requirements",
                                               _COMPLIANCE / "tools" / "extract_requirements.py")
extract_requirements = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract_requirements)


def _rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_the_ecss_requirement_lists_hold_references_not_wording():
    """Each of the four ECSS lists: every row's text is the reference to
    its clause and requirement, nothing more; the lists keep their rows."""
    files = sorted((_COMPLIANCE / "requirements").glob("ECSS-*.csv"))
    assert [f.stem for f in files] == ["ECSS-E-ST-10-04C", "ECSS-E-ST-10-09C", "ECSS-E-ST-40C", "ECSS-Q-ST-80C"]
    for path in files:
        rows = _rows(path)
        assert len(rows) > 50, path.name
        for row in rows:
            assert row["requirement_text"] == extract_requirements.ecss_reference(path.stem, row), (path.name, row["ID"])


def test_the_compliance_matrix_quotes_no_ecss_wording():
    """The matrix built from the lists carries the same references."""
    rows = _rows(_COMPLIANCE / "compliance_matrix.csv")
    ecss = [r for r in rows if not r["standard"].startswith("CCSDS")]
    assert len(ecss) > 1000
    for row in ecss:
        assert row["requirement_text"].endswith("wording not reproduced (ECSS copyright); see the standard"), row["ID"]


def test_an_extracted_ecss_row_gets_the_reference():
    """The extraction tool writes the reference, not the wording it read."""
    row = {"ID": "5.2.2.1a", "requirement_text": "The customer shall derive ..."}
    assert extract_requirements.ecss_reference("ECSS-E-ST-40C", row) == (
        "ECSS-E-ST-40C 5.2.2.1a: wording not reproduced (ECSS copyright); see the standard")
