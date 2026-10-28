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
"""Build the private Python that the .deb and the Windows setup program ship.

Unpacks a pinned, relocatable CPython (python-build-standalone) into
``--dest``, installs Basilisk and SpaceMissionStudio into it at the tested
versions (``constraints.txt``) and adds the reference data runs read:

* Basilisk's support data (SPICE kernels, gravity fields, the magnetic
  field model, albedo maps: ``kernels.ALL_SUPPORT_DATA_FILES``), fetched
  with Basilisk's own checked fetch into ``site-packages/supportData``,
  the folder Basilisk's ``dataFetcher`` reads before its download cache;
* the IERS-based Earth orientation files (NAIF ITRF93 PCKs) in
  ``earth_orientation.SYSTEM_DIR``, which every user of the install reads.

The installers then copy that folder as it is: installing needs no Python
on the machine and no internet.

Run it on the platform the installer is for, since pip installs that
platform's binary wheels::

    python packaging/bundle_python.py --platform linux --dest build/python \
        --wheel dist/spacemissionstudio-1.1.0-py3-none-any.whl

The archive is downloaded once into ``--cache`` and always checked against
its pinned SHA-256; ``--archive`` uses a file already on disk instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

#: python-build-standalone release 20261013, CPython 3.14.8, the
#: "install_only_stripped" builds (relocatable, debug symbols removed). The
#: digests are those the project publishes for these files, in the
#: release's SHA256SUMS.
PYTHON_BUILDS = {
    "linux": (
        "https://github.com/astral-sh/python-build-standalone/releases/download/20261013/"
        "cpython-3.14.8%2B20261013-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
        "d8faa1b588506b9e3e5a3f57807bb056d534a1641a6b10d15b6ea3f0b413b960",
    ),
    "windows": (
        "https://github.com/astral-sh/python-build-standalone/releases/download/20261013/"
        "cpython-3.14.8%2B20261013-x86_64-pc-windows-msvc-install_only_stripped.tar.gz",
        "dce851f280b986764037bd952d40819e94ccceb08ac914004123f43ce17f4095",
    ),
}

#: The Basilisk the installers ship: the qualified version
#: (spacemissionstudio.dependencies.QUALIFIED_BASILISK_VERSION).
BASILISK_REQUIREMENT = "bsk[all]==2.12.0"

#: Written into the bundled Python: what it is and what was installed.
MANIFEST_NAME = "SPACEMISSIONSTUDIO_RUNTIME.json"

_PACKAGING = Path(__file__).resolve().parent


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_archive(platform: str, cache: Path, archive: Path | None = None) -> Path:
    """The platform's CPython archive, checked against its pinned SHA-256."""
    url, expected = PYTHON_BUILDS[platform]
    if archive is None:
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / url.rsplit("/", 1)[1].replace("%2B", "+")
        if not archive.is_file() or sha256_of(archive) != expected:
            print(f"Downloading {url} ...", flush=True)
            partial = archive.with_suffix(archive.suffix + ".part")
            with urllib.request.urlopen(url, timeout=300) as response, partial.open("wb") as out:  # noqa: S310 (pinned https URL)
                shutil.copyfileobj(response, out)
            partial.replace(archive)
    actual = sha256_of(archive)
    if actual != expected:
        raise SystemExit(f"{archive}: SHA-256 {actual}, expected {expected}")
    return archive


def unpack(archive: Path, dest: Path) -> None:
    """Unpack the archive's top folder ``python/`` as ``dest``."""
    if dest.exists():
        raise SystemExit(f"{dest} exists; remove it first")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as scratch, tarfile.open(archive) as tar:
        tar.extractall(scratch, filter="data")
        shutil.move(str(Path(scratch) / "python"), str(dest))


def interpreter(dest: Path, platform: str) -> Path:
    return dest / ("python.exe" if platform == "windows" else "bin/python3")


def pip_install(python: Path, constraints: Path, requirement: str) -> None:
    """Install into the bundled Python; -I keeps any user site-packages out."""
    env = dict(os.environ, PYTHONNOUSERSITE="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
               PIP_ROOT_USER_ACTION="ignore")
    subprocess.run([str(python), "-I", "-m", "pip", "install", "--quiet", "--no-warn-script-location",  # noqa: S603
                    "-c", str(constraints), requirement], check=True, env=env)


def run_python(python: Path, code: str, env: dict | None = None) -> str:
    """Run ``code`` in the bundled Python, isolated from this checkout."""
    return subprocess.run([str(python), "-I", "-c", code],  # noqa: S603 -- no shell
                          check=True, capture_output=True, text=True, env=dict(os.environ, **(env or {}))).stdout


def make_readable(folder: Path) -> None:
    """World-readable files and folders: pooch writes its files 0600, and
    the .deb installs under /opt for every user."""
    for path in [folder, *folder.rglob("*")]:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))


def add_support_data(python: Path, dest: Path) -> list:
    """Fetch the support data and the Earth orientation files into the
    bundled Python; return their records for the manifest."""
    with tempfile.TemporaryDirectory() as scratch:
        # Basilisk's own fetch (registry checksums) into an empty cache,
        # then moved to the folder dataFetcher.find_local_support_data()
        # finds: a "supportData" folder in a parent of the Basilisk package.
        site = Path(run_python(python, _SUPPORT_DATA_FETCH, {"BSK_SUPPORT_DATA_CACHE": scratch}).strip())
        target = site / "supportData"
        shutil.move(str(Path(scratch) / "supportData"), str(target))
    make_readable(target)
    eop_dir = Path(run_python(python, _EOP_FETCH).strip())
    make_readable(eop_dir)
    return [{"path": path.relative_to(dest).as_posix(),
             "size_bytes": path.stat().st_size, "sha256": sha256_of(path)}
            for folder in (target, eop_dir) for path in sorted(folder.rglob("*")) if path.is_file()]


_SUPPORT_DATA_FETCH = """
from pathlib import Path
from Basilisk.utilities.supportDataTools import dataFetcher
from spacemissionstudio.engine import kernels
failed = [s for s in kernels.ensure_kernels() if not s.available]
if failed:
    raise SystemExit("support data not fetched: " + "; ".join(f"{s.filename}: {s.error}" for s in failed))
print(Path(dataFetcher.__file__).resolve().parents[3])
"""

_EOP_FETCH = """
from spacemissionstudio.engine import earth_orientation
earth_orientation.fetch(earth_orientation.SYSTEM_DIR)
print(earth_orientation.SYSTEM_DIR)
"""

#: Run with an empty download cache and no network: every support-data file
#: and the Earth orientation files must come from the bundle.
_OFFLINE_CHECK = """
import socket
def _refuse(*args, **kwargs):
    raise OSError("network access during the bundle check")
socket.socket.connect = _refuse
socket.create_connection = _refuse
from pathlib import Path
from Basilisk.utilities.supportDataTools import dataFetcher
from spacemissionstudio.engine import earth_orientation, kernels
local = Path(dataFetcher.LOCAL_SUPPORT)
for data_file in kernels.ALL_SUPPORT_DATA_FILES:
    assert local in kernels.cached_path(data_file).parents, data_file
assert earth_orientation.installed(earth_orientation.SYSTEM_DIR), "no Earth orientation files"
"""


def recompile(python: Path, dest: Path, prefix: str) -> None:
    """Rewrite every module's bytecode as if compiled at ``prefix``, where
    the installer puts ``dest``: tracebacks then name the installed files,
    not this build folder. Hash-based and unchecked, so the bytecode stays
    valid whatever modification times the installer gives the files.
    PySide6's ``*.tmpl.py`` deployment templates are not Python and are left out."""
    subprocess.run([str(python), "-I", "-m", "compileall", "-q", "-f", "-j", "0", "-x", r"\.tmpl\.py$",  # noqa: S603
                    "-s", str(dest), "-p", prefix, "--invalidation-mode", "unchecked-hash", str(dest)],
                   check=True, stdout=subprocess.DEVNULL)


def relocate_earth_orientation(dest: Path, prefix: str) -> None:
    """``earth_orientation`` records each file's absolute path in its
    manifest; point them at ``prefix``, where the installer puts ``dest``.
    (The Windows setup does the same at install time, for the folder
    chosen there.)"""
    for manifest in dest.glob("share/spacemissionstudio/earth_orientation/manifest.json"):
        folder = manifest.parent.relative_to(dest).as_posix()
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        for entry in entries:
            entry["path"] = f"{prefix.rstrip('/')}/{folder}/{Path(entry['path']).name}"
        manifest.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def bundle(platform: str, dest: Path, wheel: Path, constraints: Path, cache: Path,
           archive: Path | None = None, prefix: str | None = None) -> dict:
    """Unpack the pinned CPython into ``dest``, install Basilisk and the
    wheel and add the reference data."""
    url, expected = PYTHON_BUILDS[platform]
    unpack(fetch_archive(platform, cache, archive), dest)
    python = interpreter(dest, platform)
    print(f"Installing {BASILISK_REQUIREMENT} ...", flush=True)
    pip_install(python, constraints, BASILISK_REQUIREMENT)
    print(f"Installing {wheel.name}[gui] ...", flush=True)
    pip_install(python, constraints, f"{wheel}[gui]")
    print("Fetching the support data and the Earth orientation files ...", flush=True)
    data = add_support_data(python, dest)
    with tempfile.TemporaryDirectory() as empty_cache:
        run_python(python, _OFFLINE_CHECK, {"BSK_SUPPORT_DATA_CACHE": empty_cache})
    check = json.loads(run_python(
        python, "import json, sys, Basilisk, PySide6, spacemissionstudio; "
        "print(json.dumps({'python': sys.version.split()[0], "
        "'spacemissionstudio': spacemissionstudio.__version__, 'PySide6': PySide6.__version__}))"))
    frozen = subprocess.run([str(python), "-I", "-m", "pip", "list", "--format=freeze",  # noqa: S603 -- no shell
                             "--disable-pip-version-check"], check=True, capture_output=True, text=True).stdout.split()
    manifest = {"python_build": url, "python_build_sha256": expected, **check,
                "packages": sorted(frozen, key=str.lower), "data_files": data}
    if prefix:
        print(f"Compiling the bytecode for {prefix} ...", flush=True)
        recompile(python, dest, prefix)
        relocate_earth_orientation(dest, prefix)
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--platform", choices=sorted(PYTHON_BUILDS),
                        default="windows" if sys.platform == "win32" else "linux")
    parser.add_argument("--dest", type=Path, required=True, help="folder to create (must not exist)")
    parser.add_argument("--wheel", type=Path, required=True, help="the SpaceMissionStudio wheel to install")
    parser.add_argument("--constraints", type=Path, default=_PACKAGING / "constraints.txt")
    parser.add_argument("--cache", type=Path, default=_PACKAGING / ".python-build-cache",
                        help="where the CPython archive is downloaded")
    parser.add_argument("--archive", type=Path, help="a CPython archive already on disk (still checked)")
    parser.add_argument("--prefix", help="the folder the installer puts DEST in, when fixed (the .deb: "
                        "/opt/spacemissionstudio/python); the bytecode then names it")
    args = parser.parse_args(argv)
    manifest = bundle(args.platform, args.dest.resolve(), args.wheel.resolve(), args.constraints.resolve(),
                      args.cache, args.archive, args.prefix)
    print(f"Bundled Python {manifest['python']} with SpaceMissionStudio {manifest['spacemissionstudio']} "
          f"and {len(manifest['packages'])} packages in {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
