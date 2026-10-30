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
"""Scenario › Assumptions (transparency plan, Phase 3d): the project
configuration file the scenario names, and every parameter of the registry
with the value in effect, its unit and source, the changed ones in bold.

Selecting a parameter shows what it controls, why, and the values it may
take. A value set here is checked against those, then written into the
configuration file: only that parameter's line changes, so the file's
comments stay (``config.files.set_value``). Reset comments the line out
again. The scenario itself stores only the file's name, as it did; the page
is the form field the JSON view was until now.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QWidget)

from ..config import files, registry
from ..config.registry import ConfigError, Configuration
from .data_table import DataTable, Row
from .theme import SPACE, set_role

_HEADERS = ("Parameter", "Value", "Default", "Unit", "Source")
_VALUE = 1


class AssumptionsPage(QWidget):
    """``config_file_changed(str | None)``: the scenario names another file
    (or none); ``configuration_edited``: a value was written to the file."""

    config_file_changed = Signal(object)
    configuration_edited = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_file: str | None = None
        self._base_dir_provider = None
        self._configuration: Configuration | None = None
        self._names: list[str | None] = []  # the parameter of each table row; None for an area's heading

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        layout.setSpacing(SPACE["sm"])
        intro = set_role(QLabel(
            "The rules and margins the analyses use. A project configuration file changes them for this "
            "scenario; values it changes are in bold. Every result records the values it used."),
            tone="secondary")
        intro.setWordWrap(True)  # never sets the window's width (the 1280 px check)
        layout.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(QLabel("Configuration file"))
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("None: every value is its default")
        row.addWidget(self.file_edit, 1)
        self.choose_button = QPushButton("Choose...")
        self.choose_button.setToolTip("Name an existing configuration file (YAML) for this scenario")
        self.choose_button.clicked.connect(self._on_choose)
        row.addWidget(self.choose_button)
        self.new_button = QPushButton("New...")
        self.new_button.setToolTip("Write a new configuration file listing every parameter, commented out, and "
                                   "name it for this scenario")
        self.new_button.clicked.connect(self._on_new)
        row.addWidget(self.new_button)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setToolTip("Name no configuration file: every value back to its default (the file "
                                      "itself is kept)")
        self.remove_button.clicked.connect(lambda: self._name_file(None))
        row.addWidget(self.remove_button)
        layout.addLayout(row)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.changed_only = QCheckBox("Changed values only")
        self.changed_only.toggled.connect(self._apply_filter)
        layout.addWidget(self.changed_only)
        self.table = DataTable("No parameters.")
        self.table.set_single_pick()
        self.table.row_chosen.connect(self._on_row_chosen)
        layout.addWidget(self.table, 1)

        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Value"))
        self.value_edit = QLineEdit()
        self.value_edit.returnPressed.connect(self._on_set)
        edit_row.addWidget(self.value_edit, 1)
        self.set_button = QPushButton("Set")
        self.set_button.clicked.connect(self._on_set)
        edit_row.addWidget(self.set_button)
        self.reset_button = QPushButton("Reset to default")
        self.reset_button.clicked.connect(self._on_reset)
        edit_row.addWidget(self.reset_button)
        layout.addLayout(edit_row)
        self.edit_error = set_role(QLabel(), tone="critical")
        self.edit_error.setWordWrap(True)
        layout.addWidget(self.edit_error)
        self._selected: str | None = None
        self.refresh()

    # -- the scenario's file ------------------------------------------------------------------
    def set_base_dir_provider(self, provider) -> None:
        """``provider()``: the scenario file's folder, or None while unsaved."""
        self._base_dir_provider = provider

    def set_config_file(self, config_file: str | None) -> None:
        """The scenario's ``config_file`` (as loaded); no signal."""
        self._config_file = config_file or None
        self.refresh()

    @property
    def config_file(self) -> str | None:
        return self._config_file

    def _base_dir(self) -> Path | None:
        base = self._base_dir_provider() if self._base_dir_provider is not None else None
        return Path(base) if base else None

    def file_path(self) -> Path | None:
        """The configuration file named, resolved (None when there is none,
        or it is relative and the scenario is not saved yet)."""
        if not self._config_file:
            return None
        if self._base_dir() is None and not Path(self._config_file).expanduser().is_absolute():
            return None
        return files.resolve_path(self._config_file, self._base_dir())

    def _name_file(self, path: Path | None) -> None:
        """Name ``path`` (relative to the scenario's folder when inside it)."""
        name = None
        if path is not None:
            base = self._base_dir()
            try:
                name = str(path.resolve().relative_to(base.resolve())) if base is not None else str(path.resolve())
            except ValueError:
                name = str(path.resolve())
        if name == self._config_file:
            return
        self._config_file = name
        self.refresh()
        self.config_file_changed.emit(name)

    def _ask_open_path(self) -> str:
        start = str(self._base_dir() or Path.home())
        return QFileDialog.getOpenFileName(self, "Configuration file", start, "YAML (*.yaml *.yml)")[0]

    def _ask_save_path(self) -> str:
        start = str((self._base_dir() or Path.home()) / "project.yaml")
        return QFileDialog.getSaveFileName(self, "New configuration file", start, "YAML (*.yaml *.yml)")[0]

    def _on_choose(self) -> None:
        chosen = self._ask_open_path()
        if chosen:
            self._name_file(Path(chosen))

    def _on_new(self) -> None:
        chosen = self._ask_save_path()
        if not chosen:
            return
        try:
            files.new_file(chosen)
        except ConfigError as exc:
            self.edit_error.setText(str(exc))
            return
        self._name_file(Path(chosen))

    # -- the parameters -----------------------------------------------------------------------
    def refresh(self) -> None:
        """Read the file named again and show every parameter's value in effect."""
        self.file_edit.setText(self._config_file or "")
        self.remove_button.setEnabled(self._config_file is not None)
        self._configuration, error = None, ""
        if self._config_file:
            path = self.file_path()
            if path is None:
                error = (f"{self._config_file} is relative to the scenario file's folder: save the scenario "
                         "first, or choose the file again")
            else:
                try:
                    self._configuration = files.read(path)
                except ConfigError as exc:
                    error = str(exc)
        overrides = self._configuration.overrides if self._configuration is not None else {}
        if error:
            set_role(self.status_label, tone="critical")
            self.status_label.setText(f"{error}. The scenario does not validate until the file is fixed.")
        else:
            set_role(self.status_label, tone="secondary")
            self.status_label.setText(f"{len(overrides)} value(s) changed by the file." if self._config_file
                                      else "No configuration file: every value is its default.")
        rows, self._names, area = [], [], None
        for parameter in registry.parameters():
            if parameter.area != area:
                area = parameter.area
                rows.append(Row((area,), group=True))
                self._names.append(None)
            changed = parameter.name in overrides
            value = overrides.get(parameter.name, parameter.default)
            rows.append(Row((parameter.name, files.format_value(value), files.format_value(parameter.default),
                             parameter.unit, parameter.source),
                            tooltips={0: parameter.controls, 4: parameter.rationale or parameter.source},
                            bold=changed))
            self._names.append(parameter.name)
        self.table.set_table(_HEADERS, rows, stretch=4)
        self._apply_filter()
        self._show_selected()

    def overrides(self) -> dict:
        """The values the file named changes ({} without one)."""
        return dict(self._configuration.overrides) if self._configuration is not None else {}

    def _apply_filter(self) -> None:
        if not self.changed_only.isChecked():
            self.table.set_row_filter(None)
            return
        changed = self.overrides()
        areas = {name.split(".", 1)[0] for name in changed}
        self.table.set_row_filter(lambda row: (self._names[row] in changed) if self._names[row] is not None
                                  else self.table.model.text(row, 0) in areas)

    def select(self, name: str) -> None:
        """Select parameter ``name`` (its details and value below the table)."""
        self._selected = name
        self._show_selected()

    def _on_row_chosen(self, row: int) -> None:
        name = self._names[row] if 0 <= row < len(self._names) else None
        if name is not None:
            self.select(name)

    def _show_selected(self) -> None:
        self.edit_error.setText("")
        name = self._selected
        editable = name is not None and self.file_path() is not None and self._configuration is not None
        self.value_edit.setEnabled(name is not None)
        self.set_button.setEnabled(editable)
        self.reset_button.setEnabled(editable and name in self.overrides())
        tip = "" if editable else "Choose or create a configuration file to change a value"
        self.set_button.setToolTip(tip)
        if name is None:
            self.detail_label.setText("Select a parameter to see what it controls and to change it.")
            self.value_edit.clear()
            return
        parameter = registry.parameter(name)
        if parameter.choices is not None:
            limits = "one of " + ", ".join(f"{c:g}" for c in parameter.choices)
        else:
            bounds = [f"at least {parameter.minimum:g}" if parameter.minimum is not None else "",
                      f"at most {parameter.maximum:g}" if parameter.maximum is not None else ""]
            limits = ", ".join(b for b in bounds if b) or "any value"
        rationale = f" {parameter.rationale}" if parameter.rationale else ""
        self.detail_label.setText(f"{name} {parameter.unit}: {parameter.controls} Source: {parameter.source}."
                                  f"{rationale} It may take {limits} ({parameter.kind}).")
        self.value_edit.setText(files.format_value(self.overrides().get(name, parameter.default)))

    def _on_set(self) -> None:
        import yaml

        name, path = self._selected, self.file_path()
        if name is None or path is None or not self.set_button.isEnabled():
            return
        try:
            value = yaml.safe_load(self.value_edit.text())
        except yaml.YAMLError:
            value = self.value_edit.text()
        try:
            files.set_value(path, name, value)
        except ConfigError as exc:
            self.edit_error.setText(str(exc))
            return
        self.refresh()
        self.configuration_edited.emit()

    def _on_reset(self) -> None:
        name, path = self._selected, self.file_path()
        if name is None or path is None:
            return
        try:
            files.reset_value(path, name)
        except ConfigError as exc:
            self.edit_error.setText(str(exc))
            return
        self.refresh()
        self.configuration_edited.emit()
