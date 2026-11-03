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
"""The app's exports with their provenance (transparency plan, Phase 9a):
the Monte Carlo runs table with the batch's provenance beside it, and the
lifetime estimate as JSON from the End of Life page."""

import json

import pytest

pytestmark = pytest.mark.requires_gui


def test_the_monte_carlo_table_has_the_batchs_provenance_beside_it(qtbot, tmp_path):
    """<file>.provenance.json beside the CSV: the table's spacecraft and runs,
    the batch folder and its archive.provenance.json, or that it was not
    found."""
    from test_monte_carlo_results_widget import _save_batch

    from spacemissionstudio.gui.monte_carlo_results_widget import MonteCarloResultsWidget

    _save_batch(tmp_path)
    widget = MonteCarloResultsWidget()
    qtbot.addWidget(widget)
    widget.load_folder(tmp_path)
    path = widget.export_table_csv(tmp_path / "runs.csv")
    sidecar = json.loads((tmp_path / "runs.csv.provenance.json").read_text())
    assert sidecar["runs"] == 5 and sidecar["batch_folder"] == str(tmp_path)
    assert sidecar["batch_provenance"].startswith("not found")
    (tmp_path / "archive.provenance.json").write_text(json.dumps({"scenario_sha256": "ab" * 32}))
    widget.export_table_csv(path)
    assert json.loads((tmp_path / "runs.csv.provenance.json").read_text())["batch_provenance"] == {
        "scenario_sha256": "ab" * 32}


@pytest.mark.requires_basilisk
def test_the_lifetime_estimate_is_exported_as_its_record(qtbot, tmp_path):
    """Export JSON... writes the estimate shown, as `lifetime --out` does:
    the options it ran with, the decay curve and the provenance; a
    starting propellant set by hand only when there is one; the export is
    logged."""
    from spacemissionstudio.engine import lifetime
    from spacemissionstudio.gui import export_log
    from spacemissionstudio.gui.lifetime_widget import LifetimeWidget
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio.api import template

    scenario = load_scenario(template("22_starter_first_leo_satellite"))
    scenario.space_weather.atmosphere_model = "exponential"  # fast
    widget = LifetimeWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    assert not widget.export_button.isEnabled()
    end = lifetime.end_of_life(scenario, "my-sat", max_years=2.0, drag_coeff=2.2)
    widget._computed_for = scenario
    widget._show(end)
    assert widget.export_button.isEnabled()
    record = json.loads(widget.export_record(tmp_path / "life.json").read_text())
    assert record["kind"] == "lifetime" and record["inputs"]["max_years"] == 2.0
    assert record["inputs"]["drag_coeff"] == 2.2 and record["inputs"]["forecast_percentile"] == 50.0
    assert record["decay"]["perigee_altitude_km"] and record["provenance"]["scenario_sha256"]
    assert "propellant_kg" not in record["inputs"]
    widget._show(lifetime.end_of_life(scenario, "my-sat", max_years=2.0, drag_coeff=2.2, propellant_kg=1.5))
    edited = json.loads(widget.export_record(tmp_path / "edited.json").read_text())
    assert edited["inputs"]["propellant_kg"] == 1.5  # [kg] set on the page
    from PySide6.QtWidgets import QFileDialog

    target = tmp_path / "logged.json"
    qtbot_patch = pytest.MonkeyPatch()
    qtbot_patch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    try:
        widget._on_export()
    finally:
        qtbot_patch.undo()
    assert target.is_file() and export_log.last("lifetime_json")[1] == str(target)
