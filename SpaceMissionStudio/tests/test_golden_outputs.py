"""The regression baseline (docs/transparency_audit.md, Phase 1a): every
template gives the outputs stored in ``tests/golden/``. See
``tests/golden_capture.py`` for what is captured and how it is compared.

A failure lists each output that changed. If the change is meant, record
each changed number in ``docs/changes.md`` (before and after) and rewrite the
baseline with ``python scripts/update_golden_outputs.py --write``.
"""

import copy
import json
import math

import pytest

import golden_capture

pytestmark = pytest.mark.requires_basilisk


# About a minute or more each here (their budgets solve the re-entry), so
# "slow" as the repository marks such tests; CI runs them.
_SLOW = {"03_geo_station_keeping", "05_formation_flying_phasing", "24_formation_mean_element_control",
         "29_roe_formation_helix"}


@pytest.mark.parametrize("path", [pytest.param(p, marks=pytest.mark.slow) if p.stem in _SLOW else p
                                  for p in golden_capture.template_paths()], ids=lambda p: p.stem)
def test_every_template_gives_its_recorded_outputs(path, request):
    """Each template, run as ``spacemissionstudio run`` runs it (capped at
    6 hours of simulated time), with its lifetime, budget, Monte Carlo batch
    and Explain text, matches its stored fingerprint."""
    if path.stem.startswith("31_"):
        request.getfixturevalue("real_small_body_files")  # Eros needs the installed kernel, as its other tests do
    stored = golden_capture.GOLDEN / f"{path.stem}.json"
    golden = json.loads(stored.read_text(encoding="utf-8"))
    problems = golden_capture.compare(golden, golden_capture.capture(path))
    assert not problems, f"{len(problems)} output(s) of {path.name} changed:\n" + "\n".join(problems[:200])


def test_every_template_has_a_recorded_fingerprint():
    """No template is left out of the baseline, and none is recorded that no longer exists."""
    templates = {p.stem for p in golden_capture.template_paths()}
    recorded = {p.stem for p in golden_capture.GOLDEN.glob("*.json")}
    assert templates == recorded


def _fingerprint(series: dict) -> dict:
    """A fingerprint recorded on this platform's standard library."""
    return {"template": "t.json", "rng_library": golden_capture.rng_library(), "run": {"series": series}}


def _series(units: str, column: str, values: list[float]) -> dict:
    return {"units": units, "columns": [column], "time_s": {"n": len(values)},
            "data": [{"first": values[0], "last": values[-1], "min": min(values), "max": max(values),
                      "mean": sum(values) / len(values), "samples": values, "non_finite": 0}]}


def _changed(golden: dict, name: str, values: list[float], library: str | None = None) -> list[str]:
    actual = copy.deepcopy(golden)
    actual["run"]["series"][name] = _series(golden["run"]["series"][name]["units"],
                                            golden["run"]["series"][name]["columns"][0], values)
    return golden_capture.compare(golden, actual)


def test_the_comparison_holds_each_number_to_its_own_scale():
    """A change of 1e-5 of a column's size is caught; 1e-8 is not (what two
    computers disagree on); text and counts must match exactly."""
    golden = _fingerprint({"sat.position_N": _series("m", "x", [-7.0e6, 1.0, 7.0e6])})
    assert _changed(golden, "sat.position_N", [-7.0e6, 1.0 + 7.0e6 * 1e-8, 7.0e6]) == []
    assert _changed(golden, "sat.position_N", [-7.0e6, 1.0 + 7.0e6 * 1e-5, 7.0e6])
    assert _changed(golden, "sat.position_N", [-7.0e6, 7.0e6])
    assert golden_capture.compare({"label": "a"}, {"label": "b"})


def test_an_ill_conditioned_angle_is_held_to_its_floor_and_compares_modulo_two_pi():
    """The angles of a circular orbit differ by 1.5e-8 rad between computers
    and a RAAN of 0 is one of 2*pi: both pass. A change of 1e-5 rad does
    not."""
    golden = _fingerprint({"sat.orbit_elements.raan": _series("rad", "raan", [0.0, 1.0e-8, 3.0])})
    assert _changed(golden, "sat.orbit_elements.raan", [2.0 * math.pi, 2.5e-8, 3.0]) == []
    assert _changed(golden, "sat.orbit_elements.raan", [0.0, 1.0e-5, 3.0])


def test_sensor_noise_compares_value_by_value_only_on_the_library_that_recorded_it():
    """A sensor's noise from another C++ standard library is another draw:
    only its count is compared there. On the recording library every value
    is. Holds on every platform: the fixture is recorded on this one."""
    golden = _fingerprint({"sat.sensor.imu-1.gyro": _series("rad/s", "x", [1.0e-5, -2.0e-5, 3.0e-5])})
    other = copy.deepcopy(golden)
    other["rng_library"] = "another library"
    noise = [-4.0e-5, 1.0e-5, 2.0e-5]  # [rad/s]
    assert _changed(golden, "sat.sensor.imu-1.gyro", noise)
    assert _changed(other, "sat.sensor.imu-1.gyro", noise) == []
    assert _changed(other, "sat.sensor.imu-1.gyro", noise[:2])


def test_on_another_library_numbers_are_held_to_one_percent():
    """Off the recording platform every number is held to 1 % of its scale
    (switching controllers turn last bits into shifted switches there): a
    0.1 % change passes, a 5 % one does not, and a count still must match."""
    golden = _fingerprint({"sat.rw_speeds": _series("rad/s", "wheel_0", [-2.0, 1.0, 2.0])})
    golden["rng_library"] = "another library"
    assert _changed(golden, "sat.rw_speeds", [-2.0, 1.002, 2.0]) == []
    assert _changed(golden, "sat.rw_speeds", [-2.0, 1.1, 2.0])
    assert _changed(golden, "sat.rw_speeds", [-2.0, 2.0])
