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


"""What a run's data handling did (``engine.data_handling``), read back
from its series: Basilisk-free, for the CLI and any other summary.

Each total carries its trace (``engine.trace``, ``DataBudget.traces``): the
ledger series and the sample it was read at (``run --explain`` prints them).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .results import ResultSet
from .trace import Quantity, Trace

_REFERENCE = "SpaceMissionStudio's data-handling ledger (docs/models/link-data-and-power.md)"
_LEDGER = {"data_generated": ("Data generated", "G", "the instruments' data, counted when made"),
           "data_downlinked": ("Data downlinked", "D", "the data the transmitter sent while the link closed"),
           "data_lost": ("Data lost", "L", "the data refused whole because the memory was full")}


@dataclass
class DataBudget:
    """One spacecraft's totals over a run [bit]."""

    spacecraft: str
    generated: float
    downlinked: float
    lost: float
    stored_end: float
    capacity_full: bool  # the memory was full at some point
    traces: dict[str, Trace] = field(default_factory=dict, compare=False, repr=False)  # how each total was read


def budgets(result: ResultSet) -> list[DataBudget]:
    """The data totals of every spacecraft that has data handling."""
    found = []
    for name in sorted(result.series):
        if not name.endswith(".data_handling.data_generated"):
            continue
        sc = name[:-len(".data_handling.data_generated")]
        last = {part: float(result.series[f"{sc}.data_handling.{part}"].data[-1, 0])
                for part in ("data_generated", "data_downlinked", "data_lost")}
        stored = result.series[f"{sc}.data_handling.stored"].data[:, 0]
        budget = DataBudget(sc, last["data_generated"], last["data_downlinked"], last["data_lost"],
                            float(stored[-1]), last["data_lost"] > 0)
        budget.traces = _traces(result, sc, budget)
        found.append(budget)
    return found


def _at_end(result: ResultSet, name: str) -> str:
    series = result.series[name]
    index = series.time_s.size - 1
    return f"last run: {name}, its last sample {index} (t = {float(series.time_s[index]):.10g} s)"


def _traces(result: ResultSet, sc: str, budget: DataBudget) -> dict[str, Trace]:
    traces = {}
    for part, value in (("data_generated", budget.generated), ("data_downlinked", budget.downlinked),
                        ("data_lost", budget.lost)):
        quantity, symbol, what = _LEDGER[part]
        name = f"{sc}.data_handling.{part}"
        traces[part] = Trace(quantity, symbol, value, "[bit]", f"{symbol} = the ledger's cumulative count at the end",
                             _REFERENCE, inputs=(Quantity(what, symbol, value, "[bit]", _at_end(result, name)),))
    stored = f"{sc}.data_handling.stored"
    traces["stored_end"] = Trace(
        "Data on board at the end", "S", budget.stored_end, "[bit]", "S = the memory's total at the end", _REFERENCE,
        inputs=(Quantity("data in every partition", "S", budget.stored_end, "[bit]",
                         _at_end(result, stored) + ", column total"),),
        notes=("Basilisk's partitionedStorageUnit storageLevel.",))
    traces["capacity_full"] = Trace(
        "Memory full at some point", "full", "yes" if budget.capacity_full else "no", "[-]", "full when L > 0",
        _REFERENCE, inputs=(Quantity("data lost", "L", budget.lost, "[bit]", "trace: Data lost"),),
        notes=("Data is lost only when a step's data does not fit in the memory.",))
    return traces


def summary_lines(result: ResultSet) -> list[str]:
    """One line per spacecraft: generated, downlinked, lost, left on board."""
    return [f"{b.spacecraft}: generated {b.generated / 1e9:.4g} Gbit, downlinked {b.downlinked / 1e9:.4g}, "
            f"lost to a full memory {b.lost / 1e9:.4g}, on board at the end {b.stored_end / 1e9:.4g}"
            for b in budgets(result)]
