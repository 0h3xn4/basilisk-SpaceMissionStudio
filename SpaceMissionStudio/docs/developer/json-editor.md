# The JSON page as a code editor

The Scenario area's **Form · JSON** toggle (UI overhaul M4b, U-16) shows
the scenario as the text it is saved as, editable. It was a plain text
box that marked only the line where the text stops being JSON. The user
asked for what a programmer's editor gives: syntax highlighting, the
errors and warnings marked where they are, code completion, and
refactoring. This note records how it is built and in which steps.

## Steps

1. **Highlighting and problems in place** (done): syntax colours,
   line numbers, the current line and matching bracket, the scenario's
   problems underlined at their key or value with the message on hover
   and under the text, F8 between them, Enter keeping the indentation.
2. **Completion and hover help** (done): the keys allowed at the cursor, the
   fixed choices of a value, the names the scenario already has (parts,
   ground stations, spacecraft), each with its type, default and unit;
   the same help when pointing at a key.
3. **Refactoring** (done): rename a spacecraft, ground station or 3D
   model part everywhere it is named; go from a name to its definition;
   format the document; quick fixes for a wrong key, a value that is not
   one of its choices and a name that does not exist.

## Decisions

| ID | Decision | Why |
|---|---|---|
| JE-01 | **Built on Qt's own text editor**, not an embedded web editor (Monaco). `gui/code_editor.py`'s `JsonEditor` is a `QPlainTextEdit` with a `QSyntaxHighlighter`, a line-number gutter and extra selections; `gui/json_positions.py` (no Qt) reads where each value of the text is. | The scenario's own validation stays the one source of the problems (a JSON Schema in a web editor would check less, and its markers would have to be fed from ours anyway); nothing is added to the packages (no JavaScript bundle to ship offline and keep up to date); it follows the theme, the keyboard rules and the accessibility work of the rest of the GUI, and pytest-qt tests it like the rest. Folding, multiple cursors and a minimap, which Monaco would give, are left out. |
| JE-02 | **A problem is marked where the Problems list says it is.** `problem_location.locate` already turns each message into an area, a spacecraft or station name and a field path (`sensors[gyro].mount.position_m[0]`); `json_path` follows that path through the text's data (a list item by its `name`, an index, a key) as deep as it exists, and `mark_span` marks a plain value itself, an object or list by its key, a list item by its name. A message that names no place is not marked (it stays in Problems). | One rule for where a problem is, shared with the forms and Problems, so the JSON page cannot disagree with them. Marking a key rather than a whole block keeps a problem about a spacecraft's `power` from underlining fifty lines. |
| JE-04 | **What fits at a place comes from the schema's own records.** `schema/fields.py` follows a path of the text from `Scenario` through the record classes (`record_at`): a field typed as a record (optional or not), and a list whose items are records (`LIST_ITEMS`, a table, since the type hints say only `list`). A field's fixed choices are the constants the validation checks it against (`CHOICES`, read at run time), and the names it may refer to (a spacecraft, a ground station, a part, a material) are read from the scenario as last read (`REFERENCES`, `names`). Free keys (a device's `params`, `fsw_params`) and the mission sequence's commands (their fields depend on their `type`) are not offered. | The records are the definition of the file, so what is offered cannot drift from what is accepted. `tests/test_schema_fields.py` checks every object of every template against the record `record_at` gives, every `CHOICES` constant against the validation, and that each list whose comment names a record is in `LIST_ITEMS`. |
| JE-05 | **The help is the source's comment on each field, generated into `schema/field_help.json`** (`scripts/build_field_help.py`): the comment at the end of the field's line, with the comment lines under it that go on in lower case, else the comment block above it. It ships as package data. | An installed program has no source to read the comments from. The comments already give each field's unit, range and meaning (the ICD's field table is built from them). `tests/test_schema_fields.py` checks that the file is what the script writes, so a changed comment fails until the file is rebuilt. |
| JE-06 | **Completion is offered, never forced.** Ctrl+Space, or typing inside a key or a string value, opens a list of what fits (starting with the text typed, then containing it); Enter or Tab inserts, Escape closes; typing outside a string never opens it. A new key is inserted with its default (or an empty value of its type), selected so that typing replaces it. The key under the cursor is described under the text (its first lines, shortened to 240 characters), in full on hover and with Ctrl+Shift+Space. | A list that pops up over numbers would get in the way of typing values; inside a string something is being named, which is when a choice helps. Under the text, the description is there for the keyboard and screen readers, not only for the mouse (WCAG 2.1.1). |
| JE-07 | **Rename uses the forms' own rename** (`schema.references.rename_spacecraft`, `rename_ground_station`, `rename_part`) on the scenario the text holds, and puts back the text as the file is saved, as one edit (one Undo). A name is found at a place as a record's own `name` (a spacecraft, a ground station, a part) or a field that refers to one (`fields.REFERENCES`, a mission step's `spacecraft`/`ground_station`, `fsw_params.target_ground_station`). The new name is checked as the forms check it (`name_error`). Devices and materials are not renamed: an import record keeps device names inside value paths, and no rename of materials exists yet. | One list of reference sites (`references.py`'s, hand-listed and audited) for every way of renaming, so the JSON page cannot miss one the forms update (value marks, presets, import and export records, mission steps, dotted assignment targets). The text is written back in the saved layout, which is what the page shows to begin with; free text (a description) is not changed, as in the forms. |
| JE-08 | **Keys a record does not have are marked and fixable.** Text with such a key cannot be applied (the banner names the key but not its place); `json_refactor.unknown_keys` marks it where it is, with the field it is closest to. Ctrl+. offers: for such a key, the closest free fields and its removal (with its comma); for a value outside its field's choices, each choice (closest first); for a name that does not exist, the existing names. Nothing is fixed without being chosen. | The common mistakes in hand-edited JSON are a misspelt key or value; the schema already knows what was meant to be there. |
| JE-09 | **The editor's keys win while it has the focus** (F2, F12, F8, Ctrl+., Ctrl+Space, Ctrl+Shift+Space, Shift+Alt+F: a `ShortcutOverride` accepted), none of which the window uses; each is also in the editor's right-click menu with its key. Format Document lays the text out as the file is saved (two spaces), keeping the keys' order and the values. | The keys programmers' editors use for the same commands; the menu makes them findable without knowing the keys. |
| JE-10 | **Inside `params`, the keys of the kind beside them.** A device's `params` offer the parameters its form offers for its `kind` (`sensor_actuator_editor`'s per-kind specs, with the wheel and thruster models as choices); a mission step (a `schema.command.Command`, now a record of `fields.record_at`) offers its own fields and, in its `params`, those its `kind` reads (`fields.COMMAND_PARAMS`, with their choices and the spacecraft and station names they refer to). A step param its kind does not read is marked as a warning (it would be ignored) with its fixes; a device's are not checked, since its form lists the usual parameters, not every one Basilisk takes. | The two places a user types most by hand had no help. The step table is checked against the names `Command`'s validation reads, so it cannot drift; the device list is the form's, so the page and the form offer the same. |
| JE-03 | **The syntax colours are the theme's words colours** (`code.key` = `text.link`, `code.string` = `status.normal.text`, `code.number` = `status.serious.text`, `code.literal` = `status.standby.text`, `code.punctuation` = `text.secondary`), with a current line and a matched bracket light enough to keep each at 4.5:1 (`code.current_line`, `code.bracket`; `bg.hover` and `accent.soft` do not). The pairs are in `CONTRAST_PAIRS`. A problem's message is also given in words under the text for the cursor's place, and F8 / Shift+F8 move between problems, so neither the colour of the underline nor a mouse hover is needed. | WCAG 2.2 AA (1.4.1, 1.4.3, 2.1.1), as everywhere else in the GUI. |

## How it works

- `json_positions.tokens(text)` splits a text into strings (a key when a
  colon follows), numbers, literals and punctuation, with their places;
  the highlighter runs it on each line (a JSON string cannot span
  lines). `index(text)` reads every value with the place of its key and
  of itself, by path, and stops where the text stops being JSON, so a
  text being typed still gives what comes before. On the largest
  template (30 kB) it takes about 4 ms.
- `ScenarioJsonView.set_problems` takes the Problems list's
  `(severity, message)` pairs on every validation
  (`ScenarioEditor._update_problem_counts`) and marks them while the
  text shows the scenario; a mark is a `QTextCursor` selection, so it
  follows the text while an edit is typed and is replaced once the edit
  is applied and validated. Text that is not JSON keeps its own mark:
  the line shaded and the place underlined with the parser's reason.
- `JsonEditor` draws the gutter (line numbers, a dot in the worst
  problem's colour on each line with one), the current line, the
  matched bracket (bold, on `code.bracket`) and the wavy underlines; its
  tooltip and `problem_at_cursor` give the messages at a place.

Completion and help (step 2):

- `json_positions.context_at(text, position)` reads the text up to the
  place with a stack of the objects and lists open there: a key being
  typed (or to start) of the object at a path, or the value of a key or
  a list item, with the word typed so far and the characters a
  completion replaces (with the closing quote when there is one); the
  keys the object has, before and after the place, are not offered again.
- `json_assist.completions` turns that into what is offered
  (`schema.fields`); `help_at` describes the key at a place.
- `JsonEditor` shows them in a `QCompleter` list; `ScenarioJsonView`
  hands it the scenario as last read (for the names) and shows the key's
  description under the text when no problem is there.

Refactoring (step 3): `gui/json_refactor.py` (no Qt) finds the name at a
place, its definition, renames, formats, marks unknown keys and lists
quick fixes; `JsonEditor` has the keys, the right-click menu and the
quick-fix menu; `ScenarioJsonView.rename_at_cursor` asks for the new name
and says what was renamed (a toast, and the Log).

Inside `params` (JE-10): `json_assist.fields_at` gives the fields an
object can hold, its record's or, for `params`, those of the `kind`
read beside it; completion, help and the quick fixes use it, and
`json_refactor.unknown_keys` marks a step param its kind does not read.

## Tests

`tests/test_json_positions.py`: the tokens, every value of every template
read back from its place, a text cut short, field paths, a problem's
place (by name, index and key, the deepest that exists, a real
validation message), what is marked, and the matching bracket.
`tests/gui/test_json_editor.py`: the colours from the theme and after a
theme change, the gutter, the bracket marks, problems underlined in
their colour with a dot, the message at the cursor and F8 / Shift+F8, a
mark following the text, Enter's indentation, and template 22's JSON
page marking a dry mass of -1 kg on its value.

Step 2: `tests/test_schema_fields.py` (the help file, records at paths,
every template's objects against their records, choices, descriptions,
names), `tests/test_json_assist.py` (the context of a place, keys with
defaults, choices, names, booleans, a key's help), and in
`tests/gui/test_json_editor.py` the orbit type's choices chosen with the
keyboard, Ctrl+Space in a new sensor and Escape, and a key's description
under the text.

Step 3: `tests/test_json_refactor.py` (the name at a place, its
definition, renaming a spacecraft and a part with their references and
the names refused, formatting, unknown keys and their fixes, choices and
names), and in `tests/gui/test_json_editor.py` F2 renaming in template 05
with Undo, F12 and Ctrl+., and a misspelt key marked and the text
formatted with Shift+Alt+F.

Inside `params`: `tests/test_schema_fields.py` checks each step kind's
params against what its validation reads; `tests/test_json_assist.py`
offers a wheel's, a star tracker's and a maneuver's params, their
choices, names and help; `tests/test_json_refactor.py` marks and fixes a
misspelt step param and a wheel model.
