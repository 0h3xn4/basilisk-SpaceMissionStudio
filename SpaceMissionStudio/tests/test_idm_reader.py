#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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
"""The IDM-CIC reader (``spacemissionstudio.idm``): values as the files
write them, the archive, the object graph, poses and the placement of a
model's units, checked by hand against the synthetic fixture
(``tests/data/idm/demosat``; IDM-CIC is (c) CNES)."""

import itertools
import math
import zipfile

import numpy as np
import pytest
from idm_fixtures import model_xml, write_idm

from spacemissionstudio import idm
from spacemissionstudio.idm import archive, frames, graph, shapes, values
from spacemissionstudio.model3d.geometry import rotation_matrix


def test_values_read_decimal_commas_exponents_booleans_colours_and_dates():
    """Comma or point decimals with exponents; True/False; RGB(0..255)
    as 0..1; dd/MM/yyyy dates as ISO 8601; anything else refused."""
    assert values.number("0,5") == 0.5
    assert values.number("1,25E-02") == 0.0125
    assert values.number("-3.5e+1") == -35.0
    assert values.number("", default=2.0) == 2.0
    with pytest.raises(idm.IdmError, match="not a number"):
        values.number("1,2,3", "x")
    with pytest.raises(idm.IdmError, match="no value"):
        values.number(None, "x")
    assert values.boolean("True") is True and values.boolean("false") is False
    with pytest.raises(idm.IdmError):
        values.boolean("yes")
    assert values.color("RGB(255,0,51)") == (1.0, 0.0, 0.2)
    assert values.color("not a colour") == (0.7, 0.7, 0.7)
    assert values.date("02/03/2026 10:20:30") == "2026-03-02T10:20:30"
    assert values.date("2026") == ""


def test_the_archive_reads_model_xml_with_a_bom_any_case_and_backslash_names(tmp_path):
    """model.xml is found whatever its case or separators, read with or
    without a byte-order mark; other entries are listed, never read."""
    path = write_idm(tmp_path / "a.idm", entry="Model.XML", extra={"idmFiles\\picture.png": b"\x89PNG"})
    opened = archive.read(path)
    assert opened.model_xml.startswith("<?xml") and opened.entries == ["idmFiles/picture.png"]
    assert len(opened.sha256) == 64
    assert archive.read(write_idm(tmp_path / "b.idm", bom=False)).model_xml.startswith("<?xml")


def test_a_file_that_is_not_a_model_is_refused_with_the_reason(tmp_path):
    """No file, not a ZIP, no model.xml, not XML, a document type
    declaration (no entity expansion), another root element."""
    with pytest.raises(idm.IdmError, match="could not read"):
        idm.load(tmp_path / "missing.idm")
    (tmp_path / "text.idm").write_text("hello")
    with pytest.raises(idm.IdmError, match="not a ZIP archive"):
        idm.load(tmp_path / "text.idm")
    with zipfile.ZipFile(tmp_path / "empty.idm", "w") as z:
        z.writestr("other.xml", "<IDM/>")
    with pytest.raises(idm.IdmError, match="has no model.xml"):
        idm.load(tmp_path / "empty.idm")
    with pytest.raises(idm.IdmError, match="not well-formed"):
        idm.load(write_idm(tmp_path / "bad.idm", "<IDM><IdmData>"))
    with pytest.raises(idm.IdmError, match="document type"):
        idm.load(write_idm(tmp_path / "dtd.idm", '<!DOCTYPE IDM [<!ENTITY a "b">]><IDM>&a;</IDM>'))
    with pytest.raises(idm.IdmError, match="not <IDM>"):
        idm.load(write_idm(tmp_path / "root.idm", "<Other/>"))


def test_the_graph_indexes_objects_and_follows_references():
    """Objects by fullId, their text, nested objects and collections;
    a reference to a missing object is an error when followed."""
    g = graph.parse(model_xml())
    assert g.version == "3.4.1.1"
    wing = g.get("el.1_ss.STR_eq.2")
    assert wing.text("name") == "Wing" and [s.full_id for s in wing.many("shapes")] == ["el.1_ss.STR_eq.2_sh.1"]
    instance = g.get("el.1_ss.STR_eqi.2-1")
    assert g.follow(instance, "unit") is wing
    assert g.follow(instance, "parentCoordinateSystem").full_id == "el.1_co.2"
    assert instance.one("position").owner is instance
    with pytest.raises(idm.IdmError, match="does not contain"):
        g.get("el.9")


def test_rotations_are_intrinsic_products_in_the_order_named():
    """R = R1 @ R2 @ R3 about the axes named, for all twelve orders; the
    two transformation orders; and roll-pitch-yaw back out, including at
    pitch +-90 deg."""
    rng = np.random.default_rng(7)
    for order in frames.ROTATION_ORDERS:
        a = rng.uniform(-180.0, 180.0, 3)
        axes = [part[1].upper() for part in order.split("_")]
        expected = frames.axis_rotation(axes[0], a[0]) @ frames.axis_rotation(axes[1], a[1]) \
            @ frames.axis_rotation(axes[2], a[2])
        assert np.allclose(frames.rotation(order, a), expected)
    assert np.allclose(frames.axis_rotation("Z", 90.0) @ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    with pytest.raises(idm.IdmError):
        frames.rotation("Rx_Rx_Ry", [0, 0, 0])
    m = frames.pose([0.0, 0.1, 0.0], "Rx_Ry_Rz", [0.0, 0.0, 90.0], "Translation_Rotation")
    assert np.allclose(m[:3, 3], [0.0, 0.1, 0.0])
    m = frames.pose([0.0, 0.1, 0.0], "Rx_Ry_Rz", [0.0, 0.0, 90.0], "Rotation_Translation")
    assert np.allclose(m[:3, 3], [-0.1, 0.0, 0.0])
    for roll, pitch, yaw in itertools.product((-120.0, 0.0, 35.0), (-90.0, -30.0, 0.0, 60.0, 90.0), (-170.0, 45.0)):
        r = rotation_matrix([roll, pitch, yaw])
        assert np.allclose(rotation_matrix(frames.roll_pitch_yaw_deg(r)), r, atol=1e-12)
    assert np.allclose(frames.inverse(m) @ m, np.eye(4))


def test_the_model_lists_configurations_and_elements_and_where_each_is_mounted(tmp_path):
    model = idm.load(write_idm(tmp_path / "d.idm"))
    assert (model.version, model.project, model.last_modification) == ("3.4.1.1", "Demosat", "2026-03-02T10:20:30")
    assert [(c.id, c.name) for c in model.configurations] == [("OPS", "Operations"), ("LCH", "Launch")]
    assert [(e.name, e.mounted_on) for e in model.elements] == [("Bus", None), ("Camera", "el.1"),
                                                                 ("Ground jig", None)]
    assert model.notes == []
    assert model.configuration("Launch").id == "LCH"
    with pytest.raises(idm.IdmError, match="no configuration 'X'"):
        model.configuration("X")


def test_a_placement_holds_the_physical_units_never_an_assembly_s_templates(tmp_path):
    """The defaults: every element, the optional unit left out; the lens
    once (its assembly instance's occurrence), not its template; poses
    through the whole chain."""
    model = idm.load(write_idm(tmp_path / "d.idm"))
    placement = model.place()
    ids = [u.full_id for u in placement.units]
    assert "el.2_ss.PAY_assi.2-1_eqi.1-1" in ids and "el.2_ss.PAY_ass.2_eqi.1-1" not in ids
    assert "el.1_ss.STR_eqi.6-1" not in ids  # optional, off by default
    assert len(ids) == 10
    frame = {u.full_id: u.frame for u in placement.units}
    # The lens: camera root (0, 0, 0.5), assembly instance (0.1, 0, 0), its template's (0, 0, 0.1).
    assert np.allclose(frame["el.2_ss.PAY_assi.2-1_eqi.1-1"][:3, 3], [0.1, 0.0, 0.6])
    # The wing hangs on the hinge (0.5, 0, 0.25), turned 0 deg by default and 90 deg about y at launch.
    assert np.allclose(frame["el.1_ss.STR_eqi.2-1"][:3, :3], np.eye(3))
    launch = {u.full_id: u for u in model.place("LCH").units}
    assert np.allclose(launch["el.1_ss.STR_eqi.2-1"].frame[:3, :3], frames.axis_rotation("Y", 90.0))
    assert "el.1_ss.STR_eqi.6-1" in launch and "el.3_ss.STR_eqi.1-1" not in launch
    (tank,) = placement.units[[u.full_id for u in placement.units].index("el.1_ss.STR_eqi.5-1")].tanks
    assert (tank.fraction, tank.capacity_kg, tank.propellant_kg) == (0.5, 12.0, 6.0)
    assert launch["el.1_ss.STR_eqi.5-1"].tanks[0].propellant_kg == 12.0


def test_shape_volumes_and_areas_match_the_closed_forms():
    """The generated meshes keep each circle's area, so revolved volumes
    are exact for straight profiles and close for curved ones; a box with
    a cylinder removed loses the cylinder's volume."""
    def node(tag, **kw):
        return graph.Node(tag, values={k: str(v).replace(".", ",") for k, v in kw.items()})

    cases = [(node("HollowCylinder", d1=0.5, d3=2, d4=0.1), math.pi * (0.25 - 0.16) * 2, 1e-12),
             (node("FilledCone", d1=0.5, d2=0.2, d3=1), math.pi / 3 * (0.25 + 0.1 + 0.04), 1e-12),
             (node("FilledCylinder", d1=0.5, d3=2, angle1=0, angle2=90), math.pi * 0.25 * 2 / 4, 1e-12),
             (node("HollowSphere", d1=1, d4=0.5), 4 / 3 * math.pi * (1 - 0.125), 5e-3),
             (node("FilledTorus", d1=2, d2=0.5), 2 * math.pi ** 2 * 2 * 0.25, 5e-3),
             (node("ExtrudedTriangle", d1=1, d2=1, d3=2, angle1=90), 1.0, 1e-12),
             (node("ExtrudedQuadrangle", d1=1, d2=1, d3=1, d4=2, angle1=90, angle2=90), 2.0, 1e-12)]
    for n, exact, tolerance in cases:
        g = shapes.geometry(n)
        assert g.kind == "mesh" and g.mesh.welded().is_closed(), n.tag
        assert g.volume_m3 == pytest.approx(exact, rel=tolerance), n.tag
    disc = shapes.geometry(node("Disc", d1=1))
    assert not disc.solid and disc.area_m2 == pytest.approx(math.pi, rel=1e-12)
    box = shapes.geometry(node("Box", d1=1, d2=2, d3=3))
    assert box.kind == "box" and np.allclose(box.local[:3, 3], [0.5, 1.0, 1.5]) and box.volume_m3 == 6.0
    cone = shapes.geometry(node("FilledCone", d1=0.5, d2=0, d3=-1))  # pointing down: turned over
    assert cone.kind == "cone" and np.allclose(cone.centroid_m, [0.0, 0.0, -0.25])
    assert shapes.geometry(node("Step")).kind == "point"
    assert shapes.geometry(node("Line", d1=1, d2=0, d3=0)).wire
