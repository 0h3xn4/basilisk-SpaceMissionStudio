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

"""The reference data inventory read in a child process (UI overhaul M9).

:func:`engine.reference_data.inventory` imports Basilisk and parses the
space-weather file: about 1.5 s. In the GUI process, even on a worker
thread, it held the interpreter for most of that time (importing compiled
modules does not let other threads run), so the window stalled for up to
0.7 s at a time just after it appeared. :class:`InventoryReader` runs it
in a spawned process instead, which shares nothing with the window.
Importing this module imports no Qt and no Basilisk.
"""

from __future__ import annotations

import multiprocessing
import queue

_POLL_S = 0.1  # [s] how often the waiting thread checks for a result or a stop


def _child(result_queue) -> None:
    from .. import dependencies
    from ..engine import reference_data

    # The Basilisk version too: asking for it imports Basilisk, which on
    # the GUI thread took 0.7 s once the files had arrived.
    result_queue.put((reference_data.inventory(), dependencies.basilisk_version()))


class InventoryReader:
    """One read of the inventory in a child process: :meth:`read` blocks
    (call it from a worker thread) until (the files, the Basilisk version)
    arrive, the child ends, or :meth:`stop` ends it; None then."""

    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")  # a fresh interpreter: no Qt state in it
        self._process = None
        self._stopped = False

    def read(self) -> tuple | None:
        result_queue = self._context.Queue()
        self._process = self._context.Process(target=_child, name="spacemissionstudio-reference-data",
                                              args=(result_queue,), daemon=True)
        self._process.start()
        try:
            while not self._stopped:
                try:
                    return result_queue.get(timeout=_POLL_S)
                except queue.Empty:
                    if not self._process.is_alive():
                        try:  # the result can arrive just after the child exits
                            return result_queue.get(timeout=1.0)
                        except queue.Empty:
                            return None
            return None
        finally:
            if self._process.is_alive():
                self._process.terminate()  # it only reads files: nothing is left half-written
            self._process.join()

    def stop(self) -> None:
        """End the read (the window is closing)."""
        self._stopped = True
