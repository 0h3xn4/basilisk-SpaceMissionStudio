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

"""The origin of the body frame at the centre of gravity (decision IDM-31;
``model3d.origin``, ``idm_import.merge(origin=...)``, ``idm-import
--origin``). Moving the origin is a translation: every position from B
less the new origin's place, the rest unchanged. The centre of gravity
of the demosat fixture is worked out by hand in ``tests/test_idm_import.py``
(its ``_POINTS``; the model's computed one is 1.7 micrometres lower, the
plate's hole being a polygon, IDM-14); the devicesat fixture's devices check that what is
added after the import is measured from the new origin."""

import shutil
from pathlib import Path

import numpy as np
import pytest
from idm_fixtures import model_xml, write_idm
from test_idm_import import _POINTS

from spacemissionstudio import cli, idm, idm_import
from spacemissionstudio.model3d.origin import move_origin, shift_record_values
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import (
    ActuatorConfig, FacetConfig, FuelTankConfig, LauncherConfig, ModelMassPropertiesConfig, ModelPartConfig,
    MountConfig, MountedEquipmentConfig, OrbitIC, PartPoseConfig, RFLinkConfig, SensorConfig, SolarArrayConfig,
    SpacecraftConfig, SpacecraftModelConfig,
)

_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "spacemissionstudio" / "scenarios" / "two_body_validation.json"
_ATTITUDE = _ROOT / "spacemissionstudio" / "scenarios" / "templates" / "06_attitude_pointing_basic.json"
_HAND_COG = sum(m * np.asarray(r) for m, r in _POINTS.values()) / sum(m for m, _ in _POINTS.values())  # [m]


def _everything() -> SpacecraftConfig:
    """A spacecraft with a value in every position measured from B, and
    the directions and a part-frame mount that must not move."""
    model = SpacecraftModelConfig(
        parts=[ModelPartConfig(name="box", shape="box", position_b_m=[1.0, 2.0, 3.0], rotation_deg=[10.0, 0.0, 0.0])],
        equipment=[MountedEquipmentConfig(name="unit", kind="unit", mount=MountConfig(position_m=[0.5, 0.5, 0.5])),
                   MountedEquipmentConfig(name="on box", kind="unit",
                                          mount=MountConfig(part="box", position_m=[0.1, 0.0, 0.0]))],
        stowed=[PartPoseConfig(part="box", position_b_m=[0.0, 0.0, 1.0], rotation_deg=[0.0, 90.0, 0.0])],
        launcher=LauncherConfig(origin_b_m=[0.0, 0.0, -0.5], axis_b=[0.0, 0.0, 1.0]),
        mass_properties=ModelMassPropertiesConfig(mass_kg=10.0, center_of_mass_b_m=[0.2, 0.2, 0.2]))
    sc = SpacecraftConfig(name="sat", orbit=OrbitIC(type="keplerian"), model=model, center_of_mass_b_m=[0.3, 0.0, 0.0])
    sc.sensors = [SensorConfig(kind="coarse_sun_sensor", name="css", params={"nHat_B": [1.0, 0.0, 0.0]},
                               mount=MountConfig(position_m=[0.4, 0.0, 0.0], boresight=[1.0, 0.0, 0.0]))]
    sc.actuators = [ActuatorConfig(kind="thruster", name="thr", params={"r_B": [0.0, 0.0, -0.4],
                                                                      "tHat_B": [0.0, 0.0, 1.0]}),
                    ActuatorConfig(kind="reaction_wheel", name="rw", params={"rWB_B": [0.1, 0.1, 0.1],
                                                                           "gsHat_B": [0.0, 1.0, 0.0]})]
    sc.facets = [FacetConfig(name="f", area_m2=1.0, normal_b=[0.0, 0.0, 1.0], location_b=[0.0, 0.0, 0.6])]
    sc.fuel_tank = FuelTankConfig(propellant_mass_kg=1.0, max_propellant_mass_kg=2.0, tank_position_b_m=[0.0, 0.1, 0.0])
    sc.solar_arrays = [SolarArrayConfig(name="wing", mass_kg=1.0, span_m=1.0, width_m=0.5,
                                        hinge_position_b=[0.5, 0.0, 0.2], deploy_direction_b=[1.0, 0.0, 0.0],
                                        normal_b=[0.0, 0.0, 1.0], first_mode_hz=1.0, damping_ratio=0.01)]
    sc.rf_link = RFLinkConfig(tx_power_w=1.0, frequency_hz=2.2e9, data_rate_bps=1.0e6,
                              antenna_mount=MountConfig(position_m=[0.0, -0.2, 0.0]))
    sc.vizard_model_path = "cad.obj"
    sc.vizard_model_offset_m = [0.0, 0.0, 0.0]
    return sc


def test_moving_the_origin_moves_every_position_from_b_and_nothing_else():
    """Each position less d = (0.1, -0.2, 0.3); the directions, the
    rotations, a mount in a part's frame and the masses as they were."""
    sc = _everything()
    d = np.array([0.1, -0.2, 0.3])  # [m]
    moved = move_origin(sc, d)

    def less(p):
        return pytest.approx(list(np.asarray(p) - d))

    m = sc.model
    assert m.parts[0].position_b_m == less([1.0, 2.0, 3.0]) and m.parts[0].rotation_deg == [10.0, 0.0, 0.0]
    assert m.equipment[0].mount.position_m == less([0.5, 0.5, 0.5])
    assert m.equipment[1].mount.position_m == [0.1, 0.0, 0.0]  # in the box's frame: it moves with the box
    assert m.stowed[0].position_b_m == less([0.0, 0.0, 1.0]) and m.stowed[0].rotation_deg == [0.0, 90.0, 0.0]
    assert m.launcher.origin_b_m == less([0.0, 0.0, -0.5]) and m.launcher.axis_b == [0.0, 0.0, 1.0]
    assert m.mass_properties.center_of_mass_b_m == less([0.2, 0.2, 0.2]) and m.mass_properties.mass_kg == 10.0
    assert sc.center_of_mass_b_m == less([0.3, 0.0, 0.0])
    css, = sc.sensors
    assert css.mount.position_m == less([0.4, 0.0, 0.0]) and css.mount.boresight == [1.0, 0.0, 0.0]
    assert css.params["nHat_B"] == [1.0, 0.0, 0.0]
    thruster, wheel = sc.actuators
    assert thruster.params["r_B"] == less([0.0, 0.0, -0.4]) and thruster.params["tHat_B"] == [0.0, 0.0, 1.0]
    assert wheel.params["rWB_B"] == less([0.1, 0.1, 0.1]) and wheel.params["gsHat_B"] == [0.0, 1.0, 0.0]
    assert sc.facets[0].location_b == less([0.0, 0.0, 0.6]) and sc.facets[0].normal_b == [0.0, 0.0, 1.0]
    assert sc.fuel_tank.tank_position_b_m == less([0.0, 0.1, 0.0])
    assert sc.solar_arrays[0].hinge_position_b == less([0.5, 0.0, 0.2])
    assert sc.solar_arrays[0].deploy_direction_b == [1.0, 0.0, 0.0]
    assert sc.rf_link.antenna_mount.position_m == less([0.0, -0.2, 0.0])
    assert sc.vizard_model_offset_m == less([0.0, 0.0, 0.0])
    assert moved == ["1 part(s)", "1 mounted equipment", "1 stowed pose(s)", "the launcher's separation plane",
                     "the model's typed centre of mass", "3 sensor(s) and actuator(s)", "the RF antenna",
                     "1 facet(s)", "the fuel tank", "1 solar array hinge(s)", "the Vizard model's offset"]


def test_a_record_s_positions_move_and_its_other_values_do_not():
    values = {"model.parts[a].position_b_m[0]": 1.0, "model.parts[a].position_b_m[2]": 3.0,
              "model.parts[a].rotation_deg[0]": 1.0, "model.equipment[b].mount.position_m[1]": 0.5,
              "model.stowed[a].position_b_m[1]": 0.0, "sensors[s].mount.position_m[0]": 0.4,
              "sensors[s].mount.boresight[0]": 1.0, "sensors[s].params.nHat_B[0]": 1.0,
              "actuators[t].params.r_B[2]": -0.4, "sensors[s].kind": "imu"}
    shifted = shift_record_values(values, [0.1, 0.5, 1.0])
    assert shifted == {"model.parts[a].position_b_m[0]": pytest.approx(0.9),
                       "model.parts[a].position_b_m[2]": pytest.approx(2.0), "model.parts[a].rotation_deg[0]": 1.0,
                       "model.equipment[b].mount.position_m[1]": pytest.approx(0.0),
                       "model.stowed[a].position_b_m[1]": pytest.approx(-0.5),
                       "sensors[s].mount.position_m[0]": pytest.approx(0.3), "sensors[s].mount.boresight[0]": 1.0,
                       "sensors[s].params.nHat_B[0]": 1.0, "actuators[t].params.r_B[2]": pytest.approx(-1.4),
                       "sensors[s].kind": "imu"}


def _scenario(tmp_path, source=_SOURCE) -> Path:
    path = tmp_path / "scenario.json"
    shutil.copyfile(source, path)
    return path


def test_the_origin_at_the_centre_of_gravity(tmp_path):
    """demosat with the origin at its centre of gravity: every part moved
    by the centre of gravity (the hand-worked one, to 2 micrometres; the
    computed one, to the micrometre), which is now within a micrometre of
    B; the mass, inertia and directions as with the element's frame; the
    record keeps where the origin is."""
    path = _scenario(tmp_path)
    plain, centred = load_scenario(path), load_scenario(path)
    idm_import.merge(plain, "sat-1", idm_import.plan(idm.load(write_idm(tmp_path / "a.idm"))), path)
    summary = idm_import.merge(centred, "sat-1", idm_import.plan(idm.load(write_idm(tmp_path / "b.idm"))), path,
                               origin="cog")
    a, b = plain.spacecraft[0], centred.spacecraft[0]
    offset = np.round(a.center_of_mass_b_m, 6)
    assert np.allclose(offset, _HAND_COG, rtol=0.0, atol=2.0e-6)
    assert summary.origin == "cog" and summary.origin_m == pytest.approx(list(offset), abs=1e-12)
    assert summary.origin_moved_m == pytest.approx(list(offset), abs=1e-12)
    assert np.allclose(b.center_of_mass_b_m, 0.0, rtol=0.0, atol=1e-6)
    assert b.dry_mass_kg == pytest.approx(a.dry_mass_kg) and np.allclose(b.inertia_kg_m2, a.inertia_kg_m2)
    before = {p.source_id: p for p in a.model.parts}
    for part in b.model.parts:
        assert np.allclose(np.asarray(before[part.source_id].position_b_m) - offset, part.position_b_m,
                           rtol=0.0, atol=1e-9)
        assert part.rotation_deg == before[part.source_id].rotation_deg
    record = next(r for r in centred.imports if r.target == "model")
    assert record.details["origin"] == "cog"
    assert np.allclose([float(v) for v in record.details["origin_offset_m"].split(",")], offset, rtol=0.0, atol=1e-12)
    assert idm_import.recorded_origin(record) == ("cog", pytest.approx(list(offset)))
    assert any(line.startswith("  origin of the body frame: the centre of gravity, at [") for line in summary.lines())
    centred.validate()


def test_a_re_import_keeps_the_origin_and_can_put_it_back(tmp_path):
    """Imported again with no choice: the origin stays at the centre of
    gravity and nothing is updated; with "element": every position is as
    an import in the element's frame gives it, a hand-placed facet and
    the devices' record moving back with them."""
    path = _scenario(tmp_path)
    scenario, plain = load_scenario(path), load_scenario(path)
    model = idm.load(write_idm(tmp_path / "demosat.idm"))
    idm_import.merge(plain, "sat-1", idm_import.plan(model), path)
    idm_import.merge(scenario, "sat-1", idm_import.plan(model), path, origin="cog")
    sc = scenario.spacecraft[0]
    sc.facets = [FacetConfig(name="hand", area_m2=1.0, normal_b=[0.0, 0.0, 1.0], location_b=[0.0, 0.0, 0.0])]
    again = idm_import.merge(scenario, "sat-1", idm_import.plan(model), path)
    assert again.origin == "cog" and not again.updated and not again.kept and not again.origin_moved_m
    back = idm_import.merge(scenario, "sat-1", idm_import.plan(model), path, origin="element")
    assert back.origin == "element" and back.origin_m == [0.0, 0.0, 0.0] and not back.kept
    assert sc.facets[0].location_b == pytest.approx(list(np.round(plain.spacecraft[0].center_of_mass_b_m, 6)),
                                                    abs=1e-12)
    expected = {p.source_id: p.position_b_m for p in plain.spacecraft[0].model.parts}
    for part in sc.model.parts:
        assert np.allclose(part.position_b_m, expected[part.source_id], rtol=0.0, atol=1e-9)
    assert np.allclose(sc.center_of_mass_b_m, plain.spacecraft[0].center_of_mass_b_m, rtol=0.0, atol=1e-9)
    with pytest.raises(idm.IdmError, match="origin 'middle' must be one of"):
        idm_import.merge(scenario, "sat-1", idm_import.plan(model), path, origin="middle")


def test_devices_follow_the_origin_and_the_command_line_takes_it(tmp_path):
    """``idm-import --devices --origin cog``: the devices are placed from
    the centre of gravity (their element-frame place less the origin's);
    a later import in the element's frame moves them back, and their
    record with them, so a further ``--devices`` adds nothing twice."""
    path = _scenario(tmp_path, _ATTITUDE)
    (tmp_path / "ref").mkdir()
    reference = _scenario(tmp_path / "ref", _ATTITUDE)
    model_path = write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))
    assert cli.main(["idm-import", str(model_path), str(reference), "--spacecraft", "sat-1", "--devices"]) == 0
    assert cli.main(["idm-import", str(model_path), str(path), "--spacecraft", "sat-1", "--devices",
                     "--origin", "cog"]) == 0
    plain, centred = load_scenario(reference).spacecraft[0], load_scenario(path).spacecraft[0]
    record = next(r for r in load_scenario(path).imports if r.target == "model")
    offset = np.array([float(v) for v in record.details["origin_offset_m"].split(",")])
    assert np.allclose(offset, plain.center_of_mass_b_m, rtol=0.0, atol=1e-6) and np.linalg.norm(offset) > 0.01
    for a, b in zip(plain.sensors, centred.sensors, strict=True):
        assert np.allclose(np.asarray(a.mount.position_m) - offset, b.mount.position_m, rtol=0.0, atol=1e-9)
        assert a.mount.boresight == b.mount.boresight and a.params == b.params
    assert cli.main(["idm-import", str(model_path), str(path), "--spacecraft", "sat-1", "--devices",
                     "--origin", "element"]) == 0
    back = load_scenario(path)
    sensors = back.spacecraft[0].sensors
    assert [d.name for d in sensors] == [d.name for d in plain.sensors]
    for a, b in zip(plain.sensors, sensors, strict=True):
        assert np.allclose(a.mount.position_m, b.mount.position_m, rtol=0.0, atol=1e-9)
    devices_record = next(r for r in back.imports if r.target == "devices")
    for key, value in devices_record.values.items():
        if ".mount.position_m[" in key:
            name = key.split("[", 1)[1].split("]", 1)[0]
            k = int(key.rsplit("[", 1)[1][0])
            device = next(d for d in sensors if d.name == name)
            assert value == pytest.approx(device.mount.position_m[k], abs=1e-9)


def test_a_model_without_mass_keeps_its_origin(tmp_path):
    """No mass, no centre of gravity: the origin stays and the summary
    says why."""
    path = _scenario(tmp_path)
    scenario = load_scenario(path)
    plan = idm_import.plan(idm.load(write_idm(tmp_path / "demosat.idm")))
    for item in plan.parts + plan.equipment:
        item.config.mass_kg = 0.0
    summary = idm_import.merge(scenario, "sat-1", plan, path, origin="cog")
    assert not summary.origin_moved_m and any("no centre of gravity" in note for note in summary.notes)
