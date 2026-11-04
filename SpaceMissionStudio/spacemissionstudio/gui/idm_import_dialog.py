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
"""The 3D model editor's **Import IDM-CIC model...** dialog: choose a
``.idm`` file (IDM-CIC is (c) CNES), the configuration, an optional
stowed configuration and the body element, and see what the import will
do before it is applied. The file is read and the import planned in a
worker thread (``spacemissionstudio.idm``, ``idm_import.plan``); the
editor merges the plan into its model (``idm_import.merge``)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from .theme import set_role
from .widgets import ComboBox

CREDIT = ("Reads IDM-CIC models (IDM-CIC is © CNES) with SpaceMissionStudio's own reader. SpaceMissionStudio "
          "is not affiliated with or endorsed by CNES.")
_DEFAULT = ""  # the combo data for "the default values" / "chosen" / "none"


class _Worker(QThread):
    """Reads the file (when no model is given) and plans the import."""

    finished_ok = Signal(object, object)  # model, plan
    failed = Signal(str)

    def __init__(self, path, model, options: dict, parent=None):
        super().__init__(parent)
        self._path, self._model, self._options = path, model, options

    def run(self) -> None:
        from .. import idm, idm_import

        try:
            model = self._model or idm.load(self._path)
            self.finished_ok.emit(model, idm_import.plan(model, **self._options))
        except idm.IdmError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 -- shown in the dialog
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class IdmImportDialog(QDialog):
    """See the module docstring. :meth:`plan` is the accepted plan."""

    def __init__(self, path=None, parent: QWidget | None = None, start_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Import IDM-CIC model")
        self.resize(760, 560)
        self._start_dir = Path(start_dir) if start_dir else None
        self._path: Path | None = None
        self._model = None
        self._plan = None
        self._worker: _Worker | None = None
        self._again = False
        layout = QVBoxLayout(self)
        self.credit = set_role(QLabel(CREDIT), tone="secondary")
        self.credit.setWordWrap(True)
        layout.addWidget(self.credit)
        form = QFormLayout()
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Choose an .idm file")
        row.addWidget(self.path_edit, 1)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_browse)
        row.addWidget(browse)
        form.addRow("Model file", row)
        self.configuration_combo = ComboBox()
        self.configuration_combo.setToolTip("The configuration whose articulations, fillings and optional units are "
                                            "imported")
        form.addRow("Configuration", self.configuration_combo)
        self.stowed_combo = ComboBox()
        self.stowed_combo.setToolTip("A second configuration (e.g. the launch one) whose poses become the model's "
                                     "stowed configuration")
        form.addRow("Stowed configuration", self.stowed_combo)
        self.body_combo = ComboBox()
        self.body_combo.setToolTip("The element whose frame becomes the body frame; the elements mounted on it come "
                                   "with it")
        form.addRow("Body element", self.body_combo)
        self.facets_check = QCheckBox("Build drag and solar pressure facets from the imported shapes")
        self.facets_check.setToolTip("Off by default: the file gives no surface coefficients, so the parts keep "
                                     "the default ones")
        form.addRow("", self.facets_check)
        layout.addLayout(form)
        layout.addWidget(QLabel("What the import will do"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.preview, 1)
        self.status = set_role(QLabel(""), tone="caution")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.currentIndexChanged.connect(self._replan)
        self.facets_check.toggled.connect(self._replan)
        self._update_buttons()
        if path is not None:
            self.open_file(path)

    # -- choosing ------------------------------------------------------------------------------------------------

    def _on_browse(self) -> None:
        start = str(self._path.parent if self._path else self._start_dir or Path.home())
        name, _ = QFileDialog.getOpenFileName(self, "Import an IDM-CIC model", start, "IDM-CIC model (*.idm *.IDM)")
        if name:
            self.open_file(name)

    def open_file(self, path) -> None:
        """Read ``path`` and plan its import with the default choices."""
        self._path = Path(path)
        self.path_edit.setText(str(self._path))
        self._model = None
        self._plan = None
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.blockSignals(False)
        self._start({})

    def _options(self) -> dict:
        return {"configuration": self.configuration_combo.currentData() or None,
                "stowed_configuration": self.stowed_combo.currentData() or None,
                "body_element": self.body_combo.currentData() or None,
                "apply_facets": self.facets_check.isChecked()}

    def _replan(self) -> None:
        if self._model is None:
            return
        if self._worker is not None:
            self._again = True
            return
        self._start(self._options())

    def _start(self, options: dict) -> None:
        self._plan = None
        self.preview.setPlainText("Reading the model..." if self._model is None else "Planning the import...")
        self.status.setText("")
        self._worker = _Worker(self._path, self._model, options, self)
        self._worker.finished_ok.connect(self._on_planned)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_worker_done)
        self._update_buttons()
        self._worker.start()

    def _fill_combos(self, model) -> None:
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.blockSignals(True)
        self.configuration_combo.addItem("Default values", _DEFAULT)
        self.stowed_combo.addItem("None", _DEFAULT)
        for c in model.configurations:
            label = f"{c.id} ({c.name})" if c.name != c.id else c.id
            self.configuration_combo.addItem(label, c.id)
            self.stowed_combo.addItem(label, c.id)
        self.body_combo.addItem("Chosen (the heaviest element the others hang on)", _DEFAULT)
        for e in model.elements:
            self.body_combo.addItem(e.name, e.full_id)
        for combo in (self.configuration_combo, self.stowed_combo, self.body_combo):
            combo.blockSignals(False)

    def _on_planned(self, model, plan) -> None:
        if self._model is None:
            self._model = model
            self._fill_combos(model)
        self._plan = plan
        self.preview.setPlainText("\n".join(plan.summary.lines()))

    def _on_failed(self, message: str) -> None:
        self._plan = None
        self.preview.setPlainText("")
        self.status.setText(f"Cannot import: {message}")

    def _on_worker_done(self) -> None:
        if self._worker is not None:
            self._worker.wait()  # "finished" comes just before the thread ends: let it end before it is dropped
        self._worker = None
        if self._again:
            self._again = False
            self._start(self._options())
            return
        self._update_buttons()

    def _update_buttons(self) -> None:
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(self._plan is not None and self._worker is None)

    def _on_accept(self) -> None:
        if self._plan is not None and self._worker is None:
            self.accept()

    # -- result --------------------------------------------------------------------------------------------------

    def plan(self):
        """The import planned for the choices shown (``idm_import.Plan``), or None."""
        return self._plan

    def busy(self) -> bool:
        """Whether the file is being read or the import planned."""
        return self._worker is not None

    def done(self, result: int) -> None:  # noqa: D102 -- a closed dialog must not leave its thread running
        self._finish_worker()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        self._finish_worker()
        super().closeEvent(event)

    def _finish_worker(self) -> None:
        worker = self._worker
        if worker is not None:
            self._again = False
            worker.wait()
