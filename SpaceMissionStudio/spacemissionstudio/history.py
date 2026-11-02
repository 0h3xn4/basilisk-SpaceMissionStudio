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
"""A scenario's change history (transparency plan, Phase 7): every value a
save changes, with its old and new value, the time, the author and the
reason, in a sidecar file beside the scenario
(``mission.json`` -> ``mission.history.jsonl``), so the scenario file
itself stays clean for version control.

The file is JSON Lines, one change per line, only ever appended to::

    {"format": 1, "time_utc": "2026-11-02T12:00:00Z", "author": "ana",
     "source": "app", "kind": "edit", "path": "spacecraft[sat-1].dry_mass_kg",
     "old": 100.0, "new": 120.0, "reason": ""}

``kind``: ``"created"`` (the first save: ``path`` is empty, ``new`` the
scenario's name), ``"edit"``, ``"override"`` (a value marked overridden:
``reason`` is the mark's, which is required) or ``"replaced"`` (the file
on disk was not a scenario to compare with). A change is found by
comparing the file on disk with what is saved (``engine.scenario_diff``),
so it is the same whether it came from a form, the JSON view or the
command line. The marks and preset records are left out: they are the
record of those values, not values.

Basilisk-free, GUI-free.
"""

from __future__ import annotations

import getpass
import json
import os
from datetime import UTC, datetime
from pathlib import Path

FORMAT = 1
SUFFIX = ".history.jsonl"
# The scenario's own records of its values (Phase 5b), not values: left out.
_NOT_VALUES = ("value_marks", "presets")


def history_path(scenario_path) -> Path:
    """The sidecar beside ``scenario_path``: ``mission.json`` ->
    ``mission.history.jsonl``."""
    path = Path(scenario_path)
    return path.with_name(path.stem + SUFFIX)


def default_author() -> str:
    """The operating-system user name, the author until one is set in
    Settings; "unknown" when there is none."""
    try:
        return getpass.getuser() or "unknown"
    except (KeyError, OSError):  # no user name (a container without a passwd entry)
        return "unknown"


def changes(before: dict | None, after: dict) -> list[tuple[str, object, object]]:
    """``(path, old, new)`` for each value that differs between two
    scenario dicts (``Scenario.to_dict()``), by its path in the file."""
    from .engine.scenario_diff import diff

    if before is None:
        return []
    return [(path, old, new) for path, old, new in diff(before, after)
            if path.split(".", 1)[0].split("[", 1)[0] not in _NOT_VALUES]


def _overrides(scenario) -> dict:
    return {mark.path: mark.reason for mark in getattr(scenario, "value_marks", [])
            if mark.state == "overridden"}


def entries_for_save(path, scenario, author: str | None = None, reason: str = "", source: str = "app",
                     now: datetime | None = None) -> list[dict]:
    """The history entries saving ``scenario`` to ``path`` makes: none when
    nothing changes. Read before the file is replaced."""
    path = Path(path)
    time_utc = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    common = {"format": FORMAT, "time_utc": time_utc, "author": author or default_author(), "source": source}
    after = scenario.to_dict()
    if not path.exists():
        return [dict(common, kind="created", path="", old=None, new=scenario.name, reason=reason)]
    try:
        before = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(before, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as exc:
        return [dict(common, kind="replaced", path="", old=f"(unreadable: {exc})", new=scenario.name,
                     reason=reason)]
    overridden = _overrides(scenario)
    entries = []
    for value_path, old, new in changes(before, after):
        if value_path in overridden:
            entries.append(dict(common, kind="override", path=value_path, old=old, new=new,
                                reason=overridden[value_path] + (f"; {reason}" if reason else "")))
        else:
            entries.append(dict(common, kind="edit", path=value_path, old=old, new=new, reason=reason))
    return entries


def append(scenario_path, entries: list[dict]) -> None:
    """Add ``entries`` to the sidecar of ``scenario_path``, creating it;
    never rewrites what is there. Raises OSError."""
    if not entries:
        return
    with open(history_path(scenario_path), "a", encoding="utf-8") as stream:
        for entry in entries:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def save(scenario, path, author: str | None = None, reason: str = "", source: str = "app"):
    """Save ``scenario`` to ``path`` (``Scenario.save``: OSError when it
    cannot be written) and record what changed. Returns ``(entries, error)``:
    the entries recorded, and the reason the history could not be written
    (the scenario is saved all the same), or None."""
    entries = entries_for_save(path, scenario, author, reason, source)
    scenario.save(path)
    try:
        append(path, entries)
    except OSError as exc:
        return entries, f"the change history ({history_path(path).name}) could not be written: {exc}"
    return entries, None


def read(scenario_path) -> tuple[list[dict], list[str]]:
    """The entries of ``scenario_path``'s history, oldest first, and a
    problem for each line that is not one (it is skipped, never lost from
    the file). No file: no entries."""
    path = history_path(scenario_path)
    if not path.exists():
        return [], []
    entries, problems = [], []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if not isinstance(entry, dict) or "kind" not in entry or "path" not in entry:
                raise ValueError("not a change")
        except ValueError as exc:
            problems.append(f"{path.name} line {number}: {exc}")
            continue
        entries.append(entry)
    return entries, problems
