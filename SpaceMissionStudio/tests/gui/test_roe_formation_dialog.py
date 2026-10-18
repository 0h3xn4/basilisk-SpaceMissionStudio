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

"""Tests for gui.roe_formation_dialog.RoeFormationDialog (SRS-F-21) and the
spacecraft list's "Generate ROE formation..." button. The dialog needs
no Basilisk; placing the follower does (those tests are marked)."""

import math

import pytest

pytestmark = pytest.mark.requires_gui


def _spacecraft(name, station_keeping=True):
    from spacemissionstudio.schema.scenario import OrbitIC, SpacecraftConfig, StationKeepingConfig

    return SpacecraftConfig(
        name=name, dry_mass_kg=150.0,  # [kg]
        orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.137, eccentricity=0.0005,  # [km], [-]
                      inclination_deg=97.6, raan_deg=30.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0),  # [deg]
        station_keeping=(StationKeepingConfig(target_altitude_km=550.0, deadband_km=15.0, thrust_n=0.05,  # [km], [N]
                                              isp_s=1500.0, propellant_kg=5.0)  # [s], [kg]
                         if station_keeping else None))


def _dialog(qtbot, configs=None, central_body="earth"):
    from spacemissionstudio.gui.roe_formation_dialog import RoeFormationDialog

    configs = [_spacecraft("chief-1")] if configs is None else configs
    dialog = RoeFormationDialog([c.name for c in configs], central_body=central_body, spacecraft=configs)
    qtbot.addWidget(dialog)
    return dialog


def test_defaults_are_a_passively_safe_helix(qtbot):
    """The default is the safe helix with parallel e/i vectors at 90 deg,
    300 m each, and the dialog reports its 300 m closest approach."""
    dialog = _dialog(qtbot)
    assert dialog.selected_chief_name() == "chief-1"
    assert dialog.selected_template_name() == "chief-1"
    assert dialog.control_law() == "impulsive"
    assert dialog.roe_m() == [0.0, 0.0, 0.0, 300.0, 0.0, 300.0]
    assert "300.0 m" in dialog.margin_label.text()
    assert "not passively safe" not in dialog.margin_label.text()
    assert dialog.problem() == ""


def test_description_label_wraps(qtbot):
    """A one-line description label would size the dialog to the whole
    paragraph (see test_phasing_formation_dialog.py's regression)."""
    from PySide6.QtWidgets import QLabel

    dialog = _dialog(qtbot)
    dialog.show()
    qtbot.wait(10)
    long_labels = [w for w in dialog.findChildren(QLabel) if len(w.text()) > 100]
    assert long_labels and all(w.wordWrap() for w in long_labels)
    assert dialog.sizeHint().width() < 150 * dialog.fontMetrics().averageCharWidth()


def test_safe_formation_follows_the_fields(qtbot):
    """Each safe-formation field lands in the right element: along-track
    in δλ, the radial size in |δe|, the cross-track size in |δi|, the
    phase in both vectors' angle."""
    dialog = _dialog(qtbot)
    dialog.safe_along_m.setValue(-2000.0)  # [m]
    dialog.safe_radial_m.setValue(200.0)  # [m]
    dialog.safe_cross_m.setValue(400.0)  # [m]
    dialog.safe_phase_deg.setValue(0.0)  # [deg]
    assert dialog.roe_m() == [0.0, -2000.0, 200.0, 0.0, 400.0, 0.0]


def test_switching_to_typed_elements_keeps_the_formation_and_they_are_used(qtbot):
    """Switching to typed elements copies the safe formation into the six
    boxes; edited boxes are what the dialog then returns."""
    dialog = _dialog(qtbot)
    dialog.safe_along_m.setValue(100.0)  # [m]
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("roe"))
    assert [box.value() for box in dialog.roe_spins] == [0.0, 100.0, 0.0, 300.0, 0.0, 300.0]
    dialog.roe_spins[0].setValue(5.0)  # [m] a·δa
    dialog.roe_spins[4].setValue(50.0)  # [m] a·δix
    assert dialog.roe_m() == [5.0, 100.0, 0.0, 300.0, 50.0, 300.0]
    assert "drift along-track" in dialog.margin_label.text()


def test_crossing_orbits_are_flagged(qtbot):
    """Perpendicular e/i vectors cross in the radial/cross-track plane:
    the margin is 0 and the dialog says so."""
    dialog = _dialog(qtbot)
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("roe"))
    for box, value in zip(dialog.roe_spins, (0.0, 0.0, 300.0, 0.0, 0.0, 300.0)):  # [m]
        box.setValue(value)
    assert "0.0 m" in dialog.margin_label.text()
    assert "not passively safe" in dialog.margin_label.text()


@pytest.mark.parametrize("case, expected", [
    ("no spacecraft", "no chief spacecraft"),
    ("empty name", "New follower name is empty"),
    ("mars", "around Earth only"),
    ("no station keeping", "has no station keeping"),
    ("all zero", "every element is 0"),
])
def test_problems_keep_the_dialog_open(qtbot, case, expected):
    """Each reason Generate would fail is shown in the dialog, which stays
    open, instead of failing after it closes."""
    from PySide6.QtWidgets import QLabel

    configs = {"no spacecraft": [], "no station keeping": [_spacecraft("chief-1", station_keeping=False)]}.get(
        case, None)
    dialog = _dialog(qtbot, configs, central_body="mars" if case == "mars" else "earth")
    if case == "empty name":
        dialog.follower_name_edit.setText("  ")
    if case == "all zero":
        dialog.safe_radial_m.setValue(0.0)
        dialog.safe_cross_m.setValue(0.0)
    assert expected in dialog.problem()
    dialog._on_accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert any(expected in label.text() for label in dialog.findChildren(QLabel))


def test_continuous_law_is_selectable(qtbot):
    """The law combo offers both ROE laws, by their scenario-file names."""
    from spacemissionstudio.schema.scenario import ROE_CONTROL_LAWS

    dialog = _dialog(qtbot)
    laws = [dialog.control_law_combo.itemData(i) for i in range(dialog.control_law_combo.count())]
    assert tuple(laws) == ROE_CONTROL_LAWS
    dialog.control_law_combo.setCurrentIndex(1)
    assert dialog.control_law() == "continuous"


def _accepting(monkeypatch, setup):
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.gui.roe_formation_dialog import RoeFormationDialog

    def fake_exec(self):
        setup(self)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(RoeFormationDialog, "exec", fake_exec)


@pytest.mark.requires_basilisk
def test_generate_roe_formation_appends_a_placed_follower(qtbot, monkeypatch):
    """Generate adds the follower: cloned from the template, holding the
    dialog's formation with the chosen law, and placed so that its mean
    ROE from the chief are the formation's (within 0.2 m, as
    tests/test_roe_formation_run.py's placement test)."""
    import numpy as np
    from Basilisk.utilities import orbitalMotion

    from spacemissionstudio.engine import roe
    from spacemissionstudio.engine.roe_formation import mean_elements
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget

    lw = SpacecraftListWidget()
    qtbot.addWidget(lw)
    lw.from_list([_spacecraft("chief-1")])

    def setup(dialog):
        dialog.follower_name_edit.setText("helix-1")
        dialog.safe_along_m.setValue(-2000.0)  # [m]
        dialog.control_law_combo.setCurrentIndex(1)

    _accepting(monkeypatch, setup)
    changed = []
    lw.changed.connect(lambda: changed.append(1))
    lw._on_generate_roe_formation()

    configs = lw.to_list()
    assert [c.name for c in configs] == ["chief-1", "helix-1"]
    follower = configs[1]
    assert follower.roe_formation.chief_spacecraft == "chief-1"
    assert follower.roe_formation.control_law == "continuous"
    assert follower.roe_formation.targets[0].roe_m == [0.0, -2000.0, 0.0, 300.0, 0.0, 300.0]
    assert follower.dry_mass_kg == 150.0
    assert changed == [1]

    mu = orbitalMotion.MU_EARTH * 1.0e9  # [m^3/s^2]
    req = orbitalMotion.REQ_EARTH * 1000.0  # [m]

    def mean_of(config):
        elements = orbitalMotion.ClassicElements()
        orbit = config.orbit
        elements.a = orbit.semi_major_axis_km * 1000.0  # [m]
        elements.e = orbit.eccentricity
        elements.i = math.radians(orbit.inclination_deg)
        elements.Omega = math.radians(orbit.raan_deg)
        elements.omega = math.radians(orbit.arg_periapsis_deg)
        elements.f = math.radians(orbit.true_anomaly_deg)
        r, v = orbitalMotion.elem2rv(mu, elements)
        return mean_elements(r, v, mu, req, orbitalMotion.J2_EARTH)

    chief_mean = mean_of(configs[0])
    measured = roe.roe_from_mean_elements(chief_mean, mean_of(follower)) * chief_mean.a  # [m]
    assert np.max(np.abs(measured - np.array(follower.roe_formation.targets[0].roe_m))) < 0.2  # [m]


def test_generate_roe_formation_reports_name_collision(qtbot, monkeypatch, reported):
    """A follower name already in the scenario adds nothing and says why."""
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget

    lw = SpacecraftListWidget()
    qtbot.addWidget(lw)
    lw.from_list([_spacecraft("chief-1"), _spacecraft("follower-1")])
    _accepting(monkeypatch, lambda dialog: dialog.follower_name_edit.setText("follower-1"))
    lw._on_generate_roe_formation()
    assert len(lw.to_list()) == 2
    assert reported == [("Not added: a spacecraft named 'follower-1' already exists", "warning")]


def test_generate_roe_formation_without_basilisk_says_so(qtbot, monkeypatch, reported):
    """Without Basilisk the button reports it rather than raising."""
    import sys

    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget

    monkeypatch.setitem(sys.modules, "spacemissionstudio.engine.roe_formation", None)  # import raises ImportError
    lw = SpacecraftListWidget()
    qtbot.addWidget(lw)
    lw.from_list([_spacecraft("chief-1")])
    _accepting(monkeypatch, lambda dialog: None)
    lw._on_generate_roe_formation()
    assert len(lw.to_list()) == 1
    assert len(reported) == 1 and "Basilisk is not installed" in reported[0][0]


def test_generate_roe_formation_cancel_does_nothing(qtbot, monkeypatch):
    """Cancel adds nothing and emits no change."""
    from PySide6.QtWidgets import QDialog

    from spacemissionstudio.gui.roe_formation_dialog import RoeFormationDialog
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftListWidget

    lw = SpacecraftListWidget()
    qtbot.addWidget(lw)
    lw.from_list([_spacecraft("chief-1")])
    monkeypatch.setattr(RoeFormationDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    changed = []
    lw.changed.connect(lambda: changed.append(1))
    lw._on_generate_roe_formation()
    assert len(lw.to_list()) == 1 and changed == []
