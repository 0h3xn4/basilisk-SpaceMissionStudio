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

"""The shell of UI overhaul M2a: the action registry (gui.actions), the
navigation rail and its areas (gui.shell), the top bar's commands and
breadcrumbs (gui.app_shell) and the Settings area (gui.settings_page)."""

import pytest


@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


# -- the action registry ------------------------------------------------------------

def test_a_command_gets_its_tooltip_from_its_label_shortcut_and_tip(qtbot):
    """The tooltip is "Label (keys)" then what it does; it follows a
    changed text; an id or an area is checked."""
    from PySide6.QtWidgets import QWidget

    from spacemissionstudio.gui.actions import ActionRegistry

    owner = QWidget()
    qtbot.addWidget(owner)
    registry = ActionRegistry(owner)
    action = registry.add("file.save", "&Save", None, category="File", area="global", shortcut="Ctrl+S",
                          tip="Writes the file.")
    assert action.toolTip() == "Save (Ctrl+S)\nWrites the file."
    assert action in owner.actions() and registry["file.save"].keys == "Ctrl+S"
    action.setText("Save now")
    registry.refresh_tooltip("file.save")
    assert action.toolTip().startswith("Save now (Ctrl+S)")
    with pytest.raises(ValueError, match="twice"):
        registry.add("file.save", "Again", None, category="File", area="global")
    with pytest.raises(ValueError, match="unknown area"):
        registry.add("x.y", "X", None, category="File", area="nowhere")


def test_the_registry_does_not_keep_its_window_alive(qapp):
    """The registry holds its window weakly: a cycle through the window left
    it to the garbage collector, which ran only after Qt WebEngine had shut
    down when one test ran alone (a segfault at exit, CI's docs job)."""
    import weakref

    from PySide6.QtWidgets import QWidget

    from spacemissionstudio.gui.actions import ActionRegistry

    owner = QWidget()
    owner.commands = ActionRegistry(owner)
    owner.commands.add("file.save", "Save", None, category="File", area="global")
    ref = weakref.ref(owner)
    del owner
    assert ref() is None  # freed at once, by reference count, not by a later collection


def test_a_views_own_action_stays_in_its_view(qtbot):
    """on_window=False registers an action without moving it onto the
    window, so its shortcut keeps working only where its view has it."""
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QWidget

    from spacemissionstudio.gui.actions import ActionRegistry

    owner, view = QWidget(), QWidget()
    qtbot.addWidget(owner)
    qtbot.addWidget(view)
    own = QAction("Next", view)
    view.addAction(own)
    ActionRegistry(owner).add("cursor.next", "Next", None, category="Time Cursor", area="results", action=own,
                              shortcut="Alt+Right", on_window=False)
    assert own not in owner.actions() and own in view.actions()


def test_the_shortcut_list_is_grouped_by_category_in_the_order_added(window):
    """Settings > Keyboard lists the commands by category, each category's
    in the order they were added: Go to Home before Go to Scenario."""
    rows = window.commands.shortcut_rows()
    assert [row[0] for row in rows] == sorted(row[0] for row in rows)
    go = [label for category, label, _keys in rows if category == "Go"]
    assert go[:2] == ["Go to Home", "Go to Scenario"]


# -- the rail and its areas -------------------------------------------------------------

def test_a_later_area_slots_into_its_place_on_the_rail(qtbot):
    """register() puts an area at its order among those of its group, so
    a future area (Operations, between Timeline and Reports) needs no
    change to the shell."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.shell import Shell

    shell = Shell()
    qtbot.addWidget(shell)
    for order, area_id in ((0, "home"), (1, "timeline"), (3, "reports")):
        shell.register(area_id, "house", area_id.title(), QLabel(area_id), order)
    shell.register("operations", "activity", "Operations", QLabel("ops"), 2)
    shell.register("settings", "settings", "Settings", QLabel("s"), 4, bottom=True)
    top = shell.rail._top
    assert [top.itemAt(i).widget().text() for i in range(top.count())] == [
        "Home", "Timeline", "Operations", "Reports"]
    shell.show_area("operations")
    assert shell.rail.current() == "operations" and shell.current_area() == "operations"
    with pytest.raises(ValueError, match="twice"):
        shell.register("home", "house", "Home", QLabel("again"), 9)


def test_the_rail_follows_the_area_shown_and_keys_switch_areas(window):
    """Showing a view checks its area's rail button; Ctrl+1 to Ctrl+6 are
    the Go commands of the six top areas, named in the buttons' tooltips."""
    window.show_view(window.compare_widget)
    assert window.shell.rail.current() == "results"
    for number, (area_id, _icon, label) in enumerate(window._AREAS, start=1):
        action = window.commands.action(f"go.{area_id}")
        assert action.shortcut().toString() == f"Ctrl+{number}"
        assert window.shell.rail.buttons[area_id].toolTip() == f"{label} (Ctrl+{number})"
        action.trigger()
        assert window.shell.current_area() == area_id


def test_the_rail_collapses_to_icons_and_back(window):
    """The rail's last button and the View command show icons only; the
    two stay in step, and Reset Layout shows the names again."""
    from PySide6.QtCore import Qt

    rail = window.shell.rail
    rail.collapse_button.click()
    assert rail.collapsed and window.rail_collapse_action.isChecked()
    assert rail.buttons["home"].toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert rail.buttons["home"].accessibleName() == "Home"  # still named for a screen reader
    window.reset_layout()
    assert not rail.collapsed and not window.rail_collapse_action.isChecked()
    assert rail.buttons["home"].toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon


def test_a_new_window_opens_on_home_and_a_template_opens_the_scenario(window):
    """A new user's first move is picking a template or a file: the window
    opens on Home; opening a template goes to the Scenario area."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    assert window.shell.current_area() == "home"
    assert window.open_path(TEMPLATES_DIR / "22_starter_first_leo_satellite.json")
    assert window.shell.current_area() == "scenario" and window.current_view() is window.scenario_editor


# -- the top bar -------------------------------------------------------------------

def test_the_breadcrumbs_say_where_the_window_is(window):
    """Area › page: the Scenario tree's path, or the tab of Run and Results."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    assert window.top_bar.breadcrumb_label.text() == "Home"
    window.open_path(TEMPLATES_DIR / "22_starter_first_leo_satellite.json")
    window.scenario_editor.page_tree.tree.setCurrentItem(window.scenario_editor.environment_item)
    assert window.top_bar.breadcrumb_label.text() == "Scenario › Environment"
    window.show_view(window.compare_widget)
    assert window.top_bar.breadcrumb_label.text() == "Results › Compare"
    window.show_view(window.budget_widget)
    assert window.top_bar.breadcrumb_label.text() == "Run › Budget"


def test_the_save_button_shows_the_save_state_and_saves(window, monkeypatch):
    """The top bar's Save says whether the scenario is saved; a click is
    the Save command (here asking where, and cancelled)."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    saved = []
    window.save_action.triggered.connect(lambda: saved.append(True))
    assert window.top_bar.save_button.text() == "Not saved yet"
    window.scenario_editor.name_edit.setText("changed")
    assert window.top_bar.save_button.text() == "Save"
    window.top_bar.save_button.click()
    assert saved == [True]


def test_the_top_bar_holds_undo_redo_run_and_the_search(window, monkeypatch):
    """Undo and Redo are icon buttons of their commands, Run is the accent
    button with its mode beside it, and the search field opens the palette."""
    from PySide6.QtWidgets import QToolButton

    from spacemissionstudio.gui import command_palette

    buttons = {button.defaultAction(): button for button in window.top_bar.findChildren(QToolButton)
               if button.defaultAction() is not None}
    assert window.undo_action in buttons and window.redo_action in buttons
    assert window.top_bar.run_button.objectName() == "primaryToolButton"
    assert window.top_bar.run_button.defaultAction() is window.run_action
    opened = []
    monkeypatch.setattr(command_palette.CommandPalette, "exec", lambda self: opened.append(self) or 0)
    window.top_bar.search_button.click()
    assert len(opened) == 1


def test_the_window_title_bar_name_elides_rather_than_widening_the_window(window):
    """A long scenario name ends in "..." in the top bar: its minimum width
    does not grow with the text, and its tooltip has all of it."""
    label = window.top_bar.name_label
    before = window.top_bar.minimumSizeHint().width()
    window.scenario_editor.name_edit.setText("a very long scenario name " * 8)
    assert window.top_bar.minimumSizeHint().width() == before
    assert label.toolTip().startswith("a very long scenario name")


# -- the Settings area -----------------------------------------------------------------

def test_settings_holds_the_theme_layout_and_about_commands(window):
    """Settings shows the commands as buttons: a theme button is its theme
    command, Reset Layout its own; the palette lists each section."""
    page = window.settings_page
    assert page.buttons["view.theme.dark"].defaultAction() is window.theme_actions["dark"]
    assert page.buttons["view.reset_layout"].defaultAction() is window.reset_layout_action
    assert page.buttons["help.about"].defaultAction() is window.about_action
    labels = {entry.label for entry in window.palette_entries()}
    assert {f"Settings > {title}" for _key, title in page.sections()} <= labels
    entry = next(e for e in window.palette_entries() if e.label == "Settings > Keyboard")
    entry.run()
    assert window.shell.current_area() == "settings"
