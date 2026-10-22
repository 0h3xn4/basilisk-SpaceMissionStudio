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

"""How long switching plots in Results holds the GUI thread (UI overhaul
M6's criterion: under 50 ms; the plan's §3 measured up to 155 ms). Needs
Basilisk and the reference data. Offscreen::

    QT_QPA_PLATFORM=offscreen python scripts/measure_plot_switch.py [--template 23_] [--switches 12]

Runs the template once, then shows its plots one after the other in the
selected cell of the grid, as a click in the catalog does. For each
switch, a 2 ms heartbeat timer gives the longest gap from the switch to
1.5 s after it, and the time until the plot is drawn (the page reports
it). The runs are saved to a temporary folder, not the user's history.

The numbers are this machine's, software rendered; compare runs on one
machine, not across machines.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SETTLE_S = 1.5  # [s] after each switch


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="How long switching plots holds the GUI thread.")
    parser.add_argument("--template", default="23_", help="the template whose file name starts with this")
    parser.add_argument("--switches", type=int, default=12, help="plots shown one after the other")
    args = parser.parse_args(argv)

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.engine import run_store
    from spacemissionstudio.gui.app import freeze_start_up_objects
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(app)
    runs = Path(tempfile.mkdtemp(prefix="sms-plot-switch-"))
    run_store.default_root = lambda: runs  # keep this run out of the user's history
    from PySide6.QtCore import QSettings

    from spacemissionstudio.gui import results_widget

    layout_ini = str(runs / "layout.ini")  # and the plots it shows out of the user's saved layouts
    results_widget._settings = lambda: QSettings(layout_ini, QSettings.Format.IniFormat)

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
    freeze_start_up_objects()  # as the app does once its window is up
    results = window.results_widget
    drawn: list[float] = []
    # The page reports a plot drawn (M6a); before M6a, a page load drew it.
    signal = getattr(results, "plot_drawn", None) or results.web_view.loadFinished
    signal.connect(lambda *_args: drawn.append(time.perf_counter()))
    window.open_path(next(TEMPLATES_DIR.glob(f"{args.template}*.json")))
    spin(1.0)  # [s]
    window.on_run()
    deadline = time.perf_counter() + 600  # [s]
    while (window._run_worker is not None and window._run_worker.isRunning()) and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.001)  # [s]
    window.show_view(results)
    spin(3.0)  # [s] the first page, and plotly.js, loaded
    names = [name for name in results.plot_names() if name not in results.shown_plots()][:args.switches]
    last[0] = time.perf_counter()
    heartbeat.start()
    stalls, waits = [], []  # [ms]
    for name in names:
        count = len(drawn)
        start = time.perf_counter()
        results.show_series(name)
        spin(SETTLE_S)
        after = [ms for ended, ms in gaps if start <= ended <= start + SETTLE_S]
        stalls.append(max(after, default=0.0))
        waits.append((drawn[count] - start) * 1e3 if len(drawn) > count else float("nan"))
        print(f"{name:60s} longest stall {stalls[-1]:6.1f} ms, drawn after {waits[-1]:6.1f} ms", flush=True)
    heartbeat.stop()
    print(f"longest stall: {max(stalls):.1f} ms (median {statistics.median(stalls):.1f} ms); "
          f"drawn after at most {max(waits):.1f} ms (median {statistics.median(waits):.1f} ms)")
    window._dirty = False
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
