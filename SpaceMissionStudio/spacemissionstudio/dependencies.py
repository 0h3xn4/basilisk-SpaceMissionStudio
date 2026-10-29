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

"""The reused software this tool depends on, and the Basilisk version it is
qualified with (ECSS-Q-ST-80C 6.2.4, 6.2.7; decision D5, 2026-10-08).

Basilisk is existing (reused) software in the sense of ECSS-Q-ST-80C: the
tool is verified against one Basilisk release, :data:`QUALIFIED_BASILISK_
VERSION`, and the installers pin it. Another version still runs, but
:func:`basilisk_check` reports it at start-up and every run's provenance
records it. Importing this module does not import Basilisk.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from importlib import metadata
from pathlib import Path

QUALIFIED_BASILISK_VERSION = "2.12.0"

# Distribution names of the runtime dependencies, as pip knows them.
_DEPENDENCIES = ("bsk", "numpy", "sgp4", "pyerfa", "PySide6", "plotly")

# Files above this size are hashed once and their hash kept in
# :func:`hash_cache_path`, keyed by path, size and modification time:
# hashing de430.bsp (~114 MB) took 8 s on one computer, too long for every
# run. Until 2026-10-29 they were recorded by size only (transparency
# audit, Phase 2d).
_HASH_LIMIT_BYTES = 32 * 1024 * 1024  # [byte]
_large_file_hashes: dict = {}  # (path, size, mtime_ns) -> sha256, for this process


def basilisk_version() -> str | None:
    """Installed Basilisk version, or ``None`` when Basilisk is missing."""
    try:
        import Basilisk
    except ImportError:
        return None
    return str(getattr(Basilisk, "__version__", "unknown"))


def basilisk_check(version: str | None = None) -> str | None:
    """``None`` when the installed Basilisk is the qualified version,
    otherwise one line saying what differs."""
    version = basilisk_version() if version is None else version
    if version is None:
        return "Basilisk is not installed: simulations cannot run"
    if version != QUALIFIED_BASILISK_VERSION:
        return (f"Basilisk {version} is installed; SpaceMissionStudio is qualified with "
                f"{QUALIFIED_BASILISK_VERSION} -- results are not covered by its verification")
    return None


def dependency_versions() -> dict[str, str]:
    """``{distribution: version}`` of the runtime dependencies that are
    installed, plus the Python version and platform."""
    versions = {"python": platform.python_version(), "platform": f"{sys.platform} {platform.machine()}"}
    for name in _DEPENDENCIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return versions


def hash_cache_path() -> Path:
    """The file that keeps the SHA-256 of large data files between runs."""
    return Path.home() / ".cache" / "SpaceMissionStudio" / "file_hashes.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cached_sha256(path: Path, stat) -> tuple[str, bool]:
    """SHA-256 of a large file and whether it came from the cache. The
    cache trusts a file whose path, size and modification time are
    unchanged, as git's index does; any change hashes it again."""
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    if key in _large_file_hashes:
        return _large_file_hashes[key], True
    cache_file = hash_cache_path()
    name = f"{key[0]}|{key[1]}|{key[2]}"
    try:
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cached = {}
    if not isinstance(cached, dict):
        cached = {}
    if isinstance(cached.get(name), str):
        _large_file_hashes[key] = cached[name]
        return cached[name], True
    sha256 = _sha256(path)
    _large_file_hashes[key] = cached[name] = sha256
    try:  # written whole and swapped in: parallel Monte Carlo runs may write at once
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_file.with_name(f"{cache_file.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(cached, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(temporary, cache_file)
    except OSError:  # a read-only home: the hash is still recorded, only not kept
        pass
    return sha256, False


def file_record(path) -> dict[str, object]:
    """Path, size and SHA-256 of a reference data file. A file above
    32 MB is hashed once and its hash reused while its path, size and
    modification time stay the same (``sha256_cached``: true)."""
    path = Path(path)
    record: dict[str, object] = {"path": str(path)}
    try:
        stat = path.stat()
    except OSError:
        record["missing"] = True
        return record
    record["size_bytes"] = stat.st_size
    try:
        if stat.st_size <= _HASH_LIMIT_BYTES:
            record["sha256"] = _sha256(path)
        else:
            record["sha256"], record["sha256_cached"] = _cached_sha256(path, stat)
    except OSError as exc:  # a folder, or no read permission: recorded, not raised (audit L26)
        record["unreadable"] = str(exc)
    return record


def installed_file_record(path, installed_sha256: str | None, **extra) -> dict[str, object]:
    """:func:`file_record` of a file installed with a recorded SHA-256 (an
    Earth orientation or small-body kernel), hashed again now: the record
    says whether the file is still the one installed (``matches_install``).
    Until 2026-10-29 the install manifest's hash was copied without reading
    the file (transparency audit, Phase 2d)."""
    record = file_record(path)
    record.update(extra)
    if installed_sha256:
        record["installed_sha256"] = installed_sha256
        if "sha256" in record:
            record["matches_install"] = record["sha256"] == installed_sha256
    return record


def changed_since_install(data_files: dict) -> list[str]:
    """One run warning per data file that is not the one installed."""
    return [f"{name}: {Path(str(record.get('path', ''))).name} is not the file installed (its SHA-256 changed "
            "since; reinstall it in Reference data)"
            for name, record in sorted(data_files.items())
            if isinstance(record, dict) and record.get("matches_install") is False]
