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
"""``spacemissionstudio generate-roe-formation``: it adds a follower at the
requested relative orbital elements (checked by mapping both orbits back
to mean elements and taking the ROE), with a passively safe formation from
``--safe``, and refuses what it cannot build with a message."""

import math
from pathlib import Path

import pytest

from spacemissionstudio import cli

pytestmark = pytest.mark.requires_basilisk

_TEMPLATE = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
             / "05_formation_flying_phasing.json")


def _chief_only(tmp_path, station_keeping=True):
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATE)
    scenario.spacecraft = scenario.spacecraft[:1]
    if not station_keeping:
        scenario.spacecraft[0].station_keeping = None
    path = tmp_path / "chief.json"
    scenario.save(path)
    return path


def _mean_roe_m(chief_orbit, follower_orbit):
    """The ROE [m] between two classical-element orbits, from their mean
    elements (Basilisk's clMeanOscMap, as the run measures them)."""
    from Basilisk.utilities import orbitalMotion

    from spacemissionstudio.engine.roe import MeanElements, roe_from_mean_elements

    means = []
    for orbit in (chief_orbit, follower_orbit):
        osc = orbitalMotion.ClassicElements()
        osc.a, osc.e = orbit.semi_major_axis_km * 1000.0, orbit.eccentricity
        osc.i, osc.Omega = math.radians(orbit.inclination_deg), math.radians(orbit.raan_deg)
        osc.omega = math.radians(orbit.arg_periapsis_deg)
        osc.f = (math.radians(orbit.true_anomaly_deg) if orbit.anomaly_type == "true" else orbitalMotion.E2f(
            orbitalMotion.M2E(math.radians(orbit.mean_anomaly_deg), orbit.eccentricity), orbit.eccentricity))
        mean = orbitalMotion.ClassicElements()
        orbitalMotion.clMeanOscMap(orbitalMotion.REQ_EARTH * 1000.0, orbitalMotion.J2_EARTH, osc, mean, -1)
        means.append(MeanElements(mean.a, mean.e, mean.i, mean.Omega, mean.omega,
                                  orbitalMotion.E2M(orbitalMotion.f2E(mean.f, mean.e), mean.e)))
    return roe_from_mean_elements(*means) * means[0].a


def test_a_safe_formation_is_generated_at_its_roe(tmp_path, capsys):
    """--safe 100,300,300 places the follower 100 m ahead on a 300 m helix
    (parallel e/i vectors at 90 deg): its mean ROE are those within a
    millimetre, it holds them with the impulsive law, and the message
    gives the 300 m passive-safety margin."""
    from spacemissionstudio.schema import load_scenario

    out = tmp_path / "helix.json"
    rc = cli.main(["generate-roe-formation", str(_chief_only(tmp_path)), "--out", str(out), "--chief", "chief-1",
                   "--follower-name", "follower-1", "--safe", "100,300,300"])
    assert rc == 0
    assert "closest radial/cross-track approach 300.0 m" in capsys.readouterr().out
    scenario = load_scenario(out)
    scenario.validate()
    chief, follower = scenario.spacecraft
    assert follower.roe_formation.chief_spacecraft == "chief-1"
    assert follower.roe_formation.control_law == "impulsive"
    assert follower.roe_formation.targets[0].roe_m == [0.0, 100.0, 0.0, 300.0, 0.0, 300.0]
    assert _mean_roe_m(chief.orbit, follower.orbit) == pytest.approx([0.0, 100.0, 0.0, 300.0, 0.0, 300.0],
                                                                    abs=1e-3)


def test_explicit_roe_and_the_continuous_law(tmp_path):
    """--roe takes the six ROE in metres; --control-law continuous picks
    Basilisk's meanOEFeedback."""
    from spacemissionstudio.schema import load_scenario

    out = tmp_path / "f.json"
    rc = cli.main(["generate-roe-formation", str(_chief_only(tmp_path)), "--out", str(out), "--chief", "chief-1",
                   "--follower-name", "f", "--roe", "0,-2000,50,0,0,80", "--control-law", "continuous"])
    assert rc == 0
    chief, follower = load_scenario(out).spacecraft
    assert follower.roe_formation.control_law == "continuous"
    assert _mean_roe_m(chief.orbit, follower.orbit) == pytest.approx([0.0, -2000.0, 50.0, 0.0, 0.0, 80.0],
                                                                    abs=1e-3)


@pytest.mark.parametrize("extra, message", [
    (["--roe", "1,2,3"], "--roe takes 6 numbers"),
    (["--safe", "1,two,3"], "comma-separated numbers"),
    (["--safe", "0,300,300", "--follower-name", "chief-1"], "already exists"),
])
def test_bad_requests_are_refused(tmp_path, capsys, extra, message):
    """A wrong number of ROE, text where a number belongs, or a name in use
    is refused with a message, and nothing is written."""
    args = ["generate-roe-formation", str(_chief_only(tmp_path)), "--out", str(tmp_path / "x.json"),
            "--chief", "chief-1", "--follower-name", "f"]
    assert cli.main(args + extra) == 1
    assert message in capsys.readouterr().err
    assert not (tmp_path / "x.json").exists()


def test_a_template_without_station_keeping_is_refused(tmp_path, capsys):
    """The formation fires the station-keeping thruster: a template without
    it is refused, naming it."""
    rc = cli.main(["generate-roe-formation", str(_chief_only(tmp_path, station_keeping=False)), "--out",
                   str(tmp_path / "x.json"), "--chief", "chief-1", "--follower-name", "f", "--safe", "0,300,300"])
    assert rc == 1
    assert "chief-1 has no station keeping" in capsys.readouterr().err
