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
"""

from __future__ import annotations

import logging
import logging.handlers
import multiprocessing
import queue
from pathlib import Path

_logger = logging.getLogger(__name__)

_POLL_S = 0.2  # [s] how often the waiting thread checks that the child is alive
_LAST_RESULT_S = 2.0  # [s] how long to wait for a result after the child has exited


class BatchProcessError(Exception):
    """The batch did not end with a result: the child raised something other
    than :class:`engine.monte_carlo.MonteCarloError`, or ended without one."""


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
           result_queue) -> None:
    """The child process: the batch, then one ``(kind, value)`` result."""
    root = logging.getLogger()
    root.handlers[:] = [logging.handlers.QueueHandler(log_queue)]
    root.setLevel(logging.INFO)
    try:
        from ..engine.monte_carlo import MonteCarloError, run_monte_carlo

        failures = run_monte_carlo(scenario, mc_config, archive_dir, allow_scripts=allow_scripts,
                                   overwrite=overwrite)
    except MonteCarloError as exc:
        result_queue.put(("error", str(exc)))
    except (Exception, SystemExit) as exc:  # noqa: BLE001 -- report ANY failure (Basilisk's exit() too) to the GUI
        logging.getLogger(__name__).exception("Monte Carlo batch failed")
        result_queue.put(("failed", failure_text(exc)))
    else:
        result_queue.put(("ok", [int(index) for index in failures]))


def run_batch(scenario, mc_config, archive_dir: str | Path, allow_scripts: bool = False,
              overwrite: bool = False) -> list[int]:
    """:func:`engine.monte_carlo.run_monte_carlo` in a child process: the
    indices of the failed runs. Raises ``MonteCarloError`` with the batch's
    own message, or :class:`BatchProcessError`. Blocks until the batch ends,
    so call it from a worker thread."""
    from ..engine.monte_carlo import MonteCarloError

    context = multiprocessing.get_context("spawn")  # a fresh interpreter: no Qt state forked into it
    log_queue = context.Queue()
    result_queue = context.Queue()
    listener = logging.handlers.QueueListener(log_queue, _ToLocalLoggers())
    listener.start()
    process = context.Process(target=_child, name="spacemissionstudio-monte-carlo",
                              args=(scenario, mc_config, str(archive_dir), allow_scripts, overwrite, log_queue,
                                    result_queue))
    result = None
    try:
        process.start()
        while result is None:
            try:
                result = result_queue.get(timeout=_POLL_S)
            except queue.Empty:
                if not process.is_alive():
                    try:  # the result can arrive just after the child exits
                        result = result_queue.get(timeout=_LAST_RESULT_S)
                    except queue.Empty:
                        break
        process.join()
    finally:
        listener.stop()
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
