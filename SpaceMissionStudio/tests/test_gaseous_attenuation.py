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
"""The gases' attenuation of the link (transparency plan, Phase 6b:
``link.atmospheric_loss``): ITU-R P.676-13 (engine.gaseous_attenuation),
checked against the ITU's own validation workbook for it, and its place
in the link budget, its traces, the run and the records.

The reference values are from the ITU-R Study Group 3 validation examples,
CG-3M3J-13-ValEx-Rev8.3.0.xlsx: sheet "P676-13 SpAtt" (Annex 1's specific
attenuation at 1013.25 hPa, 15 deg C, 7.5 g/m^3) and sheet
"P676-13 A_Gas A2_INST" (Annex 2's instantaneous slant path). Part 1 is
not part of this repository: the slant-path tests use the two rows of it
that sheet lists for its frequencies, 38.5 and 39.5 GHz."""

import urllib.request
import dataclasses
import hashlib
import json
import math

import numpy as np
import pytest

from spacemissionstudio import cli
from spacemissionstudio.config.registry import Configuration
from spacemissionstudio.engine import gaseous_attenuation as gases
from spacemissionstudio.engine import link_budget
from spacemissionstudio.engine.results import ResultSet, ResultsError, TimeSeries
from spacemissionstudio.schema.scenario import (GravityConfig, GroundStationConfig, OrbitIC, RFLinkConfig, Scenario,
                                                SimSettings, SpacecraftConfig)

# "P676-13 SpAtt": f [GHz], gamma_o [dB/km], gamma_w [dB/km]
_SPECIFIC = (
    (1, 0.00538865816790655, 5.09046173249644e-05),
    (10, 0.00822441670270988, 0.00597412524547672),
    (22, 0.0131302229653917, 0.17420703333692),
    (50, 0.277268638530969, 0.111158547270094),
    (60, 14.6234747964861, 0.154841840636247),
    (118, 1.13486620187051, 0.605921952594212),
    (183, 0.0127339088358709, 27.6650083141665),
    (300, 0.0257595762819792, 5.22132904110494),
    (350, 0.0368056270504571, 10.1226731395126),
)
_SPECIFIC_E_HPA = 9.97288878634056  # [hPa] the sheet's water-vapour pressure: 7.5 g/m^3 at 288.15 K

# "P676-13 A_Gas A2_INST": P_s [hPa], T_s [K], rho [g/m^3], f [GHz], elevation [deg], A_o, A_w, A_gas [dB]
_SLANT = (
    (1007.4, 295.15, 13.998103358274586, 38.5, 45.0, 0.29403602936797063, 0.37837010993289155, 0.6724061393008622),
    (1009.0, 300.85, 13.172371197621427, 38.5, 45.0, 0.2875359502854342, 0.32961688067901995, 0.6171528309644542),
    (1009.6, 301.35, 14.53449059438436, 38.5, 45.0, 0.2866106215316874, 0.3699983276884549, 0.6566089492201423),
    (1010.8, 297.65, 15.942511766465097, 39.5, 45.0, 0.3241994198357354, 0.4465714783880208, 0.7707708982237562),
)
# The rows of Part 1 the sheet lists: f [GHz], a_o [km], b_o [km/K], c_o [km/hPa], d_o [km m^3/g]
_PART1_ROWS = ((38.5, -2.540595, 0.02858191, -0.0006404764, -0.001265134),
               (39.5, -2.549964, 0.0286276, -0.0006430543, -0.001296508))


def _two_row_part1() -> gases.Part1:
    return gases.Part1(_PART1_ROWS, "the validation workbook's rows")


@pytest.fixture
def stand_in_part1(tmp_path, monkeypatch):
    """A Part 1 of the workbook's two rows, installed as the ITU's would be:
    its size and SHA-256 stand in for the ITU's file's."""
    text = "".join(f"{f:6.2f} {a: .6e} {b: .6e} {c: .6e} {d: .6e}\r\n" for f, a, b, c, d in _PART1_ROWS)
    source = tmp_path / "part1.txt"
    source.write_bytes(text.encode("ascii"))
    monkeypatch.setattr(gases, "PART1_SIZE_BYTES", len(text))
    monkeypatch.setattr(gases, "PART1_SHA256", hashlib.sha256(text.encode("ascii")).hexdigest())
    return gases.import_file(source)


_STATION = GroundStationConfig("kiruna", 67.86, 20.96, altitude_m=390.0, rx_antenna_gain_dbi=40.0,
                               system_noise_temp_k=200.0)  # [deg], [m], [dBi], [K]
_KA_LINK = RFLinkConfig(tx_power_w=5.0, frequency_hz=38.5e9, data_rate_bps=1.0e7,  # [W], [Hz], [bit/s]
                        tx_antenna_gain_dbi=20.0, required_ebno_db=4.0)  # [dBi], [dB]


def _scenario(configuration=None, rf_link=_KA_LINK):
    scenario = Scenario(name="gases", epoch_utc="2030-01-01T00:00:00", ground_stations=[_STATION],
                        gravity=GravityConfig(central_body="earth"), sim_settings=SimSettings(duration_days=0.1),
                        spacecraft=[SpacecraftConfig(
                            name="sat", rf_link=rf_link,
                            orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                                          inclination_deg=97.6, raan_deg=0.0, arg_periapsis_deg=0.0,
                                          true_anomaly_deg=0.0))])  # [km], [deg]
    scenario.configuration = configuration
    return scenario


def _configured(**overrides):
    return Configuration(overrides={"link.atmospheric_loss": "itu_r_p676", **overrides})


def _project_scenario(tmp_path):
    """A scenario file naming a project file that chooses itu_r_p676."""
    (tmp_path / "project.yaml").write_text("parameters:\n  link.atmospheric_loss: itu_r_p676\n", encoding="utf-8")
    scenario = _scenario()
    scenario.config_file = "project.yaml"
    path = tmp_path / "gases.json"
    scenario.save(path)
    return path


# -- the method -------------------------------------------------------------------------------

def test_the_specific_attenuation_matches_the_itu_validation_example():
    """Annex 1's line-by-line oxygen and water-vapour attenuation, the 44
    and 35 lines of its Tables 1 and 2, equals the ITU's own figures."""
    for f_ghz, gamma_o, gamma_w in _SPECIFIC:
        found = gases.specific_attenuation_db_km(f_ghz, 1013.25, _SPECIFIC_E_HPA, 288.15)  # [hPa], [K]
        assert found == pytest.approx((gamma_o, gamma_w), rel=1e-12), f_ghz
    assert len(gases.OXYGEN_LINES) == 44 and len(gases.WATER_VAPOUR_LINES) == 35


def test_the_slant_path_matches_the_itu_validation_example():
    """Annex 2's instantaneous slant path: oxygen, water vapour and their
    sum equal the ITU's own figures."""
    part1 = _two_row_part1()
    for pressure, temperature, density, f_ghz, elevation, a_o, a_w, a_gas in _SLANT:
        zenith = gases.zenith(f_ghz * 1e9, gases.Surface(pressure, temperature, density), part1)
        sine = math.sin(math.radians(elevation))
        assert zenith.oxygen_db / sine == pytest.approx(a_o, rel=1e-12)
        assert zenith.water_vapour_db / sine == pytest.approx(a_w, rel=1e-12)
        assert gases.slant_path_db(zenith, elevation) == pytest.approx(a_gas, rel=1e-12)


def test_part1_is_interpolated_linearly_and_its_range_is_kept():
    part1 = _two_row_part1()
    middle = tuple((a + b) / 2 for a, b in zip(_PART1_ROWS[0][1:], _PART1_ROWS[1][1:]))
    assert part1.coefficients(39.0) == pytest.approx(middle)
    with pytest.raises(gases.GaseousAttenuationError, match="outside Part 1"):
        part1.coefficients(40.0)
    assert gases.parse_part1("39.5 1 2 3 4\n38.5 5 6 7 8\n").rows[0][0] == 38.5  # sorted by frequency
    for bad in ("38.5 1 2 3\n39.5 1 2 3 4\n", "38.5 1 2 3 4\n38.5 1 2 3 4\n", "38.5 1 2 3 nan\n39 1 2 3 4\n"):
        with pytest.raises(gases.GaseousAttenuationError):
            gases.parse_part1(bad)


def test_the_method_is_used_within_its_range_only():
    """Below 5 deg the elevation used is 5 deg; below 1 GHz the frequency
    used is 1 GHz; above 350 GHz there is no method."""
    assert gases.method_elevation_deg(2.0) == 5.0 and gases.method_elevation_deg(30.0) == 30.0
    assert gases.method_frequency_ghz(4.0e8) == 1.0 and gases.method_frequency_ghz(8.2e9) == pytest.approx(8.2)
    with pytest.raises(gases.GaseousAttenuationError, match="1 to 350 GHz"):
        gases.method_frequency_ghz(4.0e11)


# -- Part 1, installed with the tool ---------------------------------------------------------------

def test_only_the_itus_part1_is_installed_and_read(tmp_path, stand_in_part1):
    """A file is installed only when it has the ITU's size and SHA-256; the
    run reads the installed one and never downloads."""
    found = gases.installed()
    assert found is not None and found.path == str(gases.DEFAULT_DIR / gases.PART1_NAME)
    assert gases.load_part1().rows == _PART1_ROWS
    other = tmp_path / "other.txt"
    other.write_text("38.5 1 2 3 4\n39.5 1 2 3 4\n", encoding="ascii")
    with pytest.raises(gases.GaseousAttenuationError, match="is not the ITU's"):
        gases.import_file(other, tmp_path / "elsewhere")
    assert gases.installed(tmp_path / "elsewhere") is None
    with pytest.raises(gases.GaseousAttenuationError, match="is not the ITU's"):
        gases.load_part1(other)


def test_the_install_folder_can_be_moved(tmp_path, stand_in_part1):
    """The manifest's path is where it was installed; the file is found
    beside the manifest (the .deb and the Windows setup move the folder)."""
    moved = tmp_path / "moved"
    gases.DEFAULT_DIR.rename(moved)
    assert gases.installed(moved).path == str(moved / gases.PART1_NAME)


def test_fetch_downloads_from_the_itu_and_checks_the_file(monkeypatch, stand_in_part1):
    """The only network access: the ITU's URL, checked before it is installed."""
    data = gases.DEFAULT_DIR.joinpath(gases.PART1_NAME).read_bytes()
    requested = []

    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self, _limit):
            return self.body

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda request, timeout: requested.append(request.full_url) or Response(data))
    assert gases.fetch().sha256 == gases.PART1_SHA256 and requested == [gases.PART1_URL]
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: Response(b"not it"))
    with pytest.raises(gases.GaseousAttenuationError, match="is not the ITU's"):
        gases.fetch()


def test_a_missing_part1_says_how_to_install_it():
    with pytest.raises(gases.GaseousAttenuationError, match="gaseous-attenuation --fetch"):
        gases.part1_path()


def test_the_command_line_reports_fetches_and_imports_part1(tmp_path, capsys, stand_in_part1):
    assert cli.main(["gaseous-attenuation"]) == 0
    assert gases.PART1_NAME in capsys.readouterr().out
    (gases.DEFAULT_DIR / gases.PART1_NAME).unlink()
    assert cli.main(["gaseous-attenuation"]) == 1
    assert "missing" in capsys.readouterr().out
    assert cli.main(["gaseous-attenuation", "--import", str(tmp_path / "part1.txt")]) == 0
    assert gases.installed() is not None
    capsys.readouterr()


def test_the_real_part1_is_the_itus_and_matches_the_workbook(real_itu_part1):
    """The file the installers fetch: 700 frequencies from 1 to 350 GHz,
    and at 38.5 and 39.5 GHz the coefficients the workbook lists."""
    part1 = gases.load_part1()
    assert len(part1.rows) == 700 and part1.rows[0][0] == 1.0 and part1.rows[-1][0] == 350.0
    for row in _PART1_ROWS:
        assert part1.coefficients(row[0]) == pytest.approx(row[1:], rel=1e-12)


# -- the link budget ---------------------------------------------------------------------------------

def test_no_atmospheric_loss_by_default():
    """The default, "none", is what the link budget did before the choice:
    no term, whatever the elevation, and no trace for it."""
    scenario = _scenario()
    assert link_budget.atmospheric_model(scenario) == "none"
    plain = link_budget.link_budget_breakdown(1.5e6, _KA_LINK, _STATION, 0.0, scenario)  # [m], [deg]
    assert link_budget.link_budget_breakdown(1.5e6, _KA_LINK, _STATION, 0.0, scenario, 12.0) == plain
    assert plain.atmospheric_loss_db == 0.0
    traces = link_budget.link_budget_traces(1.5e6, _KA_LINK, _STATION, 0.0, scenario, elevation_deg=12.0)
    assert "atmospheric_loss" not in traces and traces["received"].equation == "C = EIRP - FSPL - L_point + G_rx"


def test_the_loss_is_in_the_link_margin(stand_in_part1):
    """With itu_r_p676 the margin is the default's less A_gas at the
    elevation, the surface conditions are the project's, and the trace
    shows each term and where it came from."""
    plain = link_budget.link_margin_db(1.5e6, _KA_LINK, _STATION, 0.0, _scenario(), 20.0)
    for overrides in ({}, {"link.surface_water_vapour_density_g_m3": 15.0, "link.surface_temperature_k": 300.0}):
        scenario = _scenario(_configured(**overrides))
        surface = link_budget.surface(scenario)
        expected = gases.slant_path_db(gases.zenith(38.5e9, surface, _two_row_part1()), 20.0)
        breakdown = link_budget.link_budget_breakdown(1.5e6, _KA_LINK, _STATION, 0.0, scenario, 20.0)
        assert breakdown.atmospheric_loss_db == pytest.approx(expected, rel=1e-12) and expected > 0.5
        assert breakdown.margin_db == pytest.approx(plain - expected, abs=1e-9)
    assert surface == gases.Surface(1013.25, 300.0, 15.0)
    traces = link_budget.link_budget_traces(1.5e6, _KA_LINK, _STATION, 0.0, scenario, elevation_deg=20.0,
                                            elevation_source="option: here")
    trace = traces["atmospheric_loss"]
    assert trace.value == breakdown.atmospheric_loss_db and trace.input("theta") == 20.0
    assert trace.input("rho_ws") == 15.0 and trace.notes == ()
    assert traces["received"].equation == "C = EIRP - FSPL - L_point - A_gas + G_rx"
    low = link_budget.link_budget_traces(1.5e6, _KA_LINK, _STATION, 0.0, scenario, elevation_deg=2.0)
    assert low["atmospheric_loss"].value == pytest.approx(link_budget.atmospheric_loss_db(_KA_LINK, 5.0, scenario))
    assert "below 5 deg" in low["atmospheric_loss"].notes[0]
    with pytest.raises(ValueError, match="needs the station's elevation"):
        link_budget.link_margin_db(1.5e6, _KA_LINK, _STATION, 0.0, scenario)


def test_without_part1_the_chosen_model_is_refused(capsys, tmp_path):
    """The model needs Part 1: the budget says how to install it, and the
    command line stops (a missing component)."""
    with pytest.raises(gases.GaseousAttenuationError, match="not installed"):
        link_budget.link_margin_db(1.5e6, _KA_LINK, _STATION, 0.0, _scenario(_configured()), 20.0)
    assert cli.main(["link-budget", str(_project_scenario(tmp_path))]) == 2
    assert "gaseous-attenuation --fetch" in capsys.readouterr().err


def test_the_command_line_budget_takes_the_station_elevation(tmp_path, capsys, stand_in_part1):
    """At the minimum elevation by default; --elevation-deg with
    --range-km; the record carries the elevation, the model and the file."""
    path = _project_scenario(tmp_path)
    out = tmp_path / "budget.json"
    assert cli.main(["link-budget", str(path), "--out", str(out)]) == 0
    assert "Atmospheric gases" in capsys.readouterr().out
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["inputs"]["elevation_deg"] == _STATION.min_elevation_deg
    assert record["model"]["models"]["link.atmospheric_loss"]["model"] == "itu_r_p676"
    assert record["provenance"]["data_files"]["itu_p676_part1"]["matches_install"] is True
    assert record["results"]["atmospheric_loss"] == pytest.approx(
        link_budget.atmospheric_loss_db(_KA_LINK, _STATION.min_elevation_deg, _scenario(_configured())))
    assert cli.main(["link-budget", str(path), "--range-km", "1500"]) == 2
    assert "--elevation-deg" in capsys.readouterr().err
    assert cli.main(["link-budget", str(path), "--range-km", "1500", "--elevation-deg", "30"]) == 0
    capsys.readouterr()


def test_the_margin_series_takes_each_samples_elevation(stand_in_part1):
    """The post-run margin of a link without a live gate: each sample less
    the gases' attenuation at its own elevation; without the elevation
    series the chosen model cannot be applied."""
    times = np.array([0.0, 10.0, 20.0, 30.0])  # [s]
    series = {"slant_range": [2.0e6, 1.4e6, 1.0e6, 1.6e6], "has_access": [0.0, 1.0, 1.0, 1.0],
              "elevation": np.radians([1.0, 4.0, 30.0, 12.0])}
    result = ResultSet("gases")
    for name, values in series.items():
        result.add(TimeSeries(f"kiruna.access_to_sat.{name}", times, (name,),
                              np.asarray(values, float).reshape(-1, 1)))
    plain = link_budget.link_margin_series(result, "kiruna", "sat", _KA_LINK, _STATION, scenario=_scenario())
    scenario = _scenario(_configured())
    margin = link_budget.link_margin_series(result, "kiruna", "sat", _KA_LINK, _STATION, scenario=scenario)
    assert np.isnan(margin.data[0, 0])
    for i, elevation in ((1, 4.0), (2, 30.0), (3, 12.0)):
        loss = link_budget.atmospheric_loss_db(_KA_LINK, elevation, scenario)
        assert margin.data[i, 0] == pytest.approx(plain.data[i, 0] - loss, abs=1e-9)
    del result.series["kiruna.access_to_sat.elevation"]
    with pytest.raises(ResultsError, match="needs the elevation series"):
        link_budget.link_margin_series(result, "kiruna", "sat", _KA_LINK, _STATION, scenario=scenario)


# -- a run --------------------------------------------------------------------------------------------

def _run(configuration, data_handling: bool):
    """A quarter-day orbit-only run over Kiruna at 38.5 GHz: with
    ``data_handling`` a live link gate, without it the post-run margin."""
    from spacemissionstudio.engine.service import SimulationService
    from spacemissionstudio.schema.scenario import DataHandlingConfig, InstrumentConfig

    scenario = _scenario(configuration)
    scenario.simulation_mode = "orbit_only"
    scenario.sim_settings = SimSettings(duration_days=0.25, dynamics_task_rate_s=10.0, integrator="rkf45")
    scenario.ground_stations = [dataclasses.replace(_STATION, min_elevation_deg=3.0)]  # [deg]
    if data_handling:
        scenario.spacecraft[0].data_handling = DataHandlingConfig(4.0, [InstrumentConfig("camera", 2.0e5)])
    scenario.validate()
    return SimulationService(scenario).run()


@pytest.mark.requires_basilisk
@pytest.mark.parametrize("data_handling", [False, True], ids=["post-run margin", "live link gate"])
def test_a_run_takes_the_loss_at_each_steps_elevation(stand_in_part1, data_handling):
    """The run's margin, from the live gate or after the run, is the
    default's less the gases' attenuation at each sample's recorded
    elevation; the run records the model and Part 1, and warns that the
    station's 3 deg minimum is below the method's 5 deg."""
    plain = _run(None, data_handling)
    chosen = _run(_configured(), data_handling)
    name = "kiruna.access_to_sat"
    margin, before = (r.series[f"{name}.link_margin_db"].data[:, 0] for r in (chosen, plain))
    elevation_deg = np.degrees(chosen.series[f"{name}.elevation"].data[:, 0])
    inside = np.isfinite(margin)
    assert inside.sum() > 10 and np.array_equal(inside, np.isfinite(before))
    scenario = _scenario(_configured())
    loss = np.array([link_budget.atmospheric_loss_db(_KA_LINK, e, scenario) for e in elevation_deg[inside]])
    assert margin[inside] == pytest.approx(before[inside] - loss, abs=1e-6)
    provenance = chosen.provenance.to_dict()
    assert provenance["models"]["link.atmospheric_loss"]["model"] == "itu_r_p676"
    assert provenance["data_files"]["itu_p676_part1"]["matches_install"] is True
    assert any(getattr(w, "rule_id", None) == "link.atmospheric_low_elevation" for w in chosen.warnings)
    assert "models" not in plain.provenance.to_dict()


@pytest.mark.requires_basilisk
def test_a_run_without_part1_is_refused_before_it_starts():
    from spacemissionstudio.engine.service import SimulationService, SimulationServiceError

    scenario = _scenario(_configured())
    scenario.simulation_mode = "orbit_only"
    with pytest.raises(SimulationServiceError, match="gaseous-attenuation --fetch"):
        SimulationService(scenario).build()


@pytest.mark.requires_gui
def test_the_dashboard_shows_the_gases_row_with_the_model_only(qtbot, stand_in_part1):
    """The Dashboard's link budget has an Atmospheric gases row only when
    the model is chosen; its value is A_gas at the run's elevation, the
    margin the default's less it, and Show calculation names the elevation's
    series."""
    from spacemissionstudio.gui.mission_dashboard_widget import MissionDashboardWidget
    from spacemissionstudio.schema.scenario import CommsPointingConfig

    result = ResultSet("gases")
    for name, column, value in (("sat.comms_pointing.active_mode", "active_mode", 1.0),
                                ("sat.comms_pointing.pointing_error_deg", "pointing_error_deg", 0.0),
                                ("kiruna.access_to_sat.has_access", "has_access", 1.0),
                                ("kiruna.access_to_sat.slant_range", "slant_range", 1.5e6),
                                ("kiruna.access_to_sat.elevation", "elevation", math.radians(20.0))):
        result.add(TimeSeries(name, np.array([0.0]), (column,), np.array([[value]])))
    widget = MissionDashboardWidget()
    qtbot.addWidget(widget)
    margins = {}
    for configuration in (None, _configured()):
        scenario = _scenario(configuration)
        scenario.spacecraft[0].comms_pointing = CommsPointingConfig(target_ground_station="kiruna")
        widget.set_result(result, scenario)
        shown = widget._rf_form.isRowVisible(widget.atmospheric_loss_label)
        margins[shown] = float(widget.margin_label.text().split()[0])  # [dB]
    loss = link_budget.atmospheric_loss_db(_KA_LINK, 20.0, scenario)
    assert set(margins) == {False, True}
    assert widget.atmospheric_loss_label.text() == f"{loss:.2f} dB"
    assert margins[True] == pytest.approx(margins[False] - loss, abs=0.011)
    trace = next(t for t in widget.explanation().traces if t.symbol == "A_gas")
    assert "kiruna.access_to_sat.elevation" in next(q.source for q in trace.inputs if q.symbol == "theta")
