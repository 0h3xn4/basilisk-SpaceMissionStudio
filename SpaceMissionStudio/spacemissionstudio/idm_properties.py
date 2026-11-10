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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""Device and battery values from the properties a team keeps in an
IDM-CIC model (``idm.properties``; ``docs/developer/idm-cic-integration.md``,
section 17).

A team's model may carry, on its equipment, properties such as "Torque"
on a reaction wheel or "Capacity" on a battery. Their names are the
team's own and their units are mostly not stated, so nothing is read
until the user maps a property name to a value (:data:`TARGETS`) and says
the unit it is in (:class:`Mapping`). A unit is suggested only when the
property's value type has the target's dimension (an ``Angle`` property
for a field of view: degrees, the unit the format uses for its own
angles); a property typed as something else, or untyped, has no
suggestion.

The values mapped fill a device's parameters (over a catalog product's,
when one is chosen too) and the battery capacity of the power budget; a
wheel or magnetorquer the file then gives every value it needs
(``idm_devices.REQUIRED_VALUES``) can be added without a product. The
mapping is kept in the import records, so a newer version of the model is
read the same way.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass

#: Value types and the dimension the format's own fields of that kind are
#: in (positions in metres, rotations in degrees, masses in kilograms).
TYPE_UNITS = {"Distance": "m", "Angle": "deg", "Mass": "kg", "MomentOfInertia": "kg*m^2"}


@dataclass(frozen=True)
class Target:
    """A value a property can give: the device kind (or "battery"), the
    parameter, its unit, the units accepted with their factor to it, and a
    label."""

    kind: str
    param: str
    unit: str
    units: tuple  # ((unit, factor to ``unit``), ...)
    label: str

    @property
    def key(self) -> str:
        return f"{self.kind}.{self.param}"

    def factor(self, unit: str) -> float:
        for name, factor in self.units:
            if name == unit:
                return factor
        raise ValueError(f"{self.key} takes {', '.join(n for n, _ in self.units)}, not {unit!r}")


_RPM_PER_RAD_S = 60.0 / (2.0 * math.pi)  # [RPM/(rad/s)]
_ARCSEC_PER_RAD = 180.0 / math.pi * 3600.0  # [arcsec/rad]

#: The values a property can be mapped to.
TARGETS = {t.key: t for t in (
    Target("reaction_wheel", "u_max", "N*m", (("N*m", 1.0), ("mN*m", 1.0e-3)), "Reaction wheel: maximum torque"),
    Target("reaction_wheel", "Js", "kg*m^2", (("kg*m^2", 1.0), ("g*cm^2", 1.0e-7)),
           "Reaction wheel: inertia about the spin axis"),
    Target("reaction_wheel", "Omega_max", "RPM", (("RPM", 1.0), ("rad/s", _RPM_PER_RAD_S)),
           "Reaction wheel: maximum speed"),
    Target("reaction_wheel", "maxMomentum", "N*m*s", (("N*m*s", 1.0), ("mN*m*s", 1.0e-3)),
           "Reaction wheel: maximum momentum"),
    Target("magnetic_torque_rod", "max_dipole_a_m2", "A*m^2", (("A*m^2", 1.0),), "Magnetorquer: maximum dipole"),
    Target("star_tracker", "noise_arcsec", "arcsec", (("arcsec", 1.0), ("deg", 3600.0), ("rad", _ARCSEC_PER_RAD)),
           "Star tracker: attitude noise (1-sigma)"),
    Target("imu", "gyro_noise_rad_s", "rad/s", (("rad/s", 1.0), ("deg/s", math.pi / 180.0),
                                                 ("deg/h", math.pi / 180.0 / 3600.0)),
           "Gyro / IMU: rate noise (1-sigma)"),
    Target("coarse_sun_sensor", "fov_deg", "deg", (("deg", 1.0), ("rad", 180.0 / math.pi)),
           "Sun sensor: full field of view"),
    Target("thruster", "MaxThrust", "N", (("N", 1.0), ("mN", 1.0e-3)), "Thruster: thrust"),
    Target("battery", "capacity_wh", "W*h", (("W*h", 1.0), ("kW*h", 1000.0)), "Battery: capacity"),
)}



def normalized(name: str) -> str:
    """A property name to match on: accents, case and spacing ignored."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().split())


def suggested_unit(value_type: str, target: Target) -> str:
    """The unit to offer for a property of ``value_type`` mapped to
    ``target``: the format's own unit for that type when the target takes
    it, else "" (the user chooses)."""
    unit = TYPE_UNITS.get(value_type, "")
    return unit if unit and any(name == unit for name, _ in target.units) else ""


@dataclass(frozen=True)
class Mapping:
    """A property name (matched by :func:`normalized`), the target key and
    the unit its values are in."""

    property: str
    target: str
    unit: str

    def check(self) -> None:
        """A ValueError when the target or unit is not one there is."""
        if self.target not in TARGETS:
            raise ValueError(f"no value {self.target!r} to map a property to (there are: {', '.join(TARGETS)})")
        if not self.property.strip():
            raise ValueError(f"a mapping to {self.target} needs a property name")
        TARGETS[self.target].factor(self.unit)


def check_mappings(mappings) -> None:
    """Each mapping valid, one per property name and target, and no wheel
    given both its inertia and its momentum (Basilisk's wheel factory
    takes one or the other)."""
    seen_properties, seen_targets = set(), set()
    for mapping in mappings:
        mapping.check()
        name = normalized(mapping.property)
        if name in seen_properties:
            raise ValueError(f"the property {mapping.property!r} is mapped twice")
        if mapping.target in seen_targets:
            raise ValueError(f"two properties are mapped to {mapping.target}")
        seen_properties.add(name)
        seen_targets.add(mapping.target)
    if {"reaction_wheel.Js", "reaction_wheel.maxMomentum"} <= seen_targets:
        raise ValueError("a reaction wheel takes its inertia or its maximum momentum, not both: map one of them")


def parse_mapping(text: str) -> Mapping:
    """``"Property name=kind.param[unit]"`` (the command line's form)."""
    name, sep, rest = text.rpartition("=")
    if not sep or not rest.endswith("]") or "[" not in rest:
        raise ValueError(f"{text!r}: write a mapping as 'Property name=kind.param[unit]', e.g. "
                         "'Torque=reaction_wheel.u_max[mN*m]'")
    target, _, unit = rest[:-1].partition("[")
    mapping = Mapping(name.strip(), target.strip(), unit.strip())
    mapping.check()
    return mapping


def mapping_text(mappings) -> str:
    """The mappings as one line (an import record's detail), in the form
    :func:`parse_mappings_text` reads back."""
    return "; ".join(f"{m.property}={m.target}[{m.unit}]" for m in mappings)


def parse_mappings_text(text: str) -> list[Mapping]:
    """The mappings :func:`mapping_text` wrote ("" for none)."""
    return [parse_mapping(part.strip()) for part in text.split("; ") if part.strip()] if text else []


@dataclass(frozen=True)
class MappedValue:
    """A value read from a property: the target, the value in the target's
    unit, and how it was read (property, value as written, unit)."""

    target: Target
    value: float
    property: str
    text: str
    unit: str

    def describe(self) -> str:
        return f"{self.property} {self.text} {self.unit} -> {self.target.param} {self.value:.6g} {self.target.unit}"


def mapped_values(kind: str, properties, mappings) -> tuple[list, list]:
    """For an equipment of device ``kind`` (or "battery") with
    ``properties`` (``idm.properties.PropertyValue``): the values the
    ``mappings`` give (:class:`MappedValue`), and why a mapped property
    gave none (an empty value, or not a number)."""
    by_name = {}
    for prop in properties:
        by_name.setdefault(normalized(prop.name), prop)
    values, problems = [], []
    for mapping in mappings:
        target = TARGETS[mapping.target]
        if target.kind != kind:
            continue
        prop = by_name.get(normalized(mapping.property))
        if prop is None:
            continue
        if prop.number is None:
            problems.append(f"{prop.name}: {'empty' if not (prop.text or '').strip() else repr(prop.text)}, "
                            "not a number")
            continue
        value = prop.number * target.factor(mapping.unit)
        values.append(MappedValue(target, float(f"{value:.12g}"), prop.name, prop.text or "", mapping.unit))
    return values, problems


def properties_by_kind(found) -> dict:
    """``{normalized name: (name, value type, {kind}, [value text])}`` of the
    properties of the equipment found (``(kind, properties)`` pairs), for
    the import dialog to offer: one row per property name."""
    rows: dict = {}
    for kind, properties in found:
        for prop in properties:
            key = normalized(prop.name)
            name, value_type, kinds, texts = rows.setdefault(key, (prop.name, prop.value_type, set(), []))
            kinds.add(kind)
            if prop.text and prop.text not in texts:
                texts.append(prop.text)
    return rows
