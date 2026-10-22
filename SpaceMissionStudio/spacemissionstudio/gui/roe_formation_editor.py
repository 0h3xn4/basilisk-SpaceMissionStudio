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

"""The spacecraft editor's table of ROE targets
(``RoeFormationConfig.targets``): one row per target, its start day and
the six relative orbital elements in metres, with a helper that adds a
passively safe formation and the closest radial/cross-track approach of
the selected row."""

from __future__ import annotations

from typing import List

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..engine.roe import min_radial_normal_separation, safe_formation
from ..schema.scenario import RoeTargetConfig
from .data_handling_editor import _TableEditor
from .widgets import PreciseDoubleSpinBox, flow_row

ROE_TARGET_HEADERS = ("Start [day]", "a·δa [m]", "a·δλ [m]", "a·δex [m]", "a·δey [m]", "a·δix [m]", "a·δiy [m]")


def _text(value: float) -> str:
    """A cell's text: every digit a value has, down to a nanometre (so the
    helper's cos(90 deg) reads 0, not 6e-17)."""
    return f"{round(value, 9) + 0.0:.15g}"  # + 0.0 turns -0.0 into 0


def _spin(minimum: float, maximum: float, value: float, suffix: str) -> PreciseDoubleSpinBox:
    box = PreciseDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(1)
    box.setValue(value)
    box.setSuffix(f" {suffix}")
    return box


class RoeTargetTableWidget(_TableEditor):
    """``RoeFormationConfig.targets``, one target per row."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(list(ROE_TARGET_HEADERS), parent)
        self.table.setToolTip(
            "Each row is a formation, held from its start day until the next row's (the first row starts at "
            "day 0). The six numbers are the chief's semi-major axis times the relative orbital elements: "
            "relative semi-major axis, mean longitude (along-track offset, + ahead), eccentricity vector "
            "(radial motion) and inclination vector (cross-track motion).")
        self.remove_button.setText("Remove")

        self.safe_along_m = _spin(-1.0e6, 1.0e6, 0.0, "m along")  # [m]
        self.safe_radial_m = _spin(0.0, 1.0e5, 300.0, "m radial")  # [m]
        self.safe_cross_m = _spin(0.0, 1.0e5, 300.0, "m cross")  # [m]
        self.safe_phase_deg = _spin(-360.0, 360.0, 90.0, "deg")  # [deg]
        # Wraps on a narrow page (M4a: on one line it made the Power page
        # 628 px wide, wider than the page beside the inspector at 1280 px).
        self.layout().addWidget(flow_row(QLabel("Passively safe:"), self.safe_along_m, self.safe_radial_m,
                                         self.safe_cross_m, self.safe_phase_deg))
        self.safe_add_button = QPushButton("Add safe formation")
        self.safe_add_button.setAutoDefault(False)
        self.safe_add_button.setToolTip(
            "Adds a target one day after the last row: the follower centred the given distance along-track from "
            "the chief, circling it on an ellipse of the given radial and cross-track half-sizes, with parallel "
            "eccentricity and inclination vectors. The two spacecraft then never cross in the radial/cross-track "
            "plane, even when the along-track spacing is lost. A phase of 90 deg is the one J2 keeps.")
        self.safe_add_button.clicked.connect(self.add_safe_formation)
        # On a line of its own: beside the four boxes it made the Power tab
        # wider than a 1280 px window (with the app's font).
        add_row = QHBoxLayout()
        add_row.addWidget(self.safe_add_button)
        add_row.addStretch(1)
        self.layout().addLayout(add_row)

        self.margin_label = QLabel("")
        self.margin_label.setWordWrap(True)
        self.layout().addWidget(self.margin_label)
        self.table.itemSelectionChanged.connect(self._show_margin)
        self.table.itemChanged.connect(self._show_margin)

    def from_list(self, targets: List[RoeTargetConfig]) -> None:
        self.table.setRowCount(0)
        for target in targets:
            self._append_row([_text(target.start_day)] + [_text(value) for value in target.roe_m])
        self._show_margin()

    def to_list(self) -> List[RoeTargetConfig]:
        """Raises ValueError naming the cell when a number doesn't parse."""
        return [RoeTargetConfig(start_day=self._number(row, 0, "ROE target"),
                                roe_m=[self._number(row, column, "ROE target") for column in range(1, 7)])
                for row in range(self.table.rowCount())]

    def add_safe_formation(self) -> None:
        """Appends the helper's passively safe formation as a new row."""
        roe_m = safe_formation(self.safe_along_m.value(), self.safe_radial_m.value(), self.safe_cross_m.value(),
                               self.safe_phase_deg.value(), 1.0)
        self._append_row([_text(self._next_start_day())] + [_text(value) for value in roe_m])
        self.table.selectRow(self.table.rowCount() - 1)

    def _next_start_day(self) -> float:
        if not self.table.rowCount():
            return 0.0  # [day]
        try:
            return self._number(self.table.rowCount() - 1, 0, "ROE target") + 1.0  # [day]
        except ValueError:
            return float(self.table.rowCount())  # [day]

    def _on_add(self) -> None:
        self._append_row([_text(self._next_start_day()), "0", "0", "0", "0", "0", "0"])

    def _show_margin(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        row = rows[0] if rows else self.table.rowCount() - 1
        if row < 0:
            self.margin_label.setText("")
            return
        try:
            roe_m = [self._number(row, column, "ROE target") for column in range(1, 7)]
        except ValueError as exc:
            self.margin_label.setText(str(exc))
            return
        margin = min_radial_normal_separation(roe_m, 1.0)  # [m] the ROE are already in metres
        self.margin_label.setText(f"Row {row + 1}: closest radial/cross-track approach {margin:.1f} m"
                                  + ("" if margin > 1.0e-3 else " (the orbits cross: not passively safe)"))
