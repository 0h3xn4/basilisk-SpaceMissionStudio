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
"""The registry of selectable models (transparency plan, Phase 6a).

Where an analysis can be done more than one way, each way is a
:class:`Model`, declared here once with its name, what it computes and
how, its inputs and outputs, its assumptions, its references and the
tests that check it. A *choice* is the parameter that selects one
(:mod:`.registry`, ``kind="model"``): a project configuration file sets
it as it sets any other parameter, and the default is the model the tool
used before the choice existed, so no result changes until a project
chooses another. The model in effect is recorded with the results it
gives (:func:`records`).

Without Basilisk, and without the GUI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    """One way of computing something. ``choice`` is the parameter that
    selects it (``<area>.<name>``), ``name`` the value that parameter
    takes for it."""

    choice: str
    name: str
    title: str  # e.g. "Population standard deviation"
    method: str  # what it computes and how, with the formula
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    assumptions: tuple[str, ...]
    references: tuple[str, ...]
    evidence: tuple[str, ...]  # the tests that check it, "tests/<file>.py::<test>"
    applies_to: str  # the records it is written into: "monte_carlo" (a batch's provenance)


_MODELS: dict[str, dict[str, Model]] = {}


def register(*models: Model) -> None:
    for model in models:
        declared = _MODELS.setdefault(model.choice, {})
        if model.name in declared:
            raise ValueError(f"model {model.name!r} of {model.choice!r} is declared twice")
        if not (model.title and model.method and model.inputs and model.outputs and model.assumptions
                and model.references and model.evidence):
            raise ValueError(f"model {model.name!r} of {model.choice!r}: every part of its declaration is needed")
        declared[model.name] = model


def choices() -> list[str]:
    """The parameters that select a model, in declaration order."""
    return list(_MODELS)


def names(choice: str) -> tuple[str, ...]:
    """The models ``choice`` may select, in declaration order: the values
    its parameter may take."""
    return tuple(_MODELS[choice])


def models(choice: str) -> list[Model]:
    return list(_MODELS[choice].values())


def model(choice: str, name: str) -> Model:
    return _MODELS[choice][name]


def active(choice: str, scenario=None) -> Model:
    """The model in effect for ``scenario``: the one its configuration
    selects, else the default."""
    from . import registry

    return model(choice, registry.value(choice, scenario))


def record(found: Model) -> dict:
    """``found`` as a provenance record keeps it."""
    return {"model": found.name, "title": found.title, "method": found.method, "references": list(found.references)}


def records(scenario, applies_to: str) -> dict:
    """``{choice: record}`` of every model in effect for ``scenario`` that is
    written into ``applies_to``'s records."""
    return {choice: record(active(choice, scenario)) for choice in choices()
            if models(choice)[0].applies_to == applies_to}


# -- Monte Carlo statistics (engine.monte_carlo_results) ---------------------------------------

_SPREAD = "monte_carlo.spread_statistic"
_SPREAD_INPUTS = ("Each successful run's radial, along-track and cross-track offset from the batch's mean [m], "
                  "at each sample", "N, the number of runs that succeeded [-]")
_SPREAD_OUTPUTS = ("<spacecraft>.monte_carlo.spread [m], the series", "the Monte Carlo page's spread tiles",
                   "the command line's \"1-sigma at the end\" line")

register(
    Model(_SPREAD, "population", "Population standard deviation",
          "The square root of the mean squared offset: sqrt(sum((x_k - mean)^2) / N) over the N runs "
          "(numpy.std with ddof=0).",
          _SPREAD_INPUTS, _SPREAD_OUTPUTS,
          ("The runs are all that is described: the spread is that of these N runs, not an estimate of the "
           "distribution they were drawn from.",
           "One run gives a spread of 0."),
          ("NumPy reference, numpy.std: the ddof argument (ddof=0, the default, divides by N).",),
          ("tests/test_monte_carlo_results.py::test_result_set_has_per_run_series_and_the_spread",
           "tests/test_monte_carlo_results.py::test_run_table_lists_drawn_values_and_where_each_run_ended",
           "tests/test_model_registry.py::test_each_spread_statistic_is_the_one_it_declares"),
          "monte_carlo"),
    Model(_SPREAD, "sample", "Sample standard deviation",
          "The square root of the sum of squared offsets over N - 1: sqrt(sum((x_k - mean)^2) / (N - 1)) over "
          "the N runs (numpy.std with ddof=1, Bessel's correction). It is sqrt(N / (N - 1)) times the "
          "population standard deviation: 1.22 times for 3 runs, 1.005 times for 100.",
          _SPREAD_INPUTS, _SPREAD_OUTPUTS,
          ("The runs are a random sample of the distribution the dispersions describe; dividing by N - 1 makes "
           "the variance an unbiased estimate of that distribution's (the standard deviation itself is still "
           "slightly low for few runs).",
           "One run gives a spread of 0, as for the population standard deviation: N - 1 would be 0."),
          ("NumPy reference, numpy.std: the ddof argument (ddof=1 divides by N - 1).",),
          ("tests/test_model_registry.py::test_each_spread_statistic_is_the_one_it_declares",
           "tests/test_monte_carlo.py::test_a_batch_uses_and_records_the_statistic_its_configuration_chooses"),
          "monte_carlo"),
)
