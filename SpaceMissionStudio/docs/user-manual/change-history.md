# The change history

Every save of a scenario records what it changed, in a file beside it:
`mission.json` gets `mission.history.jsonl`. The scenario file itself is
unchanged, so it stays clean for version control; keep the history file
with it (or not: nothing reads it to run).

## What is recorded

One line per value that a save changes, with:

| Field | What it holds |
|---|---|
| `time_utc` | when it was saved |
| `author` | who saved it: your operating-system user name (a name of your own comes with Settings, next) |
| `source` | `app`, or the command that saved it (`spacemissionstudio generate-constellation`, ...) |
| `kind` | `created` (the first save), `edit`, `override` or `replaced` |
| `path` | the value's place in the scenario file, as `spacecraft[sat-1].dry_mass_kg` |
| `old`, `new` | its value before and after |
| `reason` | why: for an override, the reason you gave it (**Give a reason...**), which an override must have |

A change is found by comparing the file on disk with what is saved, so it
is recorded the same whether it was made in a form, in the JSON view or by
a command. A save that changes nothing writes nothing. The lines are
only ever added to; nothing rewrites them.

- **An override** is a value you marked overridden
  ([Computed and overridden values](../models/value-marks.md)): its line
  has `kind` `override` and the reason you gave.
- **The marks and preset records** themselves are not lines: they are the
  record of those values, already in the scenario file.
- **A file that was not a scenario** (unreadable, not JSON) and is then
  saved over gets one `replaced` line.
- **A history that cannot be written** (a read-only folder, a full disk)
  does not stop the save: the app says so, and the command line warns.

## An example

```json
{"author": "ana", "format": 1, "kind": "created", "new": "my mission", "old": null, "path": "", "reason": "", "source": "app", "time_utc": "2026-11-02T12:00:00Z"}
{"author": "ana", "format": 1, "kind": "edit", "new": 120.0, "old": 100.0, "path": "spacecraft[sat-1].dry_mass_kg", "reason": "", "source": "app", "time_utc": "2026-11-02T12:05:00Z"}
{"author": "ana", "format": 1, "kind": "override", "new": 98.0, "old": 97.8, "path": "spacecraft[sat-1].orbit.inclination_deg", "reason": "launcher's injection", "source": "app", "time_utc": "2026-11-02T12:06:00Z"}
```

Code: `spacemissionstudio/history.py`. A History view in the app, and a
name of your own as the author, come next (the transparency plan,
Phase 7).
