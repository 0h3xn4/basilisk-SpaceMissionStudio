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
"""The events of a run, read from its recorded series (UX/UI guidelines:
"events as a timeline with a sortable, exportable table").

One model for every kind: ground-station passes, eclipses, manoeuvre
burns, thruster firings, mode changes and data downlinks. Each :class:`Event` is a
contiguous run of samples where a recorded series says the event is on,
from its first to its last such sample -- the convention the Results
tab's access timeline already uses. Nothing is simulated or estimated
here: a kind of event appears only when the run recorded the series it
comes from.

:func:`trace_of` gives how one event was found (``engine.trace``): the
series and the rule that says it is on, the first and last samples and
the samples either side of them (the event's times are known to within a
recording interval), and how its delta-V, data, elevation or sunlight was
taken. It reads the run again for that one event, so a run of 10,000
events costs nothing until one is asked about; the rules it states are the
ones extraction uses (:data:`_BURN_SOURCES`, :data:`_MODE_SOURCES` and the
``_on_*`` functions).

Basilisk-free: it reads a :class:`engine.results.ResultSet` only.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import Callable, Iterable

import numpy as np

from ..config import registry
from .results import ResultSet, TimeSeries
from .trace import Quantity, Trace

ACCESS = "pass"
ECLIPSE = "eclipse"
BURN = "burn"
THRUSTER = "thruster firing"
MODE = "mode"
DOWNLINK = "downlink"
KINDS = (ACCESS, ECLIPSE, BURN, THRUSTER, MODE, DOWNLINK)

# The measured values an event can carry (Event.quantities): key -> (column
# heading, unit, format). The Events table gives each its own column and the
# CSV export a ``<key>_<unit>`` column (docs/ux-audit.md U-31).
QUANTITIES: dict[str, tuple[str, str, str]] = {
    "max_elevation": ("Max elevation", "deg", ".1f"),
    "lowest_sunlight": ("Lowest sunlight", "%", ".0f"),
    "delta_v": ("Delta-V", "m/s", ".3f"),
    "data": ("Data", "Gbit", ".3f"),
}
_CSV_UNITS = {"deg": "deg", "%": "percent", "m/s": "m_s", "Gbit": "gbit"}

# The phasing controller's states (engine.orbit_maintenance.PhasingKeepingController).
_PHASING_IDLE, _PHASING_BURN_OUT, _PHASING_DRIFT, _PHASING_BURN_RESTORE = range(4)
_PHASING_FIRING = 4  # a Basilisk formation law firing (engine.formation_control.FIRING)
# engine.roe_formation states (not imported: events must load without Basilisk)
_ROE_IN_PLANE, _ROE_OUT_OF_PLANE, _ROE_DRIFTING, _ROE_CONTINUOUS = 2, 3, 4, 5

# Each burn: label -> (series suffix, ("column", index) or ("state", value), cumulative delta-V series suffix).
_BURN_SOURCES: dict[str, tuple[str, tuple[str, int], str]] = {
    "station-keeping burn": (".station_keeping.burn_on", ("column", 0), ".station_keeping.delta_v"),
    "east-west burn": (".geo_station_keeping.burn_on", ("column", 0), ".geo_station_keeping.east_west.delta_v"),
    "north-south burn": (".geo_station_keeping.burn_on", ("column", 1),
                         ".geo_station_keeping.north_south.delta_v"),
    "phasing burn (start drift)": (".phasing_keeping.state", ("state", _PHASING_BURN_OUT), ".phasing_keeping.delta_v"),
    "phasing burn (stop drift)": (".phasing_keeping.state", ("state", _PHASING_BURN_RESTORE),
                                  ".phasing_keeping.delta_v"),
    "formation control firing": (".phasing_keeping.state", ("state", _PHASING_FIRING), ".phasing_keeping.delta_v"),
    "ROE burn (in-plane)": (".roe_formation.state", ("state", _ROE_IN_PLANE), ".roe_formation.delta_v"),
    "ROE burn (out-of-plane)": (".roe_formation.state", ("state", _ROE_OUT_OF_PLANE), ".roe_formation.delta_v"),
    "ROE control firing": (".roe_formation.state", ("state", _ROE_CONTINUOUS), ".roe_formation.delta_v"),
}
# Each mode: label -> (series suffix, ("above", 0.5), ("not above", 0.5) or ("state", value), detail).
_MODE_SOURCES: dict[str, tuple[str, tuple[str, float], str]] = {
    "ground-station pointing": (".comms_pointing.active_mode", ("above", 0.5), "comms mode"),
    "Sun pointing": (".comms_pointing.active_mode", ("not above", 0.5), "power mode"),
    "ROE drift": (".roe_formation.state", ("state", _ROE_DRIFTING), "to the target's along-track offset"),
    "phasing drift": (".phasing_keeping.state", ("state", _PHASING_DRIFT), "between the two burns"),
}
_REFERENCE = "SpaceMissionStudio's events (docs/models/reading-results.md)"


@dataclass(frozen=True)
class Event:
    """One event: ``start_s`` to ``end_s`` [s] of elapsed (TDB) time since the epoch."""

    kind: str
    spacecraft: str
    start_s: float  # [s]
    end_s: float  # [s]
    label: str
    detail: str = ""
    other: str = ""  # the ground station of a pass
    quantities: tuple[tuple[str, float], ...] = ()  # (QUANTITIES key, value in its unit)
    note: str = ""  # what the detail says that is not a quantity (the thrusters that fired, the mode)

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s  # [s]

    def quantity(self, key: str) -> float | None:
        """The value of quantity ``key`` (in its :data:`QUANTITIES` unit), or None."""
        return dict(self.quantities).get(key)

    @property
    def row(self) -> str:
        """The timeline row this event is drawn on."""
        return f"{self.other} - {self.spacecraft}" if self.other else f"{self.spacecraft} {self.kind}"


def intervals(time_s: np.ndarray, on: np.ndarray) -> list[tuple[int, int]]:
    """``(first, last)`` sample indices of every contiguous run of ``on``."""
    on = np.asarray(on, dtype=bool)
    if on.size == 0:
        return []
    changes = np.flatnonzero(np.diff(np.concatenate([[False], on, [False]]).astype(int)))
    return list(zip(changes[0::2].tolist(), (changes[1::2] - 1).tolist()))


def _column(series: TimeSeries, index: int = 0) -> np.ndarray:
    return series.data[:, index] if series.data.shape[0] else np.zeros(0)


def _on_access(series: TimeSeries) -> np.ndarray:
    return _column(series) != 0


def _on_shaded(series: TimeSeries) -> np.ndarray:
    return _column(series) < 1.0


def _on_firing(series: TimeSeries) -> np.ndarray:
    return np.any(series.data > 0.0, axis=1)


def _on_link_closed(series: TimeSeries) -> np.ndarray:
    return _column(series) > 0.5


def _on_rule(series: TimeSeries, rule: tuple[str, float]) -> np.ndarray:
    """A burn's or a mode's rule (:data:`_BURN_SOURCES`, :data:`_MODE_SOURCES`)."""
    how, arg = rule
    if how == "column":
        return _column(series, int(arg)) != 0
    if how == "state":
        return np.rint(_column(series)).astype(int) == arg
    above = _column(series) > arg
    return above if how == "above" else ~above


def _rule_text(column: str, rule: tuple[str, float]) -> str:
    how, arg = rule
    return {"column": f"{column} != 0", "state": f"round({column}) == {arg}", "above": f"{column} > {arg}",
            "not above": f"{column} <= {arg}"}[how]


def _spans(series: TimeSeries, on: np.ndarray, make: Callable[[int, int], Event]) -> list[Event]:
    return [make(first, last) for first, last in intervals(series.time_s, on)]


def _delta_v_samples(series: TimeSeries, start_s: float, end_s: float) -> tuple[int, int]:
    """The samples a burn's delta-V is read between: the last before
    ``start_s`` and the first after ``end_s`` (the run's ends at most)."""
    before = max(int(np.searchsorted(series.time_s, start_s, side="left")) - 1, 0)
    after = min(int(np.searchsorted(series.time_s, end_s, side="right")), series.time_s.size - 1)
    return before, after


def _delta_v_between(result: ResultSet, name: str, start_s: float, end_s: float) -> float | None:
    """Cumulative delta-V [m/s] gained between two times, from ``name``."""
    series = result.series.get(name)
    if series is None or series.time_s.size == 0:
        return None
    values = _column(series)
    before, after = _delta_v_samples(series, start_s, end_s)
    return float(values[after] - values[before])  # [m/s]


def _passes(result: ResultSet) -> list[Event]:
    events = []
    for name, series in result.series.items():
        prefix, _, part = name.rpartition(".")
        if part != "has_access" or ".access_to_" not in prefix:
            continue
        station, _, spacecraft = prefix.partition(".access_to_")
        elevation = result.series.get(f"{prefix}.elevation")

        def make(first, last, series=series, station=station, spacecraft=spacecraft, elevation=elevation):
            detail, quantities = "", ()
            if elevation is not None and elevation.time_s.shape == series.time_s.shape:
                peak = math.degrees(float(np.max(_column(elevation)[first:last + 1])))  # [deg]
                detail, quantities = f"max elevation {peak:.1f} deg", (("max_elevation", peak),)
            return Event(ACCESS, spacecraft, float(series.time_s[first]), float(series.time_s[last]),
                         f"pass over {station}", detail, station, quantities)

        events += _spans(series, _on_access(series), make)
    return events


def _eclipses(result: ResultSet) -> list[Event]:
    events = []
    umbra = registry.value_of_run("results.umbra_sunlight_fraction", result)  # [-] below it the Sun is hidden
    for name, series in result.series.items():
        if not name.endswith(".eclipse.illumination_factor"):
            continue
        spacecraft = name[:-len(".eclipse.illumination_factor")]
        factor = _column(series)

        def make(first, last, series=series, spacecraft=spacecraft, factor=factor):
            deepest = float(np.min(factor[first:last + 1]))  # [-]
            label = "umbra" if deepest < umbra else "penumbra"
            return Event(ECLIPSE, spacecraft, float(series.time_s[first]), float(series.time_s[last]),
                         f"eclipse ({label})", f"lowest sunlight {deepest:.0%}",
                         quantities=(("lowest_sunlight", deepest * 100.0),))

        events += _spans(series, _on_shaded(series), make)
    return events


def _burns(result: ResultSet) -> list[Event]:
    events = []
    for name, series in result.series.items():
        for label, (suffix, rule, delta_v_suffix) in _BURN_SOURCES.items():
            if not name.endswith(suffix) or (rule[0] == "column" and rule[1] >= series.data.shape[1]):
                continue
            spacecraft = name[:-len(suffix)]
            events += _spans(series, _on_rule(series, rule),
                             _burn_maker(result, series, spacecraft, label, spacecraft + delta_v_suffix))
    return events


def _burn_maker(result, series, spacecraft, label, delta_v_name):
    def make(first, last):
        start, end = float(series.time_s[first]), float(series.time_s[last])
        delta_v = _delta_v_between(result, delta_v_name, start, end)
        if delta_v is None:
            return Event(BURN, spacecraft, start, end, label)
        return Event(BURN, spacecraft, start, end, label, f"delta-V {delta_v:.3f} m/s",
                     quantities=(("delta_v", delta_v),))
    return make


def _thruster_firings(result: ResultSet) -> list[Event]:
    events = []
    for name, series in result.series.items():
        if not name.endswith(".thruster_on_time") or series.data.shape[0] == 0:
            continue
        spacecraft = name[:-len(".thruster_on_time")]
        firing = _on_firing(series)

        def make(first, last, series=series, spacecraft=spacecraft):
            fired = [c for i, c in enumerate(series.columns) if np.any(series.data[first:last + 1, i] > 0.0)]
            return Event(THRUSTER, spacecraft, float(series.time_s[first]), float(series.time_s[last]),
                         "thruster firing", ", ".join(fired), note=", ".join(fired))

        events += _spans(series, firing, make)
    return events


def _modes(result: ResultSet) -> list[Event]:
    events = []
    for name, series in result.series.items():
        for label, (suffix, rule, detail) in _MODE_SOURCES.items():
            if not name.endswith(suffix):
                continue
            spacecraft = name[:-len(suffix)]
            events += _spans(series, _on_rule(series, rule), lambda f, la, s=series, sc=spacecraft, lb=label,
                             d=detail: Event(MODE, sc, float(s.time_s[f]), float(s.time_s[la]), lb, d, note=d))
    return events


def _downlinks(result: ResultSet) -> list[Event]:
    """Each window in which a spacecraft's link to a station closes and data
    went down (engine.data_handling), with how much. A pass that empties
    the memory early still counts as one downlink; two stations whose
    windows overlap both show the bits sent in the overlap."""
    events = []
    for name, series in result.series.items():
        prefix, _, part = name.rpartition(".")
        if part != "link_closed" or ".access_to_" not in prefix:
            continue
        station, _, spacecraft = prefix.partition(".access_to_")
        downlinked = result.series.get(f"{spacecraft}.data_handling.data_downlinked")
        if downlinked is None or downlinked.time_s.shape != series.time_s.shape:
            continue
        values = _column(downlinked)
        for first, last in intervals(series.time_s, _on_link_closed(series)):
            bits = values[last] - values[max(first - 1, 0)]  # [bit]
            if bits > 0:
                events.append(Event(DOWNLINK, spacecraft, float(series.time_s[first]), float(series.time_s[last]),
                                    f"downlink to {station}", f"{bits / 1e9:.3g} Gbit", station,
                                    (("data", bits / 1e9),)))
    return events


_EXTRACTORS = (_passes, _eclipses, _burns, _thruster_firings, _modes, _downlinks)


# -- how one event was found ---------------------------------------------------------------------

def _source(result: ResultSet, event: Event) -> tuple[str, np.ndarray, str]:
    """(the series ``event`` was found in, where its rule is true, the rule)."""
    sc, other = event.spacecraft, event.other
    if event.kind == ACCESS:
        name = f"{other}.access_to_{sc}.has_access"
        return name, _on_access(result.series[name]), "has_access != 0 (the station sees the spacecraft)"
    if event.kind == ECLIPSE:
        name = f"{sc}.eclipse.illumination_factor"
        return name, _on_shaded(result.series[name]), "illumination_factor < 1 (any shading)"
    if event.kind == BURN:
        suffix, rule, _delta_v = _BURN_SOURCES[event.label]
        series = result.series[sc + suffix]
        column = series.columns[int(rule[1])] if rule[0] == "column" else series.columns[0]
        return sc + suffix, _on_rule(series, rule), _rule_text(column, rule)
    if event.kind == THRUSTER:
        name = f"{sc}.thruster_on_time"
        return name, _on_firing(result.series[name]), "any thruster's on-time > 0"
    if event.kind == MODE:
        suffix, rule, _detail = _MODE_SOURCES[event.label]
        series = result.series[sc + suffix]
        return sc + suffix, _on_rule(series, rule), _rule_text(series.columns[0], rule)
    if event.kind == DOWNLINK:
        name = f"{other}.access_to_{sc}.link_closed"
        return name, _on_link_closed(result.series[name]), "link_closed > 0.5 (the link closes), with data sent"
    raise ValueError(f"no rule for an event of kind {event.kind!r}")


def _sample(name: str, time_s: np.ndarray, index: int) -> str:
    return f"last run: {name}, sample {index} (t = {float(time_s[index]):.10g} s)"


def trace_of(result: ResultSet, event: Event) -> list[Trace]:
    """How ``event`` was found in ``result``: its span first, then the
    trace of each value it carries (delta-V, data, elevation, sunlight).
    Raises ``KeyError`` when ``result`` lacks the event's series."""
    name, on, rule = _source(result, event)
    series = result.series[name]
    time_s = series.time_s
    first = int(np.searchsorted(time_s, event.start_s))
    last = int(np.searchsorted(time_s, event.end_s))
    if not (on[first:last + 1].all() and (first == 0 or not on[first - 1])
            and (last + 1 == time_s.size or not on[last + 1])):
        raise ValueError(f"{event.label} is not a run of samples of {name} where {rule}")
    intermediates, notes = [], ["Times are elapsed seconds since the scenario epoch (TDB)."]
    if first > 0:
        intermediates.append(Quantity("the sample before, with the rule false", "t_before",
                                      float(time_s[first - 1]), "[s]", _sample(name, time_s, first - 1)))
    if last + 1 < time_s.size:
        intermediates.append(Quantity("the sample after, with the rule false", "t_after",
                                      float(time_s[last + 1]), "[s]", _sample(name, time_s, last + 1)))
    notes.append("It began after t_before and ended before t_after: its times are known to within a recording "
                 "interval at each end." if len(intermediates) == 2 else
                 "It runs to an end of the run's record, which may cut it short.")
    values = _value_traces(result, event, name, first, last)
    intermediates += [Quantity(value.quantity.lower(), value.symbol, value.value, value.unit, f"trace: {value.quantity}")
                      for value in values]
    span = Trace(f"{event.label} ({event.spacecraft})", "T", event.duration_s, "[s]",
                 f"on where {rule}; t_start, t_end = the first and last samples on; T = t_end - t_start",
                 _REFERENCE,
                 inputs=(Quantity("first sample with the rule true", "t_start", float(time_s[first]), "[s]",
                                  _sample(name, time_s, first)),
                         Quantity("last sample with the rule true", "t_end", float(time_s[last]), "[s]",
                                  _sample(name, time_s, last))),
                 intermediates=tuple(intermediates), notes=tuple(notes))
    return [span] + values


def _value_traces(result: ResultSet, event: Event, name: str, first: int, last: int) -> list[Trace]:
    """The traces of what ``event`` carries, each read as extraction reads it."""
    sc = event.spacecraft
    if event.kind == ACCESS and event.quantity("max_elevation") is not None:
        elevation_name = name.rsplit(".", 1)[0] + ".elevation"
        elevation = result.series[elevation_name]
        at = first + int(np.argmax(_column(elevation)[first:last + 1]))
        return [Trace("Max elevation", "el_max", math.degrees(float(_column(elevation)[at])), "[deg]",
                      "el_max = the highest el over the pass's samples, in degrees", _REFERENCE,
                      inputs=(Quantity("elevation at its highest", "el", float(_column(elevation)[at]), "[rad]",
                                       _sample(elevation_name, elevation.time_s, at)),))]
    if event.kind == ECLIPSE:
        factor = _column(result.series[name])
        at = first + int(np.argmin(factor[first:last + 1]))
        umbra = registry.value_of_run("results.umbra_sunlight_fraction", result)  # [-]
        deepest = float(factor[at])  # [-]
        return [Trace("Lowest sunlight", "f_min", deepest * 100.0, "[%]",
                      "f_min = the lowest f over the eclipse x 100; umbra when f < u there, else penumbra",
                      _REFERENCE,
                      inputs=(Quantity("illumination factor at its lowest", "f", deepest, "[-]",
                                       _sample(name, result.series[name].time_s, at)),
                              Quantity("sunlight below which it is umbra", "u", umbra, "[-]",
                                       "parameter: results.umbra_sunlight_fraction")),
                      intermediates=(Quantity("umbra or penumbra", "kind", "umbra" if deepest < umbra else "penumbra",
                                              "[-]", "computed: f < u"),))]
    if event.kind == BURN and event.quantity("delta_v") is not None:
        delta_v_name = sc + _BURN_SOURCES[event.label][2]
        series = result.series[delta_v_name]
        before, after = _delta_v_samples(series, event.start_s, event.end_s)
        values = _column(series)
        return [Trace("Delta-V", "dV", float(values[after] - values[before]), "[m/s]",
                      "dV = dV_after - dV_before: the cumulative delta-V at the sample after the burn less at the "
                      "sample before it", _REFERENCE,
                      inputs=(Quantity("cumulative delta-V before the burn", "dV_before", float(values[before]),
                                       "[m/s]", _sample(delta_v_name, series.time_s, before)),
                              Quantity("cumulative delta-V after the burn", "dV_after", float(values[after]),
                                       "[m/s]", _sample(delta_v_name, series.time_s, after))))]
    if event.kind == DOWNLINK:
        data_name = f"{sc}.data_handling.data_downlinked"
        series = result.series[data_name]
        values = _column(series)
        before = max(first - 1, 0)
        return [Trace("Data downlinked", "D", float(values[last] - values[before]) / 1e9, "[Gbit]",
                      "D = (D_end - D_before) / 1e9: the data downlinked by the window's last sample less by the "
                      "sample before it", _REFERENCE,
                      inputs=(Quantity("data downlinked before the window", "D_before", float(values[before]), "[bit]",
                                       _sample(data_name, series.time_s, before)),
                              Quantity("data downlinked by its end", "D_end", float(values[last]), "[bit]",
                                       _sample(data_name, series.time_s, last))))]
    return []


def extract_events(result: ResultSet | None) -> list[Event]:
    """Every event in ``result``, sorted by start time. Never raises: a
    series that cannot be read is skipped (the rest still show)."""
    if result is None:
        return []
    events: list[Event] = []
    for extractor in _EXTRACTORS:
        try:
            events += extractor(result)
        except (ValueError, IndexError, TypeError):
            continue
    return sorted(events, key=lambda e: (e.start_s, e.kind, e.spacecraft, e.label))


def missing_kinds(result: ResultSet | None) -> dict[str, str]:
    """Kinds this run could not show, and why (the series was not recorded)."""
    names = list(result.series) if result is not None else []
    reasons = {
        ACCESS: ("no ground stations", lambda n: n.endswith(".has_access")),
        ECLIPSE: ("no Sun ephemeris (add 'sun' to the third-body perturbers)",
                  lambda n: n.endswith(".eclipse.illumination_factor")),
        BURN: ("no station-keeping or formation control",
               lambda n: n.endswith((".burn_on", ".phasing_keeping.state", ".roe_formation.state"))),
        MODE: ("no comms pointing or formation control",
               lambda n: n.endswith((".comms_pointing.active_mode", ".phasing_keeping.state",
                                     ".roe_formation.state"))),
        DOWNLINK: ("no data handling", lambda n: n.endswith(".data_handling.downlink_rate")),
    }
    return {kind: why for kind, (why, has) in reasons.items() if not any(has(n) for n in names)}


def write_csv(events: Iterable[Event], path: str | Path, epoch_utc: str | None = None) -> Path:
    """The events as CSV. With an epoch, UTC start and end columns are added;
    then one ``<quantity>_<unit>`` column per :data:`QUANTITIES` entry any
    event carries (empty where an event has none)."""
    events = list(events)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    utc = _utc_columns(events, epoch_utc)
    keys = present_quantities(events)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["kind", "spacecraft", "ground_station", "event", "start_s", "end_s", "duration_s",
                         "detail"] + (["start_utc", "end_utc"] if utc else [])
                        + [f"{key}_{_CSV_UNITS[QUANTITIES[key][1]]}" for key in keys])
        for index, event in enumerate(events):
            writer.writerow([event.kind, event.spacecraft, event.other, event.label, f"{event.start_s:.3f}",
                             f"{event.end_s:.3f}", f"{event.duration_s:.3f}", event.detail]
                            + (list(utc[index]) if utc else [])
                            + [_csv_number(event.quantity(key)) for key in keys])
    return path


def present_quantities(events: Iterable[Event]) -> list[str]:
    """The :data:`QUANTITIES` keys any of ``events`` carries, in table order."""
    carried = {key for event in events for key, _value in event.quantities}
    return [key for key in QUANTITIES if key in carried]


def _csv_number(value: float | None) -> str:
    return "" if value is None else repr(float(value))


def _utc_columns(events: list[Event], epoch_utc: str | None) -> list[tuple[str, str]]:
    if not epoch_utc or not events:
        return []
    from . import time_system

    try:
        starts = time_system.elapsed_to_utc(epoch_utc, [e.start_s for e in events])
        ends = time_system.elapsed_to_utc(epoch_utc, [e.end_s for e in events])
    except ValueError:
        return []
    return [(utc_text(s), utc_text(e)) for s, e in zip(starts, ends)]


def utc_text(moment: datetime, timespec: str = "milliseconds") -> str:
    """ISO UTC text rounded (not cut) to ``timespec`` ("seconds" or "milliseconds")."""
    half = timedelta(seconds=0.5) if timespec == "seconds" else timedelta(milliseconds=0.5)
    return (moment + half).isoformat(sep=" ", timespec=timespec)
