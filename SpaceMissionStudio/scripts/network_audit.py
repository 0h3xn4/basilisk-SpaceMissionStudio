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
"""Watch every network call of a full SpaceMissionStudio session (Linux).

Run from the ``SpaceMissionStudio`` folder, with Basilisk, the ``gui``
extra and the reference data installed, ``strace`` and ``unshare``::

    python scripts/network_audit.py --out network-audit

It runs two sessions, each in a network namespace with no interface but
loopback (``unshare -rn``: nothing can leave the computer) and under
``strace -f``, which records every ``connect``, ``sendto``, ``sendmsg`` and
``bind`` of every process and thread, the web views' Chromium processes
and the run and Monte Carlo worker processes included:

- **the GUI** (offscreen), as a user would use it: the start-up question
  left unanswered; templates opened; the Scenario, JSON and Overview pages;
  a run, its plots, Compare; a small Monte Carlo batch; the 3D model
  editor with its 3D view; an IDM-CIC import planned on the synthetic test
  model; the Reference data, Network and other settings; exports;
- **the command line**: validate, run with every export, lifetime, budget,
  design checks, model analyses, CCSDS export, IDM-CIC info and import,
  the network command.

Each recorded call is classified: to this computer (a Unix socket, the
kernel's netlink, 127.0.0.1 or ::1 on any port but 53) or **to another
computer** (any other address, any DNS query, even to a local resolver,
and a connection to a proxy the environment configures on this computer,
which would relay it). The session fails if there is one call of the second kind, or
a socket bound to any address but loopback. ``report.md`` and
``report.json`` in ``--out`` list every call; ``strace.<session>.txt``
holds the raw record.

``--no-isolate`` skips the network namespace (the calls are still
recorded; one to another computer could then leave it).

``--method guard`` is for Windows (no ``strace``): the same sessions run
as they are, and every network use of their Python code is read from
the guard's log (``network.log``): it must stay empty. It does not see
Chromium or code that is not Python; see ``docs/reference/network.md``
for watching those on Windows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACED = "connect,sendto,sendmsg,bind,execve"
_EXECVE = re.compile(r'^(?P<pid>\d+)\s+execve\("(?P<program>[^"]+)".*\)\s+=\s+0\s*$')
# What the local endpoints seen in practice are; listed in the report.
KNOWN_LOCAL = (
    ("nscd/socket", "the name service cache daemon (user, group and host lookups); absent on most systems"),
    ("dbus", "D-Bus, the desktop's local message bus (Chromium asks for it)"),
    ("pymp-", "Python multiprocessing's own sockets (the Monte Carlo workers)"),
    ("127.0.0.1", "this computer: Basilisk's import-time request sent to a closed local port (_offline.py), "
                  "or a software-in-the-loop channel"),
    ("AF_NETLINK", "the kernel, asked which network interfaces exist"),
)
_CALL = re.compile(r"^(?P<pid>\d+)\s+(?P<call>connect|sendto|sendmsg|bind)\((?P<args>.*)\)\s+=\s+(?P<result>.*)$")
_FAMILY = re.compile(r"sa_family=(AF_[A-Z0-9]+)")
_PORT = re.compile(r"sin6?_port=htons\((\d+)\)")
_ADDR4 = re.compile(r'sin_addr=inet_addr\("([^"]+)"\)')
_ADDR6 = re.compile(r'inet_pton\(AF_INET6, "([^"]+)"')
_UNIX = re.compile(r'sun_path=(@?"[^"]*"|@[^,}]*)')


def _proxy_ports() -> set[int]:
    """The ports of the proxies the environment configures on this computer:
    a connection to one would be relayed to another computer."""
    import urllib.parse
    import urllib.request

    ports = set()
    for scheme, url in urllib.request.getproxies().items():
        if scheme == "no":  # the hosts not to proxy, not a proxy
            continue
        parts = urllib.parse.urlsplit(url if "://" in url else f"http://{url}")
        try:
            port = parts.port
        except ValueError:
            continue
        if port and (parts.hostname or "").lower() in ("127.0.0.1", "localhost", "::1"):
            ports.add(port)
    return ports


PROXY_PORTS = _proxy_ports()


def classify(line: str) -> dict | None:
    """One strace line: the call, the address family, the address, and
    whether it reaches another computer. None for a line that is not a
    call (an exit, a signal, a resumed call's tail)."""
    match = _CALL.match(line.strip())
    if not match:
        return None
    args = match["args"]
    family = _FAMILY.search(args)
    family = family.group(1) if family else None
    entry = {"pid": int(match["pid"]), "call": match["call"], "family": family, "address": None, "port": None,
             "result": match["result"].strip(), "external": False, "why": ""}
    if family in ("AF_INET", "AF_INET6"):
        address = (_ADDR4.search(args) or _ADDR6.search(args))
        port = _PORT.search(args)
        entry["address"] = address.group(1) if address else "?"
        entry["port"] = int(port.group(1)) if port else None
        loopback = entry["address"].startswith("127.") or entry["address"] in ("::1", "::ffff:127.0.0.1")
        if match["call"] == "bind":
            if not loopback:
                entry["external"] = True
                entry["why"] = "a socket bound to an address other computers can reach"
        elif entry["port"] == 53:
            entry["external"] = True
            entry["why"] = "a DNS query (a name lookup)"
        elif loopback and entry["port"] in PROXY_PORTS:
            entry["external"] = True
            entry["why"] = "the proxy configured on this computer, which would relay it to another computer"
        elif not loopback:
            entry["external"] = True
            entry["why"] = "an address on another computer"
    elif family == "AF_UNIX":
        path = _UNIX.search(args)
        entry["address"] = path.group(1) if path else "?"
    elif family is None and match["call"] in ("sendto", "sendmsg"):
        return None  # on a connected socket: its connect was recorded and classified
    return entry


def analyse(trace: Path) -> dict:
    """Every call in a trace (one file per process, ``strace -ff``, or one
    file), classified, with the processes seen."""
    files = sorted(trace.parent.glob(trace.name + ".*")) or [trace]
    calls, pids, programs = [], set(), {}
    for path in files:
        pid_suffix = path.suffix.lstrip(".")
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw if raw[:1].isdigit() else f"{pid_suffix} {raw}"
            started = _EXECVE.match(line.strip())
            if started:
                name = Path(started["program"]).name
                programs[name] = programs.get(name, 0) + 1
                continue
            entry = classify(line)
            if entry is not None:
                calls.append(entry)
                pids.add(entry["pid"])
    families = {}
    for entry in calls:
        families[entry["family"] or "-"] = families.get(entry["family"] or "-", 0) + 1
    return {"calls": calls, "processes_with_calls": len(pids), "processes_traced": len(files),
            "programs_started": programs, "by_family": families,
            "external": [c for c in calls if c["external"]]}


def _what(text: str) -> str:
    return next((why for key, why in KNOWN_LOCAL if key in text), "")


# -- the sessions (run inside strace) -------------------------------------------

def _templates() -> Path:
    return ROOT / "spacemissionstudio" / "scenarios" / "templates"


def _short(name: str, folder: Path, days: float = 0.05, monte_carlo_runs: int | None = None) -> Path:
    """A copy of a template, shortened to ``days``."""
    data = json.loads((_templates() / name).read_text(encoding="utf-8"))
    data["sim_settings"]["duration_days"] = days
    if monte_carlo_runs is not None and data.get("monte_carlo"):
        data["monte_carlo"]["num_runs"] = monte_carlo_runs
    path = folder / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def session_cli(work: Path) -> None:
    """The command line, each command a process of its own."""
    exe = [sys.executable, "-m", "spacemissionstudio.cli"]
    scenario = _short("22_starter_first_leo_satellite.json", work)
    model = _short("32_smallsat_design_checks.json", work)
    sys.path.insert(0, str(ROOT / "tests"))
    from idm_fixtures import model_xml, write_idm

    idm = write_idm(work / "axessat.idm", model_xml("axessat"))
    commands = [
        ["validate", str(scenario)],
        ["run", str(scenario), "--out-dir", str(work / "run"), "--oem"],
        ["lifetime", str(scenario)],
        ["budget", str(_short("18_leo_station_keeping.json", work))],
        ["check-design", str(model)],
        ["model-analyses", str(model)],
        ["ccsds-export", str(scenario), "--out", str(work / "odm")],
        ["idm-info", str(idm)],
        ["idm-import", str(idm), str(scenario), "--spacecraft", "my-sat", "--devices", "--out", str(work / "imported.json")],
        ["network"],
    ]
    for args in commands:
        done = subprocess.run(exe + args, capture_output=True, text=True, timeout=1800)
        print(f"cli {args[0]}: status {done.returncode}", flush=True)


def session_gui(work: Path) -> None:
    """The GUI as a user would use it (see the module docstring)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from spacemissionstudio import network
    from spacemissionstudio.gui.theme import apply_theme

    network.install_guard()  # as gui.app.main does
    app = QApplication(sys.argv[:1])
    apply_theme(app)
    from spacemissionstudio.gui.main_window import MainWindow

    def spin(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)  # [s]

    def wait(done, limit_s: float, what: str) -> None:
        end = time.time() + limit_s
        while time.time() < end:
            app.processEvents()
            time.sleep(0.05)  # [s]
            if done():
                spin(1.0)  # [s]
                return
        raise SystemExit(f"timed out waiting for {what}")

    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard)
    batch_dir = work / "batch"
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(batch_dir))
    window = MainWindow(prompt_startup_fetch=True, check_autosave_recovery=False)  # the question, unanswered
    window.resize(1600, 900)
    window.show()
    spin(3.0)  # [s]
    print("gui: started", flush=True)

    window.open_path(_short("22_starter_first_leo_satellite.json", work))
    spin(2.0)  # [s]
    window.show_view(window.scenario_editor.scenario_page)
    window.scenario_editor.show_json()
    spin(2.0)  # [s]
    window.on_run()
    wait(lambda: len(window.run_history.runs) > 0 and not window._run_worker.isRunning(), 900.0, "a run")
    window.show_view(window.results_widget)
    spin(5.0)  # [s] the plots' web view loads plotly
    window.show_view(window.mission_view_widget)  # the built-in 3D view: its scene, its page, playing
    wait(lambda: window.mission_view_widget.scene is not None, 120.0, "the 3D view")
    spin(5.0)  # [s]
    window.mission_view_widget.toggle_play()
    spin(3.0)  # [s]
    window.mission_view_widget.pause()
    window.mission_view_widget.view_combo.setCurrentIndex(1)  # follow the spacecraft
    spin(2.0)  # [s]
    window.show_view(window.event_timeline_widget)
    spin(1.0)  # [s]
    window.on_run()
    wait(lambda: len(window.run_history.runs) > 1 and not window._run_worker.isRunning(), 900.0, "a second run")
    window.show_view(window.compare_widget)
    spin(5.0)  # [s]
    print("gui: runs, plots, 3D view, compare", flush=True)

    window.open_path(_short("25_monte_carlo_orbit_and_drag_dispersions.json", work, 0.05, monte_carlo_runs=2))
    spin(2.0)  # [s]
    window.on_run_monte_carlo()
    wait(lambda: window.monte_carlo_results_widget.batch is not None and not window._mc_worker.isRunning(),
         1800.0, "the Monte Carlo batch")
    window.show_view(window.monte_carlo_results_widget)
    spin(3.0)  # [s]
    print("gui: Monte Carlo batch", flush=True)

    window.open_path(_short("32_smallsat_design_checks.json", work))
    spin(2.0)  # [s]
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    scenario = window.scenario_editor.to_scenario()
    editor = ModelEditorDialog(scenario.spacecraft[0].model, spacecraft_name=scenario.spacecraft[0].name)
    editor.show()
    spin(8.0)  # [s] the 3D view
    editor.close()
    print("gui: 3D model editor", flush=True)

    sys.path.insert(0, str(ROOT / "tests"))
    from idm_fixtures import model_xml, write_idm

    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    dialog = IdmImportDialog(write_idm(work / "axessat.idm", model_xml("axessat")))
    dialog.show()
    wait(lambda: not dialog.busy() and dialog.plan() is not None, 120.0, "the IDM-CIC import plan")
    dialog.close()
    print("gui: IDM-CIC import planned", flush=True)

    for key, _title in window.settings_page.sections():
        window.show_view(window.settings_page)
        window.settings_page.show_section(key)
        spin(0.3)  # [s]
    window.data_panel_widget.refresh()
    spin(1.0)  # [s]
    window.close()
    spin(2.0)  # [s]
    print("gui: settings, reference data, closed", flush=True)


def session_selftest(work: Path) -> None:
    """A deliberate attempt to reach another computer, with no guard: the
    audit must see it (``--self-test``)."""
    import urllib.request

    try:
        urllib.request.urlopen("https://example.com/", timeout=5)  # noqa: S310 -- the attempt the audit must see
    except OSError as exc:
        print(f"selftest: {type(exc).__name__}", flush=True)


# -- driving ----------------------------------------------------------------------

def run_session(name: str, out: Path, isolate: bool) -> dict:
    """``name`` under strace (and in a network namespace), then analysed."""
    trace = out / f"strace.{name}.txt"
    for old in out.glob(trace.name + "*"):
        old.unlink()
    command = ["strace", "-f", "-ff", "-qq", "-s", "200", "-e", f"trace={TRACED}", "-o", str(trace),
               sys.executable, str(Path(__file__).resolve()), "--session", name]
    if isolate:
        command = ["unshare", "-rn"] + command
    started = time.time()
    done = subprocess.run(command, cwd=ROOT, timeout=7200, text=True, capture_output=True)
    (out / f"session.{name}.log").write_text(done.stdout + done.stderr, encoding="utf-8")
    result = analyse(trace)
    result.update(session=name, status=done.returncode, seconds=round(time.time() - started), isolated=isolate)
    return result


def run_session_guarded(name: str, out: Path) -> dict:
    """``name`` without strace: the guard's own log is the record."""
    from spacemissionstudio import network

    log = network.log_path()
    before = log.stat().st_size if log.exists() else 0
    started = time.time()
    done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--session", name], cwd=ROOT,
                          timeout=7200, text=True, capture_output=True)
    (out / f"session.{name}.log").write_text(done.stdout + done.stderr, encoding="utf-8")
    new = []
    if log.exists():
        with log.open(encoding="utf-8") as handle:
            handle.seek(before)
            new = [line.rstrip("\n") for line in handle if line.strip()]
    external = [{"pid": 0, "call": "guard", "family": "-", "address": line.split("\t")[-1], "port": None,
                 "result": line.split("\t")[1] if "\t" in line else line, "external": True,
                 "why": "a network use the guard logged"} for line in new]
    return {"session": name, "status": done.returncode, "seconds": round(time.time() - started), "isolated": False,
            "calls": external, "processes_with_calls": 0, "processes_traced": 0, "programs_started": {},
            "by_family": {}, "external": external, "method": "guard"}


def write_report(results: list[dict], out: Path) -> bool:
    ok = all(r["status"] == 0 and not r["external"] for r in results)
    (out / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    lines = ["# SpaceMissionStudio network audit", "",
             f"Result: **{'PASSED' if ok else 'FAILED'}**: "
             + ("no call reached, or tried to reach, another computer." if ok else "see below."), "",
             "| Session | Method | Status | Processes | Network calls | To this computer | To another computer | Time |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        local = len(r["calls"]) - len(r["external"])
        method = ("guard log (Python code only)" if r.get("method") == "guard" else
                  "strace, every process" + (", no network interface" if r["isolated"] else ""))
        lines.append(f"| {r['session']} | {method} | {r['status']} | {r['processes_traced']} | {len(r['calls'])} | {local} | "
                     f"{len(r['external'])} | {r['seconds']} s |")
    for r in results:
        if r.get("method") == "guard":
            lines += ["", f"## {r['session']}", "", "Read from the guard's log: "
                      + ("nothing logged." if not r["external"] else "")]
            lines += [f"- {c['result']}: {c['address']}" for c in r["external"]]
            continue
        lines += ["", f"## {r['session']}", "", "Programs started (each traced): "
                  + ", ".join(f"{k} ({v})" for k, v in sorted(r["programs_started"].items())) + ".", "",
                  "Calls by address family: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(r["by_family"].items())) + "."]
        if r["external"]:
            lines += ["", "To another computer:", ""]
            lines += [f"- pid {c['pid']} `{c['call']}` {c['family']} {c['address']}:{c['port']} ({c['why']}): "
                      f"{c['result']}" for c in r["external"]]
        local = sorted({(f"{c['call']} {c['family']} {c['address'] or ''}" + (":port" if c["port"] else "")).strip()
                        + f" = {c['result'].split(' ')[0]}" for c in r["calls"] if not c["external"]})
        if local:
            lines += ["", "To this computer (distinct; the port of a 127.0.0.1 address varies):", ""]
            lines += [f"- `{x}`" + (f": {_what(x)}" if _what(x) else "") for x in local]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("network-audit"))
    parser.add_argument("--sessions", default="cli,gui", help="cli, gui or both, comma separated")
    parser.add_argument("--no-isolate", action="store_true", help="do not use a network namespace")
    parser.add_argument("--method", choices=("strace", "guard"), default="strace",
                        help="strace (Linux: every call of every process) or guard (any OS: Python's, from the log)")
    parser.add_argument("--self-test", action="store_true",
                        help="first check that the audit sees a deliberate attempt to reach another computer")
    parser.add_argument("--session", help=argparse.SUPPRESS)  # internal: run one session (under strace)
    args = parser.parse_args()
    if args.session:
        with tempfile.TemporaryDirectory(prefix="sms-audit-") as folder:
            {"cli": session_cli, "gui": session_gui, "selftest": session_selftest}[args.session](Path(folder))
        return 0
    if args.method == "guard":
        args.out.mkdir(parents=True, exist_ok=True)
        results = [run_session_guarded(name.strip(), args.out.resolve())
                   for name in args.sessions.split(",") if name.strip()]
        ok = write_report(results, args.out)
        print((args.out / "report.md").read_text(encoding="utf-8"))
        return 0 if ok else 1
    for tool in ("strace",) + (() if args.no_isolate else ("unshare",)):
        if shutil.which(tool) is None:
            print(f"ERROR: {tool} is needed", file=sys.stderr)
            return 2
    args.out.mkdir(parents=True, exist_ok=True)
    if args.self_test:
        check = run_session("selftest", args.out.resolve(), not args.no_isolate)
        if not check["external"]:
            print("ERROR: self-test: the audit did not see a deliberate attempt to reach another computer",
                  file=sys.stderr)
            return 1
        print(f"Self-test: the audit sees a deliberate attempt ({check['external'][0]['why']}).")
    results = [run_session(name.strip(), args.out.resolve(), not args.no_isolate)
               for name in args.sessions.split(",") if name.strip()]
    ok = write_report(results, args.out)
    print((args.out / "report.md").read_text(encoding="utf-8"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
