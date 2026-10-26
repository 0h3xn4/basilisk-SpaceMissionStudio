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
"""Validation messages with the forms' labels, not field codes
(docs/ux-standard.md, error texts; iteration 7d): "my-sat: Station
keeping: Reboost thrust [N] must be > 0", not "my-sat:
station_keeping.thrust_n must be > 0", in the banner, Problems, a field's
own error line and the generator dialogs. The messages themselves (the
command line, the Log) keep their codes."""

import copy
import dataclasses
import re
import typing
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_SNAKE = re.compile(r"(?<![\w'\-./])[a-z]+(?:_[a-z0-9]+)+(?![\w'\-(\[])")


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


def test_labelled_replaces_only_the_codes_it_is_given_titles_for():
    """A code becomes its title; plain words, file names, quoted keys,
    indexed names and codes without a title stay as they are; a bare code
    is looked up in the section of the dotted code before it, and a later
    title of the same section drops the section."""
    from spacemissionstudio.gui.field_text import labelled

    titles = {"station_keeping.deadband_km": "Station keeping: Deadband [km]",
              "station_keeping.target_altitude_km": "Station keeping: Target altitude [km]"}
    assert labelled("station_keeping.deadband_km must be > 0 and < target_altitude_km", titles.get) \
        == "Station keeping: Deadband [km] must be > 0 and < Target altitude [km]"
    unchanged = ("eccentricity must be < 1 (see oct2026f10-prd.txt and earth_latest_high_prec.bpc)",
                 "params['rw_type'] must be one of", "fsw_params['x'] is unknown", "other_field must be > 0",
                 "e.g. g instead of kg")
    for text in unchanged:
        assert labelled(text, titles.get) == text


def test_a_spacecraft_message_uses_the_spacecraft_form_labels(qtbot):
    """Section fields, the top-level fields, the orbit's fields and type,
    the navigation error grid and the AD10 budget inputs all have titles;
    a scenario setting a spacecraft message names comes from
    :attr:`other_titles`."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(simulation_mode="full_attitude")
    qtbot.addWidget(dialog)
    text = dialog.problem_text
    assert text("station_keeping.thrust_n must be > 0") == "Station keeping: Reboost thrust [N] must be > 0"
    assert text("dry_mass_kg must be in (0, 1e6]") == "Dry mass [kg] must be in (0, 1e6]"
    assert text("orbit: classical_elements orbit: semi_major_axis_km must be a finite number") \
        == "Orbit (Classical elements): Semi-major axis [km] must be a finite number"
    assert text("orbit: classical_elements orbit: true_anomaly_deg must be a finite number") \
        == "Orbit (Classical elements): True anomaly [deg] must be a finite number"
    assert text("navigation_error.attitude_bound_deg must be >= 0") \
        == "Navigation error: Attitude bound must be >= 0"
    assert text("propellant_budget.mission_years must be > 0").endswith("Mission duration must be > 0")
    assert text("fuel_tank.propellant_mass_kg must be between 0 and fuel_tank.max_propellant_mass_kg") \
        == "Fuel tank: Propellant mass [kg] must be between 0 and Tank capacity [kg]"
    assert "sim_settings.duration_days" in text("phasing_keeping runs at most 100 days (sim_settings.duration_days)")
    dialog.other_titles = {"sim_settings.duration_days": "Simulation settings: Duration [days]"}.get
    assert text("phasing_keeping runs at most 100 days (sim_settings.duration_days)") \
        == "Phasing keeping runs at most 100 days (Simulation settings: Duration [days])"


def test_every_numeric_spacecraft_field_has_a_title(qtbot):
    """Each number of a spacecraft and of its sections (but the orbit, whose
    fields are tested above, and the 3D model, edited in its own dialog)
    has a widget with a label: a new field without one would show its code."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import scenario

    dialog = SpacecraftEditorDialog(simulation_mode="full_attitude")
    qtbot.addWidget(dialog)
    hints = typing.get_type_hints(scenario.SpacecraftConfig, vars(scenario))

    def inner(annotation):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return args[0] if args else annotation

    missing = []
    for field in dataclasses.fields(scenario.SpacecraftConfig):
        annotation = inner(hints[field.name])
        if field.name in ("orbit", "model"):
            continue
        if dataclasses.is_dataclass(annotation):
            section_hints = typing.get_type_hints(annotation, vars(scenario))
            codes = [f"{field.name}.{f.name}" for f in dataclasses.fields(annotation)
                     if inner(section_hints[f.name]) in (int, float)]
        else:
            codes = [field.name] if annotation in (int, float) else []
        missing += [code for code in codes if not dialog.field_title(code)]
    assert missing == []


@pytest.fixture
def editor(qtbot):
    """A Scenario Editor with template 18 (one spacecraft with station
    keeping and a power budget) loaded; no form built yet."""
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema.scenario import load_scenario

    widget = ScenarioEditorWidget()
    qtbot.addWidget(widget)
    widget.from_scenario(load_scenario(_TEMPLATES / "18_leo_station_keeping.json"))
    return widget


def test_the_editor_shows_every_message_with_labels(editor):
    """problem_display: a spacecraft's message (its form not built yet),
    the Environment's, Monte Carlo's and a scenario field's; a message
    about nothing it knows stays as it is."""
    name = editor.spacecraft_list.to_list()[0].name
    assert editor._spacecraft_nodes[0].form is None
    assert editor.problem_display(f"{name}: station_keeping.thrust_n must be > 0") \
        == f"{name}: Station keeping: Reboost thrust [N] must be > 0"
    assert editor.problem_display("sim_settings.duration_days must be > 0") \
        == "Simulation settings: Duration [days] must be > 0"
    assert editor.problem_display("monte_carlo.num_runs must be a whole number, got 0.0") \
        == "Monte Carlo: Number of runs must be a whole number, got 0.0"
    assert editor.problem_display("scenario.epoch_utc '2030-13-45' is not ISO 8601").startswith("Epoch (UTC)")
    assert editor.problem_display("unknown_thing: something_else is off") == "unknown_thing: something_else is off"


def test_no_template_message_shows_a_field_code(editor):
    """Every message validate() gives for a bad number in template 18's
    spacecraft, simulation settings or gravity (each set to -1, 0, NaN and
    1e12) shows without a snake_case code, beyond quoted values."""
    from spacemissionstudio.schema.scenario import ScenarioValidationError, load_scenario

    base = load_scenario(_TEMPLATES / "18_leo_station_keeping.json")

    def numbers(obj, path=""):
        for f in dataclasses.fields(obj):
            value, where = getattr(obj, f.name), f"{path}.{f.name}" if path else f.name
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                yield where
            elif dataclasses.is_dataclass(value):
                yield from numbers(value, where)

    targets = ([("spacecraft", p) for p in numbers(base.spacecraft[0])]
               + [("sim_settings", p) for p in numbers(base.sim_settings)] + [("gravity", p) for p in numbers(base.gravity)])
    shown = {}
    for owner, path in targets:
        for bad in (-1.0, 0.0, float("nan"), 1e12):
            scenario = copy.deepcopy(base)
            obj = scenario.spacecraft[0] if owner == "spacecraft" else getattr(scenario, owner)
            *parents, leaf = path.split(".")
            for part in parents:
                obj = getattr(obj, part)
            setattr(obj, leaf, bad)
            try:
                scenario.validate()
            except ScenarioValidationError as exc:
                shown[str(exc)] = editor.problem_display(str(exc))
    assert len(shown) > 20
    left = {raw: text for raw, text in shown.items() if _SNAKE.search(text)}
    assert left == {}


def test_problems_and_the_banner_show_the_labels(qtbot, editor):
    """A bad value typed into the spacecraft's live form: the form's banner,
    the field's own line and the Problems row all say "Station keeping:
    Reboost thrust [N]"."""
    from spacemissionstudio.gui.feedback import _error_label

    editor.show_spacecraft(0)
    qtbot.waitUntil(lambda: editor._spacecraft_nodes[0].form is not None)
    form = editor._spacecraft_nodes[0].form
    name = form.name_edit.text()
    form.show_problem("station_keeping.thrust_n", f"{name}: station_keeping.thrust_n must be > 0", focus=False)
    assert "Station keeping: Reboost thrust [N] must be > 0" in form.problem_banner.label.text()
    label = _error_label(form.sk_thrust_n)
    assert label is not None and "Reboost thrust [N]" in label.text()
    editor.problems = [("error", f"{name}: station_keeping.thrust_n must be > 0")]
    assert editor.problem_rows()[0][1] == f"{name}: station_keeping.thrust_n must be > 0"  # the message keeps its code
    assert editor.problem_rows()[0][2] == f"{name}: Station keeping: Reboost thrust [N] must be > 0"


def test_a_generator_dialog_names_its_own_fields(qtbot):
    """The Walker dialog's error names "Total satellites" and "Number of
    planes", not constellation.total_satellites and num_planes."""
    from spacemissionstudio.gui.constellation_dialog import WalkerConstellationDialog
    from spacemissionstudio.gui.feedback import dialog_error_text

    dialog = WalkerConstellationDialog([])
    qtbot.addWidget(dialog)
    dialog.total_satellites.setValue(5)
    dialog.num_planes.setValue(2)
    dialog._on_accept()
    text = dialog_error_text(dialog)
    assert "Total satellites" in text and "Number of planes" in text
    assert "total_satellites" not in text and "num_planes" not in text


def test_the_spacecraft_labels_are_the_forms_without_keeping_one(qtbot):
    """SpacecraftLabels gives every code of the schema, and every message
    validate() gives for template 18's spacecraft, the titles a new
    spacecraft's form gives them; afterwards no spacecraft form is left
    (it was 1,000 hidden widgets every theme switch restyled)."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.spacecraft_editor import (SpacecraftEditorDialog, SpacecraftLabels,
                                                          _spacecraft_field_codes)
    from spacemissionstudio.schema.scenario import ScenarioValidationError, load_scenario

    labels = SpacecraftLabels()
    base = load_scenario(_TEMPLATES / "18_leo_station_keeping.json")
    messages = []
    for path in ("dry_mass_kg", "drag_area_m2", "station_keeping.thrust_n", "station_keeping.deadband_km",
                 "drag_coeff", "inertia_kg_m2"):
        scenario = copy.deepcopy(base)
        obj, *parents, leaf = [scenario.spacecraft[0], *path.split(".")]
        for part in parents:
            obj = getattr(obj, part)
        setattr(obj, leaf, -1.0 if leaf != "inertia_kg_m2" else [-1.0] * 9)
        try:
            scenario.validate()
        except ScenarioValidationError as exc:
            messages.append(str(exc))
    assert len(messages) >= 4
    shown = {message: labels.problem_text(message) for message in messages}
    titles = {code: labels.field_title(code) for code in _spacecraft_field_codes() + ["fsw_params.k_p"]}
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not [w for w in QApplication.allWidgets() if isinstance(w, SpacecraftEditorDialog)]

    form = SpacecraftEditorDialog(embedded=True)
    qtbot.addWidget(form)
    assert shown == {message: form.problem_text(message) for message in messages}
    assert titles == {code: form.field_title(code) for code in titles}
