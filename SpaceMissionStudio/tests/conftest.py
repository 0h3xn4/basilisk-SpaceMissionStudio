"""Shared pytest fixtures/markers for the SpaceMissionStudio test suite.

Two independent "is this optional dependency installed" markers, both
auto-skipping (not failing collection, not silently passing) rather than
erroring the whole run when the corresponding install extra is missing:

* ``requires_basilisk``: needs a built Basilisk Python package. This
  development sandbox doesn't have one (see ``SpaceMissionStudio/README.md`` --
  a from-source build was attempted and failed because this sandbox's
  network policy blocks Conan Center).
* ``requires_gui``: needs PySide6 (the ``gui`` extra, ``pip install
  -e ".[gui]"``). Also forces ``QT_QPA_PLATFORM=offscreen`` before any Qt
  import happens (unless the environment already set ``QT_QPA_PLATFORM``
  explicitly) so the GUI test suite runs on a machine with no display --
  this is how it is genuinely exercised in this development sandbox too,
  not just designed to work that way in theory.
"""

import importlib.util
import logging
import os
import shutil
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

BASILISK_AVAILABLE = importlib.util.find_spec("Basilisk") is not None
# Where 'spacemissionstudio small-bodies --fetch' installs the Eros kernel for
# this user (CI runs it); the autouse fixture below hides it from other tests.
REAL_SMALL_BODIES_DIR = os.path.join(os.path.expanduser("~"), ".cache", "SpaceMissionStudio", "small_bodies")
GUI_AVAILABLE = importlib.util.find_spec("PySide6") is not None
# The exported flight-software package (spacemissionstudio.fsw_export) is
# built with CMake and the platform's C compiler; GitHub's Linux, macOS and
# Windows runners have both.
C_TOOLCHAIN_AVAILABLE = shutil.which("cmake") is not None and any(
    shutil.which(compiler) for compiler in ("cc", "gcc", "clang", "cl"))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_basilisk: test needs a built Basilisk Python package (auto-skipped without one)"
    )
    config.addinivalue_line(
        "markers", "requires_gui: test needs PySide6 (the 'gui' extra; auto-skipped without it)"
    )
    config.addinivalue_line(
        "markers", "requires_c_toolchain: test builds C code with CMake (auto-skipped without CMake and a compiler)"
    )
    config.addinivalue_line(
        "markers", "requirement(*ids): ECSS/CCSDS requirement IDs the test verifies (compliance/ traceability)"
    )
    config.addinivalue_line(
        "markers", "slow: takes about a minute or more (a full Basilisk run); CI runs it, "
                   "`pytest -m 'not slow'` leaves it out of a quick local run"
    )


@pytest.fixture(autouse=True)
def _isolate_logging_setup(tmp_path, monkeypatch):
    """``cli.main()``/``gui.app.main()`` both call ``logging_setup.
    configure_logging()`` for real -- and several tests (``test_cli.py``
    in particular) call ``cli.main()`` directly, not through a subprocess,
    so without this, the FIRST such test in the whole session would
    permanently mutate this test process's real root logger (adding a
    ``StreamHandler`` bound to whatever ``sys.stderr`` happened to be at
    that moment -- pytest's own per-test capture replaces ``sys.stderr``
    with a fresh object every test and closes the old one, so that
    handler would start raising "I/O operation on closed file" on every
    later test that logs anything) and would write real log files into
    this machine's actual ``~/.spacemissionstudio/logs``, neither of which any
    test should do as a side effect of something unrelated.

    Autouse (applies to literally every test, not just ``test_logging_
    setup.py``'s own) since the leak this prevents is caused by ANY test
    that happens to invoke a real entry point, not just tests that are
    themselves about logging.
    """
    from pathlib import Path

    from spacemissionstudio import logging_setup

    monkeypatch.setattr(logging_setup, "_log_file_path", None)
    monkeypatch.setattr(logging_setup, "_configured", False)
    # Patch Path.home() rather than default_log_dir() itself, so
    # default_log_dir()'s own logic (exercised directly by
    # test_default_log_dir_is_under_home_dot_spacemissionstudio) still runs for
    # real -- it just resolves under this test's tmp_path instead of the
    # real ~ -- rather than being replaced wholesale, which would make that
    # test observe this fixture's stand-in instead of the function it's
    # meant to test.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Same isolation for the space-weather cache, whose default directory
    # is computed from Path.home() once, at import time -- often during
    # test COLLECTION, before the patch above. Real bug: a real user's
    # full run then saw their actual ~/.cache startup-fetch CSV, and 20
    # template round-trip tests failed (they caught a real dialog bug, but
    # no test should depend on what is in the user's real cache).
    from spacemissionstudio.engine import spaceweather

    monkeypatch.setattr(spaceweather, "DEFAULT_CACHE_DIR", tmp_path / ".cache" / "SpaceMissionStudio" / "spaceweather")
    # The same for the Earth orientation files (engine.earth_orientation):
    # a test run never picks up the user's installed EOP kernels.
    from spacemissionstudio.engine import earth_orientation

    monkeypatch.setattr(earth_orientation, "DEFAULT_DIR", tmp_path / ".cache" / "SpaceMissionStudio" / "earth_orientation")
    monkeypatch.setattr(earth_orientation, "SYSTEM_DIR", tmp_path / "share" / "earth_orientation")
    # And for the small-body kernels (engine.small_bodies).
    from spacemissionstudio.engine import small_bodies

    monkeypatch.setattr(small_bodies, "DEFAULT_DIR", tmp_path / ".cache" / "SpaceMissionStudio" / "small_bodies")
    monkeypatch.setattr(small_bodies, "SYSTEM_DIR", tmp_path / "share" / "small_bodies")

    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    original_excepthook = sys.excepthook

    yield

    for handler in list(root_logger.handlers):
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
            handler.close()
    root_logger.setLevel(original_level)
    sys.excepthook = original_excepthook


def small_body_files_installed() -> bool:
    """The real Eros ephemeris kernel and shape model are installed."""
    from pathlib import Path

    from spacemissionstudio.engine import small_bodies

    try:
        return (small_bodies.installed("eros", Path(REAL_SMALL_BODIES_DIR)) is not None
                and small_bodies.shape_path(small_bodies.EROS) is not None)
    except ImportError:
        return False


@pytest.fixture
def real_small_body_files(monkeypatch):
    """Runs around Eros use the real installed files; skipped without them."""
    from pathlib import Path

    from spacemissionstudio.engine import small_bodies

    if not small_body_files_installed():
        pytest.skip("Eros ephemeris and shape not installed (spacemissionstudio small-bodies --fetch)")
    monkeypatch.setattr(small_bodies, "DEFAULT_DIR", Path(REAL_SMALL_BODIES_DIR))


@pytest.fixture
def eros_files_if_installed(monkeypatch) -> bool:
    """Whether the real Eros files are installed; when they are, runs use
    them (as real_small_body_files does), and nothing is skipped."""
    from pathlib import Path

    from spacemissionstudio.engine import small_bodies

    installed = small_body_files_installed()
    if installed:
        monkeypatch.setattr(small_bodies, "DEFAULT_DIR", Path(REAL_SMALL_BODIES_DIR))
    return installed


@pytest.fixture
def basilisk_unavailable(monkeypatch):
    """Basilisk cannot be imported for this test, as on a machine without
    it, though it is installed here.

    Every ``Basilisk`` module is replaced by None in ``sys.modules`` (an
    import of it raises ImportError, and ``importlib.util.find_spec``
    returns None), and the engine modules already imported are taken out,
    so the app's own ``from .engine... import`` runs again and meets the
    missing Basilisk. All of it is put back after the test.
    """
    monkeypatch.setitem(sys.modules, "Basilisk", None)
    for name in list(sys.modules):
        if name.startswith("Basilisk."):
            monkeypatch.setitem(sys.modules, name, None)
    for name in sorted((n for n in sys.modules if n.startswith("spacemissionstudio.engine.")),
                       key=lambda n: n.count("."), reverse=True):
        parent, _, child = name.rpartition(".")
        if parent in sys.modules:
            monkeypatch.delattr(sys.modules[parent], child, raising=False)
        monkeypatch.delitem(sys.modules, name)


def pytest_collection_modifyitems(config, items):
    skip_basilisk = pytest.mark.skip(reason="Basilisk is not installed/built in this environment")
    skip_gui = pytest.mark.skip(reason="PySide6 is not installed (pip install -e '.[gui]')")
    skip_c = pytest.mark.skip(reason="CMake and a C compiler are needed to build the exported flight software")
    for item in items:
        if not BASILISK_AVAILABLE and "requires_basilisk" in item.keywords:
            item.add_marker(skip_basilisk)
        if not GUI_AVAILABLE and "requires_gui" in item.keywords:
            item.add_marker(skip_gui)
        if not C_TOOLCHAIN_AVAILABLE and "requires_c_toolchain" in item.keywords:
            item.add_marker(skip_c)
