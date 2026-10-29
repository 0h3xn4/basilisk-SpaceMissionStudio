"""Tests for spacemissionstudio.cli. ``validate`` and ``spaceweather-resolve``
need no Basilisk build and run unconditionally; the ``run``/
``kernels-status`` tests here specifically check the graceful
no-Basilisk error path, so they're skipped on a machine that DOES have
Basilisk (where that premise doesn't hold) -- see ``conftest.py`` for the
general ``requires_basilisk``/``requires_gui`` markers this mirrors
inline for the same reason.
"""

import importlib.util
import json

import pytest

from spacemissionstudio import cli

_BASILISK_AVAILABLE = importlib.util.find_spec("Basilisk") is not None


def _write_scenario(path, **overrides):
    from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SpacecraftConfig

    scenario = Scenario(
        name=overrides.pop("name", "cli test scenario"),
        epoch_utc=overrides.pop("epoch_utc", "2030-01-01T00:00:00"),
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        spacecraft=[SpacecraftConfig(
            name="sat-1",
            orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
        )],
        **overrides,
    )
    scenario.save(path)
    return scenario


def test_validate_accepts_a_valid_scenario(tmp_path, capsys):
    """validate on a valid scenario exits 0 and prints OK."""
    path = tmp_path / "scenario.json"
    _write_scenario(path)
    rc = cli.main(["validate", str(path)])
    assert rc == 0
    assert "OK:" in capsys.readouterr().out


def test_validate_rejects_an_invalid_scenario(tmp_path, capsys):
    """validate on a scenario with an empty name exits 1 and prints INVALID to
    stderr."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 1, "name": "", "epoch_utc": "2030-01-01T00:00:00"}))
    rc = cli.main(["validate", str(path)])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_validate_rejects_malformed_json(tmp_path, capsys):
    """validate on a file that is not JSON exits 1 and prints INVALID to
    stderr."""
    path = tmp_path / "malformed.json"
    path.write_text("{not json")
    rc = cli.main(["validate", str(path)])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_spaceweather_resolve_reports_resolution(tmp_path, capsys):
    """spaceweather-resolve exits 0 and says what the scenario's space weather
    resolved to, from the bundled CelesTrak SW-All data."""
    path = tmp_path / "scenario.json"
    _write_scenario(path)
    rc = cli.main(["spaceweather-resolve", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Resolved to:" in out
    assert "From real data:" in out and "SW-All" in out


def test_spaceweather_resolve_reports_a_clean_error_instead_of_a_traceback(tmp_path, capsys):
    """Regression test for an audit finding: cmd_spaceweather_resolve() had
    no exception handling around sw.resolve(), unlike every other command
    in this file -- a SpaceWeatherError (e.g. source="local_file" pointing
    at a missing file, which schema validation allows since it only
    requires the path string to be non-empty) used to propagate as a raw
    traceback instead of this file's "ERROR: ..." + specific exit code
    convention.
    """
    from spacemissionstudio.schema.scenario import SpaceWeatherConfig

    path = tmp_path / "scenario.json"
    _write_scenario(path, space_weather=SpaceWeatherConfig(
        source="local_file", local_file_path=str(tmp_path / "does_not_exist.csv")))

    rc = cli.main(["spaceweather-resolve", str(path)])

    assert rc == 3
    assert "ERROR: space weather resolve failed" in capsys.readouterr().err


def test_generate_constellation_writes_new_scenario(tmp_path, capsys):
    """generate-constellation writes a scenario with 6 uniquely named
    spacecraft on classical elements and says how many it generated."""
    path = tmp_path / "template.json"
    _write_scenario(path)
    out_path = tmp_path / "constellation.json"

    rc = cli.main([
        "generate-constellation", str(path), "--out", str(out_path),
        "--total-satellites", "6", "--planes", "2", "--phasing-factor", "1",
        "--altitude-km", "700", "--inclination-deg", "98.0",
    ])
    assert rc == 0
    assert "Generated 6 spacecraft" in capsys.readouterr().out

    from spacemissionstudio.schema import load_scenario

    generated = load_scenario(out_path)
    assert len(generated.spacecraft) == 6
    assert len({sc.name for sc in generated.spacecraft}) == 6
    assert all(sc.orbit.type == "classical_elements" for sc in generated.spacecraft)



@pytest.mark.skipif(not _BASILISK_AVAILABLE, reason="needs Basilisk (mean to osculating elements)")
def test_generate_constellation_places_mean_elements_when_the_run_models_j2(tmp_path):
    """Audit E4: with spherical-harmonics gravity (degree >= 2) the slots
    get equal mean semi-major axes, so their osculating ones differ and
    they are written with their true anomaly; with a point mass the
    pattern is written as it is."""
    from spacemissionstudio.schema import GravityConfig, load_scenario

    for degree, expected_anomaly in ((10, "true"), (0, "mean")):
        path = tmp_path / f"template_{degree}.json"
        _write_scenario(path)
        scenario = load_scenario(path)
        scenario.gravity = GravityConfig(central_body="earth", central_body_degree=degree)
        scenario.save(path)
        out_path = tmp_path / f"constellation_{degree}.json"
        assert cli.main([
            "generate-constellation", str(path), "--out", str(out_path),
            "--total-satellites", "4", "--planes", "1", "--phasing-factor", "0",
            "--altitude-km", "550", "--inclination-deg", "53.0",
        ]) == 0
        orbits = [sc.orbit for sc in load_scenario(out_path).spacecraft]
        assert {orbit.anomaly_type for orbit in orbits} == {expected_anomaly}
        spread_m = (max(o.semi_major_axis_km for o in orbits) - min(o.semi_major_axis_km for o in orbits)) * 1e3
        assert (spread_m > 1000.0) if degree else (spread_m == 0.0)  # [m] equal mean, unequal osculating

def test_generate_constellation_append_keeps_existing_spacecraft(tmp_path, capsys):
    """generate-constellation --append keeps the original spacecraft beside the
    generated ones."""
    path = tmp_path / "template.json"
    _write_scenario(path)  # one spacecraft named "sat-1"
    out_path = tmp_path / "constellation.json"

    rc = cli.main([
        "generate-constellation", str(path), "--out", str(out_path), "--append",
        "--total-satellites", "2", "--planes", "1", "--phasing-factor", "0",
        "--altitude-km", "700", "--inclination-deg", "0.0",
    ])
    assert rc == 0

    from spacemissionstudio.schema import load_scenario

    generated = load_scenario(out_path)
    assert len(generated.spacecraft) == 3  # original sat-1 + 2 generated
    assert "sat-1" in {sc.name for sc in generated.spacecraft}


def _write_scenario_with_spacecraft(path, spacecraft):
    from spacemissionstudio.schema import GravityConfig, Scenario

    scenario = Scenario(name="cli test scenario", epoch_utc="2030-01-01T00:00:00",
                         gravity=GravityConfig(central_body="earth", central_body_degree=0), spacecraft=spacecraft)
    scenario.save(path)
    return scenario


def test_generate_constellation_requires_template_spacecraft_flag_when_ambiguous(tmp_path, capsys):
    """With two spacecraft in the file and no --template-spacecraft,
    generate-constellation exits 1 asking for the flag."""
    from spacemissionstudio.schema import OrbitIC, SpacecraftConfig

    path = tmp_path / "template.json"
    _write_scenario_with_spacecraft(path, [
        SpacecraftConfig(name="a", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                  velocity_km_s=[0, 7.5, 0])),
        SpacecraftConfig(name="b", orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0],
                                                  velocity_km_s=[0, 7.5, 0])),
    ])
    rc = cli.main([
        "generate-constellation", str(path), "--out", str(tmp_path / "out.json"),
        "--total-satellites", "2", "--planes", "1", "--phasing-factor", "0",
        "--altitude-km", "700", "--inclination-deg", "0.0",
    ])
    assert rc == 1
    assert "--template-spacecraft" in capsys.readouterr().err


def test_generate_constellation_uses_named_template_spacecraft(tmp_path, capsys):
    """generate-constellation copies the spacecraft named by
    --template-spacecraft."""
    from spacemissionstudio.schema import OrbitIC, SpacecraftConfig

    path = tmp_path / "template.json"
    _write_scenario_with_spacecraft(path, [
        SpacecraftConfig(name="a", dry_mass_kg=10.0,
                          orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0])),
        SpacecraftConfig(name="b", dry_mass_kg=99.0,
                          orbit=OrbitIC(type="cartesian", position_km=[7000, 0, 0], velocity_km_s=[0, 7.5, 0])),
    ])
    out_path = tmp_path / "out.json"
    rc = cli.main([
        "generate-constellation", str(path), "--out", str(out_path), "--template-spacecraft", "b",
        "--total-satellites", "2", "--planes", "1", "--phasing-factor", "0",
        "--altitude-km", "700", "--inclination-deg", "0.0",
    ])
    assert rc == 0

    from spacemissionstudio.schema import load_scenario

    generated = load_scenario(out_path)
    assert all(sc.dry_mass_kg == 99.0 for sc in generated.spacecraft)


def test_generate_constellation_rejects_unknown_template_spacecraft_name(tmp_path, capsys):
    """A --template-spacecraft the file does not have exits 1, naming it."""
    path = tmp_path / "template.json"
    _write_scenario(path)
    rc = cli.main([
        "generate-constellation", str(path), "--out", str(tmp_path / "out.json"),
        "--template-spacecraft", "does-not-exist",
        "--total-satellites", "2", "--planes", "1", "--phasing-factor", "0",
        "--altitude-km", "700", "--inclination-deg", "0.0",
    ])
    assert rc == 1
    assert "does-not-exist" in capsys.readouterr().err


def test_generate_constellation_rejects_invalid_walker_parameters(tmp_path, capsys):
    """10 satellites in 3 planes (not divisible) exits 1 with INVALID."""
    path = tmp_path / "template.json"
    _write_scenario(path)
    rc = cli.main([
        "generate-constellation", str(path), "--out", str(tmp_path / "out.json"),
        "--total-satellites", "10", "--planes", "3", "--phasing-factor", "0",  # 10 not divisible by 3
        "--altitude-km", "700", "--inclination-deg", "0.0",
    ])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


@pytest.mark.usefixtures("basilisk_unavailable")
def test_run_without_basilisk_reports_clear_error(tmp_path, capsys):
    """Without Basilisk, run exits 2 saying Basilisk is not installed."""
    path = tmp_path / "scenario.json"
    _write_scenario(path)
    rc = cli.main(["run", str(path), "--out-dir", str(tmp_path / "out")])
    assert rc == 2
    assert "Basilisk is not installed" in capsys.readouterr().err


@pytest.mark.usefixtures("basilisk_unavailable")
def test_kernels_status_without_basilisk_reports_clear_error(capsys):
    """Without Basilisk, kernels-status exits 2 saying Basilisk is not
    installed."""
    rc = cli.main(["kernels-status"])
    assert rc == 2
    assert "Basilisk is not installed" in capsys.readouterr().err


def _script_sequence(marker="unused"):
    from spacemissionstudio.schema.command import Command

    return [Command(kind="propagate", params={"stop_condition": "duration", "duration_days": 0.001}),
            Command(kind="script_block", params={"code": f"open({str(marker)!r}, 'w').write('ran')"})]


def test_validate_notes_script_blocks(tmp_path, capsys):
    """validate says a scenario has script blocks and that run needs
    --allow-scripts for them (SRS-S-03)."""
    path = tmp_path / "scenario.json"
    _write_scenario(path, mission_sequence=_script_sequence())
    assert cli.main(["validate", str(path)]) == 0
    assert "NOTE: 1 script_block(s) (mission_sequence[1])" in capsys.readouterr().out


def test_run_refuses_script_blocks_without_allow_scripts(tmp_path, capsys):
    """Without --allow-scripts, run stops before building anything, with
    exit code 1 and the block's path (SRS-S-03)."""
    path, marker = tmp_path / "scenario.json", tmp_path / "marker.txt"
    _write_scenario(path, mission_sequence=_script_sequence(marker))
    assert cli.main(["run", str(path), "--out-dir", str(tmp_path / "out")]) == 1
    assert not marker.exists()
    err = capsys.readouterr().err
    assert "mission_sequence[1]" in err and "--allow-scripts" in err
    assert not (tmp_path / "out").exists()


@pytest.mark.requires_basilisk
def test_run_with_allow_scripts_runs_them(tmp_path, capsys):
    """With --allow-scripts the script block runs."""
    path, marker = tmp_path / "scenario.json", tmp_path / "marker.txt"
    _write_scenario(path, mission_sequence=_script_sequence(marker))
    assert cli.main(["run", str(path), "--out-dir", str(tmp_path / "out"), "--allow-scripts"]) == 0
    assert marker.read_text() == "ran"


def test_run_rejects_both_vizard_flags_at_once(tmp_path, capsys):
    """run with both --vizard-save-file and --vizard-live-stream exits 1: at
    most one is allowed."""
    path = tmp_path / "scenario.json"
    _write_scenario(path)
    rc = cli.main([
        "run", str(path), "--out-dir", str(tmp_path / "out"),
        "--vizard-save-file", str(tmp_path / "viz.bin"), "--vizard-live-stream",
    ])
    assert rc == 1
    assert "at most one of" in capsys.readouterr().err


def test_help_opens_with_a_one_line_purpose_for_users():
    """``spacemissionstudio --help`` starts with what the tool does, examples
    and where the guide is, not the module's developer docstring."""
    help_text = cli.build_parser().format_help()
    description = help_text.split("\n\n")[1]
    assert description == "Check, run and analyse SpaceMissionStudio scenarios without the GUI."
    assert "spacemissionstudio run scenario.json --out-dir out" in help_text
    assert "docs/user-manual/command-line.md" in help_text
    assert "SimulationService" not in help_text  # internal names stay in the docstring


def test_version_prints_tool_basilisk_and_python_versions(capsys):
    """``spacemissionstudio --version`` (and ``-V``) prints three lines:
    the tool's version, the Basilisk line and Python, exits 0, and logs
    nothing (no "Logging to" line on stderr)."""
    from spacemissionstudio import __version__

    for flag in ("--version", "-V"):
        assert cli.main([flag]) == 0
        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        assert len(lines) == 3
        assert lines[0] == f"SpaceMissionStudio {__version__}"
        assert lines[1].startswith("Basilisk ")
        assert lines[2].startswith("Python ")
        assert captured.err == ""


def test_version_says_when_basilisk_is_missing_or_not_qualified(monkeypatch):
    """The Basilisk line names the qualified version when another one is
    installed, and says simulations cannot run when none is."""
    from spacemissionstudio import dependencies

    base = {"python": "3.11.0", "platform": "linux x86_64"}
    qualified = dependencies.QUALIFIED_BASILISK_VERSION
    monkeypatch.setattr(dependencies, "dependency_versions", lambda: {**base, "bsk": qualified})
    assert cli.version_text().splitlines()[1] == f"Basilisk {qualified}"

    monkeypatch.setattr(dependencies, "dependency_versions", lambda: {**base, "bsk": "9.9.9"})
    assert cli.version_text().splitlines()[1] == (
        f"Basilisk 9.9.9 (not qualified; SpaceMissionStudio is qualified with {qualified})")

    monkeypatch.setattr(dependencies, "dependency_versions", lambda: dict(base))
    monkeypatch.setattr(dependencies, "basilisk_version", lambda: None)
    assert cli.version_text().splitlines()[1] == "Basilisk not installed (simulations cannot run)"


def test_version_before_a_command_prints_the_versions_and_exits(capsys):
    """``--version`` given with other arguments goes through the parser:
    it still prints the versions to stdout and exits with status 0."""
    with pytest.raises(SystemExit) as exit_info:
        cli.build_parser().parse_args(["--version", "validate", "scenario.json"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("SpaceMissionStudio ")


def test_run_parses_vizard_camera_and_orbit_line_flags():
    """run parses --vizard-camera-target and --vizard-no-orbit-lines."""
    parser = cli.build_parser()
    args = parser.parse_args([
        "run", "scenario.json",
        "--vizard-live-stream", "--vizard-camera-target", "sat-1", "--vizard-no-orbit-lines",
    ])
    assert args.vizard_camera_target == "sat-1"
    assert args.vizard_no_orbit_lines is True


def test_run_vizard_camera_target_defaults_to_none():
    """Without the flags, run has no Vizard camera target and draws orbit
    lines."""
    parser = cli.build_parser()
    args = parser.parse_args(["run", "scenario.json"])
    assert args.vizard_camera_target is None
    assert args.vizard_no_orbit_lines is False


def test_station_keeping_summary_reports_delta_v_and_propellant_used(capsys):
    """The station-keeping summary gives the final cumulative delta-V, the
    propellant used and the propellant left."""
    import numpy as np

    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SpacecraftConfig, StationKeepingConfig

    scenario = Scenario(
        name="sk test", epoch_utc="2030-01-01T00:00:00", gravity=GravityConfig(),
        spacecraft=[SpacecraftConfig(
            name="sat-1",
            orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
            station_keeping=StationKeepingConfig(target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01,
                                                  isp_s=1500.0, propellant_kg=2.0),
        )],
    )
    result = ResultSet(scenario_name="sk test")
    t = np.array([0.0, 100.0, 200.0])
    result.add(TimeSeries("sat-1.station_keeping.delta_v", t, ("cumulative_delta_v",),
                           np.array([[0.0], [0.5], [1.25]]), units="m/s"))
    result.add(TimeSeries("sat-1.station_keeping.propellant_remaining", t, ("propellant_remaining",),
                           np.array([[2.0], [1.9], [1.75]]), units="kg"))

    cli._print_station_keeping_summary(scenario, result)
    out = capsys.readouterr().out
    assert "sat-1" in out
    assert "1.250 m/s delta-V" in out
    assert "0.250 kg propellant used" in out
    assert "1.750 kg remaining" in out


def test_station_keeping_summary_includes_phasing_delta_v_breakdown(capsys):
    """A phasing follower's summary adds its altitude-keeping and phasing
    delta-V and lists both; the chief, without station keeping, is not
    summarized."""
    import numpy as np

    from spacemissionstudio.engine.results import ResultSet, TimeSeries
    from spacemissionstudio.schema import (
        GravityConfig,
        OrbitIC,
        PhasingKeepingConfig,
        Scenario,
        SpacecraftConfig,
        StationKeepingConfig,
    )

    scenario = Scenario(
        name="phasing test", epoch_utc="2030-01-01T00:00:00", gravity=GravityConfig(),
        spacecraft=[
            SpacecraftConfig(
                name="chief",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.0,
                              inclination_deg=0.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
            ),
            SpacecraftConfig(
                name="follower",
                orbit=OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.0,
                              inclination_deg=0.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=10.0),
                station_keeping=StationKeepingConfig(target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01,
                                                      isp_s=1500.0, propellant_kg=2.0),
                phasing_keeping=PhasingKeepingConfig(chief_spacecraft="chief", target_separation_km=[100.0]),
            ),
        ],
    )
    result = ResultSet(scenario_name="phasing test")
    t = np.array([0.0, 100.0])
    result.add(TimeSeries("follower.station_keeping.delta_v", t, ("cumulative_delta_v",),
                           np.array([[0.0], [1.0]]), units="m/s"))
    result.add(TimeSeries("follower.station_keeping.propellant_remaining", t, ("propellant_remaining",),
                           np.array([[2.0], [1.8]]), units="kg"))
    result.add(TimeSeries("follower.phasing_keeping.delta_v", t, ("cumulative_delta_v",),
                           np.array([[0.0], [0.5]]), units="m/s"))

    cli._print_station_keeping_summary(scenario, result)
    out = capsys.readouterr().out
    assert "follower: 1.500 m/s delta-V" in out  # 1.0 (altitude) + 0.5 (phasing)
    assert "altitude-keeping: 1.000 m/s" in out
    assert "phasing vs. 'chief': 0.500 m/s" in out
    assert out.count("m/s delta-V") == 1  # chief itself has no station_keeping -- not summarized


def test_station_keeping_summary_skips_spacecraft_without_the_config(capsys):
    """A spacecraft without station keeping prints no summary."""
    from spacemissionstudio.engine.results import ResultSet
    from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SpacecraftConfig

    scenario = Scenario(
        name="no sk", epoch_utc="2030-01-01T00:00:00", gravity=GravityConfig(),
        spacecraft=[SpacecraftConfig(
            name="sat-1",
            orbit=OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
        )],
    )
    result = ResultSet(scenario_name="no sk")

    cli._print_station_keeping_summary(scenario, result)
    assert capsys.readouterr().out == ""


def test_monte_carlo_rejects_scenario_without_enabled_flag(tmp_path, capsys):
    """monte-carlo on a scenario with Monte Carlo off exits 1 saying so."""
    path = tmp_path / "scenario.json"
    _write_scenario(path)  # monte_carlo.enabled defaults to False
    rc = cli.main(["monte-carlo", str(path), "--archive-dir", str(tmp_path / "mc")])
    assert rc == 1
    assert "monte_carlo.enabled is false" in capsys.readouterr().err


@pytest.mark.usefixtures("basilisk_unavailable")
def test_monte_carlo_without_basilisk_reports_clear_error(tmp_path, capsys):
    """Without Basilisk, monte-carlo exits 2 saying Basilisk is not
    installed."""
    from spacemissionstudio.schema import MonteCarloConfig

    path = tmp_path / "scenario.json"
    _write_scenario(path, monte_carlo=MonteCarloConfig(enabled=True, num_runs=2))
    rc = cli.main(["monte-carlo", str(path), "--archive-dir", str(tmp_path / "mc")])
    assert rc == 2
    assert "Basilisk is not installed" in capsys.readouterr().err


def test_no_subcommand_is_an_error():
    """The command line without a subcommand exits with an error."""
    with pytest.raises(SystemExit):
        cli.main([])


def test_unknown_scenario_file_is_a_clear_error(tmp_path, capsys):
    """validate on a file that does not exist exits 1 with INVALID."""
    rc = cli.main(["validate", str(tmp_path / "does_not_exist.json")])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def _write_chief_scenario(path, **overrides):
    from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SpacecraftConfig

    scenario = Scenario(
        name=overrides.pop("name", "cli phasing test scenario"),
        epoch_utc=overrides.pop("epoch_utc", "2030-01-01T00:00:00"),
        # "sun" is required: station_keeping's eclipse gate needs a sun
        # ephemeris (Scenario.validate() rejects station_keeping without
        # it) -- see schema.scenario's own cross-field check.
        gravity=GravityConfig(central_body="earth", central_body_degree=0, third_body_perturbers=["sun"]),
        spacecraft=[SpacecraftConfig(
            name="chief-1", dry_mass_kg=100.0,
            orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.001,
                          inclination_deg=45.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
        )],
        **overrides,
    )
    scenario.save(path)
    return scenario


@pytest.mark.skipif(not _BASILISK_AVAILABLE, reason="needs a real Basilisk build (real Hill-frame transform)")
def test_generate_phasing_formation_writes_new_scenario(tmp_path, capsys):
    """generate-phasing-formation adds a follower with phasing keeping 50 km
    from the chief, and station keeping, after the chief."""
    path = tmp_path / "chief.json"
    _write_chief_scenario(path)
    out_path = tmp_path / "formation.json"

    rc = cli.main([
        "generate-phasing-formation", str(path), "--out", str(out_path),
        "--chief", "chief-1", "--follower-name", "follower-1", "--along-track-km", "50",
    ])
    assert rc == 0
    assert "Generated follower 'follower-1'" in capsys.readouterr().out

    from spacemissionstudio.schema import load_scenario

    generated = load_scenario(out_path)
    assert [sc.name for sc in generated.spacecraft] == ["chief-1", "follower-1"]
    follower = generated.spacecraft[1]
    assert follower.phasing_keeping.chief_spacecraft == "chief-1"
    assert follower.phasing_keeping.target_separation_km == [50.0]
    assert follower.station_keeping is not None


@pytest.mark.skipif(not _BASILISK_AVAILABLE, reason="needs a real Basilisk build (real Hill-frame transform)")
def test_generate_phasing_formation_takes_a_control_law(tmp_path):
    """--control-law puts a Basilisk formation law on the generated follower."""
    path = tmp_path / "chief.json"
    _write_chief_scenario(path)
    out_path = tmp_path / "formation.json"
    rc = cli.main([
        "generate-phasing-formation", str(path), "--out", str(out_path), "--chief", "chief-1",
        "--follower-name", "follower-1", "--along-track-km", "1", "--control-law", "hill_pd",
    ])
    assert rc == 0

    from spacemissionstudio.schema import load_scenario

    assert load_scenario(out_path).spacecraft[1].phasing_keeping.control_law == "hill_pd"


@pytest.mark.skipif(not _BASILISK_AVAILABLE, reason="needs a real Basilisk build (real Hill-frame transform)")
def test_generate_phasing_formation_rejects_zero_along_track_km(tmp_path, capsys):
    """generate-phasing-formation with a 0 km separation exits 1 with
    INVALID."""
    path = tmp_path / "chief.json"
    _write_chief_scenario(path)
    rc = cli.main([
        "generate-phasing-formation", str(path), "--out", str(tmp_path / "out.json"),
        "--chief", "chief-1", "--follower-name", "follower-1", "--along-track-km", "0",
    ])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_generate_phasing_formation_rejects_unknown_chief_name(tmp_path, capsys):
    """generate-phasing-formation with a chief the file does not have exits 1
    with ERROR."""
    path = tmp_path / "chief.json"
    _write_chief_scenario(path)
    rc = cli.main([
        "generate-phasing-formation", str(path), "--out", str(tmp_path / "out.json"),
        "--chief", "does-not-exist", "--follower-name", "follower-1", "--along-track-km", "50",
    ])
    assert rc == 1
    assert "ERROR" in capsys.readouterr().err


@pytest.mark.usefixtures("basilisk_unavailable")
def test_generate_phasing_formation_without_basilisk_reports_clear_error(tmp_path, capsys):
    """Without Basilisk, generate-phasing-formation exits 2 saying Basilisk is
    not installed."""
    path = tmp_path / "chief.json"
    _write_chief_scenario(path)
    rc = cli.main([
        "generate-phasing-formation", str(path), "--out", str(tmp_path / "out.json"),
        "--chief", "chief-1", "--follower-name", "follower-1", "--along-track-km", "50",
    ])
    assert rc == 2
    assert "Basilisk is not installed" in capsys.readouterr().err


def test_generate_phasing_formation_passes_every_request_field_through(tmp_path, monkeypatch):
    """Regression test: --eclipse-sunlit-threshold was missing from the CLI
    even though PhasingFormationRequest (and the GUI's own phasing dialog)
    support it. Captures the request instead of running the real
    (Basilisk-backed) generator, so this runs anywhere.
    """
    import dataclasses

    from spacemissionstudio.engine import formation

    path = tmp_path / "chief.json"
    _write_chief_scenario(path)
    captured = {}

    class _Captured(Exception):
        pass

    def fake_generate(request, chief, template, central_body, j2=0.0):
        captured["request"] = request
        raise _Captured

    monkeypatch.setattr(formation, "generate_phasing_follower", fake_generate)
    # The capture stops the command: main reports it as an internal error (audit R13).
    assert cli.main([
        "generate-phasing-formation", str(path), "--out", str(tmp_path / "out.json"),
        "--chief", "chief-1", "--follower-name", "follower-1", "--along-track-km", "50",
        "--eclipse-sunlit-threshold", "0.5", "--station-keeping-target-altitude-km", "540",
    ]) == cli.EXIT_INTERNAL_ERROR
    request = captured["request"]
    assert request.eclipse_sunlit_threshold == 0.5  # [-]
    assert request.station_keeping_target_altitude_km == 540.0  # [km]

    # Every request field must be reachable from the command line.
    subparsers = next(action for action in cli.build_parser()._actions if action.dest == "command")
    parser_dests = {action.dest for action in subparsers.choices["generate-phasing-formation"]._actions}
    field_to_dest = {"chief_name": "chief"}
    for field in dataclasses.fields(formation.PhasingFormationRequest):
        assert field_to_dest.get(field.name, field.name) in parser_dests, field.name


def test_phasing_defaults_agree_between_schema_generator_and_cli():
    """One default per setting: the schema's PhasingKeepingConfig, the
    phasing-formation generator's request, and the CLI must not drift
    apart (the correction window used to be 21 days in all of them, and
    was shortened to 3 days in response to a real user's "the phasing is
    very slow")."""
    import dataclasses

    from spacemissionstudio.engine import formation
    from spacemissionstudio.schema.scenario import PhasingKeepingConfig

    request_defaults = {f.name: f.default for f in dataclasses.fields(formation.PhasingFormationRequest)
                        if f.default is not dataclasses.MISSING}
    schema_defaults = {f.name: f.default for f in dataclasses.fields(PhasingKeepingConfig)
                       if f.default is not dataclasses.MISSING}
    for name in request_defaults.keys() & schema_defaults.keys():
        assert request_defaults[name] == schema_defaults[name], name

    subparsers = next(action for action in cli.build_parser()._actions if action.dest == "command")
    cli_defaults = {action.dest: action.default for action in subparsers.choices["generate-phasing-formation"]._actions}
    for name in request_defaults.keys() & schema_defaults.keys():
        assert cli_defaults[name] == request_defaults[name], name
    assert schema_defaults["correction_window_days"] == 3.0  # [day]


def test_run_parses_vizard_trail_and_ground_track_flags():
    """--vizard-trail and --vizard-ground-tracks are off by default and on when
    given."""
    parser = cli.build_parser()
    assert parser.parse_args(["run", "s.json"]).vizard_trail is False
    assert parser.parse_args(["run", "s.json"]).vizard_ground_tracks is False
    args = parser.parse_args(["run", "s.json", "--vizard-trail", "--vizard-ground-tracks"])
    assert args.vizard_trail is True and args.vizard_ground_tracks is True


@pytest.mark.requires_basilisk
def test_lifetime_reports_reentry_and_the_disposal_rules(capsys):
    """Template 18 at 400 km re-enters in March 2031 (about 15 months);
    with a burn down to a 200 km perigee, within weeks."""
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates" \
        / "18_leo_station_keeping.json"
    assert cli.main(["lifetime", str(path)]) == 0
    out = capsys.readouterr().out
    assert "leo-sat-1: re-entry 2031-" in out and "5-year rule: met" in out
    assert cli.main(["lifetime", str(path), "--deorbit-perigee-km", "200"]) == 0
    assert "-> perigee 200 km" in capsys.readouterr().out


@pytest.mark.requires_basilisk
def test_budget_prints_the_ad10_table(capsys):
    """Template 18 without a run: the table, a total and the notes."""
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates" \
        / "18_leo_station_keeping.json"
    assert cli.main(["budget", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Launcher injection errors, in-plane" in out and "Residual" in out and out.count("Total") == 1
    assert "NOTE: no collision avoidances entered" in out


@pytest.mark.requires_basilisk
def test_budget_launch_delays_prints_one_row_per_launch_date(capsys, monkeypatch):
    """``budget --launch-delays``: the planned launch and 1-5 years late,
    the worst marked (drag and disposal stubbed: the real ones take a
    minute or two)."""
    from pathlib import Path
    from types import SimpleNamespace

    from spacemissionstudio.engine import propellant_budget as pb

    drag = {2030: 100.0, 2031: 300.0, 2032: 200.0, 2033: 150.0, 2034: 120.0, 2035: 110.0}  # [m/s]
    original = pb.launch_delay_sweep

    def stubbed(scenario, name, result=None):
        return original(scenario, name, result, reentry_solver=lambda *_a: (0.0, 400.0, 0.5, []),
                        makeup=lambda _s, _sc, start, *_a: SimpleNamespace(
                            delta_v_m_s=drag[start.year], altitude_km=400.0, warnings=[]))

    monkeypatch.setattr(pb, "launch_delay_sweep", stubbed)
    path = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates" \
        / "18_leo_station_keeping.json"
    assert cli.main(["budget", str(path), "--launch-delays"]) == 0
    out = capsys.readouterr().out
    rows = [line for line in out.splitlines() if line[:4].isdigit()]
    assert [line[:10] for line in rows] == [f"{year}-01-01" for year in range(2030, 2036)]
    assert rows[1].endswith("<- worst") and sum("worst" in line for line in rows) == 1
    assert "NOTE: worst case: launch 2031-01-01" in out


def test_lifetime_drag_coefficient_defaults_to_ad10s_end_of_life_value():
    """lifetime's drag coefficient defaults to 2.2 (AD10's end-of-life value),
    takes 'own', and refuses a negative value."""
    parser = cli.build_parser()
    assert parser.parse_args(["lifetime", "s.json"]).drag_coeff == "2.2"
    assert parser.parse_args(["lifetime", "s.json", "--drag-coeff", "own"]).drag_coeff == "own"
    with pytest.raises(SystemExit):
        parser.parse_args(["lifetime", "s.json", "--drag-coeff", "-1"])


@pytest.mark.requires_basilisk
def test_budget_altitudes_prints_one_row_per_altitude(capsys, monkeypatch):
    """``budget --altitudes 400,500``: the worst launch date per altitude and
    whether it fits the tank (drag and disposal stubbed)."""
    from pathlib import Path
    from types import SimpleNamespace

    from spacemissionstudio.engine import propellant_budget as pb

    original = pb.altitude_trade

    def makeup(_s, spacecraft, start, *_a):
        altitude_km = spacecraft.orbit.semi_major_axis_km - pb.REQ_EARTH_M / 1e3
        return SimpleNamespace(delta_v_m_s=(400.0 if altitude_km < 450.0 else 100.0) * (2.0 if start.year == 2032 else 1.0),
                               altitude_km=altitude_km, warnings=[])

    monkeypatch.setattr(pb, "altitude_trade", lambda scenario, name, altitudes, result=None: original(
        scenario, name, altitudes, result, reentry_solver=lambda *_a: (0.0, 400.0, 0.5, []), makeup=makeup))
    path = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates" \
        / "18_leo_station_keeping.json"
    assert cli.main(["budget", str(path), "--altitudes", "400,500"]) == 0
    out = capsys.readouterr().out
    rows = [line.split() for line in out.splitlines() if line.strip().endswith(("yes", "no"))]
    assert [(r[0], r[2], r[-1]) for r in rows] == [("400km", "2032-01-01", "no"), ("500km", "2032-01-01", "yes")]
    assert "NOTE: lowest altitude whose worst launch fits the 2 kg tank: 500 km" in out


def test_budget_altitudes_parse():
    """budget's --altitudes is unset by default, empty when given bare, takes a
    comma-separated list in km and refuses an altitude below the allowed range
    (40 km)."""
    parser = cli.build_parser()
    assert parser.parse_args(["budget", "s.json"]).altitudes is None
    assert parser.parse_args(["budget", "s.json", "--altitudes"]).altitudes == []
    assert parser.parse_args(["budget", "s.json", "--altitudes", "400, 450"]).altitudes == [400.0, 450.0]
    with pytest.raises(SystemExit):
        parser.parse_args(["budget", "s.json", "--altitudes", "40"])


@pytest.mark.requires_basilisk
def test_run_reports_an_output_folder_it_cannot_write(tmp_path, capsys):
    """Audit H3: an --out-dir that sits under a file is an error the user
    sees (exit status 3), not a traceback."""
    path, blocker = tmp_path / "scenario.json", tmp_path / "a_file"
    from spacemissionstudio.schema import SimSettings

    _write_scenario(path, sim_settings=SimSettings(duration_days=0.01))  # [d]
    blocker.write_text("not a folder")
    assert cli.main(["run", str(path), "--out-dir", str(blocker / "out")]) == 3
    assert "ERROR: could not write the results" in capsys.readouterr().err


@pytest.mark.parametrize("message", ["missing.opm", "."])
def test_ccsds_import_reports_a_message_it_cannot_read(tmp_path, capsys, message):
    """Audit M12: a missing message file, or a folder, gave a traceback."""
    path = tmp_path / "scenario.json"
    _write_scenario(path)
    rc = cli.main(["ccsds-import", str(tmp_path / message), str(path), "--spacecraft", "sat-1"])
    assert rc == 1
    assert "ERROR: could not read" in capsys.readouterr().err


@pytest.mark.parametrize("stride", ["0", "-3", "x"])
def test_run_refuses_an_oem_stride_below_one(stride, capsys):
    """Audit L7: --oem-stride 0 or -3 was accepted silently."""
    with pytest.raises(SystemExit) as exited:
        cli.build_parser().parse_args(["run", "s.json", "--oem-stride", stride])
    assert exited.value.code == 2
    assert "a whole number of 1 or more" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    ["generate-phasing-formation", "s.json", "--out", "o.json", "--chief", "c", "--follower-name", "f",
     "--along-track-km", "10", "--radial-km", "nan"],
    ["lifetime", "s.json", "--max-years", "inf"],
    ["generate-constellation", "s.json", "--out", "o.json", "--altitude-km=-inf", "--inclination-deg", "53",
     "--planes", "2", "--total-satellites", "4", "--phasing-factor", "1"],
])
def test_number_options_refuse_nan_and_infinity(argv, capsys):
    """float() accepts "nan" and "inf": every number option refuses them
    with a usage error, before they reach Basilisk (generate-phasing-formation
    --radial-km nan ended in a Basilisk AttributeError)."""
    with pytest.raises(SystemExit) as exited:
        cli.build_parser().parse_args(argv)
    assert exited.value.code == 2
    assert "a finite number" in capsys.readouterr().err


def test_budget_refuses_altitudes_with_launch_delays(capsys):
    """Audit L8: --altitudes silently overrode --launch-delays."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["budget", "s.json", "--launch-delays", "--altitudes", "400,450"])
    assert "not allowed with argument" in capsys.readouterr().err


def test_ctrl_c_and_unreported_file_errors_end_with_a_message(monkeypatch, capsys):
    """Audit L10 and L9: Ctrl-C printed a traceback (now status 130), and a
    write error a command does not report itself gave one too (status 3)."""
    def interrupted(args):
        raise KeyboardInterrupt

    def unwritable(args):
        raise PermissionError(13, "Permission denied", "out.json")

    for func, status, text in ((interrupted, 130, "Interrupted."), (unwritable, 3, "ERROR: [Errno 13] Permission")):
        monkeypatch.setattr(cli, "cmd_validate", func)
        assert cli.main(["validate", "whatever.json"]) == status
        assert text in capsys.readouterr().err


def test_an_internal_error_has_its_own_status_and_names_the_log(monkeypatch, capsys):
    """Audit R13: an unexpected exception printed a traceback and exited 1,
    the status of an invalid input (ICD-02), so a script could not tell a
    bug from a bad file. It is now one INTERNAL ERROR line naming the log
    file, which holds the traceback, and status 4."""
    import logging

    from spacemissionstudio.logging_setup import get_log_file_path

    def broken(args):
        raise RuntimeError("an engine fault")

    monkeypatch.setattr(cli, "cmd_validate", broken)
    assert cli.main(["validate", "whatever.json"]) == cli.EXIT_INTERNAL_ERROR == 4
    log = get_log_file_path()  # the test's own home (tests/conftest.py)
    err = capsys.readouterr().err
    assert "INTERNAL ERROR: RuntimeError: an engine fault" in err and str(log) in err
    assert "Traceback" not in err
    for handler in logging.getLogger().handlers:
        handler.flush()
    written = log.read_text(encoding="utf-8")
    assert "Traceback" in written and "RuntimeError: an engine fault" in written


@pytest.mark.parametrize("years", ["1e6", "-5", "0", "nan"])
def test_lifetime_refuses_a_look_ahead_outside_one_hundred_years(capsys, years):
    """Audit R6: --max-years 1e6 overflowed the date (a traceback, exit 1)
    and -5 exited 3. Like the other bounded options it is now a usage
    error (status 2) saying the range, before anything is loaded."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["lifetime", "whatever.json", "--max-years", years])
    assert exc.value.code == 2
    assert "--max-years" in capsys.readouterr().err


def test_validate_prints_the_plausibility_warnings(tmp_path, capsys):
    """Audit L11: validate printed none of the GUI's plausibility checks; a
    perigee below the ground is now a WARNING line (the status stays 0)."""
    from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SpacecraftConfig

    path = tmp_path / "low.json"
    Scenario(name="low", epoch_utc="2025-06-01T00:00:00", gravity=GravityConfig(central_body="earth"),
             spacecraft=[SpacecraftConfig(name="sat-1", orbit=OrbitIC(
                 type="classical_elements", semi_major_axis_km=6500.0, eccentricity=0.1, inclination_deg=51.6,
                 raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))]).save(path)  # [km], [deg]
    assert cli.main(["validate", str(path)]) == 0
    assert "WARNING:" in capsys.readouterr().out
