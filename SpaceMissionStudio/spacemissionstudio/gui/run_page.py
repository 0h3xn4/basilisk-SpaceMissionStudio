#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""Run › Run (UI overhaul M5b): what the next run uses, for the mode
chosen, on one page instead of menus and dialogs.

- Single: Live plot; Show in 3D View while running, and its pace
  (remembered per user).
- Monte Carlo: the archive folder, remembered per scenario.
- SIL: the spacecraft whose flight software runs, and the run's options
  (the SIL dialog's form, embedded).

:class:`RunModeControl` is the mode as a segmented control (the Run
area's header). The main window owns the run; this page only holds the
choices it reads.
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from ..engine.live_view import PACING
from .page_tree import embed_dialog
from .theme import CONTENT_MAX_WIDTH_PX, set_role
from .widgets import ComboBox

MODES = (("single", "Single"), ("monte_carlo", "Monte Carlo"), ("sil", "SIL"))
_LIVE_VIEW_KEY = "run/live_3d"  # QSettings: Show in 3D View while running
_LIVE_PACING_KEY = "run/live_3d_pacing"  # QSettings: its pace, simulated seconds per real second (0: as fast as possible)


def _settings() -> QSettings:
    return QSettings(str(Path.home() / ".spacemissionstudio" / "settings.ini"), QSettings.Format.IniFormat)


class RunModeControl(QFrame):
    """Single · Monte Carlo · SIL, a segmented control (as the orbit type's,
    U-14). ``chosen`` carries the mode clicked."""

    chosen = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
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
    """The options of the mode shown. ``archive_changed`` carries the
    Monte Carlo archive folder typed or chosen."""

    archive_changed = Signal(str)
    pacing_changed = Signal(float)  # the live 3D View's pace, changed (also during a run)
    enable_monte_carlo = Signal()  # Enable Monte Carlo, from the note shown while it is off (audit G5)

    def __init__(self, parent: QWidget | None = None) -> None:
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
        layout.addStretch(1)
        self.pages = {}
        self._build_single()
        self._build_monte_carlo()
        self._build_sil()
        self.sil_form = None
        self._sil_names: list[str] = []
        self._sil_folder: Callable[[str], Path | None] = lambda _name: None
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
        settings = _settings()
        self.live_view_check = QCheckBox("Show in 3D View while running")
        self.live_view_check.setToolTip("Results › 3D View opens and shows the run as it is computed: the "
                                        "spacecraft, its path and the Earth, with a LIVE badge. Also for Mission "
                                        "Sequences and long runs; not in SIL mode. Remembered.")
        self.live_view_check.setChecked(str(settings.value(_LIVE_VIEW_KEY, "false")).lower() == "true")
        layout.addWidget(self.live_view_check)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.pacing_label = QLabel("Pace")
        row.addWidget(self.pacing_label)
        self.pacing_combo = ComboBox()
        self.pacing_combo.setToolTip("How fast the run goes: as fast as the computer can, or held to a multiple "
                                     "of real time so it can be watched. Changes take effect at once, also "
                                     "during a run. Remembered.")
        for text, factor in PACING:
            self.pacing_combo.addItem(text, factor)
        try:
            saved = float(settings.value(_LIVE_PACING_KEY, 0.0))
        except (TypeError, ValueError):
            saved = 0.0
        self.pacing_combo.setCurrentIndex(max(0, self.pacing_combo.findData(saved)))
        self.pacing_label.setBuddy(self.pacing_combo)
        row.addWidget(self.pacing_combo)
        row.addStretch(1)
        layout.addLayout(row)
        self.live_view_check.toggled.connect(self._on_live_view)
        self.pacing_combo.currentIndexChanged.connect(self._on_pacing)
        self._on_live_view(self.live_view_check.isChecked(), save=False)
        self.stack.addWidget(page)
        self.pages["single"] = page

    def _on_live_view(self, on: bool, save: bool = True) -> None:
        self.pacing_label.setEnabled(on)
        self.pacing_combo.setEnabled(on)
        if save:
            _settings().setValue(_LIVE_VIEW_KEY, bool(on))

    def _on_pacing(self, _index: int) -> None:
        _settings().setValue(_LIVE_PACING_KEY, self.pacing())
        self.pacing_changed.emit(self.pacing())

    def live_view(self) -> bool:
        """Show in 3D View while running."""
        return self.live_view_check.isChecked()

    def pacing(self) -> float:
        """The pace: simulated seconds per real second (0: as fast as possible)."""
        return float(self.pacing_combo.currentData() or 0.0)

    def _build_monte_carlo(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        # Before the click, not after it: the mode is Monte Carlo but the
        # scenario's Monte Carlo is off (audit G5).
        self.monte_carlo_off = QWidget()
        off_row = QHBoxLayout(self.monte_carlo_off)
        off_row.setContentsMargins(0, 0, 0, 0)
        off_label = set_role(QLabel("Monte Carlo is off for this scenario, so Run has no batch to run."),
                             tone="secondary")
        off_label.setWordWrap(True)
        off_row.addWidget(off_label, 1)
        self.enable_monte_carlo_button = QPushButton("Enable Monte Carlo")
        self.enable_monte_carlo_button.setToolTip("Turns Monte Carlo on and opens Scenario > Monte Carlo, where its "
                                                  "runs and dispersions are set.")
        self.enable_monte_carlo_button.clicked.connect(self.enable_monte_carlo)
        off_row.addWidget(self.enable_monte_carlo_button)
        layout.addWidget(self.monte_carlo_off)
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

    def set_monte_carlo_enabled(self, enabled: bool) -> None:
        """Show the "Monte Carlo is off" note with Enable while it is off."""
        self.monte_carlo_off.setVisible(not enabled)

    def show_mode(self, mode: str) -> None:
        # The stack is as tall as the page shown, not its tallest page.
        for name, page in self.pages.items():
            policy = QSizePolicy.Policy.Preferred if name == mode else QSizePolicy.Policy.Ignored
            page.setSizePolicy(policy, policy)
        self.stack.setCurrentWidget(self.pages[mode])
        self.stack.adjustSize()
        self.mode_label.setText({
            "single": "Run builds the scenario in Basilisk and runs it once.",
            "monte_carlo": "Run runs the scenario's Monte Carlo batch.",
            "sil": "Run runs the scenario with a spacecraft's flight software as a program in the loop.",
        }[mode])

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
    def set_sil_spacecraft(self, names: list[str], folder_of: Callable[[str], Path | None]) -> None:
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
