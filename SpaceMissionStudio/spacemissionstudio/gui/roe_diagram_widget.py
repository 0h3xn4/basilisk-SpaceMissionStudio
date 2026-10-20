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

"""RoeDiagramWidget: an ROE formation drawn for the Explain page, for
``engine.scenario_explainer.RoeDiagram``. Three panels at one scale:

- the eccentricity vector ``a·δe`` (it sets the radial motion);
- the inclination vector ``a·δi`` (the cross-track motion);
- the path the follower traces around the chief in the radial/cross-track
  plane over an orbit (first order, ``engine.roe.roe_to_rtn``).

Parallel vectors give an ellipse that keeps clear of the chief at the
centre: the passive safety the closest-approach figure in the legend
measures. Each target has its own colour, in ``SERIES_COLORS`` order.
Drawn with :class:`QPainter`, like ``formation_diagram_widget.py``.
"""

from __future__ import annotations

import math
from typing import List

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..engine.roe import min_radial_normal_separation
from ..engine.scenario_explainer import RoeDiagram
from .theme import PALETTE, SERIES_COLORS, ui_font

_PANEL_MAX = 170  # panel side, px
_TITLE_HEIGHT = 20  # px
_LEGEND_LINE = 18  # px
_GAP = 24  # px between panels
_PATH_STEPS = 72  # points on the relative-motion path


def target_summary(roe_m: List[float]) -> str:
    """A target in words: where the follower's centre of motion sits and
    the closest radial/cross-track approach."""
    dl = roe_m[1]
    margin = min_radial_normal_separation(roe_m, 1.0)  # [m] the ROE are in metres
    place = f"{abs(dl):.0f} m {'ahead' if dl >= 0 else 'behind'}"
    safety = f"closest {margin:.0f} m" if margin > 1.0 else "orbits cross"
    return f"{place}, {safety}"


class RoeDiagramWidget(QWidget):
    """``set_diagram(Optional[RoeDiagram])``; ``None`` collapses it to
    zero height, as ``FormationDiagramWidget``."""

    def __init__(self, diagram: RoeDiagram | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_diagram(diagram)

    def set_diagram(self, diagram: RoeDiagram | None) -> None:
        self._diagram = diagram
        self.setFixedHeight(self._height())
        self.setToolTip(self._tooltip())
        self.update()

    def _shown_targets(self):
        return self._diagram.targets[:len(SERIES_COLORS)] if self._diagram is not None else []

    def _height(self) -> int:
        if self._diagram is None:
            return 0
        legend_lines = len(self._shown_targets()) + (1 if len(self._diagram.targets) > len(SERIES_COLORS) else 0)
        return 8 + _TITLE_HEIGHT + _PANEL_MAX + 10 + _LEGEND_LINE * (1 + legend_lines)

    def _tooltip(self) -> str:
        if self._diagram is None:
            return ""
        lines = [f"{self._diagram.follower_name} around {self._diagram.chief_name}:"]
        for start_day, roe_m in self._diagram.targets:
            lines.append(f"day {start_day:g}: a·δe ({roe_m[2]:g}, {roe_m[3]:g}) m, a·δi ({roe_m[4]:g}, "
                         f"{roe_m[5]:g}) m; {target_summary(roe_m)}")
        return "\n".join(lines)

    def sizeHint(self) -> QSize:
        return QSize(3 * _PANEL_MAX + 2 * _GAP + 32, self._height())

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt override
        diagram = self._diagram
        if diagram is None or not diagram.targets:
            return
        side = min(_PANEL_MAX, (self.width() - 2 * _GAP - 16) / 3.0)
        if side <= 20:
            return
        targets = self._shown_targets()
        extent = max(max(abs(roe_m[0]) + math.hypot(roe_m[2], roe_m[3]), math.hypot(roe_m[4], roe_m[5]))
                     for _, roe_m in targets)
        scale = 0.4 * side / (extent if extent > 0 else 1.0)  # px per metre; vectors fill 80 % of a panel

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        title_font = ui_font("body", "semibold")
        small = ui_font("caption")
        top = 8 + _TITLE_HEIGHT
        panels = [QRectF(8 + k * (side + _GAP), top, side, side) for k in range(3)]
        titles = ("Eccentricity vector a·δe", "Inclination vector a·δi", "Path around the chief")
        axes = (("a·δex", "a·δey"), ("a·δix", "a·δiy"), ("cross-track", "radial"))
        for panel, title, (x_label, y_label) in zip(panels, titles, axes):
            painter.setPen(QColor(PALETTE["text"]))
            painter.setFont(title_font)
            painter.drawText(QRectF(panel.left(), 4, panel.width() + _GAP, _TITLE_HEIGHT),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
            axis_pen = QPen(QColor(PALETTE["border"]))
            axis_pen.setWidthF(1.0)
            painter.setPen(axis_pen)
            painter.drawRect(panel)
            painter.drawLine(QPointF(panel.left(), panel.center().y()), QPointF(panel.right(), panel.center().y()))
            painter.drawLine(QPointF(panel.center().x(), panel.top()), QPointF(panel.center().x(), panel.bottom()))
            painter.setFont(small)
            painter.setPen(QColor(PALETTE["text_muted"]))
            painter.drawText(QRectF(panel.right() - 82, panel.bottom() - 16, 78, 14),
                             Qt.AlignmentFlag.AlignRight, x_label + " →")
            painter.drawText(QRectF(panel.left() + 4, panel.top() + 2, 80, 14),
                             Qt.AlignmentFlag.AlignLeft, y_label + " ↑")

        for index, (_start_day, roe_m) in enumerate(targets):
            color = QColor(SERIES_COLORS[index])
            pen = QPen(color)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(color)
            self._arrow(painter, panels[0].center(), roe_m[2] * scale, roe_m[3] * scale)
            self._arrow(painter, panels[1].center(), roe_m[4] * scale, roe_m[5] * scale)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            centre = panels[2].center()
            for step in range(_PATH_STEPS + 1):
                u = 2.0 * math.pi * step / _PATH_STEPS
                radial = roe_m[0] - roe_m[2] * math.cos(u) - roe_m[3] * math.sin(u)  # [m]
                cross = roe_m[4] * math.sin(u) - roe_m[5] * math.cos(u)  # [m]
                point = QPointF(centre.x() + cross * scale, centre.y() - radial * scale)
                if step == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            painter.drawPath(path)

        # The chief at the centre of the path panel.
        painter.setPen(QPen(QColor(PALETTE["surface"]), 2.0))
        painter.setBrush(QColor(PALETTE["text_muted"]))
        painter.drawEllipse(panels[2].center(), 5.0, 5.0)

        # Legend: a swatch per target, text in text colours.
        painter.setFont(small)
        y = top + side + 10
        painter.setPen(QColor(PALETTE["text_muted"]))
        painter.drawText(QRectF(8, y, self.width() - 16, _LEGEND_LINE), Qt.AlignmentFlag.AlignLeft,
                         f"{diagram.follower_name} around {diagram.chief_name} (grey dot). One scale for all three: "
                         f"the panel edges are at ±{0.5 * side / scale:.0f} m")
        for index, (start_day, roe_m) in enumerate(targets):
            y += _LEGEND_LINE
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(SERIES_COLORS[index]))
            painter.drawRoundedRect(QRectF(8, y + 3, 12, 10), 2.0, 2.0)
            painter.setPen(QColor(PALETTE["text"]))
            painter.drawText(QRectF(26, y, self.width() - 34, _LEGEND_LINE), Qt.AlignmentFlag.AlignLeft,
                             f"from day {start_day:g}: {target_summary(roe_m)}")
        hidden = len(diagram.targets) - len(targets)
        if hidden > 0:
            y += _LEGEND_LINE
            painter.setPen(QColor(PALETTE["text_muted"]))
            painter.drawText(QRectF(26, y, self.width() - 34, _LEGEND_LINE), Qt.AlignmentFlag.AlignLeft,
                             f"and {hidden} later target{'s' if hidden > 1 else ''} (hover for all)")
        painter.end()

    @staticmethod
    def _arrow(painter: QPainter, origin: QPointF, dx_px: float, dy_px: float) -> None:
        """An arrow from ``origin`` to (dx, dy), y up; a dot for a zero vector."""
        tip = QPointF(origin.x() + dx_px, origin.y() - dy_px)
        length = math.hypot(dx_px, dy_px)
        if length < 1.0:
            painter.drawEllipse(origin, 3.0, 3.0)
            return
        painter.drawLine(origin, tip)
        ux, uy = (tip.x() - origin.x()) / length, (tip.y() - origin.y()) / length
        head = min(8.0, 0.5 * length)  # px
        left = QPointF(tip.x() - head * ux - 0.5 * head * uy, tip.y() - head * uy + 0.5 * head * ux)
        right = QPointF(tip.x() - head * ux + 0.5 * head * uy, tip.y() - head * uy - 0.5 * head * ux)
        painter.drawPolygon(QPolygonF([tip, left, right]))
