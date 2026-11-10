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
"""Solar-array degradation (transparency plan, Phase 6b:
``power.degradation``, the models in ``config.models``): the fraction of
its beginning-of-life efficiency a solar panel keeps after ``t`` years in
orbit.

    efficiency(t) = efficiency_BOL * F_UV * F_thermal * F(t)

* ``none`` (the default): F = 1 and no one-off factor; the efficiency is
  the scenario's, constant, as before the choice existed.
* ``yearly_rate``: F(t) = (1 - D)^t, D the yearly loss
  (``power.degradation_per_year``). The default, 2.7 %/yr, is NASA's
  expected maximum-power degradation of the ISS P6 silicon arrays in low
  Earth orbit (Kerslake and Gustafson, NASA/TM-2003-212513, 2003, p. 2).
* ``radiation_dose``: F(t) = 1 - C log10(1 + D_d t / D_x), the
  displacement-damage-dose fit of NRL and NASA (Walters et al.,
  NASA/CP-2007-214494, pp. 25-30, eq. 2), D_d the yearly
  proton-equivalent displacement damage dose [MeV/g] for the orbit and
  the cell's shielding, as SPENVIS gives it; C = 0.199 and
  D_x = 1.2e9 MeV/g are that paper's fit for Emcore ATJ and Spectrolab
  triple-junction cells (its Figures 7 and 8).

F_UV = 0.98 (ultraviolet darkening of the cover adhesive) and
F_thermal = 0.99 (thermal cycling of the interconnects) are the factors
of the Solar Maximum Mission array's prediction (T. Miller, NASA
TM-86194, 1985, p. 11), applied with either model.

``t`` is ``power.years_in_orbit_at_start`` plus the time flown since.

:func:`from_scenario` and the arithmetic are Basilisk-free;
:class:`PanelDegradation` is a Basilisk module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

CHOICE = "power.degradation"
YEAR_S = 365.25 * 86400.0  # [s] a Julian year


class DegradationError(Exception):
    """A degradation model chosen without what it needs."""


@dataclass(frozen=True)
class Degradation:
    """The degradation in effect: the model and its parameters' values."""

    model: str  # "yearly_rate", "radiation_dose" or a plugin's (spacemissionstudio.plugins)
    per_year: float  # [-] D, yearly_rate
    dose_per_year_mev_g: float  # [MeV/g] D_d, radiation_dose
    dose_fit_c: float  # [-] C
    dose_fit_dx_mev_g: float  # [MeV/g] D_x
    uv_factor: float  # [-] F_UV
    thermal_factor: float  # [-] F_thermal
    years_at_start: float  # [year] in orbit when the run starts
    plugin_factor: object = None  # a plugin model's F(years) [-]; None for the built-in models

    def time_factor(self, years: float) -> float:
        """[-] F(t), the model's own part, at ``years`` in orbit."""
        years = max(0.0, years)
        if self.plugin_factor is not None:
            return float(self.plugin_factor(years))
        if self.model == "yearly_rate":
            return (1.0 - self.per_year) ** years
        dose = self.dose_per_year_mev_g * years  # [MeV/g]
        return max(0.0, 1.0 - self.dose_fit_c * math.log10(1.0 + dose / self.dose_fit_dx_mev_g))

    def remaining(self, years: float) -> float:
        """[-] The fraction of the beginning-of-life efficiency kept at
        ``years`` in orbit: F_UV F_thermal F(t)."""
        return self.uv_factor * self.thermal_factor * self.time_factor(years)

    def years_at(self, elapsed_s: float) -> float:
        """[year] In orbit after ``elapsed_s`` of the run (and of the
        segments flown before it)."""
        return self.years_at_start + elapsed_s / YEAR_S


def from_scenario(scenario) -> Degradation | None:
    """The degradation ``scenario``'s configuration chooses; None with
    ``none``. Raises DegradationError for ``radiation_dose`` without a dose."""
    from ..config import models, registry

    model = models.active(CHOICE, scenario).name
    if model == "none":
        return None

    def value(name):
        return registry.value(f"power.{name}", scenario)

    found = Degradation(model, value("degradation_per_year"), value("displacement_damage_dose_per_year_mev_g"),
                        value("dose_fit_c"), value("dose_fit_dx_mev_g"), value("uv_darkening_factor"),
                        value("thermal_cycling_factor"), value("years_in_orbit_at_start"),
                        _plugin_factor(model, scenario))
    if model == "radiation_dose" and found.dose_per_year_mev_g <= 0.0:
        raise DegradationError(
            "power.degradation: radiation_dose needs the orbit's yearly displacement damage dose "
            "(power.displacement_damage_dose_per_year_mev_g, in MeV/g, proton-equivalent, as SPENVIS gives it "
            "for the orbit and the cells' cover glass); it is 0")
    return found


def _plugin_factor(model: str, scenario):
    """A plugin model's F(years) for ``scenario``; None for a built-in one."""
    if model in ("yearly_rate", "radiation_dose"):
        return None
    from .. import plugins

    implementation = plugins.implementation(CHOICE, model)
    return lambda years: implementation(years, scenario)


def trace(found: Degradation, years: float, efficiency_bol: float, years_source: str, efficiency_source: str):
    """How the efficiency at ``years`` in orbit was computed (``engine.trace``)."""
    from .trace import Quantity, Trace

    parameter = "parameter: power."
    inputs = [Quantity("beginning-of-life efficiency", "eta_BOL", efficiency_bol, "[-]", efficiency_source),
              Quantity("years in orbit", "t", years, "[year]", years_source),
              Quantity("ultraviolet darkening", "F_UV", found.uv_factor, "[-]", parameter + "uv_darkening_factor"),
              Quantity("thermal cycling", "F_thermal", found.thermal_factor, "[-]",
                       parameter + "thermal_cycling_factor")]
    if found.plugin_factor is not None:
        from ..config import models

        model = models.model(CHOICE, found.model)
        equation = f"eta = eta_BOL F_UV F_thermal F(t), F from {model.name}"
        reference = f"{model.title} (plugin {model.plugin}): " + "; ".join(model.references)
    elif found.model == "yearly_rate":
        equation = "eta = eta_BOL F_UV F_thermal (1 - D)^t"
        reference = "yearly rate: NASA/TM-2003-212513 (ISS P6 arrays, expected 2.7 %/yr); factors: NASA TM-86194"
        inputs.append(Quantity("yearly loss", "D", found.per_year, "[-]", parameter + "degradation_per_year"))
    else:
        equation = "eta = eta_BOL F_UV F_thermal (1 - C log10(1 + D_d t / D_x))"
        reference = ("displacement damage dose: Walters et al., NASA/CP-2007-214494, eq. 2; factors: NASA "
                     "TM-86194")
        inputs += [Quantity("yearly displacement damage dose", "D_d", found.dose_per_year_mev_g, "[MeV/g]",
                            parameter + "displacement_damage_dose_per_year_mev_g"),
                   Quantity("fit coefficient", "C", found.dose_fit_c, "[-]", parameter + "dose_fit_c"),
                   Quantity("fit dose", "D_x", found.dose_fit_dx_mev_g, "[MeV/g]", parameter + "dose_fit_dx_mev_g")]
    return Trace("Solar panel efficiency", "eta", efficiency_bol * found.remaining(years), "[-]", equation,
                 reference, inputs=tuple(inputs),
                 intermediates=(Quantity("the model's factor", "F(t)", found.time_factor(years), "[-]",
                                         f"computed: {found.model}"),))


def _make_module():
    from Basilisk.architecture import sysModel
    from Basilisk.utilities import macros

    from .orbit_maintenance import LogThinner

    class PanelDegradationModule(sysModel.SysModel):
        """Sets each of a spacecraft's solar panels' efficiency every step
        to its beginning-of-life value times :meth:`Degradation.remaining`
        (Basilisk's simpleSolarPanel reads it every step)."""

        def __init__(self, name: str, found: Degradation, panels: list, offset_s: float,
                     record_interval_s: float):
            super().__init__()
            self.ModelTag = name
            self.degradation = found
            self.panels = [(panel, float(panel.panelEfficiency)) for panel in panels]  # (module, BOL [-])
            self.offsetS = offset_s  # [s] flown before this run (a long run's earlier segments)
            self.logThinner = LogThinner(record_interval_s)
            self.tLog: list = []
            self.factorLog: list = []  # [-] remaining()

        def UpdateState(self, CurrentSimNanos):
            t = CurrentSimNanos * macros.NANO2SEC  # [s]
            factor = self.degradation.remaining(self.degradation.years_at(self.offsetS + t))
            for panel, efficiency_bol in self.panels:
                panel.panelEfficiency = efficiency_bol * factor
            if self.logThinner.due(t):
                self.tLog.append(t)
                self.factorLog.append(factor)

    return PanelDegradationModule


_MODULE = None
# Its priority in the dynamics task: before the solar panels (50), which read the efficiency.
PRIORITY = 51


def PanelDegradation(name: str, found: Degradation, panels: list, offset_s: float = 0.0,  # noqa: N802
                     record_interval_s: float = 0.0):
    """A :class:`PanelDegradationModule` (built on first use: Basilisk)."""
    global _MODULE
    if _MODULE is None:
        _MODULE = _make_module()
    return _MODULE(name, found, panels, offset_s, record_interval_s)
