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
"""Plugins (transparency plan, Phase 6c: ``spacemissionstudio.plugins``):
the example of docs/user-manual/plugins.md, loaded through a stand-in
entry point, adds its parameters, rule and models; they are chosen, traced
and recorded like the built-in ones; a plugin that fails is left out and
taken back; the command line and the Assumptions page name them."""

import dataclasses
import math
import re
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from spacemissionstudio import cli, plugins
from spacemissionstudio.config import models, registry
from spacemissionstudio.config.registry import ConfigError, Configuration
from spacemissionstudio.engine import findings, link_budget
from spacemissionstudio.engine import solar_degradation as sd
from spacemissionstudio.engine.scenario_checks import scenario_warnings
from spacemissionstudio.schema.scenario import (GravityConfig, GroundStationConfig, OrbitIC, RFLinkConfig, Scenario,
                                                SimSettings, SpacecraftConfig)

_GUIDE = Path(__file__).resolve().parents[1] / "docs" / "user-manual" / "plugins.md"
_STATION = GroundStationConfig("kiruna", 67.86, 20.96, altitude_m=390.0, rx_antenna_gain_dbi=40.0,
                               system_noise_temp_k=200.0)  # [deg], [m], [dBi], [K]
_LINK = RFLinkConfig(tx_power_w=5.0, frequency_hz=8.2e9, data_rate_bps=1.0e6,  # [W], [Hz], [bit/s]
                     tx_antenna_gain_dbi=6.0, required_ebno_db=4.0)  # [dBi], [dB]


def _guide_register():
    """``register`` of the guide's example plugin, run as the guide shows it."""
    code = re.findall(r"```python\n(.*?)```", _GUIDE.read_text(encoding="utf-8"), re.S)
    assert len(code) == 1, "the guide has one example plugin"
    module = types.ModuleType("acme_rules")
    exec(compile(code[0], str(_GUIDE), "exec"), module.__dict__)  # noqa: S102 -- the guide's own code
    return module.register


@dataclasses.dataclass
class _EntryPoint:
    """What importlib.metadata's entry point gives the loader."""

    name: str
    register: object
    dist: object = dataclasses.field(default_factory=lambda: SimpleNamespace(name="acme-rules", version="1.0"))

    def load(self):
        return self.register


@pytest.fixture
def no_plugins():
    """Whatever a test loads is taken back after it."""
    plugins.unload()
    registry.parameters()
    yield
    plugins.unload()


@pytest.fixture
def acme(no_plugins):
    plugins.unload()
    loaded = plugins.load([_EntryPoint("acme", _guide_register())])
    assert [p.name for p in loaded] == ["acme"] and plugins.problems() == []
    return loaded[0]


def _scenario(overrides=None, stations=1):
    scenario = Scenario(name="plugins", epoch_utc="2030-01-01T00:00:00", ground_stations=[_STATION] * stations,
                        gravity=GravityConfig(central_body="earth"), sim_settings=SimSettings(duration_days=0.1),
                        spacecraft=[SpacecraftConfig(
                            name="sat", rf_link=_LINK,
                            orbit=OrbitIC(type="classical_elements", semi_major_axis_km=6928.0, eccentricity=0.0,
                                          inclination_deg=97.6, raan_deg=0.0, arg_periapsis_deg=0.0,
                                          true_anomaly_deg=0.0))])  # [km], [deg]
    scenario.configuration = Configuration(overrides=overrides) if overrides is not None else None
    return scenario


def test_the_guides_plugin_adds_its_parameters_rule_and_models(acme):
    """Each addition is the plugin's: its parameters in its own area, its
    rule under its name, its models among the choices', recorded with the
    plugin's name."""
    assert acme.parameters == ["acme.zenith_loss_db", "acme.lowest_elevation_deg", "acme.loss_per_year",
                               "acme.min_ground_stations"]
    assert [p.name for p in registry.parameters("acme")] == acme.parameters
    assert registry.parameter("acme.zenith_loss_db").unit == "[dB]" and registry.default("acme.loss_per_year") == 0.02
    assert acme.rules == ["acme.ground_stations"] and findings.RULES["acme.ground_stations"].parameter == (
        "acme.min_ground_stations")
    assert acme.models == [("link.atmospheric_loss", "acme_flat"), ("power.degradation", "acme_linear"),
                           ("propellant_budget.margin_policy", "acme_margins")]
    for choice, name in acme.models:
        assert name in registry.parameter(choice).choices and models.model(choice, name).plugin == "acme"
        assert models.record(models.model(choice, name))["plugin"] == "acme"
    assert "plugin" not in models.record(models.model("link.atmospheric_loss", "itu_r_p676"))
    assert plugins.records() == [{
        "name": "acme", "distribution": "acme-rules", "version": "1.0",
        "parameters": {"acme.zenith_loss_db": 0.4, "acme.lowest_elevation_deg": 5.0, "acme.loss_per_year": 0.02,
                       "acme.min_ground_stations": 2},
        "rules": ["acme.ground_stations"],
        "models": ["link.atmospheric_loss: acme_flat", "power.degradation: acme_linear",
                   "propellant_budget.margin_policy: acme_margins"]}]


def test_the_records_name_the_plugins_and_their_values(acme):
    """A record keeps each plugin parameter's value in effect; an analysis's
    record (the link budget's here) has the plugins, and none without."""
    from spacemissionstudio.engine import analysis_records

    scenario = _scenario({"link.atmospheric_loss": "acme_flat", "acme.zenith_loss_db": 0.6})
    assert plugins.records(scenario)[0]["parameters"]["acme.zenith_loss_db"] == 0.6
    traces = link_budget.link_budget_traces(1.5e6, _LINK, _STATION, 0.0, scenario, elevation_deg=30.0)
    record = analysis_records.link_budget_record(scenario, "sat", "kiruna", 1.5e6, "option", 0.0, traces, 30.0)
    assert record["provenance"]["plugins"] == plugins.records(scenario)
    assert record["model"]["models"]["link.atmospheric_loss"]["plugin"] == "acme"
    assert "itu_p676_part1" not in record["provenance"]["data_files"]
    plugins.unload()
    plugins.load([])
    plain = _scenario()
    traces = link_budget.link_budget_traces(1.5e6, _LINK, _STATION, 0.0, plain)
    assert "plugins" not in analysis_records.link_budget_record(plain, "sat", "kiruna", 1.5e6, "option", 0.0,
                                                                traces)["provenance"]


def test_unloading_takes_back_everything(acme):
    """What a plugin added goes with it: the registry, the rules and the
    choices are the built-in ones again."""
    plugins.unload()
    assert registry.parameters("acme") == [] and "acme.ground_stations" not in findings.RULES
    assert "acme_flat" not in registry.parameter("link.atmospheric_loss").choices
    assert "acme_flat" not in models.names("link.atmospheric_loss") and plugins.records() == []


def test_the_plugins_link_loss_is_in_the_margin_and_the_trace(acme):
    """acme_flat: A = A_zenith / sin(max(theta, theta_min)), the project's
    values in place of the defaults; the margin is the default's less A and
    the calculation names the model, its plugin and its reference."""
    scenario = _scenario({"link.atmospheric_loss": "acme_flat"})
    assert link_budget.atmospheric_loss_db(_LINK, 30.0, scenario) == pytest.approx(0.8, rel=1e-12)  # [dB]
    assert link_budget.atmospheric_loss_db(_LINK, 2.0, scenario) == pytest.approx(0.4 / math.sin(math.radians(5.0)))
    own = _scenario({"link.atmospheric_loss": "acme_flat", "acme.zenith_loss_db": 0.6})
    assert link_budget.atmospheric_loss_db(_LINK, 90.0, own) == pytest.approx(0.6)
    plain = link_budget.link_margin_db(1.5e6, _LINK, _STATION, 0.0, _scenario(), 30.0)  # [m], [deg]
    assert link_budget.link_margin_db(1.5e6, _LINK, _STATION, 0.0, scenario, 30.0) == pytest.approx(plain - 0.8)
    assert link_budget.atmospheric_zenith(_LINK, scenario) is None  # ITU-R P.676's terms: not that model
    traces = link_budget.link_budget_traces(1.5e6, _LINK, _STATION, 0.0, scenario, elevation_deg=30.0,
                                            elevation_source="option: here")
    trace = traces["atmospheric_loss"]
    assert trace.value == pytest.approx(0.8) and trace.input("theta") == 30.0
    assert trace.equation == "A_gas = acme_flat(f, theta)" and "plugin acme" in trace.reference
    assert "ACME-EXAMPLE-001" in trace.reference and trace.notes == (models.model(
        "link.atmospheric_loss", "acme_flat").method,)
    assert traces["received"].equation == "C = EIRP - FSPL - L_point - A_gas + G_rx"
    with pytest.raises(ValueError, match="acme_flat needs the station's elevation"):
        link_budget.link_margin_db(1.5e6, _LINK, _STATION, 0.0, scenario)


def test_the_plugins_degradation_is_the_arrays_factor(acme):
    """acme_linear: F(t) = max(0, 1 - k t), times F_UV and F_thermal as for
    the built-in models; the trace names the model and its plugin."""
    found = sd.from_scenario(_scenario({"power.degradation": "acme_linear", "acme.loss_per_year": 0.05}))
    assert found.model == "acme_linear"
    assert found.time_factor(3.0) == pytest.approx(0.85) and found.time_factor(30.0) == 0.0
    assert found.remaining(3.0) == pytest.approx(0.98 * 0.99 * 0.85)
    trace = sd.trace(found, 3.0, 0.30, "parameter: power.years_in_orbit_at_start", "scenario: power")
    assert trace.value == pytest.approx(0.30 * found.remaining(3.0))
    assert "acme_linear" in trace.equation and "plugin acme" in trace.reference


def test_the_plugins_margin_policy_sets_its_margins(acme):
    """acme_margins sets the two margins; a project's own value still wins."""
    scenario = _scenario({"propellant_budget.margin_policy": "acme_margins"})
    assert registry.value("propellant_budget.residual_fraction", scenario) == 0.03
    assert registry.value("propellant_budget.uncertainty_fraction", scenario) == 0.15
    assert registry.set_by("propellant_budget.residual_fraction", scenario).plugin == "acme"
    own = _scenario({"propellant_budget.margin_policy": "acme_margins", "propellant_budget.residual_fraction": 0.05})
    assert registry.value("propellant_budget.residual_fraction", own) == 0.05


def test_the_plugins_rule_is_a_pre_run_warning(acme):
    """One station where acme needs two: a warning under acme's rule, with
    the value found and the limit; none once the project accepts one."""
    found = [w for w in scenario_warnings(_scenario()) if w.rule_id == "acme.ground_stations"]
    assert len(found) == 1 and (found[0].actual, found[0].limit) == ("1", "2")
    assert str(found[0]) == "1 ground station(s): acme needs at least 2"
    assert not [w for w in scenario_warnings(_scenario(stations=2)) if w.rule_id.startswith("acme.")]
    assert not [w for w in scenario_warnings(_scenario({"acme.min_ground_stations": 1})) if w.rule_id.startswith("acme.")]


def test_a_check_that_fails_says_so(no_plugins):
    def register(api):
        api.add_rule("broken", "A rule.", "Why.", "Fix.", lambda scenario: 1 / 0)

    plugins.load([_EntryPoint("broken", register)])
    found = [w for w in scenario_warnings(_scenario()) if w.rule_id == "check.not_run"]
    assert [str(w) for w in found] == ["check not run: broken.broken (ZeroDivisionError: division by zero)"]


def test_a_plugin_that_fails_is_left_out_and_taken_back(no_plugins):
    """A failure in register, a name already taken, a model of a choice that
    takes none or without its implementation, a new choice: each plugin is
    left out, whatever it had added taken back, with the reason; the others
    still load."""
    def half_done(api):
        api.add_parameter("first", 1.0, "[-]", "A value.", "A source.")
        raise RuntimeError("the second one is missing")

    def gravity_model(api):
        api.add_model("dynamics.integrator", "own", "Own", "M.", (), (), (), (), ())

    def no_code(api):
        api.add_model("power.degradation", "own", "Own", "M.", (), (), (), (), ())

    def new_choice(api):
        api.add_parameter("own", "a", "[-]", "C.", "S.", kind="model", choices=("a",))

    points = [_EntryPoint("half", half_done), _EntryPoint("power", no_code), _EntryPoint("gravity", gravity_model),
              _EntryPoint("code", no_code), _EntryPoint("choice", new_choice), _EntryPoint("acme", _guide_register()),
              _EntryPoint("Bad-Name", no_code)]
    assert [p.name for p in plugins.load(points)] == ["acme"]
    assert registry.parameters("half") == [] and "own" not in registry.parameter("power.degradation").choices
    problems = plugins.problems()
    assert len(problems) == 6
    assert "'half' (acme-rules) was not loaded: RuntimeError: the second one is missing" in problems[0]
    assert "'power'" in problems[1] and "not a built-in area" in problems[1]
    assert "'dynamics.integrator' does not take a plugin's model" in problems[2]
    assert "model 'own' needs an implementation" in problems[3]
    assert "a plugin adds models to the existing choices" in problems[4]
    assert "'Bad-Name'" in problems[5]


def test_a_choice_of_a_plugin_not_installed_is_refused(no_plugins):
    """A colleague's configuration that chooses a model of a plugin this
    installation does not have is refused, naming the model."""
    with pytest.raises(ConfigError, match="acme_flat"):
        registry.checked_overrides({"link.atmospheric_loss": "acme_flat"}, "project.yaml")


def test_the_environment_can_turn_them_off(no_plugins, monkeypatch):
    """The installed ones load at the first use of the parameters, once;
    SPACEMISSIONSTUDIO_PLUGINS=0 loads none."""
    monkeypatch.setattr(plugins, "_entry_points", lambda: [_EntryPoint("acme", _guide_register())])
    plugins.unload()
    monkeypatch.setenv(plugins.ENVIRONMENT, "0")
    assert plugins.load() == [] and registry.parameters("acme") == []
    plugins.unload()
    monkeypatch.delenv(plugins.ENVIRONMENT)
    assert [p.name for p in registry.parameters("acme")][:1] == ["acme.zenith_loss_db"]
    assert plugins.load() == plugins.loaded() and len(plugins.loaded()) == 1


def test_the_command_line_lists_them(no_plugins, capsys):
    """``plugins``: none installed; the plugin and what it added; a plugin
    not loaded is an ERROR, exit status 5."""
    plugins.unload()
    plugins.load([])
    assert cli.main(["plugins"]) == 0
    assert "No plugins installed (entry-point group 'spacemissionstudio.models'" in capsys.readouterr().out
    plugins.unload()
    plugins.load([_EntryPoint("acme", _guide_register()),
                  _EntryPoint("half", lambda api: (_ for _ in ()).throw(RuntimeError("no")))])
    assert cli.main(["plugins"]) == cli.EXIT_CHECK_FAILED
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "acme  (acme-rules 1.0)",
        "  parameters: acme.zenith_loss_db, acme.lowest_elevation_deg, acme.loss_per_year, acme.min_ground_stations",
        "  rules: acme.ground_stations",
        "  models: link.atmospheric_loss: acme_flat, power.degradation: acme_linear, "
        "propellant_budget.margin_policy: acme_margins"]
    assert "ERROR: plugin 'half' (acme-rules) was not loaded: RuntimeError: no" in err.splitlines()
    guide = _GUIDE.read_text(encoding="utf-8")
    for line in out.splitlines():
        assert line in guide, "the guide shows what the command prints"


@pytest.mark.requires_basilisk
def test_a_run_records_the_plugins_and_their_model(acme):
    """The provenance lists the plugins loaded, and the model used with its
    plugin's name; no ITU-R P.676 data file is needed."""
    from spacemissionstudio.engine.service import SimulationService

    scenario = _scenario({"link.atmospheric_loss": "acme_flat"})
    scenario.simulation_mode = "orbit_only"
    scenario.sim_settings = SimSettings(duration_days=0.1, dynamics_task_rate_s=10.0, integrator="rkf45")  # [day], [s]
    scenario.validate()
    result = SimulationService(scenario).run()
    provenance = result.provenance.to_dict()
    assert provenance["plugins"] == plugins.records(scenario)
    assert provenance["models"]["link.atmospheric_loss"]["model"] == "acme_flat"
    assert provenance["models"]["link.atmospheric_loss"]["plugin"] == "acme"
    assert "itu_p676_part1" not in provenance.get("data_files", {})


@pytest.mark.requires_gui
def test_the_assumptions_page_names_them(qtbot, acme):
    """The plugins loaded under the file field, and those not loaded with
    the reason; nothing without plugins."""
    from spacemissionstudio.gui.assumptions_page import AssumptionsPage

    page = AssumptionsPage()
    qtbot.addWidget(page)
    assert page.plugins_label.text() == "Plugins: acme (acme-rules 1.0)."
    plugins.load([_EntryPoint("half", lambda api: (_ for _ in ()).throw(RuntimeError("no")))])
    page._show_plugins()
    assert "Not loaded: plugin 'half' (acme-rules) was not loaded: RuntimeError: no." in page.plugins_label.text()
    plugins.unload()
    plugins.load([])
    page._show_plugins()
    assert page.plugins_label.text() == "" and page.plugins_label.isHidden()
