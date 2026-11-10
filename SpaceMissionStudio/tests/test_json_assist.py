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

"""Completion and help on the JSON page (``gui/json_assist.py`` and
``json_positions.context_at``, decisions JE-04 to JE-06): what is being
typed at a place, the keys a record still lacks with their defaults, a
field's choices, the names it refers to, booleans, the description of a
key."""

import json

from spacemissionstudio.gui import json_assist
from spacemissionstudio.gui.json_positions import context_at, key_at

_SAT = '{"ground_stations": [{"name": "Kiruna"}], "spacecraft": [{"name": "a", '


def _offer(text, data=None, position=None):
    start, end, items = json_assist.completions(text, len(text) if position is None else position, data)
    return start, end, [item.label for item in items], items


def test_the_context_of_a_place():
    """A key being typed (its quotes replaced), a key to start, a value
    being typed, a list item, the inside of a number (nothing), the keys
    the object has before and after."""
    text = _SAT + '"orb'
    context = context_at(text, len(text))
    assert (context.kind, context.path, context.prefix) == ("key", ("spacecraft", 0), "orb")
    assert (context.start, context.end, context.keys) == (len(_SAT), len(text), ("name",))
    closed = _SAT + '"orb", "dry_mass_kg": 1}]}'
    context = context_at(closed, len(_SAT) + 3)
    assert context.end == len(_SAT) + 5 and context.keys == ("name", "dry_mass_kg")  # the closing quote too
    context = context_at(_SAT, len(_SAT))
    assert (context.kind, context.prefix, context.start == context.end) == ("key", "", True)
    value = _SAT + '"sensors": [{"kind": "st'
    context = context_at(value, len(value))
    assert (context.kind, context.path, context.prefix) == ("value", ("spacecraft", 0, "sensors", 0, "kind"), "st")
    assert context_at(_SAT + '"dry_mass_kg": 12', len(_SAT) + 17) is None
    listed = '{"a": [1, 2, '
    assert context_at(listed, len(listed)).path == ("a", 2)
    assert context_at("", 0) is None


def test_a_key_offers_the_record_s_missing_fields_with_their_defaults():
    """A spacecraft's object offers its fields but "name"; one inserted
    puts its default, selected to type over."""
    start, end, labels, items = _offer(_SAT + '"dry')
    assert labels == ["dry_mass_kg"] and (start, end) == (len(_SAT), len(_SAT) + 4)
    insert = items[0].insert
    assert insert == '"dry_mass_kg": 100.0' and insert[slice(*items[0].select)] == "100.0"
    _s, _e, labels, _items = _offer(_SAT)
    assert "name" not in labels and labels[:3] == ["orbit", "dry_mass_kg", "inertia_kg_m2"]
    _s, _e, labels, _items = _offer(_SAT + '"area')  # starts-with first, then contains
    assert labels == ["drag_area_m2", "srp_area_m2"]
    _s, _e, labels, items = _offer(_SAT + '"sensors": [{"kind": "imu", "mo')
    assert labels == ["mount"] and items[0].insert == '"mount": {}'
    assert _offer('{"spacecraft": [{"sensors": [{"params": {"')[2] == []  # free keys: nothing offered


def test_a_value_offers_its_choices_names_or_booleans():
    _s, _e, labels, items = _offer(_SAT + '"sensors": [{"kind": "')
    assert labels == ["star_tracker", "imu", "coarse_sun_sensor", "magnetometer", "thermal"]
    assert items[1].insert == '"imu"'
    data = {"ground_stations": [{"name": "Kiruna"}, {"name": "Svalbard"}]}
    text = _SAT + '"comms_pointing": {"target_ground_station": "s'
    _s, _e, labels, _items = _offer(text, data)
    assert labels == ["Svalbard"]
    assert _offer(_SAT + '"enable_drag": ')[2] == ["true", "false"]
    assert _offer(_SAT + '"dry_mass_kg": ')[2] == []  # a number: nothing to offer
    assert _offer('{"simulation_mode": "o')[2] == ["orbit_only"]


def test_the_help_of_a_key():
    text = json.dumps({"simulation_mode": "orbit_only", "spacecraft": [{"dry_mass_kg": 5.0}]})
    assert json_assist.help_at(text, 3).startswith("simulation_mode: string, default")
    position = text.index("dry_mass_kg") + 2
    assert key_at(text, position) == (("spacecraft", 0), "dry_mass_kg")
    assert "[kg]" in json_assist.help_at(text, position)
    assert json_assist.help_at(text, text.index("orbit_only")) == ""  # a value, not a key
    assert json_assist.help_at('{"nope": 1}', 3) == ""


def test_a_device_s_params_offer_its_kind_s_parameters():
    """A reaction wheel's params offer the wheel's parameters (as its form
    does), its rw_type the wheel models; a star tracker's, its own; a
    device whose kind is not read yet offers nothing."""
    from spacemissionstudio.schema.scenario import RW_TYPES

    wheel = _SAT + '"actuators": [{"kind": "reaction_wheel", "name": "w", "params": {"'
    _s, _e, labels, items = _offer(wheel)
    assert labels[:3] == ["gsHat_B", "rw_type", "Omega_max"] and "u_max" in labels
    assert items[0].insert.startswith('"gsHat_B": [') and items[0].select is not None
    assert _offer(wheel + 'rw_type": "')[2] == list(RW_TYPES)
    tracker = _SAT + '"sensors": [{"kind": "star_tracker", "name": "st", "params": {"'
    assert _offer(tracker)[2] == ["noise_arcsec", "bias_walk_bound_arcsec"]
    assert _offer(_SAT + '"sensors": [{"name": "st", "params": {"')[2] == []  # no kind yet
    text = json.dumps({"spacecraft": [{"name": "a", "sensors": [{"kind": "imu", "name": "g",
                                                                  "params": {"gyro_noise_rad_s": 1e-5}}]}]})
    assert "[rad/s]" in json_assist.help_at(text, text.index("gyro_noise") + 2)


def test_a_mission_step_offers_its_fields_and_its_kind_s_params():
    """A step's own fields, its kinds, the params of a maneuver with their
    frame choices and the spacecraft names, and their help."""
    _s, _e, labels, _items = _offer('{"mission_sequence": [{"')
    assert labels == ["kind", "label", "params", "children", "enabled"]
    assert _offer('{"mission_sequence": [{"kind": "lam')[2] == ["lambert_transfer"]
    step = '{"mission_sequence": [{"kind": "maneuver", "params": {"'
    _s, _e, labels, items = _offer(step)
    assert labels == ["spacecraft", "delta_v_m_s", "frame"] and items[1].insert == '"delta_v_m_s": [0.0, 0.0, 0.0]'
    assert _offer(step + 'frame": "')[2] == ["inertial", "vnb", "rtn"]
    assert _offer(step + 'spacecraft": "', {"spacecraft": [{"name": "sat-1"}]})[2] == ["sat-1"]
    nested = '{"mission_sequence": [{"kind": "if", "children": [{"kind": "propagate", "params": {"st'
    assert _offer(nested)[2] == ["stop_condition", "stop_epoch_utc", "ground_station"]  # starts, then contains
    text = json.dumps({"mission_sequence": [{"kind": "propagate", "params": {"duration_days": 1.0}}]})
    assert json_assist.help_at(text, text.index("duration_days") + 2).startswith("duration_days: number, optional")
