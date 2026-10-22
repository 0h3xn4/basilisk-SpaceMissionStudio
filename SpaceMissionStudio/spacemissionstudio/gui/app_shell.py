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

"""The app shell's always-visible state (UX/UI Standard, "State is always
visible" and "Target layout"; docs/ux-audit.md U-04, U-06, U-07):

* :class:`TopBar` -- above the work area: the scenario's name, whether it
  has unsaved changes, where it came from (a template, a file or nothing
  yet), the last run, the breadcrumbs, the problem count and the window's
  commands.
* :class:`RunProgressStrip` -- the job in the status bar while a run is
  going (U-19, UI overhaul M2b): what it is doing ("Step 2 of 5: ...",
  "Propagating: day 0.4 of 1"), a progress bar, the time elapsed and an
  estimate of the time left, and **Cancel** (Esc).
* :class:`StatusChip` -- the run state in the status bar (idle, running
  43 %, done, failed, cancelled).
* :class:`StatusBarItems` -- permanent status-bar entries: the problem
  count (clicking it opens the Problems panel), the Basilisk version, the
  reference data (clicking it opens the Reference data dialog), the Earth
  orientation data and the frames runs use. They read local files only,
  never the network.

Colours come from theme.py's ``QLabel#statusChip[state=...]`` and
``QWidget#topBar`` rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QElapsedTimer, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy, QToolButton,
                               QVBoxLayout, QWidget)

from .theme import icon
from .theme.icons import keep_icon

CHIP_STATES = ("idle", "running", "done", "failed", "cancelled")


class StatusChip(QLabel):
    """The run state as a small tag; ``state`` is one of :data:`CHIP_STATES`
    and picks its colours from the theme."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusChip")
        self.set_state("idle", "No run yet")

    @property
    def state(self) -> str:
        return str(self.property("state"))

    def set_state(self, state: str, text: str) -> None:
        if state not in CHIP_STATES:
            raise ValueError(f"unknown status chip state {state!r}")
        self.setProperty("state", state)
        self.setText(text)
        # A changed dynamic property only restyles after a re-polish.
        self.style().unpolish(self)
        self.style().polish(self)


def clock_text(seconds: float) -> str:
    """ "0:07", "12:30", "1:02:05"."""
    seconds = int(max(seconds, 0.0))
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


class ElidedLabel(QLabel):
    """One line that ends in "..." when there is no room for all of it,
    instead of holding the window wider; the whole text is its tooltip."""

    def setText(self, text: str) -> None:  # noqa: N802 -- Qt API name
        super().setText(text)
        self.setToolTip(text)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 -- Qt API name
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event) -> None:  # noqa: N802 -- Qt API name
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        shown = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), shown)


_CANCEL_TIP = "Cancel (Esc): the run stops at its next checkpoint and keeps what it has"


class RunProgressStrip(QFrame):
    """A run in progress, under the top bar: phase, progress, elapsed time,
    the time left, and Cancel. Hidden while no run is going.

    The time left is estimated from the fraction done once there is enough
    to go on (2 % and 3 s); before that, and for a run that reports no
    fraction, it says nothing rather than guess."""

    cancel_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("runProgressStrip")
        # Its own width in the status bar: the entries that elide give way.
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)  # [px]
        layout.setSpacing(8)  # [px]
        # In the status bar beside its other items: the phase gives way first.
        self.phase_label = ElidedLabel()
        self.phase_label.setObjectName("runPhase")
        self.phase_label.setMinimumWidth(80)  # [px] never squeezed out of sight
        self.phase_label.setMaximumWidth(320)  # [px]
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)  # the percentage is in the time label and the status chip
        self.bar.setFixedWidth(72)  # [px]
        self.time_label = QLabel()
        self.time_label.setObjectName("runTime")
        self.cancel_button = QPushButton("Cancel")  # its key, Esc, in the tooltip: the status bar is narrow
        self.cancel_button.clicked.connect(self.cancel_requested)
        layout.addWidget(self.phase_label, 1)
        layout.addWidget(self.bar)
        layout.addWidget(self.time_label)
        layout.addWidget(self.cancel_button)
        self._elapsed = QElapsedTimer()
        self._fraction: Optional[float] = None
        self._timer = QTimer(self)
        self._timer.setInterval(500)  # [ms]
        self._timer.timeout.connect(self.refresh_time)
        self._fitted_width = 0
        self.hide()

    def start(self, phase: str, cancellable: bool = True, cancel_note: str = "") -> None:
        """A run starts: ``cancel_note`` says why it cannot be cancelled."""
        self._elapsed.start()
        self._fraction = None
        self.bar.setRange(0, 0)  # busy until a fraction arrives
        self.phase_label.setText(phase)
        self.cancel_button.setEnabled(cancellable)
        self.cancel_button.setText("Cancel")
        self.cancel_button.setToolTip(_CANCEL_TIP if cancellable else cancel_note)
        self.refresh_time()
        self._timer.start()
        self.show()
        self._fit()

    def set_phase(self, text: str) -> None:
        self.phase_label.setText(text)
        self._fit()

    def set_fraction(self, fraction: float) -> None:
        fraction = min(max(float(fraction), 0.0), 1.0)
        self._fraction = fraction
        if self.bar.maximum() == 0:
            self.bar.setRange(0, 100)
        self.bar.setValue(int(round(fraction * 100)))
        self.refresh_time()

    def cancelling(self) -> None:
        """Cancel was asked for: it takes effect at the next checkpoint."""
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")
        self._fit()

    def finish(self) -> None:
        self._timer.stop()
        self.hide()

    def elapsed_s(self) -> float:
        return self._elapsed.elapsed() / 1000.0 if self._elapsed.isValid() else 0.0

    def remaining_s(self) -> Optional[float]:
        """The estimated time left [s], or None when there is too little to go on."""
        elapsed, fraction = self.elapsed_s(), self._fraction
        if fraction is None or fraction < 0.02 or elapsed < 3.0 or fraction >= 1.0:
            return None
        return elapsed * (1.0 - fraction) / fraction

    def refresh_time(self) -> None:
        parts = [f"{clock_text(self.elapsed_s())} elapsed"]
        if self._fraction is not None:
            parts.insert(0, f"{int(round(self._fraction * 100))} %")
        remaining = self.remaining_s()
        if remaining is not None and remaining >= 1.0:  # [s] under a second, "about 0:00 left" says nothing
            parts.append(f"about {clock_text(remaining)} left")
        self.time_label.setText(" · ".join(parts))
        self._fit()

    def _fit(self) -> None:
        """Take the width the text needs now: the status bar lays its
        entries out again only when asked."""
        width = self.sizeHint().width()
        if width != self._fitted_width and self.parentWidget() is not None:
            self._fitted_width = width
            self.updateGeometry()
            layout = self.parentWidget().layout()
            if layout is not None:
                layout.invalidate()


class TopBar(QWidget):
    """Scenario name · saved or not · source · last run, the breadcrumbs
    under them; on the right the window's commands (:meth:`add_commands`)
    and, while the scenario has any, its problem count."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)  # [px]
        layout.setSpacing(12)  # [px]
        # Each gives way before the commands do: the window fits 1280 px.
        self.name_label = ElidedLabel()
        self.name_label.setObjectName("topBarName")
        self.detail_label = ElidedLabel()
        self.detail_label.setObjectName("topBarDetail")
        self.breadcrumb_label = ElidedLabel()
        self.breadcrumb_label.setObjectName("topBarBreadcrumbs")
        self.breadcrumb_label.setAccessibleName("Where you are")
        title_row = QHBoxLayout()
        title_row.setSpacing(12)  # [px]
        title_row.addWidget(self.name_label)
        title_row.addWidget(self.detail_label, 1)
        left = QVBoxLayout()
        left.setSpacing(0)
        left.addLayout(title_row)
        left.addWidget(self.breadcrumb_label)
        layout.addLayout(left, 1)
        self.commands = QHBoxLayout()
        self.commands.setSpacing(4)  # [px]
        layout.addLayout(self.commands)
        self.save_button: Optional[QToolButton] = None
        self.search_button: Optional[QToolButton] = None
        self._dirty = False
        self._source = ""
        self._last_run = ""

    def add_commands(self, undo: QAction, redo: QAction, save: QAction, run: QAction, mode_button: QWidget,
                     palette: QAction) -> None:
        """Undo and redo as icons, Save showing the save state, Run with its
        mode beside it, and the command palette's search field."""
        for action, name in ((undo, "undo-2"), (redo, "redo-2")):
            button = QToolButton()
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            keep_icon(button, icon(name, "text.secondary"))
            button.setAccessibleName(action.text().replace("&", ""))
            self.commands.addWidget(button)
        # Not the action's own button: it shows the save state, not "Save".
        self.save_button = QToolButton()
        self.save_button.setObjectName("topBarSave")
        self.save_button.setIcon(icon("save", "text.secondary"))
        self.save_button.setToolTip(save.toolTip())
        self.save_button.setAccessibleName("Save")
        self.save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.save_button.clicked.connect(save.trigger)
        self.commands.addWidget(self.save_button)
        self.commands.addSpacing(8)  # [px]
        self.run_button = QToolButton()
        self.run_button.setObjectName("primaryToolButton")
        self.run_button.setDefaultAction(run)
        self.run_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        keep_icon(self.run_button, icon("play", "text.on_accent"))  # the accent icon would vanish on the fill
        self.commands.addWidget(self.run_button)
        self.commands.addWidget(mode_button)
        self.commands.addSpacing(8)  # [px]
        self.search_button = QToolButton()
        self.search_button.setObjectName("topBarSearch")
        self.search_button.setText(f"Search...  {palette.shortcut().toString()}")
        self.search_button.setToolTip(palette.toolTip())
        self.search_button.setAccessibleName("Search commands")
        self.search_button.setIcon(icon("search", "text.secondary"))
        self.search_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.search_button.clicked.connect(palette.trigger)
        self.commands.addWidget(self.search_button)
        self.problems_button = _problems_button("topBarProblems")
        self.commands.addWidget(self.problems_button)
        self.set_problem_counts(0, 0)
        self._refresh_detail()

    def set_problem_counts(self, errors: int, warnings: int) -> None:
        """The scenario's problem count, shown only while it has some."""
        if self.search_button is None:
            return
        _show_problem_counts(self.problems_button, errors, warnings, short=True)
        self.problems_button.setVisible(bool(errors or warnings))

    def set_breadcrumbs(self, parts: List[str]) -> None:
        """Where the window is: "Scenario › Spacecraft › sat-1"."""
        self.breadcrumb_label.setText(" › ".join(part for part in parts if part))

    def set_scenario(self, name: str, dirty: bool, source: str) -> None:
        """``source``: "template 22", a file name, or "" for a new scenario."""
        self.name_label.setText(name or "Untitled scenario")
        self._dirty, self._source = dirty, source
        self._refresh_detail()

    def set_last_run(self, text: str) -> None:
        self._last_run = text
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        if self._dirty:
            state = "Unsaved changes"
        elif self._source.startswith("template "):
            state = "Unchanged"  # a template as shipped: nothing of the user's to save yet
        elif self._source:
            state = "Saved"
        else:
            state = "Not saved yet"
        parts = [state]
        if self._source:
            parts.append(f"from {self._source}")
        parts.append(self._last_run or "not run yet")
        self.detail_label.setText(" · ".join(parts))
        if self.save_button is not None:
            # The save state on the Save button too: a click saves.
            self.save_button.setText("Save" if self._dirty else state)


def source_of(path: Optional[Path], templates_dir: Path) -> str:
    """How the top bar names where a scenario came from."""
    if path is None:
        return ""
    if path.parent.resolve() == templates_dir.resolve():
        number = path.name.split("_", 1)[0]
        return f"template {number}" if number.isdigit() else path.name
    return path.name


class StatusBarItems:
    """The permanent status-bar entries. :meth:`refresh` re-reads local
    files only; the window calls it at start-up, after the reference
    data panel changes something and when a run starts."""

    def __init__(self, parent: QWidget) -> None:
        self.problems_button = _problems_button("statusProblems", parent)
        self.basilisk_label = QLabel(parent)
        self.basilisk_label.setObjectName("statusItem")
        self.data_button = QToolButton(parent)
        self.data_button.setObjectName("statusDataButton")
        self.data_button.setAutoRaise(True)
        self.data_button.setToolTip("Reference data: open the Reference data dialog")
        # The two longest entries give way while a run's job shares the bar;
        # their tooltips have all of it.
        self.earth_orientation_label = ElidedLabel(parent)
        self.earth_orientation_label.setObjectName("statusItem")
        self.earth_orientation_label.setMinimumWidth(48)  # [px]
        self.frames_label = ElidedLabel(parent)
        self.frames_label.setObjectName("statusItem")
        self.frames_label.setMinimumWidth(48)  # [px]
        items = (self.problems_button, self.basilisk_label, self.data_button, self.earth_orientation_label,
                 self.frames_label)
        # A thin rule between entries: side by side they read as one line.
        separated = [items[0]]
        for item in items[1:]:
            separated += [_separator(parent), item]
        self.widgets = tuple(separated)

    @property
    def data_clicked(self) -> Signal:
        return self.data_button.clicked

    @property
    def problems_clicked(self) -> Signal:
        return self.problems_button.clicked

    def set_problem_counts(self, errors: int, warnings: int) -> None:
        _show_problem_counts(self.problems_button, errors, warnings)

    def refresh(self) -> None:
        from .. import dependencies
        from ..engine import earth_orientation, reference_data

        version = dependencies.basilisk_version()
        note = dependencies.basilisk_check(version)
        if version is None:
            self.basilisk_label.setText("Basilisk not installed")
        else:
            self.basilisk_label.setText(f"Basilisk {version}" + (" (not qualified)" if note else ""))
        self.basilisk_label.setProperty("state", "warning" if note else "")
        self.basilisk_label.setToolTip(note or f"The qualified Basilisk release, "
                                               f"{dependencies.QUALIFIED_BASILISK_VERSION}")
        _repolish(self.basilisk_label)

        files = reference_data.inventory()
        problems = [f for f in files if f.status != "ok"]
        self.data_button.setText(f"Reference data: {len(problems)} of {len(files)} need attention" if problems
                                 else f"Reference data: all {len(files)} OK")
        self.data_button.setProperty("state", "warning" if problems else "")
        _repolish(self.data_button)

        kernels = earth_orientation.installed()
        until = earth_orientation.high_accuracy_until(kernels) if kernels else None
        if not kernels:
            self.earth_orientation_label.setText(
                f"Earth orientation: none ({earth_orientation.FALLBACK_EARTH_FRAME})")
        elif until is not None:
            self.earth_orientation_label.setText(f"Earth orientation: high accuracy to {until:%Y-%m-%d}")
        else:
            self.earth_orientation_label.setText("Earth orientation: installed")
        earth_fixed = earth_orientation.EARTH_FIXED_FRAME if kernels else earth_orientation.FALLBACK_EARTH_FRAME
        self.frames_label.setText(f"Frames: EME2000 · {earth_fixed} · UTC")
        self.frames_label.setToolTip(f"{self.frames_label.text()}\n{_FRAMES_TIP}")


_FRAMES_TIP = ("Inertial frame of orbits and results; Earth-fixed frame of ground stations; the time system "
               "of every date shown")


def _problems_button(name: str, parent: Optional[QWidget] = None) -> QToolButton:
    button = QToolButton(parent)
    button.setObjectName(name)
    button.setAutoRaise(True)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setToolTip("Open the Problems panel (Ctrl+J)")
    return button


def _show_problem_counts(button: QToolButton, errors: int, warnings: int, short: bool = False) -> None:
    """ "1 error · 2 warnings" ("3", short) with the icon of the worst;
    colour is never the only sign (design rule 1)."""
    parts = [f"{errors} error{'s' if errors != 1 else ''}"] if errors else []
    if warnings:
        parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
    if short:
        button.setText(str(errors + warnings) if parts else "")
    else:
        button.setText(" · ".join(parts) if parts else "No problems")
    button.setAccessibleName(" · ".join(parts) if parts else "No problems")
    name, ink = (("octagon-alert", "status.critical") if errors else
                 ("triangle-alert", "status.caution") if warnings else ("circle-check", "text.secondary"))
    button.setIcon(icon(name, ink))
    button.setProperty("state", "error" if errors else "warning" if warnings else "")
    _repolish(button)


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _separator(parent: QWidget) -> QFrame:
    rule = QFrame(parent)
    rule.setObjectName("statusSeparator")
    rule.setFrameShape(QFrame.Shape.VLine)
    rule.setFixedWidth(9)  # [px] the rule and a little room either side
    return rule
