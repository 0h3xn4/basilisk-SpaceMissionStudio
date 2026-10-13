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

"""Where a validation error or warning is fixed (docs/ux-audit.md U-12):
``gui.problem_location.locate`` on the messages ``Scenario.validate()`` and
``engine.scenario_checks`` really give."""

import copy
from pathlib import Path

import pytest

from spacemissionstudio.gui.problem_location import (GROUND_STATION, PROPAGATION, SCENARIO, SPACECRAFT,
                                                     ProblemLocation, locate)
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import ScenarioValidationError

_TEMPLATE_22 = next((Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates")
                    .glob("22_*.json"))


def _error(edit):
    """The message ``Scenario.validate()`` raises after ``edit`` on template 22."""
    scenario = copy.deepcopy(load_scenario(_TEMPLATE_22))
    edit(scenario)
    with pytest.raises(ScenarioValidationError) as info:
        scenario.validate()
    return str(info.value), scenario


@pytest.mark.parametrize("edit, expected", [
    (lambda s: setattr(s, "epoch_utc", "2030-13-45T99:00:00"), ProblemLocation(SCENARIO, path="epoch_utc")),
    (lambda s: setattr(s, "name", ""), ProblemLocation(SCENARIO, path="name")),
    (lambda s: setattr(s.sim_settings, "duration_days", -1.0),  # [days]
     ProblemLocation(PROPAGATION, path="sim_settings.duration_days")),
    (lambda s: setattr(s.gravity, "central_body_degree", 500), ProblemLocation(PROPAGATION, path="gravity.central_body_degree")),
    (lambda s: setattr(s.spacecraft[0], "dry_mass_kg", -1.0),  # [kg]
     ProblemLocation(SPACECRAFT, "my-sat", "dry_mass_kg")),
    (lambda s: setattr(s.spacecraft[0].orbit, "eccentricity", 1.2),  # [-]
     ProblemLocation(SPACECRAFT, "my-sat", "orbit.eccentricity")),
    (lambda s: setattr(s.ground_stations[0], "latitude_deg", 100.0),  # [deg]
     ProblemLocation(GROUND_STATION, "berlin-gs", "latitude_deg")),
])
def test_validation_errors_are_located(edit, expected):
    """Each kind of validation error is placed in its area, with its field."""
    text, scenario = _error(edit)
    names = [sc.name for sc in scenario.spacecraft]
    stations = [gs.name for gs in scenario.ground_stations]
    assert locate(text, names, stations) == expected


def test_an_orbit_error_names_its_spacecraft():
    """An orbit's own message now says which spacecraft it belongs to."""
    text, _scenario = _error(lambda s: setattr(s.spacecraft[0].orbit, "eccentricity", 1.2))  # [-]
    assert text.startswith("my-sat: orbit: classical_elements orbit needs 0 <= eccentricity < 1")


def test_warnings_without_a_field_name_their_part():
    """Plausibility warnings name no field: their words say which part, and
    a 3D model problem is the model's, even when it lists fields."""
    names = ["sat-1", "sat-10"]
    assert locate("sat-1: perigee at 80 km -- it re-enters within about an orbit", names).path == "orbit"
    assert locate("sat-10: dry_mass_kg, inertia_kg_m2 differ from the 3D model -- open the model", names) == \
        ProblemLocation(SPACECRAFT, "sat-10", "model")
    assert locate("sat-1: something new and unknown", names) == ProblemLocation(SPACECRAFT, "sat-1", "")
    assert locate("spacecraft names must be unique, got ['a', 'a']", names) is None


def test_a_location_describes_itself():
    """The field is the path's first part; the description says where."""
    location = ProblemLocation(SPACECRAFT, "my-sat", "power.bus_idle_power_w")
    assert location.field == "power" and location.describe() == "my-sat, power.bus_idle_power_w"
    assert ProblemLocation(PROPAGATION).describe() == "the propagation setup"


def test_a_mission_sequence_problem_names_its_step():
    """A step's problem leads to the step, by its path, with or without a
    label after it; one about the whole sequence to the sequence."""
    from spacemissionstudio.gui.problem_location import MISSION_SEQUENCE, ProblemLocation, locate

    assert locate("mission_sequence[2].children[0] ('Burn'): maneuver.spacecraft 'x' is not one of ...") == (
        ProblemLocation(MISSION_SEQUENCE, path="mission_sequence[2].children[0]"))
    assert locate("mission_sequence[0]: this report runs before any propagate").path == "mission_sequence[0]"
    assert locate("mission_sequence: its fixed-duration propagates add up to 120.0 days") == (
        ProblemLocation(MISSION_SEQUENCE, path="mission_sequence"))
