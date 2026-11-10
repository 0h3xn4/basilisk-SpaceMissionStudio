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
