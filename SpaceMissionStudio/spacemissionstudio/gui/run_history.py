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

In the main window (``background=True``, UI overhaul M5a) the earlier
sessions' runs are read, and each run is saved and the store pruned, in a
worker thread, so the end of a run does not wait for the disk. A run is
listed at once; :attr:`RunHistory.saved` says when it is on disk.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from ..engine import run_store
from ..engine.results import ResultSet

logger = logging.getLogger(__name__)

MAX_RUNS = 5  # runs whose series stay in memory (all of them without a store)
SAVE_DELAY_MS = 1000  # [ms] after a run ends, its save starts (its views are shown by then)


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


class _LoadWorker(QThread):
    """The store's index (:func:`run_store.load_index`), read off the GUI thread."""

    done = Signal(list)  # [run_store.SavedRun]

    def __init__(self, root: Path, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._root = root
        self.index: list = []  # what it read (also for a wait that does not wait for done)

    def run(self) -> None:
        try:
            self.index = run_store.load_index(self._root)
        except Exception:  # noqa: BLE001 -- no earlier runs listed, never a crashed thread
            logger.exception("Could not read the saved runs")
        self.done.emit(self.index)


class _SaveWorker(QThread):
    """One run saved, then the store pruned, off the GUI thread."""

    done = Signal(object, object, str, list)  # record, SavedRun or None, the error ("" if saved), pruned run ids

    def __init__(self, root: Path, record: RunRecord, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._root, self.record = root, record
        # What it did (also for a wait that does not wait for done).
        self.result: tuple = (record, None, "", [])

    def run(self) -> None:
        record, saved, error = self.record, None, ""
        try:
            saved = run_store.save(self._root, record.number, record.scenario, record._result, record.epoch_utc,
                                   record.finished, record.cancelled)
        except run_store.RunStoreError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001 -- the run stays in memory, never a crashed thread
            logger.exception("Saving the run failed")
            error = f"Could not save {record.name}: {exc}"
        try:
            deleted = list(run_store.prune(self._root))
        except Exception:  # noqa: BLE001 -- pruning is tidying up: the next save tries again
            logger.exception("Pruning the saved runs failed")
            deleted = []
        self.result = (record, saved, error, deleted)
        self.done.emit(*self.result)


class RunHistory(QObject):
    """The runs kept. ``background``: read the store and save each run in a
    worker thread (the main window); else on the spot (tests, tools)."""

    loaded = Signal()  # the earlier sessions' runs are listed
    saved = Signal(object)  # a run's save ended (its ``saved`` is set, or ``last_save_error`` says why not)

    def __init__(self, max_runs: int = MAX_RUNS, store_root: "Optional[str | Path]" = None,
                 background: bool = False, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.runs: List[RunRecord] = []
        self._count = 0
        self._max_runs = max_runs
        self.store_root = Path(store_root) if store_root is not None else None
        self.last_save_error = ""  # why the last run could not be saved, if it could not
        self._background = background
        self._loader: Optional[_LoadWorker] = None
        self._saver: Optional[_SaveWorker] = None
        self._to_save: List[RunRecord] = []
        if self.store_root is None:
            return
        if background:
            self._loader = _LoadWorker(self.store_root, self)
            self._loader.done.connect(self._on_loaded)
            self._loader.start()
        else:
            self._list(run_store.load_index(self.store_root))

    def _list(self, index: list) -> None:
        earlier = [RunRecord(saved.number, saved.scenario, None, saved.epoch_utc, saved.finished, saved.cancelled,
                             saved, earlier_session=True, loader=self._load) for saved in index]
        self.runs[:0] = earlier  # before any run of this session
        self._count = max([self._count] + [r.number for r in self.runs])

    def _on_loaded(self, index: list) -> None:
        loader, self._loader = self._loader, None
        if loader is not None:
            loader.wait()
            loader.deleteLater()
        self._list(index)
        self.loaded.emit()

    @property
    def loading(self) -> bool:
        """The earlier sessions' runs are being read."""
        return self._loader is not None

    def wait_loaded(self) -> None:
        """Block until the earlier sessions' runs are listed (a run kept
        before then must number on from them)."""
        loader = self._loader
        if loader is None:
            return
        loader.done.disconnect(self._on_loaded)  # its queued done() would list them twice
        loader.wait()
        self._on_loaded(loader.index)

    def _load(self, record: RunRecord) -> ResultSet:
        return run_store.load_result(self.store_root, record.saved)

    def add(self, scenario: dict, result: ResultSet, epoch_utc: str, cancelled: bool = False,
            finished: Optional[datetime] = None) -> RunRecord:
        self.wait_loaded()
        self._count += 1
        finished = (finished or datetime.now()).replace(microsecond=0)
        record = RunRecord(self._count, scenario, result, epoch_utc, finished, cancelled, loader=self._load)
        self.runs.append(record)
        self.last_save_error = ""
        if self.store_root is None:
            del self.runs[:-self._max_runs]
            return record
        if self._background:
            self._to_save.append(record)
            # Started once the run's views are shown (M6b): the save's zip
            # writing shares the interpreter with the GUI thread, and doubled
            # the end of a run's own time when it ran beside it.
            QTimer.singleShot(SAVE_DELAY_MS, self, self._save_next)
            return record
        saved, error = None, ""
        try:
            saved = run_store.save(self.store_root, record.number, scenario, result, epoch_utc, finished, cancelled)
        except run_store.RunStoreError as exc:
            error = str(exc)
        self._apply_save(record, saved, error, list(run_store.prune(self.store_root)))
        return record

    def _save_next(self) -> None:
        if self._saver is not None or not self._to_save:
            return  # one at a time: the next starts when this one ends
        self._saver = _SaveWorker(self.store_root, self._to_save.pop(0), self)
        self._saver.done.connect(self._on_saved)
        self._saver.start()

    def _on_saved(self, record: RunRecord, saved, error: str, deleted: list) -> None:
        saver, self._saver = self._saver, None
        if saver is not None:
            saver.wait()
            saver.deleteLater()
        self._apply_save(record, saved, error, deleted)
        self.saved.emit(record)
        self._save_next()

    def _apply_save(self, record: RunRecord, saved, error: str, deleted: list) -> None:
        record.saved = saved
        self.last_save_error = error
        if error:
            logger.warning("%s", error)
        deleted = set(deleted)
        self.runs = [r for r in self.runs if r.saved is None or r.saved.run_id not in deleted]
        unsaved = [r for r in self.runs if r.saved is None]  # only in memory: the last few
        pending = set(id(r) for r in self._to_save)  # not saved yet, not forgotten
        self.runs = [r for r in self.runs if r.saved is not None or r in unsaved[-self._max_runs:]
                     or id(r) in pending]
        in_memory = [r for r in self.runs if r.in_memory]
        for older in in_memory[:-self._max_runs]:
            older.forget_series()

    def is_saving(self, record: RunRecord) -> bool:
        """``record`` is being saved, or waits to be."""
        return record in self._to_save or (self._saver is not None and self._saver.record is record)

    @property
    def saving(self) -> bool:
        """A run is being saved, or waits to be."""
        return self._saver is not None or bool(self._to_save)

    def wait_for_saves(self) -> None:
        """Save every run waiting now, on this thread (closing, tests)."""
        saver = self._saver
        if saver is not None:
            saver.done.disconnect(self._on_saved)  # its queued done() would apply it twice
            saver.wait()
            self._saver = None
            saver.deleteLater()
            self._apply_save(*saver.result)
            self.saved.emit(saver.record)
        while self._to_save:
            record = self._to_save.pop(0)
            saved, error = None, ""
            try:
                saved = run_store.save(self.store_root, record.number, record.scenario, record._result,
                                       record.epoch_utc, record.finished, record.cancelled)
            except run_store.RunStoreError as exc:
                error = str(exc)
            self._apply_save(record, saved, error, list(run_store.prune(self.store_root)))
            self.saved.emit(record)

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
