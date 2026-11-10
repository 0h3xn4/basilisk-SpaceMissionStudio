#!/usr/bin/env bash
#
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
#
#
# Builds the Debian package spacemissionstudio_<version>_amd64.deb. It is
# self-contained: /opt/spacemissionstudio/python is a private CPython 3.14
# (python-build-standalone) with Basilisk, SpaceMissionStudio and every
# Python package installed, plus the support data and the Earth
# orientation files (packaging/bundle_python.py). Installing it needs no
# system Python and no internet; /usr/bin/spacemissionstudio runs that
# Python.
#
# Usage:
#   ./build_deb.sh [OUTPUT_DIR]
#
# Needs dpkg-deb, python3 (3.14 or later, to run bundle_python.py) and
# internet access while it builds (the CPython archive, Basilisk and the
# packages from PyPI, the support data). SMS_PYTHON_ARCHIVE=<file> uses a
# CPython archive already downloaded (its SHA-256 is still checked).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(dirname "$script_dir")"
output_dir="${1:-$project_dir/dist}"
install_dir=/opt/spacemissionstudio

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "dpkg-deb not found -- this script only runs on Debian/Ubuntu-family systems" >&2
    echo "(or any system with dpkg-dev installed: apt-get install dpkg-dev)." >&2
    exit 1
fi

version=$(cd "$project_dir" && python3 -c "import spacemissionstudio; print(spacemissionstudio.__version__)")
echo "Building spacemissionstudio_${version}_amd64.deb ..."

# The wheel the bundled Python installs: the same build as the plain wheel.
wheel_build_dir=$(mktemp -d)
staging=$(mktemp -d)
trap 'rm -rf "$wheel_build_dir" "$staging"' EXIT
"$script_dir/build_wheel.sh" "$wheel_build_dir" >/dev/null
wheels=("$wheel_build_dir"/spacemissionstudio-*.whl)
wheel=${wheels[0]}

# The staging tree: the checked-in skeleton (packaging/deb/: maintainer
# scripts, control.in, launcher, desktop entry, copyright) plus the bundled
# Python. packaging/deb/ itself is never changed.
chmod 755 "$staging"
cp -r "$script_dir/deb/." "$staging/"
archive_args=()
if [ -n "${SMS_PYTHON_ARCHIVE:-}" ]; then
    archive_args=(--archive "$SMS_PYTHON_ARCHIVE")
fi
python3 "$script_dir/bundle_python.py" --platform linux --dest "$staging$install_dir/python" \
    --wheel "$wheel" --prefix "$install_dir/python" "${archive_args[@]}"
bundled_python="$staging$install_dir/python/bin/python3"

# The notices of everything the package redistributes (bundle_python.py
# writes them with the licence texts into the bundled Python's folder), also
# where Debian users look for a package's licence files.
install -D -m 644 "$staging$install_dir/python/THIRD_PARTY_NOTICES.txt" \
    "$staging/usr/share/doc/spacemissionstudio/THIRD_PARTY_NOTICES.txt"
# The app's own licence, in English and German (the copyright file points here).
install -m 644 "$script_dir/../LICENSE" "$staging/usr/share/doc/spacemissionstudio/LICENSE"
install -m 644 "$script_dir/../LICENSE.de" "$staging/usr/share/doc/spacemissionstudio/LICENSE.de"

# The menu icon (gui/icons.py draws it; no bitmap in the repository),
# rendered now so it is a package file.
QT_QPA_PLATFORM=offscreen "$bundled_python" -I -c "
import sys
from spacemissionstudio.gui.icons import ensure_icon_file
ensure_icon_file(sys.argv[1])
" "$staging/usr/share/icons/hicolor/256x256/apps/spacemissionstudio.png"

installed_size=$(du -sk --exclude=DEBIAN "$staging" | cut -f1)
sed -e "s/@VERSION@/${version}/" -e "s/@INSTALLED_SIZE@/${installed_size}/" \
    "$staging/DEBIAN/control.in" > "$staging/DEBIAN/control"
rm "$staging/DEBIAN/control.in"
chmod 755 "$staging/DEBIAN/postinst" "$staging/DEBIAN/postrm" "$staging/usr/bin/spacemissionstudio"

mkdir -p "$output_dir"
output_deb="$output_dir/spacemissionstudio_${version}_amd64.deb"
# --root-owner-group: every file in the package is owned by root:root,
# whoever runs this script.
dpkg-deb --build --root-owner-group -Zxz "$staging" "$output_deb"

# Release checksum (security_analysis.md S-07), next to the package.
(cd "$output_dir" && sha256sum "$(basename "$output_deb")" > "$(basename "$output_deb").sha256")

echo
echo "Built: $output_deb"
echo "SHA-256: $output_deb.sha256"
echo "Install with: sudo apt install ./$(basename "$output_deb")"
