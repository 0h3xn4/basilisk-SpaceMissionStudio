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

"""Tests for gui.roe_diagram_widget.RoeDiagramWidget, the Explain page's
e/i-vector diagram of an ROE formation (SRS-F-21)."""

import pytest

pytestmark = pytest.mark.requires_gui

_APPROACH_THEN_HELIX = [(0.0, [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]),  # [m]
                        (1.0, [0.0, 0.0, 0.0, 300.0, 0.0, 300.0])]  # [m]


def _widget(qtbot, targets=None):
    from spacemissionstudio.engine.scenario_explainer import RoeDiagram
    from spacemissionstudio.gui.roe_diagram_widget import RoeDiagramWidget

    widget = RoeDiagramWidget(RoeDiagram("chief-1", "helix-1", _APPROACH_THEN_HELIX if targets is None else targets))
    qtbot.addWidget(widget)
    return widget


def test_no_diagram_collapses_to_zero_height(qtbot):
    """Without a diagram the widget takes no room and has no tooltip."""
    from spacemissionstudio.gui.roe_diagram_widget import RoeDiagramWidget

    widget = RoeDiagramWidget()
    qtbot.addWidget(widget)
    assert widget.height() == 0 and widget.toolTip() == ""


def test_target_summary_says_where_and_how_close():
    """The legend text: the along-track place and the closest approach,
    or that the orbits cross."""
    from spacemissionstudio.gui.roe_diagram_widget import target_summary

    assert target_summary([0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]) == "2000 m behind, orbits cross"
    assert target_summary([0.0, 50.0, 0.0, 300.0, 0.0, 300.0]) == "50 m ahead, closest 300 m"


def test_the_tooltip_lists_every_target(qtbot):
    """Hovering gives each target's vectors and summary, the text behind
    the picture."""
    tooltip = _widget(qtbot).toolTip()
    assert "helix-1 around chief-1" in tooltip
    assert "day 0: a·δe (0, 0) m, a·δi (0, 0) m; 2000 m behind, orbits cross" in tooltip
    assert "day 1: a·δe (0, 300) m, a·δi (0, 300) m; 0 m ahead, closest 300 m" in tooltip


def test_more_targets_than_colours_are_folded_into_one_line(qtbot):
    """Colours are never cycled: past the eighth target the legend gains
    one "and N later targets" line instead of a repeated colour."""
    from spacemissionstudio.gui.theme import SERIES_COLORS

    few = _widget(qtbot)
    many = _widget(qtbot, [(float(day), [0.0, 0.0, 0.0, 100.0 + day, 0.0, 100.0 + day]) for day in range(10)])
    assert len(many._shown_targets()) == len(SERIES_COLORS)
    assert many.height() == few.height() + (len(SERIES_COLORS) - 2 + 1) * 18  # one 18 px line per entry


def test_paints_for_unusual_formations(qtbot):
    """Zero vectors, a drift (δa), a crossing pair and a narrow widget all
    paint without raising."""
    for targets in ([(0.0, [0.0] * 6)], [(0.0, [20.0, 0.0, 0.0, 0.0, 0.0, 0.0])],
                    [(0.0, [0.0, 0.0, 300.0, 0.0, 0.0, 300.0])], _APPROACH_THEN_HELIX):
        widget = _widget(qtbot, targets)
        for width in (640, 120):
            widget.resize(width, widget.height())
            assert not widget.grab().isNull()


def test_the_explain_page_shows_it_for_an_roe_formation(qtbot):
    """The Explain page adds one ROE diagram per ROE formation."""
    from pathlib import Path

    from spacemissionstudio.gui.roe_diagram_widget import RoeDiagramWidget
    from spacemissionstudio.gui.scenario_explainer_widget import ScenarioExplainerWidget
    from spacemissionstudio.schema import RoeFormationConfig, RoeTargetConfig, load_scenario

    scenario = load_scenario(Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
                             / "05_formation_flying_phasing.json")
    follower = next(sc for sc in scenario.spacecraft if sc.phasing_keeping is not None)
    follower.roe_formation = RoeFormationConfig(chief_spacecraft=follower.phasing_keeping.chief_spacecraft,
                                                targets=[RoeTargetConfig(*target) for target in _APPROACH_THEN_HELIX])
    follower.phasing_keeping = None
    widget = ScenarioExplainerWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    [diagram] = widget.findChildren(RoeDiagramWidget)
    assert diagram.height() > 0
