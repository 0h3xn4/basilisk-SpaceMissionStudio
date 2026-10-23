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


"""Reports › Exports and the M8 settings (UI overhaul M8): every export in
one table with the time this machine last wrote it, a row opening the view
that makes it; the UI scale for the next start, reduce motion for the
toasts, and the Vizard location."""

import re
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def vizard_settings(tmp_path, monkeypatch):
    """The Vizard launcher's settings in a file of this test's own."""
    from spacemissionstudio.gui import vizard_launcher

    path = str(tmp_path / "vizard.ini")
    monkeypatch.setattr(vizard_launcher, "QSettings", lambda: QSettings(path, QSettings.Format.IniFormat))
    return path


@pytest.fixture
def window(qtbot, monkeypatch, vizard_settings):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def test_every_export_is_listed_never_written_at_first(qtbot):
    """The exports of plan §5.3, each with its format, view, destination
    and provenance; none written yet on a new machine."""
    from spacemissionstudio.gui.exports_page import EXPORTS, ExportsPage

    page = ExportsPage()
    qtbot.addWidget(page)
    table = page.table
    assert table.row_count() == len(EXPORTS) == 12
    assert [table.header_text(c) for c in range(table.column_count())] == [
        "Export", "Last written\n[UTC]", "Format", "Made in", "Default destination", "Provenance"]
    names = {table.cell(r, 0) for r in range(table.row_count())}
    assert names == {"Plot data", "Plot image", "Every shown plot", "Events", "Mission output", "Monte Carlo runs",
                     "Budget", "Flight software", "SIL report", "Vizard playback", "3D model"}
    assert all(table.cell(r, 1) == "never" for r in range(table.row_count()))
    assert all(table.cell(r, c) for r in range(table.row_count()) for c in range(6))


def test_an_export_is_logged_and_shown_with_its_time_and_path(qtbot, tmp_path, monkeypatch):
    """Exporting the events records the time (UTC with Z) and the path;
    the page, hidden then, shows it when shown."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui import event_timeline_widget
    from spacemissionstudio.gui.exports_page import EXPORTS, ExportsPage

    page = ExportsPage()
    qtbot.addWidget(page)
    timeline = event_timeline_widget.EventTimelineWidget()
    qtbot.addWidget(timeline)
    result = ResultSet("run")
    result.add(TimeSeries("sat-1.position_N", np.array([0.0, 60.0]), ("x", "y", "z"), np.zeros((2, 3)), "m"))
    timeline.set_result(result, "2030-01-01T00:00:00Z")
    target = tmp_path / "events.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    timeline._on_export()
    assert target.is_file()
    page.show()
    qtbot.waitExposed(page)
    when = page.last_written("events_csv")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", when)
    row = [export.key for export in EXPORTS].index("events_csv")
    assert page.table.cell_tooltip(row, 1) == str(target)
    assert page.last_written("output_csv") == "never"


def test_a_row_opens_the_view_that_makes_it(window):
    """Reports opens on Exports; activating a row shows its view."""
    from spacemissionstudio.gui.exports_page import EXPORTS

    window.shell.show_area("reports")
    assert window.current_view() is window.exports_page
    table = window.exports_page.table
    for key, view in (("events_csv", window.event_timeline_widget), ("plot_png", window.results_widget),
                      ("budget_csv", window.budget_widget), ("sil_report", window.flight_software_widget),
                      ("vizard_file", window.run_page)):
        index = table.proxy.index([export.key for export in EXPORTS].index(key), 0)
        table.view.activated.emit(index)
        assert window.current_view() is view, key
    window.show_view(window.flight_software_widget)
    assert window.shell.current_area() == "reports" and window.reports_views.currentWidget() is \
        window.flight_software_widget


def test_the_ui_scale_is_kept_for_the_next_start(window, monkeypatch):
    """Settings › Appearance › UI scale: remembered, says it applies at the
    next start, and becomes QT_SCALE_FACTOR then, unless the environment
    sets one."""
    from spacemissionstudio.gui import app
    from spacemissionstudio.gui.theme import ui_scale_setting

    settings = window.settings_page
    assert ui_scale_setting() == 100 and settings.ui_scale.currentText() == "100 %"
    settings.ui_scale.setCurrentIndex(settings.ui_scale.findText("125 %"))
    assert ui_scale_setting() == 125 and settings.ui_scale_note.text() == "Applies at the next start."
    environ = {}
    app.apply_ui_scale(environ)
    assert environ == {"QT_SCALE_FACTOR": "1.25"}
    environ = {"QT_SCALE_FACTOR": "2"}
    app.apply_ui_scale(environ)
    assert environ == {"QT_SCALE_FACTOR": "2"}  # the user's own wins
    settings.ui_scale.setCurrentIndex(settings.ui_scale.findText("100 %"))
    environ = {}
    app.apply_ui_scale(environ)
    assert environ == {}


def test_toasts_fade_unless_motion_is_reduced(window, qtbot):
    """A toast fades in over 150 ms and is gone at the same time as
    before; with reduce motion it appears without an effect."""
    from spacemissionstudio.gui.feedback import show_toast
    from spacemissionstudio.gui.theme import reduce_motion

    window.show()
    qtbot.waitExposed(window)
    # 3 s shown: the fade-in's end is seen before the fade-out starts even
    # when a loaded test run stalls the event loop (a 600 ms toast left only
    # 300 ms between them, and a longer stall skipped straight to the fade-out).
    toast = show_toast(window, "Saved", duration_ms=3000)
    assert toast.graphicsEffect() is not None  # fading in
    qtbot.waitUntil(lambda: toast.graphicsEffect() is None, timeout=2500)
    qtbot.waitUntil(lambda: toast.graphicsEffect() is not None, timeout=10000)  # fading out
    qtbot.waitUntil(lambda: not toast.isVisible(), timeout=10000)
    window.settings_page.reduce_motion.setChecked(True)
    assert reduce_motion()
    toast = show_toast(window, "Saved", duration_ms=600)
    assert toast.graphicsEffect() is None and toast.isVisible()
    qtbot.waitUntil(lambda: not toast.isVisible(), timeout=5000)


def test_the_vizard_location_is_browsed_and_cleared(window, tmp_path, monkeypatch, vizard_settings):
    """Settings › Vizard: Browse remembers the program Launch Vizard uses;
    Clear forgets it."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui import vizard_launcher

    settings = window.settings_page
    assert settings.vizard_path.text() == "Not set" and not settings.vizard_clear.isEnabled()
    program = tmp_path / "Vizard.x86_64"
    program.write_text("")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(program), "")))
    settings.vizard_browse.click()
    assert settings.vizard_path.text() == str(program) and settings.vizard_clear.isEnabled()
    assert vizard_launcher.find_vizard_executable() == program
    settings.vizard_clear.click()
    assert settings.vizard_path.text() == "Not set" and vizard_launcher.remembered_vizard_executable() == ""
