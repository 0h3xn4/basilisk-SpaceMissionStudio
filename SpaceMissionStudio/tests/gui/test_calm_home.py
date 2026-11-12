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

"""Calm by default (the owner, 2026-11-12): Home shows Home, the status
bar shows what needs attention, repeated notes are said once, and the
formation dialog names what its numbers do."""

import pytest

pytestmark = pytest.mark.requires_gui


@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    w.resize(1600, 900)
    w.show()
    qtbot.waitExposed(w)
    return w


def test_home_puts_the_panels_aside_and_gives_them_back(window):
    window.shell.show_area("scenario")
    window.side_dock.show()
    window.problems_dock.show()
    window.shell.show_area("home")
    assert not window.side_dock.isVisible() and not window.problems_dock.isVisible()
    window.shell.show_area("scenario")
    assert window.side_dock.isVisible() and window.problems_dock.isVisible()


def test_a_card_shows_its_title_and_kind_and_its_buttons_when_picked(window):
    home = window.load_scenario_widget
    card = home.cards[3]
    assert card.title_label.isVisibleTo(card) and card.type_label.isVisibleTo(card)
    assert not card.orbit_label.isVisibleTo(card) and not card.line_label.isVisibleTo(card)
    assert not card.buttons_shown()
    card.selected.emit(card)
    assert card.buttons_shown()
    home.cards[4].selected.emit(home.cards[4])
    assert not card.buttons_shown() and home.cards[4].buttons_shown()


def test_the_details_fold_the_headed_parts(window):
    from spacemissionstudio.gui.load_scenario_widget import split_description

    gist, parts = split_description("One gist.\n\nWhat to look at:\n- a\n- b\n\nTry changing:\n- c")
    assert gist == "One gist." and [title for title, _body in parts] == ["What to look at", "Try changing"]
    home = window.load_scenario_widget
    card = home.card("22 - Starter: your first LEO satellite")
    card.selected.emit(card)
    assert home.folds and not any(fold.is_open() for fold in home.folds)
    home.folds[0].button.click()
    assert home.folds[0].is_open() and home.folds[0].body.isVisibleTo(home)


def test_the_status_bar_shows_what_needs_attention(window):
    items = window.status_items
    items._needs_attention.clear()
    items.set_details(False)
    assert items.problems_button.isVisibleTo(window)
    assert not items.basilisk_label.isVisibleTo(window) and not items.frames_label.isVisibleTo(window)
    items._attention(items.data_button, True)
    items._apply_visibility()
    assert items.data_button.isVisibleTo(window)
    window.status_details_action.setChecked(True)
    assert items.basilisk_label.isVisibleTo(window) and items.frames_label.isVisibleTo(window)


def test_a_note_shared_by_spacecraft_is_said_once():
    from spacemissionstudio.gui.mission_view_widget import grouped_notes

    notes = [f"sat-{i}: no attitude in this run; drawn aligned with the inertial axes" for i in range(14)]
    short, full = grouped_notes(notes + ["chief: model file missing", "plain note"])
    assert short == ["14 spacecraft: no attitude in this run; drawn aligned with the inertial axes.",
                     "chief: model file missing.", "plain note"]
    assert full[0].startswith("No attitude in this run; drawn aligned with the inertial axes: sat-0, sat-1")


def test_the_formation_dialog_names_what_each_element_does(qtbot):
    from PySide6.QtWidgets import QFormLayout, QLabel

    from spacemissionstudio.gui.roe_formation_dialog import RoeFormationDialog
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    chief = SpacecraftConfig(name="chief-1", dry_mass_kg=150.0, orbit=OrbitIC(
        type="classical_elements", semi_major_axis_km=6928.137, eccentricity=0.0005, inclination_deg=97.6,
        raan_deg=30.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))
    dialog = RoeFormationDialog(["chief-1"], spacecraft=[chief])
    qtbot.addWidget(dialog)
    form = dialog.roe_spins[0].parentWidget().layout()
    assert isinstance(form, QFormLayout)
    labels = [form.labelForField(box).text() for box in dialog.roe_spins]
    assert labels[0] == "Drift (a·δa)" and labels[5] == "Cross-track y (a·δiy)"
    assert all(box.suffix().strip() == "m" for box in dialog.roe_spins)
    headings = [w.text() for w in dialog.findChildren(QLabel) if w.property("role") == "heading"]
    assert "Cross-track motion" in headings and "distance" in dialog.roe_note.text()
