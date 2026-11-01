# Monte Carlo statistics

How a Monte Carlo batch's spread is measured: each run's offset from the
mean of all runs, and the 1-sigma of those offsets. Code:
`spacemissionstudio/engine/monte_carlo_results.py`; the models are
declared in `spacemissionstudio/config/models.py` (see
[Selectable models](README.md#selectable-models)).

## The offsets

At each sample, R points from the central body to the runs' mean
position, W along the mean orbit's angular momentum, and S = W x R. A
run's offsets, in metres:

- **radial:** its distance from the central body minus the runs' mean
  distance;
- **along-track:** the arc, at that mean distance, by which it leads (+)
  or trails (-) R in the R-S plane;
- **cross-track:** the arc out of that plane.

Arcs, not straight lines: a straight-line frame would turn a large
along-track spread into a false radial one, as the orbit curves away from
the chord.

## The spread: `spread_statistic`

The spread is the standard deviation of each offset over the N runs that
succeeded, at each sample. Which standard deviation is a choice,
`monte_carlo.spread_statistic`, set in the project configuration like any
parameter:

```yaml
parameters:
  monte_carlo.spread_statistic: sample   # [-] population (default) or sample
```

| Model | Name | Formula | Use it when |
|---|---|---|---|
| Population standard deviation | `population` (default) | sqrt(sum((x_k - mean)^2) / N) | the spread should describe these runs |
| Sample standard deviation | `sample` | sqrt(sum((x_k - mean)^2) / (N - 1)) | the runs stand for the distribution the dispersions describe |

The sample standard deviation is sqrt(N / (N - 1)) times the population
one: 1.22 times for 3 runs, 1.05 for 10, 1.005 for 100. The difference
only matters for small batches.

### Population standard deviation (`population`)

- **Inputs:** each successful run's radial, along-track and cross-track
  offset from the batch's mean [m], at each sample; N, the number of runs
  that succeeded.
- **Outputs:** the `<spacecraft>.monte_carlo.spread` series [m], the Monte
  Carlo page's spread tiles, the command line's "1-sigma at the end" line.
- **Assumptions:** the spread describes these N runs only, not the
  distribution they were drawn from. One run gives a spread of 0.
- **Reference:** NumPy reference, `numpy.std`: the `ddof` argument (0, the
  default, divides by N).
- **Checked against:** `tests/test_monte_carlo_results.py` (the spread is
  `numpy.std` of the runs' offsets), `tests/test_model_registry.py` (the
  formula for three runs).
- **Why it is the default:** the tool used it before the choice existed,
  so every batch reads as it did. No derivation recorded.

### Sample standard deviation (`sample`)

- **Inputs and outputs:** as for the population standard deviation.
- **Assumptions:** the runs are a random sample of the distribution the
  dispersions describe. Dividing by N - 1 (Bessel's correction) makes the
  variance an unbiased estimate of that distribution's; the standard
  deviation itself is still slightly low for few runs. One run gives a
  spread of 0, since N - 1 would be 0.
- **Reference:** NumPy reference, `numpy.std`: the `ddof` argument (1
  divides by N - 1).
- **Checked against:** `tests/test_model_registry.py` (the formula, and
  the sqrt(3/2) ratio for three runs), `tests/test_monte_carlo.py` (a
  batch run with it keeps and records it).

## Where the choice shows

- **The batch keeps it:** `batch_results.json` records the statistic the
  batch was run with (`spread_statistic`), so a batch opened later reads
  the same, whatever the project file says by then. A summary written
  before the choice existed reads as `population`.
- **The batch's provenance** (`archive.provenance.json`) records it under
  `models`: the model's name, title, method and references.
- **The Monte Carlo page** names it in the line under the title
  ("... 1-sigma offsets from the mean of all runs (population standard
  deviation) ..."); its tooltip gives the formula.
- **The command line** prints it after the spread:
  `1-sigma: the population standard deviation of the 20 run(s)
  (monte_carlo.spread_statistic: population)`.

## Not covered

No other statistic (a percentile, a median absolute deviation) and no
confidence interval on the spread itself. The runs' drawn values and
final offsets are in the run table, and its CSV export, for any other
statistic.
