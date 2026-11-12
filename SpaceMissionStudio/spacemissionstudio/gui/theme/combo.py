#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""Drop-down lists that are easy to read and to use, in every combo box.

Qt's own list for a styled combo box sat over the field, as tall as the
screen for a long list, scrolled with two small arrows, with 24 px rows
and no mark under the pointer. :func:`prepare`, called for every
:class:`QComboBox` as Qt polishes it (:class:`theme.style.AppStyle`,
which also answers ``SH_ComboBox_Popup`` with a list below the field),
changes it:

- its list draws its rows with :class:`QStyledItemDelegate`, so the style
  sheet's row rules apply (``QComboBox QAbstractItemView::item`` in
  ``qss.py``: control-height rows, padding, a hover and a selected mark);
- the list opens below the field (``combobox-popup: 0`` in ``qss.py``),
  :data:`MAX_VISIBLE` rows high with a scroll bar, and at least as wide as
  its longest entry;
- a list of :data:`FILTER_MIN` entries or more gets a "Type to filter"
  field at its top: typing narrows the list to the entries containing the
  text (case-blind), the arrows move in what is left, Enter picks.

Nothing about the combo box's values, signals or keyboard use without the
list changes, so no code that uses one needs to know.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QLineEdit, QListView, QStyledItemDelegate, QWidget,
)

MAX_VISIBLE = 12  # rows shown before the list scrolls
FILTER_MIN = 12  # entries from which the list has a filter field
_FILTER_NAME = "comboFilter"


def prepare(combo: QComboBox) -> None:
    """Give ``combo`` the readable list (once; Qt polishes a widget again on
    every theme change)."""
    view = combo.view()
    if view is None or view.property("smsPrepared"):
        return
    view.setProperty("smsPrepared", True)
    if not isinstance(combo.itemDelegate(), QStyledItemDelegate):  # Qt's own menu-like delegate
        combo.setItemDelegate(QStyledItemDelegate(combo))
    if combo.maxVisibleItems() == 10:  # Qt's default; a value someone chose stays
        combo.setMaxVisibleItems(MAX_VISIBLE)
    if isinstance(view, QListView):
        view.setUniformItemSizes(True)  # a long list lays out at once
        view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        view.installEventFilter(_PopupFilter.instance())


class _PopupFilter(QObject):
    """One filter for every combo box's list view: on show, fit the width and
    add the filter field to a long list; keys typed go to the field; on hide,
    the whole list again. One object, holding no widget, so it keeps no
    window alive."""

    _instance: _PopupFilter | None = None

    @classmethod
    def instance(cls) -> _PopupFilter:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def eventFilter(self, view, event) -> bool:  # noqa: N802 -- Qt's name
        kind = event.type()
        if kind == QEvent.Type.Show:
            _on_show(view)
        elif kind == QEvent.Type.Hide:
            _reset(view)
        elif kind == QEvent.Type.KeyPress:
            return _on_key(view, event)
        return False


def _combo_of(view: QListView) -> QComboBox | None:
    widget = view.parentWidget()
    while widget is not None and not isinstance(widget, QComboBox):
        widget = widget.parentWidget()
    return widget


def filter_field(view: QListView) -> QLineEdit | None:
    """The filter field of ``view``'s list, when it has one."""
    container = view.parentWidget()
    return container.findChild(QLineEdit, _FILTER_NAME) if container is not None else None


def _on_show(view: QListView) -> None:
    combo = _combo_of(view)
    container = view.parentWidget()
    if combo is None or container is None:
        return
    # As wide as the longest entry (up to the screen), never narrower than the field.
    wanted = view.sizeHintForColumn(0) + 2 * view.frameWidth() + view.verticalScrollBar().sizeHint().width()
    screen = combo.screen()
    limit = screen.availableGeometry().width() if screen is not None else wanted
    width = min(max(wanted, combo.width()), limit)
    if width > container.width():
        container.resize(width, container.height())
    field = filter_field(view)
    if combo.count() < FILTER_MIN:
        if field is not None:
            field.hide()
        return
    # The field takes room from the list once laid out: the current entry
    # back in the middle, after that.
    QTimer.singleShot(0, view, lambda: view.scrollTo(view.currentIndex(), QAbstractItemView.ScrollHint.PositionAtCenter))
    if field is None and container.layout() is not None:
        field = QLineEdit(container)
        field.setObjectName(_FILTER_NAME)
        field.setPlaceholderText("Type to filter")
        field.setClearButtonEnabled(True)
        field.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        field.textChanged.connect(lambda text, v=view: apply_filter(v, text))
        field.installEventFilter(_FieldKeys.instance())
        container.layout().insertWidget(0, field)
    if field is not None:
        field.show()


def apply_filter(view: QListView, text: str) -> int:
    """Show only the rows containing ``text`` (case-blind); the first one
    left becomes current and the list starts there, so Enter picks it.
    Returns the rows shown."""
    combo = _combo_of(view)
    if combo is None:
        return 0
    needle = text.strip().casefold()
    model = view.model()
    shown = 0
    first = None
    for row in range(model.rowCount(view.rootIndex())):
        index = model.index(row, combo.modelColumn(), view.rootIndex())
        label = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        hidden = bool(needle) and needle not in label.casefold()
        view.setRowHidden(row, hidden)
        if not hidden:
            shown += 1
            if first is None:
                first = index
    if first is not None:
        view.setCurrentIndex(first)
        view.scrollTo(first, QAbstractItemView.ScrollHint.PositionAtTop)
    return shown


def _reset(view: QListView) -> None:
    field = filter_field(view)
    if field is not None and field.text():
        field.blockSignals(True)
        field.clear()
        field.blockSignals(False)
    model = view.model()
    if model is not None:
        for row in range(model.rowCount(view.rootIndex())):
            if view.isRowHidden(row):
                view.setRowHidden(row, False)


def _on_key(view: QListView, event) -> bool:
    """Printable keys, Backspace and Delete go to the filter field; the
    arrows, Page keys, Enter and Escape stay with the list."""
    field = filter_field(view)
    if field is None or not field.isVisible():
        return False
    key = event.key()
    if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
        field.backspace()
        return True
    text = event.text()
    modifiers = event.modifiers() & ~Qt.KeyboardModifier.ShiftModifier & ~Qt.KeyboardModifier.KeypadModifier
    if text and text.isprintable() and not modifiers:
        field.insert(text)
        return True
    return False


class _FieldKeys(QObject):
    """In the filter field (clicked into), the arrows and Enter act on the list."""

    _instance: _FieldKeys | None = None

    @classmethod
    def instance(cls) -> _FieldKeys:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def eventFilter(self, field, event) -> bool:  # noqa: N802 -- Qt's name
        if event.type() != QEvent.Type.KeyPress:
            return False
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
                           Qt.Key.Key_Return, Qt.Key.Key_Enter):
            container: QWidget = field.parentWidget()
            view = container.findChild(QListView) if container is not None else None
            if view is not None:
                view.setFocus()
                QApplication.sendEvent(view, event.clone())
                return True
        return False
