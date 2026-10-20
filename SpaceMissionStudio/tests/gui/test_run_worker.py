"""Tests for gui.run_worker.RunWorker.

Genuinely exercises the no-Basilisk path in this development sandbox
through a real background QThread (see test_kernel_status_widget.py's
docstring for the same point about kernel status).
"""

import importlib.util

import pytest

pytestmark = pytest.mark.requires_gui

_BASILISK_AVAILABLE = importlib.util.find_spec("Basilisk") is not None


def _load_two_body_scenario():
    from pathlib import Path

    from spacemissionstudio.schema import load_scenario

    path = Path(__file__).resolve().parent.parent.parent / "spacemissionstudio" / "scenarios" / "two_body_validation.json"
    return load_scenario(path)


@pytest.mark.skipif(_BASILISK_AVAILABLE, reason="this test's premise is specifically that Basilisk is unavailable")
def test_run_without_basilisk_emits_failed(qtbot):
    """Without Basilisk, the run worker fails saying Basilisk is not
    installed."""
    from spacemissionstudio.gui.run_worker import RunWorker

    worker = RunWorker(_load_two_body_scenario())
    with qtbot.waitSignal(worker.failed, timeout=5000) as blocker:
        worker.start()
    assert worker.wait(5000)  # join it: GC of a still-running QThread aborts the process
    assert "Basilisk is not installed" in blocker.args[0]


@pytest.mark.skipif(_BASILISK_AVAILABLE, reason="this test's premise is specifically that Basilisk is unavailable")
def test_live_run_without_basilisk_emits_failed(qtbot):
    """The live=True path fails the same way as live=False -- the
    ImportError happens before either run()/run_live() is ever reached
    (see RunWorker.run()'s try block).
    """
    from spacemissionstudio.gui.run_worker import RunWorker

    worker = RunWorker(_load_two_body_scenario(), live=True)
    with qtbot.waitSignal(worker.failed, timeout=5000) as blocker:
        worker.start()
    assert worker.wait(5000)  # join it: GC of a still-running QThread aborts the process
    assert "Basilisk is not installed" in blocker.args[0]


@pytest.mark.skipif(_BASILISK_AVAILABLE, reason="this test's premise is specifically that Basilisk is unavailable")
def test_monte_carlo_worker_without_basilisk_emits_failed(qtbot, tmp_path):
    """Without Basilisk, the Monte Carlo worker fails saying Basilisk is not
    installed."""
    from spacemissionstudio.gui.run_worker import MonteCarloWorker
    from spacemissionstudio.schema.scenario import MonteCarloConfig

    scenario = _load_two_body_scenario()
    mc_config = MonteCarloConfig(enabled=True, num_runs=2)
    worker = MonteCarloWorker(scenario, mc_config, tmp_path / "mc")
    with qtbot.waitSignal(worker.failed, timeout=5000) as blocker:
        worker.start()
    assert worker.wait(5000)  # join it: GC of a still-running QThread aborts the process
    assert "Basilisk is not installed" in blocker.args[0]


# -- RunWorker's dispatch/cancellation logic, via a faked engine.service/
# engine.mission_engine (installed into sys.modules before RunWorker.run()'s
# own lazy `from ..engine.service import ...` executes) rather than a real
# Basilisk build -- runs on any machine, with or without Basilisk actually
# installed, unlike the ImportError-path tests above. See run_worker.py's
# own module docstring for the "abort a running simulation" feature this
# is testing the plumbing for.

class _FakeResultSet:
    def __init__(self, series=None):
        self.series = series if series is not None else {"sat-1.position_N": object()}


class _FakeSimulationCancelled(Exception):
    def __init__(self, partial_result):
        super().__init__("cancelled")
        self.partial_result = partial_result


class _FakeMissionEngineCancelled(Exception):
    def __init__(self, partial_result, summary):
        super().__init__("cancelled")
        self.partial_result = partial_result
        self.summary = summary


def _install_fake_engine_service(monkeypatch, run_live_impl):
    import sys
    import types

    class FakeSimulationService:
        def __init__(self, scenario, vizard_request=None):
            self.scenario = scenario
            self.vizard_request = vizard_request

        def run_live(self, on_progress, should_cancel=None):
            return run_live_impl(self, on_progress, should_cancel)

    fake_module = types.ModuleType("spacemissionstudio.engine.service")
    fake_module.SimulationService = FakeSimulationService
    fake_module.SimulationCancelled = _FakeSimulationCancelled
    monkeypatch.setitem(sys.modules, "spacemissionstudio.engine.service", fake_module)
    return fake_module


def _install_fake_mission_engine(monkeypatch, run_impl):
    import sys
    import types

    class FakeMissionEngine:
        def __init__(self, scenario, service=None, should_cancel=None, allow_scripts=False, on_step=None):
            self.scenario = scenario
            self.service = service
            self.should_cancel = should_cancel
            self.allow_scripts = allow_scripts

        def run(self):
            return run_impl(self)

    fake_module = types.ModuleType("spacemissionstudio.engine.mission_engine")
    fake_module.MissionEngine = FakeMissionEngine
    fake_module.MissionEngineCancelled = _FakeMissionEngineCancelled
    monkeypatch.setitem(sys.modules, "spacemissionstudio.engine.mission_engine", fake_module)
    return fake_module


def test_run_always_uses_run_live_and_passes_should_cancel(qtbot, monkeypatch):
    """Confirms the non-mission_sequence path is always chunked via
    run_live() now (for cancellability), regardless of live=False -- see
    this module's own docstring on why.
    """
    from spacemissionstudio.gui.run_worker import RunWorker

    calls = {}

    def run_live_impl(service, on_progress, should_cancel):
        calls["should_cancel"] = should_cancel
        on_progress(_FakeResultSet(), 0.5)
        on_progress(_FakeResultSet(), 1.0)
        return _FakeResultSet()

    _install_fake_engine_service(monkeypatch, run_live_impl)
    worker = RunWorker(_load_two_body_scenario(), live=False)

    with qtbot.waitSignal(worker.finished_ok, timeout=5000):
        worker.start()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

    # Bound methods aren't singletons (worker._should_cancel is
    # worker._should_cancel is False in general), so compare what it's
    # bound to/backed by instead of object identity.
    assert calls["should_cancel"].__self__ is worker
    assert calls["should_cancel"].__func__ is type(worker)._should_cancel


def test_live_false_never_emits_progress(qtbot, monkeypatch):
    """A run that is not live signals no progress."""
    from spacemissionstudio.gui.run_worker import RunWorker

    def run_live_impl(service, on_progress, should_cancel):
        on_progress(_FakeResultSet(), 0.5)
        on_progress(_FakeResultSet(), 1.0)
        return _FakeResultSet()

    _install_fake_engine_service(monkeypatch, run_live_impl)
    worker = RunWorker(_load_two_body_scenario(), live=False)
    progress_calls = []
    worker.progress.connect(lambda *a: progress_calls.append(a))

    with qtbot.waitSignal(worker.finished_ok, timeout=5000):
        worker.start()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

    assert progress_calls == []


def test_live_true_emits_progress(qtbot, monkeypatch):
    """A live run signals each progress update."""
    from spacemissionstudio.gui.run_worker import RunWorker

    def run_live_impl(service, on_progress, should_cancel):
        on_progress(_FakeResultSet(), 0.5)
        on_progress(_FakeResultSet(), 1.0)
        return _FakeResultSet()

    _install_fake_engine_service(monkeypatch, run_live_impl)
    worker = RunWorker(_load_two_body_scenario(), live=True)
    progress_calls = []
    worker.progress.connect(lambda *a: progress_calls.append(a))

    with qtbot.waitSignal(worker.finished_ok, timeout=5000):
        worker.start()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

    assert len(progress_calls) == 2


def test_request_cancel_makes_should_cancel_true(qtbot, monkeypatch):
    """A cancel request is seen by the run's cancel check."""
    from spacemissionstudio.gui.run_worker import RunWorker

    seen = []

    def run_live_impl(service, on_progress, should_cancel):
        seen.append(should_cancel())
        return _FakeResultSet()

    _install_fake_engine_service(monkeypatch, run_live_impl)
    worker = RunWorker(_load_two_body_scenario())
    assert worker._should_cancel() is False
    worker.request_cancel()
    assert worker._should_cancel() is True

    with qtbot.waitSignal(worker.finished_ok, timeout=5000):
        worker.start()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    assert seen == [True]


def test_simulation_cancelled_emits_cancelled_signal_with_partial_result(qtbot, monkeypatch):
    """A cancelled run signals cancellation with its partial result and no
    summary."""
    from spacemissionstudio.gui.run_worker import RunWorker

    partial = _FakeResultSet()

    def run_live_impl(service, on_progress, should_cancel):
        on_progress(partial, 0.3)
        raise _FakeSimulationCancelled(partial)

    _install_fake_engine_service(monkeypatch, run_live_impl)
    worker = RunWorker(_load_two_body_scenario())

    with qtbot.waitSignal(worker.cancelled, timeout=5000) as blocker:
        worker.start()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

    assert blocker.args == [partial, None]


def test_mission_sequence_dispatch_passes_should_cancel_to_mission_engine(qtbot, monkeypatch):
    """A mission-sequence run hands the worker's cancel check to the mission
    engine."""
    from spacemissionstudio.gui.run_worker import RunWorker

    from spacemissionstudio.schema.command import Command

    calls = {}

    def run_impl(engine):
        calls["should_cancel"] = engine.should_cancel
        return _FakeResultSet(), object()

    _install_fake_engine_service(monkeypatch, lambda *a: (_ for _ in ()).throw(AssertionError("should not be called")))
    _install_fake_mission_engine(monkeypatch, run_impl)

    scenario = _load_two_body_scenario()
    scenario.mission_sequence = [Command(kind="script_block", params={"code": "pass"})]
    worker = RunWorker(scenario)

    with qtbot.waitSignal(worker.finished_ok, timeout=5000):
        worker.start()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

    # Bound methods aren't singletons (worker._should_cancel is
    # worker._should_cancel is False in general), so compare what it's
    # bound to/backed by instead of object identity.
    assert calls["should_cancel"].__self__ is worker
    assert calls["should_cancel"].__func__ is type(worker)._should_cancel


def test_mission_engine_cancelled_emits_cancelled_signal_with_partial_result_and_summary(qtbot, monkeypatch):
    """A cancelled mission-sequence run signals cancellation with its partial
    result and summary."""
    from spacemissionstudio.gui.run_worker import RunWorker

    from spacemissionstudio.schema.command import Command

    partial = _FakeResultSet()
    summary = object()

    def run_impl(engine):
        raise _FakeMissionEngineCancelled(partial, summary)

    _install_fake_engine_service(monkeypatch, lambda *a: (_ for _ in ()).throw(AssertionError("should not be called")))
    _install_fake_mission_engine(monkeypatch, run_impl)

    scenario = _load_two_body_scenario()
    scenario.mission_sequence = [Command(kind="script_block", params={"code": "pass"})]
    worker = RunWorker(scenario)

    with qtbot.waitSignal(worker.cancelled, timeout=5000) as blocker:
        worker.start()
    qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

    assert blocker.args == [partial, summary]


def test_a_basilisk_exit_during_a_run_is_reported_not_silent(qtbot, monkeypatch):
    """Audit H2: Basilisk's device factories call exit() (SystemExit) on
    settings they refuse. RunWorker caught only Exception, so the thread
    died with no signal and the GUI stayed "running" for ever."""
    from spacemissionstudio.gui.run_worker import RunWorker

    def exits(_service, _on_progress, _should_cancel):
        raise SystemExit(1)

    _install_fake_engine_service(monkeypatch, exits)
    worker = RunWorker(_load_two_body_scenario())
    with qtbot.waitSignal(worker.failed, timeout=5000) as blocker:
        worker.start()
    assert worker.wait(5000)
    assert "Basilisk stopped the run (exit status 1)" in blocker.args[0]


def _short_batch(num_runs: int = 2):
    """Template 09 as a short batch: the GUI's default single thread."""
    import dataclasses
    from pathlib import Path

    from spacemissionstudio.schema import load_scenario

    path = (Path(__file__).resolve().parent.parent.parent / "spacemissionstudio" / "scenarios" / "templates"
            / "09_monte_carlo_dispersion_analysis.json")
    scenario = load_scenario(path)
    scenario.sim_settings.duration_days = 0.01  # [day]
    mc_config = dataclasses.replace(scenario.monte_carlo, num_runs=num_runs, thread_count=1)
    scenario.monte_carlo = mc_config
    return scenario, mc_config


@pytest.mark.requires_basilisk
def test_monte_carlo_worker_runs_a_single_thread_batch(qtbot, tmp_path):
    """A batch with one thread succeeds from the GUI's worker thread.
    Basilisk's Monte Carlo controller sets a signal handler in each case,
    which Python allows only on a process's main thread: run on the worker
    QThread itself, every case failed ("signal only works in main thread")."""
    from spacemissionstudio.gui.run_worker import MonteCarloWorker

    scenario, mc_config = _short_batch()
    worker = MonteCarloWorker(scenario, mc_config, tmp_path / "mc")
    failed = []
    worker.failed.connect(failed.append)
    with qtbot.waitSignal(worker.finished_ok, timeout=600000) as blocker:  # [ms]
        worker.start()
    assert worker.wait(60000)  # [ms]
    assert not failed
    assert blocker.args[0] == []  # no failed run
    assert (tmp_path / "mc" / "batch_results.json").is_file()


@pytest.mark.requires_basilisk
def test_monte_carlo_worker_reports_the_batch_error(qtbot, tmp_path):
    """An error the batch raises (here: a folder holding other files)
    reaches the worker's failed signal with its message."""
    from spacemissionstudio.gui.run_worker import MonteCarloWorker

    scenario, mc_config = _short_batch()
    archive = tmp_path / "mc"
    archive.mkdir()
    (archive / "notes.txt").write_text("not a batch", encoding="utf-8")
    worker = MonteCarloWorker(scenario, mc_config, archive)
    with qtbot.waitSignal(worker.failed, timeout=120000) as blocker:  # [ms]
        worker.start()
    assert worker.wait(60000)  # [ms]
    assert "is not empty" in blocker.args[0]


@pytest.mark.requires_basilisk
def test_monte_carlo_child_logs_reach_this_process(tmp_path, caplog):
    """An unexpected error in the child process comes back as a
    BatchProcessError, and the child's log record of it reaches this
    process's loggers (the Log view and the log file listen there)."""
    import logging

    from spacemissionstudio.gui.monte_carlo_process import BatchProcessError, run_batch

    scenario, _mc_config = _short_batch()
    caplog.set_level(logging.INFO)
    with pytest.raises(BatchProcessError):
        run_batch(scenario, None, tmp_path / "mc")  # no config: run_monte_carlo raises AttributeError
    assert any(record.name == "spacemissionstudio.gui.monte_carlo_process"
               and "Monte Carlo batch failed" in record.getMessage() for record in caplog.records)
