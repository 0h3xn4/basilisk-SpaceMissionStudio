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
        asked.append(dict(old=old_label, new=new_label, current=current, converted=converted, own=own,
                          reason=reason))
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
    assert asked[0][4] == "" and "nothing converts to a TLE" in asked[0][6]


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

    with_conversion = OrbitSwitchDialog(None, "Classical elements", "Cartesian state", "a ...", "r ...", "r ...", "")
    without = OrbitSwitchDialog(None, "Classical elements", "Two-Line Element (TLE)", "a ...", "", "no lines",
                                "nothing converts to a TLE")
    for dialog in (with_conversion, without):
        qtbot.addWidget(dialog)
    assert with_conversion.convert_button.isEnabled() and not without.convert_button.isEnabled()
    with_conversion.convert_button.click()
    without.keep_button.click()
    assert (with_conversion.choice, without.choice) == ("convert", "keep")
