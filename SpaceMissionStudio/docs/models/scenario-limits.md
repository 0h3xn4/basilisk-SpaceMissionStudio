# The scenario file's limits

The limits a scenario file must keep to. A file past one is refused: it
is invalid, not warned about, and the run does not start. The message
says what is wrong, and the error names its rule (`engine/findings.py`):
what the limit is, the value found, why the limit is there and how to
fix it.

Code: `spacemissionstudio/schema/scenario.py` (`SimSettings`,
`Scenario.validate`, `name_error`, `load_scenario`) and
`engine/constellation.py`. Where the rule shows:
- **The editor's Problems panel:** hover over the error;
- **`spacemissionstudio validate --explain`:** the rule follows the
  `INVALID` line (exit status 1, as without `--explain`).

## The limits and their rules

| Limit | Value | Rule | Why |
|---|---|---|---|
| A run's length | 3660 days (about 10 years) | `schema.duration_max` | Runs past 100 days are chains of shorter simulations (`engine/long_run.py`); no derivation recorded for the 10 years |
| A run that cannot be split | 100 days | `schema.single_run` | One Basilisk run keeps time in nanoseconds in a double, exact to about 104 days. A run around a small body, or with a mission sequence, phasing keeping, an ROE formation or optical navigation, is one simulation |
| The dynamics step | at least 0.001 s | `schema.step_min` | The editor's least; a smaller step was accepted and asked for 86 400 billion steps a day (audit R9) |
| Spacecraft in a scenario, or a generated constellation | at most 1000 | `schema.spacecraft_max` | Far above any real scenario (the templates have at most 6): it stops a mistyped or damaged input (audit R9) |
| The description | at most 100 000 characters | `schema.description_max` | It stops a damaged input (audit R9) |
| The scenario file | at most 20 MB | `schema.file_size_max` | The templates are at most 27 KB; a larger file is refused after reading one byte past the limit, never whole (audit R9) |
| A name (spacecraft, part, sensor, actuator, ground station) | at most 64 characters | `schema.name_length` | Names become file names and the first part of series names (audit R8) |
| A data-handling instrument's name | at most 127 characters | `schema.data_name_length` | Basilisk's `DataNodeUsageMsgPayload.dataName` is `char[128]` |
| Monte Carlo runs | at most 100 000 | `schema.monte_carlo_runs` | The editor's own range: it stops a mistyped count (audit R4) |
| Monte Carlo processes | at most 256 | `schema.monte_carlo_threads` | As for the runs; the batch uses at most one process per CPU in any case |
| An ROE formation's chief eccentricity | at most 0.01 | `schema.roe_chief_eccentricity` | The ROE guidance (`engine/roe.py`) is the near-circular one |

None is a parameter: each is a constant of the code, and the error says
so. A project configuration file cannot change them.

## Checks without a limit

The other checks of a scenario file say whether a value can mean
anything at all: a mass that is positive, an eccentricity below 1, an
elevation between -90 and 90 deg, a name without a `/`. They are refused
with their message, which states the rule; they name no rule id.

## Checked against

- `tests/test_schema_findings.py`: a scenario past each limit is refused
  with the message as before and the rule, the value found and the
  limit; a check without a limit names no rule; `validate --explain`.
- `tests/gui/test_findings_views.py`: the Problems panel's tooltip for an
  error past a limit.
