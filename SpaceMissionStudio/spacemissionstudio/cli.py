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

r"""Batch/headless CLI, separate from the interactive GUI -- and built on
exactly the same ``schema``/``engine`` layer the GUI uses, nothing
duplicated. This is also the architectural proof that the "decoupled from
the sim engine via a clean API/service layer" goal actually held: every
command below is a thin wrapper over ``schema.load_scenario()``,
``engine.service.SimulationService``, ``engine.kernels``, and
``engine.spaceweather`` -- the exact same calls
``gui.main_window.MainWindow`` makes.

``run`` dispatches on ``scenario.mission_sequence``: a non-empty one is
executed via ``engine.mission_engine.MissionEngine`` (propagate/maneuver/
.../script_block commands drive the simulation, and a Command Summary CSV
is written alongside the usual per-series ones if any ``report`` commands
ran) instead of a single ``SimulationService.run()`` call. The GUI's run
worker makes the same choice; a scenario with no mission_sequence runs
for ``sim_settings.duration_days``.

Commands that don't need Basilisk (such as ``validate``) work without a
Basilisk build; commands that do (such as ``run``, ``monte-carlo`` and
``kernels-status``) import it lazily and report a clear, specific error
instead of an ``ImportError`` traceback if it's missing -- see each command
function's own lazy import.

Usage::

    spacemissionstudio validate scenario.json
    spacemissionstudio run scenario.json --out-dir results/
    spacemissionstudio monte-carlo scenario.json --archive-dir mc_results/
    spacemissionstudio kernels-status
    spacemissionstudio spaceweather-resolve scenario.json
    spacemissionstudio generate-constellation template.json --out constellation.json \
        --total-satellites 12 --planes 3 --phasing-factor 1 --altitude-km 780 --inclination-deg 86.4
    spacemissionstudio generate-phasing-formation chief_only.json --out formation.json \
        --chief chief-1 --follower-name follower-1 --along-track-km 50
    spacemissionstudio generate-roe-formation chief_only.json --out helix.json \
        --chief chief-1 --follower-name follower-1 --safe 0,300,300
    spacemissionstudio model scenario.json --spacecraft sat-1 --apply
    spacemissionstudio gui
    spacemissionstudio --version
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import traceback
from datetime import timedelta
from pathlib import Path

from .schema.epochs import parse_epoch_utc
from . import __version__, dependencies, output_provenance
from .logging_setup import configure_logging, get_log_file_path
from .schema import ScenarioValidationError, load_scenario
from .schema.command import runs_sequence, script_blocks
from .schema.scenario import PHASING_CONTROL_LAWS, ROE_CONTROL_LAWS

# The exit status of a fault in SpaceMissionStudio itself, as opposed to the
# input (1), a missing component or usage (2) or a failed run (3): ICD-02.
EXIT_INTERNAL_ERROR = 4
# The command ran and its check did not pass (a flight-software export no
# longer current, SIL residuals over --max-error): ICD-02. In 1.3.1 and earlier these
# returned 2, the status of a missing component or a usage error (audit 3.2).
EXIT_CHECK_FAILED = 5


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {scenario.name!r} -- {len(scenario.spacecraft)} spacecraft, "
          f"schema version {scenario.schema_version}, epoch {scenario.epoch_utc}")
    blocks = script_blocks(scenario.mission_sequence)
    if blocks:
        print(f"NOTE: {len(blocks)} script_block(s) ({', '.join(path for path, _ in blocks)}) run unrestricted "
              "Python; 'run' and 'monte-carlo' need --allow-scripts to run them")
    # The plausibility checks the GUI shows while editing (perigee below
    # the ground, an unusable TLE, no pass, data that does not cover the
    # run): warnings only, the exit status stays 0 (audit L11).
    from .engine import scenario_checks

    base_dir = args.scenario.resolve().parent  # resolves a 3D model's relative mesh paths
    for warning in (scenario_checks.plausibility_warnings(scenario, base_dir=base_dir)
                    + scenario_checks.scenario_warnings(scenario)):
        print(f"WARNING: {warning}")
    return 0


def _run_argument_error(scenario, args: argparse.Namespace):
    """Why ``run`` cannot start with these arguments, or None. A scenario
    with script blocks needs --allow-scripts: a scenario file must not run
    code without the user knowing (SRS-S-03)."""
    if args.vizard_save_file and args.vizard_live_stream:
        return "pass at most one of --vizard-save-file / --vizard-live-stream"
    blocks = script_blocks(scenario.mission_sequence)
    if blocks and not args.allow_scripts:
        return (f"{len(blocks)} script_block(s) ({', '.join(path for path, _ in blocks)}) run unrestricted "
                "Python from the scenario file. Read the code first, then pass --allow-scripts to run it.")
    return None


def _output_folder_error(out_dir: Path) -> str | None:
    """Why a run's results could not be written to ``out_dir``, found before
    the run: a folder under a file, or one without write access, used to
    fail only after the whole simulation (audit R8)."""
    import tempfile

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=out_dir):
            pass
    except OSError as exc:
        return f"could not write the results to {out_dir}: {exc}"
    return None


def _write_run_outputs(args, scenario, result, command_summary) -> None:
    """The CSV files, OEMs, events and Mission Sequence summary of a run."""
    from .engine import ccsds_odm, data_budget, events
    from .engine.results import output_path

    before = {entry.name for entry in Path(args.out_dir).iterdir()} if Path(args.out_dir).is_dir() else set()
    paths = result.export_csv(args.out_dir)
    written = {Path(path).name for path in paths.values()}
    print(f"Wrote {len(paths)} result file(s) to {args.out_dir}:")
    for name, path in sorted(paths.items()):
        print(f"  {name}: {path}")
    if args.oem:
        names = [sc.name for sc in scenario.spacecraft
                 if f"{sc.name}.position_N" in result.series and len(result.series[f"{sc.name}.position_N"].time_s)]
        for name, text in ccsds_odm.oem_from_result(result, scenario.epoch_utc, scenario.gravity.central_body,
                                                    names, stride=args.oem_stride,
                                                    interpolation=args.oem_interpolation).items():
            oem_path = output_path(args.out_dir, f"{name}.oem")
            oem_path.write_text(text, encoding="ascii")
            written.add(oem_path.name)
            print(f"  CCSDS OEM: {oem_path}")

    for line in data_budget.summary_lines(result):
        print(f"  data: {line}")
    found = events.extract_events(result)  # the GUI's Events tab, headless (provenance.json covers it)
    if found:
        events_path = events.write_csv(found, args.out_dir / "events.csv", scenario.epoch_utc)
        written.add(Path(events_path).name)
        print(f"  events ({len(found)}): {events_path}")

    # Informational only -- never affects the exit code (see
    # ResultSet.warnings's own docstring: a non-empty list here is a
    # numerical-health diagnostic, not a validation failure).
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if command_summary is not None:
        print(f"Mission sequence: executed {command_summary.commands_executed} command(s), "
              f"{len(command_summary.reports)} report(s).")
        if command_summary.reports:
            summary_path = command_summary.export_csv(args.out_dir / "command_summary.csv")
            written.add(Path(summary_path).name)
            print(f"  command_summary: {summary_path}")

    # Files an earlier run left: not this run's, though they sit beside it
    # (a stale events.csv and another spacecraft's series, audit R7).
    stale = sorted(before - written)
    if stale:
        shown = ", ".join(stale[:5]) + (f" and {len(stale) - 5} more" if len(stale) > 5 else "")
        print(f"WARNING: {args.out_dir} also holds {len(stale)} file(s) this run did not write: {shown}. They are "
              "not this run's results; use an empty --out-dir to keep runs apart.", file=sys.stderr)


def cmd_run(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    argument_error = _run_argument_error(scenario, args)
    if argument_error:
        print(f"ERROR: {argument_error}", file=sys.stderr)
        return 1

    try:
        from .engine.service import SimulationService
    except ImportError as exc:
        print(f"ERROR: Basilisk is not installed/built ({exc}) -- see SpaceMissionStudio/README.md", file=sys.stderr)
        return 2
    version_note = dependencies.basilisk_check()
    if version_note:
        print(f"WARNING: {version_note}", file=sys.stderr)

    vizard_request = None
    if args.vizard_save_file or args.vizard_live_stream:
        from .engine.vizard import VizardRequest

        vizard_request = VizardRequest(
            save_file=args.vizard_save_file, live_stream=args.vizard_live_stream,
            camera_target=args.vizard_camera_target, show_orbit_lines=not args.vizard_no_orbit_lines,
            show_trajectory_trail=args.vizard_trail, show_ground_tracks=args.vizard_ground_tracks,
            model_base_dir=str(args.scenario.resolve().parent),
        )

    folder_error = _output_folder_error(args.out_dir)
    if folder_error:
        print(f"ERROR: {folder_error}", file=sys.stderr)
        return 3

    print(f"Running {scenario.name!r} ({len(scenario.spacecraft)} spacecraft, "
          f"{scenario.sim_settings.duration_days} day(s), {scenario.sim_settings.integrator})...")
    service = SimulationService(scenario, vizard_request=vizard_request)
    command_summary = None
    try:
        if runs_sequence(scenario.mission_sequence):
            # A non-empty mission_sequence takes over how far/how the sim
            # actually runs (propagate/maneuver/... commands drive
            # ConfigureStopTime()/ExecuteSimulation(), not a single
            # duration_days-long run()) -- see engine/mission_engine.py.
            # An empty mission_sequence (still the default -- see
            # schema/command.py) keeps the exact pre-Phase-6 behavior
            # below, unchanged.
            from .engine.mission_engine import MissionEngine

            print(f"Executing mission_sequence ({len(scenario.mission_sequence)} top-level command(s))...")
            result, command_summary = MissionEngine(scenario, service=service,
                                                    allow_scripts=args.allow_scripts).run()
        else:
            result = service.run()
    except Exception as exc:  # noqa: BLE001 -- report ANY run failure with a specific message, not a bare traceback
        print(f"ERROR: run failed: {exc}", file=sys.stderr)
        return 3

    try:
        _write_run_outputs(args, scenario, result, command_summary)
    except (OSError, ValueError) as exc:  # a write that failed, or a path refused by results.output_path
        print(f"ERROR: could not write the results to {args.out_dir}: {exc}", file=sys.stderr)
        return 3

    if any(sc.station_keeping is not None for sc in scenario.spacecraft):
        print("Station-keeping summary:")
        _print_station_keeping_summary(scenario, result)
    if any(sc.constant_thrust is not None for sc in scenario.spacecraft):
        print("Constant-thrust summary:")
        _print_constant_thrust_summary(scenario, result)
    return 0


def _print_station_keeping_summary(scenario, result) -> None:
    """Prints total delta-V used and propellant used/remaining per
    spacecraft with ``station_keeping`` configured -- the headline numbers
    ``engine.orbit_maintenance`` tracks, surfaced directly rather than
    leaving the user to dig them out of a CSV. Reads the final sample of
    each spacecraft's ``.station_keeping.delta_v``/``.propellant_remaining``
    series (see ``engine.service.SimulationService.run()``); silently
    skips a spacecraft whose series aren't present (station_keeping was
    configured but, e.g., the run failed before the series could be built).

    A spacecraft with ``phasing_keeping`` ALSO configured shares one
    propellant tank between the two controllers (see
    ``schema.scenario.PhasingKeepingConfig``'s docstring), so
    ``propellant_used_kg`` here already covers both; delta-V is tracked
    separately per controller, so the total reported is their sum, with a
    breakdown line underneath.
    """
    for sc in scenario.spacecraft:
        if sc.station_keeping is None:
            continue
        delta_v_series = result.series.get(f"{sc.name}.station_keeping.delta_v")
        propellant_series = result.series.get(f"{sc.name}.station_keeping.propellant_remaining")
        if delta_v_series is None or propellant_series is None or len(delta_v_series.data) == 0:
            continue
        station_keeping_delta_v_m_s = float(delta_v_series.data[-1, 0])
        propellant_remaining_kg = float(propellant_series.data[-1, 0])
        propellant_used_kg = sc.station_keeping.propellant_kg - propellant_remaining_kg

        phasing_delta_v_m_s = 0.0
        if sc.phasing_keeping is not None:
            phasing_delta_v_series = result.series.get(f"{sc.name}.phasing_keeping.delta_v")
            if phasing_delta_v_series is not None and len(phasing_delta_v_series.data) > 0:
                phasing_delta_v_m_s = float(phasing_delta_v_series.data[-1, 0])

        total_delta_v_m_s = station_keeping_delta_v_m_s + phasing_delta_v_m_s
        print(f"  {sc.name}: {total_delta_v_m_s:.3f} m/s delta-V, "
              f"{propellant_used_kg:.3f} kg propellant used ({propellant_remaining_kg:.3f} kg remaining)")
        if sc.phasing_keeping is not None:
            print(f"    (altitude-keeping: {station_keeping_delta_v_m_s:.3f} m/s, "
                  f"phasing vs. {sc.phasing_keeping.chief_spacecraft!r}: {phasing_delta_v_m_s:.3f} m/s)")


def _print_constant_thrust_summary(scenario, result) -> None:
    """Same idea as :func:`_print_station_keeping_summary`, for
    ``constant_thrust`` -- an INDEPENDENT propellant budget/tank from
    station_keeping's (see ``schema.scenario.ConstantThrustConfig``'s
    docstring), so this is always its own separate line, never combined
    with the station-keeping summary above even when both are configured
    on the same spacecraft.
    """
    for sc in scenario.spacecraft:
        if sc.constant_thrust is None:
            continue
        delta_v_series = result.series.get(f"{sc.name}.constant_thrust.delta_v")
        propellant_series = result.series.get(f"{sc.name}.constant_thrust.propellant_remaining")
        if delta_v_series is None or propellant_series is None or len(delta_v_series.data) == 0:
            continue
        delta_v_m_s = float(delta_v_series.data[-1, 0])
        propellant_remaining_kg = float(propellant_series.data[-1, 0])
        propellant_used_kg = sc.constant_thrust.propellant_kg - propellant_remaining_kg
        print(f"  {sc.name}: {delta_v_m_s:.3f} m/s delta-V ({sc.constant_thrust.frame} frame), "
              f"{propellant_used_kg:.3f} kg propellant used ({propellant_remaining_kg:.3f} kg remaining)")


def cmd_monte_carlo(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    if not scenario.monte_carlo.enabled:
        print("ERROR: scenario.monte_carlo.enabled is false in this scenario file -- "
              "set it true (and configure dispersions) before running Monte Carlo", file=sys.stderr)
        return 1

    try:
        from .engine.monte_carlo import MonteCarloError, run_monte_carlo
    except ImportError as exc:
        print(f"ERROR: Basilisk is not installed/built ({exc}) -- see SpaceMissionStudio/README.md", file=sys.stderr)
        return 2

    print(f"Running {scenario.monte_carlo.num_runs} Monte Carlo case(s) of {scenario.name!r} "
          f"({len(scenario.monte_carlo.dispersions)} dispersion(s), {scenario.monte_carlo.thread_count} thread(s))...")
    try:
        failures = run_monte_carlo(scenario, scenario.monte_carlo, args.archive_dir,
                                   allow_scripts=args.allow_scripts, overwrite=args.overwrite)
        output_provenance.write_sidecar(Path(args.archive_dir) / "archive", output_provenance.scenario_record(scenario))
    except MonteCarloError as exc:
        print(f"ERROR: Monte Carlo run failed: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"ERROR: could not write the Monte Carlo results: {exc}", file=sys.stderr)
        return 3

    print(f"Archived results to {args.archive_dir}")
    from .engine import monte_carlo_results

    if monte_carlo_results.has_summary(args.archive_dir):
        for line in monte_carlo_results.summary_lines(monte_carlo_results.load(args.archive_dir)):
            print(f"  {line}")
    if failures:
        print(f"FAILED runs: {failures}", file=sys.stderr)
        return 3  # runs failed (ICD-02); 4 in 1.3.1 and earlier, the status of an internal error (audit 3.2)
    print(f"All {scenario.monte_carlo.num_runs} run(s) succeeded.")
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    """Report a spacecraft's 3D model: its parts, the mass properties and
    facets it gives, and whether the spacecraft's stored values match;
    optionally apply them to the file, or export the model as .obj."""
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    from .model3d import model as model3d
    from .model3d.obj_io import write_obj

    with_model = [sc for sc in scenario.spacecraft if sc.model is not None]
    if args.spacecraft:
        with_model = [sc for sc in with_model if sc.name == args.spacecraft]
        if not with_model:
            print(f"ERROR: no spacecraft {args.spacecraft!r} with a 3D model", file=sys.stderr)
            return 1
    if not with_model:
        print("No spacecraft in this scenario has a 3D model.")
        return 0
    if args.export_obj and len(with_model) > 1:
        print("ERROR: --export-obj writes one model; name it with --spacecraft", file=sys.stderr)
        return 1
    base_dir = args.scenario.resolve().parent
    orbit_only = scenario.simulation_mode == "orbit_only"
    failed = False
    for sc in with_model:
        derived = model3d.derive(sc.model, base_dir)
        parts = ", ".join(f"{p.name} ({p.shape}, {p.mass_kg:g} kg{'' if p.counts_toward_mass else ', not counted'})"
                          for p in sc.model.parts)
        print(f"{sc.name}: 3D model, {len(sc.model.parts)} part(s): {parts}")
        props = derived.mass_properties
        if props is not None:
            print(f"  mass properties ({sc.model.mass_properties_source}):")
            for line in model3d.principal_summary(props):
                print(f"    {line}")
        if derived.faces:
            areas = derived.projected_areas_m2()
            seen = ", ".join(f"{axis} {area:.3g}" for axis, area in areas.items())
            print(f"  facets: {len(derived.faces)}, {sum(f.area_m2 for f in derived.faces):.3g} m^2 in all; "
                  f"seen from {seen} m^2")
        for message in derived.errors:
            print(f"  ERROR: {message}")
            failed = True
        for message in derived.warnings:
            print(f"  WARNING: {message}")
        if args.apply:
            written = model3d.apply(sc, derived, orbit_only=orbit_only)
            print(f"  applied: {', '.join(written) if written else 'nothing (applying is switched off)'}")
        else:
            stale = model3d.stale_fields(sc, derived, orbit_only=orbit_only)
            print(f"  stored values: {'differ in ' + ', '.join(stale) if stale else 'match the model'}")
        if args.export_obj:
            groups = model3d.obj_groups(derived)
            if not groups:
                print("ERROR: the model has no part that can be drawn", file=sys.stderr)
                return 1
            path = write_obj(args.export_obj, groups)
            print(f"  wrote {path} and {path.with_suffix('.mtl').name} (body frame, metres, +z up)")
    if args.apply:
        try:
            scenario.validate()
        except ScenarioValidationError as exc:
            print(f"INVALID after applying, not saved: {exc}", file=sys.stderr)
            return 1
        scenario.save(args.scenario)
        print(f"Saved {args.scenario}")
    return 1 if failed else 0


def cmd_lifetime(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    name = args.spacecraft or scenario.spacecraft[0].name
    try:
        from .engine import lifetime
    except ImportError as exc:
        print(f"ERROR: Basilisk is not installed/built ({exc}) -- see SpaceMissionStudio/README.md", file=sys.stderr)
        return 2
    try:
        drag_coeff = None if args.drag_coeff == "own" else float(args.drag_coeff)
        end = lifetime.end_of_life(scenario, name, deorbit_perigee_km=args.deorbit_perigee_km,
                                   max_years=args.max_years, forecast_percentile=args.forecast_percentile,
                                   drag_coeff=drag_coeff)
    except lifetime.LifetimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    result = end.lifetime
    if end.deorbit is not None:
        plan = end.deorbit
        print(f"Deorbit burn: {plan.delta_v_m_s:.1f} m/s, {plan.propellant_kg:.2f} kg of "
              f"{plan.propellant_available_kg:.2f} kg -> perigee {plan.perigee_km:.0f} km")
    if result.reentered:
        print(f"{name}: re-entry {result.reentry_utc:%Y-%m-%d}, {result.lifetime_years:.2f} years from "
              f"{result.start_utc:%Y-%m-%d}")
    else:
        print(f"{name}: still in orbit after {result.horizon_years:.1f} years")
    for years, label in ((lifetime.ZERO_DEBRIS_YEARS, "5-year rule"), (lifetime.IADC_YEARS, "25-year guideline")):
        verdict = ("met" if result.meets(years) else "not met") if result.known(years) else "not known"
        print(f"  {label}: {verdict}")
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


def _print_altitude_trade(pb, scenario, name, result, altitudes) -> int:
    print(f"{name}: launch-delay sweep per altitude (several minutes; altitudes run in parallel)...")
    try:
        trade = pb.altitude_trade(scenario, name, altitudes or None, result)
    except pb.BudgetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(f"{'Altitude':>8} {'Incl.':>6} {'Worst launch':<12} {'In-plane dV':>12} {'Disposal dV':>12} "
          f"{'Prop. [kg]':>10}  Fits tank")
    for case in trade.altitudes:
        worst = case.worst
        fits = {True: "yes", False: "no", None: "-"}[trade.fits(case)]
        print(f"{case.altitude_km:>6g}km {case.inclination_deg:>6.2f} {worst.launch_utc:%Y-%m-%d}   "
              f"{worst.delta_v_of('Operations', 'In-plane'):>12.2f} {worst.delta_v_of('End of life', ''):>12.2f} "
              f"{worst.budget.total_propellant_kg:>10.3f}  {fits}")
    for note in trade.notes:
        print(f"NOTE: {note}")
    return 0


def _finite_float_arg(text: str) -> float:
    """A number argument: ``nan`` and ``inf``, which ``float()`` accepts,
    are refused here, before they reach Basilisk's element conversions
    as a traceback."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r}: not a number") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"{text!r}: a finite number")
    return value


def _max_years_arg(text: str) -> float:
    """A lifetime's look-ahead: more than 0 and at most 100 years, the
    GUI's limit (1e6 overflowed the date; -5 exited 3; audit R6)."""
    value = _finite_float_arg(text)
    if not 0.0 < value <= 100.0:  # [year] engine.lifetime.MAX_HORIZON_YEARS, without importing Basilisk here
        raise argparse.ArgumentTypeError(f"{text!r}: more than 0 and at most 100 years")
    return value


def _positive_int_arg(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r}: a whole number of 1 or more") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"{text!r}: a whole number of 1 or more")  # 0 and -3 were accepted (L7)
    return value


def _altitudes_arg(text: str) -> list:
    if text == "auto":
        return []
    try:
        altitudes = [float(v) for v in text.split(",") if v.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r}: comma-separated altitudes in km, e.g. 400,450,500") from None
    if not altitudes or any(not 150.0 <= a <= 2000.0 for a in altitudes):
        raise argparse.ArgumentTypeError(f"{text!r}: altitudes between 150 and 2000 km")
    return altitudes


def _drag_coeff_arg(text: str) -> str:
    if text != "own":
        try:
            if not 0.0 < float(text) <= 10.0:
                raise ValueError
        except ValueError:
            raise argparse.ArgumentTypeError(f"{text!r}: a drag coefficient in (0, 10], or 'own'") from None
    return text


def cmd_budget(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    name = args.spacecraft or scenario.spacecraft[0].name
    try:
        from .engine import propellant_budget as pb
        from .engine.service import SimulationService
    except ImportError as exc:
        print(f"ERROR: Basilisk is not installed/built ({exc}) -- see SpaceMissionStudio/README.md", file=sys.stderr)
        return 2
    result = None
    if args.run:
        print(f"Running {scenario.name!r} for the simulated contributors...")
        try:
            result = SimulationService(scenario).run()
        except Exception as exc:  # noqa: BLE001 -- report ANY run failure with a specific message
            print(f"ERROR: run failed: {exc}", file=sys.stderr)
            return 3
    if args.altitudes is not None:
        return _print_altitude_trade(pb, scenario, name, result, args.altitudes)
    if args.launch_delays:
        return _print_launch_delays(pb, scenario, name, result)
    try:
        budget = pb.compute_budget(scenario, name, result)
    except pb.BudgetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(f"{name}: dry mass {budget.dry_mass_kg:.1f} kg, Isp {budget.isp_s:g} s, efficiency {budget.efficiency:.3f}")
    print(f"{'Phase':<18} {'Contributor':<52} {'dV [m/s]':>9} {'Prop. [kg]':>10}  Margin")
    for row in budget.rows:
        dv = "" if row.delta_v_m_s is None else f"{row.delta_v_m_s:.2f}"
        print(f"{row.phase:<18} {row.contributor:<52} {dv:>9} {row.propellant_kg:>10.3f}  {row.margin} ({row.source})")
    print(f"{'Total':<71} {budget.total_delta_v_m_s:>9.2f} {budget.total_propellant_kg:>10.3f}")
    for note in budget.notes:
        print(f"NOTE: {note}")
    return 0


def _print_launch_delays(pb, scenario, name, result) -> int:
    print(f"{name}: budget for the planned launch and up to 5 years late (ESA AD10 Sec. 5.5)...")
    try:
        sweep = pb.launch_delay_sweep(scenario, name, result)
    except pb.BudgetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(f"{'Launch':<11} {'Delay':>6} {'In-plane dV':>12} {'Disposal dV':>12} {'Total dV':>9} {'Prop. [kg]':>10}")
    worst = sweep.worst
    for case in sweep.cases:
        in_plane = case.delta_v_of("Operations", "In-plane")
        disposal = case.delta_v_of("End of life", "")
        mark = "  <- worst" if case is worst else ""
        print(f"{case.launch_utc:%Y-%m-%d} {case.delay_years:>5g}y {in_plane:>12.2f} {disposal:>12.2f} "
              f"{case.budget.total_delta_v_m_s:>9.2f} {case.budget.total_propellant_kg:>10.3f}{mark}")
    for note in sweep.notes:
        print(f"NOTE: {note}")
    return 0


def cmd_kernels_status(args: argparse.Namespace) -> int:
    try:
        from .engine import kernels
    except ImportError as exc:
        print(f"ERROR: Basilisk is not installed/built ({exc}) -- see SpaceMissionStudio/README.md", file=sys.stderr)
        return 2

    statuses = kernels.ensure_kernels()
    for status in statuses:
        if status.available:
            cached_note = f" (cached, last modified {status.modified_utc})" if status.modified_utc else ""
            print(f"  OK    {status.filename}: {status.path}{cached_note}")
        else:
            print(f"  FAIL  {status.filename}: {status.error}")
    return 0 if all(s.available for s in statuses) else 2  # a missing component (ICD-02); 1 in 1.3.1 and earlier


def cmd_earth_orientation(args: argparse.Namespace) -> int:
    """Status of the Earth orientation files; --fetch downloads them from
    NAIF (network: only when asked), --import installs files from disk,
    --rollback restores the previous set."""
    from .engine import earth_orientation as eo

    try:
        if args.fetch:
            print(f"Downloading from {eo.NAIF_PCK_URL}: {', '.join(eo.available_files())} ...")
            eo.fetch()
        elif args.import_files:
            eo.import_files(args.import_files)
        elif args.rollback:
            eo.rollback()
    except eo.EarthOrientationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    kernels = eo.installed()
    if not kernels:
        print(f"No Earth orientation files installed: runs use {eo.FALLBACK_EARTH_FRAME}. "
              "Run 'spacemissionstudio earth-orientation --fetch' (needs internet) or --import FILE.")
        return 1
    for kernel in kernels:
        print(f"  {kernel.role:15s} {Path(kernel.path).name}  {kernel.size_bytes / 1e6:.1f} MB  "
              f"last datum {kernel.last_datum_utc or 'unknown'}  sha256 {kernel.sha256[:16]}  from {kernel.source}")
    until = eo.high_accuracy_until(kernels)
    print(f"Earth-fixed frame: {eo.EARTH_FIXED_FRAME}; high accuracy until "
          f"{until:%Y-%m-%d}, predicted after." if until else f"Earth-fixed frame: {eo.EARTH_FIXED_FRAME}.")
    return 0


def cmd_small_bodies(args: argparse.Namespace) -> int:
    """Status of the small-body files (433 Eros: ephemeris and shape);
    --fetch downloads them (network: only when asked), --import installs
    the ephemeris kernel from disk."""
    from .engine import small_bodies as sb

    body = sb.EROS
    try:
        if args.fetch:
            print(f"Downloading {body.spk_name} from {body.spk_url} and the shape {body.shape_data_file}.tab ...")
            sb.fetch(body.name)
            sb.fetch_shape(body)
        elif args.import_file:
            sb.import_file(args.import_file, body.name)
    except sb.SmallBodyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    kernel = sb.installed(body.name)
    shape = sb.shape_path(body)
    print(f"{body.title}:")
    print(f"  ephemeris  {Path(kernel.path).name}  {kernel.size_bytes / 1e6:.1f} MB  sha256 {kernel.sha256[:16]}  "
          f"from {kernel.source}" if kernel else f"  ephemeris  missing ({body.spk_name})")
    print(f"  shape      {shape}" if shape else f"  shape      missing ({body.shape_data_file}.tab)")
    if kernel is None or shape is None:
        print("Run 'spacemissionstudio small-bodies --fetch' (needs internet), or --import the ephemeris file.")
        return 1
    return 0


# A CCSDS message is read whole; a long OEM is large, an endless file
# (/dev/zero) was read until the process was killed (exit 137, audit R9).
MAX_CCSDS_MESSAGE_BYTES = 500_000_000  # [byte]


def _read_ccsds_message(path) -> str:
    """``path``'s text (ASCII, other bytes replaced); OSError when it cannot
    be read or is larger than MAX_CCSDS_MESSAGE_BYTES."""
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_CCSDS_MESSAGE_BYTES + 1)
    if len(data) > MAX_CCSDS_MESSAGE_BYTES:
        raise OSError(f"larger than {MAX_CCSDS_MESSAGE_BYTES // 1_000_000} MB: not a CCSDS message")
    return data.decode("ascii", errors="replace")


def cmd_ccsds_validate(args: argparse.Namespace) -> int:
    """Check KVN OPM/OMM/OEM files against CCSDS 502.0-B-3."""
    from .engine import ccsds_odm

    failed = False
    for path in args.files:
        try:
            text = _read_ccsds_message(path)
        except OSError as exc:
            print(f"{path}: cannot be read ({exc.strerror or exc})", file=sys.stderr)
            failed = True
            continue
        issues = ccsds_odm.validate(text)
        errors = [i for i in issues if i.level == "error"]
        failed = failed or bool(errors)
        print(f"{path}: {'conforms' if not errors else f'{len(errors)} error(s)'}"
              + (f", {len(issues) - len(errors)} warning(s)" if len(issues) > len(errors) else ""))
        for issue in issues:
            print(f"  {issue}")
    return 1 if failed else 0


def cmd_ccsds_export(args: argparse.Namespace) -> int:
    """OPM of each spacecraft's initial state, or a TLE spacecraft's OMM."""
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    from .engine import ccsds_odm, time_system
    from .engine.results import output_path

    try:
        args.out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: could not create {args.out}: {exc}", file=sys.stderr)
        return 3
    epoch = time_system.elapsed_to_utc(scenario.epoch_utc, [0.0])[0]
    for sc in scenario.spacecraft:
        if sc.orbit.type == "tle":
            text = ccsds_odm.omm_from_tle(sc.orbit.tle_line1, sc.orbit.tle_line2, sc.name,
                                          comments=output_provenance.scenario_lines(scenario))
            path = output_path(args.out, f"{sc.name}.omm")
        else:
            try:
                from .engine.service import _orbit_ic_to_rv
            except ImportError as exc:
                print(f"ERROR: Basilisk is not installed/built ({exc})", file=sys.stderr)
                return 2
            r, v = _orbit_ic_to_rv(ccsds_odm.EARTH_GM_KM3_S2 * 1e9 if scenario.gravity.central_body == "earth"
                                   else _central_mu(scenario), sc.orbit, scenario.epoch_utc)
            gm = ccsds_odm.EARTH_GM_KM3_S2 if scenario.gravity.central_body == "earth" else None
            text = ccsds_odm.write_opm(
                object_name=sc.name, object_id="UNKNOWN", center_name=scenario.gravity.central_body,
                ref_frame="EME2000", time_system="UTC", epoch=epoch, r_km=[x / 1e3 for x in r],
                v_km_s=[x / 1e3 for x in v], gm_km3_s2=gm, mass_kg=_total_mass_kg(sc),
                srp_area_m2=sc.srp_area_m2 if sc.enable_srp else None, srp_coeff=sc.srp_coeff if sc.enable_srp else None,
                drag_area_m2=sc.drag_area_m2 if sc.enable_drag else None,
                drag_coeff=sc.drag_coeff if sc.enable_drag else None,
                comments=[f"Initial state of scenario {scenario.name!r}; EME2000 is SPICE J2000",
                          *output_provenance.scenario_lines(scenario)])
            path = output_path(args.out, f"{sc.name}.opm")
        try:
            path.write_text(text, encoding="ascii")
        except OSError as exc:
            print(f"ERROR: could not write {path}: {exc}", file=sys.stderr)
            return 3
        print(f"wrote {path}")
    return 0


def _total_mass_kg(spacecraft) -> float:
    """The spacecraft's mass at the epoch [kg] (CCSDS OPM MASS): dry mass plus
    every propellant load aboard."""
    blocks = (spacecraft.station_keeping, spacecraft.geo_station_keeping, spacecraft.constant_thrust)
    propellant_kg = sum(block.propellant_kg for block in blocks if block is not None)  # [kg]
    if spacecraft.fuel_tank is not None:
        propellant_kg += spacecraft.fuel_tank.propellant_mass_kg
    return spacecraft.dry_mass_kg + propellant_kg


def _central_mu(scenario) -> float:
    from Basilisk.utilities import simIncludeGravBody

    factory = simIncludeGravBody.gravBodyFactory()
    return getattr(factory, f"create{scenario.gravity.central_body.capitalize()}")().mu


def cmd_ccsds_import(args: argparse.Namespace) -> int:
    """Set a spacecraft's initial orbit from an OPM or TLE-based OMM."""
    from .engine import ccsds_odm

    try:
        scenario = load_scenario(args.scenario)
        orbit, epoch, notes = ccsds_odm.orbit_ic_from_odm(_read_ccsds_message(args.message),
                                                          central_body=scenario.gravity.central_body)
    except OSError as exc:  # a missing message, or a folder (audit M12)
        print(f"ERROR: could not read {args.message}: {exc}", file=sys.stderr)
        return 1
    except (ScenarioValidationError, ccsds_odm.OdmError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        for issue in getattr(exc, "issues", []):
            print(f"  {issue}", file=sys.stderr)
        return 1
    matches = [sc for sc in scenario.spacecraft if sc.name == args.spacecraft]
    if not matches:
        print(f"ERROR: no spacecraft {args.spacecraft!r} in {args.scenario}", file=sys.stderr)
        return 1
    if epoch is not None:
        scenario_epoch = parse_epoch_utc(scenario.epoch_utc)
        if abs((epoch - scenario_epoch.replace(tzinfo=None)).total_seconds()) > 1e-3 and not args.set_epoch:
            print(f"ERROR: the OPM state is at {epoch.isoformat()} UTC, the scenario epoch is {scenario.epoch_utc}; "
                  "pass --set-epoch to move the scenario epoch to the OPM's", file=sys.stderr)
            return 1
        scenario.epoch_utc = epoch.isoformat()
    matches[0].orbit = orbit
    scenario.validate()
    scenario.save(args.out or args.scenario)
    for note in notes:
        print(f"  {note}")
    print(f"{args.spacecraft}: orbit set from {args.message} -> {args.out or args.scenario}")
    return 0


def cmd_export_fsw(args: argparse.Namespace) -> int:
    """Export a spacecraft's flight software as a standalone C project."""
    from .fsw_export.capture import CaptureError
    from .fsw_export.generate import ExportError
    from .fsw_export.records import export_flight_software, with_record

    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    try:
        result, record = export_flight_software(scenario, args.spacecraft, args.out, steps=args.steps,
                                                overwrite=args.overwrite)
    except (CaptureError, ExportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    manifest = result.manifest
    print(f"{args.spacecraft}: {len(manifest['modules'])} modules, {len(manifest['ports']['inputs'])} inputs, "
          f"{len(manifest['ports']['outputs'])} outputs, {manifest['recorded_steps']} recorded steps -> {result.directory}")
    print(f"  configuration digest {record.config_digest}")
    print(f"  build: cmake -S {result.directory} -B {result.directory}/build && cmake --build {result.directory}/build "
          f"&& ctest --test-dir {result.directory}/build")
    if args.record:
        scenario.fsw_exports = with_record(scenario, record)
        scenario.validate()
        scenario.save(args.scenario)
        print(f"  recorded in {args.scenario}")
    return 0


def cmd_fsw_status(args: argparse.Namespace) -> int:
    """Whether each recorded flight-software export still matches the scenario."""
    from .fsw_export.records import CURRENT, export_status

    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    if not scenario.fsw_exports:
        print("no flight-software exports recorded in this scenario")
        return 0
    worst = 0
    for record in scenario.fsw_exports:
        status = export_status(scenario, record, base_dir=args.scenario.resolve().parent)
        print(f"{record.spacecraft}: {status.state.upper()} -- {status.message} ({record.path})")
        if status.state != CURRENT:
            worst = EXIT_CHECK_FAILED
    return worst


def cmd_sil(args: argparse.Namespace) -> int:
    """Run a spacecraft's flight software as an external program, in the loop."""
    from .sil.contract import SilError
    from .sil.runner import SilOptions, SilRunError, run_sil
    from .sil.session import Timeouts

    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    timeouts = Timeouts(handshake_s=args.handshake_timeout, step_s=args.step_timeout,
                        deadline_s=args.deadline_ms * 1e-3 if args.deadline_ms else None)
    try:
        _, report = run_sil(scenario, args.spacecraft, SilOptions(str(args.binary), timeouts, args.transport))
    except SilRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if exc.report is not None and exc.report.log_tail.strip():
            print("--- the program's last output ---", file=sys.stderr)
            print(exc.report.log_tail.rstrip(), file=sys.stderr)
        return 1
    except SilError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("\n".join(report.summary_lines()))
    if args.report:
        args.report.write_text(report.to_json() + "\n")
        print(f"  report: {args.report}")
    if args.residuals_csv:
        report.write_residuals_csv(args.residuals_csv)
        print(f"  residuals: {args.residuals_csv}")
    if args.max_error is not None and (report.max_abs_error > args.max_error or report.signals_missing):
        print(f"FAIL: largest residual {report.max_abs_error:.6g} is over {args.max_error:g}"
              if report.max_abs_error > args.max_error else "FAIL: some outputs were never written", file=sys.stderr)
        return EXIT_CHECK_FAILED
    return 0


def cmd_spaceweather_resolve(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    from .engine import spaceweather as sw

    start = parse_epoch_utc(scenario.epoch_utc)
    end = start + timedelta(days=scenario.sim_settings.duration_days)
    try:
        resolved = sw.resolve_for(scenario.space_weather, start, end)
    except Exception as exc:  # noqa: BLE001 -- report ANY resolve failure with a specific message, not a bare traceback
        print(f"ERROR: space weather resolve failed: {exc}", file=sys.stderr)
        return 3
    print(f"Resolved to: {resolved.path}")
    print(f"From real data: {resolved.data_file}")
    for warning in resolved.warnings:
        print(f"  warning: {warning}")
    return 0


def cmd_generate_constellation(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    if args.template_spacecraft is not None:
        template = next((sc for sc in scenario.spacecraft if sc.name == args.template_spacecraft), None)
        if template is None:
            print(f"ERROR: no spacecraft named {args.template_spacecraft!r} in {args.scenario} -- "
                  f"this scenario has: {[sc.name for sc in scenario.spacecraft]}", file=sys.stderr)
            return 1
    elif len(scenario.spacecraft) == 1:
        template = scenario.spacecraft[0]
    else:
        print(f"ERROR: {args.scenario} has {len(scenario.spacecraft)} spacecraft -- pass "
              "--template-spacecraft NAME to say which one to clone into the constellation", file=sys.stderr)
        return 1

    from .engine.constellation import WalkerConstellationRequest, generate_walker_constellation, simulated_j2

    # central_body always comes from the scenario itself, never an
    # independent flag -- see gui.constellation_dialog's docstring for why
    # a mismatch there would silently produce satellites at the wrong
    # altitude relative to whatever body actually gets simulated.
    request = WalkerConstellationRequest(
        total_satellites=args.total_satellites, num_planes=args.planes, phasing_factor=args.phasing_factor,
        altitude_km=args.altitude_km, inclination_deg=args.inclination_deg,
        central_body=scenario.gravity.central_body, eccentricity=args.eccentricity,
        arg_periapsis_deg=args.arg_periapsis_deg, pattern=args.pattern,
        raan_offset_deg=args.raan_offset_deg, name_prefix=args.name_prefix,
    )
    try:
        generated = generate_walker_constellation(
            request, template, j2=simulated_j2(scenario.gravity.central_body, scenario.gravity.central_body_degree))
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    scenario.spacecraft = (scenario.spacecraft + generated) if args.append else generated
    try:
        scenario.save(args.out)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {len(generated)} spacecraft ({args.planes} plane(s), {request.pattern} pattern) "
          f"from template {template.name!r}, wrote {len(scenario.spacecraft)}-spacecraft scenario to {args.out}")
    return 0


def cmd_generate_phasing_formation(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    chief = next((sc for sc in scenario.spacecraft if sc.name == args.chief), None)
    if chief is None:
        print(f"ERROR: no spacecraft named {args.chief!r} in {args.scenario} -- "
              f"this scenario has: {[sc.name for sc in scenario.spacecraft]}", file=sys.stderr)
        return 1
    if args.template_spacecraft is not None:
        template = next((sc for sc in scenario.spacecraft if sc.name == args.template_spacecraft), None)
        if template is None:
            print(f"ERROR: no spacecraft named {args.template_spacecraft!r} in {args.scenario} -- "
                  f"this scenario has: {[sc.name for sc in scenario.spacecraft]}", file=sys.stderr)
            return 1
    else:
        template = chief

    # engine.formation itself has no Basilisk import at module level (see
    # its own docstring) -- the real Basilisk import is lazy, INSIDE
    # generate_phasing_follower() below, so the ImportError this needs to
    # catch can only happen around that call, not this one.
    from .engine.constellation import simulated_j2
    from .engine.formation import PhasingFormationRequest, generate_phasing_follower

    request = PhasingFormationRequest(
        chief_name=chief.name, follower_name=args.follower_name,
        radial_km=args.radial_km, along_track_km=args.along_track_km, cross_track_km=args.cross_track_km,
        reconfiguration_interval_days=args.reconfiguration_interval_days,
        tolerance_fraction=args.tolerance_fraction, restore_tolerance_fraction=args.restore_tolerance_fraction,
        correction_window_days=args.correction_window_days, max_drift_days=args.max_drift_days,
        max_delta_semi_major_axis_km=args.max_delta_semi_major_axis_km,
        station_keeping_target_altitude_km=args.station_keeping_target_altitude_km,
        station_keeping_deadband_km=args.station_keeping_deadband_km,
        thrust_n=args.thrust_n, isp_s=args.isp_s, propellant_kg=args.propellant_kg,
        eclipse_sunlit_threshold=args.eclipse_sunlit_threshold,
        min_on_time_s=args.min_on_time_s,
        eccentricity_neutral_burns=args.eccentricity_neutral_burns,
        control_law=args.control_law,
    )
    try:
        follower = generate_phasing_follower(
            request, chief, template, scenario.gravity.central_body,
            j2=simulated_j2(scenario.gravity.central_body, scenario.gravity.central_body_degree))
    except ImportError as exc:
        print(f"ERROR: Basilisk is not installed/built ({exc}) -- generating a phasing formation needs a real "
              f"Basilisk build (it computes the follower's orbit via a real Hill-frame state-vector transform) "
              f"-- see SpaceMissionStudio/README.md", file=sys.stderr)
        return 2
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    if follower.name in {sc.name for sc in scenario.spacecraft}:
        print(f"ERROR: a spacecraft named {follower.name!r} already exists in {args.scenario}", file=sys.stderr)
        return 1
    scenario.spacecraft = scenario.spacecraft + [follower]
    try:
        scenario.save(args.out)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    print(f"Generated follower {follower.name!r} (target along-track separation "
          f"{follower.phasing_keeping.target_separation_km[0]:.3f} km from chief {chief.name!r}), wrote "
          f"{len(scenario.spacecraft)}-spacecraft scenario to {args.out}")
    return 0


def _numbers(text: str, counts, what: str):
    try:
        values = [float(x) for x in text.split(",")]
    except ValueError:
        raise ValueError(f"{what} must be comma-separated numbers, got {text!r}") from None
    if len(values) not in counts:
        raise ValueError(f"{what} takes {' or '.join(str(c) for c in counts)} numbers, got {len(values)}")
    if not all(math.isfinite(x) for x in values):
        raise ValueError(f"{what} must be finite numbers, got {text!r}")
    return values


def cmd_generate_roe_formation(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    names = [sc.name for sc in scenario.spacecraft]
    chief = next((sc for sc in scenario.spacecraft if sc.name == args.chief), None)
    template = next((sc for sc in scenario.spacecraft if sc.name == (args.template_spacecraft or args.chief)), None)
    if chief is None or template is None:
        missing = args.chief if chief is None else args.template_spacecraft
        print(f"ERROR: no spacecraft named {missing!r} in {args.scenario} -- this scenario has: {names}",
              file=sys.stderr)
        return 1
    if args.follower_name in names:
        print(f"ERROR: a spacecraft named {args.follower_name!r} already exists in {args.scenario}", file=sys.stderr)
        return 1
    from .engine.roe import min_radial_normal_separation, safe_formation  # numpy only
    try:
        if args.roe is not None:
            roe_m = _numbers(args.roe, (6,), "--roe")
        else:
            along, radial, cross, *phase = _numbers(args.safe, (3, 4), "--safe")
            if radial < 0.0 or cross < 0.0:
                raise ValueError(f"--safe: the radial and cross-track sizes are half-sizes of the ellipse and "
                                 f"cannot be negative, got {radial:g} and {cross:g} m (the phase sets the direction)")
            roe_m = [round(float(x), 9) + 0.0  # cos(90 deg) as 0, not 6e-17; + 0.0 drops -0.0
                     for x in safe_formation(along, radial, cross, phase[0] if phase else 90.0, 1.0)]
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        from .engine.roe_formation import generate_roe_follower
    except ImportError as exc:
        print(f"ERROR: Basilisk is not installed/built ({exc}) -- placing an ROE follower needs its mean/osculating "
              f"element mapping -- see SpaceMissionStudio/README.md", file=sys.stderr)
        return 2
    try:
        follower = generate_roe_follower(chief, template, args.follower_name, roe_m, args.control_law)
        scenario.spacecraft = scenario.spacecraft + [follower]
        scenario.save(args.out)
    except ScenarioValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    margin = min_radial_normal_separation(roe_m, 1.0)  # [m] the ROE are in metres
    print(f"Generated follower {follower.name!r} at ROE {', '.join(f'{x:g}' for x in roe_m)} m from chief "
          f"{chief.name!r} ({args.control_law} law; closest radial/cross-track approach {margin:.1f} m), wrote "
          f"{len(scenario.spacecraft)}-spacecraft scenario to {args.out}")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    try:
        from .gui.app import main as gui_main
    except ImportError as exc:
        print(f"ERROR: the GUI needs PySide6 and plotly installed "
              f"(pip install -e '.[gui]') -- {exc}", file=sys.stderr)
        return 2
    return gui_main([])


# What ``spacemissionstudio --help`` shows: for users, unlike the module
# docstring above, which is for developers.
_HELP_DESCRIPTION = """\
Check, run and analyse SpaceMissionStudio scenarios without the GUI.

examples:
  spacemissionstudio validate scenario.json
  spacemissionstudio run scenario.json --out-dir out
  spacemissionstudio lifetime scenario.json
  spacemissionstudio gui

Each command has its own help: spacemissionstudio <command> --help.
Guide: SpaceMissionStudio/docs/user-manual/command-line.md
"""


def version_text() -> str:
    """What ``spacemissionstudio --version`` prints: this tool's version,
    the Basilisk it runs with (and whether that is the qualified one) and
    Python. Read from package metadata, so Basilisk is not imported unless
    it was installed without any (a source build)."""
    versions = dependencies.dependency_versions()
    basilisk = versions.get("bsk") or dependencies.basilisk_version()
    qualified = dependencies.QUALIFIED_BASILISK_VERSION
    if basilisk is None:
        basilisk_line = "Basilisk not installed (simulations cannot run)"
    elif basilisk == qualified:
        basilisk_line = f"Basilisk {basilisk}"
    else:
        basilisk_line = f"Basilisk {basilisk} (not qualified; SpaceMissionStudio is qualified with {qualified})"
    return "\n".join([f"SpaceMissionStudio {__version__}", basilisk_line,
                      f"Python {versions['python']} on {versions['platform']}"])


class _VersionAction(argparse.Action):
    """``--version``: print :func:`version_text` to stdout and exit 0.
    Unlike argparse's own version action, the text is built only when the
    option is given, not each time the parser is."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        print(version_text())
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spacemissionstudio", description=_HELP_DESCRIPTION,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-V", "--version", action=_VersionAction,
                        help="show the SpaceMissionStudio, Basilisk and Python versions and exit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_validate = subparsers.add_parser("validate", help="validate a scenario file (no Basilisk needed)")
    p_validate.add_argument("scenario", type=Path)
    p_validate.set_defaults(func=cmd_validate)

    p_run = subparsers.add_parser("run", help="run a scenario headlessly and export results to CSV")
    p_run.add_argument("scenario", type=Path)
    p_run.add_argument("--out-dir", type=Path, default=Path("results"), help="directory to write CSV results to")
    p_run.add_argument("--oem", action="store_true",
                       help="also write each spacecraft's ephemeris as a CCSDS OEM (KVN, EME2000, UTC)")
    p_run.add_argument("--oem-stride", type=_positive_int_arg, default=1, metavar="N",
                       help="write every Nth recorded state to the OEM (default 1: all)")
    p_run.add_argument("--oem-interpolation", choices=("hermite", "lagrange"), default="hermite",
                       help="interpolation the OEM suggests, degree 7 (GMAT reads only lagrange)")
    p_run.add_argument("--vizard-save-file", type=str, default=None,
                        help="write a Vizard .bin playback file to this path (see engine/vizard.py)")
    p_run.add_argument("--vizard-live-stream", action="store_true",
                        help="live-stream to a Vizard instance already running on this machine")
    p_run.add_argument("--vizard-camera-target", type=str, default=None,
                        help="spacecraft or celestial body name for Vizard's camera to start locked on "
                             "(default: the scenario's central body -- an Earth-centered view with the orbit "
                             "tracing around it, like STK/GMAT/FreeFlyer, rather than a spacecraft-locked close-up)")
    p_run.add_argument("--vizard-no-orbit-lines", action="store_true",
                        help="don't draw each spacecraft's orbit in Vizard (on by default)")
    p_run.add_argument("--vizard-trail", action="store_true",
                        help="also draw the flown path in Vizard (builds up into a band over long runs)")
    p_run.add_argument("--vizard-ground-tracks", action="store_true", help="also draw ground tracks in Vizard")
    p_run.add_argument("--allow-scripts", action="store_true",
                       help="run the scenario's script_block commands (unrestricted Python: only for files you "
                            "trust and have read)")
    p_run.set_defaults(func=cmd_run)

    p_mc = subparsers.add_parser("monte-carlo", help="run a Monte Carlo batch and archive retained results")
    p_mc.add_argument("scenario", type=Path)
    p_mc.add_argument("--archive-dir", type=Path, default=Path("monte_carlo_results"),
                       help="directory to archive per-run parameters and retained data to (empty, or an earlier "
                            "batch with --overwrite)")
    p_mc.add_argument("--overwrite", action="store_true",
                      help="replace an earlier Monte Carlo batch in --archive-dir")
    p_mc.add_argument("--allow-scripts", action="store_true",
                      help="run the Mission Sequence's script_block commands in every run (unrestricted Python: "
                           "only for files you trust and have read)")
    p_mc.set_defaults(func=cmd_monte_carlo)

    p_life = subparsers.add_parser("lifetime", help="estimate when a spacecraft re-enters (orbit-averaged drag)")
    p_life.add_argument("scenario", type=Path)
    p_life.add_argument("--spacecraft", help="spacecraft name (default: the first)")
    p_life.add_argument("--deorbit-perigee-km", type=_finite_float_arg, default=None,
                        help="first lower the perigee to this altitude [km] with the orbit thruster")
    p_life.add_argument("--max-years", type=_max_years_arg, default=30.0,
                        help="how far ahead to look [years], more than 0 and at most 100")
    p_life.add_argument("--forecast-percentile", type=_finite_float_arg, choices=(95.0, 50.0, 5.0), default=50.0,
                        help="MSFC solar-activity percentile (ESA AD10: 50 for end of life)")
    p_life.add_argument("--drag-coeff", default="2.2", type=_drag_coeff_arg,
                        help="drag coefficient, or 'own' for the spacecraft's (default 2.2: ESA AD10 end of life)")
    p_life.set_defaults(func=cmd_lifetime)

    p_model = subparsers.add_parser("model", help="report a spacecraft's 3D model: mass properties and facets")
    p_model.add_argument("scenario", type=Path)
    p_model.add_argument("--spacecraft", help="spacecraft name (default: every one with a model)")
    p_model.add_argument("--apply", action="store_true",
                         help="write the model's mass properties and facets into the scenario file")
    p_model.add_argument("--export-obj", type=Path, metavar="PATH",
                         help="write the model as a Wavefront .obj (and .mtl) in the body frame")
    p_model.set_defaults(func=cmd_model)

    p_budget = subparsers.add_parser("budget", help="delta-V and propellant budget (ESA AD10 style)")
    p_budget.add_argument("scenario", type=Path)
    p_budget.add_argument("--spacecraft", help="spacecraft name (default: the first)")
    p_budget.add_argument("--run", action="store_true",
                          help="run the scenario first, for orbit control and formation keeping")
    # --altitudes already sweeps the launch delays at each altitude, and
    # silently overrode --launch-delays (audit L8): one or the other.
    budget_sweep = p_budget.add_mutually_exclusive_group()
    budget_sweep.add_argument("--launch-delays", action="store_true",
                              help="repeat the budget for launches 1-5 years late (ESA AD10 Sec. 5.5)")
    budget_sweep.add_argument("--altitudes", nargs="?", const="auto", type=_altitudes_arg, default=None,
                              metavar="KM,KM,...",
                              help="launch-delay sweep at each altitude [km] (default: five around the "
                                   "spacecraft's own), against the tank")
    p_budget.set_defaults(func=cmd_budget)

    p_kernels = subparsers.add_parser("kernels-status", help="fetch/check SPICE kernel cache status")
    p_kernels.set_defaults(func=cmd_kernels_status)

    p_eop = subparsers.add_parser("earth-orientation",
                                  help="IERS-based Earth orientation files: status, --fetch, --import, --rollback")
    eop_action = p_eop.add_mutually_exclusive_group()
    eop_action.add_argument("--fetch", action="store_true", help="download the current NAIF Earth PCKs (internet)")
    eop_action.add_argument("--import", dest="import_files", nargs="+", type=Path, metavar="FILE",
                            help="install Earth PCK .bpc files from disk (a .cmt next to each is read too)")
    eop_action.add_argument("--rollback", action="store_true", help="restore the previously installed files")
    p_eop.set_defaults(func=cmd_earth_orientation)

    p_small = subparsers.add_parser("small-bodies",
                                    help="small-body files (433 Eros ephemeris and shape): status, --fetch, --import")
    small_action = p_small.add_mutually_exclusive_group()
    small_action.add_argument("--fetch", action="store_true",
                              help="download the Eros ephemeris (NAIF) and shape (Basilisk support data) (internet)")
    small_action.add_argument("--import", dest="import_file", type=Path, metavar="FILE",
                              help="install the Eros ephemeris kernel eros_1900_2100.bsp from disk")
    p_small.set_defaults(func=cmd_small_bodies)

    p_ccsds = subparsers.add_parser("ccsds-validate", help="check CCSDS OPM/OMM/OEM (KVN) files (no Basilisk needed)")
    p_ccsds.add_argument("files", nargs="+", type=Path)
    p_ccsds.set_defaults(func=cmd_ccsds_validate)
    p_ccsds_out = subparsers.add_parser("ccsds-export",
                                        help="write each spacecraft's initial state as a CCSDS OPM (or OMM for a TLE)")
    p_ccsds_out.add_argument("scenario", type=Path)
    p_ccsds_out.add_argument("--out", type=Path, required=True, help="output directory")
    p_ccsds_out.set_defaults(func=cmd_ccsds_export)
    p_ccsds_in = subparsers.add_parser("ccsds-import", help="set a spacecraft's orbit from a CCSDS OPM or TLE-based OMM")
    p_ccsds_in.add_argument("message", type=Path)
    p_ccsds_in.add_argument("scenario", type=Path)
    p_ccsds_in.add_argument("--spacecraft", required=True)
    p_ccsds_in.add_argument("--set-epoch", action="store_true", help="move the scenario epoch to the OPM's epoch")
    p_ccsds_in.add_argument("--out", type=Path, help="write the updated scenario here (default: overwrite)")
    p_ccsds_in.set_defaults(func=cmd_ccsds_import)

    p_fsw = subparsers.add_parser("export-fsw",
                                  help="export a spacecraft's flight software as a standalone C project (needs Basilisk)")
    p_fsw.add_argument("scenario", type=Path)
    p_fsw.add_argument("--spacecraft", required=True)
    p_fsw.add_argument("--out", type=Path, required=True, help="the export folder (empty, or an earlier export)")
    p_fsw.add_argument("--steps", type=int, default=None, help="flight-software steps to record for the tests (200)")
    p_fsw.add_argument("--overwrite", action="store_true", help="replace an earlier export in --out")
    p_fsw.add_argument("--record", action="store_true", help="record the export in the scenario file")
    p_fsw.set_defaults(func=cmd_export_fsw)
    p_fsw_status = subparsers.add_parser("fsw-status",
                                         help="check the scenario's recorded flight-software exports (stale or not)")
    p_fsw_status.add_argument("scenario", type=Path)
    p_fsw_status.set_defaults(func=cmd_fsw_status)

    p_sil = subparsers.add_parser("sil", help="run a spacecraft's flight software as an external program in the "
                                              "loop and compare it with the simulation's own (needs Basilisk)")
    p_sil.add_argument("scenario", type=Path)
    p_sil.add_argument("--spacecraft", required=True)
    p_sil.add_argument("--binary", type=Path, required=True,
                       help="the program: an export's fsw_host or fsw_adapter_host, or any program following "
                            "SIL_CONTRACT.md; it is run as <binary> sil <address>")
    p_sil.add_argument("--transport", choices=("auto", "unix", "tcp"), default="auto")
    p_sil.add_argument("--deadline-ms", type=_finite_float_arg, default=None,
                       help="an answer later than this counts as a dropped step (default: none, pure lock-step)")
    p_sil.add_argument("--step-timeout", type=_finite_float_arg, default=10.0, help="seconds without any answer before failing")
    p_sil.add_argument("--handshake-timeout", type=_finite_float_arg, default=30.0, help="seconds to connect and say HELLO")
    p_sil.add_argument("--report", type=Path, help="write the full report (JSON) here")
    p_sil.add_argument("--residuals-csv", type=Path, help="write the sampled residuals (CSV) here")
    p_sil.add_argument("--max-error", type=_finite_float_arg, default=None,
                       help="exit with status 2 if any residual is larger, or an output was never written")
    p_sil.set_defaults(func=cmd_sil)

    p_sw = subparsers.add_parser("spaceweather-resolve",
                                  help="resolve space weather for a scenario without running it (no Basilisk needed)")
    p_sw.add_argument("scenario", type=Path)
    p_sw.set_defaults(func=cmd_spaceweather_resolve)

    p_const = subparsers.add_parser(
        "generate-constellation",
        help="generate a Walker-pattern constellation from a template scenario (no Basilisk needed)",
    )
    p_const.add_argument("scenario", type=Path, help="scenario file to load the template spacecraft/gravity from")
    p_const.add_argument("--out", type=Path, required=True, help="scenario file to write the result to")
    p_const.add_argument("--template-spacecraft", type=str, default=None,
                          help="name of the spacecraft to clone into the constellation (required if the input "
                               "scenario has more than one spacecraft)")
    p_const.add_argument("--total-satellites", type=int, required=True, help="T -- total satellite count")
    p_const.add_argument("--planes", type=int, required=True, help="P -- number of orbital planes")
    p_const.add_argument("--phasing-factor", type=int, required=True, help="F -- Walker phasing factor, 0 <= F < P")
    p_const.add_argument("--altitude-km", type=_finite_float_arg, required=True, help="circular-orbit altitude [km]")
    p_const.add_argument("--inclination-deg", type=_finite_float_arg, required=True, help="orbit inclination [deg]")
    p_const.add_argument("--pattern", choices=["delta", "star"], default="delta",
                          help="Walker-Delta (RAAN spread over 360deg) or Walker-Star (180deg); default delta")
    p_const.add_argument("--eccentricity", type=_finite_float_arg, default=0.0)
    p_const.add_argument("--arg-periapsis-deg", type=_finite_float_arg, default=0.0)
    p_const.add_argument("--raan-offset-deg", type=_finite_float_arg, default=0.0,
                          help="rotates the whole constellation's RAAN reference")
    p_const.add_argument("--name-prefix", type=str, default="sat",
                          help="generated spacecraft are named '{prefix}-{plane:02d}-{slot:02d}'")
    p_const.add_argument("--append", action="store_true",
                          help="add the generated satellites to the template scenario's existing spacecraft "
                               "instead of replacing them")
    p_const.set_defaults(func=cmd_generate_constellation)

    p_phasing = subparsers.add_parser(
        "generate-phasing-formation",
        help="generate a follower spacecraft holding a phasing formation with an existing chief "
             "(needs a Basilisk build -- computes the follower's orbit via a real Hill-frame transform)",
    )
    p_phasing.add_argument("scenario", type=Path, help="scenario file to load the chief/template spacecraft from")
    p_phasing.add_argument("--out", type=Path, required=True, help="scenario file to write the result to")
    p_phasing.add_argument("--chief", type=str, required=True, help="name of the existing chief spacecraft")
    p_phasing.add_argument("--follower-name", type=str, required=True, help="name for the new follower spacecraft")
    p_phasing.add_argument("--template-spacecraft", type=str, default=None,
                            help="name of the spacecraft to clone the follower's non-orbit fields from "
                                 "(default: the chief itself)")
    p_phasing.add_argument("--radial-km", type=_finite_float_arg, default=0.0,
                            help="Hill-frame radial (R) offset at epoch [km] -- starting geometry only, not "
                                 "actively held (see PhasingKeepingController's own docstring)")
    p_phasing.add_argument("--along-track-km", type=_finite_float_arg, required=True,
                            help="Hill-frame along-track (T) offset at epoch [km] -- becomes "
                                 "phasing_keeping.target_separation_km, the ACTIVELY HELD separation")
    p_phasing.add_argument("--cross-track-km", type=_finite_float_arg, default=0.0,
                            help="Hill-frame cross-track (N) offset at epoch [km] -- starting geometry only, "
                                 "not actively held")
    p_phasing.add_argument("--reconfiguration-interval-days", type=_finite_float_arg, default=90.0)
    p_phasing.add_argument("--tolerance-fraction", type=_finite_float_arg, default=0.10)
    p_phasing.add_argument("--restore-tolerance-fraction", type=_finite_float_arg, default=0.02)
    p_phasing.add_argument("--correction-window-days", type=_finite_float_arg, default=3.0)
    p_phasing.add_argument("--max-drift-days", type=_finite_float_arg, default=90.0)
    p_phasing.add_argument("--max-delta-semi-major-axis-km", type=_finite_float_arg, default=3.0)
    p_phasing.add_argument("--station-keeping-target-altitude-km", type=_finite_float_arg, default=None,
                            help="default: derived from the chief's own altitude at generation time")
    p_phasing.add_argument("--station-keeping-deadband-km", type=_finite_float_arg, default=2.0)
    p_phasing.add_argument("--thrust-n", type=_finite_float_arg, default=0.05, help="shared thruster thrust [N]")
    p_phasing.add_argument("--isp-s", type=_finite_float_arg, default=1500.0, help="shared thruster specific impulse [s]")
    p_phasing.add_argument("--propellant-kg", type=_finite_float_arg, default=5.0, help="shared tank propellant [kg]")
    p_phasing.add_argument("--eclipse-sunlit-threshold", type=_finite_float_arg, default=0.99,
                            help="minimum shadow factor [-] (1.0 = full sunlight) before a station-keeping "
                                 "reboost burn may fire")
    p_phasing.add_argument("--min-on-time-s", type=_finite_float_arg, default=0.0,
                            help="shared thruster's minimum firing duration [s] (minimum impulse bit = "
                                 "thrust x this); 0 = ideal")
    p_phasing.add_argument("--eccentricity-neutral-burns", action="store_true",
                            help="gate firings so long eclipse-interrupted burns don't change eccentricity")
    p_phasing.add_argument("--control-law", choices=PHASING_CONTROL_LAWS, default="drift_orbit",
                            help="drift_orbit (occasional burns), mean_oe (Basilisk meanOEFeedback) or "
                                 "hill_pd (Basilisk hillFrameRelativeControl, close formations); see "
                                 "the User Manual's 'Formation control laws'")
    p_phasing.set_defaults(func=cmd_generate_phasing_formation)

    p_roe = subparsers.add_parser(
        "generate-roe-formation",
        help="generate a follower in a formation of relative orbital elements (ROE) with an existing chief "
             "(needs a Basilisk build -- places it with the mean/osculating element mapping)",
    )
    p_roe.add_argument("scenario", type=Path, help="scenario file to load the chief/template spacecraft from")
    p_roe.add_argument("--out", type=Path, required=True, help="scenario file to write the result to")
    p_roe.add_argument("--chief", type=str, required=True, help="name of the existing chief spacecraft")
    p_roe.add_argument("--follower-name", type=str, required=True, help="name for the new follower spacecraft")
    p_roe.add_argument("--template-spacecraft", type=str, default=None,
                       help="spacecraft to clone the follower from, with its station keeping (default: the chief)")
    where = p_roe.add_mutually_exclusive_group(required=True)
    where.add_argument("--roe", type=str, help="six ROE times the chief's semi-major axis [m]: "
                                               "a_da,a_dlambda,a_dex,a_dey,a_dix,a_diy")
    where.add_argument("--safe", type=str, help="a passively safe formation [m, deg]: along,radial,cross[,phase] "
                                                "(parallel e/i vectors; phase 90 deg by default)")
    p_roe.add_argument("--control-law", choices=ROE_CONTROL_LAWS, default="impulsive",
                       help="impulsive (the tool's burns, planned with the J2 model) or continuous (Basilisk "
                            "meanOEFeedback)")
    p_roe.set_defaults(func=cmd_generate_roe_formation)

    p_gui = subparsers.add_parser("gui", help="launch the PySide6 GUI shell")
    p_gui.set_defaults(func=cmd_gui)

    return parser


def main(argv: list | None = None) -> int:
    # First thing, before anything else can fail -- see logging_setup's
    # own module docstring for why. Also covers `spacemissionstudio gui`
    # (cmd_gui() dispatches into gui.app.main(), which calls this same,
    # idempotent function itself too -- see its own docstring -- so
    # direct-launching the GUI via `python3 -m spacemissionstudio.gui.app`
    # gets it either way).
    if (sys.argv[1:] if argv is None else list(argv)) in (["--version"], ["-V"]):
        print(version_text())  # nothing to log: no log file and no "Logging to" line for a version query
        return 0
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:  # Ctrl-C: a message and the usual status, not a traceback (audit L10)
        print("Interrupted.", file=sys.stderr)
        return 130
    except OSError as exc:
        # A file a command could not write or read that the command itself
        # does not report (saves, the SIL report, the Monte Carlo sidecar;
        # audit L9): one line and status 3, not a traceback.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 -- a fault, not the input: its own status, the traceback in the log
        # Status 1 said "invalid input" (ICD-02), so scripts could not tell a
        # bug from a bad file (audit R13).
        log = get_log_file_path()
        if log is None:  # no log file to hold the traceback: it is the only record left
            traceback.print_exc()
        else:  # DEBUG: the log file's level, below the terminal's
            logging.getLogger(__name__).debug("Internal error in %r", args.command, exc_info=True)
        where = f"; the details are in {log}" if log else ""
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}{where}. Please report it.", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
