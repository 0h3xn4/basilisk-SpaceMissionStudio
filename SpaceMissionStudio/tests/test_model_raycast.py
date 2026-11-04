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
"""Ray casting on the 3D model (model-analyses Phase A,
``model3d/raycast.py``): intersections with every primitive against
analytic distances, mesh parts against the same shapes analytically, face
sampling against the true face areas, and shaded fractions of simple
configurations against hand calculations, with their convergence."""

import math

import numpy as np
import pytest

from spacemissionstudio.model3d import shapes
from spacemissionstudio.model3d.geometry import rotation_matrix
from spacemissionstudio.model3d.raycast import Scene, ScenePart, cone_directions, face_samples

_I = np.eye(3)


def _scene(*parts):
    return Scene([ScenePart(name, shape, dims, rotation_matrix(rot), np.asarray(pos, dtype=float), **kw)
                  for name, shape, dims, pos, rot, kw in parts])


def _one(shape, dims, pos=(0, 0, 0), rot=(0, 0, 0), **kw):
    return _scene(("p", shape, dims, pos, rot, kw))


def test_rays_meet_each_primitive_where_its_surface_is():
    """Box, panel, prism, cylinder, cone and sphere: the distance along a
    ray to the true surface, against the analytic value (a curved shape is
    met on its curve, not on its drawn facets)."""
    x = [1.0, 0.0, 0.0]
    cases = [
        ("box", {"x": 1.0, "y": 1.0, "z": 1.0}, [-5, 0.3, 0.2], 4.5),  # [m] face at x = -0.5
        ("panel", {"width": 2.0, "length": 1.0, "thickness": 0.02}, [-5, 0, 0], 4.0),  # [m]
        ("prism", {"width_across_flats": 2.0, "height": 1.0}, [-5, 0, 0], 4.0),  # [m] a flat at x = -1
        ("cylinder", {"diameter": 2.0, "height": 1.0}, [-5, 0.4, 0], 5.0 - math.sqrt(1.0 - 0.16)),  # [m]
        ("sphere", {"diameter": 2.0}, [-5, 0.4, 0], 5.0 - math.sqrt(1.0 - 0.16)),  # [m]
        # base 2 m at z = -0.5, apex at +0.5: radius 0.5 m at z = 0
        ("cone", {"base_diameter": 2.0, "height": 1.0}, [-5, 0.4, 0], 5.0 - math.sqrt(0.25 - 0.16)),  # [m]
    ]
    for shape, dims, origin, expected in cases:
        distance, part = _one(shape, dims).nearest([origin], [x])
        assert distance[0] == pytest.approx(expected, abs=1e-12), shape
        assert part[0] == 0


def test_rays_that_pass_a_primitive_miss_it():
    """A ray just above a cylinder's top, beside a sphere or beside a
    cone's apex meets nothing."""
    x = [[1.0, 0.0, 0.0]]
    assert np.isinf(_one("cylinder", {"diameter": 2.0, "height": 1.0}).nearest([[-5, 0, 0.51]], x)[0][0])
    assert np.isinf(_one("sphere", {"diameter": 2.0}).nearest([[-5, 0, 1.01]], x)[0][0])
    # 0.4 m from the axis at z = 0.2: the cone's radius there is 0.3 m
    assert np.isinf(_one("cone", {"base_diameter": 2.0, "height": 1.0}).nearest([[-5, 0.4, 0.2]], x)[0][0])


def test_a_cone_is_met_on_its_apex_and_base():
    """Along the axis from above, the apex (0.5 m up); from below, the
    base plane."""
    cone = _one("cone", {"base_diameter": 2.0, "height": 1.0})
    distance, _ = cone.nearest([[0, 0, 5], [0, 0, -5]], [[0, 0, -1], [0, 0, 1]])
    assert distance == pytest.approx([4.5, 4.5])  # [m]


def test_a_placed_part_is_met_in_the_body_frame():
    """A box turned 90 deg about z and moved 3 m along +y: met where its
    placement puts it."""
    scene = _one("box", {"x": 2.0, "y": 0.5, "z": 0.5}, pos=(0, 3, 0), rot=(0, 0, 90))
    distance, _ = scene.nearest([[0, -5, 0]], [[0, 1, 0]])
    assert distance[0] == pytest.approx(7.0)  # [m] the box spans y = 2 to 4 once turned


def test_a_ray_from_inside_a_part_is_blocked_unless_the_part_is_ignored():
    """A sensor inside its own box is blocked at once by it, and sees out
    when the box is excluded."""
    scene = _scene(("bus", "box", {"x": 1.0, "y": 1.0, "z": 1.0}, (0, 0, 0), (0, 0, 0), {}))
    assert scene.nearest([[0, 0, 0]], [[0, 0, 1]])[0][0] == 0.0
    assert np.isinf(scene.nearest([[0, 0, 0]], [[0, 0, 1]], exclude=("bus",))[0][0])


def test_mesh_parts_agree_with_the_analytic_shapes():
    """2000 random rays against a box as a mesh and as a box, and against a
    finely faceted sphere mesh and the true sphere (within the faceting's
    sagitta)."""
    rng = np.random.default_rng(7)
    origins = rng.normal(size=(2000, 3)) * 3.0
    directions = rng.normal(size=(2000, 3))
    outside = ~np.all(np.abs(origins) <= 0.5, axis=1)
    box = {"x": 1.0, "y": 1.0, "z": 1.0}
    analytic = _one("box", box).nearest(origins, directions)[0][outside]
    mesh = _one("mesh", {}, mesh=shapes.mesh("box", box)).nearest(origins, directions)[0][outside]
    both_miss = np.isinf(analytic) & np.isinf(mesh)
    assert np.allclose(analytic[~both_miss], mesh[~both_miss], atol=1e-12)
    sphere_mesh = shapes.mesh("sphere", {"diameter": 2.0}, segments=256)
    r_out = np.linalg.norm(origins, axis=1) > 1.05
    true = _one("sphere", {"diameter": 2.0}).nearest(origins[r_out], directions[r_out])
    faceted = _one("mesh", {}, mesh=sphere_mesh).nearest(origins[r_out], directions[r_out])
    hit = np.isfinite(true[0]) & np.isfinite(faceted[0])
    sagitta = 1.0 - math.cos(math.pi / 128)  # [m] the faceted sphere lies inside the true one by at most this
    lengths = np.linalg.norm(directions[r_out][hit], axis=1)
    assert np.all(np.abs(true[0][hit] - faceted[0][hit]) * lengths <= sagitta * 30.0)


def test_the_nearest_part_is_reported():
    """Two boxes on one line: the nearer one's index and distance."""
    scene = _scene(("far", "box", {"x": 1, "y": 1, "z": 1}, (5, 0, 0), (0, 0, 0), {}),
                   ("near", "box", {"x": 1, "y": 1, "z": 1}, (2, 0, 0), (0, 0, 0), {}))
    distance, part = scene.nearest([[0, 0, 0]], [[1, 0, 0]])
    assert scene.names[part[0]] == "near" and distance[0] == pytest.approx(1.5)


def test_face_samples_cover_each_face_with_its_area():
    """For every shape, a face's samples add up to its true area (the
    curved strips of cylinders and cones, the sphere's cells), and their
    normals point outward."""
    dims = {"box": {"x": 1.0, "y": 2.0, "z": 3.0}, "panel": {"width": 1.0, "length": 2.0, "thickness": 0.02},
            "prism": {"width_across_flats": 2.0, "height": 1.0}, "cylinder": {"diameter": 2.0, "height": 1.0},
            "cone": {"base_diameter": 2.0, "height": 1.0}, "sphere": {"diameter": 2.0}}
    for shape, d in dims.items():
        total = 0.0
        for face in shapes.faces(shape, d):
            points, normals, weights = face_samples(shape, d, face.name, 400)
            total += weights.sum()
            assert np.all(np.einsum("ij,ij->i", normals, points) > -1e-9), (shape, face.name)
            if shape != "sphere":
                assert weights.sum() == pytest.approx(face.area_m2, rel=1e-12), (shape, face.name)
        assert total == pytest.approx(sum(f.area_m2 for f in shapes.faces(shape, d)), rel=1e-9), shape


def test_cone_directions_fill_the_cone_uniformly():
    """Every direction lies within the half-angle, and their mean cosine
    is that of a uniform cap, (1 + cos a) / 2."""
    half = math.radians(30.0)  # [rad]
    directions = cone_directions([0.0, 1.0, 0.0], half, 4000)
    cosines = directions[:, 1]
    assert cosines.min() >= math.cos(half) - 1e-12
    assert cosines.mean() == pytest.approx((1.0 + math.cos(half)) / 2.0, abs=1e-4)


def test_a_panel_shades_a_box_face_as_a_hand_calculation_gives():
    """A 1 m square box face (+z) under a 1 m x 0.5 m panel 1 m above it,
    lit from straight above: half the face is shaded. Lit at 45 deg from
    +x, the shadow slides 1 m along x, off the face."""
    scene = _scene(("bus", "box", {"x": 1.0, "y": 1.0, "z": 1.0}, (0, 0, 0), (0, 0, 0), {}),
                   ("shade", "panel", {"width": 0.5, "length": 1.0, "thickness": 0.01}, (0.25, 0, 1.5),
                    (0, 0, 0), {}))
    above = scene.face_shading("bus", "+z", [0, 0, 1], samples=4096)
    assert above.shaded_fraction == pytest.approx(0.5, abs=0.02)
    assert above.by_part == pytest.approx({"shade": above.shaded_fraction})
    slanted = scene.face_shading("bus", "+z", [1, 0, 1], samples=4096)
    assert slanted.shaded_fraction == pytest.approx(0.0, abs=1e-9)
    away = scene.face_shading("bus", "+z", [0, 0, -1])
    assert away.facing_fraction == 0.0 and away.shaded_fraction == 0.0


def test_a_shaded_fraction_converges_with_sampling():
    """A panel covering a known 0.3 of a face: the error falls as the
    samples grow, and the reported standard error bounds it."""
    scene = _scene(("bus", "box", {"x": 1.0, "y": 1.0, "z": 1.0}, (0, 0, 0), (0, 0, 0), {}),
                   ("shade", "panel", {"width": 0.3, "length": 2.0, "thickness": 0.01}, (-0.35, 0, 2.0),
                    (0, 0, 0), {}))
    errors = []
    for samples in (16, 256, 4096):
        shading = scene.face_shading("bus", "+z", [0, 0, 1], samples=samples)
        errors.append(abs(shading.shaded_fraction - 0.3))
    assert errors[-1] < errors[0] and errors[-1] < 0.01


def test_cone_blockage_of_a_panel_cutting_a_cone():
    """A sensor looking up +z with a 90 deg cone (half-angle 45 deg), and a
    large panel covering the +x half-space above it: half the cone is
    blocked, all by that panel."""
    scene = _scene(("panel", "panel", {"width": 10.0, "length": 20.0, "thickness": 0.01}, (5.0, 0, 1.0),
                    (0, 0, 0), {}))
    blocked = scene.cone_blockage([0, 0, 0], [0, 0, 1], math.radians(45.0), samples=4096)
    assert blocked.fraction == pytest.approx(0.5, abs=0.01)
    assert list(blocked.by_part) == ["panel"] and blocked.standard_error < 0.01
