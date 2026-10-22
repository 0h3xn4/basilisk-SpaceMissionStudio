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

- the lowest link margin below 0 dB (the margin already includes the
  required Eb/N0): critical, "Link margin below 0 dB";
- the battery's lowest charge at 0: critical, "Battery empty".

The status is an icon and a word as well as a colour.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..engine import run_summary
from .flow_layout import FlowLayout
from .run_history_view import ProvenancePopover, provenance_text
from .theme import CONTENT_MAX_WIDTH_PX, icon, numeric_font, set_role

CARD_WIDTH_PX = 216  # [px] a card, on the 4 px grid: four in a row at 1280 px with the side panel open
_CRITICAL_ICON_PX = 16  # [px]


def card_status(figure: run_summary.Figure) -> Optional[str]:
    """The critical status of ``figure`` (its words), or None: only the
    thresholds a scenario sets colour a card."""
    key = figure.key.rsplit(".", 1)[-1]
    if key == "lowest_link_margin" and figure.value < 0.0:  # [dB]
        return "Link margin below 0 dB"
    if key == "lowest_battery_charge" and figure.value <= 0.0:  # [W*h]
        return "Battery empty"
    return None


class MetricCard(QFrame):
    """One figure: its label, its value with the unit, and its status when
    it has one."""

    def __init__(self, figure: run_summary.Figure, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        set_role(self, role="card")
        self.setFixedWidth(CARD_WIDTH_PX)
        self.figure = figure
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
        self.status = card_status(figure)
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


class _SummaryWorker(QThread):
    """:func:`run_summary.summarize` of one result, off the GUI thread."""

    def __init__(self, result, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.result = result
        self.figures: List[run_summary.Figure] = []

    def run(self) -> None:
        self.figures = run_summary.summarize(self.result)


class ResultsOverview(QWidget):
    """Results › Overview. ``run_requested``: the empty state's Run;
    ``summarized``: the cards of the latest run are shown."""

    run_requested = Signal()
    summarized = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._result = None
        self._title = ""
        self._provenance: Optional[dict] = None
        self._worker: Optional[_SummaryWorker] = None
        self.cards: List[MetricCard] = []
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
    def set_run(self, result, title: str = "", provenance: Optional[dict] = None) -> None:
        """Show ``result``'s figures (None: the empty state); ``title``
        names the run, ``provenance`` is its provenance as a dict."""
        self._result, self._title, self._provenance = result, title, provenance
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

    def _show_cards(self, figures: List[run_summary.Figure]) -> None:
        for card in self.cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self.cards = [MetricCard(figure, self.cards_holder) for figure in figures]
        for card in self.cards:
            self.cards_layout.addWidget(card)
            card.show()
        self.cards_layout.invalidate()

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
                               button.mapToGlobal(QPoint(0, button.height())))
