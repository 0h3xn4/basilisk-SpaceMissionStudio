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
"""Where the app finds its licence texts (spacemissionstudio.legal), and what
the About box states (legal milestone M2: EUPL-1.2 from the release after
2.6.0)."""

from __future__ import annotations

from pathlib import Path

from spacemissionstudio import legal

ROOT = Path(__file__).resolve().parents[1]


def test_the_checkout_has_the_licence_in_english_and_german_and_the_notices():
    """From a source checkout: LICENSE, LICENSE.de and THIRD_PARTY_NOTICES, in that order."""
    found = legal.licence_files(prefix=ROOT / "no-such-prefix")
    names = [entry.path.name for entry in found]
    assert names == ["LICENSE", "LICENSE.de", "THIRD_PARTY_NOTICES"]
    assert found[0].path.read_text(encoding="utf-8").startswith("EUROPEAN UNION PUBLIC LICENCE v. 1.2")
    assert found[1].path.read_text(encoding="utf-8").startswith("OPEN-SOURCE-LIZENZ FÜR DIE EUROPÄISCHE UNION v. 1.2")


def test_the_installers_full_notices_win_over_the_wheels(tmp_path):
    """An installer's bundled Python has the full list at its top; it is shown instead of the wheel's own."""
    (tmp_path / "THIRD_PARTY_NOTICES.txt").write_text("all of the installer", encoding="utf-8")
    notices = legal.licence_files(prefix=tmp_path)[-1]
    assert notices.title == "Third-party notices"
    assert notices.path == tmp_path / "THIRD_PARTY_NOTICES.txt"


def test_nothing_found_is_an_empty_list_not_an_error(tmp_path, monkeypatch):
    """A broken install lists nothing; the window then says where the files are."""
    monkeypatch.setattr(legal, "_distribution_file", lambda name: None)
    assert legal.licence_files(prefix=tmp_path, checkout=tmp_path) == []


def test_the_about_text_names_the_licence_the_isc_releases_and_basilisk():
    """The About box: the copyright line, "Licensed under the EUPL", the last ISC release and Basilisk's own licence."""
    text = legal.about_html()
    assert legal.COPYRIGHT in text and "Licensed under the EUPL" in text
    assert "2.6.0" in text and "ISC" in text and "Basilisk" in text


def test_every_source_file_carries_the_eupl_notice():
    """Every Python and shell file of the app, its tests and tools names its licence (SPDX) right after the
    copyright notice, as the EUPL asks. The flight-software templates are the generated project's text and
    keep their notice (an output may not change without the owner's approval)."""
    skip = ("spacemissionstudio/fsw_export/templates/", "tests/golden/", "tests/data/", "packaging/legal/texts/")
    missing = []
    for folder in ("spacemissionstudio", "tests", "scripts", "packaging", "compliance", "examples"):
        for path in sorted((ROOT / folder).rglob("*")):
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix not in (".py", ".sh") or relative.startswith(skip) or "__pycache__" in relative:
                continue
            head = path.read_text(encoding="utf-8", errors="replace")[:1200]
            if "SPDX-License-Identifier: EUPL-1.2" not in head or "Licensed under the EUPL" not in head:
                missing.append(relative)
    assert missing == []
