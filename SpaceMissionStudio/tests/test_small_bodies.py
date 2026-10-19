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

"""engine.small_bodies: the Eros ephemeris kernel's download, import and
checks, the schema's small-body rules, and the CLI status. No test touches
the network (the download is tested with a stub)."""

import dataclasses
import hashlib
import io
from datetime import datetime
from pathlib import Path

import pytest

from spacemissionstudio.engine import small_bodies as sb
from spacemissionstudio.schema import ScenarioValidationError, load_scenario
from spacemissionstudio.schema.scenario import GroundStationConfig

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"
_KERNEL = b"DAF/SPK " + bytes(range(256)) * 4  # a stand-in kernel


@pytest.fixture
def fake_eros(monkeypatch):
    """Eros with the stand-in kernel's size and checksum."""
    body = dataclasses.replace(sb.EROS, spk_size_bytes=len(_KERNEL), spk_sha256=hashlib.sha256(_KERNEL).hexdigest())
    monkeypatch.setitem(sb.BODIES, "eros", body)
    return body


def test_eros_constants_name_their_sources():
    """GM and radius from the kernel's Horizons header, the IAU frame and
    NAIF id of pck00010, and the pinned NAIF file."""
    assert sb.EROS.gm_m3_s2 == pytest.approx(4.463e5)
    assert (sb.EROS.naif_id, sb.EROS.frame) == (2000433, "IAU_EROS")
    assert sb.EROS.spk_url.startswith("https://naif.jpl.nasa.gov/") and sb.EROS.spk_url.endswith(sb.EROS.spk_name)
    assert len(sb.EROS.spk_sha256) == 64 and sb.EROS.spk_size_bytes == 4589568
    assert sb.covers(sb.EROS, datetime(2026, 10, 19), datetime(2026, 11, 19))
    assert not sb.covers(sb.EROS, datetime(2099, 12, 1), datetime(2100, 2, 1))


def test_import_checks_and_installs_the_kernel(fake_eros, tmp_path):
    """A matching file is installed with a manifest; installed() finds it,
    and stops finding it once the file changed size."""
    source = tmp_path / "eros_1900_2100.bsp"
    source.write_bytes(_KERNEL)
    kernel = sb.import_file(source, "eros", tmp_path / "sb")
    assert Path(kernel.path).read_bytes() == _KERNEL and kernel.sha256 == fake_eros.spk_sha256
    assert sb.installed("eros", tmp_path / "sb") == kernel
    Path(kernel.path).write_bytes(_KERNEL + b"x")
    assert sb.installed("eros", tmp_path / "sb") is None


@pytest.mark.parametrize("content, reason", [(b"NOT/SPK " + bytes(1016), "DAF/SPK"),
                                             (_KERNEL + b"!", "bytes"),
                                             (_KERNEL[:-1] + b"!", "SHA-256")])
def test_a_file_that_is_not_nafs_kernel_is_refused(fake_eros, tmp_path, content, reason):
    """Wrong header, wrong size or wrong checksum: refused, nothing
    installed, no .part file left."""
    source = tmp_path / "other.bsp"
    source.write_bytes(content)
    with pytest.raises(sb.SmallBodyError, match=reason):
        sb.import_file(source, "eros", tmp_path / "sb")
    assert sb.installed("eros", tmp_path / "sb") is None
    assert not list((tmp_path / "sb").glob("*.part"))


def test_fetch_downloads_from_naif_and_checks_the_file(fake_eros, tmp_path, monkeypatch):
    """fetch() asks for the pinned NAIF URL and installs what it got; a
    failed download installs nothing."""
    asked = []

    def fake_urlopen(request, timeout):
        asked.append(request.full_url)
        return io.BytesIO(_KERNEL)

    monkeypatch.setattr(sb.urllib.request, "urlopen", fake_urlopen)
    kernel = sb.fetch("eros", tmp_path / "sb")
    assert asked == [sb.EROS.spk_url] and kernel.source == sb.EROS.spk_url
    monkeypatch.setattr(sb.urllib.request, "urlopen", lambda request, timeout: io.BytesIO(b"<html>"))
    with pytest.raises(sb.SmallBodyError, match="DAF/SPK"):
        sb.fetch("eros", tmp_path / "other")
    assert sb.installed("eros", tmp_path / "other") is None


def test_the_users_kernel_wins_over_the_install_wide_one(fake_eros, tmp_path, monkeypatch):
    """installed() looks in the user's folder first, then the install's."""
    source = tmp_path / "eros.bsp"
    source.write_bytes(_KERNEL)
    monkeypatch.setattr(sb, "DEFAULT_DIR", tmp_path / "user")
    monkeypatch.setattr(sb, "SYSTEM_DIR", tmp_path / "system")
    assert sb.installed("eros") is None
    sb.import_file(source, "eros", tmp_path / "system")
    assert Path(sb.installed("eros").path).parent == tmp_path / "system"
    sb.import_file(source, "eros", tmp_path / "user")
    assert Path(sb.installed("eros").path).parent == tmp_path / "user"


def _eros_scenario():
    scenario = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json")
    scenario.epoch_utc = "2026-10-19T00:00:00"
    scenario.gravity.central_body = "eros"
    scenario.gravity.polyhedral_gravity = True
    scenario.spacecraft[0].orbit.semi_major_axis_km = 35.0  # [km]
    return scenario


def test_eros_is_a_central_body_with_polyhedral_gravity():
    """A scenario around Eros with its shape's gravity validates."""
    _eros_scenario().validate()


def test_the_schema_refuses_what_a_run_around_eros_cannot_do():
    """Polyhedral gravity needs a small body; Eros cannot be a third body,
    have ground stations, harmonics or a run outside its kernel's span."""
    scenario = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json")
    scenario.gravity.polyhedral_gravity = True
    with pytest.raises(ScenarioValidationError, match="polyhedral_gravity needs a small body"):
        scenario.validate()
    scenario.gravity.polyhedral_gravity = False
    scenario.gravity.third_body_perturbers = ["eros"]
    with pytest.raises(ScenarioValidationError, match="'eros' can only be the central body"):
        scenario.validate()
    scenario = _eros_scenario()
    scenario.epoch_utc = "2099-12-31T12:00:00"  # one day: past the end of 2099
    with pytest.raises(ScenarioValidationError, match="ephemeris covers 1900-01-01 to 2100-01-01"):
        scenario.validate()
    scenario = _eros_scenario()
    scenario.gravity.central_body_degree = 4
    with pytest.raises(ScenarioValidationError, match="needs a central body with a gravity field"):
        scenario.validate()
    scenario = _eros_scenario()
    scenario.sim_settings.duration_days = 150.0  # [day]
    with pytest.raises(ScenarioValidationError, match="one simulation, at most 100 days"):
        scenario.validate()
    from spacemissionstudio.engine import long_run

    with pytest.raises(long_run.LongRunError, match="small body"):
        long_run.check_segmentable(scenario)
    scenario = _eros_scenario()
    scenario.ground_stations = [GroundStationConfig("site", 0.0, 0.0)]
    with pytest.raises(ScenarioValidationError, match="ground stations"):
        scenario.validate()


def test_the_cli_reports_missing_eros_files(capsys):
    """'small-bodies' without files installed says so and how to get them."""
    from spacemissionstudio import cli

    assert cli.main(["small-bodies"]) == 1
    out = capsys.readouterr().out
    assert "ephemeris  missing (eros_1900_2100.bsp)" in out and "small-bodies --fetch" in out
