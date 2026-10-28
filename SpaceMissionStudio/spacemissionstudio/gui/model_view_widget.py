#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

"""The 3D view of a spacecraft's model in the model editor: every visible
part as a shaded mesh in its colour, the body axes at point B and the
center of mass, in the body frame. Drag to turn it, scroll to zoom.

:func:`model_figure` builds the Plotly figure (testable on its own); the
widget loads one page with the local plotly.js (offline, as the Results
tab does) and then updates it in place with ``Plotly.react``, so editing
a part does not reset the camera.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from PySide6.QtCore import QUrl

from . import webengine_setup  # noqa: F401 -- sets the Chromium flags, before QtWebEngine is imported
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .results_widget import _plotlyjs_path
from .theme import TOKENS, on_change
from .theme.palettes import AXIS_COLOURS
from .theme.plotly_template import scene_axis

_DIV_ID = "model-view"
# Body axes at B: x, y, z in the usual red, green, blue (identity, not state).
_AXIS_COLORS = AXIS_COLOURS
_OTHER_PARTS_OPACITY = 0.35  # [-] the parts not selected, while one is


def _rgb(color) -> str:
    r, g, b = (int(round(255 * float(c))) for c in color)
    return f"rgb({r},{g},{b})"


def model_figure(derived, selected: str | None = None) -> go.Figure:
    """The figure for a :class:`~spacemissionstudio.model3d.model.DerivedModel`:
    one ``Mesh3d`` per visible part (named after it), the body axes at B and
    the center of mass. With a part ``selected``, the others are faded."""
    traces = []
    for part in derived.parts:
        if part.mesh is None or not part.visible or len(part.mesh.triangles) == 0:
            continue
        v, t = part.mesh.vertices, part.mesh.triangles
        opacity = 1.0 if selected in (None, part.name) else _OTHER_PARTS_OPACITY
        traces.append(go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=t[:, 0], j=t[:, 1], k=t[:, 2],
                                name=part.name, color=_rgb(part.color), opacity=opacity, flatshading=True,
                                hovertemplate=f"{part.name}<extra></extra>",
                                lighting={"ambient": 0.45, "diffuse": 0.8, "specular": 0.1}))
    box = derived.bounds()
    size = float(np.max(box[1] - box[0])) if box is not None else 1.0  # [m]
    length = 0.6 * max(size, 0.1)  # [m] of the drawn axes
    for axis, (label, color) in enumerate(zip("xyz", _AXIS_COLORS)):
        end = [0.0, 0.0, 0.0]
        end[axis] = length
        traces.append(go.Scatter3d(x=[0.0, end[0]], y=[0.0, end[1]], z=[0.0, end[2]], mode="lines+text",
                                   text=["", f"{label}_B"], textposition="top center", name=f"{label} axis",
                                   line={"color": color, "width": 5}, hoverinfo="skip",
                                   textfont={"color": color}))
    if derived.mass_properties is not None:
        com = derived.mass_properties.center_of_mass_m
        traces.append(go.Scatter3d(x=[com[0]], y=[com[1]], z=[com[2]], mode="markers", name="center of mass",
                                   marker={"symbol": "diamond", "size": 6, "color": TOKENS["text.primary"]},
                                   hovertemplate="center of mass<br>[%{x:.4g}, %{y:.4g}, %{z:.4g}] m<extra></extra>"))
    axis_style = scene_axis(TOKENS)
    layout = go.Layout(
        showlegend=False, margin={"l": 0, "r": 0, "t": 0, "b": 0}, paper_bgcolor=TOKENS["bg.surface"],
        uirevision="model",  # keeps the camera when the data change
        scene={"aspectmode": "data", "xaxis": {**axis_style, "title": "x [m]"},
               "yaxis": {**axis_style, "title": "y [m]"}, "zaxis": {**axis_style, "title": "z [m]"}})
    return go.Figure(data=traces, layout=layout)


class ModelViewWidget(QWidget):
    """A ``QWebEngineView`` showing :func:`model_figure`; call :meth:`show_model`."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        self._ready = False
        self._pending: str | None = None
        self.figure: go.Figure | None = None
        self._page_dir = tempfile.TemporaryDirectory(prefix="spacemissionstudio_model_view_")
        page = Path(self._page_dir.name) / "model.html"
        page.write_text(self._page_html(), encoding="utf-8")
        self.web_view.loadFinished.connect(self._on_loaded)
        self.web_view.load(QUrl.fromLocalFile(str(page)))
        self._derived = None
        self._selected: str | None = None
        on_change(self._on_theme_changed)

    @staticmethod
    def _page_html() -> str:
        plotly_js = QUrl.fromLocalFile(str(_plotlyjs_path())).toString()
        background = TOKENS["bg.surface"]
        return (f"<!doctype html><html><head><meta charset='utf-8'><script src='{plotly_js}'></script>"
                f"<style>html,body,#{_DIV_ID}{{margin:0;height:100%;width:100%;background:{background};"
                f"overflow:hidden}}</style></head><body><div id='{_DIV_ID}'></div><script>"
                f"window.smsShow = function(fig) {{ Plotly.react('{_DIV_ID}', fig.data, fig.layout, "
                "{displaylogo: false, responsive: true}); };</script></body></html>")

    def _on_loaded(self, ok: bool) -> None:
        self._ready = bool(ok)
        if self._ready and self._pending is not None:
            self.web_view.page().runJavaScript(self._pending)
            self._pending = None

    def show_model(self, derived, selected: str | None = None) -> None:
        """Draw ``derived`` (a DerivedModel), fading all but ``selected``."""
        self._derived, self._selected = derived, selected
        self.figure = model_figure(derived, selected)
        script = f"window.smsShow({self.figure.to_json()});"
        if self._ready:
            self.web_view.page().runJavaScript(script)
        else:
            self._pending = script

    def _on_theme_changed(self, _mode: str) -> None:
        """The page's background and the shown model in the new theme."""
        if self._ready:
            self.web_view.page().runJavaScript(
                f"document.body.style.background = '{TOKENS['bg.surface']}';"
                f"document.getElementById('{_DIV_ID}').style.background = '{TOKENS['bg.surface']}';")
        if self._derived is not None:
            self.show_model(self._derived, self._selected)
