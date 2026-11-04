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

"""CCSDS orbit data message files for a scenario: what the command line's
``ccsds-validate``, ``ccsds-export``, ``ccsds-import`` and ``run --oem``
do with files, shared with the GUI (Scenario › Export Orbits as CCSDS...,
the Orbit section's **Import CCSDS OPM/OMM...**, Results › Plots ›
Export all... › CCSDS ephemeris (OEM)..., Tools › Check a CCSDS File...).
The messages themselves are :mod:`engine.ccsds_odm`'s.

* :func:`read_message` reads a message, refusing a file too large to be one.
* :func:`orbit_from_file` reads an OPM or a TLE-based OMM as a spacecraft
  orbit, with the OPM's epoch, and :func:`orbit_import_record` records
  where it came from (``schema.scenario.ImportRecord``).
* :func:`initial_state_messages` gives each spacecraft's starting state as
  an OPM, or an OMM for a TLE spacecraft (needs Basilisk for an OPM).
* :func:`oem_messages` gives a run's ephemerides as OEMs.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

# A CCSDS message is read whole; a long OEM is large, an endless file
# (/dev/zero) was read until the process was killed (exit 137, audit R9).
MAX_MESSAGE_BYTES = 500_000_000  # [byte]


def read_message(path, max_bytes: int = MAX_MESSAGE_BYTES) -> str:
    """``path``'s text (ASCII, other bytes replaced); OSError when it cannot
    be read or is larger than ``max_bytes``."""
    with Path(path).open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise OSError(f"larger than {max_bytes // 1_000_000} MB: not a CCSDS message")
    return data.decode("ascii", errors="replace")


def orbit_format(text: str) -> str:
    """The import format of an orbit message: ``ccsds_opm`` or ``ccsds_omm``."""
    return "ccsds_opm" if "CCSDS_OPM_VERS" in text else "ccsds_omm"


def orbit_from_file(path, central_body: str, max_bytes: int = MAX_MESSAGE_BYTES):
    """``(OrbitIC, epoch or None, notes, file format)`` read from the OPM or
    TLE-based OMM at ``path`` for a scenario around ``central_body``. The
    epoch is the OPM state's (UTC, naive); an OMM's TLE is propagated to the
    scenario epoch, so it has none. Raises OSError, or
    ``ccsds_odm.OdmError`` (with ``issues`` when the message does not
    conform)."""
    from .engine import ccsds_odm

    text = read_message(path, max_bytes)
    orbit, epoch, notes = ccsds_odm.orbit_ic_from_odm(text, central_body=central_body)
    return orbit, epoch, notes, orbit_format(text)


def orbit_import_record(spacecraft: str, orbit, path, file_format: str, author: str = ""):
    """The :class:`schema.scenario.ImportRecord` of an orbit read from
    ``path``: the file's absolute path and SHA-256, and the values read."""
    from types import SimpleNamespace

    from .schema.scenario import ImportRecord, imported_values

    path = Path(path)
    return ImportRecord(spacecraft, "orbit", file_format, str(path.expanduser().resolve()),
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                        imported_values(SimpleNamespace(orbit=orbit), "orbit"),
                        datetime.now(UTC).replace(microsecond=0).isoformat(), author)


def total_mass_kg(spacecraft) -> float:
    """The spacecraft's mass at the epoch [kg] (CCSDS OPM MASS): dry mass plus
    every propellant load aboard."""
    blocks = (spacecraft.station_keeping, spacecraft.geo_station_keeping, spacecraft.constant_thrust)
    propellant_kg = sum(block.propellant_kg for block in blocks if block is not None)  # [kg]
    if spacecraft.fuel_tank is not None:
        propellant_kg += spacecraft.fuel_tank.propellant_mass_kg
    return spacecraft.dry_mass_kg + propellant_kg


def _central_mu(central_body: str) -> float:
    """The central body's GM [m^3/s^2], as the propagation uses it."""
    from .engine import ccsds_odm

    if central_body == "earth":
        return ccsds_odm.EARTH_GM_KM3_S2 * 1e9  # [m^3/s^2]
    from Basilisk.utilities import simIncludeGravBody

    factory = simIncludeGravBody.gravBodyFactory()
    return getattr(factory, f"create{central_body.capitalize()}")().mu


def initial_state_messages(scenario) -> list[tuple[str, str]]:
    """``(file name, text)`` of each spacecraft's starting state: an OPM in
    EME2000 at the scenario epoch, or the OMM of a TLE spacecraft. An OPM
    needs Basilisk (ImportError without it): the state is the one the run
    starts from."""
    from . import output_provenance
    from .engine import ccsds_odm, time_system

    epoch = time_system.elapsed_to_utc(scenario.epoch_utc, [0.0])[0]
    central_body = scenario.gravity.central_body
    messages = []
    for sc in scenario.spacecraft:
        if sc.orbit.type == "tle":
            text = ccsds_odm.omm_from_tle(sc.orbit.tle_line1, sc.orbit.tle_line2, sc.name,
                                          comments=output_provenance.scenario_lines(scenario))
            messages.append((f"{sc.name}.omm", text))
            continue
        from .engine.service import _orbit_ic_to_rv

        r, v = _orbit_ic_to_rv(_central_mu(central_body), sc.orbit, scenario.epoch_utc)
        text = ccsds_odm.write_opm(
            object_name=sc.name, object_id="UNKNOWN", center_name=central_body, ref_frame="EME2000",
            time_system="UTC", epoch=epoch, r_km=[x / 1e3 for x in r], v_km_s=[x / 1e3 for x in v],
            gm_km3_s2=ccsds_odm.EARTH_GM_KM3_S2 if central_body == "earth" else None, mass_kg=total_mass_kg(sc),
            srp_area_m2=sc.srp_area_m2 if sc.enable_srp else None, srp_coeff=sc.srp_coeff if sc.enable_srp else None,
            drag_area_m2=sc.drag_area_m2 if sc.enable_drag else None,
            drag_coeff=sc.drag_coeff if sc.enable_drag else None,
            comments=[f"Initial state of scenario {scenario.name!r}; EME2000 is SPICE J2000",
                      *output_provenance.scenario_lines(scenario)])
        messages.append((f"{sc.name}.opm", text))
    return messages


def oem_messages(result, scenario, stride: int = 1, interpolation: str = "hermite") -> dict[str, str]:
    """``{spacecraft: OEM text}`` of a run's recorded states, every
    ``stride``-th state and the last one, with the suggested
    ``interpolation`` (``hermite`` or ``lagrange``; GMAT reads Lagrange
    only). A spacecraft that recorded no state has none."""
    from .engine import ccsds_odm

    names = [sc.name for sc in scenario.spacecraft
             if f"{sc.name}.position_N" in result.series and len(result.series[f"{sc.name}.position_N"].time_s)]
    return ccsds_odm.oem_from_result(result, scenario.epoch_utc, scenario.gravity.central_body, names,
                                     stride=stride, interpolation=interpolation)
