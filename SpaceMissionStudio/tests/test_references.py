"""Tests for spacemissionstudio.schema.references -- no Basilisk import, runs
anywhere.
"""

import pytest

from spacemissionstudio.schema.command import Command
from spacemissionstudio.schema.references import (
    ReferenceError,
    find_ground_station_references,
    find_spacecraft_references,
    rename_ground_station,
    rename_spacecraft,
)
from spacemissionstudio.schema.scenario import (
    CommsPointingConfig,
    DispersionConfig,
    GroundStationConfig,
    MonteCarloConfig,
    OrbitIC,
    PhasingKeepingConfig,
    Scenario,
    SpacecraftConfig,
)


def _orbit():
    return OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0])


def _scenario(**overrides):
    defaults = dict(
        name="ref test", epoch_utc="2030-01-01T00:00:00",
        spacecraft=[SpacecraftConfig(name="sat-1", orbit=_orbit())],
    )
    defaults.update(overrides)
    return Scenario(**defaults)


# -- find_spacecraft_references ---------------------------------------------

def test_no_references_when_unreferenced():
    """A spacecraft nothing names has no references."""
    assert find_spacecraft_references(_scenario(), "sat-1") == []


def test_phasing_keeping_chief_is_found():
    """A follower's phasing-keeping chief is found as one spacecraft reference,
    at the follower's chief_spacecraft field."""
    chief = SpacecraftConfig(name="chief", orbit=_orbit())
    follower = SpacecraftConfig(name="follower", orbit=_orbit(), phasing_keeping=PhasingKeepingConfig(
        chief_spacecraft="chief", target_separation_km=[100.0], tolerance_fraction=0.1, restore_tolerance_fraction=0.5,
        correction_window_days=1.0, max_drift_days=5.0, max_delta_semi_major_axis_km=1.0,
    ))
    scenario = _scenario(spacecraft=[chief, follower])

    refs = find_spacecraft_references(scenario, "chief")

    assert len(refs) == 1
    assert refs[0].resource_kind == "spacecraft"
    assert "phasing_keeping.chief_spacecraft" in refs[0].path
    assert "follower" in refs[0].path


def test_monte_carlo_dispersion_is_found():
    """A Monte Carlo dispersion on the spacecraft is found at its dispersion
    index."""
    scenario = _scenario(monte_carlo=MonteCarloConfig(
        enabled=True, num_runs=2,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=[90, 110])],
    ))

    refs = find_spacecraft_references(scenario, "sat-1")

    assert len(refs) == 1
    assert "monte_carlo.dispersions[0]" in refs[0].path


def test_maneuver_command_reference_is_found():
    """A maneuver on the spacecraft is found at its sequence index, with the
    command's label."""
    scenario = _scenario(mission_sequence=[
        Command(kind="maneuver", label="Trim", params={"spacecraft": "sat-1", "delta_v_m_s": [1.0, 0.0, 0.0]}),
    ])

    refs = find_spacecraft_references(scenario, "sat-1")

    assert len(refs) == 1
    assert "mission_sequence[0]" in refs[0].path
    assert "'Trim'" in refs[0].path


def test_lambert_transfer_command_reference_is_found():
    """A Lambert transfer of the spacecraft is found at its sequence index,
    with the command's label."""
    scenario = _scenario(mission_sequence=[
        Command(kind="lambert_transfer", label="Transfer", params={
            "spacecraft": "sat-1", "target_position_m": [1.0, 0.0, 0.0], "time_of_flight_s": 3600.0,
        }),
    ])

    refs = find_spacecraft_references(scenario, "sat-1")

    assert len(refs) == 1
    assert "mission_sequence[0]" in refs[0].path
    assert "'Transfer'" in refs[0].path


def test_propagate_event_command_reference_is_found():
    """A propagate to the spacecraft's next periapsis is found as a
    reference."""
    scenario = _scenario(mission_sequence=[
        Command(kind="propagate", params={"stop_condition": "event", "event_kind": "periapsis",
                                            "spacecraft": "sat-1"}),
    ])
    refs = find_spacecraft_references(scenario, "sat-1")
    assert len(refs) == 1


def test_assignment_target_reference_is_found():
    """An assignment to one of the spacecraft's fields is found at the
    command's target."""
    scenario = _scenario(mission_sequence=[
        Command(kind="assignment", params={"target": "sat-1.station_keeping.thrust_n", "value": 0.5}),
    ])

    refs = find_spacecraft_references(scenario, "sat-1")

    assert len(refs) == 1
    assert "params['target']" in refs[0].path


def test_report_series_reference_is_found():
    """Real audit finding: report.params["series"] entries like
    "sat-1.position_N" are dotted spacecraft-prefixed strings exactly like
    assignment.target, but _command_references() had no "report" case at
    all -- so a report command referencing a spacecraft didn't block its
    deletion and wasn't updated on rename.
    """
    scenario = _scenario(mission_sequence=[
        Command(kind="report", params={"series": ["sat-1.position_N", "sat-1.velocity_N"]}),
    ])

    refs = find_spacecraft_references(scenario, "sat-1")

    assert len(refs) == 2
    assert "params['series'][0]" in refs[0].path
    assert "params['series'][1]" in refs[1].path


def test_report_series_reference_to_other_spacecraft_is_not_found():
    """A report of another spacecraft's series is not a reference to this
    one."""
    scenario = _scenario(spacecraft=[SpacecraftConfig(name="sat-1", orbit=_orbit()),
                                       SpacecraftConfig(name="sat-2", orbit=_orbit())],
                          mission_sequence=[
        Command(kind="report", params={"series": ["sat-2.position_N"]}),
    ])
    assert find_spacecraft_references(scenario, "sat-1") == []


def test_reference_nested_inside_if_is_found():
    """A maneuver inside an if is found at its child path."""
    scenario = _scenario(mission_sequence=[
        Command(kind="if", params={"condition": "True"}, children=[
            Command(kind="maneuver", params={"spacecraft": "sat-1", "delta_v_m_s": [1.0, 0.0, 0.0]}),
        ]),
    ])

    refs = find_spacecraft_references(scenario, "sat-1")

    assert len(refs) == 1
    assert "children[0]" in refs[0].path


def test_reference_to_a_different_spacecraft_is_not_found():
    """A maneuver on another spacecraft is not a reference to this one."""
    scenario = _scenario(spacecraft=[SpacecraftConfig(name="sat-1", orbit=_orbit()),
                                       SpacecraftConfig(name="sat-2", orbit=_orbit())],
                          mission_sequence=[
        Command(kind="maneuver", params={"spacecraft": "sat-2", "delta_v_m_s": [1.0, 0.0, 0.0]}),
    ])
    assert find_spacecraft_references(scenario, "sat-1") == []


# -- find_ground_station_references ------------------------------------------

def test_ground_station_target_is_found():
    """A locationPointing target ground station is found at the spacecraft's
    target_ground_station."""
    sc = SpacecraftConfig(name="sat-1", orbit=_orbit(), fsw_mode="locationPointing",
                            fsw_params={"target_ground_station": "dsn-goldstone", "pHat_B": [0, 0, 1]})
    scenario = _scenario(spacecraft=[sc],
                          ground_stations=[GroundStationConfig(name="dsn-goldstone", latitude_deg=35.0,
                                                                  longitude_deg=-116.0)])

    refs = find_ground_station_references(scenario, "dsn-goldstone")

    assert len(refs) == 1
    assert "target_ground_station" in refs[0].path


def test_comms_pointing_target_is_found():
    """Regression test for a real gap: comms_pointing.target_ground_station
    is a real reference (Scenario.validate() treats it as one -- see
    scenario.py's own cross-reference checks), but find_ground_station_references
    didn't know about it, which would let the GUI delete a ground station
    out from under a comms_pointing spacecraft with no warning at all.
    """
    sc = SpacecraftConfig(name="sat-1", orbit=_orbit(),
                            comms_pointing=CommsPointingConfig(target_ground_station="gs-1"))
    scenario = _scenario(spacecraft=[sc],
                          ground_stations=[GroundStationConfig(name="gs-1", latitude_deg=0.0, longitude_deg=0.0)])

    refs = find_ground_station_references(scenario, "gs-1")

    assert len(refs) == 1
    assert "comms_pointing.target_ground_station" in refs[0].path


def test_ground_station_unreferenced_is_empty():
    """A ground station nothing names has no references."""
    scenario = _scenario(ground_stations=[GroundStationConfig(name="gs-1", latitude_deg=0.0, longitude_deg=0.0)])
    assert find_ground_station_references(scenario, "gs-1") == []


# -- rename_spacecraft ------------------------------------------------------

def test_rename_spacecraft_updates_self_and_every_reference():
    """Renaming a chief renames it and its four references (phasing keeping,
    dispersion, maneuver, assignment target), after which the old name has
    none."""
    chief = SpacecraftConfig(name="chief", orbit=_orbit())
    follower = SpacecraftConfig(name="follower", orbit=_orbit(), phasing_keeping=PhasingKeepingConfig(
        chief_spacecraft="chief", target_separation_km=[100.0], tolerance_fraction=0.1, restore_tolerance_fraction=0.5,
        correction_window_days=1.0, max_drift_days=5.0, max_delta_semi_major_axis_km=1.0,
    ))
    scenario = _scenario(spacecraft=[chief, follower], mission_sequence=[
        Command(kind="maneuver", params={"spacecraft": "chief", "delta_v_m_s": [1.0, 0.0, 0.0]}),
        Command(kind="assignment", params={"target": "chief.station_keeping.thrust_n", "value": 1.0}),
    ], monte_carlo=MonteCarloConfig(
        enabled=True, num_runs=1,
        dispersions=[DispersionConfig(spacecraft="chief", quantity="dry_mass_kg", kind="uniform", bounds=[90, 110])],
    ))

    updated = rename_spacecraft(scenario, "chief", "chief-2")

    assert updated == 4  # phasing_keeping + dispersion + maneuver + assignment
    assert chief.name == "chief-2"
    assert follower.phasing_keeping.chief_spacecraft == "chief-2"
    assert scenario.monte_carlo.dispersions[0].spacecraft == "chief-2"
    assert scenario.mission_sequence[0].params["spacecraft"] == "chief-2"
    assert scenario.mission_sequence[1].params["target"] == "chief-2.station_keeping.thrust_n"
    assert find_spacecraft_references(scenario, "chief") == []


def test_rename_spacecraft_updates_lambert_transfer_reference():
    """Renaming a spacecraft updates a Lambert transfer's spacecraft, counted
    as one reference."""
    scenario = _scenario(mission_sequence=[
        Command(kind="lambert_transfer", params={
            "spacecraft": "sat-1", "target_position_m": [1.0, 0.0, 0.0], "time_of_flight_s": 3600.0,
        }),
    ])

    updated = rename_spacecraft(scenario, "sat-1", "sat-1-renamed")

    assert updated == 1  # the lambert_transfer command (SpacecraftConfig itself isn't counted)
    assert scenario.mission_sequence[0].params["spacecraft"] == "sat-1-renamed"
    assert find_spacecraft_references(scenario, "sat-1") == []


def test_rename_spacecraft_in_nested_if_children():
    """Renaming a spacecraft updates a maneuver inside a while."""
    scenario = _scenario(mission_sequence=[
        Command(kind="while", params={"condition": "True"}, children=[
            Command(kind="maneuver", params={"spacecraft": "sat-1", "delta_v_m_s": [1.0, 0.0, 0.0]}),
        ]),
    ])
    rename_spacecraft(scenario, "sat-1", "sat-1-renamed")
    assert scenario.mission_sequence[0].children[0].params["spacecraft"] == "sat-1-renamed"


def test_rename_spacecraft_raises_if_old_name_not_found():
    """Renaming a spacecraft the scenario does not have is refused."""
    with pytest.raises(ReferenceError, match="no spacecraft named"):
        rename_spacecraft(_scenario(), "does-not-exist", "new-name")


def test_rename_spacecraft_raises_on_collision():
    """Renaming a spacecraft to another spacecraft's name is refused."""
    scenario = _scenario(spacecraft=[SpacecraftConfig(name="sat-1", orbit=_orbit()),
                                       SpacecraftConfig(name="sat-2", orbit=_orbit())])
    with pytest.raises(ReferenceError, match="already exists"):
        rename_spacecraft(scenario, "sat-1", "sat-2")


def test_rename_spacecraft_raises_on_empty_new_name():
    """Renaming a spacecraft to an empty name is refused."""
    with pytest.raises(ReferenceError, match="must not be empty"):
        rename_spacecraft(_scenario(), "sat-1", "")


def test_rename_spacecraft_to_same_name_is_a_harmless_no_op():
    """Renaming a spacecraft to its own name changes nothing and counts no
    references."""
    scenario = _scenario()
    updated = rename_spacecraft(scenario, "sat-1", "sat-1")
    assert updated == 0
    assert scenario.spacecraft[0].name == "sat-1"


# -- rename_ground_station ----------------------------------------------------

def test_rename_ground_station_updates_self_and_references():
    """Renaming a ground station renames it and the spacecraft's pointing
    target."""
    sc = SpacecraftConfig(name="sat-1", orbit=_orbit(), fsw_mode="locationPointing",
                            fsw_params={"target_ground_station": "gs-1", "pHat_B": [0, 0, 1]})
    scenario = _scenario(spacecraft=[sc],
                          ground_stations=[GroundStationConfig(name="gs-1", latitude_deg=0.0, longitude_deg=0.0)])

    updated = rename_ground_station(scenario, "gs-1", "gs-1-renamed")

    assert updated == 1
    assert scenario.ground_stations[0].name == "gs-1-renamed"
    assert sc.fsw_params["target_ground_station"] == "gs-1-renamed"


def test_rename_ground_station_raises_if_not_found():
    """Renaming a ground station the scenario does not have is refused."""
    with pytest.raises(ReferenceError, match="no ground station named"):
        rename_ground_station(_scenario(), "does-not-exist", "new-name")


def test_rename_ground_station_updates_comms_pointing_reference():
    """Regression test for a real gap: rename_ground_station used to
    rename the GroundStationConfig itself but leave
    comms_pointing.target_ground_station pointing at the old, now
    -nonexistent name -- breaking the "rename updates every reference
    atomically" guarantee this module's own docstring promises.
    """
    sc = SpacecraftConfig(name="sat-1", orbit=_orbit(),
                            comms_pointing=CommsPointingConfig(target_ground_station="gs-1"))
    scenario = _scenario(spacecraft=[sc],
                          ground_stations=[GroundStationConfig(name="gs-1", latitude_deg=0.0, longitude_deg=0.0)])

    updated = rename_ground_station(scenario, "gs-1", "gs-1-renamed")

    assert updated == 1
    assert scenario.ground_stations[0].name == "gs-1-renamed"
    assert sc.comms_pointing.target_ground_station == "gs-1-renamed"


# -- pass-event propagate commands name a ground station ---------------------

def _pass_scenario():
    from spacemissionstudio.schema.command import Command

    stop = Command(kind="propagate", params={"stop_condition": "event", "event_kind": "pass_end",
                                             "spacecraft": "sat-1", "ground_station": "gs-1"})
    loop = Command(kind="while", params={"condition": "True"}, children=[stop])
    return _scenario(ground_stations=[GroundStationConfig(name="gs-1", latitude_deg=52.5, longitude_deg=13.4)],
                     mission_sequence=[loop])


def test_pass_event_station_is_found_renamed_and_checked():
    """A pass event's ground station inside a loop is found, renamed with the
    station and checked: a station the scenario does not have fails
    validation."""
    from spacemissionstudio.schema import find_ground_station_references, rename_ground_station
    from spacemissionstudio.schema.scenario import ScenarioValidationError

    scenario = _pass_scenario()
    refs = find_ground_station_references(scenario, "gs-1")
    assert [r.path for r in refs] == ["mission_sequence[0].children[0].params['ground_station']"]
    assert rename_ground_station(scenario, "gs-1", "berlin") == 1
    assert scenario.mission_sequence[0].children[0].params["ground_station"] == "berlin"
    scenario.validate()
    scenario.mission_sequence[0].children[0].params["ground_station"] = "gone"
    with pytest.raises(ScenarioValidationError, match="ground_station 'gone' is not one of"):
        scenario.validate()


def test_a_rename_reaches_export_records_conditions_and_access_series():
    """Audit L14: renaming a spacecraft missed fsw_exports[].spacecraft,
    spacecraft['...'] in conditions and stations' access series to it;
    renaming a station missed its own access series."""
    from spacemissionstudio.schema.scenario import FswExportRecord

    report = Command(kind="report", params={"series": ["gs-1.access_to_sat-1.elevation", "sat-1.position_N"]})
    loop = Command(kind="while", params={"condition": "spacecraft['sat-1']['altitude_m'] > 4e5"},
                   children=[Command(kind="propagate", params={"duration_days": 0.1}), report])
    scenario = _scenario(ground_stations=[GroundStationConfig(name="gs-1", latitude_deg=52.5, longitude_deg=13.4)],
                         mission_sequence=[loop],
                         fsw_exports=[FswExportRecord(spacecraft="sat-1", path="fsw", config_digest="0" * 64)])
    assert any(ref.path == "fsw_exports[0].spacecraft" for ref in find_spacecraft_references(scenario, "sat-1"))
    rename_spacecraft(scenario, "sat-1", "sat-A")
    assert scenario.fsw_exports[0].spacecraft == "sat-A"
    assert loop.params["condition"] == "spacecraft['sat-A']['altitude_m'] > 4e5"
    assert report.params["series"] == ["gs-1.access_to_sat-A.elevation", "sat-A.position_N"]
    rename_ground_station(scenario, "gs-1", "berlin")
    assert report.params["series"] == ["berlin.access_to_sat-A.elevation", "sat-A.position_N"]
    scenario.validate()
