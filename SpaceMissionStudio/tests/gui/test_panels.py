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

"""The panels of UI overhaul M2b: the Problems panel at the bottom
(gui.workspace_panels), the run job in the status bar (gui.app_shell), the
inspector on the right, the layout kept per project and a keyboard-only
walk of the shell (gui.main_window)."""

import pytest

_TEMPLATE = "22_starter_first_leo_satellite.json"


@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


@pytest.fixture
def shown(window, qtbot):
    """The window shown and active, so its shortcuts take key presses."""
    window.resize(1400, 900)  # [px]
    window.show()
    window.activateWindow()
    qtbot.waitExposed(window)
    return window


def _open(window, name=_TEMPLATE):
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    assert window.open_path(TEMPLATES_DIR / name)


# -- the Problems panel ----------------------------------------------------------------

def test_the_problems_table_shows_severity_id_object_and_message(qtbot):
    """Each problem is a row: severity (word and icon), the field it is
    about, the object it belongs to, the message. Errors come first; a
    column header sorts by that column."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.gui.workspace_panels import PROBLEM_COLUMNS, ProblemsWidget

    widget = ProblemsWidget()
    qtbot.addWidget(widget)
    counts = []
    widget.counts_changed.connect(lambda errors, warnings: counts.append((errors, warnings)))
    widget.set_problems([("warning", "sat-1: dry_mass_kg looks low", "dry mass looks low"),
                         ("error", "scenario.epoch_utc is not a date", "Epoch (UTC) is not a date"),
                         ("warning", "nothing it can be placed by")], spacecraft=["sat-1"])
    header = widget.table.horizontalHeader()
    assert [widget.proxy.headerData(c, Qt.Orientation.Horizontal) for c in range(header.count())] == list(
        PROBLEM_COLUMNS) == ["Severity", "ID", "Object", "Message"]
    assert widget.shown_rows() == [
        ("Error", "epoch_utc", "Scenario", "Epoch (UTC) is not a date"),
        ("Warning", "dry_mass_kg", "sat-1", "dry mass looks low"),
        ("Warning", "-", "Scenario", "nothing it can be placed by")]
    assert counts[-1] == (1, 2)
    assert not widget.proxy.index(0, 0).data(Qt.ItemDataRole.DecorationRole).isNull()  # not colour alone
    widget.table.sortByColumn(3, Qt.SortOrder.AscendingOrder)
    assert [row[3] for row in widget.shown_rows()] == [
        "dry mass looks low", "Epoch (UTC) is not a date", "nothing it can be placed by"]
    widget.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    assert widget.problem_at(0).text == "scenario.epoch_utc is not a date"


def test_the_problems_table_copies_its_selection_and_has_an_empty_state(qtbot):
    """Ctrl+C copies the selected rows as TSV under their headings; with no
    problem the panel says the scenario is valid instead of an empty table."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.workspace_panels import ProblemsWidget

    widget = ProblemsWidget()
    qtbot.addWidget(widget)
    assert widget.empty_label.isVisibleTo(widget) and not widget.table.isVisibleTo(widget)
    widget.set_problems([("error", "scenario.name must not be empty", "Name must not be empty")])
    assert widget.table.isVisibleTo(widget) and not widget.empty_label.isVisibleTo(widget)
    widget.table.selectRow(0)
    qtbot.keyClick(widget.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text() == ("Severity\tID\tObject\tMessage\n"
                                               "Error\tname\tScenario\tName must not be empty\n")


def test_the_problem_counts_show_in_the_status_bar_and_the_top_bar(window):
    """The status bar always says how many errors and warnings there are;
    the top bar shows the count only while there are some. Either opens the
    Problems panel."""
    _open(window, "01_two_body_circular_orbit.json")  # a template without a warning
    items, top = window.status_items, window.top_bar
    assert items.problems_button.text() == "No problems" and not top.problems_button.isVisibleTo(window)
    window.scenario_editor.epoch_edit.setText("2030-13-45T99:00:00")
    assert items.problems_button.text() == "1 error" and top.problems_button.text() == "1"
    assert top.problems_button.isVisibleTo(window) and window.problems_dock.windowTitle().startswith("Problems (")
    assert window.commands["view.problems"].label == "Problems"  # the command keeps its name
    window.problems_dock.hide()
    items.problems_button.click()
    assert window.problems_dock.isVisibleTo(window)
    window.problems_dock.hide()
    top.problems_button.click()
    assert window.problems_dock.isVisibleTo(window)


def test_a_refused_run_opens_a_hidden_problems_panel(window):
    """Run on an invalid scenario shows the Problems panel, even when it was
    hidden, and goes to the field."""
    window.problems_dock.hide()
    window.on_run()  # no spacecraft: invalid
    assert window._run_worker is None and window.problems_dock.isVisibleTo(window)


def test_enter_in_the_problems_table_goes_to_the_field(shown, qtbot):
    """Keyboard only: Ctrl+J into the panel, the arrow keys to a row, Enter
    to the field it is about."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    window = shown
    _open(window)
    window.scenario_editor.epoch_edit.setText("2030-13-45T99:00:00")
    window.shell.show_area("results")
    window.problems_dock.hide()
    qtbot.keyClick(window, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
    table = window.problems_widget.table
    assert window.problems_dock.isVisible() and table.hasFocus()
    qtbot.keyClick(table, Qt.Key.Key_Home)
    qtbot.keyClick(table, Qt.Key.Key_Return)
    assert window.shell.current_area() == "scenario"
    assert QApplication.focusWidget() is window.scenario_editor.epoch_edit


# -- the status bar: the run job --------------------------------------------------------

def test_a_run_is_a_job_in_the_status_bar_with_progress_and_cancel(window):
    """While a run goes, the status bar shows its phase, progress, time and
    Cancel, and the chip its state; the job leaves when the run ends."""
    bar = window.statusBar()
    progress = window.run_progress
    assert bar.isAncestorOf(progress) and bar.isAncestorOf(window.run_chip)
    assert not progress.isVisibleTo(window)
    cancelled = []
    progress.cancel_requested.connect(lambda: cancelled.append(True))
    window._start_busy("Running", determinate=True)
    progress.set_phase("Propagating: day 0.4 of 1")
    progress.set_fraction(0.43)
    window._update_busy_elapsed()
    assert progress.isVisibleTo(window) and progress.bar.value() == 43
    assert progress.phase_label.text() == "Propagating: day 0.4 of 1"
    assert window.run_chip.text() == "Running 43 %"
    assert not window.run_chip.isVisibleTo(window)  # the job says the same, with its bar
    assert progress.cancel_button.isVisibleTo(window)
    progress.cancel_button.click()
    assert cancelled == [True]
    window._stop_busy("Done", "done", "Done")
    assert not progress.isVisibleTo(window) and window.run_chip.state == "done"
    assert window.run_chip.isVisibleTo(window)


def test_the_status_bar_job_fits_a_1280_px_window(window, qapp):
    """At 1280 px, with the longest time text, the job's time and Cancel get
    all the width they need: the long entries elide instead (their tooltips
    keep the whole text). The status bar lays the job out again as its text
    grows."""
    window.resize(1280, 720)  # [px]
    window.show()
    window._start_busy("Running", determinate=True)
    progress = window.run_progress
    progress.set_phase("Propagating: day 0.4 of 1")
    progress.set_fraction(0.8)
    progress.elapsed_s = lambda: 40.0  # [s]
    progress.refresh_time()
    qapp.processEvents()
    assert progress.time_label.text() == "80 % · 0:40 elapsed · about 0:09 left"
    bar = window.statusBar()
    # Room to spare, not a fit by a few pixels: the fonts differ by machine.
    # The message lists each entry's widths, so a failure says which is wide.
    entries = "\n".join(
        f"{type(child).__name__} {child.objectName()!r}: min {child.minimumSizeHint().width()}, "
        f"min set {child.minimumWidth()}, hint {child.sizeHint().width()}, now {child.width()}, "
        f"text {getattr(child, 'text', lambda: '')()!r}"
        for child in bar.children() if child.isWidgetType() and child.isVisible())
    assert bar.minimumSizeHint().width() <= bar.width() - 60, (  # [px]
        f"window {window.width()} px, screen {window.screen().availableGeometry().width()} px:\n{entries}")
    assert progress.time_label.width() >= progress.time_label.sizeHint().width()
    assert progress.cancel_button.width() >= progress.cancel_button.sizeHint().width()
    assert progress.phase_label.width() >= 80  # [px]
    items = window.status_items
    assert items.frames_label.toolTip().startswith(items.frames_label.text())
    window._stop_busy("Done")


def test_the_status_bar_job_does_not_widen_the_window(window):
    """A long phase ends in "..." rather than holding the window wider."""
    before = window.minimumSizeHint().width()
    window._start_busy("Running")
    window.run_progress.set_phase("Step 2 of 5: " + "a long phase name " * 20)
    assert window.minimumSizeHint().width() <= before + window.run_progress.sizeHint().width()
    assert window.run_progress.phase_label.maximumWidth() < 400  # [px]
    window._stop_busy("Done")


# -- the inspector ---------------------------------------------------------------------

def test_the_inspector_and_explain_are_panels_on_the_right_without_tabs(window):
    """Inspector over Explain, each its own panel on the right; the Problems
    panel at the bottom. Ctrl+I and Ctrl+J show and hide them."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTabWidget

    right = Qt.DockWidgetArea.RightDockWidgetArea
    assert window.dockWidgetArea(window.side_dock) == window.dockWidgetArea(window.explain_dock) == right
    assert window.dockWidgetArea(window.problems_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert window.side_dock.widget() is window.inspector_widget
    assert not window.side_dock.findChildren(QTabWidget) and not window.explain_dock.findChildren(QTabWidget)
    assert window.commands["view.inspector"].keys == "Ctrl+I" and window.commands["view.problems"].keys == "Ctrl+J"


def test_ctrl_i_shows_and_hides_the_inspector(shown, qtbot):
    """Ctrl+I, pressed in the window, hides the Inspector and shows it again."""
    from PySide6.QtCore import Qt

    window = shown
    assert window.side_dock.isVisible()
    qtbot.keyClick(window, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    assert not window.side_dock.isVisible()
    qtbot.keyClick(window, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    assert window.side_dock.isVisible()


# -- the layout, per project ----------------------------------------------------------

def test_each_project_keeps_its_own_layout(window, tmp_path, qapp):
    """The rail, the panels and the splitters come back as they were for
    each scenario file; a scenario without a layout keeps the one shown."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR

    first, second = tmp_path / "first.json", tmp_path / "second.json"
    first.write_bytes((TEMPLATES_DIR / _TEMPLATE).read_bytes())
    second.write_bytes((TEMPLATES_DIR / _TEMPLATE).read_bytes())
    window.show()
    splitter = window.scenario_editor.page_tree.splitter
    assert window.open_path(first)
    window.problems_dock.hide()
    window.rail_collapse_action.setChecked(True)
    splitter.setSizes([300, 700])  # [px]
    qapp.processEvents()  # the sizes as laid out, not as asked: a narrower screen scales them
    first_sizes = splitter.sizes()

    assert window.open_path(second)  # no layout of its own yet: the one shown stays
    assert not window.problems_dock.isVisible() and window.shell.rail.collapsed
    window.problems_dock.show()
    window.side_dock.hide()
    window.rail_collapse_action.setChecked(False)
    splitter.setSizes([160, 840])  # [px]
    qapp.processEvents()
    second_sizes = splitter.sizes()

    assert window.open_path(first)
    assert not window.problems_dock.isVisible() and window.side_dock.isVisible()
    assert window.shell.rail.collapsed
    assert splitter.sizes()[0] == first_sizes[0]  # the tree's width; the page takes what the panels leave
    assert window.open_path(second)
    assert window.problems_dock.isVisible() and not window.side_dock.isVisible()
    assert not window.shell.rail.collapsed and splitter.sizes()[0] == second_sizes[0]


def test_a_project_layout_outlives_the_window(qtbot, monkeypatch, tmp_path):
    """Closing the window keeps the open project's layout for the next
    window that opens it."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    path = tmp_path / "mission.json"
    path.write_bytes((TEMPLATES_DIR / _TEMPLATE).read_bytes())
    first = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(first)
    first.show()
    assert first.open_path(path)
    first.explain_dock.hide()
    first.close()
    first.open_path(TEMPLATES_DIR / _TEMPLATE)  # nothing kept from a closed window's later changes

    second = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(second)
    second.show()
    second.explain_dock.show()
    assert second.open_path(path)
    assert not second.explain_dock.isVisible()


# -- a keyboard-only walk -----------------------------------------------------------

def test_a_keyboard_only_walk_of_the_shell(shown, qtbot, monkeypatch):
    """Every part of the shell without the mouse: Ctrl+1 to Ctrl+6 reach the
    areas, the arrow keys move along the rail and Enter opens an area, Ctrl+K
    the command palette, Ctrl+I and Ctrl+J the panels; Tab goes round the
    whole window (top bar, rail, area, panels, status bar) and back, never
    held in one widget."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui import command_palette

    window = shown
    for number, (area_id, _icon, _label) in enumerate(window._AREAS, start=1):
        qtbot.keyClick(window, getattr(Qt.Key, f"Key_{number}"), Qt.KeyboardModifier.ControlModifier)
        assert window.shell.current_area() == area_id

    rail = window.shell.rail
    rail.buttons["home"].setFocus()
    qtbot.keyClick(rail.buttons["home"], Qt.Key.Key_Down)
    assert QApplication.focusWidget() is rail.buttons["scenario"]
    qtbot.keyClick(rail.buttons["scenario"], Qt.Key.Key_Space)
    assert window.shell.current_area() == "scenario"

    opened = []
    monkeypatch.setattr(command_palette.CommandPalette, "exec", lambda self: opened.append(self) or 0)
    qtbot.keyClick(window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    assert len(opened) == 1

    qtbot.keyClick(window, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
    assert not window.problems_dock.isVisible()
    qtbot.keyClick(window, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
    assert window.problems_dock.isVisible() and window.problems_dock.isAncestorOf(QApplication.focusWidget())

    window.shell.show_area("home")
    start = rail.buttons["home"]
    start.setFocus()
    seen = []
    for _press in range(200):
        widget = QApplication.focusWidget()
        seen.append(widget)
        qtbot.keyClick(widget, Qt.Key.Key_Tab)
        if QApplication.focusWidget() is start:
            break
    else:
        pytest.fail(f"Tab never came back to the rail: held at {QApplication.focusWidget()!r}")
    top_bar, home = window.top_bar, window.shell.page("home")
    assert top_bar.save_button in seen and top_bar.run_button in seen and top_bar.search_button in seen
    assert rail.collapse_button in seen
    assert any(home.isAncestorOf(widget) for widget in seen)
    assert window.problems_widget.table in seen
    assert window.status_items.problems_button in seen and window.status_items.data_button in seen
    assert len(seen) == len(set(map(id, seen)))  # each stop once: nothing holds the focus
