#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
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

"""``spacemissionstudio.ccsds_files``: the CCSDS orbit message files the
command line and the GUI share (reading an OPM or OMM as an orbit, its
import record, each spacecraft's starting state, a run's OEMs)."""

import hashlib
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest

from spacemissionstudio import ccsds_files
from spacemissionstudio.engine import ccsds_odm
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.schema.scenario import (ImportRecord, OrbitIC, Scenario, SpacecraftConfig,
                                                imported_values, put_import)

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
EPOCH = datetime(2030, 1, 1, 0, 0, 0)  # [UTC]


def opm_text(center: str = "EARTH", epoch: datetime = EPOCH) -> str:
    return ccsds_odm.write_opm(object_name="sat-1", object_id="2030-001A", center_name=center, ref_frame="EME2000",
                               time_system="UTC", epoch=epoch, r_km=[7000.0, 0.0, 0.0],  # [km]
                               v_km_s=[0.0, 7.546, 1.0])  # [km/s]


def test_an_opm_is_read_as_a_cartesian_state_at_its_epoch(tmp_path):
    """An OPM gives a Cartesian state in km and km/s, its epoch, and the
    format ``ccsds_opm``."""
    path = tmp_path / "sat.opm"
    path.write_text(opm_text(), encoding="ascii")
    orbit, epoch, notes, file_format = ccsds_files.orbit_from_file(path, "earth")
    assert orbit.type == "cartesian" and file_format == "ccsds_opm" and epoch == EPOCH
    assert orbit.position_km == pytest.approx([7000.0, 0.0, 0.0])  # [km]
    assert orbit.velocity_km_s == pytest.approx([0.0, 7.546, 1.0])  # [km/s]
    assert notes == []


def test_an_omm_is_read_as_its_tle(tmp_path):
    """A TLE-based OMM gives the TLE back, with no epoch (SGP4 takes it to
    the scenario's), and the format ``ccsds_omm``."""
    path = tmp_path / "iss.omm"
    path.write_text(ccsds_odm.omm_from_tle(LINE1, LINE2, "ISS"), encoding="ascii")
    orbit, epoch, _notes, file_format = ccsds_files.orbit_from_file(path, "earth")
    assert (orbit.type, orbit.tle_line1, orbit.tle_line2, epoch, file_format) == ("tle", LINE1, LINE2, None,
                                                                                   "ccsds_omm")


def test_a_message_for_another_body_or_too_large_is_refused(tmp_path):
    """An Earth-centred OPM is refused for a Mars scenario; a file larger
    than the limit is not read."""
    path = tmp_path / "sat.opm"
    path.write_text(opm_text(), encoding="ascii")
    with pytest.raises(ccsds_odm.OdmError, match="central body is mars"):
        ccsds_files.orbit_from_file(path, "mars")
    with pytest.raises(OSError, match="not a CCSDS message"):
        ccsds_files.read_message(path, max_bytes=100)


def test_the_import_record_keeps_the_file_and_the_values_read(tmp_path):
    """The record names the spacecraft and the orbit target, the file's
    absolute path and SHA-256, and the values read; a scenario holding it
    validates."""
    path = tmp_path / "sat.opm"
    path.write_text(opm_text(), encoding="ascii")
    orbit, _epoch, _notes, file_format = ccsds_files.orbit_from_file(path, "earth")
    record = ccsds_files.orbit_import_record("sat-1", orbit, path, file_format, author="tester")
    assert isinstance(record, ImportRecord)
    assert (record.spacecraft, record.target, record.format, record.author) == ("sat-1", "orbit", "ccsds_opm",
                                                                                "tester")
    assert record.source == str(path.resolve())
    assert record.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record.values == imported_values(SimpleNamespace(orbit=orbit), "orbit") and record.values
    scenario = Scenario(name="s", epoch_utc="2030-01-01T00:00:00", spacecraft=[SpacecraftConfig(name="sat-1",
                                                                                                 orbit=orbit)])
    put_import(scenario, record)
    scenario.validate()


def test_a_tle_spacecraft_starts_as_an_omm_that_conforms():
    """A TLE spacecraft's starting state is its OMM (no Basilisk needed),
    and it conforms to CCSDS 502.0-B-3."""
    scenario = Scenario(name="s", epoch_utc="2019-12-10T00:00:00", spacecraft=[SpacecraftConfig(
        name="iss", orbit=OrbitIC(type="tle", tle_line1=LINE1, tle_line2=LINE2))])
    [(name, text)] = ccsds_files.initial_state_messages(scenario)
    assert name == "iss.omm"
    assert [issue for issue in ccsds_odm.validate(text) if issue.level == "error"] == []


def test_a_runs_oems_skip_a_spacecraft_with_no_state_and_follow_the_stride():
    """One OEM per spacecraft that recorded states: every stride-th state
    and the last, with the interpolation asked for."""
    t_s = np.arange(50) * 60.0  # [s]
    r_m = np.column_stack([7e6 * np.cos(t_s / 900.0), 7e6 * np.sin(t_s / 900.0), np.zeros(50)])  # [m]
    v_m_s = np.gradient(r_m, t_s, axis=0)  # [m/s]
    result = ResultSet(scenario_name="s")
    result.add(TimeSeries("sat-1.position_N", t_s, ("x", "y", "z"), r_m, units="m"))
    result.add(TimeSeries("sat-1.velocity_N", t_s, ("x", "y", "z"), v_m_s, units="m/s"))
    result.add(TimeSeries("sat-2.position_N", np.zeros(0), ("x", "y", "z"), np.zeros((0, 3)), units="m"))
    orbit = OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0])  # [km], [km/s]
    scenario = Scenario(name="s", epoch_utc="2030-01-01T00:00:00", spacecraft=[
        SpacecraftConfig(name="sat-1", orbit=orbit), SpacecraftConfig(name="sat-2", orbit=orbit)])
    messages = ccsds_files.oem_messages(result, scenario, stride=6, interpolation="lagrange")
    assert list(messages) == ["sat-1"]
    message = ccsds_odm.read(messages["sat-1"])
    assert len(message.segments[0].states) == 10  # 0, 6, ..., 48 and the last, 49
    assert "INTERPOLATION        = LAGRANGE" in messages["sat-1"]
    assert [issue for issue in ccsds_odm.validate(messages["sat-1"]) if issue.level == "error"] == []
