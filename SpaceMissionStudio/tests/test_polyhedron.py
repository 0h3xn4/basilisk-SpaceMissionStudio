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

"""engine.polyhedron: a shape model's geometry, inside test and
constant-density field, on a cube (exact answers) and on Basilisk's Eros
shape against Basilisk's own polyhedralGravityModel."""

from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import polyhedron

MU = 4.463e5  # [m^3/s^2] Eros (engine.small_bodies.EROS)


def _cube(half_m: float = 1000.0) -> polyhedron.Polyhedron:
    """A cube centred on the origin, facets counter-clockwise from outside."""
    corners = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float) * half_m
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    facets = []
    for a, b, c, d in quads:
        facets += [(a, b, c), (a, c, d)]
    return polyhedron.Polyhedron(corners, np.array(facets))


def _write_pds3(path: Path, shape: polyhedron.Polyhedron) -> Path:
    lines = [f"v {x / 1e3:.9f} {y / 1e3:.9f} {z / 1e3:.9f}" for x, y, z in shape.vertices]
    lines += [f"f {i} {j} {k}" for i, j, k in shape.facets]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def test_a_cube_has_its_volume_centroid_and_outward_normals():
    """A 2 km cube: 8 km^3, centred, every normal pointing away from the centre."""
    cube = _cube()
    assert cube.volume == pytest.approx(8.0e9, rel=1e-12)
    assert np.allclose(cube.centroid, 0.0, atol=1e-6)
    assert np.all(np.einsum("ij,ij->i", cube.facet_normals, cube.facet_centers) > 0.0)
    assert cube.facet_areas.sum() == pytest.approx(6 * 4.0e6, rel=1e-12)


def test_the_inside_test_sums_the_solid_angles():
    """Inside: the facets' solid angles add up to 4 pi; outside: to 0."""
    cube = _cube()
    assert cube.solid_angles([100.0, -200.0, 300.0]).sum() == pytest.approx(4.0 * np.pi, abs=1e-9)
    assert cube.solid_angles([3000.0, 0.0, 0.0]).sum() == pytest.approx(0.0, abs=1e-9)
    inside = cube.contains([[0.0, 0.0, 0.0], [999.0, 999.0, -999.0], [1001.0, 0.0, 0.0], [0.0, 5000.0, 0.0]])
    assert inside.tolist() == [True, True, False, False]


def test_far_from_the_cube_its_field_is_a_point_mass():
    """At 50 cube widths the field is mu/r^2: a cube has no quadrupole, and
    its next term is of order (half width / r)^4 = 1e-8."""
    potential, acceleration = _cube().field([1.0e5, 0.0, 0.0], MU)
    assert potential == pytest.approx(MU / 1.0e5, rel=1e-7)
    assert acceleration == pytest.approx([-MU / 1.0e10, 0.0, 0.0], rel=1e-7, abs=1e-18)


def test_the_field_is_the_potentials_gradient_and_obeys_poisson():
    """a = grad U (central differences); div a = -4 pi G rho inside the
    body and 0 outside it (Laplace)."""
    cube = _cube()
    g_rho = MU / cube.volume  # [1/s^2]
    step = 1.0  # [m]
    for point, laplacian in (([300.0, -200.0, 100.0], -4.0 * np.pi * g_rho), ([1500.0, 700.0, -400.0], 0.0)):
        point = np.asarray(point)
        _, acceleration = cube.field(point, MU)
        gradient, divergence = np.zeros(3), 0.0
        for k in range(3):
            offset = np.zeros(3)
            offset[k] = step
            gradient[k] = (cube.field(point + offset, MU)[0] - cube.field(point - offset, MU)[0]) / (2 * step)
            divergence += (cube.field(point + offset, MU)[1][k] - cube.field(point - offset, MU)[1][k]) / (2 * step)
        assert acceleration == pytest.approx(gradient, rel=1e-6)
        assert divergence == pytest.approx(laplacian, abs=1e-6 * 4.0 * np.pi * g_rho)


def test_load_reads_pds3_and_gaskell_files_in_km(tmp_path):
    """Both .tab layouts give the same shape, in metres, zero-based."""
    cube = _cube()
    pds3 = polyhedron.load(_write_pds3(tmp_path / "cube.tab", cube))
    rows = [f"{len(cube.vertices)} {len(cube.facets)}"]
    rows += [f"{n + 1} {x / 1e3} {y / 1e3} {z / 1e3}" for n, (x, y, z) in enumerate(cube.vertices)]
    rows += [f"{n + 1} {i + 1} {j + 1} {k + 1}" for n, (i, j, k) in enumerate(cube.facets)]
    (tmp_path / "gaskell.tab").write_text("\n".join(rows) + "\n", encoding="ascii")
    gaskell = polyhedron.load(tmp_path / "gaskell.tab")
    for shape in (pds3, gaskell):
        assert np.allclose(shape.vertices, cube.vertices) and (shape.facets == cube.facets).all()


def test_load_refuses_files_that_are_not_closed_outward_shapes(tmp_path):
    """An inside-out shape, an open one and a facet naming a missing
    vertex are refused, as is a file that is not a shape."""
    cube = _cube()
    with pytest.raises(polyhedron.ShapeError, match="outwards"):
        polyhedron.load(_write_pds3(tmp_path / "inverted.tab", polyhedron.Polyhedron(cube.vertices,
                                                                                      cube.facets[:, ::-1])))
    open_shape = polyhedron.load(_write_pds3(tmp_path / "open.tab", polyhedron.Polyhedron(cube.vertices,
                                                                                           cube.facets[1:])))
    with pytest.raises(polyhedron.ShapeError, match="not closed"):
        open_shape.field([5000.0, 0.0, 0.0], MU)
    bad = _write_pds3(tmp_path / "bad.tab", cube)
    bad.write_text(bad.read_text() + "f 0 1 99\n", encoding="ascii")
    with pytest.raises(polyhedron.ShapeError, match="vertex"):
        polyhedron.load(bad)
    (tmp_path / "text.tab").write_text("not a shape\n", encoding="ascii")
    with pytest.raises(polyhedron.ShapeError):
        polyhedron.load(tmp_path / "text.tab")


def _eros_shape_path():
    try:
        from spacemissionstudio.engine import small_bodies

        return small_bodies.shape_path(small_bodies.EROS)
    except ImportError:
        return None


@pytest.mark.requires_basilisk
@pytest.mark.skipif(_eros_shape_path() is None, reason="Eros shape model (eros007790.tab) not installed")
def test_the_eros_field_matches_basilisks_polyhedral_model():
    """On Basilisk's Eros shape, this module's field and potential equal
    Basilisk's polyhedralGravityModel from 1 km off the surface to 1000 km,
    and the shape's volume is NEAR's (2503 +- 25 km^3, Thomas et al. 2002)
    within 1 %."""
    from Basilisk.simulation.polyhedralGravityModel import PolyhedralGravityModel

    path = _eros_shape_path()
    shape = polyhedron.load(path)
    assert (len(shape.vertices), len(shape.facets)) == (3897, 7790)
    assert shape.volume / 1e9 == pytest.approx(2503.0, rel=0.01)
    assert np.linalg.norm(shape.centroid) < 100.0  # [m] the shape is centred on its centre of mass
    model = PolyhedralGravityModel().loadFromFile(str(path))
    model.muBody = MU
    model.initializeParameters()
    for point in ([40e3, 0.0, 0.0], [0.0, 12e3, 0.0], [0.0, 0.0, 8e3], [5e3, 3e3, 2e3], [-18e3, 2e3, 1e3], [1e6, 0.0, 0.0]):
        potential, acceleration = shape.field(point, MU)
        assert acceleration == pytest.approx(np.ravel(model.computeField(point)), rel=1e-10, abs=1e-15)
        assert potential == pytest.approx(model.computePotentialEnergy(point), rel=1e-10)
