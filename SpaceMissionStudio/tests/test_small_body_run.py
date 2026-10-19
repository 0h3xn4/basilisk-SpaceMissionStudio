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

"""Runs around 433 Eros in Basilisk with the real NAIF ephemeris and the
NEAR shape model (installed by 'spacemissionstudio small-bodies --fetch';
CI installs them): Eros's frame, the polyhedral field's Jacobi integral,
the impact warning, and the message when the files are missing."""

from pathlib import Path

import numpy as np
import pytest

from spacemissionstudio.engine import polyhedron, small_bodies
from spacemissionstudio.schema import load_scenario

_TEMPLATES = Path(__file__).resolve().parent.parent / "spacemissionstudio" / "scenarios" / "templates"
_ROTATION_RATE = np.radians(1639.38864745) / 86400.0  # [rad/s] pck00010 BODY2000433_PM
_POLE_RA, _POLE_DEC = np.radians(11.35), np.radians(17.22)  # [rad] pck00010 BODY2000433_POLE_RA/DEC


pytestmark = pytest.mark.requires_basilisk


def _scenario(polyhedral: bool, hours: float, sma_km: float, eccentricity: float = 0.0):
    scenario = load_scenario(_TEMPLATES / "01_two_body_circular_orbit.json")
    scenario.epoch_utc = "2026-10-19T00:00:00"
    scenario.gravity.central_body = "eros"
    scenario.gravity.polyhedral_gravity = polyhedral
    scenario.sim_settings.duration_days = hours / 24.0  # [day]
    scenario.sim_settings.dynamics_task_rate_s = 10.0  # [s]
    scenario.sim_settings.record_interval_s = 60.0  # [s]
    orbit = scenario.spacecraft[0].orbit
    orbit.semi_major_axis_km = sma_km  # [km]
    orbit.eccentricity = eccentricity
    orbit.inclination_deg = 40.0  # [deg]
    orbit.raan_deg = 0.0  # [deg]
    scenario.validate()
    return scenario


def _run(scenario):
    from spacemissionstudio.engine.service import SimulationService

    service = SimulationService(scenario)
    return service, service.run()


def test_eros_turns_about_its_iau_pole_every_5_27_hours(real_small_body_files):
    """The run's Eros frame is pck00010's: the pole at RA 11.35, Dec 17.22
    deg, and a 1639.39 deg/day spin; the SPK and shape are in the run's
    provenance."""
    service, result = _run(_scenario(False, 6.0, 35.0))
    dcm = np.asarray(service._central_body_recorder.J20002Pfix).reshape(-1, 3, 3)
    t_s = service._central_body_recorder.times() * 1e-9
    pole = [np.cos(_POLE_DEC) * np.cos(_POLE_RA), np.cos(_POLE_DEC) * np.sin(_POLE_RA), np.sin(_POLE_DEC)]
    assert dcm[0][2] == pytest.approx(pole, abs=1e-9)
    turned = np.arccos(np.clip((np.trace(dcm[60] @ dcm[0].T) - 1.0) / 2.0, -1.0, 1.0))
    assert turned == pytest.approx(_ROTATION_RATE * (t_s[60] - t_s[0]), rel=1e-6)
    assert "spice:eros_1900_2100.bsp" in result.provenance.data_files
    position_n = result.series["sat-1.position_N"].data
    position_p = result.series["sat-1.position_P"].data
    assert np.linalg.norm(position_p, axis=1) == pytest.approx(np.linalg.norm(position_n, axis=1), rel=1e-12)
    assert result.series["sat-1.small_body.distance"].data[:, 0] == pytest.approx(35e3, rel=1e-6)


def test_in_the_polyhedral_field_the_jacobi_integral_is_constant(real_small_body_files):
    """Around a uniformly spinning body the energy in its frame (Jacobi
    integral) is conserved: within 1e-6 over 6 h with the shape's gravity,
    while the orbit's radius changes by kilometres; no false warnings."""
    service, result = _run(_scenario(True, 6.0, 35.0))
    assert result.warnings == []
    assert "shape_model" in result.provenance.data_files
    position_n = result.series["sat-1.position_N"].data
    velocity_n = result.series["sat-1.velocity_N"].data
    position_p = result.series["sat-1.position_P"].data
    radius = np.linalg.norm(position_p, axis=1)
    assert radius.max() - radius.min() > 1e3  # [m] the shape's field, not a point mass
    pole = np.array([np.cos(_POLE_DEC) * np.cos(_POLE_RA), np.cos(_POLE_DEC) * np.sin(_POLE_RA), np.sin(_POLE_DEC)])
    spin = pole * _ROTATION_RATE  # [rad/s]
    shape = service.small_body_shape
    jacobi = []
    for k in range(0, len(position_n), 15):
        relative = velocity_n[k] - np.cross(spin, position_n[k])
        jacobi.append(0.5 * relative @ relative - 0.5 * np.sum(np.cross(spin, position_n[k]) ** 2)
                      - shape.field(position_p[k], small_bodies.EROS.gm_m3_s2)[0])
    jacobi = np.array(jacobi)
    assert np.abs(jacobi - jacobi[0]).max() < 1e-6 * abs(jacobi[0])


def test_an_orbit_into_the_shape_is_reported_as_an_impact(real_small_body_files):
    """Periapsis 5 km from the centre: the spacecraft enters Eros and the
    run says when, as polyhedron.contains does for the recorded positions."""
    service, result = _run(_scenario(True, 3.0, 10.0, 0.5))
    hits = [w for w in result.warnings if "hit 433 Eros" in w]
    assert len(hits) == 1
    position_p = result.series["sat-1.position_P"].data
    assert service.small_body_shape.contains(position_p).any()
    assert isinstance(service.small_body_shape, polyhedron.Polyhedron)


def test_without_the_ephemeris_the_run_says_how_to_get_it(tmp_path, monkeypatch):
    """No Eros kernel installed: the run stops before it starts and names
    the download."""
    from spacemissionstudio.engine.service import SimulationService, SimulationServiceError

    monkeypatch.setattr(small_bodies, "DEFAULT_DIR", tmp_path / "none")
    monkeypatch.setattr(small_bodies, "SYSTEM_DIR", tmp_path / "none")
    with pytest.raises(SimulationServiceError, match="small-bodies --fetch"):
        SimulationService(_scenario(False, 1.0, 35.0)).run()
