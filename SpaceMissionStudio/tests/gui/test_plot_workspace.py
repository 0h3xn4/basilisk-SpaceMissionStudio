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

"""The Results plot workspace (docs/ux-audit.md U-24 to U-30): the
catalog, the grid with linked x axes, the readout, the orbit-number
axis, event bands, the epoch subtitle, Export all and the layout kept
per scenario."""

import json
import math

import numpy as np
import pytest
from PySide6.QtCore import Qt

pytestmark = pytest.mark.requires_gui

_PAGE_LOAD_TIMEOUT_MS = 30000  # [ms] as tests/gui/test_results_widget.py (SRelD K-10)
_EPOCH = "2030-01-01T08:30:00"
_RADIUS = 6928.137e3  # [m] a 550 km circular orbit
_MU = 398600.436e9  # [m^3/s^2]
_PERIOD = 2.0 * math.pi * math.sqrt(_RADIUS ** 3 / _MU)  # [s]


def _result():
    """Two orbits of one spacecraft: position, velocity, an eclipse each
    orbit and a mode series (0 or 1, a step)."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    t = np.linspace(0.0, 2.0 * _PERIOD, 241)  # [s]
    u = 2.0 * math.pi * t / _PERIOD  # [rad] argument of latitude, from the node at t = 0
    i = math.radians(97.6)  # [rad]
    node, ahead = np.array([1.0, 0.0, 0.0]), np.array([0.0, math.cos(i), math.sin(i)])
    r = _RADIUS * (np.cos(u)[:, None] * node + np.sin(u)[:, None] * ahead)
    v = (_RADIUS * 2.0 * math.pi / _PERIOD) * (-np.sin(u)[:, None] * node + np.cos(u)[:, None] * ahead)
    sunlight = np.where(np.mod(u, 2.0 * math.pi) > 4.0, 0.0, 1.0)  # [-] in shadow for the last part of each orbit
    mode = (t > _PERIOD).astype(float)  # [-]
    result = ResultSet("demo")
    result.add(TimeSeries("sat-1.position_N", t, ("x", "y", "z"), r, units="m"))
    result.add(TimeSeries("sat-1.velocity_N", t, ("x", "y", "z"), v, units="m/s"))
    result.add(TimeSeries("sat-1.eclipse.illumination_factor", t, ("illumination_factor",), sunlight[:, None]))
    result.add(TimeSeries("sat-1.comms_pointing.active_mode", t, ("active_mode",), mode[:, None]))
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


# -- the page and its layouts (no Qt) -------------------------------------

def test_layouts_fit_the_count_and_the_pane():
    """Tall before wide without a size; with one, the cells closest to
    twice as wide as tall, never more than one cell to spare."""
    from spacemissionstudio.gui import plot_page

    assert plot_page.smallest_layout(1) == "1x1"
    assert plot_page.smallest_layout(2) == "2x1"
    assert plot_page.smallest_layout(3) == "3x1"
    assert plot_page.smallest_layout(4) == "2x2"
    assert plot_page.best_layout(3, 620, 330) == "2x2"  # [px] a wide, short pane
    assert plot_page.best_layout(2, 600, 800) == "2x1"  # [px] a tall pane stacks them
    assert plot_page.best_layout(6, 1500, 900) == "3x2"
    assert plot_page.capacity(plot_page.best_layout(plot_page.MAX_PLOTS + 3, 800, 600)) == plot_page.MAX_PLOTS


def test_page_messages_carry_the_plot_and_the_x_value():
    """Clicks, hovers and focus changes come back through the page title."""
    from spacemissionstudio.gui import plot_page

    assert plot_page.parse_message(plot_page.CLICK_MESSAGE + "2@1.25|7") == ("click", 2, "1.25")
    assert plot_page.parse_message(plot_page.HOVER_MESSAGE + "0@2030-01-01 09:00:00|8") == \
        ("hover", 0, "2030-01-01 09:00:00")
    assert plot_page.parse_message(plot_page.HOVER_MESSAGE + "1@|9") == ("hover", 1, None)
    assert plot_page.parse_message(plot_page.FOCUS_MESSAGE + "3|10") == ("focus", 3, None)
    assert plot_page.parse_message("SpaceMissionStudio") is None


# -- the readout values (no Qt) -------------------------------------------

def test_the_readout_interpolates_smooth_series_and_holds_steps():
    """Between two samples: linear for a smooth series; the last sample
    for whole-number (step) and wrapping series; nothing outside the run."""
    from spacemissionstudio.engine.results import TimeSeries
    from spacemissionstudio.gui.readout_panel import format_value, value_at

    t = np.array([0.0, 10.0, 20.0])  # [s]
    smooth = TimeSeries("a", t, ("v",), np.array([[0.0], [1.0], [4.0]]))
    t_step = np.arange(6) * 10.0  # [s]
    step = TimeSeries("b", t_step, ("v",), np.array([[0.0], [0.0], [1.0], [1.0], [1.0], [0.0]]))
    assert value_at(smooth, 0, 15.0) == pytest.approx(2.5)
    assert value_at(smooth, 0, 15.0, factor=1000.0) == pytest.approx(2500.0)
    assert value_at(step, 0, 25.0) == 1.0 and value_at(step, 0, 15.0) == 0.0
    assert value_at(smooth, 0, 15.0, wraps=True) == 1.0
    assert value_at(smooth, 0, 25.0) is None
    assert format_value(None) == "-" and format_value(531402.0) == "531,402"
    assert format_value(1.23456789e9) == "1.23457e+09"


# -- the catalog and the grid ---------------------------------------------

def test_the_catalog_groups_every_plot(widget):
    """Groups from plot_categories, with their counts."""
    widget.set_result(_result())
    groups = {widget.catalog.tree.topLevelItem(i).text(0) for i in range(widget.catalog.tree.topLevelItemCount())}
    assert groups == {"Orbit (3)", "Attitude (1)"}


def test_ticking_plots_fills_the_grid_and_grows_the_layout(widget):
    """A tick adds the plot and selects it; past the layout's cells the
    layout grows; clearing a tick takes the plot out."""
    widget.set_result(_result())
    _tick(widget, "sat-1.velocity_N")
    _tick(widget, "sat-1.eclipse.illumination_factor")
    assert widget.shown_plots() == ["sat-1.position_N", "sat-1.velocity_N", "sat-1.eclipse.illumination_factor"]
    assert len(widget.figures) == 3 and widget.current_series_name() == "sat-1.eclipse.illumination_factor"
    from spacemissionstudio.gui import plot_page

    assert plot_page.capacity(widget.layout_combo.currentData()) >= 3
    _tick(widget, "sat-1.velocity_N", on=False)
    assert widget.shown_plots() == ["sat-1.position_N", "sat-1.eclipse.illumination_factor"]


def test_a_smaller_layout_keeps_the_first_plots(widget):
    """Choosing 1 x 1 keeps the first plot and clears the others' ticks."""
    widget.set_result(_result())
    _tick(widget, "sat-1.velocity_N")
    widget.layout_combo.setCurrentIndex(widget.layout_combo.findData("1x1"))
    assert widget.shown_plots() == ["sat-1.position_N"]
    assert widget.catalog._items["sat-1.velocity_N"].checkState(0) == Qt.CheckState.Unchecked


def test_a_full_grid_refuses_another_plot(widget, monkeypatch):
    """Six plots at most: a seventh tick is cleared again, with a note."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui import feedback

    notes = []
    monkeypatch.setattr(feedback, "show_toast", lambda parent, message, **k: notes.append(message))
    result = ResultSet("many")
    for index in range(7):
        result.add(TimeSeries(f"sat-{index}.battery_charge", [0.0, 1.0], ("charge",), [[0.0], [1.0]]))
    widget.set_result(result)
    for index in range(1, 7):
        _tick(widget, f"sat-{index}.battery_charge")
    assert len(widget.shown_plots()) == 6 and "at most 6" in notes[-1]
    assert widget.catalog._items["sat-6.battery_charge"].checkState(0) == Qt.CheckState.Unchecked


def test_a_click_selects_the_plot_that_saves(widget, monkeypatch):
    """A focus message from the page selects that plot: Save PNG offers
    its name."""
    from PySide6.QtWidgets import QFileDialog

    from spacemissionstudio.gui import plot_page

    widget.set_result(_result())
    _tick(widget, "sat-1.velocity_N")
    widget._on_page_title(plot_page.FOCUS_MESSAGE + "0|1")
    assert widget.current_series_name() == "sat-1.position_N"
    offered = {}
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: offered.setdefault("name", a[2]) and ("", "")))
    widget._on_save_plot_png()
    assert offered["name"] == "sat-1.position_N.png"


def test_the_grid_links_its_x_axes_in_the_page(widget, qtbot):
    """Zooming one plot zooms the other (in the real web view)."""
    widget.set_result(_result())
    with qtbot.waitSignal(widget.web_view.loadFinished, timeout=_PAGE_LOAD_TIMEOUT_MS):
        _tick(widget, "sat-1.velocity_N")
    answer = {}

    def read_range():
        widget.web_view.page().runJavaScript(
            "(function(){var a=document.getElementById('spacemissionstudio-plot-1');"
            "return a && a.layout ? JSON.stringify(a.layout.xaxis.range) : '';})()",
            0, lambda value: answer.__setitem__("range", value))

    widget.web_view.page().runJavaScript(
        "Plotly.relayout(document.getElementById('spacemissionstudio-plot'), {'xaxis.range': [0.25, 0.75]});")

    def linked():
        read_range()
        return answer.get("range") == "[0.25,0.75]"

    qtbot.waitUntil(linked, timeout=10000)


# -- the time axes, the subtitle and the readout ---------------------------

def test_the_orbit_number_axis_counts_revolutions(widget):
    """Two orbits from the node read 0 to 2; the cursor round-trips."""
    from spacemissionstudio.gui.time_cursor import TimeCursor

    widget.set_result(_result(), _EPOCH)
    widget.x_axis_combo.setCurrentIndex(widget.x_axis_combo.findData("orbit"))
    figure = widget.figure
    assert figure.layout.xaxis.title.text == "Orbit number (sat-1)"
    assert figure.data[0].x[0] == pytest.approx(0.0, abs=1e-9)
    assert figure.data[0].x[-1] == pytest.approx(2.0, abs=1e-6)
    cursor = TimeCursor()
    widget.set_time_cursor(cursor)
    cursor.set_time(0.5 * _PERIOD)  # [s]
    assert float(widget.cursor_x_literal()) == pytest.approx(0.5, abs=1e-6)
    assert widget.plot_x_to_elapsed_s("1.5") == pytest.approx(1.5 * _PERIOD, rel=1e-6)


def test_elapsed_time_plots_name_their_epoch(widget):
    """ "t0 = ... UTC" under the title on an elapsed-time axis (U-30); the
    UTC axis shows dates itself."""
    widget.set_result(_result(), _EPOCH)
    assert "t0 = 2030-01-01 08:30:00 UTC" in widget.figure.layout.title.text
    widget.x_axis_combo.setCurrentIndex(widget.x_axis_combo.findData("epoch"))
    assert "t0 =" not in widget.figure.layout.title.text


def test_the_readout_follows_the_cursor_and_the_pointer(widget):
    """Every shown series' values with units at the cursor; while the
    pointer is over a plot, at the pointer."""
    from spacemissionstudio.gui import plot_page
    from spacemissionstudio.gui.time_cursor import TimeCursor

    widget.set_result(_result(), _EPOCH)
    _tick(widget, "sat-1.comms_pointing.active_mode")
    cursor = TimeCursor()
    widget.set_time_cursor(cursor)
    cursor.set_time(0.25 * _PERIOD)  # [s] a quarter orbit: y = r cos(i)
    rows = widget.readout.rows()
    assert widget.readout.time_label.text().endswith("(cursor)") and "orbit 0.250 of sat-1" in \
        widget.readout.time_label.text()
    y = next(row for row in rows if row[0] == "Y")
    assert float(y[1].replace(",", "")) == pytest.approx(_RADIUS * math.cos(math.radians(97.6)), rel=1e-3)
    assert y[2] == "m"
    assert ("Mode", "0", "-") in rows
    widget._on_page_title(plot_page.HOVER_MESSAGE + f"1@{1.5 * _PERIOD / 3600.0}|1")  # [h]
    assert widget.readout.time_label.text().endswith("(pointer)") and ("Mode", "1", "-") in widget.readout.rows()
    widget._on_page_title(plot_page.HOVER_MESSAGE + "1@|2")  # the pointer left
    assert widget.readout.time_label.text().endswith("(cursor)")


# -- event bands ----------------------------------------------------------

def _bands(figure, kind):
    return [shape for shape in figure.layout.shapes if shape.name == f"event-{kind}"]


def test_eclipses_and_mode_changes_are_drawn_and_switch_off(widget):
    """One band per eclipse behind the lines, a dashed line per mode
    span; the Eclipses button takes them off every plot."""
    widget.set_result(_result(), _EPOCH)
    assert len(_bands(widget.figure, "eclipse")) == 2 and _bands(widget.figure, "eclipse")[0].layer == "below"
    assert all(shape.type == "line" for shape in _bands(widget.figure, "mode"))
    assert widget._event_buttons["eclipse"].isVisibleTo(widget) and not widget._event_buttons["burn"].isVisibleTo(widget)
    widget._event_buttons["eclipse"].setChecked(False)
    assert _bands(widget.figure, "eclipse") == []


def test_too_many_bands_are_left_out_and_said(widget, monkeypatch):
    """Above the cap a kind is not drawn, and the note says so."""
    from spacemissionstudio.gui import results_widget

    monkeypatch.setattr(results_widget, "_MAX_BANDS_PER_KIND", 1)
    widget.set_result(_result(), _EPOCH)
    assert _bands(widget.figure, "eclipse") == []
    assert "Eclipses of sat-1: 2, too many to draw" in widget.events_note.text()


# -- kept per scenario, and Export all -------------------------------------

def test_the_layout_and_plots_are_kept_per_scenario(qtbot):
    """A second window on the same scenario opens on the same grid."""
    from spacemissionstudio.gui.results_widget import ResultsWidget

    first = ResultsWidget()
    qtbot.addWidget(first)
    first.set_layout_key("demo")
    first.set_result(_result())
    _tick(first, "sat-1.velocity_N")
    second = ResultsWidget()
    qtbot.addWidget(second)
    second.set_layout_key("demo")
    second.set_result(_result())
    assert second.shown_plots() == ["sat-1.position_N", "sat-1.velocity_N"]
    third = ResultsWidget()
    qtbot.addWidget(third)
    third.set_layout_key("another")
    third.set_result(_result())
    assert third.shown_plots() == ["sat-1.position_N"]


def test_export_all_writes_every_plot_its_data_and_the_provenance(widget, qtbot, tmp_path, monkeypatch):
    """Every shown plot as an image (numbered in grid order), its series
    as CSV, and provenance.json (U-29)."""
    from spacemissionstudio.engine.results import RunProvenance
    from spacemissionstudio.gui import feedback

    monkeypatch.setattr(feedback, "show_toast", lambda *a, **k: None)
    result = _result()
    result.provenance = RunProvenance("test", "2.12.0", "2030-01-01T00:00:00+00:00", "rk4", 1.0)
    widget.set_result(result, _EPOCH)
    with qtbot.waitSignal(widget.web_view.loadFinished, timeout=_PAGE_LOAD_TIMEOUT_MS):
        _tick(widget, "sat-1.velocity_N")
    widget.raise_()
    widget.activateWindow()
    widget.export_all(tmp_path, "svg")
    qtbot.waitUntil(lambda: (tmp_path / "provenance.json").exists(), timeout=30000)
    names = sorted(path.name for path in tmp_path.iterdir())
    assert names == ["01_sat-1.position_N.svg", "02_sat-1.velocity_N.svg", "provenance.json",
                     "sat-1.position_N.csv", "sat-1.velocity_N.csv"]
    assert "<svg" in (tmp_path / "01_sat-1.position_N.svg").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "provenance.json").read_text())["basilisk_version"] == "2.12.0"


def test_a_live_run_reads_its_events_only_for_drawn_chunks(widget, monkeypatch):
    """Chunks that are not drawn (throttled) reuse the events read
    shortly before; a drawn chunk, and the final result, read them fresh."""
    from spacemissionstudio.gui import results_widget

    reads = []
    real = results_widget.event_model.extract_events
    monkeypatch.setattr(results_widget.event_model, "extract_events", lambda result: reads.append(1) or real(result))
    widget.set_live_result(_result(), _EPOCH)
    first = len(reads)

    class _FrozenClock:  # no time passes: every later chunk is throttled
        def elapsed(self):
            return 0

        def restart(self):
            return 0

    monkeypatch.setattr(widget, "_live_redraw_elapsed", _FrozenClock())
    for _ in range(3):
        widget.set_live_result(_result(), _EPOCH)
    assert len(reads) == first
    widget.set_result(_result(), _EPOCH)  # drawn: fresh
    assert len(reads) > first
