#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""Chained inputs (transparency plan, Phase 8b): what the lifetime and the
budget take from the last run, shown before they compute, from the same
functions they use; a scenario changed since the run is said; the
lifetime's starting propellant is edited before computing and recorded
so."""

import copy
from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import chained_inputs
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.schema import load_scenario

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"


def _tank_run():
    """Template 17 (300 kg dry, 0.5 kg in its tank) after a one-minute run
    that left 0.1 kg."""
    from spacemissionstudio.engine import lifetime
    from spacemissionstudio.engine.service import _orbit_ic_to_rv

    scenario = load_scenario(_TEMPLATES / "17_fuel_tank_depletion.json")
    r_m, v_m_s = _orbit_ic_to_rv(lifetime.MU_EARTH_M3_S2, scenario.spacecraft[0].orbit, scenario.epoch_utc)
    result = ResultSet(scenario_name=scenario.name)
    t = np.array([0.0, 60.0])  # [s]
    result.add(TimeSeries("sat-1.position_N", t, ("x", "y", "z"), np.array([r_m, r_m])))
    result.add(TimeSeries("sat-1.velocity_N", t, ("x", "y", "z"), np.array([v_m_s, v_m_s])))
    result.add(TimeSeries("sat-1.fuel_mass_remaining", t, ("fuel_mass_remaining",), np.array([[0.5], [0.1]])))
    return scenario, result, (r_m, v_m_s)


@pytest.mark.requires_basilisk
def test_the_lifetime_shows_the_state_and_propellant_it_will_start_from():
    """The run's last state (its time, the mean perigee and apogee and the
    inclination of lifetime's own mean elements) and the tank's 0.1 kg left,
    each with where it came from: what end_of_life starts from."""
    from spacemissionstudio.engine import lifetime

    scenario, result, (r_m, v_m_s) = _tank_run()
    shown = {q.name: q for q in chained_inputs.lifetime_inputs(scenario, result, "sat-1")}
    orbit = lifetime.mean_orbit_from_state(r_m, v_m_s)
    assert shown["mean perigee height"].value == pytest.approx(orbit.perigee_altitude_km)
    assert shown["mean apogee height"].unit == "[km]" and shown["mean inclination"].unit == "[deg]"
    assert shown["fuel tank's propellant"].value == pytest.approx(0.1)
    assert shown["fuel tank's propellant"].source == "last run: sat-1.fuel_mass_remaining, last value"
    assert shown["time of the state"].value.endswith("UTC") and "0.001 days" in shown["time of the state"].source
    state = lifetime.start_state(scenario, "sat-1", result)
    assert state.tank_kg == pytest.approx(0.1) and state.from_end_of_run
    with pytest.raises(lifetime.LifetimeError, match="no spacecraft"):
        chained_inputs.lifetime_inputs(scenario, result, "nobody")


@pytest.mark.requires_basilisk
def test_the_lifetimes_propellant_is_edited_before_computing():
    """propellant_kg replaces the orbit thruster's propellant at the start:
    the mass and its trace say so; a negative one is refused."""
    from spacemissionstudio.engine import lifetime

    scenario = load_scenario(_TEMPLATES / "18_leo_station_keeping.json")
    name = scenario.spacecraft[0].name
    plain = lifetime.end_of_life(scenario, name, max_years=0.5)
    edited = lifetime.end_of_life(scenario, name, max_years=0.5, propellant_kg=7.5)
    before = lifetime.start_state(scenario, name).propellant_kg
    assert edited.mass_kg == pytest.approx(plain.mass_kg - before + 7.5)  # [kg]
    m_p = next(q for q in edited.traces["mass"].inputs if q.symbol == "m_p")
    assert (m_p.value, m_p.source) == (7.5, "option: edited before computing (the End of Life page)")
    with pytest.raises(lifetime.LifetimeError, match=">= 0 kg"):
        lifetime.end_of_life(scenario, name, max_years=0.5, propellant_kg=-1.0)


def test_the_budget_shows_what_the_run_flew_scaled_to_the_mission():
    """The run's length, its scale to the mission, and the in-plane orbit
    control it flew (delta-V and propellant over the mission)."""
    t = np.array([0.0, 86400.0])  # [s] one day
    result = ResultSet(scenario_name="budget")
    result.add(TimeSeries("sat.position_N", t, ("x", "y", "z"), np.zeros((2, 3))))
    result.add(TimeSeries("sat.station_keeping.delta_v", t, ("delta_v",), np.array([[0.0], [0.02]])))
    result.add(TimeSeries("sat.station_keeping.propellant_remaining", t, ("kg",), np.array([[5.0], [4.99]])))
    shown = {q.name: q for q in chained_inputs.budget_inputs(result, "sat", 5.0)}
    scale = 5.0 * 365.25  # [-] five years over one day
    assert shown["run length"].value == 1.0 and shown["scale to the mission"].value == pytest.approx(scale)
    assert shown["in-plane orbit control, delta-V"].value == pytest.approx(0.02 * scale)
    assert shown["in-plane orbit control, propellant"].value == pytest.approx(0.01 * scale)
    assert "sat.station_keeping.delta_v" in shown["in-plane orbit control, delta-V"].source
    assert chained_inputs.budget_inputs(ResultSet(scenario_name="none"), "sat", 5.0) == []


def test_a_scenario_changed_since_the_run_is_said():
    """Each value that differs from the scenario the run flew; none for the
    same scenario."""
    scenario = load_scenario(_TEMPLATES / "17_fuel_tank_depletion.json")
    assert chained_inputs.changed_since(scenario, copy.deepcopy(scenario)) == []
    edited = copy.deepcopy(scenario)
    edited.spacecraft[0].dry_mass_kg += 10.0  # [kg]
    assert chained_inputs.changed_since(scenario, edited) == [
        ("spacecraft[sat-1].dry_mass_kg", scenario.spacecraft[0].dry_mass_kg, edited.spacecraft[0].dry_mass_kg)]


@pytest.mark.requires_gui
@pytest.mark.requires_basilisk
def test_the_end_of_life_page_shows_the_chain_and_takes_the_edited_propellant(qtbot, monkeypatch):
    """From the end of the last run the page lists what the estimate takes,
    with a caution once the scenario changed; the edited propellant goes to
    the estimate."""
    from spacemissionstudio.gui import lifetime_widget

    scenario, result, _state = _tank_run()
    widget = lifetime_widget.LifetimeWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    widget.set_last_run(scenario, result)
    assert widget.chain_panel.isHidden()  # from the start of the scenario: nothing chained
    widget.from_combo.setCurrentText(lifetime_widget._FROM_LAST_RUN)
    assert not widget.chain_panel.isHidden() and widget.chain_panel.caution.text() == ""
    assert widget.chain_panel.rows["fuel tank's propellant"].text() == "0.1 kg"
    edited = copy.deepcopy(scenario)
    edited.spacecraft[0].dry_mass_kg += 10.0  # [kg]
    widget.set_scenario(edited)
    assert "changed since that run (1 value: spacecraft[sat-1].dry_mass_kg)" in widget.chain_panel.caution.text()
    started = []
    monkeypatch.setattr(lifetime_widget._LifetimeWorker, "start", lambda worker: started.append(worker._args))
    widget.propellant_check.setChecked(True)
    widget.propellant_spin.setValue(2.5)
    widget.compute()
    assert started and started[0][-1] == 2.5


@pytest.mark.requires_gui
def test_the_budget_page_shows_what_the_last_run_gives(qtbot):
    """With a run that flew station keeping, the Budget page lists it
    before computing; without a run, nothing."""
    from spacemissionstudio.gui.budget_widget import BudgetWidget

    scenario = load_scenario(_TEMPLATES / "22_starter_first_leo_satellite.json")
    name = scenario.spacecraft[0].name
    t = np.array([0.0, 86400.0])  # [s]
    result = ResultSet(scenario_name="budget")
    result.add(TimeSeries(f"{name}.position_N", t, ("x", "y", "z"), np.zeros((2, 3))))
    result.add(TimeSeries(f"{name}.station_keeping.delta_v", t, ("delta_v",), np.array([[0.0], [0.02]])))
    widget = BudgetWidget()
    qtbot.addWidget(widget)
    widget.set_scenario(scenario)
    assert widget.chain_panel.isHidden()
    widget.set_last_run(scenario, result)
    assert not widget.chain_panel.isHidden() and "Run length" in [
        widget.chain_panel.form.itemAt(i, widget.chain_panel.form.ItemRole.LabelRole).widget().text()
        for i in range(widget.chain_panel.form.rowCount())]
