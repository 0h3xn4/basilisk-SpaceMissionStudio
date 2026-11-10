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

"""Results › 3D View (``gui.mission_view_widget``): the run drawn by the
app's own three.js page, played back, kept in step with the shared time
cursor, followed at true size, seen from the Earth's frame and from an
instrument; empty until there is a run. The page is tested by its state
(``MV.state()``), not by its pixels."""

import json
import math
import re
from datetime import datetime, timedelta

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui

_RADIUS_M = 7000e3  # [m]


def _run(stations: bool = False):
    from spacemissionstudio import api
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.schema.scenario import GroundStationConfig

    scenario = api.load(api.template("01_two_body_circular_orbit"))
    if stations:
        scenario.ground_stations = [GroundStationConfig(name="equator-gs", latitude_deg=0.0, longitude_deg=0.0)]
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


def _state(qtbot, view):
    return json.loads(_js(qtbot, view, "JSON.stringify(MV.state())"))


def _open(qtbot, run):
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget
    from spacemissionstudio.gui.time_cursor import TimeCursor

    view = MissionViewWidget()
    qtbot.addWidget(view)
    cursor = TimeCursor()
    view.set_time_cursor(cursor)
    view.resize(900, 600)
    view.show()
    view.set_run(*run)
    qtbot.waitUntil(lambda: view.scene is not None, timeout=30000)
    qtbot.waitUntil(lambda: view._page_ready, timeout=60000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.ready === true && MV.style !== null") is True, timeout=60000)
    assert _js(qtbot, view, "JSON.stringify(MV_ERRORS)") == "[]"
    return view, cursor


@pytest.fixture
def shown(qtbot):
    """The view with a run, shown, its scene built and drawn."""
    return _open(qtbot, _run())


def test_without_a_run_the_view_says_what_to_do(qtbot):
    """No run: an empty state with what to do, no web view yet, and the
    controls off; a run without its scenario leaves it empty."""
    from spacemissionstudio.gui.mission_view_widget import MissionViewWidget

    view = MissionViewWidget()
    qtbot.addWidget(view)
    view.show()
    assert "Run a scenario" in view.empty.text() and view.web_view is None
    assert not view.play_button.isEnabled() and not view.slider.isEnabled()
    assert not view.show_button.isEnabled()
    view.set_run(None, None)
    assert view.stack.currentWidget() is view.empty


def test_the_run_is_drawn_in_the_app_s_own_page(shown, qtbot):
    """The Earth (textured, turning, with its atmosphere), the stars, the
    Moon, the spacecraft with its path, trail, body axes and arrows: drawn
    by the bundled three.js from the package's own files; the slider spans
    the run; the speed plays it in about 30 s; the spacecraft is enlarged,
    and the note says by how much."""
    from spacemissionstudio.gui.mission_view_widget import PAGE

    view, _cursor = shown
    state = _state(qtbot, view)
    assert state["ready"] and state["frames"] == 300 and state["view"] == {"mode": "orbit"}
    (craft,) = state["crafts"]
    assert craft["path"] and craft["trail"] and craft["axes"] and craft["headings"] and craft["scale"] > 1.0
    assert state["moon"] is not None and state["gl2"] is True
    assert view.slider.maximum() == len(view.scene.times_s) - 1 == 299
    assert view.speed_combo.currentData() == 300  # 5800 s / 30 s: 5 min/s
    assert "larger than they are" in view.scale_note.text()
    assert view.web_view.url().isLocalFile() and view.web_view.url().toLocalFile() == str(PAGE)
    assert [view.view_combo.itemText(i) for i in range(3)] == [
        "Whole orbit", f"Follow {view.scene.crafts[0].name}", "Earth-fixed"]


def test_the_earth_and_star_textures_are_loaded(shown, qtbot):
    """NASA's Blue Marble on the Earth and the star map on the sky, from
    the package (4096 x 2048 each in full quality)."""
    view, _cursor = shown
    _js(qtbot, view, "MV.configure({auto_quality: false}); MV.setQuality('full'); 1")
    qtbot.waitUntil(lambda: _state(qtbot, view)["loaded"] == {"earth": "earth_day_4k.jpg", "stars": "stars_4k.jpg"},
                    timeout=30000)
    state = _state(qtbot, view)
    assert state["earthTexture"] == [4096, 2048] and state["starsTexture"] == [4096, 2048]
    assert state["stars"] is True and state["atmosphere"] is True and state["quality"] == "full"


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


def test_the_overlay_shows_the_time_in_iso_8601_utc(shown, qtbot):
    """The overlay's first line is the frame's UTC time, ISO 8601 with Z,
    the same as the controls'; then the elapsed time and the speed."""
    view, _cursor = shown
    view.show_frame(150)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == 150, timeout=10000)
    qtbot.waitUntil(lambda: _state(qtbot, view)["hud"].count("\n") >= 1, timeout=10000)
    hud = _state(qtbot, view)["hud"]
    first, second = hud.split("\n")[:2]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", first)
    epoch = datetime.fromisoformat(view.scene.epoch_utc.replace("Z", ""))
    assert first == (epoch + timedelta(seconds=float(np.round(view.scene.times_s[150], 3)))).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    assert first in view.time_label.text()
    assert second.startswith("T+") and "5 min/s" in second


def test_following_a_spacecraft_shows_it_at_true_size_with_its_axes(shown, qtbot):
    """Follow: the spacecraft at the origin (the floating origin: it stays
    there, whatever its distance from the Earth), true size, its body axes
    from the run's attitude, the overlay with its altitude and speed."""
    view, _cursor = shown
    view.show_frame(150)  # half an orbit: B turned 180 degrees about z
    view.view_combo.setCurrentIndex(1)
    assert "True size" in view.scale_note.text()
    qtbot.waitUntil(lambda: _state(qtbot, view)["view"].get("mode") == "follow", timeout=10000)
    now = _state(qtbot, view)
    (craft,) = now["crafts"]
    assert craft["scale"] == 1 and craft["axes"] is True
    assert np.linalg.norm(craft["world"]) < 1e-9  # [km] drawn at the origin
    np.testing.assert_allclose(now["origin"], view.scene.crafts[0].position_km[150], atol=1e-4)
    np.testing.assert_allclose(craft["xAxis"][:2], [-1.0, 0.0], atol=0.05)  # x_B in N, half an orbit on: -x_N
    for frame in (0, 75, 299):  # the origin moves with it
        view.show_frame(frame)
        qtbot.waitUntil(lambda frame=frame: _js(qtbot, view, "MV.frame") == frame, timeout=10000)
        state = _state(qtbot, view)
        assert np.linalg.norm(state["crafts"][0]["world"]) < 1e-9
        assert np.linalg.norm(state["origin"]) == pytest.approx(_RADIUS_M / 1000.0, rel=1e-3)
    assert re.search(r"altitude \d+\.\d km  speed 7\.\d{3} km/s", _state(qtbot, view)["hud"])


def test_the_earth_fixed_view_turns_with_the_earth(shown, qtbot):
    """Earth-fixed: from one frame to another the camera turns about z by
    the Earth's rotation between them."""
    view, _cursor = shown
    view.view_combo.setCurrentIndex(2)
    qtbot.waitUntil(lambda: _state(qtbot, view)["view"] == {"mode": "earth"}, timeout=10000)
    before = json.loads(_js(qtbot, view, "JSON.stringify([MV.camera.position.toArray(), MV.rotation()])"))
    view.show_frame(100)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.frame") == 100, timeout=10000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
    after = json.loads(_js(qtbot, view, "JSON.stringify([MV.camera.position.toArray(), MV.rotation()])"))
    turned = math.atan2(after[0][1], after[0][0]) - math.atan2(before[0][1], before[0][0])
    expected = after[1] - before[1]
    assert math.remainder(turned - expected, 2.0 * math.pi) == pytest.approx(0.0, abs=1e-6)
    assert expected != pytest.approx(0.0)
    assert after[0][2] == pytest.approx(before[0][2])


def test_the_instrument_view_looks_along_a_body_axis(shown, qtbot):
    """From the spacecraft along +x_B: the camera just outside the model on
    its x_B axis (the 1 m cube's face 0.5 m from B, plus 2 % of its size),
    near the origin (the spacecraft), looking along x_B in N, with the
    view's 60 degree field."""
    view, _cursor = shown
    index = view.view_combo.findText(f"From {view.scene.crafts[0].name} along +x_B")
    view.show_frame(75)  # a quarter orbit: x_B is +y_N
    view.view_combo.setCurrentIndex(index)
    qtbot.waitUntil(lambda: _state(qtbot, view)["view"].get("mode") == "instrument", timeout=10000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
    camera = json.loads(_js(qtbot, view, "JSON.stringify([MV.camera.position.toArray(), "
                                         "MV.camera.getWorldDirection(new THREE.Vector3()).toArray(), MV.camera.fov])"))
    np.testing.assert_allclose(camera[0], [0.0, 0.00052, 0.0], atol=1e-5)  # [km] frame 75 is 0.3 deg past a quarter
    assert camera[2] == 60
    np.testing.assert_allclose(camera[1], [0.0, 1.0, 0.0], atol=0.03)


def test_an_instrument_view_takes_the_instrument_s_field_of_view(qtbot):
    """Template 32's star tracker: a view from it, with its 20 degree field
    of view, its own cone hidden; the other cones (the antenna's, the
    thruster's plume) drawn."""
    from spacemissionstudio import api
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    scenario = api.load(api.template("32_smallsat_design_checks"))
    name = scenario.spacecraft[0].name
    t = np.linspace(0.0, 600.0, 61)
    result = ResultSet(scenario_name=scenario.name)
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"),
                          np.column_stack([_RADIUS_M + 0 * t, 7.5e3 * t, 0 * t]), units="m"))
    view, _cursor = _open(qtbot, (scenario, result))
    index = view.view_combo.findText(f"From {name}: st-1 (20° field of view)")
    assert index > 0
    assert len(_state(qtbot, view)["crafts"][0]["cones"]) == 3  # star tracker, antenna, plume
    view.view_combo.setCurrentIndex(index)
    qtbot.waitUntil(lambda: _state(qtbot, view)["view"].get("mode") == "instrument", timeout=10000)
    state = _state(qtbot, view)
    assert state["fov"] == 20
    assert state["crafts"][0]["cones"].count(False) == 1 and "st-1" in view.scale_note.text()


def test_the_show_menu_switches_what_is_drawn_and_remembers_it(shown, qtbot):
    """Each item of Show hides its part of the scene in the page, and is
    remembered for the next view."""
    from spacemissionstudio.gui.mission_view_widget import TOGGLES, MissionViewWidget

    view, _cursor = shown
    assert [action.text() for action in view.toggle_actions.values()] == [text for _key, text in TOGGLES]
    assert not view.toggle_actions["groundTrack"].isChecked()
    for key in ("paths", "trails", "axes", "headings", "stars", "labels"):
        view.toggle_actions[key].setChecked(False)
    view.toggle_actions["groundTrack"].setChecked(True)
    qtbot.waitUntil(lambda: _state(qtbot, view)["toggles"]["groundTrack"] is True, timeout=10000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
    state = _state(qtbot, view)
    craft = state["crafts"][0]
    assert not (craft["path"] or craft["trail"] or craft["axes"] or craft["headings"]) and craft["track"] is True
    assert state["stars"] is False and state["labels"] == []
    again = MissionViewWidget()
    qtbot.addWidget(again)
    assert not again.toggle_actions["paths"].isChecked() and again.toggle_actions["groundTrack"].isChecked()
    assert again.toggle_actions["cones"].isChecked()


def test_a_station_s_line_of_sight_follows_its_elevation(qtbot):
    """A station at 0 deg, 0 deg: its line to the spacecraft is drawn on
    exactly the frames where the spacecraft is above its minimum elevation
    (``scene.station_visible``), and not on the others."""
    view, _cursor = _open(qtbot, _run(stations=True))
    visible = view.scene.station_visible[0, 0]
    assert visible.any() and not visible.all()
    for frame in (int(np.argmax(visible)), int(np.argmin(visible))):
        view.show_frame(frame)
        qtbot.waitUntil(lambda frame=frame: _js(qtbot, view, "MV.frame") == frame, timeout=10000)
        qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
        assert _state(qtbot, view)["links"] == [bool(visible[frame])]
    view.toggle_actions["stations"].setChecked(False)
    view.show_frame(int(np.argmax(visible)))
    qtbot.waitUntil(lambda: _state(qtbot, view)["links"] == [False], timeout=10000)


def test_reduced_quality_by_choice_and_by_itself(shown, qtbot):
    """Reduced quality: 2k textures, no atmosphere, one pixel per screen
    pixel. The page chooses it by itself when the median frame takes
    longer than 50 ms, and the menu item follows."""
    view, _cursor = shown
    _js(qtbot, view, "MV.configure({auto_quality: false}); MV.setQuality('full'); 1")
    view.quality_action.setChecked(False)
    view.quality_action.setChecked(True)
    qtbot.waitUntil(lambda: _state(qtbot, view)["loaded"] == {"earth": "earth_day_2k.jpg", "stars": "stars_2k.jpg"},
                    timeout=30000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
    state = _state(qtbot, view)
    assert state["quality"] == "reduced" and state["atmosphere"] is False and state["pixelRatio"] == 1
    assert state["earthTexture"] == [2048, 1024]
    assert json.loads(_js(qtbot, view, "JSON.stringify([MV.shouldReduce([40, 60, 70]), "
                                       "MV.shouldReduce([20, 30, 70])])")) == [True, False]
    view.quality_action.setChecked(False)
    qtbot.waitUntil(lambda: _state(qtbot, view)["quality"] == "full", timeout=10000)
    _js(qtbot, view, "document.title = 'mv:ready'; 1")
    _js(qtbot, view, "document.title = 'mv:reduced-auto'; 1")  # what the page says when it reduces by itself
    qtbot.waitUntil(view.quality_action.isChecked, timeout=10000)


def test_a_theme_change_restyles_the_page_without_reloading(shown, qtbot, restored_theme):
    """Dark theme: the page takes the dark style (overlay surface, colours)
    at once; the textures and the scene stay as they are."""
    from spacemissionstudio.gui.theme import TOKENS, apply_theme
    from spacemissionstudio.gui.theme.palettes import categorical

    view, _cursor = shown
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.loaded.earth !== ''") is True, timeout=30000)
    _js(qtbot, view, "window.KEEP = [MV.body.material.map, MV.crafts[0].mesh]; 1")
    apply_theme(restored_theme, "dark")
    qtbot.waitUntil(lambda: _state(qtbot, view)["styleMode"] == "dark", timeout=10000)
    qtbot.waitUntil(lambda: _js(qtbot, view, "MV.dirty") is False, timeout=10000)
    state = _state(qtbot, view)
    red, green, blue = (int(TOKENS["bg.raised"][i:i + 2], 16) for i in (1, 3, 5))
    assert state["hudBackground"] == f"rgb({red}, {green}, {blue})"
    assert state["crafts"][0]["colour"] == categorical("dark")[0].lower()
    assert _js(qtbot, view, "MV.body.material.map === KEEP[0] && MV.crafts[0].mesh === KEEP[1]") is True


def test_the_page_data_and_style_come_from_the_scene_and_the_theme():
    """The page gets the scene's numbers in km and s, each 3D part's own
    colour as linear light with a normal per corner, and the theme's
    colours and overlay style (``theme.mission_view_style``)."""
    from spacemissionstudio.engine import scene3d
    from spacemissionstudio.gui.mission_view_widget import scene_payload
    from spacemissionstudio.gui.theme.tokens import tokens
    from spacemissionstudio.gui.theme.mission_view_style import mission_view_style
    from spacemissionstudio.gui.theme.palettes import AXIS_COLOURS, categorical

    scenario, result = _run(stations=True)
    scene = scene3d.build_scene(scenario, result)
    payload = scene_payload(scene)
    assert "style" not in payload and payload["body"]["earth"] is True
    assert np.linalg.norm(payload["crafts"][0]["pos"][0]) == pytest.approx(_RADIUS_M / 1000.0)
    mesh = payload["crafts"][0]["mesh"]
    assert len(mesh["p"]) == len(mesh["n"]) == len(mesh["c"]) == 12 * 3 * 3
    assert mesh["c"][0] == pytest.approx(((176 / 255 + 0.055) / 1.055) ** 2.4, abs=1e-4)
    assert payload["stations"][0]["min_el"] == 10.0 and len(payload["stations"][0]["visible"][0]) == 300
    assert payload["epoch_ms"] == (datetime.fromisoformat(scenario.epoch_utc.replace("Z", ""))
                                   - datetime(1970, 1, 1)).total_seconds() * 1000.0
    for mode in ("light", "dark"):
        style = mission_view_style(mode)
        assert style["crafts"] == categorical(mode) and style["axes"] == list(AXIS_COLOURS)
        assert tokens(mode)["bg.raised"] in style["css"] and tokens(mode)["text.primary"] in style["css"]
        assert style["fov"] == tokens(mode)["accent"] and style["plume"] == tokens(mode)["status.caution"]
