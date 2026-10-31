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
"""Calculation traces (engine.trace, transparency plan Phase 4a): every
number of the propellant budget can be recomputed from its trace alone,
each input names where it came from, and the traces reach the exports and
the command line."""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from test_propellant_budget import _no_reentry, _scenario, _StubMakeup

from spacemissionstudio import constants
from spacemissionstudio.config import registry
from spacemissionstudio.config.registry import Configuration
from spacemissionstudio.engine import propellant_budget as pb
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.engine.trace import SOURCE_KINDS, Trace
from spacemissionstudio.schema.scenario import PropellantBudgetConfig


def _v(trace):
    return math.sqrt(constants.EARTH_GM_M3_S2 / trace.input("a"))  # [m/s]


# Each equation a budget trace may state, and the number it gives from the trace's own inputs.
_EQUATIONS = {
    "dV = entered": lambda t: t.input("dV"),
    "dV = 0": lambda t: 0.0,
    "dV = max(v * da / (2 a), v * de / 2)": lambda t: max(_v(t) * t.input("da") / (2.0 * t.input("a")),
                                                         _v(t) * t.input("de") / 2.0),
    "dV = 2 v sin(di / 2)": lambda t: 2.0 * _v(t) * math.sin(math.radians(t.input("di")) / 2.0),
    "dV = N * f * 2 * v * dA / (2 a)   (dA up, then back)":
        lambda t: t.input("N") * t.input("f") * 2.0 * _v(t) * t.input("dA") / (2.0 * t.input("a")),
    "dV = v * dA / (2 a)": lambda t: _v(t) * t.input("dA") / (2.0 * t.input("a")),
    "dV = dV_before + dV_last * (1 + f)": lambda t: t.input("dV_before") + t.input("dV_last") * (1.0 + t.input("f")),
    "dV = dV_run * k": lambda t: t.input("dV_run") * t.input("k"),
    "m_p = m * (1 - exp(-dV / Ve))": lambda t: t.input("m") * (1.0 - math.exp(-t.input("dV") / t.input("Ve"))),
    "m_p = entered": lambda t: t.input("m_p"),
    "m_p = m_att * f": lambda t: t.input("m_att") * t.input("f"),
    "m_p = f * m_tank": lambda t: t.input("f") * t.input("m_tank"),
    "m_p = dm_tank * s * k": lambda t: t.input("dm_tank") * t.input("s") * t.input("k"),
    "eta = cos(alpha) * cos(beta) * eta_plume * eta_mod":
        lambda t: (math.cos(math.radians(t.input("alpha"))) * math.cos(math.radians(t.input("beta")))
                   * t.input("eta_plume") * t.input("eta_mod")),
    "Ve = eta * Isp * g0": lambda t: t.input("eta") * t.input("Isp") * t.input("g0"),
    "m_dry = m_sc * (1 + f_sys)": lambda t: t.input("m_sc") * (1.0 + t.input("f_sys")),
    "m_dry = m_sc": lambda t: t.input("m_sc"),
}


def _graveyard(t):
    r1 = t.input("a")
    r2 = r1 + t.input("dr0") + t.input("k") * t.input("Cr") * t.input("A") / t.input("m_dry")
    mu = constants.EARTH_GM_M3_S2
    return (math.sqrt(mu / r1) * (math.sqrt(2.0 * r2 / (r1 + r2)) - 1.0)
            + math.sqrt(mu / r2) * (1.0 - math.sqrt(2.0 * r1 / (r1 + r2))))


def _recomputed(trace: Trace) -> float | None:
    """The trace's result from its inputs, or None for a result the trace
    names but a solver gave (the re-entry, the drag estimate, a sweep's)."""
    if trace.equation.startswith("dr = dr0 + k * Cr * A / m_dry"):
        return _graveyard(trace)
    if trace.equation.startswith(("dV: the apogee burn", "dV = 0: the orbit already", "dV = sum over the mission",
                                  "dV = the launch-delay sweep's", "m_p = sum of the rows'")):
        return None
    assert trace.equation in _EQUATIONS, f"{trace.quantity}: no check for {trace.equation!r}"
    return _EQUATIONS[trace.equation](trace)


def _all_traces(budget):
    yield from budget.traces.values()
    for row in budget.rows:
        yield from (t for t in (row.delta_v_trace, row.propellant_trace) if t is not None)


def _every_contributor(disposal="controlled_reentry", **extra):
    settings = dict(isp_s=300.0, thrust_angle_deg=5.0, misalignment_deg=0.5, plume_efficiency=0.98,
                    modulation_efficiency=0.97, injection_sma_error_km=5.0, injection_eccentricity_error=1e-3,
                    injection_inclination_error_deg=0.05, injection_raan_delta_v_m_s=4.0,
                    orbit_acquisition_delta_v_m_s=12.0, transfer_delta_v_m_s=30.0, in_plane_control_delta_v_m_s=60.0,
                    out_of_plane_control_delta_v_m_s=7.0, collision_avoidance_count=3.0,
                    formation_delta_v_m_s=2.0, attitude_thruster_propellant_kg=0.4, hall_thruster_ignition_kg=0.05,
                    clearance_sma_drop_km=10.0, disposal=disposal, controlled_reentry_delta_v_m_s=80.0,
                    controlled_reentry_last_burn_m_s=40.0, tank_capacity_kg=20.0)  # [s], [deg], [km], [m/s], [kg]
    settings.update(extra)
    return _scenario(PropellantBudgetConfig(**settings))


@pytest.mark.parametrize("disposal", ["controlled_reentry", "graveyard", "uncontrolled_reentry"])
def test_every_budget_number_is_recomputed_from_its_trace(disposal):
    """Each row's delta-V and propellant, and the efficiency, exhaust speed
    and dry mass, equal what their trace's equation gives from the trace's
    own inputs; the propellant total is the sum of the rows."""
    scenario = _every_contributor(disposal, dry_mass_includes_margin=disposal == "graveyard")
    budget = pb.compute_budget(scenario, "sat-1", reentry_solver=_no_reentry)
    assert budget.traces["efficiency"].value == budget.efficiency
    assert budget.traces["exhaust_speed"].value == budget.efficiency * budget.isp_s * pb.G0_M_S2
    assert budget.traces["dry_mass"].value == budget.dry_mass_kg
    assert budget.traces["total_propellant"].value == budget.total_propellant_kg
    for row in budget.rows:
        assert row.propellant_trace is not None, row.contributor
        assert row.propellant_trace.value == row.propellant_kg, row.contributor
        if row.delta_v_m_s is not None:
            assert row.delta_v_trace.value == row.delta_v_m_s, row.contributor
        else:
            assert row.delta_v_trace is None, row.contributor
    checked = 0
    for trace in _all_traces(budget):
        expected = _recomputed(trace)
        if expected is not None:
            assert trace.value == pytest.approx(expected, rel=1e-12, abs=1e-12), trace.quantity
            checked += 1
    assert checked >= len(budget.rows) + 3


def test_a_rows_propellant_starts_from_the_mass_the_rows_above_left():
    """The mass before each burn, in its propellant trace, is the dry mass
    plus the iteration's load less the propellant of the rows above."""
    budget = pb.compute_budget(_every_contributor(), "sat-1", reentry_solver=_no_reentry)
    load = None
    for at, row in enumerate(budget.rows):
        trace = row.propellant_trace
        if trace.equation != "m_p = m * (1 - exp(-dV / Ve))":
            continue
        source = next(q for q in trace.intermediates if q.symbol == "m").source
        load = float(source.split("m_load = ")[1].split(" kg")[0])
        above = sum(r.propellant_kg for r in budget.rows[:at])
        assert trace.input("m") == pytest.approx(budget.dry_mass_kg + load - above, rel=1e-9), row.contributor
    assert load == pytest.approx(budget.total_propellant_kg, abs=0.1)  # the last iteration's load: converged


def test_every_input_names_its_source_and_a_parameter_its_value_in_effect():
    """Each input and intermediate has a unit and a source of a known kind;
    a parameter's input is the value in effect, and follows a project's
    configuration (the collision-avoidance margin set to 5)."""
    scenario = _every_contributor()
    scenario.configuration = Configuration({"propellant_budget.cam_count_factor": 5.0})
    budget = pb.compute_budget(scenario, "sat-1", reentry_solver=_no_reentry)
    for trace in _all_traces(budget):
        assert trace.unit and trace.reference and trace.equation, trace.quantity
        for quantity in trace.inputs + trace.intermediates:
            assert quantity.unit, (trace.quantity, quantity.symbol)
            kind = quantity.source.split(":", 1)[0]
            assert kind in SOURCE_KINDS, (trace.quantity, quantity.symbol, quantity.source)
            if kind == "parameter":
                name = quantity.source.split(": ", 1)[1]
                assert quantity.value == registry.value(name, scenario), name
    cam = next(r for r in budget.rows if r.contributor.startswith("Collision avoidance"))
    assert cam.delta_v_trace.input("f") == 5.0
    assert "parameter: propellant_budget.cam_count_factor" in [q.source for q in cam.delta_v_trace.inputs]
    assert cam.delta_v_trace.reference == "ESA AD10 Secs. 6.2.4, 5.6"


def test_a_flown_contributor_is_traced_to_the_runs_series():
    """In-plane control and formation keeping from a 10-day run, scaled to
    a year: the trace names the series, the run's value, the share of the
    tank and the scale."""
    result = ResultSet(scenario_name="r")
    t = np.array([0.0, 10.0 * 86400.0])  # [s]
    result.add(TimeSeries("sat-1.position_N", t, ("x", "y", "z"), np.zeros((2, 3))))
    result.add(TimeSeries("sat-1.station_keeping.delta_v", t, ("dv",), [0.0, 3.0]))
    result.add(TimeSeries("sat-1.phasing_keeping.delta_v", t, ("dv",), [0.0, 1.0]))
    result.add(TimeSeries("sat-1.station_keeping.propellant_remaining", t, ("kg",), [5.0, 4.96]))
    budget = pb.compute_budget(_scenario(PropellantBudgetConfig(mission_years=1.0)), "sat-1", result,
                               reentry_solver=_no_reentry)
    rows = {r.contributor: r for r in budget.rows}
    in_plane, formation = rows["In-plane orbit control"], rows["Constellation/formation keeping"]
    assert in_plane.delta_v_trace.equation == "dV = dV_run * k"
    assert in_plane.delta_v_trace.input("dV_run") == 3.0
    assert in_plane.delta_v_trace.input("k") == pytest.approx(36.525)
    assert [q.source for q in in_plane.delta_v_trace.inputs][0] == "last run: sat-1.station_keeping.delta_v"
    assert in_plane.propellant_trace.input("s") == pytest.approx(0.75)
    assert formation.propellant_trace.input("s") == pytest.approx(0.25)
    assert formation.delta_v_trace.inputs[0].source == "last run: sat-1.phasing_keeping.delta_v"
    for row in (in_plane, formation):
        for trace in (row.delta_v_trace, row.propellant_trace):
            assert trace.value == pytest.approx(_recomputed(trace), rel=1e-12)


def test_contributors_given_without_the_runs_series_are_still_traced():
    """A caller's own RunContributors (no series named): the trace gives
    the run's value and the scale, and says the series is not named."""
    flown = pb.RunContributors(run_days=1500.0, scale=1.1, in_plane=(50.0, 1.0))
    budget = pb.compute_budget(_scenario(PropellantBudgetConfig()), "sat-1", flown=flown, reentry_solver=_no_reentry)
    row = next(r for r in budget.rows if r.contributor == "In-plane orbit control")
    assert row.delta_v_trace.value == 50.0 and row.delta_v_trace.value == pytest.approx(_recomputed(row.delta_v_trace))
    assert row.delta_v_trace.inputs[0].source == "last run: as given, the series not named"
    assert row.propellant_trace.value == 1.0 == _recomputed(row.propellant_trace)


def test_an_estimated_contributor_names_its_model_and_inputs():
    """Without a run, a LEO station keeper's in-plane control is the drag
    make-up: its trace names the held altitude, the mission, the MSFC
    percentile parameter and the drag coefficient."""
    budget = pb.compute_budget(_scenario(PropellantBudgetConfig()), "sat-1", reentry_solver=_no_reentry,
                               makeup=_StubMakeup())
    trace = next(r for r in budget.rows if r.contributor == "In-plane orbit control").delta_v_trace
    assert trace.value == 100.0 and "engine.lifetime.drag_makeup" in trace.equation
    assert (trace.input("h"), trace.input("T"), trace.input("P"), trace.input("Cd")) == (400.0, 5.0, 95.0, 2.2)


@pytest.mark.requires_basilisk  # the budget command imports the run service
def test_the_traces_reach_the_budget_record_and_the_command_line(tmp_path, capsys):
    """The budget's JSON record carries each row's traces and the
    budget-wide ones as plain JSON, and ``budget --explain`` prints them."""
    from spacemissionstudio import cli
    from spacemissionstudio.engine import analysis_records

    scenario = _every_contributor()
    budget = pb.compute_budget(scenario, "sat-1", reentry_solver=_no_reentry)
    record = json.loads(json.dumps(analysis_records._plain(analysis_records.budget_record(scenario, "sat-1",
                                                                                          budget))))
    rows = record["results"]["rows"]
    assert rows[0]["delta_v_trace"]["equation"] == "dV = max(v * da / (2 a), v * de / 2)"
    assert rows[0]["delta_v_trace"]["reference"] == "ESA AD10 Sec. 6.1.1"
    assert rows[0]["propellant_trace"]["inputs"][1]["source"] == "trace: Effective exhaust speed"
    assert set(record["results"]["traces"]) == {"efficiency", "exhaust_speed", "dry_mass", "total_propellant"}

    path = tmp_path / "b.json"
    path.write_text(json.dumps(_every_contributor(disposal="graveyard").to_dict()), encoding="utf-8")
    assert cli.main(["budget", str(path), "--explain"]) == 0
    out = capsys.readouterr().out
    assert "How each number was computed:" in out
    assert "Collision avoidance (3 x 4): dV = " in out and "[ESA AD10 Secs. 6.2.4, 5.6]" in out
    assert "f = 4 [-]  margin on the count  (parameter: propellant_budget.cam_count_factor)" in out
    assert cli.main(["budget", str(path), "--explain", "--launch-delays"]) == 2


def test_a_trace_is_plain_data():
    """``to_dict`` is JSON and ``text`` its lines; ``input`` finds an input
    or an intermediate by its symbol."""
    from spacemissionstudio.engine.trace import Quantity

    trace = Trace("Thing", "x", 2.0, "[m]", "x = a * b", "ESA AD10 Sec. 1",
                  inputs=(Quantity("first", "a", 1.0, "[m]", "scenario: a"),),
                  intermediates=(Quantity("second", "b", 2.0, "[-]", "computed"),), notes=("n",))
    assert json.loads(json.dumps(trace.to_dict()))["inputs"][0]["source"] == "scenario: a"
    assert trace.text() == ["Thing: x = 2 [m]", "  x = a * b   [ESA AD10 Sec. 1]", "  inputs:",
                            "    a = 1 [m]  first  (scenario: a)", "  intermediates:", "    b = 2 [-]  second  (computed)",
                            "  note: n"]
    assert trace.input("b") == 2.0
    with pytest.raises(KeyError):
        trace.input("c")


# -- the orbital lifetime (engine.lifetime) -------------------------------------------------------

def _steep_lifetime_scenario():
    """Template 18's spacecraft with the exponential atmosphere: no
    space-weather file, a decay of a few hundred steps."""
    from pathlib import Path

    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    scenario = load_scenario(next(templates.glob("18_*.json")))
    scenario.space_weather.atmosphere_model = "exponential"
    return scenario


@pytest.mark.requires_basilisk
def test_every_lifetime_figure_is_recomputed_from_its_trace():
    """The mass, the ballistic coefficient, the perigee, the deorbit burn
    and each disposal rule's verdict follow from their traces' inputs; the
    lifetime is the decay run again with the trace's ballistic coefficient
    and parameters."""
    from spacemissionstudio.engine import lifetime

    scenario = _steep_lifetime_scenario()
    name = scenario.spacecraft[0].name
    end = lifetime.end_of_life(scenario, name, deorbit_perigee_km=200.0, max_years=5.0)
    traces = end.traces
    assert set(traces) == {"orbit", "deorbit", "mass", "ballistic_coefficient", "lifetime",
                           *(key for _y, _l, key in lifetime.disposal_rules(scenario))}
    mass = traces["mass"]
    assert mass.value == end.mass_kg == pytest.approx(mass.input("m_dry") + mass.input("m_p") - mass.input("m_burn"))
    b = traces["ballistic_coefficient"]
    assert b.value == end.ballistic_coefficient_m2_kg == pytest.approx(b.input("Cd") * b.input("A") / b.input("m"))
    orbit = traces["orbit"]
    assert orbit.value == pytest.approx(orbit.input("a") * (1.0 - orbit.input("e")) / 1e3 - orbit.input("R") / 1e3)
    burn = traces["deorbit"]
    mu, r_a, a = burn.input("mu"), burn.input("r_a"), burn.input("a")
    a_new = 0.5 * (r_a + constants.EARTH_EQUATORIAL_RADIUS_M + burn.input("h_p'") * 1e3)  # [m]
    assert burn.value == end.deorbit.delta_v_m_s == pytest.approx(
        math.sqrt(mu * (2.0 / r_a - 1.0 / a)) - math.sqrt(mu * (2.0 / r_a - 1.0 / a_new)), rel=1e-12)
    assert burn.input("m_burn") == pytest.approx(
        burn.input("m") * (1.0 - math.exp(-burn.value / (burn.input("Isp") * burn.input("g0")))), rel=1e-12)
    life = traces["lifetime"]
    assert life.value == end.lifetime.lifetime_years and life.input("B") == b.value
    for symbol, parameter in (("h_re", "reentry_altitude_km"), ("n", "ring_points"), ("dt_max", "max_step_s"),
                              ("f", "max_perigee_drop_fraction")):
        assert life.input(symbol) == registry.value(f"lifetime.{parameter}", scenario)
    from spacemissionstudio.engine.service import _orbit_ic_to_rv

    r_m, v_m_s = _orbit_ic_to_rv(lifetime.MU_EARTH_M3_S2, scenario.spacecraft[0].orbit, scenario.epoch_utc)
    _dv, _kg, lowered = lifetime.deorbit_burn(lifetime.mean_orbit_from_state(r_m, v_m_s), 200.0,
                                              burn.input("m"), burn.input("Isp"))
    again = lifetime.propagate_decay(lowered, end.lifetime.start_utc, life.input("B"), lifetime.exponential_density,
                                     life.input("T"), scenario=scenario)
    assert again.lifetime_years == life.value
    for years, _label, key in lifetime.disposal_rules(scenario):
        rule = traces[key]
        assert rule.input("T") == years
        assert rule.value == ("met" if rule.input("reentered") and rule.input("L") <= rule.input("T") else "not met")
    for trace in traces.values():
        for quantity in trace.inputs + trace.intermediates:
            assert quantity.source.split(":", 1)[0] in SOURCE_KINDS, (trace.quantity, quantity.source)


@pytest.mark.requires_basilisk
def test_a_decay_reaching_the_ground_within_a_step_re_enters():
    """A decay never steps less than an orbit. In the exponential
    atmosphere, after a burn to a 200 km perigee, the drag under the
    ground blew the orbit up within a step (an eccentricity of 6e26) and
    the estimate raised. It now re-enters within that step and says so."""
    from spacemissionstudio.engine import lifetime

    scenario = _steep_lifetime_scenario()
    end = lifetime.end_of_life(scenario, scenario.spacecraft[0].name, deorbit_perigee_km=200.0, max_years=5.0)
    assert end.lifetime.reentered and 0.0 < end.lifetime.lifetime_years < 5.0
    assert end.lifetime.perigee_altitude_km[-1] == 0.0
    assert any("reached the ground within the last step" in w for w in end.lifetime.warnings)


@pytest.mark.requires_basilisk
def test_the_lifetime_traces_reach_the_record_and_the_command_line(tmp_path, capsys):
    """``lifetime --out`` writes the traces, ``lifetime --explain`` prints
    them."""
    from spacemissionstudio import cli
    from spacemissionstudio.engine import analysis_records, lifetime

    scenario = _steep_lifetime_scenario()
    name = scenario.spacecraft[0].name
    end = lifetime.end_of_life(scenario, name, max_years=1.0)
    record = json.loads(json.dumps(analysis_records._plain(
        analysis_records.lifetime_record(scenario, name, end, 1.0, 50.0, None, None))))
    traces = record["results"]["traces"]
    assert traces["ballistic_coefficient"]["equation"] == "B = Cd * A / m"
    assert traces["lifetime"]["inputs"][0]["source"] == "parameter: lifetime.reentry_altitude_km"
    path = tmp_path / "l.json"
    path.write_text(json.dumps(scenario.to_dict()), encoding="utf-8")
    assert cli.main(["lifetime", str(path), "--max-years", "1", "--explain"]) == 0
    out = capsys.readouterr().out
    assert "How each figure was computed:" in out and "Ballistic coefficient: B = " in out
    assert "Cd = 2.2 [-]  drag coefficient  (option: the drag coefficient asked for" in out


# -- the RF link budget (engine.link_budget) ------------------------------------------------------

def _link(pattern="fixed", **extra):
    from spacemissionstudio.schema.scenario import GroundStationConfig, RFLinkConfig

    settings = dict(tx_power_w=2.0, frequency_hz=8.2e9, data_rate_bps=50e6, tx_antenna_gain_dbi=6.0,
                    implementation_loss_db=2.0, required_ebno_db=4.5, antenna_pattern=pattern)  # [W], [Hz], ...
    settings.update(extra)
    station = GroundStationConfig(name="gs", latitude_deg=52.5, longitude_deg=13.4, altitude_m=34.0,
                                  min_elevation_deg=10.0, rx_antenna_gain_dbi=45.0, system_noise_temp_k=150.0)
    return RFLinkConfig(**settings), station


_LINK_EQUATIONS = {
    "EIRP = 10 log10(P_tx) + G_tx - L_impl":
        lambda t: 10.0 * math.log10(t.input("P_tx")) + t.input("G_tx") - t.input("L_impl"),
    "FSPL = 20 log10(4 pi r f / c)": lambda t: 20.0 * math.log10(4.0 * math.pi * t.input("r") * t.input("f") / t.input("c")),
    "L_point = min(L_max, k (theta / theta_3dB)^2)  (0 at theta = 0)":
        lambda t: min(t.input("L_max"), t.input("k") * (t.input("theta") / t.input("theta_3dB")) ** 2),
    "L_point = 0": lambda t: 0.0,
    "L_point = G_tx - G(theta)": lambda t: t.input("G_tx") - t.input("G(theta)"),
    "C = EIRP - FSPL - L_point + G_rx": lambda t: t.input("EIRP") - t.input("FSPL") - t.input("L_point") + t.input("G_rx"),
    "N0 = 10 log10(k_B) + 10 log10(T_sys)": lambda t: t.input("10 log10(k_B)") + 10.0 * math.log10(t.input("T_sys")),
    "C/N0 = C - N0": lambda t: t.input("C") - t.input("N0"),
    "Eb/N0 = C/N0 - 10 log10(R_b)": lambda t: t.input("C/N0") - 10.0 * math.log10(t.input("R_b")),
    "M = Eb/N0 - (Eb/N0)_req": lambda t: t.input("Eb/N0") - t.input("(Eb/N0)_req"),
    "closes: M >= M_req": lambda t: "yes" if t.input("M") >= t.input("M_req") else "no",
}


@pytest.mark.parametrize("pattern, extra, angle", [("fixed", {}, 0.0), ("fixed", {"antenna_beamwidth_deg": 20.0}, 7.0),
                                                   ("cosine", {}, 35.0)])
def test_every_link_figure_is_recomputed_from_its_trace(pattern, extra, angle):
    """EIRP, path loss, pointing loss, received power, noise density, C/N0,
    Eb/N0, margin and the verdict each follow from their trace's inputs, and
    equal the breakdown the run and the dashboard use."""
    from spacemissionstudio.engine import link_budget

    rf_link, station = _link(pattern, **extra)
    traces = link_budget.link_budget_traces(2.1e6, rf_link, station, angle)
    breakdown = link_budget.link_budget_breakdown(2.1e6, rf_link, station, angle)
    for key, field_name in (("eirp", "eirp_dbw"), ("fspl", "fspl_db"), ("pointing_loss", "pointing_loss_db"),
                            ("received", "received_dbw"), ("n0", "n0_dbw_hz"), ("cn0", "cn0_db_hz"),
                            ("ebno", "ebno_db"), ("margin", "margin_db")):
        assert traces[key].value == getattr(breakdown, field_name), key
    for key, trace in traces.items():
        assert trace.equation in _LINK_EQUATIONS, (key, trace.equation)
        expected = _LINK_EQUATIONS[trace.equation](trace)
        assert trace.value == (expected if isinstance(expected, str) else pytest.approx(expected, rel=1e-12, abs=1e-12)), key
        for quantity in trace.inputs + trace.intermediates:
            assert quantity.source.split(":", 1)[0] in SOURCE_KINDS, (key, quantity.source)
    if pattern == "cosine":
        assert traces["pointing_loss"].value > 0.0


def test_the_link_verdict_follows_the_projects_required_margin():
    """The verdict's required margin is the parameter in effect: the same
    link closes at the default 0 dB and not at 30 dB."""
    from types import SimpleNamespace

    from spacemissionstudio.engine import link_budget

    rf_link, station = _link()
    default = link_budget.link_budget_traces(2.1e6, rf_link, station)["closes"]
    strict = link_budget.link_budget_traces(2.1e6, rf_link, station, scenario=SimpleNamespace(
        configuration=Configuration({"link.required_margin_db": 30.0})))["closes"]
    assert (default.value, default.input("M_req")) == ("yes", 0.0)
    assert (strict.value, strict.input("M_req")) == ("no", 30.0)
    assert strict.inputs[1].source == "parameter: link.required_margin_db"


def test_the_longest_range_of_a_pass_is_at_the_minimum_elevation():
    """rho = sqrt(r^2 - (R cos eps)^2) - R sin eps: overhead it is the
    height, and it satisfies the triangle's law of cosines at 10 deg."""
    from spacemissionstudio.engine import link_budget

    _rf, station = _link()
    radius = constants.EARTH_EQUATORIAL_RADIUS_M + station.altitude_m  # [m]
    a_m = constants.EARTH_EQUATORIAL_RADIUS_M + 550e3  # [m]
    assert link_budget.slant_range_at_elevation_m(a_m, station, 90.0) == pytest.approx(a_m - radius)
    rho = link_budget.slant_range_at_elevation_m(a_m, station)  # [m] at the station's 10 deg
    assert a_m ** 2 == pytest.approx(radius ** 2 + rho ** 2 + 2.0 * radius * rho * math.sin(math.radians(10.0)))


def test_the_link_budget_command_explains_and_records(tmp_path, capsys, monkeypatch):
    """``link-budget`` prints the figures at the minimum-elevation range,
    ``--explain`` their traces and ``--out`` the record; it needs no
    Basilisk; a spacecraft without a link is refused."""
    import builtins

    from spacemissionstudio import cli

    real_import = builtins.__import__

    def no_basilisk(name, *args, **kwargs):
        if name.startswith("Basilisk"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_basilisk)
    template = (Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
                / "26_earth_observation_data_downlink.json")
    out = tmp_path / "link.json"
    assert cli.main(["link-budget", str(template), "--explain", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "eo-sat to berlin-gs, at 1,815.3 km, the slant range at 10 deg elevation:" in printed
    assert "How each figure was computed:" in printed and "[the link equation" in printed
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["kind"] == "link_budget" and record["results"]["closes"] == "yes"
    assert record["results"]["traces"]["fspl"]["inputs"][0]["source"].startswith("computed: rho = sqrt")
    assert record["model"]["rules"]["link.required_margin_db"] == 0.0
    assert cli.main(["link-budget", str(template), "--spacecraft", "nobody"]) == 3


# -- the run's headline figures (engine.run_summary) ----------------------------------------------

def _summary_traces(result):
    from spacemissionstudio.engine import run_summary

    figures = run_summary.summarize(result)
    assert figures and all(f.trace is not None for f in figures), [f.key for f in figures if f.trace is None]
    return run_summary.by_key(figures)


def _sum_of(trace, prefix):
    return sum(q.value for q in trace.inputs if q.symbol.startswith(prefix))


_SUMMARY_EQUATIONS = {
    "T = t_end / 3600": lambda t: t.input("t_end") / 3600.0,
    "dV = sum of each controller's cumulative delta-V at the end": lambda t: _sum_of(t, "dV_"),
    "m = sum over the tanks of (m0 - m1)": lambda t: _sum_of(t, "m0_") - _sum_of(t, "m1_"),
    "M_min = min of M while a station is in view": lambda t: t.input("M"),
    "E_min = min of E over the run": lambda t: t.input("E"),
    "N = number of passes over every station": lambda t: _sum_of(t, "N_"),
    "T_c = sum of the passes' durations / 60": lambda t: _sum_of(t, "T_") / 60.0,
    "N = N_umbra + N_penumbra": lambda t: t.input("N_umbra") + t.input("N_penumbra"),
    "T_e = sum of the eclipses' durations / 60": lambda t: t.input("T") / 60.0,
    "D = D_end / 1e9": lambda t: t.input("D_end") / 1e9,
}


def test_every_headline_figure_is_recomputed_from_its_trace():
    """Each figure of a run's summary (Results > Overview) equals what its
    trace's equation gives from the trace's own inputs, and each series its
    trace names is one the run recorded."""
    from test_run_summary import _run

    result = _run()
    figures = _summary_traces(result)
    assert set(figures) == {"run_length", "sat.delta_v", "sat.propellant_used", "sat.mean_sma_change",
                            "sat.lowest_link_margin", "sat.lowest_battery_charge", "sat.passes", "sat.contact_time",
                            "sat.eclipses", "sat.eclipse_time", "sat.data_downlinked"}
    for key, figure in figures.items():
        trace = figure.trace
        assert trace.value == figure.value, key
        if key == "sat.mean_sma_change":
            continue
        assert trace.equation in _SUMMARY_EQUATIONS, (key, trace.equation)
        assert _SUMMARY_EQUATIONS[trace.equation](trace) == pytest.approx(figure.value, rel=1e-12, abs=1e-12), key
        for quantity in trace.inputs + trace.intermediates:
            if quantity.source.startswith("last run: "):
                series = quantity.source[len("last run: "):].split(",")[0]
                assert series in result.series, (key, series)
    assert figures["sat.delta_v"].trace.input("dV_station_keeping") == 1.5  # [m/s]
    assert figures["sat.delta_v"].trace.input("dV_constant_thrust") == 0.25  # [m/s]
    assert figures["sat.lowest_link_margin"].trace.inputs[0].source == \
        "last run: gs.access_to_sat.link_margin_db, at t = 3600 s"
    assert figures["sat.eclipses"].trace.input("N_umbra") == 1


def test_the_semi_major_axis_change_is_recomputed_from_its_trace():
    """The window is N orbits of the median semi-major axis about the
    central body; the change is the last window's mean less the first's.
    The central body's GM is the run's own when it recorded one, else
    Earth's, and the trace says which."""
    from test_run_summary import _run

    from spacemissionstudio.engine.results import RunProvenance

    trace = _summary_traces(_run())["sat.mean_sma_change"].trace
    assert trace.inputs[0].source == "parameter: results.sma_window_orbits" and trace.input("N") == 1.0
    assert trace.inputs[1].source == "constant: EARTH_GM_M3_S2 (the run recorded no provenance)"
    assert trace.input("mu") == constants.EARTH_GM_M3_S2
    window = trace.input("N") * 2.0 * math.pi * math.sqrt(trace.input("a_med") ** 3 / trace.input("mu"))  # [s]
    assert trace.input("window") == pytest.approx(window, rel=1e-15)
    assert trace.value == pytest.approx((trace.input("a_last") - trace.input("a_first")) / 1000.0, rel=1e-15)

    mu_mars, a = 4.282837e13, 3789.5e3  # [m^3/s^2], [m]
    t = np.arange(0.0, 3.0 * 2.0 * math.pi * math.sqrt(a ** 3 / mu_mars), 30.0)  # [s] three orbits
    provenance = RunProvenance(spacemissionstudio_version="test", basilisk_version="test", run_started_utc="-",
                               integrator="rkf78", dynamics_task_rate_s=30.0, central_body="mars barycenter",
                               central_body_mu_m3_s2=mu_mars)
    mars = ResultSet("mars", provenance=provenance)
    mars.add(TimeSeries("probe.position_N", t, ("x", "y", "z"), np.zeros((t.size, 3)), "m"))
    mars.add(TimeSeries("probe.orbit_elements_mean.semi_major_axis", t, ("semi_major_axis",),
                        (a - 0.2 * t).reshape(-1, 1), "m"))
    trace = _summary_traces(mars)["probe.mean_sma_change"].trace
    assert trace.input("mu") == mu_mars and trace.inputs[1].source == "last run: provenance central_body_mu_m3_s2"


def test_the_run_command_explains_its_headline_figures(tmp_path, capsys):
    """``run --explain`` prints each headline figure and how it was
    computed after the run's files; without it, nothing more is printed."""
    import argparse

    from test_run_summary import _run

    from spacemissionstudio import cli
    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    scenario = load_scenario(next(templates.glob("18_*.json")))
    args = argparse.Namespace(out_dir=tmp_path / "plain", oem=False)
    cli._write_run_outputs(args, scenario, _run(), None)
    assert "Headline figures" not in capsys.readouterr().out
    args = argparse.Namespace(out_dir=tmp_path / "explained", oem=False, explain=True)
    cli._write_run_outputs(args, scenario, _run(), None)
    printed = capsys.readouterr().out
    assert "Headline figures, and how each was computed:" in printed
    assert "Delta-V: 1.750 m/s\n  Delta-V: dV = 1.75 [m/s]\n" in printed
    assert "dV_station_keeping = 1.5 [m/s]" in printed and "(last run: sat.station_keeping.delta_v" in printed
    assert cli.build_parser().parse_args(["run", "s.json", "--explain"]).explain


# -- the events (engine.events) -------------------------------------------------------------------

def _every_kind_of_event():
    """A run with a pass, eclipses, station-keeping and GEO burns, phasing
    burns and drift, a thruster firing, comms modes and a downlink."""
    t = np.arange(12, dtype=float) * 60.0  # [s]
    result = ResultSet("events")

    def add(name, columns, data, units=""):
        result.add(TimeSeries(name, t, columns, np.asarray(data, dtype=float).reshape(t.size, -1), units))

    add("gs.access_to_sat.has_access", ("has_access",), [0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1])
    add("gs.access_to_sat.elevation", ("elevation",), np.radians([0, 5, 30, 50, 10, 0, 0, 0, 3, 8, 12, 9]), "rad")
    add("gs.access_to_sat.link_closed", ("link_closed",), [0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0])
    add("sat.data_handling.data_downlinked", ("data_downlinked",),
        [0, 0, 1e9, 2.5e9, 2.5e9, 2.5e9, 2.5e9, 2.5e9, 2.5e9, 3e9, 3.5e9, 3.5e9], "bit")
    add("sat.eclipse.illumination_factor", ("illumination_factor",), [1, 1, 0.5, 0, 0, 1, 1, 0.3, 1, 1, 1, 1])
    add("sat.station_keeping.burn_on", ("burn_on",), [0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0])
    add("sat.station_keeping.delta_v", ("cumulative_delta_v",), [0, 0, 0, 0, 0.4, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
        "m/s")
    burn = np.zeros((12, 2))
    burn[2, 0] = burn[6:8, 1] = 1
    add("geo.geo_station_keeping.burn_on", ("east_west", "north_south"), burn)
    add("geo.geo_station_keeping.north_south.delta_v", ("cumulative_delta_v",), np.linspace(0.0, 2.2, 12), "m/s")
    add("f1.phasing_keeping.state", ("state",), [0, 1, 1, 2, 2, 2, 3, 0, 0, 0, 0, 0])
    on_time = np.zeros((12, 2))  # [s]
    on_time[4, 1] = 0.2
    add("sat.thruster_on_time", ("thruster_0", "thruster_1"), on_time, "s")
    add("sat.comms_pointing.active_mode", ("active_mode",), [0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1])
    return result


def test_every_event_is_found_again_from_its_trace():
    """Each event's span follows from its trace: the first and last samples
    where its rule is true, with the samples either side false; each value
    it carries (delta-V, data, elevation, sunlight) is what its trace's
    equation gives from the trace's inputs; every series named was recorded."""
    from spacemissionstudio.engine import events

    result = _every_kind_of_event()
    found = events.extract_events(result)
    assert {e.kind for e in found} == set(events.KINDS)
    for event in found:
        traces = events.trace_of(result, event)
        span = traces[0]
        assert (span.input("t_start"), span.input("t_end")) == (event.start_s, event.end_s), event
        assert span.value == span.input("t_end") - span.input("t_start") == event.duration_s, event
        for quantity in span.intermediates:
            if quantity.symbol == "t_before":
                assert quantity.value < event.start_s
            elif quantity.symbol == "t_after":
                assert quantity.value > event.end_s
            else:  # a value the event carries, opened from the span
                linked = next(t for t in traces[1:] if f"trace: {t.quantity}" == quantity.source)
                assert quantity.value == linked.value
        for trace in traces:
            for quantity in trace.inputs + trace.intermediates:
                if quantity.source.startswith("last run: "):
                    assert quantity.source[len("last run: "):].split(",")[0] in result.series, quantity.source
        values = {t.symbol: t for t in traces[1:]}
        if "dV" in values:
            dv = values["dV"]
            assert dv.value == dv.input("dV_after") - dv.input("dV_before") == event.quantity("delta_v")
        if "D" in values:
            d = values["D"]
            assert d.value == (d.input("D_end") - d.input("D_before")) / 1e9 == event.quantity("data")
        if "el_max" in values:
            assert values["el_max"].value == math.degrees(values["el_max"].input("el")) == event.quantity("max_elevation")
        if "f_min" in values:
            f = values["f_min"]
            assert f.value == f.input("f") * 100.0 == event.quantity("lowest_sunlight")
            assert event.label == f"eclipse ({'umbra' if f.input('f') < f.input('u') else 'penumbra'})"
            assert f.inputs[1].source == "parameter: results.umbra_sunlight_fraction"
        expected = {"delta_v": "dV", "data": "D", "max_elevation": "el_max", "lowest_sunlight": "f_min"}
        assert {expected[key] for key, _value in event.quantities} == set(values), event


def test_an_event_trace_states_its_rule_and_samples():
    """A station-keeping burn's trace names the series and rule, the samples
    either side, and reads the delta-V between the samples outside it."""
    from spacemissionstudio.engine import events

    result = _every_kind_of_event()
    burn = next(e for e in events.extract_events(result) if e.label == "station-keeping burn")
    span, delta_v = events.trace_of(result, burn)
    assert span.quantity == "station-keeping burn (sat)" and span.value == 60.0
    assert span.equation.startswith("on where burn_on != 0;")
    assert span.inputs[0].source == "last run: sat.station_keeping.burn_on, sample 3 (t = 180 s)"
    assert span.input("t_before") == 120.0 and span.input("t_after") == 300.0
    assert delta_v.input("dV_before") == 0.0 and delta_v.input("dV_after") == 0.9  # [m/s] samples 2 and 5
    assert span.intermediates[-1].source == "trace: Delta-V" and span.input("dV") == delta_v.value
    sun = next(e for e in events.extract_events(result) if e.label == "Sun pointing")
    assert events.trace_of(result, sun)[0].equation.startswith("on where active_mode <= 0.5;")
    with pytest.raises(KeyError):
        events.trace_of(ResultSet("empty"), burn)


# -- the data totals (engine.data_budget) and the power at the time cursor (engine.power_state) -----

def test_each_data_total_is_read_from_the_ledger_at_its_last_sample():
    """Generated, downlinked, lost and on board: each trace names its ledger
    series and last sample and gives the budget's number; the memory was
    full exactly when data was lost."""
    from test_data_handling import _synthetic_result

    from spacemissionstudio.engine import data_budget

    result = _synthetic_result()
    (budget,) = data_budget.budgets(result)
    traces = budget.traces
    assert set(traces) == {"data_generated", "data_downlinked", "data_lost", "stored_end", "capacity_full"}
    for key, value in (("data_generated", budget.generated), ("data_downlinked", budget.downlinked),
                       ("data_lost", budget.lost), ("stored_end", budget.stored_end)):
        trace = traces[key]
        name = trace.inputs[0].source[len("last run: "):].split(",")[0]
        series = result.series[name]
        column = list(series.columns).index("total") if key == "stored_end" else 0
        assert trace.value == trace.inputs[0].value == value == float(series.data[-1, column]), key
        assert trace.inputs[0].source.startswith(f"last run: {name}, its last sample {series.time_s.size - 1} ")
    assert traces["capacity_full"].value == ("yes" if traces["data_lost"].value > 0 else "no") == "no"


def test_the_run_command_explains_the_data_totals(tmp_path, capsys):
    import argparse

    from test_data_handling import _synthetic_result

    from spacemissionstudio import cli
    from spacemissionstudio.schema import load_scenario

    templates = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates"
    scenario = load_scenario(next(templates.glob("26_*.json")))
    cli._write_run_outputs(argparse.Namespace(out_dir=tmp_path, oem=False, explain=True), scenario,
                           _synthetic_result(), None)
    printed = capsys.readouterr().out
    assert "Data handling of sat, and how each total was read:" in printed
    assert "  Data generated: G = 90000000 [bit]" in printed
    assert "(last run: sat.data_handling.data_generated, its last sample 9 (t = 90 s))" in printed


def _battery_run():
    t = np.arange(6, dtype=float) * 60.0  # [s]
    result = ResultSet("power")
    result.add(TimeSeries("sat.battery_charge", t, ("charge",), np.array([40.0, 38.0, 35.0, 36.0, 39.0, 41.0])[:, None],
                          "W*hr"))
    result.add(TimeSeries("sat.battery_net_power", t, ("net_power",),
                          np.array([-5.0, -6.0, 2.0, 3.0, 4.0, 1.0])[:, None], "W"))
    return result


def test_the_power_at_the_time_cursor_is_read_from_the_battery_series():
    """At a cursor between samples the last sample at or before it is read;
    the state of charge is 100 E / E_cap held to 0..100 and opens the charge;
    without a capacity there is no state of charge; without the cursor, the
    run's end."""
    from spacemissionstudio.engine import power_state

    result = _battery_run()
    traces = power_state.battery_traces(result, "sat", capacity_wh=50.0, at_s=150.0)  # [W*h], [s]
    assert traces["charge"].value == 35.0 and traces["net_power"].value == 2.0  # sample 2 (t = 120 s)
    assert traces["charge"].inputs[0].source.startswith("last run: sat.battery_charge, sample 2 (t = 120 s)")
    soc = traces["state_of_charge"]
    assert soc.value == 100.0 * soc.input("E") / soc.input("E_cap") == 70.0  # [%]
    assert soc.inputs[0].source == "trace: Battery charge"
    assert soc.inputs[1].source == "scenario: spacecraft.power.battery_capacity_wh"
    assert power_state.battery_traces(result, "sat", capacity_wh=30.0)["state_of_charge"].value == 100.0  # held
    assert "state_of_charge" not in power_state.battery_traces(result, "sat")
    end = power_state.battery_traces(result, "sat")
    assert end["charge"].value == 41.0 and "the last at or before the end of the run" in end["charge"].inputs[0].source
    assert power_state.battery_traces(ResultSet("none"), "sat") == {}


# -- the mean orbital elements (engine.mean_elements) ----------------------------------------------

def _mean_element_run(inclinations_deg, mean_a_m):
    t = np.arange(len(inclinations_deg), dtype=float) * 60.0  # [s]
    result = ResultSet("mean")
    result.add(TimeSeries("sat.orbit_elements.inclination", t, ("i",), np.radians(inclinations_deg)[:, None], "rad"))
    result.add(TimeSeries("sat.orbit_elements_mean.semi_major_axis", t, ("a",), np.asarray(mean_a_m)[:, None], "m"))
    return result


def test_the_mean_elements_trace_names_the_map_its_constants_and_bands():
    """The trace gives the radius and J2 (the one set of constants), the two
    bands, and counts the samples in each band and those with no closed
    orbit; a run without mean elements has none."""
    from spacemissionstudio.engine import mean_elements

    result = _mean_element_run([97.4, 63.0, 63.5, 64.8, 0.5, 179.6, 45.0],
                               [7e6, 7e6, 7e6, 7e6, 7e6, np.nan, 7e6])  # [deg], [m]
    trace = mean_elements.series_trace(result, "sat")
    assert trace.quantity == "Mean orbital elements (sat)" and trace.value == "first-order J2 mean"
    assert trace.input("R_eq") == constants.EARTH_EQUATORIAL_RADIUS_M and trace.input("J2") == constants.EARTH_J2
    assert trace.input("b_crit") == trace.input("b_eq") == 1.0  # [deg]
    assert (trace.input("n_crit"), trace.input("n_eq"), trace.input("n_none")) == (2, 2, 1)
    assert trace.inputs[0].value == "7 samples"
    assert mean_elements.series_trace(ResultSet("none"), "sat") is None


@pytest.mark.requires_basilisk
def test_the_mean_elements_trace_states_the_runs_own_map():
    """The radius and J2 the trace names are the run's (Basilisk's Earth
    radEquator and J2_EARTH), and the map with them gives what the run
    records, in the critical band, the equatorial band and elsewhere."""
    from Basilisk.utilities import orbitalMotion, simIncludeGravBody

    from spacemissionstudio.engine import mean_elements
    from spacemissionstudio.engine.service import _mean_elements

    trace = mean_elements.series_trace(_mean_element_run([60.0], [7e6]), "sat")
    earth = simIncludeGravBody.gravBodyFactory().createEarth()
    assert trace.input("R_eq") == earth.radEquator and trace.input("J2") == orbitalMotion.J2_EARTH
    inclinations = np.radians([97.4, 63.2, 0.4])  # [rad] elsewhere, critical band, equatorial band
    oe = {"a": np.full(3, 6.978e6), "e": np.full(3, 1e-3), "i": inclinations, "raan": np.full(3, 0.3),
          "argp": np.full(3, 0.2), "true_anomaly": np.full(3, 1.0)}
    recorded = _mean_elements(oe, earth.radEquator, orbitalMotion.J2_EARTH)
    for k in range(3):
        osc, mean = orbitalMotion.ClassicElements(), orbitalMotion.ClassicElements()
        osc.a, osc.e, osc.i, osc.Omega, osc.omega, osc.f = (oe["a"][k], oe["e"][k], oe["i"][k], oe["raan"][k],
                                                             oe["argp"][k], oe["true_anomaly"][k])
        mean_elements.cl_mean_osc_map(trace.input("R_eq"), trace.input("J2"), osc, mean, -1)
        assert mean.a == recorded["a"][k] and mean.i == recorded["i"][k], k


def test_the_semi_major_axis_change_opens_how_the_mean_elements_were_made():
    """The headline figure's trace links the mean elements' trace (Open in
    the panel; printed after it by run --explain)."""
    from spacemissionstudio.engine import run_summary

    t = np.arange(0.0, 3.0 * 5740.0, 60.0)  # [s] three orbits
    result = ResultSet("sma")
    result.add(TimeSeries("sat.position_N", t, ("x", "y", "z"), np.zeros((t.size, 3)), "m"))
    result.add(TimeSeries("sat.orbit_elements.inclination", t, ("i",), np.full((t.size, 1), np.radians(97.4)), "rad"))
    result.add(TimeSeries("sat.orbit_elements_mean.semi_major_axis", t, ("a",),
                          (6928e3 - 0.5e3 * t / t[-1])[:, None], "m"))
    figure = run_summary.by_key(run_summary.summarize(result))["sat.mean_sma_change"]
    (made,) = figure.related
    assert made.quantity == "Mean orbital elements (sat)"
    assert figure.trace.intermediates[-1].source == "trace: Mean orbital elements (sat)"
    lines = run_summary.explain_lines([figure])
    assert any(line.startswith("  Mean orbital elements (sat): mean = first-order J2 mean") for line in lines)
