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

"""How ``scripts/network_audit.py`` reads a strace record: which calls stay
on this computer and which reach, or would reach, another one. The lines
are as strace 6 writes them, taken from audits of this tool (the
addresses of the ones to another computer from a deliberate attempt)."""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "network_audit.py"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("network_audit", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOCAL = [
    '10033 connect(3, {sa_family=AF_UNIX, sun_path="/var/run/nscd/socket"}, 110) = -1 ENOENT (No such file or '
    'directory)',
    '200 connect(5, {sa_family=AF_INET, sin_port=htons(43239), sin_addr=inet_addr("127.0.0.1")}, 16) = -1 '
    'ECONNREFUSED (Connection refused)',
    '200 bind(5, {sa_family=AF_INET, sin_port=htons(0), sin_addr=inet_addr("127.0.0.1")}, 16) = 0',
    '311 bind(9, {sa_family=AF_NETLINK, nl_pid=0, nl_groups=00000000}, 12) = 0',
    '311 connect(12, {sa_family=AF_INET6, sin6_port=htons(8080), sin6_flowinfo=htonl(0), '
    'inet_pton(AF_INET6, "::1", &sin6_addr), sin6_scope_id=0}, 28) = 0',
]
EXTERNAL = [
    ('10033 connect(3, {sa_family=AF_INET, sin_port=htons(53), sin_addr=inet_addr("8.8.8.8")}, 16) = -1 '
     'ENETUNREACH (Network is unreachable)', "DNS"),
    ('12 connect(3, {sa_family=AF_INET, sin_port=htons(53), sin_addr=inet_addr("127.0.0.53")}, 16) = 0', "DNS"),
    ('77 connect(4, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("93.184.215.14")}, 16) = -1 '
     'ENETUNREACH (Network is unreachable)', "another computer"),
    ('78 sendto(4, "x", 1, 0, {sa_family=AF_INET6, sin6_port=htons(443), sin6_flowinfo=htonl(0), '
     'inet_pton(AF_INET6, "2606:2800:21f:cb07::1", &sin6_addr), sin6_scope_id=0}, 28) = 1', "another computer"),
    ('79 bind(6, {sa_family=AF_INET, sin_port=htons(5556), sin_addr=inet_addr("0.0.0.0")}, 16) = 0', "bound"),
]


def test_calls_that_stay_on_this_computer(audit):
    for line in LOCAL:
        entry = audit.classify(line)
        assert entry is not None and not entry["external"], line


@pytest.mark.parametrize("line,why", EXTERNAL)
def test_calls_that_reach_another_computer(audit, line, why):
    """Any address not on this computer, any DNS query (a local resolver
    asks others), and a socket other computers could connect to."""
    entry = audit.classify(line)
    assert entry["external"] and why.lower() in entry["why"].lower()


def test_a_local_proxy_counts_as_another_computer(audit, monkeypatch):
    """A connection to the proxy the environment configures on this
    computer would be relayed: found by the self-test in an environment
    with one."""
    monkeypatch.setattr(audit, "PROXY_PORTS", {45099})
    line = ('5 connect(4, {sa_family=AF_INET, sin_port=htons(45099), sin_addr=inet_addr("127.0.0.1")}, 16) = 0')
    assert audit.classify(line)["external"]


def test_other_lines_are_not_calls(audit):
    """A call on a connected socket (no address), a process's exit, and a
    signal are not counted again."""
    for line in ('5 sendto(4, "\\1\\2", 2, MSG_NOSIGNAL, NULL, 0) = 2', "5 +++ exited with 0 +++",
                 "5 --- SIGCHLD {si_signo=SIGCHLD} ---"):
        assert audit.classify(line) is None


def test_a_record_per_process_is_read_whole(audit, tmp_path):
    """``strace -ff`` writes one file per process; the programs started are
    listed and every call is classified."""
    (tmp_path / "strace.gui.txt.100").write_text(
        'execve("/usr/bin/python3", ["python3"], 0x7ffd /* 30 vars */) = 0\n' + LOCAL[1].split(" ", 1)[1] + "\n",
        encoding="utf-8")
    (tmp_path / "strace.gui.txt.101").write_text(
        'execve("/opt/Qt/libexec/QtWebEngineProcess", ["QtWebEngineProcess"], 0x7ffd /* 30 vars */) = 0\n'
        + EXTERNAL[2][0].split(" ", 1)[1] + "\n", encoding="utf-8")
    result = audit.analyse(tmp_path / "strace.gui.txt")
    assert result["programs_started"] == {"python3": 1, "QtWebEngineProcess": 1}
    assert result["processes_traced"] == 2 and len(result["calls"]) == 2
    assert [c["pid"] for c in result["external"]] == [101]
