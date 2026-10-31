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

"""ResultsWidget: plots a :class:`engine.results.ResultSet` with Plotly,
embedded in a ``QWebEngineView`` -- replaces an earlier matplotlib
version, per explicit user request ("please rather use plotly, and not
matplotlib... make the plots visually more clear, professional and
appealing and informative") plus a real, separate complaint (matplotlib's
default axis formatting fell back to scientific/offset notation on
several series -- Plotly is configured below to never do that, on every
axis, regardless of data range). Takes a plain ``ResultSet`` -- no
Basilisk import in this module, so it's testable here with synthetic
data exactly like ``engine/results.py`` itself is.

``QWebEngineView``, not a static image: an embedded Plotly chart is a
real, interactive HTML/JS page (pan/zoom/box-select, a unified hover
tooltip showing every series' value at the cursor's x-position, a
built-in PNG-export button) -- a screenshot-style static render would
throw away exactly the interactivity that makes Plotly worth using over
matplotlib in the first place. ``plotly.js`` itself (~4.7 MB) is
referenced via a local ``file://`` src pointing directly at the copy
already installed as part of the ``plotly`` PyPI package's own
``package_data`` (:func:`_plotlyjs_path`) -- never a CDN reference (this
project avoids unnecessary network dependencies throughout, and a
SpaceMissionStudio desktop install has no reason to need one just to redraw a
plot), and never a second bundled copy of a multi-megabyte file this
project doesn't need to ship or keep in sync itself.

Running as root (this project's own CI/dev sandbox is; most real desktop
installs are not): Chromium refuses to start its renderer process as
root unless ``--no-sandbox`` is passed (a Chromium policy, not a Qt one
-- process sandboxing normally works by dropping privileges via setuid,
which is meaningless starting from an already-root process) -- confirmed
directly against a real ``QWebEngineView`` in this development sandbox,
which failed exactly that way without it. Handled below by setting
``QTWEBENGINE_CHROMIUM_FLAGS`` BEFORE ``PySide6.QtWebEngineWidgets`` is
imported (the only point at which QtWebEngine reads it) -- and ONLY when
actually running as root (``os.geteuid() == 0``), left off for a normal
non-root install, where Chromium's own process sandbox is real
defense-in-depth worth keeping even though this widget only ever loads
its own locally-generated HTML/JS, never remote or otherwise untrusted
content.

Verification status: the full local-``plotly.min.js``-via-``file://``
plus ``QWebEngineView.setHtml()`` pipeline was confirmed end-to-end in
this development sandbox (``QT_QPA_PLATFORM=offscreen`` -- no real
display here either) -- ``loadFinished`` fires ``True`` and a real
in-page JS check (``document.getElementsByClassName("plotly").length``)
confirms the chart div actually renders, not just that ``setHtml()``
didn't raise. The chosen design (re-send the FULL html, plotly.js
``<script src>`` reference included, on every redraw, rather than
loading the page shell once and pushing incremental updates via
``Plotly.react()`` through ``page().runJavaScript()``) was picked for
simplicity and testability (the built ``go.Figure`` object is directly
inspectable in a test, same role matplotlib's ``Axes`` used to play) --
NOT benchmarked against the incremental-update alternative for redraw
latency during a live (``set_live_result``) run; if that turns out to
feel sluggish on a real machine for a long/fast-updating run, the
incremental-update approach is the documented next step, not something
ruled out here.

Display choices below are all PLOT-only (``export_csv()``/``_on_export()``
keep writing exactly what ``TimeSeries`` holds -- raw SI units, elapsed
seconds -- since a CSV a user hands to another tool should stay
unambiguous, not follow a plot-only display preference):

* Per-category unit display (``_categorize()``, replacing an earlier
  blanket "every m/m-s series -> km/km-s" rule this project's own
  earlier version used): real user feedback was that the blanket rule
  went too far -- it converted the state vector (position/velocity) AND
  delta-V to km/km-s along with genuinely orbit-scale quantities like
  altitude and semi-major axis, but the explicit ask was the opposite
  for the first two ("delta-V shall always be displayed in m/s",
  "state vector elements shall be displayed in meters for position and
  m/s for velocity") while keeping it for the second two ("altitudes,
  semi-major axes shall be displayed in km"). Both can't be satisfied by
  one rule keyed on the literal unit string alone (position and
  semi-major axis are both recorded in plain "m"; velocity and delta-V
  are both plain "m/s") -- ``_categorize()`` keys off what each named
  series actually *is* instead (see its own docstring), with each
  category's own explicit unit choice, and only an uncategorized/future
  series (``_legacy_display()``) falls back to the old blanket rule.
  Orbital angle elements (inclination/RAAN/argument of periapsis/true
  anomaly, osculating and mean alike) additionally display in degrees,
  not Basilisk's native radians -- matching every angle INPUT field this
  app's own Scenario Editor already uses (e.g. ``inclination_deg``), and
  part of the same "convey more information" feedback that asked for
  titles/axis names/legends on every plot (see ``_categorize()``).
* The x-axis defaults to elapsed time (hours since the scenario epoch,
  as before) but can be switched to absolute epoch (UTC datetimes,
  ``series.time_s`` added to the epoch :meth:`set_result`/
  :meth:`set_live_result` were given) via ``x_axis_combo``. ``epoch_utc``
  is optional and defaults to ``None`` (falls back to elapsed time even
  if "Epoch (UTC)" is selected) so every existing caller/test that only
  ever passed a bare ``ResultSet`` keeps working unchanged. A third
  choice, "Orbit number" (``engine.orbit_number``), counts revolutions of
  one spacecraft from the ascending node (docs/ux-audit.md U-26).

The plot workspace (UX iteration 5a, docs/ux-audit.md U-24 to U-30):

* A plot **catalog** (``gui.plot_catalog``) on the left lists every plot
  of the run by group, with a search box; a tick shows a plot in the
  grid, a click on its name shows it in the selected cell.
* A **grid** of up to six plots (1 x 1 to 2 x 3), drawn as several
  Plotly figures in one web page (``gui.plot_page``; decision 4): linked
  x axes, the shared time cursor on every plot, a click selects a plot
  (Save PNG/SVG act on the selected one). The layout and the plots shown
  are kept per scenario (``set_layout_key``) in
  ``~/.spacemissionstudio/layout.ini``.
* A **readout** (``gui.readout_panel``) on the right: every shown
  series' value at the time under the pointer, or at the cursor.
* **Event bands**: eclipses, passes, burns, thruster firings, mode
  changes and downlinks from ``engine.events``, drawn behind the lines in
  the Events tab's colours, each kind switched on and off above the grid.
* The epoch under the title ("t0 = 2030-01-01 08:30:00 UTC") when the
  axis is elapsed time or orbit number, and **Export all** (every shown
  plot as PNG or SVG, with its data as CSV and the run's provenance).
"""

from __future__ import annotations

import base64
import urllib.parse

# See module docstring's "Running as root" section, and gui.webengine_setup
# (which now sets the flags for every web view) -- MUST happen before
# PySide6.QtWebEngineWidgets is imported below (env var read at that
# module's own native init time; setting it any later has no effect).
from . import export_log
from . import webengine_setup  # noqa: F401 -- importing it sets the flags

import json
import time
import weakref
from datetime import datetime, UTC
from pathlib import Path

import numpy as np

import plotly.graph_objects as go
import shiboken6
from PySide6.QtCore import QElapsedTimer, QSettings, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import output_provenance, temp_folders
from ..engine import events as event_model
from ..engine import orbit_number, time_system
from ..engine.findings import explanation_lines
from ..engine.results import ResultSet, TimeSeries, output_path
from ..plot_categories import categorize as _categorize
from ..plot_categories import legacy_display as _legacy_display
from ..plot_categories import parse_access_pair as _parse_access_pair
from ..plot_categories import plot_group
from . import plot_page
from .flow_layout import FlowLayout
from .plot_catalog import ACCESS_TIMELINE, PlotCatalog
from .readout_panel import ReadoutPanel, value_at
from .feedback import report
from .theme import SERIES_COLORS, SIZE, TOKENS, WEB_FONT_STACK, on_change, set_role
from .theme import plotly_template as pt
from .widgets import ComboBox

# Categorical series colours: the theme's categorical palette (theme/
# palettes.py has its validation), the same list object, so a figure built
# after a theme change takes the new theme's steps. The first three are the
# common case: every (x, y, z) series. A legend is shown for more than one
# line, so colour is never the only way to tell lines apart.
_SERIES_COLORS = SERIES_COLORS

# Chart chrome from the theme's Plotly template (theme/plotly_template.py),
# read where a figure is built, so a chart takes the theme in use. The
# bundled Inter is loaded into the chart page as an @font-face (the page
# cannot see fonts loaded into Qt).
_NOTE_MIN_WIDTH_PX = 360  # [px] the narrowest the wrapped notes under the toolbar get
_CATALOG_WIDTH_PX = (250, 400)  # [px] the plot list's narrowest and widest width before a drag
_CATALOG_WIDTH_SHARE = 0.16  # [-] its share of the pane until the user drags it (~350 px at 2560 px)
_FONT_FAMILY = WEB_FONT_STACK

# Fixed ids (rather than Plotly's own randomly-generated default) so
# _on_save_plot_png's injected JS can reliably find the chart div to
# rasterize -- see that method's own docstring for why a client-side
# Plotly.toImage() call is used instead of a server-side renderer
# (kaleido) this project doesn't otherwise depend on. The first plot of
# the grid has this id, the others plot_page.div_id(i).
_PLOT_DIV_ID = plot_page.PLOT_DIV_ID

# _on_save_plot_png/_poll_plot_png's poll-for-an-async-JS-result protocol
# -- see _on_save_plot_png's own docstring for why polling a page-global
# variable is used instead of relying on QWebEnginePage.runJavaScript()
# awaiting a top-level Promise itself (confirmed directly: it doesn't, on
# this PySide6 version). The sentinel distinguishes "still rendering"
# from a real result because a bare JS null/undefined also bridges back
# as an empty string here, not None.
_PNG_RESULT_JS_VAR = "__spacemissionstudioPngResult"
_SAVE_PNG_PENDING_SENTINEL = "__spacemissionstudio_png_pending__"
_SAVE_PNG_ERROR_PREFIX = "__spacemissionstudio_png_error__:"
_SAVE_PNG_POLL_INTERVAL_MS = 100
_SAVE_PNG_MAX_POLL_ATTEMPTS = 100  # 100 * 100ms = 10s -- Plotly.toImage took ~200ms in practice
_SAVE_PNG_MAX_WAIT_TICKS = 10  # poll ticks without an answer before asking again (1 s at 100 ms)

# [ms] Real user report: during a live-updating run, clicking the Series
# dropdown to switch plots appeared to do nothing. Root cause:
# set_live_result() used to call _redraw() -- a FULL QWebEngineView.setHtml()
# page reload (re-parsing the whole HTML document, reloading plotly.js,
# re-running Plotly.newPlot()) -- on every single progress chunk, with no
# throttling. A scenario that simulates faster than it can be watched (the
# common case for anything but a very long run) fires chunks faster than a
# full page reload can settle, so each setHtml() call interrupts the
# previous one's still-in-flight page load before it ever finishes
# rendering -- the view never visibly updates to anything, including a
# series the user just picked, because no reload during the storm ever
# completes. Throttling live redraws to this interval guarantees the
# QWebEngineView gets a real chance to finish each page load it starts.
# 300ms still reads as "live" to someone watching a plot update, while
# being generous enough for a full page reload to settle on a typical
# machine -- not tuned to any specific scenario.
_LIVE_REDRAW_MIN_INTERVAL_MS = 300


# Real user report: during a long run, switching to chief-1.position_N or
# .velocity_N "just doesn't change" -- the plot stayed on the previous
# series. Each was a 5.8 MB page (86,400 samples x 3 lines) and
# QWebEngineView.setHtml() silently shows nothing above 2 MB. Pages are
# now loaded from a file (no size limit), and each line is thinned to at
# most this many points for display (min and max of every stretch kept, so
# burns and peaks still show). Exports keep every sample.
_MAX_PLOT_POINTS_PER_LINE = 10000


# The shared time cursor (gui.time_cursor) on a plot: a click puts this
# prefix, the plot's index, the clicked x value and a counter in the page
# title, which the view reports through titleChanged (there is no
# QWebChannel in this app). See gui.plot_page for the page script. The
# cursor is drawn as a layout shape of this name, with Plotly.relayout
# (no reload).
_CURSOR_MESSAGE = plot_page.CLICK_MESSAGE
_CURSOR_SHAPE = plot_page.CURSOR_SHAPE


def _clicked_x(title: str) -> str | None:
    """The x value a plot click put in the page title, or None."""
    message = plot_page.parse_message(title)
    return message[2] if message is not None and message[0] == "click" else None


def _display_indices(values: np.ndarray, max_points: int = _MAX_PLOT_POINTS_PER_LINE) -> np.ndarray:
    """Indices of ``values`` to draw: all of them when there are few
    enough, otherwise the first, last, and the minimum and maximum of each
    of ``max_points // 2`` equal stretches (min-max decimation)."""
    n = len(values)
    if n <= max_points:
        return np.arange(n)
    buckets = max(1, (max_points - 2) // 2)
    edges = np.linspace(0, n, buckets + 1).astype(int)
    keep = [0, n - 1]
    finite = np.where(np.isfinite(values), values, np.nan)
    for start, end in zip(edges[:-1], edges[1:]):
        if end <= start:
            continue
        chunk = finite[start:end]
        if np.all(np.isnan(chunk)):
            keep.append(start)
            continue
        keep.append(start + int(np.nanargmin(chunk)))
        keep.append(start + int(np.nanargmax(chunk)))
    return np.unique(np.asarray(keep))


def _wrapping_display_indices(n: int, max_points: int = _MAX_PLOT_POINTS_PER_LINE) -> np.ndarray:
    """Evenly spaced indices for a wrapping angle: min-max decimation would
    pair ~0 and ~360 deg in every stretch and draw a solid band."""
    if n <= max_points:
        return np.arange(n)
    return np.unique(np.linspace(0, n - 1, max_points).astype(int))


def _break_at_wraps(x: np.ndarray, y: np.ndarray, period: float):
    """Inserts a gap wherever ``y`` wraps (jumps by more than half a
    ``period``), so 359 -> 1 deg isn't drawn as a vertical line."""
    jumps = np.flatnonzero(np.abs(np.diff(y)) > period / 2.0) + 1
    if not len(jumps):
        return x, y
    return np.insert(x, jumps, x[jumps - 1]), np.insert(y.astype(float), jumps, np.nan)


def _series_label(name: str, series: TimeSeries) -> str:
    """The name shown for a series in the Series list -- the same title
    its plot gets (e.g. "chief-1: Mean Semi-Major Axis"), not the dotted
    code name. Uncategorized series keep their code name."""
    display = _categorize(name, series) or _legacy_display(name, series)
    subject = name.split(".", 1)[0]
    return display.title if display.standalone_title else f"{subject}: {display.title}"


def _has_access_series(result: ResultSet | None) -> bool:
    return result is not None and any(
        (parsed := _parse_access_pair(name)) is not None and parsed[2] == "has_access" for name in result.series
    )


_DRIFT_WARNING_TOOLTIP = (
    "These spacecraft use two-body gravity only, so orbital energy and angular momentum should stay "
    "constant. A drift this large usually means a numerical-integration problem, not real physics: try a "
    "smaller dynamics step (Propagation Setup) or a higher-order integrator."
)
# The words engine.results.conservation_drift_warnings puts in a drift warning.
_DRIFT_WARNING_MARKERS = ("orbital energy drifted", "angular momentum drifted")


def warnings_tooltip(warnings: list[str]) -> str:
    """The run warnings' tooltip: each warning's rule (engine.findings: what
    it is, what it found against its limit, why, the fix), one paragraph
    each. A warning without one (a run saved before rules) gets none, but a
    conservation drift warning still gets the drift explanation.
    Transparency audit 3.12: the drift explanation was shown for every
    warning, a space-weather or re-entry one too."""
    rules = ["\n".join(lines) for lines in map(explanation_lines, warnings) if lines]
    if any(marker in warning for warning in warnings for marker in _DRIFT_WARNING_MARKERS
           if not explanation_lines(warning)):
        rules.insert(0, "About the drift warnings: " + _DRIFT_WARNING_TOOLTIP)
    return "\n\n".join(rules)


def _short_utc(timestamp: str) -> str:
    """"2026-10-07T14:33:38.434854+00:00" -> "2026-10-07 14:33 UTC" (the
    text unchanged if it doesn't parse)."""
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return timestamp
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


# Plotly's full page keeps the browser's default 8 px body margin under a
# 100%-height plot, which put a scroll bar beside every plot.
def _page_style() -> str:
    """The chart page's style: no margin, the theme's surface behind the
    figure, and the bundled fonts."""
    return f"<style>{pt.page_css(TOKENS)} html, body {{ overflow: hidden; }}</style>"


def _template_layout() -> dict:
    """The theme's Plotly template: fonts, transparent backgrounds over the
    page's surface, hover labels and the colourway (no axes: each figure
    sets its own)."""
    layout = pt.layout(TOKENS, SERIES_COLORS)
    layout.pop("xaxis")
    layout.pop("yaxis")
    layout.pop("legend")
    return layout


def warm_up_figures() -> None:
    """Load what a session's first plot needs: plotly builds its figure
    classes and their validators on first use, and the first run's end
    paid 0.35 s for it on the GUI thread. A small figure laid out as
    :meth:`ResultsWidget._build_figure` lays one out, built and
    serialised. Plain Python, nothing of Qt: the start-up warm-ups run it
    in a worker (``data_panel_widget``)."""
    axis = pt.axis(TOKENS)
    values = np.array([0.0, 1.0])  # arrays, as a run's series: plotly hands them to narwhals, which loads its plugins
    go.Figure(data=[go.Scatter(x=values, y=values, mode="lines", name="x", line=dict(width=2),
                               hovertemplate="%{y:.4g}<extra></extra>")],
              layout=dict(title=pt.title(TOKENS, "x", "y"), xaxis=dict(axis, title_text="t [s]", exponentformat="none"),
                          yaxis=dict(axis, title_text="[m]", separatethousands=True), **_template_layout(),
                          hovermode="x unified", showlegend=True,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                                      font=dict(color=TOKENS["text.secondary"])),
                          margin=dict(l=70, r=30, t=60, b=50),
                          shapes=[dict(type="rect", xref="x", yref="paper", x0=0.0, x1=1.0, y0=0, y1=1, line_width=0,
                                       layer="below", opacity=0.2),
                                  dict(type="line", xref="x", yref="paper", x0=0.5, x1=0.5, y0=0, y1=1,
                                       line=dict(dash="dash", width=1))])).to_json()


def _plotlyjs_path() -> Path:
    """Absolute filesystem path to the ``plotly.min.js`` bundle already
    installed as part of the ``plotly`` PyPI package -- see module
    docstring's "QWebEngineView, not a static image" section for why
    this is referenced directly rather than re-bundled or CDN-loaded.
    """
    import plotly

    return Path(plotly.__file__).parent / "package_data" / "plotly.min.js"


def _empty_state_html() -> str:
    """Shown before any run has produced a result -- previously a blank
    white canvas with no explanation (part of the "looks unfinished"
    feedback the matplotlib version's own docstring already addressed);
    kept as plain HTML/CSS here, no Plotly involved, so it costs nothing
    to render.
    """
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{pt.page_css(TOKENS)}</style></head>
<body><div class="empty">Run a simulation to see results here</div></body></html>"""


_X_AXES = (("elapsed", "Elapsed time"), ("epoch", "Epoch (UTC)"), ("orbit", "Orbit number"))
_EVENT_LABELS = {event_model.ECLIPSE: "Eclipses", event_model.ACCESS: "Passes", event_model.BURN: "Burns",
                 event_model.THRUSTER: "Thruster firings", event_model.MODE: "Modes",
                 event_model.DOWNLINK: "Downlinks"}
# [-] band opacity behind the lines: light enough that every line stays readable
_BAND_OPACITY = 0.16
# Bands of one kind drawn on one plot at most: Plotly redraws every shape on
# each zoom, and a year of LEO eclipses (~5,500) made zooming crawl.
_MAX_BANDS_PER_KIND = 400
_LAYOUT_SETTINGS_PREFIX = "results_layout"
_LAYOUT_SAVE_DELAY_MS = 500  # [ms] after the last change to the layout or plots
_EVENTS_REFRESH_S = 2.0  # [s] a live run's events are read again at most this often


# Views with a layout save pending (M6a: saved after the click): every
# read of a saved layout, and the application's quit, writes them first.
_PENDING_SAVES: weakref.WeakSet = weakref.WeakSet()
_SAVES_ON_QUIT = None  # the application whose quit writes them


def _write_pending_saves() -> None:
    for view in list(_PENDING_SAVES):
        if shiboken6.isValid(view):
            view._save_layout_now()
        else:  # Qt deleted the view: it has nothing left to save
            _PENDING_SAVES.discard(view)


def _settings() -> QSettings:
    return QSettings(str(Path.home() / ".spacemissionstudio" / "layout.ini"), QSettings.Format.IniFormat)


def _utc_text(epoch_utc: str) -> str:
    """ "2030-01-01T08:30:00" -> "2030-01-01 08:30:00 UTC" (unchanged if it doesn't parse)."""
    try:
        parsed = datetime.fromisoformat(epoch_utc.replace("Z", ""))
    except (ValueError, AttributeError):
        return epoch_utc
    return parsed.strftime("%Y-%m-%d %H:%M:%S UTC")


class _ExportCancelled(Exception):
    """Cancel pressed: the export stops before its next file."""


_exports: set = set()  # the export threads running, kept until each ends (not a widget's child)


class _ExportWorker(QThread):
    """Writes an export's files off the GUI thread (audit G2: about 1 s per
    long series, with no progress or cancel). ``job(step)`` writes them,
    calling ``step(written, total)`` before each file; Cancel stops it
    before the next one."""

    progress = Signal(int, int)  # files written, files in all
    finished_ok = Signal(object)  # what ``job`` returned
    failed = Signal(str)
    cancelled = Signal(int)  # files written before it stopped

    def __init__(self, job) -> None:
        super().__init__()
        self._job = job
        self._cancel = False
        self._written = 0

    def request_cancel(self) -> None:
        self._cancel = True

    def _step(self, written: int, total: int) -> None:
        self._written = written
        if self._cancel and written < total:
            raise _ExportCancelled
        self.progress.emit(written, total)

    def run(self) -> None:
        try:
            outcome = self._job(self._step)
        except _ExportCancelled:
            self.cancelled.emit(self._written)
        except (OSError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(outcome)


class ResultsWidget(QWidget):
    open_in_vizard = Signal(str)  # the last run's playback file
    plot_drawn = Signal(bool)  # the page drew the latest figures (M6a); False: Plotly reported an error

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._result: ResultSet | None = None
        self._epoch_utc: str | None = None
        self.figures: list = []  # the plotted go.Figure of each grid cell, in order
        self._time_cursor = None  # gui.time_cursor.TimeCursor, set by set_time_cursor()
        self.cursor_actions = self._build_cursor_actions()
        self._x_is_epoch = False  # the shown figures' x axis is UTC (else elapsed hours or orbit number)
        self._png_poll_state: dict | None = None  # set by _on_save_plot_png, read by _poll_plot_png
        self._live_redraw_elapsed = QElapsedTimer()  # throttles set_live_result()'s own redraws -- see
        # _LIVE_REDRAW_MIN_INTERVAL_MS's own comment
        self._shown: list = []  # the plots in the grid, in order (series names or ACCESS_TIMELINE)
        self._focused = 0  # the selected grid cell
        self._layout = "1x1"
        self._layout_key: str | None = None  # the scenario, for the saved layout
        self._hidden_kinds: set = set()  # event kinds switched off
        self._events_cache: tuple = (None, [], None, 0.0)  # (result, its events, its series names, when [s])
        self._allow_stale_events = False  # set while a live chunk that is not drawn rebuilds the figures
        self._orbit_cache: tuple = (None, None, None)  # (result, spacecraft, (time_s, numbers) or None)
        self._hover_time_s: float | None = None
        self._band_notes: list = []  # kinds left out of a plot for having too many bands
        # M6a: each plot's figure, kept until what it shows changes (_cached_plot):
        # name -> (key, go.Figure, its band notes)
        self._figure_cache: dict = {}
        self._cache_result = None  # the result the cached figures are of
        self._theme_generation = 0  # counts theme switches: a figure's colours come from the theme
        # The persistent page (plot_page.shell_page): loaded once, then sent each change.
        self._page_ready = False
        self._render_generation = 0  # the latest render sent; the page answers with it when drawn
        self._page_cells: list = []  # the figure each cell of the page shows
        self._page_json: dict = {}  # id(figure) -> (figure, its JSON), for the figures shown
        self._save_timer = QTimer(self)  # the layout is saved after the click, not in it
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_LAYOUT_SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._save_layout_now)

        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Layout:"))
        self.layout_combo = ComboBox()
        for name in plot_page.LAYOUTS:
            self.layout_combo.addItem(plot_page.layout_label(name), name)
        self.layout_combo.setToolTip("How many plots the grid shows. Tick plots in the catalog to fill it.")
        self.layout_combo.setAccessibleName("Plot layout")
        self.layout_combo.currentIndexChanged.connect(self._on_layout_chosen)
        top_row.addWidget(self.layout_combo)
        top_row.addWidget(QLabel("X-axis:"))
        self.x_axis_combo = ComboBox()
        for data, text in _X_AXES:
            self.x_axis_combo.addItem(text, data)
        self.x_axis_combo.setToolTip(
            "Applies to every plot. \"Epoch (UTC)\" needs the scenario's epoch, known once a run has produced "
            "this result. \"Orbit number\" counts one spacecraft's revolutions from the ascending node and needs "
            "its recorded position and velocity. Either falls back to elapsed time when it can't be shown."
        )
        self.x_axis_combo.setAccessibleName("X-axis")
        self.x_axis_combo.currentIndexChanged.connect(self._redraw)
        top_row.addWidget(self.x_axis_combo)
        self.events_label = QLabel("Events:")
        top_row.addWidget(self.events_label)
        self._event_buttons: dict = {}
        for kind in event_model.KINDS:
            button = QToolButton()
            button.setText(_EVENT_LABELS[kind])
            button.setCheckable(True)
            button.setChecked(True)
            button.setToolTip(f"Draw {_EVENT_LABELS[kind].lower()} on the plots")
            button.toggled.connect(lambda on, k=kind: self._on_event_kind_toggled(k, on))
            top_row.addWidget(button)
            self._event_buttons[kind] = button
        top_row.addStretch(1)
        layout.addLayout(top_row)

        # One-click shortcuts to the series the scenario's own description
        # points at ("What to look at"), so nobody has to find
        # berlin-gs.access_to_leo-comms-1.link_margin_db among 40 entries.
        # Filled from set_featured_series(); hidden when there are none. A
        # chip shows its plot in the selected cell.
        self._featured: list = []
        self._suggestion_chips: list = []
        self.suggestion_row = QWidget()
        suggestion_layout = QHBoxLayout(self.suggestion_row)
        suggestion_layout.setContentsMargins(0, 0, 0, 0)
        suggestion_label = QLabel("Suggested:")
        set_role(suggestion_label, tone="secondary")
        suggestion_layout.addWidget(suggestion_label, 0, Qt.AlignmentFlag.AlignTop)
        self._suggestion_box = QWidget()
        self._suggestion_flow = FlowLayout(self._suggestion_box)
        suggestion_layout.addWidget(self._suggestion_box, 1)
        self.suggestion_row.setVisible(False)
        layout.addWidget(self.suggestion_row)

        # "What am I looking at" (above) and "do something with it" (below)
        # are separate rows: one shared row squeezed the series box to a few
        # characters in the Results pane (a real regression, from a
        # screenshot).
        button_row = QHBoxLayout()
        self.export_button = QPushButton("Export CSV...")
        self.export_button.setToolTip("Export every series in this result as CSV files (SI units)")
        self.export_button.clicked.connect(self._on_export)
        self.export_button.setEnabled(False)
        button_row.addWidget(self.export_button)
        self.save_png_button = QPushButton("Save PNG...")
        self.save_png_button.setToolTip("Save the selected plot (click a plot to select it) as a PNG image")
        self.save_png_button.clicked.connect(self._on_save_plot_png)
        self.save_png_button.setEnabled(False)
        button_row.addWidget(self.save_png_button)
        # A vector export alongside the raster one, for a plot dropped into
        # a paper or report at any scale. Shares _on_save_plot_png's
        # dialog/kickoff/poll machinery via its ``fmt`` parameter.
        self.save_svg_button = QPushButton("Save SVG...")
        self.save_svg_button.setToolTip("Save the selected plot as a scalable vector (SVG) image")
        self.save_svg_button.clicked.connect(self._on_save_plot_svg)
        self.save_svg_button.setEnabled(False)
        button_row.addWidget(self.save_svg_button)
        # Every shown plot at once (U-29), with its data and the provenance.
        self.export_all_button = QPushButton("Export all...")
        self.export_all_button.setToolTip("Every shown plot as an image, with its data as CSV and the run's "
                                          "provenance, into one folder")
        export_menu = QMenu(self.export_all_button)
        for fmt, text in (("png", "PNG images and CSV..."), ("svg", "SVG images and CSV...")):
            action = QAction(text, export_menu)
            action.triggered.connect(lambda _checked=False, f=fmt: self._on_export_all(f))
            export_menu.addAction(action)
        export_menu.addSeparator()
        # The run's folder that runs itself again (transparency audit, Phase 2h).
        self.export_bundle_action = QAction("Reproduction bundle...", export_menu)
        self.export_bundle_action.setToolTip("Every series as CSV, the provenance, the scenario as run and copies of "
                                             "the files it refers to: 'spacemissionstudio reproduce' runs it again "
                                             "and compares")
        self.export_bundle_action.triggered.connect(self._on_export_bundle)
        export_menu.addAction(self.export_bundle_action)
        # The scenario file's folder at the last run start (gui.main_window):
        # a model's relative mesh paths are read from it.
        self.scenario_folder: Path | None = None
        self.export_all_button.setMenu(export_menu)
        self.export_all_button.setEnabled(False)
        button_row.addWidget(self.export_all_button)
        # An export in progress: how far, and Cancel (audit G2).
        self.export_progress_label = set_role(QLabel(""), tone="secondary")
        self.export_progress_label.hide()
        button_row.addWidget(self.export_progress_label)
        self.export_cancel_button = QPushButton("Cancel")
        self.export_cancel_button.setToolTip("Stops the export before its next file; the files written stay.")
        self.export_cancel_button.clicked.connect(self._cancel_export)
        self.export_cancel_button.hide()
        button_row.addWidget(self.export_cancel_button)
        self._export_worker: _ExportWorker | None = None
        self._export_ends: tuple = ()  # (on_done, on_failed, folder) of the export running
        # The last run's Vizard playback file (UX/UI guidelines, decision 3:
        # open only -- Vizard has no interface to follow the time cursor).
        self.vizard_button = QPushButton("Open in Vizard")
        self.vizard_button.setToolTip("Opens the playback file this run wrote in Vizard. Vizard cannot follow "
                                      "the time cursor.")
        self.vizard_button.clicked.connect(lambda: self.open_in_vizard.emit(self._vizard_file or ""))
        self.vizard_button.setVisible(False)
        self._vizard_file: str | None = None
        button_row.addWidget(self.vizard_button)
        button_row.addStretch(1)
        # Run comparison (UX/UI guidelines): the same series from an earlier
        # run of this session, dashed, and the inputs that differ.
        self._runs: list = []  # gui.run_history.RunRecord, oldest first
        self._current_run = None  # the RunRecord shown, when it is one
        self.compare_label = QLabel("Compare with:")
        self.compare_combo = ComboBox()
        self.compare_combo.setToolTip("Draws the same series from an earlier run of this session, dashed.")
        # Sized by a fixed number of characters, not by the longest run
        # label: a long scenario name widened the whole window past 1516 px
        # (docs/ux-audit.md U-03). Each item's tooltip has its full label.
        self.compare_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.compare_combo.setMinimumContentsLength(18)
        self.compare_combo.currentIndexChanged.connect(self._redraw)
        self.diff_button = QPushButton("Input differences...")
        self.diff_button.setToolTip("Lists every scenario input that differs between the two runs.")
        self.diff_button.clicked.connect(self.show_input_differences)
        layout.addLayout(button_row)
        # On a row of its own, shown only once there is an earlier run: on
        # the export row it made the pane, and so the window, too wide for
        # 1280 px (docs/ux-audit.md U-03).
        compare_row = QHBoxLayout()
        for widget in (self.compare_label, self.compare_combo, self.diff_button):
            widget.setVisible(False)
            compare_row.addWidget(widget)
        compare_row.addStretch(1)
        layout.addLayout(compare_row)

        # One line, always visible once a result exists, naming exactly what
        # produced it; blank for a hand-built result without provenance.
        self.provenance_label = QLabel("")
        set_role(self.provenance_label, role="small", tone="secondary")
        self.provenance_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.provenance_label.setWordWrap(True)  # never forces the pane wider
        # Fixed vertically: with Preferred, Qt gave this one-line label most
        # of the spare height and pushed the plots off the window (a real
        # bug, from a screenshot); the splitter below takes it instead.
        self.provenance_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.provenance_label)

        # The conservation/drift diagnostic (engine.results.
        # conservation_drift_warnings); hidden when there are none.
        self.warnings_label = QLabel("")
        self.warnings_label.setWordWrap(True)
        set_role(self.warnings_label, role="small", tone="caution")
        self.warnings_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.warnings_label.setVisible(False)
        self.warnings_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.warnings_label)
        # Event kinds left off a plot because there were too many bands.
        self.events_note = QLabel("")
        self.events_note.setWordWrap(True)
        set_role(self.events_note, role="small", tone="secondary")
        self.events_note.setVisible(False)
        self.events_note.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.events_note)
        # Qt counts a wrapped label's minimum height at its narrowest width:
        # at 90-130 px a one-line provenance line or warning took 4-5 lines
        # of the window's minimum height, and a second run left the window
        # at 1280 x 744. At 360 px each is at most two lines.
        for note in (self.provenance_label, self.warnings_label, self.events_note):
            note.setMinimumWidth(_NOTE_MIN_WIDTH_PX)

        self.catalog = PlotCatalog()
        self.catalog.activated.connect(self.show_series)
        self.catalog.toggled.connect(self._on_catalog_toggled)
        self.web_view = QWebEngineView()
        self.web_view.titleChanged.connect(self._on_page_title)
        self.web_view.loadFinished.connect(self._on_shell_loaded)
        self.web_view.setMinimumWidth(320)  # [px]
        on_change(self._on_theme_changed)
        # The page is written here and loaded from file: setHtml() cannot
        # reach the bundled plotly.js (a file:// URL) from a data URL.
        self._page_dir = temp_folders.temporary_directory(temp_folders.PLOT_PAGE)
        self._load_shell()
        self.readout = ReadoutPanel()
        # The catalog over the readout, beside the grid: the plots keep the
        # width (at 1280 px with the side panel open the pane is ~880 px).
        self.side_splitter = QSplitter(Qt.Orientation.Vertical)
        self.side_splitter.addWidget(self.catalog)
        self.side_splitter.addWidget(self.readout)
        self.side_splitter.setSizes([300, 200])  # [px]
        # Both may shrink: their own minimum heights (176 px together) made
        # the window taller than 720 px (docs/ux-audit.md U-03).
        self.catalog.setMinimumHeight(40)  # [px]
        self.readout.setMinimumHeight(30)  # [px]
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.side_splitter)
        self.splitter.addWidget(self.web_view)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([_CATALOG_WIDTH_PX[0], 650])  # [px]
        # The list follows the pane's width (resizeEvent) until the user
        # drags the divider; splitterMoved comes from drags only.
        self._catalog_dragged = False
        self.splitter.splitterMoved.connect(self._on_catalog_dragged)
        # stretch=1: the one widget in this column that should claim all
        # leftover vertical space -- see provenance_label's own comment.
        layout.addWidget(self.splitter, stretch=1)
        self._update_event_buttons()
        self._redraw()  # shows the empty-state message immediately, not just after the first set_result() call

    def resizeEvent(self, event):  # noqa: N802 -- Qt API name
        super().resizeEvent(event)
        total = sum(self.splitter.sizes())  # [px]
        if not self._catalog_dragged and total > 0:
            # At 2560 px a 250 px list cut most plot names short.
            wanted = min(max(int(total * _CATALOG_WIDTH_SHARE), _CATALOG_WIDTH_PX[0]), _CATALOG_WIDTH_PX[1])  # [px]
            self.splitter.setSizes([wanted, total - wanted])

    def hideEvent(self, event):  # noqa: N802 -- Qt API name
        if self in _PENDING_SAVES:
            self._save_layout_now()  # another area shown, or the window closed: no save left behind
        super().hideEvent(event)

    def _on_catalog_dragged(self, _pos: int, _index: int) -> None:
        self._catalog_dragged = True

    # -- the result ---------------------------------------------------------

    def set_result(self, result: ResultSet | None, epoch_utc: str | None = None) -> None:
        self._result = result
        self._epoch_utc = epoch_utc
        self._fill_catalog(result)
        self.export_button.setEnabled(result is not None and bool(result.series) and self._export_worker is None)
        self._update_provenance_label()
        self._update_warnings_label()
        self._update_event_buttons()
        self._redraw()

    @property
    def figure(self) -> go.Figure | None:
        """The selected plot's go.Figure, or None (empty state)."""
        return self.figures[self._focused] if 0 <= self._focused < len(self.figures) else None

    def _catalog_entries(self, result: ResultSet) -> list:
        """``(name, label, group)`` of every plot: the label is the plot
        title, or the code name when two plots would have the same title."""
        labels = {name: _series_label(name, series) for name, series in result.series.items()}
        counts: dict = {}
        for label in labels.values():
            counts[label] = counts.get(label, 0) + 1
        entries = [(name, self._chip_label(name) if counts[label] == 1 else name,
                    plot_group(name, result.series[name])) for name, label in labels.items()]
        if _has_access_series(result):
            entries.append((ACCESS_TIMELINE, "Ground Station Access Timeline", "Link"))
        return entries

    def _fill_catalog(self, result: ResultSet | None) -> None:
        """New result: the catalog lists its plots, and the grid opens on the
        layout saved for this scenario, else the first suggested series,
        else the first series."""
        if result is None:
            self._shown, self._focused = [], 0
            self.catalog.set_entries([], [])
            self._set_layout_combo("1x1")
            self._refresh_suggestions()
            return
        entries = self._catalog_entries(result)
        names = [entry[0] for entry in entries]
        layout, shown = self._saved_layout()
        shown = [name for name in shown if name in names]
        if not shown:
            featured = [name for name in self._featured if name in result.series]
            shown = [featured[0]] if featured else names[:1]
            layout = "1x1"
        self._layout = layout if layout in plot_page.LAYOUTS else plot_page.smallest_layout(len(shown))
        if plot_page.capacity(self._layout) < len(shown):
            self._layout = plot_page.smallest_layout(len(shown))
        self._shown = shown[:plot_page.capacity(self._layout)]
        self._focused = 0
        self.catalog.set_entries(entries, self._shown)
        self._set_layout_combo(self._layout)
        if self._shown:
            self.catalog.select(self._shown[0])
        self._refresh_suggestions()

    def set_featured_series(self, names) -> None:
        """The series to offer as one-click suggestions (normally
        ``engine.series_names.featured_series(scenario)`` for the scenario
        being run). Only those present in the result are shown, and a new
        result opens on the first of them (unless a layout was saved)."""
        self._featured = list(names)
        self._refresh_suggestions()

    def set_layout_key(self, key: str | None) -> None:
        """The scenario whose layout and plots the grid keeps (its name);
        None keeps nothing."""
        if self in _PENDING_SAVES:
            self._save_layout_now()  # the previous scenario's, before the key changes
        self._layout_key = key or None

    def _saved_layout(self) -> tuple:
        _write_pending_saves()  # a change still to be saved, by this view or another
        if not self._layout_key:
            return "1x1", []
        value = _settings().value(f"{_LAYOUT_SETTINGS_PREFIX}/{self._layout_key}")
        try:
            saved = json.loads(value) if isinstance(value, str) else {}
        except ValueError:
            saved = {}
        plots = saved.get("plots") if isinstance(saved, dict) else None
        return (saved.get("layout", "1x1") if isinstance(saved, dict) else "1x1",
                [p for p in plots if isinstance(p, str)] if isinstance(plots, list) else [])

    def _save_layout(self) -> None:
        """Save the layout and plots shortly after the change (the QSettings
        write took ~15 ms of the click, M6a); a pending save is written
        before another scenario's layout is read."""
        global _SAVES_ON_QUIT
        app = QApplication.instance()
        if app is not None and _SAVES_ON_QUIT is not app:
            app.aboutToQuit.connect(_write_pending_saves)
            _SAVES_ON_QUIT = app
        _PENDING_SAVES.add(self)
        self._save_timer.start()

    def _save_layout_now(self) -> None:
        self._save_timer.stop()
        _PENDING_SAVES.discard(self)
        if self._layout_key and self._result is not None:
            settings = _settings()
            settings.setValue(f"{_LAYOUT_SETTINGS_PREFIX}/{self._layout_key}",
                              json.dumps({"layout": self._layout, "plots": self._shown}))
            settings.sync()

    def _refresh_suggestions(self) -> None:
        for chip in self._suggestion_chips:
            self._suggestion_flow.removeWidget(chip)
            chip.deleteLater()
        self._suggestion_chips = []
        result = self._result
        names = [name for name in self._featured if result is not None and name in result.series]
        for name in names:
            chip = QPushButton(self._chip_label(name))
            chip.setObjectName("suggestionChip")
            chip.setCheckable(True)
            chip.setAutoDefault(False)
            chip.setToolTip(name)
            chip.setProperty("series_name", name)
            chip.clicked.connect(lambda _checked=False, n=name: self.show_series(n))
            self._suggestion_flow.addWidget(chip)
            self._suggestion_chips.append(chip)
        self.suggestion_row.setVisible(bool(names))
        self._update_suggestion_states()

    def _chip_label(self, name: str) -> str:
        """The plot title, minus what every chip would repeat: the
        spacecraft when the result has only one, and the station ->
        spacecraft pair when there is only one (the tooltip and the plot
        title still name them)."""
        result = self._result
        label = _series_label(name, result.series[name])
        pairs = {_parse_access_pair(n)[:2] for n in result.series if _parse_access_pair(n) is not None}
        spacecraft = {n.split(".", 1)[0] for n in result.series if _parse_access_pair(n) is None}
        if len(spacecraft) == 1 and label.startswith(f"{next(iter(spacecraft))}: "):
            label = label.split(": ", 1)[1]
        if len(pairs) == 1:
            gs, sc = next(iter(pairs))
            label = label.removesuffix(f": {gs} -> {sc}")
        return label

    def _update_suggestion_states(self) -> None:
        for chip in self._suggestion_chips:
            chip.setChecked(chip.property("series_name") in self._shown)

    # -- what the grid shows ------------------------------------------------

    def shown_plots(self) -> list:
        """The plots in the grid, in order (series names, or ACCESS_TIMELINE)."""
        return list(self._shown)

    def plot_names(self) -> list:
        """Every plot the catalog offers, in catalog order."""
        return self.catalog.names()

    def current_series_name(self) -> str:
        """Code name of the selected plot's series ("" when there is none,
        or the selected plot is the access timeline)."""
        if 0 <= self._focused < len(self._shown) and self._shown[self._focused] != ACCESS_TIMELINE:
            return self._shown[self._focused]
        return ""

    def show_series(self, name: str) -> None:
        """Show ``name`` (a series or ACCESS_TIMELINE): select its cell when
        it is already in the grid, else put it in the selected cell."""
        if self._result is None or name not in self.catalog.names():
            return
        if name in self._shown:
            self.focus_plot(self._shown.index(name))
            return
        if self._shown:
            self._shown[min(self._focused, len(self._shown) - 1)] = name
        else:
            self._shown, self._focused = [name], 0
        self.catalog.set_shown(self._shown)
        self.catalog.select(name)
        self._save_layout()
        self._redraw()

    def focus_plot(self, index: int) -> None:
        """Select grid cell ``index`` (no reload)."""
        if not 0 <= index < len(self._shown):
            return
        self._focused = index
        self.web_view.page().runJavaScript(plot_page.focus_script(index))
        self.catalog.select(self._shown[index])
        self._update_suggestion_states()

    def set_layout(self, name: str) -> None:
        """Show the grid as ``name`` (a key of plot_page.LAYOUTS); plots past
        its last cell leave the grid."""
        if name not in plot_page.LAYOUTS:
            return
        self._layout = name
        self._shown = self._shown[:plot_page.capacity(name)]
        self._focused = min(self._focused, max(len(self._shown) - 1, 0))
        self.catalog.set_shown(self._shown)
        self._set_layout_combo(name)
        self._save_layout()
        self._redraw()

    def _set_layout_combo(self, name: str) -> None:
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentIndex(max(self.layout_combo.findData(name), 0))
        self.layout_combo.blockSignals(False)

    def _on_layout_chosen(self) -> None:
        self.set_layout(self.layout_combo.currentData())

    def _on_catalog_toggled(self, name: str, on: bool) -> None:
        if on and name not in self._shown:
            if len(self._shown) >= plot_page.MAX_PLOTS:
                self.catalog.set_shown(self._shown)  # untick: the grid is full
                from .feedback import show_toast

                show_toast(self.window(), f"The grid shows at most {plot_page.MAX_PLOTS} plots: clear one first",
                           kind="info")
                return
            self._shown.append(name)
            self._focused = len(self._shown) - 1
            if plot_page.capacity(self._layout) < len(self._shown):
                self._layout = plot_page.best_layout(len(self._shown), self.web_view.width(),
                                                     self.web_view.height())
                self._set_layout_combo(self._layout)
        elif not on and name in self._shown:
            index = self._shown.index(name)
            self._shown.remove(name)
            if self._focused >= index:
                self._focused = max(self._focused - 1, 0)
        self._save_layout()
        self._redraw()

    # -- labels -------------------------------------------------------------

    def _update_warnings_label(self) -> None:
        warnings = self._result.warnings if self._result is not None else []
        if not warnings:
            self.warnings_label.setVisible(False)
            self.warnings_label.setText("")
            return
        self.warnings_label.setText("\n".join(f"⚠ {w}" for w in warnings))
        self.warnings_label.setToolTip(warnings_tooltip(warnings))
        self.warnings_label.setVisible(True)

    def _update_provenance_label(self) -> None:
        provenance = self._result.provenance if self._result is not None else None
        if provenance is None:
            self.provenance_label.setText("")
            self.provenance_label.setToolTip("")
            return
        run = f"{self._current_run.name} · " if self._current_run is not None else ""  # U-22
        self.provenance_label.setText(
            f"{run}SpaceMissionStudio {provenance.spacemissionstudio_version} · "
            f"Basilisk {provenance.basilisk_version} · {provenance.integrator.upper()}, "
            f"{provenance.dynamics_task_rate_s:g} s step · {_short_utc(provenance.run_started_utc)}"
        )
        self.provenance_label.setToolTip(provenance.rng_seed_note)

    def set_live_result(self, result: ResultSet, epoch_utc: str | None = None) -> None:
        """Updates the plots with one chunk's worth of a still-running
        simulation (see ``gui.run_worker.RunWorker``'s ``progress`` signal /
        :meth:`engine.service.SimulationService.run_live`). Unlike
        :meth:`set_result`, this never rebuilds the catalog once it already
        holds this result's series names -- the set of series a live run
        reports is fixed from its very first callback (which series exist
        is decided by the scenario, not by how much data has been
        recorded), so rebuilding it every chunk would keep resetting
        whatever the user is looking at, fighting them while they watch it
        run.

        The actual ``QWebEngineView`` redraw is throttled to at most once
        per :data:`_LIVE_REDRAW_MIN_INTERVAL_MS` -- see that constant's
        own comment for the real bug this fixes (a fast-running scenario
        firing chunks faster than a full page reload can settle, which
        left the plot visibly stuck). :attr:`figures` are still rebuilt
        from ``result`` on every single call, throttled or not.
        """
        is_first_update = self._result is None or set(self._result.series) != set(result.series)
        self._result = result
        self._epoch_utc = epoch_utc  # same every chunk of one run, but cheap enough not to bother guarding
        # Warnings can become non-empty partway through a long live run,
        # so they are updated on every call (a QLabel update is cheap).
        self._update_warnings_label()
        if is_first_update:
            self._fill_catalog(result)
            self.export_button.setEnabled(bool(result.series) and self._export_worker is None)
            self._update_provenance_label()
            self._update_event_buttons()
            self._redraw()
            self._live_redraw_elapsed.start()
            return
        # Throttled -- see _LIVE_REDRAW_MIN_INTERVAL_MS's own comment.
        # Skipping a chunk's WEBVIEW push only delays the display by at
        # most this interval; self.figures are kept fresh every chunk, a
        # user's own change (plot, layout, axis) redraws at once, and the
        # final frame always renders when the run ends.
        push = self._live_redraw_elapsed.elapsed() >= _LIVE_REDRAW_MIN_INTERVAL_MS
        self._allow_stale_events = not push
        try:
            self._update_figure()
        finally:
            self._allow_stale_events = False
        if push:
            self._push_figure_to_webview()
            self._live_redraw_elapsed.restart()

    # -- the time axis ------------------------------------------------------

    def _orbit_reference(self):
        """``(spacecraft, (time_s, numbers))`` the orbit-number axis uses, or
        ``(None, None)`` when no spacecraft recorded its position and
        velocity. The first shown series' spacecraft is preferred."""
        preferred = next((name.split(".", 1)[0] for name in self._shown if name != ACCESS_TIMELINE), None)
        result = self._result
        cached_result, cached_spacecraft, cached = self._orbit_cache
        spacecraft = orbit_number.reference_spacecraft(result, preferred)
        if cached_result is result and cached_spacecraft == spacecraft:
            return spacecraft, cached
        reference = orbit_number.for_result(result, spacecraft)
        self._orbit_cache = (result, spacecraft, reference)
        return spacecraft, reference

    def _x_mode(self) -> str:
        """The axis actually drawn: "epoch", "orbit" or "elapsed" (the first
        two fall back to elapsed time when they can't be shown)."""
        chosen = self.x_axis_combo.currentData()
        if chosen == "epoch" and self._epoch_utc:
            try:
                time_system.elapsed_to_utc(self._epoch_utc, [0.0])
                return "epoch"
            except ValueError:
                return "elapsed"
        if chosen == "orbit" and self._orbit_reference()[1] is not None:
            return "orbit"
        return "elapsed"

    def _x_axis_values(self, time_s, result: ResultSet | None = None, epoch_utc: str | None = None):
        """Returns ``(x_values, axis_label)`` for ``time_s`` [s] of ``result``
        (default: the shown one). "Epoch (UTC)" needs a real epoch and
        "Orbit number" a spacecraft's position and velocity; without them
        the axis falls back to elapsed time rather than raising, matching
        this widget's "never crash the GUI over display preferences"
        behaviour."""
        mode = self._x_mode()
        epoch_utc = epoch_utc if epoch_utc is not None else self._epoch_utc
        time_s = np.asarray(time_s, dtype=float)
        if mode == "epoch" and epoch_utc:
            try:
                # time_s is TDB seconds since the epoch (engine.time_system).
                return list(time_system.elapsed_to_utc(epoch_utc, time_s)), "Epoch (UTC)"
            except ValueError:
                pass
        if mode == "orbit":
            spacecraft, reference = self._orbit_reference()
            if result is not None and result is not self._result:
                reference = orbit_number.for_result(result, spacecraft)
            if reference is not None:
                ref_t, ref_n = reference
                note = orbit_number.reference_note(self._result, spacecraft)
                suffix = ", from the X axis" if "X axis" in note else ""  # an equatorial orbit has no node
                return np.interp(time_s, ref_t, ref_n), f"Orbit number ({spacecraft}{suffix})"
        return time_s / 3600.0, "Elapsed time [hr]"

    def _subtitle(self) -> str:
        """ "t0 = 2030-01-01 08:30:00 UTC" under a title, for an elapsed-time
        or orbit-number axis (U-30); the epoch axis shows UTC itself."""
        if self._x_mode() == "epoch" or not self._epoch_utc:
            return ""
        return f"t0 = {_utc_text(self._epoch_utc)}"

    # -- figures ------------------------------------------------------------

    def _compact(self) -> bool:
        """Several plots share the pane: smaller titles and margins."""
        return len(self._shown) > 1

    def _title(self, text: str) -> dict:
        subtitle = self._subtitle()
        return pt.title(TOKENS, text, subtitle, "body" if self._compact() else "section")

    def _margin(self, left: int = 70) -> dict:
        if self._compact():
            return dict(l=min(left, 62), r=16, t=52 if self._subtitle() else 36, b=40)
        return dict(l=left, r=30, t=78 if self._subtitle() else 60, b=50)

    def _build_figure(self, name: str, series: TimeSeries) -> go.Figure:
        display = _categorize(name, series) or _legacy_display(name, series)
        display_data = series.data * display.factor
        x_values, x_label = self._x_axis_values(series.time_s)
        is_datetime_axis = self._x_mode() == "epoch" and x_label == "Epoch (UTC)"
        self._x_is_epoch = is_datetime_axis

        traces = []
        column_labels = display.columns or {}
        x_array = np.asarray(x_values, dtype=object if isinstance(x_values, list) else None)
        # A Monte Carlo batch's per-run series (columns run_0, run_1, ...):
        # the runs are interchangeable, so one thin, translucent colour and
        # one legend entry rather than a colour (and legend row) each.
        ensemble = len(series.columns) > 1 and all(str(c).startswith("run_") for c in series.columns)
        # Compared with another run, each trace says which run it is (U-22).
        own_run = (f" (Run {self._current_run.number})"
                   if self._current_run is not None and self.comparison_run() is not None else "")
        for i, column in enumerate(series.columns):
            if display.wrap_period:
                keep = _wrapping_display_indices(len(display_data))
                x_shown, y_shown = _break_at_wraps(x_array[keep], display_data[keep, i], display.wrap_period)
            else:
                keep = _display_indices(display_data[:, i])  # see _MAX_PLOT_POINTS_PER_LINE
                x_shown, y_shown = x_array[keep], display_data[keep, i]
            traces.append(go.Scatter(
                x=list(x_shown) if x_array.dtype == object else x_shown, y=y_shown, mode="lines",
                name=(f"Each run ({len(series.columns)})" if ensemble
                      else f"{column_labels.get(column, column)}{own_run}"),
                line=(dict(color=_SERIES_COLORS[0], width=1) if ensemble
                      else dict(color=_SERIES_COLORS[i % len(_SERIES_COLORS)], width=2)),
                **(dict(opacity=0.45, legendgroup="runs", showlegend=i == 0,
                        hovertemplate=f"Run {str(column)[4:]}: %{{y:.4g}}<extra></extra>") if ensemble else {}),
            ))
        traces += self._comparison_traces(name, display)

        axis_common = pt.axis(TOKENS)
        y_title = f"{display.y_label} [{display.unit}]" if display.y_label else (f"[{display.unit}]" if display.unit else None)
        y_axis = dict(axis_common, title_text=y_title)
        x_axis = dict(axis_common, title_text=x_label)
        if not is_datetime_axis:
            # Never an offset/scientific tick notation (the complaint that
            # started this widget), and comma grouping for large numbers;
            # meaningless on a date axis, which Plotly formats itself.
            y_axis["exponentformat"] = "none"
            y_axis["separatethousands"] = True
            x_axis["exponentformat"] = "none"
            x_axis["separatethousands"] = True

        # One validated construction, traces and layout together (M6a): each
        # update_layout() parsed every key path again, ~60 ms a figure.
        return go.Figure(data=traces, layout=dict(
            title=self._title(_series_label(name, series)),
            xaxis=x_axis,
            yaxis=y_axis,
            **_template_layout(),
            # one hover row per run would list them all; show the run under the pointer
            hovermode="closest" if ensemble else "x unified",
            # a single series names itself in the title -- no legend box needed, unless compared
            showlegend=len(series.columns) > 1 or self.comparison_run() is not None,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(color=TOKENS["text.secondary"])),
            margin=self._margin(),
            shapes=self._event_shapes(name),
        ))

    def _events(self) -> list:
        """The result's events (engine.events), cached. A live run sends a
        new result every chunk: for a chunk that is not drawn (throttled)
        the events are read again at most every _EVENTS_REFRESH_S while the
        series stay the same (each read goes through the whole run so far);
        anything drawn has them fresh."""
        cached_result, cached, keys, when = self._events_cache
        result = self._result
        if cached_result is result:
            return cached
        now = time.monotonic()
        if (self._allow_stale_events and result is not None and keys == frozenset(result.series)
                and now - when < _EVENTS_REFRESH_S):
            return cached
        cached = event_model.extract_events(result)
        self._events_cache = (result, cached, frozenset(result.series) if result is not None else None, now)
        return cached

    def _event_x(self, times_s: list) -> list:
        """Event times [s] on the shown x axis."""
        x_values, _label = self._x_axis_values(np.asarray(times_s, dtype=float))
        return list(x_values) if isinstance(x_values, list) else [float(x) for x in x_values]

    def _event_shapes(self, name: str) -> list:
        """The run's events behind ``name``'s lines (U-27): a band from start
        to end of each, in the Events tab's colour; a mode change a dashed
        line at its start. Only the plot's own spacecraft's events."""
        from .event_timeline_widget import kind_colour

        parsed = _parse_access_pair(name)
        spacecraft = parsed[1] if parsed is not None else name.split(".", 1)[0]
        events = [e for e in self._events() if e.spacecraft == spacecraft and e.kind not in self._hidden_kinds]
        shapes = []
        for kind in event_model.KINDS:
            of_kind = [e for e in events if e.kind == kind]
            if not of_kind:
                continue
            if len(of_kind) > _MAX_BANDS_PER_KIND:
                self._band_notes.append(f"{_EVENT_LABELS[kind]} of {spacecraft}: {len(of_kind):,}, too many to draw "
                                        f"(see the Timeline)")
                continue
            colour = kind_colour(kind)
            starts = self._event_x([e.start_s for e in of_kind])
            ends = self._event_x([e.end_s for e in of_kind])
            for start, end in zip(starts, ends):
                if kind == event_model.MODE:
                    shapes.append(dict(type="line", xref="x", yref="paper", x0=start, x1=start, y0=0, y1=1,
                                       layer="below", name=f"event-{kind}",
                                       line=dict(color=colour, width=1, dash="dash")))
                else:
                    shapes.append(dict(type="rect", xref="x", yref="paper", x0=start, x1=end, y0=0, y1=1,
                                       layer="below", name=f"event-{kind}", fillcolor=colour,
                                       opacity=_BAND_OPACITY, line=dict(width=0)))
        return shapes

    def _update_event_buttons(self) -> None:
        """Offer the kinds this run has."""
        present = {e.kind for e in self._events()}
        for kind, button in self._event_buttons.items():
            button.setVisible(kind in present)
        self.events_label.setVisible(bool(present))

    def _on_event_kind_toggled(self, kind: str, on: bool) -> None:
        (self._hidden_kinds.discard if on else self._hidden_kinds.add)(kind)
        self._redraw()

    def _build_plot(self, name: str) -> go.Figure | None:
        if name == ACCESS_TIMELINE:
            return self._build_access_timeline_figure()
        series = self._result.series.get(name) if self._result is not None else None
        return self._build_figure(name, series) if series is not None else None

    def _figure_key(self) -> tuple:
        """What a figure shows besides its series: a figure built with
        another key is built again (M6a)."""
        mode = self._x_mode()
        other = self.comparison_run()
        return (mode, self._epoch_utc, self._compact(), self._orbit_reference()[0] if mode == "orbit" else None,
                frozenset(self._hidden_kinds), None if other is None else other.number,
                None if self._current_run is None else self._current_run.number, self._theme_generation)

    def _cached_plot(self, name: str) -> go.Figure | None:
        """``name``'s figure: the one built before when nothing it shows has
        changed, else a new one (M6a: showing another plot builds only that
        plot)."""
        if self._cache_result is not self._result:
            self._figure_cache, self._cache_result = {}, self._result
        key = self._figure_key()
        cached = self._figure_cache.get(name)
        if cached is not None and cached[0] == key:
            self._band_notes.extend(cached[2])
            return cached[1]
        notes = len(self._band_notes)
        fig = self._build_plot(name)
        self._figure_cache[name] = (key, fig, list(self._band_notes[notes:]))
        return fig

    def _update_figure(self) -> None:
        """Rebuilds :attr:`figures` from the current result and the shown
        plots -- cheap (no page reload), so it is kept fresh even on a chunk
        :meth:`set_live_result` otherwise throttles: other code (the save
        buttons, tests) reads :attr:`figure`/:attr:`figures` directly and
        must never see stale data just because the page push was skipped."""
        self.figures = []
        self._band_notes = []
        self._x_is_epoch = False
        if self._result is None:
            return
        built = [(name, self._cached_plot(name)) for name in self._shown]
        self._shown = [name for name, fig in built if fig is not None]
        self.figures = [fig for _name, fig in built if fig is not None]
        self._x_is_epoch = self._x_mode() == "epoch" and any(name != ACCESS_TIMELINE for name in self._shown)
        self._focused = min(self._focused, max(len(self.figures) - 1, 0))
        self.events_note.setText("\n".join(self._band_notes))
        self.events_note.setVisible(bool(self._band_notes))

    def _build_access_timeline_figure(self) -> go.Figure | None:
        """One Gantt-style chart of every
        ``{station}.access_to_{spacecraft}.has_access`` series in the result
        (roadmap item M5).

        Uses ELAPSED TIME ONLY, whatever the axis choice -- a horizontal
        bar on Plotly's date axis needs ``timedelta`` values, and the view's
        point is "every pass at a glance", which elapsed time serves. So in
        the grid its x axis is not linked to the others.
        """
        pairs: list = []
        for name, series in self._result.series.items():
            parsed = _parse_access_pair(name)
            if parsed is None or parsed[2] != "has_access":
                continue
            gs, sc, _field = parsed
            pairs.append((f"{gs} -> {sc}", series))
        pairs.sort(key=lambda item: item[0])

        fig = go.Figure()
        t_end_hr = max((float(series.time_s[-1]) for _label, series in pairs if len(series.time_s)),
                       default=0.0) / 3600.0
        if not pairs:
            fig.update_layout(
                annotations=[dict(
                    text="No ground-station access series in this result (no ground stations configured?)",
                    showarrow=False, font=dict(color=TOKENS["text.secondary"], size=SIZE["body"]),
                    xref="paper", yref="paper", x=0.5, y=0.5,
                )],
                **_template_layout(),
                xaxis=dict(visible=False), yaxis=dict(visible=False),
            )
            return fig

        for row_index, (pair_label, series) in enumerate(pairs):
            t_hours = series.time_s / 3600.0
            has_access = series.data[:, series.columns.index("has_access")] != 0
            color = _SERIES_COLORS[row_index % len(_SERIES_COLORS)]
            # Each contiguous True run in has_access is one thick line
            # segment; all of a pair's segments share ONE trace, separated
            # by None gaps. One trace per pass made thousands of traces on
            # a long run (2,865 for six pairs over a month), which Plotly
            # is slow to draw.
            padded = np.concatenate([[False], has_access, [False]])
            changes = np.flatnonzero(np.diff(padded.astype(int)))
            starts, ends = changes[0::2], changes[1::2] - 1
            if len(starts):
                xs: list = []
                ys: list = []
                for start, end in zip(starts, ends):
                    xs += [t_hours[start], t_hours[end], None]
                    ys += [pair_label, pair_label, None]
                # A tick at each end keeps a short pass visible on a long
                # run, where its segment is narrower than a pixel.
                fig.add_trace(go.Scatter(
                    x=xs, y=ys, mode="lines+markers", line=dict(color=color, width=16), connectgaps=False,
                    marker=dict(symbol="line-ns", size=16, line=dict(color=color, width=1)),
                    name=pair_label, hovertemplate=f"{pair_label}<br>%{{x:.3f}} hr<extra></extra>",
                ))
            else:
                # No access window at all for this pair: still a row (an
                # invisible trace), so it does not vanish from the chart.
                fig.add_trace(go.Scatter(
                    x=[t_hours[0]], y=[pair_label], mode="markers",
                    marker=dict(size=0, color=color), name=pair_label, legendgroup=pair_label,
                    hoverinfo="skip",
                ))

        axis_common = pt.axis(TOKENS)
        subtitle = f"t0 = {_utc_text(self._epoch_utc)}" if self._epoch_utc else ""
        title = "Ground Station Access Timeline"
        fig.update_layout(
            title=pt.title(TOKENS, title, subtitle),
            # Fixed to the run: the end-of-pass ticks would otherwise pad
            # the axis to before t = 0.
            xaxis=dict(axis_common, title_text="Elapsed time [hr]", exponentformat="none",
                       separatethousands=True, range=[0.0, t_end_hr]),
            yaxis=dict(axis_common, title_text=None, categoryorder="category descending"),
            **_template_layout(),
            showlegend=False,  # the y-axis category labels already name every pair -- a legend would be redundant
            margin=dict(l=160, r=30, t=78 if subtitle else 60, b=50),
        )
        return fig

    def _empty_text(self) -> str:
        return "Run a simulation to see results here" if self._result is None else \
            "Tick a plot in the catalog to show it here"

    def _load_shell(self) -> None:
        """Load the persistent page (M6a): plotly.js once; every change is
        then sent to it (:meth:`_push_figure_to_webview`). Loaded again only
        for a theme switch (its fonts and surface)."""
        self._page_ready = False
        self._page_cells, self._page_json = [], {}
        page = Path(self._page_dir.name) / "plots.html"
        if not page.parent.is_dir():
            return  # shutting down: Python removed the temporary directory first
        page.write_text(plot_page.shell_page(QUrl.fromLocalFile(str(_plotlyjs_path())).toString(), _page_style()),
                        encoding="utf-8")
        self.web_view.load(QUrl.fromLocalFile(str(page)))

    def _on_shell_loaded(self, _ok: bool) -> None:
        self._page_ready = True
        self._push_figure_to_webview()

    def _figure_json(self, fig: go.Figure) -> str:
        known = self._page_json.get(id(fig))
        return known[1] if known is not None and known[0] is fig else fig.to_json()

    def _push_figure_to_webview(self) -> None:
        """Sends :attr:`figures` (already current -- see
        :meth:`_update_figure`) to the persistent page: only the figures a
        cell does not show already (M6a; it used to load a new page with
        plotly.js each time). The page answers when they are drawn
        (:attr:`plot_drawn`). See :meth:`set_live_result`'s throttling
        comment for why this is split from building the figures.
        """
        if self._page_ready:
            self._render_generation += 1
            if not self.figures:
                script = plot_page.render_script([], self._layout, 0, [], self._render_generation,
                                                 empty=self._empty_text())
                self._page_cells, self._page_json = [], {}
            else:
                sent = [None if i < len(self._page_cells) and self._page_cells[i] is fig else self._figure_json(fig)
                        for i, fig in enumerate(self.figures)]
                self._page_json = {id(fig): (fig, self._figure_json(fig) if text is None else text)
                                   for fig, text in zip(self.figures, sent)}
                self._page_cells = list(self.figures)
                script = plot_page.render_script(sent, self._layout, self._focused,
                                                 [name != ACCESS_TIMELINE for name in self._shown],
                                                 self._render_generation)
            self.web_view.page().runJavaScript(script)
        # Never force-enable while a save-as-PNG poll is in flight (a live
        # run redraws repeatedly while the user's earlier click is still
        # being polled) -- see _on_save_plot_png's re-entrancy guard.
        # _poll_plot_png's completion paths re-enable them.
        if self._png_poll_state is None:
            for button in (self.save_png_button, self.save_svg_button, self.export_all_button):
                button.setEnabled(bool(self.figures))
            self.export_all_button.setEnabled(bool(self.figures) and self._export_worker is None)

    def _on_page_loaded(self) -> None:
        self.apply_cursor_line()
        self._update_readout()

    # -- comparison ---------------------------------------------------------

    def set_runs(self, runs: list, current=None) -> None:
        """The session's runs (``gui.run_history.RunRecord``) and the one shown;
        the others are offered under "Compare with"."""
        chosen = self.compare_combo.currentData()
        self._runs, self._current_run = list(runs), current
        others = [r for r in self._runs if current is None or r.number != current.number]
        self.compare_combo.blockSignals(True)
        self.compare_combo.clear()
        self.compare_combo.addItem("(no comparison)", None)
        for record in reversed(others):
            self.compare_combo.addItem(record.label, record.number)
            self.compare_combo.setItemData(self.compare_combo.count() - 1, record.label, Qt.ItemDataRole.ToolTipRole)
        index = self.compare_combo.findData(chosen) if chosen is not None else 0
        self.compare_combo.setCurrentIndex(max(index, 0))
        self.compare_combo.blockSignals(False)
        for widget in (self.compare_label, self.compare_combo, self.diff_button):
            widget.setVisible(bool(others) and current is not None)
        self._update_provenance_label()
        if chosen is not None or self.compare_combo.currentData() is not None:
            self._redraw()  # the comparison drawn changed; with none before or after, the plots are as they were (M5a)

    def comparison_run(self):
        number = self.compare_combo.currentData()
        return next((r for r in self._runs if r.number == number), None) if number is not None else None

    def input_differences(self) -> list:
        """``(input, shown run's value, compared run's value)`` rows."""
        from ..engine import scenario_diff

        other = self.comparison_run()
        if other is None or self._current_run is None:
            return []
        return scenario_diff.diff(self._current_run.scenario, other.scenario)

    def show_input_differences(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem

        from ..engine.scenario_diff import short

        other = self.comparison_run()
        rows = self.input_differences()
        dialog = QDialog(self)
        dialog.setWindowTitle("Input differences")
        dialog.resize(760, 420)  # [px]
        table = QTableWidget(len(rows), 3, dialog)
        table.setTabKeyNavigation(False)  # read-only: Tab leaves the table; the arrows move in it (M9)
        table.setHorizontalHeaderLabels(["Input", f"Run {self._current_run.number} (shown)",
                                         f"Run {other.number}" if other else "-"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row, (path, mine, theirs) in enumerate(rows):
            for column, text in enumerate((path, short(mine), short(theirs))):
                item = QTableWidgetItem(text)
                item.setToolTip(str((path, mine, theirs)[column]))
                table.setItem(row, column, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{len(rows)} input(s) differ." if rows else "The inputs are the same."))
        layout.addWidget(table)
        layout.addWidget(buttons)
        dialog.exec()

    def _comparison_traces(self, name: str, display) -> list:
        """The compared run's copy of ``name``, dashed, in the same colours."""
        other = self.comparison_run()
        series = other.result.series.get(name) if other is not None else None
        if series is None or series.data.shape[0] == 0:
            return []
        if self._x_mode() == "epoch" and not other.epoch_utc:
            return []
        x_values, _label = self._x_axis_values(series.time_s, other.result, other.epoch_utc or None)
        x_values = np.asarray(x_values, dtype=object if isinstance(x_values, list) else None)
        data = series.data * display.factor
        labels = display.columns or {}
        traces = []
        for i, column in enumerate(series.columns):
            if display.wrap_period:  # broken at the 0/360 wraps, as the shown run
                keep = _wrapping_display_indices(len(data))
                x_shown, y_shown = _break_at_wraps(x_values[keep], data[keep, i], display.wrap_period)
            else:
                keep = _display_indices(data[:, i])
                x_shown, y_shown = x_values[keep], data[keep, i]
            traces.append(go.Scatter(
                x=list(x_shown) if x_values.dtype == object else x_shown, y=y_shown, mode="lines",
                name=f"{labels.get(column, column)} (Run {other.number})", opacity=0.75,
                line=dict(color=_SERIES_COLORS[i % len(_SERIES_COLORS)], width=2, dash="dash"),
            ))
        return traces

    def set_vizard_file(self, path: str | None) -> None:
        """Offer "Open in Vizard" for ``path`` (the run's playback file), or hide it."""
        self._vizard_file = path
        self.vizard_button.setVisible(bool(path))

    # -- the shared time cursor and the readout -----------------------------

    def set_time_cursor(self, cursor) -> None:
        """Follow ``cursor`` (a :class:`gui.time_cursor.TimeCursor`) and set it on a plot click."""
        self._time_cursor = cursor
        cursor.changed.connect(lambda _t: self._on_cursor_moved())
        self.apply_cursor_line()

    # The time cursor from the keyboard (docs/ux-standard.md, keyboard-only
    # use): a step is one sample of the selected plot's series.
    _CURSOR_KEYS = (
        ("Next Sample", "Alt+Right", "step_cursor", 1),
        ("Previous Sample", "Alt+Left", "step_cursor", -1),
        ("Ten Samples On", "Alt+Shift+Right", "step_cursor", 10),
        ("Ten Samples Back", "Alt+Shift+Left", "step_cursor", -10),
        ("Next Event", "Alt+PgDown", "cursor_to_event", 1),
        ("Previous Event", "Alt+PgUp", "cursor_to_event", -1),
        ("Start of the Run", "Alt+Home", "cursor_to_end", -1),
        ("End of the Run", "Alt+End", "cursor_to_end", 1),
    )  # Clear Time Cursor (Alt+Backspace, MainWindow) clears it

    def _build_cursor_actions(self) -> list:
        """The time cursor's keyboard commands: shortcuts while Results has
        the focus (MainWindow registers them as the Time Cursor commands)."""
        actions = []
        for text, keys, method, amount in self._CURSOR_KEYS:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(keys))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.setData((method, amount))
            action.triggered.connect(self._on_cursor_action)
            self.addAction(action)
            actions.append(action)
        return actions

    def _on_cursor_action(self) -> None:
        method, amount = self.sender().data()
        getattr(self, method)(amount)

    def _cursor_times(self) -> np.ndarray:
        """The sample times [s] the cursor steps through: the selected
        plot's series (the first shown series for the access timeline)."""
        result = self._result
        if result is None:
            return np.zeros(0)
        focused = self._shown[self._focused] if 0 <= self._focused < len(self._shown) else None
        candidates = [focused, *self._shown, *result.series]
        name = next((n for n in candidates if n in result.series), None)
        return np.asarray(result.series[name].time_s, dtype=float) if name is not None else np.zeros(0)

    def step_cursor(self, steps: int) -> None:
        """Move the cursor ``steps`` samples (back when negative); with no
        cursor, put it on the first sample (or the last, going back)."""
        times = self._cursor_times()
        if self._time_cursor is None or not len(times):
            return
        now = self._time_cursor.time_s
        if now is None:
            index = 0 if steps > 0 else len(times) - 1
        else:
            index = int(np.argmin(np.abs(times - now))) + steps
        self._time_cursor.set_time(float(times[min(max(index, 0), len(times) - 1)]))

    def cursor_to_end(self, direction: int) -> None:
        """The cursor to the run's first sample (``direction`` < 0) or last."""
        times = self._cursor_times()
        if self._time_cursor is not None and len(times):
            self._time_cursor.set_time(float(times[0] if direction < 0 else times[-1]))

    def cursor_to_event(self, direction: int) -> None:
        """The cursor to the start of the next (or previous) event of the
        kinds shown; from no cursor, the first (or last) event."""
        if self._time_cursor is None:
            return
        starts = sorted({e.start_s for e in self._events() if e.kind not in self._hidden_kinds})
        now = self._time_cursor.time_s
        if direction > 0:
            later = [t for t in starts if now is None or t > now + 1e-6]
            target = later[0] if later else None
        else:
            earlier = [t for t in starts if now is None or t < now - 1e-6]
            target = earlier[-1] if earlier else None
        if target is not None:
            self._time_cursor.set_time(float(target))

    def _on_cursor_moved(self) -> None:
        self.apply_cursor_line()
        self._update_readout()

    def _plot_is_hours(self, index: int) -> bool:
        """Plot ``index`` is drawn against elapsed hours (the access timeline always is)."""
        names = self._shown
        return (0 <= index < len(names) and names[index] == ACCESS_TIMELINE) or self._x_mode() == "elapsed"

    def plot_x_to_elapsed_s(self, x: str, index: int | None = None) -> float | None:
        """Elapsed (TDB) seconds of an x value of plot ``index`` (default:
        the selected one): hours, an orbit number, or UTC text on an epoch
        axis."""
        index = self._focused if index is None else index
        try:
            if self._plot_is_hours(index):
                return float(x) * 3600.0  # [s]
            if self._x_mode() == "orbit":
                _spacecraft, (ref_t, ref_n) = self._orbit_reference()
                return float(np.interp(float(x), np.maximum.accumulate(ref_n), ref_t))  # [s]
            clicked = datetime.fromisoformat(x.strip().replace("T", " "))
            epoch = datetime.fromisoformat(self._epoch_utc.replace("Z", "").replace("T", " "))
        except (TypeError, ValueError, AttributeError):
            return None
        first_guess = (clicked - epoch).total_seconds()  # [s]
        try:  # one correction for the TDB - UTC change since the epoch (time_system.elapsed_to_utc)
            back = time_system.elapsed_to_utc(self._epoch_utc, [first_guess])[0]
        except ValueError:
            return first_guess
        return first_guess + (clicked - back).total_seconds()  # [s]

    def _on_page_title(self, title: str) -> None:
        message = plot_page.parse_message(title)
        if message is None:
            return
        kind, index, x = message
        if kind == "drawn":
            if index == self._render_generation:  # not an earlier render, overtaken
                self._on_page_loaded()
                self.plot_drawn.emit(x == "ok")
        elif kind == "focus":
            self.focus_plot(index)
        elif kind == "click" and x is not None:
            self.focus_plot(index)
            self._on_plot_clicked(x, index)
        elif kind == "hover":
            self._hover_time_s = self.plot_x_to_elapsed_s(x, index) if x is not None else None
            self._update_readout()

    def _on_plot_clicked(self, x: str, index: int | None = None) -> None:
        time_s = self.plot_x_to_elapsed_s(x, index)
        if time_s is not None and self._time_cursor is not None:
            self._time_cursor.set_time(time_s)

    def cursor_x_literal(self, index: int | None = None) -> str:
        """The cursor as a JavaScript x value for plot ``index`` (default:
        the selected one), or ``null``."""
        index = self._focused if index is None else index
        time_s = None if self._time_cursor is None else self._time_cursor.time_s
        if time_s is None or not 0 <= index < len(self.figures):
            return "null"
        if self._plot_is_hours(index):
            return repr(time_s / 3600.0)  # [h]
        if self._x_mode() == "orbit":
            _spacecraft, (ref_t, ref_n) = self._orbit_reference()
            return repr(float(np.interp(time_s, ref_t, ref_n)))
        try:
            moment = time_system.elapsed_to_utc(self._epoch_utc, [time_s])[0]
        except (ValueError, TypeError):
            return "null"
        return json.dumps(moment.isoformat(sep=" "))

    def apply_cursor_line(self) -> None:
        """Draw (or remove) the cursor line on every loaded plot, without a reload."""
        if not self.figures:
            return
        literals = [self.cursor_x_literal(i) for i in range(len(self.figures))]
        self.web_view.page().runJavaScript(plot_page.cursor_script(literals, TOKENS['accent']))

    def readout_time_s(self) -> float | None:
        """The time the readout shows: under the pointer, else the cursor's."""
        if self._hover_time_s is not None:
            return self._hover_time_s
        return None if self._time_cursor is None else self._time_cursor.time_s

    def _update_readout(self) -> None:
        """Every shown series' value at :meth:`readout_time_s` (U-25)."""
        time_s = self.readout_time_s()
        if time_s is None or self._result is None:
            self.readout.show_rows("Readout: click a plot or press Alt+Right to set the cursor, "
                                   "or point at a plot", [])
            return
        source = "pointer" if self._hover_time_s is not None else "cursor"
        heading = f"At t = {time_s / 3600.0:.4f} h"
        if self._epoch_utc:
            try:
                moment = time_system.elapsed_to_utc(self._epoch_utc, [time_s])[0]
                heading += f" · {moment.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            except ValueError:
                pass
        spacecraft, reference = self._orbit_reference()
        if reference is not None:
            heading += f" · orbit {float(np.interp(time_s, reference[0], reference[1])):.3f} of {spacecraft}"
        blocks = []
        for name in self._shown:
            series = self._result.series.get(name)
            if series is None:
                continue
            display = _categorize(name, series) or _legacy_display(name, series)
            labels = dict(display.columns or {})
            if len(series.columns) == 1 and not labels and display.y_label:
                labels = {series.columns[0]: display.y_label}
            lines = [(labels.get(column, column), value_at(series, i, time_s, display.factor,
                                                           wraps=display.wrap_period is not None), display.unit)
                     for i, column in enumerate(series.columns)]
            blocks.append((self._chip_label(name), lines))
        self.readout.show_rows(f"{heading} ({source})", blocks)

    def _redraw(self) -> None:
        self._update_figure()
        self._push_figure_to_webview()
        self._update_suggestion_states()

    def _on_theme_changed(self, _mode: str) -> None:
        """Redraw the shown plots (or the empty page) in the new theme, after
        the switch itself has returned: the page (its fonts and surface) is
        loaded again, and the figures built again in the theme's colours."""
        self._theme_generation += 1
        QTimer.singleShot(0, self, self._reload_in_theme)

    def _reload_in_theme(self) -> None:
        self._update_figure()
        self._load_shell()  # its load sends the figures

    # -- export -------------------------------------------------------------

    def _on_export(self) -> None:
        if self._result is None:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Export results to CSV")
        if not out_dir or self._export_worker is not None:
            return
        result = self._result

        def done(paths) -> None:
            csv_count = sum(1 for key in paths if key != "provenance")
            export_log.record("plot_csv", out_dir)
            report(self, f"Exported {csv_count} CSV file(s) to {out_dir}", kind="success")

        self._start_export(lambda step: result.export_csv(Path(out_dir), progress=step), done,
                           lambda message: report(self, f"Could not export the results to {out_dir}: {message}"),
                           out_dir)

    # -- an export's files, written off the GUI thread (audit G2) ----------------------

    def _start_export(self, job, on_done, on_failed, folder: str) -> None:
        worker = _ExportWorker(job)
        # The widget's own methods, not lambdas: Qt disconnects them when the
        # widget is deleted, so an export that ends after it calls nothing.
        self._export_ends = (on_done, on_failed, folder)
        worker.progress.connect(self._on_export_progress)
        worker.finished_ok.connect(self._on_export_done)
        worker.failed.connect(self._on_export_failed)
        worker.cancelled.connect(self._on_export_cancelled)
        self._export_worker = worker
        self.export_button.setEnabled(False)
        self.export_all_button.setEnabled(False)
        self.export_progress_label.setText("Exporting...")
        self.export_progress_label.show()
        self.export_cancel_button.setEnabled(True)
        self.export_cancel_button.show()
        _exports.add(worker)
        worker.finished.connect(lambda: _exports.discard(worker))
        worker.start()

    def _on_export_done(self, outcome) -> None:
        on_done = self._export_ends[0]
        self._end_export()
        on_done(outcome)

    def _on_export_failed(self, message: str) -> None:
        on_failed = self._export_ends[1]
        self._end_export()
        on_failed(message)

    def _on_export_cancelled(self, written: int) -> None:
        folder = self._export_ends[2]
        self._end_export()
        report(self, f"Export cancelled: {written} file(s) were written to {folder}", kind="warning")

    def _on_export_progress(self, written: int, total: int) -> None:
        self.export_progress_label.setText(f"Exporting {min(written + 1, total)} of {total} files...")

    def _cancel_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.request_cancel()
            self.export_cancel_button.setEnabled(False)
            self.export_progress_label.setText("Cancelling...")

    def _end_export(self) -> None:
        self._export_worker = None
        self.export_progress_label.hide()
        self.export_cancel_button.hide()
        self.export_button.setEnabled(self._result is not None and bool(self._result.series))
        self.export_all_button.setEnabled(bool(self.figures) and self._png_poll_state is None)

    def wait_for_export(self) -> None:
        """Let an export finish (the window is closing; tests)."""
        if self._export_worker is not None:
            self._export_worker.wait()

    def _on_export_bundle(self) -> None:
        """Results › Plots › Export all... › Reproduction bundle...: the shown
        run as a reproduction bundle (``reproduction.export_bundle``), into
        an empty folder."""
        if self._result is None or self._current_run is None or self._export_worker is not None:
            return
        folder = QFileDialog.getExistingDirectory(self, "Export a reproduction bundle (choose an empty folder)")
        if folder:
            self.export_bundle(Path(folder))

    def export_bundle(self, folder: Path) -> None:
        """The shown run (its kept record's scenario and result) as a
        reproduction bundle in ``folder``, which must be empty, off the GUI
        thread."""
        from .. import reproduction
        from ..schema.scenario import Scenario

        if any(folder.iterdir()):
            report(self, f"{folder} is not empty: choose an empty folder for the bundle, so that it holds only this "
                         "run's files")
            return
        result, scenario = self._result, Scenario.from_dict(self._current_run.scenario)
        base_dir, epoch_utc = self.scenario_folder, self._epoch_utc

        def done(manifest) -> None:
            export_log.record("bundle", folder)
            missing = reproduction.missing_inputs(manifest)
            if missing:
                report(self, f"Exported the bundle to {folder}, without {len(missing)} file(s) the scenario refers "
                             f"to and that could not be found: {', '.join(missing[:3])}", kind="warning")
            else:
                report(self, f"Exported a reproduction bundle to {folder}", kind="success")

        self._start_export(lambda step: reproduction.export_bundle(folder, scenario, result, base_dir, epoch_utc,
                                                                   progress=step), done,
                           lambda message: report(self, f"Could not export the bundle to {folder}: {message}"),
                           str(folder))

    def _on_export_all(self, fmt: str) -> None:
        folder = QFileDialog.getExistingDirectory(self, f"Export the shown plots ({fmt.upper()}) and their data")
        if folder:
            self.export_all(Path(folder), fmt)

    def export_all(self, folder: Path, fmt: str = "png") -> None:
        """Every shown plot as ``fmt`` (png or svg) into ``folder``, numbered
        in grid order, with each plot's series as CSV and the run's
        provenance (U-29). Rendering is asynchronous: the files are written
        when the page answers (see :meth:`_on_save_plot_png`)."""
        if not self.figures or self._png_poll_state is not None:
            return
        self._start_render(f"""Promise.all(Array.prototype.map.call(document.getElementById('grid').children,
                function(gd) {{ return Plotly.toImage(gd, {{format: {fmt!r}, scale: 2}}); }}
            )).then(function(urls) {{ window.{_PNG_RESULT_JS_VAR} = JSON.stringify(urls); }})""",
                           str(folder), fmt, self._on_all_rendered)

    def _plot_file_stem(self, index: int) -> str:
        name = self._shown[index] if index < len(self._shown) else "plot"
        return f"{index + 1:02d}_{'access_timeline' if name == ACCESS_TIMELINE else name}"

    def _on_all_rendered(self, data: object, folder: str, fmt: str) -> None:
        from .feedback import show_toast

        if isinstance(data, str) and data.startswith(_SAVE_PNG_ERROR_PREFIX):
            show_toast(self.window(), f"Export failed: {data[len(_SAVE_PNG_ERROR_PREFIX):]}", kind="error")
            return
        urls = json.loads(data) if isinstance(data, str) else None
        if not isinstance(urls, list) or len(urls) != len(self.figures):
            show_toast(self.window(), "Export failed: the plots could not be rendered", kind="error")
            return
        if self._export_worker is not None:
            return
        # What the files hold, taken now: the worker writes them while the
        # page may change (the decoding and writing are what took the time).
        stems = [self._plot_file_stem(index) for index in range(len(urls))]
        result = self._result
        series = [(name, result.series[name]) for name in self._shown
                  if result is not None and name in result.series]
        provenance = result.provenance if result is not None else None
        record = result.provenance_record() if result is not None else {}
        decode = self._decode_image

        def job(step) -> tuple[int, int]:
            out_dir = Path(folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            total = len(urls) + len(series) + (provenance is not None)
            for index, url in enumerate(urls):
                step(index, total)
                content = decode(url, fmt, provenance)
                path = output_path(out_dir, f"{stems[index]}.{fmt}")
                if isinstance(content, str):
                    path.write_text(content, encoding="utf-8")
                else:
                    path.write_bytes(content)
            for index, (name, one) in enumerate(series):
                step(len(urls) + index, total)
                one.to_csv(output_path(out_dir, f"{name}.csv"))
            if provenance is not None:  # last: a test waits for it
                step(total - 1, total)
                (out_dir / "provenance.json").write_text(json.dumps(record, indent=2))
            step(total, total)
            return len(urls), len(series)

        def done(counts) -> None:
            export_log.record("plots_all", folder)
            show_toast(self.window(), f"Exported {counts[0]} plot(s) as {fmt.upper()} and {counts[1]} CSV file(s) "
                                      f"to {folder}")

        self._start_export(job, done, lambda message: show_toast(self.window(), f"Export failed: {message}",
                                                                 kind="error"), folder)

    _CURRENT = object()  # _decode_image: the shown result's provenance

    def _decode_image(self, data_url: object, fmt: str, provenance=_CURRENT):
        """A rendered plot's file content: PNG bytes or SVG text, with the
        run's provenance embedded (``provenance``: the shown result's, or one
        taken when an export started). Raises ValueError when it is not one."""
        if provenance is self._CURRENT:
            provenance = self._result.provenance if self._result is not None else None
        if fmt == "svg":
            prefix = "data:image/svg+xml,"
            if not isinstance(data_url, str) or not data_url.startswith(prefix):
                raise ValueError("Could not render the plot to an SVG image.")
            svg_text = urllib.parse.unquote(data_url[len(prefix):])
            if provenance is not None:  # provenance on every output (UX/UI guidelines)
                svg_text = output_provenance.svg_with_provenance(svg_text, provenance.summary_lines(),
                                                                 provenance.to_dict())
            return svg_text
        prefix = "data:image/png;base64,"
        if not isinstance(data_url, str) or not data_url.startswith(prefix):
            raise ValueError("Could not render the plot to a PNG image.")
        png_bytes = base64.b64decode(data_url[len(prefix):])
        if provenance is not None:  # provenance on every output (UX/UI guidelines)
            png_bytes = output_provenance.png_with_provenance(png_bytes, provenance.to_dict())
        return png_bytes

    def _on_save_plot_svg(self) -> None:
        """Thin wrapper around :meth:`_on_save_plot_png` -- see that
        method's own docstring for the whole dialog/kickoff/poll
        mechanism, which is format-agnostic and shared as-is. Kept separate
        so ``save_svg_button``'s handler has the same zero-argument shape
        every other button's does, and a test can call it by name.
        """
        self._on_save_plot_png(fmt="svg")

    def _on_save_plot_png(self, fmt: str = "png") -> None:
        """Saves the SELECTED plot (only -- see :meth:`export_all` for
        every shown plot, ``_on_export`` for every series) to a
        user-chosen location via a native "Save As" dialog, as either a PNG
        (``fmt="png"``, the default) or an SVG (``fmt="svg"``, via
        :meth:`_on_save_plot_svg`).

        Plotly's own modebar has a download-as-PNG icon, but inside an
        embedded ``QWebEngineView`` it triggers Chromium's OWN download
        machinery, which this app never wires up -- confirmed directly that
        clicking it does nothing observable here. This button instead
        renders the chart CLIENT-SIDE with the plotly.js already on the
        page (``Plotly.toImage()``), rather than pulling in a server-side
        renderer (``kaleido``) this project doesn't otherwise depend on.
        ``scale: 2`` asks for a sharper-than-screen render at the chart's
        current on-screen size.

        ``Plotly.toImage()`` is asynchronous (a ``Promise``), and
        ``QWebEnginePage.runJavaScript()`` does NOT await a returned
        ``Promise`` on this PySide6 version (confirmed directly: it silently
        returned an empty string), so the render is started into a
        page-global variable that :meth:`_poll_plot_png` polls --
        ``_SAVE_PNG_PENDING_SENTINEL`` distinguishes "still rendering" from
        a real result, since a bare JS ``null``/``undefined`` also bridges
        back as an empty string.
        """
        if self.figure is None:
            return
        if self._png_poll_state is not None:
            # Re-entrancy guard: a second save (either button, or Export
            # all) while a poll runs would overwrite self._png_poll_state
            # AND the page variable both polls share, orphaning the first
            # timer -- it would fire forever, writing the file and saying
            # "saved" again every poll interval.
            return
        default_name = f"{'access_timeline' if self._shown[self._focused] == ACCESS_TIMELINE else self.current_series_name()}.{fmt}"
        file_filter = "SVG images (*.svg)" if fmt == "svg" else "PNG images (*.png)"
        path, _ = QFileDialog.getSaveFileName(self, f"Save plot as {fmt.upper()}", default_name, file_filter)
        if not path:
            return
        if not path.lower().endswith(f".{fmt}"):
            path += f".{fmt}"
        plot_id = plot_page.div_id(self._focused)
        self._start_render(f"""Plotly.toImage(document.getElementById({plot_id!r}), {{format: {fmt!r}, scale: 2}})
                .then(function(url) {{ window.{_PNG_RESULT_JS_VAR} = url; }})""",
                           path, fmt, self._on_plot_png_rendered)

    def _start_render(self, render_js: str, path: str, fmt: str, on_done) -> None:
        """Run ``render_js`` (which stores its answer in the page variable)
        once Plotly and the plots are loaded, then poll for the answer and
        hand it to ``on_done(value, path, fmt)``."""
        # Guards against a second click racing this one's own poll -- see
        # the re-entrancy guard in _on_save_plot_png.
        for button in (self.save_png_button, self.save_svg_button, self.export_all_button):
            button.setEnabled(False)
        # tryRender's retry loop guards a real (if narrow) race: the buttons
        # are enabled as soon as a page load starts, but the page loads
        # asynchronously -- an automated click (a test) could hit "Plotly is
        # not defined" (confirmed directly: this project's own test once did).
        kickoff_script = f"""
        window.{_PNG_RESULT_JS_VAR} = {_SAVE_PNG_PENDING_SENTINEL!r};
        (function tryRender(attemptsLeft) {{
            var el = document.getElementById({_PLOT_DIV_ID!r});
            if (typeof Plotly === 'undefined' || !el || !el.layout) {{
                if (attemptsLeft > 0) {{
                    setTimeout(function() {{ tryRender(attemptsLeft - 1); }}, 50);
                }} else {{
                    window.{_PNG_RESULT_JS_VAR} = '{_SAVE_PNG_ERROR_PREFIX}the plot had not finished loading';
                }}
                return;
            }}
            {render_js}
                .catch(function(err) {{
                    window.{_PNG_RESULT_JS_VAR} =
                        '{_SAVE_PNG_ERROR_PREFIX}' + (err && err.message ? err.message : err);
                }});
        }})(40);
        """
        self.web_view.page().runJavaScript(kickoff_script)

        poll_timer = QTimer(self)
        self._png_poll_state = {"path": path, "fmt": fmt, "timer": poll_timer, "attempts": 0,
                                "kickoff": kickoff_script, "on_done": on_done}
        poll_timer.timeout.connect(self._poll_plot_png)
        poll_timer.start(_SAVE_PNG_POLL_INTERVAL_MS)

    def _finish_poll(self, state: dict) -> None:
        state["timer"].stop()
        self._png_poll_state = None  # see _on_save_plot_png's own re-entrancy-guard comment
        for button in (self.save_png_button, self.save_svg_button, self.export_all_button):
            button.setEnabled(bool(self.figures))
        self.export_all_button.setEnabled(bool(self.figures) and self._export_worker is None)

    def _poll_plot_png(self) -> None:
        # runJavaScript() answers asynchronously, while the timer keeps
        # firing (SRelD K-08): a tick can arrive after the poll finished
        # (state None: the traceback in the CI logs), and on a slow machine
        # several queries could be in flight, each answer finishing the save
        # again (a second file write and "saved" dialog). One query at a
        # time, and answers to a finished poll are ignored.
        state = self._png_poll_state
        if state is None:
            return
        if state.get("in_flight"):
            # An answer that never comes must not stall the save: after a
            # second without one, ask again (a late answer is then ignored).
            state["waited_ticks"] = state.get("waited_ticks", 0) + 1
            if state["waited_ticks"] < _SAVE_PNG_MAX_WAIT_TICKS:
                return
        state["waited_ticks"] = 0
        state["attempts"] += 1
        state["in_flight"] = True

        def on_poll_result(value: object) -> None:
            state["in_flight"] = False
            if self._png_poll_state is not state:
                return  # this poll already finished (or was replaced)
            page_replaced = value in ("", None)
            if page_replaced and state["attempts"] < _SAVE_PNG_MAX_POLL_ATTEMPTS:
                # The result variable is gone: the page was reloaded since the
                # render started (a redraw loads a new page), and the pending
                # render went with it. Start it again on the new page; tryRender
                # waits for that page's Plotly. Seen in CI, where it was
                # reported as "Could not render the plot".
                self.web_view.page().runJavaScript(state["kickoff"])
                return
            if value == _SAVE_PNG_PENDING_SENTINEL or page_replaced:
                if state["attempts"] >= _SAVE_PNG_MAX_POLL_ATTEMPTS:
                    self._finish_poll(state)
                    report(self, f"Could not save the plot to {state['path']}: it did not render in time")
                return
            self._finish_poll(state)
            state.get("on_done", self._on_plot_png_rendered)(value, state["path"], state["fmt"])

        self.web_view.page().runJavaScript(f"window.{_PNG_RESULT_JS_VAR}", on_poll_result)

    def _on_plot_png_rendered(self, data_url: object, path: str, fmt: str = "png") -> None:
        """Writes the rendered plot (``Plotly.toImage()``'s data URL: base64
        for PNG, a percent-encoded TEXT data URL for SVG -- see
        :meth:`_decode_image`) to ``path``, with the run's provenance."""
        if isinstance(data_url, str) and data_url.startswith(_SAVE_PNG_ERROR_PREFIX):
            report(self, f"Could not save the plot to {path}: {data_url[len(_SAVE_PNG_ERROR_PREFIX):]}")
            return
        try:
            content = self._decode_image(data_url, fmt)
            if isinstance(content, str):
                Path(path).write_text(content, encoding="utf-8")
            else:
                Path(path).write_bytes(content)
        except (OSError, ValueError) as exc:
            report(self, f"Could not save the plot to {path}: {exc}")
            return
        export_log.record(f"plot_{fmt}", path)
        report(self, f"Saved the plot to {path}", kind="success")
