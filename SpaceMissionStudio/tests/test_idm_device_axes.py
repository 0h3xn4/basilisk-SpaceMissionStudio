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

"""A device's axis read from its equipment's shapes (decision IDM-30,
``idm_devices.model_axis``): a field-of-view cone gives a sensor's
boresight and field of view, a cylinder a wheel's spin axis or a
magnetorquer's dipole axis, and +z of the equipment frame is used when
the shapes show none. The fixture ``tests/data/idm/axessat`` is synthetic:
made-up names, sizes and poses, rotations Rx_Ry_Rz in degrees (IDM-01).
Each expected axis is worked out by hand below from those rotations."""

import math
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from idm_fixtures import model_xml, write_idm

from spacemissionstudio import cli, idm, idm_devices, idm_import
from spacemissionstudio.schema import load_scenario

_TEMPLATE = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" / \
    "06_attitude_pointing_basic.json"  # one spacecraft, sat-1, no devices

_SIN30, _COS30 = 0.5, math.sqrt(3.0) / 2.0  # [-]
_SIN20, _COS20 = math.sin(math.radians(20.0)), math.cos(math.radians(20.0))  # [-]


def _plan(tmp_path):
    return idm_import.plan(idm.load(write_idm(tmp_path / "axessat.idm", model_xml("axessat"))))


def _found(plan) -> dict:
    return {f.equipment: f for f in plan.devices}


def test_the_axes_are_read_from_the_shapes(tmp_path):
    """Each device's axis in the body frame, by hand:

    * the wheel placed with Rx 30 deg then Ry 20 deg: its cylinder's z,
      Rx(30) Ry(20) z = (sin 20, -sin 30 cos 20, cos 30 cos 20);
    * the wheel whose cylinder is turned Rx 90 deg in its equipment:
      Rx(90) z = -y; the rod's, turned Ry 90 deg: Ry(90) z = +x;
    * the star tracker placed with Ry -30 deg, its cone widening along its
      +z from the apex (radius 0 at z = 0, 0.08 m at z = 0.3 m):
      Ry(-30) z = (-sin 30, 0, cos 30), full angle 2 atan(0.08 / 0.3); its
      smaller baffle cone is not the one used;
    * the sun sensor's cone narrowing along +z (radius 0.17 m at z = 0, 0
      at z = 0.1 m): it looks along -z, full angle 2 atan(0.17 / 0.1);
    * the thruster placed with Rx 180 deg, its plume cone widening along
      its +z from the apex at its origin (radius 0 at z = 0, 0.1 m at
      z = 0.2 m): the plume goes along Rx(180) z = -z, so the thrust is +z
      (decision IDM-32), full angle 2 atan(0.1 / 0.2), from the apex at
      the unit's origin (0, 0, -0.3) m;
    * no axis from the gyro (no shape) or the magnetometer (a cylinder
      says nothing about a magnetometer's axes)."""
    found = _found(_plan(tmp_path))
    tilted = found["Reaction wheel tilted"]
    assert tilted.model_axis == pytest.approx([_SIN20, -_SIN30 * _COS20, _COS30 * _COS20])
    assert tilted.axis_source == "the cylinder 'Rotor'" and tilted.fov_deg is None
    assert found["Reaction wheel sideways"].model_axis == pytest.approx([0.0, -1.0, 0.0])
    assert found["Reaction wheel sideways"].axis("+z") == pytest.approx([0.0, 0.0, 1.0])  # its frame is not turned
    assert found["Torque rod A"].model_axis == pytest.approx([1.0, 0.0, 0.0])
    tracker = found["Star tracker optical head"]
    assert tracker.model_axis == pytest.approx([-_SIN30, 0.0, _COS30])
    assert tracker.axis_source == "the field-of-view cone 'Field of view'"
    assert tracker.fov_deg == pytest.approx(2.0 * math.degrees(math.atan(0.08 / 0.3)), abs=1.0e-4)  # [deg] kept to 6 digits
    sun = found["Sun sensor bottom"]
    assert sun.model_axis == pytest.approx([0.0, 0.0, -1.0])
    assert sun.fov_deg == pytest.approx(2.0 * math.degrees(math.atan(0.17 / 0.1)), abs=1.0e-4)  # [deg] kept to 6 digits
    thruster = found["Thruster 2"]
    assert thruster.model_axis == pytest.approx([0.0, 0.0, 1.0]) and thruster.axis_source == "the plume cone 'Plume'"
    assert thruster.fov_deg == pytest.approx(2.0 * math.degrees(math.atan(0.1 / 0.2)), abs=1.0e-4)  # [deg] 6 digits
    assert thruster.axis_origin_m == pytest.approx([0.0, 0.0, -0.3])  # [m]
    assert tracker.axis_origin_m is not None and found["Torque rod A"].axis_origin_m is None
    for name in ("Gyro unit", "Magnetometer boom tip"):
        assert (found[name].model_axis, found[name].axis_source, found[name].fov_deg) == (None, "", None), name
    assert found["Gyro unit"].axis(idm_devices.MODEL_AXIS) == found["Gyro unit"].axis("+z")


def test_the_model_s_axis_is_the_default_choice(tmp_path):
    """A device whose shapes show an axis is added along it by default;
    one whose shapes show none, along +z."""
    plan = _plan(tmp_path)
    axes = {f.equipment: c.axis for f, c in zip(plan.devices, idm_devices.default_choices(plan.devices))}
    assert axes == {"Reaction wheel tilted": "model", "Reaction wheel sideways": "model", "Torque rod A": "model",
                    "Star tracker optical head": "model", "Sun sensor bottom": "model", "Gyro unit": "+z",
                    "Magnetometer boom tip": "+z", "Thruster 2": "model"}
    with pytest.raises(ValueError, match="must be 'model' or one of"):
        plan.devices[0].axis("z")


def test_the_devices_built_take_the_model_s_axis_and_field_of_view(tmp_path):
    """A built device takes the model's axis in the parameter its kind reads
    and in its mount, a cone's angle as its mount's field of view, and its
    record says where the axis came from; an axis of the frame chosen
    instead is used as it is, with no field of view from the model."""
    plan = _plan(tmp_path)
    findings = [f for f in plan.devices if f.addable]
    choices = idm_devices.default_choices(findings)
    for choice in choices:
        if choice.kind in idm_devices.REQUIRED_VALUES:
            choice.add, choice.product = True, idm_devices.product_names(choice.kind)[0]
    result = idm_devices.build_devices(findings, choices, taken=set())
    devices = {d.name: d for d in result.sensors + result.actuators}
    by_name = {f.equipment: f for f in findings}
    for name in ("Reaction wheel tilted", "Reaction wheel sideways"):
        assert devices[name].params["gsHat_B"] == pytest.approx(by_name[name].model_axis)
        assert devices[name].mount.boresight == pytest.approx(by_name[name].model_axis)
        assert devices[name].mount.field_of_view_deg is None
    assert devices["Torque rod A"].params["gtHat_B"] == pytest.approx([1.0, 0.0, 0.0])
    assert devices["Sun sensor bottom"].params["nHat_B"] == pytest.approx([0.0, 0.0, -1.0])
    tracker = devices["Star tracker optical head"]
    assert tracker.mount.boresight == pytest.approx([-_SIN30, 0.0, _COS30])
    assert tracker.mount.field_of_view_deg == by_name["Star tracker optical head"].fov_deg
    detail = result.details["sensors[Star tracker optical head]"]
    assert "; axis from the field-of-view cone 'Field of view' (field of view 29.8628 deg); from " in detail
    assert detail.endswith(f"unit {by_name['Star tracker optical head'].source_id}")
    assert "; axis from the cylinder 'Rod'; " in result.details["actuators[Torque rod A]"]
    assert "; axis +z of the equipment frame (its shapes show none); " not in result.details["sensors[Gyro unit]"]
    assert "; axis +z of the equipment frame; " in result.details["sensors[Gyro unit]"]

    index = [f.equipment for f in findings].index("Sun sensor bottom")
    choices[index].axis = "+z"  # the user's choice over the model's
    sun = {d.name: d for d in idm_devices.build_devices(findings, choices, taken=set()).sensors}["Sun sensor bottom"]
    assert sun.params["nHat_B"] == pytest.approx([0.0, 0.0, 1.0]) and sun.mount.field_of_view_deg is None


def test_the_axis_text_says_where_the_axis_comes_from(tmp_path):
    """The words the import record and the dialog use for each choice."""
    found = _found(_plan(tmp_path))
    assert idm_devices.axis_text(found["Torque rod A"], "model") == "from the cylinder 'Rod'"
    assert idm_devices.axis_text(found["Gyro unit"], "model") == "+z of the equipment frame (its shapes show none)"
    assert idm_devices.axis_text(found["Torque rod A"], "-y") == "-y of the equipment frame"


def test_a_cone_s_axis_is_read_from_a_primitive_and_from_a_mesh():
    """``_cone_axis`` directly: a primitive cone (its base at -z of its
    centred frame, its apex at +z) looks along -z of that frame from its
    apex; a cone built as a mesh looks from its narrow end (where it
    starts) toward its wide one, with the
    angle from the model's radii (not the mesh's, scaled to keep each
    circle's area); a cylinder-like or flat one gives none. Frames: the
    identity, and a turn of 90 deg about x (which takes z to -y)."""
    turn = np.eye(4)
    turn[:3, :3] = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]  # Rx(90)
    primitive = SimpleNamespace(kind="cone", local=np.eye(4), dims={"height": 0.2, "base_diameter": 0.4}, cone=None)
    vector, angle, start = idm_devices._cone_axis(primitive, turn)
    assert vector == pytest.approx([0.0, 1.0, 0.0]) and angle == pytest.approx(90.0)
    assert start == pytest.approx([0.0, -0.1, 0.0])  # [m] the apex, at +z 0.1 m of the cone's frame, turned
    flat = SimpleNamespace(kind="cone", local=np.eye(4), dims={"height": 0.0, "base_diameter": 0.4}, cone=None)
    assert idm_devices._cone_axis(flat, np.eye(4)) is None

    def mesh(r0, r1, h):  # [m]
        return SimpleNamespace(kind="mesh", cone=(r0, r1, h))

    vector, angle, start = idm_devices._cone_axis(mesh(0.05, 0.15, 0.1), turn)  # truncated, widening along +z
    assert vector == pytest.approx([0.0, -1.0, 0.0]) and angle == pytest.approx(90.0)
    assert start == pytest.approx([0.0, 0.0, 0.0])  # [m] the narrow end, at z = 0
    vector, angle, start = idm_devices._cone_axis(mesh(0.15, 0.05, 0.1), np.eye(4))
    assert vector == pytest.approx([0.0, 0.0, -1.0]) and angle == pytest.approx(90.0)
    assert start == pytest.approx([0.0, 0.0, 0.1])  # [m] the narrow end, at z = h
    vector, _angle, start = idm_devices._cone_axis(mesh(0.0, 0.1, -0.1), np.eye(4))  # drawn along -z, widening along it
    assert vector == pytest.approx([0.0, 0.0, -1.0]) and start == pytest.approx([0.0, 0.0, 0.0])
    assert idm_devices._cone_axis(mesh(0.1, 0.1, 0.1), np.eye(4)) is None
    assert idm_devices._cone_axis(mesh(0.1, 0.2, 0.0), np.eye(4)) is None
    assert idm_devices._cone_axis(SimpleNamespace(kind="mesh", cone=None), np.eye(4)) is None


def test_the_command_line_adds_the_devices_along_the_model_s_axes(tmp_path):
    """``idm-import --devices``: the sun sensor looks along -z and the
    star tracker along its cone, with the cone's field of view."""
    path = tmp_path / "scenario.json"
    shutil.copyfile(_TEMPLATE, path)
    model = write_idm(tmp_path / "axessat.idm", model_xml("axessat"))
    assert cli.main(["idm-import", str(model), str(path), "--spacecraft", "sat-1", "--devices"]) == 0
    sensors = {d.name: d for d in load_scenario(path).spacecraft[0].sensors}
    assert sensors["Sun sensor bottom"].params["nHat_B"] == pytest.approx([0.0, 0.0, -1.0])
    assert sensors["Star tracker optical head"].mount.boresight == pytest.approx([-_SIN30, 0.0, _COS30])
    assert sensors["Star tracker optical head"].mount.field_of_view_deg == pytest.approx(29.8628)
    assert sensors["Gyro unit"].mount.boresight == pytest.approx([0.0, 0.0, 1.0])
