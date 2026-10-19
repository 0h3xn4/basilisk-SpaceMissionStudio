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

"""Vizard panels for an ROE formation (engine.vizard, engine.roe_formation):
the follower gets the same gauges as phasing keeping (delta-V, R/T/N from
the chief) plus the closest radial/cross-track approach, each wired to the
controller's own message, and the controller writes those messages with
the values its results record. Like test_vizard_fuel_tank_panel.py, the
panel test calls enable_vizard on a bare simulation."""

import math
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.requires_basilisk

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"


class _Controller:
    """The attributes enable_vizard reads from a RoeFormationController."""

    def __init__(self):
        from Basilisk.architecture import messaging

        self.chiefName = "chief-1"
        self.deltaVOutMsg = messaging.DataStorageStatusMsg()
        self.separationRadialOutMsg = messaging.DataStorageStatusMsg()
        self.separationTransverseOutMsg = messaging.DataStorageStatusMsg()
        self.separationNormalOutMsg = messaging.DataStorageStatusMsg()
        self.minSeparationOutMsg = messaging.DataStorageStatusMsg()


def _panels(tmp_path, follower_name):
    from Basilisk.simulation import spacecraft
    from Basilisk.utilities import SimulationBaseClass, macros

    from spacemissionstudio.engine import vizard

    sim = SimulationBaseClass.SimBaseClass()
    process = sim.CreateNewProcess("process")
    process.addTask(sim.CreateNewTask("task", macros.sec2nano(1.0)))
    sc_object = spacecraft.Spacecraft()
    sc_object.ModelTag = follower_name
    sim.AddModelToTask("task", sc_object)
    request = vizard.VizardRequest(save_file=str(tmp_path / "roe.viz.bin"))
    _viz, _bridges, storage_list, _sensors = vizard.enable_vizard(
        sim, "task", [sc_object], request, roe_formation_by_spacecraft={follower_name: _Controller()})
    return storage_list[0]


def test_an_roe_follower_gets_delta_v_rtn_and_approach_panels(tmp_path):
    """Five gauges, labelled for the chief, in phasing keeping's colours
    and units, plus the R/N gap in metres."""
    panels = _panels(tmp_path, "follower-1")
    assert [(p.label, p.type, p.units) for p in panels] == [
        ("ROE Delta-V", "Delta-V", "m/s"),
        ("R vs chief-1", "Separation", "km"),
        ("T vs chief-1", "Separation", "km"),
        ("N vs chief-1", "Separation", "km"),
        ("R/N gap", "Separation", "m"),
    ]


def test_a_short_follower_name_gets_labels_that_fit(tmp_path):
    """Vizard cuts a label at the panel's width, which follows the
    spacecraft's name: on a short name the delta-V label shortens."""
    labels = [p.label for p in _panels(tmp_path, "sat")]
    assert labels[0] == "ROE dV"
    assert all(len(label) <= 9 for label in labels)


def test_the_gauge_scales_follow_the_targets():
    """Twice the largest extent any target asks for (2 km behind: 4 km;
    a 300 m helix: 1.2 km along-track), and twice the largest closest
    approach (300 m: 600 m); floors for a formation of zeros."""
    from spacemissionstudio.engine.roe_formation import gauge_scales
    from spacemissionstudio.schema import RoeFormationConfig, RoeTargetConfig

    config = RoeFormationConfig(chief_spacecraft="chief-1", targets=[
        RoeTargetConfig(0.0, [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]),  # [m]
        RoeTargetConfig(1.0, [0.0, 0.0, 0.0, 300.0, 0.0, 300.0])])  # [m]
    assert gauge_scales(config) == pytest.approx((4.0, 600.0))  # [km], [m]
    zeros = RoeFormationConfig(chief_spacecraft="chief-1", targets=[RoeTargetConfig(0.0, [0.0] * 6)])
    assert gauge_scales(zeros) == pytest.approx((0.1, 10.0))  # [km], [m]


def test_the_controller_publishes_what_its_results_record():
    """Template 29 with the helix from day 0.02, flown 0.1 days: the
    messages Vizard reads hold the controller's last delta-V and closest
    approach, and the Hill-frame separation of the two final states, each
    as a magnitude within its scale."""
    from Basilisk.utilities import orbitalMotion

    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATES / "29_roe_formation_helix.json")
    scenario.spacecraft[1].roe_formation.targets[1].start_day = 0.02  # [day]
    scenario.sim_settings.duration_days = 0.1  # [day]
    service = SimulationService(scenario)
    result = service.run()
    controller = service._handles["follower-1"].roe_formation_controller

    delta_v = controller.deltaVOutMsg.read()
    assert delta_v.storageLevel == pytest.approx(controller.deltaVLog[-1], abs=1e-6)  # [m/s]
    assert delta_v.storageLevel > 0.0 and delta_v.storageCapacity == pytest.approx(controller.dvBudgetMps)
    gap = controller.minSeparationOutMsg.read()
    assert gap.storageCapacity == pytest.approx(600.0)  # [m]
    assert gap.storageLevel == pytest.approx(min(controller.minSeparationLog[-1], 600.0), abs=1e-6)  # [m]

    states = [result.series[f"{name}.{part}_N"].data[-1] for name in ("chief-1", "follower-1")
              for part in ("position", "velocity")]  # [m], [m/s]
    rho, _ = orbitalMotion.rv2hill(*states)
    for msg, value_m in zip((controller.separationRadialOutMsg, controller.separationTransverseOutMsg,
                             controller.separationNormalOutMsg), rho):
        payload = msg.read()
        assert payload.storageCapacity == pytest.approx(4.0)  # [km]
        assert payload.storageLevel == pytest.approx(min(abs(value_m) / 1000.0, 4.0), abs=0.05)  # [km]
        assert payload.storageLevel >= 0.0 and not math.isnan(payload.storageLevel)
    assert np.isfinite([controller.deltaVLog[-1], controller.minSeparationLog[-1]]).all()
