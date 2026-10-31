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
"""A spacecraft's power at one moment of a run, as the mission dashboard
shows it, with how each figure was read (transparency plan, Phase 4a).

Basilisk computes the power (``simpleSolarPanel``, ``simplePowerSink``,
``simpleBattery``; docs/models/link-data-and-power.md); the run records the
battery's stored energy and its net power. SpaceMissionStudio reads them at
the time cursor, the last sample at or before it (:func:`sample_index`), and
works out one figure of its own, the state of charge
(:func:`state_of_charge_pct`). :func:`battery_traces` gives each figure's
trace.

Basilisk-free: it reads a :class:`engine.results.ResultSet` only.
"""

from __future__ import annotations

import numpy as np

from .results import ResultSet, TimeSeries
from .trace import Quantity, Trace

_REFERENCE = "Basilisk's simpleBattery, as the run recorded it (docs/models/link-data-and-power.md)"
_S_PER_H = 3600.0  # [s/h]


def sample_index(series: TimeSeries, at_s: float | None) -> int:
    """The last sample at or before ``at_s`` [s] (the time cursor), else the last one."""
    if at_s is None:
        return series.data.shape[0] - 1
    return max(int(np.searchsorted(series.time_s, at_s, side="right")) - 1, 0)


def state_of_charge_pct(charge_wh: float, capacity_wh: float) -> float:
    """The stored energy as a share of the capacity [%], held to 0..100."""
    return max(0.0, min(100.0, 100.0 * charge_wh / capacity_wh))


def _read(result: ResultSet, name: str, at_s: float | None) -> tuple[float, str] | None:
    series = result.series.get(name)
    if series is None or series.data.shape[0] == 0:
        return None
    index = sample_index(series, at_s)
    when = "the time cursor" if at_s is not None else "the end of the run"
    return float(series.data[index, 0]), (f"last run: {name}, sample {index} (t = {float(series.time_s[index]):.10g} "
                                          f"s), the last at or before {when}")


def battery_traces(result: ResultSet, spacecraft: str, capacity_wh: float | None = None,
                   at_s: float | None = None) -> dict[str, Trace]:
    """``{"charge", "net_power", "state_of_charge"}`` of ``spacecraft`` at
    ``at_s`` (None: the end of the run), each present when the run recorded
    what it needs; the state of charge also needs ``capacity_wh``, the
    scenario's battery capacity."""
    traces: dict[str, Trace] = {}
    charge = _read(result, f"{spacecraft}.battery_charge", at_s)
    net = _read(result, f"{spacecraft}.battery_net_power", at_s)
    if charge is not None:
        traces["charge"] = Trace(
            "Battery charge", "E", charge[0], "[W*h]", "E = the battery's stored energy, as recorded", _REFERENCE,
            inputs=(Quantity("stored energy", "E", charge[0], "[W*h]", charge[1]),),
            notes=("The run records Basilisk's storageLevel [W*s] divided by 3600.",
                   "Basilisk holds it between 0 and the capacity."))
    if net is not None:
        traces["net_power"] = Trace(
            "Net power", "P_net", net[0], "[W]", "P_net = the power into the battery less the power drawn, as "
            "recorded", _REFERENCE,
            inputs=(Quantity("net power", "P_net", net[0], "[W]", net[1]),),
            notes=("Basilisk's simpleBattery sums the solar panels' power and the loads' power draw (negative).",
                   "Negative: the battery is discharging."))
    if charge is not None and capacity_wh is not None and capacity_wh > 0:
        soc = state_of_charge_pct(charge[0], capacity_wh)  # [%]
        traces["state_of_charge"] = Trace(
            "State of charge", "SOC", soc, "[%]", "SOC = 100 * E / E_cap, held to 0..100",
            "SpaceMissionStudio's dashboard (docs/models/reading-results.md)",
            inputs=(Quantity("battery charge", "E", charge[0], "[W*h]", "trace: Battery charge"),
                    Quantity("battery capacity", "E_cap", capacity_wh, "[W*h]",
                             "scenario: spacecraft.power.battery_capacity_wh")))
    return traces
