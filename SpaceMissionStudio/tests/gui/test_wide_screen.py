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
"""The window at 2560 x 1440 (docs/ux-standard.md; iteration 7c): forms,
list editors and the template list stay at a readable width, the Scenario
form's rows stay together at the top, list buttons keep their own width,
and the plot list gets wider than at 1280 px."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_WIDE = (2560, 1440)  # [px]


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    """A 2560 x 1440 main window with template 07 (full attitude, one
    spacecraft with sensors and actuators, no station) open."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    # Laid out but never put on a screen: Qt's cocoa platform fits a
    # window it shows to the screen, which on the macOS runner left the
    # 2560 px window 618 px wide (SRelD K-14).
    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    w.resize(*_WIDE)
    w.show()
    qtbot.waitUntil(w.isVisible)
    assert (w.width(), w.height()) == _WIDE  # [px] the size the checks below rely on
    assert w.open_path(_TEMPLATES / "07_attitude_pointing_with_adcs_hardware.json")
    return w


def _show(qtbot, window, page) -> None:
    window.scenario_editor.page_tree.show_page(page)
    qtbot.waitUntil(lambda: page.isVisible())
    qtbot.wait(50)


def test_forms_stay_at_a_readable_width(qtbot, window):
    """The Scenario, Environment and spacecraft forms and the End of Life
    settings are no wider than the content width on a 2560 px window,
    where their pages are about 1500 px wide."""
    from spacemissionstudio.gui.theme import CONTENT_MAX_WIDTH_PX

    editor = window.scenario_editor
    _show(qtbot, window, editor.scenario_page)
    assert editor.scenario_page.viewport().width() > CONTENT_MAX_WIDTH_PX + 300  # [px] the page has room to spare
    assert editor.name_edit.width() < CONTENT_MAX_WIDTH_PX
    _show(qtbot, window, editor.environment_page)
    assert 0 < editor._environment_form.width() <= CONTENT_MAX_WIDTH_PX
    editor.show_spacecraft(0)
    qtbot.waitUntil(lambda: editor._spacecraft_nodes[0].form is not None and editor._spacecraft_nodes[0].form.isVisible())
    assert editor._spacecraft_nodes[0].form.width() <= CONTENT_MAX_WIDTH_PX
    eol = window.lifetime_widget
    window.show_view(eol)
    qtbot.waitUntil(eol.isVisible)
    assert eol.width() > CONTENT_MAX_WIDTH_PX  # its plot keeps the page's width
    assert eol.spacecraft_combo.width() < CONTENT_MAX_WIDTH_PX


def test_the_scenario_form_rows_stay_together_at_the_top(qtbot, window):
    """Name, mode, epoch and description one under the other: on a tall
    page the form's rows were spread over its whole height (about 150 px
    between rows at 1440 px)."""
    editor = window.scenario_editor
    _show(qtbot, window, editor.scenario_page)
    name_y = editor.name_edit.mapTo(editor.scenario_page, editor.name_edit.rect().topLeft()).y()  # [px]
    mode_y = editor.simulation_mode_combo.mapTo(editor.scenario_page,
                                                editor.simulation_mode_combo.rect().topLeft()).y()  # [px]
    description_y = editor.description_edit.mapTo(editor.scenario_page,
                                                  editor.description_edit.rect().topLeft()).y()  # [px]
    assert mode_y - name_y < 60  # [px] the next row, not a sixth of the page down
    assert description_y < 250  # [px]


def test_list_buttons_keep_their_own_width(qtbot, window):
    """Add / Edit / Remove under the spacecraft, sensor and dispersion
    lists are about a button's width, not a third of a wide page each."""
    editor = window.scenario_editor
    _show(qtbot, window, editor.spacecraft_page)
    assert editor.spacecraft_list.add_button.width() < 200  # [px]
    _show(qtbot, window, editor.monte_carlo_page)
    editor.monte_carlo_group.enabled_check.setChecked(True)  # the dispersions show only while Monte Carlo is on (M4a)
    qtbot.waitUntil(lambda: editor.monte_carlo_group.dispersion_list.add_button.isVisible())
    assert editor.monte_carlo_group.dispersion_list.add_button.width() < 200  # [px]
    _show(qtbot, window, editor.ground_station_page)
    assert editor.ground_station_list.add_button.width() < 200  # [px]
    editor.show_spacecraft(0)
    qtbot.waitUntil(lambda: editor._spacecraft_nodes[0].form is not None)
    form = editor._spacecraft_nodes[0].form
    form.show_tab("Sensors / actuators")
    qtbot.waitUntil(lambda: form.sensor_list.isVisible())
    assert 0 < form.sensor_list.add_button.width() < 200  # [px]


def test_a_template_row_keeps_its_customize_button_close(qtbot, window):
    """A template card is less than two least card widths wide (the wide
    page holds more columns instead), so a card's Customize... sits within
    it, next to its title."""
    from spacemissionstudio.gui.load_scenario_widget import CARD_MIN_WIDTH_PX
    from spacemissionstudio.gui.theme import CONTENT_MAX_WIDTH_PX, SPACE

    templates = window.load_scenario_widget
    window.show_view(templates)
    qtbot.waitUntil(templates.isVisible)
    rows = [card for card in templates.cards if card.customize_button is not None]
    assert rows
    assert templates.width() > CONTENT_MAX_WIDTH_PX + 300  # [px]
    qtbot.waitUntil(lambda: templates.grid.columns() >= 3)
    assert rows[0].width() < 2 * CARD_MIN_WIDTH_PX + SPACE["md"]  # [px]
    button = rows[0].customize_button
    right = button.mapTo(rows[0], button.rect().topRight()).x()
    assert right <= rows[0].width() and right < CARD_MIN_WIDTH_PX  # [px] beside Open, within the card


@pytest.mark.parametrize("width_px, expected_px", [(1000, (250, 250)), (2200, (330, 400))])
def test_the_plot_list_widens_on_a_wide_screen(qtbot, width_px, expected_px):
    """The plot list is 250 px, and about a sixth of a wider pane (up to
    400 px), so plot names are not cut short at 2560 px; once the user
    drags the divider, a resize keeps their width."""
    from spacemissionstudio.gui.results_widget import ResultsWidget

    widget = ResultsWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.resize(width_px, 800)  # [px] after the first show, as a main window lays out its pages
    qtbot.waitUntil(lambda: expected_px[0] <= widget.splitter.sizes()[0] <= expected_px[1])
    widget.splitter.setSizes([300, sum(widget.splitter.sizes()) - 300])  # [px]
    widget.splitter.splitterMoved.emit(300, 1)  # the user's drag
    widget.resize(width_px + 200, 800)  # [px]
    qtbot.wait(50)
    assert widget.splitter.sizes()[0] == 300  # [px]
