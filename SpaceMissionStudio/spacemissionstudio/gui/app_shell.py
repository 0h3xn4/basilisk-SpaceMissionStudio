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

* :class:`TopBar` -- one line above the work area: the scenario's name,
  whether it has unsaved changes, where it came from (a template, a file
  or nothing yet), the last run, and a :class:`StatusChip` (idle,
  running 43 %, done, failed, cancelled).
* :class:`RunProgressStrip` -- under the top bar while a run is going
  (U-19): what it is doing ("Step 2 of 5: ...", "Propagating: day 0.4
  of 1"), a progress bar, the time elapsed and an estimate of the time
  left, and **Cancel (Esc)**.
* :class:`StatusBarItems` -- permanent status-bar entries: the Basilisk
  version, the reference data (clicking it opens the Reference data
  dialog), the
  Earth orientation data and the frames runs use. They read local files
  only, never the network.

Colours come from theme.py's ``QLabel#statusChip[state=...]`` and
``QWidget#topBar`` rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QElapsedTimer, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QToolButton, QWidget

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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)  # [px]
        layout.setSpacing(12)  # [px]
        self.phase_label = QLabel()
        self.phase_label.setObjectName("runPhase")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)  # the percentage is in the time label and the status chip
        self.bar.setFixedWidth(200)  # [px]
        self.time_label = QLabel()
        self.time_label.setObjectName("runTime")
        self.cancel_button = QPushButton("Cancel (Esc)")
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
        self.hide()

    def start(self, phase: str, cancellable: bool = True, cancel_note: str = "") -> None:
        """A run starts: ``cancel_note`` says why it cannot be cancelled."""
        self._elapsed.start()
        self._fraction = None
        self.bar.setRange(0, 0)  # busy until a fraction arrives
        self.phase_label.setText(phase)
        self.cancel_button.setEnabled(cancellable)
        self.cancel_button.setText("Cancel (Esc)")
        self.cancel_button.setToolTip("" if cancellable else cancel_note)
        self.refresh_time()
        self._timer.start()
        self.show()

    def set_phase(self, text: str) -> None:
        self.phase_label.setText(text)

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


class TopBar(QWidget):
    """Scenario name · saved or not · source · last run, and the status chip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)  # [px]
        layout.setSpacing(12)  # [px]
        self.name_label = QLabel()
        self.name_label.setObjectName("topBarName")
        self.detail_label = QLabel()
        self.detail_label.setObjectName("topBarDetail")
        self.chip = StatusChip()
        layout.addWidget(self.name_label)
        layout.addWidget(self.detail_label, 1)
        layout.addWidget(self.chip)
        self._dirty = False
        self._source = ""
        self._last_run = ""

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
        self.basilisk_label = QLabel(parent)
        self.basilisk_label.setObjectName("statusItem")
        self.data_button = QToolButton(parent)
        self.data_button.setObjectName("statusDataButton")
        self.data_button.setAutoRaise(True)
        self.data_button.setToolTip("Reference data: open the Reference data dialog")
        self.earth_orientation_label = QLabel(parent)
        self.earth_orientation_label.setObjectName("statusItem")
        self.frames_label = QLabel(parent)
        self.frames_label.setObjectName("statusItem")
        self.frames_label.setToolTip("Inertial frame of orbits and results; Earth-fixed frame of ground "
                                     "stations; the time system of every date shown")
        items = (self.basilisk_label, self.data_button, self.earth_orientation_label, self.frames_label)
        # A thin rule between entries: side by side they read as one line.
        separated = [items[0]]
        for item in items[1:]:
            separated += [_separator(parent), item]
        self.widgets = tuple(separated)

    @property
    def data_clicked(self) -> Signal:
        return self.data_button.clicked

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


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _separator(parent: QWidget) -> QFrame:
    rule = QFrame(parent)
    rule.setObjectName("statusSeparator")
    rule.setFrameShape(QFrame.Shape.VLine)
    rule.setFixedWidth(9)  # [px] the rule and a little room either side
    return rule
