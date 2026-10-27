"""Tests for spacemissionstudio.schema -- no Basilisk import, runs anywhere."""

import copy
import json

import pytest

from spacemissionstudio.schema import (
    CURRENT_SCHEMA_VERSION,
    ActuatorConfig,
    CommsPointingConfig,
    ConstantThrustConfig,
    DispersionConfig,
    FuelTankConfig,
    GravityConfig,
    GroundStationConfig,
    MagneticMomentumManagementConfig,
    MomentumDumpingConfig,
    MonteCarloConfig,
    OrbitIC,
    PhasingKeepingConfig,
    PowerConfig,
    RFLinkConfig,
    Scenario,
    ScenarioValidationError,
    SensorConfig,
    SimSettings,
    SpacecraftConfig,
    StationKeepingConfig,
    load_scenario,
)


def _minimal_scenario(**overrides) -> Scenario:
    defaults = dict(
        name="test scenario",
        epoch_utc="2030-01-01T00:00:00",
        spacecraft=[
            SpacecraftConfig(
                name="sat-1",
                orbit=OrbitIC(
                    type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                    inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0,
                ),
            )
        ],
    )
    defaults.update(overrides)
    return Scenario(**defaults)


def test_minimal_scenario_validates():
    """A scenario with only a name, an epoch and one spacecraft on classical
    elements validates."""
    _minimal_scenario().validate()


def test_round_trip_save_load(tmp_path):
    """Saving and loading keeps the name, epoch, description, spacecraft orbit
    and schema version."""
    scenario = _minimal_scenario(description="round-trip check")
    path = tmp_path / "scenario.json"
    scenario.save(path)

    loaded = load_scenario(path)
    assert loaded.name == scenario.name
    assert loaded.epoch_utc == scenario.epoch_utc
    assert loaded.description == "round-trip check"
    assert len(loaded.spacecraft) == 1
    assert loaded.spacecraft[0].orbit.semi_major_axis_km == 7000.0
    assert loaded.schema_version == scenario.schema_version


def test_round_trip_preserves_every_field_category(tmp_path):
    """Gravity settings, ground stations and sensor parameters survive a save
    and load."""
    scenario = _minimal_scenario()
    scenario.gravity = GravityConfig(central_body="earth", central_body_degree=10,
                                      third_body_perturbers=["sun", "moon"])
    scenario.ground_stations = [GroundStationConfig(name="gs-1", latitude_deg=40.0, longitude_deg=-105.0)]
    scenario.spacecraft[0].sensors = [SensorConfig(kind="star_tracker", name="st-1", params={"noise_arcsec": 5.0})]

    path = tmp_path / "scenario.json"
    scenario.save(path)
    loaded = load_scenario(path)

    assert loaded.gravity.central_body_degree == 10
    assert loaded.gravity.third_body_perturbers == ["sun", "moon"]
    assert loaded.ground_stations[0].name == "gs-1"
    assert loaded.spacecraft[0].sensors[0].kind == "star_tracker"
    assert loaded.spacecraft[0].sensors[0].params["noise_arcsec"] == 5.0


def test_saved_file_is_plain_readable_json(tmp_path):
    """A saved scenario is plain JSON that json.loads reads without a custom
    decoder, with the current schema version."""
    path = tmp_path / "scenario.json"
    _minimal_scenario().save(path)
    # round-trips through plain json.loads with no custom decoder -- this
    # is a "human-readable JSON", not a pickle, per the project requirement.
    data = json.loads(path.read_text())
    assert data["name"] == "test scenario"
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION


@pytest.mark.parametrize("bad_field,bad_value,match", [
    ("name", "", "name must not be empty"),
    ("epoch_utc", "not-a-date", "not a valid ISO 8601"),
])
def test_scenario_level_validation_errors(bad_field, bad_value, match):
    """An empty name and an epoch that is not ISO 8601 are refused with a
    message naming the problem."""
    scenario = _minimal_scenario(**{bad_field: bad_value})
    with pytest.raises(ScenarioValidationError, match=match):
        scenario.validate()


def test_duration_days_at_the_100_day_cap_validates():
    """A 100-day run validates."""
    scenario = _minimal_scenario(sim_settings=SimSettings(duration_days=100.0))
    scenario.validate()


def test_duration_days_beyond_ten_years_rejected():
    """A run longer than 3660 days (ten years) is refused."""
    scenario = _minimal_scenario(sim_settings=SimSettings(duration_days=4000.0))
    with pytest.raises(ScenarioValidationError, match="duration_days must be <= 3660"):
        scenario.validate()


def test_a_run_past_one_basilisk_run_validates():
    """Past ~104 days Basilisk's nanoToSec() returns NaN, so such a run is
    split into segments (engine/long_run.py); the schema allows it."""
    scenario = _minimal_scenario(sim_settings=SimSettings(duration_days=1826.25))  # [day] 5 years
    scenario.validate()


def test_a_mission_sequence_past_one_basilisk_run_is_rejected():
    """A mission sequence cannot be split into segments."""
    from spacemissionstudio.schema.command import Command

    scenario = _minimal_scenario(sim_settings=SimSettings(duration_days=120.0),  # [day]
                                 mission_sequence=[Command(kind="propagate", params={"stop_condition": "duration", "duration_days": 1.0})])  # [day]
    with pytest.raises(ScenarioValidationError, match="which a mission sequence cannot run"):
        scenario.validate()


def test_zero_spacecraft_rejected():
    """A scenario without a spacecraft is refused."""
    scenario = _minimal_scenario(spacecraft=[])
    with pytest.raises(ScenarioValidationError, match="at least one spacecraft"):
        scenario.validate()


def test_duplicate_spacecraft_names_rejected():
    """Two spacecraft with the same name are refused."""
    sc = _minimal_scenario()
    sc.spacecraft.append(SpacecraftConfig(name="sat-1", orbit=sc.spacecraft[0].orbit))
    with pytest.raises(ScenarioValidationError, match="unique"):
        sc.validate()


def test_unsupported_central_body_rejected():
    """A central body the tool does not offer (Pluto) is refused."""
    sc = _minimal_scenario()
    sc.gravity = GravityConfig(central_body="pluto")
    with pytest.raises(ScenarioValidationError, match="must be one of"):
        sc.validate()


def test_spherical_harmonics_on_a_body_without_a_field_rejected():
    """Spherical harmonics around a body without a gravity field (the Moon)
    are refused by the schema, as engine.service would refuse them at run
    time (an audit finding: `validate` and Save passed such a scenario)."""
    sc = _minimal_scenario()
    sc.gravity = GravityConfig(central_body="moon", central_body_degree=20)
    with pytest.raises(ScenarioValidationError, match="needs a central body with a gravity field"):
        sc.validate()


def test_mars_takes_the_ggm2b_field_up_to_its_degree():
    """Mars takes spherical harmonics up to GGM2B's degree 80, not beyond."""
    GravityConfig(central_body="mars barycenter", central_body_degree=80).validate()
    with pytest.raises(ScenarioValidationError, match="must be <= 80 \\(the GGM2B field's maximum\\)"):
        GravityConfig(central_body="mars barycenter", central_body_degree=81).validate()


def test_spherical_harmonics_on_earth_is_allowed():
    """Earth with a degree-20 spherical-harmonics field validates."""
    sc = _minimal_scenario()
    sc.gravity = GravityConfig(central_body="earth", central_body_degree=20)
    sc.validate()  # must not raise


def test_point_mass_on_non_earth_body_is_allowed():
    """Mars as a point mass (degree 0) validates."""
    sc = _minimal_scenario()
    sc.gravity = GravityConfig(central_body="mars barycenter", central_body_degree=0)
    sc.validate()  # must not raise


def test_invalid_eccentricity_rejected():
    """An eccentricity of 1.2 (hyperbolic) is refused: the schema takes 0 <= e
    < 1."""
    sc = _minimal_scenario()
    sc.spacecraft[0].orbit.eccentricity = 1.2  # hyperbolic, out of this schema's supported range
    with pytest.raises(ScenarioValidationError, match="0 <= eccentricity < 1"):
        sc.validate()


def test_cartesian_orbit_requires_full_vectors():
    """A Cartesian orbit with a two-element position and no velocity is
    refused."""
    orbit = OrbitIC(type="cartesian", position_km=[7000.0, 0.0])  # only 2 elements, missing velocity
    with pytest.raises(ScenarioValidationError, match="3-element"):
        orbit.validate()


def test_tle_orbit_requires_both_lines():
    """A TLE orbit with only its first line is refused."""
    orbit = OrbitIC(type="tle", tle_line1="1 25544U ...")
    with pytest.raises(ScenarioValidationError, match="both tle_line1 and tle_line2"):
        orbit.validate()


def test_classical_elements_orbit_defaults_to_true_anomaly():
    """Classical elements take the true anomaly unless told otherwise, and
    validate."""
    orbit = OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                     inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=30.0)
    assert orbit.anomaly_type == "true"
    orbit.validate()  # must not raise


def test_classical_elements_orbit_accepts_mean_anomaly():
    """Classical elements with anomaly_type 'mean' and a mean anomaly
    validate."""
    orbit = OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                     inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0,
                     anomaly_type="mean", mean_anomaly_deg=30.0)
    orbit.validate()  # must not raise


def test_classical_elements_orbit_requires_the_anomaly_matching_anomaly_type():
    """anomaly_type 'mean' with only a true anomaly is refused, asking for
    mean_anomaly_deg."""
    orbit = OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                     inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0,
                     anomaly_type="mean", true_anomaly_deg=30.0)  # wrong field for anomaly_type="mean"
    with pytest.raises(ScenarioValidationError, match="needs mean_anomaly_deg"):
        orbit.validate()


def test_classical_elements_orbit_rejects_unknown_anomaly_type():
    """An anomaly type other than true or mean ('eccentric') is refused."""
    orbit = OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                     inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0,
                     anomaly_type="eccentric", true_anomaly_deg=30.0)
    with pytest.raises(ScenarioValidationError, match="anomaly_type"):
        orbit.validate()


def test_space_weather_local_file_requires_path():
    """The local_file space-weather source without a file path is refused."""
    sc = _minimal_scenario()
    sc.space_weather.source = "local_file"
    sc.space_weather.local_file_path = None
    with pytest.raises(ScenarioValidationError, match="local_file_path was not set"):
        sc.validate()


def test_space_weather_defaults_to_nrlmsise00_nominal():
    """Space weather defaults to NRLMSISE-00 at the 50th percentile, and the
    defaults validate."""
    sc = _minimal_scenario()
    assert sc.space_weather.atmosphere_model == "nrlmsise00"
    assert sc.space_weather.forecast_percentile == 50.0  # nominal; 95 is the conservative AD10 case
    sc.validate()  # defaults must themselves be valid


def test_space_weather_rejects_unknown_atmosphere_model():
    """An atmosphere model Basilisk does not have (Jacchia-Roberts) is
    refused."""
    sc = _minimal_scenario()
    sc.space_weather.atmosphere_model = "jacchia_roberts"  # not implemented in Basilisk -- see schema docstring
    with pytest.raises(ScenarioValidationError, match="atmosphere_model"):
        sc.validate()


@pytest.mark.parametrize("percentile", [50.0, 95.0, 5.0])
def test_space_weather_takes_msfcs_published_percentiles(percentile):
    """Nominal (50), conservative (95, ESA AD10 operations) and low (5)."""
    sc = _minimal_scenario()
    sc.space_weather.forecast_percentile = percentile
    sc.validate()


@pytest.mark.parametrize("percentile", [97.7, 75.0, 0.0])
def test_space_weather_rejects_other_percentiles(percentile):
    """Forecast percentiles MSFC does not publish (97.7, 75, 0) are refused."""
    sc = _minimal_scenario()
    sc.space_weather.forecast_percentile = percentile
    with pytest.raises(ScenarioValidationError, match="forecast_percentile"):
        sc.validate()


def test_space_weather_exponential_model_round_trips_through_save_load(tmp_path):
    """The exponential atmosphere model survives a save and load."""
    sc = _minimal_scenario()
    sc.space_weather.atmosphere_model = "exponential"
    sc.save(tmp_path / "s.json")
    loaded = load_scenario(tmp_path / "s.json")
    assert loaded.space_weather.atmosphere_model == "exponential"


def test_load_scenario_missing_file_gives_clear_error(tmp_path):
    """Loading a file that does not exist says the file could not be read."""
    with pytest.raises(ScenarioValidationError, match="could not read file"):
        load_scenario(tmp_path / "does_not_exist.json")


def test_load_scenario_malformed_json_gives_clear_error(tmp_path):
    """Loading a file that is not JSON says so."""
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")
    with pytest.raises(ScenarioValidationError, match="not valid JSON"):
        load_scenario(path)


def test_load_scenario_missing_schema_version_gives_clear_error(tmp_path):
    """Loading a file without schema_version names the missing field."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"name": "no version"}))
    with pytest.raises(ScenarioValidationError, match="missing required top-level 'schema_version'"):
        load_scenario(path)


@pytest.mark.parametrize("where", ["top", "spacecraft"])
def test_load_scenario_rejects_an_unknown_field_naming_it(tmp_path, where):
    """An unknown field at the top level or in a spacecraft is refused, and
    the error names the field (ICD-01)."""
    data = json.loads(json.dumps(_minimal_scenario().to_dict()))
    (data if where == "top" else data["spacecraft"][0])["bogus_field"] = 1
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ScenarioValidationError, match="unexpected keyword argument 'bogus_field'"):
        load_scenario(path)


def test_load_scenario_future_schema_version_gives_clear_error(tmp_path):
    """A file from a newer schema version is refused, asking for an upgrade of
    the tool."""
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"schema_version": 999, "name": "from the future", "epoch_utc": "2030-01-01T00:00:00"}))
    with pytest.raises(ScenarioValidationError, match="upgrade SpaceMissionStudio"):
        load_scenario(path)


def test_load_scenario_boolean_schema_version_gives_clear_error(tmp_path):
    """Regression test: bool is a subclass of int in Python
    (isinstance(True, int) is True), so a malformed "schema_version": true
    used to pass migrations.migrate()'s isinstance(version, int) check and
    silently end up stored as a literal True instead of a real version
    number, rather than raising a clear error like every other malformed
    schema_version value does.
    """
    path = tmp_path / "bool_version.json"
    path.write_text(json.dumps({"schema_version": True, "name": "x", "epoch_utc": "2030-01-01T00:00:00"}))
    with pytest.raises(ScenarioValidationError, match="schema_version must be an integer"):
        load_scenario(path)


# -- Phase 2: sensors/actuators/FSW mode validation ---------------------------

def test_unsupported_sensor_kind_rejected():
    """A sensor kind the tool does not offer (lidar) is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="lidar", name="l-1")]
    with pytest.raises(ScenarioValidationError, match="must be one of"):
        sc.validate()


def test_unsupported_actuator_kind_rejected():
    """An actuator kind the tool does not offer (ion_engine) is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="ion_engine", name="ie-1")]
    with pytest.raises(ScenarioValidationError, match="must be one of"):
        sc.validate()


def test_duplicate_sensor_names_rejected():
    """Two sensors with the same name on one spacecraft are refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="imu", name="dup"), SensorConfig(kind="star_tracker", name="dup")]
    with pytest.raises(ScenarioValidationError, match="sensor names must be unique"):
        sc.validate()


def test_duplicate_actuator_names_rejected():
    """Two actuators with the same name on one spacecraft are refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="dup", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="thruster", name="dup"),
    ]
    with pytest.raises(ScenarioValidationError, match="actuator names must be unique"):
        sc.validate()


def test_coarse_sun_sensor_requires_nHat_B():
    """A coarse sun sensor without its normal nHat_B is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="coarse_sun_sensor", name="css-1")]
    with pytest.raises(ScenarioValidationError, match="nHat_B"):
        sc.validate()


def test_reaction_wheel_requires_gsHat_B():
    """A reaction wheel without its spin axis gsHat_B is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="reaction_wheel", name="rw-1")]
    with pytest.raises(ScenarioValidationError, match="gsHat_B"):
        sc.validate()


def test_custom_reaction_wheel_requires_u_max_or_useMaxTorque_false():
    """A custom reaction wheel without u_max is refused before
    rwFactory.create(), which exits the process on a non-positive u_max."""
    # rwFactory.create() hard-exits the whole process (not a catchable
    # error) on a non-positive u_max for rw_type="custom" (the default) --
    # this schema check exists specifically to never reach that call.
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1, 0, 0], "Js": 0.01})
    ]
    with pytest.raises(ScenarioValidationError, match="u_max"):
        sc.validate()


def test_custom_reaction_wheel_requires_inertia():
    """A custom reaction wheel without its spin inertia Js is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1, 0, 0], "u_max": 0.2})
    ]
    with pytest.raises(ScenarioValidationError, match="Js"):
        sc.validate()


def test_custom_reaction_wheel_with_u_max_and_Js_validates():
    """A custom reaction wheel with u_max and Js validates."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1, 0, 0], "u_max": 0.2, "Js": 0.01})
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.validate()  # must not raise


def test_named_hardware_reaction_wheel_type_skips_custom_requirements():
    """A named Honeywell wheel needs no u_max or Js: rwFactory supplies
    them."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0})
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.validate()  # must not raise -- named types have their own built-in defaults


@pytest.mark.parametrize("rw_type, max_momentum", [
    ("Honeywell_HR12", 60.0), ("Honeywell_HR16", 12.0), ("Honeywell_HR14", None),
])
def test_named_honeywell_wheel_needs_one_of_its_own_momentum_sizes(rw_type, max_momentum):
    """rwFactory.create() calls exit(1) on any other value, or none --
    killing the app, which the 07 wizard's free momentum field could do."""
    sc = _minimal_scenario()
    params = {"gsHat_B": [1, 0, 0], "rw_type": rw_type}
    if max_momentum is not None:
        params["maxMomentum"] = max_momentum
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="reaction_wheel", name="rw-1", params=params)]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    with pytest.raises(ScenarioValidationError, match="builds only with params\\['maxMomentum'\\]"):
        sc.validate()
    params["maxMomentum"] = 25  # [N*m*s] an int from JSON is fine
    if rw_type != "Honeywell_HR16":
        sc.validate()


def test_motor_thermal_requires_all_four_fields_together():
    """A wheel with only one of the four motor-thermal fields is refused, since
    motorThermal's Reset() exits the process on an unset field."""
    # motorThermal.MotorThermal.Reset() hard-exits the whole process (not
    # a catchable error) on an unset field in this group -- this schema
    # check exists specifically to never reach that call partially
    # configured.
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0,
                                "motor_thermal_initial_temp_c": 20.0})
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    with pytest.raises(ScenarioValidationError, match="motor_thermal"):
        sc.validate()


def test_motor_thermal_efficiency_must_be_strictly_between_zero_and_one():
    """A motor-thermal efficiency of 1.0 (motorThermal's own default, which its
    Reset() rejects) is refused."""
    # motorThermal.MotorThermal's own constructor default (1.0) is ITSELF
    # one of the values Reset() rejects -- confirmed directly against
    # motorThermal.cpp.
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0,
                                "motor_thermal_initial_temp_c": 20.0, "motor_thermal_efficiency": 1.0,
                                "motor_thermal_ambient_resistance_w_c": 5.0,
                                "motor_thermal_heat_capacity_j_c": 50.0})
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    with pytest.raises(ScenarioValidationError, match="motor_thermal_efficiency"):
        sc.validate()


def test_motor_thermal_with_all_fields_validates():
    """A wheel with all four motor-thermal fields in range validates."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0,
                                "motor_thermal_initial_temp_c": 20.0, "motor_thermal_efficiency": 0.7,
                                "motor_thermal_ambient_resistance_w_c": 5.0,
                                "motor_thermal_heat_capacity_j_c": 50.0})
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.validate()  # must not raise


def test_thermal_sensor_requires_nHat_B():
    """A thermal sensor without its normal nHat_B is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"area_m2": 1.0, "absorptivity": 0.25, "emissivity": 0.34})]
    with pytest.raises(ScenarioValidationError, match="nHat_B"):
        sc.validate()


def test_thermal_sensor_requires_area_m2():
    """A thermal sensor without its area is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "absorptivity": 0.25,
                                                       "emissivity": 0.34})]
    with pytest.raises(ScenarioValidationError, match="area_m2"):
        sc.validate()


def test_thermal_sensor_requires_absorptivity_in_range():
    """A thermal sensor absorptivity above 1 is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "area_m2": 1.0, "absorptivity": 1.5,
                                                       "emissivity": 0.34})]
    with pytest.raises(ScenarioValidationError, match="absorptivity"):
        sc.validate()


def test_thermal_sensor_requires_emissivity_in_range():
    """A thermal sensor emissivity of 0 is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "area_m2": 1.0, "absorptivity": 0.25,
                                                       "emissivity": 0.0})]
    with pytest.raises(ScenarioValidationError, match="emissivity"):
        sc.validate()


def test_thermal_sensor_rejects_unrecognized_measurement_fault_mode():
    """A thermal sensor measurement fault mode the tool does not know is
    refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "area_m2": 1.0, "absorptivity": 0.25,
                                                       "emissivity": 0.34, "measurement_fault_mode": "bogus"})]
    with pytest.raises(ScenarioValidationError, match="measurement_fault_mode"):
        sc.validate()


def test_thermal_sensor_with_required_params_validates():
    """A thermal sensor with normal, area, absorptivity and emissivity
    validates when the Sun is in the run."""
    sc = _minimal_scenario(gravity=GravityConfig(third_body_perturbers=["sun"]))  # sensorThermal needs the Sun
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "area_m2": 1.0, "absorptivity": 0.25,
                                                       "emissivity": 0.34})]
    sc.validate()  # must not raise


def test_sunSafePoint_use_css_estimation_requires_a_coarse_sun_sensor():
    """use_css_estimation in sunSafePoint without a coarse sun sensor is
    refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].fsw_params = {"use_css_estimation": True}
    with pytest.raises(ScenarioValidationError, match="use_css_estimation"):
        sc.validate()


def test_sunSafePoint_use_css_estimation_with_a_coarse_sun_sensor_validates():
    """use_css_estimation in sunSafePoint with a coarse sun sensor
    validates."""
    sc = _minimal_scenario()
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].fsw_params = {"use_css_estimation": True}
    sc.spacecraft[0].sensors = [SensorConfig(kind="coarse_sun_sensor", name="css-1", params={"nHat_B": [0, 0, 1]})]
    sc.validate()  # must not raise


def test_thruster_requires_r_B():
    """A thruster without its position r_B is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1", params={"tHat_B": [1, 0, 0], "MaxThrust": 1.0})
    ]
    with pytest.raises(ScenarioValidationError, match="r_B"):
        sc.validate()


def test_thruster_requires_tHat_B():
    """A thruster without its direction tHat_B is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1", params={"r_B": [1, 0, 0], "MaxThrust": 1.0})
    ]
    with pytest.raises(ScenarioValidationError, match="tHat_B"):
        sc.validate()


def test_thruster_requires_MaxThrust():
    """A thruster without MaxThrust is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1", params={"r_B": [1, 0, 0], "tHat_B": [1, 0, 0]})
    ]
    with pytest.raises(ScenarioValidationError, match="MaxThrust"):
        sc.validate()


def test_thruster_with_all_required_params_validates():
    """A thruster with position, direction and MaxThrust validates."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 1.28], "tHat_B": [1, 0, 0], "MaxThrust": 1.0})
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.validate()  # must not raise


def test_mixing_reaction_wheel_and_thruster_actuators_rejected():
    """Reaction wheels and thrusters together, without momentum dumping, are
    refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [0, 1, 0], "MaxThrust": 1.0}),
    ]
    with pytest.raises(ScenarioValidationError, match="mix 'reaction_wheel' and 'thruster'"):
        sc.validate()


def test_momentum_dumping_allows_mixing_reaction_wheel_and_thruster():
    """With momentum dumping, reaction wheels and thrusters together
    validate."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [0, 1, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].momentum_dumping = MomentumDumpingConfig(hs_max=50.0)
    sc.validate()  # must not raise


def test_momentum_dumping_requires_reaction_wheel_actuator():
    """Momentum dumping without a reaction wheel is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [0, 1, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].momentum_dumping = MomentumDumpingConfig(hs_max=50.0)
    with pytest.raises(ScenarioValidationError, match="needs at least one 'reaction_wheel' actuator"):
        sc.validate()


def test_momentum_dumping_requires_thruster_actuator():
    """Momentum dumping without a thruster is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].momentum_dumping = MomentumDumpingConfig(hs_max=50.0)
    with pytest.raises(ScenarioValidationError, match="needs at least one 'thruster' actuator"):
        sc.validate()


def test_momentum_dumping_requires_hs_max_positive():
    """Momentum dumping with hs_max 0 is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [0, 1, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].momentum_dumping = MomentumDumpingConfig(hs_max=0.0)
    with pytest.raises(ScenarioValidationError, match="hs_max must be > 0"):
        sc.validate()


def test_momentum_dumping_round_trips():
    """Momentum dumping's hs_max, minimum fire time and counter limit survive
    to_dict and from_dict."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [0, 1, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].momentum_dumping = MomentumDumpingConfig(hs_max=65.0, thr_min_fire_time=0.05,
                                                                max_counter_value=50)
    sc.validate()
    loaded = Scenario.from_dict(sc.to_dict())
    loaded.validate()
    assert loaded.spacecraft[0].momentum_dumping.hs_max == 65.0
    assert loaded.spacecraft[0].momentum_dumping.thr_min_fire_time == 0.05
    assert loaded.spacecraft[0].momentum_dumping.max_counter_value == 50


def test_magnetic_torque_rod_requires_gtHat_B():
    """A magnetic torque rod without its axis gtHat_B is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1", params={"max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(wheel_speed_biases_rad_s=[])
    with pytest.raises(ScenarioValidationError, match="gtHat_B"):
        sc.validate()


def test_magnetic_torque_rod_requires_max_dipole_a_m2():
    """A magnetic torque rod without its maximum dipole is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1", params={"gtHat_B": [1, 0, 0]}),
    ]
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(wheel_speed_biases_rad_s=[])
    with pytest.raises(ScenarioValidationError, match="max_dipole_a_m2"):
        sc.validate()


def test_magnetic_torque_rod_without_magnetic_momentum_management_rejected():
    """A magnetic torque rod without magnetic momentum management is
    refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": 0.1}),
    ]
    with pytest.raises(ScenarioValidationError, match="magnetic_momentum_management"):
        sc.validate()


def test_magnetic_momentum_management_requires_reaction_wheel_actuator():
    """Magnetic momentum management without a reaction wheel is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(wheel_speed_biases_rad_s=[])
    with pytest.raises(ScenarioValidationError, match="needs at least one 'reaction_wheel' actuator"):
        sc.validate()


def test_magnetic_momentum_management_requires_magnetic_torque_rod_actuator():
    """Magnetic momentum management without a magnetic torque rod is
    refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(wheel_speed_biases_rad_s=[0.0])
    with pytest.raises(ScenarioValidationError, match="needs at least one 'magnetic_torque_rod' actuator"):
        sc.validate()


def test_magnetic_momentum_management_requires_one_bias_per_reaction_wheel():
    """One wheel-speed bias for two reaction wheels is refused: it needs one
    per wheel."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="reaction_wheel", name="rw-2", params={"gsHat_B": [0, 1, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(
        wheel_speed_biases_rad_s=[10.0]  # only 1 entry for 2 reaction wheels
    )
    with pytest.raises(ScenarioValidationError, match="needs exactly 2 entries"):
        sc.validate()


def test_magnetic_momentum_management_with_all_required_params_validates():
    """Magnetic momentum management with a wheel, a torque rod and one bias per
    wheel validates."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(wheel_speed_biases_rad_s=[10.0])
    sc.validate()  # must not raise


def test_fuel_tank_requires_a_thruster_actuator():
    """A fuel tank without a thruster is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].fuel_tank = FuelTankConfig(propellant_mass_kg=20.0, max_propellant_mass_kg=25.0)
    with pytest.raises(ScenarioValidationError, match="needs at least one 'thruster' actuator"):
        sc.validate()


def test_fuel_tank_propellant_mass_must_not_exceed_capacity():
    """A fuel tank holding more propellant than its capacity is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [1, 0, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].fuel_tank = FuelTankConfig(propellant_mass_kg=30.0, max_propellant_mass_kg=25.0)
    with pytest.raises(ScenarioValidationError, match="between 0 and max_propellant_mass_kg"):
        sc.validate()


def test_fuel_tank_requires_positive_capacity():
    """A fuel tank with zero capacity is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [1, 0, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].fuel_tank = FuelTankConfig(propellant_mass_kg=0.0, max_propellant_mass_kg=0.0)
    with pytest.raises(ScenarioValidationError, match="max_propellant_mass_kg must be > 0"):
        sc.validate()


def test_fuel_tank_with_thruster_actuator_validates():
    """A fuel tank within its capacity, with a thruster, validates."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [1, 0, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].fuel_tank = FuelTankConfig(propellant_mass_kg=20.0, max_propellant_mass_kg=25.0)
    sc.validate()  # must not raise


def test_fuel_tank_round_trips():
    """The fuel tank's propellant mass, capacity and position survive to_dict
    and from_dict."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [1, 0, 0], "MaxThrust": 1.0}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].fuel_tank = FuelTankConfig(
        propellant_mass_kg=20.0, max_propellant_mass_kg=25.0, tank_position_b_m=[0.1, 0.0, -0.2],
    )
    sc.validate()
    loaded = Scenario.from_dict(sc.to_dict())
    loaded.validate()
    assert loaded.spacecraft[0].fuel_tank.propellant_mass_kg == 20.0
    assert loaded.spacecraft[0].fuel_tank.max_propellant_mass_kg == 25.0
    assert loaded.spacecraft[0].fuel_tank.tank_position_b_m == [0.1, 0.0, -0.2]


def test_mixing_reaction_wheel_and_magnetic_torque_rod_without_config_rejected():
    """Unlike the thruster case, mixing reaction_wheel with
    magnetic_torque_rod isn't caught by the generic "mix rejected" rule
    (that rule only fires for reaction_wheel+thruster) -- it's caught
    instead by magnetic_torque_rod's own "needs magnetic_momentum_management"
    requirement, which fires regardless of what else is on the spacecraft.
    """
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    with pytest.raises(ScenarioValidationError, match="magnetic_momentum_management"):
        sc.validate()


def test_momentum_dumping_and_magnetic_momentum_management_are_mutually_exclusive():
    """Both independently require 'reaction_wheel' actuators and both get
    built as SEPARATE, independent desaturation control paths in
    engine.service (confirmed by audit: two independent `if` blocks, not
    elif) -- setting both on one spacecraft would silently have two
    controllers fighting over the same wheels. A spacecraft can be pushed
    into exactly this combination: momentum_dumping is REQUIRED whenever
    'reaction_wheel'+'thruster' are mixed (e.g. for a fuel_tank, which
    needs 'thruster'), while a 'magnetic_torque_rod' actuator independently
    REQUIRES magnetic_momentum_management.
    """
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="thruster", name="thr-1",
                        params={"r_B": [1, 0, 0], "tHat_B": [0, 1, 0], "MaxThrust": 1.0}),
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].momentum_dumping = MomentumDumpingConfig(hs_max=50.0)
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(wheel_speed_biases_rad_s=[0.0])
    with pytest.raises(ScenarioValidationError, match="mutually exclusive"):
        sc.validate()


def test_magnetic_momentum_management_round_trips():
    """Magnetic momentum management's wheel-speed biases and gain survive
    to_dict and from_dict."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(
        wheel_speed_biases_rad_s=[12.5], c_gain=0.01,
    )
    sc.validate()
    loaded = Scenario.from_dict(sc.to_dict())
    loaded.validate()
    assert loaded.spacecraft[0].magnetic_momentum_management.wheel_speed_biases_rad_s == [12.5]
    assert loaded.spacecraft[0].magnetic_momentum_management.c_gain == 0.01


@pytest.mark.parametrize("field_name", ["drag_coeff", "drag_area_m2", "srp_coeff", "srp_area_m2"])
@pytest.mark.parametrize("bad_value", [0.0, -1.0])
def test_non_positive_drag_or_srp_coefficient_or_area_rejected(field_name, bad_value):
    """engine.service feeds these straight into Basilisk's drag/SRP
    effectors as a physical projected area/coefficient -- neither effector
    itself rejects a non-positive value, so this would otherwise silently
    produce a reversed or zero-magnitude force instead of a clear error.
    """
    sc = _minimal_scenario()
    setattr(sc.spacecraft[0], field_name, bad_value)
    with pytest.raises(ScenarioValidationError, match=field_name):
        sc.validate()


def test_unsupported_fsw_mode_rejected():
    """An FSW mode the tool does not offer is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].fsw_mode = "sunTrackingRasterScan"
    with pytest.raises(ScenarioValidationError, match="fsw_mode"):
        sc.validate()


def test_none_fsw_mode_is_valid():
    """A spacecraft without an FSW mode (the default) validates."""
    _minimal_scenario().validate()  # fsw_mode defaults to None -- must not raise


def test_none_vizard_model_path_is_valid():
    """A spacecraft without a Vizard model path (the default) validates."""
    _minimal_scenario().validate()  # vizard_model_path defaults to None -- must not raise


def test_blank_vizard_model_path_rejected():
    """A Vizard model path of only spaces is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].vizard_model_path = "   "
    with pytest.raises(ScenarioValidationError, match="vizard_model_path must not be blank"):
        sc.validate()


@pytest.mark.parametrize("field", ["vizard_model_offset_m", "vizard_model_rotation_deg", "vizard_model_scale"])
def test_vizard_model_vectors_require_3_elements(field):
    """The Vizard model offset, rotation and scale with two elements each are
    refused."""
    sc = _minimal_scenario()
    setattr(sc.spacecraft[0], field, [1.0, 2.0])
    with pytest.raises(ScenarioValidationError, match=f"{field} must have 3 elements"):
        sc.validate()


def test_vizard_model_path_round_trips_through_json(tmp_path):
    """The Vizard model path, offset, rotation and scale survive writing to
    JSON and loading."""
    sc = _minimal_scenario()
    sc.spacecraft[0].vizard_model_path = "CUBE"
    sc.spacecraft[0].vizard_model_offset_m = [0.1, 0.2, 0.3]
    sc.spacecraft[0].vizard_model_rotation_deg = [10.0, 20.0, 30.0]
    sc.spacecraft[0].vizard_model_scale = [2.0, 2.0, 2.0]
    sc.validate()

    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(sc.to_dict(), indent=2))
    loaded = load_scenario(path)
    assert loaded.spacecraft[0].vizard_model_path == "CUBE"
    assert loaded.spacecraft[0].vizard_model_offset_m == [0.1, 0.2, 0.3]
    assert loaded.spacecraft[0].vizard_model_rotation_deg == [10.0, 20.0, 30.0]
    assert loaded.spacecraft[0].vizard_model_scale == [2.0, 2.0, 2.0]


@pytest.mark.parametrize("mode", ["inertial3D", "hillPoint", "velocityPoint", "sunSafePoint"])
def test_every_supported_fsw_mode_validates(mode):
    """inertial3D, hillPoint, velocityPoint and sunSafePoint each validate on a
    plain spacecraft."""
    sc = _minimal_scenario()
    sc.spacecraft[0].fsw_mode = mode
    sc.validate()  # must not raise


def test_location_pointing_requires_exactly_one_target():
    """locationPointing with no target, or with both a ground station and a
    body, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].fsw_mode = "locationPointing"
    sc.spacecraft[0].fsw_params = {}  # neither target given
    with pytest.raises(ScenarioValidationError, match="exactly one of"):
        sc.validate()

    sc.spacecraft[0].fsw_params = {"target_ground_station": "gs-1", "target_body": "sun"}  # both given
    with pytest.raises(ScenarioValidationError, match="exactly one of"):
        sc.validate()


def test_location_pointing_target_ground_station_must_exist():
    """locationPointing at a ground station the scenario does not have is
    refused."""
    sc = _minimal_scenario()
    sc.ground_stations = [GroundStationConfig(name="gs-1", latitude_deg=40.0, longitude_deg=-105.0)]
    sc.spacecraft[0].fsw_mode = "locationPointing"
    sc.spacecraft[0].fsw_params = {"target_ground_station": "gs-does-not-exist"}
    with pytest.raises(ScenarioValidationError, match="not one of this scenario's ground_stations"):
        sc.validate()


def test_location_pointing_with_existing_ground_station_validates():
    """locationPointing at one of the scenario's ground stations validates."""
    sc = _minimal_scenario()
    sc.ground_stations = [GroundStationConfig(name="gs-1", latitude_deg=40.0, longitude_deg=-105.0)]
    sc.spacecraft[0].fsw_mode = "locationPointing"
    sc.spacecraft[0].fsw_params = {"target_ground_station": "gs-1"}
    sc.validate()  # must not raise


def test_location_pointing_target_body_requires_spice_tracking():
    """locationPointing at the Sun is refused when the Sun is not in the run
    (no SPICE ephemeris)."""
    sc = _minimal_scenario()
    sc.spacecraft[0].fsw_mode = "locationPointing"
    sc.spacecraft[0].fsw_params = {"target_body": "sun"}  # not in gravity.third_body_perturbers
    with pytest.raises(ScenarioValidationError, match="needs a real SPICE ephemeris"):
        sc.validate()


def test_location_pointing_with_spice_tracked_target_body_validates():
    """locationPointing at the Moon validates when the Moon is a third body."""
    sc = _minimal_scenario(gravity=GravityConfig(central_body="earth", third_body_perturbers=["moon"]))
    sc.spacecraft[0].fsw_mode = "locationPointing"
    sc.spacecraft[0].fsw_params = {"target_body": "moon"}
    sc.validate()  # must not raise


def test_location_pointing_target_body_can_be_the_central_body():
    """locationPointing at the central body validates."""
    sc = _minimal_scenario(gravity=GravityConfig(central_body="earth"))
    sc.spacecraft[0].fsw_mode = "locationPointing"
    sc.spacecraft[0].fsw_params = {"target_body": "earth"}
    sc.validate()  # must not raise


# -- Phase 3: Monte Carlo validation ------------------------------------------

def test_monte_carlo_defaults_to_disabled_and_validates():
    """Monte Carlo is off by default, without dispersions, and the default
    validates."""
    _minimal_scenario().validate()  # monte_carlo defaults to enabled=False, no dispersions


def test_monte_carlo_num_runs_must_be_positive():
    """Monte Carlo with zero runs is refused."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(enabled=True, num_runs=0)
    with pytest.raises(ScenarioValidationError, match="num_runs must be between 1 and 100000, got 0"):
        sc.validate()


def test_monte_carlo_thread_count_must_be_positive():
    """Monte Carlo with zero threads is refused."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(enabled=True, thread_count=0)
    with pytest.raises(ScenarioValidationError, match="thread_count must be between 1 and 256, got 0"):
        sc.validate()



@pytest.mark.parametrize("key, value, limit", [
    ("num_runs", 10 ** 9, 100_000),
    ("thread_count", 10 ** 6, 256),
])
def test_monte_carlo_counts_have_an_upper_limit(key, value, limit):
    """Audit R4: a shared scenario with a billion runs or a million
    processes passed validate. Each count now has a limit; the limit
    itself is accepted."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(enabled=True, **{key: value})
    with pytest.raises(ScenarioValidationError, match=f"{key} must be between 1 and {limit}, got {value}"):
        sc.validate()
    sc.monte_carlo = MonteCarloConfig(enabled=True, **{key: limit})
    sc.validate()


def test_a_batch_runs_at_most_one_process_per_cpu(monkeypatch):
    """Audit R4: more processes than CPUs only compete for the same
    cores. The batch uses one per CPU, and the Overview says so."""
    import os

    from spacemissionstudio.engine.scenario_checks import scenario_warnings
    from spacemissionstudio.schema.scenario import usable_thread_count

    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    assert [usable_thread_count(n) for n in (1, 4, 5, 256)] == [1, 4, 4, 4]
    monkeypatch.setattr(os, "cpu_count", lambda: None)  # unknown: one at a time
    assert usable_thread_count(8) == 1
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(enabled=True, thread_count=16)
    assert "Monte Carlo asks for 16 processes; this computer has 4 CPUs, so it runs that many at once" \
        in scenario_warnings(sc)
    sc.monte_carlo = MonteCarloConfig(enabled=True, thread_count=4)
    assert not [w for w in scenario_warnings(sc) if w.startswith("Monte Carlo")]

def test_dispersion_unsupported_quantity_rejected():
    """A dispersion of a quantity the tool does not offer is refused."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(
        enabled=True,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="orbit_position", kind="uniform", bounds=[0, 1])],
    )
    with pytest.raises(ScenarioValidationError, match="quantity"):
        sc.validate()


def test_dispersion_kind_not_valid_for_quantity_rejected():
    """A dispersion kind that does not fit its quantity (uniform_euler_mrp on
    dry mass) is refused."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(
        enabled=True,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform_euler_mrp",
                                       bounds=[0, 1])],
    )
    with pytest.raises(ScenarioValidationError, match="must be one of"):
        sc.validate()


def test_dispersion_uniform_requires_bounds():
    """A uniform dispersion without bounds is refused."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(
        enabled=True,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform")],
    )
    with pytest.raises(ScenarioValidationError, match="needs bounds"):
        sc.validate()


def test_dispersion_normal_requires_mean_and_std():
    """A normal dispersion without mean and standard deviation is refused."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(
        enabled=True,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="normal")],
    )
    with pytest.raises(ScenarioValidationError, match="needs mean and std_deviation"):
        sc.validate()


def test_dispersion_unknown_spacecraft_rejected():
    """A dispersion on a spacecraft the scenario does not have is refused."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(
        enabled=True,
        dispersions=[DispersionConfig(spacecraft="does-not-exist", quantity="dry_mass_kg", kind="normal",
                                       mean=100.0, std_deviation=5.0)],
    )
    with pytest.raises(ScenarioValidationError, match="not one of this scenario's spacecraft"):
        sc.validate()


def test_valid_dispersions_validate():
    """A normal dry-mass dispersion and a uniform attitude dispersion
    validate."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(
        enabled=True, num_runs=25,
        dispersions=[
            DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="normal", mean=100.0, std_deviation=5.0),
            DispersionConfig(spacecraft="sat-1", quantity="attitude_sigma_bn", kind="uniform_euler_mrp",
                              bounds=[0.0, 6.283185307]),
        ],
    )
    sc.validate()  # must not raise


def _with_dispersion(sc, **fields):
    sc.monte_carlo = MonteCarloConfig(enabled=True, dispersions=[DispersionConfig(spacecraft="sat-1", **fields)])
    return sc


def test_the_new_dispersion_quantities_validate():
    """Orbit elements, inertia, body rate and the drag and SRP coefficients."""
    sc = _minimal_scenario()
    sc.spacecraft[0].enable_drag = True
    sc.spacecraft[0].enable_srp = True
    sc.gravity.third_body_perturbers = ["sun"]
    sc.monte_carlo = MonteCarloConfig(enabled=True, dispersions=[
        DispersionConfig(spacecraft="sat-1", quantity="orbit_elements", kind="normal",
                         element_spread={"semi_major_axis_km": 0.5, "true_anomaly_deg": 0.01}),
        DispersionConfig(spacecraft="sat-1", quantity="inertia_kg_m2", kind="normal", std_deviation=0.5,
                         angle_std_deg=1.0),
        DispersionConfig(spacecraft="sat-1", quantity="angular_rate_bn_b", kind="uniform", bounds=[-0.1, 0.1]),
        DispersionConfig(spacecraft="sat-1", quantity="drag_coeff", kind="normal", mean=2.2, std_deviation=0.2),
        DispersionConfig(spacecraft="sat-1", quantity="srp_coeff", kind="uniform", bounds=[1.2, 1.5]),
    ])
    sc.validate()  # must not raise


@pytest.mark.parametrize("fields, message", [
    ({"quantity": "orbit_elements", "kind": "normal"}, "needs element_spread"),
    ({"quantity": "orbit_elements", "kind": "normal", "element_spread": {"altitude_km": 1.0}}, "element_spread key"),
    ({"quantity": "orbit_elements", "kind": "uniform", "element_spread": {"raan_deg": -1.0}}, ">= 0"),
    ({"quantity": "inertia_kg_m2", "kind": "normal"}, "needs std_deviation"),
    ({"quantity": "inertia_kg_m2", "kind": "normal", "std_deviation": 1.0, "angle_std_deg": -2.0}, "angle_std_deg"),
    ({"quantity": "angular_rate_bn_b", "kind": "uniform"}, "needs bounds"),
    ({"quantity": "drag_coeff", "kind": "normal", "std_deviation": 0.1}, "needs mean and std_deviation"),
])
def test_a_badly_formed_new_dispersion_is_rejected(fields, message):
    """Each new quantity checks the fields it uses, and says which one."""
    with pytest.raises(ScenarioValidationError, match=message):
        _with_dispersion(_minimal_scenario(), **fields).validate()


@pytest.mark.parametrize("fields, message", [
    ({"quantity": "drag_coeff", "kind": "uniform", "bounds": [2.0, 3.0]}, "needs enable_drag"),
    ({"quantity": "srp_coeff", "kind": "uniform", "bounds": [1.2, 1.5]}, "needs enable_srp"),
])
def test_a_coefficient_dispersion_needs_its_force_model(fields, message):
    """Dispersing the drag or SRP coefficient of a spacecraft with that force off is an error."""
    with pytest.raises(ScenarioValidationError, match=message):
        _with_dispersion(_minimal_scenario(), **fields).validate()


@pytest.mark.parametrize("quantity, extra", [
    ("inertia_kg_m2", {"std_deviation": 0.5}),
    ("angular_rate_bn_b", {"std_deviation": 0.05}),
])
def test_attitude_dispersions_need_full_attitude(quantity, extra):
    """Inertia and body rate do nothing without attitude dynamics."""
    sc = _with_dispersion(_minimal_scenario(simulation_mode="orbit_only"), quantity=quantity, kind="normal", **extra)
    with pytest.raises(ScenarioValidationError, match="attitude is not simulated"):
        sc.validate()


def test_monte_carlo_round_trips_through_save_load(tmp_path):
    """Monte Carlo's switch, run count, thread count and dispersions survive a
    save and load."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(
        enabled=True, num_runs=25, thread_count=2,
        dispersions=[DispersionConfig(spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=[95.0, 105.0])],
    )
    path = tmp_path / "scenario.json"
    sc.save(path)
    loaded = load_scenario(path)

    assert loaded.monte_carlo.enabled is True
    assert loaded.monte_carlo.num_runs == 25
    assert loaded.monte_carlo.thread_count == 2
    assert loaded.monte_carlo.dispersions[0].quantity == "dry_mass_kg"
    assert loaded.monte_carlo.dispersions[0].bounds == [95.0, 105.0]


def test_old_scenario_file_without_monte_carlo_key_still_loads(tmp_path):
    """A schema 1 file without a monte_carlo key loads with Monte Carlo off and
    no dispersions."""
    path = tmp_path / "old.json"
    path.write_text(json.dumps({
        "schema_version": 1, "name": "old scenario", "epoch_utc": "2030-01-01T00:00:00",
        "spacecraft": [{
            "name": "sat-1",
            "orbit": {"type": "cartesian", "position_km": [7000, 0, 0], "velocity_km_s": [0, 7.5, 0]},
        }],
    }))
    loaded = load_scenario(path)
    assert loaded.monte_carlo.enabled is False
    assert loaded.monte_carlo.dispersions == []


def test_phase2_fields_round_trip_through_save_load(tmp_path):
    """Sensor and actuator parameters, the FSW mode and the control gains
    survive a save and load."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="coarse_sun_sensor", name="css-1", params={"nHat_B": [1, 0, 0]})]
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [0, 1, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0})]
    sc.spacecraft[0].fsw_mode = "hillPoint"
    sc.spacecraft[0].control_params = {"K": 4.0, "P": 25.0}

    path = tmp_path / "scenario.json"
    sc.save(path)
    loaded = load_scenario(path)

    assert loaded.spacecraft[0].sensors[0].params["nHat_B"] == [1, 0, 0]
    assert loaded.spacecraft[0].actuators[0].params["gsHat_B"] == [0, 1, 0]
    assert loaded.spacecraft[0].fsw_mode == "hillPoint"
    assert loaded.spacecraft[0].control_params == {"K": 4.0, "P": 25.0}


def test_power_and_rf_link_default_to_none():
    """Power and RF link are unset by default, and a spacecraft without them
    validates."""
    sc = _minimal_scenario()
    assert sc.spacecraft[0].power is None
    assert sc.spacecraft[0].rf_link is None
    sc.validate()  # must not raise -- neither field is required


def test_power_config_round_trips_through_save_load(tmp_path):
    """Power and RF-link settings load back as their own classes with their
    values."""
    sc = _minimal_scenario(gravity=GravityConfig(third_body_perturbers=["sun"]))
    sc.spacecraft[0].power = PowerConfig(panel_area_m2=1.2, panel_efficiency=0.29,
                                          bus_idle_power_w=25.0, battery_capacity_wh=120.0,
                                          battery_initial_soc=0.9)
    sc.spacecraft[0].rf_link = RFLinkConfig(tx_power_w=15.0, frequency_hz=8.2e9, data_rate_bps=1.0e6)

    path = tmp_path / "scenario.json"
    sc.save(path)
    loaded = load_scenario(path)

    assert isinstance(loaded.spacecraft[0].power, PowerConfig)
    assert loaded.spacecraft[0].power.panel_area_m2 == 1.2
    assert loaded.spacecraft[0].power.battery_initial_soc == 0.9
    assert isinstance(loaded.spacecraft[0].rf_link, RFLinkConfig)
    assert loaded.spacecraft[0].rf_link.tx_power_w == 15.0
    assert loaded.spacecraft[0].rf_link.frequency_hz == 8.2e9


def test_power_config_rejects_invalid_panel_efficiency():
    """A solar panel efficiency above 1 is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].power = PowerConfig(panel_area_m2=1.0, panel_efficiency=1.5)
    with pytest.raises(ScenarioValidationError, match="panel_efficiency"):
        sc.validate()


def test_power_config_rejects_invalid_initial_soc():
    """A battery initial state of charge above 1 is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].power = PowerConfig(panel_area_m2=1.0, panel_efficiency=0.3, battery_initial_soc=1.5)
    with pytest.raises(ScenarioValidationError, match="battery_initial_soc"):
        sc.validate()


def test_rf_link_config_rejects_non_positive_data_rate():
    """An RF link with a data rate of 0 is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].rf_link = RFLinkConfig(tx_power_w=10.0, frequency_hz=8.0e9, data_rate_bps=0.0)
    with pytest.raises(ScenarioValidationError, match="data_rate_bps"):
        sc.validate()


# -- Plausibility-bound checks (docs/ux_audit.md, "units enforced only
# by naming convention") -- a generous ceiling catching a likely
# magnitude typo (e.g. a units mixup) without rejecting anything
# physically real. ----------------------------------------------------

def test_power_config_rejects_implausibly_large_panel_area():
    """A solar panel area of 1e6 m^2, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].power = PowerConfig(panel_area_m2=1.0e6, panel_efficiency=0.3)
    with pytest.raises(ScenarioValidationError, match="panel_area_m2"):
        sc.validate()


def test_power_config_rejects_implausibly_large_battery_capacity():
    """A battery capacity of 1e9 Wh, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].power = PowerConfig(panel_area_m2=1.0, panel_efficiency=0.3, battery_capacity_wh=1.0e9)
    with pytest.raises(ScenarioValidationError, match="battery_capacity_wh"):
        sc.validate()


def test_rf_link_config_rejects_implausibly_large_tx_power():
    """A transmit power of 1e8 W, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].rf_link = RFLinkConfig(tx_power_w=1.0e8, frequency_hz=8.0e9, data_rate_bps=1.0e6)
    with pytest.raises(ScenarioValidationError, match="tx_power_w"):
        sc.validate()


def test_spacecraft_rejects_implausibly_large_dry_mass():
    """A dry mass of 1e12 kg, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].dry_mass_kg = 1.0e12
    with pytest.raises(ScenarioValidationError, match="dry_mass_kg"):
        sc.validate()


def test_spacecraft_rejects_diagonal_inertia_violating_the_triangle_inequality():
    """Real bug found against a real (newer) Basilisk build: a diagonal
    inertia tensor whose largest principal moment exceeds the sum of
    the other two is unphysical for any rigid body -- a newer Basilisk
    now rejects it deep inside InitializeSimulation() with a cryptic
    message ("IHubPntBc_B is not a valid inertia tensor"); this schema
    -level check catches the exact same mistake
    (tests/test_gravity_gradient.py shipped it, undetected against the
    2.12.0 baseline this project was built against) earlier, with a
    message that actually names the problem.
    """
    sc = _minimal_scenario()
    sc.spacecraft[0].inertia_kg_m2 = [5.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 20.0]  # 5 + 10 < 20
    with pytest.raises(ScenarioValidationError, match="triangle inequality"):
        sc.validate()


def test_spacecraft_rejects_diagonal_inertia_with_a_non_positive_entry():
    """A diagonal inertia with a negative moment is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].inertia_kg_m2 = [10.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 10.0]
    with pytest.raises(ScenarioValidationError, match="positive"):
        sc.validate()


def test_spacecraft_accepts_a_valid_elongated_diagonal_inertia():
    """Companion to the rejection tests above -- confirms the new check
    doesn't reject a legitimately asymmetric (non-spherical) inertia
    tensor that DOES satisfy the triangle inequality, the exact kind of
    value a gravity-gradient or attitude-dynamics scenario legitimately
    needs.
    """
    sc = _minimal_scenario()
    sc.spacecraft[0].inertia_kg_m2 = [5.0, 0.0, 0.0, 0.0, 8.0, 0.0, 0.0, 0.0, 10.0]  # 5 + 8 >= 10
    sc.validate()  # must not raise


def test_spacecraft_skips_the_triangle_check_for_a_non_diagonal_inertia_tensor():
    """Deliberately scoped: a fully general (off-diagonal-populated)
    inertia tensor isn't checked here at all (see the validator's own
    comment on why) -- confirms a non-diagonal tensor isn't rejected by
    this specific check even when its DIAGONAL entries alone would
    violate the triangle inequality (they aren't its true principal
    moments once off-diagonal terms are present).
    """
    sc = _minimal_scenario()
    sc.spacecraft[0].inertia_kg_m2 = [5.0, 1.0, 0.0, 1.0, 10.0, 0.0, 0.0, 0.0, 20.0]
    sc.validate()  # must not raise -- off-diagonal entries present, so skipped


def test_spacecraft_rejects_implausibly_large_drag_area():
    """A drag area of 1e8 m^2, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].drag_area_m2 = 1.0e8
    with pytest.raises(ScenarioValidationError, match="drag_area_m2"):
        sc.validate()


def test_spacecraft_rejects_implausibly_large_srp_area():
    """An SRP area of 1e8 m^2, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].srp_area_m2 = 1.0e8
    with pytest.raises(ScenarioValidationError, match="srp_area_m2"):
        sc.validate()


def test_thermal_sensor_rejects_implausibly_large_area():
    """A thermal sensor area of 1e8 m^2, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "area_m2": 1.0e8, "absorptivity": 0.25,
                                                       "emissivity": 0.34})]
    with pytest.raises(ScenarioValidationError, match="area_m2"):
        sc.validate()


def test_thermal_sensor_rejects_implausibly_large_mass_when_set():
    """A thermal sensor mass of 1e9 kg, likely a unit mix-up, is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "area_m2": 1.0, "absorptivity": 0.25,
                                                       "emissivity": 0.34, "mass_kg": 1.0e9})]
    with pytest.raises(ScenarioValidationError, match="mass_kg"):
        sc.validate()


def test_thermal_sensor_with_no_mass_kg_set_still_validates():
    """A thermal sensor without a mass validates: the mass is optional and its
    bound applies only when it is set."""
    # mass_kg stays genuinely optional -- this bound only applies when set.
    sc = _minimal_scenario(gravity=GravityConfig(third_body_perturbers=["sun"]))  # sensorThermal needs the Sun
    sc.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1",
                                               params={"nHat_B": [0, 0, 1], "area_m2": 1.0, "absorptivity": 0.25,
                                                       "emissivity": 0.34})]
    sc.validate()  # must not raise


def test_ground_station_rejects_non_positive_system_noise_temp():
    """A ground station with a system noise temperature of 0 K is refused."""
    gs = GroundStationConfig(name="gs1", latitude_deg=0.0, longitude_deg=0.0, system_noise_temp_k=0.0)
    with pytest.raises(ScenarioValidationError, match="system_noise_temp_k"):
        gs.validate()


def test_rf_link_antenna_beamwidth_deg_defaults_to_none():
    """The antenna beamwidth is unset by default, and an RF link without it
    validates."""
    rf_link = RFLinkConfig(tx_power_w=10.0, frequency_hz=8.0e9, data_rate_bps=1.0e6)
    assert rf_link.antenna_beamwidth_deg is None
    rf_link.validate("sat-1")  # must not raise -- not required


def test_rf_link_antenna_beamwidth_deg_rejects_non_positive():
    """An antenna beamwidth of 0 deg is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].rf_link = RFLinkConfig(tx_power_w=10.0, frequency_hz=8.0e9, data_rate_bps=1.0e6,
                                             antenna_beamwidth_deg=0.0)
    with pytest.raises(ScenarioValidationError, match="antenna_beamwidth_deg"):
        sc.validate()


def test_comms_pointing_defaults_to_none():
    """Comms pointing is unset by default, and a spacecraft without it
    validates."""
    sc = _minimal_scenario()
    assert sc.spacecraft[0].comms_pointing is None
    sc.validate()  # must not raise -- not required


def _comms_pointing_scenario(**overrides) -> Scenario:
    """A minimal, otherwise-valid scenario with one comms_pointing
    spacecraft and the ground station it targets -- the shared starting
    point for every comms_pointing validation test below.
    """
    defaults = dict(
        gravity=GravityConfig(third_body_perturbers=["sun"]),
        ground_stations=[GroundStationConfig(name="gs-1", latitude_deg=40.0, longitude_deg=-105.0)],
    )
    defaults.update(overrides)
    sc = _minimal_scenario(**defaults)
    sc.spacecraft[0].power = PowerConfig(panel_area_m2=0.4, panel_efficiency=0.28)
    sc.spacecraft[0].comms_pointing = CommsPointingConfig(target_ground_station="gs-1")
    return sc


def test_comms_pointing_valid_scenario_validates():
    """Comms pointing at an existing ground station, with the Sun in the run,
    validates."""
    _comms_pointing_scenario().validate()  # must not raise


def test_comms_pointing_round_trips_through_save_load(tmp_path):
    """Comms pointing's target station, boresight, Sun-pointing axis and power
    survive a save and load."""
    sc = _comms_pointing_scenario()
    sc.spacecraft[0].comms_pointing = CommsPointingConfig(
        target_ground_station="gs-1", antenna_boresight_b=[1.0, 0.0, 0.0],
        sun_pointing_axis_b=[0.0, 0.0, 1.0], comms_power_w=15.0,
    )

    path = tmp_path / "scenario.json"
    sc.save(path)
    loaded = load_scenario(path)

    assert isinstance(loaded.spacecraft[0].comms_pointing, CommsPointingConfig)
    assert loaded.spacecraft[0].comms_pointing.target_ground_station == "gs-1"
    assert loaded.spacecraft[0].comms_pointing.antenna_boresight_b == [1.0, 0.0, 0.0]
    assert loaded.spacecraft[0].comms_pointing.sun_pointing_axis_b == [0.0, 0.0, 1.0]
    assert loaded.spacecraft[0].comms_pointing.comms_power_w == 15.0


def test_comms_pointing_rejects_being_combined_with_fsw_mode():
    """Comms pointing together with an FSW mode is refused."""
    sc = _comms_pointing_scenario()
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    with pytest.raises(ScenarioValidationError, match="comms_pointing and fsw_mode"):
        sc.validate()


def test_comms_pointing_rejects_unknown_ground_station():
    """Comms pointing at a ground station the scenario does not have is
    refused, naming it."""
    sc = _comms_pointing_scenario()
    sc.spacecraft[0].comms_pointing.target_ground_station = "does-not-exist"
    with pytest.raises(ScenarioValidationError, match="does-not-exist"):
        sc.validate()


def test_comms_pointing_rejects_comms_power_without_power_config():
    """A comms power draw on a spacecraft without a power model is refused."""
    sc = _comms_pointing_scenario()
    sc.spacecraft[0].power = None
    sc.spacecraft[0].comms_pointing.comms_power_w = 15.0
    with pytest.raises(ScenarioValidationError, match="comms_power_w"):
        sc.validate()


def test_comms_pointing_allows_zero_comms_power_without_power_config():
    """Comms pointing without a power model validates when its power draw is 0
    (the default)."""
    sc = _comms_pointing_scenario()
    sc.spacecraft[0].power = None
    assert sc.spacecraft[0].comms_pointing.comms_power_w == 0.0
    sc.validate()  # must not raise -- comms_power_w defaults to 0.0


def test_comms_pointing_rejects_malformed_antenna_boresight():
    """A two-element antenna boresight is refused."""
    sc = _comms_pointing_scenario()
    sc.spacecraft[0].comms_pointing.antenna_boresight_b = [1.0, 0.0]
    with pytest.raises(ScenarioValidationError, match="antenna_boresight_b"):
        sc.validate()


def test_old_scenario_file_without_power_or_rf_link_keys_still_loads(tmp_path):
    """A schema 1 file without power, RF-link or station-keeping keys loads
    with all three unset."""
    path = tmp_path / "old.json"
    path.write_text(json.dumps({
        "schema_version": 1, "name": "old scenario", "epoch_utc": "2030-01-01T00:00:00",
        "spacecraft": [{
            "name": "sat-1",
            "orbit": {"type": "cartesian", "position_km": [7000, 0, 0], "velocity_km_s": [0, 7.5, 0]},
        }],
    }))
    loaded = load_scenario(path)
    assert loaded.spacecraft[0].power is None
    assert loaded.spacecraft[0].rf_link is None
    assert loaded.spacecraft[0].station_keeping is None


def test_station_keeping_defaults_to_none():
    """Station keeping is unset by default, and a spacecraft without it
    validates."""
    sc = _minimal_scenario()
    assert sc.spacecraft[0].station_keeping is None
    sc.validate()  # must not raise -- not required


def test_station_keeping_round_trips_through_save_load(tmp_path):
    """Station keeping's settings survive a save and load, with the default
    eclipse threshold kept."""
    sc = _minimal_scenario(gravity=GravityConfig(third_body_perturbers=["sun"]))
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0,
    )

    path = tmp_path / "scenario.json"
    sc.save(path)
    loaded = load_scenario(path)

    assert isinstance(loaded.spacecraft[0].station_keeping, StationKeepingConfig)
    assert loaded.spacecraft[0].station_keeping.target_altitude_km == 500.0
    assert loaded.spacecraft[0].station_keeping.propellant_kg == 2.0
    assert loaded.spacecraft[0].station_keeping.eclipse_sunlit_threshold == 0.99  # default preserved


def test_station_keeping_rejects_deadband_not_less_than_target_altitude():
    """A station-keeping deadband as large as the target altitude is
    refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=500.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0,
    )
    with pytest.raises(ScenarioValidationError, match="deadband_km"):
        sc.validate()


def test_station_keeping_rejects_zero_deadband():
    """A station-keeping deadband of 0 km is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=0.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0,
    )
    with pytest.raises(ScenarioValidationError, match="deadband_km"):
        sc.validate()


def test_station_keeping_rejects_non_positive_thrust():
    """Station keeping with a thrust of 0 N is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.0, isp_s=1500.0, propellant_kg=2.0,
    )
    with pytest.raises(ScenarioValidationError, match="thrust_n"):
        sc.validate()


def test_station_keeping_rejects_negative_propellant():
    """Station keeping with negative propellant is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=-1.0,
    )
    with pytest.raises(ScenarioValidationError, match="propellant_kg"):
        sc.validate()


def test_station_keeping_rejects_out_of_range_eclipse_threshold():
    """A station-keeping sunlit threshold above 1 is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0,
        eclipse_sunlit_threshold=1.5,
    )
    with pytest.raises(ScenarioValidationError, match="eclipse_sunlit_threshold"):
        sc.validate()


def _configure_comms_pointing(sc):
    sc.ground_stations = [GroundStationConfig(name="gs-1", latitude_deg=0.0, longitude_deg=0.0)]
    sc.spacecraft[0].comms_pointing = CommsPointingConfig(target_ground_station="gs-1")


@pytest.mark.parametrize("configure", [
    lambda sc: setattr(sc.spacecraft[0], "power", PowerConfig(panel_area_m2=1.0, panel_efficiency=0.29)),
    lambda sc: setattr(sc.spacecraft[0], "station_keeping", StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0)),
    lambda sc: setattr(sc.spacecraft[0], "enable_srp", True),
    _configure_comms_pointing,
], ids=["power", "station_keeping", "enable_srp", "comms_pointing"])
def test_power_station_keeping_or_srp_without_sun_third_body_is_rejected(configure):
    """Mirrors engine.service.SimulationService.build()'s own
    SimulationServiceError (simpleSolarPanel/the eclipse gate/SRP all
    need a real eclipse shadow factor, which needs a sun ephemeris) --
    caught for real against two of this project's own bundled templates
    (05, 07), which validated cleanly here but failed the moment they
    were actually run. The comms_pointing case is a regression test for
    the exact same gap: comms_pointing's own internal sunSafePoint chain
    (engine.service's comms_pointing branch) needs a real sun ephemeris
    too, but Scenario.validate()'s needs_sun check didn't originally
    include it, so a comms_pointing scenario with no sun third-body
    validated cleanly here and only failed (silently sun-pointing on a
    zero/garbage heading) once actually run.
    """
    sc = _minimal_scenario()
    assert "sun" not in sc.gravity.third_body_perturbers
    configure(sc)
    with pytest.raises(ScenarioValidationError, match="third_body_perturbers"):
        sc.validate()


@pytest.mark.parametrize("configure", [
    lambda sc: setattr(sc.spacecraft[0], "power", PowerConfig(panel_area_m2=1.0, panel_efficiency=0.29)),
    lambda sc: setattr(sc.spacecraft[0], "station_keeping", StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0)),
    lambda sc: setattr(sc.spacecraft[0], "enable_srp", True),
    _configure_comms_pointing,
], ids=["power", "station_keeping", "enable_srp", "comms_pointing"])
def test_power_station_keeping_or_srp_with_sun_third_body_validates(configure):
    """Power, station keeping, SRP and comms pointing each validate when the
    Sun is a third body."""
    sc = _minimal_scenario(gravity=GravityConfig(third_body_perturbers=["sun"]))
    configure(sc)
    sc.validate()  # must not raise


def test_no_power_station_keeping_or_srp_does_not_need_sun_third_body():
    """A spacecraft with nothing that needs an eclipse shadow validates without
    the Sun."""
    sc = _minimal_scenario()
    assert "sun" not in sc.gravity.third_body_perturbers
    sc.validate()  # must not raise -- nothing here needs an eclipse shadow factor


def test_constant_thrust_defaults_to_none():
    """Constant thrust is unset by default, and a spacecraft without it
    validates."""
    sc = _minimal_scenario()
    assert sc.spacecraft[0].constant_thrust is None
    sc.validate()  # must not raise -- not required


def test_magnetometer_sensor_without_earth_central_body_is_rejected():
    """Mirrors engine.fsw.attach_sensors()'s own FswError (magneticFieldWMM,
    the only magnetic-field model this app wires up, is Earth-only) --
    a real audit finding: a magnetometer sensor was schema-valid on ANY
    central_body, only failing much later at Run Simulation time, the
    exact "validates cleanly but guaranteed to fail at run time" gap
    this schema already closed for power/station_keeping/enable_srp/
    comms_pointing needing a sun ephemeris (see the tests above).
    """
    sc = _minimal_scenario(gravity=GravityConfig(central_body="mars barycenter"))
    sc.spacecraft[0].sensors = [SensorConfig(kind="magnetometer", name="mag-1")]
    with pytest.raises(ScenarioValidationError, match="magnetometer"):
        sc.validate()


def test_magnetometer_sensor_with_earth_central_body_validates():
    """A magnetometer validates around Earth."""
    sc = _minimal_scenario(gravity=GravityConfig(central_body="earth"))
    sc.spacecraft[0].sensors = [SensorConfig(kind="magnetometer", name="mag-1")]
    sc.validate()  # must not raise


def test_magnetic_momentum_management_without_earth_central_body_is_rejected():
    """Mirrors engine.service.SimulationService.build()'s own
    SimulationServiceError for the same Earth-only magneticFieldWMM
    restriction -- MagneticMomentumManagementConfig's own docstring
    already pointed at this exact gap as deferred-to-the-engine-layer;
    this closes it, same as the magnetometer sensor case above.
    """
    sc = _minimal_scenario(gravity=GravityConfig(central_body="mars barycenter"))
    sc.spacecraft[0].actuators = [
        ActuatorConfig(kind="reaction_wheel", name="rw-1",
                        params={"gsHat_B": [1.0, 0.0, 0.0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0}),
        ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                        params={"gtHat_B": [1.0, 0.0, 0.0], "max_dipole_a_m2": 0.1}),
    ]
    sc.spacecraft[0].magnetic_momentum_management = MagneticMomentumManagementConfig(
        wheel_speed_biases_rad_s=[0.0]
    )
    with pytest.raises(ScenarioValidationError, match="magnetic_momentum_management"):
        sc.validate()


def test_constant_thrust_round_trips_through_save_load(tmp_path):
    """Constant thrust's frame, direction and thrust survive a save and
    load."""
    sc = _minimal_scenario()
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig(
        frame="RTN", direction=[0.0, 1.0, 0.0], thrust_n=0.05, isp_s=2000.0, propellant_kg=1.5,
    )

    path = tmp_path / "scenario.json"
    sc.save(path)
    loaded = load_scenario(path)

    assert isinstance(loaded.spacecraft[0].constant_thrust, ConstantThrustConfig)
    assert loaded.spacecraft[0].constant_thrust.frame == "RTN"
    assert loaded.spacecraft[0].constant_thrust.direction == [0.0, 1.0, 0.0]
    assert loaded.spacecraft[0].constant_thrust.thrust_n == 0.05


def test_constant_thrust_defaults_to_vnb_prograde():
    """Constant thrust defaults to the VNB frame along +V (prograde)."""
    config = ConstantThrustConfig()
    assert config.frame == "VNB"
    assert config.direction == [1.0, 0.0, 0.0]


def test_constant_thrust_rejects_unknown_frame():
    """A constant-thrust frame the tool does not offer (LVLH) is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig(frame="LVLH")
    with pytest.raises(ScenarioValidationError, match="frame"):
        sc.validate()


def test_constant_thrust_rejects_wrong_length_direction():
    """A two-element constant-thrust direction is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig(direction=[1.0, 0.0])
    with pytest.raises(ScenarioValidationError, match="direction"):
        sc.validate()


def test_constant_thrust_rejects_zero_direction_vector():
    """A zero constant-thrust direction is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig(direction=[0.0, 0.0, 0.0])
    with pytest.raises(ScenarioValidationError, match="non-zero, finite"):
        sc.validate()


def test_constant_thrust_rejects_non_positive_thrust():
    """Constant thrust of 0 N is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig(thrust_n=0.0)
    with pytest.raises(ScenarioValidationError, match="thrust_n"):
        sc.validate()


def test_constant_thrust_rejects_non_positive_isp():
    """Constant thrust with a specific impulse of 0 s is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig(isp_s=0.0)
    with pytest.raises(ScenarioValidationError, match="isp_s"):
        sc.validate()


def test_constant_thrust_rejects_negative_propellant():
    """Constant thrust with negative propellant is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig(propellant_kg=-1.0)
    with pytest.raises(ScenarioValidationError, match="propellant_kg"):
        sc.validate()


def test_constant_thrust_allowed_alongside_station_keeping():
    """Independent propellant budgets -- see ConstantThrustConfig's
    docstring -- so both may be set on the same spacecraft at once.
    """
    sc = _minimal_scenario(gravity=GravityConfig(third_body_perturbers=["sun"]))
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0,
    )
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig()
    sc.validate()  # must not raise


def test_simulation_mode_defaults_to_full_attitude():
    """The simulation mode defaults to full_attitude, and the default
    validates."""
    sc = _minimal_scenario()
    assert sc.simulation_mode == "full_attitude"
    sc.validate()  # must not raise


def test_simulation_mode_rejects_unknown_value():
    """A simulation mode the tool does not offer is refused."""
    sc = _minimal_scenario()
    sc.simulation_mode = "cannonball"
    with pytest.raises(ScenarioValidationError, match="simulation_mode"):
        sc.validate()


def test_orbit_only_mode_rejects_fsw_mode():
    """An FSW mode in an orbit-only run is refused."""
    sc = _minimal_scenario(simulation_mode="orbit_only")
    sc.spacecraft[0].fsw_mode = "hillPoint"
    with pytest.raises(ScenarioValidationError, match="fsw_mode"):
        sc.validate()


def test_orbit_only_mode_rejects_sensors():
    """Sensors in an orbit-only run are refused."""
    sc = _minimal_scenario(simulation_mode="orbit_only")
    sc.spacecraft[0].sensors = [SensorConfig(kind="imu", name="imu-1")]
    with pytest.raises(ScenarioValidationError, match="sensors"):
        sc.validate()


def test_orbit_only_mode_rejects_actuators():
    """Actuators in an orbit-only run are refused."""
    sc = _minimal_scenario(simulation_mode="orbit_only")
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="reaction_wheel", name="rw-1", params={"gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0})]
    with pytest.raises(ScenarioValidationError, match="actuators"):
        sc.validate()


def test_orbit_only_mode_rejects_power():
    """A power model in an orbit-only run is refused."""
    sc = _minimal_scenario(simulation_mode="orbit_only")
    sc.spacecraft[0].power = PowerConfig(panel_area_m2=1.0, panel_efficiency=0.29)
    with pytest.raises(ScenarioValidationError, match="power"):
        sc.validate()


def test_orbit_only_mode_allows_station_keeping_and_constant_thrust():
    """Neither needs an attitude model -- see Scenario.simulation_mode's
    docstring -- so both remain usable in orbit_only mode.
    """
    sc = _minimal_scenario(simulation_mode="orbit_only", gravity=GravityConfig(third_body_perturbers=["sun"]))
    sc.spacecraft[0].station_keeping = StationKeepingConfig(
        target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01, isp_s=1500.0, propellant_kg=2.0,
    )
    sc.spacecraft[0].constant_thrust = ConstantThrustConfig()
    sc.spacecraft[0].enable_drag = True
    sc.validate()  # must not raise


def test_orbit_only_mode_allows_plain_cannonball_spacecraft():
    """An orbit-only spacecraft with drag and SRP validates."""
    sc = _minimal_scenario(simulation_mode="orbit_only", gravity=GravityConfig(third_body_perturbers=["sun"]))
    sc.spacecraft[0].enable_drag = True
    sc.spacecraft[0].drag_area_m2 = 2.5
    sc.spacecraft[0].enable_srp = True
    sc.validate()  # must not raise


def _chief_and_follower_scenario(**follower_overrides):
    chief = SpacecraftConfig(
        name="chief",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.0,
                      inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),
    )
    follower_kwargs = dict(
        name="follower",
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.0,
                      inclination_deg=51.6, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=10.0),
        station_keeping=StationKeepingConfig(target_altitude_km=500.0, deadband_km=1.0, thrust_n=0.01,
                                              isp_s=1500.0, propellant_kg=2.0),
        phasing_keeping=PhasingKeepingConfig(chief_spacecraft="chief", target_separation_km=[100.0]),
    )
    follower_kwargs.update(follower_overrides)
    follower = SpacecraftConfig(**follower_kwargs)
    # station_keeping (set on `follower` by default above -- phasing_keeping
    # always needs it on the same spacecraft) needs a sun ephemeris for its
    # eclipse-gated reboost burn -- see Scenario.validate()'s own mirrored
    # check of engine.service.SimulationService.build()'s requirement.
    return Scenario(name="phasing test", epoch_utc="2030-01-01T00:00:00", spacecraft=[chief, follower],
                     gravity=GravityConfig(third_body_perturbers=["sun"]))


def test_phasing_keeping_defaults_to_none():
    """Phasing keeping is unset by default, and a spacecraft without it
    validates."""
    sc = _minimal_scenario()
    assert sc.spacecraft[0].phasing_keeping is None
    sc.validate()  # must not raise


def test_phasing_keeping_round_trips_through_save_load(tmp_path):
    """Phasing keeping's chief and target separation survive a save and load,
    with the default tolerance kept."""
    scenario = _chief_and_follower_scenario()
    path = tmp_path / "phasing.json"
    scenario.save(path)
    loaded = load_scenario(path)

    follower = next(sc for sc in loaded.spacecraft if sc.name == "follower")
    assert isinstance(follower.phasing_keeping, PhasingKeepingConfig)
    assert follower.phasing_keeping.chief_spacecraft == "chief"
    assert follower.phasing_keeping.target_separation_km == [100.0]
    assert follower.phasing_keeping.tolerance_fraction == 0.10  # default preserved


def test_phasing_keeping_requires_station_keeping_on_same_spacecraft():
    """Phasing keeping on a follower without station keeping is refused."""
    scenario = _chief_and_follower_scenario(station_keeping=None)
    with pytest.raises(ScenarioValidationError, match="requires station_keeping"):
        scenario.validate()


def test_phasing_keeping_rejects_chief_being_itself():
    """A follower that names itself as its chief is refused."""
    scenario = _chief_and_follower_scenario()
    scenario.spacecraft[1].phasing_keeping.chief_spacecraft = "follower"
    with pytest.raises(ScenarioValidationError, match="cannot be the spacecraft itself"):
        scenario.validate()


def test_phasing_keeping_rejects_unknown_chief_spacecraft():
    """A chief the scenario does not have is refused."""
    scenario = _chief_and_follower_scenario()
    scenario.spacecraft[1].phasing_keeping.chief_spacecraft = "no-such-satellite"
    with pytest.raises(ScenarioValidationError, match="chief_spacecraft"):
        scenario.validate()


def test_phasing_keeping_rejects_empty_target_separation():
    """Phasing keeping without a target separation is refused."""
    scenario = _chief_and_follower_scenario()
    scenario.spacecraft[1].phasing_keeping.target_separation_km = []
    with pytest.raises(ScenarioValidationError, match="target_separation_km"):
        scenario.validate()


def test_phasing_keeping_rejects_non_positive_target_separation():
    """A target separation of 0 km in the list is refused."""
    scenario = _chief_and_follower_scenario()
    scenario.spacecraft[1].phasing_keeping.target_separation_km = [100.0, 0.0]
    with pytest.raises(ScenarioValidationError, match="target_separation_km"):
        scenario.validate()


@pytest.mark.parametrize("field,value,match", [
    ("reconfiguration_interval_days", -1.0, "reconfiguration_interval_days"),
    ("tolerance_fraction", 0.0, "tolerance_fraction"),
    ("restore_tolerance_fraction", 0.0, "restore_tolerance_fraction"),
    ("correction_window_days", 0.0, "correction_window_days"),
    ("max_drift_days", 0.0, "max_drift_days"),
    ("max_delta_semi_major_axis_km", 0.0, "max_delta_semi_major_axis_km"),
])
def test_phasing_keeping_rejects_bad_tuning_knobs(field, value, match):
    """Each phasing-keeping tuning value out of range (a negative
    reconfiguration interval, or a zero tolerance, window, drift time or
    semi-major-axis step) is refused, naming the field."""
    scenario = _chief_and_follower_scenario()
    setattr(scenario.spacecraft[1].phasing_keeping, field, value)
    with pytest.raises(ScenarioValidationError, match=match):
        scenario.validate()


def test_phasing_keeping_full_scenario_validates():
    """A chief and a follower with station keeping and phasing keeping
    validate."""
    scenario = _chief_and_follower_scenario()
    scenario.validate()  # must not raise


# -- Mission sequence (schema.command.Command) -------------------------------

def test_mission_sequence_defaults_to_empty_list():
    """The mission sequence is empty by default."""
    assert _minimal_scenario().mission_sequence == []


def test_mission_sequence_empty_does_not_affect_existing_validation():
    """An empty mission_sequence (every scenario written before this field
    existed) must validate exactly as before -- this is the whole point of
    it being additive/opt-in.
    """
    _minimal_scenario().validate()  # must not raise


def test_mission_sequence_round_trips_through_save_load(tmp_path):
    """A mission sequence with nested commands, labels and parameters survives
    a save and load."""
    from spacemissionstudio.schema.command import Command

    scenario = _minimal_scenario(mission_sequence=[
        Command(kind="propagate", params={"stop_condition": "duration", "duration_days": 0.5}),
        Command(kind="if", label="Check periapsis", params={"condition": "alt_km < 500"}, children=[
            Command(kind="maneuver", label="Raise orbit",
                     params={"spacecraft": "sat-1", "delta_v_m_s": [0.0, 10.0, 0.0], "frame": "vnb"}),
        ]),
        Command(kind="report", params={"series": ["sat-1.position_N"]}),
    ])

    path = tmp_path / "scenario.json"
    scenario.save(path)
    loaded = load_scenario(path)

    assert loaded.mission_sequence == scenario.mission_sequence
    assert loaded.mission_sequence[1].label == "Check periapsis"
    assert loaded.mission_sequence[1].children[0].params["frame"] == "vnb"


def test_scenario_validate_raises_on_first_bad_command():
    """A maneuver command without a spacecraft makes the scenario fail
    validation."""
    from spacemissionstudio.schema.command import Command

    scenario = _minimal_scenario(mission_sequence=[Command(kind="maneuver", params={})])
    with pytest.raises(ScenarioValidationError, match="spacecraft"):
        scenario.validate()


def test_scenario_validate_raises_on_dangling_command_reference():
    """A maneuver on a spacecraft the scenario does not have is refused, naming
    it."""
    from spacemissionstudio.schema.command import Command

    scenario = _minimal_scenario(mission_sequence=[
        Command(kind="maneuver", params={"spacecraft": "no-such-spacecraft", "delta_v_m_s": [1.0, 0.0, 0.0]}),
    ])
    with pytest.raises(ScenarioValidationError, match="no-such-spacecraft"):
        scenario.validate()


def test_scenario_validate_accepts_valid_mission_sequence():
    """A propagate followed by a maneuver on an existing spacecraft
    validates."""
    from spacemissionstudio.schema.command import Command

    scenario = _minimal_scenario(mission_sequence=[
        Command(kind="propagate", params={"stop_condition": "duration", "duration_days": 1.0}),
        Command(kind="maneuver", params={"spacecraft": "sat-1", "delta_v_m_s": [1.0, 0.0, 0.0]}),
    ])
    scenario.validate()  # must not raise


def test_mission_sequence_preserves_command_order_through_round_trip(tmp_path):
    """mission_sequence is walked IN ORDER by the (not-yet-written)
    execution engine, so order is semantically load-bearing, not
    incidental -- explicitly locked in here, on top of the general
    round-trip test above.
    """
    from spacemissionstudio.schema.command import Command

    labels = ["first", "second", "third", "fourth"]
    scenario = _minimal_scenario(mission_sequence=[
        Command(kind="script_block", label=label, params={"code": f"# {label}"}) for label in labels
    ])

    path = tmp_path / "scenario.json"
    scenario.save(path)
    loaded = load_scenario(path)

    assert [c.label for c in loaded.mission_sequence] == labels


def test_mission_sequence_insert_and_reorder():
    """Reordering (insert-before/-after, drag-to-reorder in the eventual
    GUI) is just ordinary list manipulation on mission_sequence -- this
    locks in that Scenario doesn't do anything surprising (sorting,
    deduplication, etc.) that would fight that.
    """
    from spacemissionstudio.schema.command import Command

    a = Command(kind="script_block", label="a", params={"code": "pass"})
    b = Command(kind="script_block", label="b", params={"code": "pass"})
    c = Command(kind="script_block", label="c", params={"code": "pass"})
    scenario = _minimal_scenario(mission_sequence=[a, b])

    scenario.mission_sequence.insert(1, c)  # a, c, b
    assert [cmd.label for cmd in scenario.mission_sequence] == ["a", "c", "b"]

    scenario.mission_sequence.reverse()  # b, c, a
    assert [cmd.label for cmd in scenario.mission_sequence] == ["b", "c", "a"]
    scenario.validate()  # must not raise -- order never affects validity for this command set


@pytest.mark.parametrize("bad_vector", [[0.0, 0.0, 0.0], [float("nan"), 0.0, 1.0], [float("inf"), 0.0, 0.0],
                                        ["x", 0.0, 1.0]], ids=["zero", "nan", "inf", "non-numeric"])
@pytest.mark.parametrize("target", ["comms_boresight", "comms_sun_axis", "panel_normal"])
def test_direction_vectors_reject_zero_and_non_finite_values(target, bad_vector):
    """Regression test for an audit finding: a zero or NaN body-frame axis
    passed validation (only its LENGTH was checked) and only failed
    mid-run, once normalized into a NaN attitude target.
    """
    from pathlib import Path

    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"
    sc = load_scenario(templates / "19_sun_pointing_comms_link.json")
    craft = sc.spacecraft[0]
    if target == "comms_boresight":
        craft.comms_pointing.antenna_boresight_b = bad_vector
    elif target == "comms_sun_axis":
        craft.comms_pointing.sun_pointing_axis_b = bad_vector
    else:
        craft.power.panel_normal_b = bad_vector
    with pytest.raises(ScenarioValidationError, match="non-zero, finite"):
        sc.validate()


@pytest.mark.parametrize("min_on_time_s", [-1.0, float("nan"), 1.0e6])
def test_station_keeping_rejects_an_invalid_min_on_time(min_on_time_s):
    """A negative, NaN or implausibly long (1e6 s) thruster minimum on-time is
    refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].station_keeping = StationKeepingConfig(target_altitude_km=550.0, deadband_km=5.0, thrust_n=0.05,
                                                             isp_s=1500.0, propellant_kg=5.0,
                                                             min_on_time_s=min_on_time_s)
    with pytest.raises(ScenarioValidationError, match="min_on_time_s"):
        sc.spacecraft[0].station_keeping.validate("sat-1")


def test_station_keeping_thruster_realism_fields_default_to_an_ideal_thruster_when_absent_from_json():
    """A file without min_on_time_s and eccentricity_neutral_burns loads as an
    ideal thruster: no minimum on-time, single burns."""
    from spacemissionstudio.schema.scenario import Scenario

    sc = _minimal_scenario()
    sc.spacecraft[0].station_keeping = StationKeepingConfig(target_altitude_km=550.0, deadband_km=5.0, thrust_n=0.05,
                                                             isp_s=1500.0, propellant_kg=5.0)
    data = json.loads(json.dumps(sc.to_dict()))
    sk = data["spacecraft"][0]["station_keeping"]
    sk.pop("min_on_time_s")
    sk.pop("eccentricity_neutral_burns")
    loaded = Scenario.from_dict(data)
    assert loaded.spacecraft[0].station_keeping.min_on_time_s == 0.0  # [s]
    assert loaded.spacecraft[0].station_keeping.eccentricity_neutral_burns is False


def test_forecast_percentile_must_be_one_msfc_publishes():
    """MSFC publishes the 95th, 50th and 5th percentiles only."""
    from spacemissionstudio.schema.scenario import SpaceWeatherConfig

    _minimal_scenario(space_weather=SpaceWeatherConfig(forecast_percentile=95.0)).validate()
    with pytest.raises(ScenarioValidationError, match="forecast_percentile 90.0 must be one of"):
        _minimal_scenario(space_weather=SpaceWeatherConfig(forecast_percentile=90.0)).validate()


# -- Settings Basilisk's device factories exit() on (audit H2, M16) ------------


@pytest.mark.parametrize("params, message", [
    ({"gsHat_B": [1, 0, 0], "rw_type": "Bogus", "maxMomentum": 6.0}, "rw_type'\\] 'Bogus' must be one of"),
    ({"gsHat_B": [1, 0, 0], "u_max": -0.1, "Js": 0.03}, "u_max'] must be > 0"),
    ({"gsHat_B": [1, 0, 0], "u_max": 0.2, "Js": 0.0}, "Js'] must be > 0"),
    ({"gsHat_B": [1, 0, 0], "u_max": "0.2", "Js": 0.03}, "u_max'] must be a finite number"),
    ({"gsHat_B": [1, 0, 0], "u_max": 0.2, "Js": 0.03, "useMaxTorque": 1}, "useMaxTorque'] must be true or false"),
    ({"gsHat_B": [1, 0, 0], "u_max": 0.2, "Js": 0.03, "betaStatic": 0.0}, "betaStatic'] must not be 0"),
    ({"gsHat_B": [1, 0, 0], "u_max": 0.2, "Js": 0.03, "label": "wheel-one"}, "at most 5 characters"),
    ({"gsHat_B": [1, 0, 0], "u_max": 0.2, "Js": 0.03, "motor_thermal_initial_temp_c": -300.0,
      "motor_thermal_efficiency": 0.7, "motor_thermal_ambient_resistance_w_c": 5.0,
      "motor_thermal_heat_capacity_j_c": 50.0}, "above absolute zero"),
])
def test_reaction_wheel_settings_basilisk_would_exit_on_are_refused(params, message):
    """Reaction-wheel settings on which Basilisk's rwFactory would exit the
    process (an unknown type, non-positive or non-numeric u_max or Js, a
    non-boolean useMaxTorque, a zero betaStatic, a label over 5 characters, a
    motor below absolute zero) are refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="reaction_wheel", name="rw-1", params=params)]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    with pytest.raises(ScenarioValidationError, match=message):
        sc.validate()


@pytest.mark.parametrize("change, message", [
    ({"thruster_type": "Bogus"}, "thruster_type'\\] 'Bogus' must be one of"),
    ({"tHat_B": [0, 0, 0]}, "non-zero, finite thrust direction"),
    ({"MaxThrust": -1.0}, "MaxThrust'] must be > 0"),
    ({"steadyIsp": 0.0}, "steadyIsp'] must be > 0"),
    ({"r_B": [float("nan"), 0, 0]}, "r_B'] must be 3 finite numbers"),
    ({"MinOnTime": -0.1}, "MinOnTime'] must be >= 0"),
])
def test_thruster_settings_basilisk_would_exit_on_are_refused(change, message):
    """Thruster settings on which Basilisk's thrusterFactory would exit the
    process (an unknown type, a zero direction, non-positive thrust or Isp, a
    non-finite position, a negative minimum on-time) are refused."""
    sc = _minimal_scenario()
    params = {"r_B": [1, 0, 1.28], "tHat_B": [1, 0, 0], "MaxThrust": 1.0}
    params.update(change)
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="thruster", name="thr-1", params=params)]
    sc.spacecraft[0].fsw_mode = "sunSafePoint"
    with pytest.raises(ScenarioValidationError, match=message):
        sc.validate()


def test_a_torque_rod_needs_a_positive_dipole():
    """A torque rod with a negative maximum dipole is refused."""
    sc = _minimal_scenario()
    sc.spacecraft[0].actuators = [ActuatorConfig(kind="magnetic_torque_rod", name="mtb-1",
                                                 params={"gtHat_B": [1, 0, 0], "max_dipole_a_m2": -5.0})]
    with pytest.raises(ScenarioValidationError, match="max_dipole_a_m2'\\] > 0"):
        sc.validate()


def test_the_wheel_and_thruster_type_lists_match_basilisk():
    """The schema stays Basilisk-free, so it lists the factory types itself;
    they must be exactly the factories' own build methods."""
    pytest.importorskip("Basilisk")
    import inspect

    from Basilisk.utilities import simIncludeRW, simIncludeThruster

    from spacemissionstudio.schema.scenario import RW_TYPES, THRUSTER_TYPES

    def types(cls, argument):
        return {name for name, member in inspect.getmembers(cls, inspect.isfunction)
                if list(inspect.signature(member).parameters) == ["self", argument]}

    assert set(RW_TYPES) == types(simIncludeRW.rwFactory, "RW")
    assert set(THRUSTER_TYPES) == types(simIncludeThruster.thrusterFactory, "TH")


@pytest.mark.parametrize("name", ["../../escaped", "a.b", "a/b", "gs:1", "CON", "com1", " x", "x ", "a\tb", ""])
def test_names_that_cannot_be_file_names_are_refused(name):
    """Audit H3: a spacecraft name becomes an output file name, so one that
    climbs out of the output folder or is not a legal file name is refused."""
    scenario = _minimal_scenario()
    scenario.spacecraft[0].name = name
    with pytest.raises(ScenarioValidationError, match="spacecraft name"):
        scenario.validate()


@pytest.mark.parametrize("name", ["sat 1", "Satellit-Ü", "sat_1", "CONSAT"])
def test_ordinary_names_are_allowed(name):
    """Spaces inside a name, non-ASCII letters and names that merely start
    with a reserved device name stay valid."""
    scenario = _minimal_scenario()
    scenario.spacecraft[0].name = name
    scenario.validate()


@pytest.mark.parametrize("second", ["SAT-1", "sat 1", "sat_1"])
def test_spacecraft_names_whose_files_would_collide_are_refused(second):
    """Two spacecraft names that differ only in case or punctuation would
    overwrite each other's output files, so the second one is refused."""
    scenario = _minimal_scenario()
    other = copy.deepcopy(scenario.spacecraft[0])
    other.name = second
    scenario.spacecraft.append(other)
    with pytest.raises(ScenarioValidationError, match="differ only in case or punctuation"):
        scenario.validate()


def test_ground_station_names_differing_only_in_case_are_refused():
    """Two ground stations named alike but for case share one output file on
    Windows and macOS, so the scenario is refused."""
    stations = [GroundStationConfig(name="Kiruna", latitude_deg=67.86, longitude_deg=20.96),  # [deg]
                GroundStationConfig(name="KIRUNA", latitude_deg=67.86, longitude_deg=20.96)]  # [deg]
    with pytest.raises(ScenarioValidationError, match="differ only in case"):
        _minimal_scenario(ground_stations=stations).validate()


def test_a_ground_station_name_with_a_path_separator_is_refused():
    """A ground-station name is checked like a spacecraft name."""
    stations = [GroundStationConfig(name="../gs", latitude_deg=67.86, longitude_deg=20.96)]  # [deg]
    with pytest.raises(ScenarioValidationError, match="ground station name"):
        _minimal_scenario(ground_stations=stations).validate()


def test_a_mission_sequence_longer_than_one_run_is_refused():
    """Audit M3: fixed-duration propagates adding up past 100 days, or a stop
    epoch more than 100 days after the scenario epoch, are refused at load."""
    from spacemissionstudio.schema.command import Command

    too_long = [Command(kind="propagate", params={"duration_days": 60.0}),  # [day]
                Command(kind="if", params={"condition": "True"},
                        children=[Command(kind="propagate", params={"duration_days": 60.0})])]  # [day]
    with pytest.raises(ScenarioValidationError, match="add up to 120.0 days"):
        _minimal_scenario(mission_sequence=too_long).validate()
    far_epoch = [Command(kind="propagate", params={"stop_condition": "epoch",
                                                   "stop_epoch_utc": "2030-06-01T00:00:00"})]
    with pytest.raises(ScenarioValidationError, match="151.0 days after the scenario epoch"):
        _minimal_scenario(mission_sequence=far_epoch).validate()
    _minimal_scenario(mission_sequence=[Command(kind="propagate", params={"duration_days": 99.0})]).validate()  # [day]


def test_a_report_of_a_ground_station_access_series_validates():
    """Audit M6: "berlin-gs.access_to_sat-1.azimuth" (offered by the Report
    pick-list) was refused because its first segment was taken for a
    spacecraft. The station and the spacecraft it names are both checked."""
    from spacemissionstudio.schema.command import Command
    from spacemissionstudio.schema.validation import validate_all

    stations = [GroundStationConfig(name="berlin-gs", latitude_deg=52.52, longitude_deg=13.40)]  # [deg]
    report = Command(kind="report", params={"series": ["berlin-gs.access_to_sat-1.azimuth"]})
    sequence = [Command(kind="propagate", params={"duration_days": 0.1}), report]  # [day]
    scenario = _minimal_scenario(ground_stations=stations, mission_sequence=sequence)
    scenario.validate()
    assert validate_all(scenario) == []
    report.params["series"] = ["berlin-gs.access_to_sat-9.azimuth"]
    with pytest.raises(ScenarioValidationError, match="spacecraft 'sat-9' is not one of this scenario's spacecraft "):
        scenario.validate()
    report.params["series"] = ["paris-gs.access_to_sat-1.azimuth"]
    with pytest.raises(ScenarioValidationError, match="this scenario's ground stations"):
        scenario.validate()


def test_a_failed_save_leaves_the_previous_file_unchanged(tmp_path, monkeypatch):
    """Audit M9: save truncated the file before writing, so a failure part
    way through destroyed the previous good file. It now writes a temporary
    file and replaces the old one in one step, keeping its permissions."""
    import os
    import stat

    path = tmp_path / "scenario.json"
    _minimal_scenario(description="first").save(path)
    os.chmod(path, 0o640)
    before = path.read_text()

    def _fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", _fail)
    with pytest.raises(OSError, match="disk full"):
        _minimal_scenario(description="second").save(path)
    monkeypatch.undo()
    assert path.read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == ["scenario.json"]  # no temporary file left
    _minimal_scenario(description="second").save(path)
    assert load_scenario(path).description == "second"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.parametrize("orbit, match", [
    (OrbitIC(type="cartesian", position_km=[7000.0, float("nan"), 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
     "position_km must hold finite numbers"),
    (OrbitIC(type="cartesian", position_km=[0.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]),
     "must not be \\[0, 0, 0\\]"),
    (OrbitIC(type="classical_elements", semi_major_axis_km=float("inf"), eccentricity=0.0, inclination_deg=51.6,
             raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0), "semi_major_axis_km must be a finite"),
    (OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.0, inclination_deg=float("nan"),
             raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0), "inclination_deg must be a finite"),
    (OrbitIC(type="tle", tle_line1="1 25544U 98067A   08264.51782528", tle_line2="2 25544  51.6416"),
     "TLE line 1 has 32 characters"),
], ids=["nan-position", "zero-position", "inf-sma", "nan-inclination", "short-tle"])
def test_orbits_that_basilisk_cannot_fly_are_refused_at_load(orbit, match):
    """Audit M16: these passed validation and then misbehaved or failed in
    the run; they are refused when the scenario is checked."""
    scenario = _minimal_scenario()
    scenario.spacecraft[0].orbit = orbit
    with pytest.raises(ScenarioValidationError, match=match):
        scenario.validate()


def test_comms_pointing_with_actuators_is_refused_at_load():
    """Audit M16: comms pointing drives an idealised torque; with actuators
    the run failed with "Set fsw_mode", which comms pointing forbids."""
    scenario = _comms_pointing_scenario()
    scenario.spacecraft[0].actuators = [ActuatorConfig(kind="reaction_wheel", name="rw-1", params={
        "gsHat_B": [1, 0, 0], "rw_type": "Honeywell_HR16", "maxMomentum": 100.0})]  # [-], [N*m*s]
    with pytest.raises(ScenarioValidationError, match="comms_pointing commands an idealised control torque"):
        scenario.validate()


def test_a_thermal_sensor_without_the_sun_is_refused_at_load():
    """Audit M16: a thermal sensor needs the Sun's position; the build failed."""
    scenario = _minimal_scenario()
    scenario.spacecraft[0].sensors = [SensorConfig(kind="thermal", name="therm-1", params={
        "nHat_B": [0, 0, 1], "area_m2": 0.01, "absorptivity": 0.25, "emissivity": 0.34})]  # [-], [m^2]
    with pytest.raises(ScenarioValidationError, match="thermal sensor 'therm-1' needs the Sun's position"):
        scenario.validate()
    scenario.gravity.third_body_perturbers = ["sun"]
    scenario.validate()


def test_a_phasing_chief_without_classical_elements_is_refused_at_load():
    """Audit M16: phasing reads the chief's semi-major axis from its elements."""
    scenario = _chief_and_follower_scenario()
    scenario.spacecraft[0].orbit = OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0],
                                           velocity_km_s=[0.0, 7.546, 0.0])  # [km], [km/s]
    with pytest.raises(ScenarioValidationError, match="must have a 'classical_elements' orbit"):
        scenario.validate()


@pytest.mark.parametrize(("key", "value"), [("num_runs", 2.5), ("num_runs", "10"), ("thread_count", True)])
def test_monte_carlo_counts_must_be_whole_numbers(key, value):
    """Audit L29: a float, text or true/false run or thread count reached the
    batch unchecked."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(enabled=True, **{key: value})
    with pytest.raises(ScenarioValidationError, match=f"monte_carlo.{key} must be a whole number"):
        sc.validate()


@pytest.mark.parametrize(("bounds", "message"), [
    ([60.0, 40.0], "must have lo <= hi"),  # [kg]
    ([40.0, "60"], "must be two finite numbers"),
    ([40.0, float("nan")], "must be two finite numbers"),
])
def test_dispersion_bounds_must_be_ordered_finite_numbers(bounds, message):
    """Audit L29: reversed or non-numeric bounds reached Basilisk's sampler."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(enabled=True, dispersions=[DispersionConfig(
        spacecraft="sat-1", quantity="dry_mass_kg", kind="uniform", bounds=bounds)])
    with pytest.raises(ScenarioValidationError, match=message):
        sc.validate()


def test_dispersion_normal_needs_a_finite_mean_and_non_negative_spread():
    """Audit L29: a normal dispersion took any mean and a negative 1-sigma."""
    sc = _minimal_scenario()
    sc.monte_carlo = MonteCarloConfig(enabled=True, dispersions=[DispersionConfig(
        spacecraft="sat-1", quantity="dry_mass_kg", kind="normal", mean=50.0, std_deviation=-1.0)])  # [kg]
    with pytest.raises(ScenarioValidationError, match="std_deviation must be a finite number >= 0"):
        sc.validate()
    sc.monte_carlo.dispersions[0].std_deviation = 1.0  # [kg]
    sc.monte_carlo.dispersions[0].mean = float("inf")  # [kg]
    with pytest.raises(ScenarioValidationError, match="mean must be a finite number"):
        sc.validate()


def test_forecast_percentile_as_text_is_a_validation_error():
    """Audit L29: forecast_percentile given as text raised a bare ValueError
    instead of naming the field."""
    from spacemissionstudio.schema.scenario import SpaceWeatherConfig

    with pytest.raises(ScenarioValidationError, match="forecast_percentile"):
        SpaceWeatherConfig(forecast_percentile="high").validate()
