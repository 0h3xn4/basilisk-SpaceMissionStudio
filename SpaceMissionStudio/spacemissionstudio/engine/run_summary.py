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
"""A run's headline figures, for the Compare tab's summary (docs/ux-audit.md
U-33): one number per spacecraft and quantity, read from the recorded
series and the run's events, never estimated.

=============================  ==========================================
Figure                         From
=============================  ==========================================
Run length [h]                 the last recorded sample
Delta-V [m/s]                  the cumulative delta-V of the station-,
                               GEO-, phasing-keeping and constant-thrust
                               controllers, at the end
Propellant used [kg]           the drop of every recorded propellant mass
                               (the controllers' tanks, the fuel tank)
Mean semi-major axis change    the mean semi-major axis averaged over the
[km]                           last orbit minus over the first (the
                               averaging takes out what first-order mean
                               elements leave of the orbital-period
                               wobble); runs shorter than two orbits
                               have none
Lowest link margin [dB]        the lowest margin while a station is in view
Lowest battery charge [W*h]    the battery's lowest stored energy
Passes, contact time [min]     the passes (engine.events)
Eclipses, eclipse time [min]   the eclipses (engine.events)
Data downlinked [Gbit]         the data-handling ledger, at the end
=============================  ==========================================

A figure appears only when the run recorded what it comes from. The
orbital lifetime is not a run result (the End of Life tab computes it
from the scenario), so it is not here.

:func:`event_table` counts the events per kind of event ("pass over
berlin-gs", "eclipse (umbra)") with their total time, for the Compare
tab's events view.

Basilisk-free: it reads a :class:`engine.results.ResultSet` only.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from . import events as event_model
from .propellant_budget import MU_EARTH_M3_S2
from .results import ResultSet, TimeSeries

_DELTA_V_CONTROLLERS = ("station_keeping", "geo_station_keeping", "phasing_keeping", "constant_thrust")
_PROPELLANT_SUFFIXES = (".station_keeping.propellant_remaining", ".geo_station_keeping.propellant_remaining",
                        ".constant_thrust.propellant_remaining", ".fuel_mass_remaining")
_M_PER_KM = 1000.0  # [m/km]
_S_PER_MIN = 60.0  # [s/min]
_S_PER_H = 3600.0  # [s/h]
_BIT_PER_GBIT = 1e9  # [bit/Gbit]


@dataclass(frozen=True)
class Figure:
    """One headline number: ``key`` identifies it across runs."""

    key: str  # "sat-1.delta_v"
    label: str  # "sat-1: Delta-V"
    unit: str  # "m/s"
    value: float
    decimals: int  # shown at this many decimals

    def text(self) -> str:
        return f"{self.value:.{self.decimals}f}"


def _last(series: TimeSeries, column: int = 0) -> float | None:
    values = series.data[:, column] if series.data.shape[0] else np.zeros(0)
    finite = values[np.isfinite(values)]
    return float(finite[-1]) if finite.size else None


def _first(series: TimeSeries, column: int = 0) -> float | None:
    values = series.data[:, column] if series.data.shape[0] else np.zeros(0)
    finite = values[np.isfinite(values)]
    return float(finite[0]) if finite.size else None


def _orbit_averaged_change(series: TimeSeries) -> float | None:
    """Mean semi-major axis [m] averaged over the last orbit minus over the
    first; None for a run shorter than two orbits."""
    time_s, values = np.asarray(series.time_s, dtype=float), series.data[:, 0] if series.data.shape[0] else np.zeros(0)
    good = np.isfinite(values) & (values > 0.0)
    time_s, values = time_s[good], values[good]
    if time_s.size < 4:
        return None
    period_s = 2.0 * math.pi * math.sqrt(float(np.median(values)) ** 3 / MU_EARTH_M3_S2)  # [s]
    if time_s[-1] - time_s[0] < 2.0 * period_s:
        return None
    first = values[time_s <= time_s[0] + period_s]
    last = values[time_s >= time_s[-1] - period_s]
    return float(np.mean(last) - np.mean(first))  # [m]


def summarize(result: ResultSet | None, events: list[event_model.Event] | None = None) -> list[Figure]:
    """The headline figures of ``result`` (``events`` from
    :func:`engine.events.extract_events`, read here when not given)."""
    if result is None:
        return []
    events = event_model.extract_events(result) if events is None else events
    spacecraft = sorted({e.spacecraft for e in events} | {
        name[:-len(".position_N")] for name in result.series if name.endswith(".position_N")})
    several = len(spacecraft) > 1
    figures: list[Figure] = []

    def add(sc: str, key: str, label: str, unit: str, value: float | None, decimals: int) -> None:
        if value is not None and math.isfinite(value):
            figures.append(Figure(f"{sc}.{key}" if sc else key, f"{sc}: {label}" if several and sc else label,
                                  unit, float(value), decimals))

    end_s = max((float(s.time_s[-1]) for s in result.series.values() if s.time_s.size), default=None)  # [s]
    add("", "run_length", "Run length", "h", None if end_s is None else end_s / _S_PER_H, 2)
    for sc in spacecraft:
        delta_v = [_last(result.series[f"{sc}.{c}.delta_v"]) for c in _DELTA_V_CONTROLLERS
                   if f"{sc}.{c}.delta_v" in result.series]
        delta_v = [v for v in delta_v if v is not None]
        add(sc, "delta_v", "Delta-V", "m/s", sum(delta_v) if delta_v else None, 3)
        used = []
        for suffix in _PROPELLANT_SUFFIXES:
            series = result.series.get(f"{sc}{suffix}")
            if series is not None and _first(series) is not None:
                used.append(_first(series) - _last(series))  # [kg]
        add(sc, "propellant_used", "Propellant used", "kg", sum(used) if used else None, 3)
        sma = result.series.get(f"{sc}.orbit_elements_mean.semi_major_axis")
        change = _orbit_averaged_change(sma) if sma is not None else None
        add(sc, "mean_sma_change", "Mean semi-major axis change", "km",
            None if change is None else change / _M_PER_KM, 3)
        margins = [s.data[:, 0] for name, s in result.series.items()
                   if name.endswith(f".access_to_{sc}.link_margin_db") and s.data.shape[0]]
        finite = np.concatenate(margins)[np.isfinite(np.concatenate(margins))] if margins else np.zeros(0)
        add(sc, "lowest_link_margin", "Lowest link margin", "dB", float(finite.min()) if finite.size else None, 2)
        battery = result.series.get(f"{sc}.battery_charge")
        if battery is not None and battery.data.shape[0]:
            charge = battery.data[:, 0][np.isfinite(battery.data[:, 0])]
            add(sc, "lowest_battery_charge", "Lowest battery charge", "W*h",
                float(charge.min()) if charge.size else None, 2)
        mine = [e for e in events if e.spacecraft == sc]
        passes = [e for e in mine if e.kind == event_model.ACCESS]
        eclipses = [e for e in mine if e.kind == event_model.ECLIPSE]
        if any(name.endswith(f".access_to_{sc}.has_access") for name in result.series):
            add(sc, "passes", "Passes", "-", float(len(passes)), 0)
            add(sc, "contact_time", "Contact time", "min", sum(e.duration_s for e in passes) / _S_PER_MIN, 1)
        if f"{sc}.eclipse.illumination_factor" in result.series:
            add(sc, "eclipses", "Eclipses", "-", float(len(eclipses)), 0)
            add(sc, "eclipse_time", "Eclipse time", "min", sum(e.duration_s for e in eclipses) / _S_PER_MIN, 1)
        downlinked = result.series.get(f"{sc}.data_handling.data_downlinked")
        if downlinked is not None and _last(downlinked) is not None:
            add(sc, "data_downlinked", "Data downlinked", "Gbit", _last(downlinked) / _BIT_PER_GBIT, 3)
    return figures


def event_table(events: list[event_model.Event]) -> OrderedDict[str, tuple[int, float]]:
    """``{event label (with the spacecraft when there are several):
    (count, total duration [min])}``, in the order the events come."""
    several = len({e.spacecraft for e in events}) > 1
    table: OrderedDict[str, tuple[int, float]] = OrderedDict()
    for event in sorted(events, key=lambda e: (e.kind, e.spacecraft, e.label)):
        key = f"{event.spacecraft}: {event.label}" if several else event.label
        count, total = table.get(key, (0, 0.0))
        table[key] = (count + 1, total + event.duration_s / _S_PER_MIN)
    return table


def by_key(figures: list[Figure]) -> dict[str, Figure]:
    return {figure.key: figure for figure in figures}
