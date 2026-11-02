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
"""Slant-path gaseous attenuation by oxygen and water vapour, by
Recommendation ITU-R P.676-13 (08/2022), Annex 2: the instantaneous
methods (Sec. 1.1 for oxygen, Sec. 2.1, "method 1", for water vapour),
valid from 1 to 350 GHz and for elevations of 5 deg and above
(transparency plan, Phase 6b: ``link.atmospheric_loss``, the models in
``config.models``).

From the surface pressure P_s [hPa], temperature T_s [K] and water
vapour density rho [g/m^3] at the station:

    e_s = rho T_s / 216.7,   p_s = P_s - e_s                     [hPa]
    gamma_o = 0.1820 f N''_oxygen(f, p_s, e_s, T_s)              [dB/km] (Annex 2, eq. 30)
    gamma_w = 0.1820 f N''_water vapour(f, p_s, e_s, T_s)        [dB/km] (eq. 36)
    h_o = a_o(f) + b_o(f) T_s + c_o(f) P_s + d_o(f) rho          [km]    (eq. 31)
    h_w = A f + B + sum_i a_i / ((f - f_i)^2 + b_i)              [km]    (eq. 37, Table 4)
    A_gas = (gamma_o h_o + gamma_w h_w) / sin(elevation)         [dB]    (eqs. 29, 35)

N'' is Annex 1's line-by-line sum, eqs. (2a), (2b) and (3) to (9), over
the 44 oxygen and 35 water-vapour lines of its Tables 1 and 2 (in this
module, as published: physical measurements). a_o..d_o are linearly
interpolated in the Recommendation's data file **Part 1**, which is not
part of this tool: it is downloaded from the ITU at installation
(:func:`fetch`, like Basilisk's support data), checked against the size
and SHA-256 recorded here, and read from disk by every run, which never
touches the network.

Checked against the ITU's own validation workbook for P.676-13
(Study Group 3, CG-3M3J-13-ValEx, Rev 8.3.0): ``tests/test_gaseous_attenuation.py``.

Basilisk-free.
"""

from __future__ import annotations

import bisect
import dataclasses
import functools
import hashlib
import json
import math
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path

CHOICE = "link.atmospheric_loss"
RECOMMENDATION = "Recommendation ITU-R P.676-13 (08/2022), Attenuation by atmospheric gases and related effects"
MIN_ELEVATION_DEG = 5.0  # [deg] Annex 2's lowest elevation
MIN_FREQUENCY_GHZ = 1.0  # [GHz] Annex 2's range, and Part 1's
MAX_FREQUENCY_GHZ = 350.0  # [GHz]

# -- Annex 1, Table 1: spectroscopic data for oxygen attenuation ---------------------------------
# f0 [GHz], then a1 to a6 as Annex 1 eqs. (3), (6a) and (7) use them (their scale factors are in the code).
OXYGEN_LINES: tuple[tuple[float, ...], ...] = (
    (50.474214, 0.975, 9.651, 6.690, 0.0, 2.566, 6.850),
    (50.987745, 2.529, 8.653, 7.170, 0.0, 2.246, 6.800),
    (51.503360, 6.193, 7.709, 7.640, 0.0, 1.947, 6.729),
    (52.021429, 14.320, 6.819, 8.110, 0.0, 1.667, 6.640),
    (52.542418, 31.240, 5.983, 8.580, 0.0, 1.388, 6.526),
    (53.066934, 64.290, 5.201, 9.060, 0.0, 1.349, 6.206),
    (53.595775, 124.600, 4.474, 9.550, 0.0, 2.227, 5.085),
    (54.130025, 227.300, 3.800, 9.960, 0.0, 3.170, 3.750),
    (54.671180, 389.700, 3.182, 10.370, 0.0, 3.558, 2.654),
    (55.221384, 627.100, 2.618, 10.890, 0.0, 2.560, 2.952),
    (55.783815, 945.300, 2.109, 11.340, 0.0, -1.172, 6.135),
    (56.264774, 543.400, 0.014, 17.030, 0.0, 3.525, -0.978),
    (56.363399, 1331.800, 1.654, 11.890, 0.0, -2.378, 6.547),
    (56.968211, 1746.600, 1.255, 12.230, 0.0, -3.545, 6.451),
    (57.612486, 2120.100, 0.910, 12.620, 0.0, -5.416, 6.056),
    (58.323877, 2363.700, 0.621, 12.950, 0.0, -1.932, 0.436),
    (58.446588, 1442.100, 0.083, 14.910, 0.0, 6.768, -1.273),
    (59.164204, 2379.900, 0.387, 13.530, 0.0, -6.561, 2.309),
    (59.590983, 2090.700, 0.207, 14.080, 0.0, 6.957, -0.776),
    (60.306056, 2103.400, 0.207, 14.150, 0.0, -6.395, 0.699),
    (60.434778, 2438.000, 0.386, 13.390, 0.0, 6.342, -2.825),
    (61.150562, 2479.500, 0.621, 12.920, 0.0, 1.014, -0.584),
    (61.800158, 2275.900, 0.910, 12.630, 0.0, 5.014, -6.619),
    (62.411220, 1915.400, 1.255, 12.170, 0.0, 3.029, -6.759),
    (62.486253, 1503.000, 0.083, 15.130, 0.0, -4.499, 0.844),
    (62.997984, 1490.200, 1.654, 11.740, 0.0, 1.856, -6.675),
    (63.568526, 1078.000, 2.108, 11.340, 0.0, 0.658, -6.139),
    (64.127775, 728.700, 2.617, 10.880, 0.0, -3.036, -2.895),
    (64.678910, 461.300, 3.181, 10.380, 0.0, -3.968, -2.590),
    (65.224078, 274.000, 3.800, 9.960, 0.0, -3.528, -3.680),
    (65.764779, 153.000, 4.473, 9.550, 0.0, -2.548, -5.002),
    (66.302096, 80.400, 5.200, 9.060, 0.0, -1.660, -6.091),
    (66.836834, 39.800, 5.982, 8.580, 0.0, -1.680, -6.393),
    (67.369601, 18.560, 6.818, 8.110, 0.0, -1.956, -6.475),
    (67.900868, 8.172, 7.708, 7.640, 0.0, -2.216, -6.545),
    (68.431006, 3.397, 8.652, 7.170, 0.0, -2.492, -6.600),
    (68.960312, 1.334, 9.650, 6.690, 0.0, -2.773, -6.650),
    (118.750334, 940.300, 0.010, 16.640, 0.0, -0.439, 0.079),
    (368.498246, 67.400, 0.048, 16.400, 0.0, 0.000, 0.000),
    (424.763020, 637.700, 0.044, 16.400, 0.0, 0.000, 0.000),
    (487.249273, 237.400, 0.049, 16.000, 0.0, 0.000, 0.000),
    (715.392902, 98.100, 0.145, 16.000, 0.0, 0.000, 0.000),
    (773.839490, 572.300, 0.141, 16.200, 0.0, 0.000, 0.000),
    (834.145546, 183.100, 0.145, 14.700, 0.0, 0.000, 0.000),
)

# -- Annex 1, Table 2: spectroscopic data for water-vapour attenuation ---------------------------
# f0 [GHz], then b1 to b6 as Annex 1 eqs. (3) and (6a) use them. The last row is the Recommendation's
# pseudo-line at 1780 GHz: its lower wing is the wet continuum (Annex 1, Sec. 1).
WATER_VAPOUR_LINES: tuple[tuple[float, ...], ...] = (
    (22.235080, 0.1079, 2.144, 26.38, 0.76, 5.087, 1.00),
    (67.803960, 0.0011, 8.732, 28.58, 0.69, 4.930, 0.82),
    (119.995940, 0.0007, 8.353, 29.48, 0.70, 4.780, 0.79),
    (183.310087, 2.273, 0.668, 29.06, 0.77, 5.022, 0.85),
    (321.225630, 0.047, 6.179, 24.04, 0.67, 4.398, 0.54),
    (325.152888, 1.514, 1.541, 28.23, 0.64, 4.893, 0.74),
    (336.227764, 0.001, 9.825, 26.93, 0.69, 4.740, 0.61),
    (380.197353, 11.67, 1.048, 28.11, 0.54, 5.063, 0.89),
    (390.134508, 0.0045, 7.347, 21.52, 0.63, 4.810, 0.55),
    (437.346667, 0.0632, 5.048, 18.45, 0.60, 4.230, 0.48),
    (439.150807, 0.9098, 3.595, 20.07, 0.63, 4.483, 0.52),
    (443.018343, 0.192, 5.048, 15.55, 0.60, 5.083, 0.50),
    (448.001085, 10.41, 1.405, 25.64, 0.66, 5.028, 0.67),
    (470.888999, 0.3254, 3.597, 21.34, 0.66, 4.506, 0.65),
    (474.689092, 1.26, 2.379, 23.20, 0.65, 4.804, 0.64),
    (488.490108, 0.2529, 2.852, 25.86, 0.69, 5.201, 0.72),
    (503.568532, 0.0372, 6.731, 16.12, 0.61, 3.980, 0.43),
    (504.482692, 0.0124, 6.731, 16.12, 0.61, 4.010, 0.45),
    (547.676440, 0.9785, 0.158, 26.00, 0.70, 4.500, 1.00),
    (552.020960, 0.184, 0.158, 26.00, 0.70, 4.500, 1.00),
    (556.935985, 497.0, 0.159, 30.86, 0.69, 4.552, 1.00),
    (620.700807, 5.015, 2.391, 24.38, 0.71, 4.856, 0.68),
    (645.766085, 0.0067, 8.633, 18.00, 0.60, 4.000, 0.50),
    (658.005280, 0.2732, 7.816, 32.10, 0.69, 4.140, 1.00),
    (752.033113, 243.4, 0.396, 30.86, 0.68, 4.352, 0.84),
    (841.051732, 0.0134, 8.177, 15.90, 0.33, 5.760, 0.45),
    (859.965698, 0.1325, 8.055, 30.60, 0.68, 4.090, 0.84),
    (899.303175, 0.0547, 7.914, 29.85, 0.68, 4.530, 0.90),
    (902.611085, 0.0386, 8.429, 28.65, 0.70, 5.100, 0.95),
    (906.205957, 0.1836, 5.110, 24.08, 0.70, 4.700, 0.53),
    (916.171582, 8.4, 1.441, 26.73, 0.70, 5.150, 0.78),
    (923.112692, 0.0079, 10.293, 29.00, 0.70, 5.000, 0.80),
    (970.315022, 9.009, 1.919, 25.50, 0.64, 4.940, 0.67),
    (987.926764, 134.6, 0.257, 29.85, 0.68, 4.550, 0.90),
    (1780.000000, 17506.0, 0.952, 196.30, 2.00, 24.150, 5.00),
)

# -- Annex 2, eq. (37) and Table 4: the water-vapour equivalent height ---------------------------
WATER_HEIGHT_A_KM_GHZ = 5.6585e-5  # [km/GHz]
WATER_HEIGHT_B_KM = 1.8348  # [km]
WATER_HEIGHT_TERMS: tuple[tuple[float, float, float], ...] = (  # f_i [GHz], a_i [km GHz^2], b_i [GHz^2]
    (22.235080, 2.6846, 2.7649),
    (183.310087, 5.8905, 4.9219),
    (325.152888, 2.9810, 3.0748),
)

# -- The data file Part 1 (a_o, b_o, c_o, d_o by frequency), downloaded at installation ----------
PART1_NAME = "R-REC-P.676-13-Part1.txt"
PART1_URL = "https://www.itu.int/dms_pub/itu-r/oth/11/01/R11010000020001TXTM.txt"
PART1_PAGE = "https://www.itu.int/oth/R1101000002/en"
PART1_SIZE_BYTES = 44100  # [byte]
PART1_SHA256 = "9c38d278274d156c2c4dcacadff9d5a9d591e467acb3b04fd330c8b03694e7be"
_MAX_DOWNLOAD_BYTES = 1024 * 1024  # [byte]
_MANIFEST = "manifest.json"

DEFAULT_DIR = Path.home() / ".cache" / "SpaceMissionStudio" / "itu_p676"
# Filled by the .deb/Windows installers for every user of the install.
SYSTEM_DIR = Path(sys.prefix) / "share" / "spacemissionstudio" / "itu_p676"


class GaseousAttenuationError(Exception):
    """The Part 1 file is missing, is not the ITU's, or could not be
    fetched; or a frequency is outside the method's range. Carries the
    reason."""


# -- Annex 1: the imaginary part of the complex refractivity --------------------------------------

def oxygen_refractivity(f_ghz: float, p_hpa: float, e_hpa: float, t_k: float) -> float:
    """[-] N''_oxygen(f), Annex 1 eq. (2a): the oxygen lines (eqs. 3 to 7;
    the width of eq. 6a, widened for Zeeman splitting by eq. 6b) and the dry continuum
    N''_D (eq. 8, with d of eq. 9). ``p_hpa`` dry pressure, ``e_hpa``
    water-vapour partial pressure, ``t_k`` temperature."""
    theta = 300.0 / t_k  # [-]
    total = 0.0
    for f0, a1, a2, a3, a4, a5, a6 in OXYGEN_LINES:
        strength = a1 * 1e-7 * p_hpa * theta ** 3 * math.exp(a2 * (1.0 - theta))  # [kHz]
        width = a3 * 1e-4 * (p_hpa * theta ** (0.8 - a4) + 1.1 * e_hpa * theta)  # [GHz]
        width = math.sqrt(width * width + 2.25e-6)  # [GHz] eq. (6b)
        delta = (a5 + a6 * theta) * 1e-4 * (p_hpa + e_hpa) * theta ** 0.8  # [-] eq. (7)
        total += strength * _line_shape(f_ghz, f0, width, delta)
    d = 5.6e-4 * (p_hpa + e_hpa) * theta ** 0.8  # [GHz] eq. (9)
    continuum = f_ghz * p_hpa * theta ** 2 * (6.14e-5 / (d * (1.0 + (f_ghz / d) ** 2))
                                              + 1.4e-12 * p_hpa * theta ** 1.5 / (1.0 + 1.9e-5 * f_ghz ** 1.5))
    return total + continuum


def water_vapour_refractivity(f_ghz: float, p_hpa: float, e_hpa: float, t_k: float) -> float:
    """[-] N''_water vapour(f), Annex 1 eq. (2b): the water-vapour lines
    (eqs. 3 to 6;
    the width of eq. 6a, widened for Doppler broadening by eq. 6b; delta = 0, eq. 7)."""
    theta = 300.0 / t_k  # [-]
    total = 0.0
    for f0, b1, b2, b3, b4, b5, b6 in WATER_VAPOUR_LINES:
        strength = b1 * 1e-1 * e_hpa * theta ** 3.5 * math.exp(b2 * (1.0 - theta))  # [kHz]
        width = b3 * 1e-4 * (p_hpa * theta ** b4 + b5 * e_hpa * theta ** b6)  # [GHz]
        width = 0.535 * width + math.sqrt(0.217 * width * width + 2.1316e-12 * f0 * f0 / theta)  # [GHz] eq. (6b)
        total += strength * _line_shape(f_ghz, f0, width, 0.0)
    return total


def _line_shape(f_ghz: float, f0: float, width: float, delta: float) -> float:
    """The line-shape factor F, Annex 1 eq. (5)."""
    return f_ghz / f0 * ((width - delta * (f0 - f_ghz)) / ((f0 - f_ghz) ** 2 + width ** 2)
                         + (width - delta * (f0 + f_ghz)) / ((f0 + f_ghz) ** 2 + width ** 2))


def specific_attenuation_db_km(f_ghz: float, p_hpa: float, e_hpa: float, t_k: float) -> tuple[float, float]:
    """``(gamma_o, gamma_w)`` [dB/km], Annex 1 eq. (1) split by gas (Annex
    2 eqs. 30 and 36): 0.1820 f N''."""
    return (0.1820 * f_ghz * oxygen_refractivity(f_ghz, p_hpa, e_hpa, t_k),
            0.1820 * f_ghz * water_vapour_refractivity(f_ghz, p_hpa, e_hpa, t_k))


def water_vapour_height_km(f_ghz: float) -> float:
    """[km] h_w, Annex 2 eq. (37)."""
    return WATER_HEIGHT_A_KM_GHZ * f_ghz + WATER_HEIGHT_B_KM + sum(
        a / ((f_ghz - fi) ** 2 + b) for fi, a, b in WATER_HEIGHT_TERMS)


# -- Part 1 ------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Part1:
    """The data file Part 1: ``rows`` of (f [GHz], a_o [km], b_o [km/K],
    c_o [km/hPa], d_o [km m^3/g]), by increasing frequency."""

    rows: tuple[tuple[float, float, float, float, float], ...]
    source: str = ""

    def coefficients(self, f_ghz: float) -> tuple[float, float, float, float]:
        """(a_o, b_o, c_o, d_o) at ``f_ghz``, linearly interpolated between
        the file's frequencies (Annex 2, Sec. 1.1)."""
        frequencies = [row[0] for row in self.rows]
        if not frequencies[0] <= f_ghz <= frequencies[-1]:
            raise GaseousAttenuationError(f"{f_ghz:g} GHz is outside Part 1 ({frequencies[0]:g} to "
                                          f"{frequencies[-1]:g} GHz)")
        i = bisect.bisect_left(frequencies, f_ghz)
        if frequencies[i] == f_ghz:
            return self.rows[i][1:]
        low, high = self.rows[i - 1], self.rows[i]
        w = (f_ghz - low[0]) / (high[0] - low[0])  # [-]
        return tuple(a + w * (b - a) for a, b in zip(low[1:], high[1:]))

    def oxygen_height_km(self, f_ghz: float, pressure_hpa: float, temperature_k: float,
                         water_vapour_density_g_m3: float) -> float:
        """[km] h_o, Annex 2 eq. (31)."""
        a, b, c, d = self.coefficients(f_ghz)
        return a + b * temperature_k + c * pressure_hpa + d * water_vapour_density_g_m3


def parse_part1(text: str, source: str = "") -> Part1:
    """Part 1 from its text: one frequency per line, five numbers."""
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            values = tuple(float(value) for value in line.split())
        except ValueError:
            values = ()
        if len(values) != 5 or not all(math.isfinite(v) for v in values):
            raise GaseousAttenuationError(f"Part 1 line {number}: not five numbers")
        rows.append(values)
    rows.sort(key=lambda row: row[0])
    if len(rows) < 2 or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise GaseousAttenuationError("Part 1: fewer than two frequencies, or a frequency repeated")
    return Part1(tuple(rows), source)


@dataclass
class InstalledFile:
    path: str
    source: str  # the URL, or the imported file's original path
    size_bytes: int  # [byte]
    sha256: str
    installed_utc: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(path: Path) -> None:
    size = path.stat().st_size
    if size != PART1_SIZE_BYTES or _sha256(path) != PART1_SHA256:
        raise GaseousAttenuationError(f"{path.name} is not the ITU's P.676-13 Part 1 ({size} bytes, its SHA-256 "
                                      f"{'differs' if size == PART1_SIZE_BYTES else 'not checked'}; the ITU's has "
                                      f"{PART1_SIZE_BYTES} bytes, SHA-256 {PART1_SHA256})")


def installed(directory: Path | None = None) -> InstalledFile | None:
    """The installed Part 1, if its file is still there with the size it
    was installed with. Without ``directory``: the user's files, else the
    install-wide ones. The file is looked for beside its manifest, so an
    installed folder can be moved (the .deb and the Windows setup do)."""
    directories = [Path(directory)] if directory is not None else [DEFAULT_DIR, SYSTEM_DIR]
    for folder in directories:
        try:
            entry = json.loads((folder / _MANIFEST).read_text(encoding="utf-8"))
            found = InstalledFile(**{key: entry[key] for key in InstalledFile.__dataclass_fields__})
        except (OSError, ValueError, KeyError, TypeError):
            continue
        path = folder / PART1_NAME
        if path.is_file() and path.stat().st_size == found.size_bytes:
            return dataclasses.replace(found, path=str(path))
    return None


def _install(staged: Path, source: str, directory: Path) -> InstalledFile:
    _check(staged)
    destination = directory / PART1_NAME
    shutil.move(str(staged), str(destination))
    found = InstalledFile(str(destination), source, destination.stat().st_size, _sha256(destination),
                          datetime.now(UTC).replace(microsecond=0).isoformat())
    (directory / _MANIFEST).write_text(json.dumps(asdict(found), indent=2), encoding="utf-8")
    return found


def fetch(directory: Path | None = None, timeout_s: float = 120.0) -> InstalledFile:
    """Download Part 1 from the ITU, check it and install it. **Network
    access: only at installation, or when the user asks.**"""
    directory = Path(directory) if directory else DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    part = directory / (PART1_NAME + ".part")
    request = urllib.request.Request(PART1_URL, headers={"User-Agent": "SpaceMissionStudio"})  # noqa: S310 -- constant https ITU URL
    try:
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 -- constant https ITU URL
                data = response.read(_MAX_DOWNLOAD_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GaseousAttenuationError(f"could not fetch {PART1_URL}: {exc}") from exc
        if len(data) > _MAX_DOWNLOAD_BYTES:
            raise GaseousAttenuationError(f"{PART1_URL} is larger than {_MAX_DOWNLOAD_BYTES} bytes")
        part.write_bytes(data)
        return _install(part, PART1_URL, directory)
    finally:
        if part.exists():
            part.unlink()


def import_file(path, directory: Path | None = None) -> InstalledFile:
    """Install Part 1 from a copy on disk (e.g. removable media); it must
    be the ITU's file, byte for byte."""
    source = Path(path)
    directory = Path(directory) if directory else DEFAULT_DIR
    part = directory / (PART1_NAME + ".part")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, part)
        return _install(part, str(source), directory)
    except OSError as exc:
        raise GaseousAttenuationError(f"could not import {source.name}: {exc}") from exc
    finally:
        if part.exists():
            part.unlink()


def part1_path() -> Path:
    """The installed Part 1's path. Raises GaseousAttenuationError when it
    is not installed."""
    found = installed()
    if found is None:
        raise GaseousAttenuationError(
            "the ITU-R P.676-13 data file Part 1 is not installed (link.atmospheric_loss is itu_r_p676). "
            "SpaceMissionStudio does not download during a run: run 'spacemissionstudio gaseous-attenuation "
            "--fetch' (needs internet), or --import the file from disk, or choose link.atmospheric_loss: none.")
    return Path(found.path)


def load_part1(path: Path | None = None) -> Part1:
    """The installed Part 1 (or the one at ``path``), checked against the
    ITU's size and SHA-256, read once per file version."""
    path = Path(path) if path is not None else part1_path()
    try:
        stat = path.stat()
    except OSError as exc:
        raise GaseousAttenuationError(f"could not read {path}: {exc}") from exc
    return _load(str(path), stat.st_size, stat.st_mtime_ns)


@functools.lru_cache(maxsize=4)
def _load(path: str, _size: int, _mtime_ns: int) -> Part1:
    _check(Path(path))
    return parse_part1(Path(path).read_text(encoding="ascii"), path)


# -- Annex 2: the slant path -----------------------------------------------------------------------

@dataclass(frozen=True)
class Surface:
    """The station's surface conditions."""

    pressure_hpa: float  # [hPa] P_s, the total (barometric) pressure
    temperature_k: float  # [K] T_s
    water_vapour_density_g_m3: float  # [g/m^3] rho_ws

    @property
    def vapour_pressure_hpa(self) -> float:
        """[hPa] e_s = rho T_s / 216.7."""
        return self.water_vapour_density_g_m3 * self.temperature_k / 216.7

    @property
    def dry_pressure_hpa(self) -> float:
        """[hPa] p_s = P_s - e_s."""
        return self.pressure_hpa - self.vapour_pressure_hpa


@dataclass(frozen=True)
class Zenith:
    """Every frequency- and surface-dependent term at the zenith: the
    attenuation at elevation theta is ``total_db / sin(theta)``."""

    frequency_ghz: float  # [GHz] the frequency the terms were computed at
    gamma_o_db_km: float  # [dB/km]
    gamma_w_db_km: float  # [dB/km]
    h_o_km: float  # [km]
    h_w_km: float  # [km]

    @property
    def oxygen_db(self) -> float:
        return self.gamma_o_db_km * self.h_o_km

    @property
    def water_vapour_db(self) -> float:
        return self.gamma_w_db_km * self.h_w_km

    @property
    def total_db(self) -> float:
        return self.oxygen_db + self.water_vapour_db


def method_frequency_ghz(frequency_hz: float) -> float:
    """[GHz] The frequency the method is evaluated at: the link's, or 1 GHz
    below it (the method's lowest, where the gases take a few hundredths of
    a dB at the zenith: an upper bound on the less there is at lower
    frequencies). Above 350 GHz there is no method: GaseousAttenuationError."""
    f_ghz = frequency_hz / 1e9
    if f_ghz > MAX_FREQUENCY_GHZ:
        raise GaseousAttenuationError(f"ITU-R P.676-13 Annex 2 covers 1 to 350 GHz; the link is at {f_ghz:g} GHz")
    return max(f_ghz, MIN_FREQUENCY_GHZ)


def zenith(frequency_hz: float, surface: Surface, part1: Part1) -> Zenith:
    """The zenith terms at ``frequency_hz`` (see :func:`method_frequency_ghz`)."""
    f_ghz = method_frequency_ghz(frequency_hz)
    gamma_o, gamma_w = specific_attenuation_db_km(f_ghz, surface.dry_pressure_hpa, surface.vapour_pressure_hpa,
                                                  surface.temperature_k)
    h_o = part1.oxygen_height_km(f_ghz, surface.pressure_hpa, surface.temperature_k,
                                 surface.water_vapour_density_g_m3)
    return Zenith(f_ghz, gamma_o, gamma_w, h_o, water_vapour_height_km(f_ghz))


def method_elevation_deg(elevation_deg: float) -> float:
    """[deg] The elevation the method is evaluated at: the given one, or
    5 deg below it (the method's lowest)."""
    return max(float(elevation_deg), MIN_ELEVATION_DEG)


def slant_path_db(zenith_terms: Zenith, elevation_deg: float) -> float:
    """[dB] A_gas = (gamma_o h_o + gamma_w h_w) / sin(theta), theta from
    :func:`method_elevation_deg`."""
    return zenith_terms.total_db / math.sin(math.radians(method_elevation_deg(elevation_deg)))
