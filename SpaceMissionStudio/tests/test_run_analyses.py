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
"""The model analyses after a run (``analyses/run_geometry.py``,
``blinding.py``, ``shading.py``, ``exposure.py``, ``brightness.py``) on
geometry built by hand: blinding cones, a ray to a station through a
panel, array shading, atomic oxygen on a ram plate and sun hours on a
Sun-pointing face, and the brightness of a diffuse sphere and a flat plate
against Hostetler and Cowardin's Lambert sphere and a hand calculation."""

import math
from types import SimpleNamespace

import numpy as np
import pytest

from spacemissionstudio.analyses import blinding, brightness, exposure, shading
from spacemissionstudio.analyses.run_geometry import RunGeometry, mrp_to_dcm, run_geometry
from spacemissionstudio.config import registry
from spacemissionstudio.config.registry import Configuration
from spacemissionstudio.constants import ASTRONOMICAL_UNIT_M, EARTH_EQUATORIAL_RADIUS_M, SOLAR_FLUX_1AU_W_M2
from spacemissionstudio.engine.results import ResultSet, TimeSeries
from spacemissionstudio.model3d.equipment import MountedItem
from spacemissionstudio.model3d.geometry import rotation_matrix
from spacemissionstudio.model3d.raycast import Scene, ScenePart
from spacemissionstudio.schema.scenario import FacetConfig

R = EARTH_EQUATORIAL_RADIUS_M  # [m]
H = 500.0e3  # [m] altitude


def _geometry(sun_direction, n=1, sunlight=1.0, moon_n=None):
    """A spacecraft H above the point (R, 0, 0), attitude identity, the Sun
    1 AU away along ``sun_direction``."""
    t = np.arange(n, dtype=float)
    u = np.asarray(sun_direction, float) / np.linalg.norm(sun_direction)
    position = np.tile([R + H, 0.0, 0.0], (n, 1))
    return RunGeometry("sc", t, position, np.tile(np.eye(3), (n, 1, 1)), np.zeros((n, 3)), R,
                       np.tile(u * ASTRONOMICAL_UNIT_M + position[0], (n, 1)), moon_n, np.full(n, sunlight))


def _item(name, kind="star_tracker", boresight=(0, 0, 1), **kw):
    return MountedItem(name=name, kind=kind, source="equipment", part=kw.pop("part", ""),
                       position_b_m=np.asarray(kw.pop("position", (0.0, 0.0, 0.0)), float),
                       boresight_b=np.asarray(boresight, float), **kw)


def test_mrps_give_basilisks_direction_cosines():
    """sigma = tan(phi/4) e: 90 deg about z maps inertial x to body -y."""
    dcm = mrp_to_dcm(np.array([[0.0, 0.0, math.tan(math.pi / 8.0)]]))[0]
    assert dcm @ np.array([1.0, 0.0, 0.0]) == pytest.approx([0.0, -1.0, 0.0], abs=1e-12)
    assert dcm @ dcm.T == pytest.approx(np.eye(3), abs=1e-12)


def test_a_tracker_is_blinded_inside_its_cones_and_not_in_umbra():
    """Boresight +y; the Sun 29.6 deg off it (inside 30 deg plus its own
    0.27 deg radius) blinds, 30.4 deg does not; in umbra it does not. The
    Earth (centre along -x) 90 deg off +y blinds only with an exclusion
    over 90 deg minus its angular radius; two trackers, one blinded, are
    not all blinded."""
    tracker = _item("st-1", boresight=(0, 1, 0), exclusion_sun_deg=30.0)
    for angle, expected in ((29.6, 1.0), (30.4, 0.0)):
        a = math.radians(angle)
        series, _ = blinding.blinding_series(_geometry([math.sin(a), math.cos(a), 0.0]), [tracker])
        assert series[0].data[0, 0] == expected, angle
    a = math.radians(10.0)
    series, _ = blinding.blinding_series(_geometry([math.sin(a), math.cos(a), 0.0], sunlight=0.0), [tracker])
    assert series[0].data[0, 0] == 0.0
    earth_radius = math.asin(R / (R + H))  # [rad] 68.0 deg
    for exclusion, expected in ((89.0 - math.degrees(earth_radius), 0.0), (91.0 - math.degrees(earth_radius), 1.0)):
        limb = _item("st-2", boresight=(0, 1, 0), exclusion_earth_deg=exclusion)
        series, _ = blinding.blinding_series(_geometry([0, 0, 1]), [limb])
        assert series[0].data[0, 1] == expected, exclusion
    second = _item("st-3", boresight=(0, -1, 0), exclusion_sun_deg=30.0)
    series, notes = blinding.blinding_series(_geometry([0.1, 1.0, 0.0]), [tracker, second])
    by_name = {s.name: s for s in series}
    assert by_name["sc.blinding.st-1"].data[0, 3] == 1.0 and by_name["sc.blinding.all_star_trackers"].data[0, 0] == 0
    assert notes == []
    one = _item("st-4", boresight=(0, 0, 1), exclusion_moon_deg=5.0)
    assert "does not track the Moon" in blinding.blinding_series(_geometry([1, 0, 0]), [one])[1][0]


def test_a_ray_to_the_station_through_a_panel_is_obstructed():
    """The station straight below (-x); a panel across -x blocks the
    antenna's ray; outside the passes nothing is computed (0)."""
    geometry = _geometry([0, 0, 1], n=3)
    result = ResultSet(scenario_name="t")
    result.add(TimeSeries("gs.access_to_sc.has_access", geometry.time_s, ("has_access",), [[1.0], [0.0], [1.0]]))
    result.add(TimeSeries("gs.station.position_N", geometry.time_s, ("x", "y", "z"), np.tile([R, 0, 0], (3, 1))))
    panel = Scene([ScenePart("panel", "panel", {"width": 2.0, "length": 2.0, "thickness": 0.01},
                             rotation_matrix([0.0, 90.0, 0.0]), np.array([-1.0, 0.0, 0.0]))])
    antenna = _item("antenna", kind="antenna", boresight=(-1, 0, 0))
    series = blinding.obstruction_series(result, geometry, antenna, panel, ["gs"])
    assert series[0].data[:, 0].tolist() == [1.0, 0.0, 1.0]
    clear = Scene([ScenePart("panel", "panel", {"width": 2.0, "length": 2.0, "thickness": 0.01}, np.eye(3),
                             np.array([0.0, 0.0, 3.0]))])
    assert blinding.obstruction_series(result, geometry, antenna, clear, ["gs"])[0].data[:, 0].tolist() == [0, 0, 0]


def _box_and_shade():
    """A 1 m cube whose +z face carries cells, and a 1 x 0.5 m panel 1 m
    above half of it (the ray-casting test's configuration)."""
    scene = Scene([ScenePart("bus", "box", {"x": 1.0, "y": 1.0, "z": 1.0}, np.eye(3), np.zeros(3)),
                   ScenePart("shade", "panel", {"width": 0.5, "length": 1.0, "thickness": 0.01}, np.eye(3),
                             np.array([0.25, 0.0, 1.5]))])
    facets = [FacetConfig("bus: +z", 1.0, [0.0, 0.0, 1.0], [0.0, 0.0, 0.5], diffuse_coeff=0.5),
              FacetConfig("bus: -x", 1.0, [-1.0, 0.0, 0.0], [-0.5, 0.0, 0.0], diffuse_coeff=0.5)]
    return shading.FacetLight(scene, facets, 4096)


def test_array_shading_and_its_power_follow_the_hand_calculation():
    """The Sun straight above the cells (+z): half shaded, so 0.3 efficient
    cells of 1 m^2 give S x 0.3 x 0.5 with S at 1 AU; at 60 deg the shadow
    moves off and the power is S x 0.3 x cos 60."""
    light = _box_and_shade()
    cells = _item("cells", kind="solar_cell", part="bus", boresight=(0, 0, 1))
    for sun, shaded, power in (([0, 0, 1], 0.5, SOLAR_FLUX_1AU_W_M2 * 0.3 * 0.5),
                               ([math.sin(math.radians(60)), 0, math.cos(math.radians(60))], 0.0,
                                SOLAR_FLUX_1AU_W_M2 * 0.3 * 0.5)):
        series, notes = shading.shading_series(_geometry(sun), light, [cells], 0.3)
        assert series[0].data[0, 0] == pytest.approx(shaded, abs=0.02)
        assert series[1].data[0, -1] == pytest.approx(power, rel=0.04) and notes == []
    assert shading.shading_series(_geometry([0, 0, 1]), light, [cells], None)[1] == [
        "array shading: no power budget (cell efficiency): the power is not computed"]


def test_atomic_oxygen_on_a_ram_plate_and_sun_hours_on_a_sun_facing_face():
    """A ram-facing 1 m^2 face (-x here, flying along -x) for 3600 s at
    7.6 km/s relative to the air, in 1e-12 kg/m^3 of oxygen: a fluence of
    rho / m_O x v x 3600 s, in 1/cm^2; the Sun straight on +z, unshaded:
    one sun hour on it, none on -x. (No Earth rotation here: the central
    body is not the Earth.)"""
    light = _box_and_shade()
    light.scene = Scene([light.scene.parts[0]])  # no shade
    t = np.linspace(0.0, 3600.0, 61)
    geometry = _geometry([0, 0, 1], n=len(t))
    geometry.time_s = t
    result = ResultSet(scenario_name="t")
    result.add(TimeSeries("sc.atmosphere.density", t, ("density",), np.full((len(t), 1), 1e-12)))
    result.add(TimeSeries("sc.velocity_N", t, ("x", "y", "z"), np.tile([-7600.0, 0.0, 0.0], (len(t), 1))))
    series, notes = exposure.exposure_series(result, geometry, light, "moon")
    for one in series:
        result.add(one)
    rows = {row["face"]: row for row in exposure.totals(result, SimpleNamespace(name="sc"),
                                                        {"bus: -x": ("kapton_h", 3.0e-24)})}
    fluence = 1e-12 / exposure.OXYGEN_ATOM_KG * 7600.0 * 3600.0 * 1e-4  # [1/cm^2]
    assert rows["bus: -x"]["ao_fluence_cm2"] == pytest.approx(fluence, rel=1e-9)
    assert rows["bus: +z"]["ao_fluence_cm2"] == 0.0
    assert rows["bus: -x"]["erosion_um"] == pytest.approx(fluence * 3.0e-24 * 1e4)
    assert rows["bus: +z"]["sun_hours"] == pytest.approx(1.0, rel=1e-9)
    assert rows["bus: -x"]["sun_hours"] == 0.0 and "erosion_um" not in rows["bus: +z"]


class _Unshaded(shading.FacetLight):
    """A convex body: no facet shades another."""

    def shaded(self, direction_b, which=None):
        return np.zeros(len(self.facets) if which is None else len(list(which)))


def _site_result(geometry):
    result = ResultSet(scenario_name="t")
    result.add(TimeSeries("site.station.position_N", geometry.time_s, ("x", "y", "z"),
                          np.tile([R, 0.0, 0.0], (len(geometry.time_s), 1))))
    return result


def _dark_sun(depression_deg):
    """The Sun ``depression_deg`` below the site's horizon (the site's up is
    +x), so the phase angle at the spacecraft overhead is 90 - depression."""
    e = math.radians(depression_deg)
    return [-math.sin(e), math.cos(e), 0.0]


def test_a_diffuse_sphere_is_as_bright_as_the_lambert_sphere():
    """20 000 facets of a 2 m sphere with diffuse coefficient 0.3, the Sun
    10 deg below the horizon (phase 80 deg), 500 km overhead: the magnitude
    of Hostetler and Cowardin's Lambert sphere, within 0.01 mag."""
    count = 20000
    k = np.arange(count) + 0.5
    z = 1.0 - 2.0 * k / count
    phi = math.pi * (1.0 + math.sqrt(5.0)) * k
    normals = np.column_stack([np.sqrt(1 - z * z) * np.cos(phi), np.sqrt(1 - z * z) * np.sin(phi), z])
    facets = [FacetConfig(f"ball: f{i}", 4.0 * math.pi / count, n.tolist(), n.tolist(), diffuse_coeff=0.3)
              for i, n in enumerate(normals)]
    light = _Unshaded(None, facets, 1)
    geometry = _geometry(_dark_sun(10.0))
    series, notes = brightness.brightness_series(_site_result(geometry), geometry, light, [("site", 10.0)], 0.0)
    expected = brightness.lambert_sphere_magnitude(2.0, 0.3, H, math.radians(80.0))
    assert series[0].data[0, 0] == pytest.approx(expected, abs=0.01) and notes == []


def test_a_flat_plate_s_brightness_is_the_hand_calculation():
    """A 1 m^2 plate facing the site (-x), diffuse 0.5, the Sun 10 deg below
    the horizon: ratio = 0.5 x 1 x sin 10 deg x 1 / (pi H^2)."""
    light = _Unshaded(None, [FacetConfig("plate: +z", 1.0, [-1.0, 0.0, 0.0], [0, 0, 0], diffuse_coeff=0.5)], 1)
    geometry = _geometry(_dark_sun(10.0))
    series, _ = brightness.brightness_series(_site_result(geometry), geometry, light, [("site", 10.0)], 0.0)
    ratio = 0.5 * math.sin(math.radians(10.0)) / (math.pi * H ** 2)
    assert series[0].data[0, 0] == pytest.approx(brightness.SUN_MAGNITUDE - 2.5 * math.log10(ratio), abs=1e-9)


def test_the_depression_angle_sets_when_a_site_is_dark():
    """The Sun 10 deg below the horizon: dark by the default (0 deg,
    geometric sunset), not by 12 deg (set in a project configuration); a
    spacecraft in umbra or below the minimum elevation is not seen."""
    name = "analyses.observer_sun_depression_deg"
    light = _Unshaded(None, [FacetConfig("plate: +z", 1.0, [-1.0, 0.0, 0.0], [0, 0, 0], diffuse_coeff=0.5)], 1)
    geometry = _geometry(_dark_sun(10.0))
    result = _site_result(geometry)

    def seen(scenario=None, min_elevation=10.0, geometry=geometry):
        depression = registry.value(name, scenario)
        series, _ = brightness.brightness_series(result, geometry, light, [("site", min_elevation)], depression)
        return bool(np.isfinite(series[0].data[0, 0]))

    assert registry.default(name) == 0.0 and seen()
    assert not seen(SimpleNamespace(configuration=Configuration({name: 12.0})))
    assert seen(SimpleNamespace(configuration=Configuration({name: 8.0})))
    assert not seen(geometry=_geometry(_dark_sun(10.0), sunlight=0.0))
    assert brightness.brightness_series(result, geometry, light, [("nowhere", 0.0)], 0.0)[1] == [
        "brightness: no position recorded for nowhere"]


def test_a_run_without_attitude_has_no_geometry():
    """No attitude series: no run geometry (the analyses say so)."""
    result = ResultSet(scenario_name="t")
    result.add(TimeSeries("sc.position_N", [0.0], ("x", "y", "z"), [[R + H, 0.0, 0.0]]))
    assert run_geometry(result, "sc", "earth") is None


def test_the_analyses_series_give_timeline_events_with_their_traces():
    """A tracker blinded by the Sun for samples 2-4 (and so all trackers),
    the antenna obstructed for 1-2, the spacecraft visible for 5-6 at 4.2
    then 3.9 mag: one event each, found again from its trace, the
    brightest magnitude carried."""
    from spacemissionstudio.engine import events

    result = ResultSet(scenario_name="t")
    t = np.arange(8.0)
    blinded = np.zeros((8, 4))
    blinded[2:5, 0] = blinded[2:5, 3] = 1.0
    result.add(TimeSeries("sat.blinding.st-1", t, ("sun", "earth", "moon", "blinded"), blinded))
    result.add(TimeSeries("sat.blinding.all_star_trackers", t, ("all_blinded",), blinded[:, 3:]))
    result.add(TimeSeries("gs.access_to_sat.antenna_obstructed", t, ("antenna_obstructed",),
                          [[0], [1], [1], [0], [0], [0], [0], [0]]))
    magnitude = np.full((8, 1), np.nan)
    magnitude[5:7, 0] = [4.2, 3.9]
    result.add(TimeSeries("site.brightness_of_sat.visual_magnitude", t, ("visual_magnitude",), magnitude))
    found = {(e.kind, e.label): e for e in events.extract_events(result)}
    assert set(found) == {("blinding", "st-1 blinded"), ("blinding", "all star trackers blinded"),
                          ("obstruction", "antenna obstructed"), ("visible", "visible")}
    assert found[("blinding", "st-1 blinded")].detail == "by sun"
    assert (found[("obstruction", "antenna obstructed")].start_s, found[("obstruction", "antenna obstructed")].other) \
        == (1.0, "gs")
    assert found[("visible", "visible")].quantity("magnitude") == 3.9
    for event in found.values():
        span = events.trace_of(result, event)[0]
        assert (span.input("t_start"), span.input("t_end")) == (event.start_s, event.end_s)
