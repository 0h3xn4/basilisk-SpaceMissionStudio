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
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#


"""The spacecraft editor's table of flexible solar arrays
(``schema.scenario.SolarArrayConfig``), one row per array."""

from __future__ import annotations


from PySide6.QtWidgets import QWidget

from ..schema.scenario import SolarArrayConfig
from .data_handling_editor import _TableEditor

# (header, attribute, kind): "text", "number", "vector" ("x, y, z") or "yesno"
_COLUMNS = (
    ("Name", "name", "text"),
    ("Mass [kg]", "mass_kg", "number"),
    ("Span [m]", "span_m", "number"),
    ("Width [m]", "width_m", "number"),
    ("Hinge at [m] (x, y, z)", "hinge_position_b", "vector"),
    ("Extends toward (x, y, z)", "deploy_direction_b", "vector"),
    ("Cell-side normal (x, y, z)", "normal_b", "vector"),
    ("First mode [Hz]", "first_mode_hz", "number"),
    ("Damping ratio", "damping_ratio", "number"),
    ("Initial deflection [deg]", "initial_deflection_deg", "number"),
    ("Initial rate [deg/s]", "initial_rate_deg_s", "number"),
    ("Generates power", "generates_power", "yesno"),
)


class SolarArrayTableWidget(_TableEditor):
    """Flexible solar arrays, one per row. Vectors are body-frame
    ``x, y, z``; "Generates power" is yes or no."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__([header for header, _, _ in _COLUMNS], parent)
        self.table.setToolTip(
            "Each array is a flat panel on a spring-damper hinge at its root. First mode: its first bending "
            "frequency with the spacecraft held fixed, from the array's structural analysis. Mass is part of "
            "the dry mass; the inertia above is the body's without the arrays.")

    def from_list(self, arrays: list[SolarArrayConfig]) -> None:
        self.table.setRowCount(0)
        for array in arrays:
            texts = []
            for _header, attribute, kind in _COLUMNS:
                value = getattr(array, attribute)
                if kind == "vector":
                    texts.append(", ".join(f"{v:g}" for v in value))
                elif kind == "yesno":
                    texts.append("yes" if value else "no")
                elif kind == "number":
                    texts.append(f"{value:g}")
                else:
                    texts.append(value)
            self._append_row(texts)

    def to_list(self) -> list[SolarArrayConfig]:
        """Raises ValueError naming the cell when a value doesn't parse."""
        arrays = []
        for row in range(self.table.rowCount()):
            values = {}
            for column, (header, attribute, kind) in enumerate(_COLUMNS):
                text = self._cell(row, column)
                if kind == "text":
                    values[attribute] = text
                elif kind == "number":
                    values[attribute] = self._number(row, column, "Solar array")
                elif kind == "yesno":
                    if text.lower() not in ("yes", "no"):
                        raise ValueError(f"Solar array row {row + 1}: {header} {text!r} must be yes or no")
                    values[attribute] = text.lower() == "yes"
                else:
                    parts = [p.strip() for p in text.split(",")]
                    try:
                        vector = [float(p) for p in parts]
                    except ValueError:
                        vector = []
                    if len(vector) != 3:
                        raise ValueError(f"Solar array row {row + 1}: {header} {text!r} must be three numbers, "
                                         "x, y, z")
                    values[attribute] = vector
            arrays.append(SolarArrayConfig(**values))
        return arrays

    def _on_add(self) -> None:
        number = self.table.rowCount() + 1
        sign = 1 if number % 2 else -1
        self._append_row([f"wing-{number}", "5", "1.2", "0.6", f"0, {0.4 * sign:g}, 0", f"0, {sign}, 0", "0, 0, 1",
                          "1", "0.01", "0", "0", "yes"])
