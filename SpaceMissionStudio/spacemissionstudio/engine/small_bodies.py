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
"""Small bodies a run can orbit, and their data files. Basilisk-free.

**433 Eros** is the one small body so far:

* **Where it is:** NAIF's ``eros_1900_2100.bsp``, a JPL Horizons n-body
  ephemeris (orbit solution JPL#220, Sun-centred, 1900 to 2100), from
  NAIF's generic kernels. A SPICE kernel like the planets', so Eros is
  the run's SPICE origin as Earth is in an Earth run.
* **How it turns:** pck00010 (already in the support data): pole RA
  11.35 deg, Dec 17.22 deg, prime meridian 326.07 deg + 1639.38864745
  deg/day (a 5.27 h rotation); SPICE frame ``IAU_EROS``.
* **Its gravity:** GM 4.463e-4 km^3/s^2, the value in that kernel's
  Horizons header, and the shape model ``eros007790.tab`` (Gaskell's NEAR
  shape, 3897 vertices and 7790 facets) from Basilisk's support data, for
  Basilisk's ``polyhedralGravityModel`` at constant density.

**Offline policy:** :func:`fetch` is the only network access, and only
the user starts it (the data panel or ``spacemissionstudio small-bodies
--fetch``); :func:`import_file` installs a copy from disk. The kernel is
checked against the size and SHA-256 recorded here before it is used.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_DAF_SPK_MAGIC = b"DAF/SPK "
_MANIFEST = "manifest.json"
_MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024  # [byte]

DEFAULT_DIR = Path.home() / ".cache" / "SpaceMissionStudio" / "small_bodies"
# Filled by the .deb/Windows installers for every user of the install.
SYSTEM_DIR = Path(sys.prefix) / "share" / "spacemissionstudio" / "small_bodies"


class SmallBodyError(Exception):
    """A download, import or file check failed; carries the reason."""


@dataclass(frozen=True)
class SmallBody:
    name: str  # the scenario's gravity.central_body value
    title: str
    naif_id: int
    frame: str  # SPICE body-fixed frame
    gm_m3_s2: float  # [m^3/s^2]
    mean_radius_m: float  # [m] for display only; the shape decides impacts
    spk_name: str
    spk_url: str
    spk_size_bytes: int  # [byte]
    spk_sha256: str
    spk_covers: str  # the kernel's span, ISO dates
    shape_data_file: str  # Basilisk dataFetcher name, DataFile.LocalGravData.<this>
    sources: str


EROS = SmallBody(
    name="eros",
    title="433 Eros",
    naif_id=2000433,
    frame="IAU_EROS",
    gm_m3_s2=4.463e-4 * 1e9,  # [m^3/s^2] Horizons header of eros_1900_2100.bsp (4.463e-4 km^3/s^2)
    mean_radius_m=8.42e3,  # [m] Horizons header of eros_1900_2100.bsp (RAD = 8.42 km)
    spk_name="eros_1900_2100.bsp",
    spk_url="https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/asteroids/a_old_versions/eros_1900_2100.bsp",
    spk_size_bytes=4589568,  # [byte]
    spk_sha256="1389946d8f1923b9ede522db531c768d93eb0b2403b1e03736a7e6f81f701537",
    spk_covers="1900-01-01/2100-01-01",
    shape_data_file="eros007790",
    sources=("Ephemeris: JPL Horizons (orbit JPL#220) via NAIF generic kernels; rotation: pck00010; "
             "shape: Gaskell NEAR model eros007790.tab (Basilisk support data); GM: Horizons"),
)

BODIES: Dict[str, SmallBody] = {EROS.name: EROS}


@dataclass
class InstalledKernel:
    body: str
    path: str
    source: str  # URL or the imported file's original path
    size_bytes: int  # [byte]
    sha256: str
    installed_utc: str


def body(name: str) -> Optional[SmallBody]:
    return BODIES.get(name)


def covers(small_body: SmallBody, start: datetime, end: datetime) -> bool:
    """The kernel covers ``start`` to ``end`` (naive UTC)."""
    first, last = (datetime.fromisoformat(part) for part in small_body.spk_covers.split("/"))
    return first <= start and end <= last


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(small_body: SmallBody, path: Path) -> None:
    with open(path, "rb") as handle:
        if handle.read(len(_DAF_SPK_MAGIC)) != _DAF_SPK_MAGIC:
            raise SmallBodyError(f"{path.name} is not a SPICE SPK kernel (no DAF/SPK header)")
    size = path.stat().st_size
    if size != small_body.spk_size_bytes:
        raise SmallBodyError(f"{path.name} has {size} bytes, {small_body.spk_name} has "
                             f"{small_body.spk_size_bytes}")
    if _sha256(path) != small_body.spk_sha256:
        raise SmallBodyError(f"{path.name} is not NAIF's {small_body.spk_name} (its SHA-256 differs)")


def _entries(directory: Path) -> List[dict]:
    try:
        entries = json.loads((directory / _MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return entries if isinstance(entries, list) else []


def installed(name: str, directory: Optional[Path] = None) -> Optional[InstalledKernel]:
    """The installed kernel of body ``name``, if its file is still there
    with the size it was installed with. Without ``directory``: the user's
    files, else the install-wide ones."""
    directories = [Path(directory)] if directory is not None else [DEFAULT_DIR, SYSTEM_DIR]
    for folder in directories:
        for entry in _entries(folder):
            try:
                kernel = InstalledKernel(**{key: entry[key] for key in InstalledKernel.__dataclass_fields__})
            except (KeyError, TypeError):
                continue
            path = Path(kernel.path)
            if kernel.body == name and path.is_file() and path.stat().st_size == kernel.size_bytes:
                return kernel
    return None


def _install(small_body: SmallBody, staged: Path, source: str, directory: Path) -> InstalledKernel:
    _check(small_body, staged)
    destination = directory / small_body.spk_name
    shutil.move(str(staged), str(destination))
    kernel = InstalledKernel(small_body.name, str(destination), source, destination.stat().st_size,
                             _sha256(destination),
                             datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    entries = [entry for entry in _entries(directory) if entry.get("body") != small_body.name]
    (directory / _MANIFEST).write_text(json.dumps(entries + [asdict(kernel)], indent=2), encoding="utf-8")
    return kernel


def fetch(name: str = EROS.name, directory: Optional[Path] = None, timeout_s: float = 300.0) -> InstalledKernel:
    """Download body ``name``'s SPK from NAIF, check it and install it.
    **Network access: only call after the user agreed.** The shape file
    comes with Basilisk's support data (:func:`fetch_shape`)."""
    small_body = BODIES[name]
    directory = Path(directory) if directory else DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    part = directory / (small_body.spk_name + ".part")
    request = urllib.request.Request(small_body.spk_url, headers={"User-Agent": "SpaceMissionStudio"})  # noqa: S310 -- constant https NAIF URL
    try:
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 -- constant https NAIF URL
                data = response.read(_MAX_DOWNLOAD_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SmallBodyError(f"could not fetch {small_body.spk_url}: {exc}") from exc
        if len(data) > _MAX_DOWNLOAD_BYTES:
            raise SmallBodyError(f"{small_body.spk_url} is larger than {_MAX_DOWNLOAD_BYTES} bytes")
        part.write_bytes(data)
        return _install(small_body, part, small_body.spk_url, directory)
    finally:
        if part.exists():
            part.unlink()


def import_file(path, name: str = EROS.name, directory: Optional[Path] = None) -> InstalledKernel:
    """Install body ``name``'s SPK from a copy on disk (e.g. removable media)."""
    small_body = BODIES[name]
    source = Path(path)
    directory = Path(directory) if directory else DEFAULT_DIR
    part = directory / (small_body.spk_name + ".part")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, part)
        return _install(small_body, part, str(source), directory)
    except OSError as exc:
        raise SmallBodyError(f"could not import {source.name}: {exc}") from exc
    finally:
        if part.exists():
            part.unlink()


def shape_data_file(small_body: SmallBody):
    """Basilisk's ``DataFile`` entry of the body's shape."""
    from Basilisk.utilities.supportDataTools.dataFetcher import DataFile

    return getattr(DataFile.LocalGravData, small_body.shape_data_file)


def fetch_shape(small_body: SmallBody = EROS) -> Path:
    """Fetch the shape file into Basilisk's support-data cache (Basilisk's
    own checksum). **Network access: only call after the user agreed.**"""
    from . import kernels

    statuses = kernels.ensure_kernels([shape_data_file(small_body)])
    if not statuses[0].available:
        raise SmallBodyError(f"could not fetch the shape of {small_body.title}: {statuses[0].error}")
    return Path(statuses[0].path)


def shape_path(small_body: SmallBody) -> Optional[Path]:
    """The cached shape file, or None (never downloads)."""
    from . import kernels

    status = kernels.cached_statuses([shape_data_file(small_body)])[0]
    return Path(status.path) if status.available else None
