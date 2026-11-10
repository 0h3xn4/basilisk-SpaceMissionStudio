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
"""Tests for the spacecraft editor's "Optical navigation" group: an
existing configuration comes back out unchanged, a new spacecraft has
none, and a problem reads with the form's labels."""

import pytest

pytestmark = pytest.mark.requires_gui


def _spacecraft(**camera):
    from spacemissionstudio.schema.scenario import OpticalNavigationConfig, OrbitIC, SpacecraftConfig

    return SpacecraftConfig(name="probe", orbit=OrbitIC(type="cartesian", position_km=[18000, 0, 0],
                                                         velocity_km_s=[0, 1.5, 0]),
                            optical_navigation=OpticalNavigationConfig(**camera))


def test_optical_navigation_round_trips(qtbot):
    """Every field, none of them at its default, comes back out unchanged."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    existing = _spacecraft(field_of_view_deg=30.5, resolution_px=[1024, 768], camera_mrp_cb=[0.1, -0.2, 0.05],
                           measurement_interval_s=120.0, center_noise_px=0.25, radius_noise_px=0.75,
                           min_radius_px=8.0, max_phase_angle_deg=110.0, initial_position_sigma_m=5000.0,
                           initial_velocity_sigma_mps=2.5, process_noise_position_m=0.5,
                           process_noise_velocity_mps=2.0e-4, seed=42)
    dialog = SpacecraftEditorDialog(config=existing)
    qtbot.addWidget(dialog)
    assert dialog.optical_navigation_group.isChecked()
    assert dialog.to_dataclass().optical_navigation == existing.optical_navigation


def test_a_new_spacecraft_has_no_camera(qtbot):
    """Unchecked by default; checking it gives the schema's defaults."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import OpticalNavigationConfig

    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    assert not dialog.optical_navigation_group.isChecked()
    assert dialog.to_dataclass().optical_navigation is None
    dialog.optical_navigation_group.setChecked(True)
    assert dialog.to_dataclass().optical_navigation == OpticalNavigationConfig()


def test_a_problem_names_the_form_label(qtbot):
    """A validation message about the camera reads with the form's titles."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(config=_spacecraft())
    qtbot.addWidget(dialog)
    assert dialog.problem_text("optical_navigation.max_phase_angle_deg must be at most 180") \
        == "Optical navigation: Largest phase angle [deg] must be at most 180"
