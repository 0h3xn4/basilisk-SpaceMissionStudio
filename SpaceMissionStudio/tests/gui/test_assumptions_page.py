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
"""Scenario › Assumptions (transparency plan, Phase 3d): the configuration
file the scenario names, every parameter with its value in effect, and a
value changed by writing that parameter's line into the file."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture
def page(qtbot, tmp_path):
    from spacemissionstudio.gui.assumptions_page import AssumptionsPage

    view = AssumptionsPage()
    view.set_base_dir_provider(lambda: tmp_path)
    qtbot.addWidget(view)
    return view


def _row(page, name):
    return page._names.index(name)


def test_without_a_file_every_parameter_shows_its_default(page):
    """No file named: every parameter of the registry is listed, under its
    area, at its default, none in bold, and nothing can be set."""
    from spacemissionstudio.config import registry

    names = [n for n in page._names if n is not None]
    assert names == [p.name for p in registry.parameters()]
    row = _row(page, "propellant_budget.cam_count_factor")
    assert page.table.model.text(row, 1) == "4.0" and not page.table.row_is_bold(row)
    assert page.table.model.text(_row(page, "propellant_budget.cam_count_factor") - 1, 0) == "propellant_budget"
    assert "every value is its default" in page.status_label.text()
    page.select("link.required_margin_db")
    assert not page.set_button.isEnabled() and "configuration file" in page.set_button.toolTip()
    detail = page.detail_label.text()
    assert detail.startswith("link.required_margin_db [dB]: The link closes") and "Source: SpaceMissionStudio" in detail
    assert "It may take at least -20, at most 30 (number)." in detail


def test_a_file_chosen_is_named_relative_to_the_scenario_and_its_values_shown(page, qtbot, tmp_path, monkeypatch):
    """A file chosen inside the scenario's folder is named relative to it;
    the values it changes are in bold, and "Changed values only" keeps
    them and their area."""
    path = tmp_path / "project.yaml"
    path.write_text("parameters:\n  propellant_budget.residual_fraction: 0.05   # ours\n", encoding="utf-8")
    monkeypatch.setattr(page, "_ask_open_path", lambda: str(path))
    with qtbot.waitSignal(page.config_file_changed) as named:
        page.choose_button.click()
    assert named.args == ["project.yaml"] and page.file_edit.text() == "project.yaml"
    row = _row(page, "propellant_budget.residual_fraction")
    assert page.table.model.text(row, 1) == "0.05" and page.table.row_is_bold(row)
    assert page.status_label.text() == "1 value(s) changed by the file."
    page.changed_only.setChecked(True)
    shown = [page.table.proxy.mapToSource(page.table.proxy.index(r, 0)).row()
             for r in range(page.table.proxy.rowCount())]
    assert [page.table.model.text(r, 0) for r in shown] == ["propellant_budget", "propellant_budget.residual_fraction"]


def test_a_value_set_is_checked_and_written_into_its_line(page, qtbot, tmp_path, monkeypatch):
    """A new file lists every parameter commented out; a value set is
    checked against the parameter's limits, written into its own line (the
    file's comments stay) and shown; Reset comments it out again; a value
    out of range is refused and the file left as it was."""
    from spacemissionstudio.config import files

    path = tmp_path / "project.yaml"
    monkeypatch.setattr(page, "_ask_save_path", lambda: str(path))
    page.new_button.click()
    assert files.read(path).overrides == {} and page.config_file == "project.yaml"
    page.select("link.required_margin_db")
    assert page.set_button.isEnabled() and page.value_edit.text() == "0.0"
    page.value_edit.setText("3")
    with qtbot.waitSignal(page.configuration_edited):
        page.set_button.click()
    assert files.read(path).overrides == {"link.required_margin_db": 3.0}
    assert "  link.required_margin_db: 3.0  # [dB]" in path.read_text(encoding="utf-8").splitlines()
    assert page.table.row_is_bold(_row(page, "link.required_margin_db")) and page.reset_button.isEnabled()
    before = path.read_text(encoding="utf-8")
    page.value_edit.setText("99")
    page.set_button.click()
    assert "at most 30" in page.edit_error.text() and path.read_text(encoding="utf-8") == before
    with qtbot.waitSignal(page.configuration_edited):
        page.reset_button.click()
    assert files.read(path).overrides == {} and not page.table.row_is_bold(_row(page, "link.required_margin_db"))


def test_a_relative_file_of_an_unsaved_scenario_is_not_read(qtbot):
    """A relative name with no scenario folder yet cannot be read: the page
    says so, in the error tone, and nothing can be set."""
    from spacemissionstudio.gui.assumptions_page import AssumptionsPage

    view = AssumptionsPage()
    qtbot.addWidget(view)
    view.set_config_file("project.yaml")
    assert "save the scenario first" in view.status_label.text()
    assert view.status_label.property("tone") == "critical"
    view.select("lifetime.iadc_years")
    assert not view.set_button.isEnabled()


def test_the_editor_takes_the_pages_file_and_its_values(qtbot, tmp_path, monkeypatch):
    """Scenario › Assumptions in the editor: the file named there is the
    scenario's ``config_file``, a value set there is in the scenario's
    configuration, and Remove names none again."""
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    editor = ScenarioEditorWidget()
    qtbot.addWidget(editor)
    editor.set_base_dir_provider(lambda: tmp_path)
    editor.from_scenario(load_scenario(next(_TEMPLATES_DIR.glob("01_*.json"))))
    page = editor.assumptions_page
    assert editor.page_tree.tree.topLevelItemCount() and editor.assumptions_item.text(0).startswith("Assumptions")
    monkeypatch.setattr(page, "_ask_save_path", lambda: str(tmp_path / "project.yaml"))
    with qtbot.waitSignal(editor.changed):
        page.new_button.click()
    page.select("lifetime.iadc_years")
    page.value_edit.setText("20")
    with qtbot.waitSignal(editor.changed):
        page.set_button.click()
    scenario = editor.to_scenario()
    assert scenario.config_file == "project.yaml"
    assert scenario.configuration.overrides == {"lifetime.iadc_years": 20.0}
    with qtbot.waitSignal(editor.changed):
        page.remove_button.click()
    assert editor.to_scenario().config_file is None and editor.to_scenario().configuration is None
