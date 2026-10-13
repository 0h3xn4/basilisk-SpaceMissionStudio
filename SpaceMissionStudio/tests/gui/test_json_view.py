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


"""The JSON page (docs/ux-audit.md U-16): the scenario as it is saved, an
edit there applies to every page, an edit elsewhere shows there; text that
is not JSON is marked at its line and blocks the run; Problems opens it."""

import json
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
    """A main window with template 22 open, its JSON page shown."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    w.scenario_editor.show_json()
    return w


def _set(view, text):
    view.edit.setPlainText(text)
    view.flush()


def test_the_page_shows_the_saved_text(window):
    """The JSON page holds exactly what Save writes."""
    from spacemissionstudio.schema.scenario import scenario_text

    editor = window.scenario_editor
    assert editor.json_view.edit.toPlainText() == scenario_text(editor.to_scenario())


def test_an_edit_in_the_json_applies_everywhere(window):
    """A new name typed in the JSON shows on the Scenario page, marks the
    scenario changed and can be undone."""
    editor = window.scenario_editor
    data = json.loads(editor.json_view.edit.toPlainText())
    data["name"] = "renamed in JSON"
    data["spacecraft"][0]["dry_mass_kg"] = 175.0  # [kg]
    _set(editor.json_view, json.dumps(data, indent=2))
    assert editor.name_edit.text() == "renamed in JSON"
    assert editor.to_scenario().spacecraft[0].dry_mass_kg == 175.0  # [kg]
    assert editor.page_tree.current_page() is editor.json_page
    assert window.isWindowModified() or "Unsaved" in window.top_bar.detail_label.text()


def test_an_edit_elsewhere_shows_in_the_json(window):
    """Back on the JSON page, an edit made on another page is there."""
    editor = window.scenario_editor
    editor.show_scenario_page()
    editor.name_edit.setText("renamed on the page")
    editor.show_json()
    assert json.loads(editor.json_view.edit.toPlainText())["name"] == "renamed on the page"


def test_text_that_is_not_json_is_marked_and_blocks_the_run(window):
    """Broken JSON is not applied: its line is marked, the banner and
    Problems say where, the scenario is invalid until it is fixed."""
    from spacemissionstudio.schema.scenario import ScenarioValidationError

    editor = window.scenario_editor
    view = editor.json_view
    good = view.edit.toPlainText()
    _set(view, good.replace('"name": ', '"name" ', 1))
    assert view.error.startswith("JSON view: line 2, column 10: Expecting ':' delimiter")
    assert view.banner.isVisibleTo(view) and len(view.edit.extraSelections()) == 1
    assert editor.name_edit.text() == "22 - Starter: your first LEO satellite"  # not applied
    with pytest.raises(ScenarioValidationError, match="JSON view"):
        editor.to_scenario()
    assert editor.page_tree.problem_count(editor.json_item) == 1

    editor.show_scenario_page()  # leaving keeps the broken text, and the problem
    editor.show_json()
    assert view.dirty and view.error

    _set(view, good)
    assert view.error == "" and not view.banner.isVisibleTo(view) and view.edit.extraSelections() == []
    editor.to_scenario()


def test_json_that_is_not_a_scenario_is_not_applied(window):
    """Valid JSON with a field the schema does not know is refused."""
    editor = window.scenario_editor
    data = json.loads(editor.json_view.edit.toPlainText())
    data["spacecraft"][0]["warp_drive"] = True
    _set(editor.json_view, json.dumps(data))
    assert "malformed scenario structure" in editor.json_view.error and "warp_drive" in editor.json_view.error


def test_a_value_the_schema_rejects_is_applied_and_shown_at_its_field(window):
    """JSON that loads but holds a bad value is applied, like a file with
    one: Problems names it and the page shows the field."""
    editor = window.scenario_editor
    data = json.loads(editor.json_view.edit.toPlainText())
    data["epoch_utc"] = "2030-13-45T99:00:00"
    _set(editor.json_view, json.dumps(data, indent=2))
    assert editor.json_view.error == ""
    assert editor.epoch_edit.text() == "2030-13-45T99:00:00"
    assert any(text.startswith("scenario.epoch_utc") for _severity, text in editor.problems)


def test_problems_open_the_json_page(window):
    """Double-clicking the JSON page's problem opens the page."""
    editor = window.scenario_editor
    _set(editor.json_view, "{")
    window.show_view(window.results_widget)
    problems = window.problems_widget
    row = next(i for i, (_severity, text) in enumerate(problems.problems) if text.startswith("JSON view"))
    problems.list.itemActivated.emit(problems.list.item(row))
    assert window.current_view() is editor and editor.page_tree.current_page() is editor.json_page


def test_opening_another_scenario_drops_an_edit_not_applied(window):
    """A broken edit belongs to the scenario it was made in."""
    editor = window.scenario_editor
    _set(editor.json_view, "{")
    assert window.open_path(_TEMPLATES / "23_starter_complete_small_satellite.json")
    assert editor.json_view.error == "" and not editor.json_view.dirty
    assert json.loads(editor.json_view.edit.toPlainText())["name"].startswith("23")
    editor.to_scenario()
