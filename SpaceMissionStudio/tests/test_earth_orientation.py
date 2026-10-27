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

"""IERS-based Earth orientation files (ECSS-E-ST-10-09C 5.4.9f; remediation
R04): install, import, manifest, rollback, notes, and -- when the real NAIF
files are installed on this machine -- a run's Earth frame equal to SPICE's
ITRF93. No test touches the network (fetch is tested with a stub)."""

import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import earth_orientation as eo

pytestmark = pytest.mark.requirement("E-ST-10-09C 5.4.9f", "E-ST-10-04C 4.2.1c")

_REAL_DIR = Path(os.path.expanduser("~")) / ".cache" / "SpaceMissionStudio" / "earth_orientation"
_COMMENT = ("Coverage\n\n   ET Start time:             2000 JAN 01 00:01:04.183 TDB\n"
            "   UTC Epoch of last datum:   2026 OCT 07 00:00:00.000 UTC\n")


def _fake_pck(path: Path, payload: bytes = b"\0" * 64) -> Path:
    path.write_bytes(b"DAF/PCK " + payload)
    return path


def test_parse_last_datum_reads_the_naif_comment():
    """The last-datum line of a NAIF comment file is read as UTC."""
    assert eo.parse_last_datum(_COMMENT) == datetime(2026, 10, 7)
    assert eo.parse_last_datum("no such line") is None


def test_import_writes_a_manifest_with_hash_and_last_datum(tmp_path):
    """Imported files are installed with size, SHA-256, source and the last
    datum from the .cmt beside them, combined first in load order."""
    source = tmp_path / "media"
    source.mkdir()
    high = _fake_pck(source / "earth_latest_high_prec.bpc")
    (source / "earth_latest_high_prec.cmt").write_text(_COMMENT)
    combined = _fake_pck(source / "earth_1962_260806_2126_combined.bpc", b"\1" * 64)
    kernels = eo.import_files([high, combined], tmp_path / "eop")
    assert [k.role for k in kernels] == ["combined", "high_precision"]
    assert kernels[1].last_datum_utc == "2026-10-07T00:00:00"
    assert kernels[1].high_accuracy_until == datetime(2026, 12, 16)
    assert kernels[0].last_datum_utc is None
    manifest = json.loads((tmp_path / "eop" / "manifest.json").read_text())
    assert {Path(entry["source"]).name for entry in manifest} == {high.name, combined.name}
    import hashlib
    assert kernels[1].sha256 == hashlib.sha256(high.read_bytes()).hexdigest()


def test_a_file_that_is_not_a_binary_pck_is_refused(tmp_path):
    """A text file renamed to .bpc is rejected; nothing is installed."""
    bad = tmp_path / "earth_latest_high_prec.bpc"
    bad.write_text("not a kernel")
    with pytest.raises(eo.EarthOrientationError, match="not a binary PCK"):
        eo.import_files([bad], tmp_path / "eop")
    assert eo.installed(tmp_path / "eop") == []


def test_a_new_install_keeps_the_previous_files_for_rollback(tmp_path):
    """Installing again moves the old files aside; rollback restores them."""
    eop = tmp_path / "eop"
    first = _fake_pck(tmp_path / "earth_latest_high_prec.bpc", b"old" * 20)
    eo.import_files([first], eop)
    old_hash = eo.installed(eop)[0].sha256
    second_dir = tmp_path / "new"
    second_dir.mkdir()
    eo.import_files([_fake_pck(second_dir / "earth_latest_high_prec.bpc", b"new" * 20)], eop)
    assert eo.installed(eop)[0].sha256 != old_hash
    restored = eo.rollback(eop)
    assert [k.sha256 for k in restored] == [old_hash]
    with pytest.raises(eo.EarthOrientationError, match="no previous"):
        eo.rollback(eop)


def test_a_changed_file_is_not_used(tmp_path):
    """A file whose size no longer matches the manifest is left out."""
    eop = tmp_path / "eop"
    eo.import_files([_fake_pck(tmp_path / "earth_latest_high_prec.bpc")], eop)
    (eop / "earth_latest_high_prec.bpc").write_bytes(b"DAF/PCK truncated")
    assert eo.installed(eop) == []


def test_fetch_downloads_the_current_naif_files(tmp_path, monkeypatch):
    """fetch picks the newest combined file and the high-precision file from
    the NAIF listing and installs both with their comments (network stubbed)."""
    listing = ('<a href="earth_1962_250806_2125_combined.bpc"> <a href="earth_1962_260806_2126_combined.bpc"> '
               '<a href="earth_latest_high_prec.bpc">')
    served = {eo.NAIF_PCK_URL: listing.encode(),
              eo.NAIF_PCK_URL + "earth_1962_260806_2126_combined.bpc": b"DAF/PCK " + b"c" * 32,
              eo.NAIF_PCK_URL + "earth_1962_260806_2126_combined.cmt": _COMMENT.replace("OCT 07", "AUG 06").encode(),
              eo.NAIF_PCK_URL + "earth_latest_high_prec.bpc": b"DAF/PCK " + b"h" * 32,
              eo.NAIF_PCK_URL + "earth_latest_high_prec.cmt": _COMMENT.encode()}
    requested = []
    monkeypatch.setattr(eo, "_get", lambda url, timeout_s: requested.append(url) or served[url])
    kernels = eo.fetch(tmp_path / "eop")
    assert [Path(k.path).name for k in kernels] == ["earth_1962_260806_2126_combined.bpc", "earth_latest_high_prec.bpc"]
    assert kernels[0].last_datum_utc == "2026-08-06T00:00:00"
    assert all(url.startswith(eo.NAIF_PCK_URL) for url in requested)
    assert not list((tmp_path / "eop").glob("*.part"))


def test_user_files_take_precedence_over_the_install_wide_ones(tmp_path, monkeypatch):
    """installed() uses the user's directory when it has files, else the
    install-wide one the installers fill."""
    monkeypatch.setattr(eo, "DEFAULT_DIR", tmp_path / "user")
    monkeypatch.setattr(eo, "SYSTEM_DIR", tmp_path / "system")
    assert eo.installed() == []
    eo.import_files([_fake_pck(tmp_path / "earth_latest_high_prec.bpc")], tmp_path / "system")
    assert Path(eo.installed()[0].path).parent == tmp_path / "system"
    source = tmp_path / "u"
    source.mkdir()
    eo.import_files([_fake_pck(source / "earth_latest_high_prec.bpc", b"u" * 64)], tmp_path / "user")
    assert Path(eo.installed()[0].path).parent == tmp_path / "user"


def test_notes_name_the_fallback_and_the_predicted_span(tmp_path):
    """No files: the IAU model is named. A run past the high-accuracy span
    says from when it is predicted; a run inside it gets no note."""
    start, end = datetime(2026, 11, 1), datetime(2027, 1, 1)
    assert eo.notes(start, end, []) == ["Earth orientation: IAU rotation model, no IERS data installed"]
    kernel = eo.EOPKernel(role="high_precision", path="x", source="t", size_bytes=1, sha256="0", installed_utc="",
                          last_datum_utc="2026-10-07T00:00:00")
    assert eo.notes(start, end, [kernel]) == ["Earth orientation: ITRF93, predicted (low accuracy) for after 2026-12-16"]
    assert eo.notes(datetime(2030, 1, 1), datetime(2030, 2, 1), [kernel]) == [
        "Earth orientation: ITRF93, predicted (low accuracy) for the whole run"]
    assert eo.notes(start, datetime(2026, 12, 1), [kernel]) == []


@pytest.mark.requires_basilisk
@pytest.mark.skipif(not eo.installed(_REAL_DIR), reason="real NAIF Earth PCKs not installed on this machine")
def test_a_run_uses_spice_itrf93_as_the_earth_frame(monkeypatch):
    """With the real NAIF files installed, a run's Earth state message
    carries SPICE's J2000 -> ITRF93 rotation, which differs from IAU_EARTH,
    and the provenance lists the files."""
    from Basilisk.topLevelModules import pyswice
    from Basilisk.utilities.supportDataTools.dataFetcher import DataFile, get_path

    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.engine.time_system import utc_iso_to_spice_string
    from spacemissionstudio.schema import load_scenario

    monkeypatch.setattr(eo, "DEFAULT_DIR", _REAL_DIR)
    scenario = load_scenario(Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios"
                             / "templates" / "19_sun_pointing_comms_link.json")
    scenario.epoch_utc = "2026-06-01T00:00:00"
    scenario.sim_settings.duration_days = 0.01  # [day]
    service = SimulationService(scenario)
    result = service.run()
    assert service.earth_frame == "ITRF93"
    earth = service.spice_object.planetStateOutMsgs[0].read()
    assert {name for name in result.provenance.data_files if name.startswith("earth_orientation:")}

    for path in [get_path(DataFile.EphemerisData.naif0012), get_path(DataFile.EphemerisData.pck00010)] + \
            [k.path for k in eo.installed(_REAL_DIR)]:
        pyswice.furnsh_c(str(path))
    et = pyswice.new_doubleArray(1)
    pyswice.str2et_c(utc_iso_to_spice_string(scenario.epoch_utc), et)
    t_end = result.series["leo-comms-1.position_N"].time_s[-1]  # [s]

    def rotation(frame):
        out = pyswice.new_doubleArray(9)
        pyswice.pxform_c("J2000", frame, pyswice.doubleArray_getitem(et, 0) + t_end, out)
        return np.array([pyswice.doubleArray_getitem(out, i) for i in range(9)]).reshape(3, 3)

    np.testing.assert_allclose(np.array(earth.J20002Pfix), rotation("ITRF93"), atol=1e-12)
    difference = np.array(earth.J20002Pfix) @ rotation("IAU_EARTH").T
    assert np.degrees(np.arccos((np.trace(difference) - 1.0) / 2.0)) > 1e-3  # [deg] the frames really differ


def test_importing_a_missing_file_is_reported_and_leaves_nothing_behind(tmp_path):
    """Audit M12: `earth-orientation --import` with a missing file gave a
    traceback, and a failed import left .part copies. Both are fixed."""
    good = tmp_path / "source" / "earth_latest_high_prec.bpc"
    good.parent.mkdir()
    good.write_bytes(b"not used: the second file is missing")
    target = tmp_path / "installed"
    with pytest.raises(eo.EarthOrientationError, match="could not import"):
        eo.import_files([good, tmp_path / "source" / "missing.bpc"], directory=target)
    assert list(target.glob("*.part")) == []


def test_a_manifest_with_a_newer_key_still_loads(tmp_path):
    """Audit L19: a manifest entry with a key this version does not know
    (written by a newer version) raised TypeError on every build."""
    source = tmp_path / "media"
    source.mkdir()
    high = _fake_pck(source / "earth_latest_high_prec.bpc")
    eo.import_files([high], tmp_path / "eop")
    manifest_path = tmp_path / "eop" / "manifest.json"
    entries = json.loads(manifest_path.read_text())
    entries[0]["added_by_a_newer_version"] = True
    entries.append({"role": "combined"})  # a broken entry is skipped
    manifest_path.write_text(json.dumps(entries))
    assert [k.role for k in eo.installed(tmp_path / "eop")] == ["high_precision"]


def test_a_fetch_that_fails_part_way_leaves_no_part_files(tmp_path, monkeypatch):
    """Audit L19: the second download failing left the first one's .part."""
    listing = '<a href="earth_1962_260806_2126_combined.bpc"> <a href="earth_latest_high_prec.bpc">'
    served = {eo.NAIF_PCK_URL: listing.encode(),
              eo.NAIF_PCK_URL + "earth_1962_260806_2126_combined.bpc": b"DAF/PCK " + b"c" * 32,
              eo.NAIF_PCK_URL + "earth_1962_260806_2126_combined.cmt": _COMMENT.encode()}

    def get(url, timeout_s):
        if url not in served:
            raise eo.EarthOrientationError(f"could not download {url}")
        return served[url]

    monkeypatch.setattr(eo, "_get", get)
    with pytest.raises(eo.EarthOrientationError, match="could not download"):
        eo.fetch(tmp_path / "eop")
    assert not list((tmp_path / "eop").glob("*.part"))


def _daf_pck(path: Path, spans, truncate: bool = False) -> Path:
    """A minimal little-endian DAF/PCK whose segments cover ``spans``
    ((start, end) naive UTC): a file record, one summary record, a name
    record, then 10 doubles of data per segment (or one double short of
    the last segment's data when ``truncate``)."""
    import struct

    record = 1024  # [byte]
    head = bytearray(record)
    head[0:8] = b"DAF/PCK "
    head[8:16] = struct.pack("<ii", 2, 5)
    head[76:88] = struct.pack("<iii", 2, 2, 0)
    head[88:96] = b"LTL-IEEE"
    summaries = bytearray(record)
    summaries[0:24] = struct.pack("<3d", 0.0, 0.0, float(len(spans)))
    first = 3 * 128 + 1  # [double] data after the file, summary and name records
    for k, (start, end) in enumerate(spans):
        at = 24 + 40 * k
        summaries[at:at + 16] = struct.pack("<2d", (start - eo._J2000_UTC).total_seconds(),
                                            (end - eo._J2000_UTC).total_seconds())
        summaries[at + 16:at + 36] = struct.pack("<5i", 3000, 17, 2, first + 10 * k, first + 10 * k + 9)
    data = bytes(8 * (10 * len(spans) - (1 if truncate else 0)))
    path.write_bytes(bytes(head) + bytes(summaries) + bytes(record) + data)
    return path


def _kernel(path: Path) -> "eo.EOPKernel":
    return eo.EOPKernel(role="combined", path=str(path), source="test", size_bytes=path.stat().st_size, sha256="0",
                        installed_utc="", last_datum_utc=None)


def test_a_pcks_coverage_is_read_from_its_summary_records(tmp_path):
    """The span a binary PCK covers comes from its DAF summaries (to the
    second here); a header-only, truncated or text file has none."""
    path = _daf_pck(tmp_path / "a.bpc", [(datetime(2000, 1, 1), datetime(2005, 1, 1)),
                                         (datetime(2005, 1, 1), datetime(2010, 6, 1))])
    first, last = eo.pck_coverage(path)
    assert abs((first - datetime(2000, 1, 1)).total_seconds()) < 1.0 and abs((last - datetime(2010, 6, 1)).total_seconds()) < 1.0
    assert eo.pck_coverage(_fake_pck(tmp_path / "header_only.bpc")) is None
    assert eo.pck_coverage(_daf_pck(tmp_path / "cut.bpc", [(datetime(2000, 1, 1), datetime(2010, 1, 1))],
                                    truncate=True)) is None
    (tmp_path / "text.bpc").write_text("not a kernel")
    assert eo.pck_coverage(tmp_path / "text.bpc") is None
    assert eo.pck_coverage(tmp_path / "missing.bpc") is None


def test_kernels_are_used_only_when_they_cover_the_whole_run(tmp_path):
    """Audit of 2026-10-27 (R1): a run outside every loaded Earth PCK made
    SPICE stop the process. The kernels are used only when together they
    cover the run without a gap, and every one can be read."""
    early = _kernel(_daf_pck(tmp_path / "early.bpc", [(datetime(2000, 1, 1), datetime(2010, 1, 1))]))
    late = _kernel(_daf_pck(tmp_path / "late.bpc", [(datetime(2010, 1, 1), datetime(2040, 1, 1))]))
    apart = _kernel(_daf_pck(tmp_path / "apart.bpc", [(datetime(2015, 1, 1), datetime(2040, 1, 1))]))
    unreadable = _kernel(_fake_pck(tmp_path / "x.bpc"))
    assert eo.covering([early, late], datetime(2005, 1, 1), datetime(2030, 1, 1)) == [early, late]
    assert eo.covering([early], datetime(2005, 1, 1), datetime(2030, 1, 1)) == []  # ends inside the run
    assert eo.covering([early, apart], datetime(2005, 1, 1), datetime(2030, 1, 1)) == []  # a gap
    assert eo.covering([early, apart], datetime(2020, 1, 1), datetime(2030, 1, 1)) == [early, apart]
    assert eo.covering([early, late], datetime(1955, 1, 1), datetime(1955, 2, 1)) == []  # before them all
    assert eo.covering([early, unreadable], datetime(2005, 1, 1), datetime(2006, 1, 1)) == []
    assert eo.covered_until([early, late], datetime(2005, 1, 1)).year == 2040
    assert eo.coverage_text([early, late]) == "2000-01-01 to 2040-01-01"


@pytest.mark.requires_basilisk
def test_a_run_the_files_do_not_cover_uses_iau_earth_and_says_so(tmp_path, monkeypatch):
    """Template 02 at a 1955 epoch with Earth orientation files covering
    2000 to 2010: the run used to end inside SPICE; now it runs in
    IAU_EARTH, and both validate and the run say why."""
    from spacemissionstudio.engine import scenario_checks
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema import load_scenario

    kernel = _kernel(_daf_pck(tmp_path / "earth.bpc", [(datetime(2000, 1, 1), datetime(2010, 1, 1))]))
    monkeypatch.setattr(eo, "installed", lambda directory=None: [kernel])
    scenario = load_scenario(Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios"
                             / "templates" / "02_elliptical_orbit_with_perturbations.json")
    scenario.epoch_utc = "1955-01-01T00:00:00"
    scenario.sim_settings.duration_days = 0.01  # [day]
    assert any("cover 2000-01-01 to 2010-01-01, not this run" in w
               for w in scenario_checks.plausibility_warnings(scenario))
    service = SimulationService(scenario)
    result = service.run()
    assert service.earth_frame == eo.FALLBACK_EARTH_FRAME
    assert result.series["sat-1.position_N"].time_s[-1] > 0.0
    assert not {name for name in result.provenance.data_files if name.startswith("earth_orientation:")}
    assert any("the IERS files do not cover this run" in w for w in result.warnings)


@pytest.mark.requires_basilisk
def test_a_run_may_not_go_past_the_end_of_the_files():
    """A Mission Sequence can run past the span checked when the run was
    built: each stop time is checked, and one past the files' end is
    refused with a message instead of ending the process in SPICE."""
    from Basilisk.utilities import macros

    from spacemissionstudio.engine.service import SimulationService, SimulationServiceError
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios"
                             / "templates" / "02_elliptical_orbit_with_perturbations.json")
    service = SimulationService(scenario)
    service.check_stop_time(macros.sec2nano(10 * 86400.0))  # no files in use: nothing to check
    service._earth_orientation_span = (datetime(2026, 12, 1), datetime(2027, 1, 16))
    service.check_stop_time(macros.sec2nano(45 * 86400.0))  # [ns] 2027-01-15: inside
    with pytest.raises(SimulationServiceError, match="2027-01-16 00:00 UTC, where the installed Earth orientation"):
        service.check_stop_time(macros.sec2nano(47 * 86400.0))  # [ns] 2027-01-17
