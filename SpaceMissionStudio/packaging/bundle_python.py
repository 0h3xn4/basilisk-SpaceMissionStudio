#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
"""Build the private Python that the .deb and the Windows setup program ship.

Unpacks a pinned, relocatable CPython (python-build-standalone) into
``--dest``, installs Basilisk and SpaceMissionStudio into it at the tested
versions, hash-checked (``constraints-hashes.txt``), and adds the
reference data runs read:

* Basilisk's support data (SPICE kernels, gravity fields, the magnetic
  field model, albedo maps, the tabular atmosphere profiles:
  ``kernels.ALL_SUPPORT_DATA_FILES``), fetched
  with Basilisk's own checked fetch into ``site-packages/supportData``,
  the folder Basilisk's ``dataFetcher`` reads before its download cache;
* the IERS-based Earth orientation files (NAIF ITRF93 PCKs) in
  ``earth_orientation.SYSTEM_DIR``, which every user of the install reads;
* ITU-R P.676-13's data file Part 1 (``link.atmospheric_loss``) in
  ``gaseous_attenuation.SYSTEM_DIR``, checked against its pinned SHA-256.

The installers then copy that folder as it is: installing needs no Python
on the machine and no internet.

Every package is installed with ``pip install --require-hashes
--only-binary=:all:``: each file must have the SHA-256 recorded in
``constraints-hashes.txt`` (from ``hash_constraints.py``), every package
must be pinned there, and nothing is built from source. The build then
checks that each package installed is one of the pins, at its version,
and writes a software bill of materials (CycloneDX 1.6 JSON,
``SPACEMISSIONSTUDIO_SBOM.cdx.json``) next to the manifest: the CPython
build, every package with the file installed and its SHA-256 (pip's
installation report), and every data file with its SHA-256. The release
attaches it.

Run it on the platform the installer is for, since pip installs that
platform's binary wheels::

    python packaging/bundle_python.py --platform linux --dest build/python \
        --wheel dist/spacemissionstudio-<version>-py3-none-any.whl

The archive is downloaded once into ``--cache`` and always checked against
its pinned SHA-256; ``--archive`` uses a file already on disk instead.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import uuid
from pathlib import Path

# The sibling module, however this script is started (python -I leaves its
# folder off sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hash_constraints import normalise, read_pins  # noqa: E402

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
#: Written next to it: the software bill of materials (CycloneDX JSON).
SBOM_NAME = "SPACEMISSIONSTUDIO_SBOM.cdx.json"
#: The licence audit: every file of the bundle owned by a component with a
#: known licence (packaging/legal/licences.py), and the notices made from it.
LICENCE_SBOM_NAME = "SPACEMISSIONSTUDIO_LICENCES.cdx.json"
NOTICES_NAME = "THIRD_PARTY_NOTICES.txt"

_PACKAGING = Path(__file__).resolve().parent
_LEGAL = _PACKAGING / "legal"
#: Licence texts of the libraries python-build-standalone links into CPython; its
#: install_only archives carry none (packaging/legal/texts/.../README.md).
PBS_LICENCE_TEXTS = _LEGAL / "texts" / "python-build-standalone-20261013"
#: LGPL-3.0 and a notice for Qt (packaging/legal/texts/qt/README.md).
QT_LICENCE_TEXTS = _LEGAL / "texts" / "qt"


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


def pip_install(python: Path, constraints: Path, requirements: list[str]) -> list[dict]:
    """Install into the bundled Python, hash-checked: each file must have a
    digest in ``constraints`` (``constraints-hashes.txt``) or on its own
    line, every package must be pinned, and none is built from source.
    -I keeps any user site-packages out. Returns pip's record of each
    package installed (installation report: file, SHA-256, metadata)."""
    env = dict(os.environ, PYTHONNOUSERSITE="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
               PIP_ROOT_USER_ACTION="ignore")
    with tempfile.TemporaryDirectory() as scratch:
        listing, report = Path(scratch) / "requirements.txt", Path(scratch) / "report.json"
        listing.write_text("\n".join(requirements) + "\n", encoding="utf-8")
        subprocess.run([str(python), "-I", "-m", "pip", "install", "--quiet", "--no-warn-script-location",  # noqa: S603
                        "--require-hashes", "--only-binary=:all:", "--report", str(report),
                        "-c", str(constraints), "-r", str(listing)], check=True, env=env)
        return json.loads(report.read_text(encoding="utf-8"))["install"]


def local_wheel(wheel: Path, extras: str = "gui") -> str:
    """A requirement line for a wheel on disk, with its own SHA-256 (in
    hash-checking mode every requirement needs one)."""
    name = wheel.name.split("-", 1)[0]
    return f"{name}[{extras}] @ {wheel.as_uri()} --hash=sha256:{sha256_of(wheel)}"


def installed(python: Path) -> list[str]:
    """``name==version`` of every package in the bundled Python."""
    return subprocess.run([str(python), "-I", "-m", "pip", "list", "--format=freeze",  # noqa: S603 -- no shell
                           "--disable-pip-version-check"], check=True, capture_output=True, text=True).stdout.split()


def not_pinned(packages: list[str], pins: dict, own: set[str]) -> list[str]:
    """The packages installed that are not one of the pins at its version;
    ``own`` names those that come with the CPython build or are ours."""
    problems = []
    for entry in packages:
        name, _, version = entry.partition("==")
        key = normalise(name)
        if key in own:
            continue
        if key not in pins:
            problems.append(f"{entry} is not pinned")
        elif pins[key][1] != version:
            problems.append(f"{entry} is pinned at {pins[key][1]}")
    return problems


def _licences(metadata: dict) -> list[dict]:
    """CycloneDX licences from core metadata: the SPDX expression when
    given, else a short licence field, else the trove classifiers."""
    if metadata.get("license_expression"):
        return [{"expression": metadata["license_expression"]}]
    text = (metadata.get("license") or "").strip()
    if text and "\n" not in text and len(text) <= 80:
        return [{"license": {"name": text}}]
    return [{"license": {"name": classifier.split(" :: ")[-1]}}
            for classifier in metadata.get("classifier", []) if classifier.startswith("License ::")]


def _timestamp() -> str:
    """UTC, from SOURCE_DATE_EPOCH when set (reproducible builds)."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    moment = (datetime.datetime.fromtimestamp(int(epoch), datetime.UTC) if epoch
              else datetime.datetime.now(datetime.UTC))
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def sbom(platform: str, manifest: dict, report: list[dict]) -> dict:
    """The bill of materials of the bundled Python (CycloneDX 1.6): the
    CPython build, each package pip installed with the file it came from
    and its SHA-256, and each data file with its SHA-256."""
    version = manifest["spacemissionstudio"]
    components = [{
        "type": "application", "bom-ref": "cpython", "name": "CPython (python-build-standalone)",
        "version": manifest["python"], "licenses": [{"expression": "Python-2.0"}],
        "hashes": [{"alg": "SHA-256", "content": manifest["python_build_sha256"]}],
        "externalReferences": [{"type": "distribution", "url": manifest["python_build"]}],
    }]
    for item in sorted(report, key=lambda entry: normalise(entry["metadata"]["name"])):
        metadata, download = item["metadata"], item["download_info"]
        name = normalise(metadata["name"])
        if name == "spacemissionstudio":
            continue
        purl = f"pkg:pypi/{name}@{metadata['version']}"
        digest = download.get("archive_info", {}).get("hashes", {}).get("sha256")
        component = {"type": "library", "bom-ref": purl, "name": metadata["name"], "version": metadata["version"],
                     "purl": purl, "licenses": _licences(metadata),
                     "externalReferences": [{"type": "distribution", "url": download["url"]}]}
        if digest:
            component["hashes"] = [{"alg": "SHA-256", "content": digest}]
        if not component["licenses"]:
            del component["licenses"]
        components.append(component)
    components += [{"type": "file", "bom-ref": f"file:{entry['path']}", "name": entry["path"],
                    "hashes": [{"alg": "SHA-256", "content": entry["sha256"]}]} for entry in manifest["data_files"]]
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "metadata": {
            "timestamp": _timestamp(),
            "tools": {"components": [{"type": "application", "name": "packaging/bundle_python.py",
                                      "version": version}]},
            "component": {"type": "application", "bom-ref": f"pkg:pypi/spacemissionstudio@{version}",
                          "name": "spacemissionstudio", "version": version,
                          "purl": f"pkg:pypi/spacemissionstudio@{version}",
                          "description": f"SpaceMissionStudio {version}, the private Python of the {platform} installer",
                          "licenses": [{"expression": "EUPL-1.2"}]},
        },
        "components": components,
    }


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
    itu_dir = Path(run_python(python, _ITU_FETCH).strip())
    make_readable(itu_dir)
    return [{"path": path.relative_to(dest).as_posix(),
             "size_bytes": path.stat().st_size, "sha256": sha256_of(path)}
            for folder in (target, eop_dir, itu_dir) for path in sorted(folder.rglob("*")) if path.is_file()]


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

_ITU_FETCH = """
from spacemissionstudio.engine import gaseous_attenuation
gaseous_attenuation.fetch(gaseous_attenuation.SYSTEM_DIR)
print(gaseous_attenuation.SYSTEM_DIR)
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
from spacemissionstudio.engine import earth_orientation, gaseous_attenuation, kernels
local = Path(dataFetcher.LOCAL_SUPPORT)
for data_file in kernels.ALL_SUPPORT_DATA_FILES:
    assert local in kernels.cached_path(data_file).parents, data_file
assert earth_orientation.installed(earth_orientation.SYSTEM_DIR), "no Earth orientation files"
gaseous_attenuation.load_part1(gaseous_attenuation.part1_path())
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


def licence_gate(platform: str, dest: Path, mode: str) -> None:
    """Write the licence texts, the licence SBOM and THIRD_PARTY_NOTICES into the bundle, and run
    the gate (packaging/legal/licences.py check). ``mode`` is ``fail`` (a problem stops the build),
    ``warn`` (a problem is printed) or ``off``. The Windows component list is not complete yet
    (docs/legal/OBLIGATIONS.md), so it defaults to ``warn``."""
    if mode == "off":
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("smstudio_licences", _LEGAL / "licences.py")
    licences = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(licences)
    target = dest / "licenses"
    target.mkdir(exist_ok=True)
    for text in sorted(QT_LICENCE_TEXTS.glob("*.txt")):  # PySide6's wheels carry no licence text
        shutil.copy2(text, target / text.name)
    if platform == "linux":
        for text in sorted(PBS_LICENCE_TEXTS.glob("LICENSE.*.txt")):
            shutil.copy2(text, target / text.name)
    sbom_data = licences.build_sbom(dest, f"spacemissionstudio-{platform}")
    (dest / LICENCE_SBOM_NAME).write_text(json.dumps(sbom_data, indent=2) + "\n", encoding="utf-8")
    licences.write_notices(sbom_data, dest, dest / NOTICES_NAME)
    lines = licences.check(sbom_data, dest, dest / NOTICES_NAME)
    failures = [line for line in lines if not line.startswith("WARN")]
    shown = lines if len(lines) <= 400 else lines[:400]  # a first Windows run lists thousands of files
    for line in shown:
        print(line if line.startswith("WARN") else "LICENCE GATE: " + line, flush=True)
    if len(lines) > len(shown):
        print(f"LICENCE GATE: ... and {len(lines) - len(shown)} more lines", flush=True)
    report = os.environ.get("SMS_LICENCE_REPORT")
    if report:
        Path(report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if failures and mode == "fail":
        raise SystemExit(f"licence gate: {len(failures)} problems (see above; docs/legal/OBLIGATIONS.md)")


def bundle(platform: str, dest: Path, wheel: Path, constraints: Path, cache: Path,
           archive: Path | None = None, prefix: str | None = None, licence_mode: str | None = None) -> dict:
    """Unpack the pinned CPython into ``dest``, install Basilisk and the
    wheel and add the reference data."""
    url, expected = PYTHON_BUILDS[platform]
    unpack(fetch_archive(platform, cache, archive), dest)
    python = interpreter(dest, platform)
    own = {normalise(entry.partition("==")[0]) for entry in installed(python)} | {"spacemissionstudio"}
    print(f"Installing {BASILISK_REQUIREMENT} (hash-checked) ...", flush=True)
    report = pip_install(python, constraints, [BASILISK_REQUIREMENT])
    print(f"Installing {wheel.name}[gui] (hash-checked) ...", flush=True)
    report += pip_install(python, constraints, [local_wheel(wheel)])
    problems = not_pinned(installed(python), read_pins(constraints), own)
    if problems:
        raise SystemExit("installed but not pinned in " + constraints.name + ": " + "; ".join(problems))
    print("Fetching the support data, the Earth orientation files and ITU-R P.676-13 Part 1 ...", flush=True)
    data = add_support_data(python, dest)
    with tempfile.TemporaryDirectory() as empty_cache:
        run_python(python, _OFFLINE_CHECK, {"BSK_SUPPORT_DATA_CACHE": empty_cache})
    check = json.loads(run_python(
        python, "import json, sys, Basilisk, PySide6, spacemissionstudio; "
        "print(json.dumps({'python': sys.version.split()[0], "
        "'spacemissionstudio': spacemissionstudio.__version__, 'PySide6': PySide6.__version__}))"))
    manifest = {"python_build": url, "python_build_sha256": expected, **check,
                "packages": sorted(installed(python), key=str.lower), "data_files": data, "sbom": SBOM_NAME}
    if prefix:
        print(f"Compiling the bytecode for {prefix} ...", flush=True)
        recompile(python, dest, prefix)
        relocate_earth_orientation(dest, prefix)
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (dest / SBOM_NAME).write_text(json.dumps(sbom(platform, manifest, report), indent=2) + "\n", encoding="utf-8")
    licence_gate(platform, dest, licence_mode or ("fail" if platform == "linux" else "warn"))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--platform", choices=sorted(PYTHON_BUILDS),
                        default="windows" if sys.platform == "win32" else "linux")
    parser.add_argument("--dest", type=Path, required=True, help="folder to create (must not exist)")
    parser.add_argument("--wheel", type=Path, required=True, help="the SpaceMissionStudio wheel to install")
    parser.add_argument("--constraints", type=Path, default=_PACKAGING / "constraints-hashes.txt",
                        help="the pins with their SHA-256 (hash_constraints.py writes it)")
    parser.add_argument("--cache", type=Path, default=_PACKAGING / ".python-build-cache",
                        help="where the CPython archive is downloaded")
    parser.add_argument("--archive", type=Path, help="a CPython archive already on disk (still checked)")
    parser.add_argument("--prefix", help="the folder the installer puts DEST in, when fixed (the .deb: "
                        "/opt/spacemissionstudio/python); the bytecode then names it")
    parser.add_argument("--licence-gate", choices=("fail", "warn", "off"),
                        help="what a licence problem does (legal/licences.py): default fail on Linux, warn on Windows")
    args = parser.parse_args(argv)
    manifest = bundle(args.platform, args.dest.resolve(), args.wheel.resolve(), args.constraints.resolve(),
                      args.cache, args.archive, args.prefix, args.licence_gate)
    print(f"Bundled Python {manifest['python']} with SpaceMissionStudio {manifest['spacemissionstudio']} "
          f"and {len(manifest['packages'])} packages in {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
