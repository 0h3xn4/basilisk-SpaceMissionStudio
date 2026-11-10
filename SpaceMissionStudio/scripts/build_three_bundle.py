#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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
#
"""Build the three.js bundle of Results › 3D View, reproducibly.

The 3D View's page (``spacemissionstudio/gui/assets/mission_view/``)
loads three.js from one classic script that defines the global
``THREE`` (three.js and its ``OrbitControls``): a page opened from a
``file://`` URL cannot load ES modules (Chromium's CORS rule for file
origins), so the modules are bundled into an IIFE.

What this script does, with nothing taken from outside the pins:

1. copies ``scripts/three_bundle/`` (``package.json`` with exact
   versions, ``package-lock.json`` with npm's SHA-512 integrity of every
   tarball, ``entry.js``) to a temporary folder;
2. ``npm ci --ignore-scripts``: installs exactly the locked tarballs
   (three 0.187.0, esbuild 0.25.10), checked against the lock's
   integrity hashes, running no install script;
3. bundles ``entry.js`` with esbuild (``--bundle --minify --format=iife
   --global-name=THREE --legal-comments=eof``: three.js's licence
   comment stays at the end of the bundle);
4. writes ``three.bundle.min.js`` and three.js's own ``LICENSE`` as
   ``THREE_LICENSE.txt`` into the assets folder, and prints the SHA-256
   of each (``docs/THIRD_PARTY_ASSETS.md`` records them).

Needs Node.js (22) and npm, and access to registry.npmjs.org. Run from
the SpaceMissionStudio folder::

    python scripts/build_three_bundle.py            # writes the assets
    python scripts/build_three_bundle.py --check    # builds, compares, writes nothing

``--check`` fails when the built bundle differs from the committed one.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "three_bundle"
ASSETS = ROOT / "spacemissionstudio" / "gui" / "assets" / "mission_view"
BUNDLE = "three.bundle.min.js"
LICENCE = "THREE_LICENSE.txt"
THREE_VERSION = "0.187.0"
ESBUILD_VERSION = "0.25.10"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(work: Path) -> tuple[Path, Path]:
    """Build in ``work``; the bundle and the licence text."""
    for name in ("package.json", "package-lock.json", "entry.js"):
        shutil.copy2(SOURCE / name, work / name)
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm was not found: install Node.js 22")
    subprocess.run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=work, check=True)
    installed = (work / "node_modules" / "three" / "package.json").read_text(encoding="utf-8")
    if f'"version": "{THREE_VERSION}"' not in installed:
        raise SystemExit(f"three is not {THREE_VERSION}")
    esbuild = work / "node_modules" / ".bin" / ("esbuild.cmd" if sys.platform == "win32" else "esbuild")
    out = work / BUNDLE
    subprocess.run([str(esbuild), "entry.js", "--bundle", "--minify", "--format=iife", "--global-name=THREE",
                    "--legal-comments=eof", "--target=es2020", f"--outfile={out.name}"], cwd=work, check=True)
    version = subprocess.run([str(esbuild), "--version"], cwd=work, check=True, capture_output=True,
                             text=True).stdout.strip()
    if version != ESBUILD_VERSION:
        raise SystemExit(f"esbuild is {version}, not {ESBUILD_VERSION}")
    return out, work / "node_modules" / "three" / "LICENSE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="build and compare with the committed files")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="sms_three_") as folder:
        bundle, licence = build(Path(folder))
        print(f"three {THREE_VERSION}, esbuild {ESBUILD_VERSION}")
        print(f"{sha256(bundle)}  {BUNDLE} ({bundle.stat().st_size} bytes)")
        print(f"{sha256(licence)}  {LICENCE}")
        if args.check:
            same = all((ASSETS / name).is_file() and sha256(ASSETS / name) == sha256(built)
                       for name, built in ((BUNDLE, bundle), (LICENCE, licence)))
            print("the committed files are the build's" if same else "the committed files differ from the build")
            return 0 if same else 1
        ASSETS.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle, ASSETS / BUNDLE)
        shutil.copyfile(licence, ASSETS / LICENCE)
        print(f"written to {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
