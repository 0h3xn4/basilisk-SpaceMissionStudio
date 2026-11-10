#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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


def author_file() -> Path:
    """Where Settings keeps the author's name: a plain UTF-8 file, so the
    command line reads the same name as the app, without Qt."""
    return Path.home() / ".spacemissionstudio" / "author.txt"


def set_author(name: str) -> None:
    """The name Settings gives; an empty one forgets it (the user name
    again). Raises OSError."""
    name = " ".join(name.split())  # one line, no stray spaces
    path = author_file()
    if not name:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(name + "\n", encoding="utf-8")


def set_author_name() -> str:
    """The name set in Settings, or "" when none is."""
    try:
        return " ".join(author_file().read_text(encoding="utf-8").split())
    except (OSError, UnicodeDecodeError):
        return ""


def current_author() -> str:
    """Who a save records: the name set in Settings, else the user name."""
    return set_author_name() or default_author()


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
    common = {"format": FORMAT, "time_utc": time_utc, "author": author or current_author(), "source": source}
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


def spacecraft_of(value_path: str) -> str | None:
    """The spacecraft a value path is of (``spacecraft[sat-1].dry_mass_kg``
    -> ``sat-1``); None for a scenario-wide value."""
    if value_path.startswith("spacecraft[") and "]" in value_path:
        return value_path[len("spacecraft["):value_path.index("]")]
    return None


def newest_first(entries: list[dict], spacecraft: str | None = None, field: str = "") -> list[dict]:
    """``entries`` (as :func:`read` gives them, oldest first) newest first,
    those of ``spacecraft`` only when one is given (the scenario's own
    entries, created and replaced, stay), and those whose path contains
    ``field`` (any case) when one is given."""
    field = field.strip().lower()
    out = []
    for entry in reversed(entries):
        path = str(entry.get("path", ""))
        if spacecraft is not None and path and spacecraft_of(path) != spacecraft:
            continue
        if field and field not in path.lower():
            continue
        out.append(entry)
    return out


def describe(changed: list[tuple[str, object, object]]) -> tuple[str, str]:
    """``(short, long)`` naming ``changed`` (:func:`changes`' triples): the
    short for a menu ("dry_mass_kg", "3 changes"), the long with each old
    and new value, for a tooltip or the status bar."""
    from .engine.scenario_diff import short as shorten

    if not changed:
        return "the value marks", "the value marks (no value)"
    if len(changed) == 1:
        path, old, new = changed[0]
        leaf = path.rsplit(".", 1)[-1] or path
        where = spacecraft_of(path)
        return (f"{leaf} ({where})" if where and leaf != path else leaf,
                f"{path}: {shorten(old, 40)} -> {shorten(new, 40)}")
    names = ", ".join(path for path, _old, _new in changed[:3]) + (", ..." if len(changed) > 3 else "")
    return f"{len(changed)} changes", f"{len(changed)} changes: {names}"
