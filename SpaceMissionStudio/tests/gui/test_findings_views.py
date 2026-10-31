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
"""Structured warnings in the app (engine.findings, Phase 5a): the
Problems panel and Explain show a warning's rule on hover, and nothing
more until asked."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


def _flagged_scenario():
    """Template 19 with a late first pass and a long step."""
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(next(_TEMPLATES.glob("19_*.json")))
    scenario.epoch_utc = "2030-01-01T00:00:00"  # the first pass at about 8.2 h
    scenario.sim_settings.duration_days = 0.5  # [day]
    scenario.sim_settings.dynamics_task_rate_s = 120.0  # [s]
    return scenario


def test_the_problems_panel_shows_a_warnings_rule_on_hover(qtbot):
    """A warning's tooltip is its rule, what it found against its limit, why,
    the fix and the override, then the double-click hint; an error, which has
    no rule yet, keeps the hint alone. The table's columns are unchanged."""
    from PySide6.QtCore import Qt

    from spacemissionstudio.engine.findings import Finding
    from spacemissionstudio.gui.workspace_panels import ProblemsWidget

    panel = ProblemsWidget()
    qtbot.addWidget(panel)
    warning = Finding("the dynamics step is 120 s: above 60 s the orbit loses accuracy", "step.long",
                      actual="120 s", limit="60 s")
    panel.set_problems([("warning", warning), ("error", "spacecraft[0].dry_mass_kg must be positive")])
    tooltips = {panel.problem_at(row).severity: panel.proxy.index(row, 3).data(Qt.ItemDataRole.ToolTipRole)
                for row in range(panel.proxy.rowCount())}
    assert tooltips["warning"].startswith("rule step.long: A dynamics step above the limit is flagged.\n"
                                          "found 120 s; limit 60 s\nwhy: ")
    assert "checks.long_step_s" in tooltips["warning"]
    assert tooltips["warning"].endswith("\n\nDouble-click to go to where it is fixed")
    assert tooltips["error"] == "Double-click to go to where it is fixed"
    assert [row[3] for row in panel.shown_rows()].count(str(warning)) == 1  # the message, as before


def test_explain_shows_a_warnings_rule_on_hover(qtbot):
    """Explain's "Check before running" notes are the warnings, as before;
    each carries its rule as a tooltip and accessible description."""
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.scenario_explainer_widget import ScenarioExplainerWidget

    widget = ScenarioExplainerWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(_flagged_scenario())
    widget.wait_for_worker()
    labels = {label.text(): label for label in widget.findChildren(QLabel)}
    late = labels["berlin-gs: the first pass only comes at 8.2 h of a 12.0 h run"]
    assert late.toolTip().startswith("rule passes.late_first: ")
    assert "found 0.68 of the run; limit 0.5" in late.toolTip()
    assert late.accessibleDescription() == late.toolTip()
    step = next(label for text, label in labels.items() if text.startswith("the dynamics step is 120 s"))
    assert "checks.long_step_s" in step.toolTip()
    headline = widget._headline_label
    assert headline.toolTip() == ""  # labels that are not warnings get no rule
