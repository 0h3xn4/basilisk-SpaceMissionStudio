#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Computed and overridden values in the editor (the transparency plan,
Phase 5b, second step): the orbit's compute buttons mark the value
computed, a note under the field says so, an edited value can be given a
reason (overridden), and the marks follow the spacecraft."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_PATH = "spacecraft[leo-comms-1].orbit.inclination_deg"


@pytest.fixture
def editor(qtbot):
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    widget = ScenarioEditorWidget()
    qtbot.addWidget(widget)
    widget.from_scenario(load_scenario(next(_TEMPLATES.glob("19_*.json"))))  # leo-comms-1, Sun-synchronous
    widget.show_spacecraft(0)
    qtbot.waitUntil(lambda: widget._spacecraft_nodes[0].form is not None)
    return widget


def _orbit(editor):
    return editor._spacecraft_nodes[0].form.orbit_widget


def _compute_inclination(editor, qtbot):
    orbit = _orbit(editor)
    orbit.sma_km.setValue(7000.0)  # [km] away from the template's own value
    orbit._on_compute_sso_inclination()
    editor.flush_forms()
    editor.revalidate()
    return orbit


def test_the_sun_synchronous_button_marks_the_inclination_computed(editor, qtbot):
    """The button writes the inclination, as before, and the scenario
    records it as computed, with the value the field holds and its source;
    the note under the field says so."""
    from spacemissionstudio.engine.orbit_design import sun_synchronous_inclination_deg

    orbit = _compute_inclination(editor, qtbot)
    scenario = editor.to_scenario()
    (mark,) = scenario.value_marks
    assert (mark.path, mark.state) == (_PATH, "computed")
    assert mark.value == scenario.spacecraft[0].orbit.inclination_deg == orbit.inc_deg.value()
    assert mark.value == pytest.approx(sun_synchronous_inclination_deg(7000.0, orbit.ecc.value()), abs=1e-4)
    assert "Sun-synchronous inclination at a = 7000 km" in mark.source and mark.time_utc
    note = orbit.mark_notes["inclination_deg"]
    assert note.isVisibleTo(orbit) and note.status == "computed"
    assert note.label.text().startswith("Computed: Sun-synchronous inclination")
    assert not note.reason_button.isVisibleTo(orbit)
    assert not orbit.mark_notes["raan_deg"].isVisibleTo(orbit)  # a field without a mark shows nothing


def test_an_edited_value_can_be_given_a_reason(editor, qtbot, monkeypatch):
    """Edited by hand: the note says so and offers Give a reason...; the
    reason given marks the value overridden, kept with the scenario."""
    from PySide6.QtWidgets import QInputDialog

    orbit = _compute_inclination(editor, qtbot)
    computed = orbit.inc_deg.value()
    orbit.inc_deg.setValue(98.0)  # [deg]
    editor.flush_forms()
    editor.revalidate()
    note = orbit.mark_notes["inclination_deg"]
    assert note.status == "edited" and note.label.text() == f"Edited (computed {computed:g} deg)"
    assert note.reason_button.isVisibleTo(orbit)
    asked = []
    monkeypatch.setattr(QInputDialog, "getMultiLineText",
                        lambda *args, **kwargs: (asked.append(args[2]) or "the launcher's injection orbit", True))
    note.reason_button.click()
    assert "Computed: " in asked[0] and "Used: 98" in asked[0]
    (mark,) = editor.to_scenario().value_marks
    assert (mark.state, mark.reason, mark.value) == ("overridden", "the launcher's injection orbit", computed)
    assert note.status == "overridden" and "the launcher's injection orbit" in note.label.text()
    assert not note.reason_button.isVisibleTo(orbit)


def test_a_cancelled_reason_changes_nothing(editor, qtbot, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    orbit = _compute_inclination(editor, qtbot)
    orbit.inc_deg.setValue(98.0)  # [deg]
    editor.flush_forms()
    editor.revalidate()
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *args, **kwargs: ("", False))
    orbit.mark_notes["inclination_deg"].reason_button.click()
    assert editor.to_scenario().value_marks[0].state == "computed"


def test_the_marks_follow_a_rename_and_go_with_the_spacecraft(editor, qtbot):
    _compute_inclination(editor, qtbot)
    form = editor._spacecraft_nodes[0].form
    form.name_edit.setText("leo-comms-2")
    editor.flush_forms()
    editor.revalidate()
    (mark,) = editor.to_scenario().value_marks
    assert mark.path == "spacecraft[leo-comms-2].orbit.inclination_deg"
    editor.spacecraft_list.from_list([])  # the spacecraft removed
    editor.revalidate()
    assert editor.draft_scenario().value_marks == []


def test_a_scenario_with_marks_opens_with_its_notes(qtbot):
    """A scenario saved with an overridden value shows its note when the
    spacecraft's page opens; the scenario keeps the mark unchanged."""
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio.schema.scenario import ValueMark

    scenario = load_scenario(next(_TEMPLATES.glob("19_*.json")))
    used = scenario.spacecraft[0].orbit.inclination_deg
    scenario.value_marks = [ValueMark(_PATH, "overridden", 97.0, "Sun-synchronous inclination",
                                      reason="the customer's orbit")]
    widget = ScenarioEditorWidget()
    qtbot.addWidget(widget)
    widget.from_scenario(scenario)
    widget.show_spacecraft(0)
    qtbot.waitUntil(lambda: widget._spacecraft_nodes[0].form is not None)
    note = widget._spacecraft_nodes[0].form.orbit_widget.mark_notes["inclination_deg"]
    assert note.status == "overridden" and note.label.text() == "Overridden (computed 97 deg): the customer's orbit"
    assert f"Value used: {used:g} deg" in note.toolTip()
    assert widget.to_scenario().value_marks == scenario.value_marks


def test_the_wizard_marks_the_inclination_it_recomputes(qtbot):
    """A starter template's wizard keeps the orbit Sun-synchronous at the
    new size: the inclination it recomputes is marked computed."""
    from spacemissionstudio.engine.orbit_design import sun_synchronous_inclination_deg
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard, get_wizard_spec
    from spacemissionstudio.schema import load_scenario

    name = "22_starter_first_leo_satellite.json"
    wizard = TemplateCustomizeWizard(load_scenario(TEMPLATES_DIR / name), get_wizard_spec(name))
    qtbot.addWidget(wizard)
    wizard.page(0)._boxes[0].setValue(6978.0)  # [km] semi-major axis, 600 km
    wizard.accept()
    result = wizard.result_scenario()
    result.validate()
    (mark,) = result.value_marks
    orbit = result.spacecraft[0].orbit
    assert mark.path == f"spacecraft[{result.spacecraft[0].name}].orbit.inclination_deg"
    assert mark.value == orbit.inclination_deg == sun_synchronous_inclination_deg(6978.0, orbit.eccentricity)
    assert "set by the template's wizard" in mark.source


def test_a_generated_constellation_is_marked_computed(qtbot, monkeypatch):
    """Generate Walker constellation... marks each satellite's computed
    elements, and its Sun-synchronous inclination when the dialog's button
    set it; the satellites' pages show the notes."""
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.engine.constellation import WalkerConstellationRequest
    from spacemissionstudio.gui import constellation_dialog
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    class _Dialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def to_request(self):
            return WalkerConstellationRequest(total_satellites=2, num_planes=2, phasing_factor=0, altitude_km=550.0,
                                              inclination_deg=97.5976, name_prefix="walker")

        def selected_template_name(self):
            return None

        def inclination_source(self):
            return "Sun-synchronous inclination at a = 6928.14 km, e = 0 (engine.orbit_design)"

    monkeypatch.setattr(constellation_dialog, "WalkerConstellationDialog", _Dialog)
    editor = ScenarioEditorWidget()
    qtbot.addWidget(editor)
    editor.from_scenario(load_scenario(next(_TEMPLATES.glob("01_*.json"))))  # two-body: no J2
    editor.spacecraft_list._on_generate_constellation()
    editor.revalidate()
    marks = {mark.path: mark for mark in editor.to_scenario().value_marks}
    assert marks["spacecraft[walker-02-01].orbit.raan_deg"].value == 180.0
    inclination = marks["spacecraft[walker-01-01].orbit.inclination_deg"]
    assert inclination.value == 97.5976 and inclination.source.startswith("Sun-synchronous")
    row = [c.name for c in editor.spacecraft_list.to_list()].index("walker-02-01")
    editor.show_spacecraft(row)
    qtbot.waitUntil(lambda: editor._spacecraft_nodes[row].form is not None)
    notes = editor._spacecraft_nodes[row].form.orbit_widget.mark_notes
    assert notes["raan_deg"].status == "computed" and "plane 2 of 2" in notes["raan_deg"].label.text()


def test_the_note_says_what_an_edit_changes(editor, qtbot):
    """An edited Sun-synchronous inclination: the note says the node now
    drifts from the Sun; back at the computed value, it says nothing more."""
    orbit = _compute_inclination(editor, qtbot)
    computed = orbit.inc_deg.value()
    orbit.inc_deg.setValue(computed + 1.0)  # [deg]
    editor.flush_forms()
    editor.revalidate()
    note = orbit.mark_notes["inclination_deg"]
    assert note.label.text() == f"Edited (computed {computed:g} deg)"  # the status line as before
    assert "Not Sun-synchronous: the node moves" in note.consequence_label.text()
    assert note.consequence_label.isVisibleTo(orbit) and "Changes: The node drifts" in note.toolTip()
    orbit.inc_deg.setValue(computed)
    editor.flush_forms()
    editor.revalidate()
    assert note.status == "computed" and not note.consequence_label.isVisibleTo(orbit)


def test_new_from_template_records_the_preset(qtbot, monkeypatch):
    """New from template... adds the spacecraft and records its preset;
    the spacecraft's page says how many values are as the preset gave
    them, and a change shows."""
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
    from spacemissionstudio.gui import spacecraft_template_dialog
    from spacemissionstudio.gui.scenario_editor import ScenarioEditorWidget
    from spacemissionstudio.schema import load_scenario

    class _Picker:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def selected_template(self):
            return SPACECRAFT_TEMPLATES[1]

    monkeypatch.setattr(spacecraft_template_dialog, "SpacecraftTemplateDialog", _Picker)
    editor = ScenarioEditorWidget()
    qtbot.addWidget(editor)
    editor.from_scenario(load_scenario(next(_TEMPLATES.glob("19_*.json"))))
    editor.spacecraft_list._on_new_from_template()
    qtbot.waitUntil(lambda: editor._spacecraft_nodes[-1].form is not None)
    editor.revalidate()
    (record,) = editor.draft_scenario().presets
    assert record.preset == SPACECRAFT_TEMPLATES[1].name and record.spacecraft == editor._spacecraft_nodes[-1].config.name
    form = editor._spacecraft_nodes[-1].form
    assert form.preset_label.isVisibleTo(form)
    assert form.preset_label.text() == (f"From preset {record.preset}: {len(record.values)} of {len(record.values)} "
                                        "values as it gave them")
    form.dry_mass_kg.setValue(form.dry_mass_kg.value() + 10.0)  # [kg]
    editor.flush_forms()
    editor.revalidate()
    assert form.preset_label.text().endswith(", 1 changed") and "dry_mass_kg" in form.preset_label.toolTip()
    assert not editor._spacecraft_nodes[0].form or not editor._spacecraft_nodes[0].form.preset_label.isVisible()
