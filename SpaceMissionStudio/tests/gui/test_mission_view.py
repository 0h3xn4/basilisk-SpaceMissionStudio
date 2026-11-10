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

"""Results › 3D View (``gui.mission_view_widget``): the run drawn in the
app's own page, played back, kept in step with the shared time cursor,
and followed at true size; empty until there is a run."""

import json
import math

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui

_RADIUS_M = 7000e3  # [m]


def _run():
    from spacemissionstudio import api
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    name = scenario.spacecraft[0].name
    t = np.linspace(0.0, 5800.0, 300)
    angle = 2.0 * math.pi * t / 5800.0
    result = ResultSet(scenario_name=scenario.name)
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"),
                          np.column_stack([_RADIUS_M * np.cos(angle), _RADIUS_M * np.sin(angle), 0 * t]), units="m"))
    result.add(TimeSeries(f"{name}.attitude_sigma_BN", t, ("s1", "s2", "s3"),
                          np.column_stack([0 * t, 0 * t, np.tan(angle / 4.0)])))
    return scenario, result


def _js(qtbot, view, script):
    out = []
    view.web_view.page().runJavaScript(script, 0, out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=20000)
    return out[0]


@pytest.fixture
def shown(qtbot):
    """The view with a run, shown, its scene built and drawn."""
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget
    from spacemissionstudio.gui.time_cursor import TimeCursor

    view = MissionViewWidget()
    qtbot.addWidget(view)
    cursor = TimeCursor()
    view.set_time_cursor(cursor)
    view.resize(900, 600)
    view.show()
    view.set_run(*_run())
    qtbot.waitUntil(lambda: view.scene is not None, timeout=30000)
    qtbot.waitUntil(lambda: view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true") is True, timeout=60000)
    return view, cursor


def test_without_a_run_the_view_says_what_to_do(qtbot):
    """No run: an empty state with what to do, no web view yet, and the
    controls off; a run without its scenario leaves it empty."""
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget

    view = MissionViewWidget()
    qtbot.addWidget(view)
    view.show()
    assert "Run a scenario" in view.empty.text() and view.web_view is None
    assert not view.play_button.isEnabled() and not view.slider.isEnabled()
    view.set_run(None, None)
    assert view.stack.currentWidget() is view.empty


def test_the_run_is_drawn_in_the_app_s_own_page(shown, qtbot):
    """The Earth, the Sun's direction, the stations, the path, the model
    and the marker of each spacecraft, the body axes and nadir: drawn by
    the local plotly.js; the slider spans the run; the speed plays it in
    about 30 s; the spacecraft is enlarged, and the note says by how much."""
    view, _cursor = shown
    assert _js(qtbot, view, "document.getElementById('mission-view').data.length") == 3 + 3 + 4
    assert view.slider.maximum() == len(view.scene.times_s) - 1 == 299
    assert view.speed_combo.currentData() == 300  # 5800 s / 30 s: 5 min/s
    assert "larger than they are" in view.scale_note.text()
    assert view.web_view.url().isLocalFile()


def test_playback_moves_the_frame_and_pausing_moves_the_cursor(shown, qtbot):
    """Play advances the frames (the slider and the page follow); Pause
    puts the shared time cursor at the time shown."""
    view, cursor = shown
    view.toggle_play()
    assert view.is_playing() and view.play_button.text() == "Pause"
    qtbot.waitUntil(lambda: view.slider.value() > 5, timeout=10000)
    view.toggle_play()
    assert not view.is_playing()
    frame = view.slider.value()
    assert cursor.time_s == pytest.approx(view.scene.times_s[frame])
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == frame, timeout=10000)


def test_the_time_cursor_moves_the_view(shown, qtbot):
    """A time picked elsewhere (a plot, the Timeline) is shown here."""
    view, cursor = shown
    cursor.set_time(2900.0)
    expected = int(np.argmin(np.abs(view.scene.times_s - 2900.0)))
    assert view.slider.value() == expected
    assert "T+00:48:20" in view.time_label.text() or "T+00:48:" in view.time_label.text()
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == expected, timeout=10000)


def test_following_a_spacecraft_shows_it_at_true_size_with_its_axes(shown, qtbot):
    """Follow: the spacecraft at the origin, true size, its body axes from
    the run's attitude, the Earth and the path hidden."""
    view, _cursor = shown
    view.show_frame(150)  # half an orbit: B turned 180 degrees about z
    view.view_combo.setCurrentIndex(1)
    assert "True size" in view.scale_note.text()

    def state():
        return json.loads(_js(qtbot, view, "JSON.stringify((function () { const d = "
                                          "document.getElementById('mission-view').data, a = MV.axesTrace(); "
                                          "return {mode: MV.mode, earth: d[0].visible, path: d[3].visible, "
                                          "axis: d[a].visible, x: [d[a].x[1], d[a].y[1]]}; })())"))
    qtbot.waitUntil(lambda: state()["mode"] == 0, timeout=10000)
    now = state()
    assert now["earth"] is False and now["path"] is False and now["axis"] is True
    size = view.scene.crafts[0].size_km
    x_axis = np.array(now["x"]) / (1.2 * size)  # x_B in N, half an orbit on: about -x_N
    np.testing.assert_allclose(x_axis, [-1.0, 0.0], atol=0.05)


def test_the_payload_takes_its_colours_from_the_theme():
    """The page gets the theme's colours and the scene's numbers, in km."""
    from spacemissionstudio.engine import scene3d
    from spacemissionstudio.gui.mission_view_widget import scene_payload
    from spacemissionstudio.gui.theme import TOKENS
    from spacemissionstudio.gui.theme.palettes import EARTH_COLOURSCALE, categorical

    scenario, result = _run()
    albedo = np.full((36, 72), 0.3)
    payload = scene_payload(scene3d.build_scene(scenario, result, albedo=albedo), "light")
    assert payload["style"]["bg"] == TOKENS["bg.surface"] and payload["style"]["earth"] == EARTH_COLOURSCALE
    assert payload["crafts"][0]["colour"] == categorical("light")[0]
    assert len(payload["body"]["x"]) == len(payload["body"]["intensity"]) == 37 * 73
    assert np.linalg.norm(payload["crafts"][0]["pos"][0]) == pytest.approx(_RADIUS_M / 1000.0)
