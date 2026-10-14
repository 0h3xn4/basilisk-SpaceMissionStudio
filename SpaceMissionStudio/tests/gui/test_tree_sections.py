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
"""A spacecraft's tabs as nodes of the scenario tree (docs/ux-audit.md
U-01, iteration 6a): one node per tab of the spacecraft editor under the
spacecraft, the tree and the form kept on the same tab, and a tab's count
of the problems about its fields."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_ORBIT_ONLY_TABS = ["Orbit / mass", "Power / propulsion / link budget", "3D model", "Vizard model", "Budget (AD10)"]


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    """A main window with template 22 (orbit only, one spacecraft) open."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def _sections(editor, row=0):
    return editor.page_tree.sections(editor._spacecraft_nodes[row].item)


def _titles(editor, row=0):
    return [editor.page_tree.section_key(item) for item in _sections(editor, row)]


def test_a_spacecraft_has_a_node_per_tab_of_its_mode(window):
    """Orbit only: the five tabs without attitude, in the editor's order;
    full attitude adds Sensors / actuators and Attitude control. The
    nodes are there before the form is built."""
    from spacemissionstudio.gui.spacecraft_editor import TAB_TITLES

    editor = window.scenario_editor
    assert editor._spacecraft_nodes[0].form is None and _titles(editor) == _ORBIT_ONLY_TABS
    editor.simulation_mode_combo.setCurrentIndex(editor.simulation_mode_combo.findData("full_attitude"))
    assert _titles(editor) == list(TAB_TITLES)


def test_the_tree_lists_the_tabs_the_editor_shows(qtbot):
    """The tree's sections are the dialog's visible tabs, in order, in
    both modes (the tree builds them before the form)."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog, tab_titles

    for mode in ("orbit_only", "full_attitude"):
        dialog = SpacecraftEditorDialog(simulation_mode=mode)
        qtbot.addWidget(dialog)
        tabs = dialog.tabs
        assert [tabs.tabText(i) for i in range(tabs.count()) if tabs.isTabVisible(i)] == tab_titles(mode)


def test_a_tab_node_shows_its_tab_without_a_tab_bar(window):
    """Opening the spacecraft goes to Orbit / mass; another node shows
    its tab; the form has no tab bar of its own in the tree."""
    editor = window.scenario_editor
    tree = editor.page_tree
    tree.tree.setCurrentItem(editor._spacecraft_nodes[0].item)
    form = editor._spacecraft_nodes[0].form
    assert tree.tree.currentItem() is _sections(editor)[0] and form.tabs.tabText(form.tabs.currentIndex()) == "Orbit / mass"
    assert not form.tabs.tabBar().isVisibleTo(form)
    tree.show_section(editor._spacecraft_nodes[0].item, "Vizard model")
    assert form.tabs.tabText(form.tabs.currentIndex()) == "Vizard model"
    assert tree.current_page() is editor._spacecraft_nodes[0].holder


def test_a_problem_in_another_tab_moves_the_tree_there(window):
    """Problems opens a field on another tab: the form shows the tab and
    the tree selects its node."""
    editor = window.scenario_editor
    editor.show_spacecraft_problem("my-sat", "vizard_model_offset_m", "vizard_model_offset_m: not finite")
    form = editor._spacecraft_nodes[0].form
    assert form.tabs.tabText(form.tabs.currentIndex()) == "Vizard model"
    assert editor.page_tree.section_key(editor.page_tree.tree.currentItem()) == "Vizard model"


def test_a_tab_counts_the_problems_about_its_fields(window):
    """An empty name counts on the spacecraft and on Orbit / mass, where
    the name is, in the error colour."""
    from spacemissionstudio.gui.theme import PALETTE

    editor = window.scenario_editor
    editor.show_spacecraft(0)
    form = editor._spacecraft_nodes[0].form
    form.name_edit.setText("")
    editor.flush_forms()
    orbit = _sections(editor)[0]
    assert orbit.text(0) == "Orbit / mass (1)" and editor._spacecraft_nodes[0].item.text(0) == "my-sat (1)"
    assert orbit.foreground(0).color().name().upper() == PALETTE["danger_text"]
    assert all(item.text(0) == editor.page_tree.section_key(item) for item in _sections(editor)[1:])
    form.name_edit.setText("my-sat")
    editor.flush_forms()
    assert orbit.text(0) == "Orbit / mass"


def test_renaming_keeps_the_tab_shown(window):
    """A rename rebuilds the spacecraft's node; the tree stays on its tab."""
    editor = window.scenario_editor
    editor.show_spacecraft(0)
    editor._spacecraft_nodes[0].form.name_edit.setText("my-sat-2")
    editor.flush_forms()
    assert editor.page_tree.tree.currentItem() is _sections(editor)[0]
    assert editor._spacecraft_nodes[0].item.text(0) == "my-sat-2"


def test_the_palette_goes_to_a_tab(window):
    """The command palette lists each tab of a spacecraft and goes there."""
    entry = next(e for e in window.palette_entries()
                 if e.label == "Go to tab > Scenario > Spacecraft > my-sat > Budget (AD10)")
    window.show_view(window.lifetime_widget)
    entry.run()
    editor = window.scenario_editor
    form = editor._spacecraft_nodes[0].form
    assert window.main_tabs.currentWidget() is editor
    assert form.tabs.tabText(form.tabs.currentIndex()) == "Budget (AD10)"


def test_a_warning_only_count_is_yellow(window):
    """A plausibility warning (a perigee that re-enters at once) counts on
    the spacecraft and on Spacecraft in the warning colour, not red."""
    from spacemissionstudio.gui.theme import PALETTE

    editor = window.scenario_editor
    editor.show_spacecraft(0)
    form = editor._spacecraft_nodes[0].form
    form.orbit_widget.sma_km.setValue(6378.137 + 100.0)  # [km] a 100 km circular orbit
    editor.flush_forms()
    item, group = editor._spacecraft_nodes[0].item, editor.spacecraft_item
    assert any("re-enters" in text for severity, text in editor.problems if severity == "warning")
    assert item.text(0) == "my-sat (1)" and group.text(0) == "Spacecraft (1)"
    for node in (item, group):
        assert node.foreground(0).color().name().upper() == PALETTE["warning"]
    assert item.toolTip(0) == "1 warning here: see Problems"
