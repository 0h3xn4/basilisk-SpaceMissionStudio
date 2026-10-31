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

"""ScenarioExplainerWidget: renders ``engine.scenario_explainer.explain()``'s
structured output as a KPI-style stat-tile row, per-section colored
badges, and (for 2+ spacecraft) a comparison table -- never prose, never
a raw bullet-point list (both were tried first and explicitly rejected
by a real user). See that module's own docstring for the full design
rationale and the "don't regress this" discipline.

Shown as the Scenario tree's Overview page (UI overhaul M4b), driven by
``ScenarioEditorWidget.changed`` through :meth:`ScenarioExplainerWidget.request`:
250 ms after the last edit, the explanation is computed in a worker
thread and shown when it is still the latest. Does NOT touch or replace
``scenario_editor.py``'s own free-text ``description`` box -- that one is
hand-written, narrative/pedagogical prose for the 20 bundled templates
specifically; this is a terse, ALWAYS-CURRENT fact summary for any
scenario, built fresh from the scenario's actual current fields.
"""

from __future__ import annotations

import copy
import logging

from PySide6.QtCore import QEvent, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..engine.findings import explanation_lines
from ..engine.scenario_explainer import ScenarioExplanation, explain
from ..schema.scenario import Scenario
from .flow_layout import FlowLayout
from .badges import ACCENT, DANGER, MUTED, SUCCESS, WARNING, set_badge
from .formation_diagram_widget import FormationDiagramWidget
from .roe_diagram_widget import RoeDiagramWidget
from .theme import set_role

_LOG = logging.getLogger(__name__)

_FORMATION_SECTION_TITLE = "Formation / orbit maintenance"
# How long after the last edit the explanation is asked for (design rule
# 6: typing-triggered recomputation is debounced).
EXPLAIN_SETTLE_MS = 250  # [ms]

_BADGE_KIND_COLORS = {
    "neutral": MUTED,
    "accent": ACCENT,
    "success": SUCCESS,
    "warning": WARNING,
    "danger": DANGER,
}


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()  # gone now, not only once the event loop gets to the deferred delete
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


def _stat_tile(label: str, value: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("statTile")
    frame.setFrameShape(QFrame.Shape.NoFrame)
    set_role(frame, role="card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 6, 10, 6)
    layout.setSpacing(2)
    value_label = QLabel(value)
    set_role(value_label, role="value")
    value_label.setWordWrap(True)
    label_label = QLabel(label)
    set_role(label_label, role="caption")
    layout.addWidget(value_label)
    layout.addWidget(label_label)
    return frame


def _badge_label(text: str, kind: str) -> QLabel:
    label = QLabel(text)
    set_badge(label, _BADGE_KIND_COLORS.get(kind, MUTED))
    return label


def _badge_button(text: str, kind: str) -> QPushButton:
    """A badge that opens something: the badge's look, a button's focus and
    keyboard use."""
    button = QPushButton(text)
    button.setFlat(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    set_badge(button, _BADGE_KIND_COLORS.get(kind, MUTED))
    return button


class _ExplainWorker(QThread):
    """``explain(scenario)`` off the GUI thread; ``done`` carries the
    request's number and the explanation, or None when it failed (logged)."""

    done = Signal(int, object)

    def __init__(self, number: int, scenario: Scenario, parent: QWidget | None = None):
        super().__init__(parent)
        self.number, self._scenario = number, scenario

    def run(self) -> None:
        try:
            explanation = explain(self._scenario)
        except Exception:  # noqa: BLE001 -- the page shows its placeholder, never a crashed thread
            _LOG.exception("explaining the scenario failed")
            explanation = None
        self.done.emit(self.number, explanation)


class ScenarioExplainerWidget(QWidget):
    """``set_scenario(Optional[Scenario])`` rebuilds the whole display
    from scratch (clear + repopulate -- mirrors
    ``scenario_editor.py``'s own ``_refresh_propagation_summary()``
    pattern), inside a ``QScrollArea`` so it never forces the window
    taller. ``None`` (e.g. the scenario currently fails validation) shows
    a short placeholder instead of crashing.
    """

    model_requested = Signal(str)  # a 3D model badge was clicked: the spacecraft's name
    explained = Signal()  # what request() asked for is shown (its explanation or the placeholder)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        # request(): the latest scenario asked for, its number, the number
        # shown, and the worker computing one (one at a time).
        self._requested: Scenario | None = None
        self._number = self._shown = 0
        self._worker: _ExplainWorker | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(EXPLAIN_SETTLE_MS)
        self._timer.timeout.connect(self._start_worker)
        self.warning_count = 0  # pre-run warnings currently shown (see engine.scenario_checks)
        self.model_buttons: list = []  # the 3D model badges, as buttons
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # Text wraps to the panel's width (the side panel is narrow), never a
        # sideways scroll bar; tiles and badges flow onto further lines.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer_layout.addWidget(scroll)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        scroll.setWidget(content)

        self._placeholder_label = QLabel(
            "The scenario has a problem (see Problems): fix it to see its summary here."
        )
        self._placeholder_label.setWordWrap(True)
        set_role(self._placeholder_label, tone="secondary")
        self._content_layout.addWidget(self._placeholder_label)

        self._headline_label = QLabel()
        set_role(self._headline_label, role="section-title")
        self._headline_label.setWordWrap(True)
        self._content_layout.addWidget(self._headline_label)

        tiles_box = QWidget()
        self._tiles_row = FlowLayout(tiles_box, spacing=8)
        self._content_layout.addWidget(tiles_box)

        self._sections_layout = QVBoxLayout()
        self._sections_layout.setSpacing(10)
        self._content_layout.addLayout(self._sections_layout)

        self._table = QTableWidget()
        self._table.setTabKeyNavigation(False)  # read-only: Tab leaves the table; the arrows move in it (M9)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._table.verticalHeader().setVisible(False)  # the Spacecraft column already names each row
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._table.installEventFilter(self)  # refit the height when the width changes
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Fitted to its rows (below), so it never scrolls vertically.
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content_layout.addWidget(self._table)

        self._content_layout.addStretch(1)

        self.set_scenario(None)

    def _fit_table_height(self) -> None:
        """Fit the table to its rows instead of leaving a tall, mostly
        empty grid -- and, when it is wider than the pane, add room for its
        horizontal scroll bar so the last row isn't cut off."""
        table = self._table
        height = table.horizontalHeader().height() + 2 * table.frameWidth() + 2
        height += sum(table.rowHeight(r) for r in range(table.rowCount()))
        if table.horizontalHeader().length() > table.width() - 2 * table.frameWidth():
            height += table.horizontalScrollBar().sizeHint().height()
        if table.height() != height:
            table.setFixedHeight(height)

    def eventFilter(self, watched, event):  # noqa: N802 -- Qt API name
        if watched is self._table and event.type() == QEvent.Type.Resize and self._table.rowCount():
            self._fit_table_height()
        return super().eventFilter(watched, event)

    def set_scenario(self, scenario: Scenario | None) -> None:
        self.warning_count = 0  # pre-run warnings shown (see engine.scenario_checks)
        if scenario is None:
            self.model_buttons = []
            self._placeholder_label.setVisible(True)
            self._headline_label.setVisible(False)
            _clear_layout(self._tiles_row)
            _clear_layout(self._sections_layout)
            self._table.setVisible(False)
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            return

        self._show_explanation(explain(scenario))

    # -- asked for after an edit, computed in a worker ---------------------------------
    def request(self, scenario: Scenario | None) -> None:
        """Show ``scenario``'s explanation :data:`EXPLAIN_SETTLE_MS` after the
        last request, computed off the GUI thread; an answer a later
        request overtook is dropped. None shows the placeholder at once."""
        self._number += 1
        self._requested = scenario
        if scenario is None:
            self._timer.stop()
            self._shown = self._number
            self.set_scenario(None)
            self.explained.emit()
            return
        self._timer.start()

    @property
    def pending(self) -> bool:
        """A request not yet shown (waiting, or being computed)."""
        return self._shown != self._number

    def _start_worker(self) -> None:
        if self._worker is not None or self._requested is None:
            return  # one at a time: its end starts the latest
        # A copy: the editor's lists hold the same config objects, and an
        # edit replaces them while the worker reads.
        worker = _ExplainWorker(self._number, copy.deepcopy(self._requested), self)
        worker.done.connect(self._on_explained)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_explained(self, number: int, explanation) -> None:
        if number != self._number:
            return  # a later request is waiting or being computed
        self._shown = number
        if explanation is None:
            self.set_scenario(None)
        else:
            self._show_explanation(explanation)
        self.explained.emit()

    def _on_worker_finished(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()
        if self.pending and not self._timer.isActive():
            self._start_worker()  # a request arrived while it ran, and its wait is over

    def wait_for_worker(self, timeout_ms: int = 30000) -> None:
        """Blocks until a running explanation finishes (shutdown, tests)."""
        if self._worker is not None:
            self._worker.wait(timeout_ms)

    def shut_down(self) -> None:
        """No further explanation (the window closes): a waiting request is
        dropped and a running one waited for."""
        self._timer.stop()
        self._requested = None
        self.wait_for_worker()
        if self._worker is not None and self._worker.isFinished():
            # Its finished signal is still queued for the event loop, which
            # a closing window may not run again: let it go now.
            self._on_worker_finished()

    def _show_explanation(self, explanation: ScenarioExplanation) -> None:
        self._placeholder_label.setVisible(False)
        self._headline_label.setVisible(True)
        self._render(explanation)

    def _on_model_badge(self) -> None:
        self.model_requested.emit(self.sender().property("spacecraft"))

    def _render(self, explanation: ScenarioExplanation) -> None:
        self.model_buttons = []
        self.warning_count = sum(len(s.notes) for s in explanation.sections if s.title == "Check before running")
        self._headline_label.setText(explanation.headline)

        _clear_layout(self._tiles_row)
        for tile in explanation.stat_tiles:
            self._tiles_row.addWidget(_stat_tile(tile.label, tile.value))

        _clear_layout(self._sections_layout)
        for section in explanation.sections:
            section_widget = QWidget()
            # Transparent: the theme's base "QWidget" rule otherwise painted
            # each section as a grey band across this tab's white pane.
            section_widget.setObjectName("explainSection")
            section_layout = QVBoxLayout(section_widget)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)

            title_label = QLabel(section.title)
            set_role(title_label, role="heading")
            section_layout.addWidget(title_label)

            if section.badges:
                badges_box = QWidget()
                badges_row = FlowLayout(badges_box, spacing=6)
                for badge in section.badges:
                    if badge.spacecraft:
                        button = _badge_button(badge.label, badge.kind)
                        button.setToolTip(f"Open the 3D model editor for {badge.spacecraft}")
                        button.setProperty("spacecraft", badge.spacecraft)
                        button.clicked.connect(self._on_model_badge)
                        self.model_buttons.append(button)
                        badges_row.addWidget(button)
                    else:
                        badges_row.addWidget(_badge_label(badge.label, badge.kind))
                section_layout.addWidget(badges_box)

            for note in section.notes:
                note_label = QLabel(note)
                note_label.setWordWrap(True)
                set_role(note_label, tone="secondary")
                rule = "\n".join(explanation_lines(note))  # a warning's rule (engine.findings), on hover
                if rule:
                    note_label.setToolTip(rule)
                    note_label.setAccessibleDescription(rule)
                section_layout.addWidget(note_label)

            # The formation-geometry diagram(s) belong right alongside the
            # section whose badges they illustrate -- "Station-keeping"/
            # "Phasing-keeping" badges name the mechanism, the diagram
            # depicts it (per the dataviz skill's own "depict the
            # mechanism, not its name" guidance, and direct user feedback
            # that an earlier badges-only design still lacked "depth of
            # information").
            if section.title == _FORMATION_SECTION_TITLE:
                for diagram in explanation.formation_diagrams:
                    section_layout.addWidget(FormationDiagramWidget(diagram))
                for diagram in explanation.roe_diagrams:
                    section_layout.addWidget(RoeDiagramWidget(diagram))

            self._sections_layout.addWidget(section_widget)

        if explanation.spacecraft_table:
            columns = []
            for row in explanation.spacecraft_table:
                for key in row.facts:
                    if key not in columns:
                        columns.append(key)
            self._table.setVisible(True)
            self._table.setColumnCount(1 + len(columns))
            self._table.setHorizontalHeaderLabels(["Spacecraft"] + columns)
            self._table.setRowCount(len(explanation.spacecraft_table))
            for row_index, row in enumerate(explanation.spacecraft_table):
                self._table.setItem(row_index, 0, QTableWidgetItem(row.name))
                for col_index, column in enumerate(columns, start=1):
                    self._table.setItem(row_index, col_index, QTableWidgetItem(row.facts.get(column, "")))
            self._table.resizeColumnsToContents()
            self._fit_table_height()
        else:
            self._table.setVisible(False)
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
