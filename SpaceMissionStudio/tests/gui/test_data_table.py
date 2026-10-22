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

"""DataTable (UI overhaul M6b): a QTableView over a model with the table
rules -- numbers right-aligned in the numeric font, TSV copy, a column
menu, group rows across the table, a row filter, sorting by value and an
empty state with its action."""

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QGuiApplication

pytestmark = pytest.mark.requires_gui


@pytest.fixture
def table(qtbot):
    from spacemissionstudio.gui.data_table import DataTable, Row

    view = DataTable("No rows yet.", action="Run")
    qtbot.addWidget(view)
    view.set_table(["Quantity", "Before\n0 s", "After\n1 h"], [
        Row(["Semi-major axis [km]", "6,928.1", "6,930.4"], tooltips={0: "sat-1.sma"}),
        Row(["Mean elements"], group=True),
        Row(["Inclination [deg]", "97.6", "97.6"], tooltips={0: "sat-1.inc"}),
    ], numeric=[1, 2])
    return view


def test_numbers_are_right_aligned_in_the_numeric_font(table):
    from spacemissionstudio.gui.theme import numeric_font

    model = table.model
    right = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    assert model.data(model.index(0, 1), Qt.ItemDataRole.TextAlignmentRole) == right
    assert model.data(model.index(0, 1), Qt.ItemDataRole.FontRole).family() == numeric_font().family()
    assert model.data(model.index(0, 0), Qt.ItemDataRole.TextAlignmentRole) is None
    assert model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole) == right


def test_a_group_row_spans_the_table_and_follows_the_filter(table):
    assert table.view.columnSpan(1, 0) == 3
    table.set_row_filter(lambda row: row != 0)
    assert table.row_count() == 2 and table.view.columnSpan(0, 0) == 3  # the heading moved up a row
    assert table.cell(1, 0) == "Inclination [deg]" and table.cell_tooltip(1, 0) == "sat-1.inc"


def test_the_text_and_the_copy_are_tab_separated_with_the_header(table, qtbot):
    assert table.text().splitlines() == ["Quantity\tBefore 0 s\tAfter 1 h", "Semi-major axis [km]\t6,928.1\t6,930.4",
                                         "Mean elements", "Inclination [deg]\t97.6\t97.6"]
    table.view.selectRow(2)
    table.view.setFocus()
    qtbot.keyClick(table.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QGuiApplication.clipboard().text() == "Quantity\tBefore 0 s\tAfter 1 h\nInclination [deg]\t97.6\t97.6"


def test_the_header_menu_hides_a_column_but_not_the_first(table):
    table._on_header_menu(table.view.horizontalHeader().rect().center())
    actions = table.column_menu.actions()
    assert not actions[0].isEnabled()
    actions[1].setChecked(False)
    assert table.view.isColumnHidden(1) and table.text().splitlines()[0] == "Quantity\tAfter 1 h"
    table.column_menu.close()


def test_a_sortable_table_sorts_by_value(qtbot):
    from spacemissionstudio.gui.data_table import DataTable, Row

    view = DataTable()
    qtbot.addWidget(view)
    view.set_table(["Run", "Cd [-]"], [Row([str(run), f"{cd:g}"], keys=[run, cd])
                                      for run, cd in ((0, 2.0), (1, 10.0), (2, 9.5))], numeric=[0, 1])
    view.set_sortable(0)
    assert [view.cell(r, 0) for r in range(3)] == ["0", "1", "2"]
    view.sort_by(1, Qt.SortOrder.DescendingOrder)
    assert [view.cell(r, 1) for r in range(3)] == ["10", "9.5", "2"]  # not "9.5" > "2" > "10" as text


def test_an_empty_table_shows_its_text_and_action(qtbot):
    from spacemissionstudio.gui.data_table import DataTable

    view = DataTable("No rows yet.", action="Run")
    qtbot.addWidget(view)
    assert view.stack.currentWidget() is view.empty and view.empty_label.text() == "No rows yet."
    with qtbot.waitSignal(view.action_requested, timeout=1000):
        view.empty_button.click()
    view.clear("Nothing ran.")
    assert view.empty_label.text() == "Nothing ran." and view.model.rowCount(QModelIndex()) == 0
