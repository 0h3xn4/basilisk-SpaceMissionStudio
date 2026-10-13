"""Tests for gui.mission_sequence_editor.MissionSequenceEditorWidget/_CommandEditorDialog."""

import pytest

pytestmark = pytest.mark.requires_gui


def _dialog(command=None, spacecraft_names=None, series_names=None, ground_station_names=None):
    from spacemissionstudio.gui.mission_sequence_editor import _CommandEditorDialog

    return _CommandEditorDialog(command=command, spacecraft_names=spacecraft_names, series_names=series_names,
                                ground_station_names=ground_station_names)


def _widget(qtbot):
    from spacemissionstudio.gui.mission_sequence_editor import MissionSequenceEditorWidget

    widget = MissionSequenceEditorWidget()
    qtbot.addWidget(widget)
    return widget


def _tick(dialog, *names):
    from PySide6.QtCore import Qt

    for i in range(dialog.report_series_list.count()):
        item = dialog.report_series_list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) in names:
            item.setCheckState(Qt.CheckState.Checked)


def test_propagate_duration_round_trips(qtbot):
    dialog = _dialog(spacecraft_names=["sat-1"])
    qtbot.addWidget(dialog)
    dialog.label_edit.setText("Coast")
    dialog.duration_days_spin.setValue(2.5)

    command = dialog.to_dataclass()
    assert command.kind == "propagate"
    assert command.label == "Coast"
    assert command.params == {"stop_condition": "duration", "duration_days": 2.5}


def test_propagate_event_round_trips(qtbot):
    dialog = _dialog(spacecraft_names=["sat-1", "sat-2"])
    qtbot.addWidget(dialog)
    index = dialog.stop_condition_combo.findText("event")
    dialog.stop_condition_combo.setCurrentIndex(index)
    event_index = dialog.event_kind_combo.findText("apoapsis")
    dialog.event_kind_combo.setCurrentIndex(event_index)
    sc_index = dialog.propagate_event_spacecraft_combo.findText("sat-2")
    dialog.propagate_event_spacecraft_combo.setCurrentIndex(sc_index)

    command = dialog.to_dataclass()
    assert command.params == {"stop_condition": "event", "event_kind": "apoapsis", "spacecraft": "sat-2"}


def test_propagate_pass_event_picks_a_station_only_when_needed(qtbot):
    dialog = _dialog(spacecraft_names=["sat-1"], ground_station_names=["berlin-gs", "kiruna-gs"])
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.stop_condition_combo.setCurrentIndex(dialog.stop_condition_combo.findText("event"))
    assert not dialog.propagate_event_station_combo.isVisible()  # periapsis needs no station
    dialog.event_kind_combo.setCurrentIndex(dialog.event_kind_combo.findText("pass_start"))
    assert dialog.propagate_event_station_combo.isVisible()
    dialog.propagate_event_station_combo.setCurrentIndex(dialog.propagate_event_station_combo.findText("kiruna-gs"))

    command = dialog.to_dataclass()
    assert command.params == {"stop_condition": "event", "event_kind": "pass_start", "spacecraft": "sat-1",
                              "ground_station": "kiruna-gs"}
    reopened = _dialog(command=command, spacecraft_names=["sat-1"], ground_station_names=["berlin-gs", "kiruna-gs"])
    qtbot.addWidget(reopened)
    assert reopened.to_dataclass().params == command.params


def test_editor_offers_the_scenarios_ground_stations(qtbot):
    """A step's form offers the scenario's ground stations, sorted."""
    widget = _widget(qtbot)
    widget.set_ground_station_names_provider(lambda: ["kiruna-gs", "berlin-gs"])
    widget.add_step("propagate")
    combo = widget.form.propagate_event_station_combo
    assert [combo.itemText(i) for i in range(combo.count())] == ["berlin-gs", "kiruna-gs"]


def test_propagate_epoch_rejects_bad_iso8601(qtbot):
    dialog = _dialog()
    qtbot.addWidget(dialog)
    index = dialog.stop_condition_combo.findText("epoch")
    dialog.stop_condition_combo.setCurrentIndex(index)
    dialog.stop_epoch_edit.setText("not a date")

    with pytest.raises(ValueError, match="not a valid ISO 8601"):
        dialog.to_dataclass()


def test_maneuver_round_trips(qtbot):
    dialog = _dialog(spacecraft_names=["sat-1"])
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("maneuver")
    dialog.kind_combo.setCurrentIndex(index)
    sc_index = dialog.maneuver_spacecraft_combo.findText("sat-1")
    dialog.maneuver_spacecraft_combo.setCurrentIndex(sc_index)
    dialog.delta_v_x_spin.setValue(1.0)
    dialog.delta_v_y_spin.setValue(2.0)
    dialog.delta_v_z_spin.setValue(3.0)
    frame_index = dialog.maneuver_frame_combo.findText("vnb")
    dialog.maneuver_frame_combo.setCurrentIndex(frame_index)

    command = dialog.to_dataclass()
    assert command.kind == "maneuver"
    assert command.params == {"spacecraft": "sat-1", "delta_v_m_s": [1.0, 2.0, 3.0], "frame": "vnb"}


def test_maneuver_rejects_missing_spacecraft(qtbot):
    dialog = _dialog(spacecraft_names=[])  # no spacecraft defined yet -- combo stays empty
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("maneuver")
    dialog.kind_combo.setCurrentIndex(index)

    with pytest.raises(ValueError, match="spacecraft"):
        dialog.to_dataclass()


def test_lambert_transfer_round_trips(qtbot):
    dialog = _dialog(spacecraft_names=["sat-1"])
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("lambert_transfer")
    dialog.kind_combo.setCurrentIndex(index)
    sc_index = dialog.lambert_spacecraft_combo.findText("sat-1")
    dialog.lambert_spacecraft_combo.setCurrentIndex(sc_index)
    dialog.lambert_target_x_spin.setValue(-6578000.0)
    dialog.lambert_target_y_spin.setValue(0.0)
    dialog.lambert_target_z_spin.setValue(0.0)
    dialog.lambert_tof_spin.setValue(2490.0)
    dialog.lambert_num_rev_spin.setValue(1)
    dialog.lambert_max_dist_spin.setValue(500.0)
    dialog.lambert_min_radius_spin.setValue(6378000.0)

    command = dialog.to_dataclass()
    assert command.kind == "lambert_transfer"
    assert command.params == {
        "spacecraft": "sat-1",
        "target_position_m": [-6578000.0, 0.0, 0.0],
        "time_of_flight_s": 2490.0,
        "num_revolutions": 1,
        "max_distance_target_m": 500.0,
        "min_orbit_radius_m": 6378000.0,
    }


def test_lambert_transfer_rejects_missing_spacecraft(qtbot):
    dialog = _dialog(spacecraft_names=[])  # no spacecraft defined yet -- combo stays empty
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("lambert_transfer")
    dialog.kind_combo.setCurrentIndex(index)

    with pytest.raises(ValueError, match="spacecraft"):
        dialog.to_dataclass()


def test_assignment_round_trips(qtbot):
    dialog = _dialog(spacecraft_names=["sat-1"])
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("assignment")
    dialog.kind_combo.setCurrentIndex(index)
    sc_index = dialog.assignment_spacecraft_combo.findText("sat-1")
    dialog.assignment_spacecraft_combo.setCurrentIndex(sc_index)
    controller_index = dialog.assignment_controller_combo.findText("station_keeping")
    dialog.assignment_controller_combo.setCurrentIndex(controller_index)
    parameter_index = dialog.assignment_parameter_combo.findText("thrust_n")
    dialog.assignment_parameter_combo.setCurrentIndex(parameter_index)
    dialog.assignment_value_spin.setValue(0.5)

    command = dialog.to_dataclass()
    assert command.kind == "assignment"
    assert command.params == {"target": "sat-1.station_keeping.thrust_n", "value": 0.5}


def test_assignment_dialog_prefills_target_from_existing_command(qtbot):
    from spacemissionstudio.schema.command import Command

    existing = Command(kind="assignment", params={"target": "sat-1.phasing_keeping.isp_s", "value": 220.0})
    dialog = _dialog(command=existing, spacecraft_names=["sat-1"])
    qtbot.addWidget(dialog)

    assert dialog.assignment_spacecraft_combo.currentText() == "sat-1"
    assert dialog.assignment_controller_combo.currentText() == "phasing_keeping"
    assert dialog.assignment_parameter_combo.currentText() == "isp_s"
    assert dialog.assignment_value_spin.value() == pytest.approx(220.0)


def test_assignment_rejects_missing_spacecraft(qtbot):
    """Regression guard: Command.validate() alone doesn't reject a blank
    spacecraft segment in assignment.target (only that the string contains
    a '.'), unlike maneuver/propagate's explicit spacecraft checks -- so
    to_dataclass() must reject it itself before it ever reaches
    Command.validate().
    """
    dialog = _dialog(spacecraft_names=[])  # no spacecraft defined yet -- combo stays empty
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("assignment")
    dialog.kind_combo.setCurrentIndex(index)

    with pytest.raises(ValueError, match="spacecraft"):
        dialog.to_dataclass()


def test_report_series_are_picked_from_the_scenario_list(qtbot):
    """Real user feedback: series names had to be typed from memory, and
    one typo failed the run. They are now ticked in a list of the series
    this scenario produces."""
    names = ["sat-1.mass_kg", "sat-1.position_N", "sat-1.velocity_N"]
    dialog = _dialog(series_names=names)
    qtbot.addWidget(dialog)
    dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findText("report"))
    assert dialog.report_series_list.count() == 3
    assert "every series" in dialog.report_summary_label.text()
    _tick(dialog, "sat-1.position_N", "sat-1.mass_kg")
    assert "2 series" in dialog.report_summary_label.text()

    command = dialog.to_dataclass()
    assert command.params == {"series": ["sat-1.mass_kg", "sat-1.position_N"]}

    dialog.report_filter_edit.setText("veloc")
    hidden = [dialog.report_series_list.item(i).isHidden() for i in range(3)]
    assert hidden == [True, True, False]
    dialog._on_report_clear()
    assert dialog.to_dataclass().params == {"series": []}


def test_report_keeps_and_flags_a_series_the_scenario_does_not_produce(qtbot):
    from spacemissionstudio.schema.command import Command

    command = Command(kind="report", params={"series": ["sat-1.position_N", "old-sat.position_N"]})
    dialog = _dialog(command=command, series_names=["sat-1.position_N", "sat-1.velocity_N"])
    qtbot.addWidget(dialog)
    texts = [dialog.report_series_list.item(i).text() for i in range(dialog.report_series_list.count())]
    assert any("old-sat.position_N" in t and "not produced" in t for t in texts)
    assert dialog.to_dataclass().params == command.params  # open + OK changes nothing


def test_report_empty_series_means_snapshot_everything(qtbot):
    dialog = _dialog()
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("report")
    dialog.kind_combo.setCurrentIndex(index)

    command = dialog.to_dataclass()
    assert command.params == {"series": []}


def test_if_condition_round_trips(qtbot):
    dialog = _dialog()
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("if")
    dialog.kind_combo.setCurrentIndex(index)
    dialog.condition_edit.setText("t_s > 3600")

    command = dialog.to_dataclass()
    assert command.kind == "if"
    assert command.params == {"condition": "t_s > 3600"}


def test_if_rejects_empty_condition(qtbot):
    dialog = _dialog()
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("while")
    dialog.kind_combo.setCurrentIndex(index)

    with pytest.raises(ValueError, match="condition"):
        dialog.to_dataclass()


def test_script_block_round_trips(qtbot):
    dialog = _dialog()
    qtbot.addWidget(dialog)
    index = dialog.kind_combo.findText("script_block")
    dialog.kind_combo.setCurrentIndex(index)
    dialog.script_code_edit.setPlainText("summary.commands_executed += 1")

    command = dialog.to_dataclass()
    assert command.kind == "script_block"
    assert command.params == {"code": "summary.commands_executed += 1"}


def test_kind_combo_disabled_when_editing_existing_command(qtbot):
    from spacemissionstudio.schema.command import Command

    dialog = _dialog(command=Command(kind="propagate", params={"duration_days": 1.0}))
    qtbot.addWidget(dialog)
    assert not dialog.kind_combo.isEnabled()


def test_widget_add_and_remove_show_a_toast(qtbot):
    """Adding and removing a step each say so in a toast."""
    widget = _widget(qtbot)
    widget.set_spacecraft_names_provider(lambda: ["sat-1"])
    widget.add_step("propagate")
    toasts = getattr(widget.window(), "_spacemissionstudio_active_toasts", [])
    assert any("Propagate for 1 day" in t.text() for t in toasts)

    widget.tree.setCurrentItem(widget.tree.topLevelItem(0))
    widget._on_remove()
    toasts = getattr(widget.window(), "_spacemissionstudio_active_toasts", [])
    assert any("Removed" in t.text() for t in toasts)


def test_widget_add_edit_remove_top_level(qtbot):
    """Add a step, edit it in its form (applied once the edit settles, or
    at once when the sequence is read), remove it."""
    widget = _widget(qtbot)
    widget.set_spacecraft_names_provider(lambda: ["sat-1"])
    changed_count = []
    widget.changed.connect(lambda: changed_count.append(1))

    widget.add_step("propagate")
    assert widget.tree.topLevelItemCount() == 1 and changed_count == [1]
    widget.form.duration_days_spin.setValue(1.5)  # [day]
    qtbot.waitUntil(lambda: len(changed_count) == 2, timeout=2000)
    commands = widget.to_command_list()
    assert len(commands) == 1 and commands[0].kind == "propagate"
    assert commands[0].params["duration_days"] == 1.5  # [day]
    assert widget.tree.topLevelItem(0).text(0) == "Propagate for 1.5 days"

    widget.form.label_edit.setText("renamed")
    assert widget.to_command_list()[0].label == "renamed"  # flushed, no wait

    widget.tree.setCurrentItem(widget.tree.topLevelItem(0))
    widget._on_remove()
    assert widget.to_command_list() == []


def test_add_child_only_enabled_for_if_while(qtbot):
    """Add inside is offered only on an if/while step, and only they
    accept a dropped step."""
    from PySide6.QtCore import Qt

    widget = _widget(qtbot)
    widget.add_step("propagate")
    assert not widget.add_child_button.isEnabled()
    assert not widget.tree.topLevelItem(0).flags() & Qt.ItemFlag.ItemIsDropEnabled
    widget.add_step("while")
    assert widget.tree.currentItem() is widget.tree.topLevelItem(1)
    assert widget.add_child_button.isEnabled()
    assert widget.tree.topLevelItem(1).flags() & Qt.ItemFlag.ItemIsDropEnabled


def test_add_child_nests_command_and_round_trips(qtbot):
    """Add inside nests the new step in the selected while."""
    widget = _widget(qtbot)
    parent_item = widget.add_step("while")
    widget.form.condition_edit.setText("t_s < 10")
    widget.add_step("report", inside=True)

    assert parent_item.childCount() == 1
    commands = widget.to_command_list()
    assert len(commands) == 1
    assert commands[0].kind == "while" and commands[0].params == {"condition": "t_s < 10"}
    assert [child.kind for child in commands[0].children] == ["report"]


def test_move_up_down_reorders_siblings(qtbot):
    """Move up / Move down swap a step with its neighbour."""
    widget = _widget(qtbot)
    for label in ("first", "second"):
        widget.add_step("propagate")
        widget.form.label_edit.setText(label)
    assert [c.label for c in widget.to_command_list()] == ["first", "second"]

    widget.tree.setCurrentItem(widget.tree.topLevelItem(1))  # "second"
    widget._on_move_up()
    assert [c.label for c in widget.to_command_list()] == ["second", "first"]
    widget._on_move_down()
    assert [c.label for c in widget.to_command_list()] == ["first", "second"]


def test_from_command_list_to_command_list_round_trip(qtbot):
    from spacemissionstudio.gui.mission_sequence_editor import MissionSequenceEditorWidget
    from spacemissionstudio.schema.command import Command

    widget = MissionSequenceEditorWidget()
    qtbot.addWidget(widget)

    commands = [
        Command(kind="propagate", label="coast", params={"stop_condition": "duration", "duration_days": 1.0}),
        Command(kind="while", params={"condition": "t_s < 100"}, children=[
            Command(kind="report", params={"series": []}),
        ]),
    ]
    widget.from_command_list(commands)

    assert widget.tree.topLevelItemCount() == 2
    assert widget.tree.topLevelItem(1).childCount() == 1

    got = widget.to_command_list()
    assert len(got) == 2
    assert got[0].label == "coast"
    assert got[1].kind == "while"
    assert len(got[1].children) == 1
    assert got[1].children[0].kind == "report"


def test_editing_child_does_not_stale_parent_children_field(qtbot):
    """Regression guard for this module's own documented invariant: a
    parent's stored Command.children is always cleared (see _new_item),
    so to_command_list() must reflect an edited child via tree structure,
    never a stale copy captured when the parent was built.
    """
    from spacemissionstudio.schema.command import Command

    widget = _widget(qtbot)
    widget.from_command_list([
        Command(kind="if", params={"condition": "t_s > 0"}, children=[
            Command(kind="report", label="before", params={"series": []}),
        ]),
    ])
    widget.tree.setCurrentItem(widget.tree.topLevelItem(0).child(0))
    widget.form.label_edit.setText("after")
    assert widget.to_command_list()[0].children[0].label == "after"


def test_command_editor_dialog_resizes_to_its_own_sizehint_on_construction(qtbot):
    """See test_constellation_dialog.py's identical test for why."""
    dialog = _dialog(spacecraft_names=["sat-1"])
    qtbot.addWidget(dialog)

    assert dialog.size() == dialog.sizeHint()
