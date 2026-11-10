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

"""Thrusters found in an IDM-CIC model, added to the 3D model's equipment
(decision IDM-32): placed where their plume cone starts, thrusting
against the plume, with the plume's half-angle and the thrust of a
catalog product or a mapped property, for the design checks (plume
impingement, the thrust authority matrix).

The fixture ``tests/data/idm/axessat`` is synthetic (made-up names, sizes
and poses). Its "Thruster 2" is placed at (0, 0, -0.3) m turned 180 deg
about x, with a massless plume cone on the field-of-view layer: radius 0
at z = 0 and 0.1 m at z = 0.2 m of its shape frame. By hand: the plume
goes along Rx(180) z = -z of the body frame, so the thrust is +z; the
half-angle is atan(0.1 / 0.2); the plume starts at the apex."""

import copy
import math
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from idm_fixtures import model_xml, write_idm

from spacemissionstudio import cli, idm, idm_devices, idm_import
from spacemissionstudio.idm.properties import PropertyValue
from spacemissionstudio.idm_properties import Mapping
from spacemissionstudio.schema import load_scenario

_TEMPLATE = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" / \
    "06_attitude_pointing_basic.json"  # one spacecraft, sat-1, no devices

_HALF_ANGLE = math.degrees(math.atan(0.1 / 0.2))  # [deg] 26.5651
_PLUME_SHAPE = '''<Position fullId="el.1_ss.AOCS_eq.8_sh.1_pos">
<x>0</x>
<y>0</y>
<z>0</z>'''


def _xml(plume_z: float = 0.0) -> str:
    """The axessat model, its plume shape moved by ``plume_z`` [m] along
    the thruster's own z."""
    text = model_xml("axessat")
    assert text.count(_PLUME_SHAPE) == 1
    return text.replace(_PLUME_SHAPE, _PLUME_SHAPE.replace("<z>0</z>", f"<z>{plume_z:g}</z>".replace(".", ",")))


def _thruster(tmp_path, plume_z: float = 0.0):
    plan = idm_import.plan(idm.load(write_idm(tmp_path / "axessat.idm", _xml(plume_z))))
    return plan, next(f for f in plan.devices if f.equipment == "Thruster 2")


def _scenario(tmp_path) -> Path:
    path = tmp_path / "scenario.json"
    shutil.copyfile(_TEMPLATE, path)
    return path


def test_the_plume_cone_gives_the_thrust_direction_and_the_nozzle(tmp_path):
    """The thrust is against the plume (+z), the half-angle is the cone's,
    and the nozzle is the apex: with the plume shape moved 0.05 m along the
    thruster's z (body -z, the unit being turned 180 deg about x), the
    apex is at (0, 0, -0.35) m while the unit's centre of mass stays at
    (0, 0, -0.3) m."""
    _plan, thruster = _thruster(tmp_path, plume_z=0.05)
    assert thruster.kind == "thruster" and thruster.addable
    assert thruster.model_axis == pytest.approx([0.0, 0.0, 1.0])
    assert thruster.fov_deg / 2.0 == pytest.approx(_HALF_ANGLE, abs=1.0e-4)  # [deg] kept to 6 digits
    assert thruster.axis_origin_m == pytest.approx([0.0, 0.0, -0.35])  # [m]
    assert thruster.position_m == pytest.approx([0.0, 0.0, -0.3])  # [m]
    assert idm_devices.axis_text(thruster, "model") == (
        f"from the plume cone 'Plume', against the plume (plume half-angle {thruster.fov_deg / 2.0:g} deg)")


def test_a_thruster_is_added_by_default_only_with_a_plume_cone(tmp_path):
    """Thruster 2 (a plume cone) is added by default along the model's
    axis; devicesat's "Thruster 1N" (no shapes) is not, and says why."""
    plan, thruster = _thruster(tmp_path)
    [choice] = idm_devices.default_choices([thruster])
    assert (choice.add, choice.axis, choice.product) == (True, "model", "")
    other = idm_import.plan(idm.load(write_idm(tmp_path / "devicesat.idm", model_xml("devicesat"))))
    bare = next(f for f in other.devices if f.equipment == "Thruster 1N")
    [choice] = idm_devices.default_choices([bare])
    assert not choice.add
    result = idm_devices.build_devices([bare], [choice], set())
    assert result.skipped == [("Thruster 1N", idm_devices.why_not("thruster", axis_known=False))]
    assert "no plume cone" in result.skipped[0][1]


def test_the_thruster_is_built_as_model_equipment(tmp_path):
    """No product and no mapped thrust: a massless "Thruster 2 nozzle" at
    the plume's start with the plume's half-angle and no thrust; it is not
    a sensor or actuator, and the record keeps its values under
    ``model.equipment[NAME]``."""
    _plan, thruster = _thruster(tmp_path, plume_z=0.05)
    result = idm_devices.build_devices([thruster], idm_devices.default_choices([thruster]), set(),
                                       taken_equipment={"Thruster 2"})
    assert not result.sensors and not result.actuators
    [item] = result.equipment
    assert (item.name, item.kind, item.mass_kg, item.subsystem, item.source_id) == (
        "Thruster 2 nozzle", "thruster", 0.0, thruster.subsystem, "")
    assert item.mount.position_m == pytest.approx([0.0, 0.0, -0.35])  # [m]
    assert item.mount.boresight == pytest.approx([0.0, 0.0, 1.0])
    assert item.mount.plume_half_angle_deg == pytest.approx(_HALF_ANGLE, abs=1.0e-4)  # [deg]
    assert item.thrust_n is None
    detail = result.details["model.equipment[Thruster 2 nozzle]"]
    assert detail.startswith("no thrust: the authority matrix takes it per newton; axis from the plume cone")
    assert "; at the plume cone's start; from Thruster 2; unit " in detail
    assert result.values["model.equipment[Thruster 2 nozzle].mount.position_m[2]"] == pytest.approx(-0.35)
    assert result.values["model.equipment[Thruster 2 nozzle].kind"] == "thruster"
    assert "model.equipment[Thruster 2 nozzle].thrust_n" not in result.values
    assert idm_devices.recorded_units(replace(_record(), details=result.details)) == {thruster.source_id}


def _record():
    from spacemissionstudio.schema.scenario import ImportRecord

    return ImportRecord("sat-1", "devices", "idm_cic", "/x.idm", "0" * 64, {})


def test_an_axis_of_the_frame_puts_it_at_its_centre_of_mass(tmp_path):
    """An axis of the equipment frame chosen instead: the thruster sits at
    its unit's centre of mass, along that axis, with no plume half-angle
    (the model's cone is not the one chosen)."""
    _plan, thruster = _thruster(tmp_path, plume_z=0.05)
    choice = idm_devices.DeviceChoice(True, "thruster", "-z")
    [item] = idm_devices.build_devices([thruster], [choice], set()).equipment
    assert item.mount.position_m == pytest.approx([0.0, 0.0, -0.3])  # [m]
    assert item.mount.boresight == pytest.approx([0.0, 0.0, 1.0])  # -z of a frame turned 180 deg about x
    assert item.mount.plume_half_angle_deg is None and item.name == "Thruster 2 nozzle"


def test_the_thrust_comes_from_a_product_or_a_mapped_property(tmp_path):
    """A catalog product gives its ``MaxThrust``; a mapped property in mN
    goes over it."""
    _plan, thruster = _thruster(tmp_path)
    product = idm_devices.product_names("thruster")[0]
    choice = idm_devices.DeviceChoice(True, "thruster", "model", product)
    result = idm_devices.build_devices([thruster], [choice], set())
    expected = idm_devices.product_by_name("thruster", product).params["MaxThrust"]
    assert result.equipment[0].thrust_n == pytest.approx(expected)
    assert result.details["model.equipment[Thruster 2 nozzle]"].startswith(f"thrust from product: {product} (")
    assert result.values["model.equipment[Thruster 2 nozzle].thrust_n"] == pytest.approx(expected)

    mapped = replace(thruster, properties=(PropertyValue("Nominal thrust", "Real", "250", 250.0, "p.1"),))
    mappings = [Mapping("Nominal thrust", "thruster.MaxThrust", "mN")]
    result = idm_devices.build_devices([mapped], [choice], set(), mappings)
    assert result.equipment[0].thrust_n == pytest.approx(0.25)  # [N] 250 mN
    assert result.details["model.equipment[Thruster 2 nozzle]"].startswith(
        "thrust from properties: Nominal thrust 250 mN -> MaxThrust 0.25 N")


def test_a_spacecraft_without_a_model_cannot_take_a_thruster(tmp_path):
    """keep_fitting leaves out a thruster when the spacecraft has no 3D
    model to carry it, with the reason, even when the spacecraft is not
    valid as it is (then nothing else is tried); and one whose thrust is
    out of range for the model's validation."""
    scenario = load_scenario(_scenario(tmp_path))
    sat = scenario.spacecraft[0]
    assert sat.model is None
    _plan, thruster = _thruster(tmp_path)
    built = idm_devices.build_devices([thruster], idm_devices.default_choices([thruster]), set())
    kept = idm_devices.keep_fitting(sat, built)
    assert not kept.equipment and not kept.details
    [(name, why)] = kept.skipped
    assert name == "Thruster 2" and why == f"{idm_devices.CANNOT_TAKE}: it has no 3D model to carry it"

    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    sat.model = SpacecraftModelConfig(apply_facets=False, parts=[
        ModelPartConfig(name="bus", shape="box", mass_kg=100.0, dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0})])
    invalid = copy.deepcopy(sat)
    invalid.model = None
    invalid.dry_mass_kg = -1.0  # [kg] not valid as it is: nothing is tried, but the thruster still needs a model
    kept = idm_devices.keep_fitting(invalid, built)
    assert not kept.equipment and kept.skipped == [("Thruster 2", f"{idm_devices.CANNOT_TAKE}: it has no 3D model "
                                                                  "to carry it")]
    assert not any(k.startswith("model.") for k in kept.values) and not kept.details
    built.equipment[0].thrust_n = 2.0e5  # [N] above the model's limit
    kept = idm_devices.keep_fitting(sat, built)
    assert not kept.equipment and "thrust_n must be in (0, 1e5] N" in kept.skipped[0][1]


def test_the_import_adds_it_to_the_model_and_the_design_checks_use_it(tmp_path):
    """``idm-import --devices``: the thruster is on the model's equipment
    next to the unit's point mass, recorded, compared like with like (no
    device flagged as running on defaults), left as it is by a re-import,
    and the plume and authority checks take it. (The sensors added with no
    product are flagged as running on Basilisk's defaults; the thruster,
    which nothing simulates, is not.)"""
    from spacemissionstudio.analyses import thrusters
    from spacemissionstudio.engine.scenario_checks import scenario_warnings

    path = _scenario(tmp_path)
    model = write_idm(tmp_path / "axessat.idm", model_xml("axessat"))
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--devices"]) == 0
    scenario = load_scenario(path)
    sat = scenario.spacecraft[0]
    nozzles = [e for e in sat.model.equipment if e.kind == "thruster"]
    assert [e.name for e in nozzles] == ["Thruster 2 nozzle"]
    assert any(e.name == "Thruster 2" and e.kind == "unit" and e.mass_kg == pytest.approx(0.3)
               for e in sat.model.equipment)  # [kg] the model import's point mass
    record = next(r for r in scenario.imports if r.target == "devices")
    assert record.values["model.equipment[Thruster 2 nozzle].mount.boresight[2]"] == 1.0
    assert {k: v for k, v in idm_devices.device_import_values(sat).items() if k.startswith("model.")} == \
        {k: v for k, v in record.values.items() if k.startswith("model.")}
    assert not any("Thruster 2" in path for _sc, path, _kind in idm_devices.unset_devices(scenario))
    assert not any("Thruster 2" in str(w) for w in scenario_warnings(scenario))

    found, skipped = thrusters.plume_impingement(sat, samples=200, base_dir=tmp_path)
    [plume] = found
    assert plume.thruster == "Thruster 2 nozzle" and plume.half_angle_deg == pytest.approx(_HALF_ANGLE, abs=1e-4)
    assert not skipped
    authority = thrusters.thruster_authority(sat)
    [column] = authority.columns
    assert column.name == "Thruster 2 nozzle" and not column.thrust_known
    assert column.direction_b == pytest.approx([0.0, 0.0, 1.0])

    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--devices"]) == 0
    again = load_scenario(path).spacecraft[0]
    assert [e.name for e in again.model.equipment if e.kind == "thruster"] == ["Thruster 2 nozzle"]


def test_the_origin_at_the_centre_of_gravity_moves_the_thruster(tmp_path):
    """``--origin cog``: the thruster is placed from the moved origin, and
    its record with it."""
    plain = _scenario(tmp_path)
    (tmp_path / "cog").mkdir()
    centred = _scenario(tmp_path / "cog")
    model = write_idm(tmp_path / "axessat.idm", model_xml("axessat"))
    assert cli.main(["idm-import", str(model), str(plain), "--spacecraft", "sat-1", "--devices"]) == 0
    assert cli.main(["idm-import", str(model), str(centred), "--spacecraft", "sat-1", "--devices",
                     "--origin", "cog"]) == 0
    scenario = load_scenario(centred)
    offset = np.array([float(v) for v in next(r for r in scenario.imports if r.target == "model")
                       .details["origin_offset_m"].split(",")])  # [m]
    assert np.linalg.norm(offset) > 1.0e-3

    def nozzle(sc):
        return next(e for e in sc.model.equipment if e.kind == "thruster")

    a, b = nozzle(load_scenario(plain).spacecraft[0]), nozzle(scenario.spacecraft[0])
    assert np.allclose(np.asarray(a.mount.position_m) - offset, b.mount.position_m, rtol=0.0, atol=1e-9)
    record = next(r for r in scenario.imports if r.target == "devices")
    assert [record.values[f"model.equipment[{b.name}].mount.position_m[{k}]"] for k in range(3)] == \
        pytest.approx(b.mount.position_m, abs=1e-9)
