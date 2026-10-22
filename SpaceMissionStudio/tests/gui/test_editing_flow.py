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


# -- inline editing: devices, dispersions, Add -------------------------------------------------------


def _no_dialog(monkeypatch):
    """Any modal dialog fails the test: M4b's editing opens none."""
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: pytest.fail(f"a dialog opened: {type(self).__name__}"))


def test_a_devices_new_kind_has_its_fields_followed(qtbot):
    """A device's kind changed in its form rebuilds the fields: an edit in
    one of the new ones is applied too."""
    from spacemissionstudio.gui.sensor_actuator_editor import SensorActuatorListWidget
    from spacemissionstudio.schema.scenario import SUPPORTED_ACTUATOR_KINDS, ActuatorConfig

    widget = SensorActuatorListWidget(ActuatorConfig, SUPPORTED_ACTUATOR_KINDS)
    qtbot.addWidget(widget)
    widget._on_add()
    form = widget.inline.form
    form.kind_combo.setCurrentIndex(form.kind_combo.findText("reaction_wheel"))
    qtbot.waitUntil(lambda: not widget.inline.pending, timeout=5000)
    assert widget.to_list()[0].kind == "reaction_wheel"
    x, _y, _z = form._vector_boxes["gsHat_B"]
    x.setValue(0.5)  # a field the new kind built
    assert widget.inline.pending
    qtbot.waitUntil(lambda: not widget.inline.pending, timeout=5000)
    assert widget.to_list()[0].params["gsHat_B"][0] == 0.5


def test_remove_and_reload_drop_an_edit_not_applied(qtbot):
    """An edit waiting in a device's form goes with its row (Remove) or its
    list (another spacecraft's devices): it is never written to another row."""
    from spacemissionstudio.gui.sensor_actuator_editor import SensorActuatorListWidget
    from spacemissionstudio.schema.scenario import SUPPORTED_SENSOR_KINDS, SensorConfig

    widget = SensorActuatorListWidget(SensorConfig, SUPPORTED_SENSOR_KINDS)
    qtbot.addWidget(widget)
    widget.from_list([SensorConfig(kind="imu", name="a", params={}), SensorConfig(kind="imu", name="b", params={})])
    widget.list_widget.setCurrentRow(0)
    widget.inline.form.name_edit.setText("a-renamed")
    widget._on_remove()
    assert [item.name for item in widget.to_list()] == ["b"]

    widget.list_widget.setCurrentRow(0)
    widget.inline.form.name_edit.setText("b-renamed")
    widget.from_list([SensorConfig(kind="imu", name="c", params={})])
    qtbot.wait(400)  # [ms] past the settle time
    assert [item.name for item in widget.to_list()] == ["c"] and widget.inline.form is None


def test_a_dispersion_needs_a_spacecraft_to_be_added(qtbot, monkeypatch, reported):
    """With no spacecraft there is nothing to disperse: Add says so and adds nothing."""
    from spacemissionstudio.gui.monte_carlo_editor import DispersionListWidget

    _no_dialog(monkeypatch)
    widget = DispersionListWidget()
    qtbot.addWidget(widget)
    widget._on_add()
    assert widget.to_list() == []
    assert reported and reported[0][1] == "warning" and "no spacecraft" in reported[0][0]


def test_a_device_edited_in_a_spacecraft_page_reaches_the_scenario(window, qtbot, monkeypatch):
    """A device added and edited inline on a spacecraft's page is in the
    scenario, with no dialog, and Undo takes the edit back."""
    _no_dialog(monkeypatch)
    assert window.open_path(_TEMPLATES / "07_attitude_pointing_with_adcs_hardware.json")  # devices: full attitude
    editor = window.scenario_editor
    name = editor.spacecraft_list.to_list()[0].name
    editor.show_spacecraft(0)
    node = editor._spacecraft_nodes[0]
    devices = node.form.sensor_list
    before = len(editor.to_scenario().spacecraft[0].sensors)
    devices._on_add()
    devices.inline.form.name_edit.setText("st-inline")
    devices.inline.flush()
    qtbot.waitUntil(lambda: any(s.name == "st-inline" for s in editor.to_scenario().spacecraft[0].sensors),
                    timeout=5000)
    sensors = editor.to_scenario().spacecraft[0].sensors
    assert len(sensors) == before + 1 and editor.to_scenario().spacecraft[0].name == name

    window._history_timer.stop()
    window._record_history()
    window.undo_action.trigger()
    assert [s.name for s in editor.to_scenario().spacecraft[0].sensors] != [s.name for s in sensors]


def test_add_opens_a_new_spacecrafts_and_stations_page(window, monkeypatch):
    """Add in the Scenario editor adds the spacecraft or ground station and
    shows its page: no dialog first."""
    _no_dialog(monkeypatch)
    editor = window.scenario_editor
    count = len(editor.spacecraft_list.to_list())
    editor.spacecraft_list.add_button.click()
    assert len(editor.spacecraft_list.to_list()) == count + 1
    new = editor.spacecraft_list.to_list()[-1].name
    assert editor.page_tree.current_page() is editor._spacecraft_nodes[-1].holder
    assert editor._spacecraft_nodes[-1].config.name == new and new not in [
        c.name for c in editor.spacecraft_list.to_list()[:-1]]

    stations = len(editor.ground_station_list.to_list())
    editor.ground_station_list.add_button.click()
    assert len(editor.ground_station_list.to_list()) == stations + 1
    assert editor.page_tree.current_page() is editor._station_nodes[-1].holder
    editor.to_scenario()  # both validate


def test_the_inline_device_form_shows_its_card_only_for_a_picked_device(qtbot):
    """Embedded under the list, the device form has no scroll area of its
    own, and its device card shows only once a real device is picked (an
    empty card showed after the move)."""
    from PySide6.QtWidgets import QScrollArea

    from spacemissionstudio.gui.sensor_actuator_editor import SensorActuatorListWidget
    from spacemissionstudio.schema.scenario import SUPPORTED_SENSOR_KINDS, SensorConfig

    widget = SensorActuatorListWidget(SensorConfig, SUPPORTED_SENSOR_KINDS)
    qtbot.addWidget(widget)
    widget.show()
    widget._on_add()  # a star tracker, which the catalog has
    qtbot.waitUntil(lambda: not widget.inline.form.findChildren(QScrollArea), timeout=5000)  # the old ones deleted
    form = widget.inline.form
    assert form.catalog_combo.count() > 1 and form.catalog_combo.currentIndex() == 0
    assert form._card.isHidden()
    form.catalog_combo.setCurrentIndex(1)
    assert not form._card.isHidden() and form.catalog_info_label.text()
