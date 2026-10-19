"""Tests for spacemissionstudio.schema.migrations -- no Basilisk import,
runs anywhere. The v1->v2 migration exists because removing "celestrak"
as a valid SpaceWeatherConfig.source (see engine.spaceweather's own
"Closed-off/offline policy" docstring) would otherwise strand every
scenario file saved before that change: "celestrak" was the v1 DEFAULT,
so essentially all of them have it, and load_scenario() would start
raising ScenarioValidationError for files that used to load fine.
"""

import json

import pytest

from spacemissionstudio.schema import CURRENT_SCHEMA_VERSION, ScenarioValidationError, load_scenario
from spacemissionstudio.schema.migrations import migrate


def _v1_scenario(space_weather: dict | None = None) -> dict:
    data = {
        "schema_version": 1,
        "name": "v1 scenario",
        "epoch_utc": "2030-01-01T00:00:00",
        "spacecraft": [
            {
                "name": "sat-1",
                "orbit": {
                    "type": "classical_elements", "semi_major_axis_km": 7000.0, "eccentricity": 0.001,
                    "inclination_deg": 51.6, "raan_deg": 0.0, "arg_periapsis_deg": 0.0, "true_anomaly_deg": 0.0,
                },
            }
        ],
    }
    if space_weather is not None:
        data["space_weather"] = space_weather
    return data


def test_migrate_bumps_schema_version_to_current():
    """Migrating a schema 1 file brings it to the current schema version."""
    data = migrate(_v1_scenario())
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION


def test_migrate_rewrites_celestrak_source_to_bundled():
    """v1 "celestrak" became v2 "synthetic", which became v3 "bundled"
    (real CelesTrak data shipped with the app)."""
    data = migrate(_v1_scenario({"source": "celestrak"}))
    assert data["space_weather"]["source"] == "bundled"


def test_migrate_rewrites_a_v2_synthetic_source_to_bundled():
    """The synthetic profile was removed: real space weather only."""
    data = _v1_scenario({"source": "synthetic", "activity_level": "nominal"})
    data["schema_version"] = 2
    data = migrate(data)
    assert data["space_weather"]["source"] == "bundled" and data["schema_version"] == CURRENT_SCHEMA_VERSION


def test_migrate_downgrades_conservative_celestrak_to_nominal_bundled():
    """v1 -> v2 already made a conservative "celestrak" file nominal; it
    stays nominal (the 50th percentile default)."""
    data = migrate(_v1_scenario({"source": "celestrak", "activity_level": "conservative",
                                  "activity_percentile": 95.0}))
    assert data["space_weather"]["source"] == "bundled"
    assert "activity_level" not in data["space_weather"] and "activity_percentile" not in data["space_weather"]
    assert "forecast_percentile" not in data["space_weather"]


def test_migrate_leaves_local_file_source_untouched():
    """Migration keeps a local_file space-weather source and its path."""
    data = migrate(_v1_scenario({"source": "local_file", "local_file_path": "/some/file.csv"}))
    assert data["space_weather"]["source"] == "local_file"
    assert data["space_weather"]["local_file_path"] == "/some/file.csv"


def test_migrate_turns_conservative_into_msfcs_95th_percentile():
    """v3 -> v4: "conservative" (a constant percentile of the historical
    record) becomes ESA AD10's conservative case, MSFC's 95th percentile;
    the source is kept."""
    data = migrate(_v1_scenario({"source": "local_file", "local_file_path": "/some/file.csv",
                                  "activity_level": "conservative", "activity_percentile": 97.7}))
    assert data["space_weather"] == {"source": "local_file", "local_file_path": "/some/file.csv",
                                     "forecast_percentile": 95.0}


def test_migrate_drops_a_nominal_activity_level():
    """Migration drops the old activity level and percentile, keeping the
    forecast percentile."""
    data = _v1_scenario({"source": "bundled", "activity_level": "nominal", "activity_percentile": 95.0,
                         "forecast_percentile": 5.0})
    data["schema_version"] = 3
    assert migrate(data)["space_weather"] == {"source": "bundled", "forecast_percentile": 5.0}


def test_migrate_handles_a_file_with_no_space_weather_block_at_all():
    """space_weather is optional (defaults via dataclass field) -- a v1
    file that never set it explicitly must migrate cleanly, not crash on
    a missing key.
    """
    data = migrate(_v1_scenario())
    assert "space_weather" not in data or data["space_weather"] is None
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION


def test_load_scenario_migrates_an_old_celestrak_file_end_to_end(tmp_path):
    """The real regression this migration exists to prevent: a v1 file
    with the old default source must still load_scenario()+validate()
    successfully, not raise ScenarioValidationError.
    """
    path = tmp_path / "old.json"
    path.write_text(json.dumps(_v1_scenario({"source": "celestrak"})))

    scenario = load_scenario(path)

    assert scenario.space_weather.source == "bundled"
    assert scenario.schema_version == CURRENT_SCHEMA_VERSION


def test_load_scenario_migrates_an_old_conservative_celestrak_file_end_to_end(tmp_path):
    """An old file with a conservative celestrak source loads as bundled space
    weather at the 50th percentile."""
    path = tmp_path / "old_conservative.json"
    path.write_text(json.dumps(_v1_scenario({
        "source": "celestrak", "activity_level": "conservative", "activity_percentile": 95.0,
    })))

    scenario = load_scenario(path)

    assert scenario.space_weather.source == "bundled"
    assert scenario.space_weather.forecast_percentile == 50.0


def test_migrate_rejects_a_version_with_no_registered_step(monkeypatch):
    """A schema version without a migration step is refused."""
    import spacemissionstudio.schema.migrations as migrations_module

    monkeypatch.setattr(migrations_module, "MIGRATIONS", {})
    with pytest.raises(ScenarioValidationError, match="no migration registered"):
        migrate(_v1_scenario())


@pytest.mark.parametrize("version", [0, -3])
def test_a_version_below_one_is_named_as_a_bad_file(version):
    """Audit L29: schema_version 0 reported "a bug in SpaceMissionStudio";
    it is a file this tool never wrote, and the message says so."""
    data = _v1_scenario()
    data["schema_version"] = version
    with pytest.raises(ScenarioValidationError, match="scenario versions start at 1") as raised:
        migrate(data)
    assert "bug" not in str(raised.value)
