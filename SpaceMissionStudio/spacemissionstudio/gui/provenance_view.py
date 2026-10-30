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
"""The provenance view (transparency plan, Phase 4d): everything a run
recorded about what produced it, nothing left out.

The Provenance popover (Results › Overview, Run › History) gives a
summary; its **Show everything recorded** opens this window. It shows the
run's provenance record (``engine.results.RunProvenance`` and the run's
warnings, as ``provenance.json`` holds them) as a tree, in groups:

=================  ====================================================
Group              Keys
=================  ====================================================
Software           the versions, the qualified Basilisk, dependencies
Run                when, the integrator, its step and tolerances, the
                   central body and its GM, the run's warnings
Seeds              the scenario's seed, each model's, and how
Scenario           the file, its SHA-256, the scenario as run's,
                   what loading changed
Data files         each file: path, size, SHA-256
Time scales        the time system
Frames             the frames, the transformations, each series' frame
Configuration      the project configuration, the values used that the
                   file does not give, the devices' parameters
Other              any key not above (a newer record's)
=================  ====================================================

Every value of the record is a row: a nested record is a branch, a list's
items are numbered. A filter keeps the rows whose name or value contains
its text. **Copy as JSON** copies the whole record.

:func:`provenance_rows` gives the rows without Qt, for tests and text.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .theme import SPACE, mono_font, set_role

#: (group, the record's keys in it), in the order shown.
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Software", ("spacemissionstudio_version", "basilisk_version", "qualified_basilisk_version",
                  "basilisk_qualified", "dependency_versions")),
    ("Run", ("run_started_utc", "integrator", "dynamics_task_rate_s", "integrator_relative_tolerance",
             "integrator_absolute_tolerance", "central_body", "central_body_mu_m3_s2", "run_warnings")),
    ("Seeds", ("rng_seed", "rng_seeds", "rng_seed_note")),
    ("Scenario", ("scenario_file", "scenario_file_sha256", "scenario_sha256", "scenario_file_migrations")),
    ("Data files", ("data_files",)),
    ("Time scales", ("time_system",)),
    ("Frames", ("frames", "transformations", "series_frames")),
    ("Configuration", ("configuration", "effective_defaults", "effective_config_note", "device_parameters")),
)
OTHER = "Other"


def value_text(value) -> str:
    """A leaf's value as shown: numbers in full (``repr``), None as "-"."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _leaves(path: tuple[str, ...], value, rows: list) -> None:
    if isinstance(value, dict) and value:
        rows.append((path, None))
        for key, item in value.items():
            _leaves(path + (str(key),), item, rows)
    elif isinstance(value, (list, tuple)) and value:
        rows.append((path, None))
        for index, item in enumerate(value):
            _leaves(path + (f"[{index}]",), item, rows)
    elif isinstance(value, (dict, list, tuple)):
        rows.append((path, "(none)"))
    else:
        rows.append((path, value_text(value)))


def provenance_rows(provenance: dict | None) -> list[tuple[str, tuple[str, ...], str | None]]:
    """``(group, path, value text)`` for every key of ``provenance`` and
    everything nested in it, in the order shown; a branch (a non-empty
    record or list) has the value None."""
    if not provenance:
        return []
    grouped = {key for _group, keys in GROUPS for key in keys}
    rows: list[tuple[str, tuple[str, ...], str | None]] = []
    for group, keys in GROUPS + ((OTHER, tuple(k for k in provenance if k not in grouped)),):
        for key in keys:
            if key in provenance:
                found: list = []
                _leaves((key,), provenance[key], found)
                rows += [(group, path, text) for path, text in found]
    return rows


class ProvenanceDialog(QDialog):
    """See this module's docstring."""

    def __init__(self, title: str, provenance: dict | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = title if title.startswith("Provenance of ") else f"Provenance of {title}"
        self.setWindowTitle(title)
        self.provenance = provenance or {}
        self.resize(760, 560)  # [px]
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE["sm"])
        heading = set_role(QLabel(title), role="section-title")
        layout.addWidget(heading)
        note = set_role(QLabel("Everything the run recorded about what produced it, as provenance.json holds "
                               "it. Numbers are shown in full."), tone="secondary")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter: a name or a value, e.g. sha256, rng, J2000")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(("Item", "Value"))
        self.tree.setUniformRowHeights(True)
        self.tree.setWordWrap(False)
        layout.addWidget(self.tree, 1)
        self.empty_label = set_role(QLabel("No provenance: this run did not record one."), tone="secondary")
        layout.addWidget(self.empty_label)
        buttons = QHBoxLayout()
        self.copy_button = QPushButton("Copy as JSON")
        self.copy_button.setToolTip("Copy the whole record, as provenance.json holds it")
        self.copy_button.clicked.connect(self.copy)
        buttons.addWidget(self.copy_button)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._build()

    def _build(self) -> None:
        rows = provenance_rows(self.provenance)
        self.tree.setVisible(bool(rows))
        self.filter.setEnabled(bool(rows))
        self.copy_button.setEnabled(bool(rows))
        self.empty_label.setVisible(not rows)
        groups: dict[str, QTreeWidgetItem] = {}
        items: dict[tuple[str, ...], QTreeWidgetItem] = {}
        font = mono_font()
        for group, path, text in rows:
            if group not in groups:
                groups[group] = QTreeWidgetItem(self.tree, [group])
                groups[group].setFirstColumnSpanned(True)
            parent = items.get(path[:-1], groups[group])
            item = QTreeWidgetItem(parent, [path[-1], "" if text is None else text])
            item.setFont(1, font)
            item.setToolTip(1, "" if text is None else text)
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            items[path] = item
        self.tree.expandToDepth(0)
        self.tree.resizeColumnToContents(0)

    def rows_shown(self) -> list[tuple[str, ...]]:
        """The paths of the rows the filter leaves (tests)."""
        shown = []

        def walk(item: QTreeWidgetItem) -> None:
            for index in range(item.childCount()):
                child = item.child(index)
                if not child.isHidden():
                    shown.append(child.data(0, Qt.ItemDataRole.UserRole))
                    walk(child)

        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            if not group.isHidden():
                walk(group)
        return shown

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()

        def visit(item: QTreeWidgetItem, ancestor_matches: bool) -> bool:
            matches = ancestor_matches or not needle or needle in item.text(0).lower() \
                or needle in item.text(1).lower()
            child_shown = False
            for index in range(item.childCount()):
                child_shown = visit(item.child(index), matches) or child_shown
            shown = matches or child_shown
            item.setHidden(not shown)
            if needle and child_shown:
                item.setExpanded(True)
            return shown

        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index), False)

    def copy(self) -> None:
        QApplication.clipboard().setText(json.dumps(self.provenance, indent=2, default=str))
