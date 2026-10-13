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


"""A file's value outside a field's range is kept and said, never clamped
silently; and a problem waiting in one form no longer hides the others."""

import dataclasses
from pathlib import Path

import pytest

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def window(qtbot, monkeypatch):
    """A main window with template 22 open."""
    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


@pytest.mark.parametrize("cls", ["SpinBox", "DoubleSpinBox", "PreciseDoubleSpinBox"])
def test_a_box_keeps_a_value_outside_its_range(qtbot, cls):
    """The box shows the nearest allowed value but keeps the one set, until
    it is changed in the box."""
    from spacemissionstudio.gui import widgets

    box = getattr(widgets, cls)()
    qtbot.addWidget(box)
    box.setRange(0, 4)
    box.setValue(5)
    assert box.value() == 5 and box.out_of_range_value() == 5 and widgets.out_of_range_boxes(box.parentWidget()
                                                                                              or box) in ([], [box])
    assert float(box.text()) == 4
    box.stepBy(-1)
    assert box.value() == 3 and box.out_of_range_value() is None
    box.setValue(2)
    assert box.out_of_range_value() is None


def test_a_range_set_after_the_value_shows_it(qtbot):
    """A value set before its range (Qt's default 0 to 99.99) is no longer
    cut to 99.99."""
    from spacemissionstudio.gui.widgets import PreciseDoubleSpinBox

    box = PreciseDoubleSpinBox()
    qtbot.addWidget(box)
    box.setValue(150.0)  # [kg]
    box.setRange(0.0, 1000.0)  # [kg]
    assert box.value() == 150.0 and box.out_of_range_value() is None and box.text().startswith("150")  # [kg]


def test_an_out_of_range_value_is_kept_said_and_opened(window):
    """A station 12000 m up (the schema takes it; the box goes to 9000 m):
    the box is marked, Problems has a warning naming the field that opens
    it, and an edit to another field of the form keeps 12000 m."""
    from spacemissionstudio.gui.feedback import field_error_text

    editor = window.scenario_editor
    stations = editor.ground_station_list
    stations.from_list([dataclasses.replace(stations.to_list()[0], altitude_m=12000.0)])  # [m]
    editor.show_station(0)
    form = editor._station_nodes[0].form
    warning = next(text for _severity, text in editor.problems if "outside this field's range" in text)
    assert warning.startswith("berlin-gs: ") and "is 12000 in the file" in warning and "-500 to 9000" in warning
    assert field_error_text(form.alt_m) == warning and form.alt_m.property("state") == "warning"
    assert not [text for severity, text in editor.problems if severity == "error"]  # a warning: the run may go

    form.name_edit.setText("berlin-gs-2")
    editor.flush_forms()
    assert stations.to_list()[0].name == "berlin-gs-2"
    assert stations.to_list()[0].altitude_m == 12000.0  # [m] kept, not clamped to 9000
    renamed = next(text for _severity, text in editor.problems if "outside this field's range" in text)
    assert renamed.startswith("berlin-gs-2: ")
    assert editor.page_tree.problem_count(editor._station_nodes[0].item) == 1

    editor.show_scenario_page()
    window.problems_widget.activated.emit(renamed)
    assert editor.page_tree.current_page() is editor._station_nodes[0].holder


def test_a_value_the_schema_rejects_is_also_flagged_at_its_box(window):
    """Latitude 100 deg: the schema's error, and the box's warning."""
    editor = window.scenario_editor
    stations = editor.ground_station_list
    stations.from_list([dataclasses.replace(stations.to_list()[0], latitude_deg=100.0)])  # [deg]
    editor.show_station(0)
    texts = [text for _severity, text in editor.problems]
    assert any(text.startswith("berlin-gs: latitude_deg must be in [-90, 90]") for text in texts)
    assert any(text.startswith("berlin-gs: Geodetic latitude [deg]") and "is 100 in the file" in text
               for text in texts)


def test_changing_the_box_ends_the_warning(window):
    """Once the value is changed in the box, it is in range: no warning."""
    editor = window.scenario_editor
    stations = editor.ground_station_list
    stations.from_list([dataclasses.replace(stations.to_list()[0], altitude_m=12000.0)])  # [m]
    editor.show_station(0)
    form = editor._station_nodes[0].form
    form.alt_m.setValue(8000.0)  # [m]
    editor.flush_forms()
    assert not any("outside this field's range" in text for _severity, text in editor.problems)
    assert stations.to_list()[0].altitude_m == 8000.0  # [m]


def test_a_waiting_form_problem_no_longer_hides_the_others(window):
    """An empty spacecraft name in its form and a bad epoch: both listed."""
    editor = window.scenario_editor
    editor.epoch_edit.setText("2030-13-45T99:00:00")
    editor.show_spacecraft(0)
    editor._spacecraft_nodes[0].form.name_edit.setText("")
    editor.flush_forms()
    errors = [text for severity, text in editor.problems if severity == "error"]
    assert any("name must not be empty" in text for text in errors)
    assert any(text.startswith("scenario.epoch_utc") for text in errors)
    assert "(and 1 more: see Problems)" in editor.validation_label.text()
