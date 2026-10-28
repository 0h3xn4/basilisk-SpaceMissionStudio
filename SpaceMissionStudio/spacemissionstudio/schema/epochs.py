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

"""Reading the ISO 8601 epochs a scenario holds (``epoch_utc``, a Mission
Sequence ``stop_epoch_utc``).

An epoch may end in ``Z`` or carry a UTC offset (``+02:00``). Every module
compares epochs with naive UTC datetimes, so each one is read through
:func:`parse_epoch_utc`, which converts it to naive UTC. Reading it with
``datetime.fromisoformat`` alone gave an aware datetime that some modules
could not subtract and others compared hours apart (audit M7)."""

from __future__ import annotations

from datetime import datetime, UTC


def parse_epoch_utc(text: str) -> datetime:
    """``text`` (ISO 8601) as a naive UTC datetime. A trailing ``Z`` or an
    offset is converted to UTC; a value without either is taken as UTC.
    Raises ValueError when ``text`` is not ISO 8601."""
    if not isinstance(text, str):
        raise ValueError(f"an epoch must be ISO 8601 text, got {text!r}")
    value = text.strip()
    if value[-1:] in ("Z", "z"):
        value = value[:-1] + "+00:00"
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment
