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
"""The Calculation panel (transparency plan, Phase 4b): Show calculation on
the Budget, End of Life and the mission dashboard's link, and the panel that
shows a number's trace."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATE_18 = (Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
                / "18_leo_station_keeping.json")


def _two_traces():
    from spacemissionstudio.engine.trace import Quantity, Trace

    speed = Trace("Exhaust speed", "Ve", 2940.0, "[m/s]", "Ve = eta * Isp * g0", "ESA AD10 Sec. 6.2.1",
                  inputs=(Quantity("specific impulse", "Isp", 300.0, "[s]", "scenario: propellant_budget.isp_s"),))
    propellant = Trace("Propellant", "m_p", 3.5, "[kg]", "m_p = m * (1 - exp(-dV / Ve))", "ESA AD10 Sec. 6.2.1",
                       inputs=(Quantity("delta-V", "dV", 100.0, "[m/s]", "scenario: x"),
                               Quantity("exhaust speed", "Ve", 2940.0, "[m/s]", "trace: Exhaust speed")),
                       intermediates=(Quantity("mass before the burn", "m", 105.0, "[kg]", "computed: m_dry"),),
                       notes=("one burn",))
    return propellant, speed


@pytest.fixture
def panel(qtbot):
    from spacemissionstudio.gui.calculation_panel import CalculationPanel

    widget = CalculationPanel()
    qtbot.addWidget(widget)
    return widget


def test_the_panel_shows_a_trace_and_opens_the_numbers_it_is_built_from(panel):
    """The result, the equation, the reference, each input with its unit and
    source, and the notes; an input that is another number of the
    explanation has an Open button to that number's trace, and Back
    returns."""
    from spacemissionstudio.gui.calculation_panel import Explanation

    assert not panel.empty_label.isHidden() and panel.body.isHidden()
    propellant, speed = _two_traces()
    panel.explain(Explanation("Budget: sat-1", [propellant, speed]))
    assert panel.empty_label.isHidden() and not panel.body.isHidden()
    assert panel.context_label.text() == "Budget: sat-1"
    assert panel.result_label.text() == "Propellant: m_p = 3.5 [kg]"
    assert panel.equation_label.text() == "m_p = m * (1 - exp(-dV / Ve))"
    assert panel.reference_label.text() == "From: ESA AD10 Sec. 6.2.1"
    assert [label.text() for label in panel.value_labels] == [
        "dV = 100 [m/s]   delta-V", "Ve = 2940 [m/s]   exhaust speed", "m = 105 [kg]   mass before the burn"]
    assert [label.text() for label in panel.source_labels] == ["scenario: x", "trace: Exhaust speed", "computed: m_dry"]
    assert list(panel.open_buttons) == ["Exhaust speed"]
    assert panel.notes_label.text() == "Note: one burn"
    assert not panel.back_button.isEnabled()

    panel.open_buttons["Exhaust speed"].click()
    assert panel.trace is speed and panel.result_label.text() == "Exhaust speed: Ve = 2940 [m/s]"
    assert [label.text() for label in panel.source_labels] == ["scenario: propellant_budget.isp_s"]
    assert panel.notes_label.isHidden()
    assert panel.back_button.isEnabled()
    panel.back()
    assert panel.trace is propellant and not panel.back_button.isEnabled()


def test_an_input_from_a_trace_the_explanation_lacks_is_not_a_link(panel):
    from spacemissionstudio.gui.calculation_panel import Explanation

    propellant, _speed = _two_traces()
    panel.explain(Explanation("Budget: sat-1", [propellant]))
    assert panel.source_labels[1].text() == "trace: Exhaust speed"
    assert panel.open_buttons == {}
    assert not panel.open("Exhaust speed")
    assert panel.trace is propellant


def test_copy_puts_the_trace_on_the_clipboard_as_the_command_line_prints_it(panel):
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.calculation_panel import Explanation

    propellant, speed = _two_traces()
    panel.explain(Explanation("Budget: sat-1", [propellant, speed]))
    panel.copy_button.click()
    assert QApplication.clipboard().text() == "\n".join(propellant.text())


def test_an_explanation_without_traces_shows_the_empty_panel(panel):
    from spacemissionstudio.gui.calculation_panel import Explanation

    panel.explain(Explanation("Budget: sat-1", list(_two_traces())))
    panel.explain(Explanation("Budget: sat-1", []))
    assert panel.trace is None and not panel.empty_label.isHidden() and panel.body.isHidden()


# -- the pages' Show calculation ----------------------------------------------------------------

def _budget_scenario():
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio.schema.scenario import PropellantBudgetConfig

    scenario = load_scenario(_TEMPLATE_18)
    scenario.spacecraft[0].propellant_budget = PropellantBudgetConfig(
        in_plane_control_delta_v_m_s=100.0, collision_avoidance_count=3.0)  # [m/s], [-]
    return scenario


def _no_reentry(*_args):
    return 0.0, 400.0, 0.5, []


def test_the_budget_shows_the_picked_rows_calculation_or_the_total(qtbot):
    """With a row picked, Show calculation sends that row's delta-V trace
    first; with none, the propellant total's. Every trace of the budget is
    in the explanation."""
    from spacemissionstudio.engine import propellant_budget as pb
    from spacemissionstudio.gui.budget_widget import BudgetWidget

    scenario = _budget_scenario()
    name = scenario.spacecraft[0].name
    budget = pb.compute_budget(scenario, name, reentry_solver=_no_reentry)
    widget = BudgetWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    assert not widget.calculation_button.isEnabled()
    widget._show(budget)
    assert widget.calculation_button.isEnabled()

    with qtbot.waitSignal(widget.calculation_requested) as sent:
        widget.calculation_button.click()
    explanation = sent.args[0]
    assert explanation.title == f"Budget: {name}"
    assert explanation.traces[0] is budget.traces["total_propellant"]
    expected = [t for row in budget.rows for t in (row.delta_v_trace, row.propellant_trace) if t is not None]
    expected += list(budget.traces.values())
    assert sorted(map(id, explanation.traces)) == sorted(map(id, expected))

    at = next(i for i, row in enumerate(budget.rows) if row.contributor.startswith("Collision avoidance"))
    widget.table.view.selectRow(widget.table.proxy.mapFromSource(widget.table.model.index(at, 0)).row())
    with qtbot.waitSignal(widget.calculation_requested) as sent:
        widget.calculation_button.click()
    assert sent.args[0].traces[0] is budget.rows[at].delta_v_trace


@pytest.mark.requires_basilisk
def test_end_of_life_shows_the_lifetimes_calculation(qtbot):
    """After an estimate, Show calculation sends the lifetime's trace first,
    then the orbit, mass, ballistic coefficient and rule traces."""
    from spacemissionstudio.engine import lifetime
    from spacemissionstudio.gui.lifetime_widget import LifetimeWidget
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATE_18)
    scenario.space_weather.atmosphere_model = "exponential"
    name = scenario.spacecraft[0].name
    end = lifetime.end_of_life(scenario, name, max_years=5.0)
    widget = LifetimeWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    assert not widget.calculation_button.isEnabled()
    widget._computed_for = scenario
    widget._show(end)
    assert widget.calculation_button.isEnabled()
    with qtbot.waitSignal(widget.calculation_requested) as sent:
        widget.calculation_button.click()
    explanation = sent.args[0]
    assert explanation.title == f"End of Life: {name}"
    assert explanation.traces[0] is end.traces["lifetime"]
    assert sorted(map(id, explanation.traces)) == sorted(map(id, end.traces.values()))
    widget._show_error("no")
    assert not widget.calculation_button.isEnabled()


def test_the_dashboard_shows_the_link_margins_calculation_from_the_run(qtbot):
    """At a time with a link, Show calculation sends the margin's trace,
    its range and pointing error taken from the run's series; without a
    link the button is off."""
    from test_mission_dashboard_widget import _result_set, _scenario

    from spacemissionstudio.engine import link_budget
    from spacemissionstudio.gui.mission_dashboard_widget import MissionDashboardWidget

    widget = MissionDashboardWidget()
    qtbot.addWidget(widget)
    scenario = _scenario()
    widget.set_result(_result_set(active_mode=[1], pointing_error_deg=[5.0], has_access=[1], slant_range_m=[1.5e6],
                                  battery_charge_wh=[33.0], net_power_w=[-10.0]), scenario)
    assert widget.calculation_button.isEnabled()
    with qtbot.waitSignal(widget.calculation_requested) as sent:
        widget.calculation_button.click()
    explanation = sent.args[0]
    margin = explanation.traces[0]
    assert explanation.title == "Link: sat-1 to gs-1"
    assert margin.quantity == "Link margin"
    expected = link_budget.link_budget_breakdown(1.5e6, scenario.spacecraft[0].rf_link, scenario.ground_stations[0],
                                                 5.0, scenario)
    assert margin.value == pytest.approx(expected.margin_db, abs=1e-12)
    sources = {q.source for t in explanation.traces for q in t.inputs}
    assert "last run: gs-1.access_to_sat-1.slant_range, at the end of the run" in sources
    assert "last run: sat-1.comms_pointing.pointing_error_deg, at the end of the run" in sources

    widget.set_result(_result_set(active_mode=[1], pointing_error_deg=[5.0], has_access=[0], slant_range_m=[1.5e6],
                                  battery_charge_wh=[33.0], net_power_w=[-10.0]), scenario)
    assert not widget.calculation_button.isEnabled()


def test_a_results_overview_card_shows_how_its_figure_was_computed(qtbot):
    """A card of Results > Overview, clicked or given Enter, sends its
    figure's trace; the main window shows it in the Calculation panel."""
    from PySide6.QtCore import Qt
    from test_results_overview import _result

    from spacemissionstudio.gui.results_overview import ResultsOverview

    overview = ResultsOverview()
    qtbot.addWidget(overview)
    with qtbot.waitSignal(overview.summarized, timeout=10000):
        overview.set_run(_result(), "Run 1")
    cards = {card.figure.key: card for card in overview.cards}
    card = cards["sat-1.lowest_link_margin"]
    assert card.focusPolicy() == Qt.FocusPolicy.StrongFocus and card.toolTip() == "Show how this was computed"
    with qtbot.waitSignal(overview.calculation_requested) as sent:
        qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    assert sent.args[0].title == "Run 1: Lowest link margin"
    assert sent.args[0].traces == [card.figure.trace]
    battery = cards["sat-1.lowest_battery_charge"]
    with qtbot.waitSignal(overview.calculation_requested) as sent:
        qtbot.keyClick(battery, Qt.Key.Key_Return)
    assert sent.args[0].traces[0].quantity == "Lowest battery charge"
    overview.wait_for_worker()


def test_the_timeline_shows_how_the_selected_event_was_found(qtbot):
    """With an event selected in the Timeline's table, Show calculation
    sends its trace (its span first, then its delta-V); with none selected,
    or without a run, the button is off."""
    import numpy as np
    from PySide6.QtCore import Qt

    from spacemissionstudio.engine import events
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui.event_timeline_widget import EventTimelineWidget

    t = np.arange(8, dtype=float) * 60.0  # [s]
    result = ResultSet("burn")
    result.add(TimeSeries("sat.station_keeping.burn_on", t, ("burn_on",),
                          np.array([0, 0, 1, 1, 0, 0, 0, 0], dtype=float)[:, None]))
    result.add(TimeSeries("sat.station_keeping.delta_v", t, ("cumulative_delta_v",),
                          np.array([0, 0, 0, 0.3, 0.7, 0.7, 0.7, 0.7])[:, None], "m/s"))
    widget = EventTimelineWidget()
    qtbot.addWidget(widget)
    widget.set_result(result)
    assert not widget.calculation_button.isEnabled()
    widget.table.view.setCurrentIndex(widget.table.view.model().index(0, 0))
    assert widget.calculation_button.isEnabled()
    with qtbot.waitSignal(widget.calculation_requested) as sent:
        qtbot.mouseClick(widget.calculation_button, Qt.MouseButton.LeftButton)
    explanation = sent.args[0]
    (burn,) = events.extract_events(result)
    assert explanation.title == "Event: station-keeping burn (sat)"
    assert explanation.traces == events.trace_of(result, burn)
    assert [trace.quantity for trace in explanation.traces] == ["station-keeping burn (sat)", "Delta-V"]
    from spacemissionstudio.gui.calculation_panel import CalculationPanel

    panel = CalculationPanel()
    qtbot.addWidget(panel)
    panel.explain(explanation)
    panel.open_buttons["Delta-V"].click()  # the delta-V is opened from the burn
    assert panel.trace is explanation.traces[1]
    widget.set_result(None)
    assert not widget.calculation_button.isEnabled() and widget.explanation() is None


def test_the_dashboards_power_card_shows_how_its_figures_were_read(qtbot):
    """The Power card's Show calculation sends the state of charge first
    (the figure shown), then the net power and the charge, read at the
    run's end; without a run the button is off."""
    from test_mission_dashboard_widget import _result_set, _scenario

    from spacemissionstudio.gui.mission_dashboard_widget import MissionDashboardWidget

    widget = MissionDashboardWidget()
    qtbot.addWidget(widget)
    scenario = _scenario()  # a 40 W*h battery
    widget.set_result(_result_set(active_mode=[1, 1], pointing_error_deg=[5.0, 5.0], has_access=[1, 1],
                                  slant_range_m=[1.5e6, 1.5e6], battery_charge_wh=[33.0, 30.0],
                                  net_power_w=[-10.0, -12.0]), scenario)
    assert widget.power_calculation_button.isEnabled()
    with qtbot.waitSignal(widget.calculation_requested) as sent:
        widget.power_calculation_button.click()
    explanation = sent.args[0]
    assert explanation.title == "Power: sat-1"
    assert [t.quantity for t in explanation.traces] == ["State of charge", "Net power", "Battery charge"]
    soc, net, charge = explanation.traces
    assert soc.value == 75.0 and widget.battery_soc_label.text() == "75%"  # [%] 30 of 40 W*h
    assert net.value == -12.0 and widget.net_power_label.text() == "-12.00 W"
    assert charge.inputs[0].source.startswith("last run: sat-1.battery_charge, sample 1 (t = 1 s)")
    widget.set_result(None, scenario)
    assert widget.power_explanation() is None


# -- the main window ----------------------------------------------------------------------------

@pytest.fixture
def window(qtbot, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    return w


def test_the_calculation_panel_is_hidden_until_a_page_asks_for_it(window, qtbot):
    """A new window has no Calculation panel; a page's Show calculation
    opens it with that number's trace; View › Calculation toggles it, and
    Reset layout hides it again."""
    from spacemissionstudio.gui.calculation_panel import Explanation

    window.show()
    qtbot.waitExposed(window)
    assert window.calculation_dock.isHidden()
    propellant, speed = _two_traces()
    window.budget_widget.calculation_requested.emit(Explanation("Budget: sat-1", [propellant, speed]))
    assert window.calculation_dock.isVisible()
    assert window.calculation_panel.trace is propellant
    window.reset_layout()
    assert window.calculation_dock.isHidden()
    window.calculation_dock.toggleViewAction().trigger()
    assert window.calculation_dock.isVisible()
    window.calculation_dock.hide()
    window.results_overview.calculation_requested.emit(Explanation("Run 1: Delta-V", [speed]))
    assert window.calculation_dock.isVisible() and window.calculation_panel.trace is speed
