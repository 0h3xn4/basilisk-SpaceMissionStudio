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
"""The registry of named parameters (transparency audit, Phase 3a): every
engineering value or rule the analyses use, with its unit, what it
controls, where it comes from and why, and the values it may take.

A parameter is declared once, in :mod:`.parameters`. The code reads the
value in effect with :func:`value`: the default, or the one a scenario's
project configuration sets (:class:`Configuration`, :mod:`.files`).

Without Basilisk, and without the GUI.
"""

from __future__ import annotations

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
    kind: str = "number"  # "number", "integer" or "number list"
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple | None = None  # the only values it may take, e.g. MSFC's (95, 50, 5) percentiles

    @property
    def area(self) -> str:
        return self.name.split(".", 1)[0]

    def check(self, value):
        """``value`` as this parameter's kind, or :class:`ConfigError`
        naming the parameter and what it may take."""
        if self.kind == "number list":
            if not isinstance(value, (list, tuple)) or not value:
                raise ConfigError(f"{self.name}: a list of numbers {self.unit}, got {value!r}")
            return tuple(self._number(v) for v in value)
        number = self._number(value)
        if self.choices is not None and number not in self.choices:
            raise ConfigError(f"{self.name}: one of {', '.join(f'{c:g}' for c in self.choices)} {self.unit}, "
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


def value(name: str, scenario=None):
    """The value of ``name`` in effect for ``scenario``: the one its
    configuration sets, else the default."""
    configuration = getattr(scenario, "configuration", None)
    if configuration is not None and name in configuration.overrides:
        return configuration.overrides[name]
    return default(name)


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
    return {"file": configuration.file if configuration is not None else None,
            "overrides": {name: {"value": _plain(v), "default": _plain(parameter(name).default),
                                 "unit": parameter(name).unit, "source": parameter(name).source}
                          for name, v in sorted(overrides.items())}}


def recorded_value(name: str, configuration_record: dict | None):
    """The value of ``name`` a run had, from its :func:`record` (a
    provenance's ``configuration``; None or empty: the defaults), so a
    result shown later is judged by the run's own rules."""
    override = ((configuration_record or {}).get("overrides") or {}).get(name)
    return parameter(name).check(override["value"]) if override is not None else default(name)


def value_of_run(name: str, result):
    """The value of ``name`` the run ``result`` (an engine.results.ResultSet)
    had, from its provenance's configuration; the default without one."""
    provenance = getattr(result, "provenance", None)
    return recorded_value(name, getattr(provenance, "configuration", None))


def _plain(value):
    return list(value) if isinstance(value, tuple) else value
