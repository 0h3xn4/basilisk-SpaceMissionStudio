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
"""The published atmosphere profiles a run with ``atmosphere_model:
"tabular"`` interpolates (transparency plan, Phase 6b): the tables Basilisk
ships in ``supportData/AtmosphereData``, read by its own
``Basilisk.utilities.readAtmTable`` and interpolated by its
``TabularAtmosphere`` module. Their sources and the conditions they were
made for are Basilisk's ``supportData/AtmosphereData/support/README.txt``
and namelists, as recorded below.

Each profile is one column: density and temperature by altitude only, the
same everywhere and at every time, with no space-weather dependence; above
its top (and below its bottom) the density is 0.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AtmosphereTable:
    name: str  # schema.scenario.ATMOSPHERE_TABLES
    title: str
    data_file: str  # the member of Basilisk's DataFile.AtmosphereData
    reader: str  # readAtmTable's type name
    bottom_km: float  # [km] the table's lowest altitude
    top_km: float  # [km] its highest: above it the density is 0
    source: str
    conditions: str  # what it was made for


TABLES: dict[str, AtmosphereTable] = {table.name: table for table in (
    AtmosphereTable(
        "us_standard_1976", "U.S. Standard Atmosphere, 1976", "USStandardAtmosphere1976", "StdAtm76",
        -5.0, 86.0,  # [km]
        "U.S. Standard Atmosphere, 1976 (NOAA, NASA, USAF; NOAA-S/T 76-1562); the table was generated with "
        "digitaldutch.com's atmosphere calculator, every 500 m (Basilisk's AtmosphereData README).",
        "The standard's mid-latitude year-round mean; it is not defined above 86 km."),
    AtmosphereTable(
        "earthgram_2016_nominal", "Earth-GRAM 2016, nominal profile", "EarthGRAMNominal", "EarthGRAM",
        0.0, 200.0,  # [km]
        "NASA's Earth Global Reference Atmospheric Model 2016 (Earth-GRAM 2016), its mean density and "
        "temperature, every 500 m (Basilisk's AtmosphereData README and EarthGRAM_bsk_namelist.txt).",
        "40 deg N, 105.27 deg W, 2021-09-21 21 h; F10.7 230 (daily and mean), Ap 16.3."),
    AtmosphereTable(
        "nrlmsise00_nominal", "NRLMSISE-00, nominal profile", "NRLMSISE00Nominal", "MSIS",
        0.0, 499.5,  # [km]
        "NRLMSISE-00, from NASA CCMC's ModelWeb, every 500 m (Basilisk's AtmosphereData README).",
        "40 deg N, 40 deg E, 2021-04-01 21 h UT; the solar and geomagnetic indices were ModelWeb's defaults "
        "and are not recorded in the file."),
)}


def table(name: str) -> AtmosphereTable:
    return TABLES[name]


def data_file(name: str):
    """The table's Basilisk ``DataFile`` member (Basilisk)."""
    from Basilisk.utilities.supportDataTools.dataFetcher import DataFile

    return getattr(DataFile.AtmosphereData, TABLES[name].data_file)


def load(name: str, path) -> tuple[list, list, list]:
    """``(altitudes [m], densities [kg/m^3], temperatures [K])`` of the
    table at ``path``, ascending, by Basilisk's own reader (Basilisk)."""
    from Basilisk.utilities.readAtmTable import readAtmTable

    altitudes, densities, temperatures = readAtmTable(str(path), TABLES[name].reader)
    return list(altitudes), list(densities), list(temperatures)


def above_the_table(name: str, perigee_altitudes_km: dict) -> list[str]:
    """The spacecraft (``{name: perigee altitude [km]}``) whose perigee is
    above the table's top: drag on them is 0."""
    top_km = TABLES[name].top_km
    return [spacecraft for spacecraft, perigee_km in perigee_altitudes_km.items() if perigee_km > top_km]
