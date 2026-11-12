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

"""Switching the orbit type (docs/ux-audit.md U-14): a segmented control;
picking another type asks whether to convert the orbit (both sets shown)
or use that page's own values, and Cancel keeps the orbit as it was. Code
setting the type never asks."""

import pytest

from spacemissionstudio.schema.scenario import OrbitIC

pytestmark = pytest.mark.requires_gui

_CONVERTED = OrbitIC(type="cartesian", position_km=[-1197.805, -1598.774, 6628.610],  # [km]
                     velocity_km_s=[1.092724, 7.253268, 1.952497])  # [km/s]


@pytest.fixture
def widget(qtbot):
    """An orbit widget on classical elements."""
    from spacemissionstudio.gui.orbit_ic_widget import OrbitIcWidget

    w = OrbitIcWidget()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def answer(monkeypatch):
    """Answers the switch's question; records what it was shown."""
    from spacemissionstudio.gui import orbit_ic_widget

    asked = []
    state = {"choice": "convert"}

    def ask(_parent, old_label, new_label, current, converted, own, reason):
        describe = orbit_ic_widget.describe_orbit  # the orbits as the dialog's text gives them
        asked.append(dict(old=old_label, new=new_label, current=describe(current), converted=describe(converted),
                          own=describe(own), reason=reason))
        return state["choice"]

    monkeypatch.setattr(orbit_ic_widget, "ask_orbit_switch", ask)
    monkeypatch.setattr(orbit_ic_widget.orbit_conversion, "convert",
                        lambda orbit, to_type, *a, **k: _CONVERTED if to_type == "cartesian"
                        else pytest.fail("only the Cartesian conversion is used here"))
    return asked, state


def test_the_type_is_a_segmented_control(widget):
    """Three buttons, the current type checked; the combo is hidden."""
    assert [b.text() for b in widget.type_group.buttons()] == ["Classical elements", "Cartesian state",
                                                               "Two-Line Element (TLE)"]
    assert widget.type_buttons["classical_elements"].isChecked()
    assert not widget.type_combo.isVisibleTo(widget)


def test_converting_keeps_the_orbit(widget, answer):
    """Convert: the Cartesian page gets the converted state; the question
    showed the elements and the state."""
    asked, _state = answer
    widget.type_buttons["cartesian"].click()
    assert widget.to_dataclass() == _CONVERTED and widget.type_buttons["cartesian"].isChecked()
    assert asked[0]["old"] == "Classical elements" and asked[0]["current"].startswith("a 7000.000 km")
    assert asked[0]["converted"].startswith("r [-1197.805, -1598.774, 6628.610] km")


def test_keeping_uses_the_pages_own_values(widget, answer):
    """Use the page's values: the type switches, the page is untouched."""
    asked, state = answer
    state["choice"] = "keep"
    own = widget.to_dataclass("cartesian")
    widget.type_buttons["cartesian"].click()
    assert widget.to_dataclass() == own and asked[0]["own"].startswith("r [7000.000, 0.000, 0.000] km")


def test_cancelling_keeps_the_type(widget, answer):
    """Cancel: still classical elements, its button checked again."""
    _asked, state = answer
    state["choice"] = None
    before = widget.to_dataclass()
    widget.type_buttons["cartesian"].click()
    assert widget.to_dataclass() == before and widget.type_buttons["classical_elements"].isChecked()


def test_switching_to_a_tle_says_why_it_is_not_converted(widget, monkeypatch):
    """Nothing converts to a TLE: the question says why, and only "use the
    page's values" is offered."""
    from spacemissionstudio.gui import orbit_ic_widget

    asked = []
    monkeypatch.setattr(orbit_ic_widget, "ask_orbit_switch", lambda *a: asked.append(a) or "keep")
    widget.type_buttons["tle"].click()
    assert widget.to_dataclass().type == "tle"
    assert asked[0][4] is None and "nothing converts to a TLE" in asked[0][6]


def test_setting_the_type_in_code_never_asks(widget, monkeypatch):
    """from_dataclass() and the combo switch silently, and the buttons follow."""
    from spacemissionstudio.gui import orbit_ic_widget

    monkeypatch.setattr(orbit_ic_widget, "ask_orbit_switch", lambda *a: pytest.fail("asked"))
    widget.from_dataclass(_CONVERTED)
    assert widget.type_buttons["cartesian"].isChecked()
    widget.type_combo.setCurrentIndex(widget.type_combo.findData("tle"))
    assert widget.type_buttons["tle"].isChecked()


def test_the_question_offers_convert_only_when_there_is_a_conversion(qtbot):
    """The dialog's Convert button needs a converted orbit; each button
    sets its choice."""
    from spacemissionstudio.gui.orbit_ic_widget import OrbitSwitchDialog

    elements = OrbitIC(type="classical_elements", semi_major_axis_km=7000.0, eccentricity=0.001,
                       inclination_deg=97.5, raan_deg=10.0, arg_periapsis_deg=0.0, true_anomaly_deg=0.0)
    with_conversion = OrbitSwitchDialog(None, "Classical elements", "Cartesian state", elements, _CONVERTED,
                                        _CONVERTED, "")
    without = OrbitSwitchDialog(None, "Classical elements", "Two-Line Element (TLE)", elements, None, None,
                                "nothing converts to a TLE")
    for dialog in (with_conversion, without):
        qtbot.addWidget(dialog)
    assert with_conversion.convert_button.isEnabled() and not without.convert_button.isEnabled()
    with_conversion.convert_button.click()
    without.keep_button.click()
    assert (with_conversion.choice, without.choice) == ("convert", "keep")


def test_the_question_shows_each_orbit_as_a_table_of_values(qtbot):
    """Side by side, one value a row with its unit: the orbit now, after
    converting, and the new page's own values; a refusal says why first."""
    from spacemissionstudio.gui.orbit_ic_widget import OrbitSwitchDialog

    elements = OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                       inclination_deg=97.59, raan_deg=259.42, arg_periapsis_deg=0.0, true_anomaly_deg=0.0)
    dialog = OrbitSwitchDialog(None, "Classical elements", "Cartesian state", elements, _CONVERTED, None, "")
    qtbot.addWidget(dialog)
    assert dialog.current_sheet.rows[0] == ("Semi-major axis a", "6928.000", "km")
    assert dialog.current_sheet.value("Inclination i") == "97.5900"
    assert dialog.converted_sheet.rows[0] == ("Position x", "-1197.805", "km")
    assert dialog.converted_sheet.rows[3] == ("Velocity vx", "1.092724", "km/s")
    assert dialog.own_sheet.rows == [] and "no values yet" in dialog.own_sheet.text()
    refused = OrbitSwitchDialog(None, "Classical elements", "Two-Line Element (TLE)", elements, None, None,
                                "nothing converts to a TLE: a TLE holds SGP4 mean elements")
    qtbot.addWidget(refused)
    assert refused.intro_label.text().startswith("Nothing converts to a TLE: a TLE holds SGP4 mean elements.")
    assert refused.keep_button.isDefault() and refused.converted_sheet.title_label.text() == "Not converted"
