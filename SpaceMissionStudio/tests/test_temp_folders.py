"""Tests for spacemissionstudio.temp_folders (audit R14): every folder is
named after its process, and those whose process has ended are removed.
Each test works in a ``tmp_path`` standing in for the temporary folder."""

import os
import subprocess
import sys
import time

import pytest

from spacemissionstudio import temp_folders


@pytest.fixture
def temp_root(tmp_path, monkeypatch):
    """``tmp_path`` as ``tempfile``'s temporary folder."""
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def _ended_pid():
    """The process id of a process that has ended."""
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def test_each_folder_is_named_after_its_process(temp_root):
    """The plot, Compare and model pages, the icons and Vizard's models
    are made under the temporary folder, with ``<kind><pid>-`` names."""
    page = temp_folders.temporary_directory(temp_folders.PLOT_PAGE)
    try:
        assert os.path.dirname(page.name) == str(temp_root)
        assert os.path.basename(page.name).startswith(f"{temp_folders.PLOT_PAGE}{os.getpid()}-")
    finally:
        page.cleanup()


def test_a_folder_removed_at_exit_is_registered_for_it(temp_root, monkeypatch):
    """The icons' and Vizard's folders, which no object owns, are removed
    when the process exits (audit R14: Vizard's were never removed)."""
    registered = []
    monkeypatch.setattr(temp_folders.atexit, "register", lambda *call: registered.append(call))
    folder = temp_folders.folder_removed_at_exit(temp_folders.VIZARD_MODELS)
    assert folder.is_dir() and folder.name.startswith(f"{temp_folders.VIZARD_MODELS}{os.getpid()}-")
    assert registered == [(temp_folders.shutil.rmtree, folder, True)]


def test_only_the_folders_left_behind_are_removed(temp_root):
    """A folder whose process has ended goes, and an old one named before
    the process id was in the name; this process's own, a recent unnamed
    one and other programs' folders stay."""
    ended = _ended_pid()
    gone = [temp_root / f"{temp_folders.PLOT_PAGE}{ended}-abc123", temp_root / f"{temp_folders.COMPARE_PAGE}{ended}-x_1",
            temp_root / f"{temp_folders.ICONS}old0ne_x"]
    kept = [temp_root / f"{temp_folders.PLOT_PAGE}{os.getpid()}-mine0001", temp_root / f"{temp_folders.ICONS}new0ne_x",
            temp_root / "someone-elses-folder", temp_root / f"{temp_folders.VIZARD_MODELS}{os.getppid()}-parent01"]
    for folder in gone + kept:
        folder.mkdir()
        (folder / "page.html").write_text("x", encoding="utf-8")
    old = time.time() - temp_folders.UNTRACED_AGE_S - 60.0  # [s]
    os.utime(gone[2], (old, old))
    (temp_root / f"{temp_folders.PLOT_PAGE}{ended}-a_file").write_text("not a folder", encoding="utf-8")

    assert temp_folders.remove_left_behind() == 3
    assert [folder.exists() for folder in gone] == [False] * 3
    assert all(folder.is_dir() for folder in kept)
    assert (temp_root / f"{temp_folders.PLOT_PAGE}{ended}-a_file").is_file()


def test_a_process_that_has_ended_is_told_from_one_that_runs():
    """The check behind the removal, on this platform: this process and
    its parent run, an ended one does not."""
    assert temp_folders._running(os.getpid())
    assert temp_folders._running(os.getppid())
    assert not temp_folders._running(_ended_pid())


def test_the_gui_removes_what_earlier_sessions_left_behind(temp_root):
    """``gui.app`` runs the removal at start, in the background; what it
    runs removes a left-behind folder."""
    pytest.importorskip("PySide6")
    from spacemissionstudio.gui import app

    folder = temp_root / f"{temp_folders.PLOT_PAGE}{_ended_pid()}-crashed1"
    folder.mkdir()
    app.remove_left_behind_folders()
    assert not folder.exists()
