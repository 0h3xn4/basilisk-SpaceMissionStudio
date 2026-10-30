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

"""Results › Overview (UI overhaul M6a): the run's headline figures
(engine.run_summary) as metric cards, worked out in a worker thread;
critical only below the thresholds the scenario sets (link margin under
0 dB, the battery at 0), with an icon and a word; the provenance in a
popover; an empty state with Run."""

import threading
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


def _result(margin_db=3.0, lowest_charge=20.0):
    """A spacecraft with a battery and a pass over one station."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries

    t = np.linspace(0.0, 3600.0, 61)  # [s]
    access = ((t > 600.0) & (t < 1200.0)).astype(float)  # [-] in view for ten minutes
    result = ResultSet("demo")
    result.add(TimeSeries("sat-1.position_N", t, ("x", "y", "z"), np.column_stack([t, t, t]), units="m"))
    result.add(TimeSeries("sat-1.battery_charge", t, ("battery_charge",),
                          np.linspace(50.0, lowest_charge, t.size)[:, None], units="W*h"))
    result.add(TimeSeries("berlin.access_to_sat-1.has_access", t, ("has_access",), access[:, None]))
    result.add(TimeSeries("berlin.access_to_sat-1.link_margin_db", t, ("link_margin_db",),
                          np.where(access > 0, margin_db, np.nan)[:, None], units="dB"))
    return result


@pytest.fixture
def overview(qtbot):
    from spacemissionstudio.gui.results_overview import ResultsOverview

    view = ResultsOverview()
    qtbot.addWidget(view)
    yield view
    view.wait_for_worker()


def _show(overview, qtbot, result, **kwargs):
    with qtbot.waitSignal(overview.summarized, timeout=10000):
        overview.set_run(result, "Run 1", **kwargs)
    return {card.figure.key.rsplit(".", 1)[-1]: card for card in overview.cards}


def test_before_a_run_the_overview_offers_run(overview, qtbot):
    overview.set_run(None)
    assert overview.stack.currentWidget() is overview.empty
    with qtbot.waitSignal(overview.run_requested, timeout=1000):
        overview.empty_run_button.click()


def test_each_figure_is_a_card_with_its_value_and_unit(overview, qtbot):
    """The run's figures, as run_summary gives them; neutral cards."""
    from spacemissionstudio.engine import run_summary

    cards = _show(overview, qtbot, _result())
    assert [card.figure for card in overview.cards] == run_summary.summarize(_result())
    margin = cards["lowest_link_margin"]
    assert (margin.value.text(), margin.unit.text()) == ("3.00", "dB")
    assert cards["passes"].unit.text() == ""  # a count has no unit
    assert all(card.status is None and card.status_row.isHidden() for card in overview.cards)
    assert overview.title_label.text() == "Run 1"


def test_only_the_scenarios_thresholds_make_a_card_critical(overview, qtbot):
    """A link margin under 0 dB and a battery at 0: critical, with an
    icon and the words; the other cards stay neutral."""
    cards = _show(overview, qtbot, _result(margin_db=-1.5, lowest_charge=0.0))
    margin, battery = cards["lowest_link_margin"], cards["lowest_battery_charge"]
    assert margin.status == "Link margin below 0 dB" and not margin.status_row.isHidden()
    assert battery.status == "Battery empty" and not battery.status_icon.pixmap().isNull()
    assert margin.value.property("tone") == "critical"
    assert [key for key, card in cards.items() if card.status] == ["lowest_link_margin", "lowest_battery_charge"]


def test_the_link_card_uses_the_runs_required_margin(overview, qtbot):
    """A run whose project configuration required a 5 dB margin
    (``link.required_margin_db``, in its provenance): a lowest margin of
    3 dB is critical, and the card names the 5 dB."""
    from types import SimpleNamespace

    result = _result(margin_db=3.0)
    result.provenance = SimpleNamespace(configuration={"file": None, "overrides": {
        "link.required_margin_db": {"value": 5.0, "default": 0.0, "unit": "[dB]", "source": "-"}}})
    margin = _show(overview, qtbot, result)["lowest_link_margin"]
    assert margin.status == "Link margin below 5 dB" and not margin.status_row.isHidden()


def test_the_battery_card_uses_the_runs_critical_fraction(overview, qtbot):
    """A run whose project configuration set a depth-of-discharge limit
    (``results.battery_critical_fraction`` 0.5, in its provenance): a
    lowest charge of 20 W*h from a 50 W*h battery is critical, with the
    limit in its words. At the default, or without the capacity (no
    scenario as run), only an empty battery is."""
    from types import SimpleNamespace

    scenario = {"spacecraft": [{"name": "sat-1", "power": {"battery_capacity_wh": 50.0}}]}  # [W*h]
    result = _result(lowest_charge=20.0)  # [W*h]
    assert _show(overview, qtbot, result, scenario=scenario)["lowest_battery_charge"].status is None
    result.provenance = SimpleNamespace(configuration={"file": None, "overrides": {
        "results.battery_critical_fraction": {"value": 0.5, "default": 0.0, "unit": "[-]", "source": "-"}}})
    battery = _show(overview, qtbot, result, scenario=scenario)["lowest_battery_charge"]
    assert battery.status == "Battery at or below 50% of capacity" and not battery.status_row.isHidden()
    assert _show(overview, qtbot, result)["lowest_battery_charge"].status is None


def test_the_figures_are_worked_out_off_the_gui_thread(overview, qtbot, monkeypatch):
    from spacemissionstudio.engine import run_summary

    threads = []
    real = run_summary.summarize
    monkeypatch.setattr(run_summary, "summarize", lambda result: threads.append(threading.current_thread()) or
                        real(result))
    _show(overview, qtbot, _result())
    assert threads and threads[0] is not threading.main_thread()


def test_a_run_shown_while_another_is_worked_out_wins(overview, qtbot):
    """Two runs one after the other: the cards are the second's."""
    overview.set_run(_result(margin_db=5.0), "Run 1")
    with qtbot.waitSignal(overview.summarized, timeout=10000):
        overview.set_run(_result(margin_db=-2.0), "Run 2")
    qtbot.waitUntil(lambda: not overview.pending, timeout=10000)
    margin = next(card for card in overview.cards if card.figure.key.endswith("lowest_link_margin"))
    assert margin.figure.value == -2.0 and overview.title_label.text() == "Run 2"


def test_the_provenance_is_in_a_popover(overview, qtbot):
    _show(overview, qtbot, _result(), provenance={"basilisk_version": "2.12.0", "integrator": "rk4"})
    overview.show()
    overview.provenance_button.click()
    assert overview.popover.isVisible()
    assert "basilisk_version: 2.12.0" in overview.popover.body.text()
    overview.popover.hide()


def test_a_run_ending_shows_its_overview(qtbot, monkeypatch, tmp_path):
    """The main window: Results › Overview is the first view of Results and
    holds the run just ended."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui import autosave
    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    assert window.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    qtbot.waitUntil(lambda: not window.run_history.loading, timeout=10000)
    assert window.results_views.widget(0) is window.results_overview
    window._last_run_scenario = window.scenario_editor.to_scenario()
    window._start_busy("Running")
    result = _result()
    with qtbot.waitSignal(window.results_overview.summarized, timeout=10000):
        window._on_run_finished(result)
    assert window.results_overview.title_label.text().startswith("Run ")
    assert window.results_overview.cards
    qtbot.waitUntil(lambda: not window.run_history.saving, timeout=10000)
