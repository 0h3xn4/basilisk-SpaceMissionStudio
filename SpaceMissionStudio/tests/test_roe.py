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
"""Tests for spacemissionstudio.engine.roe: the relative orbital elements,
the J2 state transition matrix, the impulsive manoeuvres and the
passive-safety metric. No Basilisk: each result is checked against an
independent computation (the definitions, secular J2 propagation of both
spacecraft, Gauss's equations, a brute-force minimum)."""

import math

import numpy as np
import pytest

from spacemissionstudio.engine.roe import (
    MeanElements,
    burn_effect,
    deputy_elements_from_roe,
    in_plane_at,
    in_plane_pair,
    in_plane_sequence,
    j2_stm,
    min_radial_normal_separation,
    minimum_in_plane_dv,
    out_of_plane,
    plan_correction,
    plan_drift,
    propagate_roe,
    roe_from_mean_elements,
    roe_to_rtn,
    safe_formation,
    schedule_burns,
    secular_j2_rates,
    sequence_dl_shift,
)

MU = 3.986004415e14  # [m^3/s^2] Earth
J2 = 1.0826267e-3  # [-] Earth
R_EQ = 6378136.3  # [m] Earth
CHIEF = MeanElements(a=6928137.0, e=0.001, i=math.radians(97.6), raan=math.radians(30.0),  # 550 km SSO
                     argp=math.radians(60.0), mean_anomaly=math.radians(10.0))
N = math.sqrt(MU / CHIEF.a ** 3)  # [rad/s]
ROE_M = np.array([20.0, 500.0, 300.0, -150.0, 200.0, 300.0])  # [m] every element non-zero


def _secularly(elements: MeanElements, dt: float) -> MeanElements:
    """Mean elements ``dt`` [s] later under secular J2."""
    raan_dot, argp_dot, m_dot = secular_j2_rates(elements, J2, R_EQ, MU)
    return MeanElements(elements.a, elements.e, elements.i, elements.raan + raan_dot * dt,
                        elements.argp + argp_dot * dt, elements.mean_anomaly + m_dot * dt)


def test_deputy_elements_invert_the_roe():
    """From ROE to the deputy's elements and back gives the same ROE, to
    a nanometre."""
    roe = ROE_M / CHIEF.a
    deputy = deputy_elements_from_roe(CHIEF, roe)
    assert roe_from_mean_elements(CHIEF, deputy) * CHIEF.a == pytest.approx(ROE_M, abs=1e-6)


def test_identical_orbits_have_zero_roe():
    """A deputy on the chief's own orbit has all six ROE zero."""
    assert np.all(roe_from_mean_elements(CHIEF, CHIEF) == 0.0)


def test_an_equatorial_chief_is_refused():
    """The inclination vector needs a node: an equatorial chief raises."""
    flat = MeanElements(CHIEF.a, CHIEF.e, 0.0, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="inclined"):
        deputy_elements_from_roe(flat, ROE_M / CHIEF.a)


@pytest.mark.parametrize("days", [0.5, 3.0, 10.0])
def test_the_j2_stm_matches_secular_propagation_of_both_orbits(days):
    """The J2 STM predicts the ROE that the two spacecraft's mean
    elements, each moved with its own secular J2 rates, give: within
    0.1 m over 10 days for a formation of a few hundred metres."""
    dt = days * 86400.0  # [s]
    deputy = deputy_elements_from_roe(CHIEF, ROE_M / CHIEF.a)
    truth = roe_from_mean_elements(_secularly(CHIEF, dt), _secularly(deputy, dt))
    predicted = propagate_roe(ROE_M / CHIEF.a, CHIEF, dt, J2, R_EQ, MU)
    assert predicted * CHIEF.a == pytest.approx(truth * CHIEF.a, abs=0.1)


def test_the_keplerian_stm_misses_the_j2_drift():
    """Without J2 the same prediction is tens of metres off after 3 days
    (the e/i vectors turn and the nodes drift), so the J2 test above
    really tests the J2 terms."""
    dt = 3.0 * 86400.0  # [s]
    deputy = deputy_elements_from_roe(CHIEF, ROE_M / CHIEF.a)
    truth = roe_from_mean_elements(_secularly(CHIEF, dt), _secularly(deputy, dt))
    keplerian = propagate_roe(ROE_M / CHIEF.a, CHIEF, dt, 0.0, R_EQ, MU)
    assert np.max(np.abs(keplerian - truth)) * CHIEF.a > 30.0  # [m]


def test_without_j2_only_the_mean_longitude_drifts():
    """The Keplerian STM moves only dlambda, at -3/2 n da."""
    phi = j2_stm(CHIEF, 1000.0, 0.0, R_EQ, MU)
    expected = np.eye(6)
    expected[1, 0] = -1.5 * N * 1000.0
    assert phi == pytest.approx(expected)


def test_rtn_motion_follows_the_roe():
    """The first-order relative position: an e vector gives a radial
    oscillation of its size, an i vector a cross-track one, and dlambda
    an along-track offset."""
    roe = np.array([0.0, 1000.0, 300.0, 0.0, 0.0, 200.0]) / CHIEF.a
    position, _ = roe_to_rtn(roe, 0.0, CHIEF.a, N)
    assert position == pytest.approx([-300.0, 1000.0, -200.0])
    position, _ = roe_to_rtn(roe, math.pi / 2.0, CHIEF.a, N)
    assert position == pytest.approx([0.0, 1600.0, 0.0], abs=1e-9)


def test_the_in_plane_pair_makes_the_requested_change():
    """Two along-track burns half an orbit apart change da and the e
    vector by exactly the requested amounts (Gauss's equations), for the
    least delta-V."""
    d_da, d_dex, d_dey = 5.0 / CHIEF.a, 120.0 / CHIEF.a, -60.0 / CHIEF.a
    burns = in_plane_pair(d_da, d_dex, d_dey, CHIEF.a, N)
    total = sum(burn_effect(b, CHIEF.a, N) for b in burns)
    assert total * CHIEF.a == pytest.approx([5.0, 0.0, 120.0, -60.0, 0.0, 0.0], abs=1e-9)
    assert sum(b.magnitude for b in burns) == pytest.approx(
        minimum_in_plane_dv(d_da, math.hypot(d_dex, d_dey), CHIEF.a, N))
    assert abs(burns[1].u - burns[0].u) == pytest.approx(math.pi)


def test_burns_at_other_locations_still_make_the_change():
    """Three along-track burns away from the optimal angles (say, the
    optimal ones are in eclipse) still give the exact change, for more
    delta-V than the optimal pair."""
    d_da, d_dex, d_dey = 5.0 / CHIEF.a, 120.0 / CHIEF.a, -60.0 / CHIEF.a
    burns = in_plane_at(d_da, d_dex, d_dey, [0.3, 2.4, 4.5], CHIEF.a, N)
    total = sum(burn_effect(b, CHIEF.a, N) for b in burns)
    assert total[[0, 2, 3]] * CHIEF.a == pytest.approx([5.0, 120.0, -60.0], abs=1e-6)
    assert sum(b.magnitude for b in burns) > minimum_in_plane_dv(d_da, math.hypot(d_dex, d_dey), CHIEF.a, N)


@pytest.mark.parametrize("opposite", [False, True])
def test_the_cross_track_burn_turns_the_inclination_vector(opposite):
    """One cross-track burn, at the change's angle or half an orbit later
    with the opposite sign, makes the inclination-vector change, for
    n a |d(di)|."""
    d_dix, d_diy = -80.0 / CHIEF.a, 150.0 / CHIEF.a
    burn = out_of_plane(d_dix, d_diy, CHIEF.a, N, opposite=opposite)
    effect = burn_effect(burn, CHIEF.a, N)
    assert effect * CHIEF.a == pytest.approx([0.0, 0.0, 0.0, 0.0, -80.0, 150.0], abs=1e-9)
    assert burn.magnitude == pytest.approx(N * CHIEF.a * math.hypot(d_dix, d_diy))


def test_no_change_needs_no_burns():
    """A zero change plans no burns."""
    assert in_plane_pair(0.0, 0.0, 0.0, CHIEF.a, N) == []
    assert out_of_plane(0.0, 0.0, CHIEF.a, N) is None


def test_the_drift_brings_the_mean_longitude_to_its_target():
    """Holding the planned da for the window moves dlambda to its target,
    J2 included (checked with the STM over the window)."""
    now = np.array([0.0, -2000.0, 0.0, 300.0, 0.0, 300.0]) / CHIEF.a
    target = np.array([0.0, 0.0, 0.0, 300.0, 0.0, 300.0]) / CHIEF.a
    plan = plan_drift(now, target, CHIEF, 86400.0, 100.0 / CHIEF.a, J2, R_EQ, MU)
    drifting = target.copy()
    drifting[0], drifting[1] = plan.drift_da, now[1]
    after = propagate_roe(drifting, CHIEF, plan.duration_s, J2, R_EQ, MU)
    assert after[1] * CHIEF.a == pytest.approx(0.0, abs=1e-6)
    assert plan.duration_s == pytest.approx(86400.0)


def test_a_capped_drift_takes_longer():
    """With the drift's da capped below what the window needs, the plan
    holds the cap for longer instead."""
    now = np.array([0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]) / CHIEF.a
    target = np.zeros(6)
    plan = plan_drift(now, target, CHIEF, 86400.0, 1.0 / CHIEF.a, J2, R_EQ, MU)
    assert abs(plan.drift_da) * CHIEF.a == pytest.approx(1.0)
    assert plan.duration_s > 86400.0


def test_a_safe_formation_has_parallel_e_and_i_vectors():
    """The design helper puts the e and i vectors at the same phase, with
    the requested sizes, and the follower at the requested distance."""
    roe = safe_formation(200.0, 300.0, 400.0, 90.0, CHIEF.a) * CHIEF.a
    assert roe == pytest.approx([0.0, 200.0, 0.0, 300.0, 0.0, 400.0], abs=1e-9)


@pytest.mark.parametrize("roe_m, expected_m", [
    ([0.0, 0.0, 300.0, 0.0, 300.0, 0.0], 300.0),  # parallel, equal: the full size
    ([0.0, 0.0, 0.0, 300.0, 300.0, 0.0], 0.0),  # perpendicular: they cross
    ([0.0, 0.0, 200.0, 100.0, 50.0, 250.0], None),  # general: compared with a brute-force minimum
])
def test_the_safety_margin_is_the_closest_radial_cross_track_approach(roe_m, expected_m):
    """The passive-safety formula equals the minimum over an orbit of the
    radial/cross-track distance, from the first-order motion."""
    roe = np.array(roe_m) / CHIEF.a
    u = np.linspace(0.0, 2.0 * math.pi, 200001)
    radial = -(roe[2] * np.cos(u) + roe[3] * np.sin(u))
    normal = roe[4] * np.sin(u) - roe[5] * np.cos(u)
    brute = CHIEF.a * float(np.min(np.hypot(radial, normal)))
    margin = min_radial_normal_separation(roe, CHIEF.a)
    assert margin == pytest.approx(brute, abs=1e-3)
    if expected_m is not None:
        assert margin == pytest.approx(expected_m, abs=1e-6)


TOLERANCE = [x / CHIEF.a for x in (2.0, 20.0, 10.0, 10.0)]  # [-] da, dl, |de|, |di|
HELIX = np.array([0.0, 0.0, 0.0, 300.0, 0.0, 300.0]) / CHIEF.a  # [-]


def _plan(roe_m, target=HELIX, drift_da=None, stop_drift=False, sunlit=None):
    return plan_correction(np.asarray(roe_m) / CHIEF.a, target, CHIEF, TOLERANCE, 86400.0, 100.0 / CHIEF.a,
                           drift_da, stop_drift, sunlit, J2, R_EQ, MU)


def test_inside_the_tolerances_nothing_is_planned():
    """A formation inside every tolerance gets no burns and no drift."""
    correction = _plan([1.0, 10.0, 5.0, 305.0, -5.0, 300.0])
    assert correction.burns == () and correction.drift_da is None


def test_an_along_track_error_starts_a_drift():
    """A mean-longitude error out of tolerance starts a drift: along-track
    burns set the drift's da, which the STM says closes the error in the
    window."""
    correction = _plan([0.0, -100.0, 0.0, 300.0, 0.0, 300.0])
    assert correction.drift_s == pytest.approx(86400.0)
    total = sum(burn_effect(b, CHIEF.a, N) for b in correction.burns)
    assert total[0] == pytest.approx(correction.drift_da)
    assert {b.kind for b in correction.burns} == {"in-plane"}
    drifting = np.array([0.0, -100.0, 0.0, 300.0, 0.0, 300.0]) / CHIEF.a + total
    after = propagate_roe(drifting, CHIEF, 86400.0, J2, R_EQ, MU)
    assert after[1] * CHIEF.a == pytest.approx(0.0, abs=0.5)


def test_a_small_drift_is_shorter_not_smaller():
    """A drift whose da would be below what the burns set (a quarter of the
    da tolerance) holds that da for less time instead."""
    correction = _plan([0.0, -25.0, 0.0, 300.0, 0.0, 300.0])
    d_da = sum(burn_effect(b, CHIEF.a, N) for b in correction.burns)[0] * CHIEF.a
    assert abs(d_da) == pytest.approx(0.5, rel=1e-6)  # [m] a quarter of 2 m
    assert correction.drift_s < 86400.0


def test_a_drift_in_progress_holds_its_da():
    """While drifting, the drift's da is kept: no burns while it holds."""
    correction = _plan([-0.5, -60.0, 0.0, 300.0, 0.0, 300.0], drift_da=-0.5 / CHIEF.a)
    assert correction.burns == () and correction.drift_da == -0.5 / CHIEF.a


def test_a_stopped_drift_returns_da_to_the_target():
    """Stopping a drift brings da back to the target's, and the drift
    ends."""
    correction = _plan([-0.5, -5.0, 0.0, 300.0, 0.0, 300.0], drift_da=-0.5 / CHIEF.a, stop_drift=True)
    assert correction.drift_da is None
    assert sum(burn_effect(b, CHIEF.a, N) for b in correction.burns)[0] * CHIEF.a == pytest.approx(0.5)


def test_eclipsed_locations_are_avoided():
    """With the optimal locations in eclipse, the along-track burns move to
    sunlit ones and the cross-track burn half an orbit on, and still make
    the change."""
    sunlit = lambda u: not (math.radians(150.0) < u % (2.0 * math.pi) < math.radians(280.0))  # noqa: E731
    roe_m = np.array([0.0, 0.0, -150.0, 0.0, 0.0, 120.0])  # [m] de change along +x, di along +y
    correction = _plan(roe_m, sunlit=sunlit)
    assert all(sunlit(b.u) for b in correction.burns)
    total = sum(burn_effect(b, CHIEF.a, N) for b in correction.burns)
    assert (roe_m / CHIEF.a + total)[2:] * CHIEF.a == pytest.approx(HELIX[2:] * CHIEF.a, abs=1e-6)
    assert len([b for b in correction.burns if b.kind == "in-plane"]) == 3


def test_a_long_burn_is_split_over_orbits():
    """A burn larger than one part is split into equal parts at the same
    location on consecutive orbits; the parts come in time order."""
    burn = out_of_plane(0.0, 300.0 / CHIEF.a, CHIEF.a, N)
    scheduled = schedule_burns([burn], u_now=0.0, n=N, max_dv_per_burn=burn.magnitude / 2.5, min_lead_s=10.0,
                               min_separation_s=100.0)
    period = 2.0 * math.pi / N
    assert len(scheduled) == 3
    assert [when for when, _ in scheduled] == pytest.approx([burn.u / N + k * period for k in range(3)])
    assert sum(part.magnitude for _, part in scheduled) == pytest.approx(burn.magnitude)


def test_burns_too_close_together_wait_an_orbit():
    """A burn closer than the minimum separation to one already scheduled
    waits an orbit; one too close ahead also waits an orbit."""
    a = in_plane_pair(5.0 / CHIEF.a, 0.0, 0.0, CHIEF.a, N)[0]
    b = out_of_plane(1e-6, 0.0, CHIEF.a, N)  # at u = 0, like a
    scheduled = schedule_burns([a, b], u_now=-0.001, n=N, max_dv_per_burn=1.0, min_lead_s=1.0, min_separation_s=300.0)
    period = 2.0 * math.pi / N
    assert scheduled[1][0] - scheduled[0][0] == pytest.approx(period)
    late = schedule_burns([a], u_now=-1.0e-4, n=N, max_dv_per_burn=1.0, min_lead_s=60.0, min_separation_s=1.0)
    assert late[0][0] == pytest.approx(1.0e-4 / N + period)


def test_the_sequence_dl_shift_is_the_delayed_da():
    """A da change made t seconds from now leaves dl 1.5 n d(da) t further
    than one made now (the Keplerian STM over the same span)."""
    burn = in_plane_pair(4.0 / CHIEF.a, 0.0, 0.0, CHIEF.a, N)[0]
    delay = 3000.0  # [s]
    shift = sequence_dl_shift([(delay, burn)], CHIEF.a, N)
    d_da = burn_effect(burn, CHIEF.a, N)[0]
    now = propagate_roe([d_da, 0, 0, 0, 0, 0], CHIEF, delay, 0.0, R_EQ, MU)[1]
    assert shift == pytest.approx(-now)


def test_the_in_plane_sequence_also_lands_dl():
    """Four along-track burns over two orbits change da and the e vector
    and bring dl to its target by the last burn: stepped through with the
    Keplerian ROE motion (dl moves at -3/2 n da between burns), unlike the
    pair, which leaves dl off by 1.5 n d(da)_1 T/2."""
    roe_now = np.array([0.0, 30.0, -10.0, 300.0, 0.0, 300.0]) / CHIEF.a  # e vector 10 m off, dl 30 m off
    period = 2.0 * math.pi / N
    for places in ([0.0, math.pi], [0.3, 2.4, 4.5]):  # the change's own pair; three sunlit locations
        times = [600.0 + (u / (2.0 * math.pi) + k) * period for k in range(2) for u in places]
        sequence = in_plane_sequence(0.0, 10.0 / CHIEF.a, 0.0, -30.0 / CHIEF.a, 0.0, times, places * 2,
                                     CHIEF.a, N)
        state, clock = roe_now.copy(), 0.0
        for when, burn in sequence:
            state[1] += -1.5 * N * state[0] * (when - clock)
            state = state + burn_effect(burn, CHIEF.a, N)
            clock = when
        assert state * CHIEF.a == pytest.approx([0.0, 0.0, 0.0, 300.0, 0.0, 300.0], abs=1e-6)
