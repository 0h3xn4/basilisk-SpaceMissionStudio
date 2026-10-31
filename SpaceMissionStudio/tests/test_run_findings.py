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
"""Structured warnings of a run (engine.findings, the transparency plan's
Phase 5a): each warning a run, a long run or a lifetime estimate gives
names its rule, reads as the text it always was, and keeps its rule when
the run is saved and read back."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np

from spacemissionstudio import cli, dependencies
from spacemissionstudio.engine import earth_orientation, run_store
from spacemissionstudio.engine import environment_models as env
from spacemissionstudio.engine import spaceweather as sw
from spacemissionstudio.engine.findings import RULES, Finding, explanation_lines
from spacemissionstudio.engine.results import ResultSet, RunProvenance, TimeSeries, conservation_drift_warnings

_PACKAGE = Path(cli.__file__).resolve().parent
# Every module whose warnings reach a run's or a lifetime estimate's result.
_RUN_SOURCES = ("engine/service.py", "engine/long_run.py", "engine/results.py", "engine/spaceweather.py",
                "engine/environment_models.py", "engine/earth_orientation.py", "engine/lifetime.py",
                "dependencies.py")
_EARTH_MU = 3.986004418e14  # [m^3/s^2]


def test_no_warning_of_a_run_is_a_plain_string():
    """Each warning a run's modules append is a Finding, and every rule for
    a run's warnings is used by one of them."""
    used = set()
    for name in _RUN_SOURCES:
        source = (_PACKAGE / name).read_text(encoding="utf-8")
        assert not re.search(r'warnings\.(append|insert)\((0, )?f?"', source), name
        assert not re.search(r"warnings=\[f?\"", source), name
        used |= set(re.findall(r'"([a-z_]+\.[a-z_]+)"(?=[),])', source)) & set(RULES)
    run_rules = {r for r in RULES if r.split(".")[0] in ("run", "lifetime", "magnetic_field", "data")}
    run_rules |= {"space_weather.daily_forecast", "space_weather.monthly_forecast", "space_weather.msfc_prediction",
                  "space_weather.msfc_repeated"}
    assert run_rules <= used


def test_a_drift_warning_carries_the_drift_and_its_tolerance():
    """The conservation check's warnings: the text as before, the drift
    found, the tolerance and the parameter that sets it."""
    omega = np.sqrt(_EARTH_MU / 7.0e6 ** 3)  # [rad/s]
    t = np.linspace(0.0, 2.0 * np.pi / omega, 200)  # [s]
    r = 7.0e6 * np.column_stack([np.cos(omega * t), np.sin(omega * t), np.zeros_like(t)])  # [m]
    v = 7.0e6 * omega * np.column_stack([-np.sin(omega * t), np.cos(omega * t), np.zeros_like(t)])  # [m/s]
    warnings = conservation_drift_warnings("sat-1", _EARTH_MU, r, v * np.linspace(1.0, 1.1, t.size)[:, None])
    energy, momentum = warnings
    assert energy.startswith("sat-1: orbital energy drifted ") and energy.rule_id == "run.energy_drift"
    assert momentum.rule_id == "run.momentum_drift" and momentum.limit == "1%"
    assert f"(limit {momentum.limit})" in momentum and f"drifted {momentum.actual} " in momentum
    assert energy.rule.parameter == "dynamics.conservation_tolerance"


def test_the_environment_and_data_warnings_name_their_rules(tmp_path):
    """Earth orientation, the magnetic model, a changed data file and the
    space-weather sources read: each warning names its rule."""
    (none,) = earth_orientation.notes(datetime(2030, 1, 1), datetime(2030, 1, 2), [])
    assert none == "Earth orientation: IAU rotation model, no IERS data installed"
    assert none.rule_id == "earth_orientation.none"
    cof = tmp_path / "WMM2025.COF"
    cof.write_text("    2025.0            WMM-2025     11/13/2024\n")
    (wmm,) = env.wmm_validity_warnings("2029-12-15T00:00:00", 30.0, cof)
    assert (wmm.rule_id, wmm.limit) == ("magnetic_field.wmm_validity", "2025.0 to 2030.0")
    kernel = tmp_path / "earth_latest_high_prec.bpc"
    kernel.write_bytes(b"orientation")
    changed = dependencies.installed_file_record(kernel, hashlib.sha256(b"other").hexdigest())
    (data,) = dependencies.changed_since_install({"earth_orientation:a": changed})
    assert data.rule_id == "data.changed_since_install" and "is not the file installed" in data
    resolved = sw.resolve("bundled", datetime(2041, 6, 1), datetime(2045, 1, 1), cache_dir=tmp_path)
    by_rule = {w.rule_id: w for w in resolved.warnings}
    repeat = by_rule["space_weather.msfc_repeated"]
    assert repeat == "past 2041-10 MSFC's last 132 months repeat (ESA AD10 Sec. 5.9)"
    assert (repeat.actual, repeat.limit) == ("after 2041-10", "132 months repeat")
    assert by_rule["space_weather.msfc_prediction"].actual == "50th percentile"


def _result(warnings):
    result = ResultSet("demo", provenance=RunProvenance("test", "2.12.0", "2026-10-13T12:00:00+00:00", "rk4", 1.0),
                       warnings=warnings)
    t = np.arange(0.0, 600.0, 60.0)  # [s]
    result.add(TimeSeries("sat.position_N", t, ("x", "y", "z"), np.column_stack([t, t, -t]), "m"))
    return result


def test_a_saved_run_keeps_its_warnings_rules(tmp_path):
    """run.json keeps the warnings' text as before and, beside it, each
    one's rule; a run saved before rules, or with a rule this version does
    not know, reads back as the text."""
    drift = Finding("sat: orbital energy drifted 2.0% (limit 1%) -- try a smaller dynamics step",
                    "run.energy_drift", actual="2.0%", limit="1%")
    saved = run_store.save(tmp_path, 1, {"name": "demo"}, _result([drift, "a plain warning"]),
                           "2030-01-01T00:00:00", datetime(2026, 10, 13, 12, 19, 5))
    record_path = tmp_path / saved.run_id / "run.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["warnings"] == [str(drift), "a plain warning"]
    (back,) = run_store.load_index(tmp_path)
    first, second = run_store.load_result(tmp_path, back).warnings
    assert (first, first.rule_id, first.actual, first.limit) == (drift, "run.energy_drift", "2.0%", "1%")
    assert second == "a plain warning" and not isinstance(second, Finding)
    record["warning_rules"][0]["rule_id"] = "no.such_rule"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    (back,) = run_store.load_index(tmp_path)
    assert not isinstance(back.warnings[0], Finding) and back.warnings[0] == drift
    del record["warning_rules"]
    record_path.write_text(json.dumps(record), encoding="utf-8")
    (back,) = run_store.load_index(tmp_path)
    assert back.warnings == [str(drift), "a plain warning"]


def test_explain_prints_a_run_warnings_rule(capsys):
    """``run --explain`` and ``lifetime --explain`` follow each warning
    with its rule on stderr; without it the warnings are as before."""
    drift = Finding("sat: angular momentum drifted 3.0% (limit 1%)", "run.momentum_drift", actual="3.0%",
                    limit="1%")
    cli._print_run_warnings([drift, "a plain warning"], explain=False)
    assert capsys.readouterr().err == f"WARNING: {drift}\nWARNING: a plain warning\n"
    cli._print_run_warnings([drift, "a plain warning"], explain=True)
    err = capsys.readouterr().err.splitlines()
    assert err == [f"WARNING: {drift}", *(f"  {line}" for line in explanation_lines(drift)),
                   "WARNING: a plain warning"]
    assert "  found 3.0%; limit 1%" in err and any("dynamics.conservation_tolerance" in line for line in err)
