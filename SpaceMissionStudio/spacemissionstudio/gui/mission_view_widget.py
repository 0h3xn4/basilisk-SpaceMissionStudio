#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
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

The central body (Earth shaded by its albedo map and turning), each
spacecraft's path, the spacecraft themselves (their 3D model, turned by
the run's attitude), the ground stations and the Sun's direction, played
back over the run. **Whole orbit** shows everything, the spacecraft drawn
larger than they are so they can be seen (the factor is shown);
**Follow** a spacecraft shows it at its true size with its body axes and
the Sun's direction from it. The slider and the shared time cursor move
together: a time picked on a plot or the Timeline is shown here, and the
time shown here is the cursor elsewhere.

The scene (``engine.scene3d``) is built off the GUI thread; the page is
plotly.js, the copy installed with plotly (offline, as the Results plots),
in a web view made the first time the tab is shown. Playback moves the
models in the page itself (``MV.setFrame``), so a frame costs no Python
work beyond picking its index.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import temp_folders
from ..engine import scene3d
from ..schema.epochs import parse_epoch_utc
from .results_widget import _plotlyjs_path
from .theme import SPACE, TOKENS, current_theme, icon, mono_font, on_change, set_role
from .theme.palettes import AXIS_COLOURS, EARTH_COLOURSCALE, PLAIN_BODY_COLOUR, SUN_COLOUR, categorical
from .theme.plotly_template import WEB_FONT_STACK

_DIV_ID = "mission-view"
_TICK_MS = 40  # [ms] playback timer: 25 frames a second
_ORBIT_CRAFT_FRACTION = 0.04  # [-] in Whole orbit, a spacecraft is drawn this fraction of the scene's half-width
_FOLLOW_HALF_WIDTH = 1.6  # [-] in Follow, the view's half-width in spacecraft sizes
#: Playback speeds offered: simulated seconds per real second.
SPEEDS = (1, 10, 60, 300, 1800, 3600, 21600, 86400)
_BODY_ROWS, _BODY_COLUMNS = 37, 73  # [-] vertices of the body sphere: every 5 degrees

_PAGE_SCRIPT = r"""
const MV = {s: null, mode: -1, frame: 0, paths: true, ready: false};
MV.rot = function (x, y, a) { const c = Math.cos(a), s = Math.sin(a); return [c * x - s * y, s * x + c * y]; };
MV.toN = function (d, v) {  // C^T v, C = dcm_BN row-major
  return [d[0] * v[0] + d[3] * v[1] + d[6] * v[2], d[1] * v[0] + d[4] * v[1] + d[7] * v[2],
          d[2] * v[0] + d[5] * v[1] + d[8] * v[2]];
};
MV.I = [1, 0, 0, 0, 1, 0, 0, 0, 1];
MV.load = function (s) {
  MV.s = s; const st = s.style, b = s.body, data = [];
  data.push({type: 'mesh3d', x: b.x, y: b.y, z: b.z, i: b.i, j: b.j, k: b.k, name: s.body_name,
    intensity: b.intensity, colorscale: st.earth, cmin: 0, cmax: 0.8, showscale: false,
    color: b.intensity ? undefined : st.plain, flatshading: false, hoverinfo: 'name',
    lighting: {ambient: 0.35, diffuse: 0.9, specular: 0.05, roughness: 0.9}, lightposition: {x: 1e5, y: 0, z: 0}});
  data.push({type: 'scatter3d', mode: 'lines+text', x: [0, 0], y: [0, 0], z: [0, 0], name: 'Sun direction',
    line: {color: st.sun, width: 5}, text: ['', 'Sun'], textfont: {color: st.sun}, hoverinfo: 'name',
    visible: s.sun !== null});
  data.push({type: 'scatter3d', mode: 'markers+text', x: [], y: [], z: [], name: 'Ground stations',
    text: s.stations.map(p => p.name), textposition: 'top center', textfont: {color: st.text},
    marker: {size: 4, color: st.text, symbol: 'diamond'}, hoverinfo: 'text', visible: s.stations.length > 0});
  s.crafts.forEach(function (c) {
    data.push({type: 'scatter3d', mode: 'lines', x: c.path.x, y: c.path.y, z: c.path.z, name: c.name + ' path',
      line: {color: c.colour, width: 2}, hoverinfo: 'name'});
    data.push({type: 'mesh3d', x: [], y: [], z: [], i: c.i, j: c.j, k: c.k, facecolor: c.facecolor,
      name: c.name, hoverinfo: 'name', flatshading: true,
      lighting: {ambient: 0.45, diffuse: 0.8, specular: 0.2, roughness: 0.6}, lightposition: {x: 1e5, y: 0, z: 0}});
    data.push({type: 'scatter3d', mode: 'markers+text', x: [0], y: [0], z: [0], text: [c.name],
      textposition: 'top center', textfont: {color: c.colour}, marker: {size: 3, color: c.colour},
      name: c.name, hoverinfo: 'name'});
  });
  ['x', 'y', 'z'].forEach(function (axis, n) {
    data.push({type: 'scatter3d', mode: 'lines+text', x: [0, 0], y: [0, 0], z: [0, 0], text: ['', axis + '<sub>B</sub>'],
      textfont: {color: st.axes[n]}, line: {color: st.axes[n], width: 5}, name: 'body ' + axis, hoverinfo: 'name',
      visible: false});
  });
  data.push({type: 'scatter3d', mode: 'lines+text', x: [0, 0], y: [0, 0], z: [0, 0], text: ['', 'Nadir'],
    textfont: {color: st.text}, line: {color: st.text, width: 3, dash: 'dash'}, name: 'Nadir', hoverinfo: 'name',
    visible: false});
  const hidden = {visible: false, showgrid: false, zeroline: false, showticklabels: false, title: ''};
  const layout = {paper_bgcolor: st.bg, margin: {l: 0, r: 0, t: 0, b: 0}, showlegend: false, uirevision: 'keep',
    font: {family: st.font, color: st.text},
    scene: {bgcolor: st.bg, aspectmode: 'cube', xaxis: hidden, yaxis: hidden, zaxis: hidden,
      camera: {eye: {x: 1.25, y: 1.25, z: 0.8}}}};
  MV.mode = -1;
  return Plotly.react('mission-view', data, layout, {displaylogo: false, responsive: true}).then(function () {
    MV.ready = true; MV.setView(-1); MV.setFrame(MV.frame < s.times.length ? MV.frame : 0); return s.times.length;
  });
};
MV.crafts = function () { return 3; };  // traces before the first spacecraft
MV.axesTrace = function () { return 3 + 3 * MV.s.crafts.length; };
MV.setView = function (target) {  // -1: whole orbit; n: follow spacecraft n, drawn at the origin
  MV.mode = target; const s = MV.s, follow = target >= 0, a = MV.axesTrace();
  Plotly.restyle('mission-view', {visible: follow}, [a, a + 1, a + 2, a + 3]);
  Plotly.restyle('mission-view', {visible: !follow}, [0].concat(s.stations.length ? [2] : []));
  MV.setPaths(MV.paths);
  const e = follow ? s.crafts[target].size * s.follow_half_width : s.extent;
  Plotly.relayout('mission-view', {'scene.xaxis.range': [-e, e], 'scene.yaxis.range': [-e, e],
                                   'scene.zaxis.range': [-e, e]});
  MV.setFrame(MV.frame);
};
MV.setPaths = function (shown) {  // paths are drawn in Whole orbit only
  MV.paths = shown; const s = MV.s, indices = s.crafts.map((c, n) => 3 + 3 * n);
  Plotly.restyle('mission-view', {visible: shown && MV.mode < 0}, indices);
};
MV.scaleFor = function (c) { return MV.mode < 0 ? Math.max(1, MV.s.orbit_fraction * MV.s.extent / c.size) : 1; };
MV.setFrame = function (f) {
  const s = MV.s; if (!s || !MV.ready) return; MV.frame = f;
  const xs = [], ys = [], zs = [], idx = [];
  const angle = s.rotation ? s.rotation[f] : 0, b = s.body;
  if (s.rotation) {
    const bx = [], by = [];
    for (let n = 0; n < b.x.length; n++) { const r = MV.rot(b.x[n], b.y[n], angle); bx.push(r[0]); by.push(r[1]); }
    xs.push(bx); ys.push(by); zs.push(b.z); idx.push(0);
  }
  const sun = s.sun ? s.sun[f] : null;
  // Follow: everything relative to the followed spacecraft, so the view's
  // few metres keep their precision (WebGL draws in single precision).
  const origin = MV.mode >= 0 ? s.crafts[MV.mode].pos[f] : [0, 0, 0];
  const reach = MV.mode >= 0 ? s.crafts[MV.mode].size * s.follow_half_width * 0.9 : s.extent * 0.95;
  if (sun) {
    xs.push([0, sun[0] * reach]); ys.push([0, sun[1] * reach]); zs.push([0, sun[2] * reach]); idx.push(1);
  }
  if (s.stations.length) {
    const sx = [], sy = [], sz = [];
    s.stations.forEach(function (p) { const r = MV.rot(p.p[0], p.p[1], angle); sx.push(r[0]); sy.push(r[1]); sz.push(p.p[2]); });
    xs.push(sx); ys.push(sy); zs.push(sz); idx.push(2);
  }
  s.crafts.forEach(function (c, n) {
    const d = c.dcm ? c.dcm[f] : MV.I, k = MV.scaleFor(c), mx = [], my = [], mz = [];
    const p = [c.pos[f][0] - origin[0], c.pos[f][1] - origin[1], c.pos[f][2] - origin[2]];
    c.verts.forEach(function (v) { const w = MV.toN(d, v); mx.push(p[0] + k * w[0]); my.push(p[1] + k * w[1]); mz.push(p[2] + k * w[2]); });
    xs.push(mx); ys.push(my); zs.push(mz); idx.push(4 + 3 * n);
    xs.push([p[0]]); ys.push([p[1]]); zs.push([p[2]]); idx.push(5 + 3 * n);
  });
  if (MV.mode >= 0) {
    const c = s.crafts[MV.mode], d = c.dcm ? c.dcm[f] : MV.I, len = c.size * 1.2;
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]].forEach(function (e, n) {
      const w = MV.toN(d, e);
      xs.push([0, len * w[0]]); ys.push([0, len * w[1]]); zs.push([0, len * w[2]]); idx.push(MV.axesTrace() + n);
    });
    const r = Math.hypot(origin[0], origin[1], origin[2]) || 1;
    xs.push([0, -origin[0] / r * reach]); ys.push([0, -origin[1] / r * reach]); zs.push([0, -origin[2] / r * reach]);
    idx.push(MV.axesTrace() + 3);
  }
  Plotly.restyle('mission-view', {x: xs, y: ys, z: zs}, idx);
  if (sun) {
    const light = {x: sun[0] * 1e5, y: sun[1] * 1e5, z: sun[2] * 1e5};
    const meshes = [0].concat(s.crafts.map((c, n) => 4 + 3 * n));
    Plotly.restyle('mission-view', {lightposition: meshes.map(() => light)}, meshes);
  }
};
"""


def body_mesh(radius_km: float, albedo: np.ndarray | None) -> dict:
    """A sphere in the body-fixed frame, every 5 degrees, with the albedo
    map's value at each vertex when there is one."""
    latitudes = np.radians(np.linspace(-90.0, 90.0, _BODY_ROWS))
    longitudes = np.radians(np.linspace(-180.0, 180.0, _BODY_COLUMNS))
    lat, lon = np.meshgrid(latitudes, longitudes, indexing="ij")
    x = radius_km * np.cos(lat) * np.cos(lon)
    y = radius_km * np.cos(lat) * np.sin(lon)
    z = radius_km * np.sin(lat)
    triangles = []
    for row in range(_BODY_ROWS - 1):
        for column in range(_BODY_COLUMNS - 1):
            a = row * _BODY_COLUMNS + column
            b, c, d = a + 1, a + _BODY_COLUMNS, a + _BODY_COLUMNS + 1
            triangles += [(a, b, d), (a, d, c)]
    triangles = np.array(triangles)
    mesh = {"x": np.round(x.ravel(), 3).tolist(), "y": np.round(y.ravel(), 3).tolist(),
            "z": np.round(z.ravel(), 3).tolist(), "i": triangles[:, 0].tolist(), "j": triangles[:, 1].tolist(),
            "k": triangles[:, 2].tolist(), "intensity": None}
    if albedo is not None:
        rows, columns = albedo.shape
        r = np.clip(((np.degrees(lat) + 90.0) / 180.0 * rows).astype(int), 0, rows - 1)
        c = np.clip(((np.degrees(lon) + 180.0) / 360.0 * columns).astype(int), 0, columns - 1)
        mesh["intensity"] = np.round(albedo[r, c].ravel(), 3).tolist()
    return mesh


def scene_payload(scene: scene3d.Scene, mode: str) -> dict:
    """``scene`` as the page's ``MV.load`` takes it: lists, kilometres, the
    theme's colours."""
    colours = categorical(mode)
    crafts = []
    for n, craft in enumerate(scene.crafts):
        triangles = craft.triangles
        crafts.append({
            "name": craft.name, "colour": colours[n % len(colours)], "size": craft.size_km,
            "pos": np.round(craft.position_km, 4).tolist(),
            "dcm": None if craft.dcm_BN is None else np.round(craft.dcm_BN.reshape(-1, 9), 6).tolist(),
            "verts": np.round(craft.vertices_km, 7).tolist(), "i": triangles[:, 0].tolist(),
            "j": triangles[:, 1].tolist(), "k": triangles[:, 2].tolist(), "facecolor": craft.face_colors,
            "path": {axis: np.round(craft.path_km[:, n_axis], 3).tolist() for n_axis, axis in enumerate("xyz")}})
    return {
        "times": np.round(scene.times_s, 3).tolist(), "body_name": scene.body.title(),
        "rotation": None if scene.body_rotation_rad is None else np.round(scene.body_rotation_rad, 6).tolist(),
        "sun": None if scene.sun_direction_N is None else np.round(scene.sun_direction_N, 5).tolist(),
        "body": body_mesh(scene.body_radius_km, scene.body_albedo), "crafts": crafts,
        "stations": [{"name": name, "p": np.round(point, 3).tolist()} for name, point in scene.stations],
        "extent": scene.extent_km, "orbit_fraction": _ORBIT_CRAFT_FRACTION, "follow_half_width": _FOLLOW_HALF_WIDTH,
        "style": {"bg": TOKENS["bg.surface"], "text": TOKENS["text.primary"], "font": WEB_FONT_STACK,
                  "earth": EARTH_COLOURSCALE, "plain": PLAIN_BODY_COLOUR, "sun": SUN_COLOUR,
                  "axes": list(AXIS_COLOURS)}}


_ALBEDO: dict = {}  # the Earth albedo map, read once per process (None when not installed)


class SceneBuilder(QThread):
    """Builds the scene off the GUI thread (the albedo map is read with
    Basilisk's data fetcher the first time)."""

    built = Signal(object)  # engine.scene3d.Scene
    failed = Signal(str)

    def __init__(self, scenario, result, base_dir, parent=None):
        super().__init__(parent)
        self._scenario, self._result, self._base_dir = scenario, result, base_dir

    def run(self) -> None:
        try:
            if "earth" not in _ALBEDO and self._scenario.gravity.central_body == "earth":
                _ALBEDO["earth"] = scene3d.earth_albedo_map()
            scene = scene3d.build_scene(self._scenario, self._result, base_dir=self._base_dir,
                                        albedo=_ALBEDO.get("earth"))
        except Exception as exc:  # noqa: BLE001 -- shown in the view; the run itself is not affected
            self.failed.emit(str(exc))
            return
        self.built.emit(scene)


class MissionViewWidget(QWidget):
    """Results › 3D View. :meth:`set_run` gives it a run; the view is built
    when the tab is shown."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.scene: scene3d.Scene | None = None
        self._run = None  # (scenario, result, base_dir) not yet built
        self._builder: SceneBuilder | None = None
        self._time_cursor = None
        self._following_cursor = False
        self._epoch = None
        self._sim_time = 0.0  # [s] playback position
        self.web_view = None
        self._page_ready = False
        self._pending: str | None = None
        self._page_dir = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["sm"])
        controls = QHBoxLayout()
        controls.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], 0)
        controls.setSpacing(SPACE["sm"])
        self.play_button = QPushButton(icon("play"), "Play")
        self.play_button.setToolTip("Play the run")
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
        controls.addWidget(self.speed_combo)
        self.view_combo = QComboBox()
        self.view_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.view_combo.setToolTip("Whole orbit, or one spacecraft at its true size with its body axes")
        self.view_combo.currentIndexChanged.connect(self._on_view)
        controls.addWidget(self.view_combo)
        self.paths_box = QCheckBox("Paths")
        self.paths_box.setChecked(True)
        self.paths_box.setToolTip("Show each spacecraft's path over the run")
        self.paths_box.toggled.connect(lambda shown: self._call(f"MV.setPaths({json.dumps(bool(shown))});"))
        controls.addWidget(self.paths_box)
        layout.addLayout(controls)
        self.scale_note = QLabel()
        set_role(self.scale_note, tone="secondary")
        self.scale_note.setContentsMargins(SPACE["md"], 0, SPACE["md"], 0)
        self.scale_note.setWordWrap(True)
        layout.addWidget(self.scale_note)

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

    def _on_built(self, scene) -> None:
        if self._run is None:
            return
        self._run = None
        self.scene = scene
        self._ensure_view()
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(scene.times_s) - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._sim_time = float(scene.times_s[0])
        duration = float(scene.times_s[-1] - scene.times_s[0])
        self.speed_combo.setCurrentIndex(_speed_index(duration))
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        self.view_combo.addItem("Whole orbit", -1)
        for n, craft in enumerate(scene.crafts):
            self.view_combo.addItem(f"Follow {craft.name}", n)
        self.view_combo.blockSignals(False)
        self._show_scale_note()
        self._update_time_label(0)
        self._set_controls_enabled(True)
        self.stack.setCurrentWidget(self.web_view)
        self._load_scene()

    def _load_scene(self) -> None:
        payload = json.dumps(scene_payload(self.scene, current_theme()))
        self._call(f"MV.load({payload});", replace=True)

    def _show_scale_note(self) -> None:
        scene = self.scene
        if scene is None:
            return
        if self.view_combo.currentData() in (None, -1):
            factors = [max(1.0, _ORBIT_CRAFT_FRACTION * scene.extent_km / craft.size_km) for craft in scene.crafts]
            text = (f"Spacecraft drawn {min(factors):,.0f}× larger than they are, to be seen at this scale."
                    if max(factors) > 1.0 else "Everything at its true size.")
        else:
            text = "True size, centred on the spacecraft. Body axes: x red, y green, z blue; the Sun and nadir arrows."
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
        self.stack.addWidget(self.web_view)
        self._page_dir = temp_folders.temporary_directory(temp_folders.MISSION_VIEW_PAGE)
        page = Path(self._page_dir.name) / "mission.html"
        page.write_text(self._page_html(), encoding="utf-8")
        self.web_view.loadFinished.connect(self._on_loaded)
        self.web_view.load(QUrl.fromLocalFile(str(page)))

    @staticmethod
    def _page_html() -> str:
        plotly_js = QUrl.fromLocalFile(str(_plotlyjs_path())).toString()
        background = TOKENS["bg.surface"]
        return (f"<!doctype html><html><head><meta charset='utf-8'><script src='{plotly_js}'></script>"
                f"<style>html,body,#{_DIV_ID}{{margin:0;height:100%;width:100%;background:{background};"
                f"overflow:hidden}}</style></head><body><div id='{_DIV_ID}'></div>"
                f"<script>{_PAGE_SCRIPT}</script></body></html>")

    def _on_loaded(self, ok: bool) -> None:
        self._page_ready = bool(ok)
        if self._page_ready and self._pending is not None:
            script, self._pending = self._pending, None
            self.web_view.page().runJavaScript(script)

    def _call(self, script: str, replace: bool = False, callback=None) -> None:
        """Run ``script`` in the page, now or once it has loaded (``replace``:
        a later scene supersedes one not yet shown)."""
        if self.web_view is None:
            return
        if self._page_ready:
            if callback is None:
                self.web_view.page().runJavaScript(script)
            else:
                self.web_view.page().runJavaScript(script, 0, callback)
        elif replace or self._pending is None:
            self._pending = script

    def _on_theme_changed(self, _mode: str) -> None:
        if self.web_view is not None and self.scene is not None:
            self.web_view.page().runJavaScript(f"document.body.style.background = '{TOKENS['bg.surface']}';")
            self._load_scene()

    # -- playback ------------------------------------------------------------------
    def toggle_play(self) -> None:
        if self._timer.isActive():
            self.pause()
        elif self.scene is not None:
            if self.slider.value() >= self.slider.maximum():
                self._sim_time = float(self.scene.times_s[0])
            self._timer.start()
            self.play_button.setText("Pause")
            self.play_button.setToolTip("Pause")

    def pause(self) -> None:
        was_playing = self._timer.isActive()
        self._timer.stop()
        self.play_button.setText("Play")
        self.play_button.setToolTip("Play the run")
        if was_playing:
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
        target = self.view_combo.currentData()
        if target is None:
            return
        self._show_scale_note()
        self._call(f"MV.setView({int(target)});")

    def _update_time_label(self, frame: int) -> None:
        if self.scene is None:
            self.time_label.clear()
            return
        seconds = float(self.scene.times_s[frame])
        moment = (self._epoch + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ") if self._epoch else ""
        self.time_label.setText(f"T+{_elapsed_text(seconds)}  {moment}")

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.play_button, self.slider, self.speed_combo, self.view_combo, self.paths_box):
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
