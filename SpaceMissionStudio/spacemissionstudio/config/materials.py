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
"""The material library and the mass-margin policies of the analyses
built on the 3D model (``docs/models/materials.md``).

Every value carries its own source; a value that could not be sourced is
left out (None), and an analysis that needs it says so for the face or
part. A scenario adds its own materials (``SpacecraftModelConfig.materials``)
with the same fields. Without numpy, Basilisk or the GUI, so the schema can
check names against it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Value:
    """One sourced number: ``value`` in the unit of its field, and where it
    comes from."""

    value: float
    source: str


@dataclass(frozen=True)
class Material:
    """A library material. Each field is a :class:`Value` or None (not
    sourced)."""

    name: str
    description: str
    density_kg_m3: Value | None = None  # [kg/m^3]
    melting_temperature_k: Value | None = None  # [K]
    heat_of_fusion_j_kg: Value | None = None  # [J/kg]
    specific_heat_j_kg_k: Value | None = None  # [J/(kg*K)]
    emissivity: Value | None = None  # [-]
    solar_absorptance: Value | None = None  # [-]
    ao_erosion_yield_cm3_atom: Value | None = None  # [cm^3/atom]


# The sources, as the docs cite them (docs/models/materials.md has the tables and pages).
DAS = ("NASA DAS 3.0 User's Guide (Liou et al., NASA/TP-2019-220300, 2019), Appendix C.6, Table C-4 "
       "\"Properties of DAS 3 Built-In Materials\"")
HENNINGER = ("Henninger, Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control "
             "Coatings, NASA RP-1121, 1984 (normal emittance at about 300 K; tolerance about 0.02)")
MISSE = "de Groh & Banks, Atomic Oxygen Erosion Data From the MISSE 2-8 Missions, NASA/TM-2019-219982, 2019, Table 3"
TRIPLE_JUNCTION = ("Russell & Jones, Development of a High Efficiency UVR/IRR Coverglass for Triple Junction Solar "
                   "Cells, SPRAT XIX, 2007, Table 1 (AR-coated coverglass)")


def _das(density, melt, fusion, cp, cp_note=""):
    note = DAS + (f"; {cp_note}" if cp_note else "")
    return {"density_kg_m3": Value(density, DAS), "melting_temperature_k": Value(melt, DAS),
            "heat_of_fusion_j_kg": Value(fusion, DAS), "specific_heat_j_kg_k": Value(cp, note)}


def _optics(absorptance, emittance, page):
    source = f"{HENNINGER}, {page}"
    return {"solar_absorptance": Value(absorptance, source), "emissivity": Value(emittance, source)}


def _misse(yield_cm3, mission):
    return {"ao_erosion_yield_cm3_atom": Value(yield_cm3, f"{MISSE} ({mission})")}


#: The library, by key (the name a part or face names). Specific heats DAS
#: gives as a temperature range are the range's midpoint, stated per value.
MATERIALS: dict[str, Material] = {m.name: m for m in (
    # Structural materials for re-entry demise (DAS 3.0).
    Material("aluminium_6061_t6", "Aluminium 6061-T6",
             **_das(2707.0, 867.0, 386116.0, 896.0)),
    Material("aluminium", "Aluminium (generic)", **_das(2700.0, 850.0, 390000.0, 1100.0)),
    Material("titanium_6al_4v", "Titanium Ti-6Al-4V",
             **_das(4437.0, 1943.0, 393559.0, 780.0, "DAS gives 450 < cp < 1110: the midpoint")),
    Material("titanium", "Titanium (generic)", **_das(4400.0, 1950.0, 470000.0, 600.0)),
    Material("steel_aisi_304", "Stainless steel AISI 304",
             **_das(7900.0, 1700.0, 286098.0, 545.0, "DAS gives 482 < cp < 608: the midpoint")),
    Material("steel_aisi_316", "Stainless steel AISI 316", **_das(8026.85, 1644.0, 286098.0, 460.6)),
    Material("stainless_steel", "Stainless steel (generic)", **_das(7800.0, 1700.0, 270000.0, 600.0)),
    Material("copper", "Copper alloy",
             **_das(8938.0, 1356.0, 204921.0, 428.5, "DAS gives 385 < cp < 472: the midpoint")),
    Material("inconel_718", "Inconel 718", **_das(8190.0, 1571.0, 311664.0, 435.0)),
    Material("cfrp", "Graphite epoxy (CFRP), DAS \"Graphite epoxy 1\"", **_das(1550.5, 700.0, 232.6, 879.0)),
    Material("zerodur", "Zerodur glass-ceramic",
             **_das(2530.0, 1424.0, 250000.0, 1200.0, "DAS gives 800 < cp < 1600: the midpoint")),
    Material("gallium_arsenide", "Gallium arsenide", **_das(5316.0, 1510.0, 0.0, 325.0)),
    # Surfaces: optical properties and atomic-oxygen erosion.
    Material("white_paint_z93", "White paint Z-93", **_optics(0.17, 0.92, "White Coatings")),
    Material("white_paint_s13g", "White paint S-13G", **_optics(0.20, 0.90, "White Coatings")),
    Material("black_paint_z306", "Black paint Chemglaze Z306", **_optics(0.96, 0.91, "Black Coatings")),
    Material("buffed_aluminium", "Buffed aluminium surface", **_optics(0.16, 0.03, "Metals")),
    Material("polished_stainless_steel", "Polished stainless steel surface", **_optics(0.42, 0.11, "Metals")),
    Material("buffed_copper", "Buffed copper surface", **_optics(0.30, 0.03, "Metals")),
    Material("vapour_deposited_aluminium", "Vapour-deposited aluminium", **_optics(0.08, 0.02, "Vapor-Deposited")),
    Material("gold_electroplated", "Electroplated gold", **_optics(0.23, 0.03, "Metals")),
    Material("silvered_teflon_5mil", "Silver-backed Teflon, 5 mil", **_optics(0.08, 0.81, "Films and Tapes")),
    Material("aluminised_teflon_5mil", "Aluminium-backed Teflon (FEP), 5 mil", **_optics(0.13, 0.81, "Films and Tapes"),
             **_misse(2.11e-25, "MISSE 2, Al-backed FEP")),
    Material("mli_kapton_aluminised_1mil", "MLI outer layer: Kapton, aluminium backing, 1 mil",
             **_optics(0.38, 0.67, "Films and Tapes"),
             **_misse(3.00e-24, "the yield of Kapton H, taken for the Kapton film of the outer layer")),
    Material("kapton_h", "Kapton H polyimide", **_misse(3.00e-24, "reference value for 4.5 eV LEO atomic oxygen")),
    Material("kapton_hn", "Kapton HN polyimide", **_misse(2.81e-24, "MISSE 2")),
    Material("black_kapton_xc", "Black Kapton XC", **_misse(2.20e-24, "MISSE 7")),
    Material("mylar_pet", "Mylar (PET)", **_misse(3.01e-24, "MISSE 2")),
    Material("teflon_fep", "Teflon FEP", **_misse(2.00e-25, "MISSE 2")),
    Material("teflon_ptfe", "Teflon PTFE", **_misse(1.42e-25, "MISSE 2")),
    Material("silicone_dc93_500", "Silicone DC 93-500", **_misse(3.81e-27, "MISSE 8")),
    Material("solar_cell_triple_junction", "Triple-junction solar cell, AR-coated coverglass",
             solar_absorptance=Value(0.895, TRIPLE_JUNCTION), emissivity=Value(0.89, TRIPLE_JUNCTION)),
)}

#: Why metals have no erosion yield here (they are not left out by oversight).
METALS_AO_NOTE = ("The atomic oxygen erosion yield is not a meaningful number for most metals, whose oxide "
                  "shields them; silver is an exception (its oxide spalls). Banks, de Groh & Miller, "
                  "NASA/TM-2004-213400; Banks, Miller & de Groh, NASA/TM-2004-213223.")


@dataclass(frozen=True)
class MassMarginPolicy:
    """A cited mass-margin policy: the margin per maturity category [%] and
    the system-level margin [%]."""

    key: str
    name: str
    source: str
    categories: dict = field(default_factory=dict)  # category -> (label, margin [%])
    system_margin_percent: float = 0.0  # [%]


_S120_SOURCE = ("AIAA S-120-2006 mass growth allowance, as reproduced in NASA GRC COMPASS Team, ALIVE final "
                "report CD-2012-72, 2012, Table 2.3 \"MGA and Depletion Schedule (AIAA S-120-2006)\"")

#: AIAA S-120-2006's subsystem columns, in the table's order. Electronics
#: are split by the unit's mass: 0-5 kg, 5-15 kg, over 15 kg.
S120_SUBSYSTEMS = ("electronics", "structure", "brackets", "battery", "solar_array", "thermal", "mechanisms",
                   "propulsion", "wire_harness", "instrumentation", "eclss")
_S120_ROWS = {  # code -> (label, electronics (0-5, 5-15, >15 kg), then the other columns in S120_SUBSYSTEMS order)
    "estimated": ("1: estimated", (30, 25, 20), (25, 30, 25, 30, 25, 25, 25, 55, 55, 23)),
    "layout": ("2: layout", (25, 20, 15), (15, 20, 15, 20, 20, 15, 15, 30, 30, 15)),
    "pre_release": ("3: pre-release design", (20, 15, 10), (10, 15, 10, 10, 15, 10, 10, 25, 25, 10)),
    "released": ("4: released design", (10, 5, 5), (5, 6, 5, 5, 5, 5, 5, 10, 10, 6)),
    "existing": ("5: existing hardware", (3, 3, 3), (3, 3, 3, 3, 2, 3, 3, 5, 5, 4)),
    "measured": ("6: actual (measured) mass", (0, 0, 0), (0,) * 10),
}


def _s120_margins(row) -> dict:
    electronics, others = row[1], row[2]
    margins = {"electronics_0_5_kg": float(electronics[0]), "electronics_5_15_kg": float(electronics[1]),
               "electronics_over_15_kg": float(electronics[2])}
    margins.update({name: float(value) for name, value in zip(S120_SUBSYSTEMS[1:], others)})
    return margins


#: The policies, by key; the first is the default. A policy's categories
#: map to ``(label, {S-120 column: margin [%]})``.
MASS_MARGIN_POLICIES: dict[str, MassMarginPolicy] = {
    "aiaa_s120_2006": MassMarginPolicy(
        "aiaa_s120_2006", "AIAA S-120-2006 mass growth allowance", _S120_SOURCE,
        {code: (row[0], _s120_margins(row)) for code, row in _S120_ROWS.items()}, 0.0),
}


def growth_allowance(policy: MassMarginPolicy, category: str, subsystem: str, mass_kg: float) -> tuple[float, str]:
    """``(margin [%], column)`` of a unit of ``mass_kg`` in ``category`` of
    ``policy``, for its ``subsystem``: an S-120 column name (electronics by
    mass bracket). A subsystem that is no column takes the row's largest
    margin, the conservative choice, and says so in the column name."""
    label, margins = policy.categories[category]
    if subsystem == "electronics":
        column = ("electronics_0_5_kg" if mass_kg <= 5.0 else
                  "electronics_5_15_kg" if mass_kg <= 15.0 else "electronics_over_15_kg")
        return margins[column], column
    if subsystem in margins:
        return margins[subsystem], subsystem
    return max(margins.values()), "largest of the row (subsystem not an S-120 column)"


def mass_policy(key: str = "") -> MassMarginPolicy:
    """The policy ``key``, or the default for ""."""
    if not key:
        return next(iter(MASS_MARGIN_POLICIES.values()))
    return MASS_MARGIN_POLICIES[key]
