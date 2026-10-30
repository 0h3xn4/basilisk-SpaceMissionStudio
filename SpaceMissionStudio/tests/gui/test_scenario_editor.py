"""Tests for gui.scenario_editor.ScenarioEditorWidget."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_SCENARIO_PATH = Path(__file__).resolve().parent.parent.parent / "spacemissionstudio" / "scenarios" / "two_body_validation.json"


@pytest.fixture
def widget(qtbot):
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget

    w = ScenarioEditorWidget()
    qtbot.addWidget(w)
    return w


def _environment_labels(widget) -> list:
    """The field labels of the Environment page's form (the embedded
    PropagationSetupDialog that replaced the read-only summary, U-17),
    with the unit the form shows in the field ("Duration [days]")."""
    from PySide6.QtWidgets import QFormLayout, QLabel

    labels = []
    for form in widget._environment_form.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item is not None and isinstance(item.widget(), QLabel):
                labels.append(item.widget().property("sms_full_label") or item.widget().text())
    return labels


def test_default_state_is_invalid_with_no_spacecraft(widget):
    """A new editor shows a warning that the scenario has no spacecraft."""
    assert "⚠" in widget.validation_label.text()
    assert "spacecraft" in widget.validation_label.text().lower()


def test_full_round_trip_matches_loaded_scenario(widget):
    """A loaded scenario shows as valid and comes back with its name, epoch,
    gravity, simulation settings and spacecraft orbit."""
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_SCENARIO_PATH)
    widget.from_scenario(scenario)
    assert "✓" in widget.validation_label.text()

    got = widget.to_scenario()
    assert got.name == scenario.name
    assert got.epoch_utc == scenario.epoch_utc
    assert got.gravity.central_body == scenario.gravity.central_body
    assert got.gravity.central_body_degree == scenario.gravity.central_body_degree
    assert got.sim_settings.duration_days == scenario.sim_settings.duration_days
    assert got.sim_settings.integrator == scenario.sim_settings.integrator
    assert len(got.spacecraft) == 1
    assert got.spacecraft[0].name == scenario.spacecraft[0].name
    assert got.spacecraft[0].orbit == scenario.spacecraft[0].orbit


def test_simulation_mode_defaults_to_full_attitude(widget):
    """The simulation mode defaults to full attitude, and the spacecraft list
    sees it."""
    assert widget.simulation_mode_combo.currentData() == "full_attitude"
    assert widget.spacecraft_list._simulation_mode() == "full_attitude"


def test_simulation_mode_round_trips(widget):
    """An orbit-only scenario opens in orbit-only mode and comes back so."""
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_SCENARIO_PATH)
    scenario.simulation_mode = "orbit_only"
    scenario.spacecraft[0].sensors = []
    scenario.spacecraft[0].actuators = []
    scenario.spacecraft[0].fsw_mode = None
    scenario.spacecraft[0].power = None
    widget.from_scenario(scenario)

    assert widget.simulation_mode_combo.currentData() == "orbit_only"
    got = widget.to_scenario()
    assert got.simulation_mode == "orbit_only"


def test_simulation_mode_combo_drives_spacecraft_list_provider(widget):
    """Changing the simulation mode changes the mode the spacecraft list
    sees."""
    widget.simulation_mode_combo.setCurrentIndex(widget.simulation_mode_combo.findData("orbit_only"))
    assert widget.spacecraft_list._simulation_mode() == "orbit_only"

    widget.simulation_mode_combo.setCurrentIndex(widget.simulation_mode_combo.findData("full_attitude"))
    assert widget.spacecraft_list._simulation_mode() == "full_attitude"


def test_environment_form_reflects_defaults(widget):
    """The Environment page shows the default settings: Earth, point-mass
    gravity."""
    form = widget._environment_form
    assert form.central_body_combo.currentText().lower().startswith("earth")
    assert not form.enable_harmonics_check.isChecked()


def test_environment_form_has_labeled_rows(widget):
    """Regression guard for the old summary's complaint (unlabeled,
    pipe-joined lines): every field of the Environment page carries its
    own label, the setup's own terminology."""
    labels = _environment_labels(widget)
    for label in ("Central body", "Integrator", "Dynamics task rate [s]", "Duration [days]", "Atmosphere model"):
        assert label in labels, label


def _one_spacecraft(widget):
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    widget.spacecraft_list.from_list([
        SpacecraftConfig(name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                       velocity_km_s=[0, 7.5, 0]))
    ])


def test_edit_propagation_setup_updates_state_and_emits_changed(widget, qtbot):
    """An edit in the Environment page applies once typing settles."""
    _one_spacecraft(widget)
    form = widget._environment_form
    with qtbot.waitSignal(widget.changed, timeout=2000):  # [ms]
        form.enable_harmonics_check.setChecked(True)
        form.central_body_degree_spin.setValue(4)
    assert widget._gravity.central_body_degree == 4
    assert widget.to_scenario().gravity.central_body_degree == 4


def test_an_invalid_environment_edit_leaves_state_unchanged(widget, monkeypatch):
    """A form value that does not validate is not applied: the settings stay
    as they were, the form names the problem, and the scenario is not valid
    until it is fixed (no run with the old values)."""
    from spacemissionstudio.gui.scenario_editor import _Debounce
    from spacemissionstudio.schema.scenario import ScenarioValidationError, SimSettings

    _one_spacecraft(widget)
    form = widget._environment_form
    before = widget._sim_settings
    monkeypatch.setattr(form, "to_sim_settings", lambda: SimSettings(duration_days=0.0))  # [days]
    form.duration_days_spin.setValue(2.0)  # [days]
    form.findChild(_Debounce).flush()
    assert widget._sim_settings is before
    assert form.problem_banner.label.text().startswith("Simulation settings: Duration [days] must be > 0")
    with pytest.raises(ScenarioValidationError, match="duration_days"):
        widget.to_scenario()


def test_third_body_perturbers_round_trip(widget):
    """The Sun and Moon as third bodies come back from the editor."""
    from spacemissionstudio.schema.scenario import GravityConfig, Scenario, SpacecraftConfig, OrbitIC

    scenario = Scenario(
        name="t", epoch_utc="2030-01-01T00:00:00",
        gravity=GravityConfig(central_body="earth", central_body_degree=0, third_body_perturbers=["sun", "moon"]),
        spacecraft=[SpacecraftConfig(name="s", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                               velocity_km_s=[0, 7.5, 0]))],
    )
    widget.from_scenario(scenario)
    got = widget.to_scenario()
    assert sorted(got.gravity.third_body_perturbers) == ["moon", "sun"]


def test_live_validation_reacts_to_bad_edit(widget, qtbot):
    """Clearing the name turns the check into a warning that names the field by
    its label and marks the field with it."""
    from spacemissionstudio.schema import load_scenario

    widget.from_scenario(load_scenario(_SCENARIO_PATH))
    assert "✓" in widget.validation_label.text()

    with qtbot.waitSignal(widget.changed, timeout=1000):
        widget.name_edit.setText("")
    assert "⚠" in widget.validation_label.text()
    # The message names the field by its label, not its schema path ("scenario.name"), and
    # the field itself is marked with it (docs/ux-audit.md U-12).
    assert "Name must not be empty" in widget.validation_label.text()
    from spacemissionstudio.gui.feedback import field_error_text

    assert field_error_text(widget.name_edit) == "Name must not be empty"


def test_to_scenario_raises_on_invalid_state(widget):
    """Reading a scenario without spacecraft from the editor is refused."""
    from spacemissionstudio.schema.scenario import ScenarioValidationError

    with pytest.raises(ScenarioValidationError):
        widget.to_scenario()  # no spacecraft yet


def test_monte_carlo_round_trips(widget):
    """Monte Carlo's switch, run and thread counts and dispersion come back
    from the editor."""
    from spacemissionstudio.schema.scenario import DispersionConfig, MonteCarloConfig, OrbitIC, SpacecraftConfig

    widget.spacecraft_list.from_list([
        SpacecraftConfig(name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                       velocity_km_s=[0, 7.5, 0]))
    ])
    widget._refresh_monte_carlo_spacecraft_names()
    mc = MonteCarloConfig(
        enabled=True, num_runs=15, thread_count=2, verbose=True,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=[95, 105])],
    )
    widget.monte_carlo_group.from_dataclass(mc)

    got = widget.to_scenario()
    assert got.monte_carlo.enabled is True
    assert got.monte_carlo.num_runs == 15
    assert got.monte_carlo.thread_count == 2
    assert got.monte_carlo.dispersions[0].spacecraft == "sat-1"


def test_monte_carlo_spacecraft_names_track_spacecraft_list(widget):
    """The dispersion list offers the spacecraft the list has."""
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    assert widget.monte_carlo_group.dispersion_list._spacecraft_names == []
    widget.spacecraft_list.from_list([
        SpacecraftConfig(name="a", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0])),
    ])
    widget.spacecraft_list.changed.emit()
    assert widget.monte_carlo_group.dispersion_list._spacecraft_names == ["a"]


def test_reset_to_default_clears_spacecraft(widget):
    """Resetting the editor removes the spacecraft."""
    from spacemissionstudio.schema import load_scenario

    widget.from_scenario(load_scenario(_SCENARIO_PATH))
    assert len(widget.spacecraft_list.to_list()) == 1
    widget.reset_to_default()
    assert widget.spacecraft_list.to_list() == []


def test_mission_sequence_round_trips(widget):
    """The mission sequence comes back from the editor with its label."""
    from spacemissionstudio.schema.command import Command
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    widget.spacecraft_list.from_list([
        SpacecraftConfig(name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                       velocity_km_s=[0, 7.5, 0]))
    ])
    widget.mission_sequence_editor.from_command_list([
        Command(kind="propagate", label="coast", params={"stop_condition": "duration", "duration_days": 1.0}),
    ])

    got = widget.to_scenario()
    assert len(got.mission_sequence) == 1
    assert got.mission_sequence[0].label == "coast"


def test_mission_sequence_spacecraft_provider_tracks_spacecraft_list(widget):
    """The mission-sequence editor offers the spacecraft the list has."""
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    assert widget.mission_sequence_editor._spacecraft_names() == []
    widget.spacecraft_list.from_list([
        SpacecraftConfig(name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                       velocity_km_s=[0, 7.5, 0])),
    ])
    assert widget.mission_sequence_editor._spacecraft_names() == ["sat-1"]


def test_reset_to_default_clears_mission_sequence(widget):
    """Resetting the editor empties the mission sequence."""
    from spacemissionstudio.schema.command import Command

    widget.mission_sequence_editor.from_command_list([
        Command(kind="script_block", params={"code": "pass"}),
    ])
    assert len(widget.mission_sequence_editor.to_command_list()) == 1
    widget.reset_to_default()
    assert widget.mission_sequence_editor.to_command_list() == []


def test_mission_sequence_report_lists_the_scenarios_series(qtbot):
    """The Report command's pick-list is fed from the scenario being
    edited (engine.series_names), even before it validates."""
    from pathlib import Path

    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
    editor = ScenarioEditorWidget()
    qtbot.addWidget(editor)
    editor.from_scenario(load_scenario(templates / "05_formation_flying_phasing.json"))
    names = editor.mission_sequence_editor._series_names()
    assert len(names) == 42 and "follower-1.phasing_keeping.separation_error" in names  # 40 + two eclipse series
    editor.name_edit.setText("")  # invalid scenario: the list must still come back
    assert editor.mission_sequence_editor._series_names() == names


def test_a_scenario_loaded_is_validated_once_with_every_field_in(widget, monkeypatch):
    """from_scenario() validates the scenario once, when every field is in
    (each field set was an edit that validated it: four times per file
    opened), and the problems are those of the scenario loaded."""
    from spacemissionstudio.gui import scenario_editor
    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
    validated = []
    real = scenario_editor._validate
    monkeypatch.setattr(scenario_editor, "_validate", lambda scenario: (validated.append(scenario.name),
                                                                       real(scenario))[1])
    scenario = load_scenario(templates / "08_mission_sequence_orbit_raise.json")
    widget.from_scenario(scenario)
    assert validated == [scenario.name]
    assert "✓" in widget.validation_label.text()
    rows = widget.problems
    widget.revalidate()
    assert widget.problems == rows


_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


def test_the_duration_says_when_the_mission_sequence_decides(widget):
    """Audit G4: Duration was shown as the run's length though a Mission
    Sequence decides it. Under the Duration a note says how long the
    sequence runs and what the Duration still sets; it follows the
    sequence, and a scenario without one shows none."""
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio.schema.command import Command

    widget.from_scenario(load_scenario(next(_TEMPLATES_DIR.glob("23_*.json"))))
    note = widget._environment_form.duration_note
    assert not note.isHidden()
    assert note.text().startswith("The Mission Sequence decides how long the run is: 58 min + 2 event or condition "
                                  "stops. The Duration must still cover it")
    widget.mission_sequence_editor.from_command_list([Command(kind="propagate", params={"duration_days": 0.5})])
    widget.mission_sequence_editor.changed.emit()
    assert "is: 12.0 h." in note.text()
    widget.from_scenario(load_scenario(next(_TEMPLATES_DIR.glob("19_*.json"))))
    assert widget._environment_form.duration_note.isHidden()


def test_the_project_configuration_survives_the_editor_and_is_read_from_the_files_folder(widget, tmp_path):
    """Transparency audit, Phase 3b: the editor rebuilds the scenario from
    its fields, and the file named (shown on Scenario › Assumptions since
    Phase 3d) is kept, and read relative to the scenario file's folder at
    each to_scenario()."""
    from spacemissionstudio.schema import load_scenario

    (tmp_path / "project.yaml").write_text("parameters:\n  propellant_budget.cam_count_factor: 3\n", encoding="utf-8")
    scenario = load_scenario(_SCENARIO_PATH)
    scenario.config_file = "project.yaml"
    widget.set_base_dir_provider(lambda: tmp_path)
    widget.from_scenario(scenario)
    got = widget.to_scenario()
    assert got.config_file == "project.yaml"
    assert got.configuration.overrides == {"propellant_budget.cam_count_factor": 3.0}
