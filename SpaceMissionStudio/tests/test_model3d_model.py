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

"""Tests for a spacecraft's 3D model in the scenario: the schema, deriving
and applying mass properties and facets (model3d.model), importing mass
properties from a file (model3d.mass_import), and the plausibility
warnings. No Basilisk needed."""

import json

import numpy as np
import pytest

from spacemissionstudio.engine import scenario_checks
from spacemissionstudio.model3d import mass_import, obj_io, shapes
from spacemissionstudio.model3d import model as model3d
from spacemissionstudio.schema import ScenarioValidationError, load_scenario
from spacemissionstudio.schema.scenario import (GravityConfig, ModelMassPropertiesConfig, ModelMeshConfig,
                                                ModelPartConfig, OrbitIC, Scenario, SolarArrayConfig,
                                                SpacecraftConfig, SpacecraftModelConfig)


def _bus_and_box() -> SpacecraftModelConfig:
    """An 80 kg octagonal bus at the origin and a 20 kg box 1 m out along
    +x, mounted on the bus's +x side (that face left out)."""
    return SpacecraftModelConfig(parts=[
        ModelPartConfig(name="bus", shape="prism", dimensions_m={"width_across_flats": 1.0, "height": 1.0},
                        mass_kg=80.0),
        ModelPartConfig(name="box", shape="box", dimensions_m={"x": 0.4, "y": 0.4, "z": 0.4},
                        position_b_m=[0.7, 0.0, 0.0], mass_kg=20.0, excluded_faces=["-x"]),
    ])


def _scenario(model=None, **sc_fields) -> Scenario:
    return Scenario(name="model test", epoch_utc="2030-01-01T00:00:00",
                    gravity=GravityConfig(central_body="earth", central_body_degree=0),
                    spacecraft=[SpacecraftConfig(name="sat-1", model=model, orbit=OrbitIC(
                        type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
                        **sc_fields)])


def test_derive_combines_the_parts_mass_and_center():
    """100 kg total; the center of mass is 20 kg * 0.7 m / 100 kg = 0.14 m
    along +x; Iyy and Izz grow by the parallel-axis terms."""
    derived = model3d.derive(_bus_and_box())
    assert not derived.errors
    props = derived.mass_properties
    assert props.mass_kg == pytest.approx(100.0)
    np.testing.assert_allclose(props.center_of_mass_m, [0.14, 0.0, 0.0], atol=1e-12)
    bus = shapes.mass_properties("prism", {"width_across_flats": 1.0, "height": 1.0}, 80.0, shell=False)
    box = shapes.mass_properties("box", {"x": 0.4, "y": 0.4, "z": 0.4}, 20.0, shell=False)
    iyy = bus.inertia_kg_m2[1, 1] + 80.0 * 0.14 ** 2 + box.inertia_kg_m2[1, 1] + 20.0 * 0.56 ** 2
    assert props.inertia_kg_m2[1, 1] == pytest.approx(iyy, rel=1e-12)
    assert props.inertia_kg_m2[0, 0] == pytest.approx(bus.inertia_kg_m2[0, 0] + box.inertia_kg_m2[0, 0])


def test_derive_builds_facets_named_by_part_and_leaves_out_excluded_faces():
    """10 bus faces (8 sides, 2 caps) plus 5 box faces (its -x face, on the
    bus, left out), named 'part: face', with the part's coefficients."""
    model = _bus_and_box()
    model.parts[1].drag_coeff = 2.6
    derived = model3d.derive(model)
    names = [f.name for f in derived.facets]
    assert len(names) == 15
    assert "box: -x" not in names and "box: +x" in names and "bus: side 1" in names
    box_x = next(f for f in derived.facets if f.name == "box: +x")
    assert box_x.drag_coeff == 2.6
    np.testing.assert_allclose(box_x.location_b, [0.9, 0.0, 0.0], atol=1e-12)
    assert derived.projected_areas_m2()["+z"] == pytest.approx(
        8 * 0.5 ** 2 * np.tan(np.pi / 8) + 0.4 * 0.4)


def test_apply_writes_the_fields_and_they_validate():
    """Applying writes dry mass, center of mass, inertia and facets; the
    spacecraft then validates, and nothing is stale."""
    scenario = _scenario(_bus_and_box())
    sc = scenario.spacecraft[0]
    derived = model3d.derive(sc.model)
    written = model3d.apply(sc, derived)
    assert set(written) == {"dry_mass_kg", "center_of_mass_b_m", "inertia_kg_m2", "facets"}
    assert sc.dry_mass_kg == pytest.approx(100.0)
    assert sc.center_of_mass_b_m == pytest.approx([0.14, 0.0, 0.0])
    scenario.validate()
    assert model3d.stale_fields(sc, derived) == []
    sc.dry_mass_kg = 90.0
    sc.facets = sc.facets[:-1]
    assert set(model3d.stale_fields(sc, derived)) == {"dry_mass_kg", "facets"}


def test_apply_respects_switches_orbit_only_and_flexible_arrays():
    """Facets are not written in an orbit-only scenario or when switched
    off; dry_mass_kg adds the flexible arrays' own mass to the model's."""
    sc = _scenario(_bus_and_box(), solar_arrays=[SolarArrayConfig(
        name="wing", mass_kg=7.5, span_m=2.0, width_m=1.0, hinge_position_b=[0.5, 0.0, 0.0],  # [kg], [m]
        deploy_direction_b=[1.0, 0.0, 0.0], normal_b=[0.0, 0.0, 1.0], first_mode_hz=1.0, damping_ratio=0.02)]).spacecraft[0]
    derived = model3d.derive(sc.model)
    assert "facets" not in model3d.apply(sc, derived, orbit_only=True)
    assert sc.dry_mass_kg == pytest.approx(107.5)
    sc.model.apply_facets = False
    sc.model.apply_mass_properties = False
    assert model3d.apply(sc, derived) == []


def test_typed_mass_properties_replace_the_computed_ones():
    """With the 'typed' source the typed values are applied, while the
    computed ones stay available for comparison."""
    model = _bus_and_box()
    model.mass_properties_source = "typed"
    model.mass_properties = ModelMassPropertiesConfig(mass_kg=120.0, center_of_mass_b_m=[0.0, 0.0, 0.05],
                                                      inertia_kg_m2=[20, 0, 0, 0, 22, 0, 0, 0, 18])
    derived = model3d.derive(model)
    assert derived.mass_properties.mass_kg == 120.0
    assert derived.computed.mass_kg == pytest.approx(100.0)


def test_mesh_parts_come_from_the_obj_file(tmp_path):
    """Two groups of an .obj, in mm: each is a part; a solid group gets
    the closed box's mass properties; scale and position apply; a changed
    file is flagged by its SHA-256."""
    obj_io.write_obj(tmp_path / "parts.obj", [
        obj_io.ObjGroup("body", shapes.mesh("box", {"x": 1000.0, "y": 1000.0, "z": 1000.0})),
        obj_io.ObjGroup("plate", shapes.mesh("panel", {"width": 2000.0, "length": 1000.0, "thickness": 10.0}))])
    sha = model3d.file_sha256(tmp_path / "parts.obj")
    model = SpacecraftModelConfig(
        meshes=[ModelMeshConfig(path="parts.obj", sha256=sha, units="mm")],
        parts=[ModelPartConfig(name="body", shape="mesh", mesh_index=0, mesh_group="body", mass_kg=60.0,
                               scale=[1.0, 1.0, 0.5]),
               ModelPartConfig(name="plate", shape="mesh", mesh_index=0, mesh_group="plate", mass_kg=4.0,
                               distribution="shell", position_b_m=[0.0, 0.0, 0.6])])
    derived = model3d.derive(model, base_dir=tmp_path)
    assert not derived.errors and not derived.warnings
    body = shapes.mass_properties("box", {"x": 1.0, "y": 1.0, "z": 0.5}, 60.0, shell=False)
    plate_z = 64.0 * 0.0 + 4.0 * 0.6
    assert derived.mass_properties.center_of_mass_m[2] == pytest.approx(plate_z / 64.0)
    assert derived.computed.inertia_kg_m2[2, 2] == pytest.approx(
        body.inertia_kg_m2[2, 2] + shapes.mass_properties(
            "panel", {"width": 2.0, "length": 1.0, "thickness": 0.01}, 4.0, shell=True).inertia_kg_m2[2, 2], rel=1e-9)
    (tmp_path / "parts.obj").write_text((tmp_path / "parts.obj").read_text() + "# edited\n")
    assert any("changed since it was imported" in w for w in model3d.derive(model, base_dir=tmp_path).warnings)


def test_derive_reports_problems_without_raising(tmp_path):
    """A missing mesh file and an unknown group are errors on their parts;
    the other parts still count."""
    model = SpacecraftModelConfig(
        meshes=[ModelMeshConfig(path="missing.obj")],
        parts=[ModelPartConfig(name="ghost", shape="mesh", mesh_index=0, mesh_group="x", mass_kg=5.0),
               ModelPartConfig(name="bus", shape="box", dimensions_m={"x": 1, "y": 1, "z": 1}, mass_kg=50.0)])
    derived = model3d.derive(model, base_dir=tmp_path)
    assert any("missing.obj" in e for e in derived.errors)
    assert any("ghost" in e for e in derived.errors)
    assert derived.mass_properties.mass_kg == pytest.approx(50.0)


def test_too_many_facets_are_not_applied():
    """Over the 200-facet cap the facets are withheld, with a warning."""
    model = SpacecraftModelConfig(parts=[ModelPartConfig(
        name="ball", shape="sphere", dimensions_m={"diameter": 1.0}, segments=128, mass_kg=1.0)])
    derived = model3d.derive(model)
    assert derived.facets is None
    assert any("more than 200" in w for w in derived.warnings)


def test_model_round_trips_through_a_saved_file(tmp_path):
    """Save and load: the model and the applied fields come back equal."""
    scenario = _scenario(_bus_and_box())
    sc = scenario.spacecraft[0]
    model3d.apply(sc, model3d.derive(sc.model))
    scenario.save(tmp_path / "s.json")
    loaded = load_scenario(tmp_path / "s.json")
    assert loaded.spacecraft[0].model == sc.model
    assert loaded.spacecraft[0].center_of_mass_b_m == sc.center_of_mass_b_m
    assert loaded.spacecraft[0].facets == sc.facets


def test_old_files_without_a_model_still_load(tmp_path):
    """A spacecraft saved without the new fields loads with no model and
    the center of mass at B."""
    scenario = _scenario()
    scenario.save(tmp_path / "s.json")
    data = json.loads((tmp_path / "s.json").read_text())
    for key in ("model", "center_of_mass_b_m"):
        data["spacecraft"][0].pop(key, None)
    (tmp_path / "s.json").write_text(json.dumps(data))
    loaded = load_scenario(tmp_path / "s.json")
    assert loaded.spacecraft[0].model is None
    assert loaded.spacecraft[0].center_of_mass_b_m == [0.0, 0.0, 0.0]


@pytest.mark.parametrize("change, message", [
    (lambda m: setattr(m.parts[0], "shape", "torus"), "shape 'torus'"),
    (lambda m: m.parts[0].dimensions_m.pop("height"), "exactly"),
    (lambda m: m.parts[0].dimensions_m.update(height=-1.0), r"\(0, 1000\]"),
    (lambda m: setattr(m.parts[1], "name", "bus"), "unique"),
    (lambda m: setattr(m.parts[1], "name", "a/b"), "contains"),
    (lambda m: setattr(m.parts[1], "excluded_faces", ["sides"]), "not faces of a box"),
    (lambda m: setattr(m.parts[0], "color", [1.0, 2.0, 0.0]), "color"),
    (lambda m: setattr(m.parts[0], "sides", 2), "sides"),
    (lambda m: setattr(m, "mass_properties_source", "typed"), "needs mass_properties"),
    (lambda m: setattr(m, "parts", []), "at least one part"),
    (lambda m: m.parts.append(ModelPartConfig(name="m", shape="mesh", mesh_group="g")), "mesh_index"),
])
def test_validation_names_the_problem(change, message):
    """Each bad model field is refused with a message naming it."""
    model = _bus_and_box()
    change(model)
    with pytest.raises(ScenarioValidationError, match=message):
        _scenario(model).validate()


def test_center_of_mass_must_be_finite_and_near():
    """center_of_mass_b_m: three finite numbers within 100 m of B."""
    with pytest.raises(ScenarioValidationError, match="center_of_mass_b_m"):
        _scenario(center_of_mass_b_m=[0.0, 0.0, 150.0]).validate()


def test_mass_import_json_with_conversions(tmp_path):
    """JSON about B with +integral products: negated to the tensor and
    moved to the center of mass; the file's name and SHA-256 recorded."""
    path = tmp_path / "mass.json"
    path.write_text(json.dumps({"mass_kg": 100.0, "center_of_mass_m": [0.0, 0.0, 0.1],
                                "inertia_kg_m2": [[11.0, 0.5, 0.0], [0.5, 12.0, 0.0], [0.0, 0.0, 10.0]],
                                "inertia_about": "origin", "products_of_inertia": "integral"}))
    config, notes = mass_import.read_mass_properties(path)
    inertia = np.reshape(config.inertia_kg_m2, (3, 3))
    assert inertia[0, 1] == pytest.approx(-0.5)
    assert inertia[0, 0] == pytest.approx(11.0 - 100.0 * 0.01)  # moved off B by 0.1 m along z
    assert inertia[2, 2] == pytest.approx(10.0)
    assert config.source_file == "mass.json" and len(config.source_sha256) == 64
    assert len(notes) == 2


def test_mass_import_csv(tmp_path):
    """The CSV form gives the same values as the JSON form."""
    path = tmp_path / "mass.csv"
    path.write_text("quantity,value\nmass_kg,152.4\ncom_x_m,0.012\ncom_y_m,-0.004\ncom_z_m,0.31\n"
                    "Ixx,18.2\nIyy,21.5\nIzz,14.9\nIxy,-0.3\nIxz,0.1\nIyz,0.2\n")
    config, notes = mass_import.read_mass_properties(path)
    assert config.mass_kg == 152.4
    assert config.inertia_kg_m2 == pytest.approx([18.2, -0.3, 0.1, -0.3, 21.5, 0.2, 0.1, 0.2, 14.9])
    assert notes == []


@pytest.mark.parametrize("content, message", [
    ('{"mass_kg": 1}', "missing"),
    ('{"mass_kg": -1, "center_of_mass_m": [0,0,0], "inertia_kg_m2": [1,0,0,0,1,0,0,0,1]}', "positive"),
    ('{"mass_kg": 1, "center_of_mass_m": [0,0,0], "inertia_kg_m2": [1,0,0,0,1,0,0,0,5]}', "triangle"),
    ('{"mass_kg": 1, "center_of_mass_m": [0,0,0], "inertia_kg_m2": [1,0.2,0,0,1,0,0,0,1]}', "symmetric"),
    ('{"mass_kg": 1, "center_of_mass_m": [0,0,0], "inertia_kg_m2": [1,0,0,0,1,0,0,0,1], "inertia_about": "x"}',
     "inertia_about"),
    ("not json", "not valid JSON"),
])
def test_mass_import_refuses_bad_files(tmp_path, content, message):
    """Bad or unphysical values are refused with the reason."""
    path = tmp_path / "mass.json"
    path.write_text(content)
    with pytest.raises(mass_import.MassImportError, match=message):
        mass_import.read_mass_properties(path)


def test_plausibility_warns_about_a_stale_model():
    """A model whose applied values were changed by hand is reported, as
    is a model with a part that cannot be built."""
    scenario = _scenario(_bus_and_box())
    sc = scenario.spacecraft[0]
    model3d.apply(sc, model3d.derive(sc.model))
    assert not [w for w in scenario_checks.plausibility_warnings(scenario) if "3D model" in w]
    sc.dry_mass_kg = 50.0
    assert any("dry_mass_kg differ from the 3D model" in w for w in scenario_checks.plausibility_warnings(scenario))
