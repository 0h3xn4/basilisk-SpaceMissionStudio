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
"""The registry of selectable models (transparency plan, Phase 6a).

Where an analysis can be done more than one way, each way is a
:class:`Model`, declared here once with its name, what it computes and
how, its inputs and outputs, its assumptions, its references and the
tests that check it. A *choice* is the parameter that selects one
(:mod:`.registry`, ``kind="model"``): a project configuration file sets
it as it sets any other parameter, and the default is the model the tool
used before the choice existed, so no result changes until a project
chooses another. The model in effect is recorded with the results it
gives (:func:`records`).

A model may also set other parameters (``sets``): a margin policy is the
set of margins it gives. A value the project file sets itself replaces
the model's (:func:`.registry.effective`).

Without Basilisk, and without the GUI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    """One way of computing something. ``choice`` is the parameter that
    selects it (``<area>.<name>``), ``name`` the value that parameter
    takes for it."""

    choice: str
    name: str
    title: str  # e.g. "Population standard deviation"
    method: str  # what it computes and how, with the formula
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    assumptions: tuple[str, ...]
    references: tuple[str, ...]
    evidence: tuple[str, ...]  # the tests that check it, "tests/<file>.py::<test>"
    applies_to: str  # the records it is written into: "monte_carlo" (a batch's provenance)
    sets: tuple[tuple[str, object], ...] = ()  # (parameter, value): the values it gives other parameters
    plugin: str = ""  # the plugin that added it (spacemissionstudio.plugins); "" for a built-in one


_MODELS: dict[str, dict[str, Model]] = {}


def register(*models: Model) -> None:
    for model in models:
        declared = _MODELS.setdefault(model.choice, {})
        if model.name in declared:
            raise ValueError(f"model {model.name!r} of {model.choice!r} is declared twice")
        if not (model.title and model.method and model.inputs and model.outputs and model.assumptions
                and model.references and model.evidence):
            raise ValueError(f"model {model.name!r} of {model.choice!r}: every part of its declaration is needed")
        declared[model.name] = model


def unregister(choice: str, name: str) -> None:
    """Take back a plugin's model (``spacemissionstudio.plugins``)."""
    if _MODELS.get(choice, {}).get(name) is not None and _MODELS[choice][name].plugin:
        del _MODELS[choice][name]


def choices() -> list[str]:
    """The parameters that select a model, in declaration order."""
    return list(_MODELS)


def names(choice: str) -> tuple[str, ...]:
    """The models ``choice`` may select, in declaration order: the values
    its parameter may take."""
    return tuple(_MODELS[choice])


def models(choice: str) -> list[Model]:
    return list(_MODELS[choice].values())


def model(choice: str, name: str) -> Model:
    return _MODELS[choice][name]


def active(choice: str, scenario=None) -> Model:
    """The model in effect for ``scenario``: the one its configuration
    selects, else the default."""
    from . import registry

    return model(choice, registry.value(choice, scenario))


def set_by(name: str, chosen: dict) -> Model | None:
    """The model in effect that sets parameter ``name``, given the values
    ``chosen`` ({parameter: value}, a configuration's overrides; a choice
    not in it has its default); None when none does."""
    from . import registry

    for choice in choices():
        found = model(choice, chosen.get(choice, registry.default(choice)))
        if name in dict(found.sets):
            return found
    return None


def record(found: Model) -> dict:
    """``found`` as a provenance record keeps it."""
    out = {"model": found.name, "title": found.title, "method": found.method, "references": list(found.references)}
    if found.plugin:
        out["plugin"] = found.plugin
    if found.sets:
        out["sets"] = {name: list(value) if isinstance(value, tuple) else value for name, value in found.sets}
    return out


def records(scenario, applies_to: str) -> dict:
    """``{choice: record}`` of every model in effect for ``scenario`` that is
    written into ``applies_to``'s records."""
    return {choice: record(active(choice, scenario)) for choice in choices()
            if models(choice)[0].applies_to == applies_to}


# -- Monte Carlo statistics (engine.monte_carlo_results) ---------------------------------------

_SPREAD = "monte_carlo.spread_statistic"
_SPREAD_INPUTS = ("Each successful run's radial, along-track and cross-track offset from the batch's mean [m], "
                  "at each sample", "N, the number of runs that succeeded [-]")
_SPREAD_OUTPUTS = ("<spacecraft>.monte_carlo.spread [m], the series", "the Monte Carlo page's spread tiles",
                   "the command line's \"1-sigma at the end\" line")

register(
    Model(_SPREAD, "population", "Population standard deviation",
          "The square root of the mean squared offset: sqrt(sum((x_k - mean)^2) / N) over the N runs "
          "(numpy.std with ddof=0).",
          _SPREAD_INPUTS, _SPREAD_OUTPUTS,
          ("The runs are all that is described: the spread is that of these N runs, not an estimate of the "
           "distribution they were drawn from.",
           "One run gives a spread of 0."),
          ("NumPy reference, numpy.std: the ddof argument (ddof=0, the default, divides by N).",),
          ("tests/test_monte_carlo_results.py::test_result_set_has_per_run_series_and_the_spread",
           "tests/test_monte_carlo_results.py::test_run_table_lists_drawn_values_and_where_each_run_ended",
           "tests/test_model_registry.py::test_each_spread_statistic_is_the_one_it_declares"),
          "monte_carlo"),
    Model(_SPREAD, "sample", "Sample standard deviation",
          "The square root of the sum of squared offsets over N - 1: sqrt(sum((x_k - mean)^2) / (N - 1)) over "
          "the N runs (numpy.std with ddof=1, Bessel's correction). It is sqrt(N / (N - 1)) times the "
          "population standard deviation: 1.22 times for 3 runs, 1.005 times for 100.",
          _SPREAD_INPUTS, _SPREAD_OUTPUTS,
          ("The runs are a random sample of the distribution the dispersions describe; dividing by N - 1 makes "
           "the variance an unbiased estimate of that distribution's (the standard deviation itself is still "
           "slightly low for few runs).",
           "One run gives a spread of 0, as for the population standard deviation: N - 1 would be 0."),
          ("NumPy reference, numpy.std: the ddof argument (ddof=1 divides by N - 1).",),
          ("tests/test_model_registry.py::test_each_spread_statistic_is_the_one_it_declares",
           "tests/test_monte_carlo.py::test_a_batch_uses_and_records_the_statistic_its_configuration_chooses"),
          "monte_carlo"),
)

# -- Propellant budget margin policies (engine.propellant_budget) ------------------------------

_MARGINS = "propellant_budget.margin_policy"
_AD10 = ("ESA, Guidelines for the computation of the Delta-V and Propellant Mass budgets, EOP-FM/2024-07-177, "
         "issue 3.0 (AD10): Secs. 5.6, 5.8 and 6.4, and its summary table.")
_MARGIN_INPUTS = ("The margin parameters propellant_budget.residual_fraction and .uncertainty_fraction [-]",
                  "The tank's load, its capacity or the iteration's total [kg]")
_MARGIN_OUTPUTS = ("The budget's Residual and Loading uncertainty rows [kg], and so its propellant total",
                   "The budget's note on the residual and uncertainty")

register(
    Model(_MARGINS, "ad10_equations", "AD10's equations",
          "The margins as AD10's equations give them, the parameters' defaults: the residual 1 % and the loading "
          "and gauging uncertainty 2 % of the tank's load (Secs. 5.8, 6.4), and the other margins as declared "
          "(collision avoidances x4, attitude propellant x2, a controlled re-entry's last burn +15 %, Sec. 5.6).",
          _MARGIN_INPUTS, _MARGIN_OUTPUTS,
          ("AD10's equations are the authority where its summary table prints other values.",),
          (_AD10,),
          ("tests/test_propellant_budget.py::test_the_budget_applies_ad10s_margins_and_converges",
           "tests/test_model_registry.py::test_a_margin_policy_sets_its_margins_and_a_projects_own_value_wins"),
          "propellant_budget"),
    Model(_MARGINS, "ad10_summary_table", "AD10's summary table",
          "As AD10's equations, but the residual and the loading uncertainty AD10's summary table prints: 10 % "
          "and 20 % of the tank's load. These two are the only differences between the table and the equations "
          "recorded here.",
          _MARGIN_INPUTS, _MARGIN_OUTPUTS,
          ("The table's 10 % and 20 % are taken as fractions of the tank's load, as the equations' 1 % and 2 % "
           "are; the table's own basis is not recorded here.",
           "The other margins are the equations'.",),
          (_AD10,),
          ("tests/test_model_registry.py::test_a_margin_policy_sets_its_margins_and_a_projects_own_value_wins",
           "tests/test_model_registry.py::test_the_summary_tables_budget_says_so_and_records_it"),
          "propellant_budget",
          sets=(("propellant_budget.residual_fraction", 0.10), ("propellant_budget.uncertainty_fraction", 0.20))),
)

# -- Shadowing bodies (engine.shadows) ----------------------------------------------------------

_SHADOWS = "dynamics.shadowing_bodies"
_SHADOW_INPUTS = ("The Sun's and every tracked body's position (SPICE) [m]", "Each spacecraft's position [m]",
                  "Each body's equatorial radius, as Basilisk's eclipse knows it by name [m]")
_SHADOW_OUTPUTS = ("<spacecraft>.eclipse.illumination_factor [-], and so the eclipse events",
                   "The sunlight the solar panels, solar radiation pressure, the sun and thermal sensors and the "
                   "eclipse-gated thrusters see")
_ECLIPSE_REF = ("Basilisk's eclipse module (src/simulation/environment/eclipse): a conical umbra and penumbra "
                "of a spherical body, the Sun's disk overlap for partial shadow.")

register(
    Model(_SHADOWS, "central_body", "The central body",
          "The central body's shadow only, by one Basilisk eclipse module (in a heliocentric run, every tracked "
          "body but the Sun in that one module, which takes the shadow of the body nearest the spacecraft).",
          _SHADOW_INPUTS, _SHADOW_OUTPUTS,
          ("No other body shadows a spacecraft orbiting the central body: no lunar eclipse of an Earth orbiter.",
           "The bodies are spheres of their equatorial radius."),
          (_ECLIPSE_REF,),
          ("tests/test_shadows.py::test_only_the_central_body_shadows_by_default",),
          "run"),
    Model(_SHADOWS, "tracked_bodies", "Every tracked body",
          "The central body's module as before, and one more Basilisk eclipse module for each other tracked "
          "body but the Sun, each with that one body (one module with several takes only the nearest one's "
          "shadow). A spacecraft's sunlight is the product of the fractions each body leaves.",
          _SHADOW_INPUTS, _SHADOW_OUTPUTS,
          ("Two bodies shading the Sun at once are combined as independent: the product of their fractions. "
           "Exact whenever no more than one body shades.",
           "The bodies are spheres of their equatorial radius; a tracked body whose radius Basilisk's eclipse "
           "does not know by name (a small body other than the central one) cannot shadow, and the run warns.",
           "Each extra body adds one Basilisk module and one Python module per spacecraft: a slower run."),
          (_ECLIPSE_REF,),
          ("tests/test_shadows.py::test_the_moon_shadows_a_spacecraft_behind_it_with_tracked_bodies",
           "tests/test_shadows.py::test_the_occulters_of_each_model"),
          "run"),
)

# -- Atmospheric loss on the link (engine.link_budget, engine.gaseous_attenuation) ---------------

_ATMOSPHERIC_LOSS = "link.atmospheric_loss"
_LINK_INPUTS = ("The slant range [m] and the station's elevation [deg] at each sample of an access",
                "The link's frequency [Hz]")
_LINK_OUTPUTS = ("<station>.access_to_<spacecraft>.link_margin_db [dB], and so the live link gate's downlink",
                 "The link budget's traces (Calculation panel, spacemissionstudio link-budget)")

register(
    Model(_ATMOSPHERIC_LOSS, "none", "None",
          "No atmospheric term: C = EIRP - FSPL - L_point + G_rx.",
          _LINK_INPUTS, _LINK_OUTPUTS,
          ("The atmosphere takes nothing from the signal. A project's allowance for it, if any, is in the "
           "transmitter's implementation_loss_db.",),
          ("SpaceMissionStudio's link equation (docs/models/link-data-and-power.md)",),
          ("tests/test_gaseous_attenuation.py::test_no_atmospheric_loss_by_default",),
          "run"),
    Model(_ATMOSPHERIC_LOSS, "itu_r_p676", "ITU-R P.676-13, gaseous attenuation",
          "The oxygen and water-vapour attenuation of the slant path, by ITU-R P.676-13 Annex 2's instantaneous "
          "methods (Sec. 1.1, Sec. 2.1): A = (gamma_o h_o + gamma_w h_w) / sin(elevation), gamma from Annex 1's "
          "line-by-line sum, h_o from the Recommendation's data file Part 1, h_w from Annex 2 eq. (37); "
          "C = EIRP - FSPL - L_point - A + G_rx.",
          _LINK_INPUTS + ("The station's surface pressure [hPa], temperature [K] and water-vapour density [g/m^3] "
                          "(link.surface_*)", "ITU-R P.676-13 Part 1, installed with the tool"),
          _LINK_OUTPUTS,
          ("The same surface conditions at every station and every time: no weather, no season.",
           "Gases only: no rain, cloud, fog or scintillation (ITU-R P.618, P.840).",
           "The elevation is the geometric one, not the apparent one refraction gives (Annex 2 asks for the "
           "apparent one; they differ by less than 0.2 deg above 5 deg).",
           "Below 5 deg elevation, the method's lowest, the loss is the one at 5 deg: less than the real one.",
           "Below 1 GHz, the method's lowest, the loss is the one at 1 GHz: more than the real one. Above "
           "350 GHz there is no method and the run is refused."),
          ("Recommendation ITU-R P.676-13 (08/2022), Attenuation by atmospheric gases and related effects, "
           "Annex 1 and Annex 2, and its data file Part 1",),
          ("tests/test_gaseous_attenuation.py::test_the_specific_attenuation_matches_the_itu_validation_example",
           "tests/test_gaseous_attenuation.py::test_the_slant_path_matches_the_itu_validation_example",
           "tests/test_gaseous_attenuation.py::test_the_loss_is_in_the_link_margin"),
          "run"),
)

# -- Solar-array degradation (engine.solar_degradation) ---------------------------------------------

_DEGRADATION = "power.degradation"
_DEGRADATION_INPUTS = ("Each solar panel's beginning-of-life efficiency (power.panel_efficiency) [-]",
                       "The years in orbit: power.years_in_orbit_at_start plus the time flown [year]")
_DEGRADATION_OUTPUTS = ("Each solar panel's power, and so the battery's charge and net power",
                        "<spacecraft>.power.degradation_factor [-], the series (with a model chosen)")
_FACTORS = ("Ultraviolet darkening 0.98 and thermal cycling 0.99 (power.uv_darkening_factor, "
            "power.thermal_cycling_factor): the Solar Maximum Mission array's factors, whose FEP cover adhesive "
            "had no ultraviolet filter. They apply from the start of the run.")
_SOLAR_MAX = "T. Miller, Solar Maximum: Solar Array Degradation, NASA TM-86194 (1985), p. 11 (the one-off factors)"

register(
    Model(_DEGRADATION, "none", "None",
          "No degradation: each panel keeps its beginning-of-life efficiency.",
          _DEGRADATION_INPUTS, _DEGRADATION_OUTPUTS,
          ("Beginning of life equals end of life: no radiation, ultraviolet or thermal-cycling loss.",),
          ("SpaceMissionStudio's power model (docs/models/link-data-and-power.md)",),
          ("tests/test_solar_degradation.py::test_no_degradation_by_default",),
          "run"),
    Model(_DEGRADATION, "yearly_rate", "A yearly rate",
          "eta = eta_BOL F_UV F_thermal (1 - D)^t: a constant fraction D of the output lost each year "
          "(power.degradation_per_year).",
          _DEGRADATION_INPUTS + ("D, the yearly loss [-]",), _DEGRADATION_OUTPUTS,
          ("The same fraction is lost every year, whatever the orbit's radiation: D is the project's estimate "
           "for its cells and orbit. The default, 2.7 %/yr, is NASA's expectation for the ISS's silicon arrays "
           "in low Earth orbit; flight data range from 0.2 %/yr (the ISS arrays' current) to 4.5 %/yr (GaAs at 1100 km).",
           _FACTORS),
          ("T. W. Kerslake, E. D. Gustafson, On-Orbit Performance Degradation of the International Space Station "
           "P6 Photovoltaic Arrays, NASA/TM-2003-212513 (2003), p. 2 (the expected 2.7 %/yr)", _SOLAR_MAX),
          ("tests/test_solar_degradation.py::test_each_model_is_the_equation_it_declares",
           "tests/test_solar_degradation.py::test_a_run_degrades_the_panels_by_the_model"),
          "run"),
    Model(_DEGRADATION, "radiation_dose", "Displacement damage dose (triple-junction cells)",
          "eta = eta_BOL F_UV F_thermal (1 - C log10(1 + D_d t / D_x)): NRL and NASA's displacement-damage-dose "
          "fit, D_d the orbit's yearly displacement damage dose (power.displacement_damage_dose_per_year_mev_g).",
          _DEGRADATION_INPUTS + ("D_d, the yearly proton-equivalent displacement damage dose [MeV/g], from SPENVIS "
                                 "for the orbit and the cells' cover glass", "C [-] and D_x [MeV/g], the fit"),
          _DEGRADATION_OUTPUTS,
          ("C = 0.199 and D_x = 1.2e9 MeV/g are the fit to Emcore ATJ and Spectrolab triple-junction cells' "
           "ground data; other cells have their own.",
           "The dose accumulates at a constant yearly rate (no solar cycle, no change of orbit).",
           "The logarithm is base 10: the paper does not say so, but with the natural logarithm its fits would "
           "fall below 0.5 at 1e10 MeV/g, off the figures it is drawn on.",
           "SpaceMissionStudio has no radiation-belt model: the dose is the project's, and the run is refused "
           "without it.", _FACTORS),
          ("R. Walters, G. P. Summers, J. H. Warner, S. Messenger, J. R. Lorentzen, T. Morton et al., SPENVIS "
           "Implementation of End-of-Life Solar Cell Calculations Using the Displacement Damage Dose "
           "Methodology, NASA/CP-2007-214494 (2007), pp. 25-30, eq. 2 and Figures 7 and 8", _SOLAR_MAX),
          ("tests/test_solar_degradation.py::test_each_model_is_the_equation_it_declares",
           "tests/test_solar_degradation.py::test_the_dose_fit_is_the_papers_equation_in_base_10",
           "tests/test_solar_degradation.py::test_a_run_degrades_the_panels_by_the_model"),
          "run"),
)
