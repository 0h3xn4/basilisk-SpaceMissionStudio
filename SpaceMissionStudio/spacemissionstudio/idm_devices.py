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

"""The sensors and actuators of an IDM-CIC model, found by name
(``docs/developer/idm-cic-integration.md``, section 15).

An IDM-CIC model says what each equipment is called, which subsystem it
belongs to, its mass and where it sits; it says nothing of how it
performs. :func:`detect` reads the names: each placed equipment whose
name (in English or French, accents ignored) names a kind of device the
simulation has, and whose subsystem is not structure, thermal or harness,
is a :class:`DeviceFinding`, with its position and axes in the body frame.
A finding whose name also names a product of
:mod:`engine.device_catalog` (for example "ST200") takes that product's
published values; otherwise the device has none of its own, and the
pre-run checks say it runs with Basilisk's defaults
(``import.device_defaults``) until its values are set. Nothing is
estimated.

Star trackers, IMUs, sun sensors, magnetometers, reaction wheels and
magnetorquers can be added (:data:`ADDABLE_KINDS`), the wheels and
magnetorquers only with a catalog product, since Basilisk builds neither
without values the file does not give (:data:`REQUIRED_VALUES`); thrusters, solar
arrays and batteries are found and listed, not added: a thruster's
direction and thrust and a battery's capacity are not in the file, and
the power model takes one panel area and one battery for the whole
spacecraft (the solar arrays' panels can set that area and its normal:
``idm_import.apply_power``).

A device's axis (a sun sensor's boresight, a wheel's spin axis, a
magnetorquer's dipole axis, a star tracker's boresight for the field of
view checks) is read from its equipment's shapes when they show it
(:func:`model_axis`, decision IDM-30): a cone, which the models draw for
a field of view, gives the boresight from its apex toward its base and
the field of view's full angle; for a wheel or a magnetorquer, its
largest cylinder gives the spin or dipole axis. Otherwise it is the +z
axis of its equipment's frame, the axis of IDM-CIC's revolution shapes
(decision IDM-03). The user can choose any axis of the equipment's frame
instead.
"""

from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np

from .engine import device_catalog
from .idm import frames
from .schema.scenario import (SUPPORTED_ACTUATOR_KINDS, SUPPORTED_SENSOR_KINDS, ActuatorConfig, MountConfig,
                              SensorConfig)

#: The kinds :func:`build_devices` adds to the spacecraft.
ADDABLE_KINDS = ("star_tracker", "imu", "coarse_sun_sensor", "magnetometer", "reaction_wheel",
                 "magnetic_torque_rod")
#: The kinds found and listed only (see the module docstring).
LISTED_KINDS = ("thruster", "solar_array", "battery")
KIND_LABELS = {"star_tracker": "Star tracker", "imu": "Gyro / IMU", "coarse_sun_sensor": "Sun sensor",
               "magnetometer": "Magnetometer", "reaction_wheel": "Reaction wheel",
               "magnetic_torque_rod": "Magnetorquer", "thruster": "Thruster", "solar_array": "Solar array",
               "battery": "Battery"}
#: The parameter that holds a kind's axis (the others carry it in their mount only).
AXIS_PARAMS = {"coarse_sun_sensor": "nHat_B", "reaction_wheel": "gsHat_B", "magnetic_torque_rod": "gtHat_B"}
#: The values a kind cannot run without, which only a catalog product (or the user) gives: Basilisk builds
#: no custom wheel without its torque and inertia, and no magnetorquer without its dipole.
REQUIRED_VALUES = {"reaction_wheel": ("u_max", "Js (or Omega_max and maxMomentum)"),
                   "magnetic_torque_rod": ("max_dipole_a_m2",)}
AXES = ("+x", "-x", "+y", "-y", "+z", "-z")
CANNOT_TAKE = "the spacecraft cannot take it as it is"  # how keep_fitting's reasons start
DEFAULT_AXIS = "+z"  # the axis of IDM-CIC's revolution shapes (IDM-03)
MODEL_AXIS = "model"  # the axis read from the equipment's shapes (model_axis, IDM-30)
#: Kinds whose axis a cylinder gives (a wheel's spin axis, a rod's dipole axis).
CYLINDER_KINDS = ("reaction_wheel", "magnetic_torque_rod")

# What a name says, as phrases of normalized words (see _words): the first
# kind whose phrases match wins, unless one of its exclusions also matches.
_RULES = (
    ("star_tracker", ("star tracker", "startracker", "star sensor", "senseur stellaire", "viseur stellaire",
                      "capteur stellaire"),
     ("elec", "electronic", "electronics", "electronique", "dpu", "baffle", "support", "bracket")),
    ("magnetic_torque_rod", ("magnetorquer", "magneto torquer", "magnetotorquer", "torquer", "torque rod",
                             "torquerod", "mtq", "magnetocoupleur", "magnetocoupleurs", "magneto coupleur"),
     ("support", "bracket")),
    ("magnetometer", ("magnetometer", "magnetometre", "mtm"), ("support", "bracket")),
    ("coarse_sun_sensor", ("sun sensor", "sas", "css", "senseur solaire", "capteur solaire"),
     ("support", "bracket")),
    ("imu", ("gyro", "gyros", "gyroscope", "gyrometer", "gyrometre", "imu", "inertial measurement unit",
             "centrale inertielle"), ("support", "bracket")),
    ("reaction_wheel", ("reaction wheel", "inertia wheel", "momentum wheel", "rw", "roue", "wheel"),
     ("support", "bracket", "drive")),
    ("thruster", ("thruster", "thrusters", "propulseur", "tuyere", "rcs"), ("support", "bracket")),
    ("solar_array", ("solar panel", "solar array", "solar wing", "solar generator", "panneau solaire",
                     "generateur solaire", "aile solaire"),
     ("mechanism", "mechanisms", "mecanisme", "mecanismes", "support", "feet", "sadm", "hinge", "yoke", "drive",
      "harness")),
    ("battery", ("battery", "batterie", "batteries"), ("cone", "support", "bracket", "heater")),
)
# Subsystems whose equipment is not a device (a wheel's support, a battery's thermal cone).
_NOT_DEVICE_SUBSYSTEMS = ("struct", "thermal", "thermique", "harness", "harnais", "mechanical", "mecanique")
# Words a catalog product name may share with a plain description: a product
# matches only on a word that is not one of these.
_GENERIC = {"sun", "sensor", "fine", "thruster", "cold", "gas", "magnetic", "torque", "rod", "micro", "hydrazine",
            "n", "star", "tracker", "cgt"}


def _words(text: str) -> str:
    """``text`` lower-case, accents removed, every run of other characters
    one space, with a space at each end (so a phrase matches whole words)."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return " " + " ".join(re.findall(r"[a-z0-9]+", plain)) + " "


def _has(words: str, phrase: str) -> bool:
    return f" {phrase} " in words


def classify(name: str, subsystem: str = "") -> tuple[str, str]:
    """``(kind, phrase)`` that ``name`` names, or ``("", "")``: the kind of
    :data:`ADDABLE_KINDS` or :data:`LISTED_KINDS` and the phrase that
    matched. A subsystem of structure, thermal control or harness names
    no device."""
    sub = _words(subsystem)
    if any(word in sub for word in _NOT_DEVICE_SUBSYSTEMS):
        return "", ""
    words = _words(name)
    for kind, phrases, exclusions in _RULES:
        phrase = next((p for p in phrases if _has(words, p)), "")
        if phrase:
            if any(_has(words, e) for e in exclusions):
                return "", ""
            return kind, phrase
    return "", ""


def catalog_product(name: str, kind: str) -> device_catalog.DeviceCatalogEntry | None:
    """The catalog product of ``kind`` that ``name`` names (its product
    name as whole words, with at least one word that is not generic), or
    None; the longest product name wins."""
    words = _words(name)
    found = []
    for entry in device_catalog.catalog_entries_for_kind(kind):
        product = _words(entry.product_name).strip()
        if product and _has(words, product) and set(product.split()) - _GENERIC:
            found.append((len(product), entry))
    return max(found, key=lambda item: item[0])[1] if found else None


def product_names(kind: str) -> list[str]:
    """The catalog's products of ``kind``, by display name."""
    return [entry.display_name for entry in device_catalog.catalog_entries_for_kind(kind)]


def product_by_name(kind: str, display_name: str) -> device_catalog.DeviceCatalogEntry | None:
    return next((e for e in device_catalog.catalog_entries_for_kind(kind) if e.display_name == display_name), None)


@dataclass
class DeviceFinding:
    """An equipment of the model that names a device: its placed unit, its
    name and subsystem, the kind and the phrase that named it, its mass,
    its position [m] and axes (columns, body frame), and the catalog
    product its name names ("" for none)."""

    source_id: str
    equipment: str
    subsystem: str
    kind: str
    phrase: str
    mass_kg: float  # [kg]
    position_m: list  # [m] body frame
    axes: list  # 3 x 3, the unit's x, y, z axes as columns, body frame
    product: str = ""  # a catalog display name
    properties: tuple = ()  # idm.properties.PropertyValue of its equipment definition
    model_axis: list | None = None  # body-frame unit vector read from its shapes (model_axis)
    axis_source: str = ""  # which shape gave model_axis
    fov_deg: float | None = None  # [deg] full angle of the field-of-view cone it was read from

    @property
    def addable(self) -> bool:
        return self.kind in ADDABLE_KINDS

    def axis(self, choice: str = DEFAULT_AXIS) -> list:
        """The body-frame unit vector of the axis ``choice``: :data:`MODEL_AXIS`
        (the one read from its shapes, or +z when they show none) or one of
        :data:`AXES` of the unit's frame."""
        if choice == MODEL_AXIS:
            return list(self.model_axis) if self.model_axis is not None else self.axis(DEFAULT_AXIS)
        if choice not in AXES:
            raise ValueError(f"axis {choice!r} must be {MODEL_AXIS!r} or one of {AXES}")
        column = "xyz".index(choice[1])
        vector = np.asarray(self.axes, dtype=float)[:, column] * (1.0 if choice[0] == "+" else -1.0)
        return [_tidy(v) for v in vector / np.linalg.norm(vector)]


@dataclass
class DeviceChoice:
    """What to do with one finding: add it or not, as which kind, along
    which axis, with which catalog product ("" for none)."""

    add: bool
    kind: str
    axis: str = DEFAULT_AXIS
    product: str = ""


@dataclass
class DeviceResult:
    """The devices to add, what their import record keeps, and what was
    not added (with why)."""

    sensors: list = field(default_factory=list)
    actuators: list = field(default_factory=list)
    values: dict = field(default_factory=dict)  # {path: number or text}, as device_import_values
    details: dict = field(default_factory=dict)  # {device path: "product: ..." or "no product: ..."}
    skipped: list = field(default_factory=list)  # (equipment name, why)


def _tidy(value: float) -> float:
    return 0.0 if abs(value) < 1.0e-12 else float(f"{value:.10g}")


def detect(model, placement, body: str, mounted: dict | None = None) -> list[DeviceFinding]:
    """Every placed unit of the elements carried by ``body`` whose name
    names a device (:func:`classify`), in the placement's order."""
    from .idm.properties import equipment_properties
    from .idm_import import _mounted_on, _reaches

    mounted = _mounted_on(model) if mounted is None else mounted
    body_inverse = frames.inverse(placement.element_frames[body])
    found = []
    for unit in placement.units:
        if not _reaches(unit.element, body, mounted):
            continue
        eq = unit.equipment
        kind, phrase = classify(eq.name, unit.subsystem)
        if not kind:
            continue
        pose = body_inverse @ unit.frame
        local = np.append(eq.manual_cog_m, 1.0) if eq.manual else np.array([0.0, 0.0, 0.0, 1.0])
        mass = eq.manual_mass_kg if eq.manual else sum(max(0.0, float(s.mass_kg)) for s in eq.shapes)
        product = catalog_product(eq.name, kind) if kind in ADDABLE_KINDS else None
        found.append(DeviceFinding(unit.full_id, eq.name, unit.subsystem, kind, phrase, _tidy(mass),
                                   [_tidy(v) for v in (pose @ local)[:3]],
                                   [[_tidy(v) for v in row] for row in pose[:3, :3]],
                                   product.display_name if product is not None else "",
                                   tuple(equipment_properties(model, eq.full_id)),
                                   *model_axis(kind, eq, pose)))
    return found


def _cone_axis(geometry, frame):
    """``(boresight, full angle [deg])`` of a cone or truncated cone in
    ``frame`` (its shape's frame in the body frame): from the narrow end
    toward the wide one; None for a cylinder-like or degenerate one."""
    if geometry.kind == "cone":  # the primitive: its base at -z of its centred frame, its apex at +z
        local = frame @ geometry.local
        height = geometry.dims.get("height", 0.0)
        radius = geometry.dims.get("base_diameter", 0.0) / 2.0
        if height <= 0.0 or radius <= 0.0:
            return None
        return -local[:3, 2], 2.0 * np.degrees(np.arctan2(radius, height))
    if geometry.cone is None:
        return None
    r0, r1, h = geometry.cone  # [m] radius at z = 0, radius at z = h, h: as the model gives them
    if h == 0.0 or abs(r1 - r0) <= 1.0e-12 or min(r0, r1) < 0.0:
        return None
    sign = 1.0 if (r1 - r0) * h > 0.0 else -1.0
    return sign * frame[:3, 2], 2.0 * np.degrees(np.arctan2(abs(r1 - r0), abs(h)))


_CONES = ("Cone", "FilledCone", "HollowCone")
_CYLINDERS = ("Cylinder", "FilledCylinder", "HollowCylinder")


def model_axis(kind: str, equipment, pose) -> tuple:
    """``(axis, source, field of view [deg])`` that the equipment's shapes
    give a device of ``kind`` placed at ``pose`` (the unit's frame in the
    body frame), decision IDM-30: its largest cone (a field of view),
    from the apex toward the base, with its full angle; else, for a wheel
    or a magnetorquer, its largest cylinder's axis, along the cylinder's
    own +z; else ``(None, "", None)``. Only for the kinds that are added (a
    thruster's cone is its plume, and thrusters are listed, not added)."""
    if kind not in ADDABLE_KINDS:
        return None, "", None
    cones, cylinders = [], []
    for shape in equipment.shapes:
        geometry = shape.geometry
        frame = pose @ shape.pose
        if geometry.object_type in _CONES:
            found = _cone_axis(geometry, frame)
            if found is not None:
                cones.append((float(geometry.area_m2 or geometry.volume_m3), shape.name, *found))
        elif geometry.object_type in _CYLINDERS and kind in CYLINDER_KINDS:
            cylinders.append((float(geometry.volume_m3 or geometry.area_m2), shape.name, frame[:3, 2]))
    if cones:
        _size, name, vector, angle = max(cones, key=lambda c: c[0])
        source = f"the field-of-view cone {name!r}" if name else "the field-of-view cone"
        return _unit(vector), source, float(f"{angle:.6g}")
    if cylinders:
        _size, name, vector = max(cylinders, key=lambda c: c[0])
        return _unit(vector), (f"the cylinder {name!r}" if name else "its cylinder"), None
    return None, "", None


def _unit(vector) -> list:
    vector = np.asarray(vector, dtype=float)
    return [_tidy(v) for v in vector / np.linalg.norm(vector)]


_LISTED_WHY = {
    "thruster": "listed, not added: its direction and thrust are not in the file; add it to the actuators yourself",
    "solar_array": "listed, not added: the power model takes one panel area for the whole spacecraft; its panels "
                   "can set it (the import's Power choices)",
    "battery": "listed, not added: the power model takes one battery for the whole spacecraft, and the file "
               "has no capacity field; a capacity property, mapped, can set it (the import's Power choices)",
}


def complete(kind: str, params) -> bool:
    """Whether ``params`` (names) hold the values a device of ``kind``
    cannot be built without (:data:`REQUIRED_VALUES`)."""
    names = set(params)
    if kind == "reaction_wheel":
        return "u_max" in names and ("Js" in names or {"Omega_max", "maxMomentum"} <= names)
    if kind == "magnetic_torque_rod":
        return "max_dipole_a_m2" in names
    return True


def finding_values(finding: DeviceFinding, mappings=()) -> tuple[list, list]:
    """The values ``mappings`` (``idm_properties.Mapping``) read from the
    finding's properties, and why a mapped property gave none
    (``idm_properties.mapped_values``)."""
    from .idm_properties import mapped_values

    return mapped_values(finding.kind, finding.properties, mappings) if mappings else ([], [])


def why_not(kind: str, product: str = "", mapped=()) -> str:
    """Why a finding of ``kind`` (with catalog ``product``, and the
    parameters ``mapped`` from its properties) is not added unless chosen:
    "" when it is added by default."""
    if kind in _LISTED_WHY:
        return f"a {KIND_LABELS[kind].lower()} is {_LISTED_WHY[kind]}"
    if kind in REQUIRED_VALUES and not product and not complete(kind, mapped):
        return (f"a {KIND_LABELS[kind].lower()} needs {' and '.join(REQUIRED_VALUES[kind])}, which the file does not "
                "give: choose a catalog product, map the properties that give them, or add it yourself")
    return ""


def default_choices(findings: list[DeviceFinding], mappings=()) -> list[DeviceChoice]:
    """Add each addable finding along the axis its shapes show (+z when
    they show none) with the product its name names; not one that needs
    values only a product, or its mapped properties, give and has
    neither."""
    choices = []
    for f in findings:
        mapped = [v.target.param for v in finding_values(f, mappings)[0]]
        needs_product = f.kind in REQUIRED_VALUES and not f.product and not complete(f.kind, mapped)
        choices.append(DeviceChoice(f.addable and not needs_product, f.kind,
                                    MODEL_AXIS if f.model_axis is not None else DEFAULT_AXIS, f.product))
    return choices


def _unique(base: str, taken: set) -> str:
    name, n = base, 2
    while name in taken:
        name, n = f"{base} {n}", n + 1
    taken.add(name)
    return name


def build_devices(findings: list[DeviceFinding], choices: list[DeviceChoice], taken: set,
                  mappings=()) -> DeviceResult:
    """The sensors and actuators of the findings chosen to be added, named
    after their equipment (made unique against ``taken``, which grows), and
    what the import record keeps. The values ``mappings`` read from a
    finding's properties go over its product's. A finding is skipped, with
    the reason, when it is not chosen, its kind cannot be added, or it
    needs values (:data:`REQUIRED_VALUES`) that neither a product nor its
    properties give."""
    result = DeviceResult()
    if len(findings) != len(choices):
        raise ValueError("one choice per finding")
    for finding, choice in zip(findings, choices):
        values, _problems = finding_values(finding, mappings)
        mapped = [v.target.param for v in values]
        if not choice.add:
            result.skipped.append((finding.equipment, why_not(choice.kind, choice.product, mapped) or "not chosen"))
            continue
        kind = choice.kind
        if kind not in ADDABLE_KINDS:
            result.skipped.append((finding.equipment, why_not(kind)))
            continue
        product = product_by_name(kind, choice.product) if choice.product else None
        if choice.product and product is None:
            raise ValueError(f"{finding.equipment}: no {kind} product {choice.product!r} in the catalog")
        if product is None and kind in REQUIRED_VALUES and not complete(kind, mapped):
            result.skipped.append((finding.equipment, why_not(kind, "", mapped)))
            continue
        axis = finding.axis(choice.axis)
        params = copy.deepcopy(product.params) if product is not None else {}
        for value in values:
            if value.target.param in _EITHER:  # Basilisk's wheel factory takes one of the two, never both
                params.pop(_EITHER[value.target.param], None)
            params[value.target.param] = value.value
        if kind in AXIS_PARAMS:
            params[AXIS_PARAMS[kind]] = list(axis)
        name = _unique(finding.equipment.strip() or KIND_LABELS[kind], taken)
        mount = MountConfig(position_m=list(finding.position_m), boresight=list(axis))
        if choice.axis == MODEL_AXIS and finding.fov_deg is not None:
            mount.field_of_view_deg = finding.fov_deg  # the model's cone, as drawn
        if kind in SUPPORTED_SENSOR_KINDS:
            device, source = SensorConfig(kind=kind, name=name, params=params, mount=mount), "sensors"
            result.sensors.append(device)
        elif kind in SUPPORTED_ACTUATOR_KINDS:
            device, source = ActuatorConfig(kind=kind, name=name, params=params, mount=mount), "actuators"
            result.actuators.append(device)
        else:  # pragma: no cover -- ADDABLE_KINDS are all supported kinds (tests/test_idm_devices.py)
            raise ValueError(f"{kind} is not a sensor or actuator kind")
        result.values.update(device_values(device, source))
        if product is not None:
            origin = f"product: {product.display_name} ({product.source_url})"
        elif values:
            origin = "properties: Basilisk's defaults for the rest"
        else:
            origin = f"no product: Basilisk's defaults for a {KIND_LABELS[kind].lower()}"
        if values:
            origin += "; values from properties: " + ", ".join(v.describe() for v in values)
        origin += "; axis " + axis_text(finding, choice.axis)
        result.details[f"{source}[{name}]"] = origin + f"; from {finding.equipment}; unit {finding.source_id}"
    return result


def axis_text(finding: DeviceFinding, choice: str) -> str:
    """Where the axis ``choice`` of ``finding`` comes from, in words."""
    if choice == MODEL_AXIS and finding.model_axis is not None:
        return f"from {finding.axis_source}" + (f" (field of view {finding.fov_deg:g} deg)"
                                                 if finding.fov_deg is not None else "")
    if choice == MODEL_AXIS:
        return f"{DEFAULT_AXIS} of the equipment frame (its shapes show none)"
    return f"{choice} of the equipment frame"


#: A wheel takes its inertia or its maximum momentum: one mapped drops the other.
_EITHER = {"Js": "maxMomentum", "maxMomentum": "Js"}


def recorded_units(record) -> set:
    """The IDM-CIC units (placed units' ``fullId``) an import record of
    devices added a device for."""
    if record is None:
        return set()
    return {match.group(1) for text in record.details.values()
            for match in [re.search(r"; unit (\S+)$", text)] if match}


def keep_fitting(config, result: DeviceResult) -> DeviceResult:
    """``result`` without the devices spacecraft ``config`` cannot take as
    it is (a magnetorquer without magnetic momentum management, say): each
    is tried in turn against the spacecraft's own validation, and one that
    fails is moved to ``skipped`` with the reason. When the spacecraft is
    not valid without them, nothing is tried."""
    from .schema.scenario import ScenarioValidationError

    def problem(sensors, actuators) -> str:
        trial = copy.copy(config)
        trial.sensors, trial.actuators = list(config.sensors) + sensors, list(config.actuators) + actuators
        try:
            trial.validate()
        except ScenarioValidationError as exc:
            return str(exc)
        return ""

    if problem([], []):
        return result
    kept = DeviceResult(skipped=list(result.skipped))
    for source, devices in (("sensors", result.sensors), ("actuators", result.actuators)):
        for device in devices:
            mine = [device] if source == "sensors" else []
            why = problem(kept.sensors + mine, kept.actuators + ([device] if source == "actuators" else []))
            path = f"{source}[{device.name}]"
            equipment = re.search(r"; from (.*); unit ", result.details[path])
            if why:
                kept.skipped.append((equipment.group(1) if equipment else device.name,
                                     f"{CANNOT_TAKE}: {why}"))
                continue
            getattr(kept, source).append(device)
            kept.details[path] = result.details[path]
            kept.values.update({k: v for k, v in result.values.items() if k.startswith(f"{path}.")})
    return kept


def device_values(device, source: str) -> dict:
    """``device``'s kind, its mount and its numeric and text parameters, by
    path (``sensors[NAME].params.KEY``, a vector's components as
    ``KEY[i]``), as an import record keeps them."""
    where = f"{source}[{device.name}]"
    values = {f"{where}.kind": device.kind}
    for key, value in sorted(device.params.items()):
        if isinstance(value, bool):
            values[f"{where}.params.{key}"] = "true" if value else "false"
        elif isinstance(value, (int, float)):
            values[f"{where}.params.{key}"] = float(value)
        elif isinstance(value, str):
            values[f"{where}.params.{key}"] = value
        elif isinstance(value, (list, tuple)) and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                                      for v in value):
            values.update({f"{where}.params.{key}[{i}]": float(v) for i, v in enumerate(value)})
    mount = getattr(device, "mount", None)
    if mount is not None:
        for key in ("position_m", "boresight"):
            vector = getattr(mount, key)
            if vector is not None:
                values.update({f"{where}.mount.{key}[{i}]": float(v) for i, v in enumerate(vector)})
    return values


def device_import_values(config) -> dict:
    """Every device of spacecraft ``config`` by :func:`device_values`: what
    an import record of its devices is compared with."""
    values = {}
    for source in ("sensors", "actuators"):
        for device in getattr(config, source, None) or []:
            values.update(device_values(device, source))
    return values


def unset_devices(scenario) -> list[tuple[str, str, str]]:
    """``(spacecraft, device path, kind)`` of each device an IDM-CIC
    import added without a catalog product whose values are still those
    imported: it runs with Basilisk's defaults (``import.device_defaults``)."""
    found = []
    for record in getattr(scenario, "imports", []):
        if record.target != "devices":
            continue
        config = next((sc for sc in scenario.spacecraft if sc.name == record.spacecraft), None)
        if config is None:
            continue
        now = device_import_values(config)
        for path, text in record.details.items():
            if not text.startswith("no product"):
                continue
            mine = {key: value for key, value in record.values.items() if key.startswith(f"{path}.")}
            if mine and all(now.get(key) == value for key, value in mine.items()) \
                    and {k for k in now if k.startswith(f"{path}.")} == set(mine):
                found.append((record.spacecraft, path, str(mine.get(f"{path}.kind", ""))))
    return found
