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
"""Open data and the Python API (transparency plan, Phase 9): the guide's
examples run as written; the API's functions are the engine's; the run
comparison and the space-weather download on the command line; the
budget's launch-delay sweep and altitude trade written with their
provenance."""

import json
import re
from pathlib import Path

import pytest

from spacemissionstudio import api, cli

_GUIDE = Path(__file__).resolve().parents[1] / "docs" / "api.md"
_STARTER = "22_starter_first_leo_satellite"


def _examples() -> list[str]:
    return re.findall(r"```python\n(.*?)```", _GUIDE.read_text(encoding="utf-8"), re.S)


def test_the_api_names_its_version_and_every_function_in_the_guide():
    """Every name in __all__ is in the guide's table, and the guide has the
    four examples the tests run."""
    guide = _GUIDE.read_text(encoding="utf-8")
    assert api.API_VERSION == 1 and f"`API_VERSION` is {api.API_VERSION}" in guide
    for name in api.__all__:
        if name != "API_VERSION":
            assert f"| `{name}(" in guide, name
    assert len(_examples()) == 4


def test_the_basilisk_free_functions(tmp_path):
    """template, load, validate and assumptions without Basilisk; a missing
    template is a FileNotFoundError naming it."""
    scenario = api.load(api.template(_STARTER))
    assert scenario.spacecraft and api.template(f"{_STARTER}.json") == api.template(_STARTER)
    assert isinstance(api.validate(scenario), list)
    values = api.assumptions(scenario)
    assert values["lifetime.zero_debris_years"] == 5.0 and len(values) > 100
    with pytest.raises(FileNotFoundError, match="no template 'nothing'"):
        api.template("nothing")


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("index", range(4), ids=["run", "assumptions", "analyses", "compare"])
def test_the_guides_examples_run_as_written(index, tmp_path, monkeypatch, capsys):
    """Each example of docs/api.md, in a folder of its own; what it writes
    is there and readable."""
    monkeypatch.chdir(tmp_path)
    exec(compile(_examples()[index], f"{_GUIDE}#example{index + 1}", "exec"), {})  # noqa: S102 -- the guide's code
    out = capsys.readouterr().out
    assert out.strip()
    if index == 0:
        assert (tmp_path / "starter_results" / "provenance.json").is_file()
    if index == 2:
        record = json.loads((tmp_path / "lifetime.json").read_text())
        assert record["kind"] == "lifetime" and record["inputs"]["max_years"] == 5.0
        assert record["inputs"]["forecast_percentile"] == 50.0 and record["provenance"]["scenario_sha256"]
    if index == 3:
        comparison = json.loads((tmp_path / "comparison.json").read_text())
        assert [d["path"] for d in comparison["scenario_differences"]] == ["spacecraft[my-sat].dry_mass_kg"]
        assert comparison["figures"] and all("b_minus_a" in f for f in comparison["figures"])


@pytest.mark.requires_basilisk
def test_runs_are_saved_listed_and_compared_on_the_command_line(tmp_path, capsys):
    """run --save keeps the run in a store; runs lists it; compare prints
    the scenario differences and figures and writes JSON with both runs'
    provenance; an unknown run is an error naming the store."""
    store = tmp_path / "store"
    source = api.load(api.template(_STARTER))
    for index, mass in enumerate((0.0, 10.0)):  # [kg] added to the dry mass
        scenario = api.load(api.template(_STARTER))
        scenario.sim_settings.duration_days = 0.02  # [day]
        scenario.spacecraft[0].dry_mass_kg = source.spacecraft[0].dry_mass_kg + mass
        path = tmp_path / f"s{index}.json"
        scenario.save(path)
        assert cli.main(["run", str(path), "--out-dir", str(tmp_path / f"out{index}"), "--save",
                         "--store", str(store)]) == 0
    assert "saved as run 2" in capsys.readouterr().out
    assert cli.main(["runs", "--store", str(store)]) == 0
    listed = capsys.readouterr().out.splitlines()
    assert len(listed) == 2 and listed[0].split()[0] == "1"
    assert cli.main(["compare", "1", "2", "--store", str(store), "--out", str(tmp_path / "c.json")]) == 0
    out = capsys.readouterr().out
    assert "Scenario differences: 1" in out and "dry_mass_kg" in out and "Figures:" in out
    written = json.loads((tmp_path / "c.json").read_text())
    assert written["a"] == "run 1" and written["provenance"]["a"]["scenario_sha256"]
    assert cli.main(["compare", "1", "7", "--store", str(store)]) == 1
    assert "no saved run 7" in capsys.readouterr().err


def test_the_space_weather_download_is_a_command(monkeypatch, tmp_path, capsys):
    """spaceweather-download fetches CelesTrak's file (always fresh) and
    says where it went; a failure is an error with the reason."""
    from spacemissionstudio.engine import spaceweather

    calls = []

    def fake_fetch(dataset, force=False, **_kwargs):
        calls.append((dataset, force))
        path = tmp_path / f"{dataset}.csv"
        path.write_text("DATE,AP_AVG\n")
        return path

    monkeypatch.setattr(spaceweather, "fetch", fake_fetch)
    assert cli.main(["spaceweather-download"]) == 0
    assert calls == [("SW-All", True)] and "https://celestrak.org/SpaceData/SW-All.csv" in capsys.readouterr().out

    def failing(dataset, force=False, **_kwargs):
        raise spaceweather.SpaceWeatherError("no network")

    monkeypatch.setattr(spaceweather, "fetch", failing)
    assert cli.main(["spaceweather-download", "--dataset", "SW-Last5Years"]) == 1
    assert "ERROR: no network" in capsys.readouterr().err


@pytest.mark.requires_basilisk
def test_the_launch_delay_sweep_is_written_with_its_provenance(tmp_path, monkeypatch):
    """budget --launch-delays --out: every launch date's budget, the worst
    one, the notes and the provenance; the API's record is the same. The
    drag make-up and the re-entry search are the budget tests' stand-ins:
    what is checked here is the record, not the physics."""
    import functools

    from test_propellant_budget import _no_reentry, _StubMakeup

    from spacemissionstudio.engine import propellant_budget as pb

    monkeypatch.setattr(pb, "launch_delay_sweep", functools.partial(
        pb.launch_delay_sweep, reentry_solver=_no_reentry, makeup=_StubMakeup()))
    scenario = api.load(api.template("18_leo_station_keeping"))
    scenario.epoch_utc = "2030-01-01T00:00:00"  # the stand-in's drag is by launch year, 2030 to 2035
    path = tmp_path / "s.json"
    scenario.save(path)
    out = tmp_path / "sweep.json"
    assert cli.main(["budget", str(path), "--launch-delays", "--out", str(out)]) == 0
    record = json.loads(out.read_text())
    assert record["kind"] == "launch_delay_sweep" and len(record["results"]["cases"]) == 6
    assert record["results"]["cases"][0]["rows"] and record["provenance"]["scenario_file"] == "s.json"
    assert record["results"]["worst_launch_utc"] in [case["launch_utc"] for case in record["results"]["cases"]]
    sweep = api.launch_delays(scenario)
    assert len(api.record(scenario, sweep)["results"]["cases"]) == 6
