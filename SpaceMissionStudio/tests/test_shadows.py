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
"""engine.shadows and ``dynamics.shadowing_bodies`` (transparency plan,
Phase 6b): which bodies shadow a spacecraft from the Sun."""

import numpy as np
import pytest

from spacemissionstudio.engine import shadows

_EPOCH = "2030-01-01T00:00:00"
_BEHIND_MOON_KM = 20000.0  # [km] behind the Moon, away from the Sun: in its umbra (about 1640 km wide there)


def test_the_occulters_of_each_model():
    """The default keeps the bodies a run always had; every tracked body
    gives each other body its own eclipse module, and the bodies Basilisk's
    eclipse knows no radius for cannot shadow. The product of the fractions
    is the combined sunlight."""
    tracked = ["earth", "sun", "moon"]
    assert shadows.occulters("central_body", "earth", tracked) == (["earth"], [], [])
    assert shadows.occulters("tracked_bodies", "earth", tracked) == (["earth"], ["moon"], [])
    heliocentric = ["sun", "earth", "moon", "mars barycenter"]
    assert shadows.occulters("central_body", "sun", heliocentric) == (["earth", "moon", "mars barycenter"], [], [])
    assert shadows.occulters("tracked_bodies", "sun", heliocentric) == (["earth"], ["moon", "mars barycenter"], [])
    assert shadows.occulters("tracked_bodies", "eros", ["eros", "sun", "earth"], "eros") == (["eros"], ["earth"], [])
    assert shadows.occulters("tracked_bodies", "earth", ["earth", "sun", "eros"]) == (["earth"], [], ["eros"])
    assert shadows.combined_illumination([1.0, 0.3]) == pytest.approx(0.3)
    assert shadows.combined_illumination([0.5, 0.5]) == pytest.approx(0.25)
    assert shadows.combined_illumination([]) == 1.0


def _positions_km(epoch_utc: str):
    """The Moon's and the Sun's positions from the Earth [km], J2000, by
    SPICE directly (not through the run's own messages)."""
    from Basilisk.topLevelModules import pyswice

    from spacemissionstudio.engine import kernels, time_system

    paths = [str(status.path) for status in kernels.require_cached(kernels.DEFAULT_KERNELS[:2])]
    for path in paths:
        pyswice.furnsh_c(path)
    try:
        et = pyswice.new_doubleArray(1)
        pyswice.str2et_c(time_system.utc_iso_to_spice_string(epoch_utc), et)
        out = {}
        for body in ("MOON", "SUN"):
            position = pyswice.new_doubleArray(3)
            light_time = pyswice.new_doubleArray(1)
            pyswice.spkpos_c(body, pyswice.doubleArray_getitem(et, 0), "J2000", "NONE", "EARTH", position, light_time)
            out[body] = np.array([pyswice.doubleArray_getitem(position, i) for i in range(3)])  # [km]
    finally:
        for path in paths:
            pyswice.unload_c(path)
    return out["MOON"], out["SUN"]


def _behind_the_moon(shadowing: str | None):
    """A 5-minute run of a spacecraft 20 000 km behind the Moon, away from
    the Sun, orbiting the Earth; ``shadowing`` the project's choice."""
    from spacemissionstudio.config.registry import Configuration
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema import GravityConfig, OrbitIC, Scenario, SimSettings, SpacecraftConfig

    moon_km, sun_km = _positions_km(_EPOCH)
    away = (moon_km - sun_km) / np.linalg.norm(moon_km - sun_km)
    position_km = moon_km + _BEHIND_MOON_KM * away  # [km]
    speed_km_s = float(np.sqrt(398600.4418 / np.linalg.norm(position_km)))  # [km/s] about circular
    along = np.cross([0.0, 0.0, 1.0], position_km)
    velocity_km_s = speed_km_s * along / np.linalg.norm(along)
    scenario = Scenario(
        name="behind the moon", epoch_utc=_EPOCH,
        gravity=GravityConfig(central_body="earth", central_body_degree=0, third_body_perturbers=["sun", "moon"]),
        sim_settings=SimSettings(duration_days=300.0 / 86400.0, dynamics_task_rate_s=10.0),  # [day], [s]
        spacecraft=[SpacecraftConfig(name="sat-1", dry_mass_kg=100.0,
                                     orbit=OrbitIC(type="cartesian", position_km=list(position_km),
                                                   velocity_km_s=list(velocity_km_s)))])
    scenario.validate()
    if shadowing is not None:
        scenario.configuration = Configuration(overrides={"dynamics.shadowing_bodies": shadowing})
    service = SimulationService(scenario)
    service.build()
    return service.run()


@pytest.mark.requires_basilisk
def test_only_the_central_body_shadows_by_default():
    """With the default, a spacecraft in the Moon's shadow is lit: one
    eclipse module with the Earth alone, as before the choice existed; the
    run's provenance records no model."""
    result = _behind_the_moon(None)
    sunlight = result.series["sat-1.eclipse.illumination_factor"].data[:, 0]
    assert np.all(sunlight == 1.0)
    assert "models" not in result.provenance.to_dict()


@pytest.mark.requires_basilisk
def test_the_moon_shadows_a_spacecraft_behind_it_with_tracked_bodies():
    """With every tracked body, the same spacecraft is in the Moon's umbra
    throughout (sunlight 0), and the run's provenance names the model and
    the bodies that shadow."""
    result = _behind_the_moon("tracked_bodies")
    sunlight = result.series["sat-1.eclipse.illumination_factor"].data[:, 0]
    assert np.all(sunlight == pytest.approx(0.0, abs=1e-9))
    record = result.provenance.to_dict()["models"]["dynamics.shadowing_bodies"]
    assert record["model"] == "tracked_bodies" and record["bodies"] == ["earth", "moon"]
    assert record["cannot_shadow"] == []
    assert record["title"] == "Every tracked body"
