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
    _settle(qtbot, dialog)
    return dialog


def _settle(qtbot, dialog):
    """Until the worker has finished (its thread too) with a plan or a reason."""
    qtbot.waitUntil(lambda: not dialog.busy() and (dialog.plan() is not None or bool(dialog.status.text())),
                    timeout=30000)


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
    _settle(qtbot, dialog)
    assert dialog.plan().summary.configuration.startswith("LCH")
    assert dialog.plan().summary.stowed_configuration.startswith("OPS")
    assert "45.7 kg imported" in dialog.preview.toPlainText()
    assert dialog.plan().stowed  # the wing is elsewhere in operations


def test_a_damaged_file_is_refused_with_the_reason(qtbot, tmp_path):
    from PySide6.QtWidgets import QDialogButtonBox

    bad = tmp_path / "bad.idm"
    bad.write_text("not a zip")
    dialog = _dialog(qtbot, bad)
    assert "not a ZIP archive" in dialog.status.text() and dialog.plan() is None
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_the_model_editor_imports_and_reimports_and_hands_the_record_on(qtbot, tmp_path):
    """The editor merges the plan into its model (meshes beside the
    scenario), keeps the record for its caller; a second import keeps the
    user's edit; the scenario editor stores the record it is given."""
    from spacemissionstudio import idm, idm_import
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    editor = ModelEditorDialog(None, spacecraft_name="sat-1", base_dir=tmp_path)
    qtbot.addWidget(editor)
    assert editor.import_idm_button.text() == "Import IDM-CIC model..."
    plan = idm_import.plan(idm.load(write_idm(tmp_path / "demosat.idm")))
    summary = editor.import_idm(plan)
    assert len(summary.added) == 11 and (tmp_path / "models" / "sat-1_idm.obj").is_file()
    record = editor.import_record()
    assert (record.spacecraft, record.target, record.format) == ("sat-1", "model", "idm_cic")
    editor.recompute_now()
    assert editor.derived.mass_properties.mass_kg == pytest.approx(38.7)
    body = next(p for p in editor.model().parts if p.name == "Body box")
    editor._model.parts[editor.model().parts.index(body)].mass_kg = 21.0  # an edit
    again = editor.import_idm(plan)
    assert ("Body box", "mass") in again.kept and not again.added
    assert next(p for p in editor.model().parts if p.name == "Body box").mass_kg == 21.0

    scenario_path = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "two_body_validation.json"
    widget = ScenarioEditorWidget()
    qtbot.addWidget(widget)
    widget.from_scenario(load_scenario(scenario_path))
    widget._on_import_recorded(record)
    assert widget.to_scenario().imports == [record]


def test_a_duplicated_imported_part_is_the_user_s_own(qtbot, tmp_path):
    """The copy has no source identifier (two parts may not share one), so
    the model stays valid and a re-import leaves the copy alone."""
    from spacemissionstudio import idm, idm_import
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    editor = ModelEditorDialog(None, spacecraft_name="sat-1", base_dir=tmp_path)
    qtbot.addWidget(editor)
    editor.import_idm(idm_import.plan(idm.load(write_idm(tmp_path / "demosat.idm"))))
    editor.parts_list.setCurrentRow(0)
    editor.duplicate_part()
    twin = editor.model().parts[1]
    assert twin.name == "Body box 2" and twin.source_id == ""
    editor.model().validate("sat-1")
