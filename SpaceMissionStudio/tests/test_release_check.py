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

"""The check run before a release is tagged (packaging/release_check.py):
the version files, the CHANGELOG's newest section and its date, entries
left under Unreleased, an existing tag, the notes; and the commands it
prints when the commit is ready."""

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("release_check", _ROOT / "packaging" / "release_check.py")
release_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_check)

_CHANGELOG = """# Changelog

## 3.1.0 (2027-02-01)

A summary.

- **A feature.**

## 3.0.0 (2027-01-01)

- Older.
"""


def _tree(tmp_path: Path, version="3.1.0", iss=None, changelog=_CHANGELOG) -> Path:
    (tmp_path / "spacemissionstudio").mkdir()
    (tmp_path / "packaging" / "windows").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")
    (tmp_path / "spacemissionstudio" / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (tmp_path / "packaging" / "windows" / "spacemissionstudio.iss").write_text(
        f'#define MyAppVersion "{iss or version}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


def test_a_ready_commit_passes_and_gets_the_commands_to_tag_it(tmp_path):
    root = _tree(tmp_path)
    version, problems, passed = release_check.check(root, tags="abc\trefs/tags/spacemissionstudio-v3.0.0",
                                                    today="2027-02-01")
    assert version == "3.1.0" and problems == [] and len(passed) == 5
    text = release_check.report(version, "0123456789abcdef", problems, passed)
    assert 'git tag -a spacemissionstudio-v3.1.0 0123456789abcdef -m "SpaceMissionStudio 3.1.0"' in text
    assert "git push origin spacemissionstudio-v3.1.0" in text and "Ready to tag" in text


def test_disagreeing_version_files_are_named(tmp_path):
    root = _tree(tmp_path, iss="3.0.9")
    _, problems, _ = release_check.check(root, today="2027-02-01")
    assert len(problems) == 1 and "spacemissionstudio.iss 3.0.9" in problems[0]


def test_a_heading_dated_another_day_is_refused(tmp_path):
    """2.7.0's tag went up a day after its heading's date."""
    root = _tree(tmp_path)
    _, problems, _ = release_check.check(root, today="2027-02-02")
    assert problems == ["CHANGELOG.md dates 3.1.0 2027-02-01; today is 2027-02-02. "
                        "Date the heading today, merge that, then tag."]


def test_a_changelog_without_the_version_is_refused(tmp_path):
    root = _tree(tmp_path, version="3.2.0")
    _, problems, _ = release_check.check(root, today="2027-02-01")
    assert problems == ["CHANGELOG.md's newest section is 3.1.0, not 3.2.0."]


def test_unreleased_entries_left_out_are_refused(tmp_path):
    changelog = _CHANGELOG.replace("## 3.1.0", "## Unreleased\n\n- **Left behind.**\n- **And this.**\n\n## 3.1.0", 1)
    root = _tree(tmp_path, changelog=changelog)
    _, problems, _ = release_check.check(root, today="2027-02-01")
    assert problems == ["CHANGELOG.md has 2 Unreleased entries that 3.1.0 would leave out; move them under 3.1.0."]


def test_an_existing_tag_is_refused_whether_annotated_or_named(tmp_path):
    root = _tree(tmp_path)
    for tags in ("x\trefs/tags/spacemissionstudio-v3.1.0\nx\trefs/tags/spacemissionstudio-v3.1.0^{}",
                 "spacemissionstudio-v3.1.0"):
        _, problems, _ = release_check.check(root, tags=tags, today="2027-02-01")
        assert problems == ["The tag spacemissionstudio-v3.1.0 already exists: raise the version for a new release."]
    assert not release_check.tag_exists("3.1.0", "x\trefs/tags/spacemissionstudio-v3.1.0rc1")


def test_the_command_fails_on_a_problem_and_says_not_ready(capsys, monkeypatch):
    """This checkout: 2.7.0 is tagged, so the check fails and says why."""
    assert release_check.main(["--commit", "f" * 40, "--tags", "spacemissionstudio-v" + release_check.versions()[
        "pyproject.toml"]]) == 1
    out = capsys.readouterr().out
    assert "Not ready to tag" in out and "already exists" in out
