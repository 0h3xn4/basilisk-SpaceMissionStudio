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
"""The static design checks of the 3D model (model-analyses Phase B,
``analyses/``): field-of-view obstruction, thruster authority and plume
impingement, the mass budget with maturity margins and launcher
compatibility, each against a hand calculation, and their findings in the
plausibility checks."""

import math
from pathlib import Path

import pytest

from spacemissionstudio.analyses import design_checks, fov, launcher, mass_budget, thrusters
from spacemissionstudio.engine import scenario_checks
from spacemissionstudio.schema import load_scenario
from spacemissionstudio.schema.scenario import (
    FuelTankConfig,
    LauncherConfig,
    MassBudgetConfig,
    MountConfig,
    MountedEquipmentConfig,
    PartPoseConfig,
)

_TEMPLATE = Path(__file__).resolve().parents[1] / "spacemissionstudio" / "scenarios" / "templates" \
    / "28_octagonal_bus_3d_model.json"
_FOLDED = [PartPoseConfig("panel +y", [0.0, 0.62, 0.0], [90.0, 0.0, 0.0]),
           PartPoseConfig("panel -y", [0.0, -0.62, 0.0], [90.0, 0.0, 0.0])]


def _spacecraft():
    scenario = load_scenario(_TEMPLATE)
    return scenario, scenario.spacecraft[0]


def _rule_ids(findings):
    return [f.rule_id for f in findings]


def test_a_panel_in_a_cameras_field_of_view_is_reported():
    """A camera 1 m above the +y panel's centre looking down with a 40 deg
    field of view: its footprint on the panel (radius 0.985 tan 20 deg =
    0.36 m) lies inside the panel's 1 m width, so all of it is blocked.
    Stowed, the panel folds away and the view is clear."""
    scenario, sc = _spacecraft()
    sc.model.equipment.append(MountedEquipmentConfig("camera", "camera", MountConfig(
        position_m=[0.0, 1.7, 1.0], boresight=[0.0, 0.0, -1.0], field_of_view_deg=40.0)))
    sc.model.stowed += _FOLDED
    scenario.validate()
    report = fov.fov_obstruction(sc, samples=512, base_dir=_TEMPLATE.parent)
    by_configuration = {o.configuration: o for o in report.obstructions}
    assert by_configuration["deployed"].blocked_fraction == 1.0
    assert list(by_configuration["deployed"].by_part) == ["panel +y"]
    assert by_configuration["stowed"].blocked_fraction == 0.0
    assert report.rows()[0]["blocked_percent"] == 100.0
    findings = scenario_checks.plausibility_warnings(scenario, _TEMPLATE.parent)
    blocked = [f for f in findings if getattr(f, "rule_id", "") == "design.fov_obstructed"]
    assert len(blocked) == 1 and "camera's field of view (deployed) is 100.0 % blocked by panel +y" in blocked[0]


def test_a_viewing_item_without_a_field_of_view_is_listed_as_skipped():
    """A star tracker mounted without a field of view cannot be checked,
    and says why."""
    _, sc = _spacecraft()
    sc.sensors[0].kind = "star_tracker"
    sc.sensors[0].mount = MountConfig(part="star tracker", position_m=[0.0, 0.0, 0.125], boresight=[0.0, 0.0, 1.0])
    report = fov.fov_obstruction(sc, base_dir=_TEMPLATE.parent)
    assert (sc.sensors[0].name, "its mount gives no a field of view") in report.skipped or any(
        name == sc.sensors[0].name and "field of view" in why for name, why in report.skipped)


def test_a_symmetric_thruster_pair_gives_a_pure_torque_and_its_arms_follow_the_propellant():
    """Two 2 N thrusters at x = +-0.5 m firing +y and -y: the forces cancel
    and each gives 1 N*m about z. With 50 kg of propellant at z = 0.6 m on a
    300 kg dry spacecraft at the origin, the centre of mass starts at
    z = 0.6 x 50 / 350 = 0.0857 m, which adds +-0.0857 x 2 N*m about x to
    each thruster at the beginning of life, cancelling in the pair."""
    _, sc = _spacecraft()
    sc.center_of_mass_b_m = [0.0, 0.0, 0.0]
    sc.dry_mass_kg = 300.0  # [kg]
    sc.fuel_tank = FuelTankConfig(50.0, 60.0, [0.0, 0.0, 0.6])  # [kg], [kg], [m]
    for name, x, direction in (("thr +", 0.5, 1.0), ("thr -", -0.5, -1.0)):
        sc.model.equipment.append(MountedEquipmentConfig(name, "thruster", MountConfig(
            position_m=[x, 0.0, 0.0], boresight=[0.0, direction, 0.0]), thrust_n=2.0))
    authority = thrusters.thruster_authority(sc)
    c_z = 0.6 * 50.0 / 350.0  # [m]
    assert authority.com_bol_b_m == pytest.approx([0.0, 0.0, c_z])
    assert authority.matrix_bol[:, 0] == pytest.approx([0.0, 2.0, 0.0, 2.0 * c_z, 0.0, 1.0])
    assert authority.matrix_bol[:, 1] == pytest.approx([0.0, -2.0, 0.0, -2.0 * c_z, 0.0, 1.0])
    assert authority.matrix_bol.sum(axis=1) == pytest.approx([0.0, 0.0, 0.0, 0.0, 0.0, 2.0])
    assert authority.matrix_eol[3:, 0] == pytest.approx([0.0, 0.0, 1.0])
    assert authority.rank() == 2
    assert authority.rows()[0]["arm_change_m"] == pytest.approx(c_z)


def test_a_plume_cone_on_a_panel_edge_is_half_blocked():
    """A nozzle 0.5 m above the +y panel's edge (x = 0.5 m) firing up, so
    its plume goes down, with a 45 deg half-angle: its footprint on the
    panel (radius 0.485 m) is cut in half by the edge. Without a
    half-angle the thruster is skipped."""
    scenario, sc = _spacecraft()
    sc.model.equipment.append(MountedEquipmentConfig("orbit thruster", "thruster", MountConfig(
        position_m=[0.5, 1.7, 0.5], boresight=[0.0, 0.0, 1.0], plume_half_angle_deg=45.0), thrust_n=22.0))
    sc.model.equipment.append(MountedEquipmentConfig("spare", "thruster", MountConfig(
        position_m=[0.0, 0.0, 1.0], boresight=[0.0, 0.0, 1.0])))
    found, skipped = thrusters.plume_impingement(sc, samples=4096, base_dir=_TEMPLATE.parent)
    assert len(found) == 1 and found[0].blocked_fraction == pytest.approx(0.5, abs=0.01)
    assert list(found[0].by_part) == ["panel +y"]
    assert skipped == [("spare", "no plume half-angle, position or direction")]
    rules = _rule_ids(scenario_checks.plausibility_warnings(scenario, _TEMPLATE.parent))
    assert rules.count("design.plume_impingement") == 1


def test_the_mass_budget_adds_the_maturity_margins_as_a_hand_calculation_does():
    """Template 28's 300 kg of parts: the bus (232 kg, estimated structure,
    25 %) and the panels (2 x 10 kg, layout solar array, 20 %) give
    58 + 4 = 62 kg of growth; a 3 kg estimated electronics unit adds 30 %
    (0.9 kg); a unit of an unknown subsystem takes its row's largest, 55 %.
    A 10 % system margin on the dry mass with growth, 50 kg of propellant,
    against a 420 kg limit."""
    scenario, sc = _spacecraft()
    parts = {p.name: p for p in sc.model.parts}
    parts["bus"].maturity, parts["bus"].subsystem = "estimated", "structure"
    for name in ("panel +y", "panel -y"):
        parts[name].maturity, parts[name].subsystem = "layout", "solar_array"
    sc.model.equipment.append(MountedEquipmentConfig("obc", "unit", MountConfig(position_m=[0.0, 0.0, 0.0]),
                                                     mass_kg=3.0, maturity="estimated", subsystem="electronics"))
    sc.model.equipment.append(MountedEquipmentConfig("payload", "unit", MountConfig(position_m=[0.0, 0.0, 0.3]),
                                                     mass_kg=2.0, maturity="estimated", subsystem="payload"))
    sc.model.mass_budget = MassBudgetConfig("aiaa_s120_2006", 10.0, 420.0, "a test limit")
    sc.fuel_tank = FuelTankConfig(50.0, 60.0, [0.0, 0.0, 0.0])  # [kg], [kg], [m]
    budget = mass_budget.mass_budget(sc)
    assert budget.basic_dry_kg == pytest.approx(305.0)  # [kg]
    assert budget.growth_kg == pytest.approx(58.0 + 4.0 + 0.9 + 1.1)  # [kg]
    assert budget.system_margin_kg == pytest.approx(0.1 * (305.0 + 64.0))  # [kg]
    assert budget.launch_mass_kg == pytest.approx(1.1 * 369.0 + 50.0)  # [kg] 455.9
    assert budget.headroom_kg == pytest.approx(420.0 - 455.9)
    columns = {line.item: line.column for line in budget.lines}
    assert "largest" in columns["payload"] or columns["payload"] != "electronics"
    assert budget.by_subsystem()["structure"] == pytest.approx((232.0, 58.0))
    assert len(budget.rows()) == len(budget.lines)
    rules = _rule_ids(design_checks.design_checks(sc, base_dir=_TEMPLATE.parent).findings())
    assert rules == ["design.mass_over_limit"]


def test_a_spacecraft_without_a_model_is_one_line():
    """No model: the dry mass is the budget's one line, with no margin."""
    _, sc = _spacecraft()
    sc.model = None
    budget = mass_budget.mass_budget(sc)
    assert budget.basic_dry_kg == pytest.approx(sc.dry_mass_kg) and budget.growth_kg == 0.0


def test_parts_outside_a_launcher_envelope_by_a_known_distance():
    """Folded panels reach 1.0 m below the body origin, so 0.3 m below a
    separation plane at z = -0.7 m; a 2 m cylinder holds everything else.
    In a 1.5 m wide box the dish's apex (x = 0.8 m) sticks out 0.05 m. The
    dish's 0.3 m radius drawn with 128 sides errs by at most
    0.3 (1 - cos(pi / 128))."""
    scenario, sc = _spacecraft()
    sc.model.stowed += _FOLDED
    sc.model.launcher = LauncherConfig(shape="cylinder", diameter_m=2.0, height_m=3.0, origin_b_m=[0.0, 0.0, -0.7],
                                       source="a test envelope")
    scenario.validate()
    check = launcher.launcher_check(sc, _TEMPLATE.parent)
    assert check.configuration == "stowed" and not check.fits
    assert [(p.part, p.where) for p in check.protrusions] == [("panel +y", "below the separation plane"),
                                                              ("panel -y", "below the separation plane")]
    assert check.protrusions[0].distance_m == pytest.approx(0.3, abs=1e-12)
    assert check.largest_faceting_error_m == pytest.approx(0.3 * (1.0 - math.cos(math.pi / 128)))
    sc.model.launcher = LauncherConfig(shape="box", width_m=1.5, depth_m=3.0, height_m=3.0,
                                       origin_b_m=[0.0, 0.0, -1.0], source="a test envelope")
    check = launcher.launcher_check(sc, _TEMPLATE.parent)
    assert [(p.part, p.where) for p in check.protrusions] == [("dish", "width")]
    assert check.protrusions[0].distance_m == pytest.approx(0.05, abs=1e-12)
    sc.model.launcher = LauncherConfig(shape="profile", profile=[[0.0, 1.0], [2.5, 1.0], [3.0, 0.5]],
                                       origin_b_m=[0.0, 0.0, -1.0], source="a test envelope")
    assert launcher.launcher_check(sc, _TEMPLATE.parent).fits


def test_the_launch_mass_and_centre_of_mass_against_the_launcher_limits():
    """The stowed spacecraft's centre of mass is z_c + 0.7 m above a
    separation plane at z = -0.7 m and |x_c| from the axis; limits below
    those are reported, as is a mass limit below 300 kg."""
    scenario, sc = _spacecraft()
    sc.model.launcher = LauncherConfig(shape="cylinder", diameter_m=6.0, height_m=4.0,
                                       origin_b_m=[0.0, 0.0, -0.7], mass_limit_kg=250.0, com_height_limit_m=0.5,
                                       com_lateral_limit_m=0.01, source="a test envelope")
    scenario.validate()
    check = launcher.launcher_check(sc, _TEMPLATE.parent)
    assert check.configuration == "deployed" and check.fits
    assert check.mass_kg == pytest.approx(300.0)
    assert check.com_height_m == pytest.approx(sc.center_of_mass_b_m[2] + 0.7, abs=1e-9)
    assert check.com_lateral_m == pytest.approx(abs(sc.center_of_mass_b_m[0]), abs=1e-9)
    assert len(check.limit_problems()) == 3
    rules = _rule_ids(design_checks.design_findings(scenario, _TEMPLATE.parent))
    assert rules == ["design.launcher_limit"] * 3
    assert "Stiffness" in check.out_of_scope


def test_the_templates_raise_no_design_finding_but_template_32s_two():
    """No bundled template sets mounts, limits or an envelope that a
    design check reports, but template 32, made to show two."""
    for path in sorted(_TEMPLATE.parent.glob("*.json")):
        scenario = load_scenario(path)
        rules = _rule_ids(design_checks.design_findings(scenario, path.parent))
        expected = ["design.fov_obstructed", "design.plume_impingement"] if path.name.startswith("32_") else []
        assert rules == expected, path.name


def test_the_design_checks_on_the_command_line_and_in_the_api(tmp_path, capsys):
    """``check-design`` prints each check and its findings and writes the
    record and the tables, each table with its provenance; ``api``'s
    ``design_checks`` gives the same report and ``record`` the same
    record. A spacecraft that does not exist is an error."""
    import json

    from spacemissionstudio import api, cli

    scenario, sc = _spacecraft()
    sc.model.equipment.append(MountedEquipmentConfig("camera", "camera", MountConfig(
        position_m=[0.0, 1.7, 1.0], boresight=[0.0, 0.0, -1.0], field_of_view_deg=40.0)))
    sc.model.stowed += _FOLDED
    sc.model.launcher = LauncherConfig(shape="cylinder", diameter_m=2.0, height_m=3.0, origin_b_m=[0.0, 0.0, -0.7],
                                       source="a test envelope")
    path = tmp_path / "model.json"
    scenario.save(path)
    record_path, tables = tmp_path / "design.json", tmp_path / "tables"
    rc = cli.main(["check-design", str(path), "--samples", "128", "--explain", "--out", str(record_path),
                   "--tables", str(tables)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "camera (deployed, 40 deg): 100.0 % blocked" in out and "FINDING: octa-sat: panel +y is 300 mm" in out
    assert "rule design.envelope_protrusion" in out and "Stiffness" in out
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["kind"] == "design_checks" and record["inputs"]["samples"] == 128
    assert [f["rule_id"] for f in record["findings"]] == ["design.fov_obstructed"] + ["design.envelope_protrusion"] * 2
    assert record["provenance"]["scenario_file"] == "model.json"
    assert sorted(p.name for p in tables.iterdir()) == [
        "field_of_view.csv", "field_of_view.csv.provenance.json", "launcher_envelope.csv",
        "launcher_envelope.csv.provenance.json", "mass_budget.csv", "mass_budget.csv.provenance.json"]
    loaded = api.load(path)
    report = api.design_checks(loaded, samples=128, base_dir=tmp_path)
    assert [f.rule_id for f in report.findings()] == [f["rule_id"] for f in record["findings"]]
    assert api.record(loaded, report)["results"]["launcher"]["fits"] is False
    assert cli.main(["check-design", str(path), "--spacecraft", "nobody"]) == 1
    assert "no spacecraft named 'nobody'" in capsys.readouterr().err


def test_the_editor_s_repeated_checks_of_an_unchanged_spacecraft_cast_no_new_rays(monkeypatch):
    """The scenario editor checks at every edit: a spacecraft whose content
    has not changed keeps its findings without new ray casting; a change
    to it checks it again."""
    scenario, sc = _spacecraft()
    calls = []
    real = design_checks.design_checks
    monkeypatch.setattr(design_checks, "_FINDINGS", {})
    monkeypatch.setattr(design_checks, "design_checks", lambda *a, **k: calls.append(a) or real(*a, **k))
    first = design_checks.design_findings(scenario)
    assert design_checks.design_findings(scenario) == first and len(calls) == 1
    sc.model.parts[0].mass_kg += 1.0  # [kg]
    design_checks.design_findings(scenario)
    assert len(calls) == 2
