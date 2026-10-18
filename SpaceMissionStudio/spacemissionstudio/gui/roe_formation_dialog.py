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

"""RoeFormationDialog: the "Generate ROE formation..." dialog. It
collects the chief, the template, the new follower's name, the control
law and the formation, either as a passively safe formation (along-track
offset, radial and cross-track half-sizes, phase) or as the six relative
orbital elements in metres.

Only :mod:`engine.roe` (numpy) is imported here, for the safe formation
and its closest approach. Placing the follower needs Basilisk's
mean/osculating mapping (``engine.roe_formation.generate_roe_follower``),
which ``spacecraft_editor.py``'s ``_on_generate_roe_formation`` imports
when Generate is clicked.
"""

from __future__ import annotations

from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..engine.roe import ROE_LABELS, min_radial_normal_separation, safe_formation
from ..schema.scenario import SpacecraftConfig
from .feedback import show_dialog_error
from .widgets import ComboBox, PreciseDoubleSpinBox

_ROE_TITLES = ("a·δa [m]", "a·δλ [m]", "a·δex [m]", "a·δey [m]", "a·δix [m]", "a·δiy [m]")
_ROE_TIPS = (
    "Relative semi-major axis times the chief's semi-major axis [m]. Not zero: the follower drifts along-track.",
    "Relative mean longitude [m]: the along-track offset of the follower's centre of motion, + ahead of the chief.",
    "Eccentricity vector, first component [m]: the radial half-size of the relative ellipse, with δey.",
    "Eccentricity vector, second component [m].",
    "Inclination vector, first component [m]: the cross-track half-size, with δiy. J2 makes a nonzero δix "
    "drift the formation along-track, so the safe formations here keep it at 0.",
    "Inclination vector, second component [m].",
)


def _form_group(title: str) -> tuple[QGroupBox, QFormLayout]:
    group = QGroupBox(title)
    return group, QFormLayout(group)


def _double_spin(minimum: float, maximum: float, decimals: int, step: float, value: float) -> QDoubleSpinBox:
    box = PreciseDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    return box


class RoeFormationDialog(QDialog):
    """Modal "Generate ROE formation..." dialog. ``spacecraft_names``
    lists the scenario's spacecraft; the chief (its orbit) and the
    template (everything else, including the station keeping thruster
    the formation fires) are picked from them. ``spacecraft``, when given,
    lets the dialog refuse a template without station keeping before
    Generate."""

    def __init__(self, spacecraft_names: list[str], central_body: str = "earth", parent=None,
                 spacecraft: list[SpacecraftConfig] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Generate ROE formation")
        self._central_body = central_body
        self._spacecraft = {config.name: config for config in (spacecraft or [])}

        layout = QVBoxLayout(self)
        description_label = QLabel(
            "Adds a follower that flies in formation with the chief, set by relative orbital elements, and "
            "holds it with the chosen law. A passively safe formation keeps the two apart radially and "
            "cross-track even if the along-track spacing is lost. Hover any field for details."
        )
        description_label.setWordWrap(True)  # see phasing_formation_dialog.py: a one-line label widens the dialog
        layout.addWidget(description_label)

        spacecraft_group, spacecraft_form = _form_group("Spacecraft")
        spacecraft_form.addRow("Central body", QLabel(central_body))
        self.chief_combo = ComboBox()
        self.template_combo = ComboBox()
        if spacecraft_names:
            for name in spacecraft_names:
                self.chief_combo.addItem(name, userData=name)
                self.template_combo.addItem(name, userData=name)
        else:
            for combo in (self.chief_combo, self.template_combo):
                combo.addItem("(no spacecraft in this scenario yet)", userData=None)
                combo.setEnabled(False)
        self.chief_combo.setToolTip("The existing spacecraft the follower flies in formation with. Its orbit "
                                    "must be classical elements, near-circular (eccentricity at most 0.01).")
        self.template_combo.setToolTip(
            "The existing spacecraft everything else (mass, hardware, attitude control) is copied from. It must "
            "have station keeping: the formation fires that thruster and draws from its tank.")
        spacecraft_form.addRow("Chief (orbit source)", self.chief_combo)
        spacecraft_form.addRow("Template (everything else)", self.template_combo)
        self.follower_name_edit = QLineEdit("follower-1")
        spacecraft_form.addRow("New follower name", self.follower_name_edit)
        self.control_law_combo = ComboBox()
        for label, law in (("Impulsive burns (planned with the J2 model)", "impulsive"),
                           ("Continuous (Basilisk meanOEFeedback)", "continuous")):
            self.control_law_combo.addItem(label, userData=law)
        self.control_law_combo.setToolTip(
            "Impulsive: the tool plans along-track and cross-track burns with a J2 model, in sunlight only. "
            "Continuous: Basilisk's meanOEFeedback thrusts whenever the error asks for it. Tolerances and gain "
            "keep their defaults and can be changed in the follower's Spacecraft editor.")
        spacecraft_form.addRow("Control law", self.control_law_combo)
        layout.addWidget(spacecraft_group)

        formation_group, formation_form = _form_group("Formation")
        self.mode_combo = ComboBox()
        self.mode_combo.addItem("Passively safe formation", userData="safe")
        self.mode_combo.addItem("Relative orbital elements", userData="roe")
        self.mode_combo.setToolTip("Passively safe: set the shape and let the dialog work out the elements. "
                                   "Relative orbital elements: type all six.")
        formation_form.addRow("Specify as", self.mode_combo)

        self._pages = QStackedWidget()
        safe_page = QWidget()
        safe_form = QFormLayout(safe_page)
        safe_form.setContentsMargins(0, 0, 0, 0)
        self.safe_along_m = _double_spin(-1.0e6, 1.0e6, 1, 50.0, 0.0)  # [m]
        self.safe_along_m.setToolTip("Along-track offset of the centre of motion [m], + ahead of the chief.")
        self.safe_radial_m = _double_spin(0.0, 1.0e5, 1, 50.0, 300.0)  # [m]
        self.safe_radial_m.setToolTip("Radial half-size of the relative ellipse [m].")
        self.safe_cross_m = _double_spin(0.0, 1.0e5, 1, 50.0, 300.0)  # [m]
        self.safe_cross_m.setToolTip("Cross-track half-size of the relative ellipse [m].")
        self.safe_phase_deg = _double_spin(-360.0, 360.0, 1, 15.0, 90.0)  # [deg]
        self.safe_phase_deg.setToolTip(
            "Angle of the parallel eccentricity and inclination vectors [deg]. 90 deg puts the inclination "
            "vector along δiy, which J2 leaves alone.")
        safe_form.addRow("Along-track [m]", self.safe_along_m)
        safe_form.addRow("Radial half-size [m]", self.safe_radial_m)
        safe_form.addRow("Cross-track half-size [m]", self.safe_cross_m)
        safe_form.addRow("Phase [deg]", self.safe_phase_deg)
        self._pages.addWidget(safe_page)

        roe_page = QWidget()
        roe_form = QFormLayout(roe_page)
        roe_form.setContentsMargins(0, 0, 0, 0)
        self.roe_spins: List[QDoubleSpinBox] = []
        for label, title, tip in zip(ROE_LABELS, _ROE_TITLES, _ROE_TIPS):
            box = _double_spin(-1.0e6, 1.0e6, 3, 10.0, 0.0)  # [m]
            box.setToolTip(tip)
            box.setObjectName(f"roe_{label}")
            roe_form.addRow(title, box)
            self.roe_spins.append(box)
        self._pages.addWidget(roe_page)
        formation_form.addRow(self._pages)
        self._show_page(0)

        self.margin_label = QLabel("")
        self.margin_label.setWordWrap(True)
        formation_form.addRow(self.margin_label)
        layout.addWidget(formation_group)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        for box in (self.safe_along_m, self.safe_radial_m, self.safe_cross_m, self.safe_phase_deg, *self.roe_spins):
            box.valueChanged.connect(self._show_margin)
        self._show_margin()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(self.sizeHint())  # see phasing_formation_dialog.py: Qt can first show it smaller

    def _on_mode_changed(self) -> None:
        """Switching to typed elements starts them from the safe formation
        shown, so the switch keeps the formation."""
        if self.mode_combo.currentData() == "roe":
            for box, value in zip(self.roe_spins, self._safe_roe_m()):
                box.setValue(value)
        self._show_page(self.mode_combo.currentIndex())
        self._show_margin()

    def _show_page(self, index: int) -> None:
        """Show page ``index``, sized to it alone: a stacked widget
        otherwise keeps room for its tallest page (a gap under the safe
        formation's four rows)."""
        for k in range(self._pages.count()):
            policy = QSizePolicy.Policy.Preferred if k == index else QSizePolicy.Policy.Ignored
            self._pages.widget(k).setSizePolicy(policy, policy)
        self._pages.setCurrentIndex(index)
        self._pages.adjustSize()
        self.adjustSize()

    def _safe_roe_m(self) -> List[float]:
        roe_m = safe_formation(self.safe_along_m.value(), self.safe_radial_m.value(), self.safe_cross_m.value(),
                               self.safe_phase_deg.value(), 1.0)
        return [round(float(x), 9) + 0.0 for x in roe_m]  # cos(90 deg) as 0, not 6e-17; + 0.0 drops -0.0

    def roe_m(self) -> List[float]:
        """The formation's six relative orbital elements [m], in
        ``engine.roe.ROE_LABELS`` order."""
        if self.mode_combo.currentData() == "safe":
            return self._safe_roe_m()
        return [box.value() for box in self.roe_spins]

    def _show_margin(self) -> None:
        roe_m = self.roe_m()
        margin = min_radial_normal_separation(roe_m, 1.0)  # [m] the ROE are already in metres
        text = f"Closest radial/cross-track approach: {margin:.1f} m"
        if margin <= 1.0e-3:
            text += " (the orbits cross: not passively safe)"
        if abs(roe_m[0]) > 0.0:
            text += ". A nonzero a·δa makes the follower drift along-track until the law corrects it."
        self.margin_label.setText(text)

    def _on_accept(self) -> None:
        problem = self.problem()
        if problem:
            show_dialog_error(self, f"This formation cannot be made: {problem}")
            return
        self.accept()

    def problem(self) -> str:
        """Why Generate would fail, in the dialog's words, or ""."""
        if self.selected_chief_name() is None:
            return "no chief spacecraft: add a spacecraft to the scenario first."
        if not self.follower_name().strip():
            return "New follower name is empty."
        if self._central_body != "earth":
            return (f"the central body is {self._central_body}; ROE formations use Earth's J2 and are "
                    "available around Earth only.")
        template = self._spacecraft.get(self.selected_template_name())
        if template is not None and template.station_keeping is None:
            return (f"Template (everything else) {template.name!r} has no station keeping; the formation fires "
                    "that thruster. Add station keeping to it, or pick another template.")
        if not any(self.roe_m()):
            return "every element is 0: the follower would sit on the chief."
        return ""

    def follower_name(self) -> str:
        return self.follower_name_edit.text().strip()

    def control_law(self) -> str:
        return self.control_law_combo.currentData()

    def selected_chief_name(self) -> str | None:
        return self.chief_combo.currentData()

    def selected_template_name(self) -> str | None:
        return self.template_combo.currentData()
