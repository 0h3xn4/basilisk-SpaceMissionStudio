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
