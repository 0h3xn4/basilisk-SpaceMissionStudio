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
"""The Results time cursor from the keyboard (docs/ux-standard.md,
keyboard-only use; iteration 7b): a sample at a time, ten at a time, to
the run's ends and to the next or previous event, listed under View >
Time Cursor and in Help > Keyboard Shortcuts; Alt+Backspace clears it."""

import warnings

import numpy as np
import pytest
from PySide6.QtCore import Qt

pytestmark = pytest.mark.requires_gui

_EPOCH = "2030-01-01T08:30:00"
_T = np.arange(0.0, 3600.0 + 1.0, 60.0)  # [s] one hour at 60 s


def _result():
    """Sunlight with two eclipses (600-900 s and 2400-2700 s)."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    sunlight = np.where(((_T >= 600.0) & (_T < 900.0)) | ((_T >= 2400.0) & (_T < 2700.0)), 0.0, 1.0)  # [-]
    result = ResultSet("demo")
    result.add(TimeSeries("sat-1.eclipse.illumination_factor", _T, ("illumination_factor",), sunlight[:, None]))
    return result


@pytest.fixture
def results(qtbot):
    from spacemissionstudio.gui.results_widget import ResultsWidget
    from spacemissionstudio.gui.time_cursor import TimeCursor

    widget = ResultsWidget()
    qtbot.addWidget(widget)
    widget.resize(1000, 600)  # [px]
    cursor = TimeCursor()
    widget.set_time_cursor(cursor)
    widget.set_result(_result(), _EPOCH)
    return widget, cursor


def test_the_cursor_steps_through_the_samples(results):
    """From no cursor, Next Sample puts it on the first sample and Previous
    Sample on the last; then one or ten samples at a time, held at the
    ends."""
    widget, cursor = results
    widget.step_cursor(1)
    assert cursor.time_s == 0.0  # [s]
    widget.step_cursor(1)
    widget.step_cursor(10)
    assert cursor.time_s == 660.0  # [s] eleven samples on
    widget.step_cursor(-100)
    assert cursor.time_s == 0.0  # [s] held at the start
    cursor.clear()
    widget.step_cursor(-1)
    assert cursor.time_s == 3600.0  # [s]
    widget.cursor_to_end(-1)
    assert cursor.time_s == 0.0 and widget.readout.time_label.text().endswith("(cursor)")  # [s]


def test_the_cursor_goes_from_event_to_event(results):
    """Next and Previous Event go to the start of the next or previous
    eclipse; at the last, Next Event stays."""
    widget, cursor = results
    widget.cursor_to_event(1)
    assert cursor.time_s == pytest.approx(600.0, abs=60.0)  # [s] the first eclipse
    first = cursor.time_s
    widget.cursor_to_event(1)
    assert cursor.time_s == pytest.approx(2400.0, abs=60.0)  # [s] the second
    widget.cursor_to_event(1)
    assert cursor.time_s == pytest.approx(2400.0, abs=60.0)  # [s] no later event
    widget.cursor_to_event(-1)
    assert cursor.time_s == first


def test_the_keys_work_where_results_has_the_focus(results, qtbot):
    """Alt+Right and Alt+End reach the cursor from a widget inside Results."""
    from PySide6.QtWidgets import QApplication

    widget, cursor = results
    with qtbot.waitExposed(widget):
        widget.show()
    # A shortcut fires only in Qt's active window. Asking the window system
    # (activateWindow) is not enough on macOS: activation is per application
    # there, and the other test workers' windows, each its own process, can
    # keep it from this one (CI, cocoa: not active within 5 s). Qt's own
    # notion of the active window is what the shortcut map checks, so it is
    # set directly. QApplication.setActiveWindow is deprecated (its
    # replacement, activateWindow, is only a request to the window system) but
    # still what sets that notion in Qt 6.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        QApplication.setActiveWindow(widget)
    assert QApplication.activeWindow() is widget
    target = widget.catalog
    target.setFocus()
    qtbot.keyClick(target, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    assert cursor.time_s == 0.0  # [s]
    qtbot.keyClick(target, Qt.Key.Key_End, Qt.KeyboardModifier.AltModifier)
    assert cursor.time_s == 3600.0  # [s]


def test_the_cursor_commands_are_in_the_view_menu_and_the_shortcut_list(qtbot, monkeypatch):
    """View > Time Cursor holds the eight moves with their keys, Run >
    Clear Time Cursor is Alt+Backspace, and Help > Keyboard Shortcuts
    lists them (it looks into submenus)."""
    from spacemissionstudio.gui import help_dialog
    from spacemissionstudio.gui.main_window import MainWindow

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    view = next(a.menu() for a in window.menuBar().actions() if a.text() == "&View")
    cursor_menu = next(a.menu() for a in view.actions() if a.text() == "Time &Cursor")
    assert [(a.text(), a.shortcut().toString()) for a in cursor_menu.actions()][:2] == [
        ("Next Sample", "Alt+Right"), ("Previous Sample", "Alt+Left")]
    assert len(cursor_menu.actions()) == 8
    shown = []
    monkeypatch.setattr(help_dialog.ShortcutsDialog, "exec", lambda self: shown.append(self) or 0)
    window.on_keyboard_shortcuts()
    table = shown[0].table
    rows = {table.item(r, 0).text(): table.item(r, 1).text() for r in range(table.rowCount())}
    assert rows["Next Event"] == "Alt+PgDown" and rows["Clear Time Cursor"] == "Alt+Backspace"
