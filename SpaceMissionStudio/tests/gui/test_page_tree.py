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
    assert tree.item_c.text(0) == "C (2)" and "2 errors" in tree.item_c.toolTip(0)
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


def test_a_count_of_warnings_only_is_in_the_warning_colour(tree):
    """Red when one of the problems is an error, the warning colour when
    all are warnings; the tooltip counts each."""
    from spacemissionstudio.gui.theme import PALETTE

    tree.set_problem_count(tree.item_c, 2, warnings=2)
    assert tree.item_c.text(0) == "C (2)" and tree.item_c.foreground(0).color().name().upper() == PALETTE["warning"]
    assert tree.item_c.toolTip(0) == "2 warnings here: see Problems"
    tree.set_problem_count(tree.item_c, 3, warnings=2)
    assert tree.item_c.foreground(0).color().name().upper() == PALETTE["danger_text"]
    assert tree.item_c.toolTip(0) == "1 error and 2 warnings here: see Problems"


def test_a_section_shows_its_part_of_the_parent_page(tree, qtbot):
    """A section node shows its parent's page and names its part of it;
    the parent goes to its first section; a widget in a section's part is
    found at the section."""
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

    page = QWidget()
    first, second = QWidget(), QWidget()
    layout = QVBoxLayout(page)
    layout.addWidget(first)
    layout.addWidget(second)
    field = QLineEdit(second)
    item = tree.add_page("D", page)
    one = tree.add_section("One", "one", item)
    two = tree.add_section("Two", "two", item)
    tree.set_section_widget(one, first)
    tree.set_section_widget(two, second)
    shown = []
    tree.section_shown.connect(lambda widget, key: shown.append((widget, key)))
    tree.tree.setCurrentItem(item)
    assert tree.tree.currentItem() is one and tree.current_page() is page and shown == [(page, "one")]
    assert tree.item_of(field) is two and tree.show_page(field) and shown[-1] == (page, "two")
    assert [path for path, _item in tree.paths()][-2:] == ["D > One", "D > Two"]
    count = tree.stack.count()
    tree.remove(item)
    assert tree.stack.count() == count - 1  # the page once, not once per section


def test_the_arrow_keys_pass_through_a_group_both_ways(tree, qtbot):
    """Down into a group or a page shown through its sections selects its
    first child; Up from that child leaves it upwards, and Up from below
    selects its last child (before, Up from a group's first child came
    back to it: the keyboard could not get past the group)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    page = QWidget()
    item_d = tree.add_page("D", page)
    one = tree.add_section("One", "one", item_d)
    two = tree.add_section("Two", "two", item_d)
    tree.show()
    tree.tree.setFocus()
    tree.tree.setCurrentItem(tree.tree.topLevelItem(0))  # A

    def press(key):
        qtbot.keyClick(tree.tree, key)
        qtbot.wait(1)  # the key's direction is forgotten after the event
        return tree.tree.currentItem().text(0)

    assert press(Qt.Key.Key_Down) == "B"  # A, then G passes to B
    assert press(Qt.Key.Key_Up) == "A"  # G passes up, not back to B
    assert [press(Qt.Key.Key_Down) for _ in range(3)] == ["B", "C", "One"]  # D passes to One
    assert press(Qt.Key.Key_Down) == "Two" and tree.tree.currentItem() is two
    assert press(Qt.Key.Key_Up) == "One" and tree.tree.currentItem() is one
    assert press(Qt.Key.Key_Up) == "C"  # D passes up
    tree.tree.setCurrentItem(item_d)  # by a click or a call: its first section
    assert tree.tree.currentItem() is one
    item_e = tree.add_page("E", QWidget())
    tree.tree.setCurrentItem(item_e)
    assert press(Qt.Key.Key_Up) == "Two"  # Up into D from below: its last section
