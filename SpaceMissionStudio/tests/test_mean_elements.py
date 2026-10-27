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
"""J2 mean elements at the critical inclination (engine.mean_elements):
finite, and close to the elements averaged over one orbit of the J2
motion, a reference with no singular terms."""

import math
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import lifetime
from spacemissionstudio.engine import mean_elements as me

pytestmark = pytest.mark.requires_basilisk

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"
_MU, _RE, _J2 = lifetime.MU_EARTH_M3_S2, lifetime.REQ_EARTH_M, lifetime.J2_EARTH
_CRITICAL_DEG = math.degrees(me.CRITICAL_INCLINATION_RAD)  # [deg] 63.435
# Inclinations across both critical bands [deg], the critical values among them
_IN_BAND_DEG = [_CRITICAL_DEG + d for d in (-0.99, -0.5, -0.1, -0.01, 0.0, 0.01, 0.1, 0.5, 0.99)]
_IN_BAND_DEG += [180.0 - i for i in _IN_BAND_DEG]


def _state(a_m, eccentricity, inclination_deg):
    from Basilisk.utilities import orbitalMotion

    elements = orbitalMotion.ClassicElements()
    elements.a, elements.e, elements.i = a_m, eccentricity, math.radians(inclination_deg)
    elements.Omega, elements.omega, elements.f = 0.3, 4.0, 0.0  # [rad]
    r, v = orbitalMotion.elem2rv(_MU, elements)
    return np.array(r), np.array(v)


def _j2_acceleration(r):
    x, y, z = r
    norm = np.linalg.norm(r)
    k = 1.5 * _J2 * _MU * _RE ** 2 / norm ** 5
    f = 5.0 * z * z / norm ** 2
    return -_MU * r / norm ** 3 + k * np.array([x * (f - 1.0), y * (f - 1.0), z * (f - 3.0)])


def _orbit_averaged_perigee_km(r, v, steps=720):
    """Perigee altitude [km] from the semi-major axis and eccentricity
    vector averaged over one period of the J2 motion (RK4)."""
    from Basilisk.utilities import orbitalMotion

    period = 2.0 * math.pi * math.sqrt(orbitalMotion.rv2elem(_MU, r, v).a ** 3 / _MU)  # [s]
    h = period / steps  # [s]
    sma, ecc_vectors = [], []
    for _ in range(steps):
        sma.append(orbitalMotion.rv2elem(_MU, r, v).a)
        ecc_vectors.append(np.cross(v, np.cross(r, v)) / _MU - r / np.linalg.norm(r))
        k1r, k1v = v, _j2_acceleration(r)
        k2r, k2v = v + h / 2 * k1v, _j2_acceleration(r + h / 2 * k1r)
        k3r, k3v = v + h / 2 * k2v, _j2_acceleration(r + h / 2 * k2r)
        k4r, k4v = v + h * k3v, _j2_acceleration(r + h * k3r)
        r = r + h / 6 * (k1r + 2 * k2r + 2 * k3r + k4r)
        v = v + h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
    return (np.mean(sma) * (1.0 - np.linalg.norm(np.mean(ecc_vectors, axis=0))) - _RE) / 1e3


@pytest.mark.parametrize("name, a_km, eccentricity, tolerance_km", [
    ("600 km LEO", 6978.137, 0.01, 0.5),
    ("Molniya", 26600.0, 0.74, 1.0),
])
def test_mean_perigee_stays_right_across_the_critical_inclination(name, a_km, eccentricity, tolerance_km):
    """Across both critical bands, the mean perigee is within 0.5 km (LEO)
    or 1 km (Molniya) of the orbit-averaged one. The plain first-order map
    gave -1159 km for the LEO orbit at 63.435 deg and failed for the
    Molniya orbit (eccentricity 1.92)."""
    for inclination in _IN_BAND_DEG:
        r, v = _state(a_km * 1e3, eccentricity, inclination)
        orbit = lifetime.mean_orbit_from_state(r, v)
        perigee_km = (orbit.semi_major_axis_m * (1.0 - orbit.eccentricity) - _RE) / 1e3
        assert perigee_km == pytest.approx(_orbit_averaged_perigee_km(r, v), abs=tolerance_km), (name, inclination)
        assert math.degrees(orbit.inclination_rad) == pytest.approx(inclination, abs=0.05)


def test_outside_the_band_the_map_is_basilisks_own():
    """Away from the critical and equatorial bands nothing changes: the
    same elements as clMeanOscMap, both ways."""
    from Basilisk.utilities import orbitalMotion

    for inclination in (1.5, 28.5, 51.6, 62.0, 65.0, 97.4, 115.0, 170.0):
        for sign in (-1, 1):
            source = orbitalMotion.ClassicElements()
            source.a, source.e, source.i = 6978.137e3, 0.01, math.radians(inclination)
            source.Omega, source.omega, source.f = 0.3, 4.0, 1.0
            plain, guarded = orbitalMotion.ClassicElements(), orbitalMotion.ClassicElements()
            orbitalMotion.clMeanOscMap(_RE, _J2, source, plain, sign)
            me.cl_mean_osc_map(_RE, _J2, source, guarded, sign)
            assert [guarded.a, guarded.e, guarded.i, guarded.Omega, guarded.omega, guarded.f] == \
                [plain.a, plain.e, plain.i, plain.Omega, plain.omega, plain.f]
            assert source.i == math.radians(inclination)  # left as it was


def test_the_density_ring_is_finite_at_the_critical_inclination():
    """The lifetime's ring of states (mean -> osculating) at 63.435 deg:
    every point finite and within 10 km of the radius at 63.0 deg."""
    for inclination in (_CRITICAL_DEG, 180.0 - _CRITICAL_DEG):
        orbit = lifetime.MeanOrbit(6978.137e3, 0.01, math.radians(inclination), 0.3, 4.0)
        near = lifetime.MeanOrbit(6978.137e3, 0.01, math.radians(inclination - 0.4), 0.3, 4.0)
        r, v = lifetime.ring_states(orbit)
        r_near, _ = lifetime.ring_states(near)
        assert np.all(np.isfinite(r)) and np.all(np.isfinite(v))
        assert np.max(np.abs(np.linalg.norm(r, axis=1) - np.linalg.norm(r_near, axis=1))) < 10e3  # [m]


def test_a_lifetime_at_the_critical_inclination_matches_a_basilisk_decay_run():
    """Template 18's spacecraft from 300 km at 63.435 deg: the estimate's
    re-entry within 3% of where a full Basilisk run stops (below 100 km),
    as at the template's own inclination. Before, the estimate re-entered
    at once ("0.00 years")."""
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(_TEMPLATES / "18_leo_station_keeping.json")
    spacecraft = scenario.spacecraft[0]
    spacecraft.orbit.semi_major_axis_km = _RE / 1e3 + 300.0  # [km]
    spacecraft.orbit.inclination_deg = 63.435  # [deg]
    spacecraft.station_keeping = None
    spacecraft.drag_coeff = 2.2  # [-]
    scenario.sim_settings.duration_days = 40.0  # [day]
    scenario.sim_settings.record_interval_s = 300.0  # [s]

    estimate = lifetime.spacecraft_lifetime(scenario, spacecraft.name)
    result = SimulationService(scenario).run()
    stopped_days = result.series[f"{spacecraft.name}.position_N"].time_s[-1] / 86400.0  # [day]
    assert any(w.startswith(f"{spacecraft.name} re-entered: below 100 km") for w in result.warnings)
    assert estimate.reentered
    assert estimate.lifetime_s / 86400.0 == pytest.approx(stopped_days, rel=0.03)


def test_the_map_is_continuous_across_the_critical_inclination():
    """Two orbits a hundredth of a degree either side of 63.435 deg get
    nearly the same mean semi-major axis. With the band's nearer edge
    alone, the map jumped there by about 200 m, enough to drift a phasing
    follower 30 km a day."""
    from Basilisk.utilities import orbitalMotion

    means = []
    for inclination in (_CRITICAL_DEG - 0.005, _CRITICAL_DEG + 0.005):
        source = orbitalMotion.ClassicElements()
        source.a, source.e, source.i = 6928.137e3, 0.001, math.radians(inclination)
        source.Omega, source.omega, source.f = 0.3, 4.0, 1.0
        mean = orbitalMotion.ClassicElements()
        me.cl_mean_osc_map(_RE, _J2, source, mean, -1)
        means.append(mean.a)
    assert abs(means[1] - means[0]) < 2.0  # [m]


@pytest.mark.parametrize("inclination_deg", [0.0, 0.5, 179.5, 180.0])
def test_equatorial_orbits_map_both_ways(inclination_deg):
    """At 0 deg clMeanOscMap divides by zero. The map is finite in the
    equatorial bands, and osculating_from_mean inverts it: mapping its
    result back gives the mean elements (semi-major axis within 1 cm)."""
    from Basilisk.utilities import orbitalMotion

    for eccentricity in (0.0, 0.001):
        mean = orbitalMotion.ClassicElements()
        mean.a, mean.e, mean.i = 6928.137e3, eccentricity, math.radians(inclination_deg)
        mean.Omega, mean.omega, mean.f = 0.3, 0.2, 1.0
        osculating = me.osculating_from_mean(_RE, _J2, mean)
        assert 0.0 <= osculating.i <= math.pi
        back = orbitalMotion.ClassicElements()
        me.cl_mean_osc_map(_RE, _J2, osculating, back, -1)
        assert back.a == pytest.approx(mean.a, abs=0.01)  # [m]
        assert back.e == pytest.approx(mean.e, abs=1e-8)


def _propagate(r, v, seconds, step_s=20.0):
    """The state after ``seconds`` [s] of J2 motion (RK4)."""
    y = np.hstack([r, v])

    def rate(y):
        return np.hstack([y[3:], _j2_acceleration(y[:3])])

    for _ in range(int(seconds / step_s)):
        k1 = rate(y)
        k2 = rate(y + step_s / 2 * k1)
        k3 = rate(y + step_s / 2 * k2)
        k4 = rate(y + step_s * k3)
        y = y + step_s / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return y


def _orbit_state(orbit):
    from Basilisk.utilities import orbitalMotion

    elements = orbitalMotion.ClassicElements()
    elements.a, elements.e = orbit.semi_major_axis_km * 1e3, orbit.eccentricity
    elements.i, elements.Omega = math.radians(orbit.inclination_deg), math.radians(orbit.raan_deg)
    elements.omega = math.radians(orbit.arg_periapsis_deg)
    if orbit.anomaly_type == "true":
        elements.f = math.radians(orbit.true_anomaly_deg)
    else:
        mean_anomaly = math.radians(orbit.mean_anomaly_deg)
        elements.f = orbitalMotion.E2f(orbitalMotion.M2E(mean_anomaly, elements.e), elements.e)
    r, v = orbitalMotion.elem2rv(_MU, elements)
    return np.array(r), np.array(v)


def _angle_ahead(leader, follower):
    """How far ``follower`` is ahead of ``leader`` in ``leader``'s orbit
    plane [rad], from their positions (defined for equatorial orbits too)."""
    normal = np.cross(leader[:3], leader[3:])
    normal /= np.linalg.norm(normal)
    return math.atan2(np.dot(np.cross(leader[:3], follower[:3]), normal), np.dot(leader[:3], follower[:3]))


@pytest.mark.parametrize("inclination_deg", [53.0, _CRITICAL_DEG, 0.0])
def test_walker_slots_keep_their_spacing_under_j2(inclination_deg):
    """Audit E4: with equal osculating semi-major axes two slots 90 deg
    apart at 550 km and 53 deg closed to 75.8 deg in a day of J2 motion.
    With the run's J2 the generator places them by mean elements: within
    0.1 deg of 90 after a day (equatorial and critical included)."""
    from spacemissionstudio.engine.constellation import (
        CENTRAL_BODY_J2,
        WalkerConstellationRequest,
        generate_walker_constellation,
    )
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    template = SpacecraftConfig(name="template", orbit=OrbitIC(type="classical_elements", semi_major_axis_km=7000.0))
    request = WalkerConstellationRequest(total_satellites=4, num_planes=1, phasing_factor=0, altitude_km=550.0,
                                         inclination_deg=inclination_deg)
    separations = {}
    for j2 in (0.0, CENTRAL_BODY_J2["earth"]):
        first, second = generate_walker_constellation(request, template, j2=j2)[:2]
        states = [_propagate(*_orbit_state(sc.orbit), 86400.0) for sc in (first, second)]
        separations[j2] = math.degrees(_angle_ahead(*states))  # [deg]
    assert separations[CENTRAL_BODY_J2["earth"]] == pytest.approx(90.0, abs=0.1)
    if inclination_deg > 0.0:  # an equatorial orbit's semi-major axis has no such variation
        assert abs(separations[0.0] - 90.0) > 10.0  # the drift the mapping removes


@pytest.mark.parametrize("inclination_deg, eccentricity", [(97.6, 0.001), (_CRITICAL_DEG, 0.0), (_CRITICAL_DEG, 0.01)])
def test_a_phasing_follower_keeps_its_distance_under_j2(inclination_deg, eccentricity):
    """Audit E4: a 50 km follower with the chief's osculating semi-major
    axis was at 37.6 km after a day of J2 motion. With the run's J2 it has
    the chief's mean one: within 0.5 km of 50 after a day."""
    from spacemissionstudio.engine.constellation import CENTRAL_BODY_J2
    from spacemissionstudio.engine.formation import PhasingFormationRequest, generate_phasing_follower
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig

    chief = SpacecraftConfig(name="chief", orbit=OrbitIC(
        type="classical_elements", semi_major_axis_km=6928.137, eccentricity=eccentricity,
        inclination_deg=inclination_deg, raan_deg=10.0, arg_periapsis_deg=30.0, anomaly_type="true",
        true_anomaly_deg=40.0))
    request = PhasingFormationRequest(chief_name="chief", follower_name="follower", along_track_km=50.0)
    distances = {}
    for j2 in (0.0, CENTRAL_BODY_J2["earth"]):
        follower = generate_phasing_follower(request, chief, chief, "earth", j2=j2)
        chief_state = _propagate(*_orbit_state(chief.orbit), 86400.0)
        follower_state = _propagate(*_orbit_state(follower.orbit), 86400.0)
        distances[j2] = _angle_ahead(chief_state, follower_state) * np.linalg.norm(chief_state[:3]) / 1e3  # [km]
    assert distances[CENTRAL_BODY_J2["earth"]] == pytest.approx(50.0, abs=0.5)
    assert abs(distances[0.0] - 50.0) > 5.0
