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

"""How long the end of a run holds the GUI thread (UI overhaul M5's
criterion: no stall over 50 ms; the plan's §3 measured 256 ms). Needs
Basilisk and the reference data. Offscreen::

    QT_QPA_PLATFORM=offscreen python scripts/measure_run_end.py [--template 23_] [--runs 3]

Runs the template ``--runs`` times in one window (the first run of a
session also loads Plotly's page). For each run, a 2 ms heartbeat timer
gives the longest gap from the moment the run's "finished" slot starts to
3 s after it: the slot itself and whatever it leaves for later. The runs
are saved to a temporary folder, not the user's history.

The numbers are this machine's, software rendered; compare runs on one
machine, not across machines.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SETTLE_S = 3.0  # [s] after the end of the run


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="How long the end of a run holds the GUI thread.")
    parser.add_argument("--template", default="23_", help="the template whose file name starts with this")
    parser.add_argument("--runs", type=int, default=3, help="runs in one window")
    args = parser.parse_args(argv)

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.engine import run_store
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(app)
    runs = Path(tempfile.mkdtemp(prefix="sms-run-end-"))
    run_store.default_root = lambda: runs  # keep these runs out of the user's history

    gaps: list[tuple[float, float]] = []  # (when it ended, how long) [s], [ms]
    last = [time.perf_counter()]

    def tick():
        now = time.perf_counter()
        gaps.append((now, (now - last[0]) * 1e3))
        last[0] = now

    heartbeat = QTimer()
    heartbeat.setTimerType(Qt.PreciseTimer)
    heartbeat.setInterval(2)  # [ms]
    heartbeat.timeout.connect(tick)

    def spin(duration_s: float) -> None:
        end = time.perf_counter() + duration_s
        while time.perf_counter() < end:
            app.processEvents()
            time.sleep(0.001)  # [s]

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window.resize(1280, 720)  # [px]
    window.show()
    finished_at: list[float] = []
    slot_ms: list[float] = []
    real_finished = window._on_run_finished

    def finished(*a):
        t0 = time.perf_counter()
        finished_at.append(t0)
        real_finished(*a)
        slot_ms.append((time.perf_counter() - t0) * 1e3)

    window._on_run_finished = finished  # the worker's signal is connected at each run, to this
    path = next(TEMPLATES_DIR.glob(f"{args.template}*.json"))
    spin(0.5)  # [s]
    heartbeat.start()
    worst = 0.0  # [ms]
    for number in range(1, args.runs + 1):
        window.open_path(path)
        spin(1.5)  # [s]
        count = len(finished_at)
        window.on_run()
        deadline = time.perf_counter() + 600  # [s]
        while len(finished_at) == count and time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.001)  # [s]
        spin(SETTLE_S)
        if len(finished_at) == count:
            print(f"run {number}: did not finish")
            return 1
        start = finished_at[-1]
        after = [ms for ended, ms in gaps if ended >= start and ended <= start + SETTLE_S]
        longest = max(after, default=0.0)
        worst = max(worst, longest)
        print(f"run {number}: finished slot {slot_ms[-1]:6.1f} ms, longest stall {longest:6.1f} ms, "
              f"over 50 ms: {[round(ms) for ms in after if ms > 50]}", flush=True)
        window._dirty = False
    heartbeat.stop()
    print(f"worst stall: {worst:.1f} ms")
    window._dirty = False
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
