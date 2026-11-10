#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""SpaceMissionStudio's Python API (the transparency plan, Phase 9b).

The functions here are the stable way to script SpaceMissionStudio: load
and check a scenario, run it, and compute what the app computes from it.
They are the same engine the app and the command line use, so a number
from a script is the number the app shows. ``docs/api.md`` is the
reference, with examples the tests run.

Stability: everything named in :data:`__all__` keeps its name, arguments
and meaning within an :data:`API_VERSION`; a change that breaks a script
raises the version and is listed in the changelog. The objects returned
(``Scenario``, ``ResultSet``, ``EndOfLife``, ``Budget``) are the engine's
own; their documented fields are part of the API, their underscored ones
are not.

Records: :func:`record` turns a lifetime, a budget, a sweep or a trade
into the JSON record the command line's ``--out`` writes (inputs, model,
results with their calculation traces, provenance), and :func:`write`
saves one.

Without Basilisk only :func:`load`, :func:`validate`, :func:`assumptions`,
:func:`compare` and :func:`design_checks` work; the others raise
``ImportError``.
"""

from __future__ import annotations

from pathlib import Path

API_VERSION = 1

__all__ = ["API_VERSION", "template", "load", "validate", "assumptions", "run", "summary", "lifetime", "budget",
           "launch_delays", "altitude_trade", "monte_carlo", "compare", "design_checks", "model_analyses", "reentry", "record", "write"]


def template(name: str) -> Path:
    """The path of a template shipped with SpaceMissionStudio, by its file
    name with or without ``.json`` (``"22_starter_first_leo_satellite"``).

    :raises FileNotFoundError: no such template.
    """
    folder = Path(__file__).resolve().parent / "scenarios" / "templates"
    path = folder / (name if name.endswith(".json") else f"{name}.json")
    if not path.is_file():
        raise FileNotFoundError(f"no template {name!r} in {folder}")
    return path


def load(path) -> object:
    """The scenario in the file at ``path`` (a ``schema.scenario.Scenario``),
    validated, with its project configuration file attached.

    :param path: a scenario JSON file.
    :raises ScenarioValidationError: the file cannot be read or is not a
        valid scenario; the message names the field.
    """
    from .schema import load_scenario

    return load_scenario(Path(path))


def validate(scenario) -> list[str]:
    """Check ``scenario`` and return the pre-run warnings (the app's "to
    check": each a ``engine.findings.Finding`` with its rule id).

    :raises ScenarioValidationError: the scenario cannot run as it is.
    """
    from .engine.scenario_checks import scenario_warnings

    scenario.validate()
    return scenario_warnings(scenario)


def assumptions(scenario=None) -> dict:
    """Every named parameter (the rules, margins and models the analyses
    use) with the value in effect for ``scenario``: ``{name: value}``.
    ``config.registry`` gives each one's unit, source and rationale."""
    from .config import registry

    return {parameter.name: registry.value(parameter.name, scenario) for parameter in registry.parameters()}


def run(scenario, out_dir=None, allow_scripts: bool = False):
    """Run ``scenario`` (its Mission Sequence when it has one) and return the
    results (``engine.results.ResultSet``, with ``provenance`` and
    ``warnings``). With ``out_dir``, also write one CSV per series and
    ``provenance.json`` there, as ``spacemissionstudio run`` does.

    :param allow_scripts: run the scenario's script blocks (they are Python
        code from the scenario file: only for files you trust).
    """
    from .engine.service import SimulationService
    from .schema.command import runs_sequence

    service = SimulationService(scenario)
    if runs_sequence(scenario.mission_sequence):
        from .engine.mission_engine import MissionEngine

        result, _summary = MissionEngine(scenario, service=service, allow_scripts=allow_scripts).run()
    else:
        result = service.run()
    if out_dir is not None:
        result.export_csv(out_dir)
    return result


def summary(result) -> list:
    """The run's headline figures (Results > Overview): a list of
    ``engine.run_summary.Figure`` with ``label``, ``value``, ``unit`` and
    ``trace``, how it was computed."""
    from .engine import events, run_summary

    return run_summary.summarize(result, events.extract_events(result))


def _spacecraft(scenario, name):
    return name or scenario.spacecraft[0].name


def lifetime(scenario, spacecraft: str | None = None, result=None, **options):
    """The orbital lifetime (End of Life): ``engine.lifetime.EndOfLife``,
    with ``lifetime.reentry_utc``, the disposal rules and ``traces``.

    :param spacecraft: its name (default: the first).
    :param result: a run's results: start from its end, with the
        propellant left; None: from the scenario's start.
    :param options: ``engine.lifetime.end_of_life``'s: ``deorbit_perigee_km``,
        ``max_years``, ``forecast_percentile``, ``drag_coeff``,
        ``propellant_kg``.
    """
    from .engine import lifetime as engine_lifetime

    return engine_lifetime.end_of_life(scenario, _spacecraft(scenario, spacecraft), result, **options)


def budget(scenario, spacecraft: str | None = None, result=None):
    """The delta-V and propellant budget (ESA AD10): ``engine.propellant_budget.Budget``,
    its ``rows``, totals, notes and ``traces``. ``result``: the run whose
    orbit control and formation keeping it takes."""
    from .engine import propellant_budget

    return propellant_budget.compute_budget(scenario, _spacecraft(scenario, spacecraft), result)


def launch_delays(scenario, spacecraft: str | None = None, result=None):
    """The budget for the planned launch and up to five years late (AD10
    Sec. 5.5): ``engine.propellant_budget.LaunchDelaySweep``, its ``cases``
    and the ``worst``."""
    from .engine import propellant_budget

    return propellant_budget.launch_delay_sweep(scenario, _spacecraft(scenario, spacecraft), result)


def altitude_trade(scenario, spacecraft: str | None = None, altitudes_km=None, result=None):
    """The launch-delay sweep at each altitude [km] (default: five around
    the spacecraft's own), against the tank:
    ``engine.propellant_budget.AltitudeTrade``."""
    from .engine import propellant_budget

    return propellant_budget.altitude_trade(scenario, _spacecraft(scenario, spacecraft), altitudes_km, result)


def monte_carlo(scenario, archive_dir, allow_scripts: bool = False, overwrite: bool = False):
    """Run the scenario's Monte Carlo batch into ``archive_dir`` and return
    its results (``engine.monte_carlo_results.MonteCarloBatch``: each run's
    end state, the spread with its statistic); the folder also holds the
    batch's provenance, ``archive.provenance.json``.

    :raises MonteCarloError: the scenario has no batch, or it cannot run.
    """
    from .engine import monte_carlo_results
    from .engine.monte_carlo import MonteCarloError, run_monte_carlo

    if scenario.monte_carlo is None:
        raise MonteCarloError("the scenario has no Monte Carlo batch (monte_carlo)")
    run_monte_carlo(scenario, scenario.monte_carlo, archive_dir, allow_scripts=allow_scripts, overwrite=overwrite)
    return monte_carlo_results.load(archive_dir)


def compare(a_scenario, a_result, b_scenario, b_result):
    """Two runs side by side (Results > Compare):
    ``engine.run_comparison.Comparison`` with the scenario differences,
    the headline figures and the events; ``.to_dict()`` for JSON. Each
    scenario is a ``Scenario`` or its ``to_dict()``."""
    from .engine import run_comparison

    def as_dict(scenario):
        return scenario if isinstance(scenario, dict) else scenario.to_dict()

    return run_comparison.compare(as_dict(a_scenario), a_result, as_dict(b_scenario), b_result)


def design_checks(scenario, spacecraft: str | None = None, samples: int | None = None, base_dir=None):
    """The static design checks of a spacecraft's 3D model:
    ``analyses.design_checks.DesignReport`` with ``fov`` (field-of-view
    obstruction), ``authority`` (thruster torque arms and authority),
    ``plumes``, ``mass`` (the mass budget with maturity margins) and
    ``launcher`` (the stowed configuration against the envelope), and
    ``findings()``. Needs no Basilisk.

    :param samples: rays per cone (default: the spacecraft's
        ``model_analyses.samples``, else 256).
    :param base_dir: the folder relative mesh paths are read from (the
        scenario file's).
    """
    from .analyses import common, design_checks as checks

    return checks.design_checks(common.spacecraft(scenario, spacecraft), samples=samples, base_dir=base_dir)


def model_analyses(scenario, result, spacecraft: str | None = None, base_dir=None):
    """A run's model analyses for a spacecraft with ``model_analyses`` set:
    ``analyses.run_analyses.RunReport`` with the ``disturbances`` budget
    (``findings()`` for undersized wheels or magnetorquers) and the blinding,
    obstruction, shading, exposure and brightness tables; ``result`` is the
    run (:func:`run`), whose series hold the analyses; ``base_dir`` resolves
    the model's relative mesh paths (default: the scenario file's folder)."""
    from .analyses import common, run_analyses

    return run_analyses.report(result, scenario, common.spacecraft(scenario, spacecraft), base_dir)


def reentry(scenario, spacecraft: str | None = None, population_density_per_km2: float | None = None,
            base_dir=None):
    """The preliminary re-entry casualty estimate of a spacecraft's 3D
    model: ``analyses.reentry.ReentryEstimate`` (each part's fate, the
    casualty area, and with a population density the risk against
    1:10,000). A preliminary estimate, not a substitute for DAS."""
    from .analyses import common, reentry as estimate

    return estimate.reentry_estimate(common.spacecraft(scenario, spacecraft), base_dir, population_density_per_km2,
                                     scenario)


def record(scenario, analysis, spacecraft: str | None = None, result=None) -> dict:
    """The JSON record of ``analysis`` (an ``EndOfLife``, a ``Budget``, a
    ``LaunchDelaySweep``, an ``AltitudeTrade``, a ``DesignReport``, a ``RunReport`` or a
    ``ReentryEstimate`` computed for ``scenario``),
    as ``--out`` writes it: inputs, model, results with their traces,
    notes and provenance. ``result``: the run it took its inputs from."""
    from .engine import analysis_records, lifetime as engine_lifetime, propellant_budget

    name = _spacecraft(scenario, spacecraft)
    if isinstance(analysis, engine_lifetime.EndOfLife):
        options = analysis.options
        return analysis_records.lifetime_record(scenario, name, analysis, options["max_years"],
                                                options["forecast_percentile"], options["drag_coeff"],
                                                options["deorbit_perigee_km"], options.get("propellant_kg"))
    if isinstance(analysis, propellant_budget.Budget):
        return analysis_records.budget_record(scenario, name, analysis, result)
    if isinstance(analysis, propellant_budget.LaunchDelaySweep):
        return analysis_records.sweep_record(scenario, name, analysis, result)
    if isinstance(analysis, propellant_budget.AltitudeTrade):
        return analysis_records.trade_record(scenario, name, analysis, result)
    from .analyses import design_checks as checks, records as analysis_tables

    if isinstance(analysis, checks.DesignReport):
        return analysis_tables.design_record(scenario, analysis)
    from .analyses import reentry as reentry_module, run_analyses

    if isinstance(analysis, run_analyses.RunReport):
        return analysis_tables.run_record(scenario, analysis, result)
    if isinstance(analysis, reentry_module.ReentryEstimate):
        return analysis_tables.reentry_record(scenario, analysis)
    raise TypeError(f"no record for a {type(analysis).__name__}")


def write(path, data: dict) -> Path:
    """Write a :func:`record` (or a :func:`compare`'s ``to_dict()``) as JSON
    to ``path``; returns the path."""
    from .engine import analysis_records

    return analysis_records.write(Path(path), data)
