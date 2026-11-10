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
"""The preliminary re-entry casualty estimate (model analyses Phase D,
``analyses/reentry.py``) against hand calculations: the derived
Sutton–Graves constant, a fragment's speed at the ground (its terminal
speed), the demise of a light part and the survival of a heavy one, the
emissivity bracket, and the casualty area and risk."""

import math
from pathlib import Path

import pytest

from spacemissionstudio.analyses import reentry
from spacemissionstudio.config import registry
from spacemissionstudio.constants import EARTH_EQUATORIAL_RADIUS_M, EARTH_GM_M3_S2
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import MaterialConfig, ModelMeshConfig, ModelPartConfig

pytest.importorskip("Basilisk")
_TEMPLATE = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" \
    / "28_octagonal_bus_3d_model.json"
_MATERIALS = {"bus": "aluminium_6061_t6", "panel +y": "cfrp", "panel -y": "cfrp", "dish": "aluminium",
              "star tracker": "titanium_6al_4v", "battery": "stainless_steel"}


def test_the_sutton_graves_constant_is_derived_from_the_1971_report():
    """K_air = 0.1113 kg/(s m^1.5 atm^0.5) (TR R-376, Table II) with
    p = rho V^2 and h_s - h_w = V^2 / 2: k = K / (2 sqrt(101325 Pa))."""
    assert reentry.SUTTON_GRAVES_K == pytest.approx(1.748e-4, rel=1e-3)


def test_a_fragment_that_cannot_melt_lands_at_its_terminal_speed():
    """No heating: 2 kg with 0.2 m^2 of surface (0.05 m^2 projected,
    C_d = 1) reaches the ground at sqrt(2 m g / (rho_0 A)), rho_0 the US76
    sea-level density (1.225 kg/m^3), within 1 %."""
    atmosphere = reentry._Atmosphere()
    demise, surviving, speed = reentry.descend(2.0, 0.2, None, 1.0, 78.0e3, atmosphere)
    g = EARTH_GM_M3_S2 / EARTH_EQUATORIAL_RADIUS_M ** 2  # [m/s^2]
    expected = math.sqrt(2.0 * 2.0 * g / (atmosphere.density(0.0) * 0.05))  # [m/s]
    assert demise is None and surviving == 2.0
    assert atmosphere.density(0.0) == pytest.approx(1.225, rel=1e-3)
    assert speed == pytest.approx(expected, rel=0.01)


def test_a_light_part_demises_and_a_heavy_one_survives():
    """1 kg of aluminium over 1 m^2 melts high; 200 kg in the same 1 m^2
    with re-radiation survives; without re-radiation (eps = 0) it heats
    more and keeps less."""
    atmosphere = reentry._Atmosphere()
    aluminium = {"melting_temperature_k": 867.0, "heat_of_fusion_j_kg": 386116.0, "specific_heat_j_kg_k": 896.0}
    demise, surviving, _speed = reentry.descend(1.0, 1.0, aluminium, 1.0, 78.0e3, atmosphere)
    assert demise is not None and demise > 60.0e3 and surviving == 0.0
    _, heavy_one, _ = reentry.descend(200.0, 1.0, aluminium, 1.0, 78.0e3, atmosphere)
    _, heavy_zero, _ = reentry.descend(200.0, 1.0, aluminium, 0.0, 78.0e3, atmosphere)
    assert heavy_one > heavy_zero and heavy_one > 0.0


def test_the_casualty_area_and_risk_follow_kelley_and_the_limit():
    """Template 28 with materials: every surviving fragment over 15 J adds
    (0.6 + sqrt(S / 4))^2; the risk at 25 people per km^2 is A_c x 25e-6,
    compared with 1:10,000; the demise-prone bound is shown beside; a
    part without a material survives whole and says so."""
    scenario = load_scenario(_TEMPLATE)
    sc = scenario.spacecraft[0]
    for part in sc.model.parts:
        part.material = _MATERIALS[part.name]
    sc.model.parts[-1].material = ""
    estimate = reentry.reentry_estimate(sc, _TEMPLATE.parent, population_density_per_km2=25.0)
    by_part = {f.part: f for f in estimate.fragments}
    for fragment in estimate.fragments:
        if fragment.impact_energy_j > 15.0:
            assert fragment.casualty_area_m2 == pytest.approx((0.6 + math.sqrt(fragment.area_m2 / 4.0)) ** 2)
        else:
            assert fragment.casualty_area_m2 == 0.0
    assert by_part["battery"].surviving_mass_kg == 40.0 and "no material" in by_part["battery"].note
    assert estimate.risk == pytest.approx(estimate.casualty_area_m2 * 25.0e-6)
    assert estimate.compliant == (estimate.risk <= 1e-4)
    assert estimate.casualty_area_demise_prone_m2 <= estimate.casualty_area_m2
    assert len(estimate.rows()) == len(estimate.fragments) and "Preliminary" in estimate.label
    assert reentry.reentry_estimate(sc, _TEMPLATE.parent).risk is None


def test_a_users_material_and_the_parameters_are_used():
    """A material of the model's own with a thermal set is used; one
    without is not; the break-up altitude is the registry's (78 km, DAS)."""
    scenario = load_scenario(_TEMPLATE)
    model = scenario.spacecraft[0].model
    model.materials.append(MaterialConfig("my alloy", 2700.0, 850.0, 390000.0, 1000.0, source="a test"))
    model.materials.append(MaterialConfig("half known", 2700.0, 850.0))
    assert reentry.thermal_values(model, "my alloy")["specific_heat_j_kg_k"] == 1000.0
    assert reentry.thermal_values(model, "half known") is None and reentry.thermal_values(model, "nothing") is None
    assert reentry.thermal_values(model, "aluminium_6061_t6")["melting_temperature_k"] == 867.0
    assert registry.default("reentry.breakup_altitude_km") == 78.0
    scenario.spacecraft[0].model = None
    with pytest.raises(Exception, match="needs a 3D model"):
        reentry.reentry_estimate(scenario.spacecraft[0])


@pytest.mark.parametrize("name, value", [("reentry.breakup_altitude_km", 60.0), ("reentry.casualty_energy_j", 1000.0),
                                         ("reentry.casualty_risk_limit", 1.0)])
def test_setting_a_reentry_parameter_changes_the_estimate(name, value):
    """Each re-entry parameter set in a project configuration changes what
    it controls: a lower break-up altitude changes where the panels melt;
    a 1 kJ threshold leaves the star tracker (about 0.7 kJ) harmless; a
    limit of 1 makes the estimate compliant."""
    from types import SimpleNamespace

    from spacemissionstudio.config.registry import Configuration

    scenario = load_scenario(_TEMPLATE)
    sc = scenario.spacecraft[0]
    for part in sc.model.parts:
        part.material = _MATERIALS[part.name]

    def measure(configuration):
        holder = SimpleNamespace(configuration=configuration)
        estimate = reentry.reentry_estimate(sc, _TEMPLATE.parent, 25.0, scenario=holder)
        return (round(estimate.fragments[1].demise_altitude_km or 0.0, 6), round(estimate.casualty_area_m2, 9),
                estimate.compliant)

    before = measure(None)
    assert measure(Configuration({name: registry.default(name)})) == before
    assert measure(Configuration({name: registry.parameter(name).check(value)})) != before


def test_a_part_that_cannot_be_built_stops_the_estimate_and_the_design_checks(tmp_path):
    """A part whose mesh file is missing has no surface and is not in the
    scene: rather than leave its mass out of the casualty area (or its
    blockage out of a field of view) without a word, the estimate and the
    design checks refuse the model and name the part."""
    from spacemissionstudio.analyses import common, design_checks

    sc = load_scenario(_TEMPLATE).spacecraft[0]
    sc.model.meshes.append(ModelMeshConfig(path="missing.obj"))
    sc.model.parts.append(ModelPartConfig(name="ghost", shape="mesh", mesh_index=len(sc.model.meshes) - 1,
                                          mesh_group="x", mass_kg=5.0))  # [kg]
    with pytest.raises(common.AnalysisError, match="ghost"):
        reentry.reentry_estimate(sc, tmp_path)
    with pytest.raises(common.AnalysisError, match="could not be built"):
        design_checks.design_checks(sc, base_dir=tmp_path)


def test_a_mesh_part_s_material_is_found_from_the_scenario_s_folder(tmp_path):
    """A mesh given by a path relative to the scenario file: the exposure
    table's materials are read from that folder (the scenario's, not the
    current directory's)."""
    from spacemissionstudio.analyses import run_analyses
    from spacemissionstudio.model3d import obj_io, shapes

    obj_io.write_obj(tmp_path / "plate.obj", [obj_io.ObjGroup("plate", shapes.mesh(
        "panel", {"width": 1.0, "length": 1.0, "thickness": 0.01}))])  # [m]
    sc = load_scenario(_TEMPLATE).spacecraft[0]
    sc.model.meshes.append(ModelMeshConfig(path="plate.obj"))
    sc.model.parts.append(ModelPartConfig(name="plate", shape="mesh", mesh_index=len(sc.model.meshes) - 1,
                                          mesh_group="plate", mass_kg=1.0, material="kapton_h",  # [kg]
                                          position_b_m=[0.0, 0.0, 2.0]))  # [m]
    found = run_analyses._face_materials(sc, tmp_path)
    assert any(name.startswith("plate: ") and material == "kapton_h" for name, (material, _y) in found.items())
    assert run_analyses._face_materials(sc, None) == {}
