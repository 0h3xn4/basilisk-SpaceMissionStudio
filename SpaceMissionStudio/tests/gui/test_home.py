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
"""Home (UI overhaul plan §7, M3): a card per template with its mission
type, orbit and one line read from the template file; the recent
scenarios; New blank scenario; Customize; the reference-data card that
replaced the start-up dialog. ``tests/conftest.py`` points the home folder
(and with it ``settings.ini``) at the test's own folder."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture
def home(qtbot):
    from spacemissionstudio.gui.load_scenario_widget import LoadScenarioWidget

    widget = LoadScenarioWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def window(qtbot):
    """A main window without the start-up question; closing it discards changes."""
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window._confirm_discard_unsaved = lambda: True
    yield window
    window._mark_clean()


def _scenario_file(tmp_path, name: str) -> Path:
    """A copy of template 01 at ``tmp_path / name``: a scenario of the user's own."""
    path = tmp_path / name
    path.write_text((_TEMPLATES / "01_two_body_circular_orbit.json").read_text(encoding="utf-8"), encoding="utf-8")
    return path


# -- the cards: what they say comes from the template files ------------------------

def test_every_template_has_a_card_with_its_type_orbit_and_first_sentence(home):
    """31 cards, in file order; each card's three lines are read from its
    template: the attitude mode, the central body and orbit, the first
    sentence of the description. Nothing else is shown."""
    from spacemissionstudio.gui.load_scenario_widget import first_sentence
    from spacemissionstudio.schema import load_scenario

    files = sorted(_TEMPLATES.glob("*.json"))
    assert len(files) == 31
    assert [card.path for card in home.cards] == files
    for card, path in zip(home.cards, files):
        scenario = load_scenario(path)
        assert card.title_label.text() == scenario.name
        mode = "Orbit only" if scenario.simulation_mode == "orbit_only" else "Full attitude"
        assert card.type_label.text().startswith(mode)
        assert card.type_label.text().endswith(f"{len(scenario.spacecraft)} spacecraft")
        body = scenario.gravity.central_body.replace(" barycenter", "").title()
        assert card.orbit_label.text().startswith(body)
        line = card.line_label.text()
        assert line == first_sentence(scenario.description)
        assert scenario.description.replace("\n", " ").startswith(line[:40]) and 20 < len(line) < 260
        assert line.endswith((".", "!", "?"))


@pytest.mark.parametrize("prefix, mission_type, orbit", [
    ("01", "Orbit only · 1 spacecraft", "Earth · 400 km circular · i 97.0 deg"),
    ("02", "Orbit only · 1 spacecraft", "Earth · 941 × 35095 km · i 28.5 deg"),
    ("03", "Orbit only · 1 spacecraft", "Earth · 35788 km circular · i 0.2 deg"),
    ("04", "Orbit only · 6 spacecraft", "Earth · 700 km circular · i 53.0 deg"),
    ("07", "Full attitude · Sun pointing · 1 spacecraft", "Earth · 550 km circular · i 97.6 deg · Sun-synchronous"),
    ("19", "Full attitude · 1 spacecraft", "Earth · 550 km circular · i 97.6 deg · Sun-synchronous"),
    ("30", "Orbit only · 1 spacecraft", "Mars · 11004 × 18204 km · i 30.0 deg"),
    ("31", "Orbit only · 1 spacecraft", "Eros · 35 km from the centre · i 90.0 deg"),
])
def test_a_cards_type_and_orbit(home, prefix, mission_type, orbit):
    """Examples: a circular LEO, an eccentric orbit as periapsis and
    apoapsis altitudes, GEO, a constellation, a Sun-synchronous orbit with
    its pointing mode (template 19 points by its comms link, not an
    attitude mode, so none is named), Mars (its radius) and Eros (no single
    radius: from the centre)."""
    card = next(card for card in home.cards if card.name.startswith(prefix))
    assert card.type_label.text() == mission_type
    assert card.orbit_label.text() == orbit


def test_the_first_sentence_ends_at_a_full_stop_followed_by_a_space():
    """A sentence ends at ". " even before a lower-case word (template 29's
    "Sun-synchronous. follower-1"), not inside "e = 0.7" or after "e.g."."""
    from spacemissionstudio.gui.load_scenario_widget import first_sentence

    assert first_sentence("At 550 km, Sun-synchronous. follower-1 starts behind.") == "At 550 km, Sun-synchronous."
    assert first_sentence("An orbit (e = 0.7), with drag, e.g. a GTO. More.") == "An orbit (e = 0.7), with drag, e.g. a GTO."
    assert first_sentence("One line\nwrapped. Next.\n\nWhat to look at:\n- x") == "One line wrapped."
    assert first_sentence("") == ""


def test_the_filter_narrows_the_cards_and_says_how_many(home, qtbot):
    """Typing narrows the cards to those whose text has every word; the
    count says "n of 31"; no match shows the empty state."""
    home.show()
    home.filter_edit.setText("monte carlo")
    shown = home.grid.visible_cards()
    assert {card.name[:2] for card in shown} == {"09", "25"}
    assert home.templates_count.text() == "2 of 31"
    home.filter_edit.setText("no such template anywhere")
    assert home.grid.visible_cards() == [] and home.grid.empty_label.isVisible()
    home.filter_edit.clear()
    assert len(home.grid.visible_cards()) == 31 and home.templates_count.text() == "31"


def test_the_cards_fill_the_width_in_columns(home, qtbot):
    """As many columns as the width holds, never a card narrower than its
    least width; the cards follow a resize."""
    from spacemissionstudio.gui.load_scenario_widget import CARD_MIN_WIDTH_PX

    home.resize(1800, 900)  # [px]
    home.show()
    qtbot.waitUntil(lambda: home.grid.columns() >= 3)
    wide = home.grid.columns()
    assert all(card.width() >= CARD_MIN_WIDTH_PX for card in home.cards)
    home.resize(900, 900)  # [px]
    qtbot.waitUntil(lambda: home.grid.columns() < wide)
    assert all(card.width() >= CARD_MIN_WIDTH_PX for card in home.cards)


def test_the_keyboard_reaches_the_cards_once_and_moves_with_the_arrows(home, qtbot):
    """One Tab stop for all the cards; Right and Down move the selection
    (Down by a row), Home and End to the ends; Enter opens the card."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    home.resize(1800, 900)  # [px]
    with qtbot.waitActive(home):
        home.show()
        home.activateWindow()
    qtbot.waitUntil(lambda: home.grid.columns() >= 3)
    tab_stops = [card for card in home.cards if card.focusPolicy() & Qt.FocusPolicy.TabFocus]
    assert tab_stops == [home.cards[0]]
    home.cards[0].setFocus()
    qtbot.waitUntil(lambda: home.selected_card() is home.cards[0])  # a card selects itself on taking the focus
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Right)
    assert home.selected_card() is home.cards[1] and QApplication.focusWidget() is home.cards[1]
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)
    assert home.selected_card() is home.cards[1 + home.grid.columns()]
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_End)
    assert home.selected_card() is home.cards[-1]
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Home)
    assert home.selected_card() is home.cards[0]
    assert [card for card in home.cards if card.focusPolicy() & Qt.FocusPolicy.TabFocus] == [home.cards[0]]
    opened = []
    home.path_chosen.connect(opened.append)
    qtbot.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
    assert opened == [home.cards[0].path]


def test_a_cards_open_button_opens_that_template(home):
    """A card's Open hands on its own file, whatever is selected."""
    home.select(0)
    opened = []
    home.path_chosen.connect(opened.append)
    home.cards[4].open_button.click()
    assert opened == [home.cards[4].path]


def test_the_details_customize_opens_the_wizard_for_the_selected_template(home, monkeypatch):
    """Customize... in the details runs the wizard of the selected card's
    template and hands on its result."""
    from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard

    assert not home.customize_template_button.isEnabled()
    seen = []

    def accept(wizard):
        seen.append(wizard)
        return TemplateCustomizeWizard.DialogCode.Accepted

    monkeypatch.setattr(TemplateCustomizeWizard, "exec", accept)
    emitted = []
    home.scenario_customized.connect(emitted.append)
    home.select("18 - LEO station-keeping")
    assert home.customize_template_button.isEnabled()
    home.customize_template_button.click()
    assert len(seen) == 1 and [s.name for s in emitted] == ["18 - LEO station-keeping"]


def test_customize_opens_the_wizard_from_the_window(window, monkeypatch):
    """In the window, a card's Customize... opens the wizard, and its result
    opens in the Scenario area without a file (Save As writes one)."""
    from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard

    monkeypatch.setattr(TemplateCustomizeWizard, "exec", lambda self: TemplateCustomizeWizard.DialogCode.Accepted)
    home = window.load_scenario_widget
    home.card("22 - Starter: your first LEO satellite").customize_button.click()
    assert window.current_view() is window.scenario_editor
    assert window._current_path is None
    assert window.scenario_editor.to_scenario().name == "22 - Starter: your first LEO satellite"


def test_a_selected_card_is_marked_and_the_details_follow(home):
    """One card is selected at a time; the details show its title, its two
    summary lines and the whole description."""
    first = home.select(0)
    second = home.select(5)
    assert second.is_selected() and not first.is_selected()
    assert home.description_title.text() == second.name
    assert home.description_meta.text() == f"{second.type_label.text()}\n{second.orbit_label.text()}"
    assert "What to look at" in home.description_label.text()
    assert not home.details_empty.isVisible()


# -- recent scenarios -----------------------------------------------------------------

def test_recent_scenarios_start_empty_with_open_beside_them(home, qtbot):
    """No recent scenario: the empty state says what will be listed, with
    Open a scenario file... under it."""
    home.show()
    assert home.recent_list.count() == 0
    assert home.recent_empty.isVisible() and not home.recent_list.isVisible()
    assert home.browse_button.isVisible()
    assert not home.clear_recent_button.isVisible()


def test_opening_and_saving_a_file_lists_it_first(window, tmp_path, monkeypatch):
    """A scenario opened or saved goes to the top of the list, once."""
    from PySide6.QtWidgets import QFileDialog

    first, second = _scenario_file(tmp_path, "first.json"), _scenario_file(tmp_path, "second.json")
    home = window.load_scenario_widget
    assert window.open_path(first)
    assert window.open_path(second)
    assert home.recent_paths() == [second.resolve(), first.resolve()]
    saved = tmp_path / "saved.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(saved), "")))
    window.on_save_as()
    assert home.recent_paths() == [saved.resolve(), second.resolve(), first.resolve()]
    assert window.open_path(first)
    assert home.recent_paths() == [first.resolve(), saved.resolve(), second.resolve()]


def test_a_template_opened_is_not_a_recent_scenario(window):
    """The built-in templates are on the cards; opening one does not add it."""
    assert window.open_path(_TEMPLATES / "01_two_body_circular_orbit.json")
    assert window.load_scenario_widget.recent_paths() == []


def test_the_list_keeps_the_last_ten(tmp_path):
    """Eleven files opened: the oldest drops off. Kept in settings.ini."""
    from spacemissionstudio.gui import recent_files

    paths = [_scenario_file(tmp_path, f"s{index:02d}.json") for index in range(11)]
    for path in paths:
        recent_files.remember(path)
    assert recent_files.MAX_RECENT == 10
    assert recent_files.recent() == [path.resolve() for path in reversed(paths[1:])]
    assert (Path.home() / ".spacemissionstudio" / "settings.ini").is_file()
    recent_files.remember(paths[5])
    assert recent_files.recent()[0] == paths[5].resolve() and len(recent_files.recent()) == 10
    recent_files.clear()
    assert recent_files.recent() == []


def test_a_single_recent_file_reads_back_as_a_list(tmp_path):
    """An INI list of one entry reads back as a string; it is still one path."""
    from spacemissionstudio.gui import recent_files

    path = _scenario_file(tmp_path, "only.json")
    recent_files.remember(path)
    assert recent_files.recent() == [path.resolve()]


def test_a_missing_file_is_marked_and_not_opened(home, tmp_path, qtbot, reported):
    """A recent file that is gone says "(missing)" with a warning icon; Enter
    on it opens nothing and says why."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui import recent_files

    present, gone = _scenario_file(tmp_path, "present.json"), _scenario_file(tmp_path, "gone.json")
    recent_files.remember(present)
    recent_files.remember(gone)
    gone.unlink()
    home.refresh_recent()
    texts = [home.recent_list.item(row).text() for row in range(home.recent_list.count())]
    assert texts == ["gone.json (missing)", "present.json"]
    assert home.recent_list.item(0).data(Qt.ItemDataRole.UserRole + 1) is True
    assert not home.recent_list.item(0).icon().isNull()
    assert "moved or deleted" in home.recent_list.item(0).toolTip()
    opened = []
    home.path_chosen.connect(opened.append)
    home.recent_list.itemActivated.emit(home.recent_list.item(0))
    assert opened == []
    assert reported and reported[-1][1] == "warning" and "missing" in reported[-1][0]
    home.recent_list.itemActivated.emit(home.recent_list.item(1))
    assert opened == [present.resolve()]


def test_delete_takes_a_scenario_off_the_list_and_clear_empties_it(home, tmp_path, qtbot):
    """Delete forgets the current entry (the file stays); Clear empties the
    list and shows the empty state."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui import recent_files

    paths = [_scenario_file(tmp_path, f"{name}.json") for name in ("a", "b", "c")]
    for path in paths:
        recent_files.remember(path)
    home.show()
    home.refresh_recent()
    home.recent_list.setCurrentRow(1)
    qtbot.keyClick(home.recent_list, Qt.Key.Key_Delete)
    assert home.recent_paths() == [paths[2].resolve(), paths[0].resolve()]
    assert all(path.is_file() for path in paths)
    home.clear_recent_button.click()
    assert home.recent_paths() == [] and recent_files.recent() == []
    assert home.recent_empty.isVisible()


def test_a_recent_scenario_opens_in_the_window(window, tmp_path):
    """Enter on a recent scenario opens it in the Scenario area."""
    path = _scenario_file(tmp_path, "mine.json")
    assert window.open_path(path)
    window.on_new()
    home = window.load_scenario_widget
    home.recent_list.itemActivated.emit(home.recent_list.item(0))
    assert window._current_path == path.resolve() or window._current_path == path
    assert window.current_view() is window.scenario_editor


# -- the reference-data card ----------------------------------------------------------

def test_the_start_up_question_is_a_card_on_home_not_a_dialog(qtbot):
    """A window that asks at start-up shows the card on Home (any modal
    dialog would fail the test: tests/gui/conftest.py); Not now hides it and
    fetches nothing."""
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui import startup_fetch_dialog
    from spacemissionstudio.gui.main_window import MainWindow

    started = []
    real_start = startup_fetch_dialog.StartupFetchWorker.start
    startup_fetch_dialog.StartupFetchWorker.start = lambda self: started.append(self)
    try:
        window = MainWindow(prompt_startup_fetch=True, check_autosave_recovery=False)
        qtbot.addWidget(window)
        window.show()
        card = window.load_scenario_widget.reference_card
        qtbot.waitUntil(card.isVisible)
        assert window.shell.current_area() == "home"
        assert len(card.checkboxes) == 3 and card.fetch_button.isEnabled()
        card.skip_button.click()
        QApplication.processEvents()
        assert not card.isVisible() and started == []
    finally:
        startup_fetch_dialog.StartupFetchWorker.start = real_start


def test_the_card_offers_what_the_dialog_offered(home):
    """The card's items and defaults are the dialog's (one function makes both)."""
    from spacemissionstudio.gui.startup_fetch_dialog import StartupFetchDialog

    home.reference_card.ask()
    dialog = StartupFetchDialog()
    try:
        card_items = [(box.text(), box.isChecked()) for box in home.reference_card.checkboxes]
        dialog_items = [(box.text(), box.isChecked()) for box in (
            dialog.kernels_checkbox, dialog.space_weather_checkbox, dialog.earth_orientation_checkbox)]
        assert card_items == dialog_items
    finally:
        dialog.deleteLater()


def test_fetch_now_runs_in_a_worker_and_reports_the_summary(home, qtbot, monkeypatch):
    """Fetch now starts the worker with the ticked items, shows that it runs
    (its controls disabled) and, when done, reports one line per item as a
    toast and hides the card."""
    from spacemissionstudio.gui import startup_fetch_dialog as module

    shown = []
    monkeypatch.setattr(module, "report", lambda parent, text, kind="error": shown.append((kind, text)))
    monkeypatch.setattr(module.StartupFetchWorker, "_fetch_kernels", staticmethod(lambda: (True, "2/2 available.")))
    monkeypatch.setattr(module.StartupFetchWorker, "_fetch_space_weather",
                        staticmethod(lambda: (False, "no network")))
    home.show()
    card = home.reference_card
    card.ask()
    card.checkboxes[2].setChecked(False)  # not the Earth orientation files
    assert card.selected() == (True, True, False)
    with qtbot.waitSignal(card.finished, timeout=10000):
        card.fetch_button.click()
        assert not card.fetch_button.isEnabled() and card.progress.isVisible()
    assert not card.isVisible() and not card.is_running()
    assert len(shown) == 1
    kind, text = shown[0]
    assert kind == "warning"
    assert "Support-data kernels: 2/2 available." in text and "Space weather: could not fetch (no network)" in text
    assert "Earth orientation" not in text


def test_fetch_now_with_nothing_ticked_fetches_nothing(home, monkeypatch):
    """Every item unticked: Fetch now only hides the card."""
    from spacemissionstudio.gui import startup_fetch_dialog as module

    monkeypatch.setattr(module.StartupFetchWorker, "start", lambda self: pytest.fail("nothing was ticked"))
    card = home.reference_card
    card.ask()
    for box in card.checkboxes:
        box.setChecked(False)
    card.fetch_button.click()
    assert not card.isVisible() and not card.is_running()


# -- the page in the window -------------------------------------------------------------

def test_new_blank_scenario_and_open_are_on_home(window, monkeypatch):
    """New blank scenario makes the blank scenario; Open a scenario file...
    opens the picked file."""
    from PySide6.QtWidgets import QFileDialog

    home = window.load_scenario_widget
    home.start_from_scratch.button.click()
    assert window.current_view() is window.scenario_editor and window._current_path is None
    picked = _TEMPLATES / "18_leo_station_keeping.json"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(picked), "")))
    home.browse_button.click()
    assert window._current_path == picked


def test_the_reference_data_card_takes_only_the_height_it_needs(home, qtbot):
    """Above the columns, the card is as tall as its contents; the columns
    take the rest of the page (the harness found the card stretched)."""
    from PySide6.QtWidgets import QApplication

    home.resize(1400, 1000)  # [px]
    home.show()
    home.reference_card.ask()
    QApplication.processEvents()
    card = home.reference_card
    qtbot.waitUntil(lambda: card.height() > 0)
    assert card.height() <= card.sizeHint().height() + 1  # [px]
    assert home.splitter.height() > home.height() - card.height() - 40  # [px] the band's margin and spacing


def test_the_card_text_follows_a_live_theme_switch(home, restored_theme):
    """The cards paint their text themselves; after a switch to dark it is
    drawn in the dark theme's colours (CLAUDE.md, "Live theme switch")."""
    from PySide6.QtGui import QColor

    from spacemissionstudio.gui.theme import TOKENS, apply_theme

    def inks(widget):
        image = widget.grab().toImage()
        return {image.pixelColor(x, y).name() for y in range(image.height()) for x in range(image.width())}

    home.resize(1400, 900)  # [px]
    home.show()
    card = home.cards[0]
    apply_theme(restored_theme, "light")
    assert QColor(TOKENS["text.primary"]).name() in inks(card.title_label)
    apply_theme(restored_theme, "dark")
    assert QColor(TOKENS["text.primary"]).name() in inks(card.title_label)
    assert QColor(TOKENS["text.secondary"]).name() in inks(card.type_label)
