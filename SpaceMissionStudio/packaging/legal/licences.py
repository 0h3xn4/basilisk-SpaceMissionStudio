#!/usr/bin/env python3
#
# Licence: see ../../LICENSE. The copyright line of this file is decided in
# milestone M2 (docs/legal/PHASE1_PLAN.md, question 2).
#
"""Software bill of materials, licence gate and notices for SpaceMissionStudio's packages.

Standard library only, so it runs with the bundled Python of the installers.

Three sub-commands::

    licences.py sbom    --root TREE --name NAME --out sbom.cdx.json
    licences.py check   --sbom sbom.cdx.json [--root TREE] [--notices FILE]
    licences.py notices --sbom sbom.cdx.json --out THIRD_PARTY_NOTICES

``TREE`` is a folder that holds what a package holds: an unpacked wheel, the
``site-packages`` of a bundled Python, or the whole bundled Python. The SBOM
(CycloneDX 1.6, JSON) lists every Python distribution found by its
``*.dist-info`` folder and every other component named in ``components.json``.
A file that no component claims is listed under ``unclaimed`` and fails the
gate: nothing goes into a package without a known licence.

The data files (``components.json``, ``overrides.json``, ``allowlist.txt``)
are kept by hand and each entry names its evidence. Nothing here decides a
legal question: an entry whose licence is not clear is left out, and the gate
fails until a person has read the source and written the entry.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPDX_TOKEN = re.compile(r"\(|\)|[^\s()]+")
OPERATORS = {"AND", "OR", "WITH"}
#: Folders and suffixes that never hold a licensed file of their own.
IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc"}
#: Classifier to SPDX id, only where the classifier names exactly one licence.
CLASSIFIERS = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: BSD License": None,  # BSD-2 or BSD-3: not said
}
DIST_INFO_VERSION = re.compile(r"-[0-9][^/]*\.dist-info")
LICENCE_FILE_PATTERN = re.compile(r"(^|/)(LICEN[CS]E|COPYING|NOTICE|AUTHORS)[^/]*$", re.IGNORECASE)


def load_json(name: str) -> dict:
    """Read a data file of this folder."""
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def load_allowlist() -> set[str]:
    """SPDX ids that may be redistributed, from ``allowlist.txt``."""
    ids = set()
    for line in (HERE / "allowlist.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.add(line)
    return ids


def normalise(name: str) -> str:
    """PEP 503 name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def spdx_ids(expression: str) -> list[str]:
    """The licence ids in an SPDX expression, without operators and brackets."""
    return [t for t in SPDX_TOKEN.findall(expression) if t not in OPERATORS and t not in "()"]


def spdx_allowed(expression: str, allowed: set[str]) -> bool:
    """True when the expression is satisfied by the allowlist.

    ``A AND B`` needs both, ``A OR B`` needs one, ``A WITH E`` needs ``A``
    (an exception is a separate id and must itself be allowed). A short
    recursive-descent parser: ``or`` binds weaker than ``and``.
    """
    tokens = SPDX_TOKEN.findall(expression)
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else None

    def take():
        nonlocal position
        position += 1
        return tokens[position - 1]

    def parse_or() -> bool:
        result = parse_and()
        while peek() == "OR":
            take()
            right = parse_and()
            result = result or right
        return result

    def parse_and() -> bool:
        result = parse_atom()
        while peek() == "AND":
            take()
            right = parse_atom()
            result = result and right
        return result

    def parse_atom() -> bool:
        current = take()
        if current == "(":
            result = parse_or()
            take()  # ")"
            return result
        ok = current in allowed
        if peek() == "WITH":
            take()
            ok = ok and take() in allowed
        return ok

    try:
        result = parse_or()
    except IndexError:
        return False
    return result and position == len(tokens)


def sha256_of(path: Path) -> str:
    """SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_ignored(relative: Path) -> bool:
    """Files that are build by-products."""
    return bool(IGNORED_PARTS & set(relative.parts)) or relative.suffix in IGNORED_SUFFIXES


def all_files(root: Path) -> list[str]:
    """Every file under ``root`` as a POSIX path relative to it."""
    found = []
    for path in sorted(root.rglob("*")):
        if path.is_file() or path.is_symlink():
            relative = path.relative_to(root)
            if not is_ignored(relative):
                found.append(relative.as_posix())
    return found


def python_distributions(root: Path) -> list[dict]:
    """Components from every ``*.dist-info`` folder under ``root``."""
    overrides = load_json("overrides.json")["distributions"]
    components = []
    for info in sorted(root.rglob("*.dist-info")):
        if not (info / "METADATA").is_file():
            continue
        meta = Parser().parsestr((info / "METADATA").read_text(encoding="utf-8", errors="replace"))
        name, version = meta.get("Name", info.name), meta.get("Version", "")
        key = normalise(name)
        expression, basis = None, None
        override = overrides.get(key) or overrides.get(f"{key}=={version}")
        if override:
            expression, basis = override["licence"], "override: " + override["evidence"]
        elif meta.get("License-Expression"):
            expression, basis = meta["License-Expression"], "metadata License-Expression"
        else:
            found = {CLASSIFIERS.get(c) for c in meta.get_all("Classifier", []) if c.startswith("License ::")}
            found.discard(None)
            if len(found) == 1:
                expression, basis = found.pop(), "metadata classifier"
        files = [f for pattern in (override or {}).get("extra_licence_files", [])
                 for f in sorted(all_files(root)) if fnmatch.fnmatch(f, pattern)] if override else []
        for candidate in sorted(info.rglob("*")):
            relative = candidate.relative_to(root).as_posix()
            if candidate.is_file() and LICENCE_FILE_PATTERN.search(relative):
                files.append(relative)
        owned = owned_files(info, root)
        components.append({
            "type": "library", "name": name, "version": version, "key": key,
            "licence": expression, "licence_basis": basis,
            "licence_files": files, "holder": meta.get("Author") or meta.get("Author-email") or "",
            "url": meta.get("Home-page") or _project_url(meta), "claims": owned,
            "origin": "python-distribution",
        })
    return components


def _project_url(meta) -> str:
    """The first project URL of a distribution."""
    for entry in meta.get_all("Project-URL", []):
        return entry.split(",", 1)[-1].strip()
    return ""


def owned_files(info: Path, root: Path) -> list[str]:
    """Files a distribution lists in its RECORD, relative to ``root``."""
    record = info / "RECORD"
    if not record.is_file():
        return []
    base = info.parent
    owned = []
    for line in record.read_text(encoding="utf-8", errors="replace").splitlines():
        path = line.split(",", 1)[0]
        if not path:
            continue
        try:
            owned.append((base / path).resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            continue
    return owned


def matches(path: str, patterns: list[str]) -> bool:
    """True when a POSIX path matches one of the patterns (``*`` also crosses ``/``)."""
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def declared_components(files: list[str]) -> list[dict]:
    """Components of ``components.json`` that match at least one file.

    ``match`` lists the files the component owns, ``exclude`` removes some of
    them again, ``licence_match`` finds the component's licence texts inside
    the tree. A library linked into other files owns none: ``present_if``
    names the files that carry it.
    """
    declared = []
    for entry in load_json("components.json")["components"]:
        owned = [f for f in files if matches(f, entry.get("match", [])) and not matches(f, entry.get("exclude", []))]
        linked = any(matches(f, entry.get("present_if", [])) for f in files)
        if owned or linked:
            skip = ("match", "exclude", "licence_match", "present_if")
            item = {k: v for k, v in entry.items() if k not in skip}
            item["claims"] = owned
            item["licence_files"] = [f for f in files if matches(f, entry.get("licence_match", []))]
            item["origin"] = "declared"
            declared.append(item)
    return declared


def build_sbom(root: Path, name: str) -> dict:
    """The SBOM of a tree, as a dict."""
    files = all_files(root)
    components = python_distributions(root) + declared_components(files)
    claimed: set[str] = set()
    for component in components:
        claimed.update(component["claims"])
        claimed.update(component.get("licence_files", []))
    unclaimed = [f for f in files if f not in claimed]
    cyclonedx = []
    for component in components:
        entry = {
            "type": component.get("type", "library"), "bom-ref": f'{component["name"]}@{component["version"]}',
            "name": component["name"], "version": component["version"],
            "licenses": [{"expression": component["licence"]}] if component.get("licence") else [],
            "publisher": component.get("holder", ""), "externalReferences":
                [{"type": "website", "url": component["url"]}] if component.get("url") else [],
            "properties": [
                {"name": "smstudio:licence-basis", "value": component.get("licence_basis") or "none"},
                {"name": "smstudio:origin", "value": component["origin"]},
                {"name": "smstudio:files", "value": str(len(component["claims"]))},
            ] + [{"name": "smstudio:licence-file", "value": f} for f in component.get("licence_files", [])]
              + ([{"name": "smstudio:copyright", "value": component["copyright"]}] if component.get("copyright") else [])
              + ([{"name": "smstudio:redistribution", "value": component["redistribution"]}]
                 if component.get("redistribution") else [])
              + ([{"name": "smstudio:redistribution-status", "value": component["redistribution_status"]}]
                 if component.get("redistribution_status") else [])
              + ([{"name": "smstudio:text-source", "value": component["text_source"]}]
                 if component.get("text_source") else [])
              + ([{"name": "smstudio:text-in-zip", "value": component["text_in_zip"]}]
                 if component.get("text_in_zip") else [])
              + ([{"name": "smstudio:waived-by", "value": component["waived_by"]}]
                 if component.get("waived_by") else []),
        }
        cyclonedx.append(entry)
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {"component": {"type": "application", "name": name}},
        "components": cyclonedx,
        "properties": [{"name": "smstudio:unclaimed", "value": f} for f in unclaimed]
        + [{"name": "smstudio:file-count", "value": str(len(files))}],
    }


def find_archive(root: Path, archive: str) -> Path | None:
    """A zip named relative to a package root, or, in a larger tree, the first file of that name."""
    if (root / archive).is_file():
        return root / archive
    return next(iter(sorted(root.rglob(Path(archive).name))), None)


def licence_text_present(component: dict, root: Path | None) -> bool:
    """A component has a licence text inside the package, or a declared source for it."""
    props = {p["name"]: p["value"] for p in component["properties"] if p["name"] != "smstudio:licence-file"}
    if "smstudio:text-source" in props:
        return True
    zipped = props.get("smstudio:text-in-zip")
    if zipped and root is not None:
        archive, member = zipped.split("!", 1)
        found = find_archive(root, archive)
        if found is None:
            return False
        with zipfile.ZipFile(found) as bundle:
            return member in bundle.namelist()
    return any(p["name"] == "smstudio:licence-file" for p in component["properties"])


def check(sbom: dict, root: Path | None, notices: Path | None, strict: bool = False) -> list[str]:
    """Problems that fail the gate. ``WARN`` lines (data whose redistribution right is still open)
    fail only with ``strict``."""
    allowed = load_allowlist()
    problems: list[str] = []
    warnings: list[str] = []
    for component in sbom["components"]:
        ref = component["bom-ref"]
        if not component["licenses"]:
            problems.append(f"{ref}: no known licence (add it to overrides.json with its evidence)")
            continue
        expression = component["licenses"][0]["expression"]
        if not spdx_allowed(expression, allowed):
            problems.append(f"{ref}: licence {expression!r} is not on the allowlist")
        if not licence_text_present(component, root):
            problems.append(f"{ref}: no licence text in the package and no text source declared")
        status = {p["name"]: p["value"] for p in component["properties"]}.get("smstudio:redistribution-status")
        if status == "restricted":
            waived = {p["name"]: p["value"] for p in component["properties"]}.get("smstudio:waived-by")
            if not waived:
                problems.append(f"{ref}: the provider does not allow redistribution without permission; "
                                "get the permission, stop bundling it, or record a decision (waived_by)")
        elif status == "open" and strict:
            problems.append(f"{ref}: redistribution right still open (docs/legal/DATA_TERMS.md)")
        elif status == "open":
            warnings.append(f"WARN {ref}: redistribution right still open (docs/legal/DATA_TERMS.md)")
    for prop in sbom["properties"]:
        if prop["name"] == "smstudio:unclaimed":
            problems.append(f"unclaimed file (no component owns it): {prop['value']}")
    if notices is not None:
        if not notices.is_file():
            problems.append(f"notices file missing: {notices}")
        else:
            text = notices.read_text(encoding="utf-8")
            for component in sbom["components"]:
                if component["name"] not in text:
                    problems.append(f"{component['bom-ref']}: not named in {notices.name}")
    return problems + warnings


def write_notices(sbom: dict, root: Path | None, out: Path) -> None:
    """THIRD_PARTY_NOTICES: one entry per component, then each distinct licence text once."""
    lines = [
        "THIRD-PARTY NOTICES", "",
        "SpaceMissionStudio redistributes the components below. Each is under its own",
        "licence. The text of every licence follows the list. This file is generated by",
        "packaging/legal/licences.py from the package's contents; do not edit it by hand.", "",
    ]
    texts: dict[str, tuple[str, list[str]]] = {}
    zipped: dict[str, str] = {}
    for component in sorted(sbom["components"], key=lambda c: c["name"].lower()):
        props = {}
        files = []
        for p in component["properties"]:
            if p["name"] == "smstudio:licence-file":
                files.append(p["value"])
            else:
                props[p["name"]] = p["value"]
        expression = component["licenses"][0]["expression"] if component["licenses"] else "UNKNOWN"
        own = component["name"] == "spacemissionstudio"  # its version changes at every release
        lines += [f"* {component['name']}" + ("" if own else f" {component['version']}"), f"  Licence: {expression}"]
        if props.get("smstudio:copyright"):
            lines.append(f"  Copyright: {props['smstudio:copyright']}")
        elif component.get("publisher"):
            lines.append(f"  Author: {component['publisher']}")
        for ref in component.get("externalReferences", []):
            lines.append(f"  Source: {ref['url']}")
        if props.get("smstudio:redistribution"):
            lines.append(f"  Redistribution: {props['smstudio:redistribution']}")
        for file in files:
            lines.append(f"  Licence text: {DIST_INFO_VERSION.sub('.dist-info', file)}")
            if root is not None and (root / file).is_file():
                body = (root / file).read_text(encoding="utf-8", errors="replace").strip()
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
                texts.setdefault(digest, (file, []))[1].append(component["name"])
        if props.get("smstudio:text-in-zip") and root is not None:
            archive, member = props["smstudio:text-in-zip"].split("!", 1)
            found = find_archive(root, archive)
            if found is not None:
                with zipfile.ZipFile(found) as bundle:
                    body = bundle.read(member).decode("utf-8", errors="replace").strip()
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
                lines.append(f"  Licence text: {member} inside {archive}")
                texts.setdefault(digest, (f"{member} inside {archive}", []))[1].append(component["name"])
                zipped[digest] = body
        lines.append("")
    lines += ["", "LICENCE TEXTS", "=============", ""]
    for digest, (file, users) in texts.items():
        lines += [f"--- {DIST_INFO_VERSION.sub('.dist-info', file)} ({', '.join(users)}) [{digest}] ---", ""]
        body = zipped[digest] if digest in zipped else (root / file).read_text(encoding="utf-8", errors="replace").strip()
        lines += [body, "", ""]
    out.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("sbom")
    one.add_argument("--root", type=Path, required=True)
    one.add_argument("--name", required=True)
    one.add_argument("--out", type=Path, required=True)
    two = sub.add_parser("check")
    two.add_argument("--sbom", type=Path, required=True)
    two.add_argument("--root", type=Path)
    two.add_argument("--notices", type=Path)
    two.add_argument("--strict", action="store_true", help="fail on open redistribution rights too")
    three = sub.add_parser("notices")
    three.add_argument("--sbom", type=Path, required=True)
    three.add_argument("--root", type=Path)
    three.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "sbom":
        sbom = build_sbom(args.root, args.name)
        args.out.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
        print(f"{args.out}: {len(sbom['components'])} components")
        return 0
    sbom = json.loads(args.sbom.read_text(encoding="utf-8"))
    if args.command == "notices":
        write_notices(sbom, args.root, args.out)
        print(f"{args.out} written")
        return 0
    lines = check(sbom, args.root, args.notices, args.strict)
    failures = [line for line in lines if not line.startswith("WARN")]
    for line in lines:
        print(line if line.startswith("WARN") else "FAIL " + line)
    print(f"{len(sbom['components'])} components, {len(failures)} failures, {len(lines) - len(failures)} warnings")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
