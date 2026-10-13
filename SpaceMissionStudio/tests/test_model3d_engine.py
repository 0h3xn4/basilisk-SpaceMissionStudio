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

"""Tests for a 3D model reaching the simulation: the center-of-mass offset
in Basilisk's hub, the Vizard copy of the model, the explainer and the
``model`` command."""

import json

import numpy as np
import pytest

from spacemissionstudio import cli
from spacemissionstudio.engine import vizard
from spacemissionstudio.engine.scenario_explainer import explain
from spacemissionstudio.model3d import model as model3d
from spacemissionstudio.model3d import obj_io
from spacemissionstudio.schema.scenario import (GravityConfig, ModelMassPropertiesConfig, ModelPartConfig, OrbitIC,
                                                Scenario, SimSettings, SpacecraftConfig, SpacecraftModelConfig)


def _cube_spacecraft(center_of_mass_b_m) -> SpacecraftConfig:
    """A 1 m cube, 100 kg, whose typed center of mass is offset from the
    cube's centre (point B); drag on, in a 300 km circular orbit flying
    along +y_N with the body axes aligned to the inertial ones."""
    model = SpacecraftModelConfig(
        parts=[ModelPartConfig(name="bus", shape="box", dimensions_m={"x": 1.0, "y": 1.0, "z": 1.0}, mass_kg=100.0)],
        mass_properties_source="typed",
        mass_properties=ModelMassPropertiesConfig(mass_kg=100.0, center_of_mass_b_m=list(center_of_mass_b_m),
                                                  inertia_kg_m2=[16.7, 0, 0, 0, 16.7, 0, 0, 0, 16.7]))  # [kg*m^2]
    sc = SpacecraftConfig(name="sat-1", model=model, enable_drag=True, orbit=OrbitIC(
        type="cartesian", position_km=[6678.0, 0.0, 0.0], velocity_km_s=[0.0, 7.7258, 0.0]))  # [km], [km/s]
    model3d.apply(sc, model3d.derive(model))
    return sc


def _final_body_rate(center_of_mass_b_m) -> np.ndarray:
    from spacemissionstudio.engine.service import SimulationService

    scenario = Scenario(name="com", epoch_utc="2030-01-01T00:00:00", simulation_mode="full_attitude",
                        gravity=GravityConfig(central_body="earth", central_body_degree=0),
                        sim_settings=SimSettings(duration_days=100.0 / 86400.0, dynamics_task_rate_s=1.0),  # [day], [s]
                        spacecraft=[_cube_spacecraft(center_of_mass_b_m)])
    scenario.validate()
    return SimulationService(scenario).run().series["sat-1.body_rate_omega_BN_B"].data[-1]


@pytest.mark.requires_basilisk
def test_center_of_mass_offset_gives_drag_its_torque():
    """The drag on the cube's front (+y) face acts 0.5 m ahead of B. With
    the center of mass 5 cm off along +x, the lever arm (-0.05, 0.5, 0) m
    crossed with the drag force along -y gives a torque about +z, so the
    uncontrolled cube spins up about +z; twice the offset, twice the spin.
    Centred it does not spin. Offset along the flow, the force passes
    through the center of mass, except that the cube stays fixed in
    inertial space while the orbit turns the flow by about 6.6 deg in the
    100 s, so a little torque remains. A real run, after 100 s: 2.14e-4
    rad/s for 5 cm, 4.27e-4 for 10 cm (x 1.994), 6e-22 centred, 1.25e-5
    (6 %) along the flow."""
    centred = _final_body_rate([0.0, 0.0, 0.0])
    offset = _final_body_rate([0.05, 0.0, 0.0])  # [m]
    double = _final_body_rate([0.10, 0.0, 0.0])  # [m]
    along_flow = _final_body_rate([0.0, 0.05, 0.0])  # [m]
    assert offset[2] > 1e-4  # [rad/s]
    assert double[2] == pytest.approx(2.0 * offset[2], rel=0.02)
    assert np.abs(centred).max() < 1e-9  # [rad/s]
    assert np.abs(along_flow).max() < 0.1 * offset[2]


def test_vizard_copy_is_written_in_vizards_axes(tmp_path):
    """The Vizard .obj holds every visible part, each body point (x, y, z)
    written as (-y, z, -x) (Vizard mirrors x on import and maps body axes
    to (y, z, -x)); hidden parts are left out."""
    sc = _cube_spacecraft([0.0, 0.0, 0.0])
    sc.model.parts.append(ModelPartConfig(name="mast", shape="box", dimensions_m={"x": 0.1, "y": 0.1, "z": 1.0},
                                          position_b_m=[0.0, 0.0, 1.0], mass_kg=1.0))
    sc.model.parts.append(ModelPartConfig(name="hidden", shape="sphere", dimensions_m={"diameter": 0.2},
                                          visible=False, mass_kg=1.0))
    path = vizard.write_model_for_vizard(sc, tmp_path)
    groups = obj_io.read_obj(path).groups
    assert [g.name for g in groups] == ["bus", "mast"]
    mast = groups[1].mesh.vertices
    # The mast runs from body z = 0.5 to 1.5 m: Vizard's file y (= body z).
    assert mast[:, 1].min() == pytest.approx(0.5) and mast[:, 1].max() == pytest.approx(1.5)
    assert np.abs(mast[:, [0, 2]]).max() == pytest.approx(0.05)


def test_explain_tab_shows_the_model_and_the_offset():
    """The Explain tab names the model's part count and the center-of-mass
    offset."""
    sc = _cube_spacecraft([0.03, 0.0, 0.04])
    scenario = Scenario(name="e", epoch_utc="2030-01-01T00:00:00", spacecraft=[sc],
                        gravity=GravityConfig(central_body="earth", central_body_degree=0))
    environment = next(s for s in explain(scenario).sections if s.title == "Environment")
    assert "sat-1: 3D model, 1 parts" in [b.label for b in environment.badges]
    assert "sat-1: center of mass 5.0 cm from B" in environment.notes


def test_model_command_reports_applies_and_exports(tmp_path, capsys):
    """``spacemissionstudio model`` prints the mass properties and facets,
    says whether the stored values match, writes them with --apply and the
    body-frame .obj with --export-obj."""
    sc = _cube_spacecraft([0.05, 0.0, 0.0])
    scenario = Scenario(name="m", epoch_utc="2030-01-01T00:00:00", simulation_mode="full_attitude",
                        gravity=GravityConfig(central_body="earth", central_body_degree=0), spacecraft=[sc])
    path = tmp_path / "s.json"
    scenario.save(path)
    assert cli.main(["model", str(path)]) == 0
    out = capsys.readouterr().out
    assert "mass 100 kg" in out and "facets: 6" in out and "stored values: match the model" in out

    data = json.loads(path.read_text())
    data["spacecraft"][0]["dry_mass_kg"] = 80.0
    path.write_text(json.dumps(data))
    assert cli.main(["model", str(path)]) == 0
    assert "differ in dry_mass_kg" in capsys.readouterr().out
    assert cli.main(["model", str(path), "--apply", "--export-obj", str(tmp_path / "sat.obj")]) == 0
    assert json.loads(path.read_text())["spacecraft"][0]["dry_mass_kg"] == 100.0
    assert [g.name for g in obj_io.read_obj(tmp_path / "sat.obj").groups] == ["bus"]
    assert cli.main(["model", str(path), "--spacecraft", "nope"]) == 1


@pytest.mark.requires_basilisk
def test_service_hands_vizard_the_model_next_to_the_save_file(tmp_path):
    """With a Vizard save file, each spacecraft whose model is used for
    Vizard (and has no vizard_model_path) gets an .obj in <stem>_models/
    beside it, passed on as its custom model; a set vizard_model_path
    wins."""
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.engine.vizard import VizardRequest

    sc = _cube_spacecraft([0.0, 0.0, 0.0])
    other = _cube_spacecraft([0.0, 0.0, 0.0])
    other.name = "sat-2"
    other.vizard_model_path = "CUBE"
    scenario = Scenario(name="v", epoch_utc="2030-01-01T00:00:00", simulation_mode="full_attitude",
                        gravity=GravityConfig(central_body="earth", central_body_degree=0), spacecraft=[sc, other])
    service = SimulationService(scenario, vizard_request=VizardRequest(save_file=str(tmp_path / "run.bin")))
    models = service._vizard_models_from_3d_models(scenario)
    assert list(models) == ["sat-1"]
    assert models["sat-1"]["path"] == str(tmp_path / "run_models" / "sat-1.obj")
    assert (tmp_path / "run_models" / "sat-1.mtl").is_file()
