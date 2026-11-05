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
"""File > Change History (transparency plan, Phase 7): the change history
beside the open scenario (``spacemissionstudio.history``), newest first,
filtered by spacecraft and by field. Read only: the file is only ever
appended to, by saves."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout,
                               QWidget)

from .. import history
from ..engine.scenario_diff import short
from .data_table import DataTable, Row
from .theme import set_role
from .widgets import make_window

HEADERS = ("Time (UTC)", "Author", "Saved by", "Change", "Field", "Old", "New", "Reason")
_ALL = "All spacecraft"


class ChangeHistoryDialog(QDialog):
    """The history of ``scenario_path``: every change its saves recorded.
    A window of its own (``widgets.show_window``), beside the main window."""

    def __init__(self, scenario_path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        make_window(self)
        self.scenario_path = Path(scenario_path)
        self.setWindowTitle(f"Change history: {self.scenario_path.name}")
        self.resize(1100, 560)  # [px]
        layout = QVBoxLayout(self)
        self.file_label = set_role(QLabel(str(history.history_path(self.scenario_path))), tone="secondary")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        filters = QHBoxLayout()
        self.spacecraft_filter = QComboBox()
        self.spacecraft_filter.setAccessibleName("Spacecraft")
        self.spacecraft_filter.currentIndexChanged.connect(self._show)
        filters.addWidget(self.spacecraft_filter)
        self.field_filter = QLineEdit()
        self.field_filter.setPlaceholderText("Field contains, e.g. dry_mass_kg")
        self.field_filter.setAccessibleName("Field")
        self.field_filter.setClearButtonEnabled(True)
        self.field_filter.textChanged.connect(self._show)
        filters.addWidget(self.field_filter, 1)
        layout.addLayout(filters)
        self.table = DataTable("No change recorded yet: the history starts with the next save.")
        layout.addWidget(self.table, 1)
        self.problems_label = set_role(QLabel(), tone="caution")
        self.problems_label.setWordWrap(True)
        layout.addWidget(self.problems_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.entries: list[dict] = []
        self.reload()

    def reload(self) -> None:
        """Read the file again (a save since may have added to it)."""
        self.entries, problems = history.read(self.scenario_path)
        self.problems_label.setText("Lines that are not changes, skipped (the file keeps them): "
                                    + "; ".join(problems) if problems else "")
        self.problems_label.setVisible(bool(problems))
        names = sorted({name for entry in self.entries
                        if (name := history.spacecraft_of(str(entry.get("path", "")))) is not None})
        chosen = self.spacecraft_filter.currentText()
        self.spacecraft_filter.blockSignals(True)
        self.spacecraft_filter.clear()
        self.spacecraft_filter.addItems([_ALL, *names])
        self.spacecraft_filter.setCurrentIndex(max(0, self.spacecraft_filter.findText(chosen)))
        self.spacecraft_filter.blockSignals(False)
        self._show()

    def shown_entries(self) -> list[dict]:
        """The entries shown, newest first, as the filters leave them."""
        spacecraft = self.spacecraft_filter.currentText()
        return history.newest_first(self.entries, None if spacecraft in ("", _ALL) else spacecraft,
                                    self.field_filter.text())

    def _show(self, *_args) -> None:
        rows = []
        for entry in self.shown_entries():
            old, new = entry.get("old"), entry.get("new")
            cells = (str(entry.get("time_utc", "")).replace("T", " ").rstrip("Z"), str(entry.get("author", "")),
                     str(entry.get("source", "")), str(entry.get("kind", "")),
                     str(entry.get("path", "")) or "(the scenario)", "" if old is None else short(old),
                     "" if new is None else short(new), str(entry.get("reason", "")))
            rows.append(Row(cells, tooltips={5: str(old), 6: str(new)}))
        if not rows and self.entries:
            self.table.clear("No change matches the filters.")
        else:
            self.table.set_table(HEADERS, rows, stretch=4)
