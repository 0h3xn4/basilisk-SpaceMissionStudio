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

"""Qualified Basilisk version, its start-up check and the run's
configuration record (ECSS-Q-ST-80C 6.2.4, 6.2.7; remediation R01)."""

import hashlib
import json
import re
from pathlib import Path

import pytest

from spacemissionstudio import dependencies

pytestmark = pytest.mark.requirement("Q-ST-80C 6.2.4", "Q-ST-80C 6.2.7")

_PACKAGING = Path(__file__).resolve().parent.parent / "packaging"


def test_basilisk_check_accepts_only_the_qualified_version():
    """No note for the qualified version; a note naming both versions for
    another; a clear note when Basilisk is missing."""
    assert dependencies.basilisk_check(dependencies.QUALIFIED_BASILISK_VERSION) is None
    note = dependencies.basilisk_check("2.13.0b0")
    assert "2.13.0b0" in note and dependencies.QUALIFIED_BASILISK_VERSION in note


def test_basilisk_check_reports_a_missing_basilisk(monkeypatch):
    """Without Basilisk the check says simulations cannot run."""
    monkeypatch.setattr(dependencies, "basilisk_version", lambda: None)
    assert dependencies.basilisk_check() == "Basilisk is not installed: simulations cannot run"


def test_installers_pin_the_qualified_basilisk_version():
    """The Basilisk the .deb and the Windows setup bundle
    (packaging/bundle_python.py) is exactly the qualified version, so
    changing one without the other fails here."""
    text = (_PACKAGING / "bundle_python.py").read_text(encoding="utf-8")
    pins = re.findall(r'^BASILISK_REQUIREMENT = "bsk\[all\]([^"]*)"$', text, flags=re.MULTILINE)
    assert pins == [f"=={dependencies.QUALIFIED_BASILISK_VERSION}"]


def test_file_record_hashes_small_files_and_flags_missing_ones(tmp_path):
    """A small file gets its size and SHA-256; a missing one is marked."""
    data = tmp_path / "sw.csv"
    data.write_bytes(b"DATE,F10.7\n2026-01-01,150.0\n")
    record = dependencies.file_record(data)
    assert record == {"path": str(data), "size_bytes": len(data.read_bytes()),
                      "sha256": hashlib.sha256(data.read_bytes()).hexdigest()}
    assert dependencies.file_record(tmp_path / "absent.bsp") == {"path": str(tmp_path / "absent.bsp"),
                                                                 "missing": True}


def test_dependency_versions_lists_python_and_installed_packages():
    """Python, platform and numpy (a hard dependency) are always listed."""
    versions = dependencies.dependency_versions()
    assert {"python", "platform", "numpy"} <= set(versions)


@pytest.mark.requires_basilisk
def test_run_provenance_records_the_configuration(tmp_path):
    """A real run's provenance.json carries the Basilisk qualification, the
    dependency versions, the scenario hash and the SPICE kernels used."""
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema import load_scenario

    scenario_path = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / \
        "two_body_validation.json"
    scenario = load_scenario(scenario_path)
    scenario.sim_settings.duration_days = 0.01  # [day]
    result = SimulationService(scenario).run()
    paths = result.export_csv(tmp_path)
    provenance = json.loads(Path(paths["provenance"]).read_text())
    assert provenance["qualified_basilisk_version"] == dependencies.QUALIFIED_BASILISK_VERSION
    assert provenance["basilisk_qualified"] == (provenance["basilisk_version"]
                                                == dependencies.QUALIFIED_BASILISK_VERSION)
    assert provenance["dependency_versions"]["numpy"]
    assert provenance["scenario_sha256"] == hashlib.sha256(
        json.dumps(scenario.to_dict(), sort_keys=True).encode("utf-8")).hexdigest()
    kernels = {name: record for name, record in provenance["data_files"].items() if name.startswith("spice:")}
    assert "spice:naif0012.tls" in kernels
    assert all("size_bytes" in record for record in kernels.values())


def test_the_release_constraints_pin_every_dependency_the_installers_use():
    """Audit M14: installers and CI took the newest PySide6, plotly and numpy
    on every install. packaging/constraints.txt pins the tested versions:
    every runtime and GUI dependency, Basilisk at the qualified version, and
    each installer and the CI workflow installs with it."""
    import tomllib

    root = Path(__file__).resolve().parents[1]
    pins = {}
    for line in (root / "packaging" / "constraints.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, _, version = line.partition("==")
            assert version, f"not an exact pin: {line!r}"
            pins[name.lower().replace("_", "-")] = version
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    for requirement in project["dependencies"] + project["optional-dependencies"]["gui"]:
        name = re.split(r"[<>=!~\[ ]", requirement, maxsplit=1)[0].lower().replace("_", "-")
        assert name in pins, f"{name} is not pinned in constraints.txt"
    assert pins["bsk"] == dependencies.QUALIFIED_BASILISK_VERSION
    for installer in ("packaging/install.sh", "packaging/install.ps1", "packaging/bundle_python.py",
                      "../.github/workflows/spacemissionstudio.yml"):
        assert "constraints.txt" in (root / installer).read_text(encoding="utf-8"), installer



def test_ci_installs_pinned_development_tools():
    """Audit R11: CI took the newest ruff, pytest and its plugins on every
    run. packaging/constraints-dev.txt pins every dev extra and pip-audit,
    exactly, and every workflow that installs the dev extra uses it."""
    import tomllib

    root = Path(__file__).resolve().parents[1]
    pins = {}
    for line in (root / "packaging" / "constraints-dev.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, _, version = line.partition("==")
            assert version, f"not an exact pin: {line!r}"
            pins[name.lower().replace("_", "-")] = version
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    for requirement in project["optional-dependencies"]["dev"] + ["pip-audit", "pre-commit"]:
        name = re.split(r"[<>=!~\[ ]", requirement, maxsplit=1)[0].lower().replace("_", "-")
        assert name in pins, f"{name} is not pinned in constraints-dev.txt"
    workflows = sorted((root.parent / ".github" / "workflows").glob("spacemissionstudio*.yml"))
    installs = [line for path in workflows for line in path.read_text(encoding="utf-8").splitlines()
                if "pip install" in line and ".[dev" in line]
    assert installs
    assert all("constraints-dev.txt" in line for line in installs), installs


def test_the_debian_copyright_file_names_each_bundled_part_and_its_licence():
    """Audit R12: the .deb's copyright file said ISC for every file, though
    the package bundles CPython, Qt, fonts and icons under other licences,
    and named AVSLab/basilisk as the source. In the machine-readable format
    the last stanza whose Files pattern matches a path applies; each part
    must resolve to its own licence, and the source is this fork."""
    import fnmatch

    root = Path(__file__).resolve().parents[1]
    text = (root / "packaging/deb/usr/share/doc/spacemissionstudio/copyright").read_text(encoding="utf-8")
    header, *paragraphs = text.split("\n\n")
    assert "Source: https://github.com/0h3xn4/basilisk-SpaceMissionStudio\n" in header
    stanzas = []
    for paragraph in paragraphs:
        if paragraph.startswith("Files:"):
            fields = re.split(r"\n(?=[A-Z][\w-]*:)", paragraph)
            patterns = fields[0].removeprefix("Files:").split()
            licence = next(f for f in fields if f.startswith("License:")).splitlines()[0].removeprefix("License:")
            stanzas.append((patterns, licence.strip()))

    def licence_of(path):
        return [licence for patterns, licence in stanzas
                if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)][-1]

    site = "opt/spacemissionstudio/python/lib/python3.14/site-packages/"
    expected = {
        "usr/bin/spacemissionstudio": "ISC",
        site + "spacemissionstudio/cli.py": "ISC",
        site + "spacemissionstudio/gui/assets/fonts/inter/Inter-Regular.ttf": "OFL-1.1",
        site + "spacemissionstudio/gui/assets/fonts/jetbrains-mono/JetBrainsMono-Regular.ttf": "OFL-1.1",
        site + "spacemissionstudio/gui/assets/icons/lucide/x.svg": "ISC and MIT",
        site + "Basilisk/__init__.py": "ISC",
        site + "PySide6/QtCore.abi3.so": "LGPL-3.0-only",
        site + "shiboken6/__init__.py": "LGPL-3.0-only",
        site + "numpy/__init__.py": "various",
        site + "supportData/EphemerisData/de430.bsp": "other",
        "opt/spacemissionstudio/python/bin/python3": "PSF-2.0",
    }
    assert {path: licence_of(path) for path in expected} == expected
    # The licence texts it points to are in the package.
    for folder in ("fonts/inter", "fonts/jetbrains-mono"):
        assert (root / "spacemissionstudio/gui/assets" / folder / "OFL.txt").is_file()
    assert (root / "spacemissionstudio/gui/assets/icons/lucide/LICENSE").is_file()
    control = (root / "packaging/deb/DEBIAN/control.in").read_text(encoding="utf-8")
    assert "Homepage: https://github.com/0h3xn4/basilisk-SpaceMissionStudio\n" in control

def test_file_record_of_an_unreadable_file_is_marked_not_raised(tmp_path):
    """Audit L26: a file that could be stat()ed but not read (permissions, or
    a folder) raised in the middle of a run's provenance record."""
    record = dependencies.file_record(tmp_path)  # a folder: stat works, open fails
    assert "unreadable" in record and "sha256" not in record
