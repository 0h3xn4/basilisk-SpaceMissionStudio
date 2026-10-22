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

"""Run › Run (UI overhaul M5b): what the next run uses, for the mode
chosen, on one page instead of menus and dialogs.

- Single: Live plot, and the Vizard options (the Vizard dialog's form,
  embedded, applied as it is edited).
- Monte Carlo: the archive folder, remembered per scenario.
- SIL: the spacecraft whose flight software runs, and the run's options
  (the SIL dialog's form, embedded).

:class:`RunModeControl` is the mode as a segmented control (the Run
area's header). The main window owns the run; this page only holds the
choices it reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .page_tree import embed_dialog, watch_edits
from .theme import CONTENT_MAX_WIDTH_PX, set_role
from .widgets import ComboBox

MODES = (("single", "Single"), ("monte_carlo", "Monte Carlo"), ("sil", "SIL"))


class RunModeControl(QFrame):
    """Single · Monte Carlo · SIL, a segmented control (as the orbit type's,
    U-14). ``chosen`` carries the mode clicked."""

    chosen = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentedControl")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for mode, label in MODES:
            button = QPushButton(label)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setProperty("runMode", mode)
            self.group.addButton(button)
            self.buttons[mode] = button
            row.addWidget(button)
        self.buttons["single"].setChecked(True)
        self.group.buttonClicked.connect(lambda button: self.chosen.emit(button.property("runMode")))

    def set_mode(self, mode: str) -> None:
        self.buttons[mode].setChecked(True)


def _section(title: str, layout: QVBoxLayout) -> None:
    layout.addWidget(set_role(QLabel(title), role="section-title"))


class RunPage(QWidget):
    """The options of the mode shown. ``vizard_changed`` carries the
    request the Vizard form now holds (None: Vizard off);
    ``archive_changed`` the Monte Carlo archive folder typed or chosen."""

    vizard_changed = Signal(object)
    archive_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        content.setMaximumWidth(CONTENT_MAX_WIDTH_PX)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        self.mode_label = set_role(QLabel(), tone="secondary")
        self.mode_label.setWordWrap(True)
        layout.addWidget(self.mode_label)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        # Vizard: for a single run and a SIL run (a Monte Carlo batch has none).
        self.vizard_section = QWidget()
        vizard_layout = QVBoxLayout(self.vizard_section)
        vizard_layout.setContentsMargins(0, 16, 0, 0)  # [px] a section's gap (the 4 px grid)
        _section("Vizard", vizard_layout)
        self.vizard_holder = QVBoxLayout()
        vizard_layout.addLayout(self.vizard_holder)
        layout.addWidget(self.vizard_section)
        layout.addStretch(1)
        self.pages = {}
        self._build_single()
        self._build_monte_carlo()
        self._build_sil()
        self.vizard_form = None
        self.sil_form = None
        self._sil_names: List[str] = []
        self._sil_folder: Callable[[str], Optional[Path]] = lambda _name: None
        self.show_mode("single")

    # -- the pages ----------------------------------------------------------------------------
    def _build_single(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        _section("While it runs", layout)
        self.live_plot_check = QCheckBox("Live plot: draw the plots as the run goes")
        self.live_plot_check.setToolTip("The plots follow the run; it takes a little longer.")
        layout.addWidget(self.live_plot_check)
        self.stack.addWidget(page)
        self.pages["single"] = page

    def _build_monte_carlo(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        _section("Archive folder", layout)
        note = set_role(QLabel("Every run of the batch is saved here; the Monte Carlo view of Results opens on it. "
                               "Remembered for this scenario. Its runs and dispersions are on Scenario > Monte "
                               "Carlo."), tone="secondary")
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.archive_edit = QLineEdit()
        self.archive_edit.setPlaceholderText("Empty: Run asks for a folder")
        self.archive_edit.editingFinished.connect(lambda: self.archive_changed.emit(self.archive_dir()))
        self.archive_browse = QPushButton("Browse...")
        self.archive_browse.clicked.connect(self._on_browse_archive)
        row.addWidget(self.archive_edit, 1)
        row.addWidget(self.archive_browse)
        layout.addLayout(row)
        self.stack.addWidget(page)
        self.pages["monte_carlo"] = page

    def _build_sil(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        _section("Flight software in the loop", layout)
        row = QHBoxLayout()
        row.addWidget(QLabel("Spacecraft"))
        self.sil_combo = ComboBox()
        self.sil_combo.setToolTip("The spacecraft whose exported flight software runs as a program in the loop")
        self.sil_combo.currentTextChanged.connect(self._build_sil_form)
        row.addWidget(self.sil_combo, 1)
        layout.addLayout(row)
        self.sil_none_label = set_role(QLabel("No spacecraft's flight software can be exported: Reports > Flight "
                                              "Software says why."), tone="secondary")
        self.sil_none_label.setWordWrap(True)
        layout.addWidget(self.sil_none_label)
        self.sil_holder = QVBoxLayout()
        layout.addLayout(self.sil_holder)
        self.stack.addWidget(page)
        self.pages["sil"] = page

    def show_mode(self, mode: str) -> None:
        # The stack is as tall as the page shown, not its tallest page.
        for name, page in self.pages.items():
            policy = QSizePolicy.Policy.Preferred if name == mode else QSizePolicy.Policy.Ignored
            page.setSizePolicy(policy, policy)
        self.stack.setCurrentWidget(self.pages[mode])
        self.stack.adjustSize()
        self.vizard_section.setVisible(mode != "monte_carlo")
        self.mode_label.setText({
            "single": "Run builds the scenario in Basilisk and runs it once.",
            "monte_carlo": "Run runs the scenario's Monte Carlo batch.",
            "sil": "Run runs the scenario with a spacecraft's flight software as a program in the loop.",
        }[mode])

    # -- Vizard -------------------------------------------------------------------------------
    def set_vizard(self, request) -> None:
        """The Vizard form, showing ``request`` (None: Vizard off)."""
        from .vizard_dialog import VizardDialog

        if self.vizard_form is not None:
            self.vizard_form.setParent(None)
            self.vizard_form.deleteLater()
        form = VizardDialog(current_save_file=getattr(request, "save_file", None),
                            current_live_stream=getattr(request, "live_stream", False),
                            current_camera_target=getattr(request, "camera_target", None),
                            current_show_orbit_lines=getattr(request, "show_orbit_lines", True),
                            current_show_trajectory_trail=getattr(request, "show_trajectory_trail", False),
                            current_show_ground_tracks=getattr(request, "show_ground_tracks", False), parent=self)
        embed_dialog(form)
        form.layout().setContentsMargins(0, 0, 0, 0)  # aligned with the page's other fields
        watch_edits(form, self._on_vizard_edited)
        self.vizard_holder.addWidget(form)
        self.vizard_form = form

    def _on_vizard_edited(self, *_args) -> None:
        if self.vizard_form is not None:
            self.vizard_changed.emit(self.vizard_form.to_request())

    # -- Monte Carlo ----------------------------------------------------------------------------
    def archive_dir(self) -> str:
        return self.archive_edit.text().strip()

    def set_archive_dir(self, folder: str) -> None:
        self.archive_edit.setText(folder or "")

    def _on_browse_archive(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Monte Carlo archive directory", self.archive_dir())
        if chosen:
            self.archive_edit.setText(chosen)
            self.archive_changed.emit(chosen)

    # -- SIL ----------------------------------------------------------------------------------------
    def set_sil_spacecraft(self, names: List[str], folder_of: Callable[[str], Optional[Path]]) -> None:
        """The spacecraft that can run SIL; ``folder_of(name)`` their export folder."""
        self._sil_folder = folder_of
        if names == self._sil_names and self.sil_form is not None:
            return
        self._sil_names = list(names)
        current = self.sil_combo.currentText()
        self.sil_combo.blockSignals(True)
        self.sil_combo.clear()
        self.sil_combo.addItems(names)
        if current in names:
            self.sil_combo.setCurrentText(current)
        self.sil_combo.blockSignals(False)
        self.sil_combo.setVisible(bool(names))
        self.sil_none_label.setVisible(not names)
        self._build_sil_form(self.sil_combo.currentText())

    def _build_sil_form(self, name: str) -> None:
        from .sil_dialog import SilRunDialog

        if self.sil_form is not None:
            self.sil_form.setParent(None)
            self.sil_form.deleteLater()
            self.sil_form = None
        if not name:
            return
        form = SilRunDialog(name, self._sil_folder(name), self)
        embed_dialog(form)
        form.layout().setContentsMargins(0, 0, 0, 0)
        self.sil_holder.addWidget(form)
        self.sil_form = form

    def sil_choice(self):
        """(spacecraft, options) for Run, or (None, why not)."""
        name = self.sil_combo.currentText()
        if not name or self.sil_form is None:
            return None, "SIL needs a spacecraft whose flight software can be exported: see Flight Software"
        if not self.sil_form.run_button.isEnabled():
            return None, "Choose the flight software program and confirm it on Run > Run before a SIL run"
        return name, self.sil_form.to_options()
