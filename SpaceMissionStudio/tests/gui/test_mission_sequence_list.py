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


"""The Mission Sequence list (docs/ux-audit.md U-15): each step reads as a
sentence with its kind's icon; a checkbox leaves a step out of the run;
steps move by dragging (only into if/while) or with Move up/down; the
selected step is edited in a form beside the list, applied as you type;
a problem marks the step, and Problems opens it."""

from pathlib import Path

import pytest

from spacemissionstudio.schema.command import Command

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


def _propagate(days=1.0, **kwargs):  # [day]
    return Command(kind="propagate", params={"stop_condition": "duration", "duration_days": days}, **kwargs)


@pytest.fixture
def widget(qtbot):
    from spacemissionstudio.gui.mission_sequence_editor import MissionSequenceEditorWidget

    w = MissionSequenceEditorWidget()
    w.set_spacecraft_names_provider(lambda: ["sat-1"])
    w.set_ground_station_names_provider(lambda: ["berlin-gs"])
    qtbot.addWidget(w)
    return w


@pytest.mark.parametrize("command, sentence", [
    (_propagate(1.0), "Propagate for 1 day"),  # [day]
    (_propagate(2.5), "Propagate for 2.5 days"),  # [day]
    (_propagate(0.25), "Propagate for 6 h"),  # [day]
    (Command(kind="propagate", params={"stop_condition": "epoch", "stop_epoch_utc": "2030-01-05T00:00:00"}),
     "Propagate until 2030-01-05T00:00:00 UTC"),
    (Command(kind="propagate", params={"stop_condition": "event", "event_kind": "pass_start", "spacecraft": "sat-1",
                                       "ground_station": "berlin-gs"}),
     "Propagate until sat-1's next pass over berlin-gs starts"),
    (Command(kind="propagate", params={"stop_condition": "event", "event_kind": "apoapsis", "spacecraft": "sat-1"}),
     "Propagate until sat-1's next apoapsis"),
    (Command(kind="maneuver", params={"spacecraft": "sat-1", "delta_v_m_s": [3.0, 4.0, 0.0], "frame": "vnb"}),
     "Burn 5 m/s on sat-1 (VNB 3, 4, 0 m/s)"),
    (Command(kind="assignment", params={"target": "sat-1.station_keeping.thrust_n", "value": 0.02}),
     "Set sat-1's station keeping thrust_n to 0.02"),
    (Command(kind="report", params={"series": []}), "Report every series"),
    (Command(kind="report", params={"series": ["a", "b"]}), "Report 2 series"),
    (Command(kind="while", params={"condition": "t_s < 10"}), "While t_s < 10"),
    (Command(kind="script_block", params={"code": "a = 1\nb = 2"}), "Run a Python script (2 lines)"),
    (Command(kind="maneuver", params={"delta_v_m_s": "oops"}), "Maneuver (impulsive burn)"),
])
def test_each_step_reads_as_a_sentence(command, sentence):
    """A step says what it does; wrong parameters read as the step's kind."""
    from spacemissionstudio.gui.mission_sequence_editor import step_sentence

    assert step_sentence(command) == sentence


def test_a_step_shows_its_label_its_icon_and_its_checkbox(widget):
    """The label comes first, the kind's icon beside it, ticked when enabled."""
    from PySide6.QtCore import Qt

    widget.from_command_list([_propagate(label="Coast"), _propagate(enabled=False)])
    first, second = widget.tree.topLevelItem(0), widget.tree.topLevelItem(1)
    assert first.text(0) == "Coast: Propagate for 1 day" and not first.icon(0).isNull()
    assert first.checkState(0) == Qt.CheckState.Checked
    assert second.checkState(0) == Qt.CheckState.Unchecked and second.font(0).italic()


def test_unticking_a_step_leaves_it_out_and_greys_its_children(widget):
    """Unticking an if leaves it (and so its children) out of the run;
    the children say why."""
    from PySide6.QtCore import Qt

    widget.from_command_list([Command(kind="if", params={"condition": "t_s > 0"}, children=[_propagate()])])
    changes = []
    widget.changed.connect(lambda: changes.append(1))
    parent = widget.tree.topLevelItem(0)
    parent.setCheckState(0, Qt.CheckState.Unchecked)
    assert changes == [1]
    commands = widget.to_command_list()
    assert commands[0].enabled is False and commands[0].children[0].enabled is True
    assert "a step it is inside is unticked" in parent.child(0).toolTip(0) and parent.child(0).font(0).italic()


def test_dropping_moves_a_step_only_where_it_can_go(widget):
    """A step drops above or below another, into an if/while, but not into
    another kind of step or into itself."""
    from PySide6.QtWidgets import QAbstractItemView

    where = QAbstractItemView.DropIndicatorPosition
    widget.from_command_list([_propagate(label="a"), Command(kind="while", label="loop", params={"condition": "t_s < 9"}),
                              _propagate(label="b")])
    tree = widget.tree
    a, loop, b = (tree.topLevelItem(i) for i in range(3))
    assert not tree.move_into_place(a, b, where.OnItem)  # a propagate takes no steps
    assert not tree.move_into_place(loop, loop, where.OnItem)
    assert tree.move_into_place(b, a, where.AboveItem)
    assert [c.label for c in widget.to_command_list()] == ["b", "a", "loop"]
    assert tree.move_into_place(a, loop, where.OnItem)
    commands = widget.to_command_list()
    assert [c.label for c in commands] == ["b", "loop"] and [c.label for c in commands[1].children] == ["a"]
    assert tree.currentItem() is loop.child(0) and loop.isExpanded()
    assert tree.move_into_place(loop.child(0), None, where.OnViewport)
    assert [c.label for c in widget.to_command_list()] == ["b", "loop", "a"]


def test_a_move_keeps_paths_and_states_current(widget):
    """Moving a step renumbers the paths its tooltip and form show."""
    widget.from_command_list([_propagate(label="a"), _propagate(days=0.0, label="bad")])  # [day]
    bad = widget.tree.topLevelItem(1)
    assert "mission_sequence[1] ('bad')" in bad.toolTip(0)
    widget.tree.setCurrentItem(bad)
    widget._on_move_up()
    assert "mission_sequence[0] ('bad')" in bad.toolTip(0)
    assert widget.form_title.text().endswith("mission_sequence[0]")


def test_duplicate_copies_a_step_with_its_children(widget):
    """Duplicate puts a copy, children too, after the step."""
    widget.from_command_list([Command(kind="while", params={"condition": "t_s < 9"}, children=[_propagate()])])
    widget.tree.setCurrentItem(widget.tree.topLevelItem(0))
    widget._on_duplicate()
    commands = widget.to_command_list()
    assert len(commands) == 2 and commands[0] == commands[1]


def test_a_new_step_goes_after_the_selected_one(widget):
    """Add step inserts after the selection, and selects the new step."""
    widget.from_command_list([_propagate(label="a"), _propagate(label="b")])
    widget.tree.setCurrentItem(widget.tree.topLevelItem(0))
    item = widget.add_step("report")
    assert [c.kind for c in widget.to_command_list()] == ["propagate", "report", "propagate"]
    assert widget.tree.currentItem() is item and widget.form is not None


def test_a_wrong_value_marks_the_step_and_shows_in_the_banner(widget, qtbot):
    """A step left wrong is kept, in the error colour, its problem over
    its form."""
    from spacemissionstudio.gui.theme import PALETTE

    widget.from_command_list([Command(kind="propagate", params={"stop_condition": "epoch",
                                                                "stop_epoch_utc": "2030-01-05T00:00:00"})])
    item = widget.tree.topLevelItem(0)
    widget.tree.setCurrentItem(item)
    assert not widget.problem_banner.isVisibleTo(widget)
    widget.form.stop_epoch_edit.setText("tomorrow")
    widget.flush()
    assert widget.to_command_list()[0].params["stop_epoch_utc"] == "tomorrow"
    assert widget.problem_banner.isVisibleTo(widget) and "stop_epoch_utc" in widget.problem_banner.label.text()
    assert item.foreground(0).color().name().lower() == PALETTE["danger_text"].lower()


def test_problems_open_the_step(qtbot, tmp_path, monkeypatch):
    """Double-clicking a step's problem opens the Mission sequence page
    with that step selected; the node counts the problem."""
    import dataclasses

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.open_path(_TEMPLATES / "08_mission_sequence_orbit_raise.json")
    editor = window.scenario_editor
    sequence = editor.mission_sequence_editor
    commands = sequence.to_command_list()
    commands[2] = dataclasses.replace(commands[2], params={**commands[2].params, "spacecraft": "nobody"})
    sequence.from_command_list(commands)
    editor.revalidate()
    problems = window.problems_widget
    row = next(i for i, (_severity, text) in enumerate(problems.problems) if text.startswith("mission_sequence[2]"))
    window.show_view(window.results_widget)
    problems.table.activated.emit(problems.index_of(row))
    assert editor.page_tree.current_page() is editor.mission_sequence_page
    assert sequence.tree.currentItem() is sequence.tree.topLevelItem(2)
    assert editor.page_tree.problem_count(editor.mission_sequence_item) >= 1
