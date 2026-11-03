# Computed and overridden values

How a scenario records a value SpaceMissionStudio computed or suggested,
and a value that replaces one on purpose (the transparency plan,
Phase 5b). Code: `spacemissionstudio/schema/scenario.py` (`ValueMark`,
`resolve_value_path`, `value_mark_status`, `value_mark_records`).

## A value mark

A scenario's `value_marks` lists them, one per value:

| Field | Meaning |
|---|---|
| `path` | The value, by field names: `sim_settings.duration_days`, `spacecraft[sat-1].orbit.inclination_deg`, `ground_stations[berlin-gs].min_elevation_deg`. A list item is named in brackets, by its `name`, or by its index in a list of unnamed records |
| `state` | `computed`: the field was filled with `value`; `overridden`: the scenario's value replaces `value` on purpose |
| `value` | The value computed or suggested, in the field's own unit |
| `source` | What computed or suggested it, for example "Sun-synchronous inclination at the orbit's a and e" |
| `reason` | Why the scenario's value replaces it; required for `overridden` |
| `author`, `time_utc` | Who marked it and when (ISO 8601), if known |

```json
"value_marks": [
  {"path": "spacecraft[sat-1].orbit.inclination_deg", "state": "overridden",
   "value": 97.59, "source": "Sun-synchronous inclination at the orbit's a and e",
   "reason": "the launcher's injection inclination", "author": "A. Engineer",
   "time_utc": "2026-11-01T09:00:00+00:00"}
]
```

## Its status

- **computed:** the scenario's value is the one computed. The comparison
  is exact: the field holds the number that was written.
- **edited:** a computed value whose field now holds another number. The
  mark then only records what was computed; it is not an error.
- **overridden:** the value replaces the computed one, for the reason
  given.

## What a changed value changes

When the field no longer holds the value computed (edited or
overridden), the note says what that changes, on a line under it, and
the provenance records the same sentences (`consequences`). Code:
`spacemissionstudio/engine/value_consequences.py`. Earth orbits given as
classical elements:

- **Inclination:** the node's J2 secular drift at the value used and at
  the value computed, `-1.5 n J2 (Req/p)^2 cos i` (the formula the
  Sun-synchronous inclination is solved from). When the value computed
  was Sun-synchronous, how fast the node now moves against the mean Sun
  (360 deg per tropical year), and how far its local time moves (1 deg is
  4 min). "Not Sun-synchronous" follows Explain's rule: beyond
  `explain.sso_tolerance_deg` (0.1 deg) of the Sun-synchronous
  inclination; within it, "Still Sun-synchronous", with the drift.
- **RAAN computed for an LTAN:** how far the node's local time moves
  (15 deg of RAAN per hour), the shorter way round.
- **Semi-major axis:** the change of the two-body period.

Any other value, or another body's orbit: its difference from the value
computed, with the unit its field name gives.

These are first-order, analytic statements; no simulation runs for
them. Checked against: `tests/test_value_consequences.py`, including that
the drift at the Sun-synchronous inclination is the Sun's, to the 0.01
deg the inclination is rounded to (within 1e-3 deg/day).

## Rules

- A mark names a field that exists and holds a number; a value is marked
  once.
- An override needs a reason. The value computed must be a finite number,
  and the source must say what computed it.
- A field that no longer holds a number (an orbit switched to a
  Cartesian state) makes the mark invalid: set the value, or remove the
  mark.
- A scenario without marks writes no `value_marks`, so it saves, and
  hashes, exactly as before; an older version of SpaceMissionStudio reads
  it. A scenario with marks is refused by an older version, which names
  the field it does not know.

## Where they are recorded

Every provenance record lists the marks, each with its status, the value
used and the value computed (`value_marks`): a run's `provenance.json`
(a long run's from the scenario as given, not a segment's copy), and the
records of a lifetime, a budget, a Monte Carlo archive and a SIL report.
Each is written only when there are marks, so the record of a scenario
without them is as before. The provenance view shows them under
Scenario. A Monte Carlo run's own record shows a dispersed value as
edited, which is what it is.

## In Explain and the results

- **Scenario › Overview (Explain):** a section "Computed and overridden
  values" counts the marks by status ("12 computed", "1 overridden"), and
  gives a note for each value used in place of the one computed: its
  path, the value used and the value computed, the reason, and what it
  changes. A value still as computed gets no note; a scenario without
  marks gets no section.
- **Results:** the provenance line under the buttons ends "· 1 value
  overridden" (or edited) when the run used one; its tooltip lists them
  as Explain does. A run that used none shows the line as before.

## In the editor

- **What marks itself:** a spacecraft's orbit, on its **Orbit / mass**
  page. **Compute Sun-sync inclination for this altitude** marks the
  inclination, and **Compute RAAN for LTAN...** the RAAN, each as
  computed. The value is the one the field holds, rounded to its 4
  decimals, and the source says from what.
- **The note under the field:** "Computed: <source>"; "Edited (computed
  <value>)" with **Give a reason...**; or "Overridden (computed <value>):
  <reason>". Its tooltip has the whole record. A field without a mark
  shows no note.
- **Give a reason...** asks why the value used replaces the computed one.
  The answer marks it overridden; Cancel or an empty answer changes
  nothing.
- **Pressing a compute button again** marks the new value computed, in
  place of the old mark.
- **A renamed spacecraft or station keeps its marks.** A removed one, or
  an orbit given another way (Cartesian, TLE), takes them with it.
- **Undo, the JSON view and saving** carry the marks with the rest of the
  scenario.

## What else marks itself

- **The template wizard:** a starter template's orbit page keeps the orbit
  Sun-synchronous at the size you choose; the inclination it recomputes
  is marked computed ("..., set by the template's wizard"). A field you
  leave as it is is not written, so it gets no mark.
- **Generate Walker constellation...:** each satellite's semi-major axis
  (the body's equatorial radius plus the altitude), RAAN (its plane) and
  mean anomaly (its slot), with the pattern, plane and slot in the
  source. With J2 in the run the generator writes osculating elements
  from the pattern's mean ones, so all six are marked, the anomaly as a
  true anomaly. The inclination is the one you typed, so it is marked
  only with J2, or when the dialog's **Sun-synchronous** button set it.

## Spacecraft made from a preset

**New from template...** records the preset once per spacecraft, in the
scenario's `presets` (`PresetRecord`): the spacecraft, the preset's name,
when, and every number it gave the spacecraft as added (`values`, by field
path: `dry_mass_kg`, `inertia_kg_m2[0]`, `sensors[st-1].params.noise_arcsec`;
the name and the orbit left out, since the orbit is set after). The
values are kept, not looked up again, so a later change to a preset never
makes an older scenario look edited.

- **Status:** each kept value is compared with the spacecraft as it is now
  (`preset_status`): as the preset gave it, changed, or gone (a device
  removed).
- **Where it shows:** a line on the spacecraft's page ("From preset
  Microsatellite (150 kg): 38 of 40 values as it gave them, 2 changed",
  the changes in its tooltip); Explain's "Computed and overridden values"
  section ("1 from a preset", a note listing up to five changes); every
  provenance record (`presets`), written only when there is one.
- **Rules:** the spacecraft must exist, the preset be named, the values be
  numbers; one record per spacecraft. A renamed spacecraft keeps it; a
  removed one takes it along.

## Values read from a file

A value read from a file keeps the file it came from, so a later change
of the file, or of the value, can be seen (the transparency plan,
Phase 8c).

- **An orbit from a CCSDS message** (`spacemissionstudio ccsds-import`):
  the scenario's `imports` (`ImportRecord`) keeps the spacecraft, what
  was set (`orbit`), the format (`ccsds_opm` or `ccsds_omm`), the file's
  absolute path and SHA-256, when and who, and every value as it was read
  (`values`: the orbit's numbers and text, a TLE's lines included). A
  second import of the same orbit replaces the record.
- **Mass properties from a file** (the model's **Import file...**): the
  mass properties keep the file's name and SHA-256, as before, and now its
  absolute path (`source_path`), written only when there is one.
- **Meshes** (`.obj`) already keep their SHA-256; a changed one is a
  warning when the model is built.

**Status:** the file is hashed again: unchanged, changed or missing
(`file_state`); an orbit's values are compared with those read
(`import_status`), each one changed named. **Where it shows:** a changed
file is the pre-run warning `import.source_changed`, a missing one
`import.source_missing` (with the other pre-run warnings: the app's
**to check**, `validate`); every run's provenance (`imports`, written only
when there is one) records each import with the file's state when the
run started and the values edited since. The run uses the values in the
scenario either way: a warning does not stop it. **Rules:** the
spacecraft must exist, the target and format be known, the SHA-256 be 64
hex digits; one record per spacecraft and target. A renamed spacecraft
keeps it; a removed one takes it along.

## Checked against

- `tests/test_imports.py`: the record of an import, a changed and a
  missing file, values edited since, a rename, the file saved only with
  records, the mass properties file's path, the run's provenance.

- `tests/test_value_marks.py`: a round trip through the file, each
  status, the paths, each rule, the provenance records.
- `tests/test_scenario_hashes.py`: every template saves, and hashes, as
  it did before marks existed.
