# Exchange orbits with other tools (CCSDS and TLE)

How to bring a real orbit in (a TLE or a CCSDS message), and how to hand
your orbits to other tools as standard CCSDS files.

## Start from a TLE

In the spacecraft editor, **Orbit / mass** tab, choose the TLE orbit type
and paste the two lines (from [CelesTrak](https://celestrak.org), for
example). The app propagates the TLE with SGP4 to the scenario's epoch and
converts it to the simulation's frame. The Explain tab warns when the
TLE's epoch is more than 3 days from the scenario's: SGP4 grows less
accurate the further it propagates.

## CCSDS orbit messages

CCSDS 502.0-B-3 defines three text (KVN) messages that flight-dynamics
tools, GMAT among them, read and write:

| Message | Holds | The app can |
|---|---|---|
| OPM (Orbit Parameter Message) | One state: position and velocity at an epoch | write, read, check |
| OMM (Orbit Mean-elements Message) | Mean elements, for example a TLE | read, check |
| OEM (Orbit Ephemeris Message) | A trajectory: many states over time | write, check |

These are command-line features; the GUI has no CCSDS menu yet.

### Write

```console
$ spacemissionstudio ccsds-export spacemissionstudio/scenarios/templates/22_starter_first_leo_satellite.json --out opm
wrote opm/my-sat.opm
```

One OPM per spacecraft, with the starting state in EME2000 and UTC, plus
the osculating Keplerian elements. To write the whole trajectory instead,
add `--oem` to a run:

```bash
spacemissionstudio run scenario.json --out-dir out --oem
```

`--oem-stride N` keeps every Nth state.

**For GMAT:** GMAT R2026a reads only OEM version 1.0 with Lagrange
interpolation, and the app writes version 3.0 (the current standard).
Write with `--oem-interpolation lagrange`, then change the first line to
`CCSDS_OEM_VERS = 1.0` in a copy for GMAT; that is how the app's OEMs
were checked against GMAT.

### Read

```console
$ spacemissionstudio ccsds-import opm/my-sat.opm scenario.json --spacecraft my-sat --out scenario2.json
my-sat: orbit set from opm/my-sat.opm -> scenario2.json
```

An OPM sets the spacecraft's starting orbit; an OMM with TLE mean elements
sets a TLE orbit. If the message's epoch differs from the scenario's, it
stops and says so; `--set-epoch` moves the scenario to the message's
epoch. Without `--out` the scenario file is overwritten.

### Check

```console
$ spacemissionstudio ccsds-validate opm/my-sat.opm
opm/my-sat.opm: conforms
```

A file that breaks the standard gets a list of conformance errors
instead. An OEM cannot be imported: it is a trajectory, not a starting
state. Which parts of the standard are covered
is in the
[implementation conformance statement](../../compliance/ics_ccsds_502.csv).

## Results as CSV

Every run also writes plain CSV files in SI units
([Read the results](read-the-results.md)), which any spreadsheet or
analysis tool reads.

---

**Next:** [Reference data](reference-data.md) ·
[Use the command line](command-line.md)
