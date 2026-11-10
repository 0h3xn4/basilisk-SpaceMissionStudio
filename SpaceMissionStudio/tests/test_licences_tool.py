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
"""The licence gate of the packages (packaging/legal/licences.py): SPDX expressions, the SBOM of a
small tree, and each way the check fails (milestone M1 of docs/legal/PHASE1_PLAN.md)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "packaging" / "legal" / "licences.py"
ALLOWED = {"MIT", "ISC", "Apache-2.0", "BSD-3-Clause", "OFL-1.1"}


@pytest.fixture(scope="module")
def licences():
    """The tool as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("smstudio_licences", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_dist(root: Path, name: str, version: str, metadata_extra: str = "", licence_file: bool = True) -> None:
    """A minimal installed distribution: its dist-info and one module."""
    info = root / f"{name}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n{metadata_extra}\n")
    files = [f"{name}/__init__.py", f"{name}-{version}.dist-info/METADATA", f"{name}-{version}.dist-info/RECORD"]
    (root / name).mkdir()
    (root / name / "__init__.py").write_text("")
    if licence_file:
        (info / "LICENSE").write_text("Permission is hereby granted ...")
        files.append(f"{name}-{version}.dist-info/LICENSE")
    (info / "RECORD").write_text("".join(f"{f},,\n" for f in files))


@pytest.mark.parametrize("expression, allowed", [
    ("MIT", True), ("MIT AND ISC", True), ("MIT AND GPL-2.0-only", False), ("GPL-2.0-only OR MIT", True),
    ("GPL-2.0-only OR AGPL-3.0-only", False), ("(MIT OR ISC) AND Apache-2.0", True),
    ("(GPL-3.0-only OR ISC) AND LGPL-2.1-only", False), ("MIT WITH Unknown-exception", False), ("", False),
    ("MIT AND", False),
])
def test_spdx_expressions_follow_the_allowlist(licences, expression, allowed):
    """AND needs both sides, OR needs one, WITH needs the exception to be allowed too; broken text fails."""
    assert licences.spdx_allowed(expression, ALLOWED) is allowed


def test_a_known_licence_passes(licences, tmp_path):
    """A distribution with a licence expression and a licence file passes with no problem."""
    make_dist(tmp_path, "goodpkg", "1.0", "License-Expression: MIT\n")
    sbom = licences.build_sbom(tmp_path, "t")
    assert licences.check(sbom, tmp_path, None) == []


def test_a_distribution_without_a_licence_fails(licences, tmp_path):
    """No expression, no usable classifier, no override: the gate fails and names the package."""
    make_dist(tmp_path, "mystery", "2.0", "Classifier: License :: OSI Approved :: BSD License\n")
    problems = licences.check(licences.build_sbom(tmp_path, "t"), tmp_path, None)
    assert any("mystery@2.0: no known licence" in p for p in problems)


def test_a_licence_off_the_allowlist_fails(licences, tmp_path):
    """A licence the project has not decided to redistribute fails the gate."""
    make_dist(tmp_path, "copyleft", "1.0", "License-Expression: AGPL-3.0-only\n")
    problems = licences.check(licences.build_sbom(tmp_path, "t"), tmp_path, None)
    assert any("AGPL-3.0-only" in p and "not on the allowlist" in p for p in problems)


def test_a_missing_licence_text_fails(licences, tmp_path):
    """A licence is not enough: the text must be in the package, or its source declared."""
    make_dist(tmp_path, "notext", "1.0", "License-Expression: MIT\n", licence_file=False)
    problems = licences.check(licences.build_sbom(tmp_path, "t"), tmp_path, None)
    assert any("notext@1.0: no licence text" in p for p in problems)


def test_a_file_nobody_owns_fails(licences, tmp_path):
    """A stray file in the tree is reported: nothing ships without a component that owns it."""
    make_dist(tmp_path, "goodpkg", "1.0", "License-Expression: MIT\n")
    (tmp_path / "stray.bin").write_bytes(b"x")
    problems = licences.check(licences.build_sbom(tmp_path, "t"), tmp_path, None)
    assert problems == ["unclaimed file (no component owns it): stray.bin"]


def test_bytecode_is_not_a_stray_file(licences, tmp_path):
    """Compiled caches are build by-products, not licensed files."""
    make_dist(tmp_path, "goodpkg", "1.0", "License-Expression: MIT\n")
    cache = tmp_path / "goodpkg" / "__pycache__"
    cache.mkdir()
    (cache / "x.cpython-314.pyc").write_bytes(b"x")
    assert licences.check(licences.build_sbom(tmp_path, "t"), tmp_path, None) == []


def test_the_notices_file_must_name_every_component(licences, tmp_path):
    """A notices file that leaves a component out fails; the generated one passes."""
    make_dist(tmp_path, "goodpkg", "1.0", "License-Expression: MIT\n")
    sbom = licences.build_sbom(tmp_path, "t")
    notices = tmp_path / "NOTICES"
    notices.write_text("nothing here")
    assert any("not named" in p for p in licences.check(sbom, tmp_path, notices))
    licences.write_notices(sbom, tmp_path, notices)
    assert licences.check(sbom, tmp_path, notices) == []
    assert "Permission is hereby granted" in notices.read_text()


def test_open_redistribution_is_a_warning_and_fails_only_when_strict(licences):
    """Data whose redistribution right is still open warns; --strict makes it fail."""
    sbom = {"components": [{
        "bom-ref": "dataset@1", "name": "dataset", "version": "1", "licenses": [{"expression": "MIT"}],
        "properties": [{"name": "smstudio:text-source", "value": "docs"},
                       {"name": "smstudio:redistribution-status", "value": "open"}],
    }], "properties": []}
    soft = licences.check(sbom, None, None)
    assert soft and soft[0].startswith("WARN")
    assert licences.check(sbom, None, None, strict=True)[0].startswith("dataset@1: redistribution right still open")


def test_a_restricted_data_set_fails_until_a_decision_is_recorded(licences):
    """A provider that forbids redistribution without permission stops the gate, even without --strict."""
    props = [{"name": "smstudio:text-source", "value": "docs"},
             {"name": "smstudio:redistribution-status", "value": "restricted"}]
    sbom = {"components": [{"bom-ref": "file@1", "name": "file", "version": "1", "licenses": [{"expression": "MIT"}],
                            "properties": props}], "properties": []}
    assert any("does not allow redistribution" in p for p in licences.check(sbom, None, None))
    props.append({"name": "smstudio:waived-by", "value": "docs/DECISIONS.md D-X"})
    assert licences.check(sbom, None, None) == []


def test_the_committed_data_files_are_consistent(licences):
    """Every id used in components.json is on the allowlist, and every declared text file exists."""
    allowed = licences.load_allowlist()
    for entry in licences.load_json("components.json")["components"]:
        assert licences.spdx_allowed(entry["licence"], allowed), entry["name"]
    texts = TOOL.parent / "texts" / "python-build-standalone-20261013"
    for entry in licences.load_json("components.json")["components"]:
        for pattern in entry.get("licence_match", []):
            if pattern.startswith("licenses/"):
                assert (texts / Path(pattern).name).is_file(), pattern
    json.loads((TOOL.parent / "overrides.json").read_text())
