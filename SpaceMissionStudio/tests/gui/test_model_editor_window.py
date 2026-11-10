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

"""The 3D model editor as a window of its own: not modal and not attached
to the main window (a window manager moved the whole application with a
modal dialog), one per spacecraft, applied to the spacecraft as it is when
OK is clicked; and it writes files beside the scenario only where it may
(not into the built-in templates' folder)."""

import dataclasses
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
def answers(monkeypatch):
    """The answers the next questions get (Discard once the list is empty);
    the questions asked are kept in ``answers.asked``."""
    from PySide6.QtWidgets import QMessageBox

    queue = []

    def question(_parent, title, *_args, **_kwargs):
        queue_asked.append(title)
        return queue.pop(0) if queue else QMessageBox.StandardButton.Discard

    queue_asked = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    holder = type("Answers", (), {})()
    holder.queue, holder.asked = queue, queue_asked
    return holder


@pytest.fixture
def window(qtbot, answers):
    """A main window with template 22 open (one spacecraft, orbit only)."""
    from spacemissionstudio.gui.main_window import MainWindow

    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def test_the_editor_is_a_window_of_its_own(window):
    """3D Model... opens the editor as a top-level window with minimise and
    maximise buttons, not modal and with no transient parent, so it moves
    on its own and the main window stays usable; asking again brings the
    same window back rather than a second one."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    spacecraft_list = window.scenario_editor.spacecraft_list
    window.model_3d_action.trigger()
    [editor] = spacecraft_list.model_editors()
    assert editor.isVisible() and editor.isWindow()
    assert not editor.isModal() and editor.windowModality() == Qt.WindowModality.NonModal
    assert editor.windowHandle().transientParent() is None
    assert editor.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
    assert editor.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
    assert QApplication.activeModalWidget() is None
    window.model_3d_action.trigger()
    assert spacecraft_list.model_editors() == [editor]


def test_ok_applies_to_the_spacecraft_as_it_is_then(window):
    """While the editor is open the spacecraft is renamed and edited in the
    main window: the editor follows the name, and its OK writes the model
    into the renamed spacecraft, keeping the other edit."""
    spacecraft_list = window.scenario_editor.spacecraft_list
    editor = spacecraft_list.open_model_editor(0)
    editor.add_part("box")
    edited = dataclasses.replace(spacecraft_list.to_list()[0], name="renamed", drag_coeff=2.5)  # [-]
    spacecraft_list.replace_config(0, edited)
    assert editor.windowTitle() == "3D model: renamed"
    editor._on_ok()
    after = spacecraft_list.to_list()[0]
    assert after.name == "renamed" and after.drag_coeff == pytest.approx(2.5)  # [-]
    assert [part.shape for part in after.model.parts] == ["box"]
    assert after.dry_mass_kg == pytest.approx(after.model.parts[0].mass_kg)  # [kg]
    assert not editor.isVisible() and spacecraft_list.model_editors() == []


def test_ok_for_a_removed_spacecraft_keeps_the_window_open(window, monkeypatch):
    """The spacecraft was removed meanwhile: OK says so and keeps the
    window (and its edits) open; nothing is added to the scenario."""
    from spacemissionstudio.gui import model_editor_dialog

    shown = []
    monkeypatch.setattr(model_editor_dialog, "show_dialog_error", lambda _dialog, text: shown.append(text))
    spacecraft_list = window.scenario_editor.spacecraft_list
    editor = spacecraft_list.open_model_editor(0)
    editor.add_part("box")
    spacecraft_list.from_list([])
    editor._on_ok()
    assert editor.isVisible() and "no spacecraft named" in shown[0]
    assert spacecraft_list.to_list() == []
    editor.discard()
    assert spacecraft_list.model_editors() == []


def test_closing_an_edited_editor_asks_first(window, answers):
    """Cancel, Esc or the close button on an editor with edits asks first:
    Cancel keeps it open, Discard closes it without applying. An editor
    with no edits closes without asking."""
    from PySide6.QtWidgets import QMessageBox

    spacecraft_list = window.scenario_editor.spacecraft_list
    editor = spacecraft_list.open_model_editor(0)
    editor.close()
    assert answers.asked == [] and not editor.isVisible()

    editor = spacecraft_list.open_model_editor(0)
    editor.add_part("box")
    answers.queue.append(QMessageBox.StandardButton.Cancel)
    editor.close()
    assert answers.asked == ["Discard the changes?"] and editor.isVisible()
    editor.reject()  # the next answer is Discard
    assert not editor.isVisible() and spacecraft_list.to_list()[0].model is None


def test_replacing_the_scenario_asks_about_an_edited_editor(window, answers):
    """File › New with an editor holding edits asks first: Cancel keeps the
    scenario and the editor, Discard closes the editor with the scenario."""
    from PySide6.QtWidgets import QMessageBox

    spacecraft_list = window.scenario_editor.spacecraft_list
    name = spacecraft_list.to_list()[0].name
    editor = spacecraft_list.open_model_editor(0)
    editor.add_part("box")
    answers.queue.append(QMessageBox.StandardButton.Cancel)
    window.on_new()
    assert answers.asked == ["3D model editor open"] and editor.isVisible()
    assert [c.name for c in spacecraft_list.to_list()] == [name]
    window.on_new()
    assert not editor.isVisible() and spacecraft_list.model_editors() == []


def test_a_spacecraft_page_opens_the_one_editor_of_its_spacecraft(window):
    """The 3D model tab of a spacecraft's page opens the same editor as
    3D Model..., once per spacecraft."""
    editor_widget = window.scenario_editor
    editor_widget.show_spacecraft(0)
    form = editor_widget._spacecraft_nodes[0].form
    form.open_model_button.click()
    form.open_model_button.click()
    window.model_3d_action.trigger()
    assert len(editor_widget.spacecraft_list.model_editors()) == 1


def test_a_spacecraft_dialog_waits_for_its_editor(qtbot, monkeypatch):
    """The Add or Edit spacecraft dialog does not close while the 3D model
    editor it opened is open (its edits would be lost); once the editor
    is closed, it does."""
    from spacemissionstudio.gui import spacecraft_editor
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    said = []
    monkeypatch.setattr(spacecraft_editor, "report", lambda _parent, text, **_kwargs: said.append(text))
    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._on_open_model_editor()
    editor = dialog._model_editor
    assert editor.isVisible() and not editor.isModal()
    dialog.reject()
    assert dialog.isVisible() and "still open" in said[0]
    editor.discard()
    dialog.reject()
    assert not dialog.isVisible()


def test_the_editor_writes_beside_the_scenario_only_where_it_may(qtbot, tmp_path):
    """No file is written into the built-in templates' folder (an installed
    one is read-only: the IDM-CIC import failed with Permission denied) or
    for an unsaved scenario; the editor follows the scenario's folder, so a
    Save As while it is open lets it write."""
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    folder = [TEMPLATES_DIR]
    editor = ModelEditorDialog(None, spacecraft_name="sat-1", base_dir=lambda: folder[0])
    qtbot.addWidget(editor)
    assert "built-in template" in editor._write_problem()
    with pytest.raises(ValueError, match="built-in template"):
        editor.import_idm(None)
    obj = tmp_path / "source" / "cube.obj"
    obj.parent.mkdir()
    obj.write_text("o cube\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    editor.import_obj(obj, copy_to_scenario=True)
    assert not (TEMPLATES_DIR / "models").exists()

    folder[0] = None
    assert "not saved" in editor._write_problem()
    folder[0] = tmp_path / "mission"
    folder[0].mkdir()
    assert editor._write_problem() == ""
    editor.import_obj(obj, copy_to_scenario=True)
    assert (tmp_path / "mission" / "models" / "cube.obj").is_file()
