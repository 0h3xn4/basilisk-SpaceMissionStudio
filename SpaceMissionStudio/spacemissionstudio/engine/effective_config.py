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
"""The effective configuration of a run: the values it used that are not
in the scenario file (transparency audit, Phase 2c).

Two kinds, recorded in the run's provenance:

- **Defaults of the open ``params``** (``effective_defaults``): a sensor's,
  an actuator's or a command's ``params``, and a spacecraft's
  ``fsw_params`` and ``control_params``, hold only the keys the file gives.
  The engine reads the others with a default
  (``params.get("fov_deg", 90.0)``). :func:`record` puts each of these
  dictionaries in a :class:`RecordedParams`, which notes every key read and
  missing, with the default the reader passed: the value used. A default
  of ``None`` means the engine set nothing, so the Basilisk module keeps
  its own value (or the option is off).
- **Basilisk's device values** (``device_parameters``): a named reaction
  wheel or thruster type (``rw_type``, ``thruster_type``) takes its
  inertia, torque, thrust, Isp and so on from Basilisk's factory. They are
  read back from the devices the factory made (:func:`factory_devices`).

Without Basilisk; :func:`factory_devices` reads the objects it is given.
"""

from __future__ import annotations

import math

# How the two are to be read, recorded beside them.
NOTE = ("effective_defaults: each key the engine read that the file does not give, with the value it used; null: "
        "the engine set nothing, so the Basilisk module keeps its own value or the option is off. "
        "device_parameters: the values Basilisk's factories gave each wheel and thruster, in Basilisk's SI units "
        "(kg, kg*m^2, rad/s, N*m, N, s, W)")

# Attributes of a Basilisk reaction wheel (simIncludeRW) and thruster
# (simIncludeThruster) recorded as the device's values.
RW_ATTRIBUTES = ("RWModel", "Js", "Jt", "Jg", "mass", "Omega_max", "u_max", "u_min", "P_max", "U_s", "U_d",
                 "fCoulomb", "fStatic", "betaStatic", "cViscous")
THRUSTER_ATTRIBUTES = ("MaxThrust", "steadyIsp", "MinOnTime", "areaNozzle", "MaxSwirlTorque", "cutoffFrequency",
                       "thrusterMagDisp")


class RecordedParams(dict):
    """A ``params`` dictionary that notes the keys read with :meth:`get`
    that it does not hold, and the default each reader passed
    (``defaults``); the first read of a key is the one kept. ``where`` is
    its place in the scenario, e.g. ``spacecraft[sat-1].sensors[css-1].params``.
    It is still a ``dict`` with the same items: equal to one, written to
    JSON as one."""

    def __init__(self, data=(), where: str = ""):
        super().__init__(data)
        self.where = where
        self.defaults: dict = {}

    def get(self, key, default=None):
        if key not in self and key not in self.defaults:
            self.defaults[key] = default
        return super().get(key, default)


def _commands(commands, where: str):
    for index, command in enumerate(commands):
        path = f"{where}[{index}]"
        yield command, f"{path}.params"
        yield from _commands(command.children, f"{path}.children")


def record(scenario) -> list[RecordedParams]:
    """Put each open ``params`` dictionary of ``scenario`` in a
    :class:`RecordedParams`, in place, and return them. A dictionary
    already recorded is kept, its notes cleared: the run that builds now
    starts from nothing read. Call it once the scenario is validated, so
    that only the engine's reads are noted."""
    owners = []
    for sc in scenario.spacecraft:
        prefix = f"spacecraft[{sc.name}]"
        owners += [(device, f"{prefix}.{group}[{device.name}].params")
                   for group, devices in (("sensors", sc.sensors), ("actuators", sc.actuators)) for device in devices]
        owners += [(sc, f"{prefix}.fsw_params", "fsw_params"), (sc, f"{prefix}.control_params", "control_params")]
    owners += list(_commands(scenario.mission_sequence, "mission_sequence"))
    recorded = []
    for owner, where, *attribute in owners:
        name = attribute[0] if attribute else "params"
        params = getattr(owner, name)
        if not isinstance(params, RecordedParams):
            params = RecordedParams(params, where)
            setattr(owner, name, params)
        params.where, params.defaults = where, {}
        recorded.append(params)
    return recorded


def _plain(value):
    """``value`` as JSON: numbers, lists, strings, None; numpy and SWIG
    values made plain; a value that is not a number or a list as text."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if isinstance(value, int):
        return int(value)
    return number if math.isfinite(number) else str(number)


def defaults_used(recorded: list[RecordedParams]) -> dict:
    """``{where: {key: value used}}`` of the keys read and missing, for the
    dictionaries that had any."""
    return {params.where: {key: _plain(value) for key, value in sorted(params.defaults.items())}
            for params in recorded if params.defaults}


def factory_devices(devices, actuators, where: str, attributes) -> dict:
    """``{where[actuator]: {attribute: value}}``: the values a Basilisk
    factory gave the devices it made (``rwFactory.rwList``,
    ``thrusterFactory.thrusterList``, in creation order), for the
    ``actuators`` they were made from, in the same order."""
    out = {}
    for actuator, device in zip(actuators, devices.values()):
        out[f"{where}[{actuator.name}]"] = {name: _plain(getattr(device, name)) for name in attributes
                                           if hasattr(device, name)}
    return out
