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
| `author` | who saved it: the name set in **Settings > Change history > Author**, else your operating-system user name |
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

## The author

**Settings > Change history > Author** sets the name every save records,
in the app and on the command line alike: it is kept in a plain file,
`~/.spacemissionstudio/author.txt`. Leave it empty and saves record your
operating-system user name ("unknown" when there is none).

## Reading the history

- **In the app:** **Change History...** (the Scenario area's commands, or
  the command palette) lists every change, newest first: the time, the
  author, what saved it, the kind, the field, the old and the new value,
  and the reason. Choose a spacecraft to see its changes (and the
  scenario's created and replaced lines), or type part of a field's name
  (`dry_mass`, `orbit`). The view only reads the file. A scenario not
  saved yet has no history: it starts with the first save.
- **On the command line:**

      spacemissionstudio history mission.json [--spacecraft sat-1] [--field dry_mass]

  prints the same, newest first.

A line that is not a change (the file edited by hand, a line cut short)
is skipped and named, never removed from the file.

## Undo names the edit

Undo and Redo (the top bar, Ctrl+Z, Ctrl+Shift+Z) are labelled with the
edit they change back: "Undo dry_mass_kg (sat-1)", or "Undo 3 changes"
when one step changed several values. The tooltip gives the old and new
value, and after the step the status bar says what was undone. Undo
works on the edits since the scenario was opened; the history file keeps
what was saved.

Code: `spacemissionstudio/history.py`, `gui/change_history_dialog.py`,
`gui/undo_history.py`.
