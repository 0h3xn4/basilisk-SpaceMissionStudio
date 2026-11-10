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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Every value with its unit (transparency plan, Phase 8a): each number
field of the editors carries its unit, or is one of the dimensionless
values and counts named here; the gains carry their control laws' units;
a field that shows another unit than it saves says so; the plots' unit
preference; the elapsed-time axis names its time scale."""

import numpy as np
import pytest
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel

from spacemissionstudio.engine.results import TimeSeries
from spacemissionstudio.gui import units, widgets

pytestmark = pytest.mark.requires_gui

# The number fields with no unit, each dimensionless or a count, by its label (a row labelled by a
# checkbox or a choice is named "<checkbox>" with its text, or "(anomaly)" for the orbit's).
_NO_UNIT = {
    "Plume / modulation efficiency": "two efficiencies [-]",
    "Injection error: e vector": "an eccentricity [-]",
    "Collision avoidances": "a count",
    "Scale (body x, y, z axes, 3 components)": "scale factors [-]",
    "Panel efficiency": "an efficiency [-]",
    "Panel normal (body frame, 3 components)": "a direction [-]",
    "Battery initial state of charge": "a fraction [-]",
    "Eclipse sunlit threshold": "a fraction of full sunlight [-]",
    "Direction (3 components, in Frame above)": "a direction [-]",
    "Trigger tolerance (fraction of target)": "a fraction [-]",
    "Restore tolerance (fraction of target)": "a fraction [-]",
    "Max burn length (fraction of an orbit)": "a fraction [-]",
    "Camera mounting (MRP, camera from body)": "an MRP [-]",
    "Random seed": "a seed",
    "Landmarks": "a count",
    "Control periods between firings": "a count",
    "<checkbox> Antenna boresight (body frame)": "a direction [-]",
    "Antenna boresight (body frame B)": "a direction [-]",
    "Axis to point at the Sun (body frame B)": "a direction [-]",
    "Eccentricity": "an eccentricity [-]",
    "Drag coefficient": "a coefficient [-]",
    "SRP reflectivity coefficient": "a coefficient [-]",
    "sigma_BN (MRP, body B relative to EME2000 N)": "an MRP [-]",
    "Number of runs": "a count",
    "Thread count": "a count",
    "Degree/order": "a count",
    "Number of revolutions": "a count",
}


def _editors(qtbot):
    from spacemissionstudio.gui.budget_widget import BudgetWidget
    from spacemissionstudio.gui.ground_station_editor import GroundStationEditorDialog
    from spacemissionstudio.gui.lifetime_widget import LifetimeWidget
    from spacemissionstudio.gui.mission_sequence_editor import _CommandEditorDialog
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    roots = [SpacecraftEditorDialog(), ScenarioEditorWidget(), _DispersionEditorDialog(["sat"]), BudgetWidget(),
             LifetimeWidget(), GroundStationEditorDialog(), _CommandEditorDialog(spacecraft_names=["sat"])]
    for root in roots:
        qtbot.addWidget(root)
        widgets.units_into_fields(root)
    return roots


def _label_text(label) -> str:
    if isinstance(label, QLabel):
        return label.text()
    if label is not None and hasattr(label, "text") and type(label).__name__ == "QCheckBox":
        return f"<checkbox> {label.text()}"
    return "(anomaly)" if label is not None else "(no label)"


def _without_unit(roots) -> dict[str, str]:
    """{label: the form's group} of every form row whose number field shows no unit."""
    found = {}
    for root in roots:
        for form in root.findChildren(QFormLayout):
            for _row, roles in sorted(widgets.form_rows(form).items()):
                boxes = widgets._number_boxes(roles.get(QFormLayout.ItemRole.FieldRole))
                if boxes and not all(box.suffix().strip() for box in boxes):
                    group = form.parentWidget()
                    found[_label_text(roles.get(QFormLayout.ItemRole.LabelRole))] = (
                        group.title() if isinstance(group, QGroupBox) else type(root).__name__)
    return found


def test_every_number_field_shows_its_unit(qtbot):
    """The editors' number fields: each shows its unit, or is one of the
    dimensionless values and counts above. A new field without a unit
    fails here until it has one or is named with its reason."""
    found = _without_unit(_editors(qtbot))
    assert set(found) - set(_NO_UNIT) == set(), "number fields without a unit: " + ", ".join(
        f"{label!r} ({group})" for label, group in found.items() if label not in _NO_UNIT)


def test_the_gains_carry_their_control_laws_units(qtbot):
    """K, P, Ki and the integral limit: the units of mrpFeedback's control
    law; the momentum-management gain, Basilisk's [1/s] (was labelled [-]);
    the inertia's diagonal, kg·m²; the starting anomaly, degrees."""
    from spacemissionstudio.gui.param_form import short_label
    from spacemissionstudio.gui.spacecraft_editor import _CONTROL_PARAM_SPECS, SpacecraftEditorDialog
    from spacemissionstudio.gui.wizard_settings import _META

    assert {spec.key: short_label(spec)[1] for spec in _CONTROL_PARAM_SPECS} == {
        "K": "N*m", "P": "N*m*s", "Ki": "1/(N*m*s^2)", "integral_limit": "s"}
    assert (_META["K"].suffix, _META["P"].suffix, _META["c_gain"].suffix) == (" N*m", " N*m*s", " 1/s")
    assert units.suffix("1/(N*m*s^2)") == " 1/(N·m·s²)" and units.suffix("degC") == " °C"
    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    widgets.units_into_fields(dialog)
    assert dialog.mmm_c_gain.suffix() == " 1/s" and "1/s" in dialog.mmm_c_gain.toolTip()
    assert dialog.ixx.suffix() == dialog.izz.suffix() == " kg·m²"
    assert dialog.orbit_widget.anomaly_deg.suffix() == "°"


def test_a_field_shown_in_another_unit_says_what_is_saved(qtbot):
    """GHz and Mbit/s on the page, Hz and bit/s in the file; a dispersion's
    and an assignment's fields carry their quantity's unit."""
    from spacemissionstudio.gui.mission_sequence_editor import _CommandEditorDialog
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    assert "saved in the scenario in Hz (rf_link.frequency_hz)" in dialog.frequency_ghz.toolTip()
    assert "in bit/s (rf_link.data_rate_bps)" in dialog.data_rate_mbps.toolTip()
    dispersion = _DispersionEditorDialog(["sat"])
    qtbot.addWidget(dispersion)
    for quantity, suffix in (("dry_mass_kg", " kg"), ("angular_rate_bn_b", "°/s"), ("inertia_kg_m2", " kg·m²"),
                             ("drag_coeff", "")):
        dispersion.quantity_combo.setCurrentText(quantity)
        assert (dispersion.mean_spin.suffix(), dispersion.std_spin.suffix(),
                dispersion.bounds_lo_spin.suffix()) == (suffix,) * 3, quantity
    command = _CommandEditorDialog(spacecraft_names=["sat"])
    qtbot.addWidget(command)
    for parameter, suffix in (("thrust_n", " N"), ("isp_s", " s")):
        command.assignment_parameter_combo.setCurrentText(parameter)
        assert command.assignment_value_spin.suffix() == suffix


def test_the_plots_units_are_a_preference(qtbot):
    """Display units by default (an inclination in degrees, wrapping at
    360); as recorded, the values and unit the run recorded and exports
    (radians, wrapping at 2 pi) and the elapsed time in seconds. A series
    that records no unit keeps its display."""
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.results_widget import ELAPSED_AXIS_TITLE, ResultsWidget, _shown
    from spacemissionstudio.plot_categories import shown

    series = TimeSeries("sat.orbit_elements.raan", np.array([0.0, 60.0]), ("raan",),
                        np.array([[0.1], [0.2]]), units="rad")  # [s], [rad]
    display, recorded = shown(series.name, series), shown(series.name, series, recorded=True)
    assert (display.unit, display.wrap_period) == ("deg", 360.0) and display.factor == pytest.approx(57.29577951)
    assert (recorded.unit, recorded.factor) == ("rad", 1.0) and recorded.wrap_period == pytest.approx(2 * np.pi)
    bare = TimeSeries("sat.orbit_elements.raan", series.time_s, ("raan",), series.data)
    assert shown(bare.name, bare, recorded=True) == shown(bare.name, bare)
    assert units.plot_units() == "display" and _shown(series.name, series) == display
    assert ELAPSED_AXIS_TITLE == "Elapsed time since t0, TDB [h]"
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    page = window.settings_page
    page.plot_units.setCurrentIndex(page.plot_units.findData("recorded"))
    assert units.plot_units() == "recorded" and _shown(series.name, series) == recorded
    assert page.plot_units_note.text() == "Applies to the plots drawn next."
    plots = ResultsWidget()
    qtbot.addWidget(plots)
    assert plots._x_axis_values(np.array([0.0, 7200.0]))[1] == "Elapsed time since t0, TDB [s]"
    with pytest.raises(ValueError, match="plot units"):
        units.set_plot_units("imperial")
