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

"""Reading mass properties from a file: mass, center of mass and inertia,
as a CAD tool or a mass budget gives them.

Two formats, the same keys (all SI: kg, m, kg*m^2; body axes, measured
from body point B):

JSON::

    {"mass_kg": 152.4,
     "center_of_mass_m": [0.012, -0.004, 0.31],
     "inertia_kg_m2": [[18.2, -0.3, 0.1], [-0.3, 21.5, 0.2], [0.1, 0.2, 14.9]],
     "inertia_about": "center_of_mass",
     "products_of_inertia": "tensor"}

``inertia_kg_m2`` may also be nine numbers, row by row.

CSV, one ``quantity,value`` row each (a header row ``quantity,value`` is
allowed)::

    mass_kg,152.4
    com_x_m,0.012
    com_y_m,-0.004
    com_z_m,0.31
    Ixx,18.2
    Iyy,21.5
    Izz,14.9
    Ixy,-0.3
    Ixz,0.1
    Iyz,0.2
    inertia_about,center_of_mass
    products_of_inertia,tensor

``inertia_about``: ``center_of_mass`` (default) or ``origin`` (about B;
moved to the center of mass with the parallel-axis theorem).

``products_of_inertia``: ``tensor`` (default) when the off-diagonal values
are the tensor's, ``Ixy = -integral(x*y dm)``; ``integral`` when they are
the products themselves, ``Pxy = +integral(x*y dm)`` -- CAD tools differ,
so this has to be stated. ``integral`` values are negated.

The result is checked to be a physical inertia: symmetric, positive
principal moments, none larger than the sum of the other two.
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import List, Tuple

import numpy as np

from ..schema.scenario import ModelMassPropertiesConfig
from .model import file_sha256

MAX_FILE_BYTES = 1024 * 1024  # [byte]
INERTIA_ABOUT = ("center_of_mass", "origin")
PRODUCTS_OF_INERTIA = ("tensor", "integral")


class MassImportError(ValueError):
    """A mass-properties file that cannot be used, with the reason."""


def _number(value, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise MassImportError(f"{what} must be a number, got {value!r}") from None
    if not math.isfinite(number):
        raise MassImportError(f"{what} must be finite")
    return number


def _from_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MassImportError(f"not valid JSON ({exc})") from None
    if not isinstance(data, dict):
        raise MassImportError("the JSON must be an object with mass_kg, center_of_mass_m and inertia_kg_m2")
    missing = [k for k in ("mass_kg", "center_of_mass_m", "inertia_kg_m2") if k not in data]
    if missing:
        raise MassImportError(f"missing {', '.join(missing)}")
    com = data["center_of_mass_m"]
    if not isinstance(com, list) or len(com) != 3:
        raise MassImportError("center_of_mass_m must be [x, y, z]")
    inertia = data["inertia_kg_m2"]
    flat = [v for row in inertia for v in row] if isinstance(inertia, list) and inertia and isinstance(
        inertia[0], list) else inertia
    if not isinstance(flat, list) or len(flat) != 9:
        raise MassImportError("inertia_kg_m2 must be a 3x3 list or nine numbers")
    return {"mass_kg": data["mass_kg"], "com": com, "inertia": flat,
            "inertia_about": data.get("inertia_about", "center_of_mass"),
            "products_of_inertia": data.get("products_of_inertia", "tensor")}


_CSV_KEYS = ("mass_kg", "com_x_m", "com_y_m", "com_z_m", "Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")


def _from_csv(text: str) -> dict:
    rows = {}
    for number, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if not row or not row[0].strip() or row[0].strip().startswith("#"):
            continue
        if len(row) < 2:
            raise MassImportError(f"line {number}: expected 'quantity,value'")
        key, value = row[0].strip(), row[1].strip()
        if (key, value) == ("quantity", "value"):
            continue
        rows[key] = value
    missing = [k for k in _CSV_KEYS if k not in rows]
    if missing:
        raise MassImportError(f"missing {', '.join(missing)}")
    ixx, iyy, izz, ixy, ixz, iyz = (rows[k] for k in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"))
    return {"mass_kg": rows["mass_kg"], "com": [rows["com_x_m"], rows["com_y_m"], rows["com_z_m"]],
            "inertia": [ixx, ixy, ixz, ixy, iyy, iyz, ixz, iyz, izz],
            "inertia_about": rows.get("inertia_about", "center_of_mass"),
            "products_of_inertia": rows.get("products_of_inertia", "tensor")}


def check_inertia(inertia: np.ndarray) -> None:
    """Raise :class:`MassImportError` unless ``inertia`` (3x3) is a rigid
    body's: symmetric, positive principal moments, triangle inequality."""
    if not np.allclose(inertia, inertia.T, rtol=1e-9, atol=1e-12):
        raise MassImportError("the inertia tensor is not symmetric (Ixy must equal Iyx, and so on)")
    moments = np.linalg.eigvalsh(inertia)
    if moments[0] <= 0.0:
        raise MassImportError(f"the inertia's principal moments ({', '.join(f'{m:.6g}' for m in moments)}) "
                              "must all be positive; check the products-of-inertia sign convention")
    tolerance = 1e-9 * float(moments[-1])
    if moments[2] > moments[0] + moments[1] + tolerance:
        raise MassImportError(f"the principal moments ({', '.join(f'{m:.6g}' for m in moments)}) break the "
                              "triangle inequality: no moment can exceed the sum of the other two")


def read_mass_properties(path) -> Tuple[ModelMassPropertiesConfig, List[str]]:
    """Read ``path`` (``.json`` or ``.csv``, see the module docstring).
    Returns the values about the center of mass, with the file's name and
    SHA-256 recorded, and notes on any conversion made."""
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise MassImportError(f"{path}: cannot be read ({exc.strerror or exc})") from None
    if size > MAX_FILE_BYTES:
        raise MassImportError(f"{path}: larger than {MAX_FILE_BYTES // 1024} kB; not a mass-properties file")
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    try:
        raw = _from_json(text) if path.suffix.lower() == ".json" else _from_csv(text)
    except MassImportError as exc:
        raise MassImportError(f"{path.name}: {exc}") from None
    notes: List[str] = []
    try:
        mass = _number(raw["mass_kg"], "mass_kg")
        com = np.array([_number(v, "center of mass") for v in raw["com"]])
        inertia = np.array([_number(v, "inertia") for v in raw["inertia"]]).reshape(3, 3)
        if mass <= 0.0:
            raise MassImportError("mass_kg must be positive")
        about, products = raw["inertia_about"], raw["products_of_inertia"]
        if about not in INERTIA_ABOUT:
            raise MassImportError(f"inertia_about must be one of {INERTIA_ABOUT}, got {about!r}")
        if products not in PRODUCTS_OF_INERTIA:
            raise MassImportError(f"products_of_inertia must be one of {PRODUCTS_OF_INERTIA}, got {products!r}")
        if products == "integral":
            inertia = np.diag(np.diag(inertia)) - (inertia - np.diag(np.diag(inertia)))
            notes.append("products of inertia given as +integral(xy dm): negated to tensor form")
        if about == "origin":
            inertia = inertia - mass * (float(com @ com) * np.eye(3) - np.outer(com, com))
            notes.append("inertia given about B: moved to the center of mass")
        check_inertia(inertia)
    except MassImportError as exc:
        raise MassImportError(f"{path.name}: {exc}") from None
    config = ModelMassPropertiesConfig(mass_kg=mass, center_of_mass_b_m=[float(v) for v in com],
                                       inertia_kg_m2=[float(v) for v in inertia.reshape(9)],
                                       source_file=path.name, source_sha256=file_sha256(path))
    return config, notes
