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


"""Reports › Exports (UI overhaul M8, plan §5.3): every export the app
makes, in one table, with its format, where it is made, its default
destination, the provenance written with it and when this machine last
wrote one (:mod:`gui.export_log`). Enter or a double-click opens the view
that makes it; the exports themselves stay on their views' buttons.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import export_log
from .data_table import DataTable, Row
from .theme import SPACE, set_role


class Export(NamedTuple):
    key: str  # export_log's key
    name: str
    file_format: str
    made_in: str  # the view and its button
    destination: str  # the default destination
    provenance: str  # what is written with it, in short
    provenance_detail: str = ""  # the cell's tooltip


EXPORTS = (
    Export("plot_csv", "Plot data", "CSV, a file a series", "Results › Plots › Export CSV...", "Folder chosen",
           "provenance.json", "provenance.json in the folder"),
    Export("plot_png", "Plot image", "PNG", "Results › Plots › Save PNG...", "<series>.png", "In the file",
           "In the image, as a PNG text chunk"),
    Export("plot_svg", "Plot image", "SVG", "Results › Plots › Save SVG...", "<series>.svg", "In the file",
           "In the image, as SVG metadata"),
    Export("plots_all", "Every shown plot", "PNG or SVG, CSV", "Results › Plots › Export all...", "Folder chosen",
           "In each image; provenance.json", "In each image, and provenance.json in the folder"),
    Export("events_csv", "Events", "CSV", "Timeline › Export CSV...", "events.csv", "<file>.provenance.json",
           "<file>.provenance.json beside it"),
    Export("output_csv", "Mission output", "CSV", "Results › Output › Export CSV...", "File chosen",
           "<file>.provenance.json", "<file>.provenance.json beside it"),
    Export("monte_carlo_csv", "Monte Carlo runs", "CSV", "Results › Monte Carlo › Export table CSV...",
           "monte_carlo_runs.csv", "None", "None in the table; the batch folder keeps the batch's"),
    Export("budget_csv", "Budget", "CSV text", "Run › Budget › Copy as CSV", "Clipboard", "Its last lines",
           "Its last lines: the versions, the scenario's SHA-256 and the time"),
    Export("fsw_project", "Flight software", "C project (CMake)", "Reports › Flight Software › Export...",
           "Folder chosen", "manifest.json", "manifest.json in the folder"),
    Export("sil_report", "SIL report", "JSON, residuals CSV", "Reports › Flight Software › Save report...",
           "File chosen", "In the report", "In the report: the binary's and the configurations' SHA-256"),
    Export("vizard_file", "Vizard playback", "Vizard .bin", "Run › Run › Vizard save file", "Set on Run › Run",
           "None", "None (Basilisk writes it during the run)"),
    Export("model_obj", "3D model", "OBJ and MTL", "Scenario › 3D Model... › Export .obj...", "<spacecraft>.obj",
           "None"),
)
_HEADERS = ("Export", "Last written\n[UTC]", "Format", "Made in", "Default destination", "Provenance")
_LAST = 1  # the column of the time last written


class ExportsPage(QWidget):
    """The table of exports; ``open_requested`` carries the key of the one
    whose view should open."""

    open_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        layout.setSpacing(SPACE["sm"])
        layout.addWidget(set_role(QLabel("Every file the app writes. The files are the same as in 1.1.0, byte for "
                                         "byte. Enter or a double-click opens the view that makes one."),
                                  tone="secondary"))
        self.table = DataTable("No exports.")
        self.table.view.activated.connect(self._on_activated)
        layout.addWidget(self.table, 1)
        export_log.signals.changed.connect(self._on_logged)
        self._stale = False
        self.refresh()

    def refresh(self) -> None:
        """The table again, with the times of the export log."""
        rows = []
        for export in EXPORTS:
            last = export_log.last(export.key)
            when, path = last if last is not None else ("never", "")
            tooltips = {5: export.provenance_detail} if export.provenance_detail else {}
            if path:
                tooltips[_LAST] = path
            rows.append(Row((export.name, when, export.file_format, export.made_in, export.destination,
                             export.provenance), tooltips=tooltips))
        self.table.set_table(_HEADERS, rows, stretch=-1)  # every column its content's width
        self._stale = False

    def last_written(self, key: str) -> str:
        """The "Last written" cell of export ``key``."""
        return self.table.cell([export.key for export in EXPORTS].index(key), _LAST)

    def _on_logged(self, _key: str) -> None:
        if self.isVisible():
            self.refresh()
        else:
            self._stale = True  # refreshed when shown

    def showEvent(self, event) -> None:
        if self._stale:
            self.refresh()
        super().showEvent(event)

    def _on_activated(self, index) -> None:
        row = self.table.proxy.mapToSource(index).row()
        self.open_requested.emit(EXPORTS[row].key)
