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
"""The regression baseline of the transparency work (docs/transparency_audit.md,
Phase 1a): what every template produces today, as fingerprints, so that a
refactor that moves a number is caught.

For each template, :func:`capture` runs it as ``spacemissionstudio run`` does,
capped at :data:`SPAN_DAYS` of simulated time (a Mission Sequence runs in full),
and records:

- every series: its units, columns, sample count, and per column the first,
  last, least, greatest and mean value and 11 evenly spaced samples;
- the events, the run warnings, the run-summary figures, the Mission Output
  rows and the run's seeds and integrator settings;
- the pre-run Explain text and checks;
- for spacecraft with drag, the lifetime over :data:`LIFETIME_YEARS`, with
  the CLI's default Cd (2.2) and with the spacecraft's own;
- for every spacecraft, the propellant budget after the run, or its refusal;
- for a Monte Carlo template, a batch of :data:`MONTE_CARLO_RUNS` runs.

:func:`compare` reports every difference beyond :data:`RELATIVE_TOLERANCE`
of each quantity's own scale. ``scripts/update_golden_outputs.py`` rewrites
the stored fingerprints; a change of a number needs an entry in
``docs/changes.md``.
"""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import math
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1] / "spacemissionstudio"
TEMPLATES = PACKAGE / "scenarios" / "templates"
GOLDEN = Path(__file__).resolve().parent / "golden"
# The Eros files a user installs (spacemissionstudio small-bodies --fetch);
# template 31 needs them, as conftest.real_small_body_files does.
REAL_SMALL_BODIES_DIR = Path.home() / ".cache" / "SpaceMissionStudio" / "small_bodies"

SPAN_DAYS = 0.25  # [day] longest simulated span of a template run
LIFETIME_YEARS = 1.0  # [year] lifetime look-ahead
MONTE_CARLO_RUNS = 2  # runs of the Monte Carlo batch
MONTE_CARLO_SPAN_DAYS = 0.05  # [day]
SAMPLES = 11  # evenly spaced samples kept per column
RELATIVE_TOLERANCE = 1e-9  # [-] of each quantity's own scale

# Provenance keys that change from machine to machine or run to run.
_VOLATILE_PROVENANCE = {"run_started_utc", "dependency_versions", "data_files", "spacemissionstudio_version",
                        "basilisk_version", "qualified_basilisk_version", "basilisk_is_qualified",
                        "scenario_sha256"}


def template_paths() -> list[Path]:
    return sorted(TEMPLATES.glob("*.json"))


def _number(value):
    value = float(value)
    return value if math.isfinite(value) else repr(value)  # NaN and inf as text, so the JSON stays standard


def _column(values) -> dict:
    values = np.asarray(values, dtype=float).reshape(-1)
    if values.size == 0:
        return {"n": 0}
    finite = values[np.isfinite(values)]
    picks = np.unique(np.linspace(0, values.size - 1, SAMPLES).round().astype(int))
    summary = {"first": _number(values[0]), "last": _number(values[-1]), "samples": [_number(values[i]) for i in picks]}
    if finite.size:
        summary.update(min=_number(finite.min()), max=_number(finite.max()), mean=_number(finite.mean()))
    summary["non_finite"] = int(values.size - finite.size)
    return summary


def _plain(value):
    """``value`` as JSON: dataclasses, arrays, dates and tuples made plain."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, np.ndarray):
        return _column(value) if value.ndim <= 1 else [_column(column) for column in value.T]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (bool, str)) or value is None:
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return _number(value)
    return repr(value)


def _text(value: str) -> str:
    """``value`` with this machine's paths replaced, so text compares across machines."""
    for path, token in ((PACKAGE, "<package>"), (Path.home(), "<home>"), (Path(tempfile.gettempdir()), "<tmp>")):
        value = value.replace(str(path), token)
    return value


def _texts(values) -> list[str]:
    return [_text(str(v)) for v in values]


def _result(result) -> dict:
    from spacemissionstudio.engine import events as event_model
    from spacemissionstudio.engine import run_summary

    series = {}
    for name in sorted(result.series):
        s = result.series[name]
        series[name] = {"units": s.units, "columns": list(s.columns), "time_s": _column(s.time_s),
                        "data": [_column(s.data[:, i]) for i in range(s.data.shape[1])] if s.data.ndim == 2
                        else [_column(s.data)]}
    events = event_model.extract_events(result)
    provenance = result.provenance.to_dict() if result.provenance is not None else {}
    return {
        "series": series,
        "warnings": _texts(result.warnings),
        "events": [_plain(e) for e in events],
        "summary": [_plain(f) for f in run_summary.summarize(result, events)],
        "provenance": {k: _plain(v) for k, v in sorted(provenance.items()) if k not in _VOLATILE_PROVENANCE},
    }


def _capped(scenario):
    from spacemissionstudio.schema.command import runs_sequence

    capped = copy.deepcopy(scenario)
    if not runs_sequence(capped.mission_sequence):
        capped.sim_settings.duration_days = min(capped.sim_settings.duration_days, SPAN_DAYS)
    return capped


def _explain(scenario) -> dict:
    from spacemissionstudio.engine import scenario_checks, scenario_explainer

    return {"explanation": _plain(scenario_explainer.explain(scenario)),
            "warnings": _texts(scenario_checks.scenario_warnings(scenario)),
            "plausibility": _texts(scenario_checks.plausibility_warnings(scenario, base_dir=TEMPLATES)),
            "passes": _texts(scenario_checks.pass_summary(scenario))}


def _lifetimes(scenario) -> dict:
    from spacemissionstudio.engine import lifetime

    out = {}
    for sc in scenario.spacecraft:
        if not sc.enable_drag:
            continue
        for label, drag_coeff in (("cd_2.2", 2.2), ("own_cd", None)):
            try:
                end = lifetime.end_of_life(scenario, sc.name, max_years=LIFETIME_YEARS, drag_coeff=drag_coeff)
                out[f"{sc.name}/{label}"] = _plain(end)
            except Exception as exc:  # noqa: BLE001 -- a refusal is an output too
                out[f"{sc.name}/{label}"] = {"refused": f"{type(exc).__name__}: {_text(str(exc))}"}
    return out


# Templates whose budget is also taken with an Isp set, as most templates
# have no orbit thruster and their budget is refused.
BUDGET_WITH_ISP = {"22_starter_first_leo_satellite": 220.0, "26_earth_observation_data_downlink": 220.0}  # [s]


def _budgets(scenario, result, isp_s: float | None = None) -> dict:
    from spacemissionstudio.engine import propellant_budget

    out = {}
    for sc in scenario.spacecraft:
        budget_scenario = scenario
        if isp_s is not None:
            budget_scenario = copy.deepcopy(scenario)
            from spacemissionstudio.schema.scenario import PropellantBudgetConfig

            target = next(s for s in budget_scenario.spacecraft if s.name == sc.name)
            if target.propellant_budget is None:
                target.propellant_budget = PropellantBudgetConfig()
            target.propellant_budget.isp_s = isp_s
        try:
            out[sc.name] = _plain(propellant_budget.compute_budget(budget_scenario, sc.name, result))
        except Exception as exc:  # noqa: BLE001 -- a refusal is an output too
            out[sc.name] = {"refused": f"{type(exc).__name__}: {_text(str(exc))}"}
    return out


def _monte_carlo(scenario) -> dict:
    from spacemissionstudio.engine import monte_carlo_results
    from spacemissionstudio.engine.monte_carlo import run_monte_carlo

    batch_scenario = copy.deepcopy(scenario)
    batch_scenario.sim_settings.duration_days = min(batch_scenario.sim_settings.duration_days, MONTE_CARLO_SPAN_DAYS)
    batch_scenario.monte_carlo.num_runs = MONTE_CARLO_RUNS
    batch_scenario.monte_carlo.thread_count = 1
    with tempfile.TemporaryDirectory() as folder:
        failed = run_monte_carlo(batch_scenario, batch_scenario.monte_carlo, Path(folder) / "batch")
        batch = monte_carlo_results.load(Path(folder) / "batch")
        names = [sc.name for sc in batch_scenario.spacecraft]
        return {"failed": list(failed),
                "spread": {name: _plain(monte_carlo_results.final_spread(batch, name)) for name in names},
                "runs": _plain(monte_carlo_results.run_table(batch)),
                "summary": _texts(monte_carlo_results.summary_lines(batch))}


@contextlib.contextmanager
def isolated():
    """A home of its own, as tests/conftest.py gives every test: no
    downloaded space weather (the bundled file is used), no installed Earth
    orientation files (IAU_EARTH), and the user's installed Eros files. So
    the fingerprint means the same in a test and in the update script."""
    from spacemissionstudio.engine import earth_orientation, small_bodies, spaceweather

    with tempfile.TemporaryDirectory() as home:
        home = Path(home)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(Path, "home", lambda: home))
            for module, name, value in (
                    (spaceweather, "DEFAULT_CACHE_DIR", home / ".cache" / "SpaceMissionStudio" / "spaceweather"),
                    (earth_orientation, "DEFAULT_DIR", home / ".cache" / "SpaceMissionStudio" / "earth_orientation"),
                    (earth_orientation, "SYSTEM_DIR", home / "share" / "earth_orientation"),
                    (small_bodies, "DEFAULT_DIR", REAL_SMALL_BODIES_DIR),
                    (small_bodies, "SYSTEM_DIR", home / "share" / "small_bodies")):
                stack.enter_context(mock.patch.object(module, name, value))
            yield


def capture(path: Path) -> dict:
    """The fingerprint of the template at ``path`` (see the module docstring)."""
    with isolated():
        return _capture(path)


def _capture(path: Path) -> dict:
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema import load_scenario
    from spacemissionstudio.schema.command import runs_sequence

    scenario = load_scenario(path)
    run = _capped(scenario)
    service = SimulationService(run)
    command_rows = None
    if runs_sequence(run.mission_sequence):
        from spacemissionstudio.engine.mission_engine import MissionEngine

        result, command_summary = MissionEngine(run, service=service).run()
        command_rows = _plain(command_summary)
    else:
        result = service.run()
    fingerprint = {
        "template": path.name,
        "span_days": None if runs_sequence(run.mission_sequence) else run.sim_settings.duration_days,
        "explain": _explain(scenario),
        "run": _result(result),
        "mission_output": command_rows,
        "lifetime": _lifetimes(scenario),
        "budget": _budgets(run, result),
    }
    if path.stem in BUDGET_WITH_ISP:
        fingerprint["budget_with_isp"] = _budgets(run, result, BUDGET_WITH_ISP[path.stem])
    if scenario.monte_carlo.enabled:
        fingerprint["monte_carlo"] = _monte_carlo(scenario)
    return fingerprint


def compare(golden, actual, path: str = "", scale: float | None = None) -> list[str]:
    """Every difference between two fingerprints, as ``path: golden -> actual``.
    Numbers compare within :data:`RELATIVE_TOLERANCE` of ``scale``: the
    greatest magnitude of the quantity they belong to (a column's min and
    max), so a value near zero is held to its column's size."""
    if isinstance(golden, dict) and isinstance(actual, dict):
        if "min" in golden and "max" in golden and isinstance(golden["min"], float):
            scale = max(abs(golden["min"]), abs(golden["max"]), 1e-300)
        problems = []
        for key in sorted(set(golden) | set(actual)):
            if key not in actual:
                problems.append(f"{path}/{key}: missing now")
            elif key not in golden:
                problems.append(f"{path}/{key}: new")
            else:
                problems.extend(compare(golden[key], actual[key], f"{path}/{key}", scale))
        return problems
    if isinstance(golden, list) and isinstance(actual, list):
        if len(golden) != len(actual):
            return [f"{path}: {len(golden)} items -> {len(actual)}"]
        problems = []
        for i, (g, a) in enumerate(zip(golden, actual)):
            problems.extend(compare(g, a, f"{path}[{i}]", scale))
        return problems
    if isinstance(golden, float) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        reference = scale if scale is not None else max(abs(golden), 1e-300)
        if abs(actual - golden) > RELATIVE_TOLERANCE * reference:
            return [f"{path}: {golden!r} -> {actual!r} (difference {abs(actual - golden) / reference:.3g} of its scale)"]
        return []
    if golden != actual:
        return [f"{path}: {golden!r} -> {actual!r}"]
    return []
