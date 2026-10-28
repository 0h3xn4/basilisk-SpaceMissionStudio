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

"""Run › History (UI overhaul M5a): every run, newest first, as a table.

The runs kept (``gui.run_history``: saved, or of this session) with their
status, mode, start (UTC) and duration, and where they are saved; the
session's failed runs and Monte Carlo batches, which the run store does
not keep, are listed for the session. The duration and the start come
from the run's provenance (``run_started_utc``) and its end: no field is
added to a saved run. A run's provenance opens in a popover; a
double-click shows the run in Results; Ctrl+C copies the selected rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableView, QVBoxLayout, QWidget)

from .theme import TOKENS, icon, mono_font, set_role

HISTORY_COLUMNS = ("Status", "Run", "Scenario", "Mode", "Started (UTC)", "Duration", "Saved")
SORT_ROLE = Qt.ItemDataRole.UserRole + 1
ENTRY_ROLE = Qt.ItemDataRole.UserRole + 2

# status -> (word, icon, ink): an icon and a word, never colour alone (design rule 1).
_STATUS = {
    "done": ("Done", "circle-check", "status.normal.text"),
    "cancelled": ("Cancelled", "circle-minus", "status.standby.text"),
    "failed": ("Failed", "circle-x", "status.critical.text"),
    "partial": ("Done, some failed", "triangle-alert", "status.caution.text"),
}


@dataclass
class HistoryEntry:
    """One row: a run kept, or a failed run or a batch of this session."""

    status: str  # a key of _STATUS
    scenario: str
    number: int | None = None  # "Run 3"; None for what the store does not keep
    mode: str = ""  # "Single", "SIL", "Monte Carlo"; "" when not recorded (a run of an earlier session)
    started_utc: str = ""  # ISO 8601 with Z; "" when not known
    duration_s: float | None = None  # [s]
    saved: str = ""  # "Saved", "Saving...", "This session only"
    provenance: dict | None = None
    detail: str = ""  # a failed run's message, a batch's folder
    record: object = None  # its gui.run_history.RunRecord, when it is one
    order: float = 0.0  # [s] epoch seconds of its end: newest first
    extra: dict[str, str] = field(default_factory=dict)


def utc_text(moment: datetime | None) -> str:
    """``moment`` as ISO 8601 UTC with Z, to the second ("" for None)."""
    if moment is None:
        return ""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime | None:
    """An ISO 8601 time (naive taken as UTC), or None."""
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def duration_text(seconds: float | None) -> str:
    """ "4.2 s", "3 min 05 s", "1 h 02 min" ("" when not known)."""
    if seconds is None or seconds < 0:
        return ""
    if seconds < 60:  # [s]
        return f"{seconds:.1f} s"
    minutes, rest = divmod(int(round(seconds)), 60)
    if minutes < 60:
        return f"{minutes} min {rest:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def run_entry(record, saved: str, mode: str = "", seconds: float | None = None) -> HistoryEntry:
    """The row of a kept run (``gui.run_history.RunRecord``). ``mode`` and
    ``seconds`` when this session knows them; else the duration is its end
    less its provenance's start."""
    provenance = record.saved.provenance if record.saved is not None else None
    result = getattr(record, "_result", None)  # never read back from disk for a row
    if provenance is None and result is not None and getattr(result, "provenance", None) is not None:
        provenance = result.provenance.to_dict()
    started = parse_utc((provenance or {}).get("run_started_utc", ""))
    finished = record.finished.astimezone(UTC)  # naive: local time, as the run store writes it
    if seconds is None and started is not None:
        seconds = (finished - started).total_seconds()
    return HistoryEntry(status="cancelled" if record.cancelled else "done",
                        scenario=str(record.scenario.get("name", "")), number=record.number, mode=mode,
                        started_utc=utc_text(started), duration_s=seconds, saved=saved, provenance=provenance,
                        record=record, order=finished.timestamp())


def provenance_text(provenance: dict | None) -> str:
    """The provenance, one "key: value" a line (data files by name)."""
    if not provenance:
        return "No provenance: this run did not record one."
    lines = []
    for key, value in provenance.items():
        if key == "data_files" and isinstance(value, dict):
            lines.append(f"{key}: {', '.join(sorted(value)) or '-'}")
        elif key == "dependency_versions" and isinstance(value, dict):
            lines.append(f"{key}: " + ", ".join(f"{name} {version}" for name, version in sorted(value.items())))
        elif isinstance(value, (dict, list)):
            lines.append(f"{key}: {len(value)} entries")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


class HistoryModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.entries: list[HistoryEntry] = []

    def set_entries(self, entries: list[HistoryEntry]) -> None:
        self.beginResetModel()
        self.entries = list(entries)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(self.entries)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 -- Qt API name
        return 0 if parent is not None and parent.isValid() else len(HISTORY_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802 -- Qt API name
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return HISTORY_COLUMNS[section]
            if role == Qt.ItemDataRole.TextAlignmentRole and HISTORY_COLUMNS[section] == "Duration":
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def text(self, entry: HistoryEntry, column: int) -> str:
        word = _STATUS[entry.status][0]
        return (word, f"Run {entry.number}" if entry.number is not None else "", entry.scenario, entry.mode or "-",
                entry.started_utc, duration_text(entry.duration_s), entry.saved)[column]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry, column = self.entries[index.row()], index.column()
        _word, icon_name, ink = _STATUS[entry.status]
        name = HISTORY_COLUMNS[column]
        if role == Qt.ItemDataRole.DisplayRole:
            return self.text(entry, column)
        if role == Qt.ItemDataRole.DecorationRole and column == 0:
            return icon(icon_name, ink.rsplit(".", 1)[0])
        if role == Qt.ItemDataRole.ForegroundRole and column == 0:
            return QColor(TOKENS[ink])  # looked up when drawn: it follows a theme change
        if role == Qt.ItemDataRole.FontRole and name in ("Run", "Started (UTC)", "Duration"):
            return mono_font()
        if role == Qt.ItemDataRole.TextAlignmentRole and name == "Duration":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            if entry.detail:
                return entry.detail
            if name == "Mode" and not entry.mode:
                return "Not recorded for a run of an earlier session"
            return "Double-click to show this run in Results" if entry.record is not None else ""
        if role == ENTRY_ROLE:
            return entry
        if role == SORT_ROLE:
            if name == "Duration":
                return (entry.duration_s if entry.duration_s is not None else -1.0, entry.order)
            if name in ("Status", "Scenario", "Mode", "Saved"):
                return (self.text(entry, column).lower(), entry.order)
            return (entry.order, 0)  # Run, Started: by when it ended
        return None


class _SortProxy(QSortFilterProxyModel):
    def lessThan(self, left, right) -> bool:  # noqa: N802 -- Qt API name
        return left.data(SORT_ROLE) < right.data(SORT_ROLE)


class HistoryTable(QTableView):
    """The runs; Ctrl+C copies the selected rows as TSV, with the header."""

    def keyPressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.matches(QKeySequence.StandardKey.Copy):
            QGuiApplication.clipboard().setText(self.selection_tsv())
            return
        super().keyPressEvent(event)

    def selection_tsv(self) -> str:
        model = self.model()
        rows = sorted({index.row() for index in self.selectionModel().selectedIndexes()})
        lines = ["\t".join(HISTORY_COLUMNS)]
        for row in rows:
            lines.append("\t".join(str(model.index(row, column).data() or "") for column in range(len(HISTORY_COLUMNS))))
        return "\n".join(lines)


class ProvenancePopover(QFrame):
    """A run's provenance, in a popup beside the History (design: shadows
    only on floating elements)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        set_role(self, role="card")  # a raised surface with its border
        layout = QVBoxLayout(self)
        self.title = set_role(QLabel(), role="section-title")
        layout.addWidget(self.title)
        self.body = QLabel()
        self.body.setFont(mono_font())
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.setWordWrap(True)
        layout.addWidget(self.body)

    def show_for(self, entry: HistoryEntry, at: QPoint) -> None:
        self.show_text(f"Run {entry.number}" if entry.number is not None else entry.scenario,
                       provenance_text(entry.provenance), at)

    def show_text(self, title: str, text: str, at: QPoint) -> None:
        """``text`` under ``title``, at ``at`` (Results › Overview's too, M6a)."""
        self.title.setText(title)
        self.body.setText(text)
        self.adjustSize()
        self.move(at)
        self.show()


class RunHistoryView(QWidget):
    """Run › History. ``run_requested``: the empty state's Run; ``show_requested``
    carries the RunRecord of a double-clicked row."""

    run_requested = Signal()
    show_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.provenance_button = QPushButton("Provenance")
        self.provenance_button.setToolTip("What produced the selected run: versions, settings, data files")
        self.provenance_button.setEnabled(False)
        self.provenance_button.clicked.connect(self._on_provenance)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy the selected runs, or all of them, as tab-separated text (Ctrl+C)")
        self.copy_button.clicked.connect(self.copy)
        row.addStretch(1)
        row.addWidget(self.provenance_button)
        row.addWidget(self.copy_button)
        layout.addLayout(row)

        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.addStretch(1)
        self.empty_label = set_role(QLabel("No runs yet. Each run is listed here: its status, how long it "
                                           "took and where it is saved."), tone="secondary")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        self.empty_run_button = set_role(QPushButton("Run"), variant="primary")  # the empty state's primary action
        self.empty_run_button.clicked.connect(self.run_requested)
        empty_layout.addWidget(self.empty_run_button, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(1)
        layout.addWidget(self.empty, 1)

        self.model = HistoryModel(self)
        self.proxy = _SortProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = HistoryTable()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(HISTORY_COLUMNS.index("Started (UTC)"), Qt.SortOrder.DescendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for column, name in enumerate(HISTORY_COLUMNS):  # every column its text's width; Scenario takes the rest
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch if name == "Scenario"
                                        else QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        layout.addWidget(self.table, 1)
        self.popover = ProvenancePopover(self)
        self.set_entries([])

    def set_entries(self, entries: list[HistoryEntry]) -> None:
        self.model.set_entries(entries)
        self.table.setVisible(bool(entries))
        self.empty.setVisible(not entries)
        self.copy_button.setEnabled(bool(entries))
        self._on_selection()

    def entries(self) -> list[HistoryEntry]:
        """The rows as shown, top to bottom."""
        return [self.proxy.index(row, 0).data(ENTRY_ROLE) for row in range(self.proxy.rowCount())]

    def selected(self) -> HistoryEntry | None:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].data(ENTRY_ROLE) if rows else None

    def _on_selection(self, *_args) -> None:
        self.provenance_button.setEnabled(self.selected() is not None)

    def _on_provenance(self) -> None:
        entry = self.selected()
        if entry is not None:
            self.popover.show_for(entry, self.provenance_button.mapToGlobal(
                QPoint(0, self.provenance_button.height())))

    def _on_double_clicked(self, index) -> None:
        entry = index.data(ENTRY_ROLE)
        if entry is not None and entry.record is not None:
            self.show_requested.emit(entry.record)

    def copy(self) -> None:
        if not self.table.selectionModel().selectedRows():
            self.table.selectAll()
        QGuiApplication.clipboard().setText(self.table.selection_tsv())
