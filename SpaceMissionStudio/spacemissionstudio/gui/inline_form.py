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

"""A list's selected item, edited in a form under the list (UI overhaul
M4b): the device and dispersion lists, whose items were edited in modal
dialogs.

Select a row and its form shows; an edit is read from the form
:data:`SETTLE_MS` after the last one, as a spacecraft's page is, and
written into the list once it validates. A value that does not validate
is not applied: the banner above the form says why (a name is also marked
at its field as it is typed).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QDialog, QListWidget, QVBoxLayout, QWidget

from .feedback import ProblemBanner
from .page_tree import embed_dialog, watch_edits

SETTLE_MS = 300  # [ms] after the last edit, as a spacecraft's or ground station's page
_WATCHED = "smsInlineWatched"  # a field whose edits this form already follows (page_tree.watch_edits)


class InlineForm(QWidget):
    """The form of ``list_widget``'s current row: ``build(row)`` makes it
    (an editor dialog, shown embedded) and ``read(form, row)`` reads the
    item from it, raising ``ValueError`` for a value that does not
    validate. ``applied`` carries the row and the item read."""

    applied = Signal(int, object)

    def __init__(self, list_widget: QListWidget, build: Callable[[int], QDialog],
                 read: Callable[[QDialog, int], object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._list, self._build, self._read = list_widget, build, read
        self.form: QDialog | None = None
        self.row = -1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.banner = ProblemBanner()
        layout.addWidget(self.banner)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SETTLE_MS)
        self._timer.timeout.connect(self._apply)
        list_widget.currentRowChanged.connect(self._on_current_row)
        self.hide()

    def _on_current_row(self, row: int) -> None:
        self.flush()  # the edit made in the row left counts first
        if row != self.row or self.form is None:
            self.show_row(row)

    def show_row(self, row: int) -> None:
        """Show the form of ``row`` (none for -1), built again from its item."""
        self._timer.stop()
        if self.form is not None:
            self.form.setParent(None)
            self.form.deleteLater()
            self.form = None
        self.banner.hide()
        self.row = row
        if row < 0:
            self.hide()
            return
        form = self._build(row)
        embed_dialog(form)
        watch_edits(form, self._poke, mark=_WATCHED)
        self.layout().addWidget(form)
        self.form = form
        self.show()

    def _poke(self, *_args) -> None:
        self._timer.start()
        # An edit can add fields (a device's new kind has its own): follow
        # theirs too, once this edit has built them.
        QTimer.singleShot(0, self._watch_new_fields)

    def _watch_new_fields(self) -> None:
        if self.form is not None:
            watch_edits(self.form, self._poke, mark=_WATCHED)

    def discard(self) -> None:
        """Drop the form and an edit it holds (its row is going away)."""
        self.show_row(-1)

    def flush(self) -> None:
        """Apply a waiting edit now."""
        if self._timer.isActive():
            self._timer.stop()
            self._apply()

    @property
    def pending(self) -> bool:
        """An edit is waiting to be read."""
        return self._timer.isActive()

    def _apply(self) -> None:
        if self.form is None:
            return
        try:
            item = self._read(self.form, self.row)
        except ValueError as exc:
            self.banner.show_problem(f"Not applied: {exc}")
            return
        self.banner.hide()
        self.applied.emit(self.row, item)
