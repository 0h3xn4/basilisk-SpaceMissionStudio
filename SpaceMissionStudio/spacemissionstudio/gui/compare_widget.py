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
"""The Compare tab (docs/ux-audit.md U-33): tick two or more runs, of this
session or saved from earlier ones (decision 5), and compare them.

The oldest ticked run is the base; every other is compared with it
(old -> new):

- **Summary**: each run's headline figures (:mod:`engine.run_summary`)
  with a delta column per run;
- **Inputs**: every input that differs from the base
  (:mod:`engine.scenario_diff`);
- **Events**: each kind of event counted, with its total time, and the
  difference;
- **Plots**: one series of every ticked run, overlaid.

After a run its run and the one before it are ticked. With exactly the
shown run and one other ticked, Results draws that other dashed (and
choosing a run under Results' "Compare with" ticks the pair here).
Delete removes a saved run from disk (not the run shown).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import plotly.graph_objects as go
from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from ..engine import events as event_model
from ..engine import run_summary, scenario_diff
from ..plot_categories import categorize as _categorize
from ..plot_categories import legacy_display as _legacy_display
from . import plot_page
from .theme import SERIES_COLORS, TOKENS, on_change, set_role
from .theme import plotly_template as pt
from .widgets import ComboBox

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_S_PER_H = 3600.0  # [s/h]


def _empty_state(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("emptyState")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    set_role(label, role="empty")
    return label


def _table(columns: int = 0) -> QTableWidget:
    table = QTableWidget(0, columns)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    return table


def _home_relative(path: Path) -> str:
    """``~/.spacemissionstudio/runs`` rather than the full home path."""
    try:
        return str(Path("~") / path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _signed(value: float, decimals: int) -> str:
    text = f"{value:+.{decimals}f}"
    return "0" if float(text) == 0.0 else text


def _short(record) -> str:
    return f"Run {record.number}"


class CompareWidget(QWidget):
    """The Compare tab."""

    compare_chosen = Signal(object)  # the run Results draws dashed, or None
    delete_requested = Signal(object)  # a gui.run_history.RunRecord

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.empty_label = _empty_state("Run the scenario twice (or two versions of it) to compare the runs here. "
                                        "Runs are saved, so the runs of earlier sessions show here too.")
        layout.addWidget(self.empty_label)
        self.content = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.content, 1)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(QLabel("Runs (tick two or more):"))
        self.run_list = QListWidget()
        self.run_list.setAccessibleName("Runs to compare")
        self.run_list.setWordWrap(True)
        self.run_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.run_list.itemChanged.connect(self._on_item_changed)
        self.run_list.currentItemChanged.connect(self._update_delete_button)
        side_layout.addWidget(self.run_list, 1)
        buttons = QHBoxLayout()
        self.delete_button = QPushButton("Delete run...")
        self.delete_button.setToolTip("Remove the selected run from disk.")
        self.delete_button.clicked.connect(self._on_delete)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        side_layout.addLayout(buttons)
        self.store_label = QLabel("")
        self.store_label.setWordWrap(True)
        set_role(self.store_label, tone="secondary")
        side_layout.addWidget(self.store_label)
        self.content.addWidget(side)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)
        self.views = QTabWidget()
        self.summary_table = _table()
        self.summary_table.setAccessibleName("Summary")
        self.inputs_table = _table()
        self.inputs_table.setAccessibleName("Inputs that differ")
        self.events_table = _table()
        self.events_table.setAccessibleName("Events")
        self.views.addTab(self.summary_table, "Summary")
        self.views.addTab(self.inputs_table, "Inputs")
        self.views.addTab(self.events_table, "Events")
        plots = QWidget()
        plots_layout = QVBoxLayout(plots)
        plots_layout.setContentsMargins(0, 0, 0, 0)
        picks = QHBoxLayout()
        picks.addWidget(QLabel("Series:"))
        self.series_combo = ComboBox()
        self.series_combo.setAccessibleName("Series to overlay")
        self.series_combo.currentIndexChanged.connect(self._on_series_changed)
        picks.addWidget(self.series_combo, 3)
        self.column_combo = ComboBox()
        self.column_combo.setAccessibleName("Column")
        self.column_combo.currentIndexChanged.connect(self._draw_plot)
        picks.addWidget(self.column_combo, 1)
        plots_layout.addLayout(picks)
        self.web_view = QWebEngineView()
        plots_layout.addWidget(self.web_view, 1)
        on_change(self._on_theme_changed)
        self.views.addTab(plots, "Plots")
        main_layout.addWidget(self.views, 1)
        self.content.addWidget(main)
        self.content.setStretchFactor(0, 0)
        self.content.setStretchFactor(1, 1)
        self.content.setSizes([300, 900])  # [px]

        self._page_dir = tempfile.TemporaryDirectory(prefix="sms-compare-")
        self._runs: list = []
        self._current = None
        self._checked: set = set()
        self._seen_current: Optional[int] = None
        self._updating = False
        self._summaries: Dict[int, dict] = {}
        self._event_tables: Dict[int, dict] = {}
        self.figure: Optional[go.Figure] = None
        self.set_runs([], None)

    # -- the run list -------------------------------------------------------

    def set_runs(self, runs: list, current, chosen_number=None, store_root: Optional[Path] = None) -> None:
        """``runs``: ``gui.run_history.RunRecord`` objects, oldest first;
        ``current``: the one the run views show; ``chosen_number``: the run
        Results compares with it, if any."""
        self._runs, self._current = list(runs), current
        numbers = {r.number for r in self._runs}
        self._summaries = {n: s for n, s in self._summaries.items() if n in numbers}
        self._event_tables = {n: t for n, t in self._event_tables.items() if n in numbers}
        if current is not None and current.number != self._seen_current:
            # a new run: compare it with the run before it (or the one Results compares with)
            self._seen_current = current.number
            earlier = [r.number for r in self._runs if r.number < current.number]
            other = chosen_number if chosen_number in numbers else (earlier[-1] if earlier else None)
            self._checked = {current.number} | ({other} if other is not None else set())
        self._checked &= numbers
        self._updating = True
        self.run_list.clear()
        for record in reversed(self._runs):
            shown = current is not None and record.number == current.number
            # two lines, so a narrow column holds them: "Run 2, 09:09 (shown)" over the scenario's name
            text = (f"{record.name}{', cancelled' if record.cancelled else ''}{' (shown)' if shown else ''}\n"
                    f"{record.scenario.get('name', '')}")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, record.number)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if record.number in self._checked else Qt.CheckState.Unchecked)
            saved = getattr(record, "saved", None)
            item.setToolTip(record.label + "\n" + (f"Saved as {saved.run_id}" if saved is not None
                                                     else "Not saved: kept for this session only"))
            self.run_list.addItem(item)
        self._updating = False
        self.empty_label.setVisible(len(self._runs) < 2)
        self.content.setVisible(len(self._runs) >= 2)
        if store_root is not None:
            self.store_label.setText(f"Saved in {_home_relative(Path(store_root))}")
        self._update_delete_button()
        self._refresh()

    def follow_results_choice(self, number) -> None:
        """Results' "Compare with" changed: tick the shown run and ``number``
        (or, for "(no comparison)", untick the run it was paired with)."""
        if self._current is None:
            return
        if number is not None:
            self.set_checked([self._current.number, number])
        elif self.chosen_number() is not None:
            self.set_checked([self._current.number])

    def chosen_number(self):
        """The run Results draws dashed: with exactly the shown run and one
        other ticked, that other; otherwise None."""
        if self._current is None or len(self._checked) != 2 or self._current.number not in self._checked:
            return None
        return next(n for n in self._checked if n != self._current.number)

    def checked_runs(self) -> list:
        """The ticked runs, oldest (the base) first."""
        return [r for r in self._runs if r.number in self._checked]

    def set_checked(self, numbers) -> None:
        """Tick exactly ``numbers`` (for the keyboard-free paths and tests)."""
        self._updating = True
        for index in range(self.run_list.count()):
            item = self.run_list.item(index)
            item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in set(numbers)
                               else Qt.CheckState.Unchecked)
        self._updating = False
        self._on_item_changed()

    def _on_item_changed(self, *_args) -> None:
        if self._updating:
            return
        self._checked = {self.run_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.run_list.count())
                         if self.run_list.item(i).checkState() == Qt.CheckState.Checked}
        self._refresh()
        self.compare_chosen.emit(self.chosen_number())

    def _selected_record(self):
        item = self.run_list.currentItem()
        number = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return next((r for r in self._runs if r.number == number), None)

    def _update_delete_button(self, *_args) -> None:
        record = self._selected_record()
        shown = record is not None and self._current is not None and record.number == self._current.number
        self.delete_button.setEnabled(record is not None and not shown)
        self.delete_button.setToolTip("The run shown cannot be deleted." if shown
                                      else "Remove the selected run from disk.")

    def _on_delete(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        answer = QMessageBox.question(
            self, "Delete run", f"Delete {record.name}? Its saved series are removed from disk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(record)

    # -- the views ----------------------------------------------------------

    def _summary(self, record) -> dict:
        if record.number not in self._summaries:
            result = record.result
            found = event_model.extract_events(result)
            self._summaries[record.number] = run_summary.by_key(run_summary.summarize(result, found))
            self._event_tables[record.number] = run_summary.event_table(found)
        return self._summaries[record.number]

    def _on_theme_changed(self, _mode: str) -> None:
        """Rebuild the tables' muted cells and the plot in the new theme,
        after the switch itself has returned."""
        QTimer.singleShot(0, self, self._refresh)

    def _refresh(self) -> None:
        runs = self.checked_runs()
        for table in (self.summary_table, self.inputs_table, self.events_table):
            table.setRowCount(0)
            table.setColumnCount(0)
        if len(runs) < 2:
            self.status_label.setText("Tick two or more runs to compare them; the oldest ticked is the base.")
            self._fill_series([])
            return
        unreadable = [r for r in runs if r.result is None]
        runs = [r for r in runs if r.result is not None]
        base, others = runs[0], runs[1:]
        self.status_label.setText(
            f"Comparing with {base.name} (the oldest ticked): " + ", ".join(r.name for r in others) + "."
            + ("".join(f" {r.name} could not be read back (see the Log)." for r in unreadable)))
        if not others:
            self._fill_series([])
            return
        self._fill_summary(base, others)
        self._fill_inputs(base, others)
        self._fill_events(base, others)
        self._fill_series(runs)

    def _fill_summary(self, base, others) -> None:
        figures = [self._summary(r) for r in [base] + others]
        keys = list(dict.fromkeys(key for run in figures for key in run))
        headings = ["Figure", "Unit", f"{_short(base)} (base)"]
        for other in others:
            headings += [_short(other), f"Δ {_short(other)}"]
        table = self.summary_table
        table.setColumnCount(len(headings))
        table.setHorizontalHeaderLabels(headings)
        table.setRowCount(len(keys))
        for row, key in enumerate(keys):
            sample = next(run[key] for run in figures if key in run)
            table.setItem(row, 0, QTableWidgetItem(sample.label))
            table.setItem(row, 1, QTableWidgetItem(sample.unit))
            base_figure = figures[0].get(key)
            cells = [base_figure.text() if base_figure else "-"]
            for run in figures[1:]:
                figure = run.get(key)
                cells.append(figure.text() if figure else "-")
                cells.append(_signed(figure.value - base_figure.value, figure.decimals)
                             if figure and base_figure else "-")
            for column, text in enumerate(cells, start=2):
                item = QTableWidgetItem(text)
                item.setTextAlignment(_RIGHT)
                table.setItem(row, column, item)
        table.resizeColumnsToContents()

    def _fill_inputs(self, base, others) -> None:
        diffs = [{path: (mine, theirs) for path, mine, theirs in scenario_diff.diff(base.scenario, other.scenario)}
                 for other in others]
        paths = list(dict.fromkeys(path for diff in diffs for path in diff))
        table = self.inputs_table
        headings = ["Input", f"{_short(base)} (base)"] + [_short(other) for other in others]
        table.setColumnCount(len(headings))
        table.setHorizontalHeaderLabels(headings)
        table.setRowCount(len(paths))
        muted = QColor(TOKENS["text.secondary"])
        for row, path in enumerate(paths):
            base_value = next(diff[path][0] for diff in diffs if path in diff)
            table.setItem(row, 0, QTableWidgetItem(path))
            table.setItem(row, 1, QTableWidgetItem(scenario_diff.short(base_value)))
            table.item(row, 1).setToolTip(str(base_value))
            for column, diff in enumerate(diffs, start=2):
                if path in diff:
                    item = QTableWidgetItem(scenario_diff.short(diff[path][1]))
                    item.setToolTip(str(diff[path][1]))
                else:
                    item = QTableWidgetItem("(same)")
                    item.setForeground(muted)
                table.setItem(row, column, item)
        table.resizeColumnsToContents()
        if not paths:
            table.setColumnCount(1)
            table.setHorizontalHeaderLabels(["Input"])
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem("The inputs are the same."))

    def _fill_events(self, base, others) -> None:
        for record in [base] + others:
            self._summary(record)  # fills the event tables too
        tables = [self._event_tables[r.number] for r in [base] + others]
        labels = list(dict.fromkeys(label for run in tables for label in run))
        headings = ["Event", f"{_short(base)} (base)"]
        for other in others:
            headings += [_short(other), f"Δ {_short(other)}"]
        table = self.events_table
        table.setColumnCount(len(headings))
        table.setHorizontalHeaderLabels(headings)
        table.setRowCount(len(labels))
        for row, label in enumerate(labels):
            table.setItem(row, 0, QTableWidgetItem(label))
            base_count, base_total = tables[0].get(label, (0, 0.0))
            cells = [f"{base_count} × {base_total:.1f} min"]
            for run in tables[1:]:
                count, total = run.get(label, (0, 0.0))
                cells.append(f"{count} × {total:.1f} min")
                cells.append(f"{count - base_count:+d} × {_signed(total - base_total, 1)} min")
            for column, text in enumerate(cells, start=1):
                item = QTableWidgetItem(text)
                item.setTextAlignment(_RIGHT)
                table.setItem(row, column, item)
        table.resizeColumnsToContents()

    # -- overlaid plots -----------------------------------------------------

    def _fill_series(self, runs: list) -> None:
        from .results_widget import _series_label

        current = self.series_combo.currentData()
        names: Dict[str, str] = {}
        for record in runs:
            for name, series in record.result.series.items():
                names.setdefault(name, _series_label(name, series))
        self.series_combo.blockSignals(True)
        self.series_combo.clear()
        for name in sorted(names, key=lambda n: names[n].lower()):
            self.series_combo.addItem(names[name], name)
            self.series_combo.setItemData(self.series_combo.count() - 1, name, Qt.ItemDataRole.ToolTipRole)
        index = self.series_combo.findData(current) if current is not None else -1
        self.series_combo.setCurrentIndex(index if index >= 0 else (0 if names else -1))
        self.series_combo.blockSignals(False)
        self._on_series_changed()

    def _on_series_changed(self, *_args) -> None:
        name = self.series_combo.currentData()
        series = next((r.result.series[name] for r in self.checked_runs()
                       if r.result is not None and name in r.result.series), None) if name else None
        current = self.column_combo.currentData()
        self.column_combo.blockSignals(True)
        self.column_combo.clear()
        if series is not None:
            display = _categorize(name, series) or _legacy_display(name, series)
            labels = display.columns or {}
            for index, column in enumerate(series.columns):
                self.column_combo.addItem(str(labels.get(column, column)), index)
            found = self.column_combo.findData(current) if current is not None else -1
            self.column_combo.setCurrentIndex(max(found, 0))
        self.column_combo.setVisible(self.column_combo.count() > 1)
        self.column_combo.blockSignals(False)
        self._draw_plot()

    def _draw_plot(self, *_args) -> None:
        from .results_widget import _display_indices, _page_style, _plotlyjs_path, _template_layout

        name, column = self.series_combo.currentData(), self.column_combo.currentData()
        runs = [r for r in self.checked_runs() if r.result is not None and name in r.result.series] if name else []
        if len(runs) < 2 or column is None:
            self.figure = None
            self.web_view.setHtml(f"<html><head><style>{pt.page_css(TOKENS)}</style></head><body>"
                                  "<div class='empty'>Tick two or more runs to overlay a series.</div></body></html>",
                                  QUrl())
            return
        sample = runs[0].result.series[name]
        display = _categorize(name, sample) or _legacy_display(name, sample)
        fig = go.Figure()
        for index, record in enumerate(runs):
            series = record.result.series[name]
            if column >= series.data.shape[1]:
                continue
            values = series.data[:, column] * display.factor
            keep = _display_indices(values)
            fig.add_trace(go.Scatter(
                x=np.asarray(series.time_s)[keep] / _S_PER_H, y=values[keep], mode="lines",
                name=record.name + (" (base)" if index == 0 else ""),
                # the base solid, the others dashed: where runs agree, both still show
                line=dict(color=SERIES_COLORS[index % len(SERIES_COLORS)], width=2,
                          dash="solid" if index == 0 else "dash")))
        y_title = f"{display.y_label} [{display.unit}]" if display.y_label else (f"[{display.unit}]" if display.unit
                                                                                  else None)
        axis = dict(pt.axis(TOKENS), exponentformat="none", separatethousands=True)
        fig.update_layout(
            **_template_layout(),
            title=pt.title(TOKENS, self.series_combo.currentText()),
            xaxis=dict(axis, title_text="Elapsed time [h]"), yaxis=dict(axis, title_text=y_title),
            showlegend=True, legend=dict(orientation="h", y=-0.18, font=dict(color=TOKENS["text.secondary"])),
            margin=dict(l=70, r=30, t=60, b=80))
        self.figure = fig
        html = plot_page.build_page([fig.to_json()], "1x1", 0, [True],
                                    QUrl.fromLocalFile(str(_plotlyjs_path())).toString(), _page_style())
        page = Path(self._page_dir.name) / "compare.html"
        if not page.parent.is_dir():
            return
        page.write_text(html, encoding="utf-8")
        self.web_view.load(QUrl.fromLocalFile(str(page)))
