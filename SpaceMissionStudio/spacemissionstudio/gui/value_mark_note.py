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
"""A computed or overridden value's note, under its field (the
transparency plan, Phase 5b; schema.scenario.ValueMark).

Hidden while the field has no mark. Otherwise one short line:
"Computed: <source>", "Edited (computed <value>)" with **Give a
reason...**, or "Overridden (computed <value>): <reason>"; its tooltip has
the whole record."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import set_role


class ValueMarkNote(QWidget):
    """Emits :attr:`reason_requested` when **Give a reason...** is pressed."""

    reason_requested = Signal()

    def __init__(self, unit: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._unit = unit
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        column.addLayout(row)
        # What a value other than the computed one changes (engine.value_consequences).
        self.consequence_label = set_role(QLabel(), tone="secondary")
        self.consequence_label.setWordWrap(True)
        column.addWidget(self.consequence_label)
        self.label = set_role(QLabel(), tone="secondary")
        self.label.setWordWrap(True)
        self.reason_button = set_role(QPushButton("Give a reason..."), variant="ghost")
        self.reason_button.setToolTip("Record why this value replaces the computed one: it is then marked "
                                      "overridden in every view and export.")
        self.reason_button.clicked.connect(self.reason_requested)
        row.addWidget(self.label, 1)
        row.addWidget(self.reason_button)
        self.status = ""
        self.show_mark(None)

    def _value(self, value) -> str:
        return f"{value:g} {self._unit}".strip()

    def show_mark(self, status: str | None, mark=None, value_used=None, consequences=()) -> None:
        """``status`` (``schema.scenario.value_mark_status``) of ``mark``,
        the field holding ``value_used``, and what that changes
        (``engine.value_consequences``, shown under the status); None
        hides the note."""
        self.status = status or ""
        if status is None or mark is None:
            self.setVisible(False)
            self.label.setText("")
            self.setToolTip("")
            return
        computed = self._value(mark.value)
        if status == "computed":
            text = f"Computed: {mark.source}"
        elif status == "edited":
            text = f"Edited (computed {computed})"
        else:
            text = f"Overridden (computed {computed}): {mark.reason}"
        changes = list(consequences) if status != "computed" else []
        self.consequence_label.setText("\n".join(changes))
        self.consequence_label.setVisible(bool(changes))
        lines = [f"Computed value: {computed}", f"Source: {mark.source}"]
        if value_used is not None:
            lines.append(f"Value used: {self._value(value_used)}")
        if mark.reason:
            lines.append(f"Reason: {mark.reason}")
        lines += [f"Changes: {line}" for line in changes]
        if mark.author or mark.time_utc:
            lines.append("Marked " + " ".join(part for part in (f"by {mark.author}" if mark.author else "",
                                                                  mark.time_utc) if part))
        self.label.setText(text)
        self.setToolTip("\n".join(lines))
        self.label.setAccessibleDescription(self.toolTip())
        self.reason_button.setVisible(status == "edited")
        self.setVisible(True)
