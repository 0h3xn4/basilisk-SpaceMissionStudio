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
"""The provenance view (transparency plan, Phase 4d): every value a run
recorded about what produced it, in groups, with a filter and Copy as
JSON; opened from the Provenance popover."""

import json

import pytest

pytestmark = pytest.mark.requires_gui


def _record() -> dict:
    """A provenance record as a run writes it (provenance.json), with the
    time scales, frames and transformations the engine gives, seeds, data
    files, configuration and a key a newer record might add."""
    from spacemissionstudio.engine import frames, time_system
    from spacemissionstudio.engine.results import RunProvenance

    provenance = RunProvenance(
        spacemissionstudio_version="2.0.0", basilisk_version="2.12.0", run_started_utc="2026-10-30T12:00:00Z",
        integrator="rkf78", dynamics_task_rate_s=10.0, integrator_relative_tolerance=1e-10,  # [s], [-]
        integrator_absolute_tolerance=1e-8, rng_seed=42, rng_seeds={"sat-1.imu": 1729, "sat-1.css": 271828},
        rng_seed_note="derived from sim_settings.seed", qualified_basilisk_version="2.12.0", basilisk_qualified=True,
        dependency_versions={"numpy": "2.3.4", "PySide6": "6.11.0"},
        scenario_sha256="ab" * 32,
        data_files={"gravity": {"path": "/data/GGM03S.txt", "size_bytes": 1234567, "sha256": "cd" * 32}},
        time_system=time_system.time_scales("2030-01-01T00:00:00"),
        frames=frames.definitions("earth", "IAU_EARTH"), transformations=dict(frames.TRANSFORMATIONS),
        series_frames={"sat-1.position_N": "N"}, central_body="earth",
        central_body_mu_m3_s2=398600436233000.0,  # [m^3/s^2]
        scenario_file="/home/user/sat.json", scenario_file_sha256="ef" * 32,
        effective_defaults={"sat-1.thrusters": {"MinOnTime": 0.02}}, effective_config_note="factory values",
        device_parameters={"rw-1": {"Omega_max": 628.3}}, scenario_file_migrations=[{"from": 3, "to": 4}],
        configuration={"file": None, "overrides": {}})
    return dict(provenance.to_dict(), run_warnings=["step too large"], future_key={"nested": [1, 2]})


def _leaves(value, path=()):
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from _leaves(item, path + (str(key),))
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            yield from _leaves(item, path + (f"[{index}]",))
    else:
        yield path, value


def test_every_recorded_value_is_a_row_in_its_group():
    """Every leaf of the record, however deep, is a row with its value
    in full (no "N entries"); each key is in its group, and a key no group
    names is under Other."""
    from spacemissionstudio.gui.provenance_view import GROUPS, OTHER, provenance_rows, value_text

    record = _record()
    rows = provenance_rows(record)
    by_path = {path: (group, text) for group, path, text in rows}
    assert len(by_path) == len(rows)  # each path once
    for path, value in _leaves(record):
        assert path in by_path, path
        expected = "(none)" if isinstance(value, (dict, list)) else value_text(value)
        assert by_path[path][1] == expected, path
    assert {group for group, _path, _text in rows} == {group for group, _keys in GROUPS} | {OTHER}
    assert by_path[("data_files", "gravity", "sha256")] == ("Data files", "cd" * 32)
    assert by_path[("rng_seeds", "sat-1.css")] == ("Seeds", "271828")
    assert by_path[("time_system",)][0] == "Time scales"
    assert by_path[("central_body_mu_m3_s2",)] == ("Run", "398600436233000.0")
    assert by_path[("integrator_relative_tolerance",)][1] == "1e-10"
    assert by_path[("basilisk_qualified",)][1] == "yes"
    assert by_path[("configuration", "file")][1] == "-"
    assert by_path[("configuration", "overrides")][1] == "(none)"
    assert by_path[("future_key", "nested", "[1]")] == (OTHER, "2")
    assert by_path[("run_warnings", "[0]")] == ("Run", "step too large")
    assert provenance_rows(None) == [] and provenance_rows({}) == []


def test_the_window_shows_the_tree_filters_it_and_copies_the_record(qtbot):
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.provenance_view import ProvenanceDialog, provenance_rows

    record = _record()
    dialog = ProvenanceDialog("Run 3", record)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Provenance of Run 3"
    shown = dialog.rows_shown()
    assert shown == [path for _group, path, _text in provenance_rows(record)]
    dialog.filter.setText("sha256")
    shown = dialog.rows_shown()
    assert ("data_files", "gravity", "sha256") in shown and ("scenario_sha256",) in shown
    assert ("data_files", "gravity") in shown  # the branch leading to a match
    assert ("rng_seed",) not in shown
    dialog.filter.setText("Seeds")  # a group's name keeps its rows
    assert set(dialog.rows_shown()) == {("rng_seed",), ("rng_seeds",), ("rng_seeds", "sat-1.imu"),
                                        ("rng_seeds", "sat-1.css"), ("rng_seed_note",)}
    dialog.filter.clear()
    assert len(dialog.rows_shown()) == len(provenance_rows(record))
    dialog.copy_button.click()
    assert json.loads(QApplication.clipboard().text()) == json.loads(json.dumps(record))

    empty = ProvenanceDialog("Run 4", None)
    qtbot.addWidget(empty)
    assert empty.tree.isHidden() and not empty.empty_label.isHidden() and not empty.copy_button.isEnabled()


def test_the_popover_opens_everything_recorded(qtbot):
    """The Provenance popover's Show everything recorded opens the window
    with the run's record; without a record the button is not offered."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget

    from spacemissionstudio.gui.run_history_view import ProvenancePopover, provenance_text

    holder = QWidget()
    qtbot.addWidget(holder)
    popover = ProvenancePopover(holder)
    record = _record()
    popover.show_text("Provenance of Run 1", provenance_text(record), QPoint(0, 0), record)
    assert popover.all_button.isVisible()
    popover.all_button.click()
    assert popover.dialog is not None and popover.dialog.provenance is record
    assert popover.dialog.windowTitle() == "Provenance of Run 1" and not popover.isVisible()
    popover.dialog.close()
    popover.show_text("Provenance of Run 2", provenance_text(None), QPoint(0, 0), None)
    assert not popover.all_button.isVisible()
    popover.hide()


def test_results_overview_passes_its_runs_record_to_the_popover(qtbot):
    from test_results_overview import _result

    from spacemissionstudio.gui.results_overview import ResultsOverview

    overview = ResultsOverview()
    qtbot.addWidget(overview)
    record = _record()
    with qtbot.waitSignal(overview.summarized, timeout=10000):
        overview.set_run(_result(), "Run 1", provenance=record)
    overview.provenance_button.click()
    assert overview.popover.all_button.isVisible()
    overview.popover.all_button.click()
    assert overview.popover.dialog.provenance is record
    overview.popover.dialog.close()
    overview.wait_for_worker()
