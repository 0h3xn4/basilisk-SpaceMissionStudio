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
"""The spacecraft editor's ROE formation form (gui.roe_formation_editor
and its group in gui.spacecraft_editor): an existing formation shows and
saves unchanged, the targets table reads and refuses its cells, the
passively safe helper adds the formation it describes, and only the chosen
law's settings are shown."""

import pytest

pytestmark = pytest.mark.requires_gui


def _follower(**roe_fields):
    from spacemissionstudio.schema.scenario import (
        OrbitIC,
        RoeFormationConfig,
        RoeTargetConfig,
        SpacecraftConfig,
        StationKeepingConfig,
    )

    fields = dict(chief_spacecraft="chief",
                  targets=[RoeTargetConfig(0.0, [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]),
                           RoeTargetConfig(1.5, [0.25, 123.456789, -12.3456789, 300.0, 1.0e-3, 300.0])])  # [day], [m]
    fields.update(roe_fields)
    return SpacecraftConfig(
        name="follower",
        orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0]),
        station_keeping=StationKeepingConfig(target_altitude_km=550.0, deadband_km=1.5, thrust_n=0.015,
                                             isp_s=1550.0, propellant_kg=2.5),
        roe_formation=RoeFormationConfig(**fields),
    )


def test_an_roe_formation_round_trips(qtbot):
    """Every field of an existing formation, the continuous law and
    non-default tolerances included, comes back out unchanged."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    existing = _follower(control_law="continuous", tolerance_m=[1.0, 15.0, 5.0, 6.0], correction_window_days=2.0,
                         max_drift_m=50.0, max_burn_fraction_of_orbit=0.05, continuous_gain=1000.0,
                         target_refresh_s=300.0, differential_drag=False, drag_estimate_window_days=2.5)
    dialog = SpacecraftEditorDialog(config=existing, other_spacecraft_names=["chief"])
    qtbot.addWidget(dialog)
    assert dialog.roe_formation_group.isChecked()
    assert dialog.roe_chief_spacecraft_combo.currentData() == "chief"
    assert dialog.to_dataclass().roe_formation == existing.roe_formation


def test_the_form_defaults_to_no_formation(qtbot):
    """A new spacecraft has no ROE formation."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(other_spacecraft_names=["chief"])
    qtbot.addWidget(dialog)
    assert not dialog.roe_formation_group.isChecked()
    assert dialog.to_dataclass().roe_formation is None


def test_a_stale_chief_stays_visible(qtbot):
    """A chief that is no longer in the scenario is kept and named, not
    swapped for the first spacecraft in the list."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(config=_follower(chief_spacecraft="gone"), other_spacecraft_names=["chief"])
    qtbot.addWidget(dialog)
    assert dialog.roe_chief_spacecraft_combo.currentData() == "gone"
    assert "not found" in dialog.roe_chief_spacecraft_combo.currentText()
    assert dialog.to_dataclass().roe_formation.chief_spacecraft == "gone"


def test_no_selectable_chief_is_refused(qtbot):
    """With no other spacecraft, a checked formation cannot be saved."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import ScenarioValidationError

    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    dialog.station_keeping_group.setChecked(True)
    dialog.roe_formation_group.setChecked(True)
    with pytest.raises(ScenarioValidationError, match="no chief spacecraft is selectable"):
        dialog.to_dataclass()


def test_a_cell_that_is_not_a_number_is_named(qtbot):
    """A target cell that does not parse is refused with its row and
    column."""
    from PySide6.QtWidgets import QTableWidgetItem

    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import ScenarioValidationError

    dialog = SpacecraftEditorDialog(config=_follower(), other_spacecraft_names=["chief"])
    qtbot.addWidget(dialog)
    dialog.roe_targets.table.setItem(1, 2, QTableWidgetItem("far"))
    with pytest.raises(ScenarioValidationError, match=r"ROE target row 2: a·δλ \[m\] 'far' is not a number"):
        dialog.to_dataclass()


def test_the_safe_helper_adds_parallel_e_and_i_vectors(qtbot):
    """The helper appends a target a day after the last one, with the
    requested along-track offset and parallel e/i vectors of the requested
    sizes, and shows its safety margin."""
    from spacemissionstudio.gui.roe_formation_editor import RoeTargetTableWidget
    from spacemissionstudio.schema.scenario import RoeTargetConfig

    table = RoeTargetTableWidget()
    qtbot.addWidget(table)
    table.from_list([RoeTargetConfig(0.0, [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0])])
    table.safe_along_m.setValue(100.0)  # [m]
    table.safe_radial_m.setValue(200.0)  # [m]
    table.safe_cross_m.setValue(400.0)  # [m]
    table.safe_phase_deg.setValue(90.0)  # [deg]
    table.add_safe_formation()
    added = table.to_list()[-1]
    assert added.start_day == 1.0
    assert added.roe_m == [0.0, 100.0, 0.0, 200.0, 0.0, 400.0]
    assert "closest radial/cross-track approach 200.0 m" in table.margin_label.text()


def test_crossing_orbits_are_flagged(qtbot):
    """A target with perpendicular e/i vectors has a zero margin and says
    it is not passively safe."""
    from spacemissionstudio.gui.roe_formation_editor import RoeTargetTableWidget
    from spacemissionstudio.schema.scenario import RoeTargetConfig

    table = RoeTargetTableWidget()
    qtbot.addWidget(table)
    table.from_list([RoeTargetConfig(0.0, [0.0, 0.0, 0.0, 300.0, 300.0, 0.0])])
    assert "not passively safe" in table.margin_label.text()


def test_only_the_chosen_laws_settings_are_shown(qtbot):
    """The impulsive law shows its tolerances and drift settings; the
    continuous law shows its gain and refresh instead."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(config=_follower(), other_spacecraft_names=["chief"])
    qtbot.addWidget(dialog)
    impulsive = (dialog.roe_tolerance_m, dialog.roe_correction_window_days, dialog.roe_max_drift_m,
                 dialog.roe_max_burn_fraction_of_orbit, dialog.roe_differential_drag,
                 dialog.roe_drag_estimate_window_days)
    continuous = (dialog.roe_continuous_gain, dialog.roe_target_refresh_s)
    assert all(not w.isHidden() for w in impulsive) and all(w.isHidden() for w in continuous)
    dialog.roe_control_law_combo.setCurrentIndex(dialog.roe_control_law_combo.findData("continuous"))
    assert all(w.isHidden() for w in impulsive) and all(not w.isHidden() for w in continuous)


def test_the_drag_window_follows_the_compensation_switch(qtbot):
    """The estimate window can only be edited while differential drag is
    compensated; a new formation compensates it."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(config=_follower(), other_spacecraft_names=["chief"])
    qtbot.addWidget(dialog)
    assert dialog.roe_differential_drag.isChecked()
    assert dialog.roe_drag_estimate_window_days.isEnabled()
    dialog.roe_differential_drag.setChecked(False)
    assert not dialog.roe_drag_estimate_window_days.isEnabled()
    assert dialog.to_dataclass().roe_formation.differential_drag is False


def test_a_problem_names_the_form_label(qtbot):
    """A validation message about the formation reads with the form's
    titles, not the field codes."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(other_spacecraft_names=["chief"])
    qtbot.addWidget(dialog)
    assert dialog.problem_text("roe_formation.correction_window_days must be a finite number > 0") \
        == "ROE formation: Correction window [days] must be a finite number > 0"
