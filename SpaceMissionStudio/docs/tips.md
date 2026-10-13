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

On macOS, `Cmd` replaces `Ctrl`.

| Keys | Does |
|---|---|
| `Ctrl+K` | Command palette: find any menu command, tab, template or result series by a few letters ("save as", "events", "05 formation", "velocity") |
| `Ctrl+R` | Run Simulation |
| `F1` | User Manual |
| `Ctrl+Z` / `Ctrl+Shift+Z` (`Ctrl+Y` on Windows) | Undo / redo a scenario edit |
| `Ctrl+N`, `Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+S` | New, Open, Save, Save As |
| `Esc` on the Events tab | Clear the time cursor |

**Help > Keyboard Shortcuts** lists them all in the app.

## Working habits

- **Save As first.** Templates never change on disk, but your edits are
  only kept once you save them under your own name.
- **Read the Explain tab before you run.** It predicts ground passes and
  warns about things that cannot work (no sun sensor on the Sun-facing
  side, station keeping without drag, a formation law that needs more
  thrust than the thruster has). Its title shows how many warnings there
  are: "Explain (1 to check)".
- **Grow a scenario one step at a time** and run after each step, so you
  know which change changed the result.
- **Compare runs.** Run, change one thing, run again: **Compare with**
  on the Results tab overlays the earlier run and **Input differences...**
  lists exactly what changed.
- **Use orbit only while you design the orbit.** It is much faster than
  full attitude.
- **Set Record every** for runs longer than a few weeks, or the results
  fill memory.
- **Hover a field** for a short explanation; the message at the bottom of
  the Scenario Editor names the field to fix when something is invalid.
- **Write series names in your scenario's description** under "What to
  look at": they appear as **Suggested** buttons on the Results tab.

## Scripting and batch runs

- `spacemissionstudio validate` needs no Basilisk: use it in CI to check
  scenario files.
- `spacemissionstudio run ... --out-dir` and `monte-carlo` give the same
  numbers as the GUI.
- `spacemissionstudio sil ... --max-error 1e-9` exits with status 2 when
  external flight software disagrees with the simulation: a CI gate.
- The [examples](../examples/README.md) show the Python API: build a
  scenario, sweep a parameter, read a Monte Carlo batch.

## Files the app reads and writes

**Reads**

| File | Format | Where in the app |
|---|---|---|
| Scenario | JSON (`.json`) | File > Open..., `spacemissionstudio` commands |
| TLE | Two text lines, pasted | Spacecraft page, Orbit / mass |
| Orbit messages | CCSDS OPM, OMM (KVN text) | `ccsds-import`, `ccsds-validate` |
| Space weather | CelesTrak CSV or TXT | Data > Import file..., Scenario tree > Environment |
| Solar-activity prediction | NASA MSFC table (`.txt`) | Scenario tree > Environment |
| Earth orientation | NAIF Earth PCK (`.bpc`, `.cmt`) | Data > Import file..., `earth-orientation --import` |
| 3D model | Wavefront OBJ (`.obj`) | Spacecraft page, Vizard model |
| Flight-software program | An executable speaking the SIL contract | Run SIL..., `sil --binary` |

**Writes**

| File | Format | Where in the app |
|---|---|---|
| Scenario | JSON | File > Save, Save As... |
| Results | CSV, one per series, SI units, time in seconds | Results > Export CSV..., `run --out-dir` |
| Events | CSV (seconds and UTC) | Events > Export CSV..., `run` (`events.csv`) |
| Reports | CSV | Mission Output > Export CSV... |
| Provenance | JSON (versions and checksums of every input) | Beside every export |
| Plots | PNG, SVG | Results > Save PNG... / Save SVG... |
| Orbit messages | CCSDS OPM, OEM (KVN text) | `ccsds-export`, `run --oem` |
| Vizard playback | `.bin` | Vizard Configuration..., `run --vizard-save-file` |
| Monte Carlo batch | `batch_results.npz` and `.json`, plus Basilisk's archive | Run Monte Carlo..., `monte-carlo --archive-dir` |
| Monte Carlo table | CSV | Monte Carlo > Export table CSV... |
| Budget | CSV on the clipboard | Budget > Copy as CSV |
| Flight software | A C project with CMake, `ICD.md`, `TRACEABILITY.md`, `manifest.json` | Flight Software > Export..., `export-fsw` |
| SIL report | JSON and CSV | Flight Software > Save report..., `sil --report` |
| Logs | Text | `~/.spacemissionstudio/logs/` |

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
