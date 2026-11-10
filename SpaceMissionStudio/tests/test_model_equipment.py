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
"""Mounted equipment, the stowed configuration and face properties on the
3D model (model-analyses Phase A): the scenario fields round-trip and are
written only when set, references to parts follow a rename and dangling
ones are refused, mounts take what their definition gives and move with
their part, and the stowed configuration has its own mass properties."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.model3d import equipment, model as model3d
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.references import ReferenceError, find_part_references, rename_part
from spacemissionstudio.schema.scenario import (
    FacePropertyConfig,
    MountConfig,
    MountedEquipmentConfig,
    PartPoseConfig,
    Scenario,
    ScenarioValidationError,
)

_TEMPLATE = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" \
    / "28_octagonal_bus_3d_model.json"


def _scenario():
    return load_scenario(_TEMPLATE)


def test_a_scenario_without_the_new_fields_saves_exactly_as_before():
    """Every bundled template, loaded and saved again, gives the very same
    data: none of the new fields is written when it is not set."""
    folder = _TEMPLATE.parent
    for path in sorted(folder.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert load_scenario(path).to_dict() == raw, path.name


def test_mounts_equipment_poses_and_face_properties_round_trip():
    """A spacecraft with a sensor mount, an antenna-less equipment item, a
    stowed pose, a face property and model analyses saves and loads to the
    same records; unset values of a mount are left out of the file."""
    scenario = _scenario()
    sc = scenario.spacecraft[0]
    sc.sensors[0].mount = MountConfig(part="star tracker", position_m=[0.0, 0.0, 0.125], boresight=[0.0, 0.0, 1.0],
                                      field_of_view_deg=20.0, exclusion_sun_deg=30.0)
    sc.model.equipment.append(MountedEquipmentConfig("camera", "camera", MountConfig(
        part="bus", position_m=[0.6, 0.0, 0.0], boresight=[1.0, 0.0, 0.0], field_of_view_deg=10.0), mass_kg=3.0))
    sc.model.stowed.append(PartPoseConfig("panel +y", [0.0, 0.62, 0.0], [90.0, 0.0, 0.0]))
    sc.model.face_properties.append(FacePropertyConfig("bus", "+z", diffuse_coeff=0.5))
    data = scenario.to_dict()
    mount = data["spacecraft"][0]["sensors"][0]["mount"]
    assert "plume_half_angle_deg" not in mount and mount["exclusion_sun_deg"] == 30.0
    again = Scenario.from_dict(json.loads(json.dumps(data)))
    again.validate()
    sc2 = again.spacecraft[0]
    assert sc2.sensors[0].mount == sc.sensors[0].mount
    assert sc2.model.equipment == sc.model.equipment and sc2.model.stowed == sc.model.stowed
    assert sc2.model.face_properties == sc.model.face_properties


def test_references_to_a_part_follow_its_rename():
    """Renaming a part updates the mount on it, its stowed pose and its
    face property; a name already taken is refused."""
    scenario = _scenario()
    sc = scenario.spacecraft[0]
    sc.sensors[0].mount = MountConfig(part="star tracker", boresight=[0.0, 0.0, 1.0])
    sc.model.stowed.append(PartPoseConfig("panel +y"))
    sc.model.face_properties.append(FacePropertyConfig("panel +y", "+z", diffuse_coeff=0.2))
    assert len(find_part_references(sc, "panel +y")) == 2
    assert rename_part(sc, "panel +y", "array +y") == 2
    assert sc.model.stowed[0].part == "array +y" and sc.model.face_properties[0].part == "array +y"
    assert rename_part(sc, "star tracker", "st head") == 1 and sc.sensors[0].mount.part == "st head"
    scenario.validate()
    with pytest.raises(ReferenceError, match="already exists"):
        rename_part(sc, "bus", "dish")


def test_a_reference_to_a_missing_part_or_face_is_refused():
    """A mount, pose or face property naming a part the model lacks, or a
    face the shape lacks, does not validate."""
    for change, message in [
        (lambda sc: setattr(sc.sensors[0], "mount", MountConfig(part="nothing")), "not a part of the model"),
        (lambda sc: sc.model.stowed.append(PartPoseConfig("nothing")), "not a part of the model"),
        (lambda sc: sc.model.face_properties.append(FacePropertyConfig("bus", "+x")), "is not a face of"),
        (lambda sc: sc.model.face_properties.append(FacePropertyConfig("bus", "+z", material="unobtainium")),
         "not in the library"),
    ]:
        scenario = _scenario()
        change(scenario.spacecraft[0])
        with pytest.raises(ScenarioValidationError, match=message):
            scenario.validate()


def test_a_mount_takes_what_its_definition_gives_and_moves_with_its_part():
    """A thruster's mount takes its position and direction from r_B and
    tHat_B; a mount on a part is in the part's frame and follows the part
    to its stowed pose."""
    scenario = _scenario()
    sc = scenario.spacecraft[0]
    sc.actuators.append(copy.deepcopy(sc.actuators[0]))
    thruster = sc.actuators[-1]
    thruster.kind, thruster.name = "thruster", "thr-1"
    thruster.params = {"thruster_type": "MOOG_Monarc_1", "r_B": [0.0, 0.0, -0.7], "tHat_B": [0.0, 0.0, 1.0]}
    thruster.mount = MountConfig(plume_half_angle_deg=15.0)
    sc.model.equipment.append(MountedEquipmentConfig("sun cell", "solar_cell", MountConfig(
        part="panel +y", position_m=[0.0, 0.0, 0.015], boresight=[0.0, 0.0, 1.0])))
    sc.model.stowed.append(PartPoseConfig("panel +y", [0.0, 0.62, 0.0], [90.0, 0.0, 0.0]))
    deployed = {item.name: item for item in equipment.mounted_items(sc)}
    assert np.allclose(deployed["thr-1"].position_b_m, [0, 0, -0.7]) and deployed["thr-1"].plume_half_angle_deg == 15.0
    assert np.allclose(deployed["sun cell"].position_b_m, [0.0, 1.7, 0.015])
    stowed = {item.name: item for item in equipment.mounted_items(sc, "stowed")}
    # roll 90 deg about x: the panel's +z turns to -y; its +z face's centre goes to y = 0.62 - 0.015
    assert np.allclose(stowed["sun cell"].boresight_b, [0.0, -1.0, 0.0], atol=1e-12)
    assert np.allclose(stowed["sun cell"].position_b_m, [0.0, 0.605, 0.0], atol=1e-12)


def test_the_stowed_configuration_has_its_own_mass_properties():
    """Folding both 10 kg panels in to y = +-0.62 m keeps the mass and the
    centre of mass (symmetric), and lowers the roll inertia by
    2 x 10 kg x (1.7^2 - 0.62^2) m^2 plus the change of each panel's own."""
    scenario = _scenario()
    model = scenario.spacecraft[0].model
    model.stowed += [PartPoseConfig("panel +y", [0.0, 0.62, 0.0], [90.0, 0.0, 0.0]),
                     PartPoseConfig("panel -y", [0.0, -0.62, 0.0], [90.0, 0.0, 0.0])]
    deployed = model3d.derive(model, base_dir=_TEMPLATE.parent).computed
    stowed = model3d.derive(model, base_dir=_TEMPLATE.parent, configuration="stowed").computed
    assert stowed.mass_kg == pytest.approx(deployed.mass_kg)
    assert np.allclose(stowed.center_of_mass_m, deployed.center_of_mass_m)
    length, t = 2.0, 0.03  # [m] panel length, thickness
    own_deployed = 10.0 * (length ** 2 + t ** 2) / 12.0  # [kg*m^2] about x, panel flat
    own_stowed = 10.0 * (t ** 2 + length ** 2) / 12.0  # [kg*m^2] about x, rolled 90 deg: the same pair of extents
    expected = 2.0 * (10.0 * (1.7 ** 2 - 0.62 ** 2) + own_deployed - own_stowed)  # [kg*m^2]
    assert deployed.inertia_kg_m2[0, 0] - stowed.inertia_kg_m2[0, 0] == pytest.approx(expected, rel=1e-9)


def test_equipment_mass_counts_in_the_model():
    """A 3 kg camera on the bus adds 3 kg at its mount to the computed mass
    properties."""
    scenario = _scenario()
    model = scenario.spacecraft[0].model
    before = model3d.derive(model, base_dir=_TEMPLATE.parent).computed
    model.equipment.append(MountedEquipmentConfig("camera", "camera", MountConfig(
        position_m=[0.6, 0.0, 0.0], boresight=[1.0, 0.0, 0.0]), mass_kg=3.0))
    after = model3d.derive(model, base_dir=_TEMPLATE.parent).computed
    assert after.mass_kg == pytest.approx(before.mass_kg + 3.0)
    expected_x = (before.mass_kg * before.center_of_mass_m[0] + 3.0 * 0.6) / after.mass_kg  # [m]
    assert after.center_of_mass_m[0] == pytest.approx(expected_x)


def test_a_face_property_sets_that_faces_facets():
    """A diffuse coefficient set on the bus's sides reaches every side
    facet and no other."""
    scenario = _scenario()
    model = scenario.spacecraft[0].model
    model.face_properties.append(FacePropertyConfig("bus", "sides", diffuse_coeff=0.6, specular_coeff=0.1))
    facets = model3d.derive(model, base_dir=_TEMPLATE.parent).facets
    sides = [f for f in facets if f.name.startswith("bus: side")]
    assert sides and all(f.diffuse_coeff == 0.6 and f.specular_coeff == 0.1 for f in sides)
    assert all(f.diffuse_coeff == 0.1 for f in facets if f.name == "bus: +z")
