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
"""Plugins: models, rules and parameters added without editing
SpaceMissionStudio (transparency plan, Phase 6c).

A plugin is an installed Python distribution that declares an entry point
in the group ``spacemissionstudio.models``::

    [project.entry-points."spacemissionstudio.models"]
    acme = "acme_rules:register"

The entry point names a function ``register(api)``. Through
:class:`PluginAPI` it may add, under its own name (``acme``):

* **parameters** (:meth:`PluginAPI.add_parameter`): named values of its
  own area, ``acme.<name>``, set like any other in a project
  configuration file and listed on the Assumptions page;
* **rules** (:meth:`PluginAPI.add_rule`): a pre-run check with its rule,
  why it matters and how to fix what it finds; its warnings carry the rule
  ``acme.<rule>`` and show with the other pre-run checks;
* **models** (:meth:`PluginAPI.add_model`): another model of a choice that
  takes one (:data:`PLUGGABLE`), declared like the built-in ones (method,
  inputs, outputs, assumptions, references, evidence).

What a plugin cannot add is anything Basilisk must simulate (a sensor,
an actuator, a flight-software mode, an atmosphere or shadow model):
those are wired into the simulation and still need SpaceMissionStudio's
code.

Plugins are loaded once, at the first use of the parameters. Each run
records the plugins loaded (name, distribution and version) and any model
of one it used. A plugin that fails to load is left out, with the reason
(:func:`problems`); ``SPACEMISSIONSTUDIO_PLUGINS=0`` loads none.

Basilisk-free, GUI-free.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field

GROUP = "spacemissionstudio.models"
ENVIRONMENT = "SPACEMISSIONSTUDIO_PLUGINS"  # "0": load none

# The choices a plugin may add a model to, and what its implementation is.
PLUGGABLE: dict[str, str] = {
    "link.atmospheric_loss": "implementation(rf_link, elevation_deg, scenario) -> the loss [dB] at that elevation",
    "power.degradation": "implementation(years, scenario) -> F(t) [-], the fraction kept after that many years "
                         "(F_UV and F_thermal are applied as for the built-in models)",
    "propellant_budget.margin_policy": "no implementation: the model's sets give the margins",
}
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_logger = logging.getLogger(__name__)


class PluginError(Exception):
    """A plugin asked for something it may not have."""


@dataclass
class Plugin:
    """One loaded plugin and what it added."""

    name: str  # the entry point's name: its parameters' area and its rules' prefix
    distribution: str
    version: str
    parameters: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    models: list[tuple[str, str]] = field(default_factory=list)  # (choice, model)

    def record(self, scenario=None) -> dict:
        """What a record keeps: the plugin, its parameters with the values
        in effect for ``scenario``, its rules and models."""
        from .config import registry

        return {"name": self.name, "distribution": self.distribution, "version": self.version,
                "parameters": {name: registry.value(name, scenario) for name in self.parameters},
                "rules": list(self.rules),
                "models": [f"{choice}: {name}" for choice, name in self.models]}


@dataclass(frozen=True)
class PluginCheck:
    """A plugin's pre-run check: ``check(scenario)`` gives ``(message,
    actual, limit)`` for each thing it finds (actual and limit may be None)."""

    plugin: str
    rule_id: str
    check: Callable


_PLUGINS: dict[str, Plugin] = {}
_PROBLEMS: list[str] = []
_CHECKS: list[PluginCheck] = []
_IMPLEMENTATIONS: dict[tuple[str, str], Callable] = {}
_loaded = False


class PluginAPI:
    """What ``register(api)`` may add; everything it adds is its own name's."""

    def __init__(self, plugin: Plugin):
        self._plugin = plugin

    @property
    def name(self) -> str:
        return self._plugin.name

    def add_parameter(self, name: str, default, unit: str, controls: str, source: str, rationale: str = "",
                      kind: str = "number", minimum: float | None = None, maximum: float | None = None,
                      choices: tuple | None = None) -> str:
        """Declare the parameter ``<plugin>.<name>``, as the built-in ones
        are (``config.registry.Parameter``); returns its full name."""
        from .config import registry

        full = f"{self.name}.{_checked_name(name, 'parameter')}"
        if kind == "model":
            raise PluginError(f"{full}: a plugin adds models to the existing choices (add_model), not new choices")
        registry.register(registry.Parameter(full, default, unit, controls, source, rationale, kind, minimum,
                                             maximum, choices))
        self._plugin.parameters.append(full)
        return full

    def add_rule(self, rule_id: str, rule: str, why: str, fix: str, check: Callable,
                 override: str = "A warning does not stop the run: run it as it is if the setup is intended.",
                 parameter: str | None = None) -> str:
        """Add the pre-run check ``check(scenario)`` (see :class:`PluginCheck`)
        under the rule ``<plugin>.<rule_id>``; returns the rule's id."""
        from .engine import findings

        full = f"{self.name}.{_checked_name(rule_id, 'rule')}"
        if full in findings.RULES:
            raise PluginError(f"rule {full!r} is declared twice")
        findings.RULES[full] = findings.Rule(full, rule, why, fix, override, parameter)
        _CHECKS.append(PluginCheck(self.name, full, check))
        self._plugin.rules.append(full)
        return full

    def add_model(self, choice: str, name: str, title: str, method: str, inputs, outputs, assumptions,
                  references, evidence, implementation: Callable | None = None, sets=()) -> str:
        """Add the model ``name`` to ``choice`` (one of :data:`PLUGGABLE`),
        declared as ``config.models.Model`` is; ``implementation`` as
        :data:`PLUGGABLE` says. Returns the model's name."""
        from .config import models, registry

        if choice not in PLUGGABLE:
            raise PluginError(f"{choice!r} does not take a plugin's model; these do: {', '.join(PLUGGABLE)}")
        name = _checked_name(name, "model")
        needs_code = choice != "propellant_budget.margin_policy"
        if needs_code and not callable(implementation):
            raise PluginError(f"{choice}: model {name!r} needs an implementation: {PLUGGABLE[choice]}")
        if not needs_code and not sets:
            raise PluginError(f"{choice}: model {name!r} sets nothing: a margin policy is the margins it sets")
        for set_name, value in sets:
            registry.parameter(set_name).check(value)
        models.register(models.Model(choice, name, title, method, tuple(inputs), tuple(outputs), tuple(assumptions),
                                     tuple(references), tuple(evidence), models.models(choice)[0].applies_to,
                                     tuple(sets), plugin=self.name))
        registry.replace_choices(choice, models.names(choice))
        if implementation is not None:
            _IMPLEMENTATIONS[(choice, name)] = implementation
        self._plugin.models.append((choice, name))
        return name


def _checked_name(name: str, what: str) -> str:
    if not isinstance(name, str) or not _NAME.match(name):
        raise PluginError(f"a {what}'s name is lower case letters, digits and underscores: {name!r}")
    return name


def _entry_points():
    from importlib.metadata import entry_points

    return list(entry_points(group=GROUP))


def load(entry_points=None) -> list[Plugin]:
    """Load the installed plugins (or ``entry_points``), once. Never raises:
    a plugin that fails is left out, with what it had added taken back,
    and named in :func:`problems`."""
    global _loaded
    if _loaded and entry_points is None:
        return list(_PLUGINS.values())
    _loaded = True
    if entry_points is None:
        if os.environ.get(ENVIRONMENT, "1").strip() == "0":
            return []
        try:
            entry_points = _entry_points()
        except Exception as exc:  # noqa: BLE001 -- a broken installation must not stop the tool
            _PROBLEMS.append(f"the plugins could not be listed: {exc}")
            return []
    from .config import registry

    builtin_areas = {parameter.area for parameter in registry.parameters()}
    for point in entry_points:
        name = point.name
        dist = getattr(point, "dist", None)
        plugin = Plugin(name, getattr(dist, "name", "") or "", getattr(dist, "version", "") or "")
        if not _NAME.match(name) or name in builtin_areas or name in _PLUGINS:
            _PROBLEMS.append(f"plugin {name!r} ({plugin.distribution}): its name must be new, lower case letters, "
                             "digits and underscores, and not a built-in area")
            continue
        try:
            register = point.load()
            register(PluginAPI(plugin))
        except Exception as exc:  # noqa: BLE001 -- reported, the others still load
            _logger.warning("plugin %s could not be loaded", name, exc_info=True)
            _take_back(plugin)
            _PROBLEMS.append(f"plugin {name!r} ({plugin.distribution}) was not loaded: {type(exc).__name__}: {exc}")
            continue
        _PLUGINS[name] = plugin
    return list(_PLUGINS.values())


def _take_back(plugin: Plugin) -> None:
    from .config import models, registry
    from .engine import findings

    for name in plugin.parameters:
        registry.unregister(name)
    for rule_id in plugin.rules:
        findings.RULES.pop(rule_id, None)
    _CHECKS[:] = [check for check in _CHECKS if check.plugin != plugin.name]
    for choice, name in plugin.models:
        models.unregister(choice, name)
        registry.replace_choices(choice, models.names(choice))
        _IMPLEMENTATIONS.pop((choice, name), None)


def unload() -> None:
    """Take back every plugin (tests; a reload)."""
    global _loaded
    for plugin in list(_PLUGINS.values()):
        _take_back(plugin)
    _PLUGINS.clear()
    _PROBLEMS.clear()
    _loaded = False


def loaded() -> list[Plugin]:
    return list(_PLUGINS.values())


def problems() -> list[str]:
    return list(_PROBLEMS)


def records(scenario=None) -> list[dict]:
    """The loaded plugins, as a record keeps them (:meth:`Plugin.record`)."""
    return [plugin.record(scenario) for plugin in _PLUGINS.values()]


def implementation(choice: str, model: str) -> Callable:
    """A plugin model's implementation. KeyError for a built-in model."""
    return _IMPLEMENTATIONS[(choice, model)]


def check_findings(scenario) -> list:
    """Every plugin check's findings for ``scenario``; a check that fails
    says so (``check.not_run``), as a built-in one does."""
    from .engine.findings import Finding

    load()  # a check before any parameter was read still has the plugins'
    out = []
    for found in list(_CHECKS):
        try:
            for item in found.check(scenario) or ():
                message, actual, limit = (tuple(item) + (None, None))[:3] if not isinstance(item, str) else (
                    item, None, None)
                out.append(Finding(str(message), found.rule_id, None if actual is None else str(actual),
                                   None if limit is None else str(limit)))
        except Exception as exc:  # noqa: BLE001 -- reported, not raised
            _logger.debug("plugin check %s could not run", found.rule_id, exc_info=True)
            out.append(Finding(f"check not run: {found.rule_id} ({type(exc).__name__}: {exc})", "check.not_run"))
    return out
