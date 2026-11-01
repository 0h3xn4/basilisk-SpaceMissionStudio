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

Not marked: a spacecraft preset's values (**New from template...**). A
preset fills dozens of fields, mass, inertia, devices, which would give a
spacecraft dozens of marks; how to record a preset is still to be
decided.

## Checked against

- `tests/test_value_marks.py`: a round trip through the file, each
  status, the paths, each rule, the provenance records.
- `tests/test_scenario_hashes.py`: every template saves, and hashes, as
  it did before marks existed.
