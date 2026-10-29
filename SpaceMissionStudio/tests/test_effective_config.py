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
"""The effective configuration (engine.effective_config, transparency
audit Phase 2c): the defaults the engine applies behind the open
``params``, and the values Basilisk's factories give a device. The last
test runs a real build."""

import copy
import json
import pickle
from pathlib import Path
from types import SimpleNamespace

import pytest

from spacemissionstudio.engine import effective_config
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.command import Command

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"


def test_a_recorded_params_notes_each_missing_key_read_and_stays_the_same_dict():
    """A key read and missing is noted with the default its reader passed,
    the first read kept; a key the file gives is not. The dictionary still
    equals, serialises, copies and pickles as the plain one."""
    params = effective_config.RecordedParams({"fov_deg": 60.0}, "spacecraft[s].sensors[css].params")
    assert params.get("fov_deg", 90.0) == 60.0
    assert params.get("noise_std", 0.0) == 0.0
    assert params.get("noise_std", 1.0) == 1.0  # a second reader's default is returned, not recorded
    assert params.get("bias") is None
    assert params.defaults == {"noise_std": 0.0, "bias": None}
    assert params == {"fov_deg": 60.0} and json.dumps(params) == '{"fov_deg": 60.0}'
    for copied in (copy.deepcopy(params), pickle.loads(pickle.dumps(params))):
        assert copied == {"fov_deg": 60.0} and copied.where == params.where


def test_record_covers_every_open_params_and_starts_again_at_each_build():
    """Sensors, actuators, fsw_params, control_params and every command,
    nested ones too, each with its place in the scenario. Recording again
    (a second build) clears what was noted."""
    scenario = load_scenario(_TEMPLATES / "07_attitude_pointing_with_adcs_hardware.json")
    scenario.mission_sequence = [Command(kind="sequence", children=[Command(kind="propagate",
                                                                             params={"duration_s": 60.0})])]
    recorded = effective_config.record(scenario)
    places = {params.where for params in recorded}
    sc = scenario.spacecraft[0]
    assert {f"spacecraft[{sc.name}].sensors[{s.name}].params" for s in sc.sensors} <= places
    assert {f"spacecraft[{sc.name}].actuators[{a.name}].params" for a in sc.actuators} <= places
    assert {f"spacecraft[{sc.name}].fsw_params", f"spacecraft[{sc.name}].control_params",
            "mission_sequence[0].params", "mission_sequence[0].children[0].params"} <= places
    sc.control_params.get("K", 0.07)
    assert effective_config.defaults_used(recorded) == {f"spacecraft[{sc.name}].control_params": {"K": 0.07}}
    again = effective_config.record(scenario)
    assert again[0] is recorded[0] and effective_config.defaults_used(again) == {}


def test_a_factorys_device_values_are_read_back_per_actuator():
    """The values a Basilisk factory set are read from the devices it made,
    matched to the actuators in creation order; SWIG and numpy values are
    made plain."""
    devices = {"RW1": SimpleNamespace(Js=0.1, u_max=0.2, Omega_max=600.0),
               "RW2": SimpleNamespace(Js=0.3, u_max=0.4, Omega_max=700.0)}
    actuators = [SimpleNamespace(name="rw-a"), SimpleNamespace(name="rw-b")]
    found = effective_config.factory_devices(devices, actuators, "spacecraft[s].actuators",
                                             effective_config.RW_ATTRIBUTES)
    assert found == {"spacecraft[s].actuators[rw-a]": {"Js": 0.1, "u_max": 0.2, "Omega_max": 600.0},
                     "spacecraft[s].actuators[rw-b]": {"Js": 0.3, "u_max": 0.4, "Omega_max": 700.0}}


@pytest.mark.requires_basilisk
def test_a_run_records_the_defaults_it_applied_and_its_wheels_values():
    """Template 07: the attitude gains applied when unset are the
    inertia-scaled ones (audit 3.4), a sun sensor's field of view the
    engine's 90 deg, and each wheel's values those Basilisk's factory gave
    it, as the run's simulation holds them."""
    from spacemissionstudio.engine import solar_arrays
    from spacemissionstudio.engine.control_gains import default_mrp_gains_for_inertia
    from spacemissionstudio.engine.service import SimulationService

    scenario = load_scenario(_TEMPLATES / "07_attitude_pointing_with_adcs_hardware.json")
    sc = scenario.spacecraft[0]
    service = SimulationService(scenario)
    record = service.nominal_provenance()
    gains = default_mrp_gains_for_inertia(solar_arrays.fsw_inertia_kg_m2(sc))  # the inertia the engine scales by
    applied = record.effective_defaults[f"spacecraft[{sc.name}].control_params"]
    assert (applied["K"], applied["P"]) == pytest.approx((gains["K"], gains["P"]))
    css = next(s for s in sc.sensors if s.kind == "coarse_sun_sensor" and "fov_deg" not in s.params)
    assert record.effective_defaults[f"spacecraft[{sc.name}].sensors[{css.name}].params"]["fov_deg"] == 90.0
    wheels = [a for a in sc.actuators if a.kind == "reaction_wheel"]
    assert {f"spacecraft[{sc.name}].actuators[{a.name}]" for a in wheels} == set(record.device_parameters)
    effector = next(m for task in service.scSim.TaskList for m in task.TaskModels
                    if getattr(m, "ModelTag", "") == f"{sc.name}_reactionWheels")
    assert record.device_parameters[f"spacecraft[{sc.name}].actuators[{wheels[0].name}]"]["Js"] == \
        pytest.approx(effector.ReactionWheelData[0].Js)
    assert record.effective_config_note
