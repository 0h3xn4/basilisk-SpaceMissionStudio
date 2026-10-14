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

"""The tree of pages the Scenario Editor is built on (docs/ux-audit.md
U-01): pages and groups, finding the page of any widget, problem counts,
removal, and the edit watcher its live forms use."""

import pytest

pytestmark = pytest.mark.requires_gui


@pytest.fixture
def tree(qtbot):
    """A tree: A, a group G with B and C under it."""
    from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

    from spacemissionstudio.gui.page_tree import PageTree

    t = PageTree()
    qtbot.addWidget(t)
    t.a, t.b = QLabel("A"), QWidget()
    t.field = QLineEdit()
    QVBoxLayout(t.b).addWidget(t.field)
    t.c = QLabel("C")
    t.add_page("A", t.a)
    t.group = t.add_group("G")
    t.add_page("B", t.b, t.group)
    t.item_c = t.add_page("C", t.c, t.group)
    return t


def test_pages_groups_and_paths(tree):
    """The first page shows first; a group shows its first child; paths
    name every page."""
    assert tree.current_page() is tree.a
    tree.tree.setCurrentItem(tree.group)
    assert tree.current_page() is tree.b
    assert [path for path, _page in tree.paths()] == ["A", "G > B", "G > C"]


def test_show_page_finds_the_page_of_any_widget_in_it(tree):
    """A widget inside a page selects that page's node."""
    assert tree.show_page(tree.field) and tree.current_page() is tree.b
    from PySide6.QtWidgets import QLabel

    assert not tree.show_page(QLabel("elsewhere"))


def test_a_problem_count_follows_the_title(tree):
    """A count shows after the title, and goes with zero."""
    tree.set_problem_count(tree.item_c, 2)
    assert tree.item_c.text(0) == "C (2)" and "2 problems" in tree.item_c.toolTip(0)
    tree.set_title(tree.item_c, "Renamed")
    assert tree.item_c.text(0) == "Renamed (2)"
    tree.set_problem_count(tree.item_c, 0)
    assert tree.item_c.text(0) == "Renamed"


def test_removing_a_node_removes_its_page(tree):
    """Removing the group takes its pages out of the stack."""
    count = tree.stack.count()
    tree.remove(tree.group)
    assert tree.stack.count() == count - 2 and [path for path, _ in tree.paths()] == ["A"]


def test_watch_edits_hears_every_kind_of_field(qtbot):
    """Text, numbers, choices, ticks and custom widgets' changed signals."""
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QCheckBox, QFormLayout, QLineEdit, QWidget

    from spacemissionstudio.gui.page_tree import watch_edits
    from spacemissionstudio.gui.widgets import ComboBox, PreciseDoubleSpinBox

    class Custom(QWidget):
        changed = Signal()

    form = QWidget()
    qtbot.addWidget(form)
    layout = QFormLayout(form)
    text, number, choice, tick, custom = QLineEdit(), PreciseDoubleSpinBox(), ComboBox(), QCheckBox(), Custom()
    choice.addItems(["one", "two"])
    for widget in (text, number, choice, tick, custom):
        layout.addRow(widget)
    heard = []
    assert watch_edits(form, lambda *_: heard.append(1)) >= 5
    text.setText("x")
    number.setValue(2.5)
    choice.setCurrentIndex(1)
    tick.setChecked(True)
    custom.changed.emit()
    assert len(heard) == 5
