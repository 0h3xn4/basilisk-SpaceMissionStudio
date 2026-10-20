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

"""The GUI's responsiveness baseline for the UI overhaul
(docs/ui/UI_OVERHAUL.md): startup to the first interactive window, tab and
page switching, and the heaviest interactions, each as the longest time the
GUI thread did not return to the event loop. Offscreen::

    QT_QPA_PLATFORM=offscreen python scripts/measure_ui_baseline.py --out docs/ui/perf_baseline.json

A 2 ms heartbeat timer notes every gap between its ticks; a gap is a stall,
time in which the window could not repaint or take input. Each interaction
reports its own call time (synchronous work on the GUI thread) and the
longest stall in the settling time after it (deferred work: queued signals,
timers, web view loads). Startup runs in fresh processes, three times.
The numbers are this machine's, software rendered; compare runs on one
machine, not across machines.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BUDGET_MS = 50.0  # [ms] the brief's limit for one stretch of GUI-thread work
EXAMPLE = "23_starter_complete_small_satellite.json"


def startup_once() -> dict:
    """In a fresh process: the time from the interpreter's start to the
    first event-loop turn after the main window is shown, by stage."""
    t_spawn = float(os.environ.get("SMS_SPAWN_TIME", time.time()))
    t0 = time.perf_counter()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    t_qt = time.perf_counter()
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme
    t_import = time.perf_counter()
    app = QApplication(sys.argv[:1])
    apply_theme(app)
    t_app = time.perf_counter()
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    t_window = time.perf_counter()
    window.resize(1440, 900)
    window.show()
    t_show = time.perf_counter()
    stages = {}

    def first_turn():
        t_idle = time.perf_counter()
        stages.update({
            "interpreter_to_script_ms": (time.time() - t_spawn) * 1e3 - (t_idle - t0) * 1e3,
            "import_qt_ms": (t_qt - t0) * 1e3,
            "import_gui_ms": (t_import - t_qt) * 1e3,
            "application_and_theme_ms": (t_app - t_import) * 1e3,
            "main_window_constructor_ms": (t_window - t_app) * 1e3,
            "show_ms": (t_show - t_window) * 1e3,
            "show_to_first_idle_ms": (t_idle - t_show) * 1e3,
            "spawn_to_interactive_ms": (time.time() - t_spawn) * 1e3,
        })
        app.quit()

    QTimer.singleShot(0, first_turn)
    app.exec()
    window._dirty = False
    window.close()
    return stages


def interactions() -> list[dict]:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.engine import run_store
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(app)
    runs = Path(tempfile.mkdtemp(prefix="sms-ui-perf-"))
    run_store.default_root = lambda: runs  # keep these runs out of the user's history
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

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
    heartbeat.start()

    def spin(duration_s: float) -> None:
        end = time.perf_counter() + duration_s
        while time.perf_counter() < end:
            app.processEvents()
            time.sleep(0.001)  # [s]

    results: list[dict] = []

    def measure(name: str, action, settle_s: float = 1.5) -> None:
        spin(0.3)  # [s] quiet before
        gaps.clear()
        last[0] = time.perf_counter()
        t0 = time.perf_counter()
        action()
        call_ms = (time.perf_counter() - t0) * 1e3
        spin(settle_s)
        stall_ms = max(gaps) if gaps else call_ms
        over = sum(1 for g in gaps if g > BUDGET_MS)
        results.append({"interaction": name, "call_ms": round(call_ms, 1), "longest_stall_ms": round(stall_ms, 1),
                        "stalls_over_budget": over})
        print(f"{name:60s} call {call_ms:8.1f} ms  longest stall {stall_ms:8.1f} ms  over {BUDGET_MS:.0f} ms: {over}",
              flush=True)

    def wait(done, limit_s: float) -> None:
        end = time.perf_counter() + limit_s
        while time.perf_counter() < end and not done():
            app.processEvents()
            time.sleep(0.005)  # [s]

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window.resize(1440, 900)
    window.show()
    spin(2.0)  # [s]

    measure("open template 23 (complete small satellite)", lambda: window.open_path(TEMPLATES_DIR / EXAMPLE), 3.0)
    measure("open template 09 (Monte Carlo)",
            lambda: window.open_path(TEMPLATES_DIR / "09_monte_carlo_dispersion_analysis.json"), 3.0)
    measure("open template 23 again", lambda: window.open_path(TEMPLATES_DIR / EXAMPLE), 3.0)

    tree = window.scenario_editor.page_tree
    window.show_view(window.scenario_editor)
    for path, item in tree.paths():
        if "/" not in path:
            measure(f"scenario page: {path}", lambda item=item: tree.tree.setCurrentItem(item), 1.0)

    def type_name(text):
        window.scenario_editor.name_edit.setText(text)

    window.show_view(window.scenario_editor)
    base = window.scenario_editor.name_edit.text()
    measure("edit one field (scenario name), Explain open", lambda: type_name(base + " x"), 1.5)
    window.show_view(window.scenario_explainer_widget)
    measure("edit one field, Explain shown", lambda: type_name(base + " xy"), 1.5)
    type_name(base)

    for main in range(window.main_tabs.count()):
        page = window.main_tabs.widget(main)
        measure(f"main tab (before a run): {window.main_tabs.tabText(main)}",
                lambda page=page: window.main_tabs.setCurrentWidget(page), 1.0)
    for index in range(window.side_tabs.count()):
        page = window.side_tabs.widget(index)
        measure(f"side tab: {window.side_tabs.tabText(index).split(' (')[0]}",
                lambda page=page: window.show_view(page), 1.0)

    window.show_view(window.results_widget)
    spin(0.5)  # [s]
    gaps.clear()
    t_run = time.perf_counter()
    window.on_run()
    wait(lambda: window._run_worker is None or not window._busy_progress.isVisible(), 900.0)  # [s]
    run_s = time.perf_counter() - t_run
    worst = max(gaps) if gaps else 0.0
    over = sum(1 for g in gaps if g > BUDGET_MS)
    results.append({"interaction": "run template 23 and show its results (whole run)", "call_ms": round(run_s * 1e3, 1),
                    "longest_stall_ms": round(worst, 1), "stalls_over_budget": over})
    print(f"run: {run_s:.1f} s, longest stall {worst:.1f} ms, {over} stalls over budget", flush=True)
    measure("settle after the run", lambda: None, 3.0)

    for sub in range(window.results_views.count()):
        page = window.results_views.widget(sub)
        measure(f"results page: {window.results_views.tabText(sub)}", lambda page=page: window.show_view(page), 2.0)
    for main in range(window.main_tabs.count()):
        page = window.main_tabs.widget(main)
        measure(f"main tab (after a run): {window.main_tabs.tabText(main)}",
                lambda page=page: window.main_tabs.setCurrentWidget(page), 1.5)

    results_widget = window.results_widget
    window.show_view(results_widget)
    shown = set(results_widget._shown)
    for number, name in enumerate([n for n in results_widget.catalog.names() if n not in shown][:4]):
        measure(f"results: show plot {number + 1} ({name})", lambda name=name: results_widget.show_series(name), 2.0)
    measure("results: search the plot catalog", lambda: results_widget.catalog.search.setText("attitude"), 1.0)
    results_widget.catalog.search.setText("")

    scenario = load_scenario(TEMPLATES_DIR / EXAMPLE)
    holder = []

    def open_spacecraft():
        dialog = SpacecraftEditorDialog(config=scenario.spacecraft[0], parent=window,
                                        simulation_mode=scenario.simulation_mode)
        dialog.resize(1100, 760)
        dialog.show()
        holder.append(dialog)

    measure("open the spacecraft editor dialog", open_spacecraft, 2.0)
    holder[0].close()

    def theme(name):
        apply_theme(app, name)

    measure("apply the dark theme (live)", lambda: theme("dark"), 1.5)
    measure("apply the light theme (live)", lambda: theme("light"), 1.5)

    window._dirty = False
    window.close()
    heartbeat.stop()
    return results


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="The GUI's responsiveness baseline, offscreen.")
    parser.add_argument("--out", default="docs/ui/perf_baseline.json")
    parser.add_argument("--startup-once", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--interactions-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.startup_once:
        print(json.dumps(startup_once()))
        return 0
    if args.interactions_only:
        print("RESULT " + json.dumps(interactions()))
        return 0
    env = dict(os.environ, QT_QPA_PLATFORM=os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    startups = []
    for _ in range(3):
        env["SMS_SPAWN_TIME"] = repr(time.time())
        done = subprocess.run([sys.executable, __file__, "--startup-once"], env=env, capture_output=True, text=True,
                              check=True)
        startups.append(json.loads(done.stdout.strip().splitlines()[-1]))
        print("startup:", startups[-1], flush=True)
    done = subprocess.run([sys.executable, __file__, "--interactions-only"], env=env, stdout=subprocess.PIPE,
                          text=True, check=True)
    lines = done.stdout.splitlines()
    print("\n".join(line for line in lines if not line.startswith("RESULT ")))
    measured = json.loads(next(line for line in lines if line.startswith("RESULT "))[len("RESULT "):])
    report = {
        "machine": {"platform": platform.platform(), "python": platform.python_version(),
                    "cpus": os.cpu_count(), "qpa": env["QT_QPA_PLATFORM"]},
        "budget_ms": BUDGET_MS,
        "startup": startups,
        "interactions": measured,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
