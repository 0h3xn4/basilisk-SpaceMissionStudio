#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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

"""The power budget an IDM-CIC import offers, in the GUI: the import
dialog's **Power** section (system modes, the duty-cycle average, the
panel normal's side) and the values chosen reaching the spacecraft through
the 3D model editor's OK, from the spacecraft list and from a spacecraft
dialog. The model is the synthetic fixture ``tests/data/idm/powersat``."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/, for idm_fixtures
from idm_fixtures import model_xml, write_idm  # noqa: E402

pytestmark = pytest.mark.requires_gui

_TEMPLATE = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates" / \
    "06_attitude_pointing_basic.json"


def _dialog(qtbot, tmp_path, devices_allowed=True):
    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(write_idm(tmp_path / "powersat.idm", model_xml("powersat")),
                             devices_allowed=devices_allowed)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: not dialog.busy() and dialog.plan() is not None, timeout=30000)
    return dialog


def test_the_dialog_offers_the_system_modes_and_the_panel_sides(qtbot, tmp_path):
    """Each system mode with its power, then the duty-cycle average; the
    panel normal either way; nothing ticked until chosen, and the choice
    returned is what is shown."""
    dialog = _dialog(qtbot, tmp_path)
    assert [dialog.bus_combo.itemText(i) for i in range(dialog.bus_combo.count())] == [
        "system mode Cruise: 10.5 W", "system mode Downlink: 4.5 W", "duty-cycle average: 9.3 W"]
    assert dialog.normal_combo.itemText(1).startswith("- [0, -1, 0]: 0.96 m^2, 1 panel(s)")
    assert not dialog.power_choice().any
    dialog.bus_check.setChecked(True)
    dialog.bus_combo.setCurrentIndex(2)
    dialog.panels_check.setChecked(True)
    dialog.normal_combo.setCurrentIndex(1)
    choice = dialog.power_choice()
    assert (choice.bus_load, choice.panels, choice.normal_sign) == ("average", True, -1)


def test_an_orbit_only_scenario_sets_no_power(qtbot, tmp_path):
    """Orbit only: the modes are shown, nothing can be ticked, and the note
    says why."""
    dialog = _dialog(qtbot, tmp_path, devices_allowed=False)
    assert not dialog.bus_check.isEnabled() and not dialog.panels_check.isEnabled()
    assert "orbit only" in dialog.power_note.text()
    assert not dialog.power_choice().any


def _editor_result(tmp_path, scenario, choice):
    """What a 3D model editor's OK hands over after an import with power
    budget values chosen."""
    from spacemissionstudio import idm, idm_import

    plan = idm_import.plan(idm.load(write_idm(tmp_path / "powersat.idm", model_xml("powersat"))))
    sat = scenario.spacecraft[0]
    idm_import.merge(scenario, sat.name, plan, tmp_path / "scenario.json")
    record = next(r for r in scenario.imports if r.target == "model")
    return SimpleNamespace(spacecraft_name=sat.name, model=lambda: sat.model, devices=lambda: None,
                           import_record=lambda: record, device_import=lambda: None,
                           power_import=lambda: (plan, choice))


def test_the_spacecraft_list_sets_the_power_budget_on_the_editor_s_ok(qtbot, tmp_path):
    """From the spacecraft list: the budget is made with the bus load and
    panels chosen, and the power record is emitted after the model's."""
    from spacemissionstudio import idm_import
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATE)
    widget = SpacecraftListWidget()
    qtbot.addWidget(widget)
    widget.from_list(scenario.spacecraft)
    widget.set_simulation_mode_provider(lambda: "full_attitude")
    records = []
    widget.import_recorded.connect(records.append)
    widget._apply_model_editor(_editor_result(tmp_path, scenario, idm_import.PowerChoice("Cruise", True)))
    [sat] = widget.to_list()
    assert sat.power.bus_idle_power_w == pytest.approx(10.5) and sat.power.panel_area_m2 == pytest.approx(0.96)
    assert [r.target for r in records] == ["model", "power"]


def test_a_spacecraft_dialog_fills_its_power_page(qtbot, tmp_path, monkeypatch):
    """From a spacecraft dialog: the Power page is turned on and filled,
    its pending imports hold the power record, and the message says what
    was set and what is still the editor's."""
    from spacemissionstudio import idm_import
    from spacemissionstudio.gui import spacecraft_editor
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

    reported = []
    monkeypatch.setattr(spacecraft_editor, "report", lambda widget, text, kind="error": reported.append(text))
    scenario = load_scenario(_TEMPLATE)
    dialog = SpacecraftEditorDialog(config=scenario.spacecraft[0], simulation_mode="full_attitude")
    qtbot.addWidget(dialog)
    editor = _editor_result(tmp_path, scenario, idm_import.PowerChoice("Downlink", True, -1))
    dialog._set_imported_power(*editor.power_import())
    assert dialog.power_group.isChecked()
    assert dialog.bus_idle_power_w.value() == pytest.approx(4.5)
    assert dialog.panel_area_m2.value() == pytest.approx(0.96)
    assert dialog.panel_normal_y.value() == pytest.approx(-1.0)
    assert [r.target for r in dialog.pending_imports()] == ["power"]
    power = dialog.to_dataclass().power
    assert (power.bus_idle_power_w, power.panel_normal_b) == (pytest.approx(4.5), [0.0, -1.0, 0.0])
    assert reported[0].startswith("Power budget from the IDM-CIC model: made (it had none)")
