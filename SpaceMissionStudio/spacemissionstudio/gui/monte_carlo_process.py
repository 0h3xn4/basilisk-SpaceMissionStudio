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

"""The GUI's Monte Carlo batch, run in a child process.

Basilisk's ``MonteCarlo.Controller`` calls ``signal.signal()`` at the start
of every case, which Python allows only on a process's main thread. With
``thread_count`` 1 the controller runs each case in the calling process, so
called from the GUI's worker ``QThread`` every case failed with "signal only
works in main thread of the main interpreter". :func:`run_batch` runs
:func:`engine.monte_carlo.run_monte_carlo` in a spawned process instead,
where it runs on that process's main thread, as ``spacemissionstudio
monte-carlo`` does. With ``thread_count`` > 1 the controller's own process
pool starts from that child, as it did from the GUI process before.

The child's log records come back through a queue to the GUI process's
loggers (so the Log view and the log file get them as before); its stdout
and stderr are the GUI's. Importing this module imports no Qt and no
Basilisk: the child imports only what the batch needs.

A batch can be cancelled (audit G3): the controller has no way to stop
part way, so a thread in the child waits for a cancel event, then ends the
controller's own processes (its pool, data writer and manager) and the
child. The cases finished by then stay in the archive folder, and a second,
short child writes their summary for the Monte Carlo view.
"""

from __future__ import annotations

import logging
import logging.handlers
import multiprocessing
import os
import queue
import threading
from pathlib import Path

_logger = logging.getLogger(__name__)

_POLL_S = 0.2  # [s] how often the waiting thread checks that the child is alive
_LAST_RESULT_S = 2.0  # [s] how long to wait for a result after the child has exited
_CANCEL_WAIT_S = 15.0  # [s] how long a cancelled child has to end its processes before it is terminated
_CANCELLED_EXIT = 3  # the child's exit code when it was cancelled


class BatchProcessError(Exception):
    """The batch did not end with a result: the child raised something other
    than :class:`engine.monte_carlo.MonteCarloError`, or ended without one."""


class BatchCancelled(Exception):
    """The batch was cancelled; ``finished`` cases had ended by then (their
    files, and a summary when there is any, are in the archive folder)."""

    def __init__(self, finished: int) -> None:
        super().__init__(f"cancelled after {finished} finished case(s)")
        self.finished = finished


def _stop_on(cancel_event) -> None:
    """In the child: once ``cancel_event`` is set, end the processes the
    controller started from this one, then this process."""
    cancel_event.wait()
    children = multiprocessing.active_children()
    for child in children:
        child.terminate()
    for child in children:
        child.join(5.0)
    os._exit(_CANCELLED_EXIT)


def failure_text(exc: BaseException) -> str:
    """What a worker reports for ``exc``. Basilisk's device factories call
    ``exit()`` (``SystemExit``) on settings they refuse, printing the reason
    first; ``str()`` of that is only the exit status."""
    if isinstance(exc, SystemExit):
        return (f"Basilisk stopped the run (exit status {exc.code}) on a setting it refuses; its reason is "
                "printed in the terminal and the log file")
    return str(exc) or type(exc).__name__


class _ToLocalLoggers(logging.Handler):
    """Hands each record from the child to the logger of the same name here."""

    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


def _child(scenario, mc_config, archive_dir: str, allow_scripts: bool, overwrite: bool, log_queue,
           result_queue, cancel_event=None, scenario_file: dict | None = None) -> None:
    """The child process: the batch, then one ``(kind, value)`` result."""
    root = logging.getLogger()
    root.handlers[:] = [logging.handlers.QueueHandler(log_queue)]
    root.setLevel(logging.INFO)
    if cancel_event is not None:
        threading.Thread(target=_stop_on, args=(cancel_event,), name="cancel", daemon=True).start()
    try:
        from ..engine.monte_carlo import MonteCarloError, run_monte_carlo

        failures = run_monte_carlo(scenario, mc_config, archive_dir, allow_scripts=allow_scripts,
                                   overwrite=overwrite, scenario_file=scenario_file)
    except MonteCarloError as exc:
        result_queue.put(("error", str(exc)))
    except (Exception, SystemExit) as exc:  # noqa: BLE001 -- report ANY failure (Basilisk's exit() too) to the GUI
        logging.getLogger(__name__).exception("Monte Carlo batch failed")
        result_queue.put(("failed", failure_text(exc)))
    else:
        result_queue.put(("ok", [int(index) for index in failures]))


def _summary_child(scenario, archive_dir: str, num_runs: int) -> None:
    """A cancelled batch's summary, from the cases it finished (in a child,
    as the batch's own: the run files are pickles, read only by the process
    kind that had them written, security analysis S-04)."""
    from ..engine import monte_carlo, monte_carlo_results

    batch = monte_carlo.collect_batch(scenario, archive_dir, num_runs, [])
    batch.failed = []  # the cases not finished were stopped, not failed: the controller's own list is gone
    if batch.runs:
        monte_carlo_results.save(batch, archive_dir)


def _summarized_runs(archive_dir) -> int:
    """How many finished cases a cancelled batch's summary holds (0 when
    none finished, or it could not be written)."""
    from ..engine import monte_carlo_results

    try:
        return len(monte_carlo_results.load(archive_dir).runs)
    except monte_carlo_results.MonteCarloResultsError:
        return 0


def run_batch(scenario, mc_config, archive_dir: str | Path, allow_scripts: bool = False,
              overwrite: bool = False, should_cancel=None, scenario_file: dict | None = None) -> list[int]:
    """:func:`engine.monte_carlo.run_monte_carlo` in a child process: the
    indices of the failed runs (``scenario_file`` as there). Raises
    ``MonteCarloError`` with the batch's own message, or
    :class:`BatchProcessError`; :class:`BatchCancelled` when
    ``should_cancel()`` turned True (checked every 0.2 s). Blocks until the
    batch ends, so call it from a worker thread."""
    from ..engine.monte_carlo import MonteCarloError

    context = multiprocessing.get_context("spawn")  # a fresh interpreter: no Qt state forked into it
    log_queue = context.Queue()
    result_queue = context.Queue()
    cancel_event = context.Event()
    listener = logging.handlers.QueueListener(log_queue, _ToLocalLoggers())
    listener.start()
    process = context.Process(target=_child, name="spacemissionstudio-monte-carlo",
                              args=(scenario, mc_config, str(archive_dir), allow_scripts, overwrite, log_queue,
                                    result_queue, cancel_event, scenario_file))
    result = None
    cancelled = False
    try:
        process.start()
        while result is None:
            if should_cancel is not None and should_cancel() and not cancelled:
                cancelled = True
                cancel_event.set()
                process.join(_CANCEL_WAIT_S)
                if process.is_alive():
                    process.terminate()
                break
            try:
                result = result_queue.get(timeout=_POLL_S)
            except queue.Empty:
                if not process.is_alive():
                    try:  # the result can arrive just after the child exits
                        result = result_queue.get(timeout=_LAST_RESULT_S)
                    except queue.Empty:
                        break
        process.join()
        if cancelled:
            summary = context.Process(target=_summary_child, name="spacemissionstudio-monte-carlo-summary",
                                      args=(scenario, str(archive_dir), mc_config.num_runs))
            summary.start()
            summary.join()
    finally:
        listener.stop()
    if cancelled:
        finished = _summarized_runs(archive_dir)
        _logger.info("Monte Carlo batch cancelled: %d case(s) finished", finished)
        raise BatchCancelled(finished)
    if result is None:
        _logger.error("The Monte Carlo process ended without a result (exit code %s)", process.exitcode)
        raise BatchProcessError(f"The Monte Carlo process ended unexpectedly (exit code {process.exitcode}); "
                                "the terminal and the log file have its output")
    kind, value = result
    if kind == "ok":
        return value
    if kind == "error":
        raise MonteCarloError(value)
    raise BatchProcessError(value)
