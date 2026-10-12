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

"""Basilisk's device factories call exit() on settings they refuse (audit
H2). Validation now refuses those settings first; engine.fsw turns any exit
that still happens into an FswError instead of ending the process."""

import pytest

from spacemissionstudio.schema.scenario import ActuatorConfig

pytestmark = pytest.mark.requires_basilisk


def _sim():
    from Basilisk.utilities import SimulationBaseClass, macros

    sim = SimulationBaseClass.SimBaseClass()
    process = sim.CreateNewProcess("p")
    process.addTask(sim.CreateNewTask("t", macros.sec2nano(1.0)))
    return sim


def _spacecraft():
    from Basilisk.simulation import spacecraft

    sc = spacecraft.Spacecraft()
    sc.ModelTag = "sat-1"
    return sc


def test_a_refused_reaction_wheel_is_an_fsw_error_not_an_exit():
    """An unknown wheel type made rwFactory.create() call exit(1)."""
    from spacemissionstudio.engine.fsw import FswError, build_reaction_wheels

    wheel = ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Bogus"})
    with pytest.raises(FswError, match="rwFactory refused reaction wheel 'rw-1'"):
        build_reaction_wheels(_sim(), "t", "sat-1", _spacecraft(), [wheel])


def test_a_refused_thruster_is_an_fsw_error_not_an_exit():
    """An unknown thruster type made thrusterFactory.create() call exit(1)."""
    from spacemissionstudio.engine.fsw import FswError, build_thrusters

    thruster = ActuatorConfig(kind="thruster", name="thr-1",
                              params={"r_B": [1, 0, 0], "tHat_B": [1, 0, 0], "MaxThrust": 1.0,
                                      "thruster_type": "Bogus"})
    with pytest.raises(FswError, match="thrusterFactory refused thruster 'thr-1'"):
        build_thrusters(_sim(), "t", "sat-1", _spacecraft(), [thruster])
