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

"""The menu bar (gui.menu_bar), the drop-down lists of every combo box
(gui.theme.combo), dialogs that fit their text (gui.theme.dialogs), and the optional reference files that are not
downloaded (engine.reference_data)."""

import pytest


@pytest.fixture
def window(qtbot, monkeypatch):
    """A main window as it starts: on Home, with no scenario open."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


def _items(menu):
    """(text without ampersands, action) of a menu's items, submenus by title."""
    return [(action.text().replace("&", ""), action) for action in menu.actions() if not action.isSeparator()]


# -- the menu bar ----------------------------------------------------------------------

def test_the_menu_bar_has_the_usual_menus_in_order(window):
    assert window.menuBar().isVisibleTo(window)
    assert [text for text, _action in _items(window.menuBar())] == [
        "File", "Edit", "View", "Go", "Run", "Tools", "Help"]


def test_every_command_is_in_exactly_one_menu(window):
    """Every registered command is placed once (a new command needs a
    place in gui.menu_bar.MENUS), and the menus hold the registry's own
    actions, so text, shortcut and enabled state are shared."""
    from spacemissionstudio.gui.menu_bar import command_ids

    placed = command_ids()
    assert len(placed) == len(set(placed)), "a command is in two menus"
    assert set(placed) == {command.id for command in window.commands}

    def actions(menu):
        found = []
        for action in menu.actions():
            if action.menu() is not None:
                found.extend(actions(action.menu()))
            elif not action.isSeparator():
                found.append(action)
        return found

    in_menus = [action for menu in (a.menu() for a in window.menuBar().actions()) for action in actions(menu)]
    for command in window.commands:
        assert command.action in in_menus, command.id


def test_the_menus_put_the_commands_where_people_look_for_them(window):
    file_items = [text for text, _action in _items(window.menus["File"])]
    assert file_items[:3] == ["New Scenario", "Open...", "Open Recent"] and file_items[-1] == "Quit"
    assert [text for text, _action in _items(window.menus["Edit"])] == ["Undo", "Redo", "Settings..."]
    assert "Time Cursor" in [text for text, _action in _items(window.menus["Go"])]
    assert [text for text, _action in _items(window.menus["Run Mode"])] == [
        "Single run", "Monte Carlo", "SIL (flight software in the loop)"]
    assert [text for text, _action in _items(window.menus["Help"])][0] == "User Manual"


def test_menu_items_follow_their_commands_state(window):
    """With nothing open, Save and Run are disabled in their menus too;
    New opens a scenario and they are enabled."""
    assert not window.commands.action("file.save").isEnabled()
    window.on_new()
    assert window.commands.action("run.run").isEnabled()
    save = dict(_items(window.menus["File"]))["Save"]
    assert save is window.commands.action("file.save") and save.isEnabled()


def test_edit_settings_opens_the_settings_area(window):
    window.commands.action("edit.settings").trigger()
    assert window.shell.current_area() == "settings"
    assert window.commands["edit.settings"].keys == "Ctrl+,"


def test_the_menu_bar_can_be_hidden_and_the_choice_is_kept(window, qtbot, monkeypatch):
    """View > Menu Bar hides it; the shortcuts still work (they are the
    window's); the layout keeps the choice; Reset Layout shows it again."""
    toggle = window.commands.action("view.menu_bar")
    assert toggle.isChecked()
    toggle.setChecked(False)
    assert not window.menuBar().isVisibleTo(window)
    window.commands.action("go.reports").trigger()
    assert window.shell.current_area() == "reports"  # its action is on the window, not only in the menu
    window._save_layout()
    window.menu_bar_action.setChecked(True)
    window._restore_layout()
    assert not window.menu_bar_action.isChecked() and not window.menuBar().isVisibleTo(window)
    window.reset_layout()
    assert window.menu_bar_action.isChecked() and window.menuBar().isVisibleTo(window)


def test_open_recent_lists_the_recent_files_and_opens_one(window, tmp_path):
    """File > Open Recent: the recent files still there, newest first, each
    opening its scenario; Clear the List empties it."""
    import shutil

    from spacemissionstudio.gui import recent_files
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    first = tmp_path / "first.json"
    second = tmp_path / "second & more.json"
    for path in (first, second):
        shutil.copy(TEMPLATES_DIR / "22_starter_first_leo_satellite.json", path)
    recent_files.remember(first)
    recent_files.remember(second)
    recent_files.remember(tmp_path / "gone.json")  # remembered, then not there: not listed
    menu = window.menus["Open Recent"]
    menu.aboutToShow.emit()
    files = [action for action in menu.actions() if action.data()]
    assert [action.text() for action in files] == ["&1 second && more.json", "&2 first.json"]
    files[1].trigger()
    assert window.scenario_open and window._current_path == first
    clear = next(action for action in menu.actions() if action.text() == "&Clear the List")
    clear.trigger()
    assert recent_files.recent() == []
    menu.aboutToShow.emit()
    assert [action.text() for action in menu.actions() if not action.isSeparator()][0] == "No recent scenarios"


def test_open_recent_says_so_when_the_file_has_gone(window, tmp_path, reported):
    from PySide6.QtGui import QAction

    action = QAction("gone")
    action.setData(str(tmp_path / "gone.json"))
    window._on_recent_menu(action)
    assert not window.scenario_open
    assert any("is missing" in message for message, _kind in reported)


# -- drop-down lists -------------------------------------------------------------------

@pytest.fixture
def themed(restored_theme):
    """The app's theme applied, as at start-up (its style prepares every
    combo box); the plain Fusion style back after the test."""
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(restored_theme, "light")
    yield restored_theme
    restored_theme.setStyle("Fusion")


def _combo(qtbot, count):
    from spacemissionstudio.gui.widgets import ComboBox

    combo = ComboBox()
    combo.addItems([f"series_{i:02d}" for i in range(count)])
    combo.resize(240, 32)
    qtbot.addWidget(combo)
    combo.show()
    return combo


def test_a_combo_box_list_has_roomy_rows_and_opens_below_the_field(qtbot, themed):
    from PySide6.QtWidgets import QStyle, QStyledItemDelegate

    from spacemissionstudio.gui.theme.combo import MAX_VISIBLE
    from spacemissionstudio.gui.theme.typography import CONTROL_HEIGHT

    combo = _combo(qtbot, 4)
    assert isinstance(combo.itemDelegate(), QStyledItemDelegate)
    assert combo.maxVisibleItems() == MAX_VISIBLE
    assert combo.style().styleHint(QStyle.StyleHint.SH_ComboBox_Popup, None, combo) == 0
    combo.showPopup()
    qtbot.waitUntil(lambda: combo.view().isVisible())
    assert combo.view().sizeHintForRow(0) >= CONTROL_HEIGHT["default"]
    popup = combo.view().window()
    assert popup.geometry().top() >= combo.mapToGlobal(combo.rect().bottomLeft()).y() - 1  # below, not over it
    combo.hidePopup()


def test_a_short_list_has_no_filter_field(qtbot, themed):
    from spacemissionstudio.gui.theme.combo import FILTER_MIN, filter_field

    combo = _combo(qtbot, FILTER_MIN - 1)
    combo.showPopup()
    qtbot.waitUntil(lambda: combo.view().isVisible())
    field = filter_field(combo.view())
    assert field is None or not field.isVisible()
    combo.hidePopup()


def test_typing_in_a_long_list_filters_it_and_enter_picks(qtbot, themed):
    """Keys typed in the open list go to its filter field: the list keeps
    the entries containing the text, the first is current; Down and Enter
    pick; closed and opened again, the whole list is back."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.theme.combo import filter_field

    combo = _combo(qtbot, 40)
    combo.setCurrentIndex(30)
    combo.showPopup()
    view = combo.view()
    qtbot.waitUntil(view.isVisible)
    field = filter_field(view)
    assert field is not None and field.isVisible() and field.placeholderText() == "Type to filter"
    qtbot.keyClicks(view, "3")
    assert field.text() == "3"
    shown = [view.model().index(row, 0).data() for row in range(combo.count()) if not view.isRowHidden(row)]
    assert shown == ["series_03", "series_13", "series_23", *[f"series_3{i}" for i in range(10)]]
    assert view.currentIndex().data() == "series_03"
    qtbot.keyClick(view, Qt.Key.Key_Backspace)
    assert field.text() == "" and not any(view.isRowHidden(row) for row in range(combo.count()))
    qtbot.keyClicks(view, "_1")
    qtbot.keyClick(view, Qt.Key.Key_Down)
    qtbot.keyClick(view, Qt.Key.Key_Return)
    assert combo.currentText() == "series_11"
    qtbot.waitUntil(lambda: not view.isVisible())
    combo.showPopup()
    qtbot.waitUntil(view.isVisible)
    assert field.text() == "" and not any(view.isRowHidden(row) for row in range(combo.count()))
    combo.hidePopup()


def test_a_long_entry_widens_the_list_not_the_field(qtbot, themed):
    combo = _combo(qtbot, 3)
    combo.addItem("a much longer entry than the field is wide, which the list shows whole")
    combo.setFixedWidth(160)
    combo.showPopup()
    qtbot.waitUntil(lambda: combo.view().isVisible())
    assert combo.view().window().width() > combo.width()
    combo.hidePopup()


# -- optional reference files ------------------------------------------------------------

def test_an_optional_file_not_downloaded_needs_no_attention(monkeypatch):
    """The ITU-R P.676-13 file, which the installers cannot carry: absent,
    it is "not downloaded", says how to get it, and is not a problem."""
    from spacemissionstudio.engine import gaseous_attenuation, reference_data

    monkeypatch.setattr(gaseous_attenuation, "installed", lambda: None)
    (itu,) = reference_data._itu_files()
    assert itu.status == reference_data.NOT_DOWNLOADED
    assert "Optional" in itu.note and "Download..." in itu.note
    assert not reference_data.needs_attention(itu)
    assert reference_data.needs_attention(reference_data.ReferenceFile("x", "y", "missing"))


def test_the_dialog_and_the_status_bar_do_not_count_optional_files(qtbot, monkeypatch):
    from spacemissionstudio.engine.reference_data import NOT_DOWNLOADED, ReferenceFile
    from spacemissionstudio.gui.data_panel_widget import DataPanelWidget

    files = [ReferenceFile("SPICE kernel", "de430.bsp", "ok"),
             ReferenceFile("ITU-R recommendation data", "R-REC-P.676-13-Part1.txt", NOT_DOWNLOADED, note="Optional")]
    panel = DataPanelWidget(load=False)
    qtbot.addWidget(panel)
    panel.show_files(files)
    assert "need attention" not in panel.status_label.text()
    assert "1 optional file(s) not downloaded" in panel.status_label.text()
    assert panel.table.item(1, 2).text() == NOT_DOWNLOADED
