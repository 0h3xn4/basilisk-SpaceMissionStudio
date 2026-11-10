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

"""What the scenario file can hold at each place, for the JSON page's
completion and hover help (decisions JE-04 to JE-06 of
``docs/developer/json-editor.md``).

:func:`record_at` follows a path of the scenario's JSON (keys and list
indices, as ``json.loads`` gives them) from :class:`Scenario` through the
record classes of ``schema/scenario.py``: a field whose type is a record,
or an optional one, and a list whose items are records
(:data:`LIST_ITEMS`; the type hints say only ``list``). It gives None
where the file holds free keys (a device's ``params``, ``fsw_params``,
a mission step's ``params``) or a value. A mission step is a
``schema.command.Command``; what its ``params`` hold depends on its
``kind`` (:func:`command_params`, the table :data:`COMMAND_PARAMS`).

:func:`fields` describes a record's fields (:class:`FieldInfo`): the JSON
type, the default, whether it is required, the source's comment on it
(``field_help.json``, written by ``scripts/build_field_help.py``), its
fixed choices (:data:`CHOICES`, the constants the validation checks it
against) and what kind of name it refers to (:data:`REFERENCES`).
"""

from __future__ import annotations

import dataclasses
import json
import typing
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import NoneType, UnionType

from . import command as _command
from . import scenario as _scenario

HELP_FILE = Path(__file__).with_name("field_help.json")

#: The record class of a list field's items, by (record class, field).
LIST_ITEMS = {
    ("Scenario", "spacecraft"): "SpacecraftConfig",
    ("Scenario", "ground_stations"): "GroundStationConfig",
    ("Scenario", "fsw_exports"): "FswExportRecord",
    ("Scenario", "value_marks"): "ValueMark",
    ("Scenario", "presets"): "PresetRecord",
    ("Scenario", "imports"): "ImportRecord",
    ("MonteCarloConfig", "dispersions"): "DispersionConfig",
    ("SpacecraftConfig", "sensors"): "SensorConfig",
    ("SpacecraftConfig", "actuators"): "ActuatorConfig",
    ("SpacecraftConfig", "facets"): "FacetConfig",
    ("SpacecraftConfig", "solar_arrays"): "SolarArrayConfig",
    ("SpacecraftModelConfig", "parts"): "ModelPartConfig",
    ("SpacecraftModelConfig", "meshes"): "ModelMeshConfig",
    ("SpacecraftModelConfig", "equipment"): "MountedEquipmentConfig",
    ("SpacecraftModelConfig", "stowed"): "PartPoseConfig",
    ("SpacecraftModelConfig", "face_properties"): "FacePropertyConfig",
    ("SpacecraftModelConfig", "materials"): "MaterialConfig",
    ("ModelAnalysesConfig", "observers"): "ObserverSiteConfig",
    ("DataHandlingConfig", "instruments"): "InstrumentConfig",
    ("RoeFormationConfig", "targets"): "RoeTargetConfig",
    ("Scenario", "mission_sequence"): "Command",
    ("Command", "children"): "Command",
}
#: A field's fixed choices: the constant of ``schema/scenario.py`` the validation checks it against.
CHOICES = {
    ("Scenario", "simulation_mode"): "SUPPORTED_SIMULATION_MODES",
    ("SimSettings", "integrator"): "SUPPORTED_INTEGRATORS",
    ("SpaceWeatherConfig", "source"): "SUPPORTED_SPACE_WEATHER_SOURCES",
    ("SpaceWeatherConfig", "atmosphere_model"): "ATMOSPHERE_MODELS",
    ("SpaceWeatherConfig", "atmosphere_table"): "ATMOSPHERE_TABLES",
    ("GravityConfig", "central_body"): "SUPPORTED_CENTRAL_BODIES",
    ("OrbitIC", "type"): "ORBIT_IC_TYPES",
    ("OrbitIC", "anomaly_type"): "ANOMALY_TYPES",
    ("SensorConfig", "kind"): "SUPPORTED_SENSOR_KINDS",
    ("ActuatorConfig", "kind"): "SUPPORTED_ACTUATOR_KINDS",
    ("SpacecraftConfig", "fsw_mode"): "SUPPORTED_FSW_MODES",
    ("RFLinkConfig", "antenna_pattern"): "SUPPORTED_ANTENNA_PATTERNS",
    ("ConstantThrustConfig", "frame"): "SUPPORTED_THRUST_FRAMES",
    ("PhasingKeepingConfig", "control_law"): "PHASING_CONTROL_LAWS",
    ("RoeFormationConfig", "control_law"): "ROE_CONTROL_LAWS",
    ("PropellantBudgetConfig", "disposal"): "SUPPORTED_DISPOSALS",
    ("ModelPartConfig", "shape"): "MODEL_SHAPES",
    ("ModelPartConfig", "distribution"): "MODEL_DISTRIBUTIONS",
    ("SpacecraftModelConfig", "mass_properties_source"): "MASS_PROPERTIES_SOURCES",
    ("ModelMeshConfig", "units"): "MESH_UNITS",
    ("ModelMeshConfig", "up_axis"): "MESH_UP_AXES",
    ("MountedEquipmentConfig", "kind"): "EQUIPMENT_KINDS",
    ("LauncherConfig", "shape"): "LAUNCHER_SHAPES",
    ("DispersionConfig", "quantity"): "DISPERSION_QUANTITIES",
    ("ValueMark", "state"): "VALUE_MARK_STATES",
    ("ImportRecord", "target"): "IMPORT_TARGETS",
    ("ImportRecord", "format"): "IMPORT_FORMATS",
    ("Command", "kind"): "SUPPORTED_COMMAND_KINDS",
}
#: What kind of name a field refers to: "spacecraft", "ground_station", "part" or "material".
REFERENCES = {
    ("CommsPointingConfig", "target_ground_station"): "ground_station",
    ("PhasingKeepingConfig", "chief_spacecraft"): "spacecraft",
    ("RoeFormationConfig", "chief_spacecraft"): "spacecraft",
    ("DispersionConfig", "spacecraft"): "spacecraft",
    ("MountConfig", "part"): "part",
    ("PartPoseConfig", "part"): "part",
    ("FacePropertyConfig", "part"): "part",
    ("FacePropertyConfig", "material"): "material",
    ("ModelPartConfig", "material"): "material",
}


def record(name: str) -> type | None:
    """The record class ``name`` of ``schema/scenario.py`` (or
    ``schema/command.py``'s ``Command``), or None."""
    cls = getattr(_scenario, name, None) or getattr(_command, name, None)
    return cls if isinstance(cls, type) and dataclasses.is_dataclass(cls) else None


def constant(name: str):
    """The constant ``name`` of ``schema/scenario.py`` or ``schema/command.py``."""
    return getattr(_scenario, name, None) or getattr(_command, name, ())


@cache
def _hints(cls) -> dict:
    return typing.get_type_hints(cls)


def _record_type(hint) -> type | None:
    """The record class a field's type hint names, an optional one included."""
    if isinstance(hint, UnionType) or typing.get_origin(hint) is typing.Union:
        options = [arg for arg in typing.get_args(hint) if arg is not NoneType]
        hint = options[0] if len(options) == 1 else None
    return hint if isinstance(hint, type) and dataclasses.is_dataclass(hint) else None


def field_record(cls, name: str) -> type | None:
    """The record class of field ``name`` of ``cls`` (its own record, or its
    list items' record), or None."""
    item = LIST_ITEMS.get((cls.__name__, name))
    if item is not None:
        return record(item)
    hint = _hints(cls).get(name)
    return _record_type(hint) if hint is not None else None


def record_at(path) -> type | None:
    """The record class of the object at ``path`` (module docstring)."""
    cls = _scenario.Scenario
    i = 0
    path = tuple(path)
    while i < len(path):
        key = path[i]
        if not isinstance(key, str) or key not in {f.name for f in dataclasses.fields(cls)}:
            return None
        listed = (cls.__name__, key) in LIST_ITEMS
        cls = field_record(cls, key)
        if cls is None:
            return None
        i += 1
        if listed:
            if i >= len(path) or not isinstance(path[i], int):
                return None  # the list itself, not an item
            i += 1
    return cls


@dataclass(frozen=True)
class FieldInfo:
    """One field of a record: its ``name``, its JSON ``kind`` ("string",
    "number", "boolean", "array", "object", "any"), its ``default`` as JSON
    text ("" when required), the source's ``help``, its ``choices`` and the
    kind of name it ``refers`` to ("" for none)."""

    name: str
    kind: str
    default: str
    required: bool
    help: str
    choices: tuple = ()
    refers: str = ""
    record: str = ""  # the record class it holds, or its list items hold

    def describe(self) -> str:
        """The field in words, for a tooltip."""
        parts = [f"{self.name}: {self.kind}" + (f" of {self.record}" if self.record else "")]
        parts.append("required" if self.required else f"default {self.default}" if self.default else "optional")
        text = ", ".join(parts)
        if self.choices:
            text += "\nOne of: " + ", ".join(self.choices)
        if self.refers:
            text += f"\nThe name of a {self.refers.replace('_', ' ')} of this scenario"
        if self.help:
            text += "\n" + self.help
        return text


@cache
def _help() -> dict:
    try:
        return json.loads(HELP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _kind(hint) -> str:
    if isinstance(hint, UnionType) or typing.get_origin(hint) is typing.Union:
        options = [arg for arg in typing.get_args(hint) if arg is not NoneType]
        hint = options[0] if len(options) == 1 else object
    origin = typing.get_origin(hint) or hint
    if origin is bool:
        return "boolean"
    if origin in (int, float):
        return "number"
    if origin is str:
        return "string"
    if origin in (list, tuple):
        return "array"
    if origin is dict or (isinstance(origin, type) and dataclasses.is_dataclass(origin)):
        return "object"
    return "any"


def _default(f: dataclasses.Field) -> str:
    if f.default is not dataclasses.MISSING:
        value = f.default
    elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
        value = f.default_factory()  # type: ignore[misc]
    else:
        return ""
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return ""


@cache
def fields(cls) -> tuple[FieldInfo, ...]:
    """The fields of record ``cls`` a scenario file holds, in order."""
    helps = _help().get(cls.__name__, {})
    found = []
    for f in dataclasses.fields(cls):
        if not f.init or f.name == "configuration":  # read from config_file, never written in a scenario
            continue
        hint = _hints(cls).get(f.name, object)
        constant = CHOICES.get((cls.__name__, f.name))
        choices = globals()["constant"](constant) if constant else ()
        held = field_record(cls, f.name)
        default = _default(f)
        found.append(FieldInfo(f.name, _kind(hint), default, default == "", helps.get(f.name, ""),
                               tuple(str(c) for c in choices), REFERENCES.get((cls.__name__, f.name), ""),
                               held.__name__ if held is not None else ""))
    return tuple(found)


def field(cls, name: str) -> FieldInfo | None:
    return next((f for f in fields(cls) if f.name == name), None)


def empty_value(info: FieldInfo) -> str:
    """The JSON text to put after a new key: its default, else an empty
    value of its kind."""
    if info.default and info.default != "null":
        return info.default
    return {"string": '""', "number": "0", "boolean": "false", "array": "[]", "object": "{}"}.get(
        info.kind, "null" if info.default == "null" else '""')


def names(data, refers: str, path=()) -> list[str]:
    """The names of kind ``refers`` that ``data`` (the scenario's JSON)
    holds; for a part or a material, those of the spacecraft ``path``
    is in (its 3D model's parts, its model's materials)."""
    if not isinstance(data, dict):
        return []

    def named(items) -> list[str]:
        return [item["name"] for item in items or [] if isinstance(item, dict) and isinstance(item.get("name"), str)]

    if refers == "spacecraft":
        return named(data.get("spacecraft"))
    if refers == "ground_station":
        return named(data.get("ground_stations"))
    if refers in ("part", "material") and len(path) >= 2 and path[0] == "spacecraft" and isinstance(path[1], int):
        crafts = data.get("spacecraft") or []
        if 0 <= path[1] < len(crafts) and isinstance(crafts[path[1]], dict):
            model = crafts[path[1]].get("model") or {}
            if isinstance(model, dict):
                return named(model.get("parts" if refers == "part" else "materials"))
    return []


def _param(name, kind, default="", help_="", choices=(), refers="", required=False) -> FieldInfo:
    return FieldInfo(name, kind, default, required, help_, tuple(choices), refers)


#: What a mission step's ``params`` hold, by its kind, as ``Command.validate`` reads them
#: (``tests/test_schema_fields.py`` checks the names against it).
COMMAND_PARAMS = {
    "propagate": (
        _param("stop_condition", "string", '"duration"', "What ends the propagation.",
               _command.SUPPORTED_STOP_CONDITIONS),
        _param("duration_days", "number", "", "[day] How long, when stop_condition is \"duration\"."),
        _param("stop_epoch_utc", "string", "", "ISO 8601 UTC, when stop_condition is \"epoch\"."),
        _param("event_kind", "string", "", "The orbital event that ends it, when stop_condition is \"event\".",
               _command.SUPPORTED_EVENT_KINDS),
        _param("spacecraft", "string", "", "The spacecraft the event is evaluated against, when stop_condition "
               "is \"event\".", refers="spacecraft"),
        _param("ground_station", "string", "", "The station whose pass starts or ends it, for pass_start and "
               "pass_end.", refers="ground_station"),
    ),
    "maneuver": (
        _param("spacecraft", "string", "", "The spacecraft that burns.", refers="spacecraft", required=True),
        _param("delta_v_m_s", "array", "[0.0, 0.0, 0.0]", "[m/s] The impulsive burn [x, y, z], in frame.",
               required=True),
        _param("frame", "string", '"inertial"', "The frame of delta_v_m_s.", _command.SUPPORTED_MANEUVER_FRAMES),
    ),
    "lambert_transfer": (
        _param("spacecraft", "string", "", "The spacecraft that transfers.", refers="spacecraft", required=True),
        _param("target_position_m", "array", "[0.0, 0.0, 0.0]", "[m] Where to arrive, inertial, from the central "
               "body.", required=True),
        _param("time_of_flight_s", "number", "", "[s] From this step until arrival; the burn is applied at once.",
               required=True),
        _param("num_revolutions", "number", "0", "[-] Whole revolutions on the way (an integer >= 0)."),
        _param("max_distance_target_m", "number", "1000.0", "[m] The largest miss distance accepted."),
        _param("min_orbit_radius_m", "number", "0.0", "[m] The lowest radius the transfer may dip to (0: no "
               "check)."),
    ),
    "assignment": (
        _param("target", "string", "", "A dotted path, e.g. \"sat-1.station_keeping.thrust_n\".", required=True),
        _param("value", "any", "", "The value to set.", required=True),
    ),
    "report": (
        _param("series", "array", "[]", "The series to record (names); empty: everything."),
    ),
    "if": (_param("condition", "string", "", "An expression; the children run when it is true.", required=True),),
    "while": (_param("condition", "string", "", "An expression; the children run while it is true.",
                     required=True),),
    "script_block": (_param("code", "string", "", "Python code, run only with the user's consent.", required=True),),
}


def command_params(kind) -> tuple[FieldInfo, ...] | None:
    """What a mission step of ``kind`` holds in its ``params``, or None
    for a kind there is not."""
    return COMMAND_PARAMS.get(kind)
