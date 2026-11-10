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

"""What the scenario file can hold at each place (``schema/fields.py``,
decisions JE-04 to JE-06): the field help file is what its script writes;
the record at a path; every list of every template holds the record
:data:`LIST_ITEMS` says; the fixed choices are the validation's; the
names a field refers to."""

import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest

from spacemissionstudio.schema import fields, load_scenario
from spacemissionstudio.schema import scenario as schema
from spacemissionstudio.schema.scenario import scenario_text

_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES = sorted((_ROOT / "spacemissionstudio" / "scenarios" / "templates").glob("*.json"))


def _builder():
    spec = importlib.util.spec_from_file_location("build_field_help", _ROOT / "scripts" / "build_field_help.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_help_file_is_what_its_script_writes():
    """``field_help.json`` is regenerated whenever a record's comments
    change (python scripts/build_field_help.py)."""
    assert fields.HELP_FILE.read_text(encoding="utf-8") == _builder().text()


def test_a_comment_runs_on_in_lower_case_and_stops_at_a_new_sentence():
    """``epoch_utc``'s end-of-line comment goes on over two lower-case
    lines; ``simulation_mode`` takes the block that starts with a capital."""
    help_ = json.loads(fields.HELP_FILE.read_text(encoding="utf-8"))["Scenario"]
    assert help_["epoch_utc"].startswith("ISO 8601") and help_["epoch_utc"].endswith("out of sync with epoch_utc.")
    assert help_["simulation_mode"].startswith("Chosen up front")
    assert json.loads(fields.HELP_FILE.read_text(encoding="utf-8"))["MountConfig"]["boresight"].startswith("[-]")


def test_the_record_at_a_path():
    assert fields.record_at(()) is schema.Scenario
    assert fields.record_at(("spacecraft", 0)) is schema.SpacecraftConfig
    assert fields.record_at(("spacecraft", 2, "sensors", 0, "mount")) is schema.MountConfig
    assert fields.record_at(("spacecraft", 0, "model", "equipment", 1, "mount")) is schema.MountConfig
    assert fields.record_at(("spacecraft", 0, "power")) is schema.PowerConfig  # an optional record
    assert fields.record_at(("monte_carlo", "dispersions", 0)) is schema.DispersionConfig
    assert fields.record_at(("spacecraft",)) is None  # the list, not an item
    assert fields.record_at(("spacecraft", 0, "sensors", 0, "params")) is None  # free keys
    assert fields.record_at(("mission_sequence", 0)) is fields.record("Command")  # a mission step
    assert fields.record_at(("mission_sequence", 0, "children", 2)) is fields.record("Command")
    assert fields.record_at(("mission_sequence", 0, "params")) is None  # free keys: they depend on its kind
    assert fields.record_at(("nope",)) is None and fields.record_at(("spacecraft", "x")) is None


def test_every_list_field_with_records_is_listed():
    """Each list field of a record whose comment or name says it holds
    records is in LIST_ITEMS, and each LIST_ITEMS entry names real fields
    and records."""
    for (owner, name), item in fields.LIST_ITEMS.items():
        cls = fields.record(owner)
        assert cls is not None and name in {f.name for f in dataclasses.fields(cls)}, (owner, name)
        assert fields.record(item) is not None, item
    help_ = json.loads(fields.HELP_FILE.read_text(encoding="utf-8"))
    for owner, comments in help_.items():
        for name, text in comments.items():
            if text.startswith("list[") and text[5:].split("]")[0].endswith(("Config", "Record", "Mark")):
                assert (owner, name) in fields.LIST_ITEMS, (owner, name, text)


@pytest.mark.parametrize("path", _TEMPLATES, ids=lambda p: p.stem)
def test_every_object_of_every_template_fits_its_record(path):
    """In each template's saved text, every object at a path with a record
    has only that record's fields."""
    data = json.loads(scenario_text(load_scenario(path)))
    checked = 0

    def walk(value, where):
        nonlocal checked
        if isinstance(value, dict):
            cls = fields.record_at(where)
            if cls is not None:
                names = {f.name for f in fields.fields(cls)}
                assert set(value) <= names, (where, set(value) - names)
                checked += 1
            for key, item in value.items():
                walk(item, where + (key,))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, where + (i,))

    walk(data, ())
    assert checked >= 5


def test_the_choices_are_the_validation_s():
    """Each fixed choice is a constant of the schema; a template's value of
    such a field is one of its choices."""
    for (owner, name), constant in fields.CHOICES.items():
        assert isinstance(fields.constant(constant), (tuple, list, dict)) and fields.constant(constant), constant
        info = fields.field(fields.record(owner), name)
        assert info is not None and info.choices, (owner, name)
    sensor = fields.field(schema.SensorConfig, "kind")
    assert sensor.choices == schema.SUPPORTED_SENSOR_KINDS and sensor.required
    for path in _TEMPLATES:
        scenario = load_scenario(path)
        assert scenario.simulation_mode in fields.field(schema.Scenario, "simulation_mode").choices
        for sc in scenario.spacecraft:
            assert sc.orbit.type in fields.field(schema.OrbitIC, "type").choices


def test_a_field_is_described_with_its_type_default_choices_and_help():
    info = fields.field(schema.Scenario, "simulation_mode")
    assert (info.kind, info.default, info.required) == ("string", '"full_attitude"', False)
    text = info.describe()
    assert text.startswith('simulation_mode: string, default "full_attitude"')
    assert "One of: full_attitude, orbit_only" in text and "Chosen up front" in text
    mount = fields.field(schema.SensorConfig, "mount")
    assert (mount.kind, mount.record, fields.empty_value(mount)) == ("object", "MountConfig", "{}")
    part = fields.field(schema.MountConfig, "part")
    assert part.refers == "part" and "The name of a part of this scenario" in part.describe()
    assert fields.empty_value(fields.field(schema.SpacecraftConfig, "dry_mass_kg")) == "100.0"
    assert fields.empty_value(fields.field(schema.SensorConfig, "name")) == '""'
    assert "configuration" not in {f.name for f in fields.fields(schema.Scenario)}


def test_the_names_a_field_refers_to():
    data = {"spacecraft": [{"name": "a", "model": {"parts": [{"name": "bus"}, {"name": "wing"}],
                                                     "materials": [{"name": "Al"}]}}, {"name": "b"}],
            "ground_stations": [{"name": "Kiruna"}, {"bad": 1}]}
    assert fields.names(data, "spacecraft") == ["a", "b"]
    assert fields.names(data, "ground_station") == ["Kiruna"]
    assert fields.names(data, "part", ("spacecraft", 0, "sensors", 0, "mount")) == ["bus", "wing"]
    assert fields.names(data, "material", ("spacecraft", 0, "model", "parts", 1)) == ["Al"]
    assert fields.names(data, "part", ("spacecraft", 1, "sensors", 0)) == []
    assert fields.names(None, "spacecraft") == [] and fields.names(data, "part") == []


def test_the_step_params_are_those_the_validation_reads():
    """Each mission step kind's params in COMMAND_PARAMS are exactly the
    names its validation method reads from ``self.params``; every kind
    has an entry."""
    import inspect
    import re

    from spacemissionstudio.schema import command

    methods = {"propagate": "_validate_propagate", "maneuver": "_validate_maneuver",
               "lambert_transfer": "_validate_lambert_transfer", "assignment": "_validate_assignment",
               "report": "_validate_report", "if": "_validate_conditional", "while": "_validate_conditional",
               "script_block": "_validate_script_block"}
    assert set(fields.COMMAND_PARAMS) == set(command.SUPPORTED_COMMAND_KINDS) == set(methods)
    for kind, method in methods.items():
        source = inspect.getsource(getattr(command.Command, method))
        read = set(re.findall(r'self\.params\.get\("(\w+)"', source)) | set(re.findall(r'"(\w+)" in self\.params',
                                                                                        source))
        assert {f.name for f in fields.command_params(kind)} == read, kind
    assert fields.command_params("nope") is None
    frame = next(f for f in fields.command_params("maneuver") if f.name == "frame")
    assert frame.choices == command.SUPPORTED_MANEUVER_FRAMES and frame.describe().startswith(
        'frame: string, default "inertial"')
    days = next(f for f in fields.command_params("propagate") if f.name == "duration_days")
    assert days.describe().startswith("duration_days: number, optional") and "[day]" in days.describe()
