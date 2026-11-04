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
"""The 3D model editor's IDM-CIC import (gui.idm_import_dialog): the
file read and the import planned off the GUI thread, the configuration,
stowed configuration and body element offered from the file, the
summary shown before anything is applied, and a damaged file refused
with the reason. The model is the synthetic fixture (tests/data/idm)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
from idm_fixtures import write_idm  # noqa: E402

pytestmark = pytest.mark.requires_gui


def _dialog(qtbot, path):
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(path)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.plan() is not None or bool(dialog.status.text()), timeout=30000)
    return dialog


def test_the_dialog_previews_the_import_and_offers_the_file_s_choices(qtbot, tmp_path):
    """The defaults first; choosing the launch configuration and a stowed
    one plans again, with the spare battery and full tank, before Import."""
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = _dialog(qtbot, write_idm(tmp_path / "demosat.idm"))
    assert "© CNES" in dialog.credit.text() and "not affiliated" in dialog.credit.text()
    combos = dialog.configuration_combo
    assert [combos.itemText(i) for i in range(combos.count())] == ["Default values", "OPS (Operations)",
                                                                    "LCH (Launch)"]
    assert [dialog.body_combo.itemText(i) for i in range(dialog.body_combo.count())][1:] == ["Bus", "Camera",
                                                                                             "Ground jig"]
    assert "38.7 kg imported" in dialog.preview.toPlainText()
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok.isEnabled() and ok.text() == "Import"
    dialog.configuration_combo.setCurrentIndex(2)
    dialog.stowed_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: dialog.plan() is not None and dialog.plan().summary.configuration.startswith("LCH")
                    and dialog.plan().summary.stowed_configuration.startswith("OPS"), timeout=30000)
    assert "45.7 kg imported" in dialog.preview.toPlainText()
    assert dialog.plan().stowed  # the wing is elsewhere in operations


def test_a_damaged_file_is_refused_with_the_reason(qtbot, tmp_path):
    from PySide6.QtWidgets import QDialogButtonBox

    bad = tmp_path / "bad.idm"
    bad.write_text("not a zip")
    dialog = _dialog(qtbot, bad)
    assert "not a ZIP archive" in dialog.status.text() and dialog.plan() is None
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
