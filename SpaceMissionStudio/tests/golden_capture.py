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

:func:`compare` reports every difference beyond what two computers can
disagree on (see "How numbers are compared" below).
``scripts/update_golden_outputs.py`` rewrites the stored fingerprints; a
change of a number needs an entry in ``docs/changes.md``.

How numbers are compared
------------------------

The same template, the same Basilisk wheel and the same Python packages do
not give the same last bits on every computer: CI's Linux runners and the
computer that wrote the baseline disagreed on 22 templates, Windows on all
31 (PR #150). What differed, and the rule that follows:

- Every number may differ by :data:`RELATIVE_TOLERANCE` of its quantity's
  scale (a column's greatest magnitude, a figure's own size). Measured on
  well-conditioned outputs: at most 3.8e-7 (a Windows run summary).
- A number near zero, or one that an ill-conditioned calculation gives, may
  also differ by the absolute floor of its unit (:data:`ABSOLUTE_FLOORS`).
  The angles of a circular orbit are the case in point: an arccos near 1
  returns 0 on one computer and 2^-26 = 1.5e-8 rad on another, and the
  argument of periapsis of an orbit with e = 1e-9 moved 1.4e-7 rad.
  Relative orbit elements are lengths made from such angles (a times an
  angle: 0.1 m at 7000 km), so they get their own floor
  (:data:`ANGLE_DERIVED_FLOORS`).
- An angle that wraps (RAAN, argument of periapsis, true anomaly, azimuth,
  longitude) compares modulo 2*pi, and only its first, last and sampled
  values: 0 and 6.283185 rad are one RAAN, and one sample crossing 2*pi
  moves a column's least, greatest and mean values by any amount.
- A sensor's noise comes from Basilisk's GaussMarkov, which draws from
  ``std::normal_distribution``; the C++ standard leaves its algorithm to the
  standard library, so Windows (MSVC) and Linux (libstdc++) draw different
  noise from the same seed. A sensor output (a series or Mission Output
  value under ``sensor.``) is therefore compared value by value only on the
  standard library that recorded it (``rng_library`` in the fingerprint);
  elsewhere only its sample count and its non-finite count are. A
  spacecraft whose attitude loop closes through such sensors carries the
  other noise into its actuators (reaction-wheel speeds, magnetorquer
  dipoles: up to 4.8e-6 of their scale on Windows), so on another standard
  library a template with sensors is held to
  :data:`CROSS_LIBRARY_RELATIVE_TOLERANCE` instead.

Anything else must match exactly: texts, counts, events, warnings, keys.
A change smaller than these tolerances is not caught; it is still a change,
and ``docs/changes.md`` still needs it.
"""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import math
import re
import sys
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
RELATIVE_TOLERANCE = 1e-6  # [-] of each quantity's own scale
# For a template with sensors, run on another C++ standard library than the
# one that recorded it (module docstring): 4.8e-6 measured.
CROSS_LIBRARY_RELATIVE_TOLERANCE = 1e-4  # [-]

# Absolute floors by unit, each about ten times the largest last-bit
# difference measured across Linux and Windows (module docstring).
ABSOLUTE_FLOORS = {
    "rad": 1e-6,  # [rad] ill-defined angles of near-circular orbits: 1.4e-7 measured
    "deg": math.degrees(1e-6),  # [deg] the same angle floor
    "rad/s": 1e-12,  # [rad/s] body rates that should be zero: 2e-20 measured
    "m/s^2": 1e-9,  # [m/s^2] accelerations that should be zero: 2e-13 measured
    "-": 1e-12,  # [-] eccentricities of circular orbits: 2e-15 measured
    "km": 1e-6,  # [km] the mean semi-major axis change, a difference of two means of 7000 km: 5e-11 measured
    "N*m": 1e-12,  # [N*m]
}
# Relative orbit elements are a (semi-major axis) times angle differences, so
# they inherit the angles' last-bit noise: 0.103 m measured at 7000 km.
ANGLE_DERIVED_FLOORS = {"roe_formation.roe": 1.0, "roe_formation.roe_error": 1.0,  # [m]
                        "roe_formation.min_rn_separation": 1.0}  # [m] from the same elements
# Columns (or whole series) that hold angles that wrap at 2*pi.
WRAPPING_COLUMNS = {"argp", "raan", "true_anomaly", "azimuth"}
WRAPPING_SERIES = {"geo_station_keeping.longitude"}


def rng_library() -> str:
    """The C++ standard library whose ``std::normal_distribution`` Basilisk's
    noise uses on this platform (module docstring)."""
    return {"win32": "msvc", "darwin": "libc++"}.get(sys.platform, "libstdc++")

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
        "rng_library": rng_library(),
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


@dataclasses.dataclass(frozen=True)
class _Rule:
    """How the numbers under a part of a fingerprint compare."""

    scale: float | None = None  # greatest magnitude of the quantity, None for a number on its own
    relative: float = RELATIVE_TOLERANCE  # [-] of the scale
    floor: float = 0.0  # absolute floor of its unit
    wraps: bool = False  # an angle that wraps at 2*pi [rad] or 360 [deg]
    period: float = 2.0 * math.pi
    noise_only_shape: bool = False  # a sensor output recorded on another standard library


def _unit_of_header(header: str) -> str:
    """"sat-1 inclination [deg]" -> "deg"; "" without one."""
    match = re.search(r"\[([^\]]+)\]\s*$", header)
    return match.group(1) if match else ""


def _series_rule(name: str, series: dict, column: str, other_library: bool, base: _Rule) -> _Rule:
    kind = name.split(".", 1)[1] if "." in name else name
    units = series.get("units", "")
    floor = ANGLE_DERIVED_FLOORS.get(kind, ABSOLUTE_FLOORS.get(units, 0.0))
    wraps = units in ("rad", "deg") and (column in WRAPPING_COLUMNS or kind in WRAPPING_SERIES)
    return dataclasses.replace(base, floor=floor, wraps=wraps, period=360.0 if units == "deg" else 2.0 * math.pi,
                               noise_only_shape=other_library and ".sensor." in f".{kind}")


def compare(golden, actual, path: str = "", rule: _Rule | None = None) -> list[str]:
    """Every difference between two fingerprints, as ``path: golden -> actual``,
    beyond what two computers can disagree on (module docstring)."""
    if rule is None and isinstance(golden, dict) and "template" in golden:
        other_library = golden.get("rng_library", "libstdc++") != rng_library()
        has_sensors = any(".sensor." in f".{name}" for name in golden.get("run", {}).get("series", {}))
        base = _Rule(relative=CROSS_LIBRARY_RELATIVE_TOLERANCE if other_library and has_sensors
                     else RELATIVE_TOLERANCE)
        problems = []
        for key in sorted(set(golden) | set(actual)):
            if key == "rng_library":
                continue
            if key not in actual or key not in golden:
                problems.append(f"{path}/{key}: {'missing now' if key not in actual else 'new'}")
            elif key == "run":
                problems.extend(_compare_run(golden[key], actual[key], f"{path}/run", other_library, base))
            elif key == "mission_output":
                problems.extend(_compare_mission_output(golden[key], actual[key], f"{path}/{key}", other_library,
                                                        base))
            elif key == "monte_carlo":
                problems.extend(_compare_monte_carlo(golden[key], actual[key], f"{path}/{key}", base))
            else:
                problems.extend(compare(golden[key], actual[key], f"{path}/{key}", base))
        return problems
    rule = rule or _Rule()
    if isinstance(golden, dict) and isinstance(actual, dict):
        if "min" in golden and "max" in golden and isinstance(golden["min"], float):
            rule = dataclasses.replace(rule, scale=max(abs(golden["min"]), abs(golden["max"]), 1e-300))
        problems = []
        for key in sorted(set(golden) | set(actual)):
            if key not in actual:
                problems.append(f"{path}/{key}: missing now")
            elif key not in golden:
                problems.append(f"{path}/{key}: new")
            elif rule.noise_only_shape and key not in ("n", "non_finite"):
                continue
            elif rule.wraps and key in ("min", "max", "mean"):
                continue
            else:
                problems.extend(compare(golden[key], actual[key], f"{path}/{key}", rule))
        return problems
    if isinstance(golden, list) and isinstance(actual, list):
        if len(golden) != len(actual):
            return [f"{path}: {len(golden)} items -> {len(actual)}"]
        problems = []
        for i, (g, a) in enumerate(zip(golden, actual)):
            problems.extend(compare(g, a, f"{path}[{i}]", rule))
        return problems
    if isinstance(golden, float) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        difference = abs(actual - golden)
        if rule.wraps:
            difference = difference % rule.period
            difference = min(difference, rule.period - difference)
        reference = rule.scale if rule.scale is not None else max(abs(golden), 1e-300)
        if difference > max(rule.relative * reference, rule.floor):
            return [f"{path}: {golden!r} -> {actual!r} (difference {difference / reference:.3g} of its scale)"]
        return []
    if golden != actual:
        return [f"{path}: {golden!r} -> {actual!r}"]
    return []


def _compare_run(golden: dict, actual: dict, path: str, other_library: bool, base: _Rule) -> list[str]:
    problems = []
    for key in sorted(set(golden) | set(actual)):
        if key not in actual or key not in golden:
            problems.append(f"{path}/{key}: {'missing now' if key not in actual else 'new'}")
        elif key == "series":
            problems.extend(_compare_series(golden[key], actual[key], f"{path}/{key}", other_library, base))
        elif key == "summary":
            problems.extend(_compare_figures(golden[key], actual[key], f"{path}/{key}", base))
        else:
            problems.extend(compare(golden[key], actual[key], f"{path}/{key}", base))
    return problems


def _compare_series(golden: dict, actual: dict, path: str, other_library: bool, base: _Rule) -> list[str]:
    problems = []
    for name in sorted(set(golden) | set(actual)):
        where = f"{path}/{name}"
        if name not in actual or name not in golden:
            problems.append(f"{where}: {'missing now' if name not in actual else 'new'}")
            continue
        g, a = golden[name], actual[name]
        for key in sorted(set(g) | set(a)):
            if key not in a or key not in g:
                problems.append(f"{where}/{key}: {'missing now' if key not in a else 'new'}")
            elif key == "data" and isinstance(g[key], list) and isinstance(a[key], list) and len(g[key]) == len(a[key]):
                columns = g.get("columns") or [""] * len(g[key])
                for i, (gc, ac) in enumerate(zip(g[key], a[key])):
                    column = columns[i] if i < len(columns) else ""
                    problems.extend(compare(gc, ac, f"{where}/data[{i}]",
                                            _series_rule(name, g, column, other_library, base)))
            else:
                problems.extend(compare(g[key], a[key], f"{where}/{key}", base))
    return problems


def _compare_figures(golden: list, actual: list, path: str, base: _Rule) -> list[str]:
    """Run-summary figures: each value held to its unit's floor."""
    if len(golden) != len(actual):
        return [f"{path}: {len(golden)} items -> {len(actual)}"]
    problems = []
    for i, (g, a) in enumerate(zip(golden, actual)):
        unit = g.get("unit", "") if isinstance(g, dict) else ""
        problems.extend(compare(g, a, f"{path}[{i}]", dataclasses.replace(base, floor=ABSOLUTE_FLOORS.get(unit, 0.0))))
    return problems


def _compare_mission_output(golden, actual, path: str, other_library: bool, base: _Rule) -> list[str]:
    """Mission Output rows: a reported value under ``sensor.`` follows the
    sensor rule (module docstring)."""
    if not (isinstance(golden, dict) and isinstance(actual, dict)):
        return compare(golden, actual, path, base)
    problems = []
    for key in sorted(set(golden) | set(actual)):
        if key not in actual or key not in golden:
            problems.append(f"{path}/{key}: {'missing now' if key not in actual else 'new'}")
        elif key == "reports" and isinstance(golden[key], list) and isinstance(actual[key], list) \
                and len(golden[key]) == len(actual[key]):
            for i, (g, a) in enumerate(zip(golden[key], actual[key])):
                for field in sorted(set(g) | set(a)):
                    where = f"{path}/reports[{i}]/{field}"
                    if field not in a or field not in g:
                        problems.append(f"{where}: {'missing now' if field not in a else 'new'}")
                    elif field == "values" and isinstance(g[field], dict) and isinstance(a[field], dict):
                        for name in sorted(set(g[field]) | set(a[field])):
                            if name not in a[field] or name not in g[field]:
                                problems.append(f"{where}/{name}: {'missing now' if name not in a[field] else 'new'}")
                                continue
                            noisy = other_library and ".sensor." in f".{name}"
                            problems.extend(compare(g[field][name], a[field][name], f"{where}/{name}",
                                                    dataclasses.replace(base, noise_only_shape=noisy)))
                    else:
                        problems.extend(compare(g[field], a[field], where, base))
        else:
            problems.extend(compare(golden[key], actual[key], f"{path}/{key}", base))
    return problems


def _compare_monte_carlo(golden: dict, actual: dict, path: str, base: _Rule) -> list[str]:
    """The batch: each column of the run table held to the floor of the unit
    in its header ("sat-1 inclination [deg]")."""
    problems = []
    for key in sorted(set(golden) | set(actual)):
        if key not in actual or key not in golden:
            problems.append(f"{path}/{key}: {'missing now' if key not in actual else 'new'}")
        elif key == "runs" and len(golden[key]) == 2 == len(actual[key]):
            headers, rows = golden[key]
            problems.extend(compare(headers, actual[key][0], f"{path}/runs[0]", base))
            if len(rows) != len(actual[key][1]):
                problems.append(f"{path}/runs[1]: {len(rows)} items -> {len(actual[key][1])}")
                continue
            for r, (g_row, a_row) in enumerate(zip(rows, actual[key][1])):
                if len(g_row) != len(a_row):
                    problems.append(f"{path}/runs[1][{r}]: {len(g_row)} items -> {len(a_row)}")
                    continue
                for c, (g, a) in enumerate(zip(g_row, a_row)):
                    unit = _unit_of_header(headers[c]) if c < len(headers) else ""
                    problems.extend(compare(g, a, f"{path}/runs[1][{r}][{c}]",
                                            dataclasses.replace(base, floor=ABSOLUTE_FLOORS.get(unit, 0.0))))
        else:
            problems.extend(compare(golden[key], actual[key], f"{path}/{key}", base))
    return problems
