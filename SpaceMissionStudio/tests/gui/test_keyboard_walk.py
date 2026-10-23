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


"""The keyboard-only walk of every area (UI overhaul M9, accessibility):
each area is reached by its shortcut, Tab reaches every control in it that
takes the keyboard, and the keyboard never lands on a hidden widget."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QAbstractScrollArea, QApplication, QWidget

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_TABS = 600  # Tab presses at most: more than any area has controls


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    w.resize(1440, 900)  # [px]
    w.show()
    qtbot.waitExposed(w)
    w.activateWindow()
    assert w.open_path(_TEMPLATES / "23_starter_complete_small_satellite.json")
    return w


def _stop(widget: QWidget):
    """The Tab stop ``widget`` belongs to: an exclusive group of buttons
    (radio buttons, a segmented control) is one stop, its buttons chosen
    with the arrow keys, as Qt does."""
    if isinstance(widget, QAbstractButton):
        group = widget.group()
        if group is not None and group.exclusive():
            return group
        if widget.autoExclusive() and widget.parentWidget() is not None:
            return ("auto-exclusive", widget.parentWidget())
    return widget


def _name(stop) -> str:
    widget = stop.buttons()[0] if hasattr(stop, "buttons") else stop[1] if isinstance(stop, tuple) else stop
    return (f"{type(widget).__name__} {widget.objectName() or widget.toolTip()[:40]!r} "
            f"{getattr(widget, 'text', lambda: '')()!r}")


def _takes_tab(widget: QWidget, root: QWidget) -> bool:
    """``widget``, in ``root``, is one Tab should reach: shown, enabled,
    taking focus by Tab, and not part of a compound control that takes
    the focus itself (a spin box's line edit, a scroll area's viewport)."""
    if not (widget.isVisibleTo(root) and widget.isEnabled()):
        return False
    if not widget.focusPolicy() & Qt.FocusPolicy.TabFocus or widget.focusProxy() is not None:
        return False
    parent = widget.parentWidget()
    while parent is not None and parent is not root:
        if parent.focusProxy() is widget or (isinstance(parent, QAbstractScrollArea) and widget is parent.viewport()):
            return False
        parent = parent.parentWidget()
    return True


@pytest.mark.parametrize("area", ["home", "scenario", "run", "results", "timeline", "reports", "settings"])
def test_tab_reaches_every_control_of_the_area(window, qtbot, area):
    """The area by its shortcut (Settings from the palette's command),
    then Tab: every control of the area is reached, focus is never on a
    hidden widget, and the focus shows (the style sheet's focus ring)."""
    from spacemissionstudio.gui.theme import TOKENS, stylesheet

    keys = {"home": "1", "scenario": "2", "run": "3", "results": "4", "timeline": "5", "reports": "6"}
    if area in keys:
        qtbot.keyClick(window, getattr(Qt.Key, f"Key_{keys[area]}"), Qt.KeyboardModifier.ControlModifier)
    else:
        window.shell.show_area(area)
    assert window.shell.current_area() == area
    page = window.areas.currentWidget()
    wanted = {_stop(w) for w in page.findChildren(QWidget) if _takes_tab(w, window)}
    assert wanted, f"nothing in {area} takes the keyboard"
    window.shell.rail.setFocus() if hasattr(window.shell, "rail") else page.setFocus()
    reached = set()
    for _ in range(_TABS):
        focus = QApplication.focusWidget()
        assert focus is None or focus.isVisible(), f"the focus is on a hidden {focus!r}"
        qtbot.keyClick(focus or window, Qt.Key.Key_Tab)
        focus = QApplication.focusWidget()
        if focus is not None and page.isAncestorOf(focus):
            reached.add(_stop(focus))
        if wanted <= reached:
            break
    missing = sorted(_name(stop) for stop in wanted - reached)
    assert not missing, f"Tab never reaches {len(missing)} of {len(wanted)} controls in {area}: {missing[:15]}"
    assert ":focus" in stylesheet(TOKENS)  # the focus ring


def test_the_inspector_names_a_focused_control_by_what_it_shows(window):
    """A control without a label or a tip is named by what it shows (a tab
    bar by its current tab), never by its class name ("_TabBar")."""
    window.show_view(window.results_widget)
    tab_bar = window.results_views.tabBar()
    window.inspector_widget.inspect(tab_bar)
    assert window.inspector_widget.name_label.text() == "Plots"
