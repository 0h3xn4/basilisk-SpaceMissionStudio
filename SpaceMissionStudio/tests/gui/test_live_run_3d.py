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
"""Run › Run's "Show in 3D View while running": a real run, held to 1000×
real time, shown in Results › 3D View as it is computed (its samples
reach the page, with the LIVE badge), scrubbed back and taken live again,
then replaced by its result in the same view; the choice and its pace
remembered; Cancel prompt even while the run waits for its pace."""

import json
import time

import pytest

pytestmark = pytest.mark.requires_gui


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """As tests/gui/test_main_window.py: no real autosave location."""
    from spacemissionstudio.gui import autosave

    recovery_dir = tmp_path / "autosave"
    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", recovery_dir)
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", recovery_dir / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    w.resize(1280, 800)
    w.show()
    w.on_new()
    return w


def _short_run(window, monkeypatch, days: float):
    """Run template 01 for ``days`` instead of the editor's scenario."""
    from spacemissionstudio import api

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    scenario.sim_settings.duration_days = days  # [day]
    monkeypatch.setattr(window.scenario_editor, "to_scenario", lambda: scenario)
    return scenario


def _js(qtbot, view, script):
    out = []
    view.web_view.page().runJavaScript(script, 0, out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=20000)
    return out[0]


def _state(qtbot, view):
    return json.loads(_js(qtbot, view, "JSON.stringify(MV.state())"))


def test_the_run_page_offers_the_live_view_and_remembers_it(window, qtbot):
    """The check box and its pace (As fast as possible, 1×, 10×, 100×,
    1000× real time), the pace off while the check box is; both kept for
    the next start."""
    from spacemissionstudio.gui.run_page import RunPage

    page = window.run_page
    assert page.live_view_check.text() == "Show in 3D View while running" and not page.live_view()
    assert [page.pacing_combo.itemText(i) for i in range(page.pacing_combo.count())] == [
        "As fast as possible", "1× real time", "10× real time", "100× real time", "1000× real time"]
    assert not page.pacing_combo.isEnabled() and page.pacing() == 0.0
    page.live_view_check.setChecked(True)
    page.pacing_combo.setCurrentIndex(3)
    assert page.pacing_combo.isEnabled() and page.pacing() == 100.0
    again = RunPage()
    qtbot.addWidget(again)
    assert again.live_view() and again.pacing() == 100.0 and again.pacing_combo.isEnabled()


@pytest.mark.requires_basilisk
def test_a_run_is_shown_live_in_the_3d_view_then_replaced_by_its_result(window, qtbot, monkeypatch):
    """Results › 3D View opens when the run starts; the run's states reach
    the page as it goes, with the LIVE badge; scrubbed back, the view
    stays while the run goes on, and Go live returns to its newest
    state; at the end the result replaces the live frames, in the same
    view, at the run's end."""
    _short_run(window, monkeypatch, 0.1)  # [day] 8.6 s at 1000× real time
    window.run_page.live_view_check.setChecked(True)
    window.run_page.pacing_combo.setCurrentIndex(window.run_page.pacing_combo.findData(1000.0))
    view = window.mission_view_widget
    window.on_run()
    assert window._live_feed is not None and view.is_live() and view.isVisible()
    qtbot.waitUntil(lambda: view.scene is not None and view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true") is True, timeout=60000)
    qtbot.waitUntil(lambda: _state(qtbot, view)["frames"] >= 20, timeout=30000)
    state = _state(qtbot, view)
    assert state["live"] is True and window._run_worker.isRunning()
    assert _js(qtbot, view, "document.getElementById('live').style.display") == "inline-block"
    first = state["frames"]
    view.slider.setValue(5)  # scrub back
    assert not view.following
    qtbot.waitUntil(lambda: _state(qtbot, view)["frames"] > first + 10, timeout=30000)
    state = _state(qtbot, view)
    assert state["frame"] == 5 and state["live"] is False and window._run_worker.isRunning()
    view.go_live()
    qtbot.waitUntil(lambda: _state(qtbot, view)["frame"] > 5 and _state(qtbot, view)["live"] is True, timeout=10000)
    view.view_combo.setCurrentIndex(1)  # Follow sat-1
    qtbot.waitUntil(lambda: not window._run_worker.isRunning(), timeout=60000)
    qtbot.waitUntil(lambda: not view.is_live() and view.scene is not None and view._run is None
                    and len(view.scene.times_s) == 289, timeout=60000)  # [-] the result: 0.1 day every 30 s
    qtbot.waitUntil(lambda: _state(qtbot, view)["frames"] == 289, timeout=30000)
    state = _state(qtbot, view)
    assert state["live"] is False and state["frame"] == 288 and state["view"]["mode"] == "follow"
    assert view.view_combo.currentText().startswith("Follow") and view.isVisible()


@pytest.mark.requires_basilisk
def test_cancel_stops_a_paced_run_at_once_and_its_partial_result_replaces_the_live_frames(window, qtbot,
                                                                                         monkeypatch):
    """A run held to real time (1×) is mostly waiting: Cancel ends the
    wait and the run stops at its next checkpoint, within seconds; what
    it computed replaces the live frames."""
    _short_run(window, monkeypatch, 1.0)  # [day] a day, at real time
    window.run_page.live_view_check.setChecked(True)
    window.run_page.pacing_combo.setCurrentIndex(window.run_page.pacing_combo.findData(1.0))
    view = window.mission_view_widget
    window.on_run()
    qtbot.waitUntil(lambda: view.scene is not None, timeout=60000)
    start = time.monotonic()
    window.on_abort_run()
    qtbot.waitUntil(lambda: not window._run_worker.isRunning(), timeout=60000)
    took = time.monotonic() - start  # [s]
    assert took < 20.0  # [s] the rest of the chunk, unpaced (a day / 60 of a two-body run)
    qtbot.waitUntil(lambda: not view.is_live() and view._run is None and view.scene is not None, timeout=60000)
    assert view.scene.times_s[-1] < 86400.0  # [s] the partial run
