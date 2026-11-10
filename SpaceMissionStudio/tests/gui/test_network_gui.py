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

"""The network policy in the GUI (``spacemissionstudio/network.py``):
**Settings > Network** sets offline mode, locked when an administrator
does; offline, Download and the start-up question are gone; the web views
load nothing but the app's own files."""

import json

import pytest

from spacemissionstudio import network


@pytest.fixture
def policy_file(monkeypatch, tmp_path):
    path = tmp_path / "machine" / "policy.json"
    monkeypatch.setattr(network, "machine_policy_file", lambda: path)
    monkeypatch.delenv(network.OFFLINE_VARIABLE, raising=False)
    return path


@pytest.fixture
def window(qtbot, policy_file):
    from spacemissionstudio.gui.main_window import MainWindow

    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


def test_settings_turns_offline_on_and_the_downloads_follow(window):
    """Ticking **Work offline** saves the choice; Download is then off with
    the reason as its tooltip, and the start-up question is not asked."""
    page = window.settings_page
    assert not page.offline_box.isChecked() and page.offline_box.isEnabled()
    assert "celestrak.org" in page.network_hosts.text() and "Online" in page.network_note.text()
    page.offline_box.setChecked(True)
    assert network.policy().offline and json.loads(network.user_settings_file().read_text())["offline"] is True
    panel = window.data_panel_widget
    assert not panel.download_button.isEnabled() and "Offline" in panel.download_button.toolTip()
    assert panel.import_button.isEnabled()  # files from disk still install
    card = window.load_scenario_widget.reference_card
    card.ask()
    assert not card.isVisible()
    page.offline_box.setChecked(False)
    assert not network.policy().offline and panel.download_button.isEnabled()


def test_an_administrator_s_policy_locks_the_setting(policy_file, qtbot):
    """With the machine's policy file, the box is ticked and cannot be
    changed, and the note says who set it."""
    from spacemissionstudio.gui.main_window import MainWindow

    policy_file.parent.mkdir(parents=True)
    policy_file.write_text(json.dumps({"offline": True}), encoding="utf-8")
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    page = w.settings_page
    assert page.offline_box.isChecked() and not page.offline_box.isEnabled()
    assert "administrator" in page.network_note.text() and "cannot change" in page.network_note.text()
    assert not w.data_panel_widget.download_button.isEnabled()


def test_chromium_s_background_requests_are_off(monkeypatch):
    """The flags the views start Chromium with turn its own background
    requests off; a user's own flags are kept as they are."""
    from spacemissionstudio.gui import webengine_setup

    monkeypatch.delenv("QTWEBENGINE_CHROMIUM_FLAGS", raising=False)
    webengine_setup.configure()
    flags = __import__("os").environ["QTWEBENGINE_CHROMIUM_FLAGS"].split()
    assert set(webengine_setup.NO_BACKGROUND_NETWORK) <= set(flags)
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--mine")
    webengine_setup.configure()
    assert __import__("os").environ["QTWEBENGINE_CHROMIUM_FLAGS"] == "--mine"


def test_a_web_view_loads_nothing_from_another_computer(qtbot):
    """The views' profile blocks a request that is not for the app's own
    files, and logs it; a local page still loads."""
    from PySide6.QtCore import QUrl

    from spacemissionstudio.gui import webengine_setup
    from PySide6.QtWebEngineWidgets import QWebEngineView

    webengine_setup.guard_profile()
    view = QWebEngineView()
    qtbot.addWidget(view)
    with qtbot.waitSignal(view.loadFinished, timeout=30000) as blocked:
        view.load(QUrl("https://example.com/"))
    assert blocked.args == [False]
    assert "refused\tweb view\thttps://example.com/" in network.log_path().read_text(encoding="utf-8")
    with qtbot.waitSignal(view.loadFinished, timeout=30000) as local:
        view.setHtml("<p>local</p>")
    assert local.args == [True]
