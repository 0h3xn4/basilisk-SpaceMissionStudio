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
"""The sign-off check of pull requests from forks (scripts/check_signoff.py,
docs/legal/RISK_REGISTER.md R9), on small repositories made in a temporary folder."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_signoff.py"
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


@pytest.fixture(scope="module")
def signoff():
    spec = importlib.util.spec_from_file_location("smstudio_check_signoff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """An empty repository with one base commit; the tests run inside it."""
    env = {"GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.invalid",
           "GIT_COMMITTER_NAME": "Ada", "GIT_COMMITTER_EMAIL": "ada@example.invalid",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main"], check=True)
    commit("README", "base")
    return tmp_path


def commit(path: str, message: str, *, signoff: bool = False, email: str | None = None) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(file.read_text() + "x\n" if file.exists() else "x\n")
    subprocess.run(["git", "add", path], check=True)
    env = dict(os.environ)
    if email:
        env["GIT_AUTHOR_EMAIL"] = email
    args = ["git", "commit", "-q", "-m", message] + (["-s"] if signoff else [])
    subprocess.run(args, check=True, env=env)


def test_signed_off_commits_pass(signoff, repo, capsys):
    """Commits with the line 'git commit -s' writes pass; the count is printed."""
    commit("SpaceMissionStudio/a.py", "add a", signoff=True)
    commit("SpaceMissionStudio/b.py", "add b", signoff=True)
    assert signoff.main(["main~2", "main"]) == 0
    assert "2 commits" in capsys.readouterr().out


def test_a_commit_without_sign_off_fails_and_is_named(signoff, repo, capsys):
    """A commit with no Signed-off-by line fails the check, with its subject."""
    commit("SpaceMissionStudio/a.py", "add a", signoff=True)
    commit("SpaceMissionStudio/b.py", "forgot it")
    assert signoff.main(["main~2", "main"]) == 1
    out = capsys.readouterr().out
    assert "'forgot it': no Signed-off-by line" in out
    assert "1 of 2 commits" in out


def test_the_sign_off_must_be_the_authors(signoff, repo, capsys):
    """A sign-off by someone else than the author is not the author's certificate."""
    commit("SpaceMissionStudio/a.py", "someone else's", signoff=True, email="bob@example.invalid")
    assert signoff.main(["main~1", "main"]) == 1
    assert "author's e-mail address" in capsys.readouterr().out


def test_commits_outside_the_app_folder_are_not_checked(signoff, repo):
    """Only commits that change SpaceMissionStudio/ need the sign-off."""
    commit("src/basilisk.c", "upstream file")
    assert signoff.commits("main~1", "main") == []
    assert signoff.main(["main~1", "main"]) == 0


def test_wrong_arguments_print_the_usage(signoff, capsys):
    assert signoff.main([]) == 2
    assert "Signed-off-by" in capsys.readouterr().err


def test_the_project_takes_no_money():
    """Non-commercial (docs/legal/RISK_REGISTER.md R12): no funding file, no sponsor link in the metadata."""
    root = Path(__file__).resolve().parents[2]
    app = Path(__file__).resolve().parents[1]
    for funding in (root / ".github" / "FUNDING.yml", root / "FUNDING.yml", app / "FUNDING.yml"):
        assert not funding.exists(), funding
    metadata = (app / "pyproject.toml").read_text(encoding="utf-8").lower()
    for word in ("funding", "sponsor", "donate", "patreon", "ko-fi", "opencollective", "buymeacoffee"):
        assert word not in metadata, word
