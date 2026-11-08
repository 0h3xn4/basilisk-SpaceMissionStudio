# The JSON page as a code editor

The Scenario area's **Form · JSON** toggle (UI overhaul M4b, U-16) shows
the scenario as the text it is saved as, editable. It was a plain text
box that marked only the line where the text stops being JSON. The user
asked for what a programmer's editor gives: syntax highlighting, the
errors and warnings marked where they are, code completion, and
refactoring. This note records how it is built and in which steps.

## Steps

1. **Highlighting and problems in place** (this step): syntax colours,
   line numbers, the current line and matching bracket, the scenario's
   problems underlined at their key or value with the message on hover
   and under the text, F8 between them, Enter keeping the indentation.
2. **Completion and hover help**: the keys allowed at the cursor, the
   fixed choices of a value, the names the scenario already has (parts,
   ground stations, spacecraft), each with its type, default and unit;
   the same help when pointing at a key.
3. **Refactoring**: rename a spacecraft, part, device or ground station
   everywhere it is named; go from a name to its definition; format the
   document; quick fixes for common problems.

## Decisions

| ID | Decision | Why |
|---|---|---|
| JE-01 | **Built on Qt's own text editor**, not an embedded web editor (Monaco). `gui/code_editor.py`'s `JsonEditor` is a `QPlainTextEdit` with a `QSyntaxHighlighter`, a line-number gutter and extra selections; `gui/json_positions.py` (no Qt) reads where each value of the text is. | The scenario's own validation stays the one source of the problems (a JSON Schema in a web editor would check less, and its markers would have to be fed from ours anyway); nothing is added to the packages (no JavaScript bundle to ship offline and keep up to date); it follows the theme, the keyboard rules and the accessibility work of the rest of the GUI, and pytest-qt tests it like the rest. Folding, multiple cursors and a minimap, which Monaco would give, are left out. |
| JE-02 | **A problem is marked where the Problems list says it is.** `problem_location.locate` already turns each message into an area, a spacecraft or station name and a field path (`sensors[gyro].mount.position_m[0]`); `json_path` follows that path through the text's data (a list item by its `name`, an index, a key) as deep as it exists, and `mark_span` marks a plain value itself, an object or list by its key, a list item by its name. A message that names no place is not marked (it stays in Problems). | One rule for where a problem is, shared with the forms and Problems, so the JSON page cannot disagree with them. Marking a key rather than a whole block keeps a problem about a spacecraft's `power` from underlining fifty lines. |
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
