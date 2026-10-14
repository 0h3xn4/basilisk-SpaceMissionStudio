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
"""The runs kept for comparison (UX/UI guidelines, "run comparison";
docs/ux-audit.md U-33, decision 5: runs are saved to disk).

With a store (:mod:`engine.run_store`, the main window's
``~/.spacemissionstudio/runs``) every finished or cancelled run is saved
as it ends, and the runs of earlier sessions are listed again at start-up,
numbered on from the last one ("Run 8" after "Run 7" of yesterday). Only
the last :data:`MAX_RUNS` keep their series in memory; an older run reads
its series back from disk the first time it is compared. Without a store
(tests, or a store that cannot be written) the runs stay in memory, the
last :data:`MAX_RUNS` of them.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from ..engine import run_store
from ..engine.results import ResultSet

logger = logging.getLogger(__name__)

MAX_RUNS = 5  # runs whose series stay in memory (all of them without a store)


class RunRecord:
    """One run: what it ran, when, and its series (read from disk on first use)."""

    def __init__(self, number: int, scenario: dict, result: Optional[ResultSet], epoch_utc: str,
                 finished: datetime, cancelled: bool = False, saved: Optional[run_store.SavedRun] = None,
                 earlier_session: bool = False, loader: Optional[Callable[["RunRecord"], ResultSet]] = None):
        self.number = number  # 1 for the first run kept
        self.scenario = scenario  # Scenario.to_dict() as it ran
        self.epoch_utc = epoch_utc
        self.finished = finished
        self.cancelled = cancelled
        self.saved = saved  # its record on disk, None while it is only in memory
        self.earlier_session = earlier_session  # listed from the store at start-up
        self._result = result
        self._loader = loader

    @property
    def result(self) -> Optional[ResultSet]:
        """The run's series, read from disk if they are not in memory (None
        when they cannot be read back; the log says why)."""
        if self._result is None and self._loader is not None:
            try:
                self._result = self._loader(self)
            except run_store.RunStoreError as exc:
                logger.warning("Could not read the saved run back: %s", exc)
        return self._result

    @property
    def in_memory(self) -> bool:
        return self._result is not None

    def forget_series(self) -> None:
        """Drop the series from memory; they stay on disk (only when saved)."""
        if self.saved is not None and self._loader is not None:
            self._result = None

    @property
    def name(self) -> str:
        """ "Run 2, 12:19" (a run of an earlier session: "Run 2, 13 Oct 12:19"):
        how the run is named in the status chip, the plots and Compare (U-22)."""
        when = f"{self.finished:%d %b %H:%M}" if self.earlier_session else f"{self.finished:%H:%M}"
        return f"Run {self.number}, {when}"

    @property
    def label(self) -> str:
        name = self.scenario.get("name", "")
        when = f"{self.finished:%d %b %H:%M}" if self.earlier_session else f"{self.finished:%H:%M}"
        return f"Run {self.number} ({when}{', cancelled' if self.cancelled else ''}): {name}"


class RunHistory:
    def __init__(self, max_runs: int = MAX_RUNS, store_root: "Optional[str | Path]" = None):
        self.runs: List[RunRecord] = []
        self._count = 0
        self._max_runs = max_runs
        self.store_root = Path(store_root) if store_root is not None else None
        self.last_save_error = ""  # why the last run could not be saved, if it could not
        if self.store_root is not None:
            for saved in run_store.load_index(self.store_root):
                self.runs.append(RunRecord(saved.number, saved.scenario, None, saved.epoch_utc, saved.finished,
                                           saved.cancelled, saved, earlier_session=True, loader=self._load))
            self._count = max((r.number for r in self.runs), default=0)

    def _load(self, record: RunRecord) -> ResultSet:
        return run_store.load_result(self.store_root, record.saved)

    def add(self, scenario: dict, result: ResultSet, epoch_utc: str, cancelled: bool = False,
            finished: Optional[datetime] = None) -> RunRecord:
        self._count += 1
        finished = (finished or datetime.now()).replace(microsecond=0)
        record = RunRecord(self._count, scenario, result, epoch_utc, finished, cancelled, loader=self._load)
        self.runs.append(record)
        self.last_save_error = ""
        if self.store_root is None:
            del self.runs[:-self._max_runs]
            return record
        try:
            record.saved = run_store.save(self.store_root, record.number, scenario, result, epoch_utc, finished,
                                          cancelled)
        except run_store.RunStoreError as exc:
            self.last_save_error = str(exc)
            logger.warning("%s", exc)
        deleted = set(run_store.prune(self.store_root))
        self.runs = [r for r in self.runs if r.saved is None or r.saved.run_id not in deleted]
        unsaved = [r for r in self.runs if r.saved is None]  # only in memory: the last few
        self.runs = [r for r in self.runs if r.saved is not None or r in unsaved[-self._max_runs:]]
        in_memory = [r for r in self.runs if r.in_memory]
        for older in in_memory[:-self._max_runs]:
            older.forget_series()
        return record

    def delete(self, record: RunRecord) -> None:
        """Forget ``record`` and delete it from disk."""
        if record.saved is not None and self.store_root is not None:
            run_store.delete(self.store_root, record.saved.run_id)
        self.runs = [r for r in self.runs if r is not record]

    @property
    def next_number(self) -> int:
        """The number the next run kept will get: "Run 3" (U-22)."""
        return self._count + 1

    def latest(self) -> Optional[RunRecord]:
        return self.runs[-1] if self.runs else None

    def find(self, number: int) -> Optional[RunRecord]:
        return next((r for r in self.runs if r.number == number), None)
