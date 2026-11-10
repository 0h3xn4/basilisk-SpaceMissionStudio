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
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""The registry of named parameters (transparency audit, Phase 3a): every
engineering value or rule the analyses use, with its unit, what it
controls, where it comes from and why, and the values it may take.

A parameter is declared once, in :mod:`.parameters`. The code reads the
value in effect with :func:`value`: the default, or the one a scenario's
project configuration sets (:class:`Configuration`, :mod:`.files`).

Without Basilisk, and without the GUI.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field


class ConfigError(Exception):
    """A configuration that names an unknown parameter or a value it may
    not take, or a file that cannot be read."""


@dataclass(frozen=True)
class Parameter:
    """One named value. ``name`` is ``<area>.<parameter>``, e.g.
    ``propellant_budget.cam_count_factor``."""

    name: str
    default: object
    unit: str  # e.g. "[-]", "[m]", "[%]"
    controls: str  # what the value changes, in one sentence
    source: str  # the standard, document or study it comes from
    rationale: str = ""  # why this value, when the source alone does not say
    kind: str = "number"  # "number", "integer", "number list" or "model" (the name of a model, .models)
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple | None = None  # the only values it may take, e.g. MSFC's (95, 50, 5) percentiles

    def choices_text(self) -> str:
        """The values it may take, as the messages and pages name them."""
        return ", ".join(c if isinstance(c, str) else f"{c:g}" for c in self.choices or ())

    @property
    def area(self) -> str:
        return self.name.split(".", 1)[0]

    def check(self, value):
        """``value`` as this parameter's kind, or :class:`ConfigError`
        naming the parameter and what it may take."""
        if self.kind == "model":
            if not isinstance(value, str) or value not in (self.choices or ()):
                raise ConfigError(f"{self.name}: one of {self.choices_text()}, got {value!r}")
            return value
        if self.kind == "number list":
            if not isinstance(value, (list, tuple)) or not value:
                raise ConfigError(f"{self.name}: a list of numbers {self.unit}, got {value!r}")
            return tuple(self._number(v) for v in value)
        number = self._number(value)
        if self.choices is not None and number not in self.choices:
            raise ConfigError(f"{self.name}: one of {self.choices_text()} {self.unit}, "
                              f"got {value!r}")
        if self.kind == "integer":
            if number != int(number):
                raise ConfigError(f"{self.name}: a whole number, got {value!r}")
            return int(number)
        return number

    def _number(self, value) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ConfigError(f"{self.name}: a finite number {self.unit}, got {value!r}")
        if self.minimum is not None and value < self.minimum:
            raise ConfigError(f"{self.name}: at least {self.minimum:g} {self.unit}, got {value!r}")
        if self.maximum is not None and value > self.maximum:
            raise ConfigError(f"{self.name}: at most {self.maximum:g} {self.unit}, got {value!r}")
        return float(value)


@dataclass
class Configuration:
    """The values a scenario's project configuration changes, and the file
    they come from (:func:`.files.read`). ``error`` is set, and nothing
    else, when the file named cannot be used; the scenario then does not
    validate."""

    overrides: dict = field(default_factory=dict)  # {name: value}, checked
    file: dict | None = None  # {"path", "sha256"} of the file read
    error: str = ""


_REGISTRY: dict[str, Parameter] = {}


def register(*parameters: Parameter) -> None:
    for parameter in parameters:
        if parameter.name in _REGISTRY:
            raise ValueError(f"parameter {parameter.name!r} is declared twice")
        parameter.check(parameter.default)  # a default it may not take is a fault here, not in a user's file
        _REGISTRY[parameter.name] = parameter


def _declare() -> None:
    from . import parameters as _declared  # noqa: F401 -- declares them on first use
    from .. import plugins

    plugins.load()  # once: the installed plugins' parameters, rules and models (Phase 6c)


def unregister(name: str) -> None:
    """Take back a plugin's parameter (``spacemissionstudio.plugins``)."""
    _REGISTRY.pop(name, None)


def replace_choices(name: str, choices: tuple) -> None:
    """A choice's models after a plugin added (or took back) one."""
    _REGISTRY[name] = dataclasses.replace(_REGISTRY[name], choices=tuple(choices))


def parameters(area: str | None = None) -> list[Parameter]:
    """The parameters, in declaration order; of ``area`` only, when given."""
    _declare()
    return [p for p in _REGISTRY.values() if area is None or p.area == area]


def parameter(name: str) -> Parameter:
    _declare()  # not parameters(): a simulation step reads values through here
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ConfigError(f"unknown parameter {name!r}") from None


def default(name: str):
    return parameter(name).default


def effective(name: str, overrides: dict | None = None):
    """The value of ``name`` given a configuration's ``overrides``: the one
    they set; else the one a model in effect sets (``.models``, e.g. a
    margin policy); else the default."""
    overrides = overrides or {}
    if name in overrides:
        return overrides[name]
    from . import models

    setter = models.set_by(name, overrides)
    return dict(setter.sets)[name] if setter is not None else default(name)


def value(name: str, scenario=None):
    """The value of ``name`` in effect for ``scenario``: the one its
    configuration sets, else the one a model it chooses sets, else the
    default."""
    return effective(name, _overrides(scenario))


def set_by(name: str, scenario=None):
    """The model (``.models.Model``) whose value of ``name`` is in effect for
    ``scenario``; None when the configuration sets it itself or no model
    does."""
    from . import models

    overrides = _overrides(scenario)
    return None if name in overrides else models.set_by(name, overrides)


def _overrides(scenario) -> dict:
    configuration = getattr(scenario, "configuration", None)
    return configuration.overrides if configuration is not None else {}


def check_models() -> None:
    """Each choice of model is a parameter of kind "model" whose values are
    its models, and each value a model sets is one its parameter may take:
    a fault here, at import, not in a user's file."""
    from . import models

    for choice in models.choices():
        declared = parameter(choice)
        if declared.kind != "model" or tuple(declared.choices or ()) != models.names(choice):
            raise ValueError(f"{choice}: not a parameter of kind 'model' with the choices {models.names(choice)}")
        for found in models.models(choice):
            for name, set_value in found.sets:
                if name in models.choices():
                    raise ValueError(f"{choice}: model {found.name!r} sets the choice {name!r}")
                parameter(name).check(set_value)


def checked_overrides(values: dict, where: str) -> dict:
    """``values`` ({name: value}) checked against the registry; unknown
    names and values out of range raise :class:`ConfigError` naming
    ``where``."""
    out = {}
    for name, raw in values.items():
        try:
            out[name] = parameter(str(name)).check(raw)
        except ConfigError as exc:
            raise ConfigError(f"{where}: {exc}") from None
    return out


def record(scenario) -> dict:
    """The configuration of ``scenario`` for a provenance record: the file
    read (path, SHA-256) and each value it changes, with the default it
    replaces and its unit and source. Empty overrides: every parameter has
    its default."""
    configuration = getattr(scenario, "configuration", None)
    overrides = configuration.overrides if configuration is not None else {}
    out = {"file": configuration.file if configuration is not None else None,
           "overrides": {name: {"value": _plain(v), "default": _plain(parameter(name).default),
                                "unit": parameter(name).unit, "source": parameter(name).source}
                         for name, v in sorted(overrides.items())}}
    from . import models

    set_by_models = {}  # the values a chosen model sets in place of the defaults, when it sets any
    for name in sorted(p.name for p in parameters()):
        setter = None if name in overrides else models.set_by(name, overrides)
        if setter is not None:
            set_by_models[name] = {"value": _plain(dict(setter.sets)[name]), "default": _plain(default(name)),
                                   "unit": parameter(name).unit, "model": f"{setter.choice}: {setter.name}"}
    if set_by_models:
        out["set_by_models"] = set_by_models
    return out


def recorded_value(name: str, configuration_record: dict | None):
    """The value of ``name`` a run had, from its :func:`record` (a
    provenance's ``configuration``; None or empty: the defaults), so a
    result shown later is judged by the run's own rules."""
    overrides = (configuration_record or {}).get("overrides") or {}
    chosen = {other: parameter(other).check(entry["value"]) for other, entry in overrides.items()
              if other == name or other in _model_choices()}
    return effective(name, chosen)


def value_of_run(name: str, result):
    """The value of ``name`` the run ``result`` (an engine.results.ResultSet)
    had, from its provenance's configuration; the default without one."""
    provenance = getattr(result, "provenance", None)
    return recorded_value(name, getattr(provenance, "configuration", None))


def _model_choices() -> list[str]:
    from . import models

    return models.choices()


def _plain(value):
    return list(value) if isinstance(value, tuple) else value
