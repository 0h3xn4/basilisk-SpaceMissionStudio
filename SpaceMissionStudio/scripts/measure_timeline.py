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

"""How long the Timeline holds the GUI thread with many events (UI
overhaul M7's criterion: 10,000 events without a stall over 50 ms).
Offscreen, no Basilisk needed::

    QT_QPA_PLATFORM=offscreen python scripts/measure_timeline.py [--events 10000]

Builds ``--events`` passes and eclipses over a year for two spacecraft and
three stations (synthetic: the Timeline's own entry point is given them in
place of a run's), then times, with a 2 ms heartbeat timer, the longest
gap after: showing them, a search keystroke, clearing it, a zoom and a
paint. The numbers are this machine's, software rendered.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SETTLE_S = 0.8  # [s] after each step
_YEAR_S = 365.25 * 86400.0  # [s]


def synthetic_events(count: int):
    """``count`` passes and eclipses spread over a year (no Basilisk)."""
    from spacemissionstudio.engine import events as event_model

    rng = np.random.default_rng(1)  # a fixed seed: the same events each time
    starts = np.sort(rng.uniform(0.0, _YEAR_S, count))  # [s]
    events = []
    for index, start in enumerate(starts):
        spacecraft = ("sat-1", "sat-2")[index % 2]
        if index % 3:
            station = ("berlin", "kiruna", "malindi")[index % 3]
            events.append(event_model.Event(event_model.ACCESS, spacecraft, float(start), float(start) + 600.0,
                                            f"pass over {station}", other=station,
                                            quantities=(("max_elevation_deg", float(index % 90)),)))
        else:
            events.append(event_model.Event(event_model.ECLIPSE, spacecraft, float(start), float(start) + 2100.0,
                                            "eclipse (umbra)"))
    return events


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="How long the Timeline holds the GUI thread with many events.")
    parser.add_argument("--events", type=int, default=10000, help="events to show")
    args = parser.parse_args(argv)

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.engine import events as event_model
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui import event_timeline_widget
    from spacemissionstudio.gui.theme import apply_theme

    apply_theme(app)
    events = synthetic_events(args.events)
    event_timeline_widget.event_model.extract_events = lambda result: list(events)
    event_timeline_widget.event_model.missing_kinds = lambda result: {}
    result = ResultSet("timeline")
    result.add(TimeSeries("sat-1.position_N", np.array([0.0, _YEAR_S]), ("x", "y", "z"), np.zeros((2, 3)), "m"))

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

    widget = event_timeline_widget.EventTimelineWidget()
    widget.resize(1280, 720)  # [px]
    widget.show()
    spin(0.5)  # [s]

    steps: list[tuple[str, float]] = []  # (name, when it started) [s]

    def step(name, action) -> None:
        steps.append((name, time.perf_counter()))
        action()
        spin(SETTLE_S)

    last[0] = time.perf_counter()
    heartbeat.start()
    step(f"show {args.events} events", lambda: widget.set_result(result, "2030-01-01T00:00:00Z"))
    step("search keystroke", lambda: widget.search.setText("k"))
    step("search cleared", lambda: widget.search.setText(""))
    step("zoom in", lambda: getattr(widget.gantt, "zoom", lambda _f: widget.gantt.fit())(0.5))  # zoom: M7
    step("paint", lambda: widget.gantt.repaint())
    spin(SETTLE_S)  # the last step's work, however long, is measured
    heartbeat.stop()
    # A gap belongs to the step it began in: work a step leaves for the
    # event loop (a layout, a paint) is that step's.
    bounds = [when for _name, when in steps] + [float("inf")]
    worst = 0.0  # [ms]
    for index, (name, when) in enumerate(steps):
        longest = max((ms for ended, ms in gaps if when <= ended - ms / 1e3 < bounds[index + 1]), default=0.0)
        worst = max(worst, longest)
        print(f"{name:28s} longest stall {longest:7.1f} ms", flush=True)
    print(f"worst stall: {worst:.1f} ms ({len(event_model.KINDS)} kinds)")
    widget.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
