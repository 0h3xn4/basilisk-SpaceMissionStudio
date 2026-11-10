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
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""The input differences between two runs (UX/UI guidelines, "run
comparison": "a diff of their inputs")."""

from pathlib import Path

from spacemissionstudio.engine.scenario_diff import diff, short
from spacemissionstudio.schema import load_scenario

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"


def test_named_list_items_are_matched_by_name_not_position():
    """List items with names are compared by name, so an inserted spacecraft
    shows as new and only the changed field shows."""
    a = {"spacecraft": [{"name": "sat-1", "mass": 100}, {"name": "sat-2", "mass": 200}]}
    b = {"spacecraft": [{"name": "new", "mass": 50}, {"name": "sat-1", "mass": 100}, {"name": "sat-2", "mass": 210}]}
    assert diff(a, b) == [("spacecraft[sat-2].mass", 200, 210), ("spacecraft[new]", "(none)", {"name": "new",
                                                                                               "mass": 50})]


def test_plain_values_lists_and_missing_keys():
    """Changed values, changed lists and a missing key are each one difference;
    a scenario has none with itself."""
    a = {"gravity": {"degree": 10, "third_body_perturbers": ["sun"]}, "only_a": 1}
    b = {"gravity": {"degree": 20, "third_body_perturbers": ["sun", "moon"]}}
    assert diff(a, b) == [("gravity.degree", 10, 20), ("gravity.third_body_perturbers", ["sun"], ["sun", "moon"]),
                          ("only_a", 1, "(none)")]
    assert diff(a, a) == []


def test_a_real_template_edit_names_the_field():
    """Two edits to template 05 give exactly their two paths; long values are
    shortened to 60 characters."""
    scenario = load_scenario(_TEMPLATES / "05_formation_flying_phasing.json")
    before = scenario.to_dict()
    scenario.spacecraft[1].orbit.semi_major_axis_km += 1.0  # [km]
    scenario.sim_settings.duration_days = 30.0  # [day]
    paths = [path for path, _old, _new in diff(before, scenario.to_dict())]
    assert sorted(paths) == ["sim_settings.duration_days",
                             f"spacecraft[{scenario.spacecraft[1].name}].orbit.semi_major_axis_km"]
    assert short("x" * 100).endswith("...") and len(short("x" * 100)) == 60
