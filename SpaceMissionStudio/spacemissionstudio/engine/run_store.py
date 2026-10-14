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
"""Finished runs kept on disk, so they can be compared after the app has
closed (docs/ux-audit.md U-33, decision 5: "saved to disk").

Each run is one folder under the store's root (by default
``~/.spacemissionstudio/runs``)::

    run-0007-20261014T084230/
        run.json     the scenario as it ran, the epoch, when it finished,
                     whether it was cancelled, the provenance, the
                     warnings and each series' name, columns and units
        series.npz   each series' time and data arrays (numpy, no pickle)

A run is written to a temporary folder and renamed into place, so a crash
mid-write leaves no half run. :func:`load_index` reads only the
``run.json`` files; :func:`load_result` reads one run's arrays when it is
needed. A folder that does not read back (edited, truncated, from a newer
format) is skipped and named in the log, never loaded in part.

Reading is bounded: ``run.json`` at most :data:`MAX_RUN_JSON_BYTES`, the
arrays through ``numpy.load(allow_pickle=False)`` (no code runs from a
file), and only folder names this module writes are opened or deleted.
:func:`prune` keeps the newest :data:`MAX_SAVED_RUNS` runs and at most
:data:`MAX_STORE_BYTES` in all.

Basilisk-free: it reads and writes :class:`engine.results.ResultSet` only.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import zipfile
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .results import ResultsError, ResultSet, RunProvenance, TimeSeries

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
MAX_SAVED_RUNS = 20  # runs kept on disk; the oldest go first
MAX_STORE_BYTES = 2 * 1024 ** 3  # [byte] all saved runs together
MAX_RUN_JSON_BYTES = 50 * 1024 ** 2  # [byte] a larger run.json is not read
_RUN_JSON, _SERIES_NPZ = "run.json", "series.npz"
_RUN_ID = re.compile(r"^run-(\d{4,})-(\d{8}T\d{6})$")


class RunStoreError(Exception):
    """A saved run that cannot be written or read back."""


def default_root() -> Path:
    """``~/.spacemissionstudio/runs``."""
    return Path.home() / ".spacemissionstudio" / "runs"


@dataclass
class SavedRun:
    """One saved run's ``run.json`` (everything but the arrays)."""

    run_id: str  # the folder name
    number: int  # "Run 7"
    scenario: dict  # Scenario.to_dict() as it ran
    epoch_utc: str
    finished: datetime
    cancelled: bool = False
    series: List[dict] = field(default_factory=list)  # {"name", "columns", "units"} in order
    provenance: Optional[dict] = None
    warnings: List[str] = field(default_factory=list)
    size_bytes: int = 0  # [byte] the folder on disk

    @property
    def scenario_name(self) -> str:
        return str(self.scenario.get("name", ""))


def _run_id(number: int, finished: datetime) -> str:
    return f"run-{number:04d}-{finished:%Y%m%dT%H%M%S}"


def _folder(root: Path, run_id: str) -> Path:
    """The folder of ``run_id``, refusing any name this module does not
    write (so nothing outside the store is ever read or deleted)."""
    if not _RUN_ID.match(run_id):
        raise RunStoreError(f"not a saved run's name: {run_id!r}")
    return Path(root) / run_id


def _folder_size(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.iterdir() if p.is_file())  # [byte]


def save(root: "str | Path", number: int, scenario: dict, result: ResultSet, epoch_utc: str,
         finished: datetime, cancelled: bool = False) -> SavedRun:
    """Write ``result`` and what produced it as run ``number``. Raises
    :class:`RunStoreError` (the folder is left out) when it cannot."""
    root = Path(root)
    run_id = _run_id(number, finished)
    final = _folder(root, run_id)
    temporary = root / f".{run_id}.partial"
    names = list(result.series)
    record = {
        "format_version": FORMAT_VERSION,
        "number": int(number),
        "scenario": scenario,
        "epoch_utc": epoch_utc or "",
        "finished": finished.isoformat(timespec="seconds"),
        "cancelled": bool(cancelled),
        "series": [{"name": name, "columns": [str(c) for c in result.series[name].columns],
                    "units": result.series[name].units} for name in names],
        "provenance": result.provenance.to_dict() if result.provenance is not None else None,
        "warnings": list(result.warnings),
    }
    arrays: Dict[str, np.ndarray] = {}
    for index, name in enumerate(names):
        arrays[f"t{index}"] = np.asarray(result.series[name].time_s, dtype=float)
        arrays[f"d{index}"] = np.asarray(result.series[name].data, dtype=float)
    try:
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
        (temporary / _RUN_JSON).write_text(json.dumps(record), encoding="utf-8")
        with open(temporary / _SERIES_NPZ, "wb") as handle:
            np.savez(handle, **arrays)
        if final.exists():
            shutil.rmtree(final)
        temporary.rename(final)
    except (OSError, TypeError, ValueError) as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        raise RunStoreError(f"could not save run {number} in {root}: {exc}") from exc
    return _saved_run(run_id, record, _folder_size(final))


def _saved_run(run_id: str, record: dict, size_bytes: int) -> SavedRun:
    if record.get("format_version") != FORMAT_VERSION:
        raise RunStoreError(f"{run_id}: format {record.get('format_version')!r}, this version reads "
                            f"{FORMAT_VERSION}")
    try:
        series = [{"name": str(s["name"]), "columns": [str(c) for c in s["columns"]], "units": str(s.get("units", ""))}
                  for s in record["series"]]
        scenario = record["scenario"]
        if not isinstance(scenario, dict):
            raise TypeError("the scenario is not an object")
        return SavedRun(run_id, int(record["number"]), scenario, str(record.get("epoch_utc", "")),
                        datetime.fromisoformat(str(record["finished"])), bool(record.get("cancelled", False)),
                        series, record.get("provenance"), [str(w) for w in record.get("warnings", [])],
                        size_bytes)
    except (KeyError, TypeError, ValueError) as exc:
        raise RunStoreError(f"{run_id}: {exc}") from exc


def _read_record(folder: Path) -> SavedRun:
    path = folder / _RUN_JSON
    try:
        if path.stat().st_size > MAX_RUN_JSON_BYTES:
            raise RunStoreError(f"{folder.name}: {_RUN_JSON} is larger than {MAX_RUN_JSON_BYTES} bytes")
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RunStoreError(f"{folder.name}: {exc}") from exc
    if not isinstance(record, dict):
        raise RunStoreError(f"{folder.name}: {_RUN_JSON} is not an object")
    return _saved_run(folder.name, record, _folder_size(folder))


def load_index(root: "str | Path") -> List[SavedRun]:
    """Every saved run under ``root``, oldest first; unreadable ones are
    skipped and logged."""
    root = Path(root)
    if not root.is_dir():
        return []
    runs = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not _RUN_ID.match(folder.name):
            continue
        try:
            runs.append(_read_record(folder))
        except RunStoreError as exc:
            logger.warning("Skipped a saved run that does not read back: %s", exc)
    return sorted(runs, key=lambda run: (run.number, run.finished))


def _provenance(record: Optional[dict]) -> Optional[RunProvenance]:
    if not isinstance(record, dict):
        return None
    known = {f.name for f in fields(RunProvenance)}
    try:
        return RunProvenance(**{key: value for key, value in record.items() if key in known})
    except TypeError:
        return None


def load_result(root: "str | Path", saved: SavedRun) -> ResultSet:
    """The :class:`ResultSet` of ``saved``, read from its folder."""
    folder = _folder(Path(root), saved.run_id)
    result = ResultSet(saved.scenario_name, provenance=_provenance(saved.provenance), warnings=list(saved.warnings))
    try:
        with np.load(folder / _SERIES_NPZ, allow_pickle=False) as arrays:
            for index, entry in enumerate(saved.series):
                result.add(TimeSeries(entry["name"], arrays[f"t{index}"], tuple(entry["columns"]),
                                      arrays[f"d{index}"], entry["units"]))
    except (OSError, EOFError, KeyError, ValueError, zipfile.BadZipFile, ResultsError) as exc:
        raise RunStoreError(f"{saved.run_id}: {exc}") from exc
    return result


def delete(root: "str | Path", run_id: str) -> None:
    """Remove one saved run (nothing else: the name must be a run's)."""
    folder = _folder(Path(root), run_id)
    if folder.is_dir():
        shutil.rmtree(folder)


def prune(root: "str | Path", keep: int = MAX_SAVED_RUNS, max_bytes: int = MAX_STORE_BYTES) -> List[str]:
    """Delete the oldest runs until at most ``keep`` remain and they take
    at most ``max_bytes``; the newest run always stays. Returns the
    deleted runs' names."""
    runs = load_index(root)
    deleted = []
    while len(runs) > 1 and (len(runs) > keep or sum(r.size_bytes for r in runs) > max_bytes):
        oldest = runs.pop(0)
        try:
            delete(root, oldest.run_id)
            deleted.append(oldest.run_id)
        except OSError as exc:
            logger.warning("Could not delete the saved run %s: %s", oldest.run_id, exc)
            break
    return deleted
