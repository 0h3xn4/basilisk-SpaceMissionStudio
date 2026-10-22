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

"""A mission from scratch (gui.mission_guide): the Templates page's first
choice, a blank scenario in Orbit only, the Scenario page's guide to a
first run and to the rest of the tool, and the Spacecraft page's empty
state."""

import pytest


@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    # Teardown closes the window; never wait on an unanswered prompt.
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


def _add_spacecraft(window):
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    window.scenario_editor.spacecraft_list.from_list([
        SpacecraftConfig(name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                     velocity_km_s=[0, 7.5, 0]))])
    window.scenario_editor.changed.emit()


def _current_item(window):
    return window.scenario_editor.page_tree.tree.currentItem()


def test_the_templates_page_offers_a_blank_scenario_first(window, qtbot):
    """The Templates page opens with "Start from scratch" above the
    templates; its button makes a blank scenario and shows its Scenario
    page, in Orbit only."""
    page = window.load_scenario_widget
    layout = page.start_scroll.widget().layout()  # Home's first column, Start (M3)
    assert page.splitter.widget(0) is page.start_scroll
    assert layout.itemAt(0).widget() is page.start_from_scratch
    window.scenario_editor.simulation_mode_combo.setCurrentIndex(
        window.scenario_editor.simulation_mode_combo.findData("full_attitude"))
    page.start_from_scratch.button.click()
    assert window.current_view() is window.scenario_editor
    assert _current_item(window) is window.scenario_editor.scenario_item
    scenario = window.scenario_editor._draft_scenario()
    assert scenario.simulation_mode == "orbit_only" and scenario.spacecraft == []


def test_a_blank_scenario_starts_in_orbit_only_on_start_up_and_after_new(window):
    """Start-up and File > New give the same blank scenario: no spacecraft,
    Orbit only (the user's decision of 2026-10-21)."""
    editor = window.scenario_editor
    assert editor.simulation_mode_combo.currentData() == "orbit_only"
    editor.simulation_mode_combo.setCurrentIndex(editor.simulation_mode_combo.findData("full_attitude"))
    window.on_new()
    assert editor.simulation_mode_combo.currentData() == "orbit_only"


def test_the_guide_shows_each_step_and_follows_the_scenario(window):
    """A blank scenario needs a spacecraft and cannot run yet; with one it
    can, and ground stations stay optional until one is added."""
    guide = window.scenario_editor.mission_guide
    badges = guide.step_badges
    assert badges["spacecraft"].text() == "Needed" and badges["spacecraft"].property("badge") == "caution"
    assert badges["ground_stations"].text() == "Optional"
    assert badges["run"].text().startswith("Not yet")
    _add_spacecraft(window)
    assert badges["spacecraft"].text() == "Done: 1" and badges["spacecraft"].property("badge") == "normal"
    assert badges["run"].text() == "Ready"


def test_the_guide_says_orbit_only_is_a_start_and_offers_full_attitude(window):
    """In Orbit only the guide says what the mode is and that it is not the
    limit, and offers Full attitude; its button switches the mode, and the
    wording then describes Full attitude."""
    guide = window.scenario_editor.mission_guide
    assert "starting point, not a limit" in guide.mode_labels[1].text()
    button = guide.more_buttons["Full attitude"]
    assert not button.isHidden()
    button.click()
    assert window.scenario_editor.simulation_mode_combo.currentData() == "full_attitude"
    assert "Full attitude" in guide.mode_labels[0].text() and button.isHidden()


def test_there_is_more_names_every_area_of_the_tool_with_a_way_there(window):
    """The capability list covers attitude, the mission sequence,
    constellations and formations, Monte Carlo, the analyses, other
    central bodies and the templates, each with a button."""
    guide = window.scenario_editor.mission_guide
    assert set(guide.more_buttons) == {"Full attitude", "Manoeuvres and a mission timeline",
                                       "Constellations and formations", "Uncertainty", "Analyses",
                                       "Other worlds", "Worked examples"}


@pytest.mark.parametrize("title, item", [
    ("Manoeuvres and a mission timeline", "mission_sequence_item"),
    ("Constellations and formations", "spacecraft_item"),
    ("Uncertainty", "monte_carlo_item"),
    ("Other worlds", "environment_item"),
])
def test_the_guide_buttons_open_the_editor_pages(window, title, item):
    """Each "There is more" button opens the page where that is set."""
    window.scenario_editor.mission_guide.more_buttons[title].click()
    assert _current_item(window) is getattr(window.scenario_editor, item)


def test_the_guide_buttons_open_the_analyses_and_the_templates(window):
    """Analyses opens End of Life, the first analysis (the Run area);
    Worked examples the Templates (Home). Both are pages of the main
    window, not the editor."""
    guide = window.scenario_editor.mission_guide
    guide.more_buttons["Analyses"].click()
    assert window.current_view() is window.lifetime_widget
    guide.more_buttons["Worked examples"].click()
    assert window.current_view() is window.load_scenario_widget


@pytest.mark.parametrize("key, item", [("environment", "environment_item"), ("spacecraft", "spacecraft_item"),
                                       ("ground_stations", "ground_station_item")])
def test_the_step_buttons_open_their_pages(window, key, item):
    """The steps' "Go to" buttons open the Environment, Spacecraft and
    Ground stations pages."""
    window.scenario_editor.mission_guide.step_buttons[key].click()
    assert _current_item(window) is getattr(window.scenario_editor, item)


def test_the_spacecraft_page_has_an_empty_state_and_selection_bound_buttons(window):
    """With no spacecraft the list's place says what to do first; Edit and
    Remove wait for a selection."""
    spacecraft_list = window.scenario_editor.spacecraft_list
    assert not spacecraft_list.empty_label.isHidden() and spacecraft_list.list_widget.isHidden()
    assert "Add..." in spacecraft_list.empty_label.text()
    assert not spacecraft_list.edit_button.isEnabled() and not spacecraft_list.remove_button.isEnabled()
    _add_spacecraft(window)
    assert spacecraft_list.empty_label.isHidden() and not spacecraft_list.list_widget.isHidden()
    spacecraft_list.list_widget.setCurrentRow(0)
    assert spacecraft_list.edit_button.isEnabled() and spacecraft_list.remove_button.isEnabled()


def test_the_guide_is_open_for_a_blank_scenario_and_folded_for_an_opened_one(window):
    """A blank scenario shows the whole guide; an opened template keeps its
    description in view with the guide folded, and Show guide opens it."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    guide = window.scenario_editor.mission_guide
    assert not guide.body.isHidden()
    assert window.open_path(TEMPLATES_DIR / "22_starter_first_leo_satellite.json")
    assert guide.body.isHidden() and guide.toggle_button.text() == "Show guide"
    guide.toggle_button.click()
    assert not guide.body.isHidden() and guide.toggle_button.text() == "Hide guide"
    window.on_new()
    assert not guide.body.isHidden()
