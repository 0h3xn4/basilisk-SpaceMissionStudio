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

"""Results › Overview (UI overhaul M6a): the shown run's headline figures
as metric cards, and its provenance one click away.

The figures are :func:`engine.run_summary.summarize`'s, as Compare's
summary has them, computed in a worker thread. A card is neutral unless
the scenario sets its threshold (the brief: colour means something):

- the lowest link margin below the required margin,
  ``link.required_margin_db`` as the run had it (0 dB unless its project
  configuration set it; the margin already includes the required Eb/N0):
  critical, "Link margin below <required> dB";
- the battery's lowest charge at or below ``results.battery_critical_fraction``
  of its capacity, as the run had it (0 unless its project configuration
  set it): critical, "Battery empty", or "Battery at or below <x>% of
  capacity". The capacity is the scenario's as run; without it, only an
  empty battery is critical.

The status is an icon and a word as well as a colour.

A card with a calculation trace (``engine.trace``) shows it in the
Calculation panel when clicked, or on Enter or Space when focused:
``calculation_requested`` carries the :class:`gui.calculation_panel.Explanation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..config import registry
from ..engine import run_summary
from .calculation_panel import Explanation
from .flow_layout import FlowLayout
from .run_history_view import ProvenancePopover, provenance_text
from .theme import CONTENT_MAX_WIDTH_PX, icon, numeric_font, set_role

CARD_WIDTH_PX = 216  # [px] a card, on the 4 px grid: four in a row at 1280 px with the side panel open
_CRITICAL_ICON_PX = 16  # [px]


@dataclass(frozen=True)
class CardLimits:
    """The thresholds a run's cards are judged by: its own
    ``link.required_margin_db`` and ``results.battery_critical_fraction``,
    and each spacecraft's battery capacity as run."""

    required_margin_db: float = 0.0  # [dB]
    battery_critical_fraction: float = 0.0  # [-]
    battery_capacity_wh: dict = field(default_factory=dict)  # {spacecraft: [W*h]}

    @classmethod
    def of_run(cls, result, scenario: dict | None = None) -> CardLimits:
        """The limits of ``result`` (its provenance's configuration) and of
        ``scenario``, the scenario as run (``Scenario.to_dict()``)."""
        capacities = {sc.get("name", ""): (sc.get("power") or {}).get("battery_capacity_wh")
                      for sc in (scenario or {}).get("spacecraft", [])}
        return cls(registry.value_of_run("link.required_margin_db", result),
                   registry.value_of_run("results.battery_critical_fraction", result),
                   {name: wh for name, wh in capacities.items() if wh})


def card_status(figure: run_summary.Figure, limits: CardLimits | None = None) -> str | None:
    """The critical status of ``figure`` (its words), or None: only the
    thresholds a scenario sets colour a card (``limits``: the defaults
    when None)."""
    limits = limits or CardLimits()
    spacecraft, _, key = figure.key.rpartition(".")  # a spacecraft's figure: "<spacecraft>.<key>"
    if key == "lowest_link_margin" and figure.value < limits.required_margin_db:  # [dB]
        return f"Link margin below {limits.required_margin_db:g} dB"
    if key == "lowest_battery_charge":
        capacity_wh = limits.battery_capacity_wh.get(spacecraft)  # [W*h]
        if limits.battery_critical_fraction > 0.0 and capacity_wh is not None:
            if figure.value <= limits.battery_critical_fraction * capacity_wh:  # [W*h]
                return f"Battery at or below {limits.battery_critical_fraction * 100.0:g}% of capacity"
        elif figure.value <= 0.0:  # [W*h]
            return "Battery empty"
    return None


class MetricCard(QFrame):
    """One figure: its label, its value with the unit, and its status when
    it has one. ``chosen``: clicked, or Enter or Space while focused, when
    the figure has a trace."""

    chosen = Signal(object)  # the figure

    def __init__(self, figure: run_summary.Figure, parent: QWidget | None = None,
                 limits: CardLimits | None = None) -> None:
        super().__init__(parent)
        set_role(self, role="card")
        self.setFixedWidth(CARD_WIDTH_PX)
        self.figure = figure
        if figure.trace is not None:
            self.setObjectName("metricCard")
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Show how this was computed")
            self.setAccessibleName(f"{figure.label}: {figure.text()} {figure.unit}")
            self.setAccessibleDescription("Press Enter to show how this was computed")
        layout = QVBoxLayout(self)
        layout.setSpacing(4)  # [px]
        self.label = set_role(QLabel(figure.label), tone="secondary")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        row = QHBoxLayout()
        row.setSpacing(4)  # [px]
        self.value = QLabel(figure.text())
        self.value.setFont(numeric_font("page"))
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.value)
        self.unit = set_role(QLabel("" if figure.unit == "-" else figure.unit), tone="secondary")
        row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        layout.addLayout(row)
        self.status = card_status(figure, limits)
        self.status_row = QWidget()
        status_layout = QHBoxLayout(self.status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)  # [px]
        self.status_icon = QLabel()
        self.status_label = set_role(QLabel(self.status or ""), tone="critical")
        if self.status:
            self.status_icon.setPixmap(icon("circle-x", "status.critical").pixmap(_CRITICAL_ICON_PX,
                                                                                   _CRITICAL_ICON_PX))
            set_role(self.value, tone="critical")
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label, 1)
        self.status_row.setVisible(self.status is not None)
        layout.addWidget(self.status_row)

    def mouseReleaseEvent(self, event) -> None:
        if (self.figure.trace is not None and event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.chosen.emit(self.figure)
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if self.figure.trace is not None and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.chosen.emit(self.figure)
            return
        super().keyPressEvent(event)


class _SummaryWorker(QThread):
    """:func:`run_summary.summarize` of one result, off the GUI thread."""

    def __init__(self, result, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result = result
        self.figures: list[run_summary.Figure] = []

    def run(self) -> None:
        self.figures = run_summary.summarize(self.result)


class ResultsOverview(QWidget):
    """Results › Overview. ``run_requested``: the empty state's Run;
    ``summarized``: the cards of the latest run are shown."""

    run_requested = Signal()
    summarized = Signal()
    calculation_requested = Signal(object)  # a gui.calculation_panel.Explanation

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result = None
        self._title = ""
        self._provenance: dict | None = None
        self._scenario: dict | None = None
        self._worker: _SummaryWorker | None = None
        self.cards: list[MetricCard] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.addStretch(1)
        self.empty_label = set_role(QLabel("No run yet. After a run, its headline figures are here: delta-V, "
                                           "propellant, link margin, battery, passes, eclipses."), tone="secondary")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        self.empty_run_button = set_role(QPushButton("Run"), variant="primary")  # the empty state's primary action
        self.empty_run_button.clicked.connect(self.run_requested)
        empty_layout.addWidget(self.empty_run_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)
        self.stack.addWidget(self.empty)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setMaximumWidth(CONTENT_MAX_WIDTH_PX)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        header = QHBoxLayout()
        self.title_label = set_role(QLabel(), role="section-title")
        header.addWidget(self.title_label)
        self.provenance_button = QPushButton("Provenance")
        self.provenance_button.setIcon(icon("info"))
        self.provenance_button.setToolTip("What produced this run: versions, settings, data files")
        self.provenance_button.clicked.connect(self._on_provenance)
        header.addWidget(self.provenance_button)
        header.addStretch(1)
        layout.addLayout(header)
        self.note = set_role(QLabel(), tone="secondary")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.cards_holder = QWidget()
        self.cards_layout = FlowLayout(self.cards_holder, spacing=8)  # [px]
        layout.addWidget(self.cards_holder)
        layout.addStretch(1)
        self.stack.addWidget(scroll)
        self.page = scroll
        self.popover = ProvenancePopover(self)

    # -- the run ------------------------------------------------------------------------------
    def set_run(self, result, title: str = "", provenance: dict | None = None, scenario: dict | None = None) -> None:
        """Show ``result``'s figures (None: the empty state); ``title``
        names the run, ``provenance`` is its provenance as a dict,
        ``scenario`` the scenario as run (``Scenario.to_dict()``), for the
        battery capacities."""
        self._result, self._title, self._provenance, self._scenario = result, title, provenance, scenario
        if result is None:
            self._show_cards([])
            self.stack.setCurrentWidget(self.empty)
            return
        self.title_label.setText(title or "This run")
        self.provenance_button.setEnabled(provenance is not None)
        self.note.setText("Working out the run's figures...")
        self.stack.setCurrentWidget(self.page)
        if self._worker is None:
            self._start(result)

    @property
    def pending(self) -> bool:
        """A run's figures are being worked out."""
        return self._worker is not None

    def _start(self, result) -> None:
        self._worker = _SummaryWorker(result, self)
        self._worker.finished.connect(self._on_summarized)
        self._worker.start()

    def _on_summarized(self) -> None:
        worker, self._worker = self._worker, None
        if worker is None:
            return
        worker.wait()
        worker.deleteLater()
        if worker.result is not self._result:  # another run was shown meanwhile: work its figures out
            if self._result is not None:
                self._start(self._result)
            return
        self._show_cards(worker.figures)
        self.note.setText("" if worker.figures else "This run recorded none of the figures the overview shows.")
        self.note.setVisible(not worker.figures)
        self.summarized.emit()

    def _show_cards(self, figures: list[run_summary.Figure]) -> None:
        for card in self.cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        limits = CardLimits.of_run(self._result, self._scenario)
        self.cards = [MetricCard(figure, self.cards_holder, limits) for figure in figures]
        for card in self.cards:
            card.chosen.connect(self.show_calculation)
            self.cards_layout.addWidget(card)
            card.show()
        self.cards_layout.invalidate()

    def show_calculation(self, figure: run_summary.Figure) -> None:
        """``figure``'s trace, in the Calculation panel."""
        if figure.trace is not None:
            self.calculation_requested.emit(Explanation(f"{self._title or 'This run'}: {figure.label}",
                                                        [figure.trace, *figure.related]))

    def wait_for_worker(self) -> None:
        """Wait for a run's figures still being worked out (closing)."""
        worker = self._worker
        if worker is not None:
            worker.finished.disconnect(self._on_summarized)
            worker.wait()
            self._worker = None

    # -- provenance -----------------------------------------------------------------------------
    def provenance_text(self) -> str:
        return provenance_text(self._provenance)

    def _on_provenance(self) -> None:
        button = self.provenance_button
        self.popover.show_text(f"Provenance of {self._title or 'this run'}", self.provenance_text(),
                               button.mapToGlobal(QPoint(0, button.height())), self._provenance)
