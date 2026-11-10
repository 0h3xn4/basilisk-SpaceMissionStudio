#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#

"""CCSDS orbit data messages in the GUI, as on the command line: the
Orbit section's Import CCSDS OPM/OMM... (``ccsds-import``), Tools ›
Export Orbits as CCSDS... (``ccsds-export``), Results › Plots › Export
all... › CCSDS ephemeris (OEM)... (``run --oem``) and Tools › Check a
CCSDS File... (``ccsds-validate``)."""

from datetime import datetime, UTC
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import ccsds_odm

pytestmark = pytest.mark.requires_gui

_TEMPLATES = Path(__file__).resolve().parents[2] / "spacemissionstudio" / "scenarios" / "templates"
LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"


def _opm(tmp_path, epoch=datetime(2030, 1, 1), name="sat.opm") -> Path:
    path = tmp_path / name
    path.write_text(ccsds_odm.write_opm(object_name="sat-1", object_id="2030-001A", center_name="EARTH",
                                        ref_frame="EME2000", time_system="UTC", epoch=epoch,
                                        r_km=[7000.0, 100.0, 0.0], v_km_s=[0.0, 7.546, 1.0]),  # [km], [km/s]
                    encoding="ascii")
    return path


def _errors(issues) -> list:
    return [issue for issue in issues if issue.level == "error"]


@pytest.fixture(autouse=True)
def _isolated_autosave(tmp_path, monkeypatch):
    """Keep the window's autosave away from the real home directory."""
    from spacemissionstudio.gui import autosave

    monkeypatch.setattr(autosave, "_AUTOSAVE_DIR", tmp_path / "autosave")
    monkeypatch.setattr(autosave, "_RECOVERY_FILE", tmp_path / "autosave" / "recovery.json")


@pytest.fixture
def answer(monkeypatch):
    """The answer QMessageBox.question gives (Yes unless changed); the
    questions asked are in ``answer.asked``."""
    from PySide6.QtWidgets import QMessageBox

    holder = type("Answer", (), {})()
    holder.value, holder.asked = QMessageBox.StandardButton.Yes, []

    def question(_parent, title, text, *_args, **_kwargs):
        holder.asked.append(text)
        return holder.value

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return holder


@pytest.fixture
def orbit_widget(qtbot):
    from spacemissionstudio.gui.orbit_ic_widget import OrbitIcWidget

    widget = OrbitIcWidget()
    qtbot.addWidget(widget)
    widget.set_epoch_provider(lambda: "2030-01-01T00:00:00")
    return widget


def test_an_opm_at_the_scenario_epoch_sets_a_cartesian_state(orbit_widget, tmp_path, answer, qtbot):
    """An OPM whose state is at the scenario epoch becomes the Cartesian
    state, with no question; the widget says which file and format."""
    path = _opm(tmp_path)
    with qtbot.waitSignal(orbit_widget.orbit_imported) as signal:
        assert orbit_widget.import_ccsds(path)
    assert signal.args == [str(path), "ccsds_opm"] and answer.asked == []
    orbit = orbit_widget.to_dataclass()
    assert orbit.type == "cartesian"
    assert orbit.position_km == pytest.approx([7000.0, 100.0, 0.0]) and orbit.velocity_km_s == pytest.approx(
        [0.0, 7.546, 1.0])


def test_an_opm_at_another_epoch_asks_to_move_the_scenario_epoch(orbit_widget, tmp_path, answer):
    """An OPM's state at another time: Cancel changes nothing; Yes moves
    the scenario epoch to the OPM's, then sets the orbit."""
    from PySide6.QtWidgets import QMessageBox

    moved = []
    orbit_widget.set_epoch_setter(moved.append)
    path = _opm(tmp_path, epoch=datetime(2030, 6, 1, 12, 0, 0))
    before = orbit_widget.to_dataclass()
    answer.value = QMessageBox.StandardButton.Cancel
    assert not orbit_widget.import_ccsds(path)
    assert moved == [] and orbit_widget.to_dataclass() == before and "2030-06-01T12:00:00" in answer.asked[0]
    answer.value = QMessageBox.StandardButton.Yes
    assert orbit_widget.import_ccsds(path)
    assert moved == ["2030-06-01T12:00:00"] and orbit_widget.to_dataclass().type == "cartesian"


def test_an_omm_sets_a_tle_and_a_bad_file_changes_nothing(orbit_widget, tmp_path, reported):
    """A TLE-based OMM sets the TLE; a file that is not a conforming
    message is refused, saying why, and the orbit stays."""
    omm = tmp_path / "iss.omm"
    omm.write_text(ccsds_odm.omm_from_tle(LINE1, LINE2, "ISS"), encoding="ascii")
    assert orbit_widget.import_ccsds(omm)
    orbit = orbit_widget.to_dataclass()
    assert (orbit.type, orbit.tle_line1, orbit.tle_line2) == ("tle", LINE1, LINE2)
    broken = tmp_path / "broken.opm"
    broken.write_text(_opm(tmp_path).read_text(encoding="ascii").replace("CENTER_NAME", "CENTRE"), encoding="ascii")
    assert not orbit_widget.import_ccsds(broken)
    assert orbit_widget.to_dataclass() == orbit
    assert reported[-1][1] == "error" and "Could not import the orbit from broken.opm" in reported[-1][0]


def test_a_spacecraft_dialog_hands_on_the_orbit_import_record(qtbot, tmp_path, answer):
    """The Add or Edit spacecraft dialog keeps the import record (the file's
    path and SHA-256, the values read) for OK, under the spacecraft's name
    then."""
    import hashlib

    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog

    dialog = SpacecraftEditorDialog(epoch_provider=lambda: "2030-01-01T00:00:00")
    qtbot.addWidget(dialog)
    path = _opm(tmp_path)
    assert dialog.orbit_widget.import_ccsds(path)
    dialog.name_edit.setText("renamed")
    [record] = dialog.pending_imports()
    assert (record.spacecraft, record.target, record.format) == ("renamed", "orbit", "ccsds_opm")
    assert record.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record.values["orbit.position_km[0]"] == pytest.approx(7000.0)  # [km]


@pytest.fixture
def window(qtbot, answer):
    from spacemissionstudio.gui.main_window import MainWindow

    w = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(w)
    assert w.open_path(_TEMPLATES / "22_starter_first_leo_satellite.json")
    return w


def test_an_import_on_a_spacecraft_page_reaches_the_scenario(window, tmp_path):
    """On a spacecraft's page an OPM at another time moves the scenario
    epoch (as agreed), sets the orbit and records the import: the
    scenario validates with it."""
    editor = window.scenario_editor
    editor.show_spacecraft(0)
    form = editor._spacecraft_nodes[0].form
    path = _opm(tmp_path, epoch=datetime(2031, 3, 4, 5, 6, 7))
    assert form.orbit_widget.import_ccsds(path)
    editor.flush_forms()
    scenario = editor.to_scenario()
    scenario.validate()
    sc = scenario.spacecraft[0]
    assert scenario.epoch_utc == "2031-03-04T05:06:07"
    assert sc.orbit.type == "cartesian" and sc.orbit.position_km == pytest.approx([7000.0, 100.0, 0.0])
    [record] = [r for r in scenario.imports if r.target == "orbit"]
    assert (record.spacecraft, record.format, record.source) == (sc.name, "ccsds_opm", str(path.resolve()))


@pytest.mark.requires_basilisk
def test_export_orbits_writes_a_conforming_opm_per_spacecraft(window, tmp_path):
    """Tools › Export Orbits as CCSDS... writes each spacecraft's starting
    state as an OPM that conforms, and Reports › Exports records it."""
    from spacemissionstudio.gui import export_log

    folder = tmp_path / "orbits"
    written = window.export_ccsds_orbits(window.scenario_editor.to_scenario(), folder)
    names = [c.name for c in window.scenario_editor.spacecraft_list.to_list()]
    assert [p.name for p in written] == [f"{name}.opm" for name in names]
    for path in written:
        assert _errors(ccsds_odm.validate(path.read_text(encoding="ascii"))) == []
    assert export_log.last("ccsds_orbits")[1] == str(folder)
    assert window.commands["tools.ccsds_export"].category == "Tools"


def test_the_check_dialog_lists_each_issue(window, tmp_path):
    """Tools › Check a CCSDS File...: a conforming OPM says so with no
    issue; a broken one lists its errors with their clauses."""
    good = window.check_ccsds_file(_opm(tmp_path))
    assert good.kind == "OPM" and _errors(good.issues) == []
    assert good.verdict_label.text().startswith("This OPM conforms to CCSDS 502.0-B-3")
    broken = tmp_path / "broken.opm"
    broken.write_text(_opm(tmp_path).read_text(encoding="ascii").replace("CENTER_NAME", "CENTRE"), encoding="ascii")
    bad = window.check_ccsds_file(broken)
    assert _errors(bad.issues) and "does not conform" in bad.verdict_label.text()
    assert bad.table.model.rowCount() == len(bad.issues)
    assert "tools.ccsds_check" in window.commands


def test_the_oem_options_keep_enough_states_for_the_interpolation(qtbot):
    """The stride is capped so that an OEM holds the 8 states a degree-7
    interpolation needs, and the dialog says how many it writes."""
    from spacemissionstudio.gui.ccsds_dialogs import OemOptionsDialog, states_written

    dialog = OemOptionsDialog(50)
    qtbot.addWidget(dialog)
    dialog.stride_box.setValue(1000)
    assert states_written(50, dialog.stride()) >= 8
    assert dialog.count_label.text().startswith(f"{states_written(50, dialog.stride())} of the 50 recorded")
    dialog.interpolation_combo.setCurrentIndex(dialog.interpolation_combo.findData("lagrange"))
    assert dialog.interpolation() == "lagrange"


def test_the_shown_run_exports_its_ephemeris_as_oem(qtbot, tmp_path, reported):
    """Results › Plots › Export all... › CCSDS ephemeris (OEM)...: one OEM
    per spacecraft that conforms, every stride-th state and the last."""
    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.gui import export_log
    from spacemissionstudio.gui.results_widget import ResultsWidget
    from spacemissionstudio.gui.run_history import RunRecord
    from spacemissionstudio.schema import OrbitIC, Scenario, SpacecraftConfig

    widget = ResultsWidget()
    qtbot.addWidget(widget)
    t_s = np.arange(50) * 60.0  # [s]
    r_m = np.column_stack([7e6 * np.cos(t_s / 900.0), 7e6 * np.sin(t_s / 900.0), np.zeros(50)])  # [m]
    result = ResultSet(scenario_name="demo")
    result.add(TimeSeries("sat-1.position_N", t_s, ("x", "y", "z"), r_m, units="m"))
    result.add(TimeSeries("sat-1.velocity_N", t_s, ("x", "y", "z"), np.gradient(r_m, t_s, axis=0), units="m/s"))
    scenario = Scenario(name="demo", epoch_utc="2030-01-01T00:00:00", spacecraft=[SpacecraftConfig(
        name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]))])
    widget.set_result(result, scenario.epoch_utc)
    widget._current_run = RunRecord(1, scenario.to_dict(), result, scenario.epoch_utc, datetime.now(UTC))
    folder = tmp_path / "oem"
    widget.export_oem(folder, stride=6, interpolation="lagrange")
    qtbot.waitUntil(lambda: bool(reported), timeout=10000)
    assert reported[-1] == (f"Exported 1 CCSDS OEM file(s) to {folder}", "success")
    text = (folder / "sat-1.oem").read_text(encoding="ascii")
    assert _errors(ccsds_odm.validate(text)) == [] and "LAGRANGE" in text
    assert len(ccsds_odm.read(text).segments[0].states) == 10  # 0, 6, ..., 48 and the last, 49
    assert export_log.last("ccsds_oem")[1] == str(folder)
    assert widget.export_oem_action.text() == "CCSDS ephemeris (OEM)..."


def test_reports_exports_lists_the_ccsds_files(qtbot):
    """Reports › Exports has the starting orbits and the ephemeris."""
    from spacemissionstudio.gui.exports_page import EXPORTS

    keys = {export.key: export for export in EXPORTS}
    assert keys["ccsds_orbits"].made_in == "Tools › Export Orbits as CCSDS..."
    assert keys["ccsds_oem"].made_in == "Results › Plots › Export all... › CCSDS ephemeris (OEM)..."
