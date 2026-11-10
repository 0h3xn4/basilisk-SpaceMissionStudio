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
"""Results › 3D View: the run in 3D, inside the app, with nothing to
install and nothing sent anywhere.

A renderer of the run's own series: the Earth (NASA's Blue Marble, turning
with the Earth rotation angle, lit by the Sun, with its atmosphere's rim)
under NASA's star map, the Moon, each spacecraft (its 3D model, turned by
the run's attitude) with its path, trail, body axes, Sun, nadir and
velocity arrows, its instruments' fields of view and its thrusters'
plumes, the ground stations with their line of sight to each spacecraft
they see, and the ground track; an overlay with the time (ISO 8601 UTC),
the playback speed and the followed spacecraft's altitude and speed.

Views (the View list, ``[`` and ``]``): **Whole orbit** (around the
central body; the spacecraft drawn larger than they are, the factor
shown), **Follow** a spacecraft (true size, around it), **Earth-fixed**
(the camera turns with the Earth), and the view **from** a spacecraft
along a body axis or an instrument's boresight, with that instrument's
field of view. Drag to turn, scroll to zoom, right-drag to pan,
double-click (or Home) to reset. **Show** switches what is drawn
(remembered per user) and the reduced quality, which the page also
chooses by itself when frames take longer than 50 ms.

The slider and the shared time cursor move together. The scene
(``engine.scene3d``) and the data the page takes are built off the GUI
thread (:class:`SceneBuilder`); the page (``gui/assets/mission_view/``:
three.js, bundled, and ``mission_view.js``) opens in a web view made the
first time the tab is shown, and draws each frame itself, so playback
costs Python only the frame's index. Its look is the theme's
(``theme/mission_view_style.py``), restyled on a theme change without
reloading anything.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMenu, QPushButton, QSlider, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from ..constants import CENTRAL_BODY_EQUATORIAL_RADIUS_KM
from ..engine import scene3d
from ..schema.epochs import parse_epoch_utc
from .theme import SPACE, current_theme, icon, mono_font, on_change, set_role
from .theme.mission_view_style import mission_view_style
from .theme.palettes import SPACE_COLOUR

ASSETS = Path(__file__).resolve().parent / "assets" / "mission_view"
PAGE = ASSETS / "mission_view.html"
_TICK_MS = 40  # [ms] playback timer: 25 frames a second
_ORBIT_CRAFT_FRACTION = 0.04  # [-] in Whole orbit, a spacecraft is drawn this fraction of the scene's half-width
_REDUCE_ABOVE_MS = 50.0  # [ms] the page draws in reduced quality when a frame takes longer (under 20 fps)
#: Playback speeds offered: simulated seconds per real second.
SPEEDS = (1, 10, 60, 300, 1800, 3600, 21600, 86400)
#: What the Show menu switches, in its order: key in the page, menu text.
TOGGLES = (("paths", "Paths"), ("trails", "Trails"), ("axes", "Body axes"),
           ("headings", "Sun, nadir and velocity arrows"), ("cones", "Fields of view and plumes"),
           ("stations", "Ground stations and line of sight"), ("labels", "Labels"), ("stars", "Stars"),
           ("groundTrack", "Ground track"))
_TOGGLES_OFF = ("groundTrack",)  # off until the user turns them on
_AXES = (("+x", (1, 0, 0)), ("+y", (0, 1, 0)), ("+z", (0, 0, 1)), ("-z", (0, 0, -1)))
_SETTINGS_GROUP = "mission_view"


def _settings() -> QSettings:
    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


def _linear(rgb: np.ndarray) -> np.ndarray:
    """sRGB components (0 to 1) to linear light, as WebGL vertex colours take them."""
    rgb = np.asarray(rgb, dtype=float)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _rows(array, decimals: int) -> list:
    return np.round(np.asarray(array, dtype=float), decimals).tolist()


def scene_payload(scene: scene3d.Scene) -> dict:
    """``scene`` as the page's ``MV.load`` takes it: kilometres, seconds,
    plain lists. Colours are not in it (``MV.setStyle``), except each 3D
    part's own (the model's data, as linear light)."""
    from ..engine.geodesy import ellipsoid_for

    epoch = parse_epoch_utc(scene.epoch_utc)
    crafts = []
    for craft in scene.crafts:
        positions, normals = scene3d.mesh_normals(craft.vertices_km, craft.triangles)
        colours = np.repeat(_linear(craft.face_rgb), 3, axis=0)
        crafts.append({
            "name": craft.name, "size": craft.size_km, "pos": _rows(craft.position_km, 5),
            "vel": _rows(craft.velocity_km_s, 6), "alt": None if craft.altitude_km is None
            else _rows(craft.altitude_km, 3), "dcm": None if craft.dcm_BN is None
            else _rows(craft.dcm_BN.reshape(-1, 9), 6),
            "mesh": {"p": _rows(positions.ravel(), 8), "n": _rows(normals.ravel(), 4),
                     "c": _rows(colours.ravel(), 4)},
            "path": _rows(craft.path_km, 3),
            "track": None if craft.ground_track_deg is None else _rows(craft.ground_track_deg, 3),
            "equipment": [{"name": item["name"], "kind": item["kind"], "p": _rows(item["position_km"], 8),
                           "b": _rows(item["boresight"], 6), "fov": item["fov_deg"], "plume": item["plume_half_deg"]}
                          for item in craft.equipment]})
    flattening = ellipsoid_for(scene.body, scene.body_radius_km * 1000.0).flattening if scene.body_radius_km else 0.0
    return {
        "epoch_ms": (epoch - datetime(1970, 1, 1)).total_seconds() * 1000.0, "times": _rows(scene.times_s, 3),
        "body": {"name": scene.body.title(), "radius": scene.body_radius_km, "flattening": flattening,
                 "earth": scene.body == "earth", "rotation": None if scene.body_rotation_rad is None
                 else _rows(scene.body_rotation_rad, 7)},
        "sun": None if scene.sun_direction_N is None else _rows(scene.sun_direction_N, 6),
        "moon": None if scene.moon_position_km is None else _rows(scene.moon_position_km, 1),
        "moon_radius": CENTRAL_BODY_EQUATORIAL_RADIUS_KM["moon"], "crafts": crafts,
        "stations": [{"name": name, "p": _rows(point, 4), "min_el": minimum,
                      "visible": scene.station_visible[n].astype(int).tolist()}
                     for n, ((name, point), minimum) in enumerate(zip(scene.stations, scene.station_min_elevation_deg))],
        "extent": scene.extent_km, "orbit_fraction": _ORBIT_CRAFT_FRACTION}


def views(scene: scene3d.Scene) -> list[tuple[str, dict]]:
    """The View list: its texts and the page's camera of each."""
    found = [("Whole orbit", {"mode": "orbit"})]
    found += [(f"Follow {craft.name}", {"mode": "follow", "craft": n}) for n, craft in enumerate(scene.crafts)]
    if scene.body_rotation_rad is not None:
        found.append(("Earth-fixed", {"mode": "earth"}))
    for n, craft in enumerate(scene.crafts):
        found += [(f"From {craft.name} along {name}_B", {"mode": "instrument", "craft": n, "axis": list(axis)})
                  for name, axis in _AXES]
        found += [(f"From {craft.name}: {item['name']} ({item['fov_deg']:g}° field of view)",
                   {"mode": "instrument", "craft": n, "item": k})
                  for k, item in enumerate(craft.equipment) if item["fov_deg"]]
    return found


class SceneBuilder(QThread):
    """Builds the scene and the page's data off the GUI thread."""

    built = Signal(object, str)  # engine.scene3d.Scene, its MV.load payload as JSON
    failed = Signal(str)

    def __init__(self, scenario, result, base_dir, parent=None):
        super().__init__(parent)
        self._scenario, self._result, self._base_dir = scenario, result, base_dir

    def run(self) -> None:
        try:
            scene = scene3d.build_scene(self._scenario, self._result, base_dir=self._base_dir)
            payload = json.dumps(scene_payload(scene), separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001 -- shown in the view; the run itself is not affected
            self.failed.emit(str(exc))
            return
        self.built.emit(scene, payload)


class MissionViewWidget(QWidget):
    """Results › 3D View. :meth:`set_run` gives it a run; the view is built
    when the tab is shown."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.scene: scene3d.Scene | None = None
        self._payload: str | None = None  # the scene's MV.load data
        self._run = None  # (scenario, result, base_dir) not yet built
        self._builder: SceneBuilder | None = None
        self._time_cursor = None
        self._following_cursor = False
        self._epoch = None
        self._sim_time = 0.0  # [s] playback position
        self.web_view = None
        self._page_ready = False
        self._scene_sent = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["sm"])
        controls = QHBoxLayout()
        controls.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], 0)
        controls.setSpacing(SPACE["sm"])
        self.play_button = QPushButton(icon("play"), "Play")
        self.play_button.setToolTip("Play the run (Space)")
        self.play_button.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_button)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setToolTip("The time shown; it moves the time cursor on the plots and the Timeline")
        self.slider.valueChanged.connect(self._on_slider)
        controls.addWidget(self.slider, 1)
        self.time_label = QLabel()
        self.time_label.setFont(mono_font())
        self.time_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self.time_label)
        self.speed_combo = QComboBox()
        self.speed_combo.setToolTip("Playback speed: simulated time per second")
        for speed in SPEEDS:
            self.speed_combo.addItem(_speed_text(speed), speed)
        self.speed_combo.currentIndexChanged.connect(lambda _index: self._send_playback())
        controls.addWidget(self.speed_combo)
        self.view_combo = QComboBox()
        self.view_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.view_combo.setToolTip("The camera: whole orbit, following a spacecraft, Earth-fixed, or from a "
                                   "spacecraft along an axis or an instrument ([ and ] to step; Home or a "
                                   "double-click resets it)")
        self.view_combo.currentIndexChanged.connect(self._on_view)
        controls.addWidget(self.view_combo)
        self.show_button = QToolButton()
        self.show_button.setText("Show")
        self.show_button.setIcon(icon("sliders-horizontal"))
        self.show_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.show_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.show_button.setToolTip("What the view draws, and its quality")
        self.show_menu = QMenu(self.show_button)
        self.toggle_actions: dict[str, QAction] = {}
        settings = _settings()
        for key, text in TOGGLES:
            action = self.show_menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(_as_bool(settings.value(f"{_SETTINGS_GROUP}/{key}", key not in _TOGGLES_OFF)))
            action.toggled.connect(lambda on, key=key: self._on_toggle(key, on))
            self.toggle_actions[key] = action
        self.show_menu.addSeparator()
        self.quality_action = self.show_menu.addAction("Reduced quality")
        self.quality_action.setCheckable(True)
        self.quality_action.setChecked(_as_bool(settings.value(f"{_SETTINGS_GROUP}/reduced", False)))
        self.quality_action.setToolTip("Smaller textures, no atmosphere, one pixel per screen pixel: faster "
                                       "without a graphics card. Chosen by itself when frames are slow.")
        self.quality_action.toggled.connect(self._on_quality)
        self.reset_action = self.show_menu.addAction("Reset view")
        self.reset_action.setShortcut(QKeySequence("Home"))
        self.reset_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.reset_action.triggered.connect(lambda: self._call("MV.resetView();"))
        self.addAction(self.reset_action)
        self.show_button.setMenu(self.show_menu)
        controls.addWidget(self.show_button)
        layout.addLayout(controls)
        self.scale_note = QLabel()
        set_role(self.scale_note, tone="secondary")
        self.scale_note.setContentsMargins(SPACE["md"], 0, SPACE["md"], 0)
        self.scale_note.setWordWrap(True)
        layout.addWidget(self.scale_note)
        for keys, slot in (("Space", self.toggle_play), ("[", lambda: self._step_view(-1)),
                           ("]", lambda: self._step_view(1))):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

        self.stack = QStackedWidget()
        self.empty = QLabel("Run a scenario to see it here in 3D.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        set_role(self.empty, tone="secondary")
        self.stack.addWidget(self.empty)
        layout.addWidget(self.stack, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._set_controls_enabled(False)
        on_change(self._on_theme_changed)

    # -- the run ---------------------------------------------------------------
    def set_run(self, scenario, result, base_dir=None) -> None:
        """The run to show; built now if the tab is shown, else when it is.
        Without its scenario there is nothing to place, and the view is empty."""
        if scenario is None or result is None:
            self.clear()
            return
        self.pause()
        self._run = (scenario, result, base_dir)
        self.scene = None
        try:
            self._epoch = parse_epoch_utc(scenario.epoch_utc)
        except (TypeError, ValueError):
            self._epoch = None
        self.empty.setText("Building the 3D view...")
        self.stack.setCurrentWidget(self.empty)
        self._set_controls_enabled(False)
        if self.isVisible():
            self._build()

    def clear(self) -> None:
        self.pause()
        self._run = None
        self.scene = None
        self.empty.setText("Run a scenario to see it here in 3D.")
        self.stack.setCurrentWidget(self.empty)
        self._set_controls_enabled(False)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if self._run is not None and self.scene is None and self._builder is None:
            self._build()

    def _build(self) -> None:
        scenario, result, base_dir = self._run
        builder = SceneBuilder(scenario, result, base_dir, self)
        builder.built.connect(self._on_built)
        builder.failed.connect(self._on_failed)
        builder.finished.connect(lambda b=builder: self._builder_done(b))
        self._builder = builder
        builder.start()

    def _builder_done(self, builder) -> None:
        if self._builder is builder:
            self._builder = None
        builder.deleteLater()

    def wait_for_worker(self) -> None:
        """Let a scene still being built finish (closing the window)."""
        if self._builder is not None:
            self._builder.wait()

    def _on_failed(self, message: str) -> None:
        self.empty.setText(f"The 3D view could not be built: {message}")
        self.stack.setCurrentWidget(self.empty)

    def _on_built(self, scene, payload: str) -> None:
        if self._run is None:
            return
        self._run = None
        self.scene = scene
        self._payload = payload
        self._scene_sent = False
        self._ensure_view()
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(scene.times_s) - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._sim_time = float(scene.times_s[0])
        duration = float(scene.times_s[-1] - scene.times_s[0])
        self.speed_combo.blockSignals(True)
        self.speed_combo.setCurrentIndex(_speed_index(duration))
        self.speed_combo.blockSignals(False)
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        for text, spec in views(scene):
            self.view_combo.addItem(text, spec)
        self.view_combo.blockSignals(False)
        self._show_scale_note()
        self._update_time_label(0)
        self._set_controls_enabled(True)
        self.stack.setCurrentWidget(self.web_view)
        self._send_scene()

    def _show_scale_note(self) -> None:
        scene = self.scene
        if scene is None:
            return
        spec = self.view_combo.currentData() or {"mode": "orbit"}
        if spec["mode"] in ("orbit", "earth"):
            factors = [max(1.0, _ORBIT_CRAFT_FRACTION * scene.extent_km / craft.size_km) for craft in scene.crafts]
            text = (f"Spacecraft drawn {min(factors):,.0f}× larger than they are, to be seen at this scale."
                    if max(factors) > 1.0 else "Everything at its true size.")
            if spec["mode"] == "earth":
                text += " The camera turns with the Earth."
        elif spec["mode"] == "follow":
            text = ("True size, centred on the spacecraft. Body axes: x red, y green, z blue; arrows to the Sun, "
                    "to nadir and along the velocity.")
        else:
            text = "True size, from the spacecraft: " + self.view_combo.currentText().split(" ", 2)[-1] + "."
        notes = [n for n in scene.notes if n]
        self.scale_note.setText(" ".join([text] + notes))

    # -- the page ----------------------------------------------------------------
    def _ensure_view(self) -> None:
        if self.web_view is not None:
            return
        from . import webengine_setup  # noqa: F401 -- the Chromium flags, before QtWebEngine is imported

        webengine_setup.guard_profile()  # the app's own pages only (docs/reference/network.md)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(QColor(SPACE_COLOUR))
        self.stack.addWidget(self.web_view)
        self.web_view.loadFinished.connect(self._on_loaded)
        self.web_view.titleChanged.connect(self._on_page_title)
        self.web_view.load(QUrl.fromLocalFile(str(PAGE)))

    def _on_loaded(self, ok: bool) -> None:
        self._page_ready = bool(ok)
        if not self._page_ready:
            return
        page = self.web_view.page()
        page.runJavaScript(f"MV.setStyle({json.dumps(mission_view_style(current_theme()))});"
                           f"MV.configure({json.dumps({'reduce_above_ms': _REDUCE_ABOVE_MS})});")
        for key, action in self.toggle_actions.items():
            page.runJavaScript(f"MV.setToggle({json.dumps(key)}, {json.dumps(action.isChecked())});")
        if self.quality_action.isChecked():
            page.runJavaScript("MV.configure({auto_quality: false}); MV.setQuality('reduced');")
        self._send_scene()

    def _send_scene(self) -> None:
        """The scene, its view, frame and playback, once the page is ready."""
        if not self._page_ready or self._payload is None or self._scene_sent:
            return
        self._scene_sent = True
        page = self.web_view.page()
        page.runJavaScript("MV.load(" + self._payload + ");")
        page.runJavaScript(f"MV.setView({json.dumps(self.view_combo.currentData() or {'mode': 'orbit'})});"
                           f"MV.setFrame({self.slider.value()});")
        self._send_playback()

    def _call(self, script: str, callback=None) -> None:
        """Run ``script`` in the page once it shows the scene (else it is
        sent with the scene: the view, frame and toggles are re-sent)."""
        if self.web_view is None or not self._page_ready or not self._scene_sent:
            return
        if callback is None:
            self.web_view.page().runJavaScript(script)
        else:
            self.web_view.page().runJavaScript(script, 0, callback)

    def _send_playback(self) -> None:
        speed = self.speed_combo.currentData()
        self._call(f"MV.setPlayback({json.dumps({'speed': _speed_text(int(speed)) if speed else '', 'playing': self.is_playing()})});")

    def _on_page_title(self, title: str) -> None:
        """The page chose reduced quality by itself (its frames were slow)."""
        if title == "mv:reduced-auto" and not self.quality_action.isChecked():
            self.quality_action.blockSignals(True)
            self.quality_action.setChecked(True)
            self.quality_action.blockSignals(False)

    def _on_toggle(self, key: str, on: bool) -> None:
        _settings().setValue(f"{_SETTINGS_GROUP}/{key}", bool(on))
        if self._page_ready:
            self.web_view.page().runJavaScript(f"MV.setToggle({json.dumps(key)}, {json.dumps(bool(on))});")

    def _on_quality(self, reduced: bool) -> None:
        _settings().setValue(f"{_SETTINGS_GROUP}/reduced", bool(reduced))
        if self._page_ready:
            self.web_view.page().runJavaScript(
                f"MV.configure({{auto_quality: false}}); MV.setQuality({json.dumps('reduced' if reduced else 'full')});")

    def _on_theme_changed(self, mode: str) -> None:
        """Restyle the page (no reload: the textures and the scene stay)."""
        if self.web_view is not None and self._page_ready:
            self.web_view.page().runJavaScript(f"MV.setStyle({json.dumps(mission_view_style(mode))});")

    # -- playback ------------------------------------------------------------------
    def toggle_play(self) -> None:
        if self._timer.isActive():
            self.pause()
        elif self.scene is not None:
            if self.slider.value() >= self.slider.maximum():
                self._sim_time = float(self.scene.times_s[0])
            self._timer.start()
            self.play_button.setText("Pause")
            self.play_button.setToolTip("Pause (Space)")
            self._send_playback()

    def pause(self) -> None:
        was_playing = self._timer.isActive()
        self._timer.stop()
        self.play_button.setText("Play")
        self.play_button.setToolTip("Play the run (Space)")
        if was_playing:
            self._send_playback()
            self._move_cursor()

    def is_playing(self) -> bool:
        return self._timer.isActive()

    def _tick(self) -> None:
        times = self.scene.times_s
        self._sim_time += float(self.speed_combo.currentData()) * _TICK_MS / 1000.0
        if self._sim_time >= times[-1]:
            self._sim_time = float(times[-1])
            self.show_frame(len(times) - 1)
            self.pause()
            return
        self.show_frame(int(np.searchsorted(times, self._sim_time)))

    def show_frame(self, frame: int) -> None:
        """Show frame ``frame`` (the slider follows)."""
        if self.scene is None:
            return
        frame = int(np.clip(frame, 0, len(self.scene.times_s) - 1))
        self.slider.blockSignals(True)
        self.slider.setValue(frame)
        self.slider.blockSignals(False)
        self._update_time_label(frame)
        self._call(f"MV.setFrame({frame});")

    def _on_slider(self, frame: int) -> None:
        if self.scene is None:
            return
        self._sim_time = float(self.scene.times_s[frame])
        self._update_time_label(frame)
        self._call(f"MV.setFrame({frame});")
        if not self._timer.isActive():
            self._move_cursor()

    def _on_view(self, _index: int) -> None:
        spec = self.view_combo.currentData()
        if spec is None:
            return
        self._show_scale_note()
        self._call(f"MV.setView({json.dumps(spec)});")

    def _step_view(self, step: int) -> None:
        if self.view_combo.count() and self.view_combo.isEnabled():
            self.view_combo.setCurrentIndex((self.view_combo.currentIndex() + step) % self.view_combo.count())

    def _update_time_label(self, frame: int) -> None:
        if self.scene is None:
            self.time_label.clear()
            return
        seconds = float(self.scene.times_s[frame])
        moment = (self._epoch + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ") if self._epoch else ""
        self.time_label.setText(f"T+{_elapsed_text(seconds)}  {moment}")

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.play_button, self.slider, self.speed_combo, self.view_combo, self.show_button):
            widget.setEnabled(enabled)
        if not enabled:
            self.time_label.clear()
            self.scale_note.clear()

    # -- the shared time cursor --------------------------------------------------------
    def set_time_cursor(self, cursor) -> None:
        self._time_cursor = cursor
        cursor.changed.connect(self._on_cursor)

    def _move_cursor(self) -> None:
        if self._time_cursor is not None and self.scene is not None:
            self._following_cursor = True
            try:
                self._time_cursor.set_time(float(self.scene.times_s[self.slider.value()]))
            finally:
                self._following_cursor = False

    def _on_cursor(self, time_s) -> None:
        if self._following_cursor or time_s is None or self.scene is None or self._timer.isActive():
            return
        self._sim_time = float(time_s)
        self.show_frame(int(np.argmin(np.abs(self.scene.times_s - float(time_s)))))


def _as_bool(value) -> bool:
    """A QSettings value (a bool, or "true"/"false" read back from the file)."""
    return value is True or str(value).lower() == "true"


def _speed_text(speed: int) -> str:
    if speed < 60:
        return f"{speed} s/s"
    if speed < 3600:
        return f"{speed // 60} min/s"
    if speed < 86400:
        return f"{speed // 3600} h/s"
    return f"{speed // 86400} d/s"


def _speed_index(duration_s: float) -> int:
    """The speed that plays the whole run in about 30 s."""
    wanted = duration_s / 30.0
    return int(np.argmin([abs(np.log(max(speed, 1e-9) / max(wanted, 1e-9))) for speed in SPEEDS]))


def _elapsed_text(seconds: float) -> str:
    whole = int(round(seconds))
    days, rest = divmod(whole, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    return (f"{days}d " if days else "") + f"{hours:02d}:{minutes:02d}:{secs:02d}"
