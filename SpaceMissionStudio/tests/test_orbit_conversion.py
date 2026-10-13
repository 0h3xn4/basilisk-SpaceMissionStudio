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

"""Converting a spacecraft's initial orbit between its forms
(``engine.orbit_conversion``, docs/ux-audit.md U-14): the converted orbit
starts the run where the original would, by the run's own Basilisk
functions and constants."""

import math

import numpy as np
import pytest

from spacemissionstudio.schema.scenario import OrbitIC

pytestmark = pytest.mark.requires_basilisk

# ISS TLE as printed in the sgp4 package's documentation (as tests/test_tle.py).
LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"


def _sso(**changes):
    values = dict(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0012,  # [km], [-]
                  inclination_deg=97.59, raan_deg=259.4, arg_periapsis_deg=30.0,  # [deg]
                  anomaly_type="true", true_anomaly_deg=45.0)  # [deg]
    values.update(changes)
    return OrbitIC(**values)


def test_elements_give_the_state_the_run_starts_from():
    """Classical elements become the very state the run computes from them."""
    from spacemissionstudio.engine import orbit_conversion
    from spacemissionstudio.engine.service import _orbit_ic_to_rv

    orbit = _sso()
    converted = orbit_conversion.to_cartesian(orbit)
    r_m, v_m_s = _orbit_ic_to_rv(orbit_conversion.central_body_mu("earth"), orbit)
    assert np.allclose(np.array(converted.position_km) * 1e3, np.ravel(r_m), rtol=0, atol=1e-6)  # [m]
    assert np.allclose(np.array(converted.velocity_km_s) * 1e3, np.ravel(v_m_s), rtol=0, atol=1e-9)  # [m/s]


@pytest.mark.parametrize("anomaly_type, field", [("true", "true_anomaly_deg"), ("mean", "mean_anomaly_deg")])
def test_elements_round_trip_through_the_state(anomaly_type, field):
    """Elements -> state -> elements gives the same orbit, with either anomaly."""
    from spacemissionstudio.engine import orbit_conversion

    orbit = _sso(anomaly_type=anomaly_type, **({"true_anomaly_deg": None, "mean_anomaly_deg": 45.0}
                                                if anomaly_type == "mean" else {}))
    back = orbit_conversion.to_classical(orbit_conversion.to_cartesian(orbit), anomaly_type=anomaly_type)
    assert back.anomaly_type == anomaly_type
    for name in ("semi_major_axis_km", "eccentricity", "inclination_deg", "raan_deg", "arg_periapsis_deg", field):
        assert getattr(back, name) == pytest.approx(getattr(orbit, name), abs=1e-6), name


def test_a_tle_converts_at_the_scenario_epoch():
    """A TLE becomes its SGP4 state at the scenario epoch, in EME2000."""
    from spacemissionstudio.engine import orbit_conversion, tle

    orbit = OrbitIC(type="tle", tle_line1=LINE1, tle_line2=LINE2)
    epoch = "2019-12-10T00:00:00"
    converted = orbit_conversion.to_cartesian(orbit, epoch_utc=epoch)
    state = tle.state_at(LINE1, LINE2, epoch)
    assert np.allclose(np.array(converted.position_km) * 1e3, state.r_m, atol=1e-6)  # [m]
    elements = orbit_conversion.to_classical(orbit, epoch_utc=epoch)
    assert elements.inclination_deg == pytest.approx(51.64, abs=0.1)  # [deg] the ISS's


def test_the_central_body_sets_mu():
    """About Mars, a circular orbit's speed is sqrt(mu_Mars / r)."""
    from spacemissionstudio.engine import orbit_conversion

    orbit = _sso(semi_major_axis_km=4000.0, eccentricity=0.0, inclination_deg=30.0)  # [km], [-], [deg]
    converted = orbit_conversion.to_cartesian(orbit, central_body="mars")
    speed_km_s = float(np.linalg.norm(converted.velocity_km_s))
    assert speed_km_s == pytest.approx(math.sqrt(orbit_conversion.central_body_mu("mars") / 4.0e6) / 1e3, rel=1e-9)


@pytest.mark.parametrize("orbit, to_type, kwargs, message", [
    (_sso(), "tle", {}, "nothing converts to a TLE"),
    (OrbitIC(type="tle", tle_line1=LINE1, tle_line2=LINE2), "cartesian", {}, "at the scenario epoch"),
    (OrbitIC(type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 12.0, 0.0]),  # [km], [km/s]
     "classical_elements", {}, "not an elliptical orbit"),
    (OrbitIC(type="tle", tle_line1=LINE1, tle_line2=LINE2), "cartesian",
     {"central_body": "mars", "epoch_utc": "2019-12-10T00:00:00"}, "Earth orbit"),
])
def test_what_cannot_be_converted_says_why(orbit, to_type, kwargs, message):
    """A TLE target, a TLE without an epoch, an escape trajectory and a TLE
    about another body are refused with the reason."""
    from spacemissionstudio.engine import orbit_conversion

    with pytest.raises(orbit_conversion.OrbitConversionError, match=message):
        orbit_conversion.convert(orbit, to_type, **kwargs)
