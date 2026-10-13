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

"""The flat plates (facets) drag and solar radiation pressure act on,
taken from a model's outer faces.

A shape's faces come from :func:`.shapes.faces`, placed in the body
frame. An imported mesh has no named faces: its triangles are grouped into
plates by plane, each group one facet with the summed area, the
area-weighted centroid and the area-weighted mean normal. Triangles share a
group when their unit normals round to the same multiple of
``NORMAL_STEP`` per component (about 0.6 deg) and their planes' distances
from the origin to the same multiple of ``PLANE_STEP_M``. A curved
surface therefore gives one plate per flat triangle strip: an imported
cylinder of 32 sides gives 34 plates.

Basilisk's facet effectors treat every plate as exposed whenever it faces
the flow or the Sun: one part shading another is not modelled. Faces that
touch another part (a box mounted flat on the bus) can be left out per
part (``excluded_faces``).
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from .geometry import Mesh, triangle_areas_and_normals
from .shapes import Face

NORMAL_STEP = 0.01  # [-] per unit-normal component
PLANE_STEP_M = 1.0e-3  # [m]
MAX_FACETS = 200


def placed_faces(local_faces: Sequence[Face], rotation: np.ndarray, position_m) -> List[Face]:
    """Local faces moved into the body frame."""
    r = np.asarray(rotation, dtype=float)
    p = np.asarray(position_m, dtype=float)
    return [Face(f.name, f.group, f.area_m2, r @ f.normal, r @ f.centroid_m + p) for f in local_faces]


def mesh_faces(mesh: Mesh) -> List[Face]:
    """A mesh's triangles grouped into plane faces (see the module
    docstring), largest first."""
    areas, normals, centroids = triangle_areas_and_normals(mesh)
    keep = areas > 0.0
    areas, normals, centroids = areas[keep], normals[keep], centroids[keep]
    if len(areas) == 0:
        return []
    offsets = np.einsum("mi,mi->m", normals, centroids)
    keys = np.column_stack([np.round(normals / NORMAL_STEP), np.round(offsets / PLANE_STEP_M)]).astype(np.int64)
    _, group_of = np.unique(keys, axis=0, return_inverse=True)
    group_of = group_of.reshape(-1)
    count = int(group_of.max()) + 1
    area = np.bincount(group_of, weights=areas, minlength=count)
    moment = np.column_stack([np.bincount(group_of, weights=areas * centroids[:, k], minlength=count) for k in range(3)])
    normal_sum = np.column_stack([np.bincount(group_of, weights=areas * normals[:, k], minlength=count)
                                  for k in range(3)])
    order = np.argsort(-area, kind="stable")
    return [Face(f"plane {rank + 1}", "mesh", float(area[g]), normal_sum[g] / np.linalg.norm(normal_sum[g]),
                 moment[g] / area[g]) for rank, g in enumerate(order)]


def projected_area_m2(faces: Sequence[Face], direction) -> float:
    """The area the faces present to a flow (or light) arriving against
    ``direction``: the sum of ``A * cos`` over faces turned toward it.
    ``direction`` is where the viewer stands, e.g. ``[1, 0, 0]`` for the
    view from +x."""
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    return float(sum(f.area_m2 * max(0.0, float(f.normal @ d)) for f in faces))
