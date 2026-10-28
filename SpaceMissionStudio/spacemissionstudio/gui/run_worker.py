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

"""RunWorker/MonteCarloWorker: run :class:`engine.service.SimulationService`/
:func:`engine.monte_carlo.run_monte_carlo` on a background ``QThread`` (the
batch itself in a child process, see :mod:`gui.monte_carlo_process`) so a
(potentially long) propagation or batch never freezes the GUI's event
loop. Importing ``engine.service``/``engine.monte_carlo`` needs a
Basilisk build; when it's missing, each worker reports that clearly via
its own ``failed`` signal -- there is only one error-reporting path for
the caller (``MainWindow``) to handle per worker, whether the problem is
"no Basilisk", a bad scenario, or a Basilisk-internal error.

``RunWorker.run()`` dispatches on ``scenario.mission_sequence`` exactly
like ``cli.py``'s ``cmd_run()`` does: a non-empty sequence runs through
``engine.mission_engine.MissionEngine`` instead of
``SimulationService.run()``/``run_live()`` directly, and ``finished_ok``
always carries both the :class:`engine.results.ResultSet` and (when a
``mission_sequence`` ran) its :class:`engine.results.CommandSummary`, or
``None`` for the summary otherwise.

**Abort a running simulation** (direct user feedback: "there should be
an option to abort a running simulation, if needed, without breaking
the tool"): :meth:`RunWorker.request_cancel` sets a
:class:`threading.Event`, checked cooperatively between simulation
chunks (``SimulationService.run_live``'s ``should_cancel``) or between
mission_sequence commands (``MissionEngine``'s ``should_cancel``) --
never via ``QThread.terminate()`` or any other forced kill, which could
leave Basilisk's C++ simulation state mid-mutation and is exactly the
kind of "breaking the tool" this was asked to avoid. Cancellation
therefore always takes effect at the next such checkpoint, not
instantly (there is no hook into the middle of a single
``ExecuteSimulation()`` call -- see both ``should_cancel`` docstrings),
and a cancelled run reports the ``cancelled`` signal with whatever
partial ``ResultSet``/``CommandSummary`` had been produced so far,
rather than silently discarding it.

The non-mission_sequence path now ALWAYS runs through
``SimulationService.run_live()`` (never the plain, non-chunked
``run()``), specifically so it's always cancellable regardless of the
"Live Plot" toggle -- ``self.live`` now only controls whether
``progress`` is actually emitted (i.e. whether the plot redraws as it
goes), not whether the run is chunked at all. ``run_live()``'s own
docstring already notes ``_LIVE_DEFAULT_FRAMES`` (60) bounds this to a
small, fixed number of extra ``ExecuteSimulation()`` calls regardless
of run length -- negligible next to the actual simulated work, so this
applies with no live plot watching just as safely as with one.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .. import output_provenance
from ..schema.command import runs_sequence
from .monte_carlo_process import failure_text, run_batch
from ..schema.scenario import MonteCarloConfig, Scenario

_logger = logging.getLogger(__name__)


class RunWorker(QThread):
    finished_ok = Signal(object, object)  # engine.results.ResultSet, Optional[engine.results.CommandSummary]
    failed = Signal(str)
    progress = Signal(object, float)  # engine.results.ResultSet (partial), fraction_complete in [0, 1]
    cancelled = Signal(object, object)  # engine.results.ResultSet (partial), Optional[engine.results.CommandSummary]
    sil_report = Signal(object, str)  # sil.report.SilReport, and the failure message ("" when it ran to the end)
    # What the run is doing ("Propagating: day 0.4 of 1", "Step 2 of 5: ..."), and how far it is in [0, 1]:
    # sent for every run, with Live plot on or off, for the progress strip (docs/ux-audit.md U-19).
    phase = Signal(str)
    fraction = Signal(float)

    def __init__(self, scenario: Scenario, vizard_request: object | None = None, live: bool = False,
                 parent=None, allow_scripts: bool = False, sil: tuple | None = None):
        super().__init__(parent)
        self.scenario = scenario
        # (spacecraft name, sil.runner.SilOptions): run that spacecraft's
        # flight software as an external program in the loop (sil.runner).
        self.sil = sil
        # True only after the user confirmed the scenario's script_block
        # code (MainWindow.on_run; SRS-S-03).
        self.allow_scripts = allow_scripts
        self.vizard_request = vizard_request  # engine.vizard.VizardRequest, or None
        # Whether `progress` is actually emitted as the run goes (driving
        # a live-updating plot -- see MainWindow.on_run()/the "Live plot"
        # toggle). No longer decides HOW the run executes -- see this
        # module's own docstring on why the non-mission_sequence path is
        # always chunked via run_live() now, live or not. Qt signals
        # emitted from a QThread are queued to the receiver's own thread
        # automatically (the default AutoConnection), so this is safe to
        # connect straight to GUI-thread slots without extra locking.
        self.live = live
        self._cancel_requested = threading.Event()

    def request_cancel(self) -> None:
        """Thread-safe -- called from the GUI thread while this worker's
        run() is executing on its own thread (see this module's own
        docstring for the cooperative-cancellation design and why a
        forced kill was never an option here).
        """
        self._cancel_requested.set()

    def _should_cancel(self) -> bool:
        return self._cancel_requested.is_set()

    def run(self) -> None:
        try:
            from ..engine.service import SimulationCancelled, SimulationService
        except ImportError as exc:
            self.failed.emit(
                f"Basilisk is not installed/built ({exc}) -- cannot run a simulation until it is. "
                f"See SpaceMissionStudio/README.md."
            )
            return
        try:
            command_summary = None
            self.phase.emit("Building the simulation in Basilisk")
            if self.sil is not None:
                self._run_sil()
                return
            service = SimulationService(self.scenario, vizard_request=self.vizard_request)
            if runs_sequence(self.scenario.mission_sequence):
                from ..engine.mission_engine import MissionEngine, MissionEngineCancelled

                try:
                    result, command_summary = MissionEngine(
                        self.scenario, service=service, should_cancel=self._should_cancel,
                        allow_scripts=self.allow_scripts, on_step=self._on_step,
                    ).run()
                except MissionEngineCancelled as exc:
                    self.cancelled.emit(exc.partial_result, exc.summary)
                    return
            else:
                def on_progress(partial, fraction):
                    self._report(fraction, "Propagating")
                    if self.live:
                        self.progress.emit(partial, fraction)

                try:
                    result = service.run_live(on_progress, should_cancel=self._should_cancel)
                except SimulationCancelled as exc:
                    self.cancelled.emit(exc.partial_result, None)
                    return
        except (Exception, SystemExit) as exc:  # noqa: BLE001 -- surface ANY failure (Basilisk's exit() too) to the GUI, never end the worker silently
            # Full traceback to the log file/terminal -- see
            # logging_setup's own module docstring for why str(exc) alone
            # (all the GUI's own error dialog ever shows) can be the ONLY
            # information anywhere about a genuinely unexpected failure,
            # with nothing else to go on, unless this is logged here.
            _logger.exception("RunWorker failed")
            self.failed.emit(failure_text(exc))
            return
        self.finished_ok.emit(result, command_summary)

    def _report(self, fraction: float, doing: str) -> None:
        """Send the phase ("Propagating: day 0.4 of 1") and the fraction."""
        total_days = float(self.scenario.sim_settings.duration_days)  # [day]
        decimals = 1 if total_days >= 10.0 else 2  # a 1-day run moves in hundredths of a day
        self.phase.emit(f"{doing}: day {fraction * total_days:.{decimals}f} of {total_days:g}")
        self.fraction.emit(float(fraction))

    def _on_step(self, number: int, total: int, command) -> None:
        """A Mission Sequence step starts: "Step 2 of 5: Burn 5 m/s on sat-1"."""
        from .mission_sequence_editor import step_sentence

        self.phase.emit(f"Step {number} of {total}: {step_sentence(command)}")
        self.fraction.emit((number - 1) / total if total else 0.0)

    def _run_sil(self) -> None:
        from ..sil.contract import SilError
        from ..sil.runner import SilCancelled, SilRunError, run_sil

        name, options = self.sil

        def on_progress(partial, fraction):
            self._report(fraction, f"Propagating with {name}'s flight software in the loop")
            if self.live:
                self.progress.emit(partial, fraction)

        try:
            result, report = run_sil(self.scenario, name, options, vizard_request=self.vizard_request,
                                     on_progress=on_progress, should_cancel=self._should_cancel)
        except SilCancelled as exc:
            self.sil_report.emit(exc.report, "")
            self.cancelled.emit(exc.partial_result, None)
            return
        except SilRunError as exc:
            if exc.report is not None:
                self.sil_report.emit(exc.report, str(exc))
            self.failed.emit(f"SIL run failed: {exc}")
            return
        except SilError as exc:
            self.failed.emit(f"SIL run failed: {exc}")
            return
        self.sil_report.emit(report, "")
        self.finished_ok.emit(result, None)


class MonteCarloWorker(QThread):
    finished_ok = Signal(list)  # list[int] of failed run indices (empty == all succeeded)
    failed = Signal(str)

    def __init__(self, scenario: Scenario, mc_config: MonteCarloConfig, archive_dir: Path, parent=None,
                 allow_scripts: bool = False, overwrite: bool = False):
        super().__init__(parent)
        self.scenario = scenario
        self.mc_config = mc_config
        self.archive_dir = archive_dir
        self.allow_scripts = allow_scripts  # the user agreed to the Mission Sequence's script blocks
        self.overwrite = overwrite  # the user agreed to replace an earlier batch in archive_dir

    def run(self) -> None:
        try:
            from ..engine.monte_carlo import MonteCarloError
        except ImportError as exc:
            self.failed.emit(
                f"Basilisk is not installed/built ({exc}) -- cannot run Monte Carlo until it is. "
                f"See SpaceMissionStudio/README.md."
            )
            return
        try:
            # In a child process: Basilisk's controller needs a main thread
            # (gui.monte_carlo_process).
            failures = run_batch(self.scenario, self.mc_config, self.archive_dir,
                                 allow_scripts=self.allow_scripts, overwrite=self.overwrite)
            output_provenance.write_sidecar(Path(self.archive_dir) / "archive",
                                            output_provenance.scenario_record(self.scenario))
        except MonteCarloError as exc:
            self.failed.emit(str(exc))
            return
        except (Exception, SystemExit) as exc:  # noqa: BLE001 -- surface ANY failure (Basilisk's exit() too) to the GUI, never end the worker silently
            _logger.exception("MonteCarloWorker failed")
            self.failed.emit(failure_text(exc))
            return
        self.finished_ok.emit(failures)
