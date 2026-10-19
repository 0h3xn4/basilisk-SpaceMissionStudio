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

"""engine.landmarks (numpy only): landmark placement, pinholeCamera's
camera conventions, the gravity gradient the filter predicts with, and the
filter itself on a cube-shaped body."""

import math

import numpy as np
import pytest

from spacemissionstudio.engine import landmarks, polyhedron

from test_polyhedron import _cube

MU = 4.463e5  # [m^3/s^2]


def test_landmarks_are_distinct_facet_centres_with_their_normals():
    """Placement is seeded, picks distinct facets and returns their
    centres and outward unit normals."""
    cube = _cube()
    points, normals = landmarks.place_landmarks(cube, 8, seed=3)
    again, _ = landmarks.place_landmarks(cube, 8, seed=3)
    assert np.array_equal(points, again) and len({tuple(p) for p in points}) == 8
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0)
    on_facet = [any(np.allclose(p, c) for c in cube.facet_centers) for p in points]
    assert all(on_facet)
    assert len(landmarks.place_landmarks(cube, 100, seed=3)[0]) == 12  # no more than the facets


def test_the_pixel_pitch_gives_the_field_of_view():
    """FOVx = 2 atan(nx w / 2 f), as pinholeCamera computes it."""
    w = landmarks.pixel_pitch_m(math.radians(30.0), 1024)
    assert 2.0 * math.atan2(1024 * w, 2.0 * landmarks.FOCAL_LENGTH_M) == pytest.approx(math.radians(30.0))


def test_pixels_follow_the_pinhole_model_and_round_away_from_zero():
    """u = f dx / (dz w); rounding is away from zero (0 gives 1), and a
    pixel's centre is half a pixel back towards the image centre."""
    dcm = np.eye(3)
    uv, d_c = landmarks.project(np.array([[10.0, -20.0, 1000.0]]), np.zeros(3), dcm, dcm, 500.0)
    assert uv[0] == pytest.approx([5.0, -10.0]) and d_c[0] == pytest.approx([10.0, -20.0, 1000.0])
    assert landmarks.round_pixels(np.array([[0.2, -0.2], [3.0, -3.7], [0.0, 2.5]])).tolist() == [
        [1.0, -1.0], [3.0, -4.0], [1.0, 3.0]]
    assert landmarks.pixel_centres(np.array([[1.0, -4.0]])).tolist() == [[0.5, -3.5]]
    assert landmarks.QUANTIZATION_SIGMA_PX == pytest.approx(0.2887, abs=1e-4)


def test_the_pixel_jacobian_matches_finite_differences():
    """d(u, v)/d r_N of the filter's update, against the projection."""
    rng = np.random.default_rng(4)
    points = rng.normal(0.0, 3e3, (5, 3))
    r = np.array([2e3, -1e3, -30e3])
    dcm_pn = landmarks.rotation_z(0.3)
    dcm_cn = landmarks.rotation_z(-0.2)
    _, d_c = landmarks.project(points, r, dcm_pn, dcm_cn, 800.0)
    jacobian = landmarks.pixel_jacobian(d_c, dcm_cn, 800.0)
    step = 0.1  # [m]
    numeric = np.column_stack([(landmarks.project(points, r + step * e, dcm_pn, dcm_cn, 800.0)[0]
                                - landmarks.project(points, r - step * e, dcm_pn, dcm_cn, 800.0)[0]).reshape(-1)
                               / (2 * step) for e in np.eye(3)])
    assert jacobian == pytest.approx(numeric, rel=1e-6, abs=1e-12)


def test_visibility_needs_front_facing_lit_landmarks_on_the_detector():
    """pinholeCamera's four rules, one landmark failing each."""
    points = np.array([[0.0, 0.0, 1000.0], [0.0, 0.0, 1000.0], [0.0, 0.0, 1000.0], [0.0, 0.0, 1000.0],
                       [0.0, 0.0, 1000.0]])
    normals = np.array([[0, 0, 1], [0, 0, -1], [0, 0, 1], [0, 0, 1], [0, 0, 1]], float)
    r_p = np.array([0.0, 0.0, 5000.0])  # the camera above the landmarks, looking down (-z)
    boresight = np.array([0.0, 0.0, -1.0])
    sun = np.array([0.0, 0.0, 1.0])
    pixels = np.array([[1.0, 1.0], [1.0, 1.0], [600.0, 1.0], [1.0, 1.0], [1.0, 1.0]])
    seen = landmarks.visible(points, normals, r_p, boresight, sun, pixels, (1024, 1024), math.radians(10.0))
    assert seen.tolist() == [True, False, False, True, True]
    low_sun = np.array([1.0, 0.0, 0.1])  # about 6 deg above the horizon
    assert not landmarks.visible(points[:1], normals[:1], r_p, boresight, low_sun, pixels[:1], (1024, 1024),
                                 math.radians(10.0))[0]
    behind = landmarks.visible(points[:1], normals[:1], r_p, -boresight, sun, pixels[:1], (1024, 1024), 0.0)
    assert not behind[0]


def test_the_gravity_gradient_is_the_fields_derivative():
    """field_and_gradient's d a / d r equals central differences of the
    acceleration, is symmetric, and has trace 0 outside the body."""
    cube = _cube()
    point = np.array([3000.0, -1500.0, 800.0])
    acceleration, gradient = cube.field_and_gradient(point, MU)
    assert acceleration == pytest.approx(cube.field(point, MU)[1])
    numeric = np.column_stack([(cube.field(point + e, MU)[1] - cube.field(point - e, MU)[1]) / 2.0
                               for e in np.eye(3)])
    assert gradient == pytest.approx(numeric, rel=1e-6, abs=1e-15)
    assert gradient == pytest.approx(gradient.T) and abs(np.trace(gradient)) < 1e-12 * np.abs(gradient).max()


def test_body_dcm_turns_about_the_pole():
    """A quarter turn of spin: the body's x axis goes to where y was."""
    dcm = landmarks.body_dcm(np.eye(3), 1e-3, 0.5 * math.pi / 1e-3)
    assert dcm @ np.array([0.0, 1.0, 0.0]) == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)


def _simulate(filter_shape: polyhedron.Polyhedron, hours: float, x0: np.ndarray, sigma_r: float):
    """Truth from the filter's own prediction (no process noise), images
    every 600 s of every landmark in front of a nadir camera; the filter
    starts ``x0 - truth`` off."""
    spin = 2.0 * math.pi / (5.27 * 3600.0)  # [rad/s]
    points, normals = landmarks.place_landmarks(filter_shape, 12, seed=1)
    truth = landmarks.LandmarkFilter(filter_shape, MU, spin, points, x0, 1.0, 1.0, 0.0, 0.3, 1000.0)
    nav = landmarks.LandmarkFilter(filter_shape, MU, spin, points, x0, sigma_r, 0.05, 1e-9, 0.2887, 1000.0)
    rng = np.random.default_rng(7)
    nav.x[:3] += rng.normal(0.0, sigma_r, 3)
    errors = []
    dcm_pn = np.eye(3)
    for _ in range(int(hours * 6)):
        dcm_cn = landmarks.nadir_dcm_CN(truth.x[:3], truth.x[3:])
        uv, d_c = landmarks.project(points, truth.x[:3], dcm_pn, dcm_cn, 1000.0)
        front = d_c[:, 2] > 0.0
        nav.update(np.nonzero(front)[0], landmarks.round_pixels(uv[front]), dcm_pn, dcm_cn)
        errors.append(np.linalg.norm(nav.x[:3] - truth.x[:3]))
        truth.propagate(600.0, dcm_pn)
        nav.propagate(600.0, dcm_pn)
        dcm_pn = landmarks.body_dcm(dcm_pn, spin, 600.0)
    return np.array(errors), nav


def test_the_filter_finds_the_orbit_from_landmark_pixels():
    """Around a 2 km cube, from 100 m off, whole-pixel landmark images
    bring the filter within a few metres in two hours, inside its 3 sigma."""
    r0 = np.array([8000.0, 0.0, 0.0])  # [m]
    x0 = np.concatenate([r0, [0.0, math.sqrt(MU / 8000.0) * 0.6, math.sqrt(MU / 8000.0) * 0.5]])
    errors, nav = _simulate(_cube(), 2.0, x0, 100.0)
    assert errors[0] < 50.0 and errors[-1] < 5.0
    assert errors[-1] < 3.0 * math.sqrt(np.trace(nav.P[:3, :3]))
