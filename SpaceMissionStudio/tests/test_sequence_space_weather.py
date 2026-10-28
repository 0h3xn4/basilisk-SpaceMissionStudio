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
"""The space weather a run's drag reads is loaded for the Duration and 10
days either side. A Mission Sequence can run longer than the Duration;
past the loaded days Basilisk's spaceWeatherData held the last day's
values, for days, with only console warnings ("Publishing the last
available data"). A run may no longer go there."""

import glob
from datetime import datetime, timedelta

import pytest

from spacemissionstudio.engine import spaceweather
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.command import Command

_TEMPLATE_18 = glob.glob("spacemissionstudio/scenarios/templates/18_*.json")[0]  # drag with NRLMSISE-00


def test_the_resolved_space_weather_says_its_last_day():
    """The CSV handed to Basilisk ends 10 days after the run's end, and
    says so."""
    scenario = load_scenario(_TEMPLATE_18)
    start = datetime(2027, 3, 1)
    resolved = spaceweather.resolve_for(scenario.space_weather, start, start + timedelta(days=0.5))
    assert resolved.last_day == (start + timedelta(days=0.5 + 10)).date()
    rows = [line for line in resolved.path.read_text(encoding="utf-8").splitlines() if line[:4].isdigit()]
    assert rows[-1].startswith(resolved.last_day.isoformat())


def _sequence_scenario(sequence_days: float):
    scenario = load_scenario(_TEMPLATE_18)
    scenario.epoch_utc = "2041-10-30T00:00:00"
    scenario.sim_settings.duration_days = 0.01  # [day]
    scenario.mission_sequence = [Command(kind="propagate", params={"duration_days": sequence_days})]
    scenario.validate()
    return scenario


@pytest.mark.requires_basilisk
def test_a_mission_sequence_may_not_run_past_the_loaded_space_weather():
    """0.01 day of Duration loads space weather to 2041-11-09 (its last
    day); a sequence of 11 days stops before it runs, naming the end and
    what to do."""
    from spacemissionstudio.engine.mission_engine import MissionEngine, MissionEngineError

    with pytest.raises(MissionEngineError, match="past 2041-11-10 00:00 UTC, the end of the space weather"):
        MissionEngine(_sequence_scenario(11.0)).run()


@pytest.mark.requires_basilisk
def test_a_mission_sequence_inside_the_loaded_space_weather_runs():
    from spacemissionstudio.engine.mission_engine import MissionEngine

    scenario = _sequence_scenario(0.02)
    result, _summary = MissionEngine(scenario).run()
    last_s = next(iter(result.series.values())).time_s[-1]  # [s] the last recorded sample
    step_s = max(scenario.sim_settings.record_interval_s, scenario.sim_settings.dynamics_task_rate_s)  # [s]
    assert 0.02 * 86400.0 - step_s <= last_s <= 0.02 * 86400.0


@pytest.mark.requires_basilisk
def test_an_event_search_is_checked_where_it_stopped_not_at_its_bound():
    """The search for an event runs to a bound (10 x the Duration, at least
    10 days) that it rarely reaches: the space weather is checked where it
    stopped. Before it runs, only the Earth orientation is checked against
    the bound; after, a stop past the loaded space weather is refused."""
    from spacemissionstudio.engine.service import SimulationService, SimulationServiceError

    service = SimulationService(_sequence_scenario(0.02))
    start = datetime(2041, 10, 30)
    service._space_weather_span = (start, datetime(2041, 11, 10))
    past = int((datetime(2041, 11, 11) - start).total_seconds() * 1e9)  # [ns]
    inside = int((datetime(2041, 11, 9) - start).total_seconds() * 1e9)  # [ns]
    service.check_stop_time(past, space_weather=False)  # the bound: not refused
    service.check_stop_time(inside)
    with pytest.raises(SimulationServiceError, match="would go past 2041-11-10 00:00 UTC"):
        service.check_stop_time(past)
    with pytest.raises(SimulationServiceError, match="went past 2041-11-10 00:00 UTC"):
        service.check_space_weather(past)
