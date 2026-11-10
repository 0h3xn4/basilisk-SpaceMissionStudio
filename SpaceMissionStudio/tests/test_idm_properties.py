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
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#

"""Device and battery values from the properties a team keeps in an
IDM-CIC model (``spacemissionstudio.idm.properties``, ``idm_properties``,
``idm-import --property-map/--battery``). The fixture
``tests/data/idm/powersat`` is synthetic (made-up names and values):
"Reaction Wheel X" has "Max torque" 15 and "Wheel inertia" 0,0021 (no
units) and "Speed range" 6 typed as a distance; "Roue Y" has "Max torque"
15 and an empty "Wheel inertia"; the gyro has "ARW" 0,005; the sun sensor
"Field of view" 120 typed as an angle; the battery an additional property
"Capacity" 85."""

import math
import shutil
from pathlib import Path

import pytest
from idm_fixtures import model_xml, write_idm

from spacemissionstudio import cli, idm, idm_devices, idm_import, idm_properties
from spacemissionstudio.engine.scenario_checks import scenario_warnings
from spacemissionstudio.idm.properties import equipment_properties
from spacemissionstudio.idm_properties import Mapping, parse_mapping
from spacemissionstudio.schema import load_scenario

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_FULL_ATTITUDE = _TEMPLATES / "06_attitude_pointing_basic.json"  # one spacecraft, sat-1, no devices

_WHEEL_MAP = [Mapping("Max torque", "reaction_wheel.u_max", "mN*m"),
              Mapping("Wheel inertia", "reaction_wheel.Js", "kg*m^2")]


def _model(tmp_path) -> Path:
    return write_idm(tmp_path / "powersat.idm", model_xml("powersat"))


def _plan(tmp_path, mappings=()):
    plan = idm_import.plan(idm.load(_model(tmp_path)))
    idm_import.set_mappings(plan, mappings)
    return plan


def _scenario(tmp_path) -> Path:
    path = tmp_path / "scenario.json"
    shutil.copyfile(_FULL_ATTITUDE, path)
    return path


def _found(plan) -> dict:
    return {f.equipment: f for f in plan.devices}


def test_the_reader_gives_own_and_additional_properties(tmp_path):
    """An equipment's own properties and its additional property values
    (named and typed by their definition), with decimal commas read and an
    empty value kept as none."""
    model = idm.load(_model(tmp_path))
    wheel = equipment_properties(model, "el.1_ss.AOCS_eq.5")
    assert [(p.name, p.value_type, p.number) for p in wheel] == [
        ("Max torque", "DecimalWithoutUnit", 15.0), ("Wheel inertia", "DecimalWithoutUnit", 0.0021),
        ("Speed range", "Distance", 6.0)]
    [capacity] = equipment_properties(model, "el.1_ss.PWR_eq.12")
    assert (capacity.name, capacity.value_type, capacity.number) == ("Capacity", "DecimalWithoutUnit", 85.0)
    empty = equipment_properties(model, "el.1_ss.AOCS_eq.6")[1]
    assert (empty.name, empty.text, empty.number) == ("Wheel inertia", None, None)


def test_a_mapping_is_written_and_read_back_and_checked():
    """The command line's form round-trips through the record's text; an
    unknown value or unit, a property mapped twice, two properties to one
    value, and a wheel's inertia and momentum both are refused."""
    mapping = parse_mapping("Max torque=reaction_wheel.u_max[mN*m]")
    assert mapping == Mapping("Max torque", "reaction_wheel.u_max", "mN*m")
    assert idm_properties.parse_mappings_text(idm_properties.mapping_text(_WHEEL_MAP)) == _WHEEL_MAP
    with pytest.raises(ValueError, match="not 'kN\\*m'"):
        parse_mapping("Max torque=reaction_wheel.u_max[kN*m]")
    with pytest.raises(ValueError, match="no value 'wheel.torque'"):
        parse_mapping("Max torque=wheel.torque[N*m]")
    with pytest.raises(ValueError, match="write a mapping as"):
        parse_mapping("Max torque")
    with pytest.raises(ValueError, match="mapped twice"):
        idm_properties.check_mappings([_WHEEL_MAP[0], Mapping("max  TORQUE", "reaction_wheel.Omega_max", "RPM")])
    with pytest.raises(ValueError, match="two properties are mapped to reaction_wheel.u_max"):
        idm_properties.check_mappings([_WHEEL_MAP[0], Mapping("Torque", "reaction_wheel.u_max", "N*m")])
    with pytest.raises(ValueError, match="inertia or its maximum momentum, not both"):
        idm_properties.check_mappings([_WHEEL_MAP[1], Mapping("H", "reaction_wheel.maxMomentum", "N*m*s")])


def test_a_unit_is_offered_only_when_the_type_has_the_value_s_dimension():
    """An angle for a field of view: degrees; a "distance" for a wheel
    speed, or an untyped number: none (the user says)."""
    targets = idm_properties.TARGETS
    assert idm_properties.suggested_unit("Angle", targets["coarse_sun_sensor.fov_deg"]) == "deg"
    assert idm_properties.suggested_unit("Distance", targets["reaction_wheel.Omega_max"]) == ""
    assert idm_properties.suggested_unit("DecimalWithoutUnit", targets["reaction_wheel.u_max"]) == ""


def test_mapped_values_are_converted_to_the_parameter_s_unit(tmp_path):
    """15 mN*m is 0.015 N*m; 0.005 deg/s is 8.73e-5 rad/s; 120 deg stays;
    an empty property gives nothing and says why."""
    mappings = _WHEEL_MAP + [Mapping("ARW", "imu.gyro_noise_rad_s", "deg/s"),
                             Mapping("Field of view", "coarse_sun_sensor.fov_deg", "deg")]
    found = _found(_plan(tmp_path, mappings))
    wheel, _ = idm_devices.finding_values(found["Reaction Wheel X"], mappings)
    assert {v.target.param: v.value for v in wheel} == {"u_max": pytest.approx(0.015), "Js": pytest.approx(0.0021)}
    [gyro], _ = idm_devices.finding_values(found["Gyro unit"], mappings)
    assert gyro.value == pytest.approx(0.005 * math.pi / 180.0)
    [fov], _ = idm_devices.finding_values(found["Coarse sun sensor +X"], mappings)
    assert fov.value == 120.0
    values, problems = idm_devices.finding_values(found["Roue Y"], mappings)
    assert [v.target.param for v in values] == ["u_max"] and problems == ["Wheel inertia: empty, not a number"]


def test_a_wheel_the_properties_complete_is_added_without_a_product(tmp_path):
    """With torque and inertia mapped, "Reaction Wheel X" is added by
    default with those values (no Basilisk default warning); "Roue Y",
    whose inertia is empty, is not, and says what it needs."""
    scenario = load_scenario(_scenario(tmp_path))
    plan = _plan(tmp_path, _WHEEL_MAP)
    choices = idm_devices.default_choices(plan.devices, plan.mappings)
    added = {f.equipment for f, c in zip(plan.devices, choices) if c.add}
    assert "Reaction Wheel X" in added and "Roue Y" not in added
    result = idm_import.add_devices(scenario, "sat-1", plan, choices)
    [wheel] = [a for a in scenario.spacecraft[0].actuators if a.kind == "reaction_wheel"]
    assert (wheel.params["u_max"], wheel.params["Js"]) == (pytest.approx(0.015), pytest.approx(0.0021))
    assert "maxMomentum" not in wheel.params
    assert wheel.params["gsHat_B"] == pytest.approx(_found(plan)["Reaction Wheel X"].axis("+z"))
    detail = next(r for r in scenario.imports if r.target == "devices").details["actuators[Reaction Wheel X]"]
    assert detail.startswith("properties: Basilisk's defaults for the rest; values from properties: "
                             "Max torque 15 mN*m -> u_max 0.015 N*m")
    assert any(name == "Roue Y" and "map the properties that give them" in why for name, why in result.skipped)
    scenario.validate()
    warned = [str(w) for w in scenario_warnings(scenario) if getattr(w, "rule_id", "") == "import.device_defaults"]
    assert not any("Reaction Wheel X" in w for w in warned)


def test_a_mapped_momentum_replaces_a_product_s_inertia(tmp_path):
    """A catalog wheel takes the mapped maximum momentum instead of its own
    inertia: Basilisk's wheel factory takes one or the other."""
    mappings = [Mapping("Max torque", "reaction_wheel.u_max", "mN*m"),
                Mapping("Wheel inertia", "reaction_wheel.maxMomentum", "N*m*s")]
    plan = _plan(tmp_path, mappings)
    finding = _found(plan)["Reaction Wheel X"]
    product = idm_devices.product_names("reaction_wheel")[0]
    choice = idm_devices.DeviceChoice(True, "reaction_wheel", "+z", product)
    [wheel] = idm_devices.build_devices([finding], [choice], set(), mappings).actuators
    assert "Js" not in wheel.params and wheel.params["maxMomentum"] == pytest.approx(0.0021)
    assert wheel.params["u_max"] == pytest.approx(0.015)
    assert wheel.params["Omega_max"] == idm_devices.product_by_name("reaction_wheel", product).params["Omega_max"]


def test_the_battery_capacity_comes_from_the_mapped_property(tmp_path):
    """The battery's additional property "Capacity", mapped in W*h, sets
    the power budget's capacity; a budget the import makes with it lists
    only the rest as the editor's values."""
    scenario = load_scenario(_scenario(tmp_path))
    plan = _plan(tmp_path, [Mapping("Capacity", "battery.capacity_wh", "W*h")])
    assert idm_import.battery_capacity(plan)[0] == pytest.approx(85.0)
    idm_import.apply_power(scenario, "sat-1", plan, idm_import.PowerChoice(panels=True, battery=True))
    power = scenario.spacecraft[0].power
    assert power.battery_capacity_wh == pytest.approx(85.0)
    record = next(r for r in scenario.imports if r.target == "power")
    assert record.details["defaults"] == "panel_efficiency, battery_initial_soc"
    assert record.details["battery"].startswith("1 battery unit(s), added up: Battery pack: Capacity 85 W*h")
    with pytest.raises(idm.IdmError, match="map the batteries' capacity property"):
        idm_import.power_values(_plan(tmp_path), idm_import.PowerChoice(battery=True))


def test_the_cli_maps_properties_and_reuses_the_mapping(tmp_path, capsys):
    """``--property-map`` adds the wheel and sets the battery; the mapping
    is kept in the model record and used again without the option;
    ``--property-map none`` drops it; a bad mapping stops before anything
    is written."""
    model, path = _model(tmp_path), _scenario(tmp_path)
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--devices",
                     "--property-map", "Max torque=reaction_wheel.u_max[mN*m]",
                     "--property-map", "Wheel inertia=reaction_wheel.Js[kg*m^2]",
                     "--property-map", "Capacity=battery.capacity_wh[W*h]",
                     "--solar-panels", "+", "--battery"]) == 0
    scenario = load_scenario(path)
    assert [a.name for a in scenario.spacecraft[0].actuators] == ["Reaction Wheel X"]
    assert scenario.spacecraft[0].power.battery_capacity_wh == pytest.approx(85.0)
    model_record = next(r for r in scenario.imports if r.target == "model")
    assert model_record.details["property_map"] == ("Max torque=reaction_wheel.u_max[mN*m]; "
                                                    "Wheel inertia=reaction_wheel.Js[kg*m^2]; "
                                                    "Capacity=battery.capacity_wh[W*h]")
    capsys.readouterr()
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1"]) == 0
    again = next(r for r in load_scenario(path).imports if r.target == "model")
    assert again.details["property_map"] == model_record.details["property_map"]
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--property-map", "none"]) == 0
    assert "property_map" not in next(r for r in load_scenario(path).imports if r.target == "model").details
    before = path.read_bytes()
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1",
                     "--property-map", "Max torque=reaction_wheel.u_max[furlongs]"]) == 1
    assert "not 'furlongs'" in capsys.readouterr().err and path.read_bytes() == before


def test_idm_info_lists_the_properties_and_what_they_can_give(tmp_path, capsys):
    """``idm-info``: each property name on the devices found, its type and
    values, and the values a property can be mapped to with their units."""
    assert cli.main(["idm-info", str(_model(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "Max torque (DecimalWithoutUnit) on Reaction wheel: 15" in out
    assert "Capacity (DecimalWithoutUnit) on Battery: 85" in out
    assert "reaction_wheel.u_max [N*m, mN*m]" in out and "battery.capacity_wh [W*h, kW*h]" in out
