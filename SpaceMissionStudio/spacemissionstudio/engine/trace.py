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
"""Calculation traces (transparency plan, Phase 4a): how a computed number
was reached, written by the calculation that reached it.

A :class:`Trace` holds:
- the equation;
- the inputs, each with its unit and where it came from (a scenario
  field, a named parameter, a constant, the last run, or another trace);
- the intermediate values;
- the result, in its unit;
- the standard and clause the equation comes from.

A trace is plain data: ``to_dict`` gives JSON for the exports, and
``text`` gives lines for the command line (``--explain``) and the app.

The calculation builds its trace from the same values it computes with, so
the trace cannot describe a different calculation. Tests then recompute
each result from its trace's inputs alone (``tests/test_trace.py``).

No Basilisk, no GUI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Where an input comes from. The text after the colon names it, e.g.
#: ``"parameter: propellant_budget.cam_count_factor"``.
SOURCE_KINDS = ("scenario", "parameter", "constant", "last run", "computed", "trace")


@dataclass(frozen=True)
class Quantity:
    """One named value of a trace."""

    name: str  # what it is, e.g. "mass before the burn"
    symbol: str  # as the equation writes it, e.g. "m"
    value: float | int | str | None
    unit: str  # e.g. "[kg]", "[-]"
    source: str = ""  # e.g. "scenario: spacecraft.dry_mass_kg", "parameter: propellant_budget.cam_count_factor"

    def to_dict(self) -> dict:
        return {"name": self.name, "symbol": self.symbol, "value": self.value, "unit": self.unit,
                "source": self.source}

    def text(self) -> str:
        value = f"{self.value:.10g}" if isinstance(self.value, float) else str(self.value)
        source = f"  ({self.source})" if self.source else ""
        return f"{self.symbol} = {value} {self.unit}  {self.name}{source}"


@dataclass(frozen=True)
class Trace:
    """How one result was computed."""

    quantity: str  # what the result is, e.g. "Collision avoidance delta-V"
    symbol: str
    value: float | None
    unit: str
    equation: str  # e.g. "dV = N f v dA / a"
    reference: str  # the standard and clause, e.g. "ESA AD10 Sec. 6.2.4", or "SpaceMissionStudio's own"
    inputs: tuple[Quantity, ...] = ()
    intermediates: tuple[Quantity, ...] = ()
    notes: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict:
        return {"quantity": self.quantity, "symbol": self.symbol, "value": self.value, "unit": self.unit,
                "equation": self.equation, "reference": self.reference,
                "inputs": [q.to_dict() for q in self.inputs],
                "intermediates": [q.to_dict() for q in self.intermediates],
                "notes": list(self.notes)}

    def text(self) -> list[str]:
        """The trace as lines: the result, the equation and its reference,
        then the inputs, the intermediates and the notes."""
        value = "-" if self.value is None else f"{self.value:.10g}"
        lines = [f"{self.quantity}: {self.symbol} = {value} {self.unit}",
                 f"  {self.equation}   [{self.reference}]"]
        if self.inputs:
            lines.append("  inputs:")
            lines += [f"    {q.text()}" for q in self.inputs]
        if self.intermediates:
            lines.append("  intermediates:")
            lines += [f"    {q.text()}" for q in self.intermediates]
        lines += [f"  note: {note}" for note in self.notes]
        return lines

    def input(self, symbol: str):
        """The value of the input (or intermediate) written ``symbol``."""
        for quantity in self.inputs + self.intermediates:
            if quantity.symbol == symbol:
                return quantity.value
        raise KeyError(f"{self.quantity}: no input {symbol!r}")
