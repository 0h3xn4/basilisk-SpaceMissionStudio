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

"""CCSDS orbit data messages in the GUI (CCSDS 502.0-B-3, KVN; the
files are :mod:`spacemissionstudio.ccsds_files`'s, as on the command line):

* :class:`CcsdsCheckDialog`: Tools › Check a CCSDS File... shows whether an
  OPM, OMM or OEM conforms, each issue with its line and clause
  (``ccsds-validate``);
* :class:`OemOptionsDialog`: the stride and suggested interpolation of
  Results › Plots › Export all... › CCSDS ephemeris (OEM)...
  (``run --oem``);
* :func:`write_initial_states`: Scenario › Export Orbits as CCSDS...
  (``ccsds-export``);
* :data:`FILE_FILTER`, :data:`ORBIT_FILTER`: the file dialogs' filters.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from .data_table import DataTable, Row
from .theme import set_role
from .widgets import ComboBox, SpinBox, make_window

ORBIT_FILTER = "CCSDS orbit messages (*.opm *.omm *.OPM *.OMM *.txt *.kvn);;All files (*)"
FILE_FILTER = "CCSDS orbit data messages (*.opm *.omm *.oem *.OPM *.OMM *.OEM *.txt *.kvn);;All files (*)"
INTERPOLATIONS = (("hermite", "Hermite (degree 7)"), ("lagrange", "Lagrange (degree 7; GMAT reads only this)"))


INTERPOLATION_DEGREE = 7  # [-] the degree the OEMs suggest (ccsds_odm.oem_from_result)


def states_written(recorded: int, stride: int) -> int:
    """How many of ``recorded`` states an OEM with ``stride`` holds: every
    ``stride``-th from the first, and the last."""
    return -(-recorded // stride) + (1 if (recorded - 1) % stride else 0)


def max_stride(recorded: int) -> int:
    """The stride limit: every stride up to it writes at least the
    ``INTERPOLATION_DEGREE + 1`` states the interpolation needs (1 when
    fewer were recorded, and the export then says so)."""
    return max(1, (recorded - 1) // INTERPOLATION_DEGREE)


class OemOptionsDialog(QDialog):
    """How a run's ephemeris is written as OEMs: every ``stride``-th
    recorded state (the last always), and the interpolation the file
    suggests to the tool that reads it."""

    def __init__(self, recorded_states: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Export the ephemeris as CCSDS OEM")
        layout = QVBoxLayout(self)
        intro = QLabel("One OEM per spacecraft, in EME2000 (SPICE J2000) around the central body, with UTC epochs: "
                       "the states the run recorded.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.stride_box = SpinBox()
        self.stride_box.setRange(1, 1_000_000)
        self.stride_box.setValue(1)
        self.stride_box.setToolTip("1 writes every recorded state; N writes every Nth and the last one.")
        form.addRow("Write every Nth state", self.stride_box)
        self.interpolation_combo = ComboBox()
        for key, label in INTERPOLATIONS:
            self.interpolation_combo.addItem(label, key)
        self.interpolation_combo.setToolTip("The interpolation the OEM suggests to the tool that reads it. GMAT "
                                            "reads only Lagrange.")
        form.addRow("Suggested interpolation", self.interpolation_combo)
        layout.addLayout(form)
        self.count_label = set_role(QLabel(""), tone="secondary")
        self.count_label.setWordWrap(True)
        layout.addWidget(self.count_label)
        self._recorded = recorded_states
        if recorded_states > 0:  # a degree-7 interpolation needs 8 states (CCSDS 502.0-B-3 5.2.4.7)
            self.stride_box.setMaximum(max_stride(recorded_states))
        self.stride_box.valueChanged.connect(self._show_count)
        self._show_count()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Choose folder...")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _show_count(self) -> None:
        if self._recorded <= 0:
            self.count_label.setText("")
            return
        self.count_label.setText(f"{states_written(self._recorded, self.stride())} of the {self._recorded} recorded "
                                 "states per spacecraft (the interpolation needs at least "
                                 f"{INTERPOLATION_DEGREE + 1}).")

    def stride(self) -> int:
        """The stride, within the box's range (a value set from code
        outside it is kept by the box, not used here)."""
        return min(max(1, int(self.stride_box.value())), self.stride_box.maximum())

    def interpolation(self) -> str:
        return self.interpolation_combo.currentData()


def check_file(path) -> tuple[str, list]:
    """``(kind, issues)`` of the message at ``path``: its kind ("OPM",
    "OMM", "OEM" or "" when it cannot be read as one) and every conformance
    issue (``ccsds_odm.Issue``). Raises OSError when the file cannot be
    read."""
    from .. import ccsds_files
    from ..engine import ccsds_odm

    text = ccsds_files.read_message(path)
    try:
        kind = ccsds_odm.read(text).kind
    except ccsds_odm.OdmError:
        kind = ""
    return kind, ccsds_odm.validate(text)


def verdict(kind: str, issues: list) -> str:
    """One line: whether the message conforms, with its counts."""
    errors = sum(1 for issue in issues if issue.level == "error")
    warnings = len(issues) - errors
    what = f"This {kind}" if kind else "This file"
    if errors:
        text = f"{what} does not conform to CCSDS 502.0-B-3: {errors} error(s)"
    else:
        text = f"{what} conforms to CCSDS 502.0-B-3"
    return text + (f", {warnings} warning(s)." if warnings else ".")


class CcsdsCheckDialog(QDialog):
    """A CCSDS file checked against CCSDS 502.0-B-3, as ``ccsds-validate``
    does: the verdict, then each issue with its level, line, clause and
    what is wrong. An error is a "shall" or "must" the file breaks; a
    warning a "should". A window of its own (``widgets.show_window``), so
    it can sit beside the file's source."""

    def __init__(self, path, parent: QWidget | None = None):
        super().__init__(parent)
        make_window(self)
        self.setWindowTitle(f"CCSDS check: {Path(path).name}")
        self.resize(820, 420)
        layout = QVBoxLayout(self)
        self.path_label = set_role(QLabel(str(path)), tone="secondary")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        self.verdict_label = QLabel("")
        self.verdict_label.setWordWrap(True)
        layout.addWidget(self.verdict_label)
        self.table = DataTable("No issue: nothing to report.")
        layout.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self.kind, self.issues = "", []
        try:
            self.kind, self.issues = check_file(path)
        except OSError as exc:
            self.verdict_label.setText(f"Could not read the file: {exc.strerror or exc}")
            set_role(self.verdict_label, tone="critical")
            self.table.set_table(("Level", "Line", "Clause", "Issue"), [])
            return
        errors = any(issue.level == "error" for issue in self.issues)
        self.verdict_label.setText(verdict(self.kind, self.issues))
        if errors or self.issues:
            set_role(self.verdict_label, tone="critical" if errors else "caution")
        rows = [Row((issue.level, str(issue.line) if issue.line else "-", issue.clause, issue.message),
                    keys=(issue.level, issue.line, issue.clause, issue.message)) for issue in self.issues]
        self.table.set_table(("Level", "Line", "Clause", "Issue"), rows, numeric=(1,), stretch=3)


def write_initial_states(scenario, folder) -> list[Path]:
    """Each spacecraft's starting state as an OPM (an OMM for a TLE) in
    ``folder``, as ``ccsds-export`` writes them; returns the files. Raises
    ImportError without Basilisk (an OPM's state is the run's), OSError."""
    from .. import ccsds_files
    from ..engine.results import output_path

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in ccsds_files.initial_state_messages(scenario):
        path = output_path(folder, name)
        path.write_text(text, encoding="ascii")
        written.append(path)
    return written
