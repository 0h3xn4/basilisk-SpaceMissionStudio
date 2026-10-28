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

"""MainWindow: the top-level PySide6 window. Wires
:class:`ScenarioEditorWidget`, :class:`ResultsWidget`, and
:class:`KernelStatusWidget` together via File/Run menu actions.

No scenario or simulation logic lives here -- everything goes through
``ScenarioEditorWidget.to_scenario()``/``from_scenario()``,
``schema.load_scenario()``/``Scenario.save()``, and :class:`RunWorker`,
which is the "decoupled from the sim engine via a clean API/service
layer" requirement in practice: this class could be deleted and replaced
with a different UI toolkit entirely without touching
``schema``/``engine``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
from datetime import datetime, UTC
import subprocess
import time
import weakref
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QEvent, QEventLoop, Qt, QTimer
from PySide6.QtGui import QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QToolButton,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QScrollArea,
    QDockWidget,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import output_provenance
from ..engine import monte_carlo_results, run_store
from ..engine.series_names import featured_series
from ..logging_setup import get_log_file_path
from ..schema.command import runs_sequence, script_blocks
from ..schema.scenario import Scenario, ScenarioValidationError, load_scenario
from . import autosave
from . import export_log
from .actions import ActionRegistry
from .app_shell import RunProgressStrip, StatusBarItems, StatusChip, TopBar, source_of
from .feedback import StaleResultsBanner, report, show_toast
from .icons import toolbar_icon
from .data_panel_widget import NOT_READ, DataPanelWidget
from .event_timeline_widget import EventTimelineWidget
from .exports_page import ExportsPage
from . import recent_files
from .load_scenario_widget import TEMPLATES_DIR, LoadScenarioWidget
from .mission_dashboard_widget import MissionDashboardWidget
from .mission_output_widget import MissionOutputWidget
from .monte_carlo_results_widget import MonteCarloResultsWidget
from .results_widget import ResultsWidget
from .problem_location import (GROUND_STATION, JSON_VIEW, MISSION_SEQUENCE, PROPAGATION, SCENARIO, SPACECRAFT,
                               locate)
from .run_worker import MonteCarloWorker, RunWorker
from .scenario_editor import ScenarioEditorWidget
from .budget_widget import BudgetWidget
from .fsw_workbench_widget import FlightSoftwareWidget
from .lifetime_widget import LifetimeWidget
from .scenario_explainer_widget import ScenarioExplainerWidget
from .settings_page import SettingsPage
from .shell import AreaPage, AreaStack, Shell
from .spacecraft_editor import prepare_labels
from .time_cursor import TimeCursor, describe as describe_time
from .undo_history import ScenarioHistory
from .run_history import RunHistory
from .run_history_view import HistoryEntry, RunHistoryView, run_entry, utc_text
from .results_overview import ResultsOverview
from .run_page import RunModeControl, RunPage
from .vizard_launcher import (
    DEFAULT_LIVE_STREAM_ADDRESS,
    VizardFetchWorker,
    find_vizard_executable,
    launch_vizard,
    remember_vizard_executable,
)
from .widgets import TabWidget
from .theme import (CONTENT_MAX_WIDTH_PX, apply_theme, current_theme, follow_system, icon, resolve_theme,
                    set_theme_setting, theme_setting)
from .theme.icons import keep_icon
from .compare_widget import CompareWidget
from .workspace_panels import InspectorWidget, LogViewWidget, ProblemsWidget, install_log_view
from ..engine.vizard import playback_file as vizard_playback_file

_FILE_FILTER = "SpaceMissionStudio scenario (*.json)"


def _is_template(path: Path | None) -> bool:
    """Whether ``path`` is in the built-in templates folder."""
    try:
        return path is not None and Path(path).resolve().parent == TEMPLATES_DIR.resolve()
    except OSError:
        return False
_HISTORY_SETTLE_MS = 400  # [ms] an edit is recorded for undo once typing pauses this long

# [ms] Design-philosophy roadmap item M4 (docs/ux_roadmap.md) -- how
# often _on_autosave_tick() writes a crash-recovery copy of the
# scenario currently being edited, while it's dirty. Not tuned to any
# specific benchmark: frequent enough that a crash loses at most half a
# minute of edits, infrequent enough that the per-tick
# to_scenario()+validate()+JSON-write cost (cheap, but not free) never
# has a chance to matter.
_AUTOSAVE_INTERVAL_MS = 30_000

_logger = logging.getLogger(__name__)
# The Log's record of each run (M5a): start, end, warnings, where it is saved.
_run_logger = logging.getLogger("spacemissionstudio.run")
_RUN_END_STEP_MS = 4  # [ms] between the steps that show a run's end (M6b)
_LAYOUT_VERSION = 4  # [-] saveState() version: bump when the docks change, so an old layout is ignored
# A screen narrower than this starts with the Inspector hidden (G8): at
# 1280 x 720 it took 380 px of the plot's width.
_INSPECTOR_MIN_SCREEN_PX = 1600  # [px]


def _duration_text(seconds: float) -> str:
    """A run's length for the top bar: "6 s", "2 min 05 s", "1 h 03 min"."""
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60:02d} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"


def _with_log_file_hint(message: str) -> str:
    """Appends where the FULL traceback for ``message`` was just logged
    (see ``logging_setup``'s own module docstring) -- direct user
    feedback that a bare error message with nothing else to go on
    (e.g. a raw C++ exception's ``str()``) left no way to actually
    diagnose an unexpected failure. Falls back to ``message`` unchanged
    if logging was never configured (e.g. a test constructing
    MainWindow directly without going through a real entry point).
    """
    log_file = get_log_file_path()
    if log_file is None:
        return message
    return f"{message}\n\nFull details logged to:\n{log_file}"


_EVENT_WORDS = {"pass": ("pass", "passes"), "eclipse": ("eclipse", "eclipses"), "burn": ("burn", "burns"),
                "thruster firing": ("thruster firing", "thruster firings"), "mode": ("mode change", "mode changes"),
                "downlink": ("downlink", "downlinks")}


def events_summary(result) -> str:
    """ "4 passes, 15 eclipses" for a run's events, "no events" when it had
    none (the post-run toast, docs/ux-audit.md U-21)."""
    from ..engine.events import KINDS, extract_events

    try:
        events = extract_events(result)
    except Exception:  # noqa: BLE001 -- a summary must never turn a finished run into a failure
        _logger.exception("Counting the run's events failed")
        return ""
    counts = {kind: sum(1 for event in events if event.kind == kind) for kind in KINDS}
    parts = [f"{count} {_EVENT_WORDS.get(kind, (kind, kind + 's'))[count != 1]}"
             for kind, count in counts.items() if count]
    return ", ".join(parts) if parts else "no events"


def _join_finished_worker(worker) -> None:
    """Waits out a previous run's QThread before its last reference is replaced.

    A worker emits its terminal signal (finished_ok/failed/cancelled) from
    INSIDE its own ``run()``, so the slot that re-enables Run can execute
    while that thread is still returning. Dropping the last Python
    reference to a still-running QThread makes Qt abort the whole process
    ("QThread: Destroyed while thread is still running") -- found by
    looping the test suite, where exactly that race aborted ~1 run in 3.
    Here the thread is at most microseconds from done, so this never
    blocks noticeably.
    """
    if worker is not None and worker.isRunning():
        worker.wait()


class MainWindow(QMainWindow):
    def __init__(self, prompt_startup_fetch: bool = True, check_autosave_recovery: bool = True):
        super().__init__()
        # Wider default than before: the scenario form's own natural
        # content width (~576px, e.g. the "Full attitude (sensors,
        # actuators, FSW, power)" mode combo) needs a genuinely wide left
        # pane, and giving the left pane a smaller SHARE of the window
        # (see the splitter setup below) without also growing the window
        # itself would starve that content back down to where it needed
        # its own horizontal scrollbar.
        self.resize(1400, 850)

        self._current_path: Path | None = None
        self._dirty = False
        self._run_worker: RunWorker | None = None
        self._mc_worker: MonteCarloWorker | None = None
        self._mc_archive_dir: Path | None = None  # where the running or last batch saves (on_run_monte_carlo)
        self._progress_error_shown = False  # see _on_run_progress's own comment
        self._vizard_request = None  # engine.vizard.VizardRequest, or None -- set via the Run menu's "Vizard Configuration..." action
        self._vizard_process = None  # subprocess.Popen, or None -- set via the Run menu's "Launch Vizard" action
        # The direct_comm_address self._vizard_process was actually launched
        # with (None if it was launched with no -directComm flag at all) --
        # lets on_launch_vizard() tell a live-stream-ready instance apart
        # from one that isn't, instead of trusting ANY already-running
        # process regardless of how it was started. See on_launch_vizard()'s
        # own docstring.
        self._vizard_direct_comm_address = None
        # -directComm pre-fills Vizard's own socket address field and
        # selects DirectComm/Live Display for the user, but -- confirmed
        # by direct user report -- does NOT click its "Start
        # Visualization" button for them; that one click is still needed
        # every time Vizard is (re)launched this way, and no documented
        # command-line flag skips it while keeping the visible live view
        # (see on_launch_vizard()'s own comment). Shown once per session
        # (not on every single launch/run) so the user isn't stuck
        # wondering why the run is "stuck" without knowing this, but
        # also isn't nagged repeatedly once they do.
        self._vizard_live_stream_hint_shown = False
        self._last_run_epoch_utc: str | None = None  # set in on_run(); see its own comment
        self._last_run_vizard_file: str | None = None  # the playback file the last run writes, if any
        # the runs kept for comparison, saved in ~/.spacemissionstudio/runs (U-33, decision 5)
        # Read and saved in a worker thread (M5a): the end of a run does not wait for the disk.
        self.run_history = RunHistory(store_root=run_store.default_root(), background=True, parent=self)
        self.run_history.loaded.connect(self._on_runs_loaded)
        self.run_history.saved.connect(self._on_run_saved)
        self._compare_stale = False  # Compare is refreshed when next shown (M5a)
        self._last_run_scenario: Scenario | None = None  # set in on_run(); fed to mission_dashboard_widget

        self.scenario_editor = ScenarioEditorWidget()
        # Through a weak reference: a lambda holding the window would make a
        # cycle (window -> editor -> lambda -> window) that keeps the window
        # and its web views alive until interpreter exit, after Qt WebEngine
        # has shut down -- a segfault on exit, seen in CI's GUI tests.
        window = weakref.ref(self)
        self.scenario_editor.set_base_dir_provider(lambda: window()._scenario_dir() if window() else None)
        self.scenario_editor.reset_to_default()
        self.scenario_editor.changed.connect(self._mark_dirty)
        self.scenario_editor.changed.connect(self._refresh_scenario_explainer)
        # Undo and redo (gui.undo_history): one snapshot per settled edit.
        self._history = ScenarioHistory()
        self._restoring_history = False
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(_HISTORY_SETTLE_MS)
        self._history_timer.timeout.connect(self._record_history)
        self.scenario_editor.changed.connect(self._schedule_history)
        self._history.reset(self._editor_state())

        self.load_scenario_widget = LoadScenarioWidget()
        self.load_scenario_widget.path_chosen.connect(self._on_load_scenario_path_chosen)
        self.load_scenario_widget.scenario_customized.connect(self._on_load_scenario_customized)
        self.load_scenario_widget.blank_requested.connect(self.on_new)

        self.results_widget = ResultsWidget()
        self.mission_dashboard_widget = MissionDashboardWidget()
        self.mission_output_widget = MissionOutputWidget()
        self.data_panel_widget = DataPanelWidget(load=False)  # read in a worker below (M9)
        self.event_timeline_widget = EventTimelineWidget()
        # One time cursor for every view of a run (UX/UI guidelines).
        self.time_cursor = TimeCursor(self)
        self.event_timeline_widget.set_time_cursor(self.time_cursor)
        self.results_widget.set_time_cursor(self.time_cursor)
        self.mission_dashboard_widget.set_time_cursor(self.time_cursor)
        self.mission_output_widget.set_time_cursor(self.time_cursor)
        self.results_widget.open_in_vizard.connect(self.open_vizard_playback)
        self.scenario_explainer_widget = ScenarioExplainerWidget()
        self.scenario_explainer_widget.model_requested.connect(self.open_3d_model_of)
        self.lifetime_widget = LifetimeWidget()
        self.budget_widget = BudgetWidget()
        self.flight_software_widget = FlightSoftwareWidget()
        self.flight_software_widget.exports_changed.connect(self.scenario_editor.set_fsw_exports)
        # Reports (M8): every export in one table, then the flight software.
        self.exports_page = ExportsPage()
        self.exports_page.open_requested.connect(self._on_export_open_requested)
        self.reports_views = TabWidget()
        self.reports_views.setObjectName("reportsViews")
        self.reports_views.addTab(self.exports_page, "Exports")
        self.reports_views.addTab(self.flight_software_widget, "Flight Software")

        # Above every run view: says when the results shown are from an
        # earlier version of the scenario (docs/ux-audit.md U-20).
        self.stale_results_banner = StaleResultsBanner()
        self.stale_results_banner.rerun_requested.connect(self.on_run)
        self._shown_run_sha256: str | None = None  # the scenario hash of the run the views show

        # The workspace (UI overhaul plan §5.1): a navigation rail of areas
        # (gui.shell), the top bar above them, the inspector on the right, Problems below,
        # and the reference data in a dialog opened from the status bar.
        # The Scenario area is the scenario tree with the editor's own
        # nodes; Templates is Home, the analyses are in Run and Reports.
        # In scroll areas: the End of Life form and its results need about
        # 560 px, which kept the window from fitting 720 px (U-03); the
        # budget, launch-delay and altitude tables together outgrow short
        # windows too.
        lifetime_scroll = QScrollArea()
        lifetime_scroll.setWidgetResizable(True)
        lifetime_scroll.setWidget(self.lifetime_widget)
        budget_scroll = QScrollArea()
        budget_scroll.setWidgetResizable(True)
        budget_scroll.setWidget(self.budget_widget)
        self.scenario_editor.navigate_requested.connect(self._on_guide_navigate)

        # Results: the run's overview, the plots, the dashboard, the mission
        # output and, when there is something to show, the Monte Carlo statistics.
        self.results_views = TabWidget()
        self.results_views.setObjectName("resultsViews")
        self.results_overview = ResultsOverview()  # M6a: the run's headline figures, its provenance
        self.results_overview.run_requested.connect(self.on_run)
        self.results_views.addTab(self.results_overview, "Overview")
        self.results_views.addTab(self.results_widget, "Plots")
        self.results_views.addTab(self.mission_dashboard_widget, "Dashboard")
        self.results_views.addTab(self.mission_output_widget, "Output")
        # Added and removed as needed (_update_monte_carlo_tab), never kept
        # as a hidden tab: selecting a hidden tab crashed a CI test run.
        self.monte_carlo_results_widget = MonteCarloResultsWidget(self)
        self.monte_carlo_results_widget.hide()

        # Compare is a view of the results (§5.2), after them.
        self.compare_widget = CompareWidget()
        self.compare_widget.installEventFilter(self)  # refreshed when shown, if stale (M5a)
        self.compare_widget.compare_chosen.connect(self._on_compare_chosen)
        self.compare_widget.delete_requested.connect(self._on_delete_run)
        # a bound method, not a lambda holding the window (test_a_closed_window_is_freed)
        self.results_widget.compare_combo.currentIndexChanged.connect(self._on_results_compare_changed)
        self.results_views.addTab(self.compare_widget, "Compare")
        self.results_views.currentChanged.connect(self._apply_stale_banner)
        self.log_widget = LogViewWidget()
        # Run > History (M5a): every run kept, and this session's failed runs and batches.
        self.history_view = RunHistoryView()
        self.history_view.run_requested.connect(self.on_run)
        self.history_view.show_requested.connect(self._show_history_run)
        self._run_modes: dict = {}  # run number -> "Single" or "SIL" (this session's runs)
        self._run_seconds: dict = {}  # run number -> [s] how long it took (this session's runs)
        self._history_extra: list = []  # HistoryEntry: failed runs and batches, this session only
        self._run_started_at = None  # datetime (UTC) the current run started
        install_log_view(self.log_widget)

        # The Run area: the analyses that run on the scenario, each on its
        # one page of inputs and results (decision of M2a), and the log.
        self.run_views = TabWidget()
        self.run_views.setObjectName("runViews")
        # Run > Run (M5b): what the next run uses, for the mode chosen.
        self.run_page = RunPage()
        self.run_page.vizard_changed.connect(self._on_vizard_edited)
        self.run_page.archive_changed.connect(self._remember_archive_dir)
        self.run_views.addTab(self.run_page, "Run")
        self.run_views.addTab(lifetime_scroll, "End of Life")
        self.run_views.addTab(budget_scroll, "Budget")
        self.run_views.addTab(self.history_view, "History")
        self.run_views.addTab(self.log_widget, "Log")
        self.results_widget.set_runs(self.run_history.runs, None)  # the saved runs of earlier sessions (U-33)
        self._refresh_compare_tab()

        # The inspector on the right (UI overhaul plan §5.1, M2b): the
        # focused field. Explain (what the scenario does) is the Scenario
        # tree's first node, Overview (M4b).
        self.inspector_widget = InspectorWidget()
        self.side_dock = self._make_dock("Inspector", "inspectorDock", self.inspector_widget)
        self.scenario_explainer_widget.setMaximumWidth(CONTENT_MAX_WIDTH_PX)
        self.overview_item = self.scenario_editor.page_tree.add_page("Overview", self.scenario_explainer_widget,
                                                                     index=0)
        self.scenario_explainer_widget.explained.connect(self._on_explained)
        # The Problems panel, at the bottom (M2b): what does not validate or
        # looks implausible, as a table; Enter or a double-click goes to the field.
        self._error_count: int | None = None  # the errors last counted: None until the first count
        self.problems_widget = ProblemsWidget()
        self.problems_widget.activated.connect(self._on_problem_activated)
        self.problems_widget.counts_changed.connect(self._on_problem_counts)
        self.problems_dock = self._make_dock("Problems", "problemsDock", self.problems_widget,
                                             area=Qt.DockWidgetArea.BottomDockWidgetArea)
        self.scenario_editor.problems_changed.connect(self._on_problems_changed)
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)
        self.scenario_editor.changed.connect(self.inspector_widget.refresh)

        # The reference data files, with their downloads, imports and
        # rollbacks: a dialog the status bar's entry opens.
        self.data_dialog = QDialog(self)
        self.data_dialog.setWindowTitle("Reference data")
        self.data_dialog.resize(980, 460)  # [px]
        data_layout = QVBoxLayout(self.data_dialog)
        data_layout.addWidget(self.data_panel_widget)
        self._refresh_scenario_explainer()  # initial paint for the default scenario reset_to_default() just set up

        # The top bar: the scenario's name, its state, the last run and the
        # problem count, always visible (gui.app_shell; docs/ux-audit.md U-04).
        self.top_bar = TopBar()
        # The job in the status bar (U-19, M2b): phase, bar, elapsed time,
        # time left, Cancel. Its bar and time label are the busy indicator
        # every run updates; the chip beside it says the run's state.
        self.run_progress = RunProgressStrip()
        self.run_progress.cancel_requested.connect(self.on_abort_run)
        self._busy_label = self.run_progress.time_label
        self._busy_progress = self.run_progress.bar
        self.run_chip = StatusChip()
        # The rail and the areas (gui.shell). The top bar and, above the run
        # views, the stale-results banner (U-20) sit over the area shown.
        self.shell = Shell()
        self.areas = self.shell.stack
        self.shell.work_layout.insertWidget(0, self.top_bar)
        self.shell.work_layout.insertWidget(1, self.stale_results_banner)
        self.setCentralWidget(self.shell)
        self._run_started_s: float | None = None  # time.monotonic() when the current run started

        self._build_actions()
        self._build_areas()
        self.resizeDocks([self.side_dock], [380], Qt.Orientation.Horizontal)  # [px]
        self.resizeDocks([self.problems_dock], [140], Qt.Orientation.Vertical)  # [px] about four rows
        self._hide_default_panels()
        self._default_layout = self.saveState(_LAYOUT_VERSION)
        self._restore_layout()

        # Run-in-progress feedback: the progress strip (self.run_progress)
        # and the status chip, both in the status bar. A run reports its phase
        # and fraction (RunWorker.phase/fraction: chunks of the propagation,
        # or the Mission Sequence's steps); a Monte Carlo batch is counted
        # by its finished cases' files (_poll_monte_carlo), since Basilisk's
        # Controller has no progress hook.
        self._busy_elapsed = QElapsedTimer()
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(200)
        self._busy_timer.timeout.connect(self._update_busy_elapsed)
        self.run_problems: list[str] = []  # what _report_run_problem said, newest last
        self.last_run_seconds = None  # the last run's length [s]
        self._mc_poll = QTimer(self)
        self._mc_poll.setInterval(1000)  # [ms] a Monte Carlo case takes seconds at least
        self._mc_poll.timeout.connect(self._poll_monte_carlo)
        # Always shown (gui.app_shell; docs/ux-audit.md U-06): the Basilisk
        # version, checked at start-up (ECSS-Q-ST-80C 6.2.7, decision D5), the
        # reference data (a click opens the Reference data dialog), Earth orientation and
        # the frames. Local files only.
        self.status_items = StatusBarItems(self)
        self.basilisk_version_label = self.status_items.basilisk_label
        for widget in (self.run_progress, self.run_chip, *self.status_items.widgets):
            self.statusBar().addPermanentWidget(widget)
        # A bound method, not a lambda: a lambda holding self on a child's
        # signal keeps the window alive until the interpreter exits, and its
        # web views are then torn down too late (exit segfault, as in #48).
        self.status_items.data_clicked.connect(self._show_data_panel)
        self.data_panel_widget.refreshed.connect(self._on_reference_data_read)
        self.data_panel_widget.read_failed.connect(self.status_items.show_data_read_failure)
        # The files are read in a worker once the window is up (M9: 1.5 s
        # of start-up); the status bar fills in when they are.
        QTimer.singleShot(0, self.data_panel_widget, self.data_panel_widget.read_at_start_up)  # not once closed
        self.status_items.problems_clicked.connect(self.show_problems)
        self.top_bar.problems_button.clicked.connect(self.show_problems)
        self._on_problems_changed(self.scenario_editor.problem_rows())
        self.time_cursor_label = QLabel()
        self.time_cursor_label.setToolTip("The shared time cursor. Click a plot or the Timeline to move it; "
                                          "Clear Time Cursor (Alt+Backspace) clears it.")
        self.time_cursor_label.setVisible(False)
        self.statusBar().addPermanentWidget(self.time_cursor_label)
        self.time_cursor.changed.connect(self._on_time_cursor_changed)

        # Design-philosophy roadmap item M4 (docs/ux_roadmap.md):
        # autosave/crash-recovery for scenario edits -- see
        # gui.autosave's own module docstring. The timer runs
        # unconditionally (not just when check_autosave_recovery is
        # True -- that flag only controls the STARTUP offer to restore
        # a previous crash's leftovers, which is unrelated to whether
        # THIS session's own edits should be protected going forward);
        # _on_autosave_tick() itself no-ops whenever there's nothing
        # dirty to save, which is the common case.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(_AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)
        self._autosave_timer.start()

        self.statusBar().showMessage("Ready.")
        self._update_window_title()

        if check_autosave_recovery:
            # Fired via singleShot(0, ...) for the same reason
            # prompt_startup_fetch below is -- the window must already be
            # rendered before a blocking modal dialog appears on top of
            # it. check_autosave_recovery=False is how tests (and
            # anything else constructing MainWindow headlessly) opt out,
            # the same convention prompt_startup_fetch already
            # established -- see tests/gui/test_main_window.py's own
            # `window` fixture. Checked before the kernel-fetch prompt
            # below so a recovered scenario (which may need different
            # kernels than whatever reset_to_default() left in place) is
            # in the editor first, though the two don't otherwise
            # interact.
            QTimer.singleShot(0, self._check_autosave_recovery)

        if prompt_startup_fetch:
            # Fired via singleShot(0, ...), not called directly here, so
            # the main window has already rendered (show() has happened,
            # back in gui.app.main()) before the consent dialog appears
            # on top of it -- real user requirement: "a one time fetch
            # during each startup... the user always should be asked".
            # prompt_startup_fetch=False is how tests (and anything else
            # constructing MainWindow headlessly) opt out of it -- see
            # tests/gui/test_main_window.py's own `window` fixture. Since
            # M3 the question is a card on Home, not a modal dialog.
            QTimer.singleShot(0, self.load_scenario_widget.reference_card.ask)

    # -- commands: the action registry (gui.actions) ----------------------------
    def _build_actions(self) -> None:
        """Every command of the window, in one registry: the command
        palette, the area headers, the top bar, the shortcut list and the
        tooltips all come from it. The window owns the actions, so their
        shortcuts work in every area; there is no menu bar."""
        self.commands = registry = ActionRegistry(self)
        add = registry.add

        self.new_action = add(
            "file.new", "&New Scenario", self.on_new, category="File", area="home",
            shortcut=QKeySequence.StandardKey.New, qicon=toolbar_icon("new"),
            tip="Discards the scenario open (asking to save first if it has unsaved changes) and starts an "
                "empty one.", keywords=("blank", "from scratch"))
        self.open_action = add(
            "file.open", "&Open...", self.on_open, category="File", area="home",
            shortcut=QKeySequence.StandardKey.Open, qicon=toolbar_icon("open"),
            tip="Loads a saved .json scenario, replacing the one open (asking to save first if it has unsaved "
                "changes).")
        self.save_action = add(
            "file.save", "&Save", self.on_save, category="File", area="global",
            shortcut=QKeySequence.StandardKey.Save, qicon=toolbar_icon("save"),
            tip="Writes the scenario to its file; a scenario never saved asks where, as Save As does.")
        self.save_as_action = add(
            "file.save_as", "Save &As...", self.on_save_as, category="File", area="global",
            shortcut=QKeySequence.StandardKey.SaveAs,
            tip="Saves the scenario to a file you choose; later saves go there. Use it to branch off a variant.")
        add("file.quit", "&Quit", self.close, category="File", area="global",
            shortcut=QKeySequence.StandardKey.Quit,
            tip="Closes SpaceMissionStudio, asking to save first if the scenario has unsaved changes.")

        # The platform's Undo keys, but Alt+Backspace (in them on Linux): it is
        # Clear Time Cursor's, and a key bound twice fires neither.
        undo_keys = [keys for keys in QKeySequence.keyBindings(QKeySequence.StandardKey.Undo)
                     if keys != QKeySequence("Alt+Backspace")]
        self.undo_action = add("edit.undo", "&Undo", self.on_undo, category="Edit", area="global",
                               shortcut=undo_keys,
                               tip="Undo the last scenario edit. A field being typed in undoes its own text first.")
        self.redo_action = add("edit.redo", "&Redo", self.on_redo, category="Edit", area="global",
                               shortcut=QKeySequence.StandardKey.Redo, tip="Redo the scenario edit just undone.")
        self._update_undo_actions()

        # One Run (docs/ux-audit.md U-18, decision 3): Run starts the run
        # mode picked beside it -- a single run, a Monte Carlo batch, or a
        # run with a spacecraft's flight software in the loop (SIL).
        self.run_action = add("run.run", "&Run", self.on_run, category="Run", area="run", shortcut="Ctrl+R",
                              qicon=toolbar_icon("run"))
        self.run_mode_group = QActionGroup(self)
        self.run_mode_group.setExclusive(True)
        self.run_mode_menu = QMenu("Run mode", self)
        for mode, command_id, label, qicon, tip in (
                ("single", "run.mode.single", "&Single run", None,
                 "Build the scenario in Basilisk and run it once (the Mission Sequence, when it has one, or the "
                 "set duration)."),
                ("monte_carlo", "run.mode.monte_carlo", "&Monte Carlo", toolbar_icon("monte-carlo"),
                 "Run the scenario's Monte Carlo batch (Scenario > Monte Carlo): many runs with dispersed inputs, "
                 "saved to a folder you choose."),
                ("sil", "run.mode.sil", "S&IL (flight software in the loop)", None,
                 "Run with a spacecraft's exported flight software as an external program in the loop "
                 "(Reports > Flight Software).")):
            action = add(command_id, label, None, category="Run mode", area="run", qicon=qicon, checkable=True,
                         tip=tip)
            action.setData(mode)
            self.run_mode_group.addAction(action)
            self.run_mode_menu.addAction(action)
        self.single_run_action = registry.action("run.mode.single")
        self.monte_carlo_action = registry.action("run.mode.monte_carlo")
        self.sil_run_action = registry.action("run.mode.sil")
        self.single_run_action.setChecked(True)
        self.run_mode_group.triggered.connect(self._on_run_mode_changed)

        # "Abort a running simulation, if needed, without breaking the
        # tool" -- direct user feedback. Only ever enabled while a single
        # (non-Monte-Carlo) run is actually in flight -- see on_run()/
        # _stop_busy() for where it's toggled -- since RunWorker is the
        # only worker with a request_cancel() to call (see its module
        # docstring for the cooperative-cancellation design; Monte Carlo
        # batches have no equivalent hook and are out of scope here).
        self.abort_action = add("run.cancel", "&Cancel Run", self.on_abort_run, category="Run", area="run",
                                shortcut=QKeySequence(Qt.Key.Key_Escape), qicon=toolbar_icon("abort"),
                                tip="It stops at the next checkpoint, keeping what was computed.")
        self.abort_action.setEnabled(False)  # enabled only while a run can be cancelled
        # A labelled toggle (U-46): it says its state, rather than looking
        # like a pressed tab.
        self.live_plot_action = add(
            "run.live_plot", "Live plot: on", self._on_live_plot_toggled, category="Run", area="run",
            qicon=toolbar_icon("live-plot"), checkable=True, checked=True,
            tip="Update the Results plot as the simulation runs, instead of only once it finishes.")
        self.check_kernels_action = add(
            "run.check_data", "&Check Reference Data", self._show_data_panel, category="Run", area="settings",
            qicon=toolbar_icon("check-kernels"),
            tip="Shows every reference data file (SPICE kernels, gravity field, magnetic model, space weather, "
                "Earth orientation) with its source, dates and checksum. No network: downloads start only from "
                "the Reference data dialog's Download... menu, after asking.")
        self.vizard_action = add("run.vizard_config", "Vizard &Configuration...", self.on_configure_vizard,
                                 category="Run", area="run", qicon=toolbar_icon("vizard-config"),
                                 tip="Configure Vizard visualization for the next run.")
        # Distinct from "Vizard Configuration..." above (which only
        # decides how the NEXT run feeds Vizard, e.g. a live stream or a
        # playback file) -- this one actually starts the separate Vizard
        # application, so live-stream mode has something to connect to.
        self.vizard_launch_action = add("run.vizard_launch", "&Launch Vizard", self.on_launch_vizard,
                                        category="Run", area="run", qicon=toolbar_icon("vizard-launch"),
                                        tip="Start the external Vizard application.")
        self.open_monte_carlo_results_action = add(
            "run.open_monte_carlo", "Open Monte Carlo &Results...", self.on_open_monte_carlo_results,
            category="Run", area="run", qicon=toolbar_icon("open-monte-carlo"),
            tip="Show the batch an earlier Monte Carlo run saved in a folder.")
        self.clear_cursor_action = add(
            "run.clear_cursor", "Clear &Time Cursor", self.time_cursor.clear, category="Run", area="results",
            shortcut="Alt+Backspace", qicon=toolbar_icon("clear-cursor"), tip="Clears the shared time cursor; the views show the end of the run again.")

        # The analyses and tools, by their old menu names too (§5.2).
        self.model_3d_action = add(
            "tools.model_3d", "3D &Model...", self.on_open_3d_model, category="Tools", area="scenario",
            qicon=toolbar_icon("model-3d"),
            tip="Build or edit a spacecraft's 3D model: its look in Vizard, its mass, center of mass and inertia, "
                "and its drag and solar pressure surfaces.")
        for command_id, category, label, widget, area, tip in (
                ("analyses.end_of_life", "Analyses", "&End of Life", self.lifetime_widget, "run",
                 "Re-entry and deorbit estimates."),
                ("analyses.budget", "Analyses", "&Budget", self.budget_widget, "run",
                 "Delta-V and propellant budgets."),
                ("tools.flight_software", "Tools", "&Flight Software", self.flight_software_widget, "reports",
                 "Export the flight software, run SIL."),
                ("tools.reference_data", "Tools", "&Reference Data...", self.data_panel_widget, "settings",
                 "The data files, downloads and imports.")):
            # A bound method, not a lambda holding the window (see the status bar's).
            add(command_id, label, self._on_page_action, category=category, area=area, tip=tip).setData(widget)

        # The inspector on the right, the Problems panel at the bottom, and
        # the layout back (U-05, M2b). Showing a panel from the keyboard
        # puts the focus in it.
        add("view.inspector", "&Inspector", None, category="View", area="global",
            action=self.side_dock.toggleViewAction(), shortcut="Ctrl+I", keywords=("side panel",),
            tip="Show or hide the inspector: the focused field.").triggered.connect(
                self._on_dock_toggled)
        add("view.explain", "E&xplain", self._on_page_action, category="View", area="global",
            tip="What the scenario does: Scenario › Overview.").setData(self.scenario_explainer_widget)
        add("view.problems", "&Problems", None, category="View", area="global",
            action=self.problems_dock.toggleViewAction(), shortcut="Ctrl+J",
            tip="Show or hide the Problems panel: what does not validate.").triggered.connect(
                self._on_dock_toggled)
        self.reset_layout_action = add("view.reset_layout", "&Reset Layout", self.reset_layout, category="View",
                                       area="settings", tip="Put the panels back where they start.")
        self.rail_collapse_action = add(
            "view.rail_icons", "Navigation: Icons Only", self._on_rail_icons_toggled, category="View",
            area="global", checkable=True, tip="Show the navigation rail's areas as icons only, or with names.")
        # The theme: a choice applies at once, to every open view (gui/theme/).
        self.theme_group = QActionGroup(self)
        self.theme_actions = {}
        chosen = theme_setting()
        for value, label in (("system", "&System"), ("light", "&Light"), ("dark", "&Dark")):
            action = add(f"view.theme.{value}", f"Theme: {label}", None, category="View", area="settings",
                         checkable=True, checked=value == chosen,
                         tip="Follow the system's light or dark setting." if value == "system"
                         else f"The {value} theme.")
            action.setData(value)
            action.triggered.connect(self._on_theme_chosen)
            self.theme_group.addAction(action)
            self.theme_actions[value] = action
        # The Results time cursor from the keyboard: the views' own actions,
        # whose shortcuts work while Results has the focus.
        for action in self.results_widget.cursor_actions:
            add(f"cursor.{action.text().lower().replace(' ', '_')}", action.text(), None, category="Time Cursor",
                area="results", action=action, on_window=False, tip=action.toolTip())

        self.manual_action = add(
            "help.manual", "&User Manual", self.on_user_manual, category="Help", area="help",
            # F1 on every platform, plus the platform's own key
            shortcut=[QKeySequence("F1")] + [k for k in QKeySequence.keyBindings(
                QKeySequence.StandardKey.HelpContents) if k.toString() != "F1"],
            tip="Opens the user manual shipped with the app (works offline).")
        self.shortcuts_action = add("help.shortcuts", "&Keyboard Shortcuts", self.on_keyboard_shortcuts,
                                    category="Help", area="settings", shortcut="Ctrl+/",
                                    tip="Lists the keyboard shortcuts (Settings > Keyboard).")
        self.palette_action = add("help.palette", "&Command Palette...", self.on_command_palette, category="Help",
                                  area="global", shortcut="Ctrl+K",
                                  tip="Find any command, area, page or object by typing part of its name.")
        self.about_action = add("help.about", "&About SpaceMissionStudio", self.on_about, category="Help",
                                area="settings", tip="Shows the installed version and licensing information.")

        # The run mode beside Run, in the top bar and the Run area: its
        # menu holds the three modes.
        self.run_mode_button = self._run_mode_button()
        self.top_bar.add_commands(self.undo_action, self.redo_action, self.save_action, self.run_action,
                                  self.run_mode_button, self.palette_action)
        self._on_run_mode_changed()

    def _run_mode_button(self) -> QToolButton:
        button = QToolButton()
        button.setObjectName("runModeButton")
        button.setMenu(self.run_mode_menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolTip("What Run starts: a single run, the Monte Carlo batch, or SIL")
        return button

    # -- areas: the navigation rail (gui.shell) ----------------------------------
    _AREAS = (("home", "house", "Home"), ("scenario", "file-text", "Scenario"), ("run", "play", "Run"),
              ("results", "chart-line", "Results"), ("timeline", "chart-gantt", "Timeline"),
              ("reports", "file-output", "Reports"))

    def _build_areas(self) -> None:
        """The rail's areas, each hosting its screens unchanged (decision of
        M2a), with the area's commands in its header; Ctrl+1 to Ctrl+6
        open the six of the top."""
        contents = {"home": self.load_scenario_widget, "scenario": self.scenario_editor, "run": self.run_views,
                    "results": self.results_views, "timeline": self.event_timeline_widget,
                    "reports": self.reports_views}
        for order, (area_id, icon_name, label) in enumerate(self._AREAS):
            keys = f"Ctrl+{order + 1}"
            self.shell.register(area_id, icon_name, label, contents[area_id], order, keys=keys)
            action = self.commands.add(f"go.{area_id}", f"Go to {label}", None, category="Go", area=area_id,
                                       shortcut=keys, tip=f"Show the {label} area.",
                                       keywords=("events",) if area_id == "timeline" else ())
            action.setData(area_id)
            action.triggered.connect(self._on_go_to_area)
        self.settings_page = SettingsPage(self.commands)
        self.shell.register("settings", "settings", "Settings", self.settings_page, len(self._AREAS), bottom=True)
        self.shell.register("help", "circle-help", "Help", None, len(self._AREAS) + 1, bottom=True,
                            action=self.manual_action, keys="F1")

        # Home's own page has New blank scenario and Browse for a file.
        # The Scenario area's Form · JSON toggle (M4b), then its 3D model command.
        self.shell.page("scenario").add_widget(self.scenario_editor.mode_toggle)
        self.shell.page("scenario").add_command(self.model_3d_action)
        run = self.shell.page("run")
        self.run_area_run_button = run.add_command(self.run_action, primary=True)
        keep_icon(self.run_area_run_button, icon("play", "text.on_accent"))  # the accent icon would vanish on the fill
        # The mode as a segmented control (M5b); its options are on the Run page.
        self.run_mode_control = RunModeControl()
        self.run_mode_control.chosen.connect(self.set_run_mode)
        run.add_widget(self.run_mode_control)
        for action in (self.abort_action, self.vizard_launch_action, self.open_monte_carlo_results_action,
                       self.check_kernels_action):
            run.add_command(action)
        self.run_page.live_plot_check.setChecked(self.live_plot_action.isChecked())
        self.run_page.live_plot_check.toggled.connect(self.live_plot_action.setChecked)
        self.live_plot_action.toggled.connect(self.run_page.live_plot_check.setChecked)
        self.run_page.set_vizard(self._vizard_request)
        self.run_views.currentChanged.connect(self._refresh_run_page)
        self.shell.area_changed.connect(self._refresh_run_page)
        for area_id in ("results", "timeline"):
            self.shell.page(area_id).add_command(self.clear_cursor_action)

        self.shell.area_changed.connect(self._on_area_changed)
        # Compare, refreshed when shown (M5a): its tab, or the Results area, chosen.
        self.shell.area_changed.connect(self._refresh_compare_if_shown)
        self.results_views.currentChanged.connect(self._refresh_compare_if_shown)
        self.shell.rail.collapsed_changed.connect(self.rail_collapse_action.setChecked)
        self.scenario_editor.page_tree.tree.currentItemChanged.connect(self._refresh_breadcrumbs)
        self.scenario_editor.mode_changed.connect(self._refresh_breadcrumbs)
        for tabs in (self.results_views, self.run_views):
            tabs.currentChanged.connect(self._refresh_breadcrumbs)
        self.shell.show_area("home")  # a new user's first move is picking a template or a file
        self._refresh_breadcrumbs()
        self._on_run_mode_changed()  # the Run area's mode button has its text too

    def _on_go_to_area(self) -> None:
        self.shell.show_area(self.sender().data())

    def _on_area_changed(self, _area_id: str) -> None:
        self._apply_stale_banner()
        self._refresh_breadcrumbs()

    def _on_rail_icons_toggled(self, checked: bool) -> None:
        self.shell.rail.set_collapsed(checked)

    def _refresh_breadcrumbs(self, *_args) -> None:
        """The top bar's "Area › page": the Scenario tree's path, or the tab
        of the area shown."""
        area_id = self.shell.current_area()
        if area_id is None:
            return
        parts = [self.shell.areas[area_id].label]
        if area_id == "scenario" and self.scenario_editor.json_mode:
            parts.append("JSON")
        elif area_id == "scenario":
            item = self.scenario_editor.page_tree.tree.currentItem()
            names = []
            while item is not None:
                names.insert(0, item.text(0))
                item = item.parent()
            parts += names
        elif area_id in ("results", "run"):
            tabs = self.results_views if area_id == "results" else self.run_views
            parts.append(tabs.tabText(tabs.currentIndex()).replace("&", ""))
        self.top_bar.set_breadcrumbs(parts)

    def _show_data_panel(self) -> None:
        self.data_panel_widget.refresh_in_background()  # the dialog shows at once, the table follows
        self.show_view(self.data_panel_widget)

    def _on_reference_data_read(self) -> None:
        """The reference data panel read the files: the status bar's summary, from the same list."""
        panel = self.data_panel_widget
        version = None if panel.basilisk_version is NOT_READ else panel.basilisk_version
        self.status_items.refresh(panel.files, version)
        prepare_labels(self)  # start-up has settled: the messages' titles, a section per turn (once per process)

    # -- workspace: tabs, docks and their layout ---------------------------------
    def _make_dock(self, title: str, name: str, widget: QWidget,
                   area: Qt.DockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(name)  # saveState()/restoreState() find docks by name
        dock.setWidget(widget)
        if area == Qt.DockWidgetArea.BottomDockWidgetArea:
            dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea)
        else:
            dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(area, dock)
        return dock

    def _docks(self) -> tuple:
        return (self.side_dock, self.problems_dock)

    def _on_dock_toggled(self, shown: bool) -> None:
        """A panel shown by its command takes the focus, so the keyboard can
        work in it at once; Escape or the command again hides it."""
        dock = next(d for d in self._docks() if d.toggleViewAction() is self.sender())
        if shown:
            dock.raise_()
            dock.widget().setFocus(Qt.FocusReason.ShortcutFocusReason)

    def show_panel(self, dock: QDockWidget) -> None:
        """A panel, shown and focused."""
        dock.show()
        dock.raise_()
        dock.widget().setFocus(Qt.FocusReason.OtherFocusReason)

    def show_problems(self) -> None:
        """The Problems panel, shown and focused (the status bar's and the
        top bar's problem count)."""
        self.show_panel(self.problems_dock)

    def _on_guide_navigate(self, target: str) -> None:
        """The Scenario page's guide pointing at a page this window owns:
        the templates (Home) or the first analysis (Run > End of Life)."""
        from .mission_guide import ANALYSES, TEMPLATES

        widget = {TEMPLATES: self.load_scenario_widget, ANALYSES: self.lifetime_widget}.get(target)
        if widget is not None:
            self.show_view(widget)

    def show_view(self, widget: QWidget) -> None:
        """Bring ``widget`` into view: show its area, select the tabs that
        hold it at every level, raise the dock that holds it, or open the
        reference data dialog."""
        if widget is self.data_panel_widget:
            self.data_dialog.show()
            self.data_dialog.raise_()
            self.data_dialog.activateWindow()
            return
        for dock in self._docks():
            if dock.isAncestorOf(widget):
                dock.show()
                dock.raise_()
        current = self.scenario_editor.page_tree.current_page()
        if widget is self.scenario_editor and current is not self.scenario_explainer_widget and \
                not self.scenario_editor.is_editor_page(current):
            self.scenario_editor.show_scenario_page()
        node = widget
        while node is not None and node is not self:
            stack = node.parentWidget()
            if isinstance(stack, AreaStack):
                stack.setCurrentWidget(node)  # an area's page: the rail follows
            elif isinstance(stack, QStackedWidget) and isinstance(stack.parentWidget(), QTabWidget):
                stack.parentWidget().setCurrentWidget(node)
            elif isinstance(stack, QStackedWidget) and getattr(stack, "page_tree", None) is not None:
                stack.page_tree.show_page(node)  # a node of the scenario tree
            elif stack is self.scenario_editor.mode_stack:
                self.scenario_editor.set_json_mode(node is self.scenario_editor.json_page)  # Form or JSON
            node = stack

    def current_view(self) -> QWidget:
        """The innermost page the area shown holds (a scroll area's
        content): in the Scenario area the Scenario Editor on any of its
        own nodes, in Results and Run the tab shown."""
        page = self.areas.currentWidget()
        widget = page.content if isinstance(page, AreaPage) else page
        while True:
            if isinstance(widget, QTabWidget):
                widget = widget.currentWidget()
            elif widget is self.scenario_editor:
                page = widget.page_tree.current_page()
                if widget.is_editor_page(page):
                    return widget
                widget = page
            else:
                break
        return widget.widget() if isinstance(widget, QScrollArea) else widget

    def _show_tree_item(self, item) -> None:
        """The scenario tree's node ``item``: its page, then the node (a
        section of the page, too)."""
        tree = self.scenario_editor.page_tree
        self.show_view(tree.page_of(item))
        tree.tree.setCurrentItem(item)

    def _on_page_action(self) -> None:
        self._show_page(self.sender().data())

    def _on_export_open_requested(self, key: str) -> None:
        """Reports › Exports: the view that makes export ``key``."""
        if key == "model_obj":
            self.on_open_3d_model()
            return
        if key == "monte_carlo_csv" and self.results_views.indexOf(self.monte_carlo_results_widget) < 0:
            self.show_view(self.results_views)
            show_toast(self, "No Monte Carlo batch is shown: run one, or Open Monte Carlo Results...", kind="info")
            return
        views = {"events_csv": self.event_timeline_widget, "output_csv": self.mission_output_widget,
                 "monte_carlo_csv": self.monte_carlo_results_widget, "budget_csv": self.budget_widget,
                 "fsw_project": self.flight_software_widget, "sil_report": self.flight_software_widget,
                 "vizard_file": self.run_page}
        self.show_view(views.get(key, self.results_widget))  # the plot exports: Results › Plots

    def on_open_3d_model(self) -> None:
        """3D Model... (the Scenario area's header, Tools > 3D Model... in the
        palette): the 3D model editor for one of the
        scenario's spacecraft, chosen from a list when there are several."""
        spacecraft_list = self.scenario_editor.spacecraft_list
        names = [config.name for config in spacecraft_list.to_list()]
        if not names:
            self.show_view(self.scenario_editor)
            show_toast(self, "Add a spacecraft first (the Spacecraft page, Add), then build its 3D model",
                       kind="info")
            return
        row = 0
        if len(names) > 1:
            current = max(spacecraft_list.list_widget.currentRow(), 0)
            name, ok = QInputDialog.getItem(self, "3D model", "Spacecraft:", names, current, False)
            if not ok:
                return
            row = names.index(name)
        spacecraft_list.open_model_editor(row)

    def open_3d_model_of(self, name: str) -> None:
        """The 3D model editor for the spacecraft named ``name`` (a Problems
        entry or the Explain badge about its model)."""
        spacecraft_list = self.scenario_editor.spacecraft_list
        names = [config.name for config in spacecraft_list.to_list()]
        if name in names:
            spacecraft_list.open_model_editor(names.index(name))

    def _on_problem_activated(self, text: str) -> None:
        """A double-clicked problem opens where it is fixed (U-12): the
        Scenario Editor at the scenario's own field; the propagation setup,
        a spacecraft's or a ground station's editor at the field; a 3D
        model's problem that spacecraft's model editor."""
        self._show_scenario_editor()
        editor = self.scenario_editor
        location = locate(text, [c.name for c in editor.spacecraft_list.to_list()],
                          [g.name for g in editor.ground_station_list.to_list()])
        if editor.json_mode and (location is None or location.area != JSON_VIEW) and not editor.set_json_mode(False):
            return  # a field of the form, but the JSON text does not apply: its banner says why (M4b)
        if editor.show_range_problem(text):
            return
        if location is None:
            return
        if location.area == SCENARIO:
            editor.focus_field(location.path)
        elif location.area == PROPAGATION:
            editor.edit_propagation_setup(location.path, text)
        elif location.area == SPACECRAFT and location.field == "model":
            self.open_3d_model_of(location.name)
        elif location.area == SPACECRAFT:
            editor.show_spacecraft_problem(location.name, location.path, text)
        elif location.area == GROUND_STATION:
            editor.show_station_problem(location.name, location.path, text)
        elif location.area == MISSION_SEQUENCE:
            editor.show_step(location.path)
        elif location.area == JSON_VIEW:
            editor.show_json()

    def _show_page(self, widget: QWidget) -> None:
        if widget is self.data_panel_widget:
            self._show_data_panel()
        else:
            self.show_view(widget)

    def _show_scenario_editor(self) -> None:
        self.show_view(self.scenario_editor)

    def _on_problems_changed(self, rows: list) -> None:
        """The editor's problems, with the names a message can be about."""
        editor = self.scenario_editor
        self.problems_widget.set_problems(rows, [c.name for c in editor.spacecraft_list.to_list()],
                                          [g.name for g in editor.ground_station_list.to_list()])

    def _on_problem_counts(self, errors: int, warnings: int) -> None:
        """The counts on the panel's title, in the status bar and the top
        bar. An edit that makes a valid scenario invalid opens the Problems
        panel (G8); warnings, and the problems of a scenario just opened,
        only count."""
        if errors and self._error_count == 0 and not self.scenario_editor.opening:
            self.problems_dock.show()
        self._error_count = errors
        count = errors + warnings
        self.problems_dock.setWindowTitle(f"Problems ({count})" if count else "Problems")
        if "view.problems" in getattr(self, "commands", ()):
            # Qt names a dock's toggle after its title: the command keeps its name.
            self.problems_dock.toggleViewAction().setText("&Problems")
            self.commands.refresh_tooltip("view.problems")
        if hasattr(self, "status_items"):
            self.status_items.set_problem_counts(errors, warnings)
        self.top_bar.set_problem_counts(errors, warnings)

    def _on_focus_changed(self, _old, new) -> None:
        """The Inspector follows the focused field in this window."""
        if new is None or not self.isAncestorOf(new) or self.inspector_widget.isAncestorOf(new):
            return
        self.inspector_widget.inspect(new)

    def _on_compare_chosen(self, number) -> None:
        combo = self.results_widget.compare_combo
        combo.setCurrentIndex(max(combo.findData(number), 0) if number is not None else 0)

    def _on_results_compare_changed(self, _index: int) -> None:
        """Results' Compare with changed: the Compare view ticks the pair (U-33)."""
        self.compare_widget.follow_results_choice(self.results_widget.compare_combo.currentData())

    def _refresh_compare_tab(self, *_args) -> None:
        """Compare's runs; while it is hidden, refreshed when next shown (its
        plot took 58-113 ms at the end of every run, M5a)."""
        if not self.compare_widget.isVisibleTo(self):
            self._compare_stale = True
            return
        self._compare_stale = False
        self.compare_widget.set_runs(self.run_history.runs, self.results_widget._current_run,
                                     self.results_widget.compare_combo.currentData(), self.run_history.store_root)

    def _refresh_compare_if_shown(self, *_args) -> None:
        if self._compare_stale and self.compare_widget.isVisibleTo(self):
            self._refresh_compare_tab()

    def eventFilter(self, watched, event):  # noqa: N802 -- Qt API name
        if watched is self.compare_widget and event.type() == QEvent.Type.Show and self._compare_stale:
            QTimer.singleShot(0, self, self._refresh_compare_if_shown)
        return super().eventFilter(watched, event)

    def _on_delete_run(self, record) -> None:
        """Compare's Delete: forget the run and remove it from disk."""
        try:
            self.run_history.delete(record)
        except OSError as exc:
            show_toast(self, f"Could not delete {record.name}: {exc}", kind="error")
            return
        self.results_widget.set_runs(self.run_history.runs, self.results_widget._current_run)
        self._refresh_compare_tab()
        self._refresh_history()
        show_toast(self, f"Deleted {record.name}")

    def _layout_settings(self):
        from PySide6.QtCore import QSettings

        return QSettings(str(Path.home() / ".spacemissionstudio" / "layout.ini"), QSettings.Format.IniFormat)

    def _layout_splitters(self) -> dict:
        """The splitters a layout keeps, by name."""
        return {"scenario": self.scenario_editor.page_tree.splitter,
                "sequence": self.scenario_editor.mission_sequence_editor.splitter,
                "results": self.results_widget.splitter, "results_side": self.results_widget.side_splitter,
                "timeline": self.event_timeline_widget.splitter, "compare": self.compare_widget.content}

    def _layout_group(self) -> str | None:
        """The settings group of the open scenario's layout (M2b: the layout
        is kept per project), or None for a scenario not saved yet."""
        if self._current_path is None:
            return None
        key = hashlib.sha256(str(Path(self._current_path).resolve()).encode("utf-8")).hexdigest()[:16]
        return f"project-{key}"

    def _write_layout(self, settings, group: str) -> None:
        settings.beginGroup(group)
        settings.setValue("state", self.saveState(_LAYOUT_VERSION))
        settings.setValue("rail_collapsed", self.shell.rail.collapsed)
        for name, splitter in self._layout_splitters().items():
            settings.setValue(f"splitter_{name}", splitter.saveState())
        if group.startswith("project-"):
            settings.setValue("path", str(self._current_path))  # for whoever reads the file
        settings.endGroup()

    def _read_layout(self, settings, group: str) -> bool:
        """Apply the layout kept under ``group``; False when there is none."""
        settings.beginGroup(group)
        try:
            state = settings.value("state")
            if state is None:
                return False
            self.restoreState(state, _LAYOUT_VERSION)
            self.rail_collapse_action.setChecked(settings.value("rail_collapsed", False, type=bool))
            for name, splitter in self._layout_splitters().items():
                saved = settings.value(f"splitter_{name}")
                if saved is not None:
                    splitter.restoreState(saved)
            return True
        finally:
            settings.endGroup()

    def _restore_layout(self) -> None:
        settings = self._layout_settings()
        geometry = settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._read_layout(settings, "window")

    def _save_layout(self) -> None:
        """The window's layout, and the open project's (M2b)."""
        settings = self._layout_settings()
        settings.setValue("window/geometry", self.saveGeometry())
        self._write_layout(settings, "window")
        self._save_project_layout(settings)
        settings.sync()

    def _save_project_layout(self, settings=None) -> None:
        group = self._layout_group()
        if group is None:
            return
        settings = settings or self._layout_settings()
        self._write_layout(settings, group)
        settings.sync()

    def _restore_project_layout(self) -> None:
        """The open project's layout, when it has one; otherwise the layout
        stays as it is."""
        group = self._layout_group()
        if group is not None:
            self._read_layout(self._layout_settings(), group)

    def _on_theme_chosen(self) -> None:
        """A theme command (Settings > Appearance): remember the choice and apply it now."""
        value = self.sender().data()
        set_theme_setting(value)
        app = QApplication.instance()
        mode = resolve_theme(value, app)
        if mode != current_theme():
            apply_theme(app, mode)
        follow_system(app)
        report(self, f"Theme: {value}. It is the theme shown now.", kind="info")

    def reset_layout(self) -> None:
        """Reset Layout: the panels and the rail as a new window has them."""
        self.restoreState(self._default_layout, _LAYOUT_VERSION)
        for dock in self._docks():
            dock.show()
        self._hide_default_panels()
        self.rail_collapse_action.setChecked(False)

    def _hide_default_panels(self) -> None:
        """The panels a new window starts without (G8): Problems, which a
        new error opens, and the Inspector on a screen narrower than
        _INSPECTOR_MIN_SCREEN_PX. Ctrl+J and Ctrl+I show them."""
        self.problems_dock.hide()
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None and screen.availableGeometry().width() < _INSPECTOR_MIN_SCREEN_PX:
            self.side_dock.hide()

    def on_user_manual(self) -> None:
        from .help_dialog import ManualDialog

        dialog = ManualDialog(self)
        dialog.setModal(False)
        dialog.show()
        self._manual_dialog = dialog  # keep it alive while it is open

    def palette_entries(self):
        """For the command palette: every command of the registry (by its
        category and, as keywords, its old names), every area and page,
        the scenario's objects (its tree), the templates and every series
        of the result shown."""
        from .command_palette import PaletteEntry, command_entries

        entries = [e for e in command_entries(self.commands) if e.label != "Help > Command Palette..."]
        for area in self.shell.page_areas():
            if area.id == "scenario":
                continue  # its tree's paths below
            entries.append(PaletteEntry(f"Go to > {area.label}", lambda area_id=area.id: self.shell.show_area(area_id),
                                        keywords="events" if area.id == "timeline" else ""))
        for path, item in self.scenario_editor.page_tree.paths():
            entries.append(PaletteEntry(f"Go to > Scenario > {path}", lambda item=item: self._show_tree_item(item)))
        entries.append(PaletteEntry("Go to > Scenario > JSON", lambda: self.show_view(self.scenario_editor.json_page),
                                    keywords="form text"))
        for area_label, tabs in (("Results", self.results_views), ("Run", self.run_views),
                                 ("Reports", self.reports_views)):
            for index in range(tabs.count()):
                page = tabs.widget(index)
                entries.append(PaletteEntry(f"Go to > {area_label} > {tabs.tabText(index).replace('&', '')}",
                                            lambda page=page: self.show_view(page)))
        for dock in self._docks():
            entries.append(PaletteEntry(f"Go to panel > {dock.windowTitle().split(' (')[0]}",
                                        lambda dock=dock: self.show_panel(dock)))
        for section, label in self.settings_page.sections():
            entries.append(PaletteEntry(f"Settings > {label}",
                                        lambda section=section: self.show_settings(section)))
        from .load_scenario_widget import TEMPLATES_DIR

        for path in sorted(TEMPLATES_DIR.glob("*.json")):
            entries.append(PaletteEntry(f"Open template > {path.stem.replace('_', ' ')}",
                                        lambda path=path: self._on_load_scenario_path_chosen(path)))
        result = self.results_widget._result
        for name in sorted(result.series) if result is not None else []:
            entries.append(PaletteEntry(f"Show series > {name}", lambda name=name: self._show_series(name)))
        return entries

    def show_settings(self, section: str = "") -> None:
        """The Settings area, at ``section`` ("keyboard", "appearance", ...)."""
        self.shell.show_area("settings")
        if section:
            self.settings_page.show_section(section)

    def _show_series(self, name: str) -> None:
        self.results_widget.show_series(name)
        self.show_view(self.results_widget)

    def on_command_palette(self) -> None:
        from .command_palette import CommandPalette

        CommandPalette(self.palette_entries(), self).exec()

    def on_keyboard_shortcuts(self) -> None:
        """The shortcut list: Settings > Keyboard, generated from the registry."""
        self.show_settings("keyboard")

    def on_about(self) -> None:
        import importlib.util

        import spacemissionstudio

        basilisk_status = (
            "available" if importlib.util.find_spec("Basilisk") is not None
            else "not installed/built -- see SpaceMissionStudio/README.md"
        )
        QMessageBox.about(
            self, "About SpaceMissionStudio",
            f"<b>SpaceMissionStudio</b> {spacemissionstudio.__version__}<br><br>"
            "A GUI-based mission-analysis application built on the Basilisk "
            "astrodynamics framework (AVS Lab, University of Colorado Boulder).<br><br>"
            f"Basilisk: {basilisk_status}",
        )

    def _update_window_title(self) -> None:
        name = self._current_path.name if self._current_path else "untitled"
        star = "*" if self._dirty else ""
        self.setWindowTitle(f"SpaceMissionStudio -- {name}{star}")
        self._refresh_top_bar()

    def _refresh_top_bar(self) -> None:
        if hasattr(self, "top_bar"):  # the editor emits changes while the window is still being built
            self.top_bar.set_scenario(self.scenario_editor.name_edit.text().strip(), self._dirty,
                                      source_of(self._current_path, TEMPLATES_DIR))

    def _scenario_dir(self) -> Path | None:
        """The open scenario file's folder (a 3D model's mesh paths are relative to it)."""
        return self._current_path.parent if self._current_path is not None else None

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._update_window_title()

    def _refresh_scenario_explainer(self) -> None:
        # Same "silently skip a tick where the in-memory scenario doesn't
        # currently validate" tolerance as _on_autosave_tick -- this runs
        # on every keystroke (via ScenarioEditorWidget.changed), so a
        # momentarily-invalid mid-edit state (e.g. a required field
        # briefly blank) must never raise an error dialog the user didn't
        # directly trigger. ScenarioExplainerWidget.set_scenario(None)
        # shows its own short placeholder instead of crashing.
        try:
            scenario = self.scenario_editor.to_scenario()
        except ScenarioValidationError:
            scenario = None
        self.scenario_explainer_widget.request(scenario)  # 250 ms after the last edit, in a worker (M4b)
        self._refresh_stale_banner(scenario)
        self._refresh_top_bar()
        self.lifetime_widget.set_scenario(scenario)
        self.budget_widget.set_scenario(scenario)
        self.flight_software_widget.set_base_dir(self._current_path.parent if self._current_path else None)
        self.flight_software_widget.set_scenario(scenario)
        self._update_monte_carlo_tab(scenario)

    def _on_explained(self) -> None:
        # The Overview node's title says when there's something to check, so
        # it's seen even by someone who never reads it before pressing Run.
        count = self.scenario_explainer_widget.warning_count
        self.scenario_editor.page_tree.set_title(self.overview_item,
                                                 f"Overview ({count} to check)" if count else "Overview")

    def _update_monte_carlo_tab(self, scenario=None) -> None:
        """The Monte Carlo tab is shown while it has something to show or
        the scenario has Monte Carlo on: nine tabs no longer fit a
        typical window, and most scenarios never use it."""
        wanted = (self.monte_carlo_results_widget.batch is not None
                  or (scenario is not None and scenario.monte_carlo.enabled))
        self._set_monte_carlo_tab(wanted)

    def _set_monte_carlo_tab(self, wanted: bool) -> None:
        widget = self.monte_carlo_results_widget
        index = self.results_views.indexOf(widget)
        if wanted and index < 0:
            self.results_views.addTab(widget, "Monte Carlo")
        elif not wanted and index >= 0:
            self.results_views.removeTab(index)  # the widget stays, hidden, as the tab stack's child

    def _show_monte_carlo_tab(self) -> None:
        self._set_monte_carlo_tab(True)
        self.show_view(self.monte_carlo_results_widget)

    def on_open_monte_carlo_results(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Monte Carlo results")
        if not folder:
            return
        if self.monte_carlo_results_widget.load_folder(folder):
            self._show_monte_carlo_tab()
        else:
            report(self, f"No Monte Carlo results in {folder}: {self.monte_carlo_results_widget.hint_label.text()}",
                   kind="warning")

    def _mark_clean(self) -> None:
        self._dirty = False
        self._update_window_title()
        # Every path that reaches a clean state -- a real Save, New,
        # Open, or an explicit discard via _confirm_discard_unsaved --
        # funnels through here, so this is the one place that needs to
        # clear a pending autosave recovery file: see gui.autosave's own
        # module docstring for why a stale one left behind would be
        # worse than not having this feature at all.
        autosave.clear_recovery_file()

    def _on_autosave_tick(self) -> None:
        """Runs every ``_AUTOSAVE_INTERVAL_MS`` -- see that constant's
        own comment. No-ops unless the editor is actually dirty (the
        common case between edits), and SILENTLY skips a tick where the
        in-memory scenario doesn't currently validate (e.g. mid-edit
        with a required field momentarily blank) rather than surfacing
        an error dialog on a timer the user didn't directly trigger --
        the next tick simply tries again once the edit settles, same
        tolerance a real Save already has via
        ``ScenarioEditorWidget.to_scenario()`` itself.
        """
        if not self._dirty:
            return
        try:
            scenario = self.scenario_editor.to_scenario()
        except ScenarioValidationError:
            return
        autosave.write_recovery_file(scenario, self._current_path)

    def _check_autosave_recovery(self) -> None:
        """Startup offer to restore a previous session's crash-recovery
        file -- see ``gui.autosave``'s own module docstring. Declining
        is treated the same as an explicit discard (the recovery copy
        is cleared immediately, not left to prompt again next launch);
        accepting loads it into the editor and marks the window DIRTY,
        not clean -- the recovered content is exactly the UNSAVED state
        from before the crash, so it still needs an explicit Save (to
        ``original_path``, or Save As if there wasn't one yet) before
        it's actually safe on disk again.
        """
        info = autosave.read_recovery_file()
        if info is None:
            return
        label = str(info.original_path) if info.original_path is not None else "a new, never-yet-saved scenario"
        response = QMessageBox.question(
            self, "Restore unsaved changes?",
            f"SpaceMissionStudio did not close cleanly last time. Unsaved changes to {label} were "
            f"autosaved at {info.saved_at_utc} (UTC). Restore them?",
            QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Discard,
            QMessageBox.StandardButton.Discard,
        )
        if response != QMessageBox.StandardButton.Open:
            autosave.clear_recovery_file()
            return
        self.scenario_editor.from_scenario(info.scenario)
        self._reset_history()
        self._refresh_scenario_explainer()
        self._current_path = info.original_path
        if hasattr(self, "run_page"):
            self._recall_archive_dir()  # this scenario's Monte Carlo archive folder (M5b)
        self._clear_run_views()
        self._mark_dirty()
        self.statusBar().showMessage("Restored autosaved changes.")
        show_toast(self, "Restored autosaved changes")
        self.show_view(self.scenario_editor)

    # -- undo and redo ----------------------------------------------------

    def _editor_state(self):
        """The edited scenario as a dict, valid or not (a scenario being built
        from scratch is invalid until it has a spacecraft); None if the form
        cannot be read at all."""
        try:
            return self.scenario_editor.draft_scenario().to_dict()
        except Exception:  # noqa: BLE001 -- a half-edited form must never break undo
            _logger.debug("Undo: the edited scenario could not be read", exc_info=True)
            return None

    def _reset_history(self) -> None:
        self._history_timer.stop()
        self._history.reset(self._editor_state())
        self._update_undo_actions()

    def _schedule_history(self) -> None:
        if not self._restoring_history:
            self._history_timer.start()

    def _record_history(self) -> None:
        state = self._editor_state()
        if state is not None and self._history.record(state):
            self._update_undo_actions()

    def _update_undo_actions(self) -> None:
        if hasattr(self, "undo_action"):
            self.undo_action.setEnabled(self._history.can_undo())
            self.redo_action.setEnabled(self._history.can_redo())

    def on_undo(self) -> None:
        if self._history_timer.isActive():  # the edit just made counts first
            self._history_timer.stop()
            self._record_history()
        self._restore_history(self._history.undo(), "Undone.")

    def on_redo(self) -> None:
        self._restore_history(self._history.redo(), "Redone.")

    def _restore_history(self, state, message: str) -> None:
        if state is None:
            return
        self._restoring_history = True
        try:
            self.scenario_editor.from_scenario(Scenario.from_dict(state))
        finally:
            self._restoring_history = False
        self._history_timer.stop()
        current = self._editor_state()
        if current is not None:
            self._history.replace_current(current)
        self._refresh_scenario_explainer()
        self._mark_dirty()
        self._update_undo_actions()
        self.statusBar().showMessage(message)

    def _refresh_stale_banner(self, scenario: Scenario | None) -> None:
        """Show the stale-results banner when the run the views show was
        made from a different scenario than the editor's (``scenario`` is
        the editor's, or ``None`` while it does not validate). The hashes
        are the run provenance's (output_provenance.scenario_sha256), so
        undoing back to the run's scenario hides the banner again."""
        if self._shown_run_sha256 is None:
            self._stale_state = None
        elif scenario is None:
            self._stale_state = "invalid"
        elif output_provenance.scenario_sha256(scenario) != self._shown_run_sha256:
            self._stale_state = "valid"
        else:
            self._stale_state = None
        self._apply_stale_banner()

    def _apply_stale_banner(self, *_args) -> None:
        """The banner shows while a run view (Results, Events, Compare) is,
        not above the editor the change is being made in."""
        run_views = (self.results_widget, self.mission_dashboard_widget, self.mission_output_widget,
                     self.monte_carlo_results_widget, self.event_timeline_widget, self.compare_widget)
        if getattr(self, "_stale_state", None) and hasattr(self, "shell") and self.current_view() in run_views:
            self.stale_results_banner.show_stale(scenario_valid=self._stale_state == "valid")
        else:
            self.stale_results_banner.hide()

    def _set_shown_run(self) -> None:
        """The views now show the last run: remember its scenario's hash."""
        if self._last_run_scenario is not None:
            self._shown_run_sha256 = output_provenance.scenario_sha256(self._last_run_scenario)
        self._refresh_scenario_explainer()

    def _clear_run_views(self) -> None:
        """Clear every view of the previous run, and the time cursor."""
        self.finish_run_end()
        self._shown_run_sha256 = None
        self.stale_results_banner.hide()
        self.results_widget.set_result(None)
        self.results_overview.set_run(None)
        self.mission_dashboard_widget.set_result(None)
        self.mission_output_widget.clear()
        self.event_timeline_widget.set_result(None)
        self.results_widget.set_vizard_file(None)
        self.results_widget.set_runs(self.run_history.runs, None)
        self._refresh_compare_tab()
        self.time_cursor.clear()

    def _keep_run(self, result, cancelled: bool) -> None:
        """Keep the run for comparison (gui.run_history) and offer the earlier ones."""
        if self._last_run_scenario is None:
            return
        record = self.run_history.add(self._last_run_scenario.to_dict(), result, self._last_run_epoch_utc or "",
                                      cancelled=cancelled)  # saved in a worker: _on_run_saved
        self.results_widget.set_runs(self.run_history.runs, record)
        self.results_overview.set_run(result, record.name,
                                      result.provenance.to_dict() if result.provenance is not None else None)
        self._refresh_compare_tab()
        mode = "SIL" if getattr(self, "_last_run_sil", False) else "Single"
        self._run_modes[record.number], self._run_seconds[record.number] = mode, self.last_run_seconds
        took = f" in {_duration_text(self.last_run_seconds)}" if self.last_run_seconds is not None else ""
        _run_logger.info("Run %d %s%s: %s, %d series", record.number, "cancelled" if cancelled else "done", took,
                         record.scenario.get("name", ""), len(result.series))
        for warning in getattr(result, "warnings", []) or []:
            _run_logger.warning("Run %d: %s", record.number, warning)
        self._refresh_history()

    def _on_runs_loaded(self) -> None:
        """The earlier sessions' runs are listed (read in a worker, M5a)."""
        self.results_widget.set_runs(self.run_history.runs, self.results_widget._current_run)
        self._refresh_compare_tab()
        self._refresh_history()

    def _on_run_saved(self, record) -> None:
        """A run's save ended: a run that could not be saved stays for this
        session only, and says so."""
        if self.run_history.last_save_error:
            show_toast(self, f"{record.name} is not saved for later sessions: see the Log", kind="warning")
            _run_logger.warning("Run %d is not saved: %s", record.number, self.run_history.last_save_error)
        elif record.saved is not None:
            _run_logger.info("Run %d saved to %s", record.number, self.run_history.store_root / record.saved.run_id)
        self._refresh_compare_tab()
        self._refresh_history()

    # -- Run > History (M5a) ---------------------------------------------------------
    def _saved_text(self, record) -> str:
        if record.saved is not None or record.earlier_session:
            return "Saved"
        return "Saving..." if self.run_history.is_saving(record) else "This session only"

    def _refresh_history(self) -> None:
        entries = [run_entry(record, self._saved_text(record), self._run_modes.get(record.number, ""),
                             self._run_seconds.get(record.number)) for record in self.run_history.runs]
        self.history_view.set_entries(entries + self._history_extra)

    def _add_history_extra(self, status: str, mode: str, detail: str) -> None:
        """A failed run or a batch: listed for this session (the run store keeps neither)."""
        now = datetime.now(UTC)
        scenario = self._last_run_scenario.name if self._last_run_scenario is not None else ""
        self._history_extra.append(HistoryEntry(
            status=status, scenario=scenario, mode=mode, started_utc=utc_text(self._run_started_at),
            duration_s=self.last_run_seconds, saved="Not kept" if status == "failed" else "",
            detail=detail, order=now.timestamp()))
        self._refresh_history()

    def _show_history_run(self, record) -> None:
        """A double-clicked run of History: drawn dashed beside the shown run
        in Results (or Results, when it is the run shown)."""
        if self.results_widget._current_run is None or record.number != self.results_widget._current_run.number:
            self._on_compare_chosen(record.number)
        self.show_view(self.results_widget)

    def _offer_vizard_playback(self) -> None:
        """Show "Open in Vizard" on Results when the run wrote a playback file."""
        path = self._last_run_vizard_file
        if path and Path(path).is_file():
            export_log.record("vizard_file", path)  # Reports › Exports
        self.results_widget.set_vizard_file(path if path and Path(path).is_file() else None)

    def open_vizard_playback(self, path: str) -> bool:
        """Start Vizard on ``path`` (``-loadFile``); False if it could not be started."""
        if not path or not Path(path).is_file():
            report(self, f"No Vizard playback file: {path} is not there", kind="warning")
            return False
        executable = find_vizard_executable() or self._locate_vizard()
        if executable is None:
            return False
        try:
            launch_vizard(executable, load_file=Path(path))
        except OSError as exc:
            report(self, f"Could not launch Vizard ({executable}): {exc}")
            return False
        self.statusBar().showMessage(f"Opened {path} in Vizard.")
        return True

    def _on_time_cursor_changed(self, time_s) -> None:
        self.time_cursor_label.setVisible(time_s is not None)
        if time_s is not None:
            self.time_cursor_label.setText("Cursor " + describe_time(time_s, self._last_run_epoch_utc))

    def _confirm_discard_unsaved(self) -> bool:
        """Returns True if it's OK to proceed (no unsaved changes, the user
        saved them, or the user explicitly said to discard them) -- never
        silently discards. Save, Discard or Cancel (audit G6): Save is
        File > Save (Save As for a scenario with no file), and goes ahead
        only once the file is written.
        """
        if not self._dirty:
            return True
        response = QMessageBox.question(
            self, "Unsaved changes",
            f"Save the changes to {self.scenario_editor.name_edit.text() or 'this scenario'} first? "
            "Changes not saved cannot be recovered.",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if response == QMessageBox.StandardButton.Save:
            self.on_save()
            return not self._dirty  # a cancelled Save As, or a save that failed, leaves it unsaved
        return response == QMessageBox.StandardButton.Discard

    # -- File actions ---------------------------------------------------------
    def on_new(self) -> None:
        if not self._confirm_discard_unsaved():
            return
        self._save_project_layout()
        self.scenario_editor.reset_to_default()
        self._reset_history()
        self._refresh_scenario_explainer()
        self._current_path = None
        if hasattr(self, "run_page"):
            self._recall_archive_dir()  # this scenario's Monte Carlo archive folder (M5b)
        self._clear_run_views()
        self._mark_clean()
        self.statusBar().showMessage("New blank scenario, in Orbit only: the Scenario page guides the next steps.")
        show_toast(self, "New blank scenario")
        self.scenario_editor.show_scenario_page()
        self.show_view(self.scenario_editor)

    def on_open(self) -> None:
        if not self._confirm_discard_unsaved():
            return
        path_str, _selected_filter = QFileDialog.getOpenFileName(self, "Open scenario", "", _FILE_FILTER)
        if not path_str:
            return
        self.open_path(Path(path_str))

    def _on_load_scenario_path_chosen(self, path) -> None:
        """Handles LoadScenarioWidget.path_chosen -- a template picked
        from its built-in list, or a file picked via its own "Browse for
        a file..." button. Gated by the same unsaved-changes confirmation
        as File > New/Open, since it replaces the scenario currently
        being edited exactly like those do.
        """
        if not self._confirm_discard_unsaved():
            return
        self.open_path(Path(path))

    def _on_load_scenario_customized(self, scenario: Scenario) -> None:
        """Handles LoadScenarioWidget.scenario_customized -- a template
        run through gui.template_wizard.TemplateCustomizeWizard, with its
        curated fields already applied to an in-memory Scenario copy (see
        that module's own docstring). Same unsaved-changes gate as
        _on_load_scenario_path_chosen; unlike that path there is no file
        yet, so this validates the wizard's result here (the one thing
        load_scenario() would otherwise have done for a file-backed open)
        before handing off to _open_scenario with no path -- the user
        must File > Save As before this can overwrite anything, so the
        original template file on disk is never at risk.
        """
        if not self._confirm_discard_unsaved():
            return
        try:
            scenario.validate()
        except ScenarioValidationError as exc:
            report(self, f"Could not open the customized scenario: {exc}")
            return
        self._open_scenario(scenario, current_path=None, verb="Customized")

    def open_path(self, path: Path) -> bool:
        try:
            scenario = load_scenario(path)
        except ScenarioValidationError as exc:
            report(self, f"Could not open {path}: {exc}")
            return False
        self._open_scenario(scenario, current_path=path, verb="Opened")
        self._remember_recent(path)
        return True

    def _remember_recent(self, path: Path) -> None:
        """Home's recent scenarios: a file opened or saved, except the
        built-in templates (Home shows them as cards)."""
        try:
            if Path(path).resolve().parent == TEMPLATES_DIR:
                return
            recent_files.remember(path)
        except OSError:  # the settings file could not be written: the list is a convenience
            _logger.exception("Could not remember %s as a recent scenario", path)
            return
        self.load_scenario_widget.refresh_recent()

    def _open_scenario(self, scenario: Scenario, current_path: Path | None, verb: str) -> None:
        """Shared tail end of open_path()/_on_load_scenario_customized():
        loads ``scenario`` into the editor and resets every piece of
        per-scenario state (results, mission output, dirty flag, current
        -path) the same way regardless of where the Scenario came from.
        ``current_path=None`` (the wizard path) leaves on_save() routing
        through on_save_as() -- see that method -- rather than silently
        picking a path to write to.
        """
        self._save_project_layout()
        self.scenario_editor.from_scenario(scenario)
        # The guide opens for a scenario still without spacecraft; an
        # opened mission keeps its description in view, the guide folded.
        self.scenario_editor.mission_guide.set_expanded(not scenario.spacecraft)
        self._reset_history()
        self._refresh_scenario_explainer()
        self._current_path = current_path
        if hasattr(self, "run_page"):
            self._recall_archive_dir()  # this scenario's Monte Carlo archive folder (M5b)
        self._restore_project_layout()
        self._clear_run_views()
        self._mark_clean()
        label = str(current_path) if current_path is not None else scenario.name
        self.statusBar().showMessage(f"{verb} {label}")
        show_toast(self, f"{verb} {current_path.name if current_path is not None else scenario.name}")
        self.show_view(self.scenario_editor)

    def on_save(self) -> None:
        # A built-in template is where the scenario came from, not a file
        # to save over: Save goes to Save As (audit of 2026-10-27, G1).
        if self._current_path is None or _is_template(self._current_path):
            self.on_save_as()
            return
        self._save_to(self._current_path)

    def on_save_as(self) -> None:
        # From a template, the dialog starts in the home folder under the
        # template's file name; otherwise where the dialog last was.
        start = str(Path.home() / self._current_path.name) if _is_template(self._current_path) else ""
        path_str, _selected_filter = QFileDialog.getSaveFileName(self, "Save scenario as", start, _FILE_FILTER)
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix != ".json":
            path = path.with_suffix(".json")
        if _is_template(path):
            report(self, f"{path.name} is in the built-in templates folder, which the app keeps as shipped. "
                         "Save the scenario in another folder.", kind="warning")
            return
        self._save_to(path)

    def _save_to(self, path: Path) -> None:
        try:
            scenario: Scenario = self.scenario_editor.to_scenario()
        except ScenarioValidationError as exc:
            self._open_problem(f"Cannot save: {self.scenario_editor.problem_display(str(exc))}", str(exc))
            return
        try:
            scenario.save(path)
        except OSError as exc:  # unwritable folder, a file in the path, a full disk (audit M9)
            report(self, f"Could not save the scenario to {path}: {exc}\n"
                         "The previous file, if there was one, is unchanged.")
            return
        self._current_path = path
        if hasattr(self, "run_page"):
            self._recall_archive_dir()  # this scenario's Monte Carlo archive folder (M5b)
        self._save_project_layout()
        self._mark_clean()
        self._remember_recent(path)
        self.statusBar().showMessage(f"Saved {path}")
        show_toast(self, f"Saved {path.name}")

    # -- run-in-progress feedback -------------------------------------------
    def _set_running(self, running: bool) -> None:
        """Disables every Run-menu action while ANY run (single or Monte
        Carlo) is in flight -- previously only the action that started the
        run was disabled, so e.g. Run Monte Carlo could be triggered while a
        single run's worker was still using ``self._run_worker``, silently
        losing track of it. One run at a time.
        """
        for action in (self.run_action, self.live_plot_action, self.vizard_action,
                       self.vizard_launch_action, self.check_kernels_action, *self.run_mode_group.actions()):
            action.setEnabled(not running)
        for button in (getattr(self, "run_mode_button", None), getattr(self, "run_mode_control", None)):
            if button is not None:
                button.setEnabled(not running)

    def _start_busy(self, message: str, determinate: bool = False, cancellable: bool = True,
                    cancel_note: str = "") -> None:
        """A run starts: the progress strip shows ``message`` until the run
        reports its phase; its bar is busy until the run reports a fraction
        (``determinate``: it starts at 0 %)."""
        self.finish_run_end()  # the last run's views, before this one's
        self._set_running(True)
        self._busy_elapsed.start()
        self._run_started_at = datetime.now(UTC)
        self.run_progress.start(message.rstrip("."), cancellable=cancellable, cancel_note=cancel_note)
        if determinate:
            self.run_progress.set_fraction(0.0)
        self._busy_timer.start()
        self._run_started_s = time.monotonic()
        self.run_chip.set_state("running", "Running")
        self.run_chip.hide()  # the job beside it says the same, with its bar
        self.statusBar().showMessage(message)

    def _stop_busy(self, message: str, chip_state: str = "idle", chip_text: str = "Ready",
                   run_name: str = "") -> None:
        """End the busy state; the chip shows ``chip_state``, the top bar the
        run's start time and length when it ran. ``run_name`` ("Run 2")
        names a run that is kept (U-22)."""
        self.last_run_seconds = None
        if self._run_started_s is not None:
            seconds = time.monotonic() - self._run_started_s
            self.last_run_seconds = seconds
            if chip_state in ("done", "failed", "cancelled"):
                chip_text = f"{chip_text} in {_duration_text(seconds)}" if chip_state == "done" else chip_text
                if run_name:
                    chip_text = f"{run_name}: {chip_text[0].lower()}{chip_text[1:]}"
                self.top_bar.set_last_run(f"{run_name + ' at ' if run_name else 'last run '}"
                                          f"{time.strftime('%H:%M')}, {chip_state}, {_duration_text(seconds)}")
            self._run_started_s = None
        self.run_chip.set_state(chip_state, chip_text)
        self.run_chip.show()
        self._set_running(False)
        self.abort_action.setEnabled(False)
        self._busy_timer.stop()
        self._mc_poll.stop()
        self.run_progress.finish()
        self.statusBar().showMessage(message)

    def _report_run_problem(self, text: str, view=None, level: int = logging.ERROR) -> None:
        """A run could not start, or went wrong (U-23, U-39): written to the
        Log (where it stays), said in a toast and the status bar, and the view
        where it is dealt with opened. No message box: those are kept for
        confirming what cannot be undone. ``run_problems`` keeps the texts."""
        self.run_problems.append(text)
        _logger.log(level, "%s", text)
        first = text.strip().splitlines()[0] if text.strip() else text
        short = first if len(first) <= 160 else first[:157] + "..."
        kind = "error" if level >= logging.ERROR else "warning" if level >= logging.WARNING else "info"
        show_toast(self, short, kind=kind, duration_ms=6000)
        self.statusBar().showMessage(first)
        if view is not None:
            self.show_view(view)

    def _cannot_run(self, exc: Exception) -> None:
        """The scenario is not valid: say so, and open the problem at its field."""
        text = self.scenario_editor.problem_display(str(exc))
        self._report_run_problem(f"Cannot run: {text}", level=logging.WARNING)
        self._show_problem_at_field(str(exc))

    def _open_problem(self, text: str, problem: str) -> None:
        """Say ``text`` (a toast, the status bar, the Log) and open
        ``problem`` at its field, as a refused run does (U-39)."""
        report(self, text, kind="warning")
        self._show_problem_at_field(problem)

    def _show_problem_at_field(self, problem: str) -> None:
        self.problems_dock.show()
        self._on_problem_activated(problem)

    def _update_busy_elapsed(self) -> None:
        """The status chip mirrors the strip: the percentage when the run
        reports one, else the time elapsed."""
        seconds = self._busy_elapsed.elapsed() // 1000
        self.run_progress.refresh_time()
        if self._busy_progress.maximum() > 0:
            self.run_chip.set_state("running", f"Running {self._busy_progress.value()} %")
        else:
            self.run_chip.set_state("running", f"Running {seconds // 60}:{seconds % 60:02d}")

    # -- Run --------------------------------------------------------------
    def on_configure_vizard(self) -> None:
        """Vizard Configuration: the Vizard options, on Run > Run (M5b)."""
        self.show_view(self.run_page.vizard_section)
        if self.run_page.vizard_form is not None:
            self.run_page.vizard_form.setFocus()

    def _on_vizard_edited(self, request) -> None:
        """The Run page's Vizard form, applied as it is edited (M5b)."""
        self._vizard_request = request
        self.statusBar().showMessage("Vizard disabled for the next run." if request is None
                                     else "Vizard enabled for the next run.")

    # -- Run > Run: the Monte Carlo archive folder, the SIL spacecraft (M5b) ---------------
    def _archive_key(self) -> str:
        name = str(self._current_path.resolve()) if self._current_path is not None else \
            f"unsaved:{self.scenario_editor.name_edit.text().strip()}"
        return "monte_carlo_archive/" + hashlib.sha256(name.encode("utf-8")).hexdigest()

    def _remember_archive_dir(self, folder: str) -> None:
        """The Monte Carlo archive folder of this scenario, for next time."""
        from .recent_files import _settings

        settings = _settings()
        if folder:
            settings.setValue(self._archive_key(), folder)
        else:
            settings.remove(self._archive_key())

    def _recall_archive_dir(self) -> None:
        from .recent_files import _settings

        self.run_page.set_archive_dir(str(_settings().value(self._archive_key(), "") or ""))

    def _refresh_run_page(self, *_args) -> None:
        """The SIL spacecraft, when the Run page is shown in SIL mode."""
        if self.run_mode != "sil" or not self.run_page.isVisibleTo(self):
            return
        from .fsw_workbench_widget import exportable_reason

        try:
            scenario = self.scenario_editor.to_scenario()
        except ScenarioValidationError:
            return
        names = [sc.name for sc in scenario.spacecraft if exportable_reason(scenario, sc) is None]
        self.run_page.set_sil_spacecraft(names, self.flight_software_widget._folder_of)

    def _locate_vizard(self) -> Path | None:
        """Called only when :func:`find_vizard_executable` came up empty.
        Offers "Download Vizard" (automatic -- an explicit click, never
        automatic on its own; see ``gui.vizard_launcher``'s own module
        docstring on the "closed-off/offline policy" that still gates it)
        alongside the original manual "Browse...". Returns the resolved,
        already-``remember_vizard_executable``'d path, or ``None`` if the
        user cancelled/dismissed both options or a download genuinely
        failed (an error dialog was already shown in that case) --
        :meth:`on_launch_vizard` treats that exactly like its own previous
        "user cancelled the browse prompt" case.
        """
        box = QMessageBox(self)
        box.setWindowTitle("Vizard not found")
        box.setText(
            "Vizard wasn't found automatically. SpaceMissionStudio can download AVS's own pre-built Vizard "
            "for this platform, or you can browse for an existing install."
        )
        download_button = box.addButton("Download Vizard", QMessageBox.ButtonRole.AcceptRole)
        browse_button = box.addButton("Browse...", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()

        if clicked is download_button:
            return self._fetch_vizard_with_progress()

        if clicked is browse_button:
            path_str, _selected_filter = QFileDialog.getOpenFileName(self, "Locate the Vizard application")
            if not path_str:
                return None
            executable = Path(path_str)
            remember_vizard_executable(executable)
            return executable

        return None

    def _fetch_vizard_with_progress(self) -> Path | None:
        """Runs :class:`~.vizard_launcher.VizardFetchWorker` on a
        background thread while blocking THIS method (not the whole
        event loop -- see below) behind a modal, cancellable progress
        dialog. Blocking here, rather than connecting to the worker's
        signals and returning immediately, keeps :meth:`on_launch_vizard`'s
        existing synchronous ``bool`` return contract (also relied on by
        :meth:`on_run`'s live-stream gate) unchanged -- see
        ``VizardFetchWorker``'s own docstring.

        A nested ``QEventLoop`` (not a plain blocking call) is what makes
        this safe: it keeps pumping Qt's event loop -- repainting the
        progress dialog, handling the Cancel button -- while genuinely
        waiting for the worker thread, rather than freezing the whole GUI
        for the download's duration.
        """
        progress = QProgressDialog("Downloading Vizard...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        worker = VizardFetchWorker(parent=self)
        loop = QEventLoop()
        outcome: dict = {}

        def on_status(message: str) -> None:
            progress.setLabelText(message)

        def on_finished_ok(path_str: str) -> None:
            outcome["path"] = path_str
            loop.quit()

        def on_failed(message: str) -> None:
            outcome["error"] = message
            loop.quit()

        worker.status.connect(on_status)
        worker.finished_ok.connect(on_finished_ok)
        worker.failed.connect(on_failed)
        progress.canceled.connect(worker.request_cancel)  # cooperative -- see VizardFetchWorker's own docstring

        worker.start()
        progress.show()
        # QEventLoop.quit() is a no-op if the loop isn't running YET (Qt's
        # own documented behavior, confirmed the hard way -- a first
        # version of this method assumed quit()-before-exec() would make
        # the next exec() return immediately, which hung instead): a real
        # QThread's start() returns almost instantly, well before its
        # background run() has a chance to emit finished_ok/failed, so
        # this only matters for a worker that happens to finish
        # SYNCHRONOUSLY inside start() itself. Checking outcome first
        # covers exactly that case without affecting the real one.
        if not outcome:
            loop.exec()
        progress.close()
        worker.wait()

        if "path" in outcome:
            executable = Path(outcome["path"])
            remember_vizard_executable(executable)
            return executable

        error = outcome.get("error", "download cancelled")
        if error != "download cancelled":
            report(self, f"Could not download Vizard: {error}")
        return None

    def on_launch_vizard(self) -> bool:
        """Starts the external Vizard application -- a no-op if an
        instance already running is already suitable (see below).
        Distinct from :meth:`on_configure_vizard`, which never touches a
        process at all: it only decides how the NEXT run feeds an
        instance of Vizard, wherever/however that instance got started.

        When the current Vizard Configuration is set to live-stream,
        Vizard is launched with its own ``-directComm`` command-line
        argument (see ``vizard_launcher.DEFAULT_LIVE_STREAM_ADDRESS``'s
        own comment) -- direct user feedback that manually launching
        Vizard left it sitting on its own "Load Data Using One of the
        Following" screen, doing nothing, because nobody had typed the
        socket address in by hand. ``-directComm`` pre-fills that
        address and selects DirectComm/Live Display, but -- confirmed by
        a further direct user report -- does NOT click Vizard's own
        "Start Visualization" button; no documented command-line flag
        does that while keeping the visible live view (the fully
        headless ``-batchmode -noDisplay`` combination skips it, but
        also skips rendering anything at all, defeating the point of a
        LIVE VISUALIZATION). That one click is therefore still needed
        each time Vizard is (re)launched this way -- see
        ``self._vizard_live_stream_hint_shown`` for how that's
        communicated instead of silently left for the user to discover.

        A previously-tracked ``self._vizard_process`` (one THIS method
        itself launched earlier, in this same session -- see
        ``self._vizard_direct_comm_address``) is only trusted as-is if it
        already matches what's needed now: still running, and either no
        ``-directComm`` is needed this time, or it already has the one
        needed. A live-stream run needing one that the tracked instance
        doesn't have is a real, reachable case -- e.g. Vizard was
        launched earlier for a save-file run, or before Vizard
        Configuration was ever set to live-stream -- and trusting it
        anyway would reproduce the exact original bug, just one launch
        later. That mismatched instance is terminated and a fresh one
        relaunched with the correct flag instead. The reverse (a
        live-stream-ready instance already running, but a save-file/no
        -request launch is what's needed now) is left alone -- having
        ``-directComm`` active doesn't stop Vizard from also opening a
        save file, so there is nothing broken to fix there. An instance
        this session never itself launched (``self._vizard_process`` is
        still ``None`` -- started by the user outside SpaceMissionStudio, or
        in an earlier session) is left completely alone; a second,
        correctly-configured instance is launched alongside it instead,
        since there is no reliable way to ask an arbitrary already
        -running Vizard process "are you already connected".

        This method's own "reuse if already running and matching"
        behavior still applies when called directly from the "Launch
        Vizard" menu action -- but :meth:`on_run` (a live-stream run
        specifically) always terminates a self-launched
        ``self._vizard_process`` BEFORE calling this method, so that
        branch is effectively never reached from there: real user
        feedback was that reusing a running instance across separate runs
        left a live-streamed Vizard showing a mix of the previous run's
        and the current run's data, since a running Vizard Main Scene has
        no way to reset itself live (confirmed directly from Vizard's own
        Unity source, not merely suspected -- see ``on_run``'s own
        comment for specifics). Forcing a fresh relaunch there is the
        only way this app can guarantee a truly clean scene per run.

        Returns True once Vizard is confirmed running (already was, or
        was just started) by the end of this call, False if the user
        cancelled a browse prompt or launching genuinely failed (an
        error was already shown in that case) -- :meth:`on_run` uses
        this to decide whether it's safe to start a live-stream run at
        all.
        """
        direct_comm_address = (
            DEFAULT_LIVE_STREAM_ADDRESS
            if self._vizard_request is not None and self._vizard_request.live_stream
            else None
        )
        if self._vizard_process is not None and self._vizard_process.poll() is None:
            if not direct_comm_address or self._vizard_direct_comm_address == direct_comm_address:
                self.statusBar().showMessage("Vizard is already running.")
                return True
            self._terminate_vizard_process()

        executable = find_vizard_executable()
        if executable is None:
            executable = self._locate_vizard()
            if executable is None:
                return False
        try:
            self._vizard_process = launch_vizard(executable, direct_comm_address=direct_comm_address)
        except OSError as exc:
            report(self, f"Could not launch Vizard ({executable}): {exc}")
            return False
        self._vizard_direct_comm_address = direct_comm_address
        if direct_comm_address:
            self.statusBar().showMessage(
                f"Launched Vizard ({executable}) -- click \"Start Visualization\" in the Vizard window to connect."
            )
            if not self._vizard_live_stream_hint_shown:
                # Once per session, not once per launch/run -- see
                # self._vizard_live_stream_hint_shown's own comment. The
                # status bar message above (shown every time) is easy to
                # miss/get overwritten by the "Running..." message that
                # follows moments later when this was triggered from
                # on_run(): a longer toast the first time (U-39: no box for
                # information), and the full text in the Log.
                _logger.info("Vizard was launched with its socket address filled in (%s), but it still needs "
                             "\"Start Visualization\" clicked in its own window before the run can begin: Vizard "
                             "has no command-line option to skip that click while showing the live view.",
                             direct_comm_address)
                show_toast(self, "Vizard is open: click \"Start Visualization\" in its window to connect",
                           kind="info", duration_ms=10000)
                self._vizard_live_stream_hint_shown = True
        else:
            self.statusBar().showMessage(f"Launched Vizard ({executable}).")
        return True

    def _terminate_vizard_process(self) -> None:
        """Stops ``self._vizard_process`` (a mismatched instance
        :meth:`on_launch_vizard` is about to replace -- see its own
        docstring) and waits (bounded, so a Vizard that refuses to exit
        can't hang the GUI thread forever) for it to actually stop before
        returning, so the replacement instance doesn't briefly coexist
        with it. ``terminate()`` first (a clean exit, in case Vizard has
        anything to flush/save), ``kill()`` only if that doesn't work
        within the timeout.

        Waiting also frees the live-stream port. In Basilisk 2.12.0
        ``vizInterface`` connects out to Vizard, so the Vizard process
        started here is the one that listens on it (security analysis
        S-06; the "binds" wording in ``docs/source/Vizard/vizardAdvanced/
        vizardLiveComm.rst`` does not match the code). The tool itself
        opens no port.
        """
        self._vizard_process.terminate()
        try:
            self._vizard_process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self._vizard_process.kill()
            self._vizard_process.wait(timeout=5.0)
        self._vizard_process = None
        self._vizard_direct_comm_address = None

    def _confirm_script_blocks(self, blocks) -> bool:
        """Ask before running ``script_block`` code (SRS-S-03): it is
        unrestricted Python from the scenario file. Shows all of each
        block's code (a scrollable view), with its length and SHA-256;
        the default answer is No."""
        def entry(path, command) -> str:
            code = str(command.params.get("code", ""))
            digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
            return (f"{path}" + (f" ({command.label})" if command.label else "")
                    + f": {len(code)} characters, SHA-256 {digest}\n{code}")

        listing = "\n\n".join(entry(path, command) for path, command in blocks)
        box = QMessageBox(QMessageBox.Icon.Warning, "Run script blocks?",
                          f"This scenario has {len(blocks)} script block(s). They run as unrestricted Python, "
                          "with your user's access to files and the network. Run them only if you trust the "
                          "scenario and have read all of the code (Show Details).",
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        box.setDetailedText(listing)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    # The run modes (U-18): what the mode button and the Run tooltip say.
    _RUN_MODE_TEXT = {"single": ("Single run", "run the scenario once"),
                      "monte_carlo": ("Monte Carlo", "run the scenario's Monte Carlo batch"),
                      "sil": ("SIL", "run with a spacecraft's flight software in the loop")}

    @property
    def run_mode(self) -> str:
        """``"single"``, ``"monte_carlo"`` or ``"sil"``: what Run starts."""
        action = self.run_mode_group.checkedAction()
        return action.data() if action is not None else "single"

    def set_run_mode(self, mode: str) -> None:
        action = next(a for a in self.run_mode_group.actions() if a.data() == mode)
        action.setChecked(True)
        self._on_run_mode_changed(action)

    def _on_run_mode_changed(self, _action=None) -> None:
        label, doing = self._RUN_MODE_TEXT[self.run_mode]
        self.run_mode_button.setText(label)  # the top bar's: the button draws its own menu arrow
        if hasattr(self, "run_mode_control"):
            self.run_mode_control.set_mode(self.run_mode)
            self.run_page.show_mode(self.run_mode)
            self._refresh_run_page()
        self.commands.refresh_tooltip("run.run", tip=f"{doing}. Pick another mode beside it. The scenario must be "
                                                     "valid first: Problems says what to fix.")

    def _on_live_plot_toggled(self, checked: bool) -> None:
        self.live_plot_action.setText(f"Live plot: {'on' if checked else 'off'}")
        if hasattr(self, "commands"):
            self.commands.refresh_tooltip("run.live_plot")

    def on_run(self) -> None:
        """Run: start the selected mode (U-18)."""
        mode = self.run_mode
        if mode == "monte_carlo":
            self.on_run_monte_carlo()
        elif mode == "sil":
            self._run_sil_mode()
        else:
            self._launch_run()

    def _run_sil_mode(self) -> None:
        """Run in SIL mode: the spacecraft and the program chosen on Run > Run
        (M5b; they were asked for in two dialogs)."""
        try:
            self.scenario_editor.to_scenario()
        except ScenarioValidationError as exc:
            self._cannot_run(exc)
            return
        self.show_view(self.run_page)
        self._refresh_run_page()
        name, options = self.run_page.sil_choice()
        if name is None:
            if not self.run_page.sil_combo.count():
                self.show_view(self.flight_software_widget)  # it says why none can be exported
            show_toast(self, options, kind="error")
            return
        self.on_run_sil(name, options)

    def on_run_sil(self, spacecraft_name: str, options) -> None:
        """Run in SIL mode: the scenario with that spacecraft's flight
        software in the program ``options.binary`` (sil.runner); the user
        confirmed the program in SilRunDialog."""
        if self._run_worker is not None and self._run_worker.isRunning():
            self._report_run_problem("A run is in progress: wait for it to finish, or cancel it (Esc).",
                                     level=logging.INFO)
            return
        self.set_run_mode("sil")
        self._launch_run(sil=(spacecraft_name, options))

    def _launch_run(self, sil=None) -> None:
        try:
            scenario = self.scenario_editor.to_scenario()
        except ScenarioValidationError as exc:
            self._cannot_run(exc)
            return
        blocks = [] if sil is not None else script_blocks(scenario.mission_sequence)  # SIL leaves the sequence out
        if blocks and not self._confirm_script_blocks(blocks):
            return

        if self._vizard_request is not None and self._vizard_request.live_stream:
            # Real user feedback: "when running a new simulation after a
            # previous simulation finished, vizard should completely
            # refresh so it actually displays only stuff from the current
            # simulation, and not the previous one." Confirmed directly
            # from Vizard's own Unity source (0h3xn4/vizard,
            # MessageList.cs/ScenarioSceneManager.cs): a running Vizard
            # Main Scene has NO live "reset" capability -- its scene
            # objects are built exactly ONCE, from the very first message
            # ever received, and every later message (from ANY later run
            # that reconnects to the SAME process) just keeps appending to
            # the same ever-growing timeline. on_launch_vizard()'s own
            # "reuse an already-running, matching instance" behavior
            # (deliberate, see its own docstring -- avoids forcing a
            # needless extra "Start Visualization" click) is exactly what
            # was causing a new run to reuse that stale scene. A run this
            # session itself launched Vizard for is therefore always
            # terminated and relaunched fresh here -- an instance this
            # session never launched (started manually, or in an earlier
            # session) is left alone, same as on_launch_vizard()'s own
            # policy, since killing a process this app didn't start is
            # not this app's call to make.
            if self._vizard_process is not None and self._vizard_process.poll() is None:
                self._terminate_vizard_process()

            # Basilisk's InitializeSimulation() BLOCKS (inside native
            # C++, with no Python-level hook -- see RunWorker's own
            # module docstring on why there's no cancellation checkpoint
            # reachable here) waiting for Vizard to reply to an initial
            # handshake ping in live-stream mode -- direct user report:
            # a run appeared to hang at 0% forever, with Abort having no
            # effect, because Vizard was never actually connected.
            # on_launch_vizard() launches Vizard with -directComm when
            # needed (see its own docstring) so this handshake has
            # something to actually reply to; if it can't even do that
            # (Vizard not found/couldn't start), starting the run at all
            # would just reproduce the same hang, so it's refused here
            # instead, with a clear reason, rather than silently risking
            # it.
            if not self.on_launch_vizard():
                self._report_run_problem(
                    "Vizard is not connected: Vizard Configuration streams live, but Vizard could not be confirmed "
                    "running, and the run would wait for it with no way to cancel. Use Launch Vizard (or turn the "
                    "live stream off) first.")
                return

        # engine.mission_engine.MissionEngine (used when scenario.
        # mission_sequence is non-empty) has no run_live() equivalent --
        # see RunWorker.run()'s docstring -- so live plotting only applies
        # when there's no mission sequence to execute instead.
        live = self.live_plot_action.isChecked() and (sil is not None or not runs_sequence(scenario.mission_sequence))
        self._start_busy(f"Running {scenario.name}" + (f" with {sil[0]}'s flight software in the loop..."
                                                        if sil is not None else "..."), determinate=live)
        # Always clear the PREVIOUS run's results before this one starts --
        # not just when live (a real gap: a non-live run, or a scenario
        # with a mission_sequence, used to leave whatever the last run
        # produced on screen for the whole duration of this new run, which
        # looks exactly like this run already has results before it
        # actually does -- part of the "running another simulation seems
        # to break a lot of things" feedback).
        self._clear_run_views()
        if live:
            self.show_view(self.results_widget)
        # Reset once per run -- see _on_run_progress's own comment for why
        # this exists: suppresses a dialog-per-chunk storm if something
        # about THIS run's own data keeps failing on every single update.
        self._progress_error_shown = False
        # Captured now (not read back from self.scenario_editor later,
        # e.g. in _on_run_finished()): the editor isn't locked while a run
        # is in flight, so it could hold different, later edits by the
        # time this run actually finishes. This is the exact epoch that
        # exact ResultSet's time_s values are relative to -- and the exact
        # rf_link/ground_station/power config mission_dashboard_widget
        # needs to recompute a live link-budget breakdown.
        self._last_run_epoch_utc = scenario.epoch_utc
        self._last_run_scenario = scenario
        save_file = getattr(self._vizard_request, "save_file", None)
        self._last_run_vizard_file = str(vizard_playback_file(save_file)) if save_file else None
        self.results_widget.set_featured_series(featured_series(scenario))
        self.results_widget.set_layout_key(scenario.name)  # the plot grid is kept per scenario (U-24)
        _join_finished_worker(self._run_worker)
        extra = {"sil": sil} if sil is not None else {}  # a plain run builds its worker exactly as before
        vizard_request = self._vizard_request
        if vizard_request is not None and self._current_path is not None:
            # A 3D model's relative mesh paths are relative to the scenario file.
            vizard_request = dataclasses.replace(vizard_request, model_base_dir=str(self._current_path.parent))
        self._run_worker = RunWorker(scenario, vizard_request=vizard_request, live=live,
                                     allow_scripts=bool(blocks), **extra)
        self._last_run_sil = sil is not None
        _run_logger.info("Run %d started: %s (%s)", self.run_history.next_number, scenario.name,
                         "SIL" if sil is not None else "Single")
        if sil is not None:
            self.flight_software_widget.set_sil_running(sil[0])
            self._run_worker.sil_report.connect(self.flight_software_widget.show_sil_report)
        self._run_worker.progress.connect(self._on_run_progress)
        self._run_worker.phase.connect(self.run_progress.set_phase)
        self._run_worker.fraction.connect(self.run_progress.set_fraction)
        self._run_worker.finished_ok.connect(self._on_run_finished)
        self._run_worker.failed.connect(self._on_run_failed)
        self._run_worker.cancelled.connect(self._on_run_cancelled)
        self._run_worker.start()
        # Only RunWorker has a request_cancel() to call (see on_abort_run
        # and this action's own construction comment) -- enabled here,
        # right after start(), rather than lumped into _set_running(),
        # since on_run_monte_carlo()'s _start_busy() call must NOT enable
        # it.
        self.abort_action.setEnabled(True)

    def on_abort_run(self) -> None:
        if self._run_worker is not None and self._run_worker.isRunning():
            self._run_worker.request_cancel()
            # Cancellation is cooperative, not instant (see RunWorker's own
            # module docstring) -- disabled immediately so the user isn't
            # tempted to click it again while waiting for the next
            # checkpoint; _stop_busy() re-disables it anyway once the
            # worker actually reports back, but that can be a moment away.
            self.abort_action.setEnabled(False)
            self.run_progress.cancelling()
            self.statusBar().showMessage("Cancelling... the run stops at its next checkpoint.")

    def _on_run_progress(self, partial_result, fraction: float) -> None:
        # Real user feedback ("the app really should be robust and
        # resilient and not crash whenever something unusual happens"):
        # this slot runs on every single live-progress chunk, so if
        # anything it touches ever raised (e.g. a widget hitting an edge
        # case specific to this scenario's own series/spacecraft set), the
        # exception would propagate back through Qt's signal dispatch on
        # EVERY subsequent chunk too -- deterministically leaving the
        # Results tab stuck on its placeholder for the rest of the run
        # while the simulation itself (a separate thread, unaffected)
        # keeps going and completes normally, which looks exactly like
        # "the GUI broke" with no error ever shown. Caught here, logged
        # once with a full traceback, and surfaced ONCE per run (not a
        # dialog-per-chunk storm) via self._progress_error_shown -- the
        # run itself is never aborted by this, only this chunk's GUI
        # update is skipped.
        try:
            self.results_widget.set_live_result(partial_result, self._last_run_epoch_utc)
            self.mission_dashboard_widget.set_live_result(partial_result, self._last_run_scenario)
            self.run_progress.set_fraction(fraction)
        except Exception as exc:  # noqa: BLE001 -- see this method's own comment on why ANY failure is caught here
            _logger.exception("Failed to apply a live progress update")
            if not self._progress_error_shown:
                self._progress_error_shown = True
                self._report_run_problem(
                    _with_log_file_hint(
                        f"Updating the live display failed ({exc}): the run goes on, and the plots and dashboard "
                        "catch up when it ends. (Said once per run.)"),
                    level=logging.WARNING)

    def _on_run_finished(self, result, command_summary=None) -> None:
        number = self.run_history.next_number
        self._stop_busy(f"Run {number} complete: {len(result.series)} result series.", "done", "Done",
                        run_name=f"Run {number}")
        took = f" in {_duration_text(self.last_run_seconds)}" if self.last_run_seconds is not None else ""
        summary = events_summary(result)
        show_toast(self, f"Run {number} complete{took}" + (f": {summary}" if summary else ""))

        def failed(exc) -> None:  # the run itself DID succeed; never hide that behind a GUI bug
            _logger.exception("Run completed, but displaying its results failed")
            self._report_run_problem(
                _with_log_file_hint(
                    f"The run finished with {len(result.series)} result series, but showing them failed ({exc}). "
                    "The run itself is not affected: run again to show its results."),
                view=self.log_widget)

        def views() -> None:
            self.mission_dashboard_widget.set_live_result(result, self._last_run_scenario)
            self.event_timeline_widget.set_result(result, self._last_run_epoch_utc)
            self._set_shown_run()
            self._offer_vizard_playback()
            self._keep_run(result, cancelled=False)
            self.lifetime_widget.set_last_run(self._last_run_scenario, result)
            self.budget_widget.set_last_run(self._last_run_scenario, result)

        def shown() -> None:
            if command_summary is not None:
                self.show_view(self.mission_output_widget)
            elif getattr(self, "_last_run_sil", False):
                self.show_view(self.flight_software_widget)
            else:
                self.show_view(self.results_widget)

        # set_live_result(), not set_result(): a live run's final chunk
        # and its "finished" result always share the same series names,
        # so using set_result() here would rebuild series_combo and
        # silently snap the user's current selection back to the first
        # series the instant the run they were watching actually
        # completes -- see ResultsWidget.set_live_result()'s docstring
        # for why that rebuild is skipped when the series set hasn't
        # changed. Also correct for a non-live run: set_live_result()
        # still rebuilds normally whenever the series set differs from
        # whatever was shown before.
        self._show_run_end([lambda: self.results_widget.set_live_result(result, self._last_run_epoch_utc), views,
                            lambda: (command_summary is not None
                                     and self.mission_output_widget.set_command_summary(command_summary, result)),
                            shown], failed)

    def _on_run_failed(self, message: str) -> None:
        """A failed run: the Log opens at its error (SIL: the Flight Software
        page, with its report), and a toast says what failed (U-23)."""
        self._stop_busy("Run failed.", "failed", "Failed")
        self._report_run_problem(_with_log_file_hint(f"Run failed: {message}"))
        self._add_history_extra("failed", "SIL" if getattr(self, "_last_run_sil", False) else "Single", message)
        if getattr(self, "_last_run_sil", False):
            self.flight_software_widget.set_sil_running(None)
            self.show_view(self.flight_software_widget)
        else:
            self._show_log_errors()

    def _show_log_errors(self) -> None:
        """A failure opens the Log (the Run area) at its warnings and errors (U-23)."""
        self.log_widget.show_errors()
        self.show_view(self.log_widget)

    def _on_run_cancelled(self, partial_result, command_summary=None) -> None:
        """Handles RunWorker.cancelled -- a user-requested abort (see
        on_abort_run()), not a failure: whatever was already simulated
        before the cancellation took effect is shown exactly like a
        normal finish would show it, just with "cancelled" messaging
        instead of "complete".
        """
        number = self.run_history.next_number
        self._stop_busy(f"Run {number} cancelled.", "cancelled", "Cancelled", run_name=f"Run {number}")
        show_toast(self, f"Run {number} cancelled: what was computed is shown", kind="info")

        def failed(_exc) -> None:  # same reasoning as _on_run_finished's
            _logger.exception("Run was cancelled, but displaying its partial results failed")
            self._report_run_problem(
                _with_log_file_hint("The run was cancelled, but showing what it computed failed."),
                view=self.log_widget)

        def views() -> None:
            self.mission_dashboard_widget.set_live_result(partial_result, self._last_run_scenario)
            self.event_timeline_widget.set_result(partial_result, self._last_run_epoch_utc)
            self._set_shown_run()
            self._offer_vizard_playback()
            self._keep_run(partial_result, cancelled=True)

        self._show_run_end([
            lambda: self.results_widget.set_live_result(partial_result, self._last_run_epoch_utc), views,
            lambda: (command_summary is not None
                     and self.mission_output_widget.set_command_summary(command_summary, partial_result)),
            lambda: self.show_view(self.mission_output_widget if command_summary is not None
                                   else self.results_widget)], failed)

    # -- the end of a run, in steps (M6b) ------------------------------------------------------
    def _show_run_end(self, steps: list, failed) -> None:
        """Show a run's end in ``steps``, one an event-loop turn (each held
        the window 20-40 ms; all at once, 120 ms). ``failed(exc)`` says so
        when one raises; the rest are dropped."""
        self.finish_run_end()  # an earlier run's, first
        self._run_end_steps, self._run_end_failed = list(steps), failed
        self._next_run_end_step()

    @property
    def run_end_pending(self) -> bool:
        """A run's end is still being shown (its views filled in steps)."""
        return bool(getattr(self, "_run_end_steps", None))

    def _next_run_end_step(self) -> None:
        if not self.run_end_pending:
            return
        step = self._run_end_steps.pop(0)
        try:
            step()
        except Exception as exc:  # noqa: BLE001 -- the run's own result stands; say what could not be shown
            self._run_end_steps = []
            self._run_end_failed(exc)
            return
        if self._run_end_steps:
            # A few ms apart: with 0 two steps could run in one pass of the event loop
            QTimer.singleShot(_RUN_END_STEP_MS, self, self._next_run_end_step)

    def finish_run_end(self) -> None:
        """Take the steps of a run's end still waiting now (a new run,
        cleared views, closing)."""
        while self.run_end_pending:
            self._next_run_end_step()

    def on_run_monte_carlo(self) -> None:
        try:
            scenario = self.scenario_editor.to_scenario()
        except ScenarioValidationError as exc:
            self._cannot_run(exc)
            return
        if not scenario.monte_carlo.enabled:
            self._report_run_problem("Monte Carlo is off for this scenario: enable Monte Carlo and add at least one "
                                     "dispersion on the Monte Carlo page, then Run.", level=logging.WARNING)
            self.show_view(self.scenario_editor.monte_carlo_page)
            return

        # Every run flies the Mission Sequence (as Run Simulation does), so
        # its script blocks need the same consent.
        blocks = script_blocks(scenario.mission_sequence)
        if blocks and not self._confirm_script_blocks(blocks):
            return
        # The folder on Run > Run (M5b), remembered for the scenario; asked for when it is empty.
        archive_dir_str = self.run_page.archive_dir() or QFileDialog.getExistingDirectory(
            self, "Monte Carlo archive directory")
        if not archive_dir_str:
            return
        if archive_dir_str != self.run_page.archive_dir():
            self.run_page.set_archive_dir(archive_dir_str)
            self._remember_archive_dir(archive_dir_str)
        archive_dir = Path(archive_dir_str)
        state = monte_carlo_results.folder_state(archive_dir)
        if state == "other":
            self._report_run_problem(f"{archive_dir} holds other files: choose an empty folder for the Monte Carlo "
                                     "batch.", level=logging.WARNING)
            return
        overwrite = state == "batch"
        if overwrite and QMessageBox.question(
                self, "Replace the earlier batch?",
                f"Replace the earlier Monte Carlo batch in {archive_dir}? Its run files are deleted.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return

        self._start_busy(f"Monte Carlo: 0 of {scenario.monte_carlo.num_runs} cases done", cancellable=False,
                         cancel_note="A Monte Carlo batch runs to the end: Basilisk's Controller has no way to stop "
                                     "it part way.")
        _join_finished_worker(self._mc_worker)
        self._mc_archive_dir = archive_dir
        self._mc_total = scenario.monte_carlo.num_runs
        _run_logger.info("Monte Carlo batch started: %s, %d runs, saved in %s", scenario.name,
                         scenario.monte_carlo.num_runs, archive_dir)
        self._mc_poll.start()
        self._mc_worker = MonteCarloWorker(scenario, scenario.monte_carlo, archive_dir,
                                           allow_scripts=bool(blocks), overwrite=overwrite)
        self._mc_worker.finished_ok.connect(self._on_monte_carlo_finished)
        self._mc_worker.failed.connect(self._on_monte_carlo_failed)
        self._mc_worker.start()

    def _poll_monte_carlo(self) -> None:
        """Count the batch's finished cases (Basilisk's Controller has no
        progress hook; it writes a file per case)."""
        total = getattr(self, "_mc_total", 0)
        if not total or getattr(self, "_mc_archive_dir", None) is None:
            return
        done = min(monte_carlo_results.finished_cases(self._mc_archive_dir), total)
        self.run_progress.set_phase(f"Monte Carlo: {done} of {total} cases done")
        self.run_progress.set_fraction(done / total)

    def _on_monte_carlo_finished(self, failures: list) -> None:
        total = getattr(self, "_mc_total", 0)
        self._stop_busy(
            f"Monte Carlo complete with {len(failures)} failed run(s)." if failures
            else "Monte Carlo complete -- all runs succeeded.",
            "failed" if failures else "done", f"{len(failures)} runs failed" if failures else "Done",
        )
        took = f" in {_duration_text(self.last_run_seconds)}" if self.last_run_seconds is not None else ""
        try:
            if failures:
                # In the Log, where the failed runs' own errors are (U-23).
                self._report_run_problem(
                    f"Monte Carlo finished{took}: {len(failures)} of {total or '?'} runs failed "
                    f"(runs {', '.join(str(f) for f in failures)}). The Log has their errors.",
                    level=logging.WARNING)
            else:
                show_toast(self, f"Monte Carlo complete{took}: all {total} runs succeeded" if total
                           else f"Monte Carlo complete{took}: all runs succeeded")
            _run_logger.info("Monte Carlo batch done%s: %d of %s runs failed; saved in %s", took, len(failures),
                             total or "?", self._mc_archive_dir)
            self._add_history_extra("partial" if failures else "done", "Monte Carlo",
                                    f"{total or '?'} runs, {len(failures)} failed; saved in {self._mc_archive_dir}")
            if self.monte_carlo_results_widget.load_folder(self._mc_archive_dir):
                self._show_monte_carlo_tab()
        except Exception:  # noqa: BLE001 -- the batch itself DID finish; never hide that behind a GUI bug
            _logger.exception("Monte Carlo batch finished, but reporting its outcome failed")

    def _on_monte_carlo_failed(self, message: str) -> None:
        self._stop_busy("Monte Carlo run failed.", "failed", "Failed")
        self._report_run_problem(_with_log_file_hint(f"Monte Carlo failed: {message}"))
        self._add_history_extra("failed", "Monte Carlo", message)
        self._show_log_errors()

    # -- window lifecycle ---------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        # Refuse to close while a background run/Monte Carlo QThread is
        # still alive -- starting a run doesn't mark the scenario dirty, so
        # _confirm_discard_unsaved() alone would let the window (and, with
        # it, the whole process, since Qt tears down QApplication.exec()
        # once the last window closes) close right out from under a still
        # -running worker. Neither worker is parented. RunWorker DOES now
        # have a cooperative-cancellation hook (request_cancel(), see its
        # own module docstring / on_abort_run() above), but it only takes
        # effect at the next chunk/command checkpoint, not instantly, and
        # MonteCarloWorker/run_monte_carlo() still has no such hook at
        # all -- so closing must simply wait either way, same as it would
        # for any other in-progress, no-undo operation, rather than firing
        # an implicit abort the user never asked for.
        for worker, label in ((self._run_worker, "A simulation"), (self._mc_worker, "A Monte Carlo run")):
            if worker is not None and worker.isRunning():
                self._report_run_problem(f"{label} is still running: wait for it to finish, or cancel it (Esc), "
                                         "before closing SpaceMissionStudio.", level=logging.INFO)
                event.ignore()
                return
        if self._confirm_discard_unsaved():
            # Closed: nothing more to autosave (the scenario was saved or
            # discarded), and no explanation is started for a window going away.
            self._autosave_timer.stop()
            self.scenario_explainer_widget.shut_down()
            self.finish_run_end()  # a run that just ended is kept (and saved, below)
            self.run_history.wait_loaded()
            self.run_history.wait_for_saves()  # a run ended just before must be on disk
            self.results_overview.wait_for_worker()
            self.lifetime_widget.wait_for_worker()  # a few seconds at most; its thread must not be destroyed mid-run
            self.budget_widget.wait_for_worker()
            self.flight_software_widget.wait_for_worker()
            self.data_panel_widget.wait_for_reader()  # the start-up read of the reference data files
            self.load_scenario_widget.reference_card.wait()  # a download must not be cut off mid-file
            self._save_layout()
            event.accept()
        else:
            event.ignore()
