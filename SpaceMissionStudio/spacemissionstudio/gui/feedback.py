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

"""Two small, reusable UX primitives, built once here and reused across
gui/ rather than re-invented per widget -- real user feedback ("make the
GUI more 'reactive'... the user always knows and understands what they
did. visual cues would help... currently, everything looks very raw and
unfinished"), and a follow-up survey of this app's own existing widgets
found the same two gaps repeating across most of them (add/remove
actions with no positive feedback beyond a list silently changing;
invalid input only ever caught by a blocking dialog at Save/Run time,
never at the specific field, at the moment it's typed):

* :func:`show_toast` -- a small, non-blocking, auto-dismissing
  notification, for "did my action actually do something" feedback on
  actions where a blocking ``QMessageBox`` would be overkill (Save, Add
  spacecraft, Remove sensor, ...) and a status-bar message alone is too
  easy to miss. That's not a guess: ``MainWindow.on_launch_vizard``'s own
  docstring already documents exactly this problem for ONE case (a
  status-bar message "easy to miss/get overwritten by the 'Running...'
  message that follows moments later") and had to be promoted to a
  one-time blocking dialog to be noticed at all -- a toast is the
  general-purpose fix that case shouldn't have needed a bespoke one-off
  dialog for.
* :func:`report` -- a routine outcome (a file written, a file that could
  not be read, a launch that failed) said without a message box
  (docs/ux-audit.md U-39): a toast, the window's status bar, and for a
  warning or an error a line in the Log. Message boxes are kept for
  confirming what cannot be undone.
* :func:`show_dialog_error` -- a dialog's own error line, above its
  buttons, for input the dialog refuses on OK (U-39), instead of a box on
  top of the dialog.
* :func:`mark_invalid`/:func:`clear_invalid` -- inline, per-field
  validation feedback (a red border, via theme.py's own
  ``[state="error"]`` QSS rule, plus the reason as a tooltip), so a
  field the user is actively typing into can show it's wrong immediately
  rather than only at Save/Run time via a dialog that names the problem
  but not which of a dialog's many fields caused it.

Both are intentionally widget-library-free (no new PyPI dependency) --
plain ``QLabel``/dynamic-Qt-property mechanisms the Qt Style Sheets
system already documents, matching this project's own "no third-party
GUI-chrome dependency beyond PySide6 itself" precedent (see theme.py).
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QBoxLayout, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QScrollArea, QStackedWidget, QTabWidget, QWidget)
from shiboken6 import isValid

from .theme import PALETTE

# Carbon toast notifications (low contrast): the status background, a 3 px
# status-colour rule on the left, primary text. (background, rule) PALETTE
# keys per kind, looked up when a toast is shown.
_TOAST_KIND_COLORS = {
    "success": ("success_soft", "success"),
    "error": ("danger_soft", "danger"),
    "info": ("info_soft", "info"),  # support-info
    "warning": ("warning_soft", "warning_fill"),
}
_logger = logging.getLogger("spacemissionstudio.gui")
_REPORT_LOG_LEVELS = {"error": logging.ERROR, "warning": logging.WARNING, "info": logging.INFO,
                      "success": logging.INFO}
_REPORT_TOAST_MS = {"error": 6000, "warning": 6000, "info": 4500, "success": 3000}  # [ms]
_TOAST_MARGIN_PX = 16
_TOAST_GAP_PX = 8
_TOAST_STACK_ATTR = "_spacemissionstudio_active_toasts"


class _Toast(QLabel):
    """Not meant to be constructed directly -- see :func:`show_toast`."""

    def __init__(self, parent: QWidget, message: str, kind: str) -> None:
        # A long path has no space to wrap at: a zero-width space after each
        # separator lets it wrap inside the toast's width (shown only; the
        # message itself is unchanged).
        super().__init__(re.sub(r"([/\\])", "\\1\u200b", message), parent)
        bg, rule = (PALETTE[key] for key in _TOAST_KIND_COLORS.get(kind, _TOAST_KIND_COLORS["info"]))
        self.setStyleSheet(
            f"background-color: {bg}; color: {PALETTE['text']}; border: none; border-left: 3px solid {rule}; "
            f"border-radius: 0px; padding: 10px 16px; font-weight: 600;"
        )
        self.setWordWrap(True)
        self.setMaximumWidth(360)
        self.adjustSize()


def show_toast(window: QWidget, message: str, kind: str = "success", duration_ms: int = 2600) -> QLabel:
    """Shows ``message`` in a small notification anchored to the
    bottom-right corner of ``window`` (the app's top-level window, or any
    dialog), above its status bar, auto-dismissing after ``duration_ms``.
    ``kind`` is ``"success"`` (default), ``"error"``, ``"warning"`` or
    ``"info"`` -- picks the
    toast's color from theme.py's own palette so it reads as part of the
    same themed system, not a visually foreign popup.

    Multiple toasts shown in quick succession (e.g. several list rows
    added back-to-back) stack upward rather than overlapping -- ``window``
    carries its own small list of currently-visible toasts
    (a plain attribute, not a class member, so this works on ANY QWidget
    without every window/dialog that wants toasts needing to inherit from
    a shared base class). Returns the created ``QLabel`` -- mainly useful
    for tests; normal callers can ignore the return value.
    """
    stack: List[QLabel] = getattr(window, _TOAST_STACK_ATTR, None)
    if stack is None:
        stack = []
        setattr(window, _TOAST_STACK_ATTR, stack)

    toast = _Toast(window, message, kind)
    stack.append(toast)
    _reposition_toasts(window, stack)
    toast.show()
    toast.raise_()

    def _dismiss() -> None:
        # The QTimer below can fire AFTER `window` (and so `toast`, its
        # child) was already destroyed -- e.g. the app/dialog was closed
        # while a toast was still showing, a real sequence several
        # existing tests hit (close a window right after an action that
        # shows a toast). shiboken6.isValid() is the documented way to
        # check whether a QObject's underlying C++ object is still alive
        # before touching it; skipping silently here is correct -- there
        # is nothing left to dismiss.
        if not isValid(toast):
            return
        if toast in stack:
            stack.remove(toast)
        # hide(), not deleteLater(): a caller that kept the QLabel
        # show_toast() returned (tests do) must not end up holding a
        # dangling C++ pointer once the auto-dismiss timer fires -- Qt's
        # normal parent-child ownership (toast's parent is `window`)
        # already cleans it up for real once `window` itself is
        # destroyed, so there is nothing to leak by not deleting sooner.
        toast.hide()
        if isValid(window):
            _reposition_toasts(window, stack)

    QTimer.singleShot(duration_ms, _dismiss)
    return toast


def report(widget: Optional[QWidget], text: str, kind: str = "error") -> None:
    """Say ``text`` without a message box (U-39). The first line goes in a
    toast on ``widget``'s window (``kind`` "error", "warning", "info" or
    "success") and in its status bar; the whole text goes in the Log (an
    error or a warning at that level, the others as INFO), where it stays.
    With no widget, only the Log."""
    _logger.log(_REPORT_LOG_LEVELS.get(kind, logging.INFO), "%s", text)
    first = text.strip().splitlines()[0] if text.strip() else text
    if widget is None or not isValid(widget):
        return
    window = widget.window()
    shown = first + (" (more in the Log)" if "\n" in text.strip() and kind in ("error", "warning") else "")
    show_toast(window, shown, kind=kind, duration_ms=_REPORT_TOAST_MS.get(kind, 3000))
    if isinstance(window, QMainWindow):
        window.statusBar().showMessage(first)


_DIALOG_ERROR_NAME = "dialogError"


def show_dialog_error(dialog: QWidget, text: str) -> QLabel:
    """Show ``text`` in ``dialog``'s error line, made the first time just
    above its button box (or at the end of its layout), and keep the
    dialog open (U-39). Cleared by :func:`clear_dialog_error`."""
    label = dialog.findChild(QLabel, _DIALOG_ERROR_NAME)
    if label is None:
        label = QLabel(dialog)
        label.setObjectName(_DIALOG_ERROR_NAME)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {PALETTE['danger']};")
        layout = dialog.layout()
        if layout is not None:
            buttons = dialog.findChild(QDialogButtonBox)
            index = layout.indexOf(buttons) if buttons is not None else -1
            if isinstance(layout, QBoxLayout) and index >= 0:
                layout.insertWidget(index, label)
            elif isinstance(layout, QFormLayout):
                layout.addRow(label)
            else:
                layout.addWidget(label)
    label.setText(text)
    label.setToolTip(text)
    label.show()
    return label


def dialog_error_text(dialog: QWidget) -> str:
    """The text of ``dialog``'s error line, "" when it has none showing."""
    label = dialog.findChild(QLabel, _DIALOG_ERROR_NAME)
    return label.text() if label is not None and not label.isHidden() else ""


def clear_dialog_error(dialog: QWidget) -> None:
    label = dialog.findChild(QLabel, _DIALOG_ERROR_NAME)
    if label is not None:
        label.clear()
        label.hide()


def _reposition_toasts(window: QWidget, stack: List[QLabel]) -> None:
    y = window.height() - _TOAST_MARGIN_PX
    status_bar = window.statusBar() if isinstance(window, QMainWindow) else None
    if status_bar is not None and status_bar.isVisible():
        y -= status_bar.height()  # never over the status bar's run state and reference data
    for toast in reversed(stack):
        y -= toast.height()
        toast.move(window.width() - toast.width() - _TOAST_MARGIN_PX, y)
        y -= _TOAST_GAP_PX


_ERROR_STATE_PROPERTY = "state"
_ERROR_STATE_VALUE = "error"
_SAVED_TOOLTIP_PROPERTY = "_feedback_saved_tooltip"


def mark_invalid(widget: QWidget, message: str, warning: bool = False) -> None:
    """Flags ``widget`` (a ``QLineEdit``/``QDoubleSpinBox``/``QSpinBox``/
    ``QComboBox``) as holding an invalid value -- a red border (theme.py's
    ``[state="error"]`` QSS rule) plus ``message`` as its tooltip, so the
    user sees WHICH field is wrong and WHY without waiting for a blocking
    Save/Run dialog. Does not clear itself -- call :func:`clear_invalid`
    once the field holds an acceptable value again (typically wired to
    that widget's own ``textChanged``/``valueChanged`` signal).

    Stashes whatever tooltip the widget already had (if any, and if this
    isn't already a repeat ``mark_invalid`` call) in a dynamic property so
    :func:`clear_invalid` can restore it afterwards, instead of just
    blanking it -- every call site today happens to set no tooltip of its
    own first, so this is currently latent, but a future widget with a
    real, static tooltip (e.g. a units hint) would otherwise lose it
    permanently the first time validation ever flagged that field.
    """
    if not widget.property(_ERROR_STATE_PROPERTY):
        widget.setProperty(_SAVED_TOOLTIP_PROPERTY, widget.toolTip())
    # ``warning``: a value to look at, not one that blocks (the warning outline).
    widget.setProperty(_ERROR_STATE_PROPERTY, "warning" if warning else _ERROR_STATE_VALUE)
    widget.setToolTip(message)
    _repolish(widget)


def clear_invalid(widget: QWidget) -> None:
    """Undoes :func:`mark_invalid` -- a no-op if the widget wasn't
    marked, so this is always safe to call unconditionally (e.g. at the
    top of a field's change handler, before re-validating). Restores
    whatever tooltip the widget had before :func:`mark_invalid` was first
    called, rather than always blanking it.
    """
    if widget.property(_ERROR_STATE_PROPERTY):
        widget.setProperty(_ERROR_STATE_PROPERTY, "")
        widget.setToolTip(widget.property(_SAVED_TOOLTIP_PROPERTY) or "")
        widget.setProperty(_SAVED_TOOLTIP_PROPERTY, None)
        _repolish(widget)


# The attribute show_field_error keeps a field's message label in.
_FIELD_ERROR_ATTR = "_smsFieldErrorLabel"


def _error_label(widget: QWidget):
    label = getattr(widget, _FIELD_ERROR_ATTR, None)
    return label if label is not None and isValid(label) else None


def _find_in_forms(layout, widget: QWidget):
    """``(form, row)`` for ``widget`` in ``layout`` or the layouts nested in
    it, or None."""
    if isinstance(layout, QFormLayout):
        row, _role = layout.getWidgetPosition(widget)
        if row >= 0:
            return layout, row
    for index in range(layout.count() if layout is not None else 0):
        child = layout.itemAt(index).layout()
        found = _find_in_forms(child, widget) if child is not None else None
        if found is not None:
            return found
    return None


def _form_row(widget: QWidget):
    """``(form, row, field)``: the QFormLayout row holding ``widget`` (or
    the row widget it sits in, up to three parents up), or None."""
    field = widget
    for _level in range(4):
        parent = field.parentWidget()
        if parent is None:
            return None
        found = _find_in_forms(parent.layout(), field)
        if found is not None:
            return found[0], found[1], field
        field = parent
    return None


def row_label(widget: QWidget) -> str:
    """The label of the form row holding ``widget``, also in a layout
    nested in its form ("" when there is none)."""
    found = _form_row(widget)
    if found is None:
        return ""
    form, row, _field = found
    item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
    label = item.widget() if item is not None else None
    return label.text().rstrip(":").strip() if isinstance(label, QLabel) else ""


def show_field_error(widget: QWidget, message: str, warning: bool = False) -> None:
    """Marks ``widget`` (see :func:`mark_invalid`) and shows ``message``
    right under it (docs/ux-audit.md U-12): under its row in a form, or
    after it in its own box layout. Calling it again updates the message.
    ``warning`` marks a value to look at rather than an error."""
    mark_invalid(widget, message, warning)
    label = _error_label(widget)
    if label is not None:
        label.setText(message)
        label.setObjectName("fieldWarning" if warning else "fieldError")
        _repolish(label)
        return
    label = QLabel(message)
    label.setObjectName("fieldWarning" if warning else "fieldError")
    label.setWordWrap(True)
    placed = _form_row(widget)
    if placed is not None:
        form, row, _field = placed
        form.insertRow(row + 1, "", label)
    else:
        parent = widget.parentWidget()
        layout = parent.layout() if parent is not None else None
        if not isinstance(layout, QBoxLayout) or layout.indexOf(widget) < 0:
            label.deleteLater()  # nowhere to put it: the border and tooltip still say it
            return
        layout.insertWidget(layout.indexOf(widget) + 1, label)
    setattr(widget, _FIELD_ERROR_ATTR, label)


def clear_field_error(widget: QWidget) -> None:
    """Undoes :func:`show_field_error`; safe to call on any widget."""
    clear_invalid(widget)
    label = _error_label(widget)
    setattr(widget, _FIELD_ERROR_ATTR, None)
    if label is None:
        return
    placed = _form_row(label)
    if placed is not None:
        placed[0].removeRow(placed[1])  # deletes the label and its empty row label
    else:
        label.deleteLater()


def clear_on_edit(widget: QWidget) -> None:
    """Clears ``widget``'s :func:`show_field_error` the first time the user
    changes its value: in a dialog nothing revalidates until OK."""
    for name in ("valueChanged", "textChanged", "currentIndexChanged", "itemChanged"):
        signal = getattr(widget, name, None)
        if signal is None:
            continue

        def clear(*_args, _signal=signal):
            clear_field_error(widget)
            _signal.disconnect(clear)

        signal.connect(clear)
        return


def field_error_text(widget: QWidget) -> str:
    """The message :func:`show_field_error` shows under ``widget``, or ""."""
    label = _error_label(widget)
    return label.text() if label is not None else ""


def bring_into_view(widget: QWidget) -> None:
    """Selects every tab and stacked page ``widget`` sits in, scrolls it into
    view, and focuses it: where Problems sends the user (U-12)."""
    child = widget
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QStackedWidget) and parent.indexOf(child) >= 0:
            container = parent.parentWidget()
            if isinstance(container, QTabWidget):
                container.setCurrentWidget(child)
            else:
                parent.setCurrentWidget(child)
        if isinstance(parent, QScrollArea) and parent.widget() is not None:
            parent.ensureWidgetVisible(widget)
        child, parent = parent, parent.parentWidget()
    widget.setFocus()


class ProblemBanner(QFrame):
    """A line at the top of a dialog opened at a problem: what is wrong,
    while the field itself is marked. Hidden until :meth:`show_problem`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("problemBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)  # [px]
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.hide()

    def show_problem(self, message: str) -> None:
        self.label.setText(message)
        self.show()


def _repolish(widget: QWidget) -> None:
    """Qt caches a widget's QSS match against its dynamic properties --
    changing one (``state`` above) has no visible effect until the style
    is explicitly told to re-evaluate it (Qt docs, "Qt Style Sheets
    Reference" -> "Qt Style Sheets and Widget Style" -> "Dynamic
    Properties").
    """
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class StaleResultsBanner(QFrame):
    """A persistent notice above the run views when the results shown no
    longer match the scenario (UX/UI Standard, "State is always visible";
    docs/ux-audit.md U-20): it names what changed and offers **Re-run**.
    Hidden until :meth:`show_stale` is called; styled by theme.py's
    ``QFrame#staleResultsBanner`` rule."""

    rerun_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("staleResultsBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)  # [px]
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.rerun_button = QPushButton("Re-run")
        self.rerun_button.setToolTip("Run the scenario as it is now (Ctrl+R)")
        self.rerun_button.clicked.connect(self.rerun_requested)
        layout.addWidget(self.rerun_button)
        self.hide()

    def show_stale(self, scenario_valid: bool) -> None:
        if scenario_valid:
            self.label.setText("These results are from a previous version of this scenario. "
                               "Re-run to see the current one.")
        else:
            self.label.setText("These results are from a previous version of this scenario, "
                               "which now has a problem: fix it in the Scenario Editor, then re-run.")
        self.rerun_button.setEnabled(scenario_valid)
        self.show()
