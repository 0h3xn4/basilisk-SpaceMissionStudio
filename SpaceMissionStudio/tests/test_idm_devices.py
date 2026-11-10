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

"""The sensors and actuators of an IDM-CIC model, found by name
(``spacemissionstudio.idm_devices``, ``idm_import.add_devices``,
``idm-import --devices``). The fixture ``tests/data/idm/devicesat`` is
synthetic: made-up names, masses and poses, each equipment a manual-mass
unit placed by its instance (rotations Rx_Ry_Rz in degrees, IDM-01)."""

import shutil
from pathlib import Path

import pytest
from idm_fixtures import model_xml, write_idm

from spacemissionstudio import cli, idm, idm_devices, idm_import
from spacemissionstudio.engine.scenario_checks import scenario_warnings
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import SUPPORTED_ACTUATOR_KINDS, SUPPORTED_SENSOR_KINDS

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_FULL_ATTITUDE = _TEMPLATES / "06_attitude_pointing_basic.json"  # one spacecraft, sat-1, no devices
_ORBIT_ONLY = _TEMPLATES / "22_starter_first_leo_satellite.json"


def _plan(tmp_path):
    return idm_import.plan(idm.load(write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))))


def _scenario(tmp_path, source=_FULL_ATTITUDE) -> Path:
    path = tmp_path / "scenario.json"
    shutil.copyfile(source, path)
    return path


def _found(plan) -> dict:
    return {f.equipment: f for f in plan.devices}


@pytest.mark.parametrize("name,subsystem,kind", [
    ("Star tracker optical head", "AOCS", "star_tracker"),
    ("Senseur stellaire tête 1", "SCAO", "star_tracker"),
    ("Star tracker electronics unit", "AOCS", ""),  # the electronics box, not the sensor
    ("Inertia wheel 2", "AOCS", "reaction_wheel"),
    ("Roue de réaction 3", "SCAO", "reaction_wheel"),
    ("Wheel bracket", "Structure", ""),
    ("Wheel support", "AOCS", ""),
    ("Magneto torquer Y", "AOCS", "magnetic_torque_rod"),
    ("Magnétocoupleur Z", "SCAO", "magnetic_torque_rod"),
    ("Magnétomètre 2", "SCAO", "magnetometer"),
    ("Sun sensor -Y", "AOCS", "coarse_sun_sensor"),
    ("Gyro unit", "AOCS", "imu"),
    ("Thruster 4", "Propulsion", "thruster"),
    ("Propulseur 2", "Propulsion", "thruster"),
    ("Solar array wing", "Power", "solar_array"),
    ("Panneau solaire gauche", "Énergie", "solar_array"),
    ("Solar array drive mechanism", "Power", ""),
    ("Solar panel hinge", "Power", ""),
    ("Battery pack", "Power", "battery"),
    ("Battery heater", "Thermal control", ""),  # a thermal part of the battery
    ("On-board computer", "Data handling", ""),
])
def test_names_are_read_in_english_and_french(name, subsystem, kind):
    """A name names a device kind in English or French, accents ignored;
    a part of a device (electronics, support, mechanism, thermal cone) or
    equipment of the structure or thermal subsystem names none."""
    assert idm_devices.classify(name, subsystem)[0] == kind


def test_a_catalog_product_is_matched_by_its_name_only():
    """A product name in the equipment's name (whole words, not only generic
    ones) selects the product; a plain description selects none."""
    assert idm_devices.catalog_product("Star tracker head ST200", "star_tracker").product_name == "ST200"
    assert idm_devices.catalog_product("Wheel RSI 04-33-60A", "reaction_wheel").product_name == "RSI 04-33-60A"
    assert idm_devices.catalog_product("Fine sun sensor", "coarse_sun_sensor") is None
    assert idm_devices.catalog_product("Star tracker head", "star_tracker") is None
    assert idm_devices.catalog_product("ST2000 head", "star_tracker") is None  # not the word ST200


def test_the_devices_are_found_with_their_place_and_axes(tmp_path):
    """Each device of the fixture is found with its kind, mass, position
    and axes in the body frame: a wheel turned +90 deg about y spins along
    +x, one turned -90 deg about x along +y; the thruster turned 180 deg
    about x points -z. Look-alikes are not found."""
    found = _found(_plan(tmp_path))
    assert set(found) == {"Star tracker head ST200", "Reaction Wheel X", "Roue Y", "Magnétocoupleur Z MTQ800",
                          "Torque rod X", "Coarse sun sensor +X", "Gyro unit", "Magnetometer 1", "Battery pack",
                          "Solar array wing", "Thruster 1N"}
    tracker = found["Star tracker head ST200"]
    assert (tracker.kind, tracker.mass_kg, tracker.position_m) == ("star_tracker", 0.05, [0.3, 0.2, 0.5])  # [kg], [m]
    assert tracker.product == idm_devices.catalog_product("ST200", "star_tracker").display_name
    assert found["Reaction Wheel X"].axis() == pytest.approx([1.0, 0.0, 0.0])
    assert found["Roue Y"].axis() == pytest.approx([0.0, 1.0, 0.0])
    assert found["Coarse sun sensor +X"].axis() == pytest.approx([1.0, 0.0, 0.0])
    assert found["Thruster 1N"].axis() == pytest.approx([0.0, 0.0, -1.0])
    assert found["Roue Y"].axis("-z") == pytest.approx([0.0, -1.0, 0.0])
    assert found["Gyro unit"].axis("+x") == pytest.approx([1.0, 0.0, 0.0])
    assert "devices found by name (11)" in "\n".join(_plan(tmp_path).summary.lines())


def test_by_default_only_what_can_run_is_added(tmp_path):
    """By default: the sensors and a magnetorquer named after a catalog
    product are added; wheels and a magnetorquer without a product are
    not (Basilisk builds neither without values the file lacks), nor a
    thruster whose shapes show no plume cone; solar arrays and batteries
    are listed only, each with why."""
    plan = _plan(tmp_path)
    choices = dict(zip((f.equipment for f in plan.devices), idm_devices.default_choices(plan.devices)))
    added = {name for name, choice in choices.items() if choice.add}
    assert added == {"Star tracker head ST200", "Magnétocoupleur Z MTQ800", "Coarse sun sensor +X", "Gyro unit",
                     "Magnetometer 1"}
    assert "u_max" in idm_devices.why_not("reaction_wheel")
    assert idm_devices.why_not("reaction_wheel", "a product") == ""
    assert "no plume cone" in idm_devices.why_not("thruster", axis_known=False)  # Thruster 1N: no shapes
    assert idm_devices.why_not("thruster") == ""
    assert "the file has no capacity field" in idm_devices.why_not("battery")


def test_the_devices_built_carry_their_axis_mount_and_values(tmp_path):
    """A built device is named after its equipment (unique), takes its axis
    in the parameter its kind reads and in its mount, its product's values,
    and the record names where its values come from and its unit."""
    plan = _plan(tmp_path)
    findings = [f for f in plan.devices if f.equipment in ("Coarse sun sensor +X", "Star tracker head ST200", "Gyro unit")]
    choices = idm_devices.default_choices(findings)
    choices[1].axis = "-x"  # the sun sensor looks along -x of its frame instead
    result = idm_devices.build_devices(findings, choices, taken={"Gyro unit"})
    by_name = {d.name: d for d in result.sensors}
    assert set(by_name) == {"Star tracker head ST200", "Coarse sun sensor +X", "Gyro unit 2"}
    sun = by_name["Coarse sun sensor +X"]
    assert sun.params == {"nHat_B": pytest.approx([0.0, 0.0, 1.0])}  # -x of a frame turned +90 deg about y
    assert sun.mount.boresight == pytest.approx([0.0, 0.0, 1.0]) and sun.mount.position_m == [0.5, 0.0, 0.3]
    tracker = by_name["Star tracker head ST200"]
    product = idm_devices.catalog_product("ST200", "star_tracker")
    assert {k: v for k, v in tracker.params.items()} == product.params
    assert result.details["sensors[Star tracker head ST200]"].startswith(f"product: {product.display_name}")
    assert result.details["sensors[Gyro unit 2]"].startswith("no product: Basilisk's defaults")
    assert result.details["sensors[Gyro unit 2]"].endswith(f"unit {findings[2].source_id}")
    assert result.values["sensors[Coarse sun sensor +X].params.nHat_B[2]"] == 1.0
    with pytest.raises(ValueError, match="no star_tracker product"):
        idm_devices.build_devices(findings[:1], [idm_devices.DeviceChoice(True, "star_tracker", "+z", "Nope")], set())


def test_the_import_adds_the_devices_and_the_checks_name_those_without_values(tmp_path):
    """``idm-import --devices`` adds the sensors (the star tracker with its
    product's values), leaves out a magnetorquer the spacecraft cannot take
    (no magnetic momentum management), records the devices, and the
    pre-run checks name each device running on Basilisk's defaults; once
    its values are set, the warning goes. A second import adds nothing
    twice."""
    path = _scenario(tmp_path)
    model = write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--devices"]) == 0
    scenario = load_scenario(path)
    sat = scenario.spacecraft[0]
    assert [(d.kind, d.name) for d in sat.sensors] == [
        ("star_tracker", "Star tracker head ST200"), ("coarse_sun_sensor", "Coarse sun sensor +X"),
        ("imu", "Gyro unit"), ("magnetometer", "Magnetometer 1")]
    assert sat.actuators == []
    record = next(r for r in scenario.imports if r.target == "devices")
    assert record.format == "idm_cic" and set(record.details) == {f"sensors[{d.name}]" for d in sat.sensors}
    warned = [str(w) for w in scenario_warnings(scenario) if getattr(w, "rule_id", "") == "import.device_defaults"]
    assert len(warned) == 3 and not any("ST200" in w for w in warned)
    assert any("'Gyro unit'" in w and "Basilisk's defaults for a gyro / imu" in w for w in warned)
    sat.sensors[2].params["gyro_noise_rad_s"] = 1.0e-5  # [rad/s] the gyro's own value, set by the user
    warned = [str(w) for w in scenario_warnings(scenario) if getattr(w, "rule_id", "") == "import.device_defaults"]
    assert len(warned) == 2 and not any("'Gyro unit'" in w for w in warned)

    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--devices"]) == 0
    assert [d.name for d in load_scenario(path).spacecraft[0].sensors] == [d.name for d in sat.sensors]


def test_a_wheel_with_a_catalog_product_is_added(tmp_path):
    """A wheel the user gives a catalog product is added with the product's
    values and its spin axis from the model."""
    scenario = load_scenario(_scenario(tmp_path))
    plan = _plan(tmp_path)
    choices = [idm_devices.DeviceChoice(False, f.kind) for f in plan.devices]
    index = next(i for i, f in enumerate(plan.devices) if f.equipment == "Reaction Wheel X")
    product = idm_devices.product_names("reaction_wheel")[0]
    choices[index] = idm_devices.DeviceChoice(True, "reaction_wheel", "+z", product)
    result = idm_import.add_devices(scenario, "sat-1", plan, choices)
    [wheel] = scenario.spacecraft[0].actuators
    assert result.actuators == [wheel] and wheel.params["gsHat_B"] == pytest.approx([1.0, 0.0, 0.0])
    assert wheel.params["u_max"] == idm_devices.product_by_name("reaction_wheel", product).params["u_max"]
    scenario.validate()


def test_an_orbit_only_scenario_gets_no_devices(tmp_path):
    """An orbit-only run simulates no sensors or actuators: ``--devices``
    adds none and says so."""
    path = _scenario(tmp_path, _ORBIT_ONLY)
    name = load_scenario(path).spacecraft[0].name
    model = write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", name, "--devices"]) == 0
    sat = load_scenario(path).spacecraft[0]
    assert sat.sensors == [] and sat.actuators == []


def test_the_kinds_and_values_match_the_device_editor():
    """Every kind added is one the schema takes; each axis parameter and
    each value only a product gives is a required parameter of the device
    editor (``gui.sensor_actuator_editor``), so they cannot drift apart."""
    pytest.importorskip("PySide6")
    from spacemissionstudio.gui.sensor_actuator_editor import _KIND_PARAM_SPECS

    assert set(idm_devices.ADDABLE_KINDS) <= set(SUPPORTED_SENSOR_KINDS) | set(SUPPORTED_ACTUATOR_KINDS)
    for kind, key in idm_devices.AXIS_PARAMS.items():
        assert any(spec.key == key and spec.required for spec in _KIND_PARAM_SPECS[kind])
    required = {spec.key for spec in _KIND_PARAM_SPECS["magnetic_torque_rod"] if spec.required}
    assert set(idm_devices.REQUIRED_VALUES["magnetic_torque_rod"]) <= required
