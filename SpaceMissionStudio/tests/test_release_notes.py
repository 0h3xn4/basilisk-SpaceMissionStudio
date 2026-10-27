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

"""The notes of a release draft (packaging/release_notes.py): the layout,
the parts taken from the CHANGELOG, and the sizes and digests of the
built files."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("release_notes", _ROOT / "packaging" / "release_notes.py")
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

_CHANGELOG = """# Changelog

## 2.0.0 (2027-01-01)

A summary that
wraps over two lines.

- **A feature.** It does a thing
  over two lines.
  - a nested point
- **A fix.**

### Who should update

Everyone who flies
formations.

### Known limits

- **Something:** not done
  yet.

## 1.9.0 (2026-12-01)

- Older.
"""


def _files(folder: Path, version: str = "2.0.0") -> dict:
    names = {
        "deb": f"spacemissionstudio_{version}_amd64.deb",
        "setup": f"spacemissionstudio-{version}-setup.exe",
        "wheel": f"spacemissionstudio-{version}-py3-none-any.whl",
        "sdist": f"spacemissionstudio-{version}.tar.gz",
    }
    for index, name in enumerate(names.values()):
        (folder / name).write_bytes(bytes([index]) * (2_000_000 + index))
    return {key: folder / name for key, name in names.items()}


def test_the_changelog_section_splits_into_summary_own_sections_and_news():
    """The paragraphs before the first item are the summary; "Who should
    update" and "Known limits" are taken out; the rest is what is new.
    Wrapped lines are joined, nested items keep their own line, and the
    next release's section is not included."""
    parts = release_notes.changelog_section(_CHANGELOG, "2.0.0")
    assert parts["summary"] == "A summary that wraps over two lines."
    assert parts["Who should update"] == "Everyone who flies formations."
    assert parts["new"] == "- **A feature.** It does a thing over two lines.\n  - a nested point\n- **A fix.**"
    assert parts["Known limits"] == "- **Something:** not done yet."
    assert "Older" not in "".join(parts.values())


def test_a_version_without_a_changelog_section_is_refused():
    """The workflow stops rather than publish notes without the changes."""
    with pytest.raises(release_notes.NotesError, match=r"## 3\.0\.0 \(date\)"):
        release_notes.changelog_section(_CHANGELOG, "3.0.0")


def test_unwrap_keeps_code_blocks_tables_headings_and_paragraph_breaks():
    """Only prose lines are joined."""
    text = "One\ntwo.\n\nThree.\n\n```bash\nsudo apt\ninstall\n```\n| a | b |\n|---|---|\n### Head\n1. first\n   more"
    assert release_notes.unwrap(text) == (
        "One two.\n\nThree.\n\n```bash\nsudo apt\ninstall\n```\n| a | b |\n|---|---|\n### Head\n1. first more")


def test_the_notes_have_every_section_with_the_files_sizes_and_digests(tmp_path):
    """Summary, who should update, downloads, install, the installers'
    SHA-256, what's new, contents, checks and known limits, in that order;
    sizes and digests are those of the files, the run is linked, and the
    release's own known limits follow the standing ones."""
    files = _files(tmp_path)
    notes = release_notes.render("2.0.0", tmp_path, "https://example.invalid/runs/7", _CHANGELOG)
    headings = [line for line in notes.splitlines() if line.startswith("## ")]
    assert headings == ["## Who should update", "## Downloads", "## Install or upgrade", "## Check your download",
                        "## What's new", "## What the installers contain", "## How this release was checked",
                        "## Known limits"]
    assert notes.startswith("A summary that wraps over two lines.\n")
    for key in ("deb", "setup"):
        assert hashlib.sha256(files[key].read_bytes()).hexdigest() in notes
    assert "| `spacemissionstudio-2.0.0-setup.exe` | 2.0 MB |" in notes
    assert "sudo apt install ./spacemissionstudio_2.0.0_amd64.deb" in notes
    assert "([run](https://example.invalid/runs/7))" in notes
    limits = notes.split("## Known limits")[1]
    assert limits.index("SmartScreen") < limits.index("not done yet")


def test_the_notes_name_the_bundled_versions_and_space_weather_of_this_checkout(tmp_path):
    """Python, Basilisk and PySide6 come from the files the installers are
    built from, and the space weather from the bundled CelesTrak file."""
    versions = release_notes.bundled_versions()
    assert versions["basilisk"] == "2.12.0"
    assert versions["python"].startswith("3.14.")
    end = release_notes.space_weather_end()
    assert len(end) == 10 and end[4] == "-" and end[7] == "-"
    _files(tmp_path)
    notes = release_notes.render("2.0.0", tmp_path, "https://example.invalid/runs/7", _CHANGELOG)
    assert f"Basilisk {versions['basilisk']}" in notes and f"observations to {end}" in notes


def test_a_missing_release_file_is_named(tmp_path):
    """Notes are never written for a release that lacks one of its files."""
    files = _files(tmp_path)
    files["setup"].unlink()
    with pytest.raises(release_notes.NotesError, match="setup.exe"):
        release_notes.render("2.0.0", tmp_path, "https://example.invalid/runs/7", _CHANGELOG)


def test_the_command_writes_the_notes_or_says_what_is_missing(tmp_path, capsys):
    """Exit status 0 with the notes on standard output; 1 with the reason."""
    _files(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_CHANGELOG, encoding="utf-8")
    common = ["--files", str(tmp_path), "--run-url", "https://example.invalid/runs/7", "--changelog", str(changelog)]
    assert release_notes.main(["--version", "2.0.0", *common]) == 0
    assert "## Downloads" in capsys.readouterr().out
    assert release_notes.main(["--version", "9.9.9", *common]) == 1
    assert "no section '## 9.9.9 (date)'" in capsys.readouterr().err


def test_the_current_changelog_renders_for_its_newest_release(tmp_path):
    """The CHANGELOG in this checkout parses: its newest section gives
    notes with a summary and the changes."""
    changelog = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = next(line for line in changelog.splitlines() if line.startswith("## ") and "(" in line)
    version = newest[3:].split(" (")[0]
    _files(tmp_path, version)
    notes = release_notes.render(version, tmp_path, "https://example.invalid/runs/7", changelog)
    assert "## What's new" in notes and notes.split("\n", 1)[0].strip()
