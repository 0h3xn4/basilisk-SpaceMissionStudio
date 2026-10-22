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

"""Run > Run (UI overhaul M5b): the run mode as a segmented control in the
Run area's header, and on one page what the next run uses -- Live plot
and the Vizard options for a single run, the archive folder of a Monte
Carlo batch (remembered per scenario), the spacecraft and program of a
SIL run."""

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


def test_the_segmented_control_and_the_mode_follow_each_other(window):
    """Clicking a segment sets the run mode (the top bar's menu and Run's
    tooltip follow); a mode set elsewhere checks its segment. The page
    shows the chosen mode's options, and Vizard only where a run has it."""
    control, page = window.run_mode_control, window.run_page
    assert window.shell.page("run").header.isAncestorOf(control)
    assert control.buttons["single"].isChecked() and page.stack.currentWidget() is page.pages["single"]
    control.buttons["monte_carlo"].click()
    assert window.run_mode == "monte_carlo" and window.run_mode_button.text().startswith("Monte Carlo")
    assert page.stack.currentWidget() is page.pages["monte_carlo"] and page.vizard_section.isHidden()
    window.set_run_mode("sil")
    assert control.buttons["sil"].isChecked() and page.stack.currentWidget() is page.pages["sil"]
    assert not page.vizard_section.isHidden()


def test_live_plot_is_one_setting_on_the_page_and_in_the_palette(window):
    """The page's Live plot box and the Live plot command are one setting."""
    check, action = window.run_page.live_plot_check, window.live_plot_action
    check.setChecked(not action.isChecked())
    assert action.isChecked() is check.isChecked()
    action.trigger()
    assert check.isChecked() is action.isChecked()


def test_the_vizard_options_apply_as_they_are_edited(window, qtbot):
    """No OK: an edit of the Vizard form is the next run's request."""
    window.show()
    window.on_configure_vizard()
    assert window.shell.current_area() == "run" and window.run_page.vizard_section.isVisibleTo(window)
    form = window.run_page.vizard_form
    form.live_stream_radio.setChecked(True)
    assert window._vizard_request is not None and window._vizard_request.live_stream is True


def test_the_monte_carlo_folder_is_used_without_asking_and_remembered_per_scenario(window, monkeypatch, tmp_path):
    """A folder in the field starts the batch without the folder picker; it
    is remembered for that scenario, not for another one."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.run_worker import MonteCarloWorker

    def no_picker(*_args, **_kwargs):
        raise AssertionError("the folder picker opened")

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(no_picker))
    monkeypatch.setattr(MonteCarloWorker, "start", lambda self: None)  # no batch is flown
    mc = _TEMPLATES / "09_monte_carlo_dispersion_analysis.json"
    assert window.open_path(mc)
    window.set_run_mode("monte_carlo")
    archive = tmp_path / "mc_archive"
    window.run_page.archive_edit.setText(str(archive))
    window.run_page.archive_edit.editingFinished.emit()
    window.on_run()
    assert window._mc_worker is not None and window._mc_worker.archive_dir == archive
    window._mc_worker = None
    window._set_running(False)
    window._dirty = False
    assert window.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    assert window.run_page.archive_dir() == ""  # another scenario, its own folder
    assert window.open_path(mc)
    assert window.run_page.archive_dir() == str(archive)


def test_an_empty_monte_carlo_folder_falls_back_to_the_picker(window, monkeypatch, tmp_path):
    """With no folder on the page, Run asks for one, and the page keeps it."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui.run_worker import MonteCarloWorker

    archive = tmp_path / "picked"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(archive)))
    monkeypatch.setattr(MonteCarloWorker, "start", lambda self: None)
    assert window.open_path(_TEMPLATES / "09_monte_carlo_dispersion_analysis.json")
    window.set_run_mode("monte_carlo")
    assert window.run_page.archive_dir() == ""
    window.on_run()
    assert window._mc_worker.archive_dir == archive and window.run_page.archive_dir() == str(archive)


def test_sil_without_a_program_says_what_to_do(window, monkeypatch):
    """A SIL run whose program is not chosen and confirmed does not start;
    a toast says where to choose it and the page shows the form."""
    from spacemissionstudio.gui import fsw_workbench_widget, main_window

    monkeypatch.setattr(fsw_workbench_widget, "exportable_reason", lambda scenario, spacecraft: None)
    toasts, runs = [], []
    monkeypatch.setattr(main_window, "show_toast", lambda parent, text, **k: toasts.append(text))
    monkeypatch.setattr(window, "_launch_run", lambda sil=None: runs.append(sil))
    window.set_run_mode("sil")
    window.on_run()
    assert runs == [] and window.current_view() is window.run_page
    assert window.run_page.sil_combo.currentText() == "my-sat" and window.run_page.sil_form is not None
    assert toasts and "Run > Run" in toasts[-1]
