#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
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
"""Run › Design Checks (model analyses): the page checks the chosen
spacecraft off the GUI thread, shows each check's table, the findings and
the out-of-scope note, and saves the record and tables with their
provenance, logged as an export."""

import json
from pathlib import Path

from spacemissionstudio.gui import export_log
from spacemissionstudio.gui.design_checks_widget import STIFFNESS_NOTE, DesignChecksWidget
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import LauncherConfig, MountConfig, MountedEquipmentConfig, PartPoseConfig

_TEMPLATE = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates" \
    / "28_octagonal_bus_3d_model.json"


def _checked(qtbot, scenario):
    page = DesignChecksWidget()
    qtbot.addWidget(page)
    page.set_scenario(scenario, _TEMPLATE.parent)
    assert page.check_button.isEnabled() and not page.save_button.isEnabled()
    page.check()
    qtbot.waitUntil(lambda: page.report is not None and page._worker is None, timeout=30000)
    return page


def test_the_page_shows_each_check_and_its_findings(qtbot, tmp_path):
    """A camera looking at a panel and folded panels below the separation
    plane: the field of view row is 100 % blocked, the launcher table lists
    the two panels, the findings name both, and Save writes the record and
    the tables with their provenance."""
    scenario = load_scenario(_TEMPLATE)
    sc = scenario.spacecraft[0]
    sc.model.equipment.append(MountedEquipmentConfig("camera", "camera", MountConfig(
        position_m=[0.0, 1.7, 1.0], boresight=[0.0, 0.0, -1.0], field_of_view_deg=40.0)))
    sc.model.stowed += [PartPoseConfig("panel +y", [0.0, 0.62, 0.0], [90.0, 0.0, 0.0]),
                        PartPoseConfig("panel -y", [0.0, -0.62, 0.0], [90.0, 0.0, 0.0])]
    sc.model.launcher = LauncherConfig(shape="cylinder", diameter_m=2.0, height_m=3.0, origin_b_m=[0.0, 0.0, -0.7],
                                       source="a test envelope")
    page = _checked(qtbot, scenario)
    assert page.fov_table.cell(0, 0) == "camera" and page.fov_table.cell(0, 3) == "100.0"
    assert [page.launcher_table.cell(r, 0) for r in range(page.launcher_table.row_count())] == ["panel +y",
                                                                                                "panel -y"]
    assert "panel +y is 300 mm outside" in page.findings_label.text()
    assert "camera's field of view (deployed) is 100.0 % blocked" in page.findings_label.text()
    assert page.mass_group.isVisibleTo(page) and "launch 300.00 kg" in page.mass_label.text()
    assert STIFFNESS_NOTE in page.notes_label.text() and page.save_button.isEnabled()
    written = page.save(tmp_path / "out")
    assert {p.name for p in written} == {"design_checks.json", "field_of_view.csv", "launcher_envelope.csv",
                                         "mass_budget.csv"}
    record = json.loads((tmp_path / "out" / "design_checks.json").read_text(encoding="utf-8"))
    assert record["kind"] == "design_checks" and len(record["findings"]) == 3
    assert (tmp_path / "out" / "mass_budget.csv.provenance.json").is_file()
    assert export_log.last("design_checks")[1] == str(tmp_path / "out")


def test_a_spacecraft_without_a_model_shows_its_mass_only(qtbot):
    """No 3D model: no geometric table, the mass budget as one line, and
    no finding."""
    scenario = load_scenario(_TEMPLATE)
    scenario.spacecraft[0].model = None
    page = _checked(qtbot, scenario)
    assert not page.fov_group.isVisibleTo(page) and not page.launcher_group.isVisibleTo(page)
    assert page.mass_table.row_count() == 1 and page.findings_label.text() == "No design finding."
    page.set_scenario(None)
    assert not page.check_button.isEnabled()
