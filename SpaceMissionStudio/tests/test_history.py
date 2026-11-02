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
"""spacemissionstudio.history (transparency plan, Phase 7): the change
history beside a scenario, written by every save."""

import json
from datetime import UTC, datetime

import pytest

from spacemissionstudio import cli, history
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import OrbitIC, Scenario, SpacecraftConfig, ValueMark

_NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)


def _scenario():
    return Scenario(name="history", epoch_utc="2030-01-01T00:00:00", spacecraft=[SpacecraftConfig(
        name="sat-1", dry_mass_kg=100.0,
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                      inclination_deg=97.8, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))])


def test_the_history_sits_beside_the_scenario():
    assert history.history_path("/m/mission.json").as_posix() == "/m/mission.history.jsonl"


def test_each_save_records_what_it_changed(tmp_path):
    """The first save records the scenario's creation; a later one each
    value it changes, old and new, with the time, author and source; a save
    that changes nothing records nothing. The file is only appended to."""
    path = tmp_path / "mission.json"
    scenario = _scenario()
    entries, problem = history.save(scenario, path, author="ana", source="app")
    assert problem is None
    assert [(e["kind"], e["path"], e["new"], e["author"]) for e in entries] == [("created", "", "history", "ana")]
    scenario.spacecraft[0].dry_mass_kg = 120.0  # [kg]
    scenario.spacecraft[0].orbit.inclination_deg = 98.0  # [deg]
    edits = history.entries_for_save(path, scenario, author="ana", reason="new bus", now=_NOW)
    assert sorted((e["kind"], e["path"], e["old"], e["new"], e["reason"], e["time_utc"]) for e in edits) == [
        ("edit", "spacecraft[sat-1].dry_mass_kg", 100.0, 120.0, "new bus", "2026-11-02T12:00:00Z"),
        ("edit", "spacecraft[sat-1].orbit.inclination_deg", 97.8, 98.0, "new bus", "2026-11-02T12:00:00Z"),
    ]
    history.save(scenario, path, author="ana", reason="new bus")
    assert history.save(scenario, path, author="ana")[0] == []
    recorded, problems = history.read(path)
    assert problems == [] and [e["kind"] for e in recorded] == ["created", "edit", "edit"]
    assert {e["path"]: (e["old"], e["new"]) for e in recorded[1:]} == {
        "spacecraft[sat-1].orbit.inclination_deg": (97.8, 98.0), "spacecraft[sat-1].dry_mass_kg": (100.0, 120.0)}
    assert load_scenario(path).spacecraft[0].dry_mass_kg == 120.0


def test_an_override_carries_its_reason_and_the_marks_are_not_values(tmp_path):
    """A value marked overridden is recorded as an override with the
    mark's reason; the marks themselves (and preset records) are the record
    of those values, not values, so they are left out."""
    path = tmp_path / "mission.json"
    scenario = _scenario()
    history.save(scenario, path, author="ana")
    scenario.spacecraft[0].orbit.inclination_deg = 98.0  # [deg]
    scenario.value_marks = [ValueMark("spacecraft[sat-1].orbit.inclination_deg", "overridden", 97.8,
                                      "Sun-synchronous inclination at 621.9 km", "launcher's injection", "ana")]
    entries, _problem = history.save(scenario, path, author="ana")
    assert [(e["kind"], e["path"], e["reason"]) for e in entries] == [
        ("override", "spacecraft[sat-1].orbit.inclination_deg", "launcher's injection")]


def test_a_file_that_is_not_a_scenario_is_recorded_as_replaced(tmp_path):
    path = tmp_path / "mission.json"
    path.write_text("{not json", encoding="utf-8")
    entries, _problem = history.save(_scenario(), path, author="ana")
    assert [e["kind"] for e in entries] == ["replaced"] and "unreadable" in entries[0]["old"]


def test_a_history_that_cannot_be_written_does_not_lose_the_save(tmp_path, monkeypatch):
    """The scenario is saved; the problem is returned, for the caller to
    show, and nothing is raised."""
    path = tmp_path / "mission.json"

    def refuse(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(history, "append", refuse)
    entries, problem = history.save(_scenario(), path, author="ana")
    assert path.exists() and entries and "could not be written: disk full" in problem


def test_a_damaged_line_is_skipped_and_named(tmp_path):
    path = tmp_path / "mission.json"
    history.save(_scenario(), path, author="ana")
    with open(history.history_path(path), "a", encoding="utf-8") as stream:
        stream.write("not json\n" + json.dumps({"no": "kind"}) + "\n")
    entries, problems = history.read(path)
    assert len(entries) == 1 and len(problems) == 2 and problems[0].startswith("mission.history.jsonl line 2")


def test_the_author_is_the_user_name_until_one_is_set(monkeypatch):
    monkeypatch.setattr(history.getpass, "getuser", lambda: "ana")
    assert history.default_author() == "ana"

    def no_user():
        raise KeyError("no passwd entry")

    monkeypatch.setattr(history.getpass, "getuser", no_user)
    assert history.default_author() == "unknown"


def test_a_command_that_saves_records_its_changes(tmp_path, capsys):
    """The command line's saves record theirs, naming the command."""
    path = tmp_path / "template.json"
    _scenario().save(path)
    out = tmp_path / "constellation.json"
    assert cli.main(["generate-constellation", str(path), "--out", str(out), "--total-satellites", "2",
                     "--planes", "1", "--phasing-factor", "0", "--altitude-km", "700",
                     "--inclination-deg", "98.0"]) == 0
    entries, _problems = history.read(out)
    assert [(e["kind"], e["source"]) for e in entries] == [("created", "spacemissionstudio generate-constellation")]
    capsys.readouterr()


@pytest.mark.requires_gui
def test_the_app_records_a_save(qtbot, tmp_path, monkeypatch):
    """File > Save records the change in the history beside the file: the
    first save its creation, the next the name changed in the form."""
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    assert window.open_path(templates / "22_starter_first_leo_satellite.json")
    path = tmp_path / "mine.json"
    window._save_to(path)
    window.scenario_editor.name_edit.setText("My first satellite")
    window._save_to(path)
    entries, _problems = history.read(path)
    assert [(e["kind"], e["source"]) for e in entries] == [("created", "app"), ("edit", "app")]
    assert (entries[1]["path"], entries[1]["new"]) == ("name", "My first satellite")


def test_the_name_set_in_settings_is_every_saves_author(tmp_path, monkeypatch):
    """A name set (one line, its spaces tidied) is kept in a plain file the
    command line reads too, and every save records it; an empty one
    forgets it: the user name again."""
    monkeypatch.setattr(history.getpass, "getuser", lambda: "ana")
    assert history.current_author() == "ana" and history.set_author_name() == ""
    history.set_author("  Ana  Ruiz\n")
    assert history.author_file().read_text(encoding="utf-8") == "Ana Ruiz\n"
    assert history.current_author() == "Ana Ruiz"
    path = tmp_path / "template.json"
    _scenario().save(path)
    out = tmp_path / "constellation.json"
    assert cli.main(["generate-constellation", str(path), "--out", str(out), "--total-satellites", "2",
                     "--planes", "1", "--phasing-factor", "0", "--altitude-km", "700",
                     "--inclination-deg", "98.0"]) == 0
    assert [e["author"] for e in history.read(out)[0]] == ["Ana Ruiz"]
    history.set_author("")
    assert not history.author_file().exists() and history.current_author() == "ana"


@pytest.mark.requires_gui
def test_settings_sets_the_author_the_app_records(qtbot, tmp_path, monkeypatch):
    """Settings > Change history: the name typed is kept, shown with what
    saves will record, and the app's next save records it."""
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from spacemissionstudio.gui.main_window import MainWindow

    monkeypatch.setattr(history.getpass, "getuser", lambda: "ana")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard))
    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    qtbot.addWidget(window)
    settings = window.settings_page
    assert "history" in dict(settings.sections()) and settings.author_edit.placeholderText() == "ana"
    settings.author_edit.setText("Ana Ruiz")
    settings.author_edit.editingFinished.emit()
    assert history.set_author_name() == "Ana Ruiz"
    assert settings.author_note.text() == "Saves are recorded as Ana Ruiz."
    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    assert window.open_path(templates / "22_starter_first_leo_satellite.json")
    path = tmp_path / "mine.json"
    window._save_to(path)
    assert [e["author"] for e in history.read(path)[0]] == ["Ana Ruiz"]
