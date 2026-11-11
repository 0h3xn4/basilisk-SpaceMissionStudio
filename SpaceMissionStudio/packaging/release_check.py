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

"""Checks that a commit is ready to be tagged as a release, before the tag
(``docs/developer/releasing.md``, section 6). The "SpaceMissionStudio
release check" workflow runs it, with CI's result for the commit and the
pip-audit step; it can also be run locally::

    python3 packaging/release_check.py --commit "$(git rev-parse HEAD)" \\
        --tags "$(git ls-remote --tags origin)"

It checks what made earlier releases go wrong (``releasing.md``, the 2.7.0
paragraph):

* the version files agree (``pyproject.toml``, ``spacemissionstudio/__init__.py``,
  the Windows installer script), as the release workflow requires;
* the CHANGELOG's newest section is that version, dated today (UTC), so
  the tagged CHANGELOG carries the release's date;
* no ``## Unreleased`` entries are left above it, which would be left out
  of the release;
* the tag ``spacemissionstudio-vX.Y.Z`` does not exist yet;
* the release notes render from the CHANGELOG section.

When everything passes it prints the commit to tag and the commands.
Exit status 0 when ready, 1 when not. Standard library only.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG_PREFIX = "spacemissionstudio-v"


def _release_notes():
    spec = importlib.util.spec_from_file_location("release_notes", Path(__file__).with_name("release_notes.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def versions(root: Path = ROOT) -> dict[str, str | None]:
    """The version each version file states (None when it states none)."""
    def find(path: str, pattern: str) -> str | None:
        match = re.search(pattern, (root / path).read_text(encoding="utf-8"), re.MULTILINE)
        return match.group(1) if match else None
    return {
        "pyproject.toml": find("pyproject.toml", r'^version = "([^"]+)"$'),
        "spacemissionstudio/__init__.py": find("spacemissionstudio/__init__.py", r'^__version__ = "([^"]+)"'),
        "packaging/windows/spacemissionstudio.iss": find("packaging/windows/spacemissionstudio.iss",
                                                         r'^#define MyAppVersion "([^"]+)"'),
    }


def newest_section(changelog: str) -> tuple[str, str] | None:
    """The newest released section's version and date, ``## X.Y.Z (date)``."""
    match = re.search(r"^## (\d+\.\d+\.\d+) \((\d{4}-\d{2}-\d{2})\)", changelog, re.MULTILINE)
    return (match.group(1), match.group(2)) if match else None


def unreleased_entries(changelog: str) -> list[str]:
    """The list items of a ``## Unreleased`` section, if there is one."""
    match = re.search(r"^## Unreleased\s*$(.*?)(?=^## )", changelog, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.startswith("- ")]


def tag_exists(version: str, tags: str) -> bool:
    """Whether ``git ls-remote --tags`` output (or plain tag names) has the tag."""
    tag = f"{TAG_PREFIX}{version}"
    return any(line.split()[-1].removeprefix("refs/tags/").removesuffix("^{}") == tag
               for line in tags.splitlines() if line.strip())


def check(root: Path = ROOT, tags: str = "", today: str | None = None) -> tuple[str | None, list[str], list[str]]:
    """``(version, problems, passed)``: what blocks the tag, and what passed."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    problems, passed = [], []
    found = versions(root)
    distinct = set(found.values())
    version = found["pyproject.toml"]
    if None in distinct or len(distinct) != 1:
        problems.append("The version files disagree: " + ", ".join(f"{k} {v}" for k, v in found.items()) + ".")
    else:
        passed.append(f"Version files agree: {version}.")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    section = newest_section(changelog)
    if section is None:
        problems.append("CHANGELOG.md has no section '## X.Y.Z (YYYY-MM-DD)'.")
    elif section[0] != version:
        problems.append(f"CHANGELOG.md's newest section is {section[0]}, not {version}.")
    elif section[1] != today:
        problems.append(f"CHANGELOG.md dates {version} {section[1]}; today is {today}. "
                        f"Date the heading today, merge that, then tag.")
    else:
        passed.append(f"CHANGELOG.md has {version}, dated today ({today}).")
    left = unreleased_entries(changelog)
    if left:
        problems.append(f"CHANGELOG.md has {len(left)} Unreleased entr{'y' if len(left) == 1 else 'ies'} "
                        f"that {version} would leave out; move them under {version}.")
    else:
        passed.append("No Unreleased entries are left out.")
    if version and tag_exists(version, tags):
        problems.append(f"The tag {TAG_PREFIX}{version} already exists: raise the version for a new release.")
    elif version:
        passed.append(f"The tag {TAG_PREFIX}{version} does not exist yet.")
    if version and section and section[0] == version:
        try:
            parts = _release_notes().changelog_section(changelog, version)
            if not parts["summary"] or not parts["new"]:
                problems.append(f"The {version} section has no summary or no changes for the release notes.")
            else:
                passed.append("The release notes render from the CHANGELOG section.")
        except Exception as exc:  # the notes' own error, shown as is
            problems.append(f"The release notes do not render: {exc}")
    return version, problems, passed


def report(version: str | None, commit: str, problems: list[str], passed: list[str]) -> str:
    """The result as Markdown (the workflow's summary)."""
    lines = [f"# Release check: {version or '?'} on `{commit[:12] or '?'}`", ""]
    lines += [f"- PASS: {p}" for p in passed] + [f"- **FAIL:** {p}" for p in problems] + [""]
    if problems:
        lines.append("**Not ready to tag.** Fix the failures above, merge, and run the check again.")
    else:
        tag = f"{TAG_PREFIX}{version}"
        lines += ["**Ready to tag.** From a clone of the repository:", "", "```bash", "git fetch origin",
                  f'git tag -a {tag} {commit} -m "SpaceMissionStudio {version}"', f"git push origin {tag}", "```", "",
                  "Then wait for the release workflow's draft (Actions > SpaceMissionStudio release), check its "
                  "files, and only then publish it."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--commit", default="", help="the commit that would be tagged (full SHA)")
    parser.add_argument("--tags", default="", help="the existing tags: git ls-remote --tags output, or names")
    parser.add_argument("--today", default=None, help="the date to check against (YYYY-MM-DD); default today, UTC")
    args = parser.parse_args(argv)
    version, problems, passed = check(ROOT, args.tags, args.today)
    sys.stdout.write(report(version, args.commit, problems, passed))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
