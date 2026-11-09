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
"""The one way SpaceMissionStudio reaches the network (security analysis
S-13, S-18; ``docs/reference/network.md``).

Every download the tool can make is a :data:`PURPOSES` entry: what it is
for and the only hosts it may contact. Nothing else may leave the
computer.

- :func:`open_url` is the only place the tool's own code opens a URL: it
  takes a purpose, refuses a host that is not that purpose's, and refuses
  everything when the tool is offline.
- :func:`permit` lets a library the tool calls (Basilisk's support-data
  fetch) reach a purpose's hosts while it is active, on this thread.
- :func:`install_guard` turns on a Python audit hook (PEP 578) that sees
  every name lookup, connection and bind any Python code in the process
  makes (the tool's, Basilisk's, a plugin's) and refuses those to another
  computer unless a :func:`permit` for that host is active on the same
  thread. The command line and the GUI turn it on at start; child
  processes (runs, Monte Carlo workers) inherit it through
  :data:`GUARD_VARIABLE`. A script that only imports the package keeps
  its own network use.
- **Offline:** :func:`policy` says whether downloads are allowed. An
  administrator can force offline mode for every user of a computer with
  a policy file (:func:`machine_policy_file`) or the
  :data:`OFFLINE_VARIABLE` environment variable; otherwise each user can
  choose it (:func:`set_user_offline`, **Settings > Network**,
  ``spacemissionstudio network --offline on``). Offline, :func:`permit`
  and :func:`open_url` refuse, so no download can start.

Every network use allowed, and every attempt refused, is written to
``~/.spacemissionstudio/logs/network.log`` (:func:`log_path`).

The guard covers Python code. The web views' Chromium processes are kept
to the app's own pages by ``gui.webengine_setup``'s request interceptor;
Vizard is a separate program (``docs/reference/network.md``).
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import sys
import threading
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

OFFLINE_VARIABLE = "SPACEMISSIONSTUDIO_OFFLINE"
GUARD_VARIABLE = "SPACEMISSIONSTUDIO_NETWORK_GUARD"
_TRUE = ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Purpose:
    """A download the tool can make: its ``label`` and the only ``hosts``
    it may contact."""

    key: str
    label: str
    hosts: tuple[str, ...]


PURPOSES: dict[str, Purpose] = {p.key: p for p in (
    Purpose("support_data", "Basilisk support data (SPICE kernels, gravity, magnetic field, albedo, atmosphere)",
            ("raw.githubusercontent.com", "naif.jpl.nasa.gov", "lambda.gsfc.nasa.gov", "hanspeterschaub.info")),
    Purpose("space_weather", "Space weather (CelesTrak)", ("celestrak.org",)),
    Purpose("earth_orientation", "Earth orientation files (NAIF)", ("naif.jpl.nasa.gov",)),
    Purpose("small_bodies", "Small-body ephemerides (NAIF)", ("naif.jpl.nasa.gov",)),
    Purpose("itu_p676", "ITU-R P.676 tables (ITU)", ("www.itu.int",)),
    Purpose("vizard", "The Vizard application (AVS Lab)", ("hanspeterschaub.info",)),
)}


class NetworkRefused(OSError):
    """A network use the policy does not allow. An ``OSError``, so code
    that handles a failed download handles this the same way."""


@dataclass(frozen=True)
class Policy:
    """Whether downloads are off (``offline``), whether the user can
    change it (``locked``) and why (``source``)."""

    offline: bool
    locked: bool
    source: str

    def describe(self) -> str:
        if not self.offline:
            return "Online: downloads start only when you ask for one."
        return f"Offline: no downloads ({self.source})."


# -- the policy ---------------------------------------------------------

def machine_policy_file() -> Path:
    """The administrator's policy file: ``/etc/spacemissionstudio/policy.json``
    on Linux, ``%ProgramData%\\SpaceMissionStudio\\policy.json`` on Windows.
    ``{"offline": true}`` forces offline mode for every user."""
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SpaceMissionStudio" / "policy.json"
    return Path("/etc/spacemissionstudio/policy.json")


def user_settings_file() -> Path:
    """The user's own choice (``{"offline": true}``)."""
    return Path.home() / ".spacemissionstudio" / "network.json"


def log_path() -> Path:
    return Path.home() / ".spacemissionstudio" / "logs" / "network.log"


def _read_offline(path: Path) -> bool | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return True if path == machine_policy_file() else None  # an unreadable machine policy is taken as offline
    value = data.get("offline") if isinstance(data, dict) else None
    return bool(value) if isinstance(value, bool) else None


def policy() -> Policy:
    """The policy in effect: the environment variable, then the
    administrator's file, then the user's choice; online by default."""
    value = os.environ.get(OFFLINE_VARIABLE, "").strip().lower()
    if value in _TRUE:
        return Policy(True, True, f"the {OFFLINE_VARIABLE} environment variable")
    machine = _read_offline(machine_policy_file())
    if machine:
        return Policy(True, True, f"set by your administrator in {machine_policy_file()}")
    if _read_offline(user_settings_file()):
        return Policy(True, False, "your choice in Settings > Network")
    return Policy(False, False, "")


def set_user_offline(offline: bool) -> Policy:
    """Save the user's choice; refused (``PermissionError``) while the
    policy is locked."""
    current = policy()
    if current.locked:
        raise PermissionError(f"offline mode is fixed ({current.source}); it cannot be changed here")
    path = user_settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"offline": bool(offline)}, indent=2) + "\n", encoding="utf-8")
    return policy()


# -- the log ------------------------------------------------------------

_log_lock = threading.Lock()


def _log(outcome: str, purpose: str, detail: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')}\t{outcome}\t{purpose}\t{detail}\n"
    try:
        with _log_lock:
            path = log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
    except OSError:
        pass  # the log is a record, never a reason for a download or a refusal to fail differently


# -- permits ------------------------------------------------------------

_local = threading.local()


def _proxy_hosts() -> set[str]:
    """The hosts of the proxies urllib and requests would use: a download
    through a proxy looks the proxy up, not the server."""
    import urllib.request  # here, not at import (see open_url)

    hosts = set()
    for url in urllib.request.getproxies().values():
        host = urllib.parse.urlsplit(url if "://" in url else f"http://{url}").hostname
        if host:
            hosts.add(host.lower())
    return hosts


@contextlib.contextmanager
def permit(purpose: str):
    """While active, on this thread, the purpose's hosts (and the proxy's)
    may be reached. Refused (:class:`NetworkRefused`) when offline."""
    entry = PURPOSES[purpose]
    current = policy()
    if current.offline:
        _log("refused", purpose, current.describe())
        raise NetworkRefused(f"{entry.label}: not downloaded. {current.describe()}")
    previous = getattr(_local, "scope", None)
    _local.scope = (purpose, frozenset(h.lower() for h in entry.hosts) | _proxy_hosts())
    _log("permit", purpose, " ".join(entry.hosts))
    try:
        yield entry
    finally:
        _local.scope = previous


def open_url(url: str, purpose: str, *, timeout_s: float, headers: dict | None = None):
    """``urllib.request.urlopen`` for a purpose's https URL, under its
    permit. The response is read inside the ``with`` block of the caller,
    which this returns a context manager for."""
    entry = PURPOSES[purpose]
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in entry.hosts:
        _log("refused", purpose, url)
        raise NetworkRefused(f"{url} is not one of the addresses allowed for {entry.label}")

    @contextlib.contextmanager
    def response():
        import urllib.request  # here, not at import: the package imports this module at start

        with permit(purpose):
            request = urllib.request.Request(url, headers=headers or {})  # noqa: S310 -- https, an allowed host
            with urllib.request.urlopen(request, timeout=timeout_s) as handle:  # noqa: S310 -- checked above
                yield handle

    return response()


# -- the guard ----------------------------------------------------------

_guard = {"installed": False, "active": False}
_LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}


def _is_local(host) -> bool:
    if host is None:
        return True  # getaddrinfo(None, port): a local address to bind
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host).strip("[]").lower()
    if host in _LOOPBACK_NAMES or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _target(event: str, args: tuple):
    """The host an audited event reaches, or None for one that stays on
    this computer (a Unix socket, a file descriptor)."""
    if event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex", "socket.gethostbyaddr"):
        return args[0], False
    if event in ("socket.connect", "socket.sendto", "socket.bind"):
        address = args[1]
        if isinstance(address, tuple) and address:
            return address[0], event == "socket.bind"
    return None


def _hook(event: str, args: tuple) -> None:
    if not _guard["active"] or not event.startswith("socket."):
        return
    found = _target(event, args)
    if found is None:
        return
    host, binding = found
    if binding:
        # A server reachable from other computers: never (SIL and the
        # tool's own sockets bind to 127.0.0.1).
        if host in ("", "0.0.0.0", "::") or not _is_local(host):  # noqa: S104 -- refused, not used
            _log("refused", "-", f"{event} {host!r}")
            raise NetworkRefused(f"listening on {host or 'all interfaces'} is not allowed; use 127.0.0.1")
        return
    if _is_local(host):
        return
    scope = getattr(_local, "scope", None)
    if scope is not None:
        purpose, hosts = scope
        name = host.decode() if isinstance(host, bytes) else str(host)
        if event in ("socket.connect", "socket.sendto") or name.lower() in hosts:
            return  # a name the permit allows was looked up; its address may be reached
        _log("refused", purpose, f"{event} {name}")
        raise NetworkRefused(f"{name} is not one of the addresses allowed for {PURPOSES[purpose].label}")
    _log("refused", "-", f"{event} {host}")
    raise NetworkRefused(f"network access to {host} refused: SpaceMissionStudio reaches the network only for a "
                         "download you start (see docs/reference/network.md)")


def install_guard() -> None:
    """Turn the guard on in this process and in the child processes it
    starts (they inherit :data:`GUARD_VARIABLE`)."""
    os.environ[GUARD_VARIABLE] = "1"
    _register()
    _guard["active"] = True


def guard_active() -> bool:
    return _guard["active"]


def _register() -> None:
    if not _guard["installed"]:
        sys.addaudithook(_hook)  # cannot be removed; it does nothing while the guard is off
        _guard["installed"] = True


def _from_environment() -> None:
    """At import: a process started by a guarded one is guarded too."""
    if os.environ.get(GUARD_VARIABLE, "").strip().lower() in _TRUE:
        _register()
        _guard["active"] = True


_from_environment()
