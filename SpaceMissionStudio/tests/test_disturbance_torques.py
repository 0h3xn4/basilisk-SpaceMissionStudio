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
"""Disturbance torques (model analyses, ``engine/disturbance_recorder.py``
and ``analyses/disturbances.py``): the gravity-gradient, residual-dipole
and moved-to-the-centre-of-mass torques against hand calculations, SRP on
an offset flat plate in a run against Basilisk's own force, the momentum
against the integrated torque, and the sizing findings."""

import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from spacemissionstudio.analyses import disturbances
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import (
    ActuatorConfig,
    FacetConfig,
    ModelAnalysesConfig,
    ScenarioValidationError,
)

_TEMPLATE = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" \
    / "28_octagonal_bus_3d_model.json"
MU = 3.986004418e14  # [m^3/s^2]


class _Msg:
    def __init__(self, **payload):
        self.payload = SimpleNamespace(**payload)

    def read(self):
        return self.payload


def _recorder(r_b_n, sigma, inertia, r_c, drag=None, srp=None, field=None, dipole=(0.0, 0.0, 0.0)):
    pytest.importorskip("Basilisk")
    from spacemissionstudio.engine.disturbance_recorder import DisturbanceRecorder

    hub = SimpleNamespace(IHubPntBc_B=np.asarray(inertia).tolist(), r_BcB_B=[[v] for v in r_c])
    sc_object = SimpleNamespace(hub=hub, scStateOutMsg=_Msg(r_BN_N=list(r_b_n), sigma_BN=list(sigma)))
    field_msg = None if field is None else _Msg(magField_N=list(field))
    module = DisturbanceRecorder("test", sc_object, MU, _Msg(PositionVector=[0.0, 0.0, 0.0]), drag, srp, field_msg,
                                 list(dipole))
    module.UpdateState(0)
    return module


def test_the_gravity_gradient_at_45_deg_is_the_analytic_worst_case():
    """The radius at 45 deg between the principal x and y axes:
    T_z = 3 mu / (2 R^3) (I_y - I_x), the largest over all attitudes, and
    nothing about x or y."""
    radius = 7.0e6  # [m]
    inertia = np.diag([100.0, 300.0, 250.0])  # [kg*m^2]
    module = _recorder([radius / math.sqrt(2.0), radius / math.sqrt(2.0), 0.0], [0.0, 0.0, 0.0], inertia, [0, 0, 0])
    expected = 3.0 * MU / (2.0 * radius ** 3) * (300.0 - 100.0)  # [N*m]
    assert module.torqueLog["gravity_gradient"][0] == pytest.approx([0.0, 0.0, expected], rel=1e-12, abs=1e-18)
    along_axis = _recorder([radius, 0.0, 0.0], [0.0, 0.0, 0.0], inertia, [0, 0, 0])
    assert np.allclose(along_axis.torqueLog["gravity_gradient"][0], 0.0, atol=1e-18)


def test_a_residual_dipole_and_a_force_off_the_centre_of_mass():
    """m = 2 A*m^2 along z in a 30 uT field along x gives 6e-5 N*m along y.
    A plate's force F = (0, 0, -1e-5) N at (0.5, 0, 0) m about B, with the
    centre of mass at (0.1, 0, 0) m, gives (0.4, 0, 0) x F about it; the
    total is the sum."""
    force = np.array([0.0, 0.0, -1.0e-5])  # [N]
    plate = SimpleNamespace(forceExternal_B=[[v] for v in force],
                            torqueExternalPntB_B=[[v] for v in np.cross([0.5, 0.0, 0.0], force)])
    module = _recorder([7.0e6, 0.0, 0.0], [0.0, 0.0, 0.0], np.eye(3), [0.1, 0.0, 0.0], srp=plate,
                       field=[3.0e-5, 0.0, 0.0], dipole=[0.0, 0.0, 2.0])
    assert module.torqueLog["magnetic"][0] == pytest.approx([0.0, 6.0e-5, 0.0])
    assert module.torqueLog["srp"][0] == pytest.approx(np.cross([0.4, 0.0, 0.0], force))
    assert module.torqueLog["aero"][0] == pytest.approx([0.0, 0.0, 0.0])
    from spacemissionstudio.engine.disturbance_recorder import series

    by_name = {ts.name: ts for ts in series("sc", module)}
    total = sum(by_name[f"sc.disturbance.{s}_torque"].data for s in ("aero", "srp", "gravity_gradient", "magnetic"))
    assert np.allclose(by_name["sc.disturbance.total_torque"].data, total)


@pytest.mark.slow
def test_srp_on_an_offset_flat_plate_in_a_run():
    """One 1 m^2 plate facing +z (the Sun-pointing axis) at (0.5, 0, 0) m:
    the recorded SRP torque is (r_plate - r_c) x F for Basilisk's own force
    F at every sample, and once the spacecraft points at the Sun the force
    is anti-Sun with |F| = P A (1 + rho_s + 2 rho_d / 3) (facetSRP's flat
    plate at normal incidence), P at the epoch's Sun distance, within 1 %
    (the pointing error and Basilisk's own solar flux)."""
    pytest.importorskip("Basilisk")
    from spacemissionstudio.engine.service import SimulationService

    scenario = load_scenario(_TEMPLATE)
    scenario.sim_settings.duration_days = 0.02  # [day]
    sc = scenario.spacecraft[0]
    sc.enable_drag = False
    sc.facets = [FacetConfig("plate", 1.0, [0.0, 0.0, 1.0], [0.5, 0.0, 0.0], diffuse_coeff=0.3,
                             specular_coeff=0.2)]
    sc.model_analyses = ModelAnalysesConfig(disturbance_torques=True)
    result = SimulationService(scenario).run()
    force = result.series["octa-sat.disturbance.srp_force"].data
    torque = result.series["octa-sat.disturbance.srp_torque"].data
    arm = np.array([0.5, 0.0, 0.0]) - np.asarray(sc.center_of_mass_b_m)  # [m]
    assert np.allclose(torque, np.cross(arm, force), rtol=0.0, atol=1e-15)
    t = result.series["octa-sat.disturbance.srp_force"].time_s
    sunlight = result.series["octa-sat.eclipse.illumination_factor"]
    lit = (t > 900.0) & (np.interp(t, sunlight.time_s, sunlight.data[:, 0]) == 1.0)  # full Sun, pointing settled
    assert lit.sum() > 10
    from spacemissionstudio.constants import SPEED_OF_LIGHT_M_S
    from spacemissionstudio.engine.environment_models import solar_flux_w_m2

    pressure = solar_flux_w_m2(scenario.epoch_utc) / SPEED_OF_LIGHT_M_S  # [N/m^2] at the epoch's Sun distance
    expected = pressure * 1.0 * (1.0 + 0.2 + 2.0 * 0.3 / 3.0)  # [N]
    assert np.linalg.norm(force[lit], axis=1) == pytest.approx(expected, rel=0.01)
    assert np.all(force[lit][:, 2] < 0.0)


def _synthetic(torque_fn, period_s, orbits, dipole=(0.0, 0.0, 0.0), field=(3.0e-5, 0.0, 0.0)):
    """A ResultSet of a circular orbit of ``period_s`` with the given total
    torque (the other sources zero)."""
    radius = (MU * (period_s / (2.0 * math.pi)) ** 2) ** (1.0 / 3.0)  # [m]
    speed = math.sqrt(MU / radius)  # [m/s]
    t = np.linspace(0.0, orbits * period_s, int(orbits * 200) + 1)
    result = ResultSet(scenario_name="synthetic")
    angle = 2.0 * math.pi * t / period_s
    result.add(TimeSeries("sc.position_N", t, ("x", "y", "z"),
                          np.column_stack([radius * np.cos(angle), radius * np.sin(angle), 0 * t]), units="m"))
    result.add(TimeSeries("sc.velocity_N", t, ("x", "y", "z"),
                          np.column_stack([-speed * np.sin(angle), speed * np.cos(angle), 0 * t]), units="m/s"))
    zero = np.zeros((len(t), 3))
    total = torque_fn(t)
    for source in ("aero", "srp", "gravity_gradient"):
        result.add(TimeSeries(f"sc.disturbance.{source}_torque", t, ("x", "y", "z"), zero, units="N*m"))
    result.add(TimeSeries("sc.disturbance.magnetic_torque", t, ("x", "y", "z"), total, units="N*m"))
    result.add(TimeSeries("sc.disturbance.total_torque", t, ("x", "y", "z"), total, units="N*m"))
    for source in ("aero", "srp"):
        result.add(TimeSeries(f"sc.disturbance.{source}_force", t, ("x", "y", "z"), zero, units="N"))
    result.add(TimeSeries("sc.disturbance.magnetic_field_body", t, ("x", "y", "z"), np.tile(field, (len(t), 1)),
                          units="T"))
    sc = SimpleNamespace(name="sc", facets=[], center_of_mass_b_m=[0.0, 0.0, 0.0],
                         inertia_kg_m2=np.diag([10.0, 20.0, 30.0]).tolist(), actuators=[],
                         model_analyses=ModelAnalysesConfig(disturbance_torques=True,
                                                            residual_dipole_a_m2=list(dipole)))
    return result, sc


def test_the_momentum_is_the_integrated_torque():
    """A constant 1e-5 N*m about z for two orbits of 6000 s builds 0.06 N*m*s
    per orbit and 0.12 over the run; a torque 1e-5 sin(2 pi t / P) about x
    builds none over a whole orbit, and its largest within one is
    2e-5 P / (2 pi)."""
    period = 6000.0  # [s]
    result, sc = _synthetic(lambda t: np.column_stack([0 * t, 0 * t, 1e-5 + 0 * t]), period, 2)
    budget = disturbances.disturbance_budget(result, sc)
    assert budget.whole_orbits == 2
    assert budget.momentum_per_orbit_n_m_s == pytest.approx([0.0, 0.0, 0.06], abs=1e-12)
    assert budget.momentum_end_n_m_s == pytest.approx(0.12, rel=1e-9)
    assert budget.sources["total"].orbit_average_n_m == pytest.approx([0.0, 0.0, 1e-5])
    result, sc = _synthetic(lambda t: np.column_stack([1e-5 * np.sin(2 * np.pi * t / period), 0 * t, 0 * t]),
                            period, 1)
    budget = disturbances.disturbance_budget(result, sc)
    assert budget.momentum_end_n_m_s == pytest.approx(0.0, abs=1e-9)
    assert budget.momentum_per_orbit_n_m_s[0] == pytest.approx(2e-5 * period / (2 * math.pi), rel=1e-3)
    assert budget.sources["total"].max_n_m == pytest.approx(1e-5, rel=1e-3)
    assert budget.sources["total"].mean_n_m == pytest.approx(2e-5 / math.pi, rel=1e-3)  # mean |sin| = 2 / pi


def test_wheels_and_magnetorquers_smaller_than_the_momentum_are_findings():
    """0.06 N*m*s per orbit about z: a 0.05 N*m*s wheel on z is too small
    (ratio 0.83), a 0.1 N*m*s one is not; removing 0.06 N*m*s in an orbit
    of 6000 s with 30 uT needs at least 0.06 / (6000 x 3e-5) = 0.333
    A*m^2, so a 0.2 A*m^2 rod is too small."""
    result, sc = _synthetic(lambda t: np.column_stack([0 * t, 0 * t, 1e-5 + 0 * t]), 6000.0, 1,
                            dipole=(0.0, 0.0, 0.1))
    sc.actuators = [ActuatorConfig("reaction_wheel", "rw-z", {"gsHat_B": [0.0, 0.0, 1.0], "maxMomentum": 0.05}),
                    ActuatorConfig("magnetic_torque_rod", "mtb-z", {"gtHat_B": [0.0, 0.0, 1.0],
                                                                    "max_dipole_a_m2": 0.2})]
    budget = disturbances.disturbance_budget(result, sc)
    assert budget.wheel_ratio()[2] == pytest.approx(0.05 / 0.06)
    assert budget.dipole_needed_a_m2[2] == pytest.approx(0.06 / (6000.0 * 3e-5))
    assert [f.rule_id for f in budget.findings()] == ["design.wheel_capacity", "design.dipole_capacity"]
    sc.actuators[0].params["maxMomentum"] = 0.1
    sc.actuators[1].params["max_dipole_a_m2"] = 1.0
    assert disturbances.disturbance_budget(result, sc).findings() == []
    assert disturbances.disturbance_budget(ResultSet(scenario_name="empty"), sc) is None


def test_the_srp_worst_case_of_a_flat_plate():
    """One 2 m^2 plate facing +x at 1 m from the centre of mass, reflectance
    0.5: A = 2 m^2, L = 1 m, q = 0.5."""
    sc = SimpleNamespace(facets=[FacetConfig("p", 2.0, [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], diffuse_coeff=0.3,
                                             specular_coeff=0.2)], center_of_mass_b_m=[0.0, 0.0, 0.0])
    area, distance, q = disturbances.facet_geometry(sc)
    assert area == pytest.approx(2.0, rel=1e-3) and distance == pytest.approx(1.0) and q == pytest.approx(0.5)


def test_run_analyses_need_the_attitude_and_a_dipole_needs_the_earth():
    """In 'orbit_only' mode the run analyses are refused; a residual dipole
    around another body too."""
    scenario = load_scenario(_TEMPLATE)
    scenario.spacecraft[0].model_analyses = ModelAnalysesConfig(disturbance_torques=True,
                                                                residual_dipole_a_m2=[0.0, 0.0, 1.0])
    scenario.validate()
    scenario.simulation_mode = "orbit_only"
    with pytest.raises(ScenarioValidationError, match="disturbance_torques follow the attitude"):
        scenario.validate()


def test_an_undersized_wheel_is_among_the_runs_warnings():
    """The sizing findings join the run's warnings (the Problems panel)
    when the analyses are added to a run's results."""
    from spacemissionstudio.analyses import run_analyses

    result, sc = _synthetic(lambda t: np.column_stack([0 * t, 0 * t, 1e-5 + 0 * t]), 6000.0, 1)
    sc.actuators = [ActuatorConfig("reaction_wheel", "rw-z", {"gsHat_B": [0.0, 0.0, 1.0], "maxMomentum": 0.05})]
    attitude = np.tile([0.0, 0.0, 0.0], (len(result.series["sc.position_N"].time_s), 1))
    result.add(TimeSeries("sc.attitude_sigma_BN", result.series["sc.position_N"].time_s, ("x", "y", "z"), attitude))
    scenario = SimpleNamespace(spacecraft=[sc], gravity=SimpleNamespace(central_body="earth"), ground_stations=[])
    sc.model, sc.sensors, sc.rf_link, sc.comms_pointing = None, [], None, None
    run_analyses.add_to(result, scenario)
    assert [w.rule_id for w in result.warnings] == ["design.wheel_capacity"], [str(w) for w in result.warnings]


def test_a_segmented_run_sizes_the_wheels_on_the_whole_run():
    """A run past 100 days runs in segments, and each segment's analyses
    size the wheels on its own part of the run. The merged run keeps one
    finding, from the whole run's budget: a segment's stale one (here an
    invented 0.5 N*m*s) is replaced by the run's 0.06 N*m*s per orbit."""
    from spacemissionstudio.engine import long_run
    from spacemissionstudio.engine.findings import Finding

    result, sc = _synthetic(lambda t: np.column_stack([0 * t, 0 * t, 1e-5 + 0 * t]), 6000.0, 2)
    sc.actuators = [ActuatorConfig("reaction_wheel", "rw-z", {"gsHat_B": [0.0, 0.0, 1.0], "maxMomentum": 0.05})]
    result.warnings = [Finding("sc: a segment's wheel finding", "design.wheel_capacity", actual="0.5 N*m*s"),
                       "another warning"]
    long_run._whole_run_disturbance_findings(SimpleNamespace(spacecraft=[sc]), result)
    sizing = [w for w in result.warnings if getattr(w, "rule_id", "") == "design.wheel_capacity"]
    assert len(sizing) == 1 and sizing[0].actual == "0.06 N*m*s"
    assert "another warning" in result.warnings
