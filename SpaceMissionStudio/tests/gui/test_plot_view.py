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

"""The plot view of Results (UI overhaul M6a): one persistent page,
plotly.js loaded once, each change sent to it; each plot's figure built
once and kept until what it shows changes; the layout saved after the
click; the start-up objects out of the garbage collector's full
collections."""

import gc
import json

import numpy as np
import pytest
from PySide6.QtCore import Qt

pytestmark = pytest.mark.requires_gui

_DRAWN_TIMEOUT_MS = 30000  # [ms] as tests/gui/test_results_widget.py (SRelD K-10)


def _result():
    """One spacecraft, three series over two hours."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    t = np.linspace(0.0, 7200.0, 121)  # [s]
    result = ResultSet("demo")
    result.add(TimeSeries("sat-1.position_N", t, ("x", "y", "z"), np.column_stack([np.cos(t), np.sin(t), t]),
                          units="m"))
    result.add(TimeSeries("sat-1.velocity_N", t, ("x", "y", "z"), np.column_stack([-np.sin(t), np.cos(t), t]),
                          units="m/s"))
    result.add(TimeSeries("sat-1.battery_charge", t, ("battery_charge",), (100.0 - t / 100.0)[:, None],
                          units="W*h"))
    return result


@pytest.fixture
def widget(qtbot):
    from spacemissionstudio.gui.results_widget import ResultsWidget

    w = ResultsWidget()
    qtbot.addWidget(w)
    w.resize(1100, 700)  # [px]
    with qtbot.waitExposed(w):
        w.show()
    return w


def _tick(widget, name, on=True):
    widget.catalog._items[name].setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)


def test_the_page_is_loaded_once_and_each_change_is_drawn_in_it(widget, qtbot):
    """Showing another plot, adding one to the grid and changing the x axis
    draw in the same page: it is loaded once (plotly.js with it)."""
    loads = []
    widget.web_view.loadStarted.connect(lambda: loads.append(1))
    with qtbot.waitSignal(widget.plot_drawn, timeout=_DRAWN_TIMEOUT_MS) as drawn:
        widget.set_result(_result(), "2030-01-01T00:00:00")
    assert drawn.args == [True]
    for change in (lambda: widget.show_series("sat-1.velocity_N"), lambda: _tick(widget, "sat-1.battery_charge"),
                   lambda: widget.x_axis_combo.setCurrentIndex(widget.x_axis_combo.findData("epoch"))):
        with qtbot.waitSignal(widget.plot_drawn, timeout=_DRAWN_TIMEOUT_MS) as drawn:
            change()
        assert drawn.args == [True]
    assert loads == []
    cells = []
    widget.web_view.page().runJavaScript("document.getElementById('grid').children.length", 0, cells.append)
    qtbot.waitUntil(lambda: bool(cells), timeout=_DRAWN_TIMEOUT_MS)
    assert cells == [2]


def test_a_figure_is_built_once_until_what_it_shows_changes(widget, monkeypatch):
    """Back to a plot shown before: its figure is the one built then.
    Another x axis, or another theme, builds it again."""
    from spacemissionstudio.gui import results_widget

    built = []
    real = results_widget.ResultsWidget._build_figure
    monkeypatch.setattr(results_widget.ResultsWidget, "_build_figure",
                        lambda self, name, series: built.append(name) or real(self, name, series))
    widget.set_result(_result(), "2030-01-01T00:00:00")
    first = widget.figure
    widget.show_series("sat-1.velocity_N")
    widget.show_series("sat-1.position_N")
    assert widget.figure is first
    assert built == ["sat-1.position_N", "sat-1.velocity_N"]
    widget.x_axis_combo.setCurrentIndex(widget.x_axis_combo.findData("epoch"))
    assert widget.figure is not first and built[-1] == "sat-1.position_N"
    again = widget.figure
    widget._theme_generation += 1  # as a theme switch does
    widget._update_figure()
    assert widget.figure is not again


def test_a_figure_is_the_same_as_built_in_steps(widget):
    """One construction gives the figure the earlier add_trace and
    update_layout steps gave: the same JSON, shapes (event bands) included."""
    import plotly.graph_objects as go

    widget.set_result(_result(), "2030-01-01T00:00:00")
    built = json.loads(widget.figure.to_json())
    steps = go.Figure()
    for trace in built["data"]:
        steps.add_trace(go.Scatter(trace))
    layout = dict(built["layout"])
    steps.update_layout(**{key: value for key, value in layout.items() if key != "template"})
    steps.update_layout(template=layout.get("template"))
    assert json.loads(steps.to_json()) == built


def test_the_layout_is_saved_after_the_click_and_read_back_at_once(qtbot):
    """The change is written shortly after it, not in the click; another
    view reading the scenario's layout first writes what is pending."""
    from spacemissionstudio.gui.results_widget import ResultsWidget, _PENDING_SAVES

    first = ResultsWidget()
    qtbot.addWidget(first)
    first.set_layout_key("deferred")
    first.set_result(_result())
    _tick(first, "sat-1.velocity_N")
    assert first in _PENDING_SAVES
    second = ResultsWidget()
    qtbot.addWidget(second)
    second.set_layout_key("deferred")
    second.set_result(_result())
    assert first not in _PENDING_SAVES
    assert second.shown_plots() == ["sat-1.position_N", "sat-1.velocity_N"]
    _tick(second, "sat-1.battery_charge")
    qtbot.waitUntil(lambda: second not in _PENDING_SAVES, timeout=5000)


def test_start_up_objects_leave_the_full_collections():
    """After start-up, what exists is moved out of the collector's full
    collections, garbage collected first."""
    from spacemissionstudio.gui.app import freeze_start_up_objects

    try:
        freeze_start_up_objects()
        assert gc.get_freeze_count() > 0
    finally:
        gc.unfreeze()
