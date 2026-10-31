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

"""IERS-based Earth orientation (ECSS-E-ST-10-09C 5.4.9f; ECSS-E-ST-10-04C
4.2.1c, 4.2.2b; remediation R04). Basilisk-free.

With these files installed, the Earth-fixed frame of a run is **ITRF93**
(SPICE's built-in frame, from NAIF's binary Earth PCKs built from the JPL
EOP series: IAU 1976 precession, IAU 1980 nutation with the IERS nutation
corrections, true sidereal time from UT1, polar motion). Without them it
stays ``IAU_EARTH`` (pck00010: a rotation model without polar motion, UT1
or nutation), and the run says so.

Two NAIF files are used, loaded in this order so the second takes
precedence where both cover a time:

* ``earth_<...>_combined.bpc`` -- 1962 to ~2126: observed EOP to its "last
  datum", then NAIF's long-term prediction (low accuracy, NAIF estimates
  5-6 mrad, except about ten weeks after the last datum).
* ``earth_latest_high_prec.bpc`` -- 2000 to about three months after its
  last datum, accuracy "several microradians" (NAIF).

**Offline policy:** :func:`fetch` is the only network access, and only the
user starts it (startup prompt or ``spacemissionstudio earth-orientation --fetch``); files
can also be imported from disk (:func:`import_files`). Each install keeps
the previous files for :func:`rollback` and writes a manifest with the
source, size, SHA-256 and the EOP's last datum.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, UTC
from pathlib import Path
from collections.abc import Iterable

from .findings import Finding

NAIF_PCK_URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/"
HIGH_PRECISION_NAME = "earth_latest_high_prec.bpc"
_COMBINED_PATTERN = re.compile(r"earth_\d{4}_\d{6}_\d{4}_combined\.bpc")
_DAF_PCK_MAGIC = b"DAF/PCK "
_MAX_DOWNLOAD_BYTES = 128 * 1024 * 1024  # [byte]
_MANIFEST = "manifest.json"
# NAIF: data "about 10 weeks immediately following the epoch of the last
# datum" stay accurate to roughly 3 microradians.
HIGH_ACCURACY_AFTER_LAST_DATUM = timedelta(weeks=10)
EARTH_FIXED_FRAME = "ITRF93"
FALLBACK_EARTH_FRAME = "IAU_EARTH"

DEFAULT_DIR = Path.home() / ".cache" / "SpaceMissionStudio" / "earth_orientation"
# Filled by the .deb/Windows installers for every user of the install;
# used when the user's own DEFAULT_DIR has nothing installed.
SYSTEM_DIR = Path(sys.prefix) / "share" / "spacemissionstudio" / "earth_orientation"


class EarthOrientationError(Exception):
    """A download, import or file check failed; carries the reason."""


@dataclass
class EOPKernel:
    """One installed Earth PCK."""

    role: str  # "combined" or "high_precision" (load order)
    path: str
    source: str  # URL or the imported file's original path
    size_bytes: int
    sha256: str
    installed_utc: str
    last_datum_utc: str | None  # from the NAIF comment file, ISO 8601

    @property
    def high_accuracy_until(self) -> datetime | None:
        if not self.last_datum_utc:
            return None
        return datetime.fromisoformat(self.last_datum_utc) + HIGH_ACCURACY_AFTER_LAST_DATUM


def _role(filename: str) -> str:
    return "combined" if "combined" in filename else "high_precision"


def parse_last_datum(comment: str) -> datetime | None:
    """'UTC Epoch of last datum:   2026 OCT 07 00:00:00.000 UTC' -> datetime."""
    match = re.search(r"UTC Epoch of last datum:\s+(\d{4} [A-Z]{3} \d{2} \d{2}:\d{2}:\d{2})", comment)
    if not match:
        return None
    return datetime.strptime(match.group(1).title(), "%Y %b %d %H:%M:%S")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_pck(path: Path) -> None:
    with open(path, "rb") as f:
        if f.read(len(_DAF_PCK_MAGIC)) != _DAF_PCK_MAGIC:
            raise EarthOrientationError(f"{path.name} is not a binary PCK (no DAF/PCK header)")


def _manifest_path(directory: Path) -> Path:
    return directory / _MANIFEST


def installed(directory: Path | None = None) -> list[EOPKernel]:
    """Installed kernels in load order (combined first); files that are
    missing or changed size since installation are left out. Without
    ``directory``: the user's files, else the install-wide ones."""
    if directory is None:
        return _installed_in(DEFAULT_DIR) or _installed_in(SYSTEM_DIR)
    return _installed_in(Path(directory))


def _installed_in(directory: Path) -> list[EOPKernel]:
    try:
        entries = json.loads(_manifest_path(directory).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    # A key this version does not know (a newer version's manifest) is
    # ignored, and a broken entry skipped: either used to stop every build
    # with a TypeError (audit L19).
    known = {f.name for f in dataclasses.fields(EOPKernel)}
    kernels = []
    for entry in entries if isinstance(entries, list) else []:
        try:
            kernel = EOPKernel(**{key: value for key, value in entry.items() if key in known})
        except (TypeError, AttributeError):
            continue
        path = Path(kernel.path)
        if path.is_file() and path.stat().st_size == kernel.size_bytes:
            kernels.append(kernel)
    return sorted(kernels, key=lambda k: 0 if k.role == "combined" else 1)


def _install(directory: Path, sources: Iterable[tuple]) -> list[EOPKernel]:
    """``sources``: (filename, bpc_bytes_path, comment_text, source). Moves
    the current files to ``previous/`` and installs the new ones."""
    directory.mkdir(parents=True, exist_ok=True)
    previous = directory / "previous"
    staged = list(sources)
    for _name, staged_path, _comment, _source in staged:
        _check_pck(staged_path)
    if any(directory.glob("*.bpc")):
        if previous.exists():
            shutil.rmtree(previous)
        previous.mkdir()
        for item in list(directory.glob("*.bpc")) + list(directory.glob("*.cmt")) + [_manifest_path(directory)]:
            if item.exists():
                shutil.move(str(item), str(previous / item.name))
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    kernels = []
    for name, staged_path, comment, source in staged:
        dest = directory / name
        shutil.move(str(staged_path), str(dest))
        if comment:
            dest.with_suffix(".cmt").write_text(comment, encoding="utf-8")
        last = parse_last_datum(comment or "")
        kernels.append(EOPKernel(role=_role(name), path=str(dest), source=source, size_bytes=dest.stat().st_size,
                                 sha256=_sha256(dest), installed_utc=now,
                                 last_datum_utc=last.isoformat() if last else None))
    _manifest_path(directory).write_text(json.dumps([asdict(k) for k in kernels], indent=2), encoding="utf-8")
    return installed(directory)


def _get(url: str, timeout_s: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "SpaceMissionStudio"})  # noqa: S310 -- NAIF_PCK_URL + a name matched by a fixed pattern
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 -- constant https NAIF URL
            data = response.read(_MAX_DOWNLOAD_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EarthOrientationError(f"could not fetch {url}: {exc}") from exc
    if len(data) > _MAX_DOWNLOAD_BYTES:
        raise EarthOrientationError(f"{url} is larger than {_MAX_DOWNLOAD_BYTES} bytes")
    return data


def available_files(timeout_s: float = 60.0) -> list[str]:
    """Names of the current NAIF files this module would download."""
    listing = _get(NAIF_PCK_URL, timeout_s).decode("utf-8", "replace")
    combined = sorted(set(_COMBINED_PATTERN.findall(listing)))
    names = combined[-1:] + ([HIGH_PRECISION_NAME] if HIGH_PRECISION_NAME in listing else [])
    if not names:
        raise EarthOrientationError(f"no Earth PCK found at {NAIF_PCK_URL}")
    return names


def fetch(directory: Path | None = None, timeout_s: float = 300.0) -> list[EOPKernel]:
    """Download the current NAIF Earth PCKs (with their comment files) and
    install them. **Network access: only call after the user agreed.**"""
    directory = Path(directory) if directory else DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    staged = []
    # The download loop is inside the try: a download that fails part way
    # left the .part files of the ones before it (audit L19).
    try:
        for name in available_files(timeout_s):
            url = NAIF_PCK_URL + name
            part = directory / (name + ".part")
            staged.append((name, part, "", url))
            part.write_bytes(_get(url, timeout_s))
            comment = _get(NAIF_PCK_URL + name.replace(".bpc", ".cmt"), timeout_s).decode("utf-8", "replace")
            staged[-1] = (name, part, comment, url)
        return _install(directory, staged)
    finally:
        for _name, part, _comment, _url in staged:
            if part.exists():
                part.unlink()


def import_files(paths: Iterable, directory: Path | None = None) -> list[EOPKernel]:
    """Install Earth PCKs from disk (e.g. removable media); a ``.cmt`` next
    to a ``.bpc`` is read for the last datum."""
    directory = Path(directory) if directory else DEFAULT_DIR
    staged = []
    # A missing or unreadable file is an EarthOrientationError, and no
    # .part copy is left behind (audit M12), as in fetch().
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for path in map(Path, paths):
            if path.suffix != ".bpc":
                raise EarthOrientationError(f"{path.name}: expected a .bpc binary PCK")
            part = directory / (path.name + ".part")
            staged.append((path.name, part, "", str(path)))
            shutil.copyfile(path, part)
            comment_file = path.with_suffix(".cmt")
            comment = comment_file.read_text(encoding="utf-8", errors="replace") if comment_file.exists() else ""
            staged[-1] = (path.name, part, comment, str(path))
        return _install(directory, staged)
    except OSError as exc:
        raise EarthOrientationError(f"could not import the Earth orientation files: {exc}") from exc
    finally:
        for _name, part, _comment, _url in staged:
            if part.exists():
                part.unlink()


def rollback(directory: Path | None = None) -> list[EOPKernel]:
    """Restore the files the last install replaced."""
    directory = Path(directory) if directory else DEFAULT_DIR
    previous = directory / "previous"
    if not _manifest_path(previous).exists():
        raise EarthOrientationError("no previous Earth orientation files to restore")
    for item in list(directory.glob("*.bpc")) + list(directory.glob("*.cmt")) + [_manifest_path(directory)]:
        if item.exists():
            item.unlink()
    entries = json.loads(_manifest_path(previous).read_text(encoding="utf-8"))
    for item in previous.iterdir():
        shutil.move(str(item), str(directory / item.name))
    for entry in entries:
        entry["path"] = str(directory / Path(entry["path"]).name)
    _manifest_path(directory).write_text(json.dumps(entries, indent=2), encoding="utf-8")
    previous.rmdir()
    return installed(directory)


_DAF_RECORD_BYTES = 1024  # [byte]
_J2000_UTC = datetime(2000, 1, 1, 11, 58, 55, 816000)  # 2000-01-01 12:00 TDB in UTC (TDB - UTC = 64.184 s then)


def pck_coverage(path) -> tuple[datetime, datetime] | None:
    """The first and last time [naive UTC] a binary PCK's segments cover,
    read from its DAF summary records; None when the file is not a
    readable DAF/PCK (too short, a summary pointing past the end of the
    file). Times are to within a minute (TDB taken as UTC + 64.184 s,
    as at J2000), plenty for checking a run's span. Reads only the file
    and summary records, once per file version."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return _pck_coverage(str(path), stat.st_size, stat.st_mtime_ns)


@functools.lru_cache(maxsize=16)
def _pck_coverage(path: str, size_bytes: int, _mtime_ns: int) -> tuple[datetime, datetime] | None:
    try:
        with open(path, "rb") as f:
            head = f.read(_DAF_RECORD_BYTES)
            if len(head) < _DAF_RECORD_BYTES or not head.startswith(_DAF_PCK_MAGIC):
                return None
            endian = {b"LTL-IEEE": "<", b"BIG-IEEE": ">"}.get(head[88:96])
            if endian is None:
                return None
            nd, ni = struct.unpack(endian + "ii", head[8:16])
            (record,) = struct.unpack(endian + "i", head[76:80])
            if nd != 2 or ni != 5:  # a PCK's summaries: two times, five integers
                return None
            starts, ends, seen = [], [], set()
            while record > 0 and record not in seen:
                seen.add(record)
                f.seek((record - 1) * _DAF_RECORD_BYTES)
                block = f.read(_DAF_RECORD_BYTES)
                if len(block) < _DAF_RECORD_BYTES:
                    return None
                following, _previous, count = struct.unpack(endian + "3d", block[:24])
                if not 0 <= count <= (_DAF_RECORD_BYTES - 24) // 40:
                    return None
                for k in range(int(count)):
                    at = 24 + k * 40  # 5 doubles per summary: 2 times, then 5 integers in 3 doubles
                    begin_et, end_et = struct.unpack(endian + "2d", block[at:at + 16])
                    _body, _frame, _kind, first, last = struct.unpack(endian + "5i", block[at + 16:at + 36])
                    if not 0 < first <= last <= size_bytes // 8:
                        return None  # the segment's data lies past the end of the file (a truncated download)
                    starts.append(begin_et)
                    ends.append(end_et)
                record = int(following)
    except (OSError, struct.error, ValueError, OverflowError):
        return None
    if not starts:
        return None
    return _J2000_UTC + timedelta(seconds=min(starts)), _J2000_UTC + timedelta(seconds=max(ends))


def covered_until(kernels: list[EOPKernel], start_utc: datetime) -> datetime | None:
    """How far [naive UTC] ``kernels`` cover without a gap from
    ``start_utc``; None when they do not cover ``start_utc`` or one of
    them cannot be read."""
    spans = []
    for kernel in kernels:
        span = pck_coverage(kernel.path)
        if span is None:
            return None
        spans.append(span)
    reached = None  # [UTC] how far the spans reach, once one covers start_utc
    for first, last in sorted(span for span in spans if span[1] >= start_utc):
        if first > (start_utc if reached is None else reached):
            break  # start_utc itself not covered, or a gap
        reached = last if reached is None else max(reached, last)
    return reached


def covering(kernels: list[EOPKernel], start_utc: datetime, end_utc: datetime) -> list[EOPKernel]:
    """``kernels`` if together they cover ``start_utc`` to ``end_utc``
    (naive UTC) and each can be read, else []: a run outside every
    loaded Earth PCK made SPICE stop the whole process (audit of
    2026-10-27, R1)."""
    until = covered_until(kernels, start_utc)
    return list(kernels) if until is not None and until >= end_utc else []


def coverage_text(kernels: list[EOPKernel]) -> str:
    """'1962-01-20 to 2126-08-06', the span the kernels cover, or why not."""
    spans = [pck_coverage(k.path) for k in kernels]
    if not spans or any(span is None for span in spans):
        return "a file that cannot be read"
    return f"{min(s[0] for s in spans):%Y-%m-%d} to {max(s[1] for s in spans):%Y-%m-%d}"


def high_accuracy_until(kernels: list[EOPKernel]) -> datetime | None:
    """End of the high-accuracy span of the installed files."""
    dates = [k.high_accuracy_until for k in kernels if k.high_accuracy_until is not None]
    return max(dates) if dates else None


def notes(start_utc: datetime, end_utc: datetime, kernels: list[EOPKernel] | None = None) -> list[str]:
    """Short lines on the Earth orientation a run from ``start_utc`` to
    ``end_utc`` gets (naive UTC datetimes)."""
    kernels = installed() if kernels is None else kernels
    if not kernels:
        return [Finding("Earth orientation: IAU rotation model, no IERS data installed", "earth_orientation.none")]
    until = high_accuracy_until(kernels)
    if until is not None and end_utc > until:
        when = "the whole run" if start_utc >= until else f"after {until:%Y-%m-%d}"
        return [Finding(f"Earth orientation: {EARTH_FIXED_FRAME}, predicted (low accuracy) for {when}",
                        "earth_orientation.predicted", actual=f"run to {end_utc:%Y-%m-%d}",
                        limit=f"high accuracy to {until:%Y-%m-%d}")]
    return []
