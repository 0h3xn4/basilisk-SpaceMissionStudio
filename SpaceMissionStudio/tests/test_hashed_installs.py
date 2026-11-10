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

"""The installers' packages are hash-checked and listed in a bill of
materials (``packaging/hash_constraints.py``, ``packaging/bundle_python.py``):
the hashed pins match ``constraints.txt``; the private Python is built
with ``pip install --require-hashes --only-binary=:all:``; a package that
is not pinned stops the build; the SBOM names every package with the file
installed and its SHA-256."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_PACKAGING = Path(__file__).resolve().parents[1] / "packaging"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _PACKAGING / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hashes():
    return _load("hash_constraints")


@pytest.fixture(scope="module")
def bundle():
    sys.path.insert(0, str(_PACKAGING))
    try:
        return _load("bundle_python")
    finally:
        sys.path.remove(str(_PACKAGING))


def test_the_hashed_pins_are_the_pins(hashes):
    """``constraints-hashes.txt`` names every package of
    ``constraints.txt`` at the same version, each with SHA-256 digests;
    changing a pin without running the script fails here."""
    assert hashes.check() == []
    pins = hashes.read_pins(hashes.HASHED)
    assert len(pins) == len(hashes.read_pins(hashes.CONSTRAINTS)) and pins["tzdata"][1]
    assert all(digests for _, _, digests in pins.values())


def test_a_changed_pin_is_reported(hashes, tmp_path):
    """A version that differs, a pin without digests and a hashed package
    that is not pinned are each named."""
    constraints, hashed = tmp_path / "c.txt", tmp_path / "h.txt"
    constraints.write_text("six==1.17.0\nidna==3.20\n", encoding="utf-8")
    hashed.write_text("# header\nsix==1.16.0 --hash=sha256:" + "a" * 64 + "\nextra==1 --hash=sha256:xyz\n",
                      encoding="utf-8")
    problems = hashes.check(constraints, hashed)
    assert any("six: 1.17.0" in p for p in problems)
    assert any("idna==3.20 has no digests" in p for p in problems)
    assert any("extra is in" in p for p in problems)


@pytest.mark.parametrize("filename,keep", [
    ("numpy-2.4.6-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", True),
    ("numpy-2.4.6-cp314-cp314-win_amd64.whl", True),
    ("numpy-2.4.6-cp314-cp314t-win_amd64.whl", False),
    ("numpy-2.4.6-cp313-cp313-win_amd64.whl", False),
    ("pyerfa-2.0.1.5-cp39-abi3-win_amd64.whl", True),
    ("six-1.17.0-py2.py3-none-any.whl", True),
    ("numpy-2.4.6.tar.gz", True),
])
def test_only_files_python_3_14_can_install_are_recorded(hashes, filename, keep):
    """CPython 3.14 and abi3 wheels, pure-Python wheels and the source
    archive; not another CPython's, nor the free-threaded build's."""
    assert hashes.installable(filename) is keep


def test_a_package_reached_but_not_pinned_is_found(hashes):
    """The closure on each platform: pandas needs tzdata on Windows only."""
    releases = {
        "pandas": {"info": {"requires_dist": ['tzdata; sys_platform == "win32"', "six"]}},
        "six": {"info": {"requires_dist": None}},
        "spacemissionstudio": ["pandas"],
    }
    pins = {"pandas": ("pandas", "3", []), "six": ("six", "1", [])}
    assert hashes.unpinned(pins, releases, ["spacemissionstudio"]) == ["tzdata (windows)"]
    pins["tzdata"] = ("tzdata", "1", [])
    releases["tzdata"] = {"info": {"requires_dist": []}}
    assert hashes.unpinned(pins, releases, ["spacemissionstudio"]) == []


def test_the_private_python_is_installed_hash_checked(bundle, monkeypatch, tmp_path):
    """Each install runs with --require-hashes and --only-binary=:all:
    against the hashed pins; the wheel on disk carries its own SHA-256;
    pip's report is returned for the SBOM."""
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        listing = Path(args[args.index("-r") + 1]).read_text(encoding="utf-8")
        calls.append(listing)
        Path(args[args.index("--report") + 1]).write_text(json.dumps({"install": [{"metadata": {"name": "x"}}]}))

    monkeypatch.setattr(bundle.subprocess, "run", run)
    wheel = tmp_path / "spacemissionstudio-9.9.9-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    report = bundle.pip_install(Path("python"), _PACKAGING / "constraints-hashes.txt", [bundle.local_wheel(wheel)])
    args, listing = calls
    assert "--require-hashes" in args and "--only-binary=:all:" in args
    assert args[args.index("-c") + 1].endswith("constraints-hashes.txt")
    assert listing.startswith(f"spacemissionstudio[gui] @ {wheel.as_uri()} --hash=sha256:")
    assert bundle.sha256_of(wheel) in listing and report == [{"metadata": {"name": "x"}}]
    assert "constraints-hashes.txt" in (_PACKAGING / "bundle_python.py").read_text(encoding="utf-8")  # the default


def test_a_package_not_pinned_stops_the_build(bundle):
    """After the install, every package must be a pin at its version; the
    CPython build's own (pip) and ours are not counted."""
    pins = {"numpy": ("numpy", "2.4.6", ["a"]), "six": ("six", "1.17.0", ["b"])}
    own = {"pip", "spacemissionstudio"}
    assert bundle.not_pinned(["numpy==2.4.6", "pip==25.2", "spacemissionstudio==2.5.0", "six==1.17.0"],
                             pins, own) == []
    assert bundle.not_pinned(["numpy==2.4.5", "evil==1.0"], pins, own) == [
        "numpy==2.4.5 is pinned at 2.4.6", "evil==1.0 is not pinned"]


def test_the_bill_of_materials(bundle, monkeypatch):
    """CycloneDX 1.6: the CPython build, each package with its purl, file,
    SHA-256 and licence, and each data file with its SHA-256; our own
    package is the subject, not a component."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1762646400")
    manifest = {"spacemissionstudio": "2.6.0", "python": "3.14.8", "python_build": "https://example.org/cpython.tgz",
                "python_build_sha256": "c" * 64,
                "data_files": [{"path": "lib/supportData/de430.bsp", "size_bytes": 1, "sha256": "d" * 64}]}
    report = [
        {"metadata": {"name": "PySide6_Essentials", "version": "6.11.2", "license": "LGPLv3"},
         "download_info": {"url": "https://files.pythonhosted.org/p.whl",
                           "archive_info": {"hashes": {"sha256": "e" * 64}}}},
        {"metadata": {"name": "numpy", "version": "2.4.6", "license_expression": "BSD-3-Clause"},
         "download_info": {"url": "https://files.pythonhosted.org/n.whl",
                           "archive_info": {"hashes": {"sha256": "f" * 64}}}},
        {"metadata": {"name": "six", "version": "1.17.0",
                      "classifier": ["License :: OSI Approved :: MIT License"]},
         "download_info": {"url": "https://files.pythonhosted.org/s.whl", "archive_info": {}}},
        {"metadata": {"name": "spacemissionstudio", "version": "2.6.0"},
         "download_info": {"url": "file:///build/spacemissionstudio-2.6.0-py3-none-any.whl"}},
    ]
    bom = bundle.sbom("linux", manifest, report)
    assert (bom["bomFormat"], bom["specVersion"]) == ("CycloneDX", "1.6")
    assert bom["serialNumber"].startswith("urn:uuid:") and bom["metadata"]["timestamp"] == "2025-11-09T00:00:00Z"
    assert bom["metadata"]["component"]["purl"] == "pkg:pypi/spacemissionstudio@2.6.0"
    by_ref = {c["bom-ref"]: c for c in bom["components"]}
    assert by_ref["cpython"]["hashes"][0]["content"] == "c" * 64
    numpy = by_ref["pkg:pypi/numpy@2.4.6"]
    assert numpy["licenses"] == [{"expression": "BSD-3-Clause"}] and numpy["hashes"][0]["content"] == "f" * 64
    assert by_ref["pkg:pypi/pyside6-essentials@6.11.2"]["licenses"] == [{"license": {"name": "LGPLv3"}}]
    assert by_ref["pkg:pypi/six@1.17.0"]["licenses"] == [{"license": {"name": "MIT License"}}]
    assert "hashes" not in by_ref["pkg:pypi/six@1.17.0"]
    assert by_ref["file:lib/supportData/de430.bsp"]["type"] == "file"
    assert not any("spacemissionstudio@" in ref for ref in by_ref)


# The modules the installers leave out (legal decision D9: GPL-only Qt
# modules, Tcl/Tk, dbm), on file names of the real Linux and Windows bundles.
_PRUNED = [
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6Quick3D.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6Graphs.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6VirtualKeyboard.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6WaylandCompositor.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6QmlCompiler.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/plugins/assetimporters/libassimp.so",
    "lib/python3.14/site-packages/PySide6/Qt/plugins/qmllint/libquicklintplugin.so",
    "lib/python3.14/site-packages/PySide6/Qt/qml/QtQuick/Timeline/qmldir",
    "lib/python3.14/site-packages/PySide6/QtHttpServer.abi3.so",
    "lib/python3.14/site-packages/PySide6/QtNetworkAuth.pyi",
    "lib/python3.14/lib-dynload/_tkinter.cpython-314-x86_64-linux-gnu.so",
    "lib/python3.14/lib-dynload/_dbm.cpython-314-x86_64-linux-gnu.so",
    "lib/python3.14/tkinter/__init__.py",
    "lib/python3.14/idlelib/idle.py",
    "lib/tcl9.0/init.tcl",
    "lib/libtcl9.0.so",
    "bin/idle3",
    "Lib/site-packages/PySide6/Qt6Quick3D.dll",
    "Lib/site-packages/PySide6/qml/QtQuick/VirtualKeyboard/qmldir",
    "DLLs/_tkinter.pyd",
    "DLLs/tcl90.dll",
    "DLLs/tcl9tk90.dll",
    "DLLs/libtommath.dll",
    "tcl/tcl9.0/init.tcl",
]
_KEPT = [
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6WebEngineCore.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6Quick.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/lib/libQt6Qml.so.6",
    "lib/python3.14/site-packages/PySide6/Qt/qml/Qt5Compat/GraphicalEffects/qmldir",
    "lib/python3.14/site-packages/PySide6/QtWebEngineWidgets.abi3.so",
    "lib/python3.14/site-packages/PySide6/QtSvg.abi3.so",
    "lib/python3.14/dbm/__init__.py",
    "lib/python3.14/turtle_like_name_kept_by_nobody.py",
    "lib/python3.14/site-packages/matplotlib/backends/backend_tkagg.py",
    "Lib/site-packages/PySide6/Qt6WebEngineCore.dll",
    "Lib/threading.py",
    "DLLs/zlib1.dll",
    "DLLs/_ssl.pyd",
]


@pytest.mark.parametrize("layout", ["linux", "windows"])
def test_the_unused_modules_are_removed_and_the_ones_the_app_needs_kept(bundle, tmp_path, layout):
    """Legal decision D9: the GPL-only Qt modules, the plugins that load them, Tcl/Tk and _dbm leave
    the bundle; Qt WebEngine, Qt Quick, Qt Qml and the rest of the standard library stay. Each layout in
    a folder of its own: on Windows, ``Lib`` and ``lib`` would be the same folder."""
    windows = ("Lib/", "DLLs/", "tcl/")
    pruned = [p for p in _PRUNED if p.startswith(windows) == (layout == "windows")]
    kept = [p for p in _KEPT if p.startswith(windows) == (layout == "windows")]
    for relative in pruned + kept:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    removed = bundle.prune_unused(tmp_path)
    assert sorted(removed) == sorted(pruned)
    assert all((tmp_path / relative).is_file() for relative in kept)
    if layout == "linux":
        assert not (tmp_path / "lib/python3.14/tkinter").exists()  # its emptied folder goes too


def test_no_qt_module_the_app_imports_is_pruned(bundle):
    """Every ``PySide6.Qt*`` module the app imports survives the pruning, on Linux and Windows."""
    package = Path(__file__).resolve().parents[1] / "spacemissionstudio"
    imported = set()
    for source in package.rglob("*.py"):
        imported.update(re.findall(r"PySide6\.(Qt\w+)", source.read_text(encoding="utf-8")))
    assert {"QtCore", "QtGui", "QtWidgets", "QtWebEngineWidgets"} <= imported
    for module in imported:
        for relative in (f"lib/python3.14/site-packages/PySide6/{module}.abi3.so",
                         f"lib/python3.14/site-packages/PySide6/Qt/lib/libQt6{module[2:]}.so.6",
                         f"Lib/site-packages/PySide6/Qt6{module[2:]}.dll"):
            assert not bundle.PRUNE_QT.search(relative), relative


def test_the_qt_source_archives_match_the_pinned_pyside6():
    """Legal decision D8: every release carries the source of the Qt and PySide6 it bundles. The
    archives named in packaging/legal/qt-sources.json must be those of the PySide6 version pinned in
    constraints.txt, each with a size and a SHA-256; a PySide6 update without new archives fails here."""
    spec = json.loads((_PACKAGING / "legal" / "qt-sources.json").read_text(encoding="utf-8"))
    pins = dict(line.split("==", 1) for line in (_PACKAGING / "constraints.txt").read_text(encoding="utf-8").splitlines()
                if "==" in line and not line.startswith("#"))
    version = pins["PySide6"].strip()
    assert spec["pyside6_version"] == version
    names = [archive["name"] for archive in spec["archives"]]
    assert names == [f"qt-everywhere-src-{version}.tar.xz", f"pyside-setup-everywhere-src-{version}.tar.xz"]
    for archive in spec["archives"]:
        assert archive["url"].startswith("https://download.qt.io/official_releases/") and archive["url"].endswith(archive["name"])
        assert archive["size_bytes"] > 0 and re.fullmatch(r"[0-9a-f]{64}", archive["sha256"])


def test_the_texts_of_pruned_libraries_are_not_copied(bundle):
    """The licence gate fails on a licence text no component owns: the texts of the libraries that
    leave with ``_tkinter`` and ``_dbm`` are not copied, and every other vendored text is."""
    vendored = {path.name for path in bundle.PBS_LICENCE_TEXTS.glob("LICENSE.*.txt")}
    assert bundle.PRUNED_LIBRARY_TEXTS <= vendored
    assert {"LICENSE.openssl-3.txt", "LICENSE.sqlite.txt", "LICENSE.zstd.txt"} <= vendored - bundle.PRUNED_LIBRARY_TEXTS



#: The files of python-build-standalone 20261013's Windows build (install_only_stripped, listed
#: 2026-11-10) after pruning, one or a few of each kind, with what the licence gate must make of them.
_WINDOWS_TREE = [
    "python.exe", "pythonw.exe", "python3.dll", "python314.dll", "LICENSE.txt", "vcruntime140.dll",
    "vcruntime140_1.dll", "libs/python314.lib", "include/Python.h", "Scripts/.empty", "Lib/os.py",
    "Lib/threading.py", "Lib/dbm/dumb.py", "Lib/site-packages/README.txt", "DLLs/_ssl.pyd",
    "DLLs/_hashlib.pyd", "DLLs/_ctypes.pyd", "DLLs/_sqlite3.pyd", "DLLs/pyexpat.pyd", "DLLs/_decimal.pyd",
    "DLLs/_lzma.pyd", "DLLs/_bz2.pyd", "DLLs/_zstd.pyd", "DLLs/libcrypto-3-x64.dll", "DLLs/libssl-3-x64.dll",
    "DLLs/libffi-8.dll", "DLLs/sqlite3.dll", "DLLs/zlib1.dll",
]


def test_the_licence_gate_knows_every_file_of_the_windows_python(bundle, tmp_path):
    """On the Windows layout every file has an owner and every library its text, and there is no finding:
    the Microsoft runtime is redistributed on the conditions in CPython's Windows LICENSE.txt (owner's
    decision D10, 2026-11-10). Tcl/Tk, which the
    pruning removed, is not reported: matching is case-sensitive, so ``lib/thread*`` no longer claims
    ``Lib/threading.py``."""
    for name in _WINDOWS_TREE:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"x")
    licences = _load_licences()
    (tmp_path / "licenses").mkdir()
    for text in bundle.PBS_LICENCE_TEXTS.glob("LICENSE.*.txt"):
        if text.name not in bundle.PRUNED_LIBRARY_TEXTS | bundle.LINUX_ONLY_LIBRARY_TEXTS:
            (tmp_path / "licenses" / text.name).write_bytes(text.read_bytes())
    sbom = licences.build_sbom(tmp_path, "windows-test")
    names = {component["name"] for component in sbom["components"]}
    assert {"CPython", "OpenSSL 3", "SQLite", "libffi", "expat", "mpdecimal", "zlib", "zstd", "bzip2"} <= names
    assert not any(name.startswith(("Tcl", "Tix", "X11", "Berkeley", "libedit", "ncurses")) for name in names)
    problems = licences.check(sbom, tmp_path, None)
    assert problems == []


def _load_licences():
    import importlib.util
    spec = importlib.util.spec_from_file_location("smstudio_licences_win", _PACKAGING / "legal" / "licences.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
