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
"""Messages without message boxes (docs/ux-audit.md U-39): routine outcomes
are toasts, the status bar and the Log; input a dialog refuses is shown in
the dialog; message boxes are kept for confirming what cannot be undone."""

import logging
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_GUI = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "gui"


def test_no_information_warning_or_critical_message_box_is_left():
    """Only questions remain, each confirming something that cannot be
    undone or asking consent (a download, a restore)."""
    found = []
    for path in sorted(_GUI.glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"QMessageBox\.(information|warning|critical)\(", line):
                found.append(f"{path.name}:{number}")
    assert found == []


def test_report_shows_a_toast_writes_the_status_bar_and_the_log(qtbot, caplog, reported):
    """A report is a toast with the first line, the status bar and a Log
    line at the matching level; a longer error points to the Log."""
    from PySide6.QtWidgets import QLabel, QMainWindow

    from spacemissionstudio.gui.feedback import report

    window = QMainWindow()
    qtbot.addWidget(window)
    child = QLabel("x", window)
    window.setCentralWidget(child)
    with caplog.at_level(logging.INFO, logger="spacemissionstudio.gui"):
        report(child, "Could not save the scenario to /x: denied\nThe previous file is unchanged.")
        report(child, "Exported 3 events to /y", kind="success")
    assert reported == [("Could not save the scenario to /x: denied (more in the Log)", "error"),
                        ("Exported 3 events to /y", "success")]
    assert window.statusBar().currentMessage() == "Exported 3 events to /y"
    levels = [(r.levelno, r.getMessage()) for r in caplog.records if r.name == "spacemissionstudio.gui"]
    assert levels[0] == (logging.ERROR, "Could not save the scenario to /x: denied\nThe previous file is unchanged.")
    assert levels[1] == (logging.INFO, "Exported 3 events to /y")


def test_report_without_a_window_only_logs(caplog, reported):
    """With no widget there is nowhere to show a toast; the Log still has it."""
    from spacemissionstudio.gui.feedback import report

    with caplog.at_level(logging.WARNING, logger="spacemissionstudio.gui"):
        report(None, "Reference data: space weather: could not fetch", kind="warning")
    assert reported == [] and "could not fetch" in caplog.text


def test_a_dialog_error_sits_above_the_buttons_and_keeps_the_dialog_open(qtbot):
    """A dialog that refuses its input on OK says why in a line just above
    its buttons and stays open (U-39)."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel

    from spacemissionstudio.gui.constellation_dialog import WalkerConstellationDialog
    from spacemissionstudio.gui.feedback import clear_dialog_error, dialog_error_text

    dialog = WalkerConstellationDialog([])
    qtbot.addWidget(dialog)
    dialog.total_satellites.setValue(5)
    dialog.num_planes.setValue(2)  # 5 satellites do not split evenly into 2 planes
    dialog._on_accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog_error_text(dialog).startswith("This constellation cannot be made:")
    layout = dialog.layout()
    label = dialog.findChild(QLabel, "dialogError")
    assert layout.indexOf(label) == layout.indexOf(dialog.findChild(QDialogButtonBox)) - 1
    clear_dialog_error(dialog)
    assert dialog_error_text(dialog) == ""


def test_editor_dialogs_say_why_ok_did_nothing_in_the_dialog(qtbot):
    """The command, dispersion and phasing dialogs refuse input on OK with
    their own error line, not a box on top (U-39)."""
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.gui.feedback import dialog_error_text
    from spacemissionstudio.gui.phasing_formation_dialog import PhasingFormationDialog

    dialog = PhasingFormationDialog([])
    qtbot.addWidget(dialog)
    dialog._on_accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog_error_text(dialog)  # names what is wrong: no chief, or the request


def test_confirmations_name_the_object_and_the_consequence(qtbot, monkeypatch):
    """The questions left (U-39): the unsaved-changes question says which
    scenario and that changes not saved cannot be recovered."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda parent, title, text, *a, **k: asked.append(text)
                                     or QMessageBox.StandardButton.Cancel))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    window.scenario_editor.name_edit.setText("my mission")
    window._mark_dirty()
    assert window._confirm_discard_unsaved() is False
    assert asked == ["Save the changes to my mission first? Changes not saved cannot be recovered."]
    window._mark_clean()


def test_a_long_path_is_reported_whole_and_wraps_in_the_toast(qtbot, reported):
    """A path longer than a toast line (macOS temporary folders are) is
    not cut: the message keeps it whole, and the toast breaks it after its
    separators so it wraps inside the toast's width."""
    from PySide6.QtWidgets import QLabel, QMainWindow

    from spacemissionstudio.gui.feedback import _Toast, report

    window = QMainWindow()
    qtbot.addWidget(window)
    window.setCentralWidget(QLabel("x"))
    path = "/private/var/folders/36/" + "/".join(["tjdph2t965j8snz9_vkdnw0r0000gn"] * 6) + "/output.csv"
    report(window.centralWidget(), f"Exported the mission output to {path}", kind="success")
    assert reported == [(f"Exported the mission output to {path}", "success")]
    toast = _Toast(window, f"Exported the mission output to {path}", "success")
    assert toast.text().replace("​", "") == f"Exported the mission output to {path}"
    assert toast.width() <= 360 and toast.height() > toast.fontMetrics().height() * 2  # [px] wrapped, not clipped
