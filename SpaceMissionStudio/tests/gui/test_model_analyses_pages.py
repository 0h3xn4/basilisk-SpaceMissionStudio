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
"""The model analyses' GUI pages: End of Life's preliminary re-entry
section and Results › Model Analyses, each computed and shown from the
3D model or the run, saved with its provenance and logged as an export."""

import json
from pathlib import Path

import pytest

from spacemissionstudio.gui import export_log
from spacemissionstudio.gui.model_analyses_widget import ModelAnalysesWidget
from spacemissionstudio.gui.reentry_section import PRELIMINARY, ReentrySection
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import ModelAnalysesConfig, MountConfig

pytest.importorskip("Basilisk")
_TEMPLATE = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates" \
    / "28_octagonal_bus_3d_model.json"
_MATERIALS = {"bus": "aluminium_6061_t6", "panel +y": "cfrp", "panel -y": "cfrp", "dish": "aluminium",
              "star tracker": "titanium_6al_4v", "battery": "stainless_steel"}


def _scenario():
    scenario = load_scenario(_TEMPLATE)
    for part in scenario.spacecraft[0].model.parts:
        part.material = _MATERIALS[part.name]
    return scenario


def test_the_reentry_section_estimates_labels_and_saves(qtbot, tmp_path):
    """Every part is a row; with 25 people per km^2 the risk is compared
    with the limit; the section says it is preliminary; Save writes the
    record and logs the export."""
    section = ReentrySection()
    qtbot.addWidget(section)
    scenario = _scenario()
    section.set_scenario(scenario, _TEMPLATE.parent)
    assert section.compute_button.isEnabled()
    assert any(PRELIMINARY == label.text() for label in section.findChildren(type(section.result_label)))
    section.density_check.setChecked(True)
    section.density_field.setValue(25.0)
    section.compute()
    qtbot.waitUntil(lambda: section.estimate is not None and section._worker is None, timeout=60000)
    assert section.table.row_count() == 6
    assert "Casualty risk" in section.result_label.text() and "NASA-STD-8719.14B" in section.result_label.text()
    record = json.loads(section.save(tmp_path / "reentry.json").read_text(encoding="utf-8"))
    assert record["kind"] == "reentry_estimate" and "Preliminary" in record["label"]
    assert export_log.last("reentry_json")[1].endswith("reentry.json")
    scenario.spacecraft[0].model = None
    section.set_scenario(scenario)
    assert not section.compute_button.isEnabled()


@pytest.mark.slow
def test_the_model_analyses_tab_shows_a_runs_analyses(qtbot, tmp_path):
    """A short run with disturbance torques and blinding: their tables
    show, the momentum is summarised, and Save writes the record and the
    tables."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = _scenario()
    scenario.sim_settings.duration_days = 0.01  # [day]
    sc = scenario.spacecraft[0]
    sc.sensors[0].mount = MountConfig(part="star tracker", position_m=[0.0, 0.0, 0.125], boresight=[0.0, 0.0, 1.0],
                                      field_of_view_deg=20.0, exclusion_sun_deg=30.0)
    sc.model_analyses = ModelAnalysesConfig(disturbance_torques=True, sensor_blinding=True)
    result = SimulationService(scenario).run()
    page = ModelAnalysesWidget()
    qtbot.addWidget(page)
    assert ModelAnalysesWidget.has_analyses(scenario)
    page.set_run(scenario, result)
    assert page.groups["disturbance_torques"].isVisibleTo(page) and page.groups["blinding"].isVisibleTo(page)
    assert not page.groups["brightness"].isVisibleTo(page)
    assert page.tables["disturbance_torques"].row_count() == 5 and "Momentum" in page.summary_label.text()
    written = page.save(tmp_path / "out")
    assert {p.name for p in written} >= {"model_analyses.json", "disturbance_torques.csv", "blinding.csv"}
    assert export_log.last("model_analyses")[1] == str(tmp_path / "out")
    page.set_run(None, None)
    assert not page.save_button.isEnabled()


def test_the_spacecraft_editor_keeps_the_model_analyses(qtbot):
    """The 3D model tab's Model analyses group gives back what it was
    given, observer sites included; unchecked, none; a site whose number
    does not read is refused with its row."""
    from spacemissionstudio.gui.model_analyses_editor import ModelAnalysesGroup
    from spacemissionstudio.schema.scenario import ObserverSiteConfig

    config = ModelAnalysesConfig(sensor_blinding=True, array_shading=True,
                                 residual_dipole_a_m2=[0.0, 0.1, -0.2], samples=512,
                                 observers=[ObserverSiteConfig("boulder", 40.0, -105.3, 1600.0, 10.0)])
    group = ModelAnalysesGroup(config)
    qtbot.addWidget(group)
    assert group.to_config() == config
    assert group.field_widget("samples") is group.samples and group.field_widget("nothing") is None
    group.observers.item(0, 1).setText("north")
    with pytest.raises(ValueError, match="row 1"):
        group.to_config()
    group.setChecked(False)
    assert group.to_config() is None
    empty = ModelAnalysesGroup(None)
    qtbot.addWidget(empty)
    assert not empty.isChecked() and not empty.switches["array_shading"].isChecked()
