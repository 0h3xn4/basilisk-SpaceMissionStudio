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

"""The editing flow (UI overhaul M4b): Explain as Scenario › Overview,
asked for 250 ms after an edit and computed off the GUI thread; the
Form · JSON toggle, which applies the text before going back to the form
and refuses text that does not apply."""

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
    """A main window with template 22 open."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    qtbot.waitUntil(lambda: not w.scenario_explainer_widget.pending, timeout=10000)
    return w


def _scenario():
    from spacemissionstudio.schema import load_scenario

    return load_scenario(_TEMPLATES / "22_starter_first_leo_satellite.json")


# -- Explain: Scenario › Overview ---------------------------------------------------------------


def test_overview_is_the_trees_first_node_and_view_explain_opens_it(window):
    """Explain is no longer a panel: it is the Scenario tree's first node,
    and View › Explain shows it in the Scenario area."""
    tree = window.scenario_editor.page_tree
    assert tree.tree.topLevelItem(0) is window.overview_item
    assert window.overview_item.text(0) == "Overview"
    assert all(dock.widget() is not window.scenario_explainer_widget for dock in window._docks())
    window.commands.action("view.explain").trigger()
    assert window.shell.current_area() == "scenario"
    assert tree.current_page() is window.scenario_explainer_widget


def test_opening_a_scenario_still_shows_its_scenario_page(window):
    """Overview comes first in the tree, but opening a file shows the page
    it showed before (the Scenario page), not Overview."""
    assert window.scenario_editor.page_tree.current_page() is window.scenario_editor.scenario_page


def test_an_edit_is_explained_after_the_wait_from_a_worker(window, qtbot):
    """The explanation is asked for 250 ms after the last edit, not during
    the keystroke, and computed in a worker thread."""
    from PySide6.QtCore import QThread

    from spacemissionstudio.gui import scenario_explainer_widget as module

    assert module.EXPLAIN_SETTLE_MS == 250  # [ms]
    explainer = window.scenario_explainer_widget
    threads = []
    real_explain = module.explain

    def recording_explain(scenario):
        threads.append(QThread.currentThread())
        return real_explain(scenario)

    module.explain = recording_explain
    try:
        window.scenario_editor.name_edit.setText("renamed")
        assert explainer.pending and threads == []  # nothing computed during the keystroke
        assert explainer._timer.isActive() and explainer._timer.interval() == 250  # [ms]
        qtbot.waitUntil(lambda: not explainer.pending, timeout=10000)
    finally:
        module.explain = real_explain
    assert len(threads) == 1 and threads[0] is not window.thread()
    assert not explainer._headline_label.isHidden() and explainer._headline_label.text()


def test_typing_asks_for_one_explanation_and_drops_an_overtaken_one(window, qtbot):
    """Keystrokes inside the wait ask for one explanation; an answer a later
    edit overtook is not shown."""
    from spacemissionstudio.gui import scenario_explainer_widget as module

    explainer = window.scenario_explainer_widget
    calls = []
    real_explain = module.explain
    module.explain = lambda scenario: (calls.append(scenario.name), real_explain(scenario))[1]
    try:
        for text in ("a", "ab", "abc"):
            window.scenario_editor.name_edit.setText(text)
        qtbot.waitUntil(lambda: not explainer.pending, timeout=10000)
        assert calls == ["abc"]

        shown = []
        explainer.explained.connect(lambda: shown.append(explainer._number))
        explainer.request(_scenario())
        explainer._timer.stop()
        explainer._start_worker()  # computing the first...
        explainer.request(_scenario())  # ...when a second is asked for
        first = explainer._worker
        first.wait(10000)
        qtbot.waitUntil(lambda: not explainer.pending, timeout=10000)
        assert shown == [explainer._number]  # only the second was shown
    finally:
        module.explain = real_explain


def test_a_scenario_that_does_not_validate_shows_the_placeholder_at_once(window):
    """No wait for "fix it first": the placeholder shows during the edit."""
    explainer = window.scenario_explainer_widget
    window.scenario_editor.name_edit.setText("")
    assert not explainer.pending and not explainer._placeholder_label.isHidden()


def test_a_closed_window_starts_no_explanation_and_stops_autosaving(window, qtbot):
    """Closing waits for a running explanation, drops a waiting one, and
    stops the autosave: a closed window writes nothing more."""
    window.scenario_editor.name_edit.setText("renamed before closing")
    assert window.scenario_explainer_widget._timer.isActive()
    window._mark_clean()
    assert window.close()
    assert not window.scenario_explainer_widget._timer.isActive()
    assert window.scenario_explainer_widget._worker is None
    assert not window._autosave_timer.isActive()


# -- Form · JSON -----------------------------------------------------------------------------------


def test_the_toggle_is_in_the_scenario_areas_header(window):
    """Form · JSON replaces the tree's JSON node: a toggle in the Scenario
    area's header, Form at first."""
    editor = window.scenario_editor
    assert window.shell.page("scenario").header.isAncestorOf(editor.mode_toggle)
    assert "JSON" not in [path for path, _item in editor.page_tree.paths()]
    assert editor.form_button.isChecked() and not editor.json_mode
    editor.json_button.click()
    assert editor.json_mode and editor.mode_stack.currentWidget() is editor.json_page
    assert window.top_bar.breadcrumb_label.text() == "Scenario › JSON"
    editor.form_button.click()
    assert not editor.json_mode and editor.mode_stack.currentWidget() is editor.page_tree
    assert window.top_bar.breadcrumb_label.text() == "Scenario › Scenario"


def test_back_to_form_applies_a_waiting_edit(window):
    """An edit not yet applied (inside the 500 ms wait) is applied when the
    form is shown again."""
    editor = window.scenario_editor
    editor.json_button.click()
    data = json.loads(editor.json_view.edit.toPlainText())
    data["name"] = "renamed in JSON"
    editor.json_view.edit.setPlainText(json.dumps(data, indent=2))
    assert editor.json_view.dirty  # waiting
    editor.form_button.click()
    assert not editor.json_mode and editor.name_edit.text() == "renamed in JSON"


def test_back_to_form_is_refused_while_the_json_does_not_apply(window):
    """Text that does not parse keeps JSON mode: the toggle stays on JSON,
    the banner says what is wrong and how to go back."""
    editor = window.scenario_editor
    editor.json_button.click()
    editor.json_view.edit.setPlainText("{")
    editor.form_button.click()
    assert editor.json_mode and editor.json_button.isChecked() and not editor.form_button.isChecked()
    view = editor.json_view
    assert view.banner.isVisibleTo(view) and "Discard it to go back to the form" in view.banner.label.text()
    assert editor.json_button.text() == "JSON (1)"  # the problem counted where it is


def test_discard_puts_the_scenarios_text_back(window):
    """Discard drops the edit that does not apply: the text is the
    scenario's again, its problem goes, and the form can be shown."""
    from spacemissionstudio.schema.scenario import scenario_text

    editor = window.scenario_editor
    editor.json_button.click()
    editor.json_view.edit.setPlainText("{")
    editor.json_view.flush()
    assert editor.json_view.discard_button.isVisibleTo(editor.json_view)
    editor.json_view.discard_button.click()
    assert editor.json_view.edit.toPlainText() == scenario_text(editor.to_scenario())
    assert editor.json_view.error == "" and editor.json_button.text() == "JSON"
    assert editor.set_json_mode(False) and not editor.json_mode


def test_a_problem_in_the_form_leaves_json_mode(window):
    """A problem of a form field, double-clicked in Problems, shows the form
    (when the JSON applies)."""
    editor = window.scenario_editor
    editor.json_button.click()
    editor.name_edit.setText("")  # an edit the form makes: its problem is the scenario name's
    problems = window.problems_widget
    row = next(i for i, (_severity, text) in enumerate(problems.problems) if "name" in text)
    problems.table.activated.emit(problems.index_of(row))
    assert not editor.json_mode
