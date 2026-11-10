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

"""The one way the tool reaches the network (``spacemissionstudio/network.py``,
security analysis S-18): the code that can reach it is the reviewed list;
each download contacts only its own hosts; the offline policy and who can
change it; the guard that refuses any other Python network use, here and
in the processes a guarded one starts; the log. No test here reaches
another computer: every allowed lookup is of a name the guard lets through
before the operating system is asked, and is answered by a stub."""

import ast
import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from spacemissionstudio import cli, network

_PACKAGE = Path(network.__file__).resolve().parent

# Every module that imports something able to reach another computer, and
# why it may. A new one fails the test below until it is reviewed and added.
REVIEWED = {
    "network.py": {"urllib.request"},  # open_url: the purposes' https URLs, under a permit
    "_offline.py": {"socket"},  # a closed port on 127.0.0.1 for Basilisk's import-time request
    "engine/kernels.py": {"pooch"},  # pooch.file_hash only; Basilisk's fetch runs under permit("support_data")
    "sil/transport.py": {"socket"},  # the SIL program's channel: a Unix socket or 127.0.0.1
}
_NETWORK_MODULES = ("socket", "urllib.request", "http.client", "http.server", "requests", "urllib3", "pooch",
                    "PySide6.QtNetwork", "ftplib", "smtplib", "xmlrpc", "asyncio", "websockets", "zmq", "ssl",
                    "socketserver", "imaplib", "poplib")


def _network_imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
        for name in names:
            found.update(m for m in _NETWORK_MODULES if name == m or name.startswith(m + "."))
    return found


def test_only_the_reviewed_modules_can_reach_the_network():
    """Every module of the package that imports a networking library is in
    :data:`REVIEWED`, with exactly those libraries; ``urlopen`` is called
    in ``network.py`` only."""
    found = {}
    for path in sorted(_PACKAGE.rglob("*.py")):
        imports = _network_imports(path)
        if imports:
            found[path.relative_to(_PACKAGE).as_posix()] = imports
    assert found == REVIEWED
    callers = sorted({path.relative_to(_PACKAGE).as_posix() for path in _PACKAGE.rglob("*.py")
                      for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                      if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", ""))
                      == "urlopen"})
    assert callers == ["network.py"]


def test_every_download_is_a_purpose_with_https_hosts():
    """The downloads the tool can make, by purpose; the URLs the code uses
    are among each purpose's hosts."""
    from spacemissionstudio.engine import earth_orientation, gaseous_attenuation, small_bodies, spaceweather

    assert set(network.PURPOSES) == {"support_data", "space_weather", "earth_orientation", "small_bodies",
                                     "itu_p676"}
    uses = [("space_weather", url) for url in spaceweather.CELESTRAK_URLS.values()]
    uses += [("earth_orientation", earth_orientation.NAIF_PCK_URL), ("itu_p676", gaseous_attenuation.PART1_URL)]
    uses += [("small_bodies", body.spk_url) for body in small_bodies.BODIES.values()]
    for purpose, url in uses:
        host = url.split("/")[2]
        assert url.startswith("https://") and host in network.PURPOSES[purpose].hosts, (purpose, url)


def test_open_url_refuses_another_host_or_scheme():
    for url in ("https://example.com/SW-All.csv", "http://celestrak.org/SpaceData/SW-All.csv"):
        with pytest.raises(network.NetworkRefused, match="not one of the addresses"):
            network.open_url(url, "space_weather", timeout_s=1)


@pytest.fixture
def no_machine_policy(monkeypatch, tmp_path):
    """The administrator's policy file is one in tmp_path (absent at first)."""
    path = tmp_path / "machine" / "policy.json"
    monkeypatch.setattr(network, "machine_policy_file", lambda: path)
    monkeypatch.delenv(network.OFFLINE_VARIABLE, raising=False)
    return path


def test_the_policy_and_who_can_change_it(no_machine_policy, monkeypatch):
    """Online by default; the user's choice; the administrator's file and the
    environment variable force offline and lock it; an unreadable policy
    file counts as offline."""
    assert network.policy() == network.Policy(False, False, "")
    assert network.set_user_offline(True).offline
    assert not network.policy().locked and "your choice" in network.policy().source
    network.set_user_offline(False)
    no_machine_policy.parent.mkdir(parents=True)
    no_machine_policy.write_text(json.dumps({"offline": True}), encoding="utf-8")
    current = network.policy()
    assert current.offline and current.locked and "administrator" in current.source
    with pytest.raises(PermissionError, match="administrator"):
        network.set_user_offline(False)
    no_machine_policy.write_text("{not json", encoding="utf-8")
    assert network.policy().offline
    no_machine_policy.unlink()
    monkeypatch.setenv(network.OFFLINE_VARIABLE, "1")
    assert network.policy().locked and network.OFFLINE_VARIABLE in network.policy().source


def test_offline_no_download_can_start(no_machine_policy, monkeypatch):
    """Offline, a permit is refused before anything is looked up, and
    Basilisk's support data is only read from its cache."""
    from spacemissionstudio.engine import kernels

    network.set_user_offline(True)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("a download started offline"))
    with pytest.raises(network.NetworkRefused, match="Offline"):
        with network.open_url("https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/", "earth_orientation",
                              timeout_s=1):
            pass
    monkeypatch.setattr(kernels, "get_path", lambda kernel: pytest.fail("Basilisk's fetch was called offline"))
    monkeypatch.setattr(kernels, "cached_statuses", lambda files: ["cached only"])
    assert kernels.ensure_kernels(list(kernels.ALL_SUPPORT_DATA_FILES)[:1]) == ["cached only"]


@pytest.fixture
def guard():
    network.install_guard()


def _allowed(event: str, args: tuple) -> bool:
    """Whether the guard lets an audited event through (it is called
    directly: an allowed lookup must not reach the operating system here)."""
    try:
        network._hook(event, args)
    except network.NetworkRefused:
        return False
    return True


def test_the_guard_refuses_other_computers_outside_a_permit(guard):
    """Outside a permit, no name is looked up and no address reached, by
    any Python code (the real socket calls raise the audit events); this
    computer stays reachable (SIL, the local closed port), and nothing may
    listen on another interface."""
    for host in ("example.com", "celestrak.org"):
        with pytest.raises(network.NetworkRefused, match="refused"):
            socket.getaddrinfo(host, 443)
    with socket.socket() as sock, pytest.raises(network.NetworkRefused):
        sock.connect(("93.184.215.14", 443))
    assert socket.getaddrinfo("localhost", 0) and socket.getaddrinfo("127.0.0.1", 0)
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
    with socket.socket() as server, pytest.raises(network.NetworkRefused, match="listening on 0.0.0.0"):
        server.bind(("0.0.0.0", 0))  # noqa: S104 -- refused
    assert _allowed("socket.connect", (None, "/tmp/sil.sock"))  # noqa: S108 -- a Unix socket path, not a file


def test_a_permit_opens_its_hosts_only(guard):
    """Inside a permit, its hosts may be looked up and reached; another host
    is refused; so is everything once the permit ends, and on another
    thread."""
    import threading

    lookup = ("naif.jpl.nasa.gov", 443, 0, 0, 0)
    with network.permit("earth_orientation"):
        assert _allowed("socket.getaddrinfo", lookup) and _allowed("socket.connect", (None, ("137.78.1.1", 443)))
        assert not _allowed("socket.getaddrinfo", ("example.com", 443, 0, 0, 0))
        elsewhere = []
        thread = threading.Thread(target=lambda: elsewhere.append(_allowed("socket.getaddrinfo", lookup)))
        thread.start()
        thread.join()
        assert elsewhere == [False]
    assert not _allowed("socket.getaddrinfo", lookup)


def test_a_download_goes_through_the_gateway_and_is_logged(guard, monkeypatch, no_machine_policy):
    """``spaceweather.fetch`` opens CelesTrak's URL through the gateway, with
    the tool's user agent; the log says so."""
    from spacemissionstudio.engine import spaceweather

    sent = []

    class Response:
        def __init__(self, data):
            self._data = data

        def read(self, n=-1):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        sent.append(request)
        return Response(b"DATE,BSRN\n")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(spaceweather, "_install", lambda dest, data, url: dest)
    spaceweather.fetch("SW-All", force=True)
    assert sent[0].full_url == spaceweather.CELESTRAK_URLS["SW-All"] and sent[0].get_header("User-agent")
    log = network.log_path().read_text(encoding="utf-8")
    assert "\tpermit\tspace_weather\tcelestrak.org" in log


def test_a_process_started_by_a_guarded_one_is_guarded(tmp_path):
    """A child (a run, a Monte Carlo worker) inherits the guard through the
    environment: its own lookup is refused."""
    env = dict(os.environ, **{network.GUARD_VARIABLE: "1"}, HOME=str(tmp_path))
    code = ("import socket, spacemissionstudio\n"
            "try:\n    socket.getaddrinfo('example.com', 443)\n    print('reached')\n"
            "except OSError as exc:\n    print(type(exc).__name__)\n")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert out.stdout.strip() == "NetworkRefused", out.stderr


def test_the_network_command(no_machine_policy, capsys):
    """``spacemissionstudio network`` shows the policy and each download's
    hosts; --offline on/off sets the user's choice, refused when locked."""
    assert cli.main(["network", "--offline", "on"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Offline: no downloads (your choice") and "celestrak.org" in out
    assert network.guard_active()  # the command line turned the guard on
    assert cli.main(["network", "--offline", "off"]) == 0
    assert capsys.readouterr().out.startswith("Online")
    os.environ[network.OFFLINE_VARIABLE] = "1"
    try:
        assert cli.main(["network", "--offline", "off"]) == 2
        assert "cannot be changed" in capsys.readouterr().err
    finally:
        del os.environ[network.OFFLINE_VARIABLE]
