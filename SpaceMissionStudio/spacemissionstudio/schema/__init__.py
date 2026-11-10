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
from .command import (
    SUPPORTED_COMMAND_KINDS,
    PASS_EVENT_KINDS,
    SUPPORTED_EVENT_KINDS,
    SUPPORTED_MANEUVER_FRAMES,
    SUPPORTED_STOP_CONDITIONS,
    Command,
)
from .references import (
    Reference,
    ReferenceError,
    find_ground_station_references,
    find_spacecraft_references,
    rename_ground_station,
    rename_spacecraft,
)
from .scenario import (
    Scenario,
    ScenarioValidationError,
    GravityConfig,
    OrbitIC,
    SpacecraftConfig,
    SensorConfig,
    ActuatorConfig,
    PowerConfig,
    RFLinkConfig,
    CommsPointingConfig,
    StationKeepingConfig,
    PropellantBudgetConfig,
    PhasingKeepingConfig,
    ROE_CONTROL_LAWS,
    LandmarkNavigationConfig,
    OpticalNavigationConfig,
    RoeFormationConfig,
    RoeTargetConfig,
    ConstantThrustConfig,
    MomentumDumpingConfig,
    MagneticMomentumManagementConfig,
    FacetConfig,
    FuelTankConfig,
    GeoStationKeepingConfig,
    GroundStationConfig,
    SpaceWeatherConfig,
    SimSettings,
    DispersionConfig,
    MonteCarloConfig,
    CURRENT_SCHEMA_VERSION,
    SMALL_BODY_CENTRAL_BODIES,
    ALBEDO_MAPS,
    SUPPORTED_CENTRAL_BODIES,
    SUPPORTED_INTEGRATORS,
    SUPPORTED_SENSOR_KINDS,
    SUPPORTED_ACTUATOR_KINDS,
    SUPPORTED_FSW_MODES,
    SUPPORTED_THRUST_FRAMES,
    SUPPORTED_SIMULATION_MODES,
    DISPERSION_QUANTITIES,
    DISPERSION_KINDS_BY_QUANTITY,
    load_scenario,
)
from .validation import validate_all

__all__ = [
    "Scenario",
    "ScenarioValidationError",
    "GravityConfig",
    "OrbitIC",
    "SpacecraftConfig",
    "SensorConfig",
    "ActuatorConfig",
    "PowerConfig",
    "RFLinkConfig",
    "CommsPointingConfig",
    "StationKeepingConfig",
    "PropellantBudgetConfig",
    "PhasingKeepingConfig",
    "ROE_CONTROL_LAWS",
    "LandmarkNavigationConfig",
    "OpticalNavigationConfig",
    "RoeFormationConfig",
    "RoeTargetConfig",
    "ConstantThrustConfig",
    "MomentumDumpingConfig",
    "MagneticMomentumManagementConfig",
    "FacetConfig",
    "FuelTankConfig",
    "GeoStationKeepingConfig",
    "GroundStationConfig",
    "SpaceWeatherConfig",
    "SimSettings",
    "DispersionConfig",
    "MonteCarloConfig",
    "CURRENT_SCHEMA_VERSION",
    "SMALL_BODY_CENTRAL_BODIES",
    "ALBEDO_MAPS",
    "SUPPORTED_CENTRAL_BODIES",
    "SUPPORTED_INTEGRATORS",
    "SUPPORTED_SENSOR_KINDS",
    "SUPPORTED_ACTUATOR_KINDS",
    "SUPPORTED_FSW_MODES",
    "SUPPORTED_THRUST_FRAMES",
    "SUPPORTED_SIMULATION_MODES",
    "DISPERSION_QUANTITIES",
    "DISPERSION_KINDS_BY_QUANTITY",
    "load_scenario",
    # Mission sequence (schema.command)
    "Command",
    "SUPPORTED_COMMAND_KINDS",
    "SUPPORTED_STOP_CONDITIONS",
    "PASS_EVENT_KINDS",
    "SUPPORTED_EVENT_KINDS",
    "SUPPORTED_MANEUVER_FRAMES",
    # Reference integrity (schema.references)
    "Reference",
    "ReferenceError",
    "find_spacecraft_references",
    "find_ground_station_references",
    "rename_spacecraft",
    "rename_ground_station",
    # Collecting validation (schema.validation)
    "validate_all",
]
