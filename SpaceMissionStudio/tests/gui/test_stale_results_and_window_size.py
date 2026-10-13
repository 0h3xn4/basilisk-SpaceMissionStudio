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

"""The two blockers fixed first from docs/ux-audit.md: the run views say
when their results are from an earlier version of the scenario (U-20),
and the window fits 1280 x 720, also after a comparison of runs with long
names (U-03)."""

from pathlib import Path

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
    """A main window with template 22 open; closing it discards changes."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def _finish_a_run(window):
    """What a finished run leaves behind, without running Basilisk."""
    from spacemissionstudio.engine.results import ResultSet

    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._on_run_finished(ResultSet(scenario_name=window._last_run_scenario.name))


def test_the_banner_says_when_results_are_from_an_earlier_scenario(window):
    """No banner right after a run. An edit shows it, with Re-run enabled.
    Editing back to the run's scenario hides it, since the comparison is
    by the scenario's SHA-256. An invalid scenario shows it with Re-run
    disabled. Opening another scenario clears the run views and the
    banner."""
    banner = window.stale_results_banner
    assert not banner.isVisibleTo(window)  # no run yet
    _finish_a_run(window)
    assert not banner.isVisibleTo(window)

    name = window.scenario_editor.name_edit
    original = name.text()
    name.setText(original + " (edited)")
    assert banner.isVisibleTo(window)
    assert "previous version" in banner.label.text() and banner.rerun_button.isEnabled()

    name.setText(original)
    assert not banner.isVisibleTo(window)

    window.scenario_editor.epoch_edit.setText("2030-13-45T99:00:00")
    assert banner.isVisibleTo(window)
    assert not banner.rerun_button.isEnabled() and "problem" in banner.label.text()

    assert window.open_path(_TEMPLATES / "01_two_body_circular_orbit.json")
    assert not banner.isVisibleTo(window)


def test_re_run_on_the_banner_starts_a_run(qtbot, monkeypatch):
    """The banner's Re-run button calls the window's Run. ``on_run`` is
    replaced before the window is built (the button connects to it then),
    so no simulation starts: a real one would outlive the test and, where
    the support data is missing, open an error dialog nobody answers."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    calls = []
    monkeypatch.setattr(MainWindow, "on_run", lambda self: calls.append("run"))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    _finish_a_run(window)
    window.scenario_editor.name_edit.setText("edited")
    window.stale_results_banner.rerun_button.click()
    assert calls == ["run"]


def test_the_window_fits_1280_by_720_after_a_comparison(window, qtbot):
    """A result on show (its export buttons visible) and two runs of a
    scenario with a long name, so Results shows "Compare with". The
    window's minimum size still fits 1280 x 720, so resizing it there
    works. Before the fix a real run's window could not go below
    1516 x 758: the End of Life form forced the height; the run label in
    the combo, on the same row as the export buttons, the width."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    window.show()
    name = "22 - Starter: your first LEO satellite, with a much longer name than usual"
    result = ResultSet(scenario_name=name)
    result.add(TimeSeries("my-sat.position_N", [0.0, 60.0], ("x", "y", "z"),  # [s]
                          [[6928.0e3, 0.0, 0.0], [6927.0e3, 450.0e3, 0.0]], units="m"))  # [m]
    window.results_widget.set_result(result, "2030-01-01T08:30:00")
    window.run_history.add({"name": name}, result, "2030-01-01T08:30:00")
    second = window.run_history.add({"name": name}, result, "2030-01-01T08:30:00")
    window.results_widget.set_runs(window.run_history.runs, second)
    assert window.results_widget.compare_combo.isVisible() and window.results_widget.export_button.isVisible()
    qtbot.wait(100)  # [ms] let the layouts take in the new widgets before measuring

    hint = window.minimumSizeHint()
    assert hint.width() <= 1280 and hint.height() <= 720, hint
    window.resize(1280, 720)  # [px]
    assert (window.width(), window.height()) == (1280, 720)
