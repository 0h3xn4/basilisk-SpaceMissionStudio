#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Run comparison (UX/UI guidelines: keep finished runs in the session,
overlay a series from several runs, a diff of their inputs)."""

import numpy as np
import pytest

from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.gui.run_history import RunHistory


def _result(offset_m):
    t = np.arange(0.0, 3600.0, 60.0)  # [s]
    result = ResultSet("demo")
    result.add(TimeSeries("sat-1.orbit_elements.semi_major_axis", t, ("semi_major_axis",),
                          np.full((t.size, 1), 6928e3 + offset_m), units="m"))
    return result


def test_the_history_keeps_the_last_runs_numbered():
    """The run history keeps the last runs, numbered and labelled; older ones
    are dropped."""
    history = RunHistory(max_runs=2)
    for n in range(3):
        history.add({"name": f"s{n}"}, _result(0.0), "2026-01-01T00:00:00")
    assert [r.number for r in history.runs] == [2, 3]
    assert history.latest().label.startswith("Run 3 (") and history.latest().label.endswith("s2")
    assert history.find(1) is None and history.find(2).scenario == {"name": "s1"}


@pytest.fixture
def results(qtbot):
    from spacemissionstudio.gui.results_widget import ResultsWidget

    widget = ResultsWidget()
    qtbot.addWidget(widget)
    history = RunHistory()
    first = history.add({"name": "demo", "sim_settings": {"duration_days": 1.0}}, _result(0.0), "2026-01-01T00:00:00")
    second = history.add({"name": "demo", "sim_settings": {"duration_days": 2.0}}, _result(500.0),
                         "2026-01-01T00:00:00", cancelled=True)
    widget.set_result(second.result, second.epoch_utc)
    widget.set_runs(history.runs, second)
    return widget, first, second


def test_an_earlier_run_is_overlaid_dashed_and_named(results):
    """An earlier run chosen for comparison is overlaid dashed, named in the
    legend, at its true offset."""
    widget, first, _second = results
    assert widget.compare_combo.isVisibleTo(widget) and widget.compare_combo.count() == 2
    assert len(widget.figure.data) == 1
    widget.compare_combo.setCurrentIndex(widget.compare_combo.findData(first.number))
    traces = widget.figure.data
    assert len(traces) == 2 and traces[1].line.dash == "dash" and traces[1].name.endswith("(Run 1)")
    assert widget.figure.layout.showlegend
    assert np.allclose(np.asarray(traces[0].y) - np.asarray(traces[1].y), 0.5)  # [km] the 500 m offset


def test_the_input_differences_name_the_changed_fields(results):
    """The input differences name the changed field with both values, and the
    button shows them, in a window of its own (not modal)."""
    from PySide6.QtWidgets import QTableWidget

    widget, first, _second = results
    widget.compare_combo.setCurrentIndex(widget.compare_combo.findData(first.number))
    assert widget.input_differences() == [("sim_settings.duration_days", 2.0, 1.0)]
    widget.diff_button.click()
    window = widget.input_differences_window
    assert window.isVisible() and window.windowTitle() == "Input differences" and not window.isModal()
    table = window.findChild(QTableWidget)
    assert table.rowCount() == 1 and table.item(0, 0).text() == "sim_settings.duration_days"


def test_no_earlier_run_hides_the_comparison(qtbot):
    """With one run, the comparison is hidden and there are no differences."""
    from spacemissionstudio.gui.results_widget import ResultsWidget

    widget = ResultsWidget()
    qtbot.addWidget(widget)
    history = RunHistory()
    only = history.add({"name": "demo"}, _result(0.0), "2026-01-01T00:00:00")
    widget.set_runs(history.runs, only)
    assert not widget.compare_combo.isVisibleTo(widget) and widget.input_differences() == []
