"""Tests for gui.vizard_launcher -- the Vizard the user chose, and
starting it, with filesystem/QSettings I/O redirected into tmp_path. No
Vizard is downloaded or searched for (2026-11-09: AVS Lab's build has
Unity Analytics on; Results › 3D View is built in).
"""

import pytest
from PySide6.QtCore import QSettings

pytestmark = pytest.mark.requires_gui


def _settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_remember_then_find_returns_the_remembered_path(tmp_path, monkeypatch):
    """A remembered Vizard executable that exists is the one found."""
    from spacemissionstudio.gui import vizard_launcher

    fake_exe = tmp_path / "Vizard.x86_64"
    fake_exe.write_bytes(b"")
    settings = _settings(tmp_path)

    vizard_launcher.remember_vizard_executable(fake_exe, settings=settings)
    assert vizard_launcher.find_vizard_executable(settings=settings) == fake_exe


def test_launch_starts_the_given_executable_directly_on_linux(tmp_path, monkeypatch):
    """On Linux, the executable is started directly, without arguments, and its
    process returned."""
    from spacemissionstudio.gui import vizard_launcher

    monkeypatch.setattr(vizard_launcher.sys, "platform", "linux")
    exe = tmp_path / "Vizard.x86_64"
    exe.write_bytes(b"")

    captured = {}

    class _FakeProcess:
        pid = 4242

        def poll(self):
            return None

    def fake_popen(args):
        captured["args"] = args
        return _FakeProcess()

    monkeypatch.setattr(vizard_launcher.subprocess, "Popen", fake_popen)
    result = vizard_launcher.launch_vizard(exe)

    assert captured["args"] == [str(exe)]
    assert result.pid == 4242


def test_launch_appends_direct_comm_flag_when_given(tmp_path, monkeypatch):
    """See DEFAULT_LIVE_STREAM_ADDRESS's own comment: -directComm is what
    makes Vizard connect to a live-stream run automatically instead of
    sitting on its own manual launcher screen.
    """
    from spacemissionstudio.gui import vizard_launcher

    monkeypatch.setattr(vizard_launcher.sys, "platform", "linux")
    exe = tmp_path / "Vizard.x86_64"
    exe.write_bytes(b"")

    captured = {}
    monkeypatch.setattr(vizard_launcher.subprocess, "Popen", lambda args: captured.setdefault("args", args))

    vizard_launcher.launch_vizard(exe, direct_comm_address="tcp://localhost:5556")

    assert captured["args"] == [str(exe), "-directComm", "tcp://localhost:5556"]


def test_launch_treats_an_app_bundle_path_like_any_other(tmp_path, monkeypatch):
    """macOS is not supported (2026-10-21): a path ending in .app is no
    longer resolved to a binary inside it, but started as given, on every
    platform, even one that reports itself as macOS."""
    from spacemissionstudio.gui import vizard_launcher

    monkeypatch.setattr(vizard_launcher.sys, "platform", "darwin")
    bundle = tmp_path / "Vizard.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)
    (bundle / "Contents" / "MacOS" / "Vizard").write_bytes(b"")

    captured = {}
    monkeypatch.setattr(vizard_launcher.subprocess, "Popen", lambda args: captured.setdefault("args", args))

    vizard_launcher.launch_vizard(bundle)
    assert captured["args"] == [str(bundle)]


def test_launch_no_longer_inspects_an_empty_app_bundle(tmp_path, monkeypatch):
    """An empty .app folder used to be refused as "not a valid macOS app
    bundle"; with macOS unsupported it is not inspected, and starting it is
    left to the operating system, as for any other path."""
    from spacemissionstudio.gui import vizard_launcher

    monkeypatch.setattr(vizard_launcher.sys, "platform", "darwin")
    bundle = tmp_path / "Vizard.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)

    captured = {}
    monkeypatch.setattr(vizard_launcher.subprocess, "Popen", lambda args: captured.setdefault("args", args))

    vizard_launcher.launch_vizard(bundle)
    assert captured["args"] == [str(bundle)]


# -- no Vizard is downloaded or searched for --------------------------------

def test_nothing_is_found_unless_the_user_chose_it(tmp_path, monkeypatch):
    """No Vizard is searched for: one lying on the Desktop or in Downloads
    is not used until the user chooses it."""
    from spacemissionstudio.gui import vizard_launcher

    monkeypatch.setattr(vizard_launcher.Path, "home", lambda: tmp_path)
    for folder in ("Desktop", "Downloads"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "Vizard.x86_64").write_bytes(b"")
    settings = _settings(tmp_path)
    assert vizard_launcher.find_vizard_executable(settings=settings) is None
    vizard_launcher.remember_vizard_executable(tmp_path / "Desktop" / "Vizard.x86_64", settings=settings)
    assert vizard_launcher.find_vizard_executable(settings=settings) == tmp_path / "Desktop" / "Vizard.x86_64"


def test_a_copy_the_former_download_left_is_never_started(tmp_path, monkeypatch):
    """Up to 2.5.0 the app could download AVS Lab's build (Unity Analytics
    on) into a cache folder and remember it there: that location is
    ignored."""
    from spacemissionstudio.gui import vizard_launcher

    former = tmp_path / ".cache" / "SpaceMissionStudio" / "vizard"
    (former / "Vizard_Linux").mkdir(parents=True)
    old = former / "Vizard_Linux" / "Vizard.x86_64"
    old.write_bytes(b"")
    monkeypatch.setattr(vizard_launcher, "FORMER_DOWNLOAD_DIR", former)
    settings = _settings(tmp_path)
    vizard_launcher.remember_vizard_executable(old, settings=settings)
    assert vizard_launcher.find_vizard_executable(settings=settings) is None


def test_the_launcher_has_no_way_to_download():
    """No download code is left, and no network purpose names Vizard."""
    from spacemissionstudio import network
    from spacemissionstudio.gui import vizard_launcher

    assert not hasattr(vizard_launcher, "fetch_vizard") and not hasattr(vizard_launcher, "VizardFetchWorker")
    assert not any("vizard" in key or "hanspeterschaub.info" in purpose.hosts and key == "vizard"
                   for key, purpose in network.PURPOSES.items())
    source = (vizard_launcher.__file__)
    assert "urllib" not in open(source, encoding="utf-8").read()


def test_launch_opens_a_playback_file_with_load_file(tmp_path, monkeypatch):
    """Vizard's documented ``-loadFile`` argument opens a run's playback
    file (UX/UI guidelines, decision 3: open only)."""
    from spacemissionstudio.gui import vizard_launcher

    monkeypatch.setattr(vizard_launcher.sys, "platform", "linux")
    exe = tmp_path / "Vizard.x86_64"
    exe.write_bytes(b"")
    captured = {}
    monkeypatch.setattr(vizard_launcher.subprocess, "Popen", lambda args: captured.setdefault("args", args))
    vizard_launcher.launch_vizard(exe, load_file=tmp_path / "run.bin")
    assert captured["args"] == [str(exe), "-loadFile", str(tmp_path / "run.bin")]


def test_the_playback_file_follows_basilisks_naming():
    """vizSupport.enableUnityVisualization: a ``.bin`` path is used as is;
    any other name goes to ``_VizFiles/<name>_UnityViz.bin`` beside it."""
    from pathlib import Path

    from spacemissionstudio.engine.vizard import playback_file

    assert playback_file("/runs/a.bin") == Path("/runs/a.bin")
    assert playback_file("/runs/a") == Path("/runs/_VizFiles/a_UnityViz.bin")
    assert playback_file("a.txt") == Path("_VizFiles/a_UnityViz.bin")
