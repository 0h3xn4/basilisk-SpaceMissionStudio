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
"""The Calculation panel (transparency plan, Phase 4b; the plan's "Explain drawer"): how a computed number
was reached, one click from the number.

A page with computed numbers (the Budget, End of Life, the mission
dashboard's link) emits ``calculation_requested`` with an :class:`Explanation`:
the trace of the number asked about, and the traces of the numbers it is
built from (``engine.trace``). The main window shows it in the Calculation
panel, a dock beside the Inspector that is hidden until asked for. (Explain,
Scenario › Overview, says what a scenario does; this says how a number was
computed.)

The panel shows the result, the equation and its reference, each input
and intermediate with its value, unit and source, and the notes. Each input
takes two lines, so a narrow panel shows its source without scrolling
sideways. An input that is another number of the same explanation (source
``trace: ...``) has an Open button to that number's trace; Back returns. Copy puts the text on the
clipboard, as ``--explain`` prints it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..engine.trace import Quantity, Trace
from .theme import SPACE, mono_font, set_role


@dataclass
class Explanation:
    """The number asked about (``traces[0]``) and the ones it is built from."""

    title: str  # where it was asked from, e.g. "Budget: sat-1"
    traces: list[Trace] = field(default_factory=list)

    def find(self, quantity: str) -> Trace | None:
        return next((trace for trace in self.traces if trace.quantity == quantity), None)


def _value_text(value) -> str:
    if value is None:
        return "-"
    return f"{value:.10g}" if isinstance(value, float) else str(value)


class CalculationPanel(QWidget):
    """See this module's docstring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._explanation: Explanation | None = None
        self._history: list[Trace] = []
        self.value_labels: list[QLabel] = []  # per input and intermediate: "symbol = value unit  what"
        self.source_labels: list[QLabel] = []  # and where it came from
        self.open_buttons: dict[str, QPushButton] = {}  # by the trace each opens
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["md"], SPACE["md"])
        layout.setSpacing(SPACE["sm"])
        self.empty_label = QLabel("Choose Show calculation beside a computed number to see how it was computed: the "
                                  "equation, each input with its unit and source, and the standard it comes from.")
        self.empty_label.setWordWrap(True)
        set_role(self.empty_label, role="empty")
        layout.addWidget(self.empty_label)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(SPACE["sm"])
        self.context_label = QLabel()
        set_role(self.context_label, tone="secondary")
        body.addWidget(self.context_label)
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        set_role(self.result_label, role="strong")
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.result_label)
        self.equation_label = QLabel()
        self.equation_label.setWordWrap(True)
        self.equation_label.setFont(mono_font())
        self.equation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.equation_label)
        self.reference_label = QLabel()
        self.reference_label.setWordWrap(True)
        set_role(self.reference_label, tone="secondary")
        body.addWidget(self.reference_label)
        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        set_role(self.notes_label, tone="secondary")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        quantities = QWidget()
        self._quantities = QVBoxLayout(quantities)
        self._quantities.setContentsMargins(0, 0, 0, 0)
        self._quantities.setSpacing(SPACE["xs"])
        scroll.setWidget(quantities)
        body.addWidget(scroll, 1)
        buttons = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.setToolTip("The number this one was opened from")
        self.back_button.clicked.connect(self.back)
        buttons.addWidget(self.back_button)
        buttons.addStretch(1)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy this explanation as text, as --explain prints it")
        self.copy_button.clicked.connect(self.copy)
        buttons.addWidget(self.copy_button)
        body.addLayout(buttons)
        layout.addWidget(self.body, 1)
        self.body.setVisible(False)

    # -- what it shows ------------------------------------------------------------------------
    def explain(self, explanation: Explanation) -> None:
        """Show ``explanation``'s first trace; its others are reached from it."""
        self._explanation = explanation
        self._history = []
        if explanation.traces:
            self._show(explanation.traces[0])
        else:
            self.clear()

    def clear(self) -> None:
        self._explanation, self._history = None, []
        self.empty_label.setVisible(True)
        self.body.setVisible(False)

    @property
    def trace(self) -> Trace | None:
        """The trace shown."""
        return self._history[-1] if self._history else None

    def open(self, quantity: str) -> bool:
        """Show the explanation's trace of ``quantity``; False when it has none."""
        trace = self._explanation.find(quantity) if self._explanation is not None else None
        if trace is None:
            return False
        self._show(trace)
        return True

    def back(self) -> None:
        if len(self._history) > 1:
            self._history.pop()
            self._render(self._history[-1])

    def copy(self) -> None:
        if self.trace is not None:
            QApplication.clipboard().setText("\n".join(self.trace.text()))

    def _show(self, trace: Trace) -> None:
        self._history.append(trace)
        self._render(trace)

    def _render(self, trace: Trace) -> None:
        self.empty_label.setVisible(False)
        self.body.setVisible(True)
        self.context_label.setText(self._explanation.title if self._explanation is not None else "")
        self.result_label.setText(f"{trace.quantity}: {trace.symbol} = {_value_text(trace.value)} {trace.unit}")
        self.equation_label.setText(trace.equation)
        self.reference_label.setText(f"From: {trace.reference}")
        self._clear_quantities()
        for heading, quantities in (("Inputs", trace.inputs), ("Intermediates", trace.intermediates)):
            if quantities:
                label = QLabel(heading)
                set_role(label, role="strong")
                self._quantities.addWidget(label)
                for quantity in quantities:
                    self._add_quantity(quantity)
        self._quantities.addWidget(self.notes_label)
        self.notes_label.setText("\n".join(f"Note: {note}" for note in trace.notes))
        self.notes_label.setVisible(bool(trace.notes))
        self._quantities.addStretch(1)
        self.back_button.setEnabled(len(self._history) > 1)

    def _clear_quantities(self) -> None:
        self.value_labels, self.source_labels, self.open_buttons = [], [], {}
        while self._quantities.count():
            item = self._quantities.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self.notes_label:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                _delete_layout(item.layout())

    def _add_quantity(self, quantity: Quantity) -> None:
        """Two lines: the value with its meaning, then its source; an
        Open button when the source is another trace of the explanation."""
        value = QLabel(f"{quantity.symbol} = {_value_text(quantity.value)} {quantity.unit}   {quantity.name}")
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value_labels.append(value)
        self._quantities.addWidget(value)
        source = QLabel(quantity.source or "(source not recorded)")
        source.setWordWrap(True)
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        set_role(source, tone="secondary")
        self.source_labels.append(source)
        target = quantity.source[len("trace: "):] if quantity.source.startswith("trace: ") else None
        if target is None or self._explanation is None or self._explanation.find(target) is None:
            source.setContentsMargins(SPACE["md"], 0, 0, SPACE["xs"])
            self._quantities.addWidget(source)
            return
        row = QHBoxLayout()
        row.setContentsMargins(SPACE["md"], 0, 0, SPACE["xs"])
        row.addWidget(source, 1)
        button = QPushButton("Open")
        set_role(button, variant="ghost")
        button.setToolTip(f"How {target} was computed")
        button.setAccessibleName(f"Open {target}")
        button.clicked.connect(lambda _checked=False, quantity=target: self.open(quantity))
        row.addWidget(button)
        self.open_buttons[target] = button
        self._quantities.addLayout(row)


def _delete_layout(layout) -> None:
    while layout.count():
        widget = layout.takeAt(0).widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
    layout.deleteLater()
