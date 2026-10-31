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
                               GEO-, phasing-keeping, constant-thrust and
                               ROE formation controllers, at the end
Propellant used [kg]           the drop of every recorded propellant mass
                               (the controllers' tanks, the fuel tank)
Mean semi-major axis change    the mean semi-major axis averaged over the
[km]                           last orbit (from the central body's GM)
                               minus over the first (the
                               averaging takes out what first-order mean
                               elements leave of the orbital-period
                               wobble); runs shorter than two orbits
                               have none. The window is
                               ``results.sma_window_orbits`` (1 orbit),
                               as the run had it
Lowest link margin [dB]        the lowest margin while a station is in view
Lowest battery charge [W*h]    the battery's lowest stored energy
Passes, contact time [min]     the passes (engine.events)
Eclipses, eclipse time [min]   the eclipses (engine.events)
Data downlinked [Gbit]         the data-handling ledger, at the end
=============================  ==========================================

A figure appears only when the run recorded what it comes from. Each
carries its calculation trace (``engine.trace``): the series it was read
from, the parameters and constants it used, and the values on the way. The
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
from dataclasses import dataclass, field

import numpy as np

from ..config import registry
from . import events as event_model
from . import mean_elements
from . import orbit_number
from .results import ResultSet, TimeSeries
from .trace import Quantity, Trace

_DELTA_V_CONTROLLERS = ("station_keeping", "geo_station_keeping", "phasing_keeping", "constant_thrust",
                        "roe_formation")  # the ROE controller left out in 1.3.1 and earlier (audit 3.5)
_PROPELLANT_SUFFIXES = (".station_keeping.propellant_remaining", ".geo_station_keeping.propellant_remaining",
                        ".constant_thrust.propellant_remaining", ".fuel_mass_remaining")
_M_PER_KM = 1000.0  # [m/km]
_S_PER_MIN = 60.0  # [s/min]
_S_PER_H = 3600.0  # [s/h]
_BIT_PER_GBIT = 1e9  # [bit/Gbit]
_REFERENCE = "SpaceMissionStudio's run summary (docs/models/reading-results.md)"


@dataclass(frozen=True)
class Figure:
    """One headline number: ``key`` identifies it across runs."""

    key: str  # "sat-1.delta_v"
    label: str  # "sat-1: Delta-V"
    unit: str  # "m/s"
    value: float
    decimals: int  # shown at this many decimals
    trace: Trace | None = field(default=None, compare=False, repr=False)  # how it was computed
    related: tuple[Trace, ...] = field(default=(), compare=False, repr=False)  # traces its trace opens

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


def _orbit_averaged(series: TimeSeries, mu_m3_s2: float, window_orbits: float = 1.0) -> dict | None:
    """The parts of :func:`_orbit_averaged_change`: the median semi-major
    axis [m], the window [s], the samples and mean [m] at each end; None
    for a run shorter than two windows."""
    time_s, values = np.asarray(series.time_s, dtype=float), series.data[:, 0] if series.data.shape[0] else np.zeros(0)
    good = np.isfinite(values) & (values > 0.0)
    time_s, values = time_s[good], values[good]
    if time_s.size < 4:
        return None
    median = float(np.median(values))  # [m]
    window_s = window_orbits * 2.0 * math.pi * math.sqrt(median ** 3 / mu_m3_s2)  # [s]
    if time_s[-1] - time_s[0] < 2.0 * window_s:
        return None
    first = values[time_s <= time_s[0] + window_s]
    last = values[time_s >= time_s[-1] - window_s]
    return {"median": median, "window_s": window_s, "first_n": int(first.size), "last_n": int(last.size),
            "first": float(np.mean(first)), "last": float(np.mean(last)),
            "change": float(np.mean(last) - np.mean(first))}  # [m]


def _orbit_averaged_change(series: TimeSeries, mu_m3_s2: float, window_orbits: float = 1.0) -> float | None:
    """Mean semi-major axis [m] averaged over the last ``window_orbits``
    orbits minus over the first; None for a run shorter than two windows.
    The orbit period comes from ``mu_m3_s2``, the central body's (audit
    3.14: Earth's was used for every body)."""
    parts = _orbit_averaged(series, mu_m3_s2, window_orbits)
    return None if parts is None else parts["change"]


def _q(name: str, symbol: str, value, unit: str, source: str) -> Quantity:
    return Quantity(name, symbol, value, unit, source)


def _sum_trace(quantity: str, symbol: str, value: float, unit: str, equation: str,
               inputs: list[Quantity], notes: tuple[str, ...] = ()) -> Trace:
    return Trace(quantity, symbol, value, unit, equation, _REFERENCE, inputs=tuple(inputs), notes=notes)


def _at_time(series: TimeSeries, index: int) -> float:
    return float(series.time_s[index])  # [s]


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

    def add(sc: str, key: str, label: str, unit: str, value: float | None, decimals: int,
            trace=None, related=()) -> None:
        """``trace``: a function of the value giving its trace."""
        if value is not None and math.isfinite(value):
            figures.append(Figure(f"{sc}.{key}" if sc else key, f"{sc}: {label}" if several and sc else label,
                                  unit, float(value), decimals, trace(float(value)) if trace else None,
                                  tuple(related)))

    window_orbits = registry.value_of_run("results.sma_window_orbits", result)  # [orbit]
    ends = [(float(s.time_s[-1]), name) for name, s in result.series.items() if s.time_s.size]
    end_s, end_name = max(ends) if ends else (None, "")  # [s]
    add("", "run_length", "Run length", "h", None if end_s is None else end_s / _S_PER_H, 2,
        lambda v: _sum_trace("Run length", "T", v, "[h]", "T = t_end / 3600", [
            _q("time of the run's last recorded sample", "t_end", end_s, "[s]",
               f"last run: {end_name}, its last sample (the latest of every series)")]))
    for sc in spacecraft:
        _summarize_spacecraft(result, events, sc, window_orbits, add)
    return figures


def _summarize_spacecraft(result: ResultSet, events, sc: str, window_orbits: float, add) -> None:
    """The figures of one spacecraft (:func:`summarize`)."""
    delta_v = []  # (controller, series name, value)
    for c in _DELTA_V_CONTROLLERS:
        name = f"{sc}.{c}.delta_v"
        value = _last(result.series[name]) if name in result.series else None
        if value is not None:
            delta_v.append((c, name, value))
    add(sc, "delta_v", "Delta-V", "m/s", sum(v for _c, _n, v in delta_v) if delta_v else None, 3,
        lambda v: _sum_trace("Delta-V", "dV", v, "[m/s]", "dV = sum of each controller's cumulative delta-V at the end", [
            _q(f"{c.replace('_', ' ')}'s cumulative delta-V", f"dV_{c}", value, "[m/s]",
               f"last run: {name}, its last finite sample") for c, name, value in delta_v]))

    tanks = []  # (series name, first, last)
    for suffix in _PROPELLANT_SUFFIXES:
        name = f"{sc}{suffix}"
        series = result.series.get(name)
        if series is not None and _first(series) is not None:
            tanks.append((name, _first(series), _last(series)))
    used = [first - last for _n, first, last in tanks]  # [kg]
    add(sc, "propellant_used", "Propellant used", "kg", sum(used) if used else None, 3,
        lambda v: _sum_trace("Propellant used", "m", v, "[kg]", "m = sum over the tanks of (m0 - m1)", [
            quantity for k, (name, first, last) in enumerate(tanks, 1) for quantity in (
                _q(f"{name}: at the start", f"m0_{k}", first, "[kg]", f"last run: {name}, its first finite sample"),
                _q(f"{name}: at the end", f"m1_{k}", last, "[kg]", f"last run: {name}, its last finite sample"))]))

    sma_name = f"{sc}.orbit_elements_mean.semi_major_axis"
    sma = result.series.get(sma_name)
    mu, mu_source = orbit_number.central_body_mu_and_source(result) if sma is not None else (None, "")
    parts = _orbit_averaged(sma, mu, window_orbits) if sma is not None else None
    made = mean_elements.series_trace(result, sc) if parts is not None else None
    add(sc, "mean_sma_change", "Mean semi-major axis change", "km",
        None if parts is None else parts["change"] / _M_PER_KM, 3,
        lambda v: Trace("Mean semi-major axis change", "da", v, "[km]",
                        "da = (mean of a over the last window - mean of a over the first) / 1000;  "
                        "window = N * 2 pi sqrt(a_med^3 / mu)", _REFERENCE,
                        inputs=(_q("averaging window", "N", window_orbits, "[orbit]",
                                   "parameter: results.sma_window_orbits"),
                                _q("central body's gravitational parameter", "mu", mu, "[m^3/s^2]", mu_source)),
                        intermediates=(
                            _q("median mean semi-major axis", "a_med", parts["median"], "[m]",
                               f"last run: {sma_name}, the median of its finite positive samples"),
                            _q("averaging window", "window", parts["window_s"], "[s]",
                               "computed: N * 2 pi sqrt(a_med^3 / mu)"),
                            _q(f"mean over the first window ({parts['first_n']} samples)", "a_first",
                               parts["first"], "[m]", f"last run: {sma_name}, its first window"),
                            _q(f"mean over the last window ({parts['last_n']} samples)", "a_last",
                               parts["last"], "[m]", f"last run: {sma_name}, its last window"))
                        + (() if made is None else (_q("how the mean elements were made", "mean", made.value, "[-]",
                                                       f"trace: {made.quantity}"),)),
                        notes=("First-order mean elements still wobble at the orbital period; averaging a whole "
                               "orbit at each end takes it out.",)),
        related=() if made is None else (made,))

    lowest = None  # (value, series name, time)
    for name, series in result.series.items():
        if name.endswith(f".access_to_{sc}.link_margin_db") and series.data.shape[0]:
            values = series.data[:, 0]
            finite = np.flatnonzero(np.isfinite(values))
            if finite.size:
                at = int(finite[np.argmin(values[finite])])
                if lowest is None or values[at] < lowest[0]:
                    lowest = (float(values[at]), name, _at_time(series, at))
    add(sc, "lowest_link_margin", "Lowest link margin", "dB", None if lowest is None else lowest[0], 2,
        lambda v: _sum_trace("Lowest link margin", "M_min", v, "[dB]", "M_min = min of M while a station is in view", [
            _q("link margin at its lowest", "M", lowest[0], "[dB]",
               f"last run: {lowest[1]}, at t = {lowest[2]:.10g} s")],
            ("The run records the margin only while the station is in view (and, with comms pointing, while the "
             "spacecraft points at it); elsewhere it is not a number.",)))

    battery_name = f"{sc}.battery_charge"
    battery = result.series.get(battery_name)
    if battery is not None and battery.data.shape[0]:
        values = battery.data[:, 0]
        finite = np.flatnonzero(np.isfinite(values))
        at = int(finite[np.argmin(values[finite])]) if finite.size else None
        add(sc, "lowest_battery_charge", "Lowest battery charge", "W*h",
            None if at is None else float(values[at]), 2,
            lambda v: _sum_trace("Lowest battery charge", "E_min", v, "[W*h]", "E_min = min of E over the run", [
                _q("battery's stored energy at its lowest", "E", float(values[at]), "[W*h]",
                   f"last run: {battery_name}, at t = {_at_time(battery, at):.10g} s")]))

    mine = [e for e in events if e.spacecraft == sc]
    passes = [e for e in mine if e.kind == event_model.ACCESS]
    eclipses = [e for e in mine if e.kind == event_model.ECLIPSE]
    access_names = sorted(name for name in result.series if name.endswith(f".access_to_{sc}.has_access"))
    if access_names:
        per_station = [(name, [e for e in passes if f"{e.other}.access_to_{sc}.has_access" == name])
                       for name in access_names]
        sampled = ("A pass runs from its first recorded sample in view to its last, so its time is known to "
                   "within a recording interval at each end.",)
        add(sc, "passes", "Passes", "-", float(len(passes)), 0,
            lambda v: _sum_trace("Passes", "N", v, "[-]", "N = number of passes over every station", [
                _q(f"passes over {name.split('.access_to_')[0]}", f"N_{k}", len(found), "[-]",
                   f"last run: {name}, each run of samples in view") for k, (name, found) in enumerate(per_station, 1)],
                sampled))
        add(sc, "contact_time", "Contact time", "min", sum(e.duration_s for e in passes) / _S_PER_MIN, 1,
            lambda v: _sum_trace("Contact time", "T_c", v, "[min]", "T_c = sum of the passes' durations / 60", [
                _q(f"time over {name.split('.access_to_')[0]} ({len(found)} passes)", f"T_{k}",
                   sum(e.duration_s for e in found), "[s]", f"last run: {name}, each run of samples in view")
                for k, (name, found) in enumerate(per_station, 1)], sampled))
    eclipse_name = f"{sc}.eclipse.illumination_factor"
    if eclipse_name in result.series:
        umbra = sum(1 for e in eclipses if e.label == "eclipse (umbra)")
        shaded = ("Any shading counts: an eclipse is a run of samples whose illumination factor is below 1, "
                  "from its first such sample to its last.",)
        add(sc, "eclipses", "Eclipses", "-", float(len(eclipses)), 0,
            lambda v: _sum_trace("Eclipses", "N", v, "[-]", "N = N_umbra + N_penumbra", [
                _q("umbra eclipses (lowest sunlight below results.umbra_sunlight_fraction)", "N_umbra", umbra,
                   "[-]", f"last run: {eclipse_name}, each run of samples below 1"),
                _q("penumbra eclipses", "N_penumbra", len(eclipses) - umbra, "[-]",
                   f"last run: {eclipse_name}, each run of samples below 1")], shaded))
        add(sc, "eclipse_time", "Eclipse time", "min", sum(e.duration_s for e in eclipses) / _S_PER_MIN, 1,
            lambda v: _sum_trace("Eclipse time", "T_e", v, "[min]", "T_e = sum of the eclipses' durations / 60", [
                _q(f"time in the {len(eclipses)} eclipses", "T", sum(e.duration_s for e in eclipses), "[s]",
                   f"last run: {eclipse_name}, each run of samples below 1")], shaded))
    downlinked_name = f"{sc}.data_handling.data_downlinked"
    downlinked = result.series.get(downlinked_name)
    if downlinked is not None and _last(downlinked) is not None:
        add(sc, "data_downlinked", "Data downlinked", "Gbit", _last(downlinked) / _BIT_PER_GBIT, 3,
            lambda v: _sum_trace("Data downlinked", "D", v, "[Gbit]", "D = D_end / 1e9", [
                _q("data downlinked by the end", "D_end", _last(downlinked), "[bit]",
                   f"last run: {downlinked_name}, its last finite sample")]))


def explain_lines(figures: list[Figure]) -> list[str]:
    """Each figure with its value, then how it was computed (``run --explain``)."""
    lines = []
    for figure in figures:
        lines += ["", f"{figure.label}: {figure.text()} {figure.unit}"]
        for trace in ((figure.trace,) if figure.trace is not None else ()) + figure.related:
            lines += [f"  {line}" for line in trace.text()]
    return lines


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
