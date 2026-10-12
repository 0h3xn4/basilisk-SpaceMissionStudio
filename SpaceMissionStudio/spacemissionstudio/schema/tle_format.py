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

"""The TLE line format check (column layout, checksums, catalogue numbers,
epoch field), which needs no SGP4. Here so that :meth:`OrbitIC.validate`
refuses a malformed TLE when the scenario is loaded, instead of the run
failing on it (audit M16); :mod:`spacemissionstudio.engine.tle` uses the
same check and re-exports these names."""

from __future__ import annotations

import re


class TLEError(ValueError):
    """A TLE that cannot be used, with the reason."""


def _checksum(line: str) -> int:
    return sum(int(c) if c.isdigit() else 1 if c == "-" else 0 for c in line[:68]) % 10


def check_lines(line1: str, line2: str) -> None:
    """Raise :class:`TLEError` naming the first format problem found."""
    for number, line in (("1", line1), ("2", line2)):
        if len(line) != 69:
            raise TLEError(f"TLE line {number} has {len(line)} characters, expected 69")
        if line[0] != number or line[1] != " ":
            raise TLEError(f"TLE line {number} must start with '{number} '")
        if not line[68].isdigit():
            raise TLEError(f"TLE line {number} has no checksum digit in column 69")
        if _checksum(line) != int(line[68]):
            raise TLEError(f"TLE line {number} checksum is {line[68]}, computed {_checksum(line)}")
    if line1[2:7] != line2[2:7]:
        raise TLEError(f"TLE catalogue numbers differ: {line1[2:7]!r} and {line2[2:7]!r}")
    epoch = line1[18:32]  # columns 19-32: YYDDD.DDDDDDDD
    if not re.fullmatch(r"\d{5}\.\d{8}", epoch) or not 1.0 <= float(epoch[2:]) < 367.0:
        raise TLEError(f"TLE line 1 epoch {epoch!r} (columns 19-32) is not YYDDD.DDDDDDDD with a day of year 1-366")
