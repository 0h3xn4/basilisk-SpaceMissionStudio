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
"""Runs saved to disk for comparison (docs/ux-audit.md U-33, decision 5):
the store (engine.run_store) and the run history built on it."""

import json
from datetime import datetime

import numpy as np
import pytest

from spacemissionstudio.engine import run_store
from spacemissionstudio.engine.results import ResultSet, RunProvenance, TimeSeries
from spacemissionstudio.gui.run_history import RunHistory

_T = np.arange(0.0, 600.0, 60.0)  # [s]
_WHEN = datetime(2026, 10, 13, 12, 19, 5)


def _result(offset_m=0.0):
    result = ResultSet("demo", provenance=RunProvenance("test", "2.12.0", "2026-10-13T12:00:00+00:00", "rk4", 1.0),
                       warnings=["a warning"])
    result.add(TimeSeries("sat.position_N", _T, ("x", "y", "z"), np.column_stack([_T + offset_m, _T, -_T]), "m"))
    result.add(TimeSeries("sat.eclipse.illumination_factor", _T, ("illumination_factor",), np.ones(_T.size)))
    return result


def test_a_saved_run_reads_back_unchanged(tmp_path):
    """Every series, column, unit, the provenance, warnings and inputs."""
    saved = run_store.save(tmp_path, 7, {"name": "demo", "x": [1, 2]}, _result(5.0), "2030-01-01T00:00:00", _WHEN)
    assert saved.run_id == "run-0007-20261013T121905" and saved.size_bytes > 0
    (index,) = run_store.load_index(tmp_path)
    assert (index.number, index.scenario, index.epoch_utc, index.finished) == (7, {"name": "demo", "x": [1, 2]},
                                                                              "2030-01-01T00:00:00", _WHEN)
    back = run_store.load_result(tmp_path, index)
    original = _result(5.0)
    assert list(back.series) == list(original.series)
    for name, series in original.series.items():
        assert back.series[name].columns == tuple(series.columns) and back.series[name].units == series.units
        assert np.array_equal(back.series[name].data, series.data)
        assert np.array_equal(back.series[name].time_s, series.time_s)
    assert back.provenance == original.provenance and back.warnings == ["a warning"]
    assert not list(tmp_path.glob(".*partial"))  # written in place by a rename


def test_unreadable_runs_are_skipped_and_names_outside_the_store_refused(tmp_path):
    """An edited run.json, a newer format, a stray folder: skipped, not half loaded."""
    run_store.save(tmp_path, 1, {"name": "good"}, _result(), "", _WHEN)
    broken = run_store.save(tmp_path, 2, {"name": "broken"}, _result(), "", _WHEN)
    (tmp_path / broken.run_id / "run.json").write_text("{not json", encoding="utf-8")
    newer = run_store.save(tmp_path, 3, {"name": "newer"}, _result(), "", _WHEN)
    record = json.loads((tmp_path / newer.run_id / "run.json").read_text(encoding="utf-8"))
    record["format_version"] = 99
    (tmp_path / newer.run_id / "run.json").write_text(json.dumps(record), encoding="utf-8")
    (tmp_path / "notes").mkdir()
    assert [r.scenario_name for r in run_store.load_index(tmp_path)] == ["good"]
    with pytest.raises(run_store.RunStoreError):
        run_store.delete(tmp_path, "../elsewhere")
    truncated = run_store.save(tmp_path, 4, {"name": "truncated"}, _result(), "", _WHEN)
    (tmp_path / truncated.run_id / "series.npz").write_bytes(b"PK\x03\x04")
    with pytest.raises(run_store.RunStoreError):
        run_store.load_result(tmp_path, truncated)


def test_prune_keeps_the_newest_runs_within_the_limits(tmp_path):
    for number in range(1, 6):
        run_store.save(tmp_path, number, {"name": f"s{number}"}, _result(), "", _WHEN)
    assert run_store.prune(tmp_path, keep=3) == ["run-0001-20261013T121905", "run-0002-20261013T121905"]
    assert [r.number for r in run_store.load_index(tmp_path)] == [3, 4, 5]
    run_store.prune(tmp_path, keep=10, max_bytes=1)  # [byte] too small for any: the newest stays
    assert [r.number for r in run_store.load_index(tmp_path)] == [5]


def test_the_history_lists_earlier_sessions_and_numbers_on(tmp_path):
    """A new session sees yesterday's runs, named with their date, and
    reads their series only when asked; numbering continues."""
    first = RunHistory(store_root=tmp_path)
    first.add({"name": "demo"}, _result(), "", finished=_WHEN)
    first.add({"name": "demo"}, _result(500.0), "", finished=_WHEN)
    later = RunHistory(store_root=tmp_path)
    assert [r.number for r in later.runs] == [1, 2] and later.next_number == 3
    old = later.find(2)
    assert old.name == "Run 2, 13 Oct 12:19" and not old.in_memory
    assert old.result.series["sat.position_N"].data[0, 0] == 500.0  # [m] read back on first use
    new = later.add({"name": "demo"}, _result(), "", finished=datetime(2026, 10, 14, 9, 0))
    assert new.number == 3 and new.name == "Run 3, 09:00" and new.saved is not None
    later.delete(later.find(1))
    assert [r.number for r in RunHistory(store_root=tmp_path).runs] == [2, 3]


def test_only_the_last_runs_keep_their_series_in_memory(tmp_path):
    history = RunHistory(max_runs=2, store_root=tmp_path)
    for _ in range(4):
        history.add({"name": "demo"}, _result(), "", finished=_WHEN)
    assert [r.in_memory for r in history.runs] == [False, False, True, True]
    assert history.runs[0].result is not None  # still on disk


def test_a_store_that_cannot_be_written_keeps_the_run_in_memory(tmp_path):
    blocked = tmp_path / "file"
    blocked.write_text("not a folder", encoding="utf-8")
    history = RunHistory(store_root=blocked)
    record = history.add({"name": "demo"}, _result(), "", finished=_WHEN)
    assert record.saved is None and record.result is not None
    assert "could not save run 1" in history.last_save_error
