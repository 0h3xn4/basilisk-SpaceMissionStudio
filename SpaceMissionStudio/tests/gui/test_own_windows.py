#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#

"""The windows the user reads beside the main window are windows of their
own (``widgets.make_window`` and ``widgets.show_window``): the user manual,
File › Change History, Reference data, Tools › Check a CCSDS File..., a
run's full record and Compare's input differences. None is modal or
attached to the main window (a window manager moves a modal dialog with
its parent), none keeps the application running, and they close with the
main window."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    """A main window with template 22 open; questions answer Discard."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def _assert_own_window(widget) -> None:
    """``widget`` shows as a window of its own: a top-level window with
    minimise and maximise buttons, not modal, with no transient parent, not
    keeping the application running."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    assert widget.isVisible() and widget.isWindow()
    assert widget.windowType() == Qt.WindowType.Window
    assert widget.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
    assert widget.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
    assert widget.windowModality() == Qt.WindowModality.NonModal and not widget.isModal()
    assert QApplication.activeModalWidget() is None
    assert widget.windowHandle() is not None and widget.windowHandle().transientParent() is None
    assert not widget.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose)


def _opm(tmp_path) -> Path:
    from spacemissionstudio.engine import ccsds_odm

    path = tmp_path / "sat.opm"
    path.write_text(ccsds_odm.write_opm(object_name="sat-1", object_id="2030-001A", center_name="EARTH",
                                        ref_frame="EME2000", time_system="UTC", epoch=datetime(2030, 1, 1),
                                        r_km=[7000.0, 100.0, 0.0], v_km_s=[0.0, 7.546, 1.0]),  # [km], [km/s]
                    encoding="ascii")
    return path


def test_the_manual_is_one_window_of_its_own(window):
    """Help › User Manual opens the manual as a window of its own; asking
    again brings the same window back."""
    window.on_user_manual()
    manual = window._manual_dialog
    _assert_own_window(manual)
    manual.close()
    window.on_user_manual()
    assert window._manual_dialog is manual and manual.isVisible()


def test_the_reference_data_is_a_window_of_its_own(window):
    """The status bar's Reference data entry opens a window of its own."""
    window.show_view(window.data_panel_widget)
    _assert_own_window(window.data_dialog)


def test_the_change_history_is_one_window_per_scenario(window, tmp_path):
    """File › Change History opens a window of its own; asking again reads
    the file again into the same window, and another scenario's history
    replaces it."""
    first = tmp_path / "first.json"
    window._save_to(first)
    window.change_history_action.trigger()
    history = window._history_window
    _assert_own_window(history)
    assert history.scenario_path == first and history.table.row_count() == 1
    window.scenario_editor.name_edit.setText("Renamed")
    window._save_to(first)
    window.change_history_action.trigger()
    assert window._history_window is history and history.table.row_count() == 2
    second = tmp_path / "second.json"
    window._save_to(second)
    window.change_history_action.trigger()
    assert window._history_window is not history and window._history_window.scenario_path == second
    _assert_own_window(window._history_window)


def test_a_ccsds_check_is_a_window_of_its_own(window, tmp_path, monkeypatch):
    """Tools › Check a CCSDS File... shows its result in a window of its
    own, so the main window stays usable while it is open."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.ccsds_dialogs import CcsdsCheckDialog

    path = _opm(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    window.on_check_ccsds_file()
    [check] = [w for w in window.findChildren(CcsdsCheckDialog) if w.isVisible()]
    _assert_own_window(check)
    assert check.kind == "OPM"


def test_a_runs_record_is_a_window_of_its_own(window, qtbot):
    """Show everything recorded opens the run's record in a window of its
    own."""
    from spacemissionstudio.gui.run_history_view import ProvenancePopover

    popover = ProvenancePopover(window)
    popover._title, popover._provenance = "Run 1", {"tool": {"version": "test"}}
    popover.show_all()
    _assert_own_window(popover.dialog)


def test_the_input_differences_are_a_window_of_their_own(window, monkeypatch):
    """Compare's input differences open in a window of their own, beside
    the plots they explain."""
    results = window.results_widget
    results._current_run = SimpleNamespace(number=1)
    monkeypatch.setattr(results, "comparison_run", lambda: SimpleNamespace(number=2))
    monkeypatch.setattr(results, "input_differences", lambda: [("spacecraft[0].dry_mass_kg", 10.0, 12.0)])  # [kg]
    results.show_input_differences()
    _assert_own_window(results.input_differences_window)


def test_the_windows_close_with_the_main_window(window, qtbot):
    """Closing the main window closes the windows of their own it opened,
    and leaves its floating panels as they are."""
    window.on_user_manual()
    window.show_view(window.data_panel_widget)
    dock = window.problems_dock
    dock.setFloating(True)
    dock.show()
    window.close_own_windows()
    assert not window._manual_dialog.isVisible() and not window.data_dialog.isVisible()
    assert dock.isVisible()
