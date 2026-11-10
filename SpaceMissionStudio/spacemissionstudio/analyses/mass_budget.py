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
"""The mass budget with maturity margins.

Each part with mass (that counts toward the model's mass), each mounted
unit with mass, each flexible solar array and the propellant are a line.
A part or unit carries a maturity category of the policy in force
(``model.mass_budget.policy``; by default AIAA S-120-2006's mass growth
allowance, decision D-13) and a subsystem, which picks the policy's column.
A line with no category has no margin and is counted as such.

Totals: the basic (current best estimate) dry mass, the growth allowance,
the dry mass with it, an optional system margin on that (``system_margin_
percent``), the propellant, and the launch mass, compared with the mass
limit and its source. The model's typed or imported mass properties, when
they replace the parts', are noted: the budget is always of the parts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import materials as library


@dataclass
class MassLine:
    item: str
    kind: str  # "part", "equipment", "solar array" or "propellant"
    subsystem: str
    maturity: str  # the category's label, or "" for none
    mass_kg: float  # [kg] basic
    margin_percent: float  # [%]
    column: str  # the policy's column used

    @property
    def margin_kg(self) -> float:
        return self.mass_kg * self.margin_percent / 100.0


@dataclass
class MassBudget:
    spacecraft: str
    policy: str
    policy_source: str
    lines: list = field(default_factory=list)  # list[MassLine], dry lines
    propellant_kg: float = 0.0  # [kg]
    system_margin_percent: float = 0.0  # [%]
    mass_limit_kg: float | None = None  # [kg]
    limit_source: str = ""
    notes: list = field(default_factory=list)

    @property
    def basic_dry_kg(self) -> float:
        return sum(line.mass_kg for line in self.lines)

    @property
    def growth_kg(self) -> float:
        return sum(line.margin_kg for line in self.lines)

    @property
    def dry_with_growth_kg(self) -> float:
        return self.basic_dry_kg + self.growth_kg

    @property
    def system_margin_kg(self) -> float:
        return self.dry_with_growth_kg * self.system_margin_percent / 100.0

    @property
    def dry_with_margins_kg(self) -> float:
        return self.dry_with_growth_kg + self.system_margin_kg

    @property
    def launch_mass_kg(self) -> float:
        return self.dry_with_margins_kg + self.propellant_kg

    @property
    def headroom_kg(self) -> float | None:
        """The mass limit less the launch mass with margins (negative: over)."""
        return None if self.mass_limit_kg is None else self.mass_limit_kg - self.launch_mass_kg

    def by_subsystem(self) -> dict:
        """``{subsystem: (basic, growth)}`` [kg]."""
        groups: dict = {}
        for line in self.lines:
            basic, growth = groups.get(line.subsystem or "(none)", (0.0, 0.0))
            groups[line.subsystem or "(none)"] = (basic + line.mass_kg, growth + line.margin_kg)
        return groups

    def rows(self) -> list[dict]:
        return [{"item": line.item, "kind": line.kind, "subsystem": line.subsystem, "maturity": line.maturity,
                 "basic_mass_kg": line.mass_kg, "growth_percent": line.margin_percent, "growth_kg": line.margin_kg,
                 "mass_with_growth_kg": line.mass_kg + line.margin_kg, "column": line.column} for line in self.lines]


def mass_budget(sc) -> MassBudget:
    """The :class:`MassBudget` of spacecraft ``sc``."""
    settings = sc.model.mass_budget if sc.model is not None else None
    policy = library.mass_policy(settings.policy if settings is not None else "")
    budget = MassBudget(sc.name, policy.name, policy.source)
    if settings is not None:
        if settings.system_margin_percent is not None:
            budget.system_margin_percent = float(settings.system_margin_percent)
        budget.mass_limit_kg = settings.mass_limit_kg
        budget.limit_source = settings.limit_source

    def line(item, kind, subsystem, maturity, mass):
        if maturity:
            margin, column = library.growth_allowance(policy, maturity, subsystem, mass)
            label = policy.categories[maturity][0]
        else:
            margin, column, label = 0.0, "no maturity category", ""
        budget.lines.append(MassLine(item, kind, subsystem, label, float(mass), float(margin), column))

    if sc.model is not None:
        for part in sc.model.parts:
            if part.counts_toward_mass and part.mass_kg > 0.0:
                line(part.name, "part", part.subsystem, part.maturity, part.mass_kg)
        for item in sc.model.equipment:
            if item.mass_kg > 0.0:
                line(item.name, "equipment", item.subsystem, item.maturity, item.mass_kg)
        if sc.model.mass_properties_source != "computed":
            budget.notes.append(f"the model's mass properties are {sc.model.mass_properties_source}: the budget is "
                                "of its parts, which the run does not use")
    else:
        line(sc.name, "spacecraft", "", "", sc.dry_mass_kg)
        budget.notes.append("no 3D model: the budget is the spacecraft's dry mass as one line")
    for array in sc.solar_arrays:
        line(array.name, "solar array", "solar_array", "", array.mass_kg)
    for name, holder in (("fuel tank", sc.fuel_tank), ("station keeping", sc.station_keeping),
                         ("GEO station keeping", sc.geo_station_keeping), ("constant thrust", sc.constant_thrust)):
        mass = getattr(holder, "propellant_mass_kg", None) if holder is not None else None
        if mass is None and holder is not None:
            mass = getattr(holder, "propellant_kg", None)
        if mass:
            budget.propellant_kg += float(mass)
            budget.notes.append(f"propellant: {mass:g} kg in {name}")
    unclassified = [ln.item for ln in budget.lines if not ln.maturity and ln.kind != "spacecraft"]
    if unclassified:
        budget.notes.append(f"{len(unclassified)} line(s) without a maturity category carry no growth allowance: "
                            + ", ".join(unclassified[:6]) + ("..." if len(unclassified) > 6 else ""))
    return budget
