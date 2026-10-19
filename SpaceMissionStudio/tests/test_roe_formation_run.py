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
"""ROE formations flown in Basilisk (engine.roe_formation): template 05's
two 405 kg satellites at 550 km sun-synchronous, 10th-degree gravity, Sun
and Moon, drag, a 0.05 N thruster. Each check compares the flight with
what the guidance promises: the follower placed at the requested ROE, a
hold inside its tolerances, a reconfiguration from 2 km behind to a
passively safe helix (impulsive: for no less than the closed-form least
delta-V; continuous: Basilisk's meanOEFeedback), the results' series
and events, and a follower with three times the chief's drag area held
with and without the differential-drag compensation."""

import math
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.requires_basilisk

_TEMPLATE = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
             / "05_formation_flying_phasing.json")
TOLERANCE_M = (2.0, 20.0, 10.0, 10.0)  # [m] the defaults: da, dl, |de|, |di|
APPROACH_M = [0.0, -2000.0, 0.0, 0.0, 0.0, 0.0]  # [m] 2 km behind
HELIX_M = [0.0, 0.0, 0.0, 300.0, 0.0, 300.0]  # [m] parallel e/i vectors, 300 m
HOLD_M = [0.0, -500.0, 0.0, 200.0, 0.0, 200.0]  # [m]
DAY_S = 86400.0  # [s]
HEAVY_DRAG_AREA_M2 = 3.0  # [m^2] the follower's, three times the chief's: a*da decays about 3.5 m a day


def _fly(law, days, targets, start_m, follower_drag_area_m2=None, **roe_fields):
    from Basilisk.utilities import orbitalMotion

    from spacemissionstudio.engine import roe_formation
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema import RoeFormationConfig, RoeTargetConfig, load_scenario

    scenario = load_scenario(_TEMPLATE)
    chief, follower = scenario.spacecraft
    follower.phasing_keeping = None
    follower.roe_formation = RoeFormationConfig(chief_spacecraft=chief.name, control_law=law,
                                                targets=[RoeTargetConfig(day, roe) for day, roe in targets],
                                                **roe_fields)
    if follower_drag_area_m2 is not None:
        follower.drag_area_m2 = follower_drag_area_m2
    follower.orbit = roe_formation.follower_orbit(chief.orbit, start_m, orbitalMotion.REQ_EARTH * 1000.0,
                                                  orbitalMotion.J2_EARTH)
    scenario.sim_settings.duration_days = days
    scenario.sim_settings.record_interval_s = 60.0  # [s]
    scenario.validate()
    result = SimulationService(scenario).run()
    return scenario, follower.name, result


def _series(result, name, part):
    return result.series[f"{name}.roe_formation.{part}"]


def _after(series, day):
    return series.data[series.time_s >= day * DAY_S]


@pytest.fixture(scope="module")
def hold():
    return _fly("impulsive", 2.0, [(0.0, HOLD_M)], HOLD_M)


@pytest.fixture(scope="module")
def heavy_hold():
    return _fly("impulsive", 3.0, [(0.0, HOLD_M)], HOLD_M, HEAVY_DRAG_AREA_M2)


@pytest.fixture(scope="module")
def heavy_hold_uncompensated():
    return _fly("impulsive", 3.0, [(0.0, HOLD_M)], HOLD_M, HEAVY_DRAG_AREA_M2, differential_drag=False)


@pytest.fixture(scope="module")
def heavy_drift():
    """The heavy follower left alone (tolerances no error reaches): the
    decay as Basilisk's drag, with the bundled real space weather, makes it."""
    return _fly("impulsive", 2.0, [(0.0, HOLD_M)], HOLD_M, HEAVY_DRAG_AREA_M2, tolerance_m=[1.0e6] * 4)


def _burn_arcs(result, name):
    """How many times the logged state turns to a burn."""
    state = _series(result, name, "state").data[:, 0]
    burning = (state == 2) | (state == 3)  # IN_PLANE_BURN, OUT_OF_PLANE_BURN
    return int(np.count_nonzero(burning[1:] & ~burning[:-1]) + int(burning[0]))


@pytest.fixture(scope="module")
def reconfiguration():
    return _fly("impulsive", 2.5, [(0.0, APPROACH_M), (0.25, HELIX_M)], APPROACH_M)


@pytest.fixture(scope="module")
def continuous_reconfiguration():
    return _fly("continuous", 2.0, [(0.0, APPROACH_M), (0.25, HELIX_M)], APPROACH_M)


def test_the_follower_starts_at_the_requested_roe(hold):
    """Placed from the chief's mean elements plus the ROE, mapped back to
    osculating elements and corrected until their mean elements match, the
    follower's first measured mean ROE are the requested ones within 20 cm
    (the run turns the elements into a state with its own gravity
    constant)."""
    _, name, result = hold
    assert _series(result, name, "roe").data[0] == pytest.approx(HOLD_M, abs=0.2)


def test_an_impulsive_hold_stays_in_its_tolerances(hold):
    """After the first correction (half a day), the mean longitude, e and i
    vectors stay inside their tolerances (e: up to one decision late,
    a fifth over), the relative semi-major axis within three times its
    (between the burns of a pair), for under 0.015 m/s a day."""
    _, name, result = hold
    error = np.abs(_after(_series(result, name, "roe_error"), 0.5))
    assert np.max(error[:, 1]) <= TOLERANCE_M[1]
    assert np.max(np.hypot(error[:, 2], error[:, 3])) <= 1.2 * TOLERANCE_M[2]
    assert np.max(np.hypot(error[:, 4], error[:, 5])) <= TOLERANCE_M[3]
    assert np.max(error[:, 0]) <= 3.0 * TOLERANCE_M[0]
    assert _series(result, name, "delta_v").data[-1, 0] < 0.015 * 2.0  # [m/s]


def test_the_impulsive_law_reconfigures_to_the_safe_helix(reconfiguration):
    """From 2 km behind to the 300 m helix: over the last half day the mean
    longitude, e and i vectors are inside their tolerances (e a fifth over
    at most), the relative semi-major axis within three times its
    (between the burns of an e-vector correction), the closest
    radial/cross-track approach is at least 250 m, and the
    delta-V is no less than the closed-form least delta-V, (n a / 2)
    |d(de)| + n a |d(di)|, and within 30 % of it."""
    _, name, result = reconfiguration
    error = np.abs(_after(_series(result, name, "roe_error"), 2.0))
    assert np.max(error[:, 0]) <= 3.0 * TOLERANCE_M[0]
    assert np.max(error[:, 1]) <= TOLERANCE_M[1]
    assert np.max(np.hypot(error[:, 2], error[:, 3])) <= 1.2 * TOLERANCE_M[2]
    assert np.max(np.hypot(error[:, 4], error[:, 5])) <= TOLERANCE_M[3]
    assert np.min(_after(_series(result, name, "min_rn_separation"), 2.0)) >= 250.0  # [m]
    na = math.sqrt(3.986004415e14 / 6928137.0)  # [m/s]
    least = na / 2.0 * 300.0 / 6928137.0 + na * 300.0 / 6928137.0  # [m/s]
    delta_v = _series(result, name, "delta_v").data[-1, 0]
    assert least <= delta_v <= 1.3 * least


def test_the_continuous_law_reconfigures_for_more_delta_v(continuous_reconfiguration, reconfiguration):
    """Basilisk's meanOEFeedback reaches the same helix: over the last half
    day every ROE error is under 5 m. It fires most of the time and takes
    more delta-V than the impulsive law."""
    _, name, result = continuous_reconfiguration
    error = np.abs(_after(_series(result, name, "roe_error"), 1.5))
    assert np.max(error) < 5.0  # [m]
    _, impulsive_name, impulsive = reconfiguration
    assert (_series(result, name, "delta_v").data[-1, 0]
            > _series(impulsive, impulsive_name, "delta_v").data[-1, 0])
    force = _series(result, name, "force").data
    assert np.all(force[:, 1] <= 0.05 + 1e-12)  # [N] applied never above the thruster's


def test_the_results_have_the_expected_series_and_events(reconfiguration):
    """Every series engine.series_names promises is recorded, and the
    burns and the drift appear as events."""
    from spacemissionstudio.engine.events import BURN, MODE, extract_events
    from spacemissionstudio.engine.series_names import expected_series_names

    scenario, name, result = reconfiguration
    roe_names = [n for n in expected_series_names(scenario) if ".roe_formation." in n]
    assert roe_names and all(n in result.series for n in roe_names)
    events = [e for e in extract_events(result) if e.spacecraft == name]
    labels = {e.label for e in events if e.kind == BURN}
    assert {"ROE burn (in-plane)", "ROE burn (out-of-plane)"} <= labels
    assert any(e.kind == MODE and e.label == "ROE drift" for e in events)
    assert all("delta_v" in dict(e.quantities) for e in events if e.label.startswith("ROE burn"))


def test_the_differential_drag_estimate_is_the_decay_basilisk_flies(heavy_hold, heavy_drift):
    """The decay the controller estimates while holding (from half a day
    on, once four orbits are in) is within 8 % of the one a straight line
    through the left-alone follower's mean a*da gives over two days
    (about -3.5 m a day), and the guidance compensates all of it."""
    _, drift_name, drift = heavy_drift
    roe_series = _series(drift, drift_name, "roe")
    assert _series(drift, drift_name, "delta_v").data[-1, 0] == 0.0  # left alone
    flown_m_per_day = np.polyfit(roe_series.time_s / DAY_S, roe_series.data[:, 0], 1)[0]
    assert -4.5 < flown_m_per_day < -2.5  # [m/day]
    _, name, result = heavy_hold
    rate = _after(_series(result, name, "drag_da_rate"), 0.5)
    assert np.all(np.abs(rate[:, 0] / flown_m_per_day - 1.0) < 0.08)
    assert np.array_equal(rate[:, 1], rate[:, 0])


def test_compensating_differential_drag_keeps_the_hold_in_tolerance(heavy_hold, heavy_hold_uncompensated):
    """With the compensation the heavy follower's mean longitude stays
    inside its 20 m tolerance after the first half day (13 m measured),
    the e and i vectors as in the twin hold, the relative semi-major axis
    within three times its; without it the mean longitude leaves the
    tolerance (27 m measured). It also takes less delta-V (0.036 against
    0.044 m/s over 3 days measured) and at most 70 % of the burns (30
    against 60)."""
    _, name, result = heavy_hold
    error = np.abs(_after(_series(result, name, "roe_error"), 0.5))
    assert np.max(error[:, 1]) <= TOLERANCE_M[1]
    assert np.max(np.hypot(error[:, 2], error[:, 3])) <= 1.2 * TOLERANCE_M[2]
    assert np.max(np.hypot(error[:, 4], error[:, 5])) <= TOLERANCE_M[3]
    assert np.max(error[:, 0]) <= 3.0 * TOLERANCE_M[0]
    _, other_name, uncompensated = heavy_hold_uncompensated
    assert np.max(np.abs(_after(_series(uncompensated, other_name, "roe_error"), 0.5)[:, 1])) > TOLERANCE_M[1]
    assert (_series(result, name, "delta_v").data[-1, 0]
            < _series(uncompensated, other_name, "delta_v").data[-1, 0])
    assert _burn_arcs(result, name) <= 0.7 * _burn_arcs(uncompensated, other_name)
    assert f"{other_name}.roe_formation.drag_da_rate" not in uncompensated.series


def test_twin_spacecraft_compensate_no_drag(hold):
    """Template 05's sister satellites feel the same drag: the estimate
    stays under a tenth of a metre a day and nothing is compensated, so
    the hold flies as it did before the compensation existed."""
    _, name, result = hold
    rate = _series(result, name, "drag_da_rate").data
    assert np.all(rate[:, 1] == 0.0)
    assert np.nanmax(np.abs(_after(_series(result, name, "drag_da_rate"), 0.5)[:, 0])) < 0.1  # [m/day]
