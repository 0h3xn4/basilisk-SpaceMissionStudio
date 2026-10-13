# Plan a mission in steps (Mission Sequence)

How to fly a mission as a list of commands (coast, burn, report, repeat)
instead of one run of a fixed length.

## Add commands

1. In the **Scenario Editor**, go to the **Mission sequence** section.
2. **Add...** adds a command after the selected one; **Add Child...** adds
   one inside an `if` or `while`. **Edit...**, **Remove** and **Move
   Up/Down** do what they say.
3. Run it as usual (**Run > Run Simulation**). The run follows the
   commands instead of the scenario's duration.

## The commands

| Command | Does |
|---|---|
| `propagate` | Coasts until a stop condition: a **duration**, an **epoch**, or an **event** |
| `maneuver` | An instant burn: a delta-V in the `inertial`, `vnb` (velocity, normal, binormal) or `rtn` (radial, along-track, normal) frame |
| `lambert_transfer` | Works out the burn that reaches a target position after a set time, and applies it |
| `assignment` | Sets a value, for example a spacecraft field |
| `report` | Records chosen quantities at this moment; the **Output** view of Results shows them |
| `if` / `while` | Runs the commands inside it when, or while, a condition is true |
| `script_block` | Runs your own Python code (see below) |

A `propagate` can stop at these events: `periapsis`, `apoapsis`, and
`pass_start` or `pass_end` of the next pass over a ground station. A
`pass_start` issued during a pass waits for the next one.

## Conditions

`if` and `while` take a short expression, for example:

```text
spacecraft["sat-1"]["altitude_m"] < 500e3
t_s < 86400
```

The names available are `t_s` (elapsed time [s]), `duration_days`, and
`spacecraft`, where each spacecraft has `r_BN_N`, `v_BN_N`, `altitude_m`
and `mass_kg`. Conditions are checked by a small expression reader, not
by Python's `eval()`, so they cannot run code. A `while` stops with an
error after 10 000 rounds.

## Script blocks ask first

A `script_block` is unrestricted Python. Before a run with script blocks,
the app shows the code in a **Run script blocks?** dialog; the default is
**No**. From the command line, `spacemissionstudio run` refuses to start
a scenario with script blocks unless you add `--allow-scripts`. Only allow scripts from files you trust and
have read.

## Examples

- Template **08**: coast, report, a prograde burn, coast, report.
- Template **16**: a Lambert transfer to a target position.
- Template **23**: propagate to the start of a Berlin pass, report,
  propagate to its end, report.
- [`examples/hohmann_transfer.py`](../../examples/hohmann_transfer.py)
  builds a two-burn Hohmann transfer in Python. It prints, for example,
  `Final orbit: altitude 699.69 to 700.31 km (target 700 km)`.

**More detail:** User Manual sections 6 and 7,
[A tour of the Scenario Editor](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor).

---

**Next:** [Orbit keeping and formations](orbit-keeping-and-formations.md) ·
[Read the results](read-the-results.md)
