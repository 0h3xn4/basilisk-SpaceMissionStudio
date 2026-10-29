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
"""A run's headline figures for the Compare tab (docs/ux-audit.md U-33):
read from the recorded series and the events, only when recorded."""

import math

import numpy as np

from spacemissionstudio.engine import run_summary
from spacemissionstudio.engine.results import ResultSet, TimeSeries

_T = np.arange(0.0, 7200.0, 60.0)  # [s] two hours, one sample a minute
_N = _T.size


def _add(result, name, columns, data, units=""):
    result.add(TimeSeries(name, _T, columns, np.asarray(data, dtype=float).reshape(_N, -1), units))


def _run():
    result = ResultSet("demo")
    _add(result, "sat.position_N", ("x", "y", "z"), np.zeros((_N, 3)), "m")
    _add(result, "sat.station_keeping.delta_v", ("cumulative_delta_v",), np.linspace(0.0, 1.5, _N), "m/s")
    _add(result, "sat.constant_thrust.delta_v", ("cumulative_delta_v",), np.linspace(0.0, 0.25, _N), "m/s")
    _add(result, "sat.station_keeping.propellant_remaining", ("propellant",), np.linspace(2.0, 1.9, _N), "kg")
    t_long = np.arange(0.0, 3.0 * 5740.0, 60.0)  # [s] three orbits of a 550 km orbit
    wobble = 50.0 * np.sin(2.0 * np.pi * t_long / 5740.0)  # [m] what first-order mean elements leave
    result.add(TimeSeries("sat.orbit_elements_mean.semi_major_axis", t_long, ("semi_major_axis",),
                          6928e3 - 0.5e3 * t_long / t_long[-1] + wobble, "m"))
    access = np.zeros(_N)
    access[10:20] = access[60:70] = 1
    margin = np.full(_N, np.nan)  # [dB] NaN outside access
    margin[10:20], margin[60:70] = 6.0, 3.5
    _add(result, "gs.access_to_sat.has_access", ("has_access",), access)
    _add(result, "gs.access_to_sat.link_margin_db", ("link_margin_db",), margin, "dB")
    sunlight = np.ones(_N)  # [-]
    sunlight[30:65] = 0.0
    _add(result, "sat.eclipse.illumination_factor", ("illumination_factor",), sunlight)
    _add(result, "sat.battery_charge", ("charge",), 40.0 - 10.0 * (1.0 - sunlight), "W*hr")
    _add(result, "sat.data_handling.data_downlinked", ("data_downlinked",), np.linspace(0.0, 2.5e9, _N), "bit")
    return result


def test_the_figures_come_from_the_recorded_series_and_events():
    """The run's headline figures (delta-V of both controllers, propellant,
    orbit-averaged SMA change, length, lowest margin and charge, passes,
    eclipses, data downlinked) come from its series and events; a ground
    station gets none."""
    figures = run_summary.by_key(run_summary.summarize(_run()))
    assert math.isclose(figures["sat.delta_v"].value, 1.75)  # [m/s] both controllers
    assert math.isclose(figures["sat.propellant_used"].value, 0.1)  # [kg]
    assert math.isclose(figures["sat.mean_sma_change"].value, -0.5 * 2.0 / 3.0, rel_tol=0.02)  # [km] orbit-averaged
    assert figures["run_length"].value > 4.0  # [h] the SMA series runs longest
    assert figures["sat.lowest_link_margin"].value == 3.5  # [dB] only while in view
    assert figures["sat.lowest_battery_charge"].value == 30.0  # [W*h]
    assert figures["sat.passes"].value == 2 and math.isclose(figures["sat.contact_time"].value, 18.0)  # [min]
    assert figures["sat.eclipses"].value == 1 and math.isclose(figures["sat.eclipse_time"].value, 34.0)  # [min]
    assert math.isclose(figures["sat.data_downlinked"].value, 2.5)  # [Gbit]
    assert figures["sat.delta_v"].label == "Delta-V" and figures["sat.delta_v"].text() == "1.750"
    assert "gs.delta_v" not in figures  # a ground station is not a spacecraft


def test_a_run_shorter_than_two_orbits_has_no_semi_major_axis_change():
    """A run shorter than two orbits gives no SMA change, only its length."""
    result = ResultSet("short")
    _add(result, "sat.position_N", ("x", "y", "z"), np.zeros((_N, 3)), "m")
    _add(result, "sat.orbit_elements_mean.semi_major_axis", ("semi_major_axis",), np.linspace(6928e3, 6927e3, _N), "m")
    assert "sat.mean_sma_change" not in run_summary.by_key(run_summary.summarize(result))
    assert math.isclose(run_summary.by_key(run_summary.summarize(result))["run_length"].value, 7140.0 / 3600.0)


def test_a_figure_shows_only_when_the_run_recorded_it():
    """A run that recorded only a position gives only its length; no run gives
    nothing."""
    result = ResultSet("bare")
    _add(result, "sat.position_N", ("x", "y", "z"), np.zeros((_N, 3)), "m")
    assert [f.key for f in run_summary.summarize(result)] == ["run_length"]
    assert run_summary.summarize(None) == []


def test_several_spacecraft_name_theirs():
    """With two spacecraft, each figure carries its spacecraft's name."""
    result = _run()
    _add(result, "sat-2.position_N", ("x", "y", "z"), np.zeros((_N, 3)), "m")
    _add(result, "sat-2.station_keeping.delta_v", ("cumulative_delta_v",), np.linspace(0.0, 0.5, _N), "m/s")
    figures = run_summary.by_key(run_summary.summarize(result))
    assert figures["sat-2.delta_v"].label == "sat-2: Delta-V" and figures["sat.delta_v"].label == "sat: Delta-V"


def test_the_event_table_counts_each_kind_with_its_total_time():
    """The event table gives each kind's count and total minutes."""
    from spacemissionstudio.engine import events

    table = run_summary.event_table(events.extract_events(_run()))
    assert table["pass over gs"] == (2, 18.0)  # [min]
    assert table["eclipse (umbra)"] == (1, 34.0)  # [min]


def test_the_delta_v_includes_the_roe_formation_controller():
    """Audit 3.5: the ROE formation controller's delta-V was left out of the
    run's figure (its propellant was counted, from the shared tank)."""
    result = _run()
    _add(result, "sat.roe_formation.delta_v", ("cumulative_delta_v",), np.linspace(0.0, 0.5, _N), "m/s")
    figures = run_summary.by_key(run_summary.summarize(result))
    assert math.isclose(figures["sat.delta_v"].value, 2.25)  # [m/s] 1.5 + 0.25 + 0.5


def test_the_semi_major_axis_change_averages_over_the_central_bodys_own_orbit():
    """Audit 3.14: the averaging window was an orbit period from Earth's mu
    for every body. For a Mars orbit (period 7083 s) with a wobble at that
    period, Earth's mu gave a window of 0.33 periods, which did not average
    the wobble out; the run's own mu does."""
    from spacemissionstudio.engine.results import RunProvenance

    mu_mars, a = 4.282837e13, 3789.5e3  # [m^3/s^2], [m]
    period = 2.0 * math.pi * math.sqrt(a ** 3 / mu_mars)  # [s]
    t = np.arange(0.0, 3.0 * period, 30.0)  # [s] three orbits
    wobble = 2000.0 * np.sin(2.0 * np.pi * t / period)  # [m]
    provenance = RunProvenance(spacemissionstudio_version="test", basilisk_version="test", run_started_utc="-",
                               integrator="rkf78", dynamics_task_rate_s=30.0, central_body="mars barycenter",
                               central_body_mu_m3_s2=mu_mars)
    result = ResultSet("mars", provenance=provenance)
    result.add(TimeSeries("probe.position_N", t, ("x", "y", "z"), np.zeros((t.size, 3)), "m"))
    result.add(TimeSeries("probe.orbit_elements_mean.semi_major_axis", t, ("semi_major_axis",),
                          a - 300.0 * t / t[-1] + wobble, "m"))
    figures = run_summary.by_key(run_summary.summarize(result))
    assert math.isclose(figures["probe.mean_sma_change"].value, -0.3 * 2.0 / 3.0, rel_tol=0.05)  # [km]
