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

"""WalkerConstellationDialog: collects a
:class:`engine.constellation.WalkerConstellationRequest` plus which
existing spacecraft (if any) to use as the template -- see that module's
docstring for the Walker-pattern math and why only orbit/name vary.

Does not import ``engine.constellation`` at module scope beyond the
request dataclass itself (no Basilisk anywhere in that chain, so this is
safe -- but kept consistent with this project's "gui/ doesn't need to
know engine/ imports Basilisk" split used elsewhere, e.g. vizard_dialog.py).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..engine.constellation import CENTRAL_BODY_EQUATORIAL_RADIUS_KM, WALKER_PATTERNS, WalkerConstellationRequest
from ..engine.orbit_design import sun_synchronous_inclination_deg
from ..schema.scenario import ScenarioValidationError
from .feedback import show_dialog_error
from .field_text import attribute_title, labelled
from .widgets import ComboBox, PreciseDoubleSpinBox, SpinBox, finish_form

# The phasing-keeping laws, as the phasing formation dialog names them.
_PHASING_LAWS = (("Drift orbit (occasional burns)", "drift_orbit"),
                 ("Mean orbital elements (Basilisk)", "mean_oe"),
                 ("Hill-frame PD (Basilisk, close formations)", "hill_pd"))

_PATTERN_LABELS = {
    "delta": "Walker-Delta (planes spread over 360°, e.g. GPS)",
    "star": "Walker-Star (planes spread over 180°, e.g. Iridium -- near-polar)",
}


def _int_spin(minimum: int, maximum: int, value: int) -> QSpinBox:
    box = SpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    return box


def _double_spin(minimum: float, maximum: float, decimals: int, step: float, value: float) -> QDoubleSpinBox:
    box = PreciseDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    return box


class WalkerConstellationDialog(QDialog):
    """Modal "Generate Walker constellation" dialog. ``template_names``
    lists the scenario's current spacecraft (by name) to choose as the
    template for every generated satellite's non-orbit fields; empty means
    generate against a bare default spacecraft instead. ``central_body``
    is the scenario's ACTUAL current central body (read-only here, not a
    combo) -- deliberately not independently selectable, since a mismatch
    between this dialog's body and the scenario's real
    ``gravity.central_body`` would silently produce satellites at the
    wrong altitude relative to whatever body actually gets simulated.

    ``with_station_keeping`` names the templates that have station-keeping:
    only they can hold each plane's spacing (the phasing controller fires
    their thruster), so **Hold each plane's spacing** is offered for them
    alone.
    """

    def __init__(self, template_names: list[str], central_body: str = "earth", parent=None,
                 with_station_keeping=()):
        super().__init__(parent)
        self.setWindowTitle("Generate Walker constellation")
        self._central_body = central_body
        self._with_station_keeping = set(with_station_keeping)

        layout = QVBoxLayout(self)
        description_label = QLabel(
            "Adds a Walker constellation. Every satellite is a copy of the template spacecraft below; "
            "only the orbit and name differ."
        )
        # See phasing_formation_dialog.py's identical fix (same
        # copy-pasted top-description-QLabel shape, same missing
        # word-wrap) for the real screenshot that found this bug.
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        form = QFormLayout()
        form.addRow("Central body (from this scenario)", QLabel(central_body))

        self.template_combo = ComboBox()
        if template_names:
            for name in template_names:
                self.template_combo.addItem(name, userData=name)
        else:
            self.template_combo.addItem("(none -- use a bare default spacecraft)", userData=None)
            self.template_combo.setEnabled(False)
        form.addRow("Template spacecraft", self.template_combo)

        self.total_satellites = _int_spin(1, 10000, 12)
        self.num_planes = _int_spin(1, 1000, 3)
        self.phasing_factor = _int_spin(0, 999, 1)
        self.altitude_km = _double_spin(0.001, 1.0e7, 3, 10.0, 780.0)
        self.inclination_deg = _double_spin(0.0, 180.0, 4, 1.0, 86.4)
        self.eccentricity = _double_spin(0.0, 0.999999, 6, 0.001, 0.0)
        self.arg_periapsis_deg = _double_spin(0.0, 360.0, 4, 1.0, 0.0)
        self.pattern_combo = ComboBox()
        for pattern in WALKER_PATTERNS:
            self.pattern_combo.addItem(_PATTERN_LABELS[pattern], userData=pattern)
        self.raan_offset_deg = _double_spin(0.0, 360.0, 4, 1.0, 0.0)
        self.name_prefix_edit = QLineEdit("sat")

        form.addRow("Total satellites (T)", self.total_satellites)
        form.addRow("Number of planes (P)", self.num_planes)
        form.addRow("Phasing factor (F)", self.phasing_factor)
        form.addRow("Altitude [km]", self.altitude_km)
        inclination_row = QHBoxLayout()
        inclination_row.addWidget(self.inclination_deg, 1)
        self.sun_sync_button = QPushButton("Sun-synchronous")
        self.sun_sync_button.setToolTip("Set the inclination that makes this altitude/eccentricity "
                                        "Sun-synchronous (Earth only, J2).")
        self.sun_sync_button.clicked.connect(self._on_sun_synchronous)
        self.sun_sync_button.setEnabled(central_body == "earth")
        inclination_row.addWidget(self.sun_sync_button)
        form.addRow("Inclination [deg]", inclination_row)
        form.addRow("Eccentricity [-]", self.eccentricity)
        form.addRow("Argument of periapsis [deg]", self.arg_periapsis_deg)
        form.addRow("Pattern", self.pattern_combo)
        form.addRow("RAAN offset [deg]", self.raan_offset_deg)
        form.addRow("Generated name prefix", self.name_prefix_edit)
        self.phasing_check = QCheckBox("Hold each plane's spacing")
        self.phasing_law_combo = ComboBox()
        for label, law in _PHASING_LAWS:
            self.phasing_law_combo.addItem(label, userData=law)
        self.phasing_law_combo.setToolTip("Which flight-software law holds each satellite's separation from its "
                                          "plane's first satellite. See User Manual, 'Formation control laws'.")
        form.addRow("Phasing-keeping", self.phasing_check)
        form.addRow("Phasing control law", self.phasing_law_combo)
        layout.addLayout(form)
        self.phasing_check.toggled.connect(self._update_phasing)
        self.template_combo.currentIndexChanged.connect(self._update_phasing)
        self._update_phasing()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # See propagation_setup_dialog.py's identical fix for why this is
        # needed even though nothing here looks obviously undersized in
        # this project's own offscreen test rendering: on a real desktop
        # (confirmed from an actual user screenshot of a sibling dialog,
        # gui.template_wizard.TemplateCustomizeWizard), Qt can size a
        # freshly-constructed QDialog/QWizard smaller than its OWN
        # sizeHint() on first show() -- a real, platform-dependent layout
        # -convergence gap this project's own offscreen Qt backend does
        # not reproduce, so it can only be caught by explicitly forcing
        # the size rather than trusting Qt's default first-show sizing.
        finish_form(self)  # units in the fields, optional groups collapse (M4a)
        self.resize(self.sizeHint())

    def _update_phasing(self) -> None:
        """Hold each plane's spacing: only for a template with
        station-keeping; the law only while it is checked."""
        possible = self.template_combo.currentData() in self._with_station_keeping
        self.phasing_check.setEnabled(possible)
        if not possible:
            self.phasing_check.setChecked(False)
        self.phasing_check.setToolTip(
            "Each plane's first satellite is its chief; every other satellite of the plane keeps its slot's "
            "along-track separation from it, with the template's station-keeping thruster." if possible else
            "Needs a template spacecraft with station-keeping: phasing fires its thruster and draws on its "
            "propellant.")
        self.phasing_law_combo.setEnabled(self.phasing_check.isChecked())

    def _on_accept(self) -> None:
        try:
            self.to_request()
        except ScenarioValidationError as exc:
            message = labelled(str(exc), lambda code: attribute_title(self, code, "constellation"))
            show_dialog_error(self, f"This constellation cannot be made: {message}")
            return
        self.accept()

    def _on_sun_synchronous(self) -> None:
        semi_major_axis_km = CENTRAL_BODY_EQUATORIAL_RADIUS_KM["earth"] + self.altitude_km.value()
        try:
            self.inclination_deg.setValue(
                sun_synchronous_inclination_deg(semi_major_axis_km, self.eccentricity.value()))
        except ValueError as exc:  # too high an orbit to be Sun-synchronous
            show_dialog_error(self, f"No Sun-synchronous inclination: {exc}")
            return
        self._sun_synchronous = (self.inclination_deg.value(), (
            f"Sun-synchronous inclination at a = {semi_major_axis_km:g} km, e = {self.eccentricity.value():g} "
            f"(engine.orbit_design), rounded to {self.inclination_deg.decimals()} decimals"))

    def inclination_source(self) -> str | None:
        """What computed the inclination, while it is the Sun-synchronous
        button's value (Phase 5b); None once edited, or never computed."""
        computed = getattr(self, "_sun_synchronous", None)
        return computed[1] if computed is not None and computed[0] == self.inclination_deg.value() else None

    def to_request(self) -> WalkerConstellationRequest:
        request = WalkerConstellationRequest(
            total_satellites=self.total_satellites.value(),
            num_planes=self.num_planes.value(),
            phasing_factor=self.phasing_factor.value(),
            altitude_km=self.altitude_km.value(),
            inclination_deg=self.inclination_deg.value(),
            central_body=self._central_body,
            eccentricity=self.eccentricity.value(),
            arg_periapsis_deg=self.arg_periapsis_deg.value(),
            pattern=self.pattern_combo.currentData(),
            raan_offset_deg=self.raan_offset_deg.value(),
            name_prefix=self.name_prefix_edit.text().strip(),
            phasing_keeping=self.phasing_check.isChecked(),
            phasing_control_law=self.phasing_law_combo.currentData(),
        )
        request.validate()  # raises ScenarioValidationError with a specific message on anything bad
        return request

    def selected_template_name(self) -> str | None:
        return self.template_combo.currentData()
