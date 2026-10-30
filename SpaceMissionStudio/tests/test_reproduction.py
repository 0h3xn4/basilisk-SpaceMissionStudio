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
"""Reproduction bundles (spacemissionstudio.reproduction, transparency
audit Phase 2h): ``run --bundle`` makes a run's folder able to run itself
again, and ``reproduce`` runs it and compares."""

import csv
import json
import math
import shutil

import pytest

from spacemissionstudio import cli, reproduction
from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SimSettings, SpacecraftConfig


def _scenario(path, **spacecraft):
    scenario = Scenario(name="bundle test", epoch_utc="2030-01-01T00:00:00",
                        gravity=GravityConfig(central_body="earth", central_body_degree=0),
                        sim_settings=SimSettings(duration_days=0.01),  # [day]
                        spacecraft=[SpacecraftConfig(name="sat-1", orbit=OrbitIC(
                            type="cartesian", position_km=[6778.0, 0.0, 0.0], velocity_km_s=[0.0, 7.67, 0.0]),
                            **spacecraft)])
    scenario.save(path)
    return scenario


def _write_series(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows([["time_s", "x_m"], *rows])


def test_a_series_is_compared_column_by_column_against_its_scale(tmp_path):
    """The difference of a column is its largest, as a fraction of the
    column's largest magnitude; a series of another shape does not
    compare at all."""
    _write_series(tmp_path / "old.csv", [[0.0, 7.0e6], [10.0, -7.0e6]])
    _write_series(tmp_path / "new.csv", [[0.0, 7.0e6], [10.0, -7.0e6 + 7.0]])
    found = {d.column: d for d in reproduction.compare_series(tmp_path / "old.csv", tmp_path / "new.csv", "s")}
    assert found["time_s"].relative == 0.0
    assert found["x_m"].relative == pytest.approx(1e-6) and found["x_m"].absolute == pytest.approx(7.0)
    _write_series(tmp_path / "short.csv", [[0.0, 7.0e6]])
    shape = reproduction.compare_series(tmp_path / "old.csv", tmp_path / "short.csv", "s")
    assert [d.relative for d in shape] == [math.inf] and "1 of" in shape[0].note


def test_a_folder_that_is_not_a_bundle_or_does_not_match_itself_is_refused(tmp_path):
    """No bundle.json, a copy whose SHA-256 changed: refused before
    anything runs."""
    with pytest.raises(reproduction.BundleError, match="no bundle.json"):
        reproduction.read_manifest(tmp_path)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "w.txt").write_text("changed", encoding="utf-8")
    (tmp_path / "bundle.json").write_text(json.dumps({"format": 1, "inputs": [
        {"role": "space_weather.local_file_path", "reference": "w.txt", "file": "inputs/w.txt",
         "sha256": "0" * 64}]}), encoding="utf-8")
    with pytest.raises(reproduction.BundleError, match="its SHA-256 changed"):
        reproduction.read_manifest(tmp_path)


@pytest.mark.requires_basilisk
def test_a_bundle_runs_again_and_a_changed_result_is_caught(tmp_path, capsys):
    """``run --bundle`` then ``reproduce``: every series agrees, exit 0. A
    value of the bundle changed by 1e-4 is caught (exit 5, the series
    named, with its difference as a fraction of the column's largest
    value); a series missing from the bundle too; an edited scenario is
    refused (exit 1)."""
    path = tmp_path / "s.json"
    _scenario(path)
    bundle = tmp_path / "bundle"
    assert cli.main(["run", str(path), "--out-dir", str(bundle), "--bundle"]) == 0
    assert (bundle / reproduction.MANIFEST).is_file()
    assert cli.main(["reproduce", str(bundle), "--out-dir", str(tmp_path / "again")]) == 0
    assert "REPRODUCED:" in capsys.readouterr().out

    series = bundle / "sat-1.position_N.csv"
    rows = list(csv.reader(series.open(encoding="utf-8")))
    rows[-1][1] = repr(float(rows[-1][1]) * (1.0 + 1e-4))
    with series.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows(rows)
    (bundle / "sat-1.velocity_N.csv").unlink()
    assert cli.main(["reproduce", str(bundle), "--out-dir", str(tmp_path / "third")]) == cli.EXIT_CHECK_FAILED
    out = capsys.readouterr().out
    assert "NOT REPRODUCED" in out
    line = next(text for text in out.splitlines() if "sat-1.position_N [x_m]" in text)
    assert 1e-5 < float(line.split(": ")[1].split(" of scale")[0]) <= 1e-4  # 1e-4 of the last x, less of the largest
    assert "sat-1.velocity_N [*]" in out and "not in the bundle" in out

    as_run = bundle / reproduction.SCENARIO_AS_RUN
    as_run.write_text(as_run.read_text(encoding="utf-8").replace('"bundle test"', '"edited"'), encoding="utf-8")
    assert cli.main(["reproduce", str(bundle), "--out-dir", str(tmp_path / "fourth")]) == 1
    assert "not the scenario the bundle was made from" in capsys.readouterr().err


@pytest.mark.requires_basilisk
def test_a_bundle_carries_the_files_its_scenario_refers_to(tmp_path, capsys):
    """A run on the user's own space-weather file and with a Vizard model
    from a file: the bundle holds copies, and reproduces with the
    originals gone, saying which copies it used."""
    from spacemissionstudio.engine import spaceweather

    weather = tmp_path / "mine" / "my_weather.txt"
    weather.parent.mkdir()
    shutil.copy(spaceweather.BUNDLED_DATA_PATH, weather)
    (tmp_path / "sat.obj").write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    path = tmp_path / "s.json"
    scenario = _scenario(path, enable_drag=True, vizard_model_path="sat.obj")
    scenario.space_weather.source, scenario.space_weather.local_file_path = "local_file", str(weather)
    scenario.save(path)
    bundle = tmp_path / "bundle"
    assert cli.main(["run", str(path), "--out-dir", str(bundle), "--bundle"]) == 0
    manifest = json.loads((bundle / reproduction.MANIFEST).read_text(encoding="utf-8"))
    roles = {entry["role"]: entry["file"] for entry in manifest["inputs"]}
    assert roles["space_weather.local_file_path"] == "inputs/my_weather.txt"
    assert roles["spacecraft[sat-1].vizard_model_path"] == "inputs/sat.obj"
    shutil.rmtree(weather.parent)
    (tmp_path / "sat.obj").unlink()
    capsys.readouterr()
    assert cli.main(["reproduce", str(bundle), "--out-dir", str(tmp_path / "again")]) == 0
    out = capsys.readouterr().out
    assert "REPRODUCED:" in out
    assert "USED: space_weather.local_file_path: the bundle's inputs/my_weather.txt" in out


def test_this_computers_newer_space_weather_is_replaced_by_the_bundles(tmp_path, monkeypatch):
    """The "bundled" source reads the newer of the shipped file and a
    download, so another computer can read another file. When its file
    differs from the one the run read, the bundle's copy is used, and said
    so; when it is the same, nothing is changed."""
    from spacemissionstudio.engine import spaceweather

    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "SW-All.txt").write_text("recorded", encoding="utf-8")
    here = tmp_path / "here.txt"
    here.write_text("newer download", encoding="utf-8")
    monkeypatch.setattr(spaceweather, "real_data_path", lambda *_a, **_k: here)
    manifest = {"inputs": [{"role": "data_files.space_weather", "file": "inputs/SW-All.txt"}]}
    recorded = {"space_weather": {"sha256": reproduction._sha256(tmp_path / "inputs" / "SW-All.txt")}}
    scenario = Scenario(name="s", epoch_utc="2030-01-01T00:00:00", spacecraft=[SpacecraftConfig(
        name="sat-1", orbit=OrbitIC(type="cartesian", position_km=[6778.0, 0.0, 0.0], velocity_km_s=[0.0, 7.67, 0.0]))])
    used: list = []
    reproduction._use_bundled_space_weather(scenario, tmp_path, manifest, recorded, used)
    assert scenario.space_weather.source == "local_file"
    assert scenario.space_weather.local_file_path == str((tmp_path / "inputs" / "SW-All.txt").resolve())
    assert "differs from the one the run read" in used[0]
    same = Scenario.from_dict(json.loads(json.dumps(scenario.to_dict())))
    same.space_weather.source, same.space_weather.local_file_path = "bundled", None
    here.write_text("recorded", encoding="utf-8")
    reproduction._use_bundled_space_weather(same, tmp_path, manifest, recorded, used := [])
    assert same.space_weather.source == "bundled" and used == []
