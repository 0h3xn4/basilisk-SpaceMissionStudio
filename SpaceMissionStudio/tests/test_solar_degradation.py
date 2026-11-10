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
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Solar-array degradation (transparency plan, Phase 6b:
``power.degradation``, engine.solar_degradation): each model's equation,
its parameters, the panels of a run, a long run's time in orbit and the
records."""

import math
from types import SimpleNamespace

import numpy as np
import pytest

from spacemissionstudio.config.registry import Configuration
from spacemissionstudio.engine import solar_degradation as sd
from spacemissionstudio.schema.scenario import (GravityConfig, OrbitIC, PowerConfig, Scenario, SimSettings,
                                                SpacecraftConfig)


def _configured(**overrides):
    return SimpleNamespace(configuration=Configuration(overrides=overrides))


def _scenario(configuration=None, days=0.05):
    """A low Earth orbit at the March equinox, a body panel facing +x (the
    Sun's direction then, the attitude held inertial), no load: the
    battery's net power is the panel's."""
    scenario = Scenario(
        name="degradation", epoch_utc="2030-03-20T12:00:00", simulation_mode="full_attitude",
        gravity=GravityConfig(central_body="earth", third_body_perturbers=["sun"]),
        sim_settings=SimSettings(duration_days=days, dynamics_task_rate_s=10.0, integrator="rkf45"),  # [day], [s]
        spacecraft=[SpacecraftConfig(
            name="sat", orbit=OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.0,
                                      inclination_deg=98.0, raan_deg=0.0, arg_periapsis_deg=0.0,
                                      true_anomaly_deg=0.0),  # [km], [deg]
            power=PowerConfig(panel_area_m2=1.0, panel_efficiency=0.30, panel_normal_b=[1.0, 0.0, 0.0],
                              battery_capacity_wh=1.0e6,
                              battery_initial_soc=0.0))])  # [m^2], [-], [W*hr]
    scenario.configuration = configuration
    return scenario


def test_no_degradation_by_default():
    """The default, "none", is what a run did before the choice: no model."""
    assert sd.from_scenario(None) is None and sd.from_scenario(_configured()) is None


def test_each_model_is_the_equation_it_declares():
    """yearly_rate: F_UV F_thermal (1 - D)^t; radiation_dose: F_UV F_thermal
    (1 - C log10(1 + D_d t / D_x)); t is the years at the start plus the time
    flown; the project's values replace the defaults."""
    yearly = sd.from_scenario(_configured(**{"power.degradation": "yearly_rate"}))
    assert (yearly.per_year, yearly.uv_factor, yearly.thermal_factor) == (0.027, 0.98, 0.99)
    for years in (0.0, 1.0, 7.3):  # [year]
        assert yearly.remaining(years) == pytest.approx(0.98 * 0.99 * (1.0 - 0.027) ** years, rel=1e-14)
    assert yearly.remaining(-1.0) == yearly.remaining(0.0)
    dose = sd.from_scenario(_configured(**{"power.degradation": "radiation_dose",
                                           "power.displacement_damage_dose_per_year_mev_g": 2.0e9,
                                           "power.uv_darkening_factor": 1.0, "power.years_in_orbit_at_start": 3.0}))
    assert dose.years_at(sd.YEAR_S) == pytest.approx(4.0)
    assert dose.remaining(dose.years_at(sd.YEAR_S)) == pytest.approx(
        0.99 * (1.0 - 0.199 * math.log10(1.0 + 2.0e9 * 4.0 / 1.2e9)), rel=1e-14)


def test_the_dose_fit_is_the_papers_equation_in_base_10():
    """Walters et al.'s Figures 7 and 8 draw the fit from 1e8 to 1e11 MeV/g
    above 0.5: base 10 (0.62 at 1e11); the natural logarithm would be 0.12.
    At D_d = D_x it keeps 1 - C log10(2), 94 %."""
    dose = sd.Degradation("radiation_dose", 0.0, 1.0e11, 0.199, 1.2e9, 1.0, 1.0, 0.0)
    assert dose.time_factor(1.0) == pytest.approx(1.0 - 0.199 * math.log10(1.0 + 1.0e11 / 1.2e9))
    assert 0.5 < dose.time_factor(1.0) < 0.65 and 1.0 - 0.199 * math.log(1.0 + 1.0e11 / 1.2e9) < 0.2
    assert dataclass_replace(dose, dose_per_year_mev_g=1.2e9).time_factor(1.0) == pytest.approx(
        1.0 - 0.199 * math.log10(2.0))


def dataclass_replace(found, **changes):
    import dataclasses

    return dataclasses.replace(found, **changes)


def test_the_radiation_dose_needs_the_orbits_dose():
    """SpaceMissionStudio has no radiation-belt model: without a dose the
    model is refused, naming the parameter."""
    with pytest.raises(sd.DegradationError, match="displacement_damage_dose_per_year_mev_g"):
        sd.from_scenario(_configured(**{"power.degradation": "radiation_dose"}))


def test_the_trace_names_each_input():
    found = sd.from_scenario(_configured(**{"power.degradation": "yearly_rate"}))
    trace = sd.trace(found, 5.0, 0.30, "parameter: power.years_in_orbit_at_start", "scenario: power")
    assert trace.value == pytest.approx(0.30 * found.remaining(5.0))
    assert trace.input("D") == 0.027 and trace.input("F_UV") == 0.98 and trace.input("t") == 5.0
    assert trace.equation == "eta = eta_BOL F_UV F_thermal (1 - D)^t"


@pytest.mark.requires_basilisk
def test_the_module_sets_each_panels_efficiency_with_the_time_flown_before():
    """Each panel's efficiency is its own beginning-of-life value times the
    factor at the years in orbit, counting the time a long run flew before
    this segment."""
    found = sd.from_scenario(_configured(**{"power.degradation": "yearly_rate"}))
    panels = [SimpleNamespace(panelEfficiency=0.30), SimpleNamespace(panelEfficiency=0.28)]
    module = sd.PanelDegradation("test", found, panels, offset_s=2.0 * sd.YEAR_S)
    module.UpdateState(int(sd.YEAR_S * 1e9))  # [ns] one year into this segment
    for panel, bol in zip(panels, (0.30, 0.28)):
        assert panel.panelEfficiency == pytest.approx(bol * found.remaining(3.0), rel=1e-12)
    assert module.factorLog == [pytest.approx(found.remaining(3.0))]


@pytest.mark.requires_basilisk
def test_a_run_degrades_the_panels_by_the_model():
    """With yearly_rate and 5 years in orbit, the panel's power is the
    default run's times the factor at each sample, recorded as a series;
    the provenance records the model, and the default run has neither."""
    from spacemissionstudio.engine.service import SimulationService

    plain = SimulationService(_scenario()).run()
    chosen = SimulationService(_scenario(Configuration(overrides={
        "power.degradation": "yearly_rate", "power.years_in_orbit_at_start": 5.0}))).run()
    found = sd.from_scenario(_configured(**{"power.degradation": "yearly_rate", "power.years_in_orbit_at_start": 5.0}))
    before, after = (r.series["sat.battery_net_power"].data[:, 0] for r in (plain, chosen))
    lit = before > 1.0  # [W]
    assert lit.sum() > 10
    factor = chosen.series["sat.power.degradation_factor"]
    times = chosen.series["sat.battery_net_power"].time_s
    expected = np.array([found.remaining(found.years_at(t)) for t in times])
    assert after[lit] == pytest.approx(before[lit] * expected[lit], rel=1e-9)
    assert factor.data[0, 0] == pytest.approx(found.remaining(5.0), rel=1e-12)
    assert chosen.provenance.to_dict()["models"]["power.degradation"]["model"] == "yearly_rate"
    assert "sat.power.degradation_factor" not in plain.series and "models" not in plain.provenance.to_dict()


@pytest.mark.requires_basilisk
def test_a_run_with_radiation_dose_and_no_dose_is_refused():
    from spacemissionstudio.engine.service import SimulationService, SimulationServiceError

    with pytest.raises(SimulationServiceError, match="displacement_damage_dose_per_year_mev_g"):
        SimulationService(_scenario(Configuration(overrides={"power.degradation": "radiation_dose"}))).build()


@pytest.mark.requires_basilisk
def test_a_long_runs_segments_count_the_time_already_flown(monkeypatch):
    """Each segment of a long run starts its panels at the time flown
    before it: the factor runs on across the boundary."""
    from spacemissionstudio.engine import long_run

    monkeypatch.setattr(long_run, "segment_lengths_s", lambda scenario: [600.0, 600.0])  # [s]
    scenario = _scenario(Configuration(overrides={"power.degradation": "yearly_rate",
                                                  "power.years_in_orbit_at_start": 1.0}), days=1200.0 / 86400.0)
    result = long_run.run_segmented(scenario)
    factor = result.series["sat.power.degradation_factor"]
    found = sd.from_scenario(_configured(**{"power.degradation": "yearly_rate", "power.years_in_orbit_at_start": 1.0}))
    assert factor.time_s[-1] > 600.0
    expected = [found.remaining(found.years_at(t)) for t in factor.time_s]
    assert factor.data[:, 0] == pytest.approx(expected, rel=1e-12)
