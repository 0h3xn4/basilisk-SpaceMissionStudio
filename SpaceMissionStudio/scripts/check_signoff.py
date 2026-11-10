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
"""Check the sign-off of a pull request's commits (docs/legal/RISK_REGISTER.md R9).

Every commit in ``BASE..HEAD`` that changes a file under ``SpaceMissionStudio/``
must carry a ``Signed-off-by:`` trailer with its author's e-mail address, the
line ``git commit -s`` writes (the Developer's Certificate of Origin 1.1; the
root pull-request template links it). Merge commits are skipped. Run from
anywhere inside the repository::

    python SpaceMissionStudio/scripts/check_signoff.py BASE HEAD

The workflow ``spacemissionstudio-signoff.yml`` runs it for pull requests from
forks only: the maintainer's own branches are not checked. Exit status 1 lists
each commit without a sign-off. No network, standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys

PATH = "SpaceMissionStudio/"
_TRAILER = re.compile(r"^Signed-off-by:\s*(?P<name>.+?)\s*<(?P<email>[^<>\s]+)>\s*$", re.MULTILINE)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def commits(base: str, head: str) -> list[str]:
    """The non-merge commits of ``base..head`` that change a file under ``SpaceMissionStudio/``, oldest first."""
    out = _git("rev-list", "--reverse", "--no-merges", f"{base}..{head}", "--", PATH)
    return [line for line in out.splitlines() if line]


def problem(commit: str) -> str | None:
    """Why ``commit`` fails the check, or ``None`` when its author signed it off."""
    author = _git("show", "-s", "--format=%ae", commit).strip()
    message = _git("show", "-s", "--format=%B", commit)
    emails = [match["email"].lower() for match in _TRAILER.finditer(message)]
    subject = message.splitlines()[0] if message.strip() else ""
    if not emails:
        return f"{commit[:12]} {subject!r}: no Signed-off-by line"
    if author.lower() not in emails:
        return f"{commit[:12]} {subject!r}: no Signed-off-by line with the author's e-mail address"
    return None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    base, head = args
    checked = commits(base, head)
    problems = [p for p in map(problem, checked) if p]
    for line in problems:
        print(line)
    if problems:
        print(f"{len(problems)} of {len(checked)} commits are not signed off. Add the line with "
              "'git commit -s' (or 'git rebase --signoff BASE') and push again.")
        return 1
    print(f"{len(checked)} commits changing {PATH} checked: all signed off.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
