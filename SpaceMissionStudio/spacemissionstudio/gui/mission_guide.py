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

"""Starting a mission from scratch without feeling lost (the user's
request of 2026-10-21: a blank scenario starts in *Orbit only*, "but it
should be clear to the user that this is not the only option. The user
shall understand the full capabilities of the tool").

* :class:`StartFromScratchCard`: the first choice on the Templates page,
  above the templates.
* :class:`MissionGuide`: on the Scenario page, the steps to a first run,
  each with its state and a button to its page, and what else the tool
  does, each with the page where it is.

Both only show and navigate: the scenario editor gives the guide its
state (:meth:`MissionGuide.update_state`) and acts on :attr:`MissionGuide.go_to`.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import SPACE, set_role

# Where a guide button leads (MissionGuide.go_to's argument).
ENVIRONMENT = "environment"
SPACECRAFT = "spacecraft"
GROUND_STATIONS = "ground_stations"
MISSION_SEQUENCE = "mission_sequence"
MONTE_CARLO = "monte_carlo"
ANALYSES = "analyses"
TEMPLATES = "templates"
FULL_ATTITUDE = "full_attitude"  # not a page: switch the simulation mode

# The mode, in two lines (a label holds at most 160 characters:
# tests/gui/test_label_text.py).
ORBIT_ONLY_SUMMARY = (
    "Orbit only, where a blank scenario starts: each spacecraft is a point mass with a drag and a solar-pressure "
    "area.",
    "That covers orbits, passes, eclipses, drag, lifetime and station-keeping. It is a starting point, not a "
    "limit: see There is more.")
FULL_ATTITUDE_SUMMARY = (
    "This scenario is in Full attitude: attitude, sensors, actuators, flight software and power are simulated.",
    "Orbit only (Simulation mode, above) makes each spacecraft a point mass, for orbit questions alone.")

# (key, title, what it is for); the state and the button follow.
_STEPS: Tuple[Tuple[str, str, str], ...] = (
    ("scenario", "1. Scenario", "Name it and set the epoch (UTC): the date fixes where the Sun and Moon are and how "
     "dense the upper atmosphere is."),
    (ENVIRONMENT, "2. Environment", "Central body, gravity field, third bodies, drag and space weather, the "
     "integrator and the duration. The defaults: one day around Earth."),
    (SPACECRAFT, "3. Spacecraft", "At least one: its orbit, mass and drag area. Add... builds one, New from "
     "template... starts from a 100-500 kg preset."),
    (GROUND_STATIONS, "4. Ground stations", "Optional: where passes and contacts are computed."),
    ("run", "5. Run", "Run on the toolbar (Ctrl+R). Results, Events and Explain then show what happened."),
)

# (title, what it does, button text, where the button leads).
_MORE: Tuple[Tuple[str, str, str, str], ...] = (
    ("Full attitude", "Sensors, actuators, attitude control and flight software, solar-panel power, faceted "
     "drag and flexible solar arrays.", "Switch to Full attitude", FULL_ATTITUDE),
    ("Manoeuvres and a mission timeline", "Burns, Lambert transfers, coasts to an event, conditions and loops, "
     "in the order they happen.", "Mission sequence", MISSION_SEQUENCE),
    ("Constellations and formations", "Walker constellations, phasing formations and relative-orbital-element "
     "formations, each generated in one go.", "Spacecraft", SPACECRAFT),
    ("Uncertainty", "Monte Carlo batches over dispersed orbits, masses, inertia, attitude, drag and solar "
     "pressure.", "Monte Carlo", MONTE_CARLO),
    ("Analyses", "Lifetime and deorbit (End of Life), delta-V and propellant (Budget), flight-software export "
     "and software-in-the-loop runs (Flight Software).", "Analyses", ANALYSES),
    ("Other worlds", "Orbits around the Moon, Mars, Jupiter or the Sun, and around asteroid 433 Eros with its "
     "shape-model gravity.", "Environment", ENVIRONMENT),
    ("Worked examples", "Ready-to-run templates for all of the above, each with notes on what to try.",
     "Templates", TEMPLATES),
)


def _label(text: str = "", role: Optional[str] = None, tone: Optional[str] = None) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    set_role(label, role=role, tone=tone)
    return label


def _ghost_button(text: str) -> QPushButton:
    button = QPushButton(text)
    set_role(button, variant="ghost")
    return button


class StartFromScratchCard(QFrame):
    """The Templates page's first choice: a blank scenario, with what it
    starts as."""

    requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        set_role(self, role="card")
        layout = QHBoxLayout(self)
        text = QVBoxLayout()
        text.addWidget(_label("Start from scratch", role="heading"))
        text.addWidget(_label("An empty mission you build step by step, guided on its Scenario page.",
                              tone="secondary"))
        text.addWidget(_label("It starts in Orbit only, the simplest mode; Full attitude adds attitude, sensors, "
                              "actuators and power.", tone="secondary"))
        layout.addLayout(text, 1)
        self.button = QPushButton("New blank scenario")
        self.button.setToolTip("File > New Scenario (Ctrl+N)")
        self.button.clicked.connect(self.requested)
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)


class MissionGuide(QFrame):
    """The steps to a first run and what else there is, on the Scenario page."""

    go_to = Signal(str)  # one of this module's page keys, or FULL_ATTITUDE

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        set_role(self, role="card")
        self.setObjectName("missionGuide")
        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(_label("Build your mission", role="section-title"), 1)
        self.toggle_button = _ghost_button("Hide guide")
        self.toggle_button.clicked.connect(lambda: self.set_expanded(self.body.isHidden()))
        header.addWidget(self.toggle_button, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)
        # Everything below the title: hidden with Hide guide.
        self.body = QWidget()
        outer.addWidget(self.body)
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mode_labels = (_label(tone="secondary"), _label(tone="secondary"))
        for label in self.mode_labels:
            layout.addWidget(label)

        steps = QGridLayout()
        steps.setColumnStretch(1, 1)
        self.step_badges: Dict[str, QLabel] = {}
        self.step_buttons: Dict[str, QPushButton] = {}
        for row, (key, title, text) in enumerate(_STEPS):
            steps.addWidget(_label(title, role="heading"), row, 0, Qt.AlignmentFlag.AlignTop)
            steps.addWidget(_label(text), row, 1, Qt.AlignmentFlag.AlignTop)
            badge = QLabel()
            self.step_badges[key] = badge
            steps.addWidget(badge, row, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            if key in (ENVIRONMENT, SPACECRAFT, GROUND_STATIONS):
                button = _ghost_button(f"Go to {title.split('. ', 1)[1]}")
                button.clicked.connect(lambda _checked=False, target=key: self.go_to.emit(target))
                self.step_buttons[key] = button
                steps.addWidget(button, row, 3, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        steps.setHorizontalSpacing(SPACE["md"])
        layout.addLayout(steps)

        layout.addSpacing(SPACE["md"])
        layout.addWidget(_label("There is more", role="heading"))
        self.more_intro = _label("Orbit only is where a mission starts, not all the tool does:", tone="secondary")
        layout.addWidget(self.more_intro)
        more = QGridLayout()
        more.setColumnStretch(1, 1)
        more.setHorizontalSpacing(SPACE["md"])
        self.more_buttons: Dict[str, QPushButton] = {}
        for row, (title, text, button_text, target) in enumerate(_MORE):
            more.addWidget(_label(title, role="strong"), row, 0, Qt.AlignmentFlag.AlignTop)
            more.addWidget(_label(text), row, 1, Qt.AlignmentFlag.AlignTop)
            button = _ghost_button(button_text)
            button.clicked.connect(lambda _checked=False, where=target: self.go_to.emit(where))
            self.more_buttons[title] = button
            more.addWidget(button, row, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(more)
        self.update_state(spacecraft=0, ground_stations=0, valid=False, orbit_only=True)

    def set_expanded(self, expanded: bool) -> None:
        """The whole guide, or its title and Show guide only."""
        self.body.setVisible(expanded)
        self.toggle_button.setText("Hide guide" if expanded else "Show guide")

    def _set_badge(self, key: str, text: str, status: str) -> None:
        badge = self.step_badges[key]
        badge.setText(text)
        set_role(badge, badge=status)

    def update_state(self, spacecraft: int, ground_stations: int, valid: bool, orbit_only: bool) -> None:
        """Each step's state, and the mode's wording, from the scenario as it is."""
        self._set_badge("scenario", "You are here", "standby")
        self._set_badge(ENVIRONMENT, "Review", "standby")
        if spacecraft:
            self._set_badge(SPACECRAFT, f"Done: {spacecraft}", "normal")
        else:
            self._set_badge(SPACECRAFT, "Needed", "caution")
        if ground_stations:
            self._set_badge(GROUND_STATIONS, f"Done: {ground_stations}", "normal")
        else:
            self._set_badge(GROUND_STATIONS, "Optional", "off")
        if valid:
            self._set_badge("run", "Ready", "normal")
        else:
            self._set_badge("run", "Not yet: see Problems", "off")
        for label, text in zip(self.mode_labels, ORBIT_ONLY_SUMMARY if orbit_only else FULL_ATTITUDE_SUMMARY):
            label.setText(text)
        self.more_buttons["Full attitude"].setVisible(orbit_only)
