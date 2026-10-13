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

"""Tests for spacemissionstudio.model3d's geometry: shapes, mass
properties, .obj reading and writing, and surface facets. Every expected
value is a textbook formula or a hand-worked case, not a number read back
from the code."""

import math

import numpy as np
import pytest

from spacemissionstudio.model3d import mass_properties as mp
from spacemissionstudio.model3d import obj_io, shapes, surfaces
from spacemissionstudio.model3d.geometry import Mesh, merge, rotation_matrix

BOX = {"x": 1.2, "y": 0.8, "z": 0.5}  # [m]


def _signed_volume(mesh: Mesh) -> float:
    a, b, c = mesh.corners()
    return float(np.einsum("mi,mi->m", a, np.cross(b, c)).sum() / 6.0)


@pytest.mark.parametrize("shape, dims", [
    ("box", BOX),
    ("prism", {"width_across_flats": 1.0, "height": 0.9}),
    ("cylinder", {"diameter": 0.6, "height": 1.1}),
    ("cone", {"base_diameter": 0.8, "height": 0.7}),
    ("sphere", {"diameter": 0.5}),
    ("panel", {"width": 1.0, "length": 2.0, "thickness": 0.02}),
])
def test_every_shape_mesh_is_closed_and_wound_outward(shape, dims):
    """Each shape's drawn mesh is watertight with outward normals: its
    signed volume is positive."""
    mesh = shapes.mesh(shape, dims)
    assert mesh.is_closed()
    assert _signed_volume(mesh) > 0.0


def test_box_solid_and_shell_match_the_formulas():
    """A solid box: I = m (b^2 + c^2) / 12 per axis. A box shell: the six
    faces as thin plates, each moved out to its face (worked by hand)."""
    m = 12.0  # [kg]
    x, y, z = BOX["x"], BOX["y"], BOX["z"]
    solid = shapes.mass_properties("box", BOX, m, shell=False)
    np.testing.assert_allclose(solid.center_of_mass_m, 0.0, atol=1e-12)
    np.testing.assert_allclose(np.diag(solid.inertia_kg_m2),
                               [m * (y * y + z * z) / 12, m * (x * x + z * z) / 12, m * (x * x + y * y) / 12])
    np.testing.assert_allclose(solid.inertia_kg_m2 - np.diag(np.diag(solid.inertia_kg_m2)), 0.0, atol=1e-12)

    shell = shapes.mass_properties("box", BOX, m, shell=True)
    area = 2 * (x * y + y * z + x * z)
    sigma = m / area  # [kg/m^2]
    # Ixx: the two x-faces (y by z plates at x = +-x/2: in-plane moment only),
    # the two y-faces (x by z at y = +-y/2), the two z-faces (x by y at z = +-z/2).
    m_x, m_y, m_z = sigma * y * z, sigma * x * z, sigma * x * y
    ixx = 2 * (m_x * (y * y + z * z) / 12) + 2 * (m_y * z * z / 12 + m_y * (y / 2) ** 2) \
        + 2 * (m_z * y * y / 12 + m_z * (z / 2) ** 2)
    assert shell.inertia_kg_m2[0, 0] == pytest.approx(ixx, rel=1e-12)


def test_octagonal_prism_matches_the_regular_polygon_formula():
    """A solid regular n-gon prism of circumradius R: Izz = m R^2 (1 + 2
    cos^2(pi/n)) / 6, Ixx = Izz / 2 + m h^2 / 12; its first flat faces +x."""
    m, w, h = 80.0, 1.0, 0.9  # [kg], [m], [m]
    n = 8
    radius = (w / 2) / math.cos(math.pi / n)
    izz = m * radius ** 2 * (1 + 2 * math.cos(math.pi / n) ** 2) / 6
    props = shapes.mass_properties("prism", {"width_across_flats": w, "height": h}, m, shell=False, sides=n)
    np.testing.assert_allclose(np.diag(props.inertia_kg_m2), [izz / 2 + m * h * h / 12] * 2 + [izz], rtol=1e-12)
    xs = shapes.mesh("prism", {"width_across_flats": w, "height": h}, sides=n).vertices[:, 0]
    assert xs.max() == pytest.approx(w / 2)  # across flats along x, not across corners
    side_faces = [f for f in shapes.faces("prism", {"width_across_flats": w, "height": h}) if f.group == "sides"]
    assert len(side_faces) == n
    np.testing.assert_allclose(side_faces[0].normal, [1.0, 0.0, 0.0], atol=1e-12)


@pytest.mark.parametrize("shell", [False, True])
def test_curved_closed_forms_agree_with_finely_meshed_shapes(shell):
    """The cylinder and cone closed forms against the exact integrals of a
    256-sided mesh of the same shape: they agree to 0.1 %."""
    m = 10.0  # [kg]
    cylinder = {"diameter": 0.6, "height": 1.1}
    closed = mp.cylinder(m, 0.3, 1.1, shell)
    meshed = (mp.shell_mesh if shell else mp.solid_mesh)(shapes.mesh("cylinder", cylinder, segments=256), m)
    np.testing.assert_allclose(np.diag(meshed.inertia_kg_m2), np.diag(closed.inertia_kg_m2), rtol=1e-3)
    cone = {"base_diameter": 0.8, "height": 0.7}
    closed = mp.cone(m, 0.4, 0.7, shell)
    meshed = (mp.shell_mesh if shell else mp.solid_mesh)(shapes.mesh("cone", cone, segments=256), m)
    np.testing.assert_allclose(meshed.center_of_mass_m, closed.center_of_mass_m, atol=1e-4)
    np.testing.assert_allclose(np.diag(meshed.inertia_kg_m2), np.diag(closed.inertia_kg_m2), rtol=1e-3)


def test_sphere_solid_and_shell_moments():
    """Solid sphere 2/5 m r^2, thin shell 2/3 m r^2."""
    assert mp.sphere(3.0, 0.5, shell=False).inertia_kg_m2[0, 0] == pytest.approx(0.4 * 3.0 * 0.25)
    assert mp.sphere(3.0, 0.5, shell=True).inertia_kg_m2[2, 2] == pytest.approx(2 / 3 * 3.0 * 0.25)


def test_combine_applies_the_parallel_axis_theorem():
    """Two 1 kg points at x = +-1 m: center at 0, Iyy = Izz = 2 kg m^2,
    Ixx = 0. Moved by +0.5 m in y: the center moves, the inertia about it
    does not."""
    point = mp.MassProperties(1.0, [0, 0, 0], np.zeros((3, 3)))
    pair = mp.combine([mp.placed(point, np.eye(3), [1, 0, 0]), mp.placed(point, np.eye(3), [-1, 0, 0])])
    np.testing.assert_allclose(pair.center_of_mass_m, 0.0, atol=1e-15)
    np.testing.assert_allclose(np.diag(pair.inertia_kg_m2), [0.0, 2.0, 2.0])
    moved = mp.placed(pair, np.eye(3), [0, 0.5, 0])
    np.testing.assert_allclose(moved.center_of_mass_m, [0, 0.5, 0])
    np.testing.assert_allclose(moved.inertia_kg_m2, pair.inertia_kg_m2)
    np.testing.assert_allclose(np.diag(moved.inertia_about([0, 0, 0])), [0.5, 2.0, 2.5])


def test_rotation_turns_the_inertia_and_products_appear():
    """A box turned 90 deg in yaw swaps Ixx and Iyy; turned 45 deg it gets
    the product Ixy = (Ixx_local - Iyy_local) / 2: negative for this box,
    whose long x side now runs along x = y (tensor convention, Ixy =
    -integral(x y dm))."""
    local = shapes.mass_properties("box", BOX, 5.0, shell=False)
    ixx, iyy = local.inertia_kg_m2[0, 0], local.inertia_kg_m2[1, 1]
    turned = mp.placed(local, rotation_matrix([0, 0, 90]), [0, 0, 0])
    assert turned.inertia_kg_m2[0, 0] == pytest.approx(iyy)
    assert turned.inertia_kg_m2[1, 1] == pytest.approx(ixx)
    diagonal = mp.placed(local, rotation_matrix([0, 0, 45]), [0, 0, 0])
    assert diagonal.inertia_kg_m2[0, 1] == pytest.approx((ixx - iyy) / 2)
    assert diagonal.inertia_kg_m2[0, 1] < 0.0
    moments, _ = diagonal.principal()
    np.testing.assert_allclose(sorted(moments), sorted(np.diag(local.inertia_kg_m2)))


def test_rotation_matrix_is_yaw_then_pitch_then_roll():
    """[roll, pitch, yaw] = [0, 0, 90] turns +x onto +y; [90, 0, 0] turns +y
    onto +z; combined, roll acts about the already-yawed x axis (body +y),
    so the part's z turns onto body +x."""
    np.testing.assert_allclose(rotation_matrix([0, 0, 90]) @ [1, 0, 0], [0, 1, 0], atol=1e-12)
    np.testing.assert_allclose(rotation_matrix([90, 0, 0]) @ [0, 1, 0], [0, 0, 1], atol=1e-12)
    np.testing.assert_allclose(rotation_matrix([90, 0, 90]) @ [0, 0, 1], [1, 0, 0], atol=1e-12)


def test_open_mesh_cannot_be_a_solid_but_can_be_a_shell():
    """A box missing one face is not closed: a solid is refused with the
    hint to use a shell, which works."""
    box = shapes.mesh("box", BOX)
    open_box = Mesh(box.vertices, box.triangles[2:])
    assert not open_box.is_closed()
    with pytest.raises(mp.MassPropertiesError, match="shell"):
        mp.solid_mesh(open_box, 1.0)
    assert mp.shell_mesh(open_box, 1.0).mass_kg == 1.0


def test_welding_closes_a_mesh_with_repeated_corners():
    """Corners repeated once per face (as many exporters write them) leave
    the mesh open until they are welded."""
    box = shapes.mesh("box", BOX)
    a, b, c = box.corners()
    loose = Mesh(np.concatenate([a, b, c]), np.arange(3 * len(a)).reshape(3, -1).T)
    assert not loose.is_closed()
    assert loose.welded().is_closed()
    assert mp.solid_mesh(loose.welded(), 2.0).inertia_kg_m2[0, 0] == pytest.approx(
        mp.solid_mesh(box, 2.0).inertia_kg_m2[0, 0])


def test_mirroring_scale_keeps_normals_outward():
    """Scaling by -1 along x mirrors the mesh; the winding is reversed so
    the volume stays positive."""
    mirrored = shapes.mesh("cone", {"base_diameter": 0.8, "height": 0.7}).transformed(np.eye(3), [0, 0, 0],
                                                                                       scale=[-1, 1, 1])
    assert _signed_volume(mirrored) > 0.0


def test_box_faces_and_their_projected_areas():
    """A box's six faces: areas y*z, x*z, x*y with outward normals at the
    face centres; from +x it shows y*z. Placed and turned, they follow."""
    faces = shapes.faces("box", BOX)
    assert [f.name for f in faces] == ["+x", "-x", "+y", "-y", "+z", "-z"]
    assert surfaces.projected_area_m2(faces, [1, 0, 0]) == pytest.approx(BOX["y"] * BOX["z"])
    placed = surfaces.placed_faces(faces, rotation_matrix([0, 0, 90]), [0, 0, 2])
    np.testing.assert_allclose(placed[0].normal, [0, 1, 0], atol=1e-12)  # +x face now faces +y
    np.testing.assert_allclose(placed[0].centroid_m, [0, BOX["x"] / 2, 2], atol=1e-12)


def test_curved_faces_carry_the_true_area():
    """A cylinder's side faces share its true side area, so from across the
    axis it shows close to diameter * height; a sphere shows close to
    pi r^2 from anywhere."""
    faces = shapes.faces("cylinder", {"diameter": 0.6, "height": 1.1}, segments=64)
    assert surfaces.projected_area_m2(faces, [1, 0, 0]) == pytest.approx(0.6 * 1.1, rel=2e-3)
    sphere = shapes.faces("sphere", {"diameter": 0.5}, segments=200)
    assert surfaces.projected_area_m2(sphere, [0.3, -0.5, 0.8]) == pytest.approx(math.pi * 0.25 ** 2, rel=2e-2)


def test_mesh_faces_merge_coplanar_triangles():
    """A meshed box gives 6 planes (its 12 triangles merged in pairs); a
    32-sided cylinder gives 34; areas add up to the surface area."""
    box = surfaces.mesh_faces(shapes.mesh("box", BOX))
    assert len(box) == 6
    assert sum(f.area_m2 for f in box) == pytest.approx(2 * (1.2 * 0.8 + 0.8 * 0.5 + 1.2 * 0.5))
    top = next(f for f in box if f.normal[2] > 0.99)
    np.testing.assert_allclose(top.centroid_m, [0, 0, BOX["z"] / 2], atol=1e-12)
    assert len(surfaces.mesh_faces(shapes.mesh("cylinder", {"diameter": 0.6, "height": 1.1}, segments=32))) == 34


def test_obj_round_trip_keeps_groups_vertices_and_colours(tmp_path):
    """Write two groups, read them back: same names, vertices, triangles
    and colours."""
    groups = [obj_io.ObjGroup("bus", shapes.mesh("box", BOX), (0.8, 0.1, 0.1)),
              obj_io.ObjGroup("dish", shapes.mesh("cone", {"base_diameter": 0.8, "height": 0.3}), None)]
    path = obj_io.write_obj(tmp_path / "model.obj", groups)
    read = obj_io.read_obj(path)
    assert [g.name for g in read.groups] == ["bus", "dish"]
    for written, back in zip(groups, read.groups):
        np.testing.assert_allclose(back.mesh.vertices, written.mesh.vertices, rtol=1e-8)
        np.testing.assert_array_equal(back.mesh.triangles, written.mesh.triangles)
    assert read.groups[0].color == pytest.approx((0.8, 0.1, 0.1))
    assert read.groups[1].color == pytest.approx((0.7, 0.7, 0.7))


def test_obj_reader_handles_polygons_negative_indices_units_and_y_up(tmp_path):
    """A quad written with negative indices and v/t/n corners, in mm and
    Y-up: two triangles, metres, and the file's +y becomes +z."""
    (tmp_path / "quad.obj").write_text(
        "# test\nv 0 0 0\nv 1000 0 0\nv 1000 2000 0\nv 0 2000 0\nvt 0 0\nvn 0 0 1\n"
        "g plate\nf -4/1/1 -3/1/1 -2/1/1 -1/1/1\n")
    read = obj_io.read_obj(tmp_path / "quad.obj", units="mm", up_axis="y")
    plate = read.group("plate").mesh
    assert len(plate.triangles) == 2
    assert plate.vertices[:, 2].max() == pytest.approx(2.0)  # 2000 mm along the file's +y is +z
    assert plate.vertices[:, 0].max() == pytest.approx(1.0)


@pytest.mark.parametrize("text, message", [
    ("v 0 0\n", "three numbers"),
    ("v 0 0 0\nv 1 0 0\nf 1 2\n", "three corners"),
    ("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n", "does not exist"),
    ("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 x\n", "not a vertex index"),
    ("v 0 0 nan\n", "not finite"),
    ("v 0 0 0\n", "no faces"),
])
def test_obj_reader_names_the_bad_line(tmp_path, text, message):
    """Malformed files raise ObjError with the reason (and the line)."""
    path = tmp_path / "bad.obj"
    path.write_text(text)
    with pytest.raises(obj_io.ObjError, match=message):
        obj_io.read_obj(path)


def test_obj_reader_limits_and_material_paths(tmp_path, monkeypatch):
    """Files over the size or triangle limit are refused; a material file
    in another folder is not opened."""
    path = tmp_path / "m.obj"
    path.write_text("mtllib ../secret.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nv 1 1 0\nf 1 2 3\nf 2 4 3\n")
    read = obj_io.read_obj(path)
    assert any("not in the model's folder" in w for w in read.warnings)
    monkeypatch.setattr(obj_io, "MAX_TRIANGLES", 1)
    with pytest.raises(obj_io.ObjError, match="more than 1 triangles"):
        obj_io.read_obj(path)
    monkeypatch.setattr(obj_io, "MAX_FILE_BYTES", 10)
    with pytest.raises(obj_io.ObjError, match="limit"):
        obj_io.read_obj(path)


def test_merge_keeps_every_triangle():
    """Merging meshes offsets the second mesh's indices."""
    a = shapes.mesh("box", BOX)
    b = shapes.mesh("sphere", {"diameter": 0.2})
    merged = merge([a, b])
    assert len(merged.triangles) == len(a.triangles) + len(b.triangles)
    assert merged.is_closed()
