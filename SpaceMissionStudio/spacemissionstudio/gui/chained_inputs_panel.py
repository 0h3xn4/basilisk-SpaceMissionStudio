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
"""What an analysis takes from the last run, shown before it computes
(the transparency plan, Phase 8b, ``engine.chained_inputs``): each value
with its unit, its source in the tooltip, and a caution when the scenario
has changed since the run."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from . import units
from .theme import set_role

_SHOWN_CHANGES = 5  # the changes named in the caution's text; the tooltip has them all


def _value_text(quantity) -> str:
    value, unit = quantity.value, quantity.unit.strip("[]")
    if isinstance(value, str):
        return value
    shown = units.display(unit)
    suffix = units.suffix(unit) if shown is not None else (f" {unit}" if unit and unit != "-" else "")
    return f"{value:,.6g}{suffix}"


class ChainedInputsPanel(QWidget):
    """A heading ("From the end of the last run, 2026-11-03 06:01 UTC"), a
    caution when the scenario changed since, and one row per value."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.heading = set_role(QLabel(""), tone="secondary")
        self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.caution = set_role(QLabel(""), tone="caution")
        self.caution.setWordWrap(True)
        layout.addWidget(self.caution)
        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.form)
        self.rows: dict[str, QLabel] = {}  # quantity name -> its value label
        self.setVisible(False)

    def show_inputs(self, heading: str, quantities, changes=(), error: str = "") -> None:
        """``quantities`` (``engine.trace.Quantity``) under ``heading``;
        ``changes`` (path, as run, now) make the caution; ``error`` stands
        for the values when they cannot be read."""
        while self.form.rowCount():
            self.form.removeRow(0)
        self.rows = {}
        self.heading.setText(heading)
        if error:
            self.caution.setText(error)
        elif changes:
            named = ", ".join(path for path, _then, _now in list(changes)[:_SHOWN_CHANGES])
            more = f" and {len(changes) - _SHOWN_CHANGES} more" if len(changes) > _SHOWN_CHANGES else ""
            self.caution.setText(f"The scenario has changed since that run ({len(changes)} value"
                                 f"{'s' if len(changes) != 1 else ''}: {named}{more}): run it again for its "
                                 "results to be of this scenario.")
            self.caution.setToolTip("\n".join(f"{path}: {then!r} then, {now!r} now" for path, then, now in changes))
        else:
            self.caution.setText("")
            self.caution.setToolTip("")
        self.caution.setVisible(bool(self.caution.text()))
        for quantity in quantities if not error else ():
            label = QLabel(_value_text(quantity))
            label.setToolTip(quantity.source)
            self.form.addRow(quantity.name[:1].upper() + quantity.name[1:], label)
            self.rows[quantity.name] = label
        self.setVisible(True)

    def clear(self) -> None:
        self.setVisible(False)
