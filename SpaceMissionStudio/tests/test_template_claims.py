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

"""Each bundled template, run for real, does what its description says.

Several templates shipped claims their own setup could not deliver (16
failed at its first command, 19 had no contact for 8 h, 20's sensor never
saw the Sun, 07's battery never moved). The only all-template Basilisk
test strips the Mission Sequence and runs two minutes, so none of that
was caught. These tests run each template as shipped -- shortened only
where the claim allows -- and check its headline claim.
"""

from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.schema import load_scenario

pytestmark = pytest.mark.requires_basilisk

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"


def _template(prefix):
    return load_scenario(next(_TEMPLATES_DIR.glob(f"{prefix}_*.json")))


def _run(scenario, duration_days=None):
    from spacemissionstudio.engine.service import SimulationService

    if duration_days is not None:
        scenario.sim_settings.duration_days = duration_days
    return SimulationService(scenario).run()


def _at(series, t_s, column=0):
    return float(series.data[int(np.argmin(np.abs(series.time_s - t_s))), column])


def test_16_lambert_transfer_lands_on_its_target():
    """Used to fail at its first command (a report before any propagate);
    the description promises arrival within about 2 m."""
    from spacemissionstudio.engine.mission_engine import MissionEngine

    scenario = _template("16")
    _result, summary = MissionEngine(scenario).run()
    assert [r.label for r in summary.reports] == ["Before transfer", "After transfer (should match target_position_m)"]
    target = np.array(scenario.mission_sequence[2].params["target_position_m"])  # [m]
    assert np.linalg.norm(summary.reports[1].values["sat-1.position_N"] - target) < 5.0  # [m]


def test_19_first_berlin_pass_comes_early_and_switches_the_pointing_mode():
    """Used to start at midnight UTC: no contact for the first 8 h."""
    result = _run(_template("19"), duration_days=25.0 / 1440.0)  # [day] the first pass only
    access = result.series["berlin-gs.access_to_leo-comms-1.has_access"]
    visible = access.data[:, 0] > 0.5
    assert visible.any()
    first_s = float(access.time_s[np.argmax(visible)])  # [s]
    assert 5 * 60 <= first_s <= 15 * 60
    mode = result.series["leo-comms-1.comms_pointing.active_mode"]
    assert _at(mode, first_s + 120.0) == 1.0  # pointing at the station during the pass
    assert _at(mode, first_s - 120.0) == 0.0  # Sun pointing before it


def test_20_thermal_sensor_heats_in_sunlight_and_cools_in_eclipse():
    """therm-1 used to face +X, edge-on to the Sun once Sun-pointed."""
    result = _run(_template("20"), duration_days=70.0 / 1440.0)  # [day] first sunlit arc and eclipse
    therm = result.series["sat-1.sensor.therm-1"]
    start, sunlit_end, eclipse_end = _at(therm, 60.0), _at(therm, 22 * 60.0), _at(therm, 57 * 60.0)  # [C]
    assert sunlit_end > start + 10.0
    assert eclipse_end < sunlit_end - 10.0
    motor = result.series["sat-1.actuator.rw-1.motor_temperature"].data[:, 0]  # [C]
    assert 0.01 < motor.max() - 20.0 < 0.2  # "only ~0.05 C above its 20 C ambient"


def test_07_battery_charges_in_sunlight_and_drains_in_eclipse():
    """Used to start full with a 0 W bus load: flat at 80 Wh all run."""
    result = _run(_template("07"), duration_days=60.0 / 1440.0)  # [day]
    charge = result.series["sat-1.battery_charge"]
    assert _at(charge, 20 * 60.0) > _at(charge, 0.0) + 5.0  # [Wh] charging
    assert _at(charge, 55 * 60.0) < _at(charge, 25 * 60.0) - 3.0  # [Wh] eclipse at the 12 W bus load
    sun = result.series["sat-1.sun_heading_body"]
    assert sun.data[-1, 2] > 0.99  # +Z settled on the Sun


def test_03_geo_slot_is_held_in_longitude_and_inclination():
    """A real 45-day run: east-west burns at days 12.5, 21.4, 31.1, 36.9, north-
    south burns at days 16.4 and 30.4. 32 days covers three and two of them."""
    result = _run(_template("03"), duration_days=32.0)  # [day]
    prefix = "geo-sat-1.geo_station_keeping."
    longitude = np.degrees(result.series[prefix + "longitude"].data[:, 1])  # [deg] one-day fit
    assert 9.945 < np.nanmin(longitude) and np.nanmax(longitude) < 10.055  # [deg] box 10 +/- 0.05
    inclination = np.degrees(result.series[prefix + "inclination"].data[:, 0])  # [deg]
    assert inclination[0] < 1e-3  # starts in Earth's true equator
    assert inclination.max() < 0.053  # [deg] limit 0.05
    burns = result.series[prefix + "burn_on"].data > 0.5
    starts = [np.count_nonzero(np.diff(burns[:, col].astype(int)) == 1) for col in (0, 1)]
    assert starts == [3, 2]  # [east-west, north-south]


def test_10_uncontrolled_spacecraft_drifts_under_gravity_gradient():
    """Its attitude used to be unrecorded (only visible in Vizard)."""
    result = _run(_template("10"), duration_days=2.0 / 24.0)  # [day]
    sigma = result.series["sat-1.attitude_sigma_BN"]
    assert np.linalg.norm(sigma.data[0]) < 1e-6
    assert np.linalg.norm(sigma.data[-1]) > 0.1


def test_12_thrusters_dump_wheel_momentum():
    """Template 12 fires its thrusters three times and slows the first wheel by
    over 10 %."""
    result = _run(_template("12"))
    firing = result.series["sat-1.thruster_on_time"].data.max(axis=1) > 0.0
    assert np.count_nonzero(np.diff(firing.astype(int)) == 1) == 3  # "three in the first 4 minutes"
    speeds = result.series["sat-1.rw_speeds"].data  # [rad/s]
    assert speeds[-1, 0] < 0.9 * speeds[0, 0]


def test_17_fuel_tank_drains_about_as_described():
    """On an earlier 10 kg*m^2 bus the thrusters' on-times stayed under their
    20 ms minimum: no propellant used at all."""
    result = _run(_template("17"))
    fuel = result.series["sat-1.fuel_mass_remaining"].data[:, 0]
    assert 0.1e-3 <= fuel[0] - fuel[-1] <= 1.0e-3  # [kg] "about 0.3 g of the 0.5 kg"


def test_11_thrusters_settle_the_attitude_within_a_few_minutes():
    """Template 11 fires real pulses and settles within a few degrees in four
    minutes."""
    result = _run(_template("11"), duration_days=4.0 / 1440.0)  # [day]
    assert result.series["sat-1.thruster_on_time"].data.max() > 0.02  # [s] real pulses, above the minimum on-time
    sigma = result.series["sat-1.attitude_sigma_BN"]
    assert np.linalg.norm(sigma.data[-1]) < 0.03  # within a few degrees ("about 2 minutes")


def test_08_prograde_burn_raises_the_orbit_on_the_far_side():
    """Template 08's 50 m/s prograde burn raises the semi-major axis by 60 to
    100 km and makes the orbit elliptical."""
    from spacemissionstudio.engine.mission_engine import MissionEngine

    _result, summary = MissionEngine(_template("08")).run()
    before, after = summary.reports
    a_before = before.values["sat-1.orbit_elements.semi_major_axis"][0]  # [m]
    a_after = after.values["sat-1.orbit_elements.semi_major_axis"][0]  # [m]
    # [m] vis-viva: +50 m/s prograde at 400 km raises a by ~88 km (osculating
    # snapshots, after half a day of drag and J2: ~76 km in a real run)
    assert 60e3 < a_after - a_before < 100e3
    assert after.values["sat-1.orbit_elements.eccentricity"][0] > 0.01  # now an ellipse


def test_13_torque_rods_steer_the_wheels_to_their_target_speeds():
    """Template 13's torque rods bring every wheel within 0.5 RPM of its
    target."""
    scenario = _template("13")
    result = _run(scenario)
    speeds_rpm = result.series["sat-1.rw_speeds"].data[-1] * 60.0 / (2.0 * np.pi)  # [RPM]
    targets_rpm = np.array(scenario.spacecraft[0].magnetic_momentum_management.wheel_speed_biases_rad_s) \
        * 60.0 / (2.0 * np.pi)  # [RPM]
    assert np.abs(speeds_rpm - targets_rpm).max() < 0.5  # [RPM] "within ~0.5 RPM"


def test_14_css_estimate_settles_on_the_sun_axis_and_is_lost_in_the_shadow():
    """The estimate settles near [0, 0, 1]; in Earth's shadow (minutes
    10 to 44) every sensor reads zero and the estimate is [0, 0, 0], and
    out of it the estimate is back at the end of the orbit."""
    result = _run(_template("14"))
    estimate = result.series["sat-1.sun_heading_body_estimated"]
    assert estimate.data[-1][2] / np.linalg.norm(estimate.data[-1]) > 0.98  # near [0, 0, 1]
    illumination = result.series["sat-1.eclipse.illumination_factor"]
    dark = illumination.data.ravel() == 0.0
    shadow_min = illumination.time_s[dark] / 60.0  # [min]
    assert 9.0 < shadow_min.min() < 11.0 and 43.0 < shadow_min.max() < 45.0  # [min]
    in_shadow = np.isin(estimate.time_s, illumination.time_s[dark])
    assert in_shadow.any() and not estimate.data[in_shadow].any()
    for i in range(1, 9):
        sensor = result.series[f"sat-1.sensor.css-{i}"]
        assert not sensor.data[np.isin(sensor.time_s, illumination.time_s[dark])].any()


def test_14_earths_albedo_pulls_the_estimate_off_the_sun():
    """With "Reflected sunlight on the sun sensors" on, the estimate in
    sunlight is about 16 deg off the Sun (median), up to 27 deg, and +Z
    follows it (the description's "Try changing" claim)."""
    scenario = _template("14")
    scenario.gravity.albedo = True
    result = _run(scenario)
    true = result.series["sat-1.sun_heading_body"]
    estimate = result.series["sat-1.sun_heading_body_estimated"].data
    lit = (np.linalg.norm(estimate, axis=1) > 0.0) & (result.series["sat-1.eclipse.illumination_factor"].data.ravel()
                                                      == 1.0)
    error_deg = np.degrees(np.arccos(np.clip(np.einsum(
        "ij,ij->i", estimate[lit] / np.linalg.norm(estimate[lit], axis=1)[:, None],
        true.data[lit] / np.linalg.norm(true.data[lit], axis=1)[:, None]), -1.0, 1.0)))
    assert 13.0 < np.median(error_deg) < 19.0 and 22.0 < error_deg.max() < 30.0  # [deg] "about 16", "up to 27"
    off_sun_deg = np.degrees(np.arccos(np.clip(true.data[:, 2] / np.linalg.norm(true.data, axis=1), -1.0, 1.0)))
    assert 22.0 < off_sun_deg[true.time_s > 600.0].max() < 30.0  # [deg] +Z follows the estimate


def test_21_off_centre_array_loads_the_wheels_unless_torque_rods_unload_them():
    """A real run: rods-off stores ~1.7 N*m*s by the end of the day (1.72,
    rw-x -815 RPM), rods-on keeps its wheels under ~20 RPM (18.7): January
    2030 on NASA MSFC's 50th-percentile prediction, Cd 3.0 (re-measured
    after F-07 and F-09, compliance/drag_remeasure.md)."""
    result = _run(_template("21"))
    js = 12.0 / (6000.0 * np.pi / 30.0)  # [kg*m^2] HR12 12 N*m*s at 6000 RPM
    stored = {name: np.linalg.norm(result.series[f"{name}.rw_speeds"].data[-1]) * js  # [N*m*s]
              for name in ("rods-off", "rods-on")}
    assert 1.5 < stored["rods-off"] < 1.9  # [N*m*s] "about 1.7 N*m*s stored by the end"
    rods_on_rpm = result.series["rods-on.rw_speeds"].data[-1] * 30.0 / np.pi  # [RPM]
    assert np.abs(rods_on_rpm).max() < 25.0  # [RPM] "stay under ~20 RPM"
    for name in ("rods-off", "rods-on"):
        sun = result.series[f"{name}.sun_heading_body"]
        assert sun.data[sun.time_s > 600.0, 2].min() > 0.99  # still Sun-pointed


def test_22_starter_has_four_berlin_passes_and_a_sun_synchronous_plane():
    """The starter's description: four Berlin passes in its day, the first
    10-18 min in, and the mean orbit plane turning ~1 deg a day."""
    result = _run(_template("22"))
    access = result.series["berlin-gs.access_to_my-sat.has_access"]
    visible = np.concatenate([[0], (access.data[:, 0] > 0.5).astype(int), [0]])
    starts = access.time_s[np.flatnonzero(np.diff(visible) == 1)]  # [s]
    assert len(starts) == 4
    assert 9 * 60 <= starts[0] <= 12 * 60  # [s]
    raan = result.series["my-sat.orbit_elements_mean.raan"]
    rate_deg_day = np.degrees(raan.data[-1, 0] - raan.data[0, 0]) / (raan.time_s[-1] / 86400.0)  # [deg/day]
    assert 0.9 < rate_deg_day < 1.1  # Sun-synchronous: 0.986 deg/day


def test_23_mission_sequence_reports_at_the_pass_and_the_wheels_unload():
    """Reports at pass start and end (about 10 and 18 min in); the wheels
    spin up to turn to the Sun, then the torque rods bring them back."""
    from spacemissionstudio.engine.mission_engine import MissionEngine

    result, summary = MissionEngine(_template("23")).run()
    assert [r.label for r in summary.reports] == ["Pass start", "Pass end"]
    start_s, end_s = (r.t_s for r in summary.reports)  # [s]
    assert 9 * 60 <= start_s <= 12 * 60 and 16 * 60 <= end_s <= 20 * 60
    margin = summary.reports[0].values["berlin-gs.access_to_smallsat-1.link_margin_db"][0]  # [dB]
    assert 8.0 < margin < 14.0  # "11 dB at the 10 deg edge of the pass"
    rpm = np.abs(result.series["smallsat-1.rw_speeds"].data) * 30.0 / np.pi  # [RPM]
    assert 200.0 < rpm.max() < 400.0  # "up to ~300 RPM"
    assert rpm[-1].max() < 5.0  # [RPM] "back near zero"
    assert result.series["smallsat-1.sun_heading_body"].data[-1, 2] > 0.99  # Sun-pointed


def test_24_mean_element_control_holds_tens_of_metres():
    """Within ~65 m after the first day, at a few tenths of a m/s; three of
    its fourteen days."""
    result = _run(_template("24"), duration_days=3.0)  # [day]
    error = result.series["follower-1.phasing_keeping.separation_error"]
    error_m = np.radians(error.data[:, 0]) * 6928.0e3  # [m] along-track arc on the chief's orbit
    assert np.abs(error_m[error.time_s > 86400.0]).max() < 80.0  # [m]
    delta_v = result.series["follower-1.phasing_keeping.delta_v"].data[-1, 0]  # [m/s]
    assert 0.1 < delta_v < 0.5  # [m/s] 0.20 the first day, 0.46 in 14 days
    force = result.series["follower-1.phasing_keeping.force"].data  # [N] commanded, applied
    assert force[:, 0].max() < 0.01  # requests of a few mN, under the 50 mN thruster


def test_26_the_memory_overflows_between_berlin_pass_groups_and_the_patch_link_holds():
    """The first day: the 3 Gbit memory is full by about 12 h in and data
    is lost; Berlin's link closes throughout its passes, with ~16 dB at the
    best and ~3.7 dB at the 10 deg edge, 65 deg off the patch's boresight."""
    result = _run(_template("26"), duration_days=1.0)  # [day]
    stored = result.series["eo-sat.data_handling.stored"]
    full = stored.time_s[stored.data[:, 0] > 3.0e9 - 0.1e9]  # [s] within 0.1 Gbit of the capacity
    assert full.size and 10.0 * 3600.0 < full[0] < 13.0 * 3600.0
    assert result.series["eo-sat.data_handling.data_lost"].data[-1, 0] > 0.0
    pair = "berlin-gs.access_to_eo-sat"
    margin = result.series[f"{pair}.link_margin_db"].data[:, 0]  # [dB]
    assert 15.0 < np.nanmax(margin) < 17.5 and 2.5 < np.nanmin(margin) < 4.5
    angle = result.series[f"{pair}.antenna_off_boresight"].data[:, 0]  # [deg]
    assert 60.0 < angle[np.nanargmin(margin)] < 68.0
    access = result.series[f"{pair}.has_access"].data[:, 0]
    assert np.array_equal(result.series[f"{pair}.link_closed"].data[:, 0], access)


def test_27_the_wings_ring_at_their_coupled_mode_and_the_pointing_settles():
    """The turn to the Sun swings each wing ~0.07 deg, ringing at ~0.26 Hz
    (above its hub-fixed 0.2 Hz) and below 0.001 deg within ~4.3 min; the
    Sun is within 0.1 deg after ~7.1 min; each wing gives up to ~980 W.
    The first 15 minutes, all in sunlight."""
    result = _run(_template("27"), duration_days=0.01)  # [day]
    deflection = result.series["flex-sat.solar_array.wing-1.deflection"]
    theta_deg = np.degrees(deflection.data[:, 0])
    assert 0.05 < np.abs(theta_deg).max() < 0.08  # [deg]
    assert np.allclose(theta_deg, -np.degrees(result.series["flex-sat.solar_array.wing-2.deflection"].data[:, 0]),
                       atol=0.002)  # [deg] the two wings swing as a mirror pair
    t = deflection.time_s
    above = t[np.abs(theta_deg) > 0.001]  # [s]
    assert 3.5 * 60.0 < above[-1] < 5.0 * 60.0
    window = (t > 5.0) & (t < 120.0)  # [s] the ringing, less its slow drift
    ringing = theta_deg[window] - np.convolve(theta_deg[window], np.ones(41) / 41, mode="same")
    crossings = t[window][30:-30][np.nonzero(np.diff(np.sign(ringing[30:-30])) != 0)[0]]
    assert 0.24 < 1.0 / (2.0 * np.mean(np.diff(crossings))) < 0.28  # [Hz]
    heading = result.series["flex-sat.sun_heading_body"]
    unit = heading.data / np.linalg.norm(heading.data, axis=1)[:, None]
    off_sun_deg = np.degrees(np.arccos(np.clip(unit[:, 2], -1.0, 1.0)))
    assert 6.5 * 60.0 < heading.time_s[off_sun_deg > 0.1][-1] < 7.7 * 60.0  # [s]
    power = result.series["flex-sat.solar_array.wing-1.power"].data[:, 0]  # [W]
    assert 960.0 < power.max() < 1000.0


def test_28_the_model_s_center_of_mass_offset_drives_the_y_wheel():
    """The model gives 300 kg and a center of mass [4.8, 0, -6.3] cm from
    B. The turn to the Sun takes the wheels up to ~850 RPM and ends within
    0.1 deg after ~7 min; then sunlight, pushing 4.8 cm off the center of
    mass, drifts rw-y ~-2.1 RPM an orbit, to ~-6.5 RPM after three orbits.
    The same run with the center of mass put back at B ends near +0.3 RPM,
    so the drift is the offset's."""
    scenario = _template("28")
    spacecraft = scenario.spacecraft[0]
    assert spacecraft.dry_mass_kg == pytest.approx(300.0)
    np.testing.assert_allclose(spacecraft.center_of_mass_b_m, [0.0482, 0.0, -0.0627], atol=1e-4)  # [m]
    result = _run(scenario)
    rpm = result.series["octa-sat.rw_speeds"].data * 30.0 / np.pi  # [RPM]
    assert 750.0 < np.abs(rpm).max() < 950.0
    heading = result.series["octa-sat.sun_heading_body"]
    unit = heading.data / np.linalg.norm(heading.data, axis=1)[:, None]
    off_sun_deg = np.degrees(np.arccos(np.clip(unit[:, 2], -1.0, 1.0)))
    assert 6.0 * 60.0 < heading.time_s[off_sun_deg > 0.1][-1] < 8.0 * 60.0  # [s]
    orbit_s = 5739.0  # [s] at 550 km
    wheels = result.series["octa-sat.rw_speeds"]
    for orbits, expected_rpm in ((1, -2.1), (2, -4.3), (3, -6.5)):
        assert _at(wheels, orbits * orbit_s, column=1) * 30.0 / np.pi == pytest.approx(expected_rpm, abs=0.4)

    centred = _template("28")
    centred.spacecraft[0].center_of_mass_b_m = [0.0, 0.0, 0.0]  # [m]
    centred_rpm = _run(centred).series["octa-sat.rw_speeds"].data[-1, 1] * 30.0 / np.pi  # [RPM]
    assert 0.0 < centred_rpm < 1.5


def _roe_flight(result, name="follower-1"):
    """Days, the ROE error box (|a da|, |a dlambda|, |a de|, |a di|) [m],
    delta-V [m/s], closest radial/cross-track approach [m] and ROE [m]."""
    error = result.series[f"{name}.roe_formation.roe_error"]
    e = error.data
    box = np.c_[np.abs(e[:, 0]), np.abs(e[:, 1]), np.hypot(e[:, 2], e[:, 3]), np.hypot(e[:, 4], e[:, 5])]
    return (error.time_s / 86400.0, box, result.series[f"{name}.roe_formation.delta_v"].data[:, 0],
            result.series[f"{name}.roe_formation.min_rn_separation"].data[:, 0],
            result.series[f"{name}.roe_formation.roe"].data)


def _dv_at(day, dv, when):
    return float(dv[int(np.argmin(np.abs(day - when)))])


def test_29_the_follower_moves_to_a_passively_safe_helix_and_holds_it():
    """Held 2 km behind to day 1; the e/i vectors reach 300 m within 5 h
    while a_dlambda slips to ~4 km behind (eclipse spreads the burns), and
    a drift closes it by day 2.5. The closest approach is 0 m while
    behind, 147 m between the cross-track burns, then 292 m or more from
    day 1.2. 0.56 m/s for the move, 0.026 m/s to hold it to day 4, within
    13 m along-track."""
    day, box, dv, margin, roe_m = _roe_flight(_run(_template("29")))
    before = day < 1.0
    assert np.all(np.abs(roe_m[before, 1] + 2000.0) < 5.0)  # [m] held 2 km behind
    assert np.all(margin[before] < 1.0)  # [m] the orbits cross
    shaped = day >= 1.0 + 5.0 / 24.0
    assert np.all(np.abs(np.hypot(roe_m[shaped, 2], roe_m[shaped, 3]) - 300.0) < 11.0)  # [m] |a de|
    assert np.all(np.abs(np.hypot(roe_m[shaped, 4], roe_m[shaped, 5]) - 300.0) < 11.0)  # [m] |a di|
    assert -4100.0 < roe_m[:, 1].min() < -3800.0  # [m] the slip
    assert 140.0 < margin[(day > 1.15) & (day < 1.17)].min() < 155.0  # [m] between the cross-track burns
    assert margin[day >= 1.2].min() > 290.0  # [m]
    settled = day >= 2.5
    assert box[settled, 1].max() < 15.0  # [m] a dlambda
    assert _dv_at(day, dv, 2.5) == pytest.approx(0.56, abs=0.02)  # [m/s]
    assert dv[-1] - _dv_at(day, dv, 2.5) == pytest.approx(0.026, abs=0.01)  # [m/s]


def test_29_continuous_law_and_a_zero_phase_helix():
    """Continuous: on target by day 1.4, within 3 m from day 2 (still
    converging at 1.4: 7 to 9 m there, by platform), 1.85 m/s in
    all. A 0 deg phase (dix nonzero, which J2 turns): holding from day 2.5
    costs about three times the 90 deg helix's 0.026 m/s."""
    continuous = _template("29")
    continuous.spacecraft[1].roe_formation.control_law = "continuous"
    day, box, dv, _margin, _roe = _roe_flight(_run(continuous))
    outside = (day >= 1.0) & np.any(box > np.array([6.0, 20.0, 10.0, 10.0]), axis=1)  # [m] 3 x the da tolerance
    assert day[outside].max() < 1.45  # [day]
    assert box[day >= 2.0].max() < 3.0  # [m]
    assert dv[-1] == pytest.approx(1.85, abs=0.1)  # [m/s]

    zero_phase = _template("29")
    zero_phase.spacecraft[1].roe_formation.targets[1].roe_m = [0.0, 0.0, 300.0, 0.0, 300.0, 0.0]  # [m]
    day, _box, dv, _margin, _roe = _roe_flight(_run(zero_phase))
    assert 2.0 < (dv[-1] - _dv_at(day, dv, 2.5)) / 0.026 < 4.5


def _opnav_flight(result):
    prefix = "probe-1.optical_navigation."
    error = result.series[prefix + "position_error"]
    return (error.time_s / 86400.0, error.data, result.series[prefix + "position_3sigma"].data,
            result.series[prefix + "measurement_error"].data[:, 3],
            result.series[prefix + "measurement_state"].data[:, 0], result.series[prefix + "measurement"].data)


def test_30_the_filter_converges_from_mars_images():
    """From 68 km off to under 2 km by day 1 (1.6 km median after it), up
    to 12 km just after each night-side stretch, inside the filter's
    3-sigma for 94 % of the axis samples; one image alone 56 km (median);
    62 % of the images used; the disk 110 to 152 px in radius."""
    day, error, sigma3, single, state, disk = _opnav_flight(_run(_template("30")))
    assert error[0, 3] == pytest.approx(68.2e3, rel=0.01)  # [m] the seeded start
    after = day >= 1.0
    assert error[np.searchsorted(day, 1.0), 3] < 2.0e3  # [m]
    assert np.median(error[after, 3]) < 2.5e3  # [m]
    assert error[after, 3].max() < 20.0e3  # [m]
    assert np.mean(np.abs(error[:, :3]) <= sigma3) > 0.9
    assert 45.0e3 < np.nanmedian(single) < 70.0e3  # [m]
    assert 0.55 < np.mean(state == 0) < 0.7
    assert 105.0 < np.nanmin(disk[:, 2]) and np.nanmax(disk[:, 2]) < 160.0  # [px]


def test_30_without_pixel_noise_every_image_gives_the_true_position():
    """With centre and radius noise at 0 every used image gives the true
    position (pixelLineConverter inverts the camera model exactly); with
    the largest phase angle at 180 deg every image is used."""
    scenario = _template("30")
    camera = scenario.spacecraft[0].optical_navigation
    camera.center_noise_px = camera.radius_noise_px = 0.0  # [px]
    camera.max_phase_angle_deg = 180.0  # [deg]
    _day, _error, _sigma3, single, state, _disk = _opnav_flight(_run(scenario))
    assert np.all(state == 0)
    assert np.nanmax(single) < 1.0e-3  # [m]


def _landmark_flight(result):
    prefix = "probe-1.landmark_navigation."
    error = result.series[prefix + "position_error"]
    return (error.time_s, error.data, result.series[prefix + "position_3sigma"].data,
            result.series[prefix + "landmarks_seen"].data[:, 0], result.series[prefix + "residual_rms"].data[:, 0],
            result.series["probe-1.small_body.distance"].data[:, 0])


def test_31_the_filter_finds_the_orbit_from_eros_landmarks(real_small_body_files):
    """5.5 m after the first image, 0.35 m median after, up to 4.8 m just
    after the night-side stretches, inside the filter's 3-sigma; about 18
    landmarks per image and none in 22 of 289; 0.28 px residuals; the
    probe between 35.0 and 38.0 km from the centre."""
    _t, error, sigma3, seen, residual, distance = _landmark_flight(_run(_template("31")))
    assert error[0, 3] == pytest.approx(5.5, abs=0.1)  # [m] after the first image
    assert np.median(error[1:, 3]) == pytest.approx(0.35, abs=0.05)  # [m]
    assert error[1:, 3].max() == pytest.approx(4.8, abs=0.2)  # [m]
    assert np.mean(np.abs(error[:, :3]) <= sigma3) > 0.99
    assert np.median(seen) == 18 and np.sum(seen == 0) == 22 and len(seen) == 289
    assert np.nanmedian(residual) == pytest.approx(0.28, abs=0.01)  # [px]
    assert distance.min() == pytest.approx(35.0e3, rel=1e-3) and distance.max() == pytest.approx(38.0e3, abs=100.0)


def test_31_one_pixel_of_noise_shows_in_the_residuals_and_the_error(real_small_body_files):
    """Added pixel noise 1 px: residuals of about 1 px (hypot(0.29, 1)) and
    a median error of about 5 m over the first half day (5.1 m seen)."""
    scenario = _template("31")
    scenario.spacecraft[0].landmark_navigation.pixel_noise_px = 1.0  # [px]
    _t, error, _sigma3, _seen, residual, _distance = _landmark_flight(_run(scenario, duration_days=0.5))
    assert np.nanmedian(residual) == pytest.approx(1.04, abs=0.1)  # [px]
    assert np.median(error[1:, 3]) == pytest.approx(5.1, abs=0.5)  # [m]
