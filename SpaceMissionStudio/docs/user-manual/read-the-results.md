# Read the results

How to find what a run produced: plots, events, reports, the time cursor
and the exported files.

## Where things are

| Where | What it shows | Needs a run? |
|---|---|---|
| **Results > Plots** | A catalog of the run's plots and a grid of up to six, with a readout | Yes |
| **Results > Dashboard** | Pointing mode, power and link at a glance (for a comms-pointing spacecraft) | Yes |
| **Results > Output** | What each `report` command in a Mission Sequence recorded | Yes |
| **Results > Monte Carlo** | The spread of a batch (only when Monte Carlo is on) | A batch |
| **Events** | Passes, eclipses, burns and mode changes, as a timeline and a table | Yes |
| **Compare** | This session's runs, and the inputs that differ between two of them | Two runs |
| **Log** | What the app logged in this session; a failed run opens it | No |
| **Scenario > End of Life** | Orbital lifetime and deorbit check | No |
| **Scenario > Budget** | Delta-V and propellant budget | No (better after a run) |
| **Scenario > Flight Software** | Export the flight software, or run it in the loop | No |
| Side panel: **Inspector** | The field you are in: its value, accepted range and help | No |
| Side panel: **Explain** | What the scenario is set up to do, and warnings before you run | No |
| Side panel: **Problems** | What does not validate or looks implausible; double-click one to go to its field | No |
| **Reference data** dialog (status bar) | Every reference data file, its status and where it came from | No |

## Find a plot

1. On **Results**, type a few letters in **Search plots**, for example
   `altitude` or `rw_speeds`, and press Enter, or click a plot in the
   catalog. Hover an entry to see its code name (for example
   `sat-1.position_N`), which is also its CSV file name.
2. Or click one of the **Suggested** buttons: the series the scenario's
   description points at.
3. Tick more plots to see them together (up to six); **Layout** sets the
   grid. Zooming one zooms them all. The grid is kept for the scenario.
4. **X-axis** switches every plot between elapsed time, the calendar date
   and the orbit number. **Events** draws eclipses, passes and burns
   behind the lines.
5. Point at a plot: the readout under the catalog lists every shown
   value at that moment, with units.

## Compare two runs

Run again after a change. **Compare with** then draws the same series from
an earlier run, dashed. **Input differences...** lists every input that
differs between the two runs. The last five runs are kept until the app
closes.

![The Events tab after a run of template 22: a timeline of the Berlin passes and the eclipses, above a table of every event](../images/events_tab.png)

## Look at one moment

Click a plot, or click on the **Events** timeline, to set the **time
cursor**. A red line marks it on every view; the Events tab says what is
in progress then, and Mission Dashboard shows the values at that moment.
**Run > Clear Time Cursor** removes it.

## Save what you see

| Button | Writes |
|---|---|
| Results: **Export CSV...** | Every series, in SI units, one `.csv` per series |
| Results: **Save PNG...** / **Save SVG...** | The selected plot (click a plot to select it) |
| Results: **Export all...** | Every shown plot as PNG or SVG, with its data as CSV and `provenance.json` |
| Events: **Export CSV...** | The events shown, in seconds and UTC |
| Mission Output: **Export CSV...** | Every report, in SI units |

Every export records its provenance: the software versions and the
checksum of every input, so you can tell later exactly what produced it.
The Results export writes a `provenance.json` into its folder; the
Events and Mission Output exports write `<file>.provenance.json` beside
the CSV; PNG and SVG files carry it inside the image.

## From the command line

`spacemissionstudio run scenario.json --out-dir out` writes the same CSV
files, `events.csv` and `provenance.json` into `out/`.

**More detail:** User Manual section 7,
[Reading the Results tab](../../USER_MANUAL.md#7-reading-the-results-tab).

---

**Next:** [Use the command line](command-line.md) ·
[Monte Carlo](monte-carlo.md)
