# Network use, offline mode and telemetry

SpaceMissionStudio has **no telemetry**: no usage statistics, no crash
reports, no update check. It reaches the network only for a download you
start, and only the addresses listed for that download. This page says
what can reach the network, how that is enforced, how to switch
downloads off for good, and what is outside the tool's control.

## Contents

- [What can reach the network](#what-can-reach-the-network)
- [Offline mode](#offline-mode)
- [How it is enforced](#how-it-is-enforced)
- [The network log](#the-network-log)
- [Vizard](#vizard)
- [What this does not cover](#what-this-does-not-cover)
- [How it is tested](#how-it-is-tested)
- [Check it yourself](#check-it-yourself)

## What can reach the network

Each download is a *purpose* in `spacemissionstudio/network.py`, with the
only hosts it may contact (`spacemissionstudio network` prints this
list):

| Download | Hosts | Started by |
|---|---|---|
| Basilisk support data (SPICE kernels, gravity, magnetic field, albedo, atmosphere) | raw.githubusercontent.com, naif.jpl.nasa.gov, lambda.gsfc.nasa.gov, hanspeterschaub.info (Basilisk's backup) | **Download...** in the Reference data dialog, the start-up card, `kernels-status` |
| Space weather | celestrak.org | the same, and `spaceweather-download` |
| Earth orientation files | naif.jpl.nasa.gov | the same, and `earth-orientation --fetch` |
| Small-body ephemerides (433 Eros) | naif.jpl.nasa.gov | **Download...**, `small-bodies --fetch` |
| ITU-R P.676 tables | www.itu.int | **Download...**, `gaseous-attenuation --fetch` |

Everything else stays on your computer: a run, an export, a Monte Carlo
batch, the GUI's plots, the 3D model editor and **Results › 3D View**
(the run in 3D, drawn by the copy of three.js and the NASA images
bundled in the package), the IDM-CIC
import. Every file a
download fetches can also be installed from disk instead
([Reference data](../user-manual/reference-data.md)).

Software-in-the-loop runs talk to your program over a Unix socket or
127.0.0.1, never another computer.

## Offline mode

Offline, no download can start: **Download...** is off, the start-up card is not shown, and the commands that download
stop with the reason. Everything else works as before; files are
installed from disk.

| Who | How | Can the user change it? |
|---|---|---|
| You | **Settings > Network > Work offline**, or `spacemissionstudio network --offline on` | Yes |
| An administrator, for every user of a computer | the file `/etc/spacemissionstudio/policy.json` (Linux) or `%ProgramData%\SpaceMissionStudio\policy.json` (Windows) containing `{"offline": true}` | No: the setting is shown ticked and locked, and the reason is given |
| An administrator or a script, for one session | the environment variable `SPACEMISSIONSTUDIO_OFFLINE=1` | No |

An administrator's policy file that cannot be read counts as offline.
`spacemissionstudio network` shows the policy in effect and why.

## How it is enforced

- **One gateway.** The tool's own downloads all go through
  `network.open_url`, which refuses a URL that is not https or not one of
  its purpose's hosts, and refuses everything offline. A test fails if any
  other module imports a networking library or calls `urlopen`
  (`tests/test_network.py`).
- **A guard on all Python code.** The command line and the GUI turn on a
  Python audit hook (PEP 578) that sees every name lookup, connection and
  listening socket of any Python code in the process: the tool's,
  Basilisk's, a plugin's. It refuses those that reach another computer
  unless a download's permit for that host is open on the same thread,
  and it refuses listening on any address but 127.0.0.1. The processes the
  tool starts (runs, Monte Carlo workers) inherit it.
- **The web views load only the app's own pages.** The plots and the 3D
  view run in Qt WebEngine (Chromium). A request interceptor blocks any
  request that is not for a local file, and Chromium starts with its
  background requests off (`--disable-background-networking`,
  `--disable-component-update`, `--disable-domain-reliability`,
  `--no-pings`, `--dns-prefetch-disable`; `gui/webengine_setup.py`).
- **Basilisk's import-time request** (Basilisk 2.12.0 asks github.com for
  its release tag when it is imported) is sent to a closed port on your
  own computer (`spacemissionstudio/_offline.py`), so it never leaves it.

## The network log

Every network use allowed, and every attempt refused, is written to
`~/.spacemissionstudio/logs/network.log`, one line each: the time (UTC),
`permit` or `refused`, the download (or `-` for an attempt outside any
download, `web view` for a blocked page request) and the host or address.
**Settings > Network > Open the network log** opens it. A session that
downloaded nothing leaves no line.

## Vizard

Vizard, AVS Lab's separate 3D program, is made with Unity. The build AVS
Lab publishes has Unity Analytics switched on: its project settings
enable it and start it at launch, and the program contains Unity's
analytics libraries and AVS Lab's Unity project ID, with Unity's event
addresses (`cdp.cloud.unity3d.com`). It very likely sends usage data to
Unity when it runs (inspected 2026-11-09; not run here).

So, since 2026-11-09, SpaceMissionStudio:

- **never downloads Vizard** (the download and its network purpose are
  removed);
- **never looks for it**: only a Vizard the user chose in **Settings >
  Vizard** is started, and a copy an earlier version downloaded into
  `~/.cache/SpaceMissionStudio/vizard/` is ignored even if remembered;
- **shows runs in 3D itself:** **Results › 3D View**, drawn in the app's
  own web view, which loads only the app's files (the interceptor
  above) and is part of the network audit's GUI session.

Where Vizard is still wanted, use one built from its open source with
Unity's cloud services and analytics off, and check it with a firewall
(below).

## What this does not cover

- **A Vizard you choose** is a separate program: neither the guard nor
  the log sees it (above).
- **Code that is not Python.** The guard sees Python. Basilisk's C++
  modules make no network calls in a run except Vizard's live stream
  (`vizInterface`), which you start, on the address you give it. Chromium
  is covered by the interceptor and the flags above, not by the guard.
- **A user's own scripts.** A script that imports the package (the
  [Python API](../api.md)) is not guarded unless it calls
  `spacemissionstudio.network.install_guard()`; offline mode still applies
  to the tool's downloads.
- **Not a sandbox.** The policy file controls the tool, not the
  computer: someone who can run their own programs can reach the network
  with them. Where the network must be closed, close it at the operating
  system or the firewall too.

## How it is tested

| Test | What it shows |
|---|---|
| `tests/test_network.py` | Only the reviewed modules can reach the network; each download's URLs are among its hosts; the gateway refuses other hosts and http; the policy, its precedence and its lock; the guard's refusals, its permits per thread and per host, and a child process inheriting it; `spacemissionstudio network` |
| `tests/test_offline.py` | Validating, exporting and running a template need no network; a guarded run leaves the network log empty; the GUI starts with the download question declined and nothing is fetched. CI also runs it in a network namespace with no interface |
| `tests/gui/test_network_gui.py` | **Settings > Network**, the locked policy, Download and the start-up card offline; a web view's request for another computer is blocked and logged; Chromium's flags |
| `scripts/network_audit.py`, in CI on Linux | Every `connect`, `sendto`, `sendmsg` and `bind` of every process of a full GUI session (start-up with the download question unanswered, runs, plots, Compare, a Monte Carlo batch in worker processes, the 3D view, an IDM-CIC import, every Settings section) and a full command-line session, recorded by `strace` in a network namespace with no interface. A call to any address but this computer's, any DNS query, a connection to a local proxy or a socket other computers could reach fails the job, after a self-test shows a deliberate attempt is seen. The report lists every program started (Chromium's `QtWebEngineProcess` among them) and every call |
| `scripts/network_audit.py --method guard`, in CI on Windows | The same sessions; the guard's log must stay empty (Python code only) |
| `tests/test_network_audit.py` | How the audit classifies each kind of call |

The first audit (2026-11-09, Linux, Python 3.14, Basilisk 2.12.0) traced
53 processes and threads in the command-line session and 135 in the GUI
session (two of them Chromium's): 34 network calls, all to this
computer: Basilisk's import-time request to the closed local port, the
Monte Carlo workers' own sockets, Chromium asking for the local D-Bus,
the kernel asked for the network interfaces, the local name-service
cache (absent). None to another computer.

## Check it yourself

You need not trust the tests above. Any of these, on a computer of yours:

**Linux, every call of every process (about 3 minutes).** From the
source, with Basilisk, the `gui` extra and the reference data installed,
and `strace` (`sudo apt install strace`):

```bash
cd SpaceMissionStudio
python scripts/network_audit.py --out network-audit --self-test
```

It prints the report (also in `network-audit/report.md`; the raw
record is `network-audit/strace.*.txt*`). `PASSED` means no process
called, or tried to call, another computer. Where unprivileged user
namespaces are restricted (Ubuntu 24.04), first run
`sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`.

**Any computer, with the firewall (the strongest check: it needs
nothing from this project).** In a virtual machine or a spare computer:

1. Install SpaceMissionStudio from the installer and check its
   checksum against `SHA256SUMS-linux` or `SHA256SUMS-windows`.
2. Block all outgoing traffic and log what is blocked:
   - **Windows:** Windows Defender Firewall with Advanced Security:
     *Properties*, each profile: *Outbound connections: Block*; *Logging*:
     *Log dropped packets: Yes* (the log is
     `%systemroot%\system32\LogFiles\Firewall\pfirewall.log`). For a log
     with the program's path, also install Sysmon and read event 3
     (*Network connection*) in the Event Viewer.
   - **Linux:** for example with nftables:
     `sudo nft add table inet audit`,
     `sudo nft add chain inet audit out '{ type filter hook output priority 0; policy accept; }'`,
     `sudo nft add rule inet audit out oif != lo log prefix "sms-audit " drop`;
     blocked packets appear in `journalctl -k | grep sms-audit`.
3. Use SpaceMissionStudio as you normally would, for as long as you
   like: open your scenarios, run, look at the results, export. Leave the
   start-up question unanswered (or choose **Not now**).
4. Read the firewall's log: it should hold nothing from
   SpaceMissionStudio (`spacemissionstudio`, its `python`, or
   `QtWebEngineProcess`). Other programs of the computer may appear.
5. Then try **Download...** once: it must fail, and the network log
   (**Settings > Network > Open the network log**) and the firewall's log
   show the one host it tried.

**Offline mode.** Set it for every user as above, then check that
**Download...** is off and that `spacemissionstudio network` says
`Offline` and who set it.

**Vizard**, if you choose one, is a separate program: the audit script
does not start it. Watch it the same way with the firewall while it
shows a run. A build without analytics should show only its stream to
127.0.0.1.

---

**Next:** [Data, standards and the offline policy](data-and-standards.md) ·
[Known limitations](limitations.md) ·
[Documentation index](../README.md)
