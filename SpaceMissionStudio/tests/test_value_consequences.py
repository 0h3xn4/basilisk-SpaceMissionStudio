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
"""What an override changes (engine.value_consequences, the transparency
plan's Phase 5b): an Earth orbit's inclination, RAAN for an LTAN and
semi-major axis get their physics; any other value its difference."""

from pathlib import Path

import pytest

from spacemissionstudio.engine import orbit_design
from spacemissionstudio.engine.value_consequences import consequences
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import ValueMark, value_mark_records

_TEMPLATES = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
_ORBIT = "spacecraft[leo-comms-1].orbit."


def _scenario():
    return load_scenario(next(_TEMPLATES.glob("19_*.json")))  # leo-comms-1, Sun-synchronous, J2


def test_the_node_rate_at_the_sun_synchronous_inclination_is_the_suns():
    """The rate formula and the inclination it was solved for agree: the
    node keeps pace with the Sun, to the 0.01 deg the inclination is
    rounded to (about 7e-4 deg/day at 97 deg)."""
    a, e = 7078.137, 0.001  # [km], [-]
    rate = orbit_design.nodal_rate_deg_per_day(a, e, orbit_design.sun_synchronous_inclination_deg(a, e))
    assert rate == pytest.approx(orbit_design.SUN_MEAN_MOTION_DEG_PER_DAY, abs=1e-3)  # [deg/day]


def test_an_overridden_sun_synchronous_inclination_says_it_no_longer_is():
    scenario = _scenario()
    orbit = scenario.spacecraft[0].orbit
    computed = orbit_design.sun_synchronous_inclination_deg(orbit.semi_major_axis_km, orbit.eccentricity)
    orbit.inclination_deg = computed + 1.0  # [deg]
    mark = ValueMark(_ORBIT + "inclination_deg", "overridden", computed, "Sun-synchronous inclination at ...",
                     reason="the launcher's orbit")
    drift, sun = consequences(scenario, mark)
    used_rate = orbit_design.nodal_rate_deg_per_day(orbit.semi_major_axis_km, orbit.eccentricity, computed + 1.0)
    assert drift.startswith(f"The node drifts {used_rate:+.4f} deg/day under J2")
    off = used_rate - orbit_design.SUN_MEAN_MOTION_DEG_PER_DAY
    assert sun.startswith(f"Not Sun-synchronous: the node moves {off:+.4f} deg/day against the Sun")
    assert f"{off * 4.0:+.2f} min/day" in sun and off > 0.0  # more inclined: the node turns faster east
    orbit.inclination_deg = computed
    assert consequences(scenario, mark) == []  # the value computed: nothing changes


def test_a_raan_for_an_ltan_moves_the_local_time():
    scenario = _scenario()
    orbit = scenario.spacecraft[0].orbit
    mark = ValueMark(_ORBIT + "raan_deg", "computed", orbit.raan_deg, "RAAN for an LTAN of 10.5 h at ...")
    orbit.raan_deg = (orbit.raan_deg + 15.0) % 360.0  # [deg] one hour later
    assert consequences(scenario, mark) == ["The ascending node's local time moves +60 min from the one chosen "
                                            "(15 deg of RAAN per hour)"]


def test_a_semi_major_axis_changes_the_period():
    scenario = _scenario()
    orbit = scenario.spacecraft[0].orbit
    mark = ValueMark(_ORBIT + "semi_major_axis_km", "computed", orbit.semi_major_axis_km, "Walker ...")
    orbit.semi_major_axis_km += 10.0  # [km]
    (line,) = consequences(scenario, mark)
    change = orbit_design.orbital_period_s(mark.value + 10.0) - orbit_design.orbital_period_s(mark.value)
    assert line == f"The period changes by {change:+.1f} s (+10 km from the value computed)" and change > 0.0


def test_any_other_value_gets_its_difference_with_its_unit():
    scenario = _scenario()
    station = scenario.ground_stations[0]
    mark = ValueMark("ground_stations[berlin-gs].min_elevation_deg", "computed", station.min_elevation_deg, "x")
    station.min_elevation_deg += 5.0  # [deg]
    assert consequences(scenario, mark) == ["+5 deg from the value computed"]
    assert consequences(scenario, ValueMark("spacecraft[nobody].orbit.raan_deg", "computed", 1.0, "x")) == []


def test_the_provenance_records_what_each_override_changes():
    scenario = _scenario()
    orbit = scenario.spacecraft[0].orbit
    mark = ValueMark(_ORBIT + "inclination_deg", "computed", orbit.inclination_deg, "Sun-synchronous ...")
    scenario.value_marks = [mark]
    assert value_mark_records(scenario)[0]["consequences"] == []
    orbit.inclination_deg += 0.5  # [deg]
    (record,) = value_mark_records(scenario)
    assert record["status"] == "edited" and record["consequences"] == consequences(scenario, mark)
    assert record["consequences"][1].startswith("Not Sun-synchronous")


def test_a_small_edit_is_still_sun_synchronous_by_explains_rule():
    """Within explain.sso_tolerance_deg Explain still labels the orbit SSO,
    and the note says so, with the drift it has."""
    from spacemissionstudio.config.registry import Configuration

    scenario = _scenario()
    orbit = scenario.spacecraft[0].orbit
    computed = orbit_design.sun_synchronous_inclination_deg(orbit.semi_major_axis_km, orbit.eccentricity)
    orbit.inclination_deg = computed + 0.05  # [deg]
    mark = ValueMark(_ORBIT + "inclination_deg", "computed", computed, "Sun-synchronous inclination at ...")
    assert consequences(scenario, mark)[1].startswith("Still Sun-synchronous to Explain's 0.1 deg")
    scenario.configuration = Configuration({"explain.sso_tolerance_deg": 0.01})
    assert consequences(scenario, mark)[1].startswith("Not Sun-synchronous")


def test_explain_lists_the_values_used_in_place_of_computed_ones():
    """Scenario > Overview gets a section counting the marks; a note per
    value used in place of the one computed, with its reason and what it
    changes; none for a value still as computed, and no section without
    marks."""
    from spacemissionstudio.engine.scenario_explainer import explain

    scenario = _scenario()
    assert all(s.title != "Computed and overridden values" for s in explain(scenario).sections)
    orbit = scenario.spacecraft[0].orbit
    computed = orbit.inclination_deg
    scenario.value_marks = [
        ValueMark(_ORBIT + "inclination_deg", "overridden", computed, "Sun-synchronous inclination at ...",
                  reason="the launcher's orbit"),
        ValueMark(_ORBIT + "raan_deg", "computed", orbit.raan_deg, "RAAN for an LTAN of 10.5 h at ..."),
    ]
    orbit.inclination_deg = computed + 1.0  # [deg]
    (section,) = [s for s in explain(scenario).sections if s.title == "Computed and overridden values"]
    assert [b.label for b in section.badges] == ["1 computed", "1 overridden"]
    (note,) = section.notes
    assert note.startswith(f"{_ORBIT}inclination_deg: overridden, {computed + 1.0:g} in place of {computed:g} "
                           "(the launcher's orbit). The node drifts")
    assert "Not Sun-synchronous" in note
