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

"""Tests for the small-body parts of the forms: Eros and its shape's
gravity in the gravity form, and the spacecraft editor's "Landmark
navigation" group."""

import pytest

pytestmark = pytest.mark.requires_gui


def _spacecraft(**camera):
    from spacemissionstudio.schema.scenario import LandmarkNavigationConfig, OrbitIC, SpacecraftConfig

    return SpacecraftConfig(name="probe", orbit=OrbitIC(type="cartesian", position_km=[35, 0, 0],
                                                         velocity_km_s=[0, 0.0035, 0]),
                            landmark_navigation=LandmarkNavigationConfig(**camera))


def test_landmark_navigation_round_trips(qtbot):
    """Every field, none of them at its default, comes back out unchanged."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    existing = _spacecraft(landmark_count=250, field_of_view_deg=22.5, resolution_px=[2048, 1536],
                           camera_mrp_cb=[0.1, -0.2, 0.05], measurement_interval_s=300.0, pixel_noise_px=0.4,
                           min_sun_elevation_deg=5.0, initial_position_sigma_m=250.0,
                           initial_velocity_sigma_mps=0.02, process_noise_mps2_per_sqrt_hz=3.0e-9, seed=42)
    dialog = SpacecraftEditorDialog(config=existing)
    qtbot.addWidget(dialog)
    assert dialog.landmark_navigation_group.isChecked()
    assert dialog.to_dataclass().landmark_navigation == existing.landmark_navigation


def test_a_new_spacecraft_has_no_landmark_camera(qtbot):
    """Unchecked by default; checking it gives the schema's defaults."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema.scenario import LandmarkNavigationConfig

    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    assert dialog.to_dataclass().landmark_navigation is None
    dialog.landmark_navigation_group.setChecked(True)
    assert dialog.to_dataclass().landmark_navigation == LandmarkNavigationConfig()


def test_a_landmark_problem_names_the_form_label(qtbot):
    """A validation message about the landmark camera reads with the form's titles."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(config=_spacecraft())
    qtbot.addWidget(dialog)
    assert dialog.problem_text("landmark_navigation.landmark_count must be a whole number from 1 to 1000") \
        == "Landmark navigation: Landmarks must be a whole number from 1 to 1000"


def test_the_gravity_form_offers_eros_and_its_shapes_gravity(qtbot):
    """Eros is a central body (not a third body); the shape's gravity can
    be chosen only for it and comes back out in the gravity settings."""
    from pathlib import Path

    from spacemissionstudio.gui.propagation_setup_dialog import PropagationSetupDialog
    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
    scenario = load_scenario(templates / "01_two_body_circular_orbit.json")
    dialog = PropagationSetupDialog(scenario.gravity, scenario.sim_settings, scenario.space_weather)
    qtbot.addWidget(dialog)
    assert not dialog.polyhedral_gravity_check.isEnabled()
    dialog.central_body_combo.setCurrentText("eros")
    assert dialog.polyhedral_gravity_check.isEnabled()
    dialog.polyhedral_gravity_check.setChecked(True)
    third = [dialog.third_body_list.item(i).text() for i in range(dialog.third_body_list.count())]
    assert "eros" not in third and "sun" in third
    gravity = dialog.to_gravity()
    assert (gravity.central_body, gravity.polyhedral_gravity) == ("eros", True)
    dialog.central_body_combo.setCurrentText("earth")
    assert not dialog.polyhedral_gravity_check.isChecked() and not dialog.to_gravity().polyhedral_gravity
