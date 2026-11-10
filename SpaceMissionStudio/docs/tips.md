# Tips

Shortcuts and habits that save time, and every file the app reads and
writes, so you can move data to and from other tools.

## Contents

- [Keyboard and palette](#keyboard-and-palette)
- [Working habits](#working-habits)
- [Scripting and batch runs](#scripting-and-batch-runs)
- [Files the app reads and writes](#files-the-app-reads-and-writes)
- [Other tools](#other-tools)

## Keyboard and palette

| Keys | Does |
|---|---|
| `Ctrl+K` | Command palette (also the top bar's search): find any command, area, page, spacecraft, setting, template or result series by a few letters ("save as", "events", "sat-1", "05 formation", "velocity") |
| `Ctrl+R` | Run, in the mode beside it (Single run, Monte Carlo, SIL) |
| `Esc` | Cancel the run |
| `F1` | User Manual |
| `Ctrl+Z` / `Ctrl+Shift+Z` (`Ctrl+Y` on Windows) | Undo / redo a scenario edit (the menu names the edit: "Undo dry_mass_kg (sat-1)") |
| `Ctrl+J`, `Ctrl+I` | Show or hide the Problems panel, the Inspector |
| `Ctrl+1` to `Ctrl+6` | Go to Home, Scenario, Run, Results, Timeline, Reports |
| `Ctrl+N`, `Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+S` | New, Open, Save, Save As |
| `Esc` in the Timeline, `Alt+Backspace` anywhere | Clear the time cursor |
| `Alt+Right` / `Alt+Left` in Results (with `Shift`: ten) | Move the time cursor a sample |
| `Alt+PgDown` / `Alt+PgUp`, `Alt+Home` / `Alt+End` in Results | The time cursor to the next or previous event, or the run's start or end |

In the Scenario area's JSON page (**Form · JSON**), while the text has
the focus:

| Keys | Does |
|---|---|
| `Ctrl+Space` | Suggest what can be typed at the cursor (fields, choices, names) |
| `Ctrl+Shift+Space` | Describe the key at the cursor: type, default, unit, meaning |
| `F8` / `Shift+F8` | Go to the next / previous problem |
| `F2` | Rename the spacecraft, ground station or 3D model part at the cursor, everywhere |
| `F12` | Go to where the name at the cursor is defined |
| `Ctrl+.` | Quick fixes for the key or value at the cursor |
| `Shift+Alt+F` | Lay the text out again |

**Settings > Keyboard** (`Ctrl+/`) lists every command's shortcut in the
app (the JSON page's keys are in its right-click menu), and
**Reports > Exports** lists the exports and where each is made.

## Working habits

- **Save As first.** Templates never change on disk, but your edits are
  only kept once you save them under your own name.
- **Read Explain (Scenario › Overview) before you run.** It predicts ground passes and
  warns about things that cannot work (no sun sensor on the Sun-facing
  side, station keeping without drag, a formation law that needs more
  thrust than the thruster has). Its title shows how many warnings there
  are: "Overview (1 to check)".
- **Grow a scenario one step at a time** and run after each step, so you
  know which change changed the result.
- **Compare runs.** Run, change one thing, run again: **Results > Compare**
  shows what changed in the inputs and in the results, with the
  differences, and **Compare with** in Results overlays the
  earlier run. Runs are saved, so you can compare with yesterday's.
- **Use orbit only while you design the orbit.** It is much faster than
  full attitude.
- **Set Record every** for runs longer than a few weeks, or the results
  fill memory.
- **Hover a field** for a short explanation; the message at the bottom of
  the Scenario area names the field to fix when something is invalid.
- **Write series names in your scenario's description** under "What to
  look at": they appear as **Suggested** buttons in Results.

## Scripting and batch runs

- `spacemissionstudio validate` needs no Basilisk: use it in CI to check
  scenario files.
- `spacemissionstudio run ... --out-dir` and `monte-carlo` give the same
  numbers as the GUI.
- `spacemissionstudio sil ... --max-error 1e-9` exits with status 5 when
  external flight software disagrees with the simulation: a CI gate. An
  internal error exits 4.
- `spacemissionstudio run ... --bundle` and `spacemissionstudio reproduce`
  make a result folder anyone can run again and compare.
- `spacemissionstudio.api` ([The Python API](api.md)) gives a script the
  same lifetime, budget, run, comparison, design checks, model analyses
  and re-entry estimate the app computes.
- The [examples](../examples/README.md) show the engine from Python: build a
  scenario, sweep a parameter, read a Monte Carlo batch.

## Files the app reads and writes

**Reads**

| File | Format | Where in the app |
|---|---|---|
| Scenario | JSON (`.json`) | Open... (Ctrl+O), `spacemissionstudio` commands |
| TLE | Two text lines, pasted | Spacecraft page, Orbit / mass |
| Orbit messages | CCSDS OPM, OMM (KVN text) | Spacecraft page, Orbit / mass > Import CCSDS OPM/OMM..., `ccsds-import` |
| Orbit messages to check | CCSDS OPM, OMM, OEM (KVN text) | Check a CCSDS File... (`Ctrl+K`), `ccsds-validate` |
| Space weather | CelesTrak CSV or TXT | Reference data > Import file..., Scenario tree > Environment |
| Solar-activity prediction | NASA MSFC table (`.txt`) | Scenario tree > Environment |
| Earth orientation | NAIF Earth PCK (`.bpc`, `.cmt`) | Reference data > Import file..., `earth-orientation --import` |
| 3D model | Wavefront OBJ (`.obj`, with its `.mtl`) | 3D Model... > Import .obj... |
| Mass properties | JSON or CSV | 3D Model... > Mass properties > Import file... |
| IDM-CIC model | `.idm` (IDM-CIC is © CNES; read only) | 3D Model... > Import IDM-CIC model..., `idm-import`, `idm-info` |
| Flight-software program | An executable speaking the SIL contract | Run in SIL mode, `sil --binary` |
| Project configuration | YAML (`config_file` in the scenario) | Scenario › Assumptions, `assumptions` |
| Atmosphere gases data | ITU-R P.676-13 Part 1 (`.txt`) | Reference data > Import file..., `gaseous-attenuation --import` |
| Small-body ephemeris | NAIF `eros_1900_2100.bsp` | Reference data > Import file..., `small-bodies --import` |
| Plugins | Python packages declaring the entry point `spacemissionstudio.models` | Loaded at start-up ([Plugins](user-manual/plugins.md)) |
| Reproduction bundle | A folder written by `run --bundle` | `reproduce` |

**Writes**

| File | Format | Where in the app |
|---|---|---|
| Scenario | JSON | Save (Ctrl+S), Save As... (Ctrl+Shift+S) |
| Results | CSV, one per series, SI units, time in seconds | Results > Plots > Export CSV..., `run --out-dir` |
| Events | CSV (seconds and UTC) | Timeline > Export CSV..., `run` (`events.csv`) |
| Reports | CSV | Results > Output > Export CSV... |
| Provenance | JSON (versions and checksums of every input) | Beside every export |
| Scenario as run | JSON (`scenario_as_run.json`) | `run --out-dir`, beside the results |
| Reproduction bundle | Folder: results, provenance, the scenario as run and copies of the files it refers to (`bundle.json`) | Results > Plots > Export all... > Reproduction bundle..., `run --bundle` |
| Lifetime and budget records | JSON, with inputs, traces and provenance | End of Life > Export JSON..., `lifetime --out`, `budget --out` |
| Design checks, model analyses | JSON record and a CSV per table, with provenance | Run > Design Checks > Save..., Results > Model Analyses > Save..., `check-design --out --tables`, `model-analyses --out --tables` |
| Re-entry estimate | JSON, with provenance | Run > End of Life > Re-entry casualty > Save..., `reentry --out` |
| Change history | `mission.history.jsonl` beside `mission.json` | Every save; Change History... |
| Plots | PNG, SVG | Results > Plots > Save PNG... / Save SVG... (the selected plot), Export all... (every shown plot, with CSV) |
| Orbit messages | CCSDS OPM, OMM, OEM (KVN text) | Export Orbits as CCSDS... (`Ctrl+K`), Results > Plots > Export all... > CCSDS ephemeris (OEM)..., `ccsds-export`, `run --oem` |
| Monte Carlo batch | `batch_results.npz` and `.json`, plus Basilisk's archive | Run in Monte Carlo mode, `monte-carlo --archive-dir` |
| Monte Carlo table | CSV | Results > Monte Carlo > Export table CSV... |
| Budget | CSV on the clipboard | Run > Budget > Copy as CSV |
| 3D model | Wavefront OBJ and `.mtl` | 3D Model... > Export .obj..., `model --export-obj` |
| Flight software | A C project with CMake, `ICD.md`, `TRACEABILITY.md`, `manifest.json` | Reports > Flight Software > Export..., `export-fsw` |
| SIL report | JSON and CSV | Reports > Flight Software > Save report..., `sil --report` |
| Logs | Text | `~/.spacemissionstudio/logs/` |
| Network log | Text, one line per network use allowed or refused | `~/.spacemissionstudio/logs/network.log` |
| Offline choice | JSON | `~/.spacemissionstudio/network.json` (**Settings > Network**) |

## Other tools

SpaceMissionStudio has **no direct integration** with Harness Design
Studio, Requirements Studio, Budget Studio, AIT Logbook or ICD Studio: it
neither imports from nor exports to them, and has no format made for
them. If
one of them reads one of the formats above (CSV, JSON, CCSDS, or the
flight-software export's `ICD.md`), that is the way to move data across.
For other flight-dynamics tools, CCSDS messages are the standard route
(see [Orbit files](user-manual/orbit-files.md) for GMAT's limits).

---

**Next:** [How-to guides](user-manual/README.md) ·
[Use the command line](user-manual/command-line.md) ·
[FAQ](faq.md)
