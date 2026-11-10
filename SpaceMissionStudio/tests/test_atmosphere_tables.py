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
"""The tabular atmosphere (transparency plan, Phase 6b): Basilisk's
published profiles (engine.atmosphere_tables), the scenario's choice of
one, a run and a lifetime that read it."""

import json
import math

import numpy as np
import pytest

from spacemissionstudio.engine import atmosphere_tables
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import (ATMOSPHERE_TABLES, GravityConfig, OrbitIC, Scenario,
                                                ScenarioValidationError, SimSettings, SpacecraftConfig,
                                                SpaceWeatherConfig)

_EQUATORIAL_RADIUS_KM = 6378.1366  # [km] the one set (spacemissionstudio.constants)


def _scenario(table="nrlmsise00_nominal", altitude_km=300.0, model="tabular"):
    """An equatorial circular orbit at ``altitude_km`` with drag, a minute long."""
    return Scenario(
        name="tabular", epoch_utc="2030-01-01T00:00:00",
        gravity=GravityConfig(central_body="earth", central_body_degree=0),
        sim_settings=SimSettings(duration_days=60.0 / 86400.0, dynamics_task_rate_s=10.0),  # [day], [s]
        space_weather=SpaceWeatherConfig(atmosphere_model=model, atmosphere_table=table),
        spacecraft=[SpacecraftConfig(name="sat-1", dry_mass_kg=100.0, enable_drag=True,
                                     orbit=OrbitIC(type="classical_elements",
                                                   semi_major_axis_km=_EQUATORIAL_RADIUS_KM + altitude_km,
                                                   eccentricity=0.0, inclination_deg=0.0, raan_deg=0.0,
                                                   arg_periapsis_deg=0.0, true_anomaly_deg=0.0))])


def test_the_scenario_names_its_table_only_when_it_uses_one(tmp_path):
    """A tabular scenario saves its table and reads it back; any other
    writes none, so it saves and hashes as before; an unknown table or
    model is refused, naming the ones there are."""
    tabular = _scenario("earthgram_2016_nominal")
    tabular.save(tmp_path / "t.json")
    assert json.loads((tmp_path / "t.json").read_text())["space_weather"]["atmosphere_table"] == \
        "earthgram_2016_nominal"
    assert load_scenario(tmp_path / "t.json").space_weather.atmosphere_table == "earthgram_2016_nominal"
    msis = _scenario(model="nrlmsise00")
    assert "atmosphere_table" not in msis.to_dict()["space_weather"]
    with pytest.raises(ScenarioValidationError, match="atmosphere_table 'jb2008' must be one of 'us_standard_1976'"):
        SpaceWeatherConfig(atmosphere_model="tabular", atmosphere_table="jb2008").validate()
    assert set(atmosphere_tables.TABLES) == set(ATMOSPHERE_TABLES)


@pytest.mark.requires_basilisk
def test_the_tables_are_basilisks_and_as_recorded():
    """Each table reads with Basilisk's own reader, ascending, between the
    altitudes recorded for it, its density falling with height; the US
    Standard Atmosphere's sea level is the standard's own 1.225 kg/m^3 and
    288.15 K."""
    from spacemissionstudio.engine import kernels

    for name, table in atmosphere_tables.TABLES.items():
        altitudes, densities, temperatures = atmosphere_tables.load(
            name, kernels.cached_path(atmosphere_tables.data_file(name)))
        assert altitudes[0] == pytest.approx(table.bottom_km * 1e3) and altitudes[-1] == pytest.approx(
            table.top_km * 1e3), name
        assert all(a < b for a, b in zip(altitudes, altitudes[1:])), name
        assert densities[-1] < densities[0] / 1e5, name
        assert len(densities) == len(temperatures) == len(altitudes)
    altitudes, densities, temperatures = atmosphere_tables.load(
        "us_standard_1976", kernels.cached_path(atmosphere_tables.data_file("us_standard_1976")))
    sea_level = altitudes.index(0)
    assert (densities[sea_level], temperatures[sea_level]) == (pytest.approx(1.225), pytest.approx(288.15))


def _run(scenario):
    from spacemissionstudio.engine.service import SimulationService

    scenario.validate()
    service = SimulationService(scenario)
    service.build()
    result = service.run()
    return service, result


@pytest.mark.requires_basilisk
def test_a_tabular_run_reads_the_table_at_the_spacecrafts_altitude():
    """At 300 km over the equator, the density drag reads is the
    NRLMSISE-00 profile's at that altitude, interpolated linearly, and the
    run's provenance records the table's file."""
    from spacemissionstudio.engine import kernels

    service, result = _run(_scenario("nrlmsise00_nominal", 300.0))
    altitudes, densities, _temperatures = atmosphere_tables.load(
        "nrlmsise00_nominal", kernels.cached_path(atmosphere_tables.data_file("nrlmsise00_nominal")))
    r_m = np.array(service.spacecraft_handles["sat-1"].sc_object.scStateOutMsg.read().r_BN_N)  # [m]
    geodetic_altitude_m = float(np.linalg.norm(r_m)) - 6378137.0  # [m] over the equator: WGS-84's radius
    read = service.atmosphere_module.envOutMsgs[0].read().neutralDensity  # [kg/m^3]
    assert read == pytest.approx(float(np.interp(geodetic_altitude_m, altitudes, densities)), rel=1e-3)
    assert 1e-12 < read < 1e-10  # [kg/m^3] about 300 km
    record = result.provenance.to_dict()["data_files"]["atmosphere_table"]
    assert record["path"].endswith("NRLMSISE00Nominal.txt") and len(record["sha256"]) == 64
    assert not any(getattr(w, "rule_id", "") == "run.above_atmosphere_table" for w in result.warnings)


@pytest.mark.requires_basilisk
def test_above_the_table_there_is_no_drag_and_the_run_says_so():
    """The US Standard Atmosphere stops at 86 km: at 400 km the density is
    0 and the run warns, naming the rule, the perigee and the top."""
    service, result = _run(_scenario("us_standard_1976", 400.0))
    assert service.atmosphere_module.envOutMsgs[0].read().neutralDensity == 0.0
    warning = next(w for w in result.warnings if getattr(w, "rule_id", "") == "run.above_atmosphere_table")
    assert (warning.actual, warning.limit) == ("400 km", "86 km")
    assert "above the top of the U.S. Standard Atmosphere, 1976 table (86 km)" in str(warning)


@pytest.mark.requires_basilisk
def test_a_lifetime_uses_the_same_table_and_says_what_it_leaves_out():
    """The lifetime's density is the run's table at the geodetic altitude,
    0 above it, with a warning naming its rule; the lifetime record names
    the table."""
    from datetime import datetime

    from spacemissionstudio.engine import lifetime

    scenario = _scenario("earthgram_2016_nominal", 150.0)
    density, _years, warnings = lifetime.density_for_scenario(scenario, datetime(2030, 1, 1), 1.0)
    assert isinstance(density, lifetime.TabularDensity)
    assert [w.rule_id for w in warnings] == ["lifetime.tabular_atmosphere"]
    r_150 = np.array([[(_EQUATORIAL_RADIUS_KM + 150.0) * 1e3, 0.0, 0.0]])  # [m]
    expected = np.interp(150.0e3 - 0.4, density.altitudes_m, density.densities)  # [kg/m^3] WGS-84 0.4 m above
    assert density(0.0, r_150)[0] == pytest.approx(expected, rel=1e-4)
    assert density(0.0, np.array([[(_EQUATORIAL_RADIUS_KM + 250.0) * 1e3, 0.0, 0.0]]))[0] == 0.0
    assert math.isclose(density.table.top_km, 200.0)
    assert "atmosphere_table" in density.data_files
