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

"""Writes the notes of a release draft from its CHANGELOG section and its
built files (``docs/developer/releasing.md``, section 3).

The release workflow runs it before attaching the files::

    python3 packaging/release_notes.py --version 1.2.0 --files ../release \\
        --run-url https://github.com/<owner>/<repo>/actions/runs/<id> > notes.md

The notes have a fixed layout for someone deciding whether to download:
the summary, who should update, the downloads with their sizes, how to
install or upgrade, how to check a download (with the installers'
SHA-256), what is new, what the installers contain, how the files were
checked and the known limits.

From the CHANGELOG section ``## X.Y.Z (date)`` it takes:

* the paragraphs before the first list item or ``###`` heading: the
  summary;
* ``### Who should update`` and ``### Known limits``, when present: those
  sections, each up to the next ``###`` heading, so they go after the
  list of changes (known limits are added to the standing ones);
* every other list item and ``###`` section: "What's new".

Standard library only: the workflow runs it with the runner's Python.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_URL = "https://github.com/0h3xn4/basilisk-SpaceMissionStudio"

#: Subsections of a CHANGELOG entry that get a section of their own.
OWN_SECTIONS = ("Who should update", "Known limits")

#: Limits every release has until they are removed here.
STANDING_LIMITS = [
    "**Windows SmartScreen:** the setup program is not code-signed, so Windows warns before running it.",
    "**Linux on ARM (aarch64):** no installer; use the wheel and `packaging/install.sh`.",
]


class NotesError(RuntimeError):
    """A file or CHANGELOG section the notes need is missing."""


def changelog_section(changelog: str, version: str) -> dict[str, str]:
    """The parts of the ``## version (date)`` section: ``summary``,
    ``new`` and one entry per name of :data:`OWN_SECTIONS` present."""
    lines = changelog.splitlines()
    head = f"## {version} ("
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith(head))
    except StopIteration:
        raise NotesError(f"CHANGELOG.md has no section '## {version} (date)'") from None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body = lines[start + 1:end]

    first_item = next((i for i, line in enumerate(body) if line.startswith(("- ", "* ", "### "))), len(body))
    parts = {"summary": unwrap("\n".join(body[:first_item]).strip())}
    new: list[str] = []
    current: str | None = None
    own: dict[str, list[str]] = {}
    for line in body[first_item:]:
        if line.startswith("### "):
            title = line[4:].strip()
            current = title if title in OWN_SECTIONS else None
            if current is None:
                new.append(line)
            else:
                own[current] = []
            continue
        (own[current] if current else new).append(line)
    parts["new"] = unwrap("\n".join(new).strip())
    for title, text in own.items():
        parts[title] = unwrap("\n".join(text).strip())
    return parts


_ITEM = re.compile(r"^(\s*)([-*]|\d+\.) ")


def unwrap(text: str) -> str:
    """Joins the hard-wrapped lines of each paragraph and list item: a
    release page shows every line break. Blank lines, headings, table rows,
    code blocks and the start of each (nested) list item stay as they are."""
    out: list[str] = []
    joinable = False  # the last line is prose a continuation may join
    fenced = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            out.append(line)
            joinable = False
            continue
        if fenced or not stripped or stripped.startswith(("#", "|")):
            out.append(line)
            joinable = False
            continue
        if _ITEM.match(line):
            out.append(line.rstrip())
            joinable = True
            continue
        if joinable:
            out[-1] = f"{out[-1]} {stripped}"
        else:
            out.append(line.rstrip())
            joinable = True
    return "\n".join(out)


def _size(n_bytes: int) -> str:
    """Decimal units, as download pages show them."""
    if n_bytes >= 1e9:
        return f"{n_bytes / 1e9:.2f} GB"
    if n_bytes >= 1e8:
        return f"{n_bytes / 1e6:.0f} MB"
    if n_bytes >= 1e6:
        return f"{n_bytes / 1e6:.1f} MB"
    return f"{n_bytes / 1e3:.0f} kB"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _installed_size(deb: Path) -> int | None:
    """The .deb's Installed-Size in bytes, when dpkg-deb is there to read it."""
    dpkg_deb = shutil.which("dpkg-deb")
    if dpkg_deb is None:
        return None
    result = subprocess.run([dpkg_deb, "-f", str(deb), "Installed-Size"], capture_output=True,  # noqa: S603
                            text=True, check=False)
    value = result.stdout.strip()
    return int(value) * 1024 if result.returncode == 0 and value.isdigit() else None


def _release_files(files: Path, version: str) -> dict[str, Path]:
    names = {
        "deb": f"spacemissionstudio_{version}_amd64.deb",
        "setup": f"spacemissionstudio-{version}-setup.exe",
        "wheel": f"spacemissionstudio-{version}-py3-none-any.whl",
        "sdist": f"spacemissionstudio-{version}.tar.gz",
    }
    found = {key: files / name for key, name in names.items()}
    missing = [path.name for path in found.values() if not path.is_file()]
    if missing:
        raise NotesError(f"not in {files}: {', '.join(missing)}")
    return found


def bundled_versions(root: Path = ROOT) -> dict[str, str]:
    """CPython, Basilisk and PySide6 as the installers ship them, read from
    ``packaging/bundle_python.py`` and ``packaging/constraints.txt``."""
    bundle = (root / "packaging" / "bundle_python.py").read_text(encoding="utf-8")
    constraints = (root / "packaging" / "constraints.txt").read_text(encoding="utf-8")
    patterns = {
        "python": (bundle, r"cpython-(\d+\.\d+\.\d+)%2B"),
        "basilisk": (bundle, r'BASILISK_REQUIREMENT = "bsk\[all\]==([^"]+)"'),
        "pyside6": (constraints, r"(?m)^PySide6==(\S+)"),
    }
    versions = {}
    for key, (text, pattern) in patterns.items():
        match = re.search(pattern, text)
        if match is None:
            raise NotesError(f"cannot find the {key} version (pattern {pattern!r})")
        versions[key] = match.group(1)
    return versions


def space_weather_end(root: Path = ROOT) -> str:
    """The last observed day of the bundled CelesTrak file, ISO 8601."""
    path = root / "spacemissionstudio" / "data" / "spaceweather" / "SW-All.txt"
    previous = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("END OBSERVED"):
                year, month, day = previous.split()[:3]
                return f"{year}-{int(month):02d}-{int(day):02d}"
            previous = line
    raise NotesError(f"{path} has no OBSERVED block")


def render(version: str, files: Path, run_url: str, changelog: str, root: Path = ROOT) -> str:
    """The notes, as Markdown."""
    section = changelog_section(changelog, version)
    paths = _release_files(files, version)
    sizes = {key: path.stat().st_size for key, path in paths.items()}
    hashes = {key: _sha256(paths[key]) for key in ("deb", "setup")}
    installed = _installed_size(paths["deb"])
    versions = bundled_versions(root)
    deb, setup = paths["deb"].name, paths["setup"].name

    out: list[str] = []
    add = out.append
    if section["summary"]:
        add(section["summary"])
        add("")
    if section.get("Who should update"):
        add("## Who should update")
        add("")
        add(section["Who should update"])
        add("")

    deb_size = _size(sizes["deb"]) + (f" ({_size(installed)} installed)" if installed else "")
    add("## Downloads")
    add("")
    add("| System | File | Size |")
    add("|---|---|---|")
    add(f"| Linux x86_64 (Ubuntu 22.04, Debian 12 or later) | `{deb}` | {deb_size} |")
    add(f"| Windows 10 or 11, x64 | `{setup}` | {_size(sizes['setup'])} |")
    add(f"| Python developers (Linux, Windows) | `{paths['wheel'].name}`, `{paths['sdist'].name}` "
        f"| {_size(sizes['wheel'])}, {_size(sizes['sdist'])} |")
    add("| Checksums | `SHA256SUMS-linux`, `SHA256SUMS-windows` | |")
    add("")

    add("## Install or upgrade")
    add("")
    add("**Linux:** install the `.deb` from a terminal; it replaces an installed SpaceMissionStudio package.")
    add("")
    add("```bash")
    add(f"sudo apt install ./{deb}")
    add("```")
    add("")
    add("A final `N: Download is performed unsandboxed as root ...` line from apt is harmless.")
    add("")
    add(f"**Windows:** run `{setup}`.")
    add("- The program is not signed, so Windows asks first: choose **More info**, then **Run anyway**.")
    add("- It installs for your user only, under `%LOCALAPPDATA%\\SpaceMissionStudio`, without administrator "
        "rights.")
    add("")
    add("Then start **SpaceMissionStudio** from the application menu or the Start Menu.")
    add("")

    add("## Check your download")
    add("")
    add("```bash")
    add("sha256sum -c SHA256SUMS-linux --ignore-missing          # Linux")
    add("```")
    add("")
    add("```powershell")
    add(f"Get-FileHash .\\{setup}       # Windows: compare with SHA256SUMS-windows")
    add("```")
    add("")
    add("| File | SHA-256 |")
    add("|---|---|")
    add(f"| `{deb}` | `{hashes['deb']}` |")
    add(f"| `{setup}` | `{hashes['setup']}` |")
    add("")

    if section["new"]:
        add("## What's new")
        add("")
        add(section["new"])
        add("")

    add("## What the installers contain")
    add("")
    add("- **Software:**")
    add(f"  - Python {versions['python']} (python-build-standalone);")
    add(f"  - Basilisk {versions['basilisk']}, the version the app is verified against;")
    add(f"  - PySide6 {versions['pyside6']} and every other package, at the versions the tests ran with.")
    add("- **Reference data:**")
    add("  - the SPICE kernels;")
    add("  - the Earth and Mars gravity fields;")
    add("  - the magnetic field model;")
    add("  - the Earth and Mars albedo maps;")
    add("  - the measured Earth orientation files, current on the build day.")
    add(f"- **Bundled space weather:** CelesTrak observations to {space_weather_end(root)}.")
    add("- **Still downloaded on request:** the asteroid Eros files (Reference data, **Small bodies**), the Vizard "
        "viewer, and newer space weather. The app asks before any download.")
    add("")

    add("## How this release was checked")
    add("")
    add(f"The release workflow ([run]({run_url})) built every file and installed it on its own platform:")
    add("")
    add("- **Linux:** it installed the `.deb` with the network cut off and an empty data cache, then:")
    add("  - checked the version and every reference-data file;")
    add("  - validated every template and ran template 01 from the bundled data;")
    add("  - found the Earth orientation files;")
    add("  - opened the main window.")
    add("- **Windows:** it installed the setup silently with an empty data cache, then:")
    add("  - checked the reference data;")
    add("  - validated and ran template 01;")
    add("  - opened the main window.")
    add("- **Tests:** the whole test suite passed on the tagged commit on Linux and Windows, with lint, the "
        "document checks and a check of every pinned package against the known-vulnerability databases "
        "(pip-audit).")
    add("- **Checksums:** every attached file was checked against `SHA256SUMS-linux` and `SHA256SUMS-windows`.")
    add("")

    add("## Known limits")
    add("")
    for limit in STANDING_LIMITS:
        add(f"- {limit}")
    if section.get("Known limits"):
        add(section["Known limits"])
    add("")

    add(f"The full change list is in [`CHANGELOG.md`]({REPOSITORY_URL}/blob/develop/SpaceMissionStudio/CHANGELOG.md), "
        f"and how the installers are built is in "
        f"[`packaging/README.md`]({REPOSITORY_URL}/blob/develop/SpaceMissionStudio/packaging/README.md).")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", required=True, help="the release version, for example 1.2.0")
    parser.add_argument("--files", required=True, type=Path, help="the folder with the built release files")
    parser.add_argument("--run-url", required=True, help="the workflow run that built and checked them")
    parser.add_argument("--changelog", type=Path, default=ROOT / "CHANGELOG.md")
    args = parser.parse_args(argv)
    try:
        notes = render(args.version, args.files, args.run_url, args.changelog.read_text(encoding="utf-8"))
    except NotesError as exc:
        print(f"release_notes.py: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
