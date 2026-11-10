#!/usr/bin/env bash
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
#
# Builds spacemissionstudio's own wheel + sdist -- the Basilisk-independent part
# of packaging. This has been run for real in this project's development
# sandbox (no Basilisk build there, but none is needed for this step):
#
#     python3 -m pip install build
#     ./packaging/build_wheel.sh
#     # -> dist/spacemissionstudio-<version>-py3-none-any.whl
#     # -> dist/spacemissionstudio-<version>.tar.gz
#
# A real bug was caught doing this the first time: spacemissionstudio/scenarios/
# *.json (the two-body validation scenario) was silently missing from the
# built wheel, because setuptools' packages.find() only picks up Python
# packages (dirs with __init__.py) and scenarios/ has none. Fixed in
# pyproject.toml's [tool.setuptools.package-data] -- see that file's own
# comment. Verified by actually building the wheel, installing it into a
# throwaway venv, and running `spacemissionstudio validate` against the
# installed copy of that file; do the same after any packaging change here.
#
# This script does NOT bundle Basilisk: the wheel depends on neither it nor
# a Basilisk build (see pyproject.toml). install.sh takes a Basilisk wheel
# or requirement (--basilisk-wheel "bsk[all]==2.12.0"), and the installers
# carry it through bundle_python.py -- see this directory's README.md.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname "$script_dir")"
dist_dir="${1:-$project_dir/dist}"

cd "$project_dir"

# setuptools' own build backend writes its temp output to ./build (gitignored,
# disposable) -- a stale one left over from a PREVIOUS run of this script
# genuinely breaks the NEXT run: both `python3 -c "import ..."` and
# `python3 -m ...` insert the current directory at the front of sys.path,
# so a leftover ./build/ directory silently SHADOWS the real installed
# `build` package (it has no __main__.py, so `python3 -m build` then fails
# with "No module named build.__main__"). Caught by actually re-running this
# script twice in a row in this project's development sandbox, not a
# hypothetical -- always start from a clean slate here.
rm -rf "$project_dir/build"

if ! python3 -m pip show build >/dev/null 2>&1; then
    echo "Installing the PEP 517 'build' frontend (python3 -m pip install build)..."
    python3 -m pip install --quiet build
fi

echo "Building spacemissionstudio wheel + sdist into $dist_dir ..."
python3 -m build --wheel --sdist --outdir "$dist_dir"

echo
echo "Built:"
ls -1 "$dist_dir"/spacemissionstudio-*
# Release checksums (security_analysis.md S-07): publish SHA256SUMS with
# the files so a user can check what they downloaded.
(cd "$dist_dir" && sha256sum spacemissionstudio-* > SHA256SUMS)
echo "Checksums: $dist_dir/SHA256SUMS"
