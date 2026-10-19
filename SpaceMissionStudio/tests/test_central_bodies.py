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
"""Every central body the schema offers can be flown: a short Basilisk run
around each, and with each as a third body. "mars" and "jupiter" used to
pass validation and then fail: the bundled DE430 ephemeris has the Mars
and Jupiter system barycentres, not the planets, so a run around "mars"
stopped the whole process with SPICE(SPKINSUFFDATA) (the GUI runs in the
app's own process), and Basilisk has no body named "jupiter". They are
refused now, with the body to use instead."""

from pathlib import Path

import pytest

from spacemissionstudio.schema import GravityConfig, load_scenario
from spacemissionstudio.schema.scenario import SUPPORTED_CENTRAL_BODIES, UNRUNNABLE_BODIES, ScenarioValidationError

_TEMPLATE = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
             / "01_two_body_circular_orbit.json")
_ORBIT_RADII = 3.0  # [-] circular orbit radius in equatorial radii
_DURATION_DAYS = 0.01  # [day]


def _scenario(central_body, third_bodies):
    from spacemissionstudio.engine.constellation import CENTRAL_BODY_EQUATORIAL_RADIUS_KM

    scenario = load_scenario(_TEMPLATE)
    scenario.gravity = GravityConfig(central_body=central_body, third_body_perturbers=third_bodies)
    for sc in scenario.spacecraft:
        sc.enable_drag = False
        sc.orbit.semi_major_axis_km = _ORBIT_RADII * CENTRAL_BODY_EQUATORIAL_RADIUS_KM[central_body]  # [km]
        sc.orbit.eccentricity = 0.0  # [-]
    scenario.sim_settings.duration_days = _DURATION_DAYS
    return scenario


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("central_body", SUPPORTED_CENTRAL_BODIES)
def test_every_offered_central_body_runs(central_body):
    """A run around the body, with the Sun as a third body (except around
    the Sun itself), finishes and records the spacecraft's position."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = _scenario(central_body, [] if central_body == "sun" else ["sun"])
    scenario.validate()
    result = SimulationService(scenario).run()
    assert f"{scenario.spacecraft[0].name}.position_N" in result.series


@pytest.mark.requires_basilisk
def test_every_offered_body_runs_as_a_third_body():
    """A run around Earth with every other offered body as a third body
    finishes."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = _scenario("earth", [b for b in SUPPORTED_CENTRAL_BODIES if b != "earth"])
    scenario.validate()
    SimulationService(scenario).run()


@pytest.mark.parametrize("name", sorted(UNRUNNABLE_BODIES))
def test_a_body_no_run_can_use_is_refused_with_the_one_to_use(name):
    """"mars" and "jupiter", as central or third body, are refused before a
    run, and the message names their barycentre."""
    instead = UNRUNNABLE_BODIES[name][0]
    for gravity in (GravityConfig(central_body=name), GravityConfig(third_body_perturbers=[name])):
        with pytest.raises(ScenarioValidationError, match=f"{name!r} cannot be run: .*use {instead!r}"):
            gravity.validate()
