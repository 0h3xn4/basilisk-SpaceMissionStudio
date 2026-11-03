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
"""Two runs side by side, without the GUI (the transparency plan, Phase 9:
the run comparison of Results > Compare on the command line and in the
API): what differs between the scenarios they flew, their headline
figures with the difference, and their events.

The figures and the events are the Compare page's
(:func:`.run_summary.summarize`, :func:`.run_summary.event_table`), the
scenario differences :func:`.scenario_diff.diff`'s. Basilisk-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import events as event_model
from . import run_summary, scenario_diff


@dataclass
class Comparison:
    """``a`` against ``b``: the labels, the scenario differences (path, in
    a, in b), the figures (key, label, unit, in a or None, in b or None),
    and the events (label, (count, minutes) in a, the same in b)."""

    a: str
    b: str
    scenario: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    events: list = field(default_factory=list)

    def to_dict(self) -> dict:
        def delta(first, second):
            return None if first is None or second is None else second - first

        return {"a": self.a, "b": self.b,
                "scenario_differences": [{"path": path, "a": first, "b": second}
                                         for path, first, second in self.scenario],
                "figures": [{"key": key, "label": label, "unit": unit, "a": first, "b": second,
                             "b_minus_a": delta(first, second)}
                            for key, label, unit, first, second in self.figures],
                "events": [{"event": label, "a": {"count": first[0], "minutes": first[1]},
                            "b": {"count": second[0], "minutes": second[1]}}
                           for label, first, second in self.events]}


def compare(a_scenario: dict, a_result, b_scenario: dict, b_result, a_label: str = "a",
            b_label: str = "b") -> Comparison:
    """``a`` against ``b``: each a scenario as it ran (``Scenario.to_dict()``)
    and its :class:`.results.ResultSet`."""
    found = Comparison(a_label, b_label, scenario_diff.diff(a_scenario, b_scenario))
    a_events, b_events = event_model.extract_events(a_result), event_model.extract_events(b_result)
    a_figures = run_summary.by_key(run_summary.summarize(a_result, a_events))
    b_figures = run_summary.by_key(run_summary.summarize(b_result, b_events))
    for key in list(a_figures) + [k for k in b_figures if k not in a_figures]:
        shown = a_figures.get(key) or b_figures[key]
        found.figures.append((key, shown.label, shown.unit,
                              a_figures[key].value if key in a_figures else None,
                              b_figures[key].value if key in b_figures else None))
    a_table, b_table = run_summary.event_table(a_events), run_summary.event_table(b_events)
    for label in list(a_table) + [k for k in b_table if k not in a_table]:
        found.events.append((label, a_table.get(label, (0, 0.0)), b_table.get(label, (0, 0.0))))
    return found


def lines(found: Comparison) -> list[str]:
    """``found`` as the command line prints it."""
    out = [f"{found.a} against {found.b}"]
    out.append(f"Scenario differences: {len(found.scenario)}" if found.scenario else
               "Scenario differences: none (the same scenario)")
    out += [f"  {path}: {scenario_diff.short(first)} -> {scenario_diff.short(second)}"
            for path, first, second in found.scenario]
    if found.figures:
        out.append("Figures:")
        width = max(len(label) for _key, label, _unit, _a, _b in found.figures)
        for _key, label, unit, first, second in found.figures:
            def text(value):
                return "-" if value is None else f"{value:.6g}"
            difference = "" if first is None or second is None else f"  (b - a: {second - first:+.6g})"
            out.append(f"  {label:<{width}}  {text(first):>12}  {text(second):>12} {unit}{difference}")
    if found.events:
        out.append("Events (count, minutes):")
        for label, first, second in found.events:
            out.append(f"  {label}: {first[0]}, {first[1]:.1f}  |  {second[0]}, {second[1]:.1f}")
    return out
