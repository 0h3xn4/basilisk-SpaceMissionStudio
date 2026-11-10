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

"""The power budget an IDM-CIC model gives (``spacemissionstudio.idm.power``,
``idm_import.apply_power``, ``idm-import --bus-load/--solar-panels``): the
power of the imported equipment in each system mode, and the solar array
panels' area and normal. The fixture ``tests/data/idm/powersat`` is
synthetic (made-up names, modes and powers): system mode Cruise (duty cycle
0.8) links the element mode Quiet (star tracker 1.5 W, wheel 3 W, gyro
6 W); Downlink (0.2) maps units directly (wheel a custom 4.5 W, gyro 0 W,
star tracker not mapped); one flat 1.2 m x 0.8 m panel faces along y."""

import dataclasses
import shutil
from pathlib import Path

import numpy as np
import pytest
from idm_fixtures import model_xml, write_idm

from spacemissionstudio import cli, idm, idm_import
from spacemissionstudio.engine.scenario_checks import scenario_warnings
from spacemissionstudio.idm import power
from spacemissionstudio.idm.shapes import ShapeGeometry
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import DEFAULT_PANEL_EFFICIENCY, PowerConfig, import_status

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_FULL_ATTITUDE = _TEMPLATES / "06_attitude_pointing_basic.json"  # one spacecraft, sat-1, no power budget
_ORBIT_ONLY = _TEMPLATES / "22_starter_first_leo_satellite.json"


def _model(tmp_path, text=None) -> Path:
    return write_idm(tmp_path / "powersat.idm", text if text is not None else model_xml("powersat"))


def _plan(tmp_path, text=None):
    return idm_import.plan(idm.load(_model(tmp_path, text)))


def _scenario(tmp_path, source=_FULL_ATTITUDE) -> Path:
    path = tmp_path / "scenario.json"
    shutil.copyfile(source, path)
    return path


def _power_warnings(scenario) -> list[str]:
    return [str(w) for w in scenario_warnings(scenario) if getattr(w, "rule_id", "") == "import.power_defaults"]


def test_each_system_mode_sums_the_power_its_mappings_give(tmp_path):
    """Cruise through its element mode, Downlink through the units' own
    mappings (a power mode, or a custom power); a unit with power modes
    that a system mode does not map is reported, at 0 W; the duty-cycle
    average weighs the totals."""
    modes = {m.mode.name: m for m in _plan(tmp_path).power.modes}
    assert list(modes) == ["Cruise", "Downlink"]
    cruise, downlink = modes["Cruise"], modes["Downlink"]
    assert cruise.mode.duty_cycle == pytest.approx(0.8)
    assert cruise.units == [("Star tracker head ST200", 1.5, "On"), ("Reaction Wheel X", 3.0, "Idle"),
                            ("Gyro unit", 6.0, "On")]
    assert cruise.total_w == pytest.approx(10.5) and cruise.unstated == []
    assert downlink.units == [("Reaction Wheel X", 4.5, "custom"), ("Gyro unit", 0.0, "Off")]
    assert downlink.total_w == pytest.approx(4.5) and downlink.unstated == ["Star tracker head ST200"]
    assert _plan(tmp_path).power.average_w == pytest.approx(0.8 * 10.5 + 0.2 * 4.5)


def test_no_average_unless_the_duty_cycles_add_up_to_one(tmp_path):
    """Duty cycles adding up to 0.9: the share of the lifetime the model
    does not place is unknown, so there is no average, and asking for it
    says why."""
    plan = _plan(tmp_path, model_xml("powersat").replace("<dutyCycle>0,2</dutyCycle>", "<dutyCycle>0,1</dutyCycle>"))
    assert plan.power.average_w is None
    assert "no duty-cycle average" in "\n".join(plan.summary.lines())
    with pytest.raises(idm.IdmError, match="do not add up to one"):
        idm_import.power_values(plan, idm_import.PowerChoice("average"))


def test_the_panel_is_the_flat_face_of_the_solar_array(tmp_path):
    """The wing's 1.2 m x 0.02 m x 0.8 m box: a 0.96 m^2 face whose normal
    line is the body y axis; the summary lists it."""
    plan = _plan(tmp_path)
    [panel] = plan.power.panels
    assert (panel.equipment, panel.area_m2, panel.normal_b) == ("Solar array wing", pytest.approx(0.96),
                                                                [0.0, 1.0, 0.0])
    assert "solar array panels: 1, 0.96 m^2 in all; normal line [0.0, 1.0, 0.0]" in "\n".join(plan.summary.lines())


def test_only_flat_shapes_are_panels_and_one_line_takes_both_senses():
    """A cube is no panel, a box thin on one side is; a rectangle surface's
    normal is its plane's; panels facing either way along one line are one
    group, the largest group first."""
    cube = ShapeGeometry("Box", "box", True, dims={"x": 1.0, "y": 1.0, "z": 1.0})
    thin = ShapeGeometry("Box", "box", True, dims={"x": 2.0, "y": 1.0, "z": 0.05})
    assert power._flat_face(cube, np.eye(4)) is None
    area, normal = power._flat_face(thin, np.eye(4))
    assert area == pytest.approx(2.0) and list(normal) == [0.0, 0.0, 1.0]
    panels = [power.Panel("a", "A", 1.0, [0.0, 0.0, 1.0]), power.Panel("b", "B", 0.5, [1.0, 0.0, 0.0]),
              power.Panel("c", "C", 1.0, [0.0, 0.0, -1.0])]
    groups = power.panel_groups(panels)
    assert [(g[1], [p.source_id for p in g[2]]) for g in groups] == [(2.0, ["a", "c"]), (0.5, ["b"])]


def test_the_import_makes_a_power_budget_and_says_what_it_does_not_know(tmp_path):
    """No power budget: setting the panels makes one, with the bus load of
    a system mode, the panel normal on the side chosen and the editor's
    efficiency and battery, recorded (target "power"); the pre-run checks
    warn until the efficiency and battery are set."""
    scenario = load_scenario(_scenario(tmp_path))
    plan = _plan(tmp_path)
    values = idm_import.apply_power(scenario, "sat-1", plan, idm_import.PowerChoice("Cruise", True, -1), "me",
                                    plan.summary)
    budget = scenario.spacecraft[0].power
    assert (budget.bus_idle_power_w, budget.panel_area_m2, budget.panel_normal_b) == (
        pytest.approx(10.5), pytest.approx(0.96), [0.0, -1.0, 0.0])
    assert budget.panel_efficiency == DEFAULT_PANEL_EFFICIENCY
    assert values["bus_idle_power_w"] == pytest.approx(10.5)
    record = next(r for r in scenario.imports if r.target == "power")
    assert record.format == "idm_cic" and record.author == "me"
    assert record.values["power.panel_normal_b[1]"] == -1.0 and "power.panel_efficiency" in record.values
    assert record.details["defaults"] == "panel_efficiency, battery_capacity_wh, battery_initial_soc"
    assert record.details["bus_load"].startswith("system mode Cruise: the power of 3 imported unit(s)")
    assert any(line.startswith("  power budget: made") for line in plan.summary.lines())
    scenario.validate()
    [warned] = _power_warnings(scenario)
    assert "panel efficiency, battery capacity wh, battery initial soc" in warned
    budget.panel_efficiency = 0.3  # [-] the cells' own value, set by the user
    assert _power_warnings(scenario) == []
    assert import_status(scenario, record)["changed"] == [("power.panel_efficiency", DEFAULT_PANEL_EFFICIENCY, 0.3)]


def test_an_existing_power_budget_keeps_what_was_not_chosen(tmp_path):
    """With a power budget: only the bus load is set (the duty-cycle
    average here); the panels, efficiency and battery stay, and nothing
    is warned."""
    scenario = load_scenario(_scenario(tmp_path))
    scenario.spacecraft[0].power = PowerConfig(panel_area_m2=2.0, panel_efficiency=0.31,  # [m^2], [-]
                                               battery_capacity_wh=40.0)  # [W*hr]
    plan = _plan(tmp_path)
    assert idm_import.apply_power(scenario, "sat-1", plan, idm_import.PowerChoice("average")) == {
        "bus_idle_power_w": pytest.approx(9.3)}
    budget = scenario.spacecraft[0].power
    assert (budget.panel_area_m2, budget.panel_efficiency, budget.battery_capacity_wh) == (2.0, 0.31, 40.0)
    record = next(r for r in scenario.imports if r.target == "power")
    assert list(record.values) == ["power.bus_idle_power_w"] and "defaults" not in record.details
    assert _power_warnings(scenario) == []


def test_a_bus_load_alone_needs_a_power_budget(tmp_path):
    """No power budget and no panels chosen: nothing is set, and the
    summary says why."""
    scenario = load_scenario(_scenario(tmp_path))
    plan = _plan(tmp_path)
    assert idm_import.apply_power(scenario, "sat-1", plan, idm_import.PowerChoice("Cruise"), "", plan.summary) == {}
    assert scenario.spacecraft[0].power is None and not any(r.target == "power" for r in scenario.imports)
    assert "a new one needs the panel area" in plan.summary.power_set[0]


def test_what_the_file_does_not_give_is_refused(tmp_path):
    """An unknown system mode, or panels from a model without a flat solar
    array: an error naming what is there."""
    plan = _plan(tmp_path)
    with pytest.raises(idm.IdmError, match="no system mode 'Eclipse'.*'Cruise', 'Downlink'"):
        idm_import.power_values(plan, idm_import.PowerChoice("Eclipse"))
    devices_only = idm_import.plan(idm.load(write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))))
    assert devices_only.power.modes == [] and devices_only.power.panels == []
    with pytest.raises(idm.IdmError, match="no flat solar array panel"):
        idm_import.power_values(devices_only, idm_import.PowerChoice(panels=True))


def test_the_power_record_round_trips_through_the_scenario_file(tmp_path):
    """The record (target "power") is written and read back as it was."""
    path = _scenario(tmp_path)
    scenario = load_scenario(path)
    idm_import.apply_power(scenario, "sat-1", _plan(tmp_path), idm_import.PowerChoice("Downlink", True))
    scenario.save(path)
    again = load_scenario(path)
    assert [dataclasses.asdict(r) for r in again.imports if r.target == "power"] == \
        [dataclasses.asdict(r) for r in scenario.imports if r.target == "power"]
    assert again.spacecraft[0].power.bus_idle_power_w == pytest.approx(4.5)


def test_the_cli_sets_the_power_budget(tmp_path, capsys):
    """``idm-import --bus-load average --solar-panels +``: the budget is
    made and the summary says so; an unknown mode stops before anything is
    written; an orbit-only scenario sets nothing and says why."""
    model, path = _model(tmp_path), _scenario(tmp_path)
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--bus-load", "average",
                     "--solar-panels", "+"]) == 0
    out = capsys.readouterr().out
    assert "power budget: bus load 9.3 W (duty-cycle average of 2 system modes" in out
    budget = load_scenario(path).spacecraft[0].power
    assert budget.panel_normal_b == [0.0, 1.0, 0.0] and budget.bus_idle_power_w == pytest.approx(9.3)
    before = path.read_bytes()
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--bus-load", "Eclipse"]) == 1
    assert "no system mode 'Eclipse'" in capsys.readouterr().err
    assert path.read_bytes() == before
    orbit = _scenario(tmp_path, _ORBIT_ONLY)
    name = load_scenario(orbit).spacecraft[0].name
    assert cli.main(["idm-import", str(model), str(orbit), "--spacecraft", name, "--solar-panels", "-"]) == 0
    assert "runs orbit only, which simulates no power budget" in capsys.readouterr().out
    assert load_scenario(orbit).spacecraft[0].power is None


def test_idm_info_lists_the_system_modes_and_panels(tmp_path, capsys):
    """``idm-info``: each system mode's power, the average and the panels."""
    assert cli.main(["idm-info", str(_model(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "system modes (power of the imported units): Cruise 10.5 W (duty cycle 0.8); Downlink 4.5 W" in out
    assert "duty-cycle average 9.3 W" in out and "solar array panels: 1, 0.96 m^2" in out
