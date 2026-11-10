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
"""The live 3D View's feed and probe (``engine.live_view``): how often it
samples, its buffer, its pacing to real time (on a fake clock), and, with
Basilisk, that the probe reads what the run's results hold and changes
none of them."""

import math
import threading

import numpy as np
import pytest

from spacemissionstudio.engine import live_view
from spacemissionstudio.engine.live_view import LiveFeed, sample_interval_s


class _Clock:
    """A wall clock that moves only when slept on."""

    def __init__(self):
        self.now = 100.0  # [s]
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


# -- how often ---------------------------------------------------------------------------------------
def test_the_probe_samples_about_200_times_an_orbit_in_whole_steps():
    """A 5,800 s orbit at a 10 s step: every 30 s (29 s rounded to whole
    steps); never less than one step; at most 20,000 samples per run."""
    assert sample_interval_s(5800.0, 86400.0, 10.0) == 30.0  # [s]
    assert sample_interval_s(5800.0, 86400.0, 0.1) == pytest.approx(29.0)  # [s]
    assert sample_interval_s(5800.0, 86400.0, 60.0) == 60.0  # [s] one step at least
    assert sample_interval_s(5800.0, 100 * 86400.0, 1.0) == pytest.approx(432.0)  # [s] 100 days / 20,000
    assert sample_interval_s(None, 2000.0, 0.1) == pytest.approx(1.0)  # [s] no orbit: Duration / 2000


def test_with_pacing_it_samples_often_enough_to_watch():
    """Held to real time, at least 20 samples a real second where the
    step allows: x100 every 5 s, x1 every step (up to 100,000 samples a
    run: a watched run is sampled finer than one run unwatched)."""
    assert sample_interval_s(5800.0, 86400.0, 1.0, pacing=100.0) == 5.0  # [s]
    assert sample_interval_s(5800.0, 86400.0, 1.0, pacing=1.0) == 1.0  # [s]
    assert sample_interval_s(5800.0, 86400.0, 1.0, pacing=1000.0) == 29.0  # [s] the orbit's own is finer
    assert sample_interval_s(5800.0, 10 * 86400.0, 1.0, pacing=1.0) == 9.0  # [s] 10 days / 100,000, rounded


# -- the buffer ----------------------------------------------------------------------------------------
def test_the_feed_hands_over_every_sample_once_in_order():
    """Pushed on one thread, drained on another: every sample once, in
    order, as arrays; ``limit`` takes the oldest first."""
    feed = LiveFeed()
    feed.start(["a", "b"], [True, False], 7.0e6)
    assert feed.drain() is None

    def push():
        for n in range(500):
            feed.push(float(n), [(n, 0, 0), (0, n, 0)], [(1, 2, 3), (4, 5, 6)], [(0.1, 0, 0), (math.nan,) * 3])

    thread = threading.Thread(target=push)
    thread.start()
    got = []
    while thread.is_alive() or feed.pending():
        samples = feed.drain(limit=64)
        if samples is not None:
            assert len(samples.times_s) <= 64
            got.append(samples)
    thread.join()
    times = np.concatenate([s.times_s for s in got])
    np.testing.assert_array_equal(times, np.arange(500.0))
    position = np.concatenate([s.position_m for s in got])
    assert position.shape == (500, 2, 3) and position[42, 1, 1] == 42.0
    sigma = np.concatenate([s.sigma_BN for s in got])
    assert sigma[7, 0, 0] == 0.1 and np.isnan(sigma[:, 1]).all()
    assert feed.count == 500 and feed.names == ["a", "b"] and feed.attitude == [True, False]


# -- pacing ----------------------------------------------------------------------------------------------
def test_as_fast_as_possible_never_waits():
    clock = _Clock()
    feed = LiveFeed(clock=clock, sleep=clock.sleep)
    for t in range(0, 10000, 100):
        feed.pace(float(t))
    assert clock.sleeps == []


def test_pacing_holds_simulated_time_to_real_time_times_the_factor():
    """x10: 100 simulated seconds take 10 real seconds, slept in slices
    of at most 50 ms."""
    clock = _Clock()
    feed = LiveFeed(pacing=10.0, clock=clock, sleep=clock.sleep)
    for t in np.arange(0.0, 101.0, 10.0):  # [s]
        feed.pace(t)
    assert clock.now - 100.0 == pytest.approx(10.0)  # [s]
    assert max(clock.sleeps) <= live_view.SLEEP_SLICE_S + 1e-12
    assert feed.slept_s == pytest.approx(10.0)  # [s]


def test_a_run_slower_than_its_pace_is_not_made_to_catch_up():
    """A run that falls more than a second behind counts its pace again
    from where it is, rather than racing to catch up."""
    clock = _Clock()
    feed = LiveFeed(pacing=1.0, clock=clock, sleep=clock.sleep)
    feed.pace(0.0)
    clock.now += 5.0  # [s] a slow step: 5 s of wall clock for 1 s simulated
    feed.pace(1.0)
    assert clock.sleeps == []
    feed.pace(2.0)  # paced again from t = 1 s
    assert sum(clock.sleeps) == pytest.approx(1.0)


def test_cancel_ends_a_wait_at_once_and_the_pace_can_change_during_a_run():
    """Cancel: the probe stops waiting within one slice. A new pace
    counts from the moment it is chosen."""
    clock = _Clock()
    cancelled = []
    feed = LiveFeed(pacing=1.0, clock=clock, sleep=clock.sleep, should_cancel=lambda: bool(cancelled))
    feed.pace(0.0)
    original = clock.sleep

    def sleep(seconds):
        original(seconds)
        if clock.now > 101.0:  # [s] one real second into a 1000 s wait
            cancelled.append(True)

    feed.sleep = sleep
    feed.pace(1000.0)
    assert clock.now - 100.0 == pytest.approx(1.0 + live_view.SLEEP_SLICE_S, abs=live_view.SLEEP_SLICE_S)
    cancelled.clear()
    feed.sleep = clock.sleep
    feed.set_pacing(100.0)
    start = clock.now
    feed.pace(1000.0)  # the reference is reset: no wait for this sample
    feed.pace(1100.0)
    assert clock.now - start == pytest.approx(1.0)  # [s] 100 simulated seconds at x100
    feed.set_pacing(0.0)
    feed.pace(5000.0)
    assert clock.now - start == pytest.approx(1.0)


# -- the probe in a run (Basilisk) ------------------------------------------------------------------------
def _template(name):
    from spacemissionstudio import api

    return api.load(api.template(name))


def _identical(a, b):
    """Two ResultSets with the same series, bit for bit, and the same warnings and seeds."""
    assert set(a.series) == set(b.series)
    for name in a.series:
        np.testing.assert_array_equal(a.series[name].time_s, b.series[name].time_s, err_msg=name)
        np.testing.assert_array_equal(a.series[name].data, b.series[name].data, err_msg=name)
    assert a.warnings == b.warnings
    assert a.provenance.rng_seeds == b.provenance.rng_seeds


@pytest.mark.requires_basilisk
def test_the_probe_reads_the_run_s_own_states_and_changes_no_result():
    """Template 10 (full attitude, no control), 0.1 day: the run's
    results with the probe are bit for bit those without it (the seeds
    and the provenance's seed list too); the probe's samples are every
    interval from t = 0, and each is the run's own position, velocity
    and attitude at that time."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = _template("10_gravity_gradient_torque")
    scenario.sim_settings.duration_days = 0.1  # [day]
    plain = SimulationService(scenario).run_live(lambda partial, fraction: None)
    service = SimulationService(scenario)
    feed = LiveFeed(interval_s=60.0)  # [s]
    service.live_feed = feed
    probed = service.run_live(lambda partial, fraction: None)
    _identical(plain, probed)
    assert "liveViewProbe" not in probed.provenance.rng_seeds

    name = scenario.spacecraft[0].name
    samples = feed.drain()
    assert feed.names == [name] and feed.attitude == [True] and feed.interval_used_s == 60.0
    np.testing.assert_allclose(samples.times_s, np.arange(0.0, 0.1 * 86400.0 + 1.0, 60.0))
    position, attitude = probed.series[f"{name}.position_N"], probed.series[f"{name}.attitude_sigma_BN"]
    velocity = probed.series[f"{name}.velocity_N"]
    for k, t in enumerate(samples.times_s):
        row = np.flatnonzero(np.isclose(position.time_s, t))
        if len(row):
            np.testing.assert_array_equal(samples.position_m[k, 0], position.data[row[0]])
            np.testing.assert_array_equal(samples.velocity_m_s[k, 0], velocity.data[row[0]])
            np.testing.assert_array_equal(samples.sigma_BN[k, 0], attitude.data[row[0]])
    assert feed.extent_m == pytest.approx(np.max(np.linalg.norm(position.data, axis=1)), rel=1e-3)


@pytest.mark.requires_basilisk
def test_the_probe_samples_the_navigation_attitude_the_results_use():
    """Template 06 (attitude control): the attitude sampled is the
    navigation attitude the run's ``attitude_sigma_BN`` holds; no result
    changes."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = _template("06_attitude_pointing_basic")
    scenario.sim_settings.duration_days = 0.01  # [day]
    plain = SimulationService(scenario).run()
    service = SimulationService(scenario)
    service.live_feed = LiveFeed(interval_s=10.0)  # [s]
    probed = service.run()
    _identical(plain, probed)
    name = scenario.spacecraft[0].name
    samples = service.live_feed.drain()
    attitude = probed.series[f"{name}.attitude_sigma_BN"]
    matched = 0
    for k, t in enumerate(samples.times_s):
        row = np.flatnonzero(np.isclose(attitude.time_s, t))
        if len(row):
            np.testing.assert_array_equal(samples.sigma_BN[k, 0], attitude.data[row[0]])
            matched += 1
    assert matched >= len(samples.times_s) - 1


@pytest.mark.requires_basilisk
def test_a_mission_sequence_is_sampled_through_its_burns():
    """Template 08 (impulsive orbit raise): the probe samples the whole
    sequence, and its results are unchanged."""
    from spacemissionstudio.engine.mission_engine import MissionEngine
    from spacemissionstudio.engine.service import SimulationService

    scenario = _template("08_mission_sequence_orbit_raise")
    plain, _summary = MissionEngine(scenario, service=SimulationService(scenario)).run()
    service = SimulationService(scenario)
    service.live_feed = LiveFeed()
    probed, _summary = MissionEngine(scenario, service=service).run()
    _identical(plain, probed)
    samples = service.live_feed.drain()
    end_s = plain.series[f"{scenario.spacecraft[0].name}.position_N"].time_s[-1]  # [s]
    assert samples.times_s[0] == 0.0 and samples.times_s[-1] > end_s - 2 * service.live_feed.interval_used_s
    radius = np.linalg.norm(samples.position_m[:, 0], axis=1)  # [m]
    assert radius.max() - radius.min() > 1.0e5  # [m] the raise is in the samples


@pytest.mark.requires_basilisk
def test_a_segmented_run_is_sampled_on_one_clock(monkeypatch):
    """A run split into segments (engine.long_run): one feed across them,
    each segment's samples shifted by its start, the interval kept; its
    results unchanged."""
    from spacemissionstudio.engine import long_run
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema.scenario import OrbitIC, Scenario, SimSettings, SpacecraftConfig

    monkeypatch.setattr(long_run, "SEGMENT_DAYS", 0.25)  # [day]
    monkeypatch.setattr(SimSettings, "_MAX_SINGLE_RUN_DAYS", 0.25)  # [day]
    scenario = Scenario(name="long", epoch_utc="2030-01-01T00:00:00",
                        sim_settings=SimSettings(duration_days=1.0, dynamics_task_rate_s=30.0),
                        spacecraft=[SpacecraftConfig(name="sat-1", orbit=OrbitIC(
                            type="classical_elements", semi_major_axis_km=6778.0, eccentricity=0.0,  # [km]
                            inclination_deg=97.0, raan_deg=0.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0))])
    plain = SimulationService(scenario).run_live(lambda partial, fraction: None)
    service = SimulationService(scenario)
    service.live_feed = LiveFeed(duration_s=86400.0)  # [s]
    probed = service.run_live(lambda partial, fraction: None)
    _identical(plain, probed)
    samples = service.live_feed.drain()
    step = service.live_feed.interval_used_s
    assert step == 30.0  # [s] 5,555 s / 200 = 28 s, rounded to whole steps
    unique = np.unique(samples.times_s)
    assert unique[0] == 0.0 and unique[-1] == pytest.approx(86400.0)
    np.testing.assert_allclose(np.diff(unique), step)
    position = plain.series["sat-1.position_N"]
    for t in (0.3 * 86400.0, 0.8 * 86400.0):  # [s] in the second and the fourth segment
        k = int(np.argmin(np.abs(samples.times_s - t)))
        row = int(np.argmin(np.abs(position.time_s - samples.times_s[k])))
        assert position.time_s[row] == pytest.approx(samples.times_s[k])
        np.testing.assert_allclose(samples.position_m[k, 0], position.data[row], atol=1e-6)  # [m]
