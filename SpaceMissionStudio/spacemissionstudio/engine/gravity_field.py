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

"""Spherical-harmonics gravity fields of the central body
(:attr:`schema.scenario.GravityConfig.central_body_degree`): Earth's GGM03S
and Mars's GGM2B, both from Basilisk's support data.

**Reference radius (SRelD K-04).** A field's normalised coefficients
belong to the reference radius in its file header (GGM03S 6378136.3 m,
GGM2B 3397 km). Basilisk 2.12's
``SphericalHarmonicsGravityModel::initializeParameters(body)`` replaces
that radius with the body's equatorial radius (Earth 6378136.6 m, Mars
3396.19 km), which scales every degree-n term by ``(R_body/R_file)^n``:
about 1e-7 on Earth's J2, but 4.8e-4 on Mars's. So the model is built
here with each coefficient multiplied by ``(R_file/R_body)^n``, which
gives back the field the file describes when Basilisk evaluates it with
the body's radius. Basilisk itself is not changed: the model is its own
``SphericalHarmonicsGravityModel``, filled through its public fields.

The GM is left as Basilisk's (the body's), as deviation D-07 records: the
field's GM differs by 1.4e-8 (Earth) and 1.4e-6 (Mars), which on the
perturbing terms is far below everything else.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from Basilisk.simulation.gravityEffector import loadGravFromFileToList
from Basilisk.simulation.sphericalHarmonicsGravityModel import SphericalHarmonicsGravityModel
from Basilisk.utilities.supportDataTools.dataFetcher import DataFile

from . import kernels

#: Central body -> the Basilisk support-data field file it uses.
FIELD_FILES = {
    "earth": DataFile.LocalGravData.GGM03S,
    "mars barycenter": DataFile.LocalGravData.GGM2BData,
}


@dataclass(frozen=True)
class GravityField:
    """The field attached to the central body: its file, and the reference
    radius and GM in the file header."""

    path: Path
    reference_radius_m: float
    gm_m3_s2: float


def field_model(path: Path, degree: int, body_radius_m: float, body_gm_m3_s2: float):
    """``(model, field)``: Basilisk's ``SphericalHarmonicsGravityModel`` of
    ``path`` to ``degree``, with each degree-n coefficient scaled by
    ``(R_file / body_radius_m)^n`` so that evaluated with the body's radius
    it gives the file's field. The model's radius and GM are set to the
    body's, as Basilisk sets them when the simulation initialises."""
    c_bar, s_bar, gm_file, radius_file = loadGravFromFileToList(str(path), degree)
    ratio = radius_file / body_radius_m  # [-]
    model = SphericalHarmonicsGravityModel()
    model.cBar = [[value * ratio ** n for value in row] for n, row in enumerate(c_bar)]
    model.sBar = [[value * ratio ** n for value in row] for n, row in enumerate(s_bar)]
    model.maxDeg = degree
    model.radEquator = body_radius_m  # [m]
    model.muBody = body_gm_m3_s2  # [m^3/s^2]
    return model, GravityField(Path(path), radius_file, gm_file)


def attach(central_body, body_name: str, degree: int) -> GravityField:
    """Give ``central_body`` (a Basilisk ``GravBodyData``) its field to
    ``degree``; returns what was attached. ``body_name`` must be one of
    :data:`FIELD_FILES` (the schema refuses others)."""
    path = kernels.cached_path(FIELD_FILES[body_name])
    model, field = field_model(path, degree, central_body.radEquator, central_body.mu)
    central_body.gravityModel = model
    return field
