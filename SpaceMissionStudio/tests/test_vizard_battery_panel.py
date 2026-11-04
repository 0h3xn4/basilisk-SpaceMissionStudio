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

"""The Vizard battery panel in watt-hours: Basilisk's battery message
carries watt-seconds and ``vizInterface`` shows them unscaled, so a 700 Wh
battery read "2520000 / 2520000 W-s". The panel now reads a bridge that
republishes the battery's state in watt-hours (``engine.vizard``).

Like ``tests/test_vizard_fuel_tank_panel.py``, this calls
``engine.vizard.enable_vizard`` against a bare ``SimulationBaseClass``.
Requires a Basilisk build (marked ``requires_basilisk``)."""

import pytest

pytestmark = pytest.mark.requires_basilisk

_CAPACITY_WH = 700.0  # [W*h]
_CHARGE_WH = 525.0  # [W*h]


def _run_with_a_battery(tmp_path):
    from Basilisk.simulation import simpleBattery, simplePowerSink, spacecraft
    from Basilisk.utilities import SimulationBaseClass, macros

    from spacemissionstudio.engine import vizard

    scSim = SimulationBaseClass.SimBaseClass()
    process = scSim.CreateNewProcess("proc")
    process.addTask(scSim.CreateNewTask("task", macros.sec2nano(1.0)))
    sc_object = spacecraft.Spacecraft()
    sc_object.ModelTag = "sat"
    scSim.AddModelToTask("task", sc_object, 10)
    sink = simplePowerSink.SimplePowerSink()  # a battery reports nothing without a power node
    sink.ModelTag = "sink"
    sink.nodePowerOut = 0.0  # [W] no load: the charge stays where it starts
    scSim.AddModelToTask("task", sink, 30)
    battery = simpleBattery.SimpleBattery()
    battery.ModelTag = "battery"
    battery.storageCapacity = _CAPACITY_WH * 3600.0  # [W*s]
    battery.storedCharge_Init = _CHARGE_WH * 3600.0  # [W*s]
    battery.addPowerNodeToModel(sink.nodePowerOutMsg)
    scSim.AddModelToTask("task", battery, 20)

    request = vizard.VizardRequest(save_file=str(tmp_path / "battery.viz.bin"))
    viz, bridges, storage_list, _ = vizard.enable_vizard(scSim, "task", [sc_object], request,
                                                         battery_by_spacecraft={"sat": battery})
    scSim.InitializeSimulation()
    scSim.ConfigureStopTime(macros.sec2nano(2.0))
    scSim.ExecuteSimulation()
    return viz, bridges, storage_list


def test_the_battery_panel_reads_watt_hours(tmp_path):
    """The panel's unit is Wh, and what it reads is the battery's level
    and capacity in watt-hours, not watt-seconds."""
    viz, bridges, storage_list = _run_with_a_battery(tmp_path)
    [panel] = [p for p in storage_list[0] if p.label == "Battery"]
    assert panel.units == "Wh"
    [bridge] = [b for b in bridges if b.ModelTag == "sat_batteryWattHours"]
    state = bridge.batteryOutMsg.read()
    assert state.storageCapacity == pytest.approx(_CAPACITY_WH)  # [W*h]
    assert state.storageLevel == pytest.approx(_CHARGE_WH, abs=0.1)  # [W*h] no load: unchanged
    assert panel.batteryStateInMsg.isLinked()
