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
"""The forms (UI overhaul plan §7, M4a): number fields with their unit as
a suffix, the same values and the same file written; optional groups that
collapse when off; every Scenario page without sideways scrolling at
1280 px; the unsaved-changes indicator."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
_ALL = sorted(_TEMPLATES.glob("*.json"))


@pytest.fixture(scope="module")
def _shared_window(qapp):
    """One 1280 x 720 main window with the app's theme (widths are measured
    with its fonts), for the module. Applying the theme restyles every
    widget alive, so it is applied once: per test, in a full-suite worker
    holding the widgets of earlier tests, it took minutes."""
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme, state

    import gc

    from PySide6.QtCore import QEvent

    # Widgets earlier tests closed but Qt has not deleted yet would be
    # restyled too: delete them first.
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    saved = (qapp.font(), qapp.palette(), qapp.styleSheet())
    apply_theme(qapp, "light")
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window._confirm_discard_unsaved = lambda: True
    window.resize(1280, 720)  # [px]
    window.show()
    QApplication.processEvents()
    yield window
    window._mark_clean()
    window.close()
    window.deleteLater()
    QApplication.processEvents()
    state.select("light")
    qapp.setStyleSheet(saved[2])
    qapp.setPalette(saved[1])
    qapp.setFont(saved[0])


@pytest.fixture
def window(_shared_window):
    """The module's window, its scenario discarded after the test."""
    yield _shared_window
    _shared_window._mark_clean()


def _pages(window):
    """Every page of the Scenario tree but JSON, shown in turn: (path, item)."""
    from PySide6.QtWidgets import QApplication

    for path, item in window.scenario_editor.page_tree.paths():
        if path == "JSON":
            continue
        window._show_tree_item(item)
        QApplication.processEvents()
        yield path


def _form_labels(root):
    """(label, field widget or layout) of every shown form row under
    ``root``, read through QObjects (widgets.form_rows), never itemAt()."""
    from PySide6.QtWidgets import QFormLayout, QLabel

    from spacemissionstudio.gui.widgets import form_rows

    rows = []
    for form in root.findChildren(QFormLayout):
        if form.parentWidget() is None or not form.parentWidget().isVisible():
            continue
        for _row, roles in sorted(form_rows(form).items()):
            label = roles.get(QFormLayout.ItemRole.LabelRole)
            if isinstance(label, QLabel) and label.isVisible():
                rows.append((label, roles.get(QFormLayout.ItemRole.FieldRole)))
    return rows


# -- the same values, the same file -------------------------------------------------

def test_the_spacecraft_dialog_hands_back_what_it_was_given(qtbot):
    """Every spacecraft of every template through the spacecraft editor's
    form, unchanged (the form holds every field of the spacecraft)."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

    for path in _ALL:
        scenario = load_scenario(path)
        for spacecraft in scenario.spacecraft:
            dialog = SpacecraftEditorDialog(spacecraft, simulation_mode=scenario.simulation_mode)
            qtbot.addWidget(dialog)
            assert dialog.to_dataclass() == spacecraft, f"{path.name}: {spacecraft.name}"
            dialog.deleteLater()


# -- units in the fields --------------------------------------------------------------

def test_the_fields_show_their_units(window):
    """Examples from template 23: mass, angles, areas and power."""
    assert window.open_path(_TEMPLATES / "23_starter_complete_small_satellite.json")
    for _page in _pages(window):
        pass
    form = window.scenario_editor._spacecraft_nodes[0].form
    assert form.dry_mass_kg.suffix() == " kg" and form.dry_mass_kg.cleanText().startswith("150")
    assert form.orbit_widget.inc_deg.suffix() == "°"
    assert form.panel_area_m2.suffix() == " m²"
    assert form.battery_capacity_wh.suffix() == " Wh"
    assert form.drag_coeff.suffix() == ""  # dimensionless


def test_a_message_still_names_the_field_with_its_unit(qtbot):
    """The label shows "Dry mass" and the field " kg"; a message names the
    field as the code does, "Dry mass [kg]"."""
    from spacemissionstudio.gui.feedback import row_label
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    assert row_label(dialog.dry_mass_kg) == "Dry mass [kg]"


def test_the_unit_spellings():
    """The field shows the unit typeset; the label's bracket is parsed only
    for known units."""
    from spacemissionstudio.gui import units

    assert units.suffix("m^2") == " m²" and units.suffix("kg*m^2") == " kg·m²" and units.suffix("deg") == "°"
    assert units.suffix("W*hr") == " Wh" and units.suffix("-") == "" and units.suffix("days") == " days"
    assert units.split_label("Center of mass [m] (x, y, z from B)") == ("Center of mass (x, y, z from B)", "m")
    assert units.split_label('Visible ["visible"]') == ('Visible ["visible"]', None)  # a key, not a unit
    assert units.split_label("Noise [lo, hi]") == ("Noise [lo, hi]", None)


# -- optional groups ----------------------------------------------------------------

def test_an_optional_group_shows_only_its_title_while_off(qtbot):
    """Station keeping off: its title only; on: its fields, which keep their
    values through the round trip."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    group = dialog.station_keeping_group  # on a tab not shown: visibility is asked of the group
    assert not group.isChecked()
    assert not dialog.sk_target_altitude_km.isVisibleTo(group)
    group.setChecked(True)
    assert dialog.sk_target_altitude_km.isVisibleTo(group)
    dialog.sk_target_altitude_km.setValue(420.0)  # [km]
    group.setChecked(False)
    assert not dialog.sk_target_altitude_km.isVisibleTo(group)
    group.setChecked(True)
    assert dialog.sk_target_altitude_km.value() == 420.0  # [km]


def test_monte_carlo_off_shows_only_its_switch_and_what_it_does(qtbot):
    """Monte Carlo off: the switch and one line on what it does; on: the
    number of runs, threads and dispersions. Values set while off are kept."""
    from spacemissionstudio.gui.monte_carlo_editor import MonteCarloGroupWidget

    group = MonteCarloGroupWidget()
    qtbot.addWidget(group)
    group.show()
    assert not group.enabled_check.isChecked()
    assert group.off_label.isVisible() and not group.num_runs_spin.isVisible()
    group.num_runs_spin.setValue(25)
    group.enabled_check.setChecked(True)
    assert group.num_runs_spin.isVisible() and group.dispersion_list.isVisible() and not group.off_label.isVisible()
    assert group.num_runs_spin.value() == 25


# -- widths ---------------------------------------------------------------------------

def _sideways(window):
    from PySide6.QtWidgets import QScrollArea

    return [area for area in window.scenario_editor.findChildren(QScrollArea)
            if area.isVisible() and area.widget() is not None and area.horizontalScrollBar().isVisible()]


def _boxes_in_boxes(window):
    """A framed panel or a scroll area inside the page shown: "boxes in
    boxes". Inputs and lists keep their 1 px border; a card is a surface."""
    from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QFrame, QLabel, QLineEdit,
                                   QPlainTextEdit, QScrollArea, QTextEdit)

    page = window.scenario_editor.page_tree.stack.currentWidget()
    found = []
    for frame in page.findChildren(QFrame):
        if not frame.isVisible() or isinstance(frame, (QAbstractItemView, QLineEdit, QTextEdit, QPlainTextEdit,
                                                       QLabel, QAbstractScrollArea)):
            continue
        if frame.property("role") != "card" and frame.frameShape() != QFrame.Shape.NoFrame:
            found.append(f"framed {type(frame).__name__}")
    for area in page.findChildren(QScrollArea):
        parent = area.parentWidget()
        while area.isVisible() and parent is not None and parent is not page:
            if isinstance(parent, QScrollArea):
                found.append(f"scroll area in a scroll area: {area.objectName()}")
                break
            parent = parent.parentWidget()
    return found


# -- every page of every template, in one walk ----------------------------------------

def _units_left(window, page):
    """Labels on the page shown with a known unit in brackets and a number
    field; and number fields not right-aligned."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractSpinBox, QWidget

    from spacemissionstudio.gui import units

    found = []
    for label, field in _form_labels(window.scenario_editor):
        widget = field if isinstance(field, QWidget) else None  # a layout field: its boxes are not read here
        boxes = ([widget] if isinstance(widget, QAbstractSpinBox)
                 else widget.findChildren(QAbstractSpinBox) if widget is not None else [])
        if units.split_label(label.text())[1] is not None and boxes:
            found.append(f"{page}: unit in the label {label.text()!r}")
        found += [f"{page}: {label.text()!r} not right-aligned" for box in boxes
                  if not box.alignment() & Qt.AlignmentFlag.AlignRight]
    return found


@pytest.mark.parametrize("path", _ALL, ids=[p.name[:2] for p in _ALL])
def test_every_page_of_the_template(window, path, tmp_path):
    """One walk through every page of a template (each page builds its
    form), at 1280 x 720 with the inspector and Explain shown:
    - no form label keeps a unit its number field can show, and number
      fields are right-aligned ("150.000 kg");
    - no page scrolls sideways (the Power page did, at 1440 px), and none
      has a framed panel or a scroll area inside it (no boxes in boxes);
    - nothing widens the window;
    - saved afterwards, the file is the template's byte for byte: units
      moved into the fields change no value (the platform's line
      endings aside: the checkout has LF, a save on Windows CRLF)."""
    assert window.side_dock.isVisible()
    assert window.open_path(path)
    problems = []
    for page in _pages(window):
        problems += _units_left(window, page)
        if _sideways(window):
            problems.append(f"{page}: scrolls sideways")
        problems += [f"{page}: {what}" for what in _boxes_in_boxes(window)]
    assert problems == []
    assert window.width() == 1280  # [px]
    out = tmp_path / path.name
    window.scenario_editor.to_scenario().save(out)
    assert out.read_bytes().replace(b"\r\n", b"\n") == path.read_bytes().replace(b"\r\n", b"\n")


# -- the unsaved-changes indicator ------------------------------------------------------

def test_an_edit_in_a_number_field_shows_unsaved_changes_until_saved(window, qtbot, tmp_path, monkeypatch):
    """A changed number marks the scenario unsaved in the top bar and the
    window title once the edit settles (300 ms after it); Save As clears it."""
    from PySide6.QtWidgets import QFileDialog

    copy = tmp_path / "mine.json"
    copy.write_bytes((_TEMPLATES / "22_starter_first_leo_satellite.json").read_bytes())
    assert window.open_path(copy)
    assert not window.top_bar.detail_label.text().startswith("Unsaved changes")
    for _page in _pages(window):
        pass
    window.scenario_editor._spacecraft_nodes[0].form.dry_mass_kg.setValue(175.0)  # [kg]
    qtbot.waitUntil(lambda: window.top_bar.detail_label.text().startswith("Unsaved changes"))
    assert window.windowTitle().endswith("*")
    saved = tmp_path / "saved.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(saved), "")))
    window.on_save_as()
    assert not window.top_bar.detail_label.text().startswith("Unsaved changes")
    assert not window.windowTitle().endswith("*")


def test_the_inline_device_and_dispersion_forms_fit(window):
    """A selected device's and dispersion's form, under its list (M4b), fits
    the page at 1280 x 720 with the inspector shown: no sideways scroll, no
    boxes in boxes, the window no wider."""
    from PySide6.QtWidgets import QApplication

    assert window.open_path(_TEMPLATES / "07_attitude_pointing_with_adcs_hardware.json")
    editor = window.scenario_editor
    path, item = next((path, item) for path, item in editor.page_tree.paths() if path.endswith("Sensors / actuators"))
    window._show_tree_item(item)
    form = editor._spacecraft_nodes[0].form
    for devices in (form.sensor_list, form.actuator_list):
        assert devices.to_list(), path
        devices.list_widget.setCurrentRow(0)
        QApplication.processEvents()
        assert devices.inline.form is not None and devices.inline.form.isVisible()
        assert _sideways(window) == [] and _boxes_in_boxes(window) == [], path
    assert window.width() == 1280  # [px]

    assert window.open_path(_TEMPLATES / "09_monte_carlo_dispersion_analysis.json")
    window._show_tree_item(editor.monte_carlo_item)
    dispersions = editor.monte_carlo_group.dispersion_list
    dispersions.list_widget.setCurrentRow(0)
    QApplication.processEvents()
    assert dispersions.inline.form is not None and dispersions.inline.form.isVisible()
    assert _sideways(window) == [] and _boxes_in_boxes(window) == []
    assert window.width() == 1280  # [px]
