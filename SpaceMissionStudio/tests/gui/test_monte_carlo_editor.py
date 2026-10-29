"""Tests for gui.monte_carlo_editor."""

import pytest

pytestmark = pytest.mark.requires_gui


def test_group_default_state(qtbot):
    """The Monte Carlo group starts off, with 10 runs, 1 thread and no
    dispersions."""
    from spacemissionstudio.gui.monte_carlo_editor import MonteCarloGroupWidget

    widget = MonteCarloGroupWidget()
    qtbot.addWidget(widget)
    config = widget.to_dataclass()
    assert config.enabled is False
    assert config.num_runs == 10
    assert config.thread_count == 1
    assert config.dispersions == []


def test_group_round_trip(qtbot):
    """Monte Carlo's settings and an attitude dispersion come back from the
    group."""
    from spacemissionstudio.gui.monte_carlo_editor import MonteCarloGroupWidget
    from spacemissionstudio.schema.scenario import DispersionConfig, MonteCarloConfig

    widget = MonteCarloGroupWidget()
    qtbot.addWidget(widget)
    widget.set_spacecraft_names(["sat-1"])
    mc = MonteCarloConfig(
        enabled=True, num_runs=42, thread_count=3, verbose=True,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="attitude_sigma_bn", kind="uniform_euler_mrp",
                                       bounds=[0.0, 6.28])],
    )
    widget.from_dataclass(mc)
    got = widget.to_dataclass()
    assert got.enabled is True
    assert got.num_runs == 42
    assert got.thread_count == 3
    assert got.verbose is True
    assert got.dispersions[0].quantity == "attitude_sigma_bn"
    assert got.dispersions[0].bounds == [0.0, 6.28]


def test_dispersion_dialog_uniform(qtbot):
    """A uniform dispersion gives its spacecraft, quantity and bounds and no
    mean."""
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog

    dialog = _DispersionEditorDialog(["sat-1", "sat-2"])
    qtbot.addWidget(dialog)
    dialog.spacecraft_combo.setCurrentText("sat-2")
    dialog.quantity_combo.setCurrentText("dry_mass_kg")
    dialog.kind_combo.setCurrentText("uniform")
    dialog.bounds_lo_spin.setValue(90.0)
    dialog.bounds_hi_spin.setValue(110.0)

    config = dialog.to_dataclass()
    assert config.spacecraft == "sat-2"
    assert config.quantity == "dry_mass_kg"
    assert config.kind == "uniform"
    assert config.bounds == [90.0, 110.0]
    assert config.mean is None


def test_dispersion_dialog_normal(qtbot):
    """A normal dispersion gives its mean and standard deviation and no
    bounds."""
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog

    dialog = _DispersionEditorDialog(["sat-1"])
    qtbot.addWidget(dialog)
    dialog.quantity_combo.setCurrentText("dry_mass_kg")
    dialog.kind_combo.setCurrentText("normal")
    dialog.mean_spin.setValue(100.0)
    dialog.std_spin.setValue(5.0)

    config = dialog.to_dataclass()
    assert config.kind == "normal"
    assert config.mean == 100.0
    assert config.std_deviation == 5.0
    assert config.bounds is None


def test_dispersion_dialog_hides_fields_not_used_by_the_selected_kind(qtbot):
    """Regression guard for a real bug: Bounds/Mean/Std-deviation used
    to all be visible and editable at once regardless of Kind, even
    though to_dataclass() only ever uses the pair matching the current
    kind -- a value typed into the "wrong" row was silently discarded
    with no indication. Only the relevant row(s) should be visible.
    """
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog

    dialog = _DispersionEditorDialog(["sat-1"])
    qtbot.addWidget(dialog)
    dialog.show()  # isVisible() below needs the whole ancestor chain shown, not just setVisible() called
    dialog.quantity_combo.setCurrentText("dry_mass_kg")

    dialog.kind_combo.setCurrentText("uniform")
    assert dialog.bounds_lo_spin.isVisible()
    assert dialog.bounds_hi_spin.isVisible()
    assert not dialog.mean_spin.isVisible()
    assert not dialog.std_spin.isVisible()

    dialog.kind_combo.setCurrentText("normal")
    assert not dialog.bounds_lo_spin.isVisible()
    assert not dialog.bounds_hi_spin.isVisible()
    assert dialog.mean_spin.isVisible()
    assert dialog.std_spin.isVisible()


def test_dispersion_dialog_builds_an_orbit_element_dispersion(qtbot):
    """The orbit is dispersed element by element: only the spreads show, and
    elements left at 0 are not written."""
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog

    dialog = _DispersionEditorDialog(["sat-1"])
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.quantity_combo.setCurrentText("orbit_elements")
    dialog.kind_combo.setCurrentText("normal")
    assert dialog.element_spins["semi_major_axis_km"].isVisible()
    assert not dialog.mean_spin.isVisible() and not dialog.std_spin.isVisible()
    assert not dialog.bounds_lo_spin.isVisible()
    dialog.element_spins["semi_major_axis_km"].setValue(0.5)
    dialog.element_spins["true_anomaly_deg"].setValue(0.01)
    config = dialog.to_dataclass()
    assert config.element_spread == {"semi_major_axis_km": 0.5, "true_anomaly_deg": 0.01}
    assert config.mean is None and config.std_deviation is None and config.bounds is None


def test_dispersion_dialog_round_trips_the_new_quantities(qtbot):
    """Inertia (with its angle), body rate and the coefficients survive
    open-and-OK unchanged."""
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog
    from spacemissionstudio.schema.scenario import DispersionConfig

    for item in (
        DispersionConfig(spacecraft="sat-1", quantity="inertia_kg_m2", kind="normal", std_deviation=0.4,
                         angle_std_deg=1.5),
        DispersionConfig(spacecraft="sat-1", quantity="angular_rate_bn_b", kind="uniform", bounds=[-0.1, 0.1]),
        DispersionConfig(spacecraft="sat-1", quantity="angular_rate_bn_b", kind="normal", std_deviation=0.05),
        DispersionConfig(spacecraft="sat-1", quantity="drag_coeff", kind="normal", mean=2.5, std_deviation=0.2),
        DispersionConfig(spacecraft="sat-1", quantity="srp_coeff", kind="uniform", bounds=[1.2, 1.5]),
        DispersionConfig(spacecraft="sat-1", quantity="orbit_elements", kind="uniform",
                         element_spread={"inclination_deg": 0.05}),
    ):
        dialog = _DispersionEditorDialog(["sat-1"], item)
        qtbot.addWidget(dialog)
        assert dialog.to_dataclass() == item, item.quantity


def test_dispersion_dialog_kind_choices_follow_quantity(qtbot):
    """The kinds offered follow the quantity: uniform_euler_mrp for the
    attitude, uniform or normal for the dry mass."""
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog

    dialog = _DispersionEditorDialog(["sat-1"])
    qtbot.addWidget(dialog)
    dialog.quantity_combo.setCurrentText("attitude_sigma_bn")
    kinds = [dialog.kind_combo.itemText(i) for i in range(dialog.kind_combo.count())]
    assert kinds == ["uniform_euler_mrp"]

    dialog.quantity_combo.setCurrentText("dry_mass_kg")
    kinds = [dialog.kind_combo.itemText(i) for i in range(dialog.kind_combo.count())]
    assert set(kinds) == {"uniform", "normal"}


def test_dispersion_dialog_stale_spacecraft_is_preserved_not_silently_swapped(qtbot):
    """Regression test: item.spacecraft naming a spacecraft that no longer
    exists in spacecraft_names (e.g. renamed/removed since this dispersion
    was saved) used to be silently dropped -- findText() returned -1,
    nothing set the combo's index, and it stayed on whatever was first,
    re-targeting the dispersion at the WRONG spacecraft with no indication
    anything had changed. It must instead be round-tripped as-is.
    """
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog
    from spacemissionstudio.schema.scenario import DispersionConfig

    stale = DispersionConfig(spacecraft="renamed-sat", quantity="dry_mass_kg", kind="uniform", bounds=[90.0, 110.0])
    # "renamed-sat" is NOT in spacecraft_names -- simulates the referenced
    # spacecraft having been renamed/removed after this dispersion was saved.
    dialog = _DispersionEditorDialog(["some-other-sat"], item=stale)
    qtbot.addWidget(dialog)

    assert dialog.spacecraft_combo.currentData() == "renamed-sat"
    got = dialog.to_dataclass()
    assert got.spacecraft == "renamed-sat"


def test_dispersion_dialog_rejects_when_no_spacecraft(qtbot):
    """A dispersion without a spacecraft to choose is refused when the dialog
    is read."""
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog

    dialog = _DispersionEditorDialog([])
    qtbot.addWidget(dialog)
    with pytest.raises(ValueError, match="no spacecraft"):
        dialog.to_dataclass()


def test_dispersion_list_add_edit_remove(qtbot, monkeypatch):
    """Add lists a dispersion as one change; Edit keeps one; Remove deletes
    it."""
    from spacemissionstudio.gui.monte_carlo_editor import DispersionListWidget

    widget = DispersionListWidget()
    qtbot.addWidget(widget)
    widget.set_spacecraft_names(["sat-1"])
    changed_count = []
    widget.changed.connect(lambda: changed_count.append(1))

    widget._on_add()
    assert len(widget.to_list()) == 1
    assert changed_count == [1]

    widget.list_widget.setCurrentRow(0)
    form = widget.inline.form  # the selected dispersion's form, under the list (M4b)
    form.quantity_combo.setCurrentText("dry_mass_kg")
    form.kind_combo.setCurrentText("uniform")
    form.bounds_lo_spin.setValue(1.0)
    form.bounds_hi_spin.setValue(2.0)
    widget.inline.flush()
    assert len(widget.to_list()) == 1
    assert widget.to_list()[0].quantity == "dry_mass_kg" and widget.to_list()[0].bounds == [1.0, 2.0]

    widget.list_widget.setCurrentRow(0)
    widget._on_remove()


def test_dispersion_list_add_and_remove_show_a_toast(qtbot, monkeypatch):
    """Adding and removing a dispersion each show a toast; the added one is
    selected."""
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.gui.monte_carlo_editor import DispersionListWidget, _DispersionEditorDialog

    widget = DispersionListWidget()
    qtbot.addWidget(widget)
    widget.set_spacecraft_names(["sat-1"])

    def fake_exec(self):
        self.quantity_combo.setCurrentText("dry_mass_kg")
        self.kind_combo.setCurrentText("uniform")
        self.bounds_lo_spin.setValue(1.0)
        self.bounds_hi_spin.setValue(2.0)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_DispersionEditorDialog, "exec", fake_exec)
    widget._on_add()

    assert widget.list_widget.currentRow() == 0
    toasts = getattr(widget.window(), "_spacemissionstudio_active_toasts", [])
    assert any("dry_mass_kg" in t.text() and "Added" in t.text() for t in toasts)

    widget.list_widget.setCurrentRow(0)
    widget._on_remove()

    toasts = getattr(widget.window(), "_spacemissionstudio_active_toasts", [])
    assert any("Removed" in t.text() for t in toasts)
    assert widget.to_list() == []


def test_dispersion_editor_dialog_resizes_to_its_own_sizehint_on_construction(qtbot):
    """See test_constellation_dialog.py's identical test for why."""
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog

    dialog = _DispersionEditorDialog(spacecraft_names=["sat-1"])
    qtbot.addWidget(dialog)

    assert dialog.size() == dialog.sizeHint()


def test_a_new_dispersion_starts_at_the_spacecrafts_own_value_with_no_spread(qtbot):
    """Transparency audit 3.7: an untouched Add gave dry mass uniform in
    [0, 1] kg, written absolutely, so every run flew a 0 to 1 kg spacecraft.
    It now starts at the spacecraft's own dry mass with no spread; the toast
    says to widen it. The scenario editor hands the spacecraft's values over."""
    from spacemissionstudio.gui.monte_carlo_editor import DispersionListWidget

    widget = DispersionListWidget()
    qtbot.addWidget(widget)
    widget.set_spacecraft_names(["sat-1"], {"sat-1": {"dry_mass_kg": 150.0, "drag_coeff": 2.2, "srp_coeff": 1.3}})
    widget._on_add()
    item = widget.to_list()[0]
    assert item.quantity == "dry_mass_kg"
    if item.kind == "uniform":
        assert item.bounds == [150.0, 150.0]
    else:
        assert (item.mean, item.std_deviation) == (150.0, 0.0)
    toasts = getattr(widget.window(), "_spacemissionstudio_active_toasts", [])
    assert any("own 150 with no spread" in t.text() for t in toasts)


def test_the_scenario_editor_gives_the_dispersions_each_spacecrafts_own_values(qtbot):
    """The values a new dispersion starts at come from the scenario's spacecraft."""
    from pathlib import Path

    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    template = (Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
                / "25_monte_carlo_orbit_and_drag_dispersions.json")
    scenario = load_scenario(template)
    editor = ScenarioEditorWidget()
    qtbot.addWidget(editor)
    editor.from_scenario(scenario)
    nominals = editor.monte_carlo_group.dispersion_list._nominals
    sc = scenario.spacecraft[0]
    assert nominals[sc.name] == {"dry_mass_kg": sc.dry_mass_kg, "drag_coeff": sc.drag_coeff, "srp_coeff": sc.srp_coeff}
