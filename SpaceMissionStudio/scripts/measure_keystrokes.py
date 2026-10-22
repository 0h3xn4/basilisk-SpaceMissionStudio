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

"""How long a keystroke holds the GUI thread, on every template (UI
overhaul M4's criterion: no keystroke stalls more than 50 ms). Offscreen::

    QT_QPA_PLATFORM=offscreen python scripts/measure_keystrokes.py [--only 04_] [--repeat 3]

For each template, five keystrokes in the scenario's name field, each
followed by 600 ms of settling. Two numbers per keystroke, as
``scripts/measure_ui_baseline.py`` takes them:

- the call: the time ``setText`` takes (what the baseline's
  ``keystroke_max_ms`` is);
- the stall: the longest gap of a 2 ms heartbeat timer in the settling time,
  which is the work an edit leaves for later (the explanation after its
  250 ms wait, the undo snapshot, the autosave).

The numbers are this machine's, software rendered; compare runs on one
machine, not across machines.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SETTLE_S = 0.6  # [s] after each keystroke: the 250 ms explanation wait, its worker, the 300 ms snapshot


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="How long a keystroke holds the GUI thread, on every template.")
    parser.add_argument("--only", default="", help="only the templates whose file name starts with this")
    parser.add_argument("--repeat", type=int, default=1, help="measure each template this many times")
    args = parser.parse_args(argv)
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.engine import run_store
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(app)
    runs = Path(tempfile.mkdtemp(prefix="sms-ui-keys-"))
    run_store.default_root = lambda: runs  # keep these runs out of the user's history

    gaps: list[float] = []
    last = [time.perf_counter()]

    def tick():
        now = time.perf_counter()
        gaps.append((now - last[0]) * 1e3)
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
    spin(0.5)  # [s]
    heartbeat.start()
    worst_call = worst_stall = 0.0  # [ms]
    paths = [path for path in sorted(TEMPLATES_DIR.glob(f"{args.only}*.json")) for _ in range(args.repeat)]
    for path in paths:
        window.open_path(path)
        spin(1.0)  # [s] the open's own work settles
        base = window.scenario_editor.name_edit.text()
        calls, stalls = [], []
        for i in range(5):
            t0 = time.perf_counter()
            window.scenario_editor.name_edit.setText(base + "x" * (i + 1))
            calls.append((time.perf_counter() - t0) * 1e3)
            last[0] = time.perf_counter()
            gaps.clear()
            spin(SETTLE_S)
            stalls.append(max(gaps, default=0.0))
        worst_call, worst_stall = max(worst_call, max(calls)), max(worst_stall, max(stalls))
        print(f"{path.stem:52s} call max {max(calls):5.1f} ms  stall max {max(stalls):5.1f} ms", flush=True)
        window._dirty = False
    heartbeat.stop()
    print(f"worst: call {worst_call:.1f} ms, stall {worst_stall:.1f} ms")
    window._dirty = False
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
